//! Criteria in words, for the admin pages, the API's check text and revision diffs.

use super::{LenderRecord, Membership, Note, NoteKind, Predicate, Rule, SubmissionChannel};
use crate::facts::application::Industries;
use crate::facts::{FactKey, FlagFact, NumFact};

pub fn money(cents: i64) -> String {
    let sign = if cents < 0 { "-" } else { "" };
    let cents = cents.unsigned_abs();
    let dollars = (cents / 100).to_string();
    let mut grouped = String::new();
    for (index, digit) in dollars.chars().enumerate() {
        if index > 0 && (dollars.len() - index).is_multiple_of(3) {
            grouped.push(',');
        }
        grouped.push(digit);
    }
    format!("{sign}${grouped}.{:02}", cents % 100)
}

pub fn fact_label(key: FactKey) -> &'static str {
    match key {
        FactKey::Num(NumFact::MonthlyTrueRevenueCents) => "Monthly True revenue",
        FactKey::Num(NumFact::CreditScore) => "Credit score",
        FactKey::Num(NumFact::TimeInBusinessMonths) => "Months in business",
        FactKey::Num(NumFact::WorstMonthNegativeDays) => "Negative days in the worst statement month",
        FactKey::Num(NumFact::WorstMonthDeposits) => "Deposits in the worst statement month",
        FactKey::Num(NumFact::NewPosition) => "New position",
        FactKey::Num(NumFact::StatementMonths) => "Statement months",
        FactKey::Num(NumFact::RequestedAmountCents) => "Requested amount",
        FactKey::State => "State",
        FactKey::Industry => "Industry",
        FactKey::Entity => "Entity",
        FactKey::Flag(FlagFact::OpenBankruptcy) => "Open bankruptcy",
        FactKey::Flag(FlagFact::OpenJudgement) => "Open judgement",
        FactKey::Flag(FlagFact::TaxLien) => "Tax lien",
        FactKey::Flag(FlagFact::OpenLawsuit) => "Open lawsuit",
        FactKey::Flag(FlagFact::DefaultHistory) => "Default history",
        FactKey::Flag(FlagFact::HomeBased) => "Home-based business",
        FactKey::Flag(FlagFact::FunderPaymentHistory) => "Funder payment history",
    }
}

pub fn number(fact: NumFact, value: i64) -> String {
    if fact.is_money() { money(value) } else { value.to_string() }
}

pub fn predicate(predicate: &Predicate, industries: &Industries) -> String {
    match predicate {
        Predicate::Num { fact, bound } => {
            let label = fact_label(FactKey::Num(*fact));
            match (bound.min(), bound.max()) {
                (Some(min), Some(max)) if min == max => format!("{label} is {}", number(*fact, min)),
                (Some(min), Some(max)) => format!("{label} from {} to {}", number(*fact, min), number(*fact, max)),
                (Some(min), None) => format!("{label} at least {}", number(*fact, min)),
                (None, Some(max)) => format!("{label} at most {}", number(*fact, max)),
                (None, None) => unreachable!("a bound has a side"),
            }
        }
        Predicate::State(set) => membership("State", set, |code| code.code().to_string()),
        Predicate::Industry(set) => membership("Industry", set, |id| industries.label(id).to_string()),
        Predicate::Entity(set) => membership("Entity", set, |kind| kind.label().to_string()),
        Predicate::Flag { fact, is } => {
            let label = fact_label(FactKey::Flag(*fact));
            if *is { label.to_string() } else { format!("No {}", label.to_lowercase()) }
        }
    }
}

fn membership<T: Ord + Clone>(label: &str, set: &Membership<T>, name: impl Fn(&T) -> String) -> String {
    let (verb, values) = match set {
        Membership::In(values) => ("is one of", values),
        Membership::NotIn(values) => ("is not one of", values),
    };
    let names: Vec<String> = values.iter().map(name).collect();
    format!("{label} {verb} {}", names.join(", "))
}

fn guard(when: &[Predicate], industries: &Industries) -> Option<String> {
    (!when.is_empty()).then(|| {
        let parts: Vec<String> = when.iter().map(|p| predicate(p, industries)).collect();
        format!("When {}", parts.join(" and "))
    })
}

pub fn rule(rule: &Rule, industries: &Industries) -> String {
    let require = predicate(&rule.require, industries);
    match guard(&rule.when, industries) {
        Some(when) => format!("{when}: {require}"),
        None => require,
    }
}

pub fn note_scope(note: &Note, industries: &Industries) -> Option<String> {
    guard(&note.when, industries)
}

pub fn note_kind(kind: NoteKind) -> &'static str {
    match kind {
        NoteKind::Condition => "condition (holds a deal at review)",
        NoteKind::Info => "info (never changes a verdict)",
    }
}

/// One line per fact of the record, in a fixed order; a diff compares these lines.
pub fn record_lines(record: &LenderRecord, industries: &Industries) -> Vec<String> {
    let profile = &record.profile;
    let policy = &record.policy;
    let mut lines = vec![format!("Name: {}", profile.name), format!("Status: {}", policy.status().key())];
    if let Some(id) = &profile.legacy_record_id {
        lines.push(format!("Record Id: {id}"));
    }
    lines.push(match profile.bucket {
        Some(bucket) => format!("Bucket: {} ({})", bucket.number(), bucket.meaning()),
        None => "Bucket: unassigned".to_string(),
    });
    let products: Vec<&str> = profile.products.iter().map(|product| product.label()).collect();
    lines.push(format!("Products: {}", if products.is_empty() { "none".to_string() } else { products.join(", ") }));
    lines.push(match &profile.submission {
        None => "Submission: none".to_string(),
        Some(SubmissionChannel::Email { to, cc }) => {
            let to: Vec<&str> = to.as_slice().iter().map(|address| address.as_str()).collect();
            let cc: Vec<&str> = cc.iter().map(|address| address.as_str()).collect();
            if cc.is_empty() {
                format!("Submission: email to {}", to.join(", "))
            } else {
                format!("Submission: email to {}, cc {}", to.join(", "), cc.join(", "))
            }
        }
        Some(SubmissionChannel::Portal { url }) => format!("Submission: portal {}", url.as_str()),
    });
    for contact in &profile.contacts {
        let parts: Vec<&str> =
            [contact.name.as_deref(), contact.phone.as_deref(), contact.email.as_ref().map(|e| e.as_str())]
                .into_iter()
                .flatten()
                .collect();
        lines.push(format!("Contact ({}): {}", contact.role, parts.join(", ")));
    }
    for (label, value) in [
        ("Exclusivity", &profile.terms.exclusivity),
        ("Clawback", &profile.terms.clawback),
        ("Commission", &profile.terms.commission),
    ] {
        if let Some(value) = value {
            lines.push(format!("{label}: {value}"));
        }
    }
    for item in policy.rules() {
        lines.push(format!("{}: {}", item.id, rule(item, industries)));
    }
    for note in policy.notes() {
        let scope = note_scope(note, industries).map(|scope| format!(" [{scope}]")).unwrap_or_default();
        lines.push(format!("{} ({}){scope}: {}", note.id, note.kind.key(), note.text));
    }
    lines
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Change {
    Removed(String),
    Added(String),
}

/// Lines only in `old`, then lines only in `new`, each in its own order.
pub fn diff(old: &[String], new: &[String]) -> Vec<Change> {
    let removed = old.iter().filter(|line| !new.contains(line)).cloned().map(Change::Removed);
    let added = new.iter().filter(|line| !old.contains(line)).cloned().map(Change::Added);
    removed.chain(added).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::criteria::testing::{num, profile, rule as make_rule, state_in};
    use crate::criteria::{LenderPolicy, LenderStatus};
    use crate::facts::application::test_industries;

    #[test]
    fn money_groups_thousands() {
        assert_eq!(money(2_500_000), "$25,000.00");
        assert_eq!(money(100_000_000), "$1,000,000.00");
        assert_eq!(money(5), "$0.05");
        assert_eq!(money(-123_456), "-$1,234.56");
    }

    #[test]
    fn rules_read_as_sentences() {
        let industries = test_industries();
        let texas_first = make_rule(4, vec![state_in(&["TX"])], num(NumFact::NewPosition, None, Some(1)));
        assert_eq!(rule(&texas_first, &industries), "When State is one of TX: New position at most 1");
        let revenue = make_rule(1, vec![], num(NumFact::MonthlyTrueRevenueCents, Some(2_500_000), None));
        assert_eq!(rule(&revenue, &industries), "Monthly True revenue at least $25,000.00");
        let flag = Predicate::Flag { fact: FlagFact::DefaultHistory, is: false };
        assert_eq!(predicate(&flag, &industries), "No default history");
    }

    #[test]
    fn a_diff_shows_only_changed_lines() {
        let industries = test_industries();
        let before = LenderRecord {
            profile: profile("FABRIKAM FUNDING"),
            policy: LenderPolicy::new(
                LenderStatus::Active,
                vec![make_rule(1, vec![], num(NumFact::WorstMonthNegativeDays, None, Some(1)))],
                vec![],
            )
            .unwrap(),
        };
        let mut after = before.clone();
        after.policy = LenderPolicy::new(
            LenderStatus::Active,
            vec![make_rule(1, vec![], num(NumFact::WorstMonthNegativeDays, None, Some(3)))],
            vec![],
        )
        .unwrap();
        let changes = diff(&record_lines(&before, &industries), &record_lines(&after, &industries));
        assert_eq!(
            changes,
            [
                Change::Removed("r1: Negative days in the worst statement month at most 1".into()),
                Change::Added("r1: Negative days in the worst statement month at most 3".into()),
            ]
        );
    }
}
