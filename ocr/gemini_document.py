"""Bounded paid fallback for visual PDF transcription.

Unlimited OCR remains the preferred visual reader. This module is imported only
when that service is unavailable and one document-wide Gemini attempt remains.
It transcribes source pages; it does not calculate or classify financial data.
"""
from __future__ import annotations

import re
import time
from typing import Callable

from google import genai
from google.genai import types

from analysis.config import Settings, load_settings
from analysis.extract import (
    GEMINI_PRICING_VERSION,
    ExtractionAttempt,
    estimate_extraction_cost,
)
from .document import StatementMarkdown


_PAGE_RE = re.compile(r"---\s*Page\s+(\d+)(?:\s+\(empty\))?\s*---", re.IGNORECASE)
_PROMPT = """Transcribe this bank statement exactly, page by page, into plain Markdown.
Preserve every visible heading, account identifier, date, description, amount,
debit/credit column, running balance, summary total, and daily-balance row. Do
not calculate, infer, classify, correct, or omit financial data. Separate pages
using exactly `--- Page N ---`, with one-based page numbers. Return only the
transcription and page markers."""


def _token_count(value: object, name: str) -> int | None:
    raw = getattr(value, name, None)
    return int(raw) if raw is not None else None


def _pages(markdown: str) -> list[str]:
    text = markdown.strip()
    if text.startswith("```") and text.endswith("```"):
        text = re.sub(r"^```(?:markdown)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    matches = list(_PAGE_RE.finditer(text))
    if not matches:
        return [text]
    page_numbers = [int(match.group(1)) for match in matches]
    if (
        page_numbers != list(range(1, len(page_numbers) + 1))
        or len(page_numbers) > 500
    ):
        return [text]
    by_page: dict[int, str] = {}
    prefix = text[:matches[0].start()].strip()
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        page_number = int(match.group(1))
        page_text = text[match.end():end].strip()
        if prefix and index == 0:
            page_text = f"{prefix}\n{page_text}".strip()
        by_page[page_number] = page_text
    return [by_page.get(page_number, "") for page_number in range(1, max(by_page) + 1)]


def parse_gemini_document(
    pdf_bytes: bytes,
    *,
    source_file: str,
    settings: Settings | None = None,
    attempt_sink: Callable[[ExtractionAttempt], None] | None = None,
) -> StatementMarkdown:
    settings = settings or load_settings()
    if not settings.api_key:
        raise RuntimeError("GEMINI_API_KEY is not set for document OCR fallback")
    client = genai.Client(
        api_key=settings.api_key,
        http_options=types.HttpOptions(
            timeout=settings.request_timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=settings.http_attempts),
        ),
    )
    started = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=settings.model,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                _PROMPT,
            ],
        )
        markdown = (response.text or "").strip()
        if not markdown:
            raise RuntimeError("Gemini document OCR returned no transcription")
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = _token_count(usage, "prompt_token_count") if usage else None
        candidate_tokens = _token_count(usage, "candidates_token_count") if usage else None
        thinking_tokens = _token_count(usage, "thoughts_token_count") if usage else None
        response_tokens = None
        if candidate_tokens is not None or thinking_tokens is not None:
            response_tokens = (candidate_tokens or 0) + (thinking_tokens or 0)
        attempt = ExtractionAttempt(
            provider="google_gemini",
            model=settings.model,
            source_kind="pdf_visual_ocr",
            status="success",
            latency_ms=round((time.perf_counter() - started) * 1000),
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            thinking_tokens=thinking_tokens,
            total_tokens=_token_count(usage, "total_token_count") if usage else None,
            estimated_cost_usd=estimate_extraction_cost(
                settings.model,
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
            ),
            pricing_version=GEMINI_PRICING_VERSION,
        )
        if attempt_sink is not None:
            attempt_sink(attempt)
        return StatementMarkdown(
            source_file=source_file,
            model=f"gemini-document-ocr:{settings.model}",
            pages=_pages(markdown),
            external_attempts=[attempt],
        )
    except Exception as exc:
        if attempt_sink is not None:
            attempt_sink(
                ExtractionAttempt(
                    provider="google_gemini",
                    model=settings.model,
                    source_kind="pdf_visual_ocr",
                    status="error",
                    latency_ms=round((time.perf_counter() - started) * 1000),
                    pricing_version=GEMINI_PRICING_VERSION,
                    error_type=type(exc).__name__,
                )
            )
        raise
