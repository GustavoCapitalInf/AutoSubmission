"""The leak census for the six sites RAISE-PRIVACY-3 rerouted — BASE vs BRANCH.

    python -m tools.hygiene8_poison_sweep --scratch <private> [--out poison.json]

§PRIVACY3 P4 ran this shape as "the dynamic census: 76 cells, both trees, same
harness". No committed instrument came out of it (measured: nothing under
`tools/` mentions the poison set; the vocabulary lives in
`tests/test_privacy3_boundaries.py`), so this is the minimal successor, scoped
to what #HYGIENE8 rerouted. It exists because a headline "0 leaking cells" that
only ever ran on the branch is not a measurement of anything — the number that
makes it a measurement is the one the SAME harness produces on the base tree.

A CELL is one (site, token-shape) pair. A cell LEAKS when the poisoned token,
its canary, or any digit run inside it reaches any of the five surfaces an
exception message escapes through — `str`, `repr`, `args`, the `__cause__` /
`__context__` chain, and the traceback with each frame's own quoted SOURCE line
subtracted. That rule is `tests/test_privacy3_boundaries.assert_private`'s, and
it is IMPORTED rather than restated: a second copy of a privacy rule is a
second thing to keep in step.

THE POISON IS INVENTED, ALWAYS. `CANARY` is a made-up payer string, `DIGITS` is
a made-up digit run, the malformed dates are shapes rather than transcriptions,
and the two fixtures below are written from the detection markers already in
tracked source with invented figures and 2031 dates. Nothing here has ever been
inside a document.

TWO KINDS OF DRIVE, and the second is the one mutant R11 taught this branch to
want:

* SEAM — the rerouted callable, called directly. That reaches the branch a
  regex cannot, which is exactly the branch that leaks the day the regex widens.
* PARSER — `parse_columbia_bank_statement` and `parse_scotiabank_statement`
  driven end to end on an invented statement whose period strip matches their
  own regex and fails `strptime`. R11 survived every seam proof this branch
  had; the whole-tree reader-name rule closed it, and this is the other half —
  evidence that the site is reached through the real parser on both trees.

Read-only and $0: no archive document is opened, nothing is written to the
checkout, and no model is called.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

#: The summary figures the Columbia fixture prints, as WHOLE UNITS. They are
#: rendered into money tokens at build time rather than written as money
#: literals, so this file carries no amount-shaped string at all — which keeps
#: an invented fixture out of the amount scans instead of arguing with them
#: afterwards. Whole units rather than cents for the same reason one level down:
#: the shared privacy scan flags any digit run of five or more, and a run that
#: long collides with the archive's own reference numbers by coincidence. Every
#: value here is four digits or fewer, and all of them are arbitrary — the
#: poisoned period refuses long before any figure is read.
_UNITS = {
    "beginning": 1000,
    "low": 900,
    "credits": 500,
    "average": 950,
    "debits": 400,
    "interest": 0,
    "ending": 1100,
}


def _token(name: str) -> str:
    return f"{_UNITS[name]:,.2f}"


#: An invented Columbia-shaped statement. Every label is a detection marker or
#: a summary label already committed in `analysis/columbia_bank.py`; the account
#: number is the masked form the reader's own `([X\\d]+)` admits; the period is
#: 2031. `{token}` is substituted with the poisoned period token under test.
COLUMBIA_FIXTURE = f"""\
MARKETPLACE CHECKING

Last statement: {{token}}
This statement: December 31, 2031

Account number {'X' * 8}
Beginning balance {_token('beginning')}
Low balance {_token('low')}
Deposits/Additions {_token('credits')}
Average balance {_token('average')}
Withdrawals/Subtractions {_token('debits')}
Interest earned {_token('interest')}
Ending balance {_token('ending')}

DEPOSITS/ADDITIONS
ACH AND ELECTRONIC PAYMENTS/SUBTRACTIONS
DAILY BALANCES
"""

#: An invented Scotiabank-shaped statement, same rules. The trademark footer
#: line is institution furniture and is already a detection marker in
#: `analysis/scotia.py`. The account digits are a repeated pattern rather than
#: a written-out run, for the same reason the figures above are.
SCOTIA_FIXTURE = f"""\
SCOTIABANK
THE BANK OF NOVA SCOTIA

Business Account {'0' * 4} {'1' * 4} {{token}} Dec 31 2031

ACCOUNT DETAILS
"""


def _leaking_surfaces(exc: BaseException, token: str, canary: str, runs) -> list[str]:
    """Which surfaces leaked — the boolean form of `assert_private`."""
    from tests.test_privacy3_boundaries import _leak_surfaces
    import traceback as _traceback

    leaking: list[str] = []
    for surface, text in _leak_surfaces(exc).items():
        if surface == "traceback":
            quoted = {
                frame.line.strip()
                for frame in _traceback.extract_tb(exc.__traceback__)
                if frame.line
            }
            text = "\n".join(
                line
                for line in text.splitlines()
                if line.strip() not in quoted and not line.strip().startswith('File "')
            )
        hit = canary in text
        if token.strip() and token in text:
            hit = True
        if any(run in text for run in runs):
            hit = True
        if hit:
            leaking.append(surface)
    return leaking


def _sites(package: str):
    """The rerouted sites, resolved inside one analysis package.

    Six at `af98349`, ELEVEN here: review MAJOR-2 found four more `date()`
    sites of the site-6 class standing in the same four modules, and the four
    drives that reach them through the real reader are the census's new cells.
    They are imported from `tests/test_raise_privacy3.py` rather than restated,
    the way `_leaking_surfaces` imports the leak rule: a second copy of a drive
    is a second thing to keep in step.
    """
    from tests.test_raise_privacy3 import major2_drives

    chase = importlib.import_module(f"{package}.chase")
    scanned = importlib.import_module(f"{package}.scanned_small_bank")
    date_tokens = importlib.import_module(f"{package}.date_tokens")
    columbia = importlib.import_module(f"{package}.columbia_bank")
    scotia = importlib.import_module(f"{package}.scotia")

    def columbia_parser(token: str):
        return columbia.parse_columbia_bank_statement(COLUMBIA_FIXTURE.format(token=token))

    def scotia_parser(token: str):
        return scotia.parse_scotiabank_statement(SCOTIA_FIXTURE.format(token=token))

    rows = {
        f"{site}<row>": (call, "row", "parser")
        for site, call in major2_drives(package).items()
    }
    return {
        **rows,
        # site name -> (callable, token kind, drive)
        "chase._money_required": (chase._money_required, "money", "seam"),
        "scanned_small_bank._money": (scanned._money, "money", "seam"),
        "scanned_small_bank._iso": (scanned._iso, "date", "seam"),
        "date_tokens.parsed_datetime<columbia_bank.period>": (
            lambda t: date_tokens.parsed_datetime(t, "%B %d, %Y", reader="columbia_bank.period"),
            "date",
            "seam",
        ),
        "date_tokens.parsed_datetime<scotia.period>": (
            lambda t: date_tokens.parsed_datetime(t, "%b %d %Y", reader="scotia.period"),
            "date",
            "seam",
        ),
        "columbia_bank.parse<period>": (columbia_parser, "period", "parser"),
        "scotia.parse<period>": (scotia_parser, "period", "parser"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="10cc722")
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo))

    from tests.test_privacy3_boundaries import CANARY, DIGITS, POISONED_DATE_TOKENS, _digit_runs
    from tests.test_raise_privacy3 import MAJOR2_ROW_TOKENS, POISONED_MONEY_TOKENS
    from tools.hygiene8_base_tree import load_base_analysis

    base = load_base_analysis(args.base, repo=repo, scratch=args.scratch)

    #: Period tokens that MATCH each reader's own period regex and still fail
    #: `strptime` — the only shapes that reach the site through the parser.
    #: Invented, and out of range rather than transcribed.
    poisoned_periods = {
        "day-out-of-range": ("February 30, 2031", "Feb 30 2031"),
        "month-length": ("Februarium 11, 2031", "Fbr 11 2031"),
        "day-31-where-30-is-the-last": ("April 31, 2031", "Apr 31 2031"),
    }

    trees = {"base": base.package, "branch": "analysis"}
    results: dict[str, dict[str, object]] = {}

    for tree, package in trees.items():
        sites = _sites(package)
        cells = 0
        leaking: list[dict[str, object]] = []
        never_raised: list[str] = []
        for site, (call, kind, drive) in sorted(sites.items()):
            if kind == "money":
                tokens = dict(POISONED_MONEY_TOKENS)
            elif kind == "date":
                tokens = dict(POISONED_DATE_TOKENS)
            elif kind == "row":
                tokens = dict(MAJOR2_ROW_TOKENS[site.removesuffix("<row>")])
            else:
                index = 0 if site.startswith("columbia") else 1
                tokens = {name: pair[index] for name, pair in poisoned_periods.items()}
            for shape, token in sorted(tokens.items()):
                cells += 1
                # A printed MONTH or DAY is a TWO-digit run, and the module's
                # default floor is three: `month must be in 1..12, not 13`
                # would be invisible to this census at the three-digit floor,
                # which is exactly the leak review MAJOR-2 named. The floor
                # drops for the row cells and nowhere else, so the six original
                # sites' counts are the ones H4.1 recorded.
                runs = set(_digit_runs(token, 2 if kind == "row" else 3))
                try:
                    call(token)
                except BaseException as exc:  # noqa: BLE001 - the whole point
                    surfaces = _leaking_surfaces(exc, token, CANARY, runs)
                    if surfaces:
                        leaking.append(
                            {
                                "site": site,
                                "drive": drive,
                                "shape": shape,
                                "surfaces": surfaces,
                                "exception": type(exc).__name__,
                            }
                        )
                else:
                    # The grammar READ the token; nothing raised and nothing can
                    # have leaked. Recorded so a site that stops raising cannot
                    # be mistaken for a site that stopped leaking.
                    never_raised.append(f"{site}/{shape}")
        results[tree] = {
            "cells": cells,
            "leaking_cells": len(leaking),
            "read_without_raising": len(never_raised),
            "read_without_raising_names": sorted(never_raised),
            "leaks": leaking,
        }

    report = {
        "base": base.revision,
        "canary": CANARY,
        "digits": DIGITS,
        "sites": sorted(_sites("analysis")),
        **{f"{tree}_leaking_cells": results[tree]["leaking_cells"] for tree in trees},
        "trees": results,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(
        json.dumps(
            {
                "base_cells": results["base"]["cells"],
                "base_leaking_cells": results["base"]["leaking_cells"],
                "branch_cells": results["branch"]["cells"],
                "branch_leaking_cells": results["branch"]["leaking_cells"],
                "sites": len(report["sites"]),
            },
            sort_keys=True,
        )
    )
    for leak in results["branch"]["leaks"]:
        print("BRANCH LEAK " + json.dumps(leak, sort_keys=True))
    for leak in results["base"]["leaks"]:
        print("base leak " + json.dumps(leak, sort_keys=True))
    return 1 if results["branch"]["leaking_cells"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
