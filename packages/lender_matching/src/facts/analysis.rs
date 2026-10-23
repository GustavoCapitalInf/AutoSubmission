//! The only code that knows the v1 analysis package shape (`packages/bank_statement_analysis/docs/api/v1.md`).

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Deserializer, Serialize};
use time::Date;
use time::format_description::well_known::Iso8601;
use uuid::Uuid;

use super::application::YearMonth;
use super::{Basis, Fact, Gap, Interval, Source};

/// The parts of a ready v1 package that matching reads. Built only by `parse`.
#[derive(Clone, PartialEq, Debug)]
pub struct ReadyPackage {
    pub package_id: Uuid,
    pub revision: String,
    pub review_required: bool,
    pub figures: Option<Figures>,
    /// One per included account of an analysed statement.
    pub periods: Vec<AccountPeriod>,
}

#[derive(Clone, PartialEq, Debug)]
pub struct Figures {
    pub currency: Option<String>,
    pub months: u32,
    pub monthly_true_revenue_cents: Option<i64>,
    pub confirmed_funders: usize,
    pub positions_by_month: Vec<MonthPositions>,
}

#[derive(Clone, PartialEq, Debug)]
pub struct MonthPositions {
    pub month: YearMonth,
    pub active: Option<u32>,
    pub possible: Option<u32>,
}

#[derive(Clone, Default, PartialEq, Debug)]
pub struct AccountPeriod {
    pub start: Option<Date>,
    pub end: Option<Date>,
    pub negative_days: Option<u32>,
    pub true_revenue_count: Option<u32>,
    pub deposit_count: Option<u32>,
}

#[derive(Clone, PartialEq, Debug)]
pub enum Parsed {
    Processing,
    Ready(ReadyPackage),
}

/// Why a body is not a v1 package. It names a position or a field, not a body value, so it is safe to log.
#[derive(Clone, PartialEq, Debug, thiserror::Error)]
#[error("{0}")]
pub struct ContractMismatch(pub String);

/// Reads fields by name and ignores unknown fields, as v1 allows. Refuses a major version other
/// than 1, another package id, a value outside a closed set, a missing or mistyped field, a
/// fractional number, and a date or month in another format.
pub fn parse(body: &[u8], expected: Uuid) -> Result<Parsed, ContractMismatch> {
    let wire: WirePackage = serde_json::from_slice(body).map_err(|error| {
        ContractMismatch(format!("{:?} error at line {} column {}", error.classify(), error.line(), error.column()))
    })?;
    let (api_version, package_id) = match &wire {
        WirePackage::Processing { api_version, package_id } | WirePackage::Ready { api_version, package_id, .. } => {
            (api_version, package_id)
        }
    };
    if !api_version.starts_with("1.") {
        return Err(ContractMismatch("api_version is not 1.x".to_string()));
    }
    if Uuid::parse_str(package_id).ok() != Some(expected) {
        return Err(ContractMismatch("package_id is not the requested package".to_string()));
    }
    let WirePackage::Ready { revision, review, figures, documents, .. } = wire else {
        return Ok(Parsed::Processing);
    };
    if revision.len() != 64 || !revision.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)) {
        return Err(ContractMismatch("revision is not 64 lowercase hex digits".to_string()));
    }
    let figures = figures.map(WireFigures::parse).transpose()?;
    let mut periods = Vec::new();
    for document in documents {
        let WireDocument::Analysed { accounts } = document else { continue };
        for account in accounts {
            if let WireAccount::Included {
                period_start,
                period_end,
                negative_days,
                true_revenue_count,
                deposit_count,
            } = account
            {
                periods.push(AccountPeriod {
                    start: period_start.as_deref().map(parse_date).transpose()?,
                    end: period_end.as_deref().map(parse_date).transpose()?,
                    negative_days,
                    true_revenue_count,
                    deposit_count,
                });
            }
        }
    }
    Ok(Parsed::Ready(ReadyPackage {
        package_id: expected,
        revision,
        review_required: review.required,
        figures,
        periods,
    }))
}

fn parse_date(text: &str) -> Result<Date, ContractMismatch> {
    if text.len() != 10 {
        return Err(ContractMismatch("a period date is not YYYY-MM-DD".to_string()));
    }
    Date::parse(text, &Iso8601::DATE).map_err(|_| ContractMismatch("a period date is not YYYY-MM-DD".to_string()))
}

/// Makes a nullable field required: present as a value or as `null`.
fn nullable<'de, D: Deserializer<'de>, T: Deserialize<'de>>(deserializer: D) -> Result<Option<T>, D::Error> {
    Option::<T>::deserialize(deserializer)
}

#[derive(Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
enum WirePackage {
    Processing {
        api_version: String,
        package_id: String,
    },
    Ready {
        api_version: String,
        package_id: String,
        revision: String,
        review: WireReview,
        #[serde(deserialize_with = "nullable")]
        figures: Option<WireFigures>,
        documents: Vec<WireDocument>,
    },
}

#[derive(Deserialize)]
struct WireReview {
    required: bool,
    #[serde(rename = "decision")]
    _decision: WireDecision,
}

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
enum WireDecision {
    Approved,
    LimitedReview,
    ReviewRequired,
}

#[derive(Deserialize)]
struct WireFigures {
    #[serde(deserialize_with = "nullable")]
    currency: Option<String>,
    #[serde(deserialize_with = "nullable", rename = "currency_refusal")]
    _currency_refusal: Option<WireCurrencyRefusal>,
    months: u32,
    #[serde(deserialize_with = "nullable")]
    monthly_true_revenue_cents: Option<i64>,
    funders: Vec<serde::de::IgnoredAny>,
    active_positions_by_month: Vec<WireMonthPositions>,
}

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
enum WireCurrencyRefusal {
    MultipleCurrencies,
    UndeterminedStatementCurrency,
}

impl WireFigures {
    fn parse(self) -> Result<Figures, ContractMismatch> {
        let positions_by_month = self
            .active_positions_by_month
            .into_iter()
            .map(|row| {
                Ok(MonthPositions {
                    month: YearMonth::parse(&row.month)
                        .ok_or_else(|| ContractMismatch("a positions month is not YYYY-MM".to_string()))?,
                    active: row.active_positions,
                    possible: row.possible_positions,
                })
            })
            .collect::<Result<_, ContractMismatch>>()?;
        Ok(Figures {
            currency: self.currency,
            months: self.months,
            monthly_true_revenue_cents: self.monthly_true_revenue_cents,
            confirmed_funders: self.funders.len(),
            positions_by_month,
        })
    }
}

#[derive(Deserialize)]
struct WireMonthPositions {
    month: String,
    #[serde(deserialize_with = "nullable")]
    active_positions: Option<u32>,
    #[serde(deserialize_with = "nullable")]
    possible_positions: Option<u32>,
}

#[derive(Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
enum WireDocument {
    Analysed { accounts: Vec<WireAccount> },
    Failed {},
    Duplicate {},
}

#[derive(Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
enum WireAccount {
    Included {
        #[serde(deserialize_with = "nullable")]
        period_start: Option<String>,
        #[serde(deserialize_with = "nullable")]
        period_end: Option<String>,
        #[serde(deserialize_with = "nullable")]
        negative_days: Option<u32>,
        #[serde(deserialize_with = "nullable")]
        true_revenue_count: Option<u32>,
        #[serde(deserialize_with = "nullable")]
        deposit_count: Option<u32>,
    },
    Excluded {},
}

/// One statement month: the included account periods that stand for it, combined. Each interval
/// contains the true value. `month` is None for a statement without a readable period.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct StatementMonth {
    pub month: Option<YearMonth>,
    pub negative_days: Interval,
    pub deposits: Interval,
}

/// The analysis facts of one deal, before application facts join them.
pub struct AnalysisFacts {
    pub monthly_true_revenue: Fact<Interval>,
    pub worst_month_negative_days: Fact<Interval>,
    pub worst_month_deposits: Fact<Interval>,
    pub new_position: Fact<Interval>,
    pub statement_months: Fact<Interval>,
    pub funder_payment_history: Fact<bool>,
    pub months: Vec<StatementMonth>,
}

const REVENUE: &str = "figures.monthly_true_revenue_cents";
const NEGATIVE_DAYS: &str = "documents[].accounts[].negative_days";
const DEPOSITS: &str = "documents[].accounts[].true_revenue_count..deposit_count";
const POSITIONS: &str = "figures.active_positions_by_month";
const MONTHS: &str = "figures.months";
const FUNDERS: &str = "figures.funders";

impl AnalysisFacts {
    /// When `review.required` is true, every known fact becomes `Unknown(AnalysisReviewRequired)`
    /// with its value as `seen`: the contract sends such figures to an underwriter first.
    pub fn derive(package: Option<&ReadyPackage>) -> AnalysisFacts {
        let Some(package) = package else { return AnalysisFacts::unknown(Gap::NotSupplied) };
        let Some(figures) = &package.figures else { return AnalysisFacts::unknown(Gap::NoFigures) };
        let monthly = MonthlyDerivation::of(&package.periods);
        let facts = AnalysisFacts {
            monthly_true_revenue: revenue(figures),
            worst_month_negative_days: printed_or_unestablished(monthly.worst_negative_days, NEGATIVE_DAYS),
            worst_month_deposits: printed_or_unestablished(monthly.worst_deposits, DEPOSITS),
            new_position: new_position(&figures.positions_by_month),
            statement_months: printed(
                Interval::between(monthly.covered_months.min(i64::from(figures.months)), i64::from(figures.months))
                    .expect("lo is capped at hi"),
                "figures.months; documents[].accounts[].period_start..period_end",
            ),
            funder_payment_history: if figures.confirmed_funders > 0 {
                printed(true, FUNDERS)
            } else {
                unknown(Gap::NotEstablished, FUNDERS)
            },
            months: monthly.months,
        };
        if package.review_required { facts.held_for_review() } else { facts }
    }

    fn unknown(gap: Gap) -> AnalysisFacts {
        AnalysisFacts {
            monthly_true_revenue: unknown(gap, REVENUE),
            worst_month_negative_days: unknown(gap, NEGATIVE_DAYS),
            worst_month_deposits: unknown(gap, DEPOSITS),
            new_position: unknown(gap, POSITIONS),
            statement_months: unknown(gap, MONTHS),
            funder_payment_history: unknown(gap, FUNDERS),
            months: Vec::new(),
        }
    }

    fn held_for_review(self) -> AnalysisFacts {
        AnalysisFacts {
            monthly_true_revenue: hold(self.monthly_true_revenue),
            worst_month_negative_days: hold(self.worst_month_negative_days),
            worst_month_deposits: hold(self.worst_month_deposits),
            new_position: hold(self.new_position),
            statement_months: hold(self.statement_months),
            funder_payment_history: hold(self.funder_payment_history),
            months: self.months,
        }
    }
}

fn hold<V>(fact: Fact<V>) -> Fact<V> {
    match fact {
        Fact::Known { value, source, .. } => {
            Fact::Unknown { gap: Gap::AnalysisReviewRequired, seen: Some(value), source }
        }
        unknown => unknown,
    }
}

fn printed<V>(value: V, source: &str) -> Fact<V> {
    Fact::Known { value, basis: Basis::Printed, source: Source::Analysis(source.to_string()) }
}

fn unknown<V>(gap: Gap, source: &str) -> Fact<V> {
    Fact::Unknown { gap, seen: None, source: Source::Analysis(source.to_string()) }
}

fn printed_or_unestablished(interval: Option<Interval>, source: &str) -> Fact<Interval> {
    match interval {
        Some(interval) if interval != Interval::at_least(0) => printed(interval, source),
        _ => unknown(Gap::NotEstablished, source),
    }
}

fn revenue(figures: &Figures) -> Fact<Interval> {
    match (figures.currency.as_deref(), figures.monthly_true_revenue_cents) {
        (None, _) => unknown(Gap::CurrencyRefused, REVENUE),
        (Some(currency), _) if currency != "USD" => unknown(Gap::NotUsd, REVENUE),
        (Some(_), None) => unknown(Gap::NotEstablished, REVENUE),
        (Some(_), Some(cents)) => printed(Interval::point(cents), REVENUE),
    }
}

/// The latest listed month's positions plus one; unconfirmed potential lenders widen it upward.
fn new_position(by_month: &[MonthPositions]) -> Fact<Interval> {
    let Some(latest) = by_month.iter().max_by_key(|row| row.month) else {
        return unknown(Gap::NotEstablished, POSITIONS);
    };
    let source = format!("{POSITIONS}[{}]", latest.month);
    let Some(active) = latest.active else { return unknown(Gap::NotEstablished, &source) };
    let first = i64::from(active) + 1;
    let position = match latest.possible {
        None => Interval::at_least(first),
        Some(possible) => Interval::between(first, first + i64::from(possible)).expect("possible is not negative"),
    };
    printed(position, &source)
}

/// The per-month view of the included account periods behind `NumFact::WorstMonthNegativeDays`,
/// `NumFact::WorstMonthDeposits` and `NumFact::StatementMonths`:
///
/// - A period of about one month (28 to 31 days, or at most 31 days mostly in one calendar month)
///   stands for the calendar month holding most of its days and adds its counts there.
/// - A longer period touching `m` months adds `[0, n]` to each of them, and the worst month holds
///   at least `ceil(n / m)` of its negative days.
/// - A period without both dates may fall in any month: it adds `[0, n]` to every month and is
///   also a month of its own.
/// - Several periods in one month give negative days `[max, sum]`, since one day can be negative
///   in two accounts, and deposits that add.
/// - A period's deposits are `[true_revenue_count, deposit_count]`; a null bound widens it.
struct MonthlyDerivation {
    months: Vec<StatementMonth>,
    worst_negative_days: Option<Interval>,
    worst_deposits: Option<Interval>,
    /// Distinct calendar months a dated period stands for or covers in full.
    covered_months: i64,
}

#[derive(Clone, Copy)]
struct MonthTotal {
    negative_lo: i64,
    negative_hi: Option<i64>,
    deposits: Interval,
}

impl MonthTotal {
    const EMPTY: MonthTotal =
        MonthTotal { negative_lo: 0, negative_hi: Some(0), deposits: Interval { lo: 0, hi: Some(0) } };

    fn add(&mut self, negative_days: Interval, deposits: Interval) {
        self.negative_lo = self.negative_lo.max(negative_days.lo());
        self.negative_hi = self.negative_hi.zip(negative_days.hi()).map(|(a, b)| a + b);
        self.deposits = self.deposits.add(deposits);
    }

    fn negative_days(self) -> Interval {
        match self.negative_hi {
            Some(hi) => Interval::between(self.negative_lo, hi).expect("a count's lo is within the sum of his"),
            None => Interval::at_least(self.negative_lo),
        }
    }
}

enum Placement {
    One(YearMonth),
    Spread(Vec<YearMonth>),
    Undated,
}

fn place(start: Option<Date>, end: Option<Date>) -> Placement {
    let (Some(start), Some(end)) = (start, end) else { return Placement::Undated };
    if end < start {
        return Placement::Undated;
    }
    let days = (end - start).whole_days() + 1;
    let touched = YearMonth::of(start).through(YearMonth::of(end));
    let (majority, majority_days) = touched
        .iter()
        .map(|month| (*month, overlap_days(*month, start, end)))
        .max_by(|a, b| a.1.cmp(&b.1).then(b.0.cmp(&a.0)))
        .expect("a dated period touches its own month");
    if days <= 31 && (days >= 28 || majority_days * 2 > days) {
        Placement::One(majority)
    } else {
        Placement::Spread(touched)
    }
}

fn overlap_days(month: YearMonth, start: Date, end: Date) -> i64 {
    let from = start.max(month.first_day());
    let to = end.min(month.last_day());
    if to < from { 0 } else { (to - from).whole_days() + 1 }
}

fn up_to(hi: Option<i64>) -> Interval {
    hi.map_or(Interval::at_least(0), |hi| Interval::between(0, hi).expect("counts are not negative"))
}

fn deposits(period: &AccountPeriod) -> Interval {
    match (period.true_revenue_count, period.deposit_count) {
        (Some(revenue), Some(all)) => Interval::hull(revenue.into(), all.into()),
        (Some(revenue), None) => Interval::at_least(revenue.into()),
        (None, all) => up_to(all.map(i64::from)),
    }
}

impl MonthlyDerivation {
    fn of(periods: &[AccountPeriod]) -> MonthlyDerivation {
        let mut dated: BTreeMap<YearMonth, MonthTotal> = BTreeMap::new();
        let mut covered: BTreeSet<YearMonth> = BTreeSet::new();
        let mut worst_floor = 0;
        let mut undated = 0;
        let mut undated_negative = Interval::point(0);
        let mut undated_deposits = Interval::point(0);
        for period in periods {
            let negative = period.negative_days.map_or(Interval::at_least(0), |n| Interval::point(n.into()));
            let deposits = deposits(period);
            match place(period.start, period.end) {
                Placement::One(month) => {
                    dated.entry(month).or_insert(MonthTotal::EMPTY).add(negative, deposits);
                    covered.insert(month);
                }
                Placement::Spread(months) => {
                    let count = i64::try_from(months.len()).expect("few months");
                    if let Some(n) = period.negative_days {
                        worst_floor = worst_floor.max((i64::from(n) + count - 1) / count);
                    }
                    for month in months {
                        dated.entry(month).or_insert(MonthTotal::EMPTY).add(up_to(negative.hi()), up_to(deposits.hi()));
                        if period.start <= Some(month.first_day()) && Some(month.last_day()) <= period.end {
                            covered.insert(month);
                        }
                    }
                }
                Placement::Undated => {
                    undated += 1;
                    undated_negative = undated_negative.add(up_to(negative.hi()));
                    undated_deposits = undated_deposits.add(up_to(deposits.hi()));
                }
            }
        }
        let mut months: Vec<StatementMonth> = dated
            .into_iter()
            .map(|(month, mut total)| {
                if undated > 0 {
                    total.add(undated_negative, undated_deposits);
                }
                StatementMonth { month: Some(month), negative_days: total.negative_days(), deposits: total.deposits }
            })
            .collect();
        months.extend((0..undated).map(|_| StatementMonth {
            month: None,
            negative_days: undated_negative,
            deposits: undated_deposits,
        }));
        MonthlyDerivation {
            worst_negative_days: months
                .iter()
                .map(|month| month.negative_days)
                .reduce(Interval::max)
                .map(|worst| worst.raise_lo(worst_floor)),
            worst_deposits: months.iter().map(|month| month.deposits).reduce(Interval::min),
            covered_months: i64::try_from(covered.len()).expect("few months"),
            months,
        }
    }
}

#[cfg(test)]
pub(crate) mod testing {
    use super::*;

    pub const PACKAGE_ID: &str = "0f8fad5b-d9cb-469f-a165-70867728950e";

    pub fn period(start: &str, end: &str, negative_days: u32, revenue: u32, all: u32) -> AccountPeriod {
        AccountPeriod {
            start: Some(Date::parse(start, &Iso8601::DATE).unwrap()),
            end: Some(Date::parse(end, &Iso8601::DATE).unwrap()),
            negative_days: Some(negative_days),
            true_revenue_count: Some(revenue),
            deposit_count: Some(all),
        }
    }

    pub fn figures() -> Figures {
        Figures {
            currency: Some("USD".to_string()),
            months: 3,
            monthly_true_revenue_cents: Some(3_125_000),
            confirmed_funders: 1,
            positions_by_month: vec![
                MonthPositions { month: YearMonth::new(2026, 8).unwrap(), active: Some(3), possible: Some(0) },
                MonthPositions { month: YearMonth::new(2026, 9).unwrap(), active: Some(1), possible: Some(0) },
            ],
        }
    }

    pub fn package(periods: Vec<AccountPeriod>) -> ReadyPackage {
        ReadyPackage {
            package_id: Uuid::parse_str(PACKAGE_ID).unwrap(),
            revision: "9c".repeat(32),
            review_required: false,
            figures: Some(figures()),
            periods,
        }
    }

    pub fn three_clean_months() -> ReadyPackage {
        package(vec![
            period("2026-07-01", "2026-07-31", 0, 19, 22),
            period("2026-08-01", "2026-08-31", 2, 14, 16),
            period("2026-09-01", "2026-09-30", 1, 18, 18),
        ])
    }
}

#[cfg(test)]
mod tests {
    use super::testing::*;
    use super::*;

    fn known(fact: &Fact<Interval>) -> Interval {
        *fact.known().unwrap_or_else(|| panic!("expected a known fact, got {fact:?}"))
    }

    fn interval(lo: i64, hi: i64) -> Interval {
        Interval::between(lo, hi).unwrap()
    }

    #[test]
    fn monthly_statements_give_exact_worst_months() {
        let facts = AnalysisFacts::derive(Some(&three_clean_months()));
        assert_eq!(known(&facts.worst_month_negative_days), Interval::point(2));
        assert_eq!(known(&facts.worst_month_deposits), interval(14, 16));
        assert_eq!(known(&facts.statement_months), Interval::point(3));
        assert_eq!(known(&facts.monthly_true_revenue), Interval::point(3_125_000));
        assert_eq!(facts.months.len(), 3);
    }

    #[test]
    fn two_accounts_in_one_month_give_max_to_sum_negative_days_and_added_deposits() {
        let package =
            package(vec![period("2026-09-01", "2026-09-30", 2, 10, 12), period("2026-09-01", "2026-09-30", 3, 5, 9)]);
        let facts = AnalysisFacts::derive(Some(&package));
        assert_eq!(known(&facts.worst_month_negative_days), interval(3, 5));
        assert_eq!(known(&facts.worst_month_deposits), interval(15, 21));
        assert_eq!(facts.months.len(), 1);
    }

    #[test]
    fn a_period_straddling_two_calendar_months_stands_for_the_one_holding_most_days() {
        let package =
            package(vec![period("2026-07-15", "2026-08-14", 1, 10, 10), period("2026-08-15", "2026-09-14", 4, 20, 20)]);
        let facts = AnalysisFacts::derive(Some(&package));
        let months: Vec<_> = facts.months.iter().map(|month| month.month.unwrap().to_string()).collect();
        assert_eq!(months, ["2026-07", "2026-08"]);
        assert_eq!(known(&facts.worst_month_negative_days), Interval::point(4));
        assert_eq!(known(&facts.worst_month_deposits), Interval::point(10));
    }

    #[test]
    fn a_period_touching_three_months_spreads_and_bounds_the_worst_month_below() {
        let package = package(vec![period("2026-07-15", "2026-09-10", 5, 30, 40)]);
        let facts = AnalysisFacts::derive(Some(&package));
        assert_eq!(facts.months.len(), 3);
        assert!(facts.months.iter().all(|month| month.negative_days == interval(0, 5)));
        assert_eq!(known(&facts.worst_month_negative_days), interval(2, 5), "ceil(5 / 3) = 2");
        assert_eq!(known(&facts.worst_month_deposits), interval(0, 40));
        assert_eq!(known(&facts.statement_months), interval(1, 3), "only August is covered in full");
    }

    #[test]
    fn an_undated_period_is_its_own_month_and_may_fall_in_any_other() {
        let mut undated = period("2026-09-01", "2026-09-30", 2, 8, 9);
        undated.start = None;
        let package = package(vec![period("2026-09-01", "2026-09-30", 1, 18, 18), undated]);
        let facts = AnalysisFacts::derive(Some(&package));
        assert_eq!(facts.months[0].negative_days, interval(1, 3));
        assert_eq!(facts.months[1].month, None);
        assert_eq!(known(&facts.worst_month_negative_days), interval(1, 3));
        assert_eq!(known(&facts.worst_month_deposits), interval(0, 9));
    }

    #[test]
    fn null_counts_widen_the_month() {
        let mut unknown_counts = period("2026-09-01", "2026-09-30", 0, 0, 0);
        unknown_counts.negative_days = None;
        unknown_counts.true_revenue_count = None;
        unknown_counts.deposit_count = Some(12);
        let package = package(vec![period("2026-08-01", "2026-08-31", 1, 18, 20), unknown_counts]);
        let facts = AnalysisFacts::derive(Some(&package));
        assert_eq!(known(&facts.worst_month_negative_days), Interval::at_least(1));
        assert_eq!(known(&facts.worst_month_deposits), interval(0, 12));
    }

    #[test]
    fn only_null_negative_days_is_not_established() {
        let mut unknown_counts = period("2026-09-01", "2026-09-30", 0, 4, 4);
        unknown_counts.negative_days = None;
        let facts = AnalysisFacts::derive(Some(&package(vec![unknown_counts])));
        assert!(matches!(facts.worst_month_negative_days, Fact::Unknown { gap: Gap::NotEstablished, .. }));
    }

    #[test]
    fn statement_months_never_exceed_the_published_months() {
        let mut package = three_clean_months();
        package.figures.as_mut().unwrap().months = 2;
        let facts = AnalysisFacts::derive(Some(&package));
        assert_eq!(known(&facts.statement_months), Interval::point(2));
    }

    #[test]
    fn new_position_uses_the_latest_month_and_widens_for_potential_lenders() {
        let mut package = three_clean_months();
        assert_eq!(known(&AnalysisFacts::derive(Some(&package)).new_position), Interval::point(2));
        package.figures.as_mut().unwrap().positions_by_month[1].possible = Some(2);
        assert_eq!(known(&AnalysisFacts::derive(Some(&package)).new_position), interval(2, 4));
        package.figures.as_mut().unwrap().positions_by_month[1].possible = None;
        assert_eq!(known(&AnalysisFacts::derive(Some(&package)).new_position), Interval::at_least(2));
        package.figures.as_mut().unwrap().positions_by_month[1].active = None;
        assert!(matches!(AnalysisFacts::derive(Some(&package)).new_position, Fact::Unknown { .. }));
    }

    #[test]
    fn money_needs_one_currency_and_it_must_be_usd() {
        let mut package = three_clean_months();
        package.figures.as_mut().unwrap().currency = None;
        assert!(matches!(
            AnalysisFacts::derive(Some(&package)).monthly_true_revenue,
            Fact::Unknown { gap: Gap::CurrencyRefused, .. }
        ));
        package.figures.as_mut().unwrap().currency = Some("CAD".to_string());
        assert!(matches!(
            AnalysisFacts::derive(Some(&package)).monthly_true_revenue,
            Fact::Unknown { gap: Gap::NotUsd, .. }
        ));
        package.figures.as_mut().unwrap().currency = Some("USD".to_string());
        package.figures.as_mut().unwrap().monthly_true_revenue_cents = None;
        assert!(matches!(
            AnalysisFacts::derive(Some(&package)).monthly_true_revenue,
            Fact::Unknown { gap: Gap::NotEstablished, .. }
        ));
    }

    #[test]
    fn review_required_holds_every_analysis_fact_with_its_value_seen() {
        let mut package = three_clean_months();
        package.review_required = true;
        let facts = AnalysisFacts::derive(Some(&package));
        assert!(matches!(
            facts.worst_month_negative_days,
            Fact::Unknown { gap: Gap::AnalysisReviewRequired, seen: Some(_), .. }
        ));
        assert!(matches!(facts.funder_payment_history, Fact::Unknown { gap: Gap::AnalysisReviewRequired, .. }));
        assert_eq!(facts.months.len(), 3, "the months stay as evidence");
    }

    #[test]
    fn no_figures_and_no_funders() {
        let mut package = three_clean_months();
        package.figures.as_mut().unwrap().confirmed_funders = 0;
        assert!(matches!(
            AnalysisFacts::derive(Some(&package)).funder_payment_history,
            Fact::Unknown { gap: Gap::NotEstablished, .. }
        ));
        package.figures = None;
        assert!(matches!(
            AnalysisFacts::derive(Some(&package)).new_position,
            Fact::Unknown { gap: Gap::NoFigures, .. }
        ));
    }

    const FIXTURES: [(&str, &str); 4] = [
        ("ready_clean.json", include_str!("../../tests/fixtures/analysis/ready_clean.json")),
        ("ready_review_required.json", include_str!("../../tests/fixtures/analysis/ready_review_required.json")),
        ("ready_currency_refused.json", include_str!("../../tests/fixtures/analysis/ready_currency_refused.json")),
        ("processing.json", include_str!("../../tests/fixtures/analysis/processing.json")),
    ];

    fn fixture(name: &str) -> &'static str {
        FIXTURES.iter().find(|(file, _)| *file == name).unwrap().1
    }

    fn id() -> Uuid {
        Uuid::parse_str(PACKAGE_ID).unwrap()
    }

    #[test]
    fn the_fixtures_parse() {
        let Parsed::Ready(clean) = parse(fixture("ready_clean.json").as_bytes(), id()).unwrap() else { panic!() };
        assert!(!clean.review_required);
        assert_eq!(clean.periods.len(), 4, "the duplicate statement adds nothing");
        let figures = clean.figures.as_ref().unwrap();
        assert_eq!(figures.monthly_true_revenue_cents, Some(3_125_000));
        let Parsed::Ready(held) = parse(fixture("ready_review_required.json").as_bytes(), id()).unwrap() else {
            panic!()
        };
        assert!(held.review_required);
        let Parsed::Ready(refused) = parse(fixture("ready_currency_refused.json").as_bytes(), id()).unwrap() else {
            panic!()
        };
        assert_eq!(refused.figures.unwrap().currency, None);
        assert_eq!(parse(fixture("processing.json").as_bytes(), id()).unwrap(), Parsed::Processing);
    }

    type Edit = Box<dyn FnOnce(&mut serde_json::Value)>;

    fn mutated(edit: impl FnOnce(&mut serde_json::Value)) -> Vec<u8> {
        let mut body: serde_json::Value = serde_json::from_str(fixture("ready_clean.json")).unwrap();
        edit(&mut body);
        serde_json::to_vec(&body).unwrap()
    }

    #[test]
    fn parse_refuses_what_v1_does_not_allow() {
        let refusals: [(&str, Edit); 9] = [
            ("major version", Box::new(|b| b["api_version"] = "2.0".into())),
            ("closed decision", Box::new(|b| b["review"]["decision"] = "maybe".into())),
            ("closed document status", Box::new(|b| b["documents"][0]["status"] = "lost".into())),
            ("closed account status", Box::new(|b| b["documents"][0]["accounts"][0]["status"] = "partial".into())),
            ("fractional count", Box::new(|b| b["documents"][0]["accounts"][0]["negative_days"] = 1.5.into())),
            (
                "missing nullable field",
                Box::new(|b| _ = b["documents"][0]["accounts"][0].as_object_mut().unwrap().remove("deposit_count")),
            ),
            ("month format", Box::new(|b| b["figures"]["active_positions_by_month"][0]["month"] = "2026-9".into())),
            (
                "date format",
                Box::new(|b| b["documents"][0]["accounts"][0]["period_end"] = "2026-07-31T00:00:00Z".into()),
            ),
            ("other package", Box::new(|b| b["package_id"] = "00000000-0000-4000-8000-000000000000".into())),
        ];
        for (what, edit) in refusals {
            assert!(parse(&mutated(edit), id()).is_err(), "{what}");
        }
    }

    #[test]
    fn parse_ignores_fields_it_does_not_know() {
        let body = mutated(|b| {
            b["new_top_level_field"] = 1.into();
            b["figures"]["new_figure"] = "x".into();
        });
        assert!(parse(&body, id()).is_ok());
    }
}
