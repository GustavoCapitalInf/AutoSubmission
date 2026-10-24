use crate::fields::{BusinessField as B, FieldId, OwnerField as O, OwnerSlot, PropertyField as P, SignatureField};
use crate::values::{Entity, YesNo};

/// Capital Infusion's application form in the versions it was printed in. A new placement of a
/// known label set adds a `LayoutSpec`; only a new kind of value placement needs code.
pub(crate) struct FormTemplate {
    /// Font family prefixes a label is printed in: Calibri in the Word version, AdobeDevanagari in
    /// the PDFescape one. A value typed in another font is not taken for a label.
    pub label_fonts: &'static [&'static str],
    pub layouts: &'static [LayoutSpec],
}

pub(crate) struct SectionSpec {
    pub start: SectionStart,
    pub labels: &'static [LabelSpec],
}

pub(crate) enum SectionStart {
    /// A heading, matched by its text in any font.
    Heading(&'static str),
    /// The section's first label.
    FirstLabel,
}

#[derive(Clone, Copy)]
pub(crate) struct LabelSpec {
    /// The printed text, matched exactly apart from spacing and a trailing colon.
    pub text: &'static str,
    pub target: Target,
    pub shape: Shape,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum Target {
    Field(FieldId),
    /// A signature line: what lies on its row is the signature, which no field reads.
    Signature,
}

#[derive(Clone, Copy)]
pub(crate) enum Shape {
    /// On the label's row, to its right.
    Row,
    /// The row, then one more line under it for a value that wraps, ending above the band of the
    /// next label row.
    RowAndNextLine,
    /// The row prints `choices` in a label font, each after its box: a mark picks the one it sits
    /// before. `printed` is more form text on the row; anything else typed there describes the
    /// answer.
    Choices { choices: &'static [Choice], printed: &'static [&'static str] },
}

#[derive(Clone, Copy)]
pub(crate) struct Choice {
    pub text: &'static str,
    pub answer: ChoiceAnswer,
}

/// What a mark on a printed choice answers.
#[derive(Clone, Copy)]
pub(crate) enum ChoiceAnswer {
    Entity(Entity),
    YesNo(YesNo),
    /// The description typed on the row, read by the field's grammar.
    Described,
}

/// A known placement of the form: its label set, and where a few sentinel labels' top-left
/// corners sit relative to the BUSINESS INFORMATION heading's top-left corner, in points.
pub(crate) struct LayoutSpec {
    pub id: &'static str,
    /// In reading order. Each section runs from its start to the next section's start; the last
    /// one holds the signature lines.
    pub sections: &'static [SectionSpec],
    /// The label, its horizontal offset where one was measured, and its vertical offset, all as
    /// pdfium measures the label's loose box.
    pub sentinels: &'static [(FieldId, Option<f32>, f32)],
}

/// How far a sentinel may sit from its layout's offset.
pub(crate) const LAYOUT_TOLERANCE_PT: f32 = 3.0;
/// A value's top lies within this band of its label's top.
pub(crate) const ROW_BAND_PT: (f32, f32) = (-10.0, 8.0);
/// A mark picks the printed choice whose left edge is the first at or right of the mark's centre,
/// when that edge lies at most this far from it.
pub(crate) const MARK_REACH_PT: f32 = 30.0;
/// The line under a wrapping value's row: tops below the row band, down to this far under the
/// label's top.
pub(crate) const NEXT_LINE_BOTTOM_PT: f32 = 20.0;
/// The title of a Receivables Purchase Agreement, which is not an application.
pub(crate) const CONTRACT_TITLE: &str = "RECEIVABLES PURCHASE AGREEMENT";
/// A page whose largest image covers this share of it reads as a scan.
pub(crate) const SCAN_IMAGE_COVER: f32 = 0.8;
/// A first page with fewer characters than this has no usable text layer.
pub(crate) const MIN_TEXT_CHARS: usize = 300;

const fn row(text: &'static str, field: FieldId) -> LabelSpec {
    LabelSpec { text, target: Target::Field(field), shape: Shape::Row }
}

const fn business(text: &'static str, field: B) -> LabelSpec {
    row(text, FieldId::Business(field))
}

const fn property(text: &'static str, field: P) -> LabelSpec {
    row(text, FieldId::Property(field))
}

/// The business labels in reading order; the versions differ only in the three labels that
/// follow Phone.
const fn business_labels(after_phone: [LabelSpec; 3]) -> [LabelSpec; 20] {
    let [first, second, third] = after_phone;
    [
        business("Business Legal Name", B::LegalName),
        business("Doing Business As (DBA)", B::Dba),
        business("Address", B::Address),
        business("Suite/Floor", B::Suite),
        business("City", B::City),
        business("State", B::State),
        business("Zip", B::Zip),
        business("Phone", B::Phone),
        first,
        second,
        third,
        business("Business Start Date (MM/YYYY)", B::StartDate),
        business("Date Current Ownership Started", B::OwnershipStart),
        business("Federal Tax ID", B::TaxId),
        business("Website", B::Website),
        business("Landlord Name", B::LandlordName),
        business("Landlord Phone", B::LandlordPhone),
        business("Time Left on Lease", B::LeaseTimeLeft),
        business("Monthly Rent/Mortgage Payment", B::MonthlyRent),
        business("Are You Current with Rent/Mortgage?", B::RentCurrent),
    ]
}

/// The Word version: Fax, then Entity, a DocuSign dropdown, then Email.
static WORD_BUSINESS: [LabelSpec; 20] =
    business_labels([business("Fax", B::Fax), business("Entity", B::Entity), business("Email", B::Email)]);

/// The PDFescape version: Fax and Email share the Phone row, and the entity is a row of printed
/// choices with a description after "Other".
static PDFESCAPE_BUSINESS: [LabelSpec; 20] = business_labels([
    business("Fax", B::Fax),
    business("Email", B::Email),
    LabelSpec {
        text: "Type of Entity",
        target: Target::Field(FieldId::Business(B::Entity)),
        shape: Shape::Choices {
            choices: &[
                Choice { text: "Corporation", answer: ChoiceAnswer::Entity(Entity::Corporation) },
                Choice { text: "LLC", answer: ChoiceAnswer::Entity(Entity::Llc) },
                Choice { text: "Other", answer: ChoiceAnswer::Described },
            ],
            printed: &["(please describe)"],
        },
    },
]);

const fn owner(slot: OwnerSlot, first: &'static str) -> [LabelSpec; 10] {
    [
        row(first, FieldId::Owner(slot, O::Name)),
        row("Ownership %", FieldId::Owner(slot, O::OwnershipPercent)),
        row("Email", FieldId::Owner(slot, O::Email)),
        row("Phone", FieldId::Owner(slot, O::Phone)),
        row("Address", FieldId::Owner(slot, O::Address)),
        row("City", FieldId::Owner(slot, O::City)),
        row("State", FieldId::Owner(slot, O::State)),
        row("Zip", FieldId::Owner(slot, O::Zip)),
        row("SSN", FieldId::Owner(slot, O::Ssn)),
        row("Date of Birth", FieldId::Owner(slot, O::BirthDate)),
    ]
}

static PRINCIPAL: [LabelSpec; 10] = owner(OwnerSlot::Principal, "Principle Owner Name");
static SECONDARY: [LabelSpec; 10] = owner(OwnerSlot::Secondary, "Secondary Owner Name");

/// The property labels in reading order; the versions differ only in how the seasonal question is
/// answered.
const fn property_labels(seasonal: LabelSpec) -> [LabelSpec; 13] {
    [
        property("Business Description", P::Description),
        property("Annual Business Revenue", P::AnnualRevenue),
        property("Purpose of Funds Requested", P::FundsPurpose),
        property("Estimated Fico Score", P::EstimatedFico),
        property("Average Monthly Credit Card Volume", P::CardVolume),
        property("Amount of Receivable Outstanding", P::ReceivablesOutstanding),
        LabelSpec {
            text: "Prior/Current Loan Company (if applicable)",
            target: Target::Field(FieldId::Property(P::PriorLender)),
            shape: Shape::RowAndNextLine,
        },
        property("Existing Loan Balance", P::LoanBalance),
        property("Requested Advance Amount", P::RequestedAmount),
        property("Any open judgements?", P::OpenJudgements),
        property("Any bankruptcy?", P::Bankruptcy),
        property("Any tax liens?", P::TaxLiens),
        seasonal,
    ]
}

/// The Word version: the seasonal answer is typed.
static WORD_PROPERTY: [LabelSpec; 13] = property_labels(property("Is business seasonal?", P::Seasonal));

/// The PDFescape version: the seasonal answer is a row of the printed choices Yes and No.
static PDFESCAPE_PROPERTY: [LabelSpec; 13] = property_labels(LabelSpec {
    text: "Is business seasonal?",
    target: Target::Field(FieldId::Property(P::Seasonal)),
    shape: Shape::Choices {
        choices: &[
            Choice { text: "Yes", answer: ChoiceAnswer::YesNo(YesNo::Yes) },
            Choice { text: "No", answer: ChoiceAnswer::YesNo(YesNo::No) },
        ],
        printed: &[],
    },
});

static SIGNATURES: [LabelSpec; 4] = [
    LabelSpec { text: "Signature of Applicant One", target: Target::Signature, shape: Shape::Row },
    row("Date", FieldId::Signature(SignatureField::ApplicantOneDate)),
    LabelSpec { text: "Signature of Applicant Two", target: Target::Signature, shape: Shape::Row },
    row("Date", FieldId::Signature(SignatureField::ApplicantTwoDate)),
];

const fn sections(business: &'static [LabelSpec], property: &'static [LabelSpec]) -> [SectionSpec; 6] {
    [
        SectionSpec { start: SectionStart::Heading("BUSINESS INFORMATION"), labels: business },
        SectionSpec { start: SectionStart::Heading("OWNER INFORMATION"), labels: &[] },
        SectionSpec { start: SectionStart::FirstLabel, labels: &PRINCIPAL },
        SectionSpec { start: SectionStart::FirstLabel, labels: &SECONDARY },
        SectionSpec { start: SectionStart::Heading("BUSINESS PROPERTY INFORMATION"), labels: property },
        SectionSpec { start: SectionStart::FirstLabel, labels: &SIGNATURES },
    ]
}

static WORD_SECTIONS: [SectionSpec; 6] = sections(&WORD_BUSINESS, &WORD_PROPERTY);
/// Above BUSINESS INFORMATION this version prints the sales rep's header (Sales Rep Name, Contact
/// Email, FAX COMPLETED APPLICATION TO), and under the signature lines a Fax and Email footer.
/// Both lie outside the form area, so no field reads them and nothing there is unplaced.
static PDFESCAPE_SECTIONS: [SectionSpec; 6] = sections(&PDFESCAPE_BUSINESS, &PDFESCAPE_PROPERTY);

pub(crate) static FORM: FormTemplate = FormTemplate {
    label_fonts: &["Calibri", "AdobeDevanagari"],
    layouts: &[
        LayoutSpec {
            id: "word",
            sections: &WORD_SECTIONS,
            sentinels: &[
                (FieldId::Business(B::LegalName), Some(0.0), 16.0),
                (FieldId::Business(B::TaxId), None, 127.0),
                (FieldId::Owner(OwnerSlot::Principal, O::Ssn), None, 254.0),
                (FieldId::Owner(OwnerSlot::Secondary, O::Ssn), None, 328.0),
            ],
        },
        LayoutSpec {
            id: "pdfescape",
            sections: &PDFESCAPE_SECTIONS,
            sentinels: &[
                (FieldId::Business(B::LegalName), Some(2.0), 15.0),
                (FieldId::Business(B::TaxId), None, 121.0),
                (FieldId::Owner(OwnerSlot::Principal, O::Ssn), None, 231.0),
                (FieldId::Owner(OwnerSlot::Secondary, O::Ssn), None, 296.0),
            ],
        },
    ],
};

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeSet;

    #[test]
    fn every_layout_gives_every_field_exactly_one_label() {
        for layout in FORM.layouts {
            let mut seen = BTreeSet::new();
            for section in layout.sections {
                for label in section.labels {
                    if let Target::Field(field) = label.target {
                        assert!(seen.insert(field), "{}: {field} has two labels", layout.id);
                    }
                }
            }
            assert_eq!(seen.len(), FieldId::COUNT, "{}", layout.id);
        }
    }

    #[test]
    fn a_label_section_starts_at_its_first_label_and_layouts_name_the_same_sentinels() {
        for layout in FORM.layouts {
            for section in layout.sections {
                if matches!(section.start, SectionStart::FirstLabel) {
                    assert!(!section.labels.is_empty(), "{}", layout.id);
                }
            }
            assert_eq!(layout.sentinels.len(), FORM.layouts[0].sentinels.len(), "{}", layout.id);
            for (i, (field, _, _)) in layout.sentinels.iter().enumerate() {
                assert_eq!(*field, FORM.layouts[0].sentinels[i].0, "{} names the same sentinels", layout.id);
            }
        }
    }
}
