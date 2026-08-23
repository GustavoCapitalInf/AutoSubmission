"""Read a named population of `content_sha256` from a file — W3 §WELCH.

One reader for the three WELCH instruments, and it VALIDATES rather than
splitting. The first revision did not: each tool did its own
`text.split()`, so the comment header of `tools/welch_population.txt` became
a hundred phantom documents. Nothing measured was wrong — the detection probe
still claimed exactly the seventeen and the replay still published exactly the
seventeen — but the bookkeeping around them was, and an instrument whose
bookkeeping can be wrong quietly is an instrument that cannot be trusted when
it says zero.

So a line beginning `#` is a comment, and every remaining token must be a
64-character hexadecimal hash or the file is rejected outright. A population
file this cannot read is an error, never a shorter population.
"""
from __future__ import annotations

import re
from pathlib import Path

_SHA_RE = re.compile(r"^[0-9A-F]{64}$")


def read_population(path: Path) -> list[str]:
    """The distinct content hashes named by `path`, in file order."""
    seen: dict[str, None] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for token in stripped.split():
            candidate = token.upper()
            if not _SHA_RE.match(candidate):
                raise ValueError(
                    f"{path}:{number}: not a content_sha256 "
                    f"({len(token)} characters, expected 64 hexadecimal)"
                )
            seen.setdefault(candidate, None)
    if not seen:
        raise ValueError(f"{path}: names no documents")
    return list(seen)
