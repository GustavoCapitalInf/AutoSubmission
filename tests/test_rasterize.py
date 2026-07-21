from PIL import Image
from ocr.rasterize import rasterize_pdf

def test_rasterize_returns_images(sample_pdf):
    pages = rasterize_pdf(sample_pdf.read_bytes(), dpi=150)
    assert len(pages) >= 1
    assert all(isinstance(p, Image.Image) for p in pages)
    assert pages[0].width > 0 and pages[0].height > 0
