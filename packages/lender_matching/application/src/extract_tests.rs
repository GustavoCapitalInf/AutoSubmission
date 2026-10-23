use time::macros::date;

use super::*;
use crate::fields::{BusinessField as B, OwnerField as O, OwnerSlot, PropertyField as P, SignatureField as S};
use crate::page::build::PageBuilder;
use crate::support::form::*;

fn page(form: &Form) -> TextPage {
    form.draw(PageBuilder::new()).build()
}

fn read_form_page(form: &Form) -> Reading {
    read_pages(vec![page(form)])
}

fn read_pages(mut pages: Vec<TextPage>) -> Reading {
    pages.push(certificate(PageBuilder::new(), &[("SAMPLE OWNER", "owner@example.com")]).build());
    read(&PdfFacts { created_on: Some(date!(2026 - 10 - 21)), pages })
}

fn form(reading: &Reading) -> &FormReading {
    match &reading.document {
        Document::Application(form) => form,
        Document::ManualEntry(why) => panic!("manual entry: {why:?}"),
        Document::Refused(why) => panic!("refused: {why:?}"),
    }
}

fn canonical(form: &FormReading, field: FieldId) -> Option<String> {
    form.fields.get(field).value().map(FieldValue::canonical)
}

fn outcome(form: &FormReading, field: FieldId) -> Outcome {
    form.fields.get(field).outcome()
}

fn assert_reads_every_sample_value(reading: &Reading, layout: &str) {
    let form = form(reading);
    assert_eq!(form.layout.as_str(), layout);
    for (field, text) in expected() {
        assert_eq!(canonical(form, field).as_deref(), Some(text), "{field}: {:?}", outcome(form, field));
    }
    assert_eq!(form.fields.iter().filter(|(_, reading)| reading.outcome() != Outcome::Read).count(), 0);
    assert!(form.unplaced.is_empty(), "unplaced: {}", form.unplaced.len());
}

#[test]
fn the_word_layout_reads_every_field() {
    let reading = read_form_page(&Form::word());
    assert_reads_every_sample_value(&reading, "word");
    assert_eq!(reading.signed_on, Some(SignedOn::Certificate(date!(2026 - 10 - 20))));
    let dy: Vec<f32> = reading.offsets.iter().map(|offset| offset.dy).collect();
    assert_eq!(dy, [18.0, 129.0, 256.0, 330.0]);
}

#[test]
fn the_pdfescape_layout_reads_the_same_values() {
    let form = Form { layout: pdfescape(), ..Form::word() };
    assert_reads_every_sample_value(&read_form_page(&form), "pdfescape");
}

#[test]
fn the_pdfescape_rep_header_and_footer_are_form_text() {
    let reading = read_form_page(&Form { layout: pdfescape(), ..Form::word() });
    let form = form(&reading);
    let evidence = form.fields.iter().filter_map(|(_, reading)| reading.evidence());
    let texts: Vec<&str> =
        evidence.chain(form.unplaced.iter().map(|run| &run.evidence)).map(|e| e.text.as_str()).collect();
    for rep in ["SAMPLE REP", "512-555-0198", "rep@example.com", "512-555-0199", "forms@example.com"] {
        assert!(texts.iter().all(|text| !text.contains(rep)), "{rep} was read");
    }
}

/// The PDFescape form with `typed` as the only text typed on its entity row.
fn pdfescape_entity(typed_on_row: &[(f32, &'static str)]) -> (Outcome, Option<String>) {
    let mut layout = pdfescape();
    layout.extras.retain(|extra| extra.dy != ENTITY_MARK_DY);
    layout.extras.extend(typed_on_row.iter().map(|(x, text)| typed("ArialMT", VALUE_SIZE, *x, ENTITY_MARK_DY, text)));
    let reading = read_form_page(&Form { layout, ..Form::word() });
    let entity = FieldId::Business(B::Entity);
    (outcome(form(&reading), entity), canonical(form(&reading), entity))
}

#[test]
fn the_pdfescape_entity_reads_the_printed_choice_beside_the_mark() {
    let read = |typed: &[(f32, &'static str)]| pdfescape_entity(typed).1;
    assert_eq!(read(&[(168.0, "X")]).as_deref(), Some("CORPORATION"), "before Corporation");
    assert_eq!(read(&[(244.0, "x")]).as_deref(), Some("CORPORATION"), "after Corporation");
    assert_eq!(read(&[(320.0, "X")]).as_deref(), Some("LIMITED LIABILITY COMPANY"));
    let sole = Some("SOLE PROPRIETORSHIP");
    assert_eq!(read(&[(362.0, "X"), (512.0, "SOLE PROPRIETORSHIP")]).as_deref(), sole, "Other, described");
    assert_eq!(read(&[(512.0, "SOLE PROPRIETORSHIP")]).as_deref(), sole, "described without a mark");
}

#[test]
fn an_unclear_pdfescape_entity_mark_is_refused() {
    let refused = |typed: &[(f32, &'static str)]| pdfescape_entity(typed).0;
    assert_eq!(refused(&[(268.0, "X")]), Outcome::Refused(Refusal::MarkUnclear), "midway");
    assert_eq!(refused(&[(244.0, "X"), (320.0, "X")]), Outcome::Refused(Refusal::MarkUnclear), "two marks");
    assert_eq!(refused(&[(320.0, "X"), (512.0, "SAMPLE")]), Outcome::Refused(Refusal::Ambiguous), "LLC, described");
    assert_eq!(refused(&[(362.0, "X")]), Outcome::Refused(Refusal::NotInList), "Other, not described");
    assert_eq!(refused(&[(512.0, "SAMPLE")]), Outcome::Refused(Refusal::NotInList));
    assert_eq!(refused(&[]), Outcome::Blank);
}

#[test]
fn reading_does_not_depend_on_content_order() {
    let reading = read_pages(vec![Form::word().draw(PageBuilder::new()).reversed().build()]);
    assert_reads_every_sample_value(&reading, "word");
}

#[test]
fn labels_at_unknown_offsets_need_manual_entry_and_report_their_offsets() {
    let form = Form { layout: Layout { dy: |dy| dy * 1.1, ..word() }, ..Form::word() };
    let reading = read_form_page(&form);
    assert!(matches!(reading.document, Document::ManualEntry(ManualEntryReason::UnknownLayout)));
    let tax_id = reading.offsets.iter().find(|offset| offset.field == FieldId::Business(B::TaxId)).unwrap();
    assert!((tax_id.dy - 141.9).abs() < 0.01, "{}", tax_id.dy);
}

#[test]
fn a_value_typed_into_its_labels_run_splits_after_the_label() {
    let mut rows = word_rows();
    rows[2].1.retain(|(text, _, _)| *text != "City" && *text != "Zip");
    let layout = Layout { rows, ..word() };
    let top = HEADING.1 + 54.0;
    let page = Form { layout, ..Form::word() }
        .draw(PageBuilder::new())
        .text("Calibri", LABEL_SIZE, 40.0, top, "City SAMPLE CITY")
        .text("Calibri", LABEL_SIZE, 330.0, top, "Zip:78701")
        .build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    assert_eq!(canonical(form, FieldId::Business(B::City)).as_deref(), Some("SAMPLE CITY"));
    assert_eq!(canonical(form, FieldId::Business(B::Zip)).as_deref(), Some("78701"));
}

/// The legal name runs from its label's end at x 150.5 to x 353, over the start of the label
/// "Doing Business As (DBA)" at x 330.
const LONG_LEGAL_NAME: &str = "CONTOSO FABRIKAM NORTHWIND HOLDINGS OF SAMPLE";

#[test]
fn a_label_that_a_value_runs_over_is_still_found() {
    let reading = read_form_page(&Form::word().set(FieldId::Business(B::LegalName), LONG_LEGAL_NAME));
    let form = form(&reading);
    assert_eq!(canonical(form, FieldId::Business(B::Dba)).as_deref(), Some("NORTHWIND"));
}

#[test]
fn a_value_belongs_to_the_field_where_it_starts() {
    let reading = read_form_page(&Form::word().set(FieldId::Business(B::LegalName), LONG_LEGAL_NAME));
    let form = form(&reading);
    assert_eq!(canonical(form, FieldId::Business(B::LegalName)).as_deref(), Some(LONG_LEGAL_NAME));
    assert_eq!(canonical(form, FieldId::Business(B::Dba)).as_deref(), Some("NORTHWIND"));
    assert!(form.unplaced.is_empty(), "unplaced: {}", form.unplaced.len());
}

#[test]
fn a_value_that_starts_over_its_label_is_unplaced_whole_and_never_split() {
    let mut rows = word_rows();
    rows[2].1.retain(|(text, _, _)| *text != "City");
    rows[2].1.push(("City", 40.0, None));
    let page = Form { layout: Layout { rows, ..word() }, ..Form::word() }
        .draw(PageBuilder::new())
        .text("ArialMT", VALUE_SIZE, 50.0, HEADING.1 + 54.0 + 1.6, "AUSTIN")
        .build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    assert_eq!(outcome(form, FieldId::Business(B::City)), Outcome::Blank);
    let runs: Vec<&str> = form.unplaced.iter().map(|run| run.evidence.text.as_str()).collect();
    assert_eq!(runs, ["AUSTIN"]);
}

#[test]
fn repeated_labels_belong_to_their_owner() {
    let reading = read_form_page(&Form::word());
    let form = form(&reading);
    let city = |slot| canonical(form, FieldId::Owner(slot, O::City));
    assert_eq!(canonical(form, FieldId::Business(B::City)).as_deref(), Some("AUSTIN"));
    assert_eq!(city(OwnerSlot::Principal).as_deref(), Some("ROUND ROCK"));
    assert_eq!(city(OwnerSlot::Secondary).as_deref(), Some("DALLAS"));
}

#[test]
fn a_missing_label_is_missing_its_neighbors_still_read_and_its_value_is_unplaced() {
    let reading = read_form_page(&Form { omit: vec!["Fax"], ..Form::word() });
    let form = form(&reading);
    assert_eq!(outcome(form, FieldId::Business(B::Fax)), Outcome::LabelMissing);
    assert_eq!(outcome(form, FieldId::Business(B::Entity)), Outcome::Read);
    assert_eq!(outcome(form, FieldId::Business(B::Phone)), Outcome::Read);
    let [run] = form.unplaced.as_slice() else { panic!("{} unplaced runs", form.unplaced.len()) };
    assert_eq!(run.evidence.text, "512.555.0101");
    assert_eq!(run.after, Some(FieldId::Business(B::Phone)));
}

#[test]
fn a_label_word_inside_a_value_in_the_label_font_puts_both_fields_in_doubt() {
    let mut rows = word_rows();
    rows[0].1.retain(|(text, _, _)| *text != "Business Legal Name");
    let page = Form { layout: Layout { rows, ..word() }, ..Form::word() }
        .draw(PageBuilder::new())
        .text("Calibri", LABEL_SIZE, 40.0, HEADING.1 + 18.0, "Business Legal Name Contoso City Catering")
        .build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    assert_eq!(outcome(form, FieldId::Business(B::City)), Outcome::Doubtful(Doubt::LabelFoundTwice));
    assert_eq!(outcome(form, FieldId::Business(B::LegalName)), Outcome::Doubtful(Doubt::StrayLabel));
    assert_eq!(outcome(form, FieldId::Business(B::Suite)), Outcome::Read);
    assert_eq!(outcome(form, FieldId::Business(B::State)), Outcome::Read);
}

#[test]
fn signature_lines_side_by_side_leave_their_dates_out_of_place() {
    let mut rows = word_rows();
    rows.truncate(rows.len() - 2);
    let date_one = Some(FieldId::Signature(S::ApplicantOneDate));
    let date_two = Some(FieldId::Signature(S::ApplicantTwoDate));
    rows.push((560.0, vec![("Signature of Applicant One", 40.0, None), ("Signature of Applicant Two", 330.0, None)]));
    rows.push((590.0, vec![("Date", 40.0, date_one), ("Date", 330.0, date_two)]));
    let reading = read_form_page(&Form { layout: Layout { rows, ..word() }, ..Form::word() });
    let form = form(&reading);
    for field in [S::ApplicantOneDate, S::ApplicantTwoDate] {
        assert_eq!(outcome(form, FieldId::Signature(field)), Outcome::LabelOutOfPlace);
    }
}

#[test]
fn a_wrapped_value_reads_its_next_line() {
    let page = Form::word()
        .draw(PageBuilder::new())
        .text("ArialMT", VALUE_SIZE, 277.0, HEADING.1 + 424.0 + 11.0, "GROUP")
        .build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    assert_eq!(canonical(form, FieldId::Property(P::PriorLender)).as_deref(), Some("SAMPLE FUNDING GROUP"));
}

#[test]
fn the_wrapped_line_stops_above_the_next_label_row() {
    let mut rows = word_rows();
    let loan_row = rows.iter_mut().find(|(_, labels)| labels.iter().any(|(text, ..)| *text == "Existing Loan Balance"));
    loan_row.unwrap().0 = 424.0 + 17.0;
    let reading = read_form_page(&Form { layout: Layout { rows, ..word() }, ..Form::word() });
    let form = form(&reading);
    for (field, text) in
        [(P::PriorLender, "SAMPLE FUNDING"), (P::LoanBalance, "10,000.00"), (P::RequestedAmount, "$50,000.00")]
    {
        let field = FieldId::Property(field);
        assert_eq!(canonical(form, field).as_deref(), Some(text), "{field}: {:?}", outcome(form, field));
    }
}

#[test]
fn text_in_the_next_rows_band_belongs_to_that_row_and_not_to_the_wrapped_line() {
    let page = Form::word()
        .draw(PageBuilder::new())
        .text("ArialMT", VALUE_SIZE, 277.0, HEADING.1 + 424.0 + 15.0, "GROUP")
        .build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    assert_eq!(canonical(form, FieldId::Property(P::PriorLender)).as_deref(), Some("SAMPLE FUNDING"));
    assert_eq!(outcome(form, FieldId::Property(P::LoanBalance)), Outcome::Refused(Refusal::Format));
}

#[test]
fn a_run_that_starts_in_two_regions_puts_both_fields_in_doubt() {
    let page =
        Form::word().draw(PageBuilder::new()).text("ArialMT", VALUE_SIZE, 200.0, HEADING.1 + 26.0, "FAB").build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    assert_eq!(outcome(form, FieldId::Business(B::LegalName)), Outcome::Doubtful(Doubt::SharedGlyph));
    assert_eq!(outcome(form, FieldId::Business(B::Address)), Outcome::Doubtful(Doubt::SharedGlyph));
}

#[test]
fn text_outside_every_region_is_unplaced_whatever_its_font() {
    let top = HEADING.1 + 54.0;
    let page = Form::word()
        .draw(PageBuilder::new())
        .text("Calibri", LABEL_SIZE, 4.0, top, "SAMPLE")
        .text("ArialMT", VALUE_SIZE, 4.0, HEADING.1 + 147.0, "FAB")
        .build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    let runs: Vec<(&str, Option<FieldId>)> =
        form.unplaced.iter().map(|run| (run.evidence.text.as_str(), run.after)).collect();
    assert_eq!(runs, [("SAMPLE", Some(FieldId::Business(B::Suite))), ("FAB", Some(FieldId::Business(B::Website)))]);
}

#[test]
fn blank_and_not_applicable_answers() {
    let reading =
        read_form_page(&Form::word().clear(FieldId::Business(B::Dba)).set(FieldId::Business(B::Website), "N/A"));
    assert_eq!(outcome(form(&reading), FieldId::Business(B::Dba)), Outcome::Blank);
    assert_eq!(outcome(form(&reading), FieldId::Business(B::Website)), Outcome::NotApplicable);
    let rent = read_form_page(&Form::word().set(FieldId::Business(B::RentCurrent), "N/A"));
    assert_eq!(outcome(form(&rent), FieldId::Business(B::RentCurrent)), Outcome::NotApplicable);
}

#[test]
fn names_codes_and_identifiers_read_in_the_shapes_merchants_type() {
    let p = OwnerSlot::Principal;
    let typed = [
        (FieldId::Business(B::State), "Texas", "TX"),
        (FieldId::Owner(p, O::State), "TX.", "TX"),
        (FieldId::Business(B::Zip), "78701.", "78701"),
        (FieldId::Business(B::Phone), "512/555/0100", "512-555-0100"),
        (FieldId::Owner(p, O::Phone), "512 555-0103", "512-555-0103"),
        (FieldId::Business(B::TaxId), "12 3456789", "12-3456789"),
        (FieldId::Owner(p, O::Ssn), "900 12 3456", "900-12-3456"),
        (FieldId::Business(B::Entity), "GENERAL PARTNERSHIP (GP)", "PARTNERSHIP"),
    ];
    let form_with = typed.iter().fold(Form::word(), |form, (field, text, _)| form.set(*field, text));
    let reading = read_form_page(&form_with);
    let form = form(&reading);
    for (field, _, canonical_text) in typed {
        assert_eq!(canonical(form, field).as_deref(), Some(canonical_text), "{field}: {:?}", outcome(form, field));
    }
}

#[test]
fn a_canadian_business_refuses_dates_whose_month_and_day_could_swap() {
    let reading = read_form_page(
        &Form::word()
            .set(FieldId::Business(B::State), "ON")
            .set(FieldId::Business(B::Zip), "K1A 0B1")
            .set(FieldId::Owner(OwnerSlot::Principal, O::BirthDate), "05/06/1980"),
    );
    let form = form(&reading);
    assert_eq!(outcome(form, FieldId::Owner(OwnerSlot::Principal, O::BirthDate)), Outcome::Refused(Refusal::Ambiguous));
    assert_eq!(outcome(form, FieldId::Business(B::StartDate)), Outcome::Read, "04/15 cannot swap");
}

#[test]
fn dates_are_bounded_by_the_signing_day() {
    let late = read_form_page(&Form::word().set(FieldId::Business(B::StartDate), "11/2026"));
    assert_eq!(outcome(form(&late), FieldId::Business(B::StartDate)), Outcome::Refused(Refusal::OutOfRange));

    let later = page(&Form::word().set(FieldId::Business(B::StartDate), "11/2026"));
    let reading = read(&PdfFacts { created_on: Some(date!(2026 - 12 - 01)), pages: vec![later] });
    assert_eq!(reading.signed_on, Some(SignedOn::Created(date!(2026 - 12 - 01))));
    assert!(reading.certificate.is_none());
    assert_eq!(canonical(form(&reading), FieldId::Business(B::StartDate)).as_deref(), Some("11/2026"));

    let unsigned = read(&PdfFacts { created_on: None, pages: vec![page(&Form::word())] });
    assert_eq!(outcome(form(&unsigned), FieldId::Business(B::StartDate)), Outcome::Refused(Refusal::NoSigningDate));
}

#[test]
fn undecodable_text_is_refused() {
    let reading = read_form_page(&Form::word().set(FieldId::Business(B::LegalName), "CONTOSO \u{FFFD}LC"));
    assert_eq!(outcome(form(&reading), FieldId::Business(B::LegalName)), Outcome::Refused(Refusal::Undecodable));
}

fn document(pages: Vec<TextPage>) -> Document {
    read(&PdfFacts { created_on: None, pages }).document
}

fn filler(page: PageBuilder, lines: usize) -> PageBuilder {
    (0..lines).fold(page, |page, i| {
        page.text("ArialMT", 9.0, 40.0, 100.0 + 12.0 * i as f32, "SAMPLE TERMS OF THE AGREEMENT ARE HERE")
    })
}

#[test]
fn documents_that_are_not_the_form_are_refused_or_sent_to_manual_entry() {
    let contract = filler(
        PageBuilder::new().text("TimesNewRomanPS-BoldMT", 12.0, 40.0, 40.0, "RECEIVABLES PURCHASE AGREEMENT"),
        10,
    );
    assert!(matches!(document(vec![contract.build()]), Document::Refused(RefusalReason::Contract)));

    let paperwork = filler(PageBuilder::new(), 10).build();
    assert!(matches!(document(vec![paperwork]), Document::Refused(RefusalReason::OtherPaperwork)));

    let scan = filler(PageBuilder::new(), 10).image_cover(0.9).build();
    assert!(matches!(document(vec![scan]), Document::ManualEntry(ManualEntryReason::SuspectedScan)));

    let little_text = filler(PageBuilder::new(), 2).build();
    assert!(matches!(document(vec![little_text]), Document::ManualEntry(ManualEntryReason::SuspectedScan)));

    let scanned_form = Form::word().draw(PageBuilder::new()).image_cover(0.85).build();
    assert!(matches!(document(vec![scanned_form]), Document::ManualEntry(ManualEntryReason::SuspectedScan)));

    let both = Form::word()
        .draw(PageBuilder::new())
        .text("TimesNewRomanPS-BoldMT", 12.0, 40.0, 20.0, "RECEIVABLES PURCHASE AGREEMENT")
        .build();
    assert!(matches!(document(vec![both]), Document::ManualEntry(ManualEntryReason::AmbiguousDocument)));

    let no_secondary = page(&Form { omit: vec!["Secondary Owner Name"], ..Form::word() });
    assert!(matches!(document(vec![no_secondary]), Document::ManualEntry(ManualEntryReason::UnknownLayout)));

    assert!(matches!(document(Vec::new()), Document::Refused(RefusalReason::OtherPaperwork)));
}

#[test]
fn a_section_heading_out_of_order_needs_manual_entry() {
    let page = page(&Form { layout: Layout { headings: [201.0, 620.0], ..word() }, ..Form::word() });
    assert!(matches!(document(vec![page]), Document::ManualEntry(ManualEntryReason::UnknownLayout)));
}

#[test]
fn a_value_in_a_label_font_that_is_not_a_label_reads_as_a_value() {
    let mut rows = word_rows();
    rows[5].1.retain(|(text, _, _)| *text != "Federal Tax ID");
    let page = Form { layout: Layout { rows, ..word() }, ..Form::word().clear(FieldId::Business(B::TaxId)) }
        .draw(PageBuilder::new())
        .text("Calibri", LABEL_SIZE, 40.0, HEADING.1 + 129.0, "Federal Tax ID: 12-3456789")
        .build();
    let reading = read_pages(vec![page]);
    assert_eq!(canonical(form(&reading), FieldId::Business(B::TaxId)).as_deref(), Some("12-3456789"));
}
