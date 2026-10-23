//! Reads Capital Infusion's merchant application PDFs into typed field readings. It reaches no
//! store, network or log.

pub mod fields;
pub mod values;

pub use fields::{FieldId, FieldKind, FieldMap, FieldSpec};
pub use values::{Answer, Country, FieldValue, Jurisdiction, RawText, ReadContext, Refusal, YearMonth};
