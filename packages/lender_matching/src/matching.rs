use std::collections::BTreeMap;
use std::sync::Arc;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use time::OffsetDateTime;
use uuid::Uuid;

use crate::analysis_api::{AnalysisClient, AnalysisError, Fetched};
use crate::applications::{ApplicationRef, DataKey, current_in, matching_facts};
use crate::criteria::eval::{Evaluation, Waiver, evaluate};
use crate::criteria::{LenderId, LenderStatus, Product};
use crate::facts::application::{ApplicationFacts, Confirmations};
use crate::facts::{DealFacts, DealInput, assemble};
use crate::store::{ReadTx, Revision, Store, StoreError, now};

/// Bump when `assemble` or `evaluate` would give another verdict for the same inputs; it marks older matches.
pub const ENGINE_VERSION: u32 = 1;

/// The JSON layout of `matches.input` and `matches.facts`; a bump leaves older matches unreadable without a reader.
pub const MATCH_FORMAT: u32 = 1;

/// The JSON stored in `matches.input`. A match of a stored application keeps the facts it read;
/// `match_applications` names the revision.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct MatchInput {
    pub analysis_package: Option<Uuid>,
    pub product: Product,
    pub deal: DealInput,
    pub waivers: Vec<Waiver>,
}

/// The application side of a deal.
#[derive(Clone, PartialEq, Debug)]
pub enum ApplicationInput {
    Inline(ApplicationFacts),
    /// A stored application's revision. Matching refuses it unless it is current when the match
    /// is stored.
    Stored(ApplicationRef),
}

#[derive(Clone, PartialEq, Debug)]
pub struct MatchCommand {
    pub analysis_package: Option<Uuid>,
    pub product: Product,
    pub application: ApplicationInput,
    pub confirmations: Confirmations,
    pub waivers: Vec<Waiver>,
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Requester {
    Client(i64),
    /// A person's first match of a deal supersedes nothing.
    Person {
        user: i64,
        supersedes: Option<Uuid>,
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
    /// The stored application revision the facts came from.
    pub application: Option<ApplicationRef>,
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
    #[error("no application data key is configured")]
    ApplicationsUnavailable,
    #[error("no such application")]
    ApplicationNotFound,
    #[error("the application changed: revision {current} is current")]
    ApplicationChanged { current: u32 },
    #[error("the application is a manual-entry draft nobody confirmed")]
    ApplicationUnconfirmed,
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
    /// Opens stored applications; without it a stored application is `ApplicationsUnavailable`.
    key: Option<Arc<DataKey>>,
}

impl Matcher {
    pub fn new(store: Arc<Store>, analysis: Option<AnalysisClient>, key: Option<Arc<DataKey>>) -> Matcher {
        Matcher { store, analysis, key }
    }

    /// Fetches the analysis, then in one write transaction reads the stored application's revision,
    /// refused unless it is current and admitted, and every lender head, and stores the match, so
    /// the match names each revision it read.
    pub async fn run(&self, by: Requester, command: MatchCommand) -> Result<MatchRecord, MatchError> {
        if matches!(command.application, ApplicationInput::Stored(_)) && self.key.is_none() {
            return Err(MatchError::ApplicationsUnavailable);
        }
        let package = match command.analysis_package {
            None => None,
            Some(id) => match self.analysis.as_ref().ok_or(MatchError::AnalysisNotConfigured)?.fetch(id).await? {
                Fetched::Processing { retry_after } => return Err(MatchError::AnalysisNotReady { retry_after }),
                Fetched::Ready(package) => Some(package),
            },
        };
        let created_at = now();
        tokio::task::block_in_place(|| {
            self.store.write(|tx| {
                if let Requester::Person { supersedes: Some(older), .. } = &by
                    && tx.superseded_by(*older)?.is_some()
                {
                    return Err(MatchError::AlreadySuperseded);
                }
                let (application, link) = match command.application {
                    ApplicationInput::Inline(facts) => (facts, None),
                    ApplicationInput::Stored(expected) => {
                        let key = self.key.as_deref().ok_or(MatchError::ApplicationsUnavailable)?;
                        (stored_facts(tx, key, expected, created_at.date())?, Some(expected))
                    }
                };
                let input = MatchInput {
                    analysis_package: command.analysis_package,
                    product: command.product,
                    deal: DealInput { application, confirmations: command.confirmations },
                    waivers: command.waivers,
                };
                let facts = assemble(package.as_ref(), &input.deal, created_at.date());
                let verdicts = tx.heads()?.iter().map(|head| verdict(head, &facts, &input)).collect();
                let record = MatchRecord {
                    id: Uuid::new_v4(),
                    created_at,
                    by,
                    input,
                    facts,
                    engine_version: ENGINE_VERSION,
                    verdicts,
                    application: link,
                };
                tx.insert_match(&record)?;
                Ok(record)
            })
        })
    }
}

/// The facts of the stored revision `expected`, refused unless it is the current one and admitted.
fn stored_facts(
    tx: &ReadTx,
    key: &DataKey,
    expected: ApplicationRef,
    as_of: time::Date,
) -> Result<ApplicationFacts, MatchError> {
    let current = current_in(tx, key, expected.id)?.ok_or(MatchError::ApplicationNotFound)?;
    if current.revision.reference != expected {
        return Err(MatchError::ApplicationChanged { current: current.revision.reference.revision });
    }
    if !current.revision.state.admission.admits_matching() {
        return Err(MatchError::ApplicationUnconfirmed);
    }
    Ok(matching_facts(&current.record().resolve(), as_of))
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

pub struct MatchView {
    pub record: MatchRecord,
    pub revisions: BTreeMap<LenderId, Revision>,
    pub heads: BTreeMap<LenderId, u32>,
    pub superseded_by: Option<Uuid>,
    pub created_by: Creator,
    /// The current revision of the stored application the match read.
    pub application_head: Option<u32>,
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
        let application_head = match record.application {
            None => None,
            Some(read) => Some(
                tx.application_head(read.id)?
                    .ok_or_else(|| StoreError::Corrupt("a matched application has no revision".to_string()))?
                    .revision,
            ),
        };
        Ok(Some(MatchView {
            superseded_by: tx.superseded_by(id)?,
            record,
            revisions,
            heads,
            created_by,
            application_head,
        }))
    }

    pub fn is_current(&self, verdict: &LenderVerdict) -> bool {
        self.heads.get(&verdict.lender) == Some(&verdict.revision)
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

    fn input() -> MatchCommand {
        MatchCommand {
            analysis_package: None,
            product: Product::Mca,
            application: ApplicationInput::Inline(application()),
            confirmations: everything_confirmed(),
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

        let matcher = Matcher::new(store.clone(), None, None);
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
        let matcher = Matcher::new(store.clone(), None, None);
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
        let matcher = Matcher::new(store.clone(), None, None);
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
        let by = Requester::Person { user, supersedes: Some(first.id) };
        let second = matcher.run(by.clone(), reviewed.clone()).await.unwrap();
        assert_eq!(second.verdicts[0].result.key(), "match");
        assert_eq!(store.read(|tx| tx.superseded_by(first.id)).unwrap(), Some(second.id));
        assert!(matches!(matcher.run(by, reviewed).await, Err(MatchError::AlreadySuperseded)));
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_person_can_make_the_first_match_of_a_deal() {
        let store = Arc::new(Store::open_in_memory());
        let author = editor(&store);
        let Author::User { id: user, .. } = author.clone() else { unreachable!() };
        active_lender(&store, &author, "CONTOSO CAPITAL", 600, vec![]);
        let made = Matcher::new(store.clone(), None, None)
            .run(Requester::Person { user, supersedes: None }, input())
            .await
            .unwrap();
        let view = store.read(|tx| MatchView::load(tx, made.id)).unwrap().unwrap();
        assert_eq!(view.record, made);
        assert!(matches!(view.created_by, Creator::Person(ref name) if name == "sample.editor"));
    }

    fn stored_matcher(store: &Arc<Store>) -> Matcher {
        Matcher::new(store.clone(), None, Some(Arc::new(crate::applications::testing::key())))
    }

    fn of_stored(reference: ApplicationRef) -> MatchCommand {
        MatchCommand { application: ApplicationInput::Stored(reference), ..input() }
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_match_reads_a_stored_application_and_names_its_revision() {
        use crate::applications::testing::{service, support::form::Form, upload};
        use crate::facts::Interval;
        use crate::facts::application::{EntityKind, Jurisdiction, YearMonth};
        let store = Arc::new(Store::open_in_memory());
        let author = editor(&store);
        let Author::User { id: user, .. } = author.clone() else { unreachable!() };
        let lender = active_lender(&store, &author, "CONTOSO CAPITAL", 600, vec![]);
        let (applications, reader) = service(&store);
        let reference = upload(&applications, &reader, Form::word(), user);

        let made = stored_matcher(&store)
            .run(Requester::Person { user, supersedes: None }, of_stored(reference))
            .await
            .unwrap();
        assert_eq!(made.application, Some(reference));
        let expected = ApplicationFacts {
            business_state: Jurisdiction::from_code("TX"),
            business_start: YearMonth::new(2019, 4),
            entity: Some(EntityKind::Llc),
            estimated_fico: Some(Interval::point(700)),
            requested_amount_cents: Some(5_000_000),
            open_judgements: Some(false),
            bankruptcy: Some(false),
            tax_liens: Some(false),
            industry_suggestion: None,
        };
        assert_eq!(made.input.deal.application, expected);
        assert_eq!(made.verdicts.iter().find(|v| v.lender == lender.lender).unwrap().result.key(), "match");
        let view = store.read(|tx| MatchView::load(tx, made.id)).unwrap().unwrap();
        assert_eq!(view.record, made, "the match and its application revision read back");
        assert_eq!(view.application_head, Some(1));
        let stored_input = serde_json::to_string(&view.record.input).unwrap();
        assert!(!stored_input.contains("CONTOSO LLC") && !stored_input.contains("application_id"));
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_stale_unconfirmed_or_missing_application_is_refused_and_stores_nothing() {
        use crate::applications::testing::{service, support::form::Form, upload};
        use crate::applications::{ApplicationId, Cause, Saved};
        use crate::store::testing::rows;
        use lender_matching_application::{EditInput, Edits};
        let store = Arc::new(Store::open_in_memory());
        let author = editor(&store);
        let Author::User { id: user, .. } = author.clone() else { unreachable!() };
        let (applications, reader) = service(&store);
        let first = upload(&applications, &reader, Form::word(), user);
        let current = applications.current(first.id).unwrap();
        let edits = Edits::read(
            current.record(),
            &[(crate::applications::testing::LEGAL_NAME, EditInput::Text("FABRIKAM LLC"))],
            now().date(),
        )
        .ok()
        .unwrap();
        assert!(matches!(applications.correct(first, &edits, Cause::Reading, None, user), Ok(Saved::New(_))));
        let person = Requester::Person { user, supersedes: None };
        let matcher = stored_matcher(&store);
        assert!(matches!(
            matcher.run(person.clone(), of_stored(first)).await,
            Err(MatchError::ApplicationChanged { current: 2 })
        ));

        let draft_form = Form { omit: vec!["Secondary Owner Name"], ..Form::word() };
        let draft = upload(&applications, &reader, draft_form, user);
        assert!(matches!(matcher.run(person.clone(), of_stored(draft)).await, Err(MatchError::ApplicationUnconfirmed)));
        let missing = ApplicationRef { id: ApplicationId(Uuid::new_v4()), revision: 1 };
        assert!(matches!(matcher.run(person.clone(), of_stored(missing)).await, Err(MatchError::ApplicationNotFound)));
        let keyless = Matcher::new(store.clone(), None, None);
        let unavailable = keyless.run(person.clone(), of_stored(ApplicationRef { revision: 2, ..first })).await;
        assert!(matches!(unavailable, Err(MatchError::ApplicationsUnavailable)));
        assert_eq!(rows(&store, "matches"), 0);

        let Ok(Saved::New(confirmed)) = applications.confirm_application(draft, user) else { panic!("confirmed") };
        let made = matcher.run(person, of_stored(confirmed.revision.reference)).await.unwrap();
        assert_eq!(made.application, Some(ApplicationRef { id: draft.id, revision: 2 }));
        assert_eq!(made.input.deal.application, ApplicationFacts::default(), "a draft nobody typed into gives no fact");
        assert_eq!((rows(&store, "matches"), rows(&store, "match_applications")), (1, 1));
    }

    #[tokio::test(flavor = "multi_thread")]
    async fn a_package_without_an_analysis_service_is_refused() {
        let store = Arc::new(Store::open_in_memory());
        let mut asked = input();
        asked.analysis_package = Some(Uuid::new_v4());
        let result = Matcher::new(store.clone(), None, None).run(client(&store), asked).await;
        assert!(matches!(result, Err(MatchError::AnalysisNotConfigured)));
    }
}
