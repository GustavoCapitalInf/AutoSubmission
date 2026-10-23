//! Reads Capital Infusion's merchant application PDFs into typed field readings. It reaches no
//! store, network or log.

pub mod certificate;
pub mod extract;
pub mod fields;
pub mod page;
mod template;
pub mod values;

pub use certificate::{Certificate, SignerCheck, compare_signer};
pub use extract::{Document, FieldReading, Outcome, Reading, read};
pub use fields::{FieldId, FieldKind, FieldMap, FieldSpec};
pub use page::{Glyph, PdfFacts, Rect, TextPage};
pub use values::{Answer, Country, FieldValue, Jurisdiction, RawText, ReadContext, Refusal, YearMonth};
