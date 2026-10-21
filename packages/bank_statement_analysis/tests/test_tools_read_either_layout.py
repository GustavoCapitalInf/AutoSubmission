"""Research tools must see the same project on either side of the pure rename."""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.git_layout import PACKAGE_DIR, PACKAGE_PREFIX

PRE_MOVE = "8ccd1d46"
POST_MOVE = "ded21ce2"
DEFAULT_BASE = "10cc722"
SCHEMA_BASE = "223e21d0"
APPS_ADDED = "04c926de"
REPO_DIR = PACKAGE_DIR.parents[1]
#: An amount on unchanged lines of tests/test_no_statement_hardcodes.py since before DEFAULT_BASE. A plain diff
#: across the move reports that heavily changed file as wholly added. Built here so this file never adds it.
INHERITED_AMOUNT = f"{1111.11:,.2f}"


@pytest.fixture(autouse=True, scope="module")
def history():
    for ref in (PRE_MOVE, POST_MOVE, DEFAULT_BASE, SCHEMA_BASE, APPS_ADDED):
        proc = subprocess.run(
            ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
            cwd=PACKAGE_DIR, capture_output=True,
        )
        if proc.returncode:
            pytest.skip(f"history does not contain {ref} (shallow clone)")
    renames = subprocess.run(
        ["git", "diff", "--name-status", "-M100%", PRE_MOVE, POST_MOVE],
        cwd=PACKAGE_DIR, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    assert renames and all(line.startswith("R100\t") for line in renames)


@pytest.fixture(autouse=True)
def from_the_package_folder(monkeypatch):
    monkeypatch.chdir(PACKAGE_DIR)


@pytest.fixture(params=["default", "diff.relative"])
def git_config(request, monkeypatch):
    if request.param == "diff.relative":
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "diff.relative")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")


@pytest.fixture
def checkout_at(tmp_path):
    def make(ref):
        clone = tmp_path / f"checkout-{ref}"
        subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout", str(REPO_DIR), str(clone)], check=True)
        sha = subprocess.run(["git", "rev-parse", ref], cwd=PACKAGE_DIR, capture_output=True, text=True,
                             check=True).stdout.strip()
        subprocess.run(["git", "update-ref", "--no-deref", "HEAD", sha], cwd=clone, check=True)
        return clone
    return make


@pytest.fixture
def absent_index(tmp_path, monkeypatch):
    objects = subprocess.run(["git", "rev-parse", "--git-path", "objects"], cwd=PACKAGE_DIR,
                             capture_output=True, text=True, check=True).stdout.strip()
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "index"))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(tmp_path / "objects"))
    monkeypatch.setenv("GIT_ALTERNATE_OBJECT_DIRECTORIES", str((PACKAGE_DIR / objects).resolve()))
    (tmp_path / "objects").mkdir()


@pytest.fixture
def intent_to_add_index(absent_index):
    for args in (["read-tree", "HEAD"], ["update-index", "--force-remove", "--", "README.md"],
                 ["add", "--intent-to-add", "--", "README.md"]):
        subprocess.run(["git", *args], cwd=PACKAGE_DIR, capture_output=True, check=True)


@pytest.fixture
def inherited_line():
    source = subprocess.run(
        ["git", "show", f"{DEFAULT_BASE}:tests/test_no_statement_hardcodes.py"],
        cwd=PACKAGE_DIR, capture_output=True, text=True, check=True,
    ).stdout
    return next(line.strip() for line in source.splitlines() if INHERITED_AMOUNT in line and "docstring" in line)


@pytest.fixture
def analysis_modules():
    import analysis

    saved = {name: module for name, module in sys.modules.items()
             if name == "analysis" or name.startswith("analysis.")}
    attributes = vars(analysis).copy()
    yield
    for name in list(sys.modules):
        if name == "analysis" or name.startswith("analysis."):
            del sys.modules[name]
    sys.modules.update(saved)
    vars(analysis).clear()
    vars(analysis).update(attributes)


def test_batch9_census_reads_either_layout():
    from tools.batch9_census import git_show, parse_b8_census

    path = "docs/moneythumb-replacement/CENSUS_BATCH8_DIGITAL.md"
    before = parse_b8_census(git_show(PRE_MOVE, path))
    after = parse_b8_census(git_show(POST_MOVE, path))
    assert before
    assert after == before


def test_desccols_loads_either_layout(tmp_path, monkeypatch):
    import fitz
    from tools.desccols_movement import base_module

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "An invented page without a statement table")
        pdf = document.tobytes()
    before = base_module(PRE_MOVE)
    after = base_module(POST_MOVE)
    assert before.native_statement(pdf) is None
    assert after.native_statement(pdf) is None
    assert Path(after.__file__).read_bytes() == Path(before.__file__).read_bytes()


@pytest.mark.parametrize("default", [False, True], ids=["rename", "default"])
def test_glance_materialises_analysis(tmp_path, default):
    from tools.glance_family_replay import materialise, parse_args

    args = parse_args([
        "--rows", str(tmp_path / "rows.csv"), "--data-dir", str(tmp_path),
        "--baseline-settings-key", "fabricated",
    ])
    ref = args.base if default else PRE_MOVE
    before = materialise(ref, tmp_path / "before")
    if default:
        assert (before / "analysis" / "pipeline.py").is_file()
    else:
        after = materialise(POST_MOVE, tmp_path / "after")
        files = {path.relative_to(before): path.read_bytes()
                 for path in (before / "analysis").rglob("*.py")}
        assert files
        assert files == {path.relative_to(after): path.read_bytes()
                         for path in (after / "analysis").rglob("*.py")}


def test_coreenc_keeps_baseline_vocabulary(tmp_path, capsys):
    from tools.coreenc_archive_census import _literals

    shas = tmp_path / "shas.txt"
    shas.write_text("")
    reports = []
    for ref in (PRE_MOVE, POST_MOVE):
        out = tmp_path / f"{ref}.json"
        assert _literals(SimpleNamespace(
            data_dir=tmp_path, shas=shas, repo=PACKAGE_DIR, base=ref,
            out=out, show_residual=False,
        )) == 0
        reports.append(json.loads(out.read_text())["summary"])
        capsys.readouterr()
    assert reports[0]["base_vocabulary_files"] > 0
    for key in ("base_vocabulary_files", "base_vocabulary_literals"):
        assert reports[0][key] == reports[1][key]


def test_coreiss2_recognises_inherited_words(tmp_path, monkeypatch, capsys):
    from tools import coreiss2_probe as probe

    monkeypatch.setattr(probe, "census_family", lambda name: {"A" * 64})
    monkeypatch.setattr(probe, "document_text", lambda artifacts, sha: "Statement")
    for ref in (PRE_MOVE, POST_MOVE):
        probe.run_privacy(tmp_path, ref)
        output = capsys.readouterr().out
        match = re.search(r"archive words NOVEL .*: (\d+)", output)
        assert match is not None
        assert int(match[1]) == 0


def test_lili_inherited_content_includes_project_files():
    from tools.lili_privacy_scan import haystacks

    _, inherited = haystacks(DEFAULT_BASE)
    source = (PACKAGE_DIR / "analysis" / "eq_bank_scanned.py").read_text()
    included = source in inherited
    assert included, "the inherited haystack omitted a changed analysis module"


def test_lili_does_not_author_lines_the_base_had(inherited_line):
    from tools.lili_privacy_scan import haystacks

    authored, _ = haystacks(DEFAULT_BASE)
    assert authored
    assert inherited_line not in authored


@pytest.mark.usefixtures("git_config")
def test_lili_inherited_content_includes_files_outside_the_package():
    from tools.lili_privacy_scan import haystacks

    _, inherited = haystacks(PRE_MOVE)
    assert (REPO_DIR / "apps" / "auto_submission" / "README.md").read_text() in inherited


def test_privacy_diff_has_the_same_sites_and_exclusions():
    from tools.privacy_scan_branch import added_lines, excluded_by

    before = added_lines(DEFAULT_BASE, PRE_MOVE)
    after = added_lines(DEFAULT_BASE, POST_MOVE)
    assert before
    assert sorted((path.removeprefix("../../"), number, text) for path, number, text in after) == sorted(before)
    dates = [(path, text) for path, _, text in after
             if path.startswith("docs/") and "2026-08-28" in text]
    assert dates
    assert all(excluded_by("DATES", path, "2026-08-28", text) == "docs_session_date"
               for path, text in dates)


@pytest.mark.usefixtures("git_config")
def test_privacy_diff_scans_files_outside_the_package():
    from tools.privacy_scan_branch import added_lines

    files = {path for path, _, _ in added_lines(PRE_MOVE, APPS_ADDED)}
    assert {"../../apps/auto_submission/README.md", "../../.github/workflows/corpus-gate.yml",
            "../../README.md", "README.md"} <= files


@pytest.mark.parametrize("finding", ["docs_date", "named_residue"])
def test_privacy_tree_keeps_path_classification(tmp_path, monkeypatch, capsys, finding):
    from telemetry import run_of_record
    from tools import privacy_scan_branch as scan

    source = subprocess.run(
        ["git", "show", f"{PRE_MOVE}:docs/adb-audit-results.csv"],
        cwd=PACKAGE_DIR, capture_output=True, text=True, check=True,
    ).stdout
    round_money = next(token for token in scan.MONEY_RE.findall(source) if token.endswith(".00"))
    with sqlite3.connect(tmp_path / "webapp.db"):
        pass
    monkeypatch.setattr(run_of_record, "partitions_for_run", lambda *a, **kw: None)
    monkeypatch.setattr(scan, "rows_by_sha", lambda run: {})
    monkeypatch.setattr(scan, "cached_text", lambda *a: f"{round_money} 2026-08-28")
    monkeypatch.setattr(scan, "tracked_text", lambda ref: "")
    reports = []
    for ref in (PRE_MOVE, POST_MOVE):
        out = tmp_path / f"{ref}.json"
        scan.main([
            "--data-dir", str(tmp_path), "--run", str(tmp_path), "--sha", "A" * 64,
            "--base", PRE_MOVE, "--ref", ref, "--include-tree", "--out", str(out),
        ])
        reports.append(json.loads(out.read_text()))
        capsys.readouterr()
    if finding == "docs_date":
        counts = [report["excluded_by_rule"]["docs_session_date"] for report in reports]
        assert counts[0] > 0
        assert counts[1] == counts[0]
    else:
        counts = [report["residue_by_named_class"]["benchmark_truth_csv"]
                  for report in reports]
        assert counts[0] > 0
        assert counts[1] == counts[0]
        hits = [hit for hit in reports[1]["hits"]
                if hit["file"] == "tree:docs/adb-audit-results.csv"
                and hit["class"] == "MONEY" and hit["token"] == round_money]
        assert hits
        assert all(hit["excluded_by"] is None for hit in hits)


def test_scanhyg_rename_installs_no_changed_modules(analysis_modules):
    from tools.scanhyg_family_replay import install_modules

    assert install_modules(PACKAGE_DIR, POST_MOVE, PRE_MOVE) == []


@pytest.mark.usefixtures("git_config")
def test_scanhyg_installs_the_same_historical_modules(analysis_modules):
    from tools.scanhyg_family_replay import install_modules

    before = install_modules(PACKAGE_DIR, PRE_MOVE, SCHEMA_BASE)
    after = install_modules(PACKAGE_DIR, POST_MOVE, SCHEMA_BASE)
    assert before == ["schema"]
    assert after == before


def test_scanhyg_day_gate_reads_either_layout(analysis_modules):
    from tools.scanhyg_gate_probe import day_gate_differential

    before = day_gate_differential(SimpleNamespace(base=PRE_MOVE))
    after = day_gate_differential(SimpleNamespace(base=POST_MOVE))
    before.pop("base")
    after.pop("base")
    assert before["same"] > 0
    assert after == before


@pytest.mark.usefixtures("git_config")
def test_train_stops_on_a_conflict_outside_the_package(monkeypatch, capsys):
    from tools import train_merge_one as train

    real_run = train.run

    def fabricated_merge(*args, check=True):
        if args[1] == "diff":
            historical = [arg.replace("--diff-filter=U", "--diff-filter=AMR") for arg in args]
            return real_run(*historical, DEFAULT_BASE, APPS_ADDED, "--",
                            f":(top){PACKAGE_PREFIX}{train.W3}", ":(top)apps")
        if args[1] == "merge-base":
            return subprocess.CompletedProcess(args, 0, PRE_MOVE.encode(), b"")
        assert args[1] == "merge"
        return subprocess.CompletedProcess(args, 1, b"", b"")

    monkeypatch.setattr(train, "run", fabricated_merge)
    assert train.main(["train_merge_one", APPS_ADDED, "fabricated"]) == 3
    output = capsys.readouterr().out
    assert "apps/auto_submission/README.md" in output
    assert "NON-W3 CONFLICT" in output


def test_train_reads_either_layout():
    from tools.train_merge_one import blob

    before = blob(PRE_MOVE)
    assert before
    assert blob(POST_MOVE) == before


def test_train_recognises_a_project_conflict(monkeypatch, capsys):
    from tools import train_merge_one as train

    real_run = train.run

    def fabricated_merge(*args, check=True):
        if args[1] == "diff":
            historical = [arg.replace("--diff-filter=U", "--diff-filter=AMR") for arg in args]
            return real_run(*historical, DEFAULT_BASE, POST_MOVE, "--", train.W3)
        if args[1] == "merge-base":
            return subprocess.CompletedProcess(args, 0, PRE_MOVE.encode(), b"")
        assert args[1] == "merge"
        return subprocess.CompletedProcess(args, 1, b"", b"")

    monkeypatch.setattr(train, "run", fabricated_merge)
    monkeypatch.setattr(train, "blob", lambda rev: {PRE_MOVE: b"base", "HEAD": b"ours",
                                                  POST_MOVE: b"changed"}[rev])
    assert train.main(["train_merge_one", POST_MOVE, "fabricated"]) == 4
    assert "W3 SHAPE VIOLATION" in capsys.readouterr().out


def test_welch_does_not_add_lines_the_base_had(inherited_line):
    from tools.welch_privacy_scan import _added_lines

    added = _added_lines(DEFAULT_BASE)
    assert added
    assert inherited_line.upper() not in added


def test_coreiss2_does_not_count_an_amount_the_base_had(tmp_path, monkeypatch, capsys):
    from tools import coreiss2_probe as probe

    monkeypatch.setattr(probe, "census_family", lambda name: {"A" * 64})
    monkeypatch.setattr(probe, "document_text", lambda artifacts, sha: INHERITED_AMOUNT)
    probe.run_privacy(tmp_path, DEFAULT_BASE)
    assert "FOUND: figures/dates/accounts=0 " in capsys.readouterr().out


def test_withheldtd_does_not_count_an_amount_the_base_had(tmp_path, monkeypatch, capsys):
    from tools import withheldtd_privacy_scan as scan

    monkeypatch.setattr(scan, "texts", lambda rows, data_dir: iter([("A" * 64, INHERITED_AMOUNT)]))
    scan.main(["--base", DEFAULT_BASE, "--rows", str(tmp_path / "rows.csv"), "--data-dir", str(tmp_path)])
    assert "A. DISTINCTIVE TOKENS IN THE DIFF: 0" in capsys.readouterr().out


def test_coreenc_diffs_the_repo_it_is_given(tmp_path, capsys, checkout_at):
    from tools.coreenc_archive_census import _literals

    shas = tmp_path / "shas.txt"
    shas.write_text("")
    out = tmp_path / "report.json"
    assert _literals(SimpleNamespace(
        data_dir=tmp_path, shas=shas, repo=checkout_at(PRE_MOVE), base=PRE_MOVE,
        out=out, show_residual=False,
    )) == 0
    assert json.loads(out.read_text())["summary"]["added_lines_literals"] == 0


def test_withheldgrids_diffs_the_repo_it_is_given(tmp_path, capsys, checkout_at):
    from tools.withheldgrids_privacy_scan import main

    shas = tmp_path / "shas.txt"
    shas.write_text("")
    main([
        "--shas", str(shas), "--data-dir", str(tmp_path), "--repo", str(checkout_at(PRE_MOVE)),
        "--baseline-settings-key", "fabricated", "--base-rev", PRE_MOVE,
    ])
    assert re.search(r"files changed by the branch\s+= 0\n", capsys.readouterr().out)


def test_withheldgrids_selects_tests_from_the_repo_it_is_given(checkout_at):
    from tools.withheldgrids_tests_at_base import added_test_names

    assert added_test_names(checkout_at(DEFAULT_BASE), DEFAULT_BASE) == []


def test_scanhyg_reads_the_repo_it_is_given(analysis_modules, checkout_at):
    from tools.scanhyg_family_replay import install_modules

    assert install_modules(checkout_at(SCHEMA_BASE), SCHEMA_BASE, SCHEMA_BASE) == []


def test_scanhyg_reads_sources_at_a_ref_of_the_repo_it_is_given(analysis_modules, checkout_at, monkeypatch):
    from tools import scanhyg_family_replay as replay

    def schema(ref):
        return subprocess.run(["git", "show", f"{ref}:analysis/schema.py"], cwd=PACKAGE_DIR,
                              capture_output=True, check=True).stdout

    back = next(n for n in range(1, 500) if schema(f"{PRE_MOVE}~{n}") != schema(PRE_MOVE))
    expected = schema(f"{PRE_MOVE}~{back}")
    shown = []
    real_run = subprocess.run

    def recording(argv, **kwargs):
        proc = real_run(argv, **kwargs)
        if "show" in argv:
            shown.append(proc.stdout)
        return proc

    monkeypatch.setattr(replay.subprocess, "run", recording)
    assert replay.install_modules(checkout_at(PRE_MOVE), f"HEAD~{back}", SCHEMA_BASE) == ["schema"]
    assert shown == [expected]


def test_withheldgrids_dates_reads_the_repo_it_is_given(checkout_at):
    from tools.withheldgrids_srcdates_audit import _base_source

    expected = subprocess.run(["git", "show", f"{DEFAULT_BASE}:analysis/dates.py"], cwd=PACKAGE_DIR,
                              capture_output=True, text=True, check=True).stdout
    assert _base_source("HEAD", checkout_at(DEFAULT_BASE)) == expected


def test_withheldgrids_materialises_the_base_of_the_repo_it_is_given(tmp_path, monkeypatch, capsys, checkout_at):
    from tools import withheldgrids_tests_at_base as tool

    monkeypatch.setattr(tool, "added_test_names", lambda *a: ["test_fabricated"])
    real_run = subprocess.run

    def fabricated_pytest(args, **kwargs):
        if args[0] == sys.executable:
            return subprocess.CompletedProcess(args, 0, "PASSED tests/x.py::test_fabricated\n", "")
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fabricated_pytest)
    repo = checkout_at(DEFAULT_BASE)
    for path in tool.TEST_FILES:
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("")
    work = tmp_path / "work"
    assert tool.main(["--repo", str(repo), "--base-rev", "HEAD", "--work", str(work), "--keep"]) == 0
    expected = real_run(["git", "show", f"{DEFAULT_BASE}:analysis/dates.py"], cwd=PACKAGE_DIR,
                        capture_output=True, check=True).stdout
    assert (work / "base_tree" / "analysis" / "dates.py").read_bytes() == expected


@pytest.mark.parametrize("index", ["intent_to_add_index", "absent_index"])
def test_lili_scans_the_working_tree_whatever_the_index(request, index):
    from tools.lili_privacy_scan import haystacks

    request.getfixturevalue(index)
    authored, _ = haystacks("HEAD")
    assert isinstance(authored, str)


@pytest.mark.parametrize("index", ["intent_to_add_index", "absent_index"])
def test_withheldtd_scans_the_working_tree_whatever_the_index(request, index, tmp_path, monkeypatch, capsys):
    from tools import withheldtd_privacy_scan as scan

    request.getfixturevalue(index)
    monkeypatch.setattr(scan, "texts", lambda rows, data_dir: iter([("A" * 64, "fabricated")]))
    scan.main(["--base", "HEAD", "--rows", str(tmp_path / "rows.csv"), "--data-dir", str(tmp_path)])
    assert "documents read 1 of 1" in capsys.readouterr().out


def test_welch_reads_the_same_tracked_text():
    from tools.welch_privacy_scan import _tracked_text

    before = _tracked_text(PRE_MOVE)
    after = _tracked_text(POST_MOVE)
    assert "STATEMENT" in before
    assert Counter(after.splitlines()) == Counter(before.splitlines())


@pytest.mark.parametrize("base", [PRE_MOVE, DEFAULT_BASE])
def test_withheldgrids_recognises_inherited_literals(base):
    from tools.withheldgrids_privacy_scan import _in_base

    assert _in_base(PACKAGE_DIR, base, "Statement")
    assert _in_base(PACKAGE_DIR, POST_MOVE, "Statement")


@pytest.mark.usefixtures("git_config")
@pytest.mark.parametrize("name", ["analysis/dates.py", "../../README.md", "../../apps/auto_submission/README.md"],
                         ids=["package", "root", "apps"])
def test_withheldgrids_checks_control_bytes_in_changed_files(tmp_path, monkeypatch, capsys, name):
    from tools.withheldgrids_privacy_scan import main

    shas = tmp_path / "shas.txt"
    shas.write_text("")
    original = Path.read_bytes
    target = (PACKAGE_DIR / name).resolve()
    monkeypatch.setattr(Path, "read_bytes", lambda path: b"\x01" if path.resolve() == target else original(path))
    assert main([
        "--shas", str(shas), "--data-dir", str(tmp_path), "--repo", str(PACKAGE_DIR),
        "--baseline-settings-key", "fabricated",
    ]) == 2
    assert f"control bytes in {name}" in capsys.readouterr().out


def test_withheldgrids_skips_files_the_move_only_renamed(tmp_path, capsys):
    from tools.withheldgrids_privacy_scan import main

    shas = tmp_path / "shas.txt"
    shas.write_text("")
    main([
        "--shas", str(shas), "--data-dir", str(tmp_path), "--repo", str(PACKAGE_DIR),
        "--baseline-settings-key", "fabricated", "--base-rev", PRE_MOVE,
    ])
    assert "pdfFolderIcon" not in capsys.readouterr().out


def test_withheldgrids_recognises_literals_outside_the_package():
    from tools.withheldgrids_privacy_scan import _in_base

    assert _in_base(PACKAGE_DIR, APPS_ADDED, "Auto-Submission platform")


def test_withheldgrids_dates_reads_either_layout():
    from tools.withheldgrids_srcdates_audit import _base_source

    before = _base_source(PRE_MOVE, PACKAGE_DIR)
    assert before
    assert _base_source(POST_MOVE, PACKAGE_DIR) == before


def test_withheldgrids_selects_the_same_added_tests():
    from tools.withheldgrids_tests_at_base import added_test_names

    assert added_test_names(PACKAGE_DIR, PRE_MOVE) == added_test_names(PACKAGE_DIR, POST_MOVE)


@pytest.mark.usefixtures("git_config")
def test_withheldgrids_default_leaves_out_tests_the_base_had():
    from tools.withheldgrids_tests_at_base import TEST_FILES, added_test_names, parse_args

    defined = {name for path in TEST_FILES
               for name in re.findall(r"^def (test_\w+)", (PACKAGE_DIR / path).read_text(), re.M)}
    selected = set(added_test_names(PACKAGE_DIR, parse_args([]).base_rev))
    assert selected
    assert selected < defined


def test_withheldgrids_materialises_the_same_base(tmp_path, monkeypatch, capsys):
    from tools import withheldgrids_tests_at_base as tool

    monkeypatch.setattr(tool, "added_test_names", lambda *a: ["test_fabricated"])
    real_run = subprocess.run

    def fabricated_pytest(args, **kwargs):
        if args[0] == sys.executable:
            return subprocess.CompletedProcess(args, 0, "PASSED tests/x.py::test_fabricated\n", "")
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fabricated_pytest)
    sources = []
    for ref in (PRE_MOVE, POST_MOVE):
        work = tmp_path / ref
        assert tool.main([
            "--repo", str(PACKAGE_DIR), "--base-rev", ref, "--work", str(work), "--keep",
        ]) == 0
        sources.append((work / "base_tree" / "analysis" / "dates.py").read_bytes())
        capsys.readouterr()
    assert sources[0] == sources[1]
