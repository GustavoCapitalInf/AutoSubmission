from decimal import Decimal

from vlm import proposals as pp
from vlm.schema import empty_proposal


def _page(role="statement_page", rows=(), currency="USD", begin=500.0, end=None, last4="0001", **account):
    p = empty_proposal(role)
    p["account"].update({"currency": currency, "beginning_balance": begin, "ending_balance": end,
                         "period_start": "2031-01-01", "period_end": "2031-01-31", "account_number_last4": last4, **account})
    p["rows"] = list(rows)
    return p


def _row(date="2031-01-01", amount=10.0, direction="credit", balance=510.0, text="01/01", cont=False, desc="SYNTHETIC ROW 01"):
    return {"date": date, "date_text": text, "description": desc, "amount": amount, "direction": direction,
            "balance": balance, "continues_previous": cont}


def test_rows_from_proposal_parses_and_reparses_dates():
    rows, drops = pp.rows_from_proposal(_page(rows=[_row(date=None, text="01/02"), _row(amount=0.0)]), page=3, year_hint=2031)
    assert len(rows) == 1 and rows[0].date == "2031-01-02" and rows[0].page == 3 and rows[0].source == "stage_b"
    assert rows[0].amount == Decimal("10.00") and rows[0].locator == "p3r0" and drops["nonpositive"] == 1


def test_continuation_without_amount_merges_and_with_amount_is_kept():
    rows, drops = pp.rows_from_proposal(_page(rows=[_row(), _row(cont=True, desc="MORE TEXT", amount=0.0)]), page=0)
    assert len(rows) == 1 and rows[0].description == "SYNTHETIC ROW 01 MORE TEXT" and drops["continuation_merged"] == 1
    rows, drops = pp.rows_from_proposal(_page(rows=[_row(), _row(cont=True, desc="DEPOSIT TWO", amount=50.0, balance=560.0)]), page=0)
    assert len(rows) == 2 and rows[1].amount == Decimal("50.00") and drops["continuation_with_amount"] == 1


def test_meta_from_proposal_carries_printed_totals_and_counts():
    meta = pp.meta_from_proposal(_page(stated_total_credits=360.0, stated_total_debits=-12.5, stated_credit_count=8, stated_debit_count=1))
    assert meta.stated_total_credits == Decimal("360.00") and meta.stated_total_debits == Decimal("12.50")
    assert meta.stated_credit_count == 8 and meta.stated_debit_count == 1 and "meta:stage_b" in meta.sources


def test_merge_pages_roles_meta_and_conflicts_without_digits_in_stats():
    pages = [pp.PageProposal(0, _page("cover_or_notice", begin=None), ()),
             pp.PageProposal(1, _page(rows=[_row()], end=None), ()),
             pp.PageProposal(2, _page(rows=[_row(date="2031-01-05", balance=520.0)], currency="CAD", end=520.0, last4="4821"), ()),
             pp.PageProposal(3, {"broken": True}, ("<root>: 'page_role' is a required property",))]
    rows, meta, stats = pp.merge_pages(pages)
    assert [r.page for r in rows] == [1, 2]
    assert meta.beginning_balance == Decimal("500.00") and meta.ending_balance == Decimal("520.00") and meta.currency == "USD"
    assert stats["pages_by_role"] == {"cover_or_notice": 1, "invalid": 1, "statement_page": 2}
    assert stats["currency_conflict"] is True and stats["invalid_pages"] == 1
    assert stats["account_last4_count"] == 2 and "account_last4_set_sha256" not in stats
    assert "0001" not in str(stats) and "4821" not in str(stats)
    assert stats["rows_dropped_nonpositive"] == 0 and stats["continuation_rows_with_amount"] == 0


def test_period_year_overrides_a_model_year_when_the_text_prints_none():
    rows, _ = pp.rows_from_proposal(_page(rows=[_row(date="2024-01-05", text="01/05")]), page=0, year_hint=2031)
    assert rows[0].date == "2031-01-05"
    rows, _ = pp.rows_from_proposal(_page(rows=[_row(date="2024-01-05", text="01/05/2024")]), page=0, year_hint=2031)
    assert rows[0].date == "2024-01-05"   # the text prints its own year: the model's date stands
    rows, _ = pp.rows_from_proposal(_page(rows=[_row(date="2024-01-05", text="01/05/24")]), page=0, year_hint=2031)
    assert rows[0].date == "2024-01-05"


def test_unprinted_year_outside_the_period_snaps_into_the_period_window():
    assert pp.year_into_period("2029-01-05", "2031-01-01", "2031-01-31") == "2031-01-05"
    assert pp.year_into_period("2031-01-05", "2031-01-01", "2031-01-31") == "2031-01-05"
    assert pp.year_into_period("2029-06-05", "2031-01-01", "2031-01-31") == "2029-06-05"   # no year fits: left alone
    assert pp.year_into_period("2029-01-05", None, "2031-01-31") == "2029-01-05"
    # CTRL wave: a month name the text parser cannot read, model year two years off.
    rows, _ = pp.rows_from_proposal(_page(rows=[_row(date="2029-01-05", text="5 janv")]), page=0, year_hint=2031,
                                    period=("2031-01-01", "2031-01-31"))
    assert rows[0].date == "2031-01-05"
    # A period that crosses the year takes the year that fits.
    rows, _ = pp.rows_from_proposal(_page(rows=[_row(date="2029-12-30", text="30 dec")]), page=0, year_hint=2031,
                                    period=("2030-12-01", "2031-01-05"))
    assert rows[0].date == "2030-12-30"
    # A printed year is evidence and stays, even outside the period.
    rows, _ = pp.rows_from_proposal(_page(rows=[_row(date="2029-01-05", text="05/01/2029")]), page=0, year_hint=2031,
                                    period=("2031-01-01", "2031-01-31"))
    assert rows[0].date == "2029-01-05"
    # merge_pages passes the merged period through.
    rows, meta, _ = pp.merge_pages([pp.PageProposal(0, _page(rows=[_row(date="2029-01-05", text="5 janv")]), ())])
    assert rows[0].date == "2031-01-05" and meta.period_end == "2031-01-31"
