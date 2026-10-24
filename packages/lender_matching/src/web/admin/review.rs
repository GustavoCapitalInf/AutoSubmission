//! The reviewer form does not edit a match: it makes a new one (analysis fetched again, current
//! heads) that names the match it supersedes, with the person's confirmations and waivers. A match
//! of a stored application reads the application's current revision; when that is newer than the
//! one the match read, the confirmations and waivers are dropped, since they judged other facts.

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use lender_matching_wire::v1 as wire;
use maud::{Markup, html};
use uuid::Uuid;

use super::{Fields, PageError, RawForm, csrf, errors, fields, page, redirect, require};
use crate::applications::ApplicationRef;
use crate::criteria::CheckId;
use crate::criteria::describe;
use crate::criteria::eval::{Outcome, Waiver};
use crate::facts::application::{Confirmations, Confirmed, Industries};
use crate::facts::{FactKey, FlagFact, NumFact};
use crate::matching::{ApplicationInput, MatchCommand, MatchError, MatchView, Requester, VerdictResult};
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

/// The newer revision of the stored application the match read, if one exists.
fn changed_application(view: &MatchView) -> Option<ApplicationRef> {
    let read = view.record.application?;
    let head = view.application_head?;
    (head != read.revision).then_some(ApplicationRef { id: read.id, revision: head })
}

/// What a review submits: the facts the match read, or the stored application's revision. A
/// changed application gives its current revision with no confirmation or waiver.
fn next_command(view: &MatchView, confirmations: Confirmations, waivers: Vec<Waiver>) -> MatchCommand {
    let input = &view.record.input;
    let (application, confirmations, waivers) = match (view.record.application, changed_application(view)) {
        (_, Some(current)) => (ApplicationInput::Stored(current), Confirmations::default(), Vec::new()),
        (Some(read), None) => (ApplicationInput::Stored(read), confirmations, waivers),
        (None, None) => (ApplicationInput::Inline(input.deal.application.clone()), confirmations, waivers),
    };
    MatchCommand {
        analysis_package: input.analysis_package,
        product: input.product,
        application,
        confirmations,
        waivers,
    }
}

/// The confirmations a form gives, and a problem for an industry that is not active.
pub fn confirmations(fields: &Fields, industries: &Industries, user: &AdminUser) -> (Confirmations, Vec<String>) {
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
    (confirmations, problems)
}

/// The page for a match the matcher refused.
pub fn refused(error: MatchError) -> PageError {
    match error {
        MatchError::AlreadySuperseded => PageError::status(
            StatusCode::CONFLICT,
            "Someone already made a newer match from this one; review that one.",
        ),
        MatchError::AnalysisNotReady { retry_after } => PageError::status(
            StatusCode::CONFLICT,
            &format!("The analysis package is processing again. Try again in {} seconds.", retry_after.as_secs()),
        ),
        MatchError::ApplicationsUnavailable => PageError::status(
            StatusCode::SERVICE_UNAVAILABLE,
            "Stored applications are off: this server has no APPLICATION_DATA_KEY.",
        ),
        MatchError::ApplicationNotFound => PageError::not_found(),
        MatchError::ApplicationChanged { current } => PageError::status(
            StatusCode::CONFLICT,
            &format!("The application changed: revision {current} is current. Open it again and match that one."),
        ),
        MatchError::ApplicationUnconfirmed => {
            PageError::status(StatusCode::CONFLICT, "Confirm that this document is an application before matching it.")
        }
        MatchError::Store(error) => error.into(),
        other @ (MatchError::AnalysisNotConfigured
        | MatchError::AnalysisPackageNotFound
        | MatchError::AnalysisUnavailable(_)
        | MatchError::AnalysisContractMismatch(_)) => {
            crate::web::log_error("match", &other);
            PageError::status(
                StatusCode::BAD_GATEWAY,
                "The analysis service could not give the package; nothing was saved.",
            )
        }
    }
}

fn render(user: &AdminUser, view: &MatchView, industries: &Industries, problems: &[String]) -> Markup {
    let body = render_match(view, industries);
    let changed = changed_application(view);
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
            @if let Some(read) = view.record.application {
                p {
                    "Stored application " code { (read.id) } ", revision " (read.revision) "."
                    @if let Some(current) = changed { " " span.badge { "revision " (current.revision) " is current" } }
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
            @if can_review && changed.is_some() {
                h2 { "Review" }
                p.note { "The application changed after this match. A new match reads its current revision, with the analysis fetched again and every lender's current criteria, and starts without confirmations or waivers." }
                form method="post" action={ "/admin/matches/" (body.match_id) "/review" } {
                    (csrf(user))
                    button { "Make a new match from the current application" }
                }
            } @else if can_review {
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
                            @if let Some(suggested) = suggestion { " " span.note { "suggested: " (industries.label(suggested.as_str())) } }
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
    let (confirmations, mut problems) = confirmations(&fields, &industries, &user);
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
    let command = next_command(&view, confirmations, waivers);
    match app.matcher.run(Requester::Person { user: user.id, supersedes: Some(id) }, command).await {
        Ok(record) => Ok(redirect(&format!("/admin/matches/{}", record.id))),
        Err(error) => Err(refused(error)),
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use lender_matching_application::{EditInput, Edits};

    use super::*;
    use crate::applications::testing::{LEGAL_NAME, key, service, support::form::Form, upload};
    use crate::applications::{Cause, Saved};
    use crate::criteria::Product;
    use crate::facts::testing::everything_confirmed;
    use crate::matching::Matcher;
    use crate::store::Store;
    use crate::store::auth::Role;

    #[tokio::test(flavor = "multi_thread")]
    async fn a_review_keeps_its_choices_until_the_application_changes_and_then_drops_them() {
        let store = Arc::new(Store::open_in_memory());
        let user = store.write(|tx| tx.add_user("sample.reviewer", "correct horse battery", Role::Reviewer)).unwrap();
        let (applications, reader) = service(&store);
        let first = upload(&applications, &reader, Form::word(), user);
        let matcher = Matcher::new(store.clone(), None, Some(Arc::new(key())));
        let command = MatchCommand {
            analysis_package: None,
            product: Product::Mca,
            application: ApplicationInput::Stored(first),
            confirmations: everything_confirmed(),
            waivers: Vec::new(),
        };
        let made = matcher.run(Requester::Person { user, supersedes: None }, command).await.unwrap();
        let view = |id| store.read(|tx| MatchView::load(tx, id)).unwrap().unwrap();
        let waiver = Waiver {
            lender: crate::criteria::LenderId::generate(),
            check: CheckId::Rule(crate::criteria::RuleId(1)),
            lender_revision: 1,
            analysis_revision: None,
            by: "sample.reviewer".to_string(),
            at: now(),
            reason: "SAMPLE LENDER confirmed an exception".to_string(),
        };

        let unchanged = next_command(&view(made.id), everything_confirmed(), vec![waiver.clone()]);
        assert_eq!(unchanged.application, ApplicationInput::Stored(first));
        assert_eq!((unchanged.confirmations, unchanged.waivers), (everything_confirmed(), vec![waiver.clone()]));

        let current = applications.current(first.id).unwrap();
        let edits =
            Edits::read(current.record(), &[(LEGAL_NAME, EditInput::Text("FABRIKAM LLC"))], now().date()).ok().unwrap();
        assert!(matches!(applications.correct(first, &edits, Cause::Merchant, None, user), Ok(Saved::New(_))));
        let changed = view(made.id);
        assert_eq!(changed_application(&changed), Some(ApplicationRef { revision: 2, ..first }));
        let next = next_command(&changed, everything_confirmed(), vec![waiver]);
        assert_eq!(next.application, ApplicationInput::Stored(ApplicationRef { revision: 2, ..first }));
        assert_eq!(next.confirmations, Confirmations::default(), "choices made on other facts are dropped");
        assert!(next.waivers.is_empty());
        let remade = matcher.run(Requester::Person { user, supersedes: Some(made.id) }, next).await.unwrap();
        assert_eq!(remade.application, Some(ApplicationRef { revision: 2, ..first }));
        assert_eq!(remade.input.deal.confirmations, Confirmations::default());
    }
}
