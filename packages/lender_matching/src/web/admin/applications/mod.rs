//! The application pages: the list, upload, and the form in the cards of the owner's screenshot.
//! Viewers read; reviewers and editors upload, correct and match. An SSN shows by its last four
//! digits and a date of birth as recorded or missing, and no input holds either
//! (`empty_required_fields_are_red_unread_ones_amber_and_identity_data_stays_masked`).

mod form;
mod text;

use std::collections::BTreeMap;

use axum::Router;
use axum::extract::{DefaultBodyLimit, Multipart, Path, Query, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use lender_matching_application::extract::Document;
use lender_matching_application::fields::{BusinessField, OwnerField, OwnerSlot};
use lender_matching_application::pdf::ReadError;
use lender_matching_application::record::Attention;
use lender_matching_application::worker::WorkerError;
use lender_matching_application::{Admission, Current, Edits, FieldId, FieldValue, Resolved};
use maud::{Markup, html};
use serde::Deserialize;
use uuid::Uuid;

use super::review::{confirmations, refused};
use super::{Fields, PageError, RawForm, csrf, errors, fields, page, redirect, require, shown_time, wide_page};
use crate::applications::{
    ApplicationError, ApplicationId, ApplicationRef, Applications, Cause, Intake, Saved, Snapshot, Upload,
};
use crate::criteria::Product;
use crate::matching::{ApplicationInput, MatchCommand, Requester};
use crate::store::auth::{AdminUser, Role};
use crate::store::now;
use crate::web::Shared;
use form::{FormView, Submission, render_cards};

/// Uploads above this many bytes are refused.
const UPLOAD_LIMIT: usize = 32 << 20;

pub fn router() -> Router<Shared> {
    Router::new()
        .route("/admin/applications", get(list).post(upload).layer(DefaultBodyLimit::max(UPLOAD_LIMIT)))
        .route("/admin/applications/new", get(new_page))
        .route("/admin/applications/{id}", get(view).post(save))
        .route("/admin/applications/{id}/remove-second-owner", post(remove_second_owner))
        .route("/admin/applications/{id}/confirm", post(confirm))
        .route("/admin/applications/{id}/matches", post(create_match))
}

fn unprocessable(message: &str) -> PageError {
    PageError::status(StatusCode::UNPROCESSABLE_ENTITY, message)
}

/// The stored applications, or 503 on a server without `APPLICATION_DATA_KEY`.
fn service(app: &Shared) -> Result<&Applications, PageError> {
    app.applications.as_ref().ok_or_else(|| {
        PageError::status(
            StatusCode::SERVICE_UNAVAILABLE,
            "Stored applications are off: this server has no APPLICATION_DATA_KEY.",
        )
    })
}

fn application_id(text: &str) -> Result<ApplicationId, PageError> {
    Uuid::parse_str(text).map(ApplicationId).map_err(|_| PageError::not_found())
}

/// `Applications` reads PDFs and SQLite; this tells the runtime the worker blocks meanwhile.
fn blocking<T>(work: impl FnOnce() -> Result<T, ApplicationError>) -> Result<T, PageError> {
    tokio::task::block_in_place(work).map_err(failed)
}

fn failed(error: ApplicationError) -> PageError {
    match error {
        ApplicationError::NotFound => PageError::not_found(),
        ApplicationError::Conflict { head } => PageError::status(
            StatusCode::CONFLICT,
            &format!(
                "Revision {} was saved since this page opened; nothing was saved. Open the application again.",
                head.revision.reference.revision
            ),
        ),
        ApplicationError::NotAnApplication => {
            unprocessable("That reading takes the document for something other than an application.")
        }
        ApplicationError::Pdf(WorkerError::NoEngine) => PageError::status(
            StatusCode::SERVICE_UNAVAILABLE,
            "This server has no PDF engine: set PDFIUM_LIBRARY. Nothing was saved.",
        ),
        ApplicationError::Pdf(WorkerError::Read(ReadError::TooLarge)) => {
            PageError::status(StatusCode::PAYLOAD_TOO_LARGE, "The PDF is too large to read. Nothing was saved.")
        }
        ApplicationError::Pdf(WorkerError::Read(_)) => {
            unprocessable("This file is not a PDF the server can open. Nothing was saved.")
        }
        ApplicationError::Pdf(WorkerError::Timeout | WorkerError::Crashed) => {
            unprocessable("The PDF could not be read in time. Nothing was saved.")
        }
        ApplicationError::Unstorable => unprocessable("The PDF's reading could not be stored. Nothing was saved."),
        ApplicationError::Store(error) => error.into(),
    }
}

fn text_of(resolved: &Resolved, field: FieldId) -> Option<String> {
    resolved.value(field).map(FieldValue::canonical)
}

const LEGAL_NAME: FieldId = FieldId::Business(BusinessField::LegalName);
const PRINCIPAL_NAME: FieldId = FieldId::Owner(OwnerSlot::Principal, OwnerField::Name);

/// The layout page 1 was read in, or how else the document reads.
fn layout(head: &Snapshot) -> &'static str {
    match &head.parse.reading.document {
        Document::Application(form) => form.layout.as_str(),
        Document::ManualEntry(_) => "hand entry",
        Document::Refused(_) => "not an application",
    }
}

fn plural(count: usize, one: &str, many: &str) -> String {
    format!("{count} {}", if count == 1 { one } else { many })
}

/// The attention badges: required fields with nothing in them, fields that need review (a
/// required one counts here only), and a draft nobody confirmed.
fn badges(head: &Snapshot, resolved: &Resolved) -> Vec<String> {
    let mut badges = Vec::new();
    let review = |current: &Current| matches!(current, Current::NeedsReview);
    let required = resolved
        .iter()
        .filter(|(_, state)| !review(&state.current) && state.attention.contains(&Attention::RequiredEmpty))
        .count();
    if required > 0 {
        badges.push(format!("{required} required empty"));
    }
    let unread = resolved.iter().filter(|(_, state)| review(&state.current)).count();
    if unread > 0 {
        badges.push(plural(unread, "needs review", "need review"));
    }
    if head.revision.state.admission == Admission::AwaitingConfirmation {
        badges.push("awaiting confirmation".to_string());
    }
    badges
}

async fn list(State(app): State<Shared>, user: AdminUser) -> Result<Markup, PageError> {
    let applications = service(&app)?;
    let rows = blocking(|| applications.list())?;
    Ok(page(
        Some(&user),
        "Applications",
        html! {
            @if user.can(Role::Reviewer) { p { a href="/admin/applications/new" { "Upload an application" } } }
            table {
                tr { th { "Business" } th { "Principal owner" } th { "Uploaded" } th { "Layout" } th { "Attention" } }
                @for (upload, head) in &rows {
                    @let resolved = head.record().resolve();
                    tr {
                        td { a href={ "/admin/applications/" (upload.id) } { (text_of(&resolved, LEGAL_NAME).unwrap_or_else(|| "no legal name".to_string())) } }
                        td { (text_of(&resolved, PRINCIPAL_NAME).unwrap_or_default()) }
                        td { (upload.by) " " span.note { (shown_time(upload.at)) } }
                        td { (layout(head)) }
                        td { @for badge in badges(head, &resolved) { span.badge { (badge) } } }
                    }
                }
            }
            p.note { (plural(rows.len(), "application", "applications")) "." }
        },
    ))
}

fn upload_form(user: &AdminUser) -> Markup {
    html! {
        form method="post" action="/admin/applications" enctype="multipart/form-data" {
            (csrf(user))
            p { label { "Application PDF " input type="file" name="pdf" accept="application/pdf" required; } }
            button { "Upload" }
        }
        p.note { "The server reads the PDF, stores it sealed, and opens its form. Identical bytes open the application already stored. A file that is not the application form is refused and nothing is stored." }
    }
}

async fn new_page(user: AdminUser) -> Result<Markup, PageError> {
    require(&user, Role::Reviewer)?;
    Ok(page(Some(&user), "Upload an application", upload_form(&user)))
}

/// `POST /admin/applications`: multipart with the `csrf` part first, then `pdf`. The CSRF token is
/// checked before the file is read.
async fn upload(State(app): State<Shared>, user: AdminUser, mut multipart: Multipart) -> Result<Response, PageError> {
    require(&user, Role::Reviewer)?;
    let applications = service(&app)?;
    let stale = || {
        PageError::status(
            StatusCode::FORBIDDEN,
            "This form is stale or was not sent from these pages. Reload and try again.",
        )
    };
    let too_large =
        || PageError::status(StatusCode::PAYLOAD_TOO_LARGE, "The file is larger than 32 MiB. Nothing was saved.");
    let token = match multipart.next_field().await {
        Ok(Some(part)) if part.name() == Some("csrf") => part.text().await.map_err(|_| stale())?,
        _ => return Err(stale()),
    };
    if !user.csrf_matches(&token) {
        return Err(stale());
    }
    let pdf = match multipart.next_field().await {
        Ok(Some(part)) if part.name() == Some("pdf") => part.bytes().await.map_err(|error| {
            if error.status() == StatusCode::PAYLOAD_TOO_LARGE {
                too_large()
            } else {
                unprocessable("The upload was cut off. Nothing was saved.")
            }
        })?,
        Err(error) if error.status() == StatusCode::PAYLOAD_TOO_LARGE => return Err(too_large()),
        _ => return Err(unprocessable("Choose a PDF file. Nothing was saved.")),
    };
    if pdf.is_empty() {
        return Err(unprocessable("Choose a PDF file. Nothing was saved."));
    }
    match blocking(|| applications.upload(&pdf, user.id))? {
        Intake::Stored { reference, .. } => Ok(redirect(&format!("/admin/applications/{}", reference.id))),
        Intake::AlreadyStored(reference) => Ok(redirect(&format!("/admin/applications/{}?existing=1", reference.id))),
        Intake::Refused(reason) => {
            let body = html! {
                p.error { "This PDF reads as " (text::refused_document(reason)) ", not an application. Nothing was saved." }
                (upload_form(&user))
            };
            Ok((StatusCode::UNPROCESSABLE_ENTITY, page(Some(&user), "Upload an application", body)).into_response())
        }
    }
}

#[derive(Deserialize)]
struct ViewQuery {
    existing: Option<String>,
    done: Option<String>,
}

/// The notice after an action, by the `done` key its redirect names.
fn done_notice(done: &str) -> Option<&'static str> {
    Some(match done {
        "saved" => "Saved.",
        "unchanged" => "Nothing changed, so nothing was saved.",
        "removed" => "The second owner was removed.",
        "confirmed" => "Confirmed as an application.",
        _ => return None,
    })
}

/// One rendering of an application's page.
struct Shown<'a> {
    user: &'a AdminUser,
    head: &'a Snapshot,
    upload: &'a Upload,
    earlier: Option<ApplicationId>,
    /// Above the form, such as the notice after an action or a conflict's two changes.
    notices: Vec<Markup>,
    /// A refused or conflicting submission, shown again in the form.
    submitted: Option<&'a Submission>,
    problems: Vec<String>,
    field_problems: BTreeMap<FieldId, String>,
}

impl<'a> Shown<'a> {
    fn new(user: &'a AdminUser, head: &'a Snapshot, upload: &'a Upload, earlier: Option<ApplicationId>) -> Shown<'a> {
        Shown {
            user,
            head,
            upload,
            earlier,
            notices: Vec::new(),
            submitted: None,
            problems: Vec::new(),
            field_problems: BTreeMap::new(),
        }
    }
}

fn application_page(shown: &Shown) -> Markup {
    let head = shown.head;
    let reference = head.revision.reference;
    let id = reference.id;
    let resolved = head.record().resolve();
    let editable = shown.user.can(Role::Reviewer);
    let view = FormView {
        head,
        resolved: &resolved,
        reviewer: editable,
        submitted: shown.submitted,
        problems: &shown.field_problems,
    };
    let action = format!("/admin/applications/{id}");
    let remove = (editable && resolved.has_second_owner()).then(|| {
        html! { button.small type="submit" formaction={ (action) "/remove-second-owner" } { "Remove second owner" } }
    });
    let cause = shown.submitted.and_then(|submitted| submitted.cause);
    let reason = shown.submitted.map_or("", |submitted| submitted.reason.as_str());
    let title = text_of(&resolved, LEGAL_NAME).unwrap_or_else(|| "Application".to_string());
    let attention = badges(head, &resolved);
    wide_page(
        Some(shown.user),
        &title,
        html! {
            p.note {
                "Revision " (reference.revision) " · " (layout(head)) " · read by parser " (head.parse.parser_version)
                " · uploaded by " (shown.upload.by) " at " (shown_time(shown.upload.at))
            }
            @for notice in &shown.notices { (notice) }
            @if let Some(earlier) = shown.earlier {
                p.notice { "Another file of the same DocuSign envelope was stored first: " a href={ "/admin/applications/" (earlier) } { "that application" } "." }
            }
            @if let Document::ManualEntry(reason) = &head.parse.reading.document {
                p.notice { "Hand entry: " (text::manual_entry(*reason)) ". Type the fields from the PDF." }
            }
            @if head.revision.state.admission == Admission::AwaitingConfirmation && editable {
                form.notice method="post" action={ (action) "/confirm" } {
                    (csrf(shown.user))
                    input type="hidden" name="base_revision" value=(reference.revision);
                    "Matching waits until a person confirms this document is an application. "
                    button { "This is an application" }
                }
            }
            @if !attention.is_empty() { p { @for badge in &attention { span.badge { (badge) } } } }
            (errors(&shown.problems))
            @if editable {
                form method="post" action=(action) {
                    (csrf(shown.user))
                    input type="hidden" name="base_revision" value=(reference.revision);
                    (render_cards(&view, remove))
                    section.card {
                        h2 { "Save corrections" }
                        p {
                            "Why: "
                            label { input type="radio" name="cause" value="reading" checked[cause == Some(Cause::Reading)]; " the parser read the PDF wrong" } " "
                            label { input type="radio" name="cause" value="merchant" checked[cause == Some(Cause::Merchant)]; " the PDF is wrong: the merchant typed it wrong" }
                        }
                        p { label { "Reason (optional) " input type="text" name="reason" value=(reason) size="50"; } }
                        button { "Save corrections" }
                        p.note { "Only the inputs you change are saved, each as a person's value. A blank SSN or date of birth input keeps the stored one." }
                    }
                }
            } @else {
                (render_cards(&view, None))
            }
            p { a href="/admin/applications" { "All applications" } " · id " code { (id) } }
        },
    )
}

async fn view(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    Query(query): Query<ViewQuery>,
) -> Result<Markup, PageError> {
    let applications = service(&app)?;
    let id = application_id(&id)?;
    let (head, (upload, earlier)) = blocking(|| Ok((applications.current(id)?, applications.upload_of(id)?)))?;
    let mut shown = Shown::new(&user, &head, &upload, earlier);
    if query.existing.is_some() {
        shown.notices.push(html! { p.notice { "This file was uploaded already; this is its application." } });
    }
    if let Some(notice) = query.done.as_deref().and_then(done_notice) {
        shown.notices.push(html! { p.notice { (notice) } });
    }
    Ok(application_page(&shown))
}

/// The revision a form was rendered from, by its `base_revision`.
fn base_of(fields: &Fields, id: ApplicationId) -> Result<ApplicationRef, PageError> {
    let revision = fields
        .get("base_revision")
        .parse()
        .map_err(|_| PageError::status(StatusCode::BAD_REQUEST, "The form lacks its revision."))?;
    Ok(ApplicationRef { id, revision })
}

/// What a saving action did, as its redirect or its 409 page.
fn saved(
    result: Result<Saved, ApplicationError>,
    done: &str,
    conflict: impl FnOnce(Box<Snapshot>) -> Result<Response, PageError>,
) -> Result<Response, PageError> {
    match result {
        Ok(Saved::New(head)) => {
            Ok(redirect(&format!("/admin/applications/{}?done={done}", head.revision.reference.id)))
        }
        Ok(Saved::Unchanged(head)) => {
            Ok(redirect(&format!("/admin/applications/{}?done=unchanged", head.revision.reference.id)))
        }
        Err(ApplicationError::Conflict { head }) => conflict(head),
        Err(error) => Err(failed(error)),
    }
}

const NO_CAUSE: &str = "Say why: the parser read the PDF wrong, or the merchant typed it wrong. Nothing was saved.";

/// `POST /admin/applications/{id}`: the corrections on a form rendered from `base_revision`.
async fn save(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    require(&user, Role::Reviewer)?;
    let applications = service(&app)?;
    let id = application_id(&id)?;
    let fields = fields(form);
    fields.check_csrf(&user)?;
    let base_ref = base_of(&fields, id)?;
    let (base, (upload, earlier)) = blocking(|| Ok((applications.at(base_ref)?, applications.upload_of(id)?)))?;
    let (submission, mut problems) = form::read_submission(&fields, &base);
    if submission.changes.is_empty() && problems.is_empty() {
        return Ok(redirect(&format!("/admin/applications/{id}?done=unchanged")));
    }
    let mut field_problems = BTreeMap::new();
    let edits = match Edits::read(base.record(), &submission.inputs(), now().date()) {
        Ok(edits) => Some(edits),
        Err(refused) => {
            for (field, why) in refused {
                let message = text::edit_refusal(field, why);
                problems.push(message.clone());
                field_problems.insert(field, message);
            }
            None
        }
    };
    if submission.cause.is_none() {
        problems.push(NO_CAUSE.to_string());
    }
    let (Some(edits), Some(cause), true) = (edits, submission.cause, problems.is_empty()) else {
        let mut shown = Shown::new(&user, &base, &upload, earlier);
        shown.submitted = Some(&submission);
        shown.problems = problems;
        shown.field_problems = field_problems;
        return Ok((StatusCode::UNPROCESSABLE_ENTITY, application_page(&shown)).into_response());
    };
    let reason = Some(submission.reason.as_str());
    let result = tokio::task::block_in_place(|| applications.correct(base_ref, &edits, cause, reason, user.id));
    saved(result, "saved", |head| {
        let theirs = form::differences(&base.record().resolve(), &head.record().resolve());
        let yours: Vec<String> =
            submission.changes.iter().map(|(field, change)| form::change_text(*field, change)).collect();
        let mut shown = Shown::new(&user, &head, &upload, earlier);
        shown.submitted = Some(&submission);
        shown.notices.push(html! {
            div.error {
                p {
                    "Changed by " (head.revision.author) ": revision " (head.revision.reference.revision) " was saved at "
                    (shown_time(head.revision.saved_at)) " while you edited revision " (base_ref.revision) ". Nothing of yours was saved."
                }
                h3 { "Their change" }
                ul { @for line in &theirs { li { (line) } } @if theirs.is_empty() { li { "No field changed." } } }
                h3 { "Your unsaved change" }
                ul { @for line in &yours { li { (line) } } }
                p { "The form below shows revision " (head.revision.reference.revision) " with your change typed in again; an SSN or a date of birth you typed must be typed again." }
            }
        });
        Ok((StatusCode::CONFLICT, application_page(&shown)).into_response())
    })
}

/// `POST /admin/applications/{id}/remove-second-owner`, from the form's button: one revision that
/// empties every secondary-owner field, with the form's cause and reason.
async fn remove_second_owner(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    require(&user, Role::Reviewer)?;
    let applications = service(&app)?;
    let id = application_id(&id)?;
    let fields = fields(form);
    fields.check_csrf(&user)?;
    let base_ref = base_of(&fields, id)?;
    let (base, (upload, earlier)) = blocking(|| Ok((applications.at(base_ref)?, applications.upload_of(id)?)))?;
    let (submission, _) = form::read_submission(&fields, &base);
    let elsewhere =
        submission.changes.iter().any(|(field, _)| !matches!(field, FieldId::Owner(OwnerSlot::Secondary, _)));
    let problem = if elsewhere {
        Some("Save or undo your other changes before removing the second owner. Nothing was saved.")
    } else if submission.cause.is_none() {
        Some(NO_CAUSE)
    } else {
        None
    };
    let (None, Some(cause)) = (problem, submission.cause) else {
        let mut shown = Shown::new(&user, &base, &upload, earlier);
        shown.submitted = Some(&submission);
        shown.problems = problem.into_iter().map(str::to_string).collect();
        return Ok((StatusCode::UNPROCESSABLE_ENTITY, application_page(&shown)).into_response());
    };
    let reason = Some(submission.reason.as_str());
    let result = tokio::task::block_in_place(|| {
        applications.correct(base_ref, &Edits::remove_second_owner(), cause, reason, user.id)
    });
    saved(result, "removed", |head| Err(failed(ApplicationError::Conflict { head })))
}

/// `POST /admin/applications/{id}/confirm`: a person confirms that a hand-entry draft is an
/// application.
async fn confirm(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    require(&user, Role::Reviewer)?;
    let applications = service(&app)?;
    let id = application_id(&id)?;
    let fields = fields(form);
    fields.check_csrf(&user)?;
    let base_ref = base_of(&fields, id)?;
    let result = tokio::task::block_in_place(|| applications.confirm_application(base_ref, user.id));
    saved(result, "confirmed", |head| Err(failed(ApplicationError::Conflict { head })))
}

/// `POST /admin/applications/{id}/matches`: a person's first match of revision `base_revision`,
/// with `product`, an optional `analysis_package_id` and the review form's `confirm.*` choices.
pub async fn create_match(
    State(app): State<Shared>,
    user: AdminUser,
    Path(id): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    require(&user, Role::Reviewer)?;
    let id = application_id(&id)?;
    let fields = fields(form);
    fields.check_csrf(&user)?;
    let revision =
        fields.get("base_revision").parse().map_err(|_| unprocessable("Name the application revision to match."))?;
    let analysis_package = match fields.get("analysis_package_id").trim() {
        "" => None,
        text => Some(Uuid::parse_str(text).map_err(|_| unprocessable("The analysis package id is not a UUID."))?),
    };
    let product = Product::from_key(fields.get("product")).ok_or_else(|| unprocessable("Choose a product."))?;
    let industries = app.read(|tx| tx.industries())?;
    let (confirmations, problems) = confirmations(&fields, &industries, &user);
    if let Some(problem) = problems.first() {
        return Err(unprocessable(problem));
    }
    let command = MatchCommand {
        analysis_package,
        product,
        application: ApplicationInput::Stored(ApplicationRef { id, revision }),
        confirmations,
        waivers: Vec::new(),
    };
    match app.matcher.run(Requester::Person { user: user.id, supersedes: None }, command).await {
        Ok(record) => Ok(redirect(&format!("/admin/matches/{}", record.id))),
        Err(error) => Err(refused(error)),
    }
}
