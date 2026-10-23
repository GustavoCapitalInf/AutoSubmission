use std::collections::BTreeMap;
use std::fmt;

use serde::{Deserialize, Deserializer, Serialize, Serializer};
use time::{Date, Month, OffsetDateTime};

use super::Interval;

/// A calendar month, written `YYYY-MM`.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct YearMonth {
    year: i32,
    month: u8,
}

impl YearMonth {
    pub fn new(year: i32, month: u8) -> Option<YearMonth> {
        ((1..=12).contains(&month) && (1000..=9999).contains(&year)).then_some(YearMonth { year, month })
    }

    pub fn of(date: Date) -> YearMonth {
        YearMonth { year: date.year(), month: date.month() as u8 }
    }

    /// Accepts exactly `YYYY-MM`.
    pub fn parse(text: &str) -> Option<YearMonth> {
        let bytes = text.as_bytes();
        if bytes.len() != 7
            || bytes[4] != b'-'
            || !text[..4].bytes().chain(text[5..].bytes()).all(|b| b.is_ascii_digit())
        {
            return None;
        }
        YearMonth::new(text[..4].parse().ok()?, text[5..].parse().ok()?)
    }

    fn time_month(self) -> Month {
        Month::try_from(self.month).expect("month is 1..=12 by construction")
    }

    pub fn first_day(self) -> Date {
        Date::from_calendar_date(self.year, self.time_month(), 1).expect("valid calendar month")
    }

    pub fn last_day(self) -> Date {
        let month = self.time_month();
        Date::from_calendar_date(self.year, month, month.length(self.year)).expect("valid calendar month")
    }

    pub fn next(self) -> YearMonth {
        if self.month == 12 {
            YearMonth { year: self.year + 1, month: 1 }
        } else {
            YearMonth { year: self.year, month: self.month + 1 }
        }
    }

    /// Every month from `self` to `last`, both included; empty when `last` is earlier.
    pub fn through(self, last: YearMonth) -> Vec<YearMonth> {
        let mut months = Vec::new();
        let mut month = self;
        while month <= last {
            months.push(month);
            month = month.next();
        }
        months
    }
}

impl fmt::Display for YearMonth {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:04}-{:02}", self.year, self.month)
    }
}

impl Serialize for YearMonth {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.collect_str(self)
    }
}

impl<'de> Deserialize<'de> for YearMonth {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let text = String::deserialize(deserializer)?;
        YearMonth::parse(&text).ok_or_else(|| serde::de::Error::custom("expected a YYYY-MM month"))
    }
}

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

/// A US state, DC, a US territory or a Canadian province or territory, by postal code.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct Jurisdiction(&'static str);

const JURISDICTIONS: [&str; 69] = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR", "GU", "VI", "AS", "MP", "AB",
    "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
];

impl Jurisdiction {
    /// Takes a postal code in any case. The Info Hub's `QB` is not a postal code; the import maps it.
    pub fn from_code(code: &str) -> Option<Jurisdiction> {
        let upper = code.trim().to_ascii_uppercase();
        JURISDICTIONS.iter().find(|known| **known == upper).map(|known| Jurisdiction(known))
    }

    pub fn code(self) -> &'static str {
        self.0
    }
}

impl fmt::Display for Jurisdiction {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.0)
    }
}

impl Serialize for Jurisdiction {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.serialize_str(self.0)
    }
}

impl<'de> Deserialize<'de> for Jurisdiction {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let text = String::deserialize(deserializer)?;
        Jurisdiction::from_code(&text).ok_or_else(|| serde::de::Error::custom("unknown jurisdiction code"))
    }
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
    /// A slug the Info Hub plan proposes for a label the picklist lacks; `info_hub::run` adds the
    /// industry before it writes a rule naming it.
    pub fn unsaved(slug: String) -> IndustryId {
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

    /// An active industry by slug.
    pub fn resolve(&self, slug: &str) -> Option<IndustryId> {
        self.by_slug.get(slug).filter(|industry| !industry.retired).map(|industry| industry.id.clone())
    }

    /// Any industry, retired ones included, whose label matches ignoring case and surrounding space.
    pub fn by_label(&self, label: &str) -> Option<IndustryId> {
        let wanted = label.trim();
        self.by_slug
            .values()
            .find(|industry| industry.label.eq_ignore_ascii_case(wanted))
            .map(|industry| industry.id.clone())
    }

    pub fn label<'a>(&'a self, id: &'a IndustryId) -> &'a str {
        self.by_slug.get(&id.0).map_or(id.as_str(), |industry| industry.label.as_str())
    }

    pub fn all(&self) -> impl Iterator<Item = &Industry> {
        self.by_slug.values()
    }

    pub fn active(&self) -> impl Iterator<Item = &Industry> {
        self.by_slug.values().filter(|industry| !industry.retired)
    }

    /// The slug a new label would get: lower-case words joined by `-`, with a numeric suffix when
    /// another industry already holds that slug.
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

/// What the caller states about a deal, already parsed.
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

/// Facts that a signed-in person confirmed on the match page.
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
    fn year_month_parses_only_the_canonical_form() {
        assert_eq!(YearMonth::parse("2026-09"), YearMonth::new(2026, 9));
        for bad in ["2026-9", "2026-13", "2026-00", "26-09", "2026/09", " 2026-09", "2026-09-01"] {
            assert_eq!(YearMonth::parse(bad), None, "{bad}");
        }
    }

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
    fn jurisdictions_take_postal_codes_only() {
        assert_eq!(Jurisdiction::from_code("tx").map(Jurisdiction::code), Some("TX"));
        assert_eq!(Jurisdiction::from_code("QC").map(Jurisdiction::code), Some("QC"));
        assert_eq!(Jurisdiction::from_code("QB"), None);
        assert_eq!(Jurisdiction::from_code("XX"), None);
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
