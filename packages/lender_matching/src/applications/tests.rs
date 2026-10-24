use std::sync::Arc;

use lender_matching_application::extract::ManualEntryReason;
use lender_matching_application::fields::{BusinessField as B, FieldId, OwnerField as O, OwnerSlot};
use lender_matching_application::{Admission, EditInput, Edits, FieldValue, Override};
use time::macros::date;

use super::testing::support::form::{Form, sample_values};
use super::testing::{ENVELOPE, FakeReader, OTHER_ENVELOPE, application, contract};
use super::*;
use crate::store::auth::Role;
use crate::store::testing::{raw, rows};

const LEGAL_NAME: FieldId = FieldId::Business(B::LegalName);

struct Setup {
    store: Arc<Store>,
    reader: Arc<FakeReader>,
    applications: Applications,
    reviewer: i64,
}

fn setup_with(store: Store) -> Setup {
    let store = Arc::new(store);
    let reviewer = store.write(|tx| tx.add_user("sample.reviewer", "correct horse battery", Role::Reviewer)).unwrap();
    let reader = Arc::new(FakeReader::default());
    let applications = Applications::new(store.clone(), Arc::new(DataKey::new([7; 32])), reader.clone());
    Setup { store, reader, applications, reviewer }
}

fn setup() -> Setup {
    setup_with(Store::open_in_memory())
}

impl Setup {
    fn upload(&self, form: Form) -> ApplicationRef {
        let pdf = self.reader.knows(application(form, ENVELOPE, 21));
        match self.applications.upload(&pdf, self.reviewer).unwrap() {
            Intake::Stored { reference, manual_entry: None, same_envelope: None } => reference,
            _ => panic!("not stored as a new application"),
        }
    }

    fn edits(&self, reference: ApplicationRef, inputs: &[(FieldId, EditInput)]) -> Edits {
        let current = self.applications.current(reference.id).unwrap();
        Edits::read(current.record(), inputs, date!(2026 - 10 - 23)).map_err(|refused| format!("{refused:?}")).unwrap()
    }

    fn text(&self, id: ApplicationId, field: FieldId) -> Option<String> {
        self.applications.current(id).unwrap().record().resolve().value(field).map(FieldValue::canonical)
    }
}

fn saved(result: Result<Saved, ApplicationError>) -> Snapshot {
    match result {
        Ok(Saved::New(snapshot)) => snapshot,
        Ok(Saved::Unchanged(_)) => panic!("nothing was saved"),
        Err(error) => panic!("{error}"),
    }
}

fn unchanged(result: Result<Saved, ApplicationError>) -> Snapshot {
    match result {
        Ok(Saved::Unchanged(snapshot)) => snapshot,
        Ok(Saved::New(_)) => panic!("a revision was saved"),
        Err(error) => panic!("{error}"),
    }
}

#[test]
fn an_upload_stores_the_pdf_its_parse_and_revision_1_and_identical_bytes_give_it_back() {
    let setup = setup();
    let reference = setup.upload(Form::word());
    assert_eq!(reference.revision, 1);
    let current = setup.applications.current(reference.id).unwrap();
    assert_eq!(current.revision.kind, RevisionKind::Upload);
    assert_eq!(current.revision.author, "sample.reviewer");
    assert_eq!(current.revision.state.admission, Admission::Recognized);
    assert_eq!(current.parse.parser_version, PARSER_VERSION);
    assert_eq!(current.parse.id, current.revision.parse, "the snapshot holds the parse its revision selects");
    assert!(current.revision.saved_at <= now() && current.parse.created_at <= current.revision.saved_at);
    assert_eq!(setup.text(reference.id, LEGAL_NAME).as_deref(), Some("CONTOSO LLC"));

    let reads = setup.reader.reads();
    let pdf = application(Form::word(), ENVELOPE, 21).pdf;
    let again = setup.applications.upload(&pdf, setup.reviewer).unwrap();
    assert!(matches!(again, Intake::AlreadyStored(existing) if existing == reference));
    assert_eq!(setup.reader.reads(), reads, "identical bytes are not read again");
    assert_eq!(rows(&setup.store, "applications"), 1);
}

#[test]
fn a_refused_or_unreadable_document_stores_nothing() {
    let setup = setup();
    let pdf = setup.reader.knows(contract());
    assert!(matches!(
        setup.applications.upload(&pdf, setup.reviewer).unwrap(),
        Intake::Refused(RefusalReason::Contract)
    ));
    let error = setup.applications.upload(b"SAMPLE OWNER 900-12-3456", setup.reviewer).err().unwrap();
    assert!(matches!(error, ApplicationError::Pdf(WorkerError::Read(_))));
    assert_eq!(error.to_string(), "the PDF could not be read: not_pdf");
    for table in ["applications", "application_parses", "application_revisions"] {
        assert_eq!(rows(&setup.store, table), 0, "{table}");
    }
}

#[test]
fn an_unknown_layout_is_stored_as_a_draft_that_waits_for_confirmation() {
    let setup = setup();
    let form = Form { omit: vec!["Secondary Owner Name"], ..Form::word() };
    let pdf = setup.reader.knows(application(form, ENVELOPE, 21));
    let Intake::Stored { reference, manual_entry, .. } = setup.applications.upload(&pdf, setup.reviewer).unwrap()
    else {
        panic!("stored")
    };
    assert_eq!(manual_entry, Some(ManualEntryReason::UnknownLayout));
    let draft = setup.applications.current(reference.id).unwrap();
    assert_eq!(draft.revision.state.admission, Admission::AwaitingConfirmation);

    let confirmed = saved(setup.applications.confirm_application(reference, setup.reviewer));
    assert_eq!(confirmed.revision.state.admission, Admission::Confirmed);
    assert_eq!(confirmed.revision.kind, RevisionKind::ConfirmApplication);
    unchanged(setup.applications.confirm_application(confirmed.revision.reference, setup.reviewer));
}

#[test]
fn another_file_of_the_same_envelope_is_another_application_that_names_the_first() {
    let setup = setup();
    let first = setup.upload(Form::word());
    let pdf = setup.reader.knows(application(Form::word(), ENVELOPE, 22));
    let Intake::Stored { reference, same_envelope, .. } = setup.applications.upload(&pdf, setup.reviewer).unwrap()
    else {
        panic!("stored")
    };
    assert_ne!(reference.id, first.id);
    assert_eq!(same_envelope, Some(first.id));
    let other = setup.reader.knows(application(Form::word(), OTHER_ENVELOPE, 23));
    assert!(matches!(
        setup.applications.upload(&other, setup.reviewer).unwrap(),
        Intake::Stored { same_envelope: None, .. }
    ));
}

#[test]
fn a_correction_saves_a_revision_with_its_cause_and_reason_and_a_repeat_writes_nothing() {
    let setup = setup();
    let first = setup.upload(Form::word());
    let edits = setup.edits(first, &[(LEGAL_NAME, EditInput::Text("FABRIKAM LLC"))]);
    let reason = Some("  the merchant wrote SAMPLE HOLDINGS  ");
    let second = saved(setup.applications.correct(first, &edits, Cause::Merchant, reason, setup.reviewer));
    assert_eq!(second.revision.reference, ApplicationRef { id: first.id, revision: 2 });
    assert_eq!(second.revision.kind, RevisionKind::Edit(Cause::Merchant));
    assert_eq!(second.revision.reason.as_deref(), Some("the merchant wrote SAMPLE HOLDINGS"));
    assert_eq!(setup.text(first.id, LEGAL_NAME).as_deref(), Some("FABRIKAM LLC"));

    let repeat = unchanged(setup.applications.correct(first, &edits, Cause::Merchant, None, setup.reviewer));
    assert_eq!(repeat.revision.reference.revision, 2, "a double submit is a no-op");

    let other = setup.edits(first, &[(LEGAL_NAME, EditInput::Text("NORTHWIND LLC"))]);
    let Err(ApplicationError::Conflict { head }) =
        setup.applications.correct(first, &other, Cause::Reading, None, setup.reviewer)
    else {
        panic!("a stale base is a conflict")
    };
    assert_eq!(head.revision.reference.revision, 2);
    assert_eq!(head.record().resolve().value(LEGAL_NAME).map(FieldValue::canonical).as_deref(), Some("FABRIKAM LLC"));

    let history = setup.applications.history(first.id).unwrap();
    let kinds: Vec<RevisionKind> = history.iter().map(|revision| revision.kind).collect();
    assert_eq!(kinds, [RevisionKind::Upload, RevisionKind::Edit(Cause::Merchant)]);
    assert_eq!(rows(&setup.store, "application_revisions"), 2);
}

#[test]
fn removing_the_second_owner_is_one_edit_revision() {
    let setup = setup();
    let first = setup.upload(Form::word());
    let removed =
        saved(setup.applications.correct(first, &Edits::remove_second_owner(), Cause::Merchant, None, setup.reviewer));
    let resolved = removed.record().resolve();
    assert!(!resolved.has_second_owner());
    let principal = FieldId::Owner(OwnerSlot::Principal, O::OwnershipPercent);
    assert_eq!(resolved.value(principal).map(FieldValue::canonical).as_deref(), Some("100.00"));
}

#[test]
fn a_reparse_is_stored_once_per_parser_and_adopting_it_keeps_every_override() {
    let setup = setup();
    let older = Applications {
        parser: [1; 32],
        ..Applications::new(setup.store.clone(), Arc::new(DataKey::new([7; 32])), setup.reader.clone())
    };
    let pdf = setup.reader.knows(application(Form::word(), ENVELOPE, 21));
    let Intake::Stored { reference: first, .. } = older.upload(&pdf, setup.reviewer).unwrap() else { panic!("stored") };
    let edits = setup.edits(first, &[(LEGAL_NAME, EditInput::Text("FABRIKAM LLC"))]);
    let edited = saved(setup.applications.correct(first, &edits, Cause::Reading, None, setup.reviewer));
    let selected = edited.revision.parse;

    let reads = setup.reader.reads();
    let candidate = setup.applications.reparse(first.id).unwrap();
    assert_ne!(candidate, selected);
    assert_eq!(setup.reader.reads(), reads + 1);
    assert_eq!(setup.applications.reparse(first.id).unwrap(), candidate, "one parse per parser");
    assert_eq!(older.reparse(first.id).unwrap(), selected);
    assert_eq!(setup.reader.reads(), reads + 1, "a stored parse is not read again");
    assert_eq!(setup.applications.current(first.id).unwrap().revision.parse, selected, "a reparse selects nothing");
    assert_eq!(setup.applications.parse(first.id, candidate).unwrap().parser_version, PARSER_VERSION);

    let stale = first;
    let Err(ApplicationError::Conflict { .. }) = setup.applications.adopt_parse(stale, candidate, setup.reviewer)
    else {
        panic!("a stale base is a conflict")
    };
    let adopted = saved(setup.applications.adopt_parse(edited.revision.reference, candidate, setup.reviewer));
    assert_eq!((adopted.revision.parse, adopted.revision.kind), (candidate, RevisionKind::AdoptParse));
    assert!(adopted.revision.state.overrides == edited.revision.state.overrides);
    assert_eq!(setup.text(first.id, LEGAL_NAME).as_deref(), Some("FABRIKAM LLC"));
    unchanged(setup.applications.adopt_parse(adopted.revision.reference, candidate, setup.reviewer));
    let missing = ParseId(Uuid::new_v4());
    assert!(matches!(
        setup.applications.adopt_parse(adopted.revision.reference, missing, setup.reviewer),
        Err(ApplicationError::NotFound)
    ));
}

#[test]
fn a_parse_that_refuses_the_document_cannot_be_adopted() {
    let setup = setup();
    let older = Applications {
        parser: [1; 32],
        ..Applications::new(setup.store.clone(), Arc::new(DataKey::new([7; 32])), setup.reader.clone())
    };
    let pdf = setup.reader.knows(application(Form::word(), ENVELOPE, 21));
    let Intake::Stored { reference, .. } = older.upload(&pdf, setup.reviewer).unwrap() else { panic!("stored") };
    setup.reader.knows(super::testing::Document::reading_as(pdf, contract()));
    let candidate = setup.applications.reparse(reference.id).unwrap();
    assert!(matches!(
        setup.applications.adopt_parse(reference, candidate, setup.reviewer),
        Err(ApplicationError::NotAnApplication)
    ));
}

#[test]
fn stored_rows_open_only_with_their_key_and_cannot_be_rewritten() {
    let setup = setup();
    let reference = setup.upload(Form::word());
    assert!(check_key(&setup.store, &DataKey::new([7; 32])).is_ok());
    let message = check_key(&setup.store, &DataKey::new([8; 32])).err().unwrap();
    assert_eq!(message, "APPLICATION_DATA_KEY is not the key that sealed the stored applications");
    let other = Applications::new(setup.store.clone(), Arc::new(DataKey::new([8; 32])), setup.reader.clone());
    assert!(matches!(other.current(reference.id), Err(ApplicationError::Store(StoreError::Corrupt(_)))));

    for sql in [
        "UPDATE applications SET uploaded_by = 2",
        "DELETE FROM applications",
        "UPDATE application_parses SET format = 2",
        "DELETE FROM application_parses",
        "UPDATE application_revisions SET format = 2",
        "DELETE FROM application_revisions",
    ] {
        let error = raw(&setup.store, sql).expect_err(sql).to_string();
        assert!(error.contains("immutable"), "{sql}: {error}");
    }
}

#[test]
fn the_database_file_holds_no_fabricated_value() {
    let directory = std::env::temp_dir().join(format!("lender-matching-applications-{}", Uuid::new_v4()));
    std::fs::create_dir_all(&directory).unwrap();
    let setup = setup_with(Store::open(&directory.join("store.sqlite3")).unwrap());
    let first = setup.upload(Form::word());
    let edits = setup.edits(first, &[(LEGAL_NAME, EditInput::Text("FABRIKAM SAMPLE HOLDINGS"))]);
    let reason = "The merchant wrote NORTHWIND TRADERS on page 2";
    saved(setup.applications.correct(first, &edits, Cause::Merchant, Some(reason), setup.reviewer));
    assert!(
        *setup.applications.current(first.id).unwrap().revision.state.overrides.get(LEGAL_NAME) != Override::Inherit
    );
    drop(setup);

    let mut bytes = Vec::new();
    for entry in std::fs::read_dir(&directory).unwrap() {
        bytes.extend(std::fs::read(entry.unwrap().path()).unwrap());
    }
    let mut secrets: Vec<String> = sample_values().into_iter().map(|(_, value)| value.to_string()).collect();
    secrets.extend(
        ["FABRIKAM SAMPLE HOLDINGS", reason, "NORTHWIND TRADERS", "SAMPLE OWNER", "owner@example.com", ENVELOPE]
            .map(String::from),
    );
    for secret in secrets.iter().filter(|secret| secret.len() > 3) {
        assert!(!bytes.windows(secret.len()).any(|window| window == secret.as_bytes()), "the database holds {secret}");
    }
    std::fs::remove_dir_all(&directory).unwrap();
}

fn facts_of(form: Form) -> crate::facts::application::ApplicationFacts {
    let setup = setup();
    let reference = setup.upload(form);
    matching_facts(&setup.applications.current(reference.id).unwrap().record().resolve(), date!(2026 - 10 - 23))
}

#[test]
fn matching_reads_a_requested_amount_only_in_dollars_of_a_us_business() {
    use lender_matching_application::fields::PropertyField as P;
    let requested = FieldId::Property(P::RequestedAmount);
    let state = FieldId::Business(B::State);
    let amount = |form: Form| facts_of(form).requested_amount_cents;
    assert_eq!(amount(Form::word()), Some(5_000_000), "a bare dollar sign in Texas");
    assert_eq!(amount(Form::word().set(requested, "50,000")), Some(5_000_000), "unmarked in Texas");
    assert_eq!(amount(Form::word().set(requested, "50,000 CAD")), None, "Canadian dollars");
    assert_eq!(amount(Form::word().set(requested, "0")), None, "nothing requested");
    assert_eq!(amount(Form::word().set(state, "ON")), None, "a Canadian business");
    assert_eq!(amount(Form::word().set(state, "PR")), Some(5_000_000), "a US territory");
}

#[test]
fn matching_reads_the_start_month_the_entity_kind_and_the_history_answers() {
    use crate::facts::application::{EntityKind, YearMonth};
    use lender_matching_application::fields::PropertyField as P;
    let start = FieldId::Business(B::StartDate);
    let facts = facts_of(
        Form::word()
            .set(start, "05/2020")
            .set(FieldId::Business(B::Entity), "S CORP")
            .set(FieldId::Property(P::OpenJudgements), "YES")
            .set(FieldId::Property(P::EstimatedFico), "650-700"),
    );
    assert_eq!(facts.business_start, YearMonth::new(2020, 5));
    assert_eq!(facts.entity, Some(EntityKind::Corporation));
    assert_eq!((facts.open_judgements, facts.bankruptcy, facts.tax_liens), (Some(true), Some(false), Some(false)));
    assert_eq!(facts.estimated_fico, crate::facts::Interval::between(650, 700));
    assert_eq!(facts.industry_suggestion, None);
    let refused = facts_of(Form::word().set(start, "Q2 2019").set(FieldId::Property(P::Bankruptcy), "MAYBE"));
    assert_eq!((refused.business_start, refused.bankruptcy), (None, None), "a refused reading supplies no fact");
}
