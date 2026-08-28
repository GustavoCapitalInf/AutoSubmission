"""recon_b7_check.py — acceptance checker for the RECONSTRUCTED batch-7 baseline.

    python -m tools.recon_b7_check --run <run_dir> [--report <path.md>]

The historical run of record (`discovery_reports/…-356a4269/`) is gone. The
baseline is regenerated at the batch-7 tree (`302f8f2`) over the frozen
corpus, and THIS file decides whether that regeneration reproduces the batch-7
state well enough to serve as the comparison base for train 8. Its acceptance
logic was written and committed BEFORE the regenerated run was observed
(BATCH8_TRANSITION, "Recovery on the Linux host"); any later change to the
criteria below needs an explicit recorded reason in that document.

Three gates, every expectation quoted from a committed record:

G3  aggregate — the run, counted exactly as `discovery.compare` counts a run
    (`discovery.evidence.load_run`: telemetry keyed by content sha, duplicates
    collapsed), must reproduce the run of record: 3,380 distinct shas,
    validated 2,469 / review 17 / withheld 72 / failed 809 / deferred 13
    (PROJECT_STATUS 2026-08-22; every batch-8 handoff's "run of record" line);
    3,506 rows, dedup 124 within-archive / 82 pinned-corpus copies
    (TRANCHE1_REPORT, re-measured on disk 2026-08-27); the frozen inventory
    (discovery/inventory.py); mode `scanned`; `registration_count` 75 on every
    dispatched record (the registry at 302f8f2).
G4  per-document — every durable per-sha outcome record must be reproduced:
    O1 the pinned-corpus copies in the discovery set (corpus_gate's pinned
       verdicts, keyed through the audit CSV's sha);
    O2 the census's 598 digital no-parser documents (CENSUS_BATCH8_DIGITAL,
       run `7a317445`; fenced sha lists only, prose mentions excluded) →
       `failed`;
    O3 the census's withheld cohort table → `withheld`;
    O4 tools/welch_population.txt (17, all `failed` at base per W3 §WELCH);
    O5 RBC_CURRENCY_MEASUREMENT's 147 discovery rows with their run-of-record
       outcome (RBC moved in neither batch 6 nor batch 7 — both trains' mover
       lists are named by family in PROJECT_STATUS and contain no RBC).
    O2/O3 predate batch 7, so a document whose outcome moved UP the ladder is
    EXPLAINED iff its sha appears inside one of the ten batch-7 W3 sections
    (the only cells merged between `7a317445` and `356a4269`), capped at the
    24 improvements the batch-7 comparison recorded. Everything else is a
    discrepancy.
G5  drift attribution — a discrepancy on a document whose intake rung was
    native text is a STOP (an unexplained native-text difference cannot be
    toolchain drift: the same PyMuPDF build reads the same bytes). A
    discrepancy on a document that went through the local Tesseract rung (or
    any non-native rung) is reported SEPARATELY, named by sha, as a
    toolchain-drift candidate (Windows Tesseract 5.5.0 → Linux 5.5.3); it is
    never counted as batch-8 movement unless equivalence is independently
    established. Aggregate deltas are decomposed the same way.

Verdict: ACCEPT (exit 0) only when G3 holds exactly and G4 has no
discrepancy of any kind. REJECT otherwise — exit 2 when every discrepancy sits
on a non-native document and the aggregate deltas are bounded by the
non-native population (drift candidate; Gustavo's call), exit 1 for anything
else (a native STOP, an oracle document absent from the run, or an aggregate
delta the non-native population cannot bound).

Redacted census shas (`[… redacted]` inside the hex) are matched by their
surviving prefix and suffix against the run's shas and used only when exactly
one sha matches; unmatched or ambiguous tokens are reported, not scored.
Output names documents by the first 16 hex characters of their sha, never by
path.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W3_PATH = ROOT / "docs" / "moneythumb-replacement" / "W3_TRACKA_LOG.md"
CENSUS_PATH = ROOT / "docs" / "moneythumb-replacement" / "CENSUS_BATCH8_DIGITAL.md"
RBC_PATH = ROOT / "docs" / "moneythumb-replacement" / "RBC_CURRENCY_MEASUREMENT.md"
WELCH_PATH = ROOT / "tools" / "welch_population.txt"
BALANCE_CSV_PATH = ROOT / "docs" / "balance-metrics-audit-results.csv"

LADDER = ("failed", "withheld", "review", "validated")

#: The run of record, quoted. FROZEN before the regenerated run was observed.
RECORD = {
    "distinct_shas": 3380,
    "outcome": {"validated": 2469, "review": 17, "withheld": 72, "failed": 809, "deferred": 13},
    "rows": 3506,
    "dedup": {"duplicate": 124, "pinned_corpus_duplicate": 82},
    "inventory": {"files": 3768, "pdfs": 3615, "total_bytes": 996_080_803,
                  "pinned": 109, "discovery": 3506},
    "mode": "scanned",
    "registration_count": 75,
    "explained_improvements_cap": 24,
}
#: Reported beside G3, never gating: recorded 2026-08-07 (TRANCHE1_REPORT,
#: DISCOVERY_COMBINED_REPORT), not by the batch-7 run itself.
INFORMATIONAL = {"invalid_pdf": 17}

#: The ten cells merged between `7a317445` and `356a4269` (PROJECT_STATUS,
#: batch 7). A census document that improved must be named in one of them.
BATCH7_SECTIONS = (
    "ATBMEASURE", "PRIVACY3", "DECLINESE", "DECLINESG", "SCANFINISH",
    "CURRSRC", "DESCATTRIB", "REPAIRDOC", "TANGERINE", "DECLINESF",
)

NATIVE_PATHS = frozenset({"native"})

_HEX64 = re.compile(r"^[0-9A-F]{64}$")
_TOKEN = re.compile(r"(?<![0-9A-Za-z])((?:[0-9A-F]+|\[[^\]]+\])+)(?![0-9A-Za-z])")


# ----------------------------------------------------------------------
# oracle extraction
# ----------------------------------------------------------------------

def _hex_of(token: str) -> str:
    return re.sub(r"\[[^\]]+\]", "", token)


def _is_sha_token(token: str) -> bool:
    hexpart = _hex_of(token)
    if "[" in token:
        return len(hexpart) >= 20
    return len(hexpart) == 64


def census_failed_tokens(text: str) -> list[tuple[str, str]]:
    """(section, token) for every sha token inside a fenced block of the census.

    Fenced blocks are the machine-written sha lists; prose mentions (a
    neighbour named in a risk note, a misfile) are deliberately excluded.
    The withheld cohort's table is a different shape and is read separately.
    """
    out: list[tuple[str, str]] = []
    section = "(top)"
    fenced = False
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            fenced = False
            if _is_withheld_header(section):
                break        # everything after it is the withheld cohort's report
            continue
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            continue
        for match in _TOKEN.finditer(line):
            token = match.group(1)
            if _is_sha_token(token):
                out.append((section, token))
    return out


def _is_withheld_header(section: str) -> bool:
    return section.lower().startswith("the withheld")


def census_withheld_tokens(text: str) -> list[str]:
    """The sha16 column of the withheld cohort's per-document table.

    The cohort report is appended to the census under `## The withheld 61 …`
    and keeps its own `## Group table` / `## Per-document list` sub-headers, so
    once that header is seen every later table row is the cohort's.
    """
    out: list[str] = []
    in_report = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_report = in_report or _is_withheld_header(line[3:].strip())
            continue
        if not in_report:
            continue
        match = re.match(r"^\|\s*([0-9A-F]{16})\s*\|", line)
        if match:
            out.append(match.group(1))
    return out


def rbc_expectations(text: str) -> dict[str, str]:
    """sha -> outcome from the `Discovery (147)` table of the RBC measurement."""
    out: dict[str, str] = {}
    active = False
    for line in text.splitlines():
        if line.startswith("**Discovery (") and "run-of-record outcome" in line:
            active = True
            continue
        if not active:
            continue
        if line.startswith("**") or line.startswith("## "):
            if out:
                break
            continue
        match = re.match(
            r"^\|\s*\d+\s*\|\s*`([0-9A-F]{64})`\s*\|[^|]*\|[^|]*\|\s*(validated|review|withheld|failed)\s*\|",
            line,
        )
        if match:
            out[match.group(1)] = match.group(2)
    return out


def welch_population(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if _HEX64.match(line.strip())]


def pinned_expectations(
    balance_rows: list[dict[str, str]],
    pinned_outcomes: dict[str, str],
    pinned_refusals: dict[str, str],
) -> dict[str, str]:
    """sha -> the outcome class a pinned document's bytes must publish.

    `pinned_outcomes` is corpus_gate.PINNED_OUTCOMES reduced to its outcome
    string; a path in `pinned_refusals` publishes nothing (discovery records
    it as `failed`); every other pinned path publishes `validated`.
    """
    out: dict[str, str] = {}
    for row in balance_rows:
        path, sha = row["path"], row["sha256"].upper()
        if path in pinned_refusals:
            out[sha] = "failed"
        elif path in pinned_outcomes:
            out[sha] = pinned_outcomes[path]
        else:
            out[sha] = "validated"
    return out


def batch7_named_shas(w3_text: str) -> set[str]:
    """Every sha8 prefix mentioned inside the ten batch-7 W3 sections."""
    named: set[str] = set()
    active = False
    for line in w3_text.splitlines():
        if line.startswith("# §"):
            name = line[3:].split()[0].split("—")[0].strip()
            active = name in BATCH7_SECTIONS
            continue
        if not active:
            continue
        for match in re.finditer(r"(?<![0-9A-Za-z])[0-9A-F]{8,64}(?![0-9A-Za-z])", line):
            named.add(match.group(0)[:8])
    return named


# ----------------------------------------------------------------------
# resolving tokens against the run
# ----------------------------------------------------------------------

@dataclass
class Resolution:
    sha: str | None
    status: str  # exact | prefix | redacted | unmatched | ambiguous


def resolve(token: str, run_shas: list[str]) -> Resolution:
    token = token.strip().upper()
    if _HEX64.match(token):
        return Resolution(token, "exact") if token in set(run_shas) else Resolution(None, "unmatched")
    if "[" in token:
        parts = re.split(r"\[[^\]]+\]", token)
        prefix, suffix = parts[0], parts[-1]
        hits = [s for s in run_shas if s.startswith(prefix) and s.endswith(suffix)]
        kind = "redacted"
    else:
        hits = [s for s in run_shas if s.startswith(token)]
        kind = "prefix"
    if len(hits) == 1:
        return Resolution(hits[0], kind)
    return Resolution(None, "unmatched" if not hits else "ambiguous")


# ----------------------------------------------------------------------
# the run
# ----------------------------------------------------------------------

@dataclass
class RunView:
    outcome: dict[str, str]                 # sha -> outcome class (compare's view)
    source_path: dict[str, str]             # sha -> intake rung (rows.csv)
    parser_id: dict[str, str]               # sha -> parser id or ""
    summary: dict
    registration_counts: Counter
    rows: int


def load_run_view(run_dir: Path) -> RunView:
    from discovery.evidence import load_run  # the same counting as discovery.compare

    run = load_run(run_dir)
    outcome = {sha: doc.outcome_class for sha, doc in run.documents.items()}
    source_path: dict[str, str] = {}
    parser_id: dict[str, str] = {}
    rows = 0
    with (run_dir / "rows.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            sha = row["content_sha256"].upper()
            source_path.setdefault(sha, row.get("source_path") or "none")
            parser_id.setdefault(sha, row.get("parser_id") or "")
    counts: Counter = Counter()
    for line in (run_dir / "telemetry.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        dispatch = record.get("dispatch") or {}
        # Only DISPATCHED records carry a meaningful registry size: a document
        # whose dispatch never ran (`invalid_pdf`, `deferred_visual_ocr`)
        # records `source: unavailable` and a count of 0. The frozen rule reads
        # "75 on every dispatched record"; the first implementation counted the
        # undispatched records too (31 = 17 invalid + 14 deferred on the
        # regenerated run) and tripped on them. Corrected 2026-08-28 with
        # Gustavo's OK; G3's outcome checks, G4 and G5 are untouched.
        if "registration_count" in dispatch and dispatch.get("source") != "unavailable":
            counts[dispatch["registration_count"]] += 1
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    return RunView(outcome, source_path, parser_id, summary, counts, rows)


# ----------------------------------------------------------------------
# the gates
# ----------------------------------------------------------------------

@dataclass
class Discrepancy:
    sha: str
    oracle: str
    expected: str
    actual: str
    source_path: str
    parser_id: str
    kind: str  # STOP | DRIFT | ABSENT

    @property
    def sha16(self) -> str:
        return self.sha[:16]


@dataclass
class Report:
    g3: list[tuple[str, object, object, bool]] = field(default_factory=list)
    informational: list[tuple[str, object, object]] = field(default_factory=list)
    coverage: dict[str, int] = field(default_factory=dict)
    matched: Counter = field(default_factory=Counter)
    explained: list[tuple[str, str, str, str]] = field(default_factory=list)  # sha, oracle, expected, actual
    discrepancies: list[Discrepancy] = field(default_factory=list)
    unresolved: Counter = field(default_factory=Counter)
    non_native_total: int = 0
    non_native_in_oracle: int = 0
    non_native_by_path: Counter = field(default_factory=Counter)

    @property
    def g3_ok(self) -> bool:
        return all(ok for _, _, _, ok in self.g3)

    @property
    def stops(self) -> list[Discrepancy]:
        return [d for d in self.discrepancies if d.kind == "STOP"]

    @property
    def drift(self) -> list[Discrepancy]:
        return [d for d in self.discrepancies if d.kind == "DRIFT"]

    @property
    def absent(self) -> list[Discrepancy]:
        return [d for d in self.discrepancies if d.kind == "ABSENT"]

    def aggregate_deltas(self) -> dict[str, int]:
        return {name: int(actual) - int(expected)
                for name, expected, actual, ok in self.g3
                if name.startswith("outcome.") and not ok}

    def verdict(self) -> tuple[str, int, str]:
        if self.g3_ok and not self.discrepancies:
            return "ACCEPT", 0, "G3 exact; G4 no discrepancy"
        reasons = []
        if self.stops:
            reasons.append(f"STOP: {len(self.stops)} unexplained native-text discrepancies")
        if self.absent:
            reasons.append(f"{len(self.absent)} oracle documents absent from the run")
        deltas = self.aggregate_deltas()
        bounded = sum(abs(v) for v in deltas.values()) <= 2 * max(self.non_native_total, 0)
        if deltas:
            reasons.append("aggregate deltas " + ", ".join(f"{k}{v:+d}" for k, v in deltas.items())
                           + (" (bounded by the non-native population)" if bounded else
                              " (NOT bounded by the non-native population)"))
        if self.g3 and not self.g3_ok and not deltas:
            reasons.append("non-outcome aggregate mismatch")
        if self.drift:
            reasons.append(f"{len(self.drift)} drift candidates on non-native documents")
        drift_only = (not self.stops and not self.absent and bounded
                      and all(name.startswith("outcome.") or name == "distinct_shas" or ok
                              for name, _, _, ok in self.g3))
        return ("REJECT-DRIFT-CANDIDATE" if drift_only else "REJECT",
                2 if drift_only else 1, "; ".join(reasons))


def _rank(outcome: str) -> int | None:
    return LADDER.index(outcome) if outcome in LADDER else None


def check(
    run: RunView,
    *,
    pinned: dict[str, str],
    census_failed: list[tuple[str, str]],
    census_withheld: list[str],
    welch: list[str],
    rbc: dict[str, str],
    batch7_named: set[str],
) -> Report:
    report = Report()
    # ---- G3
    counts = Counter(run.outcome.values())
    report.g3.append(("distinct_shas", RECORD["distinct_shas"], len(run.outcome),
                      len(run.outcome) == RECORD["distinct_shas"]))
    for cls, expected in RECORD["outcome"].items():
        report.g3.append((f"outcome.{cls}", expected, counts.get(cls, 0), counts.get(cls, 0) == expected))
    report.g3.append(("rows", RECORD["rows"], run.rows, run.rows == RECORD["rows"]))
    dedup = run.summary.get("dedup") or {}
    for key, expected in RECORD["dedup"].items():
        report.g3.append((f"dedup.{key}", expected, dedup.get(key, 0), dedup.get(key, 0) == expected))
    inventory = run.summary.get("inventory") or {}
    for key, expected in RECORD["inventory"].items():
        report.g3.append((f"inventory.{key}", expected, inventory.get(key), inventory.get(key) == expected))
    report.g3.append(("mode", RECORD["mode"], run.summary.get("mode"), run.summary.get("mode") == RECORD["mode"]))
    regs = dict(run.registration_counts)
    report.g3.append(("registration_count", {RECORD["registration_count"]: "all"}, regs,
                      set(regs) == {RECORD["registration_count"]}))
    reasons = run.summary.get("reasons") or {}
    for key, expected in INFORMATIONAL.items():
        report.informational.append((f"reasons.{key}", expected, reasons.get(key, 0)))
    for key, value in (run.summary.get("deferred_reasons") or {}).items():
        report.informational.append((f"deferred_reasons.{key}", "-", value))

    # ---- non-native population
    for sha, path in run.source_path.items():
        if path not in NATIVE_PATHS:
            report.non_native_total += 1
            report.non_native_by_path[path] += 1

    # ---- G4
    run_shas = sorted(run.outcome)
    oracle: dict[str, tuple[str, str]] = {}   # sha -> (oracle name, expected)

    def add(name: str, sha: str, expected: str) -> None:
        if sha in oracle and oracle[sha][1] != expected:
            # conflicting durable records: keep the first, report the conflict
            report.unresolved[f"{name}:conflict"] += 1
            return
        oracle.setdefault(sha, (name, expected))

    for sha, expected in pinned.items():
        if sha in run.outcome:
            add("O1-pinned-copy", sha, expected)
    for section, token in census_failed:
        res = resolve(token, run_shas)
        if res.sha is None:
            report.unresolved[f"O2-census:{res.status}"] += 1
            continue
        add("O2-census-failed", res.sha, "failed")
    for token in census_withheld:
        res = resolve(token, run_shas)
        if res.sha is None:
            report.unresolved[f"O3-withheld:{res.status}"] += 1
            continue
        add("O3-census-withheld", res.sha, "withheld")
    for sha in welch:
        add("O4-welch", sha, "failed")
    for sha, expected in rbc.items():
        add("O5-rbc", sha, expected)

    explained_count = 0
    for sha, (name, expected) in sorted(oracle.items()):
        actual = run.outcome.get(sha)
        path = run.source_path.get(sha, "none")
        parser = run.parser_id.get(sha, "")
        if actual is None:
            report.discrepancies.append(Discrepancy(sha, name, expected, "(absent)", path, parser, "ABSENT"))
            continue
        report.coverage[name] = report.coverage.get(name, 0) + 1
        if path not in NATIVE_PATHS:
            report.non_native_in_oracle += 1
        if actual == expected:
            report.matched[name] += 1
            continue
        up = (_rank(actual) is not None and _rank(expected) is not None
              and _rank(actual) > _rank(expected))
        if (name in ("O2-census-failed", "O3-census-withheld") and up
                and sha[:8] in batch7_named
                and explained_count < RECORD["explained_improvements_cap"]):
            explained_count += 1
            report.explained.append((sha, name, expected, actual))
            continue
        kind = "STOP" if path in NATIVE_PATHS else "DRIFT"
        report.discrepancies.append(Discrepancy(sha, name, expected, actual, path, parser, kind))
    return report


# ----------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------

def render(report: Report, *, run_dir: str) -> str:
    verdict, code, why = report.verdict()
    lines = [f"# recon_b7_check — {run_dir}", "",
             f"**VERDICT: {verdict}** (exit {code}) — {why}", "",
             "## G3 aggregate (record → regenerated)", "",
             "| check | record | regenerated | ok |", "|---|---:|---:|:-:|"]
    for name, expected, actual, ok in report.g3:
        lines.append(f"| {name} | {expected} | {actual} | {'✓' if ok else '✗'} |")
    lines += ["", "informational (not gating): " + "; ".join(
        f"{n} record {e} / regenerated {a}" for n, e, a in report.informational), ""]
    lines += ["## G4 per-document", "",
              "| oracle | covered | matched | explained (batch-7 named) | discrepant |", "|---|---:|---:|---:|---:|"]
    names = sorted(set(report.coverage) | {d.oracle for d in report.discrepancies})
    for name in names:
        expl = sum(1 for _, n, _, _ in report.explained if n == name)
        disc = sum(1 for d in report.discrepancies if d.oracle == name)
        lines.append(f"| {name} | {report.coverage.get(name, 0)} | {report.matched.get(name, 0)} | {expl} | {disc} |")
    total_cov = sum(report.coverage.values())
    lines += ["", f"oracle coverage: {total_cov} distinct shas of {len(report.g3) and report.g3[0][2]} in the run; "
              f"unresolved tokens: {dict(report.unresolved) or 'none'}", ""]
    if report.explained:
        lines += ["### explained improvements (named in a batch-7 section)", "", "| sha16 | oracle | expected | regenerated |", "|---|---|---|---|"]
        lines += [f"| {s[:16]} | {n} | {e} | {a} |" for s, n, e, a in report.explained]
        lines.append("")
    lines += ["### discrepancies", ""]
    if not report.discrepancies:
        lines.append("none")
    else:
        lines += ["| kind | sha16 | oracle | expected | regenerated | intake rung | parser |", "|---|---|---|---|---|---|---|"]
        for d in sorted(report.discrepancies, key=lambda d: (d.kind, d.sha)):
            lines.append(f"| {d.kind} | {d.sha16} | {d.oracle} | {d.expected} | {d.actual} | {d.source_path} | {d.parser_id or '-'} |")
    lines += ["", "## G5 toolchain-drift attribution", "",
              f"non-native intake population in the run: {report.non_native_total} "
              f"({dict(report.non_native_by_path) or '-'}); of which covered by an oracle: {report.non_native_in_oracle}", ""]
    deltas = report.aggregate_deltas()
    if deltas:
        lines.append("aggregate deltas: " + ", ".join(f"{k} {v:+d}" for k, v in deltas.items()))
    lines.append(f"STOP (native, unexplained): {len(report.stops)} · DRIFT candidates (non-native, named above): "
                 f"{len(report.drift)} · ABSENT: {len(report.absent)}")
    if report.drift:
        lines += ["", "drift candidates by sha16: " + ", ".join(sorted(d.sha16 for d in report.drift))]
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, type=Path, help="a discovery run directory")
    parser.add_argument("--report", type=Path, default=None, help="write the markdown report here")
    parser.add_argument("--w3", type=Path, default=W3_PATH)
    parser.add_argument("--census", type=Path, default=CENSUS_PATH)
    parser.add_argument("--rbc", type=Path, default=RBC_PATH)
    parser.add_argument("--welch", type=Path, default=WELCH_PATH)
    parser.add_argument("--balance-csv", type=Path, default=BALANCE_CSV_PATH)
    args = parser.parse_args(argv)

    import corpus_gate

    pinned = pinned_expectations(
        corpus_gate.read_csv(args.balance_csv),
        {path: verdict.outcome for path, verdict in corpus_gate.PINNED_OUTCOMES.items()},
        dict(corpus_gate.PINNED_REFUSALS),
    )
    census_text = args.census.read_text(encoding="utf-8")
    report = check(
        load_run_view(args.run),
        pinned=pinned,
        census_failed=census_failed_tokens(census_text),
        census_withheld=census_withheld_tokens(census_text),
        welch=welch_population(args.welch.read_text(encoding="utf-8")),
        rbc=rbc_expectations(args.rbc.read_text(encoding="utf-8")),
        batch7_named=batch7_named_shas(args.w3.read_text(encoding="utf-8")),
    )
    text = render(report, run_dir=str(args.run))
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text)
    return report.verdict()[1]


if __name__ == "__main__":
    sys.exit(main())
