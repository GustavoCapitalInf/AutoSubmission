"""The owner's currency default for a statement that prints no currency: USD unless the bank is Canadian.

Owner ruling, Gustavo, 2026-09-22: a statement that prints no currency is USD unless the bank is Canadian.
`usd_default` applies it. The USD value is published with currency_source "schema_default", exactly as the
production readers publish an unlabelled US statement: it was defaulted, not read. A Canadian bank keeps its
jurisdiction default, CAD (currency_source "jurisdiction_default", as the currency doctrine does for RBC), when
every bank name the statement prints is Canadian and no US address alone says otherwise (the rulings of
2026-09-23: a Canadian bank name is enough, no address is needed; a US address with no Canadian one vetoes CAD).
Any other Canadian evidence decides neither: the currency stays unknown and the statement is held, because
wrongly refusing is safe and wrongly calling a Canadian statement USD is not. Printed currency always wins and
never reaches this module: it applies only where nothing was printed.

Deterministic and stdlib-only (re, unicodedata, collections.abc); it imports nothing of `analysis` and reads no
file, environment or model. Moved here unchanged from `vlm/currency.py` (the block from `USD_DEFAULT_RULING`
through `usd_default`) when the visual pair was removed (model-code removal, slice S4; owner ruling of
2026-10-13: the product uses no model). The pair's bridge around it (`resolve_currency`, `CurrencyResolution`,
`currency_resolution_manifest`) was deleted with the pair. Nothing in production calls this module today: its one
caller was the pair's merge (`vlm/pair.py`). The text-first reader is its planned caller, and should import it
rather than keep a second copy of the ruling.
"""
from __future__ import annotations

from collections.abc import Sequence
import re
import unicodedata


# --- Owner ruling: USD unless Canadian -----------------------------------------------------------------
USD_DEFAULT_RULING = "gustavo_2026_09_22_usd_unless_canadian_bank"
# Matched as whole words against the bank field only. Page text is NOT scanned for these names: a US statement
# can print "AIR CANADA" in a transaction. Ambiguous names (BMO, which also operates in the US) are listed on
# purpose, because a false "Canadian" only refuses the default.
CANADIAN_INSTITUTIONS = ("CANADA", "CANADIAN", "CANADA TRUST", "ROYAL BANK", "RBC", "CIBC", "BANK OF MONTREAL",
                         "BMO", "SCOTIABANK", "NOVA SCOTIA", "DESJARDINS", "BANQUE", "CAISSE", "ATB",
                         "LAURENTIAN", "TANGERINE", "SIMPLII", "EQ BANK", "MERIDIAN", "VANCITY", "SERVUS")
# A Canadian province or territory followed by a Canadian postal code, as printed in an address block. The
# postal code alone is too loose (reference codes can look like it); with the province it is specific. The
# postal-code letters are those Canada Post uses, as in analysis/rbc.py.
_PROVINCES = r"(?:AB|BC|MB|NB|NL|NS|NT|NU|ON|PE|QC|PQ|SK|YT)"
_CA_POSTAL = r"[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ \t]\d[ABCEGHJ-NPRSTV-Z]\d"
CANADIAN_ADDRESS_PATTERN = r"(?<![A-Z0-9])" + _PROVINCES + r"[ ,\t]+" + _CA_POSTAL + r"(?![A-Z0-9])"


# The ruling's other half ("Canadian banks keep their jurisdiction default, CAD, as the doctrine already does
# for RBC"): institutions that are Canadian unless their printed name marks a US or offshore arm. Stricter than
# CANADIAN_INSTITUTIONS, which only refuses the USD default: a wrong CAD would mislabel the statement.
CAD_INSTITUTIONS = ("CIBC", "ROYAL BANK OF CANADA", "RBC ROYAL BANK", "BANQUE ROYALE", "TD CANADA TRUST",
                    "CANADA TRUST", "SCOTIABANK", "BANK OF NOVA SCOTIA", "BANQUE SCOTIA", "BANK OF MONTREAL",
                    "BANQUE DE MONTREAL", "DESJARDINS", "BANQUE NATIONALE", "NATIONAL BANK OF CANADA",
                    "TANGERINE", "SIMPLII", "ATB FINANCIAL", "LAURENTIAN BANK", "BANQUE LAURENTIENNE", "EQ BANK",
                    "MERIDIAN CREDIT UNION", "VANCITY", "SERVUS CREDIT UNION", "CANADIAN WESTERN BANK",
                    "CAISSE POPULAIRE")
FOREIGN_ARM = ("USA", "U S A", "U S", "US", "N A", "NA", "N V", "NV", "S A", "SA", "AMERICA", "AMERICAS",
               "CARIBBEAN", "PUERTO RICO", "INTERNATIONAL", "HARRIS", "BAHAMAS", "CAYMAN", "JAMAICA", "BARBADOS",
               "TRINIDAD", "ARUBA", "SURINAME", "MEXICO", "PERU", "CHILE", "COLOMBIA", "COSTA RICA", "PANAMA",
               "URUGUAY", "EL SALVADOR", "DOMINICAN", "GUYANA", "BELIZE", "AGRICOLE", "FRATERNITE")


def _padded(text: str | None) -> str:
    plain = "".join(char for char in unicodedata.normalize("NFKD", str(text or "").upper())
                    if not unicodedata.combining(char))
    return " " + re.sub(r"[^A-Z0-9]+", " ", plain).strip() + " "


def canadian_evidence(bank: str | None, page_texts: Sequence[str]) -> tuple[str, ...]:
    """Why this statement looks Canadian, or () when nothing does."""
    reasons = []
    padded = _padded(bank)
    if any(f" {name} " in padded for name in CANADIAN_INSTITUTIONS):
        reasons.append("canadian_institution_name")
    if any(re.search(CANADIAN_ADDRESS_PATTERN, str(text).upper()) for text in page_texts):
        reasons.append("canadian_address")
    return tuple(reasons)


def canadian_bank(bank: str | None) -> bool:
    """Whether the printed bank name is a Canadian institution (CAD_INSTITUTIONS) and names no foreign arm."""
    padded = _padded(bank)
    return (any(f" {name} " in padded for name in CAD_INSTITUTIONS)
            and not any(f" {marker} " in padded for marker in FOREIGN_ARM))


# A US state followed by a ZIP code, as an address block prints it ("CHICAGO, IL 60603").
_US_STATES = (r"(?:AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|"
              r"NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)")
US_ADDRESS_PATTERN = r"(?<![A-Z0-9])" + _US_STATES + r"[ ,\t]+\d{5}(?:-\d{4})?(?![A-Z0-9-])"


def _canadian_name(bank: str | None) -> bool:
    """A Canadian bank's name or brand (CANADIAN_INSTITUTIONS: "RBC" printed beside "Royal Bank of Canada") that
    names no foreign arm; alone, a brand other countries share decides nothing."""
    padded = _padded(bank)
    return (any(f" {name} " in padded for name in CANADIAN_INSTITUTIONS)
            and not any(f" {marker} " in padded for marker in FOREIGN_ARM))


def usd_default(bank: str | None, page_texts: Sequence[str], *, bank_names: Sequence[str] = ()) -> dict:
    """The owner's default for a statement that printed no currency: USD unless there is Canadian evidence; a
    Canadian bank (canadian_bank) keeps its jurisdiction default, CAD, when every bank name the statement
    prints is Canadian (``bank_names``: an institution, or its brand beside it, "RBC" with "Royal Bank of
    Canada"; a US bank's name on one page and a Canadian one on another decide nothing). Other Canadian
    evidence decides neither: the currency stays unknown and the statement is held."""
    evidence = canadian_evidence(bank, page_texts)
    names = list(bank_names or [bank])
    # A US arm can print the parent's Canadian logo ("CIBC" on a CIBC Bank USA statement): a US address with no
    # Canadian one refuses CAD. No address at all does not (a Canadian statement need print none).
    us_only = ("canadian_address" not in evidence
               and any(re.search(US_ADDRESS_PATTERN, str(text).upper()) for text in page_texts))
    if not evidence:
        currency, source = "USD", "schema_default"
    elif (not us_only and any(canadian_bank(name) for name in names)
          and all(canadian_bank(name) or _canadian_name(name) for name in names)):
        currency, source = "CAD", "jurisdiction_default"
    else:
        currency, source = None, None
    return {"ruling": USD_DEFAULT_RULING, "canadian_evidence": list(evidence),
            "currency": currency, "currency_source": source}
