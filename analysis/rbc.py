from __future__ import annotations

import re
import unicodedata
from datetime import date

from .money import parse_french_amount, parse_money, read_money
from .parser_registry import excluding, make_detector, required
from .schema import Statement, Transaction
from .tables import glyph_damaged, group_rows, read_grid_rows
from .td_can import _MONTHS, normalize_mojibake

_PERIOD_RE = re.compile(
    r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})\s+to\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)
_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_DATE_START_RE = re.compile(r"^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", re.IGNORECASE)
_MONEY_RE = re.compile(r"(?<![#\w])-?\$?[\d,]+\.\d{2}(?!\w)")
_PAGE_RE = re.compile(r"^\d+ of \d+$", re.IGNORECASE)
#: The activity table's own printed column header, which is what opens the
#: grid — the business product names its first money column `Cheques & Debits`
#: and the personal one `Withdrawals`. Matching the header rather than the
#: heading above it is what makes a continuation page re-enter the table.
_ACTIVITY_GRID_RE = re.compile(
    r"DATE DESCRIPTION (?:CHEQUES & DEBITS|WITHDRAWALS)")
#: One printed money cell of the `Account Summary for this Period` block: the
#: currency symbol is optional, and a negative figure is printed either
#: `-$1,234.56` or `$-1,234.56`.
#:
#: The block prints four rows — opening balance, the two totals, closing
#: balance — in one grid, so whether the symbol is printed is a property of the
#: STATEMENT, not of the row. Reading the totals with a narrower pattern than
#: the balances was silent data loss: on a statement that prints `$` on the
#: total rows, both stated totals AND both stated counts went None, which skips
#: the summary identity check (`reconcile.summary_ok` None) and ships the
#: document approved with `summary_totals_reliable=True` and no issue raised.
#:
#: The sign is printed in three places relative to the symbol — `-$2.55`,
#: `$-2.55` and `- $2.55` — because the minus is set in the *label* column of
#: the summary grid while the symbol belongs to the figure. Reading only the
#: first two was the same class of loss one level down: a personal statement
#: closing overdrawn printed `= - $2.55` and the parser published `+2.55`, so
#: the summary identity balanced against a sign-flipped closing balance
#: instead of failing. Six of the twelve personal-layout documents close or
#: open overdrawn and print it this way.
_SUMMARY_MONEY = r"((?:-\s*)?\$?(?:-\s*)?[\d,]+\.\d{2})"

#: The denomination line RBC prints in the header block, on its own line
#: directly under the statement title, on a U.S.-dollar statement and on no
#: other: `Business Account Statement` / `U.S. Funds`. Some issues of the same
#: header set both words on one line, so the title is optional here and the
#: line is anchored at both ends — an unanchored search would reach the words
#: `funds` and `U.S.` wherever a transaction description happens to print them
#: (`Funds transfer credit TT KM CAPITAL C` is a posting on one of the four
#: pinned RBC statements, and it is a transfer TYPE, not a denomination).
_US_FUNDS_RE = re.compile(
    r"^[ \t]*(?:Business Account Statement[ \t]+)?U\.S\. Funds[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

#: The mailing header: the line RBC opens with its own print-control code,
#: `RBBDA30000_5081501 E D 07489 00380 2424647 ALBERTA INC. CAD CHEQUING
#: ACCOUNT 113 TAMARACK WAY FORT MCMURRAY AB T9K 1A2`. 157 of the 169 archive
#: documents carry one, and all twelve that name a currency carry it there.
#:
#: THE PRODUCT NAME IS READ FROM THIS LINE AND NOWHERE ELSE. The reason is the
#: ledger: this family prints 88 postings that name an account — `Online
#: Transfer to Deposit Account-5887`, `ACCOUNT TRANSFER 06032-1122647` — so a
#: document-wide search for the product spelling is one customer-named account
#: away from a counterfeit (`Online Transfer to CAD Chequing Account-1718`
#: reads as a CAD denomination, on a statement that may be neither). Measured
#: today: twelve product-spelling hits, twelve of them on this line and none
#: outside it, so the anchor costs nothing and closes the shape.
#:
#: BOTH print-control prefixes are anchored, not only the business one. RBC
#: sets this header as `RBBDA<transit>_<serial>` on the business layout and as
#: `RBPDA<transit>_<serial>_<sequence>` on the personal one; measured over the
#: RBC superset, 181 archive documents carry an `RBBDA…` line and 13 carry an
#: `RBPDA…` line. Matching only `RBBDA` left the personal layout's product line
#: UNREAD, so a personal issue that printed a product currency word would have
#: had its explicit denomination missed — and, once the jurisdiction default
#: below exists, silently defaulted instead (RBC_CURRENCY_MEASUREMENT §11 R4).
#: The explicit read must keep its precedence on both layouts, so the anchor is
#: widened in the same commit as the default. Measured on the same superset:
#: widening moves no document's read today (no personal issue prints either
#: attested product spelling), which is why it is a precedence repair rather
#: than a currency movement.
_MAILING_HEADER_RE = re.compile(r"^RB[BP]DA\d+(?:_\d+)+\b.*$", re.MULTILINE)

#: The product spellings that name a currency, and what each denominates.
#: These two and no others are attested — measured over every RBC document in
#: the archive: `CAD CHEQUING ACCOUNT` 6, `US BUSINESS ACCOUNT` 6. This is a
#: literal table rather than an alternation over `(CAD|US)` and
#: `(CHEQUING|BUSINESS)`, which would have admitted two spellings
#: (`CAD BUSINESS ACCOUNT`, `US CHEQUING ACCOUNT`) that no document prints and
#: that nothing here has measured.
#:
#: RBC prints no currency word at all in the packages that have none
#: (`RBC Digital Choice Business`, `RBC Ultimate Business`, `Business Current
#: Account`, `RBC Advantage Banking`), which is why 151 documents state
#: nothing. A bare `CAD`/`USD` token scan is deliberately NOT used either —
#: this layout prints e-Transfer reference codes of the shape `CAxxxxxx` in its
#: ledger (`e-Transfer received PHILIPPESEGUIN CADWKEFS`).
_PRODUCT_CURRENCY = {
    "CAD CHEQUING ACCOUNT": "CAD",
    "US BUSINESS ACCOUNT": "USD",
}


def _printed_currency_evidence(markdown: str) -> set[str]:
    """Every currency this document PRINTS, as a set.

    Two independent evidence sites, both of them the layout's own furniture and
    both positionally anchored: the `U.S. Funds` denomination line, and the
    product name inside the mailing header.

    The SET is the interesting object and not only its single-element case: an
    empty set means "this document states no denomination", while a two-element
    set means "this document contradicts itself". Those are different facts and
    the jurisdiction default below must treat them differently — it may speak
    where the page is silent and may not resolve a contradiction — so the
    evidence is exposed here rather than collapsed inside `_printed_currency`.
    """
    found: set[str] = set()
    if _US_FUNDS_RE.search(markdown):
        found.add("USD")
    for line in _MAILING_HEADER_RE.findall(markdown.upper()):
        for spelling, code in _PRODUCT_CURRENCY.items():
            if spelling in line:
                found.add(code)
    return found


def _printed_currency(markdown: str) -> str | None:
    """The currency this document PRINTS, or None when it prints none.

    Where the two evidence sites disagree the document contradicts itself and
    this returns None — the caller then leaves the schema default standing
    rather than picking a winner, which is the fail-closed reading of an
    ambiguity.

    Returning None is the ordinary case, not an error: 151 of the 169 English
    RBC documents in the archive print no denomination anywhere, and the honest
    answer for them is "this document does not say".
    """
    found = _printed_currency_evidence(markdown)
    if len(found) != 1:
        return None
    return found.pop()


# ---------------------------------------------------------------------------
# The RBC Canada native-currency default (CURRENCY_DOCTRINE §B, ratified
# 2026-08-16), and the evidence hierarchy it is the second rung of.
# ---------------------------------------------------------------------------
#
# The doctrine's framing matters as much as its answer. The REJECTED rule was
# `absence of "U.S. Funds" => CAD`, which reasons from silence. The RATIFIED
# rule is: a PROVEN RBC Canada account/product has CAD as its native default
# unless the document affirmatively evidences another currency. So nothing
# below ever infers a currency from an absence: the default is gated on a
# CONJUNCTION of four affirmative structural proofs the page must print, and
# two refusals are evaluated before any of them.
#
# The order of evaluation is itself part of the rule:
#
#   1. explicit statement currency evidence          (`_printed_currency`)
#   2. proven account/jurisdiction native default    (`_jurisdiction_currency`)
#   3. otherwise unknown -> nothing is published, the schema default stands
#
# and inside rung 2, U.S.-institution evidence is checked FIRST, so a document
# carrying both a U.S. shape and a Canadian one fails closed rather than being
# swept in on the strength of its Canadian half.
#
# Every predicate below reads printed text and only printed text. A filename or
# a folder label can affect nothing: `analysis.parser_registry.admissible_text`
# strips the intake comment at stage entry (W3 FILENAME-BOUNDARY), and the two
# line anchors mean the comment was never reachable even unstripped. Both
# counterfeit directions — a name that manufactures the default, and a name
# that suppresses it — are pinned in `tests/test_rbc_variants.py` THROUGH that
# seam.

#: A Canadian postal code, `A1A 1A1`, with the letter positions restricted to
#: the alphabet Canada Post actually uses (no D, F, I, O, Q, U anywhere; no W
#: or Z in the leading position). A U.S. ZIP cannot take this shape.
_CA_POSTAL = r"[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ \t]?\d[ABCEGHJ-NPRSTV-Z]\d"

#: The statement-issuing centre's own line, as RBC Canada prints it at the head
#: of page 1: the bank's name, a post-office designator, and a Canadian postal
#: code closing the line. Measured over the RBC superset the archive prints
#: exactly two of them — `P.O. BOX 4047 TERMINAL A TORONTO ON M5W 1L5` and
#: `P.O. BAG SERVICE 2650 CALGARY AB T2P 2M7`.
#:
#: Anchored at both ends on purpose. `ROYAL BANK OF CANADA` occurs inside other
#: issuers' ledgers as a COUNTERPARTY — `Book Transfer Credit B/O: Royal Bank
#: of Canada Payment Centertoronto On Canada` is a posting on Chase statements
#: in this archive — and a posting is not an issuer line.
_J_ISSUER_RE = re.compile(
    r"^[ \t]*ROYAL BANK OF CANADA[ \t]+P\.?[ \t]?O\.?[ \t]+(?:BOX|BAG[ \t]+SERVICE)\b"
    r"[^\n]*?" + _CA_POSTAL + r"[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

#: The branch-of-domicile line printed under the account-summary heading: the
#: bank's name followed by a CIVIC address — `Royal Bank of Canada 5117 49TH
#: ST-PO BOX 359, HIGH PRAIRIE, AB T0G 1E0`. The negative lookahead is what
#: makes this a SECOND, independent proof rather than a re-reading of the
#: issuer line above: a line whose address opens with the post-office
#: designator is the issuing centre and is excluded here.
_J_BRANCH_RE = re.compile(
    r"^[ \t]*ROYAL BANK OF CANADA[ \t]+"
    r"(?!P\.?[ \t]?O\.?[ \t]+(?:BOX|BAG[ \t]+SERVICE)\b)"
    r"[^\n]*?" + _CA_POSTAL + r"[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

#: RBC **Canada's own** service furniture. RBC's U.S. bank publishes
#: `rbcbank.com` and a different toll-free number, so the domain is the
#: cleanest institution discriminator these documents print. The Canadian
#: toll-free is accepted in both spellings the layout sets it in — the
#: mnemonic `1-800-ROYAL…` and the dialled `1-800-769-2520` / `-2511`.
_J_SERVICE_RE = re.compile(
    r"rbcroyalbank\.com"
    r"|1[-‑\s]?800[-‑\s]?769[-‑\s]?25(?:20|11)"
    r"|1[-‑\s]?800[-‑\s]?ROYAL",
    re.IGNORECASE,
)

#: The Canadian Payments Association account shape, in both product spellings
#: the family prints: business `Account number: <5-digit transit> <3-3-1>`,
#: personal `Your account number: <5-digit transit>-<7 digits>`. A U.S. deposit
#: account has no transit number of this shape.
_J_ACCOUNT_RE = re.compile(
    r"\bAccount number:[ \t]*\d{5}[ \t]\d{3}-\d{3}-\d\b"
    r"|\bYour account number:[ \t]*\d{5}-\d{7}\b",
    re.IGNORECASE,
)

#: RBC's U.S. institution and its U.S. banking furniture. Evaluated BEFORE any
#: Canadian marker: the Canadian default must not apply to an RBC U.S. product,
#: and a page carrying both shapes is a page to fail closed on.
#:
#: There is no RBC U.S. document in this archive (measured: zero hits of any of
#: these markers inside the 178-document RBC name superset), so this clause is
#: proven on synthetic printings rather than on the corpus — said plainly here
#: rather than implied. `FDIC`, `ABA`, `RTN` and `Routing …` are U.S. deposit
#: furniture generally, not RBC-specific: they are admitted because a document
#: printing them is not a Canadian retail account whatever name it carries.
_US_INSTITUTION_RE = re.compile(
    r"rbcbank\.com"
    r"|RBC[ \t]+Bank[ \t]*(?:\(Georgia\)|Georgia|USA|,?[ \t]*N\.A\.)"
    r"|Royal[ \t]+Bank[ \t]+of[ \t]+Canada[ \t]*\(USA\)"
    r"|RBC[ \t]+Centura"
    r"|\bFDIC\b"
    r"|\bABA\b"
    r"|\bRTN\b"
    r"|\bRouting[ \t]*(?:#|No\b\.?|Number|Transit)"
    r"|\bRaleigh\b",
    re.IGNORECASE,
)

#: Affirmative evidence of a currency other than the Canadian default,
#: DELIBERATELY wider than `_printed_currency`'s two anchored sites and swept
#: over the whole admissible text rather than over a line.
#:
#: The asymmetry is the point. The anchored reader decides what a document
#: STATES, and it must be narrow or a ledger posting counterfeits a
#: denomination. This one decides only whether to REFUSE the default, so its
#: false positives cost a document its CAD label and never mislabel one: the
#: safe direction. Measured over the superset it fires on exactly the twelve
#: documents the anchored reader already reads as USD, and on nothing else.
_CONTRARY_CURRENCY_RE = re.compile(
    r"U\.?[ \t]?S\.?[ \t]*Funds"
    r"|\bUSD\b"
    r"|U\.?[ \t]?S\.?[ \t]*Dollars?\b"
    r"|United[ \t]+States[ \t]+Dollars?\b"
    r"|American[ \t]+Dollars?\b"
    r"|fonds[ \t]+am.ricains"
    r"|devise[ \t]+am.ricaine"
    r"|US\$|\$US\b|\$U\.S\."
    r"|US[ \t]+BUSINESS[ \t]+ACCOUNT"
    r"|\b(?:EUR|GBP|CHF|JPY|AUD|NZD|MXN|HKD|CNY|RMB|INR|SGD|ZAR|SEK|NOK|DKK"
    r"|PLN|AED|BRL|PHP)\b",
    re.IGNORECASE,
)


def _jurisdiction_currency(markdown: str) -> str | None:
    """CAD when this page PROVES an RBC Canada account, else None.

    Rung 2 of the hierarchy. Three gates, in this order and for these reasons:

    * a U.S. institution/product refuses the Canadian default outright
      (doctrine §B item 3), and it is checked FIRST so that a document carrying
      both a U.S. shape and a Canadian one fails closed rather than being swept
      in on its Canadian half;
    * affirmative evidence of another currency refuses it too (doctrine §B
      item 1), because a default may never overrule what a page says;
    * and then the default applies only on the CONJUNCTION of four affirmative
      proofs the page must print — issuer, service, account shape, branch. Not
      one of them is an absence, and `$` on its own is not consulted anywhere:
      the symbol is printed by both denominations of this same layout.

    Anything else returns None, which is rung 3 — unknown. Nothing here
    resolves an ambiguity; this speaks only where the page is silent.
    """
    if _US_INSTITUTION_RE.search(markdown):
        return None
    if _CONTRARY_CURRENCY_RE.search(markdown):
        return None
    if not (
        _J_ISSUER_RE.search(markdown)
        and _J_SERVICE_RE.search(markdown)
        and _J_ACCOUNT_RE.search(markdown)
        and _J_BRANCH_RE.search(markdown)
    ):
        return None
    return "CAD"


def _statement_currency(markdown: str) -> str | None:
    """The ratified evidence hierarchy, in one place and in order.

    1. **explicit statement currency evidence** — what the document itself
       states, which always has precedence. Two sites that disagree are not one
       statement, so a contradiction stops here and publishes nothing;
    2. **proven account/jurisdiction native default** — consulted only when the
       page states nothing at all, never to overrule or to break a tie;
    3. **otherwise unknown** — None, and the caller leaves the schema default
       exactly where it was rather than inventing a denomination.

    Returning None for rung 3 is deliberately not the same act as returning
    `"USD"`: this function's answer is what the document supports, and today's
    schema default is a separate fact about the field. Recording WHICH rung
    answered is `currency_source` provenance, carded separately.
    """
    printed = _printed_currency_evidence(markdown)
    if len(printed) == 1:
        return printed.pop()
    if printed:
        return None
    return _jurisdiction_currency(markdown)


def _summary_amount(token: str) -> float | None:
    """One `Account Summary` money cell, however its sign was spaced.

    `- $2.55` and `$-2.55` are the same printed figure, but `parse_money`
    searches for the first money-shaped token and would read the detached
    minus as unrelated punctuation, returning `+2.55`. Closing the gap first
    is what makes the three printed placements one value.
    """
    return parse_money(re.sub(r"\s+", "", token))


def _date_from(day: str, mon: str, *, default_year: int) -> str:
    return date(default_year, _MONTHS[mon[:3].upper()], int(day)).isoformat()


def _column_split_signs(amounts: list[int], delta: int) -> list[int] | None:
    """Signs from the printed column order: the credit set is a prefix.

    Inside one balance block RBC prints the Deposits & Credits column above the
    Cheques & Debits column, so the credits are the rows before a single split
    point. Because every amount is positive the prefix total is strictly
    increasing, so at most ONE split reproduces the printed delta — the
    assignment is unique whenever it exists, with nothing to choose between.
    """
    total = sum(amounts)
    running = 0
    for split in range(len(amounts) + 1):
        if 2 * running - total == delta:
            return [1] * split + [-1] * (len(amounts) - split)
        if split < len(amounts):
            running += amounts[split]
    return None


def _subset_signs(amounts: list[int], delta: int, *, max_rows: int = 24,
                  max_states: int = 200_000) -> list[int] | None:
    """Signs from the printed delta when the credits are not a prefix.

    Same evidence, no ordering assumption: find a credit subset whose total is
    `(delta + sum)/2`. Reachability is computed suffix-first so the walk can
    take the earliest admissible row as a credit — the printed column order
    again, used only to make the choice deterministic where several subsets
    reproduce the same delta (which happens when equal amounts sit on both
    sides and every candidate publishes the identical credit/debit totals).
    Bounded in both rows and states so it is total: past the bound it refuses.
    """
    if len(amounts) > max_rows:
        return None
    total = sum(amounts)
    wanted = delta + total
    if wanted % 2 or wanted < 0 or wanted // 2 > total:
        return None
    wanted //= 2

    reachable: list[set[int]] = [set() for _ in range(len(amounts) + 1)]
    reachable[len(amounts)] = {0}
    for index in range(len(amounts) - 1, -1, -1):
        sums = set(reachable[index + 1])
        for value in reachable[index + 1]:
            if value + amounts[index] <= wanted:
                sums.add(value + amounts[index])
        if len(sums) > max_states:
            return None
        reachable[index] = sums
    if wanted not in reachable[0]:
        return None

    signs = []
    remaining = wanted
    for index, amount in enumerate(amounts):
        if amount <= remaining and (remaining - amount) in reachable[index + 1]:
            signs.append(1)
            remaining -= amount
        else:
            signs.append(-1)
    return signs


def _solve_from_printed_balances(rows: list[dict], opening: float | None) -> None:
    """Assign every row's direction from the statement's own running balances.

    The text layer does not carry which activity column an amount was printed
    in, so the sign is read off the arithmetic the bank printed: across the
    rows between two printed balances the signed amounts must reproduce the
    delta. Rows in a block the chain cannot close keep the direction their
    transaction type implies and the document then fails the platform's
    coverage and ledger checks — the signs are never invented to make the
    arithmetic work.
    """
    previous = opening
    segment: list[dict] = []
    for row in rows:
        segment.append(row)
        if row["balance"] is None or previous is None:
            continue
        amounts = [round(item["abs_amount"] * 100) for item in segment]
        delta = round(row["balance"] * 100) - round(previous * 100)
        signs = _column_split_signs(amounts, delta)
        if signs is None:
            signs = _subset_signs(amounts, delta)
        if signs is not None:
            for item, sign in zip(segment, signs):
                item["amount"] = round(sign * item["abs_amount"], 2)
        previous = row["balance"]
        segment = []


def _is_credit(desc: str) -> bool:
    text = desc.upper()
    return (
        "MRCH" in text
        or text.startswith("ATM DEPOSIT")
        or text.startswith("E-TRANSFER RECEIVED")
        or text.startswith("ONLINE TRANSFER RECEIVED")
        or text.startswith("ROYAL FOREIGN EXCHANGE DEPOSIT")
        or text.startswith("COMMERCIAL LOANS")
        or "FUNDS TRANSFER CREDIT" in text
        or text.startswith("BR TO BR")
        or "RETURNED NSF" in text
        or "ITEM RETURNED NSF" in text
    )


def _is_debit(desc: str) -> bool:
    # Generic banking transaction types only. Counterparty names are never
    # sign evidence (R-1 item 7: the two memorized counterparty entries were
    # removed; rows not matching a credit type default to debit below, and
    # printed running balances drive the sign solver, so behaviour is
    # unchanged - see R1_HARDCODE_LOG.md).
    text = desc.upper()
    return any(key in text for key in (
        "MONTHLY FEE",
        "TRANSACTION FEE",
        "CASH DEPOSITED FEE",
        "ONLINE BANKING PAYMENT",
        "ONLINE BANKING TRANSFER",
        "ONLINE TRANSFER SENT",
        "E-TRANSFER SENT",
        "INTERAC PURCHASE",
        "CONTACTLESS INTERAC",
        "CHEQUE -",
        "INSURANCE ",
        "BILL PAYMENT",
        "EQUIPMENT RENT",
        "BUSINESS PAD",
    ))


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


def french_detection_text(markdown: str) -> str:
    """As above, after repairing double-encoded accents."""
    return normalize_mojibake(markdown).upper()


#: The heading RBC prints over the posting table, in each of the two products
#: it issues in English. `Account Activity Details` is the business statement;
#: `Details of your account activity` is the personal one. They are the same
#: document class printed under a different product name — same institution,
#: same three-column grid, same opening/closing rows — so they are one
#: registration rather than two, and the conjunction with the bank name below
#: is what keeps either heading from reaching another issuer's statement.
_ACTIVITY_HEADINGS = ("ACCOUNT ACTIVITY DETAILS", "DETAILS OF YOUR ACCOUNT ACTIVITY")

DETECTION_MARKERS = (
    # A text layer whose own words have digits substituted into them is not
    # readable, however intact the bank name happens to be (W3 §RBCCIBC F1).
    excluding("glyph_damage", glyph_damaged),
    required("bank_name", lambda t: "ROYAL BANK OF CANADA" in t),
    required("activity_section", lambda t: any(h in t for h in _ACTIVITY_HEADINGS)),
)

#: The French activity table's own printed column header. Accented letters
#: reach this parser as U+FFFD — the text layer of this family loses them
#: outright rather than double-encoding them, so `normalize_mojibake` has
#: nothing to repair — and every accent is therefore matched as `.`, the same
#: tolerance `analysis/cibc.py` uses on the same problem.
#:
#: RBC issues its French statement under two products, exactly as it does in
#: English (see `_ACTIVITY_HEADINGS`): the personal one heads its first money
#: column `Retraits`, the business one `Chèques et débits`. This marker
#: required only the personal wording, so the registration claimed the single
#: pinned personal statement and NOTHING else — nineteen business documents of
#: the same layout went unclaimed corpus-wide. Both are matched now, and the
#: conjunction with `BANQUE ROYALE` is what keeps `Retraits` — which is also
#: CIBC's French header — from reaching a CIBC statement.
_FR_ACTIVITY_GRID_RE = re.compile(
    r"DATE DESCRIPTION (?:CH.QUES ET D.BITS|RETRAITS)", re.IGNORECASE)

FRENCH_DETECTION_MARKERS = (
    excluding("glyph_damage", glyph_damaged),
    required("bank_name", lambda t: "BANQUE ROYALE" in t),
    required("activity_header", lambda t: bool(_FR_ACTIVITY_GRID_RE.search(t))),
)

detect = make_detector(DETECTION_MARKERS, detection_text)
detect_french = make_detector(FRENCH_DETECTION_MARKERS, french_detection_text)


def parse_rbc_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    upper = markdown.upper()
    french = _parse_rbc_french_statement(markdown, base=base)
    if french is not None:
        return french
    if not detect(markdown).claims:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Royal Bank of Canada"
    # Currency, under the ratified hierarchy: what the document STATES first,
    # then the proven RBC Canada account's native default, then nothing. A
    # statement that satisfies neither rung leaves the schema default exactly
    # where it was — this reader has no evidence for it and does not invent
    # one. See `_statement_currency`.
    statement_currency = _statement_currency(markdown)
    if statement_currency is not None:
        stmt.currency = statement_currency
    entries: list[tuple[str, str, bool]] = []
    default_year: int | None = None
    in_activity = False
    current_date: str | None = None

    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        u = line.upper()

        if line.startswith("--- Page"):
            in_activity = False
            continue

        pm = _PERIOD_RE.search(line)
        if pm:
            sm, sd, sy, em, ed, ey = pm.groups()
            stmt.period_start = date(int(sy), _MONTH_NAMES[sm.lower()], int(sd)).isoformat()
            stmt.period_end = date(int(ey), _MONTH_NAMES[em.lower()], int(ed)).isoformat()
            default_year = int(ey)

        account = re.search(r"Account number:\s*([0-9 -]+)", line, re.IGNORECASE)
        if account:
            stmt.account_number = account.group(1).strip()

        m = re.search(r"Opening balance on .*?" + _SUMMARY_MONEY, line, re.IGNORECASE)
        if m:
            stmt.beginning_balance = _summary_amount(m.group(1))
        m = re.search(r"Closing balance on .*?" + _SUMMARY_MONEY, line, re.IGNORECASE)
        if m:
            stmt.ending_balance = _summary_amount(m.group(1))
        m = re.search(
            r"Total deposits & credits \((\d+)\)\s*\+?\s*" + _SUMMARY_MONEY, line, re.IGNORECASE
        )
        if m:
            stmt.stated_credit_count = int(m.group(1))
            stmt.stated_total_credits = _summary_amount(m.group(2))
        m = re.search(
            r"Total cheques & debits \((\d+)\)\s*-?\s*" + _SUMMARY_MONEY, line, re.IGNORECASE
        )
        if m:
            stmt.stated_debit_count = int(m.group(1))
            stmt.stated_total_debits = _summary_amount(m.group(2))
        # The personal product prints the same four-row summary in its own
        # words and, unlike the business one, prints NO instance counts beside
        # its totals. The counts stay None rather than being derived from the
        # ledger: a count this document does not print is not a stated count.
        m = re.search(
            r"Total deposits into your account\s*\+\s*" + _SUMMARY_MONEY, line, re.IGNORECASE
        )
        if m:
            stmt.stated_total_credits = _summary_amount(m.group(1))
        m = re.search(
            r"Total withdrawals from your account\s*-\s*" + _SUMMARY_MONEY, line, re.IGNORECASE
        )
        if m:
            stmt.stated_total_debits = _summary_amount(m.group(1))

        if _ACTIVITY_GRID_RE.search(u):
            in_activity = True
            continue
        if in_activity and (u.startswith("CLOSING BALANCE") or u.startswith("ACCOUNT FEES:")):
            in_activity = False
            continue
        if not in_activity or default_year is None:
            continue
        if u.startswith(("BUSINESS ACCOUNT STATEMENT", "ACCOUNT ACTIVITY DETAILS")):
            continue
        # The printed page footer is grid furniture. It is dropped BEFORE the
        # Date column is read, because `<n> of <m>` and its French counterpart
        # `<n> de <m>` are shaped exactly like a day plus a month token.
        if _PAGE_RE.match(line):
            continue

        dm = _DATE_START_RE.match(line)
        if dm:
            # Record the posting date the moment it is seen. RBC puts the date on
            # the first line of each group, and that line often carries no amount
            # because the description wraps ("03 Feb Royal Foreign Exchange
            # deposit" / "Reference 0521... 90.00"). Tracking the date separately
            # from row creation is what keeps the following rows on the right day
            # — deriving it from rows[-1] instead silently folded whole posting
            # dates into the previous one and corrupted the daily ledger.
            current_date = _date_from(dm.group(1), dm.group(2), default_year=default_year)
            line = line[dm.end():].strip()
            repeated = _DATE_START_RE.match(line)
            if repeated:
                line = line[repeated.end():].strip()
        elif current_date is None and not line.upper().startswith("OPENING BALANCE"):
            continue
        entries.append((line, current_date, bool(dm)))

    rows, table_opening = read_grid_rows(
        entries,
        pattern=_MONEY_RE,
        to_amount=lambda token: read_money(token) or 0.0,
        opening_label="OPENING BALANCE",
        closing_label="CLOSING BALANCE",
    )
    rows = [row for row in rows if row["description"] and row["date"]]
    for row in rows:
        # The initial reading is the row's printed transaction type, and it is
        # only ever the fallback: the printed balance chain below overrules it
        # wherever the chain closes. Rows in a block the chain cannot close
        # keep this reading, which is what makes such a block fail the bank's
        # own stated totals instead of being repaired into agreement.
        if _is_credit(row["description"]):
            signed = row["abs_amount"]
        elif _is_debit(row["description"]):
            signed = -row["abs_amount"]
        else:
            signed = -row["abs_amount"]
        row["amount"] = round(signed, 2)

    if not rows:
        return None
    if stmt.beginning_balance is None:
        stmt.beginning_balance = table_opening
    _solve_from_printed_balances(rows, stmt.beginning_balance)

    transactions = [
        Transaction(
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            direction="credit" if row["amount"] > 0 else "debit",
            running_balance=row["balance"],
        )
        for row in rows
    ]
    stmt.transactions = transactions
    return stmt


_FR_DATE_RE = re.compile(r"^(\d{1,2})\s+([^\s]+)\s+(.*)$", re.IGNORECASE)
#: One printed money cell of the French grid.
#:
#: `\s*\)` rather than `\)`: this layout sets the closing bracket in its own
#: column, so an overdrawn balance prints as `(1 066,25 )` with the gap the
#: grid left. Requiring the bracket to be adjacent matched `(1 066,25` — which
#: `parse_french_amount` then read as POSITIVE, because the token it was given
#: no longer looked bracketed. The bracket is this layout's ONLY negative
#: marker, so every overdrawn balance in the family was sign-flipped.
#:
#: `+` in the lookbehind: a reference glued to a `+` (`ARCHIVE+8 129,14`)
#: otherwise began a match at its own last digit, and the space-grouping
#: alternative then swallowed the real amount behind it — `129,14` became
#: `8 129,14`. A digit reachable only by starting mid-reference is not a cell.
_FR_MONEY_RE = re.compile(r"(?<![A-Za-z0-9+])\(?-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}\s*\)?")
#: A French summary figure, anchored so it cannot begin inside the number
#: beside it. Without `(?<!\d)` the space-grouped alternative started at the
#: last digits of the printed YEAR: `... le 23 juillet 2025 801,53 $` read as
#: `025 801,53`, publishing an opening balance of 25,801.53 for one of 801.53.
_FR_SUMMARY_MONEY = r"((?<!\d)(?:\d{1,3}(?: \d{3})+|\d+),\d{2})"
_FR_PAGE_RE = re.compile(r"^\d+ de \d+$", re.IGNORECASE)
#: Full French month names; tokens resolve by unambiguous prefix, so every
#: month works, not only December/January (R-1 item 7).
_FR_MONTH_NAMES = {
    "JANVIER": 1, "FEVRIER": 2, "MARS": 3, "AVRIL": 4, "MAI": 5, "JUIN": 6,
    "JUILLET": 7, "AOUT": 8, "SEPTEMBRE": 9, "OCTOBRE": 10, "NOVEMBRE": 11,
    "DECEMBRE": 12,
}
_FR_PERIOD_RE = re.compile(
    r"Du\s+(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})\s+au\s+(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})",
    re.IGNORECASE,
)


#: The cheque-image pages this layout appends, which declare every cheque the
#: period cleared: `No de série: 253 Montant: 127,40 $`.
_FR_CHEQUE_DECLARED_RE = re.compile(
    r"No de s.rie\s*:\s*(\d+)\s+Montant\s*:", re.IGNORECASE)
def _money_fr(text: str) -> float:
    return parse_french_amount(text, parens=True)


#: The money pattern for a statement that declares its own cheque serials.
#:
#: French thousands are spaced, so a three-digit cheque serial followed by a
#: three-digit amount is indistinguishable from one grouped number:
#: `Chèque - 253 127,40` reads as 253,127.40 and the row books a quarter of a
#: million dollars against an account holding four thousand. Nothing inside
#: the row settles it — but the statement settles it elsewhere, on the
#: cheque-image pages it appends (`No de série: 253 Montant: 127,40 $`).
#:
#: The document authorises the rule, but only DOCUMENT-WIDE, and the
#: difference matters. The declared-serial set is used as a single boolean —
#: "this statement declares cheque serials at all" — which selects this pattern
#: over the plain one. The lookbehind itself is positional, not evidential: it
#: refuses to BEGIN an amount at whatever number is printed straight after
#: `Chèque - `, without ever asking whether THAT number is one of the declared
#: serials. The remaining lookbehind then rejects the serial's interior digits
#: too, so the match lands on the amount.
#:
#: Two shapes are therefore misread on a statement that declares any serial:
#: a cheque row naming a serial the document never declares, and a row with no
#: serial at all (`Chèque - 1 234,56` reads as 234,56). Neither occurs in the
#: family, and both fail closed — the balance walk does not close and the
#: document is withheld rather than published wrong. Consulting the set
#: per row is the correct form and is a follow-up card (W3 §RBCCIBC RC8.8).
#: A statement that declares no serials keeps the plain pattern, and a row
#: mis-read there fails the bank's own totals rather than being split on a guess.
_FR_MONEY_SERIAL_RE = re.compile(
    r"(?<![A-Za-z0-9+])(?<!ch.que - )\(?-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}\s*\)?",
    re.IGNORECASE,
)


def _fr_month(month_token: str) -> int | None:
    """Resolve a (possibly abbreviated) French month token; None if ambiguous."""
    decomposed = unicodedata.normalize("NFKD", month_token)
    token = "".join(c for c in decomposed if c.isalpha()).upper()
    if not token:
        return None
    matches = {
        number
        for name, number in _FR_MONTH_NAMES.items()
        if name.startswith(token)
    }
    return matches.pop() if len(matches) == 1 else None


def _fr_transaction_date(
    day: int, month: int, *, period_start: date, period_end: date
) -> date | None:
    """The unique in-period date for a day/month pair, else None (fail closed).

    Replaces the hardcoded start-year/end-year December/January mapping
    (R-1 item 7): year choice is evidence-based - the date must fall inside
    the printed statement period, whatever months it spans.
    """
    candidates = []
    for year in {period_start.year, period_end.year}:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if period_start <= candidate <= period_end:
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def _fr_initial_sign(desc: str, amount: float) -> float:
    # Real accented characters only - the text is mojibake-normalized first
    # (R-1 item 11). The printed-balance sign solver has the final word.
    text = desc.upper()
    if any(key in text for key in ("REÇU", "ANNUL", "DÉP", "RABAIS")):
        return amount
    return -amount


def _parse_rbc_french_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    markdown = normalize_mojibake(markdown)
    upper = markdown.upper()
    if not detect_french(markdown).claims:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Banque Royale du Canada"
    stmt.currency = "CAD"

    # The full printed period line is required - day, month, and year for
    # both bounds. No default years, no hardcoded month/day (R-1 item 7:
    # previously Dec/Jan-only with (2025, 2026) fallbacks).
    period = _FR_PERIOD_RE.search(markdown)
    if not period:
        return None
    start_day, start_token, start_year, end_day, end_token, end_year = period.groups()
    start_month = _fr_month(start_token)
    end_month = _fr_month(end_token)
    if start_month is None or end_month is None:
        return None
    try:
        period_start = date(int(start_year), start_month, int(start_day))
        period_end = date(int(end_year), end_month, int(end_day))
    except ValueError:
        return None
    if period_end < period_start:
        return None
    stmt.period_start = period_start.isoformat()
    stmt.period_end = period_end.isoformat()

    # NOTE (R-1 item 7/11): the previous account-number regex carried a
    # mojibake label and could never match the real text, so no account was
    # ever extracted here. Extraction stays deliberately absent to keep the
    # audited corpus surface identical; enabling it is proposed in
    # R1_HARDCODE_LOG.md for an Ocean-approved re-baseline.

    # The summary block, read off the collapsed line rather than off the whole
    # document, and in BOTH products' wordings. The personal statement writes
    # `Total des dépôts dans votre compte +` and prints no instance count; the
    # business one writes `Total des dépôts et des crédits (10) +` and prints
    # one. Only the personal wording was ever matched, so on every business
    # statement both stated totals were silently None and
    # `reconcile.summary_ok` had nothing to check.
    #
    # Accents arrive as U+FFFD from this text layer — it loses them outright
    # rather than double-encoding them, so `normalize_mojibake` has nothing to
    # repair — and every accented letter is therefore matched as `.`, the same
    # tolerance `analysis/cibc.py` uses on the same problem.
    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        m = re.search(
            r"solde d'ouverture\b.*?" + _FR_SUMMARY_MONEY + r"\s*\$", line, re.IGNORECASE
        )
        if m:
            stmt.beginning_balance = _money_fr(m.group(1))
        m = re.search(
            r"Total des d.p.ts et des cr.dits\s*\((\d+)\)\s*\+\s*" + _FR_SUMMARY_MONEY,
            line, re.IGNORECASE,
        )
        if m:
            stmt.stated_credit_count = int(m.group(1))
            stmt.stated_total_credits = _money_fr(m.group(2))
        m = re.search(
            r"Total des ch.ques et des d.bits\s*\((\d+)\)\s*-\s*" + _FR_SUMMARY_MONEY,
            line, re.IGNORECASE,
        )
        if m:
            stmt.stated_debit_count = int(m.group(1))
            stmt.stated_total_debits = _money_fr(m.group(2))
        m = re.search(
            r"Total des d.p.ts dans votre compte\s*\+\s*" + _FR_SUMMARY_MONEY,
            line, re.IGNORECASE,
        )
        if m:
            stmt.stated_total_credits = _money_fr(m.group(1))
        m = re.search(
            r"Total des retraits de votre compte\s*-\s*" + _FR_SUMMARY_MONEY,
            line, re.IGNORECASE,
        )
        if m:
            stmt.stated_total_debits = _money_fr(m.group(1))
        m = re.search(
            r"solde de cl.ture\b.*?=\s*" + _FR_SUMMARY_MONEY + r"\s*\$", line, re.IGNORECASE
        )
        if m:
            stmt.ending_balance = _money_fr(m.group(1))

    #: Every cheque serial the statement's own cheque-image pages declare.
    serials = frozenset(_FR_CHEQUE_DECLARED_RE.findall(markdown))

    entries: list[tuple[str, str, bool]] = []
    current_date: str | None = None
    in_activity = False
    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        u = line.upper()
        if line.startswith("--- Page"):
            # Symmetric with the English layout: a page break leaves the
            # activity table and the reprinted column header re-enters it, so
            # the page's own header block never reaches the grid reader.
            in_activity = False
            continue
        if _FR_ACTIVITY_GRID_RE.search(u):
            in_activity = True
            continue
        if in_activity and (u.startswith("SOLDE DE CL") or u.startswith("VOTRE LIMITE")):
            break
        if not in_activity or u.startswith(("DOCUSIGN", "RELEV", "BANQUE ROYALE", "DU ", "RBPDA", "*3", "DATE DESCRIPTION")):
            continue
        # See the English loop: the page footer is dropped before the Date
        # column is read, because `<n> de <m>` is shaped like a French date.
        if _FR_PAGE_RE.match(line):
            continue

        dm = _FR_DATE_RE.match(line)
        if dm:
            day, month_token, rest = dm.groups()
            month = _fr_month(month_token)
            if month is None:
                continue
            resolved = _fr_transaction_date(
                int(day), month, period_start=period_start, period_end=period_end
            )
            if resolved is None:
                continue
            current_date = resolved.isoformat()
            line = rest.strip()
        elif current_date is None and not u.startswith("SOLDE D'OUVERTURE"):
            continue
        entries.append((line, current_date, bool(dm)))

    # Same grid, same two structural rules: the French layout prints
    # `Retraits ($) | Dépôts ($) | Solde ($)`, so a row carries the same two
    # money cells and the same missing column-of-origin. It is a first-class
    # family of this parser, not an exception to it.
    rows, table_opening = read_grid_rows(
        entries,
        pattern=_FR_MONEY_SERIAL_RE if serials else _FR_MONEY_RE,
        to_amount=_money_fr,
        opening_label="SOLDE D'OUVERTURE",
        closing_label="SOLDE DE CL",
    )
    rows = [row for row in rows if row["description"] and row["date"]]
    for row in rows:
        row["amount"] = _fr_initial_sign(row["description"], row["abs_amount"])
    if table_opening is not None:
        stmt.beginning_balance = table_opening
    _solve_from_printed_balances(rows, stmt.beginning_balance)

    transactions = [
        Transaction(
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            direction="credit" if row["amount"] > 0 else "debit",
            running_balance=row["balance"],
        )
        for row in rows
    ]
    if not transactions:
        return None
    stmt.transactions = transactions
    return stmt


#: Public entry point for the French-language RBC layout, registered in its
#: own right by R-3. `parse_rbc_statement` still tries it first until the
#: pipeline switches to registry dispatch.
parse_rbc_french_statement = _parse_rbc_french_statement
