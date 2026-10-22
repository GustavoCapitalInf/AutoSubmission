"""The package reads "one account" four ways, and each reading is its own policy: the months' floor (`months_linked`),
the passes' same account (`same_account`), the passes' two accounts (`different_accounts`) and the shorter-printout
pass (`_pair_kind`). These packages pin where the readings part, through what the package publishes: a full-number
conflict, a statement that prints no bank, two accounts of one document, an informal printout's bank label, and an
R-d row the passes leave out of the package but not out of the correction guard. Fabricated CONTOSO BANK statements of
CONTOSO BAKERY LLC, 2031."""
from __future__ import annotations

from analysis.pipeline import analyze_statement, DocumentReport, identify_internal_transfers
from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction
from analysis.serialization import document_report_to_dict
from tests import test_package_matching as matching
from tests.test_webapp_true_revenue import _package, _period_payload

#: The three numbers of the full-number contrast: one last four, two printed full numbers that conflict, and another
#: last four.
NUMBER, CONFLICTING, OTHER = "000000001010", "100000001010", "000000002020"


def _months(*payloads) -> int:
    return _package(*payloads)["totals"]["months"]


def _february(number=NUMBER, bank="CONTOSO BANK"):
    """02-16 to 03-15, opening on 1,500.00 and closing on 11,500.00: a statement of March by its month rule."""
    return _period_payload("2031-02-16", "2031-03-15", number=number, bank=bank)


def _march(number=NUMBER, bank="CONTOSO BANK", opening=11500.0):
    """03-16 to 04-15, a statement of March too: two statements of one account read 2 months (59 days), two
    accounts 1."""
    return _period_payload("2031-03-16", "2031-04-15", number=number, bank=bank, opening=opening)


def _returned(*, april_number=NUMBER, banks=None):
    """S1, the owner's example: does pass 1 match April's returned deposit to March's deposit? `banks` sets the bank
    each statement prints, (March, April)."""
    march, april = matching._owners_example(april_number=april_number)
    if banks is not None:
        march["statement"]["bank"], april["statement"]["bank"] = banks
    package = matching._package(("mar", march), ("apr", april))
    return "package_matches" in package


def _transfer_held(number):
    """Does pass 2 hold B's deposit as the transfer A sent, B printing `number`? The transfer out names no
    destination, so only the two accounts' numbers decide."""
    package = matching._package(("a", matching._account_a(debit="ONLINE BANKING TRANSFER CONF 5521")),
                                ("b", matching._account_b(number=number)))
    return matching._tier(package, "b", "transaction:1") == matching.HELD


def _document(*reports, period, roster=()):
    accounts = [report.accounts[0] for report in reports]
    transfers, notes = identify_internal_transfers(accounts)
    return document_report_to_dict(DocumentReport(accounts=accounts, internal_transfers=transfers,
                                                  integrity_notes=notes, account_roster=list(roster),
                                                  document_period=period))


def _cycle_report(start, end, opening):
    balance = round(opening + 10000.0, 2)
    statement = Statement(bank="CONTOSO BANK", account_name="CONTOSO BAKERY LLC", account_number=NUMBER,
                          period_start=start, period_end=end, beginning_balance=opening, ending_balance=balance,
                          currency="USD", currency_source="printed",
                          transactions=[Transaction(date=start, description="FABRIKAM INC DES:ACH PAYMENT ID:1",
                                                    amount=10000.0, direction="credit", running_balance=balance)])
    return analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                             model_used="fabricated-test")


def test_months_join_two_statements_whose_full_numbers_conflict_and_the_passes_never_do():
    assert _months(_february(), _march(CONFLICTING)) == 2
    assert _months(_february(), _march(OTHER)) == 1
    assert _returned() and not _returned(april_number=CONFLICTING)
    assert _transfer_held(CONFLICTING) and _transfer_held(OTHER) and not _transfer_held("1010")


def test_a_statement_printing_no_bank_joins_the_months_by_its_balance_chain_and_never_the_passes():
    assert _months(_february(), _march(OTHER, bank="")) == 2
    assert _months(_february(), _march(OTHER, bank="", opening=9000.0)) == 1
    assert _months(_february(), _march(OTHER)) == 1
    assert not _returned(banks=("Sample Bank", None)) and not _returned(banks=(None, None))


def test_two_accounts_of_one_document_are_never_one_account():
    january, february = (_cycle_report("2031-02-16", "2031-03-15", 1500.0),
                         _cycle_report("2031-03-16", "2031-04-15", 11500.0))
    document = _document(january, february, period=("2031-02-16", "2031-04-15"))
    assert _months(document) == 1
    assert _months(document_report_to_dict(january), document_report_to_dict(february)) == 2
    march = matching._report(matching.MARCH, month=3, opening=1500.0)
    april = matching._report(matching.APRIL, month=4, opening=matching._closing(matching.MARCH, 1500.0))
    one = matching._package(("doc", _document(march, april, period=("2031-03-01", "2031-04-28"))))
    two = matching._package(("mar", document_report_to_dict(march)), ("apr", document_report_to_dict(april)))
    assert "package_matches" not in one and one["totals"]["unmatched_deposit_return_count"] == 1
    assert "package_matches" in two


def test_the_months_read_an_informal_export_s_label_as_its_bank_and_the_passes_read_it_as_printed():
    assert _months(_february(bank="Chase"), _march(bank="Chase Transaction Export", opening=9000.0)) == 2
    assert _months(_february(bank="Chase"), _march(bank="Fabrikam Bank", opening=9000.0)) == 1
    assert not _returned(banks=("Chase", "Chase Transaction Export"))
    assert _returned(banks=("Chase", "  CHASE "))


def test_a_correction_naming_an_r_d_credit_is_never_netted_across():
    """Pass 1's correction guard reads every row the member's statement printed, its R-d rows included: a correction
    naming the R-d transfer credit stays flagged though the package leaves that credit out, and February's equal
    deposit stays counted. A correction naming no credit of its statement takes February's deposit."""
    def package(correction):
        first = matching._report([(2, "ONLINE TRANSFER FROM CHK 2020", 700.0), (6, correction, -700.0),
                                  (9, matching.NW_A, 2000.0)], month=3, opening=50000.0)
        second = matching._report([(2, "ONLINE TRANSFER TO CHK 1010", -700.0), (9, matching.FABRIKAM_B, 2000.0)],
                                  month=3, opening=1500.0, number=matching.ACCOUNT_B)
        document = _document(first, second, period=("2031-03-01", "2031-03-28"))
        assert len(document["document"]["internal_transfers"]) == 1
        february = matching._payload([(20, "DEPOSIT", 700.0)], month=2, opening=1500.0)
        return matching._package(("feb", february), ("doc", document))

    guarded = package("DEPOSIT CORRECTION ONLINE TRANSFER")
    assert "package_matches" not in guarded and guarded["totals"]["true_revenue_total"] == 4700.0
    assert [(flag["kind"], flag["source_job"], flag["source_location"]) for flag in guarded["debit_flags"]] == [
        ("unmatched_deposit_return", "doc", "transaction:2")]
    netted = package("DEPOSIT CORRECTION FABRIKAM")
    assert [(match["kind"], match["credit"]["job"], match["debit"]["source_location"])
            for match in netted["package_matches"]] == [("returned_deposit", "feb", "transaction:2")]
    assert netted["totals"]["true_revenue_total"] == 4000.0
