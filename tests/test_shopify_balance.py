"""The Shopify Balance ledger (W3 §CITI3 card A).

Every fixture is a hand-built minimal document in the layout's printed shape.
No archive text is reproduced: the fixtures carry the STRUCTURE the parser
reads — the masthead, the summary block, the grid header, the posting rows and
the closing `Totals` row — with invented names and figures.
"""
from __future__ import annotations

from analysis import shopify_balance as sb
from analysis.parser_registry_entries import load
from analysis.schema import Statement


def _document(
    *,
    account: str = "27001000000000001",
    period: tuple[str, str] = ("June 01, 2026", "June 30, 2026"),
    starting: str = "$1,000.00",
    deposits: str = "$500.00",
    withdrawals: str = "-$300.00",
    ending: str = "$1,200.00",
    closing_date: str = "06/30/2026",
    rows: str = (
        "Jun 01, 2026 Jun 01, 2026 Shopify Payments payout $500.00 $1,500.00\n"
        "Jun 02, 2026 Jun 01, 2026 SOME MERCHANT -$300.00 $1,200.00\n"
    ),
    totals: str | None = "$200.00",
) -> str:
    tail = ""
    if totals is not None:
        tail = (
            f"Totals Amount Account balance as of\n{closing_date}\n{totals} {ending}\n"
        )
    return (
        "Shopify Balance\n"
        "Shopify Inc. 151 O'Connor St, Ground Floor Ottawa, ON Canada\n"
        "Statement ID: 10000000.1\n"
        f"Account: #{account}\n"
        "Statement summary\n"
        f"{period[0]} to {period[1]}\n"
        f"Starting balance {starting}\n"
        f"Deposits and credits {deposits}\n"
        f"Withdrawals and debits {withdrawals}\n"
        f"Account balance as of {closing_date} {ending}\n"
        "Transaction history\n"
        f"{period[0]} to {period[1]}\n"
        "Posted Date Transaction Date Description Amount Account balance\n"
        f"{rows}"
        f"{tail}"
    )


#: The inert second account every multi-account document in the family carries.
_INERT_BLOCK = _document(
    account="9900000000000002",
    starting="$0.00",
    deposits="$0.00",
    withdrawals="$0.00",
    ending="$0.00",
    rows="No transactions during this period.\n",
    totals=None,
)


# ---------------------------------------------------------------------------
# detection
# ---------------------------------------------------------------------------

def test_detects_its_own_layout():
    assert sb.detect(_document()).claims


def test_the_partner_bank_named_in_the_disclosure_is_not_the_issuer():
    """The archive files these under Fifth Third because the money is held
    there. Naming the partner bank must neither be required nor sufficient."""
    without_partner = _document()
    assert "Fifth Third" not in without_partner
    assert sb.detect(without_partner).claims

    partner_only = (
        "Fifth Third Bank\nEvolve Bank & Trust\nMembers FDIC\n"
        "Beginning Balance\nEnding Balance\n"
    )
    assert not sb.detect(partner_only).claims


def test_a_mention_of_shopify_in_a_description_is_not_a_shopify_statement():
    """Other banks' statements carry `SHOPIFY*` merchant rows."""
    host = (
        "CHASE\nCHECKING SUMMARY\n"
        "06/01 SHOPIFY* 466518597 Shopify Balance transfer 290.58 1,000.00\n"
    )
    assert not sb.detect(host).claims


def test_detection_does_not_depend_on_the_filename():
    named = "<!-- SOURCE: shopify balance statement.pdf -->\nBeginning Balance\n"
    assert not sb.detect(named).claims


# ---------------------------------------------------------------------------
# the printed grid
# ---------------------------------------------------------------------------

def test_reads_the_summary_the_grid_and_the_signs():
    stmt = sb.parse_shopify_balance_statement(_document())
    assert stmt is not None
    assert stmt.bank == "Shopify Balance"
    assert stmt.account_number == "27001000000000001"
    assert stmt.period_start == "2026-06-01"
    assert stmt.period_end == "2026-06-30"
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1200.00
    # Both totals are magnitudes, though the withdrawals cell prints its own
    # minus.
    assert stmt.stated_total_credits == 500.00
    assert stmt.stated_total_debits == 300.00
    assert [t.amount for t in stmt.transactions] == [500.00, -300.00]
    assert [t.direction for t in stmt.transactions] == ["credit", "debit"]
    assert [t.running_balance for t in stmt.transactions] == [1500.00, 1200.00]


def test_the_posted_date_column_is_the_posting_date():
    """The grid prints two dates per row. The first is `Posted Date`."""
    stmt = sb.parse_shopify_balance_statement(_document())
    assert [t.date for t in stmt.transactions] == ["2026-06-01", "2026-06-02"]


def test_the_grid_prints_no_counts_so_none_are_claimed():
    stmt = sb.parse_shopify_balance_statement(_document())
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


def test_a_description_that_wraps_keeps_its_own_amount():
    """A long description pushes its money cells onto the next physical line;
    only the date pair says where one row ends and the next begins."""
    stmt = sb.parse_shopify_balance_statement(
        _document(
            rows=(
                "Jun 01, 2026 Jun 01, 2026 Shopify Payments payout $500.00 $1,500.00\n"
                "Jun 02, 2026 Jun 01, 2026 ACH transfer to Some Credit Union (**** 0107)\n"
                "-$300.00 $1,200.00\n"
            )
        )
    )
    assert stmt is not None
    assert len(stmt.transactions) == 2
    assert stmt.transactions[1].description == "ACH transfer to Some Credit Union (**** 0107)"
    assert stmt.transactions[1].amount == -300.00


def test_a_month_name_inside_a_description_does_not_split_a_row():
    stmt = sb.parse_shopify_balance_statement(
        _document(
            rows=(
                "Jun 01, 2026 Jun 01, 2026 Rewards credit: May 2026 $500.00 $1,500.00\n"
                "Jun 02, 2026 Jun 01, 2026 APY earned in May 2026 -$300.00 $1,200.00\n"
            )
        )
    )
    assert stmt is not None
    assert len(stmt.transactions) == 2
    assert stmt.transactions[0].description == "Rewards credit: May 2026"


def test_page_furniture_never_reaches_a_description():
    stmt = sb.parse_shopify_balance_statement(
        _document(
            rows=(
                "Jun 01, 2026 Jun 01, 2026 Shopify Payments payout $500.00 $1,500.00\n"
                "Page 2/3 If you have any questions or complaints, contact Shopify Support\n"
                "--- Page 3 ---\n"
                "Posted Date Transaction Date Description Amount Account balance\n"
                "Jun 02, 2026 Jun 01, 2026 SOME MERCHANT -$300.00 $1,200.00\n"
            )
        )
    )
    assert stmt is not None
    assert [t.description for t in stmt.transactions] == [
        "Shopify Payments payout",
        "SOME MERCHANT",
    ]


def test_a_header_with_no_ledger_is_not_a_statement():
    assert sb.parse_shopify_balance_statement(_document(rows="", totals=None)) is None


# ---------------------------------------------------------------------------
# more than one account on one PDF
# ---------------------------------------------------------------------------

def test_an_inert_second_account_does_not_block_the_funded_one():
    """Zero opening, zero movement, zero closing and no rows: the block is
    arithmetically absent, so publishing the funded account alone is exact."""
    stmt = sb.parse_shopify_balance_statement(_document() + _INERT_BLOCK)
    assert stmt is not None
    assert stmt.account_number == "27001000000000001"
    assert stmt.beginning_balance == 1000.00
    assert len(stmt.transactions) == 2


def test_two_funded_accounts_on_one_pdf_fail_closed():
    """The schema holds one account (L-1). Publishing either half alone would
    present a partial answer as a whole one."""
    second = _document(
        account="9900000000000002",
        starting="$50.00",
        deposits="$10.00",
        withdrawals="$0.00",
        ending="$60.00",
        rows="Jun 03, 2026 Jun 03, 2026 OTHER ACCOUNT ROW $10.00 $60.00\n",
        totals="$10.00",
    )
    assert sb.parse_shopify_balance_statement(_document() + second) is None


def test_a_second_block_with_money_but_no_rows_still_fails_closed():
    """Inertness is asserted on the printed figures, not just on row count."""
    second = _document(
        account="9900000000000002",
        starting="$50.00",
        deposits="$0.00",
        withdrawals="$0.00",
        ending="$50.00",
        rows="No transactions during this period.\n",
        totals=None,
    )
    assert sb.parse_shopify_balance_statement(_document() + second) is None


# ---------------------------------------------------------------------------
# the integrity check
# ---------------------------------------------------------------------------

def test_the_totals_row_agreeing_with_the_summary_raises_nothing():
    markdown = _document()
    stmt = sb.parse_shopify_balance_statement(markdown)
    assert sb.totals_contradictions(markdown, stmt) == []


def test_a_totals_net_that_contradicts_the_summary_is_reported():
    markdown = _document(totals="$999.00")
    stmt = sb.parse_shopify_balance_statement(markdown)
    flags = sb.totals_contradictions(markdown, stmt)
    assert flags and "Totals net" in flags[0]


def test_a_totals_closing_balance_that_contradicts_the_summary_is_reported():
    markdown = _document().replace(
        "$200.00 $1,200.00", "$200.00 $9,999.00"
    )
    stmt = sb.parse_shopify_balance_statement(markdown)
    flags = sb.totals_contradictions(markdown, stmt)
    assert any("closing balance" in flag for flag in flags)


def test_the_integrity_check_is_wired_to_the_registration():
    load()
    from analysis.parser_registry import registrations

    entry = next(r for r in registrations() if r.id == "shopify_balance")
    assert sb.totals_contradictions in entry.integrity_checks


def test_the_check_ignores_the_inert_block_which_prints_no_totals_row():
    markdown = _document() + _INERT_BLOCK
    stmt = sb.parse_shopify_balance_statement(markdown)
    assert sb.totals_contradictions(markdown, stmt) == []


# ---------------------------------------------------------------------------
# the shared date guard (analysis/dates.py)
# ---------------------------------------------------------------------------

def test_a_wrapped_totals_row_does_not_invent_a_posting_date():
    """`Totals Amount Account balance as of` / `06/30/2026` / figures: the
    bare date line is the total's own date, not an activity day."""
    from datetime import date

    from analysis.dates import source_posting_dates

    markdown = _document()
    found = source_posting_dates(markdown, date(2026, 6, 1), date(2026, 6, 30))
    assert date(2026, 6, 30) not in found


def test_the_coverage_heuristic_cannot_see_this_layouts_posting_rows():
    """Recorded, not celebrated. Every posting row of this grid prints TWO
    dates, and `_is_posting_row` treats a line carrying more than one date
    token as a balance grid rather than a posting. So `source_posting_dates`
    returns nothing here and `posting_dates_cover_source` is vacuously true:
    the wrapped `Totals` line was the ONLY line the heuristic could see, which
    is why suppressing it was enough to stop it inventing an activity day.

    What actually holds this family honest is the balance walk, which closes
    on every published row. Widening the heuristic to read two-date grids
    would touch every registration and is Ocean's call, not this cell's."""
    from datetime import date

    from analysis.dates import source_posting_dates

    assert source_posting_dates(_document(), date(2026, 6, 1), date(2026, 6, 30)) == set()


def test_a_bare_date_after_an_ordinary_line_is_still_a_posting_date():
    """The narrowing is keyed on a total's label OPENING the previous line;
    everything else keeps the existing money-proximity behaviour."""
    from datetime import date

    from analysis.dates import source_posting_dates

    markdown = "DEPOSITS AND CREDITS\n06/15/2026\nSOME MERCHANT 100.00\n"
    assert date(2026, 6, 15) in source_posting_dates(
        markdown, date(2026, 6, 1), date(2026, 6, 30)
    )


def test_a_merchant_named_total_does_not_suppress_the_next_posting_date():
    """An archive census found `... Total Quality Logi 180-05` above a real
    posting date. The word must OPEN the line to suppress anything."""
    from datetime import date

    from analysis.dates import source_posting_dates

    markdown = (
        "POS Debit- Business Debit Card 7853 06-08-26 Total Quality Logi 180-05\n"
        "06/09/2026\n"
        "SOME MERCHANT 42.00\n"
    )
    assert date(2026, 6, 9) in source_posting_dates(
        markdown, date(2026, 6, 1), date(2026, 6, 30)
    )


def test_a_column_header_ending_in_total_does_not_suppress_a_posting_date():
    from datetime import date

    from analysis.dates import source_posting_dates

    markdown = (
        "DATE DESCRIPTION CURRENCY AMOUNT FEES TOTAL*\n"
        "06/03/2026\n"
        "SOME MERCHANT 42.00\n"
    )
    assert date(2026, 6, 3) in source_posting_dates(
        markdown, date(2026, 6, 1), date(2026, 6, 30)
    )


def test_a_totals_label_that_prints_its_own_money_is_untouched():
    """Only a label whose figures WRAPPED suppresses the line below it."""
    from datetime import date

    from analysis.dates import source_posting_dates

    markdown = "Totals 1,234.56 7,890.12\n06/30/2026\nSOME MERCHANT 42.00\n"
    assert date(2026, 6, 30) in source_posting_dates(
        markdown, date(2026, 6, 1), date(2026, 6, 30)
    )


def test_the_published_statement_is_a_statement_object():
    stmt = sb.parse_shopify_balance_statement(_document())
    assert isinstance(stmt, Statement)
