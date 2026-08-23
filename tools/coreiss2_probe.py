"""W3 §COREISS2's instruments, committed so the card's numbers are reproducible.

Three measurements, one per subcommand, over the SAME read-only enumeration of
the OCR artifact store:

    python -m tools.coreiss2_probe probe    --data-dir <checkout>/webapp_data
    python -m tools.coreiss2_probe replay   --data-dir <checkout>/webapp_data
    python -m tools.coreiss2_probe privacy  --data-dir <checkout>/webapp_data \
        --diff-from main

* **probe** — the whole-archive non-target probe. Every document in the store
  gets both new registrations' live `detect`, and `parse` wherever either
  claims. It prints how many each registration claims and publishes, and names
  any document outside its census family. This is the card's "nothing else is
  claimed" number.
* **replay** — the family replay: how many of each census family publish. This
  is the number the mutation harness uses as its second, independent killer.
* **privacy** — the standing privacy rule, measured, in TWO passes. The FIGURE
  pass takes every printed money figure, full date, account mask and long
  digit run in the two families' documents; the WORD pass takes every
  alphabetic token of those same documents that is not already present
  anywhere in the BASE revision's tracked source, which is the definition of
  "a word that entered the tree from the archive" and is what makes the
  measurement immune to template furniture and to ordinary English. Both are
  compared against every added line of the branch diff. Prints counts and
  nothing else about the tokens.

READ-ONLY, in the two ways the wave requires. Nothing is written anywhere;
and the `webapp_data` sqlite index is never opened — OCR payloads are reached
by DIRECT file path, enumerating every capability partition of
`ocr_settings_key` and taking the longest offline text per document, which is
the enumeration `tools/regfp_zero_movement_sweep.py` established. It makes no
model call and costs $0.00: `detect` and these two `parse` functions have no
network path at all.

WHY THE POPULATIONS ARE READ FROM THE CENSUS. The two families' `content_sha256`
lists are already committed, in
`docs/moneythumb-replacement/CENSUS_BATCH8_DIGITAL.md`, and re-typing them here
would put a second copy of a population in the tree for the two to drift apart.
This tool parses that file instead, so the census stays the one place a family
is defined.

NO DOCUMENT TEXT, NO FIGURE and NO NAME is printed by any subcommand — the
privacy grep in particular reports COUNTS, because a tool that echoed the
tokens it was checking for would be the leak it exists to prevent.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.parser_registry import (  # noqa: E402
    admissible_text, prepare, registrations, safe_detect,
)
import analysis.parser_registry_entries  # noqa: E402,F401  — populates the registry
from analysis import core_processor_activity_summary as activity_summary  # noqa: E402
from analysis import core_processor_signed_counts as signed_counts  # noqa: E402
from ocr.document import StatementMarkdown  # noqa: E402
from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key  # noqa: E402

CENSUS = ROOT / "docs" / "moneythumb-replacement" / "CENSUS_BATCH8_DIGITAL.md"

#: (registration id, census family name, parse function). The census family is
#: the population this registration is allowed to claim and nothing else.
READERS = (
    (
        "core_processor_signed_counts",
        "business_classic_statement_of_account",
        signed_counts.parse_core_processor_signed_counts_statement,
    ),
    (
        "core_processor_activity_summary",
        "poplar_bluff_activity_summary_running",
        activity_summary.parse_core_processor_activity_summary_statement,
    ),
)

_CAPABILITY_KEYS = [
    ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
    for f, l, v in itertools.product((False, True), repeat=3)
]

#: A printed figure, a full date, an account mask or a long digit run — the
#: token classes the privacy rule names. `(?!\d)` after the cents is what makes
#: this a WHOLE-TOKEN comparison: without it an invented five-figure amount
#: reports a hit on the archive's two-figure one, because every money figure
#: ends in a shorter money figure.
_PRIVACY_TOKEN_RE = re.compile(
    r"X{2,}\d+|\d{1,2}/\d{1,2}/\d{2,4}|\d[\d,]*\.\d{2}(?!\d)|(?<!\d)\d{5,}(?!\d)"
)
#: A word, for the WORD pass. Three characters is the floor at which a token is
#: a word rather than an initial or a fragment of punctuation.
_WORD_RE = re.compile(r"[A-Za-z]{3,}")
#: Tracked files whose bytes are not prose; reading them would only add noise.
_BINARY_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".gz", ".zip", ".xlsx",
     ".woff", ".woff2", ".pyc"}
)


def census_family(name: str) -> set[str]:
    """The `content_sha256` list the committed census gives this family."""
    body = CENSUS.read_text(encoding="utf-8")
    match = re.search(
        r"^### \d+\. `" + re.escape(name) + r"`.*?- \*\*shas:\*\*\n```\n(.*?)```",
        body, re.S | re.M,
    )
    if match is None:
        raise SystemExit(f"census family not found: {name}")
    return {token.strip().upper() for token in match.group(1).split() if token.strip()}


def document_text(artifacts: Path, sha: str) -> str | None:
    """The longest cached OCR text for one document, by DIRECT file path."""
    best: str | None = None
    for key in _CAPABILITY_KEYS:
        composed = cache_key(STAGE_OCR, sha.upper(), key)
        path = artifacts / STAGE_OCR / composed[:2] / f"{composed}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, dict):
            continue
        rendered = StatementMarkdown(
            source_file="x.pdf",
            model=str(document.get("model") or ""),
            pages=[str(page) for page in (document.get("pages") or [])],
        ).to_markdown()
        if best is None or len(rendered) > len(best):
            best = rendered
    return best


def enumerate_store(artifacts: Path):
    """Every document in the store, by payload `input_sha256` -> longest text.

    The store, not a manifest and not `rows.csv`: a population derived from a
    run's own rows inherits that run's cache hits, which is the hole §COUNTSP3
    found. Returns `(documents, artifact_file_count)`.
    """
    documents: dict[str, str] = {}
    files = 0
    for path in (artifacts / STAGE_OCR).rglob("*.json"):
        files += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sha = payload.get("input_sha256")
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(sha, str) or not isinstance(document, dict):
            continue
        rendered = StatementMarkdown(
            source_file="x.pdf",
            model=str(document.get("model") or ""),
            pages=[str(page) for page in (document.get("pages") or [])],
        ).to_markdown()
        sha = sha.upper()
        if sha not in documents or len(rendered) > len(documents[sha]):
            documents[sha] = rendered
    return documents, files


def run_probe(artifacts: Path) -> int:
    documents, files = enumerate_store(artifacts)
    scanned = sum(1 for text in documents.values() if "model: native-pdf-text" not in text[:200])
    print(f"artifact files={files} documents={len(documents)} non-native-text={scanned}")

    registry = {registration.id: registration for registration in registrations()}
    claimed: dict[str, set[str]] = {reader: set() for reader, _, _ in READERS}
    published: dict[str, set[str]] = {reader: set() for reader, _, _ in READERS}
    both = 0
    for sha, markdown in documents.items():
        text = admissible_text(markdown)
        document = prepare(text)
        hits = [
            (reader, parse) for reader, _, parse in READERS
            if safe_detect(registry[reader], document).claims
        ]
        both += len(hits) > 1
        for reader, parse in hits:
            claimed[reader].add(sha)
            if parse(text) is not None:
                published[reader].add(sha)

    failures = 0
    for reader, family, _ in READERS:
        target = census_family(family)
        outside = sorted(sha for sha in claimed[reader] - target)
        unclaimed = sorted(sha for sha in target - claimed[reader])
        unpublished = sorted(sha for sha in target - published[reader])
        failures += len(outside) + len(unclaimed) + len(unpublished)
        print(
            f"{reader}: census family={len(target)} claims={len(claimed[reader])} "
            f"published={len(published[reader])} outside_family={outside} "
            f"family_not_claimed={unclaimed} family_not_published={unpublished}"
        )
    print(f"both_claimed(ambiguous)={both}")
    return 1 if failures or both else 0


def run_replay(artifacts: Path) -> int:
    line = []
    for reader, family, parse in READERS:
        target = sorted(census_family(family))
        published = 0
        for sha in target:
            markdown = document_text(artifacts, sha)
            if markdown is None:
                continue
            if parse(admissible_text(markdown)) is not None:
                published += 1
        line.append(f"{reader}={published}/{len(target)}")
    print("REPLAY " + " ".join(line))
    return 0


def run_privacy(artifacts: Path, diff_from: str) -> int:
    tokens: set[str] = set()
    archive_words: set[str] = set()
    figures = dates = accounts = 0
    for _, family, _ in READERS:
        for sha in sorted(census_family(family)):
            markdown = document_text(artifacts, sha)
            if markdown is None:
                continue
            archive_words |= {word.lower() for word in _WORD_RE.findall(markdown)}
            for token in _PRIVACY_TOKEN_RE.findall(markdown):
                # A printed ZERO is the absence of a figure rather than a
                # figure: both templates print one on their fee lines, as does
                # every synthetic fixture already in this tree.
                if re.fullmatch(r"[\d,]*\.\d{2}", token) and float(token.replace(",", "")) == 0.0:
                    continue
                tokens.add(token)
    for token in tokens:
        if "/" in token:
            dates += 1
        elif "." in token:
            figures += 1
        else:
            accounts += 1

    diff = subprocess.run(
        ["git", "diff", f"{diff_from}...HEAD", "--unified=0"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    added = [
        line[1:] for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    hits = sum(
        1 for line in added for token in _PRIVACY_TOKEN_RE.findall(line) if token in tokens
    )
    # --- the WORD pass ------------------------------------------------------
    # Every alphabetic token of the two families MINUS every alphabetic token
    # already present in the BASE revision's tracked source. The subtraction is
    # what makes this measurable at all: without it the overlap is every
    # ordinary English word and every template label, and the number means
    # nothing. What survives is the archive's own vocabulary — a merchant, a
    # holder, a descriptor keyword — and none of it may appear in the diff.
    tracked = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", diff_from],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout.split()
    known: set[str] = set()
    for relative in tracked:
        if Path(relative).suffix.lower() in _BINARY_SUFFIXES:
            continue
        blob = subprocess.run(
            ["git", "show", f"{diff_from}:{relative}"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout
        known |= {word.lower() for word in _WORD_RE.findall(blob)}
    novel = archive_words - known
    added_words = {word.lower() for word in _WORD_RE.findall("\n".join(added))}
    word_hits = novel & added_words

    print(
        f"privacy tokens from the two families: figures={figures} dates={dates} "
        f"accounts/long-digits={accounts} total={len(tokens)}"
    )
    print(f"archive words NOVEL to {diff_from}'s tracked source: {len(novel)}")
    print(f"added lines in the branch diff: {len(added)}")
    print(f"FOUND: figures/dates/accounts={hits} words={len(word_hits)}")
    return 1 if (hits or word_hits) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("probe", "replay", "privacy"))
    parser.add_argument("--data-dir", required=True, type=Path, help="the webapp_data directory")
    parser.add_argument("--diff-from", default="main", help="privacy: the base revision")
    args = parser.parse_args()
    artifacts = args.data_dir / "artifacts"
    if args.action == "probe":
        return run_probe(artifacts)
    if args.action == "replay":
        return run_replay(artifacts)
    return run_privacy(artifacts, args.diff_from)


if __name__ == "__main__":
    raise SystemExit(main())
