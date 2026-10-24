mod common;

use common::*;
use lender_matching_wire::v1 as wire;
use reqwest::StatusCode;
use reqwest::header::{ALLOW, CACHE_CONTROL, LOCATION, RETRY_AFTER, WWW_AUTHENTICATE};
use uuid::Uuid;

async fn error_code(response: reqwest::Response) -> (StatusCode, wire::ApiError) {
    let status = response.status();
    let body: wire::ErrorResponse = contract_body("ErrorResponse", response).await;
    assert_eq!(body.error.message, body.error.code.message());
    (status, body.error)
}

fn fact<'a>(body: &'a wire::MatchResponse, name: &str) -> &'a wire::Fact {
    body.facts.iter().find(|fact| fact.fact == name).unwrap_or_else(|| panic!("no fact {name}"))
}

fn range(min: i64, max: i64) -> Option<wire::FactValue> {
    Some(wire::FactValue::Range(wire::Range { min, max: Some(max) }))
}

#[tokio::test(flavor = "multi_thread")]
async fn only_a_live_token_with_the_right_scope_opens_the_api() {
    let data = TempDir::new();
    let full = token(data.path(), "auto-submission", &["match", "read"]);
    let reader = token(data.path(), "dashboard", &["read"]);
    let server = Server::start(data.path(), &[]);
    let http = http();

    assert_eq!(http.get(server.url("/healthz")).send().await.unwrap().status(), StatusCode::OK);

    let anonymous = http.get(server.url("/api/v1/industries")).send().await.unwrap();
    assert_eq!(anonymous.headers()[WWW_AUTHENTICATE], "Bearer realm=\"lender-matching-api\"");
    assert_eq!(anonymous.headers()[CACHE_CONTROL], "no-store");
    assert_eq!(error_code(anonymous).await.1.code, wire::ErrorCode::Unauthorized);
    for credential in ["Bearer lm_forged", "Basic YWRtaW46YWRtaW4=", "Bearer"] {
        let response = http.get(server.url("/api/v1/industries")).header("Authorization", credential).send().await;
        assert_eq!(response.unwrap().status(), StatusCode::UNAUTHORIZED, "{credential}");
    }
    let cookie_only = http.get(server.url("/api/v1/industries")).header("Cookie", "lm_session=anything").send().await;
    assert_eq!(cookie_only.unwrap().status(), StatusCode::UNAUTHORIZED);

    let listed =
        http.get(server.url("/api/v1/industries")).header("Authorization", format!("bearer   {reader} ")).send();
    let listed = listed.await.unwrap();
    assert_eq!(listed.status(), StatusCode::OK);
    assert_eq!(contract_body::<wire::IndustriesResponse>("IndustriesResponse", listed).await.industries, []);

    let refused =
        http.post(server.url("/api/v1/matches")).header("Authorization", bearer(&reader)).json(&bare_deal(None));
    let (status, error) = error_code(refused.send().await.unwrap()).await;
    assert_eq!((status, error.code), (StatusCode::FORBIDDEN, wire::ErrorCode::ScopeRequired));

    let made = http.post(server.url("/api/v1/matches")).header("Authorization", bearer(&full)).json(&bare_deal(None));
    assert_eq!(made.send().await.unwrap().status(), StatusCode::CREATED);

    let unknown = http.get(server.url("/api/v1/lenders")).header("Authorization", bearer(&full)).send().await.unwrap();
    assert_eq!(error_code(unknown).await.1.code, wire::ErrorCode::RouteNotFound);
    let unknown_anonymous = http.get(server.url("/api/v1/lenders")).send().await.unwrap();
    assert_eq!(unknown_anonymous.status(), StatusCode::UNAUTHORIZED, "the token is checked before the route");
    let wrong_method = http.delete(server.url("/api/v1/matches")).header("Authorization", bearer(&full)).send();
    let wrong_method = wrong_method.await.unwrap();
    assert_eq!(wrong_method.headers()[ALLOW], "POST");
    assert_eq!(error_code(wrong_method).await.1.code, wire::ErrorCode::MethodNotAllowed);

    cli_ok(data.path(), &["token", "revoke", "dashboard"]);
    let revoked = http.get(server.url("/api/v1/industries")).header("Authorization", bearer(&reader)).send().await;
    assert_eq!(revoked.unwrap().status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test(flavor = "multi_thread")]
async fn a_match_reads_the_analysis_package_and_stores_what_it_read() {
    let ready = Uuid::new_v4();
    let processing = Uuid::new_v4();
    let broken = Uuid::new_v4();
    let held = Uuid::new_v4();
    let refused = Uuid::new_v4();
    let analysis = fake_analysis(vec![
        (ready, "ready_clean"),
        (processing, "processing"),
        (broken, "broken"),
        (held, "ready_review_required"),
        (refused, "ready_currency_refused"),
    ])
    .await;
    let data = TempDir::new();
    let imported = cli_ok(data.path(), &["import-info-hub", seed_workbook(data.path()).to_str().unwrap(), "--apply"]);
    assert!(imported.contains("Applied."), "{imported}");
    let token = token(data.path(), "auto-submission", &["match", "read"]);
    let server = Server::start(data.path(), &[("ANALYSIS_API_URL", &analysis), ("ANALYSIS_API_TOKEN", ANALYSIS_TOKEN)]);
    let http = http();
    let post = |body: serde_json::Value| {
        http.post(server.url("/api/v1/matches")).header("Authorization", bearer(&token)).json(&body).send()
    };

    let created = post(deal(Some(ready))).await.unwrap();
    assert_eq!(created.status(), StatusCode::CREATED, "{}", server.log());
    assert_eq!(created.headers()[CACHE_CONTROL], "no-store");
    let location = created.headers()[LOCATION].to_str().unwrap().to_string();
    let body: wire::MatchResponse = contract_body("MatchResponse", created).await;
    assert_eq!(location, format!("/api/v1/matches/{}", body.match_id));
    assert_eq!(body.analysis.as_ref().map(|analysis| analysis.package_id), Some(ready));
    assert_eq!(body.created_by, wire::CreatedBy::Client { name: "auto-submission".to_string() });

    let revenue = fact(&body, "monthly_true_revenue_cents");
    assert_eq!((revenue.value.clone(), revenue.basis), (range(3_125_000, 3_125_000), Some(wire::Basis::Printed)));
    assert_eq!(fact(&body, "worst_month_negative_days").value, range(2, 2));
    assert_eq!(fact(&body, "worst_month_deposits").value, range(14, 15));
    assert_eq!(fact(&body, "new_position").value, range(2, 2));
    assert_eq!(fact(&body, "statement_months").value, range(4, 4));
    assert_eq!(fact(&body, "funder_payment_history").value, Some(wire::FactValue::Flag(true)));
    assert_eq!(fact(&body, "state").basis, Some(wire::Basis::Stated));
    let industry = fact(&body, "industry");
    assert_eq!((industry.known, industry.gap.as_deref()), (false, Some("needs_confirmation")));
    assert_eq!(industry.seen, Some(wire::FactValue::Text("general-retail".to_string())));
    assert_eq!(fact(&body, "default_history").gap.as_deref(), Some("needs_confirmation"));
    assert_eq!(body.months.len(), 4);
    assert!(body.verdicts.is_empty(), "imported lenders are drafts");
    assert_eq!(body.inactive.len(), 4);
    assert!(body.inactive.iter().all(|lender| lender.status == wire::InactiveStatus::Draft && lender.current));

    let stored = http.get(server.url(&location)).header("Authorization", bearer(&token)).send().await.unwrap();
    assert_eq!(contract_body::<wire::MatchResponse>("MatchResponse", stored).await, body);

    let waiting = post(deal(Some(processing))).await.unwrap();
    assert_eq!(waiting.headers()[RETRY_AFTER], "7");
    assert_eq!(error_code(waiting).await, (StatusCode::CONFLICT, error(wire::ErrorCode::AnalysisNotReady)));
    let missing = post(deal(Some(Uuid::new_v4()))).await.unwrap();
    assert_eq!(error_code(missing).await.1.code, wire::ErrorCode::AnalysisPackageNotFound);
    let mismatch = post(deal(Some(broken))).await.unwrap();
    assert_eq!(error_code(mismatch).await, (StatusCode::BAD_GATEWAY, error(wire::ErrorCode::AnalysisContractMismatch)));

    let held: wire::MatchResponse = contract_body("MatchResponse", post(deal(Some(held))).await.unwrap()).await;
    let revenue = fact(&held, "monthly_true_revenue_cents");
    assert_eq!(revenue.gap.as_deref(), Some("analysis_review_required"));
    assert_eq!(revenue.seen, range(3_125_000, 3_125_000));
    let refused: wire::MatchResponse = contract_body("MatchResponse", post(deal(Some(refused))).await.unwrap()).await;
    assert_eq!(fact(&refused, "monthly_true_revenue_cents").gap.as_deref(), Some("currency_refused"));
    assert_eq!(fact(&refused, "worst_month_negative_days").value, range(2, 2), "counts survive a currency refusal");
}

fn error(code: wire::ErrorCode) -> wire::ApiError {
    wire::ApiError { code, message: code.message().to_string(), field: None }
}

#[tokio::test(flavor = "multi_thread")]
async fn an_analysis_service_that_is_missing_or_refuses_the_token_is_reported() {
    let package = Uuid::new_v4();
    let analysis = fake_analysis(vec![(package, "ready_clean")]).await;
    let data = TempDir::new();
    let token = token(data.path(), "auto-submission", &["match"]);
    let http = http();
    let unconfigured = Server::start(data.path(), &[]);
    let response = http
        .post(unconfigured.url("/api/v1/matches"))
        .header("Authorization", bearer(&token))
        .json(&bare_deal(Some(package)))
        .send()
        .await
        .unwrap();
    assert_eq!(
        error_code(response).await,
        (StatusCode::SERVICE_UNAVAILABLE, error(wire::ErrorCode::AnalysisNotConfigured))
    );
    drop(unconfigured);

    let wrong_token =
        Server::start(data.path(), &[("ANALYSIS_API_URL", &analysis), ("ANALYSIS_API_TOKEN", "stale-token")]);
    let response = http
        .post(wrong_token.url("/api/v1/matches"))
        .header("Authorization", bearer(&token))
        .json(&bare_deal(Some(package)))
        .send()
        .await
        .unwrap();
    assert_eq!(error_code(response).await, (StatusCode::BAD_GATEWAY, error(wire::ErrorCode::AnalysisUnavailable)));
    assert!(wrong_token.log().contains("status 401"), "{}", wrong_token.log());
}

#[tokio::test(flavor = "multi_thread")]
async fn requests_are_read_strictly() {
    let data = TempDir::new();
    let token = token(data.path(), "auto-submission", &["match", "read"]);
    let server = Server::start(data.path(), &[]);
    let http = http();
    let post = |body: String| {
        http.post(server.url("/api/v1/matches"))
            .header("Authorization", bearer(&token))
            .header("Content-Type", "application/json")
            .body(body)
            .send()
    };
    for body in
        ["not json", "{}", r#"{"application": {}, "attestations": []}"#, r#"{"application": {"entity": "trust"}}"#]
    {
        let (status, error) = error_code(post(body.to_string()).await.unwrap()).await;
        assert_eq!((status, error.code), (StatusCode::BAD_REQUEST, wire::ErrorCode::InvalidRequest), "{body}");
    }
    let bad_state = post(r#"{"application": {"business_state": "XX"}}"#.to_string()).await.unwrap();
    let (status, error) = error_code(bad_state).await;
    assert_eq!(
        (status, error.field.as_deref()),
        (StatusCode::UNPROCESSABLE_ENTITY, Some("/application/business_state"))
    );
    let unknown_industry = post(r#"{"application": {"industry_suggestion": "general-retail"}}"#.to_string());
    let (_, error) = error_code(unknown_industry.await.unwrap()).await;
    assert_eq!(error.field.as_deref(), Some("/application/industry_suggestion"));

    for path in ["/api/v1/matches/not-a-uuid", &format!("/api/v1/matches/{}", Uuid::new_v4())] {
        let response = http.get(server.url(path)).header("Authorization", bearer(&token)).send().await.unwrap();
        assert_eq!(error_code(response).await.1.code, wire::ErrorCode::MatchNotFound, "{path}");
    }
}

#[test]
#[should_panic(expected = "not a valid MatchResponse")]
fn the_contract_check_refuses_a_body_missing_a_field() {
    assert_contract("MatchResponse", &serde_json::json!({"api_version": "1.0"}));
}
