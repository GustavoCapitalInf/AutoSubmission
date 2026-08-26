"""W3 §TD-FRENCH: the TD Canada Trust French (Quebec) printed layout.

Every fixture here is a SYNTHETIC reproduction of a *structural shape* found in
the 13-document French TD family. The institution and column markers are TD's
own layout sentinels — they are what the parser keys on — and every
description, counterparty, date, amount and account number is invented.

The grid is the English one, issued in French:

    DESCRIPTION        RETRAITS       DEPOTS           DATE    SOLDE

so it loses exactly what the English one loses. The text layer emits each
printed row as a single line with the column gaps collapsed, so a row arrives
as `<description> <amount> <DATE> [<solde>]`: the amount survives and *which of
the two money columns it was printed in* does not. The bank prints the answer
anyway, as a running balance at the end of each date group, and
`td_can._credit_counts_from_balances` reads it back out.

What is genuinely new here, and what each family pins:

F1 space-thousands vs description digits
    `1 640,44` is two whitespace tokens, and TD's descriptions end in digits
    (`UO342 TFR-A 5347895`). Both readings of `PETRO-CANADA 30 145,55` are
    grammatical. The rule and its fail-closed consequence are pinned BOTH ways.
F2 `DC` overdrawn suffix
    where the English layout prints a minus sign, this one suffixes `DC` — on
    the opening balance, on a row's balance, and on a page carry.
F3 page carry
    `SOLDE REPORTE` reprints the carried balance at the top of every page and
    closes a group the page break landed inside.
F4 cheque-enclosure terminator
    `<n> CHQS JOINTS`; the count is statement data, and both the singular
    `CHQ` and a non-zero count must still close the ledger.
F5 per-page footers
    `Credits <n> <total>` accumulates over pages, and `Debits 18 924,29` is
    eighteen rows totalling 924.29 — not one row totalling 18,924.29.
F6 day-first dates over a year boundary
    `31DEC` and `30JAN` on one statement take different years.
F7 direction codes
    TD's own French codes, used only where the printed balances decide
    nothing. A counterparty name is never a code.

Each family carries a negative fixture: the rule must fire on the printed
structure, never on remembered wording.
"""
from __future__ import annotations

import pytest

from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401 — populates the registry
from analysis.pipeline import analyze_markdown
from analysis.reconcile import reconcile
from analysis.td_canada_french import (
    _french_credit_like,
    _french_direction_code,
    detect,
    parse_td_canada_french_statement,
)

PERIOD = "31 JAN 26 - 28 FEV 26"

#: One printed page: the head furniture the parser reads, the grid, the ledger,
#: and the page footer block. Branch, account and amounts are invented.
_PAGE = """
--- Page {page} ---
SUCCURSALE MODELE
900 RUE INVENTEE
Tel: 1-800-000-0000
CLIENT MODELE INC 1 RUE INVENTEE
Relevé de compte Type de compte Relevé du - au
Succursale No de compte {period}
COMPTE
INVESTISSEUR
COMMERCIAL
1111 1111-2222222 Page {page} de {pages}
DESCRIPTION RETRAITS DEPOTS DATE SOLDE
{ledger}
TDCDA11111_2222222_003 - 0000000 000001
No. Montant
{terminator}
SOLDE CREDITEUR MENS MOYEN 500,00 $
Crédits {credits}
SOLDE MIN MENSUEL 100,00DC $
CONTENU DEP - DEV 0 EFF 0 LOT NON COM 0
Débits {debits}
Veuillez signaler par écrit toute erreur ou irrégularité dans les 30 jours.
Comptes émis par : LA BANQUE TORONTO-DOMINION
"""

_DEFAULT_TERMINATOR = "0 CHQS JOINTS PROCHAINE DATE DE RELEVE 31 MAR 26"


def page(
    ledger: str,
    *,
    number: int = 1,
    pages: int = 1,
    period: str = PERIOD,
    credits: str = "0 0,00",
    debits: str = "0 0,00",
    terminator: str = _DEFAULT_TERMINATOR,
) -> str:
    return _PAGE.format(
        page=number,
        pages=pages,
        period=period,
        ledger=ledger.strip("\n"),
        terminator=terminator,
        credits=credits,
        debits=debits,
    )


def amounts(stmt):
    return [t.amount for t in stmt.transactions]


def parse(*args, **kwargs):
    return parse_td_canada_french_statement(page(*args, **kwargs))


#: A group of three rows whose printed delta admits two different splits
#: (30 = 30, and 30 = 20 + 10), so the arithmetic decides nothing and the
#: transaction codes are what remains. Every F7 fixture is this shape.
UNDETERMINED = """
SOLDE REPORTE 31JAN 100,00
{row} 30,00 01FEV
LIGNE SANS CODE UN 20,00 01FEV
LIGNE SANS CODE DEUX 10,00 01FEV 100,00
"""


# ===========================================================================
# Detection — issuer furniture only, and the full negative set
# ===========================================================================

class TestDetection:
    def test_the_two_pieces_of_issuer_furniture_claim_the_document(self):
        assert detect(page("SOLDE REPORTE 31JAN 100,00")).claims

    def test_the_grid_header_alone_is_not_a_claim(self):
        assert not detect("DESCRIPTION RETRAITS DEPOTS DATE SOLDE\n").claims

    def test_the_issuer_line_alone_is_not_a_claim(self):
        assert not detect("Comptes émis par : LA BANQUE TORONTO-DOMINION\n").claims

    def test_the_bank_name_alone_is_not_a_claim(self):
        """The marker is the issuer LINE, not the institution's name.

        A Quebec statement from another bank can print `LA BANQUE
        TORONTO-DOMINION` in a transfer description, and R4-3 is the finding
        that says a bank name is not evidence about whose statement this is.
        """
        document = (
            "DESCRIPTION RETRAITS DEPOTS DATE SOLDE\n"
            "VIREMENT A LA BANQUE TORONTO-DOMINION 40,00 01FEV\n"
        )
        assert not detect(document).claims

    def test_the_english_td_layout_is_not_claimed(self):
        english = (
            "Accounts issued by: THE TORONTO-DOMINION BANK\n"
            "DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE\n"
            "BALANCE FORWARD JAN31 100.00\n"
        )
        assert not detect(english).claims

    def test_no_other_registration_claims_a_french_td_statement(self):
        """The cross-product in test_parser_conformance.py covers the minimal
        fixture; this covers a full document, which is what discovery sees."""
        document = page("""
SOLDE REPORTE 31JAN 100,00
DEPOT MOBILE 40,00 01FEV 140,00
""", credits="1 40,00")
        claimants = [
            reg.id for reg in pr.registrations() if reg.detect(document).claims
        ]
        assert claimants == ["td_canada_french"]

    def test_the_document_resolves_to_this_parser_without_ambiguity(self):
        dispatch = pr.resolve(page("""
SOLDE REPORTE 31JAN 100,00
DEPOT MOBILE 40,00 01FEV 140,00
""", credits="1 40,00"))
        assert dispatch.outcome == "claimed"
        assert dispatch.parser_id == "td_canada_french"
        assert dispatch.candidates == (("td_canada_french", 0.5),)

    def test_detection_survives_a_dropped_accent(self):
        """The furniture is printed unaccented and the prose is not; an OCR
        pass can move either way, so neither spelling may decide detection."""
        document = page("SOLDE REPORTE 31JAN 100,00").replace(
            "Comptes émis par", "Comptes emis par"
        )
        assert detect(document).claims

    def test_detection_survives_double_encoded_accents(self):
        mojibake = page("SOLDE REPORTE 31JAN 100,00").replace(
            "é", "Ã©"
        )
        assert detect(mojibake).claims

    def test_detection_is_unchanged_by_the_source_filename_comment(self):
        document = page("SOLDE REPORTE 31JAN 100,00")
        named = (
            "<!-- source: TD Bank/Releve_de_compte_FR.pdf | pages: 1 | "
            "model: native-pdf-text | empty: 0 -->\n\n" + document
        )
        assert detect(document) == detect(named)

    def test_the_filename_alone_never_produces_a_claim(self):
        named = (
            "<!-- source: TD Bank/Comptes émis par LA BANQUE TORONTO-DOMINION "
            "DESCRIPTION RETRAITS DEPOTS DATE SOLDE.pdf -->\n\n"
            "A lease agreement, not a bank statement.\n"
        )
        assert not pr.by_id("td_canada_french").detect(named).claims

    def test_detection_never_raises(self):
        for document in ("", "\x00\x01", "é" * 100, "%PDF-1.4 garbage"):
            detect(document)


# ===========================================================================
# F1 — space thousands versus description digits, pinned both ways
# ===========================================================================

class TestF1SpaceThousands:
    def test_a_thousands_group_is_joined_into_one_amount(self):
        stmt = parse("""
SOLDE REPORTE 31JAN 5 000,00
DEPOT MOBILE 1 234,56 01FEV 6 234,56
""", credits="1 1 234,56")
        assert amounts(stmt) == [1234.56]
        assert stmt.transactions[0].description == "DEPOT MOBILE"

    def test_two_groups_are_joined(self):
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
DEPOT MOBILE 10 034,67 01FEV 10 134,67
""", credits="1 10 034,67")
        assert amounts(stmt) == [10034.67]

    def test_a_description_keeps_its_digits_when_the_amount_cannot_continue(self):
        """`40,00` has a two-digit integer part, and a French thousands group is
        always padded to three, so nothing to its left can be part of it. The
        seven-digit account number stays in the description."""
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
UO342 TFR-A 5347895 40,00 01FEV 60,00
""", debits="1 40,00")
        assert amounts(stmt) == [-40.0]
        assert stmt.transactions[0].description == "UO342 TFR-A 5347895"

    def test_a_zero_padded_token_cannot_open_a_number(self):
        """Only the groups AFTER the first are padded to three digits, so
        `007` cannot be where a number starts: this is an invoice number
        printed beside an amount, not 7 100,00.

        The padded token is three digits, so it is taken by the thousands-group
        loop and never reaches the leading-group test — narrowing that pattern
        alone does not close this shape.
        """
        stmt = parse("""
SOLDE REPORTE 31JAN 200,00
FACTURE 007 100,00 01FEV 100,00
""", debits="1 100,00")
        assert amounts(stmt) == [-100.0]
        assert stmt.transactions[0].description == "FACTURE 007"

    def test_a_zero_padded_leading_group_is_not_a_leading_group(self):
        """The other half of the same rule, on the shape that does reach the
        leading-group test: `07` is one or two digits, not three."""
        stmt = parse("""
SOLDE REPORTE 31JAN 200,00
FACTURE 07 100,00 01FEV 100,00
""", debits="1 100,00")
        assert amounts(stmt) == [-100.0]
        assert stmt.transactions[0].description == "FACTURE 07"

    def test_a_genuine_number_with_a_padded_middle_group_still_reads_whole(self):
        """The contrast half. `1 007 100,00` pads its middle group and opens
        with a significant digit, so all three groups are one amount."""
        stmt = parse("""
SOLDE REPORTE 31JAN 1 007 200,00
LIGNE SANS CODE UN 1 007 100,00 01FEV 100,00
""", debits="1 1 007 100,00")
        assert amounts(stmt) == [-1007100.0]
        assert stmt.transactions[0].description == "LIGNE SANS CODE UN"

    def test_a_single_digit_amount_is_never_joined_leftwards(self):
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
LIGNE AVEC CODE 900 5,00 01FEV 95,00
""", debits="1 5,00")
        assert amounts(stmt) == [-5.0]
        assert stmt.transactions[0].description == "LIGNE AVEC CODE 900"

    #: The genuinely ambiguous shape: a description ending in one to three
    #: digits, then an amount whose integer part is exactly three digits. Both
    #: readings are grammatical French. The two tests below are the same line
    #: under two different printed balances.
    AMBIGUOUS = """
SOLDE REPORTE 31JAN {opening}
VENDEUR INVENTE 30 145,55 01FEV
FRAIS MENSUELS 10,00 01FEV {closing}
"""

    def test_the_joined_reading_is_taken_and_the_balance_confirms_it(self):
        # 40 000,00 - 30 145,55 - 10,00 = 9 844,45.
        stmt = parse_td_canada_french_statement(page(
            self.AMBIGUOUS.format(opening="40 000,00", closing="9 844,45"),
            debits="2 30 155,55",
        ))
        assert amounts(stmt) == [-30145.55, -10.0]
        assert stmt.transactions[0].description == "VENDEUR INVENTE"
        assert reconcile(stmt).ok

    def test_the_split_reading_is_not_rescued_it_fails_closed(self):
        """Same line, but here the printed balance fits only the other reading
        (500,00 - 145,55 - 10,00 = 344,45). The parser does not switch: it
        keeps the French reading of the bank's own money format, the group
        goes unsolved, and the document does not reconcile against the summary
        the solver never saw. Withheld, never published wrong."""
        stmt = parse_td_canada_french_statement(page(
            self.AMBIGUOUS.format(opening="500,00", closing="344,45"),
            debits="2 155,55",
        ))
        assert amounts(stmt) == [-30145.55, -10.0]
        assert not reconcile(stmt).ok

    def test_a_balance_is_read_the_same_way(self):
        stmt = parse("""
SOLDE REPORTE 31JAN 1 000,00
DEPOT MOBILE 500,00 01FEV 1 500,00
""", credits="1 500,00")
        assert stmt.beginning_balance == 1000.0
        assert stmt.ending_balance == 1500.0


# ===========================================================================
# F2 — the DC overdrawn suffix
# ===========================================================================

class TestF2OverdrawnSuffix:
    def test_an_overdrawn_opening_balance_is_negative(self):
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00DC
DEPOT MOBILE 40,00 01FEV 60,00DC
""", credits="1 40,00")
        assert stmt.beginning_balance == -100.0
        assert stmt.ending_balance == -60.0
        assert amounts(stmt) == [40.0]

    def test_the_suffix_changes_the_arithmetic_not_only_the_display(self):
        """Same rows and the same digits in the balance cell; only the `DC`
        differs, and it flips the direction the balances imply."""
        without = parse("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV 140,00
""", credits="1 40,00")
        with_dc = parse("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV 60,00
""", debits="1 40,00")
        assert amounts(without) == [40.0]
        assert amounts(with_dc) == [-40.0]

    def test_an_overdrawn_carry_closes_a_split_group(self):
        document = page("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 250,00 01FEV
""", number=1, pages=2, debits="1 250,00") + page("""
SOLDE REPORTE 01FEV 150,00DC
LIGNE SANS CODE DEUX 50,00 02FEV 200,00DC
""", number=2, pages=2, debits="1 50,00")
        stmt = parse_td_canada_french_statement(document)
        assert amounts(stmt) == [-250.0, -50.0]
        assert stmt.ending_balance == -200.0


# ===========================================================================
# F3 — the page carry
# ===========================================================================

class TestF3PageCarry:
    def test_a_carry_closes_the_group_the_page_break_landed_inside(self):
        document = page("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV
""", number=1, pages=2, credits="1 40,00") + page("""
SOLDE REPORTE 01FEV 140,00
LIGNE SANS CODE DEUX 25,00 02FEV 115,00
""", number=2, pages=2, debits="1 25,00")
        stmt = parse_td_canada_french_statement(document)
        assert amounts(stmt) == [40.0, -25.0]

    def test_a_reprinted_carry_that_closes_nothing_adds_no_row(self):
        document = page("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV 140,00
""", number=1, pages=2, credits="1 40,00") + page("""
SOLDE REPORTE 01FEV 140,00
LIGNE SANS CODE DEUX 25,00 02FEV 115,00
""", number=2, pages=2, debits="1 25,00")
        stmt = parse_td_canada_french_statement(document)
        assert amounts(stmt) == [40.0, -25.0]
        assert stmt.beginning_balance == 100.0

    def test_a_group_spans_several_printed_dates(self):
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV
LIGNE SANS CODE DEUX 25,00 02FEV
LIGNE SANS CODE TROIS 10,00 03FEV 155,00
""", credits="2 65,00", debits="1 10,00")
        assert amounts(stmt) == [40.0, 25.0, -10.0]


# ===========================================================================
# F4 — the cheque-enclosure terminator
# ===========================================================================

class TestF4LedgerTerminator:
    LEDGER = """
SOLDE REPORTE 31JAN 100,00
DEPOT MOBILE 40,00 01FEV 140,00
"""
    #: The cheque-image page TD prints after the ledger. Its line is shaped
    #: exactly like a ledger row — an amount and a date on one line — so only
    #: the terminator keeps it out.
    AFTER_THE_LEDGER = "\n1111-2222222 CHEQUE # 00089 217,19 $ 05FEV\n"

    @pytest.mark.parametrize("count", ["0", "1", "7", "23"])
    def test_any_cheque_count_closes_the_ledger(self, count):
        """The count is statement data. Matching a literal one left the ledger
        open past the end of every page that encloses a cheque."""
        noun = "CHQ" if count == "1" else "CHQS"
        stmt = parse_td_canada_french_statement(page(
            self.LEDGER,
            credits="1 40,00",
            terminator=f"{count} {noun} JOINTS PROCHAINE DATE DE RELEVE 31 MAR 26",
        ) + self.AFTER_THE_LEDGER)
        assert amounts(stmt) == [40.0]

    def test_a_ledger_shaped_line_before_the_terminator_is_still_a_row(self):
        """The contrast half: the terminator is what ends the grid, not the
        wording of the line after it."""
        stmt = parse_td_canada_french_statement(page(
            self.LEDGER + self.AFTER_THE_LEDGER, credits="1 40,00"
        ))
        assert amounts(stmt) == [40.0, -217.19]

    def test_in_ledger_furniture_is_not_a_row(self):
        """The page-tracking line and the `No. Montant` cheque legend are
        printed inside the grid and carry no DATE cell."""
        stmt = parse(self.LEDGER, credits="1 40,00")
        assert len(stmt.transactions) == 1


# ===========================================================================
# F5 — the per-page footers
# ===========================================================================

class TestF5PageFooters:
    def test_the_count_is_the_first_token_and_the_amount_is_the_rest(self):
        """`Debits 18 924,29` is eighteen rows totalling 924.29. Read the other
        way round it is one row totalling 18,924.29, and both are grammatical
        until you know which token is the count."""
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV 60,00
""", debits="18 924,29")
        assert stmt.stated_debit_count == 18
        assert stmt.stated_total_debits == 924.29

    def test_a_wide_count_and_a_wide_amount_stay_apart(self):
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV 60,00
""", credits="19 10 034,67")
        assert stmt.stated_credit_count == 19
        assert stmt.stated_total_credits == 10034.67

    def test_footers_accumulate_over_pages(self):
        document = page("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV 140,00
""", number=1, pages=2, credits="1 40,00", debits="0 0,00") + page("""
SOLDE REPORTE 01FEV 140,00
LIGNE SANS CODE DEUX 25,00 02FEV 115,00
""", number=2, pages=2, credits="0 0,00", debits="1 25,00")
        stmt = parse_td_canada_french_statement(document)
        assert (stmt.stated_credit_count, stmt.stated_total_credits) == (1, 40.0)
        assert (stmt.stated_debit_count, stmt.stated_total_debits) == (1, 25.0)

    def test_the_printed_average_balance_is_read_once_not_summed(self):
        """It is reprinted identically on every page; accumulating it would
        multiply the bank's figure by the page count."""
        document = page("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV 140,00
""", number=1, pages=2, credits="1 40,00") + page("""
SOLDE REPORTE 01FEV 140,00
LIGNE SANS CODE DEUX 25,00 02FEV 115,00
""", number=2, pages=2, debits="1 25,00")
        stmt = parse_td_canada_french_statement(document)
        assert stmt.stated_average_balance == 500.0

    def test_the_account_number_comes_from_the_page_head_not_a_ledger_row(self):
        """A row can name another of the customer's accounts. A bare
        branch-and-account regex over the document picks that up instead."""
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
SGE A: 3333-4444444 40,00 01FEV 60,00
""", debits="1 40,00")
        assert stmt.account_number == "1111-2222222"


# ===========================================================================
# F6 — day-first dates, and the year the bank does not print
# ===========================================================================

class TestF6Dates:
    def test_dates_are_day_first(self):
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
DEPOT MOBILE 40,00 05FEV 140,00
""", credits="1 40,00")
        assert stmt.transactions[0].date == "2026-02-05"

    def test_a_period_crossing_the_year_dates_each_row_in_its_own_year(self):
        stmt = parse("""
SOLDE REPORTE 31DEC 100,00
LIGNE SANS CODE UN 40,00 31DEC
LIGNE SANS CODE DEUX 25,00 15JAN 35,00
""", period="31 DEC 25 - 30 JAN 26", debits="2 65,00")
        assert [t.date for t in stmt.transactions] == ["2025-12-31", "2026-01-15"]
        assert (stmt.period_start, stmt.period_end) == ("2025-12-31", "2026-01-30")

    @pytest.mark.parametrize("token,iso", [
        ("05FEV", "2026-02-05"),
        ("05MAR", "2026-03-05"),
        ("05AVR", "2026-04-05"),
        ("05MAI", "2026-05-05"),
    ])
    def test_french_month_tokens_resolve(self, token, iso):
        stmt = parse(f"""
SOLDE REPORTE 31JAN 100,00
DEPOT MOBILE 40,00 {token} 140,00
""", period="31 JAN 26 - 31 MAI 26", credits="1 40,00")
        assert stmt.transactions[0].date == iso

    def test_a_document_without_a_printed_period_is_declined(self):
        """Rows cannot be dated, and a statement year is never assumed."""
        document = page("""
SOLDE REPORTE 31JAN 100,00
DEPOT MOBILE 40,00 01FEV 140,00
""").replace(PERIOD, "")
        assert parse_td_canada_french_statement(document) is None


# ===========================================================================
# F7 — TD's own French transaction codes, and only where nothing else decides
# ===========================================================================

class TestF7DirectionCodes:
    @pytest.mark.parametrize("description,is_credit", [
        ("DEP MC 11111111 DIV", True),
        ("DEPOT MOBILE", True),
        ("TP0130 11111111 DIV", True),
        ("Recept - VFC ***abc", True),
        ("Recept-VFC ***abc", True),
        ("LM503 TFR-DE 2222222", True),
        ("CREDIT D'INTERET", True),
        ("Envoi - VFC ***abc", False),
        ("Envoi - FRAIS - VFC", False),
        ("UO342 TFR-A 2222222", False),
        # Counterparty names are not codes, whichever way they usually fall.
        ("LOTO-QUEBEC DIV", False),
        ("MRCH22940680010 DIV", False),
        ("ELAVON MRCH SVC DIV", False),
        ("DEPANNEUR DU COIN", False),
        ("TPQ SERVICES", False),
    ])
    def test_the_code_vocabulary(self, description, is_credit):
        assert _french_credit_like(description) is is_credit

    def test_a_deposit_code_signs_a_row_the_balances_leave_open(self):
        stmt = parse(UNDETERMINED.format(row="DEP MC 11111111 DIV"),
                     credits="1 30,00", debits="2 30,00")
        assert amounts(stmt) == [30.0, -20.0, -10.0]
        assert reconcile(stmt).ok

    def test_a_terminal_posting_code_does_the_same(self):
        stmt = parse(UNDETERMINED.format(row="TP0130 11111111 DIV"),
                     credits="1 30,00", debits="2 30,00")
        assert amounts(stmt) == [30.0, -20.0, -10.0]

    def test_a_counterparty_name_is_not_a_code(self):
        """Same three-row shape, same amounts, same undetermined balances. Only
        the first description differs, and it is a merchant rather than one of
        TD's codes — over the corpus the printed balances make that name 53
        credits against 42 debits, so it is not evidence.

        It plays no part in the reading, and the reading is nevertheless the
        same as the coded one HERE, because the printed balance fixes the
        deposit subtotal at 30,00 either way and moving the single 30,00 row is
        the smallest change that reaches it. What the merchant name would have
        bought — a reason to prefer that row — is exactly what the arithmetic
        supplied without it. The two tests below are where a code and no code
        part company (W3 §WITHHELDTD)."""
        stmt = parse(UNDETERMINED.format(row="MRCH22940680010 DIV"),
                     credits="1 30,00", debits="2 30,00")
        assert _french_direction_code("MRCH22940680010 DIV") is None
        assert amounts(stmt) == [30.0, -20.0, -10.0]
        assert reconcile(stmt).ok

    def test_a_withdrawal_code_moves_the_deposit_off_that_row(self):
        """`ENVOI` is TD's own outgoing-transfer code, so the 30,00 row is not
        the deposit and the other two must be: a code the bank PRINTED outranks
        the smallest-change reading, and only the three-valued reader can tell
        it from a row TD says nothing about."""
        stmt = parse(UNDETERMINED.format(row="Envoi - VFC ***abc"),
                     credits="2 30,00", debits="1 30,00")
        assert _french_direction_code("Envoi - VFC ***abc") is False
        assert amounts(stmt) == [-30.0, 20.0, 10.0]
        assert reconcile(stmt).ok

    def test_the_french_codes_break_the_equal_amount_tie_not_the_english_ones(self):
        """Two rows of the same amount in one group, one of them carrying TD's
        French deposit code: the arithmetic says one of the two is the deposit
        and cannot say which, so the code does — and the code table consulted
        has to be the FRENCH one. It was the English table until W3
        §WITHHELDTD, on which `DEP MC ...` matches nothing, and the tie fell to
        document order."""
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
LIGNE SANS CODE UN 40,00 01FEV
DEP MC 11111111 DIV 40,00 01FEV 100,00
""", credits="1 40,00", debits="1 40,00")
        assert amounts(stmt) == [-40.0, 40.0]

    def test_the_printed_balance_outranks_a_credit_code(self):
        """`DEP` is TD's own deposit code and the balances say this row was a
        withdrawal. The arithmetic wins; the codes never override a document."""
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
DEP MC 11111111 DIV 40,00 01FEV
LIGNE SANS CODE UN 10,00 01FEV 50,00
""", debits="2 50,00")
        assert amounts(stmt) == [-40.0, -10.0]
        assert reconcile(stmt).ok


# ===========================================================================
# End to end
# ===========================================================================

class TestEndToEnd:
    DOCUMENT = """
SOLDE REPORTE 31JAN 100,00
DEPOT MOBILE 40,00 01FEV
LIGNE SANS CODE UN 25,00 01FEV 115,00
LM503 TFR-DE 2222222 60,00 02FEV
FRAIS MENSUELS 15,00 02FEV 160,00
"""

    def test_the_pipeline_routes_the_document_to_this_parser(self):
        report = analyze_markdown(
            page(self.DOCUMENT, credits="2 100,00", debits="2 40,00")
        )
        assert report.model_used == "td-canada-trust-deterministic"
        assert report.reconciliation.ok

    def test_the_statement_carries_the_bank_and_currency(self):
        stmt = parse(self.DOCUMENT, credits="2 100,00", debits="2 40,00")
        assert (stmt.bank, stmt.currency) == ("TD Canada Trust", "CAD")
        assert amounts(stmt) == [40.0, -25.0, 60.0, -15.0]

    def test_a_header_with_no_ledger_is_not_a_statement(self):
        assert parse_td_canada_french_statement(page("")) is None

    def test_descriptions_keep_the_case_and_the_accents_the_bank_printed(self):
        stmt = parse("""
SOLDE REPORTE 31JAN 100,00
Recept - VFC ***abc 40,00 01FEV 140,00
""", credits="1 40,00")
        assert stmt.transactions[0].description == "Recept - VFC ***abc"
