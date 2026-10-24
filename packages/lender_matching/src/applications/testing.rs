//! Fabricated application PDFs, and a reader that gives their page data without pdfium.

#[path = "../../application/tests/support/mod.rs"]
pub mod support;

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};

use lender_matching_application::pdf::ReadError;
use lender_matching_application::worker::WorkerError;
use lender_matching_application::{Glyph, PdfFacts, Rect, TextPage};
use support::form::{Canvas, Form, certificate_of};
use support::pdf::{FakePage, FakePdf};
use time::{Date, Month};

use super::{ApplicationRef, Applications, DataKey, Intake, ReadPdf};
use crate::store::Store;

/// Lays text out as the fabricated fonts do: each character half an em wide, its box one em tall.
pub struct ModelPage(TextPage);

impl ModelPage {
    fn new() -> ModelPage {
        ModelPage(TextPage { width: 612.0, height: 792.0, fonts: Vec::new(), glyphs: Vec::new(), image_cover: 0.0 })
    }
}

impl Canvas for ModelPage {
    fn text(mut self, font: &str, size: f32, x: f32, top: f32, text: &str) -> ModelPage {
        let font = match self.0.fonts.iter().position(|known| known == font) {
            Some(index) => index,
            None => {
                self.0.fonts.push(font.to_string());
                self.0.fonts.len() - 1
            }
        };
        for (i, ch) in text.chars().enumerate() {
            let x0 = x + size / 2.0 * i as f32;
            let rect = Rect { x0, top, x1: x0 + size / 2.0, bottom: top + size };
            self.0.glyphs.push(Glyph { ch, font: u16::try_from(font).unwrap(), size, rect });
        }
        self
    }
}

/// A fabricated document: the PDF's bytes and the page data pdfium reads from them.
pub struct Document {
    pub pdf: Vec<u8>,
    draw: Box<dyn Fn() -> PdfFacts + Send + Sync>,
}

impl Document {
    /// `pdf` with the page data of `other`, as another parser might read it.
    pub fn reading_as(pdf: Vec<u8>, other: Document) -> Document {
        Document { pdf, draw: other.draw }
    }
}

/// `form` on page 1 and, on page 2, a certificate of the envelope `envelope` (32 hexadecimal
/// digits). The PDF is created on `day` of October 2026, so two files of one form differ in
/// their bytes.
pub fn application(form: Form, envelope: &'static str, day: u8) -> Document {
    let signers = [("SAMPLE OWNER", "owner@example.com")];
    let pdf = FakePdf::new(vec![form.draw(FakePage::new()), certificate_of(FakePage::new(), envelope, &signers)])
        .created(2026, 10, day)
        .to_bytes();
    let created_on = Date::from_calendar_date(2026, Month::October, day).ok();
    let draw = move || PdfFacts {
        created_on,
        pages: vec![form.draw(ModelPage::new()).0, certificate_of(ModelPage::new(), envelope, &signers).0],
    };
    Document { pdf, draw: Box::new(draw) }
}

pub const ENVELOPE: &str = "0F8FAD5BD9CB469FA16570867728950E";
pub const OTHER_ENVELOPE: &str = "7C9E6679742540DE944BE07FC1F90AE7";

fn draw_contract<C: Canvas>(mut page: C) -> C {
    page = page.text("TimesNewRomanPS-BoldMT", 12.0, 40.0, 40.0, "RECEIVABLES PURCHASE AGREEMENT");
    for line in 0..10 {
        page = page.text("ArialMT", 9.0, 40.0, 80.0 + 12.0 * line as f32, "SAMPLE TERMS OF THE AGREEMENT ARE HERE");
    }
    page
}

/// A one-page Receivables Purchase Agreement.
pub fn contract() -> Document {
    let pdf = FakePdf::new(vec![draw_contract(FakePage::new())]).to_bytes();
    Document { pdf, draw: Box::new(|| PdfFacts { created_on: None, pages: vec![draw_contract(ModelPage::new()).0] }) }
}

pub const LEGAL_NAME: lender_matching_application::FieldId =
    lender_matching_application::FieldId::Business(lender_matching_application::fields::BusinessField::LegalName);

pub fn key() -> DataKey {
    DataKey::new([7; 32])
}

/// Applications over `store`, sealed with `key()`, reading fabricated documents.
pub fn service(store: &Arc<Store>) -> (Applications, Arc<FakeReader>) {
    let reader = Arc::new(FakeReader::default());
    (Applications::new(store.clone(), Arc::new(key()), reader.clone()), reader)
}

/// Uploads `form` as a new application by `by`.
pub fn upload(applications: &Applications, reader: &FakeReader, form: Form, by: i64) -> ApplicationRef {
    let pdf = reader.knows(application(form, ENVELOPE, 21));
    match applications.upload(&pdf, by).unwrap() {
        Intake::Stored { reference, .. } => reference,
        _ => panic!("not stored as a new application"),
    }
}

/// Gives each known document's page data, counting reads; other bytes are not a PDF.
#[derive(Default)]
pub struct FakeReader {
    documents: Mutex<Vec<Document>>,
    reads: AtomicUsize,
}

impl FakeReader {
    /// From now on, `document`'s bytes read as it says.
    pub fn knows(&self, document: Document) -> Vec<u8> {
        let pdf = document.pdf.clone();
        let mut documents = self.documents.lock().unwrap();
        documents.retain(|known| known.pdf != pdf);
        documents.push(document);
        pdf
    }

    pub fn reads(&self) -> usize {
        self.reads.load(Ordering::SeqCst)
    }
}

impl ReadPdf for FakeReader {
    fn facts(&self, pdf: &[u8]) -> Result<PdfFacts, WorkerError> {
        self.reads.fetch_add(1, Ordering::SeqCst);
        let documents = self.documents.lock().unwrap();
        let document = documents.iter().find(|document| document.pdf == pdf);
        document.map(|document| (document.draw)()).ok_or(WorkerError::Read(ReadError::NotPdf))
    }
}
