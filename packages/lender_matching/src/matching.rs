//! Making a match: fetch the analysis package, assemble the deal's facts, evaluate every lender's
//! head revision and store the record with the revision each verdict read.

use std::collections::BTreeMap;
use std::sync::Arc;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use time::OffsetDateTime;
use uuid::Uuid;

use crate::analysis_api::{AnalysisClient, AnalysisError, Fetched};
use crate::criteria::eval::{Evaluation, Waiver, evaluate};
use crate::criteria::{LenderId, LenderStatus, Product};
use crate::facts::{DealFacts, DealInput, assemble};
use crate::store::{ReadTx, Revision, Store, StoreError, now};

/// Bump when `assemble` or `evaluate` would give another verdict for the same inputs; stored
/// matches keep the version that computed them.
pub const ENGINE_VERSION: u32 = 1;

/// The JSON layout of a stored match's `input` and `facts`. A bump needs a reader for every older
/// format still in `matches`.
pub const MATCH_FORMAT: u32 = 1;

/// Everything a match was asked, as stored.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct MatchInput {
    pub analysis_package: Option<Uuid>,
    pub product: Product,
    pub deal: DealInput,
    /// Given by a signed-in person on the match page.
    pub waivers: Vec<Waiver>,
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Requester {
    Client(i64),
    /// A person re-matching from the match page.
    Person {
        user: i64,
        supersedes: Uuid,
    },
}

#[derive(Clone, PartialEq, Debug)]
pub struct MatchRecord {
    pub id: Uuid,
    pub created_at: OffsetDateTime,
    pub by: Requester,
    pub input: MatchInput,
    pub facts: DealFacts,
    pub engine_version: u32,
    /// One per lender in the catalog the match read.
    pub verdicts: Vec<LenderVerdict>,
}

#[derive(Clone, PartialEq, Debug)]
pub struct LenderVerdict {
    pub lender: LenderId,
    pub revision: u32,
    pub result: VerdictResult,
}

#[derive(Clone, PartialEq, Debug)]
pub enum VerdictResult {
    Evaluated(Evaluation),
    Inactive(LenderStatus),
    /// Active, but not offering the requested product.
    NotOffered,
}

impl VerdictResult {
    pub fn key(&self) -> &'static str {
        match self {
            VerdictResult::Evaluated(evaluation) => evaluation.status().key(),
            VerdictResult::Inactive(_) => "inactive",
            VerdictResult::NotOffered => "not_offered",
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum MatchError {
    #[error("no analysis service is configured")]
    AnalysisNotConfigured,
    #[error("the analysis package is still processing")]
    AnalysisNotReady { retry_after: Duration },
    #[error("the analysis service has no such package")]
    AnalysisPackageNotFound,
    #[error("{0}")]
    AnalysisUnavailable(String),
    #[error("{0}")]
    AnalysisContractMismatch(String),
    #[error("the match was already superseded")]
    AlreadySuperseded,
    #[error(transparent)]
    Store(#[from] StoreError),
}

impl From<AnalysisError> for MatchError {
    fn from(error: AnalysisError) -> Self {
        match error {
            AnalysisError::NotFound => MatchError::AnalysisPackageNotFound,
            AnalysisError::Unavailable(why) => MatchError::AnalysisUnavailable(why),
            AnalysisError::ContractMismatch(why) => MatchError::AnalysisContractMismatch(why),
        }
    }
}

pub struct Matcher {
    store: Arc<Store>,
    analysis: Option<AnalysisClient>,
}

impl Matcher {
    pub fn new(store: Arc<Store>, analysis: Option<AnalysisClient>) -> Matcher {
        Matcher { store, analysis }
    }

    /// Fetches the package, assembles the facts at today's UTC date, then reads every head and
    /// stores the match inside one write transaction, so each verdict names the revision it read.
    pub async fn run(&self, by: Requester, input: MatchInput) -> Result<MatchRecord, MatchError> {
        let package = match input.analysis_package {
            None => None,
            Some(id) => match self.analysis.as_ref().ok_or(MatchError::AnalysisNotConfigured)?.fetch(id).await? {
                Fetched::Processing { retry_after } => return Err(MatchError::AnalysisNotReady { retry_after }),
                Fetched::Ready(package) => Some(package),
            },
        };
        let created_at = now();
        let facts = assemble(package.as_ref(), &input.deal, created_at.date());
        tokio::task::block_in_place(|| {
            self.store.write(|tx| {
                if let Requester::Person { supersedes, .. } = &by
                    && tx.superseded_by(*supersedes)?.is_some()
                {
                    return Err(MatchError::AlreadySuperseded);
                }
                let verdicts = tx.heads()?.iter().map(|head| verdict(head, &facts, &input)).collect();
                let record = MatchRecord {
                    id: Uuid::new_v4(),
                    created_at,
                    by,
                    input,
                    facts,
                    engine_version: ENGINE_VERSION,
                    verdicts,
                };
                tx.insert_match(&record)?;
                Ok(record)
            })
        })
    }
}

fn verdict(head: &Revision, facts: &DealFacts, input: &MatchInput) -> LenderVerdict {
    let policy = &head.record.policy;
    let result = if policy.status() != LenderStatus::Active {
        VerdictResult::Inactive(policy.status())
    } else if !head.record.profile.products.contains(&input.product) {
        VerdictResult::NotOffered
    } else {
        let waivers: Vec<Waiver> =
            input.waivers.iter().filter(|waiver| waiver.lender == head.lender).cloned().collect();
        VerdictResult::Evaluated(evaluate(policy, head.number, facts, &waivers))
    };
    LenderVerdict { lender: head.lender.clone(), revision: head.number, result }
}

/// A stored match with what reading it needs: the revision each verdict read, each lender's
/// current head, and who made it.
pub struct MatchView {
    pub record: MatchRecord,
    pub revisions: BTreeMap<LenderId, Revision>,
    pub heads: BTreeMap<LenderId, u32>,
    pub superseded_by: Option<Uuid>,
    pub created_by: Creator,
}

pub enum Creator {
    Client(String),
    Person(String),
}

impl MatchView {
    pub fn load(tx: &ReadTx, id: Uuid) -> Result<Option<MatchView>, StoreError> {
        let Some(record) = tx.match_record(id)? else { return Ok(None) };
        let mut revisions = BTreeMap::new();
        let mut heads = BTreeMap::new();
        for verdict in &record.verdicts {
            let revision = tx
                .revision(&verdict.lender, verdict.revision)?
                .ok_or_else(|| StoreError::Corrupt(format!("{} revision {}", verdict.lender, verdict.revision)))?;
            revisions.insert(verdict.lender.clone(), revision);
            if let Some(head) = tx.head(&verdict.lender)? {
                heads.insert(verdict.lender.clone(), head.number);
            }
        }
        let created_by = match &record.by {
            Requester::Client(client) => Creator::Client(tx.client_name(*client)?.unwrap_or_default()),
            Requester::Person { user, .. } => Creator::Person(tx.username(*user)?.unwrap_or_default()),
        };
        Ok(Some(MatchView { superseded_by: tx.superseded_by(id)?, record, revisions, heads, created_by }))
    }

    pub fn is_current(&self, verdict: &LenderVerdict) -> bool {
        self.heads.get(&verdict.lender) == Some(&verdict.revision)
    }

    pub fn name(&self, lender: &LenderId) -> &str {
        self.revisions.get(lender).map_or("", |revision| revision.record.profile.name.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::criteria::testing::{num, profile, rule, state_in};
    use crate::criteria::{CheckId, LenderPolicy, LenderRecord, NoteId};
    use crate::criteria::{Note, NoteKind};
    use crate::facts::NumFact;
    use crate::facts::testing::{application, everything_confirmed};
    use crate::store::Author;
    use crate::store::testing::editor;
    use std::collections::BTreeSet;

    fn active_lender(store: &Store, author: &Author, name: &str, min_score: i64, notes: Vec<Note>) -> Revision {
        let record = LenderRecord {
            profile: profile(name),
            policy: LenderPolicy::new(
                LenderStatus::Active,
                vec![rule(1, vec![], num(NumFact::CreditScore, Some(min_score), None))],
                notes,
            )
            .unwrap(),
        };
        store.write(|tx| tx.create_lender(&record, author, None)).unwrap()
    }

    fn input() -> MatchInput {
        MatchInput {
            analysis_package: None,
            product: Product::Mca,
            deal: DealInput { application: application(), confirmations: everything_confirmed() },
            waivers: Vec::new(),
        }
    }

    fn client(store: &Store) -> Requester {
        let token = store.write(|tx| tx.create_token("auto-submission", &BTreeSet::new())).unwrap();
        Requester::Client(store.read(|tx| tx.machine_client(&token)).unwrap().unwrap().id)
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_match_evaluates_active_heads_and_lists_the_rest() {
        let store = Arc::new(Store::open_in_memory());
        let author = editor(&store);
        let passes = active_lender(&store, &author, "CONTOSO CAPITAL", 600, vec![]);
        let fails = active_lender(&store, &author, "FABRIKAM FUNDING", 700, vec![]);
        let held =
            Note { id: NoteId(1), kind: NoteKind::Condition, when: vec![state_in(&["TX"])], text: "SAMPLE".into() };
        let review = active_lender(&store, &author, "NORTHWIND ADVANCE", 600, vec![held]);
        let mut draft = passes.record.clone();
        draft.policy = draft.policy.with_status(LenderStatus::Draft).unwrap();
        draft.profile.name = "SAMPLE DRAFT".to_string();
        let draft = store.write(|tx| tx.create_lender(&draft, &author, None)).unwrap();
        let mut equipment = passes.record.clone();
        equipment.profile.name = "SAMPLE EQUIPMENT FINANCE".to_string();
        equipment.profile.products = BTreeSet::from([Product::Equipment]);
        let equipment = store.write(|tx| tx.create_lender(&equipment, &author, None)).unwrap();

        let matcher = Matcher::new(store.clone(), None);
        let record = matcher.run(client(&store), input()).await.unwrap();
        let key = |lender: &LenderId| record.verdicts.iter().find(|v| &v.lender == lender).unwrap().result.key();
        assert_eq!(key(&passes.lender), "match");
        assert_eq!(key(&fails.lender), "no_match");
        assert_eq!(key(&review.lender), "review");
        assert_eq!(key(&draft.lender), "inactive");
        assert_eq!(key(&equipment.lender), "not_offered");

        let view = store.read(|tx| MatchView::load(tx, record.id)).unwrap().unwrap();
        assert_eq!(view.record, record, "the stored match reads back as it was made");
        assert!(view.record.verdicts.iter().all(|verdict| view.is_current(verdict)));
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_saved_revision_makes_old_verdicts_not_current_and_the_next_match_reads_it() {
        let store = Arc::new(Store::open_in_memory());
        let author = editor(&store);
        let lender = active_lender(&store, &author, "CONTOSO CAPITAL", 600, vec![]);
        let matcher = Matcher::new(store.clone(), None);
        let first = matcher.run(client(&store), input()).await.unwrap();

        let mut stricter = lender.record.clone();
        stricter.policy = LenderPolicy::new(
            LenderStatus::Active,
            vec![rule(1, vec![], num(NumFact::CreditScore, Some(700), None))],
            vec![],
        )
        .unwrap();
        store.write(|tx| tx.save_revision(&lender.lender, 1, &stricter, &author, None)).unwrap();

        let view = store.read(|tx| MatchView::load(tx, first.id)).unwrap().unwrap();
        assert!(!view.is_current(&view.record.verdicts[0]));
        let second = matcher.run(Requester::Client(1), input()).await.unwrap();
        assert_eq!((second.verdicts[0].revision, second.verdicts[0].result.key()), (2, "no_match"));
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_person_supersedes_a_match_once_with_waivers_bound_to_what_they_saw() {
        let store = Arc::new(Store::open_in_memory());
        let author = editor(&store);
        let Author::User { id: user, .. } = author.clone() else { unreachable!() };
        let lender = active_lender(&store, &author, "FABRIKAM FUNDING", 700, vec![]);
        let matcher = Matcher::new(store.clone(), None);
        let first = matcher.run(client(&store), input()).await.unwrap();
        assert_eq!(first.verdicts[0].result.key(), "no_match");

        let mut reviewed = input();
        reviewed.waivers.push(Waiver {
            lender: lender.lender.clone(),
            check: CheckId::Rule(crate::criteria::RuleId(1)),
            lender_revision: 1,
            analysis_revision: None,
            by: "sample.editor".to_string(),
            at: now(),
            reason: "SAMPLE LENDER confirmed an exception".to_string(),
        });
        let by = Requester::Person { user, supersedes: first.id };
        let second = matcher.run(by.clone(), reviewed.clone()).await.unwrap();
        assert_eq!(second.verdicts[0].result.key(), "match");
        assert_eq!(store.read(|tx| tx.superseded_by(first.id)).unwrap(), Some(second.id));
        assert!(matches!(matcher.run(by, reviewed).await, Err(MatchError::AlreadySuperseded)));
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_package_without_an_analysis_service_is_refused() {
        let store = Arc::new(Store::open_in_memory());
        let mut asked = input();
        asked.analysis_package = Some(Uuid::new_v4());
        let result = Matcher::new(store.clone(), None).run(client(&store), asked).await;
        assert!(matches!(result, Err(MatchError::AnalysisNotConfigured)));
    }
}
