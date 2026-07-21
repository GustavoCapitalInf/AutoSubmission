from __future__ import annotations
from .models import OCRWord, OCRLine, BBox

def group_words_into_lines(words: list[OCRWord], y_tol: float = 6.0) -> list[OCRLine]:
    remaining = sorted(words, key=lambda w: w.bbox.y_center)
    lines: list[OCRLine] = []
    for w in remaining:
        placed = False
        for ln in lines:
            if abs(w.bbox.y_center - ln.y_center) <= y_tol:
                ln.words.append(w)
                ln.y_center = sum(x.bbox.y_center for x in ln.words) / len(ln.words)
                placed = True
                break
        if not placed:
            lines.append(OCRLine(text="", words=[w], bbox=None, y_center=w.bbox.y_center))
    for ln in lines:
        ln.words.sort(key=lambda w: w.bbox.x0)
        ln.text = " ".join(w.text for w in ln.words)
        ln.bbox = BBox(
            min(w.bbox.x0 for w in ln.words),
            min(w.bbox.y0 for w in ln.words),
            max(w.bbox.x1 for w in ln.words),
            max(w.bbox.y1 for w in ln.words),
        )
    lines.sort(key=lambda l: l.y_center)
    return lines

def words_in_x_range(line: OCRLine, x0: float, x1: float) -> list[OCRWord]:
    out = []
    for w in line.words:
        cx = (w.bbox.x0 + w.bbox.x1) / 2.0
        if x0 <= cx < x1:
            out.append(w)
    return out

def text_in_x_range(line: OCRLine, x0: float, x1: float) -> str:
    return " ".join(w.text for w in words_in_x_range(line, x0, x1))
