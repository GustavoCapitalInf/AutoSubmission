use serde::Serialize;
use time::Date;

use crate::certificate::{Certificate, read_certificate};
use crate::fields::{BusinessField, FieldId, FieldMap};
use crate::page::{PdfFacts, ReadingOrder, Rect, TextPage, words};
use crate::template::{
    self, CONTRACT_TITLE, FORM, LAYOUT_TOLERANCE_PT, LabelSpec, NEXT_LINE_BOTTOM_PT, ROW_BAND_PT, SectionStart, Shape,
    Target,
};
use crate::values::{Answer, FieldValue, RawText, ReadContext, Refusal};

/// What one PDF reads as. It holds application data, so it has no `Debug`.
pub struct Reading {
    pub document: Document,
    pub certificate: Option<Certificate>,
    pub signed_on: Option<SignedOn>,
    /// Each sentinel label's offset from the BUSINESS INFORMATION heading, wherever both were
    /// placed; how a new layout is measured.
    pub offsets: Vec<SentinelOffset>,
}

/// The signing day: the certificate's completion day, else the PDF's creation day, so a reading
/// is a function of the bytes alone.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SignedOn {
    Certificate(Date),
    Created(Date),
}

impl SignedOn {
    pub fn date(self) -> Date {
        match self {
            SignedOn::Certificate(date) | SignedOn::Created(date) => date,
        }
    }
}

#[derive(Clone, Copy, PartialEq, Debug)]
pub struct SentinelOffset {
    pub field: FieldId,
    pub dx: f32,
    pub dy: f32,
}

pub enum Document {
    Application(FormReading),
    /// A person enters the application by hand.
    ManualEntry(ManualEntryReason),
    /// Not an application.
    Refused(RefusalReason),
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ManualEntryReason {
    /// The first page is mostly image, or has too little text.
    SuspectedScan,
    /// The form's headings are there, but its labels do not fit exactly one known layout.
    UnknownLayout,
    /// The first page holds both application and contract headings.
    AmbiguousDocument,
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RefusalReason {
    /// A Receivables Purchase Agreement.
    Contract,
    /// Other envelope paperwork: none of the form's headings.
    OtherPaperwork,
}

/// A `LayoutSpec` of the template; only the template makes one.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct LayoutId(&'static str);

impl LayoutId {
    pub fn as_str(self) -> &'static str {
        self.0
    }
}

pub struct FormReading {
    pub layout: LayoutId,
    pub fields: FieldMap<FieldReading>,
    /// Text inside the form that is neither the form's own text nor in any field's region.
    pub unplaced: Vec<Unplaced>,
}

pub enum FieldReading {
    Unlocated(Unlocated),
    /// `region` is where the value belongs, whether or not anything is there: a glyph belongs to it
    /// when its horizontal center lies within `x0..x1` and its top within `top..=bottom`.
    Located {
        label: Rect,
        region: Rect,
        value: RegionValue,
    },
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Unlocated {
    /// No text of the label in its section.
    LabelMissing,
    /// The label's text is in its section, but no single place for it fits the form's order.
    LabelOutOfPlace,
}

pub enum RegionValue {
    Blank,
    NotApplicable(Evidence),
    Read(FieldValue, Evidence),
    Refused(Refusal, Evidence),
    /// Text is there, but which field it belongs to is in doubt.
    Doubtful(Doubt, Option<Evidence>),
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum Doubt {
    /// The label's text occurs more often in its section than the form prints it.
    LabelFoundTwice,
    /// Label text the form's order did not place lies in the region.
    StrayLabel,
    /// A glyph in the region also lies in another field's region.
    SharedGlyph,
}

/// Text from the page: application data, for a person to see. It has no `Debug`.
pub struct Evidence {
    pub text: String,
    pub rect: Rect,
}

pub struct Unplaced {
    pub evidence: Evidence,
    /// The last field label before it in reading order.
    pub after: Option<FieldId>,
}

/// A field reading without its value or text.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum Outcome {
    Read,
    Blank,
    NotApplicable,
    Refused(Refusal),
    LabelMissing,
    LabelOutOfPlace,
    Doubtful(Doubt),
}

impl FieldReading {
    pub fn outcome(&self) -> Outcome {
        match self {
            FieldReading::Unlocated(Unlocated::LabelMissing) => Outcome::LabelMissing,
            FieldReading::Unlocated(Unlocated::LabelOutOfPlace) => Outcome::LabelOutOfPlace,
            FieldReading::Located { value, .. } => match value {
                RegionValue::Blank => Outcome::Blank,
                RegionValue::NotApplicable(_) => Outcome::NotApplicable,
                RegionValue::Read(..) => Outcome::Read,
                RegionValue::Refused(why, _) => Outcome::Refused(*why),
                RegionValue::Doubtful(doubt, _) => Outcome::Doubtful(*doubt),
            },
        }
    }

    pub fn value(&self) -> Option<&FieldValue> {
        match self {
            FieldReading::Located { value: RegionValue::Read(value, _), .. } => Some(value),
            _ => None,
        }
    }

    pub fn evidence(&self) -> Option<&Evidence> {
        match self {
            FieldReading::Located { value, .. } => match value {
                RegionValue::NotApplicable(evidence)
                | RegionValue::Read(_, evidence)
                | RegionValue::Refused(_, evidence)
                | RegionValue::Doubtful(_, Some(evidence)) => Some(evidence),
                RegionValue::Blank | RegionValue::Doubtful(_, None) => None,
            },
            FieldReading::Unlocated(_) => None,
        }
    }
}

/// Pure: the reading depends on the PDF's content alone.
pub fn read(doc: &PdfFacts) -> Reading {
    let certificate = read_certificate(&doc.pages);
    let signed_on = certificate
        .as_ref()
        .and_then(|certificate| certificate.completed_on)
        .map(SignedOn::Certificate)
        .or(doc.created_on.map(SignedOn::Created));
    let (document, offsets) = match doc.pages.first() {
        Some(page) => read_form(page, signed_on.map(SignedOn::date)),
        None => (Document::Refused(RefusalReason::OtherPaperwork), Vec::new()),
    };
    Reading { document, certificate, signed_on, offsets }
}

/// Text of the template found on the page, at glyph level.
struct Candidate {
    text: &'static str,
    heading: bool,
    /// Positions in reading order, a trailing colon included.
    positions: Vec<usize>,
    first: Rect,
    end_x: f32,
}

impl Candidate {
    fn start(&self) -> usize {
        self.positions[0]
    }
}

/// Every occurrence of a heading (any font) or a label (in a label font) that starts a word and
/// lies on one line. The label's end needs no boundary, so `City:SAMPLE` typed in one run splits
/// after the label. Where occurrences overlap, the longer one wins.
fn find_candidates(order: &ReadingOrder) -> Vec<Candidate> {
    let mut texts: Vec<(&'static str, bool)> = vec![(CONTRACT_TITLE, true)];
    for section in FORM.sections {
        if let SectionStart::Heading(text) = section.start {
            texts.push((text, true));
        }
        for label in section.labels {
            if !texts.contains(&(label.text, false)) {
                texts.push((label.text, false));
            }
        }
    }
    let label_font = |name: &str| FORM.label_fonts.iter().any(|prefix| name.starts_with(prefix));
    let mut found = Vec::new();
    for at in 0..order.order.len() {
        if !order.starts_word(at) {
            continue;
        }
        for (text, heading) in &texts {
            let font_ok = |name: &str| *heading || label_font(name);
            if let Some(positions) = match_at(order, at, text, font_ok) {
                let first = order.glyph(positions[0]).rect;
                let end_x = order.glyph(*positions.last().expect("a label has text")).rect.x1;
                found.push(Candidate { text, heading: *heading, positions, first, end_x });
            }
        }
    }
    found.sort_by(|a, b| b.positions.len().cmp(&a.positions.len()).then(a.start().cmp(&b.start())));
    let mut claimed = vec![false; order.order.len()];
    let mut kept: Vec<Candidate> = Vec::new();
    for candidate in found {
        if candidate.positions.iter().all(|at| !claimed[*at]) {
            for at in &candidate.positions {
                claimed[*at] = true;
            }
            kept.push(candidate);
        }
    }
    kept.sort_by_key(Candidate::start);
    kept
}

fn match_at(order: &ReadingOrder, start: usize, text: &str, font_ok: impl Fn(&str) -> bool) -> Option<Vec<usize>> {
    let line = order.line[start];
    let on_line = |at: usize| at < order.order.len() && order.line[at] == line;
    let skip_spaces = |mut at: usize| {
        while on_line(at) && order.glyph(at).ch.is_whitespace() {
            at += 1;
        }
        at
    };
    let mut positions = Vec::new();
    let mut at = start;
    for ch in text.chars().filter(|c| !c.is_whitespace()) {
        at = skip_spaces(at);
        if !on_line(at) {
            return None;
        }
        let glyph = order.glyph(at);
        if glyph.ch != ch || !font_ok(order.page.font_name(glyph)) {
            return None;
        }
        positions.push(at);
        at += 1;
    }
    let colon = skip_spaces(at);
    if on_line(colon) && order.glyph(colon).ch == ':' {
        positions.push(colon);
    }
    Some(positions)
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Placement {
    Bound(usize),
    Missing,
    OutOfPlace,
}

/// The longest order-preserving matching of the section's labels to its candidates (both in
/// reading order). A label is bound only when every longest matching puts it on the same
/// candidate; otherwise it is out of place.
fn align(labels: &[LabelSpec], candidates: &[usize], all: &[Candidate]) -> Vec<Placement> {
    const MAX_CANDIDATES: usize = 64;
    if candidates.len() > MAX_CANDIDATES {
        return vec![Placement::OutOfPlace; labels.len()];
    }
    let pairs: Vec<(usize, usize)> = (0..labels.len())
        .flat_map(|i| (0..candidates.len()).map(move |j| (i, j)))
        .filter(|(i, j)| labels[*i].text == all[candidates[*j]].text)
        .collect();
    let chain = |order: &mut dyn Iterator<Item = usize>, before: &dyn Fn(usize, usize) -> bool| {
        let mut best: Vec<(usize, u128)> = vec![(0, 0); pairs.len()];
        for p in order {
            let (mut length, mut count) = (1, 1u128);
            for (q, &(before_length, before_count)) in best.iter().enumerate() {
                if before_length > 0 && before(q, p) {
                    if before_length + 1 > length {
                        (length, count) = (before_length + 1, before_count);
                    } else if before_length + 1 == length {
                        count = count.saturating_add(before_count);
                    }
                }
            }
            best[p] = (length, count);
        }
        best
    };
    let precedes = |q: usize, p: usize| pairs[q].0 < pairs[p].0 && pairs[q].1 < pairs[p].1;
    let ending = chain(&mut (0..pairs.len()), &precedes);
    let starting = chain(&mut (0..pairs.len()).rev(), &|q, p| precedes(p, q));
    let longest = ending.iter().map(|(length, _)| *length).max().unwrap_or(0);
    let total: u128 =
        ending.iter().filter(|(length, _)| *length == longest).map(|(_, count)| *count).fold(0, u128::saturating_add);
    (0..labels.len())
        .map(|i| {
            let mut through_all = None;
            let mut has_candidate = false;
            for (p, (label, candidate)) in pairs.iter().enumerate() {
                if *label != i {
                    continue;
                }
                has_candidate = true;
                let in_longest = ending[p].0 + starting[p].0 - 1 == longest;
                if in_longest && ending[p].1.saturating_mul(starting[p].1) == total {
                    through_all = Some(candidates[*candidate]);
                }
            }
            match (through_all, has_candidate) {
                (Some(candidate), _) => Placement::Bound(candidate),
                (None, true) => Placement::OutOfPlace,
                (None, false) => Placement::Missing,
            }
        })
        .collect()
}

/// A placed label and its value region.
struct Bound {
    label: &'static LabelSpec,
    section: usize,
    candidate: usize,
    region: Rect,
    /// The label's text occurs more often in its section than the form prints it.
    found_twice: bool,
}

fn in_region(region: &Rect, glyph: Rect) -> bool {
    let x = glyph.center_x();
    x >= region.x0 && x < region.x1 && glyph.top >= region.top && glyph.top <= region.bottom
}

fn read_form(page: &TextPage, signed_on: Option<Date>) -> (Document, Vec<SentinelOffset>) {
    let order = ReadingOrder::new(page);
    let candidates = find_candidates(&order);
    let heading_count = |text: &str| candidates.iter().filter(|c| c.heading && c.text == text).count();
    let form_headings = FORM
        .sections
        .iter()
        .filter(|section| matches!(section.start, SectionStart::Heading(text) if heading_count(text) > 0))
        .count();
    let contract = heading_count(CONTRACT_TITLE) > 0;
    let scan_like = page.image_cover >= template::SCAN_IMAGE_COVER || page.text_chars() < template::MIN_TEXT_CHARS;
    let early = match (contract, form_headings, scan_like) {
        (true, 1.., _) => Some(Document::ManualEntry(ManualEntryReason::AmbiguousDocument)),
        (true, 0, _) => Some(Document::Refused(RefusalReason::Contract)),
        (false, 0, true) => Some(Document::ManualEntry(ManualEntryReason::SuspectedScan)),
        (false, 0, false) => Some(Document::Refused(RefusalReason::OtherPaperwork)),
        (false, 1.., true) => Some(Document::ManualEntry(ManualEntryReason::SuspectedScan)),
        (false, 1.., false) => None,
    };
    if let Some(document) = early {
        return (document, Vec::new());
    }
    let unknown = || Document::ManualEntry(ManualEntryReason::UnknownLayout);

    // Each section starts at exactly one occurrence of its heading or first label, in order.
    let mut starts = Vec::with_capacity(FORM.sections.len());
    for section in FORM.sections {
        let (text, heading) = match section.start {
            SectionStart::Heading(text) => (text, true),
            SectionStart::FirstLabel => (section.labels[0].text, false),
        };
        let found: Vec<usize> =
            (0..candidates.len()).filter(|&c| candidates[c].heading == heading && candidates[c].text == text).collect();
        let [only] = found.as_slice() else { return (unknown(), Vec::new()) };
        if starts.last().is_some_and(|&previous: &usize| candidates[previous].start() >= candidates[*only].start()) {
            return (unknown(), Vec::new());
        }
        starts.push(*only);
    }
    let section_of = |at: usize| (0..starts.len()).rev().find(|&s| candidates[starts[s]].start() <= at);
    let business_heading = candidates[starts[0]].first;

    let mut placements: Vec<(usize, usize, Placement)> = Vec::new();
    for (s, section) in FORM.sections.iter().enumerate() {
        let mine: Vec<usize> = (0..candidates.len())
            .filter(|&c| !candidates[c].heading && section_of(candidates[c].start()) == Some(s))
            .collect();
        for (i, placement) in align(section.labels, &mine, &candidates).into_iter().enumerate() {
            placements.push((s, i, placement));
        }
    }
    let label_tops: Vec<(f32, f32)> = placements
        .iter()
        .filter_map(|(_, _, placement)| match placement {
            Placement::Bound(c) => Some((candidates[*c].first.top, candidates[*c].first.x0)),
            _ => None,
        })
        .collect();
    let mut bound: Vec<Bound> = Vec::new();
    for (s, i, placement) in &placements {
        let Placement::Bound(c) = *placement else { continue };
        let label = &FORM.sections[*s].labels[*i];
        let candidate = &candidates[c];
        let top = candidate.first.top;
        let x1 = label_tops
            .iter()
            .filter(|(other_top, x0)| {
                *other_top >= top + ROW_BAND_PT.0 && *other_top <= top + ROW_BAND_PT.1 && *x0 >= candidate.end_x
            })
            .map(|(_, x0)| *x0)
            .fold(page.width, f32::min);
        let bottom = match label.shape {
            Shape::Row => top + ROW_BAND_PT.1,
            Shape::RowAndNextLine => top + NEXT_LINE_BOTTOM_PT,
        };
        let region = Rect { x0: candidate.end_x, top: top + ROW_BAND_PT.0, x1, bottom };
        let printed = FORM.sections[*s].labels.iter().filter(|other| other.text == label.text).count();
        let present = (0..candidates.len())
            .filter(|&o| {
                let other = &candidates[o];
                !other.heading && other.text == label.text && section_of(other.start()) == Some(*s)
            })
            .count();
        bound.push(Bound { label, section: *s, candidate: c, region, found_twice: present > printed });
    }

    let field_bound = |field: FieldId| {
        bound.iter().find(|b| b.label.target == Target::Field(field)).map(|b| &candidates[b.candidate])
    };
    let offsets: Vec<SentinelOffset> = FORM.layouts[0]
        .sentinels
        .iter()
        .filter_map(|(field, _, _)| {
            field_bound(*field).map(|c| SentinelOffset {
                field: *field,
                dx: c.first.x0 - business_heading.x0,
                dy: c.first.top - business_heading.top,
            })
        })
        .collect();
    let fits: Vec<LayoutId> = FORM
        .layouts
        .iter()
        .filter(|layout| {
            layout.sentinels.iter().all(|(field, dx, dy)| {
                offsets.iter().find(|offset| offset.field == *field).is_some_and(|offset| {
                    (offset.dy - dy).abs() <= LAYOUT_TOLERANCE_PT
                        && dx.is_none_or(|dx| (offset.dx - dx).abs() <= LAYOUT_TOLERANCE_PT)
                })
            })
        })
        .map(|layout| LayoutId(layout.id))
        .collect();
    let [layout] = fits.as_slice() else { return (unknown(), offsets) };

    let (fields, unplaced) = place_and_read(&order, &candidates, &starts, &placements, &bound, signed_on);
    (Document::Application(FormReading { layout: *layout, fields, unplaced }), offsets)
}

fn place_and_read(
    order: &ReadingOrder,
    candidates: &[Candidate],
    starts: &[usize],
    placements: &[(usize, usize, Placement)],
    bound: &[Bound],
    signed_on: Option<Date>,
) -> (FieldMap<FieldReading>, Vec<Unplaced>) {
    let glyph_count = order.order.len();
    let mut template_text = vec![false; glyph_count];
    for b in bound {
        for at in &candidates[b.candidate].positions {
            template_text[*at] = true;
        }
    }
    for start in starts {
        if candidates[*start].heading {
            for at in &candidates[*start].positions {
                template_text[*at] = true;
            }
        }
    }

    let mut assigned: Vec<Vec<usize>> = vec![Vec::new(); bound.len()];
    let mut shared = vec![false; bound.len()];
    let mut stray = vec![false; bound.len()];
    let mut loose = vec![false; glyph_count];
    let business_top = candidates[starts[0]].first.top;
    let area_bottom = bound.iter().map(|b| b.region.bottom).fold(business_top, f32::max);
    // The certification paragraph lies between the last field row and the first signature line.
    // Its text is not in the template, so that band is left out of the unplaced check.
    let signatures = FORM.sections.len() - 1;
    let fields_bottom =
        bound.iter().filter(|b| b.section < signatures).map(|b| b.region.bottom).fold(f32::MIN, f32::max);
    let signature_top = bound.iter().filter(|b| b.section == signatures).map(|b| b.region.top).fold(f32::MAX, f32::min);
    for at in 0..glyph_count {
        let glyph = order.glyph(at);
        if glyph.ch.is_whitespace() || template_text[at] {
            continue;
        }
        let holders: Vec<usize> = (0..bound.len()).filter(|&b| in_region(&bound[b].region, glyph.rect)).collect();
        match holders.as_slice() {
            [] => {
                let top = glyph.rect.top;
                let certification = top > fields_bottom && top < signature_top;
                loose[at] = top >= business_top && top <= area_bottom && !certification;
            }
            [only] => assigned[*only].push(at),
            several => {
                for b in several {
                    assigned[*b].push(at);
                    shared[*b] = true;
                }
            }
        }
    }
    let bound_candidates: Vec<usize> = bound.iter().map(|b| b.candidate).collect();
    for (c, candidate) in candidates.iter().enumerate() {
        if candidate.heading || bound_candidates.contains(&c) {
            continue;
        }
        let first = order.glyph(candidate.start()).rect;
        for (b, holder) in bound.iter().enumerate() {
            if in_region(&holder.region, first) {
                stray[b] = true;
            }
        }
    }

    let evidence = |positions: &[usize]| -> Option<(RawText, Evidence)> {
        let rect = positions.iter().map(|at| order.glyph(*at).rect).reduce(Rect::union)?;
        let raw = RawText::placed(words(order, positions));
        let text = raw.as_str().to_string();
        Some((raw, Evidence { text, rect }))
    };
    let mut raw: Vec<Option<(RawText, Evidence)>> = assigned.iter().map(|positions| evidence(positions)).collect();
    let index_of = |field: FieldId| bound.iter().position(|b| b.label.target == Target::Field(field));
    let state = FieldId::Business(BusinessField::State);
    let business_country = index_of(state).and_then(|b| raw[b].as_ref()).and_then(|(text, _)| {
        match state.read(text, &ReadContext::default()) {
            Ok(Answer::Value(FieldValue::Jurisdiction(code))) => Some(code.country()),
            _ => None,
        }
    });
    let context = ReadContext { signed_on, business_country };

    let mut slots: Vec<Option<FieldReading>> = FieldId::ALL.iter().map(|_| None).collect();
    for (s, i, placement) in placements {
        let Target::Field(field) = FORM.sections[*s].labels[*i].target else { continue };
        let reading = match placement {
            Placement::Missing => FieldReading::Unlocated(Unlocated::LabelMissing),
            Placement::OutOfPlace => FieldReading::Unlocated(Unlocated::LabelOutOfPlace),
            Placement::Bound(_) => {
                let b = index_of(field).expect("a bound field has a region");
                let label = candidates[bound[b].candidate]
                    .positions
                    .iter()
                    .map(|at| order.glyph(*at).rect)
                    .reduce(Rect::union)
                    .expect("a label has text");
                let found = raw[b].take();
                let doubt = if bound[b].found_twice {
                    Some(Doubt::LabelFoundTwice)
                } else if stray[b] {
                    Some(Doubt::StrayLabel)
                } else if shared[b] {
                    Some(Doubt::SharedGlyph)
                } else {
                    None
                };
                let value = match (doubt, found) {
                    (Some(doubt), found) => RegionValue::Doubtful(doubt, found.map(|(_, evidence)| evidence)),
                    (None, None) => RegionValue::Blank,
                    (None, Some((text, evidence))) => match field.read(&text, &context) {
                        Ok(Answer::Value(value)) => RegionValue::Read(value, evidence),
                        Ok(Answer::NotApplicable) => RegionValue::NotApplicable(evidence),
                        Err(why) => RegionValue::Refused(why, evidence),
                    },
                };
                FieldReading::Located { label, region: bound[b].region, value }
            }
        };
        slots[field.index()] = Some(reading);
    }
    let mut slots = slots.into_iter();
    let readings = FieldMap::from_fn(|_| slots.next().flatten().expect("every field has a label"));

    let mut field_starts: Vec<(usize, FieldId)> = bound
        .iter()
        .filter_map(|b| match b.label.target {
            Target::Field(field) => Some((candidates[b.candidate].start(), field)),
            Target::Signature => None,
        })
        .collect();
    field_starts.sort_by_key(|(at, _)| *at);
    let mut unplaced = Vec::new();
    let mut run: Vec<usize> = Vec::new();
    let flush = |run: &mut Vec<usize>, unplaced: &mut Vec<Unplaced>| {
        if let Some((_, evidence)) = evidence(run) {
            let after = field_starts.iter().rev().find(|(at, _)| *at < run[0]).map(|(_, field)| *field);
            unplaced.push(Unplaced { evidence, after });
        }
        run.clear();
    };
    for (at, &is_loose) in loose.iter().enumerate() {
        let glyph = order.glyph(at);
        if is_loose {
            let continues = run.last().is_some_and(|&last| {
                order.line[last] == order.line[at]
                    && (last + 1..at).all(|between| order.glyph(between).ch.is_whitespace())
            });
            if !continues {
                flush(&mut run, &mut unplaced);
            }
            run.push(at);
        } else if !glyph.ch.is_whitespace() {
            flush(&mut run, &mut unplaced);
        }
    }
    flush(&mut run, &mut unplaced);
    (readings, unplaced)
}

#[cfg(test)]
#[path = "extract_tests.rs"]
mod tests;
