"""Deterministic offline corpus gate for the validated statement corpus.

Runs both independent forensic oracles over every corpus PDF and fails red on
any drift from the committed audits. Nothing here calculates a financial value
of its own: it re-runs `adb_forensic_audit` and `balance_forensic_audit`
unchanged and compares their output, field by field, with
`docs/adb-audit-results.csv` and `docs/balance-metrics-audit-results.csv`.

Three checks are deliberately NOT oracle-independent, and all three read the
same per-document payloads the product itself publishes.

`check_outcome_classes` reads the product's own per-document verdict — the
outcome class plus the WHOLE published integrity block (flags, notes,
risk_level, possible_document_issue) — and holds it to `PINNED_OUTCOMES`. It
exists because the two financial oracles are structurally blind to three kinds
of truth-set movement: a statement moving review<->validated inside the audits'
single PASS class; a statement gaining or losing a published integrity flag
without changing class; and risk_level or possible_document_issue moving
independently of the flags. All three are real; see `PINNED_OUTCOMES`.

`check_adb_doctrine` holds every pinned document to the one published ADB
basis, and `check_currency` holds every pinned document to its published
`statement.currency`. Currency is the fourth blind spot: it appears in neither
audit CSV, so 151 archive documents (four of them pinned) could change the
denomination an analyst reads with every financial field byte-identical. See
`PINNED_CURRENCY`. `check_currency_source` is its sibling and covers the fifth
blind spot: the EVIDENCE a denomination rests on can degrade — a read of the
document's own printed code falling back to a constant asserted from the
issuer — while the three letters, and therefore every other check here, stay
identical. See `PINNED_CURRENCY_SOURCE`.

**That check runs only in the gate.** `pytest -q` does not verify the 109-entry
map — the unmarked tests check its shape and prove the mechanism by mutation on
a single document, and only `python corpus_gate.py` (or `pytest -m corpus`)
compares all 109 against the product. A green default suite is not a verified
truth set.

    python corpus_gate.py                     # the gate
    python corpus_gate.py --json report.json  # plus a machine-readable report
    python corpus_gate.py --corpus <path>     # same gate against another root
    pytest -m corpus                          # same gate, through pytest

Scope: the **pinned manifest**, not the directory. The gate enumerates the 109
corpus-relative paths recorded in the committed audit CSVs and audits exactly
those. The corpus root is shared with untracked, sensitive discovery material
(`.gitignore`: `Bank Statements/**`), so "every PDF under the root is pinned" is
no longer a property the tree can have. What replaces it is stricter about the
validated set and honest about the rest — see `check_foreign_files`.

Guarantees:

- Offline. No OCR endpoint, no Gemini, no network, no Tesseract binary. The 6
  image-only statements are served from committed OCR artifacts keyed by the
  SHA-256 of their source PDF (see `corpus_artifacts`).
- Complete over the pinned manifest. Every pinned path must exist on disk, must
  hash-match its pin, and must carry a row in *both* committed audits; the two
  audits must pin the same 109 paths. A statement is never skipped silently: a
  missing file, a missing artifact, or an unreadable document is a failure, and
  any deliberate exclusion is named and counted in the report.
- Explicit about foreign files. PDFs under the root that are not in the manifest
  are counted and reported ("N non-corpus PDFs present — ignored"). Never
  silently, and never a failure: they are not the validated corpus and the gate
  makes no claim about them.
- Platform-neutral. Path-valued audit columns (`PATH_VALUED_FIELDS`) compare
  without regard to separator, so the same corpus reproduces the same audits on
  Windows and on a Linux runner. Every other field still compares byte for byte.
- Read-only against the truth set. The audit CSVs are consumed, never written.
  Regenerating them is `adb_forensic_audit.py` / `balance_forensic_audit.py`,
  which is a separate, deliberate act.

Exit code 0 when every check passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, NamedTuple

import adb_forensic_audit
import balance_forensic_audit
# A leaf that computes nothing about a statement: it answers which of the two
# published SHAPES a payload is. Importing it here does not couple this gate to
# the analysis stack the two oracles above deliberately load without.
from analysis.payload_shape import refuse_document_payload
from corpus_artifacts import (
    DEFAULT_CACHE,
    ArtifactError,
    cached_markdown,
    cached_pages,
    manifest_entries,
)

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "Bank Statements"
ADB_CSV = ROOT / "docs" / "adb-audit-results.csv"
BALANCE_CSV = ROOT / "docs" / "balance-metrics-audit-results.csv"

EXPECTED_PDF_COUNT = 109
EXPECTED_PASS = 105
EXPECTED_WITHHELD = 3
EXPECTED_REFUSED = 1
WITHHELD_STATEMENTS = {
    "Ace_Auto_Final_Cut.pdf",
    "BMO_Statement_January_2026 Final-1-2 (1).pdf",
    "IBC April (1).pdf",
}

#: The status both audit oracles write for a pinned document the deterministic
#: analysis REFUSES to publish. See `PINNED_REFUSALS`.
REFUSED_STATUS = "REFUSED"

#: Pinned documents production refuses to analyse, each with the refusal it is
#: pinned at, verbatim.
#:
#: A refusal is a pinned FACT, not an absence. The document stays in the
#: manifest, both audit CSVs keep a row for it, and this map is what the gate
#: holds the refusal to: the analysis must raise `RuntimeError` with exactly
#: this message. If the document ever publishes again — because a parser was
#: relaxed, or because a repair came back — the gate goes RED, which is the
#: same protection a published verdict gets from `PINNED_OUTCOMES`. Deleting
#: the entry, or the document, is the only way to make it green, and that is a
#: ceremony.
#:
#: CEREMONY, executed 2026-08-21 (REPAIR-DOCTRINE, W3 §REPAIRDOC, Gustavo's
#: ruling of the same day: "Parsers must never rewrite transaction amounts just
#: to force reconciliation. Replace repair-by-rewrite with discard-and-flag /
#: fail-closed."). `analysis/columbia_bank.py` held two repairs that REWROTE a
#: row's amount to bring a section into agreement with its own printed total,
#: and this document was the archive's only statement that published because of
#: them: three of its 108 amounts were parser-written rather than read
#: (sha256 0CBD2AD897B90137878F81EF608778735CA0DFEAB23D25793F2C6F1DF6C6127D).
#: With the repairs removed the ACH sections miss their printed totals, the
#: reader declines exactly as it already did for the cohort's other three
#: statements, no registration claims the document, and the analysis raises.
#: It moved `review` / `missing_declared_statement_page` -> refused; its rows in
#: both audit CSVs moved to the REFUSED shape; and its `PINNED_CURRENCY` entry
#: was withdrawn, because a document that publishes no statement publishes no
#: denomination either.
PINNED_REFUSALS: dict[str, str] = {
    "Misc/Columbia May 26 complete.pdf": "no deterministic parser matched this statement",
}

# ----------------------------------------------------------------------
# The product's own per-document verdict — the partition the two oracles
# structurally cannot see.
# ----------------------------------------------------------------------
#
# `check_outcomes` above proves 105 PASS / 3 WITHHELD / 1 REFUSED from the
# audit CSVs, and
# both audits are financial: neither has a `flags`, `notes`, `risk_level` or
# `possible_document_issue` column (see their `FIELDS`). Three consequences,
# each measured rather than argued, and each a defect this check exists to
# close:
#
# 1. `validated` and `review` are a FINER partition of the gate's PASS, so a
#    pinned statement moving review<->validated is invisible to every check
#    above while all of them stay green. Not hypothetical: at PIPELINE-FIX-2's
#    first revision (`b8013d5`) two pinned documents made exactly that move and
#    the gate reported GREEN over it (W3 §PIPEFIX P4b.5).
# 2. A pinned statement can change a PUBLISHED integrity flag without changing
#    class at all — a withheld document that loses a flag is still withheld.
#    Not hypothetical either: activating the page-declaration check withdrew
#    `missing_declared_statement_page` from the pinned BMO January statement,
#    whose class did not move. A check on the outcome CLASS alone would have
#    seen nothing, and that movement is why WIRING-1 stopped.
# 3. `risk_level` and `possible_document_issue` move INDEPENDENTLY of the flag
#    list, so pinning the class and the flags is still not enough.
#    `possible_document_issue` keys on `recon.continuity_breaks >= 3`
#    (`analysis/pipeline.py`), while the `running_balance_breaks` flag keys on
#    the same counter being non-zero — so 2 breaks -> 3 leaves class, reason and
#    flags byte-identical and flips `possible_document_issue` False -> True and
#    `risk_level` review -> high. The whole block is served to users
#    (`webapp/app.py`), and the approved Texas Bank ceremony itself moves
#    `risk_level` review -> clear.
#
# So what is pinned is the ENTIRE published integrity block, plus the outcome
# class. Measured over the 109: the old (class, reason, flags) triple failed to
# determine (risk_level, possible_document_issue, notes) on 4 of them — the
# page_coverage documents share one triple while their notes name different
# page numbers.
#
# The outcome REASON is deliberately not pinned. Over every state the pinned
# corpus reaches (6 distinct `(class, flags)` pairs, 0 collisions) the reason is
# a total function of `(class, flags)`, which `classify_outcome`'s own structure
# explains: `withheld` always carries `withheld_adb` here, `validated` always
# `approved`, and each `review` reason is selected by a named flag or by their
# absence. It is recorded here rather than silently dropped, because a future
# reason that is NOT so determined would be a real change worth pinning.
#
# The expectation is total over all 109 without enumerating all 109: this map
# holds every document that is NOT plainly published, and every pinned path
# absent from it must equal `PUBLISHED_OUTCOME`. Measured: all 102 validated
# documents share exactly one published state, so "absent" is a real
# expectation and not a gap. Recorded from the tree at WIRING-2, POST-ceremony
# (102 validated / 4 review / 3 withheld); moving an entry is truth-set
# movement and needs the same ceremony as an audit CSV.


class _Verdict(NamedTuple):
    """One pinned document's published verdict: the class plus the whole
    integrity block, field order exactly as the payload serialises it.

    `account_index` is the discriminator. `None` means *the document* — the
    verdict `PINNED_OUTCOMES` pins and the one a person reads. An integer means
    one ACCOUNT of a document that published several, in printed order, and a
    document verdict is never one of those wearing the document's name: the
    document's outcome is the fold `telemetry/record.py::classify_document`
    performs, and its integrity block is the DOCUMENT-scope one.

    The field is last and defaults to `None`, so every entry pinned before this
    existed constructs and compares exactly as it did.
    """

    outcome: str
    flags: tuple[str, ...]
    notes: tuple[str, ...]
    risk_level: str
    possible_document_issue: bool
    account_index: int | None = None


#: What every pinned path ABSENT from `PINNED_OUTCOMES` must publish.
PUBLISHED_OUTCOME = _Verdict("validated", (), (), "clear", False)

#: corpus-relative path -> the published verdict.
PINNED_OUTCOMES: dict[str, _Verdict] = {
    # A transaction export rather than a bank statement — a document class,
    # which is why its evidence is advisory.
    "Chase/Chase Business.pdf": _Verdict(
        "review",
        flags=("not_a_formal_statement",),
        notes=(
            "document is a Chase online transaction export, not a complete bank statement",
        ),
        risk_level="review",
        possible_document_issue=False,
    ),
    # Three of the five page_coverage documents. The other two — Texas Bank and
    # Regions — were carrying `missing_declared_statement_page` FALSELY: their
    # pages are present as unlabelled sheets, which W3 §PIPEFIX P4b.5 measured
    # and Gustavo approved as a review->validated ceremony (approved
    # 2026-08-14, re-scoped to three movements 2026-08-15). WIRING-2 executed
    # it, so both now publish `PUBLISHED_OUTCOME` and live outside this map.
    #
    # Two of the three still keep their flags here, and they are the reason the
    # fix is not blunt: Builder supplies 4 sheets for 5 declared pages and Link
    # Bank labels 19 of 20. In each a page really is unaccounted for.
    "Misc/Builder June 2026.pdf": _Verdict(
        "review",
        flags=("missing_declared_statement_page",),
        notes=(
            "statement declares 5 bank page(s), but page label(s) 1, 2, 3 are absent from the supplied PDF",
        ),
        risk_level="review",
        possible_document_issue=False,
    ),
    # `Misc/Columbia May 26 complete.pdf` was the third of them and is now a
    # pinned REFUSAL instead — see `PINNED_REFUSALS`. Its page really is
    # unaccounted for too, but the finding no longer has a published statement
    # to sit on.
    "Misc/Link Bank April statement.pdf": _Verdict(
        "review",
        flags=("missing_declared_statement_page",),
        notes=(
            "statement declares 20 bank page(s), but page label(s) 20 are absent from the supplied PDF",
        ),
        risk_level="review",
        possible_document_issue=False,
    ),
    # CEREMONY, executed 2026-08-15 (WIRING-2, Gustavo's OPTION A):
    #
    #   Misc/Texas Bank.pdf   744D6E04AFCB1B0C6F91F6AC4E4B1A4976CBFA8C18D4F4E2950CD50723DA6110
    #   Regions/Regions.pdf   98D069AF2A41CC6F4A6E6B6DD94FA2E8C294E18438D817BBBB05CCE1B55E849F
    #
    # both moved review -> validated on a WITHDRAWN FALSE FLAG (flags
    # ['missing_declared_statement_page'] -> [], notes 1 -> 0, risk_level
    # review -> clear, possible_document_issue unchanged), so both left this map
    # for `PUBLISHED_OUTCOME`. Their pages were never absent: Texas Bank
    # supplies 4 text-bearing sheets for 4 declared pages and Regions 3 for 3,
    # with the labels simply not printed on all of them. Every audited balance
    # and ADB field is byte-identical — the two forensic oracles above prove
    # that on every gate run, and neither reads a flag.
    #
    # This is the exact movement the gate could not see before WIRING-1's
    # verdict check: `validated` and `review` are BOTH inside the audits' PASS
    # class, so at `b8013d5` two pinned documents made this same move with the
    # gate reporting GREEN over it. It is recorded here because the map is the
    # only place that now watches it.
    #
    # The third approved movement is the BMO January statement below: withheld
    # before and after, one false flag withdrawn from its published evidence.
    #
    # The three withheld. Same three as WITHHELD_STATEMENTS, here with the
    # evidence they publish rather than only their names.
    "Misc/Ace_Auto_Final_Cut.pdf": _Verdict(
        "withheld",
        flags=(
            "ledger_sum_mismatch",
            "debit_detail_coverage_mismatch",
            "transaction_detail_not_corporate_reliable",
            "debit_count_mismatch",
        ),
        notes=(
            "transaction sum does not reconcile to the printed ending balance",
            "line-item debits do not match the bank-stated debit total",
            "summary figures may be usable, but transaction-level detail is not reliable enough for corporate approval",
            "captured debit rows do not match the bank-stated debit count",
        ),
        risk_level="review",
        possible_document_issue=False,
    ),
    # CEREMONY, executed 2026-08-15 (WIRING-2, Gustavo's OPTION A, movement 3):
    # sha256 E86143101E28E198EC5278B065E8BA967DD73E9AB735A1CAC4A0FE7CB46CB83F.
    # WITHHELD before and after — the refusal is a reconciliation one and does
    # not move — while its PUBLISHED EVIDENCE does: flags 7 -> 6 and notes
    # 8 -> 7, dropping `missing_declared_statement_page` and its note. The
    # document supplies 2 text-bearing sheets for the 2 pages it declares and
    # prints the label on one of them, so nothing was ever shown to be absent.
    # `risk_level` (high) and `possible_document_issue` (True) are unchanged:
    # they are carried by the reconciliation findings, not by this flag.
    #
    # WIRING-1 STOPPED the activation over exactly this document (W3 §WIRING
    # W1): §PIPEFIX P4b.5 enumerated the pinned page_coverage documents by
    # DIAGNOSIS and this one is diagnosed `source_contradiction`, so a sixth
    # pinned flag-carrier went uncounted and the two-document ceremony would
    # have moved a third. Withdrawing a false accusation from a withheld
    # document's published evidence is still truth-set movement, which is why
    # it waited for Gustavo's re-scope rather than being adjusted here.
    "Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf": _Verdict(
        "withheld",
        flags=(
            "ledger_sum_mismatch",
            "running_balance_breaks",
            "credit_detail_coverage_mismatch",
            "debit_detail_coverage_mismatch",
            "transaction_detail_not_corporate_reliable",
            "conflicting_statement_summaries",
        ),
        notes=(
            "transaction sum does not reconcile to the printed ending balance",
            "36 printed running-balance continuity break(s) detected",
            "line-item credits do not match the bank-stated credit total",
            "line-item debits do not match the bank-stated debit total",
            "summary figures may be usable, but transaction-level detail is not reliable enough for corporate approval",
            "conflicting bank-stated deposit totals across summary sections",
            "secondary bank-stated summary does not reconcile to the opening and final balances",
        ),
        risk_level="high",
        possible_document_issue=True,
    ),
    "Others/IBC/IBC April (1).pdf": _Verdict(
        "withheld",
        flags=(
            "summary_math_inconsistent",
            "ledger_sum_mismatch",
            "running_balance_breaks",
        ),
        notes=(
            "bank-stated summary totals do not reconcile to beginning and ending balances",
            "transaction sum does not reconcile to the printed ending balance",
            "1 printed running-balance continuity break(s) detected",
        ),
        risk_level="high",
        possible_document_issue=True,
    ),
}

# ----------------------------------------------------------------------
# The published CURRENCY of every pinned document — the fourth thing the two
# financial oracles structurally cannot see.
# ----------------------------------------------------------------------
#
# `currency` is analyst-visible output: `webapp/static/app.js` threads
# `statement.currency` into `Intl.NumberFormat`, so it decides whether a
# dashboard reads `$1,234.56` or `CA$1,234.56` for every figure on the page.
# Until this map existed it was pinned NOWHERE — measured at
# RBC_CURRENCY_MEASUREMENT §4.6: no currency column in either audit CSV or in
# the new-statement audit, zero occurrences of the string in this file, zero in
# `tests/data/parser_expectations.json`. A change that moved the published
# currency of 151 archive documents (four of them pinned) could therefore land
# with every pinned artifact byte-identical and every gate check green. That is
# the blindness class this closes, on Gustavo's ruling of 2026-08-16: "currency
# must no longer be gate-invisible ... pin the expected currency for all 109
# trusted statements, not only the four RBC movers".
#
# WHY A SEPARATE TOTAL MAP rather than a sixth field on `_Verdict`. `_Verdict`
# is an exception map: a pinned path absent from `PINNED_OUTCOMES` means "this
# document publishes the one ordinary state", and that works only because all
# 102 validated documents share it. Currency has no such single ordinary value
# — 95 USD and 14 CAD — so folding it into `_Verdict` would force fourteen
# documents into an exception map they do not otherwise belong in, and would
# entangle a currency movement with a verdict movement in the same tuple. This
# map is instead TOTAL: every pinned path appears exactly once, a manifest path
# missing from it is a failure, and an entry naming an unpinned path is a
# failure. Nothing can be added to the corpus without a currency being stated
# for it, and nothing can be silently dropped.
#
# HOW THESE VALUES WERE ESTABLISHED (the ruling's "verify the existing values
# before establishing the baseline; do not use baseline generation to bless
# unexplained values"). Every value below was measured on the UNCHANGED base
# tree first, through this file's own `production_verdict` resolution, and the
# provenance of each was measured separately by rotating
# `analysis.schema.Statement`'s field default to a sentinel: 10 documents were
# published CAD by their parser, 5 were published USD by their parser, and 94
# carried the schema default because no reader asked. The four RBC entries
# marked CEREMONY are the only values that differ from that census; every other
# entry is the pre-existing published value, recorded rather than re-derived.
#
# Enumerated because they were reviewed rather than assumed:
#
#  * the 14 CAD. Ten already published CAD before this card (CIBC French,
#    BMO Canada, the pinned French RBC statement, Scotiabank, and the six TD
#    Canada Trust statements), each from its own parser's explicit assignment.
#    Four are this card's approved ceremony.
#  * `Misc/USD FEB 2026.pdf` is a Desjardins document — a Quebec caisse — and
#    it is pinned USD on EXPLICIT evidence, not by default: its product line
#    prints `USD DESJARDINS CORPORATE BUILD-UP ACCOUNT` and
#    `analysis/desjardins.py::_printed_currency` reads it. A Canadian
#    institution's USD-denominated product is exactly what doctrine §A's second
#    RBC example describes, so this is a correct USD and not a silent default.
#  * the five `ATB/*` documents are ATB Financial — Alberta Treasury Branches,
#    a Canadian provincial bank — and they are pinned USD because that is what
#    the platform publishes today, from the schema default, with no reader
#    having asked. They are NOT evidence of a USD account. They are the same
#    shape the RBC family had before this card, they are named here as expected
#    future movers, and moving them requires ATB's own proven jurisdiction
#    evidence base first (doctrine §B, final paragraph). Pinning today's value
#    is what makes that future movement a visible ceremony instead of a silent
#    drift — which is the whole purpose of this map.
#
# Moving any entry is truth-set movement and needs the same ceremony as an
# audit CSV row.
PINNED_CURRENCY: dict[str, str] = {
    "ATB/ATB August 2023.pdf": "USD",
    "ATB/ATB Dec 2023.pdf": "USD",
    "ATB/ATB Nov 2023.pdf": "USD",
    "ATB/ATB October statement 2023.pdf": "USD",
    "ATB/ATB Sep 2023.pdf": "USD",
    "Amex/Amex Apr2026.pdf": "USD",
    "Amex/Amex June2026.pdf": "USD",
    "Amex/Amex May2026.pdf": "USD",
    "BofA/BofA 2026-05-29.pdf": "USD",
    "BofA/BofA Statement.pdf": "USD",
    "BofA/BofA.pdf": "USD",
    "BofA/Bofa 2026-02-27.pdf": "USD",
    "BofA/eStmt_2026-01-30 (3) (1).pdf": "USD",
    "BofA/eStmt_2026-02-27 (3) (1).pdf": "USD",
    "BofA/eStmt_2026-03-31 (3) (1).pdf": "USD",
    "BofA/eStmt_2026-04-30 (1).pdf": "USD",
    "CIBC French/Account Statement 1.pdf": "CAD",
    "CapitalOne/capital one april 2026.pdf": "USD",
    "CapitalOne/capital one february 2026.pdf": "USD",
    "CapitalOne/capital one march 2026.pdf": "USD",
    "CapitalOne/capital one may 2026.pdf": "USD",
    "Chase/Chase Apr.pdf": "USD",
    "Chase/Chase Business.pdf": "USD",
    "Chase/Chase Jun.pdf": "USD",
    "Chase/Chase Mar.pdf": "USD",
    "Chase/Chase May.pdf": "USD",
    "Chase/Chase Salomomon February 27 2026.pdf": "USD",
    "Chase/Chase Salomon Dec 2025.pdf": "USD",
    "Chase/Chase Salomon January.pdf": "USD",
    "Chase/Chase Salomon March 2026.pdf": "USD",
    "Chase/chase jun 30.pdf": "USD",
    "Chase/chase may 29.pdf": "USD",
    "Citizen/Citizen June 2026.pdf": "USD",
    "Citizen/Citizens April 2026.pdf": "USD",
    "Citizen/Citizens March 2026.pdf": "USD",
    "Citizen/Citizens May 2026.pdf": "USD",
    "Misc/7429_Statement_October_2025_Statement.pdf": "USD",
    "Misc/Ace_Auto_Final_Cut.pdf": "USD",
    "Misc/Builder June 2026.pdf": "USD",
    "Misc/Checking Account Statements - 1_30_2026 - 4001245.pdf": "USD",
    # `Misc/Columbia May 26 complete.pdf` is deliberately absent: it is a
    # pinned REFUSAL and publishes no statement, so it publishes no
    # denomination either. Pinning one would assert a fact the product does not
    # state. `check_currency` holds this map to the manifest MINUS the pinned
    # refusals, so the omission is enforced rather than tolerated.
    "Misc/Consumers March - Monthly Statement.pdf": "USD",
    "Misc/Field Trucking November 2025 .pdf": "USD",
    "Misc/First Farmers 2026 01-document.pdf": "USD",
    "Misc/KLR.May 31,2026 (1).pdf": "USD",
    "Misc/Link Bank April statement.pdf": "USD",
    "Misc/MidFlorida.pdf": "USD",
    "Misc/Texas Bank.pdf": "USD",
    # Desjardins, read from the printed product line. See the note above.
    "Misc/USD FEB 2026.pdf": "USD",
    "Misc/WMB May 25.pdf": "USD",
    "Navy Fed/APRIL 2026.pdf": "USD",
    "Navy Fed/JUNE 2026.pdf": "USD",
    "Navy Fed/MARCH 2026.pdf": "USD",
    "Navy Fed/MAY 2026.pdf": "USD",
    "Others/Altana/Altana april 26.pdf": "USD",
    "Others/Altana/Altana june 26.pdf": "USD",
    "Others/Altana/Altana may 26.pdf": "USD",
    "Others/B1/b1 april 2026.pdf": "USD",
    "Others/B1/b1 feb 2026 (1).pdf": "USD",
    "Others/B1/b1 march 2026.pdf": "USD",
    "Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf": "CAD",
    "Others/Banco/Banco Popular April 2026.pdf": "USD",
    "Others/Banco/Banco Popular Junio 2026.pdf": "USD",
    "Others/Banco/Banco Popular May 2026.pdf": "USD",
    "Others/Bluevine/bluevine_Statement_2026-04-02T21_36_47.777670Z (1).pdf": "USD",
    "Others/First Citizen/First Citizens Bank.pdf": "USD",
    "Others/IBC/IBC April (1).pdf": "USD",
    "Others/Navigant Credit Union 2026-06-30.pdf": "USD",
    "Others/Relay Operations-June-2026.pdf": "USD",
    "Others/Santander/Santander_April26.pdf": "USD",
    "Others/Santander/Santander_February 2026.pdf": "USD",
    "Others/Santander/Santander_March 2026.pdf": "USD",
    "Others/Secu/Secu.pdf": "USD",
    "PNC/PNC_Statement-2026-01-29.pdf": "USD",
    "PNC/PNC_Statement-2026-02-26.pdf": "USD",
    "PNC/PNC_Statement-2026-03-30.pdf": "USD",
    "PNC/PNC_Statement-2026-04-29.pdf": "USD",
    "PNC/PNC_Statement-2026-05-28.pdf": "USD",
    # Already CAD from the French reader; explicitly NOT part of the ceremony.
    "RBC French/12 - Relevé Royale Décembre 2025 - Tommy Aspirot.pdf": "CAD",
    # CEREMONY, approved by Gustavo 2026-08-16 (CURRENCY_DOCTRINE §B; the
    # eight-proof packet RBC_CURRENCY_MEASUREMENT §9.1). These four English RBC
    # chequing statements move `statement.currency` USD -> CAD and NOTHING
    # else: ADB, opening/ending balances, the transaction ledger, credits and
    # debits, revenue classifications and validation outcomes are all
    # byte-identical, which the two forensic oracles above and the verdict map
    # below prove on every gate run.
    #
    #   Chequing Statement-DEC+.pdf  A26ECE4F32488CECDD59EA5BCF13B4947786456038CBDD17AC52C0F3D9F38EE5
    #   Chequing Statement-JAN+.pdf  633F036CDE97F639D95538678B738E939E708254C99D9910F6202CB44C1FD2D3
    #   Chequing Statement-FEB+.pdf  F0348F3EDD0F64284AD49632C9FF5414C60113A79B0A3356E2441B1CB2E7CA27
    #   Chequing Statement-MAR+.pdf  4F3CC713463FDD59318770C037FB0786FB984FB1A169456B068AE735D64EFD77
    #
    # None of the four prints a denomination anywhere; all four print the four
    # affirmative RBC Canada jurisdiction proofs. The justification is that
    # affirmative evidence, never the absence of USD wording.
    "RBC/Chequing Statement-DEC+.pdf": "CAD",
    "RBC/Chequing Statement-FEB+.pdf": "CAD",
    "RBC/Chequing Statement-JAN+.pdf": "CAD",
    "RBC/Chequing Statement-MAR+.pdf": "CAD",
    "Regions/Regions-29-2026 (3).pdf": "USD",
    "Regions/Regions.pdf": "USD",
    "Regions/Regions_03-31-2026 (3) (1).pdf": "USD",
    "Regions/Regions_04-30-2026 (2) (1).pdf": "USD",
    "ScotiaBank/Scotiabank -2.pdf": "CAD",
    "TD Can/Dec_31-Jan_30_2026 (6).pdf": "CAD",
    "TD Can/Feb_27-Mar_31_2026 (2).pdf": "CAD",
    "TD Can/Jan_30-Feb_27_2026 (3).pdf": "CAD",
    "TD Can/Mar_31-Apr_30_2026.pdf": "CAD",
    "TD Can/Nov_28-Dec_31_2025 (7).pdf": "CAD",
    "TD Can/TD Bank Bank Statement.pdf": "CAD",
    "TD/TD BANK NARROW APR.pdf": "USD",
    "TD/TD BANK NARROW FEB.pdf": "USD",
    "TD/TD BANK NARROW JAN.pdf": "USD",
    "TD/TD BANK NARROW MAR.pdf": "USD",
    "Truist/Truist AUTO February, 2026.pdf": "USD",
    "Truist/Truist AUTO March 2026.pdf": "USD",
    "Truist/Truist April, 2026.pdf": "USD",
    "Truist/Truist February, 2026.pdf": "USD",
    "Truist/Truist March, 2026.pdf": "USD",
    "US Bank/US Bank 2026-03-31 Statement.pdf": "USD",
    "US Bank/US Bank 2026-04-30 Statement.pdf": "USD",
    "WellsFargo/02-28-26 WellsFargo.pdf": "USD",
    "WellsFargo/03-31-26 WellsFargo.pdf": "USD",
    "WellsFargo/04-30-26 WellsFargo 1.pdf": "USD",
    "WellsFargo/113025 WellsFargo.pdf": "USD",
}

#: The same 109 pinned documents, and the EVIDENCE CLASS each published
#: currency came from (`Statement.currency_source`, §CURRSRC). A sibling TOTAL
#: map rather than a second value inside `PINNED_CURRENCY`, for three reasons:
#: `PINNED_CURRENCY` stays byte-identical, so the batch-6 ceremony's surface and
#: the census comment above it remain exactly what was reviewed; a currency that
#: moved and a provenance that moved are different findings and the gate names
#: which; and the ratified surface form for this kind of pin is a separate total
#: map.
#:
#: MEASURED on this branch before it was pinned, by replaying the same
#: `production_verdict` resolver `check_outcome_classes` uses, and enumerated in
#: the cell's report rather than generated as a baseline. The split is
#: 90 schema_default / 7 institution_default / 7 product / 4 jurisdiction_default
#: / 1 printed, and it reconciles to the batch-6 census exactly:
#:
#:  * 90 `schema_default` — the 94 documents no reader ever asked about, less
#:    the four the RBC ceremony moved. Includes the five `ATB/*` documents,
#:    which is the point of publishing the class at all: they are a Canadian
#:    provincial bank's statements labelled USD by a field default, and they now
#:    SAY so instead of looking like the read that `Chase/*` also is not.
#:  * 7 `institution_default` — the three Canadian hardcodes batch 6 named as
#:    owing an evidence packet (CIBC French, Scotiabank, the French RBC
#:    statement) plus four U.S. ones (a Chase export, Farmers & Merchants,
#:    Southside, Apex).
#:  * 7 `product` — the six TD Canada statements whose product line prints
#:    `ACCOUNT - CAD`, and the Desjardins `USD DESJARDINS CORPORATE BUILD-UP
#:    ACCOUNT`. Batch 6 counted these inside its "7 printed"; the vocabulary
#:    separates a code read off a product designation from one stated outright.
#:  * 4 `jurisdiction_default` — the four RBC statements of the approved
#:    ceremony, and the only documents in the corpus taking a native default.
#:  * 1 `printed` — the BMO statement whose header block states `Currency: CAD`.
#:
#: RED on movement in either direction, exactly like the currency itself: a
#: document that stops reading its evidence and falls back to a default keeps
#: publishing the same code, and this map is the only thing in the gate that
#: would see it.
PINNED_CURRENCY_SOURCE: dict[str, str] = {
    "ATB/ATB August 2023.pdf": "schema_default",
    "ATB/ATB Dec 2023.pdf": "schema_default",
    "ATB/ATB Nov 2023.pdf": "schema_default",
    "ATB/ATB October statement 2023.pdf": "schema_default",
    "ATB/ATB Sep 2023.pdf": "schema_default",
    "Amex/Amex Apr2026.pdf": "schema_default",
    "Amex/Amex June2026.pdf": "schema_default",
    "Amex/Amex May2026.pdf": "schema_default",
    "BofA/BofA 2026-05-29.pdf": "schema_default",
    "BofA/BofA Statement.pdf": "schema_default",
    "BofA/BofA.pdf": "schema_default",
    "BofA/Bofa 2026-02-27.pdf": "schema_default",
    "BofA/eStmt_2026-01-30 (3) (1).pdf": "schema_default",
    "BofA/eStmt_2026-02-27 (3) (1).pdf": "schema_default",
    "BofA/eStmt_2026-03-31 (3) (1).pdf": "schema_default",
    "BofA/eStmt_2026-04-30 (1).pdf": "schema_default",
    "CIBC French/Account Statement 1.pdf": "institution_default",
    "CapitalOne/capital one april 2026.pdf": "schema_default",
    "CapitalOne/capital one february 2026.pdf": "schema_default",
    "CapitalOne/capital one march 2026.pdf": "schema_default",
    "CapitalOne/capital one may 2026.pdf": "schema_default",
    "Chase/Chase Apr.pdf": "schema_default",
    "Chase/Chase Business.pdf": "institution_default",
    "Chase/Chase Jun.pdf": "schema_default",
    "Chase/Chase Mar.pdf": "schema_default",
    "Chase/Chase May.pdf": "schema_default",
    "Chase/Chase Salomomon February 27 2026.pdf": "schema_default",
    "Chase/Chase Salomon Dec 2025.pdf": "schema_default",
    "Chase/Chase Salomon January.pdf": "schema_default",
    "Chase/Chase Salomon March 2026.pdf": "schema_default",
    "Chase/chase jun 30.pdf": "schema_default",
    "Chase/chase may 29.pdf": "schema_default",
    "Citizen/Citizen June 2026.pdf": "schema_default",
    "Citizen/Citizens April 2026.pdf": "schema_default",
    "Citizen/Citizens March 2026.pdf": "schema_default",
    "Citizen/Citizens May 2026.pdf": "schema_default",
    "Misc/7429_Statement_October_2025_Statement.pdf": "schema_default",
    "Misc/Ace_Auto_Final_Cut.pdf": "institution_default",
    "Misc/Builder June 2026.pdf": "institution_default",
    "Misc/Checking Account Statements - 1_30_2026 - 4001245.pdf": "schema_default",
    # `Misc/Columbia May 26 complete.pdf` is deliberately absent here too: a
    # pinned REFUSAL publishes no statement, so it has no provenance to pin.
    # The surface is total over the manifest MINUS `PINNED_REFUSALS`, both
    # ways, exactly like `PINNED_CURRENCY` (composed at the batch-7 train).
    "Misc/Consumers March - Monthly Statement.pdf": "schema_default",
    "Misc/Field Trucking November 2025 .pdf": "schema_default",
    "Misc/First Farmers 2026 01-document.pdf": "schema_default",
    "Misc/KLR.May 31,2026 (1).pdf": "institution_default",
    "Misc/Link Bank April statement.pdf": "schema_default",
    "Misc/MidFlorida.pdf": "schema_default",
    "Misc/Texas Bank.pdf": "schema_default",
    "Misc/USD FEB 2026.pdf": "product",
    "Misc/WMB May 25.pdf": "schema_default",
    "Navy Fed/APRIL 2026.pdf": "schema_default",
    "Navy Fed/JUNE 2026.pdf": "schema_default",
    "Navy Fed/MARCH 2026.pdf": "schema_default",
    "Navy Fed/MAY 2026.pdf": "schema_default",
    "Others/Altana/Altana april 26.pdf": "schema_default",
    "Others/Altana/Altana june 26.pdf": "schema_default",
    "Others/Altana/Altana may 26.pdf": "schema_default",
    "Others/B1/b1 april 2026.pdf": "schema_default",
    "Others/B1/b1 feb 2026 (1).pdf": "schema_default",
    "Others/B1/b1 march 2026.pdf": "schema_default",
    "Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf": "printed",
    "Others/Banco/Banco Popular April 2026.pdf": "schema_default",
    "Others/Banco/Banco Popular Junio 2026.pdf": "schema_default",
    "Others/Banco/Banco Popular May 2026.pdf": "schema_default",
    "Others/Bluevine/bluevine_Statement_2026-04-02T21_36_47.777670Z (1).pdf": "schema_default",
    "Others/First Citizen/First Citizens Bank.pdf": "schema_default",
    "Others/IBC/IBC April (1).pdf": "schema_default",
    "Others/Navigant Credit Union 2026-06-30.pdf": "schema_default",
    "Others/Relay Operations-June-2026.pdf": "schema_default",
    "Others/Santander/Santander_April26.pdf": "schema_default",
    "Others/Santander/Santander_February 2026.pdf": "schema_default",
    "Others/Santander/Santander_March 2026.pdf": "schema_default",
    "Others/Secu/Secu.pdf": "schema_default",
    "PNC/PNC_Statement-2026-01-29.pdf": "schema_default",
    "PNC/PNC_Statement-2026-02-26.pdf": "schema_default",
    "PNC/PNC_Statement-2026-03-30.pdf": "schema_default",
    "PNC/PNC_Statement-2026-04-29.pdf": "schema_default",
    "PNC/PNC_Statement-2026-05-28.pdf": "schema_default",
    "RBC French/12 - Relevé Royale Décembre 2025 - Tommy Aspirot.pdf": "institution_default",
    "RBC/Chequing Statement-DEC+.pdf": "jurisdiction_default",
    "RBC/Chequing Statement-FEB+.pdf": "jurisdiction_default",
    "RBC/Chequing Statement-JAN+.pdf": "jurisdiction_default",
    "RBC/Chequing Statement-MAR+.pdf": "jurisdiction_default",
    "Regions/Regions-29-2026 (3).pdf": "schema_default",
    "Regions/Regions.pdf": "schema_default",
    "Regions/Regions_03-31-2026 (3) (1).pdf": "schema_default",
    "Regions/Regions_04-30-2026 (2) (1).pdf": "schema_default",
    "ScotiaBank/Scotiabank -2.pdf": "institution_default",
    "TD Can/Dec_31-Jan_30_2026 (6).pdf": "product",
    "TD Can/Feb_27-Mar_31_2026 (2).pdf": "product",
    "TD Can/Jan_30-Feb_27_2026 (3).pdf": "product",
    "TD Can/Mar_31-Apr_30_2026.pdf": "product",
    "TD Can/Nov_28-Dec_31_2025 (7).pdf": "product",
    "TD Can/TD Bank Bank Statement.pdf": "product",
    "TD/TD BANK NARROW APR.pdf": "schema_default",
    "TD/TD BANK NARROW FEB.pdf": "schema_default",
    "TD/TD BANK NARROW JAN.pdf": "schema_default",
    "TD/TD BANK NARROW MAR.pdf": "schema_default",
    "Truist/Truist AUTO February, 2026.pdf": "schema_default",
    "Truist/Truist AUTO March 2026.pdf": "schema_default",
    "Truist/Truist April, 2026.pdf": "schema_default",
    "Truist/Truist February, 2026.pdf": "schema_default",
    "Truist/Truist March, 2026.pdf": "schema_default",
    "US Bank/US Bank 2026-03-31 Statement.pdf": "schema_default",
    "US Bank/US Bank 2026-04-30 Statement.pdf": "schema_default",
    "WellsFargo/02-28-26 WellsFargo.pdf": "schema_default",
    "WellsFargo/03-31-26 WellsFargo.pdf": "schema_default",
    "WellsFargo/04-30-26 WellsFargo 1.pdf": "schema_default",
    "WellsFargo/113025 WellsFargo.pdf": "schema_default",
}

#: Do production's analysis callers hand `analyze_markdown` the intake object's
#: page list yet?
#:
#: `assess_document_integrity` accepts `sheets=` and fail-closes without it.
#: W3 §PIPEFIX card 2 added the parameter with no production caller passing it —
#: the page-declaration fix shipped inert — and WIRING-2 wired all three callers
#: and flipped this in the same commit as the approved truth-set ceremony.
#: `production_verdict` below must reproduce whatever the callers actually do,
#: because a harness that analyses differently from production pins a verdict
#: production never publishes, and a harness that stays unwired while production
#: gets wired goes silently blind on the one flag this whole check was added to
#: watch.
#:
#: `tests/test_corpus_gate_outcomes.py` holds this declaration to the real call
#: sites and sweeps the repository for callers that appear in neither list, so
#: flipping production without flipping this is a red test rather than a blind
#: gate. Flipping it moves pinned verdicts, which is a truth-set ceremony:
#: `PINNED_OUTCOMES` moves in the same commit or the gate goes RED. Both steps
#: are deliberate, which is the point.
PRODUCTION_SUPPLIES_SHEETS = True

#: The production analysis call sites this declaration describes, as
#: (module path, enclosing function). Every one of them must pass `sheets=` when
#: the wiring card activates.
#:
#: W3 §PIPEFIX P4b.5 tabulates three rows; only two are callers (its third is
#: that module's docstring usage example, and its fourth — the cache key
#: material — is a separate card). `batch.py` is the third real caller and was
#: NOT in P4b.5's table: it holds the intake object in scope (`_read_source`
#: returns it), `webapp/artifact_cache.py`'s own docstring names it a CLI
#: consumer of the cache, and although its `needs_review` column keys on
#: quality rather than on integrity, `_emit` serialises the report and passes it
#: to `build_record`, which runs `classify_outcome` — so batch.py publishes an
#: outcome class derived from these flags into its telemetry JSONL. It is a
#: production caller and must be wired at activation.
#:
#: `analysis/pipeline.py::analyze_document` is the L-1 DOCUMENT entry point.
#: It is declared rather than excused, and the distinction is load-bearing: it
#: forwards the page partition it was handed to `analyze_markdown`, and the
#: seams above move to it in the stage that teaches the payload readers the
#: document shape — so a version of it that stopped forwarding `sheets` would
#: take the page-declaration check offline for EVERY caller at once, which is
#: precisely the drift this declaration exists to make loud.
ANALYSIS_CALL_SITES = (
    ("discovery/runner.py", "_analyse"),
    ("webapp/worker.py", "_analyze_doc"),
    ("batch.py", "main"),
    ("analysis/pipeline.py", "analyze_document"),
)

#: Modules that call the analysis but must NOT be wired, each with the reason.
#: The sweep test requires every repository caller to be in this list or in
#: `ANALYSIS_CALL_SITES`, so a new caller cannot appear unclassified.
EXCLUDED_ANALYSIS_CALLERS = {
    # The two independent forensic oracles. Wiring them would couple the
    # oracles to the change under test, and it would buy nothing: neither
    # audits `flags`, `notes`, `risk_level` or `possible_document_issue`.
    "adb_forensic_audit.py": "independent audit oracle - must not track production",
    "balance_forensic_audit.py": "independent audit oracle - must not track production",
    # Resolves source text through `balance_forensic_audit.source_markdown`,
    # which returns text and no intake object, so it cannot supply sheets.
    "benchmark/ourside.py": "H-2 comparison harness; its resolver yields no page list",
    # Operate on already-extracted markdown; no intake object exists.
    "analyze.py": "single-file CLI over an OCR'd .md; no intake object",
    "adb_debug.py": "developer debug utility; prints, publishes nothing",
    "coverage_audit.py": "measurement script over markdown",
    "deterministic_coverage_audit.py": "measurement script over markdown",
    # This gate's own harness, governed by PRODUCTION_SUPPLIES_SHEETS above.
    "corpus_gate.py": "the harness itself; tracks the call sites by declaration",
    # W3 §REGFP's differential (read-only, offline). Excused on the question
    # this list actually asks — it publishes no verdict: it prints aggregate
    # counts and, for a mover, a content_sha256 and the differing FIELD NAMES.
    # Nothing it computes reaches a user, a job record or a discovery row.
    # Note it is not excused for the usual reason either: it DOES supply the
    # page list, because it reconstructs the intake partition out of the OCR
    # artifact and passes it as `sheets` — a sweep that fed the analysis a
    # different partition from the one the run fed it would measure a
    # difference it had itself created.
    # W3 FROSTOZK's family-replay instrument (read-only, offline). Excused on
    # the question this list asks: it publishes no verdict. It recomputes the
    # analysis for a named list of content hashes and prints counts and class
    # names - never an amount, a date or a name - so nothing it computes
    # reaches a user, a job record or a discovery row. It DOES supply the page
    # list, reconstructed from the OCR artifact, for the same reason the sweep
    # below does.
    "tools/frostozk_family_replay.py": (
        "read-only family replay; publishes no verdict, and supplies the "
        "reconstructed page partition"
    ),
    "tools/regfp_zero_movement_sweep.py": (
        "read-only archive differential; publishes no verdict, and already "
        "supplies the reconstructed page partition"
    ),
    # Batch 9's shared targeted-cohort proof (BATCH9-RULES). Same class as the
    # two instruments above: read-only over the run of record's cache,
    # publishes no verdict — it prints outcomes, reasons, reader ids, counts and
    # leaf PATHS for a named cohort — and it DOES supply the reconstructed page
    # partition as `sheets`, for the same reason the sweep does.
    "tools/cohort_replay.py": (
        "read-only cohort replay; publishes no verdict, and supplies the "
        "reconstructed page partition"
    ),
    # The L-1 design cell's three read-only instruments and stage 1's seam
    # probe, excused on the same two grounds as every replay above: each
    # publishes no verdict — payload/leaf comparisons, reader answers by CLASS,
    # skip-site counts, digests and content sha16s, never a figure, a name or a
    # date — and each already supplies the reconstructed page partition as
    # `sheets`. The first three were composed with the design and this guard was
    # RED for them at `train9` before stage 1 began: it runs only in the full
    # default suite, which is the train's, and the design cell's own floor ran
    # the canonical guards rather than the suite. Classified here rather than
    # left red, because a card cannot report a green floor over an inherited
    # failure and the classification is the honest answer to the question the
    # list asks.
    "tools/l1_design_payload_probe.py": (
        "read-only payload-shape probe; publishes no verdict, and already "
        "supplies the reconstructed page partition"
    ),
    "tools/l1_design_reader_probe.py": (
        "read-only payload-reader probe; publishes no verdict, and already "
        "supplies the reconstructed page partition"
    ),
    "tools/l1_design_skip_probe.py": (
        "read-only sibling-skip probe on the dispatch path; publishes no "
        "verdict, and already supplies the reconstructed page partition"
    ),
    # Stage 2's successor to the probe above, excused on the same two grounds.
    # It publishes no verdict — evidence-class names from a closed vocabulary,
    # counts, exception CLASS names, content sha16s and payload leaf PATHS,
    # never a figure, a name, a date or an omitted section's printed label — and
    # it supplies the reconstructed page partition, because a probe that fed the
    # analysis a different partition from the one the run fed it would measure a
    # difference it had itself created.
    "tools/l1s2_admission_probe.py": (
        "read-only omission probe at the document seam; publishes no verdict, "
        "and already supplies the reconstructed page partition"
    ),
    # W3 §EXTRACTPRIV. Calls the analysis to prove the LLM branch is NOT
    # reachable in deterministic mode: `extract_statement` is replaced by a
    # recording sentinel and the assertion is that it records nothing. It
    # analyses one string literal, never a document, and publishes no verdict —
    # so there is no intake object to supply and nothing for `sheets` to
    # describe. Excused rather than declared, deliberately: adding it to
    # ANALYSIS_CALL_SITES would assert that this probe should pass sheets,
    # which would be a false statement about what it measures.
    "tools/extractpriv_reachability.py": "reachability probe over a literal; asserts the call never happens",
    # W3 §WELCH's family replay, excused on the same two grounds as §REGFP's
    # sweep: it publishes no verdict — it prints an outcome CLASS and reason
    # per content_sha256, row counts, and the distribution of caller-named
    # fields, never a value from a statement — and it already supplies the
    # page partition it reconstructed from the OCR artifact, so a declared
    # call site would assert nothing this does not already do.
    "tools/welch_family_replay.py": (
        "read-only family replay; publishes no verdict, and already supplies "
        "the reconstructed page partition"
    ),
    # W3 sec COREENC's coverage instrument, excused on the same two grounds as
    # the sweep above: it publishes no verdict — it prints a content_sha256, an
    # outcome CLASS and three counts, never a figure, a name or a date — and it
    # already supplies the reconstructed page partition as `sheets`, because a
    # replay that fed the analysis a different partition from the one the run
    # fed it would measure a difference it had itself created.
    "tools/coreenc_family_replay.py": (
        "read-only population replay; publishes no verdict, and already "
        "supplies the reconstructed page partition"
    ),
    # W3 §DESCATTRIB's leaf-diff, and excused on the same two grounds as
    # §REGFP's sweep beside it: it publishes no verdict — it prints leaf PATHS,
    # movement classes and string LENGTHS, never a value — and it already
    # supplies the reconstructed page partition, because a differential that
    # fed the analysis a different partition from the one the run fed it would
    # measure a difference it had itself created.
    "tools/descattrib_movement.py": (
        "read-only description leaf-diff; publishes no verdict, and already "
        "supplies the reconstructed page partition"
    ),
    # W3 §DESCCOLS' reach-and-movement differential, excused on the same two
    # grounds. It publishes no verdict — counts, classes, leaf PATHS and string
    # LENGTHS, never a value. And it supplies the page list the analysis must
    # have: the pages the LADDER produced at this tree, which is the partition
    # a wired caller would hand it for exactly this text. That is the whole
    # point of the instrument — it measures the new extraction, so it must
    # analyse the new extraction's own partition rather than the archive's.
    "tools/desccols_movement.py": (
        "read-only extraction differential; publishes no verdict, and supplies "
        "the ladder's own page partition for the text it is measuring"
    ),
    # W3 §DESCCOLS' four remaining measurements — the geometry-oracle score,
    # the pinned probe, the fail-closed fallback and the publish/refuse
    # boundary. Excused on the same two grounds as the differential above: no
    # verdict is published (counts, classes and content_sha256 only — the
    # pinned probe prints the outcome CLASSES either side of a comparison,
    # never a figure), and every call supplies the ladder's own page partition
    # for the text being measured.
    "tools/desccols_proofs.py": (
        "read-only measurement pack; publishes no verdict, and supplies the "
        "ladder's own page partition for the text it is measuring"
    ),
    # W3 §DESCATTRIB's geometry oracle. Its `detections` subcommand analyses a
    # document to ask which classifier detections the attribution rule removes
    # and whether the text each was matched on was ever printed for the row it
    # was attributed to. Excused on the same two grounds: it publishes no
    # verdict — counts, classes and booleans, never a value — and it already
    # supplies the reconstructed page partition.
    "tools/descattrib_oracle.py": (
        "read-only geometry oracle; publishes no verdict, and already supplies "
        "the reconstructed page partition"
    ),
    # W3 §LILI's family replay. It runs the analysis over ONE named
    # 20-document population so that the card's coverage number is a
    # measurement rather than an inference from a successful parse — claimed
    # is not validated, and a parse that succeeds can still be withheld or
    # sent to review downstream. It prints that class to a console and nothing
    # else: no user, job record or discovery row ever sees it. Excused on the
    # same second ground as the sweeps above — it already supplies the
    # reconstructed page partition, because a replay that fed the analysis a
    # different partition from the one a run would feed it would measure a
    # difference it had itself created.
    "tools/lili_family_replay.py": (
        "read-only family replay over a named population; publishes no "
        "verdict, and already supplies the reconstructed page partition"
    ),
    # Five batch-8 instruments the cells' closure sessions committed after their
    # branch-level proofs (this guard runs only in the full suite, which is the
    # train's). Each is excused on the same two grounds as the entries above:
    # it publishes no verdict — outcome classes, counts, leaf paths, movement
    # classes and content_sha256s, never a figure, a name or a date — and it
    # already supplies the reconstructed page partition, because a replay that
    # fed the analysis a different partition from the one the run fed it would
    # measure a difference it had itself created. Composed at train8.
    "tools/glance_family_replay.py": (
        "read-only family replay (W3 sec GLANCE); publishes no verdict, and "
        "already supplies the reconstructed page partition"
    ),
    "tools/scanhyg_family_replay.py": (
        "read-only family replay (W3 sec SCANHYG); publishes no verdict, and "
        "already supplies the reconstructed page partition"
    ),
    "tools/scanhyg_pinned_replay.py": (
        "read-only pinned replay base vs branch (W3 sec SCANHYG); publishes no "
        "verdict, and already supplies the reconstructed page partition"
    ),
    "tools/withheldgrids_leaf_diff.py": (
        "read-only leaf-diff (W3 sec WITHHELDGRIDS); publishes no verdict, and "
        "already supplies the reconstructed page partition"
    ),
    "tools/withheldgrids_srcdates_audit.py": (
        "read-only source posting-date audit (W3 sec WITHHELDGRIDS); publishes "
        "no verdict, and already supplies the reconstructed page partition"
    ),
    # W3 §HYGIENE8's two base-vs-branch replays, excused on the same two
    # grounds as §REGFP's sweep: each publishes no verdict — counts, movement
    # classes, exception CLASS names, leaf PATHS and a content_sha256, never a
    # value — and each already supplies the reconstructed page partition as
    # `sheets`, because a replay that fed the analysis a different partition
    # from the one the run fed it would measure a difference it had itself
    # created. Added by the review-closure round (H14): the branch shipped
    # both instruments without this entry and the sweep above was red for it.
    "tools/hygiene8_family_replay.py": (
        "read-only base-vs-branch replay of the dispatched population; publishes "
        "no verdict, and already supplies the reconstructed page partition"
    ),
    "tools/hygiene8_pinned_replay.py": (
        "read-only base-vs-branch replay of the pinned 109; publishes no verdict, "
        "and already supplies the intake page list it computes once for both trees"
    ),
    # W3 §ROWCAP's three measurements — the row-capture signature probe, the
    # ceiling and the sheet-strip check. Excused on the same two grounds as
    # §REGFP's sweep above. None publishes a verdict: between them they print
    # a content_sha256, an outcome CLASS and reason, row COUNTS, coverage and
    # capture RATIOS, gate NAMES and how many printed strips a ledger
    # reproduces — never an amount, a date, a description or an account
    # number. And each supplies the reconstructed page partition as `sheets`,
    # because a measurement that fed the analysis a different partition from
    # the one the run fed it would be measuring a difference it had itself
    # created.
    "tools/rowcap_probe.py": (
        "read-only row-capture probe; publishes no verdict, and already "
        "supplies the reconstructed page partition"
    ),
    "tools/rowcap_ceiling.py": (
        "read-only ceiling measurement; publishes no verdict, and already "
        "supplies the reconstructed page partition"
    ),
    "tools/rowcap_sheet_strips.py": (
        "read-only printed-strip check; publishes no verdict, and already "
        "supplies the reconstructed page partition"
    ),
    # W3 §L1S1's cross-tree seam probe (RULE S at the pipeline seam), excused
    # on the same two grounds: it publishes no verdict — byte digests and leaf
    # paths only — and supplies the reconstructed page partition as `sheets`.
    "tools/l1s1_seam_probe.py": (
        "read-only cross-tree seam probe; publishes no verdict, and already "
        "supplies the reconstructed page partition"
    ),
    # W3 §PAGECOV's probe. Excused on the same first ground as the replays
    # above — it publishes no verdict: it prints a content_sha256, sheet and
    # declaration COUNTS, page ORDINALS, declaration-form NAMES, cause tags and
    # an outcome CLASS, never an amount, a date, a description or a name.
    #
    # Its second ground is stated differently from every entry above it, and
    # deliberately, because a list whose whole purpose is to record what each
    # caller does with `sheets` must not be allowed to imply something false.
    # The probe makes TWO kinds of call. Its control (`published_flags`) and
    # the `actual` arm of `blank_sheet_counterfactual` supply the reconstructed
    # page partition, exactly as the sweeps do and for the same reason: a probe
    # that fed the analysis a different partition from the one the run fed it
    # would report a disagreement it had itself created. But the second arm of
    # `blank_sheet_counterfactual` supplies a partition that is DELIBERATELY
    # NOT the run's — one placeholder character substituted for each
    # text-empty sheet — because measuring what the page-declaration check
    # would decide if a blank sheet counted is the whole point of that mode.
    # That is a measurement of a counterfactual, never a claim about a
    # document, and it reaches no user, job record or discovery row. It is
    # excused rather than declared for that reason: listing it in
    # ANALYSIS_CALL_SITES would assert that this caller supplies the intake
    # partition, which on one of its two arms is untrue by design.
    "tools/pagecov_probe.py": (
        "read-only page-declaration probe; publishes no verdict, supplies the "
        "reconstructed page partition on its control arm, and deliberately "
        "substitutes one on its counterfactual arm"
    ),
}

# Audited columns whose value is a path, compared without regard to separator.
# `folder` (ADB audit) is written with os.sep, so the committed CSV carries
# Windows backslashes and a Linux re-run reproduces forward slashes; `path`
# (balance audit) is already POSIX everywhere and is listed so a future
# regeneration on Windows cannot reintroduce the same split. Keep this list
# minimal — see `comparable`. Note that `statement` is NOT here: a filename may
# legitimately contain a backslash on POSIX, and that difference must fail.
PATH_VALUED_FIELDS = frozenset({"folder", "path"})

# Statements the gate cannot cover offline. Empty by design: every image-only
# statement has a committed OCR artifact. An entry here must name the file and
# the reason, and it is reported as an exclusion rather than a pass.
KNOWN_EXCLUSIONS: dict[str, str] = {}

# The audit oracles must stay independent of the production financial modules.
# Built from parts so this file's own source never contains the literals it
# searches for.
FORBIDDEN_MODULES = ("adb", "metrics")
INDEPENDENT_SOURCES = (
    "adb_forensic_audit.py",
    "balance_forensic_audit.py",
    "corpus_artifacts.py",
    "corpus_gate.py",
)


@dataclass
class Check:
    name: str
    ok: bool
    summary: str
    details: list[str] = field(default_factory=list)


@dataclass
class Result:
    checks: list[Check] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def add(self, name: str, ok: bool, summary: str, details: list[str] | None = None) -> Check:
        check = Check(name, ok, summary, list(details or []))
        self.checks.append(check)
        return check

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_csv_rows(rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, str]]:
    """Serialise freshly computed rows exactly as the audit scripts write them.

    Round-tripping through DictWriter/DictReader is what makes the comparison
    apples-to-apples: the committed CSV holds DictWriter's rendering of these
    same values, so `None` becomes `''` and `True` becomes `'True'` on both
    sides rather than only one.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    return list(csv.DictReader(buffer))


def corpus_pdfs(corpus: Path) -> list[Path]:
    """Every PDF on disk under the root — pinned and foreign alike.

    Used only for foreign-file accounting. The audited set comes from
    `manifest_paths`, never from this.
    """
    return sorted(corpus.rglob("*.pdf"))


def manifest_paths(balance_csv: list[dict[str, str]]) -> list[str]:
    """The pinned manifest: corpus-relative POSIX paths of the audited set.

    The balance audit is the enumerator because it stores the whole relative
    path in one column. `check_inventory` proves the ADB audit pins exactly the
    same paths, so neither audit can drift into being the sole authority.
    """
    return sorted({row["path"] for row in balance_csv})


def manifest_pdfs(corpus: Path, manifest: list[str]) -> list[Path]:
    """Resolve the pinned manifest against a corpus root, in manifest order."""
    return [corpus / Path(rel) for rel in manifest]


def sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def relative_key(row: dict[str, str]) -> str:
    """Corpus-relative path for an ADB audit row, which stores folder + name.

    The ADB audit writes its folder with the OS-native separator, so the
    committed CSV carries backslashes. Normalise before matching anything
    against the corpus, which is enumerated as POSIX paths.
    """
    folder = row.get("folder", ".").replace("\\", "/")
    return row["statement"] if folder in {"", "."} else f"{folder}/{row['statement']}"


def comparable(column: str, value: str) -> str:
    """Render one audited field for comparison, separator-agnostic if it is a path.

    Only `PATH_VALUED_FIELDS` are normalised, and deliberately so. The ADB audit
    stores `folder` with the OS-native separator, so a CSV written on Windows
    pins `Others\\Altana` while a Linux re-run reproduces `Others/Altana` — the
    same folder, rendered by a different os.sep, with no financial field
    involved. A blanket replace across every column would also silently equate
    two genuinely different values that happen to contain a backslash, which is
    the opposite of what this gate is for: an escaped string inside a
    description or a root_cause must still be able to fail.
    """
    return value.replace("\\", "/") if column in PATH_VALUED_FIELDS else value


def compare_rows(
    fresh: list[dict[str, str]],
    committed: list[dict[str, str]],
    key: str,
    label: str,
    limit: int = 25,
) -> tuple[bool, list[str]]:
    committed_by_key = {row[key]: row for row in committed}
    fresh_by_key = {row[key]: row for row in fresh}
    details: list[str] = []

    missing = sorted(set(committed_by_key) - set(fresh_by_key))
    added = sorted(set(fresh_by_key) - set(committed_by_key))
    for name in missing:
        details.append(f"{label}: {name} is in the committed audit but was not re-audited")
    for name in added:
        details.append(f"{label}: {name} was audited but is absent from the committed audit")

    drifted = 0
    for name in sorted(set(fresh_by_key) & set(committed_by_key)):
        want, got = committed_by_key[name], fresh_by_key[name]
        for column in want:
            if comparable(column, want[column]) != comparable(column, got.get(column, "")):
                drifted += 1
                if len(details) < limit:
                    details.append(
                        f"{label}: {name} [{column}] expected {want[column]!r}, got {got.get(column, '')!r}"
                    )
    if drifted > limit:
        details.append(f"{label}: ... and {drifted - limit} further field differences")
    return (not missing and not added and drifted == 0), details


def check_inventory(result: Result, manifest: list[str], corpus: Path,
                    balance_csv: list[dict[str, str]], adb_csv: list[dict[str, str]]) -> None:
    """The pinned manifest is complete, agreed by both audits, and on disk."""
    details: list[str] = []
    ok = True

    if len(manifest) != EXPECTED_PDF_COUNT:
        ok = False
        details.append(
            f"pinned manifest holds {len(manifest)} paths, expected {EXPECTED_PDF_COUNT}"
        )

    for label, audited in (("balance audit", [row["path"] for row in balance_csv]),
                           ("ADB audit", [relative_key(row) for row in adb_csv])):
        if len(audited) != EXPECTED_PDF_COUNT:
            ok = False
            details.append(f"{label} holds {len(audited)} rows, expected {EXPECTED_PDF_COUNT}")
        if len(set(audited)) != len(audited):
            ok = False
            details.append(f"{label} holds duplicate paths")
        for name in sorted(set(manifest) - set(audited)):
            ok = False
            details.append(f"{label}: {name} is pinned but has no audited row")
        for name in sorted(set(audited) - set(manifest)):
            ok = False
            details.append(f"{label}: {name} is audited but absent from the pinned manifest")

    for rel in manifest:
        if not (corpus / Path(rel)).is_file():
            ok = False
            details.append(f"{rel} is pinned but missing from the corpus root")

    result.add(
        "inventory",
        ok,
        f"{len(manifest)} pinned corpus PDFs, all on disk and audited by both oracles",
        details,
    )


def check_foreign_files(result: Result, corpus: Path, manifest: list[str]) -> int:
    """Count PDFs under the root that are not pinned. Reported, never fatal.

    The corpus root doubles as the landing zone for untracked discovery
    material. Those documents are not the validated corpus, carry no audit row,
    and the gate makes no claim about them — but it must never pretend they are
    not there. Names are deliberately withheld: they are sensitive source data.
    """
    pinned = set(manifest)
    foreign = sorted(
        rel for rel in (path.relative_to(corpus).as_posix() for path in corpus_pdfs(corpus))
        if rel not in pinned
    )
    details: list[str] = []
    if foreign:
        folders = {rel.split("/")[0] if "/" in rel else "." for rel in foreign}
        # ASCII only: this line is printed, and a console in a legacy code page
        # must not be able to turn the merge authority into a UnicodeEncodeError.
        summary = f"{len(foreign)} non-corpus PDFs present - ignored (discovery archive)"
        details = [
            f"spread across {len(folders)} top-level folder(s) under the corpus root",
            "names withheld: unpinned documents under this root are sensitive source data",
            "these are not audited, not parsed, and not part of any gate claim",
        ]
    else:
        summary = "no non-corpus PDFs under the corpus root"
    result.add("foreign_files", True, summary, details)
    return len(foreign)


def check_source_integrity(result: Result, corpus: Path,
                           balance_csv: list[dict[str, str]]) -> None:
    """Every pinned PDF exists and still hashes to its pinned SHA-256."""
    pinned = {row["path"]: row["sha256"] for row in balance_csv}
    details: list[str] = []
    verified = 0
    for rel, expected in sorted(pinned.items()):
        path = corpus / Path(rel)
        if not path.is_file():
            details.append(f"{rel} is pinned but missing from the corpus root")
            continue
        actual = sha256_upper(path.read_bytes())
        if actual != expected:
            details.append(f"{rel} SHA-256 drifted: pinned {expected}, on disk {actual}")
        else:
            verified += 1
    result.add(
        "source_integrity",
        not details,
        f"{verified}/{len(pinned)} pinned source PDFs match their pinned SHA-256",
        details,
    )


def check_ocr_coverage(result: Result, source_types: dict[str, str],
                       manifest: list[str], cache: Path) -> None:
    scanned = sorted(name for name, kind in source_types.items() if kind.startswith("scanned"))
    native = sorted(name for name, kind in source_types.items() if not kind.startswith("scanned"))
    entries = manifest_entries(cache)
    pinned = set(manifest)
    orphans = sorted(entry["path"] for entry in entries.values() if entry["path"] not in pinned)

    details = [f"served from committed OCR artifact: {name}" for name in scanned]
    details += [f"cache holds an artifact for a document not in the corpus: {name}" for name in orphans]
    result.add(
        "ocr_coverage",
        not orphans,
        f"{len(native)} native-text + {len(scanned)} committed-OCR = "
        f"{len(source_types)} statements resolved offline; no live OCR, no model calls",
        details,
    )


def check_exclusions(result: Result) -> None:
    details = [f"{name}: {reason}" for name, reason in sorted(KNOWN_EXCLUSIONS.items())]
    result.add(
        "exclusions",
        True,
        f"{len(KNOWN_EXCLUSIONS)} named exclusions",
        details,
    )


def check_outcomes(result: Result, label: str, rows: list[dict[str, str]],
                   pass_status: str, withheld_status: str) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    withheld = {row["statement"] for row in rows if row["status"] == withheld_status}
    refused = {row["statement"] for row in rows if row["status"] == REFUSED_STATUS}
    details: list[str] = []
    ok = True

    if counts.get(pass_status, 0) != EXPECTED_PASS:
        ok = False
        details.append(f"{counts.get(pass_status, 0)} {pass_status}, expected {EXPECTED_PASS}")
    if counts.get(withheld_status, 0) != EXPECTED_WITHHELD:
        ok = False
        details.append(
            f"{counts.get(withheld_status, 0)} {withheld_status}, expected {EXPECTED_WITHHELD}"
        )
    # A REFUSED row is an oracle reporting that the analysis published nothing
    # to audit. Which documents those are is pinned in `PINNED_REFUSALS` and
    # held to the product itself by `check_outcome_classes`; here the count is
    # pinned so a second document cannot quietly join them.
    if counts.get(REFUSED_STATUS, 0) != EXPECTED_REFUSED:
        ok = False
        details.append(
            f"{counts.get(REFUSED_STATUS, 0)} {REFUSED_STATUS}, expected {EXPECTED_REFUSED}"
        )
    expected_refused = {Path(rel).name for rel in PINNED_REFUSALS}
    if refused != expected_refused:
        ok = False
        for name in sorted(refused - expected_refused):
            details.append(f"{name} is newly refused; a published statement must not stop publishing")
        for name in sorted(expected_refused - refused):
            details.append(
                f"{name} is a pinned refusal and must stay refused, not reinterpreted as passing"
            )
    for status, count in sorted(counts.items()):
        if status not in {pass_status, withheld_status, REFUSED_STATUS}:
            ok = False
            details.append(f"unexpected status {status} on {count} statement(s)")
    if withheld != WITHHELD_STATEMENTS:
        ok = False
        for name in sorted(withheld - WITHHELD_STATEMENTS):
            details.append(f"{name} is newly withheld; a passing statement must not become withheld")
        for name in sorted(WITHHELD_STATEMENTS - withheld):
            details.append(
                f"{name} is a proven source contradiction and must stay withheld, not reinterpreted as passing"
            )

    result.add(
        f"{label}_outcomes",
        ok,
        f"{label}: {EXPECTED_PASS} pass, {EXPECTED_WITHHELD} withheld (same three "
        f"statements), {EXPECTED_REFUSED} pinned refusal",
        details,
    )


#: The one Average Daily Balance basis the platform publishes, as a literal.
#:
#: Built from parts and compared as a string rather than imported from
#: `analysis.adb`: this file is one of the four `INDEPENDENT_SOURCES` that may
#: not import the production financial modules, and the whole point of the
#: check is that the gate holds its OWN copy of the doctrine. If the engine's
#: constant is ever edited, this string does not move with it and the gate
#: goes red - which is exactly the ceremony a basis change should need.
EXPECTED_ADB_BASIS = "calendar_day_printed_period"
EXPECTED_ADB_POLICY = "canonical_v1"

#: The gate's OWN copy of the `currency_source` vocabulary, held here for the
#: same reason `EXPECTED_ADB_BASIS` is: an audit that imported
#: `analysis.schema.CURRENCY_SOURCES` would widen automatically the moment
#: someone widened the enum, and a surface that agrees with the thing it audits
#: by construction is not a surface. Adding a class to the product means adding
#: it here too, deliberately.
CURRENCY_SOURCES = (
    "printed",
    "product",
    "jurisdiction_default",
    "institution_default",
    "model_extracted",
    "schema_default",
)


#: Published integrity risk, ranked clear -> worst. A level this gate has never
#: seen ranks WORST, so an unknown token cannot make a document look safer than
#: the strongest thing any of its accounts said.
_RISK_ORDER = ("clear", "review", "high")


def _account_verdict(payload: dict, index: int | None) -> _Verdict:
    """One ACCOUNT's verdict, exactly as this gate has always built one."""
    from telemetry.record import classify_outcome

    outcome, _reason = classify_outcome(payload)
    integrity = payload.get("integrity") or {}
    return _Verdict(
        outcome,
        # Published ORDER, not sorted: the block is pinned as it is served.
        flags=tuple(integrity.get("flags") or ()),
        notes=tuple(integrity.get("notes") or ()),
        risk_level=str(integrity.get("risk_level") or ""),
        possible_document_issue=bool(integrity.get("possible_document_issue")),
        account_index=index,
    )


def _assert_document_verdict_follows(
    document: _Verdict, per: tuple[_Verdict, ...]
) -> None:
    """Design §6.5's first bullet: the document verdict must FOLLOW from its accounts.

    The L1-S3 review found the per-account verdicts returned and discarded at
    the only call site (`verdict, _accounts = document_verdicts(payload)`),
    which made "one verdict per account plus a document verdict" a shape rather
    than a claim. Three ways the fold could stop following, each its own
    refusal — and a named function rather than a block inside the fold, so each
    clause can be doctored from outside and shown to fire:

    * an outcome no account holds, that is not a document-level refusal;
    * a document flag no account raised — a flag the fold invented;
    * a risk level milder than the strongest an account published.

    It raises rather than returning: a gate that publishes a verdict it cannot
    derive is worse than one that stops.
    """
    account_outcomes = [verdict.outcome for verdict in per]
    if document.outcome not in account_outcomes and document.outcome != "failed":
        raise ValueError(
            f"the document verdict {document.outcome!r} is an outcome none of "
            f"its {len(per)} accounts holds {account_outcomes!r}, and it is not "
            f"a document-level refusal (document_verdict_does_not_follow)")
    account_flags = {flag for verdict in per for flag in verdict.flags}
    invented = [flag for flag in document.flags if flag not in account_flags]
    if invented:
        raise ValueError(
            f"the document verdict carries flag(s) {invented!r} that no account "
            f"raised (document_verdict_invents_a_flag)")

    def _rank(level: str) -> int:
        return _RISK_ORDER.index(level) if level in _RISK_ORDER else len(_RISK_ORDER)

    strongest_account = max((_rank(verdict.risk_level) for verdict in per), default=0)
    if _rank(document.risk_level) < strongest_account:
        raise ValueError(
            f"the document risk level {document.risk_level!r} is milder than "
            f"the strongest an account published "
            f"(document_verdict_softens_an_account)")


def document_verdicts(payload: dict) -> tuple[_Verdict, tuple[_Verdict, ...]]:
    """`(document verdict, per-account verdicts)` for one published payload.

    On today's payload the account tuple holds exactly one verdict and the
    document verdict IS it, field for field, `account_index` included (`None`).
    That is not a special case bolted on: a single-account payload takes the
    same path it always did, so every pinned entry in `PINNED_OUTCOMES` and
    `PUBLISHED_OUTCOME` compares against the same object it compared against
    before.

    On a document publishing several accounts the document verdict is a FOLD,
    and every clause of it can only make the document's verdict WORSE than an
    account's:

    * the outcome is `classify_document`'s — the weakest account's, with the
      document-level overrides;
    * the flags are the DOCUMENT-SCOPE ones (`split_integrity_flags`, the
      partition S1 built for exactly this question), de-duplicated in printed
      account order. An account-scope flag stays where it was read: it is a
      fact about that account and reading it at the document would say the
      whole document carries it;
    * the notes are the union, in printed order;
    * the risk level is the WORST any account published, and
      `possible_document_issue` is true if ANY account said so.

    Nothing here picks an account. The pinned corpus is path-keyed with no
    account column, which is why the per-account verdicts are RETURNED rather
    than pinned: a multi-account pinned document needs a path+account key and
    that is a truth-set ceremony, not a gate change.
    """
    from analysis.payload_shape import is_document_payload, payload_accounts
    from analysis.pipeline import split_integrity_flags
    from telemetry.record import classify_document

    if not is_document_payload(payload):
        verdict = _account_verdict(payload, None)
        return verdict, (verdict,)

    surface = "corpus_gate.py::document_verdicts"
    accounts = payload_accounts(payload, surface=surface)
    per = tuple(
        _account_verdict(account, index)
        for index, account in enumerate(accounts, start=1)
    )
    outcome, _reason = classify_document(payload)
    flags: dict[str, None] = {}
    notes: dict[str, None] = {}
    for verdict in per:
        for flag in split_integrity_flags(verdict.flags)[0]:
            flags.setdefault(flag, None)
        for note in verdict.notes:
            notes.setdefault(note, None)
    risk = max(
        (verdict.risk_level for verdict in per),
        key=lambda level: (
            _RISK_ORDER.index(level) if level in _RISK_ORDER else len(_RISK_ORDER)
        ),
        default="",
    )
    document = _Verdict(
        outcome,
        flags=tuple(flags),
        notes=tuple(notes),
        risk_level=risk,
        possible_document_issue=any(
            verdict.possible_document_issue for verdict in per),
        account_index=None,
    )
    _assert_document_verdict_follows(document, per)
    return document, per


def production_verdict(path: Path, cache: Path) -> tuple[_Verdict, dict]:
    """The published verdict for one pinned statement, resolved as production does.

    The PRODUCTION intake ladder with both OCR rungs disabled, which is the
    same resolution the discovery dry run and the telemetry corpus anchor use.
    Image-only statements fall through to their committed OCR artifact, so this
    stays offline: no OCR binary, no endpoint, no model call.

    Why not `balance_forensic_audit.source_markdown`, which the two oracles
    use: NOT because the two disagree — measured over the pinned manifest they
    are byte-identical on 109 of 109 — but because `source_markdown` returns
    text and nothing else. `parse_statement` returns the intake object, and its
    `pages` are what a wired caller must hand to the analysis. Only this
    resolver can still be correct after the wiring card lands.

    The page list is supplied to the analysis exactly when production supplies
    it — see `PRODUCTION_SUPPLIES_SHEETS`, which a test holds to the real call
    sites. It is never recovered by re-splitting the markdown: page content is
    untrusted and can print a separator line (W3 §PIPEFIX P4b.1). The six
    image-only statements resolve to a committed OCR artifact rather than to an
    intake object, and since WIRING-2 that artifact carries the same intake
    run's page list (`corpus_artifacts.cached_pages`, proven to re-join to the
    committed markdown byte for byte) — which is what makes the approved
    Regions ceremony executable offline at all. An artifact with no committed
    page list still yields None, and the check fail-closes for it exactly as it
    does for any caller that cannot prove page structure.
    """
    # Imported here rather than at module scope so the two audit oracles above
    # keep loading without the production analysis stack: this check reads the
    # product's own verdict on purpose and is the one check in this file that
    # is not oracle-independent.
    from analysis.pipeline import analyze_document
    from analysis.serialization import document_report_to_dict
    from ocr.inspect import inspect_pdf
    from ocr.pipeline import parse_statement

    raw = path.read_bytes()
    document = parse_statement(
        raw,
        source_file=path.name,
        profile=inspect_pdf(raw),
        force_ocr=False,
        allow_local_ocr=False,
        allow_visual_ocr=False,
    )
    if document is not None:
        markdown = document.to_markdown()
        sheets = list(document.pages) if PRODUCTION_SUPPLIES_SHEETS else None
    else:
        markdown = cached_markdown(raw, cache)
        sheets = cached_pages(raw, cache) if PRODUCTION_SUPPLIES_SHEETS else None
        if markdown is None:
            raise ArtifactError(
                f"{path} has no native text and no committed OCR artifact in "
                f"{cache}; refusing to run OCR in offline mode"
            )
    payload = document_report_to_dict(
        analyze_document(markdown, parse_mode="deterministic", sheets=sheets)
    )
    verdict, _accounts = document_verdicts(payload)
    # The payload rides along so `check_adb_doctrine` can read the published
    # ADB basis without a THIRD full analysis pass over the manifest.
    return verdict, payload


def check_adb_doctrine(result: Result, payloads: dict[str, dict]) -> None:
    """One user-facing ADB, on one basis, on every pinned document.

    Two things are enforced, and the difference between them matters.

    **The basis and policy stamps are pinned as TOTAL assertions.** Every
    pinned document that publishes a payload must publish
    `underwriting_adb_basis == "calendar_day_printed_period"` and
    `underwriting_adb_policy == "canonical_v1"` - including the three withheld
    ones, because a refused LEDGER still has to say which methodology refused
    it. A pinned REFUSAL publishes no payload at all, so there is nothing to
    stamp and nothing to compare; those are counted in the summary line rather
    than skipped silently, and `check_outcome_classes` is what holds them. That
    is the
    doctrine made mechanical: no code path can substitute another denominator
    convention without turning this gate red.

    **The alternates are NOT pinned per document, deliberately.** Pinning five
    more numbers per statement would make every future ledger improvement a
    truth-set ceremony for figures nobody publishes. What is pinned instead is
    the property that makes them meaningful: an alternate basis must actually
    be a different computation. So for every pinned document that publishes a
    validated ADB, `alternates["banking_day"]` must differ from the canonical
    figure UNLESS one of two things makes them equal by arithmetic rather than
    by substitution - the period contains no non-banking day (identical day
    sets), or the daily series is flat (every basis over a constant series is
    that constant). Both exemptions are checked from the published daily
    ledger, not asserted.

    **The distinctness clause SKIPS documents it cannot examine, and the count
    is published so the arithmetic is visible.** A statement with no published
    ADB has no canonical figure to compare against, so there is nothing to
    assert - the three withheld documents are skipped here while still being
    held to the basis stamp above, and `distinct + exemptions + skipped` must
    account for all 109. A skip is not an exemption: an exemption is a document
    that WAS examined and whose equality was explained, a skip is a document
    that published nothing to examine.

    One further skip case, which the pinned corpus does not currently contain:
    `alternates["banking_day"]` is None when the period holds no banking day at
    all - a Saturday-to-Sunday statement, or a short period wholly inside a
    holiday weekend. The engine reports None there rather than a mean over an
    empty day set, and such a document lands in the skipped count for the same
    reason: there is no alternate figure to be distinct from.
    """
    details: list[str] = []
    stamped = 0
    distinct = 0
    skipped = 0
    exempt_same_days = 0
    exempt_flat = 0
    for rel in sorted(payloads):
        metrics = (payloads[rel].get("metrics") or {})
        adb = metrics.get("adb") or {}
        basis = adb.get("underwriting_adb_basis")
        policy = adb.get("underwriting_adb_policy")
        if basis != EXPECTED_ADB_BASIS:
            details.append(
                f"{rel}: publishes underwriting_adb_basis {basis!r}, and the only "
                f"basis this platform publishes is {EXPECTED_ADB_BASIS!r}"
            )
        else:
            stamped += 1
        if policy != EXPECTED_ADB_POLICY:
            details.append(
                f"{rel}: publishes underwriting_adb_policy {policy!r}, expected "
                f"{EXPECTED_ADB_POLICY!r}"
            )

        canonical = metrics.get("average_daily_balance")
        alternates = adb.get("underwriting_adb_alternates") or {}
        banking = alternates.get("banking_day")
        daily = adb.get("daily_balances") or []
        if canonical is None or banking is None or not daily:
            skipped += 1
            continue
        days = [date.fromisoformat(entry["date"]) for entry in daily]
        non_banking = any(day.weekday() >= 5 or _is_holiday(day) for day in days)
        balances = {entry["ending_balance"] for entry in daily}
        if banking != canonical:
            distinct += 1
        elif not non_banking:
            exempt_same_days += 1
        elif len(balances) == 1:
            exempt_flat += 1
        else:
            details.append(
                f"{rel}: the banking-day alternate equals the canonical ADB "
                f"({canonical}) over a period that contains a non-banking day and "
                f"a moving balance - an alternate basis that is not a different "
                f"computation is a substituted one"
            )

    result.add(
        "adb_doctrine",
        not details,
        f"{stamped}/{len(payloads)} statements publish the canonical basis "
        f"{EXPECTED_ADB_BASIS!r}; banking-day alternate distinct on {distinct}, "
        f"skipped {skipped} unpublished "
        f"({exempt_same_days} all-banking-day periods, {exempt_flat} flat ledgers); "
        f"{len(PINNED_REFUSALS)} pinned refusal(s) publish no payload to stamp",
        details,
    )


def check_currency(result: Result, manifest: list[str], payloads: dict[str, dict]) -> None:
    """Every pinned document publishes the currency that is pinned for it.

    A TOTAL assertion in both directions, which is what makes it a surface
    rather than a spot check: the map must name every pinned path and no other,
    and every published `statement.currency` must equal its pin. A document
    whose payload could not be produced is reported here too rather than
    passing by omission — `check_outcome_classes` already fails on it, and a
    currency check that quietly skipped the same document would be exactly the
    kind of blind spot this exists to remove.

    The compared value is the published FIELD (`payload["statement"]
    ["currency"]`), not rendered UI text. That is the value
    `webapp/static/app.js` hands to `Intl.NumberFormat`, so pinning the field
    pins what the analyst sees without coupling the gate to any template.

    Reuses the payloads `check_outcome_classes` already produced, so the whole
    surface costs no extra analysis pass over the corpus.
    """
    details: list[str] = []
    # The surface is total over the manifest MINUS the pinned refusals. A
    # document that publishes no statement publishes no denomination, so
    # pinning one for it would assert something the product never states; the
    # subtraction is written both ways so neither a missing pin nor a stale one
    # can pass.
    denominated = [rel for rel in manifest if rel not in PINNED_REFUSALS]
    for rel in sorted(set(denominated) - set(PINNED_CURRENCY)):
        details.append(
            f"{rel}: pinned in the manifest but no expected currency is recorded; "
            f"every pinned document must state one"
        )
    for rel in sorted(set(PINNED_CURRENCY) - set(denominated)):
        details.append(
            f"{rel}: a currency is pinned for a path that is not a denominated "
            f"pinned document"
        )

    counts: dict[str, int] = {}
    verified = 0
    for rel in denominated:
        expected = PINNED_CURRENCY.get(rel)
        payload = payloads.get(rel)
        if payload is None:
            details.append(f"{rel}: no payload was produced, so its currency is unverified")
            continue
        # `PINNED_CURRENCY` is keyed by corpus-relative PATH with no account
        # column, and a document publishing several accounts can denominate
        # them differently. Reading one account's code as the document's would
        # pin a denomination the paper never gave the document. Admitting one
        # needs a path+account key, which is a truth-set ceremony.
        refuse_document_payload(payload, surface="corpus_gate.py::check_currency")
        actual = (payload.get("statement") or {}).get("currency")
        counts[str(actual)] = counts.get(str(actual), 0) + 1
        if expected is None:
            continue
        if actual != expected:
            details.append(
                f"{rel}: publishes currency {actual!r}, pinned {expected!r}; the "
                f"denomination of a pinned statement is truth-set material and "
                f"does not move without a ceremony"
            )
        else:
            verified += 1

    split = " / ".join(f"{n} {name}" for name, n in sorted(counts.items()))
    result.add(
        "currency",
        not details,
        f"{verified}/{len(denominated)} statements publish their pinned currency: "
        f"{split} (+{len(manifest) - len(denominated)} pinned refusal(s), which "
        f"publish no statement and so no denomination)",
        details,
    )


def check_currency_source(result: Result, manifest: list[str],
                          payloads: dict[str, dict]) -> None:
    """Every pinned document publishes the currency PROVENANCE that is pinned.

    `check_currency` above proves no denomination moved. This proves no
    denomination changed its reason, which the currency check is structurally
    blind to: a reader that stops reading the code its document prints and falls
    back to an institution constant publishes the identical three letters, and
    the only difference in the whole payload is this field. That is a real
    regression — the platform's knowledge of the document got worse — and this
    is the surface that sees it.

    TOTAL in both directions like its sibling: the map must name every pinned
    path and no other, every value must be in `Statement`'s closed vocabulary,
    and a document whose payload could not be produced is reported rather than
    passing by omission.

    Reuses the payloads `check_outcome_classes` already produced, so the
    provenance surface costs no extra analysis pass over the corpus.
    """
    details: list[str] = []
    # Total over the manifest MINUS the pinned refusals, both ways, exactly as
    # `check_currency` is: a document that publishes no statement has no
    # provenance to pin (composed at the batch-7 train, where REPAIR-DOCTRINE's
    # pinned refusal met CURRENCY-SOURCE's 109-entry surface).
    denominated = [rel for rel in manifest if rel not in PINNED_REFUSALS]
    for rel in sorted(set(denominated) - set(PINNED_CURRENCY_SOURCE)):
        details.append(
            f"{rel}: pinned in the manifest but no expected currency source is "
            f"recorded; every pinned document must state where its currency came from"
        )
    for rel in sorted(set(PINNED_CURRENCY_SOURCE) - set(denominated)):
        details.append(
            f"{rel}: a currency source is pinned for a path that is not a denominated "
            f"pinned document"
        )
    for rel, source in sorted(PINNED_CURRENCY_SOURCE.items()):
        if source not in CURRENCY_SOURCES:
            details.append(
                f"{rel}: pins currency source {source!r}, which is not in the "
                f"published vocabulary {list(CURRENCY_SOURCES)}"
            )

    counts: dict[str, int] = {}
    verified = 0
    for rel in denominated:
        expected = PINNED_CURRENCY_SOURCE.get(rel)
        payload = payloads.get(rel)
        if payload is None:
            details.append(
                f"{rel}: no payload was produced, so its currency source is unverified"
            )
            continue
        refuse_document_payload(
            payload, surface="corpus_gate.py::check_currency_source")
        actual = (payload.get("statement") or {}).get("currency_source")
        counts[str(actual)] = counts.get(str(actual), 0) + 1
        if expected is None:
            continue
        if actual != expected:
            details.append(
                f"{rel}: publishes currency source {actual!r}, pinned {expected!r}; "
                f"the evidence a denomination rests on does not move without a "
                f"ceremony, even when the denomination itself does not"
            )
        else:
            verified += 1

    split = " / ".join(f"{n} {name}" for name, n in sorted(counts.items()))
    result.add(
        "currency_source",
        not details,
        f"{verified}/{len(denominated)} statements publish their pinned currency "
        f"provenance: {split} (+{len(manifest) - len(denominated)} pinned refusal(s), "
        f"which publish no statement and so no provenance)",
        details,
    )


#: The gate's own federal-bank-holiday test, kept independent of
#: `analysis.adb`'s: this file may not import the production financial modules,
#: and a check that borrowed the engine's calendar could not detect the engine
#: getting the calendar wrong. Only the observed-Monday rule is reproduced here,
#: which is all the exemption above needs.
def _is_holiday(day: date) -> bool:
    year = day.year
    fixed = [(1, 1), (7, 4), (11, 11), (12, 25)] + ([(6, 19)] if year >= 2021 else [])
    for month, dom in fixed:
        observed = date(year, month, dom)
        if observed.weekday() == 6:
            observed = observed + timedelta(days=1)
        elif observed.weekday() == 5:
            continue
        if observed == day:
            return True
    for month, weekday, nth in ((1, 0, 3), (2, 0, 3), (9, 0, 1), (10, 0, 2), (11, 3, 4)):
        first = date(year, month, 1)
        candidate = first + timedelta(
            days=(weekday - first.weekday()) % 7 + 7 * (nth - 1)
        )
        if candidate == day:
            return True
    may_last = date(year, 6, 1) - timedelta(days=1)
    return day == may_last - timedelta(days=(may_last.weekday() - 0) % 7)


def check_outcome_classes(result: Result, corpus: Path, manifest: list[str],
                          cache: Path) -> tuple[dict[str, int], dict[str, dict]]:
    """Every pinned document's published verdict is the one that is pinned.

    See `PINNED_OUTCOMES` for why this exists: the audit oracles compare
    financial values, so they are blind to a class moving inside PASS, to a
    published integrity flag appearing or disappearing without a class change,
    and to `risk_level` / `possible_document_issue` moving independently of
    both. This compares the product's whole published verdict, per document,
    and fails RED on any difference.

    A path in `PINNED_REFUSALS` is pinned the other way round: the analysis
    must RAISE, with that exact message. Two movements are possible and both
    are RED — it publishes a verdict again, or it raises something else —
    because a refusal that has drifted to a different cause is no longer the
    fact that was reviewed.
    """
    details: list[str] = []
    counts: dict[str, int] = {}
    payloads: dict[str, dict] = {}
    for rel in manifest:
        expected = PINNED_OUTCOMES.get(rel, PUBLISHED_OUTCOME)
        refusal = PINNED_REFUSALS.get(rel)
        try:
            actual, payload = production_verdict(corpus / Path(rel), cache)
        except Exception as exc:  # a document we cannot verdict is a failure
            if refusal is not None and type(exc) is RuntimeError and str(exc) == refusal:
                counts["refused"] = counts.get("refused", 0) + 1
                continue
            details.append(f"{rel}: could not be analysed: {type(exc).__name__}: {exc}")
            counts["error"] = counts.get("error", 0) + 1
            continue
        counts[actual.outcome] = counts.get(actual.outcome, 0) + 1
        if refusal is not None:
            details.append(
                f"{rel}: is pinned as a refusal ({refusal!r}) and now publishes a "
                f"{actual.outcome} verdict; a pinned refusal is a pinned fact and "
                f"does not move without a ceremony"
            )
            continue
        payloads[rel] = payload
        if actual == expected:
            continue
        if actual.outcome != expected.outcome:
            details.append(
                f"{rel}: outcome class moved {expected.outcome} -> {actual.outcome}; "
                f"a pinned statement's class is truth-set material and does not "
                f"move without a ceremony"
            )
        for flag in sorted(set(actual.flags) - set(expected.flags)):
            details.append(f"{rel}: newly publishes integrity flag {flag!r}")
        for flag in sorted(set(expected.flags) - set(actual.flags)):
            details.append(f"{rel}: no longer publishes pinned integrity flag {flag!r}")
        if set(actual.flags) == set(expected.flags) and actual.flags != expected.flags:
            details.append(
                f"{rel}: integrity flags are published in a different order: "
                f"{list(expected.flags)} -> {list(actual.flags)}"
            )
        for note in sorted(set(actual.notes) - set(expected.notes)):
            details.append(f"{rel}: newly publishes integrity note {note!r}")
        for note in sorted(set(expected.notes) - set(actual.notes)):
            details.append(f"{rel}: no longer publishes pinned integrity note {note!r}")
        if set(actual.notes) == set(expected.notes) and actual.notes != expected.notes:
            details.append(f"{rel}: integrity notes are published in a different order")
        if actual.risk_level != expected.risk_level:
            details.append(
                f"{rel}: risk_level moved {expected.risk_level} -> {actual.risk_level}"
            )
        if actual.possible_document_issue != expected.possible_document_issue:
            details.append(
                f"{rel}: possible_document_issue moved "
                f"{expected.possible_document_issue} -> {actual.possible_document_issue}"
            )

    split = " / ".join(f"{n} {name}" for name, n in sorted(counts.items()))
    result.add(
        "outcome_classes",
        not details,
        f"{len(manifest)} statements publish their pinned verdict "
        f"(outcome class and the whole integrity block): {split}",
        details,
    )
    return counts, payloads


def check_oracle_independence(result: Result) -> None:
    details: list[str] = []
    for name in INDEPENDENT_SOURCES:
        source = (ROOT / name).read_text(encoding="utf-8")
        for module in FORBIDDEN_MODULES:
            for statement in (f"from analysis.{module}", f"import analysis.{module}"):
                if statement in source:
                    details.append(f"{name} contains {statement!r}")
    result.add(
        "oracle_independence",
        not details,
        f"{len(INDEPENDENT_SOURCES)} audit modules import no production financial mathematics",
        details,
    )


def _stats(source_types: dict[str, str], pinned: int, foreign: int, started: float) -> dict[str, Any]:
    return {
        "corpus_pdfs": pinned,
        "foreign_pdfs": foreign,
        "native_text_statements": sum(
            1 for kind in source_types.values() if not kind.startswith("scanned")
        ),
        "committed_ocr_statements": sum(
            1 for kind in source_types.values() if kind.startswith("scanned")
        ),
        "pass": EXPECTED_PASS,
        "withheld": EXPECTED_WITHHELD,
        "refused": EXPECTED_REFUSED,
        "exclusions": len(KNOWN_EXCLUSIONS),
        "runtime_seconds": round(time.perf_counter() - started, 1),
    }


def run_gate(corpus: Path, cache: Path) -> Result:
    result = Result()
    started = time.perf_counter()

    balance_csv = read_csv(BALANCE_CSV)
    adb_csv = read_csv(ADB_CSV)
    manifest = manifest_paths(balance_csv)
    pdfs = manifest_pdfs(corpus, manifest)

    check_inventory(result, manifest, corpus, balance_csv, adb_csv)
    foreign = check_foreign_files(result, corpus, manifest)
    check_source_integrity(result, corpus, balance_csv)

    absent = [path for path in pdfs if not path.is_file()]
    if absent:
        # Both oracles would raise on the first unreadable file. Stop here so
        # the run still renders a red report naming what is gone.
        result.add(
            "audits",
            False,
            f"not run: {len(absent)} pinned statement(s) missing from {corpus}",
            [f"{path.relative_to(corpus).as_posix()} is pinned but missing" for path in absent[:25]],
        )
        result.stats = _stats({}, len(manifest), foreign, started)
        return result

    # Balance oracle: opening/ending/highest/lowest across backend, API,
    # dashboard binding, CSV, XLSX, and the package surfaces.
    balance_rows: list[dict[str, Any]] = []
    jobs: list[Any] = []
    expected_by_id: dict[str, Any] = {}
    source_types: dict[str, str] = {}
    for path in pdfs:
        row, job, expected = balance_forensic_audit.audit_source(path, corpus, ocr_cache=cache)
        balance_rows.append(row)
        jobs.append(job)
        expected_by_id[job.id] = expected
        source_types[path.relative_to(corpus).as_posix()] = row["source_type"]
    balance_forensic_audit.apply_package_results(balance_rows, jobs, expected_by_id)
    fresh_balance = as_csv_rows(balance_rows, balance_forensic_audit.FIELDS)
    ok, details = compare_rows(fresh_balance, balance_csv, "path", "balance")
    result.add(
        "balance_audit",
        ok,
        f"{len(fresh_balance)} statements reproduce every audited balance field "
        f"across backend, API, dashboard, CSV, XLSX, and package surfaces",
        details,
    )

    # ADB oracle: independent daily-ledger reconstruction vs backend, API, and
    # dashboard-package ADB.
    adb_rows: list[dict[str, Any]] = []
    for path in pdfs:
        markdown = adb_forensic_audit.source_markdown(path, ocr_cache=cache)
        adb_rows.append(adb_forensic_audit.audit_one(path, corpus, markdown))
    fresh_adb = as_csv_rows(adb_rows, adb_forensic_audit.FIELDS)
    # Key both sides by corpus-relative path so identically named statements in
    # different folders can never be compared against each other. `folder` stays
    # in the compared columns, so a separator change still surfaces as drift.
    committed_adb = [dict(row, statement=relative_key(row)) for row in adb_csv]
    keyed_adb = [dict(row, statement=relative_key(row)) for row in fresh_adb]
    ok, details = compare_rows(keyed_adb, committed_adb, "statement", "adb")
    result.add(
        "adb_audit",
        ok,
        f"{len(fresh_adb)} statements reproduce every audited ADB field across "
        f"backend, API, and dashboard-package surfaces",
        details,
    )

    check_outcomes(result, "balance", fresh_balance, "PASS", "WITHHELD_SOURCE_CONTRADICTION")
    check_outcomes(result, "adb", fresh_adb, "PASS", "WITHHELD")
    verdicts, payloads = check_outcome_classes(result, corpus, manifest, cache)
    check_adb_doctrine(result, payloads)
    check_currency(result, manifest, payloads)
    check_currency_source(result, manifest, payloads)
    check_ocr_coverage(result, source_types, manifest, cache)
    check_exclusions(result)
    check_oracle_independence(result)

    result.stats = _stats(source_types, len(pdfs), foreign, started)
    result.stats["verdicts"] = verdicts
    return result


def render(result: Result) -> str:
    lines = ["Corpus gate", ""]
    for check in result.checks:
        lines.append(f"[{'PASS' if check.ok else 'FAIL'}] {check.name}: {check.summary}")
        for detail in check.details:
            lines.append(f"         {detail}")
    lines += ["", f"Coverage: {result.stats['corpus_pdfs']} pinned PDFs "
                  f"({result.stats['native_text_statements']} native text, "
                  f"{result.stats['committed_ocr_statements']} committed OCR), "
                  f"{result.stats['exclusions']} exclusions",
              f"Ignored:  {result.stats['foreign_pdfs']} non-corpus PDFs under the corpus root",
              f"Outcomes: {result.stats['pass']} PASS / {result.stats['withheld']} WITHHELD"
              f" / {result.stats['refused']} REFUSED",
              "Verdicts: " + (
                  " / ".join(
                      f"{count} {name}"
                      for name, count in sorted(result.stats["verdicts"].items())
                  )
                  if result.stats.get("verdicts") else "not run"
              ),
              f"Runtime:  {result.stats['runtime_seconds']}s",
              "",
              "RESULT: " + ("GREEN" if result.ok else "RED")]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic offline corpus gate.")
    parser.add_argument(
        "--corpus",
        "--corpus-root",
        dest="corpus",
        default=str(CORPUS),
        help="Corpus root the pinned manifest is resolved against "
             "(default: this checkout's 'Bank Statements'). Lets one checkout's "
             "gate code audit another checkout's corpus root.",
    )
    parser.add_argument("--ocr-cache", default=str(DEFAULT_CACHE))
    parser.add_argument("--json", help="Write a machine-readable report here.")
    args = parser.parse_args()

    result = run_gate(Path(args.corpus), Path(args.ocr_cache))
    print(render(result))
    if args.json:
        payload = {
            "ok": result.ok,
            "stats": result.stats,
            "checks": [
                {"name": c.name, "ok": c.ok, "summary": c.summary, "details": c.details}
                for c in result.checks
            ],
        }
        Path(args.json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
