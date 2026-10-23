use crate::fields::{BusinessField as B, FieldId, OwnerField as O, OwnerSlot, PropertyField as P, SignatureField};

/// Capital Infusion's application form. A new placement of the same labels adds a `LayoutSpec`;
/// only a new kind of value placement needs code.
pub(crate) struct FormTemplate {
    /// In reading order. Each section runs from its start to the next section's start; the last
    /// one holds the signature lines.
    pub sections: &'static [SectionSpec],
    /// Font family prefixes a label is printed in: Calibri in the Word layout, AdobeDevanagari in
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

#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum Shape {
    /// On the label's row, to its right.
    Row,
    /// The row, then one more line under it, for a value that wraps.
    RowAndNextLine,
}

/// A known placement of the form: where a few sentinel labels' top-left corners sit relative to
/// the BUSINESS INFORMATION heading's top-left corner, in points.
pub(crate) struct LayoutSpec {
    pub id: &'static str,
    /// The label, its horizontal offset where one was measured, and its vertical offset.
    pub sentinels: &'static [(FieldId, Option<f32>, f32)],
}

/// How far a sentinel may sit from its layout's offset.
pub(crate) const LAYOUT_TOLERANCE_PT: f32 = 3.0;
/// A value's top lies within this band of its label's top.
pub(crate) const ROW_BAND_PT: (f32, f32) = (-10.0, 8.0);
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

const PRINCIPAL: [LabelSpec; 10] = owner(OwnerSlot::Principal, "Principle Owner Name");
const SECONDARY: [LabelSpec; 10] = owner(OwnerSlot::Secondary, "Secondary Owner Name");

pub(crate) static FORM: FormTemplate = FormTemplate {
    sections: &[
        SectionSpec {
            start: SectionStart::Heading("BUSINESS INFORMATION"),
            labels: &[
                business("Business Legal Name", B::LegalName),
                business("Doing Business As (DBA)", B::Dba),
                business("Address", B::Address),
                business("Suite/Floor", B::Suite),
                business("City", B::City),
                business("State", B::State),
                business("Zip", B::Zip),
                business("Phone", B::Phone),
                business("Fax", B::Fax),
                business("Entity", B::Entity),
                business("Email", B::Email),
                business("Business Start Date (MM/YYYY)", B::StartDate),
                business("Date Current Ownership Started", B::OwnershipStart),
                business("Federal Tax ID", B::TaxId),
                business("Website", B::Website),
                business("Landlord Name", B::LandlordName),
                business("Landlord Phone", B::LandlordPhone),
                business("Time Left on Lease", B::LeaseTimeLeft),
                business("Monthly Rent/Mortgage Payment", B::MonthlyRent),
                business("Are You Current with Rent/Mortgage?", B::RentCurrent),
            ],
        },
        SectionSpec { start: SectionStart::Heading("OWNER INFORMATION"), labels: &[] },
        SectionSpec { start: SectionStart::FirstLabel, labels: &PRINCIPAL },
        SectionSpec { start: SectionStart::FirstLabel, labels: &SECONDARY },
        SectionSpec {
            start: SectionStart::Heading("BUSINESS PROPERTY INFORMATION"),
            labels: &[
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
                property("Is business seasonal?", P::Seasonal),
            ],
        },
        SectionSpec {
            start: SectionStart::FirstLabel,
            labels: &[
                LabelSpec { text: "Signature of Applicant One", target: Target::Signature, shape: Shape::Row },
                row("Date", FieldId::Signature(SignatureField::ApplicantOneDate)),
                LabelSpec { text: "Signature of Applicant Two", target: Target::Signature, shape: Shape::Row },
                row("Date", FieldId::Signature(SignatureField::ApplicantTwoDate)),
            ],
        },
    ],
    label_fonts: &["Calibri", "AdobeDevanagari"],
    layouts: &[
        LayoutSpec {
            id: "word",
            sentinels: &[
                (FieldId::Business(B::LegalName), Some(0.0), 18.0),
                (FieldId::Business(B::TaxId), None, 129.0),
                (FieldId::Owner(OwnerSlot::Principal, O::Ssn), None, 256.0),
                (FieldId::Owner(OwnerSlot::Secondary, O::Ssn), None, 330.0),
            ],
        },
        LayoutSpec {
            id: "pdfescape",
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
    fn every_field_has_exactly_one_label() {
        let mut seen = BTreeSet::new();
        for section in FORM.sections {
            for label in section.labels {
                if let Target::Field(field) = label.target {
                    assert!(seen.insert(field), "{field} has two labels");
                }
            }
        }
        assert_eq!(seen.len(), FieldId::COUNT);
    }

    #[test]
    fn a_label_section_starts_at_its_first_label_and_layouts_name_placed_fields() {
        for section in FORM.sections {
            if matches!(section.start, SectionStart::FirstLabel) {
                assert!(!section.labels.is_empty());
            }
        }
        for layout in FORM.layouts {
            assert_eq!(layout.sentinels.len(), FORM.layouts[0].sentinels.len(), "{}", layout.id);
            for (i, (field, _, _)) in layout.sentinels.iter().enumerate() {
                assert_eq!(*field, FORM.layouts[0].sentinels[i].0, "{} names the same sentinels", layout.id);
            }
        }
    }
}
