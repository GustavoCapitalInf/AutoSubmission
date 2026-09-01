"""OQ2 = YES: `INTAKE_FURNITURE` is the ONLY sanctioned home for issuer-named
intake behavior in `ocr/`. These behaviors choose WHICH PIXELS ARE READ (page
selection / render variant), never what a value means.

`tests/test_no_statement_hardcodes.py`'s OCR_DIR scan is the GUARD (it fails
if an issuer-named regex exists in `ocr/ocr_client.py`, `ocr/pipeline.py` or
`ocr/render.py` without a matching register entry). This file pins what each
DECLARED entry actually does: the masked rectangle is a fixed fraction of the
page, the render variants are (dpi, mask) pairs, and neither the TD detector
nor the masking function can read or write a money token.
"""
from __future__ import annotations

import inspect

from PIL import Image

from ocr.ocr_client import (
    INTAKE_FURNITURE,
    _TD_MARKERS_RE,
    _TD_RECOVERY_VARIANTS,
    _mask_qr,
    is_td_statement,
)


def test_intake_furniture_covers_every_declared_behavior():
    expected = {"_TD_MARKERS_RE", "_TD_RECOVERY_VARIANTS", "_mask_qr", "looks_missegmented"}
    assert set(INTAKE_FURNITURE) == expected


def test_every_entry_names_issuer_behavior_justification_scope_and_pin():
    required_fields = {"issuer", "behavior", "justification", "scope", "pinned_by"}
    for name, entry in INTAKE_FURNITURE.items():
        missing = required_fields - entry.keys()
        assert not missing, f"{name}: INTAKE_FURNITURE entry missing {missing}"
        assert entry["behavior"], f"{name}: behavior must not be empty"
        assert entry["justification"], f"{name}: justification must not be empty"
        assert entry["scope"], f"{name}: scope must not be empty"
        assert entry["pinned_by"], f"{name}: pinned_by must not be empty"


def test_only_td_entries_name_an_issuer():
    # looks_missegmented is structural (a mis-segmentation SHAPE), not tied to
    # any named issuer -- its entry must say so explicitly.
    assert INTAKE_FURNITURE["_TD_MARKERS_RE"]["issuer"] == "TD"
    assert INTAKE_FURNITURE["_TD_RECOVERY_VARIANTS"]["issuer"] == "TD"
    assert INTAKE_FURNITURE["_mask_qr"]["issuer"] == "TD"
    assert INTAKE_FURNITURE["looks_missegmented"]["issuer"] is None


def test_td_recovery_variants_are_dpi_mask_pairs():
    assert len(_TD_RECOVERY_VARIANTS) >= 1
    for variant in _TD_RECOVERY_VARIANTS:
        assert isinstance(variant, tuple) and len(variant) == 2
        dpi, mask = variant
        assert isinstance(dpi, int) and dpi > 0
        assert isinstance(mask, bool)


def test_mask_qr_cannot_depend_on_a_printed_figure_by_signature():
    """Structural proof, not a promise: `_mask_qr` takes only an image. It has
    no parameter through which a printed money token could ever reach it."""
    sig = inspect.signature(_mask_qr)
    params = list(sig.parameters)
    assert params == ["image"], (
        f"_mask_qr must take only an image (no text channel that could carry "
        f"a printed figure into a masking decision): got {params}"
    )


def test_mask_qr_masks_only_the_declared_fixed_fraction():
    """60-100% width x 0-12% height, exactly, regardless of image content."""
    w, h = 1000, 1300
    img = Image.new("RGB", (w, h), (10, 20, 30))
    out = _mask_qr(img)
    assert out.size == img.size

    def is_white(x, y):
        return out.getpixel((x, y)) == (255, 255, 255)

    # Inside the declared rectangle (60-100% x, 0-12% y): must be masked white.
    assert is_white(int(w * 0.80), int(h * 0.05))
    assert is_white(w - 1, 0)
    # Just outside each edge of the rectangle: must be UNCHANGED (never masks
    # the body/table region where printed financial figures live).
    assert not is_white(int(w * 0.59), int(h * 0.05))   # left of the rectangle
    assert not is_white(int(w * 0.80), int(h * 0.13))   # below the rectangle
    assert not is_white(0, 0)                            # top-left corner (title area)
    assert not is_white(int(w * 0.10), int(h * 0.90))   # body/table region


def test_mask_qr_never_reads_the_page_text():
    """A mutant that makes `_mask_qr` depend on the page's content is killed:
    the function's only input is pixels, and the masked rectangle's position
    and color never vary with what those pixels depict -- two visually
    different images of the SAME size mask to the identical white rectangle,
    and nothing outside it changes."""
    a = Image.new("RGB", (800, 1000), (0, 0, 0))
    b = Image.new("RGB", (800, 1000), (255, 0, 255))
    out_a, out_b = _mask_qr(a), _mask_qr(b)
    box = (int(800 * 0.60), 0, 800, int(1000 * 0.12))
    pixel_count = (box[2] - box[0]) * (box[3] - box[1])
    assert out_a.crop(box).getcolors() == [(pixel_count, (255, 255, 255))]
    assert out_b.crop(box).getcolors() == [(pixel_count, (255, 255, 255))]
    # Outside the rectangle, each image keeps ITS OWN original color.
    assert out_a.getpixel((10, int(1000 * 0.90))) == (0, 0, 0)
    assert out_b.getpixel((10, int(1000 * 0.90))) == (255, 0, 255)


def test_td_markers_detect_only_named_printed_furniture():
    assert is_td_statement("TD Bank America's Most Convenient Bank")
    assert is_td_statement("TD Business Direct Deposit")
    assert not is_td_statement("Chase Bank Statement")
    # The detector is a plain substring/regex match over TEXT -- it has no
    # channel to a money value either (same structural argument as _mask_qr,
    # stated for the text-side half of the TD furniture).
    sig = inspect.signature(is_td_statement)
    assert list(sig.parameters) == ["text"]
