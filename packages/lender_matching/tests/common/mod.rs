//! Drives the built `lender-matching` binary: its CLI, and its server against a fake analysis API
//! that serves the fabricated packages in `tests/fixtures/analysis`.
#![allow(dead_code)]

use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdout, Command, Output, Stdio};
use std::sync::Arc;

use axum::extract::{Path as UrlPath, State};
use axum::http::header::{AUTHORIZATION, RETRY_AFTER};
use axum::http::{HeaderMap, HeaderValue, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::get;
use axum::{Json, Router};
use rust_xlsxwriter::Workbook;
use uuid::Uuid;

pub const ANALYSIS_TOKEN: &str = "sample-analysis-token";
pub const PASSWORD: &str = "correct horse battery staple";

/// A scratch directory outside the checkout, removed on drop.
pub struct TempDir(PathBuf);

impl TempDir {
    pub fn new() -> TempDir {
        let path = std::env::temp_dir().join(format!("lender-matching-test-{}", Uuid::new_v4()));
        std::fs::create_dir_all(&path).unwrap();
        TempDir(path)
    }

    pub fn path(&self) -> &Path {
        &self.0
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

/// The binary with a data directory and none of the developer's environment.
pub fn command(data: &Path) -> Command {
    let mut command = Command::new(env!("CARGO_BIN_EXE_lender-matching"));
    for name in ["LENDER_MATCHING_DATA_DIR", "ANALYSIS_API_URL", "ANALYSIS_API_TOKEN", "PUBLIC_URL"] {
        command.env_remove(name);
    }
    command.arg("--data-dir").arg(data);
    command
}

pub fn cli(data: &Path, args: &[&str]) -> Output {
    command(data).args(args).output().unwrap()
}

pub fn cli_ok(data: &Path, args: &[&str]) -> String {
    let output = cli(data, args);
    assert!(output.status.success(), "{args:?} failed: {}", String::from_utf8_lossy(&output.stderr));
    String::from_utf8(output.stdout).unwrap()
}

pub fn add_user(data: &Path, username: &str, role: &str) {
    let mut child = command(data)
        .args(["user", "add", username, "--role", role, "--password-stdin"])
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .spawn()
        .unwrap();
    writeln!(child.stdin.take().unwrap(), "{PASSWORD}").unwrap();
    assert!(child.wait().unwrap().success(), "user add {username}");
}

pub fn token(data: &Path, name: &str, scopes: &[&str]) -> String {
    let mut args = vec!["token", "create", name];
    for scope in scopes {
        args.extend(["--scope", scope]);
    }
    cli_ok(data, &args).trim().to_string()
}

pub struct Server {
    child: Child,
    _stdout: BufReader<ChildStdout>,
    log: PathBuf,
    pub base: String,
}

impl Server {
    pub fn start(data: &Path, env: &[(&str, &str)]) -> Server {
        let log = data.join("server.log");
        let mut child = command(data)
            .args(["serve", "--bind", "127.0.0.1:0"])
            .envs(env.iter().copied())
            .stdout(Stdio::piped())
            .stderr(File::create(&log).unwrap())
            .spawn()
            .unwrap();
        let mut stdout = BufReader::new(child.stdout.take().unwrap());
        let mut line = String::new();
        stdout.read_line(&mut line).unwrap();
        let base = match line.trim().strip_prefix("listening on ") {
            Some(base) => base.to_string(),
            None => panic!("the server did not start: {}", std::fs::read_to_string(&log).unwrap_or_default()),
        };
        Server { child, _stdout: stdout, log, base }
    }

    pub fn url(&self, path: &str) -> String {
        format!("{}{path}", self.base)
    }

    pub fn log(&self) -> String {
        std::fs::read_to_string(&self.log).unwrap_or_default()
    }
}

impl Drop for Server {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

pub fn http() -> reqwest::Client {
    let _ = rustls::crypto::ring::default_provider().install_default();
    reqwest::Client::builder().redirect(reqwest::redirect::Policy::none()).build().unwrap()
}

pub fn fixture(name: &str) -> serde_json::Value {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests").join("fixtures").join("analysis").join(name);
    serde_json::from_str(&std::fs::read_to_string(path.with_extension("json")).unwrap()).unwrap()
}

/// Serves `GET /api/v1/packages/<id>` for each id: a fixture by name, with its `package_id` set to
/// the id; `processing` adds `Retry-After: 7`; `broken` answers a body outside the contract.
pub async fn fake_analysis(packages: Vec<(Uuid, &'static str)>) -> String {
    let packages: Arc<HashMap<Uuid, &'static str>> = Arc::new(packages.into_iter().collect());
    let app = Router::new().route("/api/v1/packages/{id}", get(serve_package)).with_state(packages);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    format!("http://{address}/api/v1")
}

fn analysis_error(status: StatusCode, code: &str) -> Response {
    let body = serde_json::json!({"error": {"code": code, "message": "fixed message", "filename": null}});
    (status, Json(body)).into_response()
}

async fn serve_package(
    State(packages): State<Arc<HashMap<Uuid, &'static str>>>,
    UrlPath(id): UrlPath<Uuid>,
    headers: HeaderMap,
) -> Response {
    let expected = format!("Bearer {ANALYSIS_TOKEN}");
    if headers.get(AUTHORIZATION).and_then(|value| value.to_str().ok()) != Some(expected.as_str()) {
        return analysis_error(StatusCode::UNAUTHORIZED, "unauthorized");
    }
    match packages.get(&id).copied() {
        None => analysis_error(StatusCode::NOT_FOUND, "package_not_found"),
        Some("broken") => (StatusCode::OK, r#"{"api_version": "1.0"}"#).into_response(),
        Some(name) => {
            let mut body = fixture(name);
            body["package_id"] = id.to_string().into();
            let mut response = Json(body).into_response();
            if name == "processing" {
                response.headers_mut().insert(RETRY_AFTER, HeaderValue::from_static("7"));
            }
            response
        }
    }
}

const HEADERS: [&str; 16] = [
    "Lender Name",
    "Minimum Monthly Rev",
    "Credit Score",
    "Min Dep No.",
    "NSF Per Month",
    "Positions",
    "TIB",
    "Restricted Industries",
    "Restricted States",
    "Exclusivity",
    "Additional Info",
    "Clawback Period",
    "Accept Default History?",
    "Account Manager",
    "Contact Phone",
    "Record Id",
];

/// Writes a "Lenders Module" workbook; each row names its filled cells by header.
pub fn workbook(dir: &Path, rows: &[&[(&str, &str)]]) -> PathBuf {
    let mut book = Workbook::new();
    let sheet = book.add_worksheet();
    sheet.set_name("Lenders Module").unwrap();
    for (index, header) in HEADERS.iter().enumerate() {
        sheet.write_string(0, index as u16, *header).unwrap();
    }
    for (row, cells) in rows.iter().enumerate() {
        for (header, value) in cells.iter() {
            let column = HEADERS.iter().position(|known| known == header).unwrap() as u16;
            match value.parse::<f64>() {
                Ok(number) => sheet.write_number(row as u32 + 1, column, number).unwrap(),
                Err(_) => sheet.write_string(row as u32 + 1, column, *value).unwrap(),
            };
        }
    }
    let path = dir.join("info-hub.xlsx");
    book.save(&path).unwrap();
    path
}

/// Four fabricated lenders that, once active, answer the `deal` below with match after review,
/// review, no match, and nothing to check.
pub fn seed_workbook(dir: &Path) -> PathBuf {
    workbook(
        dir,
        &[
            &[
                ("Lender Name", "CONTOSO CAPITAL"),
                ("Record Id", "REC-1"),
                ("Minimum Monthly Rev", "25000"),
                ("Credit Score", "600"),
                ("Min Dep No.", "10"),
                ("NSF Per Month", "3"),
                ("Positions", "1-3"),
                ("TIB", "2 Years"),
                ("Restricted Industries", "Cannabis"),
                ("Restricted States", "PR"),
                ("Accept Default History?", "Yes"),
            ],
            &[
                ("Lender Name", "FABRIKAM FUNDING"),
                ("Record Id", "REC-2"),
                ("Minimum Monthly Rev", "20000"),
                ("Credit Score", "600"),
                ("NSF Per Month", "2"),
                ("Positions", "1-5+"),
                ("Accept Default History?", "No"),
                ("Additional Info", "No bank account switch in the last 3 months"),
                ("Account Manager", "SAMPLE REP"),
                ("Contact Phone", "555-0100"),
            ],
            &[
                ("Lender Name", "NORTHWIND ADVANCE"),
                ("Record Id", "REC-3"),
                ("Credit Score", "680"),
                ("Restricted Industries", "General Retail;Transportation / Trucking"),
            ],
            &[("Lender Name", "SAMPLE PARTNER LINK"), ("Additional Info", "https://partners.sample.example/apply")],
        ],
    )
}

pub fn deal(package: Option<Uuid>) -> serde_json::Value {
    serde_json::json!({
        "analysis_package_id": package,
        "application": {
            "business_state": "TX",
            "business_start_month": "2019-04",
            "entity": "llc",
            "estimated_fico": {"min": 640, "max": 640},
            "requested_amount_cents": 7_500_000,
            "open_judgements": false,
            "bankruptcy": false,
            "tax_liens": false,
            "industry_suggestion": "general-retail"
        }
    })
}

/// `deal` without an industry suggestion, for a store whose picklist is empty.
pub fn bare_deal(package: Option<Uuid>) -> serde_json::Value {
    let mut body = deal(package);
    body["application"].as_object_mut().unwrap().remove("industry_suggestion");
    body
}

pub fn bearer(token: &str) -> String {
    format!("Bearer {token}")
}
