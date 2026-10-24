mod common;
#[path = "../application/tests/support/mod.rs"]
mod support;

use std::path::{Path, PathBuf};
use std::process::Output;
use std::time::Duration;

use base64::Engine;
use base64::engine::general_purpose::STANDARD;
use lender_matching_application::Rect;
use lender_matching_application::extract::{Document, read};
use lender_matching_application::pdf::PageImage;
use lender_matching_application::worker::PdfWorker;

use common::*;
use lender_matching_application::fields::{BusinessField, FieldId};
use reqwest::StatusCode;
use support::form::{Canvas, Form, certificate_of, sample_values};
use support::pdf::{FakePage, FakePdf};

const KEY: &str = "c2FtcGxlIGtleSBmb3IgYXBwbGljYXRpb25zIDEyMzQ=";
const OTHER_KEY: &str = "YW5vdGhlciBrZXksIG5vdCB0aGUgZmlyc3QgMTIzNDU=";
const ENVELOPE: &str = "0F8FAD5BD9CB469FA16570867728950E";

fn application(form: &Form, day: u8) -> Vec<u8> {
    let certificate = certificate_of(FakePage::new(), ENVELOPE, &[("SAMPLE OWNER", "owner@example.com")]);
    FakePdf::new(vec![form.draw(FakePage::new()), certificate]).created(2026, 10, day).to_bytes()
}

fn contract() -> Vec<u8> {
    let mut page = FakePage::new().text("TimesNewRomanPS-BoldMT", 12.0, 40.0, 40.0, "RECEIVABLES PURCHASE AGREEMENT");
    for line in 0..10 {
        page = page.text("ArialMT", 9.0, 40.0, 80.0 + 12.0 * line as f32, "SAMPLE TERMS OF THE AGREEMENT ARE HERE");
    }
    FakePdf::new(vec![page]).to_bytes()
}

fn import(data: &Path, files: &[PathBuf], by: &str, key: Option<&str>, library: Option<&Path>) -> Output {
    let mut command = command(data);
    command.env_remove("PDFIUM_LIBRARY").args(["applications", "import", "--by", by]).args(files);
    if let Some(key) = key {
        command.env("APPLICATION_DATA_KEY", key);
    }
    if let Some(library) = library {
        command.env("PDFIUM_LIBRARY", library);
    }
    command.output().unwrap()
}

fn text(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}

fn database_bytes(data: &Path) -> Vec<u8> {
    let mut bytes = Vec::new();
    for entry in std::fs::read_dir(data).unwrap() {
        let path = entry.unwrap().path();
        if path.file_name().unwrap().to_string_lossy().starts_with("lender-matching.sqlite3") {
            bytes.extend(std::fs::read(path).unwrap());
        }
    }
    bytes
}

#[test]
fn import_seals_each_application_and_prints_outcomes_without_a_value() {
    let Some(library) = support::pdfium_library() else { return };
    let data = TempDir::new();
    let inbox = TempDir::new();
    add_user(data.path(), "sample.reviewer", "reviewer");
    add_user(data.path(), "sample.viewer", "viewer");
    let unknown = Form { omit: vec!["Secondary Owner Name"], ..Form::word() };
    let documents: Vec<(&str, Vec<u8>)> = vec![
        ("CONTOSO application.pdf", application(&Form::word(), 21)),
        ("CONTOSO application copy.pdf", application(&Form::word(), 21)),
        ("CONTOSO second file.pdf", application(&Form::word(), 22)),
        ("FABRIKAM contract.pdf", contract()),
        ("SAMPLE broken.pdf", b"SAMPLE OWNER 900-12-3456, not a PDF".to_vec()),
        ("NORTHWIND scan.pdf", application(&unknown, 21)),
    ];
    let files: Vec<PathBuf> = documents
        .iter()
        .map(|(name, bytes)| {
            let path = inbox.path().join(name);
            std::fs::write(&path, bytes).unwrap();
            path
        })
        .collect();

    let keyless = import(data.path(), &files, "sample.reviewer", None, Some(&library));
    assert!(!keyless.status.success() && text(&keyless.stderr).contains("set APPLICATION_DATA_KEY"));
    let malformed = import(data.path(), &files, "sample.reviewer", Some("c2FtcGxl"), Some(&library));
    let stderr = text(&malformed.stderr);
    assert!(!malformed.status.success() && stderr.contains("APPLICATION_DATA_KEY must be 32 bytes in base64"));
    assert!(!stderr.contains("c2FtcGxl"), "the key is never printed");
    let viewer = import(data.path(), &files, "sample.viewer", Some(KEY), Some(&library));
    assert!(!viewer.status.success() && text(&viewer.stderr).contains("no live reviewer or editor account"));
    let no_pdfium = import(data.path(), &files, "sample.reviewer", Some(KEY), None);
    assert!(!no_pdfium.status.success() && text(&no_pdfium.stderr).contains("set PDFIUM_LIBRARY"));

    let output = import(data.path(), &files, "sample.reviewer", Some(KEY), Some(&library));
    let stdout = text(&output.stdout);
    assert!(!output.status.success(), "a file that could not be read fails the run");
    let lines: Vec<&str> = stdout.lines().collect();
    assert_eq!(lines.len(), 6, "{stdout}");
    let id = |line: &str| line.split_whitespace().nth(2).unwrap().trim_end_matches(';').to_string();
    let first = id(lines[0]);
    assert_eq!(lines[0], format!("1: stored {first}"));
    assert_eq!(lines[1], format!("2: already stored as {first}"));
    assert!(lines[2].starts_with("3: stored ") && lines[2].ends_with(&format!("; {first} is from the same envelope")));
    assert_eq!(lines[3], "4: refused: contract");
    assert_eq!(lines[4], "5: not stored: the PDF could not be read: not_pdf");
    let draft = format!(
        "6: stored {} as a manual-entry draft (unknown_layout); {first} is from the same envelope",
        id(lines[5])
    );
    assert_eq!(lines[5], draft);

    let mut secrets: Vec<String> = sample_values().into_iter().map(|(_, value)| value.to_string()).collect();
    secrets.extend(["SAMPLE OWNER", "owner@example.com", "900-12-3456", ENVELOPE].map(String::from));
    let names: Vec<String> = documents.iter().map(|(name, _)| name.to_string()).collect();
    let database = database_bytes(data.path());
    for secret in secrets.iter().filter(|secret| secret.len() > 3) {
        assert!(
            !database.windows(secret.len()).any(|window| window == secret.as_bytes()),
            "the database holds {secret}"
        );
    }
    for secret in secrets.iter().chain(&names).filter(|secret| secret.len() > 3) {
        for (what, printed) in [("stdout", &stdout), ("stderr", &text(&output.stderr))] {
            assert!(!printed.contains(secret.as_str()), "{what} holds {secret}");
        }
    }

    let other_key = import(data.path(), &files[..1], "sample.reviewer", Some(OTHER_KEY), Some(&library));
    assert!(!other_key.status.success());
    assert!(
        text(&other_key.stderr).contains("APPLICATION_DATA_KEY is not the key that sealed the stored applications")
    );
}

#[test]
fn the_pdf_worker_refuses_the_data_key_and_a_data_directory() {
    let data = TempDir::new();
    let with_key = command(data.path()).arg("pdf-worker").env("APPLICATION_DATA_KEY", KEY).output().unwrap();
    assert!(
        !with_key.status.success()
            && text(&with_key.stderr).contains("neither APPLICATION_DATA_KEY nor a data directory")
    );
    assert!(!text(&with_key.stderr).contains(KEY));
    let with_data_dir = command(data.path()).arg("pdf-worker").output().unwrap();
    assert!(!with_data_dir.status.success(), "command() passes --data-dir");
}

fn stored_id(line: &str) -> String {
    line.split_whitespace().nth(2).unwrap().trim_end_matches(';').to_string()
}

fn post_fields(csrf: &str, changes: &[(&str, &str)]) -> Vec<(String, String)> {
    let mut fields = vec![("csrf".to_string(), csrf.to_string())];
    fields.extend(changes.iter().map(|(name, value)| (name.to_string(), value.to_string())));
    fields
}

#[tokio::test(flavor = "multi_thread")]
async fn a_stored_application_is_matched_through_the_pages_and_the_server_logs_no_value() {
    let Some(library) = support::pdfium_library() else { return };
    let data = TempDir::new();
    let inbox = TempDir::new();
    add_user(data.path(), "sample.reviewer", "reviewer");
    add_user(data.path(), "sample.viewer", "viewer");
    let token = token(data.path(), "dashboard", &["read"]);
    let application_pdf = inbox.path().join("CONTOSO application.pdf");
    std::fs::write(&application_pdf, application(&Form::word(), 21)).unwrap();
    let draft_pdf = inbox.path().join("NORTHWIND scan.pdf");
    std::fs::write(&draft_pdf, application(&Form { omit: vec!["Secondary Owner Name"], ..Form::word() }, 22)).unwrap();
    let imported = import(data.path(), &[application_pdf, draft_pdf], "sample.reviewer", Some(KEY), Some(&library));
    let lines: Vec<String> = text(&imported.stdout).lines().map(str::to_string).collect();
    let (id, draft) = (stored_id(&lines[0]), stored_id(&lines[1]));
    let matches = format!("/admin/applications/{id}/matches");
    let fields = |csrf: &str, revision: &str| {
        post_fields(csrf, &[("base_revision", revision), ("product", "mca"), ("confirm.home_based", "no")])
    };

    let refused = command(data.path())
        .args(["serve", "--bind", "127.0.0.1:0"])
        .env("APPLICATION_DATA_KEY", OTHER_KEY)
        .output()
        .unwrap();
    assert!(!refused.status.success() && text(&refused.stderr).contains("is not the key that sealed"));

    let keyless = Server::start(data.path(), &[]);
    assert!(keyless.log().contains("no APPLICATION_DATA_KEY is set; stored applications answer 503"));
    let reviewer = Browser::new(&keyless);
    reviewer.sign_in("sample.reviewer").await;
    let csrf = csrf_of(&reviewer.get("/admin/matches").await);
    assert_eq!(reviewer.post(&matches, &fields(&csrf, "1")).await.status, StatusCode::SERVICE_UNAVAILABLE);
    drop(keyless);

    let server = Server::start(data.path(), &[("APPLICATION_DATA_KEY", KEY)]);
    let reviewer = Browser::new(&server);
    reviewer.sign_in("sample.reviewer").await;
    let csrf = csrf_of(&reviewer.get("/admin/matches").await);
    let viewer = Browser::new(&server);
    viewer.sign_in("sample.viewer").await;
    let viewer_csrf = csrf_of(&viewer.get("/admin/matches").await);
    assert_eq!(viewer.post(&matches, &fields(&viewer_csrf, "1")).await.status, StatusCode::FORBIDDEN);
    assert_eq!(reviewer.post(&matches, &fields("forged", "1")).await.status, StatusCode::FORBIDDEN);
    assert_eq!(reviewer.post(&matches, &fields(&csrf, "2")).await.status, StatusCode::CONFLICT, "a stale revision");
    let draft_match = format!("/admin/applications/{draft}/matches");
    assert_eq!(
        reviewer.post(&draft_match, &fields(&csrf, "1")).await.status,
        StatusCode::CONFLICT,
        "an unconfirmed draft"
    );
    let unknown = format!("/admin/applications/{}/matches", uuid::Uuid::new_v4());
    assert_eq!(reviewer.post(&unknown, &fields(&csrf, "1")).await.status, StatusCode::NOT_FOUND);

    let made = reviewer.post(&matches, &fields(&csrf, "1")).await;
    assert_eq!(made.status, StatusCode::SEE_OTHER, "{}", made.body);
    let location = made.location.unwrap();
    let page = reviewer.get(&location).await;
    assert!(
        page.body.contains(&format!(
            "Stored application <a href=\"/admin/applications/{id}\"><code>{id}</code></a>, revision 1."
        )),
        "{}",
        page.body
    );
    assert!(page.body.contains("stated on the application"));
    let match_id = location.trim_start_matches("/admin/matches/");
    let review = format!("{location}/review");
    let reviewed = reviewer.submit(&page, &review, &[], None).await;
    assert_eq!(reviewed.status, StatusCode::SEE_OTHER, "{}", reviewed.body);
    let second = reviewer.get(reviewed.location.as_deref().unwrap()).await;
    assert!(second.body.contains(&format!(
        "Stored application <a href=\"/admin/applications/{id}\"><code>{id}</code></a>, revision 1."
    )));

    let response = http()
        .get(server.url(&format!("/api/v1/matches/{match_id}")))
        .header("Authorization", bearer(&token))
        .send()
        .await
        .unwrap();
    let body: lender_matching_wire::v1::MatchResponse = contract_body("MatchResponse", response).await;
    assert_eq!(body.supersedes, None, "a person's first match supersedes nothing");
    assert_eq!(
        body.created_by,
        lender_matching_wire::v1::CreatedBy::Person { username: "sample.reviewer".to_string() }
    );

    let log = server.log();
    let mut secrets: Vec<String> = sample_values().into_iter().map(|(_, value)| value.to_string()).collect();
    secrets.extend(["SAMPLE OWNER", "owner@example.com", ENVELOPE, KEY].map(String::from));
    for secret in secrets.iter().filter(|secret| secret.len() > 3) {
        assert!(!log.contains(secret.as_str()), "the server log holds {secret}");
        assert!(!database_bytes(data.path()).windows(secret.len()).any(|window| window == secret.as_bytes()));
    }
}

struct Pages {
    data: TempDir,
    server: Server,
    reviewer: Browser,
    viewer: Browser,
}

async fn pages(library: &Path) -> Pages {
    let data = TempDir::new();
    add_user(data.path(), "sample.reviewer", "reviewer");
    add_user(data.path(), "sample.editor", "editor");
    add_user(data.path(), "sample.viewer", "viewer");
    let library = library.to_str().unwrap();
    let server = Server::start(data.path(), &[("APPLICATION_DATA_KEY", KEY), ("PDFIUM_LIBRARY", library)]);
    let reviewer = Browser::new(&server);
    reviewer.sign_in("sample.reviewer").await;
    let viewer = Browser::new(&server);
    viewer.sign_in("sample.viewer").await;
    Pages { data, server, reviewer, viewer }
}

async fn upload(browser: &Browser, pdf: &[u8]) -> Page {
    let csrf = csrf_of(&browser.get("/admin/matches").await);
    browser.post_multipart("/admin/applications", &[("csrf", csrf.as_bytes()), ("pdf", pdf)]).await
}

/// The application page an upload redirected to.
fn stored_at(page: &Page) -> String {
    assert_eq!(page.status, StatusCode::SEE_OTHER, "{}", page.body);
    page.location.clone().unwrap().split('?').next().unwrap().to_string()
}

/// The HTML of the cell that labels `key`, up to the next cell or the end of its card.
fn cell<'a>(body: &'a str, key: &str) -> &'a str {
    let label = format!("for=\"f-{}\"", key.replace('.', "-"));
    let at = body.find(&label).unwrap_or_else(|| panic!("no cell for {key}"));
    let open = body[..at].rfind("<div class=\"field").unwrap();
    let rest = &body[at..];
    let end = [rest.find("<div class=\"field"), rest.find("</section>")].into_iter().flatten().min().unwrap();
    &body[open..at + end]
}

fn value_of(fields: &[(String, String)], name: &str) -> Option<String> {
    fields.iter().find(|(key, _)| key == name).map(|(_, value)| value.clone())
}

fn assert_no_secret(what: &str, text: &str, secrets: &[&str]) {
    for secret in secrets {
        assert!(!text.contains(secret), "{what} holds {secret}");
    }
}

const IDENTITY: [&str; 4] = ["900-12-3456", "900654321", "04/15/1980", "06/01/1975"];

#[tokio::test(flavor = "multi_thread")]
async fn an_upload_opens_its_form_and_a_duplicate_or_a_contract_stores_nothing_new() {
    let Some(library) = support::pdfium_library() else { return };
    let pages = pages(&library).await;
    let first = upload(&pages.reviewer, &application(&Form::word(), 21)).await;
    let path = stored_at(&first);
    let page = pages.reviewer.get(&path).await;
    assert_eq!(page.status, StatusCode::OK);
    assert!(page.body.contains("<h1>CONTOSO LLC</h1>") && page.body.contains("word"), "{}", page.body);
    assert!(page.headers["content-security-policy"].to_str().unwrap().contains("img-src 'self' data:"));

    let again = upload(&pages.reviewer, &application(&Form::word(), 21)).await;
    assert_eq!(again.location.as_deref(), Some(format!("{path}?existing=1").as_str()));
    assert!(pages.reviewer.get(again.location.as_deref().unwrap()).await.body.contains("uploaded already"));
    let sibling = stored_at(&upload(&pages.reviewer, &application(&Form::word(), 22)).await);
    assert_ne!(sibling, path);
    let sibling_page = pages.reviewer.get(&sibling).await;
    assert!(
        sibling_page.body.contains("same DocuSign envelope") && sibling_page.body.contains(&format!("href=\"{path}\""))
    );

    let refused = upload(&pages.reviewer, &contract()).await;
    assert_eq!(refused.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(refused.body.contains("reads as a Receivables Purchase Agreement, not an application. Nothing was saved."));
    let broken = upload(&pages.reviewer, b"SAMPLE OWNER, not a PDF").await;
    assert_eq!(broken.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(broken.body.contains("not a PDF"));
    let forged =
        pages.reviewer.post_multipart("/admin/applications", &[("csrf", b"forged"), ("pdf", &contract())]).await;
    assert_eq!(forged.status, StatusCode::FORBIDDEN);
    assert_eq!(upload(&pages.viewer, &application(&Form::word(), 23)).await.status, StatusCode::FORBIDDEN);

    let list = pages.viewer.get("/admin/applications").await;
    assert!(list.body.contains("2 applications."), "{}", list.body);
    assert!(list.body.contains(&format!("href=\"{path}\">CONTOSO LLC</a>")) && list.body.contains("SAMPLE OWNER"));
    assert!(!list.body.contains("Upload an application"), "a viewer cannot upload");
}

#[tokio::test(flavor = "multi_thread")]
async fn empty_required_fields_are_red_unread_ones_amber_and_identity_data_stays_masked() {
    let Some(library) = support::pdfium_library() else { return };
    let pages = pages(&library).await;
    let address = FieldId::Business(BusinessField::Address);
    let start = FieldId::Business(BusinessField::StartDate);
    let form = Form::word().clear(address).set(start, "13/45/2019");
    let path = stored_at(&upload(&pages.reviewer, &application(&form, 21)).await);

    let page = pages.reviewer.get(&path).await;
    let address = cell(&page.body, "business.address");
    assert!(address.starts_with("<div class=\"field required-empty\">"), "{address}");
    assert!(address.contains("Business Address<span class=\"star\">*</span>"));
    let start = cell(&page.body, "business.start_date");
    assert!(start.starts_with("<div class=\"field needs-review\">"), "{start}");
    assert!(start.contains("Could not read this as a date; write it as 04/15/2019 or 04/2019"));
    let fields = form_fields(&page.body, &path);
    assert_eq!(
        value_of(&fields, "f.business.start_date").as_deref(),
        Some("13/45/2019"),
        "a reviewer sees the PDF's text"
    );
    assert_eq!(value_of(&fields, "f.business.legal_name").as_deref(), Some("CONTOSO LLC"));
    assert_eq!(value_of(&fields, "f.principal.ssn").as_deref(), Some(""), "an SSN input is a blank replacement");
    assert!(cell(&page.body, "principal.ssn").contains("•••-••-3456"));
    assert!(cell(&page.body, "principal.birth_date").contains("Recorded"));
    assert!(cell(&page.body, "principal.ownership_percent").contains("value=\"50.00\" readonly"));
    assert!(page.body.contains("DocuSign check: matches the envelope's signer."));
    assert!(page.body.contains("1 required empty") && page.body.contains("1 needs review"));
    assert_no_secret("the reviewer's page", &page.body, &IDENTITY);

    let seen = pages.viewer.get(&path).await;
    assert!(!seen.body.contains("<form method=\"post\" action=\"/admin/applications/"), "a viewer gets no form");
    assert!(!seen.body.contains("13/45/2019"), "a viewer gets no unread text");
    assert!(!seen.body.contains("•••-••-") && cell(&seen.body, "principal.ssn").contains("Recorded"));
    assert_no_secret("the viewer's page", &seen.body, &IDENTITY);
}

#[tokio::test(flavor = "multi_thread")]
async fn a_correction_writes_only_changed_inputs_and_a_stale_form_shows_both_changes() {
    let Some(library) = support::pdfium_library() else { return };
    let pages = pages(&library).await;
    let path = stored_at(&upload(&pages.reviewer, &application(&Form::word(), 21)).await);
    let editor = Browser::new(&pages.server);
    editor.sign_in("sample.editor").await;
    let opened = pages.reviewer.get(&path).await;
    let stale = editor.get(&path).await;

    let unchanged = pages.reviewer.submit(&opened, &path, &[("cause", "reading")], None).await;
    assert_eq!(unchanged.location.as_deref(), Some(format!("{path}?done=unchanged").as_str()));
    let no_cause = pages.reviewer.submit(&opened, &path, &[("f.business.legal_name", "FABRIKAM LLC")], None).await;
    assert_eq!(no_cause.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(no_cause.body.contains("Say why"));
    let unreadable = pages
        .reviewer
        .submit(&opened, &path, &[("f.business.start_date", "13/45/2019"), ("cause", "merchant")], None)
        .await;
    assert_eq!(unreadable.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(unreadable.body.contains("Business Start Date: Could not read this as a date"));
    assert_eq!(
        value_of(&form_fields(&unreadable.body, &path), "f.business.start_date").as_deref(),
        Some("13/45/2019"),
        "the refused text is shown again"
    );

    let changes = [
        ("f.business.legal_name", "FABRIKAM LLC"),
        ("clear.business.dba", "on"),
        ("f.principal.ssn", "900-55-1234"),
        ("cause", "merchant"),
        ("reason", "SAMPLE OWNER confirmed by phone"),
    ];
    let saved = pages.reviewer.submit(&opened, &path, &changes, None).await;
    assert_eq!(saved.location.as_deref(), Some(format!("{path}?done=saved").as_str()), "{}", saved.body);
    let after = pages.reviewer.get(saved.location.as_deref().unwrap()).await;
    assert!(after.body.contains("Revision 2 ·") && after.body.contains("Saved."));
    let fields = form_fields(&after.body, &path);
    assert_eq!(value_of(&fields, "f.business.legal_name").as_deref(), Some("FABRIKAM LLC"));
    assert_eq!(value_of(&fields, "f.business.dba").as_deref(), Some(""));
    assert_eq!(value_of(&fields, "f.business.city").as_deref(), Some("AUSTIN"), "an unchanged input stays the PDF's");
    assert!(cell(&after.body, "principal.ssn").contains("•••-••-1234"));
    assert!(!after.body.contains("900-55-1234"));
    assert!(cell(&after.body, "business.legal_name").contains("name=\"parse.business.legal_name\""));
    assert!(!cell(&after.body, "business.city").contains("name=\"parse."), "only a person's value goes back");

    let conflict = editor.submit(&stale, &path, &[("f.business.city", "DALLAS"), ("cause", "reading")], None).await;
    assert_eq!(conflict.status, StatusCode::CONFLICT);
    assert!(conflict.body.contains("Changed by sample.reviewer: revision 2"));
    assert!(conflict.body.contains("Business Legal Name: CONTOSO LLC → FABRIKAM LLC"));
    assert!(conflict.body.contains("Principal SSN: changed"));
    assert!(conflict.body.contains("<li>Business City: DALLAS</li>"));
    assert_eq!(value_of(&form_fields(&conflict.body, &path), "f.business.city").as_deref(), Some("DALLAS"));
    let merged = editor.submit(&conflict, &path, &[], None).await;
    assert_eq!(merged.location.as_deref(), Some(format!("{path}?done=saved").as_str()), "{}", merged.body);
    let merged = editor.get(&path).await;
    let fields = form_fields(&merged.body, &path);
    assert!(merged.body.contains("Revision 3 ·"));
    assert_eq!(value_of(&fields, "f.business.legal_name").as_deref(), Some("FABRIKAM LLC"));
    assert_eq!(value_of(&fields, "f.business.city").as_deref(), Some("DALLAS"));

    let back = editor.submit(&merged, &path, &[("parse.business.legal_name", "on"), ("cause", "reading")], None).await;
    assert_eq!(back.status, StatusCode::SEE_OTHER);
    let back = editor.get(&path).await;
    assert_eq!(value_of(&form_fields(&back.body, &path), "f.business.legal_name").as_deref(), Some("CONTOSO LLC"));

    let mut secrets = IDENTITY.to_vec();
    secrets.extend(["900-55-1234", "SAMPLE OWNER confirmed by phone", "FABRIKAM LLC", "DALLAS"]);
    assert_no_secret("the server log", &pages.server.log(), &secrets);
    let database = database_bytes(pages.data.path());
    for secret in &secrets {
        assert!(
            !database.windows(secret.len()).any(|window| window == secret.as_bytes()),
            "the database holds {secret}"
        );
    }
}

#[tokio::test(flavor = "multi_thread")]
async fn removing_the_second_owner_gives_the_principal_all_of_it_and_a_draft_waits_for_confirmation() {
    let Some(library) = support::pdfium_library() else { return };
    let pages = pages(&library).await;
    let path = stored_at(&upload(&pages.reviewer, &application(&Form::word(), 21)).await);
    let page = pages.reviewer.get(&path).await;
    assert!(page.body.contains("Remove second owner"));
    let remove = format!("{path}/remove-second-owner");
    let mut fields = form_fields(&page.body, &path);
    let no_cause = pages.reviewer.post(&remove, &fields).await;
    assert_eq!(no_cause.status, StatusCode::UNPROCESSABLE_ENTITY);
    set(&mut fields, "f.business.city", "DALLAS");
    set(&mut fields, "cause", "merchant");
    let elsewhere = pages.reviewer.post(&remove, &fields).await;
    assert_eq!(elsewhere.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(elsewhere.body.contains("Save or undo your other changes"));
    set(&mut fields, "f.business.city", "AUSTIN");
    let removed = pages.reviewer.post(&remove, &fields).await;
    assert_eq!(removed.location.as_deref(), Some(format!("{path}?done=removed").as_str()), "{}", removed.body);
    let after = pages.reviewer.get(&path).await;
    assert!(cell(&after.body, "principal.ownership_percent").contains("value=\"100.00\""));
    assert!(cell(&after.body, "secondary.ownership_percent").contains("value=\"\""));
    assert!(
        !cell(&after.body, "secondary.phone").contains("star"),
        "the second owner's details are no longer required"
    );
    assert!(!after.body.contains("Remove second owner"));

    let draft = Form { omit: vec!["Secondary Owner Name"], ..Form::word() };
    let draft = stored_at(&upload(&pages.reviewer, &application(&draft, 22)).await);
    let page = pages.reviewer.get(&draft).await;
    assert!(page.body.contains("Hand entry") && page.body.contains("awaiting confirmation"));
    let confirmed = pages.reviewer.submit(&page, &format!("{draft}/confirm"), &[], None).await;
    assert_eq!(confirmed.location.as_deref(), Some(format!("{draft}?done=confirmed").as_str()));
    assert!(!pages.reviewer.get(&draft).await.body.contains("This is an application"));
}

/// The boxes of the SSNs and dates of birth on page 1, as pdfium reads them.
fn identity_boxes(library: &Path, pdf: &[u8]) -> Vec<Rect> {
    let binary = Path::new(env!("CARGO_BIN_EXE_lender-matching"));
    let mut worker = PdfWorker::start(binary, &["pdf-worker"], library).unwrap();
    let reading = read(&worker.facts(pdf, Duration::from_secs(60)).unwrap());
    let Document::Application(form) = reading.document else { panic!("an application") };
    let masked = form.fields.iter().filter(|(field, _)| field.spec().masked);
    masked.map(|(_, reading)| reading.evidence().expect("a value").rect).collect()
}

/// How many pixels inside `rect` are black, of how many, for page 1 drawn at `PAGE_WIDTH`.
fn black_in(png: &[u8], rect: &Rect) -> (usize, usize) {
    let image = image::load_from_memory_with_format(png, image::ImageFormat::Png).unwrap().into_rgba8();
    let scale = image.width() as f32 / 612.0;
    let (x0, x1) = ((rect.x0 * scale).ceil() as u32 + 1, (rect.x1 * scale).floor() as u32 - 1);
    let (y0, y1) = ((rect.top * scale).ceil() as u32 + 1, (rect.bottom * scale).floor() as u32 - 1);
    let pixels: Vec<_> = (y0..y1).flat_map(|y| (x0..x1).map(move |x| (x, y))).collect();
    let black = pixels.iter().filter(|(x, y)| *image.get_pixel(*x, *y) == image::Rgba([0, 0, 0, 255])).count();
    (black, pixels.len())
}

/// Every `value="…"` attribute on a page.
fn values_on(body: &str) -> Vec<&str> {
    body.split(" value=\"").skip(1).map(|rest| rest.split('"').next().unwrap()).collect()
}

fn access_log(data: &Path) -> Vec<(String, String)> {
    let database = rusqlite::Connection::open(data.join("lender-matching.sqlite3")).unwrap();
    let mut statement = database
        .prepare("SELECT a.action, u.username FROM application_access a JOIN users u ON u.id = a.user_id ORDER BY a.id")
        .unwrap();
    statement.query_map([], |row| Ok((row.get(0)?, row.get(1)?))).unwrap().map(Result::unwrap).collect()
}

#[tokio::test(flavor = "multi_thread")]
async fn page_one_is_covered_beside_the_form_and_only_a_logged_reveal_uncovers_it() {
    let Some(library) = support::pdfium_library() else { return };
    let pages = pages(&library).await;
    let pdf = application(&Form::word(), 21);
    let path = stored_at(&upload(&pages.reviewer, &pdf).await);
    let page = pages.reviewer.get(&path).await;
    let image = format!("{path}/page/1.png");
    assert!(page.body.contains(&format!("<img src=\"{image}\"")), "{}", page.body);
    let (status, headers, covered) = pages.reviewer.get_bytes(&image).await;
    assert_eq!((status, &headers["content-type"]), (StatusCode::OK, &"image/png".parse().unwrap()));
    let boxes = identity_boxes(&library, &pdf);
    assert_eq!(boxes.len(), 4);
    for rect in &boxes {
        let (black, all) = black_in(&covered, rect);
        assert!(all > 0 && black == all, "an identity value is painted over");
    }

    let seen = pages.viewer.get(&path).await;
    assert!(!seen.body.contains("<img") && !seen.body.contains("Reveal sensitive details"));
    assert_eq!(pages.viewer.get_bytes(&image).await.0, StatusCode::FORBIDDEN);
    let viewer_csrf = csrf_of(&seen);
    let reveal = format!("{path}/reveal");
    assert_eq!(pages.viewer.post(&reveal, &[("csrf".into(), viewer_csrf)]).await.status, StatusCode::FORBIDDEN);
    assert_eq!(pages.reviewer.post(&reveal, &[("csrf".into(), "forged".into())]).await.status, StatusCode::FORBIDDEN);
    assert!(access_log(pages.data.path()).is_empty(), "a refused reveal logs nothing");

    let revealed = pages.reviewer.submit(&page, &reveal, &[], None).await;
    assert_eq!(revealed.status, StatusCode::OK);
    assert_eq!(revealed.headers["cache-control"], "no-store");
    for value in IDENTITY {
        assert!(revealed.body.contains(value), "the reveal shows {value}");
    }
    for value in values_on(&revealed.body) {
        assert_no_secret("an input's value", value, &IDENTITY);
    }
    let inline = revealed.body.split("src=\"data:image/png;base64,").nth(1).expect("an inline page image");
    let png = STANDARD.decode(inline.split('"').next().unwrap()).unwrap();
    for rect in &boxes {
        let (black, all) = black_in(&png, rect);
        assert!(black < all, "the revealed page shows the value");
    }
    assert!(!revealed.body.contains(&format!("src=\"{image}\"")), "the reveal names no image address");
    assert_eq!(access_log(pages.data.path()), [("reveal".to_string(), "sample.reviewer".to_string())]);
    assert_no_secret("the page after a reveal", &pages.reviewer.get(&path).await.body, &IDENTITY);

    let draft = Form { omit: vec!["Secondary Owner Name"], ..Form::word() };
    let draft = stored_at(&upload(&pages.reviewer, &application(&draft, 22)).await);
    let page = pages.reviewer.get(&draft).await;
    assert!(page.body.contains("No covered image of page 1 can be made") && !page.body.contains("<img"));
    assert_eq!(pages.reviewer.get_bytes(&format!("{draft}/page/1.png")).await.0, StatusCode::NOT_FOUND);
}

#[tokio::test(flavor = "multi_thread")]
async fn the_history_lists_every_revision_and_reveal_and_the_same_parser_has_nothing_to_adopt() {
    let Some(library) = support::pdfium_library() else { return };
    let pages = pages(&library).await;
    let path = stored_at(&upload(&pages.reviewer, &application(&Form::word(), 21)).await);
    let page = pages.reviewer.get(&path).await;
    let changes = [
        ("f.business.legal_name", "FABRIKAM LLC"),
        ("f.principal.birth_date", "05/16/1981"),
        ("cause", "reading"),
        ("reason", "SAMPLE REASON"),
    ];
    assert_eq!(pages.reviewer.submit(&page, &path, &changes, None).await.status, StatusCode::SEE_OTHER);
    pages.reviewer.submit(&page, &format!("{path}/reveal"), &[], None).await;
    let again = pages.reviewer.submit(&page, &format!("{path}/reparse"), &[], None).await;
    assert_eq!(again.location.as_deref(), Some(format!("{path}?done=current").as_str()));
    assert!(pages.reviewer.get(again.location.as_deref().unwrap()).await.body.contains("nothing to adopt"));

    let history = pages.viewer.get(&format!("{path}/history")).await;
    assert_eq!(history.status, StatusCode::OK);
    let body = &history.body;
    assert!(body.contains("<h1>History of FABRIKAM LLC</h1>"));
    assert!(body.contains("Corrected: the parser read the PDF wrong by sample.reviewer at "));
    assert!(body.contains(": SAMPLE REASON</p>"));
    assert!(body.contains("<li>Business Legal Name: CONTOSO LLC → FABRIKAM LLC</li>"));
    assert!(body.contains("<li>Principal Date of Birth: changed</li>"));
    assert!(body.contains("Uploaded by sample.reviewer") && body.contains("<li>Read by parser"));
    assert!(body.contains("<li>reveal by sample.reviewer at "));
    assert!(body.find("<h2>Revision 2</h2>").unwrap() < body.find("<h2>Revision 1</h2>").unwrap(), "newest first");
    assert_no_secret("the history", body, &["05/16/1981", "04/15/1980", "900-12-3456"]);
}

#[tokio::test(flavor = "multi_thread")]
async fn find_lenders_matches_the_corrected_application_and_the_match_says_when_it_changed() {
    let Some(library) = support::pdfium_library() else { return };
    let pages = pages(&library).await;
    let path = stored_at(&upload(&pages.reviewer, &application(&Form::word(), 21)).await);
    let page = pages.reviewer.get(&path).await;
    let corrected = [("f.business.state", "FL"), ("cause", "merchant")];
    assert_eq!(pages.reviewer.submit(&page, &path, &corrected, None).await.status, StatusCode::SEE_OTHER);
    let page = pages.reviewer.get(&path).await;
    let find = format!("{path}/matches");
    assert_eq!(value_of(&form_fields(&page.body, &find), "base_revision").as_deref(), Some("2"));
    let made = pages.reviewer.submit(&page, &find, &[("confirm.home_based", "no")], None).await;
    assert_eq!(made.status, StatusCode::SEE_OTHER, "{}", made.body);
    let matched = made.location.unwrap();
    let shown = pages.viewer.get(&matched).await;
    assert!(shown.body.contains("revision 2.") && shown.body.contains("<td>FL</td>"), "{}", shown.body);
    assert!(!shown.body.contains("The application changed after this match"));

    let viewed = pages.viewer.get(&path).await;
    assert!(!viewed.body.contains("Find lenders"), "a viewer cannot match");
    let later = [("f.business.city", "TAMPA"), ("cause", "merchant")];
    assert_eq!(pages.reviewer.submit(&page, &path, &later, None).await.status, StatusCode::SEE_OTHER);
    let changed = pages.viewer.get(&matched).await;
    assert!(changed.body.contains("The application changed after this match: revision 3 is current."));
}

/// Page 1 as the server draws it beside an audit's inputs.
fn page_png(library: &Path, pdf: &[u8]) -> Vec<u8> {
    let binary = Path::new(env!("CARGO_BIN_EXE_lender-matching"));
    let mut worker = PdfWorker::start(binary, &["pdf-worker"], library).unwrap();
    let image = PageImage { page: 0, width: 1100, covers: Vec::new() };
    worker.page_png(pdf, &image, Duration::from_secs(60)).unwrap()
}

fn sample(data: &Path, folder: &Path, library: &Path, count: &str) -> Output {
    let mut command = command(data);
    command.env("APPLICATION_DATA_KEY", KEY).env("PDFIUM_LIBRARY", library);
    let folder = folder.to_str().unwrap();
    command.args(["applications", "sample", folder, "--count", count, "--seed", "7", "--by", "sample.reviewer"]);
    command.output().unwrap()
}

/// What the auditor types for `form`: what it prints in each field a person enters.
fn transcribed(form: &Form) -> Vec<(String, String)> {
    let entered = form.values.iter().filter(|(field, _)| field.spec().editable());
    entered.map(|(field, text)| (format!("f.{field}"), text.to_string())).collect()
}

#[tokio::test(flavor = "multi_thread")]
async fn a_blind_audit_hides_the_parse_until_it_is_saved_and_accuracy_scores_it() {
    let Some(library) = support::pdfium_library() else { return };
    let legal_name = FieldId::Business(BusinessField::LegalName);
    let city = FieldId::Business(BusinessField::City);
    let forms =
        [Form::word(), Form::word().set(legal_name, "FABRIKAM LLC"), Form::word().set(legal_name, "NORTHWIND LLC")];
    let draft = Form { omit: vec!["Secondary Owner Name"], ..Form::word() };
    let inbox = TempDir::new();
    let mut documents: Vec<(&str, Vec<u8>)> = vec![
        ("CONTOSO.pdf", application(&forms[0], 21)),
        ("FABRIKAM.pdf", application(&forms[1], 22)),
        ("NORTHWIND.pdf", application(&forms[2], 23)),
        ("SAMPLE contract.pdf", contract()),
        ("SAMPLE draft.pdf", application(&draft, 24)),
    ];
    for (name, bytes) in &documents {
        std::fs::write(inbox.path().join(name), bytes).unwrap();
    }
    std::fs::write(inbox.path().join("SAMPLE broken.pdf"), b"SAMPLE OWNER, not a PDF").unwrap();
    documents.push(("SAMPLE broken.pdf", Vec::new()));

    let mixed = TempDir::new();
    add_user(mixed.path(), "sample.reviewer", "reviewer");
    let upload = inbox.path().join("CONTOSO.pdf");
    assert!(import(mixed.path(), &[upload], "sample.reviewer", Some(KEY), Some(&library)).status.success());
    let refused = sample(mixed.path(), inbox.path(), &library, "2");
    assert!(!refused.status.success() && text(&refused.stderr).contains("not drawn for an audit"));

    let pages = pages(&library).await;
    let drawn = sample(pages.data.path(), inbox.path(), &library, "6");
    assert!(drawn.status.success(), "{}", text(&drawn.stderr));
    let stdout = text(&drawn.stdout);
    assert_eq!(
        stdout.lines().collect::<Vec<_>>(),
        [
            "applications sample: drew 6 of 6 PDF files with seed 7. Counts only.",
            "stored for the audit: application forms 3, hand-entry drafts 1, refused documents 1",
            "already stored 0; not stored, as the PDF could not be read, 1",
        ]
    );
    let again = sample(pages.data.path(), inbox.path(), &library, "6");
    assert!(text(&again.stdout).contains("already stored 5;"), "a repeat stores nothing new");
    assert!(sample(pages.data.path(), inbox.path(), &library, "7").status.code() == Some(1));

    let parsed = ["CONTOSO", "FABRIKAM", "NORTHWIND", "AUSTIN", "SAMPLE OWNER", "owner@example.com", "hand entry"];
    let list = pages.reviewer.get("/admin/applications").await;
    assert_no_secret("the list before the audits", &list.body, &parsed);
    let ids: Vec<String> = list
        .body
        .split("href=\"/admin/applications/")
        .skip(1)
        .filter_map(|rest| {
            let id = rest.split('"').next().unwrap();
            (id.len() == 36).then(|| id.to_string())
        })
        .collect();
    assert_eq!(ids.len(), 5, "{}", list.body);
    assert_eq!(list.body.matches("awaiting its audit").count(), 5);

    let renders: Vec<Vec<u8>> = documents[..5].iter().map(|(_, pdf)| page_png(&library, pdf)).collect();
    let mut audits = Vec::new();
    for id in &ids {
        let path = format!("/admin/applications/{id}");
        let page = pages.reviewer.get(&path).await;
        assert!(page.body.contains("<h1>Blind audit</h1>"), "{}", page.body);
        assert_no_secret("an audit page", &page.body, &parsed);
        let inline = page.body.split("src=\"data:image/png;base64,").nth(1).expect("page 1, uncovered");
        let png = STANDARD.decode(inline.split('"').next().unwrap()).unwrap();
        let document = renders.iter().position(|render| *render == png).expect("the page of a sampled file");
        let seen = pages.viewer.get(&path).await;
        assert!(seen.body.contains("Awaiting its audit") && !seen.body.contains("<img"));
        assert_eq!(pages.reviewer.get(&format!("{path}/history")).await.status, StatusCode::CONFLICT);
        assert_eq!(pages.reviewer.get_bytes(&format!("{path}/page/1.png")).await.0, StatusCode::CONFLICT);
        let csrf = vec![("csrf".to_string(), csrf_of(&page))];
        assert_eq!(pages.reviewer.post(&format!("{path}/reveal"), &csrf).await.status, StatusCode::CONFLICT);
        audits.push((path, page, document));
    }
    audits.sort_by_key(|(_, _, document)| *document);
    let [contoso, fabrikam, northwind, contract, draft] = &audits[..] else { panic!("five audits") };

    let audit = |path: &String| format!("{path}/audit");
    let mut typed = transcribed(&forms[0]);
    set(&mut typed, "f.business.start_date", "13/45/2019");
    let typed: Vec<(&str, &str)> = typed.iter().map(|(name, value)| (name.as_str(), value.as_str())).collect();
    let unreadable = pages.reviewer.submit(&contoso.1, &audit(&contoso.0), &typed, None).await;
    assert_eq!(unreadable.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(unreadable.body.contains("Business Start Date: Could not read this as a date"));
    assert_eq!(value_of(&form_fields(&unreadable.body, &audit(&contoso.0)), "f.principal.ssn").as_deref(), Some(""));

    let not_application = || vec![("not_application".to_string(), "on".to_string())];
    let saves = [
        (contoso, transcribed(&forms[0])),
        (fabrikam, transcribed(&Form::word().set(legal_name, "FABRIKAM LLC").set(city, "DALLAS"))),
        (northwind, not_application()),
        (contract, not_application()),
        (draft, vec![("f.business.legal_name".to_string(), "SAMPLE DRAFT LLC".to_string())]),
    ];
    for ((path, page, _), changes) in saves {
        let changes: Vec<(&str, &str)> = changes.iter().map(|(name, value)| (name.as_str(), value.as_str())).collect();
        let saved = pages.reviewer.submit(page, &audit(path), &changes, None).await;
        assert_eq!(saved.location.as_deref(), Some(format!("{path}?done=audited").as_str()), "{}", saved.body);
    }
    let after = pages.reviewer.get(&contoso.0).await;
    assert!(after.body.contains("<h1>CONTOSO LLC</h1>"), "the form shows once audited");
    let history = pages.reviewer.get(&format!("{}/history", contoso.0)).await;
    assert!(history.body.contains("Audited blind by sample.reviewer"));
    let resubmitted = pages.reviewer.submit(&contoso.1, &audit(&contoso.0), &[], None).await;
    assert_eq!(resubmitted.status, StatusCode::CONFLICT, "an audit is saved once");
    let audits_logged = access_log(pages.data.path()).iter().filter(|(action, _)| action == "audit").count();
    assert!(audits_logged >= 5);

    let scored = cli(pages.data.path(), &["applications", "accuracy"]);
    assert!(!scored.status.success(), "the key is needed");
    let scored = command(pages.data.path())
        .env("APPLICATION_DATA_KEY", KEY)
        .args(["applications", "accuracy"])
        .output()
        .unwrap();
    let report = text(&scored.stdout);
    let lines: Vec<&str> = report.lines().collect();
    assert_eq!(
        lines[0],
        "applications accuracy: 5 sampled, 5 audited, 0 awaiting their audit. Counts only; intervals are Wilson 95%."
    );
    assert!(
        lines[1].starts_with(
            "documents: 4 classified right, 1 wrong (applications refused 0, other documents kept 1); right 80.0%"
        ),
        "{report}"
    );
    let row = |field: &str, counts: [u32; 4]| {
        format!("{field:<34} {:>6} {:>6} {:>8} {:>7}", counts[0], counts[1], counts[2], counts[3])
    };
    assert!(lines.iter().any(|line| line.starts_with(&row("business.city", [2, 1, 0, 0]))), "{report}");
    assert!(lines.iter().any(|line| line.starts_with(&row("business.legal_name", [2, 0, 1, 0]))), "{report}");
    assert!(lines.last().unwrap().starts_with("applications with every field right: 1 of 3"), "{report}");

    let mut secrets: Vec<&str> = parsed.to_vec();
    secrets.extend(IDENTITY);
    secrets.extend(["SAMPLE DRAFT LLC", "DALLAS", "SAMPLE broken", "SAMPLE contract"]);
    for (what, printed) in [
        ("sample's stdout", stdout.as_str()),
        ("accuracy's stdout", report.as_str()),
        ("the server log", &pages.server.log()),
    ] {
        assert_no_secret(what, printed, &secrets);
    }
    let database = database_bytes(pages.data.path());
    for secret in secrets.iter().filter(|secret| secret.len() > 3) {
        assert!(
            !database.windows(secret.len()).any(|window| window == secret.as_bytes()),
            "the database holds {secret}"
        );
    }
}
