"""Move a fixture's dates off the archive's calendar WITHOUT changing one fact about them.

Half of what `tests/` carries into the privacy scan is DATES: 1,971 of the
4,041 residue sites at this card's base. They are residue for the ordinary
reason — a fixture written beside a real statement prints the days that
statement printed — and they are the half that cannot be repaired by inventing
a value, because a date is not an opaque id. Every one of them is load-bearing:
a statement period, a posting order, a day count an average divides by.

THE TRANSFORM, AND WHY IT IS AN IDENTITY. Add TWENTY-EIGHT YEARS to every date
in a file. Inside one century block the Gregorian calendar has a period of
exactly 28 years — four for the leap cycle, seven for the week, and no skipped
leap year in between — so the shift preserves, exactly and not approximately:

* every WEEKDAY (2031-08-03 is a Sunday; so is 2059-08-03);
* every MONTH LENGTH, February's included, because 28 is a multiple of four and
  no year in range crosses a skipped century leap;
* every INTERVAL in days between any two shifted dates;
* every ORDERING;
* every US federal BANK HOLIDAY, by month and day — the nth-weekday holidays
  because weekdays are preserved, the fixed ones because their Saturday and
  Sunday observance rules turn on the weekday too.

That last point is the one that matters most here and it is why the shift is 28
and not 8. `analysis/adb.py` publishes `weekday_only` and `banking_day`
alternates over a real holiday calendar. Under a shift that moved the weekday,
every one of those numbers would change and every fixture asserting one would
have to be RE-DERIVED from the code it is supposed to be testing — which is not
a fixture repair, it is erasing the oracle. Under +28 they are untouched.

`--self-check` proves the isomorphism rather than asserting it: it walks every
day of the range it is asked about, compares weekday and month length either
side of the shift, and compares `analysis.adb`'s own holiday set year by year.

WHAT IT REWRITES. Every shape the scanner counts as a DATES token —
`mm/dd/yyyy`, `m/d/yy`, `yyyy-mm-dd`, `January 5, 2031`, `5 January 2031` — the
`SEP 29/31` form a Canadian statement header prints, which is not a scanned
token but dates the period the scanned ones sit in — and
the two shapes it does NOT count but which must move with them or the file
stops agreeing with itself: `date(2031, 8, 1)` and `datetime(2031, 8, 1, ...)`
literals. A bare `mm/dd` day token carries no year, identifies nobody and is
never scanned, so it is left exactly as it is.

WHAT IT CANNOT SEE, and why the suite is the real gate: a year written on its
own (`STATEMENT PERIOD: AUGUST 2031`, `FY2031`) is not a date token and is not
shifted, so a file that carries one comes out disagreeing with itself. That
shows up as a FAILING TEST, which is the point — this tool proposes a rewrite,
the file's own suite decides whether it happened. `--report-years` lists every
four-digit year still standing after the shift so the residue can be read
rather than discovered.

    python -m tools.fixpriv_shift_dates --self-check
    python -m tools.fixpriv_shift_dates --dry-run tests/test_analysis.py
    python -m tools.fixpriv_shift_dates tests/test_analysis.py

Exit 0 when every file was rewritten (or would be), 1 when a file carries no
date at all, 2 when the shift would not be an identity for some date it found.
No archive, no cache, no network, $0.
"""
from __future__ import annotations

import argparse
import calendar
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Four for the leap cycle, seven for the week. See the module docstring.
SHIFT_YEARS = 28

#: English and FRENCH month names. The tree carries Canadian French readers and
#: their fixtures print `3 mars 2026` and `Du 3 mars au 2 avril`; a grammar that
#: reads only English leaves half of a bilingual fixture on the old calendar,
#: which is a file that no longer agrees with itself.
_MONTHS = (
    "JAN(?:UARY|V(?:IER)?)?|FEB(?:RUARY)?|F[E\u00c9]VR?(?:IER)?|MAR(?:CH|S)?|"
    "AVR(?:IL)?|APR(?:IL)?|MAY|MAI|JUNE?|JUIN|JULY?|JUIL(?:LET)?|AO[U\u00db]T|"
    "AUG(?:UST)?|SEPT?(?:EMBER|EMBRE)?|OCT(?:OBER|OBRE)?|NOV(?:EMBER|EMBRE)?|"
    "D[E\u00c9]C(?:EMBER|EMBRE)?"
)

#: Where a spelled month may START. A word boundary is not enough in a
#: SOURCE file. A fixture writes its page header as one Python string with
#: an escaped newline in the middle of it, so what stands in front of the
#: month is the letter of that escape - two word characters side by side,
#: no boundary between them, and the whole date goes unread while the ISO
#: expectation beside it moves. The lookbehinds name the escape sequences a
#: fixture actually glues a month to.
_MONTH_START = r"(?:\b|(?<=\\n)|(?<=\\r)|(?<=\\t))"

#: One alternation, one pass, so no shape can be shifted twice. The groups are
#: named after the shape; the year group of each is what moves.
DATE_SHAPES = re.compile(
    r"(?P<slash4>(?<![\d/])\d{1,2}/\d{1,2}/(?P<slash4y>\d{4})(?![\d/]))"
    r"|(?P<slash2>(?<![\d/])\d{1,2}/\d{1,2}/(?P<slash2y>\d{2})(?![\d/]))"
    r"|(?P<iso>(?<![\d-])(?P<isoy>\d{4})-\d{2}-\d{2}(?![\d-]))"
    rf"|(?P<spelled>{_MONTH_START}(?:{_MONTHS})\.? ?\d{{1,2}}(?:,\s*|\s+)(?P<spelledy>\d{{4}})\b)"
    rf"|(?P<spelled_first>{_MONTH_START}\d{{1,2}} (?:{_MONTHS})\.? (?P<spelled_firsty>\d{{4}})\b)"
    rf"|(?P<mdy2>{_MONTH_START}(?:{_MONTHS})\.? ?\d{{1,2}}/(?P<mdy2y>\d{{2}})(?![\d/]))"
    rf"|(?P<spelled_dash>{_MONTH_START}(?:{_MONTHS})-\d{{1,2}}-(?P<spelled_dashy>\d{{4}})\b)"
    r"|(?P<dmy_dash>(?<![\d-])\d{1,2}-\d{1,2}-(?P<dmy_dashy>\d{4})(?![\d-]))"
    r"|(?P<ctor>\b(?:date|datetime)\(\s*(?P<ctory>\d{4})\s*,)",
    re.IGNORECASE,
)

#: The same alternation with a BARE YEAR on the end. Opt-in, and last in the
#: alternation so every real date shape claims its year first.
#:
#: A bare `2026` is not a date and this tool cannot tell one from a count, an
#: index or a version — which is exactly why it is a FLAG and not the default.
#: It exists because a fixture that builds its dates in Python rather than
#: printing them (`start_year=2026`, `maybe_year="2024"`,
#: `f"05/{day:02d}/2026"`) leaves its year behind when the printed dates move,
#: and the file then disagrees with itself in a way only its own suite can
#: see. Use it per file, with that suite, and read the diff.
#:
#: The guards are `(?<![\d.])` and `(?![\d.])`: a full stop on either side
#: means a version, a float or a FILE NAME — `APRIL 2026.pdf` is a pinned
#: corpus document and moving its year points a test at a file that does not
#: exist. The range is 2005..2039: it stops at 2039 so a year this tool has
#: already shifted can never be shifted twice, and it STARTS at 2005 because
#: 2000 is not a year in this tree, it is a century PIVOT — `year + 2000 if
#: year < 100` is how every reader here reads a two-digit year, and shifting
#: that constant moves every date the reader produces. The suite found that:
#: a legacy clone and its replacement disagreed by exactly 28 years, which is
#: the whole argument for this being a flag with a suite behind it.
DATE_SHAPES_WITH_BARE_YEARS = re.compile(
    DATE_SHAPES.pattern + r"|(?<![\d.])(?P<bare>(?P<barey>20(?:0[5-9]|[1-3]\d)))(?![\d.])",
    re.IGNORECASE,
)

_CONTROL_BYTES = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")

#: The year groups, and for each the width its replacement must keep.
_YEAR_GROUPS = (
    ("slash4y", 4),
    ("slash2y", 2),
    ("isoy", 4),
    ("spelledy", 4),
    ("mdy2y", 2),
    ("spelled_firsty", 4),
    ("spelled_dashy", 4),
    ("dmy_dashy", 4),
    ("barey", 4),
    ("ctory", 4),
)


def self_check() -> None:
    """Refuse to run as an inert instrument (the heredoc / 0x08 lesson)."""
    own = Path(__file__).read_bytes()
    found = _CONTROL_BYTES.findall(own)
    if found:
        raise SystemExit(f"fixpriv_shift_dates.py carries {len(found)} control byte(s)")
    samples = {
        "slash4": "ON 08/01/2031 HERE",
        "slash2": "ON 08/01/31 HERE",
        "iso": "ON 2031-08-01 HERE",
        "spelled": "ON AUGUST 1, 2031 HERE",
        "spelled_tight": "Apr 13,2031 REMOTE",
        "spelled_after_escape": r"Checking\nMarch 31, 2031 Page 1",
        # A text layer that dropped its inter-word spacing still prints a date,
        # and this tree tests exactly that layer.
        "spelled_spaceless": "Forthe period ending April30, 2031",
        "spelled_first": "ON 1 AUGUST 2031 HERE",
        "mdy2": "SEP 29/31 - OCT 31/31",
        "ctor": "date(2031, 8, 1)",
    }
    for name, sample in samples.items():
        match = DATE_SHAPES.search(sample)
        # `spelled_tight` is the same shape with the space after the comma
        # missing, which a statement prints and the first draft of this
        # pattern skipped; it is checked against the `spelled` group.
        group = "spelled" if name.startswith("spelled_") and name != "spelled_first" else name
        if match is None or match.lastgroup is None or match.group(group) is None:
            raise SystemExit(f"DATE_SHAPES does not match its own {name} sample")
    if shift_text("ON 08/01/2031 AND 2031-08-01", SHIFT_YEARS)[0] != "ON 08/01/2059 AND 2059-08-01":
        raise SystemExit("shift_text does not move its own sample; refusing to run")
    # A bare day token has no year and must survive untouched.
    if shift_text("ATM W/D 08/01 POSTED", SHIFT_YEARS)[0] != "ATM W/D 08/01 POSTED":
        raise SystemExit("shift_text moved a bare mm/dd token; refusing to run")


def calendar_is_isomorphic(first_year: int, last_year: int, years: int) -> list[str]:
    """Every way the shift could fail to be an identity, checked rather than claimed."""
    problems: list[str] = []
    for year in range(first_year, last_year + 1):
        for month in range(1, 13):
            here = calendar.monthrange(year, month)[1]
            there = calendar.monthrange(year + years, month)[1]
            if here != there:
                problems.append(f"{year}-{month:02d} is {here} days, {year + years}-{month:02d} is {there}")
            # `min` because a month-length mismatch is already recorded above
            # and `date()` would raise on the 29th of a February that is not
            # one in the target year — the check must REPORT that, not die of it.
            for day in range(1, min(here, there) + 1):
                if date(year, month, day).weekday() != date(year + years, month, day).weekday():
                    problems.append(f"{year}-{month:02d}-{day:02d} changes weekday")
                    break
    try:
        sys.path.insert(0, str(ROOT))
        from analysis.adb import _federal_bank_holidays
    except Exception as error:  # noqa: BLE001 — the check is about dates, not imports
        problems.append(f"could not read the bank holiday calendar: {error}")
        return problems
    for year in range(first_year, last_year + 1):
        here = {(d.month, d.day) for d in _federal_bank_holidays(year)}
        there = {(d.month, d.day) for d in _federal_bank_holidays(year + years)}
        if here != there:
            problems.append(f"bank holidays differ between {year} and {year + years}")
    return problems


#: The years the identity is proved over. A four-digit year outside it is left
#: exactly where it is, and this is not caution, it is the same rule the tool
#: applies to itself: the shift is an identity BECAUSE `calendar_is_isomorphic`
#: walked this range, and a year the check never visited has no such proof
#: behind it. It also catches a class of fixture the first sweep would have
#: broken — a DELIBERATELY IMPOSSIBLE year. `"April 4, 0000"` is a poisoned
#: input in a test about refusing bad dates privately, and shifting it to a
#: year Python accepts turns a fail-closed test into a passing one.
PROVED_FIRST_YEAR = 2005
PROVED_LAST_YEAR = 2045


def _shifted_year(text: str, width: int, years: int) -> str | None:
    """The year moved, or None if it must not move."""
    value = int(text)
    if width == 2:
        # The tree's own century rule is `year + 2000 if year < 100`, so a
        # two-digit year shifts by the same amount and stays two digits.
        if not PROVED_FIRST_YEAR <= 2000 + value <= PROVED_LAST_YEAR:
            return None
        return f"{(value + years) % 100:02d}"
    if not PROVED_FIRST_YEAR <= value <= PROVED_LAST_YEAR:
        return None
    return f"{value + years:0{width}d}"


def shift_text(text: str, years: int, bare_years: bool = False) -> tuple[str, dict[str, int]]:
    """The file with every date shifted, and a count per shape."""
    pattern = DATE_SHAPES_WITH_BARE_YEARS if bare_years else DATE_SHAPES
    counts: dict[str, int] = {name: 0 for name, _ in _YEAR_GROUPS}
    counts["out_of_range"] = 0

    def replace(match: re.Match[str]) -> str:
        for name, width in _YEAR_GROUPS:
            # `barey` exists only in the bare-year pattern, so a group this
            # pattern does not carry is simply not one of its shapes.
            if name not in match.re.groupindex:
                continue
            found = match.group(name)
            if found is None:
                continue
            moved = _shifted_year(found, width, years)
            if moved is None:
                counts["out_of_range"] += 1
                return match.group(0)
            counts[name] += 1
            start, end = match.span(name)
            whole_start = match.start()
            return (
                match.group(0)[: start - whole_start]
                + moved
                + match.group(0)[end - whole_start:]
            )
        return match.group(0)

    return pattern.sub(replace, text), counts


def years_in(text: str) -> dict[str, int]:
    """Every four-digit year-shaped token still standing, with its count."""
    found: dict[str, int] = {}
    for token in re.findall(r"(?<!\d)(?:19|20)\d\d(?!\d)", text):
        found[token] = found.get(token, 0) + 1
    return dict(sorted(found.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--years", type=int, default=SHIFT_YEARS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-check", action="store_true",
                        help="prove the shift is a calendar identity and stop")
    parser.add_argument("--bare-years", action="store_true",
                        help="also shift a standalone four-digit year (2000..2039) "
                             "that no date shape claimed — UNSAFE without the "
                             "file's own suite; see the module docstring")
    parser.add_argument("--report-years", action="store_true",
                        help="list the four-digit years left standing after the shift")
    parser.add_argument("--first-year", type=int, default=2005)
    parser.add_argument("--last-year", type=int, default=2045)
    args = parser.parse_args(argv)
    self_check()

    problems = calendar_is_isomorphic(args.first_year, args.last_year, args.years)
    if problems:
        for problem in problems[:20]:
            print(f"NOT AN IDENTITY: {problem}", file=sys.stderr)
        print(f"{len(problems)} problems; refusing to shift", file=sys.stderr)
        return 2
    if args.self_check:
        span = args.last_year - args.first_year + 1
        print(f"+{args.years} years is a calendar identity over {span} years "
              f"({args.first_year}..{args.last_year}): weekday, month length and "
              f"the federal bank holiday set all reproduce")
        return 0

    status = 0
    for path in args.paths:
        original = path.read_text(encoding="utf-8", newline="")
        shifted, counts = shift_text(original, args.years, args.bare_years)
        skipped = counts.pop("out_of_range")
        moved = sum(counts.values())
        if moved == 0:
            print(f"{path}: no date token; nothing to shift", file=sys.stderr)
            status = 1
            continue
        shape = " · ".join(f"{name.removesuffix('y')} {count}"
                           for name, count in counts.items() if count)
        outside = f"  [{skipped} outside {PROVED_FIRST_YEAR}..{PROVED_LAST_YEAR}, left]" if skipped else ""
        print(f"{path}: {moved} dates shifted +{args.years}y  ({shape}){outside}")
        if args.report_years:
            print(f"    years still standing: {years_in(shifted)}")
        if not args.dry_run:
            path.write_text(shifted, encoding="utf-8", newline="")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
