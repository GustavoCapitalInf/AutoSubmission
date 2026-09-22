"""Bounded, receiptable Stage A crop recovery; model calls belong to the caller.

Two overlapping horizontal crops may supplement a failed full-page proposal only
when BOTH crops yield complete valid layouts with mappable geometry or their
decoded source pixels are proven exactly RGB white. Cropping
does not validate any row. Every recovered candidate, including partial rows
and overlapping duplicates, must be reviewed against the original full image.
No source value is repaired, no row is deduplicated, and no gate runs here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal
import io
import math
from pathlib import Path
import re
from typing import Callable

import PIL
from PIL import Image

from vlm.assemble import Block, CandidateRow, DotsLayout
from vlm.receipts import canonical_json, sha256_bytes, sha256_file

RECOVERY_VERSION = 2
RECOVERY_GENERATION = 1
_RECOVERABLE_ERRORS = (
    "stage_a_truncated", "layout_invalid_json", "layout_not_array",
    "layout_unsupported_svg", "layout_element_invalid", "layout_box_invalid",
)


class ProposalRecoveryError(ValueError):
    """Fixed, content-free recovery failure suitable for private audit codes."""


def proposal_recovery_manifest() -> dict:
    """Every crop/configuration/source change creates distinct cache material."""
    return {
        "version": RECOVERY_VERSION,
        "generation": RECOVERY_GENERATION,
        "method": "two_horizontal_overlapping_crops",
        "maximum_crop_calls": 2,
        "empty_region_proof": {
            "method": "exact_rgb_white",
            "pixel_stage": "decoded_source_jpeg_before_crop_reencoding",
            "required_channel_extrema": [[255, 255], [255, 255], [255, 255]],
            "threshold_or_variance": False,
        },
        "vertical_fraction_numerators": [[0, 56], [44, 100]],
        "vertical_fraction_denominator": 100,
        "pixel_rounding": {"top_end": "ceil", "bottom_start": "floor"},
        "full_width": True,
        "resize": False,
        "enhancement": False,
        "jpeg_quality": 90,
        "jpeg_subsampling": 0,
        "jpeg_optimize": False,
        "jpeg_progressive": False,
        "normalized_coordinate_decimals": 6,
        "deduplicate": False,
        "review_image": "original_full_page",
        "pillow_version": PIL.__version__,
        "source_sha256": sha256_file(Path(__file__)),
    }


def needs_proposal_recovery(layout: DotsLayout) -> bool:
    return layout.truncated or any(
        error.split(":", 1)[0] in _RECOVERABLE_ERRORS for error in layout.errors)


@dataclass(frozen=True)
class ProposalCrop:
    page: int
    index: int
    width: int
    height: int
    source_width: int
    source_height: int
    bounds_px: tuple[int, int, int, int]
    bbox_fullpage: tuple[float, float, float, float]
    jpeg: bytes
    jpeg_sha256: str
    pixel_sha256: str
    source_jpeg_sha256: str
    config_sha256: str
    source_rgb_extrema: tuple[tuple[int, int], ...]
    generation: int = RECOVERY_GENERATION

    @property
    def locator_prefix(self) -> str:
        return f"g{self.generation}c{self.index}/"

    def metadata(self) -> dict:
        return {key: value for key, value in asdict(self).items() if key != "jpeg"}


@dataclass(frozen=True)
class ProposalRecovery:
    layout: DotsLayout
    attempted: bool
    recovered: bool
    audit: dict
    crops: tuple[ProposalCrop, ...] = ()


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return {"invalid_number": "nan" if math.isnan(value) else
                "positive_infinity" if value > 0 else "negative_infinity"}
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _layout_record(layout: DotsLayout) -> dict:
    # Full private source evidence is retained; no model text enters exceptions.
    return _jsonable(asdict(layout))


def _crops(jpeg: bytes, page: int, config_sha256: str) -> tuple[ProposalCrop, ...]:
    if not isinstance(jpeg, bytes) or not jpeg.startswith(b"\xff\xd8\xff"):
        raise ProposalRecoveryError("proposal_recovery_jpeg_required")
    try:
        with Image.open(io.BytesIO(jpeg)) as opened:
            if opened.format != "JPEG":
                raise ProposalRecoveryError("proposal_recovery_jpeg_required")
            opened.load()
            image = opened.convert("RGB")
    except (OSError, ValueError):
        raise ProposalRecoveryError("proposal_recovery_image_invalid") from None
    width, height = image.size
    if width < 1 or height < 2:
        image.close()
        raise ProposalRecoveryError("proposal_recovery_image_too_small")
    bounds = ((0, 0, width, (height * 56 + 99) // 100),
              (0, (height * 44) // 100, width, height))
    source_sha = sha256_bytes(jpeg)
    result = []
    try:
        for index, box in enumerate(bounds):
            cropped = image.crop(box)
            try:
                buffer = io.BytesIO()
                cropped.save(buffer, format="JPEG", quality=90, subsampling=0,
                             optimize=False, progressive=False)
                raw = buffer.getvalue()
                result.append(ProposalCrop(
                    page=page, index=index, width=cropped.width, height=cropped.height,
                    source_width=width, source_height=height, bounds_px=box,
                    bbox_fullpage=(0.0, box[1] / height, 1.0, box[3] / height),
                    jpeg=raw, jpeg_sha256=sha256_bytes(raw),
                    pixel_sha256=sha256_bytes(cropped.tobytes()),
                    source_jpeg_sha256=source_sha, config_sha256=config_sha256,
                    source_rgb_extrema=cropped.getextrema()))
            finally:
                cropped.close()
    finally:
        image.close()
    return tuple(result)


def _map_box(box, crop: ProposalCrop) -> tuple[float, float, float, float]:
    if (not isinstance(box, (tuple, list)) or len(box) != 4
            or any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) for value in box)
            or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)):
        raise ProposalRecoveryError("proposal_recovery_unmappable_box")
    x0, y0, x1, y1 = crop.bounds_px
    mapped = tuple(round(value, 6) for value in (
        (x0 + box[0] * (x1 - x0)) / crop.source_width,
        (y0 + box[1] * (y1 - y0)) / crop.source_height,
        (x0 + box[2] * (x1 - x0)) / crop.source_width,
        (y0 + box[3] * (y1 - y0)) / crop.source_height))
    if not (mapped[0] < mapped[2] and mapped[1] < mapped[3]):
        raise ProposalRecoveryError("proposal_recovery_unmappable_box")
    return mapped


def _map_layout(layout: DotsLayout, crop: ProposalCrop, *, block_offset: int) -> tuple[DotsLayout, dict]:
    if layout.page != crop.page or any(item.page != crop.page for item in (*layout.blocks, *layout.rows)):
        raise ProposalRecoveryError("proposal_recovery_page_mismatch")
    block_orders = [block.order for block in layout.blocks]
    row_locators = [row.locator for row in layout.rows]
    if len(block_orders) != len(set(block_orders)) or len(row_locators) != len(set(row_locators)):
        raise ProposalRecoveryError("proposal_recovery_duplicate_locator")
    mapped_blocks, block_lineage, mapped_rows, row_lineage = [], [], [], []
    for index, block in enumerate(layout.blocks):
        mapped = replace(block, bbox=_map_box(block.bbox, crop), order=block_offset + index)
        mapped_blocks.append(mapped)
        block_lineage.append({"fullpage_order": mapped.order, "crop_order": block.order,
                              "crop_index": crop.index})
    for row in layout.rows:
        if not isinstance(row.locator, str) or not row.locator:
            raise ProposalRecoveryError("proposal_recovery_locator_invalid")
        mapped = replace(row, bbox=_map_box(row.bbox, crop),
                         locator=crop.locator_prefix + row.locator, source="stage_a_recovery")
        mapped_rows.append(mapped)
        # A table box may touch the crop boundary even when individual rows
        # do not. This is a warning for full-image review, never proof of a cut.
        touches_cut = ((crop.bounds_px[1] > 0 and row.bbox[1] == 0)
                       or (crop.bounds_px[3] < crop.source_height and row.bbox[3] == 1))
        row_lineage.append({"locator": mapped.locator, "crop_locator": row.locator,
                            "crop_index": crop.index, "box_touches_cut_boundary": touches_cut,
                            "requires_full_page_review": True})
    mapped = DotsLayout(crop.page, tuple(mapped_blocks), tuple(mapped_rows), (), False, layout.warnings)
    return mapped, {"blocks": block_lineage, "rows": row_lineage}


def _held_crop_rows(layout: DotsLayout, crop: ProposalCrop, reason: str) -> tuple[tuple[CandidateRow, ...], dict]:
    """Retain every parsed proposal for B even when its crop cannot recover.

    Trusted crop/request provenance establishes the physical page. Geometry is
    mapped only when the returned page and box are valid; otherwise bbox stays
    unknown. Unique index prefixes preserve even duplicate original locators.
    None of these rows makes the held page complete or bypasses review.
    """
    rows, lineage = [], []
    for index, row in enumerate(layout.rows):
        geometry_reason = None
        try:
            if layout.page != crop.page or row.page != crop.page:
                raise ProposalRecoveryError("proposal_recovery_page_mismatch")
            box = _map_box(row.bbox, crop)
        except ProposalRecoveryError as exc:
            box, geometry_reason = None, str(exc)
        old_locator = row.locator if isinstance(row.locator, str) else "unavailable"
        retained = replace(row, page=crop.page, bbox=box,
                           locator=f"{crop.locator_prefix}r{index}/{old_locator}",
                           source="stage_a_recovery")
        rows.append(retained)
        lineage.append({"locator": retained.locator, "crop_locator": row.locator,
                        "crop_index": crop.index, "crop_row_index": index,
                        "requires_full_page_review": True, "held_reason": reason,
                        "geometry_status": "unmappable" if geometry_reason else "mapped",
                        "geometry_held_reason": geometry_reason})
    return tuple(rows), {"blocks": [], "rows": lineage}


def recover_proposal_page(jpeg: bytes, failed_layout: DotsLayout,
                          read_crop: Callable[[ProposalCrop], DotsLayout], *,
                          original_receipt_sha256: str | None = None) -> ProposalRecovery:
    """Attempt at most two crop reads after a full-page format/truncation failure.

    The callback MUST parse using the descriptor's crop dimensions and page
    number, retain its own request/response receipts, and set layout.truncated
    for non-stop/token-limit responses. Successful crop proposals supplement
    every original candidate as a new explicit generation. Callers must review them all
    against the full page and retain this private audit in their final receipt.
    A crop of exactly RGB-white decoded source pixels needs no model call; its
    empty layout is bound to a deterministic pixel proof, never a model receipt.
    """
    if not isinstance(failed_layout, DotsLayout):
        raise ProposalRecoveryError("proposal_recovery_layout_required")
    if not isinstance(jpeg, bytes):
        raise ProposalRecoveryError("proposal_recovery_jpeg_required")
    if (original_receipt_sha256 is not None
            and re.fullmatch(r"[0-9a-f]{64}", original_receipt_sha256) is None):
        raise ProposalRecoveryError("proposal_recovery_receipt_invalid")
    if not needs_proposal_recovery(failed_layout):
        return ProposalRecovery(failed_layout, False, False, {
            "version": RECOVERY_VERSION, "attempted": False, "page": failed_layout.page,
            "reason": "full_page_has_no_format_or_truncation_failure"})
    manifest = proposal_recovery_manifest()
    audit = {
        "version": RECOVERY_VERSION, "generation": RECOVERY_GENERATION,
        "attempted": True, "recovered": False, "effective_complete": False, "page": failed_layout.page,
        "manifest": manifest, "config_sha256": sha256_bytes(canonical_json(manifest).encode()),
        "original": {"receipt_sha256": original_receipt_sha256, "layout": _layout_record(failed_layout)},
        "source_jpeg_sha256": sha256_bytes(jpeg),
        "review_image": "original_full_page", "deduplicated": False, "crops": [],
        "model_call_count": 0, "exact_white_region_count": 0,
    }
    try:
        crops = _crops(jpeg, failed_layout.page, audit["config_sha256"])
    except ProposalRecoveryError as exc:
        audit["failure"] = str(exc)
        held = replace(failed_layout, errors=tuple(dict.fromkeys(
            (*failed_layout.errors, "proposal_recovery_failed"))))
        return ProposalRecovery(held, True, False, audit)
    original_rows = tuple(replace(row, locator="g0/" + row.locator, source="stage_a_original")
                          for row in failed_layout.rows)
    audit["original_candidate_lineage"] = [
        {"locator": retained.locator, "original_locator": original.locator,
         "generation": 0, "requires_full_page_review": True}
        for original, retained in zip(failed_layout.rows, original_rows)]
    mapped, review_rows = [], list(original_rows)
    for crop in crops:
        item = {"descriptor": crop.metadata(), "complete": False, "model_called": False}
        layout = None
        try:
            if crop.source_rgb_extrema == ((255, 255),) * 3:
                item["origin"] = "deterministic_empty_region"
                item["empty_region_proof"] = {
                    **manifest["empty_region_proof"],
                    "source_rgb_extrema": crop.source_rgb_extrema,
                    "pixel_sha256": crop.pixel_sha256,
                    "source_jpeg_sha256": crop.source_jpeg_sha256,
                    "pixel_mode": "RGB", "width": crop.width, "height": crop.height,
                    "source_width": crop.source_width, "source_height": crop.source_height,
                    "bounds_px": crop.bounds_px, "bbox_fullpage": crop.bbox_fullpage,
                }
                audit["exact_white_region_count"] += 1
                layout = DotsLayout(crop.page, (), (), (), False)
            else:
                item["origin"] = "stage_a_model"
                item["model_called"] = True
                audit["model_call_count"] += 1
                layout = read_crop(crop)
            if not isinstance(layout, DotsLayout):
                raise ProposalRecoveryError("proposal_recovery_layout_required")
            item["layout"] = _layout_record(layout)
            if layout.errors or layout.truncated:
                item["failure"] = "proposal_recovery_crop_incomplete"
            else:
                fullpage, lineage = _map_layout(layout, crop, block_offset=sum(len(page.blocks) for page in mapped))
                item["lineage"] = lineage
                item["complete"] = True
                mapped.append(fullpage)
                review_rows.extend(fullpage.rows)
        except ProposalRecoveryError as exc:
            item["failure"] = str(exc)
        except Exception as exc:
            # No arbitrary exception messages or model content cross a boundary.
            item["failure"] = "proposal_recovery_reader_failed"
            item["error_type"] = type(exc).__name__
        if isinstance(layout, DotsLayout) and not item["complete"]:
            held_rows, lineage = _held_crop_rows(layout, crop, item["failure"])
            review_rows.extend(held_rows)
            item["lineage"] = lineage
        audit["crops"].append(item)
    audit.update(candidate_count=len(review_rows), original_candidate_count=len(original_rows),
                 crop_candidate_count=len(review_rows) - len(original_rows))
    if len(mapped) != 2:
        # No partial recovery can become an effective complete proposal set.
        # Every original and parsed crop candidate still needs an explicit B
        # verdict. Unknown geometry remains null; the entire page stays held.
        held_blocks = tuple(replace(block, order=index) for index, block in enumerate(
            (*failed_layout.blocks, *(block for layout in mapped for block in layout.blocks))))
        held = DotsLayout(failed_layout.page, held_blocks, tuple(review_rows), tuple(dict.fromkeys(
            (*failed_layout.errors, "proposal_recovery_failed"))),
            failed_layout.truncated or any(item.get("layout", {}).get("truncated") for item in audit["crops"]),
            failed_layout.warnings)
        return ProposalRecovery(held, True, False, audit, crops)
    warnings = tuple(dict.fromkeys(("layout_crop_recovery", "layout_overlap_candidates_preserved",
                                    *(warning for layout in mapped for warning in layout.warnings))))
    effective = DotsLayout(failed_layout.page,
                           tuple(block for layout in mapped for block in layout.blocks),
                           tuple(review_rows),
                           (), False, warnings)
    audit.update(recovered=True, effective_complete=True, candidate_count=len(effective.rows),
                 original_candidate_count=len(original_rows),
                 crop_candidate_count=len(review_rows) - len(original_rows),
                 effective_layout_sha256=sha256_bytes(canonical_json(_layout_record(effective)).encode()))
    return ProposalRecovery(effective, True, True, audit, crops)
