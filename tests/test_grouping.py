from ocr.models import OCRWord, BBox
from ocr.grouping import group_words_into_lines, words_in_x_range, text_in_x_range

def _w(text, x0, y0, x1, y1):
    return OCRWord(text=text, bbox=BBox(x0, y0, x1, y1), confidence=1.0)

def test_group_words_into_lines_orders_and_joins():
    words = [
        _w("World", 60, 21, 90, 39),
        _w("Hello", 10, 20, 50, 40),      # same row as World
        _w("Next", 10, 80, 50, 100),      # lower row
    ]
    lines = group_words_into_lines(words, y_tol=6)
    assert len(lines) == 2
    assert lines[0].text == "Hello World"   # sorted left→right, top row first
    assert lines[1].text == "Next"

def test_words_in_x_range_uses_center():
    line = group_words_into_lines([
        _w("DATE", 0, 0, 40, 10),
        _w("DESC", 100, 0, 200, 10),
        _w("9.99", 300, 0, 340, 10),
    ])[0]
    assert text_in_x_range(line, 90, 250) == "DESC"
    assert text_in_x_range(line, 280, 400) == "9.99"
    assert [w.text for w in words_in_x_range(line, 0, 90)] == ["DATE"]
