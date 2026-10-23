//! `/api/v1`: parse the wire request into domain types, run the matcher once, render the result.

use std::time::Duration;

use axum::body::Bytes;
use axum::extract::{FromRequestParts, Path, State};
use axum::http::header::{ALLOW, AUTHORIZATION, CACHE_CONTROL, LOCATION, RETRY_AFTER, WWW_AUTHENTICATE};
use axum::http::request::Parts;
use axum::http::{HeaderValue, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use lender_matching_wire::v1 as wire;
use time::Date;
use uuid::Uuid;

use super::{Shared, log_error};
use crate::criteria::describe;
use crate::criteria::eval::{Evaluation, Outcome, Overruled, Scope as NoteScope, VerdictStatus, Waiver, reads};
use crate::criteria::{LenderStatus, NoteKind, Product};
use crate::facts::application::{ApplicationFacts, EntityKind, Industries, Jurisdiction, YearMonth};
use crate::facts::{Basis, DealFacts, DealInput, Fact, FactKey, Interval, Source};
use crate::matching::{Creator, MatchError, MatchInput, MatchView, Requester, VerdictResult};
use crate::store::auth::{MachineClient, Scope};
use crate::store::{Revision, StoreError, now, time_text};

pub fn router() -> Router<Shared> {
    Router::new()
        .route("/industries", get(industries).fallback(not_allowed_get))
        .route("/matches", post(create_match).fallback(not_allowed_post))
        .route("/matches/{id}", get(get_match).fallback(not_allowed_get))
        .fallback(route_not_found)
        .layer(axum::middleware::map_response(|mut response: Response| async move {
            response.headers_mut().insert(CACHE_CONTROL, HeaderValue::from_static("no-store"));
            response
        }))
}

#[derive(Debug)]
pub struct ApiError {
    code: wire::ErrorCode,
    field: Option<&'static str>,
    retry_after: Option<Duration>,
    allow: Option<&'static str>,
}

impl ApiError {
    pub fn new(code: wire::ErrorCode) -> ApiError {
        ApiError { code, field: None, retry_after: None, allow: None }
    }

    fn invalid_fact(field: &'static str) -> ApiError {
        ApiError { field: Some(field), ..ApiError::new(wire::ErrorCode::InvalidFact) }
    }

    fn internal(context: &str, error: &dyn std::fmt::Display) -> ApiError {
        log_error(context, error);
        ApiError::new(wire::ErrorCode::InternalError)
    }
}

impl From<StoreError> for ApiError {
    fn from(error: StoreError) -> Self {
        ApiError::internal("store", &error)
    }
}

impl From<MatchError> for ApiError {
    fn from(error: MatchError) -> Self {
        use wire::ErrorCode::*;
        match error {
            MatchError::AnalysisNotConfigured => ApiError::new(AnalysisNotConfigured),
            MatchError::AnalysisNotReady { retry_after } => {
                ApiError { retry_after: Some(retry_after), ..ApiError::new(AnalysisNotReady) }
            }
            MatchError::AnalysisPackageNotFound => ApiError::new(AnalysisPackageNotFound),
            MatchError::AnalysisUnavailable(why) => {
                log_error("analysis", &why);
                ApiError::new(AnalysisUnavailable)
            }
            MatchError::AnalysisContractMismatch(why) => {
                log_error("analysis contract", &why);
                ApiError::new(AnalysisContractMismatch)
            }
            other @ (MatchError::AlreadySuperseded | MatchError::Store(_)) => ApiError::internal("match", &other),
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let body = wire::ErrorResponse {
            error: wire::ApiError {
                code: self.code,
                message: self.code.message().to_string(),
                field: self.field.map(str::to_string),
            },
        };
        let status = StatusCode::from_u16(self.code.status()).expect("error codes carry valid statuses");
        let mut response = (status, Json(body)).into_response();
        let headers = response.headers_mut();
        if self.code == wire::ErrorCode::Unauthorized {
            headers.insert(WWW_AUTHENTICATE, HeaderValue::from_static("Bearer realm=\"lender-matching-api\""));
        }
        if let Some(retry_after) = self.retry_after {
            headers.insert(RETRY_AFTER, HeaderValue::from(retry_after.as_secs()));
        }
        if let Some(allow) = self.allow {
            headers.insert(ALLOW, HeaderValue::from_static(allow));
        }
        response
    }
}

/// The token after `Bearer`, in any case, with surrounding whitespace ignored.
fn bearer(parts: &Parts) -> Option<&str> {
    let value = parts.headers.get(AUTHORIZATION)?.to_str().ok()?.trim();
    let (scheme, token) = value.split_once(char::is_whitespace)?;
    let token = token.trim();
    (scheme.eq_ignore_ascii_case("bearer") && !token.is_empty()).then_some(token)
}

impl FromRequestParts<Shared> for MachineClient {
    type Rejection = ApiError;

    async fn from_request_parts(parts: &mut Parts, app: &Shared) -> Result<Self, Self::Rejection> {
        let token = bearer(parts).ok_or_else(|| ApiError::new(wire::ErrorCode::Unauthorized))?;
        app.read(|tx| tx.machine_client(token))?.ok_or_else(|| ApiError::new(wire::ErrorCode::Unauthorized))
    }
}

fn require(client: &MachineClient, scope: Scope) -> Result<(), ApiError> {
    if client.has(scope) { Ok(()) } else { Err(ApiError::new(wire::ErrorCode::ScopeRequired)) }
}

async fn route_not_found(_client: MachineClient) -> ApiError {
    ApiError::new(wire::ErrorCode::RouteNotFound)
}

async fn not_allowed_get(_client: MachineClient) -> ApiError {
    ApiError { allow: Some("GET, HEAD"), ..ApiError::new(wire::ErrorCode::MethodNotAllowed) }
}

async fn not_allowed_post(_client: MachineClient) -> ApiError {
    ApiError { allow: Some("POST"), ..ApiError::new(wire::ErrorCode::MethodNotAllowed) }
}

async fn industries(
    State(app): State<Shared>,
    client: MachineClient,
) -> Result<Json<wire::IndustriesResponse>, ApiError> {
    require(&client, Scope::Read)?;
    let industries = app.read(|tx| tx.industries())?;
    Ok(Json(wire::IndustriesResponse {
        api_version: wire::API_VERSION.to_string(),
        industries: industries
            .active()
            .map(|industry| wire::Industry { id: industry.id.to_string(), label: industry.label.clone() })
            .collect(),
    }))
}

async fn create_match(State(app): State<Shared>, client: MachineClient, body: Bytes) -> Result<Response, ApiError> {
    require(&client, Scope::Match)?;
    let request: wire::MatchRequest =
        serde_json::from_slice(&body).map_err(|_| ApiError::new(wire::ErrorCode::InvalidRequest))?;
    let industries = app.read(|tx| tx.industries())?;
    let input = parse_request(request, &industries, now().date())?;
    let record = app.matcher.run(Requester::Client(client.id), input).await?;
    let view = app.read(|tx| MatchView::load(tx, record.id))?;
    let view = view.ok_or_else(|| ApiError::internal("match", &"a match just stored is missing"))?;
    let location = format!("/api/v1/matches/{}", record.id);
    Ok((StatusCode::CREATED, [(LOCATION, location)], Json(render_match(&view, &industries))).into_response())
}

async fn get_match(
    State(app): State<Shared>,
    client: MachineClient,
    Path(id): Path<String>,
) -> Result<Json<wire::MatchResponse>, ApiError> {
    require(&client, Scope::Read)?;
    let not_found = || ApiError::new(wire::ErrorCode::MatchNotFound);
    let id = Uuid::parse_str(&id).map_err(|_| not_found())?;
    let (view, industries) = app.read(|tx| Ok((MatchView::load(tx, id)?, tx.industries()?)))?;
    Ok(Json(render_match(&view.ok_or_else(not_found)?, &industries)))
}

fn product(product: wire::Product) -> Product {
    match product {
        wire::Product::Mca => Product::Mca,
        wire::Product::TermLoan => Product::TermLoan,
        wire::Product::LineOfCredit => Product::LineOfCredit,
        wire::Product::Equipment => Product::Equipment,
        wire::Product::Sba => Product::Sba,
    }
}

fn wire_product(product: Product) -> wire::Product {
    match product {
        Product::Mca => wire::Product::Mca,
        Product::TermLoan => wire::Product::TermLoan,
        Product::LineOfCredit => wire::Product::LineOfCredit,
        Product::Equipment => wire::Product::Equipment,
        Product::Sba => wire::Product::Sba,
    }
}

fn entity(entity: wire::Entity) -> EntityKind {
    match entity {
        wire::Entity::SoleProprietorship => EntityKind::SoleProprietorship,
        wire::Entity::Partnership => EntityKind::Partnership,
        wire::Entity::Llc => EntityKind::Llc,
        wire::Entity::Corporation => EntityKind::Corporation,
        wire::Entity::NonProfit => EntityKind::NonProfit,
        wire::Entity::Other => EntityKind::Other,
    }
}

/// Refuses a value no fact can hold with `422 invalid_fact` naming the field.
pub fn parse_request(
    request: wire::MatchRequest,
    industries: &Industries,
    today: Date,
) -> Result<MatchInput, ApiError> {
    let app = request.application;
    let state = app
        .business_state
        .map(|code| Jurisdiction::from_code(&code).ok_or(ApiError::invalid_fact("/application/business_state")))
        .transpose()?;
    let start = app
        .business_start_month
        .map(|text| {
            YearMonth::parse(&text)
                .filter(|month| *month <= YearMonth::of(today))
                .ok_or(ApiError::invalid_fact("/application/business_start_month"))
        })
        .transpose()?;
    let fico = app
        .estimated_fico
        .map(|range| {
            let max = range.max.unwrap_or(850);
            let valid = (300..=850).contains(&range.min) && (range.min..=850).contains(&max);
            valid
                .then(|| Interval::between(range.min, max))
                .flatten()
                .ok_or(ApiError::invalid_fact("/application/estimated_fico"))
        })
        .transpose()?;
    let amount = app
        .requested_amount_cents
        .map(|cents| (cents > 0).then_some(cents).ok_or(ApiError::invalid_fact("/application/requested_amount_cents")))
        .transpose()?;
    let suggestion = app
        .industry_suggestion
        .map(|slug| industries.resolve(&slug).ok_or(ApiError::invalid_fact("/application/industry_suggestion")))
        .transpose()?;
    Ok(MatchInput {
        analysis_package: request.analysis_package_id,
        product: product(request.product),
        deal: DealInput {
            application: ApplicationFacts {
                business_state: state,
                business_start: start,
                entity: app.entity.map(entity),
                estimated_fico: fico,
                requested_amount_cents: amount,
                open_judgements: app.open_judgements,
                bankruptcy: app.bankruptcy,
                tax_liens: app.tax_liens,
                industry_suggestion: suggestion,
            },
            confirmations: Default::default(),
        },
        waivers: Vec::new(),
    })
}

pub fn range(interval: Interval) -> wire::Range {
    wire::Range { min: interval.lo(), max: interval.hi() }
}

fn source(source: &Source) -> String {
    match source {
        Source::Analysis(field) | Source::Application(field) => field.clone(),
        Source::Confirmed { by, at } => format!("confirmed by {by} at {}", time_text(*at)),
    }
}

fn fact<V>(key: FactKey, fact: &Fact<V>, value: impl Fn(&V) -> wire::FactValue) -> wire::Fact {
    let (known, shown, basis, gap, seen) = match fact {
        Fact::Known { value: known, basis, .. } => {
            let basis = match basis {
                Basis::Printed => wire::Basis::Printed,
                Basis::Stated => wire::Basis::Stated,
                Basis::Confirmed => wire::Basis::Confirmed,
            };
            (true, Some(value(known)), Some(basis), None, None)
        }
        Fact::Unknown { gap, seen, .. } => (false, None, None, Some(gap.key().to_string()), seen.as_ref().map(&value)),
    };
    wire::Fact { fact: key.key().to_string(), known, value: shown, basis, gap, seen, source: source(fact.source()) }
}

pub fn render_facts(facts: &DealFacts) -> Vec<wire::Fact> {
    FactKey::all()
        .into_iter()
        .map(|key| match key {
            FactKey::Num(num) => fact(key, facts.num(num), |value| wire::FactValue::Range(range(*value))),
            FactKey::State => fact(key, facts.state(), |state| wire::FactValue::Text(state.code().to_string())),
            FactKey::Industry => fact(key, facts.industry(), |industry| wire::FactValue::Text(industry.to_string())),
            FactKey::Entity => fact(key, facts.entity(), |entity| wire::FactValue::Text(entity.key().to_string())),
            FactKey::Flag(flag) => fact(key, facts.flag(flag), |value| wire::FactValue::Flag(*value)),
        })
        .collect()
}

pub fn render_waiver(waiver: &Waiver) -> wire::Waiver {
    wire::Waiver {
        check: waiver.check.to_string(),
        lender_revision: waiver.lender_revision,
        analysis_revision: waiver.analysis_revision.clone(),
        by: waiver.by.clone(),
        at: time_text(waiver.at),
        reason: waiver.reason.clone(),
    }
}

pub fn render_verdict(
    evaluation: &Evaluation,
    revision: &Revision,
    current: bool,
    industries: &Industries,
) -> wire::Verdict {
    let policy = &revision.record.policy;
    let checks = evaluation
        .checks
        .iter()
        .filter_map(|check| {
            let rule = policy.rules().iter().find(|rule| rule.id == check.rule)?;
            let (outcome, why, overruled, waiver) = match &check.outcome {
                Outcome::Pass => (wire::Outcome::Pass, None, None, None),
                Outcome::NotApplicable => (wire::Outcome::NotApplicable, None, None, None),
                Outcome::Fail => (wire::Outcome::Fail, None, None, None),
                Outcome::Unproven(why) => (wire::Outcome::Unproven, Some(why.why()), None, None),
                Outcome::Waived { waiver, overruled: Overruled::Fail } => {
                    (wire::Outcome::Waived, None, Some(wire::Outcome::Fail), Some(render_waiver(waiver)))
                }
                Outcome::Waived { waiver, overruled: Overruled::Unproven(why) } => {
                    (wire::Outcome::Waived, Some(why.why()), Some(wire::Outcome::Unproven), Some(render_waiver(waiver)))
                }
            };
            let mut facts: Vec<String> = Vec::new();
            for key in rule.when.iter().chain([&rule.require]).map(reads) {
                if !facts.iter().any(|fact| fact == key.key()) {
                    facts.push(key.key().to_string());
                }
            }
            Some(wire::Check {
                id: rule.id.to_string(),
                text: describe::rule(rule, industries),
                outcome,
                why: why.map(str::to_string),
                overruled,
                facts,
                waiver,
            })
        })
        .collect();
    let notes = evaluation
        .notes
        .iter()
        .filter_map(|result| {
            let note = policy.notes().iter().find(|note| note.id == result.note)?;
            Some(wire::NoteResult {
                id: note.id.to_string(),
                kind: match note.kind {
                    NoteKind::Condition => wire::NoteKind::Condition,
                    NoteKind::Info => wire::NoteKind::Info,
                },
                scope: match result.scope {
                    NoteScope::In => wire::Scope::InScope,
                    NoteScope::Out => wire::Scope::OutOfScope,
                    NoteScope::Unknown => wire::Scope::ScopeUnknown,
                },
                text: note.text.clone(),
                when: describe::note_scope(note, industries),
                waiver: result.waiver.as_ref().map(render_waiver),
            })
        })
        .collect();
    wire::Verdict {
        lender_id: revision.lender.to_string(),
        name: revision.record.profile.name.clone(),
        lender_revision: revision.number,
        current,
        status: match evaluation.status() {
            VerdictStatus::Match => wire::VerdictStatus::Match,
            VerdictStatus::Review => wire::VerdictStatus::Review,
            VerdictStatus::NoMatch => wire::VerdictStatus::NoMatch,
        },
        checks,
        notes,
        stale_waivers: evaluation.stale_waivers.iter().map(render_waiver).collect(),
    }
}

pub fn render_match(view: &MatchView, industries: &Industries) -> wire::MatchResponse {
    let record = &view.record;
    let mut verdicts = Vec::new();
    let mut inactive = Vec::new();
    for verdict in &record.verdicts {
        let revision = &view.revisions[&verdict.lender];
        let current = view.is_current(verdict);
        let status = match &verdict.result {
            VerdictResult::Evaluated(evaluation) => {
                verdicts.push(render_verdict(evaluation, revision, current, industries));
                continue;
            }
            VerdictResult::Inactive(LenderStatus::Draft) => wire::InactiveStatus::Draft,
            VerdictResult::Inactive(LenderStatus::Paused | LenderStatus::Active) => wire::InactiveStatus::Paused,
            VerdictResult::NotOffered => wire::InactiveStatus::NotOffered,
        };
        inactive.push(wire::Inactive {
            lender_id: verdict.lender.to_string(),
            name: revision.record.profile.name.clone(),
            lender_revision: verdict.revision,
            current,
            status,
        });
    }
    wire::MatchResponse {
        api_version: wire::API_VERSION.to_string(),
        match_id: record.id,
        created_at: time_text(record.created_at),
        created_by: match &view.created_by {
            Creator::Client(name) => wire::CreatedBy::Client { name: name.clone() },
            Creator::Person(username) => wire::CreatedBy::Person { username: username.clone() },
        },
        supersedes: match &record.by {
            Requester::Person { supersedes, .. } => Some(*supersedes),
            Requester::Client(_) => None,
        },
        superseded_by: view.superseded_by,
        as_of: record.facts.as_of.to_string(),
        engine_version: record.engine_version,
        product: wire_product(record.input.product),
        analysis: record
            .facts
            .analysis
            .as_ref()
            .map(|analysis| wire::AnalysisRef { package_id: analysis.package_id, revision: analysis.revision.clone() }),
        facts: render_facts(&record.facts),
        months: record
            .facts
            .months
            .iter()
            .map(|month| wire::StatementMonth {
                month: month.month.map(|month| month.to_string()),
                negative_days: range(month.negative_days),
                deposits: range(month.deposits),
            })
            .collect(),
        verdicts,
        inactive,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::facts::application::test_industries;
    use time::macros::date;

    fn request(application: serde_json::Value) -> wire::MatchRequest {
        serde_json::from_value(serde_json::json!({ "application": application })).unwrap()
    }

    #[test]
    fn each_refused_field_is_named() {
        let industries = test_industries();
        let today = date!(2026 - 10 - 23);
        let cases = [
            (serde_json::json!({"business_state": "XX"}), "/application/business_state"),
            (serde_json::json!({"business_start_month": "2026-13"}), "/application/business_start_month"),
            (serde_json::json!({"business_start_month": "2026-11"}), "/application/business_start_month"),
            (serde_json::json!({"estimated_fico": {"min": 250}}), "/application/estimated_fico"),
            (serde_json::json!({"estimated_fico": {"min": 700, "max": 650}}), "/application/estimated_fico"),
            (serde_json::json!({"requested_amount_cents": 0}), "/application/requested_amount_cents"),
            (serde_json::json!({"industry_suggestion": "crypto"}), "/application/industry_suggestion"),
        ];
        for (application, field) in cases {
            let error = parse_request(request(application.clone()), &industries, today).unwrap_err();
            assert_eq!((error.code, error.field), (wire::ErrorCode::InvalidFact, Some(field)), "{application}");
        }
        let accepted = request(serde_json::json!({
            "business_state": "tx", "business_start_month": "2026-10", "estimated_fico": {"min": 650, "max": 700},
            "industry_suggestion": "cannabis", "entity": "llc"
        }));
        let input = parse_request(accepted, &industries, today).unwrap();
        assert_eq!(input.deal.application.business_state.map(Jurisdiction::code), Some("TX"));
        assert_eq!(input.product, Product::Mca);
    }

    #[test]
    fn requests_refuse_unknown_fields() {
        let body = serde_json::json!({"application": {}, "attestations": []});
        assert!(serde_json::from_value::<wire::MatchRequest>(body).is_err());
        let body = serde_json::json!({"application": {"estimated_fico_score": 640}});
        assert!(serde_json::from_value::<wire::MatchRequest>(body).is_err());
    }
}
