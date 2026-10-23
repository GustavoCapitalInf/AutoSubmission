use std::fmt;

use serde::{Deserialize, Deserializer, Serialize, Serializer};
use time::{Date, Month};

use crate::fields::FieldKind;

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

/// A US state, DC, a US territory or a Canadian province or territory, by its postal code.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub struct Jurisdiction(&'static str);

/// Each postal code with the full names that read as it, in upper case. The US codes come first;
/// `CANADA_FROM` is the index of the first Canadian one.
const JURISDICTIONS: [(&str, &[&str]); 69] = [
    ("AL", &["ALABAMA"]),
    ("AK", &["ALASKA"]),
    ("AZ", &["ARIZONA"]),
    ("AR", &["ARKANSAS"]),
    ("CA", &["CALIFORNIA"]),
    ("CO", &["COLORADO"]),
    ("CT", &["CONNECTICUT"]),
    ("DE", &["DELAWARE"]),
    ("FL", &["FLORIDA"]),
    ("GA", &["GEORGIA"]),
    ("HI", &["HAWAII"]),
    ("ID", &["IDAHO"]),
    ("IL", &["ILLINOIS"]),
    ("IN", &["INDIANA"]),
    ("IA", &["IOWA"]),
    ("KS", &["KANSAS"]),
    ("KY", &["KENTUCKY"]),
    ("LA", &["LOUISIANA"]),
    ("ME", &["MAINE"]),
    ("MD", &["MARYLAND"]),
    ("MA", &["MASSACHUSETTS"]),
    ("MI", &["MICHIGAN"]),
    ("MN", &["MINNESOTA"]),
    ("MS", &["MISSISSIPPI"]),
    ("MO", &["MISSOURI"]),
    ("MT", &["MONTANA"]),
    ("NE", &["NEBRASKA"]),
    ("NV", &["NEVADA"]),
    ("NH", &["NEW HAMPSHIRE"]),
    ("NJ", &["NEW JERSEY"]),
    ("NM", &["NEW MEXICO"]),
    ("NY", &["NEW YORK"]),
    ("NC", &["NORTH CAROLINA"]),
    ("ND", &["NORTH DAKOTA"]),
    ("OH", &["OHIO"]),
    ("OK", &["OKLAHOMA"]),
    ("OR", &["OREGON"]),
    ("PA", &["PENNSYLVANIA"]),
    ("RI", &["RHODE ISLAND"]),
    ("SC", &["SOUTH CAROLINA"]),
    ("SD", &["SOUTH DAKOTA"]),
    ("TN", &["TENNESSEE"]),
    ("TX", &["TEXAS"]),
    ("UT", &["UTAH"]),
    ("VT", &["VERMONT"]),
    ("VA", &["VIRGINIA"]),
    ("WA", &["WASHINGTON"]),
    ("WV", &["WEST VIRGINIA"]),
    ("WI", &["WISCONSIN"]),
    ("WY", &["WYOMING"]),
    ("DC", &["DISTRICT OF COLUMBIA"]),
    ("PR", &["PUERTO RICO"]),
    ("GU", &["GUAM"]),
    ("VI", &["U.S. VIRGIN ISLANDS", "US VIRGIN ISLANDS", "VIRGIN ISLANDS"]),
    ("AS", &["AMERICAN SAMOA"]),
    ("MP", &["NORTHERN MARIANA ISLANDS"]),
    ("AB", &["ALBERTA"]),
    ("BC", &["BRITISH COLUMBIA"]),
    ("MB", &["MANITOBA"]),
    ("NB", &["NEW BRUNSWICK"]),
    ("NL", &["NEWFOUNDLAND AND LABRADOR"]),
    ("NS", &["NOVA SCOTIA"]),
    ("NT", &["NORTHWEST TERRITORIES"]),
    ("NU", &["NUNAVUT"]),
    ("ON", &["ONTARIO"]),
    ("PE", &["PRINCE EDWARD ISLAND"]),
    ("QC", &["QUEBEC", "QUÉBEC"]),
    ("SK", &["SASKATCHEWAN"]),
    ("YT", &["YUKON"]),
];
const CANADA_FROM: usize = 56;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Country {
    UnitedStates,
    Canada,
}

impl Jurisdiction {
    /// Postal codes only, in any case: `QB` and `Texas` are refused.
    pub fn from_code(code: &str) -> Option<Jurisdiction> {
        let upper = code.trim().to_ascii_uppercase();
        JURISDICTIONS.iter().find(|(known, _)| *known == upper).map(|(known, _)| Jurisdiction(known))
    }

    /// A postal code with or without a trailing dot, or a full name, in any case.
    fn read(text: &str) -> Option<Jurisdiction> {
        let code = text.strip_suffix('.').unwrap_or(text);
        if code.len() == 2 {
            return Jurisdiction::from_code(code);
        }
        let upper = text.to_uppercase();
        JURISDICTIONS.iter().find(|(_, names)| names.contains(&upper.as_str())).map(|(known, _)| Jurisdiction(known))
    }

    pub fn code(self) -> &'static str {
        self.0
    }

    pub fn country(self) -> Country {
        let index = JURISDICTIONS.iter().position(|(known, _)| *known == self.0).expect("constructed from the list");
        if index >= CANADA_FROM { Country::Canada } else { Country::UnitedStates }
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

/// A field's text as the page or a person gives it. `words` carries each word's horizontal span on
/// the page, which only a checkbox answer reads; typed text has none.
pub struct RawText {
    text: String,
    words: Vec<Word>,
}

pub struct Word {
    pub text: String,
    pub x0: f32,
    pub x1: f32,
}

impl RawText {
    pub fn typed(text: &str) -> RawText {
        RawText { text: text.to_string(), words: Vec::new() }
    }

    /// Words in reading order, joined by one space.
    pub fn placed(words: Vec<Word>) -> RawText {
        let text = words.iter().map(|word| word.text.as_str()).collect::<Vec<_>>().join(" ");
        RawText { text, words }
    }

    pub fn as_str(&self) -> &str {
        &self.text
    }

    pub(crate) fn words(&self) -> &[Word] {
        &self.words
    }
}

/// What a reading of a date needs to know about the application.
#[derive(Clone, Copy, Default)]
pub struct ReadContext {
    /// The day the application was signed. A business or signature date after it, or an owner
    /// outside 18 to 100 years old on it, is refused; a two-digit year takes its century from it.
    pub signed_on: Option<Date>,
    /// From `business.state`. Unless it is the US, a date whose month and day could swap is refused.
    pub business_country: Option<Country>,
}

/// Why a field's text gives no value. A closed set that carries no text.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Refusal {
    Format,
    /// Not an email address, for this reason.
    Email(EmailFault),
    Ambiguous,
    OutOfRange,
    NotInList,
    MarkUnclear,
    Undecodable,
    NoSigningDate,
}

impl Refusal {
    pub fn key(self) -> &'static str {
        match self {
            Refusal::Format => "format",
            Refusal::Email(EmailFault::NoAt) => "format.no_at",
            Refusal::Email(EmailFault::SeveralAt) => "format.several_at",
            Refusal::Email(EmailFault::InnerSpace) => "format.inner_space",
            Refusal::Email(EmailFault::TrailingPunctuation) => "format.trailing_punctuation",
            Refusal::Email(EmailFault::BadLocal) => "format.bad_local",
            Refusal::Email(EmailFault::BadDomain) => "format.bad_domain",
            Refusal::Ambiguous => "ambiguous",
            Refusal::OutOfRange => "out_of_range",
            Refusal::NotInList => "not_in_list",
            Refusal::MarkUnclear => "mark_unclear",
            Refusal::Undecodable => "undecodable",
            Refusal::NoSigningDate => "no_signing_date",
        }
    }
}

/// Why a field's text is not an email address, checked in this order. It carries no text.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EmailFault {
    NoAt,
    SeveralAt,
    /// A space inside the local part or the domain.
    InnerSpace,
    /// The address ends in punctuation that is not stripped from around it.
    TrailingPunctuation,
    /// The local part is empty or holds a character an unquoted one cannot.
    BadLocal,
    /// The domain has fewer than two labels, an empty label, or a character a domain cannot hold.
    BadDomain,
}

pub enum Answer {
    Value(FieldValue),
    /// `N/A`, `NA`, `-`, or `NONE` outside a yes or no question: the merchant answered that
    /// nothing applies. It supplies no fact. `FieldId::read` reads `N/A` as no on the fields whose
    /// `NaMeans` is `No`.
    NotApplicable,
}

/// A field's value, of the variant its `FieldKind` reads. `Debug` names the variant only.
#[derive(Clone, PartialEq)]
pub enum FieldValue {
    /// Trimmed, with inner whitespace collapsed.
    Text(String),
    Email(Email),
    Phone(Phone),
    Jurisdiction(Jurisdiction),
    PostalCode(PostalCode),
    Entity(Entity),
    StatedDate(StatedDate),
    BirthDate(BirthDate),
    SignatureDate(Date),
    TaxId(TaxId),
    Ssn(PersonalTaxId),
    Money(Money),
    Percent(Percent),
    Score(Score),
    YesNo(YesNo),
}

/// The local part as written, the domain in lower case.
#[derive(Clone, PartialEq)]
pub struct Email {
    local: String,
    domain: String,
}

impl Email {
    pub fn local(&self) -> &str {
        &self.local
    }

    pub fn domain(&self) -> &str {
        &self.domain
    }
}

/// Ten NANP digits; a leading `1` or `+1` is dropped.
#[derive(Clone, PartialEq)]
pub struct Phone([u8; 10]);

#[derive(Clone, PartialEq)]
pub enum PostalCode {
    Us {
        five: [u8; 5],
        plus_four: Option<[u8; 4]>,
    },
    /// Upper case, without the space.
    Canada([u8; 6]),
}

/// The form's dropdown read as the matcher's entity kinds, except that S and C corporations stay
/// apart.
#[derive(Clone, Copy, PartialEq)]
pub enum Entity {
    Llc,
    /// Also a professional corporation.
    Corporation,
    SCorporation,
    CCorporation,
    SoleProprietorship,
    /// A general, limited or limited liability partnership.
    Partnership,
    NonProfit,
}

/// A business date at the precision the merchant wrote: `04/15/2019` is a day, `04/2019` a month.
#[derive(Clone, Copy, PartialEq)]
pub enum StatedDate {
    Day(Date),
    Month(YearMonth),
}

#[derive(Clone, Copy, PartialEq)]
pub struct BirthDate(Date);

/// The scheme is read from the digits' grouping only; nothing asserts that an authority issued it.
#[derive(Clone, PartialEq)]
pub enum TaxId {
    /// Grouped `99-9999999`.
    Ein([u8; 9]),
    /// Nine digits grouped otherwise: an EIN, an SSN or a Canadian business number.
    Unclassified([u8; 9]),
    /// `999999999AA9999`: the business number, its program and its reference number.
    CanadianBusinessNumber { number: [u8; 9], program: [u8; 2], reference: [u8; 4] },
}

#[derive(Clone, PartialEq)]
pub struct PersonalTaxId {
    digits: [u8; 9],
    scheme: IdScheme,
}

/// From the grouping only: `999-99-9999` is written as an SSN, `999 999 999` as a SIN, whatever
/// separates the groups.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum IdScheme {
    UsSsn,
    CanadianSin,
    Unclassified,
}

impl PersonalTaxId {
    pub fn scheme(&self) -> IdScheme {
        self.scheme
    }
}

/// An amount in hundredths, as printed.
#[derive(Clone, Copy, PartialEq)]
pub struct Money {
    cents: i64,
    denomination: Denomination,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Denomination {
    Explicit(Currency),
    /// A bare `$`, which does not say which dollar.
    DollarSign,
    Unmarked,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Currency {
    Usd,
    Cad,
}

impl Money {
    pub fn cents(self) -> i64 {
        self.cents
    }

    pub fn denomination(self) -> Denomination {
        self.denomination
    }
}

/// Hundredths of one percent, 0 to 10,000.
#[derive(Clone, Copy, PartialEq)]
pub struct Percent(u16);

/// 300 to 850; a stated range such as `650-700` stays a range, and `700+` runs to 850.
#[derive(Clone, Copy, PartialEq)]
pub struct Score {
    min: u16,
    max: u16,
}

#[derive(Clone, Copy, PartialEq)]
pub enum YesNo {
    Yes,
    No,
}

impl fmt::Debug for FieldValue {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "FieldValue::{:?}(..)", self.kind())
    }
}

const FICO: std::ops::RangeInclusive<u16> = 300..=850;

/// A check mark or an X, in any case.
pub(crate) fn is_mark(text: &str) -> bool {
    ["X", "✓", "✔"].contains(&text.to_uppercase().as_str())
}

impl FieldKind {
    /// The grammar of one kind, for text from the page or from a person; the same rules serve
    /// both. Every refusal is a closed `Refusal`, and none is a guess. A field's text is read
    /// through `FieldId::read`, which applies the field's own meaning of `N/A` first.
    pub fn read(self, text: &RawText, context: &ReadContext) -> Result<Answer, Refusal> {
        let normalized = text.as_str().split_whitespace().collect::<Vec<_>>().join(" ");
        if normalized.chars().any(|c| c == '\u{FFFD}' || c.is_control()) {
            return Err(Refusal::Undecodable);
        }
        if normalized.is_empty() {
            return Err(Refusal::Format);
        }
        if says_not_applicable(self, &normalized) {
            return Ok(Answer::NotApplicable);
        }
        let s = normalized.as_str();
        let value = match self {
            FieldKind::Text => FieldValue::Text(normalized.clone()),
            FieldKind::Email => FieldValue::Email(email(s)?),
            FieldKind::Phone => FieldValue::Phone(phone(s)?),
            FieldKind::Jurisdiction => FieldValue::Jurisdiction(Jurisdiction::read(s).ok_or(Refusal::NotInList)?),
            FieldKind::PostalCode => FieldValue::PostalCode(postal_code(s)?),
            FieldKind::Entity => FieldValue::Entity(entity(s)?),
            FieldKind::StatedDate => FieldValue::StatedDate(stated_date(s, context)?),
            FieldKind::BirthDate => FieldValue::BirthDate(BirthDate(birth_date(s, context)?)),
            FieldKind::SignatureDate => FieldValue::SignatureDate(signature_date(s, context)?),
            FieldKind::TaxId => FieldValue::TaxId(tax_id(s)?),
            FieldKind::Ssn => FieldValue::Ssn(personal_tax_id(s)?),
            FieldKind::Money => FieldValue::Money(money(s)?),
            FieldKind::Percent => FieldValue::Percent(percent(s)?),
            FieldKind::Score => FieldValue::Score(score(s)?),
            FieldKind::YesNo => FieldValue::YesNo(yes_no(s, &text.words)?),
        };
        Ok(Answer::Value(value))
    }
}

impl FieldValue {
    pub fn kind(&self) -> FieldKind {
        match self {
            FieldValue::Text(_) => FieldKind::Text,
            FieldValue::Email(_) => FieldKind::Email,
            FieldValue::Phone(_) => FieldKind::Phone,
            FieldValue::Jurisdiction(_) => FieldKind::Jurisdiction,
            FieldValue::PostalCode(_) => FieldKind::PostalCode,
            FieldValue::Entity(_) => FieldKind::Entity,
            FieldValue::StatedDate(_) => FieldKind::StatedDate,
            FieldValue::BirthDate(_) => FieldKind::BirthDate,
            FieldValue::SignatureDate(_) => FieldKind::SignatureDate,
            FieldValue::TaxId(_) => FieldKind::TaxId,
            FieldValue::Ssn(_) => FieldKind::Ssn,
            FieldValue::Money(_) => FieldKind::Money,
            FieldValue::Percent(_) => FieldKind::Percent,
            FieldValue::Score(_) => FieldKind::Score,
            FieldValue::YesNo(_) => FieldKind::YesNo,
        }
    }

    /// The value written one way. `FieldKind::read` of it gives the value back.
    pub fn canonical(&self) -> String {
        match self {
            FieldValue::Text(text) => text.clone(),
            FieldValue::Email(email) => format!("{}@{}", email.local, email.domain),
            FieldValue::Phone(Phone(d)) => format!("{}-{}-{}", digits(&d[..3]), digits(&d[3..6]), digits(&d[6..])),
            FieldValue::Jurisdiction(code) => code.code().to_string(),
            FieldValue::PostalCode(PostalCode::Us { five, plus_four }) => match plus_four {
                Some(four) => format!("{}-{}", digits(five), digits(four)),
                None => digits(five),
            },
            FieldValue::PostalCode(PostalCode::Canada(code)) => {
                let text: String = code.iter().map(|b| *b as char).collect();
                format!("{} {}", &text[..3], &text[3..])
            }
            FieldValue::Entity(entity) => entity_text(*entity).to_string(),
            FieldValue::StatedDate(StatedDate::Day(date)) | FieldValue::SignatureDate(date) => us_date(*date),
            FieldValue::StatedDate(StatedDate::Month(month)) => format!("{:02}/{:04}", month.month, month.year),
            FieldValue::BirthDate(BirthDate(date)) => us_date(*date),
            FieldValue::TaxId(TaxId::Ein(d)) => format!("{}-{}", digits(&d[..2]), digits(&d[2..])),
            FieldValue::TaxId(TaxId::Unclassified(d)) => digits(d),
            FieldValue::TaxId(TaxId::CanadianBusinessNumber { number, program, reference }) => {
                format!(
                    "{}{}{}",
                    digits(number),
                    program.iter().map(|b| *b as char).collect::<String>(),
                    digits(reference)
                )
            }
            FieldValue::Ssn(id) => {
                let d = &id.digits;
                match id.scheme {
                    IdScheme::UsSsn => format!("{}-{}-{}", digits(&d[..3]), digits(&d[3..5]), digits(&d[5..])),
                    IdScheme::CanadianSin => format!("{} {} {}", digits(&d[..3]), digits(&d[3..6]), digits(&d[6..])),
                    IdScheme::Unclassified => digits(d),
                }
            }
            FieldValue::Money(money) => {
                let amount = grouped_cents(money.cents);
                match money.denomination {
                    Denomination::Unmarked => amount,
                    Denomination::DollarSign => format!("${amount}"),
                    Denomination::Explicit(Currency::Usd) => format!("{amount} USD"),
                    Denomination::Explicit(Currency::Cad) => format!("{amount} CAD"),
                }
            }
            FieldValue::Percent(Percent(bp)) => format!("{}.{:02}", bp / 100, bp % 100),
            FieldValue::Score(Score { min, max }) if min == max => min.to_string(),
            FieldValue::Score(Score { min, max }) => format!("{min}-{max}"),
            FieldValue::YesNo(YesNo::Yes) => "YES".to_string(),
            FieldValue::YesNo(YesNo::No) => "NO".to_string(),
        }
    }
}

/// `N/A` or `NA`, in any case and spacing.
pub(crate) fn says_na(text: &RawText) -> bool {
    let compact: String = text.text.chars().filter(|c| !c.is_whitespace()).collect::<String>().to_uppercase();
    compact == "N/A" || compact == "NA"
}

fn says_not_applicable(kind: FieldKind, normalized: &str) -> bool {
    let compact: String = normalized.chars().filter(|c| !c.is_whitespace()).collect::<String>().to_uppercase();
    match compact.as_str() {
        "N/A" | "NA" | "-" => true,
        "NONE" => kind != FieldKind::YesNo,
        _ => false,
    }
}

fn digits(d: &[u8]) -> String {
    d.iter().map(|digit| char::from(b'0' + digit)).collect()
}

/// `9` in `shape` stands for one ASCII digit; every other character stands for itself.
fn matches_shape(text: &str, shape: &str) -> bool {
    text.len() == shape.len()
        && text.bytes().zip(shape.bytes()).all(|(t, s)| if s == b'9' { t.is_ascii_digit() } else { t == s })
}

fn digit_array<const N: usize>(text: &str) -> [u8; N] {
    let mut out = [0; N];
    for (slot, b) in out.iter_mut().zip(text.bytes().filter(u8::is_ascii_digit)) {
        *slot = b - b'0';
    }
    out
}

/// Quotes, brackets and sentence punctuation stripped from around the address, and spaces around
/// the `@` removed.
fn email(s: &str) -> Result<Email, Refusal> {
    let address = s
        .trim_start_matches(|c: char| c.is_whitespace() || "\"'<([{.,;:".contains(c))
        .trim_end_matches(|c: char| c.is_whitespace() || "\"'>)]}.,;:!?".contains(c));
    let fault = |fault| Err(Refusal::Email(fault));
    let parts: Vec<&str> = address.split('@').collect();
    let (local, domain) = match parts.as_slice() {
        [local, domain] => (local.trim_end(), domain.trim_start()),
        [_] => return fault(EmailFault::NoAt),
        _ => return fault(EmailFault::SeveralAt),
    };
    if local.contains(char::is_whitespace) || domain.contains(char::is_whitespace) {
        return fault(EmailFault::InnerSpace);
    }
    if domain.ends_with(|c: char| !c.is_alphanumeric()) && !domain.is_empty() {
        return fault(EmailFault::TrailingPunctuation);
    }
    let forbidden = |c: char| ",;<>()[]\\\"".contains(c);
    if local.is_empty() || local.chars().any(forbidden) {
        return fault(EmailFault::BadLocal);
    }
    if domain.split('.').count() < 2 || domain.split('.').any(str::is_empty) || domain.chars().any(forbidden) {
        return fault(EmailFault::BadDomain);
    }
    Ok(Email { local: local.to_string(), domain: domain.to_ascii_lowercase() })
}

/// Ten digits, or eleven with a leading `1` (also `+1`), between any spaces and `-`, `.`, `(`, `)`,
/// `/` or `=`. The area code and the exchange start at 2 or more.
fn phone(s: &str) -> Result<Phone, Refusal> {
    let (plus, rest) = match s.strip_prefix('+') {
        Some(rest) => (true, rest),
        None => (false, s),
    };
    if !rest.chars().all(|c| c.is_ascii_digit() || " -.()/=".contains(c)) {
        return Err(Refusal::Format);
    }
    let digits: Vec<u8> = rest.bytes().filter(u8::is_ascii_digit).map(|b| b - b'0').collect();
    let d: [u8; 10] = match digits.as_slice() {
        [1, ten @ ..] if ten.len() == 10 => ten.try_into().expect("ten digits"),
        ten if ten.len() == 10 && !plus => ten.try_into().expect("ten digits"),
        _ => return Err(Refusal::Format),
    };
    if d[0] < 2 || d[3] < 2 {
        return Err(Refusal::Format);
    }
    Ok(Phone(d))
}

/// The digit runs of `s` when it starts and ends with a digit and only `separators` lie between
/// them.
fn digit_groups<'a>(s: &'a str, separators: &str) -> Option<Vec<&'a str>> {
    let digit_ends = s.starts_with(|c: char| c.is_ascii_digit()) && s.ends_with(|c: char| c.is_ascii_digit());
    (digit_ends && s.chars().all(|c| c.is_ascii_digit() || separators.contains(c)))
        .then(|| s.split(|c: char| !c.is_ascii_digit()).filter(|group| !group.is_empty()).collect())
}

/// What may separate the digit groups of an SSN or a tax ID.
const ID_SEPARATORS: &str = " -.";

/// A trailing backtick, period or comma is dropped.
fn postal_code(s: &str) -> Result<PostalCode, Refusal> {
    let s = s.trim_end_matches(['`', '.', ',']).trim_end();
    if matches_shape(s, "99999") {
        return Ok(PostalCode::Us { five: digit_array(s), plus_four: None });
    }
    if matches_shape(s, "99999-9999") {
        return Ok(PostalCode::Us { five: digit_array(&s[..5]), plus_four: Some(digit_array(&s[6..])) });
    }
    let compact = s.to_ascii_uppercase().replacen(' ', "", 1);
    let bytes = compact.as_bytes();
    // Canada Post does not use D, F, I, O, Q or U, nor W or Z as the first letter.
    let letter =
        |b: u8, first: bool| b.is_ascii_uppercase() && !b"DFIOQU".contains(&b) && !(first && b"WZ".contains(&b));
    let canadian = bytes.len() == 6
        && (s.len() == 6 || s.as_bytes()[3] == b' ')
        && letter(bytes[0], true)
        && bytes[1].is_ascii_digit()
        && letter(bytes[2], false)
        && bytes[3].is_ascii_digit()
        && letter(bytes[4], false)
        && bytes[5].is_ascii_digit();
    if canadian {
        let mut code = [0; 6];
        code.copy_from_slice(bytes);
        return Ok(PostalCode::Canada(code));
    }
    Err(Refusal::Format)
}

fn entity_text(entity: Entity) -> &'static str {
    match entity {
        Entity::Llc => "LIMITED LIABILITY COMPANY",
        Entity::Corporation => "CORPORATION",
        Entity::SCorporation => "S CORPORATION (S CORP)",
        Entity::CCorporation => "C CORPORATION (C CORP)",
        Entity::SoleProprietorship => "SOLE PROPRIETORSHIP",
        Entity::Partnership => "PARTNERSHIP",
        Entity::NonProfit => "NONPROFIT",
    }
}

/// Each dropdown text, also without its parenthesis and as the abbreviation in it.
fn entity(s: &str) -> Result<Entity, Refusal> {
    match s.to_uppercase().as_str() {
        "LIMITED LIABILITY COMPANY (LLC)" | "LIMITED LIABILITY COMPANY" | "LLC" => Ok(Entity::Llc),
        "CORPORATION" | "CORP" | "INC" => Ok(Entity::Corporation),
        "PROFESSIONAL CORPORATION (PC)" | "PROFESSIONAL CORPORATION" | "PC" => Ok(Entity::Corporation),
        "S CORPORATION (S CORP)" | "S CORPORATION" | "S CORP" => Ok(Entity::SCorporation),
        "C CORPORATION (C CORP)" | "C CORPORATION" | "C CORP" => Ok(Entity::CCorporation),
        "SOLE PROPRIETORSHIP" => Ok(Entity::SoleProprietorship),
        "PARTNERSHIP"
        | "LIMITED LIABILITY PARTNERSHIP (LLP)"
        | "LIMITED LIABILITY PARTNERSHIP"
        | "LLP"
        | "GENERAL PARTNERSHIP (GP)"
        | "GENERAL PARTNERSHIP"
        | "GP"
        | "LIMITED PARTNERSHIP (LP)"
        | "LIMITED PARTNERSHIP"
        | "LP" => Ok(Entity::Partnership),
        "NONPROFIT" => Ok(Entity::NonProfit),
        "S CORPORATION (C CORP)" | "C CORPORATION (S CORP)" => Err(Refusal::Ambiguous),
        _ => Err(Refusal::NotInList),
    }
}

enum Year {
    Four(i32),
    Two(i32),
}

enum DateParts {
    /// Month, day and year written month first, where the month and the day could swap.
    Full(u8, u8, Year),
    /// Year, month and day of a date whose month is certain: written year first, or by name.
    Exact(i32, u8, u8),
    MonthYear(u8, i32),
    SixDigits([u8; 6]),
}

/// `part` as a number when it is all digits and one of `widths` long.
fn number(part: &str, widths: &[usize]) -> Option<i32> {
    (widths.contains(&part.len()) && part.bytes().all(|b| b.is_ascii_digit())).then(|| part.parse().ok())?
}

/// Numbers separated by one kind of separator, `/`, `-` or `.` with spaces around it allowed, or
/// by spaces alone; eight or six digits written together; or a date with the month's name.
fn date_parts(s: &str) -> Option<DateParts> {
    if s.chars().any(char::is_alphabetic) {
        return named_date_parts(s);
    }
    let mut separators = s.chars().filter(|c| "/-.".contains(*c));
    let separator = separators.next();
    if separators.any(|other| Some(other) != separator) {
        return None;
    }
    let parts: Vec<&str> = match separator {
        Some(separator) => s.split(separator).map(str::trim).collect(),
        None => s.split(' ').collect(),
    };
    let byte = |part: &str| u8::try_from(number(part, &[1, 2])?).ok();
    match parts.as_slice() {
        [digits] if matches_shape(digits, "99999999") => {
            let d: [u8; 8] = digit_array(digits);
            let year = i32::from(d[4]) * 1000 + i32::from(d[5]) * 100 + i32::from(d[6]) * 10 + i32::from(d[7]);
            Some(DateParts::Full(d[0] * 10 + d[1], d[2] * 10 + d[3], Year::Four(year)))
        }
        [digits] => matches_shape(digits, "999999").then(|| DateParts::SixDigits(digit_array(digits))),
        [year, month, day] if year.len() == 4 => {
            matches!(separator, Some('-' | '/')).then_some(())?;
            Some(DateParts::Exact(number(year, &[4])?, byte(month)?, byte(day)?))
        }
        [month, day, year] => {
            let year = match year.len() {
                4 => Year::Four(number(year, &[4])?),
                2 => Year::Two(number(year, &[2])?),
                _ => return None,
            };
            Some(DateParts::Full(byte(month)?, byte(day)?, year))
        }
        [month, year] => Some(DateParts::MonthYear(byte(month)?, number(year, &[4])?)),
        _ => None,
    }
}

const MONTHS: [&str; 12] = [
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
];

/// A month's name, its first three letters, or `SEPT`, in upper case.
fn month_named(token: &str) -> Option<u8> {
    let named = |name: &&str| *name == token || (token.len() == 3 && name.starts_with(token));
    let index = MONTHS.iter().position(named).or((token == "SEPT").then_some(8))?;
    u8::try_from(index + 1).ok()
}

/// `Jan 15 1980`, `January 15, 1980`, `15 Jan 1980`, and the month alone with its year:
/// `January 2019`, `Jan/2019`. Commas, `/`, `-` and an abbreviation's period separate the parts;
/// the year has four digits.
fn named_date_parts(s: &str) -> Option<DateParts> {
    let upper = s.to_uppercase();
    let mut spaced = String::with_capacity(upper.len());
    let mut after_letter = false;
    for c in upper.chars() {
        spaced.push(if matches!(c, ',' | '/' | '-') || (c == '.' && after_letter) { ' ' } else { c });
        after_letter = c.is_alphabetic();
    }
    let tokens: Vec<&str> = spaced.split_whitespace().collect();
    let day = |token: &str| u8::try_from(number(token, &[1, 2])?).ok();
    let year = |token: &str| number(token, &[4]);
    match tokens.as_slice() {
        [first, second, third] => {
            let (month, day) = match (month_named(first), month_named(second)) {
                (Some(month), None) => (month, day(second)?),
                (None, Some(month)) => (month, day(first)?),
                _ => return None,
            };
            Some(DateParts::Exact(year(third)?, month, day))
        }
        [month, year_token] => Some(DateParts::MonthYear(month_named(month)?, year(year_token)?)),
        _ => None,
    }
}

fn calendar(year: i32, month: u8, day: u8) -> Option<Date> {
    Date::from_calendar_date(year, Month::try_from(month).ok()?, day).ok()
}

/// Outside the US (or where the country is not known), `04/05/2019` could be either order.
fn swappable(month: u8, day: u8, context: &ReadContext) -> bool {
    context.business_country != Some(Country::UnitedStates) && month <= 12 && day <= 12 && month != day
}

/// A two-digit year of a business or signature date: the latest century that is not after the
/// signing day.
fn latest_century(two: i32, month: u8, day: u8, signed_on: Date) -> Option<Date> {
    calendar(2000 + two, month, day).filter(|date| *date <= signed_on).or_else(|| calendar(1900 + two, month, day))
}

fn age_on(birth: Date, on: Date) -> i32 {
    let mut age = on.year() - birth.year();
    if (on.month() as u8, on.day()) < (birth.month() as u8, birth.day()) {
        age -= 1;
    }
    age
}

fn not_after_signing(date: Date, context: &ReadContext) -> Result<Date, Refusal> {
    let signed_on = context.signed_on.ok_or(Refusal::NoSigningDate)?;
    if date.year() < 1900 || date > signed_on {
        return Err(Refusal::OutOfRange);
    }
    Ok(date)
}

/// A day read month first: a four-digit year as written, a two-digit one through `century`.
fn day_month_first(
    month: u8,
    day: u8,
    year: Year,
    context: &ReadContext,
    century: impl Fn(i32, u8, u8, Date) -> Result<Date, Refusal>,
) -> Result<Date, Refusal> {
    if swappable(month, day, context) {
        return Err(Refusal::Ambiguous);
    }
    match year {
        Year::Four(year) => calendar(year, month, day).ok_or(Refusal::Format),
        Year::Two(two) => {
            calendar(2000 + two, month, day).or_else(|| calendar(1900 + two, month, day)).ok_or(Refusal::Format)?;
            century(two, month, day, context.signed_on.ok_or(Refusal::NoSigningDate)?)
        }
    }
}

fn business_century(two: i32, month: u8, day: u8, signed_on: Date) -> Result<Date, Refusal> {
    latest_century(two, month, day, signed_on).ok_or(Refusal::Format)
}

fn stated_date(s: &str, context: &ReadContext) -> Result<StatedDate, Refusal> {
    match date_parts(s).ok_or(Refusal::Format)? {
        DateParts::Full(month, day, year) => {
            let date = day_month_first(month, day, year, context, business_century)?;
            Ok(StatedDate::Day(not_after_signing(date, context)?))
        }
        DateParts::Exact(year, month, day) => {
            Ok(StatedDate::Day(not_after_signing(calendar(year, month, day).ok_or(Refusal::Format)?, context)?))
        }
        DateParts::MonthYear(month, year) => stated_month(month, year, context),
        DateParts::SixDigits(d) => {
            let month = d[0] * 10 + d[1];
            let as_month_year = YearMonth::new(
                i32::from(d[2]) * 1000 + i32::from(d[3]) * 100 + i32::from(d[4]) * 10 + i32::from(d[5]),
                month,
            );
            let day = d[2] * 10 + d[3];
            let two = i32::from(d[4]) * 10 + i32::from(d[5]);
            let as_day = calendar(2000 + two, month, day).or_else(|| calendar(1900 + two, month, day));
            match (as_month_year, as_day) {
                (Some(_), Some(_)) => Err(Refusal::Ambiguous),
                (Some(month_year), None) => stated_month(month_year.month, month_year.year, context),
                (None, Some(_)) => {
                    let date = day_month_first(month, day, Year::Two(two), context, business_century)?;
                    Ok(StatedDate::Day(not_after_signing(date, context)?))
                }
                (None, None) => Err(Refusal::Format),
            }
        }
    }
}

fn stated_month(month: u8, year: i32, context: &ReadContext) -> Result<StatedDate, Refusal> {
    let month = YearMonth::new(year, month).ok_or(Refusal::Format)?;
    not_after_signing(month.first_day(), context)?;
    Ok(StatedDate::Month(month))
}

fn birth_date(s: &str, context: &ReadContext) -> Result<Date, Refusal> {
    let by_age = |two: i32, month: u8, day: u8, signed_on: Date| {
        let fits: Vec<Date> = [1900, 2000]
            .into_iter()
            .filter_map(|century| calendar(century + two, month, day))
            .filter(|birth| (18..=100).contains(&age_on(*birth, signed_on)))
            .collect();
        match fits.as_slice() {
            [one] => Ok(*one),
            [] => Err(Refusal::OutOfRange),
            _ => Err(Refusal::Ambiguous),
        }
    };
    let date = match date_parts(s).ok_or(Refusal::Format)? {
        DateParts::Full(month, day, year) => day_month_first(month, day, year, context, by_age)?,
        DateParts::Exact(year, month, day) => calendar(year, month, day).ok_or(Refusal::Format)?,
        DateParts::SixDigits(d) => day_month_first(
            d[0] * 10 + d[1],
            d[2] * 10 + d[3],
            Year::Two(i32::from(d[4]) * 10 + i32::from(d[5])),
            context,
            by_age,
        )?,
        DateParts::MonthYear(..) => return Err(Refusal::Format),
    };
    let signed_on = context.signed_on.ok_or(Refusal::NoSigningDate)?;
    if !(18..=100).contains(&age_on(date, signed_on)) {
        return Err(Refusal::OutOfRange);
    }
    Ok(date)
}

/// DocuSign's date-signed stamp, `M/D/YYYY`, on or before the signing day.
fn signature_date(s: &str, context: &ReadContext) -> Result<Date, Refusal> {
    let parts: Vec<&str> = s.split('/').collect();
    let [month, day, year] = parts.as_slice() else { return Err(Refusal::Format) };
    let byte = |part: &str| number(part, &[1, 2]).and_then(|n| u8::try_from(n).ok());
    let (Some(month), Some(day), Some(year)) = (byte(month), byte(day), number(year, &[4])) else {
        return Err(Refusal::Format);
    };
    not_after_signing(calendar(year, month, day).ok_or(Refusal::Format)?, context)
}

fn us_date(date: Date) -> String {
    format!("{:02}/{:02}/{:04}", date.month() as u8, date.day(), date.year())
}

/// Nine digits in any grouping, an EIN when grouped 2 and 7, or a Canadian business number: nine
/// digits, two letters and four digits, with spaces anywhere.
fn tax_id(s: &str) -> Result<TaxId, Refusal> {
    if let Some(groups) = digit_groups(s, ID_SEPARATORS) {
        let lengths: Vec<usize> = groups.iter().map(|group| group.len()).collect();
        return match lengths.as_slice() {
            _ if lengths.iter().sum::<usize>() != 9 => Err(Refusal::Format),
            [2, 7] => Ok(TaxId::Ein(digit_array(s))),
            _ => Ok(TaxId::Unclassified(digit_array(s))),
        };
    }
    let upper: String = s.chars().filter(|c| *c != ' ').collect::<String>().to_ascii_uppercase();
    let bytes = upper.as_bytes();
    if bytes.len() == 15
        && bytes[..9].iter().all(u8::is_ascii_digit)
        && bytes[9..11].iter().all(u8::is_ascii_uppercase)
        && bytes[11..].iter().all(u8::is_ascii_digit)
    {
        return Ok(TaxId::CanadianBusinessNumber {
            number: digit_array(&upper[..9]),
            program: [bytes[9], bytes[10]],
            reference: digit_array(&upper[11..]),
        });
    }
    Err(Refusal::Format)
}

/// Nine digits in any grouping. Grouped 3, 2 and 4 they are written as an SSN, grouped in threes
/// as a SIN.
fn personal_tax_id(s: &str) -> Result<PersonalTaxId, Refusal> {
    let groups = digit_groups(s, ID_SEPARATORS).ok_or(Refusal::Format)?;
    let lengths: Vec<usize> = groups.iter().map(|group| group.len()).collect();
    let scheme = match lengths.as_slice() {
        _ if lengths.iter().sum::<usize>() != 9 => return Err(Refusal::Format),
        [3, 2, 4] => IdScheme::UsSsn,
        [3, 3, 3] => IdScheme::CanadianSin,
        _ => IdScheme::Unclassified,
    };
    Ok(PersonalTaxId { digits: digit_array(s), scheme })
}

/// Digits with optional comma grouping and a fraction of 1 to `max_fraction` digits: all the
/// digits as one integer, and the fraction's length.
fn decimal(s: &str, max_fraction: usize) -> Option<(i128, u32)> {
    let (whole, fraction) = match s.split_once('.') {
        Some((whole, fraction)) => (whole, Some(fraction)),
        None => (s, None),
    };
    let groups: Vec<&str> = whole.split(',').collect();
    let grouped_ok = groups.len() == 1
        || (!groups[0].is_empty() && groups[0].len() <= 3 && groups[1..].iter().all(|group| group.len() == 3));
    let whole_digits: String = groups.concat();
    if !grouped_ok
        || whole_digits.is_empty()
        || whole_digits.len() > 15
        || !whole_digits.bytes().all(|b| b.is_ascii_digit())
    {
        return None;
    }
    let fraction = match fraction {
        None => "",
        Some(f) if (1..=max_fraction).contains(&f.len()) && f.bytes().all(|b| b.is_ascii_digit()) => f,
        Some(_) => return None,
    };
    Some((format!("{whole_digits}{fraction}").parse().ok()?, u32::try_from(fraction.len()).ok()?))
}

/// Digits with optional comma grouping and up to two decimals, as hundredths.
fn decimal_hundredths(s: &str) -> Option<i64> {
    let (digits, scale) = decimal(s, 2)?;
    i64::try_from(digits * 10i128.pow(2 - scale)).ok()
}

/// The words and letters that multiply an amount, longest first, in upper case.
const MULTIPLIERS: [(&str, i128); 5] =
    [("THOUSAND", 1_000), ("MILLION", 1_000_000), ("MIL", 1_000_000), ("K", 1_000), ("M", 1_000_000)];

fn grouped_cents(cents: i64) -> String {
    let whole = (cents / 100).to_string();
    let mut grouped = String::new();
    for (i, c) in whole.chars().enumerate() {
        if i > 0 && (whole.len() - i).is_multiple_of(3) {
            grouped.push(',');
        }
        grouped.push(c);
    }
    format!("{grouped}.{:02}", cents % 100)
}

/// An amount with an optional `USD` or `CAD` code, an optional `$`, and an optional multiplier: `k`,
/// `thousand`, `m`, `mil` or `million`, in any case. Ranges, a trailing `+` and other words are
/// refused.
fn money(s: &str) -> Result<Money, Refusal> {
    let upper = s.to_ascii_uppercase();
    let mut rest = upper.as_str();
    let mut code = None;
    for (text, currency) in [("USD", Currency::Usd), ("CAD", Currency::Cad)] {
        if let Some(after) = rest.strip_prefix(text) {
            code = Some(currency);
            rest = after.trim_start();
        } else if let Some(before) = rest.strip_suffix(text) {
            code = Some(currency);
            rest = before.trim_end();
        }
        if code.is_some() {
            break;
        }
    }
    let dollar = match rest.strip_prefix('$') {
        Some(after) => {
            rest = after.trim_start();
            true
        }
        None => false,
    };
    let multiplied = MULTIPLIERS
        .iter()
        .find_map(|(suffix, factor)| rest.strip_suffix(suffix).map(|number| (number.trim_end(), *factor)));
    let cents = match multiplied {
        None => decimal_hundredths(rest),
        Some((number, factor)) => decimal(number, 6).and_then(|(digits, scale)| {
            let hundredths = digits.checked_mul(factor * 100)?;
            let divisor = 10i128.pow(scale);
            (hundredths % divisor == 0).then(|| i64::try_from(hundredths / divisor).ok()).flatten()
        }),
    }
    .ok_or(Refusal::Format)?;
    let denomination = match (code, dollar) {
        (Some(currency), _) => Denomination::Explicit(currency),
        (None, true) => Denomination::DollarSign,
        (None, false) => Denomination::Unmarked,
    };
    Ok(Money { cents, denomination })
}

fn percent(s: &str) -> Result<Percent, Refusal> {
    let number = s.strip_suffix('%').map_or(s, str::trim_end);
    if number.contains(',') {
        return Err(Refusal::Format);
    }
    let hundredths = decimal_hundredths(number).ok_or(Refusal::Format)?;
    u16::try_from(hundredths).ok().filter(|bp| *bp <= 10_000).map(Percent).ok_or(Refusal::OutOfRange)
}

fn score(s: &str) -> Result<Score, Refusal> {
    let compact: String = s.chars().filter(|c| !c.is_whitespace()).collect();
    let three = |part: &str| matches_shape(part, "999").then(|| part.parse::<u16>().ok()).flatten();
    let (min, max) = if let Some(min) = compact.strip_suffix('+') {
        (three(min).ok_or(Refusal::Format)?, *FICO.end())
    } else if let Some((min, max)) = compact.split_once('-') {
        (three(min).ok_or(Refusal::Format)?, three(max).ok_or(Refusal::Format)?)
    } else {
        let point = three(&compact).ok_or(Refusal::Format)?;
        (point, point)
    };
    if !FICO.contains(&min) || !FICO.contains(&max) {
        return Err(Refusal::OutOfRange);
    }
    if min > max {
        return Err(Refusal::Format);
    }
    Ok(Score { min, max })
}

/// A word answer, or a checkbox row of the words YES and NO with one mark, read when the mark's
/// center lies under half as far from one word's center as from the other's.
fn yes_no(s: &str, words: &[Word]) -> Result<YesNo, Refusal> {
    let tokens: Vec<String> = s.split(' ').map(str::to_uppercase).collect();
    if let [token] = tokens.as_slice() {
        return match token.as_str() {
            "YES" | "Y" => Ok(YesNo::Yes),
            "NO" | "N" | "NONE" | "0" => Ok(YesNo::No),
            _ => Err(Refusal::Format),
        };
    }
    if !tokens.iter().all(|token| token == "YES" || token == "NO" || is_mark(token)) {
        return Err(Refusal::Format);
    }
    let center = |wanted: &dyn Fn(&str) -> bool| -> Vec<f32> {
        words.iter().filter(|word| wanted(&word.text.to_uppercase())).map(|word| (word.x0 + word.x1) / 2.0).collect()
    };
    let (marks, yes, no) = (center(&|t| is_mark(t)), center(&|t| t == "YES"), center(&|t| t == "NO"));
    let ([mark], [yes], [no]) = (marks.as_slice(), yes.as_slice(), no.as_slice()) else {
        return Err(Refusal::MarkUnclear);
    };
    let (to_yes, to_no) = ((mark - yes).abs(), (mark - no).abs());
    if to_yes < to_no / 2.0 {
        Ok(YesNo::Yes)
    } else if to_no < to_yes / 2.0 {
        Ok(YesNo::No)
    } else {
        Err(Refusal::MarkUnclear)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use time::macros::date;

    const SIGNED: ReadContext =
        ReadContext { signed_on: Some(date!(2026 - 10 - 20)), business_country: Some(Country::UnitedStates) };

    fn read_in(kind: FieldKind, text: &str, context: &ReadContext) -> Result<Option<String>, Refusal> {
        kind.read(&RawText::typed(text), context).map(|answer| match answer {
            Answer::Value(value) => {
                assert_eq!(value.kind(), kind);
                Some(value.canonical())
            }
            Answer::NotApplicable => None,
        })
    }

    fn read(kind: FieldKind, text: &str) -> Result<Option<String>, Refusal> {
        read_in(kind, text, &SIGNED)
    }

    fn accepts(kind: FieldKind, cases: &[(&str, &str)]) {
        for (text, canonical) in cases {
            assert_eq!(read(kind, text), Ok(Some(canonical.to_string())), "{kind:?} {text}");
        }
    }

    fn refuses(kind: FieldKind, cases: &[(&str, Refusal)]) {
        for (text, why) in cases {
            assert_eq!(read(kind, text), Err(*why), "{kind:?} {text}");
        }
    }

    #[test]
    fn text_is_trimmed_and_collapsed() {
        accepts(FieldKind::Text, &[("  CONTOSO   LLC ", "CONTOSO LLC"), ("NORTHWIND / SAMPLE", "NORTHWIND / SAMPLE")]);
        refuses(FieldKind::Text, &[("CONTOSO \u{FFFD}", Refusal::Undecodable), ("   ", Refusal::Format)]);
    }

    #[test]
    fn not_applicable_supplies_no_value() {
        for kind in [FieldKind::Text, FieldKind::Money, FieldKind::Phone, FieldKind::Score, FieldKind::YesNo] {
            for text in ["N/A", "n/a", "NA", "N / A", "-"] {
                assert_eq!(read(kind, text), Ok(None), "{kind:?} {text}");
            }
        }
        assert_eq!(read(FieldKind::Money, "NONE"), Ok(None), "NONE is not an amount of zero");
        assert_eq!(read(FieldKind::Text, "none"), Ok(None));
    }

    #[test]
    fn yes_or_no_answers() {
        accepts(
            FieldKind::YesNo,
            &[("YES", "YES"), ("y", "YES"), ("No", "NO"), ("N", "NO"), ("NONE", "NO"), ("0", "NO")],
        );
        refuses(FieldKind::YesNo, &[("TRUE", Refusal::Format), ("NO WAY", Refusal::Format), ("1", Refusal::Format)]);
    }

    fn row(words: &[(&str, f32)]) -> RawText {
        RawText::placed(
            words
                .iter()
                .map(|(text, x0)| Word { text: text.to_string(), x0: *x0, x1: x0 + 6.0 * text.len() as f32 })
                .collect(),
        )
    }

    fn checkbox(words: &[(&str, f32)]) -> Result<Option<String>, Refusal> {
        FieldKind::YesNo.read(&row(words), &SIGNED).map(|answer| match answer {
            Answer::Value(value) => Some(value.canonical()),
            Answer::NotApplicable => None,
        })
    }

    #[test]
    fn a_checkbox_row_reads_the_option_under_the_mark() {
        assert_eq!(checkbox(&[("YES", 300.0), ("NO", 340.0), ("X", 302.0)]), Ok(Some("YES".to_string())));
        assert_eq!(checkbox(&[("YES", 300.0), ("NO", 340.0), ("X", 342.0)]), Ok(Some("NO".to_string())));
        assert_eq!(checkbox(&[("YES", 300.0), ("NO", 340.0), ("✓", 339.0)]), Ok(Some("NO".to_string())));
        assert_eq!(checkbox(&[("YES", 300.0), ("NO", 340.0), ("X", 322.0)]), Err(Refusal::MarkUnclear), "between");
        assert_eq!(checkbox(&[("YES", 300.0), ("NO", 340.0)]), Err(Refusal::MarkUnclear), "no mark");
        assert_eq!(
            checkbox(&[("YES", 300.0), ("NO", 340.0), ("X", 302.0), ("X", 342.0)]),
            Err(Refusal::MarkUnclear),
            "two marks"
        );
        assert_eq!(read(FieldKind::YesNo, "YES NO X"), Err(Refusal::MarkUnclear), "typed text has no positions");
    }

    #[test]
    fn phones() {
        accepts(
            FieldKind::Phone,
            &[
                ("5125550100", "512-555-0100"),
                ("512-555-0100", "512-555-0100"),
                ("512 555 0100", "512-555-0100"),
                ("(512) 555-0100", "512-555-0100"),
                ("(512)555-0100", "512-555-0100"),
                ("512.555.0100", "512-555-0100"),
                ("15125550100", "512-555-0100"),
                ("1-512-555-0100", "512-555-0100"),
                ("+1 512 555 0100", "512-555-0100"),
                ("+1 (512) 555-0100", "512-555-0100"),
                ("512/555/0100", "512-555-0100"),
                ("512-555=0100", "512-555-0100"),
                ("512 555-0100", "512-555-0100"),
                ("(512)-555-0100", "512-555-0100"),
                ("512-5550-100", "512-555-0100"),
                ("1 (512) 555.0100", "512-555-0100"),
            ],
        );
        refuses(
            FieldKind::Phone,
            &[
                ("512-555-010", Refusal::Format),
                ("512-555-0100 x12", Refusal::Format),
                ("512-555-01000", Refusal::Format),
                ("112-555-0100", Refusal::Format),
                ("512-155-0100", Refusal::Format),
                ("+512 555 0100", Refusal::Format),
                ("512_555_0100", Refusal::Format),
            ],
        );
    }

    #[test]
    fn jurisdictions_take_postal_codes_and_full_names() {
        accepts(
            FieldKind::Jurisdiction,
            &[
                ("TX", "TX"),
                ("tx", "TX"),
                ("ON", "ON"),
                ("TX.", "TX"),
                ("Tx.", "TX"),
                ("Texas", "TX"),
                ("TEXAS", "TX"),
                ("new york", "NY"),
                ("District of Columbia", "DC"),
                ("Puerto Rico", "PR"),
                ("Québec", "QC"),
                ("QUEBEC", "QC"),
                ("Newfoundland and Labrador", "NL"),
            ],
        );
        refuses(
            FieldKind::Jurisdiction,
            &[
                ("QB", Refusal::NotInList),
                ("Tex", Refusal::NotInList),
                ("T X", Refusal::NotInList),
                ("TX..", Refusal::NotInList),
                ("Washington DC", Refusal::NotInList),
                ("New York City", Refusal::NotInList),
            ],
        );
        assert_eq!(Jurisdiction::from_code("Texas"), None, "a stored code is a code");
        assert_eq!(Jurisdiction::from_code("PR").map(Jurisdiction::country), Some(Country::UnitedStates));
        assert_eq!(Jurisdiction::from_code("AB").map(Jurisdiction::country), Some(Country::Canada));
        assert_eq!(Jurisdiction::from_code("YT").map(Jurisdiction::country), Some(Country::Canada));
    }

    #[test]
    fn postal_codes() {
        accepts(
            FieldKind::PostalCode,
            &[
                ("78701", "78701"),
                ("02134", "02134"),
                ("78701-1234", "78701-1234"),
                ("K1A 0B1", "K1A 0B1"),
                ("k1a0b1", "K1A 0B1"),
                ("K1A 0B1`", "K1A 0B1"),
                ("78701.", "78701"),
                ("78701-1234,", "78701-1234"),
            ],
        );
        refuses(
            FieldKind::PostalCode,
            &[
                ("7870", Refusal::Format),
                ("787011234", Refusal::Format),
                ("D1A 0B1", Refusal::Format),
                ("W1A 0B1", Refusal::Format),
                ("K1A-0B1", Refusal::Format),
                ("78701;", Refusal::Format),
                (".", Refusal::Format),
            ],
        );
    }

    #[test]
    fn entities() {
        accepts(
            FieldKind::Entity,
            &[
                ("LIMITED LIABILITY COMPANY (LLC)", "LIMITED LIABILITY COMPANY"),
                ("LIMITED LIABILITY COMPANY", "LIMITED LIABILITY COMPANY"),
                ("llc", "LIMITED LIABILITY COMPANY"),
                ("S CORPORATION (S CORP)", "S CORPORATION (S CORP)"),
                ("S CORP", "S CORPORATION (S CORP)"),
                ("C CORPORATION (C CORP)", "C CORPORATION (C CORP)"),
                ("CORPORATION", "CORPORATION"),
                ("INC", "CORPORATION"),
                ("PROFESSIONAL CORPORATION (PC)", "CORPORATION"),
                ("SOLE PROPRIETORSHIP", "SOLE PROPRIETORSHIP"),
                ("NONPROFIT", "NONPROFIT"),
                ("LIMITED LIABILITY PARTNERSHIP (LLP)", "PARTNERSHIP"),
                ("GENERAL PARTNERSHIP (GP)", "PARTNERSHIP"),
                ("Limited Partnership (LP)", "PARTNERSHIP"),
            ],
        );
        refuses(
            FieldKind::Entity,
            &[
                ("S CORPORATION (C CORP)", Refusal::Ambiguous),
                ("C CORPORATION (S CORP)", Refusal::Ambiguous),
                ("LLC.", Refusal::NotInList),
                ("TRUST", Refusal::NotInList),
                ("NON PROFIT CORPORATION", Refusal::NotInList),
            ],
        );
    }

    #[test]
    fn emails_keep_the_local_part_and_lower_the_domain() {
        accepts(
            FieldKind::Email,
            &[
                ("Owner@Example.COM", "Owner@example.com"),
                ("a.b+c@mail.example.com", "a.b+c@mail.example.com"),
                ("<owner@example.com>", "owner@example.com"),
                ("(owner@example.com)", "owner@example.com"),
                ("\"owner@example.com\",", "owner@example.com"),
                ("owner@example.com.", "owner@example.com"),
                ("owner @ example.com", "owner@example.com"),
                ("owner@ example.com", "owner@example.com"),
            ],
        );
        let fault = |fault| Refusal::Email(fault);
        refuses(
            FieldKind::Email,
            &[
                ("owner example.com", fault(EmailFault::NoAt)),
                ("a@b@example.com", fault(EmailFault::SeveralAt)),
                ("owner name@example.com", fault(EmailFault::InnerSpace)),
                ("owner@example .com", fault(EmailFault::InnerSpace)),
                ("owner@example.com/", fault(EmailFault::TrailingPunctuation)),
                ("owner@example-", fault(EmailFault::TrailingPunctuation)),
                ("@example.com", fault(EmailFault::BadLocal)),
                ("own,er@example.com", fault(EmailFault::BadLocal)),
                ("owner@example", fault(EmailFault::BadDomain)),
                ("owner@example..com", fault(EmailFault::BadDomain)),
                ("owner@", fault(EmailFault::BadDomain)),
            ],
        );
        assert_eq!(Refusal::Email(EmailFault::InnerSpace).key(), "format.inner_space");
    }

    #[test]
    fn business_dates_read_month_first() {
        accepts(
            FieldKind::StatedDate,
            &[
                ("04/15/2019", "04/15/2019"),
                ("4/15/2019", "04/15/2019"),
                ("04-15-2019", "04/15/2019"),
                ("04152019", "04/15/2019"),
                ("04/2019", "04/2019"),
                ("4/2019", "04/2019"),
                ("04-2019", "04/2019"),
                ("05/06/2019", "05/06/2019"),
                ("04/15/19", "04/15/2019"),
                ("04/15/27", "04/15/1927"),
                ("04.15.2019", "04/15/2019"),
                ("04 15 2019", "04/15/2019"),
                ("04 / 15 / 2019", "04/15/2019"),
                ("04/15 /2019", "04/15/2019"),
                ("04 2019", "04/2019"),
                ("2019-04-15", "04/15/2019"),
                ("2019/04/15", "04/15/2019"),
                ("Apr 15 2019", "04/15/2019"),
                ("APR 15, 2019", "04/15/2019"),
                ("15 apr 2019", "04/15/2019"),
                ("April 15, 2019", "04/15/2019"),
                ("Sept. 3, 2019", "09/03/2019"),
                ("January 2019", "01/2019"),
                ("Jan 2019", "01/2019"),
                ("Jan/2019", "01/2019"),
            ],
        );
        refuses(
            FieldKind::StatedDate,
            &[
                ("042019", Refusal::Ambiguous),
                ("13/05/2019", Refusal::Format),
                ("02/30/2019", Refusal::Format),
                ("2019", Refusal::Format),
                ("04/19", Refusal::Format),
                ("04/15-2019", Refusal::Format),
                ("04/15 2019", Refusal::Format),
                ("2019.04.15", Refusal::Format),
                ("2019-04", Refusal::Format),
                ("2019-15-04", Refusal::Format),
                ("Apr 15th 2019", Refusal::Format),
                ("Apr 19", Refusal::Format),
                ("Janu 2019", Refusal::Format),
                ("Q2 2019", Refusal::Format),
                ("Apr 31 2019", Refusal::Format),
                ("Nov 2026", Refusal::OutOfRange),
                ("11/2026", Refusal::OutOfRange),
                ("10/21/2026", Refusal::OutOfRange),
                ("01/01/1899", Refusal::OutOfRange),
            ],
        );
        assert_eq!(read(FieldKind::StatedDate, "10/20/2026"), Ok(Some("10/20/2026".to_string())), "the signing day");
        assert_eq!(read(FieldKind::StatedDate, "10/2026"), Ok(Some("10/2026".to_string())), "the signing month");
    }

    #[test]
    fn six_digit_dates_read_only_when_one_reading_fits() {
        assert_eq!(read(FieldKind::StatedDate, "121999"), Err(Refusal::Ambiguous), "12/1999 or 12/19/99");
        assert_eq!(read(FieldKind::StatedDate, "013219"), Err(Refusal::OutOfRange), "only 01/3219, after signing");
        assert_eq!(read(FieldKind::StatedDate, "120156"), Ok(Some("12/01/1956".to_string())), "12/0156 is no month");
        assert_eq!(read(FieldKind::StatedDate, "131999"), Err(Refusal::Format));
    }

    #[test]
    fn a_canadian_or_unknown_business_refuses_dates_whose_month_and_day_could_swap() {
        let canada = ReadContext { business_country: Some(Country::Canada), ..SIGNED };
        let unknown = ReadContext { business_country: None, ..SIGNED };
        for context in [&canada, &unknown] {
            assert_eq!(read_in(FieldKind::StatedDate, "05/06/2019", context), Err(Refusal::Ambiguous));
            assert_eq!(read_in(FieldKind::BirthDate, "05/06/1980", context), Err(Refusal::Ambiguous));
            assert_eq!(read_in(FieldKind::StatedDate, "05/05/2019", context), Ok(Some("05/05/2019".to_string())));
            assert_eq!(read_in(FieldKind::StatedDate, "05/16/2019", context), Ok(Some("05/16/2019".to_string())));
            assert_eq!(read_in(FieldKind::StatedDate, "05/2019", context), Ok(Some("05/2019".to_string())));
            assert_eq!(read_in(FieldKind::StatedDate, "2019-05-06", context), Ok(Some("05/06/2019".to_string())));
            assert_eq!(read_in(FieldKind::BirthDate, "6 May 1980", context), Ok(Some("05/06/1980".to_string())));
        }
    }

    #[test]
    fn birth_dates_need_an_owner_aged_18_to_100_on_the_signing_day() {
        accepts(
            FieldKind::BirthDate,
            &[
                ("04/15/1980", "04/15/1980"),
                ("4/15/1980", "04/15/1980"),
                ("04-15-1980", "04/15/1980"),
                ("04151980", "04/15/1980"),
                ("04/15/80", "04/15/1980"),
                ("041580", "04/15/1980"),
                ("04/15/05", "04/15/2005"),
                ("10/20/2008", "10/20/2008"),
                ("04.15.1980", "04/15/1980"),
                ("04 / 15 / 1980", "04/15/1980"),
                ("1980-04-15", "04/15/1980"),
                ("1980/04/15", "04/15/1980"),
                ("Apr 15 1980", "04/15/1980"),
                ("Apr 15, 1980", "04/15/1980"),
                ("15 Apr 1980", "04/15/1980"),
                ("April 15, 1980", "04/15/1980"),
                ("APR 5 1980", "04/05/1980"),
            ],
        );
        refuses(
            FieldKind::BirthDate,
            &[
                ("04/1980", Refusal::Format),
                ("April 1980", Refusal::Format),
                ("Apr 15 80", Refusal::Format),
                ("Apr 15 2015", Refusal::OutOfRange),
                ("10/21/2008", Refusal::OutOfRange),
                ("10/19/1925", Refusal::OutOfRange),
                ("04/15/2015", Refusal::OutOfRange),
                ("04/15/10", Refusal::OutOfRange),
                ("02/30/1980", Refusal::Format),
            ],
        );
    }

    #[test]
    fn dates_without_a_signing_day_are_refused() {
        let unsigned = ReadContext { signed_on: None, ..SIGNED };
        for (kind, text) in [
            (FieldKind::StatedDate, "04/15/2019"),
            (FieldKind::StatedDate, "04/2019"),
            (FieldKind::StatedDate, "04/15/19"),
            (FieldKind::BirthDate, "04/15/1980"),
            (FieldKind::SignatureDate, "10/20/2026"),
        ] {
            assert_eq!(read_in(kind, text, &unsigned), Err(Refusal::NoSigningDate), "{kind:?} {text}");
        }
    }

    #[test]
    fn signature_dates_are_docusign_stamps_on_or_before_signing() {
        accepts(
            FieldKind::SignatureDate,
            &[("10/20/2026", "10/20/2026"), ("9/9/2026", "09/09/2026"), ("10/9/2026", "10/09/2026")],
        );
        refuses(
            FieldKind::SignatureDate,
            &[
                ("10/21/2026", Refusal::OutOfRange),
                ("10/2026", Refusal::Format),
                ("10/19/26", Refusal::Format),
                ("10202026", Refusal::Format),
                ("2026-10-20", Refusal::Format),
                ("Oct 20, 2026", Refusal::Format),
                ("10/20/2026 _____", Refusal::Format),
            ],
        );
        let canada = ReadContext { business_country: Some(Country::Canada), ..SIGNED };
        assert_eq!(read_in(FieldKind::SignatureDate, "5/6/2026", &canada), Ok(Some("05/06/2026".to_string())));
    }

    #[test]
    fn tax_ids_keep_their_scheme_and_leading_zeros() {
        accepts(
            FieldKind::TaxId,
            &[
                ("01-2345678", "01-2345678"),
                ("012345678", "012345678"),
                ("123456789RT0001", "123456789RT0001"),
                ("123456789rt0001", "123456789RT0001"),
                ("01 2345678", "01-2345678"),
                ("123-45-6789", "123456789"),
                ("12-345-6789", "123456789"),
                ("12345 6789", "123456789"),
                ("12345 6789 RT 0001", "123456789RT0001"),
                ("123456789 RT0001", "123456789RT0001"),
            ],
        );
        refuses(
            FieldKind::TaxId,
            &[
                ("12-345678", Refusal::Format),
                ("12-34567890", Refusal::Format),
                ("123456789RT001", Refusal::Format),
                ("12/3456789", Refusal::Format),
                ("-123456789", Refusal::Format),
            ],
        );
    }

    #[test]
    fn personal_ids_keep_the_grouping_they_were_written_with() {
        accepts(
            FieldKind::Ssn,
            &[
                ("900-12-3456", "900-12-3456"),
                ("900123456", "900123456"),
                ("900 123 456", "900 123 456"),
                ("900 12 3456", "900-12-3456"),
                ("900.12.3456", "900-12-3456"),
                ("900 - 12 - 3456", "900-12-3456"),
                ("900-123-456", "900 123 456"),
                ("900-123456", "900123456"),
            ],
        );
        refuses(
            FieldKind::Ssn,
            &[
                ("90012345", Refusal::Format),
                ("9001234567", Refusal::Format),
                ("900-12-345", Refusal::Format),
                ("900_12_3456", Refusal::Format),
            ],
        );
        let FieldValue::Ssn(id) = value(FieldKind::Ssn, "900 123 456") else { unreachable!() };
        assert_eq!(id.scheme(), IdScheme::CanadianSin);
    }

    fn value(kind: FieldKind, text: &str) -> FieldValue {
        match kind.read(&RawText::typed(text), &SIGNED) {
            Ok(Answer::Value(value)) => value,
            _ => panic!("{kind:?} did not read"),
        }
    }

    #[test]
    fn money_keeps_cents_and_denomination_as_printed() {
        accepts(
            FieldKind::Money,
            &[
                ("50000", "50,000.00"),
                ("50,000", "50,000.00"),
                ("1,250,000", "1,250,000.00"),
                ("250,000.99", "250,000.99"),
                ("9", "9.00"),
                ("0", "0.00"),
                ("1000.5", "1,000.50"),
                ("$50,000", "$50,000.00"),
                ("$ 50000", "$50,000.00"),
                ("USD 50,000", "50,000.00 USD"),
                ("50,000 CAD", "50,000.00 CAD"),
                ("CAD $50,000", "50,000.00 CAD"),
                ("500k", "500,000.00"),
                ("500 K", "500,000.00"),
                ("$1.2M", "$1,200,000.00"),
                ("1.2 million", "1,200,000.00"),
                ("1.25 Million", "1,250,000.00"),
                ("2 mil", "2,000,000.00"),
                ("1.5MIL", "1,500,000.00"),
                ("250 thousand", "250,000.00"),
                ("1,500k", "1,500,000.00"),
                ("$ 50K", "$50,000.00"),
                ("USD 1.2M", "1,200,000.00 USD"),
            ],
        );
        refuses(
            FieldKind::Money,
            &[
                ("500k+", Refusal::Format),
                ("999,999+", Refusal::Format),
                ("500k-1M", Refusal::Format),
                ("10k to 20k", Refusal::Format),
                ("1.2MM", Refusal::Format),
                ("1.2 billion", Refusal::Format),
                ("1.2345678M", Refusal::Format),
                ("500 000", Refusal::Format),
                ("K", Refusal::Format),
                ("-500", Refusal::Format),
                ("10,000-20,000", Refusal::Format),
                ("50,00", Refusal::Format),
                ("5000,000", Refusal::Format),
                ("50.001", Refusal::Format),
                (".50", Refusal::Format),
                ("50000 $", Refusal::Format),
                ("1234567890123456", Refusal::Format),
            ],
        );
        let FieldValue::Money(money) = value(FieldKind::Money, "$50,000") else { unreachable!() };
        assert_eq!((money.cents(), money.denomination()), (5_000_000, Denomination::DollarSign));
    }

    #[test]
    fn percents_are_hundredths_up_to_100() {
        accepts(
            FieldKind::Percent,
            &[
                ("100", "100.00"),
                ("100.00", "100.00"),
                ("50.00", "50.00"),
                ("51.5", "51.50"),
                ("0", "0.00"),
                ("100%", "100.00"),
                ("50 %", "50.00"),
            ],
        );
        refuses(
            FieldKind::Percent,
            &[
                ("100.01", Refusal::OutOfRange),
                ("150", Refusal::OutOfRange),
                ("50.555", Refusal::Format),
                ("1,000", Refusal::Format),
            ],
        );
    }

    #[test]
    fn scores_are_fico_points_or_ranges() {
        accepts(
            FieldKind::Score,
            &[("700", "700"), ("650-700", "650-700"), ("650 - 700", "650-700"), ("700+", "700-850")],
        );
        refuses(
            FieldKind::Score,
            &[
                ("900", Refusal::OutOfRange),
                ("250-700", Refusal::OutOfRange),
                ("700-650", Refusal::Format),
                ("7OO", Refusal::Format),
                ("70", Refusal::Format),
            ],
        );
    }

    #[test]
    fn every_canonical_text_reads_back_as_the_same_value() {
        let samples: &[(FieldKind, &[&str])] = &[
            (FieldKind::Text, &["CONTOSO LLC"]),
            (FieldKind::Email, &["Owner@example.com"]),
            (FieldKind::Phone, &["(512) 555-0100"]),
            (FieldKind::Jurisdiction, &["on", "Texas"]),
            (FieldKind::PostalCode, &["78701-1234", "k1a0b1"]),
            (FieldKind::Entity, &["S CORP", "INC", "LLC", "C CORP", "SOLE PROPRIETORSHIP", "LLP", "NONPROFIT"]),
            (FieldKind::StatedDate, &["4/15/19", "04/2019", "120156", "Jan 2019", "2019-04-15"]),
            (FieldKind::BirthDate, &["041580", "April 15, 1980"]),
            (FieldKind::SignatureDate, &["9/9/2026"]),
            (FieldKind::TaxId, &["01-2345678", "012345678", "123456789rt0001", "123-45-6789"]),
            (FieldKind::Ssn, &["900-12-3456", "900123456", "900 123 456", "900.123.456"]),
            (FieldKind::Money, &["50000", "$ 50000", "USD 1000.5", "CAD 7", "$1.2M", "250 thousand"]),
            (FieldKind::Percent, &["51.5%"]),
            (FieldKind::Score, &["700+", "650 - 700", "700"]),
            (FieldKind::YesNo, &["y", "NONE"]),
        ];
        for (kind, texts) in samples {
            for text in *texts {
                let first = value(*kind, text);
                assert_eq!(value(*kind, &first.canonical()), first, "{kind:?} {text}");
            }
        }
    }

    #[test]
    fn debug_names_the_kind_and_never_the_value() {
        let id = value(FieldKind::Ssn, "900-12-3456");
        assert_eq!(format!("{id:?}"), "FieldValue::Ssn(..)");
        assert!(!format!("{:?}", value(FieldKind::Text, "CONTOSO LLC")).contains("CONTOSO"));
    }

    #[test]
    fn year_month_parses_only_the_canonical_form() {
        assert_eq!(YearMonth::parse("2026-09"), YearMonth::new(2026, 9));
        for bad in ["2026-9", "2026-13", "2026-00", "26-09", "2026/09", " 2026-09", "2026-09-01"] {
            assert_eq!(YearMonth::parse(bad), None, "{bad}");
        }
    }
}
