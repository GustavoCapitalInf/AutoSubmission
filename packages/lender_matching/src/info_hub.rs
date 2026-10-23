//! The rerunnable seed from the Info Hub export's "Lenders Module" sheet. Every non-empty cell ends
//! in a rule, a note, the profile, or a stated "no rule needed"; a cell it cannot read becomes a
//! `Condition` note quoting the cell, so the lender stays at review until an admin reads it.

use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::io::Cursor;
use std::path::Path;

use calamine::{Data, Reader, open_workbook_auto_from_rs};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use time::OffsetDateTime;

use crate::criteria::{
    Bound, Contact, LenderId, LenderPolicy, LenderProfile, LenderRecord, LenderStatus, Membership, NonEmptySet, Note,
    NoteId, NoteKind, Predicate, Product, Rule, RuleId, Terms,
};
use crate::facts::application::{EntityKind, Industries, IndustryId, Jurisdiction};
use crate::facts::{FlagFact, NumFact};
use crate::store::{Author, Revision, Saved, Store, StoreError, WriteTx, now};

pub const SHEET: &str = "Lenders Module";

/// Every column of the sheet. `read_sheet` refuses a header row that misses one, repeats one or
/// adds another, so no column is skipped unseen.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub enum Column {
    LenderName,
    MinMonthlyRev,
    CreditScore,
    MinDepNo,
    NsfPerMonth,
    Positions,
    Tib,
    RestrictedIndustries,
    RestrictedStates,
    Exclusivity,
    AdditionalInfo,
    ClawbackPeriod,
    AcceptDefaultHistory,
    AccountManager,
    ContactPhone,
    RecordId,
}

impl Column {
    pub const ALL: [Column; 16] = [
        Column::LenderName,
        Column::MinMonthlyRev,
        Column::CreditScore,
        Column::MinDepNo,
        Column::NsfPerMonth,
        Column::Positions,
        Column::Tib,
        Column::RestrictedIndustries,
        Column::RestrictedStates,
        Column::Exclusivity,
        Column::AdditionalInfo,
        Column::ClawbackPeriod,
        Column::AcceptDefaultHistory,
        Column::AccountManager,
        Column::ContactPhone,
        Column::RecordId,
    ];

    pub fn header(self) -> &'static str {
        match self {
            Column::LenderName => "Lender Name",
            Column::MinMonthlyRev => "Minimum Monthly Rev",
            Column::CreditScore => "Credit Score",
            Column::MinDepNo => "Min Dep No.",
            Column::NsfPerMonth => "NSF Per Month",
            Column::Positions => "Positions",
            Column::Tib => "TIB",
            Column::RestrictedIndustries => "Restricted Industries",
            Column::RestrictedStates => "Restricted States",
            Column::Exclusivity => "Exclusivity",
            Column::AdditionalInfo => "Additional Info",
            Column::ClawbackPeriod => "Clawback Period",
            Column::AcceptDefaultHistory => "Accept Default History?",
            Column::AccountManager => "Account Manager",
            Column::ContactPhone => "Contact Phone",
            Column::RecordId => "Record Id",
        }
    }

    fn from_header(text: &str) -> Option<Column> {
        let wanted = collapse(text).to_lowercase();
        Column::ALL.into_iter().find(|column| column.header().to_lowercase() == wanted)
    }

    fn index(self) -> usize {
        self as usize
    }

    pub fn is_criterion(self) -> bool {
        matches!(
            self,
            Column::MinMonthlyRev
                | Column::CreditScore
                | Column::MinDepNo
                | Column::NsfPerMonth
                | Column::Positions
                | Column::Tib
                | Column::RestrictedIndustries
                | Column::RestrictedStates
                | Column::AdditionalInfo
                | Column::AcceptDefaultHistory
        )
    }
}

impl TryFrom<String> for Column {
    type Error = String;
    fn try_from(text: String) -> Result<Self, Self::Error> {
        Column::from_header(&text).ok_or_else(|| format!("unknown column {text}"))
    }
}

impl From<Column> for String {
    fn from(column: Column) -> String {
        column.header().to_string()
    }
}

fn collapse(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

pub struct Sheet {
    pub sha256: [u8; 32],
    pub rows: Vec<SheetRow>,
}

pub struct SheetRow {
    /// The spreadsheet's own 1-based row number.
    pub line: u32,
    cells: [Option<String>; 16],
}

impl SheetRow {
    pub fn cell(&self, column: Column) -> Option<&str> {
        self.cells[column.index()].as_deref()
    }
}

#[derive(Debug, thiserror::Error)]
pub enum SheetError {
    #[error("cannot read the file: {0}")]
    Io(#[from] std::io::Error),
    #[error("not a readable .xlsx or .xls workbook")]
    Unreadable,
    #[error("the workbook has no \"{SHEET}\" sheet")]
    NoLendersModuleSheet,
    #[error("the header row lacks the column \"{}\"", .0.header())]
    MissingColumn(Column),
    #[error("the header row repeats the column \"{}\"", .0.header())]
    DuplicateColumn(Column),
    #[error("the header row has an unknown column \"{0}\"")]
    UnknownColumn(String),
}

pub fn read_sheet(path: &Path) -> Result<Sheet, SheetError> {
    read_sheet_bytes(std::fs::read(path)?)
}

pub fn read_sheet_bytes(bytes: Vec<u8>) -> Result<Sheet, SheetError> {
    let sha256: [u8; 32] = Sha256::digest(&bytes).into();
    let mut workbook = open_workbook_auto_from_rs(Cursor::new(bytes)).map_err(|_| SheetError::Unreadable)?;
    if !workbook.sheet_names().iter().any(|name| name == SHEET) {
        return Err(SheetError::NoLendersModuleSheet);
    }
    let range = workbook.worksheet_range(SHEET).map_err(|_| SheetError::Unreadable)?;
    let first_line = range.start().map_or(1, |(row, _)| row + 1);
    let mut rows = range.rows();
    let headers: Vec<Option<String>> = rows.next().map(|row| row.iter().map(cell_text).collect()).unwrap_or_default();
    let mut positions: [Option<usize>; 16] = [None; 16];
    let mut unlabelled = Vec::new();
    for (index, header) in headers.iter().enumerate() {
        let Some(header) = header else {
            unlabelled.push(index);
            continue;
        };
        let column = Column::from_header(header).ok_or_else(|| SheetError::UnknownColumn(header.clone()))?;
        if positions[column.index()].replace(index).is_some() {
            return Err(SheetError::DuplicateColumn(column));
        }
    }
    if let Some(missing) = Column::ALL.into_iter().find(|column| positions[column.index()].is_none()) {
        return Err(SheetError::MissingColumn(missing));
    }
    let mut parsed = Vec::new();
    for (offset, row) in rows.enumerate() {
        let line = first_line + 1 + u32::try_from(offset).expect("a sheet has fewer than 2^32 rows");
        let text: Vec<Option<String>> = row.iter().map(cell_text).collect();
        if let Some(index) = unlabelled.iter().find(|index| text.get(**index).is_some_and(Option::is_some)) {
            return Err(SheetError::UnknownColumn(format!("column {} without a header", index + 1)));
        }
        let cells: [Option<String>; 16] =
            std::array::from_fn(|column| positions[column].and_then(|index| text.get(index).cloned().flatten()));
        if cells.iter().any(Option::is_some) {
            parsed.push(SheetRow { line, cells });
        }
    }
    Ok(Sheet { sha256, rows: parsed })
}

fn cell_text(cell: &Data) -> Option<String> {
    let text = match cell {
        Data::Empty => return None,
        Data::String(text) => text.trim().to_string(),
        Data::Int(value) => value.to_string(),
        Data::Float(value) if value.fract() == 0.0 && value.abs() < 1e15 => format!("{}", *value as i64),
        Data::Float(value) => value.to_string(),
        Data::Bool(value) => if *value { "TRUE" } else { "FALSE" }.to_string(),
        Data::DateTime(value) => format!("a date cell (Excel serial {value})"),
        Data::DateTimeIso(text) | Data::DurationIso(text) => text.clone(),
        Data::Error(error) => format!("an error cell ({error:?})"),
    };
    (!text.is_empty()).then_some(text)
}

fn import_key(row: &SheetRow) -> Option<String> {
    match (row.cell(Column::RecordId), row.cell(Column::LenderName)) {
        (Some(record), _) => Some(format!("record:{record}")),
        (None, Some(name)) => Some(format!("name:{}", collapse(name).to_uppercase())),
        (None, None) => None,
    }
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct CellReport {
    pub column: Column,
    pub raw: Option<String>,
    pub outcome: CellOutcome,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum CellOutcome {
    Empty,
    Rules {
        ids: Vec<RuleId>,
        reading: Reading,
    },
    Note {
        id: NoteId,
        note: NoteKind,
    },
    Profile,
    NoRule {
        why: String,
    },
    /// Part of the cell became rules; the rest is a `Condition` note.
    PartlyRead {
        ids: Vec<RuleId>,
        unread: NoteId,
    },
    Unread {
        note: NoteId,
    },
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", content = "how", rename_all = "snake_case")]
pub enum Reading {
    Exact,
    /// Read through a stated mapping.
    Mapped(String),
    /// Read through a default the owner has not confirmed.
    Default(String),
}

struct Builder<'a> {
    industries: &'a Industries,
    rules: Vec<Rule>,
    notes: Vec<Note>,
    new_industries: BTreeSet<String>,
}

impl Builder<'_> {
    fn rule(&mut self, when: Vec<Predicate>, require: Predicate, source: &str) -> RuleId {
        let id = RuleId(u32::try_from(self.rules.len()).expect("few rules") + 1);
        self.rules.push(Rule { id, when, require, source: Some(source.to_string()) });
        id
    }

    fn note(&mut self, kind: NoteKind, when: Vec<Predicate>, text: String) -> NoteId {
        let id = NoteId(u32::try_from(self.notes.len()).expect("few notes") + 1);
        self.notes.push(Note { id, kind, when, text });
        id
    }

    fn unread(&mut self, column: Column, raw: &str) -> CellOutcome {
        let note = self.note(NoteKind::Condition, vec![], format!("{}: {raw}", column.header()));
        CellOutcome::Unread { note }
    }

    fn one_rule(&mut self, require: Predicate, raw: &str, reading: Reading) -> CellOutcome {
        let id = self.rule(vec![], require, raw);
        CellOutcome::Rules { ids: vec![id], reading }
    }

    fn industry(&mut self, label: &str) -> IndustryId {
        match self.industries.by_label(label) {
            Some(id) => id,
            None => {
                self.new_industries.insert(label.to_string());
                IndustryId::proposed(self.industries.slug_for(label))
            }
        }
    }
}

fn num(fact: NumFact, bound: Bound) -> Predicate {
    Predicate::Num { fact, bound }
}

fn dollars(raw: &str) -> Option<i64> {
    count(&raw.trim().trim_start_matches('$').replace(',', ""))
}

fn count(raw: &str) -> Option<i64> {
    let raw = raw.trim();
    (!raw.is_empty() && raw.bytes().all(|b| b.is_ascii_digit())).then(|| raw.parse().ok()).flatten()
}

/// `number * factor` when that is a whole number; `number` is decimal digits.
fn scaled(number: &str, factor: i64) -> Option<i64> {
    let (whole, fraction) = number.split_once('.').unwrap_or((number, ""));
    let digits = format!("{whole}{fraction}");
    if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let scale = 10i64.checked_pow(u32::try_from(fraction.len()).ok()?)?;
    let product = digits.parse::<i64>().ok()?.checked_mul(factor)?;
    (product % scale == 0).then_some(product / scale)
}

/// Months, and whether the cell named its unit.
fn tib_months(raw: &str) -> Option<(i64, bool)> {
    let lower = raw.trim().to_lowercase();
    let split = lower.find(|c: char| !(c.is_ascii_digit() || c == '.')).unwrap_or(lower.len());
    let (number, unit) = lower.split_at(split);
    let (factor, named) = match unit.trim() {
        "" => (12, false),
        "year" | "years" | "yr" | "yrs" => (12, true),
        "month" | "months" | "mo" | "mos" => (1, true),
        _ => return None,
    };
    Some((scaled(number, factor)?, named))
}

enum PositionsCell {
    Range(i64, Option<i64>),
    OpenRange(i64, i64),
}

fn positions(raw: &str) -> Option<PositionsCell> {
    let text: String = raw.chars().filter(|c| !c.is_whitespace()).collect();
    if let Some(rest) = text.strip_suffix('+') {
        return match rest.split_once('-') {
            Some((low, high)) => {
                let (low, high) = (count(low)?, count(high)?);
                (low <= high).then_some(PositionsCell::OpenRange(low, high))
            }
            None => Some(PositionsCell::Range(count(rest)?, None)),
        };
    }
    match text.split_once('-') {
        Some((low, high)) => {
            let (low, high) = (count(low)?, count(high)?);
            (low <= high).then_some(PositionsCell::Range(low, Some(high)))
        }
        None => count(&text)
            .filter(|position| *position >= 1)
            .map(|position| PositionsCell::Range(position, Some(position))),
    }
}

fn single_url(text: &str) -> bool {
    let text = text.trim();
    (text.starts_with("https://") || text.starts_with("http://")) && !text.chars().any(char::is_whitespace)
}

fn values(raw: &str) -> Vec<&str> {
    raw.split(';').map(str::trim).filter(|value| !value.is_empty()).collect()
}

struct RowReading {
    record: LenderRecord,
    cells: Vec<CellReport>,
    new_industries: BTreeSet<String>,
}

fn read_row(row: &SheetRow, industries: &Industries) -> RowReading {
    let mut builder = Builder { industries, rules: Vec::new(), notes: Vec::new(), new_industries: BTreeSet::new() };
    let mut terms = Terms::default();
    let mut cells = Vec::new();
    for column in Column::ALL {
        let raw = row.cell(column);
        let outcome = match raw {
            None => CellOutcome::Empty,
            Some(raw) => read_cell(&mut builder, &mut terms, column, raw),
        };
        cells.push(CellReport { column, raw: raw.map(str::to_string), outcome });
    }
    let contact =
        (row.cell(Column::AccountManager).is_some() || row.cell(Column::ContactPhone).is_some()).then(|| Contact {
            role: "Account manager".to_string(),
            name: row.cell(Column::AccountManager).map(str::to_string),
            phone: row.cell(Column::ContactPhone).map(str::to_string),
            email: None,
        });
    let profile = LenderProfile {
        name: row.cell(Column::LenderName).map(collapse).unwrap_or_default(),
        legacy_record_id: row.cell(Column::RecordId).map(str::to_string),
        bucket: None,
        products: BTreeSet::from([Product::Mca]),
        submission: None,
        contacts: contact.into_iter().collect(),
        terms,
    };
    let policy = LenderPolicy::new(LenderStatus::Draft, builder.rules, builder.notes)
        .expect("ids are assigned in sequence and a draft needs no rules");
    RowReading { record: LenderRecord { profile, policy }, cells, new_industries: builder.new_industries }
}

fn read_cell(builder: &mut Builder, terms: &mut Terms, column: Column, raw: &str) -> CellOutcome {
    let exact = || Reading::Exact;
    match column {
        Column::LenderName | Column::RecordId | Column::AccountManager | Column::ContactPhone => CellOutcome::Profile,
        Column::Exclusivity => {
            terms.exclusivity = Some(raw.to_string());
            CellOutcome::Profile
        }
        Column::ClawbackPeriod => {
            terms.clawback = Some(raw.to_string());
            CellOutcome::Profile
        }
        Column::MinMonthlyRev => match dollars(raw).and_then(|value| value.checked_mul(100)) {
            Some(cents) => {
                builder.one_rule(num(NumFact::MonthlyTrueRevenueCents, Bound::at_least(cents)), raw, exact())
            }
            None => builder.unread(column, raw),
        },
        Column::CreditScore => match count(raw).filter(|score| (300..=900).contains(score)) {
            Some(score) => builder.one_rule(num(NumFact::CreditScore, Bound::at_least(score)), raw, exact()),
            None => builder.unread(column, raw),
        },
        Column::MinDepNo => match count(raw) {
            Some(deposits) => builder.one_rule(
                num(NumFact::WorstMonthDeposits, Bound::at_least(deposits)),
                raw,
                Reading::Mapped("the worst statement month, read like NSF Per Month".to_string()),
            ),
            None => builder.unread(column, raw),
        },
        Column::NsfPerMonth => match count(raw) {
            Some(days) => builder.one_rule(num(NumFact::WorstMonthNegativeDays, Bound::at_most(days)), raw, exact()),
            None => builder.unread(column, raw),
        },
        Column::Positions => match positions(raw) {
            Some(PositionsCell::Range(low, high)) => {
                let bound = Bound::new(Some(low), high).expect("low <= high");
                builder.one_rule(num(NumFact::NewPosition, bound), raw, exact())
            }
            Some(PositionsCell::OpenRange(low, high)) => {
                let low = low.max(1);
                let id = builder.rule(vec![], num(NumFact::NewPosition, Bound::at_least(low)), raw);
                builder.note(
                    NoteKind::Condition,
                    vec![num(NumFact::NewPosition, Bound::at_least(high + 1))],
                    format!("Positions {raw}: positions above {high} are case by case"),
                );
                CellOutcome::Rules {
                    ids: vec![id],
                    reading: Reading::Default(format!("positions above {high} hold the deal at review")),
                }
            }
            None => builder.unread(column, raw),
        },
        Column::Tib => match tib_months(raw) {
            Some((months, named)) => {
                let reading = if named { exact() } else { Reading::Mapped("a bare number is years".to_string()) };
                builder.one_rule(num(NumFact::TimeInBusinessMonths, Bound::at_least(months)), raw, reading)
            }
            None => builder.unread(column, raw),
        },
        Column::RestrictedIndustries => {
            let is = |value: &str, form: &str| value.eq_ignore_ascii_case(form);
            let all = values(raw);
            let sole = all.iter().any(|value| is(value, "Sole Proprietorship"));
            let home = all.iter().any(|value| is(value, "Home-Based Businesses"));
            let labels =
                all.iter().filter(|value| !is(value, "Sole Proprietorship") && !is(value, "Home-Based Businesses"));
            let industries: Vec<IndustryId> = labels.map(|label| builder.industry(label)).collect();
            let mut ids = Vec::new();
            if let Some(set) = NonEmptySet::new(industries) {
                ids.push(builder.rule(vec![], Predicate::Industry(Membership::NotIn(set)), raw));
            }
            if sole {
                let set = NonEmptySet::new([EntityKind::SoleProprietorship]).expect("one entity");
                ids.push(builder.rule(vec![], Predicate::Entity(Membership::NotIn(set)), raw));
            }
            if home {
                ids.push(builder.rule(vec![], Predicate::Flag { fact: FlagFact::HomeBased, is: false }, raw));
            }
            if ids.is_empty() {
                return builder.unread(column, raw);
            }
            let reading = if sole || home {
                Reading::Mapped("Sole Proprietorship and Home-Based Businesses are business forms".to_string())
            } else {
                exact()
            };
            CellOutcome::Rules { ids, reading }
        }
        Column::RestrictedStates => {
            let mut known = Vec::new();
            let mut unknown = Vec::new();
            let mut mapped = false;
            for value in values(raw) {
                let code = if value.eq_ignore_ascii_case("QB") {
                    mapped = true;
                    "QC"
                } else {
                    value
                };
                match Jurisdiction::from_code(code) {
                    Some(state) => known.push(state),
                    None => unknown.push(value),
                }
            }
            let rule =
                NonEmptySet::new(known).map(|set| builder.rule(vec![], Predicate::State(Membership::NotIn(set)), raw));
            let reading = if mapped { Reading::Mapped("QB is Quebec, QC".to_string()) } else { exact() };
            match (rule, unknown.is_empty()) {
                (Some(id), true) => CellOutcome::Rules { ids: vec![id], reading },
                (Some(id), false) => {
                    let text = format!("Restricted States: {} not read as a state code", unknown.join(", "));
                    let unread = builder.note(NoteKind::Condition, vec![], text);
                    CellOutcome::PartlyRead { ids: vec![id], unread }
                }
                (None, _) => builder.unread(column, raw),
            }
        }
        Column::AcceptDefaultHistory => match raw.to_ascii_lowercase().as_str() {
            "no" => builder.one_rule(Predicate::Flag { fact: FlagFact::DefaultHistory, is: false }, raw, exact()),
            "yes" => CellOutcome::NoRule { why: "accepts default history".to_string() },
            _ => builder.unread(column, raw),
        },
        Column::AdditionalInfo => {
            let kind = if single_url(raw) { NoteKind::Info } else { NoteKind::Condition };
            let id = builder.note(kind, vec![], format!("Additional Info: {raw}"));
            CellOutcome::Note { id, note: kind }
        }
    }
}

pub enum RowAction {
    /// A new lender, status Draft.
    Create(LenderRecord),
    Update {
        lender: LenderId,
        base: u32,
        record: LenderRecord,
    },
    Unchanged(LenderId),
    KeptAdminEdits {
        lender: LenderId,
        head: u32,
        differs: bool,
    },
}

pub struct RowPlan {
    pub line: u32,
    pub key: String,
    pub name: String,
    pub action: RowAction,
    pub no_criteria: bool,
    pub cells: Vec<CellReport>,
}

pub struct ImportPlan {
    /// A non-empty list refuses `Apply`.
    pub blockers: Vec<String>,
    pub rows: Vec<RowPlan>,
    /// Lenders the import created that the sheet no longer lists. Reported and kept.
    pub not_in_sheet: Vec<(LenderId, String)>,
    pub new_industries: Vec<String>,
}

/// Pure: the same sheet, heads and industries give the same plan and the same rule and note ids.
/// `heads` holds the head revision of every lender the import created, by import key.
pub fn plan(sheet: &Sheet, heads: &BTreeMap<String, Revision>, industries: &Industries) -> ImportPlan {
    let mut blockers = Vec::new();
    let mut lines: BTreeMap<String, u32> = BTreeMap::new();
    let mut rows = Vec::new();
    let mut new_industries = BTreeSet::new();
    for row in &sheet.rows {
        let reading = read_row(row, industries);
        new_industries.extend(reading.new_industries);
        let (Some(key), Some(_)) = (import_key(row), row.cell(Column::LenderName)) else {
            blockers.push(format!("line {}: the row has no Lender Name", row.line));
            continue;
        };
        if let Some(first) = lines.insert(key.clone(), row.line) {
            blockers.push(format!("lines {first} and {}: both rows have the key {key}", row.line));
            continue;
        }
        let record = reading.record;
        let action = match heads.get(&key) {
            None => RowAction::Create(record.clone()),
            Some(head) if head.author.is_import() => {
                if head.record.to_stored() == record.to_stored() {
                    RowAction::Unchanged(head.lender.clone())
                } else {
                    RowAction::Update { lender: head.lender.clone(), base: head.number, record: record.clone() }
                }
            }
            Some(head) => {
                let differs = match record.policy.with_status(head.record.policy.status()) {
                    Ok(policy) => LenderRecord { profile: record.profile.clone(), policy } != head.record,
                    Err(_) => true,
                };
                RowAction::KeptAdminEdits { lender: head.lender.clone(), head: head.number, differs }
            }
        };
        rows.push(RowPlan {
            line: row.line,
            key,
            name: record.profile.name.clone(),
            action,
            no_criteria: record.policy.rules().is_empty(),
            cells: reading.cells,
        });
    }
    let not_in_sheet = heads
        .iter()
        .filter(|(key, _)| !lines.contains_key(*key))
        .map(|(_, head)| (head.lender.clone(), head.record.profile.name.clone()))
        .collect();
    ImportPlan { blockers, rows, not_in_sheet, new_industries: new_industries.into_iter().collect() }
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct ImportReport {
    #[serde(with = "time::serde::rfc3339")]
    pub run_at: OffsetDateTime,
    pub source_sha256: String,
    pub applied: bool,
    pub blockers: Vec<String>,
    pub rows: Vec<RowReport>,
    pub not_in_sheet: Vec<MissingLender>,
    pub new_industries: Vec<String>,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct RowReport {
    pub line: u32,
    pub key: String,
    pub name: String,
    /// None for a lender a dry run would create.
    pub lender: Option<LenderId>,
    pub action: ActionReport,
    pub no_criteria: bool,
    pub cells: Vec<CellReport>,
}

impl RowReport {
    pub fn uses_default_reading(&self) -> bool {
        self.cells.iter().any(|cell| matches!(cell.outcome, CellOutcome::Rules { reading: Reading::Default(_), .. }))
    }
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ActionReport {
    Create,
    /// `revision` is None in a dry run.
    Update {
        revision: Option<u32>,
    },
    Unchanged,
    KeptAdminEdits {
        head: u32,
        differs: bool,
    },
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct MissingLender {
    pub lender: LenderId,
    pub name: String,
}

impl fmt::Display for ActionReport {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ActionReport::Create => f.write_str("create (draft)"),
            ActionReport::Update { revision: Some(revision) } => write!(f, "update to revision {revision}"),
            ActionReport::Update { revision: None } => f.write_str("update"),
            ActionReport::Unchanged => f.write_str("unchanged"),
            ActionReport::KeptAdminEdits { head, differs: true } => {
                write!(f, "kept admin edits at revision {head}; the sheet now differs")
            }
            ActionReport::KeptAdminEdits { head, differs: false } => write!(f, "kept admin edits at revision {head}"),
        }
    }
}

impl ImportReport {
    fn of(plan: &ImportPlan, sheet: &Sheet) -> ImportReport {
        let rows = plan
            .rows
            .iter()
            .map(|row| {
                let (lender, action) = match &row.action {
                    RowAction::Create(_) => (None, ActionReport::Create),
                    RowAction::Update { lender, .. } => (Some(lender.clone()), ActionReport::Update { revision: None }),
                    RowAction::Unchanged(lender) => (Some(lender.clone()), ActionReport::Unchanged),
                    RowAction::KeptAdminEdits { lender, head, differs } => {
                        (Some(lender.clone()), ActionReport::KeptAdminEdits { head: *head, differs: *differs })
                    }
                };
                RowReport {
                    line: row.line,
                    key: row.key.clone(),
                    name: row.name.clone(),
                    lender,
                    action,
                    no_criteria: row.no_criteria,
                    cells: row.cells.clone(),
                }
            })
            .collect();
        ImportReport {
            run_at: now(),
            source_sha256: sheet.sha256.iter().map(|byte| format!("{byte:02x}")).collect(),
            applied: false,
            blockers: plan.blockers.clone(),
            rows,
            not_in_sheet: plan
                .not_in_sheet
                .iter()
                .map(|(lender, name)| MissingLender { lender: lender.clone(), name: name.clone() })
                .collect(),
            new_industries: plan.new_industries.clone(),
        }
    }

    pub fn count(&self, kind: fn(&ActionReport) -> bool) -> usize {
        self.rows.iter().filter(|row| kind(&row.action)).count()
    }

    pub fn lines(&self) -> Vec<String> {
        let mut lines = vec![
            format!(
                "{} rows: {} create, {} update, {} unchanged, {} kept admin edits; {} not in the sheet; {} new industries",
                self.rows.len(),
                self.count(|a| matches!(a, ActionReport::Create)),
                self.count(|a| matches!(a, ActionReport::Update { .. })),
                self.count(|a| matches!(a, ActionReport::Unchanged)),
                self.count(|a| matches!(a, ActionReport::KeptAdminEdits { .. })),
                self.not_in_sheet.len(),
                self.new_industries.len(),
            ),
            if self.applied { "Applied.".to_string() } else { "Dry run: nothing was written.".to_string() },
        ];
        lines.extend(self.blockers.iter().map(|blocker| format!("BLOCKER {blocker}")));
        for row in &self.rows {
            let criteria = if row.no_criteria { " [no criteria]" } else { "" };
            lines.push(format!("line {} {}: {}{criteria}", row.line, row.name, row.action));
            for cell in &row.cells {
                let flag = match &cell.outcome {
                    CellOutcome::Rules { reading: Reading::Mapped(how), .. } => Some(format!("mapped: {how}")),
                    CellOutcome::Rules { reading: Reading::Default(how), .. } => Some(format!("default: {how}")),
                    CellOutcome::Note { note: NoteKind::Condition, .. } => Some("condition note".to_string()),
                    CellOutcome::Note { note: NoteKind::Info, .. } => Some("info note".to_string()),
                    CellOutcome::PartlyRead { .. } => Some("partly read; the rest is a condition note".to_string()),
                    CellOutcome::Unread { .. } => Some("not read; a condition note quotes it".to_string()),
                    _ => None,
                };
                if let Some(flag) = flag {
                    lines.push(format!("    {}: {flag}", cell.column.header()));
                }
            }
        }
        for missing in &self.not_in_sheet {
            lines.push(format!("not in the sheet (kept): {} {}", missing.lender, missing.name));
        }
        for industry in &self.new_industries {
            lines.push(format!("new industry: {industry}"));
        }
        lines
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ImportMode {
    DryRun,
    Apply,
}

#[derive(Debug, thiserror::Error)]
pub enum ImportError {
    #[error("the sheet has blockers; nothing was written")]
    Blocked(Box<ImportReport>),
    #[error(transparent)]
    Store(#[from] StoreError),
}

fn import_heads(tx: &WriteTx) -> Result<BTreeMap<String, Revision>, StoreError> {
    let mut heads = BTreeMap::new();
    for (key, lender) in tx.import_keys()? {
        let head = tx.head(&lender)?.ok_or_else(|| StoreError::Corrupt(format!("{lender} has no revision")))?;
        heads.insert(key, head);
    }
    Ok(heads)
}

/// Plans and applies inside one `BEGIN IMMEDIATE` transaction. `DryRun` always rolls back.
/// `Apply` writes every row and the run's report, then commits, so a crash leaves nothing
/// half-done; blockers refuse it with nothing written.
pub fn run(store: &Store, sheet: &Sheet, mode: ImportMode) -> Result<ImportReport, ImportError> {
    let work = |tx: &WriteTx| -> Result<ImportReport, ImportError> {
        let first = plan(sheet, &import_heads(tx)?, &tx.industries()?);
        for label in &first.new_industries {
            tx.add_industry(label)?;
        }
        let plan = plan(sheet, &import_heads(tx)?, &tx.industries()?);
        let mut report = ImportReport::of(&plan, sheet);
        report.new_industries = first.new_industries;
        if mode == ImportMode::DryRun {
            return Ok(report);
        }
        if !plan.blockers.is_empty() {
            return Err(ImportError::Blocked(Box::new(report)));
        }
        let run_id = tx.insert_import_run(&sheet.sha256, &report_json(&report))?;
        let author = Author::Import(run_id);
        for (row, line) in plan.rows.iter().zip(report.rows.iter_mut()) {
            match &row.action {
                RowAction::Create(record) => {
                    line.lender = Some(tx.create_lender(record, &author, Some(&row.key))?.lender);
                }
                RowAction::Update { lender, base, record } => {
                    let saved =
                        tx.save_revision(lender, *base, record, &author, Some("Info Hub import")).map_err(|error| {
                            StoreError::Corrupt(format!("{lender} changed inside the import transaction: {error}"))
                        })?;
                    let revision = match saved {
                        Saved::New(revision) | Saved::Unchanged(revision) => revision.number,
                    };
                    line.action = ActionReport::Update { revision: Some(revision) };
                }
                RowAction::Unchanged(_) | RowAction::KeptAdminEdits { .. } => {}
            }
        }
        report.applied = true;
        tx.set_import_report(run_id, &report_json(&report))?;
        Ok(report)
    };
    match mode {
        ImportMode::DryRun => store.rehearse(work),
        ImportMode::Apply => store.write(work),
    }
}

fn report_json(report: &ImportReport) -> String {
    serde_json::to_string(report).expect("an import report serializes")
}

pub fn parse_report(json: &str) -> Result<ImportReport, StoreError> {
    serde_json::from_str(json).map_err(|error| StoreError::Corrupt(format!("an import report: {error}")))
}

#[cfg(test)]
pub(crate) mod testing {
    use super::*;
    use rust_xlsxwriter::Workbook;

    pub enum Value {
        Text(&'static str),
        Number(f64),
    }

    pub fn workbook(rows: &[Vec<(Column, Value)>]) -> Vec<u8> {
        workbook_with_headers(&Column::ALL.map(Column::header), rows)
    }

    pub fn workbook_with_headers(headers: &[&str], rows: &[Vec<(Column, Value)>]) -> Vec<u8> {
        let mut book = Workbook::new();
        let sheet = book.add_worksheet();
        sheet.set_name(SHEET).unwrap();
        for (index, header) in headers.iter().enumerate() {
            sheet.write_string(0, u16::try_from(index).unwrap(), *header).unwrap();
        }
        for (row, cells) in rows.iter().enumerate() {
            let row = u32::try_from(row).unwrap() + 1;
            for (column, value) in cells {
                let index = headers.iter().position(|header| *header == column.header()).unwrap();
                let index = u16::try_from(index).unwrap();
                match value {
                    Value::Text(text) => sheet.write_string(row, index, *text).unwrap(),
                    Value::Number(number) => sheet.write_number(row, index, *number).unwrap(),
                };
            }
        }
        book.save_to_buffer().unwrap()
    }

    pub fn lender(name: &'static str, record: &'static str, cells: Vec<(Column, Value)>) -> Vec<(Column, Value)> {
        let mut row = vec![(Column::LenderName, Value::Text(name)), (Column::RecordId, Value::Text(record))];
        row.extend(cells);
        row
    }
}

#[cfg(test)]
mod tests {
    use super::testing::*;
    use super::*;
    use crate::criteria::describe;
    use crate::criteria::eval::{VerdictStatus, evaluate};
    use crate::facts::analysis::testing::three_clean_months;
    use crate::facts::testing::{AS_OF, application, everything_confirmed};
    use crate::facts::{DealInput, assemble};
    use crate::store::testing::editor;
    use Value::{Number, Text};

    fn sheet(rows: &[Vec<(Column, Value)>]) -> Sheet {
        read_sheet_bytes(workbook(rows)).unwrap()
    }

    fn one_row(column: Column, value: Value) -> (Vec<String>, CellOutcome) {
        let industries = crate::facts::application::test_industries();
        let sheet = sheet(&[lender("CONTOSO CAPITAL", "REC-1", vec![(column, value)])]);
        let plan = plan(&sheet, &BTreeMap::new(), &industries);
        let RowAction::Create(record) = &plan.rows[0].action else { panic!("a new lender") };
        let mut texts: Vec<String> =
            record.policy.rules().iter().map(|rule| describe::rule(rule, &industries)).collect();
        texts.extend(record.policy.notes().iter().map(|note| {
            let scope = describe::note_scope(note, &industries).map(|scope| format!(" [{scope}]")).unwrap_or_default();
            format!("{} note{scope}: {}", note.kind.key(), note.text)
        }));
        let outcome = plan.rows[0].cells.iter().find(|cell| cell.column == column).unwrap().outcome.clone();
        (texts, outcome)
    }

    #[test]
    fn every_value_shape_in_the_sheet_reads_as_intended() {
        let cases: Vec<(Column, Value, &[&str])> = vec![
            (Column::MinMonthlyRev, Number(10000.0), &["Monthly True revenue at least $10,000.00"]),
            (Column::MinMonthlyRev, Number(20833.0), &["Monthly True revenue at least $20,833.00"]),
            (Column::MinMonthlyRev, Text("$25,000"), &["Monthly True revenue at least $25,000.00"]),
            (Column::CreditScore, Number(450.0), &["Credit score at least 450"]),
            (Column::CreditScore, Number(680.0), &["Credit score at least 680"]),
            (Column::MinDepNo, Number(2.0), &["Deposits in the worst statement month at least 2"]),
            (Column::NsfPerMonth, Number(3.0), &["Negative days in the worst statement month at most 3"]),
            (Column::Positions, Number(1.0), &["New position is 1"]),
            (Column::Positions, Text("1-3"), &["New position from 1 to 3"]),
            (Column::Positions, Text("1-5"), &["New position from 1 to 5"]),
            (Column::Positions, Text("2+"), &["New position at least 2"]),
            (Column::Positions, Text("2-8"), &["New position from 2 to 8"]),
            (
                Column::Positions,
                Text("0-5+"),
                &[
                    "New position at least 1",
                    "condition note [When New position at least 6]: Positions 0-5+: positions above 5 are case by case",
                ],
            ),
            (
                Column::Positions,
                Text("1-5+"),
                &[
                    "New position at least 1",
                    "condition note [When New position at least 6]: Positions 1-5+: positions above 5 are case by case",
                ],
            ),
            (Column::Tib, Text("1 Year"), &["Months in business at least 12"]),
            (Column::Tib, Text("1.5 Years"), &["Months in business at least 18"]),
            (Column::Tib, Text("6 Months"), &["Months in business at least 6"]),
            (Column::Tib, Text("3 Months"), &["Months in business at least 3"]),
            (Column::Tib, Text("1 Month"), &["Months in business at least 1"]),
            (Column::Tib, Number(3.0), &["Months in business at least 36"]),
            (Column::Tib, Number(2.0), &["Months in business at least 24"]),
            (Column::Tib, Number(1.5), &["Months in business at least 18"]),
            (Column::Tib, Text("1.3 Years"), &["condition note: TIB: 1.3 Years"]),
            (
                Column::RestrictedIndustries,
                Text("Cannabis;Transportation / Trucking"),
                &["Industry is not one of Cannabis, Transportation / Trucking"],
            ),
            (
                Column::RestrictedIndustries,
                Text("Cannabis; Sole Proprietorship; Home-Based Businesses"),
                &[
                    "Industry is not one of Cannabis",
                    "Entity is not one of sole proprietorship",
                    "No home-based business",
                ],
            ),
            (Column::RestrictedStates, Text("PR"), &["State is not one of PR"]),
            (Column::RestrictedStates, Text("PR;QB"), &["State is not one of PR, QC"]),
            (
                Column::RestrictedStates,
                Text("CA;NY;XX"),
                &["State is not one of CA, NY", "condition note: Restricted States: XX not read as a state code"],
            ),
            (Column::AcceptDefaultHistory, Text("No"), &["No default history"]),
            (Column::AcceptDefaultHistory, Text("Yes"), &[]),
            (Column::AcceptDefaultHistory, Text("Maybe"), &["condition note: Accept Default History?: Maybe"]),
            (
                Column::AdditionalInfo,
                Text("Trucking: $100k monthly revenue, 3 years TIB"),
                &["condition note: Additional Info: Trucking: $100k monthly revenue, 3 years TIB"],
            ),
            (
                Column::AdditionalInfo,
                Text("https://partners.contoso.example/apply"),
                &["info note: Additional Info: https://partners.contoso.example/apply"],
            ),
            (Column::Exclusivity, Text("14 Days from offer"), &[]),
            (Column::ClawbackPeriod, Text("30 Days"), &[]),
            (Column::AccountManager, Text("SAMPLE REP"), &[]),
            (Column::ContactPhone, Text("555-0100"), &[]),
            (Column::Positions, Text("first and second"), &["condition note: Positions: first and second"]),
        ];
        for (column, value, expected) in cases {
            let shown = match &value {
                Text(text) => text.to_string(),
                Number(number) => number.to_string(),
            };
            let (texts, outcome) = one_row(column, value);
            assert_eq!(texts, expected, "{} = {shown}: {outcome:?}", column.header());
        }
    }

    #[test]
    fn cell_outcomes_name_their_kind() {
        assert!(matches!(one_row(Column::Tib, Number(2.0)).1, CellOutcome::Rules { reading: Reading::Mapped(_), .. }));
        assert!(matches!(one_row(Column::Tib, Text("2 Years")).1, CellOutcome::Rules { reading: Reading::Exact, .. }));
        assert!(matches!(
            one_row(Column::Positions, Text("0-5+")).1,
            CellOutcome::Rules { reading: Reading::Default(_), .. }
        ));
        assert!(matches!(one_row(Column::RestrictedStates, Text("CA;XX")).1, CellOutcome::PartlyRead { .. }));
        assert!(matches!(one_row(Column::AcceptDefaultHistory, Text("Yes")).1, CellOutcome::NoRule { .. }));
        assert!(matches!(one_row(Column::Exclusivity, Text("1st to contracts signed")).1, CellOutcome::Profile));
    }

    #[test]
    fn a_cell_is_reported_empty_exactly_when_it_is_empty() {
        let full: Vec<(Column, Value)> = Column::ALL
            .into_iter()
            .map(|column| (column, if column == Column::LenderName { Text("NORTHWIND ADVANCE") } else { Text("x") }))
            .collect();
        let sparse = vec![(Column::LenderName, Text("SAMPLE FUNDING")), (Column::Tib, Number(2.0))];
        let industries = crate::facts::application::test_industries();
        let plan = plan(&sheet(&[full, sparse]), &BTreeMap::new(), &industries);
        for row in &plan.rows {
            for cell in &row.cells {
                assert_eq!(cell.raw.is_none(), cell.outcome == CellOutcome::Empty, "line {} {:?}", row.line, cell);
            }
        }
        assert!(plan.rows[1].cells.iter().filter(|cell| cell.raw.is_some()).count() == 2);
    }

    #[test]
    fn the_header_row_must_hold_every_column_once() {
        let mut headers: Vec<&str> = Column::ALL.map(Column::header).to_vec();
        headers.pop();
        let missing = read_sheet_bytes(workbook_with_headers(&headers, &[]));
        assert!(matches!(missing, Err(SheetError::MissingColumn(Column::RecordId))));
        headers.push("Record Id");
        headers.push("Lender Name");
        assert!(matches!(
            read_sheet_bytes(workbook_with_headers(&headers, &[])),
            Err(SheetError::DuplicateColumn(Column::LenderName))
        ));
        headers.pop();
        headers.push("Commission");
        assert!(matches!(read_sheet_bytes(workbook_with_headers(&headers, &[])), Err(SheetError::UnknownColumn(_))));
        let mut lower: Vec<String> = Column::ALL.map(|column| column.header().to_uppercase()).to_vec();
        lower[0] = "  lender   name ".to_string();
        let lower: Vec<&str> = lower.iter().map(String::as_str).collect();
        assert!(read_sheet_bytes(workbook_with_headers(&lower, &[])).is_ok(), "case and spacing do not matter");
    }

    #[test]
    fn a_workbook_without_the_sheet_is_refused() {
        let mut book = rust_xlsxwriter::Workbook::new();
        book.add_worksheet().set_name("Contacts").unwrap();
        let bytes = book.save_to_buffer().unwrap();
        assert!(matches!(read_sheet_bytes(bytes), Err(SheetError::NoLendersModuleSheet)));
        assert!(matches!(read_sheet_bytes(b"not a workbook".to_vec()), Err(SheetError::Unreadable)));
    }

    fn seed_rows() -> Vec<Vec<(Column, Value)>> {
        vec![
            lender(
                "CONTOSO CAPITAL",
                "REC-1",
                vec![
                    (Column::MinMonthlyRev, Number(25000.0)),
                    (Column::NsfPerMonth, Number(3.0)),
                    (Column::Positions, Text("1-3")),
                    (Column::RestrictedStates, Text("PR")),
                    (Column::RestrictedIndustries, Text("Cannabis;Firearms / Weapons")),
                ],
            ),
            lender("FABRIKAM FUNDING", "REC-2", vec![(Column::Positions, Text("1-5+"))]),
            vec![(Column::LenderName, Text("NORTHWIND ADVANCE")), (Column::Tib, Number(1.0))],
            vec![(Column::LenderName, Text("SAMPLE PARTNER LINK"))],
        ]
    }

    fn revision_count(store: &Store) -> usize {
        store
            .read(|tx| {
                let mut count = 0;
                for head in tx.heads()? {
                    count += tx.history(&head.lender)?.len();
                }
                Ok(count)
            })
            .unwrap()
    }

    #[test]
    fn a_dry_run_writes_nothing() {
        let store = Store::open_in_memory();
        let report = run(&store, &sheet(&seed_rows()), ImportMode::DryRun).unwrap();
        assert!(!report.applied);
        assert_eq!(report.count(|a| matches!(a, ActionReport::Create)), 4);
        assert_eq!(report.new_industries, ["Cannabis", "Firearms / Weapons"]);
        assert!(store.read(|tx| tx.heads()).unwrap().is_empty());
        assert_eq!(store.read(|tx| tx.industries()).unwrap().all().count(), 0);
    }

    #[test]
    fn apply_creates_drafts_and_a_rerun_writes_only_its_log_row() {
        let store = Store::open_in_memory();
        let sheet = sheet(&seed_rows());
        let first = run(&store, &sheet, ImportMode::Apply).unwrap();
        assert!(first.applied);
        let heads = store.read(|tx| tx.heads()).unwrap();
        assert_eq!(heads.len(), 4);
        assert!(heads.iter().all(|head| head.record.policy.status() == LenderStatus::Draft));
        assert!(heads.iter().all(|head| head.author.is_import()));
        assert!(first.rows.iter().all(|row| row.lender.is_some()));
        assert!(first.rows.iter().find(|row| row.name == "SAMPLE PARTNER LINK").unwrap().no_criteria);
        let industries = store.read(|tx| tx.industries()).unwrap();
        assert!(industries.resolve("firearms-weapons").is_some());

        let second = run(&store, &sheet, ImportMode::Apply).unwrap();
        assert_eq!(second.count(|a| matches!(a, ActionReport::Unchanged)), 4);
        assert_eq!(revision_count(&store), 4);
        assert_eq!(store.read(|tx| tx.import_runs()).unwrap().len(), 2);
    }

    #[test]
    fn a_changed_cell_updates_an_import_owned_lender_and_never_one_an_admin_edited() {
        let store = Store::open_in_memory();
        run(&store, &sheet(&seed_rows()), ImportMode::Apply).unwrap();
        let author = editor(&store);
        let contoso =
            store.read(|tx| tx.heads()).unwrap().into_iter().find(|h| h.record.profile.name == "CONTOSO CAPITAL");
        let contoso = contoso.unwrap();
        let mut edited = contoso.record.clone();
        edited.profile.terms.commission = Some("10 points".to_string());
        store.write(|tx| tx.save_revision(&contoso.lender, 1, &edited, &author, None)).unwrap();

        let mut rows = seed_rows();
        rows[0].push((Column::CreditScore, Number(600.0)));
        rows[1].push((Column::CreditScore, Number(550.0)));
        let report = run(&store, &sheet(&rows), ImportMode::Apply).unwrap();
        let action = |name: &str| report.rows.iter().find(|row| row.name == name).unwrap().action.clone();
        assert_eq!(action("CONTOSO CAPITAL"), ActionReport::KeptAdminEdits { head: 2, differs: true });
        assert_eq!(action("FABRIKAM FUNDING"), ActionReport::Update { revision: Some(2) });
        assert_eq!(action("NORTHWIND ADVANCE"), ActionReport::Unchanged);
        let kept = store.read(|tx| tx.head(&contoso.lender)).unwrap().unwrap();
        assert_eq!(kept.record, edited);
    }

    #[test]
    fn lenders_missing_from_the_sheet_are_reported_and_kept() {
        let store = Store::open_in_memory();
        run(&store, &sheet(&seed_rows()), ImportMode::Apply).unwrap();
        let report = run(&store, &sheet(&seed_rows()[..2]), ImportMode::Apply).unwrap();
        let missing: Vec<&str> = report.not_in_sheet.iter().map(|missing| missing.name.as_str()).collect();
        assert_eq!(missing, ["NORTHWIND ADVANCE", "SAMPLE PARTNER LINK"]);
        assert_eq!(store.read(|tx| tx.heads()).unwrap().len(), 4);
    }

    #[test]
    fn blockers_refuse_apply_and_write_nothing() {
        let store = Store::open_in_memory();
        let mut rows = seed_rows();
        rows.push(lender("CONTOSO CAPITAL AGAIN", "REC-1", vec![(Column::RestrictedIndustries, Text("Crypto"))]));
        rows.push(vec![(Column::Tib, Number(2.0))]);
        let result = run(&store, &sheet(&rows), ImportMode::Apply);
        let Err(ImportError::Blocked(report)) = result else { panic!("expected blockers") };
        assert_eq!(report.blockers.len(), 2, "{:?}", report.blockers);
        assert!(store.read(|tx| tx.heads()).unwrap().is_empty());
        assert_eq!(store.read(|tx| tx.industries()).unwrap().all().count(), 0);
    }

    #[test]
    fn an_imported_lender_evaluates_once_activated() {
        let store = Store::open_in_memory();
        run(&store, &sheet(&seed_rows()), ImportMode::Apply).unwrap();
        let contoso =
            store.read(|tx| tx.heads()).unwrap().into_iter().find(|h| h.record.profile.name == "CONTOSO CAPITAL");
        let policy = contoso.unwrap().record.policy.with_status(LenderStatus::Active).unwrap();
        let input = DealInput { application: application(), confirmations: everything_confirmed() };
        let facts = assemble(Some(&three_clean_months()), &input, AS_OF);
        assert_eq!(evaluate(&policy, 1, &facts, &[]).status(), VerdictStatus::Match);
    }

    #[test]
    fn reports_round_trip_through_json() {
        let store = Store::open_in_memory();
        let report = run(&store, &sheet(&seed_rows()), ImportMode::Apply).unwrap();
        assert_eq!(parse_report(&report_json(&report)).unwrap(), report);
        assert!(report.lines().iter().any(|line| line.contains("default: positions above 5")));
    }
}
