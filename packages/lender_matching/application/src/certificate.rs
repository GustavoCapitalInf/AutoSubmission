use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};
use time::{Date, Month};

use crate::fields::FieldKind;
use crate::page::{ReadingOrder, TextPage, words};
use crate::values::{Answer, Email, FieldValue, RawText, ReadContext, Word};

/// What a DocuSign Certificate of Completion says about its envelope. It holds no originator
/// detail: signers come only from the rows under "Signer Events", below the originator's block.
#[derive(Serialize, Deserialize)]
pub struct Certificate {
    pub envelope: Option<EnvelopeId>,
    /// The date of the "Completed" row under "Envelope Summary Events".
    #[serde(with = "crate::values::iso_date::option")]
    pub completed_on: Option<Date>,
    /// The rows under "Signer Events", in order.
    pub signers: Vec<Signer>,
}

/// 32 upper-case hexadecimal digits.
#[derive(Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EnvelopeId(String);

impl EnvelopeId {
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Serialize, Deserialize)]
pub struct Signer {
    name: String,
    email: String,
}

impl Signer {
    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn email(&self) -> &str {
        &self.email
    }
}

struct Line {
    text: String,
    words: Vec<Word>,
}

fn page_lines(page: &TextPage) -> Vec<Line> {
    let order = ReadingOrder::new(page);
    order
        .lines()
        .into_iter()
        .map(|run| {
            let positions: Vec<usize> = run.collect();
            let words = words(&order, &positions);
            let text = words.iter().map(|word| word.text.as_str()).collect::<Vec<_>>().join(" ");
            Line { text, words }
        })
        .collect()
}

/// Reads from the last page after the first that holds a "Certificate Of Completion" heading to the
/// end. A row whose shape does not fit gives nothing rather than a guess.
pub(crate) fn read_certificate(pages: &[TextPage]) -> Option<Certificate> {
    let is_heading = |line: &Line| line.text.to_lowercase().contains("certificate of completion");
    let start = (1..pages.len()).rev().find(|&index| page_lines(&pages[index]).iter().any(is_heading))?;
    let lines: Vec<Line> = pages[start..].iter().flat_map(page_lines).collect();
    let envelope = agreed_value(lines.iter().filter_map(envelope_id));
    let summary = lines.iter().position(|line| line.text.starts_with("Envelope Summary Events"));
    let completed_on = summary.and_then(|at| {
        agreed_value(lines[at + 1..].iter().filter(|line| line.text.starts_with("Completed ")).filter_map(first_date))
    });
    Some(Certificate { envelope, completed_on, signers: signers(&lines) })
}

fn agreed_value<T: PartialEq>(mut items: impl Iterator<Item = T>) -> Option<T> {
    let first = items.next()?;
    items.all(|item| item == first).then_some(first)
}

fn envelope_id(line: &Line) -> Option<EnvelopeId> {
    let (_, after) = line.text.split_once("Envelope Id:")?;
    let token = after.split_whitespace().next()?;
    let hex: String = match token.len() {
        32 => token.to_string(),
        36 if [8, 13, 18, 23].iter().all(|at| token.as_bytes()[*at] == b'-') => token.replace('-', ""),
        _ => return None,
    };
    (hex.len() == 32 && hex.bytes().all(|b| b.is_ascii_hexdigit())).then(|| EnvelopeId(hex.to_ascii_uppercase()))
}

fn first_date(line: &Line) -> Option<Date> {
    line.text.split_whitespace().find_map(|token| {
        let parts: Vec<&str> = token.split('/').collect();
        let [month, day, year] = parts.as_slice() else { return None };
        let digits = |part: &str, widths: &[usize]| {
            (widths.contains(&part.len()) && part.bytes().all(|b| b.is_ascii_digit()))
                .then(|| part.parse::<i32>().ok())?
        };
        let month = Month::try_from(u8::try_from(digits(month, &[1, 2])?).ok()?).ok()?;
        let day = u8::try_from(digits(day, &[1, 2])?).ok()?;
        Date::from_calendar_date(digits(year, &[4])?, month, day).ok()
    })
}

fn reads_as_email(text: &str) -> Option<Email> {
    match FieldKind::Email.read(&RawText::typed(text), &ReadContext::default()) {
        Ok(Answer::Value(FieldValue::Email(email))) if !text.contains(' ') => Some(email),
        _ => None,
    }
}

/// The signer column runs from the left edge to the "Signature" column heading on the "Signer
/// Events" row, and down to the next row that ends in "Events". A signer is an email line in that
/// column and the line above it.
fn signers(lines: &[Line]) -> Vec<Signer> {
    let Some(header) = lines.iter().position(|line| line.text.starts_with("Signer Events")) else {
        return Vec::new();
    };
    let Some(column_end) = lines[header].words.iter().find(|word| word.text == "Signature").map(|word| word.x0) else {
        return Vec::new();
    };
    let mut column: Vec<String> = Vec::new();
    for line in &lines[header + 1..] {
        let text = line
            .words
            .iter()
            .filter(|word| (word.x0 + word.x1) / 2.0 < column_end)
            .map(|word| word.text.as_str())
            .collect::<Vec<_>>()
            .join(" ");
        if text.ends_with("Events") {
            break;
        }
        if !text.is_empty() {
            column.push(text);
        }
    }
    let name_like = |text: &str| text.chars().any(char::is_alphabetic) && !text.contains(['@', ':']);
    column
        .windows(2)
        .filter(|pair| name_like(&pair[0]) && reads_as_email(&pair[1]).is_some())
        .map(|pair| Signer { name: pair[0].clone(), email: pair[1].clone() })
        .collect()
}

/// How the principal owner on the form compares with the certificate's signers.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SignerCheck {
    /// One signer has the owner's name and email.
    Agreement,
    /// No signer, or exactly one by name or by email but not both, corresponds to the owner.
    Disagreement,
    /// Several signers correspond to the owner.
    Ambiguous,
    /// The owner's name or email, or the signers, are missing.
    Unavailable,
}

/// How one of the principal owner's details compares with the signers'.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum DetailCheck {
    /// A signer has the owner's detail.
    Agreement,
    /// No signer has it.
    Difference,
    /// The owner's detail, or the signers, are missing.
    Unavailable,
}

pub struct SignerComparison {
    pub check: SignerCheck,
    pub name: DetailCheck,
    pub email: DetailCheck,
}

fn name_words(name: &str) -> Vec<String> {
    let kept: String = name.chars().filter(|c| c.is_alphanumeric() || c.is_whitespace()).collect();
    kept.to_uppercase().split_whitespace().map(String::from).collect()
}

/// The same set of words, or the same but one more word inside the longer name: a middle name.
fn same_name(a: &str, b: &str) -> bool {
    let (a, b) = (name_words(a), name_words(b));
    let set = |words: &[String]| words.iter().cloned().collect::<BTreeSet<String>>();
    let (long, short) = if a.len() >= b.len() { (a, b) } else { (b, a) };
    let short_set = set(&short);
    if set(&long) == short_set {
        return !short_set.is_empty();
    }
    let extra: Vec<usize> = (0..long.len()).filter(|&i| !short_set.contains(&long[i])).collect();
    let [middle] = extra.as_slice() else { return false };
    short_set.len() >= 2 && short_set.len() + 1 == long.len() && *middle > 0 && *middle + 1 < long.len()
}

/// Names compare by their words, a middle name aside; emails as whole addresses in any case.
pub fn compare_signer(name: Option<&str>, email: Option<&Email>, signers: &[Signer]) -> SignerComparison {
    let address = |email: &Email| format!("{}@{}", email.local(), email.domain()).to_lowercase();
    let by_name: Option<Vec<bool>> =
        name.map(|name| signers.iter().map(|signer| same_name(&signer.name, name)).collect());
    let by_email: Option<Vec<bool>> = email.map(|email| {
        let owner = address(email);
        signers
            .iter()
            .map(|signer| reads_as_email(&signer.email).is_some_and(|other| address(&other) == owner))
            .collect()
    });
    let detail = |matches: &Option<Vec<bool>>| match matches {
        _ if signers.is_empty() => DetailCheck::Unavailable,
        None => DetailCheck::Unavailable,
        Some(matches) if matches.contains(&true) => DetailCheck::Agreement,
        Some(_) => DetailCheck::Difference,
    };
    let check = match (&by_name, &by_email) {
        _ if signers.is_empty() => SignerCheck::Unavailable,
        (Some(by_name), Some(by_email)) => {
            let corresponding: Vec<(bool, bool)> = by_name
                .iter()
                .zip(by_email)
                .map(|(name, email)| (*name, *email))
                .filter(|(name, email)| *name || *email)
                .collect();
            match corresponding.as_slice() {
                [(true, true)] => SignerCheck::Agreement,
                [] | [_] => SignerCheck::Disagreement,
                _ => SignerCheck::Ambiguous,
            }
        }
        _ => SignerCheck::Unavailable,
    };
    SignerComparison { check, name: detail(&by_name), email: detail(&by_email) }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::page::build::PageBuilder;
    use crate::support::form::certificate;
    use time::macros::date;

    fn certificate_page(signers: &[(&str, &str)]) -> TextPage {
        certificate(PageBuilder::new(), signers).build()
    }

    fn other_page() -> TextPage {
        PageBuilder::new().text("Calibri", 11.0, 40.0, 40.0, "SAMPLE paperwork").build()
    }

    #[test]
    fn the_certificate_gives_the_envelope_the_completion_day_and_the_signers_only() {
        let pages = [other_page(), certificate_page(&[("SAMPLE OWNER", "owner@example.com")])];
        let certificate = read_certificate(&pages).expect("a certificate");
        assert_eq!(certificate.envelope.as_ref().map(EnvelopeId::as_str), Some("0F8FAD5BD9CB469FA16570867728950E"));
        assert_eq!(certificate.completed_on, Some(date!(2026 - 10 - 20)));
        let signers: Vec<(&str, &str)> = certificate.signers.iter().map(|s| (s.name(), s.email())).collect();
        assert_eq!(signers, [("SAMPLE OWNER", "owner@example.com")]);
    }

    #[test]
    fn the_originator_is_never_read() {
        let pages = [other_page(), certificate_page(&[("SAMPLE OWNER", "owner@example.com")])];
        let certificate = read_certificate(&pages).unwrap();
        for signer in &certificate.signers {
            assert!(!signer.name().contains("ORIGINATOR") && !signer.email().contains("originator"));
        }
    }

    #[test]
    fn two_signers_and_a_certificate_after_other_pages() {
        let pages = [
            other_page(),
            other_page(),
            certificate_page(&[("SAMPLE OWNER", "owner@example.com"), ("NORTHWIND PARTNER", "partner@example.com")]),
        ];
        let certificate = read_certificate(&pages).unwrap();
        assert_eq!(certificate.signers.len(), 2);
        assert_eq!(certificate.signers[1].name(), "NORTHWIND PARTNER");
    }

    #[test]
    fn no_certificate_without_its_heading_after_the_first_page() {
        assert!(read_certificate(&[certificate_page(&[("SAMPLE OWNER", "owner@example.com")])]).is_none());
        assert!(read_certificate(&[other_page(), other_page()]).is_none());
    }

    #[test]
    fn a_signer_row_without_a_name_line_gives_no_signer() {
        let pages = [other_page(), certificate_page(&[("", "owner@example.com")])];
        assert!(read_certificate(&pages).unwrap().signers.is_empty());
    }

    fn email(text: &str) -> Email {
        reads_as_email(text).unwrap()
    }

    #[test]
    fn the_signer_check_needs_one_signer_with_both_name_and_email() {
        let signers = [
            Signer { name: "SAMPLE OWNER".to_string(), email: "owner@example.com".to_string() },
            Signer { name: "NORTHWIND PARTNER".to_string(), email: "partner@example.com".to_string() },
        ];
        let check = |name: &str, address: &str| compare_signer(Some(name), Some(&email(address)), &signers).check;
        assert_eq!(check("Sample  Owner", "owner@EXAMPLE.com"), SignerCheck::Agreement);
        assert_eq!(check("SAMPLE OWNER", "Owner@Example.com"), SignerCheck::Agreement, "the whole address in any case");
        assert_eq!(check("SAMPLE OWNER", "other@example.com"), SignerCheck::Disagreement);
        assert_eq!(check("CONTOSO OWNER", "owner@example.com"), SignerCheck::Disagreement);
        assert_eq!(check("FABRIKAM", "nobody@example.com"), SignerCheck::Disagreement);
        assert_eq!(check("SAMPLE OWNER", "partner@example.com"), SignerCheck::Ambiguous);
        let unavailable = compare_signer(None, Some(&email("owner@example.com")), &signers);
        assert_eq!((unavailable.check, unavailable.name), (SignerCheck::Unavailable, DetailCheck::Unavailable));
        assert_eq!(unavailable.email, DetailCheck::Agreement);
        let no_signers = compare_signer(Some("SAMPLE OWNER"), Some(&email("owner@example.com")), &[]);
        assert_eq!(
            (no_signers.check, no_signers.name, no_signers.email),
            (SignerCheck::Unavailable, DetailCheck::Unavailable, DetailCheck::Unavailable)
        );
    }

    #[test]
    fn names_agree_by_their_words_with_a_middle_name_aside() {
        for (a, b) in [
            ("SAMPLE OWNER", "Sample  Owner"),
            ("OWNER, SAMPLE", "SAMPLE OWNER"),
            ("SAMPLE Q. OWNER", "SAMPLE OWNER"),
            ("SAMPLE OWNER", "SAMPLE NORTHWIND OWNER"),
            ("O'NEIL SAMPLE", "ONEIL SAMPLE"),
        ] {
            assert!(same_name(a, b), "{a} and {b} agree");
        }
        for (a, b) in [
            ("SAMPLE OWNER JR", "SAMPLE OWNER"),
            ("Q SAMPLE OWNER", "SAMPLE OWNER"),
            ("SAMPLE", "SAMPLE OWNER"),
            ("SAMPLE ANNE MARIE OWNER", "SAMPLE OWNER"),
            ("SAMPLE OWNER", "SAMPLE PARTNER"),
            ("", ""),
        ] {
            assert!(!same_name(a, b), "{a} and {b} differ");
        }
    }

    #[test]
    fn the_name_and_the_email_are_also_checked_one_by_one() {
        let signers = [Signer { name: "SAMPLE OWNER".to_string(), email: "owner@example.com".to_string() }];
        let compare = |name: &str, address: &str| {
            let comparison = compare_signer(Some(name), Some(&email(address)), &signers);
            (comparison.check, comparison.name, comparison.email)
        };
        use DetailCheck::{Agreement, Difference};
        assert_eq!(compare("SAMPLE Q OWNER", "Owner@example.com"), (SignerCheck::Agreement, Agreement, Agreement));
        assert_eq!(compare("NORTHWIND OWNER", "owner@example.com"), (SignerCheck::Disagreement, Difference, Agreement));
        assert_eq!(compare("SAMPLE OWNER", "other@example.com"), (SignerCheck::Disagreement, Agreement, Difference));
    }
}
