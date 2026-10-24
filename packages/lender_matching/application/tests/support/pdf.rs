use pdf_writer::types::FontFlags;
use pdf_writer::{Content, Date, Finish, Name, Pdf, Rect, Ref, Str};

use super::form::Canvas;

/// Every test font is a non-embedded TrueType font with these metrics, so each character's origin
/// advances half an em, and pdfium's loose box for it runs 0.8 em above the baseline and 0.2 em
/// below. The box's width is that of the glyph pdfium draws from a substitute font.
const ASCENT: f32 = 800.0;
const DESCENT: f32 = -200.0;
const ADVANCE: f32 = 500.0;

/// One fabricated page. `text` takes a top measured from the top edge, as the page model does;
/// the other methods take PDF user space, origin at the bottom-left.
pub struct FakePage {
    pub width: f32,
    pub height: f32,
    rotate: i32,
    crop: Option<[f32; 4]>,
    texts: Vec<(String, f32, f32, f32, String)>,
    images: Vec<Image>,
    boxes: Vec<[f32; 4]>,
}

enum Image {
    /// Drawn with this matrix.
    Direct([f32; 6]),
    /// Drawn with `image` inside a form XObject drawn with `form`.
    InForm { form: [f32; 6], image: [f32; 6] },
}

impl FakePage {
    pub fn new() -> FakePage {
        FakePage {
            width: 612.0,
            height: 792.0,
            rotate: 0,
            crop: None,
            texts: Vec::new(),
            images: Vec::new(),
            boxes: Vec::new(),
        }
    }

    pub fn rotate(mut self, degrees: i32) -> FakePage {
        self.rotate = degrees;
        self
    }

    /// The crop box as left, bottom, right, top.
    pub fn crop(mut self, crop: [f32; 4]) -> FakePage {
        self.crop = Some(crop);
        self
    }

    pub fn text_at_baseline(mut self, font: &str, size: f32, x: f32, baseline: f32, text: &str) -> FakePage {
        self.texts.push((font.to_string(), size, x, baseline, text.to_string()));
        self
    }

    /// A one-pixel gray image stretched by `matrix`.
    pub fn image(mut self, matrix: [f32; 6]) -> FakePage {
        self.images.push(Image::Direct(matrix));
        self
    }

    pub fn image_in_form(mut self, form: [f32; 6], image: [f32; 6]) -> FakePage {
        self.images.push(Image::InForm { form, image });
        self
    }

    /// A black rectangle: left, bottom, width, height.
    pub fn filled_box(mut self, rect: [f32; 4]) -> FakePage {
        self.boxes.push(rect);
        self
    }
}

impl Canvas for FakePage {
    fn text(self, font: &str, size: f32, x: f32, top: f32, text: &str) -> FakePage {
        let baseline = self.height - top - ASCENT / 1000.0 * size;
        self.text_at_baseline(font, size, x, baseline, text)
    }
}

pub struct FakePdf {
    pages: Vec<FakePage>,
    created: Option<(u16, u8, u8)>,
}

impl FakePdf {
    pub fn new(pages: Vec<FakePage>) -> FakePdf {
        FakePdf { pages, created: None }
    }

    pub fn created(mut self, year: u16, month: u8, day: u8) -> FakePdf {
        self.created = Some((year, month, day));
        self
    }

    pub fn to_bytes(&self) -> Vec<u8> {
        let mut next = 0;
        let mut alloc = move || {
            next += 1;
            Ref::new(next)
        };
        let mut pdf = Pdf::new();
        let catalog = alloc();
        let tree = alloc();
        let image = alloc();
        let mut fonts: Vec<(String, Ref, Ref)> = Vec::new();
        for page in &self.pages {
            for (font, ..) in &page.texts {
                if !fonts.iter().any(|(name, ..)| name == font) {
                    fonts.push((font.clone(), alloc(), alloc()));
                }
            }
        }
        let page_refs: Vec<(Ref, Ref)> = self.pages.iter().map(|_| (alloc(), alloc())).collect();
        pdf.catalog(catalog).pages(tree);
        pdf.pages(tree).kids(page_refs.iter().map(|(page, _)| *page)).count(self.pages.len() as i32);
        for (name, font, descriptor) in &fonts {
            let mut dict = pdf.indirect(*font).dict();
            dict.pair(Name(b"Type"), Name(b"Font"));
            dict.pair(Name(b"Subtype"), Name(b"TrueType"));
            dict.pair(Name(b"BaseFont"), Name(name.as_bytes()));
            dict.pair(Name(b"FirstChar"), 32);
            dict.pair(Name(b"LastChar"), 126);
            dict.insert(Name(b"Widths")).array().items(std::iter::repeat_n(ADVANCE, 95));
            dict.pair(Name(b"FontDescriptor"), *descriptor);
            dict.pair(Name(b"Encoding"), Name(b"WinAnsiEncoding"));
            dict.finish();
            pdf.font_descriptor(*descriptor)
                .name(Name(name.as_bytes()))
                .flags(FontFlags::NON_SYMBOLIC)
                .bbox(Rect::new(0.0, DESCENT, ADVANCE, ASCENT))
                .italic_angle(0.0)
                .ascent(ASCENT)
                .descent(DESCENT)
                .cap_height(700.0)
                .stem_v(80.0);
        }
        let mut gray = pdf.image_xobject(image, &[128]);
        gray.width(1).height(1).bits_per_component(8);
        gray.color_space().device_gray();
        gray.finish();

        for (page, (page_ref, content_ref)) in self.pages.iter().zip(&page_refs) {
            let mut content = Content::new();
            let mut forms = Vec::new();
            for rect in &page.boxes {
                content.set_fill_gray(0.0).rect(rect[0], rect[1], rect[2], rect[3]).fill_nonzero();
            }
            for drawn in &page.images {
                content.save_state();
                match drawn {
                    Image::Direct(matrix) => {
                        content.transform(*matrix).x_object(Name(b"Im1"));
                    }
                    Image::InForm { form, image } => {
                        let name = format!("Fx{}", forms.len() + 1);
                        content.transform(*form).x_object(Name(name.as_bytes()));
                        forms.push((name, alloc(), *image));
                    }
                }
                content.restore_state();
            }
            for (font, size, x, baseline, text) in &page.texts {
                let index = fonts.iter().position(|(name, ..)| name == font).expect("collected above");
                let resource = format!("F{}", index + 1);
                content
                    .begin_text()
                    .set_font(Name(resource.as_bytes()), *size)
                    .set_text_matrix([1.0, 0.0, 0.0, 1.0, *x, *baseline])
                    .show(Str(text.as_bytes()))
                    .end_text();
            }
            pdf.stream(*content_ref, &content.finish());
            for (_, form_ref, matrix) in &forms {
                let mut inner = Content::new();
                inner.save_state().transform(*matrix).x_object(Name(b"Im1")).restore_state();
                let inner = inner.finish();
                let mut form = pdf.form_xobject(*form_ref, &inner);
                form.bbox(Rect::new(0.0, 0.0, 2.0 * page.width, 2.0 * page.height));
                form.resources().x_objects().pair(Name(b"Im1"), image);
                form.finish();
            }

            let mut writer = pdf.page(*page_ref);
            writer.media_box(Rect::new(0.0, 0.0, page.width, page.height)).parent(tree).contents(*content_ref);
            if let Some([left, bottom, right, top]) = page.crop {
                writer.crop_box(Rect::new(left, bottom, right, top));
            }
            if page.rotate != 0 {
                writer.rotate(page.rotate);
            }
            let mut resources = writer.resources();
            let mut font_dict = resources.fonts();
            for (index, (_, font, _)) in fonts.iter().enumerate() {
                font_dict.pair(Name(format!("F{}", index + 1).as_bytes()), *font);
            }
            font_dict.finish();
            let mut objects = resources.x_objects();
            objects.pair(Name(b"Im1"), image);
            for (name, form_ref, _) in &forms {
                objects.pair(Name(name.as_bytes()), *form_ref);
            }
        }
        if let Some((year, month, day)) = self.created {
            pdf.document_info(alloc()).creation_date(Date::new(year).month(month).day(day));
        }
        pdf.finish()
    }
}
