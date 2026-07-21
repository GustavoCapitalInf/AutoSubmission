from __future__ import annotations
import re
from datetime import datetime

_MONEY_RE = re.compile(r"\(?\$?\s?-?\d{1,3}(?:,\d{3})*(?:\.\d{2})?-?\)?")
_MONTHS = {m.lower(): i for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], start=1)}

def parse_money(token: str) -> float | None:
    if token is None:
        return None
    t = token.strip()
    if not re.search(r"\d", t):
        return None
    cleaned = t.replace("$", "").replace(",", "").replace(" ", "")
    cleaned = cleaned.replace("(", "").replace(")", "").rstrip("-").lstrip("-")
    if not cleaned:
        return None
    try:
        return abs(float(cleaned))
    except ValueError:
        return None

def find_amounts(text: str) -> list[str]:
    out = []
    for m in _MONEY_RE.finditer(text or ""):
        tok = m.group().strip()
        if re.search(r"\d\.\d{2}", tok) or re.search(r"\d,\d{3}", tok):
            out.append(tok)
    return out

def normalize_date(raw: str, year_hint: int | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    # Numeric MM/DD[/YY[YY]]
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?$", s)
    if m:
        mo, da, yr = int(m.group(1)), int(m.group(2)), m.group(3)
        if yr is None:
            if year_hint is None:
                return None
            year = year_hint
        else:
            year = int(yr)
            if year < 100:
                year += 2000
        try:
            return datetime(year, mo, da).strftime("%Y-%m-%d")
        except ValueError:
            return None
    # "Mon DD" or "DD Mon YYYY"
    m = re.match(r"^([A-Za-z]{3,})\.?\s+(\d{1,2})(?:,?\s+(\d{4}))?$", s)
    if m and m.group(1)[:3].lower() in _MONTHS:
        mo = _MONTHS[m.group(1)[:3].lower()]
        da = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else year_hint
        if year is None:
            return None
        try:
            return datetime(year, mo, da).strftime("%Y-%m-%d")
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]{3,})\.?\s+(\d{4})$", s)
    if m and m.group(2)[:3].lower() in _MONTHS:
        try:
            return datetime(int(m.group(3)), _MONTHS[m.group(2)[:3].lower()], int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None
