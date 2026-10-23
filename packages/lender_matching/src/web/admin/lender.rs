//! One lender's pages. The edit form is all text so that a refused save re-renders exactly what
//! was sent; `LenderForm::to_record` parses it with the same domain constructors the store reads.

use std::collections::{BTreeMap, BTreeSet};

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use maud::{Markup, html};

use super::{
    Fields, PageError, RawForm, author, csrf, errors, fields, import_row, page, redirect, reports, require, shown_time,
};
use crate::criteria::describe::{self, Change};
use crate::criteria::{
    Bound, Bucket, Contact, EmailAddress, LenderId, LenderPolicy, LenderProfile, LenderRecord, LenderStatus,
    Membership, NonEmpty, NonEmptySet, Note, NoteId, NoteKind, PolicyError, PortalUrl, Predicate, Product, Rule,
    RuleId, SubmissionChannel, Terms,
};
use crate::facts::application::{EntityKind, Industries, IndustryId, Jurisdiction};
use crate::facts::{FactKey, FlagFact, NumFact};
use crate::store::auth::{AdminUser, Role};
use crate::store::{Author, Revision, SaveError, Saved};
use crate::web::Shared;

fn lender_id(text: &str) -> Result<LenderId, PageError> {
    LenderId::parse(text).ok_or_else(PageError::not_found)
}

fn by(user: &AdminUser) -> Author {
    Author::User { id: user.id, username: user.username.clone() }
}

fn dollars(cents: i64) -> String {
    if cents % 100 == 0 { (cents / 100).to_string() } else { format!("{}.{:02}", cents / 100, (cents % 100).abs()) }
}

fn parse_dollars(text: &str) -> Option<i64> {
    let text: String = text.trim().trim_start_matches('$').chars().filter(|c| *c != ',').collect();
    let (whole, cents) = text.split_once('.').unwrap_or((&text, ""));
    if whole.is_empty() || cents.len() > 2 || !whole.bytes().chain(cents.bytes()).all(|b| b.is_ascii_digit()) {
        return None;
    }
    let cents = format!("{cents:0<2}");
    whole.parse::<i64>().ok()?.checked_mul(100)?.checked_add(cents.parse::<i64>().ok()?)
}

fn parse_count(text: &str) -> Option<i64> {
    let text = text.trim();
    (!text.is_empty() && text.bytes().all(|b| b.is_ascii_digit())).then(|| text.parse().ok()).flatten()
}

fn parse_number(fact: NumFact, text: &str) -> Option<i64> {
    if fact.is_money() { parse_dollars(text) } else { parse_count(text) }
}

fn show_number(fact: NumFact, value: i64) -> String {
    if fact.is_money() { dollars(value) } else { value.to_string() }
}

const OPS: [(&str, &str); 8] = [
    ("at_least", "at least"),
    ("at_most", "at most"),
    ("between", "from … to (write 1-3)"),
    ("is", "is exactly"),
    ("one_of", "is one of"),
    ("not_one_of", "is not one of"),
    ("yes", "is yes"),
    ("no", "is no"),
];

#[derive(Clone, Default)]
pub struct PredicateRow {
    pub fact: String,
    pub op: String,
    pub value: String,
}

impl PredicateRow {
    fn is_blank(&self) -> bool {
        self.fact.trim().is_empty() && self.op.trim().is_empty() && self.value.trim().is_empty()
    }

    fn read(fields: &Fields, prefix: &str) -> PredicateRow {
        PredicateRow {
            fact: fields.get(&format!("{prefix}.fact")).to_string(),
            op: fields.get(&format!("{prefix}.op")).to_string(),
            value: fields.get(&format!("{prefix}.value")).to_string(),
        }
    }

    fn of(predicate: &Predicate, industries: &Industries) -> PredicateRow {
        let key = crate::criteria::eval::reads(predicate).key().to_string();
        let (op, value) = match predicate {
            Predicate::Num { fact, bound } => match (bound.min(), bound.max()) {
                (Some(min), Some(max)) if min == max => ("is", show_number(*fact, min)),
                (Some(min), Some(max)) => {
                    ("between", format!("{}-{}", show_number(*fact, min), show_number(*fact, max)))
                }
                (Some(min), None) => ("at_least", show_number(*fact, min)),
                (None, Some(max)) => ("at_most", show_number(*fact, max)),
                (None, None) => unreachable!("a bound has a side"),
            },
            Predicate::State(set) => membership(set, |state| state.code().to_string()),
            Predicate::Industry(set) => membership(set, |id| industries.label(id).to_string()),
            Predicate::Entity(set) => membership(set, |kind| kind.key().to_string()),
            Predicate::Flag { is, .. } => (if *is { "yes" } else { "no" }, String::new()),
        };
        PredicateRow { fact: key, op: op.to_string(), value }
    }

    fn parse(&self, industries: &Industries) -> Result<Predicate, String> {
        let key = FactKey::from_key(self.fact.trim()).ok_or("choose a fact")?;
        let label = describe::fact_label(key);
        let op = self.op.trim();
        let value = self.value.trim();
        let compare_error = || format!("{label} cannot be compared with “{op}”");
        match key {
            FactKey::Num(fact) => {
                let number = |text: &str| {
                    parse_number(fact, text).ok_or_else(|| {
                        if fact.is_money() {
                            format!("{label}: “{text}” is not an amount in dollars")
                        } else {
                            format!("{label}: “{text}” is not a whole number")
                        }
                    })
                };
                let bound = match op {
                    "at_least" => Bound::at_least(number(value)?),
                    "at_most" => Bound::at_most(number(value)?),
                    "is" => {
                        let value = number(value)?;
                        Bound::new(Some(value), Some(value)).expect("a point")
                    }
                    "between" => {
                        let (low, high) = value
                            .split_once(" to ")
                            .or_else(|| value.split_once('-'))
                            .ok_or_else(|| format!("{label}: write a range as 1-3"))?;
                        Bound::new(Some(number(low)?), Some(number(high)?))
                            .ok_or_else(|| format!("{label}: the range's start is above its end"))?
                    }
                    _ => return Err(compare_error()),
                };
                Ok(Predicate::Num { fact, bound })
            }
            FactKey::State | FactKey::Industry | FactKey::Entity if !matches!(op, "one_of" | "not_one_of") => {
                Err(compare_error())
            }
            FactKey::State => {
                let codes =
                    value.split(|c: char| c == ';' || c == ',' || c.is_whitespace()).filter(|code| !code.is_empty());
                let states = codes
                    .map(|code| {
                        Jurisdiction::from_code(code).ok_or_else(|| format!("State: “{code}” is not a postal code"))
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                Ok(Predicate::State(member(op, states).ok_or_else(|| set_error(label, op))?))
            }
            FactKey::Industry => {
                let names = value.split(';').map(str::trim).filter(|name| !name.is_empty());
                let ids = names
                    .map(|name| {
                        industries
                            .all()
                            .find(|industry| industry.id.as_str() == name || industry.label.eq_ignore_ascii_case(name))
                            .map(|industry| industry.id.clone())
                            .ok_or_else(|| format!("Industry: “{name}” is not on the Industries page"))
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                Ok(Predicate::Industry(member(op, ids).ok_or_else(|| set_error(label, op))?))
            }
            FactKey::Entity => {
                let names = value.split([';', ',']).map(str::trim).filter(|name| !name.is_empty());
                let kinds = names
                    .map(|name| {
                        EntityKind::ALL
                            .into_iter()
                            .find(|kind| kind.key() == name || kind.label().eq_ignore_ascii_case(name))
                            .ok_or_else(|| format!("Entity: “{name}” is not an entity type"))
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                Ok(Predicate::Entity(member(op, kinds).ok_or_else(|| set_error(label, op))?))
            }
            FactKey::Flag(fact) => match op {
                "yes" => Ok(Predicate::Flag { fact, is: true }),
                "no" => Ok(Predicate::Flag { fact, is: false }),
                _ => Err(compare_error()),
            },
        }
    }
}

fn membership<T: Ord + Clone>(set: &Membership<T>, name: impl Fn(&T) -> String) -> (&'static str, String) {
    let op = match set {
        Membership::In(_) => "one_of",
        Membership::NotIn(_) => "not_one_of",
    };
    (op, set.set().iter().map(name).collect::<Vec<_>>().join("; "))
}

fn member<T: Ord + Clone>(op: &str, values: Vec<T>) -> Option<Membership<T>> {
    let set = NonEmptySet::new(values)?;
    match op {
        "one_of" => Some(Membership::In(set)),
        "not_one_of" => Some(Membership::NotIn(set)),
        _ => None,
    }
}

fn set_error(label: &str, op: &str) -> String {
    if matches!(op, "one_of" | "not_one_of") {
        format!("{label}: list at least one value")
    } else {
        format!("{label} takes “is one of” or “is not one of”")
    }
}

#[derive(Clone, Default)]
pub struct RuleRow {
    pub id: String,
    pub when: Vec<PredicateRow>,
    pub require: PredicateRow,
    pub source: String,
    pub delete: bool,
}

#[derive(Clone, Default)]
pub struct NoteRow {
    pub id: String,
    pub kind: String,
    pub text: String,
    pub when: Vec<PredicateRow>,
    pub delete: bool,
}

#[derive(Clone, Default)]
pub struct ContactRow {
    pub role: String,
    pub name: String,
    pub phone: String,
    pub email: String,
}

/// The base criteria: each unguarded rule on a standard fact shows as one field, keyed by slot.
#[derive(Clone, Default)]
pub struct BaseForm {
    pub ids: BTreeMap<&'static str, String>,
    pub revenue: String,
    pub credit: String,
    pub deposits: String,
    pub negative_days: String,
    pub position_from: String,
    pub position_to: String,
    pub months_in_business: String,
    pub industries: BTreeSet<String>,
    pub states: String,
    pub entities: BTreeSet<String>,
    pub no_home_based: bool,
    pub no_default_history: bool,
}

const SLOTS: [&str; 11] = [
    "revenue",
    "credit",
    "deposits",
    "negative_days",
    "positions",
    "months_in_business",
    "industries",
    "states",
    "entities",
    "home_based",
    "default_history",
];

fn slot_of(predicate: &Predicate) -> Option<&'static str> {
    let min_only = |bound: &Bound| bound.min().is_some() && bound.max().is_none();
    match predicate {
        Predicate::Num { fact: NumFact::MonthlyTrueRevenueCents, bound } if min_only(bound) => Some("revenue"),
        Predicate::Num { fact: NumFact::CreditScore, bound } if min_only(bound) => Some("credit"),
        Predicate::Num { fact: NumFact::WorstMonthDeposits, bound } if min_only(bound) => Some("deposits"),
        Predicate::Num { fact: NumFact::WorstMonthNegativeDays, bound } if bound.min().is_none() => {
            Some("negative_days")
        }
        Predicate::Num { fact: NumFact::NewPosition, .. } => Some("positions"),
        Predicate::Num { fact: NumFact::TimeInBusinessMonths, bound } if min_only(bound) => Some("months_in_business"),
        Predicate::Industry(Membership::NotIn(_)) => Some("industries"),
        Predicate::State(Membership::NotIn(_)) => Some("states"),
        Predicate::Entity(Membership::NotIn(_)) => Some("entities"),
        Predicate::Flag { fact: FlagFact::HomeBased, is: false } => Some("home_based"),
        Predicate::Flag { fact: FlagFact::DefaultHistory, is: false } => Some("default_history"),
        _ => None,
    }
}

impl BaseForm {
    fn fill(&mut self, slot: &'static str, predicate: &Predicate) {
        match predicate {
            Predicate::Num { fact, bound } => {
                let show = |value: Option<i64>| value.map(|value| show_number(*fact, value)).unwrap_or_default();
                match slot {
                    "revenue" => self.revenue = show(bound.min()),
                    "credit" => self.credit = show(bound.min()),
                    "deposits" => self.deposits = show(bound.min()),
                    "negative_days" => self.negative_days = show(bound.max()),
                    "months_in_business" => self.months_in_business = show(bound.min()),
                    _ => {
                        self.position_from = show(bound.min());
                        self.position_to = show(bound.max());
                    }
                }
            }
            Predicate::Industry(set) => self.industries = set.set().iter().map(|id| id.to_string()).collect(),
            Predicate::State(set) => {
                self.states = set.set().iter().map(|state| state.code()).collect::<Vec<_>>().join("; ")
            }
            Predicate::Entity(set) => self.entities = set.set().iter().map(|kind| kind.key().to_string()).collect(),
            Predicate::Flag { fact: FlagFact::HomeBased, .. } => self.no_home_based = true,
            Predicate::Flag { .. } => self.no_default_history = true,
        }
    }

    fn predicates(&self, industries: &Industries, errors: &mut Vec<String>) -> Vec<(&'static str, Predicate)> {
        let mut out = Vec::new();
        let mut number = |slot: &'static str, fact: NumFact, text: &str, label: &str, at_least: bool| {
            if text.trim().is_empty() {
                return;
            }
            match parse_number(fact, text) {
                Some(value) => {
                    let bound = if at_least { Bound::at_least(value) } else { Bound::at_most(value) };
                    out.push((slot, Predicate::Num { fact, bound }));
                }
                None => errors.push(format!("{label}: “{}” is not a valid value", text.trim())),
            }
        };
        number("revenue", NumFact::MonthlyTrueRevenueCents, &self.revenue, "Minimum monthly True revenue", true);
        number("credit", NumFact::CreditScore, &self.credit, "Minimum credit score", true);
        number("deposits", NumFact::WorstMonthDeposits, &self.deposits, "Minimum deposits in the worst month", true);
        number("negative_days", NumFact::WorstMonthNegativeDays, &self.negative_days, "Maximum negative days", false);
        number(
            "months_in_business",
            NumFact::TimeInBusinessMonths,
            &self.months_in_business,
            "Minimum months in business",
            true,
        );
        let (from, to) = (self.position_from.trim(), self.position_to.trim());
        if !from.is_empty() || !to.is_empty() {
            let parse = |text: &str| if text.is_empty() { Ok(None) } else { parse_count(text).map(Some).ok_or(()) };
            match (parse(from), parse(to)) {
                (Ok(min), Ok(max)) => match Bound::new(min, max) {
                    Some(bound) => out.push(("positions", Predicate::Num { fact: NumFact::NewPosition, bound })),
                    None => errors.push("New position: the start is above the end".to_string()),
                },
                _ => errors.push("New position: use whole numbers".to_string()),
            }
        }
        let ids: Vec<IndustryId> = self
            .industries
            .iter()
            .filter_map(|slug| industries.all().find(|i| i.id.as_str() == slug))
            .map(|i| i.id.clone())
            .collect();
        if let Some(set) = NonEmptySet::new(ids) {
            out.push(("industries", Predicate::Industry(Membership::NotIn(set))));
        }
        if !self.states.trim().is_empty() {
            let row = PredicateRow { fact: "state".into(), op: "not_one_of".into(), value: self.states.clone() };
            match row.parse(industries) {
                Ok(predicate) => out.push(("states", predicate)),
                Err(error) => errors.push(format!("Restricted states: {error}")),
            }
        }
        let kinds: Vec<EntityKind> = self.entities.iter().filter_map(|key| EntityKind::from_key(key)).collect();
        if let Some(set) = NonEmptySet::new(kinds) {
            out.push(("entities", Predicate::Entity(Membership::NotIn(set))));
        }
        if self.no_home_based {
            out.push(("home_based", Predicate::Flag { fact: FlagFact::HomeBased, is: false }));
        }
        if self.no_default_history {
            out.push(("default_history", Predicate::Flag { fact: FlagFact::DefaultHistory, is: false }));
        }
        out
    }
}

#[derive(Clone, Default)]
pub struct LenderForm {
    pub base_revision: Option<u32>,
    pub reason: String,
    pub name: String,
    pub record_id: String,
    pub bucket: String,
    pub products: BTreeSet<String>,
    pub channel: String,
    pub email_to: String,
    pub email_cc: String,
    pub portal: String,
    pub contacts: Vec<ContactRow>,
    pub exclusivity: String,
    pub clawback: String,
    pub commission: String,
    pub base: BaseForm,
    pub rules: Vec<RuleRow>,
    pub notes: Vec<NoteRow>,
}

fn addresses(text: &str) -> Vec<&str> {
    text.split(|c: char| c == ',' || c == ';' || c.is_whitespace()).filter(|address| !address.is_empty()).collect()
}

impl LenderForm {
    pub fn blank() -> LenderForm {
        LenderForm {
            products: BTreeSet::from([Product::Mca.key().to_string()]),
            channel: "none".into(),
            ..Default::default()
        }
    }

    pub fn of(revision: &Revision, industries: &Industries) -> LenderForm {
        let record = &revision.record;
        let profile = &record.profile;
        let mut form = LenderForm {
            base_revision: Some(revision.number),
            name: profile.name.clone(),
            record_id: profile.legacy_record_id.clone().unwrap_or_default(),
            bucket: profile.bucket.map(|bucket| bucket.number().to_string()).unwrap_or_default(),
            products: profile.products.iter().map(|product| product.key().to_string()).collect(),
            channel: "none".into(),
            exclusivity: profile.terms.exclusivity.clone().unwrap_or_default(),
            clawback: profile.terms.clawback.clone().unwrap_or_default(),
            commission: profile.terms.commission.clone().unwrap_or_default(),
            ..Default::default()
        };
        match &profile.submission {
            None => {}
            Some(SubmissionChannel::Email { to, cc }) => {
                form.channel = "email".into();
                form.email_to = to.as_slice().iter().map(EmailAddress::as_str).collect::<Vec<_>>().join(", ");
                form.email_cc = cc.iter().map(EmailAddress::as_str).collect::<Vec<_>>().join(", ");
            }
            Some(SubmissionChannel::Portal { url }) => {
                form.channel = "portal".into();
                form.portal = url.as_str().to_string();
            }
        }
        form.contacts = profile
            .contacts
            .iter()
            .map(|contact| ContactRow {
                role: contact.role.clone(),
                name: contact.name.clone().unwrap_or_default(),
                phone: contact.phone.clone().unwrap_or_default(),
                email: contact.email.as_ref().map(|email| email.as_str().to_string()).unwrap_or_default(),
            })
            .collect();
        for rule in record.policy.rules() {
            let slot = rule.when.is_empty().then(|| slot_of(&rule.require)).flatten();
            match slot {
                Some(slot) if !form.base.ids.contains_key(slot) => {
                    form.base.ids.insert(slot, rule.id.to_string());
                    form.base.fill(slot, &rule.require);
                }
                _ => form.rules.push(RuleRow {
                    id: rule.id.to_string(),
                    when: rule.when.iter().map(|p| PredicateRow::of(p, industries)).collect(),
                    require: PredicateRow::of(&rule.require, industries),
                    source: rule.source.clone().unwrap_or_default(),
                    delete: false,
                }),
            }
        }
        form.notes = record
            .policy
            .notes()
            .iter()
            .map(|note| NoteRow {
                id: note.id.to_string(),
                kind: note.kind.key().to_string(),
                text: note.text.clone(),
                when: note.when.iter().map(|p| PredicateRow::of(p, industries)).collect(),
                delete: false,
            })
            .collect();
        form
    }

    pub fn read(fields: &Fields) -> LenderForm {
        let when = |prefix: &str| -> Vec<PredicateRow> {
            fields
                .rows(&format!("{prefix}.when"))
                .into_iter()
                .map(|j| PredicateRow::read(fields, &format!("{prefix}.when.{j}")))
                .filter(|row| !row.is_blank())
                .collect()
        };
        let mut base = BaseForm {
            revenue: fields.get("base.revenue").into(),
            credit: fields.get("base.credit").into(),
            deposits: fields.get("base.deposits").into(),
            negative_days: fields.get("base.negative_days").into(),
            position_from: fields.get("base.position_from").into(),
            position_to: fields.get("base.position_to").into(),
            months_in_business: fields.get("base.months_in_business").into(),
            industries: fields.all("base.industry").into_iter().collect(),
            states: fields.get("base.states").into(),
            entities: fields.all("base.entity").into_iter().collect(),
            no_home_based: fields.has("base.no_home_based"),
            no_default_history: fields.has("base.no_default_history"),
            ..Default::default()
        };
        for slot in SLOTS {
            let id = fields.get(&format!("base.{slot}.id")).trim();
            if !id.is_empty() {
                base.ids.insert(slot, id.to_string());
            }
        }
        LenderForm {
            base_revision: fields.get("base_revision").parse().ok(),
            reason: fields.get("reason").into(),
            name: fields.get("name").into(),
            record_id: fields.get("record_id").into(),
            bucket: fields.get("bucket").into(),
            products: fields.all("product").into_iter().collect(),
            channel: fields.get("channel").into(),
            email_to: fields.get("email_to").into(),
            email_cc: fields.get("email_cc").into(),
            portal: fields.get("portal").into(),
            contacts: fields
                .rows("contact")
                .into_iter()
                .map(|i| ContactRow {
                    role: fields.get(&format!("contact.{i}.role")).into(),
                    name: fields.get(&format!("contact.{i}.name")).into(),
                    phone: fields.get(&format!("contact.{i}.phone")).into(),
                    email: fields.get(&format!("contact.{i}.email")).into(),
                })
                .filter(|row| ![&row.role, &row.name, &row.phone, &row.email].iter().all(|v| v.trim().is_empty()))
                .collect(),
            exclusivity: fields.get("exclusivity").into(),
            clawback: fields.get("clawback").into(),
            commission: fields.get("commission").into(),
            base,
            rules: fields
                .rows("rule")
                .into_iter()
                .map(|i| RuleRow {
                    id: fields.get(&format!("rule.{i}.id")).into(),
                    when: when(&format!("rule.{i}")),
                    require: PredicateRow::read(fields, &format!("rule.{i}.req")),
                    source: fields.get(&format!("rule.{i}.source")).into(),
                    delete: fields.has(&format!("rule.{i}.delete")),
                })
                .filter(|row| !(row.id.is_empty() && row.require.is_blank() && row.when.is_empty()))
                .collect(),
            notes: fields
                .rows("note")
                .into_iter()
                .map(|i| NoteRow {
                    id: fields.get(&format!("note.{i}.id")).into(),
                    kind: fields.get(&format!("note.{i}.kind")).into(),
                    text: fields.get(&format!("note.{i}.text")).into(),
                    when: when(&format!("note.{i}")),
                    delete: fields.has(&format!("note.{i}.delete")),
                })
                .collect(),
        }
    }

    /// `base` is the revision the form was loaded from: it supplies the status, and the source of a
    /// base field whose rule is unchanged. None for a new lender, which starts as a draft.
    pub fn to_record(&self, base: Option<&Revision>, industries: &Industries) -> Result<LenderRecord, Vec<String>> {
        let mut errors = Vec::new();
        let profile = self.profile(&mut errors);
        let base_policy = base.map(|revision| &revision.record.policy);
        let mut taken: BTreeSet<u32> =
            base_policy.into_iter().flat_map(|policy| policy.rules()).map(|rule| rule.id.0).collect();
        let mut parse_rule_id = |text: &str, errors: &mut Vec<String>| -> Option<RuleId> {
            if text.trim().is_empty() {
                return None;
            }
            let id = RuleId::parse(text.trim());
            if id.is_none() {
                errors.push(format!("“{text}” is not a rule id"));
            }
            id.inspect(|id| {
                taken.insert(id.0);
            })
        };
        let base_ids: BTreeMap<&'static str, Option<RuleId>> =
            self.base.ids.iter().map(|(slot, id)| (*slot, parse_rule_id(id, &mut errors))).collect();
        let row_ids: Vec<Option<RuleId>> = self.rules.iter().map(|row| parse_rule_id(&row.id, &mut errors)).collect();
        let mut next = taken.iter().max().copied().unwrap_or(0);
        let mut fresh = || {
            next += 1;
            RuleId(next)
        };
        let mut rules = Vec::new();
        for (slot, require) in self.base.predicates(industries, &mut errors) {
            let id = base_ids.get(slot).copied().flatten().unwrap_or_else(&mut fresh);
            let source = base_policy
                .and_then(|policy| policy.rules().iter().find(|rule| rule.id == id))
                .filter(|rule| rule.when.is_empty() && rule.require == require)
                .and_then(|rule| rule.source.clone());
            rules.push(Rule { id, when: Vec::new(), require, source });
        }
        for (index, (row, id)) in self.rules.iter().zip(row_ids).enumerate() {
            if row.delete {
                continue;
            }
            let label =
                format!("Rule {}", if row.id.is_empty() { format!("{} (new)", index + 1) } else { row.id.clone() });
            let require = row.require.parse(industries).map_err(|error| errors.push(format!("{label}: {error}"))).ok();
            let when: Vec<Predicate> = row
                .when
                .iter()
                .filter_map(|p| {
                    p.parse(industries).map_err(|error| errors.push(format!("{label}, when: {error}"))).ok()
                })
                .collect();
            if let Some(require) = require {
                let source = Some(row.source.trim().to_string()).filter(|source| !source.is_empty());
                rules.push(Rule { id: id.unwrap_or_else(&mut fresh), when, require, source });
            }
        }
        let mut note_ids: BTreeSet<u32> =
            base_policy.into_iter().flat_map(|policy| policy.notes()).map(|note| note.id.0).collect();
        let mut notes = Vec::new();
        let mut pending = Vec::new();
        for row in &self.notes {
            if row.delete || (row.id.is_empty() && row.text.trim().is_empty() && row.when.is_empty()) {
                continue;
            }
            let label = format!("Note {}", if row.id.is_empty() { "(new)".to_string() } else { row.id.clone() });
            let kind = match row.kind.as_str() {
                "info" => NoteKind::Info,
                _ => NoteKind::Condition,
            };
            if row.text.trim().is_empty() {
                errors.push(format!("{label}: write the note's text or tick delete"));
                continue;
            }
            let when: Vec<Predicate> = row
                .when
                .iter()
                .filter_map(|p| {
                    p.parse(industries).map_err(|error| errors.push(format!("{label}, when: {error}"))).ok()
                })
                .collect();
            let id = if row.id.trim().is_empty() {
                None
            } else {
                let id = NoteId::parse(row.id.trim());
                if id.is_none() {
                    errors.push(format!("“{}” is not a note id", row.id));
                }
                id.inspect(|id| {
                    note_ids.insert(id.0);
                })
            };
            pending.push((id, kind, when, row.text.trim().to_string()));
        }
        let mut next_note = note_ids.iter().max().copied().unwrap_or(0);
        for (id, kind, when, text) in pending {
            let id = id.unwrap_or_else(|| {
                next_note += 1;
                NoteId(next_note)
            });
            notes.push(Note { id, kind, when, text });
        }
        let status = base.map_or(LenderStatus::Draft, |revision| revision.record.policy.status());
        if !errors.is_empty() {
            return Err(errors);
        }
        let policy = LenderPolicy::new(status, rules, notes).map_err(|error| {
            vec![match error {
                PolicyError::NoCriteria => {
                    "An active lender needs at least one rule. Pause the lender before removing every rule.".to_string()
                }
                other => other.to_string(),
            }]
        })?;
        Ok(LenderRecord { profile: profile.ok_or_else(|| vec!["the profile is incomplete".to_string()])?, policy })
    }

    fn profile(&self, errors: &mut Vec<String>) -> Option<LenderProfile> {
        let name = self.name.split_whitespace().collect::<Vec<_>>().join(" ");
        if name.is_empty() {
            errors.push("Name: a lender needs a name".to_string());
        }
        let bucket = match self.bucket.trim() {
            "" => None,
            number => match number.parse::<u8>().ok().and_then(|n| Bucket::try_from(n).ok()) {
                Some(bucket) => Some(bucket),
                None => {
                    errors.push("Bucket: choose 1, 2 or 3".to_string());
                    None
                }
            },
        };
        let products: BTreeSet<Product> = self.products.iter().filter_map(|key| Product::from_key(key)).collect();
        if products.is_empty() {
            errors.push("Products: choose at least one product".to_string());
        }
        let mut parse_addresses = |text: &str, label: &str| -> Vec<EmailAddress> {
            addresses(text)
                .into_iter()
                .filter_map(|address| {
                    let parsed = EmailAddress::parse(address);
                    if parsed.is_none() {
                        errors.push(format!("{label}: “{address}” is not an email address"));
                    }
                    parsed
                })
                .collect()
        };
        let submission = match self.channel.as_str() {
            "email" => {
                let to = parse_addresses(&self.email_to, "Submission to");
                let cc = parse_addresses(&self.email_cc, "Submission cc");
                match NonEmpty::new(to) {
                    Some(to) => Some(SubmissionChannel::Email { to, cc }),
                    None => {
                        errors.push("Submission to: an email channel needs an address".to_string());
                        None
                    }
                }
            }
            "portal" => match PortalUrl::parse(&self.portal) {
                Some(url) => Some(SubmissionChannel::Portal { url }),
                None => {
                    errors.push("Portal: give an https:// address".to_string());
                    None
                }
            },
            _ => None,
        };
        let text = |value: &str| Some(value.trim().to_string()).filter(|value| !value.is_empty());
        let mut contacts = Vec::new();
        for (index, row) in self.contacts.iter().enumerate() {
            let Some(role) = text(&row.role) else {
                errors.push(format!("Contact {}: give the contact's role", index + 1));
                continue;
            };
            let email = text(&row.email).and_then(|address| {
                let parsed = EmailAddress::parse(&address);
                if parsed.is_none() {
                    errors.push(format!("Contact {}: “{address}” is not an email address", index + 1));
                }
                parsed
            });
            contacts.push(Contact { role, name: text(&row.name), phone: text(&row.phone), email });
        }
        let terms = Terms {
            exclusivity: text(&self.exclusivity),
            clawback: text(&self.clawback),
            commission: text(&self.commission),
        };
        (!name.is_empty()).then_some(LenderProfile {
            name,
            legacy_record_id: text(&self.record_id),
            bucket,
            products,
            submission,
            contacts,
            terms,
        })
    }

    /// Handles a button that changes the form instead of saving it; false for `save`.
    /// `rule_from_note.<i>` names a note row by its rendered position, so `read` keeps blank note
    /// rows and `to_record` skips them.
    fn apply(&mut self, action: &str) -> bool {
        match action {
            "add_rule" => self.rules.push(RuleRow::default()),
            "add_note" => self.notes.push(NoteRow { kind: "condition".into(), ..Default::default() }),
            other => {
                let Some(index) = other.strip_prefix("rule_from_note.") else { return false };
                if let Some(note) = index.parse::<usize>().ok().and_then(|index| self.notes.get(index)) {
                    let rule = RuleRow { when: note.when.clone(), source: note.text.clone(), ..Default::default() };
                    self.rules.push(rule);
                }
            }
        }
        true
    }
}

fn fact_options(selected: &str) -> Markup {
    html! {
        option value="" selected[selected.is_empty()] { "" }
        @for key in FactKey::all() {
            option value=(key.key()) selected[selected == key.key()] { (describe::fact_label(key)) }
        }
    }
}

fn op_options(selected: &str) -> Markup {
    html! {
        option value="" selected[selected.is_empty()] { "" }
        @for (key, label) in OPS { option value=(key) selected[selected == key] { (label) } }
    }
}

fn predicate_inputs(prefix: &str, row: &PredicateRow) -> Markup {
    html! {
        select name={ (prefix) ".fact" } aria-label="fact" { (fact_options(&row.fact)) }
        " "
        select name={ (prefix) ".op" } aria-label="comparison" { (op_options(&row.op)) }
        " "
        input type="text" name={ (prefix) ".value" } value=(row.value) aria-label="value" size="28";
    }
}

fn when_inputs(prefix: &str, rows: &[PredicateRow]) -> Markup {
    let blank = PredicateRow::default();
    html! {
        @for (j, row) in rows.iter().chain([&blank]).enumerate() {
            div { "When " (predicate_inputs(&format!("{prefix}.when.{j}"), row)) @if j + 1 < rows.len() + 1 { " and" } }
        }
    }
}

fn text_input(name: &str, label: &str, value: &str, hint: &str) -> Markup {
    html! {
        p { label { (label) " " input type="text" name=(name) value=(value); } @if !hint.is_empty() { " " span.note { (hint) } } }
    }
}

pub fn edit_form(
    user: &AdminUser,
    form: &LenderForm,
    industries: &Industries,
    action: &str,
    problems: &[String],
) -> Markup {
    let base = &form.base;
    let selected_retired: Vec<&String> =
        base.industries.iter().filter(|slug| industries.resolve(slug).is_none()).collect();
    html! {
        (errors(problems))
        form method="post" action=(action) {
            (csrf(user))
            @if let Some(revision) = form.base_revision { input type="hidden" name="base_revision" value=(revision); }
            @for (slot, id) in &base.ids { input type="hidden" name={ "base." (slot) ".id" } value=(id); }
            p {
                label { "Reason for this change " input type="text" name="reason" value=(form.reason) size="50"; }
                " " button name="action" value="save" { "Save" }
            }
            fieldset {
                legend { "Base criteria" }
                p.note { "Each field is one rule that applies to every deal. Leave a field empty for no requirement. A rule with a condition belongs in the rules below." }
                (text_input("base.revenue", "Minimum monthly True revenue ($)", &base.revenue, ""))
                (text_input("base.credit", "Minimum credit score", &base.credit, ""))
                (text_input("base.deposits", "Minimum deposits in the worst statement month", &base.deposits, "counted between True revenue credits and all credits"))
                (text_input("base.negative_days", "Maximum negative days in the worst statement month", &base.negative_days, ""))
                p {
                    "New position from " input type="text" name="base.position_from" value=(base.position_from) size="4";
                    " to " input type="text" name="base.position_to" value=(base.position_to) size="4";
                    " " span.note { "the position a new advance would take; leave “to” empty for no upper limit" }
                }
                (text_input("base.months_in_business", "Minimum months in business", &base.months_in_business, ""))
                p { "Restricted industries:" }
                div {
                    @for industry in industries.active() {
                        label { input type="checkbox" name="base.industry" value=(industry.id) checked[base.industries.contains(industry.id.as_str())]; " " (industry.label) } " "
                    }
                    @for slug in &selected_retired {
                        label { input type="checkbox" name="base.industry" value=(slug) checked; " " (industries.label(&IndustryId::unsaved((*slug).clone()))) " (retired)" } " "
                    }
                }
                (text_input("base.states", "Restricted states", &base.states, "postal codes, such as PR; QC"))
                p {
                    "Restricted entity types: "
                    @for kind in EntityKind::ALL {
                        label { input type="checkbox" name="base.entity" value=(kind.key()) checked[base.entities.contains(kind.key())]; " " (kind.label()) } " "
                    }
                }
                p { label { input type="checkbox" name="base.no_home_based" checked[base.no_home_based]; " Home-based businesses not accepted" } }
                p { label { input type="checkbox" name="base.no_default_history" checked[base.no_default_history]; " Default history not accepted" } }
            }
            fieldset {
                legend { "Rules" }
                p.note { "A rule applies when every “when” row holds, and then requires its last row. Rules only add requirements; to loosen a base field for one state, clear the field and add two rules." }
                @for (i, row) in form.rules.iter().enumerate() {
                    div.row {
                        input type="hidden" name={ "rule." (i) ".id" } value=(row.id);
                        strong { @if row.id.is_empty() { "New rule" } @else { "Rule " (row.id) } }
                        @if let Ok(text) = rule_text(row, industries) { " " span.note { (text) } }
                        (when_inputs(&format!("rule.{i}"), &row.when))
                        div { "Require " (predicate_inputs(&format!("rule.{i}.req"), &row.require)) }
                        div { label { "Source text " input type="text" name={ "rule." (i) ".source" } value=(row.source) size="60"; } }
                        label { input type="checkbox" name={ "rule." (i) ".delete" } checked[row.delete]; " delete this rule" }
                    }
                }
                button name="action" value="add_rule" { "Add rule" }
            }
            fieldset {
                legend { "Notes" }
                p.note { "A condition note holds every deal it may apply to at review. Give it a “when” to narrow it, turn it into rules, or make it info, which never changes a verdict." }
                @for (i, row) in form.notes.iter().enumerate() {
                    div.row {
                        input type="hidden" name={ "note." (i) ".id" } value=(row.id);
                        strong { @if row.id.is_empty() { "New note" } @else { "Note " (row.id) } }
                        " "
                        select name={ "note." (i) ".kind" } aria-label="kind" {
                            option value="condition" selected[row.kind != "info"] { "condition (holds a deal at review)" }
                            option value="info" selected[row.kind == "info"] { "info (never changes a verdict)" }
                        }
                        textarea name={ "note." (i) ".text" } rows="2" { (row.text) }
                        (when_inputs(&format!("note.{i}"), &row.when))
                        label { input type="checkbox" name={ "note." (i) ".delete" } checked[row.delete]; " delete this note" }
                        " " button name="action" value={ "rule_from_note." (i) } { "Add a rule from this note" }
                    }
                }
                button name="action" value="add_note" { "Add note" }
            }
            fieldset {
                legend { "Profile" }
                (text_input("name", "Name", &form.name, ""))
                (text_input("record_id", "Info Hub Record Id", &form.record_id, ""))
                p {
                    "Bucket: "
                    label { input type="radio" name="bucket" value="" checked[form.bucket.is_empty()]; " unassigned" } " "
                    @for bucket in Bucket::ALL {
                        label { input type="radio" name="bucket" value=(bucket.number()) checked[form.bucket == bucket.number().to_string()]; " " (bucket.number()) ": " (bucket.meaning()) } " "
                    }
                }
                p {
                    "Products: "
                    @for product in Product::ALL {
                        label { input type="checkbox" name="product" value=(product.key()) checked[form.products.contains(product.key())]; " " (product.label()) } " "
                    }
                }
                p {
                    "Submission channel: "
                    @for (key, label) in [("none", "none yet"), ("email", "email"), ("portal", "portal")] {
                        label { input type="radio" name="channel" value=(key) checked[form.channel == key || (key == "none" && form.channel.is_empty())]; " " (label) } " "
                    }
                }
                (text_input("email_to", "Email to", &form.email_to, "addresses separated by commas"))
                (text_input("email_cc", "Email cc", &form.email_cc, ""))
                (text_input("portal", "Portal address", &form.portal, "https://"))
                p { "Contacts:" }
                @for (i, row) in form.contacts.iter().chain([&ContactRow::default()]).enumerate() {
                    div {
                        input type="text" name={ "contact." (i) ".role" } value=(row.role) placeholder="role" aria-label="role";
                        " " input type="text" name={ "contact." (i) ".name" } value=(row.name) placeholder="name" aria-label="name";
                        " " input type="text" name={ "contact." (i) ".phone" } value=(row.phone) placeholder="phone" aria-label="phone";
                        " " input type="text" name={ "contact." (i) ".email" } value=(row.email) placeholder="email" aria-label="email";
                    }
                }
                (text_input("exclusivity", "Exclusivity", &form.exclusivity, ""))
                (text_input("clawback", "Clawback", &form.clawback, ""))
                (text_input("commission", "Commission", &form.commission, ""))
            }
            p { button name="action" value="save" { "Save" } }
        }
    }
}

fn rule_text(row: &RuleRow, industries: &Industries) -> Result<String, String> {
    let require = row.require.parse(industries)?;
    let when = row.when.iter().map(|p| p.parse(industries)).collect::<Result<Vec<_>, _>>()?;
    Ok(describe::rule(&Rule { id: RuleId(0), when, require, source: None }, industries))
}

pub async fn new_page(State(app): State<Shared>, user: AdminUser) -> Result<Markup, PageError> {
    require(&user, Role::Editor)?;
    let industries = app.read(|tx| tx.industries())?;
    Ok(page(
        Some(&user),
        "Add a lender",
        edit_form(&user, &LenderForm::blank(), &industries, "/admin/lenders/new", &[]),
    ))
}

pub async fn create(State(app): State<Shared>, user: AdminUser, form: RawForm) -> Result<Response, PageError> {
    require(&user, Role::Editor)?;
    let fields = fields(form);
    fields.check_csrf(&user)?;
    let industries = app.read(|tx| tx.industries())?;
    let mut form = LenderForm::read(&fields);
    let action = fields.get("action").to_string();
    if form.apply(&action) {
        return Ok(page(Some(&user), "Add a lender", edit_form(&user, &form, &industries, "/admin/lenders/new", &[]))
            .into_response());
    }
    match form.to_record(None, &industries) {
        Err(problems) => Ok((
            StatusCode::UNPROCESSABLE_ENTITY,
            page(Some(&user), "Add a lender", edit_form(&user, &form, &industries, "/admin/lenders/new", &problems)),
        )
            .into_response()),
        Ok(record) => {
            let created = app.write(|tx| tx.create_lender(&record, &by(&user), None))?;
            Ok(redirect(&format!("/admin/lenders/{}", created.lender)))
        }
    }
}

pub async fn edit_page(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
) -> Result<Markup, PageError> {
    require(&user, Role::Editor)?;
    let lender = lender_id(&id)?;
    let (head, industries) = app.read(|tx| Ok((tx.head(&lender)?, tx.industries()?)))?;
    let head = head.ok_or_else(PageError::not_found)?;
    let form = LenderForm::of(&head, &industries);
    let title = format!("Edit {} (revision {})", head.record.profile.name, head.number);
    Ok(page(Some(&user), &title, edit_form(&user, &form, &industries, &format!("/admin/lenders/{lender}/edit"), &[])))
}

fn diff_list(changes: &[Change]) -> Markup {
    html! {
        @if changes.is_empty() { p.note { "No change." } }
        ul {
            @for change in changes {
                @match change {
                    Change::Removed(line) => li.removed { "− " (line) },
                    Change::Added(line) => li.added { "+ " (line) },
                }
            }
        }
    }
}

pub async fn edit(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    require(&user, Role::Editor)?;
    let lender = lender_id(&id)?;
    let fields = fields(form);
    fields.check_csrf(&user)?;
    let mut form = LenderForm::read(&fields);
    let base_number =
        form.base_revision.ok_or_else(|| PageError::status(StatusCode::BAD_REQUEST, "The form lacks its revision."))?;
    let (base, industries) = app.read(|tx| Ok((tx.revision(&lender, base_number)?, tx.industries()?)))?;
    let base = base.ok_or_else(PageError::not_found)?;
    let action_url = format!("/admin/lenders/{lender}/edit");
    let title = format!("Edit {} (revision {})", base.record.profile.name, base.number);
    if form.apply(fields.get("action")) {
        return Ok(page(Some(&user), &title, edit_form(&user, &form, &industries, &action_url, &[])).into_response());
    }
    let record = match form.to_record(Some(&base), &industries) {
        Ok(record) => record,
        Err(problems) => {
            let body = edit_form(&user, &form, &industries, &action_url, &problems);
            return Ok((StatusCode::UNPROCESSABLE_ENTITY, page(Some(&user), &title, body)).into_response());
        }
    };
    let reason = Some(form.reason.trim()).filter(|reason| !reason.is_empty());
    match app.write(|tx| tx.save_revision(&lender, base_number, &record, &by(&user), reason)) {
        Ok(Saved::New(_) | Saved::Unchanged(_)) => Ok(redirect(&format!("/admin/lenders/{lender}"))),
        Err(SaveError::NotFound) => Err(PageError::not_found()),
        Err(SaveError::Store(error)) => Err(error.into()),
        Err(SaveError::Conflict { head }) => {
            let lines = |record: &LenderRecord| describe::record_lines(record, &industries);
            let theirs = describe::diff(&lines(&base.record), &lines(&head.record));
            let yours = describe::diff(&lines(&base.record), &lines(&record));
            let fresh = LenderForm::of(&head, &industries);
            let body = html! {
                p.error {
                    "Changed by another editor: " (author(&head.author)) " saved revision " (head.number) " at " (shown_time(head.saved_at))
                    " while you edited revision " (base.number) ". Nothing of yours was saved."
                }
                h2 { "Their change" }
                (diff_list(&theirs))
                h2 { "Your unsaved change" }
                (diff_list(&yours))
                h2 { "Re-apply your change to revision " (head.number) }
                (edit_form(&user, &fresh, &industries, &action_url, &[]))
            };
            Ok((StatusCode::CONFLICT, page(Some(&user), &format!("Edit {}", head.record.profile.name), body))
                .into_response())
        }
    }
}

fn rules_and_notes(record: &LenderRecord, industries: &Industries) -> Markup {
    html! {
        h2 { "Rules" }
        @if record.policy.rules().is_empty() { p.error { "No rules: this lender cannot be activated until it has one." } }
        table {
            tr { th { "Id" } th { "Rule" } th { "Made from" } }
            @for rule in record.policy.rules() {
                tr { td { (rule.id) } td { (describe::rule(rule, industries)) } td.note { (rule.source.as_deref().unwrap_or("")) } }
            }
        }
        h2 { "Notes" }
        table {
            tr { th { "Id" } th { "Kind" } th { "Applies" } th { "Text" } }
            @for note in record.policy.notes() {
                tr {
                    td { (note.id) }
                    td { (describe::note_kind(note.kind)) }
                    td { (describe::note_scope(note, industries).unwrap_or_else(|| "always".to_string())) }
                    td { (note.text) }
                }
            }
        }
    }
}

fn profile_table(record: &LenderRecord, industries: &Industries) -> Markup {
    let lines = describe::record_lines(record, industries);
    let rule_or_note = |line: &&String| {
        line.split_once(':').is_some_and(|(id, _)| {
            let id = id.split_whitespace().next().unwrap_or_default();
            RuleId::parse(id).is_some() || NoteId::parse(id).is_some()
        })
    };
    html! { ul { @for line in lines.iter().filter(|line| !rule_or_note(line)) { li { (line) } } } }
}

pub async fn view(State(app): State<Shared>, user: AdminUser, Path(id): Path<String>) -> Result<Markup, PageError> {
    let lender = lender_id(&id)?;
    let (head, industries) = app.read(|tx| Ok((tx.head(&lender)?, tx.industries()?)))?;
    let head = head.ok_or_else(PageError::not_found)?;
    let reports = reports(&app)?;
    let badges = super::attention(&head, &reports);
    let status = head.record.policy.status();
    Ok(page(
        Some(&user),
        &head.record.profile.name,
        html! {
            p {
                "Revision " (head.number) ", saved by " (author(&head.author)) " at " (shown_time(head.saved_at)) ". "
                @for badge in &badges { span.badge { (badge) } }
            }
            p {
                a href={ "/admin/lenders/" (lender) "/history" } { "History" }
                @if user.can(Role::Editor) {
                    " · " a href={ "/admin/lenders/" (lender) "/edit" } { "Edit" }
                    @if status != LenderStatus::Active { " · " a href={ "/admin/lenders/" (lender) "/activate" } { "Review and activate" } }
                }
            }
            @if user.can(Role::Editor) && status == LenderStatus::Active {
                form method="post" action={ "/admin/lenders/" (lender) "/pause" } {
                    (csrf(&user))
                    input type="hidden" name="base_revision" value=(head.number);
                    label { "Reason " input type="text" name="reason"; } " "
                    button { "Pause matching for this lender" }
                }
            }
            h2 { "Profile" }
            (profile_table(&head.record, &industries))
            (rules_and_notes(&head.record, &industries))
        },
    ))
}

pub async fn history(State(app): State<Shared>, user: AdminUser, Path(id): Path<String>) -> Result<Markup, PageError> {
    let lender = lender_id(&id)?;
    let (revisions, industries) = app.read(|tx| Ok((tx.history(&lender)?, tx.industries()?)))?;
    let latest = revisions.last().ok_or_else(PageError::not_found)?;
    let mut previous: Vec<String> = Vec::new();
    let mut entries = Vec::new();
    for revision in &revisions {
        let lines = describe::record_lines(&revision.record, &industries);
        entries.push((revision, describe::diff(&previous, &lines)));
        previous = lines;
    }
    Ok(page(
        Some(&user),
        &format!("History of {}", latest.record.profile.name),
        html! {
            p { a href={ "/admin/lenders/" (lender) } { "Back to the lender" } }
            @for (revision, changes) in entries.iter().rev() {
                h2 { "Revision " (revision.number) }
                p.note {
                    (author(&revision.author)) " at " (shown_time(revision.saved_at))
                    @if let Some(reason) = &revision.reason { ": " (reason) }
                }
                (diff_list(changes))
            }
        },
    ))
}

pub async fn activate_page(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
) -> Result<Markup, PageError> {
    require(&user, Role::Editor)?;
    let lender = lender_id(&id)?;
    let (head, industries) = app.read(|tx| Ok((tx.head(&lender)?, tx.industries()?)))?;
    let head = head.ok_or_else(PageError::not_found)?;
    let reports = reports(&app)?;
    let imported = reports.values().rev().find_map(|report| import_row(report, &lender));
    Ok(page(
        Some(&user),
        &format!("Review and activate {}", head.record.profile.name),
        html! {
            p.note { "Activation is a new revision. Later Info Hub imports leave a lender a person has saved as it is." }
            h2 { "Profile" }
            (profile_table(&head.record, &industries))
            p.note { "Check the products: the import sets MCA only." }
            (rules_and_notes(&head.record, &industries))
            @if let Some(row) = imported {
                h2 { "The Info Hub row, cell by cell (line " (row.line) ")" }
                table {
                    tr { th { "Column" } th { "Cell" } th { "Became" } }
                    @for cell in row.cells.iter().filter(|cell| cell.raw.is_some() || cell.column.is_criterion()) {
                        tr {
                            td { (cell.column.header()) }
                            td { (cell.raw.as_deref().unwrap_or("")) }
                            td { (super::cell_outcome(&cell.outcome)) }
                        }
                    }
                }
                p.note { "An empty criteria column reads as no requirement; activating confirms each blank." }
            } @else {
                p.note { "No Info Hub import created this lender." }
            }
            @if head.record.policy.rules().is_empty() {
                p.error { "This lender has no rules, so it would match every deal. Add at least one rule before activating." }
            } @else if head.record.policy.status() == LenderStatus::Active {
                p { "This lender is active." }
            } @else {
                form method="post" action={ "/admin/lenders/" (lender) "/activate" } {
                    (csrf(&user))
                    input type="hidden" name="base_revision" value=(head.number);
                    label { "Reason " input type="text" name="reason" value="reviewed and activated" size="40"; } " "
                    button { "Activate revision " (head.number) }
                }
            }
        },
    ))
}

async fn set_status(
    app: &Shared,
    user: &AdminUser,
    id: &str,
    form: RawForm,
    status: LenderStatus,
) -> Result<Response, PageError> {
    require(user, Role::Editor)?;
    let lender = lender_id(id)?;
    let fields = fields(form);
    fields.check_csrf(user)?;
    let base: u32 = fields
        .get("base_revision")
        .parse()
        .map_err(|_| PageError::status(StatusCode::BAD_REQUEST, "The form lacks its revision."))?;
    let head = app.read(|tx| tx.head(&lender))?.ok_or_else(PageError::not_found)?;
    let policy = head.record.policy.with_status(status).map_err(|_| {
        PageError::status(
            StatusCode::CONFLICT,
            "This lender has no rules, so it would match every deal. Add a rule first.",
        )
    })?;
    let record = LenderRecord { profile: head.record.profile.clone(), policy };
    let reason = fields.get("reason").trim().to_string();
    let reason = Some(reason.as_str()).filter(|reason| !reason.is_empty());
    match app.write(|tx| tx.save_revision(&lender, base, &record, &by(user), reason)) {
        Ok(_) => Ok(redirect(&format!("/admin/lenders/{lender}"))),
        Err(SaveError::Conflict { head }) => Err(PageError::status(
            StatusCode::CONFLICT,
            &format!(
                "Changed by another editor: {} saved revision {}. Reload the lender and decide again.",
                author(&head.author),
                head.number
            ),
        )),
        Err(SaveError::NotFound) => Err(PageError::not_found()),
        Err(SaveError::Store(error)) => Err(error.into()),
    }
}

pub async fn activate(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    set_status(&app, &user, &id, form, LenderStatus::Active).await
}

pub async fn pause(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    set_status(&app, &user, &id, form, LenderStatus::Paused).await
}
