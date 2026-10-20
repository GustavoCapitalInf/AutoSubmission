"""The French `Relevé de compte` template, registered without an issuer.

W3 §UNKISSUER, card 2 (from §UNID-B UB5). Every fixture below is synthetic:
invented account numbers, invented amounts, invented counterparties. What is
pinned is the TEMPLATE's grammar and the four printed figures it is checked
against — the only things this registration is allowed to know.
"""
from __future__ import annotations

import pytest

import analysis.parser_registry_entries  # noqa: F401  (populates the registry)
from analysis.parser_registry import by_id
from analysis.reconcile import reconcile
from analysis.releve_facturation import (
    detect,
    parse_releve_facturation_statement as parse,
)

FOOTER = (
    "Veuillez vérifier ce relevé sans délai. La Banque doit être avisée par "
    "écrit de toute erreur ou omission dans les quarante-cinq (45) jours."
)
GRID = "MM JJ DESCRIPTION DÉBIT ($) CRÉDIT ($) SOLDE ($)"


def document(
    ledger: str,
    *,
    debit_count: int = 1,
    debit_total: str = "2 000,00",
    credit_count: int = 2,
    credit_total: str = "1 000,00",
    period: str = "Période du 01-04-2054 au 30-04-2054",
    product: str = "COMPTE : COMPTE COURANT CANADIEN",
    account: str = "No de compte 00-000-00 No succursale 00000",
    pages: int = 1,
) -> str:
    """One synthetic statement of this template."""
    return "\n".join(
        part for part in (
            "Relevé de compte",
            "1 RUE EXEMPLE VILLE J0J 0J0 (000) 000-0000",
            f"{period} Page 1 de {pages}",
            account,
            "EXEMPLE INC 2 RUE EXEMPLE VILLE QC J0J 0J0",
            product,
            "FORFAIT : FORFAIT EXEMPLE",
            GRID,
            ledger,
            "FACTURATION DÉTAILLÉE TRANSACTIONS/VOLUME(S) TARIF UNIT./TAUX FRAIS",
            "*FACTURATION MENSUELLE",
            "FORFAIT 0,00",
            "TOTAL 0,00",
            "NOMBRE MONTANT TOTAL NOMBRE MONTANT TOTAL",
            f"TRANSACTIONS DÉBIT {debit_count} {debit_total} "
            f"CRÉDIT {credit_count} {credit_total}",
            FOOTER,
        ) if part
    ) + "\n"


#: Opening 1 000,00; +250,00 -> 1 250,00; -2 000,00 -> -750,00 (the detached
#: minus); +750,00 -> 0,00. Two credits totalling 1 000,00, one debit of
#: 2 000,00 — which is what the fee table above prints.
LEDGER = (
    "03 31 SOLDE PRECEDENT 1 000,00 "
    "04 01 COMPTE DIVERS EXEMPLE 250,00 1 250,00 "
    "04 02 DPA ENTREPRISE EXEMPLE 2 000,00 - 750,00 "
    "04 03 G/DEPOT 00000000000 750,00 0,00"
)


# ===========================================================================
# 1. The whole point: read the template, name no bank
# ===========================================================================

def test_the_template_is_read_and_no_bank_is_named():
    stmt = parse(document(LEDGER))
    assert stmt is not None
    assert stmt.bank is None
    assert stmt.account_name == "COMPTE COURANT CANADIEN"
    assert stmt.account_number == "00-000-00"
    assert stmt.period_start == "2054-04-01"
    assert stmt.period_end == "2054-04-30"
    assert stmt.beginning_balance == 1000.0
    assert stmt.ending_balance == 0.0
    assert [t.amount for t in stmt.transactions] == [250.0, -2000.0, 750.0]
    assert [t.direction for t in stmt.transactions] == ["credit", "debit", "credit"]
    assert [t.running_balance for t in stmt.transactions] == [1250.0, -750.0, 0.0]
    assert reconcile(stmt).ok


def test_the_opening_bookend_is_not_published_as_a_transaction():
    """`SOLDE PRECEDENT` is last period's closing balance, dated the last day
    of it. It anchors the chain and is not a posting."""
    stmt = parse(document(LEDGER))
    assert all("SOLDE PRECEDENT" not in t.description for t in stmt.transactions)
    assert all(t.date >= "2054-04-01" for t in stmt.transactions)


@pytest.mark.parametrize(
    "counterparty",
    [
        "COMPTE DIVERS FED DESJARDINS",
        "PRET RBC LOAN PYMT",
        "PRET PMT PRET TD",
        "VIREMENT BANQUE NATIONALE",
    ],
)
def test_an_institution_named_in_a_ledger_row_does_not_become_the_bank(counterparty):
    """Every institution word in the 16 archive documents is one of these: a
    payment the CUSTOMER made. Six of the sixteen really do print
    `FED DESJARDINS`, and the folder label on six of them really does say
    Desjardins — they are not the same six. A counterparty is not an issuer.
    """
    stmt = parse(document(LEDGER.replace("COMPTE DIVERS EXEMPLE", counterparty)))
    assert stmt is not None
    assert stmt.bank is None


def test_the_boilerplate_that_calls_the_issuer_the_bank_names_no_bank():
    """Every page ends `La Banque doit être avisée...`. That is the whole of
    what this template says about who issued it, and it is not a name."""
    assert "La Banque" in document(LEDGER)
    assert parse(document(LEDGER)).bank is None


# ===========================================================================
# 2. The money grammar
# ===========================================================================

def test_a_reference_numbers_tail_is_not_a_thousands_group():
    """The defect that made 10 of the 16 look chain-broken.

    `TRF DT INTERNET D77100000001337 150,00 3 983,75` offers `...1337 150,00`
    to a pattern with no left digit boundary, which reads a $337,150.00 debit
    out of a document number. The row below is the same shape: the amount is
    250,00 and the digits before it belong to the reference.
    """
    ledger = LEDGER.replace(
        "COMPTE DIVERS EXEMPLE 250,00",
        "TRF DT INTERNET D77100000001337 250,00",
    )
    stmt = parse(document(ledger))
    assert stmt is not None
    assert stmt.transactions[0].amount == 250.0
    assert stmt.transactions[0].description == "TRF DT INTERNET D77100000001337"


def test_the_money_token_cannot_begin_inside_a_digit_run():
    """The left boundary, pinned AT THE PATTERN rather than by its effect.

    This guard is defence-in-depth, not load-bearing for any archive document:
    with `_amount_from_chain` in place the printed balance recovers the right
    figure even when the token is misread, and all 16 documents parse either
    way. That is exactly why it needs its own test — a guard whose removal
    changes no outcome is a guard nothing else will notice being deleted, and
    what it prevents (reading `...D77100000001337 150,00` as `337 150,00`) is
    a wrong figure reaching the resolver in the first place.
    """
    import re as _re

    from analysis.releve_facturation import _MONEY

    pattern = _re.compile(_MONEY)
    assert [m.group() for m in pattern.finditer("D77100000001337 150,00")] == ["150,00"]
    assert [m.group() for m in pattern.finditer("00105958482 224,65")] == ["224,65"]
    # and it still reads a genuine space-thousands figure whole
    assert [m.group() for m in pattern.finditer("SOLDE 4 113,92")] == ["4 113,92"]


def test_a_detached_minus_signs_the_balance_and_not_the_amount():
    """An overdrawn balance prints its sign as its own token. The two money
    columns are magnitudes; the direction is the column, read off the chain."""
    stmt = parse(document(LEDGER))
    overdrawn = stmt.transactions[1]
    assert overdrawn.amount == -2000.0
    assert overdrawn.running_balance == -750.0


def test_a_hyphen_ending_a_description_is_not_a_sign():
    """`ESSO COUCHE -TA 100,00` is a real archive description. The hyphen
    belongs to the merchant's name."""
    ledger = LEDGER.replace(
        "COMPTE DIVERS EXEMPLE 250,00",
        "C/ACHAT 00000000000 ESSO COUCHE -TA 250,00",
    )
    stmt = parse(document(ledger))
    assert stmt is not None
    assert stmt.transactions[0].amount == 250.0


# ===========================================================================
# 3. The `MM JJ` / space-thousands collision
# ===========================================================================

def test_a_date_pair_is_not_read_out_of_the_seam_between_two_figures():
    """`... 640,00 20 490,64 04 10 DPA ...` contains `00 20`, a well-formed
    `MM JJ` pair lying across an amount and the balance beside it. Anchoring
    the row start on a FOLLOWING CAPITAL separates them: a real date pair is
    followed by the description's first word, a false one by more digits.
    """
    ledger = (
        "03 31 SOLDE PRECEDENT 19 850,64 "
        "04 01 COMPTE DIVERS EXEMPLE 640,00 20 490,64 "
        "04 02 DPA ENTREPRISE EXEMPLE 20 490,64 0,00"
    )
    assert "00 20" in ledger, "the collision must be present for this to test it"
    stmt = parse(document(
        ledger, credit_count=1, credit_total="640,00",
        debit_count=1, debit_total="20 490,64",
    ))
    assert stmt is not None
    assert len(stmt.transactions) == 2
    assert [t.amount for t in stmt.transactions] == [640.0, -20490.64]


def test_a_row_start_inside_a_digit_run_is_rejected():
    """The left boundary: a pair that begins mid-number is not a date."""
    from analysis.releve_facturation import _ROW_RE

    assert not _ROW_RE.search("1234 56 ABC")
    assert _ROW_RE.search("04 06 COMPTE")


# ===========================================================================
# 4. The split ambiguity, resolved by the printed balance
# ===========================================================================

def test_a_store_number_before_an_amount_is_resolved_by_the_chain():
    """`C/ACHAT 00105958482 PETRO-CANADA 13 100,00` is a $13,100.00 purchase
    if `13` is a thousands group and a $100.00 purchase at store 13 if it is
    part of the merchant's name. Both are well-formed French money. The bank's
    own printed balance is what decides, and here it says $100.00 — so the
    `13` goes back to the description where it belongs.
    """
    ledger = (
        "03 31 SOLDE PRECEDENT 1 000,00 "
        "04 01 C/ACHAT 00000000000 PETRO-CANADA 13 100,00 900,00 "
        "04 02 G/DEPOT 00000000000 100,00 1 000,00"
    )
    stmt = parse(document(
        ledger, debit_count=1, debit_total="100,00",
        credit_count=1, credit_total="100,00",
    ))
    assert stmt is not None
    assert stmt.transactions[0].amount == -100.0
    assert stmt.transactions[0].description == "C/ACHAT 00000000000 PETRO-CANADA 13"


def test_the_same_token_is_read_as_thousands_when_the_chain_says_so():
    """The control. The reading is not a preference for the short one — the
    identical token is read as 13 100,00 when the printed balance moved by
    that much."""
    ledger = (
        "03 31 SOLDE PRECEDENT 20 000,00 "
        "04 01 C/ACHAT 00000000000 PETRO-CANADA 13 100,00 6 900,00 "
        "04 02 G/DEPOT 00000000000 100,00 7 000,00"
    )
    stmt = parse(document(
        ledger, debit_count=1, debit_total="13 100,00",
        credit_count=1, credit_total="100,00",
    ))
    assert stmt is not None
    assert stmt.transactions[0].amount == -13100.0
    assert stmt.transactions[0].description == "C/ACHAT 00000000000 PETRO-CANADA"


def test_a_leading_zero_group_is_one_number_and_not_an_ambiguity():
    """The invariant this reader used to assert and did not have.

    `_amount_from_chain` claimed its candidate readings were necessarily
    distinct numbers, so at most one could ever fit. A group of zeroes breaks
    that: `000 100,00` reads as 100.00 whether the leading group is thousands
    or description, two candidates fit the same movement, and `!= 1` refused a
    row whose amount was never ambiguous. Deduplicating by VALUE is the fix -
    same number, no ambiguity about the money.
    """
    ledger = (
        "03 31 SOLDE PRECEDENT 1 000,00 "
        "04 01 COMPTE DIVERS EXEMPLE 000 100,00 1 100,00 "
        "04 02 DPA ENTREPRISE EXEMPLE 100,00 1 000,00"
    )
    stmt = parse(document(
        ledger, credit_count=1, credit_total="100,00",
        debit_count=1, debit_total="100,00",
    ))
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [100.0, -100.0]
    # The whole money cell is the amount, so none of it is left in the text.
    assert stmt.transactions[0].description == "COMPTE DIVERS EXEMPLE"


def test_a_genuine_ambiguity_still_needs_the_balance_to_pick_one():
    """The control for the dedupe: two readings that are DIFFERENT numbers are
    still a real ambiguity, and are still resolved by the printed balance
    rather than by preferring either end."""
    from analysis.releve_facturation import _amount_from_chain

    assert _amount_from_chain("000 100,00", 100.0) == (100.0, 0)
    assert _amount_from_chain("13 100,00", 100.0) == (100.0, 3)
    assert _amount_from_chain("13 100,00", 13100.0) == (13100.0, 0)
    assert _amount_from_chain("13 100,00", 999.0) is None


def test_a_zero_movement_row_reads_as_a_credit_and_refuses_when_the_bank_counted_a_debit():
    """D2, pinned in BOTH fee-table directions.

    A zero-amount row moves no balance, so it has no movement direction, and
    the printed COLUMN that would settle it does not survive flattening. This
    reader breaks the tie as a credit. Where the bank counted such a row on
    the credit side the document publishes; where it counted a debit, both
    printed counts disagree and the document is REFUSED. Fail-closed, and the
    refusal is the point - it is not silently republished on the wrong side.
    """
    ledger = (
        "03 31 SOLDE PRECEDENT 1 000,00 "
        "04 01 COMPTE DIVERS EXEMPLE 0,00 1 000,00 "
        "04 02 DPA ENTREPRISE EXEMPLE 250,00 750,00"
    )
    counted_as_credit = parse(document(
        ledger, credit_count=1, credit_total="0,00",
        debit_count=1, debit_total="250,00",
    ))
    assert counted_as_credit is not None
    assert [t.direction for t in counted_as_credit.transactions] == ["credit", "debit"]
    assert counted_as_credit.transactions[0].amount == 0.0

    counted_as_debit = parse(document(
        ledger, credit_count=0, credit_total="0,00",
        debit_count=2, debit_total="250,00",
    ))
    assert counted_as_debit is None


def test_a_row_no_reading_of_which_fits_the_chain_refuses_the_document():
    """The ambiguity is resolved by the document or not at all. Where the
    balance demands a figure the printed amount cannot spell, the row has been
    misread and there is no honest partial answer."""
    ledger = (
        "03 31 SOLDE PRECEDENT 1 000,00 "
        "04 01 COMPTE DIVERS EXEMPLE 250,00 1 300,00"
    )
    assert parse(document(ledger, credit_count=1, credit_total="250,00",
                          debit_count=0, debit_total="0,00")) is None


# ===========================================================================
# 5. The fee table: terminator and oracle
# ===========================================================================

def test_a_facturation_row_inside_the_ledger_does_not_end_it():
    """`FACTURATION MENSUELLE` and `COMPTE A PAYER FACTURATION EDI` are
    transaction descriptions on these documents. Only the two-word
    `FACTURATION DÉTAILLÉE` is the fee table, which is why the terminator is
    matched as two words and not one."""
    ledger = LEDGER.replace(
        "G/DEPOT 00000000000 750,00", "FACTURATION MENSUELLE 750,00"
    )
    stmt = parse(document(ledger))
    assert stmt is not None
    assert len(stmt.transactions) == 3
    assert stmt.transactions[2].description == "FACTURATION MENSUELLE"


@pytest.mark.parametrize(
    "field, wrong",
    [
        ("debit_count", {"debit_count": 2}),
        ("debit_total", {"debit_total": "2 001,00"}),
        ("credit_count", {"credit_count": 3}),
        ("credit_total", {"credit_total": "1 001,00"}),
    ],
)
def test_every_one_of_the_four_printed_figures_is_load_bearing(field, wrong):
    """The fee table prints a count AND a total for each direction. All four
    are checked, so three-out-of-four is a refusal: a count check cannot see a
    misread amount and a total check cannot see a dropped zero-value row."""
    assert parse(document(LEDGER)) is not None, "the control must pass"
    assert parse(document(LEDGER, **wrong)) is None, f"{field} is not checked"


# ===========================================================================
# 6. Fail-closed on everything the document does not supply
# ===========================================================================

@pytest.mark.parametrize(
    "missing",
    [
        {"period": ""},
        {"account": ""},
        {"product": ""},
    ],
)
def test_a_document_missing_its_header_furniture_is_declined(missing):
    assert parse(document(LEDGER, **missing)) is None


def test_a_ledger_that_does_not_open_on_the_previous_balance_is_declined():
    """Without the opening bookend there is nothing to chain the first row
    against, and a chain that starts at an assumed figure is not a check."""
    ledger = LEDGER.replace("03 31 SOLDE PRECEDENT 1 000,00 ", "")
    assert parse(document(ledger)) is None


def test_a_row_dated_outside_the_period_is_declined():
    """A `MM JJ` pair carries no year; the period's months are what supply
    one. A month that is neither of them is a row this reader cannot date."""
    ledger = LEDGER.replace("04 03 G/DEPOT", "09 03 G/DEPOT")
    assert parse(document(ledger)) is None


def test_the_currency_is_the_one_the_product_line_prints():
    """`COMPTE COURANT CANADIEN` is the document's own name for the account
    and the only currency evidence on the page — the column headers print a
    bare `($)`. A product line this reader cannot read is a refusal, not a
    guess at the default."""
    assert parse(document(LEDGER)).currency == "CAD"
    assert parse(document(LEDGER, product="COMPTE : COMPTE COURANT AMERICAIN")) is None


# ===========================================================================
# 7. Detection
# ===========================================================================

def test_detection_needs_all_three_pieces_of_furniture():
    md = document(LEDGER)
    assert detect(md).claims
    for furniture in (GRID, "FACTURATION DÉTAILLÉE", "TRANSACTIONS DÉBIT"):
        assert not detect(md.replace(furniture, "XXXX")).claims, furniture


def test_accents_are_folded_so_an_unaccented_extraction_still_detects():
    """The same document extracted without accents is the same document."""
    md = document(LEDGER)
    stripped = (md.replace("É", "E").replace("é", "e")
                  .replace("È", "E").replace("è", "e"))
    assert detect(stripped).claims
    assert parse(stripped) is not None


@pytest.mark.parametrize(
    "text",
    [
        "PLAIN ASCII STATEMENT\n1,234.56\n",
        "Relevé de compte\nFACTURATION DÉTAILLÉE\n",
        "MIXED é and ascii\n",
        "",
        "a−b c",  # a minus glyph and an NBSP, both normalized first
    ],
)
def test_the_ascii_fast_path_is_the_same_fold(text):
    """`_fold` short-circuits on ASCII to keep the registry sweep affordable.

    That is only allowed because it is the SAME answer: NFKD is the identity
    on ASCII and no ASCII character combines. The check runs after the sign
    and mojibake normalizations, which are what could introduce a non-ASCII
    character in the first place.
    """
    import unicodedata

    from analysis.money import normalize_sign_glyphs
    from analysis.releve_facturation import _fold
    from analysis.td_can import normalize_mojibake

    repaired = normalize_sign_glyphs(normalize_mojibake(text))
    decomposed = unicodedata.normalize("NFKD", repaired)
    general = "".join(c for c in decomposed if not unicodedata.combining(c)).upper()
    assert _fold(text) == general


def test_the_registration_publishes_no_bank_and_its_label_names_the_template():
    """`Registration.bank` is our constant and must name the template;
    `Statement.bank` is what we publish about the document and must be None.
    The label carries no institution word and no folder-label substring —
    `discovery.evidence` matches it against folder names by containment."""
    registration = by_id("releve_facturation")
    assert registration.bank == "Releve de Compte Statement Template"
    assert registration.parse(document(LEDGER)).bank is None
