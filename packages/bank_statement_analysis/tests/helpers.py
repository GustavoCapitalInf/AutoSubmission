"""Helpers several test modules use, each one function shared rather than copied."""
from __future__ import annotations

import ast
from datetime import timedelta
from pathlib import Path

from analysis import lender_payment_changes as lpc
from discovery.runner import DocumentRow
from ocr.document import StatementMarkdown


def _checkout_ancestor(*relative: str):
    """The nearest enclosing directory that holds `relative`, or None. A git worktree does not carry gitignored
    files; the checkout it was created from does, so searching upwards lets a test run from either."""
    root = Path(__file__).resolve().parents[1]
    for base in (root, *root.parents):
        candidate = base.joinpath(*relative)
        if candidate.exists():
            return candidate
    return None


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: inside the package by construction
                continue
            if node.module:
                names.add(node.module)
    return names


def every(first, last, step=7):
    days, day = [], first
    while day <= last:
        days.append(day)
        day += timedelta(days=step)
    return days


def bdays(first, last):
    days, day = [], first
    while day <= last:
        if day.weekday() < 5 and day not in lpc._holidays("US", day.year):
            days.append(day)
        day += timedelta(days=1)
    return days


def _strptime_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "strptime"
    ]


def _both(fn_a, fn_b, value):
    out = []
    for fn in (fn_a, fn_b):
        try:
            out.append(("ok", fn(value)))
        except Exception as exc:  # noqa: BLE001 - equivalence includes failures
            out.append(("raise", type(exc).__name__))
    return out[0], out[1]


def _tesseract(monkeypatch, text: str | None):
    """Pin the local-Tesseract rung's answer (never runs the real binary). `text=None` is the rung finding nothing —
    the shape `--scanned` refuses as `insufficient_evidence` (it was `deferred_visual_ocr` until slice S5)."""
    def fake(pdf_bytes, source_file="", **kwargs):
        if text is None:
            return None
        return StatementMarkdown(source_file=source_file, model="local-tesseract-ocr", pages=[text])

    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", fake)


def _cp1252_stdout(monkeypatch):
    import io
    import sys

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\r\n")
    monkeypatch.setattr(sys, "stdout", stream)
    return stream


def _image_only_pdf() -> bytes:
    import fitz

    with fitz.open() as document:
        page = document.new_page()
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64), 0)
        pixmap.clear_with(255)
        page.insert_image(page.rect, pixmap=pixmap)
        return document.tobytes()


def _row(**kwargs) -> DocumentRow:
    base = dict(relative_path="F/a.pdf", folder_label="F",
                content_sha256="A" * 64, byte_size=1)
    base.update(kwargs)
    return DocumentRow(**base)


def _package(*members):
    from analysis.package import package_analysis
    from webapp.jobs import Job
    return package_analysis([Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload,
                                 content_sha256=job_id) for job_id, payload in members], settings={})
