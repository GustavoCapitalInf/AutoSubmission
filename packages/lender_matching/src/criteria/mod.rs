//! What a lender requires and offers. A `LenderRecord` is the whole content of one revision.

pub mod describe;
pub mod eval;

use std::collections::BTreeSet;
use std::fmt;

use serde::{Deserialize, Serialize};

use crate::facts::application::{EntityKind, IndustryId, Jurisdiction};
use crate::facts::{FlagFact, NumFact};

/// The stored `LenderRecord` JSON layout; a bump leaves older revisions unreadable until `from_stored` upgrades them.
pub const RECORD_FORMAT: u32 = 1;

/// `lnd_` and 10 lower-case base32 characters.
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
pub struct LenderId(String);

impl LenderId {
    pub fn generate() -> LenderId {
        const ALPHABET: &[u8; 32] = b"abcdefghijklmnopqrstuvwxyz234567";
        let mut bytes = [0u8; 10];
        getrandom::fill(&mut bytes).expect("the OS random source is available");
        let suffix: String = bytes.iter().map(|byte| char::from(ALPHABET[usize::from(byte % 32)])).collect();
        LenderId(format!("lnd_{suffix}"))
    }

    pub fn parse(text: &str) -> Option<LenderId> {
        let suffix = text.strip_prefix("lnd_")?;
        (suffix.len() == 10 && suffix.bytes().all(|b| b.is_ascii_lowercase() || (b'2'..=b'7').contains(&b)))
            .then(|| LenderId(text.to_string()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for LenderId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

/// Equal records serialize to equal bytes: sets are `BTreeSet`, rules and notes are sorted by id
/// and the field order is fixed.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct LenderRecord {
    pub profile: LenderProfile,
    pub policy: LenderPolicy,
}

impl LenderRecord {
    pub fn to_stored(&self) -> String {
        serde_json::to_string(self).expect("a lender record always serializes")
    }

    pub fn from_stored(format: u32, json: &str) -> Result<LenderRecord, String> {
        match format {
            RECORD_FORMAT => serde_json::from_str(json).map_err(|error| error.to_string()),
            other => Err(format!("lender record format {other} is not readable by this build")),
        }
    }
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct LenderProfile {
    pub name: String,
    pub legacy_record_id: Option<String>,
    pub bucket: Option<Bucket>,
    /// A lender is evaluated only for a product it offers.
    pub products: BTreeSet<Product>,
    pub submission: Option<SubmissionChannel>,
    pub contacts: Vec<Contact>,
    pub terms: Terms,
}

/// Which copy of the application a lender receives.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
#[serde(try_from = "u8", into = "u8")]
pub enum Bucket {
    /// Trusted: the original application.
    Original = 1,
    /// Uncertain: selected contact fields changed.
    ContactsAltered = 2,
    /// Known to share or resell merchant data: broadly changed.
    BroadlyAltered = 3,
}

impl Bucket {
    pub const ALL: [Bucket; 3] = [Bucket::Original, Bucket::ContactsAltered, Bucket::BroadlyAltered];

    pub fn number(self) -> u8 {
        self as u8
    }

    pub fn meaning(self) -> &'static str {
        match self {
            Bucket::Original => "trusted; receives the original application",
            Bucket::ContactsAltered => "uncertain; receives the application with selected contact fields changed",
            Bucket::BroadlyAltered => "known to share or resell merchant data; receives a broadly changed application",
        }
    }
}

impl TryFrom<u8> for Bucket {
    type Error = String;
    fn try_from(number: u8) -> Result<Self, Self::Error> {
        Bucket::ALL.into_iter().find(|bucket| bucket.number() == number).ok_or_else(|| format!("no bucket {number}"))
    }
}

impl From<Bucket> for u8 {
    fn from(bucket: Bucket) -> u8 {
        bucket.number()
    }
}

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Product {
    Mca,
    TermLoan,
    LineOfCredit,
    Equipment,
    Sba,
}

impl Product {
    pub const ALL: [Product; 5] =
        [Product::Mca, Product::TermLoan, Product::LineOfCredit, Product::Equipment, Product::Sba];

    pub fn key(self) -> &'static str {
        match self {
            Product::Mca => "mca",
            Product::TermLoan => "term_loan",
            Product::LineOfCredit => "line_of_credit",
            Product::Equipment => "equipment",
            Product::Sba => "sba",
        }
    }

    pub fn from_key(key: &str) -> Option<Product> {
        Product::ALL.into_iter().find(|product| product.key() == key)
    }

    pub fn label(self) -> &'static str {
        match self {
            Product::Mca => "MCA",
            Product::TermLoan => "term loan",
            Product::LineOfCredit => "line of credit",
            Product::Equipment => "equipment finance",
            Product::Sba => "SBA loan",
        }
    }
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum SubmissionChannel {
    Email { to: NonEmpty<EmailAddress>, cc: Vec<EmailAddress> },
    Portal { url: PortalUrl },
}

/// An address with one `@`, a non-empty local part, a dotted domain and no whitespace.
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Debug, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct EmailAddress(String);

impl EmailAddress {
    pub fn parse(text: &str) -> Option<EmailAddress> {
        let text = text.trim();
        let (local, domain) = text.split_once('@')?;
        let valid = !local.is_empty()
            && !domain.contains('@')
            && domain.contains('.')
            && !domain.starts_with('.')
            && !domain.ends_with('.')
            && !text.chars().any(char::is_whitespace);
        valid.then(|| EmailAddress(text.to_string()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl TryFrom<String> for EmailAddress {
    type Error = String;
    fn try_from(text: String) -> Result<Self, Self::Error> {
        EmailAddress::parse(&text).ok_or_else(|| "not an email address".to_string())
    }
}

impl From<EmailAddress> for String {
    fn from(address: EmailAddress) -> String {
        address.0
    }
}

/// An `https://` URL without whitespace.
#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct PortalUrl(String);

impl PortalUrl {
    pub fn parse(text: &str) -> Option<PortalUrl> {
        let text = text.trim();
        let rest = text.strip_prefix("https://")?;
        (!rest.is_empty() && !text.chars().any(char::is_whitespace)).then(|| PortalUrl(text.to_string()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl TryFrom<String> for PortalUrl {
    type Error = String;
    fn try_from(text: String) -> Result<Self, Self::Error> {
        PortalUrl::parse(&text).ok_or_else(|| "not an https URL".to_string())
    }
}

impl From<PortalUrl> for String {
    fn from(url: PortalUrl) -> String {
        url.0
    }
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(try_from = "Vec<T>", into = "Vec<T>")]
pub struct NonEmpty<T: Clone>(Vec<T>);

impl<T: Clone> NonEmpty<T> {
    pub fn new(items: Vec<T>) -> Option<NonEmpty<T>> {
        (!items.is_empty()).then_some(NonEmpty(items))
    }

    pub fn as_slice(&self) -> &[T] {
        &self.0
    }
}

impl<T: Clone> TryFrom<Vec<T>> for NonEmpty<T> {
    type Error = &'static str;
    fn try_from(items: Vec<T>) -> Result<Self, Self::Error> {
        NonEmpty::new(items).ok_or("must not be empty")
    }
}

impl<T: Clone> From<NonEmpty<T>> for Vec<T> {
    fn from(items: NonEmpty<T>) -> Vec<T> {
        items.0
    }
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct Contact {
    pub role: String,
    pub name: Option<String>,
    pub phone: Option<String>,
    pub email: Option<EmailAddress>,
}

#[derive(Clone, Default, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct Terms {
    pub exclusivity: Option<String>,
    pub clawback: Option<String>,
    pub commission: Option<String>,
}

/// Only `Active` lenders are evaluated; the others are listed as inactive.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LenderStatus {
    Draft,
    Active,
    Paused,
}

impl LenderStatus {
    pub fn key(self) -> &'static str {
        match self {
            LenderStatus::Draft => "draft",
            LenderStatus::Active => "active",
            LenderStatus::Paused => "paused",
        }
    }
}

/// Everything that decides a verdict. Built only by `LenderPolicy::new`.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(try_from = "PolicyParts")]
pub struct LenderPolicy {
    status: LenderStatus,
    rules: Vec<Rule>,
    notes: Vec<Note>,
}

#[derive(Deserialize)]
struct PolicyParts {
    status: LenderStatus,
    rules: Vec<Rule>,
    notes: Vec<Note>,
}

#[derive(Clone, PartialEq, Eq, Debug, thiserror::Error)]
pub enum PolicyError {
    #[error("rule id {0} is used twice")]
    DuplicateRule(RuleId),
    #[error("note id {0} is used twice")]
    DuplicateNote(NoteId),
    /// An active lender with nothing to check would match every deal.
    #[error("an active lender needs at least one rule")]
    NoCriteria,
}

impl TryFrom<PolicyParts> for LenderPolicy {
    type Error = PolicyError;
    fn try_from(parts: PolicyParts) -> Result<Self, Self::Error> {
        LenderPolicy::new(parts.status, parts.rules, parts.notes)
    }
}

impl LenderPolicy {
    /// Sorts rules and notes by id. Refuses a repeated id, and an `Active` policy without rules.
    pub fn new(status: LenderStatus, mut rules: Vec<Rule>, mut notes: Vec<Note>) -> Result<LenderPolicy, PolicyError> {
        rules.sort_by_key(|rule| rule.id);
        notes.sort_by_key(|note| note.id);
        if let Some(pair) = rules.windows(2).find(|pair| pair[0].id == pair[1].id) {
            return Err(PolicyError::DuplicateRule(pair[0].id));
        }
        if let Some(pair) = notes.windows(2).find(|pair| pair[0].id == pair[1].id) {
            return Err(PolicyError::DuplicateNote(pair[0].id));
        }
        if status == LenderStatus::Active && rules.is_empty() {
            return Err(PolicyError::NoCriteria);
        }
        Ok(LenderPolicy { status, rules, notes })
    }

    pub fn status(&self) -> LenderStatus {
        self.status
    }

    pub fn rules(&self) -> &[Rule] {
        &self.rules
    }

    pub fn notes(&self) -> &[Note] {
        &self.notes
    }

    pub fn with_status(&self, status: LenderStatus) -> Result<LenderPolicy, PolicyError> {
        LenderPolicy::new(status, self.rules.clone(), self.notes.clone())
    }
}

/// `r<n>`, unique within one policy.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct RuleId(pub u32);

/// `n<n>`, unique within one policy.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct NoteId(pub u32);

macro_rules! prefixed_id {
    ($type:ident, $prefix:literal) => {
        impl $type {
            pub fn parse(text: &str) -> Option<$type> {
                let digits = text.strip_prefix($prefix)?;
                if digits.is_empty() || digits.starts_with('0') || !digits.bytes().all(|b| b.is_ascii_digit()) {
                    return None;
                }
                digits.parse().ok().map($type)
            }
        }

        impl fmt::Display for $type {
            fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                write!(f, concat!($prefix, "{}"), self.0)
            }
        }

        impl TryFrom<String> for $type {
            type Error = String;
            fn try_from(text: String) -> Result<Self, Self::Error> {
                $type::parse(&text).ok_or_else(|| format!("not an id: {text}"))
            }
        }

        impl From<$type> for String {
            fn from(id: $type) -> String {
                id.to_string()
            }
        }
    };
}

prefixed_id!(RuleId, "r");
prefixed_id!(NoteId, "n");

/// A rule or a note of one policy: what a waiver names.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub enum CheckId {
    Rule(RuleId),
    Note(NoteId),
}

impl CheckId {
    pub fn parse(text: &str) -> Option<CheckId> {
        RuleId::parse(text).map(CheckId::Rule).or_else(|| NoteId::parse(text).map(CheckId::Note))
    }
}

impl fmt::Display for CheckId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CheckId::Rule(id) => id.fmt(f),
            CheckId::Note(id) => id.fmt(f),
        }
    }
}

impl TryFrom<String> for CheckId {
    type Error = String;
    fn try_from(text: String) -> Result<Self, Self::Error> {
        CheckId::parse(&text).ok_or_else(|| format!("not a check id: {text}"))
    }
}

impl From<CheckId> for String {
    fn from(id: CheckId) -> String {
        id.to_string()
    }
}

/// A rule applies to a deal that meets every predicate of `when`, and then checks `require`. An
/// empty `when` always applies.
/// Rules only add requirements to each other: there is no precedence and no override.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Rule {
    pub id: RuleId,
    pub when: Vec<Predicate>,
    pub require: Predicate,
    /// The text the rule was made from (an Info Hub cell or a note), shown beside it.
    pub source: Option<String>,
}

/// Text no rule captures. A `Condition` note that may apply holds the verdict at review; an `Info`
/// note is shown and does not change a verdict.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct Note {
    pub id: NoteId,
    pub kind: NoteKind,
    pub when: Vec<Predicate>,
    pub text: String,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NoteKind {
    Condition,
    Info,
}

impl NoteKind {
    pub fn key(self) -> &'static str {
        match self {
            NoteKind::Condition => "condition",
            NoteKind::Info => "info",
        }
    }
}

/// The one predicate language, shared by guards and requirements.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Predicate {
    Num { fact: NumFact, bound: Bound },
    State(Membership<Jurisdiction>),
    Industry(Membership<IndustryId>),
    Entity(Membership<EntityKind>),
    Flag { fact: FlagFact, is: bool },
}

/// Inclusive, in the fact's unit. Built only by `Bound::new`.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(try_from = "BoundParts", into = "BoundParts")]
pub struct Bound {
    min: Option<i64>,
    max: Option<i64>,
}

#[derive(Serialize, Deserialize)]
struct BoundParts {
    min: Option<i64>,
    max: Option<i64>,
}

impl Bound {
    /// None without a side, or with `min > max`.
    pub fn new(min: Option<i64>, max: Option<i64>) -> Option<Bound> {
        match (min, max) {
            (None, None) => None,
            (Some(min), Some(max)) if min > max => None,
            _ => Some(Bound { min, max }),
        }
    }

    pub fn at_least(min: i64) -> Bound {
        Bound { min: Some(min), max: None }
    }

    pub fn at_most(max: i64) -> Bound {
        Bound { min: None, max: Some(max) }
    }

    pub fn min(self) -> Option<i64> {
        self.min
    }

    pub fn max(self) -> Option<i64> {
        self.max
    }
}

impl TryFrom<BoundParts> for Bound {
    type Error = &'static str;
    fn try_from(parts: BoundParts) -> Result<Self, Self::Error> {
        Bound::new(parts.min, parts.max).ok_or("a bound needs a side and min <= max")
    }
}

impl From<Bound> for BoundParts {
    fn from(bound: Bound) -> Self {
        BoundParts { min: bound.min, max: bound.max }
    }
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Membership<T: Ord + Clone> {
    In(NonEmptySet<T>),
    NotIn(NonEmptySet<T>),
}

impl<T: Ord + Clone> Membership<T> {
    pub fn allows(&self, value: &T) -> bool {
        match self {
            Membership::In(set) => set.contains(value),
            Membership::NotIn(set) => !set.contains(value),
        }
    }

    pub fn set(&self) -> &NonEmptySet<T> {
        match self {
            Membership::In(set) | Membership::NotIn(set) => set,
        }
    }
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(try_from = "BTreeSet<T>", into = "BTreeSet<T>")]
pub struct NonEmptySet<T: Ord + Clone>(BTreeSet<T>);

impl<T: Ord + Clone> NonEmptySet<T> {
    pub fn new(items: impl IntoIterator<Item = T>) -> Option<NonEmptySet<T>> {
        let set: BTreeSet<T> = items.into_iter().collect();
        (!set.is_empty()).then_some(NonEmptySet(set))
    }

    pub fn contains(&self, item: &T) -> bool {
        self.0.contains(item)
    }

    pub fn iter(&self) -> impl Iterator<Item = &T> {
        self.0.iter()
    }
}

impl<T: Ord + Clone> TryFrom<BTreeSet<T>> for NonEmptySet<T> {
    type Error = &'static str;
    fn try_from(set: BTreeSet<T>) -> Result<Self, Self::Error> {
        NonEmptySet::new(set).ok_or("a set must not be empty")
    }
}

impl<T: Ord + Clone> From<NonEmptySet<T>> for BTreeSet<T> {
    fn from(set: NonEmptySet<T>) -> BTreeSet<T> {
        set.0
    }
}

#[cfg(test)]
pub(crate) mod testing {
    use super::*;

    pub fn rule(id: u32, when: Vec<Predicate>, require: Predicate) -> Rule {
        Rule { id: RuleId(id), when, require, source: None }
    }

    pub fn num(fact: NumFact, min: Option<i64>, max: Option<i64>) -> Predicate {
        Predicate::Num { fact, bound: Bound::new(min, max).unwrap() }
    }

    pub fn state_in(codes: &[&str]) -> Predicate {
        Predicate::State(Membership::In(
            NonEmptySet::new(codes.iter().map(|c| Jurisdiction::from_code(c).unwrap())).unwrap(),
        ))
    }

    pub fn profile(name: &str) -> LenderProfile {
        LenderProfile {
            name: name.to_string(),
            legacy_record_id: None,
            bucket: None,
            products: BTreeSet::from([Product::Mca]),
            submission: None,
            contacts: Vec::new(),
            terms: Terms::default(),
        }
    }

    pub fn active(rules: Vec<Rule>, notes: Vec<Note>) -> LenderPolicy {
        LenderPolicy::new(LenderStatus::Active, rules, notes).unwrap()
    }
}

#[cfg(test)]
mod tests {
    use super::testing::*;
    use super::*;

    #[test]
    fn policies_refuse_repeated_ids_and_active_without_rules() {
        let revenue = || rule(1, vec![], num(NumFact::MonthlyTrueRevenueCents, Some(1), None));
        assert_eq!(
            LenderPolicy::new(LenderStatus::Draft, vec![revenue(), revenue()], vec![]),
            Err(PolicyError::DuplicateRule(RuleId(1)))
        );
        assert_eq!(LenderPolicy::new(LenderStatus::Active, vec![], vec![]), Err(PolicyError::NoCriteria));
        assert!(LenderPolicy::new(LenderStatus::Draft, vec![], vec![]).is_ok());
        assert!(LenderPolicy::new(LenderStatus::Paused, vec![], vec![]).is_ok());
    }

    #[test]
    fn stored_records_refuse_invalid_content() {
        let policy = LenderPolicy::new(LenderStatus::Draft, vec![], vec![]).unwrap();
        let record = LenderRecord { profile: profile("CONTOSO CAPITAL"), policy };
        let json = record.to_stored();
        assert_eq!(LenderRecord::from_stored(RECORD_FORMAT, &json).unwrap(), record);
        assert!(LenderRecord::from_stored(RECORD_FORMAT + 1, &json).is_err());
        let invalid = json.replace(r#""status":"draft""#, r#""status":"active""#);
        assert!(LenderRecord::from_stored(RECORD_FORMAT, &invalid).is_err(), "active with no rules");
    }

    #[test]
    fn equal_records_serialize_to_equal_bytes() {
        let a = rule(2, vec![], num(NumFact::CreditScore, Some(600), None));
        let b = rule(1, vec![state_in(&["TX", "CA"])], num(NumFact::NewPosition, None, Some(1)));
        let first = LenderPolicy::new(LenderStatus::Draft, vec![a.clone(), b.clone()], vec![]).unwrap();
        let second = LenderPolicy::new(LenderStatus::Draft, vec![b, a], vec![]).unwrap();
        assert_eq!(serde_json::to_string(&first).unwrap(), serde_json::to_string(&second).unwrap());
    }

    #[test]
    fn ids_parse_their_own_text() {
        assert_eq!(CheckId::parse("r12"), Some(CheckId::Rule(RuleId(12))));
        assert_eq!(CheckId::parse("n3"), Some(CheckId::Note(NoteId(3))));
        for bad in ["r", "r01", "x1", "n-1", "r1a"] {
            assert_eq!(CheckId::parse(bad), None, "{bad}");
        }
        let id = LenderId::generate();
        assert_eq!(LenderId::parse(id.as_str()), Some(id));
        assert_eq!(LenderId::parse("lnd_ABCDEFGHIJ"), None);
    }

    #[test]
    fn bounds_and_sets_refuse_empty_shapes() {
        assert_eq!(Bound::new(None, None), None);
        assert_eq!(Bound::new(Some(3), Some(1)), None);
        assert!(NonEmptySet::<u8>::new([]).is_none());
        assert!(serde_json::from_str::<NonEmptySet<u8>>("[]").is_err());
        assert!(EmailAddress::parse("deals@fabrikam.example").is_some());
        for bad in ["deals", "@fabrikam.example", "deals@fabrikam", "a b@fabrikam.example", "a@b@c.example"] {
            assert!(EmailAddress::parse(bad).is_none(), "{bad}");
        }
        assert!(PortalUrl::parse("https://portal.contoso.example/submit").is_some());
        assert!(PortalUrl::parse("http://portal.contoso.example").is_none());
    }
}
