# S4 Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The dashboard shows the eleven flag groups (C1) that the analysis now publishes and the server filters by Settings. That means:
- a Settings section with one switch per group;
- a Flagged positions panel on the results page, the package page and the statement window;
- a tag for each new classification state, and a Flagged chip on rows the server marks `flag_shown`. A premium-financing row keeps its Insurance tag and also carries the chip;
- a Flagged ledger filter;
- a notice on a statement analysed with older lender rules.

It adds no lender math, and it changes no decision.

**Architecture:**
- Everything is presentation of what the server serves.
- The server applies the Settings switches on a copy of the analysis (S3, contract C6). The dashboard therefore keeps no copy of the settings. It renders what the server serves:
  - `detection.flagged_positions` (C5);
  - `pkg.flagged_positions` (C6);
  - the row fields `flagged_group`, `contributes_to_flagged_totals` and `flag_shown`;
  - the top-level `analysis_rules_outdated`.
- The labels live in one constant, `FLAG_GROUP_LABELS`, which a test holds equal to `analysis/flag_groups.py`.
- The Settings switches reuse the NSF switch pattern: GET/POST `/api/settings`, then `refreshShownResults()`. They are rendered into a container and saved through one delegated `change` listener.

**Tech Stack:**
- Vanilla JS: `webapp/static/app.js`.
- HTML and inline CSS: `webapp/templates/index.html`.
- pytest 9 on `C:\Python314\python.exe`.
- node on PATH, which runs the whole app.js on a fake page through `tests/webapp_js_harness.py`.

**Spec:** `docs/superpowers/specs/2026-09-24-lender-detection-design.md`, §8.5. This plan does not cover the behaviour of the Re-analyze button; that is S5's. **Master plan and contract:** `docs/superpowers/plans/2026-09-24-lender-detection.md` (C1, C5, C6, C7, C8).

## Global Constraints

Copied verbatim from the master plan:

- Only MCA/revenue-based funders and equipment financing are lenders (`confirmed_lender`). Nothing else enters `lender_*`, `withholding_*`, `eligible_deposits` (except the D1 proceeds exclusion) or the package `decision`.
- Every flag group has a Settings key, default `True`, applied at serving time. Unticking hides only (D7).
- Counterparty names and aliases live **only** in `analysis/classification_registry.py`. The guard is `tests/test_no_statement_hardcodes.py:85-87`, and there is no second exempt module.
- **Privacy:**
  - Tests use fabricated descriptors only.
  - Never commit statement text, amounts, account numbers, dates or customer names.
  - Commit messages quote no statement values.
  - Re-pinned regression expectations use derived totals only.
- `CLASSIFICATION_VERSION = "5.0"` and `ANALYSIS_STAGE_VERSION = 19` land in the same commit as the classifier change (S2).
- Run tests with `C:\Python314\python.exe -m pytest tests/<files> -q -p no:cacheprovider`. **Always pass paths under `tests/`**: a bare `pytest` also collects `discovery_reports/`.
- Known failure that predates this work, and must not be attributed to it: `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`.
- Write or patch Python with the Write/Edit tools, not with Bash heredocs (the Bash tool mangles backslashes here). Restart Flask after template edits.
- Subagents: Opus 5.5 only, never Fable. Each service runs on its own branch, and only the orchestrator merges.
- No payee or brand literals in `webapp/static/app.js` (`tests/test_revenue_classification.py:812-844`, `tests/test_lender_insurance_classification.py:566-584`). Every `formatMoney(` call passes an explicit currency (`tests/test_package_currency.py:773-796`).

Specific to S4:

- **Branch.** Work on `ld-s4-dashboard`, cut from `lender-detection`. Touch only three files:
  - `webapp/static/app.js`
  - `webapp/templates/index.html`
  - `tests/test_webapp_flagged_dashboard.py` (new)
- **Order of work.**
  - Tasks 1-10 and 12 need nothing from S1, S2 or S3. They test against fabricated payloads that follow C5/C6.
  - Task 11 needs S1 merged into `lender-detection`: C1's `analysis/flag_groups.py` exists.
  - From S1, S4 consumes C1 only. It reads no alias table (C2), no matcher (C3), and nothing of the curated registry ledger (C10): not `docs/lender-registry-ledger.json`, not S1's builder or its `--check` validator, and no research input. app.js carries no payee name, and every S4 test uses fabricated names.
  - Task 13 needs S2 and S3 merged.
  - Before Task 11 and again before Task 13, rebase onto `lender-detection`, then re-run everything (Task 14).
- **Split with S5.**
  - S4 owns the notice markup (`#rulesOutdatedNotice` holding `#reanalyzeButton`) and its show/hide.
  - S5 binds the click through `document.getElementById("reanalyzeButton")`: the `app.js` bullets of the S5 plan's Global Constraints state the split, and its listener is the top-level `document.getElementById("reanalyzeButton")?.addEventListener("click", () => { reanalyzeShownStatement(); });` of its Re-analyze button task. Neither plan adds `els.reanalyzeButton`, and S4 adds no listener on the button.
  - Cross-plan references in this plan name a contract (C1-C10), a function, a test or a task title, never another plan's line or task number: the other plans are revised in parallel, so their numbers move.
- **Eleven groups (the owner's amendment of 2026-09-24).** C1 holds eleven groups: ten classification states plus premium financing.
  - Floor plan (`floor_plan_financing` → `floor_plan`) and Factoring (`factoring` → `factoring`) are states of their own. Each gets a tag (Task 1), a label (Task 3) and a switch (Task 7), and both sit in the package fixture (Task 5).
  - Premium financing (`premium_financing`, setting `flag_premium_financing`) has **no state of its own**. Its rows keep `classification="insurance"` and `contributes_to_insurance_totals` (C4). So they keep the Insurance tag (`entity || "Insurance"`), the Insurance filter pill and their place in the insurance-provider table. They are flagged only through `flagged_group`.
  - Therefore every flagged chip, filter and payee match in this plan keys on `flag_shown`, `flagged_group` and `contributes_to_flagged_totals`, never on the classification state. Tasks 2, 4 and 5 test it on insurance rows of fabricated payloads (statement and package), and Task 13 on a statement served by S2 and S3.
  - Spec §8.1 still says "eight `flag_*` keys". C1 and C7 govern: every key in `FLAG_SETTING_KEYS`, which is eleven.
- **Flagged groups never feed** the dashboard's decisions:
  - `accountDecision`, `hasMaterialPotentialLenderDebits`, `generateSummary` and the decision pill are not touched (D7);
  - the lender table is not touched.
- **Static JS/HTML guards that must stay green.** They were verified against a scratch copy with every edit in this plan applied: 75 passed. See §Self-Review.
  - `tests/test_lender_insurance_classification.py:566-584`:
    - `<th>Potential Withholding</th>` appears exactly twice in index.html;
    - no `<th>Eligible Deposits</th>` and no `<th>Exposure</th>`;
    - the required JS strings stay;
    - the `insurance` filter pills stay.
  - `tests/test_revenue_classification.py:812-844`: no payee literals, and no "Potential Revenue", "Maximum Revenue" or "Credit Count".
  - `tests/test_package_currency.py:751-796`: every `formatMoney(` call has at least 2 arguments, and no literal `"USD"` goes to a package render.
  - `tests/test_adb.py:1218-1254`:
    - add no `metrics.min_balance`, `metrics.max_balance`, `"Average Daily Balance"` or `daily_balances`;
    - the counts are pinned at 2, 1 and 5 respectively.
  - `tests/test_webapp_confidence_label.py:51-86`:
    - no `NAME = <60-99>;` and no `return <60-99>;` literal in app.js;
    - no 60-99 number within 160 characters of the word "confidence" in app.js or index.html.

    This plan never writes the word "confidence".
  - `tests/test_webapp_confidence_label.py:222-232`: the `renderAccount` body keeps exactly one `validationLabel(report)`, plus `["Validation", validation]` and the `setBanner("done", "Extraction completed", validation)` call.
  - `tests/test_webapp_accounts_view.py:15-25, 197-243`:
    - It runs the block from `function isDocumentPayload(` to `function renderAnalysis(` with `els = {accountsPanel}` only, and it extracts `renderAnalysis` and calls it.
    - So the new helper `renderAnalysis` calls, `syncRulesOutdatedNotice`, sits **inside** that block and reads `els.rulesOutdatedNotice` null-safe. `renderUnverifiedMain`, which Task 10 also makes call it, is in the same block (app.js:1907).
  - Tests that extract functions by name, up to the next `"\nfunction "` or `"\n}\n"`:
    - `tests/test_visual_pair_ui.py:14-19, 78-80` (including `setActions` and `loadResults`);
    - `tests/test_source_contradiction.py:133-146`;
    - `tests/test_webapp_security.py:520-530` (`uploadFiles`).

    None of these functions is edited, and no top-level code is placed right after one of them. Every new top-level helper is a `function` declaration.
  - `tests/test_webapp_studio_views.py:534-544`: the Settings slice keeps `id="allAccountsToggle"` and `Statements</h2>`, and the page keeps `.results-content.is-withheld`.
  - `tests/test_webapp_studio_views.py:267-279`: a settings change re-fetches what is open through `refreshShownResults()`.
- **Existing pins that must flip:**
  - None. No existing test pins what S4 changes. The settings-dict pins in `tests/test_webapp_settings.py:31, 41-42, 57, 59-61, 129-130, 176` belong to S3 (C7).
  - Evidence: the full guard selection below passes against the scratch copy of the edited files.
- **Line numbers.** They are those of `lender-detection` at `4f219cd`, where app.js and index.html are unchanged since `31f86b7`. `4f219cd` and its parent `9d91e7b` change only the spec. Earlier tasks shift them, so every Edit below is anchored on quoted text, which is unique unless the step says `replace_all`.
- **Commits.** Each commit step gives the exact `git add` paths and the subject line. Every message then ends with the two attribution lines, added as a second `-m`:

  ```
  git commit -m "<the step's subject line>" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
  Claude-Session: <the session URL>"
  ```

  - The `Co-Authored-By` line is fixed for an Opus 5.5 (1M context) cell.
  - The `Claude-Session` URL belongs to the session that commits. Take it from that session's system reminder, which is the only place it exists.
  - If the system reminder gives different lines, use its lines.
  - Messages never quote statement values.
- **DASHBOARD GUARDS**, the command the tasks refer to:

```
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py tests/test_webapp_studio_views.py tests/test_webapp_review_ui.py tests/test_webapp_accounts_view.py tests/test_webapp_confidence_label.py tests/test_visual_pair_ui.py tests/test_lender_insurance_classification.py::test_browser_consumes_classification_records_without_keyword_scans tests/test_revenue_classification.py::test_revenue_ui_uses_authoritative_fields_and_exposes_review_controls tests/test_package_currency.py::test_dashboard_no_longer_hardcodes_usd_for_the_package_view tests/test_package_currency.py::test_no_package_money_is_rendered_with_the_usd_default tests/test_adb.py::test_existing_dashboard_field_binds_directly_to_authoritative_api_adb tests/test_adb.py::test_dashboard_balance_cards_bind_to_backend_fields_without_recalculation tests/test_adb.py::test_dashboard_has_no_adb_audit_components_or_duplicate_visible_fields tests/test_source_contradiction.py::test_the_dashboard_shows_the_contradiction_as_the_statements_failure tests/test_webapp_security.py::test_upload_failures_surface_the_server_message_not_just_a_status_code tests/test_new_statement_corpus.py::test_dashboard_uses_backend_adb_without_frontend_recalculation -q -p no:cacheprovider
```

At the base, the selection without the new file gives: **75 passed**.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `webapp/static/app.js` | Modify | Holds all dashboard behaviour:<br>- `FLAG_GROUP_LABELS` and `CADENCE_LABELS`, read through `ownKey`<br>- tags for the new states (card payments name their issuer), and the Flagged chip<br>- the `flagged` and `flagged:<group>` ledger filters<br>- `renderFlaggedPositions` and its helpers, drawn on the results page, the package page and the statement window<br>- the Settings switches (`renderFlagSettings`, the delegated save, the filter reset)<br>- `syncRulesOutdatedNotice` |
| `webapp/templates/index.html` | Modify | Holds all markup and CSS:<br>- the `#flaggedCard` panel<br>- the statement window's `#statementModalFlagged` table<br>- the two Flagged filter pills<br>- the `#flagSettingsSection` Settings section<br>- the `#rulesOutdatedNotice` notice with `#reanalyzeButton`<br>- their CSS<br>- the app.js cache-busting query |
| `tests/test_webapp_flagged_dashboard.py` | Create | Tests S4's dashboard:<br>- node-harness tests on fabricated C5/C6 payloads<br>- static markup tests<br>- parity with `analysis/flag_groups.py`<br>- one end-to-end test on the served payload |

---

### Task 1: Tags for the new classification states

**Files:**
- Modify: `webapp/static/app.js:473-489`, the `categories` map in `transactionCategory`; the anchors are line 477 (`lease_or_equipment_financing`) and line 480 (`credit_card_payment`).
- Test: `tests/test_webapp_flagged_dashboard.py` (create).

**Interfaces:**
- Consumes:
  - C4 states `alternative_position`, `line_of_credit`, `vehicle_financing`, `bank_loan`, `mortgage`, `lease_or_rental`, `personal_loan`, `floor_plan_financing` and `factoring`;
  - `credit_card_payment`, which is now the Credit cards group (C1);
  - the retired `lease_or_equipment_financing`;
  - `classification.canonical_entity`.
- Produces: `transactionCategory(tx)` returns `{label, glyph, tone}` for each of them. A credit's revenue state still wins (unchanged).
  - Every flag-group state names its payee when the classifier named one: `<entity> (<kind>)`. That includes `credit_card_payment`, whose card issuers S2 names (C2 `CARD_ISSUER_ALIASES`), so a card row's tag names the payee the panel lists.
  - Without an entity, `credit_card_payment` keeps "Credit Card Payment". Today's classifier never sets an entity on it (`analysis/transaction_classifier.py:1080-1088`), so analyses saved before this change keep their tag.
  - Premium financing has no state (C1 `state=None`). Its rows stay `insurance`, and their tag stays `entity || "Insurance"` (app.js:476, unchanged). The test pins that.

- [ ] **Step 1: Write the failing test.** Create `tests/test_webapp_flagged_dashboard.py` with exactly this content:

```python
"""The dashboard's flagged positions (webapp/static/app.js, webapp/templates/index.html), driven end to end in node on
a fake page (tests/webapp_js_harness.py): the tags of the new classification states, the Flagged chip and ledger
filter, the Flagged positions panel on a statement, a package and the statement window, the Settings switches, and the
notice on a statement analysed with older lender rules. The payloads follow the service contract
(docs/superpowers/plans/2026-09-24-lender-detection.md, C5, C6 and C8); every descriptor, payee and amount is
fabricated, and every amount is whole dollars."""
import json
import re
from pathlib import Path

import pytest

from tests.test_webapp_studio_views import CELLS, _serve
from tests.webapp_js_harness import NODE, run_dashboard

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


# ---------------------------------------------------------------- Task 1: tags of the new states

@needs_node
def test_every_new_state_has_its_own_tag_and_the_retired_state_keeps_one():
    states = [
        ("alternative_position", "FABRICATED PLATFORM CAPITAL", "FABRICATED PLATFORM CAPITAL (Alternative position)"),
        ("line_of_credit", None, "Line of credit"),
        ("vehicle_financing", "FABRICATED AUTO FINANCE", "FABRICATED AUTO FINANCE (Vehicle loan / lease)"),
        ("bank_loan", None, "Bank loan"),
        ("mortgage", "FABRICATED MORTGAGE CO", "FABRICATED MORTGAGE CO (Mortgage)"),
        ("lease_or_rental", None, "Lease / rental"),
        ("personal_loan", "FABRICATED PERSONAL LENDER", "FABRICATED PERSONAL LENDER (Personal loan)"),
        ("floor_plan_financing", "FABRICATED FLOORING CAPITAL", "FABRICATED FLOORING CAPITAL (Floor plan)"),
        ("factoring", None, "Factoring"),
        # Retired on 2026-09-24; an analysis saved before then still carries it.
        ("lease_or_equipment_financing", "FABRICATED LEASING", "Lease / Equipment"),
        # The Credit cards group names its card issuer, as the Flagged positions panel does.
        ("credit_card_payment", "FABRICATED CARD ISSUER", "FABRICATED CARD ISSUER (Credit card)"),
        ("credit_card_payment", None, "Credit Card Payment"),
    ]
    debits = [{"amount": -100.0, "classification": {"classification": state, "canonical_entity": entity}}
              for state, entity, _ in states]
    credit = {"amount": 900.0, "classification": {"classification": "other", "canonical_entity": "FABRICATED LINE LENDER",
                                                  "revenue_classification": "non_revenue"}}
    # Premium financing is no state of its own: the row stays insurance and is flagged through flagged_group (C4).
    premium = {"amount": -250.0, "classification": {"classification": "insurance",
                                                    "canonical_entity": "FABRICATED PREMIUM FINANCE",
                                                    "flagged_group": "premium_financing"}}
    result = run_dashboard(f"""
const debits = {json.dumps(debits)};
console.log(JSON.stringify({{labels: debits.map((tx) => transactionCategory(tx).label),
  credit: transactionCategory({json.dumps(credit)}).label, premium: transactionCategory({json.dumps(premium)})}}));
""")
    assert result["labels"] == [label for _, _, label in states]
    # A credit shows its revenue state first, whoever paid it.
    assert result["credit"] == "Non-Revenue"
    # A premium-financing row keeps its insurance tag, unchanged.
    assert result["premium"] == {"label": "FABRICATED PREMIUM FINANCE", "glyph": "INS", "tone": "blue"}
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py::test_every_new_state_has_its_own_tag_and_the_retired_state_keeps_one -q -p no:cacheprovider`

Expected: FAIL with `AssertionError: assert ['Other Debit', ...] == ['FABRICATED PLATFORM CAPITAL (Alternative position)', ...]`. The new states have no entry in `categories`, so they fall back to "Other Debit". The named card payment also reads "Credit Card Payment" rather than naming its issuer.

- [ ] **Step 3: Implement.** Edit `webapp/static/app.js`. Find:

```js
    lease_or_equipment_financing: { label: "Lease / Equipment", glyph: "LSE", tone: "neutral" },
```

Replace with:

```js
    // Retired 2026-09-24 (lender detection): analyses saved before then still carry it.
    lease_or_equipment_financing: { label: "Lease / Equipment", glyph: "LSE", tone: "neutral" },
    alternative_position: { label: entity ? `${entity} (Alternative position)` : "Alternative position", glyph: "ALT", tone: "neutral" },
    line_of_credit: { label: entity ? `${entity} (Line of credit)` : "Line of credit", glyph: "LOC", tone: "neutral" },
    vehicle_financing: { label: entity ? `${entity} (Vehicle loan / lease)` : "Vehicle loan / lease", glyph: "VEH", tone: "neutral" },
    bank_loan: { label: entity ? `${entity} (Bank loan)` : "Bank loan", glyph: "BNK", tone: "neutral" },
    mortgage: { label: entity ? `${entity} (Mortgage)` : "Mortgage", glyph: "MTG", tone: "neutral" },
    lease_or_rental: { label: entity ? `${entity} (Lease / rental)` : "Lease / rental", glyph: "LSE", tone: "neutral" },
    personal_loan: { label: entity ? `${entity} (Personal loan)` : "Personal loan", glyph: "PLN", tone: "neutral" },
    floor_plan_financing: { label: entity ? `${entity} (Floor plan)` : "Floor plan", glyph: "FLR", tone: "neutral" },
    factoring: { label: entity ? `${entity} (Factoring)` : "Factoring", glyph: "FCT", tone: "neutral" },
```

Edit `webapp/static/app.js`. Find:

```js
    credit_card_payment: { label: "Credit Card Payment", glyph: "CC", tone: "neutral" },
```

Replace with:

```js
    credit_card_payment: { label: entity ? `${entity} (Credit card)` : "Credit Card Payment", glyph: "CC", tone: "neutral" },
```

- [ ] **Step 4: Run the test and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py::test_every_new_state_has_its_own_tag_and_the_retired_state_keeps_one -q -p no:cacheprovider`

Expected: PASS.

Then run DASHBOARD GUARDS. Expected: no failures.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: tags for the flagged-group classification states"
```

---

### Task 2: The Flagged chip and the "flagged" ledger filter

**Files:**
- Modify `webapp/static/app.js`:
  - after `contributesToPotentialTotals` (495-501);
  - `filterTransactions` (503-517, anchored on line 509);
  - the category cell in `renderTransactionRows` (line 700).
- Modify `webapp/templates/index.html`:
  - the main pills (after line 1340);
  - the modal pills (after line 1550);
  - CSS after line 619.
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes: `classification.flag_shown` (C6), `classification.flagged_group` and `contributes_to_flagged_totals` (C4). The fixtures carry them.
- Produces:
  - `flaggedChip(tx) -> string`;
  - the filter value `"flagged"` in `filterTransactions` (C8), which keeps rows where `classification.flag_shown === true`;
  - the pills `data-transaction-filter="flagged"` and `data-modal-transaction-filter="flagged"`;
  - the fixtures `ROWS`, `_row`, `LEDGER`, `POSITIONS`, `_statement` and `_load`, and the premium-financing fixtures `_insured`, `PREMIUM_LEDGER` and `PREMIUM_POSITIONS`, which later tasks use.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 2: the Flagged chip and ledger filter

ROWS = r"""
const rowsOf = (html) => [...html.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)].map((match) => match[1]);
const datesOf = (html) => rowsOf(html).map((row) => (row.match(/<td class="tx-date">([^<]*)<\/td>/) || [])[1]);
const flaggedOf = (html) => rowsOf(html).map((row) => row.includes('<span class="chip-text">Flagged</span>'));
"""


def _row(location, date, description, amount, state, *, entity=None, group=None, counted=None, shown=None,
         revenue=None):
    """A ledger row as the server serves it: its classification record (C4) and the serving-time flag_shown (C6)."""
    record = {"classification": state, "canonical_entity": entity, "source_location": location, "flagged_group": group,
              "contributes_to_flagged_totals": bool(group) if counted is None else counted,
              "flag_shown": bool(group) if shown is None else shown}
    if revenue:
        record["revenue_classification"] = revenue
    return {"date": date, "description": description, "amount": amount, "classification": record}


LEDGER = [
    _row("transaction:1", "2031-03-03", "ACH DEBIT FABRICATED MORTGAGE CO PMT", -1200.0, "mortgage",
         entity="FABRICATED MORTGAGE CO", group="mortgages"),
    _row("transaction:2", "2031-03-05", "ONLINE PAYMENT FABRICATED CARD", -300.0, "credit_card_payment",
         group="credit_cards"),
    _row("transaction:3", "2031-03-17", "ACH DEBIT FABRICATED MORTGAGE CO PMT", -1200.0, "mortgage",
         entity="FABRICATED MORTGAGE CO", group="mortgages"),
    # The same debit printed twice: tagged and shown, never counted (a proven duplicate).
    _row("transaction:4", "2031-03-17", "ACH DEBIT FABRICATED MORTGAGE CO PMT", -1200.0, "mortgage",
         entity="FABRICATED MORTGAGE CO", group="mortgages", counted=False),
    _row("transaction:5", "2031-03-20", "ACH CREDIT FABRICATED CUSTOMER", 5000.0, "other", revenue="verified_revenue"),
    # A group unticked in Settings: the server served its row with flag_shown false.
    _row("transaction:6", "2031-03-24", "ACH DEBIT FABRICATED AUTO FINANCE", -400.0, "vehicle_financing",
         entity="FABRICATED AUTO FINANCE", group="vehicle_financing", shown=False),
]

# detection.flagged_positions as S2 serves it (C5): group order, then total, then payee. An unnamed payee is its group.
POSITIONS = [
    {"group": "credit_cards", "payee": "Credit cards", "matched_alias": None, "count": 1, "total_debited": 300.0,
     "cadence": "single", "avg_gap_days": None, "first_date": "2031-03-05", "last_date": "2031-03-05",
     "source_locations": ["transaction:2"]},
    {"group": "mortgages", "payee": "FABRICATED MORTGAGE CO", "matched_alias": "FABRICATED MORTGAGE", "count": 2,
     "total_debited": 2400.0, "cadence": "biweekly", "avg_gap_days": 14.0, "first_date": "2031-03-03",
     "last_date": "2031-03-17", "source_locations": ["transaction:1", "transaction:3"]},
]


def _statement(*, positions=POSITIONS, ledger=LEDGER, currency="CAD", outdated=None):
    """One account as /analysis serves it. `positions=None` is an analysis saved before flagged positions existed."""
    detection = {"known_funders": [], "potential_lenders": [], "insurance_providers": []}
    if positions is not None:
        detection["flagged_positions"] = positions
    payload = {"statement": {"bank": "FABRICATED COMMUNITY BANK", "currency": currency, "period_start": "2031-03-01",
                             "period_end": "2031-03-31", "transactions": ledger},
               "metrics": {"flagged_groups": {"credit_cards": {"count": 1, "total": 300.0, "payees": 1},
                                              "mortgages": {"count": 2, "total": 2400.0, "payees": 1}}},
               "detection": detection}
    if outdated is not None:
        payload["analysis_rules_outdated"] = outdated
    return payload


def _load(job_id, payload):
    """Serve one statement and open it, as a reopen from Recent does."""
    return _serve(**{job_id: payload}) + (f"currentJobId = '{job_id}'; currentJobIds = ['{job_id}'];"
                                         f" loadResults('{job_id}'); await settle();\n")


@needs_node
def test_rows_shown_as_flagged_carry_the_chip_and_the_flagged_filter_keeps_only_them():
    result = run_dashboard(ROWS + _load("s", _statement()) + """
const all = {dates: datesOf(els.transactionTable.innerHTML), flagged: flaggedOf(els.transactionTable.innerHTML)};
transactionFilter = 'flagged'; renderMainTransactions();
console.log(JSON.stringify({all, filtered: {dates: datesOf(els.transactionTable.innerHTML),
  count: els.transactionCount.textContent}}));
""")
    assert result["all"]["dates"] == ["2031-03-03", "2031-03-05", "2031-03-17", "2031-03-17", "2031-03-20",
                                      "2031-03-24"]
    # Flagged: both mortgage debits, the duplicate and the card payment; never the revenue credit, never a row of a
    # group unticked in Settings.
    assert result["all"]["flagged"] == [True, True, True, True, False, False]
    assert result["filtered"] == {"dates": ["2031-03-03", "2031-03-05", "2031-03-17", "2031-03-17"],
                                  "count": "4 flagged matches"}


def _insured(row):
    """A row counted in the insurance totals, as the classifier leaves every insurance row (C4)."""
    row["classification"]["contributes_to_insurance_totals"] = True
    return row


# Premium financing (C1, C4) is no state of its own: its rows stay insurance, in the insurance totals, and are flagged
# through flagged_group. A plain insurer's row is not flagged.
PREMIUM_LEDGER = [
    _insured(_row("transaction:1", "2031-03-04", "ACH DEBIT FABRICATED PREMIUM FINANCE", -250.0, "insurance",
                  entity="FABRICATED PREMIUM FINANCE", group="premium_financing")),
    _insured(_row("transaction:2", "2031-03-09", "ACH DEBIT FABRICATED INSURER", -90.0, "insurance",
                  entity="FABRICATED INSURER")),
    _insured(_row("transaction:3", "2031-03-18", "ACH DEBIT FABRICATED PREMIUM FINANCE", -250.0, "insurance",
                  entity="FABRICATED PREMIUM FINANCE", group="premium_financing")),
]

PREMIUM_POSITIONS = [
    {"group": "premium_financing", "payee": "FABRICATED PREMIUM FINANCE", "matched_alias": "FABRICATED PREMIUM FINANCE",
     "count": 2, "total_debited": 500.0, "cadence": "biweekly", "avg_gap_days": 14.0, "first_date": "2031-03-04",
     "last_date": "2031-03-18", "source_locations": ["transaction:1", "transaction:3"]},
]


@needs_node
def test_a_premium_financing_row_keeps_its_insurance_tag_and_filter_and_carries_the_chip():
    result = run_dashboard(ROWS + _load("p", _statement(positions=PREMIUM_POSITIONS, ledger=PREMIUM_LEDGER)) + """
const tagged = (text) => rowsOf(els.transactionTable.innerHTML)
  .map((row) => row.includes(`<span class="chip-text">${text}</span>`));
const all = {dates: datesOf(els.transactionTable.innerHTML), tag: tagged('FABRICATED PREMIUM FINANCE'),
  flagged: flaggedOf(els.transactionTable.innerHTML)};
transactionFilter = 'insurance'; renderMainTransactions();
const insurance = datesOf(els.transactionTable.innerHTML);
transactionFilter = 'flagged'; renderMainTransactions();
console.log(JSON.stringify({all, insurance, flagged: datesOf(els.transactionTable.innerHTML)}));
""")
    assert result["all"] == {"dates": ["2031-03-04", "2031-03-09", "2031-03-18"], "tag": [True, False, True],
                             "flagged": [True, False, True]}
    # Still insurance: the Insurance pill keeps every insurance row, the premium-financing ones included.
    assert result["insurance"] == ["2031-03-04", "2031-03-09", "2031-03-18"]
    assert result["flagged"] == ["2031-03-04", "2031-03-18"]


def test_both_ledgers_offer_the_flagged_filter():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert 'data-transaction-filter="flagged">Flagged</button>' in html
    assert 'data-modal-transaction-filter="flagged">Flagged</button>' in html
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py::test_rows_shown_as_flagged_carry_the_chip_and_the_flagged_filter_keeps_only_them tests/test_webapp_flagged_dashboard.py::test_a_premium_financing_row_keeps_its_insurance_tag_and_filter_and_carries_the_chip tests/test_webapp_flagged_dashboard.py::test_both_ledgers_offer_the_flagged_filter -q -p no:cacheprovider`

Expected: 3 FAIL.
- In the first, `flagged` is all `False` because no chip is drawn. The unknown filter `flagged` also keeps all 6 rows, giving "6 flagged matches".
- In the second, `flagged` is `[False, False, False]` for the same reason. The tag and the Insurance filter already hold.
- In the third, the pills are absent.

- [ ] **Step 3: Implement.**

Edit `webapp/static/app.js`. Find:

```js
  return record.contributes_to_potential_lender_count === true;
}
```

Replace with:

```js
  return record.contributes_to_potential_lender_count === true;
}

// A row of a flagged group ticked in Settings: the server marks it (flag_shown) when it serves the analysis.
function flaggedChip(tx) {
  return transactionClassification(tx).flag_shown === true ? glassChip("FLG", "Flagged", "blue", "flag-chip") : "";
}
```

Edit `webapp/static/app.js`. Find:

```js
  if (filter === "pos") matched = transactions.filter((tx) => transactionClassification(tx).classification === "pos");
```

Replace with:

```js
  if (filter === "pos") matched = transactions.filter((tx) => transactionClassification(tx).classification === "pos");
  if (filter === "flagged") matched = transactions.filter((tx) => transactionClassification(tx).flag_shown === true);
```

Edit `webapp/static/app.js`. Find:

```js
        <td>${glassChip(category.glyph, category.label, category.tone)}${reviewReasonHtml}</td>
```

Replace with:

```js
        <td>${glassChip(category.glyph, category.label, category.tone)}${flaggedChip(tx)}${reviewReasonHtml}</td>
```

Edit `webapp/templates/index.html`. Find:

```html
            <button class="transaction-filter" type="button" data-transaction-filter="insurance">Insurance</button>
```

Replace with:

```html
            <button class="transaction-filter" type="button" data-transaction-filter="insurance">Insurance</button>
            <button class="transaction-filter" type="button" data-transaction-filter="flagged">Flagged</button>
```

Edit `webapp/templates/index.html`. Find:

```html
          <button class="transaction-filter" type="button" data-modal-transaction-filter="insurance">Insurance</button>
```

Replace with:

```html
          <button class="transaction-filter" type="button" data-modal-transaction-filter="insurance">Insurance</button>
          <button class="transaction-filter" type="button" data-modal-transaction-filter="flagged">Flagged</button>
```

Edit `webapp/templates/index.html`. Find:

```css
  .glass-chip.violet { background: var(--violet-soft); color: var(--violet); }
```

Replace with:

```css
  .glass-chip.violet { background: var(--violet-soft); color: var(--violet); }
  .glass-chip.flag-chip { margin-left: 6px; }
```

- [ ] **Step 4: Run the tests and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 4 passed.

Then run DASHBOARD GUARDS. Expected: no failures.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js webapp/templates/index.html tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: Flagged chip and ledger filter for rows served as flagged"
```

---

### Task 3: FLAG_GROUP_LABELS and the Flagged positions panel on a statement

**Files:**
- Modify `webapp/static/app.js`:
  - after `nsfSourceLabel` (291-293);
  - `els` (after line 75);
  - after `renderInsurance` (ends at 1570);
  - `setInitialState` (1160-1161);
  - `renderAccount` (2469-2471).
- Modify `webapp/templates/index.html`:
  - the panel markup before line 1294 (the `split-2 package-only` section);
  - CSS after line 604.
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes:
  - C5 `detection.flagged_positions`: a list of `{group, payee, matched_alias, count, total_debited, cadence, avg_gap_days, first_date, last_date, source_locations}`. An analysis saved before this change has no such key.
  - The C1 labels.
- Produces:
  - `FLAG_GROUP_LABELS` (C8), an object literal keyed by group key.
  - `ownKey(table, key) -> boolean`. It is true when a label table defines `key` itself, and never for an inherited name such as `constructor`. It uses `Object.prototype.hasOwnProperty.call`, not `Object.hasOwn`: app.js uses `Object.hasOwn` nowhere, and it would raise the page's browser floor to ES2022.
  - `flagGroupLabel(group) -> string`.
  - `CADENCE_LABELS` and `cadenceLabel(cadence) -> string`.
  - `flaggedPositionEntries(positions) -> Array|null`. It returns `null` when the payload publishes no flagged positions.
  - `flaggedPositionRowsHtml(entries, currency, isPackage) -> string`. It draws one row per payee. For `[]` it draws a "No flagged payments" row, and for `null` a "Not available" row.
  - `renderFlaggedPositions(positions, currency, isPackage)` (C8).
  - The markup `#flaggedCard`, `#flaggedCount` and `<tbody id="flaggedTable">` (C8). Each payee is a button carrying `data-lender-evidence-filter="flagged:<group>"` and `data-lender-evidence-entity="<payee>"`. Task 4 makes the click work.
  - `els.flaggedTable` and `els.flaggedCount`.
  - The test constants `PANEL`, `NO_FLAGGED_PAYMENTS` and `NOT_AVAILABLE`, which later tasks use.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 3: the panel on a statement

PANEL = """
console.log(JSON.stringify({rows: cells(els.flaggedTable.innerHTML), count: els.flaggedCount.textContent,
  html: els.flaggedTable.innerHTML}));
"""

# The two rows a panel with no payee draws, as `cells` reads them (tags stripped).
NO_FLAGGED_PAYMENTS = "No flagged paymentsNo group ticked in Settings has payments here."
NOT_AVAILABLE = "Not availableAnalysed before flagged positions existed; re-analyze to see them."


@needs_node
def test_the_statement_panel_lists_each_payee_with_its_group_count_total_and_cadence():
    result = run_dashboard(CELLS + _load("s", _statement()) + PANEL)
    # Money in the statement's own currency (CA$), never the USD default.
    assert result["rows"] == [
        ["Credit cards", "Credit cards", "1", "CA$300.00", "Single payment"],
        ["Mortgages", "FABRICATED MORTGAGE CO", "2", "CA$2,400.00", "Every two weeks2031-03-03 to 2031-03-17"],
    ]
    assert result["count"] == "2 payees"
    assert 'data-lender-evidence-filter="flagged:mortgages"' in result["html"]
    assert 'data-lender-evidence-entity="FABRICATED MORTGAGE CO"' in result["html"]


@needs_node
@pytest.mark.parametrize(("positions", "row", "count"), [
    ([], NO_FLAGGED_PAYMENTS, "0 payees"),
    # Saved before flagged positions existed: the dashboard cannot tell whether any group was paid, and says so.
    (None, NOT_AVAILABLE, "Not available"),
], ids=["no-ticked-group-paid", "saved-before-flagged-positions"])
def test_a_statement_without_flagged_positions_says_why(positions, row, count):
    result = run_dashboard(CELLS + _load("s", _statement(positions=positions)) + PANEL)
    assert result["rows"] == [[row]]
    assert 'colspan="5"' in result["html"] and result["count"] == count


def test_the_panel_sits_after_the_evidence_and_reuses_no_lender_header():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    card = html[html.index('id="flaggedCard"'):]
    card = card[:card.index("</section>")]
    assert re.findall(r"<th[^>]*>([^<]*)</th>", card) == ["Group", "Payee", "Count", "Total", "Cadence", "Statements"]
    assert '<tbody id="flaggedTable">' in card and 'id="flaggedCount"' in card and "Flagged positions</h3>" in card
    for reused in ("Potential Withholding", "Eligible Deposits", "Exposure"):
        assert reused not in card
    assert html.index('aria-label="Evidence"') < html.index('id="flaggedCard"') \
        < html.index('aria-label="Package summary and processing"')
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider -k "statement_panel or statement_without_flagged or panel_sits"`

Expected: 4 FAIL.
- The three node tests fail with `TypeError: Cannot read properties of undefined (reading 'innerHTML')`, because `els.flaggedTable` does not exist.
- The static test fails with `ValueError: substring not found` (`id="flaggedCard"`).

- [ ] **Step 3: Implement.**

Edit `webapp/static/app.js`. Find:

```js
function nsfSourceLabel(source) {
  return NSF_SOURCE_LABELS[source] || (source ? labelize(source) : "Negative-ending days");
}
```

Replace with:

```js
function nsfSourceLabel(source) {
  return NSF_SOURCE_LABELS[source] || (source ? labelize(source) : "Negative-ending days");
}

// Whether a label table defines `key` itself: never an inherited name such as "constructor" or "toString".
function ownKey(table, key) {
  return Object.prototype.hasOwnProperty.call(table, String(key ?? ""));
}

// The groups of obligations flagged outside lender math, in the analysis's order (analysis/flag_groups.py
// FLAG_GROUPS; tests/test_webapp_flagged_dashboard.py keeps the two alike). A group's settings key is flag_<group>.
// Premium financing is the one group with no classification state: its rows stay insurance and carry flagged_group.
const FLAG_GROUP_LABELS = Object.freeze({
  alternative_positions: "Alternative positions",
  lines_of_credit: "Lines of credit",
  credit_cards: "Credit cards",
  vehicle_financing: "Vehicle loans & leases",
  bank_loans: "Bank loans",
  mortgages: "Mortgages",
  leases_rentals: "Leases & rentals",
  personal_loans: "Personal loans",
  floor_plan: "Floor plan",
  factoring: "Factoring",
  premium_financing: "Premium financing",
});

function flagGroupLabel(group) {
  return ownKey(FLAG_GROUP_LABELS, group) ? FLAG_GROUP_LABELS[group] : labelize(group);
}

// How often a flagged payee was paid, as the analysis describes it (analysis/cadence.py describe_cadence).
const CADENCE_LABELS = Object.freeze({
  daily: "Daily",
  weekly: "Weekly",
  biweekly: "Every two weeks",
  monthly: "Monthly",
  irregular: "Irregular",
  single: "Single payment",
});

function cadenceLabel(cadence) {
  return ownKey(CADENCE_LABELS, cadence) ? CADENCE_LABELS[cadence] : labelize(cadence);
}
```

Edit `webapp/static/app.js`. Find:

```js
  insuranceCount: document.getElementById("insuranceCount"),
```

Replace with:

```js
  insuranceCount: document.getElementById("insuranceCount"),
  flaggedTable: document.getElementById("flaggedTable"),
  flaggedCount: document.getElementById("flaggedCount"),
```

Edit `webapp/static/app.js`. This is the end of `renderInsurance`. Find:

```js
      <td>${glassChip("INS", "Insurance", "blue")}</td>
    </tr>
  `).join("");
}
```

Replace with:

```js
      <td>${glassChip("INS", "Insurance", "blue")}</td>
    </tr>
  `).join("");
}

/* --- flagged positions ------------------------------------------------------
   Obligations outside lender math (analysis/flag_groups.py), one row per payee, for the groups ticked in Settings:
   the server leaves the other groups out when it serves the analysis. */

// The panel's rows. A statement serves one list (detection.flagged_positions, already in group order), a package one
// list per group (flagged_positions): either way they come out group by group, each group's own order kept. Null when
// the payload publishes none (an analysis saved before flagged positions existed): the panel then cannot say whether
// any group was paid.
function flaggedPositionEntries(positions) {
  const entries = (list) => (Array.isArray(list) ? list : []).filter((entry) => entry && typeof entry === "object");
  if (Array.isArray(positions)) return entries(positions);
  if (!positions || typeof positions !== "object") return null;
  const known = Object.keys(FLAG_GROUP_LABELS);
  const groups = [...known, ...Object.keys(positions).filter((group) => !known.includes(group))];
  return groups.flatMap((group) => entries(positions[group]).map((entry) => ({ ...entry, group })));
}

// `isPackage` adds the Statements column: how many of the package's statements paid the payee.
function flaggedPositionRowsHtml(entries, currency, isPackage = false) {
  const columns = isPackage ? 6 : 5;
  if (entries === null) {
    return `
      <tr>
        <td class="empty-cell" colspan="${columns}"><strong>Not available</strong>Analysed before flagged positions existed; re-analyze to see them.</td>
      </tr>
    `;
  }
  if (!entries.length) {
    return `
      <tr>
        <td class="empty-cell" colspan="${columns}"><strong>No flagged payments</strong>No group ticked in Settings has payments here.</td>
      </tr>
    `;
  }
  return entries.map((entry) => {
    const group = String(entry.group || "");
    const payee = String(entry.payee || flagGroupLabel(group));
    const span = entry.first_date && entry.last_date && entry.first_date !== entry.last_date
      ? `<div class="table-cell-detail">${escapeHtml(entry.first_date)} to ${escapeHtml(entry.last_date)}</div>`
      : "";
    const statements = isPackage ? `<td>${escapeHtml(formatNumber(entry.documents))}</td>` : "";
    return `
      <tr>
        <td>${escapeHtml(flagGroupLabel(group))}</td>
        <td><button class="evidence-link" type="button" data-lender-evidence-filter="flagged:${escapeHtml(group)}" data-lender-evidence-entity="${escapeHtml(payee)}" aria-label="Show the transactions paid to ${escapeHtml(payee)}">${escapeHtml(payee)}</button></td>
        <td>${escapeHtml(formatNumber(entry.count))}</td>
        <td>${escapeHtml(formatMoney(entry.total_debited, currency))}</td>
        <td>${escapeHtml(cadenceLabel(entry.cadence))}${span}</td>
        ${statements}
      </tr>
    `;
  }).join("");
}

function renderFlaggedPositions(positions, currency, isPackage = false) {
  if (!els.flaggedTable || !els.flaggedCount) return;
  const entries = flaggedPositionEntries(positions);
  els.flaggedCount.textContent = entries === null
    ? "Not available"
    : `${formatNumber(entries.length)} ${entries.length === 1 ? "payee" : "payees"}`;
  els.flaggedTable.innerHTML = flaggedPositionRowsHtml(entries, currency, isPackage);
}
```

Edit `webapp/static/app.js`, in `setInitialState`. Find:

```js
  renderLenders([]);
  renderInsurance([]);
```

Replace with:

```js
  renderLenders([]);
  renderInsurance([]);
  renderFlaggedPositions([], null, false);
```

Edit `webapp/static/app.js`, in `renderAccount`. Find:

```js
  renderLenders(funders, potentialLenders, currency);
  renderInsurance(insuranceProviders, currency);
  renderMainTransactions();
```

Replace with:

```js
  renderLenders(funders, potentialLenders, currency);
  renderInsurance(insuranceProviders, currency);
  renderFlaggedPositions(detection.flagged_positions, currency, false);
  renderMainTransactions();
```

Edit `webapp/templates/index.html`. Find:

```html
        <section class="split-2 package-only" aria-label="Package summary and processing">
```

Replace with:

```html
        <!-- Obligations outside lender math, for the groups ticked in Settings (renderFlaggedPositions). -->
        <section class="panel flagged-panel" id="flaggedCard" aria-labelledby="flaggedTitle">
          <div class="panel-head">
            <h3 id="flaggedTitle">Flagged positions</h3>
            <span class="panel-sub" id="flaggedCount">0 payees</span>
          </div>
          <p class="flagged-note">Obligations outside lender math: never counted as lenders, never in withholding.</p>
          <div class="table-wrap">
            <table class="data-table flagged-table">
              <thead>
                <tr>
                  <th>Group</th>
                  <th>Payee</th>
                  <th>Count</th>
                  <th>Total</th>
                  <th>Cadence</th>
                  <th class="package-only">Statements</th>
                </tr>
              </thead>
              <tbody id="flaggedTable"></tbody>
            </table>
          </div>
        </section>

        <section class="split-2 package-only" aria-label="Package summary and processing">
```

Edit `webapp/templates/index.html`. The group column's colour rule skips the empty-state cell, which is also a first cell. Without `:not(.empty-cell)`, `.flagged-table td:first-child` (specificity 0,2,1) would beat `.flagged-table .empty-cell` (0,2,0) and colour the empty state `--text-2`. Find:

```css
  .evidence-table th:nth-child(2), .evidence-table th:nth-child(3) { text-align: right; }
```

Replace with:

```css
  .evidence-table th:nth-child(2), .evidence-table th:nth-child(3) { text-align: right; }
  .flagged-note { margin: 0; padding: 0 20px 12px; font-size: 12.5px; color: var(--text-3); }
  .flagged-table td:nth-child(3), .flagged-table td:nth-child(4), .flagged-table td:nth-child(6) { text-align: right; font-family: var(--font-mono); }
  .flagged-table th:nth-child(3), .flagged-table th:nth-child(4), .flagged-table th:nth-child(6) { text-align: right; }
  .flagged-table td:first-child:not(.empty-cell) { color: var(--text-2); }
  .flagged-table .empty-cell { color: var(--text-3); padding-top: 20px; padding-bottom: 20px; }
  .flagged-table .empty-cell strong { color: var(--text); margin-right: 6px; }
```

- [ ] **Step 4: Run the tests and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 8 passed.

Then run DASHBOARD GUARDS. Expected: no failures. In particular:
- `<th>Potential Withholding</th>` is still counted 2;
- every `formatMoney(` call still has 2 arguments.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js webapp/templates/index.html tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: Flagged positions panel on the statement page"
```

---

### Task 4: A payee click filters the ledger to the rows behind it

**Files:**
- Modify `webapp/static/app.js`:
  - after `flaggedChip` (Task 2);
  - `filterTransactions` (503-517 at the base; Task 2 added one line to it, so the three anchors below are quoted text);
  - after the `statementModalLenders` click listener (ends at 4287).
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes:
  - the row fields `flagged_group`, `contributes_to_flagged_totals`, `flag_shown` and `canonical_entity` (C4, C6);
  - `flagGroupLabel` and the payee buttons of `#flaggedTable` (Task 3);
  - the premium-financing fixtures of Task 2: a flagged row whose state is `insurance`;
  - `lenderEvidenceSelection(event)` (app.js:4256), `setTransactionFilterButtons` (app.js:1016) and `renderMainTransactions` (app.js:758), which already exist.
- Produces:
  - `flaggedFilterGroup(filter) -> string|null`.
  - `flaggedPayeeOf(tx) -> string|null`. It returns `canonical_entity`, or else the group label (C5's payee rule).
  - The ledger filter value `flagged:<group key>`. It keeps rows with `flag_shown === true`, that `flagged_group`, and `contributes_to_flagged_totals === true`. With an entity, it keeps only the rows whose `flaggedPayeeOf(tx)` equals it.
  - A `click` listener on `els.flaggedTable`.
  - The test helper `PAYEE_CLICK`, which later tasks use.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 4: a payee click filters the ledger

PAYEE_CLICK = """
const clickPayee = (table, group, payee) => {
  const button = fakeElement('payee'); button.closest = () => button;
  button.attributes['data-lender-evidence-filter'] = `flagged:${group}`;
  button.attributes['data-lender-evidence-entity'] = payee;
  table.listeners.click[0]({target: button});
};
"""


@needs_node
def test_a_payee_click_filters_the_ledger_to_the_rows_behind_it():
    result = run_dashboard(ROWS + PAYEE_CLICK + _load("s", _statement()) + """
const shown = () => ({filter: transactionFilter, entity: transactionEntityFilter,
  count: els.transactionCount.textContent, dates: datesOf(els.transactionTable.innerHTML)});
clickPayee(els.flaggedTable, 'mortgages', 'FABRICATED MORTGAGE CO');
const mortgage = shown();
clickPayee(els.flaggedTable, 'credit_cards', 'Credit cards');
console.log(JSON.stringify({mortgage, card: shown()}));
""")
    # The rows the panel counted: the duplicate is tagged but not behind the payee's count.
    assert result["mortgage"] == {"filter": "flagged:mortgages", "entity": "FABRICATED MORTGAGE CO",
                                  "count": "2 FABRICATED MORTGAGE CO", "dates": ["2031-03-03", "2031-03-17"]}
    # An unnamed payee is its group, as the server names it.
    assert result["card"] == {"filter": "flagged:credit_cards", "entity": "Credit cards", "count": "1 Credit cards",
                              "dates": ["2031-03-05"]}


@needs_node
def test_a_premium_financing_payee_is_listed_under_its_group_and_its_click_shows_its_insurance_rows():
    result = run_dashboard(CELLS + ROWS + PAYEE_CLICK
                           + _load("p", _statement(positions=PREMIUM_POSITIONS, ledger=PREMIUM_LEDGER)) + """
const panel = cells(els.flaggedTable.innerHTML);
clickPayee(els.flaggedTable, 'premium_financing', 'FABRICATED PREMIUM FINANCE');
console.log(JSON.stringify({panel, filter: transactionFilter, count: els.transactionCount.textContent,
  dates: datesOf(els.transactionTable.innerHTML)}));
""")
    assert result["panel"] == [["Premium financing", "FABRICATED PREMIUM FINANCE", "2", "CA$500.00",
                                "Every two weeks2031-03-04 to 2031-03-18"]]
    # Keyed on flagged_group, not on the state: the rows stay insurance, and the plain insurer's row is left out.
    assert result["filter"] == "flagged:premium_financing"
    assert result["count"] == "2 FABRICATED PREMIUM FINANCE"
    assert result["dates"] == ["2031-03-04", "2031-03-18"]
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py::test_a_payee_click_filters_the_ledger_to_the_rows_behind_it tests/test_webapp_flagged_dashboard.py::test_a_premium_financing_payee_is_listed_under_its_group_and_its_click_shows_its_insurance_rows -q -p no:cacheprovider`

Expected: 2 FAIL, both with `TypeError: Cannot read properties of undefined (reading '0')`, because `els.flaggedTable` has no `click` listener yet.

- [ ] **Step 3: Implement.**

Edit `webapp/static/app.js`. Find:

```js
  return transactionClassification(tx).flag_shown === true ? glassChip("FLG", "Flagged", "blue", "flag-chip") : "";
}
```

Replace with:

```js
  return transactionClassification(tx).flag_shown === true ? glassChip("FLG", "Flagged", "blue", "flag-chip") : "";
}

// The ledger filter behind one row of the Flagged positions panel is "flagged:<group>": that group's rows that count,
// of the payee clicked. Null for any other filter.
function flaggedFilterGroup(filter) {
  const match = /^flagged:([a-z_]+)$/.exec(String(filter || ""));
  return match ? match[1] : null;
}

// Who a flagged row paid, as the panel names it: the payee the classifier named, else the row's group.
function flaggedPayeeOf(tx) {
  const record = transactionClassification(tx);
  return record.canonical_entity || (record.flagged_group ? flagGroupLabel(record.flagged_group) : null);
}
```

Edit `webapp/static/app.js`. Find:

```js
function filterTransactions(transactions, filter, canonicalEntity = null) {
  let matched = transactions;
```

Replace with:

```js
function filterTransactions(transactions, filter, canonicalEntity = null) {
  let matched = transactions;
  const flagGroup = flaggedFilterGroup(filter);
```

Edit `webapp/static/app.js`. Find:

```js
  if (filter === "flagged") matched = transactions.filter((tx) => transactionClassification(tx).flag_shown === true);
```

Replace with:

```js
  if (filter === "flagged") matched = transactions.filter((tx) => transactionClassification(tx).flag_shown === true);
  if (flagGroup) {
    matched = transactions.filter((tx) => {
      const record = transactionClassification(tx);
      return record.flag_shown === true && record.flagged_group === flagGroup
        && record.contributes_to_flagged_totals === true;
    });
  }
```

Edit `webapp/static/app.js`. Find:

```js
  if (!canonicalEntity) return matched;
  return matched.filter((tx) => transactionClassification(tx).canonical_entity === canonicalEntity);
```

Replace with:

```js
  if (!canonicalEntity) return matched;
  if (flagGroup) return matched.filter((tx) => flaggedPayeeOf(tx) === canonicalEntity);
  return matched.filter((tx) => transactionClassification(tx).canonical_entity === canonicalEntity);
```

Edit `webapp/static/app.js`. This is the end of the `statementModalLenders` listener, before the All accounts block. Find:

```js
    renderModalTransactions();
    els.statementModalTransactions?.closest(".modal-panel")?.scrollIntoView({ block: "start" });
  });
}

/* --- All accounts ---------------------------------------------------------
```

Replace with:

```js
    renderModalTransactions();
    els.statementModalTransactions?.closest(".modal-panel")?.scrollIntoView({ block: "start" });
  });
}

// A payee of the Flagged positions panel shows the ledger rows behind it.
if (els.flaggedTable) {
  els.flaggedTable.addEventListener("click", (event) => {
    const selection = lenderEvidenceSelection(event);
    if (!selection) return;
    transactionFilter = selection.filter;
    transactionEntityFilter = selection.entity;
    setTransactionFilterButtons("[data-transaction-filter]", "flagged");
    renderMainTransactions();
    els.transactionCard?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

/* --- All accounts ---------------------------------------------------------
```

- [ ] **Step 4: Run the tests and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 10 passed.

Then run DASHBOARD GUARDS. Expected: no failures.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: a Flagged positions payee click filters the ledger to its counted rows"
```

---

### Task 5: The panel on the package page

**Files:**
- Modify: `webapp/static/app.js:3050-3062`, `renderPackageTables`.
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes:
  - the C6 `pkg.flagged_positions`: `{"<group key>": [{payee, documents, count, total_debited, cadence, first_date, last_date}]}`;
  - `packageCurrencyInfo(pkg).currency`, which is `null` when the currency is refused;
  - `pkg.transactions`, the combined ledger. `_package_analysis` builds each row as `{**tx, "source_job": ...}` (`webapp/app.py:1498-1509`), so each row keeps its classification record, `flag_shown` included;
  - `renderFlaggedPositions` (Task 3), and the payee click and `flagged:<group>` filter (Task 4);
  - the fixtures `_row` and `_insured` (Task 2), and `PAYEE_CLICK` (Task 4).
- Produces: the package page fills `#flaggedTable` with the Statements column, and a payee click there filters the combined ledger. The `PACKAGE` fixture is used by Task 10.
  - `PACKAGE` lists five groups, among them the amendment's three (floor plan, factoring, premium financing), in scrambled key order, so the test pins FLAG_GROUPS order across all three.
  - The package click is tested on a vehicle payee and on the premium-financing payee, whose combined-ledger rows stay `insurance`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 5: the panel on a package

PACKAGE = {
    "totals": {"decision": "approved", "flagged_position_count": 8, "flagged_position_total": 5450.0},
    "currency": {"currency": "CAD", "currencies": ["CAD"]},
    "documents": [], "transactions": [], "funders": [], "potential_lenders": [], "insurance_providers": [],
    # The package roll-up (C6): one list per ticked group, keyed by group, in no particular key order. It holds the
    # three groups of the owner's amendment (floor plan, factoring, premium financing) beside two older ones.
    "flagged_positions": {
        "factoring": [{"payee": "FABRICATED FACTOR FUNDING", "documents": 1, "count": 1, "total_debited": 150.0,
                       "cadence": "single", "first_date": "2031-02-10", "last_date": "2031-02-10"}],
        "premium_financing": [{"payee": "FABRICATED PREMIUM FINANCE", "documents": 1, "count": 2,
                               "total_debited": 500.0, "cadence": "biweekly", "first_date": "2031-02-04",
                               "last_date": "2031-02-18"}],
        "vehicle_financing": [{"payee": "FABRICATED AUTO FINANCE", "documents": 2, "count": 2, "total_debited": 800.0,
                               "cadence": "monthly", "first_date": "2031-01-24", "last_date": "2031-02-24"}],
        "floor_plan": [{"payee": "FABRICATED FLOORING CAPITAL", "documents": 2, "count": 2, "total_debited": 3000.0,
                        "cadence": "monthly", "first_date": "2031-01-15", "last_date": "2031-02-15"}],
        "alternative_positions": [{"payee": "FABRICATED PLATFORM CAPITAL", "documents": 1, "count": 1,
                                   "total_debited": 1000.0, "cadence": "single", "first_date": "2031-02-03",
                                   "last_date": "2031-02-03"}],
    },
}


def _in_statement(job_id, row):
    """A row of the package's combined ledger: the member's row, with the statement it came from."""
    return {**row, "source_job": job_id, "source_currency": "CAD"}


# The combined ledger behind PACKAGE's flagged positions. It holds the auto-finance debits of two statements, one of
# them printed twice (tagged, never counted), payees of two other groups, a revenue credit, and the premium-financing
# debits, which stay insurance, beside a plain insurer's debit.
PACKAGE_LEDGER = [
    _in_statement("a", _row("transaction:1", "2031-01-24", "ACH DEBIT FABRICATED AUTO FINANCE", -400.0,
                            "vehicle_financing", entity="FABRICATED AUTO FINANCE", group="vehicle_financing")),
    _in_statement("a", _row("transaction:2", "2031-01-27", "ACH CREDIT FABRICATED CUSTOMER", 5000.0, "other",
                            revenue="verified_revenue")),
    _in_statement("b", _row("transaction:1", "2031-02-03", "ACH DEBIT FABRICATED PLATFORM CAPITAL", -1000.0,
                            "alternative_position", entity="FABRICATED PLATFORM CAPITAL",
                            group="alternative_positions")),
    _in_statement("b", _row("transaction:2", "2031-02-24", "ACH DEBIT FABRICATED AUTO FINANCE", -400.0,
                            "vehicle_financing", entity="FABRICATED AUTO FINANCE", group="vehicle_financing")),
    _in_statement("b", _row("transaction:3", "2031-02-24", "ACH DEBIT FABRICATED AUTO FINANCE", -400.0,
                            "vehicle_financing", entity="FABRICATED AUTO FINANCE", group="vehicle_financing",
                            counted=False)),
    _in_statement("b", _row("transaction:4", "2031-02-10", "ACH DEBIT FABRICATED FACTOR FUNDING", -150.0, "factoring",
                            entity="FABRICATED FACTOR FUNDING", group="factoring")),
    _in_statement("b", _insured(_row("transaction:5", "2031-02-04", "ACH DEBIT FABRICATED PREMIUM FINANCE", -250.0,
                                     "insurance", entity="FABRICATED PREMIUM FINANCE", group="premium_financing"))),
    _in_statement("b", _insured(_row("transaction:6", "2031-02-11", "ACH DEBIT FABRICATED INSURER", -90.0, "insurance",
                                     entity="FABRICATED INSURER"))),
    _in_statement("b", _insured(_row("transaction:7", "2031-02-18", "ACH DEBIT FABRICATED PREMIUM FINANCE", -250.0,
                                     "insurance", entity="FABRICATED PREMIUM FINANCE", group="premium_financing"))),
]


def _package_page(package):
    return CELLS + f"""
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package)});
console.log(JSON.stringify({{rows: cells(els.flaggedTable.innerHTML), count: els.flaggedCount.textContent,
  html: els.flaggedTable.innerHTML, pill: els.decisionPill.textContent}}));
"""


@needs_node
def test_the_package_panel_lists_payees_group_by_group_with_their_statements():
    result = run_dashboard(_package_page(PACKAGE))
    # In FLAG_GROUPS order, whatever the order of the roll-up's keys: the amendment's three groups come last.
    assert result["rows"] == [
        ["Alternative positions", "FABRICATED PLATFORM CAPITAL", "1", "CA$1,000.00", "Single payment", "1"],
        ["Vehicle loans &amp; leases", "FABRICATED AUTO FINANCE", "2", "CA$800.00", "Monthly2031-01-24 to 2031-02-24",
         "2"],
        ["Floor plan", "FABRICATED FLOORING CAPITAL", "2", "CA$3,000.00", "Monthly2031-01-15 to 2031-02-15", "2"],
        ["Factoring", "FABRICATED FACTOR FUNDING", "1", "CA$150.00", "Single payment", "1"],
        ["Premium financing", "FABRICATED PREMIUM FINANCE", "2", "CA$500.00",
         "Every two weeks2031-02-04 to 2031-02-18", "1"],
    ]
    assert result["count"] == "5 payees"
    # Flagged positions never touch the package decision (D7).
    assert result["pill"] == "Package decision · Approved"


@needs_node
def test_a_package_that_refused_its_currency_pools_no_flagged_money():
    refused = {**PACKAGE,
               "currency": {"currency": None, "currencies": ["CAD", "USD"], "cross_currency_totals_refused": True,
                            "refusal_reason": "multiple_currencies"},
               "flagged_positions": {"vehicle_financing": [{**PACKAGE["flagged_positions"]["vehicle_financing"][0],
                                                            "total_debited": None}]}}
    result = run_dashboard(_package_page(refused))
    assert result["rows"] == [["Vehicle loans &amp; leases", "FABRICATED AUTO FINANCE", "2", "N/A",
                               "Monthly2031-01-24 to 2031-02-24", "2"]]


@needs_node
@pytest.mark.parametrize(("positions", "row"), [({}, NO_FLAGGED_PAYMENTS), (None, NOT_AVAILABLE)],
                         ids=["no-ticked-group-paid", "server-before-flagged-positions"])
def test_a_package_without_flagged_positions_says_why(positions, row):
    package = {key: value for key, value in PACKAGE.items() if key != "flagged_positions"}
    if positions is not None:
        package["flagged_positions"] = positions
    result = run_dashboard(_package_page(package))
    assert result["rows"] == [[row]]
    assert 'colspan="6"' in result["html"]


@needs_node
def test_a_package_payee_click_shows_the_combined_ledger_rows_behind_its_count():
    package = {**PACKAGE, "transactions": PACKAGE_LEDGER}
    result = run_dashboard(CELLS + ROWS + PAYEE_CLICK + f"""
currentJobIds = ['a', 'b']; renderPackageAnalysis({json.dumps(package)});
const panel = cells(els.flaggedTable.innerHTML);
const click = (group, payee) => {{
  clickPayee(els.flaggedTable, group, payee);
  return {{filter: transactionFilter, count: els.transactionCount.textContent,
    dates: datesOf(els.transactionTable.innerHTML)}};
}};
const vehicle = click('vehicle_financing', 'FABRICATED AUTO FINANCE');
console.log(JSON.stringify({{panel, vehicle, premium: click('premium_financing', 'FABRICATED PREMIUM FINANCE')}}));
""")
    [vehicle] = [row for row in result["panel"] if "FABRICATED AUTO FINANCE" in row]
    [premium] = [row for row in result["panel"] if "FABRICATED PREMIUM FINANCE" in row]
    # The ledger shows exactly the rows the panel counted, across both statements: never the duplicate, never the
    # other groups' payees, never the credit.
    assert result["vehicle"] == {"filter": "flagged:vehicle_financing",
                                 "count": f"{vehicle[2]} FABRICATED AUTO FINANCE",
                                 "dates": ["2031-01-24", "2031-02-24"]}
    assert vehicle[2] == "2"
    # Premium financing keys on flagged_group: its rows stay insurance, and the plain insurer's row is left out.
    assert result["premium"] == {"filter": "flagged:premium_financing",
                                 "count": f"{premium[2]} FABRICATED PREMIUM FINANCE",
                                 "dates": ["2031-02-04", "2031-02-18"]}
    assert (premium[0], premium[2]) == ("Premium financing", "2")
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider -k "package_panel or refused_its_currency or package_without_flagged or package_payee_click"`

Expected: 5 FAIL. The package page still shows the empty statement row that `setInitialState` drew.
- The first two tests fail on their rows (`AssertionError: assert [['No flagged...ments here.']] == [[...`), because the drawn row is the "No flagged payments" row.
- The `server-before-flagged-positions` case fails on its rows, because the drawn row reads "No flagged payments", not "Not available".
- The `no-ticked-group-paid` case fails on `colspan="6"`, because the drawn row has `colspan="5"`.
- The payee-click test fails with `ValueError: not enough values to unpack (expected 1, got 0)`, because the panel lists no payee.

- [ ] **Step 3: Implement.** Edit `webapp/static/app.js`, in `renderPackageTables`. Find:

```js
  renderInsurance(insuranceProviders, currency);
  renderRevenueEvidence(pkg.totals || {}, currency);
```

Replace with:

```js
  renderInsurance(insuranceProviders, currency);
  renderFlaggedPositions(pkg.flagged_positions, currency, true);
  renderRevenueEvidence(pkg.totals || {}, currency);
```

- [ ] **Step 4: Run the tests and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 15 passed.

Then run DASHBOARD GUARDS. Expected: no failures. `test_dashboard_no_longer_hardcodes_usd_for_the_package_view` still holds.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: Flagged positions panel on the package page with its Statements column"
```

---

### Task 6: The panel in the statement window

**Files:**
- Modify `webapp/static/app.js`:
  - `els` (after line 111);
  - `openStatementModal`, the loading block at 3240-3249 and the error block at 3299-3308;
  - `renderStatementModal`, the clears at 3358 and 3387 and the render before 3472;
  - after the `flaggedTable` listener from Task 4.
- Modify `webapp/templates/index.html`: after the `.modal-detail-grid` closing at line 1532.
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes:
  - `flaggedPositionEntries` and `flaggedPositionRowsHtml` from Task 3, including the "Not available" row for an account that publishes no flagged positions;
  - `detection.flagged_positions` of the window's account (C5);
  - `lenderEvidenceSelection`, `renderModalTransactions` and the `flagged:<group>` filter (Task 4).
- Produces:
  - `<tbody id="statementModalFlagged">` and `els.statementModalFlagged`. This id is S4-local: C8 names no id for the window's table.
  - A payee click in the window sets `modalTransactionFilter` and `modalTransactionEntityFilter`.
  - The window shows no outdated-rules notice. A statement analysed before flagged positions existed publishes no `detection.flagged_positions`, so its window panel draws the "Not available" row, which says to re-analyze (Self-Review, ambiguity 3).

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 6: the panel in the statement window

@needs_node
def test_the_statement_window_shows_the_flagged_positions_and_a_payee_click_filters_its_ledger():
    result = run_dashboard(CELLS + ROWS + PAYEE_CLICK + _serve(m=_statement(), old=_statement(positions=None)) + """
openStatementModal('m');
const loading = els.statementModalFlagged.innerHTML;
await settle();
const rows = cells(els.statementModalFlagged.innerHTML);
clickPayee(els.statementModalFlagged, 'mortgages', 'FABRICATED MORTGAGE CO');
const filtered = {filter: modalTransactionFilter, count: els.statementModalTransactionCount.textContent,
  dates: datesOf(els.statementModalTransactions.innerHTML)};
openStatementModal('old'); await settle();
const old = cells(els.statementModalFlagged.innerHTML);
openStatementModal('gone'); await settle();
console.log(JSON.stringify({loading, rows, filtered, old, failed: els.statementModalFlagged.innerHTML}));
""")
    assert "<strong>Loading</strong>" in result["loading"]
    assert result["rows"] == [
        ["Credit cards", "Credit cards", "1", "CA$300.00", "Single payment"],
        ["Mortgages", "FABRICATED MORTGAGE CO", "2", "CA$2,400.00", "Every two weeks2031-03-03 to 2031-03-17"],
    ]
    assert result["filtered"] == {"filter": "flagged:mortgages", "count": "2 FABRICATED MORTGAGE CO",
                                  "dates": ["2031-03-03", "2031-03-17"]}
    # Saved before flagged positions existed: the window says so, never that no ticked group was paid.
    assert result["old"] == [[NOT_AVAILABLE]]
    assert "<strong>Unable to load statement</strong>" in result["failed"]


def test_the_statement_window_has_its_own_flagged_table():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    modal = html[html.index('id="statementModalBackdrop"'):]
    table = modal[:modal.index('<tbody id="statementModalFlagged">')]
    table = table[table.rindex("<table"):]
    assert re.findall(r"<th[^>]*>([^<]*)</th>", table) == ["Group", "Payee", "Count", "Total", "Cadence"]
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider -k statement_window`

Expected: 2 FAIL.
- The first fails with `TypeError: Cannot read properties of undefined (reading 'innerHTML')`, because `els.statementModalFlagged` does not exist.
- The second fails with `ValueError: substring not found`.

- [ ] **Step 3: Implement.**

Edit `webapp/static/app.js`. Find:

```js
  statementModalInsurance: document.getElementById("statementModalInsurance"),
```

Replace with:

```js
  statementModalInsurance: document.getElementById("statementModalInsurance"),
  statementModalFlagged: document.getElementById("statementModalFlagged"),
```

Edit `webapp/static/app.js`. This is the loading placeholders in `openStatementModal`. Find:

```js
        <td>${glassChip("INS", "Pending", "blue")}</td>
      </tr>
    `;
  }
```

Replace with:

```js
        <td>${glassChip("INS", "Pending", "blue")}</td>
      </tr>
    `;
  }
  if (els.statementModalFlagged) {
    els.statementModalFlagged.innerHTML = `
      <tr>
        <td colspan="5"><strong>Loading</strong></td>
      </tr>
    `;
  }
```

Edit `webapp/static/app.js`. This is the failure placeholders in `openStatementModal`. Find:

```js
            <td>${glassChip("INS", "Review", "amber")}</td>
          </tr>
        `;
      }
```

Replace with:

```js
            <td>${glassChip("INS", "Review", "amber")}</td>
          </tr>
        `;
      }
      if (els.statementModalFlagged) {
        els.statementModalFlagged.innerHTML = `
          <tr>
            <td colspan="5"><strong>Unable to load statement</strong></td>
          </tr>
        `;
      }
```

Edit `webapp/static/app.js` with **`replace_all: true`**. The text occurs exactly twice: in the unverified-main path and in the no-account path of `renderStatementModal`. Find:

```js
    els.statementModalInsurance.innerHTML = "";
```

Replace with:

```js
    els.statementModalInsurance.innerHTML = "";
    els.statementModalFlagged.innerHTML = "";
```

Edit `webapp/static/app.js`, in `renderStatementModal`. Find:

```js
  if (els.statementModalRevenue) {
    els.statementModalRevenue.innerHTML = revenueEvidenceRowsHtml(metrics, currency, true);
```

Replace with:

```js
  if (els.statementModalFlagged) {
    els.statementModalFlagged.innerHTML = flaggedPositionRowsHtml(
      flaggedPositionEntries(detection.flagged_positions), currency, false);
  }
  if (els.statementModalRevenue) {
    els.statementModalRevenue.innerHTML = revenueEvidenceRowsHtml(metrics, currency, true);
```

Edit `webapp/static/app.js`. This is the end of the `flaggedTable` listener from Task 4. Find:

```js
    setTransactionFilterButtons("[data-transaction-filter]", "flagged");
    renderMainTransactions();
    els.transactionCard?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}
```

Replace with:

```js
    setTransactionFilterButtons("[data-transaction-filter]", "flagged");
    renderMainTransactions();
    els.transactionCard?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}
if (els.statementModalFlagged) {
  els.statementModalFlagged.addEventListener("click", (event) => {
    const selection = lenderEvidenceSelection(event);
    if (!selection) return;
    modalTransactionFilter = selection.filter;
    modalTransactionEntityFilter = selection.entity;
    setTransactionFilterButtons("[data-modal-transaction-filter]", "flagged");
    renderModalTransactions();
    els.statementModalTransactions?.closest(".modal-panel")?.scrollIntoView({ block: "start" });
  });
}
```

Edit `webapp/templates/index.html`. Find:

```html
              <tbody id="statementModalInsurance"></tbody>
            </table>
          </div>
        </section>
      </div>
```

Replace with:

```html
              <tbody id="statementModalInsurance"></tbody>
            </table>
          </div>
        </section>
      </div>
      <section class="panel modal-panel">
        <div class="panel-head"><h3>Flagged positions</h3></div>
        <div class="table-wrap">
          <table class="data-table flagged-table">
            <thead>
              <tr>
                <th>Group</th>
                <th>Payee</th>
                <th>Count</th>
                <th>Total</th>
                <th>Cadence</th>
              </tr>
            </thead>
            <tbody id="statementModalFlagged"></tbody>
          </table>
        </div>
      </section>
```

- [ ] **Step 4: Run the tests and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 17 passed.

Then run DASHBOARD GUARDS. Expected: no failures. This includes `tests/test_webapp_review_ui.py::test_the_statement_window_of_a_package_row_shows_and_reviews_that_account`.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js webapp/templates/index.html tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: Flagged positions in the statement window"
```

---

### Task 7: The Settings section and its switches, loaded from the server

**Files:**
- Modify `webapp/static/app.js`:
  - `els` (after line 56);
  - `loadSettings` (3982-3998);
  - after `refreshShownResults` (4000-4006);
  - the startup calls (4457-4458).
- Modify `webapp/templates/index.html`:
  - a new section between line 1418 (the end of Analysis) and line 1419 (Statements);
  - CSS after line 764.
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes:
  - `GET /api/settings`, which returns `{"settings": {...}}` with every key in `FLAG_SETTING_KEYS` (C7). A missing key counts as on (C6).
  - `FLAG_GROUP_LABELS` from Task 3.
- Produces:
  - The markup `#flagSettingsSection`, `#flagSettingsList` and `#flagSettingsStatus` (C8), and `#flagSettingsHelp`.
  - `els.flagSettingsList` and `els.flagSettingsStatus`.
  - `renderFlagSettings(settings, disabled)` (C8). Each input carries `data-flag-setting="flag_<group>"`, `id="flagSetting-<group>"` and `role="switch"`.
  - `flagSettingKey(group) -> "flag_<group>"`.
  - `setFlagSettingsStatus(message, error)`.
  - The module state `flagSettingsSaved` (object) and `flagSettingsBusy` (boolean).

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 7: the Settings switches

GROUP_KEYS = ["alternative_positions", "lines_of_credit", "credit_cards", "vehicle_financing", "bank_loans",
              "mortgages", "leases_rentals", "personal_loans", "floor_plan", "factoring", "premium_financing"]

SWITCHES = r"""
const switches = () => [...els.flagSettingsList.innerHTML.matchAll(
  /<input type="checkbox" role="switch" id="flagSetting-([a-z_]+)" data-flag-setting="([^"]+)"([^>]*)>/g)]
  .map((m) => ({group: m[1], key: m[2], checked: / checked/.test(m[3]), disabled: / disabled/.test(m[3])}));
"""


def _settings(**overrides):
    """GET/POST /api/settings's `settings` (C7): every flag key on unless overridden."""
    return {"nsf_carry_over": False, **{f"flag_{group}": True for group in GROUP_KEYS}, **overrides}


def _answer(url, answer):
    return f"FAKE_RESPONSES[{json.dumps(url)}] = {json.dumps(answer)};\n"


def test_the_flag_settings_sit_between_analysis_and_statements_with_their_own_status_line():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert html.index('id="analysisSettingsTitle"') < html.index('id="flagSettingsSection"') \
        < html.index('id="statementsSettingsTitle"')
    section = html[html.index('id="flagSettingsSection"'):]
    section = section[:section.index("</section>")]
    assert "Flagged positions</h2>" in section and 'id="flagSettingsList"' in section
    assert '<p class="setting-status" id="flagSettingsStatus" role="status" aria-live="polite"></p>' in section
    # The NSF switch keeps its own line.
    assert html.count('id="settingsStatus"') == 1 and 'id="settingsStatus"' not in section


@needs_node
def test_the_switches_start_held_and_follow_the_saved_settings_once_loaded():
    result = run_dashboard(SWITCHES + """
const atStart = switches();
""" + _answer("/api/settings", {"json": {"settings": _settings(flag_credit_cards=False)}}) + """
loadSettings();
const loading = switches();
await settle();
console.log(JSON.stringify({atStart, loading, loaded: switches(), html: els.flagSettingsList.innerHTML}));
""")
    assert [switch["group"] for switch in result["atStart"]] == GROUP_KEYS
    assert all(switch["key"] == f"flag_{switch['group']}" for switch in result["atStart"])
    assert all(switch["checked"] and switch["disabled"] for switch in result["atStart"] + result["loading"])
    assert [(switch["group"], switch["checked"], switch["disabled"]) for switch in result["loaded"]] == \
        [(group, group != "credit_cards", False) for group in GROUP_KEYS]
    for label in ("Alternative positions", "Lines of credit", "Vehicle loans &amp; leases", "Leases &amp; rentals",
                  "Floor plan", "Factoring", "Premium financing"):
        assert f">{label}</label>" in result["html"]
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider -k "flag_settings_sit or switches_start"`

Expected: 2 FAIL.
- The static test fails with `ValueError: substring not found` (`id="flagSettingsSection"`).
- The node test fails with `TypeError: Cannot read properties of undefined (reading 'innerHTML')`, because `els.flagSettingsList` does not exist.

- [ ] **Step 3: Implement.**

Edit `webapp/static/app.js`. Find:

```js
  settingsStatus: document.getElementById("settingsStatus"),
```

Replace with:

```js
  settingsStatus: document.getElementById("settingsStatus"),
  flagSettingsList: document.getElementById("flagSettingsList"),
  flagSettingsStatus: document.getElementById("flagSettingsStatus"),
```

Edit `webapp/static/app.js`. Find:

```js
function loadSettings() {
  els.nsfCarryOverToggle.disabled = true;
  fetch("/api/settings")
```

Replace with:

```js
function loadSettings() {
  els.nsfCarryOverToggle.disabled = true;
  renderFlagSettings(flagSettingsSaved, true);
  fetch("/api/settings")
```

Edit `webapp/static/app.js`. Find:

```js
      renderNsfExample(els.nsfCarryOverToggle.checked);
      setSettingsStatus("");
    })
    .catch((error) => {
      setSettingsStatus(error.message || String(error), true);
    });
}
```

Replace with:

```js
      renderNsfExample(els.nsfCarryOverToggle.checked);
      setSettingsStatus("");
      flagSettingsSaved = settings;
      // A switch still being saved keeps the group held; its own save draws the group again when it settles.
      renderFlagSettings(settings, flagSettingsBusy);
      if (!flagSettingsBusy) setFlagSettingsStatus("");
    })
    .catch((error) => {
      setSettingsStatus(error.message || String(error), true);
      setFlagSettingsStatus(error.message || String(error), true);
    });
}
```

Edit `webapp/static/app.js`. This is the end of `refreshShownResults`. Find:

```js
  else if (currentJobId && (currentAnalysis || currentDocument)) loadResults(currentJobId, { reveal: false });
}
```

Replace with:

```js
  else if (currentJobId && (currentAnalysis || currentDocument)) loadResults(currentJobId, { reveal: false });
}

/* Flagged positions: one switch per group (FLAG_GROUP_LABELS), each its own settings key, flag_<group>, on by default.
   The server applies them when it serves an analysis; a switch only hides or shows its group. */
let flagSettingsSaved = {};
let flagSettingsBusy = false;

function flagSettingKey(group) {
  return `flag_${group}`;
}

// A key the settings lack (a server older than the flags) reads as on, the default.
function renderFlagSettings(settings = {}, disabled = false) {
  if (!els.flagSettingsList) return;
  els.flagSettingsList.innerHTML = Object.entries(FLAG_GROUP_LABELS).map(([group, label]) => {
    const key = flagSettingKey(group);
    const id = `flagSetting-${group}`;
    return `
      <div class="setting-row">
        <label class="setting-title" for="${id}">${escapeHtml(label)}</label>
        <span class="switch">
          <input type="checkbox" role="switch" id="${id}" data-flag-setting="${key}" aria-describedby="flagSettingsHelp"${
            settings[key] === false ? "" : " checked"}${disabled ? " disabled" : ""}>
          <span class="switch-track" aria-hidden="true"></span>
        </span>
      </div>
    `;
  }).join("");
}

function setFlagSettingsStatus(message, error = false) {
  if (!els.flagSettingsStatus) return;
  els.flagSettingsStatus.textContent = message;
  if (error) els.flagSettingsStatus.setAttribute("data-state", "error");
  else els.flagSettingsStatus.removeAttribute("data-state");
}
```

Edit `webapp/static/app.js`. This is the startup at the end of the file. Find:

```js
setInitialState();
renderNsfExample(false);
```

Replace with:

```js
setInitialState();
renderNsfExample(false);
renderFlagSettings({}, true);
```

Edit `webapp/templates/index.html`. Find:

```html
        <section class="settings-section" aria-labelledby="statementsSettingsTitle">
```

Replace with:

```html
        <section class="settings-section" id="flagSettingsSection" aria-labelledby="flagSettingsTitle">
          <h2 class="eyebrow" id="flagSettingsTitle">Flagged positions</h2>
          <div class="panel">
            <p class="setting-help flag-settings-help" id="flagSettingsHelp">
              A ticked group is flagged on statements and packages: listed in the Flagged positions panel, tagged in the
              transactions and written to the downloads. A flagged group never counts as a lender and never changes
              withholding or the package decision; unticking it only hides it.
            </p>
            <!-- One switch per group, drawn by renderFlagSettings (webapp/static/app.js). -->
            <div id="flagSettingsList"></div>
            <div class="flag-settings-foot">
              <p class="setting-status" id="flagSettingsStatus" role="status" aria-live="polite"></p>
            </div>
          </div>
        </section>
        <section class="settings-section" aria-labelledby="statementsSettingsTitle">
```

Edit `webapp/templates/index.html`. Find:

```css
  .setting-status[data-state="error"]::before { background: var(--red); }
```

Replace with:

```css
  .setting-status[data-state="error"]::before { background: var(--red); }
  .flag-settings-help { margin: 0; padding: 16px 20px 4px; }
  .flag-settings-foot { display: flex; align-items: center; min-height: 44px; padding: 0 20px; border-top: 1px solid var(--border); background: var(--inset); }
```

- [ ] **Step 4: Run the tests and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 19 passed.

Then run DASHBOARD GUARDS. Expected: no failures. `test_the_page_carries_the_branch_s_controls_in_the_new_shell` still finds `allAccountsToggle` and `Statements</h2>`.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js webapp/templates/index.html tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: Flagged positions switches in Settings, loaded from the server"
```

---

### Task 8: Saving a switch: one key, group held, own status line, refresh

**Files:**
- Modify `webapp/static/app.js`:
  - after `setFlagSettingsStatus` (Task 7);
  - after the NSF change handler (ends at 4036).
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes:
  - `POST /api/settings` with `{"flag_<group>": bool}`. The route is unchanged, and it merges one key.
  - `responseJson(response)` (line 867) and `refreshShownResults()` (line 4000);
  - `ownKey`, `flagGroupLabel` and `FLAG_GROUP_LABELS` (Task 3);
  - `renderFlagSettings`, `setFlagSettingsStatus`, `flagSettingsSaved` and `flagSettingsBusy` (Task 7).
- Produces:
  - `flagGroupOfSetting(key) -> string|null`. It returns the group for a key `flag_<group>` whose group `FLAG_GROUP_LABELS` defines itself, and `null` otherwise (`flag_constructor` included).
  - `saveFlagSetting(key, wanted)`.
  - One delegated `change` listener on `els.flagSettingsList`.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 8: saving a switch

TOGGLE = """
const toggle = (key, on) => {
  const box = fakeElement('switch'); box.checked = on; box.attributes['data-flag-setting'] = key; box.closest = () => box;
  els.flagSettingsList.dispatch('change', {target: box});
};
const posts = () => REQUESTS.filter((request) => request.method === 'POST')
  .map((request) => [request.url, JSON.parse(request.body)]);
"""


def _settings_page_with(job_id, payload):
    """A statement open, then the Settings page loaded with every flag on."""
    return (SWITCHES + TOGGLE + _load(job_id, payload)
            + _answer("/api/settings", {"json": {"settings": _settings()}})
            + "loadSettings(); await settle(); REQUESTS.length = 0; FETCHED.length = 0;\n")


@needs_node
def test_a_change_saves_its_key_alone_holds_the_group_and_refreshes_what_is_open():
    result = run_dashboard(_settings_page_with("s", _statement())
                           + _answer("/api/settings", {"json": {"settings": _settings(flag_factoring=False)}}) + """
toggle('flag_factoring', false);
const saving = {switches: switches(), status: els.flagSettingsStatus.textContent};
await settle(); await settle();
console.log(JSON.stringify({saving, posts: posts(), fetched: FETCHED.slice(), saved: switches(),
  status: els.flagSettingsStatus.textContent, state: els.flagSettingsStatus.getAttribute('data-state'),
  nsfStatus: els.settingsStatus.textContent}));
""")
    saving = result["saving"]
    assert all(switch["disabled"] for switch in saving["switches"]) and saving["status"] == "Saving..."
    assert [switch["checked"] for switch in saving["switches"]] == [group != "factoring" for group in GROUP_KEYS]
    assert result["posts"] == [["/api/settings", {"flag_factoring": False}]]
    assert "/analysis/s" in result["fetched"]
    assert [(switch["checked"], switch["disabled"]) for switch in result["saved"]] == \
        [(group != "factoring", False) for group in GROUP_KEYS]
    # Worded to read right for every label, plural ("Mortgages") or not ("Factoring", "Floor plan").
    assert result["status"] == "Saved. Factoring: no longer flagged." and result["state"] is None
    assert result["nsfStatus"] == ""


@needs_node
def test_a_refused_save_puts_the_switch_back_and_says_why_on_its_own_line():
    result = run_dashboard(_settings_page_with("s", _statement())
                           + _answer("/api/settings", {"status": 503, "json": {"error": "fabricated save failure"}})
                           + """
toggle('flag_bank_loans', false);
await settle(); await settle();
console.log(JSON.stringify({posts: posts(), fetched: FETCHED.slice(), saved: switches(),
  status: els.flagSettingsStatus.textContent, state: els.flagSettingsStatus.getAttribute('data-state'),
  nsfStatus: els.settingsStatus.textContent}));
""")
    assert result["posts"] == [["/api/settings", {"flag_bank_loans": False}]]
    assert not any(url.startswith("/analysis/") for url in result["fetched"])
    assert all(switch["checked"] and not switch["disabled"] for switch in result["saved"])
    assert result["status"] == "fabricated save failure" and result["state"] == "error"
    assert result["nsfStatus"] == ""


@needs_node
def test_a_second_change_while_one_is_saving_is_not_sent():
    result = run_dashboard(_settings_page_with("s", _statement())
                           + _answer("/api/settings", {"json": {"settings": _settings(flag_mortgages=False)}}) + """
toggle('flag_mortgages', false);
toggle('flag_credit_cards', false);
await settle(); await settle();
console.log(JSON.stringify({posts: posts()}));
""")
    assert result["posts"] == [["/api/settings", {"flag_mortgages": False}]]
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider -k "change_saves or refused_save or second_change"`

Expected: 3 FAIL, because no `change` listener is bound yet:
- the first test fails on its first assertion: the group is not held;
- the other two fail on `posts` being `[]` (`AssertionError: assert [] == [['/api/settings', ...]]`).

- [ ] **Step 3: Implement.**

Edit `webapp/static/app.js`. This is the end of `setFlagSettingsStatus` from Task 7. Find:

```js
  if (error) els.flagSettingsStatus.setAttribute("data-state", "error");
  else els.flagSettingsStatus.removeAttribute("data-state");
}
```

Replace with:

```js
  if (error) els.flagSettingsStatus.setAttribute("data-state", "error");
  else els.flagSettingsStatus.removeAttribute("data-state");
}

function flagGroupOfSetting(key) {
  const group = String(key || "").replace(/^flag_/, "");
  return ownKey(FLAG_GROUP_LABELS, group) ? group : null;
}

// Saves one switch: that key alone (the server merges it), with the whole group held until the answer, so two quick
// changes never race two refreshes. The open statement or package is fetched again, as the server now serves it.
function saveFlagSetting(key, wanted) {
  const group = flagGroupOfSetting(key);
  if (!group || flagSettingsBusy) return;
  flagSettingsBusy = true;
  renderFlagSettings({ ...flagSettingsSaved, [key]: wanted }, true);
  setFlagSettingsStatus("Saving...");
  fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ [key]: wanted }),
  })
    .then((response) => responseJson(response).then((payload) => ({ response, payload })))
    .then(({ response, payload }) => {
      if (!response.ok || !payload.settings) throw new Error(payload.error || `Save failed (${response.status})`);
      flagSettingsSaved = payload.settings;
      const shown = payload.settings[key] !== false;
      setFlagSettingsStatus(`Saved. ${flagGroupLabel(group)}: ${shown ? "flagged" : "no longer flagged"}.`);
      refreshShownResults();
    })
    .catch((error) => {
      setFlagSettingsStatus(error.message || String(error), true);
    })
    .finally(() => {
      flagSettingsBusy = false;
      // Drawn from what the server holds, so a refused save puts the switch back.
      renderFlagSettings(flagSettingsSaved, false);
      document.getElementById(`flagSetting-${group}`)?.focus();
    });
}
```

Edit `webapp/static/app.js`. This is the end of the NSF change handler. Find:

```js
    .finally(() => {
      els.nsfCarryOverToggle.disabled = false;
    });
});
```

Replace with:

```js
    .finally(() => {
      els.nsfCarryOverToggle.disabled = false;
    });
});

els.flagSettingsList?.addEventListener("change", (event) => {
  const box = event.target instanceof Element ? event.target.closest("[data-flag-setting]") : null;
  if (box) saveFlagSetting(box.getAttribute("data-flag-setting"), box.checked === true);
});
```

- [ ] **Step 4: Run the tests and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 22 passed.

Then run DASHBOARD GUARDS. Expected: no failures. `test_a_withheld_statement_counts_as_open_and_is_fetched_again_by_a_settings_change` still passes.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: save one flag switch per change, group held, own status line, refresh what is open"
```

---

### Task 9: Unticking the group the ledger is filtered to resets the filter

**Files:**
- Modify `webapp/static/app.js`: before `flagGroupOfSetting`, and the success branch of `saveFlagSetting` (both Task 8).
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes: `flaggedFilterGroup` (Task 4), `transactionFilter`, `transactionEntityFilter` and `setTransactionFilterButtons`.
- Produces: `releaseFlagFilter(group)`.
  - When the ledger filter is `flagged:<group>`, it goes back to `"all"` with no entity.
  - The plain "Flagged" pill filter and any other group's filter are left alone.

- [ ] **Step 1: Write the tests.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 9: unticking the group being filtered

def _unticked(group):
    """The statement as the server serves it once `group` is unticked (C6): its rows no longer shown as flagged, its
    positions gone."""
    ledger = [{**row, "classification": {**row["classification"], "flag_shown": False}}
              if row["classification"]["flagged_group"] == group else row for row in LEDGER]
    return _statement(positions=[entry for entry in POSITIONS if entry["group"] != group], ledger=ledger)


@needs_node
def test_unticking_the_group_the_ledger_is_filtered_to_shows_every_row_again():
    result = run_dashboard(ROWS + PAYEE_CLICK + _settings_page_with("s", _statement()) + """
clickPayee(els.flaggedTable, 'mortgages', 'FABRICATED MORTGAGE CO');
const before = {filter: transactionFilter, count: els.transactionCount.textContent};
""" + _answer("/api/settings", {"json": {"settings": _settings(flag_mortgages=False)}})
        + _answer("/analysis/s", {"json": {"analysis": _unticked("mortgages"), "analysis_error": None}}) + """
toggle('flag_mortgages', false);
await settle(); await settle();
console.log(JSON.stringify({before, after: {filter: transactionFilter, entity: transactionEntityFilter,
  count: els.transactionCount.textContent, dates: datesOf(els.transactionTable.innerHTML)}}));
""")
    assert result["before"] == {"filter": "flagged:mortgages", "count": "2 FABRICATED MORTGAGE CO"}
    assert result["after"] == {"filter": "all", "entity": None, "count": "6 transactions",
                               "dates": ["2031-03-03", "2031-03-05", "2031-03-17", "2031-03-17", "2031-03-20",
                                         "2031-03-24"]}


@needs_node
def test_unticking_another_group_keeps_the_filter():
    result = run_dashboard(ROWS + PAYEE_CLICK + _settings_page_with("s", _statement()) + """
clickPayee(els.flaggedTable, 'credit_cards', 'Credit cards');
""" + _answer("/api/settings", {"json": {"settings": _settings(flag_mortgages=False)}})
        + _answer("/analysis/s", {"json": {"analysis": _unticked("mortgages"), "analysis_error": None}}) + """
toggle('flag_mortgages', false);
await settle(); await settle();
console.log(JSON.stringify({filter: transactionFilter, count: els.transactionCount.textContent}));
""")
    assert result == {"filter": "flagged:credit_cards", "count": "1 Credit cards"}
```

- [ ] **Step 2: Run them.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider -k unticking`

Expected: 1 FAIL and 1 PASS.
- `test_unticking_the_group_the_ledger_is_filtered_to_shows_every_row_again` FAILS. The filter stays `flagged:mortgages` and the ledger shows "No rows matched this filter", so `dates` is `[None]`.
- `test_unticking_another_group_keeps_the_filter` already PASSES. It pins that only the unticked group's filter resets. Keep it.

- [ ] **Step 3: Implement.**

Edit `webapp/static/app.js`. Find:

```js
function flagGroupOfSetting(key) {
```

Replace with:

```js
// The ledger filtered to one flagged payee (a Flagged positions panel click) shows every row again once that payee's
// group is unticked: its rows are no longer flagged, so the filter would match none.
function releaseFlagFilter(group) {
  if (flaggedFilterGroup(transactionFilter) !== group) return;
  transactionFilter = "all";
  transactionEntityFilter = null;
  setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
}

function flagGroupOfSetting(key) {
```

Edit `webapp/static/app.js`. Find:

```js
      setFlagSettingsStatus(`Saved. ${flagGroupLabel(group)}: ${shown ? "flagged" : "no longer flagged"}.`);
      refreshShownResults();
```

Replace with:

```js
      setFlagSettingsStatus(`Saved. ${flagGroupLabel(group)}: ${shown ? "flagged" : "no longer flagged"}.`);
      if (!shown) releaseFlagFilter(group);
      refreshShownResults();
```

- [ ] **Step 4: Run the tests and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 24 passed.

Then run DASHBOARD GUARDS. Expected: no failures.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: unticking the flagged group being filtered resets the ledger filter"
```

---

### Task 10: The notice on a statement analysed with older lender rules

**Files:**
- Modify `webapp/static/app.js`:
  - `els` (line 121);
  - before `renderAnalysis` and its first lines (2271-2274, inside the accounts block that starts at 1612);
  - `renderUnverifiedMain` (1907-1911, in the same block), right after its `setInitialState()`;
  - `renderPackageAnalysis` (2891);
  - `setInitialState` (1146).
- Modify `webapp/templates/index.html`:
  - markup before line 1160, after the hero;
  - CSS at line 568.
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes:
  - the top-level `analysis_rules_outdated` of the served analysis (C6). A package defines none;
  - the existing test helpers `_document`, `_all_accounts` and `_select` of `tests/test_webapp_studio_views.py` (lines 46, 76 and 80): a statement whose main account was held, beside a verified savings account;
  - `_statement` and `PACKAGE` (Tasks 2 and 5).
- Produces:
  - The markup `#rulesOutdatedNotice` (C8), starting `hidden` and holding `#reanalyzeButton` (C8). S5 binds the click through `document.getElementById("reanalyzeButton")`. Neither plan adds `els.reanalyzeButton`.
  - `els.rulesOutdatedNotice`.
  - `syncRulesOutdatedNotice(report)`: the notice shows only when `report.analysis_rules_outdated === true`.
    - It is called from `renderAnalysis`, which every statement redraw goes through: `loadResults`, a review redraw, an account selection, and S5's re-render. A payload with no account to show (the `!published.length` return) syncs `null`: it draws no statement, so it keeps no notice.
    - `renderPackageAnalysis` and `setInitialState` hide it.
    - `renderUnverifiedMain` (a statement whose main account was not verified, its metrics withheld) calls `setInitialState()` first (app.js:1910), which hides the notice. So it syncs the notice again from its own report right after. Without that line, the notice would never show on a withheld statement, and S5's Re-analyze would be unreachable there.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 10: the outdated-rules notice

@needs_node
def test_the_notice_shows_only_on_a_statement_analysed_with_older_rules():
    document = {"document": {"account_count": 2}, "accounts": [_statement(), _statement()],
                "analysis_rules_outdated": True}
    # A payload with no account to show draws no statement (renderAnalysis's "published no account" path).
    empty = {"document": {"account_count": 1}, "accounts": [], "analysis_rules_outdated": True}
    result = run_dashboard(_serve(old=_statement(outdated=True), current=_statement(outdated=False),
                                  saved=_statement(), doc=document, empty=empty) + """
const atStart = els.rulesOutdatedNotice.hidden;
const open = async (id) => {
  currentJobId = id; currentJobIds = [id]; loadResults(id); await settle(); return els.rulesOutdatedNotice.hidden;
};
const old = await open('old'), current = await open('current'), saved = await open('saved'), doc = await open('doc');
await open('old');
const empty = await open('empty');
await open('old');
currentJobIds = ['a', 'b']; renderPackageAnalysis(""" + json.dumps({**PACKAGE, "analysis_rules_outdated": True}) + """);
console.log(JSON.stringify({atStart, old, current, saved, doc, empty, package: els.rulesOutdatedNotice.hidden}));
""")
    assert result == {"atStart": True, "old": False, "current": True, "saved": True, "doc": False, "empty": True,
                      "package": True}


@needs_node
def test_the_notice_stays_on_a_statement_whose_main_account_is_withheld():
    """Re-analysis concerns the whole saved statement, so the notice stays while the main account's metrics are
    withheld: with All accounts off, with it on, and once a verified account of the statement is picked."""
    from tests.test_webapp_studio_views import _all_accounts, _document, _select

    held = {**_document("held"), "analysis_rules_outdated": True}
    open_held = """
const state = () => ({withheld: els.resultsContent.classList.contains('is-withheld'),
  hidden: els.rulesOutdatedNotice.hidden});
currentJobId = 'held'; currentJobIds = ['held']; loadResults('held'); await settle();
const held = state();
"""
    off = run_dashboard(_all_accounts("off") + _serve(held=held) + open_held
                        + "console.log(JSON.stringify({held}));\n")
    on = run_dashboard(_all_accounts("on") + _serve(held=held) + open_held + _select(0)
                       + "console.log(JSON.stringify({held, picked: state()}));\n")
    assert off == {"held": {"withheld": True, "hidden": False}}
    assert on == {"held": {"withheld": True, "hidden": False}, "picked": {"withheld": False, "hidden": False}}


def test_the_notice_carries_its_words_and_the_re_analyze_button():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    notice = html[html.index('id="rulesOutdatedNotice"'):]
    notice = notice[:notice.index("</section>")]
    assert "Analysed with older lender rules" in notice and 'id="reanalyzeButton"' in notice
    assert notice.split(">")[0].rstrip().endswith("hidden")  # hidden until a served analysis says otherwise
    # The withheld view hides every other panel; the notice is exempt (the node test above shows it stays shown).
    assert ":not(.rules-outdated)" in html
```

- [ ] **Step 2: Run them and watch them fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider -k notice`

Expected: 3 FAIL.
- The two node tests fail with `TypeError: Cannot read properties of undefined (reading 'hidden')`, because `els.rulesOutdatedNotice` does not exist.
- The static test fails with `ValueError: substring not found`.

- [ ] **Step 3: Implement.**

Edit `webapp/static/app.js`. Find:

```js
  accountsPanel: document.getElementById("accountsPanel"),
};
```

Replace with:

```js
  accountsPanel: document.getElementById("accountsPanel"),
  rulesOutdatedNotice: document.getElementById("rulesOutdatedNotice"),
};
```

Edit `webapp/static/app.js`. Find:

```js
function renderAnalysis(report) {
  if (els.monthlyCard) els.monthlyCard.style.display = "none";
  const published = publishedAccounts(report);
  const roster = accountRoster(report);
```

Replace with:

```js
// A saved statement analysed with older lender rules says so (the server sets analysis_rules_outdated when it serves
// it), beside its Re-analyze button; a package or a statement of the current rules shows nothing. Kept in the block
// that tests/test_webapp_accounts_view.py runs with only the accounts panel: every element is looked up null-safe.
function syncRulesOutdatedNotice(report) {
  if (!els.rulesOutdatedNotice) return;
  els.rulesOutdatedNotice.hidden = !(report && report.analysis_rules_outdated === true);
}

function renderAnalysis(report) {
  if (els.monthlyCard) els.monthlyCard.style.display = "none";
  const published = publishedAccounts(report);
  const roster = accountRoster(report);
  // A payload with no account to show draws no statement, so it keeps no notice either.
  syncRulesOutdatedNotice(published.length ? report : null);
```

Edit `webapp/static/app.js`, in `renderUnverifiedMain`. Its `setInitialState()` hides the notice that `renderAnalysis` has just synced. Find:

```js
  const report = currentDocument;
  setInitialState();
  currentDocument = report;
```

Replace with:

```js
  const report = currentDocument;
  setInitialState();
  // setInitialState hid the notice; this statement's own analysis decides it. Re-analysis concerns the whole saved
  // statement, so the notice stays while the main account's metrics are withheld.
  syncRulesOutdatedNotice(report);
  currentDocument = report;
```

Edit `webapp/static/app.js`, in `renderPackageAnalysis`. Find:

```js
  hideAccountsPanel();
  els.resultsContent?.classList.remove("is-withheld");
  currentAnalysis = { package: pkg };
```

Replace with:

```js
  hideAccountsPanel();
  syncRulesOutdatedNotice(null);
  els.resultsContent?.classList.remove("is-withheld");
  currentAnalysis = { package: pkg };
```

Edit `webapp/static/app.js`, in `setInitialState`. Find:

```js
  hideAccountsPanel();
  if (els.transactionCard) els.transactionCard.style.display = "block";
  renderMetricSections(emptyMetricSections);
```

Replace with:

```js
  hideAccountsPanel();
  syncRulesOutdatedNotice(null);
  if (els.transactionCard) els.transactionCard.style.display = "block";
  renderMetricSections(emptyMetricSections);
```

Edit `webapp/templates/index.html`. Find:

```html
        <!-- The accounts of a statement that holds several: the main account first, the others with All accounts -->
```

Replace with:

```html
        <!-- A saved statement analysed with older lender rules (analysis_rules_outdated, set when it is served). -->
        <section class="panel rules-outdated single-only" id="rulesOutdatedNotice" aria-labelledby="rulesOutdatedTitle" hidden>
          <p class="rules-outdated-text">
            <strong id="rulesOutdatedTitle">Analysed with older lender rules.</strong>
            Its lenders and flagged positions follow the rules it was analysed with, not the current ones.
          </p>
          <button class="btn-quiet" type="button" id="reanalyzeButton">Re-analyze</button>
        </section>

        <!-- The accounts of a statement that holds several: the main account first, the others with All accounts -->
```

Edit `webapp/templates/index.html`. Find:

```css
  .results-content.is-withheld > :not(.hero):not(.accounts-panel):not(.summary-panel) { display: none !important; }
```

Replace with:

```css
  .results-content.is-withheld > :not(.hero):not(.accounts-panel):not(.summary-panel):not(.rules-outdated) { display: none !important; }
  .rules-outdated {
    display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px 16px; padding: 14px 20px;
    border-color: var(--amber); background: var(--amber-soft);
  }
  .rules-outdated[hidden] { display: none; }
  .rules-outdated-text { margin: 0; font-size: 13.5px; line-height: 1.55; color: var(--text); }
  .rules-outdated-text strong { font-weight: 600; }
```

- [ ] **Step 4: Run the tests and the guards.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 27 passed.

Then run DASHBOARD GUARDS. Expected: no failures. This matters most for:
- the extracted `renderAnalysis` in `tests/test_webapp_accounts_view.py::test_the_dashboard_says_the_idle_main_account_needs_review_over_the_active_accounts_figures`, which runs `syncRulesOutdatedNotice` with no `els.rulesOutdatedNotice`;
- the withheld-statement tests of `tests/test_webapp_studio_views.py` (for example `test_a_statement_whose_main_account_was_not_verified_withholds_every_metric_panel`), which go through the edited `renderUnverifiedMain`.

- [ ] **Step 5: Commit.**

```
git add webapp/static/app.js webapp/templates/index.html tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: notice and Re-analyze button on a statement analysed with older lender rules"
```

---

### Task 11: FLAG_GROUP_LABELS parity with analysis/flag_groups.py

**Precondition:**
- S1 is merged into `lender-detection`.
- Rebase first: `git rebase lender-detection`, run from `ld-s4-dashboard` with a clean tree.
- Confirm that `analysis/flag_groups.py` exists and defines `FLAG_GROUPS` (C1).
- If it does not exist, stop and report to the orchestrator. Nothing in this plan works around a missing C1.

**Files:**
- Test: `tests/test_webapp_flagged_dashboard.py` (append). No production change is expected.

**Interfaces:**
- Consumes:
  - C1 `FLAG_GROUPS`, a tuple of eleven `FlagGroup(state, key, setting, label)`, where `state` is `None` for premium financing only;
  - the literal `const FLAG_GROUP_LABELS = Object.freeze({ ... });` block in app.js (Task 3);
  - the `categories` map of `transactionCategory` in app.js (Task 1), whose entries are indented four spaces.
- Produces: a static parity guard. It needs no node, so CI runs it. It checks three things:
  - the keys, labels and order match;
  - every settings key is `flag_<key>`;
  - every group with a state has a tag, and premium financing is the only group without a state.

- [ ] **Step 1: Write the test.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 11: parity with analysis/flag_groups.py

def _js_flag_group_labels():
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    block = source[source.index("const FLAG_GROUP_LABELS = Object.freeze({"):]
    block = block[:block.index("});")]
    return re.findall(r'^\s*([a-z_]+): "([^"]+)",$', block, re.M)


def test_the_dashboard_labels_every_flag_group_as_the_analysis_does():
    from analysis.flag_groups import FLAG_GROUPS

    assert _js_flag_group_labels() == [(group.key, group.label) for group in FLAG_GROUPS]
    # app.js names each switch's settings key flag_<group key> (flagSettingKey).
    assert all(group.setting == f"flag_{group.key}" for group in FLAG_GROUPS)
    # Every group that is a classification state has its own tag (transactionCategory, Task 1). Premium financing is
    # the one group without a state: its rows stay insurance and keep the Insurance tag (Tasks 1, 2 and 4).
    source = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")
    assert [group.key for group in FLAG_GROUPS if group.state is None] == ["premium_financing"]
    assert [group.state for group in FLAG_GROUPS
            if group.state is not None and f"\n    {group.state}: {{ label: " not in source] == []
```

- [ ] **Step 2: Run it.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py::test_the_dashboard_labels_every_flag_group_as_the_analysis_does -q -p no:cacheprovider`

Expected: PASS. Task 3's constant and Task 1's tags were written from C1.
- If it FAILS, compare both sides with C1's `FLAG_GROUPS` literal in the master plan.
  - If `webapp/static/app.js` departs from C1, fix `FLAG_GROUP_LABELS` in app.js to match C1, re-run, and report the drift to the orchestrator.
  - If `analysis/flag_groups.py` departs from C1, stop. Do not edit it: it is S1's file, and this branch touches only three files. Report the drift to the orchestrator and wait.

- [ ] **Step 3: Prove the guard bites, then restore.**
  1. In `webapp/static/app.js`, change `  mortgages: "Mortgages",` to `  mortgages: "Mortgage",`.
  2. Run the command from Step 2. Expected: FAIL with `('mortgages', 'Mortgage') != ('mortgages', 'Mortgages')` in the list diff.
  3. Revert the edit (`git checkout -- webapp/static/app.js`) and run the command again. Expected: PASS.
  4. In `webapp/static/app.js`, change `    factoring: { label: entity ?` to `    factoringX: { label: entity ?`.
  5. Run the command from Step 2. Expected: FAIL with `assert ['factoring'] == []`.
  6. Revert the edit (`git checkout -- webapp/static/app.js`) and run the command again. Expected: PASS.

- [ ] **Step 4: Run the guards.** Run DASHBOARD GUARDS. Expected: no failures.

- [ ] **Step 5: Commit.**

```
git add tests/test_webapp_flagged_dashboard.py
git commit -m "tests: dashboard flag group labels match analysis/flag_groups.py"
```

---

### Task 12: Browsers fetch the new script

**Files:**
- Modify: `webapp/templates/index.html:1577`.
- Test: `tests/test_webapp_flagged_dashboard.py` (append).

**Interfaces:**
- Consumes: nothing.
- Produces: `<script src="/static/app.js?v=lender-detection-1">`, so a browser holding the cached `statement-studio-1` script loads the new one.

- [ ] **Step 1: Write the failing test.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 12: browsers fetch the new script

def test_the_page_asks_browsers_for_the_new_script():
    html = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
    assert '<script src="/static/app.js?v=lender-detection-1"></script>' in html
```

- [ ] **Step 2: Run it and watch it fail.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py::test_the_page_asks_browsers_for_the_new_script -q -p no:cacheprovider`

Expected: FAIL. The page still loads `app.js?v=statement-studio-1`.

- [ ] **Step 3: Implement.** Edit `webapp/templates/index.html`. Find:

```html
<script src="/static/app.js?v=statement-studio-1"></script>
```

Replace with:

```html
<script src="/static/app.js?v=lender-detection-1"></script>
```

- [ ] **Step 4: Run the tests.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: all passed. That is 29, or 28 if Task 11 waits for S1.

- [ ] **Step 5: Commit.**

```
git add webapp/templates/index.html tests/test_webapp_flagged_dashboard.py
git commit -m "dashboard: new app.js cache key for the lender detection release"
```

---

### Task 13: End to end on a served fabricated statement

**Precondition:**
- S2 and S3 are merged into `lender-detection`.
- Rebase: `git rebase lender-detection`.
- Confirm three things:
  - `analysis/flagged_view.py` exists;
  - `webapp.settings.DEFAULTS` holds `flag_mortgages` and `flag_premium_financing`;
  - `analysis.transaction_classifier` defines `PREMIUM_FINANCE_ALIASES` (C2's table, which S2's task "Premium financing stays insurance and carries its flag" imports into the classifier at module level for the insurance rule; `_insurance_registry_match` reads it at call time, so a `monkeypatch` of the module attribute reaches the rule).
- If any of them is missing, stop and report to the orchestrator.

**Files:**
- Test: `tests/test_webapp_flagged_dashboard.py` (append). No production change is expected.

**Interfaces:**
- Consumes:
  - S2's classifier and payload: spec §4.3 step 8 makes a `MORTGAGE` descriptor with no named payee `mortgage`, and the payload follows C5;
  - S2's premium-financing rule (C4; S2 plan, the task "Premium financing stays insurance and carries its flag"): an insurance row whose insurer match is a `PREMIUM_FINANCE_ALIASES` payee keeps `classification="insurance"` and `canonical_entity=<the premium-finance entity>`, and a debit gets `flagged_group="premium_financing"` and `contributes_to_flagged_totals`. The test routes a fabricated premium financier into that table with `monkeypatch`, as S2's own fixture `fake_premium_finance` does (`tests/flag_group_fixtures.py`), so no real payee name enters the test;
  - S3's `_displayed(analysis)` (C6) and `save_settings(data_dir, updates)` (C7), which merges its updates into the saved settings (`webapp/settings.py:82`);
  - `tests.test_webapp_studio_views._report`;
  - `ROWS` (Task 2), `NO_FLAGGED_PAYMENTS` (Task 3) and `PAYEE_CLICK` (Task 4).
- Produces: an integration pin that the contract the dashboard was built on is the one the server serves, for a state group (mortgages) and for premium financing, the one group without a state. It turns the assumption of Self-Review ambiguity 9 into a test: the served `canonical_entity` of a premium-financing row is the payee the panel lists, so a click on it shows its rows.

- [ ] **Step 1: Write the test.** Append to `tests/test_webapp_flagged_dashboard.py`:

```python
# ---------------------------------------------------------------- Task 13: end to end on the served payload

SERVED_ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 6000.0), (5, "MORTGAGE PAYMENT FABRICATED HOME", -1500.0),
               (9, "ACH DEBIT FABRICATED PFC", -250.0), (19, "MORTGAGE PAYMENT FABRICATED HOME", -1500.0),
               (23, "ACH DEBIT FABRICATED PFC", -250.0), (27, "SERVICE FEE", -15.0)]


@needs_node
def test_a_served_fabricated_statement_fills_the_panel_and_follows_its_switches(tmp_path, monkeypatch):
    """S2's classifier and S3's serving, end to end. A mortgage descriptor (spec §4.3 step 8) and a premium-finance
    payee (C4: its rows stay insurance and carry flagged_group) are served as flagged positions while their switches
    are on; the panel, the chips and a payee click follow the switches without re-analysis (D7)."""
    from analysis import transaction_classifier
    from analysis.serialization import document_report_to_dict
    from tests.test_webapp_studio_views import _report
    from webapp.app import _displayed, store
    from webapp.settings import save_settings

    # A fabricated premium financier, routed into the insurance rule as S2's own tests route one
    # (tests/flag_group_fixtures.py, fake_premium_finance).
    monkeypatch.setattr(transaction_classifier, "PREMIUM_FINANCE_ALIASES",
                        {"Fabricated Premium Finance": ("FABRICATED PFC",)})
    monkeypatch.setattr(store.storage, "data_dir", tmp_path)  # the settings file of a scratch folder
    stored = document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, SERVED_ROWS))
    shown = _displayed(stored)
    save_settings(tmp_path, {"flag_premium_financing": False})
    premium_off = _displayed(stored)
    save_settings(tmp_path, {"flag_mortgages": False})
    hidden = _displayed(stored)
    result = run_dashboard(CELLS + ROWS + PAYEE_CLICK + _serve(shown=shown, premium_off=premium_off, hidden=hidden)
                           + """
const insurer = (html) => rowsOf(html)
  .map((row) => row.includes('<span class="chip-text">Fabricated Premium Finance</span>'));
const open = async (id) => {
  transactionFilter = 'all'; transactionEntityFilter = null;  // as a reopen from Recent does
  currentJobId = id; currentJobIds = [id]; loadResults(id); await settle();
  return {rows: cells(els.flaggedTable.innerHTML), flagged: flaggedOf(els.transactionTable.innerHTML),
    insurer: insurer(els.transactionTable.innerHTML)};
};
const shown = await open('shown');
clickPayee(els.flaggedTable, 'premium_financing', 'Fabricated Premium Finance');
const clicked = {count: els.transactionCount.textContent, dates: datesOf(els.transactionTable.innerHTML)};
const premiumOff = await open('premium_off');
console.log(JSON.stringify({shown, clicked, premiumOff, hidden: await open('hidden')}));
""")
    shown, premium_off, hidden = result["shown"], result["premiumOff"], result["hidden"]
    # Mortgages before Premium financing: FLAG_GROUPS order.
    assert [row[0] for row in shown["rows"]] == ["Mortgages", "Premium financing"]
    assert shown["rows"][0][2:4] == ["2", "$3,000.00"]
    assert shown["rows"][1][1:4] == ["Fabricated Premium Finance", "2", "$500.00"]
    assert shown["flagged"].count(True) == 4
    # The premium-finance rows keep their insurance tag (the insurer's name), whatever the switch says.
    assert shown["insurer"].count(True) == 2 and premium_off["insurer"] == shown["insurer"]
    # A click on the payee shows exactly its two insurance rows: the served canonical_entity is the panel's payee.
    assert result["clicked"] == {"count": "2 Fabricated Premium Finance", "dates": ["2031-03-09", "2031-03-23"]}
    # Premium financing unticked: its rows lose the chip and the panel entry; the mortgages stay flagged.
    assert [row[0] for row in premium_off["rows"]] == ["Mortgages"]
    assert premium_off["flagged"].count(True) == 2
    assert [flag for flag, tagged in zip(premium_off["flagged"], premium_off["insurer"]) if tagged] == [False, False]
    # Both unticked: nothing is flagged.
    assert hidden["rows"] == [[NO_FLAGGED_PAYMENTS]]
    assert True not in hidden["flagged"]
```

- [ ] **Step 2: Run it.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py::test_a_served_fabricated_statement_fills_the_panel_and_follows_its_switches -q -p no:cacheprovider`

Expected: PASS.
- If it FAILS, the served payload departs from C4/C5/C6. Print `shown["detection"]["flagged_positions"]` and the four flagged rows' `classification` records, and compare them with C4/C5/C6.
- If `monkeypatch.setattr` raises `AttributeError` on `PREMIUM_FINANCE_ALIASES`, S2 reads the table under another name: the precondition was not met.
- Report the drift to the orchestrator before changing any code. Do not bend the dashboard to fit an uncontracted shape.

- [ ] **Step 3: Commit.**

```
git add tests/test_webapp_flagged_dashboard.py
git commit -m "tests: dashboard flagged panel end to end on a served fabricated statement"
```

---

### Task 14: Final verification on top of S2 and S3

**Files:** none changed.

- [ ] **Step 1: Run the whole new file.**

Run: `C:\Python314\python.exe -m pytest tests/test_webapp_flagged_dashboard.py -q -p no:cacheprovider`

Expected: 30 passed.

- [ ] **Step 2: Run DASHBOARD GUARDS.** Expected: no failures.

- [ ] **Step 3: Run the master plan's Guards/JS selection.**

Run: `C:\Python314\python.exe -m pytest tests/test_no_statement_hardcodes.py tests/test_new_statement_corpus.py tests/test_webapp_accounts_view.py tests/test_webapp_studio_views.py tests/test_webapp_review_ui.py -q -p no:cacheprovider`

Expected: everything passes except the known `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`, which predates this work.

- [ ] **Step 4: Browser check** (the master plan's orchestrator step 5; to be recorded, not committed).
  1. Restart Flask, because it caches `index.html`.
  2. Open a saved statement that has flagged rows, then open a package.
  3. Tick and untick one group in Settings. Confirm that:
     - the panel, the Flagged chips and the downloads follow the switch;
     - the Flagged pill filters the ledger;
     - a payee click filters the ledger, on a statement and on a package, and unticking that group resets the filter;
     - the statement window shows its own panel;
     - an older saved analysis shows the notice, and its panel shows the "Not available" row, both on the results page and in its statement window;
     - an older saved statement whose main account was not verified (metrics withheld) still shows the notice and its Re-analyze button;
     - the empty-state rows are drawn in the muted text colour (`--text-3`), not the group column's colour;
     - Settings shows eleven switches, in the order of `analysis/flag_groups.py`;
     - on a statement with a premium-financing payee, its rows keep their Insurance tag and carry the Flagged chip, the panel lists the payee under "Premium financing", and a click on it shows those rows;
     - on a package holding floor-plan, factoring or premium-financing payees, the panel lists them after the older groups, in the order of `analysis/flag_groups.py`.
  4. Use real CDP mouse events, following the project's local browser-testing note.

---

## Self-Review

**Evidence gathered while writing and revising this plan (scratchpad only; the repository was not touched).** The numbers below are from this revision's run, 2026-09-25.
- The plan's own Find/Replace and test blocks were parsed out of this file and applied, task by task, to a scratch copy of HEAD `9d91e7b`. Nothing was retyped.
  - At `4f219cd`, `webapp/static/app.js`, `webapp/templates/index.html`, `webapp/app.py`, `webapp/settings.py`, `tests/webapp_js_harness.py`, `tests/test_webapp_studio_views.py` and `tests/test_webapp_accounts_view.py` are byte-identical to that copy (checked with `cmp`). The amendment commit changes only the spec.
  - The scripts are `s4fix3/parse_plan.py` and `s4fix3/run_plan.py`, carried over from `s4amend/` (which adapted the first reviewer's `s4rev/` scripts). Each task's Step 2 selection and the DASHBOARD GUARDS list are read from this file's own `Run:` commands. The log is `s4fix3/run_all.log`.
  - Tasks 1-12 were applied as written. Task 11 ran against a stand-in `analysis/flag_groups.py` copied from C1: eleven groups, with premium financing's `state` set to `None`.
  - Every Find anchor matched exactly once. The one `replace_all` (Task 6) matched twice, as the plan says. Task 10 now has five app.js edits and two index.html edits, all applied once.
- Each task's Step 2 was run with only the earlier tasks applied. Every test failed for the reason its Step 2 names:
  - T1: 1 fail; T2: 3; T3: 4; T4: 2; T5: 5; T6: 2; T7: 2; T8: 3; T10: 3; T12: 1.
  - T9 gave 1 fail and 1 pass; the pass is `test_unticking_another_group_keeps_the_filter`, by design.
  - T11 passed against the C1 stand-in, as its Step 2 expects.
- After each task, the whole new file gave 1/4/8/10/15/17/19/22/24/27/28/29 passed, the numbers each Step 4 predicts.
- DASHBOARD GUARDS gave **75 passed** at the base and **104 passed** after Task 12, with no failure after any task.
- **Task 10's new tests bite** (`s4fix3/mutate_t10.py`, on the copy with Tasks 1-12 applied):
  - With the `renderUnverifiedMain` re-sync removed (the reviewer's finding), `test_the_notice_stays_on_a_statement_whose_main_account_is_withheld` fails with `{'held': {'withheld': True, 'hidden': True}} != {'held': {'withheld': True, 'hidden': False}}`.
  - With the sync moved back above the no-account return, unguarded, `test_the_notice_shows_only_on_a_statement_analysed_with_older_rules` fails with `{'empty': False} != {'empty': True}`.
  - Restored, both pass.
- Task 11's Step 3 was run in the previous revision, and again by the independent reviewer. The label mutation failed with `('mortgages', 'Mortgage') != ('mortgages', 'Mortgages')`, and the tag mutation with `assert ['factoring'] == []`. After the restore the test passed. Neither Task 3's constant nor Task 1's tags changed in this revision.
- **Task 13 needs S2 and S3, so its server half was not run.**
  - Its dashboard half was run: its JS body and asserts, parsed out of this file (`s4fix3/make_t13_probe.py`). They ran against a hand-built stand-in for the served payload in the C4/C5/C6 shapes: two mortgage rows with no entity, and two insurance rows with `canonical_entity` "Fabricated Premium Finance" and `flagged_group` `premium_financing`, served three ways (all on, premium off, both off). It passed.
  - The server half was checked against the S2 and S3 plans only:
    - S2's own test `test_a_premium_finance_debit_stays_insurance_and_is_flagged` (`tests/test_premium_financing.py`, with the fixture `fake_premium_finance`, which maps "Fabricated Premium Finance" to `FABRICATED PFC` as Task 13 does) pins `classification == "insurance"`, `canonical_entity == "Fabricated Premium Finance"`, `flagged_group == "premium_financing"` and `contributes_to_flagged_totals` for `ACH DEBIT FABRICATED PFC 0001`.
    - S2's step-8 descriptor rule (`_descriptor_obligation`) classifies a debit matching `\bMORTGAGES?\b` as `mortgage` with no `canonical_entity`, so `flagged_payee` names it by its group label.
    - S2's `find_flagged_positions` groups on `flagged_group` and names the payee with `flagged_payee` (entity, else label).
    - S3 sets `flag_shown` from `flagged_group` and the setting (C6), and its own test unticks premium financing on an insurance row.
    - `save_settings` merges its updates (`webapp/settings.py:82`).
- A wider run covered every test file that reads `app.js` or `index.html` or uses the node harness, plus `test_no_statement_hardcodes`, `test_webapp_app`, `test_webapp_settings` and `test_webapp_revenue_batch`. It ran on the base copy and on the patched copy, with the new file included in the patched run.
  - Base: 812 passed, 21 failed. Patched: 841 passed (812 + the 29 new tests), 21 failed.
  - The two failure lists are identical (`diff` of the sorted `FAILED` lines is empty). They predate this plan: the scratch copy has no statement corpus. One of them is the known `test_no_literal_account_numbers_in_ocr`.
  - So nothing regresses, and no existing pin flips.
- `test_corpus_gate_outcomes.py` was left out of the wider run, because it cannot be collected in the scratch copy (`adb_forensic_audit` is absent there).

**The owner's amendment (2026-09-24: floor plan, factoring, premium financing), as this revision carries it.**
1. **Tags.** `floor_plan_financing` reads `<entity> (Floor plan)` or "Floor plan", and `factoring` reads `<entity> (Factoring)` or "Factoring" (Task 1).
2. **Labels and switches.** `FLAG_GROUP_LABELS` holds the eleven C1 groups in FLAG_GROUPS order (Task 3), so Settings draws eleven switches, and Task 7's test names all eleven (`GROUP_KEYS`) and checks the three new labels.
3. **The package.** Task 5's `PACKAGE` holds floor plan, factoring and premium financing beside two older groups, keyed in scrambled order. The panel lists them in FLAG_GROUPS order, the three new groups last.
4. **Premium financing.** It has no state of its own, so the dashboard adds no tag for it.
   - Its rows keep the Insurance tag (pinned in Task 1), the Insurance pill and the insurer table (C4 keeps the insurance totals).
   - They carry the Flagged chip, and the Flagged pill keeps them (Task 2).
   - The panel lists them under "Premium financing", and a payee click shows exactly the counted rows. The match keys on `flagged_group`, never on the state. That is tested on a statement (Task 4) and on a package's combined ledger, beside a plain insurer's row that stays out (Task 5).
   - End to end (Task 13): a fabricated premium financier routed through S2's insurance rule is served by S3 as a flagged position. Its rows keep their Insurance tag, a click on the payee shows its two rows, and its switch hides the flag without touching the mortgages.
5. **The save status.** "Saved. Factoring are no longer flagged." would be wrong for the singular labels (Floor plan, Factoring, Premium financing). The status is now `Saved. <label>: flagged.` or `Saved. <label>: no longer flagged.`, and Task 8 tests it on `flag_factoring` (Tasks 8 and 9 anchor on it).
6. **Parity.** Task 11 also checks that every group with a state has a tag, and that premium financing is the only group without one.
7. **Where each new group is exercised.** The statement fixtures `LEDGER` and `POSITIONS` stay a two-group sample (credit cards, mortgages), because many tests pin their exact rows. Each amendment group has its own tests:
   - floor plan: Tasks 1, 5, 7 and 11;
   - factoring: Tasks 1, 5, 7, 8 and 11;
   - premium financing: Tasks 1, 2, 4, 5, 7, 11 and 13.

   Code that iterates the groups (`flaggedPositionEntries`, `renderFlagSettings`, `flagGroupOfSetting`) reads `FLAG_GROUP_LABELS`, so it covers all eleven.

**Verification findings addressed in this revision (second verification of 2026-09-25: plan sound, two stale citations). No code, command or count changed.**
1. **The S5 citation (Global Constraints, Split with S5).** Right: "S5 plan, lines 44-47" no longer pointed at the button binding. It now names the S5 plan's Global Constraints (`app.js` bullets) and quotes S5's listener, `document.getElementById("reanalyzeButton")?.addEventListener("click", ...)`, instead of line numbers.
2. **The S2 serialisation citation (ambiguity 3).** Right: "S2 plan, line 3240" pointed at a metrics test. The verifier's replacement ("Task 9 Step 5, lines 3628-3636") had itself gone stale, because S2 was revised afterwards and the serialisation moved to another task. The citation now quotes the unconditional `"flagged_positions": [_flagged_dict(match) for match in detection.flagged_positions]` in `report_to_dict` and names S2's task by its title.
3. **The same drift elsewhere.** The premium-financing rule is no longer S2's Task 4, so Task 13 and ambiguity 9 name the S2 task by its title ("Premium financing stays insurance and carries its flag") and its test by name. Ambiguity 10 no longer describes S1 as eight groups: S1's current text carries the eleven C1 groups. S1 is referenced only through C1, and the plan states that it consumes nothing of C2, C3 or C10 (the curated ledger).

**Review finding addressed in the previous revision (independent review of 2026-09-25: approve with one required fix).**
1. **The notice on a withheld statement (Task 10). The finding is right and is fixed.** Checked against the code:
   - `renderAnalysis` hands a statement whose main account was not verified to `renderUnverifiedMain` (app.js:2294-2297).
   - `renderUnverifiedMain` starts with `const report = currentDocument; setInitialState(); currentDocument = report;` (app.js:1910-1912).
   - Task 10 makes `setInitialState` hide the notice.

   So the earlier revision's sync at the top of `renderAnalysis` was undone on every withheld statement. That broke C8, and Re-analyze was unreachable there. The CSS exemption `:not(.rules-outdated)` never took effect, and the static test that checked only the CSS could not see it.

   The fix:
   - `renderUnverifiedMain` syncs the notice from its own report right after `setInitialState()`.
   - A new node test, `test_the_notice_stays_on_a_statement_whose_main_account_is_withheld`, serves `_document("held")` with `analysis_rules_outdated` true. It covers All accounts off, All accounts on, and the pick of a verified account, and it fails without the fix (Evidence above).
   - The static test keeps its CSS check, now described as the complement of the node test.
2. **The optional hardening: taken.** `renderAnalysis` now syncs after computing `published`, as `syncRulesOutdatedNotice(published.length ? report : null)`. A payload with no account to show draws no statement, so it no longer leaves a previous statement's notice on, or shows one from a report the page never draws. The first notice test gains the `empty` case, which fails without the guard.
3. **The counts.** Task 10 Step 2 now expects 3 failures, and the whole-file counts are 27, 28 and 29 after Tasks 10, 11 and 12, and 30 at Task 14. DASHBOARD GUARDS gives 104 after Task 12. Ambiguity 3 below now points at the test.

**Review findings addressed in earlier revisions.**
1. **The S5 split.** The plan no longer says that S5 adds `els.reanalyzeButton`. S5 binds the click through `document.getElementById`, and neither plan adds that `els` entry (Global Constraints, Task 10, ambiguity 4).
2. **The parity task.** Task 11 no longer edits `analysis/flag_groups.py`. If S1's file departs from C1, the cell stops and reports.
3. **The legacy empty state.** A payload without flagged positions now draws "Not available", with a hint to re-analyze, instead of claiming that no ticked group was paid. This holds on the results page (Task 3), the package page (Task 5) and the statement window (Task 6).
4. **The package payee click.** Task 5 now clicks a payee on a package. The combined ledger holds rows from two statements, a duplicate, another group's payee and a credit, and the ledger count must equal the panel's Count cell.
5. **The Task 3 split.** Task 3 is now two tasks:
   - Task 3: the constants, the panel, its markup and its CSS;
   - Task 4: the `flagged:<group>` filter, `flaggedPayeeOf` and the click listener.

   The later tasks moved up by one.
6. **The card tag.** `credit_card_payment` names its issuer, as `<issuer> (Credit card)`, when the classifier named one (Task 1).
7. **The CSS.** The group column's colour rule is `td:first-child:not(.empty-cell)`, so the empty state keeps `--text-3` (Task 3).
8. **`Object.hasOwn`.** It is replaced by `ownKey`, which calls `Object.prototype.hasOwnProperty.call`. The page's browser floor stays where it was (Tasks 3 and 8).
9. **The commit trailers.** The Global Constraints now give the exact trailer lines. The only part left open is the committing session's own URL, which exists only in that session.

**Spec coverage (§8.5 and C8):**

| Spec requirement | Where |
|---|---|
| Settings: "Flagged positions" section between Analysis and Statements, own status line | Task 7 (markup, test of order and status line; eleven switches) |
| Checkboxes rendered from one JS constant into a container | Task 3 `FLAG_GROUP_LABELS`; Task 7 `renderFlagSettings` into `#flagSettingsList` |
| One delegated `change` listener, one key per change, then `refreshShownResults()` | Task 8 |
| Whole group disabled while a save is in flight | Task 8 (`saving` all disabled; second change not sent) |
| Panel on the results page, package page and statement window | Tasks 3, 5, 6 |
| Columns Group, Payee, Count, Total, Cadence, plus Statements on packages | Tasks 3, 5 (static and rendered), 6 |
| Money with the payload's currency | Tasks 3, 5, 6 (CA$ asserted; refused package shows N/A) |
| Clicking a payee filters the ledger | Task 4 (results page), Task 5 (package page, combined ledger), Task 6 (statement window) |
| Empty state when no ticked group has payments | Tasks 3, 5; a payload that publishes no flagged positions says "Not available" instead (Tasks 3, 5, 6) |
| Header does not reuse "Potential Withholding", "Eligible Deposits" or "Exposure" | Task 3 static test; the existing guard still counts two `<th>Potential Withholding</th>` |
| A tag for each new state; the retired `lease_or_equipment_financing` keeps its label | Task 1, for all nine new states, floor plan and factoring included (card payments name their issuer too; a premium-financing row keeps its Insurance tag); Task 11 checks that every group with a state has a tag |
| "Flagged" chip on `flag_shown` rows; a credit shows its revenue state first | Tasks 2, 1 (including an insurance row of the Premium financing group) |
| "Flagged" ledger filter pill (C8 `"flagged"` keeps `flag_shown === true`) | Task 2 (main and modal pills) |
| Ledger filter resets when the filtered group is unticked | Task 9 |
| Lender table unchanged | not touched |
| Outdated notice: "Analysed with older lender rules" and a Re-analyze button, shown on `analysis_rules_outdated === true` | Task 10, including a statement whose main account is withheld (All accounts off and on) and a payload with no account to show; S5 owns the click |
| `FLAG_GROUP_LABELS` parity test against `analysis/flag_groups.py` | Task 11 |
| Every group of the §2 amendment (floor plan, factoring, premium financing) has its checkbox, default on; premium-financing rows stay insurance and are also flagged | Tasks 1, 3, 7 and 11 (tags, labels, switches, parity); Task 5 (package order and the premium-financing package click); Tasks 2, 4 and 13 (premium financing on a statement, end to end) |
| Dashboard tested through `tests/webapp_js_harness.py` (spec §9) | Tasks 1-10, 13 |

**Placeholder scan.**
- No "TBD", "TODO", "similar to Task N" or "add error handling" appears.
- Every step shows its full code, and every command is exact.
- The one value the plan cannot know is the committing session's URL in the `Claude-Session` trailer (Global Constraints, Commits). It is runtime data, not missing code.
- The two preconditions (Tasks 11 and 13) name what to check and what to do when it fails. Task 13's now checks three things, `PREMIUM_FINANCE_ALIASES` in `analysis.transaction_classifier` among them.
- Every new test uses fabricated names and whole-dollar amounts. The premium financier of Task 13 is a fabricated alias routed in with `monkeypatch`, as S2's own tests do, so no real payee name enters S4's tests. No commit message quotes a statement value.

**Contract-name consistency.** The C8 names are used verbatim:
- `FLAG_GROUP_LABELS`
- `flagSettingsSection`, `flagSettingsList` and `flagSettingsStatus`
- `renderFlagSettings(settings, disabled)` and `data-flag-setting`
- `flaggedCard`, `flaggedCount` and `flaggedTable`
- `renderFlaggedPositions(positions, currency, isPackage)`
- the filter `"flagged"`
- `rulesOutdatedNotice` and `reanalyzeButton`

The payload names follow C5/C6:
- `detection.flagged_positions` and its entry keys;
- `pkg.flagged_positions` with `documents`;
- `flagged_group`, `contributes_to_flagged_totals` and `flag_shown`;
- the top-level `analysis_rules_outdated`.

The names S4 adds beyond the contract are each defined in the task that introduces them:
- `statementModalFlagged` (Task 6);
- the filter value `flagged:<group>` (Task 4);
- `ownKey`, `flagGroupLabel`, `CADENCE_LABELS` and `cadenceLabel` (Task 3);
- `flaggedPositionEntries` and `flaggedPositionRowsHtml` (Task 3);
- `flaggedFilterGroup` and `flaggedPayeeOf` (Task 4);
- `flaggedChip` (Task 2);
- `flagSettingKey` and `setFlagSettingsStatus` (Task 7);
- `flagGroupOfSetting` and `saveFlagSetting` (Task 8);
- `releaseFlagFilter` (Task 9);
- `syncRulesOutdatedNotice` (Task 10).

None of them collides with a name S5 adds, such as `reanalysisBusy` or `reanalyzeShownStatement`.

**Contract ambiguities this plan resolves (for the orchestrator):**
1. **The statement window's table.** C8 names no id for it, so this plan uses `statementModalFlagged`.
2. **The payee click.**
   - C8's `"flagged"` filter keeps every `flag_shown` row, including a proven duplicate. The Flagged pill keeps exactly that.
   - A panel payee click uses `flagged:<group>` instead. That filter also requires `flagged_group` and `contributes_to_flagged_totals`, and it matches the payee as C5 names it (the canonical entity, else the group label).
   - As a result, the rows shown equal the panel's count, on a statement and on a package, and a payee with the same name in two groups stays apart.
3. **Analyses saved before flagged positions existed.**
   - **Such a payload.** An analysis saved before S2 publishes no `detection.flagged_positions`. From S2 on, the key is always a list: S2's `report_to_dict` publishes `"flagged_positions": [_flagged_dict(match) for match in detection.flagged_positions]` unconditionally, next to `"insurance_providers"` (S2 plan, the task "`detection.flagged_positions` in the payload"), and `DetectionResult.flagged_positions` defaults to `[]`. Its panel says "Not available", with a hint to re-analyze. It does not claim that no ticked group was paid.
   - **The results page.** It also shows the notice.
   - **The statement window.** It shows no notice. Its "Not available" row carries the same message, and the Re-analyze button belongs to the results page.
   - **A package.** C6 publishes no package-level `analysis_rules_outdated`, so the notice is hidden on packages; it is also marked `single-only`.
   - **A statement whose main account was not verified.** The notice stays visible while its metrics are withheld, because re-analysis concerns the whole saved statement. Two things make that hold:
     - `renderUnverifiedMain` re-syncs the notice after its own `setInitialState()`;
     - the withheld CSS rule exempts `.rules-outdated`.

     `test_the_notice_stays_on_a_statement_whose_main_account_is_withheld` pins it (Task 10).
   - **A payload with no account to show.** It draws no statement, so it shows no notice (Task 10, the `empty` case).
   - **Open question for the orchestrator.** A package built by S3 always carries `flagged_positions`. S3 rolls it up from the members' rows (S3 plan, `_add_flagged_rows`). A package whose members all predate S2 therefore serves `{}`, and its panel says that no ticked group has payments.
     - The dashboard cannot tell that case apart without a package-level signal, and C6 defines none.
     - If the owner wants the package page to say "Not available" there, S3 would need to publish one, for example a top-level `analysis_rules_outdated` on the package. S4 would then pass it through `flaggedPositionEntries`.
     - This plan does not invent that key.
4. **The split with S5.** S4 adds `els.rulesOutdatedNotice` and the markup of both elements. S5 binds the button's click through `document.getElementById("reanalyzeButton")`. Neither plan adds `els.reanalyzeButton`.
5. **The settings key.** The dashboard derives the settings key as `flag_<group key>`; C1 follows that pattern for every group, and Task 11 pins it.
6. **The filter reset.** It applies only to the `flagged:<group>` filter of the group being unticked. The plain Flagged pill is not reset.
7. **The switches at startup.** They are drawn on and held (disabled) until `/api/settings` answers, because the default is `True` and a missing key counts as on (C6).
8. **The card tag.** `credit_card_payment` was not a new state, but it is now the Credit cards group. Its tag names the issuer, so a card row's tag and its panel payee read alike.
9. **Premium financing, which has no state (C1 `state=None`).**
   - The task asks for a tag for each new state, and premium financing is not one. So its rows keep their unchanged Insurance tag and gain the Flagged chip; there is no "Premium financing" tag.
   - They also stay under the Insurance pill and in the insurer table, as C4 keeps their insurance totals.
   - Every S4 filter and chip keys on `flag_shown`, `flagged_group` and `contributes_to_flagged_totals`, never on the state, so these rows are flagged like every other group.
   - A payee click matches because S2 sets `canonical_entity` on these insurance rows to the premium-finance entity (S2 plan, the task "Premium financing stays insurance and carries its flag"). S2's `flagged_payee` names the `detection.flagged_positions` payee from that same field (C5: "canonical_entity or group label").
   - Task 13 now pins that end to end on a fabricated premium financier. The orchestrator's browser check (Task 14) should still open one such statement.
10. **Eight or eleven keys.** Spec §8.1 still says "the eight `flag_*` keys". The amended C1 and C7 make it every key in `FLAG_SETTING_KEYS`, which is eleven, and this plan follows C1/C7.
    - S4 relies on S1 only through C1. The S1 plan's `analysis/flag_groups.py` code, as read on 2026-09-25, carries the eleven C1 groups in C1 order, with `state: str | None` and `FlagGroup(None, "premium_financing", "flag_premium_financing", "Premium financing")` last. The S2 and S3 plans carry the amendment too, and S3 raises the same point (its item 11). S5 names no group in its production code.
    - S1 is being revised in parallel for C10 (the curated registry ledger). C10 changes how S1 fills the alias tables (C2), not C1, and S4 reads no alias table. Nothing in this plan depends on the ledger, the builder or the research inputs.
    - Whatever S1 lands, Task 11 checks it: if `analysis/flag_groups.py` departs from C1 (eight groups, a missing premium financing, or a premium financing given a classification state), Task 11 fails on the label list or the state check, and its Step 2 says to stop and report rather than edit S1's file. So S4 cannot drift silently. That is the orchestrator's to reconcile.
