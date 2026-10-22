"""A statement whose main account (its business checking account) was not verified never enters a package's
figures through another of its accounts (review 8, finding 6). Fabricated payloads."""
from tests.l1s3_payloads import account_payload


class _Job:
    def __init__(self, ident, analysis):
        self.id, self.analysis = ident, analysis


def _roster(checking_status):
    return {"account_count": 2, "account_roster": [
        {"title": "FABRICATED SAVINGS", "kind": "savings", "number_last4": "0001", "status": "published",
         "published_index": 0, "balance": None, "reasons": []},
        {"title": "FABRICATED BUSINESS CHECKING", "kind": "checking", "number_last4": "0010",
         "status": checking_status, "published_index": None, "balance": None, "reasons": []},
    ]}


def test_a_statement_whose_business_checking_account_is_held_is_left_out_of_the_package():
    from analysis.package.members import package_members
    payload = {**account_payload(), "document": _roster("held")}
    members, excluded = package_members([_Job("job-1", payload)])
    # Audit round 2, R2-B15 (R15): the entry names its statement's file (None for this job, which carries no filename).
    assert members == [] and excluded == [{"job_id": "job-1", "filename": None, "account_index": None,
                                           "account_count": 2, "outcome": "withheld",
                                           "reason": "main_account_unverified"}]


def test_a_held_account_whose_title_names_no_kind_or_ranks_first_is_the_main_account():
    # Review 9, finding 4: a product title without a kind word ("... Advantage Account") can be the operating account;
    # among savings and money market, a held one leaves the main account undetermined. Cards and loans never rank.
    from analysis.package.members import _unverified_main_account, package_members
    def roster(*entries):
        return [{"title": title, "kind": kind, "status": status} for title, kind, status in entries]
    assert _unverified_main_account(roster(("FABRICATED ADVANTAGE ACCOUNT", None, "held"),
                                           ("FABRICATED SAVINGS", "savings", "published")))["kind"] is None
    assert _unverified_main_account(roster(("FABRICATED MONEY MARKET", "money_market", "held"),
                                           ("FABRICATED SAVINGS", "savings", "published"))) is not None
    assert _unverified_main_account(roster(("FABRICATED VISA", "credit_card", "held"),
                                           ("FABRICATED SAVINGS", "savings", "published"))) is None
    assert _unverified_main_account(roster(("FABRICATED BUSINESS CHECKING", "checking", "published"),
                                           ("FABRICATED ADVANTAGE ACCOUNT", None, "held"))) is None
    assert _unverified_main_account(roster(("FABRICATED CHECKING", "checking", "idle"),
                                           ("FABRICATED SAVINGS", "savings", "published"))) is None
    # Review 10, finding 5: a checking account ranks above an untyped one; cards alone set no main account.
    assert _unverified_main_account(roster(("FABRICATED BUSINESS CHECKING", "checking", "published"),
                                           ("FABRICATED BUSINESS MERCHANT SERVICES", None, "held"))) is None
    assert _unverified_main_account(roster(("FABRICATED CHECKING", "checking", "held"),
                                           ("FABRICATED BUSINESS ADVANTAGE ACCOUNT", None, "published")))["kind"] == \
        "checking"
    assert _unverified_main_account(roster(("FABRICATED VISA", "credit_card", "held"),
                                           ("FABRICATED MASTERCARD", "credit_card", "published"))) is None
    payload = {**account_payload(), "document": {"account_roster": roster(
        ("FABRICATED ADVANTAGE ACCOUNT", None, "held"), ("FABRICATED SAVINGS", "savings", "published"))}}
    members, excluded = package_members([_Job("job-1", payload)])
    assert members == [] and excluded[0]["reason"] == "main_account_unverified"


def test_an_idle_business_checking_account_needs_review_and_leaves_the_statement_out_of_the_package():
    # Owner ruling, 2026-09-23: an idle main account needs review (the dashboard keeps showing the active account).
    from analysis.package.members import _idle_main_account, package_members
    def roster(*entries):
        return [{"title": title, "kind": kind, "status": status} for title, kind, status in entries]
    idle = roster(("FABRICATED BUSINESS CHECKING", "checking", "idle"), ("FABRICATED SAVINGS", "savings", "published"))
    assert _idle_main_account(idle)["kind"] == "checking"
    # The business checking account stays the main account over a plain checking account that moved money.
    assert _idle_main_account(roster(("FABRICATED BUSINESS CHECKING", "checking", "idle"),
                                     ("FABRICATED CHECKING", "checking", "published")))["status"] == "idle"
    for active in (roster(("FABRICATED CHECKING", "checking", "idle"),
                          ("FABRICATED BUSINESS CHECKING", "checking", "published")),
                   roster(("FABRICATED BUSINESS CHECKING", "checking", "idle"),
                          ("FABRICATED BUSINESS CHECKING 2", "checking", "published")),
                   roster(("FABRICATED SAVINGS", "savings", "idle"), ("FABRICATED CHECKING", "checking", "published")),
                   roster(("FABRICATED CARD", "credit_card", "idle"))):
        assert _idle_main_account(active) is None, active
    members, excluded = package_members([_Job("job-1", {**account_payload(), "document": {"account_roster": idle}})])
    assert members == [] and excluded[0]["reason"] == "main_account_idle"


def test_a_statement_whose_business_checking_account_is_verified_or_that_prints_one_account_is_a_member():
    from analysis.package.members import package_members
    verified = {**account_payload(), "document": _roster("published")}
    members, excluded = package_members([_Job("job-1", verified), _Job("job-2", account_payload())])
    assert [member.job.id for member in members] == ["job-1", "job-2"] and excluded == []


# test_each_published_account_takes_its_own_verification_score pinned webapp/worker.py's _attach_account_confidence,
# the visual pair's per-account score; it left with the worker's pair read (model-code removal, slice S1). A stored
# job's per-account `visual_pair_confidence` is served as stored, and the package rule above is unchanged.
