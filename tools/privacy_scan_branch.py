"""Does anything a branch ADDS appear in the documents it worked on? — the shared instrument.

The batch-7 BLOCK made a standing rule and, from batch 8, one committed tool
rather than one per cell: NO archive content may enter tracked source — not a
balance, an amount, a name, an account number, a date, nor an "example" block
copied off a page. This builds the list of printed tokens from every document
in a NAMED population (cached OCR/native text, by direct artifact path, $0) and
greps the branch's ADDED lines for each one, class by class, with file:line.

    python tools/privacy_scan_branch.py --shas population.txt \
        --data-dir <main-checkout>/webapp_data --base 10cc722 --ref wave8-frostozk

    # a population from the run of record's rows.csv instead of a file:
    python tools/privacy_scan_branch.py --rows discovery_reports/<run>/rows.csv \
        --where parser_id=td_canada_native,td_canada_french --data-dir ... --base ... --ref ...

Token classes, taken from the documents rather than from memory:

* MONEY — every printed money figure carrying cents (`1,234.56`), with and
  without its separators;
* DIGITS — every digit run of `--digit-min` (default 5) or more: account,
  cheque, reference and authorisation numbers, telephone digits, ZIP+4;
* DATES — every fully-qualified date, numeric (`mm/dd/yy`, `mm/dd/yyyy`,
  `yyyy-mm-dd`) or spelled (`January 5, 2031`, `5 January 2026`, `Jan 5 2026`);
* WORDS — every alphabetic word of `--word-min` (default 4) or more characters,
  upper-cased, and every two-word sequence of them (a name whose halves are each
  ordinary).

What is excluded, and why each exclusion is safe rather than convenient: a token
that ALREADY OCCURS IN THE TRACKED TEXT TREE AT `--base`. This branch cannot be
the thing that introduced it, and the class is almost entirely template
vocabulary — `Date`, `Amount`, `Balance` — plus institution names the committed
census already carries. Bare `mm/dd` day tokens are not scanned: they identify
nobody, and every fixture must print some.

What is scanned: the diff `--base...--ref`, ADDED lines only, every text file —
production, tests, tools, fixtures, documentation. `--include-tree` additionally
scans every tracked text file at `--ref` in full (for a branch that inherited a
leak from an earlier commit).

TREE AUDITS NEED THE ROOT COMMIT AS `--base`. The base-tree exclusion removes
every token that already sits in the tracked tree at `--base` — which, for a
token inherited from an earlier commit, is exactly the token you are looking
for. `--include-tree --base 10cc722` therefore proves only that no NEW archive
token was added (SCAN-HYGIENE closure, batch 8, found this the hard way). For
an audit of what the tree already carries, pass the repository's root commit:

    python tools/privacy_scan_branch.py --shas population.txt --data-dir ... \
        --base "$(git rev-list --max-parents=0 HEAD)" --ref train8 --include-tree

and adjudicate the candidates by class.

THE EXCLUSION TABLE (batch 9, FIXTURE-PRIVACY). A whole-tree audit against a
3,351-document universe prints ~3.5x10^5 distinct money figures and ~2x10^5
digit runs, so a candidate is not yet a finding: some shapes cannot carry
archive identity at all, and some are archive text on purpose. Every rule below
names a SHAPE and is applied to every file alike — never a file list, never a
token list — and `tests/test_privacy_scan_exclusions.py` proves each one
matches exactly the shape it names and NOTHING wider (in particular that none
of them silences a bare account number). `--no-exclusions` reports the raw scan.

===================== ======================================================
rule                   what it excludes, and why that is safe
===================== ======================================================
``words_class``        class WORDS, ALL OF IT. Institution and template
                       vocabulary: `DATE`, `AMOUNT`, `DEPOSIT`, an
                       issuer's own name. An alphabetic token carries no
                       figure and no identifier, and the census already
                       names every institution. The standing exclusion
                       applied at the batch-8 train.

                       WHAT THAT COSTS, SAID PLAINLY: `tokens_of` builds
                       two-word sequences on purpose -- a name whose
                       halves are each ordinary -- and this rule then
                       discards every WORDS hit, so THE TREE IS UNAUDITED
                       FOR CUSTOMER NAMES BY CONSTRUCTION. A holder name
                       in tracked source would not be reported by this
                       instrument. The card's definition of done is
                       scoped to MONEY / DIGITS / DATES, so the scope is
                       correct, but the identity paragraph it cites says
                       'not a balance, an amount, A NAME, an account
                       number, a date' -- and names are the half no scan
                       here has ever looked at. That is a card, and it
                       has to be written knowing this.
``corpus_cache``       any path under ``tests/corpus_cache/``. That directory
                       IS cached archive text, committed on purpose so the
                       pinned corpus runs offline; scanning it re-finds the
                       archive in the archive. The standing exclusion applied
                       at the batch-8 train.
``round_money``        a MONEY token ending ``.00``, WHATEVER ITS
                       MAGNITUDE. This is the program's widest standing
                       exclusion and the one whose justification has to
                       be stated honestly: `100.00` is the bound of a
                       test's tolerance as readily as it is a deposit,
                       and a small round figure reconstructs nothing --
                       but the rule does not stop at small. Measured
                       over the whole tree it also excuses thousands of
                       four-figure and hundreds of five-figure round
                       amounts, and a five-figure round deposit beside a
                       date and an institution is not a tolerance bound.
                       The class is excused because the program CHOSE to
                       accept it wholesale at the batch-8 train, not
                       because it cannot identify. Narrowing it is not
                       this card's to do; misdescribing it would be.
``subunit_money``      a MONEY token whose integer part is a bare ``0``
                       (``0.01``..``0.99``). Cent and sub-unit CODE CONSTANTS
                       — a reconciliation tolerance, a rate floor. A
                       sub-unit magnitude identifies nobody and reconstructs
                       nothing.
``hex_sha_substring``  a DIGITS token that SITS INSIDE a name this program
                       gives one of its OWN things: 7..64 hex characters
                       carrying at least one hex LETTER — a content sha, or
                       the abbreviated git object name a record writes as
                       `f14282e`. A sha is a hash OF a document, never a token
                       FROM it. Two things keep the rule narrow. The required
                       letter: an account, cheque, card or reference number is
                       all digits and cannot satisfy the shape at ANY length,
                       so the rule cannot silence one — which a bare
                       `[0-9A-F]{16,64}` would (a 16-digit card number is
                       "hex"). And the POSITION: every occurrence of the token
                       on the line must fall inside a hex run, so a digit run
                       standing on its own beside a sha
                       (`ACCOUNT 7000004 AT COMMIT F7000004E`) is still a
                       finding. WHAT THE 7-CHARACTER FLOOR COSTS, MEASURED:
                       the floor exists because these records name a commit
                       in seven characters, and it is the widest part of the
                       rule. Of the sites this rule excuses at the closure
                       tip, one in six is excused by a run SHORTER than a
                       16-character sha prefix, and a 7..15-character mixed
                       run is a shape a reference or a terminal id can
                       accidentally take. The exact counts, and the rows /
                       sites distinction that makes them look like two
                       different numbers, are in the closure record. Raising
                       the floor is a card, not a patch: it would re-report
                       every abbreviated object name these records write.
``docs_session_date``  a DATES token in ``docs/`` that is an ISO date on or
                       after ``2026-07-01``. Those are the PROGRAM's own
                       session dates — when a cell ran, when a train closed —
                       written by this project after the archive was frozen
                       on 2026-08-06. A document date and a session date are
                       different facts that happen to share a shape, so the
                       rule is bounded by both the directory that holds the
                       program's records and the date the program began.

                       THE RESIDUAL EXPOSURE, NAMED: the archive was frozen
                       on 2026-08-06, so document dates DO reach into the
                       program's era, and a census entry inside ``docs/``
                       that quotes a statement period ending in ISO form
                       between 2026-07-01 and the freeze is silenced by
                       this rule. Measured at this tip: one site. The rule
                       is kept because the alternative is worse -- every
                       session date the records write becomes residue -- and
                       because the numeric `mm/dd/yyyy` form a statement
                       actually prints is untouched. The bound is pinned by
                       tests on both sides of it.
``institution_zip``    a DIGITS token of exactly five digits standing in a
                       POSTAL ADDRESS: a state abbreviation immediately before
                       it AND the furniture an address carries — a city and
                       its comma (`OZARK, AR 99999`), or a post-office box
                       WITH A CITY between it and the state, in the same
                       clause, which ends at a full stop, a dash or a segment
                       separator (`P.O. BOX 196 OZARK AR 99999`). A ZIP+4 tail
                       strengthens either shape and is NEVER
                       evidence on its own: `MEMBER ID 84213-6789` is a
                       member number with a suffix, not an address. Neither is
                       the mere absence of punctuation: a box marker followed
                       by an unbroken run of ordinary characters used to reach
                       an ACH company id (`PO BOX 1558 CCD CO# 45678 TRACE`),
                       so the run is TEMPERED against the words this archive
                       prints to introduce an identity, and a NUMBER SIGN is
                       barred from the gap in both shapes. The
                       postal code
                       of an institution's own service address is the
                       furniture the doctrine allows a detection marker to
                       carry; it identifies a branch, never a customer. The
                       abbreviation alone is NOT the shape — see the note on
                       `ADDRESS_ZIP_RES` for why that reading silenced account
                       and member numbers.
===================== ======================================================

Exit 1 on any hit the table does not exclude, 0 on none. The JSON summary goes
to stdout; each non-excluded hit goes to stderr as
`HIT <class> <file>:<line> <token>` — the report is for the operator's terminal
and must never itself be committed.

SELF-CHECK (the FROST-OZK / ATB-MEASURE lesson): a scan written through a
shell heredoc once lost the backslash of every `\\b` to a 0x08 byte and matched
nothing, so its zeros were vacuous. On import this module refuses to run unless
its own file carries no control byte and every pattern matches a synthetic
instance of the shape it names.

READ-ONLY over the archive; OCR artifacts by direct file path; no sqlite index;
no OCR; no hosted model; $0.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MONEY_RE = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})*\.\d{2}(?![\d.])|(?<![\d.])\d{4,}\.\d{2}(?![\d.])")
NUMERIC_DATE_RE = re.compile(
    r"(?<![\d/])(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})(?![\d/])"
)
_MONTHS = (
    "JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUNE?|JULY?|AUG(?:UST)?|"
    "SEPT?(?:EMBER)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?"
)
SPELLED_DATE_RE = re.compile(
    rf"\b(?:(?:{_MONTHS})\.? \d{{1,2}},? \d{{4}}|\d{{1,2}} (?:{_MONTHS})\.? \d{{4}})\b"
)
WORD_RE = re.compile(r"[A-Z]{4,}")

#: Tracked text formats. Everything else in the tree is a PDF of the validated
#: corpus, which is not source and cannot be what a branch added.
#:
#: `log`, `shas` and `ps1` were outside this set until FIXTURE-PRIVACY-2, which
#: means the tree carried tracked text NO SCAN HAD EVER READ — including a
#: 1,194-line run log written by a tool that prints document text. A suffix
#: list is a claim about what is worth reading, and a file the list forgets is
#: not audited by anything: the first review called this "the first item of the
#: follow-up card" and it is closed here. The list is now every text format
#: this tree actually tracks; `git ls-files` finds nothing outside it that is
#: not a PDF.
TEXT_SUFFIXES = frozenset(
    "py md txt json csv yml yaml toml cfg ini html js ts tsx jsx css sh bat "
    "gitignore in rst log shas ps1".split()
)

#: NAMED RESIDUE CLASSES — NOT exclusions, and the distinction is the point.
#: An exclusion says a shape cannot carry archive identity. A named class says
#: the opposite: this residue IS archive identity, it is here on purpose, and
#: it needs a RULING rather than a rule. Naming it costs nothing (the sites
#: stay residue, the exit code still follows them) and buys the one thing the
#: record has asked for three times: a number to put in front of the decision.
#:
#: `benchmark_truth_csv` — the three per-statement audited expectation files
#: read as DATA by `benchmark/expectations.py`. They carry real balances,
#: account masks and periods, one row per pinned document, and a class band is
#: not a float, so redacting them breaks the benchmark. One of them also holds
#: the last copy of the account number the P0 card was written to remove. That
#: is ruling R3's, not a scanner's.
NAMED_RESIDUE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("benchmark_truth_csv", (
        "docs/adb-audit-results.csv",
        "docs/balance-metrics-audit-results.csv",
        "docs/new-statement-audit-results.csv",
    )),
)


def residue_class(path: str) -> str | None:
    """The named residue class this path belongs to, or None.

    Deliberately NOT consulted by `excluded_by`: a named class is counted, not
    silenced. A future ruling can move one of these into the exclusion table,
    and that move should be a visible edit with a shape argument behind it —
    never a side effect of a reporting convenience.
    """
    for name, paths in NAMED_RESIDUE:
        if path in paths:
            return name
    return None

_CONTROL_BYTES = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")

#: A name this program gives one of its OWN things: a content sha, or the
#: abbreviated git object name the records write as `f14282e` / `32116b3`.
#: 7 to 64 hex characters, bounded by something that is not alphanumeric, and
#: carrying AT LEAST ONE hex letter.
#:
#: The letter is the whole safety of the rule, and it is why the shape is not
#: simply `[0-9A-F]{16,64}` as the card first drew it: a 16-digit card number,
#: a 20-digit reference, a 42-digit run are all "hex" by that pattern, and a
#: rule that reads them as shas silences exactly the identifiers this scan
#: exists to find. A sha without a single a–f is a 1-in-10^13 accident at 64
#: characters (1 in ~1,100 at a 16-character prefix), and when one does occur
#: it is REPORTED rather than hidden — the safe direction.
#:
#: (The scanner upper-cases every line before it matches, so the rule cannot
#: ask for lower case, and does not need to.)
HEX_RUN_RE = re.compile(
    r"(?<![0-9A-Z])(?=[0-9A-F]{7,64}(?![0-9A-Z]))[0-9A-F]*[A-F][0-9A-F]*(?![0-9A-Z])"
)
#: A state abbreviation, then at most eight characters that are not digits,
#: then the five-digit code itself. The gap is short and digit-free so that the
#: rule cannot reach past an address onto an unrelated number, and both US
#: territories and the DC code are included.
_STATE = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|"
    "MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|PR|RI|SC|SD|TN|TX|UT|VT|VA|"
    "VI|WA|WV|WI|WY"
)
#: At most eight characters between the abbreviation and the code, none of
#: them a digit and NONE OF THEM A NUMBER SIGN. `#` is the mark this archive
#: puts in front of an identifier — `CO# 45678`, `NO# 12345` — and a postal
#: code never carries one between its state and its digits. The character is
#: therefore evidence AGAINST an address, and the cheapest place to say so is
#: the gap both address shapes share.
_ZIP_GAP = r"[^0-9#]{0,8}"
#: THE ABBREVIATION IS NECESSARY AND NEVER SUFFICIENT. The scanner upper-cases
#: every line before it matches, and about half the abbreviation list is an
#: ordinary English word or ordinary statement furniture once upper-cased:
#: `IN`, `OR`, `OK`, `ID`, `CO`, `ME`, `LA`, `MA`, `MS`, `PA`, `MI`, `MT`,
#: `NE`, `AL`, `DE`, `HI`, `CA`. `\b...\b` does not help — these ARE whole
#: words. A rule of "abbreviation, then five digits" therefore reads
#: `MEMBER ID 84213` as a postal code and silences a credit-union member
#: number; it does the same to `THE ACCOUNT ENDING IN 84213`, to an ACH
#: originator id (`CCD CO# 45678 TRACE`), to an authorisation code
#: (`AUTH OK 84213`) and to a cheque number (`CHECK NO OR 84213`). Every one
#: of those is a printed identity this scan exists to find, so the rule asks
#: for the ADDRESS as well, in one of the three shapes an address is written:
#:
#: * ``CITY_STATE_ZIP`` — a city, its comma, the abbreviation, the code
#:   (`RALEIGH, NC 99999`). The comma is the city/state junction and a
#:   transaction description does not print one before a state word.
#:   WHAT THIS SHAPE CANNOT TELL APART, recorded rather than hoped away: the
#:   comma says a phrase ended, not that a city did. A company suffix
#:   (`ACME & SONS, CO 84213`), a list item (`MEMBER, ID 84213`) or any
#:   comma-terminated word followed by an abbreviation-shaped token and five
#:   digits reads as an address to this rule. None occurs in the tree today
#:   and each is a stilted line to print, but the shape is genuinely
#:   ambiguous and the next rule that leans on it should know.
#:
#: A ZIP+4 tail is NOT one of the shapes. It was, and the first re-review
#: threw it out: `NNNNN-NNNN` after an abbreviation-shaped word carries no
#: address evidence at all, and the archive prints identifiers in exactly
#: that shape — `MEMBER ID 84213-6789`, `CARD ENDING IN 84213-6789`,
#: `LOAN NO. OR 84213-1234` were all silenced by it. The tail STRENGTHENS
#: either shape above (both accept it, because neither forbids what follows
#: the five digits), and on its own it says nothing. Evidence of an address
#: is a city or a box; a postal-looking suffix is not evidence, it is a
#: coincidence a cheque number can have.
#: * ``BOX_CLAUSE_ZIP`` — a post-office box in the SAME clause, at most 70
#:   characters ahead, never across a clause end, AND WITH ADDRESS FURNITURE
#:   BETWEEN THE BOX AND THE STATE (`PO BOX 609 PITTSBURGH PA 99999`). A box
#:   marker is doctrine-sanctioned institution furniture; bounding it to the
#:   clause is what stops a box in one sentence from excusing a number in the
#:   next. The clause ends at a FULL STOP, a DASH or a segment separator, and
#:   the first re-review is why the list is that long: a clause bounded only at
#:   `;` and `|` still reached across `PO BOX 609 - ACCOUNT ENDING IN 84213`
#:   and across `REMIT TO P.O. BOX 609. AUTH OK 84213`, which are an account
#:   tail and an authorisation code standing AFTER an address, not part of one.
#:   A postal address is written as one unbroken run of words; the punctuation
#:   that ends a sentence or splits a segment is exactly where it stops.
#:
#:   THE ABSENCE OF PUNCTUATION IS NOT FURNITURE, which is what the second
#:   re-review's residual said: `PO BOX 1558 CCD CO# 45678 TRACE` carries no
#:   clause end anywhere, so the box reached straight across an unbroken run of
#:   ordinary characters to `CO` and silenced an ACH company id — the shape
#:   `analysis/core_processor_signed_counts.py`'s own grammar documents. The
#:   rule now asks for what an address actually prints between its box and its
#:   state: a CITY, which is a word of four letters or more standing at a word
#:   boundary and not one of the words this archive uses to introduce an
#:   identity. Three letters (`CCD`) are not a city. `MEMBER`, `ACCOUNT`,
#:   `AUTH`, `CHECK`, `LOAN`, `CARD`, `POLICY`, `TRACE`, `NO` and the rest of
#:   `_IDENTIFIER_WORD` are words, but they are the words that say the digits
#:   beside them are an identity — so the run from the box to the state is
#:   TEMPERED and may not cross one of them at all, in either half.
#:
#:   WHAT REMAINS, SAID PLAINLY: `PO BOX 196 <city-shaped word not in the
#:   list> <word-shaped abbreviation> <five digits>` is still excused, because
#:   by SHAPE it is `PO BOX 609 PITTSBURGH PA 99999`. The nearest real example
#:   is a company suffix standing where a city would (`PO BOX 1558 ACME CORP
#:   CO 45678`, with no `#` to give it away). This is the same
#:   irreducible ambiguity `CITY_STATE_ZIP` carries with its comma, one shape
#:   over, and no amount of punctuation or word-length reasoning closes it: the
#:   only rule that would is a state-to-ZIP-prefix consistency table (`ID` runs
#:   832xx-838xx, so `MEMBER ID 84213` could never be an Idaho address), which
#:   is a card of its own — every invented address fixture in this tree pairs a
#:   state with a code that does not belong to it, so that table re-reports
#:   them all and its cost has to be measured before it is chosen.
#:
#: The junk class allows what upper-casing a regex SOURCE leaves between the
#: comma and the abbreviation: `\s` becomes `\S`, `\w` becomes `\W`, and a
#: detection marker such as `r"P\.?O\.? BOX 196\s+OZARK,\s*AR\s*99999"` is
#: read by this scanner as its own source text.
_ADDRESS_JUNK = r"(?:\\[SW]|[^0-9A-Z])"
CITY_STATE_ZIP = re.compile(
    rf"[A-Z]{_ADDRESS_JUNK}{{0,2}},{_ADDRESS_JUNK}{{0,4}}(?:{_STATE})\b{_ZIP_GAP}(\d{{5}})(?!\d)"
)
#: One character of the run between the box marker and the state. A postal
#: address does not carry a full stop, a dash or a segment separator between
#: its box and its state, and each of those is where the next fact begins.
_CLAUSE_CHAR = r"[^;|.\-\u2013\u2014!?()\[\]]"
#: The words this archive prints to say that the digits beside them are an
#: IDENTITY rather than a place. They are city-shaped \u2014 four letters or more,
#: standing at a word boundary \u2014 which is exactly why they have to be named:
#: `PO BOX 196 MEMBER ID 84213` reads as `PO BOX 609 PITTSBURGH PA 99999` to
#: any rule that only counts letters, and `ID` is Idaho. This is a vocabulary
#: and it is incomplete by construction; it is here because the six identifier
#: classes the first review blocked on are all introduced by one of these
#: words, and a rule that survives them is worth more than one that does not.
_IDENTIFIER_WORD = (
    "ACCOUNT|ACCT|ACH|AUTH|AUTHORISATION|AUTHORIZATION|BATCH|CARD|CCD|CHECK|"
    "CHEQUE|CLIENT|CONFIRMATION|CTX|CUSTOMER|DEPOSIT|INVOICE|ITEM|LOAN|MEMBER|"
    "MERCHANT|NO|NUM|NUMBER|ORIGINATOR|POLICY|PPD|REF|REFERENCE|ROUTING|SEQ|"
    "SEQUENCE|SHARE|TERMINAL|TRACE|TRANSACTION|TRANSIT|WITHDRAWAL"
)
#: A city-shaped word: four letters or more, beginning at a word BOUNDARY, and
#: not one of the words above.
#:
#: THE `\b` CARRIES NO MUTANT, and the reason is worth writing down rather than
#: leaving as a gap in the table. Its job would be to stop the tail of a longer
#: word standing in for a city — without it, `MEMBER` offers `EMBER`. The
#: tempered run already makes that unreachable: to place a city inside
#: `MEMBER` the run would have to cover the `M` at that word's head, which is
#: exactly where the tempering refuses, and a run can never START inside a word
#: because it begins at `BOX\b`. A mutant that removes the `\b` therefore
#: cannot be killed by any line, which is the mutation table saying the
#: character is redundant. It is kept because it is what "a city-shaped WORD"
#: means, and because it holds if the tempering is ever loosened; the mutant
#: that stands in its place attacks the LENGTH, which is discriminating.
_CITY_WORD = rf"\b(?!(?:{_IDENTIFIER_WORD})\b)[A-Z]{{4,}}"
#: One character of the run, TEMPERED: it may be anything the clause allows,
#: except that it may not stand at the head of an identifier word. A tempered
#: run cannot cross `MEMBER`, `AUTH`, `CCD` or `NO`, which is what makes
#: "there is a city between the box and the state" mean what it says. Written
#: this way rather than as "furniture immediately before the state" because a
#: city is not always one word: `PO BOX <n> GREEN BAY WI <zip>` is a genuine
#: institution address whose last word before the state is three letters long,
#: and a rule that cannot read a two-word city will keep costing.
_TEMPERED_CHAR = rf"(?:(?!\b(?:{_IDENTIFIER_WORD})\b){_CLAUSE_CHAR})"
#: The two runs are bounded to 50 and 20, not to 70 and 20, so that the total
#: distance from the box marker to the state stays the SEVENTY the clause bound
#: has always been. That keeps this shape strictly NARROWER than the one it
#: replaces — same reach, tempered characters, and a city that must fit inside
#: it — which is why no line in this tree can gain an exclusion from this
#: change, only lose one.
BOX_CLAUSE_ZIP = re.compile(
    rf"\bP\.?\s?O\.?\s?BOX\b{_TEMPERED_CHAR}{{0,50}}?{_CITY_WORD}"
    rf"{_TEMPERED_CHAR}{{0,20}}?\b(?:{_STATE})\b{_ZIP_GAP}(\d{{5}})(?!\d)"
)
ADDRESS_ZIP_RES = (CITY_STATE_ZIP, BOX_CLAUSE_ZIP)
#: The archive was frozen on 2026-08-06; every record this program writes about
#: its own work is dated after it began, and the first batch-9 record is dated
#: from July 2026 on. Bounded by BOTH the directory and the date.
PROGRAM_ERA = "2026-07-01"
ISO_DATE_RE = re.compile(r"\A20\d\d-\d\d-\d\d\Z")


def _words_class(cls: str, path: str, token: str, line: str) -> bool:
    return cls == "WORDS"


def _corpus_cache(cls: str, path: str, token: str, line: str) -> bool:
    return path.startswith("tests/corpus_cache/")


def _round_money(cls: str, path: str, token: str, line: str) -> bool:
    return cls == "MONEY" and token.endswith(".00")


def _subunit_money(cls: str, path: str, token: str, line: str) -> bool:
    return cls == "MONEY" and re.fullmatch(r"0\.\d\d", token) is not None


def _occurrences(token: str, line: str) -> list[int]:
    """Every start offset of `token` in `line`, overlapping ones included."""
    found: list[int] = []
    at = line.find(token)
    while at != -1:
        found.append(at)
        at = line.find(token, at + 1)
    return found


def _hex_sha_substring(cls: str, path: str, token: str, line: str) -> bool:
    """The token has to SIT INSIDE a sha, at every position it occupies.

    Asking `any(token in run for run in HEX_RUN_RE.findall(line))` asks whether
    the characters appear somewhere inside some sha on the line, which is not
    the same question: `ACCOUNT 7000004 AT COMMIT F7000004E` prints an account
    number that is also a substring of the commit name beside it, and the
    line-scoped form excused it. So the rule asks about the OCCURRENCE — every
    place the token stands must fall inside a hex run, and a token that stands
    anywhere on its own is a finding however many shas share its line.
    """
    if cls != "DIGITS":
        return False
    runs = [match.span() for match in HEX_RUN_RE.finditer(line)]
    if not runs:
        return False
    places = _occurrences(token, line)
    return bool(places) and all(
        any(start <= at and at + len(token) <= end for start, end in runs)
        for at in places
    )


def _docs_session_date(cls: str, path: str, token: str, line: str) -> bool:
    """The program's own session dates, inside the program's own records.

    A NAMED RESIDUE path is carved out, and the reason is not bookkeeping: the
    named classes are files that hold DOCUMENT facts on purpose, one row per
    pinned statement. A date in `docs/adb-audit-results.csv` is a statement
    period, not the day a cell ran, and the two only share a shape. Counting a
    class and then letting an exclusion silence part of it would make the count
    a lie — and the reviewer measured exactly one site living on that boundary.
    """
    return (
        cls == "DATES"
        and path.startswith("docs/")
        and residue_class(path) is None
        and ISO_DATE_RE.match(token) is not None
        and token >= PROGRAM_ERA
    )


def _institution_zip(cls: str, path: str, token: str, line: str) -> bool:
    return (
        cls == "DIGITS"
        and len(token) == 5
        and any(token in pattern.findall(line) for pattern in ADDRESS_ZIP_RES)
    )


#: The table itself, in the order it is applied. A hit is attributed to the
#: FIRST rule that claims it, so the per-rule counts partition the raw hits.
EXCLUSIONS: tuple[tuple[str, object], ...] = (
    ("words_class", _words_class),
    ("corpus_cache", _corpus_cache),
    ("round_money", _round_money),
    ("subunit_money", _subunit_money),
    ("hex_sha_substring", _hex_sha_substring),
    ("docs_session_date", _docs_session_date),
    ("institution_zip", _institution_zip),
)

#: (rule, class, path, token, line, expected) — the shape each rule names and
#: the nearest thing it must NOT reach. Checked on import, so the table cannot
#: go inert the way a heredoc once made the patterns inert.
_EXCLUSION_SAMPLES = (
    ("words_class", "WORDS", "a.py", "BALANCE", "BALANCE", True),
    ("words_class", "DIGITS", "a.py", "98989", "98989", False),
    ("corpus_cache", "MONEY", "tests/corpus_cache/ocr/x.md", "909,090.91", "909,090.91", True),
    ("corpus_cache", "MONEY", "tests/test_x.py", "909,090.91", "909,090.91", False),
    ("round_money", "MONEY", "a.py", "100.00", "100.00", True),
    ("round_money", "MONEY", "a.py", "8909,090.91", "8909,090.91", False),
    ("subunit_money", "MONEY", "a.py", "0.01", "0.01", True),
    ("subunit_money", "MONEY", "a.py", "818,181.81", "818,181.81", False),
    ("hex_sha_substring", "DIGITS", "a.py", "98989", "AB98989CDEF09898967", True),
    ("hex_sha_substring", "DIGITS", "a.py", "7000004", "COMMIT F7000004E LANDED", True),
    ("hex_sha_substring", "DIGITS", "a.py", "7000004",
     "ACCOUNT 7000004 AT COMMIT F7000004E", False),
    ("hex_sha_substring", "DIGITS", "a.py", "98989", "ACCOUNT 98989", False),
    ("hex_sha_substring", "DIGITS", "a.py", "70000000011", "RUN 70000000011", False),
    ("docs_session_date", "DATES", "docs/x.md", "2026-08-29", "ON 2026-08-29", True),
    ("docs_session_date", "DATES", "docs/adb-audit-results.csv", "2026-08-29",
     "SHA,2026-08-29,2026-08-29", False),
    ("docs_session_date", "DATES", "docs/x.md", "2019-11-21", "ON 2019-11-21", False),
    ("docs_session_date", "DATES", "docs/x.md", "2001-02-03", "ON 2001-02-03", False),
    ("docs_session_date", "DATES", "tests/x.py", "2026-08-29", "ON 2026-08-29", False),
    ("institution_zip", "DIGITS", "a.py", "99999", "OZARK, AR 99999", True),
    ("institution_zip", "DIGITS", "a.py", "95959", "PO BOX 1962 COLUMBUS OH 95959-1558", True),
    ("institution_zip", "DIGITS", "a.py", "84213", "PO BOX 609 - ACCOUNT ENDING IN 84213", False),
    ("institution_zip", "DIGITS", "a.py", "84213", "MEMBER ID 84213-6789", False),
    ("institution_zip", "DIGITS", "a.py", "95959", "PO BOX 609 PITTSBURGH PA 95959", True),
    ("institution_zip", "DIGITS", "a.py", "98989", "ACCOUNT 98989", False),
    ("institution_zip", "DIGITS", "a.py", "9898967", "OZARK, AR 9898967", False),
    # The vocabulary, not the geometry: an abbreviation that is also a word.
    ("institution_zip", "DIGITS", "a.py", "84213", "MEMBER ID 84213", False),
    ("institution_zip", "DIGITS", "a.py", "45678", "CCD CO# 45678 TRACE", False),
    ("institution_zip", "DIGITS", "a.py", "84213", "AUTH OK 84213", False),
    # A box marker in front of the same lines does not make them addresses.
    ("institution_zip", "DIGITS", "a.py", "45678", "PO BOX 1558 CCD CO# 45678 TRACE", False),
    ("institution_zip", "DIGITS", "a.py", "84213", "PO BOX 196 MEMBER ID 84213", False),
    # A city may be two words, the second of them short.
    ("institution_zip", "DIGITS", "a.py", "95959", "PO BOX 1962 GREEN BAY WI 95959-9097", True),
)


def excluded_by(cls: str, path: str, token: str, line: str) -> str | None:
    """The first rule of the table that claims this hit, or None."""
    for name, rule in EXCLUSIONS:
        if rule(cls, path, token, line):  # type: ignore[operator]
            return name
    return None


def self_check() -> None:
    """Refuse to run as an inert instrument."""
    own = Path(__file__).read_bytes()
    found = _CONTROL_BYTES.findall(own)
    if found:
        raise SystemExit(f"privacy_scan_branch.py carries {len(found)} control byte(s); refusing to run")
    samples = {
        "MONEY_RE": (MONEY_RE, "TOTAL 12,345.67 AND 987.65 AND 9898967.89"),
        "NUMERIC_DATE_RE": (NUMERIC_DATE_RE, "ON 01/31/2031 OR 1/2/31 OR 2031-01-31"),
        "SPELLED_DATE_RE": (SPELLED_DATE_RE, "ON JANUARY 5, 2031 AND 5 FEB 2031 AND SEPT 30 2030"),
        "WORD_RE": (WORD_RE, "HOLDER NAME"),
    }
    for name, (pattern, sample) in samples.items():
        if not pattern.search(sample):
            raise SystemExit(f"{name} matches nothing in its own sample; refusing to run")
    if len(SPELLED_DATE_RE.findall("ON JANUARY 5, 2031 AND 5 FEB 2031 AND SEPT 30 2030")) != 3:
        raise SystemExit("SPELLED_DATE_RE does not match all three spelled shapes; refusing to run")
    named = {name for name, _ in EXCLUSIONS}
    for rule, cls, path, token, line, expected in _EXCLUSION_SAMPLES:
        if rule not in named:
            raise SystemExit(f"exclusion sample names {rule!r}, which is not in the table")
        got = excluded_by(cls, path, token, line) == rule
        if got is not expected:
            raise SystemExit(
                f"exclusion {rule!r} answers {got} for its own sample, expected {expected}; refusing to run"
            )
    for name in named:
        if not any(sample[0] == name for sample in _EXCLUSION_SAMPLES):
            raise SystemExit(f"exclusion {name!r} carries no sample; refusing to run")
    for name, paths in NAMED_RESIDUE:
        if not paths:
            raise SystemExit(f"named residue class {name!r} names no path; refusing to run")
        for path in paths:
            if residue_class(path) != name:
                raise SystemExit(f"named residue class {name!r} does not claim {path!r}")
            if path.rsplit(".", 1)[-1].lower() not in TEXT_SUFFIXES:
                raise SystemExit(f"named residue class {name!r} names {path!r}, which is never scanned")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shas", action="append", default=[], type=Path,
                        help="file of content_sha256 values, one per line, '#' comments")
    parser.add_argument("--sha", action="append", default=[], help="a single content_sha256")
    parser.add_argument("--rows", type=Path, default=None, help="a run's rows.csv")
    parser.add_argument("--where", action="append", default=[],
                        help="rows.csv filter key=v1,v2 (repeatable; all must hold)")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--digit-min", type=int, default=5)
    parser.add_argument("--word-min", type=int, default=4)
    parser.add_argument("--include-tree", action="store_true")
    parser.add_argument("--no-exclusions", action="store_true",
                        help="report the RAW scan: attribute nothing to the exclusion table")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def population(args: argparse.Namespace) -> list[str]:
    shas: set[str] = set(s.strip().upper() for s in args.sha)
    for path in args.shas:
        for line in path.read_text(encoding="utf-8").splitlines():
            token = line.split("#", 1)[0].strip().upper()
            if token:
                shas.add(token)
    if args.rows is not None:
        filters = []
        for clause in args.where:
            key, _, values = clause.partition("=")
            filters.append((key, set(v.strip() for v in values.split(","))))
        with args.rows.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if all(row.get(key, "") in values for key, values in filters):
                    if row.get("content_sha256"):
                        shas.add(row["content_sha256"].upper())
    bad = sorted(s for s in shas if not re.fullmatch(r"[0-9A-F]{64}", s))
    if bad:
        raise SystemExit(f"{len(bad)} population entries are not 64-hex shas: {bad[:3]}")
    return sorted(shas)


def cached_text(root: Path, sha: str, ocr_keys: list[str]) -> str | None:
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import STAGE_OCR, cache_key

    best = None
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
        text = StatementMarkdown(
            source_file="scan.pdf", model=str(document.get("model") or ""), pages=pages
        ).to_markdown()
        if best is None or len(text) > len(best):
            best = text
    return best


def tokens_of(text: str, digit_min: int, word_min: int) -> dict[str, set[str]]:
    upper = text.upper()
    classes: dict[str, set[str]] = {"MONEY": set(), "DIGITS": set(), "DATES": set(), "WORDS": set()}
    for figure in MONEY_RE.findall(upper):
        classes["MONEY"].add(figure)
        classes["MONEY"].add(figure.replace(",", ""))
    classes["DIGITS"].update(re.findall(rf"\d{{{digit_min},}}", upper))
    classes["DATES"].update(NUMERIC_DATE_RE.findall(upper))
    classes["DATES"].update(SPELLED_DATE_RE.findall(upper))
    words = re.findall(rf"[A-Z]{{{word_min},}}", upper)
    classes["WORDS"].update(words)
    classes["WORDS"].update(f"{a} {b}" for a, b in zip(words, words[1:]))
    return classes


def tracked_text(ref: str) -> str:
    """Every tracked TEXT file at `ref`, concatenated and upper-cased (one cat-file batch)."""
    listing = subprocess.run(
        ["git", "ls-tree", "-r", ref], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    blobs = []
    for line in listing.splitlines():
        head, _, name = line.partition("\t")
        parts = head.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        if name.strip().rsplit(".", 1)[-1].lower() not in TEXT_SUFFIXES:
            continue
        blobs.append(parts[2])
    batch = subprocess.run(
        ["git", "cat-file", "--batch"], cwd=ROOT,
        input=("\n".join(blobs) + "\n").encode(), capture_output=True, check=True,
    ).stdout
    return batch.decode("utf-8", errors="replace").upper()


HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def added_lines_from_diff(diff: str) -> list[tuple[str, int, str]]:
    """(file, new-line-number, upper-cased text) for every added line of a diff.

    A hunk header states exactly how many lines of each side its body carries,
    so the body is read BY COUNT and every line in it is classified by its
    first character alone. The reader this replaces classified every line by
    its TEXT, which is not the same thing: a line of the FILE that begins
    `+++` appears in the body as `++++`, matched the `not line.startswith
    ("+++")` guard meant for file headers, and was dropped — after which every
    line of that file was numbered one too low, once per such line. This tree's
    own records quote three diff headers, so the whole-tree audit was reading
    W3 twice under two different numberings and counting the difference as
    residue.

    Both halves matter. An added line the scan never reads is a leak it cannot
    report — that is the floor's own instrument going quiet on exactly the
    shape a diff quotes. And a hit reported against the wrong line is a site
    nobody can find and a site count nobody can reproduce.
    """
    out: list[tuple[str, int, str]] = []
    current = ""
    line_no = 0
    old_left = new_left = 0
    for line in diff.splitlines():
        if old_left > 0 or new_left > 0:
            if line.startswith("\\"):
                # "\ No newline at end of file" — not a line of either side.
                continue
            if line.startswith("+"):
                out.append((current, line_no, line[1:].upper()))
                line_no += 1
                new_left -= 1
            elif line.startswith("-"):
                old_left -= 1
            else:
                line_no += 1
                old_left -= 1
                new_left -= 1
            continue
        if line.startswith("+++ "):
            current = line[4:].removeprefix("b/")
            continue
        match = HUNK_RE.match(line)
        if match:
            line_no = int(match.group(2))
            old_left = int(match.group(1)) if match.group(1) is not None else 1
            new_left = int(match.group(3)) if match.group(3) is not None else 1
    return out


def added_lines(base: str, ref: str) -> list[tuple[str, int, str]]:
    """(file, new-line-number, upper-cased text) for every added line of base...ref."""
    diff = subprocess.run(
        ["git", "diff", f"{base}...{ref}", "--unified=0"],
        cwd=ROOT, capture_output=True, text=True, check=True, errors="replace",
    ).stdout
    return added_lines_from_diff(diff)


def main(argv: list[str] | None = None) -> int:
    self_check()
    args = parse_args(argv)
    sys.path.insert(0, str(ROOT))
    from webapp.artifact_cache import ocr_settings_key

    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]
    shas = population(args)
    printed: dict[str, set[str]] = {"MONEY": set(), "DIGITS": set(), "DATES": set(), "WORDS": set()}
    documents_read = 0
    missing: list[str] = []
    for sha in shas:
        text = cached_text(root, sha, ocr_keys)
        if text is None:
            missing.append(sha[:8])
            continue
        documents_read += 1
        for cls, values in tokens_of(text, args.digit_min, args.word_min).items():
            printed[cls].update(values)

    # The base-tree exclusion is a SET membership, not a substring search: the
    # tracked text tree is tens of megabytes and a large population prints
    # ~10^5 tokens, and `token in text` per token made the scan quadratic (a
    # 300-document population ran for an hour). Tokenising the base tree ONCE
    # with the same patterns, plus every money figure with its separators
    # stripped, gives the same answer for every class in seconds.
    base_tokens = tokens_of(tracked_text(args.base), args.digit_min, args.word_min)
    base_all: set[str] = set().union(*base_tokens.values())
    distinctive = {
        cls: sorted(token for token in values if token not in base_all)
        for cls, values in printed.items()
    }
    lines = added_lines(args.base, args.ref)
    if args.include_tree:
        listing = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", args.ref], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        for name in listing:
            if name.rsplit(".", 1)[-1].lower() not in TEXT_SUFFIXES:
                continue
            blob = subprocess.run(
                ["git", "show", f"{args.ref}:{name}"], cwd=ROOT,
                capture_output=True, text=True, errors="replace",
            ).stdout
            for number, text in enumerate(blob.splitlines(), 1):
                lines.append((f"tree:{name}", number, text.upper()))

    # The branch side is tokenised with the SAME patterns, so a match is a
    # whole token on both sides: an OCR fragment such as `WELC` printed by a
    # scan cannot hit inside `WELCOME`, and `820.05` cannot hit inside
    # `1,0820.05`. (Substring matching on this side, with set exclusion on the
    # other, produced hundreds of fragment false positives per branch.)
    #
    # The attribution is an INVERTED INDEX, token -> the sites that print it,
    # built over the tokens the document side actually asks about. The paired
    # loop it replaces (every distinctive token x every scanned line) is
    # quadratic: a whole-tree audit scans ~5x10^5 lines and a 3,380-document
    # universe makes ~5x10^4 of its tokens hit, which is ~10^10 set lookups —
    # hours, for exactly the same hit list this produces in seconds.
    wanted: set[str] = set().union(*distinctive.values()) if distinctive else set()
    sites: dict[str, list[int]] = {}
    for index, (_file, _number, text) in enumerate(lines):
        for token in set().union(*tokens_of(text, args.digit_min, args.word_min).values()) & wanted:
            sites.setdefault(token, []).append(index)
    hits: list[dict[str, object]] = []
    for cls, tokens in distinctive.items():
        for token in tokens:
            for index in sites.get(token, ()):
                file, number, text = lines[index]
                # `--include-tree` labels the whole-file pass `tree:<path>`;
                # the exclusion rules are about the PATH, so they see it bare.
                path = file[5:] if file.startswith("tree:") else file
                rule = None if args.no_exclusions else excluded_by(cls, path, str(token), text)
                hits.append({
                    "class": cls, "file": file, "line": number,
                    "token": token, "excluded_by": rule,
                })
    hits.sort(key=lambda h: (str(h["file"]), int(h["line"]), str(h["class"])))

    kept = [hit for hit in hits if hit["excluded_by"] is None]
    # With a root-commit `--base`, the diff pass and `--include-tree` reach the
    # same line twice under two labels. A SITE is the thing to count and to
    # fix: one class, one path, one line, one token.
    site_keys = {
        (str(h["class"]), str(h["file"]).removeprefix("tree:"), int(h["line"]), str(h["token"]))
        for h in kept
    }
    by_class_dir: dict[str, int] = {}
    for cls, path, _number, _token in site_keys:
        top = path.split("/", 1)[0] if "/" in path else "(root)"
        by_class_dir[f"{cls} {top}"] = by_class_dir.get(f"{cls} {top}", 0) + 1
    by_named_class: dict[str, int] = {name: 0 for name, _paths in NAMED_RESIDUE}
    for _cls, path, _number, _token in site_keys:
        named = residue_class(path)
        if named is not None:
            by_named_class[named] += 1

    report = {
        "population": len(shas),
        "documents_read": documents_read,
        "no_cached_text": missing,
        "printed_tokens": {cls: len(v) for cls, v in printed.items()},
        "distinctive_scanned": {cls: len(v) for cls, v in distinctive.items()},
        "added_lines": len(lines),
        "raw_hit_count": len(hits),
        "excluded_by_rule": {
            name: sum(1 for h in hits if h["excluded_by"] == name) for name, _ in EXCLUSIONS
        },
        "hits_by_class": {cls: sum(1 for h in kept if h["class"] == cls) for cls in printed},
        "hit_count": len(kept),
        "residue_sites": len(site_keys),
        "residue_files": len({path for _cls, path, _n, _t in site_keys}),
        "residue_by_class_dir": dict(sorted(by_class_dir.items())),
        # Counted, named and STILL RESIDUE: these sites are inside
        # `residue_sites` above, not subtracted from it.
        "residue_by_named_class": dict(sorted(by_named_class.items())),
        "base": args.base,
        "ref": args.ref,
    }
    if args.out is not None:
        args.out.write_text(json.dumps({**report, "hits": hits}, indent=1), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    for hit in kept:
        print(f"HIT {hit['class']} {hit['file']}:{hit['line']} {hit['token']!r}", file=sys.stderr)
    return 1 if kept else 0


if __name__ == "__main__":
    raise SystemExit(main())
