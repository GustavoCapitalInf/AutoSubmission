# Lender Detection and Flagged Positions: Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement each service plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Count as lenders only MCA funders and equipment financing. Flag eleven other groups (alternative positions, lines of credit, credit cards, vehicle, bank loans, mortgages, leases & rentals, personal loans, floor plan, factoring, premium financing), each with its own Settings checkbox, and keep them out of lender math. Make detection find the lenders it misses today.

**Architecture:**
- A compiled known-payee matcher covers one alias table per group. It feeds a reordered classifier with new states, a financing-proceeds rule for credits, and a potential tier for unknown funders.
- The analysis payload carries every group.
- The webapp filters groups by Settings at serving time, following the NSF carry-over pattern.
- The dashboard adds a Settings section, a Flagged positions panel, tags and a re-analyze action.

**Spec:** `docs/superpowers/specs/2026-09-24-lender-detection-design.md` (approved 2026-09-24). Section numbers (§) below refer to it.

**Tech Stack:** Python 3.14 (`C:\Python314\python.exe`), pytest 9, Flask, vanilla JS (`webapp/static/app.js`, tested in node through `tests/webapp_js_harness.py`), SQLite (`webapp/storage.py`).

## Global Constraints

- Only MCA/revenue-based funders and equipment financing are lenders (`confirmed_lender`). Nothing else enters `lender_*`, `withholding_*`, `eligible_deposits` (except the D1 proceeds exclusion) or the package `decision`.
- Every flag group has a Settings key, default `True`, applied at serving time. Unticking hides only (D7).
- Counterparty names and aliases live **only** in `analysis/classification_registry.py`. The guard is `tests/test_no_statement_hardcodes.py:85-87`, and there is no second exempt module.
- **Privacy:**
  - Tests use fabricated descriptors only.
  - Never commit statement text, amounts, account numbers, dates or customer names.
  - Commit messages quote no statement values.
  - Re-pinned regression expectations use derived totals only.
- `CLASSIFICATION_VERSION = "5.0"` and `ANALYSIS_STAGE_VERSION = 19` land in the same commit as the classifier change (S2). The D6 clarification (2026-09-26) moves them to `"5.1"` and `20` together, and the second one (2026-09-27) to `"5.2"` and `21`.
- Run tests with `C:\Python314\python.exe -m pytest tests/<files> -q -p no:cacheprovider`. **Always pass paths under `tests/`**: a bare `pytest` also collects `discovery_reports/`.
- Known failure that predates this work, and must not be attributed to it: `tests/test_no_statement_hardcodes.py::test_no_literal_account_numbers_in_ocr`.
- Write or patch Python with the Write/Edit tools, not with Bash heredocs (the Bash tool mangles backslashes here). Restart Flask after template edits.
- Subagents: Opus 5.5 only, never Fable. Each service runs on its own branch, and only the orchestrator merges.
- No payee or brand literals in `webapp/static/app.js` (`tests/test_revenue_classification.py:812-844`, `tests/test_lender_insurance_classification.py:566-584`). Every `formatMoney(` call passes an explicit currency (`tests/test_package_currency.py:773-796`).

## Branches and order

| Service | Plan | Branch (from) | Starts after |
|---|---|---|---|
| S1 Registry and matcher | `2026-09-24-lender-detection-s1-registry-matcher.md` | `ld-s1-registry` (from `lender-detection`) | now for Tasks 1-8; Task 9 only after the C10 ledger gate below |
| S2 Classifier and analysis payload | `2026-09-24-lender-detection-s2-classifier.md` | `ld-s2-classifier` (from `lender-detection` after S1 merges) | S1 merged, and the orchestrator's checks of S1 below done |
| S3 Webapp serving, package, downloads | `2026-09-24-lender-detection-s3-webapp.md` | `ld-s3-webapp` (from `lender-detection`) | the contract below; finishes on top of S2 |
| S4 Dashboard | `2026-09-24-lender-detection-s4-dashboard.md` | `ld-s4-dashboard` (from `lender-detection`) | the contract below; finishes on top of S2 and S3 |
| S5 Re-analysis of saved statements | `2026-09-24-lender-detection-s5-reanalysis.md` | `ld-s5-reanalysis` (from `lender-detection`) | the contract below; finishes on top of S2 and S3 |

- **Merge order:** S1 → S2 → S3 → {S4, S5}. S4 and S5 may merge in either order; their `webapp/static/app.js` edit sites do not overlap (S5's "S5-specific constraints").
- **The owner's ruling of 2026-09-26 (factoring credits: revenue, and flagged).** It adds one task per service that builds a surface of it, and it moves no merge:
  - S2's Task 18 runs after its Task 17, before S2 merges. It covers the C4 record, the C5 fields, the documentation corrections and a read-only cache measurement.
  - S3's Task 12 runs after its Task 9 and before its Tasks 10-11. It needs nothing from S2, and Tasks 10-11 are written on top of it.
  - S4's Task 15 runs after its Task 12 and before its Task 13. It needs nothing from S2 or S3, and its Task 14 covers it.
  - S5's plan records the owner's ratification of its item 2. Its Task 11 pin still counts a factoring deposit among the reviews a rule decides, which the ruling ends. That deposit is now replayed, so the pin's counts move. This is open for the orchestrator.
- **Review and merge.** Each service ends with an independent Opus review. The orchestrator checks the evidence (reruns the service's tests, reads its diff) before merging into `lender-detection`.
- **S3, S4 and S5** build against fabricated payloads that follow the contract below. They rebase onto `lender-detection` once S2 has merged, and re-run their tests there. S4 and S5 close only after S3 has merged too, and rebase again onto it:
  - S4's Task 14 is its final verification on top of S2 and S3;
  - S5's Task 11 pins C6's `analysis_rules_outdated` and S3's `flag_shown` through `_displayed`. Before S3 merges, it fails with `KeyError: 'analysis_rules_outdated'`.
- **The C10 ledger gate (before S1's Task 9).** S1 stops after Task 8 until all of these hold (S1, "Prerequisite: the curated ledger"):
  1. The orchestrator's research workflow (C10) has committed `docs/lender-registry-ledger.json` on `lender-detection` or on `ld-s1-registry`.
  2. On a checkout that has S1's Task 7, the orchestrator runs S1's preview command (`--write` into a folder outside the repository) or `python -m tools.build_lender_registry --check --ledger <ledger>`. It exits 0 and prints no `problem:` line. A problem is fixed in the ledger, never in S1's code.
  3. The orchestrator reads every `move:` line and checks that each reason is about its move.
  4. The owner reads the rendered evidence ledger: the lender list first, then the moves and the entities awaiting a ruling. For a revised ledger, the owner reads the changed entities.
  5. The message that starts S1's Task 9 says that 1-4 hold.

## Interface contract (every service uses exactly these names)

### C1. `analysis/flag_groups.py` (created by S1; no imports from other analysis modules)

```python
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
    # Owner ruling 2026-09-27 (classification 5.3): debt-settlement account processors and debtor-side debt-relief
    # firms. Never lender math, and not in FINANCING_STATES: its payees never lend.
    FlagGroup("debt_relief", "debt_relief", "flag_debt_relief", "Debt relief"),
)
FLAG_GROUP_BY_STATE: dict[str, FlagGroup] = {g.state: g for g in FLAG_GROUPS if g.state is not None}
FLAG_GROUP_BY_KEY: dict[str, FlagGroup] = {g.key: g for g in FLAG_GROUPS}
FLAG_SETTING_KEYS: tuple[str, ...] = tuple(g.setting for g in FLAG_GROUPS)
# D1: a credit from a payee of these states is financing proceeds (non_revenue + lender credit exclusion),
# except a PAYOUT_CREDIT_ENTITIES entity's credit (revenue) and a factoring payee's credit (owner ruling
# 2026-09-26: revenue, and flagged as factoring).
FINANCING_STATES: frozenset[str] = frozenset({
    "confirmed_lender", "alternative_position", "line_of_credit", "bank_loan",
    "vehicle_financing", "mortgage", "personal_loan", "floor_plan_financing", "factoring",
})
```

(Amended 2026-09-27, classification 5.3: docs/superpowers/plans/2026-09-27-false-potential-lenders.md.) The twelfth `FlagGroup`, Debt relief, comes last (owner ruling 2026-09-27). Its state `debt_relief` is not in `FINANCING_STATES`, so a debt-relief payee's credit is never financing proceeds.

### C2. `analysis/classification_registry.py` (S1)

- **Group alias tables**, each `dict[str, tuple[str, ...]]` (canonical entity → aliases):
  - `LENDER_ALIASES`
  - `ALTERNATIVE_POSITION_ALIASES`
  - `LINE_OF_CREDIT_ALIASES`
  - `CARD_ISSUER_ALIASES`
  - `VEHICLE_FINANCE_ALIASES`
  - `MORTGAGE_SERVICER_ALIASES`
  - `LEASE_RENTAL_ALIASES`
  - `PERSONAL_LOAN_ALIASES`
  - `FLOOR_PLAN_ALIASES`
  - `FACTORING_ALIASES`
  - `PREMIUM_FINANCE_ALIASES` (premium-finance payees; the S2 insurance rule consults it, and it is **not** in `PAYEE_GROUP_REGISTRIES`)
- **`BANK_NAME_ALIASES`**, a `dict[str, tuple[str, ...]]` of banks, used only for D5.
- `POTENTIAL_LENDER_ALIASES`, `INSURANCE_PROVIDER_ALIASES`, `OPERATING_REVENUE_SOURCE_ALIASES` and `OPERATING_REVENUE_SOURCE_TYPES` keep their names.
- `CONFIRMED_LENDER_ALIASES = LENDER_ALIASES` remains as a compatibility name. `analysis/lenders.py` reads only this name (`analysis/lenders.py:4, 13`), so neither S1 nor S2 edits it.
- **Today's lists, until S2.** S1 changes no classification, so it keeps today's three lists as deprecated verbatim copies that the pre-S2 classifier reads: `LEASE_PROVIDER_ALIASES`, and today's confirmed and potential lists renamed `LEGACY_CONFIRMED_LENDER_ALIASES` and `LEGACY_POTENTIAL_LENDER_ALIASES`. The classifier is their only reader. S2's Task 5 removes those reads, and S2's Task 6 deletes all three tables with their "Deprecated" comment block. After S2, `LEASE_PROVIDER_ALIASES` no longer exists.
- **Hand-kept validator inputs.** Seven constants live in this module, outside the GENERATED block, and change only on an owner ruling:
  - `OWNER_NAMED_PAYEES`, `BARE_PLATFORM_NAMES` and `BARE_BRAND_NAMES` (S1, spec §2 and §5);
  - on the owner's rulings of 2026-09-25 (spec §2 and §5):
    - `PREMIUM_FINANCE_INSURER_ALIASES: tuple[str, ...]`, the premium-finance spellings that may equal an alias of the hand-kept `INSURANCE_PROVIDER_ALIASES` (`("FIRST INSURANCE",)`);
    - `MERGED_REGISTRY_ENTITIES: dict[str, str]`, an entity of today's registry mapped to the ledger entity that absorbs it (`{"EBF HOLDINGS": "EVEREST BUSINESS FUNDING"}`);
    - `REATTRIBUTED_REGISTRY_ALIASES: dict[str, str]`, an alias of today's registry that names another company, mapped to that company's ledger entity (`{"SMARTPAY SOL": "SmartPay Solutions, LLC"}`);
    - `PAYOUT_CREDIT_ENTITIES: tuple[str, ...]`, the ledger entities whose credits are the account holder's own sales settled by the platform (`("Sezzle Inc", "American First Finance, LLC", "PAYABILITY")`). S2 reads it as D1's exception (C4).

  S2 never edits or deletes them. They sit between `PAYEE_GROUP_REGISTRIES` and the Deprecated block, so S2's deletion of that block does not reach them.
- **`PAYEE_GROUP_REGISTRIES`** is a `dict[str, dict[str, tuple[str, ...]]]` keyed by classification state, in this order:
  - `"confirmed_lender"` → `LENDER_ALIASES`
  - `"alternative_position"` → `ALTERNATIVE_POSITION_ALIASES`
  - `"line_of_credit"` → `LINE_OF_CREDIT_ALIASES`
  - `"vehicle_financing"` → `VEHICLE_FINANCE_ALIASES`
  - `"mortgage"` → `MORTGAGE_SERVICER_ALIASES`
  - `"personal_loan"` → `PERSONAL_LOAN_ALIASES`
  - `"floor_plan_financing"` → `FLOOR_PLAN_ALIASES`
  - `"factoring"` → `FACTORING_ALIASES`
  - `"lease_or_rental"` → `LEASE_RENTAL_ALIASES`
  - `"credit_card_payment"` → `CARD_ISSUER_ALIASES`
- **Card issuers.** The `CARD_ISSUER_ALIASES` entries need card-payment context. S1 stores bare issuer names such as `CAPITAL ONE` in a separate table, `CARD_ISSUER_CONTEXT_ALIASES`, used only by the S2 descriptor rule (§4.3 step 8).
- (Amended 2026-09-27, classification 5.3: docs/superpowers/plans/2026-09-27-false-potential-lenders.md.)
  - **`DEBT_RELIEF_ALIASES`**, a `dict[str, tuple[str, ...]]` rendered from the ledger's `debt_relief` group. It is **not** a known-payee registry and is not in `PAYEE_GROUP_REGISTRIES`: only `match_debt_relief_payee` (C3) reads it, on a debit no known payee claimed.
  - **`REVIEW_FLAG_ENTITIES`**, a `dict[str, str]` rendered in the GENERATED block after the tables: each `review` entity of a routed flag group (vehicle financing, mortgage, lease or rental, personal loan, debt relief) whose business type is known, mapped to that group (C10). The entities stay in `POTENTIAL_LENDER_ALIASES`.
  - **`FIELD_ORDER_PAYEE_FORMS`**, a hand-kept `dict[str, tuple[str, ...]]` beside the other owner-ruled inputs (owner ruling 2026-09-27): an admitted ledger entity of a known-payee group mapped to the regular expressions of its printed forms in the bank's field order (Chase's 'ORIG CO NAME … CO ENTRY DESCR', Truist's entry description first), read on debits only when no alias matched.
  - `CARD_ISSUER_CONTEXT_ALIASES` is also read the other way: an issuer alias whose words lead a D6 payee's words is a card payment printed alone, which D6 does not take.

### C3. `analysis/payee_matcher.py` (S1)

```python
from dataclasses import dataclass
from typing import Mapping, Sequence

@dataclass(frozen=True)
class PayeeMatch:
    entity: str   # canonical entity
    state: str    # classification state from PAYEE_GROUP_REGISTRIES
    alias: str    # the alias as written in the registry

class AliasIndex:
    """Aliases normalized and compiled ONCE. match() returns the longest normalized alias found on token
    boundaries (?<![A-Z0-9])alias(?![A-Z0-9]); ties go to the earlier registry, then the earlier alias.
    A spaced alias whose run-together form has >= 8 characters also matches that form."""
    def __init__(self, registries: Mapping[str, Mapping[str, Sequence[str]]]) -> None: ...
    def match(self, normalized_text: str) -> PayeeMatch | None: ...

def match_known_payee(normalized_text: str) -> PayeeMatch | None: ...   # over PAYEE_GROUP_REGISTRIES
def registry_match(normalized_text: str, registry: Mapping[str, Sequence[str]]) -> tuple[str, str] | None: ...
    # Same (canonical, alias) semantics as today's transaction_classifier._registry_match (longest alias
    # first within one registry, same boundary rule), compiled once per registry object; used by S2
    # for the insurance, potential, operating and bank-name registries.
```

(Amended 2026-09-27, classification 5.3: docs/superpowers/plans/2026-09-27-false-potential-lenders.md.)

```python
class AliasIndex:
    def __init__(self, registries, *, run_together: bool = True, glued_digits: bool = False) -> None: ...
    # glued_digits: the last word of a multi-word alias whose last word has three letters or more also matches
    # that word with digits glued on (GOAT ADVANCE1234). Only _DEFAULT_INDEX (the known-payee index) sets it.

def match_debt_relief_payee(normalized_text: str) -> PayeeMatch | None: ...
    # The longest DEBT_RELIEF_ALIASES alias (state "debt_relief"), read through an index of its own built with
    # run_together=True (FORTHPAY, RAMPAYMENTS). The classifier calls it only after no known payee matched, on a
    # debit, with the row's receiver fields removed.
```

### C4. Classification record and states (S2, `analysis/transaction_classifier.py`)

- **New states** in `ClassificationState` and `CLASSIFICATION_STATES`:
  - `alternative_position`
  - `line_of_credit`
  - `vehicle_financing`
  - `bank_loan`
  - `mortgage`
  - `lease_or_rental`
  - `personal_loan`
  - `floor_plan_financing`
  - `factoring`
- **Premium financing:** an insurance row whose insurer match is a `PREMIUM_FINANCE_ALIASES` payee, or (owner ruling 2026-09-25) whose descriptor has premium-finance wording and no such payee, keeps `classification="insurance"` and `contributes_to_insurance_totals`. It also gets `flagged_group="premium_financing"` and `contributes_to_flagged_totals` (posted debits only).
- `lease_or_equipment_financing` is **no longer produced**. It remains in `CLASSIFICATION_STATES` so that stored records still validate, and the dashboard keeps its label.
- **New `TransactionClassification` fields**, with defaults:
  - `flagged_group: str | None = None`, the `FlagGroup.key` for a flag-group state, otherwise None;
  - `contributes_to_flagged_totals: bool = False`, True for a posted debit whose state is a flag-group state, and for a posted factoring credit (owner ruling 2026-09-26, below). It is cleared for duplicates, settlement-reversed debits and credits that the reversal pass pairs with a debit.
- A credit from a `FINANCING_STATES` payee has:
  - `classification="other"`
  - `canonical_entity=<entity>`
  - `matched_rule="financing_proceeds_credit"`
  - `contributes_to_lender_credit_exclusion=True`
  - revenue `non_revenue` with `revenue_match_method="financing_proceeds_credit"`

  There are two exceptions.
  - **Payout credits.** A payee whose entity is in C2's `PAYOUT_CREDIT_ENTITIES` (spec D1, owner ruling 2026-09-25). Its credit is not financing proceeds: it goes on to the operating-revenue path with today's treatment of platform settlements, with no `financing_proceeds_credit` and no `contributes_to_lender_credit_exclusion`. Its debits keep their group.
  - **Factoring credits** (spec §2 and D1, owner ruling 2026-09-26). A factor's payout is the business's own sales. The credit takes the same revenue treatment as a payout credit: the operating-revenue path, no `financing_proceeds_credit`, no `contributes_to_lender_credit_exclusion`, so it stays in eligible deposits. It also carries the Factoring flag, with this record:
    - `classification="factoring"`
    - `canonical_entity=<entity>`, `match_method="known_payee_alias"`, `matched_alias=<alias>`
    - `matched_rule="factoring_revenue_credit"`
    - `flagged_group="factoring"`, and `contributes_to_flagged_totals` when it is posted (cleared as above)
    - the revenue fields of the operating-revenue path

    A factoring credit that an earlier rule claims (a transfer, an insurance term) keeps that rule's state, with no flag and no exclusion. Factoring debits are unchanged. `FINANCING_STATES` keeps `factoring` (C1): the payee still claims its credit at step 7, which S1's alias audit reads.
- Three credits are financing proceeds by their own words, with no payee named (spec D1, owner rulings 2026-09-25): the statement bank's own line advance (exactly `LOAN CREDIT`), a line-of-credit draw, and a per-vehicle floor-plan advance. They get the same record, except that `matched_rule` (and `revenue_matched_rule`) names the rule (`bank_line_advance_credit`, `loc_draw_credit`, `floor_plan_advance_credit`) and `canonical_entity` is the statement bank, or None for the floor-plan advance.
- `CLASSIFICATION_VERSION = "5.0"`; `"5.1"` since the D6 clarification (2026-09-26: three different dates, no card-purchase posting), with `ANALYSIS_STAGE_VERSION` 19 → 20; `"5.2"` since the second D6 clarification (2026-09-27: no compensation memo, a masked recipient account after `TO` is part of the payee), with `ANALYSIS_STAGE_VERSION` 20 → 21; `"5.3"` since the false-potential release (2026-09-27), with `ANALYSIS_STAGE_VERSION` 21 → 22.
- (Amended 2026-09-27, classification 5.3: docs/superpowers/plans/2026-09-27-false-potential-lenders.md.)
  - **The state `debt_relief`** in `ClassificationState` and `CLASSIFICATION_STATES`: a debit to a debt-relief payee (`match_debt_relief_payee`), or to a routed review entity of the debt-relief group. Debits only; a credit keeps today's rules.
  - **The field `potential_payee_label: str | None = None`**, last in `TransactionClassification`: the Potential Lenders line of an unnamed potential payee ('Unidentified lender obligation' or 'MCA servicer (funder not identified)'), one per payee key within the statement, for example 'Unidentified lender obligation (weekly, 450.00)', with ' #2' for a second key with the same label. `canonical_entity` does not change.
  - **Two match methods:**
    - `unconfirmed_flag_payee_alias`: a debit whose potential alias belongs to a `REVIEW_FLAG_ENTITIES` entity takes that group's state, `matched_rule="<state>_review_registry"` and `review_required=True`;
    - `known_payee_field_order`: a debit that a `FIELD_ORDER_PAYEE_FORMS` form reads takes its payee's group, `matched_rule="<state>_field_order"` (D9's LOC wording still wins), with no `matched_alias`.

### C5. Analysis payload (S2), per account

- `metrics.flagged_groups`: `{"<group key>": {"count": int, "total": float, "count_credited": int, "total_credited": float, "payees": int}}`. It contains only groups with at least one contributing row, and the money is rounded to 2 decimals.
  - `count` and `total` are the contributing debits.
  - `count_credited` and `total_credited` are the contributing credits: a factor's payouts, owner ruling 2026-09-26. They are 0 and 0.0 in a group without one.
  - `payees` counts the payees with any contributing row.
- `detection.flagged_positions`: a list of objects, sorted by `group` in FLAG_GROUPS order, then by `total_debited + total_credited` descending, then by `payee`. Each object has:

  ```json
  {"group": "<group key>", "payee": "<canonical_entity or group label>", "matched_alias": "<alias or null>",
   "count": 3, "total_debited": 1234.5, "count_credited": 0, "total_credited": 0.0,
   "cadence": "monthly", "avg_gap_days": 30.5,
   "first_date": "YYYY-MM-DD or null", "last_date": "YYYY-MM-DD or null",
   "source_locations": ["transaction:4", "transaction:9"]}
  ```

  - `count` and `total_debited` stay debit-only. `count_credited` and `total_credited` are the position's contributing credits, 0 and 0.0 without one (owner ruling 2026-09-26).
  - A position whose rows are only credits exists, with `count` 0 and `total_debited` 0.0.
  - `cadence`, `avg_gap_days`, `first_date`, `last_date` and `source_locations` read every contributing row, debit or credit.
- `analysis/cadence.py` provides `describe_cadence(dates: Sequence[date]) -> tuple[str, float | None]`, returning one of `"daily" | "weekly" | "biweekly" | "monthly" | "irregular" | "single"`.
- (Amended 2026-09-27, classification 5.3: docs/superpowers/plans/2026-09-27-false-potential-lenders.md.)
  - Each flagged position carries `review_required: bool` **last**, after `source_locations`: true when any contributing row of the payee requires review (a routed unconfirmed payee).
  - `detection.potential_lenders[].funder` is the `potential_payee_label` for an unnamed payee, so each unnamed payee key is its own entry. `metrics.potential_lenders_detected` counts those labels, and a named payee keeps its entity.

### C6. Serving (S3)

- `analysis/flagged_view.py` provides `apply_flagged_groups_to_payload(payload: object, *, enabled: Mapping[str, bool]) -> object`:
  - It takes `enabled`, keyed by `FlagGroup.setting`; a missing key counts as True.
  - It deep-copies every account's `statement.transactions`, `detection` and `metrics` before changing them.
  - On each account, it drops unticked groups from `metrics.flagged_groups` and `detection.flagged_positions`.
  - It sets `classification["flag_shown"] = bool(flagged_group and enabled[group.setting])` on every copied row.
  - At the TOP level of the returned payload, it sets `analysis_rules_outdated: bool`: True when any row's classification record carries no `classification_version` (absent or null), or a readable one older than the running `CLASSIFICATION_VERSION`. The two compare as numeric `(major, minor)` pairs, and the running version is read from `analysis.transaction_classifier` at each call. The same or a newer version is not outdated.
    - A record without the field predates versioning, so older lender rules classified it (D12). The orchestrator decided this on 2026-09-26, delegated by the owner: the sentence used to say "is present", which left stored analyses of version-less revenue records without the notice and the Re-analyze button.
    - Any older version, not only a major version below 5. The orchestrator decided this on 2026-09-26, delegated by the owner: the sentence used to say "whose major version is below 5", which would have left a 5.0 analysis without the notice and the Re-analyze button once the D6 clarification (5.1) runs. A re-analysis clears it.
    - A version that is present but cannot be read marks nothing. Only `<major>` or `<major>.<minor>` in ASCII digits is read, around outer whitespace; an integer reads as `<major>.0`.
    - A payload with no classification record is False.
  - It never raises. A non-dict payload is returned unchanged.
- `webapp/app.py`:
  - `_displayed(analysis, *, carry_over=None, settings=None)`. Settings are loaded once when `settings is None`, and `carry_over` still overrides NSF when it is given.
  - One settings read per package. `_package_analysis(jobs, *, settings=None)` calls `_package_members`, so it reads the settings once and passes them to `_package_members(jobs, *, settings=None)`, which reads them itself only when it is called alone. Both keep today's call shapes (S3, "Contract points" 2).
  - The package payload gains:
    - top-level `flagged_positions: {"<group key>": [{"payee", "documents", "count", "total_debited", "count_credited", "total_credited", "cadence", "first_date", "last_date"}]}`, for ticked groups only;
      - `count` and `total_debited` are the counted debits, and `count_credited` and `total_credited` the counted credits (owner ruling 2026-09-26);
      - items are ordered by `total_debited + total_credited` descending, then payee, or by `count + count_credited` under a currency refusal;
      - the dates and the cadence read both;
    - top-level `flagged_evidence`: a list of the counted flagged classification records of the ticked groups (credits included), each with `source_job` and `source_document`, plus `source_account` for an account of a multi-account document (spec §8.3). It goes to the JSON only; the CSV/XLSX carry the `flagged_<group>_<n>` rows (§8.4);
    - `totals.flagged_position_count` (int: the ticked groups' counted debits, the sum of the items' `count`) and `totals.flagged_position_total` (money);
    - `totals.flagged_position_count_credited` (int: the counted credits, the sum of the items' `count_credited`; unit-free) and `totals.flagged_position_total_credited` (money; it joins `_CROSS_CURRENCY_TOTAL_KEYS`, and `total_credited` joins `_CROSS_CURRENCY_ROLLUP_KEYS`), owner ruling 2026-09-26.
  - The statement sheets' `flagged_<group>_<n>` sections carry `payee`, `count`, `total_debited`, `count_credited`, `total_credited` and `cadence`. The package sheets carry every item and total field, and the currency sweep covers the credited ones.
  - Serving needs no new rule for credits: `flag_shown` and the group filter key on `flagged_group`, so a ticked group's credit row is shown and its credited figures are served, and an unticked group's are hidden with its debits.
  - (Amended 2026-09-27, classification 5.3: docs/superpowers/plans/2026-09-27-false-potential-lenders.md.) Each package flagged item carries `review_required` **last**, after `last_date`: true when any member's counted row of the payee requires review. The statement and package sheets' `flagged_<group>_<n>` sections carry it last too. The package's potential rows are keyed by `potential_payee_label` when a row has one, else by `canonical_entity`.

### C7. Settings (S3)

`webapp/settings.py` `DEFAULTS` gains every key in `FLAG_SETTING_KEYS`, each set to `True`.

### C8. Dashboard (S4, `webapp/static/app.js` and `webapp/templates/index.html`)

- **Constant.** `FLAG_GROUP_LABELS` is an object literal keyed by group key, with the labels from C1. A test checks that it matches `analysis/flag_groups.py`.
- **Settings markup.** A section `id="flagSettingsSection"` holds the container `id="flagSettingsList"` and the status line `id="flagSettingsStatus"`. Checkbox rows are rendered by `renderFlagSettings(settings, disabled)`, and each input carries `data-flag-setting="<settings key>"`.
- **Panel markup.** The panel `id="flaggedCard"` holds `id="flaggedCount"` and `<tbody id="flaggedTable">`. It is rendered by `renderFlaggedPositions(positions, currency, isPackage)`. On a statement, `positions` is the `detection.flagged_positions` list; on a package, it is the `pkg.flagged_positions` object.
  - Since the owner's ruling of 2026-09-26, a row with `count_credited` above 0 shows its credits under its Count and Total as detail lines, "`<n>` received" and "`<money>` received", on the results page, the package page and the statement window. The columns and headers do not change.
- **Filter.** `filterTransactions` gains the filter `"flagged"`, which keeps rows whose `classification.flag_shown === true`. It and the "Flagged" chip key on the row's flag fields, never on its direction, so they cover flagged credit rows (a factor's payouts). A credit still shows its revenue tag first.
- **Outdated notice.** The notice `id="rulesOutdatedNotice"` has a button `id="reanalyzeButton"`. It is shown when the served analysis has `analysis_rules_outdated === true`.

### C9. Re-analysis (S5)

- `POST /analysis/<job_id>/reanalyze` returns 200 with `{"analysis": <displayed, masked>, "reviews_replayed": int, "reviews_not_replayed": int, "reviews_decided_by_rules": int}` (S5 Decisions 5-6). It refuses in this order:
  1. 400 `{"error": "the request must be a JSON object"}` for a body that is not a JSON object, the review and settings routes' CSRF rule (S5 Decision 4);
  2. 404 `{"error": "job not found"}` for an unknown job;
  3. 409 `{"error": "job is not finished"}` when the job is not done;
  4. 409 `{"error": "the original PDF is not stored"}` when the PDF is missing.
- It returns 422 `{"error": "no new analysis was saved; the saved analysis is unchanged", "reason": str}` when the re-run produces no analysis to save, and writes nothing (S5 Decision 3). `reason` is text the worker already publishes, or one of `webapp/reanalysis.py`'s `READING_NOT_CACHED` and `READS_DIFFERENTLY`.
- The previous `analysis_json` is written to the audit log before it is replaced, in one transaction with the job update. The audit row has `event_type = "reanalysis"` and `detail = {"reviews_replayed": [ids], "reviews_not_replayed": [ids], "reviews_decided_by_rules": [ids], "previous_analysis_json": <stored text, verbatim>, "previous_analysis_error": <text or null>}` (S5 Decision 6).
- The JS calls it from `#reanalyzeButton` and re-renders from the response.
- The owner ratified S5's two open decisions on 2026-09-26 (S5, "What the orchestrator must ratify", item 2), and the plan's defaults stand:
  - cache-only re-reading (Decision 2): a statement whose reading is not cached is refused with `READING_NOT_CACHED`, and the owner accepts the decision's two known limits;
  - rule-decided reviews reported apart (Decision 5): `reviews_decided_by_rules` stays in the 200 body and the audit detail as written above.

### C10. The curated registry ledger (data; the orchestrator produces it, S1 consumes it)

The research is consolidated into one entity per company **outside the code**, by an orchestrator research workflow: consolidation, an adversarial check per entity, and a completeness critic. The result is committed as `docs/lender-registry-ledger.json`. **The code never infers names, groups or aliases from raw research output.** It only validates the ledger and renders the GENERATED part of `analysis/classification_registry.py` from it, deterministically. A drift test checks that the committed registry equals the rendering of the committed ledger.

```json
{
  "schema": 1,
  "entities": [
    {
      "entity": "Hunter Caroline",
      "group": "confirmed_lender",
      "business_type": "mca_or_revenue_based_funder",
      "aliases": ["HUNTER CAROLINE"],
      "status": "admitted",
      "short_alias_reason": null,
      "evidence": [{"source": "https://www.huntercaroline.com/", "note": "company site: small-business funding"}],
      "verdicts": [{"round": "r1", "verdict": "upheld", "confirmed": true}],
      "where_looked": ["https://www.huntercaroline.com/"],
      "notes": ""
    }
  ]
}
```

**`group`** is one of:
- `confirmed_lender`
- `alternative_position`
- `line_of_credit`
- `vehicle_financing`
- `mortgage`
- `personal_loan`
- `floor_plan_financing`
- `factoring`
- `lease_or_rental`
- `credit_card_payment` (aliases that are already payment-specific)
- `card_issuer_context` (bare issuer names, used only with card-payment context)
- `premium_financing`
- `bank_name`
- `potential_lender`

**`status`** decides where the entity is rendered:

| status | Rendered into |
|---|---|
| `admitted` | its group's table |
| `review` | `POTENTIAL_LENDER_ALIASES` (review tier), whatever its group |
| `owner_ruling` | no table; listed in the ledger document for the owner |
| `rejected` | no table; the ledger keeps it as evidence |

**The validator** (`tools/build_lender_registry.py --check`, plus unit tests) refuses the ledger when any of these hold:
- an `admitted` entity has no evidence, or no verdict of `upheld` or `corrected` with `confirmed: true`;
- an alias contains `#`, lowercase, or characters outside `[A-Z0-9 &]`;
- an alias is a bare generic word (a fixed list: CAPITAL, FUNDING, FINANCIAL, FINANCE, CREDIT, LOAN, LENDING, ADVANCE, BANK, GROUP, HOLDINGS, SERVICES, PAYMENT, LLC, INC, CORP…);
- an alias is a bare platform name outside the operating registry (SQUARE, SHOPIFY, PAYPAL, STRIPE, INTUIT, AMAZON);
- an alias has 4 characters or fewer without a `short_alias_reason`;
- the same alias appears under two entities;
- an owner-named lender (OnDeck, Bitty, Legend, LG Funding, Hunter Caroline, CAN Capital, CanaCap) is not an `admitted` `confirmed_lender`;
- an owner-named alternative position or line of credit is not `admitted` in its group.

**S1's validator is normative for the ledger producer.** `--check` applies every rule above and every rule of S1's Decision 3, and the research workflow writes the ledger to all of them. S1's "Prerequisite: the curated ledger" gives the spellings and the checks. A ledger written to the list above alone fails `--check`, and S1's Task 9 stops at its `problem:` lines. The rules the list above does not state:
- **Scope by status.** The character, digit, URL and entity-name rules, and "one alias, one entity", apply to every entity. The generic-word, platform, hand-kept-alias, brand, card-wording and short-alias rules apply only to `admitted` and `review` entities. A `rejected` or `owner_ruling` entity may keep a generic or colliding spelling as evidence.
- **Generic words.** A refused "bare generic word" is any alias made only of generic words (S1's `tools/lender_ledger.GENERIC_WORDS`, which holds the fixed list above). `FUNDING LLC` and `EQUIPMENT FINANCE` are refused too.
- **Platform names** include `AMZN` besides the six above (`BARE_PLATFORM_NAMES`).
- **Hand-kept tables.** An alias equal to an alias of the hand-kept `OPERATING_REVENUE_SOURCE_ALIASES` or `INSURANCE_PROVIDER_ALIASES` is refused. So is an entity named like a hand-kept entity, and an entity name used twice.
  - The one exception (owner ruling 2026-09-25): a `premium_financing` alias may equal an `INSURANCE_PROVIDER_ALIASES` alias when `PREMIUM_FINANCE_INSURER_ALIASES` holds that spelling (`FIRST INSURANCE`, held by FIRST Insurance Funding). The same spelling in any other group, or equal to an operating-revenue alias, is still refused.
- **Brands (spec §5).** An alias equal to a bare brand or issuer name in `BARE_BRAND_NAMES` (`TOYOTA`, `FORD`, `APPLE`, `CAPITAL ONE`…) is allowed only in `card_issuer_context` or `bank_name`.
- **Context-only groups.** No `review` entity may be in `credit_card_payment`, `card_issuer_context`, `bank_name` or `premium_financing`: a `review` entity renders into `POTENTIAL_LENDER_ALIASES`, which the classifier reads with no context. An unconfirmed entity of these groups is `owner_ruling` or `rejected`.
- **Card aliases.** Every `credit_card_payment` alias carries the wording of S2's card-payment rule: `CARD`, `CRD`, `CRCARD`, `CARDMEMBER`, `CREDIT CARD`, `AUTOPAY`, `AUTO PAY`, `EPAY`, `EPAYMENT`, `PAYMENT`, `PMT` or `PYMT`. A bare issuer name belongs in `card_issuer_context`.
- **Run-together forms (spec §4.6).** The run-together form of a spaced alias may not be another entity's alias or run-together form.
- **Every owner-named payee** in spec §2, in every group, resolves to its group (`OWNER_NAMED_PAYEES`): the lenders, including the equipment lenders; the alternative positions and lines of credit; the card issuers; the vehicle lenders; Truist as a `bank_name`; the lease-to-own names; the floor-plan, factoring and premium-finance payees. A bank or a premium financier must also match no known payee. Since the owner's ruling of 2026-09-25, BlueVine's spelling is `BLUEVINE CAPITAL` and SmartPay's is `SMARTPAY LEASING`.
- **Privacy.** No run of five or more digits outside a URL, unless today's registry already holds that exact alias. Every `evidence` source and `where_looked` entry is an http(s) URL without a query string or a fragment. The numbered Ontario company is an `owner_ruling` entity with no `evidence` and no `where_looked`, and its number appears nowhere.
- **Today's registry** (read from git at `693fd009c5c96a838ef47b61ba5b65a610ea5ba1`):
  - every entity of today's three lists is held by a ledger entity;
  - the entity that holds today's first alias keeps today's `entity` name, because S2's pins and the census compare names;
  - a **move** (a change of place, or a lost alias of today's registry) needs a sentence of `notes` that starts `Move:`, for example `"notes": "Move: spec §2 makes BDC an alternative position."` Any other note does not count. An entry of today's lease list may become a lender, a lease or rental, or vehicle financing without one (spec §4.1). The example above has empty `notes` because Hunter Caroline is not in today's registry.
- **Merged entities** (owner ruling 2026-09-25). Each `MERGED_REGISTRY_ENTITIES` key must be an entity of today's lists, and its value a ledger entity. The validator reads the merged entity as held by its target: it keeps no name of its own, and the aliases it loses need a `Move:` sentence in the target's `notes`, which is about the merge. A rendered ledger entity that still carries the merged name is refused.
- **Reattributed aliases** (owner ruling 2026-09-25). Each `REATTRIBUTED_REGISTRY_ALIASES` key must be an alias of today's lists, and its value the ledger entity that holds it. The alias is left out of today's entity: it does not decide which ledger entity holds that entity, it is not its first alias for the name rule, and it is not counted as lost. A rendered registry whose known-payee matcher, or else potential table, reads the alias as any other entity is refused.
- **Payout-credit entities** (owner ruling 2026-09-25). Every `PAYOUT_CREDIT_ENTITIES` name must be an `admitted` ledger entity of a group whose credits D1 makes financing proceeds (`FINANCING_STATES`). A `bank_name` entity is refused too.
- **Schema.** `schema` is 1, and every entity has exactly the ten fields of the example above, with their types.

`--check` and `--write` print one `move:` line per move, with its reason. A merged entity's line says `merged into <target>`, and an entity with a reattributed alias says `<alias> reattributed to <target>`. The orchestrator reads each one (the C10 ledger gate above).

`docs/lender-registry-evidence.md` is rendered from the ledger for the owner to read.

(Amended 2026-09-27, classification 5.3: docs/superpowers/plans/2026-09-27-false-potential-lenders.md.)
- **`group`** gains `debt_relief` (owner ruling 2026-09-27). An admitted `debt_relief` entity renders into `DEBT_RELIEF_ALIASES`, its own table and never a known-payee registry. Its run-together forms join the validator's run-together collision check, so a glued debt-relief alias can never equal a lender's alias or glued form. `OWNER_NAMED_PAYEES` holds its owner-named payees (RAM Payments / Reliant, Global Holdings, Tayne Law Group).
- **The routing rule.** `tools/lender_ledger.review_flag_entities` renders `REVIEW_FLAG_ENTITIES`: each `review` entity whose group is in `ROUTED_REVIEW_GROUPS` (`vehicle_financing`, `mortgage`, `lease_or_rental`, `personal_loan`, `debt_relief`) and whose `business_type` does not start with `unknown`, mapped to its group. The table stays `status`-driven: such an entity still renders into `POTENTIAL_LENDER_ALIASES`, which keeps its credits' exclusion, and only its debits take the flag, marked unconfirmed. A review entity of `confirmed_lender`, `potential_lender`, `alternative_position` or `factoring` is never routed. `tests/test_lender_registry_drift.py` renders the block with the map.
- **Generic words.** `GENERIC_WORDS` (and `tools/lender_census.GENERIC_WORDS`) gain `DEBT`, `RELIEF`, `SETTLEMENT`, `CONSOLIDATION`, `RESOLUTION`, `NEGOTIATION`, `PROGRAM` and `LAW`, so a phrase such as `DEBT RELIEF` alone is never an alias.
- **The field-order validator.** `--check` refuses a `FIELD_ORDER_PAYEE_FORMS` entity that is not an `admitted` ledger entity of a known-payee group, and a form that does not compile.

## Orchestrator verification (after each service, before merging)

1. Read the service's diff in full, and check it against its plan and the contract above.
2. Re-run the service's own test commands and the targeted selections below. Compare the result with the baseline (including the one known failure).
   - **Core:** `tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_r1_hardcodes.py tests/test_webapp_settings.py tests/test_package_currency.py tests/test_webapp_app.py`
   - **Guards/JS:** `tests/test_no_statement_hardcodes.py tests/test_new_statement_corpus.py tests/test_webapp_accounts_view.py tests/test_webapp_studio_views.py tests/test_webapp_review_ui.py`
   - **Wider:** `tests/test_analysis.py tests/test_artifact_cache.py tests/test_benchmark_harness.py tests/test_batch.py`
   - **Surface census:** `tests/test_l1s3_census.py`. It fails for any production function that reads the payload key `statement` (or `accounts`) and is neither declared in `tools/l1s3_surface_census.py`'s `READERS` nor excused in its `EXCUSED`. S3 declares `analysis/flagged_view.py::apply_flagged_groups_to_payload` (S3 Task 3), and S5 declares its readers (S5 Tasks 3-4). A rebase conflict in `READERS` or `EXCUSED` keeps both sides.
     - Run it from a worktree or clone that has no `discovery_reports/`. The census sweeps every `*.py` under the checkout, and the main checkout's gitignored `discovery_reports/` holds scratch copies of production modules. There it fails before any change (measured 2026-09-25 at `4f219cd`: `2 failed, 20 passed` in 194 s). With `discovery_reports/` left out, the census holds at `4f219cd` (0 reader failures, 0 seam failures).
     - It is its own item, not part of Guards/JS, because S1 and S2 pin the Guards/JS counts of the main checkout (`146 passed, 1 failed`).
3. Run an independent Opus review of the service's branch. Check every finding against the code before acting on it.
   - **Before S2 is branched**, the orchestrator (or the independent S1 reviewer) also:
     - reads every `move:` line that S1's last `--write` printed, as reported in S1's hand-off;
     - checks S1's allow decisions in S1's local `alias-review.json`, beside the `aliases` section of its `alias-audit.json`: every allow by key alone, and at least 30 others spread across entities, including every allow on a BlueVine alias (S1 Task 10 Step 7; the owner's ruling of 2026-09-25 dropped bare `BLUEVINE`). A wrong allow becomes a deny, which goes back through S1's Task 10 Step 4. The report names entities and counts, never a payee key.
4. After S2 has merged:
   - the local census (`tools/lender_census.py`);
   - the alias audit (`tools/lender_alias_audit.py`);
   - the owner's NMEF statement probe.
5. After S4 has merged: a real-browser check of the dashboard.
6. In the report to the owner, mark anything not confirmed and say where you looked.
