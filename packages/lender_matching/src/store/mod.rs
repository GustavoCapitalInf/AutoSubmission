//! The one SQLite database. `Store::read` and `Store::write` run a closure inside one transaction;
//! a write is `BEGIN IMMEDIATE` and commits only when the closure returns `Ok`.

pub mod auth;

use std::collections::BTreeSet;
use std::ops::Deref;
use std::path::Path;
use std::sync::Mutex;
use std::time::Duration;

use rusqlite::{Connection, OptionalExtension, TransactionBehavior, params};
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

use crate::criteria::{LenderId, LenderRecord, RECORD_FORMAT};
use crate::facts::application::{Industries, IndustryId};
use auth::{AdminUser, MachineClient, NewSession, Role, Scope};

const MIGRATIONS: [&str; 1] = [include_str!("schema.sql")];

const SESSION_HOURS: i64 = 12;

#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error("database: {0}")]
    Sqlite(#[from] rusqlite::Error),
    #[error("the database is at schema {found}, newer than this build's {known}")]
    NewerSchema { found: u32, known: u32 },
    #[error("a stored row is unreadable: {0}")]
    Corrupt(String),
    #[error("the database lock was poisoned by a panic")]
    Poisoned,
}

pub struct Store {
    conn: Mutex<Connection>,
}

impl Store {
    pub fn open(path: &Path) -> Result<Store, StoreError> {
        Store::setup(Connection::open(path)?)
    }

    #[cfg(test)]
    pub fn open_in_memory() -> Store {
        Store::setup(Connection::open_in_memory().unwrap()).unwrap()
    }

    fn setup(mut conn: Connection) -> Result<Store, StoreError> {
        conn.busy_timeout(Duration::from_secs(5))?;
        conn.pragma_update(None, "foreign_keys", true)?;
        conn.pragma_update_and_check(None, "journal_mode", "WAL", |_| Ok(()))?;
        let current: u32 = conn.pragma_query_value(None, "user_version", |row| row.get(0))?;
        let known = u32::try_from(MIGRATIONS.len()).expect("few migrations");
        if current > known {
            return Err(StoreError::NewerSchema { found: current, known });
        }
        for (version, sql) in (1..=known).zip(MIGRATIONS).skip(current as usize) {
            let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate)?;
            tx.execute_batch(sql)?;
            tx.pragma_update(None, "user_version", version)?;
            tx.commit()?;
        }
        Ok(Store { conn: Mutex::new(conn) })
    }

    pub fn read<R>(&self, f: impl FnOnce(&ReadTx) -> Result<R, StoreError>) -> Result<R, StoreError> {
        let mut conn = self.conn.lock().map_err(|_| StoreError::Poisoned)?;
        let tx = conn.transaction_with_behavior(TransactionBehavior::Deferred)?;
        f(&ReadTx { conn: &tx })
    }

    /// Runs `f` like `write` and always rolls back: a dry run of a write.
    pub fn rehearse<R, E: From<StoreError>>(&self, f: impl FnOnce(&WriteTx) -> Result<R, E>) -> Result<R, E> {
        let mut conn = self.conn.lock().map_err(|_| StoreError::Poisoned)?;
        let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate).map_err(StoreError::from)?;
        f(&WriteTx { read: ReadTx { conn: &tx } })
    }

    pub fn write<R, E: From<StoreError>>(&self, f: impl FnOnce(&WriteTx) -> Result<R, E>) -> Result<R, E> {
        let mut conn = self.conn.lock().map_err(|_| StoreError::Poisoned)?;
        let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate).map_err(StoreError::from)?;
        let result = f(&WriteTx { read: ReadTx { conn: &tx } })?;
        tx.commit().map_err(StoreError::from)?;
        Ok(result)
    }
}

pub fn now() -> OffsetDateTime {
    OffsetDateTime::now_utc()
}

pub fn time_text(time: OffsetDateTime) -> String {
    time.format(&Rfc3339).expect("UTC times format as RFC 3339")
}

pub fn parse_time(text: &str) -> Result<OffsetDateTime, StoreError> {
    OffsetDateTime::parse(text, &Rfc3339).map_err(|_| StoreError::Corrupt(format!("not an RFC 3339 time: {text}")))
}

#[derive(Clone, PartialEq, Debug)]
pub enum Author {
    User { id: i64, username: String },
    Import(i64),
}

impl Author {
    pub fn is_import(&self) -> bool {
        matches!(self, Author::Import(_))
    }
}

#[derive(Clone, PartialEq, Debug)]
pub struct Revision {
    pub lender: LenderId,
    pub number: u32,
    pub record: LenderRecord,
    pub author: Author,
    pub saved_at: OffsetDateTime,
    pub reason: Option<String>,
}

#[derive(Debug)]
pub enum Saved {
    New(Revision),
    /// The record equals the head; nothing was written.
    Unchanged(Revision),
}

#[derive(Debug, thiserror::Error)]
pub enum SaveError {
    #[error("another revision was saved first")]
    Conflict { head: Box<Revision> },
    #[error("no such lender")]
    NotFound,
    #[error(transparent)]
    Store(#[from] StoreError),
}

pub struct ImportRun {
    pub id: i64,
    pub run_at: OffsetDateTime,
    /// JSON `info_hub::ImportReport`.
    pub report: String,
}

pub struct ReadTx<'a> {
    conn: &'a Connection,
}

pub struct WriteTx<'a> {
    read: ReadTx<'a>,
}

impl<'a> Deref for WriteTx<'a> {
    type Target = ReadTx<'a>;
    fn deref(&self) -> &ReadTx<'a> {
        &self.read
    }
}

const REVISION_COLUMNS: &str = "r.lender_id, r.revision, r.saved_at, r.author_user_id, u.username, \
     r.author_import_run_id, r.reason, r.format, r.record";

fn revision_row(row: &rusqlite::Row) -> rusqlite::Result<RevisionRow> {
    Ok(RevisionRow {
        lender: row.get(0)?,
        number: row.get(1)?,
        saved_at: row.get(2)?,
        user_id: row.get(3)?,
        username: row.get(4)?,
        import_run: row.get(5)?,
        reason: row.get(6)?,
        format: row.get(7)?,
        record: row.get(8)?,
    })
}

struct RevisionRow {
    lender: String,
    number: u32,
    saved_at: String,
    user_id: Option<i64>,
    username: Option<String>,
    import_run: Option<i64>,
    reason: Option<String>,
    format: u32,
    record: String,
}

impl RevisionRow {
    fn parse(self) -> Result<Revision, StoreError> {
        let lender = LenderId::parse(&self.lender).ok_or_else(|| StoreError::Corrupt("a lender id".to_string()))?;
        let record = LenderRecord::from_stored(self.format, &self.record)
            .map_err(|error| StoreError::Corrupt(format!("{lender} revision {}: {error}", self.number)))?;
        let author = match (self.user_id, self.import_run) {
            (Some(id), None) => Author::User { id, username: self.username.unwrap_or_default() },
            (None, Some(run)) => Author::Import(run),
            _ => return Err(StoreError::Corrupt(format!("{lender} revision {} has no single author", self.number))),
        };
        Ok(Revision {
            lender,
            number: self.number,
            record,
            author,
            saved_at: parse_time(&self.saved_at)?,
            reason: self.reason,
        })
    }
}

impl ReadTx<'_> {
    fn revisions(&self, filter: &str, params: impl rusqlite::Params) -> Result<Vec<Revision>, StoreError> {
        let sql = format!("SELECT {REVISION_COLUMNS} FROM {filter}");
        let mut statement = self.conn.prepare(&sql)?;
        let rows = statement.query_map(params, revision_row)?.collect::<Result<Vec<_>, _>>()?;
        rows.into_iter().map(RevisionRow::parse).collect()
    }

    /// Every lender's head revision, by name.
    pub fn heads(&self) -> Result<Vec<Revision>, StoreError> {
        let mut heads = self.revisions("lender_heads r LEFT JOIN users u ON u.id = r.author_user_id", [])?;
        heads.sort_by_key(|head| head.record.profile.name.to_lowercase());
        Ok(heads)
    }

    pub fn head(&self, lender: &LenderId) -> Result<Option<Revision>, StoreError> {
        let rows = self.revisions(
            "lender_heads r LEFT JOIN users u ON u.id = r.author_user_id WHERE r.lender_id = ?1",
            [lender.as_str()],
        )?;
        Ok(rows.into_iter().next())
    }

    pub fn revision(&self, lender: &LenderId, number: u32) -> Result<Option<Revision>, StoreError> {
        let rows = self.revisions(
            "lender_revisions r LEFT JOIN users u ON u.id = r.author_user_id WHERE r.lender_id = ?1 AND r.revision = ?2",
            params![lender.as_str(), number],
        )?;
        Ok(rows.into_iter().next())
    }

    /// Oldest first.
    pub fn history(&self, lender: &LenderId) -> Result<Vec<Revision>, StoreError> {
        self.revisions(
            "lender_revisions r LEFT JOIN users u ON u.id = r.author_user_id WHERE r.lender_id = ?1 ORDER BY r.revision",
            [lender.as_str()],
        )
    }

    /// Every lender the import created, by import key.
    pub fn import_keys(&self) -> Result<Vec<(String, LenderId)>, StoreError> {
        let mut statement = self.conn.prepare("SELECT import_key, id FROM lenders WHERE import_key IS NOT NULL")?;
        let rows = statement.query_map([], |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)))?;
        rows.map(|row| {
            let (key, id) = row?;
            let id = LenderId::parse(&id).ok_or_else(|| StoreError::Corrupt("a lender id".to_string()))?;
            Ok((key, id))
        })
        .collect()
    }

    pub fn industries(&self) -> Result<Industries, StoreError> {
        let mut statement = self.conn.prepare("SELECT slug, label, retired_at IS NOT NULL FROM industries")?;
        let rows = statement.query_map([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?;
        Ok(Industries::new(rows.collect::<Result<Vec<_>, _>>()?))
    }

    pub fn session(&self, cookie: &str) -> Result<Option<AdminUser>, StoreError> {
        let row = self
            .conn
            .query_row(
                "SELECT u.id, u.username, u.role, s.csrf_token, s.expires_at FROM sessions s \
                 JOIN users u ON u.id = s.user_id WHERE s.token_sha256 = ?1 AND u.disabled_at IS NULL",
                [auth::digest(cookie)],
                |row| {
                    Ok((
                        row.get::<_, i64>(0)?,
                        row.get::<_, String>(1)?,
                        row.get::<_, String>(2)?,
                        row.get::<_, String>(3)?,
                        row.get::<_, String>(4)?,
                    ))
                },
            )
            .optional()?;
        let Some((id, username, role, csrf, expires_at)) = row else { return Ok(None) };
        if parse_time(&expires_at)? <= now() {
            return Ok(None);
        }
        let role = Role::from_key(&role).ok_or_else(|| StoreError::Corrupt(format!("role {role}")))?;
        Ok(Some(AdminUser { id, username, role, csrf }))
    }

    pub fn machine_client(&self, token: &str) -> Result<Option<MachineClient>, StoreError> {
        let row = self
            .conn
            .query_row(
                "SELECT id, name, scopes FROM api_clients WHERE token_sha256 = ?1 AND revoked_at IS NULL",
                [auth::digest(token)],
                |row| Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?, row.get::<_, String>(2)?)),
            )
            .optional()?;
        let Some((id, name, scopes)) = row else { return Ok(None) };
        let scopes = scopes
            .split_whitespace()
            .map(|key| Scope::from_key(key).ok_or_else(|| StoreError::Corrupt(format!("scope {key}"))))
            .collect::<Result<BTreeSet<_>, _>>()?;
        Ok(Some(MachineClient { id, name, scopes }))
    }

    /// Newest first.
    pub fn import_runs(&self) -> Result<Vec<ImportRun>, StoreError> {
        let mut statement = self.conn.prepare("SELECT id, run_at, report FROM import_runs ORDER BY id DESC")?;
        let rows = statement.query_map([], |row| Ok((row.get(0)?, row.get::<_, String>(1)?, row.get(2)?)))?;
        rows.map(|row| {
            let (id, run_at, report) = row?;
            Ok(ImportRun { id, run_at: parse_time(&run_at)?, report })
        })
        .collect()
    }

    pub fn import_run(&self, id: i64) -> Result<Option<ImportRun>, StoreError> {
        Ok(self.import_runs()?.into_iter().find(|run| run.id == id))
    }

    pub fn username(&self, user: i64) -> Result<Option<String>, StoreError> {
        Ok(self.conn.query_row("SELECT username FROM users WHERE id = ?1", [user], |row| row.get(0)).optional()?)
    }

    pub fn client_name(&self, client: i64) -> Result<Option<String>, StoreError> {
        Ok(self.conn.query_row("SELECT name FROM api_clients WHERE id = ?1", [client], |row| row.get(0)).optional()?)
    }
}

impl WriteTx<'_> {
    fn insert_revision(
        &self,
        lender: &LenderId,
        number: u32,
        record: &LenderRecord,
        author: &Author,
        reason: Option<&str>,
    ) -> Result<(), StoreError> {
        let (user, run) = match author {
            Author::User { id, .. } => (Some(*id), None),
            Author::Import(run) => (None, Some(*run)),
        };
        self.conn.execute(
            "INSERT INTO lender_revisions (lender_id, revision, saved_at, author_user_id, author_import_run_id, \
             reason, format, record) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![lender.as_str(), number, time_text(now()), user, run, reason, RECORD_FORMAT, record.to_stored()],
        )?;
        Ok(())
    }

    pub fn create_lender(
        &self,
        record: &LenderRecord,
        author: &Author,
        import_key: Option<&str>,
    ) -> Result<Revision, StoreError> {
        let lender = LenderId::generate();
        self.conn.execute(
            "INSERT INTO lenders (id, import_key, created_at) VALUES (?1, ?2, ?3)",
            params![lender.as_str(), import_key, time_text(now())],
        )?;
        self.insert_revision(&lender, 1, record, author, None)?;
        self.head(&lender)?.ok_or_else(|| StoreError::Corrupt("a revision just written".to_string()))
    }

    /// Returns `Unchanged(head)` when `record` equals the head, whatever `base` is. Otherwise
    /// appends `base + 1` when `base` is the head, and refuses with `Conflict` when it is not.
    pub fn save_revision(
        &self,
        lender: &LenderId,
        base: u32,
        record: &LenderRecord,
        author: &Author,
        reason: Option<&str>,
    ) -> Result<Saved, SaveError> {
        let head = self.head(lender)?.ok_or(SaveError::NotFound)?;
        if head.record.to_stored() == record.to_stored() {
            return Ok(Saved::Unchanged(head));
        }
        if head.number != base {
            return Err(SaveError::Conflict { head: Box::new(head) });
        }
        self.insert_revision(lender, base + 1, record, author, reason)?;
        let saved = self.head(lender)?.ok_or_else(|| StoreError::Corrupt("a revision just written".to_string()))?;
        Ok(Saved::New(saved))
    }

    /// Returns the existing industry when one has this label, ignoring case.
    pub fn add_industry(&self, label: &str) -> Result<IndustryId, StoreError> {
        let label = label.trim();
        let industries = self.industries()?;
        if let Some(id) = industries.by_label(label) {
            return Ok(id);
        }
        let slug = industries.slug_for(label);
        self.conn.execute("INSERT INTO industries (slug, label) VALUES (?1, ?2)", params![slug, label])?;
        self.industries()?.by_label(label).ok_or_else(|| StoreError::Corrupt("an industry just written".to_string()))
    }

    /// False when no industry has this slug.
    pub fn set_industry_retired(&self, slug: &str, retired: bool) -> Result<bool, StoreError> {
        let retired_at = retired.then(|| time_text(now()));
        Ok(self.conn.execute("UPDATE industries SET retired_at = ?2 WHERE slug = ?1", params![slug, retired_at])? == 1)
    }

    pub fn insert_import_run(&self, source_sha256: &[u8; 32], readings: &str, report: &str) -> Result<i64, StoreError> {
        self.conn.execute(
            "INSERT INTO import_runs (run_at, source_sha256, readings, report) VALUES (?1, ?2, ?3, ?4)",
            params![time_text(now()), source_sha256.as_slice(), readings, report],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    pub fn set_import_report(&self, id: i64, report: &str) -> Result<(), StoreError> {
        self.conn.execute("UPDATE import_runs SET report = ?2 WHERE id = ?1", params![id, report])?;
        Ok(())
    }

    pub fn add_user(&self, username: &str, password: &str, role: Role) -> Result<i64, StoreError> {
        self.conn.execute(
            "INSERT INTO users (username, password_phc, role, created_at) VALUES (?1, ?2, ?3, ?4)",
            params![username, auth::hash_password(password), role.key(), time_text(now())],
        )?;
        Ok(self.conn.last_insert_rowid())
    }

    /// None when the username or password is wrong or the account is disabled.
    pub fn sign_in(&self, username: &str, password: &str) -> Result<Option<NewSession>, StoreError> {
        let row = self
            .conn
            .query_row(
                "SELECT id, password_phc FROM users WHERE username = ?1 AND disabled_at IS NULL",
                [username],
                |row| Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?)),
            )
            .optional()?;
        if !auth::verify_password(password, row.as_ref().map(|(_, phc)| phc.as_str())) {
            return Ok(None);
        }
        let Some((user_id, _)) = row else { return Ok(None) };
        let cookie = auth::random_secret();
        let created = now();
        self.conn.execute(
            "INSERT INTO sessions (token_sha256, user_id, csrf_token, created_at, expires_at) VALUES (?1, ?2, ?3, ?4, ?5)",
            params![
                auth::digest(&cookie),
                user_id,
                auth::random_secret(),
                time_text(created),
                time_text(created + time::Duration::hours(SESSION_HOURS))
            ],
        )?;
        let user = self.session(&cookie)?.ok_or_else(|| StoreError::Corrupt("a session just written".to_string()))?;
        Ok(Some(NewSession { cookie, user }))
    }

    pub fn sign_out(&self, cookie: &str) -> Result<(), StoreError> {
        self.conn.execute("DELETE FROM sessions WHERE token_sha256 = ?1", [auth::digest(cookie)])?;
        Ok(())
    }

    /// Returns the token, which is stored only as its digest. Refuses a name another live token holds.
    pub fn create_token(&self, name: &str, scopes: &BTreeSet<Scope>) -> Result<String, StoreError> {
        let token = format!("lm_{}", auth::random_secret());
        self.conn.execute(
            "INSERT INTO api_clients (name, token_sha256, scopes, created_at) VALUES (?1, ?2, ?3, ?4)",
            params![name, auth::digest(&token), auth::scopes_text(scopes), time_text(now())],
        )?;
        Ok(token)
    }

    /// False when no live token has this name.
    pub fn revoke_token(&self, name: &str) -> Result<bool, StoreError> {
        let changed = self.conn.execute(
            "UPDATE api_clients SET revoked_at = ?2 WHERE name = ?1 AND revoked_at IS NULL",
            params![name, time_text(now())],
        )?;
        Ok(changed == 1)
    }
}

#[cfg(test)]
pub(crate) mod testing {
    use super::*;

    pub fn editor(store: &Store) -> Author {
        let id = store.write(|tx| tx.add_user("sample.editor", "correct horse battery", Role::Editor)).unwrap();
        Author::User { id, username: "sample.editor".to_string() }
    }
}

#[cfg(test)]
mod tests {
    use super::testing::editor;
    use super::*;
    use crate::criteria::testing::{num, profile, rule};
    use crate::criteria::{LenderPolicy, LenderStatus};
    use crate::facts::NumFact;

    fn record(name: &str, max_negative_days: i64) -> LenderRecord {
        LenderRecord {
            profile: profile(name),
            policy: LenderPolicy::new(
                LenderStatus::Draft,
                vec![rule(1, vec![], num(NumFact::WorstMonthNegativeDays, None, Some(max_negative_days)))],
                vec![],
            )
            .unwrap(),
        }
    }

    #[test]
    fn migrations_apply_once_and_refuse_a_newer_schema() {
        let directory = std::env::temp_dir().join(format!("lender-matching-store-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join("store.sqlite3");
        drop(Store::open(&path).unwrap());
        drop(Store::open(&path).unwrap());
        Connection::open(&path).unwrap().pragma_update(None, "user_version", 99).unwrap();
        assert!(matches!(Store::open(&path), Err(StoreError::NewerSchema { found: 99, known: 1 })));
        std::fs::remove_dir_all(&directory).unwrap();
    }

    #[test]
    fn saves_append_revisions_and_refuse_a_stale_base() {
        let store = Store::open_in_memory();
        let author = editor(&store);
        let created = store.write(|tx| tx.create_lender(&record("FABRIKAM FUNDING", 1), &author, None)).unwrap();
        assert_eq!(created.number, 1);
        let lender = created.lender.clone();

        let saved = store
            .write(|tx| tx.save_revision(&lender, 1, &record("FABRIKAM FUNDING", 3), &author, Some("new limit")))
            .unwrap();
        let Saved::New(second) = saved else { panic!("expected a new revision") };
        assert_eq!((second.number, second.reason.as_deref()), (2, Some("new limit")));

        let stale = store.write(|tx| tx.save_revision(&lender, 1, &record("FABRIKAM FUNDING", 5), &author, None));
        let Err(SaveError::Conflict { head }) = stale else { panic!("expected a conflict") };
        assert_eq!(head.number, 2);
        assert_eq!(store.read(|tx| tx.history(&lender)).unwrap().len(), 2, "the conflict wrote nothing");
    }

    #[test]
    fn an_identical_save_writes_nothing() {
        let store = Store::open_in_memory();
        let author = editor(&store);
        let created = store.write(|tx| tx.create_lender(&record("CONTOSO CAPITAL", 2), &author, None)).unwrap();
        for base in [1, 7] {
            let saved = store
                .write(|tx| tx.save_revision(&created.lender, base, &record("CONTOSO CAPITAL", 2), &author, None))
                .unwrap();
            assert!(matches!(saved, Saved::Unchanged(head) if head.number == 1));
        }
        assert_eq!(store.read(|tx| tx.history(&created.lender)).unwrap().len(), 1);
    }

    #[test]
    fn revisions_matches_and_industries_cannot_be_rewritten() {
        let store = Store::open_in_memory();
        let author = editor(&store);
        let created = store.write(|tx| tx.create_lender(&record("NORTHWIND ADVANCE", 2), &author, None)).unwrap();
        store.write(|tx| tx.create_token("auto-submission", &BTreeSet::from([Scope::Match]))).unwrap();
        store.write(|tx| tx.add_industry("Cannabis")).unwrap();
        let conn = store.conn.lock().unwrap();
        conn.execute_batch(&format!(
            "INSERT INTO matches (id, created_at, client_id, as_of, engine_version, format, input, facts) \
             VALUES ('m1', '2026-10-23T00:00:00Z', 1, '2026-10-23', 1, 1, '{{}}', '{{}}'); \
             INSERT INTO match_verdicts (match_id, lender_id, revision, status) VALUES ('m1', '{}', 1, 'inactive');",
            created.lender
        ))
        .unwrap();
        for sql in [
            "UPDATE lender_revisions SET record = '{}'",
            "DELETE FROM lender_revisions",
            "UPDATE matches SET as_of = '2026-10-24'",
            "DELETE FROM matches",
            "UPDATE match_verdicts SET status = 'match'",
            "DELETE FROM match_verdicts",
            "DELETE FROM industries",
        ] {
            let error = conn.execute(sql, []).expect_err(sql).to_string();
            assert!(error.contains("immutable") || error.contains("retire it instead"), "{sql}: {error}");
        }
        drop(conn);
        assert_eq!(store.read(|tx| tx.head(&created.lender)).unwrap().unwrap().record, record("NORTHWIND ADVANCE", 2));
    }

    #[test]
    fn a_failed_write_rolls_back() {
        let store = Store::open_in_memory();
        let author = editor(&store);
        let result: Result<(), StoreError> = store.write(|tx| {
            tx.create_lender(&record("SAMPLE EQUIPMENT FINANCE", 1), &author, Some("name:SAMPLE"))?;
            Err(StoreError::Corrupt("abandon".to_string()))
        });
        assert!(result.is_err());
        assert!(store.read(|tx| tx.heads()).unwrap().is_empty());
    }

    #[test]
    fn industries_are_added_once_by_label_and_retired_not_deleted() {
        let store = Store::open_in_memory();
        let first = store.write(|tx| tx.add_industry("Transportation / Trucking")).unwrap();
        let again = store.write(|tx| tx.add_industry(" transportation / trucking ")).unwrap();
        assert_eq!(first, again);
        assert_eq!(first.as_str(), "transportation-trucking");
        assert!(store.write(|tx| tx.set_industry_retired("transportation-trucking", true)).unwrap());
        let industries = store.read(|tx| tx.industries()).unwrap();
        assert!(industries.resolve("transportation-trucking").is_none());
        assert_eq!(industries.label(&first), "Transportation / Trucking");
        assert!(!store.write(|tx| tx.set_industry_retired("no-such-industry", true)).unwrap());
    }

    #[test]
    fn sign_in_checks_the_password_and_sessions_expire() {
        let store = Store::open_in_memory();
        store.write(|tx| tx.add_user("sample.reviewer", "correct horse battery", Role::Reviewer)).unwrap();
        assert!(store.write(|tx| tx.sign_in("sample.reviewer", "wrong password")).unwrap().is_none());
        assert!(store.write(|tx| tx.sign_in("nobody", "correct horse battery")).unwrap().is_none());
        let session = store.write(|tx| tx.sign_in("SAMPLE.REVIEWER", "correct horse battery")).unwrap().unwrap();
        let user = store.read(|tx| tx.session(&session.cookie)).unwrap().unwrap();
        assert_eq!((user.username.as_str(), user.role), ("sample.reviewer", Role::Reviewer));
        assert!(user.can(Role::Viewer) && user.can(Role::Reviewer) && !user.can(Role::Editor));
        assert!(user.csrf_matches(&session.user.csrf) && !user.csrf_matches("forged"));

        store.conn.lock().unwrap().execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00Z'", []).unwrap();
        assert!(store.read(|tx| tx.session(&session.cookie)).unwrap().is_none());

        let fresh = store.write(|tx| tx.sign_in("sample.reviewer", "correct horse battery")).unwrap().unwrap();
        store.write(|tx| tx.sign_out(&fresh.cookie)).unwrap();
        assert!(store.read(|tx| tx.session(&fresh.cookie)).unwrap().is_none());
    }

    #[test]
    fn tokens_open_only_until_revoked_and_names_can_be_reused_after() {
        let store = Store::open_in_memory();
        let scopes = BTreeSet::from([Scope::Match, Scope::Read]);
        let token = store.write(|tx| tx.create_token("auto-submission", &scopes)).unwrap();
        let client = store.read(|tx| tx.machine_client(&token)).unwrap().unwrap();
        assert_eq!(client.name, "auto-submission");
        assert!(client.has(Scope::Match) && client.has(Scope::Read));
        assert!(store.read(|tx| tx.machine_client("lm_forged")).unwrap().is_none());
        assert!(store.write(|tx| tx.create_token("auto-submission", &scopes)).is_err(), "one live token per name");

        assert!(store.write(|tx| tx.revoke_token("auto-submission")).unwrap());
        assert!(store.read(|tx| tx.machine_client(&token)).unwrap().is_none());
        assert!(!store.write(|tx| tx.revoke_token("auto-submission")).unwrap());
        let replacement = store.write(|tx| tx.create_token("auto-submission", &BTreeSet::from([Scope::Read]))).unwrap();
        assert!(!store.read(|tx| tx.machine_client(&replacement)).unwrap().unwrap().has(Scope::Match));
    }
}
