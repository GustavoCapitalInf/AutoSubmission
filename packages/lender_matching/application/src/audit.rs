//! The accuracy of frozen parses against blind audits: what a person typed from page 1, and
//! whether the document is an application, before any parser value was visible. Reports hold
//! field keys and counts only.

use crate::extract::{Document, FieldReading, Reading, RegionValue};
use crate::fields::{FieldId, FieldMap};
use crate::record::{Admission, Override, RevisionState};
use crate::values::FieldValue;

/// How one field of an audited application compares with its frozen parse.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum FieldOutcome {
    /// The parse read the value the page shows, or nothing where the page shows nothing.
    Right,
    /// The parse read a value the page does not show: the silent error.
    Wrong,
    /// The parse flagged the field for a person: a refused value, a missing label or a doubt, or
    /// a hand-entry draft's field that the page fills.
    Refused,
    /// The parse read nothing where the page shows a value, or refused an application.
    Missed,
}

#[derive(Clone, Copy, Default, PartialEq, Eq, Debug)]
pub struct FieldScore {
    pub right: u32,
    pub wrong: u32,
    pub refused: u32,
    pub missed: u32,
}

impl FieldScore {
    fn add(&mut self, outcome: FieldOutcome) {
        match outcome {
            FieldOutcome::Right => self.right += 1,
            FieldOutcome::Wrong => self.wrong += 1,
            FieldOutcome::Refused => self.refused += 1,
            FieldOutcome::Missed => self.missed += 1,
        }
    }

    fn total(self) -> u32 {
        self.right + self.wrong + self.refused + self.missed
    }

    fn plus(self, other: FieldScore) -> FieldScore {
        FieldScore {
            right: self.right + other.right,
            wrong: self.wrong + other.wrong,
            refused: self.refused + other.refused,
            missed: self.missed + other.missed,
        }
    }
}

/// Text and emails compare without case; every other value as read.
fn same(truth: &FieldValue, parsed: &FieldValue) -> bool {
    match (truth, parsed) {
        (FieldValue::Text(_), FieldValue::Text(_)) | (FieldValue::Email(_), FieldValue::Email(_)) => {
            truth.canonical().to_lowercase() == parsed.canonical().to_lowercase()
        }
        _ => truth == parsed,
    }
}

/// `truth` is the audit's value, or None where it found the field empty.
pub fn field_outcome(document: &Document, field: FieldId, truth: Option<&FieldValue>) -> FieldOutcome {
    match document {
        Document::Application(form) => match form.fields.get(field) {
            FieldReading::Located { value: RegionValue::Read(value, _), .. } => match truth {
                Some(truth) if same(truth, value) => FieldOutcome::Right,
                _ => FieldOutcome::Wrong,
            },
            FieldReading::Located { value: RegionValue::Blank | RegionValue::NotApplicable(_), .. } => match truth {
                None => FieldOutcome::Right,
                Some(_) => FieldOutcome::Missed,
            },
            FieldReading::Located { value: RegionValue::Refused(..) | RegionValue::Doubtful(..), .. }
            | FieldReading::Unlocated(_) => FieldOutcome::Refused,
        },
        Document::ManualEntry(_) if truth.is_some() => FieldOutcome::Refused,
        Document::Refused(_) if truth.is_some() => FieldOutcome::Missed,
        Document::ManualEntry(_) | Document::Refused(_) => FieldOutcome::Right,
    }
}

/// The tally of every audited document. A field counts only in a document the audit found to be
/// an application, and only when the audit gave it: a value, or empty.
#[derive(Default)]
pub struct Accuracy {
    /// Sampled documents not audited yet.
    pub awaiting: u32,
    pub audited: u32,
    /// The parse and the audit agree on whether the document is an application; a hand-entry
    /// draft counts as one.
    pub classified_right: u32,
    pub applications_refused: u32,
    pub others_kept: u32,
    pub applications: u32,
    pub wholly_right: u32,
    pub fields: FieldMap<FieldScore>,
}

impl Accuracy {
    /// One audited document: the parse frozen when it was sampled, and the audit's state.
    pub fn add(&mut self, frozen: &Reading, audit: &RevisionState) {
        self.audited += 1;
        let application = audit.admission != Admission::NotAnApplication;
        match (application, matches!(frozen.document, Document::Refused(_))) {
            (true, false) | (false, true) => self.classified_right += 1,
            (true, true) => self.applications_refused += 1,
            (false, false) => self.others_kept += 1,
        }
        if !application {
            return;
        }
        self.applications += 1;
        let mut whole = matches!(frozen.document, Document::Application(_));
        for (field, given) in audit.overrides.iter() {
            let truth = match given {
                Override::Set(value) => Some(value),
                Override::Empty(_) => None,
                Override::Inherit => continue,
            };
            let outcome = field_outcome(&frozen.document, field, truth);
            whole &= outcome == FieldOutcome::Right;
            self.fields.get_mut(field).add(outcome);
        }
        if whole {
            self.wholly_right += 1;
        }
    }

    pub fn lines(&self) -> Vec<String> {
        let wrong = self.applications_refused + self.others_kept;
        let mut lines = vec![
            format!(
                "applications accuracy: {} sampled, {} audited, {} awaiting their audit. Counts only; intervals are Wilson 95%.",
                self.audited + self.awaiting,
                self.audited,
                self.awaiting
            ),
            format!(
                "documents: {} classified right, {wrong} wrong (applications refused {}, other documents kept {}); right {}",
                self.classified_right,
                self.applications_refused,
                self.others_kept,
                share(self.classified_right, self.audited)
            ),
            format!("fields of the {} audited applications:", self.applications),
            format!(
                "{:<34} {:>6} {:>6} {:>8} {:>7}  {:<22} {}",
                "field", "right", "wrong", "refused", "missed", "right", "wrong"
            ),
        ];
        let row = |name: &str, score: FieldScore| {
            format!(
                "{name:<34} {:>6} {:>6} {:>8} {:>7}  {:<22} {}",
                score.right,
                score.wrong,
                score.refused,
                score.missed,
                share(score.right, score.total()),
                share(score.wrong, score.total())
            )
        };
        let mut all = FieldScore::default();
        for (field, score) in self.fields.iter().filter(|(_, score)| score.total() > 0) {
            lines.push(row(&field.to_string(), *score));
            all = all.plus(*score);
        }
        lines.push(row("all fields", all));
        lines.push(format!(
            "applications with every field right: {} of {}, {}",
            self.wholly_right,
            self.applications,
            share(self.wholly_right, self.applications)
        ));
        lines
    }
}

/// `part` of `whole` as a percent with its Wilson 95% interval, such as `96.2% (87.0-98.9)`.
fn share(part: u32, whole: u32) -> String {
    match wilson(part, whole) {
        Some((low, high)) => {
            format!("{:.1}% ({:.1}-{:.1})", 100.0 * f64::from(part) / f64::from(whole), 100.0 * low, 100.0 * high)
        }
        None => "n/a".to_string(),
    }
}

/// The Wilson score interval at 95% for `successes` of `trials`; None without a trial.
pub fn wilson(successes: u32, trials: u32) -> Option<(f64, f64)> {
    if trials == 0 {
        return None;
    }
    let z = 1.959_963_984_540_054_f64;
    let n = f64::from(trials);
    let p = f64::from(successes) / n;
    let denominator = 1.0 + z * z / n;
    let centre = (p + z * z / (2.0 * n)) / denominator;
    let half = z * (p * (1.0 - p) / n + z * z / (4.0 * n * n)).sqrt() / denominator;
    Some(((centre - half).max(0.0), (centre + half).min(1.0)))
}

#[cfg(test)]
mod tests {
    use time::Date;
    use time::macros::date;

    use super::*;
    use crate::extract::{ManualEntryReason, read};
    use crate::fields::BusinessField as B;
    use crate::page::build::PageBuilder;
    use crate::page::{PdfFacts, TextPage};
    use crate::record::{EditInput, Edits, Record};
    use crate::support::form::{Form, certificate, expected};

    const TODAY: Date = date!(2026 - 10 - 23);

    fn reading_of(page: TextPage) -> Reading {
        let certificate = certificate(PageBuilder::new(), &[("SAMPLE OWNER", "owner@example.com")]).build();
        read(&PdfFacts { created_on: Some(date!(2026 - 10 - 21)), pages: vec![page, certificate] })
    }

    fn contract() -> Reading {
        let mut page =
            PageBuilder::new().text("TimesNewRomanPS-BoldMT", 12.0, 40.0, 40.0, "RECEIVABLES PURCHASE AGREEMENT");
        for line in 0..10 {
            page = page.text("ArialMT", 9.0, 40.0, 80.0 + 12.0 * line as f32, "SAMPLE TERMS OF THE AGREEMENT ARE HERE");
        }
        reading_of(page.build())
    }

    /// An audit of `reading` that typed what the sample form prints, with `typed` instead where it
    /// names a field (an empty text leaves the field empty).
    fn audit(reading: &Reading, typed: &[(FieldId, &str)], application: bool) -> RevisionState {
        let sampled = RevisionState::awaiting_audit();
        let truth = expected();
        let inputs: Vec<(FieldId, EditInput)> = FieldId::ALL
            .into_iter()
            .filter(|field| field.spec().editable())
            .map(|field| {
                let text = typed.iter().chain(&truth).find(|(known, _)| *known == field).map_or("", |(_, text)| *text);
                (field, if text.is_empty() { EditInput::Clear } else { EditInput::Text(text) })
            })
            .collect();
        let edits = Edits::read(Record { reading, state: &sampled }, &inputs, TODAY)
            .unwrap_or_else(|refused| panic!("the audit reads: {refused:?}"));
        sampled.audited(&edits, application)
    }

    const LEGAL_NAME: FieldId = FieldId::Business(B::LegalName);

    #[test]
    fn each_field_is_right_wrong_refused_or_missed_against_what_the_auditor_typed() {
        let start = FieldId::Business(B::StartDate);
        let form = Form::word().set(start, "13/45/2019").clear(FieldId::Business(B::Dba));
        let frozen = reading_of(form.draw(PageBuilder::new()).build());
        let city = FieldId::Business(B::City);
        let website = FieldId::Business(B::Website);
        let typed = [
            (LEGAL_NAME, "contoso llc"),
            (city, "DALLAS"),
            (FieldId::Business(B::Dba), "NORTHWIND"),
            (start, "04/15/2019"),
            (website, ""),
        ];
        let mut accuracy = Accuracy::default();
        accuracy.add(&frozen, &audit(&frozen, &typed, true));
        let score = |field| *accuracy.fields.get(field);
        assert_eq!(score(LEGAL_NAME).right, 1, "text compares without case");
        assert_eq!(score(city).wrong, 1);
        assert_eq!(score(website).wrong, 1, "a value the page does not show");
        assert_eq!(score(FieldId::Business(B::Dba)).missed, 1);
        assert_eq!(score(start).refused, 1);
        let all = accuracy.fields.iter().fold(FieldScore::default(), |all, (_, score)| all.plus(*score));
        let editable = FieldId::ALL.iter().filter(|field| field.spec().editable()).count() as u32;
        assert_eq!((all.total(), all.wrong, all.refused, all.missed), (editable, 2, 1, 1));
        assert_eq!((accuracy.applications, accuracy.wholly_right, accuracy.classified_right), (1, 0, 1));

        let mut whole = Accuracy::default();
        let clean = reading_of(Form::word().draw(PageBuilder::new()).build());
        whole.add(&clean, &audit(&clean, &[], true));
        assert_eq!(whole.wholly_right, 1);
        assert!(whole.lines().iter().any(|line| line.starts_with("all fields") && line.contains("100.0%")));
    }

    #[test]
    fn a_document_counts_by_whether_the_parse_and_the_audit_take_it_for_an_application() {
        let mut accuracy = Accuracy { awaiting: 2, ..Accuracy::default() };
        let refused = contract();
        accuracy.add(&refused, &audit(&refused, &[], false));
        assert_eq!((accuracy.classified_right, accuracy.applications), (1, 0), "a refused contract counts no field");
        accuracy.add(&refused, &audit(&refused, &[], true));
        assert_eq!(accuracy.applications_refused, 1);
        assert_eq!(accuracy.fields.get(LEGAL_NAME).missed, 1, "a refused application misses what it holds");
        let form = reading_of(Form::word().draw(PageBuilder::new()).build());
        accuracy.add(&form, &audit(&form, &[], false));
        assert_eq!(accuracy.others_kept, 1);
        let draft =
            reading_of(Form { omit: vec!["Secondary Owner Name"], ..Form::word() }.draw(PageBuilder::new()).build());
        assert!(matches!(draft.document, Document::ManualEntry(ManualEntryReason::UnknownLayout)));
        accuracy.add(&draft, &audit(&draft, &[(FieldId::Business(B::Fax), "")], true));
        assert_eq!(accuracy.fields.get(LEGAL_NAME).refused, 1, "a draft flags what the page fills");
        assert_eq!(accuracy.fields.get(FieldId::Business(B::Fax)).right, 1, "and is right where it is empty");
        assert_eq!((accuracy.audited, accuracy.classified_right, accuracy.wholly_right), (4, 2, 0));
        let lines = accuracy.lines();
        assert!(lines[0].starts_with("applications accuracy: 6 sampled, 4 audited, 2 awaiting their audit."));
        assert!(
            lines[1]
                .starts_with("documents: 2 classified right, 2 wrong (applications refused 1, other documents kept 1)")
        );
        assert!(lines.last().unwrap().starts_with("applications with every field right: 0 of 2"));
    }

    #[test]
    fn wilson_intervals_match_their_published_values() {
        let (low, high) = wilson(81, 100).unwrap();
        assert!((low - 0.7222).abs() < 1e-4 && (high - 0.8749).abs() < 1e-4, "{low} {high}");
        let (low, high) = wilson(0, 10).unwrap();
        assert!(low == 0.0 && (high - 0.2775).abs() < 1e-4);
        assert_eq!(wilson(0, 0), None);
        assert_eq!(share(1, 2), "50.0% (9.5-90.5)");
    }
}
