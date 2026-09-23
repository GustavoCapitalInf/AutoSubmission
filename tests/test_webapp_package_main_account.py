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
    from webapp.app import _package_members
    payload = {**account_payload(), "document": _roster("held")}
    members, excluded = _package_members([_Job("job-1", payload)])
    assert members == [] and excluded == [{"job_id": "job-1", "account_index": None, "account_count": 2,
                                           "outcome": "withheld", "reason": "main_account_unverified"}]


def test_a_held_account_whose_title_names_no_kind_or_ranks_first_is_the_main_account():
    # Review 9, finding 4: a product title without a kind word ("... Advantage Account") can be the operating account;
    # among savings and money market, a held one leaves the main account undetermined. Cards and loans never rank.
    from webapp.app import _package_members, _unverified_main_account
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
    payload = {**account_payload(), "document": {"account_roster": roster(
        ("FABRICATED ADVANTAGE ACCOUNT", None, "held"), ("FABRICATED SAVINGS", "savings", "published"))}}
    members, excluded = _package_members([_Job("job-1", payload)])
    assert members == [] and excluded[0]["reason"] == "main_account_unverified"


def test_a_statement_whose_business_checking_account_is_verified_or_that_prints_one_account_is_a_member():
    from webapp.app import _package_members
    verified = {**account_payload(), "document": _roster("published")}
    members, excluded = _package_members([_Job("job-1", verified), _Job("job-2", account_payload())])
    assert [member[0].id for member in members] == ["job-1", "job-2"] and excluded == []


def test_each_published_account_takes_its_own_verification_score():
    from tests.l1s3_payloads import document_payload
    from webapp.worker import _attach_account_confidence
    scores = {"accounts": [{"confidence": {"score": 0.125}}, {"confidence": {"score": 0.625}},
                           {"confidence": {"score": 0.875}}]}
    document = document_payload()
    document["document"]["account_roster"] = [
        {"status": "published", "published_index": 0}, {"status": "held", "published_index": None},
        {"status": "published", "published_index": 1}]
    _attach_account_confidence(document, scores)
    assert [account["visual_pair_confidence"] for account in document["accounts"]] == [{"score": 0.125},
                                                                                       {"score": 0.875}]
    single = {**account_payload(), "document": {"account_roster": [
        {"status": "held", "published_index": None}, {"status": "published", "published_index": 0},
        {"status": "idle", "published_index": None}]}}
    _attach_account_confidence(single, scores)
    assert single["visual_pair_confidence"] == {"score": 0.625}
