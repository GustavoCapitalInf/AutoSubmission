"""§CURRSRC — every published currency says where it came from.

`Statement.currency_source` is CURRENCY_DOCTRINE §B's evidence hierarchy moved
out of prose and each reader's comments and into the payload. It is additive
and provenance-only: no currency VALUE moves anywhere, no FX happens, and
nothing downstream computes with it (Gustavo, 2026-08-21).

Two kinds of proof live here, and the second is the one that matters.

**Structural** (`TestTheVocabularyIsClosed`, `TestEveryReaderDeclaresIt`) — the
set is closed, and a reader may not publish a currency without saying where it
came from. These are AST scans over the whole `analysis` package rather than a
list of parsers someone has to remember to extend: a NEW registration that sets
`currency` and forgets the provenance fails here, which is the only version of
this rule that survives the next parser cell.

**Earned** — the rule that gives the vocabulary its meaning is that *a reader
may not set a source it did not earn*, so every class below is exercised twice:
once on a printing that carries its evidence (the class is published) and once
on a printing that lacks it (the class is REFUSED and something weaker is
published, or the document is not claimed at all). A class that only ever
appears in the first half of that pair would be a label, not a measurement.

Every fixture is synthetic — the existing per-layout suites' own headers, reused
so this file adds no new statement text to the tree.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.schema import CURRENCY_SOURCES, Statement

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"

#: The same exclusion list `tests/test_corpus_gate_outcomes.py` uses for its own
#: repo-wide sweep, and for the same reason: a developer checkout carries whole
#: sibling checkouts under `.claude/worktrees/`, so a scan rooted at the repo
#: would otherwise read another cell's copy of this very file and report it as
#: an unexpected mention of the field.
NON_PRODUCTION_DIRS = ("tests", "docs", ".claude", ".git", "build")


# ===========================================================================
# 1. The vocabulary
# ===========================================================================


class TestTheVocabularyIsClosed:
    def test_the_field_defaults_to_the_truth_about_a_reader_that_never_set_it(self):
        """`schema_default` is the default so that the ~45 registrations which
        never touch `currency` publish an honest account of their `"USD"`
        rather than one indistinguishable from a read."""
        field = Statement.model_fields["currency_source"]
        assert field.default == "schema_default"
        assert Statement().currency_source == "schema_default"
        assert Statement().currency == "USD"

    def test_the_annotation_is_the_closed_set_and_not_free_text(self):
        """An enum, not a string field: the annotation and the tuple the tests
        and the corpus gate read are the same six members, in one order."""
        annotation = Statement.model_fields["currency_source"].annotation
        assert set(getattr(annotation, "__args__", ())) == set(CURRENCY_SOURCES)
        assert CURRENCY_SOURCES == (
            "printed",
            "product",
            "jurisdiction_default",
            "institution_default",
            "model_extracted",
            "schema_default",
        )

    def test_a_value_outside_the_vocabulary_is_rejected_on_construction(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Statement(currency="CAD", currency_source="because_canada")


# ===========================================================================
# 2. Every reader that publishes a currency declares its provenance
# ===========================================================================


def _statement_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Statement"
    ]


def _attribute_targets(node: ast.AST, name: str) -> list[ast.Attribute]:
    """Every `<expr>.<name>` written to by an assignment inside `node`.

    Tuple targets count — `stmt.currency, stmt.currency_source = ruling` is one
    assignment writing both, which is exactly the shape `analysis/rbc.py` uses
    so the code and the class it claims cannot come from two evaluations.
    """
    found: list[ast.Attribute] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Assign):
            continue
        for target in child.targets:
            elements = target.elts if isinstance(target, ast.Tuple) else [target]
            found += [
                element for element in elements
                if isinstance(element, ast.Attribute) and element.attr == name
            ]
    return found


def _modules() -> list[tuple[str, ast.Module]]:
    return [
        (str(path.relative_to(ANALYSIS.parent)).replace("\\", "/"),
         ast.parse(path.read_text(encoding="utf-8")))
        for path in sorted(ANALYSIS.rglob("*.py"))
    ]


def _functions(tree: ast.Module):
    return [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


class TestEveryReaderDeclaresIt:
    def test_a_statement_built_with_a_currency_is_built_with_its_source(self):
        """The constructor half. `Statement(bank=..., currency="USD")` asserts a
        denomination; the call that asserts it names the evidence in the same
        call, where the two cannot drift apart."""
        missing = []
        for name, tree in _modules():
            for call in _statement_calls(tree):
                keywords = {kw.arg for kw in call.keywords}
                if "currency" in keywords and "currency_source" not in keywords:
                    missing.append(f"{name}:{call.lineno}")
        assert not missing, (
            "these Statement(...) constructions publish a currency with no "
            f"provenance: {missing}"
        )

    def test_a_reader_that_assigns_a_currency_assigns_its_source(self):
        """The attribute half, per function body — the unit a parser writes a
        statement in. `stmt.currency = "CAD"` with no `stmt.currency_source`
        beside it is a denomination asserted from nowhere."""
        missing = []
        for name, tree in _modules():
            for function in _functions(tree):
                if not _attribute_targets(function, "currency"):
                    continue
                if not _attribute_targets(function, "currency_source"):
                    missing.append(f"{name}:{function.lineno} {function.name}")
        assert not missing, (
            "these readers assign a currency and never say where it came from: "
            f"{missing}"
        )

    def test_every_source_the_analysis_layer_writes_is_in_the_vocabulary(self):
        """A free-text provenance is worse than none: it would pass every gate
        in this file while meaning nothing. Constants and the two-armed
        conditionals the branching readers use are both read."""
        written: set[str] = set()
        unreadable: list[str] = []
        for name, tree in _modules():
            values: list[tuple[int, ast.AST]] = []
            for call in _statement_calls(tree):
                values += [
                    (call.lineno, kw.value) for kw in call.keywords
                    if kw.arg == "currency_source"
                ]
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Attribute) and t.attr == "currency_source"
                    for t in node.targets
                ):
                    values.append((node.lineno, node.value))
            for lineno, value in values:
                arms = (
                    [value.body, value.orelse] if isinstance(value, ast.IfExp) else [value]
                )
                for arm in arms:
                    if isinstance(arm, ast.Constant) and isinstance(arm.value, str):
                        written.add(arm.value)
                    else:
                        unreadable.append(f"{name}:{lineno}")
        assert not (written - set(CURRENCY_SOURCES)), sorted(written - set(CURRENCY_SOURCES))
        # `analysis/rbc.py` unpacks its ruling into both fields at once, which
        # is not a literal and is proven behaviourally in section 3 instead.
        assert unreadable == [], unreadable
        # ...and the scan is not vacuous: it really did find the literals.
        assert {"printed", "product", "institution_default", "schema_default"} <= written


# ===========================================================================
# 3. Earned, class by class — the evidence, and the refusal without it
# ===========================================================================


def _rbc():
    from tests.test_rbc_variants import _mailing, canadian, plain_statement

    return _mailing, canadian, plain_statement


class TestPrinted:
    """`printed` — a currency word or code the document states outright."""

    def test_bmo_reads_the_currency_its_header_block_states(self):
        from analysis.bmo import parse_bmo_statement
        from tests.test_bmo_layouts import BMO_SUMMARY_TOTALS_LAYOUT

        stmt = parse_bmo_statement(BMO_SUMMARY_TOTALS_LAYOUT)
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "printed")

    def test_bmo_refuses_printed_when_the_header_states_nothing(self):
        """The same document with its `Currency:` line removed publishes the
        SAME code — the institution fallback — and must not claim to have read
        it. This is the mutation the class exists to make visible."""
        from analysis.bmo import parse_bmo_statement
        from tests.test_bmo_layouts import BMO_SUMMARY_TOTALS_LAYOUT

        silent = BMO_SUMMARY_TOTALS_LAYOUT.replace("Currency: CAD\n", "")
        stmt = parse_bmo_statement(silent)
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "institution_default")

    def test_cibc_reads_the_code_printed_on_its_closing_balance_row(self):
        from analysis.cibc import parse_cibc_statement
        from tests.test_cibc_layouts import statement

        body = "Date Description Withdrawals ($) Deposits ($) Balance ($)\nNov 2 Sample row 100.00 900.00\n"
        stated = statement(
            body, opening="1,000.00", closing="900.00",
            credits="0.00", debits="100.00", code="USD",
        )
        stmt = parse_cibc_statement(stated)
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("USD", "printed")

    def test_cibc_refuses_printed_when_no_code_is_on_that_row(self):
        from analysis.cibc import parse_cibc_statement
        from tests.test_cibc_layouts import statement

        body = "Date Description Withdrawals ($) Deposits ($) Balance ($)\nNov 2 Sample row 100.00 900.00\n"
        silent = statement(
            body, opening="1,000.00", closing="900.00",
            credits="0.00", debits="100.00",
        )
        stmt = parse_cibc_statement(silent)
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "institution_default")

    def test_wealthsimple_reads_the_code_its_required_grid_header_prints(self):
        """The read is the REGISTRATION's: `AMOUNT (CAD) BALANCE (CAD)` is a
        required detection marker, so a document that reaches the assignment
        has printed the code over both money columns."""
        from analysis.wealthsimple import parse_wealthsimple_statement
        from tests.test_wealthsimple import ONE_ROW

        stmt = parse_wealthsimple_statement(ONE_ROW)
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "printed")

    def test_wealthsimple_refuses_the_whole_document_when_the_code_is_absent(self):
        """The strongest refusal shape there is: without the printed code the
        registration does not claim the document at all, so no currency and no
        provenance is published for it by this reader."""
        from analysis.wealthsimple import detect, parse_wealthsimple_statement
        from tests.test_wealthsimple import ONE_ROW

        other = ONE_ROW.replace("AMOUNT (CAD) BALANCE (CAD)", "AMOUNT (EUR) BALANCE (EUR)")
        assert not detect(other).claims
        assert parse_wealthsimple_statement(other) is None

    def test_rbc_reads_its_us_funds_denomination_line(self):
        from analysis.rbc import parse_rbc_statement

        _mailing, canadian, plain_statement = _rbc()
        document = canadian(plain_statement()).replace(
            "Business Account Statement", "Business Account Statement\nU.S. Funds"
        )
        stmt = parse_rbc_statement(document)
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("USD", "printed")


class TestProduct:
    """`product` — a printed product designation that fixes the denomination."""

    def test_rbc_reads_the_product_name_in_its_mailing_header(self):
        from analysis.rbc import parse_rbc_statement

        _mailing, canadian, plain_statement = _rbc()
        stmt = parse_rbc_statement(_mailing(plain_statement(), "CAD CHEQUING ACCOUNT"))
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "product")

    def test_rbc_refuses_product_for_a_spelling_no_document_prints(self):
        """The map is a literal table of two attested spellings. An invented
        `CAD BUSINESS ACCOUNT` is not evidence, and the page then states
        nothing at all — so the answer falls to a lower rung, never to
        `product`."""
        from analysis.rbc import parse_rbc_statement

        _mailing, canadian, plain_statement = _rbc()
        stmt = parse_rbc_statement(_mailing(plain_statement(), "CAD BUSINESS ACCOUNT"))
        assert stmt is not None
        assert stmt.currency_source == "schema_default"

    def test_the_stated_line_outranks_a_product_name_that_agrees_with_it(self):
        """Both sites fire and they agree, which is not a contradiction. The
        stronger evidence names the class."""
        from analysis.rbc import _printed_currency_evidence

        _mailing, canadian, plain_statement = _rbc()
        both = _mailing(
            plain_statement().replace(
                "Business Account Statement", "Business Account Statement\nU.S. Funds"
            ),
            "US BUSINESS ACCOUNT",
        )
        assert _printed_currency_evidence(both) == {"USD": "printed"}

    def test_td_canada_reads_the_suffix_on_its_product_line(self):
        from analysis.td_can import parse_native_td_canada_statement
        from tests.test_td_can_native_variants import TestF7PrintedDenomination, _statement

        document = _statement(TestF7PrintedDenomination.LEDGER)
        stmt = parse_native_td_canada_statement(document)
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "product")

    def test_td_canada_refuses_product_where_the_product_has_no_suffix(self):
        """One archive document of this layout prints `BUSINESS / INVESTOR /
        ACCOUNT` with no denomination. Its currency is not stated, the reader
        falls back to the layout's institution default, and it says so."""
        from analysis.td_can import parse_native_td_canada_statement
        from tests.test_td_can_native_variants import TestF7PrintedDenomination, _statement

        silent = _statement(TestF7PrintedDenomination.LEDGER).replace("ACCOUNT - CAD", "ACCOUNT")
        stmt = parse_native_td_canada_statement(silent)
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "institution_default")

    def test_desjardins_reads_the_code_in_front_of_its_product_name(self):
        from analysis.desjardins import parse_desjardins_statement
        from tests.test_analysis import _DESJ_HEAD

        stmt = parse_desjardins_statement(_DESJ_HEAD.format(code="USD "))
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("USD", "product")

    def test_desjardins_refuses_product_where_the_line_prints_no_code(self):
        """And the refusal lands on `schema_default`, NOT
        `institution_default`: this caisse is Canadian, so "USD because
        Desjardins" is a claim nobody can make. The published value is the
        field's own default standing where no evidence was read — §CUR6's named
        residual, now visible in the payload."""
        from analysis.desjardins import parse_desjardins_statement
        from tests.test_analysis import _DESJ_HEAD

        stmt = parse_desjardins_statement(_DESJ_HEAD.format(code=""))
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("USD", "schema_default")

    def test_the_unknown_issuer_quebec_layout_reads_its_product_designation(self):
        """`product` and not `institution_default`, because this registration
        identifies no institution at all — it publishes `bank=None`. The
        `COMPTE COURANT CANADIEN` product line is a REQUIRED marker and is the
        only currency evidence on the page."""
        from tests.test_releve_facturation import LEDGER, document, parse

        stmt = parse(document(LEDGER))
        assert stmt is not None
        assert stmt.bank is None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "product")

    def test_the_unknown_issuer_layout_refuses_the_document_with_no_product_line(self):
        from tests.test_releve_facturation import LEDGER, document, parse

        assert parse(document(LEDGER, product="")) is None


class TestJurisdictionDefault:
    """`jurisdiction_default` — the ratified RBC Canada rule, and only it."""

    def test_a_proven_rbc_canada_account_that_states_nothing_takes_the_default(self):
        from analysis.rbc import parse_rbc_statement

        _mailing, canadian, plain_statement = _rbc()
        stmt = parse_rbc_statement(canadian(plain_statement()))
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "jurisdiction_default")

    @pytest.mark.parametrize("evidence", ["issuer", "service", "account", "branch"])
    def test_removing_any_one_of_the_four_proofs_refuses_the_class(self, evidence):
        """The conjunction is the rule. Ablate one proof and the reader does not
        fall back to a weaker CAD — it publishes nothing, so the schema default
        stands and says so."""
        from analysis.rbc import parse_rbc_statement

        _mailing, canadian, plain_statement = _rbc()
        stmt = parse_rbc_statement(canadian(plain_statement(), without=evidence))
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("USD", "schema_default")

    def test_contrary_currency_evidence_refuses_the_default_before_it_speaks(self):
        """Doctrine §B: a default may never overrule what the page says, and it
        may not resolve a contradiction either. Both stop short of publishing a
        jurisdiction default."""
        from analysis.rbc import parse_rbc_statement

        _mailing, canadian, plain_statement = _rbc()
        contradicting = _mailing(
            canadian(plain_statement()).replace(
                "Business Account Statement", "Business Account Statement\nU.S. Funds"
            ),
            "CAD CHEQUING ACCOUNT",
        )
        stmt = parse_rbc_statement(contradicting)
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("USD", "schema_default")

    def test_no_other_reader_in_the_layer_claims_a_jurisdiction_default(self):
        """Doctrine §B's final paragraph: the same shape generalizes to TD, BMO
        and CIBC only after each proves its own jurisdiction evidence base. Until
        then exactly one module may write this class, and this test is what
        makes a second one a deliberate act."""
        writers = set()
        for name, tree in _modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and node.value == "jurisdiction_default":
                    writers.add(name)
        assert writers == {"analysis/rbc.py", "analysis/schema.py"}, sorted(writers)


#: One well-formed Scotiabank ledger, the shape `tests/test_scotia_layouts.py`
#: drives every one of its own cases with.
ROWS = (
    "01/30/2026 BALANCE FORWARD 1,000.00 "
    "02/02/2026 POINT OF SALE PURCHASE FPOS SAMPLE STORE 60.00 940.00 "
    "02/03/2026 MISC PAYMENT SAMPLE PAYER 50.00 990.00 "
    "02/04/2026 SERVICE CHARGE 40.00 950.00"
)


class TestInstitutionDefault:
    """`institution_default` — asserted from the issuer, read from nothing."""

    def test_scotiabank_asserts_cad_from_the_institution_it_detected(self):
        from analysis.scotia import parse_scotiabank_statement
        from tests.test_scotia_layouts import SUMMARY_2D_1C, _statement

        stmt = parse_scotiabank_statement(_statement(SUMMARY_2D_1C, ROWS))
        assert stmt is not None
        assert (stmt.currency, stmt.currency_source) == ("CAD", "institution_default")

    def test_the_french_rbc_reader_asserts_rather_than_reads(self):
        """Named honestly against the handoff's own filing of `rbc.py:829`: this
        site is not the four-proof conjunction, it is the French reader stating
        CAD because it recognised Banque Royale du Canada. It is one of the
        three institution-hardcoded CAD the batch-6 census named as owing an
        evidence packet, and the payload now says so."""
        from analysis.rbc import parse_rbc_statement
        from tests.test_rbc_variants import FR

        stmt = parse_rbc_statement(FR.format(body="5 mars Article un 500,00 1 500,00\n"))
        assert stmt is not None
        assert stmt.bank == "Banque Royale du Canada"
        assert (stmt.currency, stmt.currency_source) == ("CAD", "institution_default")

    def test_a_document_the_institution_does_not_claim_gets_no_source_from_it(self):
        """The refusal available to an assertion-from-identity: strip the
        issuer's own furniture and the registration does not claim the document,
        so it publishes neither the currency nor the class."""
        from analysis.scotia import parse_scotiabank_statement
        from tests.test_scotia_layouts import FOOTER, SUMMARY_2D_1C, _statement

        document = _statement(SUMMARY_2D_1C, ROWS).replace(FOOTER, "")
        assert parse_scotiabank_statement(document) is None


class TestModelExtracted:
    """`model_extracted` — and a model may not certify its own provenance."""

    def test_the_llm_branchs_currency_is_labelled_as_the_models(self, monkeypatch):
        import analysis.extract as extract

        monkeypatch.setattr(
            extract, "_get_client", lambda _settings: _StubClient(
                Statement(currency="CAD")
            )
        )
        stmt = extract.extract_statement("--- Page 1 ---\n", settings=_StubSettings())
        assert (stmt.currency, stmt.currency_source) == ("CAD", "model_extracted")

    def test_a_source_the_model_filled_in_itself_is_discarded(self, monkeypatch):
        """`Statement` is this call's `response_schema`, so `currency_source` is
        a field the model can fill. A returned `printed` is a language model
        asserting that it read evidence, which is precisely the claim nothing
        here can verify."""
        import analysis.extract as extract

        monkeypatch.setattr(
            extract, "_get_client", lambda _settings: _StubClient(
                Statement(currency="CAD", currency_source="printed")
            )
        )
        stmt = extract.extract_statement("--- Page 1 ---\n", settings=_StubSettings())
        assert stmt.currency_source == "model_extracted"


class _StubSettings:
    model = "stub-model"
    escalation_model = "stub-model"


class _StubModels:
    def __init__(self, parsed):
        self._parsed = parsed

    def generate_content(self, **_kwargs):
        return type("_Resp", (), {"parsed": self._parsed})()


class _StubClient:
    """Offline by construction — no vendor call is made anywhere in this file."""

    def __init__(self, parsed):
        self.models = _StubModels(parsed)


class TestSchemaDefault:
    """`schema_default` — nothing was read and the field's own default stands."""

    def test_a_reader_that_never_asks_publishes_the_truth_about_its_usd(self):
        """ATB Financial is a Canadian provincial bank whose five pinned
        documents publish `USD` today because no reader ever asked. That is the
        exact shape the RBC family had before its ceremony, and the payload now
        distinguishes it from a U.S. account's read."""
        from analysis.atb import parse_atb_statement
        from tests.test_analysis import ATB_NATIVE_TEXT

        stmt = parse_atb_statement(ATB_NATIVE_TEXT)
        assert stmt is not None
        assert stmt.bank == "ATB Financial"
        assert (stmt.currency, stmt.currency_source) == ("USD", "schema_default")


# ===========================================================================
# 4. Additive only — the field carries, and nothing computes with it
# ===========================================================================


def test_the_published_payload_carries_the_field_beside_the_currency():
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from tests.test_rbc_variants import _mailing, canadian, plain_statement

    report = analyze_markdown(canadian(plain_statement()), parse_mode="deterministic")
    payload = report_to_dict(report)
    assert payload["statement"]["currency"] == "CAD"
    assert payload["statement"]["currency_source"] == "jurisdiction_default"


#: Every non-test module in the tree allowed to mention `currency_source` at
#: all, and the whole reason each may: the readers that EARN a class, the schema
#: that defines the vocabulary, the model boundary that refuses to let the LLM
#: certify itself, and the gate that pins the surface. Nothing else — no metric,
#: no ADB, no reconciliation, no package total, no export, no UI.
PROVENANCE_MODULES = {
    "analysis/bmo.py",
    "analysis/bmo_ca_business.py",
    "analysis/bmo_us_activity.py",
    "analysis/brex.py",
    "analysis/chase.py",
    "analysis/cibc.py",
    "analysis/desjardins.py",
    "analysis/extract.py",
    "analysis/farmers_merchants.py",
    "analysis/found_lead.py",
    "analysis/mercury.py",
    "analysis/rbc.py",
    "analysis/releve_facturation.py",
    "analysis/scanned_small_bank.py",
    "analysis/schema.py",
    "analysis/scotia.py",
    "analysis/square_checking.py",
    "analysis/symitar.py",
    "analysis/td_can.py",
    "analysis/td_canada_french.py",
    "analysis/wealthsimple.py",
    "analysis/welch_state_bank.py",
    "analysis/woodforest.py",
    "corpus_gate.py",
}


def test_only_the_readers_the_schema_and_the_gate_know_the_provenance_exists():
    """Provenance-ONLY, enforced structurally and in both directions.

    The moment a metric, an ADB, a package total or a verdict consults this
    label it has become an input to money, and doctrine §A/§F is at risk from a
    field that was supposed to be additive. So the set of modules that may even
    name it is enumerated: a new mention outside it fails here, and a module
    that stops setting a class it used to set fails here too.
    """
    found = set()
    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT)
        if any(part in NON_PRODUCTION_DIRS for part in relative.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):  # pragma: no cover
            continue
        if "currency_source" in text:
            found.add(relative.as_posix())
    assert found == PROVENANCE_MODULES, {
        "unexpected": sorted(found - PROVENANCE_MODULES),
        "silent": sorted(PROVENANCE_MODULES - found),
    }
