"""True revenue spec §14.2, §14.3 and §14.5: the revenue census (tools/revenue_census.py) on fabricated snapshots.
The census itself runs only on the local cache and on a copy of the tryout host's job store; these tests feed it
hand-built snapshots and one fabricated statement analysed by the real code."""
from __future__ import annotations

import gzip
import json

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
    base = _snap("5.4", {"a": _account([_credit(0, 5000, "non_revenue", "financing_proceeds_credit",
                                                text="DEPOSIT 12 OAK LOAN")])})
    after = _snap("5.6", {"a": _account([_credit(0, 5000, "unverified_deposit", "x", tier="counted_flagged",
                                                 reason="no_payer_printed", text="DEPOSIT 12 OAK LN")])})
    run = _run(base, after)
    assert run["street_ln_changes"][0]["base"] == "non_revenue|financing_proceeds_credit"
    assert run["guards"]["G7b"]["failures"] == 1


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

    def _put(self, stage, input_sha, artifact, created_at):
        self.count += 1
        key = f"{self.count:064X}"
        path = self.root / "artifacts" / stage / key[:2] / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps({"stage": stage, "artifact": artifact})
        path.write_text(text, encoding="utf-8")
        self.connection.execute(
            "INSERT INTO artifact_cache (stage, cache_key, input_sha256, settings_key, format_version, artifact_path,"
            " byte_size, created_at) VALUES (?, ?, ?, 'S', 1, ?, ?, ?)",
            (stage, key, input_sha, f"{stage}\\{key[:2]}\\{key}.json", len(text), created_at),
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

    def analysis(self, input_sha, statements, created_at):
        self._put("analysis", input_sha, {"analysis": {"accounts": [
            {"statement": statement, "reconciliation": {"ok": True}} for statement in statements]}}, created_at)


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
    assert stats == {"analysis_inputs": 7, "pdfs": 5, "pdfs_joined": 4, "pdfs_joined_on_newest_route": 3,
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
    assert pdf["basis_stats"]["pdfs_joined"] == 4 and per_input["basis_stats"] == {"analysis_inputs": 7}
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
