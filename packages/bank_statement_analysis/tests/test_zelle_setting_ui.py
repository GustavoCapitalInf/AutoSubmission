"""The owner's amendment of 2026-10-06 to the underwriter's Q3 (true revenue spec §10; R2-OW17): the Settings page's "Mark
Zelle Payments as True Revenue" (two labelled checkboxes driven as a radio pair, Yes by default) and the dashboard's
Zelle copy in both readings: the True card's fact, the memo, the Non-Revenue note and the ledger's Zelle chip (the
Monthly Statements cell carried a Zelle line until the owner's follow-up of 2026-10-07 took it out; its pins now say
no row carries one). The whole webapp/static/app.js runs in node on the fake page (tests/webapp_js_harness.py);
elements are reached by id. Fabricated statements only (tests/zelle_setting_fixtures.py)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from analysis import zelle_view
from tests import zelle_setting_fixtures as fx
from tests.test_webapp_studio_views import _package, _serve
from tests.test_webapp_true_revenue_ui import METRIC_ROWS, MONTHLY
from tests.webapp_js_harness import NODE, run_dashboard

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

PAIR = r"""
const yesBox = els.zelleTrueRevenueYes, noBox = els.zelleTrueRevenueNo;
const pair = () => ({yes: yesBox.checked, no: noBox.checked, yesAria: yesBox.getAttribute('aria-checked'),
  noAria: noBox.getAttribute('aria-checked'), disabled: [yesBox.disabled, noBox.disabled],
  status: els.zelleSettingStatus.textContent, state: els.zelleSettingStatus.getAttribute('data-state')});
const click = (box) => { box.checked = !box.checked; box.dispatch('change', {target: box}); };
const posts = () => REQUESTS.filter((request) => request.method === 'POST')
  .map((request) => [request.url, JSON.parse(request.body)]);
"""


def _answer(answer):
    return f"FAKE_RESPONSES['/api/settings'] = {json.dumps(answer)};\n"


def _loaded(settings, *, open_job=None):
    """The Settings page loaded with `settings` (and, first, a statement open), the request log cleared."""
    opened = ""
    if open_job is not None:
        opened = _serve(**{open_job: zelle_view.apply_zelle_view(fx.case("Z1"), counted=True)}) + (
            f"currentJobId = '{open_job}'; currentJobIds = ['{open_job}']; loadResults('{open_job}'); await settle();\n")
    return (PAIR + opened + _answer({"json": {"settings": settings}})
            + "loadSettings(); await settle(); REQUESTS.length = 0; FETCHED.length = 0;\n")


# --- the control (F1, F2) --------------------------------------------------------------------------------------------


def test_u7_the_row_names_the_choice_and_never_says_it_leaves_withholding_alone():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    row = html[html.index('id="zelleTrueRevenueRow"'):]
    row = row[:row.index('id="flagSettingsSection"')]
    text = " ".join(re.sub(r"<[^>]+>", " ", row).split())
    assert "Mark Zelle Payments as True Revenue" in text
    assert "never changes withholding" not in text
    assert "Yes (default):" in text and "nothing is reprocessed" in text and "asset sales stay out" in text
    assert 'role="radiogroup" aria-labelledby="zelleTrueRevenueTitle"' in row
    for box in ("zelleTrueRevenueYes", "zelleTrueRevenueNo"):
        found = re.search(rf'<input type="checkbox" id="{box}"([^>]*)>', row)
        assert found and 'role="radio"' in found[1] and "disabled" in found[1] and 'aria-checked="false"' in found[1]
    assert '<p class="setting-status" id="zelleSettingStatus" role="status" aria-live="polite"></p>' in row
    assert html.count('id="settingsStatus"') == 1
    assert ".choice-pair" in html[:html.index("</style>")]
    # It follows the NSF example block, inside the Analysis panel.
    assert html.index('id="nsfExampleTotal"') < html.index('id="zelleTrueRevenueRow"') < html.index(
        'id="flagSettingsSection"')


@needs_node
@pytest.mark.parametrize(("settings", "expected"), [({}, (True, False)), ({"zelle_true_revenue": False}, (False, True)),
                                                    ({"zelle_true_revenue": True}, (True, False))])
def test_u1_the_pair_starts_held_and_draws_the_saved_choice(settings, expected):
    result = run_dashboard(PAIR + _answer({"json": {"settings": settings}}) + """
loadSettings();
const loading = pair();
await settle();
console.log(JSON.stringify({loading, loaded: pair()}));
""")
    assert result["loading"]["disabled"] == [True, True]
    loaded = result["loaded"]
    assert (loaded["yes"], loaded["no"]) == expected
    assert (loaded["yesAria"], loaded["noAria"]) == tuple("true" if ticked else "false" for ticked in expected)
    assert loaded["disabled"] == [False, False]


@needs_node
def test_u1_a_failed_load_leaves_the_pair_held_unticked_and_says_why():
    result = run_dashboard(PAIR + _answer({"status": 500, "json": {"error": "fabricated"}}) + """
loadSettings(); await settle();
console.log(JSON.stringify(pair()));
""")
    assert (result["yes"], result["no"], result["disabled"]) == (False, False, [True, True])
    assert result["status"] == "Settings unavailable (500)" and result["state"] == "error"


@needs_node
def test_u2_ticking_no_saves_it_and_refreshes_what_is_open():
    result = run_dashboard(_loaded({}, open_job="s") + _answer({"json": {"settings": {"zelle_true_revenue": False}}})
                           + """
click(noBox);
const saving = pair();
await settle(); await settle();
console.log(JSON.stringify({saving, saved: pair(), posts: posts(), fetched: FETCHED.slice()}));
""")
    assert result["saving"]["disabled"] == [True, True] and result["saving"]["status"] == "Saving…"
    saved = result["saved"]
    assert (saved["yes"], saved["no"], saved["yesAria"], saved["noAria"]) == (False, True, "false", "true")
    assert saved["disabled"] == [False, False]
    assert result["posts"] == [["/api/settings", {"zelle_true_revenue": False}]]
    assert saved["status"] == "Saved: Zelle deposits are non-revenue." and saved["state"] is None
    assert "/analysis/s" in result["fetched"]


@needs_node
def test_u2_ticking_yes_says_it_counts():
    result = run_dashboard(_loaded({"zelle_true_revenue": False}) + _answer({"json": {"settings": {}}}) + """
click(yesBox); await settle(); await settle();
console.log(JSON.stringify({saved: pair(), posts: posts()}));
""")
    assert result["posts"] == [["/api/settings", {"zelle_true_revenue": True}]]
    assert (result["saved"]["yes"], result["saved"]["no"]) == (True, False)
    assert result["saved"]["status"] == "Saved: Zelle deposits count as True revenue."


@needs_node
def test_u3_unticking_the_ticked_box_re_ticks_it_and_sends_nothing():
    result = run_dashboard(_loaded({}) + """
click(yesBox); await settle();
console.log(JSON.stringify({after: pair(), posts: posts()}));
""")
    assert (result["after"]["yes"], result["after"]["no"]) == (True, False)
    assert result["posts"] == []


@needs_node
def test_u4_a_refused_save_restores_the_pair_and_says_why():
    result = run_dashboard(_loaded({}) + _answer({"status": 500, "json": {"error": "fabricated save failure"}}) + """
click(noBox); await settle(); await settle();
console.log(JSON.stringify(pair()));
""")
    assert (result["yes"], result["no"], result["disabled"]) == (True, False, [False, False])
    assert result["status"] == "fabricated save failure" and result["state"] == "error"


@needs_node
def test_u5_a_second_change_while_saving_is_ignored():
    result = run_dashboard(_loaded({}) + _answer({"json": {"settings": {"zelle_true_revenue": False}}}) + """
click(noBox);
click(yesBox);
const held = pair();
await settle(); await settle();
console.log(JSON.stringify({held, posts: posts(), saved: pair()}));
""")
    assert (result["held"]["yes"], result["held"]["no"]) == (False, True)
    assert result["posts"] == [["/api/settings", {"zelle_true_revenue": False}]]
    assert (result["saved"]["yes"], result["saved"]["no"]) == (False, True)


@needs_node
def test_u6_exactly_one_box_is_ever_ticked():
    result = run_dashboard(_loaded({}) + """
const seen = [];
const answers = [{zelle_true_revenue: false}, {zelle_true_revenue: true}, {zelle_true_revenue: false}];
for (const [box, answer] of [[noBox, answers[0]], [noBox, null], [yesBox, answers[1]], [yesBox, null], [noBox, answers[2]]]) {
  if (answer) FAKE_RESPONSES['/api/settings'] = {json: {settings: answer}};
  click(box); seen.push([yesBox.checked, noBox.checked]);
  await settle(); await settle(); seen.push([yesBox.checked, noBox.checked]);
}
console.log(JSON.stringify(seen));
""")
    assert all(state.count(True) == 1 for state in result)
    assert result[-1] == [False, True]


@needs_node
def test_u8_a_save_clears_the_other_recent_entries_tone_and_redraws_the_open_one():
    result = run_dashboard(_loaded({}, open_job="s") + _answer({"json": {"settings": {"zelle_true_revenue": False}}})
                           + """
rememberAnalysis({kind: 'statement', key: 'other', ids: ['other'], label: 'Other', meta: '', tone: 'green'});
rememberAnalysis({kind: 'package', key: 'p1,p2', ids: ['p1', 'p2'], label: 'Package', meta: '2', tone: 'amber'});
const openTone = recentAnalyses.find((item) => item.key === 's').tone;
click(noBox); await settle(); await settle();
console.log(JSON.stringify({tones: Object.fromEntries(recentAnalyses.map((item) => [item.key, item.tone])),
  openTone, fetched: FETCHED.slice(), open: openAnalysisKey}));
""")
    assert result["open"] == "s"
    assert result["tones"]["other"] == "neutral" and result["tones"]["p1,p2"] == "neutral"
    assert result["tones"]["s"] != "neutral" and "/analysis/s" in result["fetched"]


# --- the copy in both readings (F3) ----------------------------------------------------------------------------------

TRUE_NOTE = "Posted credits minus known non-revenue and the deposits held for review · "
NON_REVENUE = "Own-account transfers, funding, refunds and other known non-revenue, Zelle deposits included"
YES_FACT = "Zelle deposits in True revenue: $1,234.56 (1) · held for review: $6,500.00 (3)"
NO_FACT = "Zelle deposits excluded: $7,734.56 (4)"


def _decided(*decisions, shown=True):
    """Z1's stored payload after the reviewer's decisions (with_both_readings, as the routes write them)."""
    payload = fx.case("Z1")
    for location, decision, view in decisions:
        payload = zelle_view.with_both_readings(copy.deepcopy(payload), shown=view, decisions=[(location, decision,
                                                                                                None)])
    return payload


def _statement_copy(stored, counted):
    """The True card's notes, the Non-Revenue note, the memo and the ledger's Zelle chips of a statement served in one
    reading."""
    from tests.test_webapp_true_revenue_ui import _served

    served = _served(stored, zelle=counted)
    result = run_dashboard(METRIC_ROWS + _serve(z=served) + """
currentJobId = 'z'; currentJobIds = ['z']; loadResults('z'); await settle();
const rows = metricRows(els.metricsGrid.innerHTML);
const chips = [...els.transactionTable.innerHTML.matchAll(/<tr[^>]*>([\\s\\S]*?)<\\/tr>/g)]
  .map((m) => [(m[1].match(/<td class="tx-desc">([^<]*)<\\/td>/) || [])[1] || "",
               /<span class="chip-text">Zelle<\\/span>/.test(m[1])]);
generateSummary();
console.log(JSON.stringify({rows, chips, memo: els.summaryBox.textContent}));
""")
    notes = {row["label"]: row["note"].replace("&#39;", "'") for row in result["rows"]}
    values = {row["label"]: row["value"] for row in result["rows"]}
    return {"true": notes["True Revenue"], "non_revenue": notes["Non-Revenue"], "memo": result["memo"],
            "chipped": [text for text, chip in result["chips"] if chip], "true_value": values["True Revenue"]}


@needs_node
def test_the_statement_copy_in_both_readings():
    yes = _statement_copy(fx.case("Z1"), True)
    assert yes["true"] == TRUE_NOTE + YES_FACT
    assert yes["non_revenue"] == "Own-account transfers, funding, refunds and other known non-revenue"
    assert sorted(yes["chipped"]) == sorted([fx.PAT, fx.FABRIKAM_1, fx.FABRIKAM_2, fx.OWN])
    assert (", non-revenue $0.00 ($0.00 a month); Zelle deposits counted as True revenue $1,234.56, held for review "
            "$6,500.00.") in yes["memo"]
    no = _statement_copy(fx.case("Z1"), False)
    assert no["true"] == TRUE_NOTE + NO_FACT
    assert no["non_revenue"] == NON_REVENUE
    assert no["chipped"] == []
    assert ", of which Zelle deposits excluded $7,734.56." in no["memo"]


@needs_node
def test_the_copy_after_a_confirm_in_yes():
    stored = _decided(("transaction:2", "confirm", True))
    no = _statement_copy(stored, False)
    # The owner's request of 2026-10-11 (true revenue spec §2.2, §10.1): the part a review counted is "counted in True
    # revenue", never a verified part.
    assert no["true"] == TRUE_NOTE + "Zelle deposits excluded: $6,500.00 (3) · counted in True revenue: $1,234.56 (1)"
    assert (", of which Zelle deposits excluded $6,500.00; Zelle deposits counted in True revenue "
            "$1,234.56.") in no["memo"]
    yes = _statement_copy(stored, True)
    assert yes["true"] == TRUE_NOTE + YES_FACT


@needs_node
def test_the_copy_after_a_confirm_then_a_reject_in_yes():
    stored = _decided(("transaction:2", "confirm", True), ("transaction:2", "reject", True))
    yes = _statement_copy(stored, True)
    assert yes["true"] == TRUE_NOTE + ("Zelle deposits in True revenue: $0.00 (0) · held for review: $6,500.00 (3) · "
                                       "non-revenue: $1,234.56 (1)")
    assert ("; Zelle deposits counted as True revenue $0.00, held for review $6,500.00, "
            "non-revenue $1,234.56.") in yes["memo"]
    no = _statement_copy(stored, False)
    assert no["true"] == TRUE_NOTE + NO_FACT


@needs_node
def test_a_zelle_free_statement_keeps_today_s_non_revenue_note_in_both_modes():
    for counted in (True, False):
        copy_ = _statement_copy(fx.payload(fx.FREE), counted)
        assert copy_["non_revenue"] == NON_REVENUE and "Zelle" not in copy_["true"] and copy_["chipped"] == []


@needs_node
def test_a_statement_analysed_before_the_setting_says_so():
    stored = fx.case("Z1")
    stored.pop("zelle_counted_reading")
    yes = _statement_copy(stored, True)
    assert yes["true"] == TRUE_NOTE + NO_FACT + " · analysed before the Zelle setting: shown as analysed"
    # Audit round 3, R3-B20 (R3-19; §10.5): the memo carries the notice too.
    assert (", of which Zelle deposits excluded $7,734.56; analysed before the Zelle setting: shown as analysed. "
            "Average daily balance") in yes["memo"]


def _package_copy(analyses, tmp_path, monkeypatch, counted):
    from webapp.settings import save_settings

    save_settings(tmp_path, {"zelle_true_revenue": counted})
    package = _package(analyses, tmp_path, monkeypatch)
    result = run_dashboard(METRIC_ROWS + MONTHLY + f"""
currentJobIds = {json.dumps(list(analyses))}; renderPackageAnalysis({json.dumps(package)});
const rows = metricRows(els.metricsGrid.innerHTML);
const details = [...els.monthlyTable.innerHTML.matchAll(/<tr[^>]*>([\\s\\S]*?)<\\/tr>/g)].map((m) =>
  [...m[1].matchAll(/<div class="table-cell-detail">([^<]*)<\\/div>/g)].map((d) => d[1]).filter((d) => /Zelle/.test(d)));
generateSummary();
console.log(JSON.stringify({{rows, details, memo: els.summaryBox.textContent}}));
""")
    notes = {row["label"]: row["note"].replace("&#39;", "'") for row in result["rows"]}
    values = {row["label"]: row["value"] for row in result["rows"]}
    return package, {"true": notes["True Revenue"], "non_revenue": notes["Non-Revenue"], "memo": result["memo"],
                     "details": result["details"], "true_value": values["True Revenue"]}


@needs_node
def test_the_package_copy_and_the_monthly_cells_in_both_readings(tmp_path, monkeypatch):
    analyses = {"mar": fx.case("Z1"), "apr": fx.case("Z2", month=4)}
    _package_, yes = _package_copy(analyses, tmp_path, monkeypatch, True)
    assert yes["true"] == TRUE_NOTE + "Zelle deposits in True revenue: $2,734.56 (2) · held for review: $6,500.00 (3)"
    assert yes["non_revenue"] == "Own-account transfers, funding, refunds and other known non-revenue"
    # The owner's follow-up of 2026-10-07: no Monthly Statements row carries a Zelle line, under either choice.
    assert yes["details"] == [[], []]
    _package_, no = _package_copy(analyses, tmp_path, monkeypatch, False)
    assert no["true"] == TRUE_NOTE + "Zelle deposits excluded: $9,234.56 (5)"
    assert no["non_revenue"] == NON_REVENUE
    assert no["details"] == [[], []]
    assert ", of which Zelle deposits excluded $9,234.56." in no["memo"]
    assert "; Zelle deposits counted as True revenue $2,734.56, held for review $6,500.00." in yes["memo"]


@needs_node
def test_the_package_names_a_confirmed_zelle_deposit_in_no(tmp_path, monkeypatch):
    analyses = {"mar": _decided(("transaction:2", "confirm", True))}
    _package_, no = _package_copy(analyses, tmp_path, monkeypatch, False)
    assert no["true"] == TRUE_NOTE + "Zelle deposits excluded: $6,500.00 (3) · counted in True revenue: $1,234.56 (1)"
    assert no["details"] == [[]]  # the owner's follow-up of 2026-10-07: no Zelle line in the Monthly Statements


NOTICE = "a statement analysed before the Zelle setting is shown as analysed"


def _older(name, **kwargs):
    """A fabricated statement analysed between the Zelle policy and the setting: its policy rows, no counted reading's
    edits (served as analysed under Yes, `setting_applied` false)."""
    stored = fx.case(name, **kwargs)
    stored.pop("zelle_counted_reading")
    return stored


def _legacy(name, **kwargs):
    """A stand-in for a statement analysed before the Zelle policy (test_zelle_setting.py's Z11 legacy fixture): the
    counted reading stored, no edits (served as stored under No, counted, `setting_applied` false)."""
    from analysis.serialization import _account_payload

    report = fx.case_document(name, **kwargs).accounts[0]
    return json.loads(json.dumps(_account_payload(report.zelle_counted)))


@needs_node
def test_a_package_with_a_member_analysed_before_the_setting_prints_every_part(tmp_path, monkeypatch):
    package, yes = _package_copy({"mar": fx.case("Z1"), "apr": _older("Z2", month=4)}, tmp_path, monkeypatch, True)
    # Audit round 3, R3-B20 (R3-19; §9.2, §10.1, §10.5): the package's flag says what its members serve: one member is
    # served as analysed, its Zelle deposits out of True, so the package's Zelle deposits do not all count; the card and
    # the memo name where each part sits, and the notice.
    figures = package["totals"]["zelle_deposits"]
    assert (figures["counted_as_true_revenue"], figures["setting"], figures["setting_applied"]) == (False, True, False)
    assert yes["true"] == TRUE_NOTE + (
        "Zelle deposits excluded: $1,500.00 (1) · counted in True revenue: $1,234.56 (1) · held for review: $6,500.00 (3)"
        f" · {NOTICE}")
    assert yes["non_revenue"] == NON_REVENUE
    assert (", of which Zelle deposits excluded $1,500.00; Zelle deposits counted in True revenue $1,234.56, held for "
            f"review $6,500.00; {NOTICE}.") in yes["memo"]
    assert "counted as True revenue" not in yes["memo"]


@needs_node
def test_r3_19_a_package_of_members_analysed_before_the_setting_under_yes(tmp_path, monkeypatch):
    """Audit round 3, R3-B20 (R3-19): under Yes, every member served as analysed: the package's Zelle deposits are
    excluded, as each member serves them; the Non-Revenue note keeps them; the memo never says $0.00 counted."""
    from webapp.package_export import _package_rows

    analyses = {"mar": _older("Z1"), "apr": _older("Z2", month=4)}
    package, yes = _package_copy(analyses, tmp_path, monkeypatch, True)
    figures = package["totals"]["zelle_deposits"]
    assert (figures["counted_as_true_revenue"], figures["setting"], figures["setting_applied"]) == (False, True, False)
    assert figures["by_tier"] == {"non_revenue": {"count": 5, "total": 9234.56}}
    assert yes["non_revenue"] == NON_REVENUE
    assert yes["true"] == TRUE_NOTE + f"Zelle deposits excluded: $9,234.56 (5) · {NOTICE}"
    assert f", of which Zelle deposits excluded $9,234.56; {NOTICE}." in yes["memo"]
    assert "counted as True revenue $0.00" not in yes["memo"]
    # The download names the setting the package was served under, beside the members' reading.
    assert ("revenue_tier", "zelle_deposits.setting", "Yes") in _package_rows(package)


@needs_node
def test_r3_19_a_package_of_legacy_members_under_no(tmp_path, monkeypatch):
    """Audit round 3, R3-B20 (R3-19): under No, every member analysed before the Zelle policy (its Zelle counted, served
    as stored): the package's Zelle deposits count, as its members serve them; the Non-Revenue note drops them; the memo
    says where they sit, with the notice; the download's setting reads No."""
    from webapp.package_export import _package_rows

    analyses = {"mar": _legacy("Z1"), "apr": _legacy("Z2", month=4)}
    package, no = _package_copy(analyses, tmp_path, monkeypatch, False)
    figures = package["totals"]["zelle_deposits"]
    assert (figures["counted_as_true_revenue"], figures["setting"], figures["setting_applied"]) == (True, False, False)
    assert no["non_revenue"] == "Own-account transfers, funding, refunds and other known non-revenue"
    assert no["true"] == TRUE_NOTE + (
        f"Zelle deposits in True revenue: $2,734.56 (2) · held for review: $6,500.00 (3) · {NOTICE}")
    assert (f"; Zelle deposits counted as True revenue $2,734.56, held for review $6,500.00; {NOTICE}.") in no["memo"]
    assert "of which Zelle deposits excluded" not in no["memo"]
    rows = _package_rows(package)
    assert ("revenue_tier", "zelle_deposits.setting", "No") in rows
    assert ("revenue_tier", "zelle_deposits.setting_applied", False) in rows


@needs_node
def test_r3_19_a_mixed_package_under_no_names_the_legacy_member_s_parts(tmp_path, monkeypatch):
    """Audit round 3, R3-B20 (R3-19): under No, a fresh member (its Zelle excluded, no figures served) beside a legacy
    one (its Zelle counted): the package's Zelle deposits do not all count; the memo names the excluded and counted
    parts and the notice."""
    analyses = {"mar": fx.case("Z1"), "apr": _legacy("Z2", month=4)}
    package, no = _package_copy(analyses, tmp_path, monkeypatch, False)
    figures = package["totals"]["zelle_deposits"]
    assert (figures["counted_as_true_revenue"], figures["setting"], figures["setting_applied"]) == (False, False, False)
    assert no["true"] == TRUE_NOTE + (
        f"Zelle deposits excluded: $7,734.56 (4) · counted in True revenue: $1,500.00 (1) · {NOTICE}")
    assert no["non_revenue"] == NON_REVENUE
    assert (f", of which Zelle deposits excluded $7,734.56; Zelle deposits counted in True revenue $1,500.00; "
            f"{NOTICE}.") in no["memo"]


@needs_node
def test_a_mixed_currency_package_prints_the_counts_only(tmp_path, monkeypatch):
    cad = fx.case("Z2", month=4, currency="CAD")
    package, yes = _package_copy({"mar": fx.case("Z1"), "apr": cad}, tmp_path, monkeypatch, True)
    assert package["totals"]["cross_currency_totals_refused"] is True
    # The refusal replaces the card's notes; the facts themselves print the counts only.
    facts = run_dashboard(f"console.log(JSON.stringify(packageRevenueFacts({json.dumps(package['totals'])}, null)));")
    assert "Zelle deposits in True revenue: 2 · held for review: 3" in facts
    # The owner's follow-up of 2026-10-07: no Monthly Statements row carries a Zelle line (R2-B16's units stay on the
    # rows' own cells).
    assert yes["details"] == [[], []]


# --- Audit round 3, R3-B20 (R3-48; spec §10.1, §10.4's I51, §10.5): where the revenue is not established, the Zelle
# figures say what the captured rows say (the count and total, the non-revenue part) and no part of True or Held.


def _unestablished(name="Z1", **kwargs):
    """A fabricated statement whose captured credits are not the money its Total counts (the shape the webapp tests
    use: a summary Total above the captured credits)."""
    stored = fx.case(name, **kwargs)
    stored["metrics"]["deposits_source"] = "summary"
    stored["metrics"]["effective_total_deposits"] = 99999.0
    return stored


@needs_node
def test_an_unestablished_statement_names_its_captured_zelle_rows_only():
    yes = _statement_copy(_unestablished(), True)
    assert yes["true_value"] == "N/A"
    assert yes["true"] == TRUE_NOTE + "Zelle deposits captured: $7,734.56 (4), captured rows only"
    assert "True revenue N/A, non-revenue " in yes["memo"]
    assert ("captured rows only); Zelle deposits captured $7,734.56 (captured rows only).") in yes["memo"]
    assert "counted as True revenue" not in yes["memo"] and "held for review" not in yes["memo"]
    # The established statement reads as before (test_the_statement_copy_in_both_readings).
    assert _statement_copy(fx.case("Z1"), True)["true"] == TRUE_NOTE + YES_FACT


@needs_node
def test_an_unestablished_statement_keeps_its_zelle_non_revenue_part():
    yes = _statement_copy(_unestablished("Z4_TRUCK"), True)
    assert yes["true"] == TRUE_NOTE + ("Zelle deposits captured: $9,000.00 (1), captured rows only · non-revenue: "
                                       "$9,000.00 (1)")
    assert "; Zelle deposits captured $9,000.00 (captured rows only), non-revenue $9,000.00." in yes["memo"]


@needs_node
def test_a_package_with_an_unestablished_member_names_its_captured_zelle_rows_only(tmp_path, monkeypatch):
    analyses = {"mar": fx.case("Z1"), "apr": _unestablished("Z2", month=4)}
    package, yes = _package_copy(analyses, tmp_path, monkeypatch, True)
    assert package["totals"]["true_revenue_total"] is None and yes["true_value"] == "N/A"
    assert yes["true"] == TRUE_NOTE + "Zelle deposits captured: $9,234.56 (5), captured rows only"
    assert "; Zelle deposits captured $9,234.56 (captured rows only)." in yes["memo"]
    assert "counted as True revenue" not in yes["memo"]
    # The unestablished member's Monthly cell names no firm Zelle figure in True (its parts are None). Audit round 3,
    # R3-MERGE: since the owner's follow-up of 2026-10-07 (the hosting line) no Monthly Statements row carries a Zelle
    # line at all, so neither member's cell names a Zelle figure (it read "Zelle in True N/A" on this one).
    assert yes["details"] == [[], []]


# --- Audit round 3, R3-B20 (R3-51; spec §10.6, §10.7): under No, an excluded Zelle deposit names the reading the rules
# give it with Zelle counted (its `zelle_prior` signal), and says a confirm releases a hold in both settings. Display
# only: the one-click Confirm Revenue and the both-readings write are unchanged (the owner-decision default, option a).

EXCLUDED = ("Zelle deposit (excluded by policy). A Zelle deposit, excluded from true revenue by policy; confirm it if "
            "this business takes customer payments by Zelle.")
RELEASES = " Confirm Revenue releases it in both settings."
#: A payer the business also pays by Zelle (the R3-51 probes' shape; fabricated).
PAYS_BOTH_IN = "ZELLE PAYMENT FROM NORTHWIND TRADING LLC CONF# Q1W2E3R4T"
PAYS_BOTH = [(fx.SALE, 10000.00, 2), (PAYS_BOTH_IN, 1750.25, 8),
             ("ZELLE PAYMENT TO NORTHWIND TRADING LLC CONF# Q1W2E3R4Y", -600.00, 12), (fx.KAPITUS, -850.00, 9)]
#: The rules' hold, as the No row says it.
HOLDS = " With Zelle counted (Yes), the rules hold it for review: "
REVIEW = r"""
const actions = (html) => [...html.matchAll(/data-revenue-review-action="([a-z]+)"/g)].map((m) => m[1]);
const review = (rows) => rows.map((tx) => ({description: tx.description, reason: revenueReviewReason(tx),
  tag: transactionCategory(tx).label, controls: actions(revenueReviewControls(tx, "job1", null))}));
"""


def _reviewed(stored, counted):
    """Each posted credit's reason line, ledger tag and review controls, as the dashboard draws the served rows."""
    from tests.test_webapp_true_revenue_ui import _served

    rows = [tx for tx in _served(stored, zelle=counted)["statement"]["transactions"] if tx["amount"] > 0]
    return {entry["description"]: entry for entry in run_dashboard(
        REVIEW + f"console.log(JSON.stringify(review({json.dumps(rows)})));")}


@needs_node
def test_r3_51_under_no_an_excluded_zelle_deposit_names_the_rules_reading():
    no = _reviewed(fx.case("Z1"), False)
    held = HOLDS
    assert no[fx.OWN]["reason"] == EXCLUDED + held + "From the holder's own name or brand." + RELEASES
    assert no[fx.FABRIKAM_1]["reason"] == no[fx.FABRIKAM_2]["reason"] == (
        EXCLUDED + held + "Repeated round sums from one sender." + RELEASES)
    # The owner's request of 2026-10-11 (§2.2, §10.6): a reading in True revenue says so, never its counted reason.
    assert no[fx.PAT]["reason"] == EXCLUDED + " With Zelle counted (Yes), it counts in True revenue."
    # The control is still Confirm Revenue only (the owner-decision default).
    assert all(no[text]["controls"] == ["confirm"] for text in (fx.OWN, fx.FABRIKAM_1, fx.FABRIKAM_2, fx.PAT))
    # A row no Zelle rule reads is as before: counted in True revenue, it carries no reason line (since the owner's
    # request of 2026-10-11).
    assert no[fx.VENMO]["reason"] == "" and no[fx.VENMO]["tag"] == "True revenue"
    also = _reviewed(fx.payload(PAYS_BOTH), False)[PAYS_BOTH_IN]
    assert also["reason"] == EXCLUDED + held + "Payer also debited this account." + RELEASES
    assert also["controls"] == ["confirm"]


@needs_node
def test_r3_51_the_yes_rows_read_as_before():
    yes = _reviewed(fx.case("Z1"), True)
    assert yes[fx.OWN]["reason"] == (
        "From the holder's own name or brand. The credit comes from the account holder's own name or brand.")
    assert yes[fx.OWN]["tag"] == "Held: From the holder's own name or brand"
    assert yes[fx.FABRIKAM_1]["tag"] == "Held: Repeated round sums from one sender"
    assert yes[fx.PAT]["reason"] == "" and yes[fx.PAT]["tag"] == "True revenue"
    assert yes[fx.OWN]["controls"] == ["confirm", "reject"]


@needs_node
def test_r3_51_rows_without_a_prior_and_the_prior_s_other_shapes():
    from tests.test_webapp_true_revenue_ui import _record

    rows = [
        _record("non_revenue", reason="government_no_purpose"),
        _record("non_revenue", reason="zelle_excluded", signals=("zelle_deposit_excluded",)),
        _record("non_revenue", reason="zelle_excluded",
                signals=("zelle_deposit_excluded", "zelle_prior:excluded_pending_review:fabricated_code")),
        _record("non_revenue", reason="zelle_excluded", signals=("zelle_deposit_excluded", "zelle_prior:verified:")),
        _record("non_revenue", reason="zelle_excluded",
                signals=("zelle_deposit_excluded", "zelle_prior:counted_flagged:check_deposit")),
    ]
    result = run_dashboard(REVIEW + f"""
const entry = (code) => `${{REVENUE_TIER_REASONS[code][1]}}. ${{REVENUE_TIER_REASONS[code][2]}}`;
console.log(JSON.stringify({{reasons: review({json.dumps(rows)}).map((row) => row.reason),
  government: entry("government_no_purpose"),
  priors: {json.dumps(rows)}.map((tx) => zellePriorReading(tx.classification))}}));
""")
    reasons = result["reasons"]
    assert reasons[0] == result["government"]
    assert reasons[1] == EXCLUDED
    assert reasons[2] == EXCLUDED + HOLDS + "fabricated_code." + RELEASES
    assert reasons[3] == EXCLUDED + " With Zelle counted (Yes), it counts in True revenue."
    assert reasons[4] == EXCLUDED + " With Zelle counted (Yes), it counts in True revenue."
    assert result["priors"] == [None, None, {"tier": "excluded_pending_review", "reason": "fabricated_code"},
                                {"tier": "verified", "reason": None},
                                {"tier": "counted_flagged", "reason": "check_deposit"}]


def test_r3_51_the_prior_reader_mirrors_the_analysis():
    """zellePriorReading reads the signal analysis/true_revenue/zelle.py zelle_prior_reading reads: its prefix, and the tier
    and reason split at the first colon."""
    from analysis.true_revenue.zelle import _ZELLE_PRIOR

    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert f'const ZELLE_PRIOR_SIGNAL = "{_ZELLE_PRIOR}";' in source


@needs_node
def test_r3_51_the_statement_ledger_shows_the_rules_reading_under_no():
    from tests.test_webapp_true_revenue_ui import _served

    result = run_dashboard(_serve(z=_served(fx.case("Z1"), zelle=False)) + """
currentJobId = 'z'; currentJobIds = ['z']; loadResults('z'); await settle();
console.log(JSON.stringify([...els.transactionTable.innerHTML.matchAll(/<strong>Reason:<\\/strong> ([^<]*)<\\/div>/g)]
  .map((m) => m[1].replace(/&#39;/g, "'"))));
""")
    assert EXCLUDED + HOLDS + "From the holder's own name or brand." + RELEASES in result


@needs_node
def test_r3_51_the_package_ledger_shows_the_rules_reading_under_no(tmp_path, monkeypatch):
    from webapp.settings import save_settings

    save_settings(tmp_path, {"zelle_true_revenue": False})
    package = _package({"mar": fx.case("Z1")}, tmp_path, monkeypatch)
    result = run_dashboard(f"""
currentJobIds = ['mar']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify([...els.transactionTable.innerHTML.matchAll(/<strong>Reason:<\\/strong> ([^<]*)<\\/div>/g)]
  .map((m) => m[1].replace(/&#39;/g, "'"))));
""")
    assert EXCLUDED + HOLDS + "Repeated round sums from one sender." + RELEASES in result
