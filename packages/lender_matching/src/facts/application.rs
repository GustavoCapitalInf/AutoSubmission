use std::collections::BTreeMap;
use std::fmt;

pub use lender_matching_application::{Jurisdiction, YearMonth};
use serde::{Deserialize, Serialize};
use time::{Date, Month, OffsetDateTime};

use super::Interval;

/// Whole months from `from` to `to`: the largest `m` with `from + m months <= to`, a day past
/// the end of a shorter month counting as that month's last day. Zero when `to` is earlier.
pub fn whole_months(from: Date, to: Date) -> i64 {
    if to < from {
        return 0;
    }
    let mut months =
        i64::from(to.year() - from.year()) * 12 + i64::from(to.month() as u8) - i64::from(from.month() as u8);
    if add_months(from, months) > to {
        months -= 1;
    }
    months.max(0)
}

fn add_months(date: Date, months: i64) -> Date {
    let index = i64::from(date.year()) * 12 + i64::from(date.month() as u8 - 1) + months;
    let year = i32::try_from(index.div_euclid(12)).expect("year in range");
    let month = Month::try_from(u8::try_from(index.rem_euclid(12) + 1).expect("1..=12")).expect("1..=12");
    let day = date.day().min(month.length(year));
    Date::from_calendar_date(year, month, day).expect("clamped day is valid")
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EntityKind {
    SoleProprietorship,
    Partnership,
    Llc,
    Corporation,
    NonProfit,
    Other,
}

impl EntityKind {
    pub const ALL: [EntityKind; 6] = [
        EntityKind::SoleProprietorship,
        EntityKind::Partnership,
        EntityKind::Llc,
        EntityKind::Corporation,
        EntityKind::NonProfit,
        EntityKind::Other,
    ];

    pub fn key(self) -> &'static str {
        match self {
            EntityKind::SoleProprietorship => "sole_proprietorship",
            EntityKind::Partnership => "partnership",
            EntityKind::Llc => "llc",
            EntityKind::Corporation => "corporation",
            EntityKind::NonProfit => "non_profit",
            EntityKind::Other => "other",
        }
    }

    pub fn from_key(key: &str) -> Option<EntityKind> {
        EntityKind::ALL.into_iter().find(|kind| kind.key() == key)
    }

    pub fn label(self) -> &'static str {
        match self {
            EntityKind::SoleProprietorship => "sole proprietorship",
            EntityKind::Partnership => "partnership",
            EntityKind::Llc => "LLC",
            EntityKind::Corporation => "corporation",
            EntityKind::NonProfit => "non-profit",
            EntityKind::Other => "other",
        }
    }
}

/// A slug that names a row of `industries`. Requests get one only from `Industries::resolve`, which
/// refuses an unknown or retired slug.
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
pub struct IndustryId(String);

impl IndustryId {
    pub fn proposed(slug: String) -> IndustryId {
        IndustryId(slug)
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for IndustryId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Industry {
    pub id: IndustryId,
    pub label: String,
    pub retired: bool,
}

/// The industry picklist, retired entries included so stored rules can still name them.
#[derive(Clone, Default, Debug)]
pub struct Industries {
    by_slug: BTreeMap<String, Industry>,
}

impl Industries {
    pub fn new(rows: impl IntoIterator<Item = (String, String, bool)>) -> Industries {
        let by_slug = rows
            .into_iter()
            .map(|(slug, label, retired)| (slug.clone(), Industry { id: IndustryId(slug), label, retired }))
            .collect();
        Industries { by_slug }
    }

    pub fn resolve(&self, slug: &str) -> Option<IndustryId> {
        self.by_slug.get(slug).filter(|industry| !industry.retired).map(|industry| industry.id.clone())
    }

    pub fn by_label(&self, label: &str) -> Option<IndustryId> {
        let wanted = label.trim();
        self.by_slug
            .values()
            .find(|industry| industry.label.eq_ignore_ascii_case(wanted))
            .map(|industry| industry.id.clone())
    }

    pub fn label<'a>(&'a self, slug: &'a str) -> &'a str {
        self.by_slug.get(slug).map_or(slug, |industry| industry.label.as_str())
    }

    pub fn all(&self) -> impl Iterator<Item = &Industry> {
        self.by_slug.values()
    }

    pub fn active(&self) -> impl Iterator<Item = &Industry> {
        self.by_slug.values().filter(|industry| !industry.retired)
    }

    pub fn slug_for(&self, label: &str) -> String {
        let mut base = String::new();
        for word in label.split(|c: char| !c.is_ascii_alphanumeric()).filter(|word| !word.is_empty()) {
            if !base.is_empty() {
                base.push('-');
            }
            base.push_str(&word.to_ascii_lowercase());
        }
        if base.is_empty() {
            base.push_str("industry");
        }
        let mut slug = base.clone();
        let mut suffix = 2;
        while self.by_slug.contains_key(&slug) {
            slug = format!("{base}-{suffix}");
            suffix += 1;
        }
        slug
    }
}

#[derive(Clone, Default, PartialEq, Debug, Serialize, Deserialize)]
pub struct ApplicationFacts {
    pub business_state: Option<Jurisdiction>,
    pub business_start: Option<YearMonth>,
    pub entity: Option<EntityKind>,
    /// A form value such as 650-700 stays a range.
    pub estimated_fico: Option<Interval>,
    pub requested_amount_cents: Option<i64>,
    pub open_judgements: Option<bool>,
    pub bankruptcy: Option<bool>,
    pub tax_liens: Option<bool>,
    /// Evidence only: the industry fact needs a person's confirmation.
    pub industry_suggestion: Option<IndustryId>,
}

#[derive(Clone, Default, PartialEq, Debug, Serialize, Deserialize)]
pub struct Confirmations {
    pub industry: Option<Confirmed<IndustryId>>,
    pub default_history: Option<Confirmed<bool>>,
    pub home_based: Option<Confirmed<bool>>,
    pub open_lawsuit: Option<Confirmed<bool>>,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Confirmed<T> {
    pub value: T,
    /// The signed-in account's username.
    pub by: String,
    #[serde(with = "time::serde::rfc3339")]
    pub at: OffsetDateTime,
}

#[cfg(test)]
pub(crate) fn test_industries() -> Industries {
    Industries::new([
        ("construction-contractor".to_string(), "Construction / Contractor".to_string(), false),
        ("transportation-trucking".to_string(), "Transportation / Trucking".to_string(), false),
        ("cannabis".to_string(), "Cannabis".to_string(), false),
        ("general-retail".to_string(), "General Retail".to_string(), false),
        ("crypto".to_string(), "Crypto".to_string(), true),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;
    use time::macros::date;

    #[test]
    fn whole_months_counts_completed_months_only() {
        let cases = [
            (date!(2025 - 10 - 01), date!(2026 - 10 - 23), 12),
            (date!(2025 - 10 - 31), date!(2026 - 10 - 23), 11),
            (date!(2026 - 01 - 31), date!(2026 - 02 - 28), 1),
            (date!(2026 - 01 - 31), date!(2026 - 02 - 27), 0),
            (date!(2026 - 10 - 31), date!(2026 - 10 - 23), 0),
        ];
        for (from, to, expected) in cases {
            assert_eq!(whole_months(from, to), expected, "{from} to {to}");
        }
    }

    #[test]
    fn industries_resolve_only_active_slugs() {
        let industries = test_industries();
        assert!(industries.resolve("cannabis").is_some());
        assert!(industries.resolve("crypto").is_none(), "retired");
        assert!(industries.by_label(" crypto ").is_some(), "labels still find retired industries");
        assert_eq!(industries.slug_for("Auto Repair / Collision / Tire"), "auto-repair-collision-tire");
        assert_eq!(industries.slug_for("Cannabis"), "cannabis-2");
    }
}
