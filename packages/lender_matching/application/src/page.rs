use time::Date;

use crate::values::Word;

/// A box in PDF points on the displayed page, after the crop box and rotation: origin at the
/// top-left, y growing downward.
#[derive(Clone, Copy, PartialEq, Debug)]
pub struct Rect {
    pub x0: f32,
    pub top: f32,
    pub x1: f32,
    pub bottom: f32,
}

impl Rect {
    pub fn union(self, other: Rect) -> Rect {
        Rect {
            x0: self.x0.min(other.x0),
            top: self.top.min(other.top),
            x1: self.x1.max(other.x1),
            bottom: self.bottom.max(other.bottom),
        }
    }

    pub fn center_x(self) -> f32 {
        (self.x0 + self.x1) / 2.0
    }

    fn center_y(self) -> f32 {
        (self.top + self.bottom) / 2.0
    }
}

/// What reading a PDF needs from it, as owned data with no engine handle.
pub struct PdfFacts {
    /// The date the info dictionary's CreationDate names, in its own time zone.
    pub created_on: Option<Date>,
    pub pages: Vec<TextPage>,
}

pub struct TextPage {
    pub width: f32,
    pub height: f32,
    /// Base font names without a subset tag.
    pub fonts: Vec<String>,
    /// In content order, which is not reading order.
    pub glyphs: Vec<Glyph>,
    /// The largest share of the page one image covers, 0 to 1.
    pub image_cover: f32,
}

pub struct Glyph {
    /// U+FFFD where the PDF maps the glyph to no character.
    pub ch: char,
    /// An index into `TextPage::fonts`.
    pub font: u16,
    pub size: f32,
    /// The engine's loose box: from the origin, the font's ascent and descent, and the drawn
    /// glyph's width, which can exceed the advance to the next glyph.
    pub rect: Rect,
}

impl TextPage {
    pub fn font_name(&self, glyph: &Glyph) -> &str {
        self.fonts.get(usize::from(glyph.font)).map_or("", String::as_str)
    }

    pub fn text_chars(&self) -> usize {
        self.glyphs.iter().filter(|glyph| !glyph.ch.is_whitespace()).count()
    }
}

/// A gap wider than this share of the font size separates two words.
const WORD_GAP: f32 = 0.25;
/// Glyphs whose vertical centers lie within this share of the first one's size share a line.
const LINE_TOLERANCE: f32 = 0.35;

/// The page's glyphs in reading order: lines top to bottom, each left to right.
pub(crate) struct ReadingOrder<'a> {
    pub page: &'a TextPage,
    /// Glyph indices.
    pub order: Vec<usize>,
    /// The line of each position in `order`.
    pub line: Vec<usize>,
}

impl<'a> ReadingOrder<'a> {
    pub fn new(page: &'a TextPage) -> ReadingOrder<'a> {
        let glyphs = &page.glyphs;
        let mut by_height: Vec<usize> = (0..glyphs.len()).collect();
        by_height.sort_by(|a, b| {
            let (a, b) = (glyphs[*a].rect, glyphs[*b].rect);
            a.center_y().total_cmp(&b.center_y()).then(a.x0.total_cmp(&b.x0))
        });
        let mut lines: Vec<Vec<usize>> = Vec::new();
        let mut anchor: Option<(f32, f32)> = None;
        for index in by_height {
            let glyph = &glyphs[index];
            match anchor {
                Some((center, size)) if (glyph.rect.center_y() - center).abs() <= LINE_TOLERANCE * size => {
                    lines.last_mut().expect("an anchor has a line").push(index);
                }
                _ => {
                    anchor = Some((glyph.rect.center_y(), glyph.size.max(1.0)));
                    lines.push(vec![index]);
                }
            }
        }
        let mut order = Vec::with_capacity(glyphs.len());
        let mut line = Vec::with_capacity(glyphs.len());
        for (number, mut members) in lines.into_iter().enumerate() {
            members.sort_by(|a, b| glyphs[*a].rect.x0.total_cmp(&glyphs[*b].rect.x0));
            line.extend(std::iter::repeat_n(number, members.len()));
            order.extend(members);
        }
        ReadingOrder { page, order, line }
    }

    pub fn glyph(&self, at: usize) -> &'a Glyph {
        &self.page.glyphs[self.order[at]]
    }

    /// Whether a word may start at `at`: a line start, or after a space, a gap or punctuation.
    pub fn starts_word(&self, at: usize) -> bool {
        let glyph = self.glyph(at);
        if glyph.ch.is_whitespace() {
            return false;
        }
        if at == 0 || self.line[at - 1] != self.line[at] {
            return true;
        }
        let previous = self.glyph(at - 1);
        previous.ch.is_whitespace()
            || !previous.ch.is_alphanumeric()
            || glyph.rect.x0 - previous.rect.x1 > WORD_GAP * glyph.size
    }

    /// The lines as runs of positions in `order`.
    pub fn lines(&self) -> Vec<std::ops::Range<usize>> {
        let mut runs = Vec::new();
        let mut start = 0;
        for at in 1..=self.order.len() {
            if at == self.order.len() || self.line[at] != self.line[start] {
                if start < at {
                    runs.push(start..at);
                }
                start = at;
            }
        }
        runs
    }
}

/// Words from glyphs given in reading order. A new line, a wide gap, or a space glyph between two
/// of them in reading order ends a word, whether or not the space is among `positions`: a loose
/// box can be wider than the glyph's advance, so a gap alone can hide a typed space.
pub(crate) fn words(order: &ReadingOrder, positions: &[usize]) -> Vec<Word> {
    let mut words: Vec<Word> = Vec::new();
    let mut previous: Option<usize> = None;
    for &at in positions {
        let glyph = order.glyph(at);
        if glyph.ch.is_whitespace() {
            previous = None;
            continue;
        }
        let joins = previous.is_some_and(|before| {
            let before_glyph = order.glyph(before);
            order.line[before] == order.line[at]
                && (before + 1..at).all(|between| !order.glyph(between).ch.is_whitespace())
                && glyph.rect.x0 - before_glyph.rect.x1 <= WORD_GAP * glyph.size
        });
        match words.last_mut() {
            Some(word) if joins => {
                word.text.push(glyph.ch);
                word.x1 = glyph.rect.x1;
            }
            _ => words.push(Word { text: glyph.ch.to_string(), x0: glyph.rect.x0, x1: glyph.rect.x1 }),
        }
        previous = Some(at);
    }
    words
}

#[cfg(test)]
pub(crate) mod build {
    use super::*;

    /// Lays text out as a test font would: each character 0.5 em wide, the box one em tall.
    pub(crate) struct PageBuilder(TextPage);

    impl PageBuilder {
        pub fn new() -> PageBuilder {
            PageBuilder(TextPage {
                width: 612.0,
                height: 792.0,
                fonts: Vec::new(),
                glyphs: Vec::new(),
                image_cover: 0.0,
            })
        }

        pub fn text(mut self, font: &str, size: f32, x: f32, top: f32, text: &str) -> PageBuilder {
            let font = match self.0.fonts.iter().position(|known| known == font) {
                Some(index) => index,
                None => {
                    self.0.fonts.push(font.to_string());
                    self.0.fonts.len() - 1
                }
            };
            let advance = size / 2.0;
            for (i, ch) in text.chars().enumerate() {
                let x0 = x + advance * i as f32;
                let rect = Rect { x0, top, x1: x0 + advance, bottom: top + size };
                self.0.glyphs.push(Glyph { ch, font: u16::try_from(font).unwrap(), size, rect });
            }
            self
        }

        pub fn image_cover(mut self, cover: f32) -> PageBuilder {
            self.0.image_cover = cover;
            self
        }

        /// Reverses the content order, which reading must not depend on.
        pub fn reversed(mut self) -> PageBuilder {
            self.0.glyphs.reverse();
            self
        }

        pub fn build(self) -> TextPage {
            self.0
        }
    }

    impl crate::support::form::Canvas for PageBuilder {
        fn text(self, font: &str, size: f32, x: f32, top: f32, text: &str) -> PageBuilder {
            PageBuilder::text(self, font, size, x, top, text)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::build::PageBuilder;
    use super::*;

    #[test]
    fn reading_order_follows_lines_not_content_order() {
        let page = PageBuilder::new()
            .text("ArialMT", 9.0, 200.0, 101.0, "SAMPLE")
            .text("Calibri", 11.0, 40.0, 100.0, "City")
            .text("Calibri", 11.0, 40.0, 80.0, "Name")
            .reversed()
            .build();
        let order = ReadingOrder::new(&page);
        let text: String = (0..order.order.len()).map(|at| order.glyph(at).ch).collect();
        assert_eq!(text, "NameCitySAMPLE");
        assert_eq!(order.lines().len(), 2);
    }

    #[test]
    fn a_space_outside_the_chosen_glyphs_still_ends_a_word() {
        let mut page = PageBuilder::new().text("ArialMT", 9.0, 100.0, 100.0, "AM PM").build();
        for glyph in &mut page.glyphs {
            glyph.rect.x1 += 3.0;
        }
        let order = ReadingOrder::new(&page);
        let letters: Vec<usize> = (0..order.order.len()).filter(|at| !order.glyph(*at).ch.is_whitespace()).collect();
        let found: Vec<String> = words(&order, &letters).into_iter().map(|word| word.text).collect();
        assert_eq!(found, ["AM", "PM"]);
    }

    #[test]
    fn words_break_at_spaces_gaps_and_lines() {
        let page = PageBuilder::new()
            .text("ArialMT", 9.0, 100.0, 100.0, "CONTOSO LLC")
            .text("ArialMT", 9.0, 160.0, 100.0, "TX")
            .text("ArialMT", 9.0, 100.0, 120.0, "NEXT")
            .build();
        let order = ReadingOrder::new(&page);
        let all: Vec<usize> = (0..order.order.len()).collect();
        let found: Vec<String> = words(&order, &all).into_iter().map(|word| word.text).collect();
        assert_eq!(found, ["CONTOSO", "LLC", "TX", "NEXT"]);
    }
}
