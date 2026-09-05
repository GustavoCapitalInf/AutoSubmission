"""tools/adjudicate.py — the adjudication CLI (P22-HOLDOUT item 3; R3).

    python -m tools.adjudicate queue --rows <run>/rows.csv --slice <name> --shas <file>
        --packets <PRIVATE dir> [--pdf-root <dir>] [--census <per_sha.csv>]
        [--classification <csv>] [--moneythumb <csv>] [--dpi N] [--max-pages N]
    python -m tools.adjudicate run --slice <name> --packets <PRIVATE dir>
        [--answers <json>] [--adjudicator <role>] [--limit N]
    python -m tools.adjudicate status
    python -m tools.adjudicate verify [--digest <path>]
    python -m tools.adjudicate export-digest [--out <path>]
    python -m tools.adjudicate holdout-add | holdout-burn | holdout-graduate | holdout-list

`queue` builds one evidence packet per sha into the PRIVATE packet directory
(outside every checkout; refused otherwise): page images rendered LOCALLY with
PyMuPDF at a modest dpi (up to `--max-pages`, default 40; a cut packet says so
in `packet.json` and the queue reports how many were cut), the prior census
tag labelled `EVIDENCE (census, agent-derived, not truth)`, the classifier's
proposal — only when a per-sha classification CSV is supplied — labelled
`EVIDENCE (classifier proposal, tool-derived, not truth)`, a MoneyThumb
comparison ONLY when explicitly supplied and labelled likewise, and the packet
digest (sha256 over everything shown, page-image shas included). `run` first
verifies the store against its manifest, then walks the queue: for every
entry it RECOMPUTES the packet digest from the packet files (`packet.json` and
the page images) and refuses a packet whose digest no longer matches the
queue's (review MINOR-1), renders the evidence from `packet.json`, asks for the
verdict and PROPOSES NOTHING as a default — the human types the kind; an
answer without a kind appends nothing — then appends the record to the sealed
store, verifies the chain, advances. Notes are hashed, never stored. `status`
prints aggregates only. `verify` checks both chains against their manifests
and, with `--digest`, against a repository digest. `export-digest` writes the
repository digest. `holdout-add` asserts `not_in_dev_corpus` ONLY against a
run's `rows.csv` (`--dev-rows`, required; review MAJOR-3). `holdout-graduate`
resolves the freeze tag through git only (review MAJOR-2). `--answers <json>`
is the non-interactive mode for tests (synthetic).

Gustavo is the adjudicator (R3). This tool adjudicates nothing.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from tools.holdout import digest as digest_mod
from tools.holdout.manifest import (
    ACCOUNT_SHAPES,
    BANK_FAMILIARITY,
    HOLDOUT_STATUSES,
    TABLE_SHAPES,
    HoldoutManifest,
    build_strata,
    dev_corpus_from_rows,
    freeze_tags_from_git,
)
from tools.holdout.store import (
    ACCOUNT_KINDS,
    COMPLETENESS_CODES,
    KINDS,
    MODALITIES,
    RecordError,
    StoreError,
    TruthStore,
    _retry,
    _this_checkout_root,
    canonical_json,
    content_sha256_of,
    refuse_inside_checkout,
    sha256_hex,
    utc_now_iso,
    validate_role,
    validate_sha,
)

COMMANDS = (
    "queue", "run", "status", "verify", "export-digest",
    "holdout-add", "holdout-burn", "holdout-graduate", "holdout-list",
)
CENSUS_LABEL = "EVIDENCE (census, agent-derived, not truth)"
CLASSIFIER_LABEL = "EVIDENCE (classifier proposal, tool-derived, not truth)"
MONEYTHUMB_LABEL = "EVIDENCE (MoneyThumb, vendor output, not truth)"
PROFILE_LABEL = "FILE FACTS (run-of-record profile)"
CENSUS_FIELDS = ("cluster", "cluster_group", "b8_kind", "text_density", "classification", "text_route")
PROFILE_FIELDS = ("valid_pdf", "classification", "page_count")
DEFAULT_DPI = 100
DEFAULT_MAX_PAGES = 40
QUEUE_FILE = "queue.json"
QUEUE_DIGEST_FILE = "QUEUE_DIGEST.txt"
PACKET_FILE = "packet.json"
EVIDENCE_FILE = "EVIDENCE.txt"
ANSWER_FIELDS = (
    "kind", "sub_kind", "account_kind", "modality", "legible", "completeness_findings",
    "account_count", "printed_period_start", "printed_period_end", "opening_balance",
    "closing_balance", "printed_transaction_count", "sampled_rows", "notes",
)
_SLICE_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{0,59}")
_PAGE_NAME_RE = re.compile(r"page-\d{3,}\.png")
_SKIP = object()
_QUIT = object()


def ask(prompt: str) -> str:
    """The one place the CLI reads a human's answer (tests replace it)."""
    return input(prompt)


# --- inputs ------------------------------------------------------------------


def read_sha_list(path: Path) -> list[str]:
    shas: list[str] = []
    seen: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        token = line.split("#", 1)[0].strip()
        if not token:
            continue
        sha = validate_sha(token)
        if sha not in seen:
            seen.add(sha)
            shas.append(sha)
    return shas


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_rows(path: Path) -> dict[str, dict]:
    """One row per sha from a run's rows.csv: the first by relative path."""
    rows: dict[str, dict] = {}
    for row in sorted(_read_csv(path), key=lambda r: r.get("relative_path") or ""):
        sha = (row.get("content_sha256") or "").strip().upper()
        if sha and sha not in rows:
            rows[sha] = row
    return rows


def load_keyed_csv(path: Path | None, keys=("content_sha256", "sha")) -> dict[str, dict]:
    if path is None:
        return {}
    keyed: dict[str, dict] = {}
    for row in _read_csv(path):
        for key in keys:
            if row.get(key):
                keyed[row[key].strip().upper()] = row
                break
    return keyed


# --- packets ----------------------------------------------------------------


def render_pages(pdf_bytes: bytes, out_dir: Path, *, dpi: int, max_pages: int) -> dict:
    """Page PNGs into `out_dir` (a private directory), locally, with PyMuPDF.
    Never raises: an unreadable file is a packet with an error and no pages."""
    for stale in out_dir.glob("page-*.png"):
        stale.unlink()
    render = {"page_count": None, "rendered": 0, "truncated": False, "error": None, "pages": []}
    try:
        import fitz  # PyMuPDF — the only third-party import, lazily, here
    except Exception as exc:  # pragma: no cover - environment without PyMuPDF
        render["error"] = f"renderer_unavailable:{type(exc).__name__}"
        return render
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        render["error"] = f"invalid_pdf:{type(exc).__name__}"
        return render
    try:
        render["page_count"] = int(document.page_count)
        if document.needs_pass:
            render["error"] = "encrypted"
            return render
        if render["page_count"] == 0:
            render["error"] = "no_pages"
            return render
        for index, page in enumerate(document):
            if index >= max_pages:
                render["truncated"] = True
                break
            try:
                data = page.get_pixmap(dpi=dpi).tobytes("png")
            except Exception as exc:
                render["error"] = f"render_failed:{type(exc).__name__}:page{index + 1}"
                break
            name = f"page-{index + 1:03d}.png"
            _retry(lambda: (out_dir / name).write_bytes(data))
            render["pages"].append({"name": name, "sha256": sha256_hex(data)})
            render["rendered"] += 1
    finally:
        document.close()
    return render


def build_evidence(sha: str, census_row, classifier_row, moneythumb_row) -> dict:
    evidence: dict = {}
    if census_row is not None:
        evidence["census"] = {
            "label": CENSUS_LABEL,
            "values": {field: (census_row.get(field) or "") for field in CENSUS_FIELDS},
        }
    if classifier_row is not None:
        evidence["classifier"] = {
            "label": CLASSIFIER_LABEL,
            "values": {k: v for k, v in classifier_row.items()
                       if k not in ("content_sha256", "sha", "sha16") and v not in (None, "")},
        }
    if moneythumb_row is not None:
        evidence["moneythumb"] = {
            "label": MONEYTHUMB_LABEL,
            "values": {k: v for k, v in moneythumb_row.items()
                       if k not in ("content_sha256", "sha", "sha16") and v not in (None, "")},
        }
    return evidence


def packet_content(sha: str, slice_name: str, pages: list[dict], render: Mapping, evidence: Mapping,
                   profile: Mapping) -> dict:
    """Exactly what the packet digest covers — everything the adjudicator is shown."""
    return {
        "content_sha256": sha,
        "slice": slice_name,
        "pages": pages,
        "render": {key: render.get(key) for key in ("page_count", "rendered", "truncated", "error")},
        "evidence": evidence,
        "profile": profile,
    }


def packet_digest_from_dir(packet_dir: Path) -> tuple[str, dict]:
    """Recompute a packet's digest from the files on disk (`packet.json` plus
    the page images it names, re-hashed) — the digest `run` records must be
    the digest of what is on disk NOW, not what `queue` once wrote."""
    packet = json.loads((packet_dir / PACKET_FILE).read_text(encoding="utf-8"))
    pages: list[dict] = []
    for page in packet.get("pages", []):
        name = str(page.get("name", ""))
        if not _PAGE_NAME_RE.fullmatch(name):
            raise StoreError(f"packet names a page outside the packet shape: {name!r}")
        data = (packet_dir / name).read_bytes()
        pages.append({"name": name, "sha256": sha256_hex(data)})
    content = packet_content(packet["content_sha256"], packet["slice"], pages, packet["render"],
                             packet["evidence"], packet["profile"])
    return sha256_hex(canonical_json(content)), packet


def evidence_text(packet: Mapping) -> str:
    lines = [
        f"DOCUMENT {packet['sha16']} (content sha256 {packet['content_sha256']})",
        f"slice: {packet['slice']}",
        f"pages: rendered {packet['render']['rendered']} of {packet['render']['page_count']}"
        + (f" (cut at the {packet['max_pages']}-page cap)" if packet["render"].get("truncated") else "")
        + (f" -- render error: {packet['render']['error']}" if packet["render"]["error"] else ""),
        f"---- {packet['profile']['label']} ----",
    ]
    lines += [f"{k}: {v}" for k, v in packet["profile"]["values"].items()]
    for key in ("census", "classifier", "moneythumb"):
        block = packet["evidence"].get(key)
        if block is None:
            continue
        lines.append(f"---- {block['label']} ----")
        lines += [f"{k}: {v}" for k, v in block["values"].items()] or ["(no values)"]
    lines.append("----")
    lines.append("Nothing above is a label. The verdict is the adjudicator's; nothing is pre-filled.")
    return "\n".join(lines) + "\n"


def _write_text(path: Path, text: str) -> None:
    def _write():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    _retry(_write)


def _write_queue(slice_dir: Path, queue: dict) -> None:
    _write_text(slice_dir / QUEUE_FILE, json.dumps(queue, indent=2, sort_keys=True) + "\n")


def queue_digest(entries: list[dict]) -> str:
    material = sorted((e["content_sha256"], e.get("packet_digest") or "") for e in entries)
    return sha256_hex(canonical_json(material))


def build_queue(
    rows_csv: Path,
    slice_name: str,
    shas_path: Path,
    packets_dir: Path,
    *,
    pdf_root: Path,
    census_csv: Path | None = None,
    classification_csv: Path | None = None,
    moneythumb_csv: Path | None = None,
    dpi: int = DEFAULT_DPI,
    max_pages: int = DEFAULT_MAX_PAGES,
    out=print,
) -> dict:
    packets = refuse_inside_checkout(packets_dir, what="the packet directory")
    if not _SLICE_RE.fullmatch(slice_name or ""):
        raise StoreError(f"slice: a lowercase label is required, got {slice_name!r}")
    root = Path(pdf_root).resolve()
    if not root.is_dir():
        raise StoreError(f"pdf root is not a directory: {root}")
    rows = load_rows(rows_csv)
    census = load_keyed_csv(census_csv)
    classification = load_keyed_csv(classification_csv)
    moneythumb = load_keyed_csv(moneythumb_csv)
    shas = read_sha_list(shas_path)
    slice_dir = packets / slice_name
    entries: list[dict] = []
    for sha in shas:
        sha16 = sha[:16]
        row = rows.get(sha)
        if row is None:
            entries.append({"content_sha256": sha, "sha16": sha16, "status": "unavailable",
                            "reason": "not_in_rows"})
            continue
        pdf_path = root / (row.get("relative_path") or "")
        if not pdf_path.is_file():
            entries.append({"content_sha256": sha, "sha16": sha16, "status": "unavailable",
                            "reason": "pdf_missing"})
            continue
        data = _retry(lambda: pdf_path.read_bytes())
        if content_sha256_of(data) != sha:
            entries.append({"content_sha256": sha, "sha16": sha16, "status": "unavailable",
                            "reason": "pdf_sha_mismatch"})
            continue
        packet_dir = slice_dir / sha16
        _retry(lambda: packet_dir.mkdir(parents=True, exist_ok=True))
        render = render_pages(data, packet_dir, dpi=dpi, max_pages=max_pages)
        profile = {"label": PROFILE_LABEL,
                   "values": {field: (row.get(field) or "") for field in PROFILE_FIELDS}}
        content = packet_content(sha, slice_name, render["pages"], render,
                                 build_evidence(sha, census.get(sha), classification.get(sha), moneythumb.get(sha)),
                                 profile)
        digest = sha256_hex(canonical_json(content))
        packet = dict(content, sha16=sha16, packet_digest=digest, relative_path=row.get("relative_path") or "",
                      dpi=dpi, max_pages=max_pages)
        _write_text(packet_dir / PACKET_FILE, json.dumps(packet, indent=2, sort_keys=True) + "\n")
        _write_text(packet_dir / EVIDENCE_FILE, evidence_text(packet))
        entries.append({
            "content_sha256": sha, "sha16": sha16, "packet_dir": sha16, "packet_digest": digest,
            "page_count": render["page_count"], "pages_rendered": render["rendered"],
            "truncated": render["truncated"], "render_error": render["error"], "status": "pending",
        })
    queue = {"slice": slice_name, "created_at": utc_now_iso(), "rows_csv": str(rows_csv),
             "count": len(entries), "page_cap": max_pages, "entries": entries}
    _write_queue(slice_dir, queue)
    packets_built = sum(1 for e in entries if e["status"] == "pending")
    unavailable = len(entries) - packets_built
    truncated = sum(1 for e in entries if e.get("truncated"))
    digest = queue_digest(entries)
    _write_text(slice_dir / QUEUE_DIGEST_FILE,
                f"slice: {slice_name}\ncount: {len(entries)}\npackets: {packets_built}\n"
                f"unavailable: {unavailable}\ntruncated: {truncated} (page cap {max_pages})\n"
                f"queue_digest: {digest}\n")
    out(f"slice {slice_name}: {len(entries)} shas; packets: {packets_built}; "
        f"unavailable: {unavailable}; truncated: {truncated} (page cap {max_pages}); "
        f"queue digest {digest}; dir {slice_dir}")
    return queue


# --- run ----------------------------------------------------------------------


def _fields_from_answer(answer: Mapping) -> dict:
    unknown = set(answer) - set(ANSWER_FIELDS)
    if unknown:
        raise RecordError(f"answer carries unknown fields {sorted(unknown)}")
    fields = {key: answer.get(key) for key in ANSWER_FIELDS}
    if fields["completeness_findings"] is None:
        fields["completeness_findings"] = []
    if fields["sampled_rows"] is None:
        fields["sampled_rows"] = []
    return fields


def _int_or_none(text: str, what: str):
    text = text.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise RecordError(f"{what}: not an integer: {text!r}") from exc


def _interactive(out) -> dict | object:
    out("Type the verdict. Nothing is pre-filled; the evidence above is evidence only.")
    out("Notes are hashed (sha256) and not stored.")
    kind = ask("kind (one of " + "|".join(KINDS) + "; 'skip' | 'quit') > ").strip()
    if kind == "quit":
        return _QUIT
    if not kind or kind == "skip":
        out("no kind typed: the classifier proposal is EVIDENCE, not a default; left pending")
        return _SKIP
    fields: dict = {"kind": kind}
    fields["sub_kind"] = ask("sub_kind (lowercase code; empty for none) > ").strip() or None
    fields["account_kind"] = ask("account_kind (" + "|".join(ACCOUNT_KINDS) + ") > ").strip()
    fields["modality"] = ask("modality (" + "|".join(MODALITIES) + ") > ").strip()
    legible = ask("legible (y/n) > ").strip().lower()
    if legible not in ("y", "yes", "n", "no"):
        raise RecordError(f"legible: answer y or n, got {legible!r}")
    fields["legible"] = legible in ("y", "yes")
    findings = ask("completeness findings (comma-separated codes from "
                   + ",".join(COMPLETENESS_CODES) + "; empty for none) > ")
    fields["completeness_findings"] = [c.strip() for c in findings.split(",") if c.strip()]
    fields["account_count"] = _int_or_none(ask("account_count (integer; empty for unknown) > "), "account_count")
    fields["printed_period_start"] = ask("printed_period_start (YYYY-MM-DD; empty for none) > ").strip() or None
    fields["printed_period_end"] = ask("printed_period_end (YYYY-MM-DD; empty for none) > ").strip() or None
    fields["opening_balance"] = ask("opening_balance (plain decimal; empty for none) > ").strip() or None
    fields["closing_balance"] = ask("closing_balance (plain decimal; empty for none) > ").strip() or None
    fields["printed_transaction_count"] = _int_or_none(
        ask("printed_transaction_count (integer; empty for none) > "), "printed_transaction_count")
    rows: list[dict] = []
    for number in range(1, 4):
        line = ask(f"sampled row {number} (date | description | amount; empty to stop) > ").strip()
        if not line:
            break
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3:
            raise RecordError(f"sampled row {number}: expected date | description | amount")
        rows.append({"date": parts[0], "description": parts[1], "amount": parts[2]})
    fields["sampled_rows"] = rows
    fields["notes"] = ask("notes (hashed, not stored; empty for none) > ") or None
    if ask("append this record? (y/n) > ").strip().lower() not in ("y", "yes"):
        out("not appended; left pending")
        return _SKIP
    return fields


def run_queue(
    slice_name: str,
    packets_dir: Path,
    *,
    store: TruthStore,
    answers: Mapping | None = None,
    adjudicator: str | None = None,
    limit: int | None = None,
    out=print,
) -> dict:
    packets = refuse_inside_checkout(packets_dir, what="the packet directory")
    slice_dir = packets / slice_name
    queue_path = slice_dir / QUEUE_FILE
    if not queue_path.is_file():
        raise StoreError(f"no queue for slice {slice_name!r} under {packets}")
    store.verify_against_manifest()  # MAJOR-1: a truncated store is refused before anything is shown
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    role = validate_role((answers or {}).get("adjudicator") or adjudicator or "")
    answer_map = {
        str(key).strip().upper(): value for key, value in ((answers or {}).get("answers") or {}).items()
    }
    summary: Counter = Counter()
    processed = 0
    for entry in queue["entries"]:
        if entry.get("status") != "pending":
            continue
        if limit is not None and processed >= limit:
            break
        processed += 1
        sha = entry["content_sha256"]
        packet_dir = slice_dir / entry["packet_dir"]
        out("=" * 72)
        out(f"packet {packet_dir}")
        # MINOR-1: the digest recorded is the digest of what is on disk now.
        try:
            recomputed, packet = packet_digest_from_dir(packet_dir)
        except (OSError, ValueError, KeyError, StoreError) as exc:
            out(f"refused: packet unreadable ({type(exc).__name__}); left pending")
            summary["refused"] += 1
            continue
        if recomputed != entry.get("packet_digest") or recomputed != packet.get("packet_digest") \
                or packet.get("content_sha256") != sha:
            out("refused: packet digest mismatch (the packet was edited since queue); left pending")
            summary["refused"] += 1
            continue
        out(f"pages rendered {entry.get('pages_rendered')} of {entry.get('page_count')}"
            + (f" (cut at the {packet.get('max_pages')}-page cap)" if packet["render"].get("truncated") else "")
            + (f"; render error {entry['render_error']}" if entry.get("render_error") else ""))
        out(evidence_text(packet).rstrip("\n"))
        if answers is not None:
            answer = answer_map.get(sha)
            if answer is None:
                out("no answer supplied; left pending")
                summary["skipped"] += 1
                continue
            if not (answer.get("kind") or "").strip():
                out("no kind typed: the classifier proposal is EVIDENCE, not a default; left pending")
                summary["skipped"] += 1
                continue
            out("notes are hashed (sha256) and not stored")
            try:
                fields = _fields_from_answer(answer)
            except RecordError as exc:
                out(f"refused: {exc}; left pending")
                summary["refused"] += 1
                continue
        else:
            try:
                fields = _interactive(out)
            except RecordError as exc:
                out(f"refused: {exc}; left pending")
                summary["refused"] += 1
                continue
            if fields is _QUIT:
                out("stopped by the adjudicator")
                break
            if fields is _SKIP:
                summary["skipped"] += 1
                continue
        try:
            record = store.append_record(
                content_sha256=sha, adjudicator=role, packet_digest=recomputed, **fields
            )
            store.verify_against_manifest()
        except RecordError as exc:
            out(f"refused: {exc}; left pending")
            summary["refused"] += 1
            continue
        entry["status"] = "adjudicated"
        entry["record_id"] = record["record_id"]
        entry["adjudicated_at"] = record["adjudicated_at"]
        _write_queue(slice_dir, queue)
        summary["adjudicated"] += 1
        out(f"appended {record['record_id']}; chain verified")
    pending = sum(1 for e in queue["entries"] if e.get("status") == "pending")
    out(f"adjudicated: {summary['adjudicated']}; skipped: {summary['skipped']}; "
        f"refused: {summary['refused']}; pending: {pending}")
    return {"adjudicated": summary["adjudicated"], "skipped": summary["skipped"],
            "refused": summary["refused"], "pending": pending}


# --- status / verify / digest ------------------------------------------------


def print_status(store: TruthStore, manifest: HoldoutManifest, out=print) -> None:
    records = store.records()
    head = store.verify_against_manifest()
    latest = store.latest_by_sha()
    out(f"store: {store.directory}")
    out(f"records: {len(records)}")
    out(f"chain_head: {head}")
    out(f"documents adjudicated: {len(latest)}")
    out("by kind:")
    for kind, count in store.counts_by_kind().items():
        out(f"  {kind}: {count}")
    counts = manifest.counts_by_status()
    out(f"holdout items: {sum(counts.values())}")
    for status in HOLDOUT_STATUSES:
        out(f"  {status}: {counts[status]}")


def verify_store(store: TruthStore, manifest: HoldoutManifest, digest_path: Path | None, out=print) -> list[str]:
    head = store.verify_against_manifest()
    holdout_head = manifest.verify_against_manifest()
    out(f"truth chain: {len(store.records())} records, head {head[:16]}, agrees with manifest.json")
    out(f"holdout chain: {len(manifest.events())} events, head {holdout_head[:16]}, agrees with holdout_manifest.json")
    if digest_path is None:
        return []
    text = Path(digest_path).read_text(encoding="utf-8")
    mismatches = digest_mod.verify_against_digest(store, manifest, text)
    if mismatches:
        out(f"refused: the store disagrees with the digest {digest_path} on {mismatches}")
    else:
        out(f"the store agrees with the digest {digest_path}")
    return mismatches


def print_holdout_list(manifest: HoldoutManifest, out=print) -> None:
    items = manifest.items()
    counts = manifest.counts_by_status()
    out(f"holdout items: {len(items)}")
    for status in HOLDOUT_STATUSES:
        out(f"  {status}: {counts[status]}")
    for holdout_id in sorted(items):
        item = items[holdout_id]
        strata = item["strata"]
        out(f"{holdout_id} {item['status']} {item['source_batch']} "
            + " ".join(f"{k}={strata[k]}" for k in sorted(strata))
            + (f" engine={item['last_engine_version']}" if item.get("last_engine_version") else ""))


# --- the parser --------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.adjudicate",
                                     description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    queue = sub.add_parser("queue", help="build evidence packets for a slice (private directory)")
    queue.add_argument("--rows", type=Path, required=True)
    queue.add_argument("--slice", required=True)
    queue.add_argument("--shas", type=Path, required=True)
    queue.add_argument("--packets", type=Path, required=True, help="PRIVATE dir, outside the checkout")
    queue.add_argument("--pdf-root", type=Path, default=_this_checkout_root() / "Bank Statements")
    queue.add_argument("--census", type=Path, default=None, help="census per_sha.csv (evidence only)")
    queue.add_argument("--classification", type=Path, default=None, help="per-sha classifier CSV (evidence only)")
    queue.add_argument("--moneythumb", type=Path, default=None, help="explicit MoneyThumb comparison CSV (evidence only)")
    queue.add_argument("--dpi", type=int, default=DEFAULT_DPI)
    queue.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                       help="page cap per packet; cut packets are counted in the queue output")

    run = sub.add_parser("run", help="walk a slice's queue and record verdicts")
    run.add_argument("--slice", required=True)
    run.add_argument("--packets", type=Path, required=True)
    run.add_argument("--answers", type=Path, default=None, help="non-interactive answers (tests)")
    run.add_argument("--adjudicator", default=None, help="a role code, never an email")
    run.add_argument("--limit", type=int, default=None)

    sub.add_parser("status", help="aggregate counts for the store and the holdout")

    verify = sub.add_parser("verify", help="both chains against their manifests (and a digest)")
    verify.add_argument("--digest", type=Path, default=None,
                        help="a repository digest to anchor against (e.g. the committed MANIFEST_DIGEST.txt)")

    export = sub.add_parser("export-digest", help="write the repository digest")
    export.add_argument("--out", type=Path, default=None)

    add = sub.add_parser("holdout-add", help="add an UNSEEN document to the holdout manifest")
    add.add_argument("--sha", required=True)
    add.add_argument("--source-batch", required=True)
    add.add_argument("--dev-rows", type=Path, required=True,
                     help="the run of record's rows.csv: the ONLY source of the development corpus")
    add.add_argument("--modality", required=True, choices=MODALITIES)
    add.add_argument("--bank", required=True, choices=BANK_FAMILIARITY)
    add.add_argument("--accounts", required=True, choices=ACCOUNT_SHAPES)
    add.add_argument("--table", required=True, choices=TABLE_SHAPES)
    add.add_argument("--currency", required=True)
    add.add_argument("--pages", type=int, required=True)
    add.add_argument("--layout-family", required=True, help="a code, never a customer or bank name")

    burn = sub.add_parser("holdout-burn", help="evaluated -> burned, naming the card")
    burn.add_argument("--id", required=True)
    burn.add_argument("--by", required=True, help="the card / commit that named the item")

    graduate = sub.add_parser("holdout-graduate", help="evaluated -> graduated at a SUBSEQUENT freeze tag")
    graduate.add_argument("--id", required=True)
    graduate.add_argument("--tag", required=True, help="a freeze tag (`*-final`) resolved through git")
    graduate.add_argument("--attest", action="store_true",
                          help="attest the engine version did not change because of the item")
    graduate.add_argument("--attested-by", required=True)
    graduate.add_argument("--repo", type=Path, default=None,
                          help="the git repository whose tags are consulted (default: this checkout)")

    sub.add_parser("holdout-list", help="holdout items by status (no shas)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        if args.command == "queue":
            build_queue(args.rows, args.slice, args.shas, args.packets, pdf_root=args.pdf_root,
                        census_csv=args.census, classification_csv=args.classification,
                        moneythumb_csv=args.moneythumb, dpi=args.dpi, max_pages=args.max_pages)
        elif args.command == "run":
            answers = None
            if args.answers is not None:
                answers = json.loads(Path(args.answers).read_text(encoding="utf-8"))
            run_queue(args.slice, args.packets, store=TruthStore.open(), answers=answers,
                      adjudicator=args.adjudicator, limit=args.limit)
        elif args.command == "status":
            print_status(TruthStore.open(), HoldoutManifest.open())
        elif args.command == "verify":
            if verify_store(TruthStore.open(), HoldoutManifest.open(), args.digest):
                return 1
        elif args.command == "export-digest":
            target = digest_mod.export_digest(path=args.out)
            parsed = digest_mod.parse_digest(target.read_text(encoding="utf-8"))
            print(f"digest written: {target} (records {parsed['record_count']}, "
                  f"holdout {len(parsed['holdout_sha16_status'])})")
        elif args.command == "holdout-add":
            try:
                strata = build_strata(modality=args.modality, bank_familiarity=args.bank,
                                      account_shape=args.accounts, table_shape=args.table,
                                      currency=args.currency, page_count=args.pages,
                                      layout_family_code=args.layout_family)
            except ValueError as exc:
                print(f"refused: {exc}", file=sys.stderr)
                return 2
            dev_corpus = dev_corpus_from_rows(args.dev_rows)
            manifest = HoldoutManifest.open()
            item = manifest.add(content_sha256=args.sha, source_batch=args.source_batch,
                                strata=strata, dev_corpus=dev_corpus)
            print(f"added {item['holdout_id']} ({item['status']}); dev corpus {dev_corpus.source}: "
                  f"{dev_corpus.size} shas over {dev_corpus.rows} rows, digest {dev_corpus.digest[:16]}")
        elif args.command == "holdout-burn":
            item = HoldoutManifest.open().burn(args.id, burned_by=args.by)
            print(f"{item['holdout_id']} -> {item['status']} by {item['burned_by']}")
        elif args.command == "holdout-graduate":
            repo = Path(args.repo) if args.repo is not None else _this_checkout_root()
            item = HoldoutManifest.open().graduate(
                args.id, graduated_at_tag=args.tag, freeze_tags=freeze_tags_from_git(repo),
                attest_engine_version_unchanged=bool(args.attest), attested_by=args.attested_by,
            )
            print(f"{item['holdout_id']} -> {item['status']} at {item['graduated_at_tag']} "
                  f"(commit {item['graduation_attestation']['tag_commit'][:12]})")
        elif args.command == "holdout-list":
            print_holdout_list(HoldoutManifest.open())
        else:  # pragma: no cover - argparse restricts the choices
            parser.error(f"unknown command {args.command!r}")
    except StoreError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
