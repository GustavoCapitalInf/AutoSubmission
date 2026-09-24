"""The page-proposal schema: what Stage B must emit, and what the harness validates locally.

Grammar-safe subset only (vLLM structured outputs, xgrammar backend): type, properties, required,
additionalProperties=false, enum, items, nullable unions. Source-level fields only; never a metric.

Schema 5 requires a source description observation and compact field corrections;
the deterministic merge retains full original and corrected row evidence.
Schema 4 adds the explicit per-candidate review contract and full source metadata;
the independent proposal API retains its schema-3 shape for existing callers.
Schema 3 (DEV wave: `box` and `section_index` dropped — unused by the gate and ~15 percent of the
output tokens on dense pages; review MAJOR-4): the account block asks for the bank's OWN printed totals and counts, so the
reader's summary identity and per-direction count coverage can decide admission independently of the
proposal's own arithmetic.
"""
from __future__ import annotations

import json
from copy import deepcopy
import jsonschema

from vlm.receipts import canonical_json, sha256_bytes

SCHEMA_VERSION = 6
PAGE_ROLES = ("statement_page", "summary_page", "cheque_images", "cover_or_notice", "blank_or_other")
DIRECTIONS = ("credit", "debit", "unknown")
SECTION_KINDS = ("deposits", "withdrawals", "checks", "fees", "mixed", "daily_balances", "other")


def _nullable(kind: str) -> dict:
    return {"type": [kind, "null"]}


_ROW = {
    "type": "object",
    "additionalProperties": False,
    "required": ["date", "date_text", "description", "amount", "direction", "balance", "continues_previous"],
    "properties": {
        "date": _nullable("string"),
        "date_text": {"type": "string"},
        "description": {"type": "string"},
        "amount": {"type": "number"},
        "direction": {"type": "string", "enum": list(DIRECTIONS)},
        "balance": _nullable("number"),
        "continues_previous": {"type": "boolean"},
    },
}

_ACCOUNT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["bank", "account_name", "account_number_last4", "currency", "period_start",
                 "period_end", "beginning_balance", "ending_balance",
                 "stated_total_credits", "stated_total_debits", "stated_credit_count", "stated_debit_count"],
    "properties": {
        "bank": _nullable("string"),
        "account_name": _nullable("string"),
        "account_number_last4": _nullable("string"),
        "currency": _nullable("string"),
        "period_start": _nullable("string"),
        "period_end": _nullable("string"),
        "beginning_balance": _nullable("number"),
        "ending_balance": _nullable("number"),
        "stated_total_credits": _nullable("number"),
        "stated_total_debits": _nullable("number"),
        "stated_credit_count": _nullable("integer"),
        "stated_debit_count": _nullable("integer"),
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


# Schema 4 adds review mode without changing the independent proposal contract.
# Date and cross-field semantics are validated locally. Review boxes also carry
# constrained numeric/array bounds to prevent pixel coordinates in guided output.
REVIEW_VERDICTS = ("confirm", "correct", "reject", "unresolved")
REVIEW_ROW_FIELDS = ("date", "date_text", "description", "amount", "direction", "balance", "bbox", "printed_amount")
REVIEW_ROW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": list(REVIEW_ROW_FIELDS),
    "properties": {**{k: v for k, v in _ROW["properties"].items() if k != "continues_previous"},
                   "bbox": {"type": ["array", "null"], "minItems": 4, "maxItems": 4,
                            "items": {"type": "number", "minimum": 0, "maximum": 1}},
                   "printed_amount": _nullable("number")},
}
_REVIEW_ACCOUNT_PROPERTIES = {
    **{k: v for k, v in _ACCOUNT["properties"].items() if k != "account_number_last4"},
    "account_number": _nullable("string"),
    "days_in_period": _nullable("integer"),
    "stated_service_charge": _nullable("number"),
    "stated_interest_paid": _nullable("number"),
    "stated_nsf_count": _nullable("integer"),
    "bank_reported_average_balance": _nullable("number"),
    "bank_reported_average_label": _nullable("string"),
}
# A field's exact type is checked again on the reconstructed row locally. Keeping
# the wire value compact avoids repeating two complete rows for every correction.
_REVIEW_FIELD_VALUE = {"type": ["string", "number", "array", "null"], "items": {"type": "number"}}
PAGE_REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["page_role", "account", "account_numbers_seen", "reviews", "added", "daily_balances", "notes"],
    "properties": {
        "page_role": {"type": "string", "enum": list(PAGE_ROLES)},
        "account": {"type": "object", "additionalProperties": False,
                    "required": list(_REVIEW_ACCOUNT_PROPERTIES), "properties": _REVIEW_ACCOUNT_PROPERTIES},
        "account_numbers_seen": {"type": "array", "items": {"type": "string"}},
        "reviews": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["candidate_id", "observed_description", "verdict", "corrections", "reason"],
            "properties": {
                "candidate_id": {"type": "string"},
                "observed_description": _nullable("string"),
                "verdict": {"type": "string", "enum": list(REVIEW_VERDICTS)},
                "corrections": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["field", "original", "corrected"],
                    "properties": {
                        "field": {"type": "string", "enum": list(REVIEW_ROW_FIELDS)},
                        "original": _REVIEW_FIELD_VALUE,
                        "corrected": _REVIEW_FIELD_VALUE,
                    },
                }},
                "reason": {"type": "string"},
            },
        }},
        "added": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["row", "after_candidate_id"],
            "properties": {"row": REVIEW_ROW_SCHEMA, "after_candidate_id": _nullable("string")},
        }},
        "daily_balances": PAGE_PROPOSAL_SCHEMA["properties"]["daily_balances"],
        "notes": {"type": "string"},
    },
}
_REVIEW_VALIDATOR = jsonschema.Draft202012Validator(PAGE_REVIEW_SCHEMA)
_REVIEW_ROW_VALIDATOR = jsonschema.Draft202012Validator(REVIEW_ROW_SCHEMA)

# Batched review owns candidate verdicts only. One later page pass owns all
# additions and metadata, so batches cannot rediscover each other's rows.
REVIEW_BATCH_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["reviews"],
    "properties": {"reviews": deepcopy(PAGE_REVIEW_SCHEMA["properties"]["reviews"])},
}
PAGE_DISCOVERY_SCHEMA = {
    **deepcopy(PAGE_REVIEW_SCHEMA),
    "required": [field for field in PAGE_REVIEW_SCHEMA["required"] if field != "reviews"],
    "properties": {field: deepcopy(value) for field, value in PAGE_REVIEW_SCHEMA["properties"].items()
                   if field != "reviews"},
}


def review_batch_schema(candidate_ids) -> dict:
    schema = deepcopy(REVIEW_BATCH_SCHEMA)
    ids = list(candidate_ids)
    schema["properties"]["reviews"].update(minItems=len(ids), maxItems=len(ids))
    schema["properties"]["reviews"]["items"]["properties"]["candidate_id"]["enum"] = ids
    return schema


def review_discovery_schema(candidate_ids) -> dict:
    schema = deepcopy(PAGE_DISCOVERY_SCHEMA)
    schema["properties"]["added"]["items"]["properties"]["after_candidate_id"]["enum"] = [None, *candidate_ids]
    return schema


def review_schema_sha256() -> str:
    return sha256_bytes(canonical_json(PAGE_REVIEW_SCHEMA).encode("utf-8"))


def review_schema_ordered_sha256() -> str:
    """Pin declaration order separately from JSON Schema's unordered semantics."""
    return sha256_bytes(json.dumps(PAGE_REVIEW_SCHEMA, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def validate_page_review(obj: object) -> list[str]:
    return sorted(f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in _REVIEW_VALIDATOR.iter_errors(obj))


def valid_review_row(obj: object) -> bool:
    """Check field-specific types after compact corrections are reconstructed."""
    return _REVIEW_ROW_VALIDATOR.is_valid(obj)


def empty_review(page_role: str = "blank_or_other") -> dict:
    return {"page_role": page_role, "account": {k: None for k in _REVIEW_ACCOUNT_PROPERTIES},
            "account_numbers_seen": [], "reviews": [], "added": [], "daily_balances": [], "notes": ""}
