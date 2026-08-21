"""The Fiserv Premier `Statement of Account`, parenthesised-counts issue.

Fiserv Premier is a core banking platform, not a bank: the same printed
template is issued by many institutions, and the registry already holds three
parsers for banks that run on it (`linkbank`, `capital_one`,
`farmers_merchants`), each keyed on its own issuer's furniture. This module is
deliberately narrower than "Fiserv": it reads the **parenthesised-counts**
issue of the summary block,

    Previous Balance $4,778.62 Average Ledger $3,220.98
    Deposits/Credits (28) $17,321.67 Average Collected $3,220.98
    Checks/Debits (60) $17,224.89 Service Charge $0.00
    Interest Paid $0.00 Ending Balance $4,875.40

which is disjoint from the leading-counts issue those three parsers read
(`26 Deposits/Credits 221,708.70`). The disjointness is measured, not assumed —
see the anti-collision note below and `tests/test_fiserv_premier.py`.

**Detection.** The counts clause on its own is not usable evidence. Written the
obvious way it is a bare digit run in front of a label, and the digit run it
finds on a Wells Fargo statement is the last three digits of the balance
printed to the left of `Deposits/Credits` — which matched 216 of the 236
Wells Fargo documents in the stratified probe. The conjunction this module
registers therefore *requires* the opening-balance clause (`Previous Balance`,
which no Wells Fargo layout prints) alongside the counts clause and the
template's own `Statement of Account` heading. Each of the three is necessary;
the scoring rule makes that literal, since one missing required marker caps the
score below the claim threshold no matter how much else fires.

**The issuer is read off the document, and only when the document corroborates
it.** The template prints its bank's name nowhere prominent — only in passing,
in front of an address, in a disclosure directory or a Regulation E notice. A
capitalized run in front of an address is *not* an identity: regulatory
boilerplate and third-party notice addresses have the same shape. `_issuer`
therefore publishes a name only when the document's own web address spells it
(`_spells`), and otherwise leaves `Statement.bank` as None rather than
guessing. The arithmetic does not depend on the name, so an unnamed issuer
costs a label, not a document.

**Two ledger shapes**, both gated on the summary's own counts and totals:
a single `Transaction Activity` grid carrying a running balance, whose chain is
walked from the opening balance to the closing one; and separate
`Credit Transactions` / `Debit Transactions` sections with no balance column,
where the counts and totals are the whole of the evidence.

**A THIRD printed issue exists, is claimed, and is deliberately NOT read**
(W3 §FISERVISS). Four archive documents print this summary strip — the
detection conjunction fires on all three markers and the identity closes to the
cent on all four — over a ledger of a different vocabulary entirely
(`Deposits` / `Other Credits` / `Debits` / `Checks Cleared` /
`Daily Balance Information`), under a period line this module does not read
(`Statement of Account <Month DD, YYYY> thru <Month DD, YYYY>` with the length
printed separately as `Days in the Statement Period: N`, where the two issues
above print `Statement Dates 3/01/26 to 3/31/26 (31 days)`). Neither gap is an
absence: both facts are printed, in wordings no clause here matches. So the
document is claimed and then refused, twice over, and
`test_the_third_printed_issue_is_claimed_and_refused_twice_over` pins that
refusal along with the two repairs it would take to lift it. The issuer is NOT
among the reasons — all four print a web address and no bank name, which is the
`bank=None` path above and costs a label, not a document.
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import MONTH_NAME_ALT, iso_from_named_month_day, iso_within_period
from .money import PARENS_OR_LEADING_MINUS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: `$1,234.56`, `-$1,234.56`, `1,234.56`, `.56`.
_MONEY = r"-?\$?-?(?:[\d,]+\.\d{2}|\.\d{2})"

#: Detection runs over `detection_text`, which is upper-cased; parsing runs
#: over the document as printed. These two are used by detection only, so they
#: are case-insensitive rather than assuming either.
_COUNTS_CREDIT_RE = re.compile(r"DEPOSITS/CREDITS\s*\(\d+\)", re.IGNORECASE)
_COUNTS_DEBIT_RE = re.compile(r"CHECKS/DEBITS\s*\(\d+\)", re.IGNORECASE)

_SUMMARY_RE = re.compile(
    r"Previous Balance\s+(" + _MONEY + r")"
    r"(?:\s+Average Ledger\s+(" + _MONEY + r"))?"
    r"\s+Deposits/Credits\s*\((\d+)\)\s*(" + _MONEY + r")"
    r"(?:\s+Average Collected\s+(" + _MONEY + r"))?"
    r"\s+Checks/Debits\s*\((\d+)\)\s*(" + _MONEY + r")"
    r"(?:\s+Service Charge\s+(" + _MONEY + r"))?"
    r"(?:\s+Interest Paid\s+(" + _MONEY + r"))?"
    r"\s+(?:Ending|Current) Balance\s+(" + _MONEY + r")"
)

_PERIOD_RE = re.compile(
    r"Statement Dates\s+(\d{1,2})/(\d{1,2})/(\d{2})\s+to\s+"
    r"(\d{1,2})/(\d{1,2})/(\d{2})\s*\((\d+)\s*days?\)"
)

#: The SECOND period wording, printed by the third issue: the two dates in the
#: masthead heading and the length in the activity strip, instead of the dates
#: and the length in one clause.
#:
#: Anchored on `Statement of Account` rather than floating, because the pattern
#: is otherwise two capitalized month words around `thru` and the disclosures
#: below are prose. The month table is the shared one (`MONTH_NAME_ALT` /
#: `iso_from_named_month_day`) so a month can never mean two things here and
#: something else elsewhere.
_LONG_PERIOD_RE = re.compile(
    r"Statement of Account\s+(" + MONTH_NAME_ALT + r")\s+(\d{1,2}),\s*(\d{4})"
    r"\s+thru\s+(" + MONTH_NAME_ALT + r")\s+(\d{1,2}),\s*(\d{4})",
    re.IGNORECASE,
)
#: `Activity Summary Days in the Statement Period:  30` — the length, printed
#: away from the dates.
_DAYS_RE = re.compile(r"Days in the Statement Period:\s*(\d+)")
_TITLE_RE = re.compile(r"Account Title:\s*(.+?)\s*$", re.MULTILINE)
_PRODUCT_RE = re.compile(r"^(.+?)\s+-\s+(X+\d+)\s*$", re.MULTILINE)

#: A printed web address. Used for the issuer's identity, never for routing.
_DOMAIN_RE = re.compile(
    r"\b(?:www\.)?([A-Za-z][A-Za-z0-9\-]{2,})\.(?:com|bank|net|org)\b", re.IGNORECASE
)
#: The statement's own return address, printed at the top of page one.
_RETURN_RE = re.compile(
    r"^(PO Box \d+|\d+ [A-Z][^\n,]{3,40})\s+([A-Za-z .'\-]+),\s*[A-Z]{2}\s+\d{5}",
    re.MULTILINE,
)

_PAGE_RE = re.compile(r"^--- Page \d+")
_ACTIVITY_RE = re.compile(r"^Transaction Activity\s+Date\s+Description\s+Debits\s+Credits\s+Balance\b(.*)$")
_CREDIT_RE = re.compile(r"^Credit Transactions\s+Date\s+Description\s+Amount\b(.*)$")
_DEBIT_RE = re.compile(r"^Debit Transactions\s+Date\s+Description\s+Amount\b(.*)$")

#: `3/02 DESCRIPTION -$17.39 $423.43` — amount then running balance.
_ACTIVITY_ROW_RE = re.compile(
    r"(?<![\d/])(\d{1,2}/\d{1,2})\s+(.+?)\s+(-?\$" + r"[\d,]*\.\d{2})\s+(-?\$[\d,]*\.\d{2})(?=\s|$)"
)
#: `4/01 DESCRIPTION $145.35` — one amount, direction fixed by the section.
#:
#: The description is OPTIONAL because the cheque recap printed at the foot of
#: the debit section identifies its items by number, and an item drawn without
#: one prints as a bare `2/26 $20.00`. It is also `[^$]` rather than `.`: with
#: an unconstrained description the engine happily spans a bare pair into the
#: next row's amount and silently merges two postings into one.
_PLAIN_ROW_RE = re.compile(
    r"(?<![\d/])(\d{1,2}/\d{1,2})\s+(?:([^$]+?)\s+)?(-?\$[\d,]*\.\d{2})(?=\s|$)"
)

#: ---------------------------------------------------------------------------
#: The THIRD printed issue's ledger (W3 §FISERVISS FI2.2, card FISERV-ISSUE3).
#: ---------------------------------------------------------------------------
#: Its section heads. `Deposits` and `Other Credits` are two printed sections of
#: ONE direction; `Debits` and `Checks Cleared` are two printed sections of the
#: other. The cheque recap is a posting section here, not a recap: its items are
#: inside the printed `Checks/Debits` count and total, and the arithmetic below
#: proves it — dropping it leaves every one of the four documents short.
_EMBEDDED_HEAD_RES = (
    ("credit", re.compile(r"^Deposits\s+Date\s+Description\s+Amount\s*\$?(.*)$")),
    ("credit", re.compile(r"^Other Credits\s+Date\s+Description\s+Amount\s*\$?(.*)$")),
    ("debit", re.compile(r"^Debits\s+Date\s+Description\s+Amount\s*\$?(.*)$")),
    ("debit", re.compile(r"^Checks Cleared\b\s*(.*)$")),
)
#: The column header this issue RE-DECLARES at the top of every continuation
#: page, carrying no section name. It is the only thing that reopens a section
#: across a page break — see `_embedded_sections`.
_EMBEDDED_CONTINUATION_RE = re.compile(
    r"^Date\s+(?:Description|Check No)\s+Amount\s*\$?(.*)$"
)
#: What ENDS the ledger. All three are printed recaps or statistics, never
#: posting detail, and one of them always follows the last posting section.
_EMBEDDED_END_RE = re.compile(
    r"^(?:Itemization of Service Charge|Daily Balance Information"
    r"|Overdraft and Returned Item Fees)\b"
)
_EMBEDDED_DAILY_HEAD_RE = re.compile(r"^Daily Balance Information\b")
_EMBEDDED_DAILY_CONT_RE = re.compile(r"^Date\s+Balance\s*\$?(.*)$")

#: **THE MONEY-GRAMMAR RULE, and its refusal.**
#:
#: This issue prints an overdraft fee as
#:
#:     04/01 CHK# 00 AMT $579.45, NSF PAID ITEM FEE $31.00
#:
#: where the FIRST money token is a REFERENCE to the item that caused the fee
#: and the row's own amount is the last one. 109 such rows are printed across
#: the four documents of this issue (34 / 10 / 37 / 28), every one of them a
#: $31.00 fee against a reference of some other size.
#:
#: `_PLAIN_ROW_RE`'s `[^$]` description cannot span a reference, so it drops the
#: row whole, and the printed debit count and total then refuse the document.
#: The fix must NOT be to relax that class: with an unconstrained description
#: the engine spans a bare pair into the next row's amount and merges two
#: postings into one, and with a plain "the amount is the last money token"
#: rule it merges rows at section ends (measured, §FI2.3: 1–3 lost per
#: document). The `(?=\s|$)` lookahead is likewise load-bearing — it is the
#: only reason the comma-terminated reference fails today instead of publishing
#: $579.45 as a $31.00 fee (§FI5.4).
#:
#: So the relaxation is EXACTLY one shape wide and is paired with a refusal:
#:
#: * the description may cross a `$` **only** where the token is introduced by
#:   the reference keyword `AMT` (`_EMBEDDED_REFERENCE`); anywhere else `[^$]`
#:   still bounds it, so a row can still never run into its neighbour;
#: * a money token introduced by `AMT` can **never** be the row's amount
#:   (`(?<!\bAMT) ` in front of the amount capture). This is the refusal, and it
#:   does not depend on the comma: strip the comma and the reference is still
#:   refused as an amount and still read as part of the description.
#:
#: The trailing comma is therefore OPTIONAL here rather than required. Requiring
#: it would make the refusal an accident of punctuation — exactly the accident
#: §FI5.4 warned about — and it would refuse the whole document if one row's
#: comma failed to survive the text layer.
#:
#: **WHAT THIS RULE ASSUMES, stated so the next reader does not have to derive
#: it** (W3 §FISERV3 F14, review MINOR-1/2/3):
#:
#: 1. **The keyword is the literal uppercase token `AMT`.** Both halves of the
#:    rule key on it, so a variant spelling the template does not print today —
#:    `Amt`, `AMT:` — would be neither admitted into the description nor refused
#:    as an amount. WITHOUT the trailing comma such a row would publish the
#:    REFERENCE as its amount. Measured over the ledger sections of all four
#:    documents: 109 occurrences, 109 of them bare uppercase `AMT`, 0 variant
#:    spellings, and 0 not immediately followed by a money token. So the hole is
#:    unreachable on the attested corpus, and it is fail-closed at DOCUMENT
#:    level if it ever opens: a mis-read amount misses the printed debit total
#:    and the printed daily grid, and the document refuses rather than
#:    publishing a wrong figure. Widening the keyword class is a measurement, not
#:    a guess, and belongs to whichever cell meets the variant.
#: 2. **The `\b` is deliberately asymmetric, and it is inert here.**
#:    `(?<!\bAMT) ` is word-bounded (so `PAYAMT $5.00` is an ordinary amount, not
#:    a refused reference) while `_EMBEDDED_REFERENCE` is not (so a description
#:    could in principle cross `PAYAMT $5.00` as if it were a reference). No
#:    archive row prints `AMT` as a word-suffix, so the two never disagree on
#:    real text. Recorded because the asymmetry looks like an oversight and is
#:    not one: the REFUSAL is the half that must be precise, since over-refusing
#:    costs a document and under-refusing costs a number.
#: 3. **A genuine row whose DESCRIPTION ends in `AMT` before its own amount
#:    refuses the document.** `06/01 WIRE TRANSFER AMT $500.00` is read as a
#:    reference with no fee behind it, matches nothing, is dropped, and the
#:    printed count then refuses. That is the intended trade and it is the right
#:    way round — it costs a document, never a number — but it IS a false
#:    refusal, and it is why the keyword class must not be widened casually.
_EMBEDDED_REFERENCE = r"AMT -?\$[\d,]*\.\d{2},?"
#: The row: a posting date, a description that may carry references and nothing
#: else with a `$` in it, and the row's own amount.
#:
#: Read over WHITESPACE-NORMALIZED section text (`_embedded_rows`), which is
#: what makes the fixed-width `(?<!\bAMT)` lookbehind exact: on raw text
#: `AMT  $579.45` (this text layer does print double spaces — "Days in the
#: Statement Period:  30") would step around a lookbehind anchored to one
#: space, and the reference would be published as the amount.
#:
#: There is deliberately no second, "structural" re-check of the matched amount
#: alongside this lookbehind. One was written and then measured UNREACHABLE:
#: with the description class bounded as above, no input reaches
#: `_embedded_rows` with an `AMT`-introduced token in the amount slot — such a
#: row simply fails to match and is dropped, and the printed counts refuse the
#: document. A guard nothing can trip is the §FI5.4 shape in reverse: it reads
#: like protection while proving nothing, and it would have made the lookbehind
#: look optional. The lookbehind is the mechanism, and
#: `test_the_refusal_does_not_rest_on_the_reference_comma` is what kills its
#: removal.
_EMBEDDED_ROW_RE = re.compile(
    r"(?<![\d/])(\d{1,2}/\d{1,2}) "
    r"(?:((?:" + _EMBEDDED_REFERENCE + r"|[^$])+?)(?<!\bAMT) )?"
    r"(-?\$[\d,]*\.\d{2})(?= |$)"
)

_TOLERANCE = 0.005


def _money(value: str | None) -> float | None:
    return parse_amount(value, PARENS_OR_LEADING_MINUS)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    required("statement_of_account", lambda t: "STATEMENT OF ACCOUNT" in t),
    # THE ANTI-COLLISION CLAUSE, and it is required rather than corroborating:
    # the counts clause alone reaches 216 of 236 Wells Fargo documents, and no
    # Wells Fargo layout prints an opening balance under this name.
    required("opening_balance", lambda t: "PREVIOUS BALANCE" in t),
    required(
        "parenthesised_counts",
        lambda t: bool(_COUNTS_CREDIT_RE.search(t)) and bool(_COUNTS_DEBIT_RE.search(t)),
    ),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def _spells(label: str, name: str) -> bool:
    """Is `label` the way `name` writes itself as a domain?

    True when the domain's letters appear in the name in order and both start
    with the same letter — which is what a bank's own web address is: the name
    spelled short. It covers the name written out (``altabank`` /
    "Altabank"), the name shortened (``ches`` / "Chesapeake Bank") and the name
    reduced to an abbreviation (``fsbmsla`` / "First Security Bank of
    Missoula"), without any of them being enumerated here.

    The shared first letter is what stops a short label drifting onto unrelated
    text: ``ches`` is a subsequence of "Notices to Smith and Jones LLP" as
    letters, and is rejected because that phrase does not begin with a ``c``.
    """
    if not label or not name or label[0] != name[0]:
        return False
    remaining = iter(name)
    return all(character in remaining for character in label)


def _own_domain(markdown: str) -> str | None:
    """The registrable label of the domain this statement prints for itself.

    The contact block at the head of page one is the statement's own; the
    disclosure directory further down lists every sibling division's domain, so
    document order is what separates "mine" from "theirs".
    """
    m = _DOMAIN_RE.search(markdown)
    return m.group(1).lower() if m else None


def _issuer(markdown: str) -> str | None:
    """The division that issued this statement, or None when it is not printed.

    The template names its issuer only in passing: beside the return address in
    the group's disclosure directory, or in the Regulation E notice ("write us
    at <bank> <address>"). Both are just a capitalized run in front of an
    address — and **a capitalized run in front of an address is not an
    identity**. The same shape is produced by regulatory boilerplate ("Member
    FDIC Equal Housing Lender") and by a third party's notice address ("Notices
    to <firm>"), and publishing either as `Statement.bank` would put a fiction
    into underwriting output. This registration is meant to generalize across
    many issuers of one platform, so the guard has to be structural rather than
    a list of known bad phrases.

    A candidate is therefore published only when the document ties it to the one
    identity it *does* print unambiguously — its own web address — by `_spells`:
    the domain has to be that name written short. Boilerplate that merely sits
    in front of an address does not spell the bank's domain, so it never
    survives, and no phrase has to be enumerated for it to be rejected.

    When nothing is corroborated, or more than one thing is, the answer is None
    and the caller publishes no bank at all: an unnamed issuer is a gap a human
    can close, where a wrong one is a finding nobody knows to question.
    """
    ret = _RETURN_RE.search(markdown)
    domain = _own_domain(markdown)
    if ret is None or domain is None:
        return None
    anchor = f"{ret.group(1)} {ret.group(2)}"
    named = re.compile(r"([A-Z][A-Za-z.&'\- ]{2,40}?)\s+" + re.escape(anchor))

    corroborated: set[str] = set()
    for match in named.finditer(markdown):
        name = match.group(1).strip()
        # The text layer emits runs of one repeated glyph as page furniture.
        if len(set(name.replace(" ", ""))) <= 1:
            continue
        if _spells(re.sub(r"[^a-z0-9]", "", domain), re.sub(r"[^a-z0-9]", "", name.lower())):
            corroborated.add(name)
    return corroborated.pop() if len(corroborated) == 1 else None


def _period(markdown: str) -> tuple[date, date, int] | None:
    """The statement period, in either wording this template prints.

    The registered clause (`Statement Dates 4/01/26 to 4/30/26 (30 days)`) is
    tried first and is unchanged: a document that prints it takes exactly the
    same path it took before this reader existed.

    The second wording prints the same two facts in two places — the dates in
    the masthead, the length in the activity strip — and the two are welded
    here by requiring the printed length to be the calendar span they describe.
    That check exists only for this wording, and only because it is two
    independent reads: in the registered clause the dates and the length are
    one clause, so there is nothing to corroborate. Disagreement means one of
    the two was misread, and a wrong period basis silently re-bounds every row
    (`iso_within_period`) and re-bases the average daily balance.
    """
    registered = _PERIOD_RE.search(markdown)
    if registered is not None:
        sm, sd, sy, em, ed, ey, days = (int(part) for part in registered.groups())
        try:
            return date(2000 + sy, sm, sd), date(2000 + ey, em, ed), days
        except ValueError:
            return None

    printed = _LONG_PERIOD_RE.search(markdown)
    length = _DAYS_RE.search(markdown)
    if printed is None or length is None:
        return None
    start_iso = iso_from_named_month_day(printed.group(1), printed.group(2), printed.group(3))
    end_iso = iso_from_named_month_day(printed.group(4), printed.group(5), printed.group(6))
    if start_iso is None or end_iso is None:
        return None
    start, end = date.fromisoformat(start_iso), date.fromisoformat(end_iso)
    days = int(length.group(1))
    if end < start or (end - start).days + 1 != days:
        return None
    return start, end, days


def _summary(markdown: str):
    m = _SUMMARY_RE.search(markdown)
    if m is None:
        return None
    (
        previous, _average_ledger, credit_count, credits, _average_collected,
        debit_count, debits, service_charge, interest, closing,
    ) = m.groups()
    values = {
        "previous": _money(previous),
        "credits": _money(credits),
        "debits": _money(debits),
        "closing": _money(closing),
        "service_charge": _money(service_charge) if service_charge else 0.0,
        "interest": _money(interest) if interest else 0.0,
        "average": _money(_average_ledger) if _average_ledger else None,
    }
    if any(v is None for k, v in values.items() if k != "average"):
        return None
    values["credit_count"] = int(credit_count)
    values["debit_count"] = int(debit_count)
    return values


#: The `Daily Balance` recap is printed inside the last ledger section rather
#: than after it, and its `date amount` pairs are row-shaped. It is a printed
#: recap, not posting detail, so it TERMINATES the ledger — the same structural
#: bound the section headings provide everywhere else in this template.
_DAILY_BALANCE_RE = re.compile(r"Daily Balance\s+Date\s+Amount")
#: `4/01 $3,174.46`, with no description between the two — which is exactly what
#: distinguishes a recap pair from a posting row.
_DAILY_PAIR_RE = re.compile(r"(?<![\d/])(\d{1,2}/\d{1,2})\s+(-?\$[\d,]*\.\d{2})(?![\d.,])")


def _sections(markdown: str) -> dict[str, str]:
    gathered: dict[str, list[str]] = {"activity": [], "credit": [], "debit": []}
    current: str | None = None
    for line in markdown.splitlines():
        line = line.rstrip()
        if _PAGE_RE.match(line):
            current = None
            continue
        for name, pattern in (
            ("activity", _ACTIVITY_RE), ("credit", _CREDIT_RE), ("debit", _DEBIT_RE),
        ):
            head = pattern.match(line)
            if head:
                current = name
                if head.group(1).strip():
                    gathered[name].append(head.group(1).strip())
                break
        else:
            if current is not None:
                gathered[current].append(line)

    sections = {name: " ".join(lines) for name, lines in gathered.items()}
    recap: list[str] = []
    for name, text in list(sections.items()):
        cut = _DAILY_BALANCE_RE.search(text)
        if cut:
            sections[name] = text[: cut.start()]
            recap.append(text[cut.end():])
    sections["daily"] = " ".join(recap)
    return sections



def _embedded_sections(markdown: str) -> dict[str, str]:
    """The third issue's ledger, by direction, plus its printed daily grid.

    Two things differ from `_sections`, and both are properties of THIS issue's
    printing rather than preferences:

    * **Four printed sections, two directions.** `Deposits` and `Other Credits`
      are both credits; `Debits` and `Checks Cleared` are both debits. The
      direction is the section's, never the sign's — no amount in this ledger
      carries one.
    * **Sections continue across page breaks.** `_sections` closes at
      `--- Page` because the two issues it reads re-print their named heading on
      every page. This one does not: it re-declares only the bare column header
      (`Date Description Amount $`), and a disclosure page or a cheque-image
      page can sit in the middle of a section. Closing at the page break loses
      those continuations; carrying blindly across it swallows the disclosure
      prose and the cheque-image list into the ledger.

      So the carry is neither: a page break SUSPENDS the section, and only the
      document's own re-declared column header resumes it. Prose that follows a
      page break is outside every section because it declares nothing, which is
      the same structural bound the headings give everywhere else.

    A recap or statistics heading ends the ledger outright and cannot be
    resumed — `Daily Balance Information` opens the printed daily grid, which
    is evidence rather than posting detail and is read separately.
    """
    gathered: dict[str, list[str]] = {"credit": [], "debit": [], "daily": []}
    current: str | None = None
    suspended: str | None = None
    for line in markdown.splitlines():
        line = line.rstrip()
        if _PAGE_RE.match(line):
            if current is not None:
                suspended = current
            current = None
            continue
        if _EMBEDDED_END_RE.match(line):
            if _EMBEDDED_DAILY_HEAD_RE.match(line):
                current = "daily"
            else:
                current = None
            suspended = None
            continue
        if current == "daily":
            grid = _EMBEDDED_DAILY_CONT_RE.match(line)
            if grid and grid.group(1).strip():
                gathered["daily"].append(grid.group(1).strip())
            continue
        for name, pattern in _EMBEDDED_HEAD_RES:
            head = pattern.match(line)
            if head:
                current, suspended = name, None
                if head.group(1).strip():
                    gathered[name].append(head.group(1).strip())
                break
        else:
            resumed = _EMBEDDED_CONTINUATION_RE.match(line)
            if resumed:
                if current is None:
                    current, suspended = suspended, None
                if current is not None and resumed.group(1).strip():
                    gathered[current].append(resumed.group(1).strip())
            elif current is not None:
                gathered[current].append(line)
    return {name: " ".join(lines) for name, lines in gathered.items()}


def _embedded_rows(text: str, start: date, end: date, sign: int):
    """The third issue's posting rows, under the money grammar above.

    Returns None — refusing the whole document — rather than dropping a row it
    cannot read, because every row of this ledger is inside a printed count and
    a printed total that the caller checks.
    """
    # Whitespace-normalized FIRST, and that is not cosmetic: it is what makes
    # the pattern's fixed-width `(?<!\bAMT)` lookbehind exact. `AMT  $579.45`
    # would otherwise step around a lookbehind anchored to one space and publish
    # the reference as the fee, and this text layer does print double spaces.
    text = " ".join(text.split())
    rows: list[Transaction] = []
    for m in _EMBEDDED_ROW_RE.finditer(text):
        amount = _money(m.group(3))
        posted = iso_within_period(m.group(1), start, end)
        if amount is None or posted is None:
            return None
        rows.append(
            Transaction(
                date=posted,
                description=re.sub(r"\s+", " ", m.group(2) or "").strip(),
                amount=sign * abs(amount),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return rows


def _daily_grid_agrees(text: str, transactions, start: date, end: date,
                       opening: float, closing: float) -> bool:
    """Does the printed daily-balance grid reproduce the rows we read?

    The third oracle, and the only one that binds a row to a DAY. The printed
    counts and totals gate the ledger as a whole; this grid gates its shape:
    walked from the opening balance, each printed day must equal the opening
    plus every row filed on or before it, the last must be the closing balance,
    and no row may fall on a day the grid does not print.

    It is required rather than advisory because the underwriting ADB is a
    calendar-day average over exactly these daily balances: a ledger whose rows
    are on the wrong days can still satisfy both printed totals and still
    produce a wrong average.
    """
    printed: list[tuple[str, float]] = []
    for token, value in _DAILY_PAIR_RE.findall(text):
        posted = iso_within_period(token, start, end)
        balance = _money(value)
        if posted is None or balance is None:
            return False
        printed.append((posted, balance))
    if not printed:
        return False
    if [day for day, _ in printed] != sorted(day for day, _ in printed):
        return False

    moved: dict[str, float] = {}
    for txn in transactions:
        moved[txn.date] = round(moved.get(txn.date, 0.0) + txn.amount, 2)
    running = opening
    for day, balance in printed:
        running = round(running + moved.pop(day, 0.0), 2)
        if abs(running - balance) > _TOLERANCE:
            return False
    # A row on a day the grid never prints is a row the grid cannot vouch for.
    return not moved and abs(running - closing) <= _TOLERANCE


def _activity_rows(text: str, start: date, end: date, opening: float):
    """The single-grid shape: every row's balance must continue the chain."""
    rows: list[Transaction] = []
    running = opening
    for m in _ACTIVITY_ROW_RE.finditer(text):
        amount = _money(m.group(3))
        balance = _money(m.group(4))
        posted = iso_within_period(m.group(1), start, end)
        if amount is None or balance is None or posted is None:
            return None
        # A zero-amount posting has no sign to read a direction from, and this
        # grid prints the amount in a Debits or a Credits column whose identity
        # the flattened text layer has already destroyed. Direction is a
        # property of the column, not of the sign (the platform rule), so there
        # is nothing here to derive it from — refuse rather than file the row
        # under a guessed side and let it count against a printed total.
        if amount == 0:
            return None
        if abs(round(running + amount, 2) - balance) > _TOLERANCE:
            return None
        running = balance
        rows.append(
            Transaction(
                date=posted,
                description=re.sub(r"\s+", " ", m.group(2)).strip(),
                amount=amount,
                direction="credit" if amount >= 0 else "debit",
                running_balance=balance,
            )
        )
    return rows


def _plain_rows(text: str, start: date, end: date, sign: int):
    rows: list[Transaction] = []
    for m in _PLAIN_ROW_RE.finditer(text):
        amount = _money(m.group(3))
        posted = iso_within_period(m.group(1), start, end)
        if amount is None or posted is None:
            return None
        rows.append(
            Transaction(
                date=posted,
                description=re.sub(r"\s+", " ", m.group(2) or "").strip(),
                amount=sign * abs(amount),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return rows


def parse_fiserv_premier_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    summary = _summary(markdown)
    period = _period(markdown)
    # An unnamed issuer is not a reason to refuse the document: the arithmetic
    # is the same either way, and `bank=None` reports exactly what the page
    # supports. Refusing would also make the guard above look like a parse
    # failure in the telemetry, which is the opposite of what it is.
    issuer = _issuer(markdown)
    if summary is None or period is None:
        return None

    start, end, days = period
    if end < start:
        return None

    # The summary closes on itself before any row is read.
    #
    # The fee terms are treated as SEPARATE from the two transaction totals —
    # a service charge is not inside `Checks/Debits`, interest is not inside
    # `Deposits/Credits`. Every document of this family in the archive prints
    # both as zero, so that reading is not corroborated by the corpus; it is
    # kept because getting it wrong fails CLOSED. A charge that is in fact
    # already inside the debit total would be subtracted twice here, the
    # identity would miss, and the document would be refused rather than
    # published with a wrong opening or closing balance.
    walked = (
        summary["previous"]
        + abs(summary["credits"])
        - abs(summary["debits"])
        - abs(summary["service_charge"])
        + abs(summary["interest"])
    )
    if abs(walked - summary["closing"]) > _TOLERANCE:
        return None

    sections = _sections(markdown)
    if sections["activity"]:
        if sections["credit"] or sections["debit"]:
            return None  # two ledger shapes in one document: not understood
        transactions = _activity_rows(
            sections["activity"], start, end, summary["previous"]
        )
        if transactions is None:
            return None
        if abs((transactions[-1].running_balance if transactions else summary["previous"])
               - summary["closing"]) > _TOLERANCE:
            return None
    elif sections["credit"] or sections["debit"]:
        credits = _plain_rows(sections["credit"], start, end, 1)
        debits = _plain_rows(sections["debit"], start, end, -1)
        if credits is None or debits is None:
            return None
        transactions = credits + debits
    else:
        # The THIRD printed issue, reached only when neither of the two read
        # vocabularies is present at all. Deliberately the LAST branch and
        # guarded by that `else`: a document that prints either read shape takes
        # exactly the path it took before this branch existed, so nothing this
        # cell added can reach it.
        embedded = _embedded_sections(markdown)
        if not (embedded["credit"] or embedded["debit"]):
            return None
        credits = _embedded_rows(embedded["credit"], start, end, 1)
        debits = _embedded_rows(embedded["debit"], start, end, -1)
        if credits is None or debits is None:
            return None
        transactions = credits + debits
        if not _daily_grid_agrees(
            embedded["daily"], transactions, start, end,
            summary["previous"], summary["closing"],
        ):
            return None

    if not transactions:
        return None

    # The summary's own counts and totals are the gate on the rows.
    # Partitioned by DIRECTION, not by sign. A zero-amount row belongs to
    # whichever side the document filed it under, and a sign test would drop it
    # out of both counts while still carrying it in `transactions` — the count
    # gate below would then compare a short list against the printed total and
    # pass, publishing a ledger with a row nobody counted.
    credit_rows = [t for t in transactions if t.direction == "credit"]
    debit_rows = [t for t in transactions if t.direction == "debit"]
    if len(credit_rows) != summary["credit_count"]:
        return None
    if len(debit_rows) != summary["debit_count"]:
        return None
    if abs(sum(t.amount for t in credit_rows) - abs(summary["credits"])) > _TOLERANCE:
        return None
    if abs(sum(-t.amount for t in debit_rows) - abs(summary["debits"])) > _TOLERANCE:
        return None

    # Only the split-section shape is re-ordered, because its credits and debits
    # are printed in two separate runs. The single-grid shape is left in the
    # order the document printed it: its rows carry running balances whose chain
    # was verified in exactly that order, and re-ordering them would publish a
    # balance sequence the document does not show.
    if all(txn.running_balance is None for txn in transactions):
        transactions.sort(key=lambda txn: txn.date)
    title = _TITLE_RE.search(markdown)
    product = _PRODUCT_RE.search(markdown)
    return Statement(
        bank=issuer,
        account_name=(product.group(1).strip() if product
                      else title.group(1).strip() if title else None),
        account_number=product.group(2) if product else None,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=days,
        beginning_balance=summary["previous"],
        ending_balance=summary["closing"],
        stated_total_credits=abs(summary["credits"]),
        stated_total_debits=abs(summary["debits"]),
        stated_credit_count=summary["credit_count"],
        stated_debit_count=summary["debit_count"],
        bank_reported_average_balance=summary["average"],
        bank_reported_average_label=(
            "Average Ledger" if summary["average"] is not None else None
        ),
        stated_service_charge=abs(summary["service_charge"]),
        stated_interest_paid=abs(summary["interest"]),
        transactions=transactions,
    )
