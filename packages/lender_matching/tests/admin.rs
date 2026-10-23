//! The admin pages, end to end, driven as a browser without JavaScript would drive them.

mod common;

use common::*;
use lender_matching_wire::v1 as wire;
use reqwest::StatusCode;
use uuid::Uuid;

fn lender_id(list: &Page, name: &str) -> String {
    let at = list.body.find(&format!(">{name}</a>")).unwrap_or_else(|| panic!("{name} is not listed"));
    let href = list.body[..at].rfind("/admin/lenders/").unwrap() + "/admin/lenders/".len();
    list.body[href..].split('"').next().unwrap().to_string()
}

fn csrf_only(page: &Page) -> Vec<(String, String)> {
    vec![("csrf".to_string(), csrf_of(page))]
}

struct Api {
    http: reqwest::Client,
    base: String,
    token: String,
}

impl Api {
    async fn create(&self, body: &serde_json::Value) -> wire::MatchResponse {
        let response = self
            .http
            .post(format!("{}/api/v1/matches", self.base))
            .header("Authorization", bearer(&self.token))
            .json(body)
            .send()
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::CREATED);
        response.json().await.unwrap()
    }

    async fn get(&self, id: Uuid) -> wire::MatchResponse {
        let response = self
            .http
            .get(format!("{}/api/v1/matches/{id}", self.base))
            .header("Authorization", bearer(&self.token))
            .send()
            .await
            .unwrap();
        response.json().await.unwrap()
    }
}

fn verdict<'a>(body: &'a wire::MatchResponse, name: &str) -> &'a wire::Verdict {
    body.verdicts.iter().find(|verdict| verdict.name == name).unwrap_or_else(|| panic!("no verdict for {name}"))
}

#[tokio::test(flavor = "multi_thread")]
async fn sign_in_needs_its_token_and_the_pages_take_only_a_session() {
    let data = TempDir::new();
    add_user(data.path(), "sample.editor", "editor");
    let server = Server::start(data.path(), &[]);
    let browser = Browser::new(&server);

    let anonymous = browser.get("/admin").await;
    assert_eq!((anonymous.status, anonymous.location.as_deref()), (StatusCode::SEE_OTHER, Some("/login")));
    let forged = browser
        .post("/login", &[("username".into(), "sample.editor".into()), ("password".into(), PASSWORD.into())])
        .await;
    assert_eq!(forged.status, StatusCode::FORBIDDEN, "no sign-in token");

    let login = browser.get("/login").await;
    let mut fields = form_fields(&login.body, "/login");
    set(&mut fields, "username", "sample.editor");
    set(&mut fields, "password", "not the password");
    let wrong = browser.post("/login", &fields).await;
    assert_eq!(wrong.status, StatusCode::UNAUTHORIZED);
    assert!(wrong.body.contains("Wrong username or password."));

    browser.sign_in("sample.editor").await;
    let list = browser.get("/admin").await;
    assert_eq!(list.status, StatusCode::OK);
    assert!(list.headers["content-security-policy"].to_str().unwrap().contains("default-src 'none'"));
    assert_eq!(list.headers["cache-control"], "no-store");

    let with_bearer = http()
        .get(server.url("/admin"))
        .header("Cookie", format!("lm_session={}", "anything"))
        .header("Authorization", "Bearer lm_anything")
        .send()
        .await
        .unwrap();
    assert_eq!(with_bearer.status(), StatusCode::UNAUTHORIZED);

    let forged_csrf =
        browser.post("/admin/industries", &[("csrf".into(), "forged".into()), ("label".into(), "Solar".into())]).await;
    assert_eq!(forged_csrf.status, StatusCode::FORBIDDEN);

    let signed_out = browser.post("/logout", &csrf_only(&list)).await;
    assert_eq!(signed_out.location.as_deref(), Some("/login"));
    assert_eq!(browser.get("/admin").await.location.as_deref(), Some("/login"));
}

#[tokio::test(flavor = "multi_thread")]
async fn lenders_are_activated_edited_reviewed_and_paused_through_the_pages() {
    let package = Uuid::new_v4();
    let analysis = fake_analysis(vec![(package, "ready_clean")]).await;
    let data = TempDir::new();
    cli_ok(data.path(), &["import-info-hub", seed_workbook(data.path()).to_str().unwrap(), "--apply"]);
    for (username, role) in [("sample.editor", "editor"), ("sample.reviewer", "reviewer"), ("sample.viewer", "viewer")]
    {
        add_user(data.path(), username, role);
    }
    let token = token(data.path(), "auto-submission", &["match", "read"]);
    let server = Server::start(data.path(), &[("ANALYSIS_API_URL", &analysis), ("ANALYSIS_API_TOKEN", ANALYSIS_TOKEN)]);
    let api = Api { http: http(), base: server.base.clone(), token };
    let editor = Browser::new(&server);
    editor.sign_in("sample.editor").await;

    let list = editor.get("/admin").await;
    assert!(list.body.contains("draft") && list.body.contains("condition note"), "{}", list.body);
    let [contoso, fabrikam, northwind, partner] =
        ["CONTOSO CAPITAL", "FABRIKAM FUNDING", "NORTHWIND ADVANCE", "SAMPLE PARTNER LINK"]
            .map(|name| lender_id(&list, name));

    for lender in [&contoso, &fabrikam, &northwind, &partner] {
        let action = format!("/admin/lenders/{lender}/edit");
        let form = editor.get(&action).await;
        let saved = editor.submit(&form, &action, &[], Some(("action", "save"))).await;
        assert_eq!(saved.status, StatusCode::SEE_OTHER, "{lender}: {}", saved.body);
        assert!(
            editor.get(&format!("/admin/lenders/{lender}")).await.body.contains("Revision 1,"),
            "an unchanged form saves nothing"
        );
    }

    let partner_page = editor.get(&format!("/admin/lenders/{partner}/activate")).await;
    assert!(partner_page.body.contains("has no rules"));
    let refused = editor
        .post(
            &format!("/admin/lenders/{partner}/activate"),
            &[("csrf".into(), csrf_of(&partner_page)), ("base_revision".into(), "1".into())],
        )
        .await;
    assert_eq!(refused.status, StatusCode::CONFLICT);

    for lender in [&contoso, &fabrikam, &northwind] {
        let action = format!("/admin/lenders/{lender}/activate");
        let page = editor.get(&action).await;
        assert!(page.body.contains("no requirement"), "the blank Info Hub columns are listed");
        let activated = editor.submit(&page, &action, &[], None).await;
        assert_eq!(activated.status, StatusCode::SEE_OTHER, "{}", activated.body);
    }

    let first = api.create(&deal(Some(package))).await;
    assert_eq!(verdict(&first, "CONTOSO CAPITAL").status, wire::VerdictStatus::Review, "the industry is unconfirmed");
    let fabrikam_first = verdict(&first, "FABRIKAM FUNDING");
    assert_eq!(fabrikam_first.status, wire::VerdictStatus::Review);
    assert!(
        fabrikam_first
            .checks
            .iter()
            .any(|c| c.text == "No default history" && c.why.as_deref() == Some("fact_unknown"))
    );
    assert!(
        fabrikam_first.notes.iter().any(|n| n.kind == wire::NoteKind::Condition && n.scope == wire::Scope::InScope)
    );
    assert_eq!(verdict(&first, "NORTHWIND ADVANCE").status, wire::VerdictStatus::NoMatch, "credit 640 is below 680");
    assert_eq!(first.inactive.iter().map(|lender| lender.name.as_str()).collect::<Vec<_>>(), ["SAMPLE PARTNER LINK"]);

    let edit_action = format!("/admin/lenders/{fabrikam}/edit");
    let stale_form = editor.get(&edit_action).await;
    let edited = editor
        .submit(
            &stale_form,
            &edit_action,
            &[("base.negative_days", "3"), ("reason", "rep confirmed new limit")],
            Some(("action", "save")),
        )
        .await;
    assert_eq!(edited.status, StatusCode::SEE_OTHER, "{}", edited.body);
    let history = editor.get(&format!("/admin/lenders/{fabrikam}/history")).await.body;
    assert!(history.contains("rep confirmed new limit"));
    assert!(history.contains("Negative days in the worst statement month at most 2"));
    assert!(history.contains("Negative days in the worst statement month at most 3"));
    let first_again = api.get(first.match_id).await;
    assert!(!verdict(&first_again, "FABRIKAM FUNDING").current, "the verdict read revision 2; revision 3 is current");

    let conflict = editor.submit(&stale_form, &edit_action, &[("base.credit", "650")], Some(("action", "save"))).await;
    assert_eq!(conflict.status, StatusCode::CONFLICT);
    assert!(conflict.body.contains("Changed by another editor"));
    assert!(conflict.body.contains("at most 3"), "the page shows their change");

    let current = editor.get(&edit_action).await;
    let with_row = editor.submit(&current, &edit_action, &[], Some(("action", "add_rule"))).await;
    assert_eq!(with_row.status, StatusCode::OK);
    assert!(with_row.body.contains("New rule"));
    let new_row = form_fields(&with_row.body, &edit_action)
        .into_iter()
        .filter_map(|(name, _)| name.strip_suffix(".id").and_then(|row| row.strip_prefix("rule.")).map(str::to_string))
        .next_back()
        .unwrap();
    let invalid = editor
        .submit(
            &with_row,
            &edit_action,
            &[
                (&format!("rule.{new_row}.req.fact"), "state"),
                (&format!("rule.{new_row}.req.op"), "at_least"),
                (&format!("rule.{new_row}.req.value"), "3"),
            ],
            Some(("action", "save")),
        )
        .await;
    assert_eq!(invalid.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(invalid.body.contains("State cannot be compared with"), "{}", invalid.body);
    let texas_first = editor
        .submit(
            &with_row,
            &edit_action,
            &[
                (&format!("rule.{new_row}.when.0.fact"), "state"),
                (&format!("rule.{new_row}.when.0.op"), "one_of"),
                (&format!("rule.{new_row}.when.0.value"), "CA"),
                (&format!("rule.{new_row}.req.fact"), "new_position"),
                (&format!("rule.{new_row}.req.op"), "at_most"),
                (&format!("rule.{new_row}.req.value"), "1"),
            ],
            Some(("action", "save")),
        )
        .await;
    assert_eq!(texas_first.status, StatusCode::SEE_OTHER, "{}", texas_first.body);
    assert!(
        editor
            .get(&format!("/admin/lenders/{fabrikam}"))
            .await
            .body
            .contains("When State is one of CA: New position at most 1")
    );

    let second = api.create(&deal(Some(package))).await;
    let reviewer = Browser::new(&server);
    reviewer.sign_in("sample.reviewer").await;
    let review_action = format!("/admin/matches/{}/review", second.match_id);
    let page = reviewer.get(&format!("/admin/matches/{}", second.match_id)).await;
    assert!(page.body.contains("Make a new match"));
    let waive = format!("waive.{fabrikam}.n2");
    let reason = format!("reason.{fabrikam}.n2");
    let confirmations = [("confirm.industry", "general-retail"), ("confirm.default_history", "no")];
    let mut missing_reason: Vec<(&str, &str)> = confirmations.to_vec();
    missing_reason.push((&waive, "on"));
    let refused = reviewer.submit(&page, &review_action, &missing_reason, None).await;
    assert_eq!(refused.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert!(refused.body.contains("give a reason for the waiver"));
    let mut reviewed: Vec<(&str, &str)> = missing_reason.clone();
    reviewed.push((&reason, "The statements show one operating account"));
    let made = reviewer.submit(&page, &review_action, &reviewed, None).await;
    assert_eq!(made.status, StatusCode::SEE_OTHER, "{}", made.body);
    let third_id: Uuid = made.location.unwrap().rsplit('/').next().unwrap().parse().unwrap();

    let third = api.get(third_id).await;
    assert_eq!(third.supersedes, Some(second.match_id));
    assert_eq!(third.created_by, wire::CreatedBy::Person { username: "sample.reviewer".to_string() });
    let industry = third.facts.iter().find(|fact| fact.fact == "industry").unwrap();
    assert_eq!(
        (industry.basis, industry.source.starts_with("confirmed by sample.reviewer")),
        (Some(wire::Basis::Confirmed), true)
    );
    assert_eq!(verdict(&third, "CONTOSO CAPITAL").status, wire::VerdictStatus::Match);
    let fabrikam_third = verdict(&third, "FABRIKAM FUNDING");
    assert_eq!(fabrikam_third.status, wire::VerdictStatus::Match, "{fabrikam_third:#?}");
    let additional_info = fabrikam_third.notes.iter().find(|note| note.id == "n2").unwrap();
    assert_eq!(additional_info.waiver.as_ref().map(|w| w.by.as_str()), Some("sample.reviewer"));
    assert_eq!(verdict(&third, "NORTHWIND ADVANCE").status, wire::VerdictStatus::NoMatch);
    assert_eq!(api.get(second.match_id).await.superseded_by, Some(third_id));
    let twice = reviewer.submit(&page, &review_action, &reviewed, None).await;
    assert_eq!(twice.status, StatusCode::CONFLICT, "a match is superseded once");

    let viewer = Browser::new(&server);
    viewer.sign_in("sample.viewer").await;
    assert_eq!(viewer.get(&edit_action).await.status, StatusCode::FORBIDDEN);
    let third_page = viewer.get(&format!("/admin/matches/{third_id}")).await;
    assert!(!third_page.body.contains("Make a new match"), "a viewer sees no review form");
    let viewer_review = viewer.post(&format!("/admin/matches/{third_id}/review"), &csrf_only(&third_page)).await;
    assert_eq!(viewer_review.status, StatusCode::FORBIDDEN);

    let contoso_page = editor.get(&format!("/admin/lenders/{contoso}")).await;
    let paused = editor
        .submit(&contoso_page, &format!("/admin/lenders/{contoso}/pause"), &[("reason", "SAMPLE hold")], None)
        .await;
    assert_eq!(paused.status, StatusCode::SEE_OTHER, "{}", paused.body);
    let after_pause = api.create(&deal(Some(package))).await;
    let contoso_inactive = after_pause.inactive.iter().find(|lender| lender.name == "CONTOSO CAPITAL").unwrap();
    assert_eq!(contoso_inactive.status, wire::InactiveStatus::Paused);
}

#[tokio::test(flavor = "multi_thread")]
async fn industries_and_import_reports_have_pages() {
    let data = TempDir::new();
    cli_ok(data.path(), &["import-info-hub", seed_workbook(data.path()).to_str().unwrap(), "--apply"]);
    add_user(data.path(), "sample.editor", "editor");
    let token = token(data.path(), "dashboard", &["read"]);
    let server = Server::start(data.path(), &[]);
    let editor = Browser::new(&server);
    editor.sign_in("sample.editor").await;
    let industries = || async {
        let response =
            http().get(server.url("/api/v1/industries")).header("Authorization", bearer(&token)).send().await;
        let body: wire::IndustriesResponse = response.unwrap().json().await.unwrap();
        body.industries.into_iter().map(|industry| industry.id).collect::<Vec<_>>()
    };
    assert_eq!(industries().await, ["cannabis", "general-retail", "transportation-trucking"]);

    let page = editor.get("/admin/industries").await;
    let added = editor.submit(&page, "/admin/industries", &[("label", "Solar")], None).await;
    assert_eq!(added.status, StatusCode::SEE_OTHER);
    assert!(industries().await.contains(&"solar".to_string()));
    let page = editor.get("/admin/industries").await;
    let retired = editor.submit(&page, "/admin/industries/cannabis", &[], Some(("retired", "true"))).await;
    assert_eq!(retired.status, StatusCode::SEE_OTHER);
    assert!(!industries().await.contains(&"cannabis".to_string()));
    assert!(editor.get("/admin/industries").await.body.contains("retired"));

    let imports = editor.get("/admin/imports").await;
    assert!(imports.body.contains("/admin/imports/1"));
    let report = editor.get("/admin/imports/1").await.body;
    assert!(
        report.contains("FABRIKAM FUNDING") && report.contains("Additional Info") && report.contains("condition note")
    );
    assert!(report.contains("default: positions above 5"));
}
