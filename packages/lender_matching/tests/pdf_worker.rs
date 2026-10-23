#[path = "../application/tests/support/mod.rs"]
mod support;

use std::path::Path;
use std::time::Duration;

use lender_matching_application::extract::{Document, read};
use lender_matching_application::pdf::ReadError;
use lender_matching_application::worker::{PdfWorker, WorkerError};
use support::form::{Form, certificate};
use support::pdf::{FakePage, FakePdf};

const ENOUGH: Duration = Duration::from_secs(60);

fn binary() -> &'static Path {
    Path::new(env!("CARGO_BIN_EXE_lender-matching"))
}

fn application() -> Vec<u8> {
    let pages = vec![
        Form::word().draw(FakePage::new()),
        certificate(FakePage::new(), &[("SAMPLE OWNER", "owner@example.com")]),
    ];
    FakePdf::new(pages).created(2026, 10, 21).to_bytes()
}

fn is_application(facts: &lender_matching_application::PdfFacts) -> bool {
    matches!(read(facts).document, Document::Application(_))
}

#[test]
fn the_worker_reads_documents_one_after_another() {
    let Some(library) = support::pdfium_library() else { return };
    let mut worker = PdfWorker::start(binary(), &["pdf-worker"], &library).expect("the worker starts");
    for _ in 0..3 {
        assert!(is_application(&worker.facts(&application(), ENOUGH).unwrap()));
    }
    assert_eq!(worker.facts(b"SAMPLE, not a PDF", ENOUGH).err(), Some(WorkerError::Read(ReadError::NotPdf)));
    assert!(is_application(&worker.facts(&application(), ENOUGH).unwrap()), "a refused document leaves it serving");
}

#[test]
fn a_timeout_stops_the_worker_and_the_next_document_starts_a_new_one() {
    let Some(library) = support::pdfium_library() else { return };
    let mut worker = PdfWorker::start(binary(), &["pdf-worker"], &library).unwrap();
    assert_eq!(worker.facts(&application(), Duration::ZERO).err(), Some(WorkerError::Timeout));
    assert!(is_application(&worker.facts(&application(), ENOUGH).unwrap()));
}

#[test]
fn a_worker_that_cannot_load_pdfium_says_so() {
    let missing = std::env::temp_dir().join("lender-matching-no-such-pdfium").join("libpdfium.so");
    assert_eq!(PdfWorker::start(binary(), &["pdf-worker"], &missing).err(), Some(WorkerError::NoEngine));
}

#[test]
fn a_process_that_breaks_the_protocol_is_reported_as_crashed() {
    let library = std::env::temp_dir().join("libpdfium.so");
    assert_eq!(PdfWorker::start(binary(), &["--version"], &library).err(), Some(WorkerError::Crashed));
}
