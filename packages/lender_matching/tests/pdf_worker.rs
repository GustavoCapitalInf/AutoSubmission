#[path = "../application/tests/support/mod.rs"]
mod support;

use std::path::Path;
use std::time::Duration;

use lender_matching_application::Rect;
use lender_matching_application::extract::{Document, read};
use lender_matching_application::pdf::{PageImage, ReadError};
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

fn decode(png: &[u8]) -> image::RgbaImage {
    image::load_from_memory_with_format(png, image::ImageFormat::Png).expect("a PNG").into_rgba8()
}

/// The pixels of `rect` in a 2-pixels-per-point image, shrunk by a pixel against rounding.
fn pixels<'a>(image: &'a image::RgbaImage, rect: &Rect) -> impl Iterator<Item = &'a image::Rgba<u8>> {
    let (x0, x1) = ((rect.x0 * 2.0).ceil() as u32 + 1, (rect.x1 * 2.0).floor() as u32 - 1);
    let (y0, y1) = ((rect.top * 2.0).ceil() as u32 + 1, (rect.bottom * 2.0).floor() as u32 - 1);
    (y0..y1).flat_map(move |y| (x0..x1).map(move |x| image.get_pixel(x, y)))
}

#[test]
fn a_page_image_has_the_identity_fields_painted_over_in_its_pixels() {
    let Some(library) = support::pdfium_library() else { return };
    let mut worker = PdfWorker::start(binary(), &["pdf-worker"], &library).unwrap();
    let pdf = application();
    let reading = read(&worker.facts(&pdf, ENOUGH).unwrap());
    let covers = reading.masked_covers().expect("every masked field has a region");
    let mut render = |covers: Vec<Rect>| {
        decode(&worker.page_png(&pdf, &PageImage { page: 0, width: 1224, covers }, ENOUGH).unwrap())
    };
    let plain = render(Vec::new());
    let covered = render(covers.clone());
    assert_eq!(covered.dimensions(), (1224, 1584));
    let black = image::Rgba([0, 0, 0, 255]);
    let Document::Application(form) = &reading.document else { panic!("an application") };
    for (field, value) in form.fields.iter().filter(|(field, _)| field.spec().masked) {
        let value = value.evidence().expect("a value").rect;
        assert!(pixels(&plain, &value).any(|pixel| pixel[0] < 128), "{field} shows text without covers");
        assert!(pixels(&covered, &value).all(|pixel| *pixel == black), "{field} is painted over");
    }
    let inside = |x: u32, y: u32| {
        let (x, y) = (x as f32 / 2.0, y as f32 / 2.0);
        covers.iter().any(|c| x >= c.x0 - 1.0 && x <= c.x1 + 1.0 && y >= c.top - 1.0 && y <= c.bottom + 1.0)
    };
    let outside_differs =
        plain.enumerate_pixels().filter(|(x, y, pixel)| !inside(*x, *y) && covered.get_pixel(*x, *y) != *pixel).count();
    assert_eq!(outside_differs, 0, "nothing outside the covers changes");
    assert!(plain.pixels().any(|pixel| pixel[0] < 128) && covered.pixels().any(|pixel| pixel[0] > 128));

    let missing = PageImage { page: 9, width: 100, covers: Vec::new() };
    assert_eq!(worker.page_png(&pdf, &missing, ENOUGH).err(), Some(WorkerError::Read(ReadError::NoSuchPage)));
    let wide = PageImage { page: 0, width: 0, covers: Vec::new() };
    assert_eq!(worker.page_png(&pdf, &wide, ENOUGH).err(), Some(WorkerError::Read(ReadError::TooLarge)));
    assert!(is_application(&worker.facts(&pdf, ENOUGH).unwrap()), "the worker still reads after a refusal");
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
