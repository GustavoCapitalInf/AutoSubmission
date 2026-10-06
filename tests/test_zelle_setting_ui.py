"""The owner's amendment of 2026-10-06 to the underwriter's Q3 (true revenue spec §10; R2-OW17): the Settings page's "Mark
Zelle Payments as True Revenue" (two labelled checkboxes driven as a radio pair, Yes by default) and the dashboard's
Zelle copy in both readings: the True card's fact, the memo, the Monthly Statements cell, the Non-Revenue note and the
ledger's Zelle chip. The whole webapp/static/app.js runs in node on the fake page (tests/webapp_js_harness.py); elements
are reached by id. Fabricated statements only (tests/zelle_setting_fixtures.py)."""
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
    return {"true": notes["True Revenue"], "non_revenue": notes["Non-Revenue"], "memo": result["memo"],
            "chipped": [text for text, chip in result["chips"] if chip]}


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
    assert no["true"] == TRUE_NOTE + "Zelle deposits excluded: $6,500.00 (3) · counted after review: $1,234.56 (1)"
    assert (", of which Zelle deposits excluded $6,500.00; Zelle deposits counted after review "
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
    return package, {"true": notes["True Revenue"], "non_revenue": notes["Non-Revenue"], "memo": result["memo"],
                     "details": result["details"]}


@needs_node
def test_the_package_copy_and_the_monthly_cells_in_both_readings(tmp_path, monkeypatch):
    analyses = {"mar": fx.case("Z1"), "apr": fx.case("Z2", month=4)}
    _package_, yes = _package_copy(analyses, tmp_path, monkeypatch, True)
    assert yes["true"] == TRUE_NOTE + "Zelle deposits in True revenue: $2,734.56 (2) · held for review: $6,500.00 (3)"
    assert yes["non_revenue"] == "Own-account transfers, funding, refunds and other known non-revenue"
    assert yes["details"] == [["Zelle in True 1,235 · held 6,500"], ["Zelle in True 1,500"]]
    _package_, no = _package_copy(analyses, tmp_path, monkeypatch, False)
    assert no["true"] == TRUE_NOTE + "Zelle deposits excluded: $9,234.56 (5)"
    assert no["non_revenue"] == NON_REVENUE
    assert no["details"] == [["Zelle excluded 7,735"], ["Zelle excluded 1,500"]]
    assert ", of which Zelle deposits excluded $9,234.56." in no["memo"]
    assert "; Zelle deposits counted as True revenue $2,734.56, held for review $6,500.00." in yes["memo"]


@needs_node
def test_the_package_names_a_confirmed_zelle_deposit_in_no(tmp_path, monkeypatch):
    analyses = {"mar": _decided(("transaction:2", "confirm", True))}
    _package_, no = _package_copy(analyses, tmp_path, monkeypatch, False)
    assert no["true"] == TRUE_NOTE + "Zelle deposits excluded: $6,500.00 (3) · counted after review: $1,234.56 (1)"
    assert no["details"] == [["Zelle excluded 6,500 · counted after review 1,235"]]


@needs_node
def test_a_package_with_a_member_analysed_before_the_setting_prints_every_part(tmp_path, monkeypatch):
    older = fx.case("Z2", month=4)
    older.pop("zelle_counted_reading")
    _package_, yes = _package_copy({"mar": fx.case("Z1"), "apr": older}, tmp_path, monkeypatch, True)
    assert yes["true"] == TRUE_NOTE + (
        "Zelle deposits in True revenue: $1,234.56 (1) · held for review: $6,500.00 (3) · non-revenue: $1,500.00 (1)"
        " · a statement analysed before the Zelle setting is shown as analysed")


@needs_node
def test_a_mixed_currency_package_prints_the_counts_only(tmp_path, monkeypatch):
    cad = fx.case("Z2", month=4, currency="CAD")
    package, yes = _package_copy({"mar": fx.case("Z1"), "apr": cad}, tmp_path, monkeypatch, True)
    assert package["totals"]["cross_currency_totals_refused"] is True
    # The refusal replaces the card's notes; the facts themselves print the counts only.
    facts = run_dashboard(f"console.log(JSON.stringify(packageRevenueFacts({json.dumps(package['totals'])}, null)));")
    assert "Zelle deposits in True revenue: 2 · held for review: 3" in facts
    assert yes["details"] == [["Zelle in True 1,235 · held 6,500"], ["Zelle in True 1,500 CAD"]]
