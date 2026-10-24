//! What the application pages print for a field: its label, and why it needs a person. Every
//! message is fixed text that names the field, never its value.

use lender_matching_application::extract::{Doubt, ManualEntryReason, RefusalReason, Unlocated};
use lender_matching_application::fields::SignatureField;
use lender_matching_application::fields::{BusinessField as B, OwnerField as O, OwnerSlot, PropertyField as P};
use lender_matching_application::record::Attention;
use lender_matching_application::{EditRefusal, EmailFault, FieldId, FieldKind, Refusal};

use crate::applications::{Cause, RevisionKind};

pub fn label(field: FieldId) -> String {
    match field {
        FieldId::Business(field) => match field {
            B::LegalName => "Business Legal Name",
            B::Dba => "Doing Business As (DBA)",
            B::Address => "Business Address",
            B::Suite => "Suite/Floor",
            B::City => "Business City",
            B::State => "Business State",
            B::Zip => "Business Zip",
            B::Phone => "Business Phone",
            B::Fax => "Business Fax",
            B::Entity => "Entity",
            B::Email => "Business Email",
            B::StartDate => "Business Start Date",
            B::OwnershipStart => "Date Current Ownership Started",
            B::TaxId => "Federal Tax ID",
            B::Website => "Website",
            B::LandlordName => "Landlord Name",
            B::LandlordPhone => "Landlord Phone",
            B::LeaseTimeLeft => "Time Left on Lease",
            B::MonthlyRent => "Monthly Rent/Mortgage Payment",
            B::RentCurrent => "Current with Rent/Mortgage?",
        }
        .to_string(),
        FieldId::Owner(slot, field) => {
            let owner = match slot {
                OwnerSlot::Principal => "Principal",
                OwnerSlot::Secondary => "Secondary",
            };
            let field = match field {
                O::Name => "Owner Name",
                O::OwnershipPercent => "Ownership %",
                O::Email => "Email",
                O::Phone => "Phone",
                O::Address => "Address",
                O::City => "City",
                O::State => "State",
                O::Zip => "Zip",
                O::Ssn => "SSN",
                O::BirthDate => "Date of Birth",
            };
            format!("{owner} {field}")
        }
        FieldId::Property(field) => match field {
            P::Description => "Business Description",
            P::AnnualRevenue => "Annual Business Revenue",
            P::FundsPurpose => "Purpose of Funds Requested",
            P::EstimatedFico => "Estimated FICO Score",
            P::CardVolume => "Average Monthly Credit Card Volume",
            P::ReceivablesOutstanding => "Amount of Receivables Outstanding",
            P::PriorLender => "Prior/Current Loan Company",
            P::LoanBalance => "Existing Loan Balance",
            P::RequestedAmount => "Requested Advance Amount",
            P::OpenJudgements => "Any open judgements?",
            P::Bankruptcy => "Any bankruptcy?",
            P::TaxLiens => "Any tax liens?",
            P::Seasonal => "Is business seasonal?",
        }
        .to_string(),
        FieldId::Signature(SignatureField::ApplicantOneDate) => "Applicant One Signed".to_string(),
        FieldId::Signature(SignatureField::ApplicantTwoDate) => "Applicant Two Signed".to_string(),
    }
}

fn noun(kind: FieldKind) -> &'static str {
    match kind {
        FieldKind::Text => "text",
        FieldKind::Email => "an email address",
        FieldKind::Phone => "a phone number",
        FieldKind::Jurisdiction => "a state or province",
        FieldKind::PostalCode => "a zip or postal code",
        FieldKind::Entity => "an entity type",
        FieldKind::StatedDate | FieldKind::BirthDate | FieldKind::SignatureDate => "a date",
        FieldKind::TaxId => "a tax ID",
        FieldKind::Ssn => "an SSN",
        FieldKind::Money => "an amount",
        FieldKind::Percent => "a percent",
        FieldKind::Score => "a score",
        FieldKind::YesNo => "a yes or no",
    }
}

fn example(kind: FieldKind) -> &'static str {
    match kind {
        FieldKind::Text => "type it as the page shows it",
        FieldKind::Email => "write it as name@example.com",
        FieldKind::Phone => "write 10 digits, such as 512-555-0100",
        FieldKind::Jurisdiction => "write a postal code such as TX or ON, or the full name",
        FieldKind::PostalCode => "write it as 78701 or K1A 0B1",
        FieldKind::Entity => {
            "write LLC, corporation, S corporation, C corporation, sole proprietorship, partnership or non-profit"
        }
        FieldKind::StatedDate => "write it as 04/15/2019 or 04/2019",
        FieldKind::BirthDate => "write it as 04/15/1980",
        FieldKind::SignatureDate => "it is DocuSign's date stamp",
        FieldKind::TaxId => "write 9 digits, such as 12-3456789",
        FieldKind::Ssn => "write its 9 digits",
        FieldKind::Money => "write an amount such as 50,000",
        FieldKind::Percent => "write a percent such as 50",
        FieldKind::Score => "write a score from 300 to 850, such as 700",
        FieldKind::YesNo => "write YES or NO",
    }
}

fn email_fault(fault: EmailFault) -> &'static str {
    match fault {
        EmailFault::NoAt => "it has no @",
        EmailFault::SeveralAt => "it has more than one @",
        EmailFault::InnerSpace => "it holds a space",
        EmailFault::TrailingPunctuation => "it ends in punctuation",
        EmailFault::BadLocal => "the part before the @ is not valid",
        EmailFault::BadDomain => "the part after the @ is not a domain",
    }
}

/// Why text gives no value of `kind`, and how to write one.
pub fn refusal(kind: FieldKind, why: Refusal) -> String {
    let example = example(kind);
    let dated = matches!(kind, FieldKind::StatedDate | FieldKind::BirthDate | FieldKind::SignatureDate);
    match why {
        Refusal::Format => format!("Could not read this as {}; {example}", noun(kind)),
        Refusal::Email(fault) => format!("Not an email address: {}; {example}", email_fault(fault)),
        Refusal::Ambiguous if dated => {
            "This date reads more than one way; write it with the year first, such as 2019-04-15".to_string()
        }
        Refusal::Ambiguous => format!("This reads more than one way; {example}"),
        Refusal::OutOfRange => match kind {
            FieldKind::StatedDate | FieldKind::SignatureDate => "This date is after the application was signed",
            FieldKind::BirthDate => {
                "This makes the owner younger than 18 or older than 100 when the application was signed"
            }
            FieldKind::Score => "A score lies from 300 to 850",
            FieldKind::Percent => "A percent lies from 0 to 100",
            _ => "This is out of range",
        }
        .to_string(),
        Refusal::NotInList => {
            let known = match kind {
                FieldKind::Jurisdiction => "state or province",
                FieldKind::Entity => "entity type",
                _ => "value",
            };
            format!("Not a known {known}; {example}")
        }
        Refusal::MarkUnclear => format!("The marks on the page are unclear; {example}"),
        Refusal::Undecodable => "The PDF's text could not be decoded; type it as the page shows it".to_string(),
        Refusal::NoSigningDate => {
            "The signing date is unknown, so a two-digit year cannot be read; write the year in full".to_string()
        }
    }
}

/// The hint beside a field that needs a person.
pub fn attention(kind: FieldKind, attention: Attention) -> String {
    match attention {
        Attention::RequiredEmpty => "Required".to_string(),
        Attention::Refused(why) => refusal(kind, why),
        Attention::Unlocated(Unlocated::LabelMissing) => {
            "The label was not found on the page; enter this from the page".to_string()
        }
        Attention::Unlocated(Unlocated::LabelOutOfPlace) => {
            "The label is out of place on the page; enter this from the page".to_string()
        }
        Attention::Doubtful(Doubt::LabelFoundTwice) => {
            "The label is printed more than once; check this against the page".to_string()
        }
        Attention::Doubtful(Doubt::StrayLabel) => {
            "Other label text lies in this field; check it against the page".to_string()
        }
        Attention::Doubtful(Doubt::SharedGlyph) => {
            "This text may belong to the next field; check it against the page".to_string()
        }
    }
}

/// A refused correction, naming the field.
pub fn edit_refusal(field: FieldId, why: EditRefusal) -> String {
    let why = match why {
        EditRefusal::NotEditable => "this field is not edited by hand".to_string(),
        EditRefusal::Repeated => "it was given twice".to_string(),
        EditRefusal::Value(why) => refusal(field.spec().kind, why),
    };
    format!("{}: {why}", label(field))
}

pub fn manual_entry(reason: ManualEntryReason) -> &'static str {
    match reason {
        ManualEntryReason::SuspectedScan => "page 1 looks like a scan, with little or no text",
        ManualEntryReason::UnknownLayout => "page 1 has the form's headings, but its labels fit no known layout",
        ManualEntryReason::AmbiguousDocument => "page 1 has both the application's and a contract's headings",
    }
}

pub fn refused_document(reason: RefusalReason) -> &'static str {
    match reason {
        RefusalReason::Contract => "a Receivables Purchase Agreement",
        RefusalReason::OtherPaperwork => "other envelope paperwork, without the application form's headings",
    }
}

pub fn revision_kind(kind: RevisionKind) -> &'static str {
    match kind {
        RevisionKind::Upload => "Uploaded",
        RevisionKind::Edit(Cause::Reading) => "Corrected: the parser read the PDF wrong",
        RevisionKind::Edit(Cause::Merchant) => "Corrected: the merchant typed it wrong",
        RevisionKind::AdoptParse => "A new reading of the PDF adopted",
        RevisionKind::ConfirmApplication => "Confirmed as an application",
    }
}
