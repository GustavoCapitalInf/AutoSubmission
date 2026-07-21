from ocr.models import OCRWord, BBox
from ocr.grouping import group_words_into_lines
from ocr.profiles.base import GenericProfile

def _line(text, y):
    # Build a line whose words carry increasing x so ordering is stable.
    words = []
    x = 0
    for tok in text.split():
        words.append(OCRWord(tok, BBox(x, y, x + 10 * len(tok), y + 10), 1.0))
        x += 10 * len(tok) + 10
    return words

def test_generic_parses_dated_money_line():
    words = _line("02/03 ZELLE PAYMENT DEPOSIT 250.00 984.56", 10)
    lines = group_words_into_lines(words)
    txns = GenericProfile().parse_transactions(lines, year_hint=2026)
    assert len(txns) == 1
    t = txns[0]
    assert t.date == "2026-02-03"
    assert t.balance == 984.56
    assert t.credit == 250.00        # "deposit" → credit
    assert t.debit is None

def test_generic_skips_non_transaction_line():
    words = _line("Beginning balance on statement", 10)
    lines = group_words_into_lines(words)
    assert GenericProfile().parse_transactions(lines, year_hint=2026) == []
