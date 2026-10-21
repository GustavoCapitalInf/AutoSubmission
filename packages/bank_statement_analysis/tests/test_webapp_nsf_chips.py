"""The dashboard's two NSF chips (owner request 2026-09-27, "Two chips"), driven end to end: fabricated statements
analysed by the real analysis path, served as the web app serves them (`displayed`, which re-bases the
NSF count in analysis/nsf_days.py and publishes `metrics.nsf_days`), packaged by the real package code, and rendered by
the whole webapp/static/app.js in node on a fake page (tests/webapp_js_harness.py).

"NSFs" lists the days that ended negative on the basis in force, each shown by the posting that ended it, so its count
is always the NSF tile's. "NSF fees" lists what the old chip listed: the rows classified nsf_or_return (the bank's NSF
fee and returned-item lines, evidence only since R18). Every descriptor and amount is fabricated, in whole dollars."""
import json
import re
from pathlib import Path

import pytest

from tests.test_webapp_studio_views import _report, _serve
from tests.webapp_js_harness import NODE, run_dashboard

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

# Opening 100: the 2nd ends -200 (one posting); the 3rd and 4th carry it; the 9th ends -135 after two postings (the
# fee is the last); the 10th and 11th carry it; the 20th goes below zero during the day and ends at +65, which is no
# NSF day. Printed basis: 2 days (the 2nd, the 9th). Carry-over basis: 6 days. Either way two rows show them.
NEGATIVE_ROWS = [(2, "CARD PURCHASE FABRICATED SUPPLY", -300.0), (5, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 1000.0),
                 (9, "CHECK 1041", -900.0), (9, "NSF FEE", -35.0), (12, "DEPOSIT FABRICATED", 500.0),
                 (20, "WIRE TRANSFER OUT FABRICATED VENDOR", -400.0), (20, "DEPOSIT FABRICATED", 100.0)]
NEGATIVE_DAY_ROWS = ["2031-03-02", "2031-03-09"]
# Six NSF fee / returned-item rows on a balance that never goes below zero: the owner's case.
FEE_ROWS = [(3, "NSF FEE", -35.0), (6, "RETURNED ITEM FEE", -35.0), (9, "NSF FEE", -35.0), (12, "NSF FEE", -35.0),
            (15, "UNPAID ITEM FEE", -35.0), (18, "NSF FEE", -35.0), (20, "DEPOSIT FABRICATED", 800.0)]
# One day below zero, on either basis.
ONE_DAY_ROWS = [(2, "CARD PURCHASE FABRICATED SUPPLY", -300.0), (3, "DEPOSIT FABRICATED", 1000.0)]
# A second account whose rows sit at the same locations as the negative account's, on a positive balance.
SAVINGS_ROWS = [(3, "INTEREST PAID", 2.0), (6, "DEPOSIT FABRICATED", 100.0), (9, "DEPOSIT FABRICATED", 100.0),
                (12, "DEPOSIT FABRICATED", 100.0)]


def _settings(carry_over=False):
    from webapp.settings import DEFAULTS
    return {**DEFAULTS, "nsf_carry_over": carry_over}


def _analysis(rows, opening, month=3):
    from analysis.serialization import document_report_to_dict
    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", opening, rows, month))


def _served(payload, carry_over=False):
    """The analysis as /analysis/<job> serves it: the owner's Settings applied to a copy."""
    from analysis.served_view import displayed
    return displayed(payload, settings=_settings(carry_over))


def _two_accounts():
    """One statement of two accounts: business checking (the main account, with the negative days) and savings."""
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.serialization import document_report_to_dict

    checking = _report("FABRICATED BUSINESS CHECKING", "000000001010", 100.0, NEGATIVE_ROWS).accounts[0]
    savings = _report("FABRICATED SAVINGS", "000000002020", 9000.0, SAVINGS_ROWS).accounts[0]
    roster = [AccountRosterEntry("FABRICATED BUSINESS CHECKING", "checking", "1010", "published", published_index=0),
              AccountRosterEntry("FABRICATED SAVINGS", "savings", "2020", "published", published_index=1)]
    transfers, notes = identify_internal_transfers([checking, savings])
    return document_report_to_dict(DocumentReport(accounts=[checking, savings],
                                                  document_period=("2031-03-01", "2031-03-28"),
                                                  internal_transfers=transfers, integrity_notes=notes,
                                                  account_roster=roster))


def _package(analyses, tmp_path, monkeypatch, carry_over=False):
    """The real package payload (job id -> stored analysis), built on the given NSF basis."""
    from webapp.app import store
    from analysis.package import package_analysis
    from webapp.jobs import Job

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    return package_analysis([Job(id=job_id, filename=f"fabricated-{job_id}.pdf", status="done", analysis=analysis,
                                 content_sha256=job_id) for job_id, analysis in analyses.items()],
                            settings=_settings(carry_over))


# ---------------------------------------------------------------- the server: package members carry their days

@pytest.mark.parametrize(("carry_over", "days"), [(False, 2), (True, 6)], ids=["printed", "carry-over"])
def test_each_package_member_carries_the_days_its_count_counts(tmp_path, monkeypatch, carry_over, days):
    package = _package({"neg": _analysis(NEGATIVE_ROWS, 100.0), "fees": _analysis(FEE_ROWS, 5000.0, month=4)},
                       tmp_path, monkeypatch, carry_over)
    documents = {doc["id"]: doc for doc in package["documents"]}
    assert len(documents["neg"]["nsf_days"]) == documents["neg"]["nsf_count"] == days
    assert {day["source_location"] for day in documents["neg"]["nsf_days"]} == {"transaction:1", "transaction:4"}
    assert documents["fees"]["nsf_days"] == [] and documents["fees"]["nsf_count"] == 0
    # The package's NSF figure is unchanged: the members' counts, summed.
    assert package["totals"]["nsf_count"] == sum(len(doc["nsf_days"]) for doc in documents.values()) == days


def test_each_account_of_a_package_member_carries_its_own_days(tmp_path, monkeypatch):
    package = _package({"doc": _two_accounts()}, tmp_path, monkeypatch)
    documents = {doc["id"]: doc for doc in package["documents"]}
    assert [len(documents[key]["nsf_days"]) for key in ("doc#account_1", "doc#account_2")] == [2, 0]
    assert package["totals"]["nsf_count"] == 2


def test_the_dashboard_is_served_the_days_and_no_download_carries_them(tmp_path, monkeypatch):
    from webapp.app import app, store

    monkeypatch.setattr(store.storage, "data_dir", tmp_path)  # the default NSF basis: printed days
    jobs = []
    for name, analysis in (("neg", _analysis(NEGATIVE_ROWS, 100.0)), ("fees", _analysis(FEE_ROWS, 5000.0, month=4))):
        job = store.create(f"fabricated-{name}.pdf")
        store.set_result(job.id, "# fabricated", "<h1>fabricated</h1>", analysis=analysis)
        jobs.append(job.id)
    client = app.test_client()
    served = client.get(f"/analysis/{jobs[0]}").get_json()["analysis"]["metrics"]
    assert len(served["nsf_days"]) == served["effective_nsf_count"] == 2
    package = client.get(f"/package_analysis?ids={','.join(jobs)}").get_json()
    assert [len(doc["nsf_days"]) for doc in package["documents"]] == [2, 0]
    # The downloads carry what they carried before the chip: the counts, never the listed days.
    for fmt in ("json", "csv"):
        body = client.get(f"/download/{jobs[0]}/{fmt}").get_data(as_text=True)
        assert "nsf_days" not in body and "effective_nsf_count" in body
        body = client.get(f"/package_download/{fmt}?ids={','.join(jobs)}").get_data(as_text=True)
        assert "nsf_days" not in body and "nsf_count" in body
    for url in (f"/download/{jobs[0]}/xlsx", f"/package_download/xlsx?ids={','.join(jobs)}"):
        response = client.get(url)
        assert response.status_code == 200 and response.get_data()[:2] == b"PK"


# ---------------------------------------------------------------- the chips

def test_both_ledgers_offer_nsfs_then_nsf_fees():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    for attribute in ("data-transaction-filter", "data-modal-transaction-filter"):
        chips = re.findall(rf'{attribute}="([a-z_]+)">([^<]*)</button>', html)
        keys = [key for key, _ in chips]
        assert ("nsf", "NSFs") in chips and ("nsf_fees", "NSF fees") in chips
        assert keys.index("nsf_fees") == keys.index("nsf") + 1


ROWS = r"""
const rowsOf = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((match) => match[1]);
const datesOf = (html) => rowsOf(html).map((row) => (row.match(/<td class="tx-date">([^<]*)<\/td>/) || [])[1])
  .filter(Boolean);
const descriptionsOf = (html) => rowsOf(html).map((row) => (row.match(/<td class="tx-desc">([^<]*)<\/td>/) || [])[1])
  .filter(Boolean);
const tile = () => (els.totalsGrid.innerHTML.match(
  /<span class="total-label">NSFs<\/span>\s*<span class="total-value[^"]*" title="[^"]*">([^<]*)<\/span>/) || [])[1];
const main = (filter) => {
  transactionFilter = filter; renderMainTransactions();
  return {count: els.transactionCount.textContent, dates: datesOf(els.transactionTable.innerHTML),
          descriptions: descriptionsOf(els.transactionTable.innerHTML), empty: els.transactionTable.innerHTML
            .includes('class="empty-cell"') ? els.transactionTable.innerHTML.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim() : null};
};
const modal = (filter) => {
  modalTransactionFilter = filter; renderModalTransactions();
  return {count: els.statementModalTransactionCount.textContent,
          dates: datesOf(els.statementModalTransactions.innerHTML)};
};
const modalTile = () => (els.statementModalMetrics.innerHTML.match(
  /<div class="metric-label">NSFs<\/div>[\s\S]*?<div class="metric-value">([^<]*)<\/div>/) || [])[1];
"""


def _load(job_id, payload):
    return _serve(**{job_id: payload}) + (f"currentJobId = '{job_id}'; currentJobIds = ['{job_id}'];"
                                         f" loadResults('{job_id}'); await settle();\n")


CHIPS = """
console.log(JSON.stringify({tile: tile(), nsf: main('nsf'), fees: main('nsf_fees'), all: main('all').count}));
"""


@needs_node
@pytest.mark.parametrize("carry_over", [False, True], ids=["printed", "carry-over"])
def test_six_fee_rows_on_a_balance_that_never_ends_negative_show_no_nsf_day(carry_over):
    served = _served(_analysis(FEE_ROWS, 5000.0), carry_over)
    result = run_dashboard(ROWS + _load("fees", served) + CHIPS)
    assert result["tile"] == "0"
    assert result["nsf"]["count"] == "0 days ending negative" and result["nsf"]["dates"] == []
    assert "No day ended with a negative balance" in result["nsf"]["empty"]
    assert result["fees"]["count"] == "6 NSF fee rows"
    assert result["fees"]["dates"] == ["2031-03-03", "2031-03-06", "2031-03-09", "2031-03-12", "2031-03-15",
                                       "2031-03-18"]
    assert result["all"] == "7 transactions"


@needs_node
@pytest.mark.parametrize(("carry_over", "days"), [(False, "2"), (True, "6")], ids=["printed", "carry-over"])
def test_the_nsfs_chip_shows_each_negative_day_by_the_row_that_ended_it(carry_over, days):
    served = _served(_analysis(NEGATIVE_ROWS, 100.0), carry_over)
    result = run_dashboard(ROWS + _load("neg", served) + CHIPS)
    # The chip counts days, always the tile's figure; one row may show several days, and is shown once.
    assert result["tile"] == days
    assert result["nsf"]["count"] == f"{days} days ending negative"
    assert result["nsf"]["dates"] == NEGATIVE_DAY_ROWS
    # The 9th is shown by its last posting, the fee; the 20th went below zero during the day only.
    assert result["nsf"]["descriptions"] == ["CARD PURCHASE FABRICATED SUPPLY", "NSF FEE"]
    assert result["fees"] == {"count": "1 NSF fee row", "dates": ["2031-03-09"], "descriptions": ["NSF FEE"],
                              "empty": None}


@needs_node
def test_one_negative_day_reads_in_the_singular():
    result = run_dashboard(ROWS + _load("one", _served(_analysis(ONE_DAY_ROWS, 100.0))) + CHIPS)
    assert result["tile"] == "1"
    assert result["nsf"]["count"] == "1 day ending negative" and result["nsf"]["dates"] == ["2031-03-02"]


@needs_node
def test_a_count_without_a_validated_ledger_says_so():
    served = _served(_analysis(NEGATIVE_ROWS, 100.0))
    served["metrics"].update({"nsf_source": "negative_ending_days_unavailable", "effective_nsf_count": 0,
                              "nsf_days": []})
    result = run_dashboard(ROWS + _load("gone", served) + CHIPS)
    assert result["nsf"]["count"] == "NSF days not computable: no validated daily ledger"
    assert result["nsf"]["dates"] == []
    assert result["fees"]["count"] == "1 NSF fee row"


@needs_node
def test_a_count_the_ledger_cannot_list_keeps_the_tiles_figure_and_says_why():
    served = _served(_analysis(NEGATIVE_ROWS, 100.0))
    served["metrics"]["nsf_days"] = []
    result = run_dashboard(ROWS + _load("unlisted", served) + CHIPS)
    assert result["tile"] == "2"
    assert result["nsf"]["count"].startswith("2 days ending negative")
    assert "not listed" in result["nsf"]["count"]


@needs_node
def test_the_statement_window_offers_the_same_two_chips():
    served = {"neg": _served(_analysis(NEGATIVE_ROWS, 100.0), carry_over=True),
              "fees": _served(_analysis(FEE_ROWS, 5000.0), carry_over=True)}
    result = run_dashboard(ROWS + _serve(**served) + """
openStatementModal('neg'); await settle();
const neg = {tile: modalTile(), nsf: modal('nsf'), fees: modal('nsf_fees')};
openStatementModal('fees'); await settle();
const fees = {tile: modalTile(), nsf: modal('nsf'), fees: modal('nsf_fees')};
console.log(JSON.stringify({neg, fees}));
""")
    assert result["neg"] == {"tile": "6", "nsf": {"count": "6 days ending negative", "dates": NEGATIVE_DAY_ROWS},
                             "fees": {"count": "1 NSF fee row", "dates": ["2031-03-09"]}}
    assert result["fees"]["tile"] == "0"
    assert result["fees"]["nsf"] == {"count": "0 days ending negative", "dates": []}
    assert result["fees"]["fees"]["count"] == "6 NSF fee rows"


PACKAGE = """
currentJobIds = %s; renderPackageAnalysis(%s);
console.log(JSON.stringify({tile: tile(), nsf: main('nsf'), fees: main('nsf_fees')}));
"""


@needs_node
@pytest.mark.parametrize(("carry_over", "days"), [(False, "2"), (True, "6")], ids=["printed", "carry-over"])
def test_a_package_of_two_statements_shows_each_members_own_rows(tmp_path, monkeypatch, carry_over, days):
    # The fee statement's rows 1 and 4 sit at the same locations as the rows that ended the other statement's negative
    # days: only the member whose days they are shows them.
    package = _package({"neg": _analysis(NEGATIVE_ROWS, 100.0), "fees": _analysis(FEE_ROWS, 5000.0, month=4)},
                       tmp_path, monkeypatch, carry_over)
    result = run_dashboard(ROWS + PACKAGE % (json.dumps(["neg", "fees"]), json.dumps(package)))
    assert result["tile"] == days == str(package["totals"]["nsf_count"])
    assert result["nsf"]["count"] == f"{days} days ending negative"
    assert result["nsf"]["dates"] == NEGATIVE_DAY_ROWS
    assert result["fees"]["count"] == "7 NSF fee rows"
    assert result["fees"]["dates"] == ["2031-03-09", "2031-04-03", "2031-04-06", "2031-04-09", "2031-04-12",
                                       "2031-04-15", "2031-04-18"]


@needs_node
def test_a_package_member_of_two_accounts_shows_only_the_rows_of_the_account_whose_days_they_are(tmp_path,
                                                                                                    monkeypatch):
    package = _package({"doc": _two_accounts()}, tmp_path, monkeypatch)
    result = run_dashboard(ROWS + PACKAGE % (json.dumps(["doc"]), json.dumps(package)))
    assert result["tile"] == "2"
    assert result["nsf"]["count"] == "2 days ending negative"
    assert result["nsf"]["descriptions"] == ["CARD PURCHASE FABRICATED SUPPLY", "NSF FEE"]
