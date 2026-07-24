"""Dev-only: scan OCR'd output/*.md for known defect signatures so we can triage
which banks need postprocessor work without eyeballing every file."""
from __future__ import annotations
import re
from pathlib import Path

OUT = Path("output")

CHECKS = {
    "leftover_det_tags": re.compile(r"<\|/?det\|>"),
    "non_text_marker": re.compile(r"\[Non-?Text\]", re.IGNORECASE),
    "image_placeholder": re.compile(r"\[(image|figure|logo|picture|photo)\]", re.IGNORECASE),
    # header glued to a value in one cell, e.g. "DATE01/02", "AMOUNT$1,000.00"
    "fused_header_cell": re.compile(r"<td>(DATE|AMOUNT|BALANCE|DESCRIPTION)(?=[^\s<])"),
    # 3+ whitespace-separated money tokens (repetition degeneration)
    "money_run": re.compile(r"(-?\$?[\d,]+\.\d{2})(?:\s+-?\$?[\d,]+\.\d{2}){2,}"),
    "empty_table": re.compile(r"<table>\s*</table>"),
    # a cell holding description text AND a trailing amount (column bleed)
    "amount_bleed": re.compile(r"<td>[^<]* [A-Za-z]{3}[^<]* -?\$?[\d,]+\.\d{2}</td>"),
}


def main():
    files = sorted(p for p in OUT.glob("*.md") if not p.name.startswith("_"))
    if not files:
        print("no output/*.md yet")
        return
    width = max(len(p.stem) for p in files)
    hits_total = {k: 0 for k in CHECKS}
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        # ignore base64 image payloads when scanning
        text = re.sub(r"base64,[A-Za-z0-9+/=]+", "base64,", text)
        flags = []
        for name, rx in CHECKS.items():
            n = len(rx.findall(text))
            if n:
                flags.append(f"{name}={n}")
                hits_total[name] += 1
        status = "  ".join(flags) if flags else "clean"
        print(f"{p.stem:<{width}}  {status}")
    print("\n-- files affected per signature --")
    for k, v in sorted(hits_total.items(), key=lambda kv: -kv[1]):
        if v:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
