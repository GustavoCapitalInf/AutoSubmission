//! Reads Capital Infusion's merchant application PDFs into typed field readings. It reaches no
//! store, network or log. `pdf` is the only part that touches pdfium, and `worker` runs it in a
//! child process; every other function is pure.

pub mod certificate;
pub mod extract;
pub mod fields;
pub mod page;
pub mod pdf;
pub mod record;
pub mod tally;
mod template;
pub mod values;
pub mod worker;

/// A bump makes earlier evaluate reports stale; bump it when the same PDF would read differently.
pub const PARSER_VERSION: u32 = 3;

#[cfg(test)]
extern crate self as lender_matching_application;
#[cfg(test)]
#[path = "../tests/support/mod.rs"]
mod support;

pub use certificate::{Certificate, DetailCheck, SignerCheck, SignerComparison, compare_signer};
pub use extract::{Document, FieldReading, Outcome, Reading, read};
pub use fields::{FieldId, FieldKind, FieldMap, FieldSpec};
pub use page::{Glyph, PdfFacts, Rect, TextPage};
pub use record::{
    Admission, Current, EditInput, EditRefusal, Edits, EmptyReason, Override, Record, Resolved, RevisionState,
};
pub use values::{Answer, Country, EmailFault, FieldValue, Jurisdiction, RawText, ReadContext, Refusal, YearMonth};
