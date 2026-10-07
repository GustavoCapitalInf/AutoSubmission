"""Unit tests for the deterministic analysis stages (no network / no LLM).
These lock in the math and detection logic — the parts that must be exactly right."""
from __future__ import annotations
import csv
from datetime import date
from functools import lru_cache
from pathlib import Path
import pytest
from analysis.schema import Statement, Transaction
from analysis.adb import compute_average_daily_balance
from analysis.reconcile import reconcile
from analysis.metrics import compute_metrics, daily_closing_balances
from analysis.detect import detect, find_known_funders, find_recurring_debits
from analysis.transaction_classifier import classify_statement_transactions
from analysis.extract import strip_embedded_images
from analysis.altana import parse_altana_statement
from analysis.atb import parse_atb_statement
from analysis.b1 import parse_b1_statement
from analysis.banco_popular import parse_banco_popular_statement
from analysis.bmo import parse_bmo_statement
from analysis.bluevine import parse_bluevine_statement
from analysis.cibc import parse_cibc_french_statement
from analysis.community_section import parse_dakota_west_statement, parse_mission_valley_statement
from analysis.consumers import parse_consumers_statement
from analysis.demo_national import parse_demo_national_statement
from analysis.desjardins import parse_desjardins_statement
from analysis.ibc import parse_ibc_statement
from analysis.linkbank import parse_linkbank_statement
from analysis.midflorida import parse_midflorida_statement
from analysis.navy_federal import parse_navy_federal_statement
from analysis.pipeline import (
    HOSTED_EXTRACTION_OPT_IN_ENV,
    HOSTED_EXTRACTION_OPT_IN_LITERAL,
    analyze_markdown,
    apply_statement_repairs,
    assess_document_integrity,
    normalize_statement,
    Quality,
)
from analysis.td_can import parse_td_canada_statement
from analysis.td_us import parse_td_us_statement
from analysis.texas_bank import parse_texas_bank_statement
from analysis.truist import parse_truist_statement
from analysis.us_bank import parse_us_bank_statement
from analysis.bofa import parse_bofa_statement, repair_bofa_summary
from analysis.capital_one import parse_capital_one_statement
from analysis.chase import parse_chase_statement
from analysis.first_community import parse_first_community_statement, repair_first_community_posted_activity
from analysis.first_citizens import parse_first_citizens_statement
from analysis.pnc import parse_pnc_statement
from analysis.rbc import parse_rbc_statement
from analysis.money import MINUS_GLYPHS
from analysis.regions import _money as regions_money
from analysis.regions import parse_regions_statement, repair_regions_summary
from analysis.santander import parse_santander_statement
from analysis.scanned_small_bank import _section, parse_apex_scanned_statement
from analysis.secu import parse_secu_statement
from analysis.wilson_muir import parse_wilson_muir_statement
from ocr.document import StatementMarkdown
from ocr.native_text import (
    parse_native_desjardins,
    parse_native_navy_federal,
    parse_native_pdf_text,
)


@lru_cache(maxsize=1)
def _pinned_corpus_pdfs() -> dict[str, list[Path]]:
    """Pinned corpus PDFs by file stem, from the committed balance audit.

    Resolution is against the pinned manifest rather than an rglob of
    `Bank Statements/`: that root is shared with untracked discovery material,
    whose stems collide with corpus stems, so an rglob would either pick a
    foreign document or trip the uniqueness assertion below. The manifest is the
    same 109 paths the corpus gate audits.
    """
    manifest = Path("docs/balance-metrics-audit-results.csv")
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_stem: dict[str, list[Path]] = {}
    for row in rows:
        path = Path("Bank Statements", row["path"])
        by_stem.setdefault(path.stem, []).append(path)
    return by_stem


def _artifact_markdown(filename: str) -> str:
    artifact = Path("output/new_bank_statements_artifacts", filename)
    if artifact.exists():
        return artifact.read_text(encoding="utf-8")

    statement_stem = Path(filename[4:]).stem
    matches = _pinned_corpus_pdfs().get(statement_stem, [])
    assert len(matches) == 1, f"expected one source PDF for missing artifact {filename}"
    source = matches[0]
    document = parse_native_pdf_text(source.read_bytes(), source_file=source.name)
    assert document is not None, f"no native text in source PDF for {filename}"
    return document.to_markdown()


def _raw_pdf_report(relative_path: str):
    source = Path("Bank Statements", relative_path)
    document = parse_native_pdf_text(source.read_bytes(), source_file=source.name)
    assert document is not None
    markdown = document.to_markdown()
    return markdown, analyze_markdown(markdown, parse_mode="deterministic")


def _assert_withheld_adb_is_not_public(report, filename: str) -> None:
    import io
    import zipfile

    from analysis.serialization import report_to_dict
    from webapp.app import _analysis_csv, _analysis_rows, _analysis_xlsx, _package_analysis
    from webapp.jobs import Job

    payload = report_to_dict(report)
    metrics = payload["metrics"]
    assert metrics["adb_ok"] is False
    assert metrics["average_daily_balance"] is None
    assert metrics["daily_balance_sum"] is None
    assert "average_balance" not in metrics
    assert "average_balance_source" not in metrics
    assert "average_daily_balance" not in metrics["adb"]
    assert metrics["adb"]["ok"] is False
    assert metrics["adb"]["daily_balance_sum"] is None
    assert metrics["adb"]["daily_balances"] == []
    assert metrics["min_balance"] is None
    assert metrics["max_balance"] is None

    rows = _analysis_rows(payload)
    assert not any(section == "adb_daily_balance" for section, _, _ in rows)
    assert not any(
        section == "adb" and field in {"average_daily_balance", "daily_balance_sum"}
        for section, field, _ in rows
    )
    csv_export = _analysis_csv(payload)
    assert "adb_daily_balance" not in csv_export
    assert "adb,average_daily_balance" not in csv_export

    workbook = _analysis_xlsx(payload)
    with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "adb_daily_balance" not in sheet
    assert "adb,average_daily_balance" not in sheet

    package = _package_analysis([
        Job(id=f"withheld-{filename}", filename=filename, status="done", analysis=payload)
    ])
    assert package["documents"][0]["average_daily_balance"] is None
    assert package["documents"][0]["adb_validated"] is False
    assert package["documents"][0]["min_balance"] is None
    assert package["documents"][0]["max_balance"] is None
    assert package["documents"][0]["daily_balance_extrema_validated"] is False
    assert package["totals"]["average_daily_balance"] is None


def test_strip_embedded_images_removes_base64_bloat():
    md = ('Deposits\n<img class="doc-image" src="data:image/png;base64,QUJDRA==" alt="image" />\n'
          '<table><tr><td>04/01</td><td>ACH</td><td>100.00</td></tr></table>')
    out = strip_embedded_images(md)
    assert "base64" not in out and "<img" not in out
    assert "Deposits" in out and "100.00" in out  # text ledger preserved


def test_normalize_statement_drops_daily_balance_summary_rows():
    stmt = Statement(transactions=[
        _txn("2054-04-30", -10.0, "MAINTENANCE FEE"),
        _txn("2054-04-30", 0.0, "DAILY BALANCE", bal=35121.16),
        _txn("2054-04-29", 0.0, "DAILY BALANCE SUMMARY", bal=36361.22),
    ])
    cleaned = normalize_statement(stmt)
    assert [t.description for t in cleaned.transactions] == ["MAINTENANCE FEE"]


def test_parse_td_canada_table_handles_fused_and_shifted_rows():
    md = """
Accounts issued by: THE TORONTO-DOMINION BANK
<table>
<tr><td>Branch No.</td><td>Account No.</td><td>BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY A</td><td>SEP 29/53 - OCT 31/53</td></tr>
<tr><td>2023</td><td>2023-5224784</td><td>EVERY DAY A</td><td>Page 1 of 2</td></tr>
<tr><td>DESCRIPTION</td><td>CHEQUE/DEBIT</td><td>DEPOSIT/CREDIT</td><td>DATE</td><td>BALANCE</td></tr>
<tr><td>BALANCE FORWARD PRODIGY SYSTEMS PAY</td><td></td><td>100.00</td><td>SEP29 OCT10</td><td>19.070D</td></tr>
<tr><td>SEND E-TFR FEE</td><td>1.50</td><td></td><td>200.00</td><td>OCT15</td></tr>
<tr><td>PRODIGY SYSTEMS PAY</td><td></td><td></td><td>OCT24</td><td></td></tr>
<tr><td>0 CHQS ENCLOSED NEXT STATEMENT DATE IS</td><td>NOV 28/53</td><td></td><td>No.</td><td>Amount</td></tr>
<tr><td>MONTHLY AVER. CR. BAL.</td><td>$294.88</td><td>Credits</td><td>2 300.00</td></tr>
<tr><td>DEP CONTENT- CASH 0</td><td>ITEMS 0</td><td>UNC BATCH 0</td><td>Debits</td><td>1 1.50</td></tr>
</table>
<table>
<tr><td>Branch No.</td><td>Account No.</td><td>BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY A</td><td>SEP 29/53 - OCT 31/53</td></tr>
<tr><td>2023</td><td>2023-5224784</td><td>EVERY DAY A</td><td>Page 2 of 2</td></tr>
<tr><td>DESCRIPTION</td><td>CHEQUE/DEBIT</td><td>DEPOSIT/CREDIT</td><td>DATE</td><td>BALANCE</td></tr>
<tr><td>BALANCE FORWARD</td><td></td><td></td><td>OCT24</td><td>279.43</td></tr>
<tr><td>MONTHLY PLAN FEE</td><td>30.00</td><td></td><td>OCT31</td><td>249.43</td></tr>
<tr><td>0 CHQS ENCLOSED NEXT STATEMENT DATE IS NOV 28/53</td><td></td><td></td><td>No.</td><td>Amount</td></tr>
<tr><td>MONTHLY AVER. CR. BAL.</td><td>$294.88</td><td></td><td>Credits</td><td>0 0.00</td></tr>
<tr><td>DEP CONTENT- CASH 0 ITEMS 0 UNC BATCH 0</td><td></td><td></td><td>Debits</td><td>1 30.00</td></tr>
</table>
"""
    stmt = parse_td_canada_statement(md)
    assert stmt is not None
    assert stmt.account_number == "2023-5224784"
    assert stmt.period_start == "2053-09-29"
    assert stmt.period_end == "2053-10-31"
    assert stmt.beginning_balance == -19.07
    assert stmt.ending_balance == 249.43
    assert stmt.stated_total_credits == 300.0
    assert stmt.stated_total_debits == 31.5
    assert [(t.description, t.amount) for t in stmt.transactions] == [
        ("PRODIGY SYSTEMS PAY", 100.0),
        ("SEND E-TFR FEE", -1.5),
        ("PRODIGY SYSTEMS PAY", 200.0),
        ("MONTHLY PLAN FEE", -30.0),
    ]
    assert all(t.running_balance is None for t in stmt.transactions)
    assert reconcile(stmt).ok


def test_analyze_td_canada_native_text_bypasses_gemini(monkeypatch):
    def fail_extract(*args, **kwargs):
        raise AssertionError("Gemini extraction should not run for deterministic TD Canada")

    monkeypatch.setattr("analysis.pipeline.extract_statement", fail_extract)
    md = """
--- Page 1 ---
Accounts issued by: THE TORONTO-DOMINION BANK
Statement of Account Account Type Statement From - To
Branch No. Account No. MAR 31/54 - APR 30/54
BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY B
4444 0052-5220318 Page 1 of 1
DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE
BALANCE FORWARD MAR31 29.42
Lightspeed MSP 100.00 APR01
CMCA Finance BUS 50.00 APR01
SERVICE CHARGE 23.39 APR30 56.03
MONTHLY AVER. CR. BAL. $483.78
Credits 1 100.00
Debits 2 73.39
0 CHQS ENCLOSED NEXT STATEMENT DATE IS MAY 29/54
"""
    report = analyze_markdown(md)
    assert report.model_used == "td-canada-trust-deterministic"
    assert report.reconciliation.ok
    assert report.metrics.effective_total_deposits == 100.0
    assert report.metrics.effective_total_withdrawals == 73.39


def test_parse_td_us_native_text_sections_with_subtotals():
    md = """
STATEMENT OF ACCOUNT
Page: 1 of 2 Statement Period: Mar 01 2054-Mar 31 2054 Cust Ref #: 8264919330-713-7-### Primary Account #: 826-4919330
TD Bank, N.A.
TD Business Simple Checking
NARROWCAST MEDIA LLC Account # 826-4919330
ACCOUNT SUMMARY Beginning Balance 100.00 Deposits 300.00 Electronic Deposits 200.00 Other Credits 50.00
Average Collected Balance 125.00 Interest Earned This Period 0.00 Interest Paid Year-to-Date 0.00 Annual Percentage Yield Earned 0.00% Days in Period 31
Checks Paid 100.00 Electronic Payments 150.00 Other Withdrawals 75.00 Service Charges 10.00 Ending Balance 315.00
DAILY ACCOUNT ACTIVITY Deposits POSTING DATE DESCRIPTION AMOUNT
03/01 DEPOSIT 100.00 03/02 DEPOSIT 200.00
Subtotal: 300.00 Electronic Deposits POSTING DATE DESCRIPTION AMOUNT
03/03 CCD DEPOSIT, STRIPE TRANSFER 125.00 03/04 RTP RCVD,
75.00
STRIPE PAYMENTS COMPANY
Subtotal: 200.00 Other Credits POSTING DATE DESCRIPTION AMOUNT
03/05 WIRE TRANSFER INCOMING 50.00
Subtotal: 50.00
Checks Paid No. Checks: 1 *Indicates break in serial sequence or check processed electronically and listed under Electronic Payments
DATE SERIAL NO. AMOUNT DATE SERIAL NO. AMOUNT
03/06 221* 100.00
Subtotal: 100.00 Electronic Payments POSTING DATE DESCRIPTION AMOUNT
03/07 DBCRD PMT AP, AUT VISA DDA PUR AP
90.00
VENDOR DETAIL
03/08 TD ZELLE SENT, 123 Zelle Vendor 60.00
Subtotal: 150.00 Other Withdrawals POSTING DATE DESCRIPTION AMOUNT
03/09 COUNTER WITHDRAWAL 75.00
Subtotal: 75.00 Service Charges POSTING DATE DESCRIPTION AMOUNT
03/31 MAINTENANCE FEE 10.00
Subtotal: 10.00
"""
    stmt = parse_td_us_statement(md)
    assert stmt is not None
    assert stmt.account_number == "826-4919330"
    assert stmt.period_start == "2054-03-01"
    assert stmt.period_end == "2054-03-31"
    assert stmt.stated_total_credits == 550.0
    assert stmt.stated_total_debits == 335.0
    assert stmt.stated_average_balance == 125.0
    assert stmt.ending_balance == 315.0
    assert [t.amount for t in stmt.transactions] == [100.0, 200.0, 125.0, 75.0, 50.0, -100.0, -90.0, -60.0, -75.0, -10.0]
    assert reconcile(stmt).ok


def test_deterministic_mode_rejects_unmatched_statement(monkeypatch):
    def fail_extract(*args, **kwargs):
        raise AssertionError("Gemini extraction should not run in deterministic-only mode")

    monkeypatch.setattr("analysis.pipeline.extract_statement", fail_extract)

    with pytest.raises(RuntimeError, match="no deterministic parser matched"):
        analyze_markdown("UNSUPPORTED BANK STATEMENT", parse_mode="deterministic")


def test_document_integrity_clear_for_reconciled_transaction_detail():
    stmt = Statement(
        bank="Test Bank",
        beginning_balance=100.0,
        ending_balance=150.0,
        stated_total_credits=75.0,
        stated_total_debits=25.0,
        transactions=[_txn("2054-01-01", 75.0), _txn("2054-01-02", -25.0)],
    )
    recon = reconcile(stmt)
    quality = Quality(
        level="transaction_level",
        transaction_detail_reliable=True,
        summary_totals_reliable=True,
        corporate_use="approved",
    )
    integrity = assess_document_integrity(stmt, recon, quality)
    assert integrity.risk_level == "clear"
    assert integrity.flags == []
    assert integrity.possible_document_issue is False


def test_document_integrity_review_for_incomplete_detail_with_trusted_summary():
    stmt = Statement(
        bank="Test Bank",
        beginning_balance=100.0,
        ending_balance=250.0,
        stated_total_credits=200.0,
        stated_total_debits=50.0,
        transactions=[_txn("2054-01-01", 100.0)],
    )
    recon = reconcile(stmt)
    quality = Quality(
        level="summary_trusted",
        transaction_detail_reliable=False,
        summary_totals_reliable=True,
        corporate_use="summary_only",
    )
    integrity = assess_document_integrity(stmt, recon, quality)
    assert integrity.risk_level == "review"
    assert "transaction_detail_not_corporate_reliable" in integrity.flags
    assert integrity.possible_document_issue is False


def test_document_integrity_high_for_bank_summary_math_contradiction():
    stmt = Statement(
        bank="Test Bank",
        beginning_balance=100.0,
        ending_balance=250.0,
        stated_total_credits=10.0,
        stated_total_debits=50.0,
        transactions=[_txn("2054-01-01", 100.0)],
    )
    recon = reconcile(stmt)
    quality = Quality(
        level="needs_review",
        transaction_detail_reliable=False,
        summary_totals_reliable=False,
        corporate_use="manual_review_required",
    )
    integrity = assess_document_integrity(stmt, recon, quality)
    assert integrity.risk_level == "high"
    assert "summary_math_inconsistent" in integrity.flags
    assert integrity.possible_document_issue is True


def _reconciled_statement_for_page_declarations() -> tuple[Statement, object, Quality]:
    """A document with nothing wrong with it, so the only flag that can appear
    is the page-declaration one under test."""
    stmt = Statement(
        bank="Test Bank",
        beginning_balance=100.0,
        ending_balance=150.0,
        stated_total_credits=75.0,
        stated_total_debits=25.0,
        transactions=[_txn("2054-01-01", 75.0), _txn("2054-01-02", -25.0)],
    )
    quality = Quality(
        level="transaction_level",
        transaction_detail_reliable=True,
        summary_totals_reliable=True,
        corporate_use="approved",
    )
    return stmt, reconcile(stmt), quality


def test_continuation_footer_above_a_page_number_is_not_a_page_declaration():
    """`CONTINUED ON NEXT PAGE` + `2 of 20` is one sentence's last word and the
    next line's first token, not a declaration of 20 bank pages (W3 §M6.1)."""
    stmt, recon, quality = _reconciled_statement_for_page_declarations()
    markdown = (
        "Statement Summary\n"
        "CONTINUED ON NEXT PAGE\n"
        "2 of 20\n"
        "Monthly Activity Details\n"
    )
    integrity = assess_document_integrity(stmt, recon, quality, markdown=markdown)
    assert "missing_declared_statement_page" not in integrity.flags
    assert integrity.flags == []


def test_a_printed_page_declaration_still_flags_absent_pages():
    """The restriction removes the continuation footer and nothing else: a real
    `Page N of M` label with pages missing must still flag."""
    stmt, recon, quality = _reconciled_statement_for_page_declarations()
    markdown = "Page 2 of 20\nMonthly Activity Details\n"
    integrity = assess_document_integrity(stmt, recon, quality, markdown=markdown)
    assert integrity.flags == ["missing_declared_statement_page"]
    assert any("1, 3, 4" in note for note in integrity.notes)


def test_a_page_declaration_still_flags_when_a_continuation_footer_is_also_present():
    """Both shapes on one document: the footer is ignored, the declaration is
    still read, so a genuinely short PDF cannot hide behind the footer."""
    stmt, recon, quality = _reconciled_statement_for_page_declarations()
    markdown = (
        "Page 1 of 3\n"
        "CONTINUED ON NEXT PAGE\n"
        "2 of 3\n"
        "Page 2 of 3\n"
    )
    integrity = assess_document_integrity(stmt, recon, quality, markdown=markdown)
    assert integrity.flags == ["missing_declared_statement_page"]
    assert any("3 are absent" in note for note in integrity.notes)


def test_the_page_declaration_restriction_can_only_remove_matches():
    """The property the protected-module change rests on, asserted directly:
    every page declaration the restricted pattern finds was also found by the
    pattern it replaced, so the flag can only ever be withdrawn."""
    import re

    from analysis import pipeline

    before = re.compile(r"\bPage\s*:?\s*(\d+)\s+of\s+(\d+)\b", re.IGNORECASE)
    after = re.compile(r"(?<!NEXT )\bPage\s*:?\s*(\d+)\s+of\s+(\d+)\b", re.IGNORECASE)
    source = Path(pipeline.__file__).read_text(encoding="utf-8")
    assert after.pattern in source, "the shipped pattern is the one asserted here"

    samples = [
        "Page 1 of 4",
        "page: 2 of 4",
        "PAGE 3 OF 4",
        "CONTINUED ON NEXT PAGE\n2 of 20",
        "continued on next page 7 of 9",
        "Statement Page 2 of 2 CONTINUED ON NEXT PAGE\n3 of 2",
        "no page declaration here at all",
    ]
    for sample in samples:
        assert set(after.findall(sample)) <= set(before.findall(sample))


def _page_integrity(*pages: str):
    """The integrity assessment of a PDF whose physical sheets are `pages`.

    Both arguments the production path supplies: the rendered markdown AND the
    intake object's own page list. They are passed separately on purpose — the
    check must never recover the second from the first.
    """
    stmt, recon, quality = _reconciled_statement_for_page_declarations()
    document = StatementMarkdown(
        source_file="statement.pdf", model="test-model", pages=list(pages)
    )
    return assess_document_integrity(
        stmt, recon, quality, markdown=document.to_markdown(), sheets=document.pages
    )


def test_an_unlabelled_sheet_is_not_a_missing_page():
    """HUNT-CELL H6.2: a layout whose last declared page is a deposit-image
    sheet prints no footer on it, so the label is absent while the page is
    present. Accusing that document of a missing page is a false finding."""
    integrity = _page_integrity(
        "Page 1 of 3\nAccount Summary",
        "Page 2 of 3\nActivity",
        "Images of deposited items\n2/13 $18,245.24    2/23 $8,000.00",
    )
    assert "missing_declared_statement_page" not in integrity.flags
    assert integrity.flags == []


def test_a_declared_page_absent_from_a_fully_labelled_pdf_still_flags():
    """The discriminating case, and why the restriction does not blunt the
    check: the pinned Columbia statement declares five pages, supplies four
    sheets and prints a label on every one of them. Nothing unlabelled can
    stand in for page 5, so the page really is absent and the flag stands."""
    integrity = _page_integrity(
        "Page 1 of 5\nAccount Summary",
        "Page 2 of 5\nActivity",
        "Page 3 of 5\nActivity",
        "Page 4 of 5\nActivity",
    )
    assert integrity.flags == ["missing_declared_statement_page"]
    assert any("5 are absent" in note for note in integrity.notes)


def test_two_unnumbered_disclosure_inserts_are_not_two_missing_pages():
    """The second shape of the same defect (UNID-PACK-B §UB4.3): a Fiserv
    Premier statement footers its pages `1 of 8` … `6 of 8` and then appends the
    GLBA privacy notice as two sheets carrying no footer, so the printed
    denominator counts pages the footers never label. Two unlabelled sheets
    account for two unfound labels exactly — the boundary of the count."""
    integrity = _page_integrity(
        "Page 1 of 4\nAccount Summary",
        "Page 2 of 4\nActivity",
        "IMPORTANT PRIVACY CHOICES FOR CONSUMERS\nWhat we do with your information",
        "To limit our sharing, call the number on your statement",
    )
    assert "missing_declared_statement_page" not in integrity.flags
    assert integrity.flags == []


def test_more_missing_labels_than_unlabelled_sheets_still_flags():
    """The restriction is a count, not a switch: one unlabelled sheet excuses
    one missing label, and no more. Two pages absent behind a single unlabelled
    sheet is still a finding."""
    integrity = _page_integrity(
        "Page 1 of 4\nAccount Summary",
        "Page 2 of 4\nActivity",
        "Images of deposited items",
    )
    assert integrity.flags == ["missing_declared_statement_page"]
    assert any("3, 4 are absent" in note for note in integrity.notes)


def test_page_content_cannot_forge_a_sheet_boundary():
    """The separator-injection vector, and why the sheet count comes from the
    intake object rather than from re-splitting the rendered markdown.

    `--- Page N ---` is an unescaped text convention that `to_markdown` writes
    BETWEEN pages, and page content is OCR output of whatever the document
    printed. This statement declares 5 pages, supplies 4, and its last page
    carries the literal separator line — so a reader that recovered the sheet
    count from the string would see a fifth, unlabelled sheet and withdraw a
    genuine missing-page finding. The PDF has four sheets and page 5 is absent.
    """
    import re

    forged = "Page 4 of 5\nActivity\n\n--- Page 5 ---\n\nnothing was scanned here"
    integrity = _page_integrity(
        "Page 1 of 5\nAccount Summary",
        "Page 2 of 5\nActivity",
        "Page 3 of 5\nActivity",
        forged,
    )
    assert integrity.flags == ["missing_declared_statement_page"], (
        "page content forged a sheet boundary and cleared a fraud-relevant flag"
    )
    # The vector is real: the rendered string does carry a fifth separator.
    assert len(re.findall(r"(?m)^--- Page \d+ ---$", _sheet_markdown(
        "Page 1 of 5\nAccount Summary", "Page 2 of 5\nActivity",
        "Page 3 of 5\nActivity", forged,
    ))) == 5


def test_padding_the_pdf_with_a_blank_sheet_does_not_clear_the_flag():
    """The other way to manufacture an unlabelled sheet: append one to the PDF.

    Columbia's shape with one near-empty sheet stapled on. The sheet is real,
    so the intake object reports it — and it is still refused, because a sheet
    with no text is not a candidate for a page the bank printed and because the
    supplied PDF is still short of the declared total.

    What the combined rule therefore refuses: a short PDF padded with blank or
    whitespace-only sheets, and any document supplying fewer text-bearing
    sheets than it declares pages. What it still accepts, and is the honest
    residual: padding with a sheet that carries real text, which is
    indistinguishable from an unlabelled insert without reading the page.
    """
    integrity = _page_integrity(
        "Page 1 of 5\nAccount Summary",
        "Page 2 of 5\nActivity",
        "Page 3 of 5\nActivity",
        "Page 4 of 5\nActivity",
        "   \n  \n",
    )
    assert integrity.flags == ["missing_declared_statement_page"]


def test_no_sheet_list_leaves_the_check_exactly_as_it_was():
    """Fail-closed: a caller that cannot supply the intake page list gets the
    pre-cell behaviour, so silence can never weaken a fraud-relevant flag."""
    stmt, recon, quality = _reconciled_statement_for_page_declarations()
    markdown = _sheet_markdown(
        "Page 1 of 3\nAccount Summary",
        "Page 2 of 3\nActivity",
        "Images of deposited items",
    )
    integrity = assess_document_integrity(stmt, recon, quality, markdown=markdown)
    assert integrity.flags == ["missing_declared_statement_page"]


def test_passing_the_document_text_as_the_sheet_list_is_refused():
    """`str` is a `Sequence[str]`, so `sheets=markdown` type-checks and then
    iterates one CHARACTER per sheet — thousands of unlabelled sheets, and a
    fraud-relevant flag cleared on every document that carries it. The one
    call-site mistake this parameter invites is refused loudly."""
    stmt, recon, quality = _reconciled_statement_for_page_declarations()
    markdown = _sheet_markdown(
        "Page 1 of 5\nAccount Summary",
        "Page 2 of 5\nActivity",
        "Page 3 of 5\nActivity",
        "Page 4 of 5\nActivity",
    )
    with pytest.raises(TypeError, match="per character"):
        assess_document_integrity(
            stmt, recon, quality, markdown=markdown, sheets=markdown
        )


def _sheet_markdown(*pages: str) -> str:
    return StatementMarkdown(
        source_file="statement.pdf", model="test-model", pages=list(pages)
    ).to_markdown()


#: One synthetic ATB Financial statement of the native-text layout. Hoisted to
#: module scope so §CURRSRC can reuse it: ATB is the schema-default family the
#: batch-6 census named as an expected future currency mover.
ATB_NATIVE_TEXT = """
Deposit Account Statement
Statement date August 31, 2051 Transit number 08479-219 Customer number 0002913777 Page number 1 of 1
Your ATB Financial Branch 08479 Fort McMurray Downtown Branch
A summary of Deposit Account Unlimited Business Banking
00273985278 Transit # 08479-219
Your balance forward on Jul 31, 2051 $1,000.00
Debits to your account (2 items) - $350.00
Credits to your account (2 items) + $600.00
Your closing balance on Aug 31, 2051 = $1,250.00
Details of your account transactions
Debits to your
Credits to your
Date Description
account ($)
account ($) Balance ($)
Jul 31 Balance forward $1,000.00
Aug 1 Direct Deposit Misc. Payments Client $500.00 1,500.00
Aug 2 Direct Debit Business PAD Vendor $200.00 1,300.00
Aug 3 Interac e-Transfer Received $100.00 1,400.00
Aug 31 Monthly Maintenance Fees $150.00 1,250.00
Aug 31 Closing balance $1,250.00
"""


def test_parse_atb_native_text_transactions_from_running_balance():
    stmt = parse_atb_statement(ATB_NATIVE_TEXT)
    assert stmt is not None
    assert stmt.bank == "ATB Financial"
    assert stmt.account_number == "00273985278"
    assert stmt.period_start == "2051-08-01"
    assert stmt.period_end == "2051-08-31"
    assert stmt.stated_total_credits == 600.0
    assert stmt.stated_total_debits == 350.0
    assert [t.amount for t in stmt.transactions] == [500.0, -200.0, 100.0, -150.0]
    assert reconcile(stmt).ok


def test_parse_b1_native_text_running_balances_and_ending_totals():
    md = """
Last statement: March 31, 2054 This statement: April 30, 2054 Total days in statement period: 30
B1Bank 500 Laurel St Baton Rouge LA 70801
Essential Business Checking
Account number XXXXXXX6478 Enclosures 2 Low balance $79,802.46 Average balance $165,555.58
DAILY ACTIVITY DAILY ACTIVITY DAILY ACTIVITY DAILY ACTIVITY
Date Date Description Description Additions Additions Subtractions Subtractions Balance Balance
03-31 Beginning balance $1,000.00 04-01 Incoming Wire 500.00 1,500.00
WIRE DETAIL
04-01 ' Service Charge -20.00 1,480.00
OUT WIRE OLB
04-02 ' Debit Card Purchase -120.00 1,360.00
MERCHANT PURCHASE TERMINAL
04-03 ' Olb Transfer Debit -300.00 1,060.00
REF TRANSFER
Ending totals Ending totals Ending totals Ending totals 500.00 500.00 500.00 500.00 -440.00 -440.00 -440.00 -440.00 $1,060.00 $1,060.00 $1,060.00 $1,060.00
"""
    stmt = parse_b1_statement(md)
    assert stmt is not None
    assert stmt.account_number == "XXXXXXX6478"
    assert stmt.period_start == "2054-04-01"
    assert stmt.period_end == "2054-04-30"
    assert stmt.days_in_period == 30
    assert stmt.stated_average_balance == 165555.58
    assert stmt.stated_total_credits == 500.0
    assert stmt.stated_total_debits == 440.0
    assert [t.amount for t in stmt.transactions] == [500.0, -20.0, -120.0, -300.0]
    assert reconcile(stmt).ok


def test_parse_santander_native_text_running_balances_and_summary_totals():
    md = """
Statement Period 04/01/54 TO 04/30/54
Primary Account #: 51100013856
Santander Bank, N.A.
BUSINESS BANKING ANALYZED CHECKING Statement Period 04/01/54 - 04/30/54
Balances
Beginning Balance $225,068.44 Ending Balance $318,936.83 Deposits/Credits +$136,370.89 Average Daily Balance $250,434.95 Withdrawals/Debits -$42,502.50
Checks Posted
2 Check(s) Posted = $17,222.64
Account Activity
Date Description Credits Debits Balance 04-01 Beginning Balance $225,068.44 04-01 6002 Esquire EPS Daily Dep APR 600200020970 $131.01 $225,199.45
04-02 CHECK 000000046771 $3,502.50 $221,696.95
04-03 TREAS.LINK TRANSFER TO ACCT 231372691 8941321697 - BUSINESS BANKING ANALYZED CHE
$35,000.00 $186,696.95
04-06 USD WIRE IN FROM BANCO BAC SAN J ACCT * 3016 GOOD LIFE COSTA REF BALANCE ORDER 4
$61,920.60 $248,617.55
04-08 USD WIRE IN FROM BANCOLOMBIA (PA ACCT * 1173 NATURNET COLOMBI REF
$69,039.42 $317,656.97
04-09 CHECK 000000046770 $4,000.00 $313,656.97
04-14 CHECK RETURNED 000000046833 46833 REFER TO MAKER $40.00 $313,696.97
04-30 6002 Esquire EPS Daily Dep APR 600200020970 $5,239.86 $318,936.83
04-30 Ending Balance $318,936.83
Please contact us immediately if you think your statement contains any errors.
"""
    stmt = parse_santander_statement(md)
    assert stmt is not None
    assert stmt.account_number == "51100013856"
    assert stmt.period_start == "2054-04-01"
    assert stmt.period_end == "2054-04-30"
    assert stmt.days_in_period == 30
    assert stmt.stated_total_credits == 136370.89
    assert stmt.stated_total_debits == 42502.5
    assert stmt.stated_average_balance == 250434.95
    assert [t.amount for t in stmt.transactions] == [131.01, -3502.5, -35000.0, 61920.6, 69039.42, -4000.0, 40.0, 5239.86]
    assert reconcile(stmt).ok


def test_parse_bluevine_native_text_transactions_and_summary():
    md = """
Bluevine Inc.
Account statement
Account Number: 875108782439
Statement Period: March 2026 (March 1, 2054 - March 31, 2054)
Activity summary
Beginning Balance on 03/01/2054 $1,556.68
Deposits/credits $55,504.86
Withdrawals/debits $-33,007.48
Ending balance on 03/31/2054 $24,054.06
Transactions
Date Description Amount
03/01/54 Interest earned in February 2026 $7.50
03/07/54 LOWES #01195* PLATTSBURGH NY $506.18
03/09/54 JB HOME SERVICES, JB HOME SE $4,945.12
03/20/54 Incoming Wire from JACALYN M BORN $24,921.00
03/24/54 Incoming Wire from JACALYN M BORN $24,921.00
03/31/54 Client payment $204.06
03/01/54 PAYPAL *bmill1026, 4029357733, CA $-103.20
03/11/54 ACH payment to Jessica Favaro $-850.00
03/23/54 PROGRESSIVE *INSURANCE, MAYFIELD VLG, OH $-1,959.79
03/25/54 ACH payment to Jessica Favaro $-850.00
03/31/54 Vendor withdrawal $-29,244.49
"""
    stmt = parse_bluevine_statement(md)
    assert stmt is not None
    assert stmt.account_number == "875108782439"
    assert stmt.period_start == "2054-03-01"
    assert stmt.period_end == "2054-03-31"
    assert stmt.days_in_period == 31
    assert stmt.stated_total_credits == 55504.86
    assert stmt.stated_total_debits == 33007.48
    assert [t.amount for t in stmt.transactions] == [7.5, 506.18, 4945.12, 24921.0, 24921.0, 204.06, -103.2, -850.0, -1959.79, -850.0, -29244.49]
    assert reconcile(stmt).ok


def test_parse_rbc_english_fee_breakdown_is_not_treated_as_month():
    md = """
ROYAL BANK OF CANADA
Business Account Statement
March 2, 2054 to April 1, 2054
Account number: 01678 101-196-4
Account Summary for this Period
Opening balance on March 2, 2054 -$216.54
Total deposits & credits (3) + 21,422.47
Total cheques & debits (5) - 8,624.00
Closing balance on April 1, 2054 = $12,581.93
Account Activity Details
Date Description Cheques & Debits ($) Deposits & Credits ($) Balance ($)
Opening balance -216.54
02 Mar Cheque returned NSF 20,952.47
Monthly fee 6.00
Regular transaction fee 13 Drs @ 2.50
2 Crs @ 2.50 37.50
In branch cash deposited fee $14100 CD @5.00M 70.50 20,621.93
03 Mar ATM deposit - TW922689 270.00
e-Transfer received MICHAELGIANG CA42RuUB 200.00 21,091.93
04 Mar 04 Mar Web payment BIZFUND CA LTD 6,510.00
e-Transfer sent hoang td personal 2,000.00 12,581.93
"""
    stmt = parse_rbc_statement(md)
    assert stmt is not None
    assert stmt.account_number == "01678 101-196-4"
    assert stmt.period_start == "2054-03-02"
    assert stmt.period_end == "2054-04-01"
    # W3 Track A cell 3: the fee breakdown keeps ALL its printed text. The
    # truncated form this used to assert was an artefact of the row splitting
    # at `2.50` -- a printed unit price, not a money cell -- and then patching
    # the row back together with a `<n> Crs @` regex. Rates are now excluded
    # from the grid by the `@` marker the statement prints beside them, so the
    # description is what the bank printed and the amount is unchanged.
    assert [t.description for t in stmt.transactions] == [
        "Cheque returned NSF",
        "Monthly fee",
        "Regular transaction fee 13 Drs @ 2.50 2 Crs @ 2.50",
        "In branch cash deposited fee $14100 CD @5.00M",
        "ATM deposit - TW922689",
        "e-Transfer received MICHAELGIANG CA42RuUB",
        "Web payment BIZFUND CA LTD",
        "e-Transfer sent hoang td personal",
    ]
    assert [t.amount for t in stmt.transactions] == [20952.47, -6.0, -37.5, -70.5, 270.0, 200.0, -6510.0, -2000.0]
    assert reconcile(stmt).ok


def test_parse_cibc_french_statement_uses_balances_for_ambiguous_amounts():
    md = """
Releve de compte CIBC
Du 1 oct au 31 oct 2053
Numero de compte 89-49638
Sommaire du compte
Solde d'ouverture le 1 oct 2053 -16,31 $
Retraits - 1 000,77
Depots + 1 128,76
Solde de cloture le 31 oct 2053 = 111,68 $
Detail de vos operations
Date Description Retraits ($) Depots ($) Solde ($) 1 oct Solde d'ouverture -16,31 $ 1 oct DEBIT PREAUTORISE L'INDUSTRIELLE-ALLIANCE
242,14 -258,45
DEBIT PREAUTORISE L'INDUSTRIELLE-ALLIANCE
277,41 -535,86
2 oct DEPOT GAB BOUCHERVILLE              3E0I
400,00 -135,86
VIREMENT INTERNET 000000109413 350,00 -485,86 VIREMENT INTERAC  011379549504 FLORENCE MAURICE
623,00 137,14
8 oct ACHAT AU DETAIL   528117414391 PETRO-CANADA 14
130,01 7,13
31 oct INTERET SUR DECOUVERT 1,21 5,92 VIREMENT INTERAC  011402666438 Anaymone Codio
105,76 111,68
Solde de cloture 111,68 $
"""
    stmt = parse_cibc_french_statement(md)
    assert stmt is not None
    assert stmt.account_number == "89-49638"
    assert stmt.currency == "CAD"
    assert stmt.period_start == "2053-10-01"
    assert stmt.period_end == "2053-10-31"
    assert stmt.stated_total_credits == 1128.76
    assert stmt.stated_total_debits == 1000.77
    assert [t.amount for t in stmt.transactions] == [-242.14, -277.41, 400.0, -350.0, 623.0, -130.01, -1.21, 105.76]
    assert reconcile(stmt).ok


def test_parse_demo_national_sample_statement_from_running_balances():
    md = """
SAMPLE BUSINESS BANK STATEMENT
Test document for OCR/dashboard validation - not a real bank record
Bank: Demo National Bank Statement Period: January 1, 2054 - January 31, 2054
Business: Apex Auto Detailing LLC Account Number: XXXXX4408
Address: 901 NW 7th Ave, Fort Lauderdale, FL 33311 Account Type: Business Checking
Account Summary Count Amount
Beginning Balance $100.00
Deposits / Credits 2 $550.00
Checks / Debits 2 $175.00
Lender / MCA Debits Included In Debits 1 $125.00
Ending Balance $475.00
Checking Account Activity
Date Description Deposits / Credits Withdrawals / Debits Balance
01/02/2054 ACH CREDIT CLOVER NETWORK $300.00 $400.00
01/05/2054 ACH DEBIT STRATEGIC FUNDING PAYMENT $125.00 $275.00
01/10/2054 MOBILE DEPOSIT CUSTOMER CHECK $250.00 $525.00
01/15/2054 BANK SERVICE FEE $50.00 $475.00
Savings Account Activity
No savings account activity for this statement period.
"""
    stmt = parse_demo_national_statement(md)
    assert stmt is not None
    assert stmt.bank == "Demo National Bank"
    assert stmt.account_number == "XXXXX4408"
    assert stmt.period_start == "2054-01-01"
    assert stmt.period_end == "2054-01-31"
    assert stmt.stated_total_credits == 550.0
    assert stmt.stated_total_debits == 175.0
    assert [t.amount for t in stmt.transactions] == [300.0, -125.0, 250.0, -50.0]
    assert reconcile(stmt).ok


def test_parse_linkbank_running_balance_rows_with_trailing_minus():
    md = """
Managing Your Accounts
LINKBANK.COM
Business Checking Check Safekeeping Account Number XXXXXXXXXXXX0393 Statement Dates 4/01/54 thru 4/30/54 Previous Balance 100.00 Days in the Statement Period 30 2 Deposits/Credits 1,500.00 Average Ledger 500.00 3 Checks/Debits 1,850.00 Average Collected 500.00 Service Charge .00 Interest Paid .00 Current Balance 250.00-
Activity in Date Order Date Description Amount Balance
4/01 Mobile Deposit 1,000.00 1,100.00
4/02 ACH FORWARD FINANCIN 1,200.00- 100.00-
4/13 Check 1510 500.00- 600.00-
4/14 1000015687 UGI Utilities So 500.00 100.00-
4/30 Transfer from x0393 to x0335 150.00- 250.00-
Checks in Number Order
"""
    stmt = parse_linkbank_statement(md)
    assert stmt is not None
    assert stmt.account_number == "XXXXXXXXXXXX0393"
    assert stmt.period_start == "2054-04-01"
    assert stmt.period_end == "2054-04-30"
    assert stmt.ending_balance == -250.0
    assert stmt.stated_total_credits == 1500.0
    assert stmt.stated_total_debits == 1850.0
    assert stmt.stated_average_balance == 500.0
    assert [t.amount for t in stmt.transactions] == [1000.0, -1200.0, -500.0, 500.0, -150.0]
    assert reconcile(stmt).ok


def test_parse_midflorida_statement_reconciles_running_balances():
    md = """
Website midflorida.com
Free Business Checking - XXXXXXXX3628
Account Summary Date Description Amount 04/01/2054 Beginning Balance -$438.53
2 Credit(s) This Period $956.84 1 Debit(s) This Period $227.67
04/30/2054 Ending Balance $290.64
Account Activity
Post Date Description Withdrawal Deposit Balance
04/01/2054 Beginning Balance -$438.53
04/01/2054 Deposit $856.84 $418.31
04/02/2054 External Withdrawal Kemper Auto $227.67 $190.64
04/03/2054 Zelle Deposit Zelle From Make it True Product $100.00 $290.64
Checks Cleared
Overdraft and Returned Item Fees
"""
    stmt = parse_midflorida_statement(md)
    assert stmt is not None
    assert stmt.bank == "MIDFLORIDA Credit Union"
    assert stmt.stated_total_credits == 956.84
    assert stmt.stated_total_debits == 227.67
    assert len(stmt.transactions) == 3
    assert reconcile(stmt).ok


def test_parse_texas_bank_statement_keeps_service_charge_separate():
    md = """
Texas Bank and Trust
6250TEXAS NNNNNN
SMALL BUSINESS CHECKING
Account Number 564400 Balance on 06/01/54 9,793.64 Date From 06/01/54
Deposits ( 1 ) + 3,061.11 Date To 06/30/54 Interest Paid + 0.00
Days in Statement Period 30 Checks/Debits ( 1 ) - 536.69
Average Ledger 4,879.33 Service Charge - 10.00 Average Collected 4,859.11
Balance on 06/30/54 12,308.06
Deposits and Other Credits
Date Description Amount 06/04/54 ACH_LBP REPUBLIC FINANCE PPD 3,061.11
Withdrawals and Other Debits
Date Description Amount 06/01/54 POS DEB 1010 05/31/54 SHREVEPORT TRUCK LA C#8801 536.69-
06/30/54 SERVICE CHARGE 10.00-
Daily Balance Information
WITHDRAWALS AND OTHER DEBITS (CONTINUED)
"""
    stmt = parse_texas_bank_statement(md)
    assert stmt is not None
    assert stmt.stated_total_debits == 536.69
    assert stmt.stated_service_charge == 10.0
    assert len(stmt.transactions) == 3
    assert reconcile(stmt).ok


def test_parse_wilson_muir_statement_combines_summary_categories():
    md = """
WILSON & MUIR BK & TRUST
Statement Date: 05/30/2053 Account No.: #299 Page: 1
SMALL BUSINESS PACKAGE SUMMARY Type : **REG Status : Active
Category Number Amount Balance Forward From 04/30/53 100.00
Deposits 1 50.00+ Debits 1 30.00 Automatic Withdrawals 1 20.00
Automatic Deposits 1 10.00+ Card Activity 0 0.00
Ending Balance On 05/30/53 110.00 Foreign Items Deposited 0 Items Deposited 1
Average Balance (Ledger) 105.00+
ALL CREDIT ACTIVITY
Date Type Amount 05/08/53 Deposit 50.00
Date Description Amount 05/29/53 MERCH BNKCD NSD DEPOSIT 10.00
ELECTRONIC DEBITS
Date Description Amount 05/01/53 ONDECK CAPITAL 5 33952 20.00
CHECKS AND OTHER DEBITS * indicates a gap in the check numbers
Date Check # Amount 05/02/53 1367 30.00
DAILY BALANCE SUMMARY
"""
    stmt = parse_wilson_muir_statement(md)
    assert stmt is not None
    assert stmt.stated_total_credits == 60.0
    assert stmt.stated_total_debits == 50.0
    assert stmt.stated_average_balance == 105.0
    assert len(stmt.transactions) == 4
    assert reconcile(stmt).ok


def test_parse_secu_statement_reconciles_business_checking_detail():
    md = """
Statement Period: From: 03/01/2054 To: 03/31/2054 Page Number: 1 of 3
secumd.org
Your Deposit Account(s) Summary
Account Starting Deposits Withdrawals Interest Ending YTD Interest Description Balance ($) Credits ($) Debits ($) Dividend ($) Balance ($) Dividend ($)
8,646.18 1,300.00 175.43 0.00 9,770.75 0.00 Free Business Checking (8035073268)
Your Detailed Statement
Date Transaction Description Amount ($) Total Balance ($) Free Business Checking  (8035073268)
03/01 8,646.18 Starting Balance
03/01 -25.43 8,620.75 Check Card Withdrawal PETSMART # 0358 BOWIE MDUS
03/02 -150.00 8,470.75 NOW Withdrawal Zelle To Sherrie Waul
03/03 +1,300.00 9,770.75 External Deposit H.A. PRINCE GEOR - CHECKING
03/31 9,770.75 Ending Balance
General Statement policies for SECU of MD, Inc.
"""
    stmt = parse_secu_statement(md)
    assert stmt is not None
    assert stmt.bank == "SECU Maryland"
    assert stmt.account_number == "8035073268"
    assert stmt.stated_total_credits == 1300.0
    assert stmt.stated_total_debits == 175.43
    assert [t.amount for t in stmt.transactions] == [-25.43, -150.0, 1300.0]
    assert reconcile(stmt).ok


def test_parse_navy_federal_statement_handles_reordered_credit_rows():
    md = """
Statement of Account
Statement Period
04/01/54 - 04/30/54
Navy Federal
Summary of your deposit accounts
Previous Deposits/ Withdrawals/ Ending YTD Balance Credits Debits Balance Dividends
Business Checking
7208449525
$0.00
$50.00
$3.07
$46.93
$0.00
Checking
Business Checking - 7208449525
Date
Transaction Detail
Amount($)
Balance($)
0.00
04-01
Beginning Balance
50.00
50.00
04-13
Transfer From Savings
3.07 46.93
-
04-13
POS Debit- Business Debit Card 0875 04-12-26 McDonald's F6430 Columbia MD
04-30
Ending Balance
46.93
Average Daily Balance - Current Cycle: $87.57
Mbr Business Savings
"""
    stmt = parse_navy_federal_statement(md)
    assert stmt is not None
    assert stmt.bank == "Navy Federal Credit Union"
    assert stmt.account_number == "7208449525"
    assert stmt.stated_average_balance == 87.57
    assert [t.amount for t in stmt.transactions] == [50.0, -3.07]
    assert [t.date for t in stmt.transactions] == ["2054-04-13", "2054-04-13"]
    assert reconcile(stmt).ok


def test_parse_navy_federal_statement_handles_separate_negative_balance_marker():
    md = """
Statement of Account
Statement Period
06/01/54 - 06/30/54
Navy Federal
Summary of your deposit accounts
Previous Deposits/ Withdrawals/ Ending YTD Balance Credits Debits Balance Dividends
Business Checking
7208449525
$0.48
$0.00
$59.00
$58.52-
$0.00
Checking
Business Checking - 7208449525
Date
Transaction Detail
Amount($)
Balance($)
0.48
06-01
Beginning Balance
06-05
Returned Item Fee 12114039
29.00 28.52 -
-
06-05
Returned Item Fee 12114040
30.00
58.52 -
06-30
Ending Balance
58.52-
Average Daily Balance - Current Cycle: $12.90-
Mbr Business Savings
"""
    stmt = parse_navy_federal_statement(md)
    assert stmt is not None
    assert stmt.ending_balance == -58.52
    assert stmt.stated_average_balance == -12.9
    assert [t.amount for t in stmt.transactions] == [-29.0, -30.0]
    assert stmt.stated_nsf_count is None
    assert compute_metrics(stmt).nsf_count == 2
    assert reconcile(stmt).ok


@pytest.mark.parametrize(
    ("filename", "transaction_count", "posting_days", "nsf_count", "average_daily_balance"),
    [
        ("APRIL 2026.pdf", 80, 11, 1, 87.58),
        ("MAY 2026.pdf", 87, 15, 2, 73.00),
        ("JUNE 2026.pdf", 63, 14, 2, 138.77),
        ("MARCH 2026.pdf", 5, 3, 0, -12.91),
    ],
)
def test_navy_federal_native_layout_preserves_dates_and_descriptions(
    filename: str,
    transaction_count: int,
    posting_days: int,
    nsf_count: int,
    average_daily_balance: float,
):
    path = Path("Bank Statements/Navy Fed", filename)
    doc = parse_native_navy_federal(path.read_bytes(), source_file=filename)
    assert doc is not None
    assert doc.model == "native-pdf-text+navy-federal-layout"

    report = analyze_markdown(doc.to_markdown(), parse_mode="deterministic")
    assert len(report.statement.transactions) == transaction_count
    assert reconcile(report.statement).ok
    assert report.metrics.nsf_count == nsf_count
    assert report.statement.stated_nsf_count is None

    adb = report.metrics.adb
    assert adb is not None
    assert adb.average_daily_balance == average_daily_balance
    assert adb.validations["posting_dates_cover_source"] is True
    assert adb.parsed_posting_days == posting_days
    assert adb.source_posting_days == posting_days
    assert adb.missing_posting_dates == []
    assert adb.ok is True
    assert report.statement.stated_average_balance is not None
    assert round(
        abs(average_daily_balance - report.statement.stated_average_balance), 2
    ) <= 0.01


def test_parse_consumers_primary_business_checking_with_wrapped_amounts():
    md = """
Summary of All Accounts
Statement Period:
Mar 01, 2053 to Mar 31, 2053
credit union
ConsumersCU.org
BusinessPlus Checking (S70) - 0836327000
Account Holders: Example LLC
Beginning Balance $1,000.00 Total Check(s) & Debits (-) - $125.00 Ending Balance $1,177.25 Total Deposit(s) (+) + $302.25
Transaction Details
POSTED DATE TRANSACTION DESCRIPTION DEPOSITS(+) WITHDRAWALS(-) BALANCE
Mar 01 Previous Balance $1,000.00
Mar 03 ACH CREDIT DIRECT-PAY CONSUMERS CREDIT ID2242176753
$300.00 $1,300.00
Mar 04 ACH DEBIT PAYMENT CAN CAPITAL ID1061508068 $100.00 $1,200.00
Mar 31 DIVIDEND CREDIT $2.25 $1,202.25
Mar 31 SHARE DRAFT (53275) $25.00 $1,177.25
Account Fee Summary
"""
    stmt = parse_consumers_statement(md)
    assert stmt is not None
    assert stmt.bank == "Consumers Credit Union"
    assert stmt.account_number == "0836327000"
    assert stmt.period_start == "2053-03-01"
    assert stmt.period_end == "2053-03-31"
    assert stmt.stated_total_credits == 302.25
    assert stmt.stated_total_debits == 125.0
    assert [t.amount for t in stmt.transactions] == [300.0, -100.0, 2.25, -25.0]
    assert reconcile(stmt).ok


def test_consumers_included_prior_date_rows_are_applied_to_opening_day():
    stmt = parse_consumers_statement(_artifact_markdown("041_Consumers March - Monthly Statement.md"))
    assert stmt is not None
    assert all(stmt.period_start <= txn.date <= stmt.period_end for txn in stmt.transactions)
    shifted = [txn for txn in stmt.transactions if "printed 2025-02-28" in txn.description]
    assert len(shifted) == 2
    assert all(txn.date == "2025-03-01" for txn in shifted)
    assert compute_metrics(stmt).average_daily_balance == 26804.59


def test_parse_first_citizens_statement_reconciles_section_totals():
    md = _artifact_markdown("064_First Citizens Bank.md")
    stmt = parse_first_citizens_statement(md)
    assert stmt is not None
    assert stmt.bank == "First Citizens Bank"
    assert stmt.account_number == "009167365168"
    assert stmt.period_start == "2026-03-01"
    assert stmt.period_end == "2026-03-31"
    assert stmt.beginning_balance == -1145.55
    assert stmt.ending_balance == 14702.87
    assert len(stmt.transactions) == 116
    assert stmt.stated_total_credits == 99911.91
    assert stmt.stated_total_debits == 84063.49
    assert stmt.stated_average_balance == 8117.14
    assert round(sum(t.amount for t in stmt.transactions if t.amount > 0), 2) == 99911.91
    assert round(-sum(t.amount for t in stmt.transactions if t.amount < 0), 2) == 84063.49
    # Counts and the service charge come off the printed summary too, and the
    # counts account for every posting: 10 deposits + 9 other credits,
    # 11 cheques + 86 other debits.
    assert stmt.stated_credit_count == 19
    assert stmt.stated_debit_count == 97
    assert stmt.stated_credit_count + stmt.stated_debit_count == len(stmt.transactions)
    assert stmt.stated_service_charge == 0.0
    # Cheques keep their printed serial; the deposits grid prints no
    # description column at all.
    assert any(t.description == "Check #1181" for t in stmt.transactions)
    assert reconcile(stmt).ok


def test_first_citizens_balances_are_not_derived_from_the_postings():
    """Pins NON-DERIVATION of the two balances. Not independence.

    The parser this replaced computed `beginning = ending - credits + debits`
    from its own transaction sums, so the balances moved with whatever it
    happened to parse and `beginning + credits - debits == ending` held for any
    input at all. Mutating the posting list after the parse must now change the
    walk, which is what this asserts: the balances are fixed by the printed
    summary and do not follow the detail.

    It deliberately does NOT claim reconciliation independently tests the
    detail. It cannot for this bank: `_matches` already requires each parsed
    section to equal the total the bank printed for it, and the printed summary
    closes on its own arithmetic, so on any statement the parser ACCEPTS the
    reconciliation is algebraically forced. The gate is what does the work; the
    mutation here bypasses that gate on purpose.
    """
    md = _artifact_markdown("064_First Citizens Bank.md")
    stmt = parse_first_citizens_statement(md)
    assert stmt is not None
    assert reconcile(stmt).ok

    damaged = stmt.model_copy(deep=True)
    damaged.transactions = damaged.transactions[:-1]
    assert not reconcile(damaged).ok


def test_first_citizens_declines_a_statement_with_no_printed_summary():
    """No control record, no parse — the figures are not inferable."""
    md = _artifact_markdown("064_First Citizens Bank.md")
    without_summary = md.replace("Statement Period Days Average Ledger Balance", "")
    assert parse_first_citizens_statement(without_summary) is None


def test_ibc_source_summary_conflict_fails_closed():
    md = _artifact_markdown("065_IBC April (1).md")
    stmt = parse_ibc_statement(md)
    assert stmt is not None
    assert stmt.bank == "IBC Bank"
    assert stmt.account_number == "2117858783"
    assert stmt.period_start == "2026-04-01"
    assert stmt.period_end == "2026-04-30"
    assert stmt.beginning_balance == 10625.31
    assert stmt.ending_balance == 18442.35
    assert len(stmt.stated_daily_balances) == 21
    assert stmt.stated_daily_balances[0].balance == -625.31
    assert stmt.stated_daily_balances[-1].balance == 8442.35
    assert len(stmt.transactions) == 317
    assert stmt.stated_credit_count == 21
    assert stmt.stated_debit_count == 296
    assert stmt.stated_total_credits == 98812.6
    assert stmt.stated_total_debits == 89744.94
    assert stmt.stated_service_charge == 46.85
    assert stmt.stated_average_balance == 14388.96
    assert any("NSF Return Item Fee" in t.description for t in stmt.transactions)
    assert any("MUDFLAP" in t.description for t in stmt.transactions)
    reconciliation = reconcile(stmt)
    assert reconciliation.ok is False
    assert reconciliation.summary_ok is False
    assert reconciliation.stated_beginning == 10625.31
    assert reconciliation.stated_ending == 18442.35
    assert reconciliation.computed_ending == 19692.97
    assert reconciliation.sum_delta == 1250.62
    metrics = compute_metrics(stmt)
    assert metrics.adb_ok is False
    assert metrics.average_daily_balance is None
    assert metrics.min_balance is None
    assert metrics.max_balance is None
    assert metrics.nsf_count == 1
    # MUDFLAP rows are card-present fuel purchases, not lender repayments.
    assert metrics.lender_debits == 0.0

    report = analyze_markdown(md, parse_mode="deterministic")
    from analysis.serialization import report_to_dict

    payload = report_to_dict(report)
    assert payload["statement"]["beginning_balance"] == 10625.31
    assert payload["statement"]["ending_balance"] is None
    assert payload["reconciliation"]["stated_ending"] == 18442.35
    _assert_withheld_adb_is_not_public(report, "IBC April (1).pdf")


@pytest.mark.parametrize(
    ("filename", "period_start", "period_end", "row_count", "beginning", "ending", "credits", "debits", "adb"),
    [
        ("053_Altana april 26.md", "2026-04-01", "2026-04-30", 482, 635.57, 3927.30, 135523.25, 132231.52, 7188.19),
        ("054_Altana june 26.md", "2026-06-01", "2026-06-30", 505, 5613.58, 3903.99, 229517.01, 231226.60, 10508.91),
        ("055_Altana may 26.md", "2026-05-01", "2026-05-31", 473, 3927.30, 5613.58, 190025.61, 188339.33, 9244.82),
    ],
)
def test_parse_altana_statement_reconciles_running_balance_detail(
    filename,
    period_start,
    period_end,
    row_count,
    beginning,
    ending,
    credits,
    debits,
    adb,
):
    md = _artifact_markdown(filename)
    stmt = parse_altana_statement(md)
    assert stmt is not None
    assert stmt.bank == "Altana Federal Credit Union"
    assert stmt.account_number == "0050"
    assert stmt.period_start == period_start
    assert stmt.period_end == period_end
    assert stmt.beginning_balance == beginning
    assert stmt.ending_balance == ending
    assert len(stmt.transactions) == row_count
    assert round(sum(t.amount for t in stmt.transactions if t.amount > 0), 2) == credits
    assert round(-sum(t.amount for t in stmt.transactions if t.amount < 0), 2) == debits
    assert reconcile(stmt).ok
    metrics = compute_metrics(stmt)
    assert metrics.average_daily_balance == adb
    assert metrics.lender_debits > 0


def test_parse_altana_june_handles_intraday_negative_balance_crossing():
    md = _artifact_markdown("054_Altana june 26.md")
    stmt = parse_altana_statement(md)
    assert stmt is not None
    negative_rows = [tx for tx in stmt.transactions if tx.running_balance is not None and tx.running_balance < 0]
    assert [tx.running_balance for tx in negative_rows] == [-35.54, -105.54, -115.22]
    assert reconcile(stmt).ok


def test_parse_desjardins_usd_layout_statement_reconciles_native_text():
    pdf = Path("Bank Statements/Misc/USD FEB 2026.pdf").read_bytes()
    doc = parse_native_desjardins(pdf, source_file="USD FEB 2026.pdf")
    assert doc is not None
    assert doc.model == "native-pdf-text+desjardins-layout"
    stmt = parse_desjardins_statement(doc.to_markdown())
    assert stmt is not None
    assert stmt.bank == "Desjardins"
    assert stmt.account_number == "SJ 815-30355-9"
    assert stmt.period_start == "2026-02-01"
    assert stmt.period_end == "2026-02-28"
    assert stmt.currency == "USD"
    assert stmt.beginning_balance == 628.57
    assert stmt.ending_balance == 1071.53
    assert len(stmt.transactions) == 47
    assert round(sum(t.amount for t in stmt.transactions if t.amount > 0), 2) == 75893.82
    assert round(-sum(t.amount for t in stmt.transactions if t.amount < 0), 2) == 75450.86
    assert stmt.transactions[-1].description.startswith("INT Interest on PCA")
    assert reconcile(stmt).ok
    metrics = compute_metrics(stmt)
    assert metrics.average_daily_balance == 3595.43


# ---------------------------------------------------------------------------
# Desjardins — the printed denomination (W3 #CURRENCY). The caisse prints the
# account's currency in front of the product name that heads the ledger. Every
# archive document of this layout prints `USD`, so the value published does not
# change; what changes is where it comes from.
# ---------------------------------------------------------------------------

_DESJ_HEAD = """
CAISSE DESJARDINS DE BORDEAUX-CARTIER
From February 1 to February 28, 2054
STATEMENT OF ACCOUNT
SJ 000-00000-0
PCA                           {code}DESJARDINS CORPORATE BUILD-UP ACCOUNT
  Date  Code                       Description   Charges  Withdrawal  Deposit  Balance
               Balance forward                                                 100.00
 FEB   6 INBD Funds transfer received / EXAMPLE/                    50.00      150.00
"""


def test_desjardins_publishes_the_denomination_printed_on_the_product_line():
    stmt = parse_desjardins_statement(_DESJ_HEAD.format(code="USD "))
    assert stmt is not None
    assert stmt.currency == "USD"


def test_desjardins_publishes_cad_when_the_product_line_prints_cad():
    """The reader has no CAD document of this layout to point at — and that is
    exactly why the currency must come off the page rather than out of a
    constant that assumed the only issue anyone had seen."""
    stmt = parse_desjardins_statement(_DESJ_HEAD.format(code="CAD "))
    assert stmt is not None
    assert stmt.currency == "CAD"


def test_desjardins_source_filename_cannot_set_the_currency():
    """W3 FILENAME-BOUNDARY / F-PROVENANCE. This reader's anchor is the product
    name, not a line position, so a file named after the product carries the
    exact token: on a Canadian-dollar issue, `USD DESJARDINS CORPORATE BUILD-UP
    ACCOUNT.pdf` in the source comment is a live counterfeit. `admissible_text`
    — the seam every parser sits behind — removes the comment first. The
    pinned Desjardins statement really is named `USD FEB 2026.pdf`, so this is
    the one family where the operator's name and the page say the same thing
    for reasons that have nothing to do with each other."""
    from analysis.parser_registry import admissible_text
    from analysis.desjardins import _printed_currency

    comment = (
        "<!-- source: USD DESJARDINS CORPORATE BUILD-UP ACCOUNT.pdf "
        "| pages: 1 | model: x | empty: 0 -->\n\n"
    )
    cad = _DESJ_HEAD.format(code="CAD ")
    assert _printed_currency(comment + cad) is None  # counterfeit -> two codes
    assert _printed_currency(admissible_text(comment + cad)) == "CAD"

    silent = _DESJ_HEAD.format(code="")
    assert _printed_currency(comment + silent) == "USD"  # the name alone decides
    assert _printed_currency(admissible_text(comment + silent)) is None

    stmt = parse_desjardins_statement(admissible_text(comment + cad))
    assert stmt is not None
    assert stmt.currency == "CAD"


def test_desjardins_does_not_publish_the_account_type_mark_as_a_currency():
    """`PCA` is the three-letter account-type mark printed immediately before
    the product name. A reader that published whatever three letters it
    captured would publish `PCA`; the admissible set is closed, so a product
    line with no denomination leaves the default standing instead."""
    from analysis.desjardins import _printed_currency

    document = _DESJ_HEAD.format(code="")
    assert _printed_currency(document) is None
    stmt = parse_desjardins_statement(document)
    assert stmt is not None
    assert stmt.currency == "USD"


@pytest.mark.parametrize(
    (
        "filename", "period_start", "period_end", "row_count", "beginning",
        "ending", "credits", "debits", "service", "daily_count", "adb",
    ),
    [
        ("059_Banco Popular April 2026.md", "2026-04-01", "2026-04-30", 179, 470.78, 42.30, 76943.18, 77088.92, 282.74, 22, 679.27),
        ("060_Banco Popular Junio 2026.md", "2026-05-30", "2026-06-30", 172, 1908.41, 1821.39, 96990.28, 96605.21, 472.09, 21, 1507.80),
        ("061_Banco Popular May 2026.md", "2026-05-01", "2026-05-29", 180, 42.30, 1908.41, 114025.86, 111959.70, 200.05, 20, 2342.51),
    ],
)
def test_parse_banco_popular_statement_reconciles_with_service_charge(
    filename,
    period_start,
    period_end,
    row_count,
    beginning,
    ending,
    credits,
    debits,
    service,
    daily_count,
    adb,
):
    stmt = parse_banco_popular_statement(_artifact_markdown(filename))
    assert stmt is not None
    assert stmt.bank == "Banco Popular"
    assert stmt.account_number == "318-867491"
    assert stmt.period_start == period_start
    assert stmt.period_end == period_end
    assert stmt.beginning_balance == beginning
    assert stmt.ending_balance == ending
    assert stmt.stated_total_credits == credits
    assert stmt.stated_total_debits == debits
    assert stmt.stated_service_charge == service
    assert len(stmt.stated_daily_balances) == daily_count
    assert len(stmt.transactions) == row_count
    assert stmt.transactions[-1].description == "Service charges"
    assert stmt.transactions[-1].amount == -service
    assert round(sum(t.amount for t in stmt.transactions if t.amount > 0), 2) == credits
    assert round(-sum(t.amount for t in stmt.transactions if t.amount < 0), 2) == round(debits + service, 2)
    assert reconcile(stmt).ok
    metrics = compute_metrics(stmt)
    assert metrics.average_daily_balance == adb
    assert metrics.adb is not None and metrics.adb.ok


def test_parse_mission_valley_sectioned_statement_with_checks_and_daily_balances():
    md = """
Online Banking www.missionvalleybank.com
Thank you for choosing Mission Valley Bank as your financial partner.
GREEN CONVERGENCE XXXXXXXX1245 Statement Ending 01/30/2054 Page 1 of 6
Business Checking - XXXXXXXX1245
Account Summary Date Description Amount 01/01/2054 Beginning Statement Balance $100.00 2 Credit(s) This Period $350.00 3 Debit(s) This Period $125.00 01/30/2054 Ending Statement Balance $325.00 Service Charges $0.00
Deposits Date Description Amount 01/02/2054 MERCHANT CAPTURE DEPOSIT $150.00
Deposits (continued) Date Description Amount 01/03/2054 Incoming Wire,LG FUNDING LLC,Funding Deal $200.00
Electronic Debits Date Description Amount 01/04/2054 DIRECT DEB DELAGELANDEN TRN* 1* 5945551\\ $50.00
Other Debits Date Description Amount 01/05/2054 SERVICE CHARGE $25.00
Checks Cleared
Check Nbr Date Amount 30812 01/06/2054 $50.00 * Indicates skipped check number
Daily Balances
Date Amount 01/02/2054 $250.00 01/03/2054 $450.00
Date Amount 01/04/2054 $400.00 01/05/2054 $375.00 01/06/2054 $325.00
"""
    stmt = parse_mission_valley_statement(md)
    assert stmt is not None
    assert stmt.bank == "Mission Valley Bank"
    assert stmt.account_number == "XXXXXXXX1245"
    assert stmt.stated_credit_count == 2
    assert stmt.stated_debit_count == 3
    assert [t.amount for t in stmt.transactions] == [150.0, 200.0, -50.0, -25.0, -50.0]
    assert stmt.transactions[-1].running_balance == 325.0
    assert reconcile(stmt).ok


def test_parse_dakota_west_sectioned_statement_with_wrapped_debit_amount():
    md = """
Thank you for being a member of Dakota West Credit Union.
Website dakotawestcu.com
Account Type Account Number Ending Balance Badlands Savings 35127372 $50.41 Small Business Checking 35127380 $4,026.32
Small Business Checking - 35127380
Account Summary Date Description Amount 11/01/2053 Beginning Balance $100.00 1 Credit(s) This Period $500.00 3 Debit(s) This Period $225.00 11/30/2053 Ending Balance $375.00
Other Credits Date Description Amount 11/04/2053 External Deposit ACH ACH FILE - ACH 193219 $500.00
Other Debits Date Description Amount 11/03/2053 POS Signature Purchase GOOGLE * GSUITE_ 1600 AMPHITHEATRE PMOUNTAIN VIEW CAUS
$25.00
11/03/2053 External Withdrawal EBF Holdings - EBF DEBIT 12686396 $100.00
Checks Cleared
Check Nbr Date Amount 1172 11/20/2053 $100.00 * Indicates skipped check number
"""
    stmt = parse_dakota_west_statement(md)
    assert stmt is not None
    assert stmt.bank == "Dakota West Credit Union"
    assert stmt.account_number == "35127380"
    assert [t.amount for t in stmt.transactions] == [-25.0, -100.0, 500.0, -100.0]
    assert reconcile(stmt).ok


def test_parse_truist_native_text_sections_and_ignores_secondary_account():
    md = """
Your consolidated statement
Truist.com
¡ TRUIST DYNAMIC BUSINESS CHECKING - CORE TIER 1100033769111
Account summary Your previous balance as of 01/30/2054 $100.00 Checks - 75.00 Other withdrawals, debits and service charges - 125.00 Deposits, credits and interest + 300.00 Your new balance as of 02/27/2054 = $200.00
Checks DATE CHECK # AMOUNT($) DATE CHECK # AMOUNT($) DATE CHECK # AMOUNT($) 02/05 1049 25.00 02/17 *1054 50.00 * indicates a skip in sequential check numbers above this item Total checks = $75.00
Other withdrawals, debits and service charges DATE DESCRIPTION AMOUNT($) 02/02 DEBIT CARD PURCHASE STORE 25.00 02/03 ZELLE BUSINESS PAYMENT TO Vendor PAYMENT ID BBT1 50.00 continued
§ PAGE  1  OF  2 0000001
--- Page 2 ---
¡ TRUIST DYNAMIC BUSINESS CHECKING - CORE TIER 1100033769111 (continued) DATE DESCRIPTION AMOUNT($) 02/04 OVERDRAFT ITEM FEE ($36/ITEM) 36 50.00 Total other withdrawals, debits and service charges = $125.00
Deposits, credits and interest DATE DESCRIPTION AMOUNT($) 02/02 ZELLE BUSINESS PAYMENT FROM Client PAYMENT ID BBT2 100.00 02/05 CASH DEPOSIT 02-05-26 BRANCH 200.00 Total deposits, credits and interest = $300.00
¡ TRUIST SIMPLE BUSINESS CHECKING 1100033769138
Account summary Your previous balance as of 01/30/2054 $15.98 Checks - 0.00 Other withdrawals, debits and service charges - 0.00 Deposits, credits and interest + 0.00 Your new balance as of 02/27/2054 = $15.98
"""
    stmt = parse_truist_statement(md)
    assert stmt is not None
    assert stmt.account_number == "1100033769111"
    assert stmt.period_start == "2054-01-31"
    assert stmt.period_end == "2054-02-27"
    assert stmt.beginning_balance == 100.0
    assert stmt.ending_balance == 200.0
    assert stmt.stated_total_credits == 300.0
    assert stmt.stated_total_debits == 200.0
    assert [t.amount for t in stmt.transactions] == [-25.0, -50.0, -25.0, -50.0, -50.0, 100.0, 200.0]
    assert reconcile(stmt).ok


def test_parse_us_bank_native_text_sections_and_totals():
    md = """
Business Statement
Account Number:
1 047 5916 1631 Statement Period:
Apr 1, 2054
through Apr 30, 2054
PLATINUM BUSINESS MONEY MARKET
U.S. Bank National Association
Account Number 1-047-5916-1631
Account Summary
# Items
Annual Percentage Yield Earned 0.56% Interest Earned this Period $ 8.04 Interest Paid this Year $ 34.79 Number of Days in Statement Period 30
Beginning Balance on Apr 1 $ 4,664.53 Customer Deposits 1 38,604.42 Other Deposits 2 510,008.04 Other Withdrawals 3 512,963.42-
Ending Balance on  Apr 30, 2054 $ 40,313.57
Customer Deposits
Number Date Ref Number Amount
Apr 2 8952044985 38,604.42
Total Customer Deposits $ 38,604.42
Other Deposits
Date Description of Transaction Ref Number Amount
Apr 17 Mobile Banking Transfer From Account 104787701788 $ 510,000.00
Products and services available in U.S. only.
--- Page 3 ---
PLATINUM BUSINESS MONEY MARKET (CONTINUED)
U.S. Bank National Association
Account Number 1-047-5916-1631
Other Deposits (continued)
Date Description of Transaction Ref Number Amount
Apr 30 Interest Paid 3000007237 8.04
Total Other Deposits $ 510,008.04
Other Withdrawals
Date Description of Transaction Ref Number Amount
Apr 1 Electronic Withdrawal
To Yardi Service Ch
9000278329SIGONFILE HVLKKL $ 0.95-
REF=260900146243390N00
Apr 17 Wire Debit REF005842
JPMCHASE NYC        260417B02H4F
1175 JOHN STREET WEST H 512,947.47-
BNF=PAYCHEX OF NEW YORK
Apr 30 Monthly Maintenance Fee 3000007238 15.00-
Total Other Withdrawals $ 512,963.42-
"""
    stmt = parse_us_bank_statement(md)
    assert stmt is not None
    assert stmt.account_number == "1-047-5916-1631"
    assert stmt.period_start == "2054-04-01"
    assert stmt.period_end == "2054-04-30"
    assert stmt.days_in_period == 30
    assert stmt.stated_total_credits == 548612.46
    assert stmt.stated_total_debits == 512963.42
    assert stmt.stated_interest_paid == 8.04
    assert [t.amount for t in stmt.transactions] == [38604.42, 510000.0, 8.04, -0.95, -512947.47, -15.0]
    assert reconcile(stmt).ok


def test_parse_capital_one_uses_running_balances_to_fix_miscolumned_credits():
    md = """
AN IMPORTANT MESSAGE TO OUR CLIENTS
CapitalOne Bank
ACCOUNT SUMMARY FOR PERIOD MARCH 01, 2054 - MARCH 31, 2054
Business Basic Checking 00005733890536
<table><tr><td>Previous Balance 02/28/54</td><td>$619.39</td></tr><tr><td>19 Deposits/Credits</td><td>$9,230.78</td></tr><tr><td>30 Checks/Debits</td><td>($8,968.79)</td></tr><tr><td>Service Charges</td><td>($15.00)</td></tr><tr><td>Ending Balance 03/31/54</td><td>$866.38</td></tr></table>
<table><tr><td>Number of Days in Cycle</td><td>31</td></tr><tr><td>Minimum Balance This Cycle</td><td>($20.71)</td></tr><tr><td>Average Collected Balance</td><td>$194.39</td></tr></table>
<table><tr><td>Date</td><td>Description</td><td>Deposits/Credits</td><td>Withdrawals/Debits</td><td>Resulting Balance</td></tr>
<tr><td>03/02</td><td>TRANSFER DEPOSIT From ....2395</td><td>$550.00</td><td></td><td>$1,169.39</td></tr>
<tr><td>03/02</td><td>Debit Card Purchase AFFIRMCOM PAYMENTS</td><td></td><td>$26.10</td><td>$1,143.29</td></tr>
<tr><td>03/09</td><td>TRANSFER DEPOSIT From ....2395</td><td></td><td>$150.00</td><td>$1,293.29</td></tr>
<tr><td>03/24</td><td>DEBIT CARD MONEY RECEIVED SQ ID6IGNYR2</td><td></td><td>$700.90</td><td>$1,994.19</td></tr>
<tr><td>03/24</td><td>TRANSFER WITHDRAWAL To ....2395</td><td></td><td>$1,127.81</td><td>$866.38</td></tr>
</table>
"""
    stmt = parse_capital_one_statement(md)
    assert stmt is not None
    assert stmt.account_number == "00005733890536"
    assert stmt.stated_total_credits == 9230.78
    assert stmt.stated_total_debits == 8968.79
    assert stmt.stated_service_charge == 15.0
    assert [t.amount for t in stmt.transactions] == [550.0, -26.1, 150.0, 700.9, -1127.81]
    recon = reconcile(stmt)
    assert recon.sum_delta == 0.0
    assert recon.continuity_breaks == 0


def test_parse_capital_one_native_text_uses_resulting_balances():
    md = """
AN IMPORTANT MESSAGE TO OUR CLIENTS
Capital One
ACCOUNT SUMMARY      FOR PERIOD
MARCH 01, 2054  -  MARCH 31, 2054
Previous Balance  02/28/54 $619.39 Number of Days in Cycle 31 2 Deposits/Credits $700.00 Minimum Balance This Cycle ($20.71) 2 Checks/Debits ($695.00) Average Collected Balance $194.39 Service Charges ($5.00) Ending Balance 03/31/54 $619.39
ACCOUNT DETAIL    FOR PERIOD  MARCH 01, 2054  -  MARCH 31, 2054
Date Description Deposits/Credits Withdrawals/Debits Resulting Balance 03/02 TRANSFER DEPOSIT From ....2395 UTIDMMFTMUDBOSKEAU0
$550.00 $1,169.39
03/02 ACH Withdrawal AMEX EPAYMENT ACH PMT
$550.00 $619.39
03/09 TRANSFER DEPOSIT From ....2395 UTIDMM02U8G727CPLXZ
$150.00 $769.39
03/31 Maintenance charge $5.00 $764.39
03/31 ACH Withdrawal Vendor
$130.00 $634.39
03/31 ACH Withdrawal Vendor
$15.00 $619.39
Total $700.00 $700.00
Total For This Period Total Year-to-Date
"""
    stmt = parse_capital_one_statement(md)
    assert stmt is not None
    assert stmt.beginning_balance == 619.39
    assert stmt.ending_balance == 619.39
    assert stmt.stated_total_credits == 700.0
    assert stmt.stated_total_debits == 695.0
    assert stmt.stated_service_charge == 5.0
    assert stmt.stated_average_balance == 194.39
    assert [t.amount for t in stmt.transactions] == [550.0, -550.0, 150.0, -5.0, -130.0, -15.0]
    assert reconcile(stmt).ok


@pytest.mark.parametrize(
    ("filename", "expected_adb", "printed_date"),
    [
        ("018_capital one february 2026.md", 986.45, "2026-02-28"),
        ("020_capital one may 2026.md", 311.37, "2026-05-31"),
    ],
)
def test_capital_one_short_cycle_charge_is_normalized_to_cycle_end(
    filename, expected_adb, printed_date
):
    stmt = parse_capital_one_statement(_artifact_markdown(filename))
    assert stmt is not None
    assert all(stmt.period_start <= txn.date <= stmt.period_end for txn in stmt.transactions)
    charge = next(txn for txn in stmt.transactions if txn.description.startswith("Maintenance charge"))
    assert charge.date == stmt.period_end
    assert f"printed {printed_date}" in charge.description
    assert compute_metrics(stmt).average_daily_balance == expected_adb


def test_parse_chase_sections_and_infers_single_missing_section_amount():
    md = """
*start*summary
CHASE
JPMorgan Chase Bank, N.A.
April 29, 2051 through May 31, 2051
Account Number: 000000700000031
CHECKING SUMMARY
Chase Business Complete Checking
<table><tr><td></td><td>INSTANCES</td><td>AMOUNT</td></tr><tr><td>Beginning Balance</td><td></td><td>$100.00</td></tr><tr><td>Deposits and Additions</td><td>2</td><td>300.00</td></tr><tr><td>ATM &amp; Debit Card Withdrawals</td><td>2</td><td>-80.00</td></tr><tr><td>Electronic Withdrawals</td><td>1</td><td>-25.00</td></tr><tr><td>Fees</td><td>1</td><td>-15.00</td></tr><tr><td>Ending Balance</td><td>6</td><td>$280.00</td></tr></table>
DEPOSITS AND ADDITIONS
<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr><tr><td>05/01</td><td>Payment Received</td><td>$100.00</td></tr><tr><td>05/02</td><td>Remote Online Deposit 1</td><td>200.00</td></tr><tr><td colspan="2">Total Deposits and Additions</td><td>$300.00</td></tr></table>
ATM & DEBIT CARD WITHDRAWALS
<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr><tr><td>05/03</td><td>Card Purchase</td><td>Store NY Card 8651</td></tr><tr><td>05/04</td><td>Card Purchase</td><td>Gas Station NY Card 8651</td><td>50.00</td></tr><tr><td colspan="2">Total ATM &amp; Debit Card Withdrawals</td><td>$80.00</td></tr></table>
ELECTRONIC WITHDRAWALS
<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr><tr><td>05/05</td><td>Zelle Payment To My Normal Bank</td><td>25.00</td></tr><tr><td colspan="2">Total Electronic Withdrawals</td><td>$25.00</td></tr></table>
FEES
<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr><tr><td>05/31</td><td>Monthly Service Fee</td><td>$15.00</td></tr><tr><td colspan="2">Total Fees</td><td>$15.00</td></tr></table>
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert stmt.bank == "Chase"
    # An INVENTED id, and the shape is the assertion: fifteen characters with
    # six leading zeros, read as a string. The reader must lift the printed
    # `Account Number:` value verbatim — not int() it, not strip the padding,
    # not take the first token of the line — and only a zero-padded id can say
    # so. The number this replaces was a real one, printed by a document of the
    # pinned corpus and carried here since the fixture was written in July;
    # `fixpriv_invent` reports the replacement CLEAR against all 208,695 digit
    # runs of the 3,351-document universe.
    assert stmt.account_number == "000000700000031"
    assert stmt.account_name == "Chase Business Complete Checking"
    assert stmt.stated_total_credits == 300.0
    assert stmt.stated_total_debits == 120.0
    assert [t.amount for t in stmt.transactions] == [100.0, 200.0, -50.0, -30.0, -25.0, -15.0]
    assert stmt.transactions[3].description == "Card Purchase Store NY Card 8651"
    assert reconcile(stmt).ok


def test_parse_chase_native_text_sections():
    md = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A.
Account Number: 000000123456789
*start*summary
CHECKING SUMMARY Chase Business Complete Checking
INSTANCES AMOUNT Beginning Balance $1,000.00
Deposits and Additions 2 800.00 ATM & Debit Card Withdrawals 1 -25.00 Electronic Withdrawals 1 -300.00 Other Withdrawals 1 -100.00 Fees 1 -15.00 Ending Balance 6 $1,360.00
*end*summary
*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT 01/02 Deposit 500.00 01/03 Zelle Payment From Client 300.00
Total Deposits and Additions $800.00
*end*deposits and additions
*start*atmdebitwithdrawal
ATM & DEBIT CARD WITHDRAWALS
DATE DESCRIPTION AMOUNT 01/04 Card Purchase 01/03 Vendor NY Card 1111 $25.00
Total ATM & Debit Card Withdrawals $25.00
*end*atmdebit withdrawal
*start*electronicwithdrawal
ELECTRONIC WITHDRAWALS
DATE DESCRIPTION AMOUNT 01/05 Orig CO Name:Capital One Orig ID:123 Desc Date: CO Entry
$300.00
Descr:Mobile Pmtsec:CCD Trace#:021000024404424
Total Electronic Withdrawals $300.00
*end*electronicwithdrawal
*start*otherwithdrawals
OTHER WITHDRAWALS
DATE DESCRIPTION AMOUNT 01/06 01/06 Withdrawal $100.00
Total Other Withdrawals $100.00
*end*otherwithdrawals
*start*fees section
FEES
DATE DESCRIPTION AMOUNT 01/31 Monthly Service Fee $15.00
Total Fees $15.00
*end*fees section
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert stmt.account_number == "000000123456789"
    assert stmt.stated_total_credits == 800.0
    assert stmt.stated_total_debits == 440.0
    assert [t.amount for t in stmt.transactions] == [500.0, 300.0, -25.0, -300.0, -100.0, -15.0]
    assert reconcile(stmt).ok


def test_parse_chase_native_checks_with_skipped_check_marker_before_caret():
    md = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A.
Account Number: 000000123456789
*start*summary
CHECKING SUMMARY Chase Business Complete Checking
INSTANCES AMOUNT Beginning Balance $2,000.00
Deposits and Additions 0 0.00 Checks Paid 2 -1,172.09 ATM & Debit Card Withdrawals 0 -0.00 Electronic Withdrawals 0 -0.00 Other Withdrawals 0 -0.00 Fees 0 -0.00 Ending Balance 2 $827.91
*end*summary
*start*checks paid section3
CHECKS PAID
DATE
AMOUNT
CHECK NO. DESCRIPTION
PAID
1027 ^ 01/12 $895.04
1029 * ^ 01/12 277.05
Total Checks Paid $1,172.09
*end*checks paid section3
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [-895.04, -277.05]
    assert reconcile(stmt).ok


def test_parse_chase_native_online_transfer_rows_do_not_merge_with_previous_row():
    md = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A.
Account Number: 000000123456789
*start*summary
CHECKING SUMMARY Chase Business Complete Checking
INSTANCES AMOUNT Beginning Balance $100.00
Deposits and Additions 2 2,840.00 Checks Paid 0 -0.00 ATM & Debit Card Withdrawals 0 -0.00 Electronic Withdrawals 1 -40.00 Other Withdrawals 0 -0.00 Fees 0 -0.00 Ending Balance 3 $2,900.00
*end*summary
*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/04 Remote Online Deposit 1 $40.00
01/04 Online Transfer From Chk ...2219 Transaction#: 29073236136 2,800.00
Total Deposits and Additions $2,840.00
*end*deposits and additions
*start*electronic withdrawal
ELECTRONIC WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/05 01/05 Online Transfer To Chk ...2219 Transaction#: 29036510079 40.00
Total Electronic Withdrawals $40.00
*end*electronic withdrawal
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [40.0, 2800.0, -40.0]
    assert reconcile(stmt).ok


def test_parse_chase_native_real_time_transfer_recd_splits_from_online_transfer():
    md = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A.
Account Number: 000000123456789
*start*summary
CHECKING SUMMARY Chase Business Complete Checking
INSTANCES AMOUNT Beginning Balance $100.00
Deposits and Additions 2 8,427.93 Checks Paid 0 -0.00 ATM & Debit Card Withdrawals 0 -0.00 Electronic Withdrawals 0 -0.00 Other Withdrawals 0 -0.00 Fees 0 -0.00 Ending Balance 2 $8,527.93
*end*summary
*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/09 Online Transfer From Chk ...2219 Transaction#: 29554480798 2,800.00
01/10 Real Time Transfer Recd From Aba/Contr Bnk-021000021 From: Intuit Payments Inc. Ref:
5,627.93
F0Fabe1C417E4E2681Df Info: Text
Total Deposits and Additions $8,427.93
*end*deposits and additions
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [2800.0, 5627.93]
    assert reconcile(stmt).ok


def test_parse_chase_native_online_payment_splits_from_previous_ach_row():
    md = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A.
Account Number: 000000123456789
*start*summary
CHECKING SUMMARY Chase Business Complete Checking
INSTANCES AMOUNT Beginning Balance $3,000.00
Deposits and Additions 0 0.00 Checks Paid 0 -0.00 ATM & Debit Card Withdrawals 0 -0.00 Electronic Withdrawals 2 -2,479.55 Other Withdrawals 0 -0.00 Fees 0 -0.00 Ending Balance 2 $520.45
*end*summary
*start*electronic withdrawal
ELECTRONIC WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/19 Orig CO Name:Sbfs LLC Orig ID:4271333844 Desc Date:260519 CO Entry
2,140.98
Descr:Vendor Paysec:CCD
01/19 01/19 Online Payment 29280234114 To Als 9336 338.57
Total Electronic Withdrawals $2,479.55
*end*electronic withdrawal
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [-2140.98, -338.57]
    assert reconcile(stmt).ok


def test_parse_chase_native_payment_sent_card_rows_split_from_previous_purchase():
    md = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A.
Account Number: 000000123456789
*start*summary
CHECKING SUMMARY Chase Business Complete Checking
INSTANCES AMOUNT Beginning Balance $1,000.00
Deposits and Additions 0 0.00 Checks Paid 0 -0.00 ATM & Debit Card Withdrawals 2 -410.32 Electronic Withdrawals 0 -0.00 Other Withdrawals 0 -0.00 Fees 0 -0.00 Ending Balance 2 $589.68
*end*summary
*start*atm debit withdrawal
ATM & DEBIT CARD WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/03 Card Purchase 01/03 E-Z*Passny Payment 800-333-8655 NY Card 0298 10.00
01/03 Payment Sent 01/03 Rmtly* C87B1 Remitly.Com WA Card 0298 400.32
Total ATM & Debit Card Withdrawals $410.32
*end*atm debit withdrawal
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [-10.0, -400.32]
    assert reconcile(stmt).ok


def test_parse_chase_native_payment_to_rows_split_from_previous_ach_row():
    md = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A.
Account Number: 000000123456789
*start*summary
CHECKING SUMMARY Chase Business Complete Checking
INSTANCES AMOUNT Beginning Balance $5,000.00
Deposits and Additions 0 0.00 Checks Paid 0 -0.00 ATM & Debit Card Withdrawals 0 -0.00 Electronic Withdrawals 2 -1,243.45 Other Withdrawals 0 -0.00 Fees 0 -0.00 Ending Balance 2 $3,756.55
*end*summary
*start*electronic withdrawal
ELECTRONIC WITHDRAWALS
DATE DESCRIPTION AMOUNT
01/21 Orig CO Name:Home Depot Orig ID:Citictp Desc Date:260120 CO Entry
243.45
Descr:Online Pmtsec:Web
01/21 01/21 Payment To Chase Card Ending IN 3171 1,000.00
Total Electronic Withdrawals $1,243.45
*end*electronic withdrawal
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [-243.45, -1000.0]
    assert reconcile(stmt).ok


def test_parse_chase_native_fee_reversal_splits_from_previous_deposit():
    md = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A.
Account Number: 000000123456789
*start*summary
CHECKING SUMMARY Chase Business Complete Checking
INSTANCES AMOUNT Beginning Balance $100.00
Deposits and Additions 2 8,747.00 Checks Paid 0 -0.00 ATM & Debit Card Withdrawals 0 -0.00 Electronic Withdrawals 0 -0.00 Other Withdrawals 0 -0.00 Fees 0 -0.00 Ending Balance 2 $8,847.00
*end*summary
*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/19 Orig CO Name:Paymentech Orig ID:1020401225 Desc Date:260219 CO Entry
8,645.00
Descr:Deposit Sec:CCD
01/20 Fee Reversal 102.00
Total Deposits and Additions $8,747.00
*end*deposits and additions
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [8645.0, 102.0]
    assert reconcile(stmt).ok


def test_repair_bofa_summary_folds_checks_and_service_fees():
    md = """
Bank of America
Account summary
Beginning balance on February 1, 2054 $6,767.39
# of deposits/credits: 52
Deposits and other credits 35,968.84
# of withdrawals/debits: 154
Withdrawals and other debits -35,626.82
Checks -5,490.40
Service fees -120.43
Ending balance on February 28, 2054 $1,498.58
Total # of checks 10
"""
    stmt = repair_bofa_summary(md, Statement(bank="Bank of America"))
    assert stmt.stated_total_debits == 41237.65
    # The MONEY folds — cheques and fees are printed as their own summary lines
    # and their money is outside `Withdrawals and other debits`. The COUNT does
    # not: `# of withdrawals/debits` already counts every row in the debit
    # column, cheques included, so the raw printed 154 is stored and the
    # printed `Total # of checks 10` is not added to it. This assertion read
    # 164 until BOFA-COUNTS; the mapping was measured wrong on all 107 archive
    # documents that print a cheque count (`analysis/bofa.py`,
    # `_SUMMARY_COUNT_SCOPE`).
    assert stmt.stated_debit_count == 154
    assert reconcile(stmt).summary_ok is True


def test_repair_bofa_summary_preserves_signed_balances():
    md = """
Bank of America
Account summary
Beginning balance on January 1, 2054 -$225.43
# of deposits/credits: 1
Deposits and other credits 260.24
# of withdrawals/debits: 0
Withdrawals and other debits -0.00
Checks -0.00
Service fees -0.00
Ending balance on January 31, 2054 $34.81
"""
    stmt = repair_bofa_summary(md, Statement(bank="Bank of America"))
    assert stmt.beginning_balance == -225.43
    assert stmt.ending_balance == 34.81
    assert reconcile(stmt).summary_ok is True


def test_parse_bofa_native_text_sections():
    md = """
bankofamerica.com
Bank of America, N.A.
Your Business Advantage Fundamentals Banking
for January 1, 2054 to January 31, 2054 Account number: 3252 0847 6098
HK OFFROAD / HK GRILLS INC.
Account summary
Beginning balance on January 1, 2054 -$225.43
# of deposits/credits: 2
Deposits and other credits 300.00
# of withdrawals/debits: 2
Withdrawals and other debits -250.00
# of items-previous cycle¹: 0
Checks -0.00
# of days in cycle: 31
Service fees -15.00
Average ledger balance: $96.99
Ending balance on January 31, 2054 -$190.43
Your checking account
Deposits and other credits Date Description Amount
01/02/54 Deposit one 100.00
01/03/54 ACH CREDIT
200.00
Total deposits and other credits $300.00
Withdrawals and other debits Date Description Amount 01/04/54 Payment one -50.00
01/05/54 ACH DEBIT
-200.00
Total withdrawals and other debits -$250.00
"""
    stmt = parse_bofa_statement(md)
    assert stmt is not None
    assert stmt.account_number == "325208476098"
    assert stmt.beginning_balance == -225.43
    assert stmt.stated_total_credits == 300.0
    assert stmt.stated_total_debits == 265.0
    assert stmt.stated_average_balance == 96.99
    assert [t.amount for t in stmt.transactions] == [100.0, 200.0, -50.0, -200.0]


def test_parse_bofa_native_card_subtotal_does_not_replace_row_amount():
    md = """
bankofamerica.com
Bank of America, N.A.
Your Business Advantage Fundamentals Banking
for February 1, 2054 to February 28, 2054 Account number: 3251 9756 7296
Account summary
Beginning balance on February 1, 2054 $729.80
# of deposits/credits: 1
Deposits and other credits 100.00
# of withdrawals/debits: 2
Withdrawals and other debits -51.00
# of days in cycle: 28
Service fees -16.00
Ending balance on February 28, 2054 $762.80
Your checking account
Deposits and other credits Date Description Amount
02/02/54 Deposit 100.00
Total deposits and other credits $100.00
Withdrawals and other debits Date Description Amount
02/03/54 Zelle payment to Vendor -45.00
02/04/54 CHECKCARD STORE XXXX
-6.00
Subtotal for card account # XXXX XXXX XXXX 2354 -$803.83 Total withdrawals and other debits -$51.00
Service fees Date Transaction description Amount
02/05/54 Monthly Fee Business Adv Fundamentals -16.00
Total service fees -$16.00
"""
    stmt = parse_bofa_statement(md)
    assert stmt is not None
    stmt = repair_bofa_summary(md, stmt)
    assert [t.amount for t in stmt.transactions] == [100.0, -45.0, -6.0, -16.0]
    assert reconcile(stmt).ok


def test_parse_bofa_native_checks_and_service_fees():
    md = """
bankofamerica.com
Bank of America, N.A.
Your Business Advantage Relationship Banking
for November 1, 2053 to November 30, 2053 Account number: 2910 2587 9041
Account summary
Beginning balance on November 1, 2053 $1,000.00
# of deposits/credits: 1
Deposits and other credits 500.00
# of withdrawals/debits: 1
Withdrawals and other debits -100.00
Checks -350.00
Service fees -50.00
Ending balance on November 30, 2053 $1,000.00
Your checking account
Deposits and other credits Date Description Amount
11/03/53 Deposit 500.00
Total deposits and other credits $500.00
Withdrawals and other debits Date Description Amount
11/04/53 ACH Debit -100.00
Total withdrawals and other debits -$100.00
Checks
Date Check # Amount Date Check # Amount
11/05/53 1247 -150.00 11/06/53 1248* -200.00
Total checks -$350.00
Total # of checks 2
Service fees Date Transaction description Amount
11/07/53 Monthly Fee -20.00
11/08/53 Remote Deposit Fee
-30.00
Total service fees -$50.00
"""
    stmt = parse_bofa_statement(md)
    assert stmt is not None
    stmt = repair_bofa_summary(md, stmt)
    assert [t.amount for t in stmt.transactions] == [500.0, -100.0, -150.0, -200.0, -20.0, -30.0]
    assert reconcile(stmt).ok


def test_regions_reads_the_whole_shared_sign_class_and_not_half_of_it():
    """W3 §MGD MGD10 finding 3, closed by differential.

    `regions._money` opened with `value.strip().replace("–", "-")` — half of
    `money.normalize_sign_glyphs`: U+2013 handled, U+2212 missed. A cell whose
    minus the generator set as a true MINUS SIGN lost it twice, because the
    non-ASCII scrub two lines down then deleted the glyph before `parse_money`
    could see it. The reader now consumes the shared helper, so its class is
    the canon's by construction rather than by agreement.

    Regions cannot be proven end to end offline (§WIRING: the pinned statement
    is image-only and its committed artifact is a markdown string), so this is
    a differential against the shared helper plus the unit proof, and the
    archive evidence is stated rather than replayed: all 24 live-detected
    Regions documents print the ASCII hyphen and not one carries U+2212,
    U+2013 or U+2014 anywhere, so nothing in the archive moves.
    """
    for glyph in MINUS_GLYPHS:
        assert regions_money(f"{glyph}250.00") == -250.0
        assert regions_money(f"250.00{glyph}") == -250.0
        assert regions_money(f"{glyph}250.00") == regions_money("-250.00")
    assert regions_money("250.00") == 250.0
    assert regions_money("N/A") is None, "a probe answers None; it does not raise"


@pytest.mark.parametrize("glyph", list(MINUS_GLYPHS))
def test_regions_summary_repair_reads_a_trailing_sign_in_any_glyph(glyph):
    """The native path is the one that runs, and its trailing-sign group was
    ASCII-only too. Same defect, same fix, one class."""
    md = f"""
Regions Bank
SUMMARY
Beginning Balance $7,317.34 Withdrawals $65,850.69 - Ending Balance $595.51 {glyph}
Total Withdrawals $65,850.69
"""
    stmt = repair_regions_summary(md, Statement(bank="Regions Bank"))
    assert stmt.ending_balance == -595.51


def test_repair_regions_summary_handles_returned_checks_and_trailing_minus():
    md = """
Regions Bank
SUMMARY
Beginning Balance $7,317.34 Deposits & Credits $53,689.64 + Withdrawals $65,850.69 - Fees $108.00 - Automatic Transfers $0.00 + Returned Checks $17,142.47 + Checks $12,786.27 - Ending Balance $595.51 -
Total Deposits & Credits $53,689.64
Total Withdrawals $65,850.69
Total Fees $108.00
Total Returned Checks $17,142.47
Total Checks $12,786.27
Average Balance $297
"""
    stmt = repair_regions_summary(md, Statement(bank="Regions Bank"))
    assert stmt.ending_balance == -595.51
    assert stmt.stated_total_credits == 70832.11
    assert stmt.stated_total_debits == 78744.96
    assert stmt.stated_average_balance == 297.0
    assert reconcile(stmt).summary_ok is True


# ---------------------------------------------------------------------------
# Bank-summary repairs are keyed on the claiming registration (HUNT-CELL H6.1)
# ---------------------------------------------------------------------------

#: A statement of another issuer's that PAYS a bill to Regions and prints its
#: own `Service Charge Summary` — which is all the retired substring gate
#: (`"REGIONS" ... "SUMMARY"`) ever required. The figures below are this
#: issuer's own; the repair would overwrite them from the labels it recognises.
_COUNTERPARTY_MARKDOWN = """
The Huntington National Bank
Beginning Balance 1,000.00 Ending Balance 2,000.00
Deposits & Credits 5,000.00 Withdrawals 3,100.00
Checks 900.00
Service Charge Summary
Total Service Charges 25.00
02/14 ONLINE BILL PAY REGIONS BANK CARD PMT 250.00
"""


def _claimed_by(parser_id: str, bank: str):
    """A `Dispatch` in which `parser_id` claimed the document. Built directly
    rather than registered, so the registry the rest of the suite sees is
    untouched."""
    from analysis.parser_registry import Dispatch, Marker, Registration

    registration = Registration(
        id=parser_id, bank=bank, markers=(Marker("m", lambda text: True),),
        parse=lambda markdown: None,
    )
    return Dispatch("claimed", registration=registration)


def test_a_repair_does_not_fire_for_a_bank_named_only_as_a_counterparty():
    """HUNT-CELL H6.1: five Huntington statements that merely pay a bill to
    Regions Bank had their balances and stated totals rewritten by the Regions
    repair, and failed reconciliation. The claiming registration is the gate."""
    # `stated_total_debits` is this issuer's own printed `Debits (-)`. The
    # Regions repair adds `Checks` to `Withdrawals`, which on this paper double
    # counts the cheques — HUNT-CELL measured exactly that substitution.
    original = Statement(
        bank="Huntington National Bank", beginning_balance=1000.0, ending_balance=2000.0,
        stated_total_credits=5000.0, stated_total_debits=3100.0, stated_service_charge=25.0,
    )
    # The retired gate is genuinely satisfied by this document...
    assert "REGIONS" in _COUNTERPARTY_MARKDOWN.upper()
    assert "SUMMARY" in _COUNTERPARTY_MARKDOWN.upper()
    assert repair_regions_summary(_COUNTERPARTY_MARKDOWN, original) != original
    # ...and the claiming registration is what now keeps the repair off it.
    repaired = apply_statement_repairs(
        _COUNTERPARTY_MARKDOWN, original,
        dispatch=_claimed_by("huntington", "Huntington National Bank"),
    )
    for field in ("beginning_balance", "ending_balance", "stated_total_credits",
                  "stated_total_debits", "stated_service_charge"):
        assert getattr(repaired, field) == getattr(original, field), field


def test_a_repair_still_fires_for_the_registration_that_owns_it():
    """The other direction, so the gate cannot be satisfied by switching every
    repair off: the owning parser's claim still applies its repair."""
    markdown = _COUNTERPARTY_MARKDOWN.replace(
        "The Huntington National Bank", "Regions Bank"
    )
    original = Statement(bank="Regions Bank")
    repaired = apply_statement_repairs(
        markdown, original, dispatch=_claimed_by("regions", "Regions Bank")
    )
    assert repaired.beginning_balance == 1000.0
    assert repaired.ending_balance == 2000.0


def test_an_llm_extraction_gets_its_repair_by_bank_label():
    """The R-3 ruling: a document no parser claimed still gets the document
    knowledge of the registration whose bank label the extraction named — that
    is what the pre-R-3 `stmt.bank == ...` literals gave it."""
    from analysis.parser_registry import Dispatch

    markdown = _COUNTERPARTY_MARKDOWN.replace(
        "The Huntington National Bank", "Regions Bank"
    )
    unclaimed = Dispatch("unclaimed")
    named = apply_statement_repairs(
        markdown, Statement(bank="Regions Bank"), dispatch=unclaimed
    )
    assert named.beginning_balance == 1000.0
    # ...and an extraction naming a bank we have no parser for gets nothing.
    unnamed = apply_statement_repairs(
        _COUNTERPARTY_MARKDOWN,
        Statement(bank="Huntington National Bank"),
        dispatch=unclaimed,
    )
    assert unnamed.beginning_balance is None


def test_every_summary_repair_is_keyed_on_a_live_registration():
    """The ids in `_SUMMARY_REPAIRS` are registry keys, so a renamed parser
    would silently switch its repair off. This is what makes that loud."""
    from analysis import parser_registry
    from analysis.pipeline import _SUMMARY_REPAIRS

    assert _SUMMARY_REPAIRS, "the table must not be empty"
    for parser_id in _SUMMARY_REPAIRS:
        assert parser_registry.by_id(parser_id).id == parser_id


def test_parse_regions_native_text_sections():
    md = """
Thank you for banking with Regions!
Regions Bank Homer Georgia
ACCOUNT # 9900001234
ADVANTAGE BUSINESS CHECKING
May 1, 2054 through May 29, 2054
SUMMARY
Beginning Balance $100.00 Deposits & Credits $300.00 + Withdrawals $125.00 - Fees $12.00 - Automatic Transfers $0.00 + Returned Checks $40.00 + Checks $53.00 - Ending Balance $250.00
Minimum Daily Balance $100 Average Monthly Statement Balance $175
DEPOSITS & CREDITS
05/01 Deposit - Thank You 200.00 05/02 Bankcard Dep Merch Dep 100.00
Total Deposits & Credits $300.00
WITHDRAWALS
05/03 Card Purchase Store 25.00 05/04 Kapitus Achpmt Test 100.00
Total Withdrawals $125.00
FEES
05/05 Monthly Fee 12.00
Total Fees $12.00
RETURNED CHECKS
05/06 Credit-Returned Ck#1234 40.00
Total Returned Checks $40.00
CHECKS
Date Check No. Amount 05/07 1033 25.00 05/08 1034 * 28.00
Total Checks $53.00
DAILY BALANCE SUMMARY
"""
    stmt = parse_regions_statement(md)
    assert stmt is not None
    assert stmt.account_number == "9900001234"
    assert stmt.account_name == "ADVANTAGE BUSINESS CHECKING"
    assert stmt.beginning_balance == 100.0
    assert stmt.ending_balance == 250.0
    assert stmt.stated_total_credits == 340.0
    assert stmt.stated_total_debits == 190.0
    assert stmt.stated_average_balance == 175.0
    assert [t.amount for t in stmt.transactions] == [200.0, 100.0, -25.0, -100.0, -12.0, 40.0, -25.0, -28.0]
    assert reconcile(stmt).ok


def _regions_with_page_break(footer: str) -> str:
    """The same statement with its WITHDRAWALS section split by a page break.

    The bank prints its sign-off at the foot of the page, and the flattening
    welds it onto the last row above it (W3 §WITHHELDGRIDS).
    100.00 + 300.00 - 125.00 = 275.00.
    """
    return f"""
Thank you for banking with Regions!
Regions Bank Homer Georgia
ACCOUNT # 9900001234
ADVANTAGE BUSINESS CHECKING
May 1, 2054 through May 29, 2054
SUMMARY
Beginning Balance $100.00 Deposits & Credits $300.00 + Withdrawals $125.00 - Ending Balance $275.00
DEPOSITS & CREDITS
05/01 Deposit - Thank You 200.00 05/02 Bankcard Dep Merch Dep 100.00
Total Deposits & Credits $300.00
WITHDRAWALS
05/03 Card Purchase Store 25.00 05/04 Kapitus Achpmt Test 100.00
{footer}
--- Page 2 ---
WITHDRAWALS (CONTINUED)
Total Withdrawals $125.00
DAILY BALANCE SUMMARY
"""


def test_a_row_welded_to_the_page_sign_off_is_still_read():
    """A row is read by a pattern ANCHORED on the line ending in its amount,
    so a footer flattened onto the last row of a page does not misread that
    row — it deletes it, and the ledger then misses the printed
    `Total Withdrawals` by exactly one row and cannot close."""
    stmt = parse_regions_statement(
        _regions_with_page_break("Thank You For Banking With Regions!\n2026 Regions Bank Member FDIC.")
    )
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [200.0, 100.0, -25.0, -100.0]
    assert reconcile(stmt).ok


def test_the_sign_off_is_cut_from_the_row_and_not_from_the_document():
    """The ablation. With no footer printed in that position the same
    statement reads identically, so the trailer is cutting furniture off a
    row rather than changing how rows are found."""
    without = parse_regions_statement(_regions_with_page_break(""))
    with_footer = parse_regions_statement(
        _regions_with_page_break("Thank You For Banking With Regions!\n2026 Regions Bank Member FDIC.")
    )
    assert without is not None and with_footer is not None
    assert [t.amount for t in without.transactions] == [
        t.amount for t in with_footer.transactions
    ]
    assert [t.description for t in without.transactions] == [
        t.description for t in with_footer.transactions
    ]


def test_parse_pnc_native_text_sections():
    md = """
PNC Bank
For the Period 05/01/2054 to 05/29/2054 Primary Account Number: XX-XXXX-5985
JONED TRANSPORT CO. Business Checking Summary Account number:   XX-XXXX-5985
Balance Summary
Ending balance 100.00 300.00 125.00 275.00
Beginning
Deposits and other additions
Checks and other
balance
deductions
Average ledger
Average collected
balance 175.00 175.00
balance
Overdraft and Returned Item Fee Summary
Total for this Period Total Year to Date
Total Returned Item Fees (NSF) 36.00 72.00
Activity Detail
Deposits and Other Additions
ACH Additions
Date posted Amount
Transaction description
Reference
number 05/02 200.00 Corporate ACH Payments Client 0001 05/03 100.00 Corporate ACH Deposit Client 0002
Checks and Other Deductions
Debit Card Purchases
Date posted Amount
Transaction description
Reference
number 05/04 25.00 3975 Debit Card Purchase Store 12345
ACH Deductions
Date posted Amount
Transaction description
Reference
number 05/05 64.00 ACH Debit Vendor 987
Service Charges and Fees
Date posted Amount
Transaction description
Reference
number 05/06 36.00 Returned Item Fee (nsf) 0001
Detail of Services Used During Current Period
"""
    stmt = parse_pnc_statement(md)
    assert stmt is not None
    assert stmt.account_number == "XX-XXXX-5985"
    assert stmt.beginning_balance == 100.0
    assert stmt.ending_balance == 275.0
    assert stmt.stated_total_credits == 300.0
    assert stmt.stated_total_debits == 125.0
    assert stmt.stated_average_balance == 175.0


def test_parse_citizens_native_text_sections():
    md = """
    Commercial Account
    Statement
    Beginning April 01, 2054 through April 30, 2054
    citizensbank.com
    Business Advisor Checking
    XXXXXX-877-4
    Business Advisor Checking for XXXXXX-877-4
    Balance Calculation Previous Balance -2,197.06 Checks - .00 Debits - 105.00 Deposits & Credit + 300.00 Current Balance = -2,002.06
    Your average daily checking balance used to qualify this statement period is: $822
    TRANSACTION DETAILS FOR BUSINESS CHECKING ACCOUNT ENDING 877-4
    Debits
    Date Amount Description
    Other Debits
    04/01 35.00 RETURNED ITEM FEE ( 1 AT $35 ) 04/02 70.00 RETURNED ITEM FEE ( 2 AT $35 EACH )
    Deposits & Credits
    Total Deposits & Credits
    + 300.00
    Date Amount Description
    04/03 100.00 MOBILE DEPOSIT 04/04 200.00 ONLINE TRANSFER FROM CHECKING 4003819283
    Current Balance
    Daily Balance
    = -2,002.06
    """
    report = analyze_markdown(md, parse_mode="deterministic")
    stmt = report.statement
    assert report.model_used == "citizens-bank-deterministic"
    assert report.quality.corporate_use == "approved"
    assert stmt.bank == "Citizens Bank"
    assert stmt.period_start == "2054-04-01"
    assert stmt.period_end == "2054-04-30"
    assert stmt.account_number == "XXXXXX-877-4"
    assert stmt.stated_average_balance == 822.0
    assert stmt.stated_total_credits == 300.0
    assert stmt.stated_total_debits == 105.0
    assert report.metrics.nsf_count == 2                 # two returned items, reported apart
    assert report.metrics.negative_days == 30             # carry-over basis: every April day ends overdrawn
    assert report.metrics.effective_nsf_count == 4        # printed basis (default): the four posting days
    assert stmt.stated_nsf_count is None
    assert [t.amount for t in stmt.transactions] == [-35.0, -70.0, 100.0, 200.0]
    assert reconcile(stmt).ok


def test_parse_amex_business_checking_native_text():
    md = """
    Business Checking Account Statement
    Statement Date: 04/30/2054 Account Ending: *1056 Account Name: PSCBATH
    Statement Summary
    Beginning Balance as of 04/01/2054 $100.00
    Earned Period 04/01/2054 - 04/30/2054
    Total Credits This Period $75.00
    Days in Statement Period 30
    Total Debits This Period -$50.00
    Ending Balance as of 04/30/2054 $125.00
    Account Activity
    Date Description Credits Debits Balance
    04/01/2054 Beginning Balance $100.00
    04/02/2054 Online Transfer / Payment: Debit
    -$50.00 $50.00
    VENDOR PAYMENT
    ID 009
    04/03/2054 Wire Transfer Domestic Incoming
    $75.00 $125.00
    ID 010
    04/30/2054 Ending Balance $125.00
    americanexpress.com/businesscheckinghome
    """
    report = analyze_markdown(md, parse_mode="deterministic")
    stmt = report.statement
    assert report.model_used == "american-express-deterministic"
    assert report.quality.corporate_use == "approved"
    assert stmt.bank == "American Express"
    assert stmt.account_number == "*1056"
    assert stmt.days_in_period == 30
    assert stmt.stated_total_credits == 75.0
    assert stmt.stated_total_debits == 50.0
    assert [t.running_balance for t in stmt.transactions] == [50.0, 125.0]
    assert reconcile(stmt).ok


def test_repair_first_community_removes_balance_neutral_failed_efts():
    stmt = Statement(
        bank="First Community",
        beginning_balance=100.0,
        ending_balance=150.0,
        stated_total_credits=100.0,
        stated_total_debits=250.0,
        transactions=[
            _txn("2053-10-01", 100.0, "DIRECT DEPOSIT", bal=200.0),
            _txn("2053-10-02", -200.0, "EFT - FAILED ATTEMPT", bal=200.0),
            _txn("2053-10-03", -50.0, "POS - PURCHASE", bal=150.0),
        ],
    )
    repaired = repair_first_community_posted_activity(stmt)
    assert [t.description for t in repaired.transactions] == ["DIRECT DEPOSIT", "POS - PURCHASE"]
    assert repaired.stated_total_debits == 50.0
    assert reconcile(repaired).ok


def test_parse_first_community_business_plus_spaced_minus_debits():
    md = """
STATEMENT ENDING 10/31/2053
Online Access: www.firstcommunity.com
SUMMARY OF ACCOUNTS
BUSINESS PLUS CKG 946887429-70 $1,641.37
BUSINESS PLUS CKG-946887429-70
ACCOUNT SUMMARY
DATE DESCRIPTION AMOUNT 10/01 Beginning Balance $301.73
DESCRIPTION AMOUNT Dividends Earned From 10/01 Through 10/31
2 Credits This Period $20,083.34
Annual Percentage Yield Earned 0.096%
4 Debits This Period $32,951.70
Dividend Days 31
10/31 Ending Balance $1,641.37
Dividends Earned $0.10
ACCOUNT ACTIVITY
POST DATE DESCRIPTION DEBITS CREDITS BALANCE
10/01 Beginning Balance $301.73
10/08 DIRECT DEPOSIT - STRIPE - TRANSFER 5,875.34 6,177.07
10/08 EFT - PUSHPAY USA INC - 0341391 - SOFTWARE - 14,208.00 6,177.07
10/08 NSF FEE - PUSHPAY USA INC - 0341391 - SOFTWARE -27.50 6,149.57
10/16 DIRECT DEPOSIT - STRIPE - TRANSFER 14,208.00 20,357.57
10/16 ATM SH TO SH TRANSFER - 10/16/2053 09 363958 TFR TO SHARES #######10-70 - 18,700.00 1,657.57
10/31 COMMERCIAL -16.20 1,641.37
10/31 Ending Balance $1,641.37
OVERDRAFT AND RETURNED ITEM FEES
ACCOUNT ANALYSIS STATEMENT
ACCOUNT SUMMARY
Service Class BPCK-BUSINESS PLUS CHKG Average Daily Balance $1,233.51
ANALYSIS SUMMARY
Accumulated Fees $16.20 $16.20 will be charged to the account on 10/31/2053.
"""
    stmt = parse_first_community_statement(md)
    assert stmt is not None
    assert [t.amount for t in stmt.transactions] == [5875.34, -14208.0, -27.5, 14208.0, -18700.0, -16.2]
    repaired = repair_first_community_posted_activity(normalize_statement(stmt))
    assert [t.amount for t in repaired.transactions] == [5875.34, -27.5, 14208.0, -18700.0, -16.2]
    assert reconcile(repaired).ok
    # The printed claim is `4 Debits This Period $32,951.70`; one balance-neutral
    # EFT is dropped, so both halves narrow together.
    assert repaired.stated_debit_count == 3
    assert repaired.stated_total_debits == 18743.70
    assert repaired.stated_credit_count == 2


def test_repair_first_community_narrows_the_debit_count_with_the_debit_total():
    """The count-scope alignment (D5 `semantics_difference`): the repair drops N
    printed balance-neutral rows, so the bank's whole-direction debit COUNT has
    to narrow by the same N that its debit TOTAL narrows by.

    The shape is the pinned corpus document's (`7429_Statement_October_2025`):
    `202 Debits This Period`, seven balance-neutral failed EFTs dropped, 195
    debit rows left. Scaled here to the same arithmetic on a fixture.
    """
    txns = [_txn("2053-10-01", 100.0, "DIRECT DEPOSIT", bal=200.0)]
    # seven balance-neutral failed EFT attempts, then one real posted debit
    for i in range(7):
        txns.append(_txn(f"2025-10-0{i + 2}", -10.0, "EFT - FAILED ATTEMPT", bal=200.0))
    txns.append(_txn("2053-10-09", -50.0, "POS - PURCHASE", bal=150.0))

    stmt = Statement(
        bank="First Community",
        beginning_balance=100.0,
        ending_balance=150.0,
        stated_total_credits=100.0,
        stated_total_debits=120.0,
        stated_credit_count=1,
        stated_debit_count=202,
        transactions=txns,
    )
    repaired = repair_first_community_posted_activity(stmt)

    assert len(stmt.transactions) - len(repaired.transactions) == 7
    assert repaired.stated_debit_count == 195, "202 printed debits minus the 7 dropped rows"
    assert repaired.stated_total_debits == 50.0, "the paired total rewrite is unchanged"
    assert repaired.stated_credit_count == 1, "the credit direction is untouched"
    assert reconcile(repaired).ok


def test_repair_first_community_leaves_counts_alone_when_nothing_is_dropped():
    """A First Community document with no balance-neutral failed EFT keeps the
    bank's printed counts and totals exactly as printed."""
    stmt = Statement(
        bank="First Community",
        beginning_balance=100.0,
        ending_balance=150.0,
        stated_total_credits=100.0,
        stated_total_debits=50.0,
        stated_credit_count=1,
        stated_debit_count=1,
        transactions=[
            _txn("2053-10-01", 100.0, "DIRECT DEPOSIT", bal=200.0),
            _txn("2053-10-02", -50.0, "POS - PURCHASE", bal=150.0),
        ],
    )
    repaired = repair_first_community_posted_activity(stmt)
    assert repaired is stmt
    assert repaired.stated_debit_count == 1
    assert repaired.stated_total_debits == 50.0


def test_repair_first_community_never_rewrites_the_count_without_the_total():
    """The guard: the two halves of `N Debits This Period $X` move as a pair.

    A count with no total beside it is not narrowed on its own — a rewritten
    count paired with an as-printed total would describe two different sets of
    rows, which is the very inconsistency this fix exists to remove.
    """
    def _statement(**summary) -> Statement:
        return Statement(
            bank="First Community",
            beginning_balance=100.0,
            ending_balance=150.0,
            transactions=[
                _txn("2053-10-01", 100.0, "DIRECT DEPOSIT", bal=200.0),
                _txn("2053-10-02", -200.0, "EFT - FAILED ATTEMPT", bal=200.0),
                _txn("2053-10-03", -50.0, "POS - PURCHASE", bal=150.0),
            ],
            **summary,
        )

    # count printed, total absent -> the count is NOT narrowed
    count_only = repair_first_community_posted_activity(_statement(stated_debit_count=4))
    assert len(count_only.transactions) == 2, "the row drop itself still happens"
    assert count_only.stated_debit_count == 4
    assert count_only.stated_total_debits is None

    # total printed, count absent -> the total is narrowed, and no count is
    # invented for a document that never printed one
    total_only = repair_first_community_posted_activity(_statement(stated_total_debits=250.0))
    assert total_only.stated_total_debits == 50.0
    assert total_only.stated_debit_count is None

    # both printed -> both narrow, by the same one dropped row
    both = repair_first_community_posted_activity(
        _statement(stated_total_debits=250.0, stated_debit_count=4)
    )
    assert both.stated_total_debits == 50.0
    assert both.stated_debit_count == 3


def test_analysis_marks_incomplete_detail_as_manual_review(monkeypatch):
    def fake_extract(*args, **kwargs):
        return Statement(
            bank="BMO",
            account_name="Example",
            beginning_balance=100.0,
            ending_balance=250.0,
            stated_total_credits=200.0,
            stated_total_debits=50.0,
            transactions=[_txn("2054-01-01", 100.0)],
        )

    monkeypatch.setattr("analysis.pipeline.extract_statement", fake_extract)
    # P22-FENCE (Ruling A in code): this test exercises the HOSTED branch on a
    # fake extractor, and that branch runs only behind the operator's exact
    # opt-in literal; without it auto mode takes the deterministic refusal.
    monkeypatch.setenv(HOSTED_EXTRACTION_OPT_IN_ENV, HOSTED_EXTRACTION_OPT_IN_LITERAL)
    report = analyze_markdown("BMO Account Summary")
    assert not report.reconciliation.ok
    assert report.reconciliation.summary_ok is True
    assert report.quality.level == "needs_review"
    assert report.quality.corporate_use == "manual_review_required"
    assert report.quality.transaction_detail_reliable is False
    assert not any("UNCAPTURED" in t.description for t in report.statement.transactions)


def test_chase_business_transaction_export_reconciles_but_requires_review():
    md = """
CHASE & for BUSINESS
Printed from Chase for Business
BUS COMPLETE CHK (...7350)
BUS COMPLETE CHK (...7350)
SEA WONDERS LLC
Transactions
Date Description Type Amount Balance
May 14, 2054 ORIG CO ACH credit $20.00 $115.00
May 13, 2054 SAMPLE Card -$5.00 $95.00
Apr 30 (...2896)
Apr 13,2054 REMOTE ONLINE Deposit $100.00 $100.00
JPMorgan Chase Bank, N.A. Member FDIC
"""
    report = analyze_markdown(md, parse_mode="deterministic")
    assert report.statement.bank == "Chase Transaction Export"
    assert report.statement.account_name == "SEA WONDERS LLC"
    assert report.statement.beginning_balance == 0.0
    assert report.statement.ending_balance == 115.0
    assert report.statement.period_start == "2054-04-13"
    assert report.reconciliation.ok
    assert report.metrics.adb is not None
    assert report.metrics.adb.validations["posting_dates_cover_source"] is True
    assert report.quality.corporate_use == "manual_review_required"
    assert "not_a_formal_statement" in report.integrity.flags


def _chase_export_markdown(minus: str) -> str:
    """The same export, printing its debit sign with `minus`."""
    return f"""
CHASE & for BUSINESS
Printed from Chase for Business
BUS COMPLETE CHK (...7350)
BUS COMPLETE CHK (...7350)
SEA WONDERS LLC
Transactions
Date Description Type Amount Balance
May 14, 2054 ORIG CO ACH credit $20.00 $115.00
May 13, 2054 SAMPLE Card {minus}$5.00 $95.00
Apr 13,2054 REMOTE ONLINE Deposit $100.00 $100.00
JPMorgan Chase Bank, N.A. Member FDIC
"""


@pytest.mark.parametrize("minus", ["-", "−", "–"], ids=["ascii", "u2212", "u2013"])
def test_chase_export_reads_every_spelling_of_the_minus_it_prints(minus):
    """W3 §MONEY-GRAMMAR card 1. The web export prints U+2212; while the row
    finder knew only ASCII it matched from the `$` onwards, dropped the sign,
    and booked the debit as a CREDIT — the balance walk then failed and the
    document withheld. The three spellings must parse identically."""
    report = analyze_markdown(_chase_export_markdown(minus), parse_mode="deterministic")
    card = [t for t in report.statement.transactions if t.description == "SAMPLE Card"]
    assert len(card) == 1
    assert card[0].amount == -5.0
    assert card[0].direction == "debit"
    assert report.statement.ending_balance == 115.0
    assert report.reconciliation.ok


def _chase_export_with_wrapped_type_cell(type_cell: str) -> str:
    """An export whose long `type_cell` wrapped onto a line of its own.

    The amount pair is then alone on the next physical line, exactly as the
    archive prints it on all three chase_export documents.
    """
    return f"""
CHASE & for BUSINESS
Printed from Chase for Business
BUS COMPLETE CHK (...7350)
BUS COMPLETE CHK (...7350)
SEA WONDERS LLC
Transactions
Date Description Type Amount Balance
May 14, 2054 BOOK TRANSFER CREDIT B/O: ACME LLC TRN: 3426966198ES
{type_cell}
$20,000.00 $20,095.00
May 13, 2054 SAMPLE Card −$5.00 $95.00
Apr 13,2054 REMOTE ONLINE Deposit $100.00 $100.00
JPMorgan Chase Bank, N.A. Member FDIC
"""


def test_chase_export_recovers_a_row_whose_type_cell_wrapped_onto_its_own_line():
    """W3 §MG-C1. A long type cell does not fit beside the amounts and wraps,
    leaving the amount pair with no text in front of it. `if not description`
    then dropped the whole transaction — silently, from a ledger the platform
    goes on to reconcile against a printed balance.

    Measured on the base tree this fixture kept 2 rows with the $20,000.00
    wire missing, which is below the parser's 3-row floor, so it returned None
    and the document died with `RuntimeError: no deterministic parser matched
    this statement`. It is the same shape W3 §MG7 measured on the archive as
    `sum check off by -20000.00`.
    """
    report = analyze_markdown(
        _chase_export_with_wrapped_type_cell("Incoming wire transfer"),
        parse_mode="deterministic",
    )
    wires = [t for t in report.statement.transactions if t.description == "Incoming wire transfer"]
    assert len(wires) == 1
    assert wires[0].amount == 20000.0
    assert wires[0].direction == "credit"
    assert wires[0].date == "2054-05-14"
    assert wires[0].running_balance == 20095.0
    assert len(report.statement.transactions) == 3
    assert report.statement.ending_balance == 20095.0
    assert report.reconciliation.ok


@pytest.mark.parametrize(
    "type_cell",
    ["Incoming wire transfer", "Outgoing wire transfer", "ACH vendor payment", "Zelle payment sent"],
)
def test_chase_export_wrapped_recovery_is_shape_based_not_a_list_of_type_strings(type_cell):
    """Only three type cells are long enough to wrap in today's archive, and
    hardcoding those three would be a statement-specific constant that the
    next long cell defeats. The rule is structural — the last text-only line —
    so a type cell nobody has surveyed recovers identically."""
    report = analyze_markdown(
        _chase_export_with_wrapped_type_cell(type_cell), parse_mode="deterministic"
    )
    rows = [t for t in report.statement.transactions if t.description == type_cell]
    assert len(rows) == 1
    assert rows[0].amount == 20000.0
    assert report.reconciliation.ok


def test_chase_export_a_pending_row_never_lends_its_type_to_the_row_below():
    """The carry is consumed by any line that carries an amount, complete row
    or pending one. A pending row (`−$43.00 —`, no balance) is a row in its
    own right that already used the type cell above it, so the amount-only
    line beneath must NOT inherit it and invent a labelled transaction. It
    stays dropped: fail-closed beats a borrowed description."""
    md = """
CHASE & for BUSINESS
Printed from Chase for Business
BUS COMPLETE CHK (...7350)
BUS COMPLETE CHK (...7350)
SEA WONDERS LLC
Transactions
Date Description Type Amount Balance
May 15, 2054 POS DEBIT FRESHBOOKS 866-303-6061 DE 0019 (...5129)
Outgoing wire transfer
−$50.00 —
$100.00 $200.00
May 14, 2054 ANOTHER Card −$10.00 $85.00
May 13, 2054 SAMPLE Card −$5.00 $95.00
Apr 13,2054 REMOTE ONLINE Deposit $100.00 $100.00
JPMorgan Chase Bank, N.A. Member FDIC
"""
    report = analyze_markdown(md, parse_mode="deterministic")
    descriptions = [t.description for t in report.statement.transactions]
    assert "Outgoing wire transfer" not in descriptions
    assert descriptions == ["REMOTE ONLINE Deposit", "SAMPLE Card", "ANOTHER Card"]


#: W3 §MG-C1 anchoring. `head` is spliced in above three rows that always
#: parse, so every fixture below differs ONLY in what sits between the type
#: cell and the amount pair. Recovered, the ledger is
#: 0 -> 100 -> 95 -> 85 -> 20,085; dropped, it is 0 -> 100 -> 95 -> 85.
def _chase_export_anchoring(head: str) -> str:
    return f"""
CHASE & for BUSINESS
Printed from Chase for Business
BUS COMPLETE CHK (...7350)
BUS COMPLETE CHK (...7350)
SEA WONDERS LLC
Transactions
Date Description Type Amount Balance
{head}
May 14, 2054 ANOTHER Card −$10.00 $85.00
May 13, 2054 SAMPLE Card −$5.00 $95.00
Apr 13,2054 REMOTE ONLINE Deposit $100.00 $100.00
JPMorgan Chase Bank, N.A. Member FDIC
"""


def _descriptions(md: str) -> list[str]:
    return [t.description for t in analyze_markdown(md, parse_mode="deterministic").statement.transactions]


#: The attested shape: descriptive text, then the type cell, then the amounts.
GENUINE_WRAP = """May 15, 2054 BOOK TRANSFER CREDIT B/O: ACME LLC TRN: 3426966198ES
Incoming wire transfer
$20,000.00 $20,085.00"""


def test_chase_export_carry_is_the_last_text_line_and_never_an_accumulation():
    """SINGLE. Every genuine wrap in the archive is preceded by TWO or more
    text-only lines (measured: 2 x10, 5 x2, 6 x2 — never one), because the
    export prints the row's descriptive text above its type cell and, across a
    page break, its header furniture too. So the carry must be last-one-wins:
    the earlier lines are neither concatenated into the description nor
    retained once the type cell arrives."""
    descriptions = _descriptions(_chase_export_anchoring(GENUINE_WRAP))
    assert "Incoming wire transfer" in descriptions
    assert not any("BOOK TRANSFER" in d for d in descriptions)
    assert not any("ACME" in d for d in descriptions)
    report = analyze_markdown(_chase_export_anchoring(GENUINE_WRAP), parse_mode="deterministic")
    assert len(report.statement.transactions) == 4
    assert report.statement.ending_balance == 20085.0
    assert report.reconciliation.ok


@pytest.mark.parametrize(
    "intervening, why",
    [
        ("--- Page 2 ---", "a page separator"),
        ("Pending authorization", "a pending row"),
        ("Misc. debit −$43.00 —", "a row carrying an amount of its own"),
    ],
)
def test_chase_export_anything_between_the_type_cell_and_the_amounts_kills_the_carry(intervening, why):
    """ADJACENCY. In all 14 attested wraps the type cell is IMMEDIATELY before
    the amount pair. Anything else in between means this is not that shape, and
    guessing would attach a real amount to a description it never had."""
    head = GENUINE_WRAP.replace("\n$20,000.00", f"\n{intervening}\n$20,000.00")
    descriptions = _descriptions(_chase_export_anchoring(head))
    assert "Incoming wire transfer" not in descriptions, why
    assert descriptions == ["REMOTE ONLINE Deposit", "SAMPLE Card", "ANOTHER Card"]


def test_chase_export_a_carry_never_crosses_a_date_boundary():
    """SAME DATE. A row's type cell belongs to that row's date. Here the amount
    pair posts under May 14 while the carry was set under May 15, so the carry
    is refused rather than describing a transaction on the wrong day."""
    head = """May 15, 2054 BOOK TRANSFER CREDIT B/O: ACME LLC TRN: 3426966198ES
Outgoing wire transfer
May 12, 2054 $20,000.00 $20,085.00"""
    descriptions = _descriptions(_chase_export_anchoring(head))
    assert "Outgoing wire transfer" not in descriptions
    assert descriptions == ["REMOTE ONLINE Deposit", "SAMPLE Card", "ANOTHER Card"]


def test_chase_export_a_dangling_carry_at_the_end_is_discarded():
    """CONSUMED. A type cell with no amount pair after it describes nothing.
    It must not survive to be applied to whatever the next section prints."""
    md = _chase_export_anchoring(GENUINE_WRAP).replace(
        "JPMorgan Chase Bank, N.A. Member FDIC",
        "Outgoing wire transfer\nJPMorgan Chase Bank, N.A. Member FDIC",
    )
    descriptions = _descriptions(md)
    assert "Outgoing wire transfer" not in descriptions
    assert descriptions == ["REMOTE ONLINE Deposit", "SAMPLE Card", "ANOTHER Card", "Incoming wire transfer"]


def test_southside_scanned_statement_reconciles_with_daily_balances():
    md = """
SOUTHSIDE STATEMENT OF ACCOUNT
THE GRANITE GIRLS, LLC
BUILDER ACCOUNT
ACCOUNT SUMMARY
Commercial Checking
Account Number 1626833 Statement Dates 6/01/54 thru 6/30/54
Previous Balance 8,816.33 Days in Statement Period 30
2 Deposits/Credits 2,300.00
2 Checks/Debits 1,300.00
Total Service Charge 0.00
Interest Paid 0.00
Ending Balance 9,816.33
*** DEPOSITS ***
Date Description Amount
Ee 6/02 Regular Deposit 1,800.00
Â£ 6/05 Telephone transfer 500.00
WITHDRAWALS ***
Date Description Amount
6/02 Telephone transfer per Cherie 800.00
--- Page 2 ---
SUMMARY BY CHECK NUMBER
Date Check Number Amount
6/03 1938 500.00
DAILY BALANCE SUMMARY
Date Balance Date Balance
6/02 9,816.33 6/03 9,316.33 6/30 9,816.33
"""
    report = analyze_markdown(md, parse_mode="deterministic")
    assert report.statement.bank == "Southside Bank"
    assert report.reconciliation.ok
    assert report.quality.corporate_use == "approved"
    assert report.metrics.average_daily_balance is not None


def test_southside_discards_corrupted_ocr_balance_grid_after_detail_reconciles():
    md = """
SOUTHSIDE STATEMENT OF ACCOUNT
THE GRANITE GIRLS, LLC
BUILDER ACCOUNT
ACCOUNT SUMMARY
Commercial Checking
Account Number 1626833 Statement Dates 6/01/54 thru 6/30/54
Previous Balance 8,816.33 Days in Statement Period 30
2 Deposits/Credits 2,300.00
2 Checks/Debits 1,300.00
Total Service Charge 0.00
Interest Paid 0.00
Ending Balance 9,816.33
*** DEPOSITS ***
Date Description Amount
6/02 Regular Deposit 1,800.00
6/05 Telephone transfer 500.00
WITHDRAWALS ***
Date Description Amount
6/02 Telephone transfer per Cherie 800.00
--- Page 2 ---
SUMMARY BY CHECK NUMBER
Date Check Number Amount
6/03 1938 500.00
DAILY BALANCE SUMMARY
Date Balance Date Balance
6/02 19,816.33 6/03 9,316.33 6/30 9,816.33
"""
    report = analyze_markdown(md, parse_mode="deterministic")
    assert report.reconciliation.ok
    assert report.metrics.adb_ok is True
    assert all(t.running_balance is None for t in report.statement.transactions)


def test_scanned_section_groups_alternative_stop_patterns():
    assert _section("START wanted FIRST STOP trailing", r"START", r"FIRST STOP|SECOND STOP").strip() == "wanted"


def test_apex_scanned_parser_handles_ocr_headings_and_complete_detail():
    other_debits = "\n".join(
        f"05/{day:02d}/2026 10.00 Ach withdrawal\nVendor {day}"
        for day in range(1, 15)
    )
    md = f"""
KLR ENTERPRISES
SUMMIT BUSINESS CHECKING
Account Number: ****4124
Balance Forward From 05/01/2054 1,000.00
3 Deposits/Credits 300.00 + Minimum Balance 830.00
17 Withdrawals/Debits 170.00 - Average Balance 1,100.00
Ending Balance As Of 05/31/2054 1,130.00
Interest Paid This Period 0.00
Days In Earnings Period 31
DATE AMOUNT DESCRIPTION DATE AMOUNT DESCRIPTION
05/15/2054 100.00 Regular Deposit 05/26/2054 100.00 Regular Deposit
OTHER CREDITS
DATE AMOUNT DESCRIPTION
05/04/2054 100.00 Wire Transfer In
CHECK NO DATE AMOUNT CHECK NO DATE AMOUNT
2847 05/01/2054 10.00
* - denotes missing check number in sequence
OTHER DEBITS
DATE AMOUNT DESCRIPTION
{other_debits}
SERVICE CHARGES
DATE AMOUNT DESCRIPTION
05/29/2054 10.00 Net Service Charge
SFRVICE CHARGE ANALYSIS
FEESCHARGED
DATE AMOUNT DESCRIPTION
05/13/2054 10.00 NSF Charge
TOTAL FEES FOR THIS PERIOD
DAILY BALANCE INFORMATION
"""
    stmt = parse_apex_scanned_statement(md)
    assert stmt is not None
    assert len(stmt.transactions) == 20
    assert round(sum(t.amount for t in stmt.transactions if t.amount > 0), 2) == 300.00
    assert round(-sum(t.amount for t in stmt.transactions if t.amount < 0), 2) == 170.00
    assert reconcile(stmt).ok


def _txn(date, amount, desc="x", bal=None):
    return Transaction(
        date=date, description=desc, amount=amount,
        direction="credit" if amount >= 0 else "debit", running_balance=bal,
    )


# ---- reconciliation ----------------------------------------------------------

def test_reconcile_ok():
    s = Statement(beginning_balance=1000.0, ending_balance=1300.0, transactions=[
        _txn("2054-01-01", 500.0, bal=1500.0),
        _txn("2054-01-02", -200.0, bal=1300.0),
    ])
    r = reconcile(s)
    assert r.ok
    assert r.sum_delta == 0.0
    assert r.continuity_breaks == 0


def test_reconcile_sum_mismatch():
    s = Statement(beginning_balance=1000.0, ending_balance=9999.0, transactions=[
        _txn("2054-01-01", 500.0),
    ])
    r = reconcile(s)
    assert not r.ok
    assert any("sum check" in i for i in r.issues)


def test_reconcile_continuity_break():
    s = Statement(beginning_balance=1000.0, ending_balance=1300.0, transactions=[
        _txn("2054-01-01", 500.0, bal=1500.0),
        _txn("2054-01-02", -200.0, bal=9999.0),  # wrong running balance
    ])
    r = reconcile(s)
    assert not r.ok
    assert r.continuity_breaks == 1


def test_reconcile_sparse_running_balances_accumulates_intervening_rows():
    s = Statement(beginning_balance=100.0, ending_balance=85.0, transactions=[
        _txn("2054-01-01", -10.0),
        _txn("2054-01-01", -5.0, bal=85.0),
    ])
    r = reconcile(s)
    assert r.ok
    assert r.continuity_breaks == 0


def test_reconcile_implies_missing_beginning_from_stated_summary():
    s = Statement(
        ending_balance=167.73,
        stated_total_credits=12023.20,
        stated_total_debits=11836.40,
        transactions=[
            _txn("2053-10-10", 12023.20),
            _txn("2053-10-31", -11836.40, bal=167.73),
        ],
    )
    r = reconcile(s)
    assert r.summary_ok is True
    assert r.computed_ending == 167.73
    assert r.sum_delta == 0.0


def test_reconcile_flags_scrambled_summary():
    # credits/debits swapped and a count (26) read as the debit total -> the
    # bank-stated summary itself no longer reconciles.
    s = Statement(
        beginning_balance=-78.68, ending_balance=3297.42,
        stated_total_credits=3945.12, stated_total_debits=26.0,  # scrambled
        transactions=[],
    )
    r = reconcile(s)
    assert not r.ok
    assert r.summary_ok is False
    assert any("summary does not reconcile" in i for i in r.issues)


def test_reconcile_good_summary_with_separate_service_charge():
    # Real F&M values: -78.68 + 7329.22 - 3945.12 - 8.00 SC + 0 interest == 3297.42
    s = Statement(
        beginning_balance=-78.68, ending_balance=3297.42,
        stated_total_credits=7329.22, stated_total_debits=3945.12,
        stated_service_charge=8.00, stated_interest_paid=0.0,
        transactions=[],
    )
    r = reconcile(s)
    assert r.summary_ok is True
    assert not any("summary does not reconcile" in i for i in r.issues)


def test_reconcile_good_summary_service_charge_folded_into_debits():
    # Bank folds the $8 charge into the debit total; no separate SC field.
    s = Statement(
        beginning_balance=-78.68, ending_balance=3297.42,
        stated_total_credits=7329.22, stated_total_debits=3953.12,  # 3945.12 + 8
        transactions=[],
    )
    r = reconcile(s)
    assert r.summary_ok is True


def test_reconcile_debit_coverage_flags_incomplete_ocr():
    # Bank says $4000 of debits; we only captured $756 of line items.
    s = Statement(
        beginning_balance=0.0, ending_balance=0.0,
        stated_total_credits=7329.22, stated_total_debits=3945.12,
        stated_credit_count=3, stated_debit_count=26,
        transactions=[_txn("2054-01-01", 7329.22), _txn("2054-01-02", -756.30)],
    )
    r = reconcile(s)
    assert r.credit_coverage == 1.0
    assert r.debit_coverage is not None and r.debit_coverage < 0.5
    assert any("stated" in i and "debits" in i for i in r.issues)


# ---- metrics -----------------------------------------------------------------

def test_daily_average_balance_carries_forward():
    # 3-day period; no activity on day 3 carries day 2's balance forward.
    s = Statement(
        period_start="2054-01-01", period_end="2054-01-03",
        beginning_balance=1000.0, ending_balance=1300.0, transactions=[
            _txn("2054-01-01", 500.0, bal=1500.0),
            _txn("2054-01-02", -200.0, bal=1300.0),
        ],
    )
    balances = daily_closing_balances(s)
    assert balances[date(2054, 1, 3)] == 1300.0  # carried from day 2
    m = compute_metrics(s)
    assert m.days_in_period == 3
    assert m.average_daily_balance == round((1500 + 1300 + 1300) / 3, 2)  # 1366.67


def test_daily_average_balance_tolerates_rows_without_running_balance():
    # Real statements sometimes omit the balance on fee/detail rows. Those rows
    # must still move that day's ending balance — the money did leave the
    # account — and must not prevent ADB from being computed.
    s = Statement(
        period_start="2054-01-01", period_end="2054-01-04",
        beginning_balance=1000.0, ending_balance=1125.0, transactions=[
            _txn("2054-01-01", 200.0, bal=1200.0),
            _txn("2054-01-02", -25.0, "SERVICE FEE", bal=None),
            _txn("2054-01-03", -50.0, bal=1125.0),
        ],
    )
    balances = daily_closing_balances(s)
    assert balances[date(2054, 1, 2)] == 1175.0  # reconstructed: 1200 - 25
    assert balances[date(2054, 1, 4)] == 1125.0  # carried from Jan 3
    m = compute_metrics(s)
    assert m.average_daily_balance == round((1200 + 1175 + 1125 + 1125) / 4, 2)  # 1156.25
    assert m.adb is not None and m.adb.ok
    assert m.adb.validations["ledger_reconciles_to_closing"] is True


def test_metrics_retains_bank_stated_average_only_as_comparison_evidence():
    s = Statement(stated_average_balance=1569.0, transactions=[_txn("2054-01-01", 100.0)])
    m = compute_metrics(s)
    assert m.stated_average_balance == 1569.0
    assert "average_balance" not in vars(m)
    assert "average_balance_source" not in vars(m)
    assert m.average_daily_balance is None  # nothing to compute


def test_metrics_effective_totals_use_reconciled_bank_summary():
    s = Statement(
        stated_total_credits=5000.0,
        stated_total_debits=3200.0,
        stated_credit_count=8,
        stated_debit_count=20,
        transactions=[_txn("2054-01-01", 1000.0), _txn("2054-01-02", -250.0)],
    )
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.total_deposits == 1000.0
    assert m.total_withdrawals == 250.0
    assert m.effective_total_deposits == 5000.0
    assert m.effective_total_withdrawals == 3200.0
    assert m.effective_num_deposits == 8
    assert m.effective_num_withdrawals == 20
    assert m.deposits_source == "bank_stated_reconciled"
    assert m.withdrawals_source == "bank_stated_reconciled"


def test_metrics_effective_withdrawals_include_separate_service_charge():
    s = Statement(
        beginning_balance=11982.22,
        ending_balance=35121.16,
        stated_total_credits=141759.20,
        stated_total_debits=118610.26,
        stated_service_charge=10.00,
        transactions=[],
    )
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.effective_total_withdrawals == 118620.26


def test_metrics_does_not_compute_adb_when_running_balances_untrusted():
    s = Statement(
        period_start="2054-01-01", period_end="2054-01-02",
        stated_average_balance=100.0,
        transactions=[_txn("2054-01-01", 50.0, bal=150.0)],
    )
    m = compute_metrics(s, trust_running_balances=False)
    assert m.average_daily_balance is None
    assert m.adb_ok is False
    assert m.daily_balance_sum is None
    assert m.min_balance is None
    assert any("reconciliation failed" in n for n in m.notes)


def test_metrics_ignores_bank_totals_when_summary_fails():
    s = Statement(
        stated_total_credits=5000.0,
        stated_total_debits=3200.0,
        transactions=[_txn("2054-01-01", 1000.0), _txn("2054-01-02", -250.0)],
    )
    m = compute_metrics(s, trust_stated_summary=False)
    assert m.effective_total_deposits == 1000.0
    assert m.effective_total_withdrawals == 250.0
    assert m.deposits_source == "line_items"
    assert m.withdrawals_source == "line_items"
    assert any("ignored bank-stated" in n for n in m.notes)


def test_metrics_counts_and_nsf():
    s = Statement(transactions=[
        _txn("2054-01-01", 500.0, "DEPOSIT"),
        _txn("2054-01-02", -30.0, "NSF FEE"),
        _txn("2054-01-03", -20.0, "Returned item fee"),
    ])
    m = compute_metrics(s)
    assert m.num_deposits == 1 and m.num_withdrawals == 2
    assert m.total_deposits == 500.0 and m.total_withdrawals == 50.0
    assert m.nsf_count == 2


def test_metrics_effective_nsf_uses_classified_rows_over_bank_stated_count():
    s = Statement(stated_nsf_count=4, transactions=[
        _txn("2054-01-02", -30.0, "NSF FEE"),
    ])
    m = compute_metrics(s)
    assert m.nsf_count == 1                                   # returned items stay as evidence
    assert m.effective_nsf_count == 0                         # R18: no validated ledger, so no negative-day count
    assert m.nsf_source == "negative_ending_days_unavailable"
    assert any("bank-stated NSF count 4 differs" in note for note in m.notes)


def test_metrics_computes_true_revenue_cash_flow_lender_pos_and_loan_counts():
    s = Statement(stated_total_credits=12000.0, stated_total_debits=5000.0, transactions=[
        _txn("2054-01-02", 10000.0, "CUSTOMER DEPOSIT"),
        _txn("2054-01-03", 2000.0, "ACH CREDIT RAPID FINANCE FUNDING"),
        _txn("2054-01-04", -500.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
        _txn("2054-01-05", -25.0, "DEBIT CARD PURCHASE GAS"),
        _txn("2054-01-06", -750.0, "SBA LOAN PAYMENT"),
    ])
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.lender_credits == 2000.0
    assert m.lender_debits == 500.0
    assert m.monthly_lender_debits == 500.0
    # 5.6 (T9): true_revenue is True revenue; the bare teller CUSTOMER DEPOSIT is counted (no payer printed).
    assert m.true_revenue == 10000.0
    assert m.verified_revenue_total == 0.0
    assert m.cash_flow == 7000.0
    assert m.withholding_rate == 5.0
    assert m.pos_count == 1
    assert m.loan_count == 1
    # Owner ruling 2026-09-24: SBA is an alternative position, never a potential lender.
    assert classify_statement_transactions(s)[4].classification == "alternative_position"
    assert m.potential_lender_debit_count == 0
    assert m.flagged_groups == {
        "alternative_positions": {"count": 1, "total": 750.0, "count_credited": 0, "total_credited": 0.0, "payees": 1}
    }


def test_metrics_uses_exact_posted_lender_debits_for_withholding_rate():
    s = Statement(stated_total_credits=4330.0, stated_total_debits=400.0, transactions=[
        _txn("2054-01-01", 4330.0, "CUSTOMER DEPOSIT"),
        _txn("2054-01-02", -100.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
        _txn("2054-01-09", -100.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
        _txn("2054-01-16", -100.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
        _txn("2054-01-23", -100.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
    ])
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.lender_debits == 400.0
    assert m.monthly_lender_debits == 400.0
    assert m.withholding_numerator == 400.0
    assert m.withholding_denominator == 4330.0
    assert m.withholding_rate == 400.0 / 4330.0 * 100


def test_metrics_withholding_rate_is_zero_without_lender_debits():
    s = Statement(stated_total_credits=10000.0, stated_total_debits=500.0, transactions=[
        _txn("2054-01-01", 10000.0, "CUSTOMER DEPOSIT"),
        _txn("2054-01-02", 750.0, "ACH CREDIT CAN CAPITAL FUNDING"),
        _txn("2054-01-03", -500.0, "RENT PAYMENT"),
    ])
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.lender_credits == 750.0
    assert m.lender_debits == 0.0
    assert m.withholding_rate == 0.0
    assert not m.withholding_review_required


def test_metrics_counts_forward_funding_alias_for_withholding_rate():
    s = Statement(stated_total_credits=10000.0, stated_total_debits=205.0, transactions=[
        _txn("2054-01-01", 10000.0, "CUSTOMER DEPOSIT"),
        _txn("2054-01-02", -205.0, "Direct Debit Business PAD Forward Funding"),
    ])
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.lender_debits == 205.0
    assert m.monthly_lender_debits == 205.0
    assert m.withholding_rate == 205.0 / 10000.0 * 100


# ---- withheld-source forensic regressions -----------------------------------

def test_farmers_merchants_source_pdf_is_complete_extraction_but_incomplete_ledger():
    markdown, report = _raw_pdf_report("Misc/Ace_Auto_Final_Cut.pdf")
    stmt = report.statement

    assert markdown.count("--- Page") == 3
    assert report.model_used == "farmers-&-merchants-bank-deterministic"
    assert [(txn.date, txn.amount) for txn in stmt.transactions] == [
        ("2025-12-01", 1104.71),
        ("2025-12-08", 3000.0),
        ("2025-12-29", 3224.51),
        ("2025-12-01", -19.29),
        ("2025-12-02", -32.0),
        ("2025-12-10", -184.16),
        ("2025-12-11", -200.0),
        ("2025-12-19", -50.0),
        ("2025-12-23", -73.63),
        ("2025-12-23", -110.45),
        ("2025-12-30", -19.29),
        ("2025-12-31", -2.0),
        ("2025-12-31", -151.62),
        ("2025-12-31", -159.23),
        ("2025-12-31", -8.0),
    ]
    assert stmt.stated_credit_count == 3
    assert stmt.stated_debit_count == 26
    assert stmt.stated_total_credits == 7329.22
    assert stmt.stated_total_debits == 3945.12
    assert round(sum(txn.amount for txn in stmt.transactions if txn.amount > 0), 2) == 7329.22
    normal_debits = round(-sum(
        txn.amount
        for txn in stmt.transactions
        if txn.amount < 0 and txn.description != "TOTAL SERVICE CHARGE"
    ), 2)
    assert normal_debits == 1001.67

    adb = compute_average_daily_balance(stmt, source_markdown=markdown)
    assert adb.computed_closing_balance == 6240.87
    assert adb.daily_balance_sum == 101004.80
    assert adb.average_daily_balance == 3258.22
    assert not adb.ok
    assert report.reconciliation.summary_ok is True
    assert report.reconciliation.sum_delta == 2943.45
    assert report.metrics.average_daily_balance is None
    _assert_withheld_adb_is_not_public(report, "Ace_Auto_Final_Cut.pdf")


def test_bmo_source_pdf_rows_are_fully_captured_but_mutually_contradictory():
    markdown, report = _raw_pdf_report(
        "Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf"
    )
    stmt = report.statement

    assert markdown.count("--- Page") == 2
    assert report.model_used == "bmo-deterministic"
    assert [(txn.date, txn.amount, txn.running_balance) for txn in stmt.transactions] == [
        ("2026-01-01", 11788.0, 740888.0),
        ("2026-01-01", 11788.0, 751676.0),
        ("2026-01-02", -1000.0, 762464.0),
        ("2026-01-02", 14000.0, 765676.0),
        ("2026-01-03", -650.0, 765026.0),
        ("2026-01-03", 11788.0, 792600.0),
        ("2026-01-04", 11788.0, 773252.0),
        ("2026-01-04", -1000.0, 803600.0),
        ("2026-01-05", 11788.0, 814600.0),
        ("2026-01-05", 12800.0, 823890.0),
        ("2026-01-06", -1800.0, 821090.0),
        ("2026-01-06", 11788.0, 824600.0),
        ("2026-01-07", 13500.0, 835878.0),
        ("2026-01-07", -2800.0, 833570.0),
        ("2026-01-08", 11788.0, 835100.0),
        ("2026-01-08", 11788.0, 846100.0),
        ("2026-01-09", -1000.0, 856600.0),
        ("2026-01-09", 11788.0, 867600.0),
        ("2026-01-10", 11788.0, 877600.0),
        ("2026-01-11", -1000.0, 888600.0),
        ("2026-01-12", 11788.0, 899100.0),
        ("2026-01-13", 14000.0, 899050.0),
        ("2026-01-14", -7000.0, 895050.0),
        ("2026-01-15", 11788.0, 910100.0),
        ("2026-01-16", 13000.0, 917550.0),
        ("2026-01-17", -2000.0, 915550.0),
        ("2026-01-18", 11788.0, 920600.0),
        ("2026-01-19", 11788.0, 931600.0),
        ("2026-01-20", -1000.0, 942600.0),
        ("2026-01-21", 1200.0, 953100.0),
        ("2026-01-22", 1200.0, 963600.0),
        ("2026-01-23", -1000.0, 973600.0),
        ("2026-01-24", 1380.0, 983600.0),
        ("2026-01-25", -1000.0, 982600.0),
        ("2026-01-26", 1188.0, 983688.0),
        ("2026-01-27", 1200.0, 884600.0),
        ("2026-01-28", -1000.0, 983600.0),
        ("2026-01-28", 1300.0, 984100.0),
        ("2026-01-29", 1300.0, 986600.0),
        ("2026-01-30", -1000.0, 985600.0),
        ("2026-01-31", 14400.0, 1000000.0),
    ]
    assert sum(txn.amount for txn in stmt.transactions if txn.amount > 0) == 255500.0
    assert -sum(txn.amount for txn in stmt.transactions if txn.amount < 0) == 23250.0

    adb = compute_average_daily_balance(stmt, source_markdown=markdown)
    assert adb.computed_closing_balance == 962350.0
    assert adb.daily_balance_sum == 27733670.0
    assert adb.average_daily_balance == 894634.52
    assert not adb.ok
    assert report.reconciliation.sum_delta == -37650.0
    assert report.reconciliation.continuity_breaks == 36
    assert report.metrics.average_daily_balance is None
    assert "conflicting_statement_summaries" in report.integrity.flags
    assert any(
        "secondary bank-stated summary does not reconcile" in note
        for note in report.integrity.notes
    )
    _assert_withheld_adb_is_not_public(
        report, "BMO_Statement_January_2026 Final-1-2 (1).pdf"
    )


def test_bmo_parser_uses_the_printed_period_and_balance_continuity():
    markdown = """
Account Summary Totals
BMO BANK STATEMENT
Statement Period: February 2056
Example Company
Account Number: 123456 | Currency: USD
Account Summary
Opening Balance $ 100.00
Total Deposits $ 50.00
Total Withdrawals $ 20.00
Interest Earned $ 0.00
Fees and Charges $ -0.00
Closing Balance $ 130.00
Transaction Details
Date Description Withdrawal Deposit Balance
02/02 Neutral row alpha $ 20.00 $ 80.00
02/29 Neutral row beta $ 50.00 $ 130.00
Page 1 - Transactions 1-2
"""
    stmt = parse_bmo_statement(markdown)
    assert stmt is not None
    assert stmt.period_start == "2056-02-01"
    assert stmt.period_end == "2056-02-29"
    assert stmt.currency == "USD"
    assert [(txn.date, txn.amount) for txn in stmt.transactions] == [
        ("2056-02-02", -20.0),
        ("2056-02-29", 50.0),
    ]
    assert compute_metrics(stmt).average_daily_balance == 82.41


# ---- detection ---------------------------------------------------------------

def test_detect_known_funder():
    s = Statement(transactions=[
        _txn("2054-01-02", -450.0, "Orig CO Name:Kapitus Descr:Payment ACH Debit"),
        _txn("2054-01-03", -450.0, "Orig CO Name:Kapitus Descr:Payment ACH Debit"),
    ])
    matches = find_known_funders(s)
    assert len(matches) == 1
    assert matches[0].funder == "KAPITUS"
    assert matches[0].total_debited == 900.0


def test_detect_affirm_without_space():
    s = Statement(transactions=[
        _txn("2054-03-02", -26.10, "Debit Card Purchase 030226 AFFIRMCOM PAYMENTS 8554233729 CA"),
        _txn("2054-03-30", -26.10, "Recur Debit Card Purchase 033026 AFFIRM COM PAYMENTS 8554233729 CA"),
    ])
    matches = find_known_funders(s)
    assert matches == []
    # D8: a card-paid Affirm instalment is classified by who was paid.
    assert [record.classification for record in classify_statement_transactions(s)] == [
        "alternative_position",
        "alternative_position",
    ]
    assert compute_metrics(s).pos_count == 0


def test_detect_expanded_lender_keyword_aliases():
    s = Statement(transactions=[
        _txn("2054-01-02", -300.0, "ACH DEBIT THE FUNDWORKS LLC PMT"),
        _txn("2054-01-03", -225.0, "DIRECT DEB DELAGELANDEN LEASE"),
    ])
    matches = find_known_funders(s)
    assert [m.funder for m in matches] == ["FUNDWORKS", "De Lage Landen"]


def test_recurring_debits_filters_generic_processors():
    s = Statement(transactions=[
        _txn("2054-01-02", -45.0, "DEBIT CARD PURCHASE COFFEE 0102"),
        _txn("2054-01-03", -45.0, "DEBIT CARD PURCHASE COFFEE 0103"),
        _txn("2054-01-04", -45.0, "DEBIT CARD PURCHASE COFFEE 0104"),
    ])
    assert find_recurring_debits(s) == []


def test_detect_recurring_daily_pattern():
    # 5 fixed $450 debits on business days -> daily cadence.
    s = Statement(transactions=[
        _txn("2054-01-02", -450.0, "ACH Debit Funder 0102"),
        _txn("2054-01-05", -450.0, "ACH Debit Funder 0105"),
        _txn("2054-01-06", -450.0, "ACH Debit Funder 0106"),
        _txn("2054-01-07", -450.0, "ACH Debit Funder 0107"),
        _txn("2054-01-08", -450.0, "ACH Debit Funder 0108"),
    ])
    rec = find_recurring_debits(s)
    assert rec == []


def test_detect_ignores_one_off_debits():
    s = Statement(transactions=[
        _txn("2054-01-02", -12.34, "Coffee"),
        _txn("2054-01-03", -56.78, "Gas"),
    ])
    d = detect(s)
    assert d.recurring_debits == []
    assert d.known_funders == []


def test_r18_underwriting_nsf_counts_negative_ending_days_not_returned_items():
    stmt = Statement(
        bank="Test Bank", period_start="2054-01-01", period_end="2054-01-05",
        beginning_balance=100.0, ending_balance=-20.0,
        transactions=[_txn("2054-01-02", -150.0, "ITEM RETURNED NSF", bal=-50.0), _txn("2054-01-04", 30.0, "DEPOSIT", bal=-20.0)],
    )
    assert reconcile(stmt).ok
    m = compute_metrics(stmt)
    assert m.nsf_count == 1                     # the returned item is still evidence
    assert m.negative_days == 4                 # carry-over basis: 01-02 through 01-05 end below zero
    assert m.negative_printed_days == 2         # printed basis: 01-02 and 01-04, the days with activity
    assert m.effective_nsf_count == 2 and m.nsf_source == "negative_printed_days"


def test_r18_underwriting_nsf_is_unavailable_without_a_validated_ledger():
    stmt = Statement(
        bank="Test Bank", period_start="2054-01-01", period_end="2054-01-05",
        beginning_balance=100.0, ending_balance=-20.0,
        transactions=[_txn("2054-01-02", -150.0, "ITEM RETURNED NSF"), _txn("2054-01-04", 30.0, "DEPOSIT")],
    )
    m = compute_metrics(stmt, trust_running_balances=False)
    assert m.nsf_count == 1 and m.effective_nsf_count == 0 and m.nsf_source == "negative_ending_days_unavailable"
    assert any("not computable" in note for note in m.notes)


# --- Audit B9 (I13, I38): the holder's name is its own field, read from the header or the address block -------------
# Fabricated statements only: invented names, the 555 telephone range, zero-filled mail-routing codes.

_CHASE_SUMMARY_LINES = """Beginning Balance $1,000.00
Deposits and Additions 2 800.00
Fees 1 -15.00
Ending Balance 3 $1,785.00
*end*summary
*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT 01/02 Deposit 500.00 01/03 Zelle Payment From Client 300.00
Total Deposits and Additions $800.00
*end*deposits and additions
*start*fees section
FEES
DATE DESCRIPTION AMOUNT 01/31 Monthly Service Fee $15.00
Total Fees $15.00
*end*fees section
"""

_CHASE_MAILING_BLOCK = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A. P O Box 100000 Sampleville, TX 75001 - 0001
000000123456789
Account Number:
CUSTOMER SERVICE INFORMATION
Chase.com
Web site:
1-800-555-0100
Service Center:
Para Espanol: 1-888-555-0101
00000001 DRE 001 001 00001 NNNNNNNNNNN T 1 000000001 01 0001
International Calls:
1-713-555-0102
NORTHWIND MARINE LLC
We accept operator relay calls
DBA NORTHWIND BOATWORKS
100 SAMPLE ST
SAMPLEVILLE TX 75001-0001
00000000000000000000
*start*summary
Chase Business Complete Checking
CHECKING SUMMARY
INSTANCES AMOUNT
""" + _CHASE_SUMMARY_LINES

_CHASE_FLAT_MAILING_LINE = """
January 01, 2054 through January 31, 2054
JPMorgan Chase Bank, N.A. P O Box 100000 Sampleville, TX 75001 - 0001
Account Number: 000000123456789
CUSTOMER SERVICE INFORMATION
Web site: Chase.com Service Center: 1-800-555-0100 Para Espanol: 1-888-555-0101 We accept operator relay calls
00000001 DRI 001 001 00001 NNNNNNNNNNN 1 000000001 01 0001 CONTOSO TRADING CO LLC 100 SAMPLE ST STE 2 SAMPLEVILLE TX 75001-0001
00000000000000000000
*start*summary
CHECKING SUMMARY Chase Business Complete Checking
INSTANCES AMOUNT Beginning Balance $1,000.00
Deposits and Additions 2 800.00 Fees 1 -15.00 Ending Balance 3 $1,785.00
*end*summary
*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT 01/02 Deposit 500.00 01/03 Zelle Payment From Client 300.00
Total Deposits and Additions $800.00
*end*deposits and additions
*start*fees section
FEES
DATE DESCRIPTION AMOUNT 01/31 Monthly Service Fee $15.00
Total Fees $15.00
*end*fees section
"""


def test_chase_never_publishes_its_summary_grid_header_as_the_account_name():
    stmt = parse_chase_statement(_CHASE_MAILING_BLOCK)
    assert stmt is not None
    assert reconcile(stmt).ok
    assert stmt.account_name is None
    assert [t.amount for t in stmt.transactions] == [500.0, 300.0, -15.0]


@pytest.mark.parametrize("header", [
    "INSTANCES AMOUNT\nBeginning Balance $1,000.00",
    "AMOUNT\nBeginning Balance $1,000.00",
    "INSTANCES AMOUNT Beginning Balance $1,000.00",
])
def test_chase_reads_no_grid_header_spelling_as_the_account_name(header):
    md = _CHASE_MAILING_BLOCK.replace("INSTANCES AMOUNT\nBeginning Balance $1,000.00\n", f"{header}\n")
    stmt = parse_chase_statement(md)
    assert stmt is not None and stmt.account_name is None


def test_chase_reads_the_holder_from_its_mailing_block():
    stmt = parse_chase_statement(_CHASE_MAILING_BLOCK)
    assert stmt is not None
    assert stmt.holder_name == "NORTHWIND MARINE LLC DBA NORTHWIND BOATWORKS"


def test_chase_reads_the_holder_from_a_mailing_block_flattened_onto_one_line():
    stmt = parse_chase_statement(_CHASE_FLAT_MAILING_LINE)
    assert stmt is not None
    assert reconcile(stmt).ok
    assert stmt.holder_name == "CONTOSO TRADING CO LLC"
    assert stmt.account_name is None


def test_chase_reads_no_holder_without_its_mailing_block():
    md = "\n".join(line for line in _CHASE_MAILING_BLOCK.splitlines() if " DRE " not in line)
    stmt = parse_chase_statement(md)
    assert stmt is not None and stmt.holder_name is None


def test_chase_s_owner_line_after_the_holder_is_no_part_of_the_holder_s_name():
    md = _CHASE_MAILING_BLOCK.replace("DBA NORTHWIND BOATWORKS", "SAMPLE PERSON NAME")
    stmt = parse_chase_statement(md)
    assert stmt is not None and stmt.holder_name == "NORTHWIND MARINE LLC"


def test_a_chase_product_line_after_the_summary_heading_is_still_the_account_name():
    md = _CHASE_MAILING_BLOCK.replace(
        "Chase Business Complete Checking\nCHECKING SUMMARY\nINSTANCES AMOUNT\n",
        "CHECKING SUMMARY\nChase Business Complete Checking\nINSTANCES AMOUNT\n",
    )
    stmt = parse_chase_statement(md)
    assert stmt is not None and stmt.account_name == "Chase Business Complete Checking"


_FIRST_CITIZENS_HOLDER_LINE = (
    "CONTOSO LLC DBA NORTHWIND AGENCY, LLC PREMIUM TRUST ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001 1,234.56"
)


def test_first_citizens_reads_the_holder_line_before_its_summary():
    import re

    real = parse_first_citizens_statement(_artifact_markdown("064_First Citizens Bank.md"))
    md = re.sub(
        r"^[^\n]*\n(?=Your Account\(s\) At A Glance)", _FIRST_CITIZENS_HOLDER_LINE + "\n",
        _artifact_markdown("064_First Citizens Bank.md"), count=1, flags=re.MULTILINE,
    )
    stmt = parse_first_citizens_statement(md)
    assert stmt is not None and real is not None
    assert stmt.holder_name == "CONTOSO LLC DBA NORTHWIND AGENCY, LLC"
    # Owner ruling 2026-10-02 (Q10), R2-OW10: the designation the line prints after the name is the account's title,
    # read from the same line.
    assert stmt.account_title == "PREMIUM TRUST ACCOUNT"
    # The holder line changes nothing else the parser reads.
    assert stmt.model_dump(exclude={"holder_name", "account_title"}) == real.model_dump(
        exclude={"holder_name", "account_title"}
    )


@pytest.mark.parametrize(("line", "holder"), [
    (_FIRST_CITIZENS_HOLDER_LINE, "CONTOSO LLC DBA NORTHWIND AGENCY, LLC"),
    ("CONTOSO LLC DBA NORTHWIND AGENCY LLC OPERATING ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "CONTOSO LLC DBA NORTHWIND AGENCY LLC"),
    ("CONTOSO LLC DBA NORTHWIND AGENCY LLC WIRE ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001 12.00",
     "CONTOSO LLC DBA NORTHWIND AGENCY LLC"),
    ("CONTOSO LLC DBA NORTHWIND AGENCY, LLC PRODUCER PAYABLE ACCOUNT PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "CONTOSO LLC DBA NORTHWIND AGENCY, LLC"),
    # A designation printed after the legal form is never part of the name, whatever its words.
    ("CONTOSO LLC DBA NORTHWIND AGENCY LLC SAMPLE SYNDICATE PO BOX 100 SAMPLEVILLE SC 29000-0001",
     "CONTOSO LLC DBA NORTHWIND AGENCY LLC"),
    ("CONTOSO LLC PO BOX 100 SAMPLEVILLE SC 29000-0001", "CONTOSO LLC"),
    ("FABRIKAM HOMES INC 1000 SAMPLE HAVEN DR SAMPLEVILLE NC 27000-0001", "FABRIKAM HOMES INC"),
    ("FABRIKAM KIDS DENTISTRY INC DBA FABRIKAM DENTISTRY 1000 SAMPLE TRAIL RD STE 100 SAMPLEVILLE GA 30000-0001",
     "FABRIKAM KIDS DENTISTRY INC DBA FABRIKAM DENTISTRY"),
    ("SAMPLE J PERSON DMD PA 10000 SAMPLE POINT DR UNIT C SAMPLEVILLE NC 28000-0001", "SAMPLE J PERSON DMD PA"),
    ("NORTHWIND SERVICES TRUST ACCOUNT P O BOX 100 SAMPLEVILLE SC 29000-0001", "NORTHWIND SERVICES"),
    # An address with no name before it names nobody.
    ("PO BOX 100 SAMPLEVILLE SC 29000-0001", None),
    ("", None),
])
def test_the_address_line_reader_keeps_the_name_and_drops_the_designation_and_the_address(line, holder):
    from analysis.holder_name import holder_from_address_line, read_address_line

    assert holder_from_address_line(line) == holder
    assert read_address_line(line).name == holder


@pytest.mark.parametrize(("lines", "holder"), [
    (["NORTHWIND MARINE LLC", "DBA NORTHWIND BOATWORKS", "100 SAMPLE ST", "SAMPLEVILLE TX 75001-0001"],
     "NORTHWIND MARINE LLC DBA NORTHWIND BOATWORKS"),
    (["NORTHWIND MARINE LLC", "SAMPLE PERSON NAME", "100 SAMPLE ST", "SAMPLEVILLE TX 75001-0001"],
     "NORTHWIND MARINE LLC"),
    (["CONTOSO TRADING CO LLC", "PO BOX 100", "SAMPLEVILLE KS 66000-0001"], "CONTOSO TRADING CO LLC"),
    # A name wrapped after a connector continues on the next line; a returned-mail hold is no part of the name.
    (["NORTHWIND HEART &", "VASCULAR CARE LLC", "100 SAMPLE ST", "SAMPLEVILLE TX 75001-0001"],
     "NORTHWIND HEART & VASCULAR CARE LLC"),
    (["HOLD - RETURN MAIL CONTOSO BUILDERS GROUP LLC", "100 SAMPLE ST", "SAMPLEVILLE TX 75001-0001"],
     "CONTOSO BUILDERS GROUP LLC"),
    (["SAMPLE PERSON", "OR SAMPLE OTHER PERSON", "100 SAMPLE ST", "SAMPLEVILLE TX 75001-0001"], "SAMPLE PERSON"),
    (["100 SAMPLE ST", "SAMPLEVILLE TX 75001-0001"], None),
    ([], None),
])
def test_the_address_block_reader_keeps_the_name_lines_before_the_street(lines, holder):
    from analysis.holder_name import holder_from_address_block, read_address_block

    assert holder_from_address_block(lines) == holder
    assert read_address_block(lines).name == holder


@pytest.mark.parametrize(("line", "holder"), [
    # A contact or a case printed after the name is no part of it.
    ("NORTHWIND PDR ATTN SAMPLE PERSON 100 SAMPLE ST STE 2 SAMPLEVILLE TX 75001-0001", "NORTHWIND PDR"),
    ("CONTOSO TRADING LLC C/O SAMPLE PERSON 100 SAMPLE ST SAMPLEVILLE TX 75001-0001", "CONTOSO TRADING LLC"),
    ("SAMPLE PERSON CASE 12-34567-AB 100 SAMPLE LN SAMPLEVILLE SC 29000-0001", "SAMPLE PERSON"),
    # A numbered company keeps its number.
    ("1234567 ONTARIO INC. 100 SAMPLE ST W UNIT 2 SAMPLEVILLE ON L1M 2L3", "1234567 ONTARIO INC."),
    ("1234-5678 QUEBEC INC. SAMPLE PERSON 100A SAINT-SAMPLE BOUL SAMPLEVILLE PQ H1R 2J3", "1234-5678 QUEBEC INC."),
])
def test_the_address_line_reader_cuts_a_contact_and_keeps_a_numbered_company(line, holder):
    from analysis.holder_name import holder_from_address_line, read_address_line

    assert holder_from_address_line(line) == holder
    assert read_address_line(line).name == holder


@pytest.mark.parametrize(("name", "holder"), [
    ("CONTOSO LLC DBA NORTHWIND AGENCY LLC OPERATING ACCOUNT", "CONTOSO LLC DBA NORTHWIND AGENCY LLC"),
    ("NORTHWIND TRANSPORT CO.", "NORTHWIND TRANSPORT CO."),
    ("SAMPLE PERSON DBA SAMPLE PERSON CONSULTING", "SAMPLE PERSON DBA SAMPLE PERSON CONSULTING"),
    ("", None),
])
def test_a_bare_name_line_loses_only_its_designation(name, holder):
    from analysis.holder_name import holder_from_name, read_name

    assert holder_from_name(name) == holder
    assert read_name(name).name == holder


# Owner ruling 2026-10-02 (the underwriter's Q10), audit round 2, R2-OW10: the holder readers return the account title
# they drop after the holder's name (HolderReading: name, title), from the same tokens; every holder name stays as it
# was. Fabricated lines only.

def _frozen_without_designation(tokens):
    """analysis.holder_name._without_designation as it stood before R2-OW10 (audit B9), frozen for the fuzz below."""
    from analysis import holder_name as hn

    last_form = max((index for index, token in enumerate(tokens) if index > 0 and hn._legal_form(token)), default=None)
    if last_form is not None:
        return tokens[: last_form + 1]
    if tokens and hn._word(tokens[-1]) in hn._ACCOUNT_WORDS:
        cut = len(tokens) - 1
        while cut > 0 and len(tokens) - 1 - cut < hn._MAX_DESIGNATION_WORDS and hn._word(tokens[cut - 1]) in (
            hn._DESIGNATION_WORDS
        ):
            cut -= 1
        if cut > 0:
            return tokens[:cut]
    return tokens


def _frozen_name(tokens):
    """analysis.holder_name._name as it stood before R2-OW10 (audit B9), frozen for the fuzz below."""
    from analysis import holder_name as hn

    tokens = hn._without_contact(tokens)
    split = next(((index, width) for index in range(1, len(tokens)) if (width := hn._dba(tokens, index))), None)
    if split is None:
        parts = [_frozen_without_designation(tokens)]
        markers: list[str] = []
    else:
        index, width = split
        parts = [_frozen_without_designation(tokens[:index]), _frozen_without_designation(tokens[index + width:])]
        markers = [" ".join(tokens[index:index + width])]
        if not parts[1]:
            parts, markers = parts[:1], []
    words = list(parts[0])
    for marker, part in zip(markers, parts[1:]):
        words.extend([marker, *part])
    name = " ".join(words).strip(" ,;:")
    return name if sum(character.isalpha() for character in name) >= 2 else None


_FUZZ_VOCABULARY = [
    "CONTOSO", "NORTHWIND", "AGENCY", "LLC", "LLC,", "INC", "L.L.C.", "CO", "CO.", "PREMIUM", "TRUST", "ACCOUNT",
    "ACCT", "OPERATING", "WIRE", "PRODUCER", "PAYABLE", "ESCROW", "CLIENT", "DBA", "D/B/A", "D", "B", "A", "THE", "OF",
    "&", "100", "SAMPLE", "ATTN", "ATTN:", "C/O", "CASE", "12-345", "TRUST,", "ACCOUNT,", "LTD", "PA", "DMD", "-",
    "–", "X",
]


def test_the_designation_split_keeps_every_name_the_frozen_cut_kept():
    """_split_designation returns (name tokens, title tokens): its first element is the frozen _without_designation's
    cut, byte for byte, and the two together are the tokens (200,000 random token lists, 0 mismatches)."""
    import random

    from analysis import holder_name as hn

    generator = random.Random(7)
    mismatches = 0
    for _ in range(200_000):
        tokens = [generator.choice(_FUZZ_VOCABULARY) for _ in range(generator.randint(0, 9))]
        name, title = hn._split_designation(list(tokens))
        mismatches += (
            name != _frozen_without_designation(list(tokens)) or name + title != tokens
            or hn._without_designation(list(tokens)) != name
        )
    assert mismatches == 0


def test_every_reader_s_name_is_the_frozen_reader_s_name():
    """The readings' names equal the frozen B9 reader's on random name lines (50,000, the DBA split, the contact cut and
    the designation cut included); a reading with no name has no title."""
    import random

    from analysis.holder_name import read_name

    generator = random.Random(11)
    for _ in range(50_000):
        text = " ".join(generator.choice(_FUZZ_VOCABULARY) for _ in range(generator.randint(0, 10)))
        reading = read_name(text)
        assert reading.name == _frozen_name(text.split()), text
        if reading.name is None:
            assert reading.title is None, text


_TITLE_ADDRESS = "PO BOX 100 SAMPLEVILLE SC 29000-0001"


@pytest.mark.parametrize(("line", "holder", "title"), [
    (_FIRST_CITIZENS_HOLDER_LINE, "CONTOSO LLC DBA NORTHWIND AGENCY, LLC", "PREMIUM TRUST ACCOUNT"),
    (f"NORTHWIND INSURANCE AGENCY LLC - PREMIUM TRUST ACCOUNT {_TITLE_ADDRESS}", "NORTHWIND INSURANCE AGENCY LLC",
     "PREMIUM TRUST ACCOUNT"),
    ("NORTHWIND INSURANCE AGENCY LLC – PREMIUM TRUST ACCOUNT 100 SAMPLE ST SAMPLEVILLE SC 29000-0001",
     "NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT"),
    (f"CONTOSO LLC DBA NORTHWIND AGENCY LLC OPERATING ACCOUNT {_TITLE_ADDRESS}", "CONTOSO LLC DBA NORTHWIND AGENCY LLC",
     "OPERATING ACCOUNT"),
    (f"CONTOSO LLC {_TITLE_ADDRESS}", "CONTOSO LLC", None),
    ("NORTHWIND SERVICES TRUST ACCOUNT P O BOX 100 SAMPLEVILLE SC 29000-0001", "NORTHWIND SERVICES", "TRUST ACCOUNT"),
    (f"NORTHWIND AGENCY PREMIUM TRUST ACCOUNT {_TITLE_ADDRESS}", "NORTHWIND AGENCY", "PREMIUM TRUST ACCOUNT"),
    ("FABRIKAM KIDS DENTISTRY INC DBA FABRIKAM DENTISTRY 1000 SAMPLE TRAIL RD STE 100 SAMPLEVILLE GA 30000-0001",
     "FABRIKAM KIDS DENTISTRY INC DBA FABRIKAM DENTISTRY", None),
    (_TITLE_ADDRESS, None, None),
    # The question's own example as a holder line: a name with no legal form keeps its dash (today's name, pinned
    # byte for byte), and the title is read.
    (f"NORTHWIND INSURANCE AGENCY – PREMIUM TRUST ACCOUNT {_TITLE_ADDRESS}", "NORTHWIND INSURANCE AGENCY –",
     "PREMIUM TRUST ACCOUNT"),
    (f"NORTHWIND INSURANCE AGENCY - PREMIUM TRUST ACCOUNT {_TITLE_ADDRESS}", "NORTHWIND INSURANCE AGENCY -",
     "PREMIUM TRUST ACCOUNT"),
    (f"NORTHWIND INSURANCE AGENCY LLC – PREMIUM TRUST ACCOUNT {_TITLE_ADDRESS}", "NORTHWIND INSURANCE AGENCY LLC",
     "PREMIUM TRUST ACCOUNT"),
    # A second trade name printed after the legal form is what the reader drops: it is published as printed (the
    # revenue rule reads only the title forms, R2-OW11).
    ("CONTOSO HOLDINGS LLC PREMIUM TRUST ROOFING 100 MAIN ST SAMPLEVILLE SC 29000-0001", "CONTOSO HOLDINGS LLC",
     "PREMIUM TRUST ROOFING"),
    (f"NORTHWIND INSURANCE AGENCY LLC OPERATING ACCOUNT {_TITLE_ADDRESS}", "NORTHWIND INSURANCE AGENCY LLC",
     "OPERATING ACCOUNT"),
    # A contact after the name is never a title, whatever words it prints.
    (f"CONTOSO INSURANCE AGENCY INC ATTN PREMIUM TRUST DEPT {_TITLE_ADDRESS}", "CONTOSO INSURANCE AGENCY INC", None),
    (f"CONTOSO INSURANCE AGENCY INC ATTN: PREMIUM TRUST ACCOUNT {_TITLE_ADDRESS}", "CONTOSO INSURANCE AGENCY INC", None),
    (f"CONTOSO INSURANCE AGENCY INC C/O PREMIUM TRUST SERVICES LLC {_TITLE_ADDRESS}", "CONTOSO INSURANCE AGENCY INC",
     None),
])
def test_the_address_line_reader_returns_the_title_it_drops(line, holder, title):
    from analysis.holder_name import HolderReading, holder_from_address_line, read_address_line

    assert read_address_line(line) == HolderReading(holder, title)
    assert holder_from_address_line(line) == holder


@pytest.mark.parametrize(("lines", "holder", "title"), [
    (["NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT", "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"],
     "NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT"),
    (["NORTHWIND INSURANCE AGENCY LLC PREMIUM TRUST ACCOUNT", "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"],
     "NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT"),
    (["CONTOSO LLC", "DBA NORTHWIND AGENCY", "PREMIUM TRUST", "PO BOX 100", "SAMPLEVILLE SC 29000-0001"],
     "CONTOSO LLC DBA NORTHWIND AGENCY", "PREMIUM TRUST"),
    # An owner's line is never published.
    (["NORTHWIND INSURANCE AGENCY LLC", "SAMPLE PERSON", "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"],
     "NORTHWIND INSURANCE AGENCY LLC", None),
    (["NORTHWIND INSURANCE AGENCY LLC", "OPERATING ACCOUNT", "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"],
     "NORTHWIND INSURANCE AGENCY LLC", "OPERATING ACCOUNT"),
    # A wrapped name line is the name's.
    (["NORTHWIND HEART &", "VASCULAR LLC", "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"],
     "NORTHWIND HEART & VASCULAR LLC", None),
    (["SAMPLE PERSON", "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"], "SAMPLE PERSON", None),
    # A contact's line is never published, even when it prints the title's words (its first token is the marker,
    # which _without_contact never cuts).
    (["NORTHWIND INSURANCE AGENCY LLC", "ATTN PREMIUM TRUST DEPT", "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"],
     "NORTHWIND INSURANCE AGENCY LLC", None),
    (["NORTHWIND INSURANCE AGENCY LLC", "C/O PREMIUM TRUST ACCOUNTING", "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"],
     "NORTHWIND INSURANCE AGENCY LLC", None),
    (["NORTHWIND INSURANCE AGENCY LLC", "ATTENTION: ACCOUNTS PAYABLE", "100 SAMPLE ST", "SAMPLEVILLE SC 29000-0001"],
     "NORTHWIND INSURANCE AGENCY LLC", None),
    # A title line's own contact after its words is cut, as the holder's is.
    (["NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT ATTN SAMPLE PERSON", "100 SAMPLE ST",
      "SAMPLEVILLE SC 29000-0001"], "NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT"),
    # No street after the name: no reading at all.
    (["NORTHWIND INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT"], None, None),
])
def test_the_address_block_reader_returns_the_title_and_never_an_owner_s_or_a_contact_s_line(lines, holder, title):
    from analysis.holder_name import HolderReading, holder_from_address_block, read_address_block

    assert read_address_block(lines) == HolderReading(holder, title)
    assert holder_from_address_block(lines) == holder


@pytest.mark.parametrize(("name", "holder", "title"), [
    ("NORTHWIND AGENCY PREMIUM TRUST ACCOUNT", "NORTHWIND AGENCY", "PREMIUM TRUST ACCOUNT"),
    ("CONTOSO INC PREMIUM TRUST", "CONTOSO INC", "PREMIUM TRUST"),
    ("CONTOSO TRADING LLC", "CONTOSO TRADING LLC", None),
    ("SAMPLE PERSON", "SAMPLE PERSON", None),
    # A name the reader cannot keep carries no title.
    ("X ACCOUNT", None, None),
    ("", None, None),
])
def test_the_name_reader_returns_the_title_it_drops(name, holder, title):
    from analysis.holder_name import HolderReading, holder_from_name, read_name

    assert read_name(name) == HolderReading(holder, title)
    assert holder_from_name(name) == holder


def test_a_statement_without_a_title_serializes_as_before_and_the_extraction_schema_never_names_one():
    """Statement.account_title is kept out of the extraction response schema and out of every payload that carries no
    title, so no stored payload gains a key it did not have; a title, when read, is serialized and read back."""
    plain = Statement(bank="SAMPLE BANK", holder_name="CONTOSO LLC", transactions=[
        Transaction(date="2054-01-02", description="DEPOSIT", amount=10.0, direction="credit"),
    ], bank_reported_average_balance=5.0)
    assert plain.account_title is None
    assert "account_title" not in plain.model_dump()
    assert "account_title" not in plain.model_dump(mode="json")
    assert "account_title" not in plain.model_dump_json()
    assert plain.model_dump()["stated_average_balance"] == 5.0
    assert "account_title" not in Statement.model_json_schema().get("properties", {})
    titled = plain.model_copy(update={"account_title": "PREMIUM TRUST ACCOUNT"})
    assert titled.model_dump()["account_title"] == "PREMIUM TRUST ACCOUNT"
    assert Statement.model_validate(titled.model_dump()).account_title == "PREMIUM TRUST ACCOUNT"
    assert "account_title" not in titled.model_dump(exclude={"account_title"})
    assert titled.model_dump(exclude={"account_title"}) == plain.model_dump()


# Audit B9 (I13): the other parsers that publish a product name read the holder's line their banks print.

def test_td_bank_reads_the_holder_line_before_its_account_number():
    from analysis import td_us

    header = (
        "STATEMENT OF ACCOUNT\n"
        "Page: 1 of 2 Statement Period: Mar 01 2054-Mar 31 2054 Cust Ref #: 1234567890-000-E-*** "
        "Primary Account #: 123-4567890\n"
        "CONTOSO TRADING LLC 100 SAMPLE AVE UNIT 2 SAMPLEVILLE NJ 07000\n"
        "TD Business Convenience Plus\n"
        "CONTOSO TRADING LLC Account # 123-4567890\n"
        "ACCOUNT SUMMARY Beginning Balance 100.00\n"
    )
    assert td_us._holder_reading(header).name == "CONTOSO TRADING LLC"
    assert td_us._holder_reading(header.replace("CONTOSO TRADING LLC Account #", "Account #")) == (None, None)
    document = td_us_statement_with_holder("CONTOSO TRADING LLC Account # 9999999999\n")
    assert parse_td_us_statement(document).holder_name == "CONTOSO TRADING LLC"


def td_us_statement_with_holder(holder_line: str) -> str:
    """tests/test_parser_crash_shapes.py's fabricated TD Bank document with a holder line."""
    from tests.test_parser_crash_shapes import td_us_document

    return td_us_document().replace("Primary Account #: 9999999999\n", "Primary Account #: 9999999999\n" + holder_line)


@pytest.mark.parametrize(("line", "holder"), [
    ("123-45-67-89  12345   1  C  123  45  S    67  890 CONTOSO TRADING LLC 1000 SAMPLE CIR SAMPLEVILLE FL  34000-0001",
     "CONTOSO TRADING LLC"),
    ("123-45-67-89  12345  U  1  C  123  45  S  T  67  890 NORTHWIND PDR ATTN SAMPLE PERSON 100 S SAMPLE ST STE 1 "
     "SAMPLEVILLE TX  75000-0001", "NORTHWIND PDR"),
    ("123-45-67-89  12345    12  C  123  45       67  890 FABRIKAM CONST PO BOX 1000 SAMPLEVILLE TX  78700-0001",
     "FABRIKAM CONST"),
])
def test_truist_reads_the_holder_after_its_mail_routing_code(line, holder):
    from analysis import truist

    assert truist._holder_reading(f"Page 1 of 2 01/01/54 FL 1234567890123\n{line}\nContact us\n").name == holder
    assert truist._holder_reading("Page 1 of 2\nContact us\n") == (None, None)


def test_pnc_reads_the_holder_before_its_product_summary():
    from analysis import pnc

    for product in ("Business Checking", "Business Checking Plus", "Treasury Enterprise Plan"):
        line = f"CONTOSO TRADING LLC {product} Summary Account number:   XX-XXXX-0000\n"
        assert pnc._holder_reading("PNC Bank\n" + line).name == "CONTOSO TRADING LLC"
    assert pnc._holder_reading("PNC Bank\nBusiness Checking Summary Account number:\n") == (None, None)
    from tests.test_pnc_layouts import TREASURY_DOC

    document = TREASURY_DOC.replace(
        "Balance Summary\n", "CONTOSO TRADING LLC Treasury Enterprise Plan Summary Account number: XX-XXXX-0000\n"
        "Balance Summary\n", 1,
    )
    statement = parse_pnc_statement(document)
    assert statement is not None and statement.holder_name == "CONTOSO TRADING LLC"
    assert statement.account_name == "Treasury Enterprise Plan"


def test_pnc_never_reads_its_own_product_in_capitals_as_the_holder():
    # Audit B9 review round 1: a summary title whose product prints in capitals names no holder.
    from analysis import pnc

    for line in ("TREASURY ENTERPRISE PLAN", "ANALYSIS BUSINESS CHECKING", "BUSINESS CHECKING PLUS",
                 "PNC CORE COMMERCIAL CHECKING"):
        assert pnc._holder_reading(f"PNC Bank\n{line} Summary Account number: XX-XXXX-0000\n") == (None, None)
    line = "CONTOSO TRADING LLC TREASURY ENTERPRISE PLAN Summary Account number: XX-XXXX-0000\n"
    assert pnc._holder_reading("PNC Bank\n" + line).name == "CONTOSO TRADING LLC"


def test_navy_federal_reads_the_holder_from_its_mailing_block():
    from analysis import navy_federal

    block = (
        "Questions about this Statement?\n"
        "CONTOSO TRADING LLC\n"
        "Toll-free in the U.S. 1-888-555-0100\n"
        "1000 SAMPLE CT\n"
        "For toll-free numbers when overseas,\n"
        "SAMPLEVILLE MD 21000-0001\n"
        "visit\n"
        "navyfederal.org/overseas/\n"
    )
    assert navy_federal._holder_reading("Statement of Account\n" + block).name == "CONTOSO TRADING LLC"
    # A block whose first line is already the street names no holder.
    assert navy_federal._holder_reading(
        "Statement of Account\n" + block.replace("CONTOSO TRADING LLC\n", "")
    ) == (None, None)
    from tests.test_declines_c_variants import _navy_federal

    statement = parse_navy_federal_statement(block + _navy_federal("Business Checking"))
    assert statement is not None and statement.holder_name == "CONTOSO TRADING LLC"


@pytest.mark.parametrize(("line", "holder"), [
    ("CONTOSO CONSTRUCTION LTD. 1000 SAMPLE DR SAMPLEVILLE BC V1E 2C3", "CONTOSO CONSTRUCTION LTD."),
    ("1234567 ONTARIO INC 10 SAMPLE CRES SAMPLEVILLE ON L1P 2W3", "1234567 ONTARIO INC"),
    ("SAMPLE DELUXE S.E.N.C. 1000 SAMPLE RUE O SUITE 100 SAMPLEVILLE PQ H1P 2N3", "SAMPLE DELUXE S.E.N.C."),
])
def test_td_canada_trust_reads_the_holder_after_its_mail_routing_code(line, holder):
    from analysis import td_can

    markdown = f"Tel: 1-800-555-0100\nTDCDA12345_1234567_123 E R 12345 12345\n{line}\nStatement of Account\n"
    assert td_can._holder_reading(markdown).name == holder
    assert td_can._holder_reading(markdown.replace("TDCDA12345_1234567_123", "TDXX")) == (None, None)


def test_td_canada_trust_s_native_entry_point_reads_the_holder_too():
    # The registry dispatches the native layout straight to its own entry point, never through
    # parse_td_canada_statement: the holder is read there as well (the frozen oracle of the row reader is untouched).
    from analysis import td_can
    from tests.test_row_grouping import TD_DOCUMENTS

    routing = "TDCDA12345_1234567_123 E R 12345 12345\nCONTOSO CONSTRUCTION LTD. 1000 SAMPLE DR SAMPLEVILLE BC V1E 2C3\n"
    parsed = [td_can.parse_native_td_canada_statement(routing + document) for document in TD_DOCUMENTS]
    assert any(statement is not None for statement in parsed)
    assert all(statement.holder_name == "CONTOSO CONSTRUCTION LTD." for statement in parsed if statement is not None)
    assert all(
        statement is None or statement.holder_name is None
        for statement in map(td_can.parse_native_td_canada_statement, TD_DOCUMENTS)
    )
