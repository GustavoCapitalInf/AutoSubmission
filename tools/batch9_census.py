"""batch9_census.py — deterministic census of every NON-validated content sha of a run.

    python -m tools.batch9_census \
        [--run <run dir>] [--data-dir <cold WEBAPP_DATA_DIR>] \
        [--b8-census-ref 10cc722] [--out-dir docs/moneythumb-replacement/census_batch9] \
        [--report docs/moneythumb-replacement/CENSUS_BATCH9.md]

Batch 9 opens from the frozen batch-8 state (main / `batch8-final` = 68110ce;
official run TRAIN8-7185633 / cda8882d; 3,380 shas; 2,596 validated). This
instrument enumerates the remaining non-validated shas ONCE, mechanically, so
that later sessions never rediscover the population. It is read-only over the
run artifacts and the run's own cold cache; it runs no parser, no OCR and no
model, and it writes nothing outside `--out-dir` / `--report`.

Inputs (all pre-existing, all keyed by content sha):
  * `<run>/rows.csv` — one row per archive path; collapsed to one record per
    sha exactly as `discovery.evidence.load_run` collapses it (the outcome is
    identical across a sha's duplicate rows; the instrument asserts that).
  * `<run>/telemetry.jsonl` — dispatch scores / attempted / exceptions, stage
    timings, diagnostics (evaluated, adb_checks_failed, integrity_flags, codes).
  * `<run>/train8_compare.md` — the control -> train-8 movement for each sha.
  * `<data-dir>/webapp.db` + `<data-dir>/artifacts/` — the run's own OCR
    artifact per sha (text-layer metrics; NEVER the text) and, for the shas
    whose reader published a payload (withheld / review), the analysis artifact
    resolved by `webapp.artifact_cache.analysis_input_sha` over that OCR text —
    the same key the run used, imported, never re-derived.
  * `git show <ref>:docs/moneythumb-replacement/CENSUS_BATCH8_DIGITAL.md` —
    the batch-8 census's per-sha family lists. The committed copy was redacted
    at cc64232 by a digit-run regex that also damaged the 64-hex shas, so the
    sha lists are read from the pre-redaction commit; ONLY shas, family keys and
    the census's own per-family estimates (n / expected / confidence — census
    numbers, not archive figures) cross from it. No prose is copied.
  * `docs/agent-handoffs/*.md` — which batch card named a family key (a
    substring test; deterministic).
  * the live parser registry — registered bank labels (OUR constants) as the
    only vocabulary a text hint may be expressed in.

What crosses into the artifacts: shas, folder labels, registry ids and labels,
telemetry codes and counts, ratios and per-page densities, booleans. No
document text, amount, name, account number or address is ever read into an
output field: the text is reduced to metrics in memory and dropped. The
instrument scans its own outputs (shas masked first) for digit runs and
money-shaped tokens and refuses to write if any are found (exit 3).

Classification rules are FIXED and listed in the report; anything the rules
cannot decide is `unknown`. A batch-8 census family is evidence (a committed
artifact); a near-miss dispatch score is NOT identity evidence (a score below
CLAIM_THRESHOLD means "not every required marker fired") and is recorded as a
candidate only. Expected-yield / difficulty / cost columns are NOT computed
here — they are Ocean's estimates, kept in `<out-dir>/opportunity_estimates.json`
and rendered under their own heading so measurement and judgement never share
a column.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sqlite3
import string
import subprocess
import sys
from pathlib import Path

SHA_LINE = re.compile(r"^[0-9A-F]{64}$")
SHA64 = re.compile(r"[0-9A-F]{64}")
SHA16 = re.compile(r"\b[0-9A-F]{16}\b")
MONEY_TOKEN = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})*\.\d{2}(?![\w])")
DATE_TOKEN = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
ALPHA_WORD = re.compile(r"[A-Za-z]{3,}")
VOWEL = re.compile(r"[aeiouyAEIOUY]")
PUNCT = set(string.punctuation)

#: Words that make a registry bank label a TEMPLATE name rather than an
#: institution; a label made only of these is not a text hint vocabulary entry.
GENERIC_LABEL_WORDS = frozenset({
    "core", "processor", "enclosures", "daily", "sectioned", "counted", "activity",
    "summary", "signed", "counts", "balance", "by", "date", "category", "partition",
    "community", "section", "scanned", "small", "bank", "statement", "export",
    "releve", "facturation", "found", "lead", "generic", "template", "platform",
})

#: The batch-8 withheld census's cause codes, keyed by the ADB check that failed.
ADB_CHECK_CODE = {
    "ledger_reconciles_to_closing": "A",
    "final_balance_matches_statement_closing": "A",
    "running_balances_support_daily_ledger": "B",
    "posting_dates_cover_source": "C",
    "transactions_within_period": "D",
    "opening_balance_matches_statement": "F",
}

UNLABELLED_FOLDERS = frozenset({"misc", "others", "unidentified", "(root)", "root", ""})

DEFAULT_RUN_POINTER = Path("discovery_reports/train8-logs/train8_run_dir.txt")
DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_B8_REF = "10cc722"
B8_CENSUS_PATH = "docs/moneythumb-replacement/CENSUS_BATCH8_DIGITAL.md"
HANDOFF_DIR = Path("docs/agent-handoffs")


# ----------------------------------------------------------------------------
# run artifacts
# ----------------------------------------------------------------------------

def read_run_pointer(pointer: Path) -> Path:
    return Path(pointer.read_text(encoding="utf-8").strip())


def load_rows(run: Path) -> dict[str, dict]:
    """sha -> the first row plus the set of folder labels / path count."""
    by_sha: dict[str, dict] = {}
    with (run / "rows.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if not sha:
                continue
            entry = by_sha.get(sha)
            if entry is None:
                by_sha[sha] = {"row": row, "n_paths": 1, "folders": [row.get("folder_label") or ""],
                               "outcomes": {row.get("outcome_class") or ""}}
            else:
                entry["n_paths"] += 1
                if (row.get("folder_label") or "") not in entry["folders"]:
                    entry["folders"].append(row.get("folder_label") or "")
                entry["outcomes"].add(row.get("outcome_class") or "")
    conflicts = [s for s, e in by_sha.items() if len(e["outcomes"]) > 1]
    if conflicts:
        raise SystemExit(f"rows.csv: {len(conflicts)} shas carry more than one outcome class — refusing")
    return by_sha


def load_telemetry(run: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    with (run / "telemetry.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            sha = ((record.get("document") or {}).get("content_sha256") or "").upper()
            if sha:
                records[sha] = record          # last writer wins, as load_run does
    return records


def load_movers(run: Path) -> dict[str, dict]:
    """sha16 -> movement row from train8_compare.md (comparable movers table)."""
    path = run / "train8_compare.md"
    movers: dict[str, dict] = {}
    if not path.is_file():
        return movers
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| improved") and not line.startswith("| regressed") \
                and not line.startswith("| unranked"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        direction, sha16, _folder, before, after, parsers = cells[:6]
        movers[sha16] = {"direction": direction, "before": before, "after": after, "parsers": parsers}
    return movers


# ----------------------------------------------------------------------------
# the batch-8 census (pre-redaction sha lists, committed keys)
# ----------------------------------------------------------------------------

def git_show(ref: str, path: str) -> str:
    out = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, check=True)
    return out.stdout.decode("utf-8")


def _sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _fenced_json(lines: list[str]):
    """The first fenced block of a section, parsed as JSON (None if none/invalid)."""
    block: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("```"):
            if inside:
                break
            inside = True
            continue
        if inside:
            block.append(line)
    if not block:
        return None
    try:
        return json.loads("\n".join(block))
    except ValueError:
        return None


def _num(token: str) -> float | None:
    try:
        return float(token.strip())
    except ValueError:
        return None


def parse_b8_census(text: str) -> dict:
    sections = _sections(text)
    membership: dict[str, tuple[str, str]] = {}
    duplicates: list[str] = []
    families: dict[str, dict] = {}

    def put(sha: str, kind: str, key: str) -> None:
        if sha in membership:
            duplicates.append(sha)
            return
        membership[sha] = (kind, key)

    header = re.compile(r"^### (\d+)\. `([^`]+)` \(n=(\d+), expected ([^,]+), ([^)]+)\)")
    key = None
    for line in sections.get("Family records", []):
        match = header.match(line)
        if match:
            key = match.group(2)
            families[key] = {"rank": int(match.group(1)), "n": int(match.group(3)),
                             "expected": _num(match.group(4)), "conf": _num(match.group(5))}
            continue
        if key and SHA_LINE.match(line.strip()):
            put(line.strip(), "family", key)

    singles = _fenced_json(sections.get("singletons", []))
    if isinstance(singles, list):
        for item in singles:
            if isinstance(item, dict) and SHA_LINE.match(str(item.get("sha", ""))):
                fam = str(item.get("family_key") or "singleton")
                put(item["sha"], "singleton", fam)
                families.setdefault(fam, {"rank": None, "n": 1, "expected": _num(str(item.get("confidence", ""))),
                                          "conf": _num(str(item.get("confidence", "")))})

    for title, kind in (("Text-layer defects (route to OCR)", "text_layer_defect"),
                        ("Portal and range exports (not statements)", "portal_export"),
                        ("not_statements", "not_statement"),
                        ("no_text", "no_text")):
        for line in sections.get(title, []):
            for sha in SHA64.findall(line):
                put(sha, kind, kind)

    withheld: dict[str, dict] = {}
    for line in sections.get("Per-document list", []):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.fullmatch(r"[0-9A-F]{16}", cells[0]):
            withheld[cells[0]] = {"parser": cells[1].strip("`"), "cause": cells[2]}

    return {"membership": membership, "families": families, "withheld": withheld,
            "duplicates": sorted(set(duplicates)), "total": len(membership)}


def handoff_mentions(family_keys: list[str]) -> dict[str, list[str]]:
    mentions: dict[str, list[str]] = {k: [] for k in family_keys}
    if not HANDOFF_DIR.is_dir():
        return mentions
    for path in sorted(HANDOFF_DIR.glob("*.md")):
        body = path.read_text(encoding="utf-8", errors="replace")
        for key in family_keys:
            if key in body:
                mentions[key].append(path.stem)
    return mentions


# ----------------------------------------------------------------------------
# registry vocabulary and the cold cache
# ----------------------------------------------------------------------------

def registry_label_patterns() -> list[tuple[str, re.Pattern]]:
    from analysis import parser_registry_entries  # noqa: F401  (populates the registry)
    from analysis.parser_registry import registrations

    seen: dict[str, re.Pattern] = {}
    for registration in registrations():
        bank = (registration.bank or "").strip()
        words = re.findall(r"[a-z0-9]+", bank.lower())
        if not words or all(word in GENERIC_LABEL_WORDS for word in words):
            continue
        if bank in seen:
            continue
        seen[bank] = re.compile(
            r"(?<![a-z0-9])" + r"[^a-z0-9]{0,3}".join(re.escape(w) for w in words) + r"(?![a-z0-9])"
        )
    return sorted(seen.items())


class ColdCache:
    """Read-only view of the run's own artifact cache, by the run's own keys."""

    def __init__(self, data_dir: Path):
        self.root = data_dir / "artifacts"
        self.conn = sqlite3.connect(str(data_dir / "webapp.db"))
        from ocr.document import StatementMarkdown
        from webapp.artifact_cache import analysis_input_sha
        self._markdown = StatementMarkdown
        self._input_sha = analysis_input_sha

    def _payload(self, stage: str, input_sha: str) -> tuple[bool, dict | None]:
        rows = self.conn.execute(
            "SELECT artifact_path FROM artifact_cache WHERE stage = ? AND input_sha256 = ?",
            (stage, input_sha),
        ).fetchall()
        if not rows:
            return False, None
        path = self.root / rows[0][0]
        try:
            return True, json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False, None

    def ocr_document(self, sha: str) -> tuple[str, dict | None]:
        """('hit'|'negative'|'absent', document)."""
        hit, payload = self._payload("ocr", sha)
        if not hit:
            return "absent", None
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            return "negative", None
        return "hit", document

    def analysis(self, document: dict) -> dict | None:
        pages = [str(page) for page in (document.get("pages") or [])]
        markdown = self._markdown(source_file="census.pdf", model=str(document.get("model") or ""),
                                  pages=pages).to_markdown()
        hit, payload = self._payload("analysis", self._input_sha(markdown, pages))
        if not hit:
            return None
        try:
            return payload["artifact"]["analysis"]
        except (KeyError, TypeError):
            return None


# ----------------------------------------------------------------------------
# per-document derivations (metrics only — the text never leaves this function)
# ----------------------------------------------------------------------------

def text_metrics(pages: list[str]) -> dict:
    text = "\n".join(pages)
    n = len(text)
    out = {"ocr_pages": len(pages), "chars_total": n}
    if n == 0:
        out.update({"chars_per_page": 0, "digit_share": None, "alpha_share": None, "other_share": None,
                    "nonascii_share": None, "vowel_word_share": None, "money_per_page": 0,
                    "date_per_page": 0, "low_text_pages": len(pages)})
        return out
    digits = sum(c.isdigit() for c in text)
    alpha = sum(c.isalpha() for c in text)
    space = sum(c.isspace() for c in text)
    punct = sum(c in PUNCT for c in text)
    nonascii = sum(ord(c) > 127 for c in text)
    words = ALPHA_WORD.findall(text)
    vowel = sum(1 for w in words if VOWEL.search(w))
    pages_n = max(len(pages), 1)
    out.update({
        "chars_per_page": round(n / pages_n),
        "digit_share": round(digits / n, 3),
        "alpha_share": round(alpha / n, 3),
        "other_share": round(max(n - digits - alpha - space - punct, 0) / n, 3),
        "nonascii_share": round(nonascii / n, 3),
        "vowel_word_share": round(vowel / len(words), 3) if words else None,
        "money_per_page": round(len(MONEY_TOKEN.findall(text)) / pages_n, 1),
        "date_per_page": round(len(DATE_TOKEN.findall(text)) / pages_n, 1),
        "low_text_pages": sum(1 for p in pages if len(p.strip()) < 200),
    })
    return out


def text_density(metrics: dict) -> str:
    """Fixed thresholds over per-page densities: `dense` (>= 1500 chars and >= 8
    money-shaped tokens per page), `thin` (< 600 chars or < 3 money tokens per
    page), `medium` otherwise, `none` without text."""
    if not metrics.get("ocr_pages"):
        return "none"
    chars, money = metrics["chars_per_page"], metrics["money_per_page"]
    if chars >= 1500 and money >= 8:
        return "dense"
    if chars < 600 or money < 3:
        return "thin"
    return "medium"


MAGIC_KINDS = ((b"%PDF", "pdf"), (b"\xac\xed\x00\x05", "java-serialized"), (b"PK", "zip"),
               (b"<", "html/xml"), (b"{", "json"), (b"[", "json"))


def file_magic(path: Path) -> str:
    """A kind label for the first bytes of a file (the bytes never leave here)."""
    try:
        head = path.read_bytes()[:8]
    except OSError:
        return "unreadable"
    for prefix, kind in MAGIC_KINDS:
        if head.startswith(prefix):
            return kind
    return "other"


def load_hash_map(run: Path) -> dict[str, str]:
    """sha -> first archive-relative path (used ONLY to read magic bytes)."""
    first: dict[str, str] = {}
    path = run / "hash_map.csv"
    if not path.is_file():
        return first
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            first.setdefault((row.get("content_sha256") or "").upper(), row.get("relative_path") or "")
    return first


def bank_hits(pages: list[str], patterns: list[tuple[str, re.Pattern]]) -> tuple[list[str], int]:
    first = next((p for p in pages if len(p.strip()) >= 50), pages[0] if pages else "")
    first_l = first.lower()
    all_l = "\n".join(pages).lower()
    p1 = [label for label, pattern in patterns if pattern.search(first_l)]
    everywhere = sum(1 for _label, pattern in patterns if pattern.search(all_l))
    return p1, everywhere


def analysis_facts(payload: dict | None) -> dict:
    keys = ("recon_ok", "summary_ok", "credit_coverage", "debit_coverage", "continuity_breaks",
            "currency", "currency_source", "period_present", "days_in_period", "n_transactions",
            "stated_counts_present", "stated_totals_present", "stated_daily_balances_n",
            "quality_level", "adb_ok")
    facts = {k: None for k in keys}
    if not payload:
        return facts
    stmt = payload.get("statement") or {}
    recon = payload.get("reconciliation") or {}
    metrics = payload.get("metrics") or {}
    quality = payload.get("quality") or {}
    facts.update({
        "recon_ok": recon.get("ok"),
        "summary_ok": recon.get("summary_ok"),
        "credit_coverage": None if recon.get("credit_coverage") is None else round(float(recon["credit_coverage"]), 3),
        "debit_coverage": None if recon.get("debit_coverage") is None else round(float(recon["debit_coverage"]), 3),
        "continuity_breaks": recon.get("continuity_breaks"),
        "currency": stmt.get("currency"),
        "currency_source": stmt.get("currency_source"),
        "period_present": bool(stmt.get("period_start")) and bool(stmt.get("period_end")),
        "days_in_period": stmt.get("days_in_period"),
        "n_transactions": len(stmt.get("transactions") or []),
        "stated_counts_present": stmt.get("stated_credit_count") is not None
        and stmt.get("stated_debit_count") is not None,
        "stated_totals_present": stmt.get("stated_total_credits") is not None
        and stmt.get("stated_total_debits") is not None,
        "stated_daily_balances_n": len(stmt.get("stated_daily_balances") or []),
        "quality_level": quality.get("level"),
        "adb_ok": metrics.get("adb_ok"),
    })
    return facts


def failure_stage(outcome_class: str, reason: str) -> str:
    if reason in ("invalid_pdf", "encrypted"):
        return "preflight"
    if outcome_class == "deferred":
        return "ocr:no-text"
    if outcome_class == "withheld":
        return "analysis:adb-withheld"
    if outcome_class == "review":
        return "analysis:integrity-review"
    if reason == "no_parser_matched":
        return "dispatch:unclaimed"
    if reason == "parser_declined":
        return "dispatch:declined"
    if reason == "parser_exception":
        return "dispatch:parser-exception"
    if reason == "ocr_failed":
        return "ocr:failed"
    return f"other:{outcome_class}:{reason}"


def assign_cluster(rec: dict) -> tuple[str, str, str]:
    """(cluster, cluster_group, evidence). Fixed rules; see the module docstring."""
    oc, reason = rec["outcome_class"], rec["outcome_reason"]
    parser = rec["parser_id"] or "-"
    if reason in ("invalid_pdf", "encrypted"):
        return "PF-INVALID-PDF", "PF-INVALID-PDF", "rows.csv outcome_reason (preflight)"
    if oc == "deferred":
        return "OCR-NEGATIVE", "OCR-NEGATIVE", "telemetry deferred_visual_ocr; cached negative OCR artifact"
    if oc == "withheld":
        checks = [c for c in rec["adb_checks_failed"].split(";") if c]
        codes = sorted({ADB_CHECK_CODE.get(c, c) for c in checks}) or ["E"]
        return f"WH:{parser}:{'+'.join(codes)}", f"WH:{parser}", "telemetry diagnostics.adb_checks_failed"
    if oc == "review":
        flags = sorted({f for f in rec["integrity_flags"].split(";") if f}) or ["none"]
        return f"RV:{parser}:{'+'.join(flags)}", f"RV:{parser}", "telemetry diagnostics.integrity_flags"
    if reason == "parser_declined":
        attempted = rec["attempted"] or "unknown"
        return f"DECL:{attempted}", f"DECL:{attempted}", "telemetry dispatch.attempted (claimed at detection, parse returned None)"
    if reason == "parser_exception":
        return f"CRASH:{rec['attempted'] or 'unknown'}", "CRASH", "telemetry dispatch.exceptions"
    if reason == "no_parser_matched":
        kind, key = rec["_b8"]
        if kind in ("family", "singleton"):
            return f"FAM:{key}", f"FAM:{key}", f"CENSUS_BATCH8_DIGITAL {kind} sha list (10cc722)"
        if kind == "text_layer_defect":
            return "TEXT-LAYER-DEFECT", "TEXT-LAYER-DEFECT", "CENSUS_BATCH8_DIGITAL text-layer defects list (10cc722)"
        if kind == "portal_export":
            return "NOT-STATEMENT:portal-export", "NOT-STATEMENT", "CENSUS_BATCH8_DIGITAL portal/range exports list (10cc722)"
        if kind == "not_statement":
            return "NOT-STATEMENT:other", "NOT-STATEMENT", "CENSUS_BATCH8_DIGITAL not_statements list (10cc722)"
        if kind == "no_text":
            return "NO-TEXT", "NO-TEXT", "CENSUS_BATCH8_DIGITAL no_text list (10cc722)"
        if rec["ocr_status"] == "hit" and rec["chars_total"] == 0:
            return "NO-TEXT", "NO-TEXT", "OCR artifact holds 0 characters"
        hint = rec["bank_hint"] if rec["bank_hint"] != "unknown" else "unknown"
        if rec["text_route"] == "ocr_tesseract":
            return f"SCAN-UNCLAIMED:{hint}", "SCAN-UNCLAIMED", "not in the batch-8 census (digital only); source_path local_tesseract"
        return f"DIG-UNCLAIMED-NEW:{hint}", "DIG-UNCLAIMED-NEW", "digital, unclaimed, not in the batch-8 census sha lists"
    return f"OTHER:{oc}:{reason}", "OTHER", "unmapped outcome/reason"


# ----------------------------------------------------------------------------
# output hygiene
# ----------------------------------------------------------------------------

DIGIT_RUN = re.compile(r"\d{7,}")
MONEY_SHAPE = re.compile(r"\d{1,3}(?:,\d{3})+\.\d{2}|\d{4,}\.\d{2}")


def privacy_findings(text: str, known: tuple[str, ...] = ()) -> list[str]:
    """Digit runs / money-shaped tokens left after masking shas and the run's own
    identifiers (`known`: run dir, run id, data dir — constants, not document facts)."""
    masked = text
    for token in sorted((k for k in known if k), key=len, reverse=True):
        masked = masked.replace(token, "<known>")
    masked = SHA64.sub("<sha>", masked)
    masked = SHA16.sub("<sha16>", masked)
    found = [m.group(0) for m in DIGIT_RUN.finditer(masked)]
    found += [m.group(0) for m in MONEY_SHAPE.finditer(masked)]
    return found


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

COLUMNS = [
    "sha", "sha16", "outcome_class", "outcome_reason", "error_type", "failure_stage",
    "folder_label", "folder_labels_all", "n_paths", "dedup_status",
    "classification", "source_path", "text_route", "page_count", "size_kb", "file_magic", "truncated_pages",
    "parser_id", "dispatch_outcome", "attempted", "candidates", "near_miss_top3", "parser_exceptions",
    "analysis_stage_reached", "evaluated", "payload_resolved",
    "recon_ok", "summary_ok", "credit_coverage", "debit_coverage", "continuity_breaks",
    "adb_checks_failed", "integrity_flags", "primary_class", "diag_codes_n",
    "currency", "currency_source", "period_present", "days_in_period", "n_transactions",
    "stated_counts_present", "stated_totals_present", "stated_daily_balances_n", "claim_names_issuer",
    "quality_level", "adb_ok",
    "b8_kind", "b8_family", "b8_family_rank", "b8_family_n", "b8_family_expected", "b8_family_conf",
    "b8_withheld_parser", "b8_withheld_cause", "b8_movement",
    "ocr_status", "ocr_pages", "chars_total", "chars_per_page", "digit_share", "alpha_share", "other_share",
    "nonascii_share", "vowel_word_share", "money_per_page", "date_per_page", "low_text_pages", "text_density",
    "bank_hits_p1", "bank_hits_all_n", "bank_hint", "bank_hint_source",
    "layout_family", "layout_family_source",
    "cluster", "cluster_group", "cluster_evidence",
]


def _join(values) -> str:
    return ";".join(str(v) for v in values if v not in (None, ""))


def build_records(args) -> tuple[list[dict], dict]:
    run = args.run
    rows = load_rows(run)
    telemetry = load_telemetry(run)
    movers = load_movers(run)
    b8 = parse_b8_census(git_show(args.b8_census_ref, B8_CENSUS_PATH))
    patterns = registry_label_patterns()
    cache = ColdCache(args.data_dir)
    hash_map = load_hash_map(run)
    archive_root = Path(args.archive_root) if args.archive_root else None

    population = sorted(s for s, e in rows.items() if e["row"]["outcome_class"] != "validated")
    records: list[dict] = []
    for sha in population:
        entry = rows[sha]
        row = entry["row"]
        tel = telemetry.get(sha) or {}
        dispatch = tel.get("dispatch") or {}
        diag = tel.get("diagnostics") or {}
        stages = tel.get("stages") or {}
        outcome_class, reason = row["outcome_class"], row["outcome_reason"]
        source_path = row.get("source_path") or "none"
        text_route = {"native": "native", "local_tesseract": "ocr_tesseract"}.get(source_path, "none")

        ocr_status, document = cache.ocr_document(sha)
        pages = [str(p) for p in (document.get("pages") or [])] if document else []
        metrics = text_metrics(pages) if document else {
            "ocr_pages": 0, "chars_total": 0, "chars_per_page": 0, "digit_share": None, "alpha_share": None,
            "other_share": None, "nonascii_share": None, "vowel_word_share": None, "money_per_page": 0,
            "date_per_page": 0, "low_text_pages": 0}
        hits_p1, hits_all = bank_hits(pages, patterns) if pages else ([], 0)

        payload = None
        if document and outcome_class in ("withheld", "review"):
            payload = cache.analysis(document)
        facts = analysis_facts(payload)

        kind, key = b8["membership"].get(sha, ("none", ""))
        fam_meta = b8["families"].get(key, {}) if kind in ("family", "singleton") else {}
        wh = b8["withheld"].get(sha[:16], {})
        mover = movers.get(sha[:16])

        folder = (row.get("folder_label") or "").strip()
        folder_is_bank = folder.lower() not in UNLABELLED_FOLDERS
        if folder_is_bank:
            bank_hint, hint_source = folder, "human folder label"
        elif len(hits_p1) == 1:
            bank_hint, hint_source = hits_p1[0], "registry bank label found on the first text page"
        else:
            bank_hint, hint_source = "unknown", ("no single registry label on the first page"
                                                 if pages else "no text available")
        if kind in ("family", "singleton"):
            layout_family, layout_source = key, f"CENSUS_BATCH8_DIGITAL {kind} (10cc722)"
        else:
            layout_family, layout_source = "unknown", "no committed family assignment"

        scores = dispatch.get("scores") or []
        near = [f"{name}:{score}" for name, score in scores if score < 0.5][:3]
        magic = ""
        if reason in ("invalid_pdf", "encrypted") and archive_root is not None and hash_map.get(sha):
            magic = file_magic(archive_root / hash_map[sha])
        rec = {
            "sha": sha, "sha16": sha[:16],
            "outcome_class": outcome_class, "outcome_reason": reason,
            "error_type": row.get("error_type") or "",
            "failure_stage": failure_stage(outcome_class, reason),
            "folder_label": folder, "folder_labels_all": "|".join(entry["folders"]),
            "n_paths": entry["n_paths"], "dedup_status": row.get("dedup_status") or "",
            "classification": row.get("classification") or "", "source_path": source_path,
            "text_route": text_route, "page_count": row.get("page_count") or "",
            "size_kb": (int(row["byte_size"]) // 1024 if (row.get("byte_size") or "").isdigit() else ""),
            "truncated_pages": row.get("truncated_pages") or "",
            "parser_id": dispatch.get("parser_id") or "", "dispatch_outcome": dispatch.get("outcome") or "",
            "attempted": _join(dispatch.get("attempted") or []),
            "candidates": _join(f"{n}:{s}" for n, s in (dispatch.get("candidates") or [])),
            "near_miss_top3": _join(near),
            "parser_exceptions": _join(":".join(str(x) for x in e) for e in (dispatch.get("exceptions") or [])),
            "analysis_stage_reached": "analysis" in stages,
            "evaluated": bool(diag.get("evaluated")),
            "payload_resolved": payload is not None,
            **facts,
            "adb_checks_failed": _join(diag.get("adb_checks_failed") or []),
            "integrity_flags": _join(diag.get("integrity_flags") or []),
            "primary_class": diag.get("primary_class") or "",
            "diag_codes_n": len(diag.get("codes") or []),
            "claim_names_issuer": bool((row.get("statement_bank") or "").strip()),
            "b8_kind": kind, "b8_family": key if kind in ("family", "singleton") else "",
            "b8_family_rank": fam_meta.get("rank") if fam_meta else "",
            "b8_family_n": fam_meta.get("n") if fam_meta else "",
            "b8_family_expected": fam_meta.get("expected") if fam_meta else "",
            "b8_family_conf": fam_meta.get("conf") if fam_meta else "",
            "b8_withheld_parser": wh.get("parser", ""), "b8_withheld_cause": wh.get("cause", ""),
            "b8_movement": (f"{mover['direction']}:{mover['before']}->{mover['after']}" if mover
                            else f"unchanged:{outcome_class}/{reason}"),
            "ocr_status": ocr_status, **metrics, "text_density": text_density(metrics),
            "file_magic": magic,
            "bank_hits_p1": _join(hits_p1), "bank_hits_all_n": hits_all,
            "bank_hint": bank_hint, "bank_hint_source": hint_source,
            "layout_family": layout_family, "layout_family_source": layout_source,
            "_b8": (kind, key),
        }
        rec["cluster"], rec["cluster_group"], rec["cluster_evidence"] = assign_cluster(rec)
        records.append(rec)

    meta = {
        "run_dir": str(run), "run_id": (next(iter(telemetry.values()), {}) or {}).get("run_id"),
        "data_dir": str(args.data_dir), "b8_census_ref": args.b8_census_ref,
        "shas_total": len(rows), "population": len(population),
        "b8_census_total": b8["total"], "b8_census_duplicates": b8["duplicates"],
        "b8_families": b8["families"], "b8_withheld_n": len(b8["withheld"]),
        "registry_labels": [label for label, _ in patterns],
        "outcomes_all": dict(collections.Counter(e["row"]["outcome_class"] for e in rows.values())),
    }
    return records, meta


# ----------------------------------------------------------------------------
# aggregation and rendering
# ----------------------------------------------------------------------------

def aggregate(records: list[dict], meta: dict) -> dict:
    groups: dict[str, dict] = {}
    for rec in records:
        g = groups.setdefault(rec["cluster_group"], {
            "docs": 0, "outcomes": collections.Counter(), "routes": collections.Counter(),
            "clusters": collections.Counter(), "shas16": [], "folders": collections.Counter(),
            "bank_hints": collections.Counter(), "b8_kinds": collections.Counter(),
            "movement": collections.Counter(), "density": collections.Counter(), "b8_overlap": 0,
        })
        g["docs"] += 1
        g["density"][rec["text_density"]] += 1
        g["b8_overlap"] += int(rec["b8_kind"] != "none" or bool(rec["b8_withheld_cause"]))
        g["outcomes"][f"{rec['outcome_class']}/{rec['outcome_reason']}"] += 1
        g["routes"][rec["text_route"]] += 1
        g["clusters"][rec["cluster"]] += 1
        g["shas16"].append(rec["sha16"])
        g["folders"][rec["folder_label"] or "(unlabelled)"] += 1
        g["bank_hints"][rec["bank_hint"]] += 1
        g["b8_kinds"][rec["b8_kind"]] += 1
        g["movement"][rec["b8_movement"].split(":")[0]] += 1
    for g in groups.values():
        for k in ("outcomes", "routes", "clusters", "folders", "bank_hints", "b8_kinds", "movement", "density"):
            g[k] = dict(sorted(g[k].items(), key=lambda kv: (-kv[1], kv[0])))
        g["shas16"].sort()

    # institution roll-up: one reader per institution is a shared root cause that
    # cuts across FAM / DECL / WH / RV / SCAN groups. Non-document groups excluded.
    excluded = {"NOT-STATEMENT", "PF-INVALID-PDF", "OCR-NEGATIVE", "NO-TEXT", "TEXT-LAYER-DEFECT"}
    institutions: dict[str, dict] = {}
    for rec in records:
        if rec["cluster_group"] in excluded:
            continue
        inst = institutions.setdefault(rec["bank_hint"], {"docs": 0, "by_kind": collections.Counter(),
                                                           "parsers": collections.Counter(), "families": collections.Counter()})
        inst["docs"] += 1
        inst["by_kind"][rec["cluster_group"].split(":")[0]] += 1
        parser = rec["parser_id"] or rec["attempted"]
        if parser:
            inst["parsers"][parser] += 1
        if rec["b8_family"]:
            inst["families"][rec["b8_family"]] += 1
    for inst in institutions.values():
        for k in ("by_kind", "parsers", "families"):
            inst[k] = dict(sorted(inst[k].items(), key=lambda kv: (-kv[1], kv[0])))
    institutions = dict(sorted(institutions.items(), key=lambda kv: (-kv[1]["docs"], kv[0])))

    scan_density = collections.Counter(
        (rec["text_density"], "hint known" if rec["bank_hint"] != "unknown" else "hint unknown",
         "1 page" if str(rec["page_count"]) == "1" else "2+ pages")
        for rec in records if rec["cluster_group"] == "SCAN-UNCLAIMED")

    return {"groups": dict(sorted(groups.items(), key=lambda kv: (-kv[1]["docs"], kv[0]))),
            "institutions": institutions,
            "scan_density": {" / ".join(k): v for k, v in sorted(scan_density.items(), key=lambda kv: -kv[1])}}


def family_residual(records: list[dict], rows_outcomes: dict[str, str], b8_membership: dict,
                    families: dict, mentions: dict) -> list[dict]:
    remaining_by_family: dict[str, list[dict]] = collections.defaultdict(list)
    for rec in records:
        if rec["b8_kind"] in ("family", "singleton"):
            remaining_by_family[rec["b8_family"]].append(rec)
    members: dict[str, list[str]] = collections.defaultdict(list)
    for sha, (kind, key) in b8_membership.items():
        if kind in ("family", "singleton"):
            members[key].append(sha)
    table = []
    for key, meta in families.items():
        shas = members.get(key, [])
        now = collections.Counter(rows_outcomes.get(s, "absent") for s in shas)
        remaining = remaining_by_family.get(key, [])
        table.append({
            "family": key, "rank": meta.get("rank"), "n_b8": len(shas),
            "validated_now": now.get("validated", 0),
            "remaining": len(remaining),
            "remaining_outcomes": dict(collections.Counter(f"{r['outcome_class']}/{r['outcome_reason']}" for r in remaining)),
            "absent_from_run": now.get("absent", 0),
            "b8_expected": meta.get("expected"), "b8_conf": meta.get("conf"),
            # the census's own expectation, pro-rated to the members still non-validated
            "census_yield_remaining": (round(meta["expected"] * len(remaining) / len(shas), 2)
                                       if meta.get("expected") is not None and shas else None),
            "handoff_cards": mentions.get(key, []),
        })
    table.sort(key=lambda t: (-t["remaining"], t["rank"] if t["rank"] is not None else 10**6, t["family"]))
    return table


def load_estimates(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_counter(d: dict, limit: int = 6) -> str:
    items = list(d.items())[:limit]
    text = ", ".join(f"{k} {v}" for k, v in items)
    if len(d) > limit:
        text += f", … (+{len(d) - limit})"
    return text or "-"


def render_report(records: list[dict], meta: dict, agg: dict, residual: list[dict], estimates: dict) -> str:
    pop = collections.Counter(f"{r['outcome_class']}/{r['outcome_reason']}" for r in records)
    by_class = collections.Counter(r["outcome_class"] for r in records)
    routes = collections.Counter((r["outcome_class"], r["text_route"]) for r in records)
    stages = collections.Counter(r["failure_stage"] for r in records)
    lines = [
        f"# Batch-9 census — the {meta['population']} non-validated shas of run `{meta['run_id']}`",
        "",
        f"Produced by `tools/batch9_census.py` (deterministic; read-only; no parser, OCR or model run) over "
        f"`{meta['run_dir']}` and its cold cache `{meta['data_dir']}`. Batch-8 census sha lists read from "
        f"`{meta['b8_census_ref']}` ({meta['b8_census_total']} shas, {len(meta['b8_census_duplicates'])} duplicate "
        f"assignments). Per-sha data: `census_batch9/per_sha.csv` ({len(COLUMNS)} columns); cluster membership: "
        f"`census_batch9/clusters.json`. Documents are named by sha; no document text, amount, name or account "
        f"number is reproduced. Estimates (yield / difficulty / cost) live in `census_batch9/opportunity_estimates.json` "
        f"and are rendered under their own heading — they are Ocean's judgement, not this instrument's measurement.",
        "",
        "## Population reconciliation",
        "",
        f"| | count |", "|---|---:|",
        f"| shas in the run | {meta['shas_total']} |",
    ]
    for k in ("validated", "review", "withheld", "failed", "deferred"):
        lines.append(f"| {k} | {meta['outcomes_all'].get(k, 0)} |")
    lines += [f"| **non-validated (census population)** | **{meta['population']}** |", ""]
    lines += ["| outcome / reason | docs | native | ocr_tesseract | none |", "|---|---:|---:|---:|---:|"]
    for key, n in sorted(pop.items(), key=lambda kv: -kv[1]):
        oc = key.split("/")[0]
        lines.append(f"| {key} | {n} | {routes.get((oc, 'native'), 0) if True else 0} | "
                     f"{routes.get((oc, 'ocr_tesseract'), 0)} | {routes.get((oc, 'none'), 0)} |")
    lines += ["", "(route columns are per outcome CLASS, repeated on each reason row of that class)", ""]
    lines += ["| failure stage | docs |", "|---|---:|"]
    for k, n in sorted(stages.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {n} |")
    lines += ["", "## Classification rules (fixed)", "",
              "1. `PF-INVALID-PDF` — preflight `invalid_pdf`/`encrypted`.",
              "2. `OCR-NEGATIVE` — `deferred_visual_ocr`: local Tesseract produced no text (cached negative artifact).",
              "3. `WH:<parser>:<codes>` — withheld; codes are the batch-8 withheld census's letters for the ADB checks that failed "
              "(A ledger/closing, B running balances, C posting-date coverage, D out-of-period, E no validations run, F opening), raw check names otherwise.",
              "4. `RV:<parser>:<flags>` — review; the integrity flags as emitted.",
              "5. `DECL:<parser>` — `parser_declined`: a registration claimed at detection and its `parse` returned None.",
              "6. `FAM:<key>` — `no_parser_matched` sha listed under a batch-8 census family / singleton (committed artifact).",
              "7. `TEXT-LAYER-DEFECT`, `NOT-STATEMENT`, `NO-TEXT` — the batch-8 census's own lists; `NO-TEXT` also when the OCR artifact holds 0 characters.",
              "8. `SCAN-UNCLAIMED:<hint>` / `DIG-UNCLAIMED-NEW:<hint>` — unclaimed shas the batch-8 census (digital only) never saw; "
              "hint = the human folder label when the folder is a bank, else the single registry bank label found on the first text page, else `unknown`.",
              "", "`layout_family` is a census family key or `unknown`; `bank_hint` is a folder label or a registry label, never a token read out of the document. "
              "Near-miss scores are recorded but never used for identity (a score < 0.5 means not every required marker fired).", ""]

    lines += ["## Cluster groups (ranked by size)", "",
              "| cluster group | docs | outcomes | route | text density | in batch-8 census | batch-8 movement | bank hints (top) | fine clusters |",
              "|---|---:|---|---|---|---:|---|---|---:|"]
    for name, g in agg["groups"].items():
        lines.append(f"| `{name}` | {g['docs']} | {fmt_counter(g['outcomes'], 3)} | {fmt_counter(g['routes'], 3)} | "
                     f"{fmt_counter(g['density'], 4)} | {g['b8_overlap']} | {fmt_counter(g['movement'], 3)} | "
                     f"{fmt_counter(g['bank_hints'], 4)} | {len(g['clusters'])} |")

    lines += ["", "## Institution roll-up (shared root cause: one reader per institution)", "",
              "Across FAM / DECL / WH / RV / SCAN groups (non-document groups excluded), keyed by `bank_hint` "
              "(human folder label, else the single registry label on the first text page).", "",
              "| institution (hint) | docs | by kind | readers involved | census families |", "|---|---:|---|---|---|"]
    for name, inst in list(agg["institutions"].items())[:45]:
        lines.append(f"| {name} | {inst['docs']} | {fmt_counter(inst['by_kind'], 5)} | {fmt_counter(inst['parsers'], 4)} | "
                     f"{fmt_counter(inst['families'], 3)} |")
    if len(agg["institutions"]) > 45:
        lines.append(f"| … {len(agg['institutions']) - 45} more institutions | | | | |")

    lines += ["", "## Scanned-unclaimed text density (`SCAN-UNCLAIMED`)", "",
              "| density / hint / pages | docs |", "|---|---:|"]
    for key, n in agg["scan_density"].items():
        lines.append(f"| {key} | {n} |")
    lines += ["", "## Fine clusters (all)", "", "| cluster | docs | group |", "|---|---:|---|"]
    fine = collections.Counter(r["cluster"] for r in records)
    group_of = {r["cluster"]: r["cluster_group"] for r in records}
    for name, n in sorted(fine.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{name}` | {n} | `{group_of[name]}` |")

    lines += ["", "## Batch-8 census families — residual accounting", "",
              "Every family the batch-8 census listed, with its members' outcome in THIS run. `remaining` = still non-validated "
              "(these shas carry `FAM:<key>` above when unclaimed, or a WH/RV/DECL cluster when a reader now claims them).", "",
              "| family | b8 rank | n (b8) | validated now | remaining | remaining outcomes | b8 expected | b8 conf | census yield on remaining | handoff cards naming the key |",
              "|---|---:|---:|---:|---:|---|---:|---:|---:|---|"]
    yield_total = 0.0
    remaining_total = 0
    for t in residual:
        if t["n_b8"] == 0:
            continue
        yield_total += t["census_yield_remaining"] or 0.0
        remaining_total += t["remaining"]
        lines.append(f"| `{t['family']}` | {t['rank'] if t['rank'] is not None else '-'} | {t['n_b8']} | {t['validated_now']} | "
                     f"{t['remaining']} | {fmt_counter(t['remaining_outcomes'], 3)} | "
                     f"{'' if t['b8_expected'] is None else t['b8_expected']} | {'' if t['b8_conf'] is None else t['b8_conf']} | "
                     f"{'' if t['census_yield_remaining'] is None else t['census_yield_remaining']} | "
                     f"{', '.join(t['handoff_cards']) or '-'} |")
    lines.append(f"| **total** | | | | **{remaining_total}** | | | | **{round(yield_total, 1)}** | |")

    lines += ["", "## Registry label vocabulary used for first-page hints", "",
              ", ".join(f"`{l}`" for l in meta["registry_labels"]), ""]

    lines += ["## Opportunity table (Ocean's estimates over the measured clusters)", ""]
    if estimates:
        lines += [f"Basis: `{estimates.get('_basis', 'see opportunity_estimates.json')}`", "",
                  "| # | cluster | docs | current outcomes | root cause | likely fix | expected recoverable | confidence | difficulty | regression surface | marginal runtime/model cost | score |",
                  "|---:|---|---:|---|---|---|---|---|---|---|---|---:|"]
        rows_out = []
        for name, est in estimates.items():
            if name.startswith("_"):
                continue
            docs = sum(agg["groups"][g]["docs"] for g in est.get("groups", [name]) if g in agg["groups"])
            outcomes = collections.Counter()
            for g in est.get("groups", [name]):
                if g in agg["groups"]:
                    outcomes.update(agg["groups"][g]["outcomes"])
            rows_out.append((est.get("score", 0), name, docs, outcomes, est))
        rows_out.sort(key=lambda t: -t[0])
        for i, (score, name, docs, outcomes, est) in enumerate(rows_out, 1):
            lines.append(f"| {i} | `{name}` | {docs} | {fmt_counter(dict(outcomes), 3)} | {est.get('root_cause', '')} | "
                         f"{est.get('likely_fix', '')} | {est.get('expected_recoverable', '')} | {est.get('confidence', '')} | "
                         f"{est.get('difficulty', '')} | {est.get('regression_surface', '')} | {est.get('marginal_cost', '')} | {score} |")
        rated = {g for est in estimates.values() if isinstance(est, dict) for g in est.get("groups", [])}
        unrated = [g for g in agg["groups"] if g not in rated]
        if unrated:
            lines += ["", "Unrated cluster groups: " + ", ".join(f"`{g}` ({agg['groups'][g]['docs']})" for g in unrated)]
    else:
        lines.append("_No estimates file present; measurement only._")

    lines += ["", "## Appendix — sha16 lists per cluster group", ""]
    for name, g in agg["groups"].items():
        lines += [f"### `{name}` ({g['docs']})", "", "```", *g["shas16"], "```", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=None, help="run directory (default: the train8 pointer file)")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--b8-census-ref", default=DEFAULT_B8_REF)
    parser.add_argument("--archive-root", default="Bank Statements",
                        help="archive root, read ONLY for the magic bytes of invalid-PDF shas ('' to skip)")
    parser.add_argument("--out-dir", type=Path, default=Path("docs/moneythumb-replacement/census_batch9"))
    parser.add_argument("--report", type=Path, default=Path("docs/moneythumb-replacement/CENSUS_BATCH9.md"))
    args = parser.parse_args(argv)
    if args.run is None:
        args.run = read_run_pointer(DEFAULT_RUN_POINTER)

    records, meta = build_records(args)
    rows_outcomes = {}
    with (args.run / "rows.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows_outcomes.setdefault((row.get("content_sha256") or "").upper(), row.get("outcome_class") or "")
    b8 = parse_b8_census(git_show(args.b8_census_ref, B8_CENSUS_PATH))
    mentions = handoff_mentions(sorted(b8["families"]))
    agg = aggregate(records, meta)
    residual = family_residual(records, rows_outcomes, b8["membership"], b8["families"], mentions)
    estimates = load_estimates(args.out_dir / "opportunity_estimates.json")

    # --- serialise
    out_csv = []
    for rec in records:
        out_csv.append({c: ("" if rec.get(c) is None else rec.get(c)) for c in COLUMNS})
    buffer_csv = []
    import io
    sink = io.StringIO()
    writer = csv.DictWriter(sink, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(out_csv)
    csv_text = sink.getvalue()
    clusters_json = json.dumps({
        "meta": {k: v for k, v in meta.items() if k != "b8_families"},
        "groups": {name: {"docs": g["docs"], "outcomes": g["outcomes"], "routes": g["routes"],
                          "clusters": g["clusters"], "movement": g["movement"], "shas16": g["shas16"]}
                   for name, g in agg["groups"].items()},
        "family_residual": residual,
    }, indent=1, sort_keys=False)
    report = render_report(records, meta, agg, residual, estimates)

    known = (str(args.run), str(args.run).replace("\\", "/"), str(args.data_dir), str(meta.get("run_id") or ""),
             args.run.name, args.run.parent.name)
    findings = (privacy_findings(csv_text, known) + privacy_findings(clusters_json, known)
                + privacy_findings(report, known))
    if findings:
        print(f"REFUSED: {len(findings)} digit-run / money-shaped tokens in the outputs: "
              + ", ".join(sorted(set(findings))[:10]))
        return 3

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "per_sha.csv").write_text(csv_text, encoding="utf-8")
    (args.out_dir / "clusters.json").write_text(clusters_json, encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")

    print(f"population {meta['population']} of {meta['shas_total']} shas; "
          f"groups {len(agg['groups'])}; fine clusters {len(set(r['cluster'] for r in records))}")
    for name, g in list(agg["groups"].items())[:40]:
        print(f"  {g['docs']:4d}  {name}")
    print(f"wrote {args.out_dir / 'per_sha.csv'}, {args.out_dir / 'clusters.json'}, {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
