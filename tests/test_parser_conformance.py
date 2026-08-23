"""R-4: every registration is conformance-tested, and the registry says so.

Before R-4 six parsers had no direct test at all and the rest were tested only
through whichever corpus document happened to exercise them. This module gives
all 76 registrations the same four checks, and — crucially — enumerates the
registry to do it, so a parser added without a fixture fails here rather than
being discovered later by a wrong parse.

The four checks per registration:

1. **detection-positive** — it recognises a minimal document carrying its own
   bank's identification.
2. **detection-negative** — run as a full cross product: every other
   registration's fixture must NOT be claimed. 76 × 75 = 5,700 assertions. This
   is the check that matters for discovery (WAVE2_BRIEF R-4): it proves parser
   X does not claim bank Y's statement, which arithmetic reconciliation cannot
   catch when a wrong parse happens to balance.
3. **self-invalidation** — a header with no ledger is not a statement, so
   `parse` must decline rather than invent one.
4. **filename invariance** — detection must not depend on the source filename
   echoed into the markdown as `<!-- SOURCE: ... -->`. That text is metadata,
   not evidence; the RFC's detect contract admits the document, not its name.

Check 4 found two real defects. They are recorded here as a pinned set, not
patched: R-4 reports parser defects to Ocean, it does not silently fix them.
See `docs/moneythumb-replacement/R4_CONFORMANCE_FINDINGS.md`.
"""
from __future__ import annotations

import re

import pytest

from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401  — populates the registry
from tests.data.parser_conformance_fixtures import ALTERNATE_FIXTURES, FIXTURES

REGISTRATIONS = pr.registrations()
IDS = [registration.id for registration in REGISTRATIONS]

#: The OCR/native-text layer prefixes every document with a comment naming the
#: source file. `corpus_gate.py` documents carry it; so will every discovery
#: document.
SOURCE_COMMENT_RE = re.compile(r"^<!--\s*SOURCE:.*?-->\s*$", re.MULTILINE | re.IGNORECASE)

#: A statement that belongs to no registration, used as the host document when
#: testing what a *mention* of a bank does. Asserted to be unclaimed below.
NEUTRAL_HOST = (
    "COMMUNITY TRUST BANK\nStatement of Account\nBeginning Balance\nEnding Balance\n"
)

#: Findings R4-1, R4-2 and R4-3 are fixed (R-4b). Both sets are empty and
#: asserted empty: a parser that starts detecting on a bare bank name, or on
#: the filename echo, fails the pins below rather than being rediscovered by a
#: wrong parse. See R4_CONFORMANCE_FINDINGS.md.
COUNTERPARTY_VULNERABLE: set[str] = set()
FILENAME_DEPENDENT_PARSERS: set[str] = set()

#: `td_canada` identifies itself by a table-layout probe rather than a name, so
#: the "two required markers" invariant below does not apply to it.
SINGLE_MARKER_BY_DESIGN = {"td_canada"}

#: Registrations with no document in the pinned corpus. Their only coverage is
#: this module, which is why it enumerates the registry.
CORPUS_UNREPRESENTED = {"demo_national"}

#: The six parsers that had no direct test before R-4 (WAVE2_BRIEF R-4,
#: pulled forward by Ocean's ruling 6). Named so the gap cannot silently
#: reopen if someone deletes a fixture.
PREVIOUSLY_UNTESTED = {
    "wells_fargo",
    "scotiabank",
    "columbia_bank",
    "navigant",
    "relay",
    "first_farmers",
}


# ===========================================================================
# Completeness — the test that fails on an uncovered registration
# ===========================================================================

def test_every_registration_has_a_conformance_fixture():
    """Enumerates the registry, not a hand-maintained list."""
    missing = set(IDS) - set(FIXTURES)
    assert not missing, (
        f"registrations with no conformance fixture: {sorted(missing)}. "
        "Add one to tests/data/parser_conformance_fixtures.py."
    )


def test_no_fixture_names_a_registration_that_does_not_exist():
    unknown = set(FIXTURES) - set(IDS)
    assert not unknown, f"fixtures for unknown registrations: {sorted(unknown)}"


def test_the_registry_holds_the_documented_number_of_registrations():
    assert len(REGISTRATIONS) == 76, (
        "43 registry entry points, the three promoted sub-dispatches, the "
        "three BMO layouts, the Square Checking layout, the Chase savings "
        "product, the TD Canada Trust French layout, the English CIBC "
        "layout, plus the batch-3 train: Huntington, Burke & Herbert, "
        "Shopify Balance, CitiBusiness, Zions, Mercury, Brex, Found's "
        "closed statement and month-to-date view, Woodforest, Wealthsimple "
        "Symitar, the Fifth Third commercial print stream, Fiserv Premier, "
        "the issuer-agnostic core-processor template, the French "
        "`Relevé de compte` template that names no institution, the "
        "second core processor's sectioned template, the batch-4 "
        "partitioned-summary core-processor template, the batch-5 "
        "third core-processor template, the batch-6 counted-partition "
        "grammar of that third processor, and the batch-6 scanned Texas First "
        "four-way partition, and the batch-7 scanned Canadian direct-bank "
        "running-balance ledger, and the batch-8 community-bank core whose "
        "summary is a signed category partition; "
        "update this count and the docs together"
    )


def test_the_six_previously_untested_parsers_are_now_covered():
    """Ocean's ruling 6, made verifiable."""
    assert PREVIOUSLY_UNTESTED <= set(FIXTURES)
    assert PREVIOUSLY_UNTESTED <= set(IDS)


def test_corpus_unrepresented_parsers_are_covered_here_or_nowhere():
    """`demo_national` claims no corpus document, so these fixtures are its
    only coverage. Stated as an assertion so the list stays honest."""
    assert CORPUS_UNREPRESENTED <= set(FIXTURES)


# ===========================================================================
# 1. Detection-positive
# ===========================================================================

@pytest.mark.parametrize("registration", REGISTRATIONS, ids=IDS)
def test_detection_positive(registration):
    detection = registration.detect(FIXTURES[registration.id])
    assert detection.claims, (
        f"{registration.id} does not recognise its own bank's statement header: {detection}"
    )


@pytest.mark.parametrize(
    "parser_id,document",
    [(pid, doc) for pid, docs in ALTERNATE_FIXTURES.items() for doc in docs],
    ids=[f"{pid}-alt{i}" for pid, docs in ALTERNATE_FIXTURES.items() for i in range(len(docs))],
)
def test_detection_positive_for_each_branch_of_a_disjunctive_marker(parser_id, document):
    """A parser whose evidence is `A or B` must recognise both branches."""
    detection = pr.by_id(parser_id).detect(document)
    assert detection.claims, f"{parser_id} misses an alternate branch of its own marker: {detection}"


# ===========================================================================
# 2. Detection-negative — the full cross product
# ===========================================================================

@pytest.mark.parametrize("registration", REGISTRATIONS, ids=IDS)
def test_detection_negative_against_every_other_banks_fixture(registration):
    """Parser X must not claim bank Y's statement, for every Y."""
    wrongly_claimed = [
        other_id
        for other_id, document in FIXTURES.items()
        if other_id != registration.id and registration.detect(document).claims
    ]
    assert not wrongly_claimed, (
        f"{registration.id} claims statements belonging to: {wrongly_claimed}"
    )


@pytest.mark.parametrize("registration", REGISTRATIONS, ids=IDS)
def test_detection_negative_against_non_statements(registration):
    for document in (
        "",
        "   \n\n  ",
        "This is a lease agreement between the parties named below.",
        "Invoice 12 Total due on receipt. Thank you for your business.",
        "<html><body><p>404 Not Found</p></body></html>",
    ):
        assert not registration.detect(document).claims, (
            f"{registration.id} claims a document that is not a bank statement: {document!r}"
        )


def _mention_of(parser_id: str) -> str:
    """Another bank's statement whose ledger merely names `parser_id`'s bank."""
    name = FIXTURES[parser_id].splitlines()[0].strip()
    return f"{NEUTRAL_HOST}01/15 ACH DEBIT PAYMENT TO {name} 250.00\n"


@pytest.mark.parametrize("registration", REGISTRATIONS, ids=IDS)
def test_a_bank_name_in_a_transaction_line_is_not_a_claim(registration):
    """The generalised form of the R-3.4 finding.

    Every registration's own fixture text, demoted into a transaction
    description inside another bank's statement, must not produce a claim.
    """
    detection = registration.detect(_mention_of(registration.id))
    assert not detection.claims, (
        f"{registration.id} claims a statement that merely names it: {detection}"
    )


def test_the_neutral_host_document_belongs_to_no_registration():
    """Otherwise the mention tests would be measuring the host, not the mention."""
    claimers = [reg.id for reg in REGISTRATIONS if reg.detect(NEUTRAL_HOST).claims]
    assert not claimers, f"the neutral host is claimed by {claimers}"


def test_the_set_of_counterparty_vulnerable_parsers_is_exactly_the_recorded_finding():
    """Pins finding R4-3 both ways: it cannot grow unnoticed, and this test
    fails once a parser is fixed until its entry is removed."""
    vulnerable = {
        registration.id
        for registration in REGISTRATIONS
        if registration.detect(_mention_of(registration.id)).claims
    }
    assert vulnerable == COUNTERPARTY_VULNERABLE, (
        "counterparty-vulnerable parsers changed; update "
        "docs/moneythumb-replacement/R4_CONFORMANCE_FINDINGS.md with the diff"
    )


def test_no_registration_identifies_a_bank_by_one_marker_alone():
    """The structural lesson of R4-3, kept as an invariant.

    Every parser that names a bank needs a second piece of evidence, because a
    bank's name appears in other banks' statements as a counterparty. The one
    exception probes for a table layout rather than a name.
    """
    thin = {
        registration.id: [m.id for m in registration.markers if m.kind == "required"]
        for registration in REGISTRATIONS
        if len([m for m in registration.markers if m.kind == "required"]) < 2
    }
    assert set(thin) <= SINGLE_MARKER_BY_DESIGN, (
        f"registrations resting on a single required marker: {thin}"
    )


# ===========================================================================
# 3. Self-invalidation
# ===========================================================================

@pytest.mark.parametrize("registration", REGISTRATIONS, ids=IDS)
def test_self_invalidation_a_header_without_a_ledger_is_not_parsed(registration):
    """Detection may claim; `parse` must still decline.

    A statement header with no transactions, balances or period is not a
    parseable statement. A parser that returns a `Statement` here would be
    fabricating one, and the reconciliation gate would then be judging an
    invention.
    """
    statement = registration.parse(FIXTURES[registration.id])
    assert statement is None, (
        f"{registration.id} produced a Statement from a header with no ledger: {statement}"
    )


@pytest.mark.parametrize("registration", REGISTRATIONS, ids=IDS)
def test_parse_declines_a_document_it_does_not_claim(registration):
    """`parse` re-checks detection; it never trusts the caller."""
    assert registration.parse("a lease agreement, not a bank statement") is None


def test_a_header_only_document_resolves_to_unclaimed_with_the_attempt_recorded():
    """End to end: the right parser claims, tries, declines, and the attempt is
    visible — the fallthrough the or-chain used to hide."""
    for parser_id, document in FIXTURES.items():
        dispatch = pr.resolve(document)
        assert dispatch.outcome == "unclaimed", f"{parser_id}: {dispatch.outcome}"
        assert dispatch.attempted == (parser_id,), f"{parser_id}: {dispatch.attempted}"


# ===========================================================================
# 4. Filename invariance
# ===========================================================================

def _with_source_comment(document: str, filename: str) -> str:
    return f"<!-- source: {filename} | pages: 1 | model: native-pdf-text | empty: 0 -->\n\n{document}"


@pytest.mark.parametrize("registration", REGISTRATIONS, ids=IDS)
def test_detection_is_unchanged_by_the_presence_of_a_neutral_source_comment(registration):
    """The comment itself must be inert when it names nothing relevant."""
    document = FIXTURES[registration.id]
    assert registration.detect(document) == registration.detect(
        _with_source_comment(document, "statement.pdf")
    )


def test_first_farmers_does_not_detect_on_the_filename():
    """Regression test for finding R4-1, fixed in R-4b.

    The bank name is absent from this body and only the file is named after the
    bank. Before the fix `first_farmers` claimed it — and that was how it
    recognised its own corpus document.
    """
    body = "\n".join(
        [
            "BUSINESS BASIC CHECKING ACCOUNT",
            "BALANCE LAST STATEMENT",
            "TOTAL DAYS IN STATEMENT PERIOD",
        ]
    )
    document = _with_source_comment(body, "First Farmers 2026 01-document.pdf")
    assert not pr.by_id("first_farmers").detect(document).claims


def test_relay_scores_nothing_from_the_filename():
    """Regression test for finding R4-2, fixed in R-4b.

    No claim decision ever changed here - relay needs four markers and only one
    fired - but the near-miss score was inflated by metadata, and that score is
    what DSC-2 ranks unknown-layout clusters by.
    """
    document = _with_source_comment("Some other bank statement", "Account Statement 1.pdf")
    assert pr.by_id("relay").detect(document).score == 0.0


# ===========================================================================
# Registry-wide invariants
# ===========================================================================

@pytest.mark.parametrize("registration", REGISTRATIONS, ids=IDS)
def test_detect_does_not_mutate_its_input(registration):
    document = FIXTURES[registration.id]
    before = document
    registration.detect(document)
    assert document == before


@pytest.mark.parametrize("registration", REGISTRATIONS, ids=IDS)
def test_detect_never_raises(registration):
    """`detect` is total: a full registry sweep runs on every discovery
    document, and one exception would abort the run."""
    for document in ("", "\x00\x01", "é" * 100, "<table><tr><td>", "%PDF-1.4 garbage"):
        registration.detect(document)
