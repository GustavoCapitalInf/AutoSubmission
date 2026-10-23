//! What a deal is proven to be. Every fact is `Known` (a value, or for a number the inclusive
//! interval the inputs bound it to) or `Unknown` with the reason. A wider interval only turns a
//! pass or a fail into unproven, so a derivation may be coarse as long as it contains the true value.

pub mod analysis;
pub mod application;

use std::fmt;

use serde::{Deserialize, Serialize};
use time::{Date, OffsetDateTime};
use uuid::Uuid;

use analysis::{AnalysisFacts, ReadyPackage, StatementMonth};
use application::{ApplicationFacts, Confirmations, Confirmed, EntityKind, IndustryId, Jurisdiction, whole_months};

/// A numeric deal fact. `DealFacts::num` matches on it, so a new variant needs a field and a
/// source before it builds.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NumFact {
    /// Cents of USD; `figures.monthly_true_revenue_cents`.
    MonthlyTrueRevenueCents,
    /// The application's estimated FICO.
    CreditScore,
    /// Whole months from the application's business start month to `as_of`.
    TimeInBusinessMonths,
    /// Negative printed days in the worst statement month.
    WorstMonthNegativeDays,
    /// Deposits in the worst statement month, between the True revenue credits and all credits.
    WorstMonthDeposits,
    /// The position a new advance would take: the latest month's active positions plus one.
    NewPosition,
    /// Calendar months of statements.
    StatementMonths,
    /// Cents of USD; the application's requested advance.
    RequestedAmountCents,
}

impl NumFact {
    pub const ALL: [NumFact; 8] = [
        NumFact::MonthlyTrueRevenueCents,
        NumFact::CreditScore,
        NumFact::TimeInBusinessMonths,
        NumFact::WorstMonthNegativeDays,
        NumFact::WorstMonthDeposits,
        NumFact::NewPosition,
        NumFact::StatementMonths,
        NumFact::RequestedAmountCents,
    ];

    pub fn key(self) -> &'static str {
        match self {
            NumFact::MonthlyTrueRevenueCents => "monthly_true_revenue_cents",
            NumFact::CreditScore => "credit_score",
            NumFact::TimeInBusinessMonths => "time_in_business_months",
            NumFact::WorstMonthNegativeDays => "worst_month_negative_days",
            NumFact::WorstMonthDeposits => "worst_month_deposits",
            NumFact::NewPosition => "new_position",
            NumFact::StatementMonths => "statement_months",
            NumFact::RequestedAmountCents => "requested_amount_cents",
        }
    }

    pub fn is_money(self) -> bool {
        matches!(self, NumFact::MonthlyTrueRevenueCents | NumFact::RequestedAmountCents)
    }
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FlagFact {
    OpenBankruptcy,
    OpenJudgement,
    TaxLien,
    OpenLawsuit,
    DefaultHistory,
    HomeBased,
    /// The statements show payments to a confirmed funder.
    FunderPaymentHistory,
}

impl FlagFact {
    pub const ALL: [FlagFact; 7] = [
        FlagFact::OpenBankruptcy,
        FlagFact::OpenJudgement,
        FlagFact::TaxLien,
        FlagFact::OpenLawsuit,
        FlagFact::DefaultHistory,
        FlagFact::HomeBased,
        FlagFact::FunderPaymentHistory,
    ];

    pub fn key(self) -> &'static str {
        match self {
            FlagFact::OpenBankruptcy => "open_bankruptcy",
            FlagFact::OpenJudgement => "open_judgement",
            FlagFact::TaxLien => "tax_lien",
            FlagFact::OpenLawsuit => "open_lawsuit",
            FlagFact::DefaultHistory => "default_history",
            FlagFact::HomeBased => "home_based",
            FlagFact::FunderPaymentHistory => "funder_payment_history",
        }
    }
}

/// Names any fact. Its wire name is `key()`.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FactKey {
    Num(NumFact),
    State,
    Industry,
    Entity,
    Flag(FlagFact),
}

impl FactKey {
    pub fn all() -> Vec<FactKey> {
        let mut keys: Vec<FactKey> = NumFact::ALL.into_iter().map(FactKey::Num).collect();
        keys.extend([FactKey::State, FactKey::Industry, FactKey::Entity]);
        keys.extend(FlagFact::ALL.into_iter().map(FactKey::Flag));
        keys
    }

    pub fn key(self) -> &'static str {
        match self {
            FactKey::Num(fact) => fact.key(),
            FactKey::State => "state",
            FactKey::Industry => "industry",
            FactKey::Entity => "entity",
            FactKey::Flag(fact) => fact.key(),
        }
    }

    pub fn from_key(key: &str) -> Option<FactKey> {
        FactKey::all().into_iter().find(|fact| fact.key() == key)
    }
}

/// Inclusive bounds an integer fact is proven to lie within; `hi: None` is unbounded above.
/// Invariant: `lo <= hi`.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(try_from = "IntervalParts", into = "IntervalParts")]
pub struct Interval {
    lo: i64,
    hi: Option<i64>,
}

#[derive(Serialize, Deserialize)]
struct IntervalParts {
    min: i64,
    max: Option<i64>,
}

impl TryFrom<IntervalParts> for Interval {
    type Error = &'static str;
    fn try_from(parts: IntervalParts) -> Result<Self, Self::Error> {
        match parts.max {
            Some(max) => Interval::between(parts.min, max).ok_or("min is above max"),
            None => Ok(Interval::at_least(parts.min)),
        }
    }
}

impl From<Interval> for IntervalParts {
    fn from(interval: Interval) -> Self {
        IntervalParts { min: interval.lo, max: interval.hi }
    }
}

impl Interval {
    pub fn point(value: i64) -> Interval {
        Interval { lo: value, hi: Some(value) }
    }

    /// None when `lo > hi`.
    pub fn between(lo: i64, hi: i64) -> Option<Interval> {
        (lo <= hi).then_some(Interval { lo, hi: Some(hi) })
    }

    pub fn at_least(lo: i64) -> Interval {
        Interval { lo, hi: None }
    }

    /// The smallest interval holding both values.
    pub fn hull(a: i64, b: i64) -> Interval {
        Interval { lo: a.min(b), hi: Some(a.max(b)) }
    }

    pub fn lo(self) -> i64 {
        self.lo
    }

    pub fn hi(self) -> Option<i64> {
        self.hi
    }

    /// Bounds of `max(a, b)` for `a` in `self` and `b` in `other`.
    pub fn max(self, other: Interval) -> Interval {
        let hi = match (self.hi, other.hi) {
            (Some(a), Some(b)) => Some(a.max(b)),
            _ => None,
        };
        Interval { lo: self.lo.max(other.lo), hi }
    }

    /// Bounds of `min(a, b)` for `a` in `self` and `b` in `other`.
    pub fn min(self, other: Interval) -> Interval {
        let hi = match (self.hi, other.hi) {
            (Some(a), Some(b)) => Some(a.min(b)),
            (Some(a), None) | (None, Some(a)) => Some(a),
            (None, None) => None,
        };
        Interval { lo: self.lo.min(other.lo), hi }
    }

    /// Bounds of `a + b`.
    pub fn add(self, other: Interval) -> Interval {
        let hi = match (self.hi, other.hi) {
            (Some(a), Some(b)) => Some(a.saturating_add(b)),
            _ => None,
        };
        Interval { lo: self.lo.saturating_add(other.lo), hi }
    }

    /// The same interval with `lo` raised to at least `floor`, capped at `hi`.
    pub fn raise_lo(self, floor: i64) -> Interval {
        let lo = match self.hi {
            Some(hi) => self.lo.max(floor).min(hi),
            None => self.lo.max(floor),
        };
        Interval { lo, hi: self.hi }
    }
}

impl fmt::Display for Interval {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self.hi {
            Some(hi) if hi == self.lo => write!(f, "{hi}"),
            Some(hi) => write!(f, "{} to {hi}", self.lo),
            None => write!(f, "at least {}", self.lo),
        }
    }
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Fact<V> {
    /// The inputs fix the value (or, for an interval, bound it).
    Known { value: V, basis: Basis, source: Source },
    /// The inputs do not establish it. `seen` is an unproven value shown as evidence and not evaluated.
    Unknown { gap: Gap, seen: Option<V>, source: Source },
}

impl<V> Fact<V> {
    pub fn known(&self) -> Option<&V> {
        match self {
            Fact::Known { value, .. } => Some(value),
            Fact::Unknown { .. } => None,
        }
    }

    pub fn source(&self) -> &Source {
        match self {
            Fact::Known { source, .. } | Fact::Unknown { source, .. } => source,
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Basis {
    /// Published by the bank statement analysis.
    Printed,
    /// Stated on the application.
    Stated,
    /// Confirmed by a signed-in person.
    Confirmed,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Gap {
    /// No analysis package, or the application gave no value.
    NotSupplied,
    /// The package's `figures` is null.
    NoFigures,
    /// The analysis published null, or the statements cannot establish it.
    NotEstablished,
    /// `figures.currency` is null.
    CurrencyRefused,
    /// Criteria money is USD.
    NotUsd,
    /// `review.required` is true; `seen` holds the provisional value.
    AnalysisReviewRequired,
    /// Only a person's confirmation proves this fact.
    NeedsConfirmation,
}

impl Gap {
    pub fn key(self) -> &'static str {
        match self {
            Gap::NotSupplied => "not_supplied",
            Gap::NoFigures => "no_figures",
            Gap::NotEstablished => "not_established",
            Gap::CurrencyRefused => "currency_refused",
            Gap::NotUsd => "not_usd",
            Gap::AnalysisReviewRequired => "analysis_review_required",
            Gap::NeedsConfirmation => "needs_confirmation",
        }
    }
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Source {
    /// A v1 analysis field path.
    Analysis(String),
    /// A match request field path.
    Application(String),
    Confirmed {
        by: String,
        #[serde(with = "time::serde::rfc3339")]
        at: OffsetDateTime,
    },
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct AnalysisRef {
    pub package_id: Uuid,
    pub revision: String,
}

/// What the caller supplies about a deal, already parsed.
#[derive(Clone, Default, PartialEq, Debug, Serialize, Deserialize)]
pub struct DealInput {
    pub application: ApplicationFacts,
    pub confirmations: Confirmations,
}

/// Every fact of one deal at `as_of`. Built only by `assemble`.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct DealFacts {
    #[serde(with = "iso_date")]
    pub as_of: Date,
    pub analysis: Option<AnalysisRef>,
    monthly_true_revenue: Fact<Interval>,
    credit_score: Fact<Interval>,
    time_in_business: Fact<Interval>,
    worst_month_negative_days: Fact<Interval>,
    worst_month_deposits: Fact<Interval>,
    new_position: Fact<Interval>,
    statement_months: Fact<Interval>,
    requested_amount: Fact<Interval>,
    state: Fact<Jurisdiction>,
    industry: Fact<IndustryId>,
    entity: Fact<EntityKind>,
    open_bankruptcy: Fact<bool>,
    open_judgement: Fact<bool>,
    tax_lien: Fact<bool>,
    open_lawsuit: Fact<bool>,
    default_history: Fact<bool>,
    home_based: Fact<bool>,
    funder_payment_history: Fact<bool>,
    /// The per-month numbers behind the worst-month facts.
    pub months: Vec<StatementMonth>,
}

impl DealFacts {
    pub fn num(&self, fact: NumFact) -> &Fact<Interval> {
        match fact {
            NumFact::MonthlyTrueRevenueCents => &self.monthly_true_revenue,
            NumFact::CreditScore => &self.credit_score,
            NumFact::TimeInBusinessMonths => &self.time_in_business,
            NumFact::WorstMonthNegativeDays => &self.worst_month_negative_days,
            NumFact::WorstMonthDeposits => &self.worst_month_deposits,
            NumFact::NewPosition => &self.new_position,
            NumFact::StatementMonths => &self.statement_months,
            NumFact::RequestedAmountCents => &self.requested_amount,
        }
    }

    pub fn flag(&self, fact: FlagFact) -> &Fact<bool> {
        match fact {
            FlagFact::OpenBankruptcy => &self.open_bankruptcy,
            FlagFact::OpenJudgement => &self.open_judgement,
            FlagFact::TaxLien => &self.tax_lien,
            FlagFact::OpenLawsuit => &self.open_lawsuit,
            FlagFact::DefaultHistory => &self.default_history,
            FlagFact::HomeBased => &self.home_based,
            FlagFact::FunderPaymentHistory => &self.funder_payment_history,
        }
    }

    pub fn state(&self) -> &Fact<Jurisdiction> {
        &self.state
    }

    pub fn industry(&self) -> &Fact<IndustryId> {
        &self.industry
    }

    pub fn entity(&self) -> &Fact<EntityKind> {
        &self.entity
    }
}

/// The facts a stated value cannot prove: the industry (a judgment from free text) and the flags
/// no application field states.
pub fn requires_confirmation(fact: FactKey) -> bool {
    matches!(
        fact,
        FactKey::Industry | FactKey::Flag(FlagFact::DefaultHistory | FlagFact::HomeBased | FlagFact::OpenLawsuit)
    )
}

/// Pure. `analysis` is None when the request named no package; every analysis fact is then
/// `Unknown(NotSupplied)`. Application values are `Stated` unless `requires_confirmation` names
/// the fact; such a value stays `Unknown(NeedsConfirmation)`, shown as `seen`, until a person's
/// confirmation supplies it.
pub fn assemble(analysis: Option<&ReadyPackage>, input: &DealInput, as_of: Date) -> DealFacts {
    let AnalysisFacts {
        monthly_true_revenue,
        worst_month_negative_days,
        worst_month_deposits,
        new_position,
        statement_months,
        funder_payment_history,
        months,
    } = AnalysisFacts::derive(analysis);
    let app = &input.application;
    let confirmed = &input.confirmations;
    let time_in_business = app.business_start.map(|start| {
        let shortest = whole_months(start.last_day(), as_of);
        let longest = whole_months(start.first_day(), as_of);
        Interval::between(shortest, longest).expect("a later start gives fewer months")
    });
    DealFacts {
        as_of,
        analysis: analysis
            .map(|package| AnalysisRef { package_id: package.package_id, revision: package.revision.clone() }),
        monthly_true_revenue,
        credit_score: stated(FactKey::Num(NumFact::CreditScore), app.estimated_fico, "/application/estimated_fico"),
        time_in_business: stated(
            FactKey::Num(NumFact::TimeInBusinessMonths),
            time_in_business,
            "/application/business_start_month",
        ),
        worst_month_negative_days,
        worst_month_deposits,
        new_position,
        statement_months,
        requested_amount: stated(
            FactKey::Num(NumFact::RequestedAmountCents),
            app.requested_amount_cents.map(Interval::point),
            "/application/requested_amount_cents",
        ),
        state: stated(FactKey::State, app.business_state, "/application/business_state"),
        industry: confirmable(
            stated(FactKey::Industry, app.industry_suggestion.clone(), "/application/industry_suggestion"),
            confirmed.industry.as_ref(),
        ),
        entity: stated(FactKey::Entity, app.entity, "/application/entity"),
        open_bankruptcy: stated(FactKey::Flag(FlagFact::OpenBankruptcy), app.bankruptcy, "/application/bankruptcy"),
        open_judgement: stated(
            FactKey::Flag(FlagFact::OpenJudgement),
            app.open_judgements,
            "/application/open_judgements",
        ),
        tax_lien: stated(FactKey::Flag(FlagFact::TaxLien), app.tax_liens, "/application/tax_liens"),
        open_lawsuit: confirmable(needs_person(), confirmed.open_lawsuit.as_ref()),
        default_history: confirmable(needs_person(), confirmed.default_history.as_ref()),
        home_based: confirmable(needs_person(), confirmed.home_based.as_ref()),
        funder_payment_history,
        months,
    }
}

fn stated<V>(fact: FactKey, value: Option<V>, field: &str) -> Fact<V> {
    let source = Source::Application(field.to_string());
    match value {
        None => Fact::Unknown { gap: Gap::NotSupplied, seen: None, source },
        Some(value) if requires_confirmation(fact) => {
            Fact::Unknown { gap: Gap::NeedsConfirmation, seen: Some(value), source }
        }
        Some(value) => Fact::Known { value, basis: Basis::Stated, source },
    }
}

fn needs_person<V>() -> Fact<V> {
    Fact::Unknown {
        gap: Gap::NeedsConfirmation,
        seen: None,
        source: Source::Application("a confirmation on the match page".to_string()),
    }
}

fn confirmable<V: Clone>(unconfirmed: Fact<V>, confirmation: Option<&Confirmed<V>>) -> Fact<V> {
    match confirmation {
        Some(confirmed) => Fact::Known {
            value: confirmed.value.clone(),
            basis: Basis::Confirmed,
            source: Source::Confirmed { by: confirmed.by.clone(), at: confirmed.at },
        },
        None => unconfirmed,
    }
}

mod iso_date {
    use serde::{Deserialize, Deserializer, Serializer};
    use time::Date;
    use time::format_description::well_known::Iso8601;
    use time::format_description::well_known::iso8601::{Config, EncodedConfig, FormattedComponents};

    const DATE_ONLY: EncodedConfig = Config::DEFAULT.set_formatted_components(FormattedComponents::Date).encode();

    pub fn serialize<S: Serializer>(date: &Date, serializer: S) -> Result<S::Ok, S::Error> {
        let text = date.format(&Iso8601::<DATE_ONLY>).map_err(serde::ser::Error::custom)?;
        serializer.serialize_str(&text)
    }

    pub fn deserialize<'de, D: Deserializer<'de>>(deserializer: D) -> Result<Date, D::Error> {
        let text = String::deserialize(deserializer)?;
        Date::parse(&text, &Iso8601::<DATE_ONLY>).map_err(serde::de::Error::custom)
    }
}

#[cfg(test)]
pub(crate) mod testing {
    use super::*;
    use application::YearMonth;
    use time::macros::{date, datetime};

    pub const AS_OF: Date = date!(2026 - 10 - 23);

    pub fn application() -> ApplicationFacts {
        ApplicationFacts {
            business_state: Jurisdiction::from_code("TX"),
            business_start: YearMonth::new(2019, 4),
            entity: Some(EntityKind::Llc),
            estimated_fico: Some(Interval::point(640)),
            requested_amount_cents: Some(7_500_000),
            open_judgements: Some(false),
            bankruptcy: Some(false),
            tax_liens: Some(false),
            industry_suggestion: application::test_industries().resolve("construction-contractor"),
        }
    }

    pub fn confirmed<T>(value: T) -> Option<Confirmed<T>> {
        Some(Confirmed { value, by: "sample.reviewer".to_string(), at: datetime!(2026-10-23 14:02 UTC) })
    }

    pub fn everything_confirmed() -> Confirmations {
        Confirmations {
            industry: confirmed(application::test_industries().resolve("construction-contractor").unwrap()),
            default_history: confirmed(false),
            home_based: confirmed(false),
            open_lawsuit: confirmed(false),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::testing::*;
    use super::*;
    use application::YearMonth;

    #[test]
    fn interval_arithmetic_bounds_every_combination() {
        let a = Interval::between(1, 3).unwrap();
        let b = Interval::at_least(2);
        assert_eq!(a.max(b), Interval::at_least(2));
        assert_eq!(a.min(b), Interval::between(1, 3).unwrap());
        assert_eq!(a.add(Interval::point(2)), Interval::between(3, 5).unwrap());
        assert_eq!(a.add(b), Interval::at_least(3));
        assert_eq!(Interval::hull(5, 2), Interval::between(2, 5).unwrap());
        assert_eq!(Interval::between(0, 4).unwrap().raise_lo(2), Interval::between(2, 4).unwrap());
        assert_eq!(Interval::between(0, 1).unwrap().raise_lo(2), Interval::point(1));
        assert_eq!(Interval::between(3, 2), None);
    }

    #[test]
    fn interval_json_refuses_min_above_max() {
        assert!(serde_json::from_str::<Interval>(r#"{"min": 3, "max": 2}"#).is_err());
        assert_eq!(serde_json::from_str::<Interval>(r#"{"min": 3, "max": null}"#).unwrap(), Interval::at_least(3));
    }

    #[test]
    fn stated_values_are_known_except_those_needing_a_person() {
        let input = DealInput { application: application(), confirmations: Confirmations::default() };
        let facts = assemble(None, &input, AS_OF);
        assert!(matches!(facts.state(), Fact::Known { basis: Basis::Stated, .. }));
        assert!(matches!(facts.num(NumFact::CreditScore), Fact::Known { basis: Basis::Stated, .. }));
        assert!(matches!(facts.industry(), Fact::Unknown { gap: Gap::NeedsConfirmation, seen: Some(_), .. }));
        for flag in [FlagFact::DefaultHistory, FlagFact::HomeBased, FlagFact::OpenLawsuit] {
            assert!(
                matches!(facts.flag(flag), Fact::Unknown { gap: Gap::NeedsConfirmation, seen: None, .. }),
                "{flag:?}"
            );
        }
        assert!(matches!(facts.num(NumFact::MonthlyTrueRevenueCents), Fact::Unknown { gap: Gap::NotSupplied, .. }));
    }

    #[test]
    fn confirmations_prove_the_facts_they_name() {
        let input = DealInput { application: application(), confirmations: everything_confirmed() };
        let facts = assemble(None, &input, AS_OF);
        assert!(matches!(facts.industry(), Fact::Known { basis: Basis::Confirmed, .. }));
        assert_eq!(facts.flag(FlagFact::DefaultHistory).known(), Some(&false));
        assert!(matches!(facts.flag(FlagFact::HomeBased).source(), Source::Confirmed { .. }));
    }

    #[test]
    fn a_start_month_bounds_time_in_business() {
        let mut app = application();
        app.business_start = YearMonth::new(2025, 10);
        let facts = assemble(None, &DealInput { application: app, ..DealInput::default() }, AS_OF);
        assert_eq!(facts.num(NumFact::TimeInBusinessMonths).known(), Interval::between(11, 12).as_ref());
    }

    #[test]
    fn missing_application_values_are_not_supplied() {
        let facts = assemble(None, &DealInput::default(), AS_OF);
        for key in [NumFact::CreditScore, NumFact::TimeInBusinessMonths, NumFact::RequestedAmountCents] {
            assert!(matches!(facts.num(key), Fact::Unknown { gap: Gap::NotSupplied, .. }), "{key:?}");
        }
        assert!(matches!(facts.flag(FlagFact::TaxLien), Fact::Unknown { gap: Gap::NotSupplied, .. }));
    }

    #[test]
    fn deal_facts_round_trip_through_json() {
        let input = DealInput { application: application(), confirmations: everything_confirmed() };
        let facts = assemble(None, &input, AS_OF);
        let json = serde_json::to_string(&facts).unwrap();
        assert_eq!(serde_json::from_str::<DealFacts>(&json).unwrap(), facts);
    }

    #[test]
    fn fact_keys_round_trip() {
        for key in FactKey::all() {
            assert_eq!(FactKey::from_key(key.key()), Some(key));
        }
    }
}
