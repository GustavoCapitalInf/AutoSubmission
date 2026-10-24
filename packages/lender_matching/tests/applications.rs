mod common;
#[path = "../application/tests/support/mod.rs"]
mod support;

use std::path::{Path, PathBuf};
use std::process::Output;

use common::*;
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
