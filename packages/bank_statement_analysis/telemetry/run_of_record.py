"""One artifact-selection policy for a discovery run, used by
``telemetry/stated_counts.py::_ArtifactJoin``.

Why this exists
---------------
Readers of the artifact-cache index must not guess which artifact a run used:
``rows[0]`` with no ``ORDER BY``, or a preference order over partitions, is
correct only while every input holds exactly one artifact per stage. The rule
(ruling OQ10): **historical truth follows the artifact the official run
actually consumed**, never ``rows[0]``, never a preference order, never
database order. This module is that one policy.

The three primitives
---------------------
:func:`partitions_for_run`
    ``run_dir -> RunPartitions``: what a run of record actually consumed,
    either RECORDED (``tools/train/provenance.py``) or deterministically
    RECONSTRUCTED from what an older run recorded about itself
    (``OCR_STAGE_VERSION``, ``ANALYSIS_STAGE_VERSION``,
    ``analysis_settings_key_deterministic``, its env, and its ``mode`` from
    ``summary.json``). A reconstruction is VERIFIED against the cache it was
    built to describe (:func:`verify_reconstruction`) — a key it names must
    actually be in the index, or the reconstruction is a wrong guess, never
    served. See :class:`RunOfRecordError`.
:func:`ocr_partition_for_row` / :func:`analysis_partition`
    ``(row, partitions) -> settings_key | None``: which of a run's partitions
    ONE document's row actually named. Never a preference walk — the row
    itself says (``source_path`` / ``visual_rung`` for OCR; the run's one
    recorded analysis key for analysis).
:func:`select_artifact`
    ``(conn, stage, input_sha256, settings_key) -> artifact_path | None``: the
    exact, single row the composed key names. The table's primary key is
    ``(stage, cache_key)`` and ``cache_key`` is a pure function of
    ``(stage, input, settings)``, so an honest index can never hold two rows
    for one ``(stage, input_sha256, settings_key)`` triple — seeing two is a
    corrupt index, a finding rather than a choice, and this raises rather
    than picking one.

A row naming a partition the cache does not hold (an OCR-stage miss because
no artifact was ever written under a key nothing else in the run used, or a
row from a fingerprint the cache never saw) resolves to ``None`` — never to
another partition. That is the whole point: NEVER a fallback, NEVER a guess.

Research partitions
--------------------------------------------------
The OCR settings key carries ``research_partition`` (empty for production;
``webapp/artifact_cache.py::ocr_settings_key``). A run whose RECORDED
partitions block names a non-empty one is a research run and this module
REFUSES it outright (:class:`ResearchPartitionRefused`, naming the
partition) before any key is read — a research artifact can never become
historical truth, whichever reader asks. A production run (the field empty
or absent) is selected exactly as before.

Kept out of this module by design
---------------------------------
No page-level partitions, no ``page_extractor``. No writes: every
function here is a pure read over an already-written index. No import of
``webapp``, ``ocr``, ``analysis`` or ``discovery`` at MODULE level — every one
of those is imported LAZILY, inside a function, the same discipline
``telemetry/stated_counts.py::_ArtifactJoin`` already keeps, so that a plain
``import telemetry.run_of_record`` (and therefore
``import telemetry.stated_counts``) never drags in the webapp/ocr/analysis
stack and never risks a circular import through ``discovery.runner`` (which
itself imports ``telemetry`` at module level).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "ORIGIN_RECORDED",
    "ORIGIN_RECONSTRUCTED",
    "ResearchPartitionRefused",
    "RunOfRecordError",
    "RunPartitions",
    "partitions_for_run",
    "verify_reconstruction",
    "ocr_partition_for_row",
    "analysis_partition",
    "select_artifact",
]

#: A run whose ``provenance.json`` carries its own ``run_of_record.partitions``
#: block (written by ``tools/train/provenance.py`` from THIS cell forward).
ORIGIN_RECORDED = "recorded"
#: A run predating that record (batch 8, batch 9): partitions are
#: deterministically derived from what it DID record and then verified
#: against its own cache index.
ORIGIN_RECONSTRUCTED = "reconstructed"

#: Row-level vocabulary values that mean "the visual rung produced this
#: document's text" (``discovery/runner.py``: ``VISUAL_RECOVERED`` /
#: ``VISUAL_UPGRADED``). Duplicated here as literals rather than imported —
#: unlike the ladder-mode constants below, these two are `telemetry`'s own
#: read of a CSV column already published as a stable row vocabulary
#: (``discovery/report.py``), not a computation this module must never
#: re-derive; importing ``discovery.runner`` at all is done lazily and only
#: where its actual policy constant (``LOCAL_OCR_MODES``) is load-bearing.
_VISUAL_ROW_OUTCOMES = frozenset({"recovered", "upgraded"})

#: The SAME shape, for the Paddle rung's own row column
#: (``discovery/report.py``'s ``paddle_rung``). A row can carry
#: `recovered`/`upgraded` in AT MOST ONE of ``visual_rung`` / ``paddle_rung`` (a
#: mode enables exactly one escalation extractor — D4), so the two partitions
#: are mutually exclusive per row by construction, never by a precedence rule
#: this module would have to enforce.
_PADDLE_ROW_OUTCOMES = frozenset({"recovered", "upgraded"})


class RunOfRecordError(RuntimeError):
    """Fail-closed. Raised when:

    * a run's ``provenance.json`` / ``summary.json`` is missing a field a
      reconstruction needs;
    * a run's ``provenance.json`` carries a ``run_of_record`` block that is
      present but malformed (never silently falls back to reconstruction —
      a half-written record is a defect to surface, not paper over);
    * a RECONSTRUCTED key does not appear in the cache it was built to
      describe (:func:`verify_reconstruction`);
    * :func:`select_artifact` finds more than one row for one
      ``(stage, input_sha256, settings_key)`` triple (a corrupt index).

    CLI callers turn this into exit 5. Never a
    guess, never a silent fallback.
    """


class ResearchPartitionRefused(RunOfRecordError):
    """A run whose recorded OCR
    settings key carries a non-empty ``research_partition`` is a RESEARCH
    run: its artifacts were written under a research partition (Phase 2.3's
    broad Paddle wave, or any later research mode) and can never become
    historical truth. This module refuses to select any artifact of such a
    run — the refusal names the partition — so
    ``telemetry.stated_counts._ArtifactJoin`` (which goes through
    :func:`partitions_for_run`) can never replay, compare or count against it.
    A ``RunOfRecordError`` subclass, so every existing exit-5 boundary
    honours it unchanged."""

    def __init__(self, partition: str, run_dir: Path | str) -> None:
        self.partition = partition
        super().__init__(
            f"{run_dir}/provenance.json: run_of_record.partitions.research_partition is "
            f"{partition!r} — a research partition is never selectable as a run of record; refused"
        )


@dataclass(frozen=True)
class RunPartitions:
    """What a run of record actually consumed.

    ``ocr_keys_by_source`` maps a row's OCR provenance label to the settings
    key that produced it: ``"native"`` and ``"local_tesseract"`` share ONE
    value (the offline ladder's settings key does not distinguish which rung
    inside it actually claimed — ``allow_local_ocr`` is a per-RUN constant,
    not a per-document one), and ``"visual"`` is a second, independent value.
    A source absent from this mapping (there is never a ``"none"`` entry —
    ``source_path=none`` means the run produced no OCR text for that document
    at all) resolves to ``None`` via :func:`ocr_partition_for_row`.
    """

    ocr_keys_by_source: Mapping[str, str]
    analysis_key: str
    ocr_stage_version: int
    analysis_stage_version: int
    mode: str
    origin: str
    #: The research partition the run's OCR keys carry. Always ``""`` on an
    #: object this module builds — a non-empty value is refused before
    #: construction (:class:`ResearchPartitionRefused`) — and recorded here so
    #: the fact is on the object, not only in the refusal.
    research_partition: str = ""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise RunOfRecordError(f"cannot read {path}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise RunOfRecordError(f"{path} does not hold a JSON object")
    return data


def _recorded_partitions(run_dir: Path, provenance: dict[str, Any]) -> RunPartitions | None:
    """``None`` when the run predates recording; raises when the record is
    PRESENT but malformed (a half-written block is a defect, never a silent
    invitation to reconstruct instead).

    Review MAJOR-1/the recorded ``mode`` is cross-checked against the run's OWN
    ``summary.json:mode`` when the latter exists (it always does for a real run
    of record — ``tools/train/provenance.py`` is invoked a second time, into the
    run directory, only after the run itself completed and wrote
    ``summary.json``). A disagreement means the ``--mode`` an operator passed to
    ``provenance.py`` does not match what the run actually did — a typo, most
    likely — and the record is refused rather than silently trusted."""
    block = provenance.get("run_of_record")
    if block is None:
        return None
    partitions = block.get("partitions") if isinstance(block, dict) else None
    if not isinstance(partitions, dict):
        raise RunOfRecordError(
            f"{run_dir}/provenance.json: 'run_of_record' present but its "
            "'partitions' block is missing or not an object"
        )
    offline_key = partitions.get("offline_ocr_key")
    analysis_key = partitions.get("analysis_key")
    mode = partitions.get("mode")
    visual_key = partitions.get("visual_ocr_key")
    paddle_key = partitions.get("paddle_ocr_key")
    for name, value in (("offline_ocr_key", offline_key), ("analysis_key", analysis_key), ("mode", mode)):
        if not isinstance(value, str) or not value:
            raise RunOfRecordError(
                f"{run_dir}/provenance.json: run_of_record.partitions.{name} "
                "missing or empty"
            )
    # The research partition is refused BEFORE any key is read into a
    # `RunPartitions` — a run recorded before the field existed (no key at all)
    # and a production run (the empty string) are the same fact; anything
    # non-empty is a research run and never a run of record.
    research_partition = partitions.get("research_partition", "")
    if research_partition is None:
        research_partition = ""
    if not isinstance(research_partition, str):
        raise RunOfRecordError(
            f"{run_dir}/provenance.json: run_of_record.partitions.research_partition "
            "is not a string"
        )
    if research_partition:
        raise ResearchPartitionRefused(research_partition, run_dir)
    summary_path = run_dir / "summary.json"
    if summary_path.is_file():
        summary_mode = _load_json(summary_path).get("mode")
        if isinstance(summary_mode, str) and summary_mode and summary_mode != mode:
            raise RunOfRecordError(
                f"{run_dir}/provenance.json: run_of_record.partitions.mode "
                f"({mode!r}) disagrees with {run_dir}/summary.json:mode "
                f"({summary_mode!r}) — refused rather than silently trusted"
            )
    ocr_keys_by_source = {"native": offline_key, "local_tesseract": offline_key}
    if isinstance(visual_key, str) and visual_key:
        ocr_keys_by_source["visual"] = visual_key
    # `paddle_ocr_key` is OPTIONAL, like `visual_ocr_key` — a run recorded
    # before this cell, or one whose Paddle settings did not load at provenance
    # time, simply has no Paddle partition, and a `paddle_rung` row on such a
    # run resolves to `None` via `ocr_partition_for_row` (never a fallback to
    # another partition).
    if isinstance(paddle_key, str) and paddle_key:
        ocr_keys_by_source["paddle"] = paddle_key
    tree = provenance.get("tree") if isinstance(provenance.get("tree"), dict) else {}
    return RunPartitions(
        ocr_keys_by_source=ocr_keys_by_source,
        analysis_key=analysis_key,
        ocr_stage_version=int(tree.get("OCR_STAGE_VERSION", -1)),
        analysis_stage_version=int(tree.get("ANALYSIS_STAGE_VERSION", -1)),
        mode=mode,
        origin=ORIGIN_RECORDED,
    )


def _env_str(env: Mapping[str, Any], key: str, default: str) -> str:
    value = env.get(key)
    return default if value in (None, "") else str(value)


#: The retired ``ocr.config.load_settings``'s own literal fallbacks (deleted
#: with the visual OCR client in slice S2 of the model-code removal; the same
#: four values are frozen key material in
#: ``webapp.artifact_cache.FROZEN_OCR_SETTINGS``), duplicated deliberately
#: rather than called: ``load_settings()`` read the CALLING
#: process's CURRENT environment, and this function reconstructs a
#: HISTORICAL run's settings from that run's RECORDED environment
#: (``tools/train/provenance.py``'s ``ENV_KNOBS``) — calling it here would let
#: whatever happens to be set in the environment doing the reconstruction
#: (a developer's shell, a CI job) silently override the run's own recorded
#: absence of the knob. A knob change in ``ocr/config.py`` (not owned here)
#: would only matter to a NEW run recording its OWN partitions (item 3 of the
#: card) — reconstruction only ever serves batch-8/9-era runs frozen before
#: this cell existed, so this literal pair can never drift out from under a
#: run this module will actually reconstruct.
_OCR_MODEL_DEFAULT = "baidu/Unlimited-OCR"
_OCR_BASE_URL_DEFAULT = "http://localhost:8000/v1"
_OCR_NGRAM_SIZE_DEFAULT = "35"
_OCR_WINDOW_SIZE_DEFAULT = "128"


def _reconstructed_ocr_settings(env: Mapping[str, Any]):
    """A duck-typed stand-in for the retired ``ocr.config.Settings`` built from
    a run's RECORDED environment, falling back to ``load_settings()``'s own
    literal defaults (see above) for a knob the record shows unset. Read by
    ``ocr_settings_key`` attribute by attribute, exactly as before S2."""
    return type(
        "ReconstructedOcrSettings",
        (),
        {
            "model": _env_str(env, "OCR_MODEL", _OCR_MODEL_DEFAULT),
            "base_url": _env_str(env, "OCR_BASE_URL", _OCR_BASE_URL_DEFAULT),
            "ngram_size": int(_env_str(env, "OCR_NGRAM_SIZE", _OCR_NGRAM_SIZE_DEFAULT)),
            "window_size": int(_env_str(env, "OCR_WINDOW_SIZE", _OCR_WINDOW_SIZE_DEFAULT)),
        },
    )()


def _reconstruct_partitions(run_dir: Path, provenance: dict[str, Any]) -> RunPartitions:
    from discovery.runner import LOCAL_OCR_MODES  # lazy: see module docstring
    from webapp.artifact_cache import ocr_settings_key

    tree = provenance.get("tree")
    if not isinstance(tree, dict):
        raise RunOfRecordError(f"{run_dir}/provenance.json has no 'tree' block")
    ocr_stage_version = tree.get("OCR_STAGE_VERSION")
    analysis_stage_version = tree.get("ANALYSIS_STAGE_VERSION")
    analysis_key = tree.get("analysis_settings_key_deterministic")
    if not isinstance(ocr_stage_version, int):
        raise RunOfRecordError(
            f"{run_dir}/provenance.json: tree.OCR_STAGE_VERSION missing or not an int"
        )
    if not isinstance(analysis_stage_version, int):
        raise RunOfRecordError(
            f"{run_dir}/provenance.json: tree.ANALYSIS_STAGE_VERSION missing or not an int"
        )
    if not isinstance(analysis_key, str) or not analysis_key:
        raise RunOfRecordError(
            f"{run_dir}/provenance.json: tree.analysis_settings_key_deterministic missing"
        )

    summary = _load_json(run_dir / "summary.json")
    mode = summary.get("mode")
    if not isinstance(mode, str) or not mode:
        raise RunOfRecordError(f"{run_dir}/summary.json: 'mode' missing or empty")

    env = provenance.get("env")
    env = env if isinstance(env, dict) else {}
    ocr_settings = _reconstructed_ocr_settings(env)
    allow_local_ocr = mode in LOCAL_OCR_MODES

    offline_key = ocr_settings_key(
        force_ocr=False,
        allow_local_ocr=allow_local_ocr,
        allow_visual_ocr=False,
        stage_version=ocr_stage_version,
        ocr_settings=ocr_settings,
    )
    visual_key = ocr_settings_key(
        force_ocr=True,
        allow_local_ocr=False,
        allow_visual_ocr=True,
        stage_version=ocr_stage_version,
        ocr_settings=ocr_settings,
    )
    return RunPartitions(
        ocr_keys_by_source={"native": offline_key, "local_tesseract": offline_key, "visual": visual_key},
        analysis_key=analysis_key,
        ocr_stage_version=ocr_stage_version,
        analysis_stage_version=analysis_stage_version,
        mode=mode,
        origin=ORIGIN_RECONSTRUCTED,
    )


def partitions_for_run(run_dir: str | Path, *, conn: Any | None = None) -> RunPartitions:
    """The run of record's partitions: RECORDED if its ``provenance.json``
    says so, else deterministically RECONSTRUCTED and, when ``conn`` is given
    (an open connection to the cache the run's artifacts live in), VERIFIED
    against it — see :func:`verify_reconstruction`. Pass ``conn`` at every
    real call site; it is optional only so a caller that has not opened the
    cache yet can still inspect a run's declared mode/versions.
    """
    run_dir = Path(run_dir)
    provenance = _load_json(run_dir / "provenance.json")
    partitions = _recorded_partitions(run_dir, provenance)
    if partitions is None:
        partitions = _reconstruct_partitions(run_dir, provenance)
    if conn is not None:
        verify_reconstruction(partitions, conn, run_dir)
    return partitions


def verify_reconstruction(partitions: RunPartitions, conn: Any, run_dir: str | Path) -> None:
    """Review verified for EVERY origin, RECORDED included.

    A RECORDED run's keys come from an operator-supplied ``--mode`` on
    ``tools/train/provenance.py`` and are not otherwise cross-checked (the
    ``mode``-vs-``summary.json`` disagreement check lives in
    :func:`_recorded_partitions`, which runs unconditionally for a RECORDED
    block; this function is the SECOND, cache-facing half of that same
    "recording is not proof" principle) — the premise *"a RECORDED run's own
    keys are, by construction, exactly what it wrote"* is false the moment a
    human fat-fingers ``--mode``, and this cell's own proof floor never
    exercised that path because every run it measured predates recording.

    Two checks, for BOTH origins:

    1. **EXISTENCE.** The offline OCR key and the analysis key must each
       appear SOMEWHERE in the cache's index for their stage — cheap, and it
       catches a typo'd or wholly stale key.
    2. **CORRESPONDENCE.** Existence alone is not enough on a multi-partition
       archive: a key can exist in the index and still be the WRONG
       partition for THIS run (measured: a run whose declared/reconstructed
       offline key exists in the cache under a DIFFERENT tranche's artifacts
       resolves that other tranche's text silently). A bounded sample — the
       first 50 of the run's own rows whose ``source_path`` is ``native`` or
       ``local_tesseract`` (their own provenance already says text was
       read) — must resolve an artifact under the offline key for its own
       ``content_sha256`` on at least :data:`_CORRESPONDENCE_MIN_RESOLVED_FRACTION`
       (90%) of the sample, or the record is refused (review a
       weaker "resolves at least one" bound closed the reproduced 0-of-N
       failure but let a 1-of-N accident through unchallenged). This is a
       SUPERMAJORITY, not "resolves all": measured directly against the
       train9 archive (every ``native``/``local_tesseract`` row, not just a
       sample), **3,476 of 3,476 offline rows resolve their own sha under
       the archive's one offline key — 100%**. The archive supports "resolves
       all" outright; 90% is a deliberate SAFETY MARGIN below that measured
       ceiling, for a hypothetical future archive with genuine partial
       coverage, not evidence that one exists today. (An EARLIER version of
       this docstring cited the OCR cache's own "3,364 inputs / 3,380 run
       shas" count as if it were that evidence — it is not: 3,380 minus the
       29 shas whose ``source_path`` is ``none`` throughout (no offline read
       was ever attempted, so :func:`_sample_offline_rows` already excludes
       them) is 3,351 offline shas, every one cached, plus 13 cached
       NEGATIVE/deferred OCR results (a real cached fact, not a miss) is
       3,364. That arithmetic describes documents this sample never looks
       at in the first place, not a gap in the ones it does.)

       **A residual this bound does NOT close, stated honestly rather than
       silently accepted:** a resolution-RATE check cannot distinguish two
       tranches that each fully cover the sampled documents. If a wrong
       tranche happens to hold an artifact for EVERY document the sample
       looks at (not just the ones the correct tranche holds), the wrong
       key resolves 100% of the sample too, and this check cannot tell them
       apart — proven, not merely asserted, by
       ``test_correspondence_cannot_tell_two_full_tranches_apart`` below.
       Unreachable on either frozen cold cache (re-verified: each holds
       exactly one OCR settings key), and strictly narrower than the defect
       this whole module replaces (there, EVERY reconstruction was exposed
       to it; here, only a wrong tranche that happens to duplicate the
       correct tranche's exact coverage is) — closing it needs a check that
       can tell two artifacts APART (e.g. by content or by provenance
       metadata), which is a different instrument than "does something
       exist here", and is out of this card's scope.

    The VISUAL key is exempt from both: a run whose visual rung never fired
    (batch 8, batch 9 — ``visual_rung = not_attempted`` on every row)
    legitimately has ZERO rows under it, and that absence is the documented,
    expected state, not a defect (a row that names the visual partition
    still resolves correctly to ``None`` via :func:`select_artifact` on such
    a cache — a miss, never a guess at another partition)."""
    run_dir = Path(run_dir)
    offline_key = partitions.ocr_keys_by_source.get("native") or partitions.ocr_keys_by_source.get(
        "local_tesseract"
    )
    _require_key_in_cache(conn, "ocr", offline_key)
    _require_key_in_cache(conn, "analysis", partitions.analysis_key)
    _require_offline_key_resolves_a_sample(conn, run_dir, offline_key)


def _require_key_in_cache(conn: Any, stage: str, key: str | None) -> None:
    if not key:
        return
    row = conn.execute(
        "SELECT 1 FROM artifact_cache WHERE stage = ? AND settings_key = ? LIMIT 1",
        (stage, key),
    ).fetchone()
    if row is None:
        raise RunOfRecordError(
            f"{stage} settings key not found in the cache index it was "
            f"recorded/reconstructed to describe: {key} — a record that names "
            "a key absent from the cache is a wrong guess, never served"
        )


#: How many of a run's own rows :func:`_require_offline_key_resolves_a_sample`
#: samples — the first N whose own provenance says text was read. Bounded so
#: the check costs one indexed lookup each, not a full-archive scan.
_CORRESPONDENCE_SAMPLE_SIZE = 50


def _sample_offline_rows(run_dir: Path, limit: int) -> list[dict[str, Any]]:
    """The first ``limit`` rows of ``run_dir/rows.csv`` whose own provenance
    says offline text was read (``source_path`` ``native``/``local_tesseract``).
    ``rows.csv`` is read directly (not via
    ``telemetry.stated_counts.load_run_rows``) to keep this module's only
    dependency on the run directory's on-disk shape, with no import of
    a reader it serves."""
    import csv

    path = run_dir / "rows.csv"
    if not path.is_file():
        return []
    sampled: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("source_path") or "").strip() in ("native", "local_tesseract"):
                sampled.append(row)
                if len(sampled) >= limit:
                    break
    return sampled


#: Review the SUPERMAJORITY bound `_require_offline_key_resolves_a_sample`
#: enforces. Measured on the train9 archive (every offline row, not just a sample):
#: 3,476/3,476 resolve — 100%. 90% is a deliberate safety margin below that
#: ceiling; see:func:`verify_reconstruction`'s docstring for the full derivation
#: and the residual this bound does NOT close.
_CORRESPONDENCE_MIN_RESOLVED_FRACTION = 0.90


def _require_offline_key_resolves_a_sample(
    conn: Any, run_dir: Path, offline_key: str | None, *, sample_size: int = _CORRESPONDENCE_SAMPLE_SIZE
) -> None:
    if not offline_key:
        return
    sample = _sample_offline_rows(run_dir, sample_size)
    if not sample:
        # Nothing to check against — a run with no offline reads at all
        # (unusual, but not this function's call to refuse).
        return
    shas = [(row.get("content_sha256") or "").strip().upper() for row in sample]
    shas = [sha for sha in shas if sha]
    if not shas:
        return
    resolved = sum(
        1 for sha in shas if select_artifact(conn, "ocr", sha, offline_key) is not None
    )
    fraction = resolved / len(shas)
    if fraction < _CORRESPONDENCE_MIN_RESOLVED_FRACTION:
        raise RunOfRecordError(
            f"the offline OCR key {offline_key!r} resolves only {resolved}/{len(shas)} "
            f"({fraction:.0%}) of the sampled rows this run recorded as read "
            "(source_path native/local_tesseract) — below the required "
            f"{_CORRESPONDENCE_MIN_RESOLVED_FRACTION:.0%} — the record names the wrong "
            "partition for this cache and must not be served"
        )


def ocr_partition_for_row(row: Mapping[str, Any], partitions: RunPartitions) -> str | None:
    """The OCR settings key ONE row's own provenance names, or ``None`` when
    the row names a partition ``partitions`` does not have (e.g. a
    ``source_path`` of ``"none"`` — no OCR text at all — or a
    ``visual_rung``/``paddle_rung`` of ``"recovered"``/``"upgraded"`` on a run
    whose partitions carry no visual/paddle key). Never a fallback to another
    partition.

    `paddle_rung` is checked FIRST — a row is never both (`enabled_extractors`
    holds one extractor per mode, D4), but checking one order rather than
    "whichever is set" keeps this a total, deterministic function of the row
    rather than one that could disagree with itself across two reads of the same
    row."""
    paddle_rung = str(row.get("paddle_rung") or "").strip()
    if paddle_rung in _PADDLE_ROW_OUTCOMES:
        return partitions.ocr_keys_by_source.get("paddle")
    visual_rung = str(row.get("visual_rung") or "").strip()
    if visual_rung in _VISUAL_ROW_OUTCOMES:
        return partitions.ocr_keys_by_source.get("visual")
    source_path = str(row.get("source_path") or "").strip()
    return partitions.ocr_keys_by_source.get(source_path)


def analysis_partition(partitions: RunPartitions) -> str:
    """The run's one analysis settings key. A thin named accessor — callers
    should reach the field through this function rather than the dataclass
    directly, so a future per-document analysis partition (there is none
    today; see the module docstring on the analysis settings key being a
    per-RUN constant, not per-document) has one call site to change."""
    return partitions.analysis_key


def select_artifact(conn: Any, stage: str, input_sha256: str, settings_key: str | None) -> str | None:
    """The artifact path at exactly ``(stage, input_sha256, settings_key)``,
    or ``None`` on a miss. The table's primary key is ``(stage, cache_key)``
    and ``cache_key`` is a pure function of this triple, so an honest index
    holds AT MOST ONE row here; seeing more is a corrupt index, and this
    raises rather than picking one (the ``rows[0]`` bug this module replaces).
    """
    if not settings_key:
        return None
    rows = conn.execute(
        "SELECT artifact_path FROM artifact_cache "
        "WHERE stage = ? AND input_sha256 = ? AND settings_key = ?",
        (stage, input_sha256, settings_key),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise RunOfRecordError(
            f"{len(rows)} rows share stage={stage!r} input_sha256={input_sha256!r} "
            f"settings_key={settings_key!r}; the primary key (stage, cache_key) "
            "should make this impossible — a corrupt index is a finding, never a choice"
        )
    return str(rows[0][0])
