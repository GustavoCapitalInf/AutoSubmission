"""The page-proposal schema: what Stage B must emit, and what the harness validates locally.

Grammar-safe subset only (vLLM structured outputs, xgrammar backend): type, properties, required,
additionalProperties=false, enum, items, nullable unions. Source-level fields only; never a metric.
"""
from __future__ import annotations

import jsonschema

from vlm.receipts import canonical_json, sha256_bytes

SCHEMA_VERSION = 1
PAGE_ROLES = ("statement_page", "summary_page", "cheque_images", "cover_or_notice", "blank_or_other")
DIRECTIONS = ("credit", "debit", "unknown")
SECTION_KINDS = ("deposits", "withdrawals", "checks", "fees", "mixed", "daily_balances", "other")


def _nullable(kind: str) -> dict:
    return {"type": [kind, "null"]}


_ROW = {
    "type": "object",
    "additionalProperties": False,
    "required": ["date", "date_text", "description", "amount", "direction", "balance",
                 "section_index", "continues_previous", "box"],
    "properties": {
        "date": _nullable("string"),
        "date_text": {"type": "string"},
        "description": {"type": "string"},
        "amount": {"type": "number"},
        "direction": {"type": "string", "enum": list(DIRECTIONS)},
        "balance": _nullable("number"),
        "section_index": _nullable("integer"),
        "continues_previous": {"type": "boolean"},
        "box": {"type": ["array", "null"], "items": {"type": "number"}},
    },
}

_ACCOUNT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["bank", "account_name", "account_number_last4", "currency", "period_start",
                 "period_end", "beginning_balance", "ending_balance"],
    "properties": {
        "bank": _nullable("string"),
        "account_name": _nullable("string"),
        "account_number_last4": _nullable("string"),
        "currency": _nullable("string"),
        "period_start": _nullable("string"),
        "period_end": _nullable("string"),
        "beginning_balance": _nullable("number"),
        "ending_balance": _nullable("number"),
    },
}

PAGE_PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page_role", "account", "sections", "rows", "daily_balances", "notes"],
    "properties": {
        "page_role": {"type": "string", "enum": list(PAGE_ROLES)},
        "account": _ACCOUNT,
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "kind"],
                "properties": {"name": {"type": "string"}, "kind": {"type": "string", "enum": list(SECTION_KINDS)}},
            },
        },
        "rows": {"type": "array", "items": _ROW},
        "daily_balances": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["date", "balance"],
                "properties": {"date": _nullable("string"), "balance": {"type": "number"}},
            },
        },
        "notes": {"type": "string"},
    },
}

_VALIDATOR = jsonschema.Draft202012Validator(PAGE_PROPOSAL_SCHEMA)


def schema_sha256() -> str:
    return sha256_bytes(canonical_json(PAGE_PROPOSAL_SCHEMA).encode("utf-8"))


def validate_page_proposal(obj: object) -> list[str]:
    return sorted(f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in _VALIDATOR.iter_errors(obj))


def empty_proposal(page_role: str = "blank_or_other") -> dict:
    return {
        "page_role": page_role,
        "account": {k: None for k in _ACCOUNT["required"]},
        "sections": [],
        "rows": [],
        "daily_balances": [],
        "notes": "",
    }
