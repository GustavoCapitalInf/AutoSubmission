"""The extraction receipt of a PDF nothing could be read from says so (owner-approved wording, 2026-10-15): a scanned or
image-only PDF with no usable native text, on which local OCR read no usable statement text either, reads
"Not read: no usable text" in the banner and "Local OCR: no usable text" in its rows, not "Extraction available;
metrics withheld" and "OCR completed: Yes". That state only: a document that was read and held for review, and a
statement that was read, keep their labels. The refusal sentence itself is one of the five approved texts and does not
change.

The whole dashboard script runs in node on a fake page (tests/webapp_js_harness.py) and draws each result through the
real `loadResults` path, as an upload or a reopen from Recent does. Fabricated data only."""
import json
import re

import pytest

from tests.webapp_js_harness import NODE, run_dashboard

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

#: The approved no-usable-text refusal sentence (`friendlyAnalysisError`), unchanged by the new labels.
NO_TEXT_SENTENCE = ("This PDF has no usable native text, and local OCR on this machine could not read usable statement "
                    "text from its pages.")
#: The shape a job stored before the model removal carries: the same prefix, then the retired advice.
STORED_WITH_RETIRED_ADVICE = ("native PDF text unavailable or too sparse, and local Tesseract OCR did not produce usable "
                              "statement text; turn on Force visual OCR to use the OCR service, or use Auto mode")
NOT_READ_TITLE = "Not read: no usable text"
NOT_READ_ROW = ["Local OCR", "no usable text"]
HELD_TITLE = "Extraction available; metrics withheld"
HELD_ROWS = [["OCR completed", "Yes"], ["Validation", "Review required"], ["Metrics", "Withheld"]]

_KV = re.compile(r'<span class="kv-key">(.*?)</span>\s*<span class="kv-value"[^>]*>(.*?)</span>', re.S)


def _rows(html):
    return [[key.strip(), value.strip()] for key, value in _KV.findall(html)]


def _held(job_id, message):
    return {f"/analysis/{job_id}": {"json": {"analysis": None, "analysis_error": message}},
            f"/markdown/{job_id}": {"text": "fabricated reading"}}


def _read_statement():
    """A fabricated statement the real analysis path reads and approves (invented bank, a 2054 period, whole dollars)."""
    from analysis.pipeline import analyze_statement
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction
    from analysis.serialization import document_report_to_dict

    rows = [(2, "ACH CREDIT FABRICATED CUSTOMER", 2400.0), (6, "CARD PURCHASE FABRICATED SUPPLY", -300.0),
            (14, "DEPOSIT FABRICATED", 1100.0), (27, "SERVICE FEE", -20.0)]
    transactions, balance = [], 1000.0
    for day, description, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=f"2054-03-{day:02d}", description=description, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(bank="FABRICATED SAVINGS BANK", account_name="FABRICATED BUSINESS CHECKING",
                          account_number="000000003030", period_start="2054-03-01", period_end="2054-03-31",
                          beginning_balance=1000.0, ending_balance=balance, currency="USD", currency_source="printed",
                          transactions=transactions)
    report = analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                               model_used="fabricated-test")
    return document_report_to_dict(report)


_RECEIPT = """
const receipt = () => ({title: els.statusCopy.textContent, heading: els.statusHeading.textContent,
  validation: els.validationValue.textContent, rows: els.statusList.innerHTML, processing: els.processingList.innerHTML,
  message: els.statusMessage.hidden ? "" : els.statusMessage.textContent, pill: els.decisionPill.textContent});
"""


def _draw(responses, job_ids):
    """Draw each job in turn through `loadResults` and return each one's receipt."""
    steps = "".join(f"currentJobId = {json.dumps(job_id)}; currentJobIds = [{json.dumps(job_id)}]; "
                    f"loadResults({json.dumps(job_id)}); await settle(); drawn.push(receipt());\n"
                    for job_id in job_ids)
    return run_dashboard(f"Object.assign(FAKE_RESPONSES, {json.dumps(responses)});\n" + _RECEIPT
                         + "const drawn = [];\n" + steps + "console.log(JSON.stringify(drawn));")


@pytest.mark.parametrize("message", [
    pytest.param(None, id="the worker's refusal"),
    pytest.param(STORED_WITH_RETIRED_ADVICE, id="a job stored with the retired advice"),
    pytest.param("native text too sparse", id="too sparse"),
    pytest.param("no native text", id="no native text"),
])
def test_a_pdf_nothing_could_be_read_from_says_it_was_not_read(message):
    from webapp.worker import NO_USABLE_TEXT

    [receipt] = _draw(_held("unread", message or NO_USABLE_TEXT), ["unread"])
    assert receipt["title"] == NOT_READ_TITLE
    rows = _rows(receipt["rows"])
    assert rows == [NOT_READ_ROW, ["Validation", "Review required"], ["Metrics", "Withheld"]], rows
    assert _rows(receipt["processing"]) == rows  # the results page's Processing list repeats the same rows
    assert "OCR completed" not in receipt["rows"] and "Extraction available" not in json.dumps(receipt)
    # The approved refusal sentence is unchanged and still leads the explanation; nothing else moved.
    assert receipt["message"].startswith(NO_TEXT_SENTENCE + " Open Review extraction"), receipt["message"]
    assert "visual" not in receipt["message"].lower()
    assert (receipt["heading"], receipt["validation"], receipt["pill"]) == (
        "Extraction needs review", "Review required", "Review required")


@pytest.mark.parametrize("message, sentence", [
    pytest.param("no deterministic parser matched this statement",
                 "No deterministic parser matched this statement. Nothing was guessed; this layout needs a parser before "
                 "it can be analysed.", id="read, no parser matched"),
    pytest.param("visual pair requires human review", "Visual pair requires human review.",
                 id="a stored held read"),
])
def test_a_document_that_was_read_and_held_for_review_keeps_its_labels(message, sentence):
    [receipt] = _draw(_held("held", message), ["held"])
    assert receipt["title"] == HELD_TITLE
    assert _rows(receipt["rows"]) == HELD_ROWS
    assert "Local OCR" not in receipt["rows"] and "Not read" not in json.dumps(receipt)
    assert receipt["message"].startswith(sentence + " Open Review extraction"), receipt["message"]


def test_a_statement_that_was_read_keeps_its_labels_after_an_unread_one():
    from webapp.worker import NO_USABLE_TEXT

    responses = {**_held("unread", NO_USABLE_TEXT),
                 "/analysis/read": {"json": {"analysis": _read_statement(), "analysis_error": None}},
                 "/markdown/read": {"text": ""}}
    unread, read, unread_again = _draw(responses, ["unread", "read", "unread"])
    assert unread["title"] == NOT_READ_TITLE and _rows(unread["rows"])[0] == NOT_READ_ROW
    assert read["title"] == "Extraction completed" and read["heading"] == "OCR completed"
    rows = _rows(read["rows"])
    assert rows[0] == ["OCR completed", "Yes"], rows
    assert "Local OCR" not in read["rows"] and "Not read" not in json.dumps(read)
    # Reopening the unread one from Recent draws the same receipt again.
    assert unread_again["title"] == NOT_READ_TITLE and _rows(unread_again["rows"]) == _rows(unread["rows"])
