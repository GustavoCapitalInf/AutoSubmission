"""The package's Monthly Statements table (owner request, 2026-09-22): the CRM's seasonality columns. The
server supplies each statement's deposit count beside its deposit total. Fabricated payloads only."""
from tests.test_package_currency import statement_payload
from analysis.package import package_analysis
from webapp.jobs import Job


def _member(job_id, **metrics):
    payload = statement_payload("USD")
    payload["metrics"].update(metrics)
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


def test_each_statement_row_carries_the_deposit_count_that_pairs_with_its_deposit_total():
    package = package_analysis([_member("a", effective_num_deposits=134), _member("b", effective_num_deposits=139)])
    assert [row["deposit_count"] for row in package["documents"]] == [134, 139]
    assert [row["credits"] for row in package["documents"]] == [10_000.0, 10_000.0]


def test_a_statement_without_a_deposit_count_shows_none_rather_than_zero():
    package = package_analysis([_member("a")])
    assert package["documents"][0]["deposit_count"] is None


def test_a_non_integer_count_is_not_trusted():
    package = package_analysis([_member("a", effective_num_deposits=True), _member("b", effective_num_deposits="12")])
    assert [row["deposit_count"] for row in package["documents"]] == [None, None]


def _stated_member(job_id, *, line_item_total, stated_count=None, count=3):
    # The bank printed its deposit total (10,000); the parser captured `count` rows summing to line_item_total.
    payload = statement_payload("USD")
    payload["metrics"].update(effective_num_deposits=count if stated_count is None else stated_count,
                              num_deposits=count, total_deposits=line_item_total,
                              deposits_source="bank_stated_unverified")
    payload["statement"]["stated_credit_count"] = stated_count
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


def test_a_line_item_count_is_not_shown_beside_a_bank_total_it_does_not_cover():
    # Review finding: many parsers read the bank's printed TOTAL but not its printed COUNT; the count beside
    # it would then be the captured rows, which may not add up to that total.
    package = package_analysis([_stated_member("a", line_item_total=6_000.0)])
    assert package["documents"][0]["deposit_count"] is None


def test_the_line_item_count_pairs_when_its_rows_add_up_to_the_bank_total():
    package = package_analysis([_stated_member("a", line_item_total=10_000.0)])
    assert package["documents"][0]["deposit_count"] == 3


def test_the_banks_own_printed_count_always_pairs_with_its_total():
    package = package_analysis([_stated_member("a", line_item_total=6_000.0, stated_count=7)])
    assert package["documents"][0]["deposit_count"] == 7
