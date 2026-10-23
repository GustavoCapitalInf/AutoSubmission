use time::macros::date;

use super::*;
use crate::certificate::tests::certificate_page;
use crate::fields::{BusinessField as B, OwnerField as O, OwnerSlot, PropertyField as P, SignatureField as S};
use crate::page::build::{PageBuilder, width};

const LABEL_SIZE: f32 = 11.0;
const VALUE_SIZE: f32 = 9.0;
const HEADING: (f32, f32) = (40.0, 60.0);

fn business(field: B) -> Option<FieldId> {
    Some(FieldId::Business(field))
}
fn principal(field: O) -> Option<FieldId> {
    Some(FieldId::Owner(OwnerSlot::Principal, field))
}
fn secondary(field: O) -> Option<FieldId> {
    Some(FieldId::Owner(OwnerSlot::Secondary, field))
}
fn property(field: P) -> Option<FieldId> {
    Some(FieldId::Property(field))
}

type Row = (f32, Vec<(&'static str, f32, Option<FieldId>)>);

/// The Word placement, as offsets from the BUSINESS INFORMATION heading's top-left corner.
fn word_rows() -> Vec<Row> {
    vec![
        (
            18.0,
            vec![
                ("Business Legal Name", 40.0, business(B::LegalName)),
                ("Doing Business As (DBA)", 330.0, business(B::Dba)),
            ],
        ),
        (36.0, vec![("Address", 40.0, business(B::Address)), ("Suite/Floor", 330.0, business(B::Suite))]),
        (
            54.0,
            vec![
                ("City", 40.0, business(B::City)),
                ("State", 250.0, business(B::State)),
                ("Zip", 330.0, business(B::Zip)),
                ("Phone", 440.0, business(B::Phone)),
            ],
        ),
        (
            72.0,
            vec![
                ("Fax", 40.0, business(B::Fax)),
                ("Entity", 200.0, business(B::Entity)),
                ("Email", 380.0, business(B::Email)),
            ],
        ),
        (
            90.0,
            vec![
                ("Business Start Date (MM/YYYY)", 40.0, business(B::StartDate)),
                ("Date Current Ownership Started", 300.0, business(B::OwnershipStart)),
            ],
        ),
        (129.0, vec![("Federal Tax ID", 40.0, business(B::TaxId)), ("Website", 300.0, business(B::Website))]),
        (
            147.0,
            vec![
                ("Landlord Name", 40.0, business(B::LandlordName)),
                ("Landlord Phone", 300.0, business(B::LandlordPhone)),
            ],
        ),
        (
            165.0,
            vec![
                ("Time Left on Lease", 40.0, business(B::LeaseTimeLeft)),
                ("Monthly Rent/Mortgage Payment", 250.0, business(B::MonthlyRent)),
            ],
        ),
        (183.0, vec![("Are You Current with Rent/Mortgage?", 40.0, business(B::RentCurrent))]),
        (
            220.0,
            vec![
                ("Principle Owner Name", 40.0, principal(O::Name)),
                ("Ownership %", 330.0, principal(O::OwnershipPercent)),
            ],
        ),
        (
            238.0,
            vec![
                ("Email", 40.0, principal(O::Email)),
                ("Phone", 250.0, principal(O::Phone)),
                ("Address", 380.0, principal(O::Address)),
            ],
        ),
        (
            256.0,
            vec![
                ("City", 40.0, principal(O::City)),
                ("State", 170.0, principal(O::State)),
                ("Zip", 250.0, principal(O::Zip)),
                ("SSN", 330.0, principal(O::Ssn)),
                ("Date of Birth", 440.0, principal(O::BirthDate)),
            ],
        ),
        (
            280.0,
            vec![
                ("Secondary Owner Name", 40.0, secondary(O::Name)),
                ("Ownership %", 330.0, secondary(O::OwnershipPercent)),
            ],
        ),
        (
            298.0,
            vec![
                ("Email", 40.0, secondary(O::Email)),
                ("Phone", 250.0, secondary(O::Phone)),
                ("Address", 380.0, secondary(O::Address)),
            ],
        ),
        (
            330.0,
            vec![
                ("City", 40.0, secondary(O::City)),
                ("State", 170.0, secondary(O::State)),
                ("Zip", 250.0, secondary(O::Zip)),
                ("SSN", 330.0, secondary(O::Ssn)),
                ("Date of Birth", 440.0, secondary(O::BirthDate)),
            ],
        ),
        (
            370.0,
            vec![
                ("Business Description", 40.0, property(P::Description)),
                ("Annual Business Revenue", 330.0, property(P::AnnualRevenue)),
            ],
        ),
        (
            388.0,
            vec![
                ("Purpose of Funds Requested", 40.0, property(P::FundsPurpose)),
                ("Estimated Fico Score", 330.0, property(P::EstimatedFico)),
            ],
        ),
        (
            406.0,
            vec![
                ("Average Monthly Credit Card Volume", 40.0, property(P::CardVolume)),
                ("Amount of Receivable Outstanding", 310.0, property(P::ReceivablesOutstanding)),
            ],
        ),
        (424.0, vec![("Prior/Current Loan Company (if applicable)", 40.0, property(P::PriorLender))]),
        (
            448.0,
            vec![
                ("Existing Loan Balance", 40.0, property(P::LoanBalance)),
                ("Requested Advance Amount", 310.0, property(P::RequestedAmount)),
            ],
        ),
        (
            466.0,
            vec![
                ("Any open judgements?", 40.0, property(P::OpenJudgements)),
                ("Any bankruptcy?", 200.0, property(P::Bankruptcy)),
                ("Any tax liens?", 330.0, property(P::TaxLiens)),
            ],
        ),
        (484.0, vec![("Is business seasonal?", 40.0, property(P::Seasonal))]),
        (
            560.0,
            vec![
                ("Signature of Applicant One", 40.0, None),
                ("Date", 330.0, Some(FieldId::Signature(S::ApplicantOneDate))),
            ],
        ),
        (
            590.0,
            vec![
                ("Signature of Applicant Two", 40.0, None),
                ("Date", 330.0, Some(FieldId::Signature(S::ApplicantTwoDate))),
            ],
        ),
    ]
}

struct Layout {
    rows: Vec<Row>,
    /// The OWNER INFORMATION and BUSINESS PROPERTY INFORMATION headings' Word offsets.
    headings: [f32; 2],
    label_font: &'static str,
    dx: f32,
    /// Maps a Word offset to this layout's.
    dy: fn(f32) -> f32,
}

fn word() -> Layout {
    Layout { rows: word_rows(), headings: [201.0, 352.0], label_font: "Calibri", dx: 0.0, dy: |dy| dy }
}

/// The PDFescape placement: the sentinels at their measured offsets, the rows between them
/// spaced in proportion, and every label 2 pt to the right.
fn pdfescape() -> Layout {
    fn dy(dy: f32) -> f32 {
        let knots = [(0.0, 0.0), (18.0, 15.0), (129.0, 121.0), (256.0, 231.0), (330.0, 296.0)];
        for pair in knots.windows(2) {
            let ((a, fa), (b, fb)) = (pair[0], pair[1]);
            if dy <= b {
                return fa + (dy - a) * (fb - fa) / (b - a);
            }
        }
        dy - 34.0
    }
    Layout { label_font: "AdobeDevanagari-Regular", dx: 2.0, dy, ..word() }
}

fn sample_values() -> Vec<(FieldId, &'static str)> {
    let o = |slot, field| FieldId::Owner(slot, field);
    let (p, s) = (OwnerSlot::Principal, OwnerSlot::Secondary);
    vec![
        (FieldId::Business(B::LegalName), "CONTOSO LLC"),
        (FieldId::Business(B::Dba), "NORTHWIND"),
        (FieldId::Business(B::Address), "100 SAMPLE ST"),
        (FieldId::Business(B::Suite), "SUITE 5"),
        (FieldId::Business(B::City), "AUSTIN"),
        (FieldId::Business(B::State), "TX"),
        (FieldId::Business(B::Zip), "78701"),
        (FieldId::Business(B::Phone), "(512) 555-0100"),
        (FieldId::Business(B::Fax), "512.555.0101"),
        (FieldId::Business(B::Entity), "LIMITED LIABILITY COMPANY"),
        (FieldId::Business(B::Email), "office@example.com"),
        (FieldId::Business(B::StartDate), "04/15/2019"),
        (FieldId::Business(B::OwnershipStart), "05/2020"),
        (FieldId::Business(B::TaxId), "12-3456789"),
        (FieldId::Business(B::Website), "contoso.example.com"),
        (FieldId::Business(B::LandlordName), "FABRIKAM PROPERTIES"),
        (FieldId::Business(B::LandlordPhone), "5125550102"),
        (FieldId::Business(B::LeaseTimeLeft), "3 YEARS"),
        (FieldId::Business(B::MonthlyRent), "2,500"),
        (FieldId::Business(B::RentCurrent), "YES"),
        (o(p, O::Name), "SAMPLE OWNER"),
        (o(p, O::OwnershipPercent), "50.00"),
        (o(p, O::Email), "owner@example.com"),
        (o(p, O::Phone), "512-555-0103"),
        (o(p, O::Address), "200 SAMPLE AVE"),
        (o(p, O::City), "ROUND ROCK"),
        (o(p, O::State), "TX"),
        (o(p, O::Zip), "78664"),
        (o(p, O::Ssn), "900-12-3456"),
        (o(p, O::BirthDate), "04/15/1980"),
        (o(s, O::Name), "NORTHWIND PARTNER"),
        (o(s, O::OwnershipPercent), "50"),
        (o(s, O::Email), "partner@example.com"),
        (o(s, O::Phone), "512-555-0104"),
        (o(s, O::Address), "300 SAMPLE BLVD"),
        (o(s, O::City), "DALLAS"),
        (o(s, O::State), "TX"),
        (o(s, O::Zip), "75201"),
        (o(s, O::Ssn), "900654321"),
        (o(s, O::BirthDate), "06/01/1975"),
        (FieldId::Property(P::Description), "CATERING / EVENTS"),
        (FieldId::Property(P::AnnualRevenue), "1,200,000"),
        (FieldId::Property(P::FundsPurpose), "EQUIPMENT"),
        (FieldId::Property(P::EstimatedFico), "700"),
        (FieldId::Property(P::CardVolume), "15,000"),
        (FieldId::Property(P::ReceivablesOutstanding), "0"),
        (FieldId::Property(P::PriorLender), "SAMPLE FUNDING"),
        (FieldId::Property(P::LoanBalance), "10,000"),
        (FieldId::Property(P::RequestedAmount), "$50,000"),
        (FieldId::Property(P::OpenJudgements), "NO"),
        (FieldId::Property(P::Bankruptcy), "N/A"),
        (FieldId::Property(P::TaxLiens), "NONE"),
        (FieldId::Signature(S::ApplicantOneDate), "10/20/2026"),
        (FieldId::Signature(S::ApplicantTwoDate), "10/20/2026"),
    ]
}

/// What each sample value reads as.
fn expected() -> Vec<(FieldId, &'static str)> {
    let mut values = sample_values();
    let canonical = [
        (FieldId::Business(B::Phone), "512-555-0100"),
        (FieldId::Business(B::Fax), "512-555-0101"),
        (FieldId::Business(B::LandlordPhone), "512-555-0102"),
        (FieldId::Business(B::MonthlyRent), "2,500.00"),
        (FieldId::Owner(OwnerSlot::Secondary, O::OwnershipPercent), "50.00"),
        (FieldId::Property(P::AnnualRevenue), "1,200,000.00"),
        (FieldId::Property(P::CardVolume), "15,000.00"),
        (FieldId::Property(P::ReceivablesOutstanding), "0.00"),
        (FieldId::Property(P::LoanBalance), "10,000.00"),
        (FieldId::Property(P::RequestedAmount), "$50,000.00"),
        (FieldId::Property(P::Bankruptcy), "NO"),
        (FieldId::Property(P::TaxLiens), "NO"),
    ];
    for (field, text) in canonical {
        values.iter_mut().find(|(f, _)| *f == field).unwrap().1 = text;
    }
    values.push((FieldId::Property(P::Seasonal), "NO"));
    values
}

struct Form {
    layout: Layout,
    values: Vec<(FieldId, &'static str)>,
    /// Labels left off the page.
    omit: Vec<&'static str>,
}

impl Form {
    fn word() -> Form {
        Form { layout: word(), values: sample_values(), omit: Vec::new() }
    }

    fn set(mut self, field: FieldId, text: &'static str) -> Form {
        self.values.retain(|(f, _)| *f != field);
        self.values.push((field, text));
        self
    }

    fn clear(mut self, field: FieldId) -> Form {
        self.values.retain(|(f, _)| *f != field);
        self
    }

    fn label_top(&self, dy: f32) -> f32 {
        HEADING.1 + (self.layout.dy)(dy)
    }

    fn builder(&self) -> PageBuilder {
        let heading_font = "TimesNewRomanPS-BoldMT";
        let mut page = PageBuilder::new()
            .text(heading_font, 10.0, HEADING.0, HEADING.1, "BUSINESS INFORMATION")
            .text(heading_font, 10.0, HEADING.0, self.label_top(self.layout.headings[0]), "OWNER INFORMATION")
            .text(
                heading_font,
                10.0,
                HEADING.0,
                self.label_top(self.layout.headings[1]),
                "BUSINESS PROPERTY INFORMATION",
            );
        for (dy, labels) in &self.layout.rows {
            let top = self.label_top(*dy);
            for (text, x, field) in labels {
                let x = x + self.layout.dx;
                if !self.omit.contains(text) {
                    page = page.text(self.layout.label_font, LABEL_SIZE, x, top, text);
                }
                let value = field.and_then(|field| self.values.iter().find(|(f, _)| *f == field));
                if let Some((_, value)) = value {
                    page = page.text("ArialMT", VALUE_SIZE, x + width(LABEL_SIZE, text) + 6.0, top + 1.6, value);
                }
            }
        }
        let seasonal = self.label_top(484.0);
        page.text(self.layout.label_font, LABEL_SIZE, 170.0, seasonal, "YES")
            .text(self.layout.label_font, LABEL_SIZE, 220.0, seasonal, "NO")
            .text("ArialMT", VALUE_SIZE, 236.0, seasonal + 1.6, "X")
            .text(
                self.layout.label_font,
                10.0,
                40.0,
                self.label_top(510.0),
                "I certify that the information above is true and correct,",
            )
            .text(self.layout.label_font, 10.0, 40.0, self.label_top(524.0), "and I authorize SAMPLE to verify it.")
            .text("DancingScript", 14.0, 200.0, self.label_top(560.0) - 2.0, "Sample Owner")
    }

    fn page(&self) -> TextPage {
        self.builder().build()
    }

    fn read(&self) -> Reading {
        read_pages(vec![self.page()])
    }
}

fn read_pages(mut pages: Vec<TextPage>) -> Reading {
    pages.push(certificate_page(&[("SAMPLE OWNER", "owner@example.com")]));
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
    let reading = Form::word().read();
    assert_reads_every_sample_value(&reading, "word");
    assert_eq!(reading.signed_on, Some(SignedOn::Certificate(date!(2026 - 10 - 20))));
    let dy: Vec<f32> = reading.offsets.iter().map(|offset| offset.dy).collect();
    assert_eq!(dy, [18.0, 129.0, 256.0, 330.0]);
}

#[test]
fn the_pdfescape_layout_reads_the_same_values() {
    let form = Form { layout: pdfescape(), ..Form::word() };
    assert_reads_every_sample_value(&form.read(), "pdfescape");
}

#[test]
fn reading_does_not_depend_on_content_order() {
    let reading = read_pages(vec![Form::word().builder().reversed().build()]);
    assert_reads_every_sample_value(&reading, "word");
}

#[test]
fn labels_at_unknown_offsets_need_manual_entry_and_report_their_offsets() {
    let form = Form { layout: Layout { dy: |dy| dy * 1.1, ..word() }, ..Form::word() };
    let reading = form.read();
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
        .builder()
        .text("Calibri", LABEL_SIZE, 40.0, top, "City SAMPLE CITY")
        .text("Calibri", LABEL_SIZE, 330.0, top, "Zip:78701")
        .build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    assert_eq!(canonical(form, FieldId::Business(B::City)).as_deref(), Some("SAMPLE CITY"));
    assert_eq!(canonical(form, FieldId::Business(B::Zip)).as_deref(), Some("78701"));
}

#[test]
fn repeated_labels_belong_to_their_owner() {
    let reading = Form::word().read();
    let form = form(&reading);
    let city = |slot| canonical(form, FieldId::Owner(slot, O::City));
    assert_eq!(canonical(form, FieldId::Business(B::City)).as_deref(), Some("AUSTIN"));
    assert_eq!(city(OwnerSlot::Principal).as_deref(), Some("ROUND ROCK"));
    assert_eq!(city(OwnerSlot::Secondary).as_deref(), Some("DALLAS"));
}

#[test]
fn a_missing_label_is_missing_its_neighbors_still_read_and_its_value_is_unplaced() {
    let reading = Form { omit: vec!["Fax"], ..Form::word() }.read();
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
        .builder()
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
    let reading = Form { layout: Layout { rows, ..word() }, ..Form::word() }.read();
    let form = form(&reading);
    for field in [S::ApplicantOneDate, S::ApplicantTwoDate] {
        assert_eq!(outcome(form, FieldId::Signature(field)), Outcome::LabelOutOfPlace);
    }
}

#[test]
fn a_wrapped_value_reads_its_next_line() {
    let page = Form::word().builder().text("ArialMT", VALUE_SIZE, 277.0, HEADING.1 + 424.0 + 11.0, "GROUP").build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    assert_eq!(canonical(form, FieldId::Property(P::PriorLender)).as_deref(), Some("SAMPLE FUNDING GROUP"));
}

#[test]
fn a_glyph_in_two_regions_puts_both_fields_in_doubt() {
    let page = Form::word().builder().text("ArialMT", VALUE_SIZE, 277.0, HEADING.1 + 424.0 + 15.0, "GROUP").build();
    let reading = read_pages(vec![page]);
    let form = form(&reading);
    assert_eq!(outcome(form, FieldId::Property(P::PriorLender)), Outcome::Doubtful(Doubt::SharedGlyph));
    assert_eq!(outcome(form, FieldId::Property(P::LoanBalance)), Outcome::Doubtful(Doubt::SharedGlyph));
}

#[test]
fn text_outside_every_region_is_unplaced_whatever_its_font() {
    let top = HEADING.1 + 54.0;
    let page = Form::word()
        .builder()
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
    let reading = Form::word().clear(FieldId::Business(B::Dba)).set(FieldId::Business(B::Website), "N/A").read();
    assert_eq!(outcome(form(&reading), FieldId::Business(B::Dba)), Outcome::Blank);
    assert_eq!(outcome(form(&reading), FieldId::Business(B::Website)), Outcome::NotApplicable);
    let rent = Form::word().set(FieldId::Business(B::RentCurrent), "N/A").read();
    assert_eq!(outcome(form(&rent), FieldId::Business(B::RentCurrent)), Outcome::NotApplicable);
}

#[test]
fn a_canadian_business_refuses_dates_whose_month_and_day_could_swap() {
    let reading = Form::word()
        .set(FieldId::Business(B::State), "ON")
        .set(FieldId::Business(B::Zip), "K1A 0B1")
        .set(FieldId::Owner(OwnerSlot::Principal, O::BirthDate), "05/06/1980")
        .read();
    let form = form(&reading);
    assert_eq!(outcome(form, FieldId::Owner(OwnerSlot::Principal, O::BirthDate)), Outcome::Refused(Refusal::Ambiguous));
    assert_eq!(outcome(form, FieldId::Business(B::StartDate)), Outcome::Read, "04/15 cannot swap");
}

#[test]
fn dates_are_bounded_by_the_signing_day() {
    let late = Form::word().set(FieldId::Business(B::StartDate), "11/2026").read();
    assert_eq!(outcome(form(&late), FieldId::Business(B::StartDate)), Outcome::Refused(Refusal::OutOfRange));

    let page = Form::word().set(FieldId::Business(B::StartDate), "11/2026").page();
    let reading = read(&PdfFacts { created_on: Some(date!(2026 - 12 - 01)), pages: vec![page] });
    assert_eq!(reading.signed_on, Some(SignedOn::Created(date!(2026 - 12 - 01))));
    assert!(reading.certificate.is_none());
    assert_eq!(canonical(form(&reading), FieldId::Business(B::StartDate)).as_deref(), Some("11/2026"));

    let unsigned = read(&PdfFacts { created_on: None, pages: vec![Form::word().page()] });
    assert_eq!(outcome(form(&unsigned), FieldId::Business(B::StartDate)), Outcome::Refused(Refusal::NoSigningDate));
}

#[test]
fn undecodable_text_is_refused() {
    let reading = Form::word().set(FieldId::Business(B::LegalName), "CONTOSO \u{FFFD}LC").read();
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

    let scanned_form = Form::word().builder().image_cover(0.85).build();
    assert!(matches!(document(vec![scanned_form]), Document::ManualEntry(ManualEntryReason::SuspectedScan)));

    let both = Form::word()
        .builder()
        .text("TimesNewRomanPS-BoldMT", 12.0, 40.0, 20.0, "RECEIVABLES PURCHASE AGREEMENT")
        .build();
    assert!(matches!(document(vec![both]), Document::ManualEntry(ManualEntryReason::AmbiguousDocument)));

    let no_secondary = Form { omit: vec!["Secondary Owner Name"], ..Form::word() }.page();
    assert!(matches!(document(vec![no_secondary]), Document::ManualEntry(ManualEntryReason::UnknownLayout)));

    assert!(matches!(document(Vec::new()), Document::Refused(RefusalReason::OtherPaperwork)));
}

#[test]
fn a_section_heading_out_of_order_needs_manual_entry() {
    let page = Form { layout: Layout { headings: [201.0, 620.0], ..word() }, ..Form::word() }.page();
    assert!(matches!(document(vec![page]), Document::ManualEntry(ManualEntryReason::UnknownLayout)));
}

#[test]
fn a_value_in_a_label_font_that_is_not_a_label_reads_as_a_value() {
    let mut rows = word_rows();
    rows[5].1.retain(|(text, _, _)| *text != "Federal Tax ID");
    let page = Form { layout: Layout { rows, ..word() }, ..Form::word().clear(FieldId::Business(B::TaxId)) }
        .builder()
        .text("Calibri", LABEL_SIZE, 40.0, HEADING.1 + 129.0, "Federal Tax ID: 12-3456789")
        .build();
    let reading = read_pages(vec![page]);
    assert_eq!(canonical(form(&reading), FieldId::Business(B::TaxId)).as_deref(), Some("12-3456789"));
}
