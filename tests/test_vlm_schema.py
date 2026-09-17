from vlm import schema


def _row(**overrides):
    row = {"date": "2031-01-02", "date_text": "01/02", "description": "SYNTHETIC ROW 02", "amount": 20.0,
           "direction": "credit", "balance": 530.0, "section_index": 0, "continues_previous": False,
           "box": [0.1, 0.2, 0.9, 0.22]}
    row.update(overrides)
    return row


def _proposal():
    return {
        "page_role": "statement_page",
        "account": {"bank": "SYNTHETIC BANK", "account_name": None, "account_number_last4": "0001",
                    "currency": "USD", "period_start": "2031-01-01", "period_end": "2031-01-31",
                    "beginning_balance": 500.0, "ending_balance": 860.0,
                    "stated_total_credits": 360.0, "stated_total_debits": None,
                    "stated_credit_count": 8, "stated_debit_count": None},
        "sections": [{"name": "TRANSACTIONS", "kind": "mixed"}],
        "rows": [_row()],
        "daily_balances": [],
        "notes": "",
    }


def test_valid_proposal_has_no_errors():
    assert schema.validate_page_proposal(_proposal()) == []


def test_additional_property_is_rejected():
    bad = _proposal()
    bad["extra"] = 1
    assert schema.validate_page_proposal(bad)


def test_bad_direction_and_missing_field_are_rejected():
    bad = _proposal()
    bad["rows"][0]["direction"] = "in"
    assert schema.validate_page_proposal(bad)
    bad2 = _proposal()
    del bad2["rows"][0]["amount"]
    assert schema.validate_page_proposal(bad2)


def test_nullables_allowed():
    ok = _proposal()
    ok["rows"][0].update({"date": None, "balance": None, "section_index": None, "box": None})
    ok["account"] = {k: None for k in ok["account"]}
    assert schema.validate_page_proposal(ok) == []


def test_schema_uses_only_grammar_safe_keywords():
    def keys(node):
        if isinstance(node, dict):
            for k, v in node.items():
                yield k
                yield from keys(v)
        elif isinstance(node, list):
            for v in node:
                yield from keys(v)
    forbidden = {"pattern", "format", "minimum", "maximum", "minLength", "maxLength", "oneOf", "allOf", "$ref"}
    assert not (set(keys(schema.PAGE_PROPOSAL_SCHEMA)) & forbidden)


def test_schema_hash_is_stable_and_empty_proposal_valid():
    assert schema.schema_sha256() == schema.schema_sha256() and len(schema.schema_sha256()) == 64
    assert schema.validate_page_proposal(schema.empty_proposal()) == []
    assert schema.empty_proposal()["page_role"] == "blank_or_other"
