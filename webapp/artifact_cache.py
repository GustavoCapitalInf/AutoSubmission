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
    visual-OCR service knobs from ``ocr.config.Settings``.
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
    postprocess chain's quarantine state, read from ``ocr.ocr_client`` via
    ``getattr`` with the pinned defaults ``"quarantined"`` / ``()`` (cell B1
    owns the module-level constants; until it composes, or for any
    ``"offline"``-labelled call, the pinned defaults are used directly WITHOUT
    importing ``ocr.ocr_client`` — that chain is reachable only from the
    visual rung (``ocr/pipeline.py``), so importing it for an offline read
    would be a pure regression against the "the model client module is never
    even imported" property two tests already enforce
    (``tests/test_discovery.py``, ``tests/test_visual_rung.py``); the value is
    identical either way because the constants are process-wide, not
    per-call).
    ``raster_version`` = ``ocr.rasterize.RASTER_VERSION``.
    ``extraction_schema_version`` = :data:`EXTRACTION_SCHEMA_VERSION`.
    ``endpoint_class`` — from ``ocr_settings`` via ``getattr``, default
    ``"loopback"`` (cell B2 adds the real field to ``ocr.config.Settings``).
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
    ``parse_mode`` (``auto`` | ``deterministic``), ``model``,
    ``escalation_model``, ``withholding_denominator_mode`` — the whole of
    ``analysis.config.Settings`` that reaches the output, plus
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
* ``max_workers`` — page concurrency; ``ocr/config.py`` documents that it does
  not change output.
* ``timeout``, ``retries``, ``api_key`` — transport and secrets. Secrets must
  never be hashed into a key that is written to disk.
* callbacks (``on_stage``, ``on_page_delta``, ``on_page_replace``,
  ``page_ocr_fn``) and the preflight ``profile`` — the profile is derived from
  the bytes already in the key.

Over-partitioning is safe, under-partitioning is not: when the native rung
wins, the visual-OCR service knobs did not affect the result yet still
partition the key. That costs a cheap offline recompute after an env change
and never returns a stale artifact.

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
ANALYSIS_STAGE_VERSION = 26
#: Bump when the HTML renderer's output changes for unchanged settings.
REPORT_STAGE_VERSION = 1
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


#: Pinned defaults for the legacy OCR postprocess chain's quarantine state
#: (`ocr.ocr_client`, cell B1) — used directly, with no import, whenever a
#: call is labelled ``"offline"`` (that chain is unreachable from the offline
#: rungs; see `ocr_settings_key`'s docstring) and as the getattr fallback once
#: B1's module-level constants are read for a ``"visual"``-labelled call.
POSTPROCESS_STATE_DEFAULT = "quarantined"
ADMITTED_POSTPROCESS_DEFAULT: tuple[str, ...] = ()

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
    ``allow_visual_ocr=True`` — discovery's visual rung,
    `discovery/runner.py::_read_visual`). Every other shape, including the
    ambiguous "auto" call (``force_ocr=False``, ``allow_visual_ocr=True``)
    where a single ``ocr.pipeline.parse_statement`` call lets the offline
    ladder go first and only falls through to the visual rung internally, is
    ``"offline"`` — the offline ladder is what CAN run, whatever eventually
    does. ``allow_local_ocr`` does not enter the decision: it already
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

    The legacy postprocess chain (`ocr.ocr_client`) is imported ONLY for a
    ``"visual"``-labelled call: ``ocr/pipeline.py`` never even imports that
    module outside its visual-rung branch, and two tests
    (`tests/test_discovery.py`, `tests/test_visual_rung.py`) assert the model
    client module is absent from ``sys.modules`` after an offline-only run.
    Importing it here unconditionally would silently break that property for
    every offline document a real cache processes. The value is identical
    either way — B1's constants are process-wide, not per-call — so skipping
    the import for ``"offline"`` costs nothing but the import itself."""
    if extractor != "visual":
        return POSTPROCESS_STATE_DEFAULT, ADMITTED_POSTPROCESS_DEFAULT
    from ocr import ocr_client  # lazy: only the visual partition's key needs it

    state = str(getattr(ocr_client, "POSTPROCESS_STATE", POSTPROCESS_STATE_DEFAULT))
    admitted = tuple(
        str(item)
        for item in getattr(ocr_client, "ADMITTED_POSTPROCESS", ADMITTED_POSTPROCESS_DEFAULT)
    )
    return state, admitted


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

    ``ocr_settings`` is an ``ocr.config.Settings`` (or anything with the same
    attributes); when omitted it is loaded from the environment, so callers
    that never touch the OCR service still partition correctly if
    ``OCR_MODEL`` changes under them.

    ``stage_version`` defaults to the live :data:`OCR_STAGE_VERSION` (5+: the
    v5 key material below is included). Passing an EXPLICIT older version
    reconstructs the key EXACTLY as that version computed it — in particular,
    passing ``4`` reproduces the pre-P20-ARTIFACTS 9-field key byte-for-byte,
    with none of the v5 fields present, because at v4 they did not exist. This
    is what lets ``telemetry/run_of_record.py`` reconstruct a historical run's
    own OCR key (batch 8, batch 9) rather than recompute today's shape under
    yesterday's version number — the two are not the same key."""
    if ocr_settings is None:
        from ocr.config import load_settings as _load_ocr_settings

        ocr_settings = _load_ocr_settings()
    version = OCR_STAGE_VERSION if stage_version is None else int(stage_version)
    partition = _validate_research_partition(research_partition)
    if allow_visual_pair and version < 5:
        raise ValueError("visual pair requires OCR stage version 5 or later")
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
        if allow_visual_pair:
            extractor = "visual_pair"
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
        if allow_visual_pair:
            from ocr.visual_pair_config import load_visual_pair_settings, visual_pair_settings_key_material

            settings["allow_visual_pair"] = True
            settings["visual_pair"] = visual_pair_settings_key_material(
                visual_pair_settings or load_visual_pair_settings()
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

    ``hosted_extraction_opt_in`` (P22-FENCE review F3, Ocean's composition
    item) is the fence's own predicate ``hosted_extraction_opted_in()`` read
    from the process environment: an auto-mode payload produced under the
    opt-in literal must never be served later to a process without it (a
    cache hit is not a call, but it is the same payload). The boolean is
    derived by the fence, never recomposed here.
    """
    if analysis_settings is None:
        from analysis.config import load_settings as _load_analysis_settings

        analysis_settings = _load_analysis_settings()
    # Function-local, like ``analysis.config``: importing this module must stay
    # cheap, and the structurer package is only needed when a key is derived.
    from analysis.structurer import structurer_enabled
    from analysis.pipeline import hosted_extraction_opted_in
    return _fingerprint(
        {
            "stage_version": ANALYSIS_STAGE_VERSION,
            "parse_mode": str(parse_mode),
            "model": str(getattr(analysis_settings, "model", "")),
            "escalation_model": str(getattr(analysis_settings, "escalation_model", "")),
            "withholding_denominator_mode": str(
                getattr(analysis_settings, "withholding_denominator_mode", "")
            ),
            "parser_registry": registry_fingerprint(),
            "reconstruction_mode": str(getattr(analysis_settings, "reconstruction_mode", "off")),
            "generic_structurer": bool(structurer_enabled(analysis_settings)),
            "hosted_extraction_opt_in": bool(hosted_extraction_opted_in()),
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
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = _canonical_json(payload).encode("utf-8")
        tmp = path.with_suffix(".json.tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, path)
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
        sha a restore must reproduce byte-for-byte and re-verify against."""
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
    """
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
