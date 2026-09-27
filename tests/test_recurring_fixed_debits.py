from __future__ import annotations

import pytest

from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions
from tests.flag_group_fixtures import txn

UNIDENTIFIED = "Unidentified lender obligation"


def _statement(rows) -> Statement:
    return Statement(transactions=[txn(day, description, amount) for day, description, amount in rows])


def test_fixed_weekly_debits_of_an_unknown_payee_become_a_potential_lender():
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", f"ACH DEBIT FABRICATED WIDGETS LLC {day:04d}", -400.0) for day in (2, 9, 16, 23)]
    ))
    assert {record.classification for record in records} == {"potential_lender"}
    assert {record.match_method for record in records} == {"recurring_fixed_debit"}
    # classify_cadence (unchanged) renders an integral mean gap without a decimal.
    assert {record.matched_rule for record in records} == {"weekly_fixed_debit_7_day_average"}
    assert {record.canonical_entity for record in records} == {"Fabricated Widgets LLC"}
    assert all(record.review_required for record in records)
    assert all(
        record.contributes_to_potential_lender_totals and record.contributes_to_potential_withholding_exposure
        for record in records
    )
    assert not any(record.contributes_to_withholding_rate for record in records)


def test_fixed_daily_debits_without_an_organisation_name_stay_unidentified():
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", "ACH DEBIT PAT EXAMPLE", -150.0) for day in (5, 6, 7, 8, 9)]
    ))
    assert {(record.classification, record.canonical_entity) for record in records} == {
        ("potential_lender", UNIDENTIFIED)
    }


NOT_PROMOTED = {
    "two rows": [
        ("2054-01-02", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0),
        ("2054-01-09", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0),
    ],
    "monthly": [(day, "ACH DEBIT FABRICATED WIDGETS LLC", -400.0) for day in ("2054-01-05", "2054-02-05", "2054-03-05")],
    "different amounts": [
        (f"2054-01-{day:02d}", "ACH DEBIT FABRICATED WIDGETS LLC", amount)
        for day, amount in ((2, -100.0), (9, -110.0), (16, -120.0))
    ],
    "transfer wording": [(f"2054-01-{day:02d}", "TRANSFER TO PAT EXAMPLE", -300.0) for day in (2, 9, 16)],
    "channel words only": [(f"2054-01-{day:02d}", f"AB{day:02d} TFR TO 0000000", -300.0) for day in (2, 9, 16)],
    "no payee words": [(f"2054-01-{day:02d}", f"ACH DEBIT {day:04d}", -300.0) for day in (2, 9, 16)],
    "credits": [(f"2054-01-{day:02d}", "FABRICATED WIDGETS LLC", 400.0) for day in (2, 9, 16)],
}


@pytest.mark.parametrize("rows", list(NOT_PROMOTED.values()), ids=list(NOT_PROMOTED))
def test_recurrence_without_a_fixed_daily_or_weekly_unknown_payee_is_not_promoted(rows):
    records = classify_statement_transactions(_statement(rows))
    assert not any(record.classification == "potential_lender" for record in records)


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("CARD PURCHASE FABRICATED STORE", "pos"),
        ("ONLINE TRANSFER TO SAVINGS", "transfer"),
        ("MONTHLY SERVICE FEE", "fee"),
        ("ADP PAYROLL FABRICATED", "payroll"),
        ("IRS TAX PAYMENT FABRICATED", "tax"),
        ("ELECTRIC UTILITY FABRICATED", "utility"),
        ("RENT FABRICATED LANDLORD", "rent"),
        ("FABRICATED INSURANCE PREMIUM", "insurance"),
        ("CHECK FABRICATED CLEANING", "other"),
    ],
)
def test_recurring_rows_a_rule_already_claimed_are_never_promoted(description, state):
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", description, -300.0) for day in (2, 9, 16, 23)]
    ))
    assert {record.classification for record in records} == {state}


def test_proven_duplicates_do_not_make_a_recurring_group():
    statement = Statement(
        transactions=[
            txn("2054-01-02", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0, balance=600.0),
            txn("2054-01-02", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0, balance=600.0),
            txn("2054-01-09", "ACH DEBIT FABRICATED WIDGETS LLC", -400.0, balance=200.0),
        ]
    )
    records = classify_statement_transactions(statement)
    assert not any(record.classification == "potential_lender" for record in records)


def _rows_on_dates(description: str, amount: float, days: tuple[int, ...]):
    return [(f"2054-01-{day:02d}", description, amount) for day in days]


#: Three same-day rows, then five same-day rows five days later: eight rows but
#: only two dates, so one five-day gap would otherwise read as weekly.
TWO_DATES = (2, 2, 2, 7, 7, 7, 7, 7)


@pytest.mark.parametrize(
    "description",
    ["ACH DEBIT FABRICATED WIDGETS LLC", "ACH DEBIT FABRICATED FUNDING LLC"],
    ids=["unknown payee (D6)", "financing keyword"],
)
def test_same_amount_rows_on_only_two_dates_are_not_a_recurrence(description):
    records = classify_statement_transactions(_statement(_rows_on_dates(description, -10.0, TWO_DATES)))
    assert not any(record.classification == "potential_lender" for record in records)
    assert not any(
        record.match_method in {"recurring_fixed_debit", "recurring_financing_counterparty"}
        for record in records
    )


@pytest.mark.parametrize(
    ("description", "method"),
    [
        ("ACH DEBIT FABRICATED WIDGETS LLC", "recurring_fixed_debit"),
        ("ACH DEBIT FABRICATED FUNDING LLC", "recurring_financing_counterparty"),
    ],
    ids=["unknown payee (D6)", "financing keyword"],
)
@pytest.mark.parametrize(
    "days",
    [(2, 9, 16), (2, 9, 9, 16)],
    ids=["three rows on three weekly dates", "four rows on three weekly dates"],
)
def test_same_amount_rows_on_three_weekly_dates_are_promoted(description, method, days):
    records = classify_statement_transactions(_statement(_rows_on_dates(description, -10.0, days)))
    assert {(record.classification, record.match_method) for record in records} == {
        ("potential_lender", method)
    }
    assert len(records) == len(days)


WEEKLY = (2, 9, 16, 23)


@pytest.mark.parametrize(
    "template",
    [
        "PURCHASE 01{day:02d} 4TE*FABRICATED CAFE RICHMOND TX",
        "RECURRING PURCHASE 01{day:02d} FABRICATED STREAMING CO",
        "TST*FABRICATED GRILL AUSTIN TX",
        "SQ *FABRICATED CAFE",
        "TST* FABRICATED GRILL",
    ],
    ids=["purchase mmdd with processor mark", "recurring purchase mmdd", "processor mark only",
         "space before the star", "space after the star"],
)
def test_card_purchase_postings_are_never_a_d6_recurrence(template):
    """D6 does not apply to card purchases, whatever format the bank prints them in."""
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", template.format(day=day), -10.0) for day in WEEKLY]
    ))
    assert {(record.classification, record.match_method) for record in records} == {("other", "default")}


def test_the_reported_card_purchase_shape_stays_other():
    """The owner's report, fabricated: eight same-amount card purchases at one merchant,
    three on one date and five on a date five days later."""
    records = classify_statement_transactions(_statement(
        [(f"2054-01-{day:02d}", f"PURCHASE 01{day:02d} 4TE*FABRICATED CAFE RICHMOND TX", -10.0) for day in TWO_DATES]
    ))
    assert {(record.classification, record.match_method) for record in records} == {("other", "default")}


@pytest.mark.parametrize(
    "description",
    [
        "ACH DEBIT FABRICATED WIDGETS LLC",
        "FABRICATED WIDGETS LLC DES:PURCHASE ID:0000 INDN:PAT EXAMPLE CO ID:0000 CCD",
        "ACH DEBIT FABRICATED WIDGETS LLC PURCHASE 0000",
    ],
    ids=["ach debit", "purchase as entry description", "purchase and digits after the payee"],
)
def test_ach_fixed_weekly_debits_still_reach_d6_when_they_print_purchase(description):
    records = classify_statement_transactions(_statement(_rows_on_dates(description, -10.0, WEEKLY)))
    assert {(record.classification, record.match_method) for record in records} == {
        ("potential_lender", "recurring_fixed_debit")
    }


def _d6_methods(description: str) -> set[tuple[str, str]]:
    records = classify_statement_transactions(_statement(_rows_on_dates(description, -10.0, WEEKLY)))
    return {(record.classification, record.match_method) for record in records}


D6 = {("potential_lender", "recurring_fixed_debit")}


@pytest.mark.parametrize(
    "description",
    [
        "ACH DEBIT FABRICATED WIDGETS LLC CCD RMR*IV*0000",
        "ACH DEBIT FABRICATED WIDGETS LLC ACCT XXXX*0000",
        "FABRICATED WIDGETS LLC DES:PAYMENT ID:FAB*0000",
    ],
    ids=["addenda star", "masked account", "id with a star"],
)
def test_ach_fixed_weekly_debits_whose_fields_print_a_star_still_reach_d6(description):
    """An ACH entry prints stars too; its field marks say it is no card purchase."""
    assert _d6_methods(description) == D6


@pytest.mark.parametrize(
    "mark",
    ["ACH", "CCD", "PPD", "CTX", "WEB", "DES:PAYMENT", "INDN:PAT EXAMPLE", "CO ID:0000", "ID:0000",
     "ORIG CO NAME:FABRICATED", "RMR"],
)
def test_each_ach_field_mark_keeps_a_starred_row_in_d6(mark):
    assert _d6_methods(f"FABRICATED WIDGETS LLC {mark} FAB*0000") == D6


def test_the_same_starred_row_without_an_ach_field_mark_is_read_as_a_card_purchase():
    assert _d6_methods("FABRICATED WIDGETS LLC FAB*0000") == {("other", "default")}


@pytest.mark.parametrize(
    "description",
    ["FABRICATED WIDGETS LLC 0000 *", "*FABRICATED WIDGETS LLC 0000", "FABRICATED WIDGETS LLC ** 0000"],
    ids=["trailing star", "leading star", "double star"],
)
def test_a_star_that_is_no_processor_mark_keeps_the_row_in_d6(description):
    """Only a star between a letter or digit and a letter or digit (one space allowed on each side) is a card
    mark. A bare star is not: this fails if the mark is read as any star."""
    assert _d6_methods(description) == D6


def test_financing_keyword_rows_of_two_unnamed_payees_are_not_merged():
    records = classify_statement_transactions(_statement([
        ("2054-01-02", "ADVANCE PAT EXAMPLE PMT", -200.0),
        ("2054-01-09", "ADVANCE LEE SAMPLE PMT", -200.0),
        ("2054-01-16", "ADVANCE PAT EXAMPLE PMT", -200.0),
        ("2054-01-23", "ADVANCE LEE SAMPLE PMT", -200.0),
    ]))
    assert {record.match_method for record in records} == {"financing_keyword_review"}


def test_fixed_debits_join_the_recurring_debit_view():
    """The CLI's "Recurring fixed debits" lines and batch.py's recurring_debit_groups
    read detect.find_recurring_debits, so the D6 rows must reach it."""
    from analysis.detect import find_recurring_debits

    statement = _statement(
        [(f"2054-01-{day:02d}", f"ACH DEBIT FABRICATED WIDGETS LLC {day:04d}", -400.0) for day in (2, 9, 16, 23)]
    )
    [recurring] = find_recurring_debits(statement)
    assert (recurring.description_key, recurring.amount, recurring.count, recurring.cadence) == (
        "Fabricated Widgets LLC",
        400.0,
        4,
        "weekly",
    )


# --- D6 and push payments (clarified 2026-09-27) -------------------------------------------------------------------
# A push payment the account holder sends prints a masked recipient account, a reference with digits and a free-text
# memo. The reference and the masked digits are reference tokens, so the payee words are the memo's words alone.


def _push(mark: str, day: int, memo: str) -> str:
    """A fabricated push payment: `mark` is the printed recipient ("To ....1111"), the reference varies by day."""
    return f"ACH PAYMENT {mark} FABREF{day:02d}F0FAB7FABRICATED {memo}"


def _push_rows(mark: str, memo: str, amount: float, days: tuple[int, ...]):
    return [(f"2054-01-{day:02d}", _push(mark, day, memo), amount) for day in days]


@pytest.mark.parametrize(
    "memo",
    ["FABRICATED COMMISSION", "fabricated commission", "FABRICAT COMMISION", "FABRICATED BONUS", "FABRICATED SALARY"],
)
def test_weekly_push_payments_whose_memo_names_compensation_stay_other(memo):
    """A commission, a bonus or a salary is pay, not an MCA remittance. D6 only skips the row: it stays "other"."""
    records = classify_statement_transactions(_statement(_push_rows("To ....1111", memo, -140.0, WEEKLY)))
    assert {(record.classification, record.match_method) for record in records} == {("other", "default")}


@pytest.mark.parametrize(
    "word",
    ["COMMISSION", "COMMISSIONS", "COMMISION", "COMMISIONS", "COMISSION", "COMISION", "COMISSIONS", "COMMISSON",
     "BONUS", "BONUSES", "SALARY", "SALARIES", "STIPEND", "STIPENDS", "REIMBURSEMENT", "REIMBURSEMENTS", "REIMB",
     "REIMBURSE", "REIMBURSED", "REIMBURSMENT"],
)
def test_each_compensation_word_keeps_a_fixed_weekly_debit_out_of_d6(word):
    assert _d6_methods(f"ACH DEBIT FABRICATED {word}") == {("other", "default")}


@pytest.mark.parametrize(
    "word", ["COMMON", "COMMISSARY", "COMMITTEE", "COMMISSIONER", "BONUSLY", "SALARYMAN", "REIMAGINE"]
)
def test_words_that_only_look_like_compensation_stay_in_d6(word):
    """Compensation words are read as whole words: these are payee names, and D6 still takes them."""
    assert _d6_methods(f"ACH DEBIT FABRICATED {word}") == D6


#: The printed forms of a masked recipient account after TO.
RECIPIENT_MARKS = ["To ....{}", "TO XXXX{}", "to xxxx{}", "TO ***{}", "TO #{}", "TO x{}", "TO ACCT XXXX{}"]


@pytest.mark.parametrize("mark", RECIPIENT_MARKS)
def test_weekly_push_payments_to_one_masked_recipient_are_still_promoted(mark):
    records = classify_statement_transactions(_statement(
        _push_rows(mark.format("1111"), "FABRICATED WIDGETS LLC", -10.0, (2, 9, 16))
    ))
    assert {(record.classification, record.match_method) for record in records} == D6
    # The recipient's digits split the payees; they never join the published name.
    (entity,) = {record.canonical_entity for record in records}
    assert entity and not any(character.isdigit() for character in entity)


def test_the_masked_recipient_digits_never_join_the_name():
    records = classify_statement_transactions(_statement(
        _push_rows("To ....1111", "FABRICATED WIDGETS LLC", -10.0, (2, 9, 16))
    ))
    assert {record.canonical_entity for record in records} == {"Fabricated Widgets LLC"}


@pytest.mark.parametrize("mark", RECIPIENT_MARKS)
def test_push_payments_to_two_masked_recipients_are_two_payees(mark):
    """The owner's shape, fabricated: the same memo and amount to two recipient accounts on one day, then weekly.
    Together the rows fall on three weekly dates; each recipient alone has two, so neither is a recurrence."""
    rows = [
        *_push_rows(mark.format("1111"), "FABRICATED SUPPLIES", -10.0, (2, 16)),
        *_push_rows(mark.format("2222"), "FABRICATED SUPPLIES", -10.0, (2, 9)),
    ]
    records = classify_statement_transactions(_statement(rows))
    assert {(record.classification, record.match_method) for record in records} == {("other", "default")}


@pytest.mark.parametrize("mark", RECIPIENT_MARKS)
def test_only_the_recipient_with_three_weekly_dates_is_promoted(mark):
    rows = [
        *_push_rows(mark.format("1111"), "FABRICATED SUPPLIES", -10.0, (2, 9, 16)),
        *_push_rows(mark.format("2222"), "FABRICATED SUPPLIES", -10.0, (2, 9)),
    ]
    records = classify_statement_transactions(_statement(rows))
    assert [(record.classification, record.match_method) for record in records] == [
        *[("potential_lender", "recurring_fixed_debit")] * 3,
        *[("other", "default")] * 2,
    ]
    assert records[0].canonical_entity == UNIDENTIFIED


@pytest.mark.parametrize(
    "template",
    ["ACH PAYMENT TO {} FABRICATED WIDGETS LLC", "ACH DEBIT FABRICATED WIDGETS LLC ACCT XXXX{}"],
    ids=["digits after TO with no mask", "a masked account that follows no TO"],
)
def test_rows_without_a_masked_recipient_keep_one_payee(template):
    """Only a masked account printed after TO splits a payee. Without one the key is today's: payee words and amount."""
    rows = [
        (f"2054-01-{day:02d}", template.format(account), -10.0)
        for day, account in zip(WEEKLY, ("1111", "2222", "1111", "2222"))
    ]
    records = classify_statement_transactions(_statement(rows))
    assert {(record.classification, record.match_method) for record in records} == D6
    assert len({record.canonical_entity for record in records}) == 1
