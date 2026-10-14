"""Content-addressed artifact cache (Wave 2 / D-3).

Identical bytes must never be OCR'd twice and identical markdown must never be
re-extracted twice. This module is the whole cache: key composition, the
on-disk payload store, and the three memoizing wrappers the webapp worker and
the CLI consumers (``batch.py``, the Wave-2 discovery runner) call.

It is deliberately Flask-free — importing it starts nothing, binds nothing and
needs no application context, so ``python -m discovery`` can use exactly the
same cache the web dashboard fills.

Stages (each cached INDEPENDENTLY)
----------------------------------
``ocr``       raw PDF bytes  -> ``StatementMarkdown`` (pages + model +
              O-3 ``page_integrity``)
``analysis``  statement markdown -> the ``document_report_to_dict`` payload
``report``    statement markdown -> the rendered HTML artifact

Chaining is by content, not by job: the analysis stage is keyed on the hash of
the markdown it is about to analyze, not on the PDF hash. That is what makes
the stages independent — a document whose OCR is cached but whose ANALYSIS
settings changed re-analyzes WITHOUT re-OCR, and two different PDFs that
happen to OCR to the same markdown share one analysis.

Cache key composition (exact)
-----------------------------
::

    settings_key = SHA256_UPPER(canonical_json(<stage settings dict>))
    cache_key    = SHA256_UPPER(canonical_json({
        "cache_format": CACHE_FORMAT_VERSION,
        "stage":        <stage>,
        "input":        <input sha256, UPPER hex>,
        "settings":     settings_key,
    }))

``canonical_json`` is ``json.dumps(obj, sort_keys=True, separators=(",", ":"))``
so key material is stable across runs and platforms. Every hash is UPPERCASE
hex SHA-256 — the one convention established by ``ocr/inspect.py``
(``content_sha256``) and ``corpus_gate.sha256_upper``.

``input`` per stage:

* ``ocr``      — ``content_sha256(pdf_bytes)``: the raw PDF bytes, nothing else.
* ``analysis`` — :func:`analysis_input_sha`: a digest over BOTH inputs the
  analysis reads — ``text_sha256(admissible_text(markdown))``, the markdown with
  the source-filename comment removed (W3 FILENAME-BOUNDARY), and
  :func:`sheets_sha256`, a digest over the intake object's page PARTITION.
  ``admissible_text`` strips the ``<!-- source: … | pages: N | … -->`` header,
  so before WIRING-2 the page structure was not in the key material at all —
  and ``to_markdown`` is not injective over that text, so an honest three-sheet
  document and a forged one-sheet document that prints the separators render to
  the same string, take the same key, and have DIFFERENT correct answers on
  ``missing_declared_statement_page``. The COUNT is not enough either: two
  two-sheet lists can render to one string with opposite answers, so the
  partition is what the key carries (W3 §WIRING W3). The header is not
  re-admitted, because it also carries the filename.
* ``report``   — ``text_sha256(markdown)``: the WHOLE markdown, filename comment
  included. The rendered artifact is not the analysis: it can show provenance,
  so the filename stays key material here.

The sheet evidence deliberately lives in the analysis stage's INPUT hash and
not in :func:`analysis_settings_key`: the settings key is a per-RUN constant,
and the telemetry observer's read-only artifact join (under ``telemetry/``)
indexes the whole artifact table on one value of it. A per-document value there
would silently blind that join — it would report nothing wrong while measuring
nothing.

``settings`` per stage — every knob that can change that stage's output, and
nothing else (surveyed from ``webapp/worker.py`` and the functions it calls,
``ocr.pipeline.parse_statement`` / ``analysis.pipeline.analyze_markdown`` /
``ocr.render.markdown_to_html``):

``ocr`` (:func:`ocr_settings_key`)
    ``force_ocr``, ``allow_local_ocr``, ``allow_visual_ocr`` — the ladder
    capability flags; they decide WHICH rung produces the text (the worker's
    deterministic preflight passes ``allow_visual_ocr=False``, auto mode
    passes ``allow_local_ocr=True``, the escalation call passes
    ``force_ocr=True``).
    ``dpi``, ``fallback_dpi`` — rasterization and the mis-segmentation retry.
    ``ocr_model``, ``ocr_base_url``, ``ngram_size``, ``window_size`` — the
    retired visual-OCR service knobs. Since slice S2 of the model-code removal
    they are FROZEN literals (:data:`FROZEN_OCR_SETTINGS`, the defaults the
    retired ``ocr.config.Settings`` held) unless a caller passes its own
    ``ocr_settings`` (historical reconstruction); the environment no longer
    moves them.
    ``stage_version`` = :data:`OCR_STAGE_VERSION`.

    Joining at v5 (P20-ARTIFACTS, Phase 2.0, OQ8/F-6) — present only when
    ``stage_version >= 5``, so a caller reconstructing a HISTORICAL v4 key (see
    :func:`ocr_settings_key`'s ``stage_version`` parameter and
    ``telemetry/run_of_record.py``) reproduces the pre-v5 dict byte-for-byte
    rather than a v5 shape with v4's version number stamped on it:

    ``extractor`` — ``"offline"`` or ``"visual"``, derived from the three
    capability flags by :func:`_ocr_extractor` (ONE function, pinned): visual
    only for the forced-escalation call shape (``force_ocr=True`` AND
    ``allow_visual_ocr=True``); every other call — including the ambiguous
    ``allow_visual_ocr=True, force_ocr=False`` "auto" shape, where the offline
    ladder still gets first refusal inside a single :func:`ocr.pipeline.parse_statement`
    call — is ``"offline"``. This is a LABEL on the settings partition, not a
    certified claim about which rung actually produced a given artifact (the
    artifact's own ``model`` field is that record); a third extractor stack
    (PaddleOCR) would add a third label here in a later phase — excluded now.
    ``postprocess_state`` / ``postprocess_admitted`` — the legacy OCR
    postprocess chain's quarantine state: the pinned ``"quarantined"`` /
    ``()`` for every extractor label (frozen key material since slice S2; the
    retired client's own constants always held exactly these values).
    ``raster_version`` = ``ocr.rasterize.RASTER_VERSION``.
    ``extraction_schema_version`` = :data:`EXTRACTION_SCHEMA_VERSION`.
    ``endpoint_class`` — from ``ocr_settings`` via ``getattr``, default
    ``"loopback"`` (the frozen :data:`FROZEN_OCR_SETTINGS` value when no
    ``ocr_settings`` is passed).
    ``tesseract_version``, ``poppler_version``, ``pymupdf_version`` — the
    binary/library versions the offline and visual rungs actually depend on
    (F-6), from :func:`ocr_toolchain_versions` — a never-raising, once-per-
    process probe; ``"unknown"`` when a version cannot be read, which
    partitions conservatively (a new key, a re-read) rather than silently
    reusing an artifact produced by a different binary.
    ``research_partition`` (P22-IDENTITY, Phase 2.2, D7) — present ONLY when
    non-empty: a research run's own partition id; absent (not an empty
    string) for every production call, so the production key is unchanged.

``analysis`` (:func:`analysis_settings_key`)
    ``parse_mode`` (``auto`` | ``deterministic``), ``withholding_denominator_mode``
    — the part of ``analysis.config.Settings`` that reaches the output; ``model``
    and ``escalation_model`` (frozen key material since slice S3 of the
    model-code removal: the literals :data:`FROZEN_ANALYSIS_MODEL` /
    :data:`FROZEN_ANALYSIS_ESCALATION_MODEL`, the names of the removed hosted
    extractor, never read from the settings), plus
    ``stage_version`` = :data:`ANALYSIS_STAGE_VERSION`, plus
    ``parser_registry`` = ``analysis.parser_registry.registry_fingerprint()``,
    plus ``generic_structurer`` =
    ``analysis.structurer.structurer_enabled()``.

    The registry fingerprint (W3 §REGFP) is a digest over the registration set
    itself — ids, bank labels, bands, ``supersedes`` edges, each marker's id and
    kind, the declared names of ``parse``/``normalize``/``integrity_checks``,
    and the ``formal_statement`` trio. Until it landed, the key could not see
    the registry at all: a registration added, removed, rewired or re-banded
    without a stage bump served every affected document its pre-change analysis
    out of the cache, and the only thing standing between that and a wrong
    published answer was the composed :data:`ANALYSIS_STAGE_VERSION` bump this
    programme performs at each train — a policy, not a construction. It is the
    settings key rather than the input hash because the registry is a per-RUN
    constant; see :func:`analysis_settings_key` for the WIRING-2 symmetry.

    ``reconstruction_mode`` (P22-IDENTITY, Phase 2.2, D6) =
    ``analysis.config.Settings.reconstruction_mode`` — the closed vocabulary
    ``off | research | production`` (environment ``RECONSTRUCTION_MODE``; the
    retired ``GENERIC_STRUCTURER_ENABLED`` is inert). It decides whether the
    W3-3c generic rung runs on the unclaimed branch, which changes the
    published payload of every document no parser claimed, so it partitions
    the cache exactly as ``parse_mode`` does. ``generic_structurer`` is the
    derived boolean, read through the structurer's OWN accessor over the SAME
    settings object (``structurer_enabled(analysis_settings)``) — one place
    decides what "enabled" means. ``off`` today and always: no artifact in the
    archive was written under any other value.

    ``hosted_extraction_opt_in`` (P22-FENCE review F3) = the frozen literal
    ``False`` (:data:`FROZEN_HOSTED_EXTRACTION_OPT_IN`) since slice S3: it
    recorded whether the removed hosted extractor's operator opt-in was set,
    and no default environment ever set it.

    Since Phase 2.2 the analysis INPUT hash also carries the sha of the
    evidence a geometry-fed analysis consumed (absent for text-only) — see
    :func:`analysis_input_sha`.

``report`` (:func:`report_settings_key`)
    ``title`` (the rendered document title) and ``stage_version`` =
    :data:`REPORT_STAGE_VERSION`.

Deliberately EXCLUDED from the keys, with reasons:

* ``source_file`` / filename — a LABEL, not a knob. It is re-stamped onto the
  cached ``StatementMarkdown`` on read, so the markdown header always names
  the file actually being processed while a re-upload under a new name still
  skips OCR entirely. It no longer reaches the ANALYSIS stage input either:
  that stage hashes ``admissible_text(markdown)``, the same filename-free text
  the pipeline analyzes (W3 FILENAME-BOUNDARY). The old justification — that a
  renamed duplicate is a genuinely different analysis input because "parser
  detection reads the markdown as a whole" — was obsoleted twice over: R-4b
  made detection filename-blind, and the boundary made parsing filename-blind.
  Keying on it now would mint a separate, durably-cached report for every
  rename of the same statement: N copies of one answer, each recomputed, and
  a cache that grows with operator filing habits rather than with documents.
* ``max_workers`` — the retired visual rung's page concurrency, which did not
  change output (never key material).
* ``timeout``, ``retries``, ``api_key`` — the retired visual rung's transport
  and secrets. Secrets must never be hashed into a key that is written to disk.
* callbacks (``on_stage``, ``on_page_replace``) and the preflight ``profile``
  — the profile is derived from the bytes already in the key.

Over-partitioning is safe, under-partitioning is not: the frozen visual-OCR
service knobs did not affect any offline result yet still partition the key,
exactly as they always have, so no cached reading is re-keyed.

CODE changes are NOT captured by any key, with one carve-out named below. If
the OCR ladder or the analysis pipeline changes its output, bump
:data:`OCR_STAGE_VERSION` / :data:`ANALYSIS_STAGE_VERSION` /
:data:`REPORT_STAGE_VERSION` in the same commit; bumping
:data:`CACHE_FORMAT_VERSION` invalidates everything.

The carve-out is narrow and is exactly this: the parser registry's OWN SHAPE —
the fields ``registry_key_material`` enumerates — is data rather than code and
is hashed into the analysis settings key (see ``parser_registry`` above), so
registering, removing, re-banding or rewiring a parser invalidates the analysis
stage by construction and needs no bump to be honest.

Nothing wider than that is covered, and two examples are worth naming because
they LOOK like registry data and are not: ``analysis.count_semantics``'s
per-parser-id ``SEMANTICS``/``CountMapping`` table is keyed by registration id
and moves published documents, and every parser's own extraction code is keyed
by nothing at all. Both are outside the digest and both still require a
:data:`ANALYSIS_STAGE_VERSION` bump in the same commit — as do the money
grammar, the ADB engine and the pipeline itself.
D-3b is the first exercise of that rule: O-3 added ``page_integrity`` to
``StatementMarkdown``, so the OCR artifact's shape changed and
:data:`OCR_STAGE_VERSION` went 1 -> 2. Entries written before it lack the
field and are invalidated rather than silently served without flags.

A cached read must be INDISTINGUISHABLE from a fresh one. For the OCR stage
that means the reconstructed document carries the model, the pages and the
O-3 per-page integrity records (truncation flags, signals, finish reason).
The one thing not reconstructed is the ``PageText`` str subclass the visual
rung produces: its model-side completion signals are consumed only inside
``ocr/pipeline.py``, which distils them into ``page_integrity`` BEFORE the
document exists — so no consumer of a ``StatementMarkdown`` can tell.

Persistence
-----------
Under the existing ``WEBAPP_DATA_DIR`` convention (``webapp.storage.
default_data_dir``): payloads are JSON files at
``<data_dir>/artifacts/<stage>/<first2 of key>/<key>.json`` (written to a temp
name and ``os.replace``d, so a reader never sees a half-written artifact), and
the index rows live in the ``artifact_cache`` table of the same SQLite store
(schema v3, forward-only migration per D-1). Large artifacts therefore never
enter the database. A missing or unreadable payload file is treated as a MISS
and its index row is dropped — the cache degrades to "recompute", never to
"wrong answer".

Module-level API for CLI consumers (discovery runner / batch.py)
----------------------------------------------------------------
::

    from webapp.artifact_cache import (
        open_cache, cached_ocr, cached_analysis, cached_report,
    )

    cache = open_cache()                    # WEBAPP_DATA_DIR, or an explicit dir

    ocr = cached_ocr(
        pdf_bytes,
        compute=lambda: parse_statement(pdf_bytes, source_file=name,
                                        allow_local_ocr=True,
                                        allow_visual_ocr=False),
        cache=cache, source_file=name,
        force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False,
    )
    doc = ocr.value            # StatementMarkdown | None   (None IS cached)
    ocr.cached                 # True -> compute() was never called

    result = cached_analysis(
        doc.to_markdown(),
        compute=lambda: document_report_to_dict(
            analyze_document(md, parse_mode="auto", sheets=doc.pages)
        ),
        cache=cache, parse_mode="auto", sheets=doc.pages,
    )

``sheets`` is the intake object's page list, and it must be the SAME list the
``compute`` call analyzes — it is key material, so handing the cache one
partition and the analysis another would store an answer under a key that does
not describe it. A caller with no intake object passes nothing and gets the
fail-closed behaviour end to end.

``compute`` is a zero-argument callable invoked ONLY on a miss; passing
``cache=None`` disables caching entirely (compute always runs), which is how a
caller opts out without branching. Exceptions from ``compute`` propagate and
are never cached: a failed extraction is not an artifact.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from analysis.parser_registry import admissible_text, registry_fingerprint
from evidence.canonical import EvidenceError, from_json, to_json
from ocr.config import ProvenanceTokenError
from ocr.document import StatementMarkdown
from ocr.inspect import content_sha256
from ocr.truncation import PageIntegrity

from .settings import _replace as _replace_retrying
from .storage import Storage

__all__ = [
    "ArtifactCache",
    "CacheResult",
    "CACHE_FINDING_EVIDENCE_DRIFT",
    "cache_finding_of",
    "CACHE_FORMAT_VERSION",
    "OCR_STAGE_VERSION",
    "ANALYSIS_STAGE_VERSION",
    "REPORT_STAGE_VERSION",
    "EXTRACTION_SCHEMA_VERSION",
    "STAGE_OCR",
    "STAGE_ANALYSIS",
    "STAGE_REPORT",
    "analysis_input_sha",
    "analysis_settings_key",
    "cached_analysis",
    "cached_ocr",
    "cached_report",
    "content_sha256",
    "ocr_settings_key",
    "ocr_toolchain_versions",
    "open_cache",
    "report_settings_key",
    "sheets_sha256",
    "text_sha256",
]

#: Bump to invalidate EVERY cached artifact (payload envelope change).
CACHE_FORMAT_VERSION = 1

#: Bump when the OCR ladder's output changes for unchanged settings.
#: v2 (D-3b): O-3's ``page_integrity`` joined the cached OCR artifact.
#: v3 (GEOM-1): the native rung gained ``parse_native_woodforest``, which
#: appends a column-read block to that family's markdown. The block is the
#: only place the printed Credits/Debits column survives, so a v2 entry would
#: keep serving the pre-fix flattened markdown — and the change would be
#: invisible on a warm cache rather than wrong-looking. This bump is GLOBAL by
#: construction (one integer for the whole ladder): it invalidates every
#: cached OCR artifact in the archive, and the next full discovery run re-reads
#: it. Vendor cost stays $0.00 — the native rung makes no model calls — but the
#: wall clock is paid again. Recorded here because the cost is real and was
#: chosen, not overlooked.
#: v4 (DESC-COLUMNS, coverage-wave batch 8): the native rung gained the
#: printed-row extraction behind the fail-closed furniture gate (G9) and the
#: never-raise guard, which changes the analysis INPUT of the core-processor
#: complex for unchanged settings (83 documents claimed, 6 payload movers on
#: the 7 counted, 0 raises) — a v3 entry would keep serving the pre-rung
#: markdown and the change would be invisible on a warm cache. GLOBAL by
#: construction, as v3 was: every cached OCR artifact is invalidated and the
#: train-8 cold run re-reads the archive (the local Tesseract rung's wall
#: clock is paid again; vendor cost stays $0.00). One composed bump before the
#: round's measurement, taken on the same host as the batch-7 control run.
#: v5 (P20-ARTIFACTS, Phase 2.0 — OQ8/OQ10/F-6): the key gains `extractor`,
#: `postprocess_state` + `postprocess_admitted`, `raster_version`,
#: `extraction_schema_version`, `endpoint_class`, and the Tesseract/Poppler/
#: PyMuPDF binary versions (module docstring's "Joining at v5" note;
#: `ocr_settings_key`'s `stage_version` parameter keeps a v4 RECONSTRUCTION —
#: `telemetry/run_of_record.py`, built to verify against a batch-8/9 run's
#: own cache — byte-identical to the key that run actually wrote). No
#: extractor's OUTPUT changed and the artifact SHAPE did not change either
#: (`CACHE_FORMAT_VERSION` stays 1); this bump exists so a future binary,
#: endpoint or postprocess change has a lever already proven to invalidate
#: the archive, rather than one added under time pressure the day it is
#: first needed. GLOBAL by construction, as v2-v4 were: every cached OCR
#: artifact is invalidated and the Phase 2.0 cold run re-reads the archive.
#: Vendor cost stays $0.00 (no extractor's model changed, only what the key
#: records about it).
OCR_STAGE_VERSION = 5
#: Bump when the analysis pipeline's output changes for unchanged settings.
# 1 -> 2: Track A cell 1 (chase variant completeness, merge of b70496c)
# changed chase extraction output for unchanged settings — cached chase
# analyses from v1 would keep serving pre-fix withheld results forever.
# 2 -> 3: Track A cells 2+3 (TD Canada direction recovery, RBC grid reader
# + balance-chain sign solving; merges of 2dea5ba and 488580f) change
# analysis output for unchanged settings. One composed bump after both
# merges — no pre-TD/RBC artifact can survive into the post-merge
# measurement.
# 3 -> 4: Track A cell 4 (bofa grid reader, merge of f7f6143) changes
# analysis output for unchanged settings on ~294 archive documents.
# (The GROUPER promotion merged alongside is proven byte-identical and
# owes no bump on its own.)
# 4 -> 5: Track A cells 5-8 (wells label-owned summary + multi-account
# primary; us_bank/truist/pnc vocabulary and grid fixes; merges of
# 2607da3 and 306f2ac) change analysis output for unchanged settings.
# One composed bump before the round's measurement.
# 5 -> 6: phase cell 1 (BMO layout registrations, merge of a990e95)
# adds claiming parsers for ~154 archive documents — their analyses
# change from no-parser to full extraction for unchanged settings.
# 6 -> 7: FIXUPS-1 (merge of acd0b07) — page-declaration restriction,
# totals posting-date exclusion, first_community count alignment change
# analysis output for 23+3+3 archive documents for unchanged settings.
# 7 -> 8: composed — COUNTS-P2 (merge of 67010d9: four ReconResult count
# fields on every payload; integrity flags on ~23 already-withheld
# documents) + phase cell 2 (merge of ae90180: chase overdrawn-sign fix
# changes ~108 archive documents from no-parse to full extraction;
# square_checking claims 11). Both change analysis output for unchanged
# settings; one composed bump before the round's measurement.
# 8 -> 9: composed — the 2026-08-13 coverage-wave batch (eight reviewed
# merges): chase A′ zero-activity + card C guard + chase_savings (+14);
# community_section head-noun grammar (+19); scotia rebuild — printed
# cell as amount of record (+3, three withheld corrected in place);
# bofa stated_debit_count scope (107 docs' published fields); pnc
# summary bounding + furniture row; rbc/truist/capital_one money
# grammar; FILENAME-BOUNDARY (admissible text at stage entry — also
# re-keys this stage's input hash, so v8 entries are unreachable
# regardless). One composed bump before the round's measurement.
# 9 -> 10: composed — coverage-wave batch 2 (three reviewed merges):
# td_us overdrawn-opening + section softening and td_can credit
# vocabulary (+10, +2 honest withheld); td_canada_french registration
# (+9, 4 withheld); rbc money-grammar hardening + English-personal +
# French-business layouts + English CIBC registration + CMap guard
# (+66; 4 mangled docs structurally refused). One composed bump before
# the round's measurement.
# 10 -> 11: composed — coverage-wave batch 3 (eleven reviewed merges):
# first_citizens control-record rebuild + citizens container fix (+47);
# us_bank/capital_one decline closures + R-1 product hardcodes removed
# (+28, 22 account_name -> None); bluevine/relay/navy_federal declines
# (+21); shared money grammar — U+2212/U+2013 sign class, one-decimal
# refusal, 13-digit bound, welded marker tokens (3 corrected movers);
# huntington + burke_herbert (+36); shopify_balance + citibusiness +
# zions (+41); mercury + found_lead(+activity) + brex (+52, 3 review by
# the issuer's own disclaimer); community_section issuer-agnostic
# template + 4 supersedes edges (+47); woodforest + wealthsimple +
# symitar (+38); fifth_third + fiserv_premier (+19); pipeline repairs
# keyed on the claiming registration (+3 chase whose ending balance a
# foreign repair rewrote) with the page-declaration sheet count inert
# until the ceremony-gated wiring card. Registry 53 -> 68. One composed
# bump before the round's measurement.
# 11 -> 12: composed — coverage-wave batch 4 (twelve reviewed merges):
# stated-count promotions x3 + first_citizens split + OBSERVER_VERSION 3
# (4 td_canada_french flag movers); fifth_third scanned issue (+4);
# first_citizens printed-description recovery (35 docs — description-
# keyed metrics move as measured in W3 #FI14.1/#FCX); woodforest
# geometry columns (+2, OCR_STAGE_VERSION 2 -> 3 composed with the
# first_citizens native rung); bank=None honest-unknown-issuer policy
# (community_section 5 + releve_facturation 16); core_processor_
# sectioned (+10) + balance_by_date (+11) platforms; chase_export
# wrapped rows (3 withheld -> review) + the fail-open or-0.0 class
# closed via read_money; woodforest initialization-event evidence half
# (inert; adb wiring awaits ruling); gate outcome-block check +
# PreparedDocument detect seam (behavior-identical, proven). Registry
# 68 -> 71. One composed bump before the round's measurement.
# 12 -> 13: composed — coverage-wave batch 5 (eleven reviewed merges):
# sheets activation + the APPROVED Option-A ceremony (Texas Bank + Regions
# review->validated, BMO January flag withdrawal) + the partition-digest
# input key (also rotates every analysis entry by construction); the
# ratified ADB doctrine (underwriting_adb split + basis literal gate-
# pinned + H1 required + the two Woodforest initialization movers);
# CountMapping promotions (21 stated_debit_count_matches false->true);
# repair seam (discard+flag) + honest model_used for bank=None (54 docs
# with LOWERCASE-PERIOD's); minus-glyph canon; evidence-based currency
# (9 movers); core_processor_daily (+13); parser_id cache-hit projection;
# PreparedDocument across both sweeps; one shared native ladder + the
# unreadable-text-layer reason channel. Registry 71 -> 72. One composed
# bump before the round's measurement.
# 13 -> 14: composed — coverage-wave batch 6 (thirteen reviewed merges):
# the APPROVED RBC Canada jurisdiction default (151 statement.currency
# USD -> CAD, label-only; the four pinned RBC movers; the pinned currency
# surface, 109/109); registry fingerprint + generic_structurer flag folded
# into the analysis settings key (rotates every analysis entry by
# construction); fiserv_premier third printed issue (+4);
# core_processor_counted (+8); texas_first_scanned (+4 validated, +1
# review); wilson_muir summary strip + square_checking Location column
# (+10); columbia_bank fifth grammar (extension, zero movement); sign
# glyphs read as signs (U+2212/U+2013); the money grammar's refusals, the
# worker boundary and the LLM branch stop quoting the document; the
# package layer refuses cross-currency aggregation; telemetry
# deterministic-coverage repair. Registry 72 -> 74. One composed bump
# before the round's measurement.
# 14 -> 15: composed — coverage-wave batch 7 (ten reviewed merges + one
# train composition): the APPROVED REPAIR-DOCTRINE ceremony (columbia_bank
# loses both amount-rewriting repairs and publishes the printed daily-grid
# cell with disagreement flagged; the pinned Columbia statement moves to a
# pinned REFUSAL — a parse-BODY change the registry key material does not
# capture, which is the bump's load-bearing reason); DESC-ATTRIB (count-based
# description attribution across the core-processor complex: 4 documents'
# descriptions shorten, 15 classifier detections change); CURRENCY-SOURCE
# (the currency-PROVENANCE field added to EVERY published statement — a
# warm cache would serve payloads without it); DECLINES-E chase grid (+3);
# DECLINES-F first_citizens At-A-Glance (+4) + FC-PRODUCT labels; DECLINES-G
# symitar yield-only sibling (+3) + FISERV-LABELS; SCAN-FINISH southside +
# citizens (+3 validated, +2 review, +6 withheld); SCAN-TANGERINE = the
# eq_bank_scanned registration (+3 withheld); PRIVACY-3 and ATB-MEASURE move
# nothing. Registry 74 -> 75. One composed bump before the round's
# measurement.
# 15 -> 16: composed — coverage-wave batch 8 (twelve reviewed merges + train
# compositions). The registry grows 75 -> 83 (core_processor_signed_counts,
# core_processor_activity_summary, welch_state_bank, lili, bank_ozk, frost,
# core_processor_enclosures, category_partition) — which the registry
# fingerprint in the settings key captures on its own; the bump's load-bearing
# reasons are the parse-BODY changes the key material does not capture:
# WITHHELD-TD (td_canada_native / td_canada_french / td_us: +11 withheld ->
# validated, row-level signs); WITHHELD-GRIDS (the source posting-date rules
# tightened archive-wide, +16 withheld -> validated, one diagnostic leaf on the
# pinned ibc document — an accepted, named move); CP-SECTIONED-SCAN (three
# grammar corrections on the two shared scanned readers, 0 movement measured
# over 135 documents); SCAN-HYGIENE (integrity checks on three registrations:
# 8 withheld payload movers, flags/notes/risk/quality only); DESC-COLUMNS (the
# native-text rung rotates the analysis INPUT: 6 payload movers, descriptions
# only — the OCR v4 bump above); CORE-ENCLOSURES (three supersedes edges over
# burke_herbert / farmers_merchants / linkbank) and GLANCE (a supersedes edge
# from wilson_muir) re-route documents between readers; HYGIENE-8a (refusal
# messages stop carrying document tokens; 0 payload movement by measurement);
# CORE-ISSUES-2 / WELCH / LILI / FROST-OZK claim only documents no reader
# claimed before. Batch total claimed, uncomposed: +129 validated. One
# composed bump before the round's measurement.
# Batch 9 (composed 2026-08-31, the L-1 multi-account train): DocumentReport /
# analyze_document at the pipeline seam; evidence-based sibling admission with the
# omission on the document object; every reader and seam taught the document shape;
# the guardian_cu first publisher (+8 validated / 12 accounts, rulings 8.8-8.16);
# the serialized shape decided by account count alone, and the document surface lit
# for 23 documents (15 protected carriers + the 8 published) per Q10 — a payload-
# shape change, so a warm cache keyed on 16 would serve old-shape payloads.
# 17 -> 18: P22-IDENTITY (Phase 2.2, D6) — the analysis key becomes geometry-
# aware: `analysis_input_sha` carries the evidence sha that fed geometry
# (absent for a text-only analysis), `analysis_settings_key` carries
# `Settings.reconstruction_mode` (`off` everywhere the archive has ever run),
# and `generic_structurer` is derived from that setting rather than from the
# retired environment variable. No analysis OUTPUT changes at this tree (the
# structurer stays off and no caller passes geometry yet); the bump exists so
# no stage-17 artifact — computed under the geometry-blind key — can ever be
# served to a stage-18 call, and so the run of record's analysis partition
# rotates once, at the train's cold run, together with the OCR partition
# (`EXTRACTION_SCHEMA_VERSION` 3). Pinned in the same commit
# (`tests/test_artifact_cache.py`).
# 18 -> 19: LENDER-DETECTION (2026-09-24 design, service S2) — classification
# version 5.0: ten flag-group states, the premium-financing flag on insurance
# rows, and the `flagged_group` / `contributes_to_flagged_totals` record
# fields; the reordered payee rules (known-payee matcher, card-paid lenders,
# LOC wording); financing-proceeds credits; obligation descriptors;
# unknown-payee naming and the fixed-debit
# review tier; `metrics.flagged_groups` and `detection.flagged_positions` join
# the payload. The classifier's registry is not key material, so a warm cache
# keyed on 18 would serve the old lender groups. OCR stays cached. Pinned in the
# same commit (`tests/test_artifact_cache.py`).
# 19 -> 20: LENDER-DETECTION D6 clarification (2026-09-26) — classification
# version 5.1: a same-amount recurrence (D6 and the financing-keyword tier) needs
# at least three different dates, several rows on one date counting as one; and
# D6 never takes a card-purchase posting the POS rule does not read (a posting
# that starts PURCHASE and its mmdd, or a processor*merchant star on a row with
# no ACH field mark). Stored rows lose `recurring_fixed_debit` /
# `recurring_financing_counterparty` promotions, so a warm cache keyed on 19
# would serve them; a re-analysis (webapp/reanalysis.py) misses the analysis
# stage and recomputes it from the cached reading. OCR stays cached. Pinned in
# the same change (`tests/test_artifact_cache.py`).
# 20 -> 21: LENDER-DETECTION second D6 clarification (2026-09-27) —
# classification version 5.2: D6 never takes a row whose words name
# compensation (a commission and its misspellings, a bonus, a salary, a stipend,
# a reimbursement), and a masked recipient account printed after TO joins the D6
# payee key, so payments to two recipient accounts are never one payee. Stored
# rows lose `recurring_fixed_debit` promotions, so a warm cache keyed on 20 would
# serve them; a re-analysis recomputes the analysis stage from the cached
# reading. OCR stays cached. Pinned in the same change
# (`tests/test_artifact_cache.py`).
# 21 -> 22: LENDER-DETECTION false-potential release (2026-09-27) —
# classification version 5.3: new D6 skips, fee/NSF, cheque, card, payroll,
# mortgage and POS wording, admitted payees in the bank's field order, unconfirmed
# flag payees routed to their flag, D11 naming fixes, one Potential Lenders line
# per unnamed payee key (potential_payee_label), and the Debt relief group (a new
# state). The groups D6 no longer promotes (the skips and the $25 floor for
# unnamed payees) also leave detect.find_recurring_debits, so the CLI's
# 'Recurring fixed debits' lines, batch.py's recurring_debit_groups and the
# payload's detection.recurring_debits lose them too. Stored rows change state,
# entity and fields, so a warm cache keyed on 21 would serve them; a re-analysis
# recomputes the analysis stage from the cached reading. OCR stays cached.
# Pinned in the same change (`tests/test_artifact_cache.py`).
# 22 -> 23: LENDER-DETECTION Idea Financial ruling (owner, 2026-09-28) —
# classification version 5.4: IDEA FINANCIAL moves from the line-of-credit table
# to the lender table and gains its printed ACH spellings (IDEALOAN, IDEA 247
# INC), so its debits become counted lender rows (a row printing LOC or LINE OF
# CREDIT stays a line of credit, D9) and its credits stay financing proceeds.
# Stored rows change state and entity, so a warm cache keyed on 22 would serve
# them; a re-analysis recomputes the analysis stage from the cached reading. OCR
# stays cached. Pinned in the same change (`tests/test_artifact_cache.py`).
# 23 -> 24: TRUE-REVENUE bug fixes (2026-09-28 design, §7) — classification
# version 5.5: credits move between verified_revenue, unverified_deposit and
# non_revenue (card and payout forms, the recurrence pass, payer remittance,
# public and healthcare payers, invoice wires, the non-revenue narrowings), and
# SQ CAP and SBA or EIDL credits become financing proceeds. Stored rows change
# revenue state, so a warm cache keyed on 23 would serve them; a re-analysis
# recomputes the analysis stage from the cached reading. OCR stays cached.
# Pinned in the same change (`tests/test_artifact_cache.py`).
# Review fixes (2026-09-29): glued dates never change a reading; the holder's
# name never names a payer; own-account transfers, glued and invoice wires and
# platform financing words keep their vetoes.
# 24 -> 25: TRUE-REVENUE definitional rules (2026-09-28 design, §8) —
# classification version 5.6: every posted credit carries revenue_tier,
# revenue_initial_tier and revenue_tier_reason, the metrics gain True revenue and
# its counted and held parts, true_revenue is repointed, and
# revenue_review_required follows the held share (T7). A payload-shape change:
# a warm cache keyed on 24 would serve tier-less rows; a re-analysis recomputes
# the analysis stage from the cached reading. OCR stays cached. Pinned in the
# same change (`tests/test_artifact_cache.py`).
# Review decisions (2026-09-29): direction conflicts never lifted; bare
# transfers, micro entries, owner money, deferred sources and round-sum repeats
# held or counted as ruled; Q7 honours the section 8.1 holds.
# 25 -> 26: TRUE-REVENUE audit batch B9 (holder identity) — the statement
# gains `holder_name` (the holder's name read from the header or the mailing
# block, apart from the product in `account_name`); the Chase parser stops
# publishing its CHECKING SUMMARY grid header as the account name and reads the
# holder from its mailing block, and First Citizens reads its holder line; TD
# Bank, Truist, PNC, Navy Federal and TD Canada Trust read theirs too (the
# batch's second code commit, under the same bump; so is its review round 1,
# where PNC never reads its own product printed in capitals as the holder,
# stage 26 never having been published). A
# payload-shape change (the statement, each classification record and the
# metrics' `holder_unscreened`), and the holder holds read the new name, so a
# warm cache keyed on 25 would serve rows held or counted without it; a
# re-analysis recomputes the analysis stage from the cached reading. OCR stays
# cached. Pinned in the same change (`tests/test_artifact_cache.py`).
# 26 -> 27: TRUE-REVENUE audit batch B10 (lost payer text) — the parsers keep
# the payer a credit prints beside its posting-type label: BMO US's activity
# grid (the head line after the amount and the Description column's lines
# below it), the counted core-processor template (the merchant block printed
# below a credit's amount, by the attribution count), the community platform's
# same-line text after a credit's amount (Arbor, Falcon's wire sender), the
# balance-by-date template's transfer field and U.S. Bank's `ORG=` wire sender;
# a credit whose printed payer a parser could not read is marked
# (`Transaction.payer_text_unread`, serialized only where set) and counted as
# `payer_text_not_read`; the metrics gain `payer_text_unread` and its count.
# The batch's review round 1 lands under the same version (nothing between
# was released): the daily core-processor template marks the credits whose
# block it does not read yet, U.S. Bank reads the ORG= field up to the sender's
# address or the next field, the community platform's tail stops at a heading
# and reads published credits only, BMO US skips a page break whole, and a
# marked cash, branch, teller or ATM label keeps `no_payer_printed`.
# Descriptions and tiers move, so a warm cache keyed on 26 would serve the bare
# labels; a re-analysis recomputes the analysis stage from the cached reading.
# OCR stays cached. Pinned in the same change (`tests/test_artifact_cache.py`).
# 27 -> 28: TRUE-REVENUE audit batch B11 (the review gate) — T7 also gates a
# statement whose held credits are 10% or more of True plus held and at least
# $500 (`REVENUE_REVIEW_HELD_FLOOR`), so `metrics.revenue_review_required`
# moves on statements heavy with non-revenue; the metrics gain
# `revenue_tiers_sum_to_posted`, the four-tier identity under its own name
# (`revenue_reconciles` stays as its alias), and the BNPL or marketplace
# settlement reason gets its new label. No tier and no figure moves. A warm
# cache keyed on 27 would serve the old gate; a re-analysis recomputes the
# analysis stage from the cached reading. OCR stays cached. Pinned in the same
# change (`tests/test_artifact_cache.py`).
# 28 -> 29: TRUE-REVENUE audit round 2, batch R2-B04 (holder screening, the
# holder-name strip and the holder's own push) — `metrics.holder_unscreened`
# reads a holder name the parser read as known whatever its shape (a trailing
# CO, a partnership, a DBA or 'Operating as' name, S.E.N.C., five words or
# more) and reads a statement with no transaction (R19); the I47 strip reads
# each side of such a name, a cut last word at the row's end and the holder's
# business names beside a person's (R19, R40); the holder test reads two shared
# trade words, and a person's given name, as no holder (R20); the holder's own
# push is held where an earlier rule verified it and on American Express's
# receiver block (R41); a processor's or a franchisor's credit printing the
# holder's name is no holder's own money, and Capital One's Mercury tails never
# hide one (R04 parts 1 and 3). The stored metric and the holds move, so a warm
# cache keyed on 28 would serve them; a re-analysis recomputes the analysis
# stage from the cached reading. OCR stays cached. No parser changes. Pinned in
# the same change (`tests/test_artifact_cache.py`).
# 29 -> 30: TRUE-REVENUE audit round 2, batch R2-B05 (R04 parts 2 and 4: the
# holder-name readers) — fourteen more parsers publish `Statement.holder_name`
# from page 1's mailing address (Bank of America, Wells Fargo, U.S. Bank, RBC
# and Banque Royale, Scotiabank, Bluevine, Huntington, Capital One, CIBC,
# Square, Mission Valley, BMO's US activity layout, Santander and Citibank;
# Desjardins' reader is held for the owner), TD Canada Trust's French issue reads the
# English issue's mail-routing anchor, and Chase, Navy Federal, TD Bank and PNC
# gain a page-1 block fallback where their anchor reads none. Only the holder
# name moves in the extraction (every transaction is byte-identical); the holder
# holds read it, so a warm cache keyed on 29 would serve the old tiers; a
# re-analysis recomputes the analysis stage from the cached reading. OCR stays
# cached. Pinned in the same change (`tests/test_artifact_cache.py`).
# 30 -> 31: TRUE-REVENUE audit round 2, batch R2-B06 (R03; R21 part B's parser
# line) — Navy Federal's compatibility path reads its block text as tokens with
# one token of lookahead, so a retail product's amount-first text gives each
# row its own date and description (the old line reader runs only where that
# reading does not fit), and the native layout rung reads the one checking
# product the summary declares instead of 'Business Checking' alone. The
# cached readings of the four EveryDay Checking statements are the generic
# block text, so their rows move on re-analysis; a warm cache keyed on 30
# would serve the shifted rows. OCR stays cached and OCR_STAGE_VERSION is not
# bumped (a fresh upload reads the layout rung; Business Checking's native
# output is byte-identical). Pinned in the same change
# (`tests/test_artifact_cache.py`). The batch's second parser commit (R21 part
# B) drops the page header both readers glued into the last row before a page
# break ('Statement of Account', 'Joint Owner(s): NONE'); it ships under the
# same stage, as nothing was released between the two commits.
# 31 -> 32: TRUE-REVENUE audit round 2, batch R2-B07 (R07) — the counted
# core-processor template keeps, on each credit it marks 'payer text not read'
# at a welded flush, that flush's joined text in a new stored transaction field
# (`Transaction.unread_payer_text`, written only where set and kept out of the
# extraction schema), and the true-revenue pass holds such a credit when the
# run prints a registry lender's or a lending bank's block. Every amount and
# every published description is unchanged; a warm cache keyed on 31 would
# serve stored transactions without the field, so those credits would stay
# counted. OCR stays cached. Pinned in the same change
# (`tests/test_artifact_cache.py`).
# 32 -> 33: TRUE-REVENUE audit round 2, batch R2-B16 (R56), in the commit that
# moves CLASSIFICATION_VERSION 5.6 -> 5.7 (the audit's fix batches B01 to B12,
# round 2's R2-B01 to R2-B16 and the owner's rulings of 2026-10-02 and
# 2026-10-06, R2-OW01 to R2-OW18 with R2-L01's ledger admission, moved tiers,
# reasons and the review gate under 5.6). This bump is required with it:
# Re-analyze reads the analysis cache through (`_CacheOnly` passes
# `get_analysis` through), so with 5.7 alone it would return the stage-32
# entry still stamped 5.6 and the re-analyze notice would survive its own
# button; at 33 a re-analysis or a re-upload misses that entry and recomputes
# the analysis stage from the cached reading. A shape change, not only a tier
# move: the owner batches (their CR2) changed the stored payload without a
# bump of their own, so a stage-32 entry lacks `Statement.account_title`
# (R2-OW10, where the holder reader reads a title); the record fields
# `revenue_funding_series` (R2-OW12, a list on every record),
# `returned_funder_payment_by` and `returns_funder_payment` (R2-OW13) and
# `potential_payee_key` (R2-OW18); the metrics' `non_revenue_by_reason`
# (R2-OW03), `premium_trust_account` (R2-OW11) and
# `returned_funder_payment_total`, `_count` and `_evidence` (R2-OW13, with the
# new meaning of `withholding_numerator`); the detection's
# `returned_funder_payments` and the funder matches' `returned_count`,
# `returned_total` and `returned_payments` (R2-OW13) and
# `lender_payment_changes` (R2-OW18); the account key `zelle_counted_reading`
# (R2-OW17: the counted reading's edits, so a stage-32 entry is served as
# analysed until it is recomputed); and the reason codes `zelle_excluded`
# (R2-OW02), `government_no_purpose` (R2-OW03), `customer_financing_payout`
# and `customer_financing_lump_sum` (R2-OW04), `lender_paid_for_services`
# (R2-OW05), `construction_progress_draw` and `asset_sale_proceeds`
# (R2-OW06), `insurer_paid_for_services` (R2-OW08), `finance_named_customer`
# and `lessor_rent` (R2-OW09) and `premium_trust_account` (R2-OW11), beside
# R2-B07's `unread_run_names_financing`. The withholding default `true_revenue`
# (R2-OW14) changes the analysis settings key itself. The package's keys
# (R2-OW11's premium trust, R2-OW13's returned totals, R2-OW15's matches and
# R2-OW16's `own_account_transfer_matched` overlay, R2-OW18's payment changes)
# and the served ones (R2-OW15's flag keys, R2-OW17's `zelle_deposits` and row
# tag) are computed when served, from the stored analysis. Nothing between 32
# and 33 was released. OCR stays cached. Pinned in the same change
# (`tests/test_artifact_cache.py`). Folded into 33 (the final review of round
# 2, F2(a), true revenue spec §9.3): a confirmed funder's paid payment pairs on
# the lender side only with a return dated on or after it, which changes the
# stored lender fields of a pair a return printed before the payment made (the
# payment's `reversed_by`, `returned_funder_payment_by`, contributions and
# reason; the return's `reversal_of`, `settlement_reversal` and
# `returns_funder_payment`). Stage 33 was never released and the cache held no
# stage-33 analysis when it landed, so it needs no bump of its own. F1 (the
# withholding basis) is applied when an analysis is served and F2(b) when a
# package is built: neither changes a stored analysis.
# 33 -> 36:TRUE-REVENUE audit round 3, batch R3-B25, in the commit that moves
# CLASSIFICATION_VERSION 5.7 -> 5.8 (required with it: Re-analyze reads the
# analysis cache through, so with 5.8 alone it would return the stage-33 entry
# still stamped 5.7 and the notice would survive its own button; at 36 a
# re-analysis or a re-upload misses that entry and recomputes the analysis
# stage from the cached reading). Stages 34 and 35 are skipped: the hosting
# line (fix/boa-nsf, deployed on the Fly demo) used them for its Capital One
# carry-in fix (34) and its Bank of America daily-ledger table (35), code this
# branch merges after the run, never back to 34 or 35, so no entry cached under
# 34 or 35 is served as this branch's reading. 36 is reserved for this branch
# (a further hosting-line change takes 37 or above), and since the merge
# changes the analysis output (those two parsers), the merge commit moves the
# stage again, to the next free stage above both lines (37 if neither line has
# moved by then), so no entry cached at 36 before the merge is served as the
# merged code's (R3-B25 review round 1). The round-3 fix batches (R3-B01 to
# R3-B24) changed stored output under 5.7 and stage 33 with no bump of their
# own: R3-B01, the classification of a bank's stop-payment and item charges
# that name a funder (`fee` or `nsf_or_return`, no lender row; R3-80) and of
# ODKRAOD's debits as ONDECK's (R3-26: paid to lenders, the withholding
# numerator and rates, the funder rollup); R3-B02, the record field
# `represented_by` and, on a returned funder payment the funder re-debited, its
# `contributes_to_withholding_rate` and reason, the numerator, the rates, the
# metrics note and the detection item's `represented_*` keys (R3-73), a
# potential lender's return paired only with a payment on or before it
# (`reversed_by`, `reversal_of`, contributions; R3-71) and the funding aid's
# `revenue_funding_series` where a bounced attempt precedes the deposit
# (R3-66); R3-B03, the metrics' `withholding_basis_below_floor`,
# `lump_sum_payoff_total` and `lump_sum_payoff_count`, the record field
# `lump_sum_payoff`, the detection's `lump_sum_payoffs`, the rates, exposure,
# notes and potential lenders' denominators under the $500 basis floor (R3-20)
# and a worded payoff's place outside the rate (R3-79); R3-B04 to R3-B06, the
# statement items of `detection.lender_payment_changes` (items gained and
# lost, the `catch_up` kind and its fields, `first_after_amount`,
# `first_after_multiple`, `larger_debits_inside`, `catch_ups_inside`,
# `other_debits_after.catch_ups`, `payoff.earlier`, `same_amount_debits`,
# `alongside` and the weekly totals, the funding note's credit); R3-B07,
# R3-B08, R3-B10 and R3-B12 to R3-B17, the revenue reading of the credits
# their readers move (state, tier, reason, method, matched rule, sentence,
# contribution flags; R3-B12's PNC and French P2P rails with their
# `zelle_prior` signals and `zelle_counted_reading` edits) with their
# statements' totals, review gate and True-basis rates, R3-B08's credit
# classes and check, ACH and POS facts where page furniture decided them
# (R3-92) and R3-B14's Cherry loan credits' D1 record (R3-06); R3-B09, the
# parser output `Transaction.payer_text_unread` and `unread_payer_text` the
# daily core-processor, balance-by-date and B1 readers now write (R3-91), the
# metrics' `payer_text_unread` and its count, and the `possible_return` holds
# on outgoing e-Transfer labels (R3-75); R3-B11, the 22 holder readers'
# `Statement.holder_name` and `account_title` on contact lines and the
# premium-trust forms (R3-61, R3-65; 0 corpus statements); R3-B15, the held
# rows' `revenue_reason` (R3-53) and the $1 floor's method on demoted rows
# (R3-63). A warm cache keyed on 33 would serve each of them as the round-2
# reading. The package (R3-B03's mixed basis, R3-B06's reappearance, R3-B18's
# `days_shared`, R3-B19's gate on the sums, R3-B20's Zelle `setting`, R3-B24's
# large-deposit totals), the served flags (R3-B20's unestablished Zelle
# parts, R3-B24's `large_unsourced_deposit_*`), the downloads (R3-B05's
# catch-up fields and notes, R3-B06's `reappears_in_other_account` cells,
# R3-B20's empty Zelle cells and the package's `setting` row, R3-B23's
# sections, empty cells and title filter, R3-B24's metric rows and sections),
# the CLI and batch output (R3-B05's catch-up line and
# `lender_payment_catch_ups` column, R3-B06's stop line, R3-B20's N/A Zelle
# line and empty `zelle_in_true_revenue_total`, R3-B22's basis columns,
# R3-B24's columns and line), the copied memos (R3-B22's, R3-B24's) and the
# census tools are computed when served or exported, never stored. Nothing of
# this branch's between 33 and 36 was released. OCR stays cached. Pinned in
# the same change (`tests/test_artifact_cache.py`).
# The round's final review (R3-FF) is folded into 36, still unreleased: the
# stored `metrics.withholding_formula` words (F5) and, latent in the corpus, a
# returned payment whose only re-debit was a worded payoff (F3) and a wire from
# a company named only with R3-40's words (F4); its member-row rates (F2) and
# large-deposit floor (F6) are computed when served.
# The hosting line (`fix/boa-nsf`, served on the Fly demo) moved the stage on
# its own, from 33, for code this branch did not carry until the merge-back:
# 33 -> 34 (owner report 2026-10-08, Capital One daily ledger): the parser declares postings printed on the
# previous-balance day (`Statement.pre_period_carry_in_count`) and the ADB engine folds them into the opening
# balance, so such a statement's stored ADB and NSF days change from withheld to published; OCR stays cached.
# 34 -> 35 (owner report 2026-10-08, Bank of America NSF): its verified Daily ledger balances join the stored ledger.
# 36 -> 37: TRUE-REVENUE audit round 3, R3-MERGE, the merge-back of the hosting
# line (`fix/boa-nsf` f2e9ae1) into this branch, in the merge commit itself.
# The merged analysis output differs from both lines' (round 3's readings at
# 36 with the hosting line's two parser fixes at 34 and 35: a Capital One
# statement's carry-in fold and a Bank of America statement's verified Daily
# ledger balances in the stored ledger), so neither line's entry may be served
# as the merged code's: 37 is the next free stage above both lines (34 and 35
# are the hosting line's, 36 this branch's). CLASSIFICATION_VERSION stays 5.8:
# the hosting line changed no classification. The hosting line's dashboard
# changes (the plain-voice lender notes, the hero, the Monthly Statements
# columns, the chart's colours) are computed when served, never stored. OCR
# stays cached. Pinned in the same change (`tests/test_artifact_cache.py`).
# 37 -> 38: LENDER-DETECTION Amerifi Capital ruling (owner, 2026-10-11), in
# the commit that moves CLASSIFICATION_VERSION 5.8 -> 5.9 (required with it:
# Re-analyze reads the analysis cache through, so with 5.9 alone it would
# return the stage-37 entry still stamped 5.8 and the notice would survive its
# own button). The ledger admits Amerifi Capital as a confirmed lender (alias
# AMERIFI CAPITAL), so its debits, stored until now as `potential_lender` rows
# (D6), become counted lender rows (state, entity, alias, match method, reason,
# the lender, withholding and lender-count contributions, the potential ones
# off; a row printing LOC or LINE OF CREDIT is `line_of_credit`, D9) with the
# account's lender and withholding metrics and its detection (`known_funders`,
# `potential_lenders`, the lender payment changes' series), and its credits,
# held until now as unverified deposits, become financing proceeds (D1:
# `non_revenue`, the lender-credit exclusion) with the revenue totals. No
# cached corpus row prints the name, so no cached analysis moves; a statement
# that prints it (the owner's, not in the local cache) does. This change rides
# the hosting line ahead of true revenue audit round 4, whose last batch
# therefore takes 39 (and 5.10). OCR stays cached. Pinned in the same change
# (`tests/test_artifact_cache.py`).
# 38 -> 39: the code audit of 2026-10-13 (one pull request, branch
# `audit/2026-10-13`; this is its ONE stage move, made in batch A03). It
# supersedes the line above: 39 is the audit's, so true revenue audit round 4
# takes 40 or above. What a warm cache keyed on 38 would serve wrongly: the
# integrity block of a document whose sum check failed by at most a dollar or
# could not run (REC-4: `ledger_sum_mismatch` at one cent, the new
# `ledger_sum_uncheckable`, their notes and risk level); the ADB's
# `validations` and `warnings` and the account's `notes` on every statement
# that publishes a bank-printed daily balance (REC-1 step 1, the advisory
# `bank_daily_balances_agree_with_rows`); every reading of a PNC, IBC,
# Columbia Bank or First Community statement whose period crosses a year
# boundary or prints a row or printed cell outside its period (PARSERS-2),
# and of a CIBC-named document carrying IBC's product phrase (PARSERS-8); and
# a money token the raising or strict grammar now refuses (PARSERS-4). The
# batch's other analysis changes need the same invalidation and are covered
# by this one move: A02's five fenced bank repairs and the re-keyed three
# (an archive replay moved nothing; an upload could). CLASSIFICATION_VERSION
# stays 5.9: no classification changed. OCR stays cached. Pinned in the same
# change (`tests/test_artifact_cache.py`).
ANALYSIS_STAGE_VERSION = 39
#: Bump when the HTML renderer's output changes for unchanged settings.
#: 1 -> 2: audit 2026-10-13, EXP-1 (`ocr/render.py`): markup printed in statement text is shown as text, the visual-OCR
#: table markup let through loses its attributes, the header comment is kept only when it carries no angle bracket,
#: and the page head carries the report's Content-Security-Policy meta tag. Text with no markup renders as before; a
#: v1 report would keep serving live markup and no policy. OCR and analysis stay cached. Pinned in
#: `tests/test_artifact_cache.py`.
#: 2 -> 3: the final review of the same audit, finding 2 (`ocr/render.py`): only the exact, attribute-free table tags
#: pass through; a table tag carrying anything more or written in capitals, and statement text that only starts like
#: one ("<TD SAMPLE BANK>"), is shown as text instead of becoming a bare tag that hid its words. A v2 report would keep
#: hiding them. Value 3 was never used by any branch. OCR and analysis stay cached.
REPORT_STAGE_VERSION = 3
#: The OCR artifact's own record shape (P20-ARTIFACTS, Phase 2.0, F-6/§10):
#: joins the OCR settings key at :data:`OCR_STAGE_VERSION` 5+ so a change to
#: what `StatementMarkdown` records (independent of which extractor or binary
#: produced it — that is `OCR_STAGE_VERSION`'s and `extractor`'s job) gets its
#: own lever. v1 is the shape at Phase 2.0: `model`, `pages`, `page_integrity`.
#: v2 (P21-ROUTING, Phase 2.1, D6): the record gains `page_extractor`
#: (per-page provenance, every rung) and `evidence` (the full canonical
#: evidence behind a Paddle read — `None` for every other rung), and
#: `ocr_settings_key` gains the boolean partition field `allow_paddle_ocr` at
#: the same v5+ material — so the offline partition's key changes too, and
#: the WHOLE OCR cache goes cold at the train's cold run (required anyway by
#: the completion gate). A schema-1 cached record (every archive entry before
#: this cell) restores with `page_extractor=[]` and `evidence=None`, which
#: `StatementMarkdown.__post_init__` accepts as "not populated" — never a
#: crash on an old cache entry.
#: v3 (P22-IDENTITY, Phase 2.2, D5): the record gains `native_evidence` (the
#: ONE native reader's canonical word evidence in the display frame, behind a
#: native-rung read — `None` for every other rung) and `native_evidence_sha256`
#: (its sha, stored beside it so a restore re-verifies the blob against the
#: sha the record CLAIMS, not only the sha the blob reproduces). Key material
#: for every extractor at v5+, so the WHOLE OCR cache goes cold at the train's
#: cold run (required anyway: every native document is re-read once to attach
#: its evidence). A schema-2 record (no `native_evidence*` keys) restores with
#: `native_evidence=None` and analyses — never a crash on an old cache entry.
#: `to_markdown()` is byte-identical with or without the field.
EXTRACTION_SCHEMA_VERSION = 3

STAGE_OCR = "ocr"
STAGE_ANALYSIS = "analysis"
STAGE_REPORT = "report"

#: P21-ROUTING closure (MAJOR-1). The one member of :class:`CacheResult`'s
#: ``finding`` vocabulary today: a cached OCR entry's ``evidence`` /
#: ``page_extractor`` failed the round-trip / consistency check
#: `cached_ocr` itself enforces on every restore, so the entry was treated as
#: a miss and recomputed rather than served.
CACHE_FINDING_EVIDENCE_DRIFT = "cached_evidence_drift"

T = TypeVar("T")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def text_sha256(text: str) -> str:
    """UPPERCASE hex SHA-256 of a string's UTF-8 bytes — the same convention
    as ``content_sha256`` for raw bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _fingerprint(settings: dict[str, Any]) -> str:
    return text_sha256(_canonical_json(settings))


def sheets_sha256(sheets: Sequence[str] | None) -> str | None:
    """A digest over the intake page PARTITION, or ``None`` for no page list.

    ``None`` and ``[]`` are different facts and hash differently: no evidence of
    page structure is not the same as a document with no sheets, and the
    analysis fail-closes on the first while the second is a real (if degenerate)
    partition.

    Per-sheet digests rather than the concatenated text, because the whole point
    is the BOUNDARIES: ``["ab", "c"]`` and ``["a", "bc"]`` must not collide, and
    joining them would make them identical. Sheet text is hashed rather than
    embedded so that key material stays bounded whatever the document's size.

    ORDER IS KEY MATERIAL, deliberately. ``["a", "b"]`` and ``["b", "a"]`` hash
    differently although both render to the same markdown under a caller that
    reordered them, so three sheets have six permutations and six keys for one
    answer. That is over-partitioning, which this module's contract says is the
    safe direction: it costs a recompute and never returns a stale artifact.
    It is also unreachable in production — the markdown is rendered from the
    same ordered list that is hashed here — so the cost is theoretical and the
    conservatism is free.

    THE ACCEPTED TYPE is a re-iterable sequence of ``str``, and everything else
    is refused rather than coerced. Three ways a call site can get this wrong,
    all of them silent without the guards:

    * ``str`` — refused for the same reason ``assess_document_integrity``
      refuses it: ``str`` is itself a ``Sequence[str]``, so ``sheets=markdown``
      type-checks and then iterates one CHARACTER per sheet. There it would
      clear a fraud-relevant flag; here it would partition the cache by
      something meaningless.
    * a one-shot iterable (generator, map, zip, an exhausted iterator) —
      refused because hashing CONSUMES it, and the caller then hands the
      analysis an empty sequence. The analysis fail-closes on that, so the
      answer is conservative, but it is stored under the key of a partition
      that WAS proven: a later caller supplying the same pages properly gets
      served the fail-closed answer. Nothing in the payload looks wrong, which
      is what makes it worth a refusal rather than a note.
    * non-``str`` members — refused with a message that names the offender,
      because the alternative is an ``AttributeError`` from inside
      ``text_sha256`` with no indication of which call site is at fault.

    Only a call site can reach any of these — no document's content can — so
    raising costs nothing at runtime and fails a mis-wiring loudly.
    """
    if sheets is None:
        return None
    if isinstance(sheets, str):
        raise TypeError(
            "sheets must be the intake object's page list, not the document "
            "text: a str is a Sequence[str] of single characters"
        )
    if not isinstance(sheets, Sequence):
        raise TypeError(
            "sheets must be a re-iterable sequence of page strings, not a "
            f"one-shot iterable ({type(sheets).__name__}): hashing it here "
            "would consume it and leave the analysis with no page structure"
        )
    for index, sheet in enumerate(sheets):
        if not isinstance(sheet, str):
            raise TypeError(
                f"sheets[{index}] is {type(sheet).__name__}, not a page string"
            )
    return text_sha256(_canonical_json([text_sha256(sheet) for sheet in sheets]))


def _is_sha256_hex(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789ABCDEFabcdef" for c in value)


def analysis_input_sha(
    markdown: str, sheets: Sequence[str] | None = None, *, evidence_sha256: str | None = None,
) -> str:
    """The analysis stage's input hash: the admissible text, the page partition,
    and — when the analysis was fed geometry — the sha of the evidence it
    came from (P22-IDENTITY, Phase 2.2, D6).

    THE one place this is derived. The telemetry observer (under ``telemetry/``)
    reconstructs the same document out of the OCR artifact and must resolve the
    same key, and a second copy of this composition is exactly the drift the
    FILENAME-BOUNDARY lesson warned about — an instrument that goes blind while
    reporting nothing wrong. Import this; do not re-derive it.

    ``evidence_sha256`` is the `evidence_sha256` of the canonical evidence a
    `DocumentGeometry` handed to `analyze_document` was built from (a native
    read's `native_evidence`, or a Paddle read's `evidence`), or ``None`` for a
    text-only analysis. A geometry-fed analysis therefore hashes DIFFERENTLY
    from a text-only analysis of the same markdown — the geometry-blind key
    was the named stale-cache hazard (two artifacts with identical page
    strings and different word boxes, or one with evidence and one without,
    resolved to the same key). The material carries an ``"evidence"`` field
    ONLY when a sha is given: a text-only call hashes exactly the two-field
    composition every run of record before this cell wrote, so
    ``tools/cohort_replay.py`` and the telemetry observer's artifact join —
    which look historical analysis artifacts up by THIS function with no
    version parameter — keep resolving them (the card's literal
    ``"no-geometry"`` is deliberately not hashed for that reason; see the
    cell's W3 section). A
    stage-17 text-only artifact and a stage-18 one still never collide: the
    stage version is settings-key material. A malformed sha (anything but
    ``None`` or 64 hex characters — in particular the empty string, which
    would silently mean "geometry-fed, no lineage") is refused.
    """
    material: dict[str, Any] = {
        "text": text_sha256(admissible_text(markdown)),
        "sheets": sheets_sha256(sheets),
    }
    if evidence_sha256 is not None:
        if not _is_sha256_hex(evidence_sha256):
            raise ValueError(
                "evidence_sha256 must be None (text-only analysis) or a 64-character "
                "hex digest of the evidence that fed geometry"
            )
        material["evidence"] = evidence_sha256.upper()
    return text_sha256(_canonical_json(material))


def cache_key(stage: str, input_sha256: str, settings_key: str) -> str:
    """The composed key. See the module docstring for the exact fields."""
    return text_sha256(
        _canonical_json(
            {
                "cache_format": CACHE_FORMAT_VERSION,
                "stage": stage,
                "input": input_sha256,
                "settings": settings_key,
            }
        )
    )


# ----------------------------------------------------------------------
# settings fingerprints — one function per stage, each enumerating exactly
# the knobs that can change that stage's output
# ----------------------------------------------------------------------


#: Pinned values of the legacy OCR postprocess chain's quarantine state (the
#: retired visual OCR client's `POSTPROCESS_STATE` / `ADMITTED_POSTPROCESS`,
#: cell B1). FROZEN KEY MATERIAL since slice S2 of the model-code removal: the
#: client is gone, and these are the values it held ("quarantined", nothing
#: admitted; proven equal at the S1 head before it was deleted), so every
#: extractor label's key keeps exactly the material it always had.
POSTPROCESS_STATE_DEFAULT = "quarantined"
ADMITTED_POSTPROCESS_DEFAULT: tuple[str, ...] = ()

#: FROZEN KEY MATERIAL (model-code removal, slice S2; plan D3). The visual OCR
#: service knobs `ocr_settings_key` has always hashed when no ``ocr_settings``
#: is passed: the defaults `ocr.config.load_settings()` produced on an
#: environment that set none of OCR_MODEL / OCR_BASE_URL / OCR_NGRAM_SIZE /
#: OCR_WINDOW_SIZE, with the endpoint class that base URL classified as. The
#: client and its settings are gone (owner ruling of 2026-10-13: the product
#: uses no model), but dropping or changing any of these fields would re-key
#: every cached reading, Tesseract ones included, so they stay as literals.
#: They name an endpoint and a model that no longer exist; they are key
#: material only, read by nothing else. Those four environment names no longer
#: move the key (declared in the S2 report).
@dataclass(frozen=True)
class _FrozenOcrSettings:
    """The frozen stand-in `ocr_settings_key` reads when no ``ocr_settings`` is
    passed: the same five attributes, by `getattr`, as an explicitly passed
    settings object (the historical reconstructions in
    `telemetry/run_of_record.py` and `tools/train/provenance.py`)."""

    model: str = "baidu/Unlimited-OCR"
    base_url: str = "http://localhost:8000/v1"
    ngram_size: int = 35
    window_size: int = 128
    endpoint_class: str = "loopback"


FROZEN_OCR_SETTINGS = _FrozenOcrSettings()

#: FROZEN KEY MATERIAL (model-code removal, slice S3; plan D3). The three
#: analysis-key fields that described the hosted extractor and its opt-in:
#: the defaults `analysis.config.load_settings()` produced on an environment
#: that set neither GEMINI_MODEL nor GEMINI_ESCALATION_MODEL, and the opt-in
#: absent. The extractor and the opt-in are gone; dropping or changing any of
#: these would re-key every stored analysis, so `analysis_settings_key` writes
#: them as these literals for every call. They name models nothing calls; they
#: are key material only, read by nothing else. GEMINI_MODEL,
#: GEMINI_ESCALATION_MODEL and HOSTED_EXTRACTION_OPT_IN no longer move the key
#: (declared in the S3 report).
FROZEN_ANALYSIS_MODEL = "gemini-3.5-flash-lite"
FROZEN_ANALYSIS_ESCALATION_MODEL = "gemini-3.5-flash"
FROZEN_HOSTED_EXTRACTION_OPT_IN = False

#: Model-code removal, slice S4: the fixed refusal of a key or cached read that
#: asks for the retired visual pair's partition (`allow_visual_pair=True`). The
#: pair and its settings (`ocr/visual_pair_config.py`) are gone, so that
#: partition's key cannot be computed; its stored readings are left orphaned.
VISUAL_PAIR_RETIRED = "the visual pair was removed: no OCR key has a visual-pair partition any more"

#: A pinned duplicate of ``ocr.rasterize.RASTER_VERSION`` (review MINOR-1).
#: ``ocr/rasterize.py`` imports ``pdf2image`` + ``PIL`` at module level, so an
#: unguarded ``from ocr.rasterize import RASTER_VERSION`` would let a missing
#: rasterization backend raise ``ModuleNotFoundError`` out of every OCR cache
#: lookup — for the sake of one integer, and in violation of the same
#: "never raises" discipline :func:`ocr_toolchain_versions` already keeps.
#: :func:`ocr_settings_key` tries the real import first and falls back to
#: this duplicate only on ``ImportError``; ``test_raster_version_fallback_matches_the_source_module``
#: pins that the two never drift apart.
_RASTER_VERSION_FALLBACK = 2

_toolchain_versions_cache: dict[str, str] | None = None

#: P22-IDENTITY (Phase 2.2, D7): the closed shape of a research partition id
#: — a short label (letters, digits, `.`, `_`, `-`; up to 64 characters) an
#: operator names on `discovery --research-paddle --research-partition <id>`
#: and `tools/train/provenance.py --research-partition <id>`. Key material
#: when non-empty; written verbatim into `provenance.json`, so the charset
#: is closed the way every provenance token's is.
_RESEARCH_PARTITION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def _validate_research_partition(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("research_partition must be a str (empty for production)")
    if value == "":
        return ""
    if _RESEARCH_PARTITION_RE.fullmatch(value) is None:  # fullmatch: `$` would admit a trailing newline
        raise ValueError(
            "research_partition must match [A-Za-z0-9][A-Za-z0-9._-]{0,63} (or be empty for production)"
        )
    return value


def _ocr_extractor(
    *, force_ocr: bool, allow_local_ocr: bool, allow_visual_ocr: bool,
    allow_paddle_ocr: bool = False,
) -> str:
    """The extractor stack a call names — ONE function, pinned (F-6/§10).

    ``"paddle"`` for the forced-Paddle call shape (``force_ocr=True`` AND
    ``allow_paddle_ocr=True`` — discovery's Paddle rung,
    `discovery/runner.py::_read_paddle`, P21-ROUTING); ``"visual"`` for the
    forced-escalation call shape (``force_ocr=True`` AND
    ``allow_visual_ocr=True`` — discovery's retired visual rung, deleted in
    slice S2 of the model-code removal; the label stays so historical
    reconstructions still compute that partition's key). Every other shape,
    including the old ambiguous "auto" call (``force_ocr=False``,
    ``allow_visual_ocr=True``), is ``"offline"`` — the offline ladder is what
    CAN run, whatever eventually does. ``allow_local_ocr`` does not enter the decision: it already
    partitions the key on its own (native vs local-Tesseract share one
    "offline" label and one settings key, exactly as they always have).

    **This field cannot partition the key on its own, and no test should
    claim it does (review BLOCK-1).** It is a TOTAL function of ``force_ocr``,
    ``allow_visual_ocr`` and ``allow_paddle_ocr``, all of which are ALREADY
    key material -- any input that changes ``extractor`` necessarily changes
    one of those fields too, so ``extractor`` is a LEGIBILITY / extensibility
    slot (a human- and log-readable label), not additional partitioning
    power. What IS pinned, and is the honest proof for this function, is the
    truth table ``test_extractor_is_visual_only_for_the_forced_escalation_shape``
    (and its Paddle counterpart) exercise directly. ``parse_statement`` itself
    refuses ``allow_paddle_ocr and allow_visual_ocr`` together, so the two
    forced branches here are mutually exclusive in every call this codebase
    actually makes; ``"paddle"`` is checked first only so a hand-built,
    contract-violating call resolves to a defined answer rather than an
    unspecified one."""
    if force_ocr and allow_paddle_ocr:
        return "paddle"
    return "visual" if (force_ocr and allow_visual_ocr) else "offline"


def _ocr_postprocess_readout(extractor: str) -> tuple[str, tuple[str, ...]]:
    """``(postprocess_state, postprocess_admitted)`` for the OCR settings key.

    The frozen pinned values for EVERY extractor label (model-code removal,
    slice S2). A ``"visual"``-labelled key used to read them off the legacy
    client (`ocr.ocr_client`), whose module-level constants always equalled
    these pins; the client is gone, so the visual partition's key — still
    computed for historical reconstruction (`telemetry/run_of_record.py`,
    `tools/train/provenance.py`) — keeps exactly the material it had."""
    del extractor  # every label reads the same frozen pins
    return POSTPROCESS_STATE_DEFAULT, ADMITTED_POSTPROCESS_DEFAULT


def ocr_toolchain_versions() -> dict[str, str]:
    """``{"tesseract_version", "poppler_version", "pymupdf_version"}`` (F-6).

    Never raises; a version that cannot be read is the sentinel
    ``"unknown"``, which partitions the OCR settings key CONSERVATIVELY (a
    fresh key, a re-read) rather than silently reusing an artifact a
    different binary produced. Shells out to the `tesseract` / `pdftoppm`
    executables and imports PyMuPDF (`fitz`) — already an offline-rung
    dependency (`ocr/local_tesseract.py`, `ocr/native_text.py`), not the
    model client this module otherwise keeps out of the offline path.
    Computed once per process and cached: this is a settings-key input read
    on every OCR cache lookup, not a per-page cost."""
    global _toolchain_versions_cache
    if _toolchain_versions_cache is not None:
        return dict(_toolchain_versions_cache)
    versions = {
        "tesseract_version": "unknown",
        "poppler_version": "unknown",
        "pymupdf_version": "unknown",
    }
    import shutil
    import subprocess

    try:
        tesseract = shutil.which("tesseract")
        if tesseract:
            completed = subprocess.run(
                [tesseract, "--version"], capture_output=True, text=True, timeout=10
            )
            first = next(
                (line.strip() for line in (completed.stdout + "\n" + completed.stderr).splitlines()
                 if line.strip()),
                None,
            )
            if first:
                versions["tesseract_version"] = first
    except Exception:  # never raises: an unreadable version is "unknown"
        pass
    try:
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm:
            completed = subprocess.run(
                [pdftoppm, "-v"], capture_output=True, text=True, timeout=10
            )
            first = next(
                (line.strip() for line in (completed.stderr + "\n" + completed.stdout).splitlines()
                 if line.strip()),
                None,
            )
            if first:
                versions["poppler_version"] = first
    except Exception:
        pass
    try:
        import fitz  # PyMuPDF

        versions["pymupdf_version"] = str(
            getattr(fitz, "VersionBind", None) or getattr(fitz, "version", None) or "unknown"
        )
    except Exception:
        pass
    _toolchain_versions_cache = versions
    return dict(versions)


def ocr_settings_key(
    *,
    force_ocr: bool = False,
    allow_local_ocr: bool = False,
    allow_visual_ocr: bool = True,
    allow_paddle_ocr: bool = False,
    allow_visual_pair: bool = False,
    visual_pair_settings: Any | None = None,
    dpi: int = 300,
    fallback_dpi: int | None = 250,
    ocr_settings: Any | None = None,
    stage_version: int | None = None,
    research_partition: str = "",
) -> str:
    """Fingerprint of every knob that changes OCR output.

    ``research_partition`` (P22-IDENTITY, Phase 2.2, D7): empty for every
    production call — and then NOT in the material at all, so the production
    key is byte-identical to a call that never heard of the field; a
    non-empty id (closed shape, `_RESEARCH_PARTITION_RE`) is key material of
    its own partition, so a research run's artifacts can never collide with
    production's, and `telemetry/run_of_record.py` refuses a run recorded
    under one as historical truth.

    ``ocr_settings`` is anything with the attributes ``model``, ``base_url``,
    ``ngram_size``, ``window_size`` and ``endpoint_class``, read by
    ``getattr`` (the historical reconstructions in
    ``telemetry/run_of_record.py`` and ``tools/train/provenance.py`` pass
    one). When omitted, the frozen :data:`FROZEN_OCR_SETTINGS` literals are
    hashed: the defaults the retired ``ocr.config.load_settings()`` produced,
    so every key on a default environment is unchanged, and the environment
    no longer moves it (model-code removal, slice S2).

    ``stage_version`` defaults to the live :data:`OCR_STAGE_VERSION` (5+: the
    v5 key material below is included). Passing an EXPLICIT older version
    reconstructs the key EXACTLY as that version computed it — in particular,
    passing ``4`` reproduces the pre-P20-ARTIFACTS 9-field key byte-for-byte,
    with none of the v5 fields present, because at v4 they did not exist. This
    is what lets ``telemetry/run_of_record.py`` reconstruct a historical run's
    own OCR key (batch 8, batch 9) rather than recompute today's shape under
    yesterday's version number — the two are not the same key.

    ``allow_visual_pair=True`` RAISES ``ValueError`` (model-code removal,
    slice S4): the visual pair was removed, so no key names its partition any
    more and its stored readings are orphaned, never re-keyed into a
    deterministic partition. The parameter and its ``False`` default stay
    (``False`` never entered the material, so every other key is unchanged);
    ``visual_pair_settings`` was read only on that branch and is ignored. A
    stored reading that carries ``visual_pair`` evidence still restores
    through :func:`cached_ocr`, which re-verifies its hash."""
    if allow_visual_pair:
        raise ValueError(VISUAL_PAIR_RETIRED)
    del visual_pair_settings  # read only by the retired visual-pair branch
    if ocr_settings is None:
        # Frozen key material (plan D3): never read from the environment.
        ocr_settings = FROZEN_OCR_SETTINGS
    version = OCR_STAGE_VERSION if stage_version is None else int(stage_version)
    partition = _validate_research_partition(research_partition)
    if partition and version < 5:
        # P22-IDENTITY closure-2 (review F-4): a pre-v5 key has no partition
        # field; silently dropping a research partition there would hand a
        # research run a production-shaped key. Refuse instead — a pre-v5
        # run never carried one, so this is unreachable on a real record.
        raise ValueError(
            "research_partition requires OCR stage version 5 or later; a pre-v5 key cannot carry one"
        )
    settings: dict[str, Any] = {
        "stage_version": version,
        "force_ocr": bool(force_ocr),
        "allow_local_ocr": bool(allow_local_ocr),
        "allow_visual_ocr": bool(allow_visual_ocr),
        "dpi": int(dpi),
        "fallback_dpi": None if fallback_dpi is None else int(fallback_dpi),
        "ocr_model": str(getattr(ocr_settings, "model", "")),
        "ocr_base_url": str(getattr(ocr_settings, "base_url", "")),
        "ngram_size": int(getattr(ocr_settings, "ngram_size", 0)),
        "window_size": int(getattr(ocr_settings, "window_size", 0)),
    }
    if version >= 5:
        extractor = _ocr_extractor(
            force_ocr=force_ocr, allow_local_ocr=allow_local_ocr,
            allow_visual_ocr=allow_visual_ocr, allow_paddle_ocr=allow_paddle_ocr,
        )
        postprocess_state, postprocess_admitted = _ocr_postprocess_readout(extractor)
        try:
            from ocr.rasterize import RASTER_VERSION as _raster_version
        except ImportError:  # pdf2image/PIL missing (MINOR-1): never raise for one integer
            _raster_version = _RASTER_VERSION_FALLBACK

        toolchain = ocr_toolchain_versions()
        settings.update(
            {
                "extractor": extractor,
                # P21-ROUTING: a boolean partition field, like the other
                # three capability flags above — always present at v5+
                # (never only under `extractor == "paddle"`), so the offline
                # and visual partitions partition on it too (accepted; see
                # EXTRACTION_SCHEMA_VERSION's docstring).
                "allow_paddle_ocr": bool(allow_paddle_ocr),
                "postprocess_state": postprocess_state,
                "postprocess_admitted": list(postprocess_admitted),
                "raster_version": int(_raster_version),
                "extraction_schema_version": int(EXTRACTION_SCHEMA_VERSION),
                "endpoint_class": str(getattr(ocr_settings, "endpoint_class", "loopback")),
                "tesseract_version": toolchain["tesseract_version"],
                "poppler_version": toolchain["poppler_version"],
                "pymupdf_version": toolchain["pymupdf_version"],
            }
        )
        if partition:
            # D7: present ONLY when non-empty — see the docstring. Every
            # extractor label gets its own research partition.
            settings["research_partition"] = partition
        if extractor == "paddle":
            # Lazy import: the offline and visual partitions' keys must
            # never touch Paddle settings at all (asserted by test) — only a
            # paddle-labelled call reaches this branch. A Paddle read whose
            # settings CANNOT be loaded (no env) REFUSES here rather than
            # falling back to a default block: `PaddleConfigError` propagates
            # unchanged, exactly as the rung itself refuses before any
            # request (D5, design item 5).
            from ocr.paddle_config import load_paddle_settings, paddle_settings_key_material

            settings["paddle"] = paddle_settings_key_material(load_paddle_settings())
    return _fingerprint(settings)


def analysis_settings_key(
    *, parse_mode: str = "auto", analysis_settings: Any | None = None
) -> str:
    """Fingerprint of every knob that changes extraction/analysis output.

    Includes the PARSER REGISTRY's fingerprint (W3 §REGFP). The registry is a
    per-RUN constant — one registration set serves every document of a run — so
    it belongs here and not in the input hash. WIRING-2's lesson was the exact
    inverse and is worth stating next to it: the page partition is per-DOCUMENT
    and therefore had to go into :func:`analysis_input_sha`, because a
    per-document value in the settings key would have shattered the telemetry
    join's one-value index and blinded it. A per-run value in the input hash
    would be the opposite mistake — recomputed identically for every document
    and unable to invalidate anything.

    ``registry_fingerprint`` is imported, never recomposed, for the reason the
    module docstring gives about :func:`analysis_input_sha`: telemetry's
    ``_ArtifactJoin`` reconstructs THIS key to find a run's payloads, and a
    second derivation anywhere would go blind while reporting nothing wrong.
    It also loads the production registry if the calling process has not — see
    ``analysis.parser_registry._ensure_registry_loaded``.

    ``reconstruction_mode`` (P22-IDENTITY, Phase 2.2, D6) is
    ``Settings.reconstruction_mode`` — the closed vocabulary ``off | research |
    production`` that decides whether the generic rung runs and, later, in
    what capacity; it partitions the key exactly as ``parse_mode`` does.
    ``generic_structurer`` is derived from the SAME settings object through
    ``structurer_enabled(analysis_settings)``: the structurer owns what
    "enabled" means, and reading the mode here and the flag there from two
    different sources would let the key and the rung disagree. The retired
    ``GENERIC_STRUCTURER_ENABLED`` variable is not consulted at all.

    FROZEN KEY MATERIAL (model-code removal, slice S3; plan D3). ``model``
    ``"gemini-3.5-flash-lite"``, ``escalation_model`` ``"gemini-3.5-flash"``
    and ``hosted_extraction_opt_in`` ``False`` are literals for EVERY call,
    including one that passes a settings object. They named the hosted
    extractor (``analysis/extract.py``) and its operator opt-in, both removed:
    nothing they described can change an analysis any more, but dropping or
    changing any of them would re-key every stored analysis. The literals are
    the values every default environment wrote (``analysis.config.
    load_settings``'s defaults, and the opt-in absent), so every entry in the
    archive keeps its key. Only a process that had overridden ``GEMINI_MODEL``
    / ``GEMINI_ESCALATION_MODEL`` or set the exact opt-in literal re-keys once,
    under these frozen defaults (declared). ``parse_mode`` stays real key
    material: Auto and Deterministic only read alike now, and are still cached
    apart, as they always were.
    """
    if analysis_settings is None:
        from analysis.config import load_settings as _load_analysis_settings

        analysis_settings = _load_analysis_settings()
    # Function-local, like ``analysis.config``: importing this module must stay
    # cheap, and the structurer package is only needed when a key is derived.
    from analysis.structurer import structurer_enabled
    return _fingerprint(
        {
            "stage_version": ANALYSIS_STAGE_VERSION,
            "parse_mode": str(parse_mode),
            # Frozen key material (see the docstring): never read from
            # ``analysis_settings`` or the environment.
            "model": FROZEN_ANALYSIS_MODEL,
            "escalation_model": FROZEN_ANALYSIS_ESCALATION_MODEL,
            "withholding_denominator_mode": str(
                getattr(analysis_settings, "withholding_denominator_mode", "")
            ),
            "parser_registry": registry_fingerprint(),
            "reconstruction_mode": str(getattr(analysis_settings, "reconstruction_mode", "off")),
            "generic_structurer": bool(structurer_enabled(analysis_settings)),
            # Frozen key material: the removed opt-in was never set by any
            # default environment.
            "hosted_extraction_opt_in": FROZEN_HOSTED_EXTRACTION_OPT_IN,
        }
    )


def report_settings_key(*, title: str = "") -> str:
    """Fingerprint of every knob that changes the rendered report artifact."""
    return _fingerprint({"stage_version": REPORT_STAGE_VERSION, "title": str(title)})


@dataclass(frozen=True)
class CacheResult:
    """What a memoizing wrapper returns.

    ``cached`` is the whole proof surface: ``True`` means ``compute`` was never
    called, i.e. zero OCR / zero LLM work for this stage.

    ``finding`` (P21-ROUTING closure, MAJOR-1) is ``None`` on every ordinary
    hit, miss or bypass, and a closed-vocabulary string when the wrapper
    observed something worth a caller's attention DESPITE resolving the call
    normally — today the only member is ``"cached_evidence_drift"``
    (:func:`cached_ocr`'s cached ``evidence``/``page_extractor`` failed its own
    round-trip check, so the entry was treated as a miss and recomputed). This
    is what keeps "the artifact was corrupt and we recomputed it" from being
    indistinguishable from "this was never cached at all" once the recompute
    overwrites the drifted entry: the finding travels out of the function on
    the SAME return value the caller already reads, so it cannot be dropped
    by a caller that only checks ``cached``."""

    value: Any
    cached: bool
    stage: str
    cache_key: str | None
    finding: str | None = None


class ArtifactCache:
    """Read/write access to the content-addressed artifact store.

    One instance per data directory. Safe to construct repeatedly (it owns no
    connection; ``Storage`` opens one per call), and safe to share between the
    request threads and the single worker thread under the same single-writer
    discipline documented in ``webapp/storage.py``.
    """

    def __init__(
        self, storage: Storage | None = None, data_dir: str | Path | None = None
    ) -> None:
        if storage is None:
            storage = Storage(data_dir)
        elif data_dir is not None:
            raise ValueError("pass either a Storage or a data_dir, not both")
        self.storage = storage
        self.root = storage.artifact_root()

    # -- payload files -------------------------------------------------

    def _artifact_path(self, stage: str, key: str) -> Path:
        # Two-character shard: a flat directory of millions of discovery
        # artifacts is hostile to every filesystem tool.
        return self.root / stage / key[:2] / f"{key}.json"

    def _write_payload(self, path: Path, payload: dict) -> int:
        """Write a payload file through a temporary file of its own and rename it into place (audit 2026-10-13,
        BE-4): one fixed ``<key>.json.tmp`` was shared by every writer of a key, so two writers of the same entry at
        once (a CLI pointed at a live server's data directory) could fail each other. The rename is retried briefly
        on the Windows refusal while a reader has the target open; the temporary file is always removed. The
        temporary name ends in ``.tmp``, so nothing that lists ``*.json`` payloads ever sees it."""
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = _canonical_json(payload).encode("utf-8")
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem[:16]}-", suffix=".json.tmp")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(blob)
            _replace_retrying(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return len(blob)

    # -- generic get/put -----------------------------------------------

    def get(self, stage: str, input_sha256: str, settings_key: str) -> dict | None:
        """The cached payload envelope, or None on a miss.

        A row whose payload file is missing or unreadable is a MISS and the
        row is dropped, so a half-deleted data directory self-heals."""
        key = cache_key(stage, input_sha256, settings_key)
        row = self.storage.cache_lookup(stage, key)
        if row is None:
            return None
        path = self.root / row["artifact_path"]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.storage.cache_forget(stage, key)
            return None
        if not isinstance(payload, dict) or payload.get("cache_format") != CACHE_FORMAT_VERSION:
            self.storage.cache_forget(stage, key)
            return None
        self.storage.cache_record_hit(stage, key)
        return payload

    def put(
        self, stage: str, input_sha256: str, settings_key: str, artifact: dict
    ) -> str:
        """Write an artifact and index it. Returns the cache key."""
        key = cache_key(stage, input_sha256, settings_key)
        path = self._artifact_path(stage, key)
        payload = {
            "cache_format": CACHE_FORMAT_VERSION,
            "stage": stage,
            "input_sha256": input_sha256,
            "settings_key": settings_key,
            "artifact": artifact,
        }
        byte_size = self._write_payload(path, payload)
        self.storage.cache_record(
            stage,
            key,
            input_sha256=input_sha256,
            settings_key=settings_key,
            artifact_path=str(path.relative_to(self.root)),
            byte_size=byte_size,
            format_version=CACHE_FORMAT_VERSION,
        )
        return key

    # -- stage-typed helpers -------------------------------------------

    def get_ocr(self, content_hash: str, settings_key: str) -> tuple[bool, dict | None]:
        """``(hit, document_dict_or_None)``. The second element is ``None``
        both on a miss and on a cached NEGATIVE result, so the hit flag is the
        one that decides whether to call the ladder."""
        payload = self.get(STAGE_OCR, content_hash, settings_key)
        if payload is None:
            return False, None
        return True, payload["artifact"].get("document")

    def put_ocr(
        self, content_hash: str, settings_key: str, document: StatementMarkdown | None
    ) -> str:
        """Store an OCR result. Everything a consumer of ``StatementMarkdown``
        can observe is stored: model, pages, O-3's per-page integrity
        records, and (P21-ROUTING, D6) ``page_extractor`` / ``evidence`` — a
        cached read is not allowed to be a read with any of these quietly
        missing. ``pages`` is normalized to plain ``str`` because the visual
        rung's ``PageText`` carries only the model-side signals already
        distilled into ``page_integrity``.

        ``page_integrity`` / ``page_extractor`` are read through ``getattr``
        — the same tolerance O-3 built into its own readers — so a
        document-shaped object that predates a field (a hand-built extractor
        result, a test double) stores as "not assessed" / "not populated"
        instead of raising. ``evidence`` serializes via
        ``evidence.canonical.to_json`` when present, else ``None``.

        P22-IDENTITY (D5, schema 3): ``native_evidence`` serializes the same
        way, and ``native_evidence_sha256`` stores its sha BESIDE it — the
        sha a restore must reproduce byte-for-byte and re-verify against.

        ``visual_pair`` / ``visual_pair_sha256`` are written only for a
        document that carries visual-pair evidence. No reader produces one
        since the pair was removed (model-code removal, slice S4); the shape
        stays unchanged so the artifact format, and every stored reading, is
        exactly what it was."""
        evidence = getattr(document, "evidence", None) if document is not None else None
        native_evidence = getattr(document, "native_evidence", None) if document is not None else None
        return self.put(
            STAGE_OCR,
            content_hash,
            settings_key,
            {
                "document": None
                if document is None
                else {
                    "model": document.model,
                    **({"visual_pair": document.visual_pair,
                        "visual_pair_sha256": _fingerprint(document.visual_pair)}
                       if getattr(document, "visual_pair", None) is not None else {}),
                    "pages": [str(page) for page in document.pages],
                    "page_integrity": [
                        item.to_dict()
                        for item in (getattr(document, "page_integrity", None) or [])
                    ],
                    "page_extractor": list(getattr(document, "page_extractor", None) or []),
                    "evidence": to_json(evidence) if evidence is not None else None,
                    "native_evidence": to_json(native_evidence) if native_evidence is not None else None,
                    "native_evidence_sha256": (
                        native_evidence.evidence_sha256 if native_evidence is not None else None
                    ),
                }
            },
        )

    def get_analysis(self, markdown_hash: str, settings_key: str) -> dict | None:
        payload = self.get(STAGE_ANALYSIS, markdown_hash, settings_key)
        return None if payload is None else payload["artifact"]["analysis"]

    def put_analysis(self, markdown_hash: str, settings_key: str, analysis: dict) -> str:
        return self.put(STAGE_ANALYSIS, markdown_hash, settings_key, {"analysis": analysis})

    def get_report(self, markdown_hash: str, settings_key: str) -> str | None:
        payload = self.get(STAGE_REPORT, markdown_hash, settings_key)
        return None if payload is None else payload["artifact"]["html"]

    def put_report(self, markdown_hash: str, settings_key: str, html: str) -> str:
        return self.put(STAGE_REPORT, markdown_hash, settings_key, {"html": html})

    # -- reporting -----------------------------------------------------

    def stats(self) -> dict[str, dict[str, int]]:
        """Per-stage ``{entries, bytes, hits}`` — the discovery runner's
        cache-effectiveness report in one call."""
        return self.storage.cache_stats()


def open_cache(data_dir: str | Path | None = None) -> ArtifactCache:
    """Open (creating if needed) the artifact cache for a data directory.

    ``data_dir=None`` uses the ``WEBAPP_DATA_DIR`` convention, so a CLI run and
    the dashboard share one cache by default. This is the entry point CLI
    consumers should call."""
    return ArtifactCache(Storage(data_dir))


# ----------------------------------------------------------------------
# memoizing wrappers — the API the worker and the CLI both call
# ----------------------------------------------------------------------


def _page_integrity(entries: object) -> list[PageIntegrity]:
    """Rebuild O-3 ``PageIntegrity`` records from a cached OCR artifact.

    Read defensively (missing keys default to the dataclass's own "no
    evidence" values) so a payload written by an older shape degrades to an
    unflagged record rather than raising — though the OCR stage version is
    what actually keeps such payloads from being served at all."""
    rebuilt: list[PageIntegrity] = []
    for index, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        rebuilt.append(
            PageIntegrity(
                page_index=int(entry.get("page_index", index)),
                truncated=bool(entry.get("truncated", False)),
                signals=list(entry.get("signals") or []),
                finish_reason=entry.get("finish_reason"),
            )
        )
    return rebuilt


def _restore_native_evidence(document: dict):
    """The record's ``native_evidence`` rebuilt (P22-IDENTITY, D5), or
    ``None`` for a schema-2 record. Raises ``EvidenceError`` — the drift
    class :func:`cached_ocr` turns into a miss-with-finding — when the blob
    does not reproduce the sha the record claims in ``native_evidence_sha256``
    (M6: a restore without this re-verification would serve a blob whose
    self-hash happens to hold beside a stale sidecar sha), or when a sidecar
    sha is stored with no blob to back it."""
    payload = document.get("native_evidence")
    claimed = document.get("native_evidence_sha256")
    if payload is None:
        if claimed:
            raise EvidenceError("native_evidence_sha256 stored without its native_evidence")
        return None
    restored = from_json(payload)
    if not isinstance(claimed, str) or restored.evidence_sha256 != claimed:
        raise EvidenceError("native_evidence does not reproduce the record's native_evidence_sha256")
    return restored


def cached_ocr(
    pdf_bytes: bytes,
    *,
    compute: Callable[[], StatementMarkdown | None],
    cache: ArtifactCache | None = None,
    source_file: str = "",
    content_hash: str | None = None,
    force_ocr: bool = False,
    allow_local_ocr: bool = False,
    allow_visual_ocr: bool = True,
    allow_paddle_ocr: bool = False,
    allow_visual_pair: bool = False,
    visual_pair_settings: Any | None = None,
    dpi: int = 300,
    fallback_dpi: int | None = 250,
    ocr_settings: Any | None = None,
    research_partition: str = "",
) -> CacheResult:
    """Memoize one intake-ladder run over ``pdf_bytes``.

    ``research_partition`` (P22-IDENTITY, D7) is threaded to
    :func:`ocr_settings_key` unchanged: empty for production, a partition id
    for a research run (which also writes to its own data directory).

    P22-IDENTITY (D5): a hit restores ``native_evidence`` too and RE-VERIFIES
    its sha against the record's own ``native_evidence_sha256`` — a blob that
    reproduces some sha is not enough; it must reproduce the sha the record
    claims — and a sha stored without its blob is a drift as well. Either
    mismatch is the same miss-with-finding as a drifted ``evidence``. A
    schema-2 record (neither key present) restores with
    ``native_evidence=None``.

    The capability flags must mirror the ``ocr.pipeline.parse_statement`` call
    that ``compute`` performs — they are the cache key, so a mismatch would
    serve one rung's output for another's.

    A NEGATIVE outcome (the deterministic preflight returning ``None``) is
    cached too: it is a deterministic function of the same bytes and settings,
    and not caching it would leave the local-Tesseract rung re-running on every
    re-upload of a scan.

    ``content_hash`` may be supplied when the caller already computed it (the
    webapp has it from the O-1 preflight profile) to avoid re-hashing.

    P21-ROUTING (D6): a hit also restores ``page_extractor`` and ``evidence``
    (``evidence.canonical.from_json``). A payload whose stored evidence does
    not round-trip (its own hash does not reproduce, or the reconstructed
    ``StatementMarkdown`` refuses the page-count/page-text consistency check)
    is a DRIFTED cached copy — surfaced as a cache MISS, never served: this
    function falls through to a fresh ``compute()`` exactly as an actual miss
    would, and overwrites the drifted entry with the freshly computed one.

    P21-ROUTING closure (MAJOR-1): a drift is also a FINDING, not only a
    miss. The returned :class:`CacheResult` carries
    ``finding=CACHE_FINDING_EVIDENCE_DRIFT`` on exactly the recompute this
    docstring describes — every other path (true hit, true miss, bypass)
    returns ``finding=None`` — so "we silently repaired a corrupted artifact"
    is a counted, callable fact rather than indistinguishable from an
    ordinary miss once the recompute overwrites the drifted entry.

    P21-ROUTING closure-2 (MINOR-D): when a drift was detected and the
    recompute itself then RAISES (a worker that refuses connections, a
    transport failure, a refusal), no :class:`CacheResult` exists to carry
    the finding — so the finding is attached to the exception instead, as
    the attribute :func:`cache_finding_of` reads back
    (``exc.cache_finding == CACHE_FINDING_EVIDENCE_DRIFT``), and the
    exception propagates unchanged in type and message (callers that key on
    ``type(exc).__name__`` see the same class). The drifted entry is NOT
    overwritten on that path (nothing was computed to overwrite it with): it
    is found — and reported — again on the next call, never lost and never
    served. An exception with no drift behind it carries no attribute.

    ``allow_visual_pair=True`` raises ``ValueError`` before ``compute`` runs,
    with or without a cache (model-code removal, slice S4; see
    :func:`ocr_settings_key`).
    """
    if allow_visual_pair:
        raise ValueError(VISUAL_PAIR_RETIRED)
    if cache is None:
        return CacheResult(compute(), False, STAGE_OCR, None)
    input_sha = content_hash or content_sha256(pdf_bytes)
    settings_key = ocr_settings_key(
        force_ocr=force_ocr,
        allow_local_ocr=allow_local_ocr,
        allow_visual_ocr=allow_visual_ocr,
        allow_paddle_ocr=allow_paddle_ocr,
        allow_visual_pair=allow_visual_pair,
        visual_pair_settings=visual_pair_settings,
        dpi=dpi,
        fallback_dpi=fallback_dpi,
        ocr_settings=ocr_settings,
        research_partition=research_partition,
    )
    key = cache_key(STAGE_OCR, input_sha, settings_key)
    hit, document = cache.get_ocr(input_sha, settings_key)
    drifted = False
    if hit:
        try:
            evidence_payload = document.get("evidence") if document is not None else None
            # Kept after the visual pair's removal (slice S4): a stored reading that carries its evidence still
            # restores, and only when the evidence reproduces the hash stored beside it.
            if document is not None and document.get("visual_pair") is not None:
                if _fingerprint(document["visual_pair"]) != document.get("visual_pair_sha256"):
                    raise ProvenanceTokenError("visual pair cache evidence hash mismatch")
            value = (
                None
                if document is None
                # source_file is re-stamped, never keyed: the markdown header must
                # name the file being processed now, not the one that filled the
                # cache.
                else StatementMarkdown(
                    source_file=source_file,
                    model=document.get("model", ""),
                    pages=list(document.get("pages") or []),
                    page_integrity=_page_integrity(document.get("page_integrity")),
                    page_extractor=list(document.get("page_extractor") or []),
                    evidence=from_json(evidence_payload) if evidence_payload is not None else None,
                    native_evidence=_restore_native_evidence(document),
                    visual_pair=document.get("visual_pair"),
                )
            )
        except (EvidenceError, ProvenanceTokenError, TypeError, KeyError):
            drifted = True  # a drifted cached copy: fall through to a fresh compute() below
        else:
            return CacheResult(value, True, STAGE_OCR, key, finding=None)
    try:
        document_out = compute()
    except Exception as exc:
        if drifted:
            # MINOR-D: no CacheResult will exist to carry the finding, so the
            # exception carries it. Every BaseException instance accepts
            # attribute assignment (the C-level struct owns a __dict__), so
            # this cannot itself fail; the type and message are untouched.
            exc.cache_finding = CACHE_FINDING_EVIDENCE_DRIFT
        raise
    cache.put_ocr(input_sha, settings_key, document_out)
    return CacheResult(
        document_out, False, STAGE_OCR, key,
        finding=CACHE_FINDING_EVIDENCE_DRIFT if drifted else None,
    )


def cache_finding_of(exc: BaseException) -> str | None:
    """P21-ROUTING closure-2 (MINOR-D): the cache finding :func:`cached_ocr`
    attached to ``exc`` before letting it propagate out of a failed
    recompute — ``CACHE_FINDING_EVIDENCE_DRIFT`` when the entry the failed
    recompute was replacing had drifted, else ``None``. The ONE reader of the
    attribute; callers never spell the attribute name themselves."""
    finding = getattr(exc, "cache_finding", None)
    return finding if isinstance(finding, str) and finding else None


def cached_analysis(
    markdown: str,
    *,
    compute: Callable[[], dict],
    cache: ArtifactCache | None = None,
    parse_mode: str = "auto",
    analysis_settings: Any | None = None,
    sheets: Sequence[str] | None = None,
    evidence_sha256: str | None = None,
) -> CacheResult:
    """Memoize extraction+analysis over the EXACT markdown being analyzed.

    ``sheets`` is the intake object's page list, which ``analyze_markdown``
    reads as well as the markdown — so it is key material, and it must be the
    same list ``compute`` passes down. Omit it only where the caller genuinely
    has no intake object; the analysis then fail-closes and the key records
    that it did.

    ``evidence_sha256`` (P22-IDENTITY, D6) is the sha of the evidence behind
    the `DocumentGeometry` ``compute`` hands to ``analyze_document`` — or
    ``None`` when it hands none. Key material, threaded to
    :func:`analysis_input_sha`: a geometry-fed analysis and a text-only one
    of the same markdown never share an entry. Whoever passes geometry passes
    the sha (the runner's seam, Phase 2.2 cell T); today every caller is
    text-only.

    Only successful results are cached — ``compute`` raising propagates
    untouched, because an extraction failure (a transient model error as much
    as a genuine no-parser-matched) is not an artifact worth pinning.
    """
    if cache is None:
        return CacheResult(compute(), False, STAGE_ANALYSIS, None)
    # Key on what the analysis actually reads, not on the bytes we were handed:
    # `analyze_markdown` strips the source-filename comment at its parse seam
    # (W3 FILENAME-BOUNDARY), so two uploads of one statement under two
    # filenames are the same analysis input and must share one cache entry —
    # and it also reads the intake page list, which that same strip removes from
    # the text, so the partition is carried explicitly (W3 §WIRING W3).
    input_sha = analysis_input_sha(markdown, sheets, evidence_sha256=evidence_sha256)
    settings_key = analysis_settings_key(
        parse_mode=parse_mode, analysis_settings=analysis_settings
    )
    key = cache_key(STAGE_ANALYSIS, input_sha, settings_key)
    hit = cache.get_analysis(input_sha, settings_key)
    if hit is not None:
        return CacheResult(hit, True, STAGE_ANALYSIS, key)
    analysis = compute()
    if isinstance(analysis, dict):
        cache.put_analysis(input_sha, settings_key, analysis)
    return CacheResult(analysis, False, STAGE_ANALYSIS, key)


def cached_report(
    markdown: str,
    *,
    compute: Callable[[], str],
    cache: ArtifactCache | None = None,
    title: str = "",
) -> CacheResult:
    """Memoize the rendered HTML report artifact for a markdown document."""
    if cache is None:
        return CacheResult(compute(), False, STAGE_REPORT, None)
    input_sha = text_sha256(markdown)
    settings_key = report_settings_key(title=title)
    key = cache_key(STAGE_REPORT, input_sha, settings_key)
    hit = cache.get_report(input_sha, settings_key)
    if hit is not None:
        return CacheResult(hit, True, STAGE_REPORT, key)
    html = compute()
    if isinstance(html, str):
        cache.put_report(input_sha, settings_key, html)
    return CacheResult(html, False, STAGE_REPORT, key)
