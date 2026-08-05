from analysis.grounding import parser_validated_source, validate_generic_source
from analysis.schema import Statement, StatementDailyBalance, Transaction


def _transaction(*, page: int | None = 1, amount: float = 125.5) -> Transaction:
    return Transaction(
        date="2026-06-05",
        description="ACME CUSTOMER RECEIPT",
        amount=amount,
        direction="credit" if amount >= 0 else "debit",
        running_balance=1125.5,
        source_page=page,
    )


def _statement(**values) -> Statement:
    defaults = {
        "bank": "Test Community Bank",
        "account_number": "1234",
        "document_account_count": 1,
        "account_selection_status": "single_account",
        "period_start": "2026-06-01",
        "period_end": "2026-06-30",
    }
    defaults.update(values)
    return Statement(**defaults)


def _validate_source(statement: Statement, markdown: str):
    return validate_generic_source(
        statement,
        markdown + "\nTEST COMMUNITY BANK Account 1234\n",
    )


def test_generic_source_grounding_matches_row_and_statement_amounts():
    statement = _statement(
        beginning_balance=1000.0,
        ending_balance=1125.5,
        stated_total_credits=125.5,
        stated_total_debits=0.0,
        transactions=[_transaction()],
    )
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    Beginning Balance 1,000.00
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    Total Credits 125.50
    Total Debits 0.00
    Ending Balance 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert result.ok
    assert result.score == 1.0
    assert result.grounded_transaction_count == 1


def test_generic_source_grounding_rejects_wrong_claimed_page():
    statement = _statement(transactions=[_transaction(page=1)])
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    No activity on this page.
    --- Page 2 ---
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.ungrounded_transaction_indexes == [1]
    assert result.missing_page_evidence_indexes == []


def test_generic_source_grounding_does_not_reuse_one_amount_for_duplicate_rows():
    statement = _statement(transactions=[_transaction(), _transaction()])
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.grounded_transaction_count == 1
    assert result.ungrounded_transaction_indexes == [2]


def test_generic_source_grounding_rejects_hallucinated_summary_field():
    statement = _statement(
        beginning_balance=1000.0,
        ending_balance=9999.99,
        transactions=[_transaction()],
    )
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    Beginning Balance 1,000.00
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    Ending Balance 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.ungrounded_statement_fields == ["ending_balance"]


def test_generic_source_grounding_requires_proven_single_account_scope():
    statement = Statement(transactions=[_transaction()])
    markdown = """
    --- Page 1 ---
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.account_scope_valid is False
    assert result.score < 1.0
    assert "generic extraction did not prove isolation of one source account" in result.notes


def test_generic_source_grounding_rejects_wrong_posting_date():
    statement = _statement(transactions=[_transaction()])
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    06/06 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.ungrounded_transaction_indexes == [1]


def test_generic_source_grounding_rejects_unprinted_running_balance():
    statement = _statement(transactions=[_transaction()])
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    06/05 ACME CUSTOMER RECEIPT 125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.ungrounded_transaction_indexes == [1]


def test_generic_source_grounding_rejects_zero_amount_rows():
    statement = _statement(transactions=[_transaction(amount=0.0)])
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    06/05 ACME CUSTOMER RECEIPT 0.00 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.ungrounded_transaction_indexes == [1]


def test_generic_source_grounding_rejects_unprinted_period_boundary():
    statement = _statement(
        period_start="2026-06-05",
        period_end="2026-06-30",
        transactions=[_transaction()],
    )
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.period_scope_valid is False


def test_statement_balance_requires_nearby_source_label():
    statement = _statement(
        ending_balance=1125.5,
        transactions=[_transaction()],
    )
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.ungrounded_statement_fields == ["ending_balance"]


def test_explicit_zero_activity_statement_can_be_grounded():
    statement = _statement(
        beginning_balance=1000.0,
        ending_balance=1000.0,
        stated_total_credits=0.0,
        stated_total_debits=0.0,
        transactions=[],
    )
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    Beginning Balance 1,000.00
    Total Credits 0.00
    Total Debits 0.00
    Ending Balance 1,000.00
    """

    result = _validate_source(statement, markdown)

    assert result.ok
    assert result.zero_activity_supported is True
    assert result.score == 1.0


def test_generic_source_grounding_rejects_wrong_account_suffix():
    statement = _statement(account_number="9999", transactions=[_transaction()])
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.identity_scope_valid is False


def test_generic_period_grounding_accepts_two_digit_years():
    statement = _statement(transactions=[_transaction()])
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/26 through 06/30/26
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert result.period_scope_valid is True


def test_generic_source_grounding_rejects_unprinted_daily_balance_row():
    statement = _statement(
        transactions=[_transaction()],
        stated_daily_balances=[
            StatementDailyBalance(
                date="2026-06-05",
                balance=1125.5,
                source_page=1,
            )
        ],
    )
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert not result.ok
    assert result.ungrounded_daily_balance_indexes == [1]


def test_short_punctuated_bank_identity_is_grounded_as_a_token():
    statement = _statement(bank="U.S. Bank", transactions=[_transaction()])
    markdown = """
    --- Page 1 ---
    U.S. BANK Account 1234
    Statement Period 06/01/2026 through 06/30/2026
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    """

    result = validate_generic_source(statement, markdown)

    assert result.identity_scope_valid is True


def test_generic_source_grounding_accepts_printed_daily_balance_row():
    statement = _statement(
        transactions=[_transaction()],
        stated_daily_balances=[
            StatementDailyBalance(
                date="2026-06-05",
                balance=1125.5,
                source_page=1,
            )
        ],
    )
    markdown = """
    --- Page 1 ---
    Statement Period 06/01/2026 through 06/30/2026
    06/05 ACME CUSTOMER RECEIPT 125.50 1,125.50
    Daily Balance Summary
    06/05 1,125.50
    """

    result = _validate_source(statement, markdown)

    assert result.ok
    assert result.grounded_daily_balance_count == 1


def test_deterministic_parser_contract_is_explicitly_non_generic():
    result = parser_validated_source()

    assert result.ok
    assert result.method == "deterministic_parser_contract"
