use std::collections::HashMap;
use std::fmt;
use std::io::Cursor;
use std::path::{Path, PathBuf};

use image::{ImageFormat, Rgba};
use pdfium_render::prelude::{
    PdfDocument, PdfDocumentMetadataTagType, PdfMatrix, PdfPage, PdfPageObject, PdfPageObjectCommon,
    PdfPageObjectsCommon, PdfPageRenderRotation, PdfRect, PdfRenderConfig, Pdfium, PdfiumError, PdfiumInternalError,
};
use serde::Serialize;
use time::{Date, Month};

use crate::page::{Glyph, PdfFacts, Rect, TextPage};

/// A larger document is refused before pdfium opens it.
pub const MAX_BYTES: usize = 64 << 20;
pub const MAX_PAGES: usize = 128;
/// Across all pages of one document.
pub const MAX_GLYPHS: usize = 1_000_000;
/// Form XObjects nested deeper than this are not searched for images.
const MAX_FORM_DEPTH: usize = 8;
/// The widest page image, in pixels.
pub const MAX_IMAGE_WIDTH: u32 = 3000;

/// pdfium, bound once per process. Its calls take `&mut self` because pdfium is not thread-safe.
pub struct PdfEngine {
    pdfium: Pdfium,
}

#[derive(Debug)]
pub enum EngineError {
    NotAbsolute(PathBuf),
    Bind(PathBuf),
}

impl fmt::Display for EngineError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EngineError::NotAbsolute(path) => write!(f, "the pdfium library path {} is not absolute", path.display()),
            EngineError::Bind(path) => write!(f, "cannot load pdfium from {}", path.display()),
        }
    }
}

/// Why a PDF gives no page data. A closed set that carries no document text.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ReadError {
    NotPdf,
    Encrypted,
    TooLarge,
    Engine,
    /// A page image asked for a page the document does not have.
    NoSuchPage,
}

/// Page `page` of a document drawn `width` pixels wide, its height in the page's proportions, with
/// each cover painted solid black over it.
pub struct PageImage {
    /// The displayed page's index, from 0.
    pub page: u16,
    pub width: u32,
    /// In points on the displayed page, as `Rect` measures.
    pub covers: Vec<Rect>,
}

impl PdfEngine {
    /// Binds the pdfium shared library at `library`, an absolute path; nothing else is searched.
    pub fn bind(library: &Path) -> Result<PdfEngine, EngineError> {
        if !library.is_absolute() {
            return Err(EngineError::NotAbsolute(library.to_path_buf()));
        }
        let bindings = Pdfium::bind_to_library(library).map_err(|_| EngineError::Bind(library.to_path_buf()))?;
        Ok(PdfEngine { pdfium: Pdfium::new(bindings) })
    }

    fn open<'a>(&'a self, bytes: &'a [u8]) -> Result<PdfDocument<'a>, ReadError> {
        if bytes.len() > MAX_BYTES {
            return Err(ReadError::TooLarge);
        }
        self.pdfium.load_pdf_from_byte_slice(bytes, None).map_err(|error| match error {
            PdfiumError::PdfiumLibraryInternalError(PdfiumInternalError::PasswordError)
            | PdfiumError::PdfiumLibraryInternalError(PdfiumInternalError::SecurityError) => ReadError::Encrypted,
            PdfiumError::PdfiumLibraryInternalError(PdfiumInternalError::FormatError)
            | PdfiumError::PdfiumLibraryInternalError(PdfiumInternalError::FileError) => ReadError::NotPdf,
            _ => ReadError::Engine,
        })
    }

    /// Opens `bytes` from memory and copies out every page's glyphs, fonts and image cover, and
    /// the info dictionary's creation date.
    pub fn facts(&mut self, bytes: &[u8]) -> Result<PdfFacts, ReadError> {
        let document = self.open(bytes)?;
        let created_on =
            document.metadata().get(PdfDocumentMetadataTagType::CreationDate).and_then(|tag| pdf_date(tag.value()));
        if usize::try_from(document.pages().len()).map_or(true, |count| count > MAX_PAGES) {
            return Err(ReadError::TooLarge);
        }
        let mut glyphs = 0;
        let mut pages = Vec::new();
        for page in document.pages().iter() {
            pages.push(text_page(&page, &mut glyphs)?);
        }
        Ok(PdfFacts { created_on, pages })
    }

    /// The page as a PNG, with every cover painted in the bitmap itself. A width of 0 or over
    /// `MAX_IMAGE_WIDTH` is `TooLarge`.
    pub fn page_png(&mut self, bytes: &[u8], request: &PageImage) -> Result<Vec<u8>, ReadError> {
        if request.width == 0 || request.width > MAX_IMAGE_WIDTH {
            return Err(ReadError::TooLarge);
        }
        let document = self.open(bytes)?;
        let page = document.pages().get(request.page.into()).map_err(|_| ReadError::NoSuchPage)?;
        let (points_wide, points_high) = View::of(&page)?.size();
        let width = i32::try_from(request.width).map_err(|_| ReadError::TooLarge)?;
        let bitmap =
            page.render_with_config(&PdfRenderConfig::new().set_target_width(width)).map_err(|_| ReadError::Engine)?;
        let mut image = bitmap.as_image().map_err(|_| ReadError::Engine)?.into_rgba8();
        let (w, h) = image.dimensions();
        let (sx, sy) = (w as f32 / points_wide, h as f32 / points_high);
        let pixel = |points: f32, scale: f32, limit: u32| (points * scale).clamp(0.0, limit as f32);
        for cover in &request.covers {
            let (x0, x1) = (pixel(cover.x0, sx, w).floor() as u32, pixel(cover.x1, sx, w).ceil() as u32);
            let (y0, y1) = (pixel(cover.top, sy, h).floor() as u32, pixel(cover.bottom, sy, h).ceil() as u32);
            for y in y0..y1 {
                for x in x0..x1 {
                    image.put_pixel(x, y, Rgba([0, 0, 0, 255]));
                }
            }
        }
        let mut png = Vec::new();
        image.write_to(&mut Cursor::new(&mut png), ImageFormat::Png).map_err(|_| ReadError::Engine)?;
        Ok(png)
    }
}

/// `D:YYYYMMDD...`, the date as written, in its own time zone.
fn pdf_date(value: &str) -> Option<Date> {
    let digits = value.strip_prefix("D:").unwrap_or(value);
    let part = |range: std::ops::Range<usize>| digits.get(range).filter(|p| p.bytes().all(|b| b.is_ascii_digit()));
    let year = part(0..4)?.parse().ok()?;
    let month = Month::try_from(part(4..6)?.parse::<u8>().ok()?).ok()?;
    Date::from_calendar_date(year, month, part(6..8)?.parse().ok()?).ok()
}

/// Maps PDF user space to the displayed page: after the crop box and the page's clockwise
/// rotation, origin at the top-left, y down.
struct View {
    crop: [f32; 4],
    quarter_turns: u8,
}

impl View {
    fn of(page: &PdfPage) -> Result<View, ReadError> {
        let boundaries = page.boundaries();
        let crop = boundaries.crop().or_else(|_| boundaries.media()).map_err(|_| ReadError::Engine)?.bounds;
        let quarter_turns = match page.rotation().map_err(|_| ReadError::Engine)? {
            PdfPageRenderRotation::None => 0,
            PdfPageRenderRotation::Degrees90 => 1,
            PdfPageRenderRotation::Degrees180 => 2,
            PdfPageRenderRotation::Degrees270 => 3,
        };
        Ok(View { crop: [crop.left().value, crop.bottom().value, crop.right().value, crop.top().value], quarter_turns })
    }

    fn size(&self) -> (f32, f32) {
        let [left, bottom, right, top] = self.crop;
        if self.quarter_turns.is_multiple_of(2) { (right - left, top - bottom) } else { (top - bottom, right - left) }
    }

    fn point(&self, x: f32, y: f32) -> (f32, f32) {
        let [left, bottom, right, top] = self.crop;
        match self.quarter_turns {
            0 => (x - left, top - y),
            1 => (y - bottom, x - left),
            2 => (right - x, y - bottom),
            _ => (top - y, right - x),
        }
    }

    fn rect(&self, corners: impl IntoIterator<Item = (f32, f32)>) -> Rect {
        let points: Vec<(f32, f32)> = corners.into_iter().map(|(x, y)| self.point(x, y)).collect();
        let fold = |pick: fn(&(f32, f32)) -> f32, min: bool| {
            points
                .iter()
                .map(pick)
                .fold(if min { f32::MAX } else { f32::MIN }, |a, b| if min { a.min(b) } else { a.max(b) })
        };
        Rect {
            x0: fold(|p| p.0, true),
            top: fold(|p| p.1, true),
            x1: fold(|p| p.0, false),
            bottom: fold(|p| p.1, false),
        }
    }

    fn of_pdf_rect(&self, rect: PdfRect) -> Rect {
        let (left, bottom, right, top) = (rect.left().value, rect.bottom().value, rect.right().value, rect.top().value);
        self.rect([(left, bottom), (right, top)])
    }
}

/// A font name without its subset tag: `ABCDEF+Calibri` is `Calibri`.
fn base_font(name: &str) -> &str {
    match name.split_once('+') {
        Some((tag, rest)) if tag.len() == 6 && tag.bytes().all(|b| b.is_ascii_uppercase()) => rest,
        _ => name,
    }
}

fn text_page(page: &PdfPage, glyph_total: &mut usize) -> Result<TextPage, ReadError> {
    let view = View::of(page)?;
    let (width, height) = view.size();
    let text = page.text().map_err(|_| ReadError::Engine)?;
    let mut fonts: Vec<String> = Vec::new();
    let mut font_index: HashMap<String, u16> = HashMap::new();
    let mut glyphs = Vec::new();
    for ch in text.chars().iter() {
        if ch.is_generated().unwrap_or(false) {
            continue;
        }
        let printed = match ch.unicode_char() {
            Some(c) if c.is_whitespace() => ' ',
            Some(c) if !c.is_control() && c != '\u{FFFE}' && c != '\u{FFFF}' => c,
            _ => '\u{FFFD}',
        };
        let name = base_font(&ch.font_name()).to_string();
        let font = match font_index.get(&name) {
            Some(index) => *index,
            None => {
                let index = u16::try_from(fonts.len()).map_err(|_| ReadError::TooLarge)?;
                fonts.push(name.clone());
                font_index.insert(name, index);
                index
            }
        };
        let rect = view.of_pdf_rect(ch.loose_bounds().map_err(|_| ReadError::Engine)?);
        glyphs.push(Glyph { ch: printed, font, size: ch.scaled_font_size().value, rect });
        *glyph_total += 1;
        if *glyph_total > MAX_GLYPHS {
            return Err(ReadError::TooLarge);
        }
    }
    let mut cover: f32 = 0.0;
    let area = (width * height).max(1.0);
    let mut largest = |rect: Rect| {
        let w = (rect.x1.min(width) - rect.x0.max(0.0)).max(0.0);
        let h = (rect.bottom.min(height) - rect.top.max(0.0)).max(0.0);
        cover = cover.max(w * h / area);
    };
    images(page.objects().iter(), &[], 0, &view, &mut largest);
    Ok(TextPage { width, height, fonts, glyphs, image_cover: cover.min(1.0) })
}

/// Every image's displayed box. `outer` holds the matrices of the form XObjects around these
/// objects, innermost first.
fn images<'a>(
    objects: impl Iterator<Item = PdfPageObject<'a>>,
    outer: &[PdfMatrix],
    depth: usize,
    view: &View,
    found: &mut dyn FnMut(Rect),
) {
    for object in objects {
        match &object {
            PdfPageObject::Image(image) => {
                let Ok(bounds) = image.bounds() else { continue };
                let corners = [
                    (bounds.x1(), bounds.y1()),
                    (bounds.x2(), bounds.y2()),
                    (bounds.x3(), bounds.y3()),
                    (bounds.x4(), bounds.y4()),
                ]
                .map(|(x, y)| outer.iter().fold((x, y), |(x, y), matrix| matrix.apply_to_points(x, y)))
                .map(|(x, y)| (x.value, y.value));
                found(view.rect(corners));
            }
            PdfPageObject::XObjectForm(form) if depth < MAX_FORM_DEPTH => {
                let Ok(matrix) = form.matrix() else { continue };
                let chain: Vec<PdfMatrix> = std::iter::once(matrix).chain(outer.iter().copied()).collect();
                images(form.iter(), &chain, depth + 1, view, found);
            }
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use pdfium_render::prelude::PdfRenderConfig;
    use time::macros::date;

    use super::*;
    use crate::extract::{Document, RefusalReason, read};
    use crate::fields::{BusinessField, FieldId};
    use crate::support::form::{Canvas, Form, certificate, expected, pdfescape};
    use crate::support::pdf::{FakePage, FakePdf};
    use crate::support::pdfium_library;

    /// pdfium binds once per process and its engine stays on one thread, so one test runs every
    /// check against it.
    #[test]
    fn pdfium_reads_fabricated_pdfs() {
        let Some(library) = pdfium_library() else { return };
        let mut engine = PdfEngine::bind(&library).expect("PDFIUM_LIBRARY loads");
        a_fabricated_application_reads_every_field(&mut engine);
        a_value_over_the_next_label_reads_whole_in_its_own_field(&mut engine);
        glyphs_keep_their_font_size_and_loose_box(&mut engine);
        coordinates_follow_the_crop_box_and_the_rotation_pdfium_displays(&engine);
        image_cover_counts_the_largest_image_also_inside_a_form(&mut engine);
        what_is_not_a_readable_pdf_is_refused_by_kind(&mut engine);
        a_contract_is_refused(&mut engine);
    }

    fn application(form: &Form) -> Vec<u8> {
        let pages =
            vec![form.draw(FakePage::new()), certificate(FakePage::new(), &[("SAMPLE OWNER", "owner@example.com")])];
        FakePdf::new(pages).created(2026, 10, 21).to_bytes()
    }

    fn a_fabricated_application_reads_every_field(engine: &mut PdfEngine) {
        for (form, layout) in [(Form::word(), "word"), (Form { layout: pdfescape(), ..Form::word() }, "pdfescape")] {
            let facts = engine.facts(&application(&form)).expect("pdfium reads a fabricated PDF");
            assert_eq!(facts.created_on, Some(date!(2026 - 10 - 21)));
            let reading = read(&facts);
            let Document::Application(found) = &reading.document else {
                panic!("{layout} is not read as an application")
            };
            assert_eq!(found.layout.as_str(), layout);
            for (field, text) in expected() {
                let value = found.fields.get(field).value().map(|value| value.canonical());
                assert_eq!(value.as_deref(), Some(text), "{layout} {field}: {:?}", found.fields.get(field).outcome());
            }
            assert!(found.unplaced.is_empty(), "{layout}: {} unplaced", found.unplaced.len());
            let signers = &reading.certificate.as_ref().expect("a certificate").signers;
            assert_eq!(signers.len(), 1);
        }
    }

    fn a_value_over_the_next_label_reads_whole_in_its_own_field(engine: &mut PdfEngine) {
        let long = "CONTOSO FABRIKAM NORTHWIND HOLDINGS OF SAMPLE";
        let form = Form::word().set(FieldId::Business(BusinessField::LegalName), long);
        let reading = read(&engine.facts(&application(&form)).unwrap());
        let Document::Application(found) = &reading.document else { panic!("not read as an application") };
        let text = |field| found.fields.get(FieldId::Business(field)).value().map(|value| value.canonical());
        assert_eq!(text(BusinessField::LegalName).as_deref(), Some(long));
        assert_eq!(text(BusinessField::Dba).as_deref(), Some("NORTHWIND"));
        assert!(found.unplaced.is_empty(), "{} unplaced", found.unplaced.len());
    }

    fn glyphs_keep_their_font_size_and_loose_box(engine: &mut PdfEngine) {
        let page =
            FakePage::new().text("ABCDEF+Calibri", 11.0, 100.0, 200.0, "City").text("ArialMT", 9.0, 140.0, 201.6, "X");
        let facts = engine.facts(&FakePdf::new(vec![page]).to_bytes()).unwrap();
        let page = &facts.pages[0];
        assert_eq!((page.width, page.height), (612.0, 792.0));
        let read: Vec<(char, &str, f32)> =
            page.glyphs.iter().map(|glyph| (glyph.ch, page.font_name(glyph), glyph.size)).collect();
        assert_eq!(
            read,
            [
                ('C', "Calibri", 11.0),
                ('i', "Calibri", 11.0),
                ('t', "Calibri", 11.0),
                ('y', "Calibri", 11.0),
                ('X', "ArialMT", 9.0)
            ]
        );
        let origins: Vec<f32> = page.glyphs[..4].iter().map(|glyph| glyph.rect.x0).collect();
        assert_eq!(origins, [100.0, 105.5, 111.0, 116.5], "each origin advances by the font's width");
        let first = page.glyphs[0].rect;
        for (got, want) in [(first.top, 200.0), (first.bottom, 211.0)] {
            assert!((got - want).abs() < 0.05, "{got} is not {want}");
        }
        assert!(first.x1 > first.x0, "the box's width is the drawn glyph's, which the test fonts do not fix");
        assert_eq!(facts.created_on, None);
    }

    /// The dark pixels pdfium renders for one black box, in displayed points.
    fn rendered_box(engine: &PdfEngine, bytes: &[u8], points_wide: f32) -> Rect {
        let document = engine.pdfium.load_pdf_from_byte_slice(bytes, None).unwrap();
        let page = document.pages().get(0).unwrap();
        let bitmap = page.render_with_config(&PdfRenderConfig::new().set_target_width(1000)).unwrap();
        let (w, h) = (bitmap.width() as usize, bitmap.height() as usize);
        let pixels = bitmap.as_raw_bytes();
        let scale = points_wide / w as f32;
        let dark: Vec<(usize, usize)> =
            (0..h).flat_map(|y| (0..w).map(move |x| (x, y))).filter(|(x, y)| pixels[(y * w + x) * 4] < 64).collect();
        let (x0, x1) = (dark.iter().map(|p| p.0).min().unwrap(), dark.iter().map(|p| p.0).max().unwrap() + 1);
        let (y0, y1) = (dark.iter().map(|p| p.1).min().unwrap(), dark.iter().map(|p| p.1).max().unwrap() + 1);
        Rect { x0: x0 as f32 * scale, top: y0 as f32 * scale, x1: x1 as f32 * scale, bottom: y1 as f32 * scale }
    }

    fn coordinates_follow_the_crop_box_and_the_rotation_pdfium_displays(engine: &PdfEngine) {
        for rotate in [0, 90, 180, 270] {
            let page =
                FakePage::new().crop([20.0, 30.0, 520.0, 730.0]).rotate(rotate).filled_box([100.0, 500.0, 80.0, 40.0]);
            let bytes = FakePdf::new(vec![page]).to_bytes();
            let document = engine.pdfium.load_pdf_from_byte_slice(&bytes, None).unwrap();
            let view = View::of(&document.pages().get(0).unwrap()).unwrap();
            let mapped = view.rect([(100.0, 500.0), (180.0, 540.0)]);
            let rendered = rendered_box(engine, &bytes, view.size().0);
            for (got, want) in [
                (mapped.x0, rendered.x0),
                (mapped.top, rendered.top),
                (mapped.x1, rendered.x1),
                (mapped.bottom, rendered.bottom),
            ] {
                assert!((got - want).abs() < 1.5, "rotate {rotate}: {mapped:?} against {rendered:?}");
            }
            let expected_size = if rotate % 180 == 0 { (500.0, 700.0) } else { (700.0, 500.0) };
            assert_eq!(view.size(), expected_size);
        }
    }

    fn image_cover_counts_the_largest_image_also_inside_a_form(engine: &mut PdfEngine) {
        let mut cover = |page: FakePage| engine_cover(engine, page);
        assert_eq!(cover(FakePage::new()), 0.0);
        let direct = cover(FakePage::new().image([612.0 * 0.9, 0.0, 0.0, 792.0, 0.0, 0.0]));
        assert!((direct - 0.9).abs() < 0.01, "{direct}");
        let nested = cover(
            FakePage::new()
                .image_in_form([0.5, 0.0, 0.0, 0.5, 0.0, 0.0], [612.0 * 1.8, 0.0, 0.0, 792.0 * 2.0, 0.0, 0.0]),
        );
        assert!((nested - 0.9).abs() < 0.01, "{nested}");
        let small = cover(FakePage::new().image([100.0, 0.0, 0.0, 100.0, 50.0, 50.0]));
        assert!((small - 10_000.0 / (612.0 * 792.0)).abs() < 0.001, "{small}");
    }

    fn engine_cover(engine: &mut PdfEngine, page: FakePage) -> f32 {
        engine.facts(&FakePdf::new(vec![page]).to_bytes()).unwrap().pages[0].image_cover
    }

    fn what_is_not_a_readable_pdf_is_refused_by_kind(engine: &mut PdfEngine) {
        assert_eq!(engine.facts(b"SAMPLE, not a PDF").err(), Some(ReadError::NotPdf));
        let pages: Vec<FakePage> = (0..=MAX_PAGES).map(|_| FakePage::new()).collect();
        assert_eq!(engine.facts(&FakePdf::new(pages).to_bytes()).err(), Some(ReadError::TooLarge));
        assert_eq!(engine.facts(&vec![b' '; MAX_BYTES + 1]).err(), Some(ReadError::TooLarge));
    }

    fn a_contract_is_refused(engine: &mut PdfEngine) {
        let mut page =
            FakePage::new().text("TimesNewRomanPS-BoldMT", 12.0, 40.0, 40.0, "RECEIVABLES PURCHASE AGREEMENT");
        for line in 0..10 {
            page = page.text("ArialMT", 9.0, 40.0, 80.0 + 12.0 * line as f32, "SAMPLE TERMS OF THE AGREEMENT ARE HERE");
        }
        let reading = read(&engine.facts(&FakePdf::new(vec![page]).to_bytes()).unwrap());
        assert!(matches!(reading.document, Document::Refused(RefusalReason::Contract)));
    }

    #[test]
    fn dates_and_font_names_parse_as_written() {
        assert_eq!(pdf_date("D:20261020093000-07'00'"), Some(date!(2026 - 10 - 20)));
        assert_eq!(pdf_date("D:2026"), None);
        assert_eq!(pdf_date("D:20261320"), None);
        assert_eq!(base_font("ABCDEF+Calibri-Bold"), "Calibri-Bold");
        assert_eq!(base_font("Calibri"), "Calibri");
        assert_eq!(base_font("abc+Calibri"), "abc+Calibri");
    }
}
