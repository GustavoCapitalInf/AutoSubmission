"""The surface census must FAIL when doctored — in both directions.

The re-review's point, kept as a test: a list that cannot fail is not an exit
criterion. So the census is doctored four ways here — a declared reader whose
branch is gone, a declared reader that is not there at all, a site that reads
the payload key and is not declared, and a seam that publishes one account —
and each must be reported.
"""
from __future__ import annotations

import pytest

from tools import l1s3_surface_census as census


def test_the_census_holds_at_this_tree():
    reader_failures, _notes, sites = census.census_readers()
    seam_failures, _notes2, seams = census.census_seams()
    assert reader_failures == []
    assert seam_failures == []
    assert sites > 0, "a census that swept nothing proves nothing"
    assert seams, "every production seam publishes through the document entry point"


def test_a_taught_reader_whose_branch_is_gone_fails_it(monkeypatch):
    """FORWARD. `_masked` genuinely never reads the account key, so declaring
    it `refuses` is exactly the state of a reader whose refusal was deleted."""
    monkeypatch.setattr(census, "READERS", (
        ("webapp/app.py", "_masked", "refuses", "doctored"),
    ))
    failures, _notes, _sites = census.census_readers()
    assert any("never calls" in failure and "_masked" in failure
               for failure in failures)


def test_a_declared_reader_that_is_not_there_fails_it(monkeypatch):
    """FORWARD, the other way: the list may not name a reader the tree lost."""
    monkeypatch.setattr(census, "READERS", (
        ("webapp/app.py", "_a_reader_that_does_not_exist", "refuses", "doctored"),
    ))
    failures, _notes, _sites = census.census_readers()
    assert any("is not defined there" in failure for failure in failures)


def test_a_reader_the_list_does_not_know_about_fails_it(monkeypatch):
    """REVERSE — the direction that makes the zero non-vacuous.

    Every declaration is withdrawn, which is the same state the tree would be
    in if someone wrote a new payload reader and told the list nothing.
    """
    monkeypatch.setattr(census, "READERS", ())
    monkeypatch.setattr(census, "EXCUSED", {})
    failures, _notes, _sites = census.census_readers()
    assert failures
    assert any("neither a declared reader nor an excused site" in failure
               for failure in failures)


def test_an_agnostic_reader_that_starts_reading_the_key_fails_it(monkeypatch):
    """`_analysis_rows` reads the key through its account half, so declaring it
    `agnostic` is the state of a reader that quietly grew a statement read."""
    monkeypatch.setattr(census, "READERS", (
        ("analysis/revenue.py", "_rebuild_account_revenue_views", "agnostic",
         "doctored"),
    ))
    failures, _notes, _sites = census.census_readers()
    assert any("declared `agnostic` but it reads" in failure for failure in failures)


def test_a_seam_that_publishes_one_account_fails_it(tmp_path, monkeypatch):
    """The seam half, doctored in the TREE rather than in the list: a module
    that publishes through the single-account serializer is what a document
    with three accounts would be published one of through."""
    doctored = tmp_path / "doctored_seam.py"
    doctored.write_text(
        "def publish(report):\n    return report_to_dict(report)\n",
        encoding="utf-8")
    monkeypatch.setattr(census, "REPO", tmp_path)
    failures, _notes, seams = census.census_seams()
    assert seams == []
    assert any("publishes through" in failure for failure in failures)


def test_the_census_exits_non_zero_when_it_fails(monkeypatch, capsys):
    monkeypatch.setattr(census, "READERS", (
        ("webapp/app.py", "_masked", "refuses", "doctored"),
    ))
    assert census.main(["--readers"]) == 1
    assert "CENSUS FAILS" in capsys.readouterr().out


def test_the_census_exits_zero_at_this_tree(capsys):
    assert census.main([]) == 0
    assert "CENSUS HOLDS" in capsys.readouterr().out


def test_every_declared_disposition_is_one_the_census_can_check():
    assert {disposition for _m, _f, disposition, _w in census.READERS} <= {
        "per_account", "refuses", "agnostic"}


def test_the_mutation_table_targets_apply_exactly_once():
    """A mutant that cannot be applied exactly as documented is not a mutant.

    Checked here rather than only inside the harness, so a refactor that makes
    an anchor ambiguous is a red test rather than a harness that refuses on the
    day someone runs it.
    """
    from tools import l1s3_mutation_table as table

    for mutant in table.MUTANTS:
        text = (table.ROOT / mutant.file).read_text(encoding="utf-8")
        assert text.count(mutant.old) == 1, mutant.id


def test_the_mutation_table_refuses_a_dirty_tree():
    from tools import l1s3_mutation_table as table

    assert "REFUSING" in table.main.__doc__ if table.main.__doc__ else True
    # The refusal is a real branch, not a comment: it is reachable from `main`
    # and it is what stops a restore-by-bytes running against unknown content.
    source = (table.ROOT / "tools/l1s3_mutation_table.py").read_text(encoding="utf-8")
    assert "if not tree_is_clean():" in source
    assert "finally:" in source


@pytest.mark.parametrize("disposition", ["per_account", "refuses"])
def test_each_disposition_is_actually_used(disposition):
    assert any(entry[2] == disposition for entry in census.READERS)

# --- MAJOR-1: the L1-S3 review's seven scratch readers ----------------------
#
# The review wrote seven readers, each reaching ONE account, none declared and
# none excused, and measured the census exit 0 with all seven in the tree. They
# are the test vector now: six are caught, and the seventh is out of scope for
# a stated reason this test pins rather than leaves to memory.

_SEVEN = {
    "one": 'def read(payload):\n    return payload["accounts"][0]["metrics"]\n',
    "two": 'def read(payload):\n    return next(iter(payload.get("accounts") or []), {})\n',
    "three": 'def read(payload):\n    return (payload.get("accounts") or [{}])[0].get("metrics", {})\n',
    "four": '_KEY = "statement"\n\n\ndef read(payload):\n    return payload[_KEY]\n',
    "five": (
        'def read(payload):\n'
        '    for key, value in payload.items():\n'
        '        if key == "statement":\n'
        '            return value\n'
        '    return {}\n'
    ),
    "six_out_of_scope": 'def read(report):\n    return report.statement\n',
    "seven_aliased_publisher": (
        'from analysis.serialization import report_to_dict as _publish_one_account\n'
        '\n\ndef publish(report):\n    return _publish_one_account(report)\n'
    ),
}


def _tree_with(tmp_path, names):
    for name in names:
        (tmp_path / f"scratch_{name}.py").write_text(_SEVEN[name], encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("name", ["one", "two", "three", "four", "five"])
def test_each_reverse_scratch_reader_is_caught(tmp_path, monkeypatch, name):
    """Five of the review's seven reach an account through the PAYLOAD, and the
    widened predicate sees each: the document shape's own key three ways, the
    swept key through a NAME, and a key comparison — which is how a `.items()`
    walk picks a key out of a payload it is iterating."""
    monkeypatch.setattr(census, "REPO", _tree_with(tmp_path, [name]))
    monkeypatch.setattr(census, "READERS", ())
    monkeypatch.setattr(census, "EXCUSED", {})
    failures, _notes, sites = census.census_readers()
    assert sites >= 1
    assert any(f"scratch_{name}.py::read" in failure for failure in failures)


def test_the_aliased_account_publisher_is_caught(tmp_path, monkeypatch):
    """The seventh. Both censuses missed it before: the AST one matched the
    call NAME, and the design's probe greps the text `report_to_dict(`."""
    monkeypatch.setattr(census, "REPO", _tree_with(tmp_path, ["seven_aliased_publisher"]))
    failures, _notes, seams = census.census_seams()
    assert seams == []
    assert any("aliased as" in failure and "scratch_seven" in failure
               for failure in failures)


def test_attribute_access_on_a_report_is_out_of_scope_and_the_document_object_is_not(
    tmp_path, monkeypatch
):
    """The sixth, and the one boundary this census draws deliberately.

    `report.statement` reads a `Report`, and a `Report` IS one account by
    construction — there is no second account there to drop. The hazard is
    reaching one account out of something that holds SEVERAL, and that is
    `document.accounts`, which IS swept. Pinned so the boundary is a decision
    on the record rather than an omission.
    """
    monkeypatch.setattr(census, "REPO", _tree_with(tmp_path, ["six_out_of_scope"]))
    monkeypatch.setattr(census, "READERS", ())
    monkeypatch.setattr(census, "EXCUSED", {})
    failures, _notes, sites = census.census_readers()
    assert sites == 0 and failures == []

    (tmp_path / "scratch_document_object.py").write_text(
        "def read(document):\n    return document.accounts[0]\n", encoding="utf-8")
    failures, _notes, sites = census.census_readers()
    assert sites >= 1
    assert any("scratch_document_object.py::read" in failure for failure in failures)


def test_a_refusal_in_a_dead_branch_no_longer_satisfies_the_forward_check(
    tmp_path, monkeypatch
):
    """MINOR-3. The review moved the refusal into `if False:` at all eight
    refusal sites and the census stayed exit 0 at every one."""
    module = tmp_path / "scratch_dead_refusal.py"
    module.write_text(
        "def read(payload):\n"
        "    if False:\n"
        "        refuse_document_payload(payload, surface='x')\n"
        "    return payload\n", encoding="utf-8")
    monkeypatch.setattr(census, "REPO", tmp_path)
    monkeypatch.setattr(census, "READERS", (
        ("scratch_dead_refusal.py", "read", "refuses", "doctored"),
    ))
    monkeypatch.setattr(census, "EXCUSED", {})
    failures, _notes, _sites = census.census_readers()
    assert any("never calls" in failure for failure in failures)

    module.write_text(
        "def read(payload):\n"
        "    refuse_document_payload(payload, surface='x')\n"
        "    return payload\n", encoding="utf-8")
    failures, _notes, _sites = census.census_readers()
    assert not any("never calls" in failure for failure in failures)


def test_a_new_single_account_publish_inside_the_publisher_is_caught(tmp_path, monkeypatch):
    """MINOR-9. Both censuses skip the publisher module wholesale, which is
    right and was blind: the count of its internal account-publisher calls is
    pinned, so a third one has to be declared."""
    publisher = tmp_path / "analysis"
    publisher.mkdir()
    (publisher / "serialization.py").write_text(
        "def report_to_dict(report):\n    return {}\n\n\n"
        "def document_report_to_dict(document):\n"
        "    return report_to_dict(document.accounts[0])\n", encoding="utf-8")
    monkeypatch.setattr(census, "REPO", tmp_path)
    failures, _notes, _seams = census.census_seams()
    assert any("inside itself" in failure for failure in failures)
