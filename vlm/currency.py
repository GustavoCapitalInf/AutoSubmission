"""Reuse an existing currency rule only through a faithful visual-text bridge.

No PDF or native text is read here. The caller supplies visual extraction text
and the reviewed source Statement; no filename, bank-name lookup, new default,
or model call is a currency proof. Existing weak schema defaults stay unknown.
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
    }


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
