use time::macros::date;

use super::*;
use crate::extract::{ManualEntryReason, read};
use crate::fields::{BusinessField as B, OwnerField as O, PropertyField as P, SignatureField as S};
use crate::page::build::PageBuilder;
use crate::page::{PdfFacts, TextPage};
use crate::support::form::*;
use crate::values::EmailFault;

const TODAY: Date = date!(2026 - 10 - 23);

fn reading_of(page: TextPage) -> Reading {
    let certificate = certificate(PageBuilder::new(), &[("SAMPLE OWNER", "owner@example.com")]).build();
    read(&PdfFacts { created_on: Some(date!(2026 - 10 - 21)), pages: vec![page, certificate] })
}

fn reading(form: &Form) -> Reading {
    reading_of(form.draw(PageBuilder::new()).build())
}

fn manual_entry() -> Reading {
    let page = Form { omit: vec!["Secondary Owner Name"], ..Form::word() }.draw(PageBuilder::new()).build();
    let reading = reading_of(page);
    assert!(matches!(reading.document, Document::ManualEntry(ManualEntryReason::UnknownLayout)));
    reading
}

fn first(reading: &Reading) -> RevisionState {
    RevisionState::initial(&reading.document).expect("not refused")
}

fn text(resolved: &Resolved, field: FieldId) -> Option<String> {
    resolved.value(field).map(FieldValue::canonical)
}

fn origin(resolved: &Resolved, field: FieldId) -> Option<Origin> {
    match resolved.get(field).current {
        Current::Value { origin, .. } | Current::Empty { origin } => Some(origin),
        Current::NeedsReview => None,
    }
}

fn edits(reading: &Reading, state: &RevisionState, inputs: &[(FieldId, EditInput)]) -> Edits {
    Edits::read(Record { reading, state }, inputs, TODAY).unwrap_or_else(|refused| panic!("refused: {refused:?}"))
}

fn business(field: B) -> FieldId {
    FieldId::Business(field)
}

fn principal(field: O) -> FieldId {
    FieldId::Owner(OwnerSlot::Principal, field)
}

fn secondary(field: O) -> FieldId {
    FieldId::Owner(OwnerSlot::Secondary, field)
}

#[test]
fn the_first_revision_inherits_every_reading_and_needs_nothing() {
    let reading = reading(&Form::word());
    let state = first(&reading);
    assert_eq!(state.admission, Admission::Recognized);
    let resolved = Record { reading: &reading, state: &state }.resolve();
    assert_eq!(text(&resolved, business(B::LegalName)).as_deref(), Some("CONTOSO LLC"));
    assert_eq!(origin(&resolved, business(B::LegalName)), Some(Origin::Parse));
    assert!(resolved.iter().all(|(_, field)| field.attention.is_empty()));
}

#[test]
fn a_set_an_empty_and_an_inherit_resolve_to_the_value_nothing_and_the_reading() {
    let reading = reading(&Form::word());
    let state = first(&reading);
    let edited = state.edited(&edits(
        &reading,
        &state,
        &[(business(B::LegalName), EditInput::Text(" FABRIKAM   LLC ")), (business(B::Dba), EditInput::Clear)],
    ));
    let resolved = Record { reading: &reading, state: &edited }.resolve();
    assert_eq!(text(&resolved, business(B::LegalName)).as_deref(), Some("FABRIKAM LLC"));
    assert_eq!(origin(&resolved, business(B::LegalName)), Some(Origin::Person));
    assert!(matches!(resolved.get(business(B::Dba)).current, Current::Empty { origin: Origin::Person }));
    assert!(*edited.overrides.get(business(B::Dba)) == Override::Empty(EmptyReason::Cleared));

    let back = edited.edited(&edits(&reading, &edited, &[(business(B::LegalName), EditInput::UseParse)]));
    let resolved = Record { reading: &reading, state: &back }.resolve();
    assert_eq!(text(&resolved, business(B::LegalName)).as_deref(), Some("CONTOSO LLC"));
    assert_eq!(origin(&resolved, business(B::LegalName)), Some(Origin::Parse));
}

#[test]
fn na_typed_by_a_person_empties_the_field_as_not_applicable() {
    let reading = reading(&Form::word());
    let state = first(&reading);
    let edited = state.edited(&edits(&reading, &state, &[(business(B::Website), EditInput::Text("n/a"))]));
    assert!(*edited.overrides.get(business(B::Website)) == Override::Empty(EmptyReason::NotApplicable));
    let history = edited.edited(&edits(&reading, &edited, &[(FieldId::Property(P::TaxLiens), EditInput::Text("N/A"))]));
    let resolved = Record { reading: &reading, state: &history }.resolve();
    assert_eq!(
        text(&resolved, FieldId::Property(P::TaxLiens)).as_deref(),
        Some("NO"),
        "N/A on a history question is no"
    );
}

#[test]
fn an_identical_edit_gives_an_identical_state() {
    let reading = reading(&Form::word());
    let state = first(&reading);
    let input = [(business(B::LegalName), EditInput::Text("FABRIKAM LLC"))];
    let once = state.edited(&edits(&reading, &state, &input));
    let twice = once.edited(&edits(&reading, &once, &input));
    assert!(once == twice);
    assert!(once != state);
    assert!(edits(&reading, &state, &[]).is_empty());
}

#[test]
fn ownership_follows_the_number_of_owners_whatever_was_printed() {
    let two = reading(&Form::word().set(principal(O::OwnershipPercent), "75"));
    let resolved = Record { reading: &two, state: &first(&two) }.resolve();
    assert!(resolved.has_second_owner());
    for slot in [OwnerSlot::Principal, OwnerSlot::Secondary] {
        let share = FieldId::Owner(slot, O::OwnershipPercent);
        assert_eq!(text(&resolved, share).as_deref(), Some("50.00"), "{share}");
        assert_eq!(origin(&resolved, share), Some(Origin::Derived));
    }
    let Document::Application(form) = &two.document else { panic!("an application") };
    let printed = form.fields.get(principal(O::OwnershipPercent)).value().map(FieldValue::canonical);
    assert_eq!(printed.as_deref(), Some("75.00"), "the printed value stays as evidence");

    let mut one = Form::word();
    for field in OwnerSlot::Secondary.fields() {
        one = one.clear(field);
    }
    let one = reading(&one);
    let resolved = Record { reading: &one, state: &first(&one) }.resolve();
    assert!(!resolved.has_second_owner());
    assert_eq!(text(&resolved, principal(O::OwnershipPercent)).as_deref(), Some("100.00"));
    assert!(matches!(resolved.get(secondary(O::OwnershipPercent)).current, Current::Empty { origin: Origin::Derived }));
}

#[test]
fn derived_fields_and_signature_dates_refuse_edits() {
    let reading = reading(&Form::word());
    let state = first(&reading);
    let inputs = [
        (principal(O::OwnershipPercent), EditInput::Text("100")),
        (FieldId::Signature(S::ApplicantOneDate), EditInput::Clear),
        (business(B::LegalName), EditInput::Text("FABRIKAM LLC")),
    ];
    let refused = Edits::read(Record { reading: &reading, state: &state }, &inputs, TODAY).err().unwrap();
    assert_eq!(
        refused,
        [
            (principal(O::OwnershipPercent), EditRefusal::NotEditable),
            (FieldId::Signature(S::ApplicantOneDate), EditRefusal::NotEditable)
        ]
    );
}

#[test]
fn a_refused_or_repeated_input_names_its_field_and_reason() {
    let reading = reading(&Form::word());
    let state = first(&reading);
    let inputs = [
        (business(B::Email), EditInput::Text("office.example.com")),
        (business(B::Zip), EditInput::Text("787")),
        (business(B::City), EditInput::Text("AUSTIN")),
        (business(B::City), EditInput::Clear),
    ];
    let refused = Edits::read(Record { reading: &reading, state: &state }, &inputs, TODAY).err().unwrap();
    assert_eq!(
        refused,
        [
            (business(B::Email), EditRefusal::Value(Refusal::Email(EmailFault::NoAt))),
            (business(B::Zip), EditRefusal::Value(Refusal::Format)),
            (business(B::City), EditRefusal::Repeated),
        ]
    );
}

#[test]
fn a_state_edit_sets_the_country_its_dates_read_with() {
    let reading = reading(&Form::word());
    let state = first(&reading);
    let start = business(B::StartDate);
    let us = edits(&reading, &state, &[(start, EditInput::Text("04/05/2019"))]);
    let resolved = Record { reading: &reading, state: &state.edited(&us) }.resolve();
    assert_eq!(text(&resolved, start).as_deref(), Some("04/05/2019"));
    let canadian = [(start, EditInput::Text("04/05/2019")), (business(B::State), EditInput::Text("ON"))];
    let refused = Edits::read(Record { reading: &reading, state: &state }, &canadian, TODAY).err().unwrap();
    assert_eq!(refused, [(start, EditRefusal::Value(Refusal::Ambiguous))]);
}

#[test]
fn attention_names_required_empty_refused_unlocated_and_doubtful_fields() {
    let mut rows = word_rows();
    rows[0].1.retain(|(text, _, _)| *text != "Business Legal Name");
    let page = Form { layout: Layout { rows, ..word() }, omit: vec!["Fax"], ..Form::word() }
        .set(business(B::Email), "office.example.com")
        .clear(principal(O::Zip))
        .draw(PageBuilder::new())
        .text("Calibri", LABEL_SIZE, 40.0, HEADING.1 + 18.0, "Business Legal Name Contoso City Catering")
        .build();
    let reading = reading_of(page);
    let resolved = Record { reading: &reading, state: &first(&reading) }.resolve();
    let attention = |field| resolved.get(field).attention.clone();
    assert_eq!(
        attention(business(B::Email)),
        [Attention::Refused(Refusal::Email(EmailFault::NoAt)), Attention::RequiredEmpty]
    );
    assert_eq!(attention(principal(O::Zip)), [Attention::RequiredEmpty]);
    assert_eq!(attention(business(B::Fax)), [Attention::Unlocated(Unlocated::LabelMissing)]);
    assert_eq!(attention(business(B::LegalName)), [Attention::Doubtful(Doubt::StrayLabel)]);
    assert_eq!(attention(business(B::City)), [Attention::Doubtful(Doubt::LabelFoundTwice), Attention::RequiredEmpty]);
    assert!(matches!(resolved.get(business(B::City)).current, Current::NeedsReview));
    assert!(attention(business(B::Website)).is_empty());
}

#[test]
fn secondary_details_are_required_only_while_a_secondary_owner_is_named() {
    let reading = reading(&Form::word().clear(secondary(O::Phone)).clear(secondary(O::Ssn)));
    let state = first(&reading);
    let resolved = Record { reading: &reading, state: &state }.resolve();
    let required: Vec<FieldId> = resolved
        .iter()
        .filter(|(_, field)| field.attention.contains(&Attention::RequiredEmpty))
        .map(|(field, _)| field)
        .collect();
    assert_eq!(required, [secondary(O::Phone), secondary(O::Ssn)]);

    let removed = state.edited(&Edits::remove_second_owner());
    let resolved = Record { reading: &reading, state: &removed }.resolve();
    assert!(!resolved.has_second_owner());
    assert!(resolved.iter().all(|(_, field)| field.attention.is_empty()));
    assert_eq!(text(&resolved, principal(O::OwnershipPercent)).as_deref(), Some("100.00"));
    for field in OwnerSlot::Secondary.fields().filter(|field| field.spec().editable()) {
        assert!(*removed.overrides.get(field) == Override::Empty(EmptyReason::RemovedOwner), "{field}");
    }
    assert!(*removed.overrides.get(secondary(O::OwnershipPercent)) == Override::Inherit);

    let named =
        removed.edited(&edits(&reading, &removed, &[(secondary(O::Name), EditInput::Text("NORTHWIND PARTNER"))]));
    let resolved = Record { reading: &reading, state: &named }.resolve();
    assert!(resolved.has_second_owner());
    assert!(resolved.get(secondary(O::City)).attention.contains(&Attention::RequiredEmpty), "the owner is back");
    assert_eq!(text(&resolved, principal(O::OwnershipPercent)).as_deref(), Some("50.00"));
}

#[test]
fn adopting_a_parse_keeps_every_override_and_follows_the_new_reading_elsewhere() {
    let old = reading(&Form::word());
    let state = first(&old);
    let edited = state.edited(&edits(
        &old,
        &state,
        &[(business(B::LegalName), EditInput::Text("FABRIKAM LLC")), (business(B::Dba), EditInput::Clear)],
    ));
    let new = reading(
        &Form::word()
            .set(business(B::LegalName), "NORTHWIND LLC")
            .set(business(B::Dba), "SAMPLE")
            .set(business(B::City), "DALLAS"),
    );
    let adopted = edited.adopting(&new.document).unwrap();
    assert!(adopted.overrides == edited.overrides);
    let resolved = Record { reading: &new, state: &adopted }.resolve();
    assert_eq!(text(&resolved, business(B::LegalName)).as_deref(), Some("FABRIKAM LLC"));
    assert_eq!(text(&resolved, business(B::Dba)), None);
    assert_eq!(text(&resolved, business(B::City)).as_deref(), Some("DALLAS"));
}

#[test]
fn a_manual_entry_draft_waits_for_a_person_and_fills_from_overrides_only() {
    let draft = manual_entry();
    let state = first(&draft);
    assert_eq!(state.admission, Admission::AwaitingConfirmation);
    assert!(!state.admission.admits_matching());
    let resolved = Record { reading: &draft, state: &state }.resolve();
    assert_eq!(text(&resolved, business(B::LegalName)), None);
    assert!(resolved.get(business(B::City)).attention == [Attention::RequiredEmpty]);

    let typed = state.edited(&edits(&draft, &state, &[(principal(O::BirthDate), EditInput::Text("04/15/1980"))]));
    let resolved = Record { reading: &draft, state: &typed }.resolve();
    assert_eq!(text(&resolved, principal(O::BirthDate)).as_deref(), Some("04/15/1980"));

    let confirmed = typed.confirmed();
    assert_eq!(confirmed.admission, Admission::Confirmed);
    assert!(confirmed.admission.admits_matching());
    assert!(confirmed.confirmed() == confirmed);
    let form = reading(&Form::word());
    assert_eq!(confirmed.adopting(&form.document).unwrap().admission, Admission::Confirmed, "a confirmation stays");
    assert_eq!(first(&form).adopting(&draft.document).unwrap().admission, Admission::AwaitingConfirmation);
}

#[test]
fn a_sampled_document_waits_for_its_audit_which_settles_whether_it_is_an_application() {
    let form = reading(&Form::word());
    let sampled = RevisionState::awaiting_audit();
    assert!(!sampled.admission.admits_matching());
    assert_eq!(sampled.adopting(&form.document).unwrap().admission, Admission::AwaitingAudit);
    assert!(sampled.confirmed() == sampled, "only an audit settles it");
    let typed = edits(&form, &sampled, &[(business(B::LegalName), EditInput::Text("FABRIKAM LLC"))]);
    let audited = sampled.audited(&typed, true);
    assert_eq!(audited.admission, Admission::Confirmed);
    let resolved = Record { reading: &form, state: &audited }.resolve();
    assert_eq!(text(&resolved, business(B::LegalName)).as_deref(), Some("FABRIKAM LLC"));
    let other = sampled.audited(&typed, false);
    assert_eq!(other.admission, Admission::NotAnApplication);
    assert!(!other.admission.admits_matching());
    assert_eq!(other.adopting(&form.document).unwrap().admission, Admission::NotAnApplication);
}

#[test]
fn a_refused_document_has_no_state() {
    let contract =
        PageBuilder::new().text("TimesNewRomanPS-BoldMT", 12.0, 40.0, 40.0, "RECEIVABLES PURCHASE AGREEMENT");
    let mut page = contract;
    for line in 0..10 {
        page = page.text("ArialMT", 9.0, 40.0, 80.0 + 12.0 * line as f32, "SAMPLE TERMS OF THE AGREEMENT ARE HERE");
    }
    let refused = reading_of(page.build());
    assert!(RevisionState::initial(&refused.document).is_none());
    assert!(first(&reading(&Form::word())).adopting(&refused.document).is_none());
}

#[test]
fn a_reading_and_a_state_survive_a_round_trip() {
    let reading = reading(&Form { layout: pdfescape(), ..Form::word() });
    let state = first(&reading);
    let state = state.edited(&edits(
        &reading,
        &state,
        &[(principal(O::Ssn), EditInput::Text("900-55-0101")), (business(B::Website), EditInput::Clear)],
    ));
    let back: Reading = serde_json::from_str(&serde_json::to_string(&reading).unwrap()).unwrap();
    let back_state: RevisionState = serde_json::from_str(&serde_json::to_string(&state).unwrap()).unwrap();
    assert!(back_state == state);
    let (Document::Application(a), Document::Application(b)) = (&reading.document, &back.document) else {
        panic!("applications")
    };
    assert_eq!(a.layout, b.layout);
    assert_eq!(back.signed_on, reading.signed_on);
    for (field, original) in a.fields.iter() {
        let restored = b.fields.get(field);
        assert_eq!(original.outcome(), restored.outcome(), "{field}");
        assert!(original.value() == restored.value(), "{field}");
        assert_eq!(original.evidence().map(|e| (&e.text, e.rect)), restored.evidence().map(|e| (&e.text, e.rect)));
    }
    let resolved = Record { reading: &back, state: &back_state }.resolve();
    assert_eq!(text(&resolved, principal(O::Ssn)).as_deref(), Some("900-55-0101"));
    let signers = |reading: &Reading| reading.certificate.as_ref().map(|c| c.signers.len());
    assert_eq!(signers(&back), signers(&reading));
}

#[test]
fn a_stored_field_map_needs_every_field_once() {
    let map: FieldMap<u8> = FieldMap::from_fn(|_| 1);
    let mut json: serde_json::Value = serde_json::to_value(&map).unwrap();
    assert!(serde_json::from_value::<FieldMap<u8>>(json.clone()).is_ok());
    json.as_object_mut().unwrap().remove("business.dba");
    assert!(serde_json::from_value::<FieldMap<u8>>(json.clone()).is_err());
    json.as_object_mut().unwrap().insert("business.ssn".to_string(), 1.into());
    assert!(serde_json::from_value::<FieldMap<u8>>(json).is_err());
}
