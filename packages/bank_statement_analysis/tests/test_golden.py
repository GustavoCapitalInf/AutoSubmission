from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

from tools import golden

JOB = "0f8fad5b-d9cb-469f-a165-70867728950e"
OTHER = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
THIRD = "16fd2706-8baf-433b-82eb-8c7fada847da"
PLAN = json.dumps(golden.make_plan([("CONTOSO/a.pdf", 1)], shards=1)).encode()
RESPONSES = [f"s0000.{profile}.{kind}" for profile in ("default", "flipped")
             for kind in ("analysis", "json", "csv", "xlsx")]
BODY = b'200 application/json\n\n{"total": "SAMPLE 1"}'


def _xlsx(cell: str, stamp: str, when: tuple) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo("xl/worksheets/sheet1.xml", when),
                         f'<sheetData><row r="1"><c r="A1"><v>{cell}</v></c></row></sheetData>')
        archive.writestr(zipfile.ZipInfo("docProps/core.xml", when),
                         f"<dcterms:created>{stamp}</dcterms:created>")
    return out.getvalue()


def _shard(work: Path, bodies: dict[str, bytes], outcomes: dict[str, str] | None = None) -> Path:
    """Shard 0 of a run as the shard leaves it: each response gzipped beside a manifest of their hashes."""
    out = work / "capture" / "shard0"
    out.mkdir(parents=True)
    for key, body in bodies.items():
        (out / f"{key}.gz").write_bytes(gzip.compress(body))
    manifest = {"responses": {key: hashlib.sha256(body).hexdigest() for key, body in bodies.items()},
                "statements": outcomes or {"0": "analysed"}, "packages": {}}
    (out / "manifest.json").write_text(json.dumps(manifest))
    return work


def _finished(work: Path, changed: dict[str, bytes] | None = None, plan: bytes = PLAN) -> Path:
    """A finished run over PLAN: statement 0 analysed, its eight responses BODY unless changed."""
    _shard(work, {key: BODY for key in RESPONSES} | (changed or {}))
    golden.seal(work, plan)
    return work


def _exit(monkeypatch, *args) -> int | str | None:
    monkeypatch.setattr(sys, "argv", ["golden.py", *map(str, args)])
    try:
        golden.main()
    except SystemExit as exited:
        return exited.code
    return 0


def test_plan_cuts_each_folder_into_packages_of_two_to_six_within_one_shard():
    files = [(f"CONTOSO BANK/statement-{i}.pdf", 100 + i) for i in range(9)]
    files += [("FABRIKAM/only.pdf", 50), ("NORTHWIND/a.pdf", 10), ("NORTHWIND/older/b.pdf", 20)]
    plan = golden.make_plan(files, shards=3)

    assert plan == golden.make_plan(list(reversed(files)), shards=3)
    assert [s["path"] for s in plan["statements"]] == sorted(path for path, _ in files)
    assert [len(p["members"]) for p in plan["packages"]] == [2, 3, 4, 2]
    for package in plan["packages"]:
        members = [plan["statements"][i] for i in package["members"]]
        assert len({m["path"].split("/")[0] for m in members}) == 1
        assert {m["shard"] for m in members} == {package["shard"]}
    packed = {i for p in plan["packages"] for i in p["members"]}
    assert [plan["statements"][i]["path"] for i in range(len(files)) if i not in packed] == ["FABRIKAM/only.pdf"]
    assert {s["shard"] for s in plan["statements"]} == {0, 1, 2}


def test_an_xlsx_is_compared_by_its_parts_with_the_creation_stamp_masked():
    first = golden.canonical(200, "application/xlsx", "",
                             _xlsx("1", "2026-01-02T03:04:05+00:00", (2026, 1, 2, 3, 4, 6)), {})
    later = golden.canonical(200, "application/xlsx", "",
                             _xlsx("1", "2026-02-03T04:05:06+00:00", (2026, 2, 3, 4, 5, 8)), {})
    changed = golden.canonical(200, "application/xlsx", "",
                               _xlsx("2", "2026-01-02T03:04:05+00:00", (2026, 1, 2, 3, 4, 6)), {})

    assert first == later
    assert first != changed


def test_only_the_ids_the_tool_issued_become_tokens():
    body = json.dumps({"job": JOB, "reference": OTHER}).encode()

    assert golden.canonical(200, "application/json", "", body, {JOB.encode(): b"job-0007"}) == (
        b'200 application/json\n\n{"job": "job-0007", "reference": "%s"}' % OTHER.encode())
    responses = {"text/csv": lambda ref: f"section,field,value\r\nSAMPLE,reference,{ref}\r\n".encode(),
                 "application/xlsx": lambda ref: _xlsx(ref, "2026-01-02", (2026, 1, 2, 3, 4, 6))}
    for content_type, response in responses.items():
        assert (golden.canonical(200, content_type, "", response(OTHER), {}) !=
                golden.canonical(200, content_type, "", response(THIRD), {}))


def test_compare_exits_zero_when_identical_and_one_when_a_response_differs(tmp_path, monkeypatch, capsys):
    a = _finished(tmp_path / "a")
    b = _finished(tmp_path / "b")
    c = _finished(tmp_path / "c", {"s0000.flipped.csv": b"200 text/csv\n\nsection,field,value\r\nSAMPLE,total,2\r\n"})

    assert _exit(monkeypatch, "compare", a, b) == 0
    assert "responses: {'identical': 8}" in capsys.readouterr().out
    assert _exit(monkeypatch, "compare", a, c) == 1
    assert "different s0000.flipped.csv" in capsys.readouterr().out


def test_compare_refuses_sides_that_hold_no_completion_marker(tmp_path, monkeypatch):
    bodies = {key: BODY for key in RESPONSES}

    assert _exit(monkeypatch, "compare", _shard(tmp_path / "a", bodies), _shard(tmp_path / "b", bodies)) == 2
    assert _exit(monkeypatch, "compare", tmp_path / "missing-a", tmp_path / "missing-b") == 2


DAMAGE = {
    "no manifest": lambda side: (side / "capture/shard0/manifest.json").unlink(),
    "an emptied shard": lambda side: (side / "capture/shard0/manifest.json").write_text(
        '{"responses": {}, "statements": {"0": "analysed"}, "packages": {}}'),
    "a missing capture": lambda side: (side / "capture/shard0/s0000.default.csv.gz").unlink(),
    "a capture changed after the run": lambda side: (side / "capture/shard0/s0000.default.csv.gz").write_bytes(
        gzip.compress(b"200 text/csv\n\nSAMPLE 2")),
    "a truncated capture": lambda side: (side / "capture/shard0/s0000.default.csv.gz").write_bytes(
        gzip.compress(BODY)[:12]),
}


@pytest.mark.parametrize("damage", DAMAGE)
def test_compare_exits_two_on_a_side_with_incomplete_evidence(tmp_path, monkeypatch, damage):
    a = _finished(tmp_path / "a")
    b = _finished(tmp_path / "b")
    DAMAGE[damage](b)

    assert _exit(monkeypatch, "compare", a, b) == 2
    assert _exit(monkeypatch, "compare", b, a) == 2


def test_compare_exits_two_on_sides_that_ran_different_plans(tmp_path, monkeypatch):
    other = json.dumps(golden.make_plan([("FABRIKAM/a.pdf", 1)], shards=1)).encode()

    assert _exit(monkeypatch, "compare", _finished(tmp_path / "a"), _finished(tmp_path / "b", plan=other)) == 2


def test_a_run_is_sealed_only_when_each_shard_holds_every_response_its_outcomes_call_for(tmp_path):
    refused = _shard(tmp_path / "refused", {}, {"0": "upload refused"})
    short = _shard(tmp_path / "short", {key: BODY for key in RESPONSES[:-1]})

    for work in (refused, short):
        with pytest.raises(SystemExit):
            golden.seal(work, PLAN)
        assert not (work / "complete.json").exists()


def test_diff_names_differing_paths_with_every_digit_masked():
    a = {"accounts": {"CONTOSO 1234": {"total": 10.5}}, "rows": ["FABRIKAM 1", "NORTHWIND 2", "SAMPLE 3"]}
    b = {"accounts": {"CONTOSO 1234": {"total": 99.25}}, "rows": ["CONTOSO 0", "FABRIKAM 1", "NORTHWIND 2", "SAMPLE 4"]}
    trees = [golden.parsed("s0001.default.json",
                           golden.canonical(200, "application/json", "", json.dumps(x).encode(), {})) for x in (a, b)]

    assert golden.differences(*trees) == [
        ("/body/accounts/CONTOSO ####/total", "##.#", "##.##"),
        ("/body/rows[-:0]", "<absent>", "CONTOSO #"),
        ("/body/rows[2:3]", "SAMPLE #", "SAMPLE #"),
    ]

    bodies = (b"section,field,value\r\nrevenue,total,12\r\n", b"section,field,value\r\nrevenue,total,13\r\n")
    csv_trees = [golden.parsed("p0002.default.csv", golden.canonical(200, "text/csv", "", body, {})) for body in bodies]
    assert golden.differences(*csv_trees) == [("/body[1:1][2:2]", "##", "##")]


def test_outputs_are_refused_inside_a_repository(tmp_path):
    (tmp_path / "checkout" / ".git").mkdir(parents=True)

    assert golden.repository_of(tmp_path / "checkout" / "deep" / "plan.json") == (tmp_path / "checkout").resolve()
    assert golden.repository_of(tmp_path / "outside" / "plan.json") is None


def test_plan_diff_and_capture_files_are_mode_600_even_over_an_existing_file(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus" / "CONTOSO"
    corpus.mkdir(parents=True)
    (corpus / "a.pdf").write_bytes(b"%PDF-1.4 SAMPLE")
    a = _shard(tmp_path / "a", {"s0000.default.json": BODY})
    b = _shard(tmp_path / "b", {"s0000.default.json": BODY.replace(b"1", b"2")})
    plan, report, capture = tmp_path / "plan.json", tmp_path / "diff.txt", tmp_path / "s0000.default.json.gz"
    for path in (plan, report, capture):
        path.write_text("{}")
        path.chmod(0o644)

    assert _exit(monkeypatch, "plan", "--corpus", tmp_path / "corpus", "--out", plan, "--shards", "1") == 0
    assert _exit(monkeypatch, "diff", a, b, "--index", "s0000.default.json", "--out", report) == 0
    golden.write_private(capture, gzip.compress(BODY))
    assert {path.name: path.stat().st_mode & 0o777 for path in (plan, report, capture)} == {
        "plan.json": 0o600, "diff.txt": 0o600, "s0000.default.json.gz": 0o600}
