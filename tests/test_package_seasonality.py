"""The package's Monthly Statements table (owner request, 2026-09-22): the CRM's seasonality columns. The
server supplies each statement's deposit count beside its deposit total. Fabricated payloads only."""
from tests.test_package_currency import statement_payload
from webapp.app import _package_analysis
from webapp.jobs import Job


def _member(job_id, **metrics):
    payload = statement_payload("USD")
    payload["metrics"].update(metrics)
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


def test_each_statement_row_carries_the_deposit_count_that_pairs_with_its_deposit_total():
    package = _package_analysis([_member("a", effective_num_deposits=134), _member("b", effective_num_deposits=139)])
    assert [row["deposit_count"] for row in package["documents"]] == [134, 139]
    assert [row["credits"] for row in package["documents"]] == [10_000.0, 10_000.0]


def test_a_statement_without_a_deposit_count_shows_none_rather_than_zero():
    package = _package_analysis([_member("a")])
    assert package["documents"][0]["deposit_count"] is None


def test_a_non_integer_count_is_not_trusted():
    package = _package_analysis([_member("a", effective_num_deposits=True), _member("b", effective_num_deposits="12")])
    assert [row["deposit_count"] for row in package["documents"]] == [None, None]
