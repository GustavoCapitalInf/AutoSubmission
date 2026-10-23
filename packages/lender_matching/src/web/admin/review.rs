//! A match's evidence for a person, and the reviewer form. The form does not edit a match: it makes
//! a new one (analysis fetched again, current heads) that names the match it supersedes, with the
//! person's confirmations and waivers.

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use lender_matching_wire::v1 as wire;
use maud::{Markup, html};
use uuid::Uuid;

use super::{PageError, RawForm, csrf, errors, fields, page, redirect, require};
use crate::criteria::CheckId;
use crate::criteria::describe;
use crate::criteria::eval::{Outcome, Waiver};
use crate::facts::application::{Confirmations, Confirmed, Industries};
use crate::facts::{FactKey, FlagFact, NumFact};
use crate::matching::{MatchError, MatchInput, MatchView, Requester, VerdictResult};
use crate::store::auth::{AdminUser, Role};
use crate::store::now;
use crate::web::Shared;
use crate::web::api::render_match;

fn match_id(text: &str) -> Result<Uuid, PageError> {
    Uuid::parse_str(text).map_err(|_| PageError::not_found())
}

fn value_text(fact: &str, value: &Option<wire::FactValue>) -> String {
    let money = matches!(FactKey::from_key(fact), Some(FactKey::Num(num)) if num.is_money());
    let number = |value: i64| if money { describe::money(value) } else { value.to_string() };
    match value {
        None => String::new(),
        Some(wire::FactValue::Range(range)) => match range.max {
            Some(max) if max == range.min => number(max),
            Some(max) => format!("{} to {}", number(range.min), number(max)),
            None => format!("at least {}", number(range.min)),
        },
        Some(wire::FactValue::Text(text)) => text.clone(),
        Some(wire::FactValue::Flag(flag)) => if *flag { "yes" } else { "no" }.to_string(),
    }
}

fn label(fact: &str) -> String {
    FactKey::from_key(fact).map_or_else(|| fact.to_string(), |key| describe::fact_label(key).to_string())
}

/// The checks and notes a person can set aside on this verdict: those that fail or are unproven,
/// and condition notes that may apply.
fn waivable(verdict: &wire::Verdict) -> Vec<(String, String)> {
    let checks = verdict
        .checks
        .iter()
        .filter(|check| matches!(check.outcome, wire::Outcome::Fail | wire::Outcome::Unproven | wire::Outcome::Waived))
        .map(|check| (check.id.clone(), check.text.clone()));
    let notes = verdict
        .notes
        .iter()
        .filter(|note| note.kind == wire::NoteKind::Condition && note.scope != wire::Scope::OutOfScope)
        .map(|note| (note.id.clone(), format!("Note: {}", note.text)));
    checks.chain(notes).collect()
}

fn applied_waiver(view: &MatchView, lender: &str, check: &str) -> Option<Waiver> {
    let verdict = view.record.verdicts.iter().find(|verdict| verdict.lender.as_str() == lender)?;
    let VerdictResult::Evaluated(evaluation) = &verdict.result else { return None };
    let check = CheckId::parse(check)?;
    let from_checks = evaluation.checks.iter().find_map(|result| match &result.outcome {
        Outcome::Waived { waiver, .. } if CheckId::Rule(result.rule) == check => Some(waiver.clone()),
        _ => None,
    });
    from_checks.or_else(|| {
        evaluation.notes.iter().find(|note| CheckId::Note(note.note) == check).and_then(|note| note.waiver.clone())
    })
}

fn outcome_label(outcome: wire::Outcome) -> &'static str {
    match outcome {
        wire::Outcome::Pass => "pass",
        wire::Outcome::NotApplicable => "does not apply",
        wire::Outcome::Fail => "fail",
        wire::Outcome::Unproven => "unproven",
        wire::Outcome::Waived => "waived",
    }
}

fn scope_label(scope: wire::Scope) -> &'static str {
    match scope {
        wire::Scope::InScope => "applies",
        wire::Scope::OutOfScope => "does not apply",
        wire::Scope::ScopeUnknown => "may apply",
    }
}

fn status_label(status: wire::VerdictStatus) -> (&'static str, &'static str) {
    match status {
        wire::VerdictStatus::Match => ("badge match", "match"),
        wire::VerdictStatus::Review => ("badge review", "review"),
        wire::VerdictStatus::NoMatch => ("badge no_match", "no match"),
    }
}

fn inactive_label(status: wire::InactiveStatus) -> &'static str {
    match status {
        wire::InactiveStatus::Draft => "draft",
        wire::InactiveStatus::Paused => "paused",
        wire::InactiveStatus::NotOffered => "does not offer this product",
    }
}

fn basis_label(basis: wire::Basis) -> &'static str {
    match basis {
        wire::Basis::Printed => "printed by the analysis",
        wire::Basis::Stated => "stated on the application",
        wire::Basis::Confirmed => "confirmed by a person",
    }
}

fn product_label(product: wire::Product) -> &'static str {
    match product {
        wire::Product::Mca => "MCA",
        wire::Product::TermLoan => "term loan",
        wire::Product::LineOfCredit => "line of credit",
        wire::Product::Equipment => "equipment finance",
        wire::Product::Sba => "SBA loan",
    }
}

fn kind_label(kind: wire::NoteKind) -> &'static str {
    match kind {
        wire::NoteKind::Condition => "condition",
        wire::NoteKind::Info => "info",
    }
}

fn render(user: &AdminUser, view: &MatchView, industries: &Industries, problems: &[String]) -> Markup {
    let body = render_match(view, industries);
    let confirmations = &view.record.input.deal.confirmations;
    let flag_choice = |name: &str, current: Option<bool>| {
        html! {
            label { input type="radio" name=(name) value="" checked[current.is_none()]; " not confirmed" } " "
            label { input type="radio" name=(name) value="no" checked[current == Some(false)]; " no" } " "
            label { input type="radio" name=(name) value="yes" checked[current == Some(true)]; " yes" }
        }
    };
    let suggestion = view.record.input.deal.application.industry_suggestion.as_ref();
    let can_review = user.can(Role::Reviewer) && view.superseded_by.is_none();
    page(
        Some(user),
        "Match",
        html! {
            p {
                code { (body.match_id) } " made " (body.created_at) " by "
                @match &body.created_by {
                    wire::CreatedBy::Client { name } => { "client " (name) }
                    wire::CreatedBy::Person { username } => { (username) }
                }
                ". Time in business is counted to " (body.as_of) ". Product: " (product_label(body.product)) "."
            }
            @if let Some(older) = body.supersedes { p { "Supersedes " a href={ "/admin/matches/" (older) } { (older) } "." } }
            @if let Some(newer) = body.superseded_by { p.error { "Superseded by " a href={ "/admin/matches/" (newer) } { (newer) } "; review that one." } }
            p {
                @match &body.analysis {
                    Some(analysis) => { "Analysis package " code { (analysis.package_id) } ", revision " code { (analysis.revision) } "." }
                    None => { "No analysis package: every statement fact is unknown." }
                }
            }
            h2 { "Facts" }
            table {
                tr { th { "Fact" } th { "Value" } th { "Basis or gap" } th { "Source" } th { "Seen, not proven" } }
                @for fact in &body.facts {
                    tr {
                        td { (label(&fact.fact)) }
                        td { (value_text(&fact.fact, &fact.value)) }
                        td {
                            @match (&fact.basis, &fact.gap) {
                                (Some(basis), _) => (basis_label(*basis)),
                                (None, Some(gap)) => span.badge { (gap.replace('_', " ")) },
                                (None, None) => "",
                            }
                        }
                        td.note { (fact.source) }
                        td { (value_text(&fact.fact, &fact.seen)) }
                    }
                }
            }
            @if !body.months.is_empty() {
                h2 { "Statement months" }
                table {
                    tr { th { "Month" } th { "Negative days" } th { "Deposits" } }
                    @for month in &body.months {
                        tr {
                            td { (month.month.as_deref().unwrap_or("undated statement")) }
                            td { (value_text(NumFact::WorstMonthNegativeDays.key(), &Some(wire::FactValue::Range(month.negative_days)))) }
                            td { (value_text(NumFact::WorstMonthDeposits.key(), &Some(wire::FactValue::Range(month.deposits)))) }
                        }
                    }
                }
            }
            h2 { "Verdicts" }
            @for verdict in &body.verdicts {
                h3 {
                    @let (class, text) = status_label(verdict.status);
                    span class=(class) { (text) }
                    " " a href={ "/admin/lenders/" (verdict.lender_id) } { (verdict.name) }
                    " " span.note { "revision " (verdict.lender_revision) @if !verdict.current { ", since changed" } }
                }
                table {
                    tr { th { "Check" } th { "Outcome" } th { "Facts read" } }
                    @for check in &verdict.checks {
                        tr {
                            td { (check.id) ": " (check.text) }
                            td {
                                (outcome_label(check.outcome))
                                @if let Some(why) = &check.why { " (" (why.replace('_', " ")) ")" }
                                @if let Some(waiver) = &check.waiver { br; span.note { "waived by " (waiver.by) ": " (waiver.reason) } }
                            }
                            td.note { (check.facts.iter().map(|fact| label(fact)).collect::<Vec<_>>().join(", ")) }
                        }
                    }
                    @for note in &verdict.notes {
                        tr {
                            td { (note.id) " (" (kind_label(note.kind)) "): " (note.text) @if let Some(when) = &note.when { br; span.note { (when) } } }
                            td {
                                (scope_label(note.scope))
                                @if let Some(waiver) = &note.waiver { br; span.note { "waived by " (waiver.by) ": " (waiver.reason) } }
                            }
                            td {}
                        }
                    }
                }
                @if !verdict.stale_waivers.is_empty() {
                    p.note { "Not applied, given on another revision: " @for waiver in &verdict.stale_waivers { (waiver.check) " (" (waiver.reason) ") " } }
                }
            }
            @if !body.inactive.is_empty() {
                h2 { "Not evaluated" }
                ul {
                    @for lender in &body.inactive {
                        li { a href={ "/admin/lenders/" (lender.lender_id) } { (lender.name) } " " span.note { (inactive_label(lender.status)) } }
                    }
                }
            }
            @if can_review {
                h2 { "Review" }
                p.note { "Submitting makes a new match with the analysis fetched again and every lender's current criteria. A waiver holds only while the lender's revision and the analysis revision stay as shown here." }
                (errors(problems))
                form method="post" action={ "/admin/matches/" (body.match_id) "/review" } {
                    (csrf(user))
                    fieldset {
                        legend { "Confirm facts" }
                        p {
                            "Industry: "
                            select name="confirm.industry" {
                                option value="" selected[confirmations.industry.is_none()] { "not confirmed" }
                                @for industry in industries.active() {
                                    option value=(industry.id) selected[confirmations.industry.as_ref().is_some_and(|c| c.value == industry.id)] { (industry.label) }
                                }
                            }
                            @if let Some(suggested) = suggestion { " " span.note { "suggested: " (industries.label(suggested)) } }
                        }
                        p { (describe::fact_label(FactKey::Flag(FlagFact::DefaultHistory))) ": " (flag_choice("confirm.default_history", confirmations.default_history.as_ref().map(|c| c.value))) }
                        p { (describe::fact_label(FactKey::Flag(FlagFact::HomeBased))) ": " (flag_choice("confirm.home_based", confirmations.home_based.as_ref().map(|c| c.value))) }
                        p { (describe::fact_label(FactKey::Flag(FlagFact::OpenLawsuit))) ": " (flag_choice("confirm.open_lawsuit", confirmations.open_lawsuit.as_ref().map(|c| c.value))) }
                    }
                    fieldset {
                        legend { "Waive checks" }
                        @for verdict in &body.verdicts {
                            @let items = waivable(verdict);
                            @if !items.is_empty() {
                                p { strong { (verdict.name) } }
                                @for (check, text) in &items {
                                    @let key = format!("{}.{}", verdict.lender_id, check);
                                    @let applied = applied_waiver(view, &verdict.lender_id, check);
                                    div {
                                        label { input type="checkbox" name={ "waive." (key) } checked[applied.is_some()]; " " (check) ": " (text) }
                                        " " input type="text" name={ "reason." (key) } placeholder="reason" size="40" value=(applied.as_ref().map_or("", |w| w.reason.as_str()));
                                    }
                                }
                            }
                        }
                    }
                    button { "Make a new match with these confirmations and waivers" }
                }
            }
        },
    )
}

pub async fn view(State(app): State<Shared>, user: AdminUser, Path(id): Path<String>) -> Result<Markup, PageError> {
    let id = match_id(&id)?;
    let (view, industries) = app.read(|tx| Ok((MatchView::load(tx, id)?, tx.industries()?)))?;
    Ok(render(&user, &view.ok_or_else(PageError::not_found)?, &industries, &[]))
}

pub async fn submit(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    require(&user, Role::Reviewer)?;
    let id = match_id(&id)?;
    let fields = fields(form);
    fields.check_csrf(&user)?;
    let (view, industries) = app.read(|tx| Ok((MatchView::load(tx, id)?, tx.industries()?)))?;
    let view = view.ok_or_else(PageError::not_found)?;
    if view.superseded_by.is_some() {
        return Err(PageError::status(
            StatusCode::CONFLICT,
            "Someone already made a newer match from this one; review that one.",
        ));
    }
    let at = now();
    let mut problems = Vec::new();
    let industry = match fields.get("confirm.industry") {
        "" => None,
        slug => match industries.resolve(slug) {
            Some(id) => Some(Confirmed { value: id, by: user.username.clone(), at }),
            None => {
                problems.push("Industry: choose an active industry".to_string());
                None
            }
        },
    };
    let flag = |name: &str| {
        let value = match fields.get(name) {
            "yes" => true,
            "no" => false,
            _ => return None,
        };
        Some(Confirmed { value, by: user.username.clone(), at })
    };
    let confirmations = Confirmations {
        industry,
        default_history: flag("confirm.default_history"),
        home_based: flag("confirm.home_based"),
        open_lawsuit: flag("confirm.open_lawsuit"),
    };
    let body = render_match(&view, &industries);
    let analysis_revision = view.record.facts.analysis.as_ref().map(|analysis| analysis.revision.clone());
    let mut waivers = Vec::new();
    for verdict in &body.verdicts {
        for (check, _) in waivable(verdict) {
            let key = format!("{}.{}", verdict.lender_id, check);
            if !fields.has(&format!("waive.{key}")) {
                continue;
            }
            let reason = fields.get(&format!("reason.{key}")).trim().to_string();
            if reason.is_empty() {
                problems.push(format!("{} {check}: give a reason for the waiver", verdict.name));
                continue;
            }
            let (Some(lender), Some(check)) =
                (crate::criteria::LenderId::parse(&verdict.lender_id), CheckId::parse(&check))
            else {
                continue;
            };
            waivers.push(Waiver {
                lender,
                check,
                lender_revision: verdict.lender_revision,
                analysis_revision: analysis_revision.clone(),
                by: user.username.clone(),
                at,
                reason,
            });
        }
    }
    if !problems.is_empty() {
        return Ok((StatusCode::UNPROCESSABLE_ENTITY, render(&user, &view, &industries, &problems)).into_response());
    }
    let input = MatchInput {
        deal: crate::facts::DealInput { confirmations, ..view.record.input.deal.clone() },
        waivers,
        ..view.record.input.clone()
    };
    match app.matcher.run(Requester::Person { user: user.id, supersedes: id }, input).await {
        Ok(record) => Ok(redirect(&format!("/admin/matches/{}", record.id))),
        Err(MatchError::AlreadySuperseded) => Err(PageError::status(
            StatusCode::CONFLICT,
            "Someone already made a newer match from this one; review that one.",
        )),
        Err(MatchError::AnalysisNotReady { retry_after }) => Err(PageError::status(
            StatusCode::CONFLICT,
            &format!("The analysis package is processing again. Try again in {} seconds.", retry_after.as_secs()),
        )),
        Err(MatchError::Store(error)) => Err(error.into()),
        Err(other) => {
            crate::web::log_error("review", &other);
            Err(PageError::status(
                StatusCode::BAD_GATEWAY,
                "The analysis service could not give the package; nothing was saved.",
            ))
        }
    }
}
