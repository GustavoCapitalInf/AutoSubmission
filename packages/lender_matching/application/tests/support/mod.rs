//! Test content shared by this crate's tests and the service's through `#[path]`.
//! Every value is fabricated: CONTOSO, FABRIKAM, NORTHWIND, SAMPLE, `example.com`, `555-01xx`
//! phones and SSNs in the 9xx range.
#![allow(dead_code)]

pub mod form;
pub mod pdf;

use std::path::PathBuf;

/// The pdfium library from `PDFIUM_LIBRARY`. Without it, a test that needs pdfium fails when
/// `PDFIUM_REQUIRED` is set, and otherwise prints why it skips.
pub fn pdfium_library() -> Option<PathBuf> {
    match std::env::var_os("PDFIUM_LIBRARY").filter(|path| !path.is_empty()) {
        Some(path) => Some(PathBuf::from(path)),
        None if std::env::var_os("PDFIUM_REQUIRED").is_some() => {
            panic!("PDFIUM_REQUIRED is set, but PDFIUM_LIBRARY names no pdfium library")
        }
        None => {
            eprintln!("skipped: PDFIUM_LIBRARY is not set");
            None
        }
    }
}
