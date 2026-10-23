//! The admin pages: server-rendered HTML forms behind a session cookie. Every POST carries the
//! session's CSRF token, and a request that carries `Authorization` is refused.

mod lender;
mod review;

use std::collections::{BTreeMap, BTreeSet};

use axum::extract::{FromRequestParts, Path, Query, State};
use axum::http::header::{AUTHORIZATION, CACHE_CONTROL, CONTENT_SECURITY_POLICY, COOKIE, LOCATION, SET_COOKIE};
use axum::http::request::Parts;
use axum::http::{HeaderMap, HeaderValue, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Form, Router};
use maud::{DOCTYPE, Markup, html};
use serde::Deserialize;

use super::Shared;
use crate::criteria::{LenderId, LenderStatus, NoteKind};
use crate::info_hub::{ActionReport, CellOutcome, ImportReport, Reading, parse_report};
use crate::store::auth::{AdminUser, Role, random_secret};
use crate::store::{Author, Revision, StoreError};

const SESSION_COOKIE: &str = "lm_session";
const LOGIN_COOKIE: &str = "lm_login";

pub fn router() -> Router<Shared> {
    Router::new()
        .route("/", get(|| async { redirect("/admin") }))
        .route("/login", get(login_page).post(login))
        .route("/logout", post(logout))
        .route("/admin", get(lenders))
        .route("/admin/lenders/new", get(lender::new_page).post(lender::create))
        .route("/admin/lenders/{id}", get(lender::view))
        .route("/admin/lenders/{id}/edit", get(lender::edit_page).post(lender::edit))
        .route("/admin/lenders/{id}/history", get(lender::history))
        .route("/admin/lenders/{id}/activate", get(lender::activate_page).post(lender::activate))
        .route("/admin/lenders/{id}/pause", post(lender::pause))
        .route("/admin/industries", get(industries).post(add_industry))
        .route("/admin/industries/{slug}", post(set_industry))
        .route("/admin/imports", get(imports))
        .route("/admin/imports/{run}", get(import_run))
        .route("/admin/matches", get(matches))
        .route("/admin/matches/{id}", get(review::view))
        .route("/admin/matches/{id}/review", post(review::submit))
        .layer(axum::middleware::map_response(|mut response: Response| async move {
            let headers = response.headers_mut();
            headers.insert(CACHE_CONTROL, HeaderValue::from_static("no-store"));
            headers.insert(
                CONTENT_SECURITY_POLICY,
                HeaderValue::from_static(
                    "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'",
                ),
            );
            headers.insert("referrer-policy", HeaderValue::from_static("no-referrer"));
            response
        }))
}

/// A page that is not the one asked for: a redirect, a refusal or an error, already rendered.
pub struct PageError(Box<Response>);

impl IntoResponse for PageError {
    fn into_response(self) -> Response {
        *self.0
    }
}

impl From<StoreError> for PageError {
    fn from(error: StoreError) -> Self {
        super::log_error("admin store", &error);
        PageError::status(StatusCode::INTERNAL_SERVER_ERROR, "The server could not answer this request.")
    }
}

impl PageError {
    pub fn status(status: StatusCode, message: &str) -> PageError {
        PageError(Box::new((status, page(None, "Error", html! { p.error { (message) } })).into_response()))
    }

    pub fn not_found() -> PageError {
        PageError::status(StatusCode::NOT_FOUND, "Nothing is at this address.")
    }
}

pub fn redirect(to: &str) -> Response {
    (StatusCode::SEE_OTHER, [(LOCATION, to.to_string())]).into_response()
}

fn cookie(headers: &HeaderMap, name: &str) -> Option<String> {
    headers.get_all(COOKIE).iter().filter_map(|value| value.to_str().ok()).flat_map(|value| value.split(';')).find_map(
        |pair| {
            let (key, value) = pair.trim().split_once('=')?;
            (key == name && !value.is_empty()).then(|| value.to_string())
        },
    )
}

impl FromRequestParts<Shared> for AdminUser {
    type Rejection = PageError;

    async fn from_request_parts(parts: &mut Parts, app: &Shared) -> Result<Self, Self::Rejection> {
        if parts.headers.contains_key(AUTHORIZATION) {
            return Err(PageError::status(StatusCode::UNAUTHORIZED, "The admin pages take a signed-in session only."));
        }
        let Some(session) = cookie(&parts.headers, SESSION_COOKIE) else {
            return Err(PageError(Box::new(redirect("/login"))));
        };
        app.read(|tx| tx.session(&session))?.ok_or_else(|| PageError(Box::new(redirect("/login"))))
    }
}

pub fn require(user: &AdminUser, role: Role) -> Result<(), PageError> {
    if user.can(role) {
        Ok(())
    } else {
        Err(PageError::status(StatusCode::FORBIDDEN, &format!("This needs the {} role.", role.key())))
    }
}

/// A submitted form: every field in order, a name possibly repeated.
pub struct Fields(Vec<(String, String)>);

impl Fields {
    pub fn get(&self, name: &str) -> &str {
        self.0.iter().find(|(key, _)| key == name).map_or("", |(_, value)| value.as_str())
    }

    pub fn all(&self, name: &str) -> Vec<String> {
        self.0.iter().filter(|(key, _)| key == name).map(|(_, value)| value.clone()).collect()
    }

    pub fn has(&self, name: &str) -> bool {
        self.0.iter().any(|(key, _)| key == name)
    }

    /// The row numbers `n` of fields named `<prefix>.<n>.…`, ascending.
    pub fn rows(&self, prefix: &str) -> Vec<usize> {
        let rows: BTreeSet<usize> = self
            .0
            .iter()
            .filter_map(|(key, _)| key.strip_prefix(prefix)?.strip_prefix('.')?.split('.').next()?.parse().ok())
            .collect();
        rows.into_iter().collect()
    }

    pub fn check_csrf(&self, user: &AdminUser) -> Result<(), PageError> {
        if user.csrf_matches(self.get("csrf")) {
            Ok(())
        } else {
            Err(PageError::status(
                StatusCode::FORBIDDEN,
                "This form is stale or was not sent from these pages. Reload and try again.",
            ))
        }
    }
}

pub type RawForm = Form<Vec<(String, String)>>;

pub fn fields(Form(pairs): RawForm) -> Fields {
    Fields(pairs)
}

const STYLE: &str = "body{font:15px/1.45 system-ui,sans-serif;margin:0;color:#1d1d1f;background:#fafafa}\
header{background:#22313f;color:#fff;padding:.6em 1.2em;display:flex;gap:1.2em;align-items:center;flex-wrap:wrap}\
header a{color:#fff}header form{margin-left:auto}main{padding:1em 1.2em;max-width:72em}\
table{border-collapse:collapse;margin:.5em 0 1em;background:#fff}td,th{border:1px solid #ccd;padding:.3em .5em;text-align:left;vertical-align:top}\
th{background:#eef}fieldset{border:1px solid #ccd;margin:1em 0;background:#fff}legend{font-weight:600}\
.error{background:#fde8e8;border:1px solid #c33;padding:.5em;color:#800}.note{color:#555}\
.badge{display:inline-block;border-radius:3px;padding:0 .4em;margin:0 .2em;font-size:85%;background:#ffe7b3}\
.match{background:#d4f5dd}.review{background:#ffe7b3}.no_match{background:#f9d0d0}\
.removed{color:#900}.added{color:#060}input[type=text],textarea,select{font:inherit}textarea{width:100%}\
.row{border-top:1px dashed #ccd;padding:.4em 0}";

pub fn page(user: Option<&AdminUser>, title: &str, body: Markup) -> Markup {
    html! {
        (DOCTYPE)
        html lang="en" {
            head {
                meta charset="utf-8";
                meta name="viewport" content="width=device-width, initial-scale=1";
                title { (title) " | Lender matching" }
                style { (STYLE) }
            }
            body {
                header {
                    strong { "Lender matching" }
                    @if let Some(user) = user {
                        a href="/admin" { "Lenders" }
                        a href="/admin?attention=1" { "Needs attention" }
                        a href="/admin/industries" { "Industries" }
                        a href="/admin/imports" { "Imports" }
                        a href="/admin/matches" { "Matches" }
                        form method="post" action="/logout" {
                            (csrf(user))
                            span { (user.username) " (" (user.role.key()) ") " }
                            button { "Sign out" }
                        }
                    }
                }
                main {
                    h1 { (title) }
                    (body)
                }
            }
        }
    }
}

pub fn csrf(user: &AdminUser) -> Markup {
    html! { input type="hidden" name="csrf" value=(user.csrf); }
}

pub fn errors(list: &[String]) -> Markup {
    html! {
        @if !list.is_empty() {
            div.error {
                p { "Nothing was saved:" }
                ul { @for error in list { li { (error) } } }
            }
        }
    }
}

fn session_cookie(value: &str, max_age: i64, secure: bool) -> HeaderValue {
    let secure = if secure { "; Secure" } else { "" };
    HeaderValue::from_str(&format!(
        "{SESSION_COOKIE}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}{secure}"
    ))
    .expect("cookie values are base64url")
}

fn login_form(token: &str, failed: bool) -> Markup {
    page(
        None,
        "Sign in",
        html! {
            @if failed { p.error { "Wrong username or password." } }
            form method="post" action="/login" {
                input type="hidden" name="csrf" value=(token);
                p { label { "Username " input type="text" name="username" autocomplete="username" required; } }
                p { label { "Password " input type="password" name="password" autocomplete="current-password" required; } }
                button { "Sign in" }
            }
        },
    )
}

/// Sign-in has no session yet, so its CSRF token is a cookie the form echoes.
async fn login_page(State(app): State<Shared>, headers: HeaderMap) -> Result<Response, PageError> {
    if headers.contains_key(AUTHORIZATION) {
        return Err(PageError::status(StatusCode::UNAUTHORIZED, "The admin pages take a signed-in session only."));
    }
    let token = random_secret();
    let secure = if app.secure_cookies { "; Secure" } else { "" };
    let cookie = format!("{LOGIN_COOKIE}={token}; Path=/login; HttpOnly; SameSite=Strict; Max-Age=3600{secure}");
    Ok(([(SET_COOKIE, cookie)], login_form(&token, false)).into_response())
}

async fn login(State(app): State<Shared>, headers: HeaderMap, form: RawForm) -> Result<Response, PageError> {
    if headers.contains_key(AUTHORIZATION) {
        return Err(PageError::status(StatusCode::UNAUTHORIZED, "The admin pages take a signed-in session only."));
    }
    let form = fields(form);
    let expected = cookie(&headers, LOGIN_COOKIE).unwrap_or_default();
    if expected.is_empty() || !crate::store::auth::constant_time_eq(expected.as_bytes(), form.get("csrf").as_bytes()) {
        return Err(PageError::status(
            StatusCode::FORBIDDEN,
            "The sign-in form is stale. Reload the page and try again.",
        ));
    }
    let username = form.get("username").trim().to_string();
    let password = form.get("password").to_string();
    match app.write(|tx| tx.sign_in(&username, &password))? {
        Some(session) => {
            let mut response = redirect("/admin");
            response.headers_mut().append(SET_COOKIE, session_cookie(&session.cookie, 12 * 3600, app.secure_cookies));
            Ok(response)
        }
        None => Ok((StatusCode::UNAUTHORIZED, login_form(&expected, true)).into_response()),
    }
}

async fn logout(
    State(app): State<Shared>,
    user: AdminUser,
    headers: HeaderMap,
    form: RawForm,
) -> Result<Response, PageError> {
    fields(form).check_csrf(&user)?;
    if let Some(session) = cookie(&headers, SESSION_COOKIE) {
        app.write(|tx| tx.sign_out(&session))?;
    }
    let mut response = redirect("/login");
    response.headers_mut().append(SET_COOKIE, session_cookie("", 0, app.secure_cookies));
    Ok(response)
}

/// What an admin should look at before trusting a lender's verdicts.
pub fn attention(head: &Revision, reports: &BTreeMap<i64, ImportReport>) -> Vec<String> {
    let record = &head.record;
    let mut badges = Vec::new();
    match record.policy.status() {
        LenderStatus::Draft => badges.push("draft".to_string()),
        LenderStatus::Paused => badges.push("paused".to_string()),
        LenderStatus::Active => {}
    }
    let conditions = record.policy.notes().iter().filter(|note| note.kind == NoteKind::Condition).count();
    if conditions > 0 {
        badges.push(format!("{conditions} condition note{}", if conditions == 1 { "" } else { "s" }));
    }
    if record.policy.rules().is_empty() {
        badges.push("no rules".to_string());
    }
    if record.profile.bucket.is_none() {
        badges.push("no bucket".to_string());
    }
    if record.profile.submission.is_none() {
        badges.push("no submission channel".to_string());
    }
    if let Author::Import(run) = head.author
        && let Some(row) = reports.get(&run).and_then(|report| import_row(report, &head.lender))
        && row.uses_default_reading()
    {
        badges.push("unconfirmed default reading".to_string());
    }
    badges
}

pub fn import_row<'a>(report: &'a ImportReport, lender: &LenderId) -> Option<&'a crate::info_hub::RowReport> {
    report.rows.iter().find(|row| row.lender.as_ref() == Some(lender))
}

pub fn reports(app: &Shared) -> Result<BTreeMap<i64, ImportReport>, StoreError> {
    let runs = app.read(|tx| tx.import_runs())?;
    runs.into_iter().map(|run| Ok((run.id, parse_report(&run.report)?))).collect()
}

#[derive(Deserialize)]
struct ListQuery {
    attention: Option<String>,
}

async fn lenders(
    State(app): State<Shared>,
    user: AdminUser,
    Query(query): Query<ListQuery>,
) -> Result<Markup, PageError> {
    let heads = app.read(|tx| tx.heads())?;
    let reports = reports(&app)?;
    let only_attention = query.attention.is_some();
    let rows: Vec<(Revision, Vec<String>)> = heads
        .into_iter()
        .map(|head| {
            let badges = attention(&head, &reports);
            (head, badges)
        })
        .filter(|(_, badges)| !only_attention || !badges.is_empty())
        .collect();
    let title = if only_attention { "Lenders that need attention" } else { "Lenders" };
    Ok(page(
        Some(&user),
        title,
        html! {
            @if user.can(Role::Editor) { p { a href="/admin/lenders/new" { "Add a lender" } } }
            table {
                tr { th { "Lender" } th { "Status" } th { "Bucket" } th { "Revision" } th { "Last saved by" } th { "Attention" } }
                @for (head, badges) in &rows {
                    tr {
                        td { a href={ "/admin/lenders/" (head.lender) } { (head.record.profile.name) } }
                        td { (head.record.policy.status().key()) }
                        td { @match head.record.profile.bucket { Some(bucket) => (bucket.number()), None => "unassigned" } }
                        td { (head.number) }
                        td { (author(&head.author)) " " span.note { (shown_time(head.saved_at)) } }
                        td { @for badge in badges { span.badge { (badge) } } }
                    }
                }
            }
            p.note { (rows.len()) " lenders." }
        },
    ))
}

/// To the minute, in UTC.
pub fn shown_time(time: time::OffsetDateTime) -> String {
    time.format(time::macros::format_description!("[year]-[month]-[day] [hour]:[minute] UTC"))
        .expect("a UTC time formats")
}

pub fn author(author: &Author) -> String {
    match author {
        Author::User { username, .. } => username.clone(),
        Author::Import(run) => format!("Info Hub import #{run}"),
    }
}

async fn industries(State(app): State<Shared>, user: AdminUser) -> Result<Markup, PageError> {
    let industries = app.read(|tx| tx.industries())?;
    Ok(page(
        Some(&user),
        "Industries",
        html! {
            p.note { "Rules name industries by id, so an industry is retired rather than deleted. A retired industry stays in the rules that name it and is refused in new match requests." }
            table {
                tr { th { "Label" } th { "Id" } th { "State" } @if user.can(Role::Editor) { th {} } }
                @for industry in industries.all() {
                    tr {
                        td { (industry.label) }
                        td { code { (industry.id) } }
                        td { @if industry.retired { "retired" } @else { "active" } }
                        @if user.can(Role::Editor) {
                            td {
                                form method="post" action={ "/admin/industries/" (industry.id) } {
                                    (csrf(&user))
                                    @if industry.retired {
                                        button name="retired" value="false" { "Restore" }
                                    } @else {
                                        button name="retired" value="true" { "Retire" }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            @if user.can(Role::Editor) {
                form method="post" action="/admin/industries" {
                    (csrf(&user))
                    label { "New industry " input type="text" name="label" required; }
                    " " button { "Add" }
                }
            }
        },
    ))
}

async fn add_industry(State(app): State<Shared>, user: AdminUser, form: RawForm) -> Result<Response, PageError> {
    require(&user, Role::Editor)?;
    let form = fields(form);
    form.check_csrf(&user)?;
    let label = form.get("label").trim().to_string();
    if !label.is_empty() {
        app.write(|tx| tx.add_industry(&label))?;
    }
    Ok(redirect("/admin/industries"))
}

async fn set_industry(
    State(app): State<Shared>,
    user: AdminUser,
    Path(slug): Path<String>,
    form: RawForm,
) -> Result<Response, PageError> {
    require(&user, Role::Editor)?;
    let form = fields(form);
    form.check_csrf(&user)?;
    let retired = form.get("retired") == "true";
    if !app.write(|tx| tx.set_industry_retired(&slug, retired))? {
        return Err(PageError::not_found());
    }
    Ok(redirect("/admin/industries"))
}

async fn imports(State(app): State<Shared>, user: AdminUser) -> Result<Markup, PageError> {
    let reports = reports(&app)?;
    Ok(page(
        Some(&user),
        "Info Hub imports",
        html! {
            p.note { "Run " code { "lender-matching import-info-hub <workbook> --apply" } " on the server host to import. Only applied runs are listed." }
            table {
                tr { th { "Run" } th { "When" } th { "Rows" } th { "Created" } th { "Updated" } th { "Kept admin edits" } }
                @for (id, report) in reports.iter().rev() {
                    tr {
                        td { a href={ "/admin/imports/" (id) } { "#" (id) } }
                        td { (shown_time(report.run_at)) }
                        td { (report.rows.len()) }
                        td { (report.count(|a| matches!(a, ActionReport::Create))) }
                        td { (report.count(|a| matches!(a, ActionReport::Update { .. }))) }
                        td { (report.count(|a| matches!(a, ActionReport::KeptAdminEdits { .. }))) }
                    }
                }
            }
        },
    ))
}

pub fn cell_outcome(outcome: &CellOutcome) -> String {
    let reading = |reading: &Reading| match reading {
        Reading::Exact => String::new(),
        Reading::Mapped(how) => format!(" (mapped: {how})"),
        Reading::Default(how) => format!(" (default: {how})"),
    };
    let ids = |ids: &[crate::criteria::RuleId]| ids.iter().map(ToString::to_string).collect::<Vec<_>>().join(", ");
    match outcome {
        CellOutcome::Empty => "no requirement".to_string(),
        CellOutcome::Rules { ids: rules, reading: how } => format!("rules {}{}", ids(rules), reading(how)),
        CellOutcome::Note { id, note } => format!("{} note {id}", note.key()),
        CellOutcome::Profile => "profile".to_string(),
        CellOutcome::NoRule { why } => format!("no rule: {why}"),
        CellOutcome::PartlyRead { ids: rules, unread } => {
            format!("rules {}; condition note {unread} for the rest", ids(rules))
        }
        CellOutcome::Unread { note } => format!("not read; condition note {note} quotes it"),
    }
}

async fn import_run(State(app): State<Shared>, user: AdminUser, Path(run): Path<i64>) -> Result<Markup, PageError> {
    let report = app.read(|tx| tx.import_run(run))?.ok_or_else(PageError::not_found)?;
    let report = parse_report(&report.report)?;
    Ok(page(
        Some(&user),
        &format!("Info Hub import #{run}"),
        html! {
            ul { @for line in report.lines().iter().take(2) { li { (line) } } }
            p.note { "Source SHA-256 " code { (report.source_sha256) } }
            @for row in &report.rows {
                h3 {
                    "Line " (row.line) ": "
                    @if let Some(lender) = &row.lender { a href={ "/admin/lenders/" (lender) } { (row.name) } } @else { (row.name) }
                    " " span.note { (row.action.to_string()) }
                    @if row.no_criteria { span.badge { "no criteria" } }
                }
                table {
                    tr { th { "Column" } th { "Cell" } th { "Became" } }
                    @for cell in row.cells.iter().filter(|cell| cell.raw.is_some()) {
                        tr { td { (cell.column.header()) } td { (cell.raw.as_deref().unwrap_or("")) } td { (cell_outcome(&cell.outcome)) } }
                    }
                }
            }
            @if !report.not_in_sheet.is_empty() {
                h3 { "Not in the sheet (kept)" }
                ul { @for missing in &report.not_in_sheet { li { a href={ "/admin/lenders/" (missing.lender) } { (missing.name) } } } }
            }
        },
    ))
}

async fn matches(State(app): State<Shared>, user: AdminUser) -> Result<Markup, PageError> {
    let recent = app.read(|tx| tx.recent_matches(100))?;
    Ok(page(
        Some(&user),
        "Recent matches",
        html! {
            table {
                tr { th { "Match" } th { "When" } th { "By" } th { "Match" } th { "Review" } th { "No match" } th {} }
                @for summary in &recent {
                    tr {
                        td { a href={ "/admin/matches/" (summary.id) } { code { (summary.id) } } }
                        td { (shown_time(summary.created_at)) }
                        td { (summary.by) }
                        td { (summary.matched) } td { (summary.review) } td { (summary.no_match) }
                        td { @if summary.superseded { span.note { "superseded" } } }
                    }
                }
            }
        },
    ))
}
