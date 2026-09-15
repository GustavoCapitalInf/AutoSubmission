"""tools/paddle_wave.py — the Phase 2.3 broad-evidence wave runner (cell W,
`docs/agent-handoffs/P23-WAVE.md`).

    python -m tools.paddle_wave populations --run <run-of-record dir> --out <dir>
    python -m tools.paddle_wave preflight  --population <file> --data-dir <dir> --config paddle-v5-prod
    python -m tools.paddle_wave run        --population <file> --data-dir <dir> --config paddle-v5-prod \
                                           --out <run dir> --root <archive root>
    python -m tools.paddle_wave report     --data-dir <dir> --config paddle-v5-prod

A THIN, RESUMABLE orchestrator around the Phase 2.2 research mode. It owns
three things and nothing else: which documents are studied (`populations`),
that a study may start at all (`preflight` and the lifecycle), and what the
study produced (`report`). It does not read a page, does not adapt a result,
does not decide an outcome and does not import the Paddle rung — an AST test
in `tests/test_paddle_wave.py` pins that last one, because "we simply would
not" is not enforcement. Every page this tool causes to be read is read by
`python -m discovery --research-paddle`, through the same router, the same
extraction ladder and the same cache the Phase 2.2 cells built and reviewed.

What makes it resumable: the wave's progress lives in a STATE FILE under the
research data directory, keyed by content sha, written after every chunk. An
agent that dies mid-wave loses nothing but the chunk in flight, and even that
chunk's finished documents come back as cache hits under the same partition
key. A sha that produced evidence is complete; a sha that was REFUSED is
recorded with its reason and stays pending, because "we tried and it refused"
is a counted finding, not a closed one.

Three rules this file exists to enforce rather than describe:

* **Both opt-in literals, in THIS process's environment, or nothing happens.**
  The research mode already refuses at its own door; `preflight` refuses first
  and names the missing one, so an operator learns it before a corpus is
  enumerated rather than after. The literals are set per command by the
  operator and appear in no tracked file, no `.env` and no log.
* **The control sample first (D3).** A run of the unresolved corpus refuses to
  start while the control sample still has an unattempted document under the
  same configuration; the slice refuses while either is incomplete. The rule is
  read off the state files, not off an operator's memory of what they ran.
* **Nothing leaks.** Connection details reach this tool only through
  `ocr.paddle_config.load_paddle_settings()` and leave it only through
  `tools.paddle_vast.mask_text`. No log line, report key or state field carries
  a host, a port, a user, a token, a document's contents, or a sha beside a
  verdict. There is no cost, rate, price, usd or billing key anywhere in this
  file: cost accounting is out of scope by Gustavo's ruling and the report's
  keys are grepped for those tokens by test.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

# Imported for its ONE side effect: `ocr/config.py` is this tree's single
# dotenv entry point (`load_dotenv()` at import, `override=False`), and the
# connection contract lives in the gitignored `.env` and nowhere else. Without
# it this tool reads whatever the shell happens to carry — which is the same in
# the main checkout and EMPTY in a worktree, where `find_dotenv` still resolves
# the one `.env` but nothing had asked it to. `override=False` means an
# explicit per-command variable (the two opt-in literals) still wins, which is
# the property that matters: the environment authorizes, the file configures.
import ocr.config  # noqa: F401
from ocr.paddle_config import (
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
    PADDLE_RASTER_DPI,
    PADDLE_REMOTE_OPT_IN_ENV,
    PADDLE_REMOTE_OPT_IN_LITERAL,
    REFUSAL_REASONS,
)

ROOT = Path(__file__).resolve().parents[1]

__all__ = [
    "CONFIGURATIONS",
    "POPULATION_ORDER",
    "PRODUCTION_CONFIG",
    "STATE_VERSION",
    "RetentionAttestation",
    "WaveRefused",
    "WaveState",
    "attest_retention",
    "derive_populations",
    "main",
    "missing_opt_in_literals",
    "population_digests",
    "recorded_evidence_for",
    "retain_rasters_for",
    "wave_report",
]


class WaveRefused(RuntimeError):
    """Every refusal this tool makes. Carries a reason a human can act on and
    never a connection value, a document's contents or a sha with a verdict."""


class WaveExportFailed(WaveRefused):
    def __init__(self, processed: int):
        super().__init__("wave_export_failed_offline_retry_required")
        self.processed = processed


# ---------------------------------------------------------------------------
# Configurations. Cell V owns the named configuration BLOCKS in
# `ocr/paddle_config.py`; this cell runs the production block only, and names
# the others so an operator who asks for one is told where they live rather
# than silently given the production pins under another partition's name.
# ---------------------------------------------------------------------------

PRODUCTION_CONFIG = "paddle-v5-prod"

#: `name -> (research partition id, what it is)`. The partition id is OCR-key
#: material and must match `RESEARCH_PARTITION_PATTERN`, which admits no `/`.
#: RULED (Ocean, 2026-09-11, after the umbrella card's `research/paddle-v5-prod`
#: was found to be prose the shape cannot carry): the research partition id IS
#: the configuration block's name — `paddle-v5-prod`, not a `research-` prefixed
#: variant of it. The prefix would be shape-legal and still wrong: what makes a
#: partition research is the id being non-empty at all (`telemetry/run_of_record.py`
#: refuses any run that carries one), never the spelling, and a second spelling
#: for one configuration is a second name for one partition of evidence.
CONFIGURATIONS: dict[str, dict[str, str]] = {
    PRODUCTION_CONFIG: {
        "partition": PRODUCTION_CONFIG,
        "what": "the Phase 2.1 production pins, unchanged; the configuration that counts",
    },
}

#: Configurations this cell knows the NAME of and deliberately does not run.
#: Naming them is the point: an operator who asks for one gets a refusal that
#: says who owns it, not "unknown configuration".
DEFERRED_CONFIGURATIONS: dict[str, str] = {
    "paddle-v5-orient": "cell V (P23-CONFIG): the orientation-classifier A/B",
    "paddle-v6": "cell V (P23-CONFIG): the PP-OCRv6 A/B",
}

#: D3. A population may not start while an EARLIER one still has a document
#: nothing has attempted under the same configuration. The order is a property
#: of the evidence — the agreement baseline and the false-accept instrument are
#: calibrated on the control sample before an unresolved document is read — so
#: it is enforced here rather than left to an operator's running order.
POPULATION_ORDER: tuple[str, ...] = ("CTRL", "U755", "SLICE")

STATE_VERSION = 2
PRIVATE_RUN_STORAGE = "research-private-v1"
EXPORT_SCHEMA_VERSION = 1
EXPORT_KIND = "paddle-wave-technical"
EXPORT_ROWS = "wave_technical_rows.csv"
EXPORT_MARKER = "wave_export.json"
TECHNICAL_FIELDS = (
    "content_sha256", "evidence_sha256", "page_count", "stage_evidence",
    "source_path", "cache_paddle", "wave_refusal_reason", "bytes_up", "bytes_down",
    "inference_ms", "vram_mb", "peak_rss_mb", "elapsed_ms", "research_partition",
)
# These are software reasons, including the legacy state's coarse OCR reason.
# Exception class names are individually named, never arbitrary messages/types.
WAVE_REFUSAL_REASONS = frozenset(REFUSAL_REASONS) | frozenset({
    "invalid_pdf", "ocr_failed", "unrecorded", "no_row_produced", "paddle_not_attempted",
    "paddle_evidence_missing", "paddle_rung_failed_unnamed", "paddle_refusal_row_unavailable",
    "PaddleRefused", "PaddleTransportError", "PaddleConfigError", "PaddleAdapterError",
    "RuntimeError", "ValueError", "TypeError", "OSError",
})

#: The outcome vocabulary of one document in the state file. Closed, and
#: enforced where it is written: a third state would let "we do not know" hide
#: inside one of these two.
OUTCOME_EVIDENCE = "evidence"
OUTCOME_REFUSED = "refused"

DEFAULT_CHUNK_SIZE = 50


# ---------------------------------------------------------------------------
# The doors
# ---------------------------------------------------------------------------

def missing_opt_in_literals(environ: Mapping[str, str] | None = None) -> list[str]:
    """The NAMES (never the values) of the opt-in variables whose exact
    authorized literal is absent from `environ` (default the real process
    environment).

    Both are required and each is checked on its own, so a refusal names the
    one that is missing: an operator who set one and forgot the other must be
    told which. The literals themselves are never printed — a refusal message
    is not the place to publish the token that lifts it.
    """
    source = os.environ if environ is None else environ
    return [
        name
        for name, literal in (
            (PADDLE_REMOTE_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_LITERAL),
            (PADDLE_CUSTOMER_DATA_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL),
        )
        if source.get(name) != literal
    ]


def require_opt_in(environ: Mapping[str, str] | None = None) -> None:
    missing = missing_opt_in_literals(environ)
    if missing:
        raise WaveRefused(
            "the wave cannot start: remote-paid PaddleOCR on customer documents is "
            "EXPLICITLY opted into and never defaulted; this process's environment is "
            "missing the exact authorized value of " + " and ".join(missing)
        )


def resolve_configuration(name: str) -> dict[str, str]:
    if name in CONFIGURATIONS:
        return CONFIGURATIONS[name]
    if name in DEFERRED_CONFIGURATIONS:
        raise WaveRefused(
            f"configuration {name!r} is not this cell's to run: it belongs to "
            f"{DEFERRED_CONFIGURATIONS[name]}. This cell runs the production block only."
        )
    raise WaveRefused(
        f"unknown configuration {name!r}; known here: {', '.join(sorted(CONFIGURATIONS))}"
    )


def refuse_a_production_data_dir(data_dir: Path) -> None:
    """T's door, reused rather than re-implemented. One definition of "a
    research run writes to its own directory" for the whole tree."""
    from discovery.runner import refuse_production_data_dir

    try:
        refuse_production_data_dir(data_dir)
    except ValueError as exc:
        raise WaveRefused(str(exc)) from exc


def read_population_file(path: Path) -> frozenset[str]:
    """T's reader, reused: one 64-hex content sha per line, `#` comments
    allowed, a malformed line refuses the whole file."""
    from discovery.runner import read_population

    try:
        return read_population(path)
    except ValueError as exc:
        raise WaveRefused(str(exc)) from exc


def population_digests(path: Path) -> dict[str, Any]:
    """Two digests, because they answer two questions. `file_sha256` is the
    bytes on disk — what a later reader reproduces to prove they hold the same
    file. `set_sha256` is the canonical digest of the SET the file names
    (sorted, upper-cased, one per line), which is stable across a comment
    edit and is what actually identifies the population studied."""
    raw = Path(path).read_bytes()
    shas = sorted(read_population_file(Path(path)))
    canonical = "\n".join(shas) + "\n"
    return {
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "set_sha256": hashlib.sha256(canonical.encode("ascii")).hexdigest(),
        "documents": len(shas),
    }


def holdout_sha16s() -> frozenset[str]:
    """The repository holdout digest's sha16 block — the ONE holdout artefact
    runtime code may read, through T's reader."""
    from discovery.cli import DEFAULT_HOLDOUT_DIGEST
    from discovery.runner import holdout_sha16s_from_digest

    try:
        return holdout_sha16s_from_digest(DEFAULT_HOLDOUT_DIGEST)
    except ValueError as exc:
        raise WaveRefused(str(exc)) from exc


def refuse_holdout_members(shas: Iterable[str], *, held: frozenset[str] | None = None) -> None:
    """A population that names a held-out document is refused, by COUNT. The
    shas are never printed: naming them would put holdout identities in an
    operator's console, which is most of what an unseen holdout protects."""
    held = holdout_sha16s() if held is None else held
    overlap = sum(1 for sha in shas if sha[:16].upper() in held)
    if overlap:
        raise WaveRefused(
            f"{overlap} of this population's documents are in the holdout manifest. An "
            "opened holdout item is no longer unseen; remove them deliberately, or study "
            "a different set."
        )


# ---------------------------------------------------------------------------
# The state file: the whole reason this is resumable
# ---------------------------------------------------------------------------

@dataclass
class DocumentOutcome:
    outcome: str
    reason: str = ""
    pages: int = 0
    chunk: int = -1
    at: str = ""


@dataclass
class WaveState:
    """One (configuration, population) study's progress, by content sha.

    Deliberately small and deliberately boring: an outcome token, a refusal
    reason from the row's own closed vocabulary, a page count, which chunk saw
    it and when. No path, no text, no verdict, no figure that could identify a
    document's contents. It lives under the research data directory, which is
    gitignored and under the archive's retention rule, beside the artifacts it
    describes — so a resume reads the same directory the evidence is in and
    cannot describe a different one.
    """

    version: int = STATE_VERSION
    config: str = ""
    partition: str = ""
    population_name: str = ""
    population_file_sha256: str = ""
    population_set_sha256: str = ""
    documents: dict[str, DocumentOutcome] = field(default_factory=dict)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    sessions: list[dict[str, Any]] = field(default_factory=list)

    # -- persistence ------------------------------------------------------

    @staticmethod
    def path_for(data_dir: Path, partition: str, population_name: str) -> Path:
        return Path(data_dir) / ".wave" / partition / f"{population_name}.json"

    @classmethod
    def load(cls, path: Path) -> "WaveState":
        if not Path(path).exists():
            return cls()
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or type(payload.get("version")) is not int \
                or payload["version"] not in (1, STATE_VERSION):
            raise WaveRefused("wave_state_version_unknown; refusing to resume")
        _validate_storage_chunks(payload.get("chunks", []), payload["version"])
        state = cls(**{key: value for key, value in payload.items() if key != "documents"})
        state.documents = {
            sha: DocumentOutcome(**outcome) for sha, outcome in (payload.get("documents") or {}).items()
        }
        return state

    def save(self, path: Path) -> None:
        """Written whole, every time, through a temporary file in the same
        directory: a wave killed mid-write must find a readable state, not a
        truncated one."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(asdict(self))
        payload["documents"] = {sha: asdict(outcome) for sha, outcome in sorted(self.documents.items())}
        temporary = path.with_suffix(".json.writing")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)

    # -- the two questions the wave asks it --------------------------------

    def record(self, sha: str, outcome: DocumentOutcome) -> None:
        if outcome.outcome not in (OUTCOME_EVIDENCE, OUTCOME_REFUSED):
            raise WaveRefused(
                f"outcome {outcome.outcome!r} is not one of {OUTCOME_EVIDENCE!r} / "
                f"{OUTCOME_REFUSED!r}: a document either produced evidence or was refused "
                "with a reason, and there is no third state for it to hide in"
            )
        self.documents[sha.upper()] = outcome

    def pending(self, population: Iterable[str]) -> list[str]:
        """What a run still has to do: every sha that has not produced
        EVIDENCE.

        A REFUSED sha is pending again, and that is the whole point of the
        distinction (M12). A state that treated a refusal as finished would
        resume PAST a document whose only record is that something went wrong
        — a transport failure, a worker restart, a runtime mismatch — and the
        wave would quietly study a smaller population than the one it named.
        The refusal stays recorded with its reason either way, so nothing is
        lost by retrying it and a permanent refusal simply refuses again.
        """
        done = {
            sha for sha, outcome in self.documents.items() if outcome.outcome == OUTCOME_EVIDENCE
        }
        return sorted(sha.upper() for sha in population if sha.upper() not in done)

    def unattempted(self, population: Iterable[str]) -> list[str]:
        """What nothing has ever tried. The D3 order rule reads THIS, not
        `pending`: a document that was attempted and refused HAS had its
        controlled opportunity, and holding the next population hostage to a
        permanently unreadable one would make the rule unsatisfiable."""
        return sorted(sha.upper() for sha in population if sha.upper() not in self.documents)

    def counts(self) -> dict[str, int]:
        evidence = sum(1 for o in self.documents.values() if o.outcome == OUTCOME_EVIDENCE)
        refused = sum(1 for o in self.documents.values() if o.outcome == OUTCOME_REFUSED)
        return {
            "attempted": len(self.documents),
            "evidence": evidence,
            "refused": refused,
            "pages_evidence": sum(o.pages for o in self.documents.values()
                                  if o.outcome == OUTCOME_EVIDENCE),
            "pages_refused": sum(o.pages for o in self.documents.values()
                                 if o.outcome == OUTCOME_REFUSED),
        }

    def refusals_by_reason(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for outcome in self.documents.values():
            if outcome.outcome == OUTCOME_REFUSED:
                tally[outcome.reason or "unrecorded"] = tally.get(outcome.reason or "unrecorded", 0) + 1
        return dict(sorted(tally.items()))


def refuse_out_of_order(
    population_name: str, *, data_dir: Path, partition: str, populations_dir: Path,
) -> list[str]:
    """D3, case 8. Returns the predecessor names checked (for the log).

    A population outside `POPULATION_ORDER` has no predecessor and no order to
    violate; the named three are ordered absolutely. The check reads the
    predecessor's POPULATION FILE and its STATE FILE and requires every sha in
    the former to appear in the latter — so an operator cannot satisfy it by
    running a one-document control sample, and cannot fail it by having run the
    predecessor under a different configuration (a different partition is a
    different state file, which is the honest answer: that evidence was not
    produced under this configuration).
    """
    if population_name not in POPULATION_ORDER:
        return []
    checked: list[str] = []
    for earlier in POPULATION_ORDER[: POPULATION_ORDER.index(population_name)]:
        earlier_file = Path(populations_dir) / f"{earlier}.shas"
        if not earlier_file.exists():
            raise WaveRefused(
                f"{population_name} may not start: {earlier} must run first (D3) and its "
                f"population file is not in {populations_dir}"
            )
        earlier_population = read_population_file(earlier_file)
        state = WaveState.load(WaveState.path_for(data_dir, partition, earlier))
        outstanding = state.unattempted(earlier_population)
        if outstanding:
            raise WaveRefused(
                f"{population_name} may not start: {earlier} still has {len(outstanding)} of "
                f"{len(earlier_population)} documents that nothing has attempted under "
                f"configuration partition {partition}. The control sample calibrates the "
                "instruments the later populations are read with; it runs first, in full."
            )
        checked.append(earlier)
    return checked


# ---------------------------------------------------------------------------
# populations (card item 5)
# ---------------------------------------------------------------------------

#: Page-count buckets for the control sample's stratification. Boundaries, not
#: magic: a one-page document, a short statement, a normal one, a long one, and
#: everything above. Recorded in the derivation header so the file reproduces.
PAGE_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("p1", 1, 1),
    ("p2-3", 2, 3),
    ("p4-6", 4, 6),
    ("p7-12", 7, 12),
    ("p13+", 13, 10 ** 6),
)

DEFAULT_CTRL_TARGET = 114
DEFAULT_SEED = "P23-WAVE"


def _page_bucket(pages: int) -> str:
    for name, low, high in PAGE_BUCKETS:
        if low <= pages <= high:
            return name
    return PAGE_BUCKETS[-1][0]


def _stratified_sample(
    candidates: Sequence[tuple[str, str]], *, target: int, seed: str,
) -> list[str]:
    """`candidates` is `(stratum key, sha)`; returns `target` shas (or every
    candidate when there are fewer), chosen DETERMINISTICALLY from `seed`.

    The rule is a round robin over strata sorted by size, largest first, each
    stratum's own members ordered by `sha256(seed + sha)`. That gives three
    properties worth having together: every stratum that exists is represented
    before any stratum is sampled twice; the result is a pure function of the
    seed and the candidate set, so the file reproduces byte for byte; and
    nothing about the CONTENT of a document influences which one is drawn,
    which is what keeps a "control sample" from quietly becoming a curated one.
    """
    strata: dict[str, list[str]] = {}
    for key, sha in candidates:
        strata.setdefault(key, []).append(sha.upper())
    ordered_keys = sorted(strata, key=lambda key: (-len(strata[key]), key))
    for key in ordered_keys:
        strata[key].sort(key=lambda sha: hashlib.sha256((seed + sha).encode("ascii")).hexdigest())
    chosen: list[str] = []
    cursor = {key: 0 for key in ordered_keys}
    while len(chosen) < target:
        drew = False
        for key in ordered_keys:
            if len(chosen) >= target:
                break
            index = cursor[key]
            if index < len(strata[key]):
                chosen.append(strata[key][index])
                cursor[key] = index + 1
                drew = True
        if not drew:
            break
    return sorted(chosen)


def _rows_of(run_dir: Path) -> list[dict[str, str]]:
    path = Path(run_dir) / "rows.csv"
    if not path.exists():
        raise WaveRefused(f"no rows.csv under {run_dir}: that is not a discovery run directory")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def derive_populations(
    run_dir: Path, *, seed: str = DEFAULT_SEED, ctrl_target: int = DEFAULT_CTRL_TARGET,
    pinned: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """The three populations, derived from the run of record's own rows.

    * **CTRL** — every document the local Tesseract rung produced the text of
      record for AND the deterministic validator VALIDATED, plus
      native-validated documents stratified by folder family and page-count
      bucket up to `ctrl_target` in total. The Tesseract half is the whole
      scanned control: it is small, and it is the population where a Paddle
      read has a directly comparable predecessor. The native half is what makes
      the sample a control for the ENGINE rather than for the OCR — documents
      Phase 1 handles perfectly, where a disagreement is Paddle's.
    * **U755** — every distinct content sha the run of record did not validate.
      Not "failed": a document with a `review` or `withheld` row is unresolved
      too, and the floor's denominator is the distinct sha, so the population is
      "every sha with no validated row" and its size is the corpus minus the
      floor by construction.
    * **SLICE** — the audited corpus manifest, as far as the research mode can
      reach it. See the note this function returns under `slice_note`.

    Returns `{name: {"shas": [...], "note": "...", "strata": {...}}}` — lists,
    never files; the caller writes them.
    """
    rows = _rows_of(run_dir)
    validated_shas = {
        row["content_sha256"].upper() for row in rows if row["outcome_class"] == "validated"
    }
    all_shas = {row["content_sha256"].upper() for row in rows}

    tesseract_ctrl = sorted({
        row["content_sha256"].upper()
        for row in rows
        if row["outcome_class"] == "validated" and row["source_path"] == "local_tesseract"
    })
    native_candidates: dict[str, tuple[str, str]] = {}
    for row in rows:
        sha = row["content_sha256"].upper()
        if row["outcome_class"] != "validated" or row["source_path"] != "native":
            continue
        if sha in tesseract_ctrl or sha in native_candidates:
            continue
        pages = int(row["page_count"] or 0)
        native_candidates[sha] = (f'{row["folder_label"]}|{_page_bucket(pages)}', sha)
    native_target = max(0, ctrl_target - len(tesseract_ctrl))
    native_ctrl = _stratified_sample(
        sorted(native_candidates.values()), target=native_target, seed=seed,
    )
    ctrl = sorted(set(tesseract_ctrl) | set(native_ctrl))

    unresolved = sorted(all_shas - validated_shas)

    if pinned is None:
        from discovery.inventory import pinned_hashes

        pinned = pinned_hashes()
    pinned_shas = {sha.upper() for sha in pinned.values()}
    reachable = sorted(pinned_shas & all_shas)

    strata: dict[str, int] = {}
    for key, _sha in native_candidates.values():
        strata[key] = strata.get(key, 0) + 1

    return {
        "CTRL": {
            "shas": ctrl,
            "note": (
                f"{len(tesseract_ctrl)} validated documents the local Tesseract rung read, "
                f"plus {len(native_ctrl)} validated native documents drawn deterministically "
                f"from seed {seed!r}, stratified over {len(strata)} folder-family x "
                "page-count strata"
            ),
            "strata": strata,
        },
        "U755": {
            "shas": unresolved,
            "note": (
                f"every distinct content sha of the run of record with no validated row: "
                f"{len(all_shas)} distinct shas minus {len(validated_shas)} validated"
            ),
            "strata": {},
        },
        "SLICE": {
            "shas": reachable,
            "note": (
                f"the audited corpus manifest ({len(pinned_shas)} documents) intersected with "
                f"the run of record's own document set: {len(reachable)} are reachable. The "
                "manifest's documents are the PINNED partition of the archive and the "
                "research mode enumerates the DISCOVERY partition, so only the manifest "
                "documents that also appear in the discovery set (as content duplicates under "
                "their own paths) can be read at all; the rest are named here and left unread "
                "rather than silently dropped"
            ),
            "strata": {"unreachable": len(pinned_shas) - len(reachable)},
        },
    }


def write_population_files(
    populations: Mapping[str, Mapping[str, Any]], out_dir: Path, *, run_dir: Path, seed: str,
) -> dict[str, dict[str, Any]]:
    """Write `<name>.shas` and return each file's digests. The header is
    comments: what the file is, where it came from, and the rule that produced
    it — never a verdict beside a sha, and never a figure from a document."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    digests: dict[str, dict[str, Any]] = {}
    for name in POPULATION_ORDER:
        entry = populations[name]
        lines = [
            f"# {name} — a Phase 2.3 research population (P23-WAVE, cell W)",
            f"# derived from the run of record: {Path(run_dir).name}",
            f"# rule: {entry['note']}",
            f"# seed: {seed}",
            f"# documents: {len(entry['shas'])}",
            "# content shas only; this file names WHICH documents are studied and nothing else",
        ]
        lines.extend(entry["shas"])
        path = out_dir / f"{name}.shas"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        digests[name] = population_digests(path)
    return digests


# ---------------------------------------------------------------------------
# The retention attestation (card item 4, case 12)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetentionAttestation:
    """A CLOSED record: booleans and counts, never a path from the instance.

    `inspected` is the field that makes this an attestation rather than a
    claim. An inspection that did not run leaves it False and `passed` is
    False whatever else is true — which is exactly the mutant M8 describes: a
    version of this that reported `none` because the worker said so, without
    ever looking.
    """

    retention_declared: bool
    inspected: bool
    worker_process_alive: bool
    pidfile_present: bool
    request_artefacts: int
    page_byte_files: int
    unexpected_files: int
    #: Recorded, NOT gated. The instance's `/tmp` is shared with whatever else
    #: the image runs, so a file there is an observation to read, not a verdict
    #: on this worker. The gated fields above are all inside the worker's own
    #: directory, which this pipeline is the only writer of. Counted since the
    #: session began, so a file that was already there is not read as ours.
    temp_image_files: int = 0
    #: How many times the instance was inspected before this record was made.
    #: 1 is the ordinary answer; more means the worker process was still
    #: exiting on the earlier looks, which is a fact about the STOP, not about
    #: retention, and is recorded rather than smoothed away.
    probes: int = 1
    error: str = ""

    @property
    def passed(self) -> bool:
        return (
            self.retention_declared
            and self.inspected
            and not self.worker_process_alive
            and not self.pidfile_present
            and self.request_artefacts == 0
            and self.page_byte_files == 0
            and self.unexpected_files == 0
        )

    def as_record(self) -> dict[str, Any]:
        record = dict(asdict(self))
        record["passed"] = self.passed
        return record


# Match the executable and script argument, not arbitrary text in an argv.
# The inspection shell itself contains the worker filename in its find command;
# grepping ps args therefore counts the inspector as a worker even when idle.
# cmd_start launches the interpreter followed directly by REMOTE_WORKER_PATH.
_WORKER_PROCESS_AWK = (
    '$1 ~ /^python([0-9]+([.][0-9]+)*)?$/ && $3 == "{worker}" '
    '{{n++}} END {{print n+0}}'
)

#: The remote inspection, as ONE `sh` command producing `KEY=<integer>` lines.
#: It counts; it never lists. A name from the instance's filesystem must not
#: reach a log on this machine, and a count answers the question the
#: attestation actually asks.
_ATTESTATION_COMMAND = (
    'D="{directory}"; [ -d "$D" ] && [ -r "$D" ] && [ -x "$D" ] || exit 1; '
    "PROCESSES=$(ps -eo comm=,args= 2>/dev/null) || exit 1; "
    "PROC=$(printf '%s\\n' \"$PROCESSES\" | awk '" + _WORKER_PROCESS_AWK + "') || exit 1; "
    'echo PROC="$PROC"; '
    "echo PIDFILE=$([ -f $D/worker.pid ] && echo 1 || echo 0); "
    'IMAGES=$(find "$D" -type f '
    "\\( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.pdf' -o -name '*.b64' "
    "-o -name '*.npy' \\) -printf x 2>/dev/null) || exit 1; echo IMAGES=${{#IMAGES}}; "
    'REQUESTS=$(find "$D" -type f '
    "\\( -name '*.json' -o -name 'request*' -o -name '*.tmp' -o -name '*.part' \\) "
    "-printf x 2>/dev/null) || exit 1; echo REQUESTS=${{#REQUESTS}}; "
    'OTHER=$(find "$D" -mindepth 1 ! -type d ! -path "$D/paddle_worker.py" '
    '! -path "$D/worker.log" -printf x 2>/dev/null) || exit 1; echo OTHER=${{#OTHER}}; '
    "TMPIMG=$(find /tmp -maxdepth 2 -type f "
    "\\( -name '*.png' -o -name '*.pdf' \\) -newermt '@{since}' "
    "-printf x 2>/dev/null) || exit 1; echo TMPIMG=${{#TMPIMG}}"
)

#: How long the attestation lets the worker process finish DYING before it
#: calls it alive, and how often it looks. Found on the real instance during
#: the CTRL run: the inspection ran ~2 s after `stop` and counted a process
#: that was already exiting (30 minutes later the same probe answered `PROC=0`,
#: with no artefact of any kind under the worker's directory). Waiting is not
#: a weakening — a process still alive after the whole grace period still
#: FAILS the attestation, and the record says how many probes it took.
_ATTESTATION_EXIT_GRACE_S = 30.0
_ATTESTATION_PROBE_INTERVAL_S = 5.0


def _parse_attestation_output(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\s*([A-Z]+)=(\d+)\s*", line)
        if match:
            values[match.group(1)] = int(match.group(2))
    return values


def attest_retention(
    settings: Any, *, runner: Callable[..., Any] | None = None, retention_declared: bool,
    since_epoch: float = 0.0, sleep: Callable[[float], None] = time.sleep,
) -> RetentionAttestation:
    """Inspect the instance AFTER `stop`, over the lifecycle tool's own masked
    SSH command builder.

    `retention_declared` is the worker's `/version` answer, read BEFORE the
    stop (there is nothing to ask afterwards) and handed in, so this function
    does exactly one thing: look. Every failure to look — a transport error, a
    non-zero exit, an unparsable reply, a missing key — leaves `inspected`
    False and the attestation FAILING, because "we could not check" and
    "there was nothing there" are the same silence and only one of them is
    safe.

    `since_epoch` is the moment this session began: `/tmp` is shared with
    whatever else the image runs, so a file there is this session's business
    only if this session could have written it. The CTRL run found the other
    case on the real instance — one synthetic PNG left in `/tmp` by the
    operator's own live test two hours BEFORE the session — and counted it
    beside our own work. Omit it (default 0) and every matching file counts,
    which is the conservative reading for a caller that cannot say when it
    started.

    The worker process gets a bounded GRACE to finish dying
    (`_ATTESTATION_EXIT_GRACE_S`, probed every `_ATTESTATION_PROBE_INTERVAL_S`).
    The same CTRL run found that too: the inspection ran about two seconds
    after `stop` and counted a process that was already exiting — a race in the
    INSTRUMENT, reported as a retention failure on the instance. A process that
    is still there when the grace expires still fails the attestation; the
    record carries how many probes it took, so "it died on the second look" and
    "it was never alive" are different facts in the log.
    """
    import tools.paddle_vast as vast

    if runner is None:
        runner = subprocess.run
    command = _ATTESTATION_COMMAND.format(
        directory=vast.REMOTE_WORKER_DIR, worker=vast.REMOTE_WORKER_PATH, since=int(since_epoch),
    )

    def refused(error: str) -> RetentionAttestation:
        return RetentionAttestation(
            retention_declared=retention_declared, inspected=False, worker_process_alive=True,
            pidfile_present=True, request_artefacts=-1, page_byte_files=-1, unexpected_files=-1,
            error=error, probes=probes,
        )

    probes = 0
    # A BUDGET of looks, not a wall-clock deadline: the waiting is the caller's
    # `sleep`, so a test that passes a no-op sleep must finish immediately
    # rather than spin through the grace period issuing probes.
    budget = max(1, int(_ATTESTATION_EXIT_GRACE_S // _ATTESTATION_PROBE_INTERVAL_S) + 1)
    while True:
        probes += 1
        try:
            completed = vast._run(
                runner, vast._ssh_command(settings, command),
                capture_output=True, text=True, timeout=60,
            )
        except Exception as exc:  # noqa: BLE001 - the class name only; never the message
            return refused(type(exc).__name__)
        if getattr(completed, "returncode", 1) != 0:
            return refused("remote_inspection_failed")
        values = _parse_attestation_output(vast.mask_text(completed.stdout or "", settings))
        required = ("PROC", "PIDFILE", "IMAGES", "REQUESTS", "OTHER")
        if any(name not in values for name in required):
            return refused("remote_inspection_incomplete")
        if values["PROC"] <= 0 or probes >= budget:
            break
        sleep(_ATTESTATION_PROBE_INTERVAL_S)
    return RetentionAttestation(
        retention_declared=retention_declared,
        inspected=True,
        worker_process_alive=values["PROC"] > 0,
        pidfile_present=values["PIDFILE"] > 0,
        request_artefacts=values["REQUESTS"],
        page_byte_files=values["IMAGES"],
        unexpected_files=values["OTHER"],
        temp_image_files=values.get("TMPIMG", 0),
        probes=probes,
    )


# ---------------------------------------------------------------------------
# Rasters (D2, card item 6)
# ---------------------------------------------------------------------------

def recorded_evidence_for(cache, sha: str):
    """The geometry evidence this research cache already holds for `sha`, found
    through the cache's OWN INDEX — or `None` when it holds none.

    Why the index and not a settings key: the key of a Paddle read can only be
    spelled by naming the Paddle capability flag, and `tests/test_paddle_routing.py`
    pins the exact, reviewed set of call sites that may name it — the boundary
    that keeps "a document was read by Paddle" a thing somebody reviewed rather
    than a thing anybody can spell. This tool never reads a page and must not
    become such a site merely to LOOK UP what the run it drove already wrote;
    `discovery/cli.py` refused the same trade for the same reason (a research
    run's `provenance.json` deliberately records no Paddle key). The cache
    stores `settings_key` beside every entry it holds, so the key is READ from
    the run that actually made it. That is also the stronger property: a
    reconstructed key is a second copy of the call shape, and a second copy can
    drift from the first (a DPI default, a stage version, an environment that
    loads different pins) and then silently retain nothing.

    Ambiguity is refused, never guessed. If this research directory holds more
    than one evidence-bearing read of one document — a second configuration
    under a second partition (cell V's A/B) pointed at the same `--data-dir` —
    the reads are accepted only while they record the SAME `raster_sha256` for
    the same page, in which case the bytes to retain are the same bytes
    whichever read is meant. When they disagree the function refuses: writing
    one configuration's pixels under the other's name is the one error a
    sha-named archive cannot show later.
    """
    from evidence.canonical import from_json
    from webapp.artifact_cache import STAGE_OCR

    candidates = []
    for entry in cache.storage.cache_entries(STAGE_OCR, input_sha256=sha.upper()):
        hit, record = cache.get_ocr(sha.upper(), entry["settings_key"])
        if not hit or not record or not record.get("evidence"):
            continue
        candidates.append(from_json(record["evidence"]))
    if not candidates:
        return None
    fingerprints = {
        tuple((page.frame.page_index, page.frame.raster_sha256) for page in evidence.pages)
        for evidence in candidates
    }
    if len(fingerprints) > 1:
        raise WaveRefused(
            f"retain_rasters_for refuses an ambiguous research data directory: it holds "
            f"{len(candidates)} evidence-bearing reads of one document that record different "
            f"page rasters (more than one configuration under one --data-dir); give each "
            f"configuration its own research data directory"
        )
    return candidates[0]


def retain_rasters_for(
    sha: str, *, pdf_bytes: bytes, data_dir: Path, partition: str, dpi: int = PADDLE_RASTER_DPI,
) -> dict[str, int]:
    """Keep the PNG of every page THIS wave sent, sha-named under the research
    partition's own directory (`<data-dir>/rasters/<content sha>/pNNNN.png`).

    The pixels are re-produced here rather than intercepted inside the rung —
    the rung is not this cell's file, and it deliberately writes nothing to
    disk (M11 pins that it opens no path derived from a document). What makes
    that safe is that the claim is CHECKED, not assumed: every page's raster
    sha256 is compared against the `raster_sha256` the immutable evidence
    already records for that page, and a page whose bytes do not reproduce is
    counted as a mismatch and NOT written. So a retained raster is provably
    the image the worker saw, and a drift in the rasteriser shows up as a
    number in the report instead of as a quietly wrong archive.

    Production partitions are unaffected: this function is only ever called
    with a research partition, it writes under `<data-dir>/rasters/`, and the
    production path keeps `raster_sha256` and no file (proven by test).
    `partition` is exactly that assertion — a non-empty research id, refused
    when absent — and not a lookup argument: WHICH read to retain the pages of
    is answered by :func:`recorded_evidence_for` from the cache's own index,
    for the reasons written there.
    """
    from io import BytesIO

    from ocr.rasterize import rasterize_page
    from webapp.artifact_cache import open_cache

    if not partition:
        raise WaveRefused("retain_rasters_for refuses an empty research partition")
    cache = open_cache(Path(data_dir))
    evidence = recorded_evidence_for(cache, sha)
    if evidence is None:
        return {"written": 0, "mismatched": 0, "pages": 0, "skipped_no_evidence": 1}
    out_dir = Path(data_dir) / "rasters" / sha.upper()
    written = mismatched = 0
    for page in evidence.pages:
        index = page.frame.page_index
        expected = page.frame.raster_sha256
        target = out_dir / f"p{index:04d}.png"
        if expected is None:
            continue
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            written += 1
            continue
        buffer = BytesIO()
        # one page at a time: this host is memory-tight and a long statement's
        # full raster set does not need to exist at once to write one file.
        rasterize_page(pdf_bytes, index, dpi=dpi).save(buffer, format="PNG")
        produced = buffer.getvalue()
        if hashlib.sha256(produced).hexdigest() != expected:
            mismatched += 1
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(produced)
        written += 1
    return {"written": written, "mismatched": mismatched, "pages": len(evidence.pages),
            "skipped_no_evidence": 0}


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


class WaveLog:
    """One line per event, appended and flushed. Masked: every line goes
    through the lifecycle tool's own masker before it is written, so a
    connection value cannot reach a log even by accident."""

    def __init__(self, path: Path | None, settings: Any | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._settings = settings
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def bind(self, settings: Any) -> None:
        self._settings = settings

    def __call__(self, event: str, **fields: Any) -> None:
        _validate_wave_event(event, fields)
        rendered = " ".join(f"{name}={value}" for name, value in sorted(fields.items()))
        line = f"{_now()} {event} {rendered}".rstrip()
        if self._settings is not None:
            import tools.paddle_vast as vast

            line = vast.mask_text(line, self._settings)
        print(line, flush=True)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def _refusal_reason(row: Mapping[str, str]) -> str:
    """The reason THIS document produced no PADDLE evidence, from the row's own
    closed vocabularies. Never a message, never a path.

    The U755 run taught this function what a row actually means. `error_type`
    is NOT a Paddle column: when the rung fails and the ladder falls closed to
    another rung, `discovery/runner.py` rebinds `error_type` to the DOCUMENT's
    own outcome further down (for an unresolved statement, typically
    `RuntimeError`, i.e. "no deterministic parser matched"). Reading it as the
    Paddle cause turned 318 unresolved documents into a `RuntimeError` bucket
    that said nothing about Paddle at all. `error_type` IS the Paddle cause in
    exactly one shape — when the rung's failure was also the document's, so no
    other rung produced a read (`source_path` is `none`) and nothing rebinds
    it. Anywhere else a failed rung without its own closed reason is named for
    what is actually known: it failed, and the row kept no reason for it.

    The vocabulary, most specific first:
    * the rung's own `paddle_refusal_reason` (`paddle_evidence_malformed`,
      `remote_customer_data_refused`, `paddle_runtime_mismatch`, …);
    * `paddle_rung_failed_unnamed` — it failed, another rung read the
      document, and the failure's class did not survive on the row;
    * the terminal `error_type` when the document failed with the rung;
    * `paddle_not_attempted` — no research trigger ever reached the rung, so
      "no evidence" is not a Paddle outcome at all;
    * `paddle_evidence_missing` for a rung that ran but left no evidence;
      a financial outcome is never an extractor refusal reason.
    """
    reason = (row.get("paddle_refusal_reason") or "").strip()
    if reason:
        return reason
    rung = (row.get("paddle_rung") or "").strip()
    error = (row.get("error_type") or "").strip()
    if rung in ("", "not_attempted"):
        return "invalid_pdf" if row.get("outcome_reason") == "invalid_pdf" else "paddle_not_attempted"
    if rung.endswith("failed") or "refused" in rung:
        if (row.get("source_path") or "").strip() in ("", "none"):
            return error or "paddle_rung_failed_unnamed"
        return "paddle_rung_failed_unnamed"
    return "paddle_evidence_missing"


def _export_require(value: bool, code: str) -> None:
    if not value:
        raise WaveRefused(code)


def _closed_refusal(reason: str, *, empty: bool = False) -> str:
    _export_require(isinstance(reason, str) and (reason in WAVE_REFUSAL_REASONS or (empty and reason == "")),
                    "wave_refusal_code_unknown")
    return reason


def _finite_number(value: Any, *, nullable: bool = False) -> bool:
    return (nullable and value is None) or (
        type(value) in (int, float) and math.isfinite(value) and value >= 0)


def _validate_attestation(record: Mapping[str, Any]) -> None:
    booleans = {"retention_declared", "inspected", "worker_process_alive", "pidfile_present", "passed"}
    counts = {"request_artefacts", "page_byte_files", "unexpected_files", "temp_image_files", "probes"}
    required = booleans | {"request_artefacts", "page_byte_files", "unexpected_files"}
    _export_require(isinstance(record, dict) and required <= set(record)
                    and set(record) <= booleans | counts | {"error"}, "wave_attestation_fields_invalid")
    unavailable_counts = {"request_artefacts", "page_byte_files", "unexpected_files"}
    failed_inspection = (
        record.get("inspected") is False and record.get("worker_process_alive") is True
        and record.get("pidfile_present") is True and record.get("passed") is False
        and record.get("error") in ("remote_inspection_failed", "remote_inspection_incomplete", "PaddleVastError")
        and all(type(record.get(key)) is int and record[key] == -1 for key in unavailable_counts)
    )
    for key, value in record.items():
        if key in booleans:
            _export_require(type(value) is bool, "wave_attestation_value_invalid")
        elif key in counts:
            _export_require(type(value) is int and (value >= 0 or
                            (failed_inspection and key in unavailable_counts and value == -1)),
                            "wave_attestation_value_invalid")
        else:
            _export_require(value in ("", "remote_inspection_failed", "remote_inspection_incomplete", "PaddleVastError"),
                            "wave_attestation_error_unknown")


def _validate_wave_event(event: str, fields: Mapping[str, Any]) -> None:
    """The ordinary log is a closed software event, not a free-form message."""
    schemas = {
        "lifecycle.check": {"reached", "versions_match_pins"},
        "lifecycle.tunnel_up": {"local_port"}, "lifecycle.start": {"worker_port"},
        "lifecycle.status": {"available", "reason", "tunnel_running"},
        "lifecycle.deploy": {"scp_ok", "self_check_ok"},
        "lifecycle.retention": {"declared"}, "lifecycle.stop": set(), "lifecycle.tunnel_down": set(),
        "wave.preflight": {"population", "documents", "set_sha256", "partition", "config", "predecessors"},
        "wave.pending": {"population", "pending", "already_evidence"},
        "wave.chunk_budget_spent": {"chunks"},
        "chunk.start": {"chunk", "documents"}, "chunk.failed": {"chunk", "returncode", "run_dir"},
        "chunk.end": {"chunk", "documents", "cache_hits", "rasters_written", "rasters_mismatched",
                      "elapsed_ms", "run_dir"},
        "chunk.export": {"chunk", "status"},
        "wave.session_end": {"started", "ended", "population", "config", "partition", "chunks",
                             "documents", "retention_declared", "attempted", "evidence", "refused",
                             "pages_evidence", "pages_refused", "export_status"},
    }
    if event == "lifecycle.attestation":
        _validate_attestation(dict(fields))
        return
    _export_require(event in schemas and set(fields) <= schemas[event], "wave_event_fields_invalid")
    bools = {"reached", "versions_match_pins", "available", "tunnel_running", "scp_ok", "self_check_ok",
             "declared", "retention_declared"}
    for key, value in fields.items():
        if key in bools:
            _export_require(type(value) is bool, "wave_event_value_invalid")
        elif key == "population":
            _export_require(value in POPULATION_ORDER, "wave_event_population_invalid")
        elif key in ("config", "partition"):
            _export_require(value in CONFIGURATIONS, "wave_event_configuration_invalid")
        elif key == "predecessors":
            _export_require(value in ("none", "CTRL", "CTRL,U755"), "wave_event_predecessors_invalid")
        elif key == "reason":
            _export_require(value == "ok" or value in REFUSAL_REASONS, "wave_event_reason_unknown")
        elif key in ("status", "export_status"):
            _export_require(value in ("failed", "complete"), "wave_event_status_unknown")
        elif key == "set_sha256":
            _export_require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                            "wave_event_hash_invalid")
        elif key == "run_dir":
            if value != "none":
                _export_session(value)
        elif key in ("started", "ended"):
            _export_require(isinstance(value, str) and re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}", value) is not None,
                "wave_event_timestamp_invalid")
        elif key == "returncode":
            _export_require(value is None or type(value) is int, "wave_event_returncode_invalid")
        else:
            _export_require(_finite_number(value), "wave_event_measurement_invalid")


def _safe_run_name(name: str) -> str:
    _export_require(isinstance(name, str) and name not in (".", "..")
                    and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", name) is not None,
                    "wave_run_name_invalid")
    return name


def _export_session(name: str) -> str:
    _safe_run_name(name)
    _export_require(re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}(?:\.[0-9]{6})?-0000-[0-9a-f]{8}",
        name) is not None, "wave_export_session_invalid")
    return name


def _inside(path: Path, parent: Path, *, exists: bool = False) -> Path:
    try:
        base = Path(parent).resolve(strict=exists)
        resolved = Path(path).resolve(strict=exists)
    except (OSError, RuntimeError):
        raise WaveRefused("wave_path_unavailable") from None
    _export_require(resolved != base and resolved.is_relative_to(base), "wave_path_escaped")
    return resolved


def _assert_bindings(bindings: Mapping[Path, Path]) -> None:
    """Keep the supplied lexical paths bound, including their parent symlinks."""
    try:
        valid = all(path.resolve(strict=True) == resolved for path, resolved in bindings.items())
    except (OSError, RuntimeError):
        raise WaveRefused("wave_path_binding_changed") from None
    _export_require(valid, "wave_path_binding_changed")


def _validate_storage_chunks(chunks: Any, version: int) -> None:
    _export_require(isinstance(chunks, list), "wave_state_chunks_invalid")
    for chunk in chunks:
        _export_require(isinstance(chunk, dict), "wave_state_chunk_invalid")
        if "storage" in chunk:
            _export_require(version == STATE_VERSION and chunk["storage"] == PRIVATE_RUN_STORAGE,
                            "wave_custody_storage_unknown")


def _disjoint(left: Path, right: Path) -> None:
    left, right = Path(left).resolve(), Path(right).resolve()
    _export_require(left != right and not left.is_relative_to(right)
                    and not right.is_relative_to(left), "wave_storage_roots_overlap")


def _custody_run_parent(data_dir: Path, partition: str, population_name: str,
                        out_dir: Path | None = None) -> Path:
    _export_require(partition in {block["partition"] for block in CONFIGURATIONS.values()}
                    and population_name in POPULATION_ORDER, "wave_custody_identity_invalid")
    data = Path(data_dir).resolve()
    parent = _inside(data / ".wave" / partition / "discovery-runs" / population_name, data)
    if out_dir is not None:
        _disjoint(data, Path(out_dir))
        _disjoint(parent, Path(out_dir))
    return parent


def _closed_bytes(path: Path, *, maximum: int = 32 * 1024 * 1024) -> bytes:
    """Bounded stable read of a closed producer file; never print its path/value."""
    original = Path(path)
    try:
        resolved = original.resolve(strict=True)
        _export_require(resolved.is_file(), "wave_source_not_file")
        with resolved.open("rb") as handle:
            before = os.fstat(handle.fileno())
            _export_require(before.st_size <= maximum, "wave_source_byte_limit")
            raw = handle.read(maximum + 1)
            after = os.fstat(handle.fileno())
        current = original.stat()
        _assert_bindings({original: resolved})
    except (OSError, RuntimeError):
        raise WaveRefused("wave_source_unavailable") from None
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
    _export_require(len(raw) == before.st_size and identity(before) == identity(after) == identity(current),
                    "wave_source_changed")
    return raw


def _csv_records(raw: bytes, *, fields: Sequence[str] | None = None) -> list[dict[str, str]]:
    try:
        decoded = raw.decode("utf-8", errors="strict")
        table = list(csv.reader(io.StringIO(decoded, newline=""), strict=True))
    except (UnicodeError, csv.Error):
        raise WaveRefused("wave_rows_encoding_invalid") from None
    reader = iter(table)
    header = next(reader, [])
    _export_require(bool(header) and len(header) == len(set(header)), "wave_rows_header_invalid")
    if fields is not None:
        _export_require(header == list(fields), "wave_export_schema_mismatch")
    records = []
    for values in reader:
        _export_require(len(values) == len(header), "wave_rows_width_invalid")
        records.append(dict(zip(header, values)))
    return records


def _technical_row(row: Mapping[str, str], partition: str) -> dict[str, str]:
    _export_require(tuple(row) == TECHNICAL_FIELDS, "wave_export_fields_invalid")
    _export_require(all(isinstance(value, str) for value in row.values()), "wave_export_value_type")
    for name in ("content_sha256", "evidence_sha256"):
        _export_require((name == "evidence_sha256" and row[name] == "")
                        or re.fullmatch(r"[0-9A-Fa-f]{64}", row[name]) is not None,
                        "wave_export_hash_invalid")
    _export_require(row["research_partition"] == partition, "wave_export_partition_mismatch")
    for name, choices in (
        ("stage_evidence", {"not_attempted", "present", "absent"}),
        ("source_path", {"none", "native", "local_tesseract", "paddle", "visual", "committed_artifact"}),
        ("cache_paddle", {"", "hit", "miss", "bypass"}),
    ):
        _export_require(row[name] in choices, "wave_export_status_unknown")
    _closed_refusal(row["wave_refusal_reason"], empty=True)
    evidence = row["stage_evidence"] == "present" and row["source_path"] == "paddle"
    _export_require((row["wave_refusal_reason"] == "") == evidence,
                    "wave_export_refusal_shape_invalid")
    for name in ("page_count", "bytes_up", "bytes_down"):
        value = row[name]
        _export_require((name != "page_count" and value == "")
                        or re.fullmatch(r"(?:0|[1-9][0-9]*)", value) is not None,
                        "wave_export_count_invalid")
    for name in ("inference_ms", "vram_mb", "peak_rss_mb", "elapsed_ms"):
        value = row[name]
        if value == "" or (name == "peak_rss_mb" and value == "not measured"):
            continue
        _export_require(re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", value)
                        is not None, "wave_export_measurement_invalid")
        _export_require(math.isfinite(float(value)) and float(value) >= 0,
                        "wave_export_measurement_invalid")
    return dict(row)


def _project_wave_technical_rows(raw_rows: Sequence[Mapping[str, str]], partition: str) -> list[dict[str, str]]:
    result = []
    for raw in raw_rows:
        _export_require(all(name in raw for name in TECHNICAL_FIELDS if name != "wave_refusal_reason"),
                        "wave_source_columns_missing")
        reason = "" if raw.get("stage_evidence") == "present" and raw.get("source_path") == "paddle" \
            else _closed_refusal(_refusal_reason(raw))
        projected = {name: reason if name == "wave_refusal_reason" else raw[name]
                     for name in TECHNICAL_FIELDS}
        result.append(_technical_row(projected, partition))
    return result


def _export_identity(configuration: str, partition: str, population_name: str,
                     session: str, source_sha256: str, provenance_sha256: str) -> None:
    _export_require(configuration in CONFIGURATIONS
                    and CONFIGURATIONS[configuration]["partition"] == partition
                    and population_name in POPULATION_ORDER, "wave_export_identity_invalid")
    _export_session(session)
    _export_require(all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
                        for value in (source_sha256, provenance_sha256)),
                    "wave_source_binding_invalid")


def _atomic_export_file(path: Path, raw: bytes, *, validate: Callable[[], None]) -> None:
    temporary = path.with_name(path.name + ".writing")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    temporary_binding = {temporary: path.parent.resolve(strict=True) / temporary.name}
    _export_require(not path.exists(), "wave_export_destination_exists")
    validate()
    _assert_bindings(temporary_binding)
    _export_require(_closed_bytes(temporary) == raw and not path.exists(), "wave_export_file_changed")
    temporary.rename(path)


def write_wave_technical_export(
    custody_run: Path, out_dir: Path, *, configuration: str, partition: str,
    population_name: str, expected_source_rows_sha256: str,
    expected_source_provenance_sha256: str, expected_session: str,
) -> Path:
    """Offline-only projection of an explicitly bound, closed custody run.

    No pending-document loop, state write, lifecycle or extractor is called.
    Both expected source hashes/session come from the caller's private record.
    Partial destinations remain without a completion marker after failure.
    """
    _export_identity(configuration, partition, population_name, expected_session,
                     expected_source_rows_sha256, expected_source_provenance_sha256)
    supplied_source, supplied_output = Path(custody_run), Path(out_dir)
    source = supplied_source.resolve(strict=True)
    output = supplied_output.resolve()
    _export_require(source.is_dir() and source.name == expected_session, "wave_source_session_mismatch")
    _disjoint(source, output)
    rows_path = supplied_source / "rows.csv"
    provenance_path = supplied_source / "provenance.json"
    bindings = {supplied_source: source,
                rows_path: _inside(rows_path, source, exists=True),
                provenance_path: _inside(provenance_path, source, exists=True)}
    raw, provenance_raw = _closed_bytes(rows_path), _closed_bytes(provenance_path)
    _export_require(hashlib.sha256(raw).hexdigest() == expected_source_rows_sha256,
                    "wave_source_rows_binding_mismatch")
    _export_require(hashlib.sha256(provenance_raw).hexdigest() == expected_source_provenance_sha256,
                    "wave_source_provenance_binding_mismatch")
    provenance = json.loads(provenance_raw.decode("utf-8", errors="strict"))
    _export_require(isinstance(provenance, dict), "wave_source_provenance_shape")
    run_record = provenance.get("run_of_record")
    _export_require(isinstance(run_record, dict), "wave_source_provenance_shape")
    identity = run_record.get("partitions")
    _export_require(isinstance(identity, dict), "wave_source_provenance_shape")
    _export_require(identity.get("mode") == "research-paddle"
                    and identity.get("research_partition") == partition,
                    "wave_source_provenance_mismatch")
    records = _project_wave_technical_rows(_csv_records(raw), partition)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=TECHNICAL_FIELDS)
    writer.writeheader()
    writer.writerows(records)
    scan_raw = stream.getvalue().encode("utf-8", errors="strict")
    marker = {
        "kind": EXPORT_KIND, "schema_version": EXPORT_SCHEMA_VERSION,
        "configuration": configuration, "partition": partition, "population": population_name,
        "source_session": expected_session, "source_rows_sha256": expected_source_rows_sha256,
        "source_provenance_sha256": expected_source_provenance_sha256,
        "rows_sha256": hashlib.sha256(scan_raw).hexdigest(),
        "fields": list(TECHNICAL_FIELDS), "row_count": len(records),
    }
    _assert_bindings(bindings)
    _export_require(supplied_output.resolve() == output, "wave_export_path_retargeted")
    output.mkdir(parents=True, exist_ok=True)
    target = supplied_output / expected_session
    resolved_target = _inside(target, output)
    _export_require(not target.exists(), "wave_export_destination_exists")
    target.mkdir(exist_ok=False)
    bindings.update({supplied_output: output, target: resolved_target})

    def validate() -> None:
        _assert_bindings(bindings)
        _disjoint(supplied_source, supplied_output)
        _export_require(_closed_bytes(rows_path) == raw and _closed_bytes(provenance_path) == provenance_raw,
                        "wave_source_changed")
        if target / EXPORT_ROWS in bindings:
            _export_require(_closed_bytes(target / EXPORT_ROWS) == scan_raw, "wave_export_file_changed")
        _assert_bindings(bindings)

    _atomic_export_file(target / EXPORT_ROWS, scan_raw, validate=validate)
    bindings[target / EXPORT_ROWS] = _inside(target / EXPORT_ROWS, resolved_target, exists=True)
    validate()
    _atomic_export_file(target / EXPORT_MARKER,
                       (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode("utf-8"), validate=validate)
    return target


def read_wave_technical_export(
    run_dir: Path, *, expected_configuration: str, expected_partition: str,
    expected_population: str, expected_source_rows_sha256: str,
    expected_source_provenance_sha256: str, expected_session: str,
) -> list[dict[str, str]]:
    """Validate an export against an independently trusted private source binding."""
    _export_identity(expected_configuration, expected_partition, expected_population,
                     expected_session, expected_source_rows_sha256, expected_source_provenance_sha256)
    supplied = Path(run_dir)
    directory = supplied.resolve(strict=True)
    _export_require(directory.name == expected_session, "wave_export_session_mismatch")
    marker_path, rows_path = supplied / EXPORT_MARKER, supplied / EXPORT_ROWS
    bindings = {supplied: directory,
                marker_path: _inside(marker_path, directory, exists=True),
                rows_path: _inside(rows_path, directory, exists=True)}
    _export_require({item.name for item in supplied.iterdir()} == {EXPORT_ROWS, EXPORT_MARKER},
                    "wave_export_files_invalid")
    marker_raw = _closed_bytes(marker_path)
    marker = json.loads(marker_raw.decode("utf-8", errors="strict"))
    _export_require(isinstance(marker, dict) and set(marker) == {"kind", "schema_version", "configuration", "partition", "population",
                                    "source_session", "source_rows_sha256", "source_provenance_sha256",
                                    "rows_sha256", "fields", "row_count"}, "wave_export_marker_fields")
    _export_require(marker["kind"] == EXPORT_KIND and type(marker["schema_version"]) is int
                    and marker["schema_version"] == EXPORT_SCHEMA_VERSION, "wave_export_marker_version")
    for key, value in (("configuration", expected_configuration), ("partition", expected_partition),
                       ("population", expected_population), ("source_session", expected_session),
                       ("source_provenance_sha256", expected_source_provenance_sha256),
                       ("source_rows_sha256", expected_source_rows_sha256), ("fields", list(TECHNICAL_FIELDS))):
        _export_require(marker[key] == value, "wave_export_marker_binding_mismatch")
    for key in ("source_provenance_sha256", "rows_sha256"):
        _export_require(isinstance(marker[key], str) and re.fullmatch(r"[0-9a-f]{64}", marker[key]) is not None,
                        "wave_export_marker_hash_invalid")
    rows_raw = _closed_bytes(rows_path)
    _export_require(hashlib.sha256(rows_raw).hexdigest() == marker["rows_sha256"],
                    "wave_export_rows_hash_mismatch")
    records = _csv_records(rows_raw, fields=TECHNICAL_FIELDS)
    _export_require(type(marker["row_count"]) is int and marker["row_count"] == len(records),
                    "wave_export_row_count_mismatch")
    for record in records:
        _technical_row(record, expected_partition)
    _export_require(_closed_bytes(marker_path) == marker_raw
                    and _closed_bytes(rows_path) == rows_raw,
                    "wave_export_changed_during_read")
    _assert_bindings(bindings)
    _export_require({item.name for item in supplied.iterdir()} == {EXPORT_ROWS, EXPORT_MARKER},
                    "wave_export_files_invalid")
    return records


def _discovery_argv(
    *, population_file: Path, partition: str, data_dir: Path, out_dir: Path, root: Path,
    skip_baseline: bool = False,
) -> list[str]:
    """The ONE command this tool ever runs against a document.

    `skip_baseline` exists for the synthetic end-to-end proof and is
    deliberately NOT on this tool's command line: the frozen-archive baseline
    is what makes one wave's numbers comparable to another's, and an operator
    must not be able to turn it off from a shell. A test that builds its own
    three-document root has no frozen baseline to check and passes it in
    process.
    """
    argv = [
        sys.executable, "-m", "discovery", "--research-paddle",
        "--population", str(population_file),
        "--research-partition", partition,
        "--data-dir", str(data_dir),
        "--out", str(out_dir),
        "--root", str(root),
        "--quiet",
    ]
    if skip_baseline:
        argv.append("--skip-baseline")
    return argv


def _chunk_environment(data_dir: Path) -> dict[str, str]:
    """This process's environment — including the two opt-in literals, which
    is the ONLY way they reach the chunk and the reason `preflight` insists
    they are here — plus one containment: `WEBAPP_DATA_DIR`.

    `python -m discovery` constructs a `JobStore()` at IMPORT time (the CLI
    imports `corpus_gate` -> `adb_forensic_audit` -> `webapp.app`), which
    creates an empty database wherever `WEBAPP_DATA_DIR` points — by default a
    `webapp_data` directory beside the working directory. That is a
    pre-existing import-time side effect of the whole CLI, recorded as such by
    the Phase 2.2 cell that measured it; the wave points it at a named sink
    beside the research directory so a research session leaves nothing that
    LOOKS like a production cache in a checkout. The sink is a sibling, never
    inside the research directory, so the research door's containment rule is
    unaffected.
    """
    environment = dict(os.environ)
    sink = Path(data_dir).parent / f"{Path(data_dir).name}_import_sink"
    environment["WEBAPP_DATA_DIR"] = str(sink)
    return environment


def _new_run_dir(out_dir: Path, before: set[Path]) -> Path | None:
    after = {path for path in Path(out_dir).iterdir() if path.is_dir()} if Path(out_dir).exists() else set()
    fresh = sorted(after - before)
    _export_require(len(fresh) <= 1, "wave_child_run_ambiguous")
    return fresh[0] if fresh else None


@dataclass
class Lifecycle:
    """The instance's up/down sequence, behind one object so a test can drive
    the whole wave without a network. The real one is `tools.paddle_vast`'s
    subcommands, called in the documented order and in no other."""

    settings: Any
    log: WaveLog
    deploy_if_needed: bool = True

    def up(self) -> dict[str, Any]:
        import tools.paddle_vast as vast

        record: dict[str, Any] = {}
        check = vast.cmd_check(self.settings)
        record["versions_match_pins"] = bool(check.get("versions_match_pins"))
        # An instance that answered and an instance that could not be reached
        # must not produce the same refusal. `cmd_check` reports `None` for the
        # GPU and for both remote versions when its SSH command did not run at
        # all, and `versions_match_pins` is then False for a reason that has
        # nothing to do with a version — so a stopped or re-provisioned
        # instance would otherwise be reported as a model-pin drift, and the
        # next operator would go looking for an upgrade that never happened.
        reached = check.get("gpu") is not None or check.get("remote_paddleocr_version") is not None
        self.log("lifecycle.check", reached=reached,
                 versions_match_pins=record["versions_match_pins"])
        if not reached:
            raise WaveRefused(
                "the approved instance did not answer: the lifecycle's own check reached "
                "neither the GPU nor the remote interpreter. The connection contract comes "
                "from the gitignored environment file and nothing here may guess another "
                "host, port or user, and the previous instance is retired for customer data "
                "— so this is an operator action (start or re-provision the approved "
                "instance and update that file), not something the wave can work around."
            )
        if not record["versions_match_pins"]:
            raise WaveRefused(
                "the instance's PaddleOCR/PaddlePaddle versions do not match the pins; a "
                "remote upgrade STOPS the rung until it is reviewed (D5)"
            )
        if not vast._port_listening(self.settings.tunnel_local_port):
            vast.cmd_tunnel_up(self.settings)
            self.log("lifecycle.tunnel_up", local_port=self.settings.tunnel_local_port)
        status = vast.cmd_status(self.settings)
        available = bool(status["probe"]["available"])
        self.log("lifecycle.status", available=available, reason=status["probe"]["reason"],
                 tunnel_running=status["tunnel_running"])
        if not available and self.deploy_if_needed:
            # A worker may still be alive from an earlier session holding an
            # EARLIER session token — it would answer `start`'s successor with
            # a 401 and keep the port. Stopping first is a no-op when nothing
            # is running (`not_running`) and the only way a token ROTATION
            # actually takes effect.
            vast.cmd_stop(self.settings)
            deployed = vast.cmd_deploy(self.settings)
            self.log("lifecycle.deploy", scp_ok=deployed.get("scp_ok"),
                     self_check_ok=deployed.get("self_check_ok"))
            vast.cmd_start(self.settings)
            self.log("lifecycle.start", worker_port=self.settings.worker_port)
            # `start` MINTS the session token and writes it to the gitignored
            # runtime directory; the settings object in hand was loaded before
            # that file existed and still carries the old value (or none), so
            # every later call would authenticate as nobody. Re-read them: the
            # loader's own fallback is that file. The log's masker is re-bound
            # to the new object so the new token is masked too.
            from ocr.paddle_config import load_paddle_settings

            self.settings = load_paddle_settings()
            self.log.bind(self.settings)
            for _ in range(30):
                status = vast.cmd_status(self.settings)
                if status["probe"]["available"]:
                    break
                time.sleep(2)
            available = bool(status["probe"]["available"])
            self.log("lifecycle.status", available=available, reason=status["probe"]["reason"])
        if not available:
            raise WaveRefused(
                f"the worker is not usable: {status['probe']['reason']}; the wave sends nothing"
            )
        record["identity"] = status["probe"]["reason"]
        record["retention_declared"] = self._retention()
        self.log("lifecycle.retention", declared=record["retention_declared"])
        return record

    def _retention(self) -> bool:
        from ocr.paddle_client import PaddleClient, retention_declaration

        version = PaddleClient(self.settings).version()
        return retention_declaration(version) is not None

    def down(self, *, retention_declared: bool, since_epoch: float = 0.0) -> RetentionAttestation:
        import tools.paddle_vast as vast

        vast.cmd_stop(self.settings)
        self.log("lifecycle.stop")
        attestation = attest_retention(
            self.settings, retention_declared=retention_declared, since_epoch=since_epoch,
        )
        self.log("lifecycle.attestation", **attestation.as_record())
        vast.cmd_tunnel_down(self.settings)
        self.log("lifecycle.tunnel_down")
        return attestation


def run_wave(
    *,
    population_file: Path,
    population_name: str,
    populations_dir: Path,
    config: str,
    data_dir: Path,
    out_dir: Path,
    root: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_chunks: int | None = None,
    retain_rasters: bool = True,
    lifecycle: Any | None = None,
    log: WaveLog | None = None,
    environ: Mapping[str, str] | None = None,
    subprocess_runner: Callable[..., Any] | None = None,
    skip_baseline: bool = False,
) -> dict[str, Any]:
    """One wave SESSION: the doors, the instance up, chunks until the
    population is read or `max_chunks` is spent, the instance down, the
    attestation. Resumable: everything it learns is in the state file before
    the next chunk starts."""
    log = log or WaveLog(None)
    runner = subprocess_runner or subprocess.run

    require_opt_in(environ)
    block = resolve_configuration(config)
    partition = block["partition"]
    data_dir = Path(data_dir)
    refuse_a_production_data_dir(data_dir)
    _custody_run_parent(data_dir, partition, population_name, out_dir)
    population = read_population_file(Path(population_file))
    refuse_holdout_members(population)
    digests = population_digests(Path(population_file))
    predecessors = refuse_out_of_order(
        population_name, data_dir=data_dir, partition=partition,
        populations_dir=Path(populations_dir),
    )
    log("wave.preflight", population=population_name, documents=len(population),
        set_sha256=digests["set_sha256"], partition=partition, config=config,
        predecessors=",".join(predecessors) or "none")

    state_path = WaveState.path_for(data_dir, partition, population_name)
    state = WaveState.load(state_path)
    if state.population_set_sha256 and state.population_set_sha256 != digests["set_sha256"]:
        raise WaveRefused(
            f"the {population_name} state under partition {partition} was built for a different "
            "population (its set digest disagrees). A wave never silently studies a different "
            "set than the one it resumed"
        )
    state.config, state.partition, state.population_name = config, partition, population_name
    state.population_file_sha256 = digests["file_sha256"]
    state.population_set_sha256 = digests["set_sha256"]
    pending = state.pending(population)
    if pending:
        state.version = STATE_VERSION
    state.save(state_path)
    log("wave.pending", population=population_name, pending=len(pending),
        already_evidence=state.counts()["evidence"])

    session: dict[str, Any] = {
        "started": _now(), "population": population_name, "config": config,
        "partition": partition, "chunks": 0, "documents": 0,
    }
    attestation: RetentionAttestation | None = None
    retention_declared = False
    # The wall-clock moment this session began, handed to the attestation so a
    # file that was already in the instance's shared `/tmp` before we touched
    # it is not counted as something this session left behind (the CTRL run
    # found exactly one such file, the operator's own live-test fixture).
    session_epoch = time.time()
    session_chunk_start = len(state.chunks)
    try:
        if pending and lifecycle is not None:
            up = lifecycle.up()
            retention_declared = bool(up.get("retention_declared"))
            session["retention_declared"] = retention_declared
        chunk_index = len(state.chunks)
        for offset in range(0, len(pending), chunk_size):
            if max_chunks is not None and session["chunks"] >= max_chunks:
                log("wave.chunk_budget_spent", chunks=session["chunks"])
                break
            chunk = pending[offset: offset + chunk_size]
            try:
                processed = _run_one_chunk(
                    chunk=chunk, chunk_index=chunk_index, state=state, state_path=state_path,
                    partition=partition, data_dir=data_dir, out_dir=Path(out_dir), root=Path(root),
                    retain_rasters=retain_rasters, log=log, runner=runner,
                    skip_baseline=skip_baseline,
                )
            except WaveExportFailed as exc:
                session["chunks"] += 1
                session["documents"] += exc.processed
                session["export_status"] = "failed"
                raise
            session["chunks"] += 1
            session["documents"] += processed
            chunk_index += 1
    finally:
        if lifecycle is not None and pending:
            attestation = lifecycle.down(
                retention_declared=retention_declared, since_epoch=session_epoch,
            )
            session["attestation"] = attestation.as_record()
        session["ended"] = _now()
        # A first private save can fail while this final audit save succeeds.
        # Count completed chunks persisted here, including that case; failed
        # children and no-work sessions contribute no completed work.
        completed_here = [chunk for chunk in state.chunks[session_chunk_start:]
                          if chunk.get("status") == "complete"]
        session["chunks"] = len(completed_here)
        session["documents"] = sum(chunk["documents"] for chunk in completed_here)
        session.update(state.counts())
        state.sessions.append(session)
        state.save(state_path)
    log("wave.session_end", **{key: value for key, value in session.items()
                               if key != "attestation"})
    return {"state": state, "session": session,
            "attestation": None if attestation is None else attestation.as_record()}


def _run_one_chunk(
    *, chunk: Sequence[str], chunk_index: int, state: WaveState, state_path: Path,
    partition: str, data_dir: Path, out_dir: Path, root: Path, retain_rasters: bool,
    log: WaveLog, runner: Callable[..., Any], skip_baseline: bool = False,
) -> int:
    """One `python -m discovery --research-paddle` invocation over one slice of
    the population, then the rows it produced folded into the state.

    The chunk's population file is written under the research data directory,
    not a temporary one: a wave that dies here leaves the exact set it was
    reading on disk beside the state that says it was reading it.
    """
    chunk_dir = Path(data_dir) / ".wave" / partition / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_file = chunk_dir / f"chunk-{chunk_index:04d}.shas"
    chunk_file.write_text(
        f"# chunk {chunk_index} of the wave; {len(chunk)} documents\n" + "\n".join(chunk) + "\n",
        encoding="utf-8",
    )
    custody_parent = _custody_run_parent(data_dir, partition, state.population_name, out_dir)
    custody_parent.mkdir(parents=True, exist_ok=True)
    before = {path for path in custody_parent.iterdir() if path.is_dir()}
    argv = _discovery_argv(population_file=chunk_file, partition=partition, data_dir=data_dir,
                            out_dir=custody_parent, root=root, skip_baseline=skip_baseline)
    started = time.perf_counter()
    log("chunk.start", chunk=chunk_index, documents=len(chunk))
    completed = runner(argv, cwd=str(ROOT), capture_output=True, text=True,
                       env=_chunk_environment(data_dir))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    _export_require(_custody_run_parent(data_dir, partition, state.population_name, out_dir)
                    == custody_parent, "wave_custody_parent_retargeted")
    run_dir = _new_run_dir(custody_parent, before)
    run_bindings = {Path(data_dir): Path(data_dir).resolve(), custody_parent: custody_parent}
    if run_dir is not None:
        run_bindings[run_dir] = _inside(run_dir, custody_parent, exists=True)
        _export_session(run_dir.name)
    if getattr(completed, "returncode", 1) != 0 or run_dir is None:
        # The chunk failed as a WHOLE (a door refused, the process died). No
        # document of it is recorded: nothing was learned about any of them,
        # and a resume must attempt every one again.
        log("chunk.failed", chunk=chunk_index, returncode=getattr(completed, "returncode", None),
            run_dir="none" if run_dir is None else run_dir.name)
        state.chunks.append({"index": chunk_index, "documents": len(chunk), "status": "failed",
                             "elapsed_ms": elapsed_ms})
        state.save(state_path)
        raise WaveRefused(
            f"chunk {chunk_index} did not complete (exit "
            f"{getattr(completed, 'returncode', None)}); the wave stops rather than reporting "
            "a population it did not read"
        )

    rows_path, provenance_path = run_dir / "rows.csv", run_dir / "provenance.json"
    run_bindings[rows_path] = _inside(rows_path, run_dir, exists=True)
    run_bindings[provenance_path] = _inside(provenance_path, run_dir, exists=True)
    source_rows = _closed_bytes(rows_path)
    rows_sha256 = hashlib.sha256(source_rows).hexdigest()
    source_provenance = _closed_bytes(provenance_path)
    rows = {row["content_sha256"].upper(): row for row in _csv_records(source_rows)}
    wanted = {sha.upper() for sha in chunk}
    staged_outcomes: dict[str, DocumentOutcome] = {}
    processed = 0
    rasters = {"written": 0, "mismatched": 0}
    for sha in sorted(wanted):
        row = rows.get(sha)
        if row is None:
            # D4: a document of the named population that produced no row at
            # all is a REFUSAL with its own reason, never a silent hole.
            staged_outcomes[sha] = DocumentOutcome(
                outcome=OUTCOME_REFUSED, reason="no_row_produced", pages=0,
                chunk=chunk_index, at=_now(),
            )
            processed += 1
            continue
        pages = int(row.get("page_count") or 0)
        if row.get("stage_evidence") == "present" and row.get("source_path") == "paddle":
            staged_outcomes[sha] = DocumentOutcome(outcome=OUTCOME_EVIDENCE, reason="", pages=pages,
                                                   chunk=chunk_index, at=_now())
            if retain_rasters:
                counts = retain_rasters_for(
                    sha, pdf_bytes=(Path(root) / row["relative_path"]).read_bytes(),
                    data_dir=data_dir, partition=partition,
                )
                rasters["written"] += counts["written"]
                rasters["mismatched"] += counts["mismatched"]
        else:
            staged_outcomes[sha] = DocumentOutcome(outcome=OUTCOME_REFUSED, reason=_refusal_reason(row),
                                                   pages=pages, chunk=chunk_index, at=_now())
        processed += 1
    cache_hits = sum(1 for sha in wanted
                     if rows.get(sha, {}).get("cache_paddle") == "hit")
    _export_require(_closed_bytes(rows_path) == source_rows
                    and _closed_bytes(provenance_path) == source_provenance,
                    "wave_custody_source_changed")
    _assert_bindings(run_bindings)
    _export_require(_custody_run_parent(data_dir, partition, state.population_name, out_dir)
                    == custody_parent, "wave_custody_parent_retargeted")
    # Only byte- and path-bound custody can change resume outcomes. The final
    # session save must not persist records from a rejected custody read.
    for sha, outcome in staged_outcomes.items():
        state.record(sha, outcome)
    state.chunks.append({
        "index": chunk_index, "documents": len(chunk), "status": "complete",
        "run_dir": run_dir.name, "elapsed_ms": elapsed_ms, "cache_hits": cache_hits,
        "rasters_written": rasters["written"], "rasters_mismatched": rasters["mismatched"],
        "storage": PRIVATE_RUN_STORAGE, "rows_sha256": rows_sha256,
        "provenance_sha256": hashlib.sha256(source_provenance).hexdigest(),
    })
    state.save(state_path)
    log("chunk.end", chunk=chunk_index, documents=processed, cache_hits=cache_hits,
        rasters_written=rasters["written"], rasters_mismatched=rasters["mismatched"],
        elapsed_ms=elapsed_ms, run_dir=run_dir.name)
    # Extraction/state is authoritative and complete before a reporting attempt.
    # A failed export is recovered offline, never by calling pending() again.
    try:
        write_wave_technical_export(
            run_dir, out_dir, configuration=state.config, partition=partition,
            population_name=state.population_name, expected_source_rows_sha256=rows_sha256,
            expected_source_provenance_sha256=hashlib.sha256(source_provenance).hexdigest(),
            expected_session=run_dir.name,
        )
    except Exception:
        state.chunks[-1]["export_status"] = "failed"
        state.save(state_path)
        log("chunk.export", chunk=chunk_index, status="failed")
        raise WaveExportFailed(processed) from None
    state.chunks[-1]["export_status"] = "complete"
    state.save(state_path)
    log("chunk.export", chunk=chunk_index, status="complete")
    return processed


# ---------------------------------------------------------------------------
# report (card item 7)
# ---------------------------------------------------------------------------

def _percentiles(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "p50": round(statistics.median(ordered), 1),
        "p95": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 1),
        "max": round(ordered[-1], 1),
    }


def wave_report(
    *, data_dir: Path, config: str, populations_dir: Path | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Per population and configuration: what was attempted, what produced
    evidence, what refused and why, what a re-run served from cache, and the
    technical measurements. Counts and figures only.

    The latency figures are per DOCUMENT, and the report says so in its own key
    names. Per-REQUEST latency is measured (the rung times every page) but it
    is transient by ruling — it never enters the OCR artifact, and the wave
    reads its rows after the process that held it has exited — so a per-page
    percentile here would be a number this tool did not measure. What it can
    say honestly it says: the document total, and the per-page MEAN of that
    total, whose distribution is exact for the single-page documents and an
    average elsewhere.
    """
    block = resolve_configuration(config)
    partition = block["partition"]
    report: dict[str, Any] = {
        "config": config, "partition": partition, "populations": {},
        "attestations": [],
    }
    for name in POPULATION_ORDER:
        state_path = WaveState.path_for(Path(data_dir), partition, name)
        if not state_path.exists():
            continue
        state = WaveState.load(state_path)
        _export_require(state.config == config and state.partition == partition
                        and state.population_name == name, "wave_report_state_identity_mismatch")
        _export_require(state.population_set_sha256 == "" or re.fullmatch(
            r"[0-9a-f]{64}", state.population_set_sha256) is not None, "wave_report_digest_invalid")
        counts = state.counts()
        entry: dict[str, Any] = {
            "population_set_sha256": state.population_set_sha256,
            "attempted": counts["attempted"],
            "evidence": counts["evidence"],
            "refused": counts["refused"],
            "pages_evidence": counts["pages_evidence"],
            "pages_refused": counts["pages_refused"],
            "pages_attempted": counts["pages_evidence"] + counts["pages_refused"],
            "cache_hits": sum(int(chunk.get("cache_hits") or 0) for chunk in state.chunks),
            "rasters_written": sum(int(chunk.get("rasters_written") or 0) for chunk in state.chunks),
            "rasters_mismatched": sum(int(chunk.get("rasters_mismatched") or 0)
                                      for chunk in state.chunks),
            "chunks": len(state.chunks),
            "sessions": len(state.sessions),
        }
        entry.update(_reported_refusals(state, out_dir, data_dir=Path(data_dir)))
        entry["count_identity_holds"] = (
            counts["attempted"] == counts["evidence"] + counts["refused"]
        )
        if populations_dir is not None:
            population_file = Path(populations_dir) / f"{name}.shas"
            if population_file.exists():
                population = read_population_file(population_file)
                entry["population_documents"] = len(population)
                entry["unattempted"] = len(state.unattempted(population))
                entry["complete"] = not state.unattempted(population)
        entry.update(_technical_measurements(state, out_dir, data_dir=Path(data_dir)))
        for session in state.sessions:
            if session.get("attestation"):
                _validate_attestation(session["attestation"])
                report["attestations"].append({"population": name, **session["attestation"]})
        report["populations"][name] = entry
    return report


def _recorded_run_directory(state: WaveState, out_dir: Path, name: str) -> Path | None:
    _safe_run_name(name)
    _export_require(state.population_name in POPULATION_ORDER, "wave_custody_identity_invalid")
    root = Path(out_dir).resolve()
    supplied = (root / state.population_name / name, root / name)
    for path in supplied:
        _inside(path, root)
    candidates = {
        path.resolve() for path in supplied if (path / "rows.csv").exists()
    }
    if len(candidates) > 1:
        raise WaveRefused("ambiguous population run directory for technical measurements")
    return candidates.pop() if candidates else None


def _recorded_chunk_rows(state: WaveState, chunk: Mapping[str, Any], *,
                         data_dir: Path | None, out_dir: Path | None) -> list[dict[str, str]] | None:
    """Original custody alone is authoritative; never read an ordinary export."""
    name = chunk.get("run_dir")
    _validate_storage_chunks([dict(chunk)], state.version)
    storage = chunk.get("storage")
    if "storage" in chunk:
        _export_require(state.version == STATE_VERSION and storage == PRIVATE_RUN_STORAGE and data_dir is not None,
                        "wave_custody_storage_unknown")
        _export_session(name)
        parent = _custody_run_parent(data_dir, state.partition, state.population_name)
        directory = parent / name
        resolved_directory = _inside(directory, parent, exists=True)
        rows_path, provenance_path = directory / "rows.csv", directory / "provenance.json"
        bindings = {Path(data_dir): Path(data_dir).resolve(strict=True), parent: parent,
                    directory: resolved_directory,
                    rows_path: _inside(rows_path, resolved_directory, exists=True),
                    provenance_path: _inside(provenance_path, resolved_directory, exists=True)}
        raw, provenance_raw = _closed_bytes(rows_path), _closed_bytes(provenance_path)
        _export_require(hashlib.sha256(raw).hexdigest() == chunk.get("rows_sha256")
                        and hashlib.sha256(provenance_raw).hexdigest() == chunk.get("provenance_sha256"),
                        "wave_recorded_custody_hash_mismatch")
        _export_require(_custody_run_parent(data_dir, state.partition, state.population_name) == parent,
                        "wave_custody_parent_retargeted")
        _assert_bindings(bindings)
        return _csv_records(raw)
    if not name or out_dir is None:
        return None
    directory = _recorded_run_directory(state, out_dir, name)
    if directory is None:
        return None
    rows_path = directory / "rows.csv"
    bindings = {Path(out_dir): Path(out_dir).resolve(strict=True), directory: directory,
                rows_path: _inside(rows_path, directory, exists=True)}
    raw = _closed_bytes(rows_path)
    _export_require(_recorded_run_directory(state, out_dir, name) == directory,
                    "wave_legacy_source_retargeted")
    _assert_bindings(bindings)
    return _csv_records(raw)


def _reported_refusals(state: WaveState, out_dir: Path | None, *, data_dir: Path | None = None) -> dict[str, Any]:
    # Preserve historical state. Read the exact chunk that wrote each outcome,
    # never a different population row or an earlier attempt.
    if out_dir is None and not any("storage" in chunk for chunk in state.chunks):
        historical = state.refusals_by_reason()
        for reason in historical:
            _closed_refusal(reason)
        return {"refused_by_reason": historical,
                "refusal_reason_source": "historical_state"}
    by_chunk = {chunk["index"]: chunk for chunk in state.chunks if "index" in chunk}
    rows_by_chunk: dict[int, dict[str, dict[str, str]]] = {}
    reasons: dict[str, int] = {}
    recovered = unavailable = 0
    for sha, outcome in state.documents.items():
        if outcome.outcome != OUTCOME_REFUSED:
            continue
        if outcome.chunk not in rows_by_chunk:
            source_rows = _recorded_chunk_rows(state, by_chunk.get(outcome.chunk, {}),
                                               data_dir=data_dir, out_dir=out_dir)
            rows_by_chunk[outcome.chunk] = {} if source_rows is None else {
                row["content_sha256"].upper(): row for row in source_rows
            }
        row = rows_by_chunk[outcome.chunk].get(sha.upper())
        if row is None:
            reason = "paddle_refusal_row_unavailable"
            unavailable += 1
        else:
            reason = _closed_refusal(_refusal_reason(row))
            recovered += 1
        reasons[reason] = reasons.get(reason, 0) + 1
    return {"refused_by_reason": dict(sorted(reasons.items())),
            "refusal_reason_source": "recorded_rows", "refusals_rederived": recovered,
            "refusals_without_rows": unavailable}


def _technical_measurements(state: WaveState, out_dir: Path | None, *, data_dir: Path | None = None) -> dict[str, Any]:
    """The four telemetry columns plus the local memory reading, gathered from
    the rows the chunks produced. Empty when the run directories are not
    available to this call — a measurement nobody can re-read is not reported
    as one."""
    if out_dir is None and not any("storage" in chunk for chunk in state.chunks):
        return {"telemetry": {}}
    document_ms: list[float] = []
    per_page_mean_ms: list[float] = []
    bytes_up = bytes_down = 0
    vram: list[int] = []
    rss: list[float] = []
    wall_ms: list[float] = []
    for chunk in state.chunks:
        source_rows = _recorded_chunk_rows(state, chunk, data_dir=data_dir, out_dir=out_dir)
        if source_rows is None:
            continue
        for row in source_rows:
            if not (row.get("inference_ms") or "").strip():
                continue
            for field_name in ("inference_ms", "page_count", "bytes_up", "bytes_down",
                               "vram_mb", "peak_rss_mb", "elapsed_ms"):
                value = row.get(field_name) or ""
                if value == "" or (field_name == "peak_rss_mb" and value == "not measured"):
                    continue
                _export_require(re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", value)
                                is not None and math.isfinite(float(value)),
                                "wave_report_measurement_invalid")
            total = float(row["inference_ms"])
            document_ms.append(total)
            pages = int(row.get("page_count") or 0)
            if pages > 0:
                per_page_mean_ms.append(total / pages)
            bytes_up += int(row.get("bytes_up") or 0)
            bytes_down += int(row.get("bytes_down") or 0)
            if (row.get("vram_mb") or "").strip().isdigit():
                vram.append(int(row["vram_mb"]))
            peak = (row.get("peak_rss_mb") or "").strip()
            try:
                rss.append(float(peak))
            except ValueError:
                pass
            try:
                wall_ms.append(float(row.get("elapsed_ms") or 0.0))
            except ValueError:
                pass
    return {
        "telemetry": {
            "documents_measured": len(document_ms),
            "inference_ms_per_document": _percentiles(document_ms),
            "inference_ms_per_page_mean": _percentiles(per_page_mean_ms),
            "wall_ms_per_document": _percentiles(wall_ms),
            "bytes_up_total": bytes_up,
            "bytes_down_total": bytes_down,
            "bytes_up_basis": "raw_png_payload_before_base64_and_transport_compression",
            "bytes_down_basis": "json_reserialization_estimate_before_transport_compression",
            "transport_bytes_measured": False,
            "vram_mb": _percentiles([float(value) for value in vram]),
            "peak_rss_mb": _percentiles(rss),
        }
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=PRODUCTION_CONFIG,
                        help=f"the configuration block to run (default {PRODUCTION_CONFIG})")
    parser.add_argument("--data-dir", required=True,
                        help="the research artifact cache this wave writes to; a production or "
                             "cold cache is refused")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.paddle_wave",
        description="The Phase 2.3 broad Paddle evidence wave (cell W).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    populations = sub.add_parser("populations", help="derive CTRL / U755 / SLICE from a run of record")
    populations.add_argument("--run", required=True, help="the run-of-record directory")
    populations.add_argument("--out", required=True, help="where the .shas files are written")
    populations.add_argument("--seed", default=DEFAULT_SEED)
    populations.add_argument("--ctrl-target", type=int, default=DEFAULT_CTRL_TARGET)

    preflight = sub.add_parser("preflight", help="every door, and nothing else")
    preflight.add_argument("--population", required=True)
    preflight.add_argument("--population-name", default=None)
    preflight.add_argument("--populations-dir", default=None)
    _add_common(preflight)

    run = sub.add_parser("run", help="read the population through the research mode, resumably")
    run.add_argument("--population", required=True)
    run.add_argument("--population-name", default=None)
    run.add_argument("--populations-dir", default=None)
    run.add_argument("--out", required=True, help="fresh ordinary technical exports; original runs stay in research custody")
    run.add_argument("--root", required=True, help="the archive root")
    run.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    run.add_argument("--max-chunks", type=int, default=None)
    run.add_argument("--no-retain-rasters", action="store_true")
    run.add_argument("--no-lifecycle", action="store_true",
                     help="do not bring the instance up or down (an already-running worker)")
    run.add_argument("--log", default=None)
    _add_common(run)

    report = sub.add_parser("report", help="what the wave produced")
    report.add_argument("--populations-dir", default=None)
    report.add_argument("--out", default=None, help="explicit historical raw run root for markerless legacy chunks")
    report.add_argument("--json", dest="json_out", default=None)
    _add_common(report)

    export = sub.add_parser("export", help="project one explicitly bound closed run, without OCR")
    export.add_argument("--run", required=True)
    export.add_argument("--out", required=True)
    export.add_argument("--population-name", required=True, choices=POPULATION_ORDER)
    export.add_argument("--source-rows-sha256", required=True)
    export.add_argument("--source-provenance-sha256", required=True)
    export.add_argument("--session", required=True)
    _add_common(export)

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except WaveRefused as exc:
        print(f"paddle_wave: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        if args.command not in ("export", "report"):
            raise
        print("paddle_wave: wave_export_or_report_invalid", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "export":
        _export_require(args.config in CONFIGURATIONS, "wave_export_configuration_invalid")
        partition = CONFIGURATIONS[args.config]["partition"]
        refuse_a_production_data_dir(Path(args.data_dir))
        _disjoint(Path(args.data_dir), Path(args.out))
        write_wave_technical_export(
            Path(args.run), Path(args.out), configuration=args.config, partition=partition,
            population_name=args.population_name, expected_source_rows_sha256=args.source_rows_sha256,
            expected_source_provenance_sha256=args.source_provenance_sha256,
            expected_session=args.session,
        )
        print(json.dumps({"status": "complete", "population": args.population_name,
                          "configuration": args.config, "schema_version": EXPORT_SCHEMA_VERSION}))
        return 0
    if args.command == "populations":
        derived = derive_populations(Path(args.run), seed=args.seed, ctrl_target=args.ctrl_target)
        for name in POPULATION_ORDER:
            refuse_holdout_members(derived[name]["shas"])
        digests = write_population_files(
            derived, Path(args.out), run_dir=Path(args.run), seed=args.seed,
        )
        for name in POPULATION_ORDER:
            entry = digests[name]
            print(f"{name}: documents={entry['documents']} "
                  f"file_sha256={entry['file_sha256']} set_sha256={entry['set_sha256']}")
            print(f"    {derived[name]['note']}")
        return 0

    population_arg = getattr(args, "population", None)
    name = getattr(args, "population_name", None) or (
        Path(population_arg).stem if population_arg else ""
    )
    if getattr(args, "populations_dir", None):
        populations_dir = Path(args.populations_dir)
    elif population_arg:
        populations_dir = Path(population_arg).parent
    else:
        populations_dir = Path(args.data_dir)

    if args.command == "preflight":
        require_opt_in()
        block = resolve_configuration(args.config)
        refuse_a_production_data_dir(Path(args.data_dir))
        population = read_population_file(Path(args.population))
        refuse_holdout_members(population)
        digests = population_digests(Path(args.population))
        predecessors = refuse_out_of_order(
            name, data_dir=Path(args.data_dir), partition=block["partition"],
            populations_dir=populations_dir,
        )
        print(json.dumps({
            "population": name, "documents": len(population), "config": args.config,
            "partition": block["partition"], "predecessors_complete": predecessors,
            **digests,
        }, indent=2, sort_keys=True))
        return 0

    if args.command == "run":
        from ocr.paddle_config import load_paddle_settings

        log = WaveLog(Path(args.log) if args.log else None)
        lifecycle = None
        if not args.no_lifecycle:
            settings = load_paddle_settings()
            log.bind(settings)
            lifecycle = Lifecycle(settings=settings, log=log)
        result = run_wave(
            population_file=Path(args.population), population_name=name,
            populations_dir=populations_dir, config=args.config, data_dir=Path(args.data_dir),
            out_dir=Path(args.out), root=Path(args.root), chunk_size=args.chunk_size,
            max_chunks=args.max_chunks, retain_rasters=not args.no_retain_rasters,
            lifecycle=lifecycle, log=log,
        )
        attestation = result["attestation"]
        if attestation is not None and not attestation["passed"]:
            print("paddle_wave: the retention attestation did NOT pass", file=sys.stderr)
            return 3
        return 0

    if args.command == "report":
        report = wave_report(
            data_dir=Path(args.data_dir), config=args.config,
            populations_dir=populations_dir if getattr(args, "populations_dir", None) else None,
            out_dir=Path(args.out) if args.out else None,
        )
        rendered = json.dumps(report, indent=2, sort_keys=True)
        print(rendered)
        if args.json_out:
            Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_out).write_text(rendered + "\n", encoding="utf-8")
        return 0

    raise WaveRefused(f"unknown command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
