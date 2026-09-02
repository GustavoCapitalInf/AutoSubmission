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
    looks_truncated_td,
    recover_truncated_td_page,
)
from tests.test_no_statement_hardcodes import ISSUER_NAME_LEXICON, ISSUER_MARKERS_BY_ISSUER


def test_intake_furniture_covers_every_declared_behavior():
    # Review MAJOR-4: the register omitted the two behaviors that select
    # among candidate reads by document content; now seven entries.
    expected = {
        "_TD_MARKERS_RE", "is_td_statement", "looks_truncated_td",
        "_TD_RECOVERY_VARIANTS", "recover_truncated_td_page",
        "_mask_qr", "looks_missegmented",
    }
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
    assert INTAKE_FURNITURE["is_td_statement"]["issuer"] == "TD"
    assert INTAKE_FURNITURE["looks_truncated_td"]["issuer"] == "TD"
    assert INTAKE_FURNITURE["_TD_RECOVERY_VARIANTS"]["issuer"] == "TD"
    assert INTAKE_FURNITURE["recover_truncated_td_page"]["issuer"] == "TD"
    assert INTAKE_FURNITURE["_mask_qr"]["issuer"] == "TD"
    assert INTAKE_FURNITURE["looks_missegmented"]["issuer"] is None


def test_two_entries_declare_they_select_among_candidate_reads():
    """Review MAJOR-4: `_TD_RECOVERY_VARIANTS` and `looks_missegmented` do not
    only pick a render parameter -- they select which of several candidate
    OCR reads survives. The register must say so, accurately: keyed on a
    printed structural caption / a table-shape signature, never a figure."""
    for name in ("_TD_RECOVERY_VARIANTS", "looks_missegmented"):
        scope = INTAKE_FURNITURE[name]["scope"]
        assert "candidate" in scope.lower(), f"{name}: scope does not declare candidate-read selection"
        assert "never on a printed figure" in scope, f"{name}: scope does not disclaim figure-dependence"


def _resolve_regex_subjects():
    """Review MINOR-R2: every `INTAKE_FURNITURE` key that resolves, on
    `ocr.ocr_client`, to an object carrying a `.pattern` (a compiled regex) --
    not a name hardcoded to `_TD_MARKERS_RE`. A future registered entry whose
    subject is also a compiled regex is picked up automatically; one whose
    subject is a function, a list, or anything else without `.pattern` is
    correctly excluded (it has no "pattern text" for this check to read)."""
    import ocr.ocr_client as ocr_client_module

    subjects = {}
    for name in INTAKE_FURNITURE:
        obj = getattr(ocr_client_module, name, None)
        if hasattr(obj, "pattern"):
            subjects[name] = obj
    return subjects


def test_registered_regex_pattern_matches_its_declared_issuer_and_no_other():
    """Review MAJOR-3 (+ MINOR-R2): a registered NAME is not a blanket
    licence for every other issuer. For every register entry whose subject is
    a compiled regex with a non-None issuer, the pattern text must contain
    THAT issuer's own markers (looked up from `ISSUER_MARKERS_BY_ISSUER`, not
    re-hardcoded here) and no marker belonging to a different institution.

    Mutant K, applied directly (not only via the mutation campaign against
    the real file): widening `_TD_MARKERS_RE` to a second issuer must fail
    this exact check."""
    regex_subjects = _resolve_regex_subjects()
    assert regex_subjects, "no compiled-regex subject resolved from INTAKE_FURNITURE -- vacuous check"
    for name, compiled in regex_subjects.items():
        entry = INTAKE_FURNITURE[name]
        if entry["issuer"] is None:
            continue
        own_markers = ISSUER_MARKERS_BY_ISSUER.get(entry["issuer"])
        assert own_markers, f"{entry['issuer']!r} has no entry in ISSUER_MARKERS_BY_ISSUER"
        pattern_low = compiled.pattern.lower()
        own_markers_present = [m for m in own_markers if m in pattern_low]
        assert own_markers_present, f"{name}: pattern carries none of its declared issuer's own markers"
        other_markers_present = [
            m for m in ISSUER_NAME_LEXICON
            if m not in own_markers and m in pattern_low
        ]
        assert not other_markers_present, (
            f"{name}: registered issuer is {entry['issuer']!r} but the pattern "
            f"also matches other institutions: {other_markers_present}"
        )


def test_registered_regex_check_actually_catches_a_second_issuer(monkeypatch):
    """Mutant K, applied to the real compiled pattern object (not a copy):
    widen `_TD_MARKERS_RE` with a second issuer and confirm the check above
    would fail."""
    import re
    import ocr.ocr_client as ocr_client_module

    widened = re.compile(
        r"most convenient bank|td business|\btd bank\b|wells fargo",
        re.IGNORECASE,
    )
    monkeypatch.setattr(ocr_client_module, "_TD_MARKERS_RE", widened)
    td_markers = ISSUER_MARKERS_BY_ISSUER["TD"]
    pattern_low = ocr_client_module._TD_MARKERS_RE.pattern.lower()
    other_markers_present = [
        m for m in ISSUER_NAME_LEXICON if m not in td_markers and m in pattern_low
    ]
    assert other_markers_present == ["wells fargo"], (
        "the widened pattern must be caught as carrying a second issuer's marker"
    )


def test_is_td_statement_false_for_every_other_institution_in_the_lexicon():
    """Review MINOR-R1: the exclusivity check above tests full-marker
    substring containment; a SHORTER, bare word-boundary prefix of another
    institution's marker folded into `_TD_MARKERS_RE` would not contain any
    FULL lexicon marker and would slip past it. The only reliable check is
    behavioral: sweep every non-TD institution in the lexicon and confirm
    `is_td_statement` says no for each one's own printed text, rather than
    relying on whichever banks happen to have an incidental negative test
    elsewhere (mutant U died only because Chase already had one; mutant W,
    for an institution with no such test, survived the first pass)."""
    td_own = ISSUER_MARKERS_BY_ISSUER["TD"]
    for marker in ISSUER_NAME_LEXICON:
        if marker in td_own:
            continue
        assert not is_td_statement(f"{marker} statement of account"), (
            f"is_td_statement matched a non-TD institution's own marker: {marker!r}"
        )


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


def test_looks_truncated_td_keyed_on_a_structural_caption_only():
    """`looks_truncated_td` (now registered, review MAJOR-4) is the
    text-side half of the QR-derailment detector: present banner, absent
    caption. No numeric comparison of any kind participates."""
    truncated = "TD Bank STATEMENT OF ACCOUNT\nCust Ref #: 826-713"
    full = "TD Bank STATEMENT OF ACCOUNT\nACCOUNT SUMMARY\nBeginning Balance $999,999.00"
    assert looks_truncated_td(truncated)
    assert not looks_truncated_td(full)
    sig = inspect.signature(looks_truncated_td)
    assert list(sig.parameters) == ["text"]


def test_recover_truncated_td_page_selects_by_caption_not_by_figure(monkeypatch):
    """Review MAJOR-4's own characterization, proven: `recover_truncated_td_page`
    selects which of several candidate re-OCR reads survives on a printed
    structural section caption alone -- never on which read prints a
    'larger', 'smaller', or otherwise more plausible figure. Here the FIRST
    four candidate variants print an implausibly large balance and are still
    truncated (no ACCOUNT SUMMARY); the LAST variant tried recovers the
    caption with a much smaller balance, and it is the one kept."""
    import ocr.ocr_client as ocr_client_module

    def fake_rasterize_page(pdf_bytes, page_index, dpi):
        return f"img@{dpi}"

    def fake_ocr_page(image, *, settings, client, on_delta=None):
        if image == "img@150":  # the last variant in _TD_RECOVERY_VARIANTS
            return ("TD Bank STATEMENT OF ACCOUNT\nACCOUNT SUMMARY\n"
                     "Beginning Balance $1.00")
        return "TD Bank STATEMENT OF ACCOUNT\nBeginning Balance $999,999.00"

    monkeypatch.setattr("ocr.rasterize.rasterize_page", fake_rasterize_page)
    monkeypatch.setattr(ocr_client_module, "ocr_page", fake_ocr_page)
    monkeypatch.setattr(ocr_client_module, "_mask_qr", lambda img: img)

    out = ocr_client_module.recover_truncated_td_page(
        b"%PDF-fake", 0, settings=object(), client=object()
    )
    assert out is not None
    assert "$1.00" in out
    assert "999,999" not in out


def test_recover_truncated_td_page_returns_none_when_nothing_recovers(monkeypatch):
    import ocr.ocr_client as ocr_client_module

    monkeypatch.setattr("ocr.rasterize.rasterize_page", lambda pdf, i, dpi: "img")
    monkeypatch.setattr(ocr_client_module, "ocr_page",
                        lambda image, *, settings, client, on_delta=None:
                        "TD Bank STATEMENT OF ACCOUNT\nCust Ref #: 826-713")
    monkeypatch.setattr(ocr_client_module, "_mask_qr", lambda img: img)
    out = ocr_client_module.recover_truncated_td_page(
        b"%PDF-fake", 0, settings=object(), client=object()
    )
    assert out is None
