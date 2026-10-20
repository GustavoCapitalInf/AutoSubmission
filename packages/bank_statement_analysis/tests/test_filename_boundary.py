"""The provenance admissibility boundary: a rename cannot change an answer.

The OCR/native layer prefixes every document with `<!-- source: <file> ... -->`.
A filename is operator-supplied metadata — trivially wrong, and on the discovery
archive a folder-derived guess — so no financial claim may rest on it.

R-4b made DETECTION filename-blind (`parser_registry.admissible_text`, pinned by
`test_parser_parity.test_detection_is_invariant_to_the_filename_echo`). PARSING
was explicitly left out, and that carve-out was the vulnerability: F-PROVENANCE
measured 7 of 10 sampled parsers reading financial evidence out of the comment —
period replacement recomputing ADB (up to +521%, one sign flip), period-windowing
dropping transactions, `wells._infer_year` taking the document's FIRST year token
(the comment's), and `date_tokens.period_from_long_dates` raising `KeyError` on an
abbreviated month (a `ParserCrashError` in deterministic mode; in the webapp's
auto mode a silent fall-through to LLM extraction — an engine swap by filename).

W3 FILENAME-BOUNDARY closed it at ONE seam: `pipeline.analyze_markdown` applies
`admissible_text` before dispatch, so every parser is behind the boundary and no
parser carries its own exclusion. These tests are what keeps it closed. They are
deliberately in the DEFAULT suite (no corpus PDFs, no OCR cache, no network):
this invariant must be cheap enough that nobody is tempted to skip it.

Every fixture is synthetic. No customer, account number, amount or date from the
archive appears in this file.
"""
from __future__ import annotations

import json

import pytest

from analysis import parser_registry_entries  # noqa: F401  — populates the registry
from analysis.date_tokens import period_from_long_dates
from analysis.parser_registry import admissible_text, resolve
from analysis.pipeline import analyze_markdown
from analysis.serialization import report_to_dict
from ocr.document import StatementMarkdown

# ---------------------------------------------------------------------------
# The hostile filename set — the F-PROVENANCE mutation grammar
# ---------------------------------------------------------------------------

#: A benign operator filename. Every fixture's published answer under this name
#: is the control every hostile name is compared against.
CONTROL_NAME = "statement.pdf"

#: Each entry is a filename an operator could plausibly produce (banks' own
#: export names quote the statement's title line) that also parses as period
#: evidence in at least one parser's grammar. `wide_*` are the SILENT attack:
#: they widen the period to the whole calendar year, so every transaction stays
#: inside the window, nothing fails closed, no integrity flag fires, and only
#: the average-daily-balance denominator moves.
HOSTILE_FILENAMES = {
    # generic / degenerate provenance
    "empty": "",
    "absurdly_long": "A" * 4000 + ".pdf",
    "money_amounts": "invoice $1,234,567.89 refund $9,876.54.pdf",
    "account_number": "Account Number: 000000123456789.pdf",
    "txn_row_shaped": "01/15 ACH DEPOSIT COMPANY XYZ 5,000.00.pdf",
    "pipe_field_inject": "x | pages: 999 | model: evil | empty: 0 | y.pdf",
    # period grammars, anchored on the fixtures' own printed period
    "anchor_through_long": "January 1, 2048 through January 31, 2048.pdf",
    "anchor_for_to": "for January 1, 2048 to January 31, 2048.pdf",
    "anchor_to_long": "January 1, 2048 to January 31, 2048.pdf",
    "anchor_for_the_period": "For the Period 01/01/2048 to 01/31/2048.pdf",
    "anchor_period_ending": "For the period ending January 31, 2048.pdf",
    "anchor_square_title": "Checking statement January 1 - January 31, 2048.pdf",
    "anchor_td_tokens": "JAN 1/48 - JAN 31/48.pdf",
    "anchor_wells_labels": "Beginning balance on 1/1 Ending balance on 1/31.pdf",
    # abbreviated months — the `date_tokens` crash vector
    "abbrev_through": "Jan 1, 2048 through Dec 31, 2048.pdf",
    "abbrev_mixed": "Jan 1, 2048 through December 31, 2048.pdf",
    # bare years — the `wells._infer_year` vector
    "bare_year": "2020.pdf",
    "bare_year_padded": "scan 2020 copy.pdf",
    # the silent period-widening attack
    "wide_through_long": "January 1, 2054 through December 31, 2054.pdf",
    "wide_for_period": "For the Period 01/01/2054 to 12/31/2054.pdf",
    "wide_period_ending": "For the period ending December 31, 2054.pdf",
    # page labels — the `assess_document_integrity` page-declaration vector
    "page_label_single": "Page 1 of 9.pdf",
    "page_label_full_set": "Page 1 of 4 Page 2 of 4 Page 3 of 4 Page 4 of 4.pdf",
    # another bank's name — the `apply_statement_repairs` substring-gate vector
    "bofa_repair_gate": "BANK OF AMERICA statement.pdf",
    "regions_repair_gate": "REGIONS BANK statement.pdf",
    # everything at once
    "kitchen_sink": (
        "January 1, 2048 through January 31, 2048 "
        "for January 1, 2048 to January 31, 2048 "
        "For the Period 01/01/2048 to 01/31/2048 "
        "For the period ending January 31, 2048 "
        "Checking statement January 1 - January 31, 2048 "
        "JAN 1/48 - JAN 31/48.pdf"
    ),
}

#: A token that appears in no fixture body, so finding it anywhere in a published
#: report proves the filename reached the answer.
SENTINEL = "ZZQXPROVENANCEZZ"

# ---------------------------------------------------------------------------
# Fixtures — one representative document per parser family
# ---------------------------------------------------------------------------

CHASE = (
    "JPMorgan Chase Bank, N.A. Member FDIC\n"
    "January 1, 2054 through January 31, 2054\n"
    "*start*summary\n"
    "Chase Business Complete Checking\n"
    "CHECKING SUMMARY\n"
    "INSTANCES AMOUNT\n"
    "Beginning Balance $1,000.00\n"
    "Deposits and Additions 1 500.00\n"
    "Electronic Withdrawals 1 -450.00\n"
    "Ending Balance 2 $1,050.00\n"
    "*end*summary\n"
    "*start*deposits and additions\n"
    "DEPOSITS AND ADDITIONS\n"
    "DATE DESCRIPTION AMOUNT\n"
    "01/05 Example Deposit Source 500.00\n"
    "Total Deposits and Additions $500.00\n"
    "*end*deposits and additions\n"
    "*start*electronic withdrawal\n"
    "ELECTRONIC WITHDRAWALS\n"
    "DATE DESCRIPTION AMOUNT\n"
    "01/09 Example Counterparty Payment -450.00\n"
    "Total Electronic Withdrawals $450.00\n"
    "*end*electronic withdrawal\n"
)

SQUARE_CHECKING = (
    "Square Checking Routing number: 000000000\n"
    "Account number: 4321\n"
    "Checking statement June 1 - June 30, 2054\n"
    "Example Trading Co\n"
    "Starting balance Activities Ending balance $100.00 3 $150.00\n"
    "Block Inc. 1955 Broadway, Suite 600 Oakland, CA 94612\n"
    "squareup.com/help\n"
    "Date Details Activity type Balance Amount\n"
    "6/1/2054 Example Merchant Card spend $80.00 -$20.00\n"
    "6/2/2054 4 Activities Sales $180.00 $100.00\n"
    "6/3/2054 Example Bank Transfer out $150.00 -$30.00\n"
)

WELLS_FARGO = (
    "Wells Fargo Everyday Checking\n"
    "March 31, 2054         Page 1 of 4\n"
    "Account number:   1234567890  (primary account)\n"
    "Transaction history\n"
    "WF_NATIVE_TRANSACTIONS\n"
    "WF_TX|3/2|Deposit From A Customer|500.00||1,500.00\n"
    "WF_TX|3/4|Purchase At A Merchant||200.00|1,300.00\n"
    "WF_NATIVE_TRANSACTIONS_END\n"
)

BMO_CA_BUSINESS = (
    "1 SAMPLE STREET SOMEWHERE, ON A1A1A1 Business Banking\n"
    "Your branch address:\n"
    "Your Branch SAMPLE BRANCH Transit number: 1234\n"
    "NORTHWIND SUPPLY LTD. 1 SAMPLE STREET SOMEWHERE ON A1A1A1\n"
    "For questions about your statement call (000) 000-0000\n"
    "Direct Banking 1-000-000-0000 www.bmo.com\n"
    "Your Plan Enhanced Plan\n"
    "Business Banking statement\n"
    "For the period ending April 30, 2054\n"
    "Summary of account\n"
    "Total Total Closing Opening amounts amounts balance ($) on - + = Account "
    "balance ($) debited ($) credited ($) April 30, 2054\n"
    "Business Account # 1234 1000-001 1,000.00 300.00 500.00 1,200.00\n"
    "Transaction details\n"
    "Amounts debited Amounts credited Date Description from your account ($) "
    "to your account ($) Balance ($)\n"
    "Business Account # 1234 1000-001\n"
    "Account Type: CHQ BUS Business name: NORTHWIND SUPPLY LTD.\n"
    "Apr 01 Opening balance 1,000.00\n"
    "Apr 02 Debit Card Purchase, SAMPLE MERCHANT 100.00 900.00\n"
    "Apr 03 Direct Deposit, SAMPLE PAYER 500.00 1,400.00\n"
    "Apr 04 INTERAC e-Transfer Sent 200.00 1,200.00\n"
    "Apr 30 Closing totals 300.00 500.00\n"
    "Number of items processed 2 .................................. 1 ..........\n"
    "Page 1 of 1\n"
)

#: parser id -> the document that parser must claim. The brief's minimum set:
#: two US layouts whose periods are printed in different grammars, the parser
#: with the year-inference defect, and a non-US layout.
FIXTURES = {
    "chase": CHASE,
    "wells_fargo": WELLS_FARGO,
    "square_checking": SQUARE_CHECKING,
    "bmo_ca_business": BMO_CA_BUSINESS,
}


def _markdown(body: str, filename: str) -> str:
    """The document exactly as the intake ladder emits it, under `filename`."""
    return StatementMarkdown(source_file=filename, model="test-model", pages=[body]).to_markdown()


def _published(body: str, filename: str) -> str:
    """The published answer, canonicalized — what a reader of the report sees."""
    report = analyze_markdown(_markdown(body, filename), parse_mode="deterministic")
    return json.dumps(report_to_dict(report), sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# Vacuity guards — a fixture that stopped being parsed would pass everything
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("parser_id", sorted(FIXTURES))
def test_each_fixture_is_claimed_by_the_parser_it_stands_for(parser_id):
    """Without this, a fixture that silently stopped parsing would make every
    invariance assertion below trivially true (identical failures compare equal).
    """
    dispatch = resolve(_markdown(FIXTURES[parser_id], CONTROL_NAME))
    assert dispatch.outcome == "claimed", (
        f"{parser_id} fixture is {dispatch.outcome}, not claimed "
        f"(candidates={[c.id for c in dispatch.candidates]})"
    )
    assert dispatch.registration.id == parser_id, (
        f"{parser_id} fixture is now claimed by {dispatch.registration.id}"
    )
    assert dispatch.statement is not None
    assert dispatch.statement.transactions, f"{parser_id} fixture parsed no transactions"


# ---------------------------------------------------------------------------
# The primary invariant
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("parser_id", sorted(FIXTURES))
@pytest.mark.parametrize("label", sorted(HOSTILE_FILENAMES))
def test_published_analysis_is_invariant_to_a_hostile_filename(parser_id, label):
    """Identical statement bytes under a hostile name publish an identical answer.

    This is the whole boundary in one assertion: the comparison is the FULL
    serialized report, not a chosen field list, so a parser that starts reading
    provenance for any reason at all fails here rather than being caught later
    by whichever field somebody remembered to watch.
    """
    body = FIXTURES[parser_id]
    control = _published(body, CONTROL_NAME)
    assert _published(body, HOSTILE_FILENAMES[label]) == control, (
        f"{parser_id}: renaming the file to {label!r} changed the published analysis"
    )


@pytest.mark.parametrize("parser_id", sorted(FIXTURES))
def test_no_filename_text_reaches_the_published_report(parser_id):
    """The stronger, field-agnostic form: filename bytes are simply absent."""
    published = _published(FIXTURES[parser_id], f"{SENTINEL} 2020 statement.pdf")
    assert SENTINEL not in published, (
        f"{parser_id}: filename text appears in the published report"
    )


@pytest.mark.parametrize("parser_id", sorted(FIXTURES))
def test_the_boundary_is_idempotent_at_the_parse_seam(parser_id):
    """Pre-stripping the comment is a no-op, because the seam already strips it.

    Pins F-PROVENANCE's fuzz5 parity property permanently: the pipeline's input
    is `admissible_text(markdown)` whether or not the caller already applied it.
    Also the regression test for the boundary being MOVED rather than removed —
    if a future edit strips the comment somewhere that is not the seam, the two
    sides of this comparison stop agreeing.
    """
    body = FIXTURES[parser_id]
    raw = _markdown(body, "some operator name 2020.pdf")
    pre_stripped = admissible_text(raw)
    assert pre_stripped != raw, "fixture must actually carry a source comment"
    left = json.dumps(report_to_dict(analyze_markdown(raw, parse_mode="deterministic")),
                      sort_keys=True, default=str)
    right = json.dumps(report_to_dict(analyze_markdown(pre_stripped, parse_mode="deterministic")),
                       sort_keys=True, default=str)
    assert left == right


def test_the_boundary_is_the_detect_sweeps_own_preparation(monkeypatch):
    """Where the rebind comes from, now that it comes from `prepare` (#PREPHAND).

    `PreparedDocument`'s first act is `admissible_text(markdown)` — the same
    function this module has always pinned — and the pipeline takes its
    admissible text from there rather than computing it alongside. The risk
    that buys the second sweep's preparation is that the boundary quietly
    becomes something else, so this asserts the three facts that would move:
    the document is prepared ONCE, from the raw text; the sweep runs on that
    preparation; and the text it exposes is `admissible_text` of the input,
    character for character.
    """
    from analysis import pipeline as pipeline_module
    from analysis.parser_registry import PreparedDocument

    raw = _markdown(FIXTURES["chase"], "some operator name 2020.pdf")
    prepared_from: list[str] = []
    swept: list[object] = []
    real_prepare, real_resolve = pipeline_module.prepare, pipeline_module.resolve
    monkeypatch.setattr(pipeline_module, "prepare",
                        lambda md: prepared_from.append(md) or real_prepare(md))
    monkeypatch.setattr(pipeline_module, "resolve",
                        lambda doc: swept.append(doc) or real_resolve(doc))

    report = analyze_markdown(raw, parse_mode="deterministic")

    assert prepared_from == [raw], "the analysis prepared its document more than once"
    assert len(swept) == 1 and isinstance(swept[0], PreparedDocument)
    assert swept[0].admissible == admissible_text(raw)
    assert report.statement.transactions, "vacuous: the fixture must still parse"


# ---------------------------------------------------------------------------
# The two non-parser consumers of the raw markdown (SC-FILENAME survey)
# ---------------------------------------------------------------------------
#
# The boundary is at STAGE ENTRY, not at the parser call site, because `parse`
# is not the only consumer of the document text. `analyze_markdown` also hands
# the same string to `apply_statement_repairs` (whose BofA and Regions repairs
# are gated on a substring of it) and to `assess_document_integrity` (whose
# page-declaration set is a regex over it). Both are covered by the one rebind;
# these tests are what proves it, per consumer, rather than by inspection.


@pytest.mark.parametrize("parser_id", sorted(FIXTURES))
def test_a_filename_naming_another_bank_cannot_fire_that_banks_repair(parser_id):
    """`repair_bofa_summary` / `repair_regions_summary` gate on a substring of
    the markdown. A filename satisfying that gate could overwrite another bank's
    published balances, on every path including LLM extractions.
    """
    body = FIXTURES[parser_id]
    for token, filename in (("BANK OF AMERICA", HOSTILE_FILENAMES["bofa_repair_gate"]),
                            ("REGIONS", HOSTILE_FILENAMES["regions_repair_gate"])):
        raw = _markdown(body, filename)
        # The gate is genuinely satisfiable from the filename alone...
        assert token in raw.upper(), "fixture no longer exercises the gate"
        assert token not in body.upper(), "fixture body must not contain the token"
        # ...and the boundary is what stops it reaching the repair stage.
        assert token not in admissible_text(raw).upper()
        assert _published(body, filename) == _published(body, CONTROL_NAME), (
            f"{parser_id}: a filename containing {token!r} changed the published analysis"
        )


def test_a_page_label_filename_cannot_fabricate_a_page_declaration():
    """`missing_declared_statement_page` is a fraud-relevant flag. A filename
    spelling "Page 1 of 9" must not invent a declaration the document never
    printed — that would raise the flag on a clean statement.
    """
    for parser_id in ("chase", "square_checking", "bmo_ca_business"):
        body = FIXTURES[parser_id]
        control = analyze_markdown(_markdown(body, CONTROL_NAME), parse_mode="deterministic")
        assert "missing_declared_statement_page" not in control.integrity.flags, (
            f"{parser_id} fixture must start clean for this test to mean anything"
        )
        renamed = analyze_markdown(
            _markdown(body, HOSTILE_FILENAMES["page_label_single"]), parse_mode="deterministic"
        )
        assert "missing_declared_statement_page" not in renamed.integrity.flags, (
            f"{parser_id}: a page-label filename fabricated a page declaration"
        )
        assert renamed.integrity.risk_level == control.integrity.risk_level


def test_a_page_label_filename_cannot_suppress_the_missing_page_flag():
    """The dangerous direction: the wells fixture prints "Page 1 of 4" and is
    missing pages 2-4, so it carries the flag. A filename supplying the absent
    labels would complete the set and clear a fraud-risk signal by rename.
    """
    body = FIXTURES["wells_fargo"]
    control = analyze_markdown(_markdown(body, CONTROL_NAME), parse_mode="deterministic")
    assert "missing_declared_statement_page" in control.integrity.flags, (
        "the wells fixture must carry the flag for this test to mean anything"
    )
    renamed = analyze_markdown(
        _markdown(body, HOSTILE_FILENAMES["page_label_full_set"]), parse_mode="deterministic"
    )
    assert "missing_declared_statement_page" in renamed.integrity.flags, (
        "a page-label filename suppressed the missing-page flag"
    )
    assert renamed.integrity.risk_level == control.integrity.risk_level == "review"


def test_admissible_text_is_idempotent():
    raw = _markdown(CHASE, "anything 2020.pdf")
    once = admissible_text(raw)
    assert admissible_text(once) == once
    assert "source:" not in once.splitlines()[0]


# ---------------------------------------------------------------------------
# The `date_tokens` crash vector (F-PROVENANCE card 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "Jan 5, 2054 through February 4, 2054",       # abbreviated start
        "January 5, 2054 through Feb 4, 2054",        # abbreviated end
        "Jan 5, 2054 through Feb 4, 2054",            # both abbreviated
        "Balance 5, 2026 through February 4, 2054",   # a capitalized non-month
        "Statement 1, 2026 through Period 2, 2026",   # neither side is a month
    ],
)
def test_a_long_date_phrase_that_is_not_months_is_a_non_match(phrase):
    """`([A-Z][a-z]+)` matches any capitalized word, so a phrase shaped like a
    long period but headed by something else reaches the month lookup. The
    documented contract is "None means try another period format" — a KeyError
    escaping instead is a `ParserCrashError` in deterministic mode and, in the
    webapp's auto mode, a silent fall-through to LLM extraction.
    """
    assert period_from_long_dates(f"Statement {phrase} detail") is None


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("January 5, 2054 through February 4, 2054", ("2054-01-05", "2054-02-04")),
        ("December 1, 2053 through December 31, 2053", ("2053-12-01", "2053-12-31")),
        ("May 1, 2054 through June 30, 2054", ("2054-05-01", "2054-06-30")),
    ],
)
def test_genuine_long_dates_are_unchanged(phrase, expected):
    """The card-2 fix must narrow nothing: real long-date periods still parse."""
    assert period_from_long_dates(f"Period {phrase} shown") == expected


# ---------------------------------------------------------------------------
# The analysis cache key (F-PROVENANCE card 3)
# ---------------------------------------------------------------------------


def test_analysis_cache_is_shared_across_renames_of_one_statement(tmp_path):
    """A rename must not mint a second durably-cached copy of one answer.

    Keying the analysis stage on the raw markdown put the filename back into the
    key by the header route, so N renames of one statement cached N identical
    reports and recomputed each. The stage now keys on `admissible_text`.
    """
    from webapp.artifact_cache import ArtifactCache, cached_analysis
    from webapp.storage import Storage

    cache = ArtifactCache(Storage(tmp_path / "data"))
    calls: list[str] = []

    def analyse(markdown: str):
        def compute() -> dict:
            calls.append(markdown)
            return {"answer": 1}

        return cached_analysis(markdown, compute=compute, cache=cache,
                               parse_mode="deterministic")

    first = analyse(_markdown(CHASE, "original name.pdf"))
    second = analyse(_markdown(CHASE, "renamed copy 2020.pdf"))

    assert first.cache_key == second.cache_key, "a rename produced a different analysis cache key"
    assert not first.cached and second.cached, "the renamed upload should have hit the cache"
    assert len(calls) == 1, f"analysis recomputed {len(calls)} times across a rename"


def test_analysis_cache_still_separates_genuinely_different_statements(tmp_path):
    """The key must not have been widened into a collision: different BODIES
    under one filename remain different analyses."""
    from webapp.artifact_cache import ArtifactCache, cached_analysis
    from webapp.storage import Storage

    cache = ArtifactCache(Storage(tmp_path / "data"))
    calls: list[str] = []

    def analyse(markdown: str):
        def compute() -> dict:
            calls.append(markdown)
            return {"answer": len(calls)}

        return cached_analysis(markdown, compute=compute, cache=cache,
                               parse_mode="deterministic")

    first = analyse(_markdown(CHASE, "same name.pdf"))
    second = analyse(_markdown(WELLS_FARGO, "same name.pdf"))

    assert first.cache_key != second.cache_key
    assert not second.cached
    assert len(calls) == 2
