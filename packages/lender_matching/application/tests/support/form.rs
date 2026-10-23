use lender_matching_application::fields::{
    BusinessField as B, FieldId, OwnerField as O, OwnerSlot, PropertyField as P, SignatureField as S,
};

/// Where fabricated text goes: a built page model or a written PDF.
pub trait Canvas: Sized {
    /// `top` is the top of the text's box, which is one em tall; each character is half an em wide.
    fn text(self, font: &str, size: f32, x: f32, top: f32, text: &str) -> Self;
}

pub fn width(size: f32, text: &str) -> f32 {
    size / 2.0 * text.chars().count() as f32
}

pub const LABEL_SIZE: f32 = 11.0;
pub const VALUE_SIZE: f32 = 9.0;
pub const HEADING: (f32, f32) = (40.0, 60.0);

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

pub type Row = (f32, Vec<(&'static str, f32, Option<FieldId>)>);

/// The Word placement, as offsets from the BUSINESS INFORMATION heading's top-left corner.
pub fn word_rows() -> Vec<Row> {
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

/// Text a layout prints besides its labels and the values typed after them.
pub struct Extra {
    /// The layout's label font when none is named.
    pub font: Option<&'static str>,
    pub size: f32,
    pub x: f32,
    /// The top, as an offset like a row's.
    pub dy: f32,
    pub text: &'static str,
}

/// Form text in the layout's label font.
pub fn printed(size: f32, x: f32, dy: f32, text: &'static str) -> Extra {
    Extra { font: None, size, x, dy, text }
}

/// Text typed in `font`.
pub fn typed(font: &'static str, size: f32, x: f32, dy: f32, text: &'static str) -> Extra {
    Extra { font: Some(font), size, x, dy, text }
}

pub struct Layout {
    pub rows: Vec<Row>,
    /// The OWNER INFORMATION and BUSINESS PROPERTY INFORMATION headings' offsets.
    pub headings: [f32; 2],
    pub label_font: &'static str,
    pub dx: f32,
    /// Maps an offset to where the page prints it.
    pub dy: fn(f32) -> f32,
    pub extras: Vec<Extra>,
}

/// The blank line printed after each signature line's "Date", which the date stamp overprints.
pub const SIGNATURE_DATE_LINE: &str = "_______________";

pub fn word() -> Layout {
    let seasonal = 484.0;
    Layout {
        rows: word_rows(),
        headings: [201.0, 352.0],
        label_font: "Calibri",
        dx: 0.0,
        dy: |dy| dy,
        extras: vec![
            printed(LABEL_SIZE, 170.0, seasonal, "YES"),
            printed(LABEL_SIZE, 220.0, seasonal, "NO"),
            typed("ArialMT", VALUE_SIZE, 236.0, seasonal + 1.6, "X"),
            printed(10.0, 40.0, 510.0, "I certify that the information above is true and correct,"),
            printed(10.0, 40.0, 524.0, "and I authorize SAMPLE to verify it."),
            typed("DancingScript", 14.0, 200.0, 558.0, "Sample Owner"),
            printed(LABEL_SIZE, 353.0, 560.0, SIGNATURE_DATE_LINE),
            printed(LABEL_SIZE, 353.0, 590.0, SIGNATURE_DATE_LINE),
        ],
    }
}

/// The PDFescape entity row: its printed choices start at x 180 (Corporation), 300 (LLC) and 370
/// (Other), and the mark sits on this top.
pub const ENTITY_MARK_DY: f32 = 86.0 + 1.6;

/// The PDFescape version at its measured offsets: its own label set, a sales rep header above
/// BUSINESS INFORMATION and a Fax and Email footer under the signature lines.
pub fn pdfescape() -> Layout {
    let x = |dx: f32| HEADING.0 + dx;
    let rows = vec![
        (
            15.0,
            vec![
                ("Business Legal Name", x(2.0), business(B::LegalName)),
                ("Doing Business As (DBA)", x(260.0), business(B::Dba)),
            ],
        ),
        (33.0, vec![("Address", x(2.0), business(B::Address)), ("Suite/Floor", x(260.0), business(B::Suite))]),
        (
            50.0,
            vec![
                ("City", x(2.0), business(B::City)),
                ("State", x(176.0), business(B::State)),
                ("Zip", x(344.0), business(B::Zip)),
            ],
        ),
        (
            65.0,
            vec![
                ("Phone", x(2.0), business(B::Phone)),
                ("Fax", x(176.0), business(B::Fax)),
                ("Email", x(344.0), business(B::Email)),
            ],
        ),
        (86.0, vec![("Type of Entity", x(2.0), None)]),
        (
            106.0,
            vec![
                ("Business Start Date (MM/YYYY)", x(2.0), business(B::StartDate)),
                ("Date Current Ownership Started", x(260.0), business(B::OwnershipStart)),
            ],
        ),
        (121.0, vec![("Federal Tax ID", x(2.0), business(B::TaxId)), ("Website", x(260.0), business(B::Website))]),
        (
            136.0,
            vec![
                ("Landlord Name", x(2.0), business(B::LandlordName)),
                ("Landlord Phone", x(176.0), business(B::LandlordPhone)),
                ("Time Left on Lease", x(344.0), business(B::LeaseTimeLeft)),
            ],
        ),
        (
            151.0,
            vec![
                ("Monthly Rent/Mortgage Payment", x(2.0), business(B::MonthlyRent)),
                ("Are You Current with Rent/Mortgage?", x(260.0), business(B::RentCurrent)),
            ],
        ),
        (
            183.0,
            vec![("Ownership %", x(207.0), principal(O::OwnershipPercent)), ("Email", x(341.0), principal(O::Email))],
        ),
        (184.0, vec![("Principle Owner Name", x(2.0), principal(O::Name))]),
        (197.0, vec![("Phone", x(2.0), principal(O::Phone)), ("Address", x(260.0), principal(O::Address))]),
        (212.0, vec![("City", x(2.0), principal(O::City)), ("Zip", x(345.0), principal(O::Zip))]),
        (214.0, vec![("State", x(228.0), principal(O::State))]),
        (231.0, vec![("SSN", x(2.0), principal(O::Ssn)), ("Date of Birth", x(260.0), principal(O::BirthDate))]),
        (
            247.0,
            vec![("Ownership %", x(206.0), secondary(O::OwnershipPercent)), ("Email", x(341.0), secondary(O::Email))],
        ),
        (248.0, vec![("Secondary Owner Name", x(2.0), secondary(O::Name))]),
        (262.0, vec![("Phone", x(2.0), secondary(O::Phone)), ("Address", x(260.0), secondary(O::Address))]),
        (
            277.0,
            vec![
                ("City", x(2.0), secondary(O::City)),
                ("State", x(228.0), secondary(O::State)),
                ("Zip", x(345.0), secondary(O::Zip)),
            ],
        ),
        (296.0, vec![("SSN", x(2.0), secondary(O::Ssn)), ("Date of Birth", x(260.0), secondary(O::BirthDate))]),
        (327.0, vec![("Annual Business Revenue", x(260.0), property(P::AnnualRevenue))]),
        (329.0, vec![("Business Description", x(2.0), property(P::Description))]),
        (
            345.0,
            vec![
                ("Purpose of Funds Requested", x(2.0), property(P::FundsPurpose)),
                ("Estimated Fico Score", x(260.0), property(P::EstimatedFico)),
            ],
        ),
        (
            363.0,
            vec![
                ("Average Monthly Credit Card Volume", x(2.0), property(P::CardVolume)),
                ("Amount of Receivable Outstanding", x(260.0), property(P::ReceivablesOutstanding)),
            ],
        ),
        (382.0, vec![("Prior/Current Loan Company (if applicable)", x(2.0), property(P::PriorLender))]),
        (401.0, vec![("Requested Advance Amount", x(260.0), property(P::RequestedAmount))]),
        (402.0, vec![("Existing Loan Balance", x(2.0), property(P::LoanBalance))]),
        (417.0, vec![("Any bankruptcy?", x(259.0), property(P::Bankruptcy))]),
        (418.0, vec![("Any open judgements?", x(1.0), property(P::OpenJudgements))]),
        (
            434.0,
            vec![
                ("Any tax liens?", x(1.0), property(P::TaxLiens)),
                ("Is business seasonal?", x(260.0), property(P::Seasonal)),
            ],
        ),
        (
            611.0,
            vec![
                ("Signature of Applicant One", x(2.0), None),
                ("Date", x(290.0), Some(FieldId::Signature(S::ApplicantOneDate))),
            ],
        ),
        (
            638.0,
            vec![
                ("Signature of Applicant Two", x(2.0), None),
                ("Date", x(290.0), Some(FieldId::Signature(S::ApplicantTwoDate))),
            ],
        ),
    ];
    let seasonal = 434.0;
    Layout {
        rows,
        headings: [167.0, 311.0],
        label_font: "AdobeDevanagari-Regular",
        dx: 0.0,
        dy: |dy| dy,
        extras: vec![
            printed(8.0, x(-3.0), -60.0, "Sales Rep Name:"),
            typed("ArialMT", VALUE_SIZE, x(70.0), -59.0, "SAMPLE REP"),
            printed(10.0, x(149.0), -54.0, "FAX COMPLETED APPLICATION TO:"),
            typed("ArialMT", VALUE_SIZE, x(330.0), -53.0, "512-555-0198"),
            printed(8.0, x(-3.0), -38.0, "Contact Email:"),
            typed("ArialMT", VALUE_SIZE, x(70.0), -37.0, "rep@example.com"),
            printed(LABEL_SIZE, 180.0, 86.0, "Corporation"),
            printed(LABEL_SIZE, 300.0, 86.0, "LLC"),
            printed(LABEL_SIZE, 370.0, 86.0, "Other: (please describe):"),
            typed("ArialMT", VALUE_SIZE, 320.0, ENTITY_MARK_DY, "X"),
            printed(LABEL_SIZE, 440.0, seasonal, "YES"),
            printed(LABEL_SIZE, 480.0, seasonal, "NO"),
            typed("ArialMT", VALUE_SIZE, 496.0, seasonal + 1.6, "X"),
            printed(10.0, 40.0, 470.0, "I certify that the information above is true and correct,"),
            printed(10.0, 40.0, 484.0, "and I authorize SAMPLE to verify it."),
            typed("DancingScript", 14.0, 200.0, 609.0, "Sample Owner"),
            printed(LABEL_SIZE, 353.0, 611.0, SIGNATURE_DATE_LINE),
            printed(LABEL_SIZE, 353.0, 638.0, SIGNATURE_DATE_LINE),
            printed(12.0, x(89.0), 660.0, "Fax: 512-555-0199"),
            printed(12.0, x(196.0), 660.0, "Email: forms@example.com"),
        ],
    }
}

pub fn sample_values() -> Vec<(FieldId, &'static str)> {
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
        (FieldId::Business(B::Entity), "LIMITED LIABILITY COMPANY (LLC)"),
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
pub fn expected() -> Vec<(FieldId, &'static str)> {
    let mut values = sample_values();
    let canonical = [
        (FieldId::Business(B::Phone), "512-555-0100"),
        (FieldId::Business(B::Fax), "512-555-0101"),
        (FieldId::Business(B::Entity), "LIMITED LIABILITY COMPANY"),
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

pub struct Form {
    pub layout: Layout,
    pub values: Vec<(FieldId, &'static str)>,
    /// Labels left off the page.
    pub omit: Vec<&'static str>,
}

impl Form {
    pub fn word() -> Form {
        Form { layout: word(), values: sample_values(), omit: Vec::new() }
    }

    pub fn set(mut self, field: FieldId, text: &'static str) -> Form {
        self.values.retain(|(f, _)| *f != field);
        self.values.push((field, text));
        self
    }

    pub fn clear(mut self, field: FieldId) -> Form {
        self.values.retain(|(f, _)| *f != field);
        self
    }

    pub fn label_top(&self, dy: f32) -> f32 {
        HEADING.1 + (self.layout.dy)(dy)
    }

    pub fn draw<C: Canvas>(&self, canvas: C) -> C {
        let heading_font = "TimesNewRomanPS-BoldMT";
        let mut page = canvas
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
        for extra in &self.layout.extras {
            let font = extra.font.unwrap_or(self.layout.label_font);
            page = page.text(font, extra.size, extra.x + self.layout.dx, self.label_top(extra.dy), extra.text);
        }
        page
    }
}

/// A fabricated certificate in DocuSign's arrangement, with an originator block above the
/// signer rows.
pub fn certificate<C: Canvas>(canvas: C, signers: &[(&str, &str)]) -> C {
    let font = "ArialMT";
    let mut page = canvas
        .text(font, 12.0, 40.0, 40.0, "Certificate Of Completion")
        .text(font, 9.0, 40.0, 60.0, "Envelope Id: 0F8FAD5BD9CB469FA16570867728950E")
        .text(font, 9.0, 330.0, 60.0, "Status: Completed")
        .text(font, 9.0, 40.0, 75.0, "Document Pages: 1")
        .text(font, 9.0, 330.0, 75.0, "Envelope Originator:")
        .text(font, 9.0, 330.0, 87.0, "SAMPLE ORIGINATOR")
        .text(font, 9.0, 330.0, 99.0, "originator@example.com")
        .text(font, 9.0, 40.0, 120.0, "Signer Events")
        .text(font, 9.0, 250.0, 120.0, "Signature")
        .text(font, 9.0, 420.0, 120.0, "Timestamp");
    let mut top = 135.0;
    for (name, email) in signers {
        page = page
            .text(font, 9.0, 40.0, top, name)
            .text(font, 9.0, 250.0, top, name)
            .text(font, 9.0, 420.0, top, "Sent: 10/20/2026 | 09:01 AM")
            .text(font, 9.0, 40.0, top + 11.0, email)
            .text(font, 9.0, 420.0, top + 11.0, "Signed: 10/20/2026 | 09:30 AM")
            .text(font, 9.0, 40.0, top + 22.0, "Security Level: Email, Account Authentication (None)");
        top += 40.0;
    }
    page.text(font, 9.0, 40.0, top, "In Person Signer Events")
        .text(font, 9.0, 250.0, top, "Signature")
        .text(font, 9.0, 40.0, top + 30.0, "Envelope Summary Events")
        .text(font, 9.0, 40.0, top + 42.0, "Envelope Sent Hashed/Encrypted 10/19/2026 | 09:01 AM")
        .text(font, 9.0, 40.0, top + 54.0, "Completed Security Checked 10/20/2026 | 09:30 AM")
}
