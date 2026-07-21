from ocr.models import BBox, OCRWord, OCRLine, Transaction, AccountInfo, StatementResult

def test_bbox_geometry():
    b = BBox(10, 20, 30, 60)
    assert b.width == 20
    assert b.height == 40
    assert b.y_center == 40

def test_transaction_defaults():
    t = Transaction(date="2026-01-03", description="ACME", debit=10.0,
                    credit=None, balance=90.0, raw_line="01/03 ACME 10.00 90.00")
    assert t.credit is None
    assert t.debit == 10.0

def test_statement_result_holds_parts():
    r = StatementResult(
        account_info=AccountInfo(bank="chase"),
        transactions=[],
        raw_text=["page one"],
        meta={"page_count": 1},
    )
    assert r.account_info.bank == "chase"
    assert r.raw_text == ["page one"]
