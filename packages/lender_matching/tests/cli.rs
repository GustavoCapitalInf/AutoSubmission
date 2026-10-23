//! The command line: the import's dry run and apply, accounts, tokens, and the start-up refusals.

mod common;

use common::*;

fn stdout(output: &std::process::Output) -> String {
    String::from_utf8_lossy(&output.stdout).to_string()
}

fn stderr(output: &std::process::Output) -> String {
    String::from_utf8_lossy(&output.stderr).to_string()
}

#[test]
fn the_import_is_a_dry_run_until_apply_and_a_rerun_changes_nothing() {
    let data = TempDir::new();
    let workbook = seed_workbook(data.path());
    let path = workbook.to_str().unwrap();
    for _ in 0..2 {
        let dry = cli_ok(data.path(), &["import-info-hub", path]);
        assert!(dry.contains("4 rows: 4 create") && dry.contains("Dry run: nothing was written."), "{dry}");
    }
    let applied = cli_ok(data.path(), &["import-info-hub", path, "--apply"]);
    assert!(applied.contains("4 create") && applied.contains("Applied."), "{applied}");
    let again = cli_ok(data.path(), &["import-info-hub", path, "--apply"]);
    assert!(again.contains("0 create, 0 update, 4 unchanged"), "{again}");
    let capped = cli_ok(data.path(), &["import-info-hub", path, "--open-positions", "capped"]);
    assert!(capped.contains("1 update"), "a new reading updates the 1-5+ lender: {capped}");
}

#[test]
fn an_import_with_blockers_writes_nothing_and_fails() {
    let data = TempDir::new();
    let workbook = workbook(
        data.path(),
        &[
            &[("Lender Name", "CONTOSO CAPITAL"), ("Record Id", "REC-1"), ("Credit Score", "600")],
            &[("Lender Name", "CONTOSO CAPITAL TWO"), ("Record Id", "REC-1")],
            &[("Credit Score", "650")],
        ],
    );
    let output = cli(data.path(), &["import-info-hub", workbook.to_str().unwrap(), "--apply"]);
    assert!(!output.status.success());
    let report = stdout(&output);
    assert!(report.contains("BLOCKER lines 2 and 3") && report.contains("BLOCKER line 4"), "{report}");
    let dry = cli(data.path(), &["import-info-hub", workbook.to_str().unwrap()]);
    assert!(!dry.status.success(), "a dry run with blockers fails too");
    assert!(stdout(&dry).contains("1 create"), "nothing was written: {}", stdout(&dry));

    let unreadable = data.path().join("not-a-workbook.xlsx");
    std::fs::write(&unreadable, b"SAMPLE").unwrap();
    let output = cli(data.path(), &["import-info-hub", unreadable.to_str().unwrap()]);
    assert!(!output.status.success() && stderr(&output).contains("not a readable .xlsx or .xls workbook"));
}

#[test]
fn accounts_and_tokens_are_checked() {
    let data = TempDir::new();
    let mut short = command(data.path())
        .args(["user", "add", "sample.editor", "--role", "editor", "--password-stdin"])
        .stdin(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap();
    std::io::Write::write_all(&mut short.stdin.take().unwrap(), b"short\n").unwrap();
    let output = short.wait_with_output().unwrap();
    assert!(!output.status.success() && stderr(&output).contains("at least 12 characters"));
    add_user(data.path(), "sample.editor", "editor");

    let revoked = cli(data.path(), &["token", "revoke", "nobody"]);
    assert!(!revoked.status.success() && stderr(&revoked).contains("no live token is named nobody"));
    let token = token(data.path(), "auto-submission", &["match"]);
    assert!(token.starts_with("lm_") && token.len() > 40);
    let twice = cli(data.path(), &["token", "create", "auto-submission", "--scope", "read"]);
    assert!(!twice.status.success(), "one live token per name");
    let no_scope = cli(data.path(), &["token", "create", "dashboard"]);
    assert!(!no_scope.status.success(), "a token needs a scope");
}

#[test]
fn the_server_refuses_an_unsafe_start() {
    let inside = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("target").join("cli-test-data");
    let output = cli(&inside, &["token", "create", "x", "--scope", "read"]);
    assert!(!output.status.success() && stderr(&output).contains("inside the git work tree"), "{}", stderr(&output));
    let _ = std::fs::remove_dir_all(inside);

    let data = TempDir::new();
    type Env<'a> = &'a [(&'a str, &'a str)];
    let refusals: [(Env, &str, &str); 4] = [
        (&[], "0.0.0.0:0", "set PUBLIC_URL"),
        (&[("PUBLIC_URL", "http://lenders.contoso.example")], "0.0.0.0:0", "must start with https://"),
        (&[("ANALYSIS_API_URL", "https://analysis.contoso.example/api/v1")], "127.0.0.1:0", "or neither"),
        (
            &[("ANALYSIS_API_URL", "http://analysis.contoso.example/api/v1"), ("ANALYSIS_API_TOKEN", "t")],
            "127.0.0.1:0",
            "must use https://",
        ),
    ];
    for (env, bind, message) in refusals {
        let output = command(data.path()).args(["serve", "--bind", bind]).envs(env.iter().copied()).output().unwrap();
        assert!(!output.status.success() && stderr(&output).contains(message), "{env:?}: {}", stderr(&output));
    }
}
