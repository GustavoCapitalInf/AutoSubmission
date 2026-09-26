# S3 Webapp Serving, Package and Downloads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve, package and export the eleven flag groups exactly as the owner's Settings tick them. That means eleven Settings checkboxes, on by default. Serving works on a copy that hides unticked groups, tags each row with `flag_shown` and marks analyses classified by older rules. The package gains a roll-up and two totals, both covered by the currency refusal. Since the owner's ruling of 2026-09-26, a flagged payee's credits (a factor's payouts) are counted apart from its debits, in the served summaries, the roll-up, two more totals and the sheets (Task 12). Readable `flagged_<group>_<n>` rows go into every CSV/XLSX. The lender totals, the withholding and the package `decision` must not move.

**Architecture:**
- A new presentation module, `analysis/flagged_view.py`, follows the NSF-basis pattern (`analysis/nsf_days.py`):
  - it works on either payload shape (`analysis/payload_shape.py`);
  - it deep-copies before changing anything;
  - it never refuses.
- `webapp/app.py::_displayed` applies the NSF basis and then this module, from one settings snapshot. `_package_analysis` reads that snapshot once and passes it to `_package_members`.
- The package roll-up reads only each member's displayed rows:
  - the rows the analysis marked `contributes_to_flagged_totals`, in ticked groups;
  - the internal-transfer legs are already removed.

  It never reads lender or withholding figures and never writes to them.
- Everything keys on the row's `classification.flagged_group` and on `FLAG_GROUP_BY_KEY`, never on the classification state. Premium financing has no state of its own (C1 `state=None`): its rows stay `insurance` and keep their insurance totals, and they carry the flag as well.
- The exports add their own readable sections, and those rows go through the existing escaped-row writers.

**Tech Stack:** Python 3.14 (`C:\Python314\python.exe`), pytest 9, Flask. No JS changes (S4 owns `webapp/static/app.js`).

**Spec:** `docs/superpowers/specs/2026-09-24-lender-detection-design.md` §8.1-8.4. **Contract:** `docs/superpowers/plans/2026-09-24-lender-detection.md` C1, C5, C6, C7. **Branch:** `ld-s3-webapp`, from `lender-detection` (`4f219cd` when this plan was written: the spec amendment that adds floor plan, factoring and premium financing; its code is byte-identical to `9d91e7b`). Every line number below is at `4f219cd`. Line numbers move as tasks land, so each edit is anchored by the exact text it replaces.

## Global Constraints

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

**S3-specific constraints**

- S3 changes only these files:
  - `webapp/settings.py`
  - `webapp/app.py`
  - `analysis/flagged_view.py` (new)
  - `tools/l1s3_surface_census.py`, one `READERS` entry (Task 3)
  - `analysis/flag_groups.py`, only in the Task 1 fallback
  - the test files listed under File Structure

  It never touches the classifier, metrics, detection or serialization (S2), `webapp/static/app.js` or the templates (S4), or any re-analysis route (S5).
- **The stored job is never mutated by serving.**
  - `_displayed` deep-copies every account's `statement.transactions`, `metrics` and `detection` before it changes them.
  - The review routes persist whatever `job.analysis` holds (`webapp/app.py:2338-2355`), so a tag written in place would be saved.
- **A presentation step never raises.**
  - A payload that is not one of the two published shapes is returned as the same object.
  - This matters for `{}` in particular. `_package_analysis` counts a member whose analysis is `{}` as carrying no currency (`webapp/app.py:1026-1033`). A key added to it would fail the package closed.
- **Additive only.**
  - A payload without flag fields keeps every stored value.
  - It gains only `flag_shown: false` on each classification record and a top-level `analysis_rules_outdated`.
- The lender totals, the withholding and the `decision` stay byte-for-byte what they were (D7).
- **Premium financing (spec §2 amendment, C1, C4).**
  - A group is read from `classification.flagged_group` and looked up in `FLAG_GROUP_BY_KEY`. S3 never maps a classification state to a group, and never reads `FLAG_GROUP_BY_STATE`, which has no entry for premium financing.
  - A premium-financing row keeps `classification="insurance"` and `contributes_to_insurance_totals`. S3 never edits the insurance totals, rows or evidence, so the row counts in the insurance totals whether its checkbox is ticked or not, and it also counts in the flag roll-up while ticked.
- `analysis/flag_groups.py` belongs to S1:
  - S3 creates it only when `lender-detection` does not have it yet (Task 1);
  - S3 never edits or re-pins S1's copy. S1's copy must pass Task 1's C1 pin: eleven groups, and premium financing with `state=None`. If it fails, S3 stops and reports to the orchestrator (Task 1, Step 3);
  - on a rebase conflict, S3 takes `lender-detection`'s copy only after that copy passes the same pin (Task 1, Step 7). If the copy fails, S3 aborts the rebase and reports.
- Tasks 10 and 11 start only after S2 has merged into `lender-detection` and this branch is rebased onto it.
- Task 12 (the owner's ruling of 2026-09-26 on factoring credits) runs after Task 9 and before Task 10. It needs nothing from S2, and Tasks 10 and 11 are written on top of it (Task 12, "Why it runs now").
- **Commands** are written for PowerShell, the primary shell. From Git Bash, write the interpreter as `C:/Python314/python.exe`.
- **Commits.** Every commit step gives the exact `git add` paths and the whole `git commit` command. Its second `-m` carries the two attribution lines:
  - `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` is fixed for an Opus 5.5 (1M context) cell.
  - The `Claude-Session` URL belongs to the session that commits. Replace `<the Claude-Session URL from your system reminder>` with the URL from that session's system reminder, which is the only place it exists.
  - If that system reminder gives different attribution lines, use its lines.
  - Messages never quote statement values.

---

## File Structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `analysis/flag_groups.py` | Create only if absent (Task 1) | C1, verbatim: the eleven groups, their keys, settings and labels. S1 owns it. |
| `analysis/flagged_view.py` | Create | C6 `apply_flagged_groups_to_payload`: on a copy, drops the unticked groups from the summaries, tags rows with `flag_shown`, sets the top-level `analysis_rules_outdated`, never raises. Also `enabled_group_keys`. |
| `tools/l1s3_surface_census.py` | Modify: one `READERS` entry after `webapp/worker.py`'s (`:151-152`), just before `analysis/nsf_days.py`'s. S5 appends its own entry after `analysis/nsf_days.py`'s (`:153-154`), so each plan's edit still finds its anchor after the other merges, and git rebases the two without a conflict (checked on a scratch copy of the file) | Declares `apply_flagged_groups_to_payload` a `per_account` payload reader, as `apply_nsf_basis_to_payload` is. Its account reads go through the imported `STATEMENT_KEY`, which the census's reverse sweep does not follow, so only the declaration puts it under the census's forward check (master plan, Orchestrator verification). |
| `webapp/settings.py` | Modify `:19-28` | C7: `DEFAULTS` gains every key of `FLAG_SETTING_KEYS`, each `True`. |
| `webapp/app.py` | Modify | `_displayed` takes the settings snapshot. `_package_members` and `_package_analysis` share one snapshot. The package flag roll-up, evidence, totals, currency refusal and ordering. Readable flag rows in the statement and package CSV/XLSX. The credited fields of each (Task 12). |
| `tests/flagged_payloads.py` | Create | Fabricated payloads that follow C4/C5 (rows, `metrics.flagged_groups`, `detection.flagged_positions`), built on `tests/l1s3_payloads.py`. A premium-financing row is an `insurance` row that also carries the flag. Since Task 12, a factoring credit counts too (`CREDITED_GROUP_KEYS`), and the summaries carry `count_credited` and `total_credited`. |
| `tests/test_flagged_view.py` | Create | Unit tests for `analysis/flagged_view.py`. |
| `tests/test_webapp_flagged_positions.py` | Create | Every served surface for every checkbox: `/analysis`, the JSON/CSV/XLSX downloads, the review response, package members and document accounts, exclusions, one settings read per package, roll-up, totals, premium financing staying insurance, package exports, cadence, and conformance with S2 (floor plan, factoring and premium financing included). Task 12 adds the flagged credits (a factor's payouts) on every one of these surfaces. |
| `tests/test_webapp_settings.py` | Modify `:1-9, :31, :41-42, :57-61, :129-130, :176`, and append | The whole-dict pins take the new keys. New checkbox tests. |
| `tests/test_package_currency.py` | Modify `:31-41, :45-78, :83-109, :565-571, :595-628, :716`, and insert before `:401` | The refused-totals and unit-free sets, the widened `CROSS_DOCUMENT_SECTION`, a sweep that is not vacuous over flagged rows, the refusal tests for the flag roll-up, and 32 becoming 33. Task 12 adds the credited keys to the three sets, a factoring credit to the sweep, two refusal tests for the credited roll-up, and 33 becoming 34. |

## Existing pins that flip (derived values only)

| Pin (at `4f219cd`) | Today | Becomes | Edit (Task) |
|---|---|---|---|
| `tests/test_webapp_settings.py:31` | `== {"nsf_carry_over": False} == DEFAULTS` | `== EXPECTED_DEFAULTS == DEFAULTS`, where `EXPECTED_DEFAULTS` is spelled out: the NSF key (`False`) plus the eleven `flag_*` keys, all `True` | Task 2 |
| `tests/test_webapp_settings.py:41-42` | `== {"nsf_carry_over": True}` twice | `== CARRY_OVER` (`{**EXPECTED_DEFAULTS, "nsf_carry_over": True}`), because a save merges | Task 2 |
| `tests/test_webapp_settings.py:57, :59, :60, :61` | whole dicts with one key | `EXPECTED_DEFAULTS` at `:57`, and `CARRY_OVER` at `:59`, `:60` and `:61` | Task 2 |
| `tests/test_webapp_settings.py:129-130` | `{"nsf_carry_over": True}` | `CARRY_OVER` | Task 2 |
| `tests/test_webapp_settings.py:176` | `{"nsf_carry_over": True}` | `CARRY_OVER` | Task 2 |
| `tests/test_package_currency.py:45-78` `EXPECTED_REFUSED_TOTALS` | 32 keys | adds `"flagged_position_total"` | Task 8 |
| `tests/test_package_currency.py:83-109` `UNIT_FREE_TOTALS` | as listed | adds `"flagged_position_count"` | Task 8 |
| `tests/test_package_currency.py:716` | `== 32` | `== 33` | Task 8 |
| `tests/test_package_currency.py:569-571` `CROSS_DOCUMENT_SECTION` | four section kinds | adds `flagged_(<the eleven keys>)_\d+` | Task 9 |
| `tests/test_package_currency.py:595` and `:622-628` (the sweep) | members with no flag rows | both members gain one fabricated `credit_cards` debit, and `exercised` must include a `flagged_credit_cards_` section | Task 9 |
| `tests/test_package_currency.py` `EXPECTED_REFUSED_TOTALS`, `UNIT_FREE_TOTALS`, `UNIT_FREE_ROLLUP_KEYS` | as Tasks 8-9 leave them | add `"flagged_position_total_credited"`, `"flagged_position_count_credited"` and `"count_credited"` | Task 12 |
| the refused-field count (Task 8's `== 33`) | `33` | `34` | Task 12 |
| the sweep (Task 9) | one `credit_cards` debit per member | also one fabricated `factoring` credit per member, and the swept rows include its `count_credited` and a refused `total_credited` | Task 12 |
| `tests/test_webapp_flagged_positions.py`, `test_displayed_takes_one_settings_snapshot_and_carry_over_still_decides_the_nsf_basis` | `{"count": 1, "total": FLAGGED_DEBIT, "payees": 1}` | the same with `"count_credited": 0, "total_credited": 0.0` (C5 as amended) | Task 12 |

These stay green unchanged, and the plan relies on that:
- `tests/test_l1s3_surfaces.py:54-57`: `account_payload()` has no `flagged_positions`, so its section set is untouched.
- `tests/test_webapp_app.py:321-419`: a legacy package still publishes 6.82 and `approved`. The new totals are 0 and 0.0.
- `tests/test_webapp_settings.py:83-232`: the NSF tests.

## Contract points this plan resolves

1. **Pass-through vs. the new keys (spec §8.2 against C6).**
   - A payload in one of the two published shapes always gets:
     - the top-level `analysis_rules_outdated: bool`, which is False when no record has an older major version;
     - `flag_shown` on every classification record, False for a record that names no group.
   - Nothing stored is dropped or altered, so "legacy payloads pass through" holds for every stored value.
   - Anything that is not a published shape is returned as the same object, including `{}`, `None`, a malformed document and the shim.
   - S5's plan asserts `analysis_rules_outdated is False` after a re-analysis (its `test_the_outdated_rules_flag_clears_after_a_reanalysis`), so the key is always a bool.
2. **Where the settings snapshot is read (spec §8.2).**
   - The spec says `_package_members` "reads … and passes it to `_package_analysis`". The call order is the reverse: `_package_analysis` calls `_package_members`.
   - So `_package_analysis(jobs, *, settings=None)` reads once and passes the snapshot to `_package_members(jobs, *, settings=None)`, which reads only when it is called alone.
   - Either way there is one read per package, and both keep today's call shapes (`tests/test_l1s3_surfaces.py:103`, `tests/test_adb.py:1171`).
3. **`flagged_position_count`** counts the ticked groups' counted **debits**, and pairs with `flagged_position_total`. This follows the contract's `count` vocabulary (`metrics.flagged_groups[g].count`, and each roll-up item's `count`). It is also how S4's package fixture reads it: S4 Task 5's `PACKAGE` gives `"flagged_position_count": 8` beside `"flagged_position_total": 5450.0`, and 8 is the sum of its roll-up items' `count` (1 + 2 + 2 + 2 + 1).
4. **`documents`** on a roll-up item counts the package members the payee appears in, as the funder roll-up does (`webapp/app.py:1386`).
5. **Payee.** A roll-up keys on `canonical_entity`, or on the group label when the analysis named none (C5).
6. **Unknown and malformed groups.** A group key C1 does not define is never shown: not a string, or not a key. It is dropped from the summaries and gets `flag_shown: false`. The function never raises on it.
7. **Evidence.** Spec §8.3 requires evidence that carries `source_account`, and C6 named no key for it. The master plan's C6 now names `flagged_evidence`, as below, and states resolution 2's call order.
   - The package publishes it as a new top-level `flagged_evidence`: classification records plus `source_job` and `source_document`, and `source_account` for an account of a multi-account document.
   - It goes to JSON only. §8.4 names only `flagged_<group>_<n>` rows for the sheets.
8. **Cadence.**
   - The package cadence needs S2's `analysis/cadence.py::describe_cadence` (C5), so it is its own gated task (Task 10). Before that, roll-up items carry every C6 field except `cadence`.
   - A payee with no parseable date gets `cadence: None`.
9. **Single-statement rows.**
   - The fields are `payee`, `count`, `total_debited` and `cadence`. §8.4 says "total", and the payload and package key is `total_debited`, so one name serves both sheets.
   - The `detection.flagged_positions` JSON cell is replaced by these rows.
10. **Copy cost.** C6's deep copy was measured on a fabricated 300-row account: about 12 ms per account per request. It is accepted for the safety it buys.
11. **Eleven checkboxes, not eight (spec §8.1 against the §2 amendment, C1 and C7).**
    - Spec §8.1 still says "the eight `flag_*` keys". The owner's amendment (spec §2) added floor plan, factoring and premium financing, "each with its own checkbox, default on", and C1 carries eleven groups.
    - C7 says "every key in `FLAG_SETTING_KEYS`", so `DEFAULTS` gains eleven keys. The test pins them spelled out (`EXPECTED_DEFAULTS`), so a twelfth group cannot slip in unseen.
12. **Premium financing counts twice, in two separate figures.**
    - Its rows stay in the insurance totals, as today (spec §2, C4), and they also count in `flagged_position_count` and `flagged_position_total` while the checkbox is ticked.
    - The two are separate figures, and neither feeds the lender totals, the withholding or the decision. Nothing adds them together.
    - Unticking premium financing removes it from the flag roll-up and the flag totals only. The insurance count, total and evidence do not move (Task 7, `test_premium_financing_stays_insurance_whether_or_not_it_is_flagged`).
13. **Flagged credits (the owner's ruling of 2026-09-26; C4-C6 as amended; Task 12).**
    - A factoring credit stays revenue and carries the Factoring flag. It is a contributing row of the Factoring group, so `_counts_as_flagged` counts it and `flag_shown` tags it with no serving change.
    - The roll-up keeps it apart from the debits: `count` and `total_debited` stay debit-only (resolution 3 still holds for `flagged_position_count`), and a credit adds to `count_credited` and `total_credited`. `totals.flagged_position_count_credited` (unit-free) and `totals.flagged_position_total_credited` (money, refused across currencies) sum them.
    - Order within a group is `total_debited + total_credited`, then payee, or `count + count_credited`, then payee, under a refusal. The dates, and Task 10's cadence, read debits and credits alike, as C5 reads them for a statement.
    - A payee whose counted rows are all credits is an item with `count` 0.

---

### Task 1: Start the branch and bring in the C1 module

**Files:**
- Create (only if `lender-detection` lacks it): `analysis/flag_groups.py`
- Create: `tests/test_flagged_view.py`

**Interfaces:**
- Consumes: nothing.
- Produces: C1 `FLAG_GROUPS`, `FLAG_GROUP_BY_STATE`, `FLAG_GROUP_BY_KEY`, `FLAG_SETTING_KEYS` and `FINANCING_STATES`, exactly as the master plan writes them.

- [ ] **Step 1: Create the branch.**

```powershell
git switch -c ld-s3-webapp lender-detection
git ls-tree --name-only lender-detection -- analysis/flag_groups.py
```

Expected:
- the switch succeeds;
- the second command prints `analysis/flag_groups.py` when S1 has merged, or nothing when it has not.

- [ ] **Step 2: Write the pin test.** Create `tests/test_flagged_view.py`:

```python
"""Flag groups as Settings shows them (lender detection §8.2, plan contract C6). Fabricated payloads only."""
from analysis.flag_groups import FLAG_GROUPS, FLAG_SETTING_KEYS


def test_the_view_reads_the_eleven_contract_groups():
    assert tuple(group.key for group in FLAG_GROUPS) == (
        "alternative_positions", "lines_of_credit", "credit_cards", "vehicle_financing",
        "bank_loans", "mortgages", "leases_rentals", "personal_loans",
        "floor_plan", "factoring", "premium_financing",
    )
    assert FLAG_SETTING_KEYS == tuple(f"flag_{group.key}" for group in FLAG_GROUPS)
    # Premium financing is the one group with no state of its own: its rows stay insurance (C1, C4).
    assert [group.key for group in FLAG_GROUPS if group.state is None] == ["premium_financing"]
```

- [ ] **Step 3: Run it.**

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py -q -p no:cacheprovider
```

Expected:
- If Step 1 printed nothing: FAIL at collection with `ModuleNotFoundError: No module named 'analysis.flag_groups'`. Go on to Step 4.
- If Step 1 printed the path: `1 passed`. The module is S1's and follows C1. Skip Step 4.
- If Step 1 printed the path and the test FAILS, S1's module departs from C1. For example, it has eight groups, no premium financing, or `state: str`. This branch is a safeguard: S1's plan has created the module as C1 verbatim since its 2026-09-25 amendment, so it is not expected to run. Stop here:
  - print what the module holds:

    ```powershell
    C:\Python314\python.exe -c "from analysis.flag_groups import FLAG_GROUPS; print([(g.state, g.key, g.setting, g.label) for g in FLAG_GROUPS])"
    ```

  - report that list and pytest's assertion diff to the orchestrator;
  - do not create, edit or re-pin `analysis/flag_groups.py` or this test, and do not start Task 2. Every later task reads the eleven groups.

- [ ] **Step 4 (only when the module is absent): create `analysis/flag_groups.py`** with exactly the C1 block:

```python
"""The eleven flag groups (lender detection, plan contract C1). No imports from other analysis modules."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FlagGroup:
    state: str | None  # classification state, e.g. "alternative_position"; None = set by rule (premium financing)
    key: str        # flagged_group value and payload key, e.g. "alternative_positions"
    setting: str    # webapp Settings key, e.g. "flag_alternative_positions"
    label: str      # human label, e.g. "Alternative positions"


FLAG_GROUPS: tuple[FlagGroup, ...] = (
    FlagGroup("alternative_position", "alternative_positions", "flag_alternative_positions", "Alternative positions"),
    FlagGroup("line_of_credit", "lines_of_credit", "flag_lines_of_credit", "Lines of credit"),
    FlagGroup("credit_card_payment", "credit_cards", "flag_credit_cards", "Credit cards"),
    FlagGroup("vehicle_financing", "vehicle_financing", "flag_vehicle_financing", "Vehicle loans & leases"),
    FlagGroup("bank_loan", "bank_loans", "flag_bank_loans", "Bank loans"),
    FlagGroup("mortgage", "mortgages", "flag_mortgages", "Mortgages"),
    FlagGroup("lease_or_rental", "leases_rentals", "flag_leases_rentals", "Leases & rentals"),
    FlagGroup("personal_loan", "personal_loans", "flag_personal_loans", "Personal loans"),
    FlagGroup("floor_plan_financing", "floor_plan", "flag_floor_plan", "Floor plan"),
    FlagGroup("factoring", "factoring", "flag_factoring", "Factoring"),
    # Premium financing: rows keep classification "insurance" (and their insurance totals); the classifier
    # sets flagged_group="premium_financing" when the insurance match is a PREMIUM_FINANCE_ALIASES payee.
    FlagGroup(None, "premium_financing", "flag_premium_financing", "Premium financing"),
)
FLAG_GROUP_BY_STATE: dict[str, FlagGroup] = {g.state: g for g in FLAG_GROUPS if g.state is not None}
FLAG_GROUP_BY_KEY: dict[str, FlagGroup] = {g.key: g for g in FLAG_GROUPS}
FLAG_SETTING_KEYS: tuple[str, ...] = tuple(g.setting for g in FLAG_GROUPS)
# D1: credits from these states are financing proceeds (non_revenue + lender credit exclusion).
FINANCING_STATES: frozenset[str] = frozenset({
    "confirmed_lender", "alternative_position", "line_of_credit", "bank_loan",
    "vehicle_financing", "mortgage", "personal_loan", "floor_plan_financing", "factoring",
})
```

- [ ] **Step 5: Run the test and the analysis-layer guards.**

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py -q -p no:cacheprovider
```

Expected:
- `test_the_view_reads_the_eleven_contract_groups` passes;
- the only failure is the known `test_no_literal_account_numbers_in_ocr`.

- [ ] **Step 6: Commit.** Add `analysis/flag_groups.py` only if Step 4 created it.

```powershell
git add tests/test_flagged_view.py analysis/flag_groups.py
git commit -m "analysis: pin the eleven flag groups the webapp service reads (contract C1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

- [ ] **Step 7 (only when a rebase stops on `analysis/flag_groups.py`): take S1's copy only if it follows C1.**

This happens in Task 10, Step 1, when Step 4 created the module here and S1's merged copy differs from it. During a rebase:
- `--ours` is the branch being rebased onto (`lender-detection`);
- the working tree holds this task's `tests/test_flagged_view.py`, because this is the commit being replayed.

```powershell
git checkout --ours -- analysis/flag_groups.py
C:\Python314\python.exe -m pytest tests/test_flagged_view.py::test_the_view_reads_the_eleven_contract_groups -q -p no:cacheprovider
```

Expected: `1 passed`. Only then finish the resolution:

```powershell
git add analysis/flag_groups.py
git -c core.editor=true rebase --continue
```

`core.editor=true` keeps the replayed commit's message. Without it, and with no `GIT_EDITOR` set, `git rebase --continue` opens an editor for a commit that had a conflict (measured), and a non-interactive session would hang.

If the test FAILS, S1's copy departs from C1. Do not continue the rebase, and do not edit S1's module:

```powershell
git rebase --abort
```

The branch is back where it was before the rebase. Report the failing assertion to the orchestrator, with the list that Step 3's print command shows.

The outcomes were simulated in a scratch repository, with this task's commit replayed onto a branch that adds its own `analysis/flag_groups.py`:
- with an eight-group module, as S1's plan was written before its 2026-09-25 amendment, the pin gave `1 failed`, and `git rebase --abort` restored this task's commit;
- with a C1 copy whose docstring differs, the pin gave `1 passed`, and the rebase finished;
- with S1's amended module (C1 verbatim, with its own docstring and `from __future__ import annotations`), the add/add conflict resolved with `--ours`, the pin gave `1 passed`, the rebase finished, and the replayed commit kept only `tests/test_flagged_view.py`.

S1's plan now creates the module as C1 verbatim, so this step's failure branch, like Step 3's stop branch, is a safeguard that is not expected to fire.

---

### Task 2: One Settings checkbox per flag group (C7)

**Files:**
- Modify: `webapp/settings.py:19-28`
- Test: `tests/test_webapp_settings.py:1-9, :31, :40-43, :55-61, :118-130, :164-176`, plus new tests after `:69`

**Interfaces:**
- Consumes: C1 `FLAG_SETTING_KEYS`, `FLAG_GROUPS`.
- Produces: C7. `DEFAULTS` holds `nsf_carry_over` plus every `FLAG_SETTING_KEYS` key, each `True`. `GET/POST /api/settings` is unchanged (`webapp/app.py:2049-2068`).

- [ ] **Step 1: Write the failing tests.** In `tests/test_webapp_settings.py`, replace lines 1-9:

```python
"""The Settings page's NSF basis toggle (owner ruling, 2026-09-22). Fabricated payloads only."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from webapp.app import app, store
from webapp.settings import DEFAULTS, SETTINGS_FILE, load_settings, save_settings
```

with:

```python
"""The Settings page: the NSF basis toggle (owner ruling, 2026-09-22) and one checkbox per flag group (lender
detection, 2026-09-24). Fabricated payloads only."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from analysis.flag_groups import FLAG_GROUPS, FLAG_SETTING_KEYS
from webapp.app import app, store
from webapp.settings import DEFAULTS, SETTINGS_FILE, load_settings, save_settings

#: The whole settings dict with nothing saved: printed NSF days, and every flag group shown. Spelled out rather
#: than derived, so a key added to DEFAULTS without thinking fails here.
EXPECTED_DEFAULTS = {
    "nsf_carry_over": False,
    "flag_alternative_positions": True,
    "flag_lines_of_credit": True,
    "flag_credit_cards": True,
    "flag_vehicle_financing": True,
    "flag_bank_loans": True,
    "flag_mortgages": True,
    "flag_leases_rentals": True,
    "flag_personal_loans": True,
    "flag_floor_plan": True,
    "flag_factoring": True,
    "flag_premium_financing": True,
}
#: The settings after the NSF toggle alone is turned on: a save merges, so every other key keeps its default.
CARRY_OVER = {**EXPECTED_DEFAULTS, "nsf_carry_over": True}
```

Make these exact edits to the pins:
- `:31`: `    assert load_settings(tmp_path) == {"nsf_carry_over": False} == DEFAULTS` becomes `    assert load_settings(tmp_path) == EXPECTED_DEFAULTS == DEFAULTS`.
- `:41-42`: `== {"nsf_carry_over": True}` becomes `== CARRY_OVER` on both lines. The result is:

```python
    assert save_settings(tmp_path, {"nsf_carry_over": True}) == CARRY_OVER
    assert load_settings(tmp_path) == CARRY_OVER
```

- `:57-61`: the block becomes:

```python
    assert client.get("/api/settings").get_json() == {"settings": EXPECTED_DEFAULTS}
    response = client.post("/api/settings", json={"nsf_carry_over": True})
    assert response.status_code == 200 and response.get_json() == {"settings": CARRY_OVER}
    assert json.loads(settings_file.read_text(encoding="utf-8")) == CARRY_OVER
    assert client.get("/api/settings").get_json() == {"settings": CARRY_OVER}
```

- `:129-130` becomes:

```python
    assert save_settings(settings_file.parent, {"nsf_carry_over": True}) == CARRY_OVER
    assert len(calls) == 3 and load_settings(settings_file.parent) == CARRY_OVER
```

- `:176` becomes `    assert load_settings(tmp_path) == CARRY_OVER and len(calls) == 2`.

Then insert, directly after `test_the_api_refuses_a_form_post_and_unknown_keys_without_echoing_them` (it ends at `:69`, `    assert not settings_file.exists()`):

```python


# --- the flag-group checkboxes (lender detection §8.1) -------------------------------------------------------

def test_every_flag_group_has_a_checkbox_that_is_on_by_default():
    assert FLAG_SETTING_KEYS == tuple(group.setting for group in FLAG_GROUPS)
    assert set(DEFAULTS) == {"nsf_carry_over", *FLAG_SETTING_KEYS}
    assert all(DEFAULTS[key] is True for key in FLAG_SETTING_KEYS)


@pytest.mark.parametrize("key", FLAG_SETTING_KEYS)
@pytest.mark.parametrize("stored", ['"no"', "0", "null"])
def test_a_malformed_checkbox_value_reads_as_shown(tmp_path, key, stored):
    (tmp_path / SETTINGS_FILE).write_text(f'{{"{key}": {stored}}}', encoding="utf-8")
    assert load_settings(tmp_path) == EXPECTED_DEFAULTS


@pytest.mark.parametrize("key", FLAG_SETTING_KEYS)
@pytest.mark.parametrize("value", ["false", 0, None])
def test_a_checkbox_update_that_is_not_a_bool_is_refused_and_writes_nothing(tmp_path, key, value):
    with pytest.raises(ValueError, match=f"setting {key} must be bool"):
        save_settings(tmp_path, {key: value})
    assert not (tmp_path / SETTINGS_FILE).exists()


@pytest.mark.parametrize("key", FLAG_SETTING_KEYS)
def test_the_api_saves_one_checkbox_and_keeps_every_other_setting(settings_file, key):
    client = app.test_client()
    save_settings(settings_file.parent, {"nsf_carry_over": True})
    response = client.post("/api/settings", json={key: False})
    assert response.status_code == 200 and response.get_json() == {"settings": {**CARRY_OVER, key: False}}
    assert json.loads(settings_file.read_text(encoding="utf-8")) == {**CARRY_OVER, key: False}
    assert client.get("/api/settings").get_json() == {"settings": {**CARRY_OVER, key: False}}
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_settings.py -q -p no:cacheprovider
```

Expected: FAIL, `83 failed, 17 passed`:
- the five whole-dict pins still see `{"nsf_carry_over": ...}` alone;
- the new tests fail with the key missing or "unknown setting".

- [ ] **Step 3: Implement.** In `webapp/settings.py`, replace lines 19-28:

```python
from pathlib import Path

SETTINGS_FILE = "settings.json"

#: Every setting, with its default. Unknown keys are refused on save and ignored on load.
DEFAULTS: dict[str, bool] = {
    # Owner ruling, 2026-09-22: the NSF count (negative-ending days) counts printed days only by default.
    # On: a day with no activity carries the previous day's ending balance and counts if it is negative.
    "nsf_carry_over": False,
}
```

with:

```python
from pathlib import Path

from analysis.flag_groups import FLAG_SETTING_KEYS

SETTINGS_FILE = "settings.json"

#: Every setting, with its default. Unknown keys are refused on save and ignored on load.
DEFAULTS: dict[str, bool] = {
    # Owner ruling, 2026-09-22: the NSF count (negative-ending days) counts printed days only by default.
    # On: a day with no activity carries the previous day's ending balance and counts if it is negative.
    "nsf_carry_over": False,
    # Owner ruling, 2026-09-24 (lender detection): one checkbox per flag group (analysis/flag_groups.py), each on
    # by default. Unticking one hides that group wherever an analysis is shown or exported; it never moves a row
    # into review or into lender math (analysis/flagged_view.py).
    **{key: True for key in FLAG_SETTING_KEYS},
}
```

- [ ] **Step 4: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_settings.py -q -p no:cacheprovider
```

Expected: PASS, `100 passed`.

- [ ] **Step 5: Commit.**

```powershell
git add webapp/settings.py tests/test_webapp_settings.py
git commit -m "webapp: one Settings checkbox per flag group, on by default" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 3: Serve the flag groups as Settings ticks them, on a copy

**Files:**
- Create: `tests/flagged_payloads.py`
- Create: `analysis/flagged_view.py`
- Modify: `tools/l1s3_surface_census.py` (one `READERS` entry)
- Test: `tests/test_flagged_view.py` (the whole file is replaced; Task 1's test is kept verbatim)

**Interfaces:**
- Consumes:
  - C1 `FLAG_GROUPS`, `FLAG_GROUP_BY_KEY`;
  - `analysis/payload_shape.py`: `ACCOUNTS_KEY`, `DOCUMENT_SHAPE`, `STATEMENT_KEY`, `PayloadShapeError`, `assert_payload_shape`, `payload_accounts` (verified at `analysis/payload_shape.py:66-205`);
  - `tests/l1s3_payloads.py`: `account_payload(index)`, `document_payload()`.
- Produces:
  - C6 `apply_flagged_groups_to_payload(payload: object, *, enabled: Mapping[str, bool]) -> object`, without `analysis_rules_outdated` until Task 4;
  - `enabled_group_keys(enabled: Mapping[str, bool]) -> frozenset[str]`;
  - the fixture API `FLAGGED_DEBIT`, `CURRENT_VERSION`, `GROUP_KEYS`, `PREMIUM_FINANCING_STATE`, `fabricated_payee(group_key)`, `row_state(group_key)`, `flagged_row(group_key, *, payee=None, amount=-FLAGGED_DEBIT, date="2054-01-05", contributes=None, version=CURRENT_VERSION)`, `with_flagged_rows(payload, rows)`, `flagged_account_payload(index=0, *, groups=GROUP_KEYS, currency="USD", amount=-FLAGGED_DEBIT, date="2054-01-05")`, `flagged_document_payload(*, groups=GROUP_KEYS)`.

- [ ] **Step 1: Write the fixture module and the failing tests.** Create `tests/flagged_payloads.py`:

```python
"""FABRICATED payloads that follow the lender-detection payload contract (plan C4/C5). Never a real statement.

Every payee is an invented name built from its group key, every amount a short named constant, and every date
falls in a year no statement in the archive covers. The rows carry exactly the fields the contract publishes, so
the serving, export and package tests run before the classifier that produces them (service S2) has landed.
"""
from __future__ import annotations

from analysis.flag_groups import FLAG_GROUP_BY_KEY, FLAG_GROUPS
from tests.l1s3_payloads import account_payload, document_payload

#: The invented debit each fabricated flagged row posts. Short and named once, as tests/l1s3_payloads.py does,
#: so no added line carries a figure a real statement could have printed.
FLAGGED_DEBIT = 7.0
#: The classifier version the contract's records carry (C4).
CURRENT_VERSION = "5.0"
#: The flag-group keys in contract order.
GROUP_KEYS = tuple(group.key for group in FLAG_GROUPS)
#: The state a premium-financing row keeps: it has no state of its own and stays insurance (plan contract C1, C4).
PREMIUM_FINANCING_STATE = "insurance"


def fabricated_payee(group_key: str) -> str:
    """An obviously invented payee for one flag group."""
    return f"FABRICATED {group_key.upper()} PAYEE"


def row_state(group_key: str | None) -> str:
    """The classification state a row of `group_key` carries: the group's own state, "insurance" for premium
    financing (C1 `state=None`), or "other" for a row of no flag group."""
    if group_key is None:
        return "other"
    return FLAG_GROUP_BY_KEY[group_key].state or PREMIUM_FINANCING_STATE


def flagged_row(
    group_key: str | None,
    *,
    payee: str | None = None,
    amount: float = -FLAGGED_DEBIT,
    date: str = "2054-01-05",
    contributes: bool | None = None,
    version: str | None = CURRENT_VERSION,
) -> dict:
    """One ledger row whose classification record follows C4. `group_key` None is a row of no flag group.

    `contributes` defaults to the contract rule (a debit of a flag group); pass False for a duplicate or a
    settlement-reversed debit. A premium-financing row is an insurance row that also carries the flag, so its
    `contributes_to_insurance_totals` follows the same rule. `version` None leaves `classification_version` out,
    as a record written before the field existed would."""
    state = row_state(group_key)
    name = payee if payee is not None else (fabricated_payee(group_key) if group_key else None)
    if contributes is None:
        contributes = group_key is not None and amount < 0
    direction = "debit" if amount < 0 else "credit"
    classification = {
        "source_location": None,
        "date": date,
        "amount": amount,
        "direction": direction,
        "classification": state,
        "canonical_entity": name,
        "matched_alias": name,
        "is_posted": True,
        "review_required": False,
        "revenue_classification": None,
        "contributes_to_insurance_totals": state == PREMIUM_FINANCING_STATE and contributes,
        "flagged_group": group_key,
        "contributes_to_flagged_totals": contributes,
    }
    if version is not None:
        classification["classification_version"] = version
    return {
        "date": date,
        "description": f"FABRICATED {state.upper()} ROW",
        "amount": amount,
        "direction": direction,
        "classification": classification,
    }


def with_flagged_rows(payload: dict, rows: list[dict]) -> dict:
    """`payload`, an ACCOUNT payload, with `rows` appended to its ledger (numbered after the rows already there)
    and its `metrics.flagged_groups` and `detection.flagged_positions` rebuilt from the whole ledger the way C5
    publishes them. Mutates and returns `payload`."""
    ledger = payload.setdefault("statement", {}).setdefault("transactions", [])
    for row in rows:
        row["classification"]["source_location"] = f"transaction:{len(ledger) + 1}"
        ledger.append(row)
    by_payee: dict[tuple[str, str], list[dict]] = {}
    for row in ledger:
        record = row.get("classification") or {}
        if record.get("contributes_to_flagged_totals") is True:
            group = record["flagged_group"]
            payee = record.get("canonical_entity") or FLAG_GROUP_BY_KEY[group].label
            by_payee.setdefault((group, payee), []).append(row)
    entries = []
    for (group, payee), members in by_payee.items():
        dates = sorted(row["date"] for row in members)
        entries.append({
            "group": group,
            "payee": payee,
            "matched_alias": payee,
            "count": len(members),
            "total_debited": round(sum(abs(row["amount"]) for row in members), 2),
            "cadence": "single" if len(dates) == 1 else "irregular",
            "avg_gap_days": None,
            "first_date": dates[0],
            "last_date": dates[-1],
            "source_locations": [row["classification"]["source_location"] for row in members],
        })
    entries.sort(key=lambda entry: (GROUP_KEYS.index(entry["group"]), -entry["total_debited"], entry["payee"]))
    summaries: dict[str, dict] = {}
    for entry in entries:
        summary = summaries.setdefault(entry["group"], {"count": 0, "total": 0.0, "payees": 0})
        summary["count"] += entry["count"]
        summary["total"] = round(summary["total"] + entry["total_debited"], 2)
        summary["payees"] += 1
    payload.setdefault("metrics", {})["flagged_groups"] = summaries
    payload.setdefault("detection", {})["flagged_positions"] = entries
    return payload


def flagged_account_payload(
    index: int = 0,
    *,
    groups: tuple[str, ...] = GROUP_KEYS,
    currency: str = "USD",
    amount: float = -FLAGGED_DEBIT,
    date: str = "2054-01-05",
) -> dict:
    """A validated ACCOUNT payload (tests/l1s3_payloads.py) in `currency`, with one fabricated debit of `amount`
    on `date` per group in `groups`, each to its own fabricated payee."""
    payload = account_payload(index)
    payload["statement"]["currency"] = currency
    return with_flagged_rows(payload, [flagged_row(key, amount=amount, date=date) for key in groups])


def flagged_document_payload(*, groups: tuple[str, ...] = GROUP_KEYS) -> dict:
    """The DOCUMENT shape (tests/l1s3_payloads.py): two validated accounts, each with one fabricated debit per
    group in `groups`; the second account's debits are twice the first's."""
    payload = document_payload()
    for index, account in enumerate(payload["accounts"]):
        with_flagged_rows(account, [flagged_row(key, amount=-FLAGGED_DEBIT * (index + 1)) for key in groups])
    return payload
```

Replace the whole of `tests/test_flagged_view.py` with:

```python
"""Flag groups as Settings shows them (lender detection §8.2, plan contract C6). Fabricated payloads only."""
import copy

import pytest

from analysis.flag_groups import FLAG_GROUPS, FLAG_SETTING_KEYS
from analysis.flagged_view import apply_flagged_groups_to_payload, enabled_group_keys
from tests.flagged_payloads import (
    FLAGGED_DEBIT,
    GROUP_KEYS,
    PREMIUM_FINANCING_STATE,
    flagged_account_payload,
    flagged_document_payload,
    flagged_row,
    row_state,
    with_flagged_rows,
)
from tests.l1s3_payloads import account_payload

ALL_TICKED: dict = {}
NONE_TICKED = {key: False for key in FLAG_SETTING_KEYS}
EACH_GROUP = pytest.mark.parametrize("group", FLAG_GROUPS, ids=lambda group: group.key)


def _flagged_rows(account):
    return [row for row in account["statement"]["transactions"] if row["classification"].get("flagged_group")]


def test_the_view_reads_the_eleven_contract_groups():
    assert tuple(group.key for group in FLAG_GROUPS) == (
        "alternative_positions", "lines_of_credit", "credit_cards", "vehicle_financing",
        "bank_loans", "mortgages", "leases_rentals", "personal_loans",
        "floor_plan", "factoring", "premium_financing",
    )
    assert FLAG_SETTING_KEYS == tuple(f"flag_{group.key}" for group in FLAG_GROUPS)
    # Premium financing is the one group with no state of its own: its rows stay insurance (C1, C4).
    assert [group.key for group in FLAG_GROUPS if group.state is None] == ["premium_financing"]


def test_every_group_is_shown_when_nothing_is_unticked():
    shown = apply_flagged_groups_to_payload(flagged_account_payload(), enabled=ALL_TICKED)
    assert list(shown["metrics"]["flagged_groups"]) == list(GROUP_KEYS)
    assert [entry["group"] for entry in shown["detection"]["flagged_positions"]] == list(GROUP_KEYS)
    assert all(row["classification"]["flag_shown"] is True for row in _flagged_rows(shown))
    # The fixture's revenue credit names no flag group, so it carries no flag.
    assert shown["statement"]["transactions"][0]["classification"]["flag_shown"] is False
    assert enabled_group_keys(ALL_TICKED) == frozenset(GROUP_KEYS)


@EACH_GROUP
def test_unticking_a_group_hides_that_group_only(group):
    shown = apply_flagged_groups_to_payload(flagged_account_payload(), enabled={group.setting: False})
    others = [key for key in GROUP_KEYS if key != group.key]
    assert list(shown["metrics"]["flagged_groups"]) == others
    assert [entry["group"] for entry in shown["detection"]["flagged_positions"]] == others
    flags = {row["classification"]["flagged_group"]: row["classification"]["flag_shown"]
             for row in _flagged_rows(shown)}
    assert flags == {key: key != group.key for key in GROUP_KEYS}
    # Hidden, never re-classified: the record keeps its state, its group and its contribution (D7).
    hidden = next(row for row in _flagged_rows(shown) if row["classification"]["flagged_group"] == group.key)
    assert hidden["classification"]["classification"] == row_state(group.key)
    assert hidden["classification"]["contributes_to_flagged_totals"] is True


def test_unticking_premium_financing_hides_the_flag_and_keeps_the_insurance_record():
    # Premium financing has no state of its own: the row stays insurance and keeps its insurance totals (C4).
    payload = flagged_account_payload(groups=("premium_financing",))
    shown = apply_flagged_groups_to_payload(payload, enabled={"flag_premium_financing": False})
    record = shown["statement"]["transactions"][-1]["classification"]
    assert (record["classification"], record["contributes_to_insurance_totals"]) == (PREMIUM_FINANCING_STATE, True)
    assert (record["flagged_group"], record["flag_shown"]) == ("premium_financing", False)
    assert shown["metrics"]["flagged_groups"] == {} and shown["detection"]["flagged_positions"] == []


@EACH_GROUP
def test_a_group_ticked_explicitly_is_shown(group):
    shown = apply_flagged_groups_to_payload(flagged_account_payload(groups=(group.key,)), enabled={group.setting: True})
    assert list(shown["metrics"]["flagged_groups"]) == [group.key]
    assert _flagged_rows(shown)[0]["classification"]["flag_shown"] is True


def test_a_row_that_does_not_count_still_shows_its_group_tag():
    # A proven duplicate keeps its state and its group but contributes nothing; the tag follows the group (C6).
    payload = with_flagged_rows(account_payload(), [flagged_row("mortgages", contributes=False)])
    shown = apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)
    assert shown["statement"]["transactions"][-1]["classification"]["flag_shown"] is True
    assert shown["metrics"]["flagged_groups"] == {}
    assert shown["detection"]["flagged_positions"] == []


@pytest.mark.parametrize("bad", ["fabricated_group", ["mortgages"], 7, None], ids=["unknown", "list", "int", "none"])
def test_a_group_the_contract_does_not_define_is_never_shown(bad):
    payload = flagged_account_payload(groups=("mortgages",))
    payload["statement"]["transactions"][-1]["classification"]["flagged_group"] = bad
    payload["metrics"]["flagged_groups"]["fabricated_group"] = {"count": 1, "total": FLAGGED_DEBIT, "payees": 1}
    payload["detection"]["flagged_positions"].append({"group": bad, "payee": "FABRICATED PAYEE"})
    payload["detection"]["flagged_positions"].append("not an entry")
    shown = apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)
    assert shown["statement"]["transactions"][-1]["classification"]["flag_shown"] is False
    assert list(shown["metrics"]["flagged_groups"]) == ["mortgages"]
    assert [entry["group"] for entry in shown["detection"]["flagged_positions"]] == ["mortgages"]


@pytest.mark.parametrize("build", [flagged_account_payload, flagged_document_payload])
def test_the_stored_payload_is_never_mutated_and_nothing_changed_is_shared(build):
    payload = build()
    stored = copy.deepcopy(payload)
    shown = apply_flagged_groups_to_payload(payload, enabled=NONE_TICKED)
    assert payload == stored
    for served, original in zip(shown.get("accounts") or [shown], payload.get("accounts") or [payload]):
        assert served["detection"]["flagged_positions"] == []
        assert served["statement"]["transactions"] is not original["statement"]["transactions"]
        for served_row, original_row in zip(served["statement"]["transactions"], original["statement"]["transactions"]):
            assert served_row["classification"] is not original_row["classification"]
        assert served["metrics"] is not original["metrics"]
        assert served["detection"] is not original["detection"]
        assert served["detection"]["known_funders"] is not original["detection"]["known_funders"]


@EACH_GROUP
def test_every_account_of_a_document_follows_the_checkbox(group):
    shown = apply_flagged_groups_to_payload(flagged_document_payload(), enabled={group.setting: False})
    assert len(shown["accounts"]) == 2
    for account in shown["accounts"]:
        assert list(account["metrics"]["flagged_groups"]) == [key for key in GROUP_KEYS if key != group.key]
        assert all(entry["group"] != group.key for entry in account["detection"]["flagged_positions"])
        assert [row["classification"]["flag_shown"] for row in _flagged_rows(account)] == [
            key != group.key for key in GROUP_KEYS
        ]
    assert shown["document"] == flagged_document_payload()["document"]


def test_a_payload_without_the_new_fields_keeps_every_stored_value():
    legacy = account_payload()  # classified before flag groups existed: no flagged_group, no flag summaries
    shown = apply_flagged_groups_to_payload(legacy, enabled=NONE_TICKED)
    assert shown["metrics"] == legacy["metrics"]
    assert shown["detection"] == legacy["detection"]
    row = legacy["statement"]["transactions"][0]["classification"]
    assert shown["statement"]["transactions"][0]["classification"] == {**row, "flag_shown": False}


@pytest.mark.parametrize("payload", [None, [], "text", {}, {"accounts": "not a list"}, {"accounts": []},
                                     {"statement": {}, "accounts": []}])
def test_anything_that_is_not_a_published_shape_is_returned_unchanged(payload):
    # `{}` matters beyond tidiness: the package reads a member whose analysis is empty as carrying no currency,
    # and a key added here would make it one that declares none (webapp/app.py::_package_analysis).
    assert apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED) is payload
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py -q -p no:cacheprovider
```

Expected: FAIL at collection with `ModuleNotFoundError: No module named 'analysis.flagged_view'`.

- [ ] **Step 3: Implement.** Create `analysis/flagged_view.py`:

```python
"""Flagged positions as the owner's Settings present them (lender detection, spec §8.2).

The analysis publishes every flag group (analysis/flag_groups.py): each classification record carries
`flagged_group` and `contributes_to_flagged_totals`, each account's metrics carry `flagged_groups`, and its
detection carries `flagged_positions`. Settings has one checkbox per group, on by default. Unticking one HIDES
that group, on a copy, when an analysis is served; it never moves a row into review or into lender math (D7), and
the stored record is never rewritten, so a change applies to every statement at once, old and new, with no
re-analysis. The NSF basis (analysis/nsf_days.py) is the same kind of step.

A presentation step, so it never refuses: a payload that is not one of the two published shapes
(analysis/payload_shape.py) is returned unchanged, for the readers that refuse it to refuse it.
"""
from __future__ import annotations

import copy
from collections.abc import Mapping

from analysis.flag_groups import FLAG_GROUPS
from analysis.payload_shape import (
    ACCOUNTS_KEY,
    DOCUMENT_SHAPE,
    STATEMENT_KEY,
    PayloadShapeError,
    assert_payload_shape,
    payload_accounts,
)

_SURFACE = "analysis/flagged_view.py::apply_flagged_groups_to_payload"


def enabled_group_keys(enabled: Mapping[str, bool]) -> frozenset[str]:
    """The flag-group keys Settings shows. `enabled` is keyed by `FlagGroup.setting`; a missing key is ticked."""
    return frozenset(group.key for group in FLAG_GROUPS if bool(enabled.get(group.setting, True)))


def _is_shown(group: object, shown: frozenset[str]) -> bool:
    """A group key Settings shows. Anything but a string (a malformed stored value) is never shown."""
    return isinstance(group, str) and group in shown


def _shown_account(account: Mapping, shown: frozenset[str]) -> dict:
    """One account with its ledger tagged and its flag summaries cut to the shown groups, on copies.

    Every structure that changes is deep-copied first: the stored job lives in the job store for the life of the
    process, and the review routes persist whatever it holds (webapp/app.py), so a tag written into it would be
    saved by the next review."""
    result = dict(account)
    statement = result.get(STATEMENT_KEY)
    if isinstance(statement, Mapping) and isinstance(statement.get("transactions"), list):
        transactions = copy.deepcopy(statement["transactions"])
        for row in transactions:
            classification = row.get("classification") if isinstance(row, dict) else None
            if isinstance(classification, dict):
                classification["flag_shown"] = _is_shown(classification.get("flagged_group"), shown)
        result[STATEMENT_KEY] = {**statement, "transactions": transactions}
    metrics = result.get("metrics")
    if isinstance(metrics, Mapping):
        metrics = copy.deepcopy(dict(metrics))
        if isinstance(metrics.get("flagged_groups"), dict):
            metrics["flagged_groups"] = {
                key: value for key, value in metrics["flagged_groups"].items() if _is_shown(key, shown)
            }
        result["metrics"] = metrics
    detection = result.get("detection")
    if isinstance(detection, Mapping):
        detection = copy.deepcopy(dict(detection))
        if isinstance(detection.get("flagged_positions"), list):
            detection["flagged_positions"] = [
                entry for entry in detection["flagged_positions"]
                if isinstance(entry, Mapping) and _is_shown(entry.get("group"), shown)
            ]
        result["detection"] = detection
    return result


def apply_flagged_groups_to_payload(payload: object, *, enabled: Mapping[str, bool]) -> object:
    """A copy of a published analysis payload as Settings shows its flag groups (plan contract C6).

    On every account, the account shape or each account of the document shape:
    * `metrics.flagged_groups` and `detection.flagged_positions` keep only the ticked groups;
    * every classification record in `statement.transactions` gains `flag_shown`: it names a flag group, and that
      group is ticked. The record's `flagged_group` and its contribution flags are kept as stored (D7).

    `enabled` is keyed by `FlagGroup.setting`; a missing key counts as ticked. A group key the contract does not
    define is never shown. The input is never mutated."""
    try:
        shape = assert_payload_shape(payload, surface=_SURFACE)
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    shown = enabled_group_keys(enabled)
    if shape == DOCUMENT_SHAPE:
        return {**payload, ACCOUNTS_KEY: [_shown_account(account, shown) for account in accounts]}
    return _shown_account(payload, shown)
```

Then declare the new payload reader in the L1-S3 surface census, as `analysis/nsf_days.py::apply_nsf_basis_to_payload` is declared. `_shown_account` reads each account through the imported name `STATEMENT_KEY`, which the census's reverse sweep does not follow (`_key_aliases` collects only names bound in the module itself, `tools/l1s3_surface_census.py:266-285`). So without this entry the census never sees the reader. With it, the census's forward check holds the function to the `per_account` branch it has: its body calls `assert_payload_shape` and `payload_accounts`.

In `tools/l1s3_surface_census.py`, with the Edit tool, replace this `old_string` (lines 151-152, the `READERS` entry of `webapp/worker.py`):

```python
    ("webapp/worker.py", "_attach_account_confidence", "per_account",
     "each published account takes its own verification score, found through payload_accounts"),
```

with:

```python
    ("webapp/worker.py", "_attach_account_confidence", "per_account",
     "each published account takes its own verification score, found through payload_accounts"),
    ("analysis/flagged_view.py", "apply_flagged_groups_to_payload", "per_account",
     "the flag groups are served per account ledger; every account is tagged, a malformed document passes untouched"),
```

The entry goes before `analysis/nsf_days.py`'s, not after it: S5 appends its own entry after `analysis/nsf_days.py`'s, anchored on that entry and the tuple's closing `)`. Placed here, both edits keep their anchors, and git rebases one onto the other without a conflict.

- [ ] **Step 4: Run the tests, the analysis-layer guards and the surface census.**

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py tests/test_no_fail_open_money_reads.py tests/test_l1s3_census.py -q -p no:cacheprovider
```

Expected:
- `tests/test_flagged_view.py`: `51 passed`;
- the guards pass apart from the known `test_no_literal_account_numbers_in_ocr`. The new module carries no year, amount or account literal, and no function body that copies another;
- `tests/test_l1s3_census.py`: `22 passed`. Run it from a worktree or clone that has no `discovery_reports/`. In the main checkout, the census also sweeps the gitignored `discovery_reports/`, which holds scratch copies of production modules, so there it fails before any S3 change (`2 failed, 20 passed`). A failure that names `analysis/flagged_view.py` means the entry above is missing or misspelled.

- [ ] **Step 5: Commit.**

```powershell
git add analysis/flagged_view.py tests/flagged_payloads.py tests/test_flagged_view.py tools/l1s3_surface_census.py
git commit -m "analysis: serve flag groups as Settings ticks them, on a copy" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 4: Mark analyses classified by older lender rules

**Files:**
- Modify: `analysis/flagged_view.py` (new in Task 3)
- Test: `tests/test_flagged_view.py` (append)

**Interfaces:**
- Consumes: the stored `classification.classification_version` (today `"4.1"`, `analysis/transaction_classifier.py:64,139`; `"5.0"` after S2, C4).
- Produces: C6's top-level `analysis_rules_outdated: bool` on every payload in a published shape. It is consumed by S4 (`#rulesOutdatedNotice`) and S5.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_flagged_view.py`:

```python


# --- analysed with older lender rules (spec §8.2, D12) ------------------------------------------------------------

@pytest.mark.parametrize("version, outdated", [
    ("4.1", True), ("3.0", True), ("4", True), (4, True),
    ("5.0", False), ("5.2", False), ("6.0", False), (None, False), ("unknown", False), (True, False),
])
def test_rows_classified_by_older_rules_mark_the_analysis_outdated(version, outdated):
    payload = with_flagged_rows(account_payload(), [flagged_row(None)])
    payload["statement"]["transactions"][-1]["classification"]["classification_version"] = version
    assert apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)["analysis_rules_outdated"] is outdated


def test_a_fresh_analysis_and_one_without_classified_rows_are_not_outdated():
    assert apply_flagged_groups_to_payload(flagged_account_payload(), enabled=ALL_TICKED)[
        "analysis_rules_outdated"] is False
    assert apply_flagged_groups_to_payload({"statement": {}}, enabled=ALL_TICKED)["analysis_rules_outdated"] is False


def test_one_outdated_account_marks_the_whole_document_at_the_top_level():
    payload = flagged_document_payload()
    payload["accounts"][1]["statement"]["transactions"][-1]["classification"]["classification_version"] = "4.1"
    shown = apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)
    assert shown["analysis_rules_outdated"] is True
    assert all("analysis_rules_outdated" not in account for account in shown["accounts"])
    assert "analysis_rules_outdated" not in payload
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py -q -p no:cacheprovider
```

Expected: FAIL, `12 failed, 51 passed`, each with `KeyError: 'analysis_rules_outdated'`.

- [ ] **Step 3: Implement.** In `analysis/flagged_view.py`:

(a) Replace `_SURFACE = "analysis/flagged_view.py::apply_flagged_groups_to_payload"` with:

```python
_SURFACE = "analysis/flagged_view.py::apply_flagged_groups_to_payload"
#: The first classifier major version that writes flag groups (plan contract C4, `CLASSIFICATION_VERSION`).
FLAG_RULES_MAJOR = 5
#: The top-level key that says the stored rows were classified by older lender rules (spec §8.2, D12).
RULES_OUTDATED_KEY = "analysis_rules_outdated"
```

(b) Insert after the `enabled_group_keys` function:

```python


def _major_version(version: object) -> int | None:
    """The major number of a stored `classification_version` ("4.1" gives 4); None when it cannot be read."""
    if isinstance(version, int) and not isinstance(version, bool):
        return version
    if isinstance(version, str):
        head = version.strip().split(".", 1)[0]
        return int(head) if head.isdigit() else None
    return None


def _rules_outdated(accounts: list[Mapping]) -> bool:
    """Whether any stored record was written by a classifier older than the flag-group rules. Such an analysis
    keeps its stored labels until it is re-analysed (D12); the dashboard says so."""
    for account in accounts:
        statement = account.get(STATEMENT_KEY)
        rows = statement.get("transactions") if isinstance(statement, Mapping) else None
        for row in rows if isinstance(rows, list) else []:
            classification = row.get("classification") if isinstance(row, Mapping) else None
            if not isinstance(classification, Mapping):
                continue
            major = _major_version(classification.get("classification_version"))
            if major is not None and major < FLAG_RULES_MAJOR:
                return True
    return False
```

(c) In `apply_flagged_groups_to_payload`, replace:

```python
    `enabled` is keyed by `FlagGroup.setting`; a missing key counts as ticked. A group key the contract does not
    define is never shown. The input is never mutated."""
    try:
        shape = assert_payload_shape(payload, surface=_SURFACE)
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    shown = enabled_group_keys(enabled)
    if shape == DOCUMENT_SHAPE:
        return {**payload, ACCOUNTS_KEY: [_shown_account(account, shown) for account in accounts]}
    return _shown_account(payload, shown)
```

with:

```python
    At the TOP level it sets `analysis_rules_outdated`: True when any record's `classification_version` has a major
    version below the flag-group rules (D12).

    `enabled` is keyed by `FlagGroup.setting`; a missing key counts as ticked. A group key the contract does not
    define is never shown. The input is never mutated."""
    try:
        shape = assert_payload_shape(payload, surface=_SURFACE)
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    shown = enabled_group_keys(enabled)
    outdated = _rules_outdated(accounts)
    if shape == DOCUMENT_SHAPE:
        return {
            **payload,
            ACCOUNTS_KEY: [_shown_account(account, shown) for account in accounts],
            RULES_OUTDATED_KEY: outdated,
        }
    return {**_shown_account(payload, shown), RULES_OUTDATED_KEY: outdated}
```

- [ ] **Step 4: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py -q -p no:cacheprovider
```

Expected:
- `tests/test_flagged_view.py`: `63 passed`;
- the guards pass apart from the known `test_no_literal_account_numbers_in_ocr`.

- [ ] **Step 5: Commit.**

```powershell
git add analysis/flagged_view.py tests/test_flagged_view.py
git commit -m "analysis: mark analyses classified by older lender rules" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 5: Displayed analyses and package members follow the checkboxes

**Files:**
- Modify: `webapp/app.py:34-36` (imports), `:197-206` (`_displayed`), `:805` and `:811-815` and `:838-841` (`_package_members`), `:917-919` (`_package_analysis` head)
- Create: `tests/test_webapp_flagged_positions.py`

**Interfaces:**
- Consumes:
  - `apply_flagged_groups_to_payload` (Tasks 3-4);
  - `load_settings`, `DEFAULTS` (`webapp/settings.py`);
  - `tests/test_webapp_settings.py`: `_ledger_metrics()` (`:19-25`) and `_roster(main_status)` (`:193-200`).
- Produces (C6):
  - `_displayed(analysis: object, *, carry_over: bool | None = None, settings: dict | None = None) -> object`;
  - `_package_members(jobs, *, settings: dict | None = None) -> tuple[list[tuple], list[dict]]`;
  - `_package_analysis(jobs, *, settings: dict | None = None) -> dict`.

  Every existing caller keeps working unchanged: the routes at `webapp/app.py:2211, 2358, 2422, 2569, 2574, 2579`, and tests that call `_package_members(jobs)` or `_package_analysis(jobs)`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_webapp_flagged_positions.py`:

```python
"""Every served surface follows the flag-group checkboxes (lender detection §8.2-8.4). Fabricated payloads only."""
import copy
import json
from types import SimpleNamespace

import pytest

from analysis.flag_groups import FLAG_GROUPS, FLAG_SETTING_KEYS
from tests.flagged_payloads import (
    FLAGGED_DEBIT,
    GROUP_KEYS,
    flagged_account_payload,
    flagged_document_payload,
    flagged_row,
    with_flagged_rows,
)
from webapp.app import app, store
from webapp.jobs import Job
from webapp.settings import DEFAULTS, SETTINGS_FILE, save_settings

EACH_GROUP = pytest.mark.parametrize("group", FLAG_GROUPS, ids=lambda group: group.key)


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    # The module store's data folder may be a real one ($WEBAPP_DATA_DIR); never touch its settings.
    monkeypatch.setattr(store.storage, "data_dir", tmp_path)
    return tmp_path / SETTINGS_FILE


@pytest.fixture
def done_job(monkeypatch):
    job = SimpleNamespace(id="job-flagged", status="done", analysis=flagged_account_payload(),
                          analysis_error=None, filename="fabricated.pdf", markdown="", html="")
    original = store.get
    monkeypatch.setattr(store, "get", lambda job_id: job if job_id == job.id else original(job_id))
    return job


def _groups(account):
    # A set: Flask serves JSON with its keys sorted, so the served order is not the payload's.
    return set(account["metrics"]["flagged_groups"])


def _flags(account):
    return {row["classification"]["flagged_group"]: row["classification"]["flag_shown"]
            for row in account["statement"]["transactions"] if row["classification"].get("flagged_group")}


def _member(job_id, payload):
    return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)


# --- one statement: the analysis, its JSON export and the review responses (§8.2) ------------------------------

@EACH_GROUP
def test_the_analysis_and_its_json_export_follow_the_checkbox(settings_file, done_job, group):
    client = app.test_client()
    stored = copy.deepcopy(done_job.analysis)
    shown = client.get("/analysis/job-flagged").get_json()["analysis"]
    assert _groups(shown) == set(GROUP_KEYS) and all(_flags(shown).values())
    assert shown["analysis_rules_outdated"] is False
    client.post("/api/settings", json={group.setting: False})
    shown = client.get("/analysis/job-flagged").get_json()["analysis"]
    assert group.key not in _groups(shown)
    assert all(entry["group"] != group.key for entry in shown["detection"]["flagged_positions"])
    assert _flags(shown) == {key: key != group.key for key in GROUP_KEYS}
    exported = json.loads(client.get("/download/job-flagged/json").data)
    assert group.key not in _groups(exported) and _flags(exported)[group.key] is False
    # The stored record is never rewritten by presenting it, and never carries a serving-time tag.
    assert done_job.analysis == stored


def test_displayed_takes_one_settings_snapshot_and_carry_over_still_decides_the_nsf_basis(settings_file):
    from tests.test_webapp_settings import _ledger_metrics
    from webapp.app import _displayed

    payload = flagged_account_payload(groups=("mortgages",))
    payload["metrics"].update(_ledger_metrics())
    snapshot = {**DEFAULTS, "flag_mortgages": False}
    shown = _displayed(payload, settings=snapshot)
    assert shown["metrics"]["effective_nsf_count"] == 1 and shown["metrics"]["flagged_groups"] == {}
    shown = _displayed(payload, carry_over=True, settings=snapshot)
    assert shown["metrics"]["effective_nsf_count"] == 2 and shown["metrics"]["flagged_groups"] == {}
    assert _displayed(payload)["metrics"]["flagged_groups"] == {"mortgages": {"count": 1, "total": FLAGGED_DEBIT,
                                                                              "payees": 1}}
    save_settings(settings_file.parent, {"flag_mortgages": False})
    assert _displayed(payload)["metrics"]["flagged_groups"] == {}


def test_a_review_answers_with_the_checkboxes_applied_and_stores_no_tag(settings_file):
    payload = flagged_account_payload()
    credit = flagged_row(None, amount=FLAGGED_DEBIT, date="2054-01-06")
    credit["classification"].update({
        "revenue_classification": "unverified_deposit",
        "revenue_initial_classification": "unverified_deposit",
        "revenue_review_required": True,
    })
    with_flagged_rows(payload, [credit])
    job = store.create("fabricated-review.pdf")
    store.set_result(job.id, "# fabricated", "<h1>fabricated</h1>", analysis=payload)
    save_settings(settings_file.parent, {"flag_mortgages": False})
    response = app.test_client().post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": credit["classification"]["source_location"], "decision": "confirm"},
    )
    assert response.status_code == 200
    shown = response.get_json()["analysis"]
    assert "mortgages" not in _groups(shown) and _flags(shown)["mortgages"] is False
    stored = store.get(job.id).analysis
    assert "mortgages" in _groups(stored)
    assert all("flag_shown" not in row["classification"] for row in stored["statement"]["transactions"])
    assert "analysis_rules_outdated" not in stored


# --- package members (§8.2) -----------------------------------------------------------------------------------

@EACH_GROUP
def test_package_members_carry_the_displayed_checkboxes(settings_file, done_job, group):
    from webapp.app import _package_members

    members, _ = _package_members([done_job])
    assert group.key in _groups(members[0][1])
    save_settings(settings_file.parent, {group.setting: False})
    members, _ = _package_members([done_job])
    assert group.key not in _groups(members[0][1]) and _flags(members[0][1])[group.key] is False


@EACH_GROUP
def test_every_published_account_of_a_document_member_follows_the_checkbox(settings_file, group):
    from webapp.app import _package_members

    job = Job(id="doc", filename="doc.pdf", status="done", analysis=flagged_document_payload(), content_sha256="doc")
    save_settings(settings_file.parent, {group.setting: False})
    members, excluded = _package_members([job])
    assert [member[2] for member in members] == [1, 2] and excluded == []
    for _job, account, _index, _count in members:
        assert group.key not in _groups(account) and _flags(account)[group.key] is False


def test_the_checkboxes_never_change_which_accounts_a_package_leaves_out(settings_file):
    # The exclusions read the roster off the displayed copy (webapp/app.py::_package_members); the flag step
    # touches only each account's rows, metrics and detection, so the idle and unverified main-account rules
    # decide the same way whatever is ticked, and the stored records are never rewritten.
    from tests.test_webapp_settings import _roster
    from webapp.app import _package_members

    def document_job(job_id, roster=None):
        payload = flagged_document_payload()
        if roster is not None:
            payload["document"]["account_roster"] = roster
        return Job(id=job_id, filename=f"{job_id}.pdf", status="done", analysis=payload, content_sha256=job_id)

    jobs = [document_job("idle", _roster("idle")), document_job("held", _roster("held")),
            document_job("verified", _roster("published")), document_job("no-roster")]
    stored = [copy.deepcopy(job.analysis) for job in jobs]

    def decided():
        members, excluded = _package_members(jobs)
        return sorted((member[0].id, member[2]) for member in members), excluded

    ticked = decided()
    save_settings(settings_file.parent, {key: False for key in FLAG_SETTING_KEYS})
    assert decided() == ticked
    assert [item["reason"] for item in ticked[1]] == ["main_account_idle", "main_account_unverified"]
    assert [job.analysis for job in jobs] == stored


def test_a_package_reads_the_settings_once_and_hands_that_snapshot_to_every_member(settings_file, monkeypatch):
    # One read per package (spec §8.2, C6). Every member's displayed copy, and the flag roll-up (Task 7), use that
    # one snapshot, so a checkbox saved mid-request cannot split a package across two sets of ticked groups.
    from webapp.app import _package_analysis, _package_members
    from webapp.settings import load_settings

    reads = []

    def counting_load(data_dir):
        reads.append(data_dir)
        return load_settings(data_dir)

    monkeypatch.setattr("webapp.app.load_settings", counting_load)
    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    _package_analysis(jobs)
    assert len(reads) == 1
    _package_members(jobs)
    assert len(reads) == 2
    # A caller that passes the snapshot reads nothing more.
    _package_analysis(jobs, settings=dict(DEFAULTS))
    _package_members(jobs, settings=dict(DEFAULTS))
    assert len(reads) == 2


def test_package_members_follow_the_snapshot_they_are_handed_not_the_file(settings_file):
    from webapp.app import _package_analysis

    save_settings(settings_file.parent, dict(DEFAULTS))  # the file ticks every group
    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    package = _package_analysis(jobs, settings={**DEFAULTS, "flag_mortgages": False})
    records = [row["classification"] for row in package["transactions"] if row["classification"].get("flagged_group")]
    assert len(records) == 2 * len(GROUP_KEYS)
    assert all(record["flag_shown"] is (record["flagged_group"] != "mortgages") for record in records)
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_positions.py -q -p no:cacheprovider
```

Expected: FAIL, `37 failed, 1 passed`. Every test fails except `test_the_checkboxes_never_change_which_accounts_a_package_leaves_out`, which guards behaviour that must not change:
- the served analysis has no `analysis_rules_outdated` and no `flag_shown`, so `KeyError`;
- `_displayed() got an unexpected keyword argument 'settings'`, a `TypeError`;
- `_package_analysis() got an unexpected keyword argument 'settings'`, a `TypeError`, in the two snapshot tests;
- package members still show the unticked group.

- [ ] **Step 3: Implement.** In `webapp/app.py`:

(a) Imports. Replace:

```python
from analysis.nsf_days import apply_nsf_basis_to_payload
from .jobs import JobStore
from .settings import load_settings, save_settings
```

with:

```python
from analysis.nsf_days import apply_nsf_basis_to_payload
from analysis.flagged_view import apply_flagged_groups_to_payload
from .jobs import JobStore
from .settings import DEFAULTS as SETTINGS_DEFAULTS, load_settings, save_settings
```

(b) `_displayed` (`:197-206`). Replace the whole function with:

```python
def _displayed(
    analysis: object, *, carry_over: bool | None = None, settings: dict | None = None
) -> object:
    """A stored analysis as the dashboard presents it: the owner's Settings applied to a COPY.

    Two settings apply. The NSF basis (analysis/nsf_days.py): printed days by default, or every calendar day with
    the balance carried over inactive days when Settings turns carry-over on. And the flag groups
    (analysis/flagged_view.py): an unticked group is hidden from the summaries and its rows lose their flag.
    Every surface that shows or exports an analysis goes through here, so the dashboard, the downloads and the
    package agree; the stored record is never rewritten, and a change of setting applies to every job at once.

    `settings` is a snapshot of every setting, read here once when it is not passed; `carry_over`, when given,
    still decides the NSF basis."""
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    if carry_over is None:
        carry_over = settings.get("nsf_carry_over", SETTINGS_DEFAULTS["nsf_carry_over"])
    rebased = apply_nsf_basis_to_payload(analysis, carry_over=carry_over)
    return apply_flagged_groups_to_payload(rebased, enabled=settings)
```

(c) `_package_members` signature (`:805`). Replace `def _package_members(jobs) -> tuple[list[tuple], list[dict]]:` with:

```python
def _package_members(jobs, *, settings: dict | None = None) -> tuple[list[tuple], list[dict]]:
```

In its docstring (`:812-815`), replace:

```
    shows it (`_displayed`: the owner's NSF basis applied to a copy; the stored
    record is never rewritten and every other field is the stored one). The
    NSF basis is read once per package, so a setting saved mid-request cannot
    split the members across two bases.
```

with:

```
    shows it (`_displayed`: the owner's NSF basis and flag groups applied to a
    copy; the stored record is never rewritten and every other field is the
    stored one). Settings are read once per package — here, or by the caller
    that passes `settings` — so a setting saved mid-request cannot split the
    members across two NSF bases or two sets of ticked flag groups.
```

Replace `:838-841`:

```python
    # One read per package, so a setting saved mid-request cannot split the members across two NSF bases.
    carry_over = load_settings(store.storage.data_dir)["nsf_carry_over"]
    for job in jobs:
        analysis = _displayed(job.analysis or {}, carry_over=carry_over)
```

with:

```python
    # One read per package, so a setting saved mid-request cannot split the members across two NSF bases or two
    # sets of ticked flag groups.
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    for job in jobs:
        analysis = _displayed(job.analysis or {}, settings=settings)
```

(d) `_package_analysis` head (`:917-919`). Replace:

```python
def _package_analysis(jobs) -> dict:
    duplicate_of, duplicate_groups = _package_duplicates(jobs)
    members, excluded_accounts = _package_members(jobs)
```

with:

```python
def _package_analysis(jobs, *, settings: dict | None = None) -> dict:
    # The one settings snapshot this package is built on: its members are displayed with it, and its flag roll-up
    # keeps the groups it ticks.
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    duplicate_of, duplicate_groups = _package_duplicates(jobs)
    members, excluded_accounts = _package_members(jobs, settings=settings)
```

- [ ] **Step 4: Run the new tests and the surfaces that already go through `_displayed`.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_positions.py tests/test_webapp_settings.py tests/test_nsf_days.py tests/test_l1s3_surfaces.py tests/test_webapp_app.py tests/test_webapp_security.py tests/test_package_currency.py -q -p no:cacheprovider
```

Expected: PASS, `345 passed` in all. `tests/test_webapp_flagged_positions.py` has `38 passed`, and every other file is green as before.

Both snapshot tests are needed. If `_package_members` ignored the snapshot it is handed and called `_displayed(job.analysis or {})`, every other test here would still pass, because each of them saves its settings to the file. The counting test then sees three reads, and the other test sees the unticked mortgages still tagged.

- [ ] **Step 5: Commit.**

```powershell
git add webapp/app.py tests/test_webapp_flagged_positions.py
git commit -m "webapp: displayed analyses and package members follow the flag checkboxes" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 6: Readable flagged rows in the statement CSV and XLSX

**Files:**
- Modify: `webapp/app.py`:
  - the imports (after Task 5);
  - `:360-366`, the detection loop of `_account_analysis_rows`;
  - a new `_flagged_position_rows` directly after it.
- Test: `tests/test_webapp_flagged_positions.py` (imports; append)

**Interfaces:**
- Consumes:
  - the displayed `detection.flagged_positions` (C5 entries, already filtered to ticked groups);
  - C1 `FLAG_GROUP_BY_KEY`.
- Produces:
  - `_flagged_position_rows(positions: object) -> list[tuple[str, str, object]]`;
  - sections `flagged_<group>_<n>` with the fields `payee`, `count`, `total_debited` and `cadence`, which a document payload prefixes `account_<i>.`.

  The rows reach files only through `_escaped_rows` (`webapp/app.py:373, 460`).

- [ ] **Step 1: Write the failing tests.** In `tests/test_webapp_flagged_positions.py`, replace the import head:

```python
import copy
import json
from types import SimpleNamespace
```

with:

```python
import copy
import csv
import io
import json
import zipfile
from types import SimpleNamespace
```

Then replace:

```python
    FLAGGED_DEBIT,
    GROUP_KEYS,
    flagged_account_payload,
```

with:

```python
    FLAGGED_DEBIT,
    GROUP_KEYS,
    fabricated_payee,
    flagged_account_payload,
```

and replace `from webapp.app import app, store` with:

```python
from tests.l1s3_payloads import account_payload
from webapp.app import app, store
```

Append to the end of the file:

```python


# --- one statement: the CSV and XLSX exports (§8.4) -------------------------------------------------------------

def _csv_cells(text):
    return {(row[0], row[1]): row[2] for row in list(csv.reader(io.StringIO(text)))[1:]}


def _sheet(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return archive.read("xl/worksheets/sheet1.xml").decode("utf-8")


@EACH_GROUP
def test_the_csv_and_xlsx_exports_carry_readable_rows_for_ticked_groups_only(settings_file, done_job, group):
    client = app.test_client()
    section = f"flagged_{group.key}_1"
    cells = _csv_cells(client.get("/download/job-flagged/csv").get_data(as_text=True))
    assert cells[(section, "payee")] == fabricated_payee(group.key)
    assert cells[(section, "count")] == "1"
    assert cells[(section, "total_debited")] == str(FLAGGED_DEBIT)
    assert cells[(section, "cadence")] == "single"
    assert ("detection", "flagged_positions") not in cells  # the readable rows replace the JSON cell
    assert f"<t>{section}</t>" in _sheet(client.get("/download/job-flagged/xlsx").get_data())
    client.post("/api/settings", json={group.setting: False})
    cells = _csv_cells(client.get("/download/job-flagged/csv").get_data(as_text=True))
    assert not [key for key in cells if key[0].startswith(f"flagged_{group.key}_")]
    assert len({key[0] for key in cells if key[0].startswith("flagged_")}) == len(GROUP_KEYS) - 1
    assert f"<t>{section}</t>" not in _sheet(client.get("/download/job-flagged/xlsx").get_data())


def test_every_account_of_a_document_gets_its_own_flagged_rows():
    from webapp.app import _analysis_rows

    rows = _analysis_rows(flagged_document_payload(groups=("mortgages",)))
    assert {"account_1.flagged_mortgages_1", "account_2.flagged_mortgages_1"} <= {section for section, _f, _v in rows}


def test_two_payees_of_one_group_are_numbered_in_the_payload_order():
    from webapp.app import _analysis_rows

    payload = with_flagged_rows(account_payload(), [
        flagged_row("mortgages", payee="FABRICATED MORTGAGE A"),
        flagged_row("mortgages", payee="FABRICATED MORTGAGE B", amount=-2 * FLAGGED_DEBIT),
    ])
    payees = {section: value for section, field, value in _analysis_rows(payload) if field == "payee"}
    assert payees == {"flagged_mortgages_1": "FABRICATED MORTGAGE B", "flagged_mortgages_2": "FABRICATED MORTGAGE A"}


def test_a_payee_that_reads_as_a_formula_is_escaped_in_both_sheets():
    from webapp.app import _analysis_csv, _analysis_xlsx, _displayed

    payload = with_flagged_rows(account_payload(), [flagged_row("mortgages", payee="=FABRICATED(1)")])
    shown = _displayed(payload, settings=dict(DEFAULTS))
    assert "flagged_mortgages_1,payee,'=FABRICATED(1)" in _analysis_csv(shown)
    sheet = _sheet(_analysis_xlsx(shown))
    assert "<t>'=FABRICATED(1)</t>" in sheet and "<t>=FABRICATED(1)</t>" not in sheet
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_positions.py -q -p no:cacheprovider
```

Expected: FAIL, `14 failed, 38 passed`. The 14 are the new tests:
- the `KeyError` is `('flagged_<group>_1', 'payee')`, because only the `detection.flagged_positions` JSON cell exists today;
- the document, numbering and formula tests find no `flagged_` section.

- [ ] **Step 3: Implement.** In `webapp/app.py`:

(a) Imports. Replace:

```python
from analysis.nsf_days import apply_nsf_basis_to_payload
from analysis.flagged_view import apply_flagged_groups_to_payload
```

with:

```python
from analysis.nsf_days import apply_nsf_basis_to_payload
from analysis.flag_groups import FLAG_GROUP_BY_KEY
from analysis.flagged_view import apply_flagged_groups_to_payload
```

(b) Replace the end of `_account_analysis_rows` (`:360-366`):

```python
    detection = analysis.get("detection")
    if isinstance(detection, dict):
        for key, item in detection.items():
            if isinstance(item, (dict, list)):
                item = json.dumps(item)
            rows.append(("detection", key, "" if item is None else item))
    return rows
```

with:

```python
    detection = analysis.get("detection")
    if isinstance(detection, dict):
        for key, item in detection.items():
            if key == "flagged_positions":
                continue  # emitted as readable rows below
            if isinstance(item, (dict, list)):
                item = json.dumps(item)
            rows.append(("detection", key, "" if item is None else item))
        rows.extend(_flagged_position_rows(detection.get("flagged_positions")))
    return rows


def _flagged_position_rows(positions: object) -> list[tuple[str, str, object]]:
    """An account's flagged positions, one readable section per payee (lender detection §8.4):
    `flagged_<group>_<n>` with the payee, its debit count, the total debited and the cadence.

    Served payloads hold only the ticked groups (analysis/flagged_view.py via `_displayed`), so the sheet follows
    Settings. A payee name is statement text: these rows reach a file only through `_escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    numbers: dict[str, int] = {}
    for entry in positions if isinstance(positions, list) else []:
        group = entry.get("group") if isinstance(entry, dict) else None
        if not isinstance(group, str) or group not in FLAG_GROUP_BY_KEY:
            continue
        numbers[group] = numbers.get(group, 0) + 1
        for field in ("payee", "count", "total_debited", "cadence"):
            value = entry.get(field)
            rows.append((f"flagged_{group}_{numbers[group]}", field, "" if value is None else value))
    return rows
```

- [ ] **Step 4: Run them, with the export pins.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_positions.py tests/test_l1s3_surfaces.py tests/test_webapp_security.py tests/test_webapp_app.py -q -p no:cacheprovider
```

Expected: PASS.
- `tests/test_webapp_flagged_positions.py` has `52 passed`; the whole command, `207 passed`.
- `tests/test_l1s3_surfaces.py::test_the_export_sheet_is_unchanged_for_one_account` (`:49-57`) stays green, because `account_payload()` publishes no `flagged_positions`.

- [ ] **Step 5: Commit.**

```powershell
git add webapp/app.py tests/test_webapp_flagged_positions.py
git commit -m "webapp: readable flagged rows in the statement CSV and XLSX" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 7: The package roll-up of the ticked flag groups

**Files:**
- Modify `webapp/app.py`:
  - imports;
  - three helpers after `_contributes_to_potential_totals` (`:505-509`);
  - inside `_package_analysis`:
    - the head (after Task 5);
    - the containers `:996-998`;
    - after `insurance_rows` `:1140-1144`;
    - after the insurance roll-up `:1475-1494`;
    - the ledger evidence `:1525-1526`;
    - after the roll-up sorts `:1820-1822`;
    - the return `:1938-1944`.
- Test: `tests/test_webapp_flagged_positions.py` (append).

**Interfaces:**
- Consumes:
  - each member's displayed rows with `classification.contributes_to_flagged_totals` and `classification.flagged_group` (C4). `statement_transactions` has already dropped the internal-transfer positions (`webapp/app.py:1070-1081`);
  - `enabled_group_keys` (Task 3);
  - `analysis.dates.parse_date(value) -> date | None` (`analysis/dates.py:46-66`, verified never to raise).
- Produces:
  - `_counts_as_flagged(classification: dict, shown: frozenset[str]) -> bool`;
  - `_add_flagged_rows(rollup: dict[tuple[str, str], dict], rows: list[dict]) -> None`;
  - `_published_flagged_positions(rollup) -> dict[str, list[dict]]`;
  - on the package: `flagged_positions: {group: [{payee, documents, count, total_debited, first_date, last_date}]}` for the ticked groups that have a counted row, in C1 order. `cadence` arrives in Task 10;
  - `flagged_evidence: [classification record + source_job + source_document (+ source_account)]`.

  The lender totals, the withholding and `decision` are untouched.

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_webapp_flagged_positions.py`:

```python


# --- the package roll-up (§8.3) -------------------------------------------------------------------------------

def _not_flagged(totals):
    return {key: value for key, value in totals.items() if not key.startswith("flagged_")}


def test_the_package_rolls_up_each_ticked_group_across_members(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([
        _member("a", flagged_account_payload(0)),
        _member("b", flagged_account_payload(1, amount=-3.0, date="2054-01-12")),
    ])
    assert list(package["flagged_positions"]) == list(GROUP_KEYS)
    for key in GROUP_KEYS:
        [item] = package["flagged_positions"][key]
        assert item["payee"] == fabricated_payee(key)
        assert (item["documents"], item["count"], item["total_debited"]) == (2, 2, FLAGGED_DEBIT + 3.0)
        assert (item["first_date"], item["last_date"]) == ("2054-01-05", "2054-01-12")
    assert len(package["flagged_evidence"]) == 2 * len(GROUP_KEYS)
    assert {evidence["source_job"] for evidence in package["flagged_evidence"]} == {"a", "b"}
    assert all("source_account" not in evidence for evidence in package["flagged_evidence"])


def test_a_row_without_a_named_payee_rolls_up_under_its_group_label(settings_file):
    from analysis.flag_groups import FLAG_GROUP_BY_KEY
    from webapp.app import _package_analysis

    payload = with_flagged_rows(account_payload(), [flagged_row("bank_loans", payee="")])
    [item] = _package_analysis([_member("a", payload)])["flagged_positions"]["bank_loans"]
    assert item["payee"] == FLAG_GROUP_BY_KEY["bank_loans"].label


def test_a_row_the_analysis_does_not_count_never_enters_the_roll_up(settings_file):
    from webapp.app import _package_analysis

    payload = with_flagged_rows(account_payload(), [flagged_row("mortgages"),
                                                    flagged_row("mortgages", contributes=False)])
    package = _package_analysis([_member("a", payload)])
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["count"], item["total_debited"]) == (1, FLAGGED_DEBIT)
    assert len(package["flagged_evidence"]) == 1


@EACH_GROUP
def test_an_unticked_group_leaves_the_package_and_nothing_else_moves(settings_file, group):
    from webapp.app import _package_analysis

    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    ticked = _package_analysis(jobs)
    save_settings(settings_file.parent, {group.setting: False})
    unticked = _package_analysis(jobs)
    assert set(unticked["flagged_positions"]) == set(GROUP_KEYS) - {group.key}
    assert all(evidence["flagged_group"] != group.key for evidence in unticked["flagged_evidence"])
    # D7: the lender totals, the withholding and the decision never read a flag group or its checkbox.
    assert _not_flagged(unticked["totals"]) == _not_flagged(ticked["totals"])
    assert ticked["totals"]["decision"] == "approved"
    assert unticked["funders"] == ticked["funders"] and unticked["potential_lenders"] == ticked["potential_lenders"]


def test_premium_financing_stays_insurance_whether_or_not_it_is_flagged(settings_file):
    from webapp.app import _package_analysis

    jobs = [_member("a", flagged_account_payload(0, groups=("premium_financing",))),
            _member("b", flagged_account_payload(1, groups=("premium_financing",)))]
    ticked = _package_analysis(jobs)
    [item] = ticked["flagged_positions"]["premium_financing"]
    assert (item["count"], item["total_debited"]) == (2, 2 * FLAGGED_DEBIT)
    assert (ticked["totals"]["insurance_count"], ticked["totals"]["insurance_total"]) == (2, 2 * FLAGGED_DEBIT)
    save_settings(settings_file.parent, {"flag_premium_financing": False})
    unticked = _package_analysis(jobs)
    assert unticked["flagged_positions"] == {} and unticked["flagged_evidence"] == []
    # The checkbox hides the flag only: the rows are still insurance, counted and evidenced as today.
    assert (unticked["totals"]["insurance_count"], unticked["totals"]["insurance_total"]) == (2, 2 * FLAGGED_DEBIT)
    assert [evidence["source_job"] for evidence in unticked["insurance_evidence"]] == ["a", "b"]


def test_the_roll_up_reads_the_same_snapshot_as_the_member_rows(settings_file):
    # Spec §8.2: the members' tags and the roll-up come from ONE snapshot. The file ticks every group and the
    # snapshot unticks premium financing, so a roll-up that re-read the file would still show it.
    from webapp.app import _package_analysis

    save_settings(settings_file.parent, dict(DEFAULTS))
    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    package = _package_analysis(jobs, settings={**DEFAULTS, "flag_premium_financing": False})
    assert set(package["flagged_positions"]) == set(GROUP_KEYS) - {"premium_financing"}
    assert {evidence["flagged_group"] for evidence in package["flagged_evidence"]} == set(package["flagged_positions"])
    tagged = {row["classification"]["flagged_group"] for row in package["transactions"]
              if row["classification"]["flag_shown"]}
    assert tagged == set(package["flagged_positions"])
    # Hidden, never re-classified: both premium-financing rows still count as insurance (C4, D7).
    assert package["totals"]["insurance_count"] == 2


def test_flag_evidence_of_a_document_member_names_its_account(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([_member("doc", flagged_document_payload(groups=("mortgages",)))])
    assert [(evidence["source_job"], evidence["source_account"], evidence["source_location"])
            for evidence in package["flagged_evidence"]] == [("doc", 1, "transaction:2"), ("doc", 2, "transaction:2")]
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["documents"], item["count"], item["total_debited"]) == (2, 2, 3 * FLAGGED_DEBIT)


def test_an_internal_transfer_leg_never_enters_the_flag_roll_up(settings_file):
    from webapp.app import _package_analysis

    payload = flagged_document_payload(groups=("mortgages",))
    # Account 1's ledger holds its revenue credit at position 0 and its flagged debit at position 1; the document
    # pairs that debit with account 2's credit as one movement between its own accounts.
    payload["document"]["internal_transfers"] = [{"a": [0, 1], "b": [1, 0]}]
    package = _package_analysis([_member("doc", payload)])
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["documents"], item["count"], item["total_debited"]) == (1, 1, 2 * FLAGGED_DEBIT)
    assert [evidence["source_account"] for evidence in package["flagged_evidence"]] == [2]


def test_a_package_of_payloads_without_flag_groups_rolls_up_nothing(settings_file):
    from tests.test_package_currency import member
    from webapp.app import _package_analysis

    package = _package_analysis([member("a", "USD"), _member("b", account_payload())])
    assert package["flagged_positions"] == {} and package["flagged_evidence"] == []
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_positions.py -q -p no:cacheprovider
```

Expected: FAIL, `19 failed, 52 passed`. The 19 new tests fail with `KeyError: 'flagged_positions'` or `KeyError: 'flagged_evidence'`, because the package publishes neither.

- [ ] **Step 3: Implement.** In `webapp/app.py`:

(a) Imports. Replace:

```python
from analysis.flag_groups import FLAG_GROUP_BY_KEY
from analysis.flagged_view import apply_flagged_groups_to_payload
```

with:

```python
from analysis.dates import parse_date
from analysis.flag_groups import FLAG_GROUP_BY_KEY, FLAG_GROUPS
from analysis.flagged_view import apply_flagged_groups_to_payload, enabled_group_keys
```

(b) Helpers. Insert directly after `_contributes_to_potential_totals` (the function ends with `    return classification.get("contributes_to_potential_lender_count") is True`):

```python


def _counts_as_flagged(classification: dict, shown: frozenset[str]) -> bool:
    """A row the package's flag roll-up counts: the analysis marked it a contributing debit of a flag group
    (`contributes_to_flagged_totals`: posted, not a proven duplicate, not settlement-reversed), and Settings ticks
    its group."""
    group = classification.get("flagged_group")
    return (
        classification.get("contributes_to_flagged_totals") is True
        and isinstance(group, str)
        and group in shown
    )


def _add_flagged_rows(rollup: dict[tuple[str, str], dict], rows: list[dict]) -> None:
    """Fold one member's counted flag rows into the package roll-up, keyed by (group, payee).

    The payee is the row's canonical entity, or its group's label when the analysis named none (plan contract
    C5). `documents` counts the members a payee appears in, as the funder roll-up does. The dates are kept so the
    first and last dates, and the cadence, are read across every member rather than per statement."""
    seen: set[tuple[str, str]] = set()
    for row in rows:
        classification = row["classification"]
        group = classification["flagged_group"]
        entity = classification.get("canonical_entity")
        payee = entity if isinstance(entity, str) and entity else FLAG_GROUP_BY_KEY[group].label
        item = rollup.setdefault(
            (group, payee),
            {"payee": payee, "documents": 0, "count": 0, "total_debited": 0.0, "dates": []},
        )
        if (group, payee) not in seen:
            seen.add((group, payee))
            item["documents"] += 1
        item["count"] += 1
        item["total_debited"] = round(item["total_debited"] + abs(_num(row.get("amount"))), 2)
        posted = parse_date(row.get("date") or classification.get("date"))
        if posted is not None:
            item["dates"].append(posted)


def _published_flagged_positions(rollup: dict[tuple[str, str], dict]) -> dict[str, list[dict]]:
    """The package's `flagged_positions` (plan contract C6): each ticked group with a counted row, in contract
    order, as a list of `{payee, documents, count, total_debited, first_date, last_date}`, largest total first."""
    published: dict[str, list[dict]] = {}
    for group in FLAG_GROUPS:
        items = []
        for (key, _payee), item in rollup.items():
            if key != group.key:
                continue
            dates = sorted(item["dates"])
            items.append({
                "payee": item["payee"],
                "documents": item["documents"],
                "count": item["count"],
                "total_debited": item["total_debited"],
                "first_date": dates[0].isoformat() if dates else None,
                "last_date": dates[-1].isoformat() if dates else None,
            })
        if items:
            published[group.key] = sorted(items, key=lambda item: (-item["total_debited"], item["payee"]))
    return published
```

(c) The shown groups. In `_package_analysis`, replace:

```python
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    duplicate_of, duplicate_groups = _package_duplicates(jobs)
```

with:

```python
    if settings is None:
        settings = load_settings(store.storage.data_dir)
    shown_groups = enabled_group_keys(settings)
    duplicate_of, duplicate_groups = _package_duplicates(jobs)
```

(d) Containers (`:996-999`). Replace:

```python
    package_revenue_evidence: dict[str, list[dict]] = {
        state: [] for state in REVENUE_STATES
    }
    denominator_modes: set[str] = set()
```

with:

```python
    package_revenue_evidence: dict[str, list[dict]] = {
        state: [] for state in REVENUE_STATES
    }
    #: (group key, payee) -> the running roll-up of the ticked flag groups (lender detection §8.3).
    flagged_rollup: dict[tuple[str, str], dict] = {}
    package_flagged_evidence: list[dict] = []
    denominator_modes: set[str] = set()
```

(e) Row selection (`:1140-1145`). Replace:

```python
            if transaction["classification"].get("contributes_to_insurance_totals") is True
        ]
        positive_statement_rows = [
```

with:

```python
            if transaction["classification"].get("contributes_to_insurance_totals") is True
        ]
        flagged_rows = [
            transaction
            for transaction in authoritative_rows
            if _counts_as_flagged(transaction["classification"], shown_groups)
        ]
        positive_statement_rows = [
```

(f) Roll-up (`:1487-1496`). Replace:

```python
            package_insurance_matches.append(
                {
                    "provider": name,
                    "source_job": job.id,
                    "transactions": match.get("transactions") or [],
                    "evidence": match.get("evidence") or [],
                }
            )

        # Flattened ledger so the dashboard can show every statement's rows at once.
```

with:

```python
            package_insurance_matches.append(
                {
                    "provider": name,
                    "source_job": job.id,
                    "transactions": match.get("transactions") or [],
                    "evidence": match.get("evidence") or [],
                }
            )

        # Flag groups (lender detection §8.3): the ticked groups' counted rows of this member's ledger, less its
        # internal-transfer legs. They never reach the lender totals, the withholding or the decision (D7).
        _add_flagged_rows(flagged_rollup, flagged_rows)

        # Flattened ledger so the dashboard can show every statement's rows at once.
```

(g) Evidence (`:1525-1527`). Replace:

```python
            if classification.get("contributes_to_insurance_totals") is True:
                package_insurance_evidence.append(evidence)
            revenue_state = classification.get("revenue_classification")
```

with:

```python
            if classification.get("contributes_to_insurance_totals") is True:
                package_insurance_evidence.append(evidence)
            if _counts_as_flagged(classification, shown_groups):
                # A location is numbered within its own account, so a multi-account member's evidence names it.
                package_flagged_evidence.append(
                    evidence if account_index is None else {**evidence, "source_account": account_index}
                )
            revenue_state = classification.get("revenue_classification")
```

(h) Publication (`:1820-1822`). Replace:

```python
    package_potential_lenders = sorted(
        potential_lenders.values(), key=lambda r: r["funder"]
    )
```

with:

```python
    package_potential_lenders = sorted(
        potential_lenders.values(), key=lambda r: r["funder"]
    )
    package_flagged_positions = _published_flagged_positions(flagged_rollup)
```

(i) Return (`:1940-1944`). Replace:

```python
        "insurance_providers": package_insurance_providers,
        "transactions": package_transactions,
        "lender_evidence": package_lender_evidence,
        "potential_lender_evidence": package_potential_lender_evidence,
        "insurance_evidence": package_insurance_evidence,
        "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
```

with:

```python
        "insurance_providers": package_insurance_providers,
        # Lender detection §8.3: the ticked flag groups, never lender math.
        "flagged_positions": package_flagged_positions,
        "transactions": package_transactions,
        "lender_evidence": package_lender_evidence,
        "potential_lender_evidence": package_potential_lender_evidence,
        "insurance_evidence": package_insurance_evidence,
        "flagged_evidence": package_flagged_evidence,
        "verified_revenue_evidence": package_revenue_evidence["verified_revenue"],
```

This match is unique: the `detection` mirror at `:1950-1962` has no `"insurance_providers": package_insurance_providers,` line.

- [ ] **Step 4: Run them, with every package test.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_positions.py tests/test_package_currency.py tests/test_webapp_settings.py tests/test_l1s3_surfaces.py tests/test_webapp_app.py tests/test_adb.py -q -p no:cacheprovider
```

Expected: PASS, `370 passed` in all. `tests/test_webapp_flagged_positions.py` has `71 passed`. `test_package_currency.py` is unchanged, and its sweep still sees no `flagged_` section, because its members carry no flag rows until Task 9.

- [ ] **Step 5: Commit.**

```powershell
git add webapp/app.py tests/test_webapp_flagged_positions.py
git commit -m "webapp: package roll-up and evidence of the ticked flag groups" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 8: Flagged package totals and the currency refusal

**Files:**
- Modify `webapp/app.py`:
  - `_published_flagged_positions` (Task 7);
  - `_CROSS_CURRENCY_TOTAL_KEYS` `:536-569`;
  - the totals init `:977-979`;
  - after `:1694-1695`;
  - the publication call (Task 7);
  - the refusal loop `:1899-1906`.
- Test:
  - `tests/test_package_currency.py`: `:39-41` (imports), `:45-78`, `:83-109`, `:716`, and insert before `:401`;
  - `tests/test_webapp_flagged_positions.py` (append).

**Interfaces:**
- Consumes: `refuse_cross_currency` (`webapp/app.py:1792`) and `_CROSS_CURRENCY_ROLLUP_KEYS`, whose `total_debited` is already there (`:582-587`).
- Produces:
  - `totals.flagged_position_count`: int, the ticked groups' counted debits;
  - `totals.flagged_position_total`: money, their sum;
  - `_published_flagged_positions(rollup, *, refuse_cross_currency: bool)`.

  Under a currency refusal:
  - `flagged_position_total` and every roll-up item's `total_debited` are None;
  - the counts survive;
  - items are ordered by count descending, then payee.

- [ ] **Step 1: Write the failing tests.** In `tests/test_package_currency.py`:

(a) Replace:

```python
from webapp.jobs import Job

ROOT = Path(__file__).resolve().parents[1]
```

with:

```python
from webapp.jobs import Job
from tests.flagged_payloads import FLAGGED_DEBIT, flagged_row, with_flagged_rows

ROOT = Path(__file__).resolve().parents[1]
```

(b) In `EXPECTED_REFUSED_TOTALS`, replace:

```python
    "eligible_deposits",
    "insurance_total",
    "lender_debits",
```

with:

```python
    "eligible_deposits",
    "flagged_position_total",
    "insurance_total",
    "lender_debits",
```

(c) In `UNIT_FREE_TOTALS`, replace:

```python
    "failed",
    "insurance_count",
```

with:

```python
    "failed",
    "flagged_position_count",
    "insurance_count",
```

(d) At `:716`, replace `    assert len(body["currency"]["refused_total_fields"]) == 32` with `    assert len(body["currency"]["refused_total_fields"]) == 33`.

(e) Insert directly before `def test_statement_level_results_survive_a_mixed_currency_refusal():` (`:401`):

```python
def test_mixed_currency_refusal_covers_the_flag_roll_up():
    """Lender detection §8.3. The flag roll-up sums money across members exactly as the funder roll-up does, so
    a refused package publishes its counts and none of its money."""
    cad, usd = member("a", "CAD"), member("b", "USD")
    with_flagged_rows(cad.analysis, [flagged_row("credit_cards")])
    with_flagged_rows(usd.analysis, [flagged_row("credit_cards")])
    package = _package_analysis([cad, usd])
    assert package["totals"]["flagged_position_total"] is None
    assert package["totals"]["flagged_position_count"] == 2
    [item] = package["flagged_positions"]["credit_cards"]
    assert item["total_debited"] is None
    assert (item["documents"], item["count"]) == (2, 2)


def test_refused_packages_rank_flagged_positions_by_count_then_payee():
    """MINOR-1's rule, applied to the flag roll-up: no row order read off a cross-currency magnitude."""
    def build(first_currency, second_currency):
        big = member("a", first_currency)
        with_flagged_rows(big.analysis, [flagged_row("mortgages", payee="ZZZ FABRICATED BIG",
                                                     amount=-100 * FLAGGED_DEBIT)])
        many = member("b", second_currency)
        with_flagged_rows(many.analysis, [flagged_row("mortgages", payee="AAA FABRICATED MANY") for _ in range(3)])
        return _package_analysis([big, many])

    refused = build("CAD", "USD")
    assert [item["payee"] for item in refused["flagged_positions"]["mortgages"]] == [
        "AAA FABRICATED MANY", "ZZZ FABRICATED BIG"]
    single = build("CAD", "CAD")
    assert [item["payee"] for item in single["flagged_positions"]["mortgages"]] == [
        "ZZZ FABRICATED BIG", "AAA FABRICATED MANY"]
    assert single["totals"]["flagged_position_count"] == 4
    assert single["totals"]["flagged_position_total"] == 103 * FLAGGED_DEBIT


```

Append to `tests/test_webapp_flagged_positions.py`:

```python


@EACH_GROUP
def test_the_package_totals_count_the_debits_of_ticked_groups_only(settings_file, group):
    from webapp.app import _package_analysis

    # Two members, one debit per group each: every group counts two debits and debits both amounts.
    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1, amount=-3.0))]
    per_group = FLAGGED_DEBIT + 3.0
    totals = _package_analysis(jobs)["totals"]
    assert (totals["flagged_position_count"], totals["flagged_position_total"]) == (
        2 * len(GROUP_KEYS), len(GROUP_KEYS) * per_group)
    save_settings(settings_file.parent, {group.setting: False})
    totals = _package_analysis(jobs)["totals"]
    assert (totals["flagged_position_count"], totals["flagged_position_total"]) == (
        2 * (len(GROUP_KEYS) - 1), (len(GROUP_KEYS) - 1) * per_group)


def test_a_package_without_flag_groups_publishes_zero_flagged_totals(settings_file):
    from webapp.app import _package_analysis

    totals = _package_analysis([_member("b", account_payload())])["totals"]
    assert (totals["flagged_position_count"], totals["flagged_position_total"]) == (0, 0.0)


def test_a_member_without_analysis_adds_nothing_to_the_flag_roll_up(settings_file):
    # Mirrors the NSF basis test of the same shape (tests/test_webapp_settings.py): a failed member has no analysis.
    from webapp.app import _package_analysis

    done = _member("a", flagged_account_payload(0, groups=("mortgages",)))
    failed = Job(id="b", filename="b.pdf", status="failed", analysis=None, content_sha256="b")
    package = _package_analysis([done, failed])
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["documents"], item["count"], package["totals"]["flagged_position_count"]) == (1, 1, 1)
    alone = _package_analysis([failed])
    assert alone["flagged_positions"] == {} and alone["totals"]["flagged_position_count"] == 0
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_package_currency.py tests/test_webapp_flagged_positions.py -q -p no:cacheprovider
```

Expected: FAIL, `20 failed, 108 passed`. In `tests/test_package_currency.py`, seven fail:
- `test_mixed_currency_package_refuses_every_cross_currency_total`: `KeyError: 'flagged_position_total'`, because the package publishes no such total yet;
- `test_mixed_currency_refusal_leaves_every_count_intact`: `KeyError: 'flagged_position_count'`;
- `test_refused_field_list_matches_the_constant_and_the_payload`: `_CROSS_CURRENCY_TOTAL_KEYS` lacks `flagged_position_total`;
- `test_csv_export_carries_the_refusal_and_never_a_mixed_number`: `KeyError: ('totals', 'flagged_position_total')`;
- `test_the_route_serves_the_undetermined_bucket_end_to_end`: `assert 32 == 33`;
- the two new tests: `KeyError: 'flagged_position_total'`, and the money order under refusal.

In `tests/test_webapp_flagged_positions.py`, the 13 new totals tests fail with `KeyError`.

- [ ] **Step 3: Implement.** In `webapp/app.py`:

(a) Replace the whole `_published_flagged_positions` from Task 7 with:

```python
def _published_flagged_positions(
    rollup: dict[tuple[str, str], dict], *, refuse_cross_currency: bool
) -> dict[str, list[dict]]:
    """The package's `flagged_positions` (plan contract C6): each ticked group with a counted row, in contract
    order, as a list of `{payee, documents, count, total_debited, first_date, last_date}`.

    Largest total first; a package that refuses to combine currencies ranks by the unit-free count, then the
    payee, because an order read off summed money would publish the cross-currency comparison the refusal
    withholds (CURRENCY DOCTRINE §F)."""
    published: dict[str, list[dict]] = {}
    for group in FLAG_GROUPS:
        items = []
        for (key, _payee), item in rollup.items():
            if key != group.key:
                continue
            dates = sorted(item["dates"])
            items.append({
                "payee": item["payee"],
                "documents": item["documents"],
                "count": item["count"],
                "total_debited": item["total_debited"],
                "first_date": dates[0].isoformat() if dates else None,
                "last_date": dates[-1].isoformat() if dates else None,
            })
        if not items:
            continue
        if refuse_cross_currency:
            published[group.key] = sorted(items, key=lambda item: (-item["count"], item["payee"]))
        else:
            published[group.key] = sorted(items, key=lambda item: (-item["total_debited"], item["payee"]))
    return published
```

(b) In `_CROSS_CURRENCY_TOTAL_KEYS`, replace:

```python
    "eligible_deposits",
    "insurance_total",
```

with:

```python
    "eligible_deposits",
    "flagged_position_total",
    "insurance_total",
```

(c) Totals init (`:978-979`). Replace:

```python
        "insurance_total": 0.0,
        "withholding_numerator": 0.0,
```

with:

```python
        "insurance_total": 0.0,
        # Lender detection §8.3: the ticked flag groups' counted debits and their total. Never lender math (D7).
        "flagged_position_count": 0,
        "flagged_position_total": 0.0,
        "withholding_numerator": 0.0,
```

(d) After the loop (`:1694-1695`). Replace:

```python
    totals["lenders_detected"] = len(funders)
    totals["potential_lenders_detected"] = len(potential_lenders)
```

with:

```python
    totals["lenders_detected"] = len(funders)
    totals["potential_lenders_detected"] = len(potential_lenders)
    totals["flagged_position_count"] = sum(item["count"] for item in flagged_rollup.values())
    totals["flagged_position_total"] = round(sum(item["total_debited"] for item in flagged_rollup.values()), 2)
```

(e) Publication. Replace `    package_flagged_positions = _published_flagged_positions(flagged_rollup)` with:

```python
    package_flagged_positions = _published_flagged_positions(
        flagged_rollup, refuse_cross_currency=refuse_cross_currency
    )
```

(f) The refusal loop (`:1899-1903`). Replace:

```python
            *package_insurance_providers,
        ):
```

with:

```python
            *package_insurance_providers,
            *(item for items in package_flagged_positions.values() for item in items),
        ):
```

- [ ] **Step 4: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_package_currency.py tests/test_webapp_flagged_positions.py tests/test_webapp_settings.py tests/test_webapp_app.py tests/test_l1s3_surfaces.py -q -p no:cacheprovider
```

Expected: PASS, `313 passed` in all.
- `tests/test_package_currency.py`: `44 passed`.
- `tests/test_webapp_flagged_positions.py`: `84 passed`.

- [ ] **Step 5: Commit.**

```powershell
git add webapp/app.py tests/test_package_currency.py tests/test_webapp_flagged_positions.py
git commit -m "webapp: flagged package totals and their currency refusal" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 9: Flagged rows in the package CSV and XLSX; widen the currency sweep

**Files:**
- Modify: `webapp/app.py`, `_package_rows`, after the `insurance_provider_{n}` loop (`:405-407`).
- Test:
  - `tests/test_package_currency.py`: imports, `:565-571`, `:595-597`, `:625-628`;
  - `tests/test_webapp_flagged_positions.py` (append).

**Interfaces:**
- Consumes: the package's `flagged_positions` (Tasks 7-8).
- Produces: `flagged_<group>_<n>` sections carrying every field of each roll-up item, written through `_package_csv`/`_package_xlsx`, and so through `_escaped_rows`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_package_currency.py`:

(a) Replace:

```python
from webapp.jobs import Job
from tests.flagged_payloads import FLAGGED_DEBIT, flagged_row, with_flagged_rows
```

with:

```python
from analysis.flag_groups import FLAG_GROUPS
from webapp.jobs import Job
from tests.flagged_payloads import FLAGGED_DEBIT, flagged_row, with_flagged_rows
```

(b) Replace `:565-571`:

```python
#: Sections that aggregate ACROSS documents. Matched exactly so that
#: `potential_lender_evidence_3` — a per-transaction classification record, and
#: therefore statement-level — is not mistaken for the `potential_lender_3`
#: rollup.
CROSS_DOCUMENT_SECTION = re.compile(
    r"^(totals|funder_\d+|potential_lender_\d+|insurance_provider_\d+)$"
)
```

with:

```python
#: Sections that aggregate ACROSS documents. Matched exactly so that
#: `potential_lender_evidence_3` — a per-transaction classification record, and
#: therefore statement-level — is not mistaken for the `potential_lender_3`
#: rollup. The flag roll-up (`flagged_<group>_<n>`, lender detection §8.4) is
#: named group by group for the same reason.
CROSS_DOCUMENT_SECTION = re.compile(
    r"^(totals|funder_\d+|potential_lender_\d+|insurance_provider_\d+"
    r"|flagged_(?:" + "|".join(group.key for group in FLAG_GROUPS) + r")_\d+)$"
)
```

(c) In `test_every_money_row_the_export_emits_is_covered_by_a_declared_currency`, replace:

```python
    package = _package_analysis([member("a", "CAD"), member("b", "USD")])
    rows = _package_rows(package)
    assert package["totals"]["cross_currency_totals_refused"] is True
```

with:

```python
    cad, usd = member("a", "CAD"), member("b", "USD")
    for job in (cad, usd):
        # A flag roll-up in the refused package, so the flagged sections are swept too.
        with_flagged_rows(job.analysis, [flagged_row("credit_cards")])
    package = _package_analysis([cad, usd])
    rows = _package_rows(package)
    assert package["totals"]["cross_currency_totals_refused"] is True
```

and replace:

```python
    assert any(s.startswith("insurance_provider_") for s in exercised)
```

with:

```python
    assert any(s.startswith("insurance_provider_") for s in exercised)
    assert any(s.startswith("flagged_credit_cards_") for s in exercised)
```

Append to `tests/test_webapp_flagged_positions.py`:

```python


# --- the package CSV and XLSX (§8.4) -------------------------------------------------------------------------

@EACH_GROUP
def test_the_package_csv_and_xlsx_carry_the_ticked_groups_only(settings_file, group):
    from webapp.app import _package_analysis, _package_csv, _package_xlsx

    jobs = [_member("a", flagged_account_payload(0)), _member("b", flagged_account_payload(1))]
    section = f"flagged_{group.key}_1"
    package = _package_analysis(jobs)
    cells = _csv_cells(_package_csv(package))
    assert cells[(section, "payee")] == fabricated_payee(group.key)
    assert (cells[(section, "documents")], cells[(section, "count")]) == ("2", "2")
    assert cells[(section, "total_debited")] == str(2 * FLAGGED_DEBIT)
    assert cells[("totals", "flagged_position_count")] == str(2 * len(GROUP_KEYS))
    assert f"<t>{section}</t>" in _sheet(_package_xlsx(package))
    save_settings(settings_file.parent, {group.setting: False})
    package = _package_analysis(jobs)
    cells = _csv_cells(_package_csv(package))
    assert not [key for key in cells if key[0].startswith(f"flagged_{group.key}_")]
    assert f"<t>{section}</t>" not in _sheet(_package_xlsx(package))


def test_a_package_payee_that_reads_as_a_formula_is_escaped(settings_file):
    from webapp.app import _package_analysis, _package_csv, _package_xlsx

    payload = with_flagged_rows(account_payload(), [flagged_row("mortgages", payee="=FABRICATED(1)")])
    package = _package_analysis([_member("a", payload)])
    assert "flagged_mortgages_1,payee,'=FABRICATED(1)" in _package_csv(package)
    sheet = _sheet(_package_xlsx(package))
    assert "<t>'=FABRICATED(1)</t>" in sheet and "<t>=FABRICATED(1)</t>" not in sheet


def test_the_package_routes_follow_the_checkboxes(settings_file):
    ids = []
    for index in (0, 1):
        job = store.create(f"fabricated-{index}.pdf")
        store.set_result(job.id, "# fabricated", "<h1>fabricated</h1>", analysis=flagged_account_payload(index))
        ids.append(job.id)
    client = app.test_client()
    save_settings(settings_file.parent, {"flag_credit_cards": False})
    served = client.get(f"/package_analysis?ids={','.join(ids)}").get_json()
    assert "credit_cards" not in served["flagged_positions"] and "mortgages" in served["flagged_positions"]
    cells = _csv_cells(client.get(f"/package_download/csv?ids={','.join(ids)}").get_data(as_text=True))
    assert ("flagged_mortgages_1", "payee") in cells
    assert not [key for key in cells if key[0].startswith("flagged_credit_cards_")]
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_package_currency.py tests/test_webapp_flagged_positions.py -q -p no:cacheprovider
```

Expected: FAIL, `14 failed, 127 passed`:
- `test_every_money_row_the_export_emits_is_covered_by_a_declared_currency`: the sweep's new `exercised` assertion finds no `flagged_credit_cards_` section, because `_package_rows` writes none;
- the 13 new package-export tests fail with `KeyError: ('flagged_<group>_1', 'payee')`, or find no formula row.

- [ ] **Step 3: Implement.** In `webapp/app.py::_package_rows`, replace:

```python
    for idx, provider in enumerate(package.get("insurance_providers") or [], start=1):
        for key, value in provider.items():
            rows.append((f"insurance_provider_{idx}", key, "" if value is None else value))
```

with:

```python
    for idx, provider in enumerate(package.get("insurance_providers") or [], start=1):
        for key, value in provider.items():
            rows.append((f"insurance_provider_{idx}", key, "" if value is None else value))
    # Lender detection §8.4: one section per flagged payee, `flagged_<group>_<n>`. The package holds only the
    # groups Settings ticks, so the sheet follows Settings.
    for group, items in (package.get("flagged_positions") or {}).items():
        for idx, item in enumerate(items, start=1):
            for key, value in item.items():
                rows.append((f"flagged_{group}_{idx}", key, "" if value is None else value))
```

- [ ] **Step 4: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_package_currency.py tests/test_webapp_flagged_positions.py tests/test_webapp_security.py tests/test_webapp_app.py tests/test_l1s3_surfaces.py -q -p no:cacheprovider
```

Expected: PASS, `296 passed` in all.
- `tests/test_package_currency.py`: `44 passed`. The sweep now reads every `flagged_credit_cards_<n>` cell of a refused package: `total_debited` is empty, and `count`/`documents` are unit-free.
- `tests/test_webapp_flagged_positions.py`: `97 passed`.

- [ ] **Step 5: Commit.**

```powershell
git add webapp/app.py tests/test_package_currency.py tests/test_webapp_flagged_positions.py
git commit -m "webapp: flagged rows in the package CSV and XLSX; widen the currency sweep" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 12: Flagged credits in serving, the package roll-up, the exports and the currency sweep (runs after Task 9, before Tasks 10-11)

The owner ruled on 2026-09-26 that a factoring payee's credit is the business's sales, paid by the factor that bought its invoices: it stays revenue, and it also carries the Factoring flag. The master plan's C4, C5 and C6 carry the ruling since that date:
- C4: a factoring credit is a row of state `factoring` with `flagged_group="factoring"` and, when posted, `contributes_to_flagged_totals`;
- C5: every `metrics.flagged_groups` value and every `detection.flagged_positions` entry gains `count_credited` and `total_credited`, while `count` and `total_debited` stay debit-only;
- C6: the package roll-up item gains the same two fields, and the package totals gain `flagged_position_count_credited` and `flagged_position_total_credited`.

This task serves, filters, rolls up, exports and currency-checks the credited fields exactly as it does the debited ones.

**Why it runs now, before Tasks 10-11.**
- It needs nothing from S2. Its tests build fabricated payloads that follow the amended C4/C5 (`tests/flagged_payloads.py`), as Tasks 1-9 do, so it runs while S2 does its own Task 18 (the classifier's side of the ruling).
- Tasks 10 and 11 build on it, and this plan writes them that way (amended 2026-09-26). Task 10 replaces the whole `_published_flagged_positions` with its cadence version, and that version keeps the credited fields. Task 10's field-order test and Task 11's C5 key sets and conformance test name them too. Run in the other order, Task 10 would drop the credited fields, and Task 11's key-set test would fail on S2's payload, which carries them once S2 merges with its Task 18.
- Serving needs no code change. `apply_flagged_groups_to_payload` keys on `flagged_group`, so a credit row of a ticked group gets `flag_shown`, and its group's summaries keep their credited fields. Two tests pin that, and they pass before the implementation.

**Files:**
- Modify `webapp/app.py`:
  - `_flagged_position_rows` (Task 6);
  - the `_counts_as_flagged` docstring and `_add_flagged_rows` (Task 7);
  - `_published_flagged_positions` (Task 8);
  - `_CROSS_CURRENCY_TOTAL_KEYS` and `_CROSS_CURRENCY_ROLLUP_KEYS`;
  - the package totals: their initial values and their computation (Task 8).
- Modify `tests/flagged_payloads.py`: `CREDITED_GROUP_KEYS`, and the `flagged_row` and `with_flagged_rows` fixtures.
- Test:
  - `tests/test_flagged_view.py` (append);
  - `tests/test_webapp_flagged_positions.py` (one pin, then append);
  - `tests/test_package_currency.py`: the three key sets, the refused-field count, the currency sweep, and two tests inserted after `test_refused_packages_rank_flagged_positions_by_count_then_payee`.

**Interfaces:**
- Consumes:
  - C4 as amended: a factoring credit row `{"classification": "factoring", "flagged_group": "factoring", "contributes_to_flagged_totals": true, "amount": > 0, ...}`, and no other group's credit contributes;
  - C5 as amended: `count_credited` and `total_credited` on `metrics.flagged_groups` values and `detection.flagged_positions` entries;
  - Tasks 6-9: `_flagged_position_rows`, `_counts_as_flagged`, `_add_flagged_rows`, `_published_flagged_positions`, `refuse_cross_currency`, `_package_rows`, and the fixtures `flagged_row`, `with_flagged_rows`, `account_payload`, `FLAGGED_DEBIT`.
- Produces (C6 as amended 2026-09-26):
  - package roll-up items `{payee, documents, count, total_debited, count_credited, total_credited, first_date, last_date}`, where Task 10 adds `cadence` after `total_credited`. `count` and `total_debited` hold the debits, and `count_credited` and `total_credited` the credits. The dates read both.
  - Order within a group: `total_debited + total_credited` descending, then payee. A refused package orders by `count + count_credited` descending, then payee.
  - `totals.flagged_position_count_credited` (int, unit-free) and `totals.flagged_position_total_credited` (money). `flagged_position_count` and `flagged_position_total` stay debit-only.
  - `total_credited` joins `_CROSS_CURRENCY_ROLLUP_KEYS`, and `flagged_position_total_credited` joins `_CROSS_CURRENCY_TOTAL_KEYS` (34 refused totals).
  - The statement sheets' `flagged_<group>_<n>` sections carry `payee, count, total_debited, count_credited, total_credited, cadence`. The package sheets carry every item and total field.
  - The fixtures: `CREDITED_GROUP_KEYS = ("factoring",)`. `flagged_row`'s default `contributes` holds for a debit of a flag group or a credit of a credited group. `with_flagged_rows` builds C5 as amended.

- [ ] **Step 1: Write the failing tests.** In `tests/flagged_payloads.py`:

(a) Replace:

```python
PREMIUM_FINANCING_STATE = "insurance"
```

with:

```python
PREMIUM_FINANCING_STATE = "insurance"
#: The groups whose posted credits count in the flagged totals (plan contract C4; owner ruling 2026-09-26: a
#: factor's payout is the business's own sales, stays revenue and carries the Factoring flag).
CREDITED_GROUP_KEYS = ("factoring",)
```

(b) Replace:

```python
    `contributes` defaults to the contract rule (a debit of a flag group); pass False for a duplicate or a
    settlement-reversed debit. A premium-financing row is an insurance row that also carries the flag, so its
    `contributes_to_insurance_totals` follows the same rule. `version` None leaves `classification_version` out,
    as a record written before the field existed would."""
    state = row_state(group_key)
    name = payee if payee is not None else (fabricated_payee(group_key) if group_key else None)
    if contributes is None:
        contributes = group_key is not None and amount < 0
```

with:

```python
    `contributes` defaults to the contract rule (a debit of a flag group, or a credit of a CREDITED_GROUP_KEYS
    group); pass False for a duplicate or a reversed row. A premium-financing row is an insurance row that also
    carries the flag, so its `contributes_to_insurance_totals` follows the same rule. `version` None leaves
    `classification_version` out, as a record written before the field existed would."""
    state = row_state(group_key)
    name = payee if payee is not None else (fabricated_payee(group_key) if group_key else None)
    if contributes is None:
        contributes = group_key is not None and (amount < 0 or (amount > 0 and group_key in CREDITED_GROUP_KEYS))
```

(c) Replace:

```python
    entries = []
    for (group, payee), members in by_payee.items():
        dates = sorted(row["date"] for row in members)
        entries.append({
            "group": group,
            "payee": payee,
            "matched_alias": payee,
            "count": len(members),
            "total_debited": round(sum(abs(row["amount"]) for row in members), 2),
            "cadence": "single" if len(dates) == 1 else "irregular",
            "avg_gap_days": None,
            "first_date": dates[0],
            "last_date": dates[-1],
            "source_locations": [row["classification"]["source_location"] for row in members],
        })
    entries.sort(key=lambda entry: (GROUP_KEYS.index(entry["group"]), -entry["total_debited"], entry["payee"]))
    summaries: dict[str, dict] = {}
    for entry in entries:
        summary = summaries.setdefault(entry["group"], {"count": 0, "total": 0.0, "payees": 0})
        summary["count"] += entry["count"]
        summary["total"] = round(summary["total"] + entry["total_debited"], 2)
        summary["payees"] += 1
```

with:

```python
    entries = []
    for (group, payee), members in by_payee.items():
        dates = sorted(row["date"] for row in members)
        debits = [row for row in members if row["amount"] < 0]
        credits = [row for row in members if row["amount"] >= 0]
        entries.append({
            "group": group,
            "payee": payee,
            "matched_alias": payee,
            "count": len(debits),
            "total_debited": round(sum(abs(row["amount"]) for row in debits), 2),
            "count_credited": len(credits),
            "total_credited": round(sum(row["amount"] for row in credits), 2),
            "cadence": "single" if len(dates) == 1 else "irregular",
            "avg_gap_days": None,
            "first_date": dates[0],
            "last_date": dates[-1],
            "source_locations": [row["classification"]["source_location"] for row in members],
        })
    entries.sort(key=lambda entry: (GROUP_KEYS.index(entry["group"]),
                                    -(entry["total_debited"] + entry["total_credited"]), entry["payee"]))
    summaries: dict[str, dict] = {}
    for entry in entries:
        summary = summaries.setdefault(
            entry["group"], {"count": 0, "total": 0.0, "count_credited": 0, "total_credited": 0.0, "payees": 0})
        summary["count"] += entry["count"]
        summary["total"] = round(summary["total"] + entry["total_debited"], 2)
        summary["count_credited"] += entry["count_credited"]
        summary["total_credited"] = round(summary["total_credited"] + entry["total_credited"], 2)
        summary["payees"] += 1
```

Append to `tests/test_flagged_view.py`:

```python


def test_a_flagged_credit_is_shown_and_hidden_with_its_group():
    """Owner ruling 2026-09-26 (C4): a factor's payout is a credit row of the Factoring group. It is tagged and its
    credited figures are served while the group is ticked, and both go when it is unticked; the record is kept."""
    payload = with_flagged_rows(account_payload(), [flagged_row("factoring", amount=3 * FLAGGED_DEBIT)])
    shown = apply_flagged_groups_to_payload(payload, enabled=ALL_TICKED)
    [credit] = _flagged_rows(shown)
    assert (credit["amount"] > 0, credit["classification"]["flag_shown"]) == (True, True)
    assert shown["metrics"]["flagged_groups"]["factoring"]["count_credited"] == 1
    assert shown["detection"]["flagged_positions"][0]["total_credited"] == 3 * FLAGGED_DEBIT
    hidden = apply_flagged_groups_to_payload(payload, enabled={"flag_factoring": False})
    [credit] = _flagged_rows(hidden)
    assert credit["classification"]["flag_shown"] is False
    assert credit["classification"]["contributes_to_flagged_totals"] is True
    assert hidden["metrics"]["flagged_groups"] == {} and hidden["detection"]["flagged_positions"] == []
```

In `tests/test_webapp_flagged_positions.py`:

(d) Replace:

```python
    assert _displayed(payload)["metrics"]["flagged_groups"] == {"mortgages": {"count": 1, "total": FLAGGED_DEBIT,
                                                                              "payees": 1}}
```

with:

```python
    assert _displayed(payload)["metrics"]["flagged_groups"] == {"mortgages": {
        "count": 1, "total": FLAGGED_DEBIT, "count_credited": 0, "total_credited": 0.0, "payees": 1}}
```

Append to `tests/test_webapp_flagged_positions.py`:

```python


# --- flagged credits: a factor's payouts (owner ruling 2026-09-26; contract C4-C6) -----------------------------

#: What each fabricated factoring credit posts: three times a flagged debit, so the two totals never coincide.
FACTOR_PAYOUT = 3 * FLAGGED_DEBIT


def _factored(index=0, *, payee=None, payouts=1, date="2054-01-12"):
    """An ACCOUNT payload whose factoring payee is paid one debit and pays in `payouts` credits (C4)."""
    return with_flagged_rows(account_payload(index), [
        flagged_row("factoring", payee=payee),
        *(flagged_row("factoring", payee=payee, amount=FACTOR_PAYOUT, date=date) for _ in range(payouts)),
    ])


def test_a_factoring_credit_is_served_flagged_and_follows_its_checkbox(settings_file):
    from webapp.app import _displayed

    shown = _displayed(_factored(), settings=dict(DEFAULTS))
    assert shown["metrics"]["flagged_groups"] == {"factoring": {
        "count": 1, "total": FLAGGED_DEBIT, "count_credited": 1, "total_credited": FACTOR_PAYOUT, "payees": 1}}
    [entry] = shown["detection"]["flagged_positions"]
    assert (entry["count"], entry["total_debited"], entry["count_credited"], entry["total_credited"]) == (
        1, FLAGGED_DEBIT, 1, FACTOR_PAYOUT)
    rows = [row for row in shown["statement"]["transactions"] if row["classification"].get("flagged_group")]
    assert [(row["amount"] > 0, row["classification"]["flag_shown"]) for row in rows] == [(False, True), (True, True)]
    hidden = _displayed(_factored(), settings={**DEFAULTS, "flag_factoring": False})
    assert hidden["metrics"]["flagged_groups"] == {} and hidden["detection"]["flagged_positions"] == []
    assert not [row for row in hidden["statement"]["transactions"] if row["classification"]["flag_shown"]]


def test_the_statement_csv_and_xlsx_carry_the_credited_fields(settings_file):
    from webapp.app import _analysis_csv, _analysis_xlsx, _displayed

    shown = _displayed(_factored(), settings=dict(DEFAULTS))
    cells = _csv_cells(_analysis_csv(shown))
    assert (cells[("flagged_factoring_1", "count")], cells[("flagged_factoring_1", "total_debited")]) == (
        "1", str(FLAGGED_DEBIT))
    assert (cells[("flagged_factoring_1", "count_credited")], cells[("flagged_factoring_1", "total_credited")]) == (
        "1", str(FACTOR_PAYOUT))
    assert "<t>total_credited</t>" in _sheet(_analysis_xlsx(shown))


def test_the_package_rolls_up_credits_apart_from_debits(settings_file):
    from webapp.app import _package_analysis

    jobs = [_member("a", _factored(0)), _member("b", _factored(1, date="2054-01-19"))]
    package = _package_analysis(jobs)
    [item] = package["flagged_positions"]["factoring"]
    assert (item["documents"], item["count"], item["total_debited"]) == (2, 2, 2 * FLAGGED_DEBIT)
    assert (item["count_credited"], item["total_credited"]) == (2, 2 * FACTOR_PAYOUT)
    # The dates are every counted row's, debit or credit.
    assert (item["first_date"], item["last_date"]) == ("2054-01-05", "2054-01-19")
    totals = package["totals"]
    # flagged_position_count and flagged_position_total stay debits only (C6).
    assert (totals["flagged_position_count"], totals["flagged_position_total"]) == (2, 2 * FLAGGED_DEBIT)
    assert (totals["flagged_position_count_credited"], totals["flagged_position_total_credited"]) == (
        2, 2 * FACTOR_PAYOUT)
    assert len(package["flagged_evidence"]) == 4
    # D7: the credits never touch the decision, and unticking the group moves nothing but the flag figures.
    save_settings(settings_file.parent, {"flag_factoring": False})
    unticked = _package_analysis(jobs)
    assert (unticked["totals"]["flagged_position_count_credited"],
            unticked["totals"]["flagged_position_total_credited"]) == (0, 0.0)
    assert _not_flagged(unticked["totals"]) == _not_flagged(totals)
    assert totals["decision"] == unticked["totals"]["decision"]


def test_a_payee_whose_counted_rows_are_all_credits_rolls_up_with_no_debits(settings_file):
    from webapp.app import _package_analysis

    payload = with_flagged_rows(account_payload(), [flagged_row("factoring", amount=FACTOR_PAYOUT)])
    [item] = _package_analysis([_member("a", payload)])["flagged_positions"]["factoring"]
    assert (item["count"], item["total_debited"], item["count_credited"], item["total_credited"]) == (
        0, 0.0, 1, FACTOR_PAYOUT)


def test_package_positions_rank_by_debited_plus_credited(settings_file):
    from webapp.app import _package_analysis

    payload = with_flagged_rows(account_payload(), [
        flagged_row("factoring", payee="FABRICATED DEBITED FACTOR", amount=-3 * FLAGGED_DEBIT),
        flagged_row("factoring", payee="FABRICATED PAYING FACTOR", amount=-FLAGGED_DEBIT),
        flagged_row("factoring", payee="FABRICATED PAYING FACTOR", amount=FACTOR_PAYOUT),
    ])
    items = _package_analysis([_member("a", payload)])["flagged_positions"]["factoring"]
    # 1 debited plus 3 paid in outranks 3 debited alone, and the paid-in money never joins total_debited.
    assert [(item["payee"], item["total_debited"], item["total_credited"]) for item in items] == [
        ("FABRICATED PAYING FACTOR", FLAGGED_DEBIT, FACTOR_PAYOUT),
        ("FABRICATED DEBITED FACTOR", 3 * FLAGGED_DEBIT, 0.0),
    ]


def test_the_package_csv_and_xlsx_carry_the_credited_fields(settings_file):
    from webapp.app import _package_analysis, _package_csv, _package_xlsx

    package = _package_analysis([_member("a", _factored(0)), _member("b", _factored(1))])
    cells = _csv_cells(_package_csv(package))
    assert (cells[("flagged_factoring_1", "count_credited")], cells[("flagged_factoring_1", "total_credited")]) == (
        "2", str(2 * FACTOR_PAYOUT))
    assert (cells[("totals", "flagged_position_count_credited")],
            cells[("totals", "flagged_position_total_credited")]) == ("2", str(2 * FACTOR_PAYOUT))
    assert "<t>flagged_position_total_credited</t>" in _sheet(_package_xlsx(package))
```

In `tests/test_package_currency.py`:

(e) In `EXPECTED_REFUSED_TOTALS`, replace:

```python
    "flagged_position_total",
    "insurance_total",
```

with:

```python
    "flagged_position_total",
    "flagged_position_total_credited",
    "insurance_total",
```

(f) In `UNIT_FREE_TOTALS`, replace:

```python
    "flagged_position_count",
    "insurance_count",
```

with:

```python
    "flagged_position_count",
    "flagged_position_count_credited",
    "insurance_count",
```

(g) In `UNIT_FREE_ROLLUP_KEYS`, replace:

```python
    "count",
    "debit_count",
```

with:

```python
    "count",
    "count_credited",
    "debit_count",
```

(h) Replace `    assert len(body["currency"]["refused_total_fields"]) == 33` with `    assert len(body["currency"]["refused_total_fields"]) == 34`.

(i) In `test_every_money_row_the_export_emits_is_covered_by_a_declared_currency`, replace:

```python
    for job in (cad, usd):
        # A flag roll-up in the refused package, so the flagged sections are swept too.
        with_flagged_rows(job.analysis, [flagged_row("credit_cards")])
```

with:

```python
    for job in (cad, usd):
        # A flag roll-up in the refused package, so the flagged sections are swept too: a debit, and a factoring
        # credit, whose credited count and total are swept as the debited ones are (C6, owner ruling 2026-09-26).
        with_flagged_rows(job.analysis, [flagged_row("credit_cards"),
                                         flagged_row("factoring", amount=3 * FLAGGED_DEBIT)])
```

and replace:

```python
    assert any(s.startswith("flagged_credit_cards_") for s in exercised)
```

with:

```python
    assert any(s.startswith("flagged_credit_cards_") for s in exercised)
    assert ("flagged_factoring_1", "total_credited", "") in rows
    assert ("flagged_factoring_1", "count_credited", 2) in rows
```

(j) Replace:

```python
    assert single["totals"]["flagged_position_count"] == 4
    assert single["totals"]["flagged_position_total"] == 103 * FLAGGED_DEBIT
```

with:

```python
    assert single["totals"]["flagged_position_count"] == 4
    assert single["totals"]["flagged_position_total"] == 103 * FLAGGED_DEBIT


def test_mixed_currency_refusal_covers_the_credited_flag_roll_up():
    """C6 and the owner's ruling of 2026-09-26: a factor's payouts roll up as credited money, refused exactly as
    the debited money is, while both counts survive."""
    cad, usd = member("a", "CAD"), member("b", "USD")
    for job in (cad, usd):
        with_flagged_rows(job.analysis, [flagged_row("factoring"), flagged_row("factoring", amount=3 * FLAGGED_DEBIT)])
    package = _package_analysis([cad, usd])
    totals = package["totals"]
    assert (totals["flagged_position_total"], totals["flagged_position_total_credited"]) == (None, None)
    assert (totals["flagged_position_count"], totals["flagged_position_count_credited"]) == (2, 2)
    [item] = package["flagged_positions"]["factoring"]
    assert (item["total_debited"], item["total_credited"]) == (None, None)
    assert (item["documents"], item["count"], item["count_credited"]) == (2, 2, 2)


def test_refused_packages_rank_flagged_positions_by_debits_plus_credits():
    """A refused package ranks by the unit-free count, debits plus credits, never by money."""
    def build(first_currency, second_currency):
        paid = member("a", first_currency)
        with_flagged_rows(paid.analysis, [flagged_row("factoring", payee="ZZZ FABRICATED PAID",
                                                      amount=-100 * FLAGGED_DEBIT) for _ in range(2)])
        paying = member("b", second_currency)
        with_flagged_rows(paying.analysis, [flagged_row("factoring", payee="AAA FABRICATED PAYING",
                                                        amount=FLAGGED_DEBIT) for _ in range(3)])
        return _package_analysis([paid, paying])

    refused = build("CAD", "USD")
    assert [(item["payee"], item["count"], item["count_credited"])
            for item in refused["flagged_positions"]["factoring"]] == [
        ("AAA FABRICATED PAYING", 0, 3), ("ZZZ FABRICATED PAID", 2, 0)]
    single = build("CAD", "CAD")
    assert [item["payee"] for item in single["flagged_positions"]["factoring"]] == [
        "ZZZ FABRICATED PAID", "AAA FABRICATED PAYING"]
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py tests/test_webapp_flagged_positions.py tests/test_webapp_settings.py tests/test_package_currency.py -q -p no:cacheprovider
```

Expected: FAIL, `13 failed, 300 passed` (measured on a scratch export of `b18cacf`):
- the four roll-up and export tests of `tests/test_webapp_flagged_positions.py` fail with `KeyError: ('flagged_factoring_1', 'count_credited')`, `KeyError: 'count_credited'` or `assert (2, 4, 56.0) == (2, 2, 14.0)`: today a credit adds to `count` and `total_debited`. The ranking test fails too, because `total_debited` still holds the paid-in money.
- eight tests of `tests/test_package_currency.py` fail with `KeyError: 'flagged_position_total_credited'`, `KeyError: 'flagged_position_count_credited'`, `KeyError: 'count_credited'` (the refused ranking), the refused-set mismatch, the swept rows and `assert 33 == 34`.
- `test_a_flagged_credit_is_shown_and_hidden_with_its_group` and `test_a_factoring_credit_is_served_flagged_and_follows_its_checkbox` pass already: serving keys on `flagged_group`, so they pin behaviour that needs no change.

- [ ] **Step 3: Implement.** In `webapp/app.py`:

(k) In `_flagged_position_rows`, replace:

```python
    """An account's flagged positions, one readable section per payee (lender detection §8.4):
    `flagged_<group>_<n>` with the payee, its debit count, the total debited and the cadence.
```

with:

```python
    """An account's flagged positions, one readable section per payee (lender detection §8.4):
    `flagged_<group>_<n>` with the payee, its debit count, the total debited, the credits it paid in and their
    total (plan contract C5: a factor's payouts, owner ruling 2026-09-26), and the cadence.
```

and replace:

```python
        for field in ("payee", "count", "total_debited", "cadence"):
```

with:

```python
        for field in ("payee", "count", "total_debited", "count_credited", "total_credited", "cadence"):
```

(l) Replace:

```python
    """A row the package's flag roll-up counts: the analysis marked it a contributing debit of a flag group
    (`contributes_to_flagged_totals`: posted, not a proven duplicate, not settlement-reversed), and Settings ticks
    its group."""
```

with:

```python
    """A row the package's flag roll-up counts: the analysis marked it a contributing row of a flag group
    (`contributes_to_flagged_totals`: a posted debit, or a posted factoring credit, that is not a proven duplicate
    and not reversed; plan contract C4), and Settings ticks its group."""
```

(m) In `_add_flagged_rows`, replace:

```python
    C5). `documents` counts the members a payee appears in, as the funder roll-up does. The dates are kept so the
    first and last dates, and the cadence, are read across every member rather than per statement."""
    seen: set[tuple[str, str]] = set()
    for row in rows:
        classification = row["classification"]
        group = classification["flagged_group"]
        entity = classification.get("canonical_entity")
        payee = entity if isinstance(entity, str) and entity else FLAG_GROUP_BY_KEY[group].label
        item = rollup.setdefault(
            (group, payee),
            {"payee": payee, "documents": 0, "count": 0, "total_debited": 0.0, "dates": []},
        )
        if (group, payee) not in seen:
            seen.add((group, payee))
            item["documents"] += 1
        item["count"] += 1
        item["total_debited"] = round(item["total_debited"] + abs(_num(row.get("amount"))), 2)
```

with:

```python
    C5). `documents` counts the members a payee appears in, as the funder roll-up does. A debit adds to `count`
    and `total_debited`; a credit (a factor's payout, owner ruling 2026-09-26) adds to `count_credited` and
    `total_credited`. The dates of both are kept so the first and last dates, and the cadence, are read across
    every member rather than per statement."""
    seen: set[tuple[str, str]] = set()
    for row in rows:
        classification = row["classification"]
        group = classification["flagged_group"]
        entity = classification.get("canonical_entity")
        payee = entity if isinstance(entity, str) and entity else FLAG_GROUP_BY_KEY[group].label
        item = rollup.setdefault(
            (group, payee),
            {"payee": payee, "documents": 0, "count": 0, "total_debited": 0.0, "count_credited": 0,
             "total_credited": 0.0, "dates": []},
        )
        if (group, payee) not in seen:
            seen.add((group, payee))
            item["documents"] += 1
        amount = _num(row.get("amount"))
        if amount < 0:
            item["count"] += 1
            item["total_debited"] = round(item["total_debited"] + abs(amount), 2)
        else:
            item["count_credited"] += 1
            item["total_credited"] = round(item["total_credited"] + amount, 2)
```

(n) Replace the whole `_published_flagged_positions` (from Task 8) with:

```python
def _published_flagged_positions(
    rollup: dict[tuple[str, str], dict], *, refuse_cross_currency: bool
) -> dict[str, list[dict]]:
    """The package's `flagged_positions` (plan contract C6): each ticked group with a counted row, in contract
    order, as a list of `{payee, documents, count, total_debited, count_credited, total_credited, first_date,
    last_date}`.

    Largest total first, debited plus credited; a package that refuses to combine currencies ranks by the
    unit-free count, debits plus credits, then the payee, because an order read off summed money would publish the
    cross-currency comparison the refusal withholds (CURRENCY DOCTRINE §F)."""
    published: dict[str, list[dict]] = {}
    for group in FLAG_GROUPS:
        items = []
        for (key, _payee), item in rollup.items():
            if key != group.key:
                continue
            dates = sorted(item["dates"])
            items.append({
                "payee": item["payee"],
                "documents": item["documents"],
                "count": item["count"],
                "total_debited": item["total_debited"],
                "count_credited": item["count_credited"],
                "total_credited": item["total_credited"],
                "first_date": dates[0].isoformat() if dates else None,
                "last_date": dates[-1].isoformat() if dates else None,
            })
        if not items:
            continue
        if refuse_cross_currency:
            published[group.key] = sorted(
                items, key=lambda item: (-(item["count"] + item["count_credited"]), item["payee"])
            )
        else:
            published[group.key] = sorted(
                items, key=lambda item: (-(item["total_debited"] + item["total_credited"]), item["payee"])
            )
    return published
```

(o) In `_CROSS_CURRENCY_TOTAL_KEYS`, replace:

```python
    "flagged_position_total",
    "insurance_total",
    "lender_debits",
```

with:

```python
    "flagged_position_total",
    "flagged_position_total_credited",
    "insurance_total",
    "lender_debits",
```

(p) Replace:

```python
_CROSS_CURRENCY_ROLLUP_KEYS = (
    "total_debited",
    "potential_lender_debit_total",
```

with:

```python
_CROSS_CURRENCY_ROLLUP_KEYS = (
    "total_debited",
    "total_credited",
    "potential_lender_debit_total",
```

(q) In the totals init of `_package_analysis`, replace:

```python
        # Lender detection §8.3: the ticked flag groups' counted debits and their total. Never lender math (D7).
        "flagged_position_count": 0,
        "flagged_position_total": 0.0,
```

with:

```python
        # Lender detection §8.3: the ticked flag groups' counted debits and their total, and apart from them the
        # counted credits (a factor's payouts, owner ruling 2026-09-26) and theirs. Never lender math (D7).
        "flagged_position_count": 0,
        "flagged_position_total": 0.0,
        "flagged_position_count_credited": 0,
        "flagged_position_total_credited": 0.0,
```

(r) Replace:

```python
    totals["flagged_position_count"] = sum(item["count"] for item in flagged_rollup.values())
    totals["flagged_position_total"] = round(sum(item["total_debited"] for item in flagged_rollup.values()), 2)
```

with:

```python
    totals["flagged_position_count"] = sum(item["count"] for item in flagged_rollup.values())
    totals["flagged_position_total"] = round(sum(item["total_debited"] for item in flagged_rollup.values()), 2)
    totals["flagged_position_count_credited"] = sum(item["count_credited"] for item in flagged_rollup.values())
    totals["flagged_position_total_credited"] = round(
        sum(item["total_credited"] for item in flagged_rollup.values()), 2
    )
```

The refusal loop needs no edit: it nulls every `_CROSS_CURRENCY_ROLLUP_KEYS` key an item holds, so `total_credited` goes with `total_debited`. The package sheets write every item and total field (Task 9), so they carry the new ones with no edit.

- [ ] **Step 4: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py tests/test_webapp_flagged_positions.py tests/test_webapp_settings.py tests/test_package_currency.py -q -p no:cacheprovider
```

Expected: PASS, `313 passed` (64 + 103 + 100 + 46).

Then the neighbours:

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py tests/test_webapp_flagged_positions.py tests/test_webapp_settings.py tests/test_package_currency.py tests/test_l1s3_surfaces.py tests/test_webapp_app.py tests/test_webapp_security.py tests/test_nsf_days.py tests/test_adb.py -q -p no:cacheprovider
```

Expected: PASS, `550 passed` (541 before this task, plus its nine new tests).

- [ ] **Step 5: Commit.**

```powershell
git add webapp/app.py tests/flagged_payloads.py tests/test_flagged_view.py tests/test_webapp_flagged_positions.py tests/test_package_currency.py
git commit -m "webapp: flagged credits in serving, the package roll-up, the exports and the currency sweep" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 10: The package cadence across members (after S2 merges)

**Files:**
- Modify: `webapp/app.py` (imports, and `_published_flagged_positions`).
- Test: `tests/test_webapp_flagged_positions.py` (append).

**Interfaces:**
- Consumes: C5 `analysis/cadence.py::describe_cadence(dates: Sequence[date]) -> tuple[str, float | None]`, which returns one of `daily | weekly | biweekly | monthly | irregular | single`. S2 provides it.
- Produces: C6's `cadence` on every roll-up item, in the order `{payee, documents, count, total_debited, count_credited, total_credited, cadence, first_date, last_date}` (the credited fields come from Task 12, which runs before this task). It is `None` when no date parses, and it reads a payee's debits and credits alike.

- [ ] **Step 1: Rebase onto S2.**

```powershell
git switch ld-s3-webapp
git rebase lender-detection
git ls-tree --name-only HEAD -- analysis/cadence.py
```

Expected:
- the last command prints `analysis/cadence.py`;
- if the rebase stops on `analysis/flag_groups.py`, resolve it with Task 1, Step 7. Take `lender-detection`'s copy only when it passes the C1 pin; otherwise run `git rebase --abort`, report, and stop here.

Then re-run the tests of Tasks 1-9 and 12:

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py tests/test_webapp_flagged_positions.py tests/test_webapp_settings.py tests/test_package_currency.py -q -p no:cacheprovider
```

Expected: PASS, with 64 + 103 + 100 + 46 (313).

These tests read S1's `analysis/flag_groups.py` from here on, instead of Task 1's copy. If `test_the_view_reads_the_eleven_contract_groups` or `test_every_flag_group_has_a_checkbox_that_is_on_by_default` fails, S1's module departs from C1 (for example, eight groups instead of eleven). Report it to the orchestrator with the printed tuple. Do not re-pin.

- [ ] **Step 2: Write the failing tests.** Append to `tests/test_webapp_flagged_positions.py`:

```python


# --- the package cadence (§8.3; needs analysis/cadence.py from S2) -------------------------------------------

def _member_paying(job_id, index, group_key, dates):
    payload = with_flagged_rows(account_payload(index), [flagged_row(group_key, date=date) for date in dates])
    return _member(job_id, payload)


def test_the_package_cadence_is_read_across_every_members_dates(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([
        _member_paying("a", 0, "vehicle_financing", ("2054-01-05", "2054-01-12")),
        _member_paying("b", 1, "vehicle_financing", ("2054-01-19", "2054-01-26")),
    ])
    [item] = package["flagged_positions"]["vehicle_financing"]
    assert (item["cadence"], item["count"]) == ("weekly", 4)
    assert (item["first_date"], item["last_date"]) == ("2054-01-05", "2054-01-26")


def test_one_payment_per_monthly_statement_reads_as_monthly(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([
        _member_paying("jan", 0, "mortgages", ("2054-01-15",)),
        _member_paying("feb", 1, "mortgages", ("2054-02-15",)),
        _member_paying("mar", 2, "mortgages", ("2054-03-15",)),
    ])
    [item] = package["flagged_positions"]["mortgages"]
    assert (item["cadence"], item["documents"]) == ("monthly", 3)


def test_a_payee_paid_once_in_the_package_has_a_single_cadence(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([_member("a", flagged_account_payload(0, groups=("mortgages",)))])
    assert package["flagged_positions"]["mortgages"][0]["cadence"] == "single"


def test_every_flag_roll_up_item_carries_the_contract_fields_in_order(settings_file):
    from webapp.app import _package_analysis

    package = _package_analysis([_member("a", flagged_account_payload(0))])
    for items in package["flagged_positions"].values():
        for item in items:
            assert list(item) == ["payee", "documents", "count", "total_debited", "count_credited", "total_credited",
                                  "cadence", "first_date", "last_date"]
```

- [ ] **Step 3: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_positions.py -q -p no:cacheprovider
```

Expected: FAIL, `4 failed, 103 passed`. The four new tests fail with `KeyError: 'cadence'`, or with a key list that lacks `cadence`.

- [ ] **Step 4: Implement.** In `webapp/app.py`:

(a) Replace `from analysis.nsf_days import apply_nsf_basis_to_payload` with:

```python
from analysis.nsf_days import apply_nsf_basis_to_payload
from analysis.cadence import describe_cadence
```

(b) Replace the whole `_published_flagged_positions` (as Task 12 left it) with:

```python
def _published_flagged_positions(
    rollup: dict[tuple[str, str], dict], *, refuse_cross_currency: bool
) -> dict[str, list[dict]]:
    """The package's `flagged_positions` (plan contract C6): each ticked group with a counted row, in contract
    order, as a list of `{payee, documents, count, total_debited, count_credited, total_credited, cadence,
    first_date, last_date}`. The cadence is read over the payee's dates in every member together
    (analysis/cadence.py), its debits and its credits alike, so a monthly payment split across monthly statements
    reads as monthly.

    Largest total first, debited plus credited; a package that refuses to combine currencies ranks by the
    unit-free count, debits plus credits, then the payee, because an order read off summed money would publish the
    cross-currency comparison the refusal withholds (CURRENCY DOCTRINE §F)."""
    published: dict[str, list[dict]] = {}
    for group in FLAG_GROUPS:
        items = []
        for (key, _payee), item in rollup.items():
            if key != group.key:
                continue
            dates = sorted(item["dates"])
            items.append({
                "payee": item["payee"],
                "documents": item["documents"],
                "count": item["count"],
                "total_debited": item["total_debited"],
                "count_credited": item["count_credited"],
                "total_credited": item["total_credited"],
                "cadence": describe_cadence(dates)[0] if dates else None,
                "first_date": dates[0].isoformat() if dates else None,
                "last_date": dates[-1].isoformat() if dates else None,
            })
        if not items:
            continue
        if refuse_cross_currency:
            published[group.key] = sorted(
                items, key=lambda item: (-(item["count"] + item["count_credited"]), item["payee"])
            )
        else:
            published[group.key] = sorted(
                items, key=lambda item: (-(item["total_debited"] + item["total_credited"]), item["payee"])
            )
    return published
```

This keeps Task 12's credited fields and order, and adds only `cadence` (amended 2026-09-26 for Task 12, which runs before this task).

- [ ] **Step 5: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_positions.py tests/test_package_currency.py -q -p no:cacheprovider
```

Expected: PASS, `153 passed` in all. `tests/test_webapp_flagged_positions.py`: `107 passed`.
- The `cadence` column appears in the package CSV rows (Task 9 writes every item field).
- The currency sweep ignores it, because a word does not parse as a number.
- If `weekly`, `monthly` or `single` comes back as another value, S2's helper departs from C5 for exact 7-day gaps, 28-31-day gaps or one date. Report it to the orchestrator with the returned value. Do not re-pin.

- [ ] **Step 6: Commit.**

```powershell
git add webapp/app.py tests/test_webapp_flagged_positions.py
git commit -m "webapp: package cadence of flagged positions across members" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 11: Conformance with S2's real payload, and the re-run after S2

**Files:**
- Test: `tests/test_webapp_flagged_positions.py` (one import edit; append)

**Interfaces:**
- Consumes the C2 tables `PREMIUM_FINANCE_ALIASES`, `FLOOR_PLAN_ALIASES` and `FACTORING_ALIASES` (`analysis/classification_registry.py`). S1 renders them from the C10 ledger (`docs/lender-registry-ledger.json`): each holds the `admitted` entities of the ledger group `premium_financing`, `floor_plan_financing` or `factoring`. Each gives one payee name, read at run time, so the test writes none.
  - All three tables hold at least one entity once S1 has merged. S1's validator (`tools/build_lender_registry.py --check`, normative for the ledger per the master plan's C10) refuses a ledger unless every owner-named payee of spec §2 resolves to its group through `OWNER_NAMED_PAYEES`: NextGear Capital and Westlake Flooring in the floor-plan table, RTS Financial, OTR Capital, Apex Capital and BC Factoring in the factoring table, IPFS and First Insurance Funding in the premium-finance table. S2's Task 0 (fact 1) checks NextGear, RTS, IPFS and First Insurance Funding again. `first_alias` stays as a safeguard: an empty table is named in the failure instead of raising a bare `StopIteration`.
- Consumes the fixture's `row_state` (Task 3), which maps a group key to its C1 state, or to `insurance` for premium financing.
- Consumes S2's real pipeline pieces, all present at `4f219cd` and verified:
  - `classify_statement_transactions(statement)` (`analysis/transaction_classifier.py:1460`);
  - `compute_metrics(stmt, *, classifications=...)` (`analysis/metrics.py:294`);
  - `detect(stmt, *, classifications=..., eligible_deposits=...)` (`analysis/detect.py:205`);
  - `report_to_dict(report)` (`analysis/serialization.py:139`);
  - `Report`, `Quality` and `DocumentIntegrity` (`analysis/pipeline.py`, as `tests/test_lender_insurance_classification.py:10,230-272` builds them);
  - C4 `TransactionClassification.flagged_group` and `contributes_to_flagged_totals`, and `CLASSIFICATION_VERSION == "5.0"`.
- Produces proof of five things:
  - C4/C5, as S2 built them, flow through C6 serving and the package, including D7: the decision stays `approved`;
  - the three amendment groups arrive under their C1 keys: `floor_plan` from the `floor_plan_financing` state, `factoring` from `factoring`, and `premium_financing` on an `insurance` row;
  - every flagged record carries the state the fixtures give its group;
  - S2's premium-financing row has the shape the fixtures give it: an `insurance` row that also carries the flag;
  - (the owner's ruling of 2026-09-26, S2's Task 18) S2's factoring credit has the shape the fixtures give it: a `factoring` row that counts, is never financing proceeds, and rolls up as `count_credited` / `total_credited`; C5's key sets include the credited fields.

- [ ] **Step 1: Write the tests.** In `tests/test_webapp_flagged_positions.py`, replace:

```python
from tests.flagged_payloads import (
    FLAGGED_DEBIT,
```

with:

```python
from tests.flagged_payloads import (
    CURRENT_VERSION,
    FLAGGED_DEBIT,
```

and replace:

```python
    flagged_row,
    with_flagged_rows,
)
```

with:

```python
    flagged_row,
    row_state,
    with_flagged_rows,
)
```

Append to the end of the file:

```python


# --- S2's real payload flows through serving and the package (contract C4/C5; after S2 merges) ----------------

#: The keys C5 publishes on every `detection.flagged_positions` entry, and on every `metrics.flagged_groups` value.
C5_POSITION_KEYS = {"group", "payee", "matched_alias", "count", "total_debited", "count_credited", "total_credited",
                    "cadence", "avg_gap_days", "first_date", "last_date", "source_locations"}
C5_GROUP_KEYS = {"count", "total", "count_credited", "total_credited", "payees"}


def _analysed_payload() -> dict:
    """A fabricated statement run through the real classifier, metrics, detection and serializer.

    The first two debits name no payee; S2's descriptor rules (spec §4.3 step 8) file them under mortgages and
    lines of credit. The next three pay the owner's amendment groups (spec §2): an insurance premium to a
    premium-finance payee, a floor-plan payee and a factoring payee. The last row is that factoring payee's payout
    for invoices it bought, a credit that stays revenue and carries the Factoring flag (owner ruling 2026-09-26).
    Each name is the first alias of its C2 table, which S1 renders from the C10 ledger, read at run time, so no payee
    name is written in a test."""
    from analysis.classification_registry import FACTORING_ALIASES, FLOOR_PLAN_ALIASES, PREMIUM_FINANCE_ALIASES
    from analysis.detect import detect
    from analysis.metrics import compute_metrics
    from analysis.pipeline import DocumentIntegrity, Quality, Report
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction
    from analysis.serialization import report_to_dict
    from analysis.transaction_classifier import classify_statement_transactions

    def row(day, description, amount):
        return Transaction(date=day, description=description, amount=amount,
                           direction="credit" if amount >= 0 else "debit")

    def first_alias(name, table):
        # C10's validator requires no admitted entity in these three groups, so an empty table is named here
        # instead of surfacing as a bare StopIteration.
        aliases = [alias for entity_aliases in table.values() for alias in entity_aliases]
        assert aliases, f"{name} holds no alias: the C10 ledger admits no entity in this group"
        return aliases[0]

    premium_payee = first_alias("PREMIUM_FINANCE_ALIASES", PREMIUM_FINANCE_ALIASES)
    floor_plan_payee = first_alias("FLOOR_PLAN_ALIASES", FLOOR_PLAN_ALIASES)
    factoring_payee = first_alias("FACTORING_ALIASES", FACTORING_ALIASES)
    statement = Statement(bank="FABRICATED BANK", account_number="0000", transactions=[
        row("2054-01-02", "FABRICATED CUSTOMER DEPOSIT", 10 * FLAGGED_DEBIT),
        row("2054-01-05", "FABRICATED MORTGAGE PAYMENT", -FLAGGED_DEBIT),
        row("2054-01-06", "FABRICATED LINE OF CREDIT PAYMENT", -FLAGGED_DEBIT),
        row("2054-01-07", f"FABRICATED {premium_payee} INSURANCE PREMIUM", -FLAGGED_DEBIT),
        row("2054-01-08", f"FABRICATED {floor_plan_payee} PAYMENT", -FLAGGED_DEBIT),
        row("2054-01-09", f"FABRICATED {factoring_payee} PAYMENT", -FLAGGED_DEBIT),
        row("2054-01-10", f"FABRICATED {factoring_payee} INVOICE PAYMENT", 3 * FLAGGED_DEBIT),
    ])
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    detection = detect(statement, classifications=records, eligible_deposits=metrics.eligible_deposits)
    return report_to_dict(Report(
        statement=statement, reconciliation=reconcile(statement), metrics=metrics, detection=detection,
        quality=Quality(level="transaction_level", transaction_detail_reliable=True,
                        summary_totals_reliable=True, corporate_use="approved"),
        integrity=DocumentIntegrity(risk_level="clear", flags=[], notes=[]),
        model_used="test", escalated=False, classifications=records,
    ))


def test_the_classifiers_payload_carries_the_contract_fields():
    payload = _analysed_payload()
    positions = payload["detection"]["flagged_positions"]
    groups = {entry["group"] for entry in positions}
    assert groups & {"mortgages", "lines_of_credit"}
    assert {"premium_financing", "floor_plan", "factoring"} <= groups
    assert all(set(entry) == C5_POSITION_KEYS for entry in positions)
    assert all(set(value) == C5_GROUP_KEYS for value in payload["metrics"]["flagged_groups"].values())
    flagged = [row["classification"] for row in payload["statement"]["transactions"]
               if row["classification"]["flagged_group"]]
    assert flagged and all(record["contributes_to_flagged_totals"] is True for record in flagged)
    # Every record carries the state the fixtures give its group: floor_plan_financing, factoring (its payout
    # credit too), and insurance for premium financing (C1, C4).
    assert all(record["classification"] == row_state(record["flagged_group"]) for record in flagged)


def test_the_classifiers_premium_financing_row_is_an_insurance_row_with_the_flag():
    payload = _analysed_payload()
    [premium] = [row["classification"] for row in payload["statement"]["transactions"]
                 if row["classification"]["flagged_group"] == "premium_financing"]
    fixture = flagged_row("premium_financing")["classification"]
    names = ("classification", "flagged_group", "contributes_to_insurance_totals", "contributes_to_flagged_totals")
    assert {name: premium[name] for name in names} == {name: fixture[name] for name in names}


def test_the_classifiers_factoring_credit_is_revenue_and_rolls_up_as_credited(settings_file):
    """Owner ruling 2026-09-26 (C4-C6): the factor's payout is flagged, counted apart from the debits, never
    financing proceeds, and it matches the fixtures' credit row."""
    from webapp.app import _package_analysis

    payload = _analysed_payload()
    [credit] = [row["classification"] for row in payload["statement"]["transactions"]
                if row["classification"]["flagged_group"] == "factoring" and row["amount"] > 0]
    fixture = flagged_row("factoring", amount=3 * FLAGGED_DEBIT)["classification"]
    names = ("classification", "flagged_group", "contributes_to_flagged_totals")
    assert {name: credit[name] for name in names} == {name: fixture[name] for name in names}
    assert credit["contributes_to_lender_credit_exclusion"] is False
    assert credit["revenue_match_method"] != "financing_proceeds_credit"
    assert payload["metrics"]["lender_credits"] == 0.0
    [position] = [entry for entry in payload["detection"]["flagged_positions"] if entry["group"] == "factoring"]
    assert (position["count"], position["count_credited"], position["total_credited"]) == (1, 1, 3 * FLAGGED_DEBIT)
    package = _package_analysis([_member("fabricated", payload)])
    [item] = package["flagged_positions"]["factoring"]
    assert (item["count"], item["count_credited"], item["total_credited"]) == (1, 1, 3 * FLAGGED_DEBIT)
    assert package["totals"]["flagged_position_count_credited"] == 1


def test_the_classifiers_payload_is_served_and_packaged_by_the_checkboxes(settings_file):
    from webapp.app import _displayed, _package_analysis

    payload = _analysed_payload()
    none_ticked = {**DEFAULTS, **{key: False for key in FLAG_SETTING_KEYS}}
    hidden = _displayed(payload, settings=none_ticked)
    assert hidden["metrics"]["flagged_groups"] == {} and hidden["detection"]["flagged_positions"] == []
    assert hidden["analysis_rules_outdated"] is False
    package = _package_analysis([_member("fabricated", payload)])
    assert set(package["flagged_positions"]) == {entry["group"] for entry in payload["detection"]["flagged_positions"]}
    # D7: flag groups never make a package need review, and never enter the lender math.
    assert package["totals"]["decision"] == "approved"
    assert package["totals"]["lender_debit_count"] == 0 and package["totals"]["potential_lender_debit_count"] == 0
    # Unticking every group hides every flag; the premium-financing row still counts as insurance.
    unticked = _package_analysis([_member("fabricated", payload)], settings=none_ticked)
    assert unticked["flagged_positions"] == {} and unticked["totals"]["flagged_position_count"] == 0
    assert unticked["totals"]["flagged_position_count_credited"] == 0
    assert unticked["totals"]["insurance_count"] == package["totals"]["insurance_count"] == 1
    assert unticked["totals"]["decision"] == "approved"


def test_the_fixture_records_use_only_fields_the_classifier_writes():
    from dataclasses import fields

    from analysis.transaction_classifier import CLASSIFICATION_VERSION, TransactionClassification

    names = {field.name for field in fields(TransactionClassification)}
    assert set(flagged_row("mortgages")["classification"]) <= names
    assert CLASSIFICATION_VERSION == CURRENT_VERSION
```

- [ ] **Step 2: Run them.**

```powershell
C:\Python314\python.exe -m pytest tests/test_webapp_flagged_positions.py -q -p no:cacheprovider
```

Expected: PASS, `112 passed` (the 107 of Tasks 1-10 and 12, plus these five). These tests have no red phase on this branch, because they check S2's already-merged output.
- On the pre-S2 base (measured), all four tests of the first revision failed: the three amendment registries do not exist, and the records carry no `flagged_group`.
- Their assertions were also run over a C5-shaped fabricated stand-in for `_analysed_payload()`, with one fixture row each for mortgages, lines of credit, premium financing, floor plan and factoring. The three payload tests passed.
- The revision of 2026-09-26 (the owner's ruling on factoring credits) was run on a scratch tree of S2 with its Task 18 plus S3 with Tasks 1-10 and 12: `112 passed`. On a `lender-detection` whose S2 lacks Task 18, the C5 key-set test and the factoring-credit test fail: S2 merges with its Task 18.

If one fails now:
- print `payload["statement"]["transactions"]` classifications and `payload["detection"]["flagged_positions"]`;
- compare them with C4/C5, and report the departure to the orchestrator. An `ImportError` on one of the three registries means S1's registry departs from C2.
- An `AssertionError` that names a table and says it "holds no alias" means the committed C10 ledger admits no entity in that group. The ledger is the orchestrator's (C10): report which table is empty. S3 does not edit the ledger or the registry, and does not change the test.

Do not edit the expectations.

- [ ] **Step 3: Re-run everything S3 touches, and the master selections.**

```powershell
C:\Python314\python.exe -m pytest tests/test_flagged_view.py tests/test_webapp_flagged_positions.py tests/test_webapp_settings.py tests/test_package_currency.py tests/test_l1s3_surfaces.py tests/test_webapp_app.py tests/test_webapp_security.py tests/test_nsf_days.py tests/test_adb.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_r1_hardcodes.py tests/test_webapp_settings.py tests/test_package_currency.py tests/test_webapp_app.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_no_statement_hardcodes.py tests/test_new_statement_corpus.py tests/test_webapp_accounts_view.py tests/test_webapp_studio_views.py tests/test_webapp_review_ui.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_analysis.py tests/test_artifact_cache.py tests/test_benchmark_harness.py tests/test_batch.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_l1s3_census.py -q -p no:cacheprovider
```

Expected: PASS, except the known `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`. The JS tests need `node` on PATH, and skip silently without it. Check `node --version` first. The last command, the master plan's surface-census item, gives `22 passed` from a worktree or clone without `discovery_reports/` (Task 3 Step 4).

Three more tests fail at `4f219cd` before any S3 change. They are outside these selections and concern `vlm/` and `tools/` modules, so do not attribute them to S3. Measured on the repository at `4f219cd`: `3 failed`.
- `tests/test_corpus_gate_outcomes.py::test_every_production_caller_of_the_analysis_is_classified`
- `tests/test_stated_counts.py::test_the_observer_is_not_wired_into_any_production_module`
- `tests/test_extraction_quality_admission.py::test_router_implementation_preserves_phase2_extraction_quality_exclusion`

These must be re-run after S2 merges, because their inputs change once S2's classifier is in:
- everything in S3's own files, because the fabricated fixtures stand in for S2 until then;
- `tests/test_lender_insurance_classification.py::test_metrics_api_tables_filters_and_withholding_share_exact_evidence`, which runs `_package_analysis` over classifier output that now carries flag groups;
- `tests/test_transaction_classifier.py::test_atb_november_lender_and_potential_obligation_regression`, whose package half is at `:367-369`;
- `tests/test_new_statement_corpus.py::test_new_statement_api_and_exports_preserve_authoritative_values`, which covers CSV/XLSX and the package over real classifier output.

- [ ] **Step 4: Commit.**

```powershell
git add tests/test_webapp_flagged_positions.py
git commit -m "tests: the classifier's flag payload flows through serving and the package" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

## Self-Review

**Spec coverage (the sections S3 owns)**

| Spec | Where |
|---|---|
| §8.1 with the §2 amendment: `DEFAULTS` gains one `flag_*` key per group, each `True` | Task 2 (C7): eleven keys, driven by `FLAG_SETTING_KEYS` and pinned spelled out (resolution 11). |
| §8.1: the routes do not change | Task 2. `test_the_api_saves_one_checkbox_and_keeps_every_other_setting` goes through the unchanged `/api/settings`. |
| §8.1: the whole-dict tests are updated | Task 2, all five pins (see the table above). |
| §8.2: `_displayed(analysis, *, settings=None)` reads Settings once, applies the NSF basis and then `apply_flagged_groups_to_payload` | Task 5. `carry_over` is kept per C6. |
| §8.2: copies before changing | Task 3: deep copies of `statement.transactions`, `metrics` and `detection`. It is tested for equality and for identity of the changed structures, and through the routes (`done_job.analysis == stored`, and the review test's stored record has no tag). |
| §8.2: removes unticked groups | Task 3, for both shapes. Tasks 5 and 6 cover every route. |
| §8.2: `flag_shown` | Task 3 (the C6 formula), Task 5 (routes and package members). |
| §8.2: `analysis_rules_outdated` | Task 4. |
| §8.2: never refuses; legacy payloads pass through | Task 3: the shape-less inputs return the same object, and a legacy payload keeps every stored value. |
| §8.2: `_package_members` reads the whole snapshot once | Task 5 (read once per package; resolution 2). `test_a_package_reads_the_settings_once_and_hands_that_snapshot_to_every_member` counts the reads: one per `_package_analysis(jobs)`, and none when a snapshot is passed. `test_package_members_follow_the_snapshot_they_are_handed_not_the_file` pins that the members' tags come from the snapshot. Task 7's `test_the_roll_up_reads_the_same_snapshot_as_the_member_rows` pins the same for the roll-up, the evidence and the package ledger. |
| §8.3: roll-up `{payee, documents, count, total_debited, cadence, first_date, last_date}` from the ticked groups of validated members | Tasks 7 and 10. Only validated members reach `members`: document accounts are excluded by `_package_members` and are unchanged, as the exclusion test shows. |
| §8.3: internal-transfer legs excluded | Task 7, `test_an_internal_transfer_leg_never_enters_the_flag_roll_up`. |
| §8.3: evidence carries `source_account` | Task 7, in `flagged_evidence` (resolution 7). |
| §8.3: cadence across all members' dates | Task 10. |
| §8.3: `flagged_position_count` in `UNIT_FREE_TOTALS`; `flagged_position_total` in `_CROSS_CURRENCY_TOTAL_KEYS` and `EXPECTED_REFUSED_TOTALS` | Task 8. |
| §8.3: `total_debited` is already refused; roll-up nulled under refusal | Task 8, the refusal loop and `test_mixed_currency_refusal_covers_the_flag_roll_up`. |
| §8.3: a refused package orders by count, then name | Task 8, `test_refused_packages_rank_flagged_positions_by_count_then_payee`. |
| §8.3: lender totals, withholding and `decision` untouched | Tasks 7 and 11. Every non-flag total is equal whether groups are ticked or unticked, and the decision stays `approved`. No line in the lender, withholding or decision blocks (`webapp/app.py:1360-1377`, `:1720-1761`) is edited. |
| §8.4: single-statement CSV/XLSX `flagged_<group>_<n>` rows, ticked only, escaped | Task 6. |
| §8.4: package CSV/XLSX rows; `CROSS_DOCUMENT_SECTION` widened | Task 9. |
| §8.4: JSON follows the displayed payload | Task 5 (`/download/<id>/json`); Task 9 (`/package_analysis`, `/package_download/csv`). |
| §2 amendment: premium-financing rows stay counted as insurance and are also flagged; floor plan and factoring are flagged like alternative positions | Floor plan and factoring are ordinary groups in every parametrized test. Premium financing: the fixture row is an `insurance` row with the flag (Task 3); unticking hides only the flag (Task 3, `test_unticking_premium_financing_hides_the_flag_and_keeps_the_insurance_record`); the package insurance count, total and evidence do not move with the checkbox (Task 7, `test_premium_financing_stays_insurance_whether_or_not_it_is_flagged`, and the snapshot test); S2's real row is checked against the fixture (Task 11). Task 11 also runs a floor-plan payee and a factoring payee through S2's real classifier. It checks that they arrive as `floor_plan` and `factoring`, and that every flagged record carries the state the fixtures give its group. |
| §9: tests for Settings, serving and exports for every checkbox, with the stored record unchanged; package roll-up and refusal | Tasks 2-3 and 5-9 are parametrized over all eleven `FLAG_GROUPS`. |
| Owner ruling 2026-09-26 (C4-C6 as amended): a factoring credit stays revenue and is flagged; the credited count and total are served, filtered by Settings, rolled up per package, written to CSV/XLSX and currency-checked exactly as the debited ones | Task 12 (fabricated payloads; the two serving tests pin behaviour that needed no change), Task 10 (the cadence version keeps the credited fields), Task 11 (S2's real factoring credit through serving and the package). |
| The NSF tests at `tests/test_webapp_settings.py:83-232`, mirrored per checkbox | `:83` analysis and exports → Task 5 `test_the_analysis_and_its_json_export_follow_the_checkbox` and Task 6 `test_the_csv_and_xlsx_exports_carry_readable_rows_for_ticked_groups_only`; `:96` package members → Task 5 `test_package_members_carry_the_displayed_checkboxes`; `:133` package totals and rows → Task 8 `test_the_package_totals_count_the_debits_of_ticked_groups_only` and Task 9 `test_the_package_csv_and_xlsx_carry_the_ticked_groups_only`; `:151` a member without analysis → Task 8 `test_a_member_without_analysis_adds_nothing_to_the_flag_roll_up`; `:203` document accounts → Task 5 `test_every_published_account_of_a_document_member_follows_the_checkbox`; `:213` exclusions → Task 5 `test_the_checkboxes_never_change_which_accounts_a_package_leaves_out`. The file-writing tests (`:105`, `:118`, `:164`) do not depend on the key; Task 2 re-pins them to the merged dict. |

**Placeholder scan.**
- No TBD, TODO, "similar to Task N" or undefined helper.
- Each task has complete test and implementation code.
- Each step names the exact text it replaces.
- The conditional steps are decided by a command's output:
  - Task 1, Step 4 runs when Step 1 prints nothing;
  - Task 1, Step 3's stop branch runs when S1's module fails the C1 pin;
  - Task 1, Step 7 runs when a rebase stops on `analysis/flag_groups.py`.
- The one value the plan cannot know is the committing session's `Claude-Session` URL. Every commit command marks it as `<the Claude-Session URL from your system reminder>`, and the S3-specific constraints say where it comes from.

**Contract-name consistency.**
- **C1:** `FLAG_GROUPS`, `FLAG_GROUP_BY_KEY`, `FLAG_SETTING_KEYS`, `FlagGroup.key`, `.setting`, `.state` (None for premium financing) and `.label`.
  - `FLAG_GROUP_BY_STATE` and `FINANCING_STATES` appear only in Task 1's verbatim copy of C1; no S3 code reads them.
  - The eleven keys are spelled out in two places: Task 1's pin (`test_the_view_reads_the_eleven_contract_groups`) and Task 2's `EXPECTED_DEFAULTS`. Everything else iterates `FLAG_GROUPS`: the parametrized tests, `CROSS_DOCUMENT_SECTION`, the settings defaults and the roll-up order.
- **C2:** `PREMIUM_FINANCE_ALIASES`, `FLOOR_PLAN_ALIASES` and `FACTORING_ALIASES`, read at run time in Task 11 only.
- **C10:** S3 reads no ledger and runs no builder. Its only dependency on the ledger is that the three C2 tables above hold at least one admitted entity each by the time Task 11 runs. S1's validator already requires that (the owner-named floor-plan, factoring and premium-finance payees), and Task 11's `first_alias` stays as a safeguard: it names an empty table in its failure, and Step 2 says to report it.
- S1 is referred to only by these contract names (C1, C2, C10), never by its task numbers.
- **C4:** `flagged_group`, `contributes_to_flagged_totals`, `contributes_to_insurance_totals`, `classification_version`, `canonical_entity`, `source_location`, `date` and `amount`.
- **C5:**
  - `metrics.flagged_groups` values `{count, total, payees}`, and `count_credited`, `total_credited` since the amendment of 2026-09-26 (Task 12);
  - `detection.flagged_positions` entries `{group, payee, matched_alias, count, total_debited, cadence, avg_gap_days, first_date, last_date, source_locations}`, and `count_credited`, `total_credited` after `total_debited` since the same amendment;
  - `describe_cadence`.
- **C6:**
  - `apply_flagged_groups_to_payload(payload, *, enabled)`, `flag_shown`, `analysis_rules_outdated`;
  - `_displayed(analysis, *, carry_over=None, settings=None)`;
  - package `flagged_positions` with `{payee, documents, count, total_debited, count_credited, total_credited, cadence, first_date, last_date}` (the credited pair from Task 12);
  - `totals.flagged_position_count` and `totals.flagged_position_total`, and `totals.flagged_position_count_credited` and `totals.flagged_position_total_credited` (Task 12).
- **C7:** `DEFAULTS`.
- **S3-internal names**, defined in the task that introduces them and not used by other services:
  - `enabled_group_keys`, `FLAG_RULES_MAJOR` and `RULES_OUTDATED_KEY` (Tasks 3-4);
  - `_flagged_position_rows` (Task 6);
  - `_counts_as_flagged`, `_add_flagged_rows`, `_published_flagged_positions` and the package key `flagged_evidence` (Task 7);
  - the fixture API in `tests/flagged_payloads.py` (Task 3), and its `CREDITED_GROUP_KEYS` (Task 12).
- S4 and S5 may import `tests/flagged_payloads.py` once S3 has merged. They should not create a file of that name.

**Prototype check.** Every code block of this plan was applied verbatim, task by task, to an export of `4f219cd` in a scratch folder. Each "replace" anchor had to match exactly once. Nothing in the repository was touched. Every red and green count written above is the measured one:
- `tests/test_webapp_settings.py`: 83 failed / 17 passed before Task 2's implementation, then 100 passed.
- `tests/test_flagged_view.py`: 51 passed after Task 3, and 63 after Task 4.
- `tests/test_webapp_flagged_positions.py`: 38, 52, 71, 84 and 97 passed after Tasks 5-9, and 101 after Task 10; the four Task 11 tests make 105. Task 10 ran with S2's planned `analysis/cadence.py`, copied verbatim from S2's plan.
- `tests/test_package_currency.py`: 44 passed.
- The final tree:
  - `tests/test_flagged_view.py tests/test_webapp_settings.py tests/test_package_currency.py tests/test_l1s3_surfaces.py tests/test_webapp_app.py tests/test_webapp_security.py tests/test_nsf_days.py tests/test_adb.py`: 444 passed;
  - `tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_r1_hardcodes.py`: 298 passed;
  - the guards and node-harness JS selection: 146 passed, plus the known `test_no_literal_account_numbers_in_ocr` failure (node v24 on PATH);
  - the wider selection: 306 passed.
- Task 11 on the pre-S2 classifier: all four tests fail, as expected. Three fail with `ImportError` (the amendment registries are not there yet), and the fourth because the records carry no `flagged_group`.
  - Its three payload tests were also run over a C5-shaped fabricated stand-in for `_analysed_payload()`: one fixture row each for mortgages, lines of credit, premium financing, floor plan and factoring, with C4's defaults on the other rows. All three passed.
  - With the floor-plan row's state changed to `alternative_position`, the contract-fields test failed. The real check comes after S2 merges.

**The owner's ruling of 2026-09-26 (Task 12, and Tasks 10-11 amended).** Measured on scratch exports; nothing in the repository was touched.
- Task 12's blocks were applied verbatim to an export of `b18cacf` (22 replacements, each anchor matched once): red `13 failed, 300 passed`, green `313 passed` (64 + 103 + 100 + 46), and the neighbour selection of its Step 4 `550 passed` (541 before).
- Tasks 10 and 11, as amended, were then applied to a scratch tree of S2 with its Task 18 plus that S3 tree: `tests/test_webapp_flagged_positions.py` `107 passed` after Task 10 (`153` with the currency file) and `112 passed` after Task 11. The selections of Task 11 Step 3 (S3's files, Core and Guards/JS) gave `995 passed` and the known `test_no_literal_account_numbers_in_ocr` failure.
- Task 11's factoring credit reads `INVOICE PAYMENT`, so S2's operating-revenue path makes it verified revenue and the package decision stays `approved`.

**Review fixes (2026-09-25).** An independent review ACCEPTED this plan WITH FIXES. The fixes were re-measured by replaying the edited blocks, stage by stage, on a clone of the reviewer's replay of `4f219cd`. Every count above is from that replay.
- **S1 conformance (major).** When this plan was first written, S1's plan built an eight-group `analysis/flag_groups.py` with `state: str`. Task 1, Step 3 now stops and reports when S1's module fails the C1 pin. Task 1, Step 7 takes `lender-detection`'s copy during a rebase only after the same pin passes; otherwise it aborts the rebase. Both outcomes were simulated (Task 1, Step 7). S3 never edits S1's module.
  - S1's plan was amended on 2026-09-25 and now creates the module as C1 verbatim: eleven groups, `state: str | None`, and premium financing with `state=None`.
  - A replay of this plan's Task 1 commit onto S1's amended module passed the pin and finished the rebase (Task 1, Step 7).
  - Steps 3 and 7 stay as safeguards, and are not expected to fire.
- **One snapshot per package (minor).** Two tests were added in Task 5 and one in Task 7. Each mutation below was caught, while every earlier test still passed. The counts depend on the stage, because Task 7's roll-up snapshot test also catches the first two. They were re-measured on the Task 5 and Task 9 replay trees over `tests/test_webapp_flagged_positions.py tests/test_package_currency.py tests/test_webapp_settings.py tests/test_l1s3_surfaces.py tests/test_webapp_app.py`:
  - `_package_members` calling `_displayed(job.analysis or {})` (three reads counted instead of one): 2 failed at Task 5, and 3 failed from Task 7 on;
  - `_package_analysis` calling `_package_members(jobs)` without the snapshot: 2 failed at Task 5, and 3 failed from Task 7 on;
  - the roll-up reading `enabled_group_keys(load_settings(...))`, which exists from Task 7 on: 2 failed from Task 7 on.
  - The two Task 5 tests fail under the first two mutations at every stage. From Task 7 on, `test_the_roll_up_reads_the_same_snapshot_as_the_member_rows` fails as well. The third mutation fails `test_a_package_reads_the_settings_once_and_hands_that_snapshot_to_every_member` and the roll-up snapshot test.
- **Commit attribution (minor).** Every commit command now carries the attribution trailer as its second `-m`.
- **Tests outside the selections.** Three tests fail at `4f219cd` before any S3 change (measured on the repository: `3 failed`). They are listed in Task 11, Step 3.

**Second verification (2026-09-25).** A fresh replay of every block reproduced every count above, and found two wording issues, both fixed above: the S1 conformance text described S1's plan before its amendment, and the mutation counts were given for one stage only. The master plan's new C10 (the curated registry ledger) was checked against this plan too:
- S3 does not reference S1's builder, its research inputs or its task numbers.
- Task 11 now states its one dependency on the ledger: the premium-finance, floor-plan and factoring tables must each hold an admitted entity.
- `first_alias` now names an empty table in its failure. With fabricated stub tables it produced a payload identical to the earlier helper's. With each table emptied in turn, it raised an `AssertionError` naming that table, for example `FLOOR_PLAN_ALIASES holds no alias: the C10 ledger admits no entity in this group`.

**Cross-plan consistency check (2026-09-25).** Three changes, none to a count above:
- Contract point 3 now quotes S4's current `PACKAGE` fixture (8 debits, 5450.0) instead of an earlier draft's figures.
- Task 11's notes now say that S1's validator already requires the owner-named floor-plan, factoring and premium-finance payees; `first_alias` stays as a safeguard.
- Task 3 declares `apply_flagged_groups_to_payload` in the L1-S3 surface census (the master plan's decision), and Task 3 Step 4 and Task 11 Step 3 run `tests/test_l1s3_census.py`. Measured without `discovery_reports/` at `4f219cd`, the census holds (0 reader failures, 0 seam failures). The entry's placement was rebased against S5's census entry on a scratch copy of the file, cleanly in both orders of the two edits' commits.
