"""The exact bytes each statement and package route serves, pinned for fabricated jobs.

Each case stores fabricated statements, analysed by the real pipeline with the suite's own builders, in a job store of
its own, and requests what a user reads: `/analysis/<id>` and `/download/<id>/<json|csv|xlsx>` for every job, then
`/package_analysis` and `/package_download/<json|csv|xlsx>` for all of them. It reads every route twice: from the jobs
the store holds after `set_result` (fresh), and from a second store opened on the same folder, which loads each
analysis back from its JSON (reloaded). The two differ wherever a payload holds a tuple. An XLSX is read part by part,
in archive order, with `docProps/core.xml`'s creation time masked: the writer stamps the clock there.

Each case folder under `tests/data/output_characterization/` holds `fingerprints.txt`, the SHA-256 of every served
body (prefixed with its HTTP status when it is not 200) for the fresh read and, where it differs, the reloaded read, and
`package.csv`, the package CSV download as served, for a reviewer to read. A default run never writes. To rewrite the
pins on purpose, run

    UPDATE_OUTPUT_PINS=1 python -m pytest tests/test_output_characterization.py

To see what moved, run the module with `OUTPUT_PINS_DUMP=<folder outside the repository>` at two commits and diff the
folders. The dump holds every served body, with the API JSON indented and each sheet row on its own line.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import json
import os
import re
import shutil
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis.display_settings import DEFAULTS
from tests import test_active_positions as active
from tests import test_large_unsourced_deposits as large_deposits
from tests import test_lender_payment_changes_package as lender_changes
from tests import test_lump_sum_payoffs as payoffs
from tests import test_package_matching as matching
from tests import test_represented_funder_payments as represented
from tests import test_returned_funder_payment_boundaries as boundaries
from tests import test_webapp_app as webapp_cases
from tests import test_webapp_true_revenue as true_revenue
from tests import zelle_setting_fixtures as zelle
from tests.flagged_payloads import flagged_account_payload
from tests.helpers import every
from webapp import app as webapp_app
from webapp import jobs
from webapp.jobs import JobStore
from webapp.settings import save_settings
from webapp.storage import Storage

PINS = Path(__file__).resolve().parent / "data" / "output_characterization"
UPDATE = os.environ.get("UPDATE_OUTPUT_PINS") == "1"
DUMP = os.environ.get("OUTPUT_PINS_DUMP")
PACKAGE_CSV = "package/download.csv"
NO_ANALYSIS = "fabricated: the statement printed no readable rows"
CREATED = re.compile(rb"(<dcterms:created>)[^<]*(</dcterms:created>)")
ROW = re.compile(rb"(?=<row |</sheetData>)")


@dataclass(frozen=True)
class Upload:
    """One stored job. `analysis` None with status "done" is a job that finished without an analysis. Two uploads
    with the same `pdf` are one PDF uploaded twice."""
    job_id: str
    analysis: dict | None = None
    status: str = "done"
    pdf: str | None = None


@dataclass(frozen=True)
class Case:
    uploads: Callable[[], list[Upload]]
    settings: dict | None = None


def _uploads(**payloads) -> list[Upload]:
    return [Upload(job_id, payload) for job_id, payload in payloads.items()]


def _from_jobs(*jobs) -> list[Upload]:
    return [Upload(job.id, job.analysis) for job in jobs]


def _no_pair_months():
    march = matching._payload(matching.NO_PAIR_MARCH, month=3, opening=1500.0)
    opening = matching._closing(matching.NO_PAIR_MARCH, 1500.0)
    return march, matching._payload(matching.NO_PAIR_APRIL, month=4, opening=opening)


def _one_account_two_months():
    march, april = _no_pair_months()
    return _uploads(mar=march, apr=april)


def _detection_and_reason_maps():
    return _uploads(mar=true_revenue._payload(true_revenue.DETECTED_ROWS), apr=true_revenue._payload(month=4))


def _zelle_deposits():
    return _uploads(mar=zelle.case("Z1"), apr=zelle.payload(zelle.FREE, month=4))


def _lines_of_credit_and_negative_days():
    days = every(lender_changes.M(4), lender_changes.M(25))
    rows = [*lender_changes.debits(days, 1000), *lender_changes.debits(days, 600, active.LINE),
            *lender_changes.debits(days, 550, active.CARD)]
    return _uploads(mar=lender_changes.statement_payload(rows, month=3, opening=-15000.0))


def _mixed_currency():
    march = matching._payload(matching.NO_PAIR_MARCH, month=3, opening=1500.0, currency="CAD",
                              number=matching.ACCOUNT_B)
    april = matching._payload(matching.NO_PAIR_APRIL, month=4, opening=1500.0)
    return _uploads(mar=march, apr=april)


def _undeclared_currency():
    march, april = matching._owners_example()
    march["statement"]["currency"] = None
    return _uploads(mar=march, apr=april)


def _two_accounts_one_document():
    return _uploads(doc=matching._two_account_document(matching._rows_a(), matching._rows_b()))


def _own_account_transfer():
    return _uploads(a=matching._account_a(), b=matching._account_b())


def _already_held_transfer():
    return _uploads(a=matching._account_a(), b=matching._account_b("TRANSFER CREDIT"))


def _returned_deposit_and_chargeback():
    march, april = matching._owners_example([*matching.APRIL, *matching.CHARGEBACK_ROWS[1:2]])
    return _uploads(mar=march, apr=april)


def _older_rules_member():
    march, april = matching._owners_example()
    return _uploads(mar=true_revenue._untiered(march), apr=april)


def _partial_revenue():
    return _uploads(mar=true_revenue._payload(), apr=true_revenue._summary_only(4),
                    may=true_revenue._verified_unestablished(5))


def _stored_legacy_basis():
    stored = true_revenue._payload(month=4)
    metrics = stored["metrics"]
    for key in ("withholding_denominator_mode", "withholding_denominator_label", "eligible_deposit_definition"):
        metrics.pop(key)
    for key in ("eligible_deposits", "withholding_denominator", "potential_withholding_denominator"):
        metrics[key] = 2000.0
    return _uploads(mar=true_revenue._payload(), apr=stored)


def _failed_pending_and_no_analysis():
    march, _april = _no_pair_months()
    return [Upload("mar", march), Upload("apr"), Upload("may", status="error"), Upload("jun", status="queued")]


def _same_pdf_twice():
    march, april = _no_pair_months()
    return [Upload("mar", march, pdf="march"), Upload("mar-again", copy.deepcopy(march), pdf="march"),
            Upload("apr", april)]


def _quarterly_printout_superseded():
    quarter = webapp_cases._period("q1", webapp_cases._JAN + webapp_cases._FEB + webapp_cases._MAR_Q1, "2031-01-01",
                                   "2031-03-31")
    return _from_jobs(*webapp_cases._first_quarter(), quarter)


def _document_account_repeats_a_statement():
    january, february, _march = webapp_cases._first_quarter()
    document = webapp_cases._document_with(webapp_cases._ACCOUNT, webapp_cases._JAN + webapp_cases._FEB,
                                           start="2031-01-01", end="2031-02-28", opening=1500.0)
    return [*_from_jobs(january, february), Upload("doc", document)]


def _withheld_and_omitted_accounts():
    ratified = [{"label": "CONTOSO SECTION B", "reason": "printed_dormancy_declaration", "posting_count": 0}]
    return _from_jobs(webapp_cases._r15_month(1), webapp_cases._r15_document(2, main="held"),
                      webapp_cases._r15_document(3, omitted=ratified))


def _active_positions_across_two_accounts():
    payload, debits, closing = lender_changes.statement_payload, lender_changes.debits, lender_changes.closing
    march_days = every(lender_changes.M(4), lender_changes.M(25))
    a_march = payload(debits(march_days, 1000), month=3)
    a_april = payload(debits(every(lender_changes.A(1), lender_changes.A(8)), 1000), month=4, opening=closing(a_march))
    a_may = payload([], month=5, opening=closing(a_april))
    b_march = payload(debits(march_days, 700), month=3, account=lender_changes.ACCOUNT_B)
    b_april = payload(debits(every(lender_changes.A(1), lender_changes.A(29)), 700), month=4,
                      account=lender_changes.ACCOUNT_B, opening=closing(b_march))
    b_may = payload(debits(every(lender_changes.Y(6), lender_changes.Y(27)), 700), month=5,
                    account=lender_changes.ACCOUNT_B, opening=closing(b_april))
    return _uploads(a_march=a_march, a_april=a_april, a_may=a_may, b_march=b_march, b_april=b_april, b_may=b_may)


def _lump_sum_payoff():
    march, april = payoffs._months()
    return _uploads(mar=march, apr=april)


def _large_unsourced_deposits():
    march, april = large_deposits._months()
    return _uploads(mar=march, apr=april)


def _returned_funder_payment_re_debited():
    march, april = represented._months(
        [*represented.MARCH, (28, represented.BARE_BOUNCE, 850.0)],
        [(2, matching.NW_APRIL, 30000.0), (3, represented.KAPITUS_BAKERY, -850.0)]
        + [(day, represented.KAPITUS_BAKERY, -850.0) for day in (1, 8, 15, 22)])
    return _uploads(mar=march, apr=april)


def _funder_payment_returned_in_the_next_statement():
    march, april = boundaries._months(boundaries._april())
    return _uploads(mar=march, apr=april)


def _every_flag_group_zelle_and_negative_days():
    (negative_days,) = _lines_of_credit_and_negative_days()
    return [Upload("flagged", flagged_account_payload()), *_zelle_deposits(),
            Upload("negative", negative_days.analysis)]


CASES = {
    "one_account_two_months": Case(_one_account_two_months),
    "detection_and_reason_maps": Case(_detection_and_reason_maps),
    "zelle_counted": Case(_zelle_deposits),
    "zelle_excluded": Case(_zelle_deposits, {"zelle_true_revenue": False}),
    "lines_of_credit_shown": Case(_lines_of_credit_and_negative_days),
    "lines_of_credit_hidden_and_carry_over": Case(_lines_of_credit_and_negative_days,
                                                  {"flag_lines_of_credit": False, "nsf_carry_over": True}),
    "mixed_currency": Case(_mixed_currency),
    "undeclared_currency": Case(_undeclared_currency),
    "two_accounts_one_document": Case(_two_accounts_one_document),
    "own_account_transfer": Case(_own_account_transfer),
    "already_held_transfer": Case(_already_held_transfer),
    "returned_deposit_and_chargeback": Case(_returned_deposit_and_chargeback),
    "older_rules_member": Case(_older_rules_member),
    "partial_revenue": Case(_partial_revenue),
    "stored_legacy_basis": Case(_stored_legacy_basis),
    "failed_pending_and_no_analysis": Case(_failed_pending_and_no_analysis),
    "same_pdf_twice": Case(_same_pdf_twice),
    "quarterly_printout_superseded": Case(_quarterly_printout_superseded),
    "document_account_repeats_a_statement": Case(_document_account_repeats_a_statement),
    "withheld_and_omitted_accounts": Case(_withheld_and_omitted_accounts),
    "active_positions_across_two_accounts": Case(_active_positions_across_two_accounts),
    "lump_sum_payoff": Case(_lump_sum_payoff),
    "large_unsourced_deposits": Case(_large_unsourced_deposits),
    "returned_funder_payment_re_debited": Case(_returned_funder_payment_re_debited),
    "funder_payment_returned_in_the_next_statement": Case(_funder_payment_returned_in_the_next_statement),
    "every_setting_opposite_its_default": Case(_every_flag_group_zelle_and_negative_days,
                                               {key: not default for key, default in DEFAULTS.items()}),
}


@dataclass(frozen=True)
class Response:
    """One request's answer. `files` maps a path in the case's dump folder to the bytes served: the body, or for an
    XLSX served with 200 each zip part plus `parts.txt`, the part list with each part's compression."""
    url: str
    name: str
    status: int
    files: dict[str, bytes]


@dataclass(frozen=True)
class Fingerprint:
    """`fresh` is a SHA-256, prefixed `http-<status>:` for a route that does not answer 200. `reloaded` is `same` when
    the reloaded read serves the fresh bytes."""
    path: str
    url: str
    fresh: str
    reloaded: str

    def line(self) -> str:
        return f"{self.path} {self.fresh} {self.reloaded}\n"


def _upload(store, upload: Upload) -> None:
    job = store.create(f"{upload.job_id}.pdf", pdf_bytes=f"%PDF-fabricated {upload.pdf or upload.job_id}".encode())
    if upload.status == "error":
        store.set_error(job.id, "fabricated failure")
    elif upload.status == "done":
        store.set_result(job.id, f"# {upload.job_id}", f"<h1>{upload.job_id}</h1>", analysis=upload.analysis,
                         analysis_error=None if upload.analysis is not None else NO_ANALYSIS)


def _files(name: str, body: bytes) -> dict[str, bytes]:
    if not name.endswith(".xlsx"):
        return {name: body}
    archive = zipfile.ZipFile(BytesIO(body))
    parts = "".join(f"{info.filename} {info.compress_type}\n" for info in archive.infolist())
    files = {f"{name}/parts.txt": parts.encode()}
    for info in archive.infolist():
        part = archive.read(info)
        if info.filename == "docProps/core.xml":
            part = CREATED.sub(rb"\1masked\2", part)
        files[f"{name}/{info.filename}"] = part
    return files


def _requested(uploads: list[Upload]) -> list[Response]:
    client = webapp_app.app.test_client()
    ids = ",".join(upload.job_id for upload in uploads)
    routes = []
    for job in (upload.job_id for upload in uploads):
        routes += [(f"/analysis/{job}", f"{job}/analysis.json")]
        routes += [(f"/download/{job}/{fmt}", f"{job}/download.{fmt}") for fmt in ("json", "csv", "xlsx")]
    routes += [(f"/package_analysis?ids={ids}", "package/analysis.json")]
    routes += [(f"/package_download/{fmt}?ids={ids}", f"package/download.{fmt}") for fmt in ("json", "csv", "xlsx")]
    responses = []
    for url, name in routes:
        response = client.get(url)
        files = _files(name, response.data) if response.status_code == 200 else {name: response.data}
        responses.append(Response(url, name, response.status_code, files))
    return responses


def _served(case: Case, folder: Path) -> dict[str, list[Response]]:
    uploads = case.uploads()
    with pytest.MonkeyPatch.context() as patch:
        job_ids = iter([upload.job_id for upload in uploads])
        patch.setattr(jobs, "uuid", SimpleNamespace(uuid4=lambda: next(job_ids)))
        fresh = JobStore(Storage(folder))
        if case.settings:
            save_settings(folder, case.settings)
        for upload in uploads:
            _upload(fresh, upload)
        served = {}
        for read, store in (("fresh", fresh), ("reloaded", JobStore(Storage(folder)))):
            patch.setattr(webapp_app, "store", store)
            served[read] = _requested(uploads)
    return served


def _digest(response: Response, path: str) -> str:
    if path not in response.files:
        return "absent"
    digest = hashlib.sha256(response.files[path]).hexdigest()
    return digest if response.status == 200 else f"http-{response.status}:{digest}"


def _fingerprints(served: dict[str, list[Response]]) -> list[Fingerprint]:
    prints = []
    for fresh, reloaded in zip(served["fresh"], served["reloaded"], strict=True):
        for path in dict.fromkeys([*fresh.files, *reloaded.files]):
            digest = _digest(fresh, path)
            again = _digest(reloaded, path)
            prints.append(Fingerprint(path, fresh.url, digest, "same" if again == digest else again))
    return prints


def _pinned(name: str) -> tuple[dict[str, tuple[str, str]], bytes | None]:
    folder = PINS / name
    assert (folder / "fingerprints.txt").is_file(), f"no pin for {name}"
    rows = (line.split(" ") for line in (folder / "fingerprints.txt").read_text().splitlines())
    csv = folder / "package.csv"
    return {path: (fresh, reloaded) for path, fresh, reloaded in rows}, csv.read_bytes() if csv.is_file() else None


def _write(name: str, prints: list[Fingerprint], csv: bytes | None) -> None:
    folder = PINS / name
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    (folder / "fingerprints.txt").write_text("".join(fingerprint.line() for fingerprint in prints))
    if csv is not None:
        (folder / "package.csv").write_bytes(csv)


def _readable(path: str, body: bytes) -> bytes:
    if path.endswith("analysis.json"):
        return (json.dumps(json.loads(body), indent=1) + "\n").encode()
    if path.endswith(".xml"):
        return ROW.sub(b"\n", body)
    return body


def _exact(path: str, readable: bytes) -> bytes:
    if path.endswith("analysis.json"):
        return (json.dumps(json.loads(readable), separators=(",", ":")) + "\n").encode()
    if path.endswith(".xml"):
        return readable.replace(b"\n<row ", b"<row ").replace(b"\n</sheetData>", b"</sheetData>")
    return readable


def _dump_root() -> Path:
    root = Path(DUMP).expanduser().resolve()
    repository = next((folder for folder in (root, *root.parents) if (folder / ".git").exists()), None)
    if repository is not None:
        pytest.fail(f"OUTPUT_PINS_DUMP={root} is inside the repository at {repository}; pick a folder outside it")
    return root


def _dump(name: str, served: dict[str, list[Response]]) -> None:
    folder = _dump_root() / name
    shutil.rmtree(folder, ignore_errors=True)
    fresh = {}
    for read, responses in served.items():
        files = {path: body for response in responses for path, body in response.files.items()}
        files["routes.txt"] = "".join(f"{response.status} {response.url}\n" for response in responses).encode()
        errors = {response.name for response in responses if response.status != 200}
        for path, body in files.items():
            if read == "reloaded" and fresh.get(path) == body:
                continue
            readable = body if path in errors else _readable(path, body)
            exact = path in errors or _exact(path, readable) == body
            assert exact, f"{name} {read} {path}: the readable form loses bytes"
            target = folder / read / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(readable)
        fresh = files


def _differences(pinned: dict[str, tuple[str, str]], prints: list[Fingerprint]) -> list[str]:
    found = []
    for fingerprint in prints:
        if fingerprint.path not in pinned:
            found.append(f"{fingerprint.path} from {fingerprint.url}: served, never pinned")
            continue
        for read, expected, served in zip(("fresh", "reloaded"), pinned[fingerprint.path],
                                          (fingerprint.fresh, fingerprint.reloaded)):
            if expected != served:
                found.append(f"{fingerprint.path} from {fingerprint.url}, {read} read: pinned {expected[:25]}, "
                             f"served {served[:25]}")
    paths = [fingerprint.path for fingerprint in prints]
    found += [f"{path}: pinned, no longer served" for path in pinned.keys() - set(paths)]
    if not found and list(pinned) != paths:
        found.append("the pinned files are served in a new order: " + ", ".join(paths))
    return found


def _csv_diff(pinned: bytes | None, served: bytes | None) -> str:
    before, after = (text.decode().splitlines(True) if text else [] for text in (pinned, served))
    lines = difflib.unified_diff(before, after, "package.csv pinned", "package.csv served", n=1)
    return "".join(f"    {line}" for line in list(lines)[:40])


@pytest.mark.parametrize("name", CASES)
def test_every_route_serves_the_pinned_bytes(name, tmp_path):
    served = _served(CASES[name], tmp_path)
    prints = _fingerprints(served)
    csv = next((response.files[PACKAGE_CSV] for response in served["fresh"] if PACKAGE_CSV in response.files), None)
    if DUMP:
        _dump(name, served)
    if UPDATE:
        _write(name, prints, csv)
    pinned, pinned_csv = _pinned(name)
    differences = _differences(pinned, prints)
    if pinned_csv != csv:
        differences.append(f"{PACKAGE_CSV}, fresh read, as text:\n{_csv_diff(pinned_csv, csv)}")
    assert not differences, (
        f"{name}: {len(differences)} served outputs differ from the pins. To see them, run this test with "
        "OUTPUT_PINS_DUMP=<folder> here and at the parent commit and diff the two folders.\n" + "\n".join(differences))


def test_every_pin_belongs_to_a_case():
    folders = {path.name for path in PINS.iterdir() if path.is_dir()}
    if UPDATE:
        for stale in folders - CASES.keys():
            shutil.rmtree(PINS / stale)
        folders &= CASES.keys()
    assert sorted(folders) == sorted(CASES)
