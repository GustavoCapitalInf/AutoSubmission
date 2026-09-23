"""Reuse an existing currency rule only through a faithful visual-text bridge, then apply the owner's default.

No PDF or native text is read here. The caller supplies visual extraction text
and the reviewed source Statement; no filename or model call is a currency proof.

Owner ruling, Gustavo, 2026-09-22: a statement that prints no currency is USD unless the bank is Canadian.
`usd_default` applies it. The value is published with currency_source "schema_default", exactly as the
production readers publish an unlabelled US statement: it was defaulted, not read. A Canadian statement is
never defaulted here; it keeps its own proven jurisdiction rules (RBC today, through the bridge) or stays
currency_missing. When the evidence is mixed the statement is treated as Canadian, because wrongly refusing
is safe and wrongly calling a Canadian statement USD is not. Printed currency always wins, and two different
printed currencies remain a conflict.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from pydantic import ValidationError

from analysis.config import Settings
from analysis.parser_registry import AmbiguousParserError, ParserCrashError, registry_fingerprint
from analysis.pipeline import analyze_document
from analysis.schema import Statement


CURRENCY_RESOLVER_VERSION = 2
_REUSABLE_SOURCES = frozenset({"institution_default"})
_REQUIRES_REVIEWED_DENOMINATION = frozenset({"printed", "product", "jurisdiction_default"})
_NO_PARSER = "no deterministic parser matched this statement"
_EXCLUDED = {"currency", "currency_source", "stated_average_balance"}


def currency_resolution_manifest() -> dict:
    """Bind reuse to both registry declarations and every analysis source file.

    The registry fingerprint does not cover parser implementations. The source
    digest also invalidates a visual-pair receipt when the existing rule or the
    deterministic bridge changes, without changing any global cache version.
    """
    root = Path(__file__).resolve().parents[1]
    sources = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((root / "analysis").rglob("*.py"))
    }
    digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "resolver_version": CURRENCY_RESOLVER_VERSION,
        "registry_fingerprint": registry_fingerprint(),
        "analysis_source_sha256": digest,
        "owner_default": {"ruling": USD_DEFAULT_RULING, "currency": "USD", "currency_source": "schema_default",
                          "canadian_institutions": list(CANADIAN_INSTITUTIONS),
                          "canadian_address_pattern": CANADIAN_ADDRESS_PATTERN,
                          "cad_institutions": list(CAD_INSTITUTIONS), "foreign_arm": list(FOREIGN_ARM),
                          "canadian_bank_currency": "CAD", "canadian_bank_currency_source": "jurisdiction_default"},
    }


# --- Owner ruling: USD unless Canadian -----------------------------------------------------------------
USD_DEFAULT_RULING = "gustavo_2026_09_22_usd_unless_canadian_bank"
# Matched as whole words against the reviewer's bank field only. Page text is NOT scanned for these names:
# a US statement can print "AIR CANADA" in a transaction. Ambiguous names (BMO, which also operates in the
# US) are listed on purpose, because a false "Canadian" only refuses the default.
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
FOREIGN_ARM = ("USA", "U S A", "U S", "N A", "AMERICA", "AMERICAS", "CARIBBEAN", "PUERTO RICO", "INTERNATIONAL",
               "HARRIS", "BAHAMAS", "CAYMAN", "JAMAICA", "BARBADOS", "TRINIDAD")


def _padded(text: str | None) -> str:
    import unicodedata

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


def usd_default(bank: str | None, page_texts: Sequence[str]) -> dict:
    """The owner's default for a statement that printed no currency: USD unless there is Canadian evidence; a
    Canadian bank (canadian_bank) keeps its jurisdiction default, CAD. Other Canadian evidence decides neither:
    the currency stays unknown and the statement is held."""
    evidence = canadian_evidence(bank, page_texts)
    if not evidence:
        currency, source = "USD", "schema_default"
    elif canadian_bank(bank):
        currency, source = "CAD", "jurisdiction_default"
    else:
        currency, source = None, None
    return {"ruling": USD_DEFAULT_RULING, "canadian_evidence": list(evidence),
            "currency": currency, "currency_source": source}


@dataclass(frozen=True)
class CurrencyResolution:
    status: str
    reason: str
    currency: str | None = None
    currency_source: str | None = None
    parser_id: str | None = None
    bridge_currency_source: str | None = None

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"


def _valid_code(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Z]{3}", value) is not None


def resolve_currency(
    reviewed_statement: Mapping,
    visual_markdown: str,
    *,
    sheets: Sequence[str] | None = None,
) -> CurrencyResolution:
    """Return a denomination plus its unchanged evidence class, or unknown.

    A non-null reviewed denomination is source evidence already owned by the
    pair and stays model_extracted; the model cannot certify its provenance.
    For a missing denomination, an existing deterministic parser must claim
    the supplied visual text cleanly and reproduce every reviewed Statement
    field except denomination/provenance. Only its fixed institution rule can
    then be reused with its existing institution_default label. Printed,
    product and jurisdiction rules depend on additional Stage A text whose
    denomination evidence has not been reviewed, so they cannot fill the gap.

    A schema_default says no rule earned the value. It is never upgraded or
    used to supply a missing denomination, including on a matching ledger.
    This deliberately leaves layouts whose visual text no longer preserves
    their parser grammar unresolved. It neither manufactures grammar nor
    copies source fields out of the bridge into the reviewed statement.
    """
    if not isinstance(reviewed_statement, Mapping):
        return CurrencyResolution("unresolved", "source_statement_invalid")
    explicit = reviewed_statement.get("currency")
    if explicit is not None:
        if not _valid_code(explicit):
            return CurrencyResolution("unresolved", "source_currency_invalid")
        return CurrencyResolution("resolved", "reviewed_denomination", explicit, "model_extracted")
    allowed = set(Statement.model_fields) | {"stated_average_balance"}
    if set(reviewed_statement) - allowed:
        return CurrencyResolution("unresolved", "source_statement_invalid")
    if not isinstance(visual_markdown, str) or not visual_markdown.strip():
        return CurrencyResolution("unresolved", "visual_source_missing")

    dispatches = []
    try:
        document = analyze_document(
            visual_markdown, parse_mode="deterministic", sheets=sheets,
            settings=Settings(api_key="", model="offline-currency-bridge",
                              escalation_model="offline-currency-bridge", reconstruction_mode="off"),
            on_dispatch=dispatches.append,
        )
    except AmbiguousParserError:
        return CurrencyResolution("unresolved", "bridge_ambiguous")
    except ParserCrashError:
        return CurrencyResolution("unresolved", "bridge_parser_failed")
    except RuntimeError as exc:
        return CurrencyResolution("unresolved", "bridge_unclaimed" if str(exc) == _NO_PARSER else "bridge_failed")
    except Exception:
        return CurrencyResolution("unresolved", "bridge_failed")
    if len(dispatches) != 1:
        return CurrencyResolution("unresolved", "bridge_claim_missing")
    dispatch = dispatches[0]
    parser_id = dispatch.parser_id
    if dispatch.outcome != "claimed" or not parser_id or dispatch.exceptions:
        return CurrencyResolution("unresolved", "bridge_claim_not_clean", parser_id=parser_id)
    if len(document.accounts) != 1 or document.omissions:
        return CurrencyResolution("unresolved", "bridge_multiple_accounts", parser_id=parser_id)
    parsed = document.accounts[0].statement
    provenance = parsed.currency_source
    diagnostics = {"parser_id": parser_id, "bridge_currency_source": provenance}
    try:
        expected = Statement.model_validate({**reviewed_statement, "currency": parsed.currency,
                                             "currency_source": provenance})
    except (ValidationError, TypeError, ValueError):
        return CurrencyResolution("unresolved", "source_statement_invalid", **diagnostics)
    if expected.model_dump(exclude=_EXCLUDED) != parsed.model_dump(exclude=_EXCLUDED):
        return CurrencyResolution("unresolved", "bridge_sources_differ", **diagnostics)
    if provenance in _REQUIRES_REVIEWED_DENOMINATION:
        return CurrencyResolution("unresolved", "bridge_needs_reviewed_denomination", **diagnostics)
    if provenance not in _REUSABLE_SOURCES:
        return CurrencyResolution("unresolved", "bridge_denomination_unproven", **diagnostics)
    if not _valid_code(parsed.currency):
        return CurrencyResolution("unresolved", "bridge_currency_invalid", **diagnostics)
    return CurrencyResolution("resolved", "existing_parser_rule", parsed.currency,
                              provenance, **diagnostics)
