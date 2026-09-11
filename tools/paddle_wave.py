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
import json
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
    "retain_rasters_for",
    "wave_report",
]


class WaveRefused(RuntimeError):
    """Every refusal this tool makes. Carries a reason a human can act on and
    never a connection value, a document's contents or a sha with a verdict."""


# ---------------------------------------------------------------------------
# Configurations. Cell V owns the named configuration BLOCKS in
# `ocr/paddle_config.py`; this cell runs the production block only, and names
# the others so an operator who asks for one is told where they live rather
# than silently given the production pins under another partition's name.
# ---------------------------------------------------------------------------

PRODUCTION_CONFIG = "paddle-v5-prod"

#: `name -> (research partition id, what it is)`. The partition id is OCR-key
#: material and must match `RESEARCH_PARTITION_PATTERN`, which admits no `/`
#: — so the umbrella card's `research/paddle-v5-prod` is spelled with a hyphen
#: here, deliberately and once.
CONFIGURATIONS: dict[str, dict[str, str]] = {
    PRODUCTION_CONFIG: {
        "partition": "research-paddle-v5-prod",
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

STATE_VERSION = 1

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
        if payload.get("version") != STATE_VERSION:
            raise WaveRefused(
                f"wave state {path} is version {payload.get('version')!r}, this tool writes "
                f"{STATE_VERSION}; refusing to resume a state it may not understand"
            )
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
    #: directory, which this pipeline is the only writer of.
    temp_image_files: int = 0
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


#: The remote inspection, as ONE `sh` command producing `KEY=<integer>` lines.
#: It counts; it never lists. A name from the instance's filesystem must not
#: reach a log on this machine, and a count answers the question the
#: attestation actually asks.
_ATTESTATION_COMMAND = (
    "D={directory}; "
    "echo PROC=$(ps -eo args 2>/dev/null | grep -c '[p]addle_worker.py'); "
    "echo PIDFILE=$([ -f $D/worker.pid ] && echo 1 || echo 0); "
    "echo IMAGES=$(find $D -type f "
    "\\( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.pdf' -o -name '*.b64' "
    "-o -name '*.npy' \\) 2>/dev/null | wc -l); "
    "echo REQUESTS=$(find $D -type f "
    "\\( -name '*.json' -o -name 'request*' -o -name '*.tmp' -o -name '*.part' \\) "
    "2>/dev/null | wc -l); "
    "echo OTHER=$(find $D -maxdepth 1 -type f ! -name 'paddle_worker.py' ! -name 'worker.log' "
    "2>/dev/null | wc -l); "
    "echo TMPIMG=$(find /tmp -maxdepth 2 -type f "
    "\\( -name '*.png' -o -name '*.pdf' \\) 2>/dev/null | wc -l)"
)


def _parse_attestation_output(text: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\s*([A-Z]+)=(\d+)\s*", line)
        if match:
            values[match.group(1)] = int(match.group(2))
    return values


def attest_retention(
    settings: Any, *, runner: Callable[..., Any] | None = None, retention_declared: bool,
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
    """
    import tools.paddle_vast as vast

    if runner is None:
        runner = subprocess.run
    command = _ATTESTATION_COMMAND.format(directory=vast.REMOTE_WORKER_DIR)
    try:
        completed = vast._run(
            runner, vast._ssh_command(settings, command),
            capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:  # noqa: BLE001 - the class name only; never the message
        return RetentionAttestation(
            retention_declared=retention_declared, inspected=False, worker_process_alive=True,
            pidfile_present=True, request_artefacts=-1, page_byte_files=-1, unexpected_files=-1,
            error=type(exc).__name__,
        )
    if getattr(completed, "returncode", 1) != 0:
        return RetentionAttestation(
            retention_declared=retention_declared, inspected=False, worker_process_alive=True,
            pidfile_present=True, request_artefacts=-1, page_byte_files=-1, unexpected_files=-1,
            error="remote_inspection_failed",
        )
    values = _parse_attestation_output(vast.mask_text(completed.stdout or "", settings))
    required = ("PROC", "PIDFILE", "IMAGES", "REQUESTS", "OTHER")
    if any(name not in values for name in required):
        return RetentionAttestation(
            retention_declared=retention_declared, inspected=False, worker_process_alive=True,
            pidfile_present=True, request_artefacts=-1, page_byte_files=-1, unexpected_files=-1,
            error="remote_inspection_incomplete",
        )
    return RetentionAttestation(
        retention_declared=retention_declared,
        inspected=True,
        worker_process_alive=values["PROC"] > 0,
        pidfile_present=values["PIDFILE"] > 0,
        request_artefacts=values["REQUESTS"],
        page_byte_files=values["IMAGES"],
        unexpected_files=values["OTHER"],
        temp_image_files=values.get("TMPIMG", 0),
    )


# ---------------------------------------------------------------------------
# Rasters (D2, card item 6)
# ---------------------------------------------------------------------------

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
    """
    from io import BytesIO

    from evidence.canonical import from_json
    from ocr.rasterize import rasterize_page
    from webapp.artifact_cache import ocr_settings_key, open_cache

    if not partition:
        raise WaveRefused("retain_rasters_for refuses an empty research partition")
    cache = open_cache(Path(data_dir))
    key = ocr_settings_key(
        force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False, allow_paddle_ocr=True,
        research_partition=partition,
    )
    hit, record = cache.get_ocr(sha.upper(), key)
    if not hit or not record or not record.get("evidence"):
        return {"written": 0, "mismatched": 0, "pages": 0, "skipped_no_evidence": 1}
    evidence = from_json(record["evidence"])
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
    """The reason THIS document produced no evidence, from the row's own
    closed vocabularies, most specific first. Never a message, never a path."""
    for name in ("paddle_refusal_reason", "error_type", "outcome_reason"):
        value = (row.get(name) or "").strip()
        if value:
            return value
    return "unrecorded"


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
    return fresh[-1] if fresh else None


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

    def down(self, *, retention_declared: bool) -> RetentionAttestation:
        import tools.paddle_vast as vast

        vast.cmd_stop(self.settings)
        self.log("lifecycle.stop")
        attestation = attest_retention(self.settings, retention_declared=retention_declared)
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
    state.version = STATE_VERSION
    state.config, state.partition, state.population_name = config, partition, population_name
    state.population_file_sha256 = digests["file_sha256"]
    state.population_set_sha256 = digests["set_sha256"]
    state.save(state_path)

    pending = state.pending(population)
    log("wave.pending", population=population_name, pending=len(pending),
        already_evidence=state.counts()["evidence"])

    session: dict[str, Any] = {
        "started": _now(), "population": population_name, "config": config,
        "partition": partition, "chunks": 0, "documents": 0,
    }
    attestation: RetentionAttestation | None = None
    retention_declared = False
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
            processed = _run_one_chunk(
                chunk=chunk, chunk_index=chunk_index, state=state, state_path=state_path,
                partition=partition, data_dir=data_dir, out_dir=Path(out_dir), root=Path(root),
                retain_rasters=retain_rasters, log=log, runner=runner,
                skip_baseline=skip_baseline,
            )
            session["chunks"] += 1
            session["documents"] += processed
            chunk_index += 1
    finally:
        if lifecycle is not None:
            attestation = lifecycle.down(retention_declared=retention_declared)
            session["attestation"] = attestation.as_record()
        session["ended"] = _now()
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
    out_dir.mkdir(parents=True, exist_ok=True)
    before = {path for path in out_dir.iterdir() if path.is_dir()}
    argv = _discovery_argv(population_file=chunk_file, partition=partition, data_dir=data_dir,
                            out_dir=out_dir, root=root, skip_baseline=skip_baseline)
    started = time.perf_counter()
    log("chunk.start", chunk=chunk_index, documents=len(chunk))
    completed = runner(argv, cwd=str(ROOT), capture_output=True, text=True,
                       env=_chunk_environment(data_dir))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    run_dir = _new_run_dir(out_dir, before)
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

    rows = {row["content_sha256"].upper(): row for row in _rows_of(run_dir)}
    wanted = {sha.upper() for sha in chunk}
    processed = 0
    rasters = {"written": 0, "mismatched": 0}
    for sha in sorted(wanted):
        row = rows.get(sha)
        if row is None:
            # D4: a document of the named population that produced no row at
            # all is a REFUSAL with its own reason, never a silent hole.
            state.record(sha, DocumentOutcome(
                outcome=OUTCOME_REFUSED, reason="no_row_produced", pages=0,
                chunk=chunk_index, at=_now(),
            ))
            processed += 1
            continue
        pages = int(row.get("page_count") or 0)
        if row.get("stage_evidence") == "present" and row.get("source_path") == "paddle":
            state.record(sha, DocumentOutcome(outcome=OUTCOME_EVIDENCE, reason="", pages=pages,
                                              chunk=chunk_index, at=_now()))
            if retain_rasters:
                counts = retain_rasters_for(
                    sha, pdf_bytes=(Path(root) / row["relative_path"]).read_bytes(),
                    data_dir=data_dir, partition=partition,
                )
                rasters["written"] += counts["written"]
                rasters["mismatched"] += counts["mismatched"]
        else:
            state.record(sha, DocumentOutcome(outcome=OUTCOME_REFUSED, reason=_refusal_reason(row),
                                              pages=pages, chunk=chunk_index, at=_now()))
        processed += 1
    cache_hits = sum(1 for sha in wanted
                     if rows.get(sha, {}).get("cache_paddle") == "hit")
    state.chunks.append({
        "index": chunk_index, "documents": len(chunk), "status": "complete",
        "run_dir": run_dir.name, "elapsed_ms": elapsed_ms, "cache_hits": cache_hits,
        "rasters_written": rasters["written"], "rasters_mismatched": rasters["mismatched"],
    })
    state.save(state_path)
    log("chunk.end", chunk=chunk_index, documents=processed, cache_hits=cache_hits,
        rasters_written=rasters["written"], rasters_mismatched=rasters["mismatched"],
        elapsed_ms=elapsed_ms, run_dir=run_dir.name)
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
        counts = state.counts()
        entry: dict[str, Any] = {
            "population_set_sha256": state.population_set_sha256,
            "attempted": counts["attempted"],
            "evidence": counts["evidence"],
            "refused": counts["refused"],
            "pages_evidence": counts["pages_evidence"],
            "pages_refused": counts["pages_refused"],
            "pages_attempted": counts["pages_evidence"] + counts["pages_refused"],
            "refused_by_reason": state.refusals_by_reason(),
            "cache_hits": sum(int(chunk.get("cache_hits") or 0) for chunk in state.chunks),
            "rasters_written": sum(int(chunk.get("rasters_written") or 0) for chunk in state.chunks),
            "rasters_mismatched": sum(int(chunk.get("rasters_mismatched") or 0)
                                      for chunk in state.chunks),
            "chunks": len(state.chunks),
            "sessions": len(state.sessions),
        }
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
        entry.update(_technical_measurements(state, out_dir))
        for session in state.sessions:
            if session.get("attestation"):
                report["attestations"].append({"population": name, **session["attestation"]})
        report["populations"][name] = entry
    return report


def _technical_measurements(state: WaveState, out_dir: Path | None) -> dict[str, Any]:
    """The four telemetry columns plus the local memory reading, gathered from
    the rows the chunks produced. Empty when the run directories are not
    available to this call — a measurement nobody can re-read is not reported
    as one."""
    if out_dir is None:
        return {"telemetry": {}}
    document_ms: list[float] = []
    per_page_mean_ms: list[float] = []
    bytes_up = bytes_down = 0
    vram: list[int] = []
    rss: list[float] = []
    wall_ms: list[float] = []
    for chunk in state.chunks:
        name = chunk.get("run_dir")
        if not name:
            continue
        run_dir = Path(out_dir) / name
        if not (run_dir / "rows.csv").exists():
            continue
        for row in _rows_of(run_dir):
            if not (row.get("inference_ms") or "").strip():
                continue
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
    run.add_argument("--out", required=True, help="where each chunk's discovery run lands")
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
    report.add_argument("--out", default=None, help="the run directory the chunks wrote into")
    report.add_argument("--json", dest="json_out", default=None)
    _add_common(report)

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except WaveRefused as exc:
        print(f"paddle_wave: {exc}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
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
