//! Lender matching API v1. In a response, `fact`, `gap`, `why` and `source` are open strings
//! that 1.x may extend; every enum here is a closed set, and a new value needs v2. A response
//! field that can be null is always present.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// This contract's version.
pub const API_VERSION: &str = "1.0";

/// `POST /api/v1/matches`: match one deal against every active lender.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MatchRequest {
    /// The bank statement analysis package to read; absent or null matches on the application alone.
    #[serde(default)]
    pub analysis_package_id: Option<Uuid>,
    /// The funding product sought; `mca` when absent. A lender that does not offer it is listed as `not_offered`.
    #[serde(default)]
    pub product: Product,
    /// What the merchant stated on the application. Every field may be absent or null.
    pub application: Application,
}

#[derive(Clone, Copy, Default, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Product {
    #[default]
    Mca,
    TermLoan,
    LineOfCredit,
    Equipment,
    Sba,
}

#[derive(Clone, Default, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Application {
    /// A US state, DC, US territory or Canadian province postal code, such as `TX`.
    #[serde(default)]
    pub business_state: Option<String>,
    /// The business start month, `YYYY-MM`, not after the current month.
    #[serde(default)]
    pub business_start_month: Option<String>,
    #[serde(default)]
    pub entity: Option<Entity>,
    /// The estimated FICO score, 300 to 850; a stated range such as 650-700 stays a range.
    #[serde(default)]
    pub estimated_fico: Option<Range>,
    /// The requested advance in USD cents; greater than 0.
    #[serde(default)]
    pub requested_amount_cents: Option<i64>,
    #[serde(default)]
    pub open_judgements: Option<bool>,
    #[serde(default)]
    pub bankruptcy: Option<bool>,
    #[serde(default)]
    pub tax_liens: Option<bool>,
    /// An active industry `id` from `GET /api/v1/industries`. Shown as evidence only: the industry
    /// is a fact only once a person confirms it on the match page.
    #[serde(default)]
    pub industry_suggestion: Option<String>,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Entity {
    SoleProprietorship,
    Partnership,
    Llc,
    Corporation,
    NonProfit,
    Other,
}

/// Inclusive integer bounds; `max` null is unbounded above.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Range {
    pub min: i64,
    #[serde(default)]
    pub max: Option<i64>,
}

/// `GET /api/v1/industries`: the active industry picklist.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct IndustriesResponse {
    pub api_version: String,
    pub industries: Vec<Industry>,
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Industry {
    pub id: String,
    pub label: String,
}

/// A stored match: the facts it read, and one verdict per active lender that offers the product.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct MatchResponse {
    pub api_version: String,
    pub match_id: Uuid,
    /// RFC 3339, UTC.
    pub created_at: String,
    pub created_by: CreatedBy,
    /// The match this one replaced, when a person made it from the match page.
    pub supersedes: Option<Uuid>,
    /// The newer match a person made from this one; null while this one is the latest.
    pub superseded_by: Option<Uuid>,
    /// The date, `YYYY-MM-DD` in UTC, that time in business is counted to.
    pub as_of: String,
    /// The version of the fact assembly and evaluation that computed this match.
    pub engine_version: u32,
    pub product: Product,
    /// The analysis package and revision the facts came from; null when the request named none.
    pub analysis: Option<AnalysisRef>,
    /// Every fact, known or not, once each.
    pub facts: Vec<Fact>,
    /// The per-month numbers behind the worst-month facts.
    pub months: Vec<StatementMonth>,
    pub verdicts: Vec<Verdict>,
    /// Lenders not evaluated: not active, or not offering the product.
    pub inactive: Vec<Inactive>,
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum CreatedBy {
    /// A machine client, by its token name.
    Client { name: String },
    /// A signed-in person, by username.
    Person { username: String },
}

#[derive(Clone, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct AnalysisRef {
    pub package_id: Uuid,
    /// The analysis package's opaque change token.
    pub revision: String,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Fact {
    /// The fact's name, such as `monthly_true_revenue_cents`.
    pub fact: String,
    pub known: bool,
    /// The proven value, or for a number the interval it is proven to lie within; null when unknown.
    pub value: Option<FactValue>,
    /// Where a known value comes from; null when unknown.
    pub basis: Option<Basis>,
    /// Why the fact is unknown, such as `needs_confirmation`; null when known.
    pub gap: Option<String>,
    /// An unproven value shown as evidence and not evaluated, such as a stated industry.
    pub seen: Option<FactValue>,
    /// The field it came from, or who confirmed it and when.
    pub source: String,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(untagged)]
pub enum FactValue {
    Range(Range),
    Text(String),
    Flag(bool),
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Basis {
    /// Published by the bank statement analysis.
    Printed,
    /// Stated on the application.
    Stated,
    /// Confirmed by a signed-in person.
    Confirmed,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct StatementMonth {
    /// `YYYY-MM`; null for a statement without a readable period.
    pub month: Option<String>,
    pub negative_days: Range,
    pub deposits: Range,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Verdict {
    pub lender_id: String,
    pub name: String,
    /// The lender revision this verdict read.
    pub lender_revision: u32,
    /// Whether that revision is still the lender's current one.
    pub current: bool,
    pub status: VerdictStatus,
    pub checks: Vec<Check>,
    pub notes: Vec<NoteResult>,
    /// Waivers given on another lender or analysis revision; they were not applied.
    pub stale_waivers: Vec<Waiver>,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum VerdictStatus {
    /// Every check passes or is waived, and no condition note may apply unwaived.
    Match,
    /// No check fails, but a check is unproven or a condition note may apply.
    Review,
    /// A check fails.
    NoMatch,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Check {
    /// The rule's id within the lender revision, such as `r1`.
    pub id: String,
    /// The rule in words.
    pub text: String,
    pub outcome: Outcome,
    /// For `unproven`, or `waived` over an unproven check: `fact_unknown`, `straddles` or `scope_unknown`.
    pub why: Option<String>,
    /// For `waived`: what the waiver overruled, `fail` or `unproven`.
    pub overruled: Option<Outcome>,
    /// The facts the rule reads.
    pub facts: Vec<String>,
    pub waiver: Option<Waiver>,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    Pass,
    /// The rule's condition is false for this deal.
    NotApplicable,
    Fail,
    Unproven,
    Waived,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct NoteResult {
    /// The note's id within the lender revision, such as `n1`.
    pub id: String,
    pub kind: NoteKind,
    pub scope: Scope,
    pub text: String,
    /// The note's condition in words; null when it always applies.
    pub when: Option<String>,
    pub waiver: Option<Waiver>,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum NoteKind {
    /// Holds the verdict at review while it may apply.
    Condition,
    /// Shown; does not change a verdict.
    Info,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Scope {
    InScope,
    OutOfScope,
    ScopeUnknown,
}

/// A signed-in person's decision to set a check or note aside for this deal.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Waiver {
    pub check: String,
    pub lender_revision: u32,
    pub analysis_revision: Option<String>,
    /// The person's username.
    pub by: String,
    /// RFC 3339, UTC.
    pub at: String,
    pub reason: String,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct Inactive {
    pub lender_id: String,
    pub name: String,
    pub lender_revision: u32,
    pub current: bool,
    pub status: InactiveStatus,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum InactiveStatus {
    Draft,
    Paused,
    NotOffered,
}

/// Every error body.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct ErrorResponse {
    pub error: ApiError,
}

#[derive(Clone, PartialEq, Debug, Serialize, Deserialize, JsonSchema)]
pub struct ApiError {
    pub code: ErrorCode,
    /// The code's one fixed message.
    pub message: String,
    /// For `invalid_fact`: the JSON pointer of the refused field, such as `/application/business_state`.
    pub field: Option<String>,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ErrorCode {
    InvalidRequest,
    InvalidFact,
    Unauthorized,
    ScopeRequired,
    MatchNotFound,
    RouteNotFound,
    MethodNotAllowed,
    AnalysisNotReady,
    AnalysisPackageNotFound,
    InternalError,
    AnalysisUnavailable,
    AnalysisContractMismatch,
    AnalysisNotConfigured,
}

impl ErrorCode {
    pub const ALL: [ErrorCode; 13] = [
        ErrorCode::InvalidRequest,
        ErrorCode::InvalidFact,
        ErrorCode::Unauthorized,
        ErrorCode::ScopeRequired,
        ErrorCode::MatchNotFound,
        ErrorCode::RouteNotFound,
        ErrorCode::MethodNotAllowed,
        ErrorCode::AnalysisNotReady,
        ErrorCode::AnalysisPackageNotFound,
        ErrorCode::InternalError,
        ErrorCode::AnalysisUnavailable,
        ErrorCode::AnalysisContractMismatch,
        ErrorCode::AnalysisNotConfigured,
    ];

    pub fn key(self) -> &'static str {
        match self {
            ErrorCode::InvalidRequest => "invalid_request",
            ErrorCode::InvalidFact => "invalid_fact",
            ErrorCode::Unauthorized => "unauthorized",
            ErrorCode::ScopeRequired => "scope_required",
            ErrorCode::MatchNotFound => "match_not_found",
            ErrorCode::RouteNotFound => "route_not_found",
            ErrorCode::MethodNotAllowed => "method_not_allowed",
            ErrorCode::AnalysisNotReady => "analysis_not_ready",
            ErrorCode::AnalysisPackageNotFound => "analysis_package_not_found",
            ErrorCode::InternalError => "internal_error",
            ErrorCode::AnalysisUnavailable => "analysis_unavailable",
            ErrorCode::AnalysisContractMismatch => "analysis_contract_mismatch",
            ErrorCode::AnalysisNotConfigured => "analysis_not_configured",
        }
    }

    pub fn status(self) -> u16 {
        match self {
            ErrorCode::InvalidRequest => 400,
            ErrorCode::Unauthorized => 401,
            ErrorCode::ScopeRequired => 403,
            ErrorCode::MatchNotFound | ErrorCode::RouteNotFound => 404,
            ErrorCode::MethodNotAllowed => 405,
            ErrorCode::AnalysisNotReady => 409,
            ErrorCode::InvalidFact | ErrorCode::AnalysisPackageNotFound => 422,
            ErrorCode::InternalError => 500,
            ErrorCode::AnalysisUnavailable | ErrorCode::AnalysisContractMismatch => 502,
            ErrorCode::AnalysisNotConfigured => 503,
        }
    }

    pub fn message(self) -> &'static str {
        match self {
            ErrorCode::InvalidRequest => "the request could not be read",
            ErrorCode::InvalidFact => "a field holds a value this API does not accept",
            ErrorCode::Unauthorized => "a valid bearer token is required",
            ErrorCode::ScopeRequired => "the token lacks the scope this request needs",
            ErrorCode::MatchNotFound => "no match has this id",
            ErrorCode::RouteNotFound => "no API route has this path",
            ErrorCode::MethodNotAllowed => "this route does not accept this method",
            ErrorCode::AnalysisNotReady => "the analysis package is still processing; retry after Retry-After seconds",
            ErrorCode::AnalysisPackageNotFound => "the analysis service has no package with this id",
            ErrorCode::InternalError => "the server could not answer this request",
            ErrorCode::AnalysisUnavailable => "the analysis service could not be reached or refused the request",
            ErrorCode::AnalysisContractMismatch => "the analysis service answered with a body outside its v1 contract",
            ErrorCode::AnalysisNotConfigured => "this server has no analysis service configured",
        }
    }
}
