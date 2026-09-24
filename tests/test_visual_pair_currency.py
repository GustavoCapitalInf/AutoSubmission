"""Currency reuse from fabricated visual text, without PDFs or model calls."""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from analysis.config import Settings
from analysis.pipeline import analyze_document
from analysis.schema import Statement, Transaction
from vlm import currency


DEMO_TEXT = """SAMPLE BUSINESS BANK STATEMENT
Bank: Demo National Bank
Statement Period: February 1, 2031 - February 3, 2031
Account Number: 00000000
Beginning Balance $100.00
Deposits / Credits 1 $50.00
Checks / Debits 1 $20.00
Ending Balance $130.00
Checking Account Activity
Date Description Amount Balance
02/01/2031 SYNTHETIC DEPOSIT $50.00 $150.00
02/02/2031 SYNTHETIC PURCHASE $20.00 $130.00
End of statement
"""


def _statement(source="institution_default"):
    return Statement(bank="FABRICATED ISSUER", account_name="FABRICATED PRODUCT", account_number="0000",
                     period_start="2031-02-01", period_end="2031-02-03", beginning_balance=100,
                     ending_balance=150, currency="CAD", currency_source=source,
                     transactions=[Transaction(date="2031-02-02", description="SYNTHETIC  DEPOSIT / 001",
                                               amount=50, direction="credit", running_balance=150)])


def _reviewed(statement):
    source = statement.model_dump(exclude_computed_fields=True)
    source["currency"] = None
    source.pop("currency_source")
    return source


def _bridge(monkeypatch, statement, *, outcome="claimed", exceptions=(), accounts=1, omissions=()):
    def analyze(markdown, **kwargs):
        assert markdown == "fabricated visual text"
        assert kwargs["parse_mode"] == "deterministic"
        assert kwargs["settings"].api_key == ""
        assert kwargs["settings"].reconstruction_mode == "off"
        kwargs["on_dispatch"](SimpleNamespace(parser_id="synthetic_reader", outcome=outcome, exceptions=exceptions))
        return SimpleNamespace(accounts=[SimpleNamespace(statement=statement)] * accounts, omissions=omissions)

    monkeypatch.setattr(currency, "analyze_document", analyze)


def test_faithful_bridge_reuses_the_exact_existing_institution_provenance(monkeypatch):
    source = "institution_default"
    parsed = _statement(source)
    reviewed = _reviewed(parsed)
    original = deepcopy(reviewed)
    _bridge(monkeypatch, parsed)
    resolved = currency.resolve_currency(reviewed, "fabricated visual text")
    assert resolved.resolved and resolved.currency == "CAD"
    assert resolved.currency_source == source
    assert resolved.bridge_currency_source == source
    assert resolved.parser_id == "synthetic_reader"
    assert reviewed == original


@pytest.mark.parametrize("source", ["printed", "product", "jurisdiction_default"])
def test_matching_ledger_cannot_certify_unreviewed_denomination_evidence(monkeypatch, source):
    parsed = _statement(source)
    reviewed = _reviewed(parsed)
    original = deepcopy(reviewed)
    _bridge(monkeypatch, parsed)
    resolved = currency.resolve_currency(reviewed, "fabricated visual text")
    assert not resolved.resolved and resolved.currency is None and resolved.currency_source is None
    assert resolved.reason == "bridge_needs_reviewed_denomination"
    assert resolved.bridge_currency_source == source
    assert resolved.parser_id == "synthetic_reader"
    assert reviewed == original


@pytest.mark.parametrize("unreviewed_code", ["CAD", "USD"])
def test_registered_parser_cannot_promote_a_denomination_seen_only_by_stage_a(unreviewed_code):
    from tests.test_bmo_layouts import BMO_SUMMARY_TOTALS_LAYOUT

    settings = Settings(api_key="", model="offline-test", escalation_model="offline-test", reconstruction_mode="off")
    baseline = analyze_document(BMO_SUMMARY_TOTALS_LAYOUT, parse_mode="deterministic", settings=settings,
                                sheets=[BMO_SUMMARY_TOTALS_LAYOUT]).accounts[0].statement
    text = BMO_SUMMARY_TOTALS_LAYOUT.replace("Currency: CAD", "Currency: " + unreviewed_code)
    resolved = currency.resolve_currency(_reviewed(baseline), text, sheets=[text])
    assert not resolved.resolved and resolved.currency is None
    assert resolved.reason == "bridge_needs_reviewed_denomination"
    assert resolved.bridge_currency_source == "printed"


def test_real_registered_parser_schema_default_does_not_supply_missing_currency():
    settings = Settings(api_key="", model="offline-test", escalation_model="offline-test", reconstruction_mode="off")
    parsed = analyze_document(DEMO_TEXT, parse_mode="deterministic", settings=settings,
                              sheets=[DEMO_TEXT]).accounts[0].statement
    assert parsed.currency_source == "schema_default"
    resolved = currency.resolve_currency(_reviewed(parsed), DEMO_TEXT, sheets=[DEMO_TEXT])
    assert not resolved.resolved and resolved.currency is None
    assert resolved.reason == "bridge_denomination_unproven"
    assert resolved.bridge_currency_source == "schema_default"


def test_existing_registered_institution_rule_is_reusable_from_visual_text():
    from tests.test_bmo_layouts import BMO_SUMMARY_TOTALS_LAYOUT

    text = BMO_SUMMARY_TOTALS_LAYOUT.replace("Currency: CAD\n", "")
    settings = Settings(api_key="", model="offline-test", escalation_model="offline-test", reconstruction_mode="off")
    parsed = analyze_document(text, parse_mode="deterministic", settings=settings,
                              sheets=[text]).accounts[0].statement
    assert parsed.currency_source == "institution_default"
    resolved = currency.resolve_currency(_reviewed(parsed), text, sheets=[text])
    assert resolved.resolved
    assert (resolved.currency, resolved.currency_source) == (parsed.currency, parsed.currency_source)


@pytest.mark.parametrize("field", ["bank", "account_name", "description", "amount", "period_end", "ending_balance"])
def test_bridge_cannot_borrow_currency_when_any_reviewed_source_differs(monkeypatch, field):
    parsed = _statement()
    reviewed = _reviewed(parsed)
    if field == "description":
        reviewed["transactions"][0][field] = "SYNTHETIC CORRECTED DESCRIPTION"
    elif field == "amount":
        reviewed["transactions"][0][field] = 51
    else:
        reviewed[field] = 151 if field == "ending_balance" else "2031-02-04" if field == "period_end" else "DIFFERENT"
    _bridge(monkeypatch, parsed)
    resolved = currency.resolve_currency(reviewed, "fabricated visual text")
    assert not resolved.resolved and resolved.reason == "bridge_sources_differ"


@pytest.mark.parametrize("changes,reason", [
    ({"outcome": "ambiguous"}, "bridge_claim_not_clean"),
    ({"exceptions": ("SyntheticFailure",)}, "bridge_claim_not_clean"),
    ({"accounts": 2}, "bridge_multiple_accounts"),
    ({"omissions": ("SyntheticOmission",)}, "bridge_multiple_accounts"),
])
def test_unclean_or_multiple_account_bridge_stays_unresolved(monkeypatch, changes, reason):
    parsed = _statement()
    _bridge(monkeypatch, parsed, **changes)
    resolved = currency.resolve_currency(_reviewed(parsed), "fabricated visual text")
    assert not resolved.resolved and resolved.reason == reason


def test_explicit_reviewed_denomination_overrides_defaults_without_self_certified_provenance(monkeypatch):
    source = _reviewed(_statement())
    source.update(currency="USD", currency_source="jurisdiction_default")
    monkeypatch.setattr(currency, "analyze_document", lambda *args, **kwargs: pytest.fail("bridge consulted"))
    resolved = currency.resolve_currency(source, "fabricated visual text")
    assert (resolved.currency, resolved.currency_source) == ("USD", "model_extracted")


def test_bank_name_or_dollar_symbol_alone_does_not_supply_a_currency():
    source = _reviewed(_statement())
    resolved = currency.resolve_currency(source, "FABRICATED ISSUER $100.00", sheets=["FABRICATED ISSUER $100.00"])
    assert not resolved.resolved and resolved.currency is None


def test_exception_message_cannot_escape_the_resolver(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError("SYNTHETIC PRIVATE DOCUMENT FRAGMENT")

    monkeypatch.setattr(currency, "analyze_document", fail)
    resolved = currency.resolve_currency(_reviewed(_statement()), "fabricated visual text")
    assert not resolved.resolved and resolved.reason == "bridge_failed"
    assert "PRIVATE DOCUMENT" not in repr(resolved)


def test_adapter_preserves_only_the_platforms_existing_parser_proof():
    from tests.test_bmo_layouts import ca_statement
    from tests.test_visual_pair_adapter import _doc
    from ocr.truncation import assess_pages
    from vlm import pair_adapter

    text = ca_statement()
    settings = Settings(api_key="", model="offline-test", escalation_model="offline-test", reconstruction_mode="off")
    parsed = analyze_document(text, parse_mode="deterministic", settings=settings,
                              sheets=[text]).accounts[0].statement
    reviewed = _reviewed(parsed)
    resolved = currency.resolve_currency(reviewed, text, sheets=[text])
    assert resolved.resolved and resolved.reason == "existing_parser_rule"
    reviewed.update(currency=resolved.currency, currency_source=resolved.currency_source)
    doc = _doc()
    doc.pages = [text]
    doc.page_integrity = assess_pages(doc.pages)
    doc.visual_pair.update(statement=reviewed, currency_resolution=asdict(resolved))
    result = pair_adapter.analyze_visual_pair(doc, settings=settings, review_policy="admit_gated")
    assert result.accounts[0].statement.currency_source == "institution_default"
    assert result.accounts[0].statement.currency == parsed.currency


@pytest.mark.parametrize("proof", [None, {}, {"status": "unresolved"},
    {"status": "resolved", "reason": "reviewed_denomination", "currency_source": "printed"},
])
def test_adapter_raw_provenance_without_existing_parser_proof_cannot_certify(proof):
    from tests.test_visual_pair_adapter import _source
    from vlm import pair_adapter

    raw = _source()
    raw["currency_source"] = "printed"
    assert pair_adapter._source_statement(raw, currency_resolution=proof).currency_source == "model_extracted"


@pytest.mark.parametrize("changes", [
    {"status": "unresolved"}, {"currency": "USD"}, {"parser_id": ""},
    {"parser_id": "synthetic_unregistered_reader"}, {"parser_id": []},
    {"currency_source": "schema_default"}, {"currency_source": "model_extracted"},
    {"currency_source": {}}, {"bridge_currency_source": "printed"},
])
def test_inconsistent_claimed_parser_proof_refuses_before_analysis(monkeypatch, changes):
    from tests.test_visual_pair_adapter import _doc
    from vlm import pair_adapter

    doc = _doc()
    doc.visual_pair["statement"]["currency_source"] = "institution_default"
    proof = asdict(currency.CurrencyResolution("resolved", "existing_parser_rule", "CAD",
                                                "institution_default", "bmo", "institution_default"))
    proof.update(changes)
    doc.visual_pair["currency_resolution"] = proof
    monkeypatch.setattr(pair_adapter, "analyze_document", lambda *args, **kwargs: pytest.fail("parser called"))
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="currency resolution is invalid"):
        pair_adapter.analyze_visual_pair(doc, review_policy="admit_gated")


def test_raw_provenance_conflicting_with_platform_proof_refuses():
    from tests.test_visual_pair_adapter import _source
    from vlm import pair_adapter

    raw = _source()
    raw["currency_source"] = "printed"
    proof = asdict(currency.CurrencyResolution("resolved", "existing_parser_rule", "CAD",
                                                "institution_default", "bmo", "institution_default"))
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="currency resolution is invalid"):
        pair_adapter._source_statement(raw, currency_resolution=proof)


@pytest.mark.parametrize("source", ["printed", "product", "jurisdiction_default"])
def test_adapter_refuses_even_consistent_unreviewed_denomination_proof(source):
    from tests.test_visual_pair_adapter import _source
    from vlm import pair_adapter

    raw = _source()
    raw["currency_source"] = source
    proof = asdict(currency.CurrencyResolution("resolved", "existing_parser_rule", raw["currency"],
                                                source, "bmo", source))
    with pytest.raises(pair_adapter.VisualPairAdmissionError, match="currency resolution is invalid"):
        pair_adapter._source_statement(raw, currency_resolution=proof)


def test_currency_manifest_invalidates_on_parser_code_and_registry_changes(tmp_path, monkeypatch):
    (tmp_path / "vlm").mkdir()
    source_dir = tmp_path / "analysis"
    source_dir.mkdir()
    source = source_dir / "synthetic.py"
    source.write_text("VALUE = 1\n")
    monkeypatch.setattr(currency, "__file__", str(tmp_path / "vlm" / "currency.py"))
    monkeypatch.setattr(currency, "registry_fingerprint", lambda: "synthetic-registry-a")
    before = currency.currency_resolution_manifest()
    assert before == currency.currency_resolution_manifest()
    assert before["resolver_version"] == currency.CURRENCY_RESOLVER_VERSION
    source.write_text("VALUE = 2\n")
    changed_source = currency.currency_resolution_manifest()
    assert before["analysis_source_sha256"] != changed_source["analysis_source_sha256"]
    monkeypatch.setattr(currency, "registry_fingerprint", lambda: "synthetic-registry-b")
    changed_registry = currency.currency_resolution_manifest()
    assert changed_source["registry_fingerprint"] != changed_registry["registry_fingerprint"]
    assert changed_source["analysis_source_sha256"] == changed_registry["analysis_source_sha256"]
