from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import shutil
import sys
import uuid
import zipfile
from collections import Counter
from pathlib import Path

import pytest

from tools import golden

JOB = "0f8fad5b-d9cb-469f-a165-70867728950e"
OTHER = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
THIRD = "16fd2706-8baf-433b-82eb-8c7fada847da"
PLAN = json.dumps(golden.make_plan([("CONTOSO/a.pdf", 1)], shards=1)).encode()
PAIR = json.dumps(golden.make_plan([("CONTOSO/a.pdf", 1), ("CONTOSO/b.pdf", 1)], shards=1)).encode()


def _responses(*names: str) -> list[str]:
    return [f"{name}.{profile}.{kind}" for name in names for profile in ("default", "flipped")
            for kind in ("analysis", "json", "csv", "xlsx")]


RESPONSES = _responses("s0000")
BODY = b'200 application/json\n\n{"total": "SAMPLE 1"}'


def _xlsx(cell: str, stamp: str, when: tuple) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo("xl/worksheets/sheet1.xml", when),
                         f'<sheetData><row r="1"><c r="A1"><v>{cell}</v></c></row></sheetData>')
        archive.writestr(zipfile.ZipInfo("docProps/core.xml", when),
                         f"<dcterms:created>{stamp}</dcterms:created>")
    return out.getvalue()


def _shard(work: Path, bodies: dict[str, bytes], outcomes: dict[str, str] | None = None,
           packages: dict[str, int] | None = None) -> Path:
    """Shard 0 of a run as the shard leaves it: each response gzipped beside a manifest of their hashes."""
    out = work / "capture" / "shard0"
    out.mkdir(parents=True)
    for key, body in bodies.items():
        (out / f"{key}.gz").write_bytes(gzip.compress(body))
    manifest = {"responses": {key: hashlib.sha256(body).hexdigest() for key, body in bodies.items()},
                "statements": outcomes or {"0": "analysed"}, "packages": packages or {}}
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


def _forge_manifest(side: Path, data: bytes) -> None:
    """Replace the manifest and re-pin its digest in the marker, as if the run had written it."""
    (side / "capture/shard0/manifest.json").write_bytes(data)
    marker = json.loads((side / "complete.json").read_text())
    marker["shards"][0]["manifest"] = hashlib.sha256(data).hexdigest()
    (side / "complete.json").write_text(json.dumps(marker))


DAMAGE = {
    "no manifest": lambda side: (side / "capture/shard0/manifest.json").unlink(),
    "an unreadable manifest": lambda side: (side / "capture/shard0/manifest.json").chmod(0),
    "an unreadable capture": lambda side: (side / "capture/shard0/s0000.default.csv.gz").chmod(0),
    "a marker without its fields": lambda side: (side / "complete.json").write_text("{}"),
    "a marker whose shards are not objects": lambda side: (side / "complete.json").write_text(
        json.dumps({"plan": hashlib.sha256(PLAN).hexdigest(), "shards": [1]})),
    "a marker that seals no shard": lambda side: (side / "complete.json").write_text(
        json.dumps({"plan": hashlib.sha256(PLAN).hexdigest(), "shards": []})),
    "a sealed manifest that is not a manifest": lambda side: _forge_manifest(side, b"[]"),
    "a sealed manifest with no responses": lambda side: _forge_manifest(
        side, b'{"responses": {}, "statements": {"0": "analysed"}, "packages": {}}'),
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
    assert _exit(monkeypatch, "compare", b, b) == 2


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


INVENTORIES = {
    "a planned statement with no outcome": (PAIR, {"0": "analysed"}, {}, ["s0000"]),
    "an outcome for a statement the plan does not hold": (PLAN, {"0": "analysed", "1": "analysed"}, {},
                                                          ["s0000", "s0001"]),
    "an outcome that is not one": (PLAN, {"0": "SAMPLE"}, {}, ["s0000"]),
    "a planned package left out": (PAIR, {"0": "analysed", "1": "analysed"}, {}, ["s0000", "s0001"]),
    "a package the plan does not hold": (PLAN, {"0": "analysed"}, {"0": 1}, ["s0000", "p0000"]),
    "a package with the wrong analysed count": (PAIR, {"0": "analysed", "1": "analysed"}, {"0": 1},
                                                ["s0000", "s0001", "p0000"]),
}


@pytest.mark.parametrize("inventory", INVENTORIES)
def test_a_run_whose_inventory_differs_from_its_plan_is_not_sealed(tmp_path, monkeypatch, inventory):
    plan, outcomes, packages, names = INVENTORIES[inventory]
    work = _shard(tmp_path / "run", {key: BODY for key in _responses(*names)}, outcomes, packages)

    with pytest.raises(SystemExit) as refused:
        golden.seal(work, plan)
    assert refused.value.code == 2
    assert not (work / "complete.json").exists()
    assert _exit(monkeypatch, "compare", work, work) == 2


def _pair(work: Path) -> Path:
    """A run over PAIR before its seal: both statements analysed and packaged together, every response BODY."""
    return _shard(work, {key: BODY for key in _responses("s0000", "s0001", "p0000")},
                  {"0": "analysed", "1": "analysed"}, {"0": 2})


MALFORMED_MANIFESTS = {
    "a repeated outcome key": ('"statements": {"0": "analysed"',
                               '"statements": {"0": "upload refused", "0": "analysed"'),
    "an array outcome": ('"0": "analysed"', '"0": []'),
    "an object outcome": ('"0": "analysed"', '"0": {}'),
    "a string package count": ('"packages": {"0": 2}', '"packages": {"0": "2"}'),
    "a null package count": ('"packages": {"0": 2}', '"packages": {"0": null}'),
}


@pytest.mark.parametrize("case", MALFORMED_MANIFESTS)
def test_a_manifest_the_tool_did_not_write_is_neither_sealed_nor_compared(tmp_path, monkeypatch, case):
    old, new = MALFORMED_MANIFESTS[case]
    a, b = _pair(tmp_path / "a"), _pair(tmp_path / "b")
    golden.seal(a, PAIR)
    manifest = b / "capture/shard0/manifest.json"
    assert manifest.read_text().count(old) == 1
    manifest.write_text(manifest.read_text().replace(old, new))

    with pytest.raises(SystemExit) as refused:
        golden.seal(b, PAIR)
    assert refused.value.code == 2
    assert not (b / "complete.json").exists()
    shutil.copy(a / "complete.json", b / "complete.json")
    _forge_manifest(b, manifest.read_bytes())
    assert _exit(monkeypatch, "compare", a, b) == 2
    assert _exit(monkeypatch, "compare", b, a) == 2


MALFORMED_MARKERS = {
    "a string response count": lambda sealed: {**sealed, "responses": str(sealed["responses"])},
    "no counts": lambda sealed: {"manifest": sealed["manifest"]},
    "another response count": lambda sealed: {**sealed, "responses": sealed["responses"] + 8},
}


@pytest.mark.parametrize("case", MALFORMED_MARKERS)
def test_a_marker_whose_counts_the_tool_did_not_write_is_not_compared(tmp_path, monkeypatch, case):
    a, b = _finished(tmp_path / "a"), _finished(tmp_path / "b")
    marker = json.loads((b / "complete.json").read_text())
    marker["shards"][0] = MALFORMED_MARKERS[case](marker["shards"][0])
    (b / "complete.json").write_text(json.dumps(marker))

    assert _exit(monkeypatch, "compare", a, b) == 2
    assert _exit(monkeypatch, "compare", b, a) == 2


def test_compare_exits_two_on_a_side_that_holds_a_statement_in_two_shards(tmp_path, monkeypatch):
    a, b = _finished(tmp_path / "a"), _finished(tmp_path / "b")
    shutil.copytree(b / "capture/shard0", b / "capture/shard1")
    marker = json.loads((b / "complete.json").read_text())
    marker["shards"] *= 2
    (b / "complete.json").write_text(json.dumps(marker))

    assert _exit(monkeypatch, "compare", a, b) == 2
    assert _exit(monkeypatch, "compare", b, a) == 2


class _Pairs(list):
    """A JSON object read as its (key, value) pairs, so a test can write one that repeats a key."""


def _dump(node: object) -> str:
    if isinstance(node, _Pairs):
        return "{" + ", ".join(f"{json.dumps(key)}: {_dump(value)}" for key, value in node) + "}"
    if isinstance(node, list):
        return "[" + ", ".join(map(_dump, node)) + "]"
    return json.dumps(node)


BREAKS = ("delete", "string", "list", "object", "null", "negative", "float", "repeat")


def _broken(text: str):
    """(label, text) for each member of each object and each element of each list of a JSON file, broken each way
    in BREAKS: deleted, retyped, made negative or a float, or repeated (an object's key twice, a list's element)."""
    def places(node, at, label):
        if isinstance(node, list):
            for i, item in enumerate(node):
                key, value = item if isinstance(node, _Pairs) else (i, item)
                yield (*at, i), f"{label}/{key}"
                yield from places(value, (*at, i), f"{label}/{key}")

    root = json.loads(text, object_pairs_hook=_Pairs)
    for at, label in places(root, (), ""):
        for how in BREAKS:
            tree = copy.deepcopy(root)
            parent = tree
            for i in at[:-1]:
                parent = parent[i][1] if isinstance(parent, _Pairs) else parent[i]
            i = at[-1]
            key, value = parent[i] if isinstance(parent, _Pairs) else (None, parent[i])
            if how == "delete":
                del parent[i]
            elif how == "repeat":
                parent.insert(i + 1, copy.deepcopy(parent[i]))
            else:
                new = {"string": str(value) if type(value) in (int, float) else "SAMPLE", "list": [],
                       "object": _Pairs(), "null": None, "negative": -1,
                       "float": float(value) if type(value) is int else 0.5}[how]
                parent[i] = (key, new) if isinstance(parent, _Pairs) else new
            yield f"{label} {how}", _dump(tree)


def _seal(work: Path, plan: bytes) -> str:
    try:
        golden.seal(work, plan)
    except SystemExit as refused:
        return "refused" if refused.code == 2 and not (work / "complete.json").exists() else f"exit {refused.code}"
    return "sealed"


def test_every_field_of_every_evidence_file_broken_any_way_is_refused(tmp_path, monkeypatch):
    a, b, unsealed = _pair(tmp_path / "a"), _pair(tmp_path / "b"), _pair(tmp_path / "unsealed")
    golden.seal(a, PAIR)
    golden.seal(b, PAIR)
    marker, manifest = b / "complete.json", b / "capture/shard0/manifest.json"
    files = {"plan": PAIR.decode(), "marker": marker.read_text(), "manifest": manifest.read_text()}

    def incomplete_both_ways(side: Path) -> bool:
        return _exit(monkeypatch, "compare", a, side) == 2 and _exit(monkeypatch, "compare", side, a) == 2

    assert all(_dump(json.loads(text, object_pairs_hook=_Pairs)) == text for text in files.values())
    assert _seal(unsealed, PAIR) == "sealed" and _exit(monkeypatch, "compare", a, unsealed) == 0
    (unsealed / "complete.json").unlink()
    _forge_manifest(b, json.dumps(json.loads(files["manifest"]), sort_keys=True).encode())
    assert _exit(monkeypatch, "compare", a, b) == 0
    manifest.write_text(files["manifest"])
    marker.write_text(files["marker"])

    tried, escaped = Counter(), []
    for name, text in files.items():
        for label, broken in _broken(text):
            tried[name] += 1
            if name == "plan":
                sealed = _seal(unsealed, broken.encode())
                refused = sealed == "refused" or sealed == "sealed" and incomplete_both_ways(unsealed)
                (unsealed / "complete.json").unlink(missing_ok=True)
            elif name == "marker":
                marker.write_text(broken)
                refused = incomplete_both_ways(b)
            else:
                manifest.write_text(broken)
                marker.unlink()
                refused = _seal(b, PAIR) == "refused"
                marker.write_text(files["marker"])
                _forge_manifest(b, broken.encode())
                refused = incomplete_both_ways(b) and refused
            manifest.write_text(files["manifest"])
            marker.write_text(files["marker"])
            if not refused:
                escaped.append(f"{name}{label}")

    assert escaped == []
    assert tried == {"plan": 15 * len(BREAKS), "marker": 7 * len(BREAKS), "manifest": 30 * len(BREAKS)}
    assert _exit(monkeypatch, "compare", a, b) == 0


def test_a_run_matching_its_plan_is_sealed_with_refused_uploads_and_unanalysed_members(tmp_path, monkeypatch):
    both = _shard(tmp_path / "both", {key: BODY for key in _responses("s0000", "s0001", "p0000")},
                  {"0": "analysed", "1": "no matching parser"}, {"0": 1})
    one = _shard(tmp_path / "one", {key: BODY for key in RESPONSES}, {"0": "analysed", "1": "upload refused"})

    assert golden.seal(both, PAIR) == 24
    assert golden.seal(one, PAIR) == 8
    assert _exit(monkeypatch, "compare", both, both) == 0


def test_no_plan_or_run_of_fewer_than_one_shard(tmp_path, monkeypatch):
    corpus = tmp_path / "corpus" / "CONTOSO"
    corpus.mkdir(parents=True)
    (corpus / "a.pdf").write_bytes(b"%PDF-1.4 SAMPLE")
    empty = tmp_path / "empty-plan.json"
    empty.write_text(json.dumps({"shards": 0, "statements": [], "packages": [], "corpus": str(tmp_path)}))

    for shards in (0, -1):
        assert _exit(monkeypatch, "plan", "--corpus", tmp_path / "corpus", "--out", tmp_path / "p.json",
                     "--shards", shards) == 2
        assert not (tmp_path / "p.json").exists()
    assert _exit(monkeypatch, "run", "--plan", empty, "--code", tmp_path, "--work", tmp_path / "run") == 2
    assert not (tmp_path / "run").exists()
    with pytest.raises(SystemExit) as refused:
        golden.seal(tmp_path, empty.read_bytes())
    assert refused.value.code == 2
    assert not (tmp_path / "complete.json").exists()


def test_ids_repeat_while_both_sides_accept_the_same_uploads_and_tokens_follow_plan_position(monkeypatch):
    monkeypatch.setattr(uuid, "uuid4", uuid.uuid4)
    golden.repeatable_ids("shard0")
    base = [str(uuid.uuid4()) for _ in range(3)]
    golden.repeatable_ids("shard0")
    same = [str(uuid.uuid4()) for _ in range(3)]
    golden.repeatable_ids("shard0")
    refused_first = [None, *(str(uuid.uuid4()) for _ in range(2))]

    def third_job(ids: list) -> bytes:
        return golden.canonical(200, "application/json", "", json.dumps({"job": ids[2]}).encode(),
                                {ids[2].encode(): b"job-0002"})

    assert same == base
    assert refused_first[2] != base[2]
    assert third_job(refused_first) == third_job(base)


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
