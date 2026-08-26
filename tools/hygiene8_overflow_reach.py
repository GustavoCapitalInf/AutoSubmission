"""The `OverflowError` contract: the eleven-entry-point census, and whether the
archive can reach it at all.

    python -m tools.hygiene8_overflow_reach --scratch <private>            # census only
    python -m tools.hygiene8_overflow_reach --scratch <private> \
        --rows <run>/rows.csv --data-dir <main>/webapp_data               # + archive reach

#HYGIENE8 RAISE-PRIVACY-3 widened seven handlers in `analysis/date_tokens.py`
from `except ValueError` to `except (ValueError, OverflowError)`. That module
is reached by parsers all over the registry, so unlike the other two sub-cards
this one is NOT provable by a family population — `tools.hygiene8_family_replay`
measures seven registrations and this change is not confined to them.

TWO MEASUREMENTS, and together they close it.

**The census** drives every public entry point on BOTH trees with an integer
past a C long and records what escapes. Two counts come out of it and they are
not the same number, so both are reported: `entry_points` counts the module's
public functions (twelve rows, because `iso_or_none` takes the number in two
different argument positions and each is a separate way in), while
`escaped_at_base` counts the DRIVES that let an `OverflowError` out. The commit
message's "ELEVEN entry points, EIGHT let the OverflowError escape" is the
second count over the eleven CONVERTING drives — `date_refusal` converts
nothing and is the twelfth row here. By distinct function the escapers are
seven, because `iso_or_none` escapes on both of its arguments.

It is re-derived per tree rather than asserted, because the size of a C long is
a property of the platform (it is 32-bit on this one) and a claim about it
should not be a constant in a log.

**The archive reach** was meant to settle tree-wide movement cheaply and DOES
NOT. Every path into `date()` in that module converts a run of DECIMAL DIGITS
taken from the document, so a document printing no digit run large enough could
not raise `OverflowError` anywhere in the module whatever parser read it — and
if the count came back zero, that would have been a proof of zero movement
costing no analysis passes.

It came back 2,765 of 3,351. A ten-digit number clears a 32-bit C long, and a
statement is full of them: account numbers, references, authorisation codes,
telephone digits. So the necessary condition is met almost everywhere and this
scan bounds nothing. It is kept, and reported, precisely because it is the
measurement that refused to make the convenient argument: what is left standing
after it is the family replay over the dispatched population, the pinned
manifest, and the archive-wide sweep the wave owes at the final tree — not a
sentence about how a regex probably bounds every caller.

The threshold is MEASURED, not typed: the smallest overflowing integer is found
by bisection at runtime, and 2000 is subtracted from it because
`iso_from_month_day_year` adds a century to a two-digit year before converting.

Read-only and $0: OCR artifacts by direct file path over every capability
partition, the sqlite index never opened, nothing written, no model called.
NOTHING IT PRINTS QUOTES A DOCUMENT — a finding is a `content_sha256` and the
LENGTH of the offending digit run, never the run itself, which on a real
statement would be an account or reference number.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import itertools
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

_DIGIT_RUN = re.compile(r"\d+")


def smallest_overflowing_integer() -> int:
    """The least `n` for which `date(2026, 1, n)` raises `OverflowError`.

    Bisection rather than a constant: `date()` overflows when the day argument
    passes a C long, and a C long is 32-bit on Windows and 64-bit elsewhere. A
    hard-coded bound would make this instrument silently wrong on the other
    platform, in the direction that under-reports.
    """
    low, high = 1, 1
    while True:
        try:
            date(2026, 1, high)
        except OverflowError:
            break
        except ValueError:
            pass
        low = high
        high *= 2
        if high > 10 ** 40:  # pragma: no cover - no platform behaves this way
            raise RuntimeError("date() never overflowed; the census is vacuous")
    while low + 1 < high:
        middle = (low + high) // 2
        try:
            date(2026, 1, middle)
        except OverflowError:
            high = middle
        except ValueError:
            low = middle
        else:  # pragma: no cover - a valid day is far below the bound
            low = middle
    return high


def overflow_cases(package: str, huge: int) -> dict[str, object]:
    """Every public entry point of `date_tokens`, driven with `huge`.

    The list is derived from the module's public surface rather than
    maintained: `assert_covers_public_surface` below fails if a function is
    added and not driven, so this census cannot quietly go stale. `date_refusal`
    is the constructor and converts nothing; the other ten each reach `date()`
    or `strptime` with a number the document supplied, and `iso_or_none` is
    driven twice because its year and its day are two different ways in.
    """
    dt = importlib.import_module(f"{package}.date_tokens")
    start, end = date(2026, 1, 1), date(2026, 3, 1)
    calls = {
        "date_refusal": lambda: dt.date_refusal("census", str(huge)),
        "parsed_datetime": lambda: dt.parsed_datetime(str(huge), "%Y", reader="census"),
        "iso_or_none/year": lambda: dt.iso_or_none(huge, 1, 1),
        "iso_or_none/day": lambda: dt.iso_or_none(2026, 1, huge),
        "iso_from_month_day": lambda: dt.iso_from_month_day(f"1/{huge}", 2026),
        "iso_from_month_day_strict": lambda: dt.iso_from_month_day_strict(f"1/{huge}", 2026),
        "iso_from_month_day_year": lambda: dt.iso_from_month_day_year(f"1/1/{huge}"),
        "iso_from_named_month_day": lambda: dt.iso_from_named_month_day(
            "April", str(huge), "2026"
        ),
        "iso_unique_in_period": lambda: dt.iso_unique_in_period(1, huge, start=start, end=end),
        "year_within_period": lambda: dt.year_within_period(1, huge, start, end),
        "iso_within_period": lambda: dt.iso_within_period(f"1/{huge}", start, end),
        "period_from_long_dates": lambda: dt.period_from_long_dates(
            f"April {huge}, 2026 through May 4, 2026"
        ),
    }
    # A census that silently stopped covering the module would report a
    # comfortable zero. The public surface is read off the module and compared
    # with what is driven, so a function added later fails this rather than
    # being missed.
    public = {
        name
        for name in vars(dt)
        if not name.startswith("_")
        and callable(getattr(dt, name))
        and getattr(getattr(dt, name), "__module__", "") == dt.__name__
    }
    driven = {name.split("/")[0] for name in calls}
    missing = public - driven
    if missing:
        raise RuntimeError(f"date_tokens entry points not driven by the census: {sorted(missing)}")

    # `iso_from_month_day_strict` and `period_from_long_dates` both bound the
    # token with a regex before converting, which is protection that lives in
    # the CALLER's pattern and not in a handler — recorded, because it is the
    # kind that disappears the day the pattern is widened.
    outcomes: dict[str, object] = {}
    for name, call in calls.items():
        try:
            result = call()
        except OverflowError:
            outcomes[name] = "OverflowError-ESCAPED"
        except ValueError as exc:
            outcomes[name] = (
                "refusal"
                if "date grammar refused a printed token" in str(exc)
                else "ValueError"
            )
        except Exception as exc:  # noqa: BLE001
            outcomes[name] = type(exc).__name__
        else:
            outcomes[name] = "None" if result is None else "value"
    return outcomes


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="10cc722")
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--rows", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo))
    from tools.hygiene8_base_tree import load_base_analysis

    base = load_base_analysis(args.base, repo=repo, scratch=args.scratch)
    bound = smallest_overflowing_integer()
    huge = bound + 1
    base_cases = overflow_cases(base.package, huge)
    branch_cases = overflow_cases("analysis", huge)
    escaped_at_base = sorted(k for k, v in base_cases.items() if v == "OverflowError-ESCAPED")
    escaped_at_branch = sorted(k for k, v in branch_cases.items() if v == "OverflowError-ESCAPED")

    report: dict[str, object] = {
        "base": base.revision,
        "smallest_overflowing_integer_digits": len(str(bound)),
        "public_functions": len({name.split("/")[0] for name in branch_cases}),
        "conversion_drives": len(branch_cases) - 1,  # `date_refusal` converts nothing
        "escaped_at_base": len(escaped_at_base),
        "escaped_at_base_functions": len({name.split("/")[0] for name in escaped_at_base}),
        "escaped_at_branch": len(escaped_at_branch),
        "escaped_at_base_names": escaped_at_base,
        "escaped_at_branch_names": escaped_at_branch,
        "base_outcomes": base_cases,
        "branch_outcomes": branch_cases,
    }

    if args.rows is not None and args.data_dir is not None:
        from ocr.document import StatementMarkdown
        from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

        # A two-digit year gains a century before conversion, so the reachable
        # bound is lower than the overflow bound by exactly that.
        threshold = bound - 2000
        root = args.data_dir / "artifacts"
        ocr_keys = [
            ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
            for force, local, visual in itertools.product((False, True), repeat=3)
        ]
        with args.rows.open(encoding="utf-8", newline="") as handle:
            shas = sorted({row["content_sha256"] for row in csv.DictReader(handle) if row["content_sha256"]})

        started = time.perf_counter()
        scanned = 0
        no_text = 0
        longest_run = 0
        over_threshold: list[dict[str, object]] = []
        for sha in shas:
            texts: list[str] = []
            for key in ocr_keys:
                composed = cache_key(STAGE_OCR, sha, key)
                path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
                if not path.exists():
                    continue
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                document = (payload.get("artifact") or {}).get("document")
                if not isinstance(document, dict):
                    continue
                pages = [str(page) for page in (document.get("pages") or [])]
                texts.append(
                    StatementMarkdown(
                        source_file="scan.pdf",
                        model=str(document.get("model") or ""),
                        pages=pages,
                    ).to_markdown()
                )
            if not texts:
                no_text += 1
                continue
            scanned += 1
            worst = 0
            worst_length = 0
            for text in texts:
                for match in _DIGIT_RUN.finditer(text):
                    run = match.group(0)
                    if len(run) > worst_length:
                        worst_length = len(run)
                    # Only the value matters, and only up to the threshold: a
                    # 400-digit run is compared, never stored.
                    if len(run) <= 40:
                        worst = max(worst, int(run))
            longest_run = max(longest_run, worst_length)
            if worst >= threshold:
                over_threshold.append(
                    {
                        "content_sha256": sha,
                        # LENGTH only. The run itself would be an account or a
                        # reference number on a real statement.
                        "digit_run_length": worst_length,
                    }
                )
        report["archive"] = {
            "documents_in_run": len(shas),
            "documents_with_text": scanned,
            "documents_without_text": no_text,
            "reachable_threshold": threshold,
            "longest_digit_run": longest_run,
            "documents_at_or_over_threshold": len(over_threshold),
            "findings": over_threshold[:50],
            "seconds": round(time.perf_counter() - started, 1),
        }

    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    printable = {k: v for k, v in report.items() if k not in {"base_outcomes", "branch_outcomes"}}
    if "archive" in printable:
        printable["archive"] = {
            k: v for k, v in report["archive"].items() if k != "findings"  # type: ignore[index]
        }
    print(json.dumps(printable, sort_keys=True))
    for name in sorted(branch_cases):
        print(f"  {name:28s} base={base_cases[name]:24s} branch={branch_cases[name]}")
    return 1 if escaped_at_branch else 0


if __name__ == "__main__":
    raise SystemExit(main())
