"""Fabricated inputs only. Gustavo's ruling of 2026-09-22: a statement that prints no currency is USD unless the
bank is Canadian (and the rulings of 2026-09-23: a Canadian bank name is enough; a US address alone vetoes CAD).

The rule lives in `analysis/currency_default.py` since the visual pair was removed (model-code removal, slice S4).
These tests moved here from `tests/test_visual_pair_owner_rulings.py` (its currency section), with the import
changed from `vlm.currency`; the one that needed a visual-pair helper keeps its `usd_default` assertions on the
names that helper returned, and the manifest test became the ruling-string pin below.
"""
import ast
import subprocess
import sys
from pathlib import Path

from analysis.currency_default import USD_DEFAULT_RULING, canadian_evidence, usd_default

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "analysis" / "currency_default.py"


def test_a_us_statement_without_printed_currency_defaults_to_usd_as_a_schema_default():
    result = usd_default("FABRICATED NATIONAL BANK", ["FABRICATED CO\n100 MAIN ST\nANYTOWN MN 55555"])
    assert result == {"ruling": USD_DEFAULT_RULING, "canadian_evidence": [],
                      "currency": "USD", "currency_source": "schema_default"}


def test_a_canadian_bank_keeps_its_jurisdiction_default_cad():
    # "USD should be made the default (unless its a canadian bank)": Canadian banks keep CAD, as the currency
    # doctrine does for RBC.
    for bank in ("TD Canada Trust", "Royal Bank of Canada", "CIBC", "Scotiabank", "Desjardins", "Banque Nationale",
                 "Banque Royale du Canada", "BANQUE DE MONTRÉAL"):
        result = usd_default(bank, [])
        assert result["currency"] == "CAD" and result["currency_source"] == "jurisdiction_default", bank
        assert result["canadian_evidence"] == ["canadian_institution_name"], bank


def test_a_name_other_countries_share_or_a_foreign_arm_decides_no_currency():
    # Names that also belong to US or offshore banks, and arms that name themselves, stay unknown (held).
    for bank in ("RBC", "BMO", "BMO Harris Bank N.A.", "CIBC Bank USA", "Scotiabank Caribbean", "Royal Bank",
                 "CIBC US", "Scotiabank Mexico", "Scotiabank Perú", "Scotiabank Chile", "Scotiabank de Costa Rica",
                 "RBC Royal Bank (Aruba) N.V.", "RBC Royal Bank (Suriname)", "Banque Nationale Agricole",
                 "Caisse Populaire Fraternité"):
        result = usd_default(bank, [])
        assert result["currency"] is None and result["canadian_evidence"] == ["canadian_institution_name"], bank


def test_cad_needs_every_bank_name_the_statement_prints_to_be_canadian():
    # Review 4: one page's bank read as a US bank, another's as a Canadian one, decide nothing.
    names = ["Chase", "Royal Bank of Canada"]
    assert usd_default(" ".join(names), [], bank_names=names)["currency"] is None
    names = ["Royal Bank of Canada", "RBC Royal Bank"]
    assert usd_default(" ".join(names), [], bank_names=names)["currency"] == "CAD"
    # A brand printed beside the institution's full name is the same bank (RBC's pages print "RBC" and
    # "Royal Bank of Canada"); the brand alone still decides nothing.
    names = ["Royal Bank of Canada", "RBC", "Banque Royale du Canada"]
    assert usd_default(" ".join(names), [], bank_names=names)["currency"] == "CAD"
    assert usd_default("RBC", [], bank_names=["RBC", "RBC"])["currency"] is None
    names = ["BMO Harris Bank N.A.", "Bank of Montreal"]
    assert usd_default(" ".join(names), [], bank_names=names)["currency"] is None


def test_a_canadian_logo_on_a_statement_mailed_to_a_us_address_is_not_cad():
    # Review 4: a US arm printing its parent's logo ("CIBC") with a Chicago address. A Canadian address, or no
    # address at all, keeps CAD.
    assert usd_default("CIBC", ["FABRICATED CO\n100 FABRICATED ST\nCHICAGO, IL 60603"])["currency"] is None
    assert usd_default("CIBC", ["FABRICATED CO\nFABRICATED CITY QC H0H 0H0"])["currency"] == "CAD"
    assert usd_default("CIBC", ["FABRICATED CO"])["currency"] == "CAD"


def test_a_canadian_address_blocks_the_default_whatever_the_bank_is_called():
    result = usd_default("FABRICATED TRUST", ["FABRICATED INC.\nFABRICATED CITY QC H0H 0H0"])
    assert result["currency"] is None and result["canadian_evidence"] == ["canadian_address"]
    assert canadian_evidence(None, ["FABRICATED CITY, ON K1A 0B1"]) == ("canadian_address",)


def test_california_and_postal_lookalikes_without_a_province_are_not_canadian():
    assert canadian_evidence(None, ["ANYTOWN CA 90000-0000"]) == ()
    assert canadian_evidence(None, ["REF A1B 2C3 TRANSFER"]) == ()          # no province before it


def test_every_bank_name_the_statement_prints_counts():
    # Adapted (slice S4): the bank names below are what the visual pair's `statement_bank_names` returned for its
    # fabricated pages (a pictured cheque's bank left out, a repeated name kept once); the helper left with the pair,
    # and the ruling's half of the test stays: one Canadian name among the printed ones refuses the USD default.
    names = ["FABRICATED NATIONAL BANK", "FABRICATED TRUST OF CANADA"]
    assert usd_default(" ".join(names), [])["currency"] is None
    assert usd_default(" ".join(["FABRICATED NATIONAL BANK"]), [])["currency"] == "USD"


def test_canada_inside_a_transaction_description_is_not_evidence():
    # Page text is scanned for Canadian ADDRESSES only; a US card purchase can say AIR CANADA.
    assert canadian_evidence("FABRICATED NATIONAL BANK", ["POS PURCHASE AIR CANADA 123.45"]) == ()


def test_the_ruling_string_is_pinned():
    # Replaces the visual pair's manifest test (slice S4): the ruling string is part of every result and of stored
    # pair evidence, so it never changes.
    assert USD_DEFAULT_RULING == "gustavo_2026_09_22_usd_unless_canadian_bank"
    assert usd_default("FABRICATED NATIONAL BANK", [])["ruling"] == USD_DEFAULT_RULING


def test_the_rule_is_stdlib_only_and_imports_nothing_of_the_analysis_layer():
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import"
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
    assert imported == {"__future__", "collections", "re", "unicodedata"}, imported
    probe = ("import sys\nimport analysis.currency_default\n"
             "print(sorted(m for m in sys.modules if m.startswith(('analysis.', 'pydantic', 'vlm', 'dotenv'))))\n")
    result = subprocess.run([sys.executable, "-B", "-c", probe], cwd=ROOT, capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "['analysis.currency_default']"
