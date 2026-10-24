//! The SQL of stored applications. Sealed columns pass through as bytes; `crate::applications`
//! seals and opens them.

use rusqlite::{OptionalExtension, params};
use time::OffsetDateTime;
use uuid::Uuid;

use super::{ReadTx, StoreError, WriteTx, now, parse_time, time_text};
use crate::applications::{ApplicationId, ApplicationRef, ParseId, RevisionKind};

pub struct NewApplication<'a> {
    pub id: ApplicationId,
    pub source_sha256: [u8; 32],
    pub envelope_id_sha256: Option<[u8; 32]>,
    pub uploaded_by: i64,
    pub source_pdf: &'a [u8],
}

pub struct ParseRow {
    pub id: ParseId,
    pub application: ApplicationId,
    pub parser_version: u32,
    pub parser_fingerprint: [u8; 32],
    pub created_at: OffsetDateTime,
    pub format: u32,
    pub payload: Vec<u8>,
}

pub struct NewRevision<'a> {
    pub application: ApplicationId,
    pub revision: u32,
    pub selected_parse: ParseId,
    pub author: i64,
    pub kind: RevisionKind,
    pub format: u32,
    pub state: &'a [u8],
    pub reason: Option<&'a [u8]>,
}

/// Who stored an application and when.
pub struct UploadRow {
    pub id: ApplicationId,
    pub uploaded_at: OffsetDateTime,
    pub uploaded_by: String,
}

/// One logged look at an application's identity data.
pub struct AccessRow {
    pub action: String,
    pub username: String,
    pub occurred_at: OffsetDateTime,
}

pub struct RevisionRow {
    pub application: ApplicationId,
    pub revision: u32,
    pub selected_parse: ParseId,
    pub saved_at: OffsetDateTime,
    pub author_name: String,
    pub kind: RevisionKind,
    pub format: u32,
    pub state: Vec<u8>,
    pub reason: Option<Vec<u8>>,
}

fn uuid(text: &str) -> Result<Uuid, StoreError> {
    Uuid::parse_str(text).map_err(|_| StoreError::Corrupt("an application id".to_string()))
}

const PARSE_COLUMNS: &str =
    "id, application_id, parser_version, parser_fingerprint, created_at, format, payload FROM application_parses";

type RawParse = (String, String, u32, Vec<u8>, String, u32, Vec<u8>);

fn parse_row(row: &rusqlite::Row) -> rusqlite::Result<RawParse> {
    Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?, row.get(4)?, row.get(5)?, row.get(6)?))
}

fn parse_of(raw: RawParse) -> Result<ParseRow, StoreError> {
    let (id, application, parser_version, fingerprint, created_at, format, payload) = raw;
    Ok(ParseRow {
        id: ParseId(uuid(&id)?),
        application: ApplicationId(uuid(&application)?),
        parser_version,
        parser_fingerprint: fingerprint
            .try_into()
            .map_err(|_| StoreError::Corrupt("a parser fingerprint".to_string()))?,
        created_at: parse_time(&created_at)?,
        format,
        payload,
    })
}

const REVISION_COLUMNS: &str = "r.application_id, r.revision, r.selected_parse_id, r.saved_at, u.username, r.kind, \
     r.cause, r.format, r.state, r.reason FROM application_revisions r JOIN users u ON u.id = r.author_user_id";

type RawRevision = (String, u32, String, String, String, String, Option<String>, u32, Vec<u8>, Option<Vec<u8>>);

fn revision_row(row: &rusqlite::Row) -> rusqlite::Result<RawRevision> {
    Ok((
        row.get(0)?,
        row.get(1)?,
        row.get(2)?,
        row.get(3)?,
        row.get(4)?,
        row.get(5)?,
        row.get(6)?,
        row.get(7)?,
        row.get(8)?,
        row.get(9)?,
    ))
}

fn revision_of(raw: RawRevision) -> Result<RevisionRow, StoreError> {
    let (application, revision, parse, saved_at, author_name, kind, cause, format, state, reason) = raw;
    let kind = RevisionKind::from_keys(&kind, cause.as_deref())
        .ok_or_else(|| StoreError::Corrupt(format!("application revision {revision} has kind {kind}")))?;
    Ok(RevisionRow {
        application: ApplicationId(uuid(&application)?),
        revision,
        selected_parse: ParseId(uuid(&parse)?),
        saved_at: parse_time(&saved_at)?,
        author_name,
        kind,
        format,
        state,
        reason,
    })
}

fn upload_of(raw: (String, String, String)) -> Result<UploadRow, StoreError> {
    let (id, uploaded_at, uploaded_by) = raw;
    Ok(UploadRow { id: ApplicationId(uuid(&id)?), uploaded_at: parse_time(&uploaded_at)?, uploaded_by })
}

const UPLOAD_COLUMNS: &str = "a.id, a.uploaded_at, u.username FROM applications a JOIN users u ON u.id = a.uploaded_by";

impl ReadTx<'_> {
    /// Every application, the latest upload first.
    pub fn application_uploads(&self) -> Result<Vec<UploadRow>, StoreError> {
        let mut statement = self.conn.prepare(&format!("SELECT {UPLOAD_COLUMNS} ORDER BY a.rowid DESC"))?;
        let rows = statement
            .query_map([], |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)))?
            .collect::<Result<Vec<_>, _>>()?;
        rows.into_iter().map(upload_of).collect()
    }

    pub fn application_upload(&self, id: ApplicationId) -> Result<Option<UploadRow>, StoreError> {
        let raw = self
            .conn
            .query_row(&format!("SELECT {UPLOAD_COLUMNS} WHERE a.id = ?1"), [id.0.to_string()], |row| {
                Ok((row.get(0)?, row.get(1)?, row.get(2)?))
            })
            .optional()?;
        raw.map(upload_of).transpose()
    }

    /// The first application stored before `id` from the same envelope.
    pub fn earlier_of_envelope(&self, id: ApplicationId) -> Result<Option<ApplicationId>, StoreError> {
        let earlier: Option<String> = self
            .conn
            .query_row(
                "SELECT e.id FROM applications a JOIN applications e ON e.envelope_id_sha256 = a.envelope_id_sha256 \
                 WHERE a.id = ?1 AND e.rowid < a.rowid ORDER BY e.rowid LIMIT 1",
                [id.0.to_string()],
                |row| row.get(0),
            )
            .optional()?;
        earlier.map(|id| Ok(ApplicationId(uuid(&id)?))).transpose()
    }

    pub fn application_by_source(&self, source_sha256: &[u8; 32]) -> Result<Option<ApplicationId>, StoreError> {
        let id: Option<String> = self
            .conn
            .query_row("SELECT id FROM applications WHERE source_sha256 = ?1", [source_sha256.as_slice()], |row| {
                row.get(0)
            })
            .optional()?;
        id.map(|id| Ok(ApplicationId(uuid(&id)?))).transpose()
    }

    /// The first application uploaded from this envelope.
    pub fn application_by_envelope(&self, envelope_id_sha256: &[u8; 32]) -> Result<Option<ApplicationId>, StoreError> {
        let id: Option<String> = self
            .conn
            .query_row(
                "SELECT id FROM applications WHERE envelope_id_sha256 = ?1 ORDER BY rowid LIMIT 1",
                [envelope_id_sha256.as_slice()],
                |row| row.get(0),
            )
            .optional()?;
        id.map(|id| Ok(ApplicationId(uuid(&id)?))).transpose()
    }

    /// The sealed source PDF.
    pub fn application_source(&self, id: ApplicationId) -> Result<Option<Vec<u8>>, StoreError> {
        Ok(self
            .conn
            .query_row("SELECT source_pdf FROM applications WHERE id = ?1", [id.0.to_string()], |row| row.get(0))
            .optional()?)
    }

    pub fn application_parse(&self, application: ApplicationId, id: ParseId) -> Result<Option<ParseRow>, StoreError> {
        let sql = format!("SELECT {PARSE_COLUMNS} WHERE application_id = ?1 AND id = ?2");
        let raw =
            self.conn.query_row(&sql, params![application.0.to_string(), id.0.to_string()], parse_row).optional()?;
        raw.map(parse_of).transpose()
    }

    pub fn application_parse_by_fingerprint(
        &self,
        application: ApplicationId,
        fingerprint: &[u8; 32],
    ) -> Result<Option<ParseRow>, StoreError> {
        let sql = format!("SELECT {PARSE_COLUMNS} WHERE application_id = ?1 AND parser_fingerprint = ?2");
        let raw = self
            .conn
            .query_row(&sql, params![application.0.to_string(), fingerprint.as_slice()], parse_row)
            .optional()?;
        raw.map(parse_of).transpose()
    }

    fn application_revision_where(
        &self,
        filter: &str,
        params: impl rusqlite::Params,
    ) -> Result<Vec<RevisionRow>, StoreError> {
        let sql = format!("SELECT {REVISION_COLUMNS} {filter}");
        let mut statement = self.conn.prepare(&sql)?;
        let rows = statement.query_map(params, revision_row)?.collect::<Result<Vec<_>, _>>()?;
        rows.into_iter().map(revision_of).collect()
    }

    pub fn application_head(&self, id: ApplicationId) -> Result<Option<RevisionRow>, StoreError> {
        let rows = self.application_revision_where(
            "WHERE r.application_id = ?1 ORDER BY r.revision DESC LIMIT 1",
            [id.0.to_string()],
        )?;
        Ok(rows.into_iter().next())
    }

    pub fn application_revision(&self, at: ApplicationRef) -> Result<Option<RevisionRow>, StoreError> {
        let rows = self.application_revision_where(
            "WHERE r.application_id = ?1 AND r.revision = ?2",
            params![at.id.0.to_string(), at.revision],
        )?;
        Ok(rows.into_iter().next())
    }

    pub fn application_revisions(&self, id: ApplicationId) -> Result<Vec<RevisionRow>, StoreError> {
        self.application_revision_where("WHERE r.application_id = ?1 ORDER BY r.revision", [id.0.to_string()])
    }

    /// The application revision a match read.
    pub fn match_application(&self, match_id: Uuid) -> Result<Option<ApplicationRef>, StoreError> {
        let row: Option<(String, u32)> = self
            .conn
            .query_row(
                "SELECT application_id, revision FROM match_applications WHERE match_id = ?1",
                [match_id.to_string()],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        row.map(|(id, revision)| Ok(ApplicationRef { id: ApplicationId(uuid(&id)?), revision })).transpose()
    }

    pub fn application_accesses(&self, id: ApplicationId) -> Result<Vec<AccessRow>, StoreError> {
        let mut statement = self.conn.prepare(
            "SELECT a.action, u.username, a.occurred_at FROM application_access a JOIN users u ON u.id = a.user_id \
             WHERE a.application_id = ?1 ORDER BY a.id",
        )?;
        let rows = statement
            .query_map([id.0.to_string()], |row| Ok((row.get(0)?, row.get(1)?, row.get::<_, String>(2)?)))?
            .collect::<Result<Vec<_>, _>>()?;
        rows.into_iter()
            .map(|(action, username, at)| Ok(AccessRow { action, username, occurred_at: parse_time(&at)? }))
            .collect()
    }

    /// Any one sealed revision state, to tell which key the stored applications use.
    pub fn some_application_state(&self) -> Result<Option<Vec<u8>>, StoreError> {
        Ok(self.conn.query_row("SELECT state FROM application_revisions LIMIT 1", [], |row| row.get(0)).optional()?)
    }
}

impl WriteTx<'_> {
    pub fn insert_application_access(&self, id: ApplicationId, user: i64, action: &str) -> Result<(), StoreError> {
        self.conn.execute(
            "INSERT INTO application_access (application_id, user_id, occurred_at, action) VALUES (?1, ?2, ?3, ?4)",
            params![id.0.to_string(), user, time_text(now()), action],
        )?;
        Ok(())
    }

    pub fn insert_match_application(&self, match_id: Uuid, read: ApplicationRef) -> Result<(), StoreError> {
        self.conn.execute(
            "INSERT INTO match_applications (match_id, application_id, revision) VALUES (?1, ?2, ?3)",
            params![match_id.to_string(), read.id.0.to_string(), read.revision],
        )?;
        Ok(())
    }

    pub fn insert_application(&self, new: &NewApplication) -> Result<(), StoreError> {
        self.conn.execute(
            "INSERT INTO applications (id, source_sha256, envelope_id_sha256, uploaded_at, uploaded_by, source_pdf) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![
                new.id.0.to_string(),
                new.source_sha256.as_slice(),
                new.envelope_id_sha256.as_ref().map(|digest| digest.as_slice()),
                time_text(now()),
                new.uploaded_by,
                new.source_pdf
            ],
        )?;
        Ok(())
    }

    pub fn insert_application_parse(&self, parse: &ParseRow) -> Result<(), StoreError> {
        self.conn.execute(
            "INSERT INTO application_parses (id, application_id, parser_version, parser_fingerprint, created_at, \
             format, payload) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                parse.id.0.to_string(),
                parse.application.0.to_string(),
                parse.parser_version,
                parse.parser_fingerprint.as_slice(),
                time_text(parse.created_at),
                parse.format,
                parse.payload
            ],
        )?;
        Ok(())
    }

    pub fn insert_application_revision(&self, revision: &NewRevision) -> Result<(), StoreError> {
        let (kind, cause) = revision.kind.keys();
        self.conn.execute(
            "INSERT INTO application_revisions (application_id, revision, selected_parse_id, saved_at, \
             author_user_id, kind, cause, format, state, reason) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
            params![
                revision.application.0.to_string(),
                revision.revision,
                revision.selected_parse.0.to_string(),
                time_text(now()),
                revision.author,
                kind,
                cause,
                revision.format,
                revision.state,
                revision.reason
            ],
        )?;
        Ok(())
    }
}
