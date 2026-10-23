mod common;
#[path = "../application/tests/support/mod.rs"]
mod support;

use std::path::Path;
use std::process::{Command, Output};

use common::TempDir;
use lender_matching_application::fields::{BusinessField, FieldId};
use support::form::{Canvas, Form, Layout, certificate, pdfescape, sample_values, word};
use support::pdf::{FakePage, FakePdf};

fn application(form: &Form) -> Vec<u8> {
    let pages =
        vec![form.draw(FakePage::new()), certificate(FakePage::new(), &[("SAMPLE OWNER", "owner@example.com")])];
    FakePdf::new(pages).created(2026, 10, 21).to_bytes()
}

fn contract() -> Vec<u8> {
    let mut page = FakePage::new().text("TimesNewRomanPS-BoldMT", 12.0, 40.0, 40.0, "RECEIVABLES PURCHASE AGREEMENT");
    for line in 0..10 {
        page = page.text("ArialMT", 9.0, 40.0, 80.0 + 12.0 * line as f32, "SAMPLE TERMS OF THE AGREEMENT ARE HERE");
    }
    FakePdf::new(vec![page]).to_bytes()
}

fn evaluate(folder: &Path, library: Option<&Path>, args: &[&str]) -> Output {
    let mut command = Command::new(env!("CARGO_BIN_EXE_lender-matching"));
    command.env_remove("PDFIUM_LIBRARY").args(["applications", "evaluate"]).arg(folder).args(args);
    if let Some(library) = library {
        command.env("PDFIUM_LIBRARY", library);
    }
    command.output().unwrap()
}

#[test]
fn evaluate_prints_counts_and_never_a_value_or_a_file_name() {
    let Some(library) = support::pdfium_library() else { return };
    let corpus = TempDir::new();
    let reports = TempDir::new();
    let folder = corpus.path().join("CONTOSO applications");
    std::fs::create_dir_all(folder.join("NORTHWIND nested")).unwrap();
    let start = FieldId::Business(BusinessField::StartDate);
    let unknown = Form { layout: Layout { dy: |dy| dy * 1.1, ..word() }, ..Form::word() };
    let files: Vec<(&str, Vec<u8>)> = vec![
        ("CONTOSO word.pdf", application(&Form::word())),
        ("NORTHWIND nested/FABRIKAM escape.PDF", application(&Form { layout: pdfescape(), ..Form::word() })),
        ("SAMPLE 2019.pdf", application(&Form::word().set(start, "2019"))),
        ("SAMPLE 2018.pdf", application(&Form::word().set(start, "2018"))),
        ("SAMPLE 2017.pdf", application(&Form::word().set(start, "2017"))),
        ("SAMPLE quarter.pdf", application(&Form::word().set(start, "Q2 2019"))),
        ("FABRIKAM contract.pdf", contract()),
        ("SAMPLE unknown.pdf", application(&unknown)),
        ("SAMPLE broken.pdf", b"SAMPLE OWNER 900-12-3456, not a PDF".to_vec()),
        ("CONTOSO notes.txt", b"SAMPLE OWNER".to_vec()),
    ];
    for (name, bytes) in &files {
        std::fs::write(folder.join(name), bytes).unwrap();
    }
    let json = reports.path().join("report.json");
    let output = evaluate(&folder, Some(&library), &["--offsets", "--shapes", "--json", json.to_str().unwrap()]);
    let stdout = String::from_utf8(output.stdout).unwrap();
    let stderr = String::from_utf8(output.stderr).unwrap();
    assert!(output.status.success(), "{stderr}");
    for expected in [
        "parser 2, 9 PDF files, 1 other files skipped",
        "documents     application 6 · manual_entry.unknown_layout 1 · refused.contract 1",
        "failures      not_pdf 1",
        "layouts       pdfescape 1 · word 5",
        "signer check  agreement 6",
        "9999 ×3 · other ×1",
        "dy +15 ×1 · +18 ×5 · +20 ×1",
    ] {
        assert!(stdout.contains(expected), "missing {expected:?} in\n{stdout}");
    }
    let report = std::fs::read_to_string(&json).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&report).unwrap();
    assert_eq!(parsed["documents"]["application"], 6);
    assert_eq!(parsed["fields"]["business.start_date"]["refused.format"], 4);

    let mut secrets: Vec<String> = sample_values().into_iter().map(|(_, value)| value.to_string()).collect();
    secrets.extend(
        ["CONTOSO", "NORTHWIND", "FABRIKAM", "SAMPLE", "owner@example.com", "Q2 2019", "900-12-3456"].map(String::from),
    );
    secrets.extend(files.iter().map(|(name, _)| name.to_string()));
    secrets.push(corpus.path().to_string_lossy().into_owned());
    for secret in secrets.iter().filter(|secret| secret.len() > 3) {
        for (what, text) in [("stdout", &stdout), ("stderr", &stderr), ("JSON", &report)] {
            assert!(!text.contains(secret.as_str()), "{what} holds a fabricated value or a file name");
        }
    }
}

#[test]
fn evaluate_needs_pdfium() {
    let corpus = TempDir::new();
    let output = evaluate(corpus.path(), None, &[]);
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("set PDFIUM_LIBRARY"));
}

#[test]
fn an_unlistable_folder_is_refused_without_its_path() {
    let corpus = TempDir::new();
    let missing = corpus.path().join("SAMPLE missing");
    let output = evaluate(&missing, Some(&std::env::temp_dir().join("libpdfium.so")), &[]);
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(!output.status.success() && stderr.contains("cannot list the folder"), "{stderr}");
    assert!(!stderr.contains("SAMPLE"));
}
