//! Three-valued (Kleene) evaluation: a check passes only when every value the facts allow passes
//! it, fails only when every value fails it, and is unproven otherwise.

use serde::{Deserialize, Serialize};
use time::OffsetDateTime;

use super::{CheckId, LenderId, LenderPolicy, Membership, NoteId, NoteKind, Predicate, RuleId};
use crate::facts::{DealFacts, Fact, FactKey, Interval};

/// A person's decision to set a check aside for one deal. It binds to the lender revision and the
/// analysis revision it was given on, and lapses when either changes.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Waiver {
    pub lender: LenderId,
    pub check: CheckId,
    pub lender_revision: u32,
    pub analysis_revision: Option<String>,
    /// The signed-in account's username.
    pub by: String,
    #[serde(with = "time::serde::rfc3339")]
    pub at: OffsetDateTime,
    pub reason: String,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Evaluation {
    pub checks: Vec<CheckResult>,
    pub notes: Vec<NoteResult>,
    pub stale_waivers: Vec<Waiver>,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct CheckResult {
    pub rule: RuleId,
    pub outcome: Outcome,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct NoteResult {
    pub note: NoteId,
    pub kind: NoteKind,
    pub scope: Scope,
    pub waiver: Option<Waiver>,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    Pass,
    NotApplicable,
    Fail,
    Unproven(Unproven),
    Waived { waiver: Waiver, overruled: Overruled },
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Overruled {
    Fail,
    Unproven(Unproven),
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Unproven {
    FactUnknown(FactKey),
    Straddles(FactKey),
    /// The rule may apply, and this fact, which decides whether it does, is not proven.
    ScopeUnknown(FactKey),
}

impl Unproven {
    pub fn why(self) -> &'static str {
        match self {
            Unproven::FactUnknown(_) => "fact_unknown",
            Unproven::Straddles(_) => "straddles",
            Unproven::ScopeUnknown(_) => "scope_unknown",
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum Scope {
    #[serde(rename = "in_scope")]
    In,
    #[serde(rename = "out_of_scope")]
    Out,
    #[serde(rename = "scope_unknown")]
    Unknown,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VerdictStatus {
    Match,
    Review,
    NoMatch,
}

impl VerdictStatus {
    pub fn key(self) -> &'static str {
        match self {
            VerdictStatus::Match => "match",
            VerdictStatus::Review => "review",
            VerdictStatus::NoMatch => "no_match",
        }
    }
}

impl Evaluation {
    pub fn status(&self) -> VerdictStatus {
        if self.checks.iter().any(|check| check.outcome == Outcome::Fail) {
            return VerdictStatus::NoMatch;
        }
        let unproven = self.checks.iter().any(|check| matches!(check.outcome, Outcome::Unproven(_)));
        let held = self
            .notes
            .iter()
            .any(|note| note.kind == NoteKind::Condition && note.scope != Scope::Out && note.waiver.is_none());
        if unproven || held { VerdictStatus::Review } else { VerdictStatus::Match }
    }
}

enum Tri {
    Yes,
    No,
    Maybe(Unproven),
}

/// Pure and deterministic. `waivers` are this lender's: `Waiver::lender` is not checked.
pub fn evaluate(policy: &LenderPolicy, revision: u32, facts: &DealFacts, waivers: &[Waiver]) -> Evaluation {
    let analysis_revision = facts.analysis.as_ref().map(|analysis| analysis.revision.as_str());
    let (live, stale): (Vec<&Waiver>, Vec<&Waiver>) = waivers.iter().partition(|waiver| {
        waiver.lender_revision == revision && waiver.analysis_revision.as_deref() == analysis_revision
    });
    let live_for = |check: CheckId| live.iter().find(|waiver| waiver.check == check).map(|waiver| (*waiver).clone());
    let checks = policy
        .rules()
        .iter()
        .map(|rule| {
            let outcome = match all(&rule.when, facts) {
                Tri::No => Outcome::NotApplicable,
                Tri::Yes => match test(&rule.require, facts) {
                    Tri::Yes => Outcome::Pass,
                    Tri::No => Outcome::Fail,
                    Tri::Maybe(why) => Outcome::Unproven(why),
                },
                Tri::Maybe(why) => match test(&rule.require, facts) {
                    Tri::Yes => Outcome::Pass,
                    _ => Outcome::Unproven(Unproven::ScopeUnknown(fact_of(why))),
                },
            };
            let overruled = match &outcome {
                Outcome::Fail => Some(Overruled::Fail),
                Outcome::Unproven(why) => Some(Overruled::Unproven(*why)),
                _ => None,
            };
            let outcome = match (overruled, live_for(CheckId::Rule(rule.id))) {
                (Some(overruled), Some(waiver)) => Outcome::Waived { waiver, overruled },
                _ => outcome,
            };
            CheckResult { rule: rule.id, outcome }
        })
        .collect();
    let notes = policy
        .notes()
        .iter()
        .map(|note| {
            let scope = match all(&note.when, facts) {
                Tri::Yes => Scope::In,
                Tri::No => Scope::Out,
                Tri::Maybe(_) => Scope::Unknown,
            };
            let waivable = note.kind == NoteKind::Condition && scope != Scope::Out;
            let waiver = if waivable { live_for(CheckId::Note(note.id)) } else { None };
            NoteResult { note: note.id, kind: note.kind, scope, waiver }
        })
        .collect();
    Evaluation { checks, notes, stale_waivers: stale.into_iter().cloned().collect() }
}

fn fact_of(why: Unproven) -> FactKey {
    match why {
        Unproven::FactUnknown(fact) | Unproven::Straddles(fact) | Unproven::ScopeUnknown(fact) => fact,
    }
}

fn all(predicates: &[Predicate], facts: &DealFacts) -> Tri {
    let mut maybe = None;
    for predicate in predicates {
        match test(predicate, facts) {
            Tri::No => return Tri::No,
            Tri::Maybe(why) => maybe = maybe.or(Some(why)),
            Tri::Yes => {}
        }
    }
    maybe.map_or(Tri::Yes, Tri::Maybe)
}

pub fn reads(predicate: &Predicate) -> FactKey {
    match predicate {
        Predicate::Num { fact, .. } => FactKey::Num(*fact),
        Predicate::State(_) => FactKey::State,
        Predicate::Industry(_) => FactKey::Industry,
        Predicate::Entity(_) => FactKey::Entity,
        Predicate::Flag { fact, .. } => FactKey::Flag(*fact),
    }
}

fn test(predicate: &Predicate, facts: &DealFacts) -> Tri {
    let key = reads(predicate);
    match predicate {
        Predicate::Num { fact, bound } => match facts.num(*fact) {
            Fact::Unknown { .. } => Tri::Maybe(Unproven::FactUnknown(key)),
            Fact::Known { value, .. } => within(*value, bound.min(), bound.max(), key),
        },
        Predicate::State(set) => member(facts.state(), set, key),
        Predicate::Industry(set) => member(facts.industry(), set, key),
        Predicate::Entity(set) => member(facts.entity(), set, key),
        Predicate::Flag { fact, is } => match facts.flag(*fact) {
            Fact::Unknown { .. } => Tri::Maybe(Unproven::FactUnknown(key)),
            Fact::Known { value, .. } if value == is => Tri::Yes,
            Fact::Known { .. } => Tri::No,
        },
    }
}

fn within(value: Interval, min: Option<i64>, max: Option<i64>, key: FactKey) -> Tri {
    let below = min.is_some_and(|min| value.hi().is_some_and(|hi| hi < min));
    let above = max.is_some_and(|max| value.lo() > max);
    if below || above {
        return Tri::No;
    }
    let meets_min = min.is_none_or(|min| min <= value.lo());
    let meets_max = max.is_none_or(|max| value.hi().is_some_and(|hi| hi <= max));
    if meets_min && meets_max { Tri::Yes } else { Tri::Maybe(Unproven::Straddles(key)) }
}

fn member<T: Ord + Clone>(fact: &Fact<T>, set: &Membership<T>, key: FactKey) -> Tri {
    match fact {
        Fact::Unknown { .. } => Tri::Maybe(Unproven::FactUnknown(key)),
        Fact::Known { value, .. } if set.allows(value) => Tri::Yes,
        Fact::Known { .. } => Tri::No,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::criteria::testing::*;
    use crate::criteria::{EntityKind, LenderStatus, Membership, NonEmptySet, Note};
    use crate::facts::analysis::testing::{package, period, three_clean_months};
    use crate::facts::application::test_industries;
    use crate::facts::testing::{AS_OF, application, everything_confirmed};
    use crate::facts::{DealInput, FlagFact, NumFact, assemble};
    use time::macros::datetime;

    fn deal() -> DealFacts {
        let input = DealInput { application: application(), confirmations: everything_confirmed() };
        assemble(Some(&three_clean_months()), &input, AS_OF)
    }

    fn outcome(policy: &LenderPolicy, facts: &DealFacts) -> Outcome {
        evaluate(policy, 1, facts, &[]).checks.remove(0).outcome
    }

    fn one(require: Predicate) -> LenderPolicy {
        active(vec![rule(1, vec![], require)], vec![])
    }

    fn guarded(when: Vec<Predicate>, require: Predicate) -> LenderPolicy {
        active(vec![rule(1, when, require)], vec![])
    }

    #[test]
    fn numeric_bounds_pass_fail_or_straddle() {
        let facts = deal();
        let revenue = NumFact::MonthlyTrueRevenueCents;
        let deposits = NumFact::WorstMonthDeposits;
        let cases = [
            (num(revenue, Some(2_500_000), None), Outcome::Pass),
            (num(revenue, Some(3_125_000), None), Outcome::Pass),
            (num(revenue, Some(3_125_001), None), Outcome::Fail),
            (num(NumFact::WorstMonthNegativeDays, None, Some(2)), Outcome::Pass),
            (num(NumFact::WorstMonthNegativeDays, None, Some(1)), Outcome::Fail),
            (num(deposits, Some(14), None), Outcome::Pass),
            (num(deposits, Some(15), None), Outcome::Unproven(Unproven::Straddles(FactKey::Num(deposits)))),
            (num(deposits, Some(17), None), Outcome::Fail),
            (num(NumFact::NewPosition, Some(1), Some(3)), Outcome::Pass),
            (num(NumFact::NewPosition, Some(3), None), Outcome::Fail),
        ];
        for (require, expected) in cases {
            assert_eq!(outcome(&one(require.clone()), &facts), expected, "{require:?}");
        }
    }

    #[test]
    fn unknown_facts_never_pass() {
        let facts = assemble(None, &DealInput::default(), AS_OF);
        let cases = [
            num(NumFact::MonthlyTrueRevenueCents, Some(1), None),
            num(NumFact::WorstMonthNegativeDays, None, Some(10)),
            Predicate::Entity(Membership::NotIn(NonEmptySet::new([EntityKind::NonProfit]).unwrap())),
            Predicate::Flag { fact: FlagFact::DefaultHistory, is: false },
            state_in(&["TX"]),
        ];
        for require in cases {
            let key = reads(&require);
            assert_eq!(outcome(&one(require), &facts), Outcome::Unproven(Unproven::FactUnknown(key)));
        }
    }

    #[test]
    fn guards_scope_rules_in_three_values() {
        let facts = deal();
        let first_only = num(NumFact::NewPosition, None, Some(1));
        assert_eq!(outcome(&guarded(vec![state_in(&["TX"])], first_only.clone()), &facts), Outcome::Fail);
        assert_eq!(outcome(&guarded(vec![state_in(&["CA"])], first_only.clone()), &facts), Outcome::NotApplicable);

        let unknown_state = assemble(Some(&three_clean_months()), &DealInput::default(), AS_OF);
        assert_eq!(
            outcome(&guarded(vec![state_in(&["TX"])], first_only), &unknown_state),
            Outcome::Unproven(Unproven::ScopeUnknown(FactKey::State)),
        );
        let passes_anyway = num(NumFact::NewPosition, None, Some(4));
        assert_eq!(outcome(&guarded(vec![state_in(&["TX"])], passes_anyway), &unknown_state), Outcome::Pass);
    }

    #[test]
    fn any_false_guard_makes_a_rule_not_applicable() {
        let unknown_state = assemble(Some(&three_clean_months()), &DealInput::default(), AS_OF);
        let when = vec![state_in(&["TX"]), num(NumFact::MonthlyTrueRevenueCents, None, Some(100))];
        let policy = guarded(when, num(NumFact::NewPosition, None, Some(1)));
        assert_eq!(outcome(&policy, &unknown_state), Outcome::NotApplicable);
    }

    #[test]
    fn verdicts_combine_checks_and_condition_notes() {
        let facts = deal();
        let pass = rule(1, vec![], num(NumFact::CreditScore, Some(600), None));
        let fail = rule(2, vec![], num(NumFact::CreditScore, Some(700), None));
        let unproven = rule(3, vec![], num(NumFact::WorstMonthDeposits, Some(15), None));
        let condition = |id, when| Note { id: NoteId(id), kind: NoteKind::Condition, when, text: "SAMPLE".into() };
        let info = Note { id: NoteId(9), kind: NoteKind::Info, when: vec![], text: "Pays 10 points".into() };
        let status = |rules, notes| evaluate(&active(rules, notes), 1, &facts, &[]).status();

        assert_eq!(status(vec![pass.clone()], vec![info.clone()]), VerdictStatus::Match);
        assert_eq!(status(vec![pass.clone(), unproven.clone()], vec![]), VerdictStatus::Review);
        assert_eq!(status(vec![pass.clone(), unproven, fail], vec![]), VerdictStatus::NoMatch);
        assert_eq!(status(vec![pass.clone()], vec![condition(1, vec![])]), VerdictStatus::Review);
        assert_eq!(status(vec![pass.clone()], vec![condition(1, vec![state_in(&["CA"])])]), VerdictStatus::Match);
        assert_eq!(status(vec![pass], vec![condition(1, vec![state_in(&["TX"])])]), VerdictStatus::Review);
    }

    #[test]
    fn unconfirmed_potential_lenders_hold_a_position_range_at_review() {
        let mut package = three_clean_months();
        package.figures.as_mut().unwrap().positions_by_month[1].possible = Some(2);
        let facts = assemble(Some(&package), &DealInput::default(), AS_OF);
        let within_three = one(num(NumFact::NewPosition, Some(1), Some(3)));
        assert_eq!(evaluate(&within_three, 1, &facts, &[]).status(), VerdictStatus::Review);
    }

    #[test]
    fn a_multi_account_month_straddles_a_negative_day_limit() {
        let package =
            package(vec![period("2026-09-01", "2026-09-30", 2, 10, 12), period("2026-09-01", "2026-09-30", 2, 5, 9)]);
        let facts = assemble(Some(&package), &DealInput::default(), AS_OF);
        let three_days = one(num(NumFact::WorstMonthNegativeDays, None, Some(3)));
        assert_eq!(
            outcome(&three_days, &facts),
            Outcome::Unproven(Unproven::Straddles(FactKey::Num(NumFact::WorstMonthNegativeDays)))
        );
    }

    fn waiver(check: CheckId, lender_revision: u32, analysis_revision: Option<String>) -> Waiver {
        Waiver {
            lender: crate::criteria::LenderId::parse("lnd_aaaaaaaaaa").unwrap(),
            check,
            lender_revision,
            analysis_revision,
            by: "sample.reviewer".to_string(),
            at: datetime!(2026-10-23 14:10 UTC),
            reason: "The statements show one operating account".to_string(),
        }
    }

    #[test]
    fn waivers_bind_to_both_revisions() {
        let facts = deal();
        let analysis = facts.analysis.as_ref().map(|analysis| analysis.revision.clone());
        let note = Note { id: NoteId(1), kind: NoteKind::Condition, when: vec![], text: "No account switch".into() };
        let policy = active(vec![rule(1, vec![], num(NumFact::WorstMonthDeposits, Some(15), None))], vec![note]);
        let on_this =
            [waiver(CheckId::Rule(RuleId(1)), 4, analysis.clone()), waiver(CheckId::Note(NoteId(1)), 4, analysis)];

        let applied = evaluate(&policy, 4, &facts, &on_this);
        assert_eq!(applied.status(), VerdictStatus::Match);
        assert!(matches!(applied.checks[0].outcome, Outcome::Waived { overruled: Overruled::Unproven(_), .. }));

        let later_revision = evaluate(&policy, 5, &facts, &on_this);
        assert_eq!(later_revision.status(), VerdictStatus::Review);
        assert_eq!(later_revision.stale_waivers.len(), 2);

        let other_analysis = [waiver(CheckId::Rule(RuleId(1)), 4, Some("ff".repeat(32)))];
        assert_eq!(evaluate(&policy, 4, &facts, &other_analysis).stale_waivers.len(), 1);
    }

    #[test]
    fn a_waiver_overrules_a_fail_but_never_touches_a_pass() {
        let facts = deal();
        let analysis = facts.analysis.as_ref().map(|analysis| analysis.revision.clone());
        let policy = active(
            vec![
                rule(1, vec![], num(NumFact::CreditScore, Some(700), None)),
                rule(2, vec![], num(NumFact::CreditScore, Some(600), None)),
            ],
            vec![],
        );
        let waivers =
            [waiver(CheckId::Rule(RuleId(1)), 1, analysis.clone()), waiver(CheckId::Rule(RuleId(2)), 1, analysis)];
        let evaluation = evaluate(&policy, 1, &facts, &waivers);
        assert!(matches!(evaluation.checks[0].outcome, Outcome::Waived { overruled: Overruled::Fail, .. }));
        assert_eq!(evaluation.checks[1].outcome, Outcome::Pass);
        assert_eq!(evaluation.status(), VerdictStatus::Match);
    }

    #[test]
    fn industry_needs_a_confirmation_before_a_restriction_passes() {
        let industries = test_industries();
        let no_cannabis =
            Predicate::Industry(Membership::NotIn(NonEmptySet::new(industries.resolve("cannabis")).unwrap()));
        let policy = one(no_cannabis);
        let unconfirmed = assemble(None, &DealInput { application: application(), ..DealInput::default() }, AS_OF);
        assert_eq!(outcome(&policy, &unconfirmed), Outcome::Unproven(Unproven::FactUnknown(FactKey::Industry)));
        assert_eq!(outcome(&policy, &deal()), Outcome::Pass);
    }

    #[test]
    fn an_empty_policy_matches_every_deal() {
        let policy = LenderPolicy::new(LenderStatus::Draft, vec![], vec![]).unwrap();
        assert_eq!(evaluate(&policy, 1, &deal(), &[]).status(), VerdictStatus::Match);
    }
}
