"""True revenue spec §14.2, §14.3 and §14.5: the revenue census (tools/revenue_census.py) on fabricated snapshots.
The census itself runs only on the local cache and on a copy of the tryout host's job store; these tests feed it
hand-built snapshots and one fabricated statement analysed by the real code."""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
from pathlib import Path

import pytest

from tools import revenue_census as census


def _credit(i, cents, state, method, *, tier=None, reason=None, text="FABRICATED ROW", rule=None, entity=None,
            lender_credit=False, **facts):
    return {"i": i, "cents": cents, "state": state, "method": method, "rule": rule, "entity": entity, "tier": tier,
            "reason": reason, "class": "other", "lender_credit": lender_credit, "text": text, "facts": facts}


def _account(credits, *, gated=False, deposits=1000.0):
    return {"bank": "FABRICATED BANK", "rows": 10, "credits": credits,
            "posted_cents": sum(credit["cents"] for credit in credits), "lender_credits": 0.0,
            "posted_credit_count": len(credits), "posted_credit_cents": sum(credit["cents"] for credit in credits),
            "tier_totals": None, "eligible_deposits": deposits, "revenue_review_required": gated}


def _snap(version, accounts, skipped=None):
    return {"classification_version": version, "accounts": accounts, "skipped": skipped or {}}


def _run(base, after):
    return census.compare(base, [after])["runs"][0]


BASE = _snap("5.4", {"a": _account([
    _credit(0, 70000, "verified_revenue", "operating_income_descriptor"),
    _credit(1, 30000, "unverified_deposit", "deposit_source_requires_review"),
    _credit(2, 90000, "unverified_deposit", "deposit_source_requires_review"),
    _credit(3, 10000, "non_revenue", "strong_non_revenue_rule", text="BOOK TRANSFER CREDIT B O FABRIKAM INC"),
])})
AFTER = _snap("5.6", {"a": _account([
    _credit(0, 70000, "verified_revenue", "named_payer_company_form", tier="verified"),
    _credit(1, 30000, "unverified_deposit", "check_deposit_requires_review", tier="counted_flagged",
            reason="check_deposit"),
    _credit(2, 90000, "unverified_deposit", "deposit_source_requires_review", tier="excluded_pending_review",
            reason="financing_named_payer", financing_root=True),
    _credit(3, 10000, "unverified_deposit", "wire_requires_review", tier="counted_flagged",
            reason="wire_named_sender", text="BOOK TRANSFER CREDIT B O FABRIKAM INC", third_party_originator=True),
], gated=True)})


def test_the_summary_reports_true_verified_and_the_reasons():
    report = census.compare(BASE, [AFTER])
    summary = report["runs"][0]["summary"]
    assert (summary["true_share"], summary["verified_share"], summary["held_share"]) == (55.0, 35.0, 45.0)
    assert summary["zero_true_statements"] == 0 and summary["gated_share"] == 100.0
    assert summary["reasons"]["excluded_pending_review/financing_named_payer"] == {"rows": 1, "dollars": 900.0}
    assert report["base"]["true_share"] is None and report["base"]["verified_share"] == 35.0


def test_a_row_that_leaves_non_revenue_names_its_narrowing():
    run = _run(BASE, AFTER)
    assert run["left_non_revenue"] == {"4_book_or_funds_transfer": {"rows": 1, "dollars": 100.0, "statements": 1}}
    assert run["guards"] == {}
    assert run["gated_statements_by_held_reason"] == {"financing_named_payer": 1}


def test_a_row_that_leaves_non_revenue_by_no_narrowing_fails_g1():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["a"]["credits"][3]["text"] = "FABRICATED ROW"
    assert _run(BASE, after)["guards"]["G1"]["failures"] == 1


def test_a_book_transfer_leaves_non_revenue_only_on_a_third_party_originator():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["a"]["credits"][3]["facts"]["third_party_originator"] = False
    run = _run(BASE, after)
    assert run["left_non_revenue"] == {"outside_the_narrowings": {"rows": 1, "dollars": 100.0, "statements": 1}}
    assert run["guards"]["G1"]["failures"] == 1


@pytest.mark.parametrize(("entity", "cause"), [("AFFIRM", "8_oq2_bnpl_settlement"),
                                               ("FABRIKAM FUNDING LLC", "outside_the_narrowings")])
def test_only_the_five_bnpl_settlements_leave_d1_by_the_owner_s_ruling(entity, cause):
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "non_revenue", "financing_proceeds_credit", entity=entity,
                                                lender_credit=True)])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="payout_credit_entity", entity=entity)])})
    run = _run(base, after)
    assert list(run["left_non_revenue"]) == [cause]
    assert ("G1" in run["guards"]) is (cause == "outside_the_narrowings")
    moved = {"8_oq2_bnpl_settlement": "8_oq2_bnpl_settlement", "outside_the_narrowings": "left:x"}[cause]
    assert run["lender_credit_moves_by_cause"][moved]["eligible_deposit_dollars"] == 50.0


@pytest.mark.parametrize(("guard", "credit"), [
    ("G2", _credit(0, 100, "verified_revenue", "named_payer_company_form", tier="verified", financing_root=True)),
    ("G2", _credit(0, 100, "verified_revenue", "recurring_operating_source", tier="verified", registry_root=True)),
    ("G3", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p", holder=True)),
    ("G4", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p",
                   transfer_no_counterparty=True)),
    ("G6", _credit(0, 100, "verified_revenue", "direction_conflict", tier="verified")),
    ("G10", _credit(0, 100, "verified_revenue", "operating_income_descriptor", tier="verified", gate="closed")),
    ("G10", _credit(0, 100, "verified_revenue", "named_payer_repeats", tier="verified", gate="push")),
    ("G11", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p", pay_or_personal=True)),
    ("G12", _credit(0, 100, "verified_revenue", "auto_lender_dealer_funding", tier="verified", q7_payer_ok=False)),
    ("G12", _credit(0, 100, "verified_revenue", "auto_lender_dealer_funding", tier="verified", q7_payer_ok=True,
                    q7_veto_word=True)),
    ("G13", _credit(0, 100, "verified_revenue", "named_payer_company_form", tier="verified", numbered=True)),
    ("G13", _credit(0, 100, "verified_revenue", "recurring_operating_source", tier="verified", numbered_region=True)),
    ("G14", _credit(0, 100, "verified_revenue", "recurring_operating_source", tier="verified",
                    pooled_while_vetoed=True)),
    ("G5", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p", known_financing=True)),
    ("G15", _credit(0, 100, "verified_revenue", "named_payer_repeats", tier="verified",
                    text="FABRIKAM INC DES CUSTREFUNDS ID #")),
    ("G15", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="named_payer_one_off",
                    text="FABRIKAM INC DES PREFUND ID #")),
    ("G16", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="named_payer_one_off",
                    text="FRANCHISE TAX BD DES CASTTAXRFD ID #")),
    ("G16", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="named_payer_one_off",
                    text="IRS TREAS ### DES TAXEIC ID #")),
    ("G17", _credit(0, 100, "unverified_deposit", "x", tier="counted_flagged", reason="p2p", own_transfer=True)),
])
def test_each_row_guard_fails_on_its_row(guard, credit):
    assert census._row_guards(credit)[guard] is True


def test_the_row_guards_hold_on_clean_rows():
    clean = [
        # A registry row reads G2 on its own root (the holder's words and §7.0's FUNDING settlements aside).
        _credit(0, 100, "verified_revenue", "recurring_operating_source", tier="verified", financing_root=True),
        # A push-rail row the registry verified.
        _credit(0, 100, "verified_revenue", "operating_source_with_credit_context", tier="verified", gate="push"),
        # A refund word the bank prints in the receiver field is the holder's, not the row's.
        _credit(0, 100, "verified_revenue", "named_payer_repeats", tier="verified",
                text="FABRIKAM INC DES PAYMENT INDN REFUNDS DEPT"),
        # A held refund is out of True.
        _credit(0, 100, "unverified_deposit", "x", tier="excluded_pending_review", reason="non_sale_purpose",
                text="FABRIKAM INC DES REFUNDS ID #"),
        # A processor's card settlement printed after BMO's MISC PAYMENT <digits> template: its payer is the processor.
        _credit(0, 100, "verified_revenue", "operating_income_descriptor", tier="verified", numbered=True,
                rule="card_settlement_form_gbl_brand", text="MISC PAYMENT ####### GBL VI"),
    ]
    assert not any(value for credit in clean for value in census._row_guards(credit).values())


def test_a_processor_s_template_row_is_listed_apart_from_g13():
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "unverified_deposit", "x")])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "verified_revenue", "operating_income_descriptor",
                                                 tier="verified", numbered=True, rule="card_settlement_form_gbl_brand",
                                                 text="MISC PAYMENT ####### GBL VI")])})
    run = _run(base, after)
    assert "G13" not in run["guards"]
    assert run["g13_listed_apart"] == {"operating_income_descriptor": {"rows": 1, "dollars": 50.0, "statements": 1}}


def test_the_four_tier_identity_is_checked_on_every_account():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["a"]["posted_cents"] += 1
    assert _run(BASE, after)["guards"]["G9"]["failures"] >= 1


@pytest.mark.parametrize("breakage", ["tier_state", "no_state", "metrics", "unmatched", "error_skip"])
def test_g9_fails_on_every_way_an_account_can_fall_out_of_the_identity(breakage):
    after = json.loads(json.dumps(AFTER))
    account = after["accounts"]["a"]
    if breakage == "tier_state":
        account["credits"][0]["tier"] = "counted_flagged"
    elif breakage == "no_state":
        account["posted_credit_count"] += 1
    elif breakage == "metrics":
        account["tier_totals"] = {"verified": 70000, "counted_flagged": 40000, "excluded_pending_review": 0,
                                  "non_revenue": 90000}
    elif breakage == "unmatched":
        after["accounts"] = {"b": account}
    else:
        after["skipped"] = {"ValueError": 1}
    assert _run(BASE, after)["guards"]["G9"]["failures"] >= 1


def test_the_metrics_tier_totals_that_agree_hold():
    after = json.loads(json.dumps(AFTER))
    after["accounts"]["a"]["tier_totals"] = {"verified": 70000, "counted_flagged": 40000,
                                             "excluded_pending_review": 90000, "non_revenue": 0}
    assert "G9" not in _run(BASE, after)["guards"]


@pytest.mark.parametrize(("rows", "fails"), [(1, True), (2, False)])
def test_a_credit_union_s_dealer_funding_needs_two_credits(rows, fails):
    credits = [_credit(i, 3000000, "verified_revenue", "auto_lender_dealer_funding", tier="verified",
                       q7_payer_ok=True, q7_credit_union=True, q7_listed=False) for i in range(rows)]
    base = _snap("5.4", {"a": _account([_credit(i, 3000000, "unverified_deposit", "x") for i in range(rows)])})
    assert ("G12" in _run(base, _snap("5.6", {"a": _account(credits)}))["guards"]) is fails


@pytest.mark.parametrize(("vetoed", "fails"), [(2, True), (0, False)])
def test_a_recurrence_lift_needs_its_count_without_the_vetoed_rows(vetoed, fails):
    credits = [_credit(i, 50000 + i, "verified_revenue", "recurring_operating_source", tier="verified",
                       entity="Stripe", pool_candidate=True, pool_vetoed=i < vetoed, pool_threshold=3)
               for i in range(3)]
    base = _snap("5.4", {"a": _account([_credit(i, 50000 + i, "unverified_deposit", "x") for i in range(3)])})
    assert ("G14" in _run(base, _snap("5.6", {"a": _account(credits)}))["guards"]) is fails


def test_a_text_the_street_ln_guard_changed_is_listed_and_never_financing_into_true():
    # Re-pinned by the final review's I8 (the orchestrator's ruling; a tool fixture, not a real-statement test): 5.4
    # reads '... LN DISB' as a loan through the strong non-revenue rule, the base a misfiring guard would release, and
    # G7b fails for any non_revenue base a text change takes into True, except the guard's own street release.
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "non_revenue", "strong_non_revenue_rule",
                                                text="DEPOSIT 12 COMMERCIAL LOAN DISB")])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="no_payer_printed", text="DEPOSIT 12 COMMERCIAL LN DISB")])})
    run = _run(base, after)
    assert run["street_ln_changes"][0]["base"] == "non_revenue|strong_non_revenue_rule"
    assert run["guards"]["G7b"]["failures"] == 1
    street = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                  reason="no_payer_printed", text="DEPOSIT 12 OAK LN")])})
    street_base = _snap("5.4", {"a": _account([_credit(0, 5000, "non_revenue", "strong_non_revenue_rule",
                                                       text="DEPOSIT 12 OAK LOAN")])})
    assert "G7b" not in _run(street_base, street)["guards"]


def test_a_verified_row_demoted_without_a_declared_cause_fails_the_census():
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "verified_revenue", "operating_income_descriptor")])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="named_payer_one_off")])})
    run = _run(base, after)
    assert run["verified_demotions"] == {"undeclared": {"rows": 1, "dollars": 50.0, "statements": 1}}
    assert run["guards"]["undeclared_demotion"]["failures"] == 1


def test_the_precision_sample_draws_each_stratum_and_the_largest_counted_rows():
    accounts = {f"s{n}": _account([
        _credit(0, 1000 + n, "verified_revenue", "named_payer_company_form", tier="verified"),
        _credit(1, 500 * n, "unverified_deposit", "x", tier="counted_flagged", reason="p2p"),
        _credit(2, 700, "verified_revenue", "recurring_operating_source", tier="verified", holder=True),
    ]) for n in range(60)}
    accounts["forms"] = _account([
        _credit(0, 900, "verified_revenue", "operating_income_descriptor", tier="verified",
                rule="card_settlement_form_bankcard"),
        _credit(1, 800, "verified_revenue", "operating_source_with_credit_context", tier="verified", numbered=True),
    ])
    accounts["forms"]["credits"][1]["alias"] = "whatnot_fbo_form"
    sample = census.precision_sample(_snap("5.6", accounts))
    assert len(sample["q6b_company_form"]) == 20 and len(sample["holder_test_rows"]) == 20
    assert [row["dollars"] for row in sample["numbered_template_rows"]] == [8.0]
    assert sorted(row["dollars"] for row in sample["card_and_payout_forms"]) == [8.0, 9.0]
    assert [row["dollars"] for row in sample["largest_counted"][:2]] == [295.0, 290.0]
    assert len(sample["largest_counted"]) == 50 and all(row["sort"] == "" for row in sample["largest_counted"])


def test_the_sample_command_writes_outside_the_repository(tmp_path, capsys):
    snapshot = tmp_path / "s56.json.gz"
    snapshot.write_bytes(gzip.compress(json.dumps(_snap("5.6", {"a": _account([
        _credit(0, 5000, "verified_revenue", "named_payer_repeats", tier="verified")])})).encode("utf-8")))
    assert census.main(["sample", "--snapshot", str(snapshot), "--out", str(tmp_path / "sample.json")]) == 0
    assert json.loads((tmp_path / "sample.json").read_text(encoding="utf-8"))["q6a_repeats"][0]["dollars"] == 50.0
    assert census.main(["sample", "--snapshot", str(snapshot), "--out", str(census.ROOT / "sample.json")]) == 2


def test_the_cli_refuses_to_write_inside_the_repository(tmp_path, capsys):
    snapshot = tmp_path / "base.json.gz"
    snapshot.write_bytes(gzip.compress(json.dumps(BASE).encode("utf-8")))
    inside = census.ROOT / "census-output.json"
    assert census.main(["compare", "--base", str(snapshot), "--after", str(snapshot), "--out", str(inside)]) == 2
    assert "inside the repository" in capsys.readouterr().err
    assert not inside.exists()
    outside = tmp_path / "report.json"
    assert census.main(["compare", "--base", str(snapshot), "--after", str(snapshot), "--out", str(outside)]) == 0


# ---------------------------------------------------------------------------------------------------------------------
# S3.1 additions (decided by the orchestrator on the owner's delegation): the declared causes of the reviewed 5.5
# fixes (the wire vetoes, the receiver's value), the recurrence veto through a glued digit, the OQ2 rows' public
# shapes, and the per-PDF basis (one analysis per source PDF, beside the plan's one per analysis input).
# ---------------------------------------------------------------------------------------------------------------------

WIRE = "WIRE TYPE WIRE IN ORIG FABRIKAM DESIGN INC OBI CUSTOMER PAYMENT"


@pytest.mark.parametrize(("vetoed", "after_method", "cause"), [
    (True, "ambiguous_credit_descriptor", "wire_veto"),
    (True, "unidentified_posted_credit", "wire_veto"),
    (False, "ambiguous_credit_descriptor", "undeclared"),
    # The wire vetoes refuse a rule, and the row then falls to steps 15 and 16; a row another rule took is not theirs.
    (True, "named_payer_one_off", "undeclared"),
])
def test_a_verified_wire_the_wire_vetoes_now_refuse_is_a_declared_demotion(vetoed, after_method, cause):
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "verified_revenue", "operating_income_descriptor",
                                                rule="verified_operating_income_descriptor", text=WIRE)])})
    after = _snap("5.5", {"a": _account([_credit(0, 5000, "unverified_deposit", after_method, text=WIRE,
                                                 wire_vetoed=vetoed)])})
    run = _run(base, after)
    assert list(run["verified_demotions"]) == [cause]
    assert ("undeclared_demotion" in run["guards"]) is (cause == "undeclared")


@pytest.mark.parametrize(("method", "alias", "text", "cause"), [
    # The operating alias was read only in the holder's name, the receiver field's value (S2.2 review, spec §5.2).
    ("operating_source_with_credit_context", "STRIPE", "FABRIKAM DES PAYMENT ID # INDN STRIPE STREET CAFE CO ID # CCD",
     "receiver_value"),
    ("recurring_operating_source", "STRIPE", "FABRIKAM DES PAYMENT ID # INDN STRIPE STREET CAFE CO ID # CCD",
     "receiver_value"),
    # The alias is also printed before the receiver field: the receiver's value did not make the verification.
    ("operating_source_with_credit_context", "STRIPE", "STRIPE DES TRANSFER ID # INDN STRIPE STREET CAFE CO ID # CCD",
     "undeclared"),
    # Step 11's customer descriptor, read in 5.4 on a CUSTOMER that only the holder's name printed.
    ("operating_income_descriptor", None, "FABRIKAM DES PAYMENT ID # INDN CUSTOMER CARE LLC CO ID # CCD",
     "receiver_value"),
    ("operating_income_descriptor", None, "NORTHWIND CUSTOMER PAYMENT ACH", "undeclared"),
])
def test_a_verification_read_only_in_the_receiver_s_value_is_a_declared_demotion(method, alias, text, cause):
    prior = _credit(0, 5000, "verified_revenue", method, text=text,
                    rule="verified_operating_income_descriptor" if alias is None else None)
    prior["alias"] = alias
    base = _snap("5.4", {"a": _account([prior])})
    after = _snap("5.5", {"a": _account([_credit(0, 5000, "unverified_deposit", "unidentified_posted_credit",
                                                 text=text)])})
    assert list(_run(base, after)["verified_demotions"]) == [cause]


@pytest.mark.parametrize(("text", "facts", "cause"), [
    # S2.2-A: a veto word of four letters or more reads through a glued digit (masked to '#').
    ("FABRIKAM DES ####PAYROLL ID #", {}, "recurrence_veto"),
    ("FABRIKAM DES ####LOAN ID #", {}, "recurrence_veto"),
    # A three-letter word glued to a digit is an ID's suffix, which the classifier never reads as the word.
    ("FABRIKAM DES SALES ID ####FIN", {}, "undeclared"),
    ("FABRIKAM DES SALES ID # FIN", {}, "recurrence_veto"),
    # The veto reads the row before its receiver fields: the holder's name is not the row's.
    ("FABRIKAM DES SALES ID # INDN SAMPLE PAYROLL LLC CO ID # CCD", {}, "undeclared"),
    # A snapshot of the 5.5 code carries the classifier's own reading, which decides.
    ("FABRIKAM DES SALES ID #", {"recurrence_veto_wording": True}, "recurrence_veto"),
    ("FABRIKAM DES CAPITAL ID #", {"recurrence_veto_wording": False}, "undeclared"),
])
def test_a_recurrence_veto_word_is_read_as_the_classifier_reads_it(text, facts, cause):
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "verified_revenue", "recurring_operating_source",
                                                text=text, entity="Stripe")])})
    after = _snap("5.5", {"a": _account([_credit(0, 5000, "unverified_deposit", "unidentified_posted_credit",
                                                 text=text, entity="Stripe", **facts)])})
    assert list(_run(base, after)["verified_demotions"]) == [cause]


def test_each_bnpl_settlement_that_leaves_d1_is_listed_by_its_public_words():
    texts = ["AFFIRM INC DES SETTLEMENT ID ####### INDN SAMPLE GOODS LLC CO ID ####### CCD"] * 55 + [
        "AFFIRMCARD DES BALANCE WITHDRAWAL NORTHWIND ROASTERS"]
    base = _snap("5.4", {"a": _account([_credit(i, 5000, "non_revenue", "financing_proceeds_credit", entity="AFFIRM",
                                                text=text, lender_credit=True) for i, text in enumerate(texts)])})
    after = _snap("5.5", {"a": _account([_credit(i, 5000, "unverified_deposit", "operating_source_requires_context",
                                                 entity="AFFIRM", text=text) for i, text in enumerate(texts)])})
    listing = _run(base, after)["bnpl_settlements"]
    assert listing["rows"] == 56 and len(listing["listed"]) == 50
    assert listing["shapes"] == {"AFFIRM INC DES SETTLEMENT ID # INDN * LLC CO ID # CCD": 55,
                                 "AFFIRMCARD DES BALANCE WITHDRAWAL *": 1}
    assert listing["listed"][0] == {"account": "a", "i": 0, "entity": "AFFIRM",
                                    "after": "unverified_deposit|operating_source_requires_context",
                                    "shape": "AFFIRM INC DES SETTLEMENT ID # INDN * LLC CO ID # CCD"}
    # Never a person's or a private business's name.
    assert not {"SAMPLE", "GOODS", "NORTHWIND", "ROASTERS"} & set(json.dumps(listing).replace('"', " ").split())


def test_a_bnpl_shape_keeps_only_public_words():
    assert census.public_shape("SP AFF ##### SAMPLE STORE") == "SP AFF # *"
    assert census.public_shape("TRUEACCORD KLARNA DES REFUND ID 1234 INDN CONTOSO") == (
        "TRUEACCORD KLARNA DES REFUND ID # INDN *")
    assert census.public_shape("SUNBIT ##AB12 FUNDING") == "SUNBIT # FUNDING"


def test_the_compare_records_the_basis_and_never_mixes_two():
    assert census.compare(BASE, [AFTER])["basis"] == "input"
    pdf = census.compare(dict(BASE, basis="pdf"), [dict(AFTER, basis="pdf", basis_stats={"pdfs": 1})])
    assert pdf["basis"] == "pdf" and pdf["basis_stats"]["after"] == [{"pdfs": 1}]
    with pytest.raises(census.BasisMismatch):
        census.compare(BASE, [dict(AFTER, basis="pdf")])


_ARTIFACT_TABLE = (
    "CREATE TABLE artifact_cache (stage TEXT NOT NULL, cache_key TEXT NOT NULL, input_sha256 TEXT NOT NULL,"
    " settings_key TEXT NOT NULL, format_version INTEGER NOT NULL, artifact_path TEXT NOT NULL,"
    " byte_size INTEGER NOT NULL, created_at TEXT NOT NULL, last_hit_at TEXT, hit_count INTEGER NOT NULL DEFAULT 0,"
    " PRIMARY KEY (stage, cache_key))"
)
ROWS = [(5, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0), (9, "CARD PURCHASE FABRICATED SUPPLY", -300.0)]


def _statement(number, rows=ROWS):
    from analysis.schema import Statement, Transaction

    balance, transactions = 1000.0, []
    for day, description, amount in rows:
        balance += amount
        transactions.append(Transaction(date=f"2031-03-{day:02d}", description=description, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    return Statement(bank="FABRICATED BANK", account_name="CONTOSO BAKERY LLC", account_number=number,
                     period_start="2031-03-01", period_end="2031-03-28", beginning_balance=1000.0,
                     ending_balance=balance, transactions=transactions).model_dump(mode="json")


class _FabricatedCache:
    """A webapp data directory in the artifact cache's layout (webapp/artifact_cache.py): an `artifact_cache` index
    in webapp.db, payloads under artifacts/<stage>/, and the Windows separators the real index stores."""

    def __init__(self, root):
        import sqlite3

        self.root = root
        (root / "artifacts").mkdir(parents=True)
        self.connection = sqlite3.connect(root / "webapp.db")
        self.connection.execute(_ARTIFACT_TABLE)
        self.count = 0

    def _put(self, stage, input_sha, artifact, created_at, settings="S"):
        self.count += 1
        key = f"{self.count:064X}"
        path = self.root / "artifacts" / stage / key[:2] / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps({"stage": stage, "artifact": artifact})
        path.write_text(text, encoding="utf-8")
        self.connection.execute(
            "INSERT INTO artifact_cache (stage, cache_key, input_sha256, settings_key, format_version, artifact_path,"
            " byte_size, created_at) VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
            (stage, key, input_sha, settings, f"{stage}\\{key[:2]}\\{key}.json", len(text), created_at),
        )
        self.connection.commit()

    def ocr(self, pdf, pages, created_at):
        """One OCR route of one PDF; returns the analysis input its document is analysed under (None: no document)."""
        from ocr.document import StatementMarkdown
        from webapp.artifact_cache import analysis_input_sha

        self._put("ocr", pdf, {"document": None if pages is None else {"model": "fabricated", "pages": pages}},
                  created_at)
        if pages is None:
            return None
        markdown = StatementMarkdown(source_file="fabricated.pdf", model="fabricated", pages=pages).to_markdown()
        return analysis_input_sha(markdown, pages)

    def analysis(self, input_sha, statements, created_at, settings="S", model_used=None):
        accounts = [{"statement": statement, "reconciliation": {"ok": True}} for statement in statements]
        if model_used is not None:
            for account in accounts:
                account["model_used"] = model_used
        self._put("analysis", input_sha, {"analysis": {"accounts": accounts}}, created_at, settings)


PDF_G, PDF_A, PDF_B, PDF_C, PDF_H = "0" * 64, "A" * 64, "B" * 64, "C" * 64, "F" * 64


@pytest.fixture
def fabricated_cache(tmp_path):
    cache = _FabricatedCache(tmp_path / "webapp_data")
    # PDF A is read by two OCR routes into two different markdowns, so the cache holds two analysis inputs of one PDF.
    newest = cache.ocr(PDF_A, ["FABRICATED PAGE ONE", "FABRICATED PAGE TWO"], "2031-03-02T00:00:00")
    older = cache.ocr(PDF_A, ["FABRICATED PAGE ONE AND TWO"], "2031-03-01T00:00:00")
    cache.analysis(newest, [_statement("XXXX1234")], "2031-03-03T00:00:00")
    cache.analysis(older, [_statement("XXXX1234", ROWS + [(12, "DEPOSIT", 100.0)])], "2031-03-03T00:00:00")
    # PDF B, and PDF H whose one route reads exactly B's markdown (two PDFs, one analysis).
    only_b = cache.ocr(PDF_B, ["FABRICATED PAGE B"], "2031-03-01T00:00:00")
    cache.ocr(PDF_H, ["FABRICATED PAGE B"], "2031-03-01T00:00:00")
    cache.analysis(only_b, [_statement("XXXX5678")], "2031-03-03T00:00:00")
    # PDF C's OCR found no document; PDF G's newest route was never analysed, its older one was.
    cache.ocr(PDF_C, None, "2031-03-01T00:00:00")
    cache.ocr(PDF_G, ["FABRICATED PAGE G AGAIN"], "2031-03-02T00:00:00")
    cache.analysis(cache.ocr(PDF_G, ["FABRICATED PAGE G"], "2031-03-01T00:00:00"), [_statement("XXXX3456")],
                   "2031-03-03T00:00:00")
    # Analyses no OCR route of the cache reads: one of A's statement, one of another, one without an account number.
    cache.analysis("D" * 64, [_statement("XXXX1234", ROWS[:1])], "2031-03-04T00:00:00")
    cache.analysis("E" * 64, [_statement("XXXX9012")], "2031-03-05T00:00:00")
    cache.analysis("1" * 64, [_statement(None)], "2031-03-04T00:00:00")
    cache.connection.close()
    return cache.root, newest


def _tree(root):
    return {path.relative_to(root): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_the_pdf_basis_reads_one_analysis_per_source_pdf(fabricated_cache):
    data_dir, newest = fabricated_cache
    before = _tree(data_dir)
    assert len(list(census.cached_accounts(data_dir))) == 7
    stats: dict = {}
    accounts = list(census.cached_accounts(data_dir, basis="pdf", stats=stats))
    assert [key for key, _ in accounts] == [
        f"p{PDF_G[:12]}.0", f"p{PDF_A[:12]}.0", f"p{PDF_B[:12]}.0", f"o{'E' * 12}.0", f"o{'1' * 12}.0"]
    # PDF A counts once, from its newest OCR route.
    assert len(accounts[1][1]["statement"]["transactions"]) == len(ROWS)
    # B1 (I60): the stages the cache's analyses were made under are recorded beside the basis's counts.
    assert list(stats.pop("analysis_stages")) == ["S"]
    assert stats == {"analysis_inputs": 7, "pdfs": 5, "pdfs_joined": 4, "pdfs_joined_on_newest_route": 3,
                     "pdfs_on_an_older_reconciling_route": 0, "pdfs_without_a_reconciling_route": 0,
                     "pdfs_without_an_analysis": 1, "pdfs_sharing_an_analysis": 1, "analysis_inputs_joined": 4,
                     "orphan_inputs": 3, "orphan_accounts_kept": 2, "orphan_accounts_matching_a_kept_statement": 1,
                     "orphan_accounts_without_identity": 1}
    # Read-only: the cache is byte for byte what it was, and no journal was left beside it.
    assert _tree(data_dir) == before


def test_a_limited_pdf_basis_reads_only_its_first_analyses(fabricated_cache):
    data_dir, _newest = fabricated_cache
    stats: dict = {}
    assert [key for key, _ in census.cached_accounts(data_dir, 2, basis="pdf", stats=stats)] == [
        f"p{PDF_G[:12]}.0", f"p{PDF_A[:12]}.0"]
    assert stats["limit_reached"] is True


def test_the_snapshot_command_records_its_basis_and_compare_refuses_two(fabricated_cache, tmp_path, capsys):
    data_dir, _newest = fabricated_cache
    by_pdf, by_input = tmp_path / "pdf.json.gz", tmp_path / "input.json.gz"
    assert census.main(["snapshot", "--data-dir", str(data_dir), "--basis", "pdf", "--out", str(by_pdf)]) == 0
    assert census.main(["snapshot", "--data-dir", str(data_dir), "--out", str(by_input)]) == 0
    pdf, per_input = census._read(by_pdf), census._read(by_input)
    assert (pdf["basis"], per_input["basis"]) == ("pdf", "input")
    assert (len(pdf["accounts"]), len(per_input["accounts"])) == (5, 7)
    assert pdf["basis_stats"]["pdfs_joined"] == 4 and per_input["basis_stats"]["analysis_inputs"] == 7
    report = tmp_path / "report.json"
    assert census.main(["compare", "--base", str(by_pdf), "--after", str(by_pdf), "--out", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["basis"] == "pdf"
    capsys.readouterr()
    assert census.main(["compare", "--base", str(by_input), "--after", str(by_pdf), "--out", str(report)]) == 2
    assert "basis" in capsys.readouterr().err


def test_the_pdf_basis_of_a_job_store_keeps_each_pdf_s_newest_job(tmp_path):
    import sqlite3

    database = tmp_path / "webapp.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, content_sha256 TEXT NOT NULL)")
    connection.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, document_id INTEGER, analysis_json TEXT,"
                       " created_at TEXT NOT NULL)")
    connection.executemany("INSERT INTO documents VALUES (?, ?)", [(1, PDF_A), (2, PDF_A), (3, PDF_B)])
    payload = json.dumps({"accounts": [{"statement": _statement("XXXX1234"), "reconciliation": {"ok": True}}]})
    connection.executemany("INSERT INTO jobs VALUES (?, ?, ?, ?)", [
        ("job-a-first", 1, payload, "2031-03-01T00:00:00"), ("job-a-again", 2, payload, "2031-03-02T00:00:00"),
        ("job-b", 3, payload, "2031-03-01T00:00:00"), ("job-none", None, payload, "2031-03-01T00:00:00")])
    connection.commit()
    connection.close()
    assert len(list(census.job_accounts(database))) == 4
    stats: dict = {}
    assert sorted(key for key, _ in census.job_accounts(database, basis="pdf", stats=stats)) == [
        "jjob-a-ag.0", "jjob-b.0", "jjob-none.0"]
    assert stats == {"jobs": 4, "pdfs": 2, "jobs_repeating_a_pdf": 1}


def test_the_snapshot_reads_the_wire_veto_and_the_recurrence_veto_with_the_checkout_s_code():
    from analysis.schema import Statement

    statement = Statement.model_validate(_statement("XXXX1234", [
        (3, "WIRE TYPE WIRE IN ORIG FABRIKAM DESIGN INC OBI INVOICE PAYMENT ESCROW", 3000.0),
        (5, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0),
        (7, "NORTHWIND DES 1234PAYROLL ID 5678", 900.0),
    ]))
    credits = census.account_snapshot({"statement": statement.model_dump(mode="json")})["credits"]
    facts = [(credit["i"], credit["facts"]["wire_vetoed"], credit["facts"]["recurrence_veto_wording"])
             for credit in credits]
    assert facts == [(0, True, False), (1, False, False), (2, False, True)]
    assert credits[0]["state"] == "unverified_deposit" and credits[1]["state"] == "verified_revenue"


# ---------------------------------------------------------------------------------------------------------------------
# S3.1 review, fix round 1 (decided by the orchestrator on the owner's delegation): every declared cause is tied to the
# 5.4 rule it explains and the 5.5 outcome it produces; a guard whose facts the run lacks is reported unchecked, never
# held; no output inside any repository; the per-PDF basis prefers a reconciling route; the bank is masked.
# ---------------------------------------------------------------------------------------------------------------------

def _step_11(text):
    """A credit 5.4's step 11 verified (its plain verified-descriptor rule)."""
    return _credit(0, 5000, "verified_revenue", "operating_income_descriptor", rule="verified_operating_income_descriptor",
                   text=text)


def _registry(method, text, *, entity="Stripe", alias="STRIPE", cents=5000):
    """A credit 5.4's operating registry verified (its context, its recurrence or its related activity)."""
    credit = _credit(0, cents, "verified_revenue", method, text=text, entity=entity)
    credit["alias"] = alias
    return credit


def _later(method, text, *, state="unverified_deposit", cents=5000, rule=None, entity=None, **facts):
    return _credit(0, cents, state, method, text=text, rule=rule, entity=entity, **facts)


def _causes(priors, laters, admissions=None):
    base = _snap("5.4", {"a": _account(priors)})
    after = _snap("5.5", {"a": _account(laters)})
    return {cause: value["rows"] for cause, value in
            census.compare(base, [after], admissions=admissions)["runs"][0]["verified_demotions"].items()}


SQ_CAP = "SQUARE INC DES SQ CAP#### ID #"
CAPITAL_SETTLEMENT = "FABRIKAM CAPITAL DES MERCHANT SETTLEMENT ID #"
TRUIST = "FABRIKAM DES PAYMENT CUSTOMER ID ####"
CHECK = "FABRIKAM INC DES CUSTOMER PAYMENT CHECK ####"
HOLDER = "CONTOSO BAKERY LLC DES CUSTOMER PAYMENT ID #"
NUMBERED = "####### NOVA SCOTIA LTD DES CUSTOMER PAYMENT"
CLAIM = "BLUE CROSS BLUE DES HCCLAIMPMT ID #"
PUSH = "RTP CREDIT FABRIKAM CUSTOMER PAYMENT"


@pytest.mark.parametrize(("prior", "later", "admissions", "cause"), [
    # D1 by descriptor precedes every verifying rule (§6.1 step 7): Square Capital's SQ CAP.
    (_registry("operating_source_with_credit_context", SQ_CAP, entity="Square", alias="SQUARE"),
     _later("financing_proceeds_credit", SQ_CAP, state="non_revenue", rule="square_capital_credit"), None,
     "sq_cap_or_sba"),
    # Financing proceeds of an entity the S1.5 admissions added: declared only with the signed-off list, and only for
    # an entity on it.
    (_step_11(CAPITAL_SETTLEMENT), _later("financing_proceeds_credit", CAPITAL_SETTLEMENT, state="non_revenue",
                                          rule="financing_proceeds_credit", entity="Fabrikam Capital"),
     ["Fabrikam Capital"], "ledger_admission"),
    (_step_11(CAPITAL_SETTLEMENT), _later("financing_proceeds_credit", CAPITAL_SETTLEMENT, state="non_revenue",
                                          rule="financing_proceeds_credit", entity="Fabrikam Capital"),
     None, "undeclared"),
    (_step_11(CAPITAL_SETTLEMENT), _later("financing_proceeds_credit", CAPITAL_SETTLEMENT, state="non_revenue",
                                          rule="financing_proceeds_credit", entity="Fabrikam Capital"),
     ["Contoso Capital"], "undeclared"),
    # The reversal-pair pass (its markers widened, §7.11); a duplicate is not it.
    (_step_11(HOLDER), _later("matched_reversal_pair", HOLDER, state="non_revenue"), None, "reversal_pair"),
    (_step_11(HOLDER), _later("duplicate_credit_exclusion", HOLDER, state="non_revenue"), None, "undeclared"),
    # Strong non-revenue declares only the words §7.11 adds to it.
    (_registry("operating_source_with_credit_context", "STRIPE DES ACCTVERIFY ID #"),
     _later("strong_non_revenue_rule", "STRIPE DES ACCTVERIFY ID #", state="non_revenue"), None, "acctverify"),
    (_registry("operating_source_with_credit_context", "IRS TREAS ### DES TAX REF"),
     _later("strong_non_revenue_rule", "IRS TREAS ### DES TAX REF", state="non_revenue"), None,
     "new_non_revenue_marker"),
    (_registry("operating_source_with_credit_context", "STRIPE DES INTEREST PAID"),
     _later("strong_non_revenue_rule", "STRIPE DES INTEREST PAID", state="non_revenue"), None, "undeclared"),
    # The reversal rule declares only a return code §7.11 adds, read as the classifier reads it (a code glued to a
    # digit is an ID's suffix; REVERSAL is 5.4's own word).
    (_registry("operating_source_with_credit_context", "STRIPE DES PAYMENT RTN ID #"),
     _later("reversal_cancellation_exclusion", "STRIPE DES PAYMENT RTN ID #", state="non_revenue"), None,
     "new_non_revenue_marker"),
    (_registry("operating_source_with_credit_context", "STRIPE DES PAYMENT ID ####RTN"),
     _later("reversal_cancellation_exclusion", "STRIPE DES PAYMENT ID ####RTN", state="non_revenue"), None,
     "undeclared"),
    (_registry("operating_source_with_credit_context", "STRIPE DES REVERSAL"),
     _later("reversal_cancellation_exclusion", "STRIPE DES REVERSAL", state="non_revenue"), None, "undeclared"),
    # Claim first off (§7.7): step 11's claim descriptor held with the insurer's credits; not a registry row.
    (_step_11(CLAIM), _later("insurer_customer_payment", CLAIM), None, "claim_first_off"),
    (_registry("operating_source_with_credit_context", CLAIM), _later("insurer_customer_payment", CLAIM), None,
     "undeclared"),
    # A row 5.4's recurrence lifted that 5.5 reads as a direction conflict; a step-11 row is not the pool's.
    (_registry("recurring_operating_source", "ELAVON MERCHANT DES DEPOSIT ID #", entity=None, alias=None),
     _later("direction_conflict", "ELAVON MERCHANT DES DEPOSIT ID #"), None, "direction_conflict_pool"),
    (_step_11("FABRIKAM DES MERCHANT DEPOSIT"), _later("direction_conflict", "FABRIKAM DES MERCHANT DEPOSIT"), None,
     "undeclared"),
    # The $1 floor governs the recurrence pool, not a row verified on its own context.
    (_registry("recurring_operating_source", "STRIPE DES TRANSFER ID #", cents=50),
     _later("operating_source_requires_context", "STRIPE DES TRANSFER ID #", cents=50, entity="Stripe"), None,
     "micro_deposit_floor"),
    (_registry("operating_source_with_credit_context", "STRIPE DES TRANSFER ID #", cents=50),
     _later("operating_source_requires_context", "STRIPE DES TRANSFER ID #", cents=50, entity="Stripe"), None,
     "undeclared"),
    # The channel gate: a closed row is never verified; a push row is refused to steps 11 to 14, not to the registry.
    (_registry("recurring_operating_source", "ZELLE FROM FABRIKAM STRIPE"),
     _later("unidentified_posted_credit", "ZELLE FROM FABRIKAM STRIPE", gate="closed"), None, "channel_gate"),
    (_step_11(PUSH), _later("ambiguous_credit_descriptor", PUSH, gate="push"), None, "channel_gate"),
    (_registry("operating_source_with_credit_context", PUSH), _later("ambiguous_credit_descriptor", PUSH, gate="push"),
     None, "undeclared"),
    # CUSTOMER ID (§7.11): step 11 whose every match needed it; not a registry row printing it (Truist prints it on
    # every ACH line), nor a row another CUSTOMER still verifies.
    (_step_11(TRUIST), _later("ambiguous_credit_descriptor", TRUIST), None, "customer_id"),
    (_registry("operating_source_with_credit_context", "STRIPE TRANSFER CUSTOMER ID ####### ST-XXXX SETTLEMENT"),
     _later("operating_source_requires_context", "STRIPE TRANSFER CUSTOMER ID ####### ST-XXXX SETTLEMENT",
            entity="Stripe"), None, "undeclared"),
    (_step_11("NORTHWIND CUSTOMER PAYMENT ACH CUSTOMER ID ####"),
     _later("ambiguous_credit_descriptor", "NORTHWIND CUSTOMER PAYMENT ACH CUSTOMER ID ####"), None, "undeclared"),
    # CUSTOMER with CHECK or CHEQUE (§7.11, Q3): step 11 only, and only when no other descriptor verified it.
    (_step_11(CHECK), _later("unidentified_posted_credit", CHECK), None, "customer_check"),
    (_registry("operating_source_with_credit_context", CHECK), _later("unidentified_posted_credit", CHECK), None,
     "undeclared"),
    (_step_11("FABRIKAM MERCHANT DEPOSIT CUSTOMER CHECK"),
     _later("unidentified_posted_credit", "FABRIKAM MERCHANT DEPOSIT CUSTOMER CHECK"), None, "undeclared"),
    # The receiver's value: the registry row must have lost its entity's reading, not kept it.
    (_registry("operating_source_with_credit_context", "FABRIKAM DES PAYMENT ID # INDN STRIPE STREET CAFE CO ID # CCD"),
     _later("operating_source_requires_context", "FABRIKAM DES PAYMENT ID # INDN STRIPE STREET CAFE CO ID # CCD",
            entity="Stripe"), None, "undeclared"),
    # The wire vetoes govern step 11's customer and invoice descriptors, not a settlement descriptor on a wire.
    (_step_11("WIRE TYPE WIRE IN ORIG FABRIKAM DESIGN INC OBI MERCHANT DEPOSIT"),
     _later("ambiguous_credit_descriptor", "WIRE TYPE WIRE IN ORIG FABRIKAM DESIGN INC OBI MERCHANT DEPOSIT",
            wire_vetoed=True), None, "undeclared"),
    # The holder veto (§5.2) governs steps 11 to 14, never the registry, and its outcome is holder_named_payer.
    (_step_11(HOLDER), _later("holder_named_payer", HOLDER, holder=True), None, "holder_veto"),
    (_registry("operating_source_with_credit_context", "DEPOSIT STRIPE CONTOSO BAKERY PAYOUT"),
     _later("operating_source_requires_context", "DEPOSIT STRIPE CONTOSO BAKERY PAYOUT", entity="Stripe", holder=True),
     None, "undeclared"),
    (_step_11(HOLDER), _later("unidentified_posted_credit", HOLDER, holder=True), None, "undeclared"),
    # The numbered-company guard (§5.2, T11) governs steps 11 to 14, never a processor's settlement or the registry.
    (_step_11(NUMBERED), _later("unidentified_posted_credit", NUMBERED, numbered=True), None, "numbered_company"),
    (_step_11("MISC PAYMENT ####### MERCHANT DEPOSIT"),
     _later("unidentified_posted_credit", "MISC PAYMENT ####### MERCHANT DEPOSIT", numbered=True), None, "undeclared"),
    (_registry("operating_source_with_credit_context", "MISC PAYMENT ####### STRIPE PAYOUT"),
     _later("ambiguous_credit_descriptor", "MISC PAYMENT ####### STRIPE PAYOUT", numbered=True), None, "undeclared"),
    # Square payroll: a Square row 5.4's recurrence lifted, with a pay word, Square read as a word (never SQ inside
    # BISQUE); the veto governs the pool only (S3.1 re-review), so a row verified on its own context that loses its
    # verification is undeclared whatever it prints.
    (_registry("recurring_operating_source", "SQUARE INC DES PAYROLL ID #", entity="Square", alias="SQUARE"),
     _later("operating_source_requires_context", "SQUARE INC DES PAYROLL ID #", entity="Square"), None,
     "square_payroll"),
    (_registry("operating_source_with_credit_context", "SQUARE INC DES PAYROLL ID #", entity="Square", alias="SQUARE"),
     _later("operating_source_requires_context", "SQUARE INC DES PAYROLL ID #", entity="Square"), None,
     "undeclared"),
    (_step_11("BISQUE BAKERY DES BONUS CUSTOMER PAYMENT ID #"),
     _later("unidentified_posted_credit", "BISQUE BAKERY DES BONUS CUSTOMER PAYMENT ID #"), None, "undeclared"),
    (_registry("recurring_operating_source", "BISQUE BAKERY DES BONUS STRIPE PAYOUT"),
     _later("operating_source_requires_context", "BISQUE BAKERY DES BONUS STRIPE PAYOUT", entity="Stripe"), None,
     "recurrence_veto"),
    (_registry("operating_source_related_activity", "STRIPE DES VERIFY PAYOUT"),
     _later("unidentified_posted_credit", "STRIPE DES VERIFY PAYOUT", recurrence_veto_wording=True), None,
     "recurrence_veto"),
    # The recurrence veto never explains a 5.4 single-row context row (its context, or the wholesale auction form):
    # no 5.5 rule leaves one unlifted or fallen for a veto word, the checkout's fact or the words notwithstanding.
    (_registry("operating_source_with_credit_context", "BISQUE BAKERY DES BONUS STRIPE PAYOUT"),
     _later("operating_source_requires_context", "BISQUE BAKERY DES BONUS STRIPE PAYOUT", entity="Stripe"), None,
     "undeclared"),
    (_registry("operating_source_with_credit_context", "STRIPE DES VERIFY PAYOUT"),
     _later("operating_source_requires_context", "STRIPE DES VERIFY PAYOUT", entity="Stripe",
            recurrence_veto_wording=True), None, "undeclared"),
    (_registry("operating_source_with_credit_context", "STRIPE DES PAYROLL INDN SQ BAKERY CO ID #"),
     _later("operating_source_requires_context", "STRIPE DES PAYROLL INDN SQ BAKERY CO ID #", entity="Stripe",
            recurrence_veto_wording=True), None, "undeclared"),
    (_registry("wholesale_auction_payout_form", "MANHEIM DES CAPITAL PAYOUT", entity="Manheim", alias="MANHEIM"),
     _later("operating_source_requires_context", "MANHEIM DES CAPITAL PAYOUT", entity="Manheim",
            recurrence_veto_wording=True), None, "undeclared"),
    (_registry("wholesale_auction_payout_form", "MANHEIM DES CAPITAL PAYOUT", entity="Manheim", alias="MANHEIM"),
     _later("unidentified_posted_credit", "MANHEIM DES CAPITAL PAYOUT", recurrence_veto_wording=True), None,
     "undeclared"),
    # The recurrence veto governs the registry's rows, never step 11's, whatever the fact or the words say.
    (_step_11("FABRIKAM CAPITAL PARTNERS DES MERCHANT SETTLEMENT ID #"),
     _later("unidentified_posted_credit", "FABRIKAM CAPITAL PARTNERS DES MERCHANT SETTLEMENT ID #",
            recurrence_veto_wording=True), None, "undeclared"),
    (_step_11("FABRIKAM INSURANCE AGENCY DES MERCHANT SETTLEMENT ID #"),
     _later("unidentified_posted_credit", "FABRIKAM INSURANCE AGENCY DES MERCHANT SETTLEMENT ID #"), None,
     "undeclared"),
    # An entity split takes a pool the recurrence lifted, not a row verified on its own context.
    (_registry("recurring_operating_source", "STRIPE SHOPIFY DES TRANSFER ID #"),
     _later("operating_source_requires_context", "STRIPE SHOPIFY DES TRANSFER ID #", entity="Shopify"), None,
     "entity_split"),
    (_registry("operating_source_with_credit_context", "STRIPE SHOPIFY DES TRANSFER ID #"),
     _later("operating_source_requires_context", "STRIPE SHOPIFY DES TRANSFER ID #", entity="Shopify"), None,
     "undeclared"),
])
def test_each_declared_cause_explains_only_its_own_rule_and_outcome(prior, later, admissions, cause):
    assert _causes([prior], [later], admissions) == {cause: 1}


def _held(method, text, *, cents=50, reason="non_sale_purpose"):
    """A 5.6 credit held for review (tier excluded_pending_review) with `reason`."""
    return _credit(0, cents, "unverified_deposit", method, tier="excluded_pending_review", reason=reason, text=text)


INVOICE = "NORTHWIND SUPPLY LLC DES INVOICE PAYMENT ID #"
PAYABLE = "NORTHWIND SUPPLY LLC DES ACCTS PAYABLE ID #"


@pytest.mark.parametrize(("prior", "later", "cause"), [
    # S4.4/S4.5 review, fix round 1: the $1 floor is absolute in 5.6 (§7.0, §8.10), so it declares a 5.4-verified credit
    # of any rule family that 5.6 holds by the floor: under 100 cents, held with the floor's reason (non_sale_purpose).
    (_registry("operating_source_with_credit_context", "SQUARE INC DES SQ###### ID #", entity="Square", alias="SQUARE",
               cents=3),
     _held("micro_deposit_floor", "SQUARE INC DES SQ###### ID #", cents=3), "micro_deposit_floor"),
    ({**_step_11(INVOICE), "cents": 50}, _held("micro_deposit_floor", INVOICE), "micro_deposit_floor"),
    (_credit(0, 99, "verified_revenue", "payer_remittance_descriptor", text=PAYABLE),
     _held("micro_deposit_floor", PAYABLE, cents=99), "micro_deposit_floor"),
    # Tied to the 5.6 outcome: a dollar is not under the floor, and a credit under it held for another reason is not
    # the floor's.
    ({**_step_11(INVOICE), "cents": 100}, _held("unidentified_posted_credit", INVOICE, cents=100), "undeclared"),
    ({**_step_11(INVOICE), "cents": 50}, _held("ambiguous_credit_descriptor", INVOICE, reason="possible_return"),
     "undeclared"),
])
def test_the_floor_declares_a_credit_of_any_rule_that_5_6_holds_under_one_dollar(prior, later, cause):
    assert _causes([prior], [later]) == {cause: 1}


def _pool(n, *, entity="Stripe", overrides=None):
    overrides = overrides or {}
    rows = []
    for i in range(n):
        credit = _credit(i, 50000 + 100 * i, "verified_revenue", "recurring_operating_source",
                         text="STRIPE DES TRANSFER ID #", entity=entity)
        credit["alias"] = "STRIPE"
        credit.update(overrides.get(i, {}))
        rows.append(credit)
    return rows


def _unlifted(n, *, entity="Stripe", **facts_by_row):
    return [_credit(i, 50000 + 100 * i, "unverified_deposit", "operating_source_requires_context",
                    text="STRIPE DES TRANSFER ID #", entity=(facts_by_row.get(f"entity{i}") or entity),
                    **facts_by_row.get(f"facts{i}", {}))
            for i in range(n)]


@pytest.mark.parametrize(("vetoed", "causes"), [
    (True, {"recurrence_veto": 1, "pool_below_recurrence_after_a_declared_veto": 2}),
    # No member was taken out by a declared veto: the pool fell below its count for no declared reason.
    (False, {"undeclared": 3}),
])
def test_a_pool_left_below_its_count_needs_a_vetoed_member_of_the_same_pool(vetoed, causes):
    laters = _unlifted(3, facts0={"recurrence_veto_wording": vetoed})
    assert _causes(_pool(3), laters) == causes


def test_a_vetoed_member_of_another_pool_or_account_explains_nothing():
    base = _snap("5.4", {"a": _account(_pool(2)), "b": _account(_pool(1))})
    vetoed_elsewhere = _unlifted(1, facts0={"recurrence_veto_wording": True})
    after = _snap("5.5", {"a": _account(_unlifted(2)), "b": _account(vetoed_elsewhere)})
    demoted = census.compare(base, [after])["runs"][0]["verified_demotions"]
    assert {cause: value["rows"] for cause, value in demoted.items()} == {"recurrence_veto": 1, "undeclared": 2}
    other_entity = _pool(3)
    other_entity[0]["entity"] = "Square"
    assert _causes(other_entity, _unlifted(3, facts0={"recurrence_veto_wording": True})) == {
        "recurrence_veto": 1, "undeclared": 2}


def test_a_pooled_direction_conflict_is_its_pool_s_declared_veto_by_the_registry_s_reading():
    """5.4 pooled a direction conflict the registry names; its own decision names no entity, so the snapshot's
    registry reading (registry_entity) keys its pool."""
    priors = _pool(3, overrides={2: {"entity": None, "registry_entity": "Stripe"}})
    laters = _unlifted(3)
    laters[2] = _credit(2, 50200, "unverified_deposit", "direction_conflict", text="STRIPE DES TRANSFER ID #")
    assert _causes(priors, laters) == {"direction_conflict_pool": 1,
                                       "pool_below_recurrence_after_a_declared_veto": 2}


def test_a_pool_split_by_one_member_s_re_reading_is_declared_for_every_member():
    laters = _unlifted(3, entity0="Shopify")
    assert _causes(_pool(3), laters) == {"entity_split": 3}


def test_the_admissions_list_is_given_to_compare_on_the_command_line(tmp_path, capsys):
    base, after = tmp_path / "s54.json.gz", tmp_path / "s55.json.gz"
    base.write_bytes(gzip.compress(json.dumps(_snap("5.4", {"a": _account([_step_11(CAPITAL_SETTLEMENT)])})).encode()))
    after.write_bytes(gzip.compress(json.dumps(_snap("5.5", {"a": _account([
        _later("financing_proceeds_credit", CAPITAL_SETTLEMENT, state="non_revenue", rule="financing_proceeds_credit",
               entity="Fabrikam Capital")])})).encode()))
    admissions = tmp_path / "admissions.json"
    admissions.write_text(json.dumps({"signed_off": "fabricated", "entities": ["Fabrikam Capital"]}), encoding="utf-8")
    report = tmp_path / "report.json"
    arguments = ["compare", "--base", str(base), "--after", str(after), "--out", str(report)]
    assert census.main(arguments + ["--admissions", str(admissions)]) == 0
    run = json.loads(report.read_text(encoding="utf-8"))["runs"][0]
    assert list(run["verified_demotions"]) == ["ledger_admission"]
    assert census.main(arguments) == 1
    assert list(json.loads(report.read_text(encoding="utf-8"))["runs"][0]["verified_demotions"]) == ["undeclared"]
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    assert census.main(arguments + ["--admissions", str(tmp_path / "broken.json")]) == 2


def test_the_square_capital_name_is_gone_and_every_declared_cause_is_produced():
    assert "square_capital" not in census.DECLARED_DEMOTIONS
    assert {"direction_conflict_pool", "customer_check", "numbered_company", "ledger_admission"} <= set(
        census.DECLARED_DEMOTIONS)


#: The facts a 5.5 snapshot carries (the S2.1 readers'), and those true_revenue.guard_facts adds in 5.6 (S4.2, S4.3).
FACTS_55 = {"gate": None, "holder": False, "numbered": False, "third_party_originator": False, "own_transfer": False,
            "pool_candidate": False, "pool_vetoed": False, "pool_threshold": 3, "wire_vetoed": False,
            "recurrence_veto_wording": False}
FACTS_56 = {"financing_root": False, "registry_root": False, "registry_financing": False, "pay_or_personal": False,
            "transfer_no_counterparty": False, "known_financing": False, "payout_or_factoring": False,
            "numbered_region": False, "customer_descriptor": False, "pooled_while_vetoed": False, "q6_shape": False,
            "q7_payer_ok": True, "q7_listed": False, "q7_credit_union": False, "q7_veto_word": False}
UNCHECKED_AT_55 = ["G2", "G3 step 11", "G4", "G5", "G9 tiers", "G11", "G12", "G13 region", "G13 step 11",
                   "G14 per row"]


def test_a_5_5_snapshot_reports_the_guards_its_facts_cannot_check():
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "unverified_deposit", "x")])})
    after = _snap("5.5", {"a": _account([_credit(0, 5000, "verified_revenue", "named_payer_repeats", **FACTS_55)])})
    run = _run(base, after)
    assert run["unchecked_guards"] == UNCHECKED_AT_55
    assert run["guard_checks"]["G2"] == {"checked": False, "facts": ["financing_root", "registry_root"],
                                         "status": "not checked (facts arrive in 5.6)"}
    assert {name: check["status"] for name, check in run["guard_checks"].items() if check["checked"]} == {
        name: "held" for name in ("G1", "G3", "G6", "G7b", "G9", "G10", "G13", "G14", "G15", "G16", "G17",
                                  "undeclared_demotion")}
    assert run["verdict"] == "hold" and run["failed_guards"] == []


def test_a_5_6_snapshot_with_the_guard_facts_checks_every_guard():
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "unverified_deposit", "x")])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "verified_revenue", "named_payer_repeats", tier="verified",
                                                 **FACTS_55, **FACTS_56)])})
    run = _run(base, after)
    assert run["unchecked_guards"] == [] and run["verdict"] == "hold"
    assert all(check["status"] == "held" for check in run["guard_checks"].values())
    after["accounts"]["a"]["credits"][0]["facts"]["financing_root"] = True
    run = _run(base, after)
    assert run["guard_checks"]["G2"]["status"] == "failed" and run["failed_guards"] == ["G2"]
    assert run["verdict"] == "fail"


def test_a_recorded_guard_failure_counts_though_the_run_lacks_another_key_of_its_check():
    """S3.1 re-review: a Verified row with financing_root and no registry_root key fails G2; the recorded failure
    proves the check ran, so it fails the verdict and G2 is not reported as unchecked."""
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "unverified_deposit", "x")])})
    after = _snap("5.5", {"a": _account([_credit(0, 5000, "verified_revenue", "named_payer_repeats",
                                                 **FACTS_55, financing_root=True)])})
    run = _run(base, after)
    assert run["guards"]["G2"]["failures"] == 1
    assert run["failed_guards"] == ["G2"] and run["verdict"] == "fail"
    assert run["guard_checks"]["G2"] == {"checked": True, "facts": ["financing_root", "registry_root"],
                                         "status": "failed"}
    assert "G2" not in run["unchecked_guards"]
    assert run["unchecked_guards"] == [name for name in UNCHECKED_AT_55 if name != "G2"]


def test_the_printed_report_never_shows_an_unchecked_guard_as_held(tmp_path, capsys):
    base, after = tmp_path / "s54.json.gz", tmp_path / "s55.json.gz"
    base.write_bytes(gzip.compress(json.dumps(_snap("5.4", {"a": _account([
        _credit(0, 5000, "unverified_deposit", "x")])})).encode()))
    after.write_bytes(gzip.compress(json.dumps(_snap("5.5", {"a": _account([
        _credit(0, 5000, "verified_revenue", "named_payer_repeats", **FACTS_55)])})).encode()))
    capsys.readouterr()
    assert census.main(["compare", "--base", str(base), "--after", str(after),
                        "--out", str(tmp_path / "report.json")]) == 0
    printed = capsys.readouterr().out
    assert "guards: every checked guard holds" in printed and "all hold" not in printed
    assert "not checked (facts arrive in 5.6): " + ", ".join(UNCHECKED_AT_55) in printed


@pytest.mark.parametrize("entry", ["directory", "file"])
@pytest.mark.parametrize("depth", [(), ("reports",), ("reports", "deeper")])
def test_no_output_is_written_inside_any_repository(tmp_path, capsys, entry, depth):
    """A folder holding a `.git` entry is a checkout (a directory) or a worktree (a file), of any repository."""
    snapshot = tmp_path / "base.json.gz"
    snapshot.write_bytes(gzip.compress(json.dumps(BASE).encode("utf-8")))
    checkout = tmp_path / "some-checkout"
    checkout.mkdir()
    if entry == "directory":
        (checkout / ".git").mkdir()
    else:
        (checkout / ".git").write_text("gitdir: ../elsewhere/.git/worktrees/some-checkout\n", encoding="utf-8")
    out = checkout.joinpath(*depth, "report.json")
    arguments = ["compare", "--base", str(snapshot), "--after", str(snapshot), "--out"]
    for spelling in (str(out), "\\\\?\\" + str(out)):
        assert census.main(arguments + [spelling]) == 2
        assert "inside the repository" in capsys.readouterr().err
    assert not out.exists() and not (checkout / "reports").exists()
    assert census.main(arguments + [str(tmp_path / "plain" / "report.json")]) == 0
    assert (tmp_path / "plain" / "report.json").is_file()


def test_the_extended_length_form_of_this_checkout_is_refused(capsys):
    assert census._output_repository(census.ROOT / "x-census.json") is not None
    assert census._output_repository(Path("\\\\?\\" + str(census.ROOT / "tools" / "x-census.json"))) is not None


def _volume_name(drive: str) -> str | None:
    """The `\\\\?\\Volume{...}\\` name of a drive (Windows), or None."""
    import ctypes

    buffer = ctypes.create_unicode_buffer(64)
    if not ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(drive, buffer, len(buffer)):
        return None
    return buffer.value


@pytest.mark.skipif(sys.platform != "win32", reason="a volume name is a Windows spelling")
def test_a_volume_name_spelling_of_a_checkout_is_refused(tmp_path, monkeypatch):
    """S3.1 re-review: the path is resolved before its `\\\\?\\` prefix is stripped, so a volume's name resolves to its
    drive; stripped first, `Volume{...}\\...` would be a relative path read against the working folder."""
    volume = _volume_name(tmp_path.anchor)
    if volume is None:
        pytest.skip("the temporary folder's drive has no volume name")
    checkout = tmp_path / "some-checkout"
    (checkout / ".git").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    inside = Path(volume + str(checkout / "reports" / "report.json")[len(tmp_path.anchor):])
    found = census._output_repository(inside)
    assert found is not None and os.path.samefile(found, checkout)
    assert census._output_repository(Path(volume + str(elsewhere / "report.json")[len(tmp_path.anchor):])) is None
    # This checkout, spelled by its volume's name.
    own = _volume_name(census.ROOT.resolve().anchor)
    if own is not None:
        assert census._output_repository(
            Path(own + str(census.ROOT.resolve() / "x-census.json")[len(census.ROOT.resolve().anchor):])) is not None


def test_the_pdf_basis_prefers_the_newest_route_whose_analysis_reconciles(tmp_path):
    cache = _FabricatedCache(tmp_path / "webapp_data")
    newest = cache.ocr(PDF_A, ["FABRICATED PAGE NEW"], "2031-03-02T00:00:00")
    older = cache.ocr(PDF_A, ["FABRICATED PAGE OLD"], "2031-03-01T00:00:00")
    cache.analysis(older, [_statement("XXXX1234")], "2031-03-03T00:00:00")
    cache._put("analysis", newest, {"analysis": {"accounts": [
        {"statement": _statement("XXXX1234", ROWS[:1]), "reconciliation": {"ok": False}}]}}, "2031-03-03T00:00:00")
    # PDF B: no route reconciles, so its newest analysed route is kept (and the snapshot's filter drops it).
    only_b = cache.ocr(PDF_B, ["FABRICATED PAGE B"], "2031-03-01T00:00:00")
    cache._put("analysis", only_b, {"analysis": {"accounts": [
        {"statement": _statement("XXXX5678"), "reconciliation": {"ok": False}}]}}, "2031-03-03T00:00:00")
    cache.connection.close()
    stats: dict = {}
    accounts = list(census.cached_accounts(cache.root, basis="pdf", stats=stats))
    assert [(key, len(account["statement"]["transactions"])) for key, account in accounts] == [
        (f"p{PDF_A[:12]}.0", len(ROWS)), (f"p{PDF_B[:12]}.0", len(ROWS))]
    assert (stats["pdfs_joined_on_newest_route"], stats["pdfs_on_an_older_reconciling_route"],
            stats["pdfs_without_a_reconciling_route"]) == (1, 1, 1)
    assert len(census.snapshot(iter(accounts), basis="pdf")["accounts"]) == 1


def test_the_snapshot_masks_the_bank_and_records_the_registry_s_pool_key():
    from analysis.schema import Statement

    payload = _statement("XXXX1234", [(3, "SQUARE INC DES SETTLEMENT ID 1234", 500.0)])
    payload["bank"] = "FABRICATED BANK 24"
    snap = census.account_snapshot({"statement": Statement.model_validate(payload).model_dump(mode="json")})
    assert snap["bank"] == "FABRICATED BANK ##"
    assert snap["credits"][0]["registry_entity"] == "Square"


def test_one_fabricated_statement_snapshots_with_its_tiers_and_facts():
    from analysis.serialization import document_report_to_dict
    from tests.test_webapp_studio_views import _report

    rows = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 300.0),
            (4, "FABRIKAM FUNDING LLC DES:PAYMENT ID:1", 900.0), (5, "INTERNAL TRANSFER FROM SAVINGS", 100.0),
            (9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)]
    payload = document_report_to_dict(_report("CONTOSO BAKERY LLC", "000000001010", 1500.0, rows))
    # A statement of one account is served flat; a document of several carries `accounts`.
    snap = census.snapshot([("s", payload["accounts"][0] if "accounts" in payload else payload)])
    [account] = snap["accounts"].values()
    tiers = sorted((credit["tier"], credit["reason"]) for credit in account["credits"])
    assert tiers == [("counted_flagged", "check_deposit"), ("excluded_pending_review", "financing_named_payer"),
                     ("non_revenue", None), ("verified", None)]
    # Every digit is masked in the census output.
    assert not any(ch.isdigit() for credit in account["credits"] for ch in credit["text"])
    assert account["credits"][2]["facts"]["financing_root"]
    assert account["posted_credit_count"] == 4 and account["posted_credit_cents"] == 200000
    assert _run(snap, snap)["guards"] == {}


def test_the_holder_guards_skip_a_row_the_registry_or_a_payout_entity_claimed():
    # §8.1 (S4.2 review M1): the holds skip claimed rows, so G3 and G17 never fail on a platform's payout into a holder
    # whose name the platform shares; an unclaimed holder row still fails.
    claimed = _credit(0, 100, "unverified_deposit", "unidentified_posted_credit", tier="counted_flagged",
                      reason="payout_credit_entity", holder=True, own_transfer=True, claimed=True)
    assert not census._row_guards(claimed)["G3"] and not census._row_guards(claimed)["G17"]
    unclaimed = dict(claimed, facts={"holder": True, "own_transfer": True, "claimed": False})
    assert census._row_guards(unclaimed)["G3"] and census._row_guards(unclaimed)["G17"]


@pytest.mark.parametrize(("holder", "text"), [
    ("SEZZLE SALON LLC", "SEZZLE DES:PAYOUT ID:1"),
    ("SQUARE ONE BAKERY LLC", "SQUARE INC DES:TRANSFER ID:1"),
])
def test_a_platform_payout_into_a_holder_named_like_it_passes_the_guards(holder, text):
    from analysis.schema import Statement, Transaction

    statement = Statement(account_name=holder, transactions=[
        Transaction(date="2054-03-02", description=text, amount=500.0, direction="credit")])
    snap = census.account_snapshot({"statement": statement.model_dump(mode="json")})
    [credit] = snap["credits"]
    assert credit["tier"] == "counted_flagged" and credit["facts"]["claimed"]
    assert not any(census._row_guards(credit).values())


# S4.2 fix round 4: the reversal rule's French cancel words (ANNUL, ANNULE, ANNULEE, ANNULATION), which 5.4 never read,
# are a new non-revenue marker of that rule, as its return codes are; read as the classifier reads them.
ANNULE_ROW = "STRIPE DES PAYMENT ANNULE ID #"


@pytest.mark.parametrize(("prior", "later", "cause"), [
    (_registry("operating_source_with_credit_context", ANNULE_ROW),
     _later("reversal_cancellation_exclusion", ANNULE_ROW, state="non_revenue"), "new_non_revenue_marker"),
    (_step_11("FABRIKAM DES CUSTOMER PAYMENT ANNULATION ####"),
     _later("reversal_cancellation_exclusion", "FABRIKAM DES CUSTOMER PAYMENT ANNULATION ####", state="non_revenue"),
     "new_non_revenue_marker"),
    (_step_11("FABRIKAM CUSTOMER PAYMENT ####ANNULEE"),
     _later("reversal_cancellation_exclusion", "FABRIKAM CUSTOMER PAYMENT ####ANNULEE", state="non_revenue"),
     "new_non_revenue_marker"),
    (_step_11("ANNUL FABRIKAM CUSTOMER PAYMENT"),
     _later("reversal_cancellation_exclusion", "ANNUL FABRIKAM CUSTOMER PAYMENT", state="non_revenue"),
     "new_non_revenue_marker"),
    # A reversal pair keeps its own cause.
    (_registry("operating_source_with_credit_context", ANNULE_ROW),
     _later("matched_reversal_pair", ANNULE_ROW, state="non_revenue"), "reversal_pair"),
    # Not the words: a word that only starts like them, or one glued to a digit after it (an ID's prefix).
    (_step_11("FABRIKAM ANNULUS CUSTOMER PAYMENT"),
     _later("reversal_cancellation_exclusion", "FABRIKAM ANNULUS CUSTOMER PAYMENT", state="non_revenue"),
     "undeclared"),
    (_step_11("FABRIKAM CUSTOMER PAYMENT ANNULE####"),
     _later("reversal_cancellation_exclusion", "FABRIKAM CUSTOMER PAYMENT ANNULE####", state="non_revenue"),
     "undeclared"),
    # Not the rule: the words on a row another rule demoted.
    (_registry("operating_source_with_credit_context", ANNULE_ROW),
     _later("strong_non_revenue_rule", ANNULE_ROW, state="non_revenue"), "undeclared"),
    (_registry("operating_source_with_credit_context", ANNULE_ROW),
     _later("duplicate_credit_exclusion", ANNULE_ROW, state="non_revenue"), "undeclared"),
    (_step_11("FABRIKAM DES CUSTOMER PAYMENT ANNULE"),
     _later("unidentified_posted_credit", "FABRIKAM DES CUSTOMER PAYMENT ANNULE"), "undeclared"),
])
def test_the_reversal_rule_s_french_cancel_words_are_a_declared_new_marker(prior, later, cause):
    assert _causes([prior], [later]) == {cause: 1}


# S4.2 fix round 5: the plurals ANNULES and ANNULEES joined the reversal rule's French cancel words.
@pytest.mark.parametrize("text", ["FABRIKAM DES CUSTOMER PAYMENT ANNULES ####", "FABRIKAM CUSTOMER PAYMENT ANNULEES"])
def test_the_reversal_rule_s_french_plural_cancel_words_are_a_declared_new_marker(text):
    later = _later("reversal_cancellation_exclusion", text, state="non_revenue")
    assert _causes([_step_11(text)], [later]) == {"new_non_revenue_marker": 1}


# S3.1 privacy fix (the census masks every digit): the per-credit record writes an entity or alias as-is only when the
# snapshot's code names it in a registry or ledger table; any other name (S4.3: Q7's credit-union arm names the credit
# union from the payer region; D1's bank line advance names the statement's bank) is written through mask().
NAMED_ROWS = [
    (2, "SAMPLE1234 CU DES:VHCL PURCH ID:1", 18000.0),
    (3, "SAMPLE1234 CU DES:VHCL PURCH ID:2", 21000.0),
    (4, "LOAN CREDIT", 5000.0),
    (5, "SHIFT4 CAPITAL DES:FUNDING ID:1", 9000.0),
    (6, "SHIFT4 PAYMENTS DES:SETTLEMENT ID:1", 700.0),
    (7, "11 101 SIGNAL R DES:SETTLEMENT ID:1", 800.0),
]


def _named_snapshot():
    from analysis.schema import Statement

    payload = _statement("XXXX1234", NAMED_ROWS)
    payload.update(bank="FABRICATED BANK 24", account_name="SAMPLE MOTORS LLC")
    return census.account_snapshot({"statement": Statement.model_validate(payload).model_dump(mode="json")})


def test_the_snapshot_masks_an_entity_or_alias_no_registry_names():
    snap = _named_snapshot()
    assert [(credit["method"], credit["entity"], credit["alias"]) for credit in snap["credits"]] == [
        ("auto_lender_dealer_funding", "CU", "SAMPLE#### CU"),
        ("auto_lender_dealer_funding", "CU", "SAMPLE#### CU"),
        ("financing_proceeds_credit", "FABRICATED BANK ##", None),
        # Registry and ledger names are written as-is, digits and all: the census compares them by name.
        ("financing_proceeds_credit", "Shift4 Capital", "SHIFT4 CAPITAL"),
        ("operating_source_with_credit_context", "Shift4", "SHIFT4 PAYMENTS"),
        ("operating_source_with_credit_context", "11-101 Signal R", "11 101 SIGNAL R"),
    ]
    # The registry's reading is always an operating-registry entity.
    assert [credit["registry_entity"] for credit in snap["credits"]] == [
        None, None, None, "Shift4", "Shift4", "11-101 Signal R"]


def test_a_credit_union_named_with_digits_is_written_masked(monkeypatch):
    from dataclasses import replace

    from analysis import transaction_classifier

    classify = transaction_classifier.classify_statement_transactions

    def fabricated(*args, **kwargs):
        return [
            replace(record, revenue_canonical_entity="SAMPLE CU 1234", revenue_matched_alias="SAMPLE CU 1234")
            if record.revenue_match_method == "auto_lender_dealer_funding" else record
            for record in classify(*args, **kwargs)
        ]

    monkeypatch.setattr(transaction_classifier, "classify_statement_transactions", fabricated)
    credits = _named_snapshot()["credits"]
    assert [(credit["entity"], credit["alias"]) for credit in credits[:2]] == [("SAMPLE CU ####", "SAMPLE CU ####")] * 2
    assert credits[3]["entity"] == "Shift4 Capital"


def test_the_ledger_admission_still_reads_shift4_capital_by_name():
    after = _snap("5.5", {"a": _named_snapshot()})
    base = json.loads(json.dumps(after))
    base["classification_version"] = "5.4"
    base["accounts"]["a"]["credits"][3].update(state="verified_revenue", method="operating_income_descriptor",
                                               rule="verified_operating_income_descriptor", entity=None, alias=None)
    demoted = census.compare(base, [after], admissions=["Shift4 Capital"])["runs"][0]["verified_demotions"]
    assert {cause: value["rows"] for cause, value in demoted.items()} == {"ledger_admission": 1}


def test_a_name_masked_in_a_later_snapshot_is_the_name_an_older_snapshot_wrote_unmasked():
    """A snapshot written before the fix holds every name unmasked: its pool key and the later snapshot's masked
    spelling of it are one name, so the pool is not split. Two names without a masked digit compare as before."""
    laters = _unlifted(3, entity="SAMPLE CU ####", facts0={"recurrence_veto_wording": True})
    assert _causes(_pool(3, entity="SAMPLE CU 1234"), laters) == {
        "recurrence_veto": 1, "pool_below_recurrence_after_a_declared_veto": 2}
    assert _causes(_pool(3, entity="Shift4"), _unlifted(3, entity="Shift5")) == {"entity_split": 3}
    assert census._same_name("SAMPLE CU ####", "SAMPLE CU 1234") and census._same_name(None, None)
    assert not census._same_name("SAMPLE CU ####", "OTHER CU 1234") and not census._same_name("Shift4", "Shift5")
    assert not census._same_name(None, "SAMPLE CU ####")


# ---------------------------------------------------------------------------------------------------------------------
# The final whole-branch review's fix wave (2026-09-30): I7 (every §20 demotion cause, one declared table), I8 (the
# loose guards) and M11 (the accounts and skips only the later run holds). Fabricated rows only.
# ---------------------------------------------------------------------------------------------------------------------
FACTOR_WIRE = "WIRE TYPE WIRE IN ORIG SAMPLE FACTOR LLC ID # PMT DET INV ####"
Q5_WIRE = "WIRE TYPE WIRE IN ORIG FABRIKAM EXPORTS LLC ID # SND BK SAMPLE BANK ID #"
ACH_ROW = "NORTHWIND SUPPLY LLC DES PAYMENT ID # INDN CONTOSO BAKERY LLC CO ID ########## CCD"
#: Audit B5 (I15, I55): PNC's CORPORATE ACH layout and a Chase export's empty ORIG CO label, digit-masked.
PNC_ROW = "CORPORATE ACH PAYMENTS ################# NORTHWIND SUPPLY ##########"
EMPTY_LABEL_ROW = "ORIG CO ACH CREDIT"
#: GOV (owner ruling 2026-09-30): a state's unemployment deposit (class B) and a Farm Service Agency payment (class D),
#: digit-masked.
GOV_UI = "ACH DEPOSIT NYS DOL UI DD UI DD #######"
GOV_GRANT = "FSA TREAS ### MISC PAY ####"


def _q56(method, text, **extra):
    """A credit a 5.6 base verified by Q5 or Q6."""
    return {**_credit(0, 500000, "verified_revenue", method, tier="verified", text=text), **extra}


def _after56(method, text, *, tier, reason, rule=None, **facts):
    return _credit(0, 500000, "unverified_deposit", method, tier=tier, reason=reason, text=text, rule=rule, **facts)


def _cause56(prior, later):
    base = _snap("5.6", {"a": _account([prior])})
    after = _snap("5.6", {"a": _account([later])})
    run = _run(base, after)
    return {cause: value["rows"] for cause, value in run["verified_demotions"].items()}, run


@pytest.mark.parametrize(("prior", "later", "cause"), [
    # The factor is never verified (§20 A3-H review): an earlier rule's verification overruled, or a Q5/Q6 repeat
    # refused, read as factoring_payout with the pass's own factor reading.
    (_q56("wire_remittance_purpose", FACTOR_WIRE),
     _after56("factoring_payout_payer", FACTOR_WIRE, tier="counted_flagged", reason="factoring_payout",
              rule="factoring_payer_never_verified"), "factor_never_verified"),
    (_q56("payer_remittance_descriptor", FACTOR_WIRE),
     _after56("factoring_payout_payer", FACTOR_WIRE, tier="counted_flagged", reason="factoring_payout",
              rule="factoring_payer_never_verified"), "factor_never_verified"),
    (_q56("repeat_wire_sender", FACTOR_WIRE),
     _after56("unidentified_posted_credit", FACTOR_WIRE, tier="counted_flagged", reason="factoring_payout",
              factoring_payer=True), "factor_never_verified"),
    (_q56("repeat_wire_sender", FACTOR_WIRE),
     _after56("unidentified_posted_credit", FACTOR_WIRE, tier="counted_flagged", reason="factoring_payout"),
     "undeclared"),
    # A Q5/Q6 row a later 5.6 hold names: the holder test, a personal trust, the holder's currency conversion, a title
    # firm, a bank-originated wire (by the pass's own hold reading), or a relaying bank's customer.
    (_q56("repeat_wire_sender", Q5_WIRE),
     _after56("unidentified_posted_credit", Q5_WIRE, tier="excluded_pending_review", reason="holder_name"),
     "q5_q6_held_holder_name"),
    (_q56("repeat_wire_sender", Q5_WIRE),
     _after56("unidentified_posted_credit", Q5_WIRE, tier="excluded_pending_review", reason="non_sale_purpose",
              hold_rule="personal_trust"), "q5_q6_held_personal_trust"),
    (_q56("named_payer_company_form", ACH_ROW),
     _after56("unidentified_posted_credit", ACH_ROW, tier="excluded_pending_review", reason="non_sale_purpose",
              hold_rule="currency_conversion"), "q5_q6_held_currency_conversion"),
    (_q56("named_payer_company_form", ACH_ROW),
     _after56("unidentified_posted_credit", ACH_ROW, tier="excluded_pending_review", reason="non_sale_purpose",
              hold_rule="title_firm"), "q5_q6_held_title_firm"),
    (_q56("repeat_wire_sender", Q5_WIRE),
     _after56("unidentified_posted_credit", Q5_WIRE, tier="excluded_pending_review",
              reason="financing_named_payer", hold_rule="bank_originated_wire"), "q5_q6_held_bank_originated_wire"),
    (_q56("repeat_wire_sender", Q5_WIRE),
     _after56("unidentified_posted_credit", Q5_WIRE, tier="counted_flagged", reason="wire_named_sender",
              relayed_customer=True), "q5_q6_relayed_customer"),
    # GOV (owner ruling 2026-09-30): a Q6 repeat that is a personal benefit (class B) or a grant (class D).
    (_q56("named_payer_repeats", GOV_UI),
     _after56("unidentified_posted_credit", GOV_UI, tier="excluded_pending_review", reason="personal_income",
              hold_rule="government_benefit"), "q5_q6_held_government_benefit"),
    (_q56("named_payer_repeats", GOV_GRANT),
     _after56("unidentified_posted_credit", GOV_GRANT, tier="excluded_pending_review", reason="non_sale_purpose",
              hold_rule="government_grant"), "q5_q6_held_government_grant"),
    (_q56("named_payer_repeats", GOV_UI),
     _after56("unidentified_posted_credit", GOV_UI, tier="excluded_pending_review", reason="personal_income"),
     "undeclared"),
    (_q56("named_payer_repeats", GOV_GRANT),
     _after56("unidentified_posted_credit", GOV_GRANT, tier="excluded_pending_review", reason="personal_income",
              hold_rule="government_grant"), "undeclared"),
    # Keyed on the rule that fires: a hold with no such reading, or another rule's row, is undeclared.
    (_q56("repeat_wire_sender", Q5_WIRE),
     _after56("unidentified_posted_credit", Q5_WIRE, tier="excluded_pending_review", reason="non_sale_purpose"),
     "undeclared"),
    (_q56("named_payer_company_form", ACH_ROW),
     _after56("unidentified_posted_credit", ACH_ROW, tier="excluded_pending_review", reason="financing_named_payer",
              hold_rule="personal_trust"), "undeclared"),
    (_step_11(INVOICE),
     _after56("unidentified_posted_credit", INVOICE, tier="excluded_pending_review", reason="holder_name"),
     "undeclared"),
    # The premium-coded insurer entry (§20 A3-H): Q6c refuses it as proof.
    (_q56("public_or_healthcare_payer", "SAMPLE HEALTH PLAN DES PREM ID #"),
     _after56("unidentified_posted_credit", "SAMPLE HEALTH PLAN DES PREM ID #", tier="counted_flagged",
              reason="named_payer_purpose_refused", premium_coded=True), "premium_coded_insurer_entry"),
    (_q56("public_or_healthcare_payer", "SAMPLE HEALTH PLAN DES PREM ID #"),
     _after56("unidentified_posted_credit", "SAMPLE HEALTH PLAN DES PREM ID #", tier="counted_flagged",
              reason="named_payer_purpose_refused"), "undeclared"),
    # Final review I3: a short healthcare alias inside a business's name no longer verifies by Q6c.
    (_q56("public_or_healthcare_payer", ACH_ROW),
     _after56("unidentified_posted_credit", ACH_ROW, tier="counted_flagged", reason="named_payer_one_off",
              short_healthcare_alias=True), "short_healthcare_alias_in_a_name"),
    # §15 deferred sources and the rows left to their family: Q5/Q6 never verify them.
    (_q56("named_payer_repeats", ACH_ROW),
     _after56("unidentified_posted_credit", ACH_ROW, tier="counted_flagged", reason="named_payer_purpose_refused",
              deferred_source=True), "q5_q6_deferred_source"),
    (_q56("named_payer_repeats", "STRIPE DES TRANSFER ID #"),
     _after56("operating_source_requires_context", "STRIPE DES TRANSFER ID #", tier="counted_flagged",
              reason="platform_unconfirmed"), "q5_q6_left_to_its_family"),
    # Pass 6: an accounts-payable remittance whose payer the statement also debits.
    (_q56("payer_remittance_descriptor", PAYABLE),
     _after56("payer_remittance_with_counter_debit", PAYABLE, tier="excluded_pending_review",
              reason="payer_also_debited"), "counter_debit"),
    # Audit B4 (I38, I22, I56): a Q5 or Q6 row whose payer a debit now names (a glued or spaced name, a split
    # reference, a funder's cut name by prefix, a three-letter payroll provider): the counter-debit holds of §8.1.
    (_q56("named_payer_company_form", ACH_ROW),
     _after56("unidentified_posted_credit", ACH_ROW, tier="excluded_pending_review", reason="payer_also_debited"),
     "q5_q6_held_counter_debit"),
    (_q56("repeat_wire_sender", Q5_WIRE),
     _after56("unidentified_posted_credit", Q5_WIRE, tier="excluded_pending_review", reason="payer_debited_as_lender"),
     "q5_q6_held_lender_counter_debit"),
    # Keyed on the hold alone: a counter-debit hold beside another hold reading, or another rule's row, is undeclared.
    (_q56("named_payer_company_form", ACH_ROW),
     _after56("unidentified_posted_credit", ACH_ROW, tier="excluded_pending_review", reason="payer_also_debited",
              hold_rule="owner_money"), "undeclared"),
    (_step_11(INVOICE),
     _after56("unidentified_posted_credit", INVOICE, tier="excluded_pending_review", reason="payer_also_debited"),
     "undeclared"),
    # Audit B5 (I15, I55): a Q5 or Q6 repeat keyed on a bank's label, entry or reference (PNC's entry word, an empty
    # ORIG CO label), now that the payer region reads the payer printed after it (the pass's payer_label_layout fact):
    # counted as a one-off payer, or as no payer printed.
    (_q56("named_payer_repeats", PNC_ROW),
     _after56("unidentified_posted_credit", PNC_ROW, tier="counted_flagged", reason="named_payer_one_off",
              payer_label_layout=True), "q5_q6_payer_after_a_label"),
    (_q56("named_payer_repeats", EMPTY_LABEL_ROW),
     _after56("unidentified_posted_credit", EMPTY_LABEL_ROW, tier="counted_flagged", reason="no_payer_printed",
              payer_label_layout=True), "q5_q6_payer_after_a_label"),
    # Keyed on the fact and the counted tier: without the fact, or held, the demotion is undeclared.
    (_q56("named_payer_repeats", PNC_ROW),
     _after56("unidentified_posted_credit", PNC_ROW, tier="counted_flagged", reason="named_payer_one_off"),
     "undeclared"),
    (_q56("named_payer_repeats", PNC_ROW),
     _after56("unidentified_posted_credit", PNC_ROW, tier="excluded_pending_review", reason="non_sale_purpose",
              payer_label_layout=True), "undeclared"),
    (_step_11(INVOICE),
     _after56("unidentified_posted_credit", INVOICE, tier="counted_flagged", reason="named_payer_one_off",
              payer_label_layout=True), "undeclared"),
    # The $1 floor's own method (pass 7's last step).
    ({**_q56("named_payer_repeats", ACH_ROW), "cents": 40},
     {**_after56("micro_deposit_floor", ACH_ROW, tier="excluded_pending_review", reason="non_sale_purpose"),
      "cents": 40}, "micro_deposit_floor"),
])
def test_every_section_20_demotion_is_declared_by_the_rule_that_fires(prior, later, cause):
    causes, _ = _cause56(prior, later)
    assert causes == {cause: 1}


def test_a_platform_credit_whose_entry_leads_with_a_financing_word_is_a_declared_demotion():
    # Re-review N6: keyed on the registry's own rule for the financing entry; another registry reading is undeclared.
    text = "SQUARE INC DES CAPITAL PAYOUT ID #"
    prior = _registry("operating_source_with_credit_context", text, entity="Square", alias="SQUARE")
    later = _held("operating_source_requires_context", text, cents=5000, reason="financing_named_payer")
    assert _causes([prior], [{**later, "rule": census.PLATFORM_FINANCING_ENTRY_RULE}]) == {"platform_financing_entry": 1}
    assert _causes([prior], [{**later, "rule": "operating_source_without_payout_context"}]) == {"undeclared": 1}
    from analysis.transaction_classifier import PLATFORM_FINANCING_ENTRY_RULE

    assert census.PLATFORM_FINANCING_ENTRY_RULE == PLATFORM_FINANCING_ENTRY_RULE


def test_the_cra_refund_is_a_declared_new_non_revenue_marker():
    text = "DIRECT DEPOSIT CANADA RIT ####"
    base = _snap("5.4", {"a": _account([_step_11(text)])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "non_revenue", "strong_non_revenue_rule",
                                                 tier="non_revenue", text=text)])})
    assert {cause: value["rows"] for cause, value in _run(base, after)["verified_demotions"].items()} == {
        "new_non_revenue_marker": 1}
    other = _snap("5.6", {"a": _account([_credit(0, 5000, "non_revenue", "strong_non_revenue_rule",
                                                  tier="non_revenue", text="DIRECT DEPOSIT CANADA RITE ####")])})
    assert "undeclared" in _run(_snap("5.4", {"a": _account([_step_11("DIRECT DEPOSIT CANADA RITE ####")])}),
                                other)["verified_demotions"]


@pytest.mark.parametrize(("text", "cause"), [
    # GOV (owner ruling 2026-09-30, class C): the GST/HST refund forms and a payment the IRS issues joined the strong
    # non-revenue rule, so a verified row they take is a declared new non-revenue marker.
    ("DIRECT DEPOSIT CANADA GST TPS", "new_non_revenue_marker"),
    ("GST CANADA ####", "new_non_revenue_marker"),
    ("RQ GST", "new_non_revenue_marker"),
    ("ELECTRONIC DEPOSIT FROM IRS TREAS ###", "new_non_revenue_marker"),
    ("ACH CREDIT IRS TREAS ### XXXXXXXXXXX#### ####", "new_non_revenue_marker"),
    # GOV review (M3): the classifier's posting words before the form (EFT, PAY, GC and its number, a glued date), and
    # (M4) the CRA's name, a country code and the GST program account after it.
    ("EFT GST CANADA", "new_non_revenue_marker"),
    ("PAY GST CANADA", "new_non_revenue_marker"),
    ("GC #### GST CANADA", "new_non_revenue_marker"),
    ("####GST CANADA", "new_non_revenue_marker"),
    ("PREAUTHORIZED CREDIT RQ GST", "new_non_revenue_marker"),
    ("CANADA GST TPS CANADA", "new_non_revenue_marker"),
    ("GST CANADA CA", "new_non_revenue_marker"),
    ("DEPOSIT CANADA GST TPS RT####", "new_non_revenue_marker"),
    # GST inside a name is no refund form.
    ("GST CANADA LOGISTICS INC DES PAYMENT ID #", "undeclared"),
    ("NORTHWIND RQ GST SUPPLY", "undeclared"),
])
def test_gov_the_government_tax_refunds_are_declared_new_non_revenue_markers(text, cause):
    base = _snap("5.4", {"a": _account([_step_11(text)])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "non_revenue", "strong_non_revenue_rule",
                                                 tier="non_revenue", text=text)])})
    assert {name: value["rows"] for name, value in _run(base, after)["verified_demotions"].items()} == {cause: 1}


def test_the_declared_table_is_the_one_the_compare_reads(monkeypatch):
    prior = _q56("repeat_wire_sender", Q5_WIRE)
    later = _after56("unidentified_posted_credit", Q5_WIRE, tier="excluded_pending_review", reason="holder_name")
    causes, run = _cause56(prior, later)
    assert causes == {"q5_q6_held_holder_name": 1} and "undeclared_demotion" not in run["guards"]
    monkeypatch.setattr(census, "DECLARED_DEMOTIONS",
                        tuple(name for name in census.DECLARED_DEMOTIONS if name != "q5_q6_held_holder_name"))
    _, run = _cause56(prior, later)
    assert run["guards"]["undeclared_demotion"]["failures"] == 1


def test_every_cause_the_census_can_name_is_in_the_declared_table():
    import inspect

    named = set(re.findall(r'return "([a-z0-9_]+)"', inspect.getsource(census._demotion_cause)))
    assert named - {"undeclared"} <= set(census.DECLARED_DEMOTIONS)


@pytest.mark.parametrize(("base_method", "base_text", "after_text", "narrowing"), [
    # Final review I8: narrowing 5 needs a loan-reading base and LOAN in the base where the later text prints LN.
    ("strong_non_revenue_rule", "DEPOSIT ## OAK LOAN", "DEPOSIT ## OAK LN", "5_street_ln"),
    ("reversal_cancellation_exclusion", "RETURN ITEM ## OAK LOAN", "RETURN ITEM ## OAK LN", None),
    ("duplicate_credit_exclusion", "WIRE TYPE WIRE IN ORIG #/SAMPLE CO # OAK LN", "WIRE TYPE WIRE IN ORIG SAMPLE CO # OAK LN",
     None),
    ("strong_non_revenue_rule", "DEPOSIT ## OAK LOAN", "DEPOSIT ## OAK LOAN LN", None),
])
def test_narrowing_5_is_only_the_street_ln_guard_on_a_loan_reading(base_method, base_text, after_text, narrowing):
    base = _credit(0, 5000, "non_revenue", base_method, text=base_text)
    after = _credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged", reason="no_payer_printed",
                    text=after_text)
    assert census._narrowing(base, after) == narrowing


@pytest.mark.parametrize(("base_method", "text", "tier", "state", "fails"), [
    # Final review I8: narrowings 2 and 6 lead to True only through verification (§6.3).
    ("insurance_provider_credit_exclusion", "SAMPLE MUTUAL DES HCCLAIMPMT", "counted_flagged", "unverified_deposit",
     True),
    ("insurance_provider_credit_exclusion", "SAMPLE MUTUAL DES HCCLAIMPMT", "verified", "verified_revenue", False),
    ("insurance_provider_credit_exclusion", "SAMPLE MUTUAL DES HCCLAIMPMT", "excluded_pending_review",
     "unverified_deposit", False),
    ("reversal_cancellation_exclusion", "DEBIT CARD CREDIT SAMPLE STORE", "counted_flagged", "unverified_deposit", True),
    ("reversal_cancellation_exclusion", "DEBIT CARD CREDIT SAMPLE STORE", "verified", "verified_revenue", False),
])
def test_narrowings_2_and_6_reach_true_only_when_verified(base_method, text, tier, state, fails):
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "non_revenue", base_method, text=text)])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, state, "x", tier=tier, reason="named_payer_one_off"
                                                 if tier != "verified" else None, text=text)])})
    assert ("G1" in _run(base, after)["guards"]) is fails


@pytest.mark.parametrize(("text", "fails"), [
    ("KLARNA BALANCE WITHDRAWAL", True), ("AFFIRMCARD REFUND", True), ("SP AFF ####", True),
    ("TRUEACCORD KLARNA", True), ("KLARNA INC DES SETTLEMENT ID #", False),
])
def test_narrowing_8_fails_on_the_consumer_words(text, fails):
    # Final review I8: the OQ2 ruling covers the providers' merchant settlements, never a consumer-side credit.
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "non_revenue", "financing_proceeds_credit",
                                                entity="Klarna Inc", lender_credit=True, text=text)])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="named_payer_unlabelled", entity="Klarna Inc", text=text)])})
    assert ("G1" in _run(base, after)["guards"]) is fails


@pytest.mark.parametrize(("base_method", "base_text", "after_text", "fails"), [
    # Final review I8: G7b fails for any non_revenue base a text change takes into True, except the street-LN guard's
    # own release (a LOAN the base read, printed LN at the end of a street address).
    ("strong_non_revenue_rule", "DEPOSIT ## COMMERCIAL LOAN DISB", "DEPOSIT ## COMMERCIAL LN DISB", True),
    ("strong_non_revenue_rule", "DEPOSIT ## OAK LOAN PMT", "DEPOSIT ## OAK LN PMT", True),
    ("financing_proceeds_credit", "DEPOSIT ## OAK LOAN", "DEPOSIT ## OAK LN", False),
    ("strong_non_revenue_rule", "DEPOSIT ## OAK LOAN", "DEPOSIT ## OAK LN", False),
    ("duplicate_credit_exclusion", "WIRE TYPE WIRE IN ORIG #/SAMPLE CO", "WIRE TYPE WIRE IN ORIG SAMPLE CO", True),
])
def test_g7b_fails_for_any_non_revenue_base_a_text_change_takes_into_true(base_method, base_text, after_text,
                                                                           fails):
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "non_revenue", base_method, text=base_text)])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="no_payer_printed", text=after_text)])})
    run = _run(base, after)
    assert len(run["street_ln_changes"]) == 1
    assert ("G7b" in run["guards"]) is fails


@pytest.mark.parametrize(("text", "fact", "value"), [
    ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:1 SEQ:1/2 ORIG:JANE Q SAMPLE REVOCABLE TRUST ID:99 SND BK:SAMPLE "
     "BANK ID:1", "hold_rule", "personal_trust"),
    ("ONLINE BANKING FOREIGN EXCHANGE 1234", "hold_rule", "currency_conversion"),
    ("FABRIKAM TITLE LLC DES:PAYMENT ID:1", "hold_rule", "title_firm"),
    ("WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:1 SEQ:1/2 ORIG:SAMPLE BANK NA ID:99 SND BK:SAMPLE BANK ID:1",
     "hold_rule", "bank_originated_wire"),
    ("NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", "hold_rule", None),
    # GOV (owner ruling 2026-09-30): a personal benefit (class B) and a grant or subsidy (class D).
    ("ACH DEPOSIT NYS DOL UI DD UI DD 1234567", "hold_rule", "government_benefit"),
    ("CANADA CHILD BENEFIT CANADA", "hold_rule", "government_benefit"),
    ("FSA TREAS 310 MISC PAY 1234", "hold_rule", "government_grant"),
    ("HHSSTIMULUS DES:HHSPAYMENT ID:1", "hold_rule", "government_grant"),
    ("SSA TREAS 310 DES:XXSOC SEC ID:1", "hold_rule", None),
    # GOV review: the wage subsidy, the farm-program and ESDC payments are grants; a business named like a benefit
    # names none.
    ("CANADA CEWS CANADA", "hold_rule", "government_grant"),
    ("CCC TREAS 310 MISC PAY 1234", "hold_rule", "government_grant"),
    ("GOVERNMENT ESDC 123-456 Paiement federal/Federal Pmt", "hold_rule", "government_grant"),
    ("PROV LOCAL GVT PAYMENT CANADA PRO", "hold_rule", "government_benefit"),
    ("OLD AGE SECURITY SYSTEMS LTD DES:PAYMENT ID:1", "hold_rule", None),
    ("NORTHWIND UI DD LLC DES:PAYMENT ID:1", "hold_rule", None),
    ("ANTHEM ROOFING DES:PAYMENT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD", "short_healthcare_alias", True),
    ("WPS DES:PAYMENT ID:1 INDN:CONTOSO BAKERY LLC CO ID:1 CCD", "short_healthcare_alias", False),
])
def test_the_pass_records_the_readings_the_demotion_causes_key_on(text, fact, value):
    # Final review I7: the snapshot's facts name the rule that fires (true_revenue.guard_facts, read with the
    # checkout's own code).
    from analysis.schema import Statement, Transaction
    from analysis.transaction_classifier import classify_statement_transactions, revenue_text
    from analysis.true_revenue import guard_facts

    [record] = classify_statement_transactions(Statement(account_name="CONTOSO BAKERY LLC", transactions=[
        Transaction(date="2054-03-02", description=text, amount=5000.0, direction="credit")]))
    assert guard_facts(record, revenue_text(record.normalized_description))[fact] == value


def test_the_guards_read_an_account_only_the_later_run_holds_and_a_vanished_error_skip():
    # Final review M11: the row and account guards also read an account the base does not hold, and an error skip
    # the base recorded and the later run lost fails G9.
    bad = _credit(0, 5000, "verified_revenue", "direction_conflict", tier="verified", financing_root=True,
                  gate="closed")
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "unverified_deposit", "x")])}, skipped={"ValueError": 1})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="p2p")]), "b": _account([bad])})
    run = _run(base, after)
    assert {"G2", "G6", "G10", "G9"} <= set(run["guards"])
    assert run["accounts_only_after"] == 1
    assert any(item.get("skipped") == "ValueError" for item in run["guards"]["G9"]["sample"])
    same = _snap("5.6", {"a": after["accounts"]["a"]}, skipped={"ValueError": 1})
    assert "G9" not in _run(base, same)["guards"]


# B1 (audit I60): among the analyses of one statement (one fingerprint), the census keeps the newest, records each
# account's analysis stage and parser route, and lists an older analysis whose parse differs as a stale parse.
STALE_ROWS = [(5, "OTHER CREDIT", 4200.0), (9, "CARD PURCHASE FABRICATED SUPPLY", -300.0)]
ROUTE = "fabricated-bank-deterministic"


@pytest.fixture
def restated_cache(tmp_path):
    """Three analyses of one fabricated statement, and one of another. The oldest has the lowest input sha and prints
    the parser's section label ('Other Credit'); the newest prints the described rows; a middle one reads the newest's
    rows exactly. The other statement has a single analysis."""
    cache = _FabricatedCache(tmp_path / "webapp_data")
    cache.analysis("1" * 64, [_statement("XXXX1234", STALE_ROWS)], "2031-03-03T00:00:00", "STAGEOLD0001", ROUTE)
    cache.analysis("E" * 64, [_statement("XXXX1234")], "2031-03-09T00:00:00", "STAGENEW0002", ROUTE)
    cache.analysis("7" * 64, [_statement("XXXX1234")], "2031-03-05T00:00:00", "STAGEOLD0001", ROUTE)
    cache.analysis("2" * 64, [_statement("XXXX5678")], "2031-03-04T00:00:00", "STAGEOLD0001", ROUTE)
    cache.connection.close()
    return cache.root


def test_the_input_basis_keeps_each_statement_s_newest_analysis_and_lists_an_older_parse_as_stale(restated_cache):
    stats: dict = {}
    accounts = list(census.cached_accounts(restated_cache, stats=stats))
    # The input basis reads the newest analyses first.
    assert [key for key, _ in accounts] == [f"c{'E' * 12}.0", f"c{'7' * 12}.0", f"c{'2' * 12}.0", f"c{'1' * 12}.0"]
    snap = census.snapshot(iter(accounts), basis_stats=stats)
    newest, single = f"c{'E' * 12}.0", f"c{'2' * 12}.0"
    assert set(snap["accounts"]) == {newest, single}
    assert [credit["text"] for credit in snap["accounts"][newest]["credits"]] == ["ACH CREDIT NORTHWIND CUSTOMER PAYMENT"]
    # The oldest parse (the section label) is stale; the middle one reads the kept rows exactly, a plain duplicate.
    assert snap["skipped"]["duplicate"] == 2
    assert snap["duplicates"] == {f"c{'7' * 12}.0": newest, f"c{'1' * 12}.0": newest}
    [stale] = snap["stale_parses"]
    assert (stale["account"], stale["kept"], stale["rows_differing"], stale["credit_rows_differing"]) == (
        f"c{'1' * 12}.0", newest, 1, 1)
    assert (stale["analysis_stage"], stale["kept_analysis_stage"]) == ("STAGEOLD00", "STAGENEW00")
    assert (stale["parser_route"], stale["kept_parser_route"]) == (ROUTE, ROUTE)
    # Each account records its analysis stage, when it was analysed and the parser route that published it; the
    # stages are ranked by their first analysis.
    kept = snap["accounts"][newest]
    assert (kept["analysis_stage"], kept["analysis_created"], kept["parser_route"]) == (
        "STAGENEW00", "2031-03-09T00:00:00", ROUTE)
    assert snap["accounts"][single]["analysis_stage"] == "STAGEOLD00"
    stages = snap["basis_stats"]["analysis_stages"]
    assert {stage: (row["generation"], row["analyses"], row["first_created"]) for stage, row in stages.items()} == {
        "STAGEOLD00": (1, 3, "2031-03-03"), "STAGENEW00": (2, 1, "2031-03-09")}
    assert not any(row["current"] for row in stages.values())


def test_a_statement_with_a_single_analysis_keeps_its_id_and_is_never_stale(restated_cache):
    snap = census.snapshot(census.cached_accounts(restated_cache))
    single = snap["accounts"][f"c{'2' * 12}.0"]
    assert [credit["text"] for credit in single["credits"]] == ["ACH CREDIT NORTHWIND CUSTOMER PAYMENT"]
    assert f"c{'2' * 12}.0" not in snap["duplicates"] and f"c{'2' * 12}.0" not in snap["duplicates"].values()
    assert all(f"c{'2' * 12}.0" not in (row["account"], row["kept"]) for row in snap["stale_parses"])


def test_the_newest_analysis_of_a_statement_wins_in_any_reading_order(restated_cache):
    accounts = list(census.cached_accounts(restated_cache))
    for order in (accounts, accounts[::-1]):
        snap = census.snapshot(iter([(key, json.loads(json.dumps(account))) for key, account in order]))
        assert set(snap["accounts"]) == {f"c{'E' * 12}.0", f"c{'2' * 12}.0"}
        assert [row["account"] for row in snap["stale_parses"]] == [f"c{'1' * 12}.0"]
        assert snap["duplicates"] == {f"c{'7' * 12}.0": f"c{'E' * 12}.0", f"c{'1' * 12}.0": f"c{'E' * 12}.0"}


def test_a_job_store_keeps_each_statement_s_newest_job(tmp_path):
    import sqlite3

    database = tmp_path / "webapp.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, document_id INTEGER, analysis_json TEXT,"
                       " created_at TEXT NOT NULL)")
    old = json.dumps({"accounts": [{"statement": _statement("XXXX1234", STALE_ROWS), "reconciliation": {"ok": True}}]})
    new = json.dumps({"accounts": [{"statement": _statement("XXXX1234"), "reconciliation": {"ok": True}}]})
    connection.executemany("INSERT INTO jobs VALUES (?, ?, ?, ?)", [
        ("job-new", None, new, "2031-03-02T00:00:00"), ("job-old", None, old, "2031-03-01T00:00:00")])
    connection.commit()
    connection.close()
    snap = census.snapshot(census.job_accounts(database))
    assert list(snap["accounts"]) == ["jjob-new.0"]
    assert [(row["account"], row["kept"]) for row in snap["stale_parses"]] == [("jjob-old.0", "jjob-new.0")]


def test_the_compare_follows_a_statement_to_the_analysis_the_later_run_keeps():
    # A base snapshot built before B1 keyed a statement by the analysis it kept then; the later run names the analysis
    # it keeps now and maps the older id to it (`duplicates`). An analysis whose parse differs is compared apart, as a
    # parse change (no rule moved its rows, so no G1, G7b or demotion cause is read on them); one whose parse is the
    # same is compared as usual.
    stale = _account([
        _credit(0, 420000, "unverified_deposit", "x", tier="counted_flagged", reason="no_payer_printed",
                text="OTHER CREDIT"),
        _credit(1, 30000, "verified_revenue", "named_payer_repeats", tier="verified", text="OTHER CREDIT"),
        _credit(2, 20000, "non_revenue", "strong_non_revenue_rule", tier="non_revenue", text="OTHER CREDIT"),
    ])
    described = _account([
        _credit(0, 420000, "verified_revenue", "named_payer_company_form", tier="verified",
                text="ACH CREDIT NORTHWIND CUSTOMER PAYMENT"),
        _credit(1, 30000, "unverified_deposit", "x", tier="excluded_pending_review", reason="transfer_no_counterparty",
                text="TRANSFER INTERNET"),
        _credit(2, 20000, "unverified_deposit", "x", tier="counted_flagged", reason="p2p",
                text="TRANSFER FROM FABRIKAM SUPPLY"),
    ])
    same = _account([_credit(0, 5000, "verified_revenue", "named_payer_repeats", tier="verified")])
    moved = _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged", reason="named_payer_one_off")])
    base = _snap("5.6", {"cOLD.0": stale, "cKEEP.0": same, "cSAME.0": same})
    after = dict(_snap("5.6", {"cNEW.0": described, "cKEEP.0": same, "cTWIN.0": moved}),
                 duplicates={"cOLD.0": "cNEW.0", "cSAME.0": "cTWIN.0"})
    run = _run(base, after)
    assert (run["accounts_unmatched"], run["accounts_only_after"]) == (0, 0)
    rekeyed = run["rekeyed"]
    assert rekeyed["accounts"] == 2 and rekeyed["reparsed"]["accounts"] == 1
    assert rekeyed["reparsed"]["tiers"] == {
        "base": {"counted_flagged": 4200.0, "verified": 300.0, "non_revenue": 200.0},
        "after": {"verified": 4200.0, "excluded_pending_review": 300.0, "counted_flagged": 200.0}}
    assert {(row["from"], row["to"], row["rows"]) for row in rekeyed["reparsed"]["move_matrix"]} == {
        ("counted_flagged|no_payer_printed", "verified|named_payer_company_form", 1),
        ("verified|named_payer_repeats", "excluded_pending_review|transfer_no_counterparty", 1),
        ("non_revenue|strong_non_revenue_rule", "counted_flagged|p2p", 1)}
    assert {"G1", "G7b", "G9"}.isdisjoint(run["guards"])
    assert run["left_non_revenue"] == {} and run["street_ln_changes"] == []
    # The same parse under another id is compared as usual: its verified row lost its verification by no rule.
    assert run["verified_demotions"] == {"undeclared": {"rows": 1, "dollars": 50.0, "statements": 1}}
    # Without the later run's map, both statements are unmatched, as before.
    assert _run(base, dict(after, duplicates={}))["accounts_unmatched"] == 2


# B1 (audit I39): the standing sweep of the non-revenue a credit's wording identifies inside True, by class; class H
# (a government payment that prints no purpose) is the owner's, reported apart and never in the overstatement.
def _swept(*rows):
    """A 5.6 snapshot of one account whose credits are (text, tier, cents), digit-masked as the census writes them."""
    states = {"verified": "verified_revenue", "non_revenue": "non_revenue"}
    return _snap("5.6", {"a": _account([
        _credit(index, cents, states.get(tier, "unverified_deposit"), "x", tier=tier,
                reason=None if tier in states else "named_payer_one_off", text=census.mask(text))
        for index, (text, tier, cents) in enumerate(rows)])})


@pytest.mark.parametrize(("text", "letter"), [
    ("OVERDRAFT PROTECTION FROM 9999999999", "A"),
    ("OD PROTECTION TRANSFER FROM CREDIT CARD", "A"),
    ("TRANSFER IN RAINY DAY", "A"),
    ("EB FROM CHECKING 1234567890 REF 12 34", "A"),
    ("NORTHWIND BAKERY LLC DES MERCURYACH ID MRCR ABCDE INDN NORTHWIND BAKERY LLC CO ID 1234567890 CCD", "B"),
    ("ORIG CO NAME CONTOSO TRADING C ORIG ID 1234567890 DESC DATE 310301 CO DESCR ACH PUSH SEC CCD TRACE 1"
     " EED 310301 IND ID IND NAME CONTOSO TRADING CO LLC TRN 1234567890TC", "B"),
    ("ORIG CO NAME CONTOSO TRADING C ORIG ID 1234567890 DESC DATE 310301 CO ENTRY DESCR LINE OF CRSEC CCD TRACE 1"
     " EED 310301 IND ID IND NAME CONTOSO TRADING CO LINE OF CREDIT PAYMENT TRN 1234567890TC", "B"),
    ("LOAN PROCEEDS SAMPLE BANK", "C"),
    ("ITEM RET NOT PAID", "D"),
    ("ERROR CORRECTION BR 1234", "D"),
    ("CASH REDEMPTION", "D"),
    ("WIRE FROM COINBASE INC REF 1234", "E"),
    ("VISA DIRECT DRAFTKINGS 1234567890", "F"),
    ("CANADA CHILD BENEFIT CANADA", "G"),
    ("ADP TAX DES ADP TAX ID ABCDE 123456VV", "G"),
    ("CONTOSO STATE MMB", "H"),
    ("12 TREAS 310 MISC PAY 1234567890", "H"),
    ("WORK COMP BOARD WSIB 1234", "H"),
])
def test_each_class_of_the_sweep_reads_its_own_wording(text, letter):
    sweep = census.sweep(_swept((text, "counted_flagged", 10000)))
    assert {name: row["rows"] for name, row in sweep["classes"].items() if row["rows"]} == {letter: 1}


@pytest.mark.parametrize("text", [
    "BITCOIN PAYMENT SALES",
    "DRAFTKINGS DES AP PAYMENT ID 1",
    "NORTHWIND BAKERY LLC DES PAYMENT ID 1 INDN CONTOSO DINER LLC CO ID 1 CCD",
    "ORIG CO NAME FABRIKAM SUPPLY ORIG ID 1 DESC DATE 1 CO ENTRY DESCR PAYMENT SEC CCD TRACE 1 EED 1 IND ID IND NAME"
    " CONTOSO DINER LLC TRN 1TC",
    # A processor's settlement or payout originated under the holder's own name is revenue, not the holder's push.
    "ORIG CO NAME CONTOSO TRADING C ORIG ID 1234567890 DESC DATE 310301 CO DESCR NET SETTLESEC CCD TRACE 1 EED 310301"
    " IND ID 1 IND NAME CONTOSO TRADING CO LLC TRN 1234567890TC",
    "NORTHWIND BAKERY LLC DES NORTHWIND BAKE ID ST-ABCDE INDN NORTHWIND BAKERY LLC CO ID 1234567890 CCD",
    "FEDWIRE CREDIT VIA SAMPLE TRUST COMPANY B O FABRIKAM INC",
    "IRS TREAS 310 DES VENDOR PAY ID 1",
    "COUNTY OF CONTOSO DES VENDOR PAY ID 1",
    "NORTHWIND OVERDRAFT SERVICES LLC DES PAYMENT ID 1",
    "ACH CREDIT NORTHWIND CUSTOMER PAYMENT",
])
def test_the_sweep_leaves_revenue_wording_alone(text):
    sweep = census.sweep(_swept((text, "counted_flagged", 10000)))
    assert not any(row["rows"] for row in sweep["classes"].values())


@pytest.mark.parametrize(("text", "own"), [
    ("NORTHWIND BAKERY LLC DES MERCURYACH ID MRCR ABCDE INDN NORTHWIND BAKERY LLC CO ID 1234567890 CCD", True),
    ("NORTHWIND BAKERY DES TRANSFER ID 1 INDN NORTHWIND BAKERY LLC CO ID 1 CCD", True),
    # The originator is the holder, but the entry is a processor's settlement or payout under the holder's name.
    ("ORIG CO NAME CONTOSO TRADING C ORIG ID 1234567890 DESC DATE 310301 CO DESCR NET SETTLESEC CCD TRACE 1 EED 310301"
     " IND ID 1 IND NAME CONTOSO TRADING CO LLC TRN 1234567890TC", False),
    ("NORTHWIND BAKERY LLC DES NORTHWIND BAKE ID ST-ABCDE INDN NORTHWIND BAKERY LLC CO ID 1234567890 CCD", False),
    # One shared first word is not the holder's name.
    ("NORTHWIND DES TRANSFER ID 1 INDN NORTHWIND BAKERY LLC CO ID 1 CCD", False),
    ("NORTHWIND BAKERY LLC DES TRANSFER ID 1 INDN CONTOSO DINER LLC CO ID 1 CCD", False),
])
def test_the_holder_s_own_push_reads_the_originator_the_receiver_and_the_entry(text, own):
    assert census._own_ach(census.mask(text)) is own


def test_the_sweep_reads_true_only_and_reports_class_h_apart():
    sweep = census.sweep(_swept(
        ("OVERDRAFT PROTECTION FROM 9999999999", "counted_flagged", 10000),
        ("ITEM RET NOT PAID", "verified", 20000),
        ("CASH REDEMPTION", "counted_flagged", 3000),
        ("CONTOSO STATE MMB", "verified", 90000),
        ("OVERDRAFT PROTECTION FROM 9999999999", "excluded_pending_review", 50000),
        ("ITEM RET NOT PAID", "non_revenue", 70000),
        ("ACH CREDIT NORTHWIND CUSTOMER PAYMENT", "counted_flagged", 400000),
    ))
    assert sweep["true_dollars"] == 5230.0
    assert sweep["overstatement"]["high"] == {"rows": 2, "dollars": 300.0, "share_of_true": round(100 * 300 / 5230, 3)}
    assert sweep["overstatement"]["all"] == {"rows": 3, "dollars": 330.0, "share_of_true": round(100 * 330 / 5230, 3)}
    assert sweep["unclear_owner"] == {"class": "H", "rows": 1, "dollars": 900.0, "verified_dollars": 900.0,
                                      "share_of_true": round(100 * 900 / 5230, 3)}
    assert (sweep["classes"]["D"]["verified_dollars"], sweep["classes"]["D"]["medium_dollars"]) == (200.0, 30.0)
    assert sweep["classes"]["A"]["shapes"] == {"OVERDRAFT PROTECTION FROM #": 100.0}


def test_the_compare_and_the_sweep_command_report_the_sweep(tmp_path, capsys):
    base, after = tmp_path / "base.json.gz", tmp_path / "after.json.gz"
    base.write_bytes(gzip.compress(json.dumps(_swept(
        ("ACH CREDIT NORTHWIND CUSTOMER PAYMENT", "counted_flagged", 10000))).encode("utf-8")))
    after.write_bytes(gzip.compress(json.dumps(_swept(
        ("ITEM RET NOT PAID", "counted_flagged", 10000))).encode("utf-8")))
    report = tmp_path / "report.json"
    census.main(["compare", "--base", str(base), "--after", str(after), "--out", str(report)])
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["base"]["non_revenue_in_true"]["overstatement"]["all"]["dollars"] == 0
    assert written["runs"][0]["summary"]["non_revenue_in_true"]["overstatement"]["all"]["dollars"] == 100.0
    assert "non-revenue in True" in capsys.readouterr().out
    swept = tmp_path / "sweep.json"
    assert census.main(["sweep", "--snapshot", str(after), "--out", str(swept)]) == 0
    assert json.loads(swept.read_text(encoding="utf-8"))["classes"]["D"]["rows"] == 1
    assert census.main(["sweep", "--snapshot", str(after), "--out", str(census.ROOT / "x-sweep.json")]) == 2


@pytest.mark.parametrize(("text", "tier", "reason", "narrowing", "fails"), [
    # Audit B2 (I20, §6.3 narrowing 8, the census's ninth): a named sender after an own-account designation leaves
    # the strong non-revenue rule only to be held (T13), never into True.
    ("ONLINE TRANSFER FROM CHK #### CONFIRMATION AB##CD##E CONTOSO SEAFOOD CORP", "excluded_pending_review",
     "transfer_account_designation", "9_named_transfer_after_designation", False),
    ("MOBILE TRANSFER FROM SAV #### CONFIRMATION ABCDEFGHI PAT SAMPLE", "excluded_pending_review", "holder_name",
     "9_named_transfer_after_designation", False),
    ("TFR FROM XXXXXX#### TRANSFER DEPOSIT CONTOSO LAWN CARE LLC", "excluded_pending_review",
     "transfer_account_designation", "9_named_transfer_after_designation", False),
    ("ONLINE TRANSFER FROM CHK #### CONFIRMATION AB##CD##E CONTOSO SEAFOOD CORP", "counted_flagged", "p2p",
     "9_named_transfer_after_designation", True),
    # The own-account forms with no name after the designation are no narrowing.
    ("ONLINE BANKING TRANSFER FROM CHK #### CONFIRMATION ##########", "excluded_pending_review",
     "transfer_account_designation", "outside_the_narrowings", True),
    ("TRANSFER FROM SHARES PAT SAMPLE", "excluded_pending_review", "transfer_account_designation",
     "outside_the_narrowings", True),
])
def test_narrowing_9_holds_a_named_transfer_after_an_own_account_designation(text, tier, reason, narrowing, fails):
    base = _snap("5.6", {"a": _account([_credit(0, 5000, "non_revenue", "strong_non_revenue_rule", text=text)])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "unidentified_posted_credit",
                                                 tier=tier, reason=reason, text=text)])})
    run = _run(base, after)
    assert list(run["left_non_revenue"]) == [narrowing]
    assert ("G1" in run["guards"]) is fails
    assert dict(census.NARROWINGS)["9_named_transfer_after_designation"] is False


@pytest.mark.parametrize(("text", "state", "method", "tier", "reason", "narrowing", "fails"), [
    # Audit B3 (I11, §6.3 narrowing 9, the census's tenth): a processor's instant payout printed as a card credit,
    # released by the pass beside the processor's own ACH activity, is counted and flagged.
    ("DEBIT CARD CREDIT STRIPE", "unverified_deposit", "processor_card_payout", "counted_flagged",
     "platform_unconfirmed", "10_processor_card_payout", False),
    ("DEBIT CARD CREDIT INTUIT", "unverified_deposit", "processor_card_payout", "counted_flagged",
     "platform_unconfirmed", "10_processor_card_payout", False),
    # Never verified.
    ("DEBIT CARD CREDIT STRIPE", "verified_revenue", "processor_card_payout", "verified", None,
     "10_processor_card_payout", True),
    # Another method counted from a card credit is still narrowing 6, which reaches True only verified.
    ("DEBIT CARD CREDIT STRIPE", "unverified_deposit", "unidentified_posted_credit", "counted_flagged",
     "named_payer_unlabelled", "6_card_credit_release", True),
    # A Cash App push released by the push words (§7.11) is held: narrowing 6, out of True.
    ("DEBIT CARD CREDIT CASH APP", "unverified_deposit", "unidentified_posted_credit", "excluded_pending_review",
     "possible_return", "6_card_credit_release", False),
])
def test_narrowing_10_counts_a_processor_s_card_payout(text, state, method, tier, reason, narrowing, fails):
    from analysis.true_revenue import PROCESSOR_CARD_PAYOUT_METHOD

    base = _snap("5.6", {"a": _account([_credit(0, 5000, "non_revenue", "reversal_cancellation_exclusion",
                                                tier="non_revenue", text=text)])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, state, method, tier=tier, reason=reason, text=text)])})
    run = _run(base, after)
    assert list(run["left_non_revenue"]) == [narrowing]
    assert ("G1" in run["guards"]) is fails
    assert dict(census.NARROWINGS)["10_processor_card_payout"] is True
    assert census.PROCESSOR_CARD_PAYOUT_METHOD == PROCESSOR_CARD_PAYOUT_METHOD


@pytest.mark.parametrize(("text", "cause"), [
    # Audit B3 (I04): step 3's 5.6 return, correction and refund spellings, read as the classifier reads them, are a
    # declared new non-revenue marker of the reversal rule.
    ("ITEM RET NOT PAID", "new_non_revenue_marker"),
    ("RET DEP ITEM ######", "new_non_revenue_marker"),
    ("ERROR CORRECTION OPOS UBER CANADA UBERTRIPTORONTO ONCA", "new_non_revenue_marker"),
    ("TRANSACTION CORRECTION", "new_non_revenue_marker"),
    ("CORRECTION UBER CANADA UBE ############", "new_non_revenue_marker"),
    ("CORRECTION############ CONTOSO", "new_non_revenue_marker"),
    ("DEBIT PURCHASE RET VISA ON ###### SAMPLEVILLE CA ##########", "new_non_revenue_marker"),
    ("DEBIT CARD CREDI CARD ENDING IN #### CONTOSO HARDWARE", "new_non_revenue_marker"),
    ("CHECKCARD #### CONTOSO HARDWARE SAMPLEVILLE MO", "new_non_revenue_marker"),
    ("## ##CHECKCARD #### CONTOSO HARDWARE", "new_non_revenue_marker"),
    ("POINT OF SALE DEPOSIT CONTOSO AUTO PARTS", "new_non_revenue_marker"),
    ("BANKING CARD PROVISIONAL CR", "new_non_revenue_marker"),
    ("SETTLEMENT ACH UNAUTHORIZED", "new_non_revenue_marker"),
    ("E TRANSFER RECLAIM############ #### ###", "new_non_revenue_marker"),
    ("REV MOBILE DEBIT PURCHASE ###### FABRIKAM", "new_non_revenue_marker"),
    ("RENV TFE DEBIT", "new_non_revenue_marker"),
    ("RETOUR MDSE ############ CONTOSO", "new_non_revenue_marker"),
    ("REMBOURSEMENT INTERAC SANS CONTACT #### FABRIKAM", "new_non_revenue_marker"),
    ("## HOUR GRACE OVERDRAFT FEE WAIVER", "new_non_revenue_marker"),
    ("WIRE OUT COURTESY REF", "new_non_revenue_marker"),
    # Not the spellings: a name that only starts like one, or a marker word printed elsewhere.
    ("RECLAIMED WOOD CONTOSO LLC DES PAYMENT ID #", "undeclared"),
    ("DEPT OF CORRECTION DES VENDOR PAY ID #", "undeclared"),
    ("CONTOSO CHECKCARD #### SUPPLY", "undeclared"),
    # Review round 1: the narrowed spellings, as the classifier reads them. Still read: a reclaim printed last, a
    # reversed purchase at a merchant with a company form, a merchandise return at a company, a returned item printed
    # as the whole row, a bare unauthorized entry.
    ("E TRANSFER RECLAIM", "new_non_revenue_marker"),
    ("REV MOBILE DEBIT PURCHASE ###### CONTOSO HARDWARE INC", "new_non_revenue_marker"),
    ("RETOUR MDSE ############ CONTOSO INC", "new_non_revenue_marker"),
    ("NOT PAID ######", "new_non_revenue_marker"),
    ("UNAUTHORIZED", "new_non_revenue_marker"),
    # Never a company's name or a memo.
    ("RECLAIM CONTOSO LLC DES PAYMENT ID # INDN NORTHWIND PLUMBING LLC CO ID # CCD", "undeclared"),
    ("REV MOBILE LLC DES PAYMENT ID # INDN NORTHWIND PLUMBING LLC CO ID # CCD", "undeclared"),
    ("RETOUR CONTOSO INC DES PAYMENT ID #", "undeclared"),
    ("ZELLE FROM PAT SAMPLE ON ## ## REF #### INVOICE NOT PAID LAST MONTH", "undeclared"),
    ("UNAUTHORIZED CONTOSO LLC DES PAYMENT ID #", "undeclared"),
])
def test_b3_the_reversal_rule_s_new_spellings_are_a_declared_new_marker(text, cause):
    later = _later("reversal_cancellation_exclusion", text, state="non_revenue")
    assert _causes([_step_11(text)], [later]) == {cause: 1}


@pytest.mark.parametrize(("text", "cause"), [
    # Audit B3 (I43): the card-rewards redemptions that joined the strong non-revenue rule.
    ("CASH REDEMPTION", "new_non_revenue_marker"),
    ("CASH REDEMPTION #######", "new_non_revenue_marker"),
    ("PNC PURCHASE PAYBACK AWARD", "new_non_revenue_marker"),
    ("POINTS REDEMPTION", "new_non_revenue_marker"),
    ("AMERICAN EXPRESS DES MR REDEEM ID ########## INDN NORTHWIND PLUMBING LLC CO ID ########## PPD",
     "new_non_revenue_marker"),
    # A payer named REDEMPTION is never one.
    ("REDEMPTION FABRIKAM CHURCH INC DES PAYMENT ID #", "undeclared"),
    ("CASH REDEMPTION CONTOSO LLC DES PAYMENT ID #", "undeclared"),
])
def test_b3_the_card_rewards_redemptions_are_a_declared_new_marker(text, cause):
    later = _later("strong_non_revenue_rule", text, state="non_revenue")
    assert _causes([_step_11(text)], [later]) == {cause: 1}


def test_b3_a_returned_deposit_s_pair_is_the_declared_reversal_pair_cause():
    # Audit B3 (I03): pass 4's returned-deposit pairs keep the pair's own method, so a verified row they take is the
    # declared reversal_pair cause (none in the corpus: a deposit is never verified).
    later = _later("matched_reversal_pair", "MOBILE DEPOSIT", state="non_revenue", rule="returned_deposit_amount_date_match")
    assert _causes([_step_11("MOBILE DEPOSIT")], [later]) == {"reversal_pair": 1}


def test_b3_the_snapshot_reads_a_released_processor_payout_with_no_guard_failure(monkeypatch):
    from analysis import true_revenue
    from analysis.schema import Statement, Transaction

    # The owner's switch (it ships off: the release moves a real statement's pinned figures).
    monkeypatch.setattr(true_revenue, "PROCESSOR_CARD_PAYOUT_RELEASE", True)
    statement = Statement(bank="Thread Bank (Relay)", account_name="NORTHWIND PLUMBING LLC", transactions=[
        Transaction(date="2054-03-02", description="Debit Card Credit: Stripe", amount=2100.0, direction="credit"),
        Transaction(date="2054-03-20", description="ACH Pull: Stripe", amount=-50.0, direction="debit"),
    ])
    snap = census.account_snapshot({"statement": statement.model_dump(mode="json")})
    [credit] = snap["credits"]
    assert (credit["method"], credit["tier"], credit["reason"]) == (
        "processor_card_payout", "counted_flagged", "platform_unconfirmed")
    assert credit["facts"]["claimed"]
    assert not any(census._row_guards(credit).values())
    base = {**snap, "credits": [{**credit, "state": "non_revenue", "method": "reversal_cancellation_exclusion",
                                 "tier": "non_revenue", "reason": None}]}
    run = _run(_snap("5.6", {"a": base}), _snap("5.6", {"a": snap}))
    assert list(run["left_non_revenue"]) == ["10_processor_card_payout"] and "G1" not in run["guards"]
