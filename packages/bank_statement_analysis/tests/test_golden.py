from __future__ import annotations

import io
import json
import zipfile

from tools.golden import (
    canonical,
    compare_manifests,
    differences,
    make_plan,
    parsed,
    repository_of,
    write_private,
)

JOB = "0f8fad5b-d9cb-469f-a165-70867728950e"
OTHER = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def _xlsx(cell: str, stamp: str, when: tuple) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo("xl/worksheets/sheet1.xml", when),
                         f'<sheetData><row r="1"><c r="A1"><v>{cell}</v></c></row></sheetData>')
        archive.writestr(zipfile.ZipInfo("docProps/core.xml", when),
                         f"<dcterms:created>{stamp}</dcterms:created>")
    return out.getvalue()


def test_plan_cuts_each_folder_into_packages_of_two_to_six_within_one_shard():
    files = [(f"CONTOSO BANK/statement-{i}.pdf", 100 + i) for i in range(9)]
    files += [("FABRIKAM/only.pdf", 50), ("NORTHWIND/a.pdf", 10), ("NORTHWIND/older/b.pdf", 20)]
    plan = make_plan(files, shards=3)

    assert plan == make_plan(list(reversed(files)), shards=3)
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
    first = canonical(200, "application/xlsx", "", _xlsx("1", "2026-01-02T03:04:05+00:00", (2026, 1, 2, 3, 4, 6)), {})
    later = canonical(200, "application/xlsx", "", _xlsx("1", "2026-02-03T04:05:06+00:00", (2026, 2, 3, 4, 5, 8)), {})
    changed = canonical(200, "application/xlsx", "", _xlsx("2", "2026-01-02T03:04:05+00:00", (2026, 1, 2, 3, 4, 6)), {})

    assert first == later
    assert first != changed


def test_known_ids_become_plan_positions_and_other_uuids_one_mark():
    body = json.dumps({"job": JOB, "unknown": OTHER}).encode()

    assert canonical(200, "application/json", "", body, {JOB.encode(): b"job-0007"}) == (
        b'200 application/json\n\n{"job": "job-0007", "unknown": "uuid"}')


def test_compare_counts_each_verdict_by_response_kind():
    a = {"s0001.default.csv": "x", "s0001.default.json": "y", "p0002.flipped.xlsx": "z"}
    b = {"s0001.default.csv": "x", "s0001.default.json": "Y", "s0003.flipped.analysis": "w"}

    kinds, found = compare_manifests(a, b)

    assert kinds == {"statement.default.csv": {"identical": 1}, "statement.default.json": {"different": 1},
                     "package.flipped.xlsx": {"only in A": 1}, "statement.flipped.analysis": {"only in B": 1}}
    assert found == [("only in A", "p0002.flipped.xlsx"), ("different", "s0001.default.json"),
                     ("only in B", "s0003.flipped.analysis")]


def test_diff_names_differing_paths_with_every_digit_masked():
    a = {"accounts": {"CONTOSO 1234": {"total": 10.5}}, "rows": ["FABRIKAM 1", "NORTHWIND 2", "SAMPLE 3"]}
    b = {"accounts": {"CONTOSO 1234": {"total": 99.25}}, "rows": ["CONTOSO 0", "FABRIKAM 1", "NORTHWIND 2", "SAMPLE 4"]}
    trees = [parsed("s0001.default.json", canonical(200, "application/json", "", json.dumps(x).encode(), {}))
             for x in (a, b)]

    assert differences(*trees) == [
        ("/body/accounts/CONTOSO ####/total", "##.#", "##.##"),
        ("/body/rows[-:0]", "<absent>", "CONTOSO #"),
        ("/body/rows[2:3]", "SAMPLE #", "SAMPLE #"),
    ]

    bodies = (b"section,field,value\r\nrevenue,total,12\r\n", b"section,field,value\r\nrevenue,total,13\r\n")
    csv_trees = [parsed("p0002.default.csv", canonical(200, "text/csv", "", body, {})) for body in bodies]
    assert differences(*csv_trees) == [("/body[1:1][2:2]", "##", "##")]


def test_outputs_are_refused_inside_a_repository_and_written_private(tmp_path):
    (tmp_path / "checkout" / ".git").mkdir(parents=True)

    assert repository_of(tmp_path / "checkout" / "deep" / "plan.json") == (tmp_path / "checkout").resolve()
    assert repository_of(tmp_path / "outside" / "plan.json") is None

    write_private(tmp_path / "plan.json", b"{}")
    assert (tmp_path / "plan.json").stat().st_mode & 0o777 == 0o600
