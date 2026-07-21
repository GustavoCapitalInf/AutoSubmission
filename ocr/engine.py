from __future__ import annotations
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from .models import BBox, OCRWord

_reader: PaddleOCR | None = None

def get_reader() -> PaddleOCR:
    global _reader
    if _reader is None:
        _reader = PaddleOCR(use_textline_orientation=True, lang="en", enable_mkldnn=False)
    return _reader

def words_from_paddle_result(result_dict: dict) -> list[OCRWord]:
    """Adapt one page's PaddleOCR 3.x result dict into OCRWords."""
    texts = result_dict.get("rec_texts", []) or []
    scores = result_dict.get("rec_scores", []) or []
    polys = result_dict.get("rec_polys", []) or []
    words: list[OCRWord] = []
    for i, text in enumerate(texts):
        poly = polys[i]
        xs = [pt[0] for pt in poly]
        ys = [pt[1] for pt in poly]
        bbox = BBox(min(xs), min(ys), max(xs), max(ys))
        conf = float(scores[i]) if i < len(scores) else 1.0
        words.append(OCRWord(text=str(text), bbox=bbox, confidence=conf))
    return words

def _extract_res(predict_output) -> dict:
    """Normalize PaddleOCR.predict() output for one page into a plain dict."""
    item = predict_output[0]
    data = getattr(item, "json", None)
    if isinstance(data, dict):
        return data.get("res", data)
    # Mapping-style result object
    return item["res"] if "res" in item else dict(item)

def ocr_image(image: Image.Image) -> list[OCRWord]:
    reader = get_reader()
    arr = np.array(image.convert("RGB"))
    output = reader.predict(arr)
    return words_from_paddle_result(_extract_res(output))
