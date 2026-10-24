use std::collections::BTreeMap;

use serde::{Serialize, Serializer};

use crate::PARSER_VERSION;
use crate::certificate::{DetailCheck, SignerCheck, compare_signer};
use crate::extract::{Document, ManualEntryReason, Outcome, Reading, RefusalReason, SignedOn};
use crate::fields::{FieldId, FieldMap, OwnerField, OwnerSlot};
use crate::pdf::ReadError;
use crate::values::FieldValue;
use crate::worker::WorkerError;

/// A shape seen fewer times than this for a field is reported as `other`.
const SHAPE_MIN_COUNT: u32 = 3;
const SHAPE_MAX_LEN: usize = 24;

/// What `applications evaluate` counts. It holds counts, field keys and closed reasons. The one
/// exception is `shapes`, built from refused values of structured kinds; it is written only with
/// rare shapes folded into `other`.
#[derive(Serialize)]
pub struct Tally {
    pub parser_version: u32,
    pub pdf_files: u32,
    pub other_files: u32,
    #[serde(serialize_with = "keyed")]
    pub failures: BTreeMap<Failure, u32>,
    #[serde(serialize_with = "keyed")]
    pub documents: BTreeMap<DocumentKind, u32>,
    pub layouts: BTreeMap<&'static str, u32>,
    pub signed_on: SignedOnCounts,
    pub certificate: CertificateCounts,
    /// Applications only.
    #[serde(serialize_with = "keyed")]
    pub signer_check: BTreeMap<SignerCheck, u32>,
    /// The principal owner's name against the signers' names, applications only.
    #[serde(serialize_with = "keyed")]
    pub signer_name: BTreeMap<DetailCheck, u32>,
    /// The principal owner's email against the signers' emails, applications only.
    #[serde(serialize_with = "keyed")]
    pub signer_email: BTreeMap<DetailCheck, u32>,
    pub unplaced: UnplacedCounts,
    pub fields: FieldMap<FieldCounts>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub offsets: Option<BTreeMap<FieldId, Offsets>>,
    #[serde(skip_serializing_if = "Option::is_none", serialize_with = "folded")]
    shapes: Option<BTreeMap<FieldId, BTreeMap<String, u32>>>,
}

#[derive(Clone, Copy, Default)]
pub struct TallyOptions {
    pub offsets: bool,
    pub shapes: bool,
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum Failure {
    /// The file could not be read from disk.
    Unopened,
    Worker(WorkerError),
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub enum DocumentKind {
    Application,
    ManualEntry(ManualEntryReason),
    Refused(RefusalReason),
}

#[derive(Default, Serialize)]
pub struct SignedOnCounts {
    pub certificate: u32,
    pub creation_date: u32,
    pub none: u32,
}

#[derive(Default, Serialize)]
pub struct CertificateCounts {
    pub found: u32,
    pub envelope_id: u32,
    pub completed_on: u32,
    pub no_signer: u32,
    pub one_signer: u32,
    pub more_signers: u32,
}

#[derive(Default, Serialize)]
pub struct UnplacedCounts {
    pub applications: u32,
    pub runs: u32,
    /// Runs by the field label before them, or `start` before the first one.
    pub after: BTreeMap<String, u32>,
}

#[derive(Clone, Default)]
pub struct FieldCounts(BTreeMap<Outcome, u32>);

/// Whole points, rounded.
#[derive(Default, Serialize)]
pub struct Offsets {
    pub dx: BTreeMap<i32, u32>,
    pub dy: BTreeMap<i32, u32>,
}

trait Key {
    fn key(&self) -> String;
}

impl Key for Failure {
    fn key(&self) -> String {
        match self {
            Failure::Unopened => "unopened",
            Failure::Worker(WorkerError::Read(ReadError::NotPdf)) => "not_pdf",
            Failure::Worker(WorkerError::Read(ReadError::Encrypted)) => "encrypted",
            Failure::Worker(WorkerError::Read(ReadError::TooLarge)) => "too_large",
            Failure::Worker(WorkerError::Read(ReadError::Engine)) => "engine_error",
            Failure::Worker(WorkerError::Timeout) => "timeout",
            Failure::Worker(WorkerError::Crashed) => "worker_crashed",
            Failure::Worker(WorkerError::NoEngine) => "no_engine",
        }
        .to_string()
    }
}

impl Key for DocumentKind {
    fn key(&self) -> String {
        match self {
            DocumentKind::Application => "application".to_string(),
            DocumentKind::ManualEntry(reason) => format!("manual_entry.{}", snake(reason)),
            DocumentKind::Refused(reason) => format!("refused.{}", snake(reason)),
        }
    }
}

impl Key for SignerCheck {
    fn key(&self) -> String {
        snake(self)
    }
}

impl Key for DetailCheck {
    fn key(&self) -> String {
        snake(self)
    }
}

impl Key for Outcome {
    fn key(&self) -> String {
        match self {
            Outcome::Read => "read".to_string(),
            Outcome::Blank => "blank".to_string(),
            Outcome::NotApplicable => "not_applicable".to_string(),
            Outcome::Refused(why) => format!("refused.{}", why.key()),
            Outcome::LabelMissing => "label_missing".to_string(),
            Outcome::LabelOutOfPlace => "label_out_of_place".to_string(),
            Outcome::Doubtful(doubt) => format!("doubtful.{}", snake(doubt)),
        }
    }
}

/// A unit variant's name in snake case: `LabelFoundTwice` as `label_found_twice`.
fn snake(value: &impl std::fmt::Debug) -> String {
    let mut out = String::new();
    for (i, c) in format!("{value:?}").chars().enumerate() {
        if c.is_uppercase() && i > 0 {
            out.push('_');
        }
        out.extend(c.to_lowercase());
    }
    out
}

fn keyed<K: Key, S: Serializer>(map: &BTreeMap<K, u32>, serializer: S) -> Result<S::Ok, S::Error> {
    serializer.collect_map(map.iter().map(|(key, count)| (key.key(), count)))
}

impl Serialize for FieldCounts {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        keyed(&self.0, serializer)
    }
}

fn fold(shapes: &BTreeMap<String, u32>) -> BTreeMap<String, u32> {
    let mut folded = BTreeMap::new();
    for (shape, count) in shapes {
        let key = if *count < SHAPE_MIN_COUNT { "other".to_string() } else { shape.clone() };
        *folded.entry(key).or_insert(0) += count;
    }
    folded
}

fn folded<S: Serializer>(
    shapes: &Option<BTreeMap<FieldId, BTreeMap<String, u32>>>,
    serializer: S,
) -> Result<S::Ok, S::Error> {
    let folded = shapes.as_ref().map(|shapes| {
        shapes
            .iter()
            .map(|(field, shapes)| (*field, fold(shapes)))
            .collect::<BTreeMap<FieldId, BTreeMap<String, u32>>>()
    });
    folded.serialize(serializer)
}

/// Digits as `9`, letters as `A` or `a`, other characters outside ASCII as `?`, spacing collapsed;
/// `long` past `SHAPE_MAX_LEN` characters.
fn shape(text: &str) -> String {
    let words: Vec<String> = text
        .split_whitespace()
        .map(|word| {
            word.chars()
                .map(|c| match c {
                    c if c.is_numeric() => '9',
                    c if c.is_alphabetic() && c.is_uppercase() => 'A',
                    c if c.is_alphabetic() => 'a',
                    c if c.is_ascii() => c,
                    _ => '?',
                })
                .collect()
        })
        .collect();
    let shape = words.join(" ");
    if shape.chars().count() > SHAPE_MAX_LEN { "long".to_string() } else { shape }
}

impl Tally {
    pub fn new(options: TallyOptions) -> Tally {
        Tally {
            parser_version: PARSER_VERSION,
            pdf_files: 0,
            other_files: 0,
            failures: BTreeMap::new(),
            documents: BTreeMap::new(),
            layouts: BTreeMap::new(),
            signed_on: SignedOnCounts::default(),
            certificate: CertificateCounts::default(),
            signer_check: BTreeMap::new(),
            signer_name: BTreeMap::new(),
            signer_email: BTreeMap::new(),
            unplaced: UnplacedCounts::default(),
            fields: FieldMap::default(),
            offsets: options.offsets.then(BTreeMap::new),
            shapes: options.shapes.then(BTreeMap::new),
        }
    }

    pub fn add_failure(&mut self, failure: Failure) {
        self.pdf_files += 1;
        *self.failures.entry(failure).or_insert(0) += 1;
    }

    pub fn add(&mut self, reading: &Reading) {
        self.pdf_files += 1;
        let kind = match &reading.document {
            Document::Application(_) => DocumentKind::Application,
            Document::ManualEntry(reason) => DocumentKind::ManualEntry(*reason),
            Document::Refused(reason) => DocumentKind::Refused(*reason),
        };
        *self.documents.entry(kind).or_insert(0) += 1;
        match reading.signed_on {
            Some(SignedOn::Certificate(_)) => self.signed_on.certificate += 1,
            Some(SignedOn::Created(_)) => self.signed_on.creation_date += 1,
            None => self.signed_on.none += 1,
        }
        if let Some(certificate) = &reading.certificate {
            self.certificate.found += 1;
            self.certificate.envelope_id += u32::from(certificate.envelope.is_some());
            self.certificate.completed_on += u32::from(certificate.completed_on.is_some());
            match certificate.signers.len() {
                0 => self.certificate.no_signer += 1,
                1 => self.certificate.one_signer += 1,
                _ => self.certificate.more_signers += 1,
            }
        }
        if let Some(offsets) = &mut self.offsets {
            for offset in &reading.offsets {
                let histogram = offsets.entry(offset.field).or_default();
                *histogram.dx.entry(offset.dx.round() as i32).or_insert(0) += 1;
                *histogram.dy.entry(offset.dy.round() as i32).or_insert(0) += 1;
            }
        }
        let Document::Application(form) = &reading.document else { return };
        *self.layouts.entry(form.layout.as_str()).or_insert(0) += 1;
        for (field, field_reading) in form.fields.iter() {
            let outcome = field_reading.outcome();
            *self.fields.get_mut(field).0.entry(outcome).or_insert(0) += 1;
            if let (Some(shapes), Outcome::Refused(_)) = (&mut self.shapes, outcome)
                && field.spec().kind.is_structured()
                && let Some(evidence) = field_reading.evidence()
            {
                *shapes.entry(field).or_default().entry(shape(&evidence.text)).or_insert(0) += 1;
            }
        }
        if !form.unplaced.is_empty() {
            self.unplaced.applications += 1;
        }
        for run in &form.unplaced {
            self.unplaced.runs += 1;
            let after = run.after.map_or("start".to_string(), |field| field.to_string());
            *self.unplaced.after.entry(after).or_insert(0) += 1;
        }
        let principal = |field| form.fields.get(FieldId::Owner(OwnerSlot::Principal, field)).value();
        let name = match principal(OwnerField::Name) {
            Some(FieldValue::Text(name)) => Some(name.as_str()),
            _ => None,
        };
        let email = match principal(OwnerField::Email) {
            Some(FieldValue::Email(email)) => Some(email),
            _ => None,
        };
        let signers = reading.certificate.as_ref().map_or(&[][..], |certificate| &certificate.signers);
        let comparison = compare_signer(name, email, signers);
        *self.signer_check.entry(comparison.check).or_insert(0) += 1;
        *self.signer_name.entry(comparison.name).or_insert(0) += 1;
        *self.signer_email.entry(comparison.email).or_insert(0) += 1;
    }

    /// The report as text lines.
    pub fn lines(&self) -> Vec<String> {
        let join = |items: Vec<String>| if items.is_empty() { "none".to_string() } else { items.join(" · ") };
        let counted = |map: &BTreeMap<String, u32>| {
            join(map.iter().filter(|(_, n)| **n > 0).map(|(key, n)| format!("{key} {n}")).collect())
        };
        let listed = |pairs: Vec<(String, u32)>| counted(&pairs.into_iter().collect());
        let mut lines = vec![
            format!(
                "applications evaluate: parser {}, {} PDF files, {} other files skipped. Counts only.",
                self.parser_version, self.pdf_files, self.other_files
            ),
            format!("documents     {}", listed(self.documents.iter().map(|(k, n)| (k.key(), *n)).collect())),
            format!("failures      {}", listed(self.failures.iter().map(|(k, n)| (k.key(), *n)).collect())),
            format!("layouts       {}", listed(self.layouts.iter().map(|(k, n)| (k.to_string(), *n)).collect())),
            format!(
                "signing day   certificate {} · creation date {} · none {}",
                self.signed_on.certificate, self.signed_on.creation_date, self.signed_on.none
            ),
            format!(
                "certificate   found {} · envelope id {} · completed day {} · signers: none {}, one {}, more {}",
                self.certificate.found,
                self.certificate.envelope_id,
                self.certificate.completed_on,
                self.certificate.no_signer,
                self.certificate.one_signer,
                self.certificate.more_signers
            ),
            format!("signer check  {}", listed(self.signer_check.iter().map(|(k, n)| (k.key(), *n)).collect())),
            format!("signer name   {}", listed(self.signer_name.iter().map(|(k, n)| (k.key(), *n)).collect())),
            format!("signer email  {}", listed(self.signer_email.iter().map(|(k, n)| (k.key(), *n)).collect())),
            format!(
                "unplaced      {} applications hold {} runs · by the label before them: {}",
                self.unplaced.applications,
                self.unplaced.runs,
                counted(&self.unplaced.after)
            ),
            String::new(),
            format!(
                "{:<34}{:>7}{:>7}{:>7}{:>9}{:>11}{:>10}",
                "field", "read", "blank", "n/a", "refused", "unlocated", "doubtful"
            ),
        ];
        for (field, counts) in self.fields.iter() {
            let count = |pick: &dyn Fn(&Outcome) -> bool| -> u32 {
                counts.0.iter().filter(|(outcome, _)| pick(outcome)).map(|(_, n)| n).sum()
            };
            let details: Vec<String> = counts
                .0
                .iter()
                .filter(|(outcome, _)| !matches!(outcome, Outcome::Read | Outcome::Blank | Outcome::NotApplicable))
                .map(|(outcome, n)| format!("{} {n}", outcome.key()))
                .collect();
            let line = format!(
                "{:<34}{:>7}{:>7}{:>7}{:>9}{:>11}{:>10}  {}",
                field.to_string(),
                count(&|o| *o == Outcome::Read),
                count(&|o| *o == Outcome::Blank),
                count(&|o| *o == Outcome::NotApplicable),
                count(&|o| matches!(o, Outcome::Refused(_))),
                count(&|o| matches!(o, Outcome::LabelMissing | Outcome::LabelOutOfPlace)),
                count(&|o| matches!(o, Outcome::Doubtful(_))),
                details.join(" · ")
            );
            lines.push(line.trim_end().to_string());
        }
        if let Some(offsets) = &self.offsets {
            lines.push(String::new());
            lines.push("offsets from the BUSINESS INFORMATION heading, in whole points (documents)".to_string());
            for (field, histogram) in offsets {
                let render =
                    |map: &BTreeMap<i32, u32>| join(map.iter().map(|(at, n)| format!("{at:+} ×{n}")).collect());
                lines.push(format!("{:<34}dx {}", field.to_string(), render(&histogram.dx)));
                lines.push(format!("{:<34}dy {}", "", render(&histogram.dy)));
            }
        }
        if let Some(shapes) = &self.shapes {
            lines.push(String::new());
            lines.push(format!("shapes of refused values (fewer than {SHAPE_MIN_COUNT} fold into other)"));
            for (field, shapes) in shapes {
                let folded = fold(shapes);
                lines.push(format!(
                    "{:<34}{}",
                    field.to_string(),
                    join(folded.iter().map(|(shape, n)| format!("{shape} ×{n}")).collect())
                ));
            }
        }
        lines
    }
}

#[cfg(test)]
mod tests {
    use time::macros::date;

    use super::*;
    use crate::extract::read;
    use crate::fields::BusinessField;
    use crate::page::PdfFacts;
    use crate::page::build::PageBuilder;
    use crate::support::form::{Form, certificate, pdfescape, sample_values};

    fn reading(form: &Form) -> Reading {
        let pages = vec![
            form.draw(PageBuilder::new()).build(),
            certificate(PageBuilder::new(), &[("SAMPLE OWNER", "owner@example.com")]).build(),
        ];
        read(&PdfFacts { created_on: Some(date!(2026 - 10 - 21)), pages })
    }

    fn sample_tally() -> Tally {
        let mut tally = Tally::new(TallyOptions { offsets: true, shapes: true });
        tally.add(&reading(&Form::word()));
        tally.add(&reading(&Form { layout: pdfescape(), ..Form::word() }));
        let principal = |field| FieldId::Owner(OwnerSlot::Principal, field);
        tally.add(&reading(&Form::word().set(principal(OwnerField::Name), "SAMPLE Q. OWNER")));
        tally.add(&reading(&Form::word().set(principal(OwnerField::Email), "Owner@Example.com")));
        tally.add(&reading(&Form::word().set(principal(OwnerField::Name), "NORTHWIND OWNER")));
        let start = FieldId::Business(BusinessField::StartDate);
        for text in ["2019", "2018", "2020", "Q2 2019"] {
            tally.add(&reading(&Form::word().set(start, text)));
        }
        tally.add_failure(Failure::Worker(WorkerError::Read(ReadError::NotPdf)));
        tally.add_failure(Failure::Unopened);
        tally
    }

    #[test]
    fn a_tally_counts_documents_fields_and_failures() {
        let tally = sample_tally();
        assert_eq!(tally.pdf_files, 11);
        assert_eq!(tally.documents.get(&DocumentKind::Application), Some(&9));
        assert_eq!(tally.layouts.get("word"), Some(&8));
        assert_eq!(tally.layouts.get("pdfescape"), Some(&1));
        assert_eq!(tally.signer_check.get(&SignerCheck::Agreement), Some(&8));
        assert_eq!(tally.signer_check.get(&SignerCheck::Disagreement), Some(&1));
        assert_eq!(tally.signer_name.get(&DetailCheck::Difference), Some(&1));
        assert_eq!(tally.signer_email.get(&DetailCheck::Agreement), Some(&9));
        let start = tally.fields.get(FieldId::Business(BusinessField::StartDate));
        assert_eq!(start.0.get(&Outcome::Read), Some(&5));
        assert_eq!(start.0.get(&Outcome::Refused(crate::values::Refusal::Format)), Some(&4));
        let lines = tally.lines().join("\n");
        assert!(lines.contains("failures      not_pdf 1 · unopened 1"), "{lines}");
        assert!(lines.contains("9999 ×3 · other ×1"), "{lines}");
        assert!(lines.contains("dy +15 ×1 · +18 ×8"), "{lines}");
        assert!(lines.contains("signer name   agreement 8 · difference 1"), "{lines}");
        assert!(lines.contains("signer email  agreement 9"), "{lines}");
    }

    #[test]
    fn refused_emails_are_counted_by_why_and_never_by_their_text() {
        let mut tally = Tally::new(TallyOptions { offsets: false, shapes: true });
        let email = FieldId::Business(BusinessField::Email);
        for text in ["office at example.com", "office@example.com/", "office @ example.com."] {
            tally.add(&reading(&Form::word().set(email, text)));
        }
        let fields = tally.fields.get(email);
        assert_eq!(fields.0.get(&Outcome::Read), Some(&1));
        let lines = tally.lines().join("\n");
        assert!(lines.contains("refused.format.no_at 1 · refused.format.trailing_punctuation 1"), "{lines}");
        let json = serde_json::to_string(&tally).unwrap();
        assert!(json.contains(r#""refused.format.no_at":1"#), "{json}");
        assert!(!lines.contains("office") && !json.contains("office"), "a report holds an address");
    }

    #[test]
    fn a_tally_holds_no_fabricated_value() {
        let tally = sample_tally();
        let text = tally.lines().join("\n");
        let json = serde_json::to_string(&tally).unwrap();
        let mut values: Vec<&str> = sample_values().into_iter().map(|(_, value)| value).collect();
        values.extend(["SAMPLE OWNER", "owner@example.com", "Q2 2019", "0F8FAD5B", "ORIGINATOR"]);
        values.extend(["SAMPLE Q. OWNER", "NORTHWIND OWNER", "Owner@Example.com"]);
        for value in values.into_iter().filter(|value| value.len() > 3) {
            assert!(!text.contains(value), "the text report holds a value");
            assert!(!json.contains(value), "the JSON report holds a value");
        }
        assert!(json.contains(r#""9999":3"#) && json.contains(r#""other":1"#), "shapes are folded in JSON too");
    }
}
