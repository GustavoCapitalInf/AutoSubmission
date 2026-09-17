from decimal import Decimal

from vlm import proposals as pp
from vlm.schema import empty_proposal


def _page(role="statement_page", rows=(), currency="USD", begin=500.0, end=None, last4="0001"):
    p = empty_proposal(role)
    p["account"].update({"currency": currency, "beginning_balance": begin, "ending_balance": end,
                         "period_start": "2031-01-01", "period_end": "2031-01-31", "account_number_last4": last4})
    p["rows"] = list(rows)
    return p


def _row(date="2031-01-01", amount=10.0, direction="credit", balance=510.0, text="01/01", cont=False, desc="SYNTHETIC ROW 01"):
    return {"date": date, "date_text": text, "description": desc, "amount": amount, "direction": direction,
            "balance": balance, "section_index": None, "continues_previous": cont, "box": None}


def test_rows_from_proposal_parses_and_reparses_dates():
    rows = pp.rows_from_proposal(_page(rows=[_row(date=None, text="01/02"), _row(amount=0.0)]), page=3, year_hint=2031)
    assert len(rows) == 1 and rows[0].date == "2031-01-02" and rows[0].page == 3 and rows[0].source == "stage_b"
    assert rows[0].amount == Decimal("10.00") and rows[0].locator == "p3r0"


def test_continuation_rows_merge():
    rows = pp.rows_from_proposal(_page(rows=[_row(), _row(cont=True, desc="MORE TEXT", amount=1.0)]), page=0)
    assert len(rows) == 1 and rows[0].description == "SYNTHETIC ROW 01 MORE TEXT"


def test_merge_pages_roles_meta_and_conflicts():
    pages = [pp.PageProposal(0, _page("cover_or_notice", begin=None), ()),
             pp.PageProposal(1, _page(rows=[_row()], end=None), ()),
             pp.PageProposal(2, _page(rows=[_row(date="2031-01-05", balance=520.0)], currency="CAD", end=520.0), ()),
             pp.PageProposal(3, {"broken": True}, ("<root>: 'page_role' is a required property",))]
    rows, meta, stats = pp.merge_pages(pages)
    assert [r.page for r in rows] == [1, 2]
    assert meta.beginning_balance == Decimal("500.00") and meta.ending_balance == Decimal("520.00") and meta.currency == "USD"
    assert stats["pages_by_role"] == {"cover_or_notice": 1, "invalid": 1, "statement_page": 2}
    assert stats["currency_conflict"] is True and stats["invalid_pages"] == 1 and stats["account_last4_values"] == ["0001"]
    assert "meta:stage_b" in meta.sources
