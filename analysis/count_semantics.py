"""What a bank's PRINTED per-direction count actually denotes.

The platform compares the bank's printed `stated_credit_count` /
`stated_debit_count` against the rows it captured
(`analysis/reconcile.py`), and `analysis/pipeline.py` turns a disagreement
into an integrity flag. That comparison is only a defect detector where the
two sides count **the same set of rows**. This module is the table that
decides where they do.

Why a table rather than an equality test
----------------------------------------
Twenty parser modules fill those two fields from twenty different printed
summaries, and the summaries do not all mean the same thing:

- some banks print ONE figure per direction meaning "every row printed in
  this column" — comparable;
- some print a category subtotal, or a sum over a closed label list, so the
  EXPECTED side is only as complete as the parser's label list;
- some print a figure that excludes a line the parser nonetheless records as
  a row (a service charge, a cheque block), so the two sides differ by scope
  while the money reconciles to the cent.

Comparing the second and third classes by equality does not find defects; it
manufactures them. Measured before any of this was wired up: treating the
four banks in that position as comparable would have moved 14 pinned-PASS
corpus documents into the flagged population, at least 5 of them because the
check was misreading the document
(`docs/moneythumb-replacement/COUNTS_P1_MEASUREMENT.md` §7.2).

The default is INCOMPARABLE, and that is load-bearing
-----------------------------------------------------
:func:`semantics_for` returns :data:`UNSURVEYED` — `comparable=False` — for
any parser id absent from :data:`SEMANTICS`. A parser that starts populating
a printed count without a table entry therefore emits **nothing**: no flag,
no outcome movement, no silent assumption that its printed figure means what
some other bank's means. Registering a new parser can only make this check
quieter, never louder, and that property is what makes the table's
completeness auditable rather than assumed. It is asserted directly by
`tests/test_count_semantics.py`.

Provenance
----------
Every entry carries the argument that put it there, with its `file:line`
evidence, taken from the phase-1 measurement
(`COUNTS_P1_MEASUREMENT.md` §3) which Gustavo signed off on 2026-08-13.
The three promotions to comparable (chase debit, us_bank both directions,
wilson_muir both directions) were re-proven against the current archive
before they were written here; each entry records the counterfactual that
earned it.

Two banks are deliberately absent: :data:`SECTION_LEVEL_ORACLES` records
printed count evidence this schema has nowhere to put, so the disclosure
travels as data instead of as a paragraph someone must remember.
"""
from __future__ import annotations

from dataclasses import dataclass

#: The two printed directions. `Transaction.direction` is required and is one
#: of exactly these (`analysis/schema.py:18`) — the column the bank printed
#: the row in, never the sign of the amount.
DIRECTIONS = ("credit", "debit")


@dataclass(frozen=True)
class CountSemantics:
    """What one bank's printed count for one direction denotes.

    `comparable` is the whole decision: False means the printed figure counts
    a different set of rows than `direction == <this direction>` does, so an
    equality test between them is not a defect detector — it is a mis-reading
    of the document. `scope` is the short label a rollup groups by; `reason`
    carries the argument and its `file:line` provenance.
    """

    comparable: bool
    scope: str
    reason: str


def _whole(printed: str, provenance: str) -> CountSemantics:
    """A bank that prints ONE count meaning 'every row in this direction'."""
    return CountSemantics(
        comparable=True,
        scope="whole_direction",
        reason=f"prints {printed}; one printed figure per direction ({provenance})",
    )


#: Per parser id (`analysis/parser_registry_entries.py`), per direction.
#:
#: Only parsers that ASSIGN a printed count are listed. Everything else falls
#: to :data:`UNSURVEYED`.
SEMANTICS: dict[str, dict[str, CountSemantics]] = {
    # -- comparable: one printed figure per direction ------------------
    "atb": {
        "credit": _whole("a credit count and a debit count in one summary block", "analysis/atb.py:121-122"),
        "debit": _whole("a credit count and a debit count in one summary block", "analysis/atb.py:121-122"),
    },
    "capital_one": {
        # "N Deposits/Credits" is a whole-direction figure and cheques ARE
        # inside the printed debit figure by the bank's own label — folded on
        # both sides, which is comparable (cf. bofa, folded on one side only).
        "credit": _whole("'N Deposits/Credits'", "analysis/capital_one.py:81-88, :106"),
        "debit": CountSemantics(
            comparable=False,
            scope="service_charge_excluded_from_printed_debit_count",
            reason=(
                "the printed summary is a LIST of lines — 'N Checks/Debits "
                "($x)' AND a separate 'Service Charges ($y)' "
                "(analysis/capital_one.py:81-108). The service charge "
                "is its own printed line with no count, its money is inside "
                "the printed debit TOTAL, and the parser records it as a debit "
                "ROW. So the printed debit count enumerates a strict subset of "
                "the parser's debit rows: same money, different scope. "
                "Measured: 12 of 12 capital_one documents disagree by EXACTLY "
                "+1 captured debit with a non-zero stated_service_charge on "
                "every one, and debit_coverage is 1.0 with sum_delta 0.0 "
                "throughout — the rows are right and the scopes differ. "
                "`stated_debit_count + 1 where a service charge is printed` is "
                "the mapping a parser card should encode; asserting it at the "
                "platform level would change the expected side, which is a "
                "parser's job and not this table's."
            ),
        ),
    },
    "chase": {
        "credit": _whole("'Deposits and Additions  N  $x'", "analysis/chase.py:428 (native), :581 (table label)"),
        "debit": CountSemantics(
            comparable=True,
            scope="category_subtotal_sum_proven_complete",
            reason=(
                "PROMOTED to comparable on measured evidence. The debit figure "
                "is a SUM over a closed label list (_SUMMARY_DEBIT_LABELS, "
                "analysis/chase.py:380-387; summed at :409-418 and :535-543) "
                "rather than a printed whole-direction count, so it is "
                "comparable only as long as the label list is complete for the "
                "layouts we see. It reproduces the captured debit rows on "
                "387 of 387 chase documents that print one — 0 disagreements "
                "in the phase-1 archive measurement (COUNTS_P1_MEASUREMENT.md "
                "§3.3) and 0 again when re-measured against the current "
                "archive before this entry was written. CAVEAT, recorded "
                "because it is the failure mode this entry buys: a label-list "
                "sum is only as complete as its label list, so a NEW Chase "
                "layout printing a debit category the list does not name "
                "under-counts the EXPECTED side quietly rather than failing "
                "loudly, and would surface here as a count mismatch on correct "
                "rows. That is a flag, never a withholding, and the "
                "remediation is the Chase parser card."
            ),
        ),
    },
    "chase_export": {
        "credit": _whole("'Deposits and Additions  N  $x'", "analysis/chase.py:428 (native), :581 (table label)"),
        "debit": CountSemantics(
            comparable=False,
            scope="category_subtotal_sum",
            reason=(
                "same summary reader as `chase` (analysis/chase.py:380-387), "
                "but NOT promoted with it: no chase_export document in the "
                "archive prints a debit count at all (4 of 4 report the "
                "expected side absent), so the counterfactual that earned "
                "chase's promotion does not exist here and there is nothing to "
                "promote on. Kept incomparable deliberately — an unproven "
                "mapping stays unproven."
            ),
        ),
    },
    "farmers_merchants": {
        "credit": _whole("a credit count in the printed account summary", "analysis/farmers_merchants.py:56-57"),
        "debit": _whole("a debit count in the printed account summary", "analysis/farmers_merchants.py:56-57"),
    },
    "first_community": {
        "credit": _whole("a credit count in the printed summary line", "analysis/first_community.py:150-151"),
        "debit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "prints 'N Debits This Period $X' — one printed figure per "
                "direction (analysis/first_community.py:151). DISCLOSURE, in "
                "the idiom of the bank_of_america entry: the expected side "
                "actually compared here is POST-REPAIR, not the raw printed "
                "read. `repair_first_community_posted_activity` drops the "
                "bank's balance-neutral failed-EFT attempt rows from the "
                "posted activity and, when it does, narrows the printed debit "
                "COUNT and the printed debit TOTAL together "
                "(analysis/first_community.py:209-211, applied at "
                "analysis/pipeline.py:78). The two halves move as a pair or "
                "not at all, and an absent half is never narrowed from the "
                "other. That pairing is what makes this direction comparable: "
                "rewriting the total alone left the count describing a set of "
                "rows the statement no longer reports, which is exactly the "
                "`semantics_difference` D5 adjudicated on the one pinned-PASS "
                "document (`08B2A61B…`), and it is why that document reads "
                "`match` since FIXUPS-1 `acd0b07`. Independence holds: the "
                "repair narrows the expected side from PRINTED "
                "balance-neutrality evidence, never from what we captured, so "
                "nothing derived is read back. If that repair is ever changed "
                "to rewrite one half without the other, this entry stops "
                "being true and must go back to incomparable."
            ),
        ),
    },
    "first_farmers": {
        "credit": _whole("a printed credit count", "analysis/first_farmers.py:152-153"),
        "debit": _whole("a printed debit count", "analysis/first_farmers.py:152-153"),
    },
    "ibc": {
        "credit": _whole("a printed credit count", "analysis/ibc.py:241-242"),
        "debit": _whole("a printed debit count", "analysis/ibc.py:241-242"),
    },
    "linkbank": {
        "credit": _whole("a printed credit count", "analysis/linkbank.py:70-71"),
        "debit": _whole("a printed debit count", "analysis/linkbank.py:70-71"),
    },
    "midflorida": {
        "credit": _whole("a printed credit count", "analysis/midflorida.py:119-120"),
        "debit": _whole("a printed debit count", "analysis/midflorida.py:119-120"),
    },
    "rbc": {
        "credit": _whole("'Total deposits & credits (N)  + $x'", "analysis/rbc.py:298-308 (business; the personal layout prints no counts and assigns none)"),
        "debit": _whole("'Total cheques & debits (N)  - $x'", "analysis/rbc.py:298-308 (business; the personal layout prints no counts and assigns none)"),
    },
    "rbc_french": {
        "credit": _whole("the French twin of 'Total deposits et credits (N)'", "analysis/rbc.py:565-578 — LIVE since W3 RBCCIBC: the business layout prints and assigns both counts (19 docs, all match); the personal product prints none"),
        "debit": _whole("the French twin of 'Total cheques et debits (N)'", "analysis/rbc.py:565-578 — LIVE since W3 RBCCIBC: see credit note"),
    },
    "scotiabank": {
        "credit": _whole("'No. of Credits' in the printed summary grid", "analysis/scotia.py:176-181"),
        "debit": _whole("'No. of Debits' in the printed summary grid", "analysis/scotia.py:176-181"),
    },
    "td_canada": {
        "credit": _whole("'CREDITS  N  $x'", "analysis/td_can.py:449-453"),
        "debit": _whole("'DEBITS  N  $x'", "analysis/td_can.py:454-457"),
    },
    "td_canada_native": {
        # Accumulated across every printed summary line (`(or 0) + n`,
        # analysis/td_can.py:451/456 and :586-598) because a TD statement can
        # print the block more than once. Each line is still a whole-direction
        # figure, so the sum is one; a REPEATED block would double the expected
        # side, which is a defect worth flagging rather than a semantics
        # difference this table should hide.
        "credit": _whole("'CREDITS  N  $x', summed over printed summary lines", "analysis/td_can.py:451, :586-592"),
        "debit": _whole("'DEBITS  N  $x', summed over printed summary lines", "analysis/td_can.py:456, :598"),
    },
    "texas_bank": {
        "credit": _whole("'Deposits ( N ) + $x'", "analysis/texas_bank.py:68, :129"),
        "debit": CountSemantics(
            comparable=False,
            scope="service_charge_excluded_from_printed_debit_count",
            reason=(
                "the same shape as capital_one, and the parser proves it on "
                "itself: the summary prints 'Checks/Debits ( N ) - $x' and a "
                "SEPARATE 'Service Charge - $y' (analysis/texas_bank.py:70-71), "
                "and the parser's own acceptance gate is "
                "`debit_sum == debits + service_charge` (:108, :111-112) — it "
                "requires the service-charge row to be a debit row whose money "
                "is OUTSIDE the printed 'Checks/Debits' figure. The printed "
                "count therefore cannot enumerate it. Measured: the single "
                "texas_bank document disagrees by exactly +1."
            ),
        ),
    },
    "demo_national": {
        "credit": _whole("a printed credit count", "analysis/demo_national.py:50-51"),
        "debit": _whole("a printed debit count", "analysis/demo_national.py:50-51"),
    },
    # `community_section` and `scanned_small_bank` already run a count
    # comparison AS A CLAIM GATE — on mismatch the parser returns None and the
    # document goes unclaimed (analysis/community_section.py (gate),
    # analysis/scanned_small_bank.py:206-207, :368-369, :525-527). A document
    # they claimed has, by construction, matching counts — and for the three
    # `community_section` registrations that is now matching counts UNDER THIS
    # CHECK'S OWN KEY.
    #
    # RECORD OF A CHANGE (W3 §JHA-CELL). Until that cell the gate keyed on
    # `amount > 0` / `amount < 0` — the SIGN — while this check keys on
    # `Transaction.direction`, the column the bank printed the row in. A
    # zero-amount row is on neither side of a sign test and on exactly one side
    # of a column test, so the two could disagree and these parsers were NOT
    # immune to this check. The gate now keys on `direction` as well, for the
    # reason the difference exists: this platform posts genuine `$0.00` rows (a
    # returned ACH), the bank counts them, and a sign-keyed gate therefore
    # rejected documents whose ledgers were complete — three archive documents
    # measurably so. The two keys are now the same key.
    #
    # What that costs is stated plainly: these three parsers are now immune to
    # this check BY CONSTRUCTION, so a `match` here is a tautology and carries
    # no information. It is not a silent one — this paragraph is the
    # disclosure, and the independent evidence for these parsers is the printed
    # per-section `N item(s) totaling $X` trailer, which
    # `_section_oracle_disagrees` checks and which no summary figure can
    # reproduce.
    "mission_valley": {
        "credit": _whole("a printed credit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
        "debit": _whole("a printed debit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
    },
    "dakota_west": {
        "credit": _whole("a printed credit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
        "debit": _whole("a printed debit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
    },
    "community_section": {
        "credit": _whole("a printed credit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
        "debit": _whole("a printed debit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
    },
    "apex_scanned": {
        "credit": _whole("a printed credit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
        "debit": _whole("a printed debit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
    },
    "southside_scanned": {
        "credit": _whole("a printed credit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
        "debit": _whole("a printed debit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
    },
    "us_bank": {
        "credit": CountSemantics(
            comparable=True,
            scope="category_subtotal_sum_proven_complete",
            reason=(
                "PROMOTED to comparable on measured evidence. Both counts are "
                "sums over the printed Account Summary's category lines, split "
                "into credit and debit BY THE SIGN OF THE CATEGORY AMOUNT "
                "(analysis/us_bank.py:399-412, :467-468) — a summary-level sign split, "
                "which is why this was held incomparable until it had been "
                "measured. It reproduces the captured rows on 40 of 40 us_bank "
                "documents in both directions (COUNTS_P1_MEASUREMENT.md §3.3), "
                "re-measured as 40/40 with 0 disagreements against the current "
                "archive before this entry was written. Note what the evidence "
                "does and does not cover: the categories are printed by the "
                "bank per direction, so the split is over printed subtotals "
                "and not over individual row amounts — no zero-amount row can "
                "move across it."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="category_subtotal_sum_proven_complete",
            reason=(
                "PROMOTED with the credit direction and on the same evidence: "
                "the printed Account Summary category sums split by the sign "
                "of the category amount (analysis/us_bank.py:399-412, :467-468), "
                "reproducing the captured debit rows on 40 of 40 documents in "
                "the phase-1 measurement and 40 of 40 again when re-measured "
                "against the current archive."
            ),
        ),
    },
    "wilson_muir": {
        "credit": CountSemantics(
            comparable=True,
            scope="multi_category_sum_proven_complete",
            reason=(
                "PROMOTED to comparable on measured evidence. The expected "
                "side is `deposit_count + automatic_deposit_count` "
                "(analysis/wilson_muir.py:162) — a two-way sum of printed "
                "category counts — and the parser gates on the printed TOTALS "
                "rather than on the counts (:133-136), so a count "
                "disagreement is reachable rather than gated away. It "
                "reproduces the captured credit rows on 8 of 8 wilson_muir "
                "documents (COUNTS_P1_MEASUREMENT.md §3.3), re-measured 8/8 "
                "with 0 disagreements against the current archive. Same "
                "caveat as any category sum: a printed category this parser "
                "does not add would under-count the expected side."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="multi_category_sum_proven_complete",
            reason=(
                "PROMOTED with the credit direction. The expected side is the "
                "three-way sum `debit_count + automatic_withdrawal_count + "
                "card_count` (analysis/wilson_muir.py:163), reproducing the "
                "captured debit rows on 8 of 8 documents in the phase-1 "
                "measurement and 8 of 8 again when re-measured against the "
                "current archive."
            ),
        ),
    },
    # -- incomparable, each with its own argument ----------------------
    "altana": {
        # BOTH directions, on one argument. The parser's acceptance gate is
        # `label_deposits != deposit_count -> return None` and
        # `label_withdrawals != withdrawal_count -> return None`
        # (analysis/altana.py:187-190): what the printed counts are proven
        # equal to is the count of LABEL-MATCHED rows, not the count of rows in
        # that direction. Classifying only the debit side incomparable — which
        # the parser's comment names explicitly — while comparing the credit
        # side on the identical construction would be an inconsistency this
        # check would then report as a defect.
        "credit": CountSemantics(
            comparable=False,
            scope="label_scoped_subset",
            reason=(
                "the printed deposit count is gated equal to the count of "
                "LABEL-MATCHED deposit rows (analysis/altana.py:187), not to "
                "every row the parser records as a credit. Measured: 3 of 3 "
                "altana documents record 1-2 more credit rows than the "
                "printed figure, and altana sets no stated_total_credits at "
                "all, so nothing else in the payload can even see it. An "
                "altana parser card owns the label scope; until it lands, "
                "this direction says nothing."
            ),
        ),
        "debit": CountSemantics(
            comparable=False,
            scope="label_scoped_subset",
            reason=(
                "the parser's own comment records it: \"the statement's "
                "withdrawal summary is LABEL-BASED and excludes some "
                "balance-increasing adjustment rows\" "
                "(analysis/altana.py:203-206), and the gate at :189 pins the "
                "printed figure to the labelled subset. The parser "
                "deliberately keeps the line-item rows rather than the "
                "summary's scope."
            ),
        ),
    },
    "bank_of_america": {
        "credit": _whole("'# of deposits/credits: N'", "analysis/bofa.py:427-428, :552-554, :639-641"),
        "debit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "PROMOTED to comparable once the three readers were made to "
                "agree (BOFA-COUNTS). The history is the argument: BofA prints "
                "'# of withdrawals/debits' and, on some layouts, a SEPARATE "
                "'Total # of checks', and the Checks section's rows are "
                "recorded as debits by the parser — so the repair path added "
                "`debit_count + (check_count or 0)` while the native and table "
                "readers stored the raw printed figure. One field, two "
                "meanings, and the payload records nowhere which ran. "
                "CHARACTERISED FIRST, from the archive's own documents: the "
                "raw printed figure reproduces the captured debit rows on "
                "344 of 344 documents that print it, and `raw + check_count` "
                "on 0 of the 107 that also print a cheque count — the printed "
                "statistic ALREADY counts cheques, and the mapping "
                "double-counted them on every document where it fired. The "
                "control is the credit sibling in the same printed statistics "
                "box, 344 of 344. The repair now stores the raw figure "
                "(analysis/bofa.py:642) and all three readers store one "
                "documented scope (`_SUMMARY_COUNT_SCOPE`, :368-403). "
                "WHY THE MAPPING LOOKED RIGHT, recorded so nobody re-derives "
                "it: the cheque MONEY genuinely is outside 'Withdrawals and "
                "other debits' — the summary prints 'Checks' as its own line, "
                "equal to the section's own 'Total checks' figure on 107 of "
                "107, and `stated_total_debits` really does sum those lines. "
                "Money scope and count scope differ on this bank, and reading "
                "one off the other is the defect. "
                "SCOPE OF THE EVIDENCE: all 344 are the native business "
                "summary; the 16 consumer-vocabulary documents print no debit "
                "count at all (the check is `not_printed` there, never a "
                "comparison), and NO archive document renders the account "
                "summary as an HTML table, so the table reader's scope is "
                "inherited from the identical printed line rather than "
                "measured. Independence holds: the expected side is the "
                "integer the bank printed, read straight off the page, with "
                "nothing derived from a captured row. FALSIFIER: if a BofA "
                "layout is ever found whose '# of withdrawals/debits' excludes "
                "the cheque block — the tell is `raw + Total # of checks` "
                "matching where `raw` does not — this entry stops being true "
                "and the direction goes back to incomparable rather than the "
                "readers going back to disagreeing."
            ),
        ),
    },
    # W3 §CITI3 card C. A new registration, surveyed here rather than left
    # UNSURVEYED because its printed counts and the rows this parser captures
    # are the same set BY CONSTRUCTION, and that construction is checked.
    "zions": {
        "credit": CountSemantics(
            comparable=True,
            # The existing label, not a new one: this IS "one printed figure
            # per direction". The grid prints one instance count above the
            # `Deposits/Credits` column and the parser publishes exactly the
            # rows of the `DEPOSITS/CREDITS` section that column heads.
            scope="whole_direction",
            reason=(
                "The summary grid prints one instance count above the "
                "`Deposits/Credits` column (analysis/zions.py:_blocks), and "
                "the parser's credit rows are exactly the rows of the "
                "`DEPOSITS/CREDITS` section that column heads — one printed "
                "column, one published direction. Two things stop the sides "
                "drifting apart silently: the parser refuses any row whose "
                "printed sign contradicts its section, and it parses the "
                "grid's column legend rather than assuming it, so a layout "
                "printing an unknown extra column fails the document closed "
                "instead of under-counting (analysis/zions.py:_rows, "
                ":_blocks). Measured over all 13 archive documents of the "
                "family: 13/13 agree, 0 disagreements, 0 flags raised."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="multi_category_sum_proven_complete",
            reason=(
                "The layout splits money out across TWO printed columns, "
                "`Withdrawals/Debits` and `Checks Processed`, each with its "
                "own instance count; the expected side is their sum, and the "
                "debit TOTAL is the sum of the same two columns, so count and "
                "total cover one scope — the alignment W3 §FIXUPS-1 corrected "
                "on `first_community`. Both categories post into the single "
                "`CHARGES/DEBITS` section, which is what the parser reads; "
                "`CHECKS PROCESSED` is a register of rows already posted "
                "there and is deliberately not read, so no cheque is counted "
                "twice. Measured over all 13 archive documents: 13/13 agree, "
                "0 disagreements, 0 flags raised. Same caveat as any category "
                "sum — a third printed debit category this parser did not add "
                "would under-count the expected side; the family prints none, "
                "and the grid's column legend is parsed rather than assumed, "
                "so an unknown third column fails the document closed."
            ),
        ),
    },
}

#: Applied to any parser that populated a printed count but is not in
#: :data:`SEMANTICS`. Fail-closed for the CHECK, which means SILENT: an unread
#: semantics is not a comparable one, so the flag is never raised.
UNSURVEYED = CountSemantics(
    comparable=False,
    scope="unsurveyed",
    reason=(
        "this parser is not in the surveyed semantics table but populated a "
        "printed count. The check refuses to compare semantics nobody has "
        "read rather than default to equality, so it says nothing at all "
        "about this direction."
    ),
)

#: Banks whose printed count evidence exists but is PER SECTION, which the
#: `Statement` schema has no field for, so it is not expressible in this
#: check's schema at all. Recorded here so the disclosure is data rather than
#: a paragraph someone must remember to write: PNC prints an item count per
#: section (`W3_TRACKA_LOG.md` §3.3, §3.7 item 3) and is the witness that
#: caught the swallowed-section defect, but a PER-DIRECTION check would not
#: have caught the `Fee Refunds` case because the direction totals were right.
#: Wells prints a per-account `Totals` line nothing reads (§W7.4). Neither
#: parser assigns a per-direction count, so both are silent here — which is
#: TRUE of the schema and FALSE of the document, and that distinction is the
#: disclosure.
SECTION_LEVEL_ORACLES = {
    "pnc": "prints a per-SECTION item count the Statement schema cannot hold (W3_TRACKA_LOG.md sec 3.3, sec 3.7 item 3); no per-direction field is assigned",
    "wells_fargo": "prints a per-account `Totals` line that no parser reads (W3_TRACKA_LOG.md sec W7.4)",
}


def semantics_for(parser_id: str | None, direction: str) -> CountSemantics:
    """The count semantics for one parser and one printed direction.

    An unknown parser — including `None`, which is what an LLM extraction or
    an unclaimed document has — gets :data:`UNSURVEYED`, never a comparison.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown direction: {direction!r}")
    table = SEMANTICS.get(parser_id or "")
    if table is None:
        return UNSURVEYED
    return table[direction]


def counts_comparable(parser_id: str | None, direction: str) -> bool:
    """Does this parser's printed count for this direction denote our rows?

    The one predicate the integrity check calls. False is the default for
    everything unproven, so a caller that forgets to ask gets no flag rather
    than a wrong one.
    """
    return semantics_for(parser_id, direction).comparable
