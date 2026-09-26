# Registry and Matcher (S1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver S1 of lender detection (spec §4.6 and §5; contract C1-C3 and C10; the owner's amendment of 2026-09-24):
- the eleven flag-group constants;
- a compiled known-payee matcher;
- the regrouped registry, rendered deterministically from the curated ledger `docs/lender-registry-ledger.json` (C10), including the floor-plan, factoring and premium-finance tables;
- the ledger's validator and the evidence ledger;
- a reviewed local alias-collision audit.

Until S2 lands, classification stays exactly what it is today.

**Architecture:**
- `analysis/flag_groups.py` holds the eleven flag groups (C1). Premium financing is the one group without a classification state.
- `analysis/payee_matcher.py` normalizes and indexes every alias once. It exposes `AliasIndex`, `match_known_payee` and `registry_match` (C3). The classifier's `_registry_match` delegates to it, which is where the ≥10× speedup comes from.
- **The research is consolidated outside the code (C10).** The orchestrator's research workflow turns it into one entity per company (consolidation, an adversarial check per entity, a completeness critic) and commits `docs/lender-registry-ledger.json`. No S1 code reads research output or infers a name, a group or an alias.
- `tools/lender_ledger.py` is the ledger's schema and validator. It applies every C10 rule, plus the spec rules C10 leaves to the code (Decision 3).
- `tools/build_lender_registry.py` has three modes:
  - `--check` validates the ledger;
  - `--write` validates it, then renders the GENERATED block of `analysis/classification_registry.py` (the C2 tables) and `docs/lender-registry-evidence.md`;
  - `--privacy-review` prints the lines a person reads before a commit.
- A drift test holds the committed registry block and evidence ledger equal to the rendering of the committed ledger.
- `analysis/classification_registry.py` also gains the validator's seven hand-kept inputs, outside the GENERATED block: `OWNER_NAMED_PAYEES`, `BARE_PLATFORM_NAMES` and `BARE_BRAND_NAMES`, and, on the owner's ruling of 2026-09-25, `PREMIUM_FINANCE_INSURER_ALIASES`, `MERGED_REGISTRY_ENTITIES`, `REATTRIBUTED_REGISTRY_ALIASES` and `PAYOUT_CREDIT_ENTITIES`.
- The pre-S2 classifier keeps reading today's three lists under deprecated names, so S1 changes no classification.
- `tools/lender_alias_audit.py` replays the local artifact cache through the rendered registries in the classifier's rule order. S1's acceptance is a reviewed audit with zero undecided matches that need review and zero denied collisions. After a revised ledger it also needs zero rows that an entity lost without a decision (`--before`).

**Tech Stack:** Python 3.14 (`C:\Python314\python.exe`), pytest 9, the standard library only (`ast`, `hashlib`, `json`, `re`, `sqlite3`, `subprocess`, `dataclasses`), and git (the validator reads today's registry with `git show`). No new dependency.

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

S1-specific constraints:

- **S1 changes no classification.** Until S2, the classifier keeps reading today's three lists, byte for byte:
  - `LEGACY_CONFIRMED_LENDER_ALIASES`
  - `LEGACY_POTENTIAL_LENDER_ALIASES`
  - `LEASE_PROVIDER_ALIASES`

  Every existing test stays green unchanged. No pin flips in S1 (see "Existing pins" below).
- **Where names live.**
  - Code reads counterparty names and aliases only from `analysis/classification_registry.py`, the module the guard exempts.
  - The one other committed copy is the C10 ledger `docs/lender-registry-ledger.json`. It is data the orchestrator owns, and the GENERATED block is rendered from it. The drift test keeps the two identical.
  - Nothing under `tools/` holds a real payee name. Tests use fabricated names, plus fabricated descriptors around the public company names that spec §2 and S2's Task 0 name.
- **The code infers nothing, and S1 never edits the ledger (C10).** Every ledger change belongs to the orchestrator, including the drop of an alias that the reviewed audit denies. S1 sends each denial to the orchestrator, naming the entity, the alias and the kind of collision (Task 10 Step 4). The orchestrator answers with a ruling or with a revised ledger that the owner has read.
- **These files stay outside the repository:**
  - the alias review file;
  - the audit report, and the report of the previous ledger;
  - the local copy of S2's precondition script.

  The audit refuses a path inside the repository, because payee keys come from customer statements.
- **The numbered Ontario company's number is never written anywhere:** not in code, tests, the ledger, a commit message or a report to the owner.
  - The validator refuses a run of five or more digits outside a URL, unless today's registry already holds that exact alias, and its messages never quote such a run.
  - A URL could still carry the number. The company is not searched anywhere, by rule (spec §5), so Task 9's content test requires its entity to have no evidence and no `where_looked`.
- **Commits.** Each commit step gives the exact `git add` paths and the subject, which names no statement value. The attribution lines follow as a second `-m`, as in the S2 plan:
  - The `Co-Authored-By` line is fixed for an Opus 5.5 (1M context) cell.
  - The `Claude-Session` URL belongs to the session that commits. Take it from that session's system reminder, and put it where the step shows `<the Claude-Session URL from your system reminder>`.
- Commands are PowerShell, run from the repository root of the S1 branch.
- Every S1 file is ASCII-only. Non-ASCII characters in code are built with `chr()`.

---

## Decisions this plan makes (contract ambiguities, resolved)

1. **The legacy lists.** `LEASE_PROVIDER_ALIASES` is kept as a deprecated verbatim list, because the pre-S2 classifier still reads it. C2 says it is removed; S2 removes it.
   - S1 also renames today's confirmed and potential lists to `LEGACY_CONFIRMED_LENDER_ALIASES` and `LEGACY_POTENTIAL_LENDER_ALIASES`, which the classifier reads. `CONFIRMED_LENDER_ALIASES = LENDER_ALIASES` and the new `POTENTIAL_LENDER_ALIASES` hold the rendered content that C2 requires.
   - S2 deletes all three legacy tables in its Task 6, after its Task 5 has removed their last readers.
2. **C10 replaces the builder of the earlier draft.**
   - The draft's Tasks 5-12 derived entities, groups and aliases from the raw research files. Its verification found four major defects:
     - the builder dropped confirmed companies;
     - it lost the evidence of answers it could not group;
     - it held premium financiers back;
     - its collision audit never suspected a different business that shared the alias word.
   - Per C10, consolidation is now the orchestrator's research workflow. S1's code only validates and renders:
     - `tools/lender_ledger.py` holds the schema (`parse_ledger`), the validator (`validate`), the table rendering (`render_tables`), today's registry (`load_baseline`, `baseline_moves`), the premium/insurer overlaps and the privacy review;
     - `tools/build_lender_registry.py` holds `render_block`, `replace_block`, `current_block`, `render_evidence` and the command line.
3. **What the validator refuses.** Every rule C10 lists, with these readings and additions:
   - **Scope by status.** The character rules, the digit and URL rules, the entity-name rules and "one alias, one entity" apply to every entity, because the committed ledger carries them all. The generic-word, platform, hand-kept-alias, brand, card-wording and short-alias rules apply only to the entities rendered into a table (`admitted`, `review`). A `rejected` or `owner_ruling` entity may therefore keep a generic or colliding spelling as evidence, such as today's `ACH CAPITAL`.
   - **Generic words.** "A bare generic word" is read as "an alias made only of generic words" (`GENERIC_WORDS`). So `FUNDING LLC` and `EQUIPMENT FINANCE` are refused as well.
   - **Short aliases.** Four characters or fewer, spaces not counted. The entity's one `short_alias_reason` covers all its short aliases.
   - **Platform names.** `BARE_PLATFORM_NAMES` holds C10's six names, plus `AMZN`.
   - **Hand-kept tables.** A rendered alias equal to an alias of the hand-kept `OPERATING_REVENUE_SOURCE_ALIASES` or `INSURANCE_PROVIDER_ALIASES` is refused. So is an entity, of any status, named like a hand-kept entity, and so is an entity name used twice. This keeps `First Insurance Funding` and the hand-kept insurer `First Insurance` apart without a duplicate entity (Decision 8).
     - The one exception is the owner's ruling of 2026-09-25 (amended): a `premium_financing` alias may equal an `INSURANCE_PROVIDER_ALIASES` alias when the hand-kept `PREMIUM_FINANCE_INSURER_ALIASES` holds that spelling (`FIRST INSURANCE`). The rule exempts exactly those spellings, only on a `premium_financing` entity, and only against the insurer table: the same spelling in any other group, or equal to an operating-revenue alias, is still refused.
   - **Brands (spec §5).** An alias equal to a bare brand or issuer name in `BARE_BRAND_NAMES` (`TOYOTA`, `FORD`, `APPLE`, `CAPITAL ONE` and so on) is allowed only in `card_issuer_context` or `bank_name`. The classifier reads those two tables only with payment or loan wording.
   - **Context-only tables (C2, C10).** The classifier reads four tables only with context:
     - `credit_card_payment` and `card_issuer_context` with card or payment wording;
     - `bank_name` with loan wording;
     - `premium_financing` inside the insurance rule.

     C10 renders a `review` entity into `POTENTIAL_LENDER_ALIASES`, which is read with no context at all. So a `review` entity in one of these four groups would put a bare bank or issuer name, or a card payment, into the potential tier. There it would claim every debit that names it, and today's classifier treats every credit that matches it as non-revenue.
     - Spec §1 lists American Express and RBC loan payments shown as potential lenders as failures to fix.
     - The validator therefore refuses `review` in these four groups. An unconfirmed entity of one of them is `owner_ruling` or `rejected`.
   - **Card aliases (C2 and C10: `credit_card_payment` holds "aliases that are already payment-specific").** Every alias rendered into `CARD_ISSUER_ALIASES` carries the wording of S2's card-payment rule: `CARD`, `CRD`, `CRCARD`, `CARDMEMBER`, `CREDIT CARD`, `AUTOPAY`, `AUTO PAY`, `EPAY`, `EPAYMENT`, `PAYMENT`, `PMT` or `PYMT`. A bare issuer name belongs in `card_issuer_context`.
   - **Run-together forms (spec §4.6).** In the known-payee matcher, the run-together form of a spaced alias may not be another entity's alias or run-together form.
   - **Owner-named payees.** C10 names only the lenders, alternative positions and lines of credit. `OWNER_NAMED_PAYEES` carries every payee spec §2 names, in every group, and the validator checks them all:
     - a card issuer passes as a card alias or as a bare issuer name of the context table;
     - a premium financier or a bank passes in its own table and must match no known payee.
     - The owner's ruling of 2026-09-25 (amended) respelled two of them: BlueVine is `BLUEVINE CAPITAL`, because bare `BLUEVINE` also takes Bluevine Bill Pay and checking rows; SmartPay is `SMARTPAY LEASING`, because `SMARTPAY SOL` is SmartPay Solutions' premium billing. The respelling alone does not carry out the SmartPay half: today's SmartPay holds `SMARTPAY SOL`, so the validator also reads the hand-kept `REATTRIBUTED_REGISTRY_ALIASES`, which gives that alias to SmartPay Solutions (see "Today's registry" below).
   - **Payout credits (the owner's ruling of 2026-09-25, amended).** The hand-kept `PAYOUT_CREDIT_ENTITIES` names the entities whose credits are the account holder's own sales, settled by the platform: revenue, not financing proceeds. It is a D1 exception that S2 reads; their debits keep their group. The validator refuses a name that is not an admitted ledger entity of a group whose credits D1 treats as financing proceeds (`analysis.flag_groups.FINANCING_STATES`): the credits of every other group are not financing proceeds, so the exception has nothing to except there. The one group this refuses although its rows reach a financing state is `bank_name`, whose rows S2 gives `bank_loan` (D5), which is in `FINANCING_STATES`: no ledger group is `bank_loan`, none of the owner's payout-credit entities is a bank, and S2 reads a bank's own name only with loan wording, which a sales settlement does not carry. A bank whose credits settle the holder's sales goes back to the owner.
   - **Privacy.**
     - No run of five or more digits outside a URL, unless today's registry already holds that exact alias.
     - Every evidence source and `where_looked` entry is an http(s) URL without a query string, a fragment, a `|` or credentials, on a public host: not `localhost`, not a private or loopback IP address, not an undotted host. The validator parses it with `urllib.parse.urlsplit` (amended after review).
     - No validator message, `move:` line, privacy-review line or evidence-ledger move row quotes a run of five or more digits: each masks the names and values it prints, and `validate` scrubs every problem as a backstop (amended after review).
   - **Today's registry (spec §9 and S2's prerequisite 9).**
     - Every entity of today's three lists is held by a ledger entity: the one holding its first alias, else most of its aliases, else the one that keeps its name (amended after the review of the owner's ruling: an entity that keeps today's name but none of today's aliases has lost them all, and was wrongly reported as in no ledger entity).
     - The entity holding its first alias keeps today's name, because S2's pins and the census compare entity names.
     - A change of place, or a lost alias of today's registry, needs a reason: a sentence of `notes` that starts `Move:` (`MOVE_MARKER`). Any other text in `notes` does not count, so an unrelated note never excuses a move. An entry of the lease list may become a lender, a lease or rental, or vehicle financing without one (spec §4.1).
     - **Merges (the owner's ruling of 2026-09-25, amended).** The hand-kept `MERGED_REGISTRY_ENTITIES` maps an entity of today's registry to the ledger entity that absorbs it (`EBF HOLDINGS` into `EVEREST BUSINESS FUNDING`). The validator treats the merged entity as held by its target: the "keeps today's name" rule does not apply to it, it is never missing, and its lost aliases, like a change of place, need a `Move:` sentence in the target's notes. It refuses a key that is not an entity of today's lists, a target that is not a ledger entity, and a rendered ledger entity that still carries the merged name (the target has not absorbed it).
       - The merge's reason is the target's `Move:` sentence, the same one that explains the target's own moves, so the orchestrator writes that sentence about the merge.
     - **Reattributions (the owner's ruling of 2026-09-25, amended after its review).** The hand-kept `REATTRIBUTED_REGISTRY_ALIASES` maps an alias of today's registry that names a company other than today's entity to the ledger entity of that company (`SMARTPAY SOL` to `SmartPay Solutions, LLC`). Without it no ledger could carry out the SmartPay ruling: holding that first alias, SmartPay Solutions would have to keep today's name `SmartPay`, and it would take today's SmartPay to its own place. The validator leaves the alias out of today's entity: it does not decide which ledger entity holds the entity, it is not the entity's first alias for the name rule, and it is not counted as lost. It refuses an alias that is not an alias of today's lists, a target that is not a ledger entity or does not hold the alias, and a rendered registry that reads the alias, without context, as any entity other than its target: the known-payee matcher, else the potential table. So today's entity cannot keep a shorter alias that still reads it (bare `SMARTPAY` would read `SMARTPAY SOL` as SmartPay).
     - `--check` and `--write` print one `move:` line per move, with its reason; a merged entity always has one, which says `merged into <target>`, and so does an entity with a reattributed alias, which says `<alias> reattributed to <target>` (why: `none needed (the owner's reattribution, REATTRIBUTED_REGISTRY_ALIASES)` when nothing else moved). The evidence ledger's moves section shows the merge and the reattribution in its "Now" column. The orchestrator reads each one before the owner reads the rendered list, and S1 reports them in the hand-off.
   - **Schema.** `schema` is 1, and every entity has exactly C10's ten fields, with their types.
4. **The hand-kept inputs live in the registry module**, outside the GENERATED block:
   - `OWNER_NAMED_PAYEES` (spec §2): one public spelling per payee;
   - `BARE_PLATFORM_NAMES` and `BARE_BRAND_NAMES` (spec §5);
   - on the owner's ruling of 2026-09-25 (amended): `PREMIUM_FINANCE_INSURER_ALIASES` (Decision 8), `MERGED_REGISTRY_ENTITIES`, `REATTRIBUTED_REGISTRY_ALIASES` and `PAYOUT_CREDIT_ENTITIES` (Decision 3).

   Counterparty names live only in that module, and these change only on an owner ruling. "Prerequisite: the curated ledger" lists the spellings, so the orchestrator can run the validator before S1 does.
5. **Rendering.**
   - An `admitted` entity renders into its group's table, and a `review` entity into `POTENTIAL_LENDER_ALIASES`, whatever its group. `owner_ruling` and `rejected` entities render into no table.
   - Within a table, entities are in case-folded name order, and aliases keep the ledger's order with exact repeats dropped. The order is the matcher's tie-break, so it is part of the rendering.
   - The evidence ledger lists every entity with its group, its verdicts and its first public source (else `none recorded`), and, for anything not admitted, where the researchers looked (spec section 5). A rendered entity also shows its status and aliases, so a `review` entity shows the group it was researched for. (Amended after review: the earlier rows left out the group of a rendered entity and the source of an entity awaiting a ruling or rejected.) After the tables it adds:
     - the moves from today's registry;
     - the entities awaiting an owner ruling;
     - the premium/insurer overlaps;
     - the rejected entities.
   - The ledger's digest is the sha256 of its canonical JSON, not of its bytes, because `core.autocrlf=true` in this checkout changes the line endings.
6. **The drift test runs from Task 7 on.** Until the orchestrator's ledger reaches the branch:
   - the committed block must equal the rendering of the empty ledger, which is exactly what Task 2 writes;
   - the evidence ledger must not exist.
7. **Today's registry is read from git** at `BASELINE_REVISION = 693fd009c5c96a838ef47b61ba5b65a610ea5ba1`, the last commit that changed it. The check survives S2's deletion of the legacy lists, and no second copy is committed.
8. **Premium financing and the hand-kept insurers.** The hand-kept `INSURANCE_PROVIDER_ALIASES` holds `First Insurance` (`FIRST INSURANCE`). S1 keeps that entry unchanged, because S1 changes no classification and the ledger has no insurer group.
   - The owner ruled on 2026-09-25 (amended) that the bare `FIRST INSURANCE` originator is the premium financier FIRST Insurance Funding: its rows stay insurance and are also flagged premium financing. `PREMIUM_FINANCE_INSURER_ALIASES` holds that spelling, so a `premium_financing` entity may carry it (Decision 3).
   - The validator still refuses every other premium alias equal to an insurer alias, and a premium entity named like an insurer (Decision 3). So the ledger's `First Insurance Funding` stays an entity of its own beside the hand-kept insurer.
   - S2's insurance rule looks up `PREMIUM_FINANCE_ALIASES` first (S2 Task 7). A row that prints a premium alias therefore goes to the financier, and so does a row that prints only `FIRST INSURANCE` once the ledger gives it to FIRST Insurance Funding. A row that prints only another insurer's alias stays plain insurance, unflagged.
   - The evidence ledger lists, under "Awaiting an owner ruling", every premium alias that contains an insurer's alias, except an insurer alias that a premium entity holds itself (`premium_insurer_overlaps`): the rows that print that alias are premium financing already, so no premium entity's overlap with it waits for a ruling. Its Admission section states the ruling. The owner decides the overlaps that remain. Task 9's content test pins this.
9. **The audit's review rule.** A taken match needs review when its payee key may name someone else:
   - the alias is one word and the key is not exactly that word;
   - the key holds a word outside the alias, the entity's name (and their run-together forms), `VOCAB` and `ORG_CUES`;
   - or the key shares no word with the alias.

   `--strict` fails until every such pair has a decision. The earlier draft's seed file is gone with its builder: C10 puts the collisions the research found into the ledger, as dropped aliases with their reason in `notes`. The review rule catches a business with the same name word, such as `QUILLON BAKERY` for the alias `QUILLON`.
10. **Denials go to the orchestrator; S1 never edits the ledger.** C10 makes the orchestrator the ledger's only producer. An alias that S1 dropped itself would have three problems:
    - it would bypass the owner's read of the rendered list;
    - it would leave one agent deciding every collision;
    - it would vanish the next time the orchestrator's workflow regenerates the ledger.

    So S1 records a reviewed deny only in its local review file. It sends the orchestrator the entity, the alias and the kind of collision, never the payee key, and marks when the alias is:
    - an alias of an owner-named payee;
    - the entity's last alias.

    For these two, a drop is not the fix. (Bare `BLUEVINE` was a third mark until the owner's ruling of 2026-09-25 dropped the alias; Task 10 Step 3.) The orchestrator answers each denial in one of two ways:
    - **A ruling that allows the pair.** S1 records it as an allow whose `why` starts `orchestrator ruling <date>:`.
    - **A revised ledger that the owner has read**, for example with a narrower alias, or with the other business admitted under a longer alias that wins. S1 brings the revised ledger and reruns Task 9 through its rerun path (Step 1 on), then Task 10 from Step 2.

    The rerun compares the audit with the report of the previous ledger (`--before`, Decision 15). It fails on every (entity, payee key) whose taken rows dropped without a deny decision. So a drop that also took the entity's own rows is caught before S2.
11. **Normalization moves** to `analysis/description_text.py`, and `analysis/transaction_classifier.py` re-exports it. This breaks the import cycle: the classifier imports the matcher, and the matcher needs normalization at import time.
    - The two new classifier imports go **after** the `from .revenue import ...` line.
    - S2's Task 5 Step 3 replaces only the `from .classification_registry import (...)` block, and S2's Task 4 widens S1's `from .payee_matcher import registry_match` line. Both S1 imports survive.
12. **`AliasIndex.__init__`** adds a keyword-only `run_together: bool = True` to the C3 signature. `registry_match` uses `run_together=False`, which keeps today's `_registry_match` semantics exactly.
13. **The speed benchmark** swaps the classifier's `registry_match` / `match_known_payee` (whichever the module holds) for the pre-S1 algorithm. It therefore keeps measuring "today vs now" after S2 rewires the rule order. The timing test stays in the suite (about 3 s). It measured 36× against the required 10×, and its compiled path is best of three, so a loaded host is unlikely to fail it.
14. **`analysis/lenders.py` is not edited.**
    - It keeps reading `CONFIRMED_LENDER_ALIASES`, which is now `LENDER_ALIASES`. Its `LENDER_KEYWORDS` becomes `{}` after Task 2, and follows the rendered lender table after Task 9. `git grep LENDER_KEYWORDS` finds no reader, so nothing moves.
    - S2 leaves the module unedited too (its File Structure note) and guards its helpers in its Task 5.
    - Pointing it at a legacy list instead would break it once S2's Task 6 deletes the legacy lists.
15. **Rows lost to a ledger change.** A deny decides one pair (alias A, payee key K). The ledger carries it out by dropping or narrowing A, which affects every key A matched. If A was also the only alias that matched some of the entity's own rows, those real lender rows are lost. That is the missed-lender failure of spec §1.
    - `lost_matches(before, after, decisions)` compares two audit reports of the same cache. It totals the taken rows per (entity, payee key) in each report, leaving out the rows of denied pairs from the earlier one. It returns every pair whose total fell, with both totals.
    - `--before <earlier report>` prints `lost matches: <n>` and one `LOST` line per pair, writes them to the report, and fails the audit when any exists.
    - A loss the orchestrator intends is recorded as a deny on the entity and the key, `{"entity": E, "key": K, "why": "orchestrator ruling <date>: ..."}`. From then on the audit also fails if the entity takes that key again.
    - Payee keys appear only on the terminal and in the local report, as they already do for `COLLISION` lines.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `analysis/flag_groups.py` | Create | C1: the eleven flag groups, lookups, Settings keys, `FINANCING_STATES`. |
| `analysis/description_text.py` | Create | `normalize_transaction_description`, moved verbatim out of the classifier. |
| `analysis/payee_matcher.py` | Create | C3: `PayeeMatch`, `AliasIndex`, `match_known_payee`, `registry_match`. |
| `analysis/classification_registry.py` | Modify | C2: the fourteen GENERATED tables (rendered from the ledger in Task 9), `CONFIRMED_LENDER_ALIASES = LENDER_ALIASES`, `PAYEE_GROUP_REGISTRIES` (ten states). Also the hand-kept `OWNER_NAMED_PAYEES`, `BARE_PLATFORM_NAMES`, `BARE_BRAND_NAMES`, `PREMIUM_FINANCE_INSURER_ALIASES`, `MERGED_REGISTRY_ENTITIES`, `REATTRIBUTED_REGISTRY_ALIASES` and `PAYOUT_CREDIT_ENTITIES`, and today's lists renamed `LEGACY_*` (deprecated). |
| `analysis/transaction_classifier.py` | Modify | Reads the `LEGACY_*` lists; re-exports normalization; `_registry_match` delegates to `registry_match`. |
| `analysis/lenders.py` | Not edited | Its unused `LENDER_KEYWORDS` follows `CONFIRMED_LENDER_ALIASES` (Decision 14). |
| `tools/bench_classifier.py` | Create | The legacy matcher (reference), the fabricated 300-row statement, `measure()`. |
| `tools/lender_ledger.py` | Create | C10: the ledger's schema, validator and table rendering; today's registry from git; the premium/insurer overlaps; the privacy review; `current_rules()`. |
| `tools/build_lender_registry.py` | Create | C10's command line (`--check`, `--write`, `--privacy-review`); renders the GENERATED block and the evidence ledger. |
| `docs/lender-registry-ledger.json` | Consumed | The C10 ledger. The orchestrator commits it and every revision of it; S1 never edits it. Task 9 brings it onto the branch when it is only on `lender-detection`, and brings a revised ledger when Task 10 Step 4 leads to one. |
| `docs/lender-registry-evidence.md` | Create (rendered) | The evidence ledger (spec §5). |
| `tools/lender_alias_audit.py` | Create | The local, read-only alias-collision audit, which replays the rule order over the artifact cache and, with `--before`, finds the rows a ledger change took from an entity. |
| `tests/test_flag_groups.py` | Create | C1. |
| `tests/test_classification_registry_groups.py` | Create | C2 structure and the legacy readers. |
| `tests/test_payee_matcher.py` | Create | C3 semantics and parity with the legacy matcher. |
| `tests/test_classifier_speed.py` | Create | Delegation, no-change parity, ≥10× speed. |
| `tests/lender_ledger_fixture.py` | Create | A fabricated ledger, baseline and hand-kept inputs. |
| `tests/test_lender_ledger.py` | Create | The schema and every validator rule, the baseline and the privacy review. |
| `tests/test_build_lender_registry.py` | Create | The rendering and the command line. |
| `tests/test_lender_registry_drift.py` | Create | The committed registry and evidence ledger equal the rendering of the committed ledger. |
| `tests/test_lender_registry_content.py` | Create | Spec §2 and §5, and S2's Task-0 facts, on the committed registry. |
| `tests/test_lender_alias_audit.py` | Create | The audit over a fabricated artifact cache. |

## Existing pins

**No pin flips in S1.** The classifier's inputs stay byte-identical (`LEGACY_*`, `LEASE_PROVIDER_ALIASES`), and `_registry_match` returns identical results (the parity tests of Tasks 3 and 4).

For S2's coordination only (S2 owns these edits):
- S2's plan holds the pin ledger of every pin that its routing moves.
- S2's Task 0 checks the ledger facts those pins rely on ("Prerequisites from S1", facts 1-10).
- The ledger's content selects one pre-measured variant: navigant's bank-name rows (S2 pin-ledger row 15). Since the owner's rulings of 2026-09-25, relay's card-paid personal-loan payees (row 17) are an exact pin, not a variant.
- S1's Task 10 Step 6 runs S2's Task 0 on this branch, and reports every FAIL and info line.

**Trial of this revision (2026-09-25, after the second verification).** A script replayed every code block of Tasks 1-9 of this file, in order, on a fresh clone of `lender-detection@4f219cd`:
- every red and green step gave the counts written in it;
- each new rule's test failed when its rule was taken out;
- the three selections kept the baseline counts;
- the benchmark measured about 36×.

Task 9's tests, the drift tests, the privacy review, the audit and S2's Task 0 were run against a **stand-in** ledger. The stand-in was built from today's registry and the earlier draft's rulings, and was never committed; it is not the orchestrator's ledger.
- It was brought up to this revision's rules: `Move:` sentences, the two bare issuer names moved to `card_issuer_context`, and the numbered company unsearched.
- On it, all 224 S1 tests passed. S2's Task 0 printed `0 failure(s)`, card counts `3` and `0`, navigant `0` and no relay variant.
- The audit ran on the real cache: 422 taken matches, 334 needing review. Run twice at `--limit 300`, with the first report as `--before`, it printed `lost matches: 0`.

The real ledger's counts will differ.

**After the trial (the cross-plan consistency check, 2026-09-25).** Two edits were made without a replay of the whole file:
- Task 9's content test lost one parametrized case: `VSA PUR INTUIT QBOOKS ONLINE` comes from the H-2 real-statement evidence, and S2's Task 0 no longer uses it. `CARD PURCHASE INTUIT QUICKBOOKS 0001` covers the same case. The counts move by one: Task 9 Step 8 gives 97 (58 content tests), and Step 9 gives 223.
- Task 8's audit now reads S2's exact step-8 wording and order in its bank-name and card-context passes (`_LOAN_WORDING`, `_CARD_WORDING`). The wording was replayed on a scratch script against S2's step-8 rules as S2's plan writes them: on 223,652 fabricated descriptors built from the rules' own words, around a listed bank and a listed issuer, the two passes took exactly the rows S2 gives to the bank-name and card-payment rules. The extended test `test_only_the_descriptor_rule_passes_need_loan_or_card_wording` pins it, and the audit keeps its 22 tests. The trial's audit counts were taken with the earlier wording.

**After the review of Tasks 5-8 (fix round 1, 2026-09-25).** The independent review found two Important and three Minor defects in the plan's own code, and the orchestrator ruled that the binding constraints and spec section 5 govern over the code blocks. The code blocks of Tasks 5-8 are amended to the reviewed code (each task says so). The counts above predate the fix; the amended steps give Task 5 107 tests, Task 6 11, Task 7 Step 8 130, Task 8 23 and 197 for every S1 test so far, and Task 9 Step 9 255.

**After the owner's ruling of 2026-09-25 (amendments A1-A4, delegated).** The owner ruled four changes to the hand-kept inputs, and the code blocks of Tasks 5-7 are amended to the committed code (each task says so):
- A1: two `OWNER_NAMED_PAYEES` spellings, BlueVine `BLUEVINE CAPITAL` and SmartPay `SMARTPAY LEASING` (Decision 3);
- A2: `PREMIUM_FINANCE_INSURER_ALIASES`, the premium-finance spellings that may equal an insurer alias (Decisions 3 and 8);
- A3: `MERGED_REGISTRY_ENTITIES`, the entities of today's registry that a ledger entity absorbs (Decision 3);
- A4: `PAYOUT_CREDIT_ENTITIES`, the D1 exception S2 reads (Decision 3).

The amended steps give Task 5 128 tests, Task 6 14, Task 7 Step 8 160, Task 8 23 (unchanged) and 227 for every S1 test so far; the three selections keep their baseline counts. Tasks 9-10 are amended separately.

**After the review of amendments A1-A4 (2026-09-25).** The review found that A1's respelling does not carry out the SmartPay half of the ruling: no ledger that the validator accepted could give today's `SMARTPAY SOL` to SmartPay Solutions and keep SmartPay a lease. The fix, test-first, and the code blocks of Tasks 5-7 amended to it (each task says so):
- `REATTRIBUTED_REGISTRY_ALIASES`, a seventh hand-kept constant: an alias of today's registry that names another company, and the ledger entity of that company (Decision 3, "Reattributions");
- an entity of today's registry that keeps its name but none of today's aliases is held by that name, not reported as in no ledger entity (Decision 3, "Today's registry");
- the `move:` line and the evidence ledger's moves section show each reattributed alias beside today's entity.

The amended steps give Task 5 140 tests, Task 6 15, Task 7 Step 8 176, Task 8 23 (unchanged) and 243 for every S1 test so far; the three selections keep their baseline counts.

## Prerequisite: the curated ledger (Task 9 starts only when both hold)

1. The orchestrator's consolidation workflow has produced `docs/lender-registry-ledger.json` (C10). It is committed on `lender-detection` or on this branch.
2. The owner has read the rendered lender list, and the orchestrator says so in the message that starts Task 9. For a revised ledger (Task 10 Step 4), the owner has read the changed entities.

If either is missing, S1 stops after Task 8 and reports `Task 9 blocked: ledger absent` or `Task 9 blocked: owner read not confirmed` to the orchestrator. Tasks 1-8 need neither.

**The owner's preview.** The orchestrator renders the list for the owner on a checkout that has Task 7 (this branch after Task 8, for example), without touching that checkout's files:

```powershell
$preview = "C:\Users\GustavoPrietodePaula\lender-research\ledger-preview"
New-Item -ItemType Directory -Force $preview | Out-Null
Copy-Item analysis/classification_registry.py "$preview\classification_registry.py"
C:\Python314\python.exe -m tools.build_lender_registry --write --ledger "<path of the ledger to preview>" --registry "$preview\classification_registry.py" --evidence "$preview\lender-registry-evidence.md"; $LASTEXITCODE
```

Expected output:
- `ledger ok: <n> entities, sha256:<64 hex>`;
- one `move:` line per entity of today's registry that changes place or loses an alias;
- one line per table, from `LENDER_ALIASES: ...` to `POTENTIAL_LENDER_ALIASES: ...`;
- `0`.

The owner reads `$preview\lender-registry-evidence.md`. Its first table section is the lender list, and the moves and the entities awaiting a ruling follow. A ledger with problems prints `problem:` lines, exits `1` and writes nothing.

**The ledger of the owner's delegated rulings of 2026-09-25.** The owner read the counted lender list on 2026-09-25 and delegated every open question to the orchestrator; the orchestrator's decisions are owner rulings, and the ledger carries them. Rendered with this branch's tools at `b69d12e` in a scratch clone, it printed:
- `ledger ok: 1085 entities, sha256:cdcd7ecabd83621d88e0359b36b5cb1b0033076ebd39cf386142f32cf70dabdf`;
- 58 `move:` lines, among them `EBF HOLDINGS` `merged into EVEREST BUSINESS FUNDING`, SmartPay's `SMARTPAY SOL reattributed to SmartPay Solutions, LLC`, and `CAPITAL INFUSION` `confirmed_lender -> alternative_position`;
- `LENDER_ALIASES: 286 entities, 505 aliases`, `ALTERNATIVE_POSITION_ALIASES: 54 entities, 94 aliases`, `LINE_OF_CREDIT_ALIASES: 14 entities, 21 aliases`, `CARD_ISSUER_ALIASES: 41 entities, 115 aliases`, `CARD_ISSUER_CONTEXT_ALIASES: 58 entities, 105 aliases`, `VEHICLE_FINANCE_ALIASES: 48 entities, 115 aliases`, `MORTGAGE_SERVICER_ALIASES: 35 entities, 48 aliases`, `LEASE_RENTAL_ALIASES: 32 entities, 65 aliases`, `PERSONAL_LOAN_ALIASES: 78 entities, 126 aliases`, `FLOOR_PLAN_ALIASES: 8 entities, 18 aliases`, `FACTORING_ALIASES: 13 entities, 21 aliases`, `PREMIUM_FINANCE_ALIASES: 21 entities, 47 aliases`, `BANK_NAME_ALIASES: 34 entities, 51 aliases`, `POTENTIAL_LENDER_ALIASES: 110 entities, 128 aliases`;
- `0`.

A later revision of the ledger prints other counts; the items below still hold for it.

The ledger passes Task 9 only when every item below holds. The orchestrator can check the first three before S1 runs, with `python -m tools.build_lender_registry --check` on a checkout that has Task 7.

- **`--check` exits 0**: every rule of Decision 3. The rules most likely to catch a ledger written before this revision:
  - every move from today's registry has a sentence of `notes` that starts `Move:`;
  - no `review` entity is in `credit_card_payment`, `card_issuer_context`, `bank_name` or `premium_financing`;
  - every `credit_card_payment` alias carries card or payment wording, and bare issuer names are in `card_issuer_context`.
- **The `move:` lines.** The orchestrator reads every `move:` line that `--check` prints, and checks that each reason is about that move.
- **`OWNER_NAMED_PAYEES` resolves.** Each spelling must resolve to its group in the rendered tables:

  | Group | Payee: the spelling the validator matches |
  |---|---|
  | `confirmed_lender` | OnDeck: `ONDECK`; Bitty: `BITTY ADVANCE`; Legend: `LEGEND ADVANCE FUNDING`; LG Funding: `LG FUNDING`; Hunter Caroline: `HUNTER CAROLINE`; CAN Capital: `CAN CAPITAL`; CanaCap: `CANACAP`; NMEF: `NMEF FUNDING`; Balboa: `BALBOA CAPITAL`; Navitas: `NAVITAS CREDIT CORP`; Deere: `JOHN DEERE FINANCIAL` |
  | `alternative_position` | SBA/EIDL: `SBA EIDL`; BDC: `BDC`; Affirm: `AFFIRM`; Amex loans: `AMERICAN EXPRESS BUSINESS LOAN`; Intuit: `INTUIT FINANCING`; Square: `SQUARE CAPITAL`; Shopify: `SHOPIFY CAPITAL`; PayPal: `PAYPAL WORKING CAPITAL`; Stripe: `STRIPE CAPITAL`; Amazon financing: `AMAZON CAPITAL SERVICES` |
  | `line_of_credit` | Fundbox: `FUNDBOX`; BlueVine: `BLUEVINE CAPITAL`; Kabbage: `KABBAGE` |
  | `credit_card_payment` (a card alias, or a bare issuer name in `card_issuer_context`) | American Express: `AMEX EPAYMENT ACH PMT`; Capital One: `CAPITAL ONE ONLINE PMT`; Chase: `CHASE CREDIT CRD EPAY`; Credit One: `CREDIT ONE BANK PAYMENT`; Concora: `CONCORA CREDIT PAYMENT` |
  | `vehicle_financing` | GM Financial: `GM FINANCIAL`; Ford Credit: `FORD CREDIT`; Toyota Financial: `TOYOTA FINANCIAL`; Ally: `ALLY FINANCIAL` |
  | `bank_name` (and no known payee) | Truist: `TRUIST LN PYMT` |
  | `lease_or_rental` | Progressive: `PROGRESSIVE LEASING`; SmartPay: `SMARTPAY LEASING`; Snap: `SNAP FINANCE` |
  | `floor_plan_financing` | NextGear Capital: `NEXTGEAR CAPITAL`; Westlake Flooring: `WESTLAKE FLOORING` |
  | `factoring` | RTS Financial: `RTS FINANCIAL`; OTR Capital: `OTR CAPITAL`; Apex Capital: `APEX CAPITAL`; BC Factoring: `BC FACTORING` |
  | `premium_financing` (and no known payee) | IPFS: `IPFS`; First Insurance Funding: `FIRST INSURANCE FUNDING` |

  The owner's ruling of 2026-09-25 respelled two of them (Decision 3). BlueVine is `BLUEVINE CAPITAL`: bare `BLUEVINE` also takes Bluevine Bill Pay payments and receipts between other businesses and Bluevine checking transfers. SmartPay is `SMARTPAY LEASING`, the lease-to-own SmartPay Leasing: `SMARTPAY SOL` is SmartPay Solutions' insurance premium billing (`REATTRIBUTED_REGISTRY_ALIASES`).

- **S2's Task-0 facts** (S2 "Prerequisites from S1", facts 1-6 and 9), as the owner's rulings of 2026-09-25 amend them. The five payees that S2 once listed as expected conflicts (AFC FUNDING CORP, Econolease, Clover Equipment, CMCA Finance, Lily Advance) are ordinary facts now, with the ledger's filing. Task 9's content test restates them:
  - each payee that S2 pins by name keeps today's `entity` spelling (`NMEF`, `Navitas Credit Corp`, `Balboa Capital`, `De Lage Landen`, `FORA FINANCIAL`, `ONDECK`, `CanaCap`, `CAN Capital`, `Forward Funding`, `Forward Financing`, `RAPID FINANCE`, `KAPITUS`, `FUNDWORKS`, `EVEREST BUSINESS FUNDING`, `AFC FUNDING CORP`, `BDC`, `AFFIRM`, `INTUIT FINANCING`, `SQUARE CAPITAL`, `SHOPIFY CAPITAL`, `PAYPAL WORKING CAPITAL`, `CAPITAL INFUSION`, `BLUEVINE`, `FUNDBOX`, `KABBAGE`, `SNAP Finance`, `Progressive Leasing`, `SmartPay`, `NETCREDIT`, `Econolease`, `Clover Equipment`, `CMCA Finance`, `Lily Advance`), in the group S2's Task 0 expects. `AFC FUNDING CORP` is `floor_plan_financing` (a dealer floor-plan lender's receivables-funding subsidiary), and `CAPITAL INFUSION` (the house) is an `alternative_position`: flagged, never counted;
  - De Lage Landen matches `DELAGELANDEN`;
  - the `line_of_credit` entity `BLUEVINE` holds `BLUEVINE CAPITAL` and `BLUEVINE LOAN` and no bare `BLUEVINE`, so no rendered table claims a Bluevine Bill Pay row or a Bluevine transfer;
  - the `lease_or_rental` entity `SmartPay` holds only `SMARTPAY LEASING`; `SMARTPAY SOL` is held by the rejected SmartPay Solutions, LLC, and no rendered table claims it;
  - no rendered entity carries `ACH CAPITAL`;
  - NETCREDIT is in a financing group;
  - Econolease (equipment finance), CMCA Finance and Lily Advance are counted lenders (`confirmed_lender` known payees), and none of them is a potential alias;
  - Clover Equipment stays in review: it is no known payee, and it renders into `POTENTIAL_LENDER_ALIASES`;
  - `EBF HOLDINGS` is merged into `EVEREST BUSINESS FUNDING` (`MERGED_REGISTRY_ENTITIES`): no ledger entity is named `EBF HOLDINGS`, and `EVEREST BUSINESS FUNDING` holds `EBF HOLDINGS`, `EBF DEBIT` and `HOLDINGS EBF`, so the funder counts once;
  - every `PAYOUT_CREDIT_ENTITIES` name (`Sezzle Inc`, `American First Finance, LLC`, `PAYABILITY`) is an admitted entity of a financing group, and its rows match in that group (S2 makes their credits revenue; their debits keep the group);
  - no bare platform name is a known payee.
- **The other delegated rulings of 2026-09-25**, which the content test pins by ledger place: MERCH PAD (probably Merchant Growth) and Rewards Network in review, never counted; MR BIZ CAPITAL rejected (a broker); Keep Technologies rejected, so `KEEP BUS` is unflagged; LADCO Leasing, a card-terminal lessor, in Leases & rentals, not a lender.
- **The spec's examples.**
  - `FORWARDFINANCING` and `EXPANSIONCAP` match their lenders (spec §1).
  - `ONDECK` claims neither the Journey Capital rows nor an unrelated `ENOVA` utility, and `SmartPay` claims no Atlas Financial card rows (spec §5).
- **First Insurance** (the owner's ruling of 2026-09-25, Decision 8). A premium alias matches `FIRST INSURANCE FUNDING`. The bare `FIRST INSURANCE` is a premium alias of FIRST Insurance Funding (`PREMIUM_FINANCE_INSURER_ALIASES`), and it is the only premium alias equal to an insurer alias. The hand-kept insurer `First Insurance` keeps `FIRST INSURANCE` unchanged. The Canadian spellings stay with FIRST Insurance Funding of Canada. The evidence ledger states the ruling in its Admission section and lists no premium/insurer overlap under "Awaiting an owner ruling".
- **The numbered Ontario company.** It is an `owner_ruling` entity whose name or `notes` says "numbered Ontario company".
  - It has no `evidence` and no `where_looked`, because it is not searched anywhere, by rule (spec §5). A URL is the one place the validator's digit rule does not look.
  - Neither its number nor an alias that carries the number appears anywhere.

## Before Task 1

- [ ] Create the branch `ld-s1-registry` from `lender-detection` (with superpowers:using-git-worktrees if you work in a worktree). Then set these PowerShell variables in every session that runs Tasks 9-10:

```powershell
$local = "C:\Users\GustavoPrietodePaula\lender-research\s1-local"
$webappData = "C:\Users\GustavoPrietodePaula\OneDrive - Capital Infusion\Desktop\Capital Infusion Projects\bankStatementAnalysis\webapp_data"
New-Item -ItemType Directory -Force $local | Out-Null
```

- `$local` is a private folder outside the repository and outside OneDrive.
- `$webappData` is the local artifact cache, which the audit only reads. In a worktree it still names the main checkout's `webapp_data`.

- [ ] Check that git can show the baseline revision:

```powershell
git cat-file -e 693fd009c5c96a838ef47b61ba5b65a610ea5ba1:analysis/classification_registry.py; $LASTEXITCODE
```

Expected: `0`. `693fd009c5c96a838ef47b61ba5b65a610ea5ba1` is the last commit that changed today's registry; `git log -1 --format=%H -- analysis/classification_registry.py` prints it until Task 2 commits.

- [ ] Check whether the ledger is already on the branch:

```powershell
Test-Path docs/lender-registry-ledger.json
```

Expected: `False`, and then Task 7's drift tests pass as written. If it prints `True`, Task 7 Step 8 gives the counts for that case.

- [ ] Record the baseline of the three selections:

```powershell
C:\Python314\python.exe -m pytest tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_r1_hardcodes.py tests/test_webapp_settings.py tests/test_package_currency.py tests/test_webapp_app.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_no_statement_hardcodes.py tests/test_new_statement_corpus.py tests/test_webapp_accounts_view.py tests/test_webapp_studio_views.py tests/test_webapp_review_ui.py -q -p no:cacheprovider
C:\Python314\python.exe -m pytest tests/test_analysis.py tests/test_artifact_cache.py tests/test_benchmark_harness.py tests/test_batch.py -q -p no:cacheprovider
```

Expected: `404 passed`; `146 passed, 1 failed` (the known failure); `306 passed`.

---

### Task 1: The flag groups (C1)

**Files:**
- Create: `analysis/flag_groups.py`
- Test: `tests/test_flag_groups.py`

**Interfaces:**
- Consumes: nothing.
- Produces, exactly as contract C1:
  - `FlagGroup(state: str | None, key: str, setting: str, label: str)` (frozen dataclass);
  - `FLAG_GROUPS: tuple[FlagGroup, ...]`, eleven groups, the last one `FlagGroup(None, "premium_financing", "flag_premium_financing", "Premium financing")`;
  - `FLAG_GROUP_BY_STATE: dict[str, FlagGroup]` (the ten groups with a state);
  - `FLAG_GROUP_BY_KEY: dict[str, FlagGroup]`;
  - `FLAG_SETTING_KEYS: tuple[str, ...]`;
  - `FINANCING_STATES: frozenset[str]`, including `floor_plan_financing` and `factoring`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_flag_groups.py`:

```python
"""Contract C1: the flagged obligation groups (spec section 4.2, amended 2026-09-24)."""
from __future__ import annotations

import ast
from pathlib import Path

from analysis.flag_groups import (
    FINANCING_STATES,
    FLAG_GROUP_BY_KEY,
    FLAG_GROUP_BY_STATE,
    FLAG_GROUPS,
    FLAG_SETTING_KEYS,
    FlagGroup,
)

EXPECTED = (
    ("alternative_position", "alternative_positions", "flag_alternative_positions", "Alternative positions"),
    ("line_of_credit", "lines_of_credit", "flag_lines_of_credit", "Lines of credit"),
    ("credit_card_payment", "credit_cards", "flag_credit_cards", "Credit cards"),
    ("vehicle_financing", "vehicle_financing", "flag_vehicle_financing", "Vehicle loans & leases"),
    ("bank_loan", "bank_loans", "flag_bank_loans", "Bank loans"),
    ("mortgage", "mortgages", "flag_mortgages", "Mortgages"),
    ("lease_or_rental", "leases_rentals", "flag_leases_rentals", "Leases & rentals"),
    ("personal_loan", "personal_loans", "flag_personal_loans", "Personal loans"),
    ("floor_plan_financing", "floor_plan", "flag_floor_plan", "Floor plan"),
    ("factoring", "factoring", "flag_factoring", "Factoring"),
    (None, "premium_financing", "flag_premium_financing", "Premium financing"),
)


def test_the_eleven_groups_match_the_spec_table_in_order():
    assert tuple((g.state, g.key, g.setting, g.label) for g in FLAG_GROUPS) == EXPECTED
    assert all(isinstance(g, FlagGroup) for g in FLAG_GROUPS)


def test_premium_financing_is_the_one_group_without_a_state():
    assert [g.key for g in FLAG_GROUPS if g.state is None] == ["premium_financing"]


def test_lookups_and_setting_keys_are_derived_from_the_one_tuple():
    assert FLAG_GROUP_BY_STATE == {g.state: g for g in FLAG_GROUPS if g.state is not None}
    assert None not in FLAG_GROUP_BY_STATE
    assert len(FLAG_GROUP_BY_STATE) == 10
    assert FLAG_GROUP_BY_KEY == {g.key: g for g in FLAG_GROUPS}
    assert FLAG_SETTING_KEYS == tuple(row[2] for row in EXPECTED)


def test_financing_states_are_the_d1_groups_and_never_cards_leases_or_premium_financing():
    assert FINANCING_STATES == frozenset({
        "confirmed_lender", "alternative_position", "line_of_credit", "bank_loan",
        "vehicle_financing", "mortgage", "personal_loan", "floor_plan_financing", "factoring",
    })
    assert "credit_card_payment" not in FINANCING_STATES
    assert "lease_or_rental" not in FINANCING_STATES
    assert "insurance" not in FINANCING_STATES


def test_flag_groups_imports_nothing_from_the_analysis_package():
    source = Path(__file__).resolve().parent.parent / "analysis" / "flag_groups.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append((node.level, node.module or ""))
        elif isinstance(node, ast.Import):
            imported.extend((0, alias.name) for alias in node.names)
    assert all(level == 0 and not module.startswith("analysis") for level, module in imported), imported
```

- [ ] **Step 2: Run it to verify it fails**

Run: `C:\Python314\python.exe -m pytest tests/test_flag_groups.py -q -p no:cacheprovider`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'analysis.flag_groups'`.

- [ ] **Step 3: Write the implementation**

Create `analysis/flag_groups.py` (the dataclass and the tuple are contract C1 verbatim):

```python
"""The flagged obligation groups (spec section 4.2): one Settings checkbox each, never lender math.

This module imports nothing from the rest of ``analysis``: the classifier, the serving layer and the
dashboard test all read the groups from here.
"""
from __future__ import annotations

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

- [ ] **Step 4: Run the tests to verify they pass**

Run: `C:\Python314\python.exe -m pytest tests/test_flag_groups.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider`
Expected: `test_flag_groups.py` 5 passed. `test_no_statement_hardcodes.py` fails only on the known `test_no_literal_account_numbers_in_ocr`; its layer-wide scans now cover the new module, and they pass.

- [ ] **Step 5: Commit**

```powershell
git add analysis/flag_groups.py tests/test_flag_groups.py
git commit -m "analysis: the eleven flag group constants (contract C1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 2: Regroup the registry without changing any classification (C2 structure)

**Files:**
- Modify: `analysis/classification_registry.py:1-10` (docstring, the GENERATED block, the compatibility name, `PAYEE_GROUP_REGISTRIES`, the rename to `LEGACY_CONFIRMED_LENDER_ALIASES`), `:139` (the rename to `LEGACY_POTENTIAL_LENDER_ALIASES`), `:301-302` (comment)
- Modify: `analysis/transaction_classifier.py:10-18` (imports), `:217`, `:636`, `:649`, `:1111`, `:1152` (the two renamed lists)
- Test: `tests/test_classification_registry_groups.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (C2):
  - Fourteen tables, each `dict[str, tuple[str, ...]]`, empty until Task 9: `LENDER_ALIASES`, `ALTERNATIVE_POSITION_ALIASES`, `LINE_OF_CREDIT_ALIASES`, `CARD_ISSUER_ALIASES`, `CARD_ISSUER_CONTEXT_ALIASES`, `VEHICLE_FINANCE_ALIASES`, `MORTGAGE_SERVICER_ALIASES`, `LEASE_RENTAL_ALIASES`, `PERSONAL_LOAN_ALIASES`, `FLOOR_PLAN_ALIASES`, `FACTORING_ALIASES`, `PREMIUM_FINANCE_ALIASES`, `BANK_NAME_ALIASES`, `POTENTIAL_LENDER_ALIASES`.
  - `CONFIRMED_LENDER_ALIASES` (is `LENDER_ALIASES`).
  - `PAYEE_GROUP_REGISTRIES: dict[str, dict[str, tuple[str, ...]]]`, the ten states in the contract order: `confirmed_lender`, `alternative_position`, `line_of_credit`, `vehicle_financing`, `mortgage`, `personal_loan`, `floor_plan_financing`, `factoring`, `lease_or_rental`, `credit_card_payment`. `PREMIUM_FINANCE_ALIASES` is not in it.
  - Deprecated: `LEGACY_CONFIRMED_LENDER_ALIASES`, `LEGACY_POTENTIAL_LENDER_ALIASES`, `LEASE_PROVIDER_ALIASES`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_classification_registry_groups.py`:

```python
"""Contract C2: the regrouped registry and its compatibility names."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis import classification_registry as registry

ROOT = Path(__file__).resolve().parent.parent
GROUP_TABLES = (
    "LENDER_ALIASES",
    "ALTERNATIVE_POSITION_ALIASES",
    "LINE_OF_CREDIT_ALIASES",
    "CARD_ISSUER_ALIASES",
    "CARD_ISSUER_CONTEXT_ALIASES",
    "VEHICLE_FINANCE_ALIASES",
    "MORTGAGE_SERVICER_ALIASES",
    "LEASE_RENTAL_ALIASES",
    "PERSONAL_LOAN_ALIASES",
    "FLOOR_PLAN_ALIASES",
    "FACTORING_ALIASES",
    "PREMIUM_FINANCE_ALIASES",
    "BANK_NAME_ALIASES",
    "POTENTIAL_LENDER_ALIASES",
    "INSURANCE_PROVIDER_ALIASES",
    "OPERATING_REVENUE_SOURCE_ALIASES",
)
LEGACY_NAMES = ("LEGACY_CONFIRMED_LENDER_ALIASES", "LEGACY_POTENTIAL_LENDER_ALIASES", "LEASE_PROVIDER_ALIASES")


@pytest.mark.parametrize("name", GROUP_TABLES)
def test_every_table_maps_an_entity_to_a_tuple_of_string_aliases(name):
    table = getattr(registry, name)
    assert isinstance(table, dict)
    for entity, aliases in table.items():
        assert isinstance(entity, str) and entity
        assert isinstance(aliases, tuple) and aliases, entity
        assert all(isinstance(alias, str) and alias for alias in aliases), entity


def test_payee_group_registries_follow_the_contract_order_and_are_the_tables_themselves():
    assert list(registry.PAYEE_GROUP_REGISTRIES) == [
        "confirmed_lender",
        "alternative_position",
        "line_of_credit",
        "vehicle_financing",
        "mortgage",
        "personal_loan",
        "floor_plan_financing",
        "factoring",
        "lease_or_rental",
        "credit_card_payment",
    ]
    expected = (
        registry.LENDER_ALIASES,
        registry.ALTERNATIVE_POSITION_ALIASES,
        registry.LINE_OF_CREDIT_ALIASES,
        registry.VEHICLE_FINANCE_ALIASES,
        registry.MORTGAGE_SERVICER_ALIASES,
        registry.PERSONAL_LOAN_ALIASES,
        registry.FLOOR_PLAN_ALIASES,
        registry.FACTORING_ALIASES,
        registry.LEASE_RENTAL_ALIASES,
        registry.CARD_ISSUER_ALIASES,
    )
    assert len(registry.PAYEE_GROUP_REGISTRIES) == len(expected)
    assert all(actual is table for actual, table in zip(registry.PAYEE_GROUP_REGISTRIES.values(), expected))


def test_confirmed_lender_aliases_is_the_compatibility_name_of_the_lender_table():
    assert registry.CONFIRMED_LENDER_ALIASES is registry.LENDER_ALIASES


def test_the_context_bank_potential_and_premium_tables_stay_out_of_the_known_payee_matcher():
    matcher_tables = [id(table) for table in registry.PAYEE_GROUP_REGISTRIES.values()]
    for name in ("CARD_ISSUER_CONTEXT_ALIASES", "BANK_NAME_ALIASES", "POTENTIAL_LENDER_ALIASES",
                 "PREMIUM_FINANCE_ALIASES"):
        assert id(getattr(registry, name)) not in matcher_tables, name


def test_premium_finance_payees_share_no_entity_with_a_group_table():
    premium = registry.PREMIUM_FINANCE_ALIASES
    for table in registry.PAYEE_GROUP_REGISTRIES.values():
        assert not set(premium) & set(table)


def test_the_legacy_lists_are_read_only_by_the_pre_s2_classifier():
    readers = set()
    for path in sorted((ROOT / "analysis").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if any(re.search(rf"\b{name}\b", text) for name in LEGACY_NAMES):
            readers.add(path.name)
    assert readers <= {"classification_registry.py", "transaction_classifier.py"}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `C:\Python314\python.exe -m pytest tests/test_classification_registry_groups.py -q -p no:cacheprovider`
Expected: `17 failed, 4 passed`.
- The table tests fail with `AttributeError: module 'analysis.classification_registry' has no attribute 'LENDER_ALIASES'` (and the other new names).
- Four tests already pass before the change, and that is expected: the table tests of `POTENTIAL_LENDER_ALIASES`, `INSURANCE_PROVIDER_ALIASES` and `OPERATING_REVENUE_SOURCE_ALIASES` (those names exist today), and the legacy-reader test (no `LEGACY_*` name exists yet).

- [ ] **Step 3: Insert the GENERATED block and rename today's confirmed list**

Between its two markers, the new text below is exactly what `tools/build_lender_registry.py` renders for an empty ledger (Task 6), and Task 7's drift test checks it. Copy it byte for byte.

In `analysis/classification_registry.py`, replace this exact text (lines 1-10):

```python
"""Maintained entity registries for deterministic transaction classification.

Aliases are normalized and matched on token boundaries by
``analysis.transaction_classifier``. Keep generic financing words out of the
verified registry; they are evidence signals, not lender identities.
"""
from __future__ import annotations


CONFIRMED_LENDER_ALIASES: dict[str, tuple[str, ...]] = {
```

with:

```python
"""Maintained entity registries for deterministic transaction classification.

Aliases are normalized and matched on token boundaries by
``analysis.payee_matcher``. Keep generic financing words out of the named
registries; they are evidence signals, not lender identities.

The group tables between the GENERATED markers are rendered by
``tools/build_lender_registry.py`` from ``docs/lender-registry-ledger.json``,
the curated lender ledger (contract C10). The evidence for every entity is in
``docs/lender-registry-evidence.md``.
"""
from __future__ import annotations

# --- BEGIN GENERATED: tools/build_lender_registry.py ---
# Rendered by tools/build_lender_registry.py from docs/lender-registry-ledger.json (contract C10).
# Never edit by hand: change the ledger, then run python -m tools.build_lender_registry --write.

#: Lenders: MCA and revenue-based funders, equipment financing.
LENDER_ALIASES: dict[str, tuple[str, ...]] = {}

#: Alternative positions.
ALTERNATIVE_POSITION_ALIASES: dict[str, tuple[str, ...]] = {}

#: Lines of credit.
LINE_OF_CREDIT_ALIASES: dict[str, tuple[str, ...]] = {}

#: Credit cards: aliases that carry card-payment wording.
CARD_ISSUER_ALIASES: dict[str, tuple[str, ...]] = {}

#: Card issuers: bare names, used only with card-payment wording.
CARD_ISSUER_CONTEXT_ALIASES: dict[str, tuple[str, ...]] = {}

#: Vehicle loans & leases.
VEHICLE_FINANCE_ALIASES: dict[str, tuple[str, ...]] = {}

#: Mortgages.
MORTGAGE_SERVICER_ALIASES: dict[str, tuple[str, ...]] = {}

#: Leases & rentals.
LEASE_RENTAL_ALIASES: dict[str, tuple[str, ...]] = {}

#: Personal loans.
PERSONAL_LOAN_ALIASES: dict[str, tuple[str, ...]] = {}

#: Floor plan.
FLOOR_PLAN_ALIASES: dict[str, tuple[str, ...]] = {}

#: Factoring.
FACTORING_ALIASES: dict[str, tuple[str, ...]] = {}

#: Premium financing: premium-finance payees, read only by the insurance rule.
PREMIUM_FINANCE_ALIASES: dict[str, tuple[str, ...]] = {}

#: Bank names: bank loans (D5).
BANK_NAME_ALIASES: dict[str, tuple[str, ...]] = {}

#: Potential lenders: review, never counted.
POTENTIAL_LENDER_ALIASES: dict[str, tuple[str, ...]] = {}

# --- END GENERATED: tools/build_lender_registry.py ---

#: Compatibility name (spec section 5): the lender table under its old name.
CONFIRMED_LENDER_ALIASES = LENDER_ALIASES

#: The known-payee matcher's registries (contract C2), keyed by classification
#: state. The order is the tie-break order of ``analysis.payee_matcher``.
#: PREMIUM_FINANCE_ALIASES is not here: only the insurance rule reads it.
PAYEE_GROUP_REGISTRIES: dict[str, dict[str, tuple[str, ...]]] = {
    "confirmed_lender": LENDER_ALIASES,
    "alternative_position": ALTERNATIVE_POSITION_ALIASES,
    "line_of_credit": LINE_OF_CREDIT_ALIASES,
    "vehicle_financing": VEHICLE_FINANCE_ALIASES,
    "mortgage": MORTGAGE_SERVICER_ALIASES,
    "personal_loan": PERSONAL_LOAN_ALIASES,
    "floor_plan_financing": FLOOR_PLAN_ALIASES,
    "factoring": FACTORING_ALIASES,
    "lease_or_rental": LEASE_RENTAL_ALIASES,
    "credit_card_payment": CARD_ISSUER_ALIASES,
}


# --- Deprecated: the inputs of the classifier as it stands before S2 ---
# LEGACY_CONFIRMED_LENDER_ALIASES, LEGACY_POTENTIAL_LENDER_ALIASES and
# LEASE_PROVIDER_ALIASES are today's three lists, byte for byte, so that S1
# changes no classification. Only analysis/transaction_classifier.py reads
# them. S2 deletes all three together with those reads; tools/lender_ledger.py
# reads today's lists from git at its BASELINE_REVISION to check the ledger.
LEGACY_CONFIRMED_LENDER_ALIASES: dict[str, tuple[str, ...]] = {
```

- [ ] **Step 4: Rename today's potential list and fix the comment**

In `analysis/classification_registry.py`, replace:

```python
POTENTIAL_LENDER_ALIASES: dict[str, tuple[str, ...]] = {
    "CMCA Finance": (
```

with:

```python
LEGACY_POTENTIAL_LENDER_ALIASES: dict[str, tuple[str, ...]] = {
    "CMCA Finance": (
```

Then replace:

```python
# Reserved for transaction codes whose meaning is specific to an institution.
# Global aliases belong in ``CONFIRMED_LENDER_ALIASES``.
```

with:

```python
# Reserved for transaction codes whose meaning is specific to an institution.
# Global aliases belong in ``LENDER_ALIASES``.
```

- [ ] **Step 5: Point the classifier at the legacy lists**

In `analysis/transaction_classifier.py`, replace:

```python
from .classification_registry import (
    BANK_SPECIFIC_LENDER_ALIASES,
    CONFIRMED_LENDER_ALIASES,
    INSURANCE_PROVIDER_ALIASES,
    LEASE_PROVIDER_ALIASES,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    POTENTIAL_LENDER_ALIASES,
)
```

with:

```python
from .classification_registry import (
    BANK_SPECIFIC_LENDER_ALIASES,
    INSURANCE_PROVIDER_ALIASES,
    LEASE_PROVIDER_ALIASES,
    LEGACY_CONFIRMED_LENDER_ALIASES,
    LEGACY_POTENTIAL_LENDER_ALIASES,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
)
```

Then make two replace-all edits in the same file:
- ` CONFIRMED_LENDER_ALIASES)` → ` LEGACY_CONFIRMED_LENDER_ALIASES)`. There are 3 occurrences, at lines 217, 636 and 1111.
- ` POTENTIAL_LENDER_ALIASES)` → ` LEGACY_POTENTIAL_LENDER_ALIASES)`. There are 2 occurrences, at lines 649 and 1152.

Verify: `git grep -n "LEGACY_\|CONFIRMED_LENDER_ALIASES\|POTENTIAL_LENDER_ALIASES" -- analysis/transaction_classifier.py`
Expected: only the two import lines and the five `LEGACY_...` use sites.

- [ ] **Step 6: Run the tests to verify they pass and nothing else moved**

Run: `C:\Python314\python.exe -m pytest tests/test_classification_registry_groups.py tests/test_flag_groups.py -q -p no:cacheprovider`
Expected: 26 passed (21 + 5).

Run the three baseline selections from "Before Task 1".
Expected: the same counts: `404 passed`; `146 passed, 1 failed` (the known failure); `306 passed`.

- [ ] **Step 7: Commit**

```powershell
git add analysis/classification_registry.py analysis/transaction_classifier.py tests/test_classification_registry_groups.py
git commit -m "registry: group tables (contract C2) beside the unchanged lists the classifier still reads" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 3: The compiled known-payee matcher (C3)

**Files:**
- Create: `analysis/description_text.py`, `analysis/payee_matcher.py`, `tools/bench_classifier.py` (first version: the legacy reference only)
- Modify: `analysis/transaction_classifier.py:3-4` (drop `import unicodedata`), `:19-20` (imports), `:171-184` (delete `normalize_transaction_description`, which moves)
- Test: `tests/test_payee_matcher.py`

**Interfaces:**
- Consumes: `PAYEE_GROUP_REGISTRIES` (Task 2).
- Produces:
  - `analysis.description_text.normalize_transaction_description(description: str) -> str`, which `analysis.transaction_classifier` re-exports under the same name.
  - `PayeeMatch(entity: str, state: str, alias: str)`.
  - `AliasIndex(registries: Mapping[str, Mapping[str, Sequence[str]]], *, run_together: bool = True)` with `.match(normalized_text: str) -> PayeeMatch | None`.
  - `match_known_payee(normalized_text: str) -> PayeeMatch | None`.
  - `registry_match(normalized_text: str, registry: Mapping[str, Sequence[str]]) -> tuple[str, str] | None`.
  - `RUN_TOGETHER_MIN_LENGTH = 8`.
  - `tools.bench_classifier.legacy_registry_match(text: str, registry: dict[str, tuple[str, ...]]) -> tuple[str, str] | None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_payee_matcher.py`:

```python
"""Contract C3: the compiled known-payee matcher (spec section 4.6). Fabricated descriptors only."""
from __future__ import annotations

import pytest

from analysis import classification_registry as registry
from analysis import transaction_classifier
from analysis.description_text import normalize_transaction_description as normalize
from analysis.payee_matcher import (
    RUN_TOGETHER_MIN_LENGTH,
    AliasIndex,
    PayeeMatch,
    match_known_payee,
    registry_match,
)
from tools.bench_classifier import legacy_registry_match

FABRICATED = {
    "alternative_position": {"Quillon Card Loans": ("QUILLON CARD BUSINESS LOAN",)},
    "credit_card_payment": {"Quillon Card": ("QUILLON CARD",)},
    "confirmed_lender": {
        "Brambleway Funding": ("BRAMBLEWAY FUNDING", "BRAMBLEWAY"),
        "Tarnmoor Capital": ("TARNMOOR CAPITAL", "TARN MOOR"),
    },
}

TEXTS = (
    "ACH DEBIT BRAMBLEWAY FUNDING LLC",
    "CHECKCARD 0102 TARNMOORCAPITAL",
    "BRAMBLEWAYS BAKERY",
    "WEB PMT QUILLON CARD BUSINESS LOAN",
    "QUILLON CARD EPAYMENT",
    "xBRAMBLEWAYy",
    "BRAMBLEWAY-FUNDING",
    "",
    "PAYMENT TO TARN MOOR",
)


def test_normalization_moved_but_keeps_its_old_import_path():
    assert transaction_classifier.normalize_transaction_description is normalize


def test_longest_alias_wins_across_registries():
    index = AliasIndex(FABRICATED)
    assert index.match(normalize("WEB PMT QUILLON CARD BUSINESS LOAN")) == PayeeMatch(
        "Quillon Card Loans", "alternative_position", "QUILLON CARD BUSINESS LOAN"
    )
    assert index.match(normalize("QUILLON CARD EPAYMENT")) == PayeeMatch(
        "Quillon Card", "credit_card_payment", "QUILLON CARD"
    )


def test_ties_go_to_the_earlier_registry_then_the_earlier_alias():
    index = AliasIndex({
        "confirmed_lender": {"First": ("OXBOW FUND",)},
        "alternative_position": {"Second": ("OXBOW LEND",)},
    })
    assert index.match("OXBOW FUND OXBOW LEND").entity == "First"
    same_registry = AliasIndex({"confirmed_lender": {"A": ("OXBOW FUND",), "B": ("OXBOW LEND",)}})
    assert same_registry.match("OXBOW LEND OXBOW FUND").entity == "A"


def test_aliases_match_on_token_boundaries_only():
    index = AliasIndex(FABRICATED)
    assert index.match(normalize("BRAMBLEWAYS BAKERY")) is None
    assert index.match("xBRAMBLEWAYy").entity == "Brambleway Funding"
    assert index.match("BRAMBLEWAY-FUNDING").alias == "BRAMBLEWAY"


def test_a_spaced_alias_also_matches_its_run_together_form_of_eight_characters_or_more():
    index = AliasIndex(FABRICATED)
    assert RUN_TOGETHER_MIN_LENGTH == 8
    assert index.match(normalize("CHECKCARD 0102 TARNMOORCAPITAL")) == PayeeMatch(
        "Tarnmoor Capital", "confirmed_lender", "TARNMOOR CAPITAL"
    )
    assert index.match(normalize("PAYMENT TO TARNMOOR")) == PayeeMatch(
        "Tarnmoor Capital", "confirmed_lender", "TARN MOOR"
    )
    seven = AliasIndex({"confirmed_lender": {"Oxbow Lend": ("OXBOW LE",)}})  # "OXBOWLE" has 7 characters
    assert seven.match("OXBOWLE") is None


def test_an_explicit_alias_beats_another_entitys_run_together_form():
    index = AliasIndex({
        "confirmed_lender": {"Joined": ("NORTH WINDFUND",)},
        "alternative_position": {"Explicit": ("NORTHWINDFUND",)},
    })
    assert index.match("NORTHWINDFUND").entity == "Explicit"


def test_registry_match_has_no_run_together_forms():
    table = {"Tarnmoor Capital": ("TARNMOOR CAPITAL",)}
    assert registry_match("TARNMOORCAPITAL", table) is None
    assert registry_match("ACH TARNMOOR CAPITAL", table) == ("Tarnmoor Capital", "TARNMOOR CAPITAL")


def test_registry_match_on_an_empty_registry_is_none():
    assert registry_match("ANYTHING", {}) is None


def test_registry_match_never_serves_one_registrys_index_for_another():
    first = {"Brambleway Funding": ("BRAMBLEWAY",)}
    assert registry_match("BRAMBLEWAY", first) == ("Brambleway Funding", "BRAMBLEWAY")
    del first
    second = {"Tarnmoor Capital": ("TARNMOOR",)}
    assert registry_match("BRAMBLEWAY", second) is None
    assert registry_match("TARNMOOR", second) == ("Tarnmoor Capital", "TARNMOOR")


LIVE_REGISTRIES = (
    "INSURANCE_PROVIDER_ALIASES",
    "OPERATING_REVENUE_SOURCE_ALIASES",
    "LEGACY_CONFIRMED_LENDER_ALIASES",
    "LEGACY_POTENTIAL_LENDER_ALIASES",
    "LEASE_PROVIDER_ALIASES",
)


@pytest.mark.parametrize("name", LIVE_REGISTRIES)
def test_registry_match_agrees_with_the_legacy_matcher_on_every_alias_of_the_live_registries(name):
    table = getattr(registry, name, None)
    if table is None:
        pytest.skip(f"{name} no longer exists")
    texts = [*TEXTS]
    for aliases in table.values():
        for alias in aliases:
            texts.append(f"ACH DEBIT {alias} PMT 0102")
            texts.append(normalize(f"POS {alias}X"))
            texts.append(normalize(f"{alias}-{alias}"))
    for text in texts:
        assert registry_match(text, table) == legacy_registry_match(text, table), text


def test_match_known_payee_is_the_index_over_payee_group_registries():
    index = AliasIndex(registry.PAYEE_GROUP_REGISTRIES)
    texts = [normalize(f"ACH DEBIT {alias}") for table in registry.PAYEE_GROUP_REGISTRIES.values()
             for aliases in table.values() for alias in aliases]
    for text in [*texts, *TEXTS]:
        assert match_known_payee(text) == index.match(text)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `C:\Python314\python.exe -m pytest tests/test_payee_matcher.py -q -p no:cacheprovider`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'analysis.description_text'`.

- [ ] **Step 3: Move normalization into its own module**

Create `analysis/description_text.py`:

```python
"""Normalization of transaction descriptions, shared by the classifier and the payee matcher.

It lives in its own module so that ``analysis.payee_matcher`` can normalize registry aliases at
import time without importing ``analysis.transaction_classifier``, which imports the matcher.
``analysis.transaction_classifier`` re-exports the function under its old import path.
"""
from __future__ import annotations

import re
import unicodedata


def normalize_transaction_description(description: str) -> str:
    """Normalize matching text while retaining the exact source separately."""
    decomposed = unicodedata.normalize("NFKD", description or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = ascii_text.upper().replace("&", " AND ")
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    normalized = re.sub(r"\bP0S\b", "POS", normalized)
    normalized = re.sub(r"\bN(?:\s|5)*S(?:\s)*F\b|\bN5F\b", "NSF", normalized)
    normalized = re.sub(r"\bA(?:\s)*[T7](?:\s)*M\b", "ATM", normalized)
    normalized = re.sub(r"\b1NSURANCE\b|\bINSURANCF\b", "INSURANCE", normalized)
    normalized = re.sub(r"\bF1NANCE\b", "FINANCE", normalized)
    normalized = re.sub(r"\bLN\b", "LOAN", normalized)
    normalized = re.sub(r"\bPAYMT\b", "PAYMENT", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
```

In `analysis/transaction_classifier.py`, make three edits.

First, replace:

```python
import re
import unicodedata
from dataclasses import dataclass, replace
```

with:

```python
import re
from dataclasses import dataclass, replace
```

Second, replace:

```python
from .dates import parse_date
from .revenue import RevenueState, revenue_contribution_flags
```

with:

```python
from .dates import parse_date
from .revenue import RevenueState, revenue_contribution_flags
# Imported after the registry and revenue imports on purpose: a rewrite of that block must not drop them.
from .description_text import normalize_transaction_description
```

Third, delete this whole function (lines 171-184) **together with the two blank lines after it** (185-186). `def _contains_alias(` then follows the class above it after two blank lines, as the function did:

```python
def normalize_transaction_description(description: str) -> str:
    """Normalize matching text while retaining the exact source separately."""
    decomposed = unicodedata.normalize("NFKD", description or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = ascii_text.upper().replace("&", " AND ")
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    normalized = re.sub(r"\bP0S\b", "POS", normalized)
    normalized = re.sub(r"\bN(?:\s|5)*S(?:\s)*F\b|\bN5F\b", "NSF", normalized)
    normalized = re.sub(r"\bA(?:\s)*[T7](?:\s)*M\b", "ATM", normalized)
    normalized = re.sub(r"\b1NSURANCE\b|\bINSURANCF\b", "INSURANCE", normalized)
    normalized = re.sub(r"\bF1NANCE\b", "FINANCE", normalized)
    normalized = re.sub(r"\bLN\b", "LOAN", normalized)
    normalized = re.sub(r"\bPAYMT\b", "PAYMENT", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
```

- [ ] **Step 4: Write the matcher**

Create `analysis/payee_matcher.py`:

```python
"""The known-payee matcher (spec section 4.6, contract C3).

Every alias is normalized once and indexed by its tokens. An alias matches when its tokens appear
as consecutive whole tokens of the description, separated by single spaces. That is exactly the
boundary rule ``(?<![A-Z0-9])alias(?![A-Z0-9])`` the classifier has always applied, evaluated with
dictionary lookups instead of one regular-expression search per alias.

Registries are read-only after import. An index is built once per registry object and is not
rebuilt when that object is later mutated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

from .classification_registry import PAYEE_GROUP_REGISTRIES
from .description_text import normalize_transaction_description

#: A spaced alias also matches its run-together form when that form has at least this many characters.
RUN_TOGETHER_MIN_LENGTH = 8
_TOKEN = re.compile(r"[A-Z0-9]+")


@dataclass(frozen=True)
class PayeeMatch:
    entity: str   # canonical entity
    state: str    # classification state from PAYEE_GROUP_REGISTRIES
    alias: str    # the alias as written in the registry


@dataclass(frozen=True)
class _Entry:
    length: int
    rank: int
    match: PayeeMatch


class AliasIndex:
    """Aliases normalized and compiled ONCE. match() returns the longest normalized alias found on token
    boundaries (?<![A-Z0-9])alias(?![A-Z0-9]); ties go to the earlier registry, then the earlier alias.
    A spaced alias whose run-together form has >= 8 characters also matches that form."""

    def __init__(
        self,
        registries: Mapping[str, Mapping[str, Sequence[str]]],
        *,
        run_together: bool = True,
    ) -> None:
        table: dict[tuple[str, ...], _Entry] = {}
        joined: list[tuple[tuple[str, ...], _Entry]] = []
        rank = 0
        for state, registry in registries.items():
            for entity, aliases in registry.items():
                for alias in aliases:
                    normalized = normalize_transaction_description(alias)
                    if not normalized:
                        continue
                    tokens = tuple(normalized.split(" "))
                    entry = _Entry(len(normalized), rank, PayeeMatch(entity, state, alias))
                    rank += 1
                    table.setdefault(tokens, entry)
                    form = "".join(tokens)
                    if run_together and len(tokens) > 1 and len(form) >= RUN_TOGETHER_MIN_LENGTH:
                        joined.append(((form,), _Entry(len(form), entry.rank, entry.match)))
        for tokens, entry in joined:
            table.setdefault(tokens, entry)
        self._table = table
        self._longest = max((len(tokens) for tokens in table), default=0)

    def match(self, normalized_text: str) -> PayeeMatch | None:
        if not self._table or not normalized_text:
            return None
        runs = [(found.group(), found.start(), found.end()) for found in _TOKEN.finditer(normalized_text)]
        best: _Entry | None = None
        for start in range(len(runs)):
            tokens: list[str] = []
            for position in range(start, min(len(runs), start + self._longest)):
                if position > start and normalized_text[runs[position - 1][2]:runs[position][1]] != " ":
                    break
                tokens.append(runs[position][0])
                entry = self._table.get(tuple(tokens))
                if entry is not None and (
                    best is None
                    or entry.length > best.length
                    or (entry.length == best.length and entry.rank < best.rank)
                ):
                    best = entry
        return None if best is None else best.match


_DEFAULT_INDEX = AliasIndex(PAYEE_GROUP_REGISTRIES)
_REGISTRY_INDEXES: dict[int, tuple[Mapping[str, Sequence[str]], AliasIndex]] = {}
_REGISTRY_INDEX_LIMIT = 64


def match_known_payee(normalized_text: str) -> PayeeMatch | None:
    """The longest alias across every group registry (spec section 4.6), or None."""
    return _DEFAULT_INDEX.match(normalized_text)


def registry_match(
    normalized_text: str,
    registry: Mapping[str, Sequence[str]],
) -> tuple[str, str] | None:
    """Same (canonical, alias) semantics as the classifier's original ``_registry_match``: the longest
    alias of one registry on token boundaries, ties to the earlier entity and alias, no run-together
    forms. The index is built once per registry object."""
    if not registry:
        return None
    cached = _REGISTRY_INDEXES.get(id(registry))
    if cached is None or cached[0] is not registry:
        if len(_REGISTRY_INDEXES) >= _REGISTRY_INDEX_LIMIT:
            _REGISTRY_INDEXES.clear()
        cached = (registry, AliasIndex({"": registry}, run_together=False))
        _REGISTRY_INDEXES[id(registry)] = cached
    found = cached[1].match(normalized_text)
    return None if found is None else (found.entity, found.alias)
```

- [ ] **Step 5: Write the legacy reference (first version of the benchmark module)**

Create `tools/bench_classifier.py`:

```python
"""Classifier speed benchmark (spec section 4.6): a fabricated 300-row statement, classified with the
compiled matcher and with the matcher as it stood before S1. Nothing here reads a statement.

    python -m tools.bench_classifier
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.description_text import normalize_transaction_description  # noqa: E402


def legacy_registry_match(text: str, registry: dict[str, tuple[str, ...]]) -> tuple[str, str] | None:
    """The classifier's ``_registry_match`` before S1, verbatim in behaviour: re-normalizes and re-sorts
    every alias on every call. Kept only as the reference for parity and speed."""
    candidates = ((canonical, alias) for canonical, aliases in registry.items() for alias in aliases)
    for canonical, alias in sorted(
        candidates,
        key=lambda item: len(normalize_transaction_description(item[1])),
        reverse=True,
    ):
        normalized_alias = normalize_transaction_description(alias)
        if normalized_alias and re.search(
            rf"(?<![A-Z0-9]){re.escape(normalized_alias)}(?![A-Z0-9])", text
        ) is not None:
            return canonical, alias
    return None
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `C:\Python314\python.exe -m pytest tests/test_payee_matcher.py -q -p no:cacheprovider`
Expected: 15 passed.

Run: `C:\Python314\python.exe -m pytest tests/test_lender_insurance_classification.py tests/test_transaction_classifier.py tests/test_revenue_classification.py tests/test_r1_hardcodes.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider`
Expected: everything passes except the known `test_no_literal_account_numbers_in_ocr`.

- [ ] **Step 7: Commit**

```powershell
git add analysis/description_text.py analysis/payee_matcher.py analysis/transaction_classifier.py tools/bench_classifier.py tests/test_payee_matcher.py
git commit -m "analysis: compiled known-payee matcher (contract C3); normalization in its own module" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 4: The classifier matches through the compiled index (≥10× faster, no classification change)

**Files:**
- Modify: `analysis/transaction_classifier.py` (the import added in Task 3; `_registry_match`, lines 183-199 after Task 3)
- Replace: `tools/bench_classifier.py` (full version)
- Test: `tests/test_classifier_speed.py`

**Interfaces:**
- Consumes:
  - `registry_match` (Task 3);
  - `legacy_registry_match` (Task 3);
  - `PAYEE_GROUP_REGISTRIES` (Task 2);
  - `PayeeMatch` (Task 3).
- Produces:
  - `tools.bench_classifier.REQUIRED_SPEEDUP = 10.0`;
  - `legacy_match_known_payee(normalized_text: str) -> PayeeMatch | None`;
  - `legacy_matchers()`, a context manager;
  - `fabricated_statement(rows: int = 300) -> Statement`;
  - `measure(rows: int = 300) -> dict[str, float]` with keys `rows`, `legacy_seconds`, `current_seconds` and `speedup`;
  - `main() -> int`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_classifier_speed.py`:

```python
"""Spec section 4.6: the compiled matcher classifies a fabricated 300-row statement at least 10x faster,
and changes no classification."""
from __future__ import annotations

from dataclasses import asdict

from analysis import transaction_classifier
from tools.bench_classifier import REQUIRED_SPEEDUP, fabricated_statement, legacy_matchers, measure


def test_the_classifier_matches_through_the_compiled_registry_index(monkeypatch):
    calls = []
    compiled = transaction_classifier.registry_match

    def spy(text, registry):
        calls.append(text)
        return compiled(text, registry)

    monkeypatch.setattr(transaction_classifier, "registry_match", spy)
    transaction_classifier.classify_statement_transactions(fabricated_statement(3))
    assert calls


def test_the_compiled_matcher_changes_no_record_of_the_fabricated_statement():
    statement = fabricated_statement(60)
    compiled = [asdict(record) for record in transaction_classifier.classify_statement_transactions(statement)]
    with legacy_matchers():
        legacy = [asdict(record) for record in transaction_classifier.classify_statement_transactions(statement)]
    assert compiled == legacy


def test_three_hundred_fabricated_rows_classify_at_least_ten_times_faster():
    result = measure(300)
    assert result["speedup"] >= REQUIRED_SPEEDUP, result
```

- [ ] **Step 2: Run it to verify it fails**

Run: `C:\Python314\python.exe -m pytest tests/test_classifier_speed.py -q -p no:cacheprovider`
Expected: FAIL at collection with `ImportError: cannot import name 'REQUIRED_SPEEDUP' from 'tools.bench_classifier'`.

- [ ] **Step 3: Delegate `_registry_match` to the compiled index**

In `analysis/transaction_classifier.py`, replace:

```python
# Imported after the registry and revenue imports on purpose: a rewrite of that block must not drop them.
from .description_text import normalize_transaction_description
```

with:

```python
# Imported after the registry and revenue imports on purpose: a rewrite of that block must not drop them.
from .description_text import normalize_transaction_description
from .payee_matcher import registry_match
```

Then replace:

```python
def _registry_match(
    text: str,
    registry: dict[str, tuple[str, ...]],
) -> tuple[str, str] | None:
    candidates = (
        (canonical, alias)
        for canonical, aliases in registry.items()
        for alias in aliases
    )
    for canonical, alias in sorted(
        candidates,
        key=lambda item: len(normalize_transaction_description(item[1])),
        reverse=True,
    ):
        if _contains_alias(text, alias):
            return canonical, alias
    return None
```

with:

```python
def _registry_match(
    text: str,
    registry: dict[str, tuple[str, ...]],
) -> tuple[str, str] | None:
    # Spec section 4.6: the aliases are normalized and indexed once per registry, not on every call.
    return registry_match(text, registry)
```

- [ ] **Step 4: Write the full benchmark module**

Replace the whole content of `tools/bench_classifier.py` with:

```python
"""Classifier speed benchmark (spec section 4.6): a fabricated 300-row statement, classified with the
compiled matcher and with the matcher as it stood before S1. Nothing here reads a statement.

    python -m tools.bench_classifier
"""
from __future__ import annotations

import re
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis import transaction_classifier  # noqa: E402
from analysis.classification_registry import PAYEE_GROUP_REGISTRIES  # noqa: E402
from analysis.description_text import normalize_transaction_description  # noqa: E402
from analysis.payee_matcher import PayeeMatch  # noqa: E402
from analysis.schema import Statement, Transaction  # noqa: E402

#: Spec section 4.6: the new matcher must classify the statement at least this many times faster.
REQUIRED_SPEEDUP = 10.0


def legacy_registry_match(text: str, registry: dict[str, tuple[str, ...]]) -> tuple[str, str] | None:
    """The classifier's ``_registry_match`` before S1, verbatim in behaviour: re-normalizes and re-sorts
    every alias on every call. Kept only as the reference for parity and speed."""
    candidates = ((canonical, alias) for canonical, aliases in registry.items() for alias in aliases)
    for canonical, alias in sorted(
        candidates,
        key=lambda item: len(normalize_transaction_description(item[1])),
        reverse=True,
    ):
        normalized_alias = normalize_transaction_description(alias)
        if normalized_alias and re.search(
            rf"(?<![A-Z0-9]){re.escape(normalized_alias)}(?![A-Z0-9])", text
        ) is not None:
            return canonical, alias
    return None


def legacy_match_known_payee(normalized_text: str) -> PayeeMatch | None:
    """The known-payee lookup done the pre-S1 way: one legacy scan per group registry."""
    best: tuple[int, PayeeMatch] | None = None
    for state, registry in PAYEE_GROUP_REGISTRIES.items():
        found = legacy_registry_match(normalized_text, registry)
        if found is not None:
            length = len(normalize_transaction_description(found[1]))
            if best is None or length > best[0]:
                best = (length, PayeeMatch(found[0], state, found[1]))
    return None if best is None else best[1]


@contextmanager
def legacy_matchers() -> Iterator[None]:
    """Swap the classifier's compiled matchers for the pre-S1 algorithm while the block runs. It swaps
    whichever of ``registry_match`` and ``match_known_payee`` the classifier module holds, so it works
    before and after S2 rewires the rule order."""
    swaps = {"registry_match": legacy_registry_match, "match_known_payee": legacy_match_known_payee}
    saved = {name: getattr(transaction_classifier, name) for name in swaps if hasattr(transaction_classifier, name)}
    try:
        for name in saved:
            setattr(transaction_classifier, name, swaps[name])
        yield
    finally:
        for name, value in saved.items():
            setattr(transaction_classifier, name, value)


def fabricated_statement(rows: int = 300) -> Statement:
    """A third credits, a third ACH debits, a third card purchases; every descriptor is invented."""
    transactions = []
    for index in range(rows):
        day = f"2054-01-{index % 28 + 1:02d}"
        if index % 3 == 0:
            transactions.append(Transaction(
                date=day, description=f"MOBILE DEPOSIT REF {index:06d}", amount=250.0 + index, direction="credit"))
        elif index % 3 == 1:
            transactions.append(Transaction(
                date=day, description=f"ACH DEBIT VENDOR {index} PAYMENT", amount=-(40.0 + index), direction="debit"))
        else:
            transactions.append(Transaction(
                date=day, description=f"POS DEBIT SHOP {index}", amount=-(5.0 + index), direction="debit"))
    return Statement(transactions=transactions)


def _seconds(statement: Statement, repeats: int) -> float:
    best = float("inf")
    for _ in range(repeats):
        started = time.perf_counter()
        transaction_classifier.classify_statement_transactions(statement)
        best = min(best, time.perf_counter() - started)
    return best


def measure(rows: int = 300) -> dict[str, float]:
    """Best of three with the compiled matchers; one run with the legacy matchers swapped in."""
    statement = fabricated_statement(rows)
    _seconds(statement, 1)
    current = _seconds(statement, 3)
    with legacy_matchers():
        legacy = _seconds(statement, 1)
    return {"rows": rows, "legacy_seconds": legacy, "current_seconds": current, "speedup": legacy / current}


def main() -> int:
    result = measure()
    print(f"{result['rows']} fabricated rows: legacy {result['legacy_seconds']:.3f} s, "
          f"compiled {result['current_seconds']:.3f} s, {result['speedup']:.1f}x faster "
          f"(required: {REQUIRED_SPEEDUP:.0f}x)")
    return 0 if result["speedup"] >= REQUIRED_SPEEDUP else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the tests to verify they pass, and measure**

Run: `C:\Python314\python.exe -m pytest tests/test_classifier_speed.py tests/test_payee_matcher.py -q -p no:cacheprovider`
Expected: 18 passed, in about 6 s (the legacy run alone takes 2-5 s).

Run: `C:\Python314\python.exe -m tools.bench_classifier`
Expected: exit code 0, and a line such as `300 fabricated rows: legacy 2.586 s, compiled 0.071 s, 36.6x faster (required: 10x)`. That line comes from the trial run on this host; your timings will vary. The speedup must be at least 10.

- [ ] **Step 6: Run the three selections**

Run the three commands from "Before Task 1".
Expected: the same counts as the baseline: `404 passed`; `146 passed, 1 failed` (the known failure); `306 passed`.

- [ ] **Step 7: Commit**

```powershell
git add analysis/transaction_classifier.py tools/bench_classifier.py tests/test_classifier_speed.py
git commit -m "classifier: registry lookups through the compiled index (spec 4.6 speed, no classification change)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 5: The ledger's schema and validator (C10)

> **Amended after review (fix round 1, 2026-09-25).** The code blocks below are the reviewed code:
> - every validator message masks the names and values it quotes (`_shown`, `mask_digit_runs`), and `validate` scrubs every problem as a backstop, so no message quotes a run of five or more digits; `privacy_review` masks digit runs too;
> - `_public_url` parses URLs with `urllib.parse.urlsplit` and refuses credentials, `localhost`, private or loopback IP addresses, undotted or numeric hosts and a `|`;
> - the fixture's rejected entity looks somewhere other than its source (Task 6's column test).
>
> Step 5 counts 107 tests.
>
> **Amended for the owner's ruling of 2026-09-25 (A2-A4).** `Rules` gains `premium_insurer_aliases`, `merged` and `payout_credit`, which the fixture's `RULES` sets empty:
> - the hand-kept-alias rule exempts a ruled premium spelling on a `premium_financing` entity (`INSURER_TABLE`), and `premium_insurer_overlaps` leaves out an insurer alias that a premium entity holds itself;
> - `baseline_moves` and `baseline_problems` take `merged`: a merged entity is held by its target, is always a move (`Move.merged`), keeps no name of its own, and its lost aliases need the target's `Move:` sentence; `_merge_problems` refuses a bad key or target and a rendered entity under the merged name;
> - `payout_credit_problems` refuses a payout-credit name that is not an admitted entity of a group in `FINANCING_STATES`.
>
> Step 5 counts 128 tests.
>
> **Amended after the review of A1-A4 (2026-09-25).** `Rules` gains `reattributed`, which the fixture's `RULES` sets empty, and the fixture gains `PELLAM_BASELINE` and `pellam_ledger` (a fabricated lease entry whose first alias the owner gave to another company):
> - `baseline_moves` and `baseline_problems` take `reattributed`: a reattributed alias is left out of today's entity (it decides nothing, is never lost and is not the first alias of the name rule), and the entity is always a move that lists it (`Move.reattributed`);
> - `_reattribution_problems` refuses an alias that is not today's, a target that is not a ledger entity or does not hold the alias, and a registry that reads the alias as another entity;
> - `baseline_moves` holds an entity of today's registry by its name when no ledger entity holds any of its aliases, so `test_an_admitted_or_review_entity_needs_an_alias` now expects a lost alias, not a missing entity.
>
> Step 5 counts 140 tests.

**Files:**
- Create: `tools/lender_ledger.py`
- Create: `tests/lender_ledger_fixture.py`
- Test: `tests/test_lender_ledger.py`

**Interfaces:**
- Consumes:
  - `analysis.description_text.normalize_transaction_description` (Task 3);
  - `AliasIndex`, `registry_match` and `RUN_TOGETHER_MIN_LENGTH` (Task 3);
  - `analysis.flag_groups.FINANCING_STATES` (Task 1).
- Produces (used by Tasks 6-10):
  - **Constants:** `SCHEMA`, `LEDGER_PATH`, `EMPTY_LEDGER`, `TABLES` (group, table, heading) in C2 order, `GROUPS`, `TABLE_OF_GROUP`, `PAYEE_STATES`, `STATUSES`, `RENDERED`, `ADMITTING_VERDICTS`, `FIELDS`, `SHORT_ALIAS`, `GENERIC_WORDS`, `ORG_CUES`, `CONTEXT_ONLY_GROUPS`, `INSURER_TABLE`, `MOVE_MARKER`, `BASELINE_REVISION`, `BASELINE_TABLES`, `BASELINE_STATE`, `UNRULED_PLACES`, `WITHHELD`.
  - **Data model:**
    - `Evidence(source, note)` and `Verdict(round, verdict, confirmed)`;
    - `LedgerEntity(index, entity, group, business_type, aliases, status, short_alias_reason, evidence, verdicts, where_looked, notes)`, with the properties `.table` (its C2 table, or None) and `.place` (its group, `"potential_lender"` or `"no table"`);
    - `Rules(owner_named, platforms, brands, hand_kept, baseline, premium_insurer_aliases, merged, payout_credit, reattributed)`;
    - `Move(entity, table, was, now, lost, holder, reason, merged=False, reattributed=())`.
  - **Functions:**
    - `read_ledger(path: Path) -> object` and `ledger_digest(data: object) -> str`;
    - `parse_ledger(data: object) -> tuple[list[LedgerEntity], list[str]]`;
    - `render_tables(entities: list[LedgerEntity]) -> dict[str, dict[str, tuple[str, ...]]]`;
    - `baseline_from_source(source: str) -> dict` and `load_baseline(revision: str = BASELINE_REVISION) -> dict`;
    - `move_reason(notes: str) -> str`, the text of the `Move:` sentence or `""`;
    - `baseline_moves(entities, baseline, merged=None, reattributed=None) -> tuple[list[Move], list[tuple[str, str]]]` and `baseline_problems(entities, baseline, merged=None, reattributed=None) -> list[str]`;
    - `owner_named_problems(tables, owner_named) -> list[str]`;
    - `payout_credit_problems(entities, names) -> list[str]`;
    - `validate(data: object, rules: Rules) -> list[str]`;
    - `premium_insurer_overlaps(entities, insurers) -> list[tuple[str, str]]`;
    - `privacy_review(entities) -> list[str]`;
    - `mask_digit_runs(text: str) -> str`, which replaces every run of five or more digits with `WITHHELD`.
  - **Fixture:** `tests.lender_ledger_fixture.entity(...)`, `ledger(*changes)`, `pellam_ledger(aliases=..., notes=..., extra=())`, and the constants `ENTITIES`, `UNRESOLVED`, `BASELINE`, `OWNER_NAMED`, `HAND_KEPT`, `RULES` and `PELLAM_BASELINE`.

- [ ] **Step 1: Write the fabricated ledger fixture**

Create `tests/lender_ledger_fixture.py`:

```python
"""A fabricated curated ledger (contract C10) and the hand-kept inputs its validator reads.

Every company name, spelling and URL here is invented; none comes from a statement."""
from __future__ import annotations

import copy

from tools.lender_ledger import Rules


def entity(name, group, aliases, *, status="admitted", business_type="mca_or_revenue_based_funder",
           short_alias_reason=None, evidence=None, verdicts=None, where_looked=None, notes=""):
    slug = name.split()[0].lower()
    return {
        "entity": name,
        "group": group,
        "business_type": business_type,
        "aliases": list(aliases),
        "status": status,
        "short_alias_reason": short_alias_reason,
        "evidence": ([{"source": f"https://{slug}.example/", "note": "fabricated company site"}]
                     if evidence is None else evidence),
        "verdicts": ([{"round": "r1", "verdict": "upheld", "confirmed": True}] if verdicts is None else verdicts),
        "where_looked": [f"https://{slug}.example/"] if where_looked is None else where_looked,
        "notes": notes,
    }


UNRESOLVED = [{"round": "r2", "verdict": "unresolved", "confirmed": False}]

#: Index, name: 0 Quillon Funding, 1 Oldco Funding, 2 Ruledco, 3 Brambleway Capital, 4 Oxbow Card, 5 Oxbow,
#: 6 Rivett Motor Credit, 7 Penwick Mortgage, 8 Westfen Leasing, 9 Kelder Loans, 10 Gantry Floorplan Credit,
#: 11 Loxley Factoring, 12 Hollin Premium Finance, 13 Brisk Mutual Funding, 14 Brambleway Bank,
#: 15 Heldco Advance, 16 Marsh Recovery, 17 Tarnmoor Capital.
ENTITIES = [
    entity("Quillon Funding", "confirmed_lender", ["QUILLON FUNDING", "QUILLONFUND"]),
    entity("Oldco Funding", "confirmed_lender", ["OLDCO FUNDING", "OLDCO"]),
    entity("Ruledco", "alternative_position", ["RULEDCO CAPITAL"], business_type="platform_embedded_financing",
           notes="Move: fabricated owner ruling, an alternative position."),
    entity("Brambleway Capital", "line_of_credit", ["BRAMBLEWAY CAPITAL"], business_type="business_loc_provider"),
    entity("Oxbow Card", "credit_card_payment", ["OXBOW CARD PMT"], business_type="credit_card_payment"),
    entity("Oxbow", "card_issuer_context", ["OXBOW"], business_type="credit_card_payment"),
    entity("Rivett Motor Credit", "vehicle_financing", ["RIVETT MOTOR CREDIT"],
           business_type="auto_or_vehicle_finance"),
    entity("Penwick Mortgage", "mortgage", ["PENWICK MTG"], business_type="mortgage_servicer"),
    entity("Westfen Leasing", "lease_or_rental", ["WESTFEN LEASING"], business_type="lease_to_own"),
    entity("Kelder Loans", "personal_loan", ["KELDER LOANS"], business_type="personal_or_consumer_loan"),
    entity("Gantry Floorplan Credit", "floor_plan_financing", ["GANTRY FLOORPLAN"],
           business_type="floor_plan_financing"),
    entity("Loxley Factoring", "factoring", ["LOXLEY FACTORING"], business_type="factoring"),
    entity("Hollin Premium Finance", "premium_financing", ["HOLLIN PREMIUM FIN"], business_type="premium_finance"),
    entity("Brisk Mutual Funding", "premium_financing", ["BRISK MUTUAL FUNDING"], business_type="premium_finance"),
    entity("Brambleway Bank", "bank_name", ["BRAMBLEWAY BANK"], business_type="bank_loan_or_bank_loc"),
    entity("Heldco Advance", "confirmed_lender", ["HELDCO ADVANCE"], status="review", evidence=[],
           verdicts=UNRESOLVED, where_looked=["https://registry.example/heldco", "https://heldco.example/"],
           notes="Fabricated: identity unconfirmed."),
    entity("Marsh Recovery", "potential_lender", ["MARSH RECOVERY"], status="owner_ruling",
           business_type="servicer_or_processor_for_funders", evidence=[], verdicts=UNRESOLVED,
           where_looked=["https://marsh.example/", "https://registry.example/marsh"],
           notes="Fabricated: a collector whose funder is unknown; the owner decides."),
    entity("Tarnmoor Capital", "confirmed_lender", ["TARNMOOR CAP"], status="rejected",
           evidence=[{"source": "https://tarnmoor.example/", "note": "fabricated: a bakery"}],
           verdicts=[{"round": "r2", "verdict": "refuted", "confirmed": False}],
           where_looked=["https://registry.example/tarnmoor"], notes="Fabricated: a bakery, not a funder."),
]

#: Today's three lists, as the validator reads them from git (fabricated).
BASELINE = {
    "CONFIRMED_LENDER_ALIASES": {"Oldco Funding": ("OLDCO FUNDING", "OLDCO"), "Ruledco": ("RULEDCO CAPITAL",)},
    "POTENTIAL_LENDER_ALIASES": {"Heldco Advance": ("HELDCO ADVANCE",)},
    "LEASE_PROVIDER_ALIASES": {"Westfen Leasing": ("WESTFEN LEASING",)},
}

OWNER_NAMED = {
    "confirmed_lender": (("Quillon", "QUILLON FUNDING"),),
    "alternative_position": (("Ruledco", "RULEDCO CAPITAL"),),
    "line_of_credit": (("Brambleway", "BRAMBLEWAY CAPITAL"),),
    "credit_card_payment": (("Oxbow", "OXBOW CARD PMT"),),
    "floor_plan_financing": (("Gantry", "GANTRY FLOORPLAN"),),
    "factoring": (("Loxley", "LOXLEY FACTORING"),),
    "premium_financing": (("Hollin", "HOLLIN PREMIUM FIN"),),
    "bank_name": (("Brambleway Bank", "BRAMBLEWAY BANK LN PYMT"),),
}

HAND_KEPT = {
    "INSURANCE_PROVIDER_ALIASES": {"Brisk Mutual": ("BRISK MUTUAL",)},
    "OPERATING_REVENUE_SOURCE_ALIASES": {"Zanthos Pay": ("ZANTHOS PAY", "ZANTHOS")},
}

RULES = Rules(
    owner_named=OWNER_NAMED,
    platforms=frozenset({"ZANTHOS", "VELLUM"}),
    brands=frozenset({"RIVETT"}),
    hand_kept=HAND_KEPT,
    baseline=BASELINE,
    premium_insurer_aliases=frozenset(),
    merged={},
    payout_credit=(),
    reattributed={},
)


def ledger(*changes):
    """The fabricated ledger, with ``(index, field, value)`` changes applied to a deep copy."""
    entities = copy.deepcopy(ENTITIES)
    for index, field_name, value in changes:
        entities[index][field_name] = value
    return {"schema": 1, "entities": entities}


#: Today's three lists plus 'Pellam', a fabricated lease entry whose first alias the owner ruled names another
#: company, 'Pellam Solutions' (the reattribution tests).
PELLAM_BASELINE = {**BASELINE, "LEASE_PROVIDER_ALIASES": {
    **BASELINE["LEASE_PROVIDER_ALIASES"], "Pellam": ("PELLAM SOL", "PELLAM")}}


def pellam_ledger(aliases=("PELLAM LEASING",),
                  notes="Fabricated: a lease-to-own company. Move: bare PELLAM names other companies.", extra=()):
    """The fabricated ledger plus entity 18, 'Pellam', which keeps today's name with ``aliases``, entity 19,
    'Pellam Solutions', rejected, which holds the alias the owner gave it, and the ``extra`` entities."""
    data = ledger()
    data["entities"] += [
        entity("Pellam", "lease_or_rental", aliases, business_type="lease_to_own", notes=notes),
        entity("Pellam Solutions", "potential_lender", ["PELLAM SOL"], status="rejected",
               business_type="premium_billing", evidence=[], verdicts=UNRESOLVED,
               notes="Fabricated: premium billing, not a lender."),
        *extra,
    ]
    return data
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_lender_ledger.py`:

```python
"""Contract C10: the curated ledger's schema and every rule of its validator, on fabricated ledgers."""
from __future__ import annotations

import dataclasses
import re

import pytest

from tests.lender_ledger_fixture import (
    BASELINE, ENTITIES, HAND_KEPT, PELLAM_BASELINE, RULES, UNRESOLVED, entity, ledger, pellam_ledger,
)
from tools import lender_ledger


def _problems(*changes, rules=RULES):
    return lender_ledger.validate(ledger(*changes), rules)


def _entities(*changes):
    entities, problems = lender_ledger.parse_ledger(ledger(*changes))
    assert problems == []
    return entities


# --- the schema ------------------------------------------------------------------------------------------------


def test_the_fabricated_ledger_passes_every_rule():
    assert _problems() == []
    assert len(_entities()) == len(ENTITIES)


@pytest.mark.parametrize("data,problem", [
    ([], "the ledger is not an object with exactly the keys 'schema' and 'entities'"),
    ({"schema": 1, "entities": [], "extra": 1}, "the ledger is not an object with exactly the keys 'schema' and "
                                                "'entities'"),
    ({"schema": 2, "entities": []}, "the ledger schema is 2; this validator reads schema 1"),
    ({"schema": 1, "entities": {}}, "the ledger's 'entities' is not a list"),
])
def test_the_ledger_is_schema_1_with_a_list_of_entities(data, problem):
    assert lender_ledger.validate(data, RULES) == [problem]


def test_every_entity_has_exactly_the_c10_fields():
    data = ledger()
    del data["entities"][0]["notes"]
    data["entities"][0]["alias"] = "QUILLON"
    data["entities"][1] = "Oldco Funding"
    assert lender_ledger.validate(data, RULES) == [
        "entity 0: missing field(s) notes",
        "entity 0: unknown field(s) alias",
        "entity 1 is not an object",
    ]


@pytest.mark.parametrize("field_name,value,problem", [
    ("entity", "", "entity is not a non-empty string"),
    ("group", "insurance", "group 'insurance' is not a C10 group"),
    ("business_type", " ", "business_type is not a non-empty string"),
    ("aliases", "QUILLON FUNDING", "aliases is not a list of strings"),
    ("status", "maybe", "status 'maybe' is not one of admitted, review, owner_ruling, rejected"),
    ("short_alias_reason", "", "short_alias_reason is neither null nor a non-empty string"),
    ("evidence", {"source": "https://quillon.example/"}, "evidence is not a list"),
    ("evidence", [{"source": "https://quillon.example/"}],
     "evidence 0 is not an object of the strings 'source' and 'note'"),
    ("verdicts", [{"round": "r1", "verdict": "upheld", "confirmed": "yes"}],
     "verdict 0 is not an object of the strings 'round' and 'verdict' and a true/false 'confirmed'"),
    ("where_looked", "https://quillon.example/", "where_looked is not a list of strings"),
    ("notes", None, "notes is not a string"),
])
def test_every_field_has_its_c10_type(field_name, value, problem):
    assert _problems((0, field_name, value)) == [f"entity 0: {problem}"]


# --- C10: admission ---------------------------------------------------------------------------------------------


def test_an_admitted_entity_needs_evidence():
    assert _problems((0, "evidence", [])) == ["entity 0 ('Quillon Funding') is admitted without evidence"]


@pytest.mark.parametrize("verdicts", [
    [],
    [{"round": "r1", "verdict": "unresolved", "confirmed": True}],
    [{"round": "r1", "verdict": "upheld", "confirmed": False}],
])
def test_an_admitted_entity_needs_an_upheld_or_corrected_verdict_that_confirms_it(verdicts):
    assert _problems((0, "verdicts", verdicts)) == [
        "entity 0 ('Quillon Funding') is admitted without an upheld or corrected verdict that confirms it"
    ]


def test_a_corrected_verdict_admits_and_other_statuses_need_no_verdict():
    assert _problems((0, "verdicts", [{"round": "r2", "verdict": "corrected", "confirmed": True}])) == []
    assert _problems((17, "evidence", []), (17, "verdicts", [])) == []


def test_an_admitted_or_review_entity_needs_an_alias():
    assert _problems((15, "aliases", [])) == ["entity 15 ('Heldco Advance') is review but has no alias",
                                              "today's POTENTIAL_LENDER_ALIASES entity 'Heldco Advance' loses 1 of "
                                              "today's aliases without a sentence starting 'Move:' in its notes"]
    assert _problems((16, "aliases", [])) == []


@pytest.mark.parametrize("group", ["credit_card_payment", "card_issuer_context", "bank_name", "premium_financing"])
def test_an_entity_of_a_table_read_only_with_context_is_never_under_review(group):
    data = ledger()
    data["entities"].append(entity("Zephyrton Card Services", group, ["ZEPHYRTON CARD PMT"], status="review",
                                   business_type="fabricated_context_payee", evidence=[], verdicts=UNRESOLVED,
                                   notes="Fabricated: identity unconfirmed."))
    assert lender_ledger.validate(data, RULES) == [
        f"entity 18 ('Zephyrton Card Services') is review in {group}, a table the classifier reads only with "
        "context, but the potential tier reads its aliases without that context: admit it, or record it as "
        "owner_ruling or rejected"
    ]


# --- C10: the alias rules --------------------------------------------------------------------------------------


@pytest.mark.parametrize("alias,problem", [
    ("QUILLON#FUND", "alias 'QUILLON#FUND' is masked ('#')"),
    ("Quillon Fund", "alias 'Quillon Fund' has lowercase letters"),
    ("QUILLON-FUND", "alias 'QUILLON-FUND' has characters outside A-Z, 0-9, space and '&'"),
    ("QUILLON  FUND", "alias 'QUILLON  FUND' has extra spaces"),
    ("", "an alias is empty"),
])
def test_an_alias_is_upper_case_letters_digits_spaces_and_ampersands(alias, problem):
    assert _problems((0, "aliases", ["QUILLON FUNDING", alias])) == [f"entity 0 ('Quillon Funding'): {problem}"]


def test_the_character_rules_hold_for_every_status_and_an_ampersand_is_allowed():
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QUILLON & SONS"])) == []
    assert _problems((17, "aliases", ["TARNMOOR#CAP"])) == [
        "entity 17 ('Tarnmoor Capital'): alias 'TARNMOOR#CAP' is masked ('#')"
    ]


@pytest.mark.parametrize("alias", ["CAPITAL", "FUNDING LLC", "EQUIPMENT FINANCE", "LOAN PAYMENT"])
def test_an_alias_of_generic_words_only_is_refused(alias):
    assert _problems((0, "aliases", ["QUILLON FUNDING", alias])) == [
        f"entity 0 ('Quillon Funding'): alias {alias!r} is only generic words"
    ]


def test_an_entity_in_no_table_may_keep_a_generic_alias_as_evidence():
    assert _problems((17, "aliases", ["TARNMOOR CAP", "CAPITAL FUNDING"])) == []


def test_a_bare_platform_name_or_a_hand_kept_alias_is_refused_and_a_financing_alias_is_not():
    assert _problems((0, "aliases", ["QUILLON FUNDING", "VELLUM"])) == [
        "entity 0 ('Quillon Funding'): alias 'VELLUM' is a bare platform name (spec section 5: the "
        "operating-revenue registry only)"
    ]
    assert _problems((0, "aliases", ["QUILLON FUNDING", "ZANTHOS PAY"])) == [
        "entity 0 ('Quillon Funding'): alias 'ZANTHOS PAY' is also an alias of the hand-kept "
        "OPERATING_REVENUE_SOURCE_ALIASES entity 'Zanthos Pay'"
    ]
    assert _problems((0, "aliases", ["QUILLON FUNDING", "ZANTHOS CAPITAL"])) == []


def test_a_bare_brand_name_is_an_alias_only_of_the_context_or_bank_tables():
    assert _problems((6, "aliases", ["RIVETT MOTOR CREDIT", "RIVETT"])) == [
        "entity 6 ('Rivett Motor Credit'): alias 'RIVETT' is a bare brand name; it belongs in "
        "card_issuer_context or bank_name (spec section 5)"
    ]
    data = ledger()
    data["entities"].append(entity("Rivett", "card_issuer_context", ["RIVETT"]))
    assert lender_ledger.validate(data, RULES) == []


def test_a_card_payment_alias_carries_card_or_payment_wording():
    assert _problems((4, "aliases", ["OXBOW CARD PMT", "OXBOW MUTUAL"])) == [
        "entity 4 ('Oxbow Card'): alias 'OXBOW MUTUAL' has no card or payment wording; a bare issuer name "
        "belongs in card_issuer_context (contract C10)"
    ]
    assert _problems((4, "aliases", ["OXBOW CARD PMT", "OXBOW AUTO PAY", "OXBOW CRD EPAY"])) == []


def test_an_alias_of_four_characters_or_fewer_needs_a_reason():
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QFND"])) == [
        "entity 0 ('Quillon Funding'): alias 'QFND' has 4 characters or fewer and no short_alias_reason"
    ]
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QFND"]),
                     (0, "short_alias_reason", "Fabricated: the funder's own initialism.")) == []


@pytest.mark.parametrize("index,aliases,problem", [
    (3, ["BRAMBLEWAY CAPITAL", "QUILLON FUNDING"],
     "alias 'QUILLON FUNDING' appears under entity 0 ('Quillon Funding') and entity 3 ('Brambleway Capital')"),
    (17, ["TARNMOOR CAP", "QUILLON FUNDING"],
     "alias 'QUILLON FUNDING' appears under entity 0 ('Quillon Funding') and entity 17 ('Tarnmoor Capital')"),
])
def test_one_alias_belongs_to_one_entity_whatever_its_status(index, aliases, problem):
    assert _problems((index, "aliases", aliases)) == [problem]


def test_spellings_that_normalize_alike_are_one_alias():
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QUILLON & SONS"]),
                     (3, "aliases", ["BRAMBLEWAY CAPITAL", "QUILLON AND SONS"])) == [
        "alias 'QUILLON AND SONS' appears under entity 0 ('Quillon Funding') and entity 3 ('Brambleway Capital')"
    ]


def test_a_run_together_form_of_a_known_payee_alias_belongs_to_that_payee_only():
    assert _problems((3, "aliases", ["BRAMBLEWAY CAPITAL", "QUILLONFUNDING"])) == [
        "run-together form 'QUILLONFUNDING' of entity 0 ('Quillon Funding') is also claimed by entity 3 "
        "('Brambleway Capital')"
    ]


def test_an_entity_name_is_used_once_and_never_the_name_of_a_hand_kept_entity():
    data = ledger()
    data["entities"].append(entity("Quillon Funding", "confirmed_lender", ["QUILLON CAPITAL"], status="rejected"))
    assert lender_ledger.validate(data, RULES) == [
        "entity name 'Quillon Funding' appears more than once (entities 0 and 18)"
    ]
    assert _problems((13, "entity", "Brisk Mutual")) == [
        "entity 13 ('Brisk Mutual') has the name of an entity of the hand-kept INSURANCE_PROVIDER_ALIASES"
    ]


def test_a_premium_alias_never_repeats_a_hand_kept_insurer_alias():
    assert _problems((13, "aliases", ["BRISK MUTUAL FUNDING", "BRISK MUTUAL"])) == [
        "entity 13 ('Brisk Mutual Funding'): alias 'BRISK MUTUAL' is also an alias of the hand-kept "
        "INSURANCE_PROVIDER_ALIASES entity 'Brisk Mutual'"
    ]


def test_a_premium_alias_that_contains_an_insurer_alias_is_listed_for_the_owner_not_refused():
    assert lender_ledger.premium_insurer_overlaps(_entities(), HAND_KEPT["INSURANCE_PROVIDER_ALIASES"]) == [
        ("Brisk Mutual Funding", "Brisk Mutual")
    ]


def _premium_ruled(*spellings, **changes):
    """RULES with the premium-finance spellings the owner ruled may repeat an insurer alias."""
    return dataclasses.replace(RULES, premium_insurer_aliases=frozenset(spellings), **changes)


def test_a_premium_alias_the_owner_ruled_may_repeat_a_hand_kept_insurer_alias():
    assert _problems((13, "aliases", ["BRISK MUTUAL FUNDING", "BRISK MUTUAL"]),
                     rules=_premium_ruled("BRISK MUTUAL")) == []


def test_the_premium_insurer_ruling_holds_only_on_a_premium_financing_entity():
    assert _problems((11, "aliases", ["LOXLEY FACTORING", "BRISK MUTUAL"]), rules=_premium_ruled("BRISK MUTUAL")) == [
        "entity 11 ('Loxley Factoring'): alias 'BRISK MUTUAL' is also an alias of the hand-kept "
        "INSURANCE_PROVIDER_ALIASES entity 'Brisk Mutual'"
    ]


def test_the_premium_insurer_ruling_exempts_only_its_own_spellings():
    insurers = {**HAND_KEPT, "INSURANCE_PROVIDER_ALIASES": {"Brisk Mutual": ("BRISK MUTUAL", "BRISK MUTUAL GROUP")}}
    rules = _premium_ruled("BRISK MUTUAL", hand_kept=insurers)
    assert _problems((13, "aliases", ["BRISK MUTUAL FUNDING", "BRISK MUTUAL", "BRISK MUTUAL GROUP"]),
                     rules=rules) == [
        "entity 13 ('Brisk Mutual Funding'): alias 'BRISK MUTUAL GROUP' is also an alias of the hand-kept "
        "INSURANCE_PROVIDER_ALIASES entity 'Brisk Mutual'"
    ]


def test_the_premium_insurer_ruling_never_exempts_an_operating_revenue_alias():
    assert _problems((13, "aliases", ["BRISK MUTUAL FUNDING", "ZANTHOS PAY"]),
                     rules=_premium_ruled("ZANTHOS PAY")) == [
        "entity 13 ('Brisk Mutual Funding'): alias 'ZANTHOS PAY' is also an alias of the hand-kept "
        "OPERATING_REVENUE_SOURCE_ALIASES entity 'Zanthos Pay'"
    ]


def test_an_insurer_alias_that_a_premium_entity_holds_is_an_overlap_of_no_premium_entity():
    insurers = HAND_KEPT["INSURANCE_PROVIDER_ALIASES"]
    hollin = (12, "aliases", ["HOLLIN PREMIUM FIN", "HOLLIN BRISK MUTUAL"])
    assert lender_ledger.premium_insurer_overlaps(_entities(hollin), insurers) == [
        ("Hollin Premium Finance", "Brisk Mutual"), ("Brisk Mutual Funding", "Brisk Mutual")
    ]
    held = (13, "aliases", ["BRISK MUTUAL FUNDING", "BRISK MUTUAL"])
    assert lender_ledger.premium_insurer_overlaps(_entities(hollin, held), insurers) == []


# --- C10: the payees the owner named ----------------------------------------------------------------------------


@pytest.mark.parametrize("changes,problem", [
    ([(0, "status", "review")],
     "owner-named Quillon is not admitted in confirmed_lender: 'QUILLON FUNDING' matches nothing"),
    ([(2, "group", "confirmed_lender"), (2, "business_type", "mca_or_revenue_based_funder")],
     "owner-named Ruledco is not admitted in alternative_position: 'RULEDCO CAPITAL' matches 'Ruledco' "
     "(confirmed_lender)"),
    ([(3, "status", "owner_ruling")],
     "owner-named Brambleway is not admitted in line_of_credit: 'BRAMBLEWAY CAPITAL' matches nothing"),
    ([(4, "group", "lease_or_rental")],
     "owner-named Oxbow is not admitted in credit_card_payment: 'OXBOW CARD PMT' matches 'Oxbow Card' "
     "(lease_or_rental)"),
    ([(12, "group", "factoring")],
     "owner-named Hollin is not admitted in premium_financing: 'HOLLIN PREMIUM FIN' matches "
     "'Hollin Premium Finance' (factoring)"),
    ([(14, "status", "rejected")],
     "owner-named Brambleway Bank is not admitted in bank_name: 'BRAMBLEWAY BANK LN PYMT' matches nothing"),
])
def test_every_payee_the_owner_named_is_admitted_in_its_group(changes, problem):
    assert _problems(*changes) == [problem]


def test_a_card_issuer_the_owner_named_may_be_a_bare_issuer_name_of_the_context_table():
    rules = dataclasses.replace(RULES, owner_named={"credit_card_payment": (("Oxbow", "OXBOW EPAYMENT"),)})
    assert _problems(rules=rules) == []


# --- the payout-credit entities (owner ruling: a D1 exception S2 reads) ------------------------------------------


def test_a_payout_credit_entity_is_an_admitted_entity_of_a_group_whose_credits_are_financing_proceeds():
    names = ("Quillon Funding", "Ruledco", "Brambleway Capital", "Rivett Motor Credit", "Penwick Mortgage",
             "Kelder Loans", "Gantry Floorplan Credit", "Loxley Factoring")
    assert _problems(rules=dataclasses.replace(RULES, payout_credit=names)) == []


NOT_PAYOUT = ("a payout-credit exception needs an admitted entity of a group whose credits D1 treats as financing "
              "proceeds")


@pytest.mark.parametrize("name,problem", [
    ("Quillon Capital", "PAYOUT_CREDIT_ENTITIES names 'Quillon Capital', which is not a ledger entity"),
    ("Heldco Advance", f"PAYOUT_CREDIT_ENTITIES names entity 15 ('Heldco Advance'), review in confirmed_lender: "
                       f"{NOT_PAYOUT}"),
    ("Tarnmoor Capital", f"PAYOUT_CREDIT_ENTITIES names entity 17 ('Tarnmoor Capital'), rejected in "
                         f"confirmed_lender: {NOT_PAYOUT}"),
    ("Westfen Leasing", f"PAYOUT_CREDIT_ENTITIES names entity 8 ('Westfen Leasing'), admitted in lease_or_rental: "
                        f"{NOT_PAYOUT}"),
    ("Oxbow Card", f"PAYOUT_CREDIT_ENTITIES names entity 4 ('Oxbow Card'), admitted in credit_card_payment: "
                   f"{NOT_PAYOUT}"),
    ("Brambleway Bank", f"PAYOUT_CREDIT_ENTITIES names entity 14 ('Brambleway Bank'), admitted in bank_name: "
                        f"{NOT_PAYOUT}"),
    ("Hollin Premium Finance", f"PAYOUT_CREDIT_ENTITIES names entity 12 ('Hollin Premium Finance'), admitted in "
                               f"premium_financing: {NOT_PAYOUT}"),
])
def test_a_payout_credit_entity_outside_the_financing_groups_is_refused(name, problem):
    assert _problems(rules=dataclasses.replace(RULES, payout_credit=(name,))) == [problem]


def test_no_payout_credit_problem_quotes_a_run_of_five_or_more_digits():
    assert _problems((9, "entity", "Kelder 7777777 Loans"),
                     rules=dataclasses.replace(RULES, payout_credit=("Quillon 7777777", "Kelder 7777777 Loans"))) == [
        "entity 9: the entity field carries a run of five or more digits",
        f"PAYOUT_CREDIT_ENTITIES names {lender_ledger.WITHHELD}, which is not a ledger entity",
    ]


# --- privacy -----------------------------------------------------------------------------------------------------


def test_a_run_of_five_or_more_digits_is_refused_outside_urls():
    assert _problems((0, "notes", "fabricated reference 5551234")) == [
        "entity 0 ('Quillon Funding'): the notes field carries a run of five or more digits"
    ]
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QUILLON 45219"])) == [
        "entity 0 ('Quillon Funding'): an alias carries a run of five or more digits that today's registry does "
        "not hold"
    ]
    assert _problems((16, "entity", "7777777 ONTARIO INC")) == [
        "entity 16: the entity field carries a run of five or more digits"
    ]
    assert _problems((0, "evidence", [{"source": "https://registry.example/company/12345678", "note": "x"}])) == []


def test_a_digit_run_is_allowed_in_an_alias_todays_registry_already_holds():
    baseline = {**BASELINE, "CONFIRMED_LENDER_ALIASES": {
        **BASELINE["CONFIRMED_LENDER_ALIASES"], "Oldco Funding": ("OLDCO FUNDING", "OLDCO", "OLDCO 4444444")}}
    rules = dataclasses.replace(RULES, baseline=baseline)
    assert _problems((1, "aliases", ["OLDCO FUNDING", "OLDCO", "OLDCO 4444444"]), rules=rules) == []


NUMBERED = "7777777 ONTARIO INC"
WITHHELD = "(withheld: a run of digits)"


def test_no_message_quotes_a_digit_run_name_that_is_duplicated_and_holds_todays_first_alias():
    assert _problems((1, "entity", NUMBERED), (16, "entity", NUMBERED)) == [
        f"entity name {WITHHELD} appears more than once (entities 1 and 16)",
        "entity 1: the entity field carries a run of five or more digits",
        "entity 16: the entity field carries a run of five or more digits",
        f"the ledger entity holding the first alias of today's 'Oldco Funding' is named {WITHHELD}: keep today's "
        "name (S2's pins and the census compare entity names)",
    ]


@pytest.mark.parametrize("data,rules", [
    (ledger((0, "entity", "Quillon 7777777 Funding"), (0, "group", "line_of_credit")), RULES),
    (ledger(), dataclasses.replace(RULES, baseline={**BASELINE, "POTENTIAL_LENDER_ALIASES": {
        **BASELINE["POTENTIAL_LENDER_ALIASES"], "Septima 7777777 Holdings": ("SEPTIMA HOLDINGS",)}})),
    (ledger(), dataclasses.replace(RULES, owner_named={
        "confirmed_lender": (("Quillon 7777777", "QUILLON 7777777"),)})),
    (ledger((13, "aliases", ["BRISK MUTUAL FUNDING", "BRISK MUTUAL"])),
     dataclasses.replace(RULES, hand_kept={"INSURANCE_PROVIDER_ALIASES": {"Brisk 7777777": ("BRISK MUTUAL",)}})),
    (ledger((0, "group", "grp 7777777")), RULES),
    (ledger((0, "status", "7777777")), RULES),
    (ledger((0, "7777777", "x")), RULES),
    ({"schema": 7777777, "entities": []}, RULES),
])
def test_no_problem_ever_quotes_a_run_of_five_or_more_digits(data, rules):
    problems = lender_ledger.validate(data, rules)
    assert problems
    assert [problem for problem in problems if re.search(r"\d{5}", problem)] == []
    assert any(WITHHELD in problem for problem in problems)


def test_validate_withholds_a_digit_run_whichever_rule_would_quote_it(monkeypatch):
    monkeypatch.setattr(lender_ledger, "baseline_problems", lambda *_args: ["fabricated 12345 and 7777777"])
    assert lender_ledger.validate(ledger(), RULES) == [f"fabricated {WITHHELD} and {WITHHELD}"]


def test_the_privacy_review_never_quotes_a_run_of_five_or_more_digits():
    assert lender_ledger.privacy_review(_entities((16, "entity", "Marsh 7777777 Recovery"),
                                                  (16, "aliases", ["MARSH RECOVERY", "REMCO 4444444"]))) == [
        "alias shares no word with its name: Quillon Funding | QUILLONFUND",
        "no organisation word in the name: Ruledco (admitted)",
        "no organisation word in the name: Oxbow Card (admitted)",
        "no organisation word in the name: Oxbow (admitted)",
        f"no organisation word in the name: Marsh {WITHHELD} Recovery (owner_ruling)",
        f"alias shares no word with its name: Marsh {WITHHELD} Recovery | REMCO {WITHHELD}",
    ]


def test_sources_and_where_looked_are_public_urls_without_a_query_string():
    assert _problems((0, "where_looked", ["https://search.example/?q=QUILLON"]),
                     (0, "evidence", [{"source": "descriptor: fabricated", "note": "x"}])) == [
        "entity 0 ('Quillon Funding'): evidence 0 source is not a public URL without a query string",
        "entity 0 ('Quillon Funding'): where_looked 0 is not a public URL without a query string",
    ]


@pytest.mark.parametrize("url", [
    "https://user:token@quillon.example/",
    "https://user@quillon.example/",
    "http://localhost/quillon",
    "http://docs.localhost/quillon",
    "http://127.0.0.1/quillon",
    "http://10.1.2.3/quillon",
    "http://192.168.1.20/quillon",
    "http://[::1]/quillon",
    "http://intranet/quillon",
    "http://0177.0.0.1/quillon",
    "https:///quillon",
    "https://quillon.example:port/",
    "https://quillon.example/a|b",
])
def test_a_url_with_credentials_or_on_a_local_private_or_undotted_host_is_not_public(url):
    assert _problems((0, "where_looked", [url])) == [
        "entity 0 ('Quillon Funding'): where_looked 0 is not a public URL without a query string"
    ]


@pytest.mark.parametrize("url", [
    "https://quillon.example/", "http://registry.example/company/about.html", "https://quillon.example:8443/",
    "https://8.8.8.8/quillon",
])
def test_a_url_on_a_public_host_is_public(url):
    assert _problems((0, "where_looked", [url])) == []


def test_the_privacy_review_lists_every_name_without_an_organisation_word_and_every_foreign_alias():
    assert lender_ledger.privacy_review(_entities()) == [
        "alias shares no word with its name: Quillon Funding | QUILLONFUND",
        "no organisation word in the name: Ruledco (admitted)",
        "no organisation word in the name: Oxbow Card (admitted)",
        "no organisation word in the name: Oxbow (admitted)",
        "no organisation word in the name: Marsh Recovery (owner_ruling)",
    ]


# --- spec section 9: today's registry -------------------------------------------------------------------------


def test_every_entity_of_todays_registry_is_in_the_ledger():
    data = ledger()
    del data["entities"][1]
    problems = lender_ledger.validate(data, RULES)
    assert problems == ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' is in no ledger entity: record it "
                        "in its place, or moved or rejected with a sentence starting 'Move:' in its notes"]


def test_an_entity_of_todays_registry_that_keeps_its_name_but_none_of_its_aliases_loses_them_all():
    assert _problems((1, "aliases", ["OLDCO FUNDING GROUP"])) == [
        "today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' loses 2 of today's aliases without a sentence "
        "starting 'Move:' in its notes"
    ]
    assert _problems((1, "aliases", ["OLDCO FUNDING GROUP"]),
                     (1, "notes", "Move: fabricated: its statements print the longer name.")) == []


def test_an_entity_of_todays_registry_keeps_its_name():
    assert _problems((1, "entity", "Oldco Funding LLC")) == [
        "the ledger entity holding the first alias of today's 'Oldco Funding' is named 'Oldco Funding LLC': keep "
        "today's name (S2's pins and the census compare entity names)"
    ]


@pytest.mark.parametrize("changes,problems", [
    ([(1, "group", "line_of_credit"), (1, "business_type", "business_loc_provider")],
     ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' moves from confirmed_lender to line_of_credit "
      "without a sentence starting 'Move:' in its notes"]),
    ([(1, "group", "line_of_credit"), (1, "business_type", "business_loc_provider"),
      (1, "notes", "Fabricated: the company site describes small-business funding.")],
     ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' moves from confirmed_lender to line_of_credit "
      "without a sentence starting 'Move:' in its notes"]),
    ([(1, "aliases", ["OLDCO FUNDING"])],
     ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' loses 1 of today's aliases without a sentence "
      "starting 'Move:' in its notes"]),
    ([(1, "status", "rejected")],
     ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' moves from confirmed_lender to no table without "
      "a sentence starting 'Move:' in its notes",
      "today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' loses 2 of today's aliases without a sentence "
      "starting 'Move:' in its notes"]),
    ([(8, "group", "personal_loan")],
     ["today's LEASE_PROVIDER_ALIASES entity 'Westfen Leasing' moves from lease_or_equipment_financing to "
      "personal_loan without a sentence starting 'Move:' in its notes"]),
    ([(8, "group", "confirmed_lender")], []),
    ([(1, "status", "rejected"), (1, "notes", "Fabricated: a funder. Move: the owner ruled it out.")], []),
])
def test_a_move_or_a_lost_alias_of_todays_registry_needs_a_move_sentence(changes, problems):
    assert _problems(*changes) == problems


@pytest.mark.parametrize("notes,reason", [
    ("Move: the owner ruled it out.", "the owner ruled it out."),
    ("Fabricated: a funder. Move: the owner ruled it out.", "the owner ruled it out."),
    ("Fabricated: a funder; Move:  renamed by the owner.", "renamed by the owner."),
    ("Fabricated: see the Move: column.", ""),
    ("Move:", ""),
    ("", ""),
])
def test_only_a_sentence_that_starts_with_the_move_marker_is_a_reason(notes, reason):
    assert lender_ledger.move_reason(notes) == reason


def test_baseline_moves_list_every_changed_entity_with_its_reason():
    moves, missing = lender_ledger.baseline_moves(_entities(), BASELINE)
    assert missing == []
    assert moves == [
        lender_ledger.Move("Ruledco", "CONFIRMED_LENDER_ALIASES", "confirmed_lender", "alternative_position", 0,
                           "Ruledco", "fabricated owner ruling, an alternative position."),
        lender_ledger.Move("Westfen Leasing", "LEASE_PROVIDER_ALIASES", "lease_or_equipment_financing",
                           "lease_or_rental", 0, "Westfen Leasing", ""),
    ]


#: Entity 0 holding the aliases of a fabricated entity of today's registry that the owner merged into it.
ABSORBED = (0, "aliases", ["QUILLON FUNDING", "QUILLONFUND", "QUILLON HOLDINGS", "QUILLON HLDG"])


def _merged(**changes):
    """RULES whose today's registry also holds 'Quillon Holdings', which the owner merged into 'Quillon Funding'."""
    baseline = {**BASELINE, "CONFIRMED_LENDER_ALIASES": {
        **BASELINE["CONFIRMED_LENDER_ALIASES"], "Quillon Holdings": ("QUILLON HOLDINGS", "QUILLON HLDG")}}
    return dataclasses.replace(RULES, **{"baseline": baseline, "merged": {"Quillon Holdings": "Quillon Funding"},
                                         **changes})


def test_a_merged_entity_of_todays_registry_is_held_by_its_target_under_the_targets_name():
    assert _problems(ABSORBED, rules=_merged()) == []
    assert _problems(ABSORBED, rules=_merged(merged={})) == [
        "the ledger entity holding the first alias of today's 'Quillon Holdings' is named 'Quillon Funding': keep "
        "today's name (S2's pins and the census compare entity names)"
    ]


def test_the_aliases_a_merge_loses_need_the_targets_move_sentence():
    assert _problems(rules=_merged()) == [
        "today's CONFIRMED_LENDER_ALIASES entity 'Quillon Holdings' loses 2 of today's aliases without a sentence "
        "starting 'Move:' in the notes of 'Quillon Funding', which absorbs it"
    ]
    assert _problems((0, "notes", "Move: fabricated merger; the holding company's names print on no row."),
                     rules=_merged()) == []


def test_baseline_moves_list_a_merge_even_when_it_loses_nothing():
    rules = _merged()
    moves, missing = lender_ledger.baseline_moves(_entities(ABSORBED), rules.baseline, rules.merged)
    assert missing == []
    assert moves == [
        lender_ledger.Move("Ruledco", "CONFIRMED_LENDER_ALIASES", "confirmed_lender", "alternative_position", 0,
                           "Ruledco", "fabricated owner ruling, an alternative position."),
        lender_ledger.Move("Quillon Holdings", "CONFIRMED_LENDER_ALIASES", "confirmed_lender", "confirmed_lender", 0,
                           "Quillon Funding", "", merged=True),
        lender_ledger.Move("Westfen Leasing", "LEASE_PROVIDER_ALIASES", "lease_or_equipment_financing",
                           "lease_or_rental", 0, "Westfen Leasing", ""),
    ]


@pytest.mark.parametrize("merged,problems", [
    ({"Septima Holdings": "Quillon Funding"},
     ["MERGED_REGISTRY_ENTITIES merges 'Septima Holdings', which is not an entity of today's registry"]),
    ({"Heldco Advance": "Heldco Capital"},
     ["MERGED_REGISTRY_ENTITIES merges 'Heldco Advance' into 'Heldco Capital', which is not a ledger entity",
      "MERGED_REGISTRY_ENTITIES merges 'Heldco Advance' into 'Heldco Capital', but entity 15 ('Heldco Advance') "
      "still renders under the merged name"]),
    ({"Heldco Advance": "Quillon Funding"},
     ["MERGED_REGISTRY_ENTITIES merges 'Heldco Advance' into 'Quillon Funding', but entity 15 ('Heldco Advance') "
      "still renders under the merged name",
      "today's POTENTIAL_LENDER_ALIASES entity 'Heldco Advance' moves from potential_lender to confirmed_lender "
      "without a sentence starting 'Move:' in the notes of 'Quillon Funding', which absorbs it",
      "today's POTENTIAL_LENDER_ALIASES entity 'Heldco Advance' loses 1 of today's aliases without a sentence "
      "starting 'Move:' in the notes of 'Quillon Funding', which absorbs it"]),
])
def test_a_merge_names_an_entity_of_todays_registry_that_a_ledger_entity_absorbs(merged, problems):
    assert _problems(rules=dataclasses.replace(RULES, merged=merged)) == problems


def test_no_merge_problem_quotes_a_run_of_five_or_more_digits():
    assert _problems(rules=dataclasses.replace(RULES, merged={"Septima 7777777": "Tarnmoor 4444444 Capital"})) == [
        f"MERGED_REGISTRY_ENTITIES merges {WITHHELD}, which is not an entity of today's registry",
        f"MERGED_REGISTRY_ENTITIES merges {WITHHELD} into {WITHHELD}, which is not a ledger entity",
    ]


def _reattributed(**changes):
    """RULES whose today's lease list also holds 'Pellam', whose first alias the owner gave to 'Pellam Solutions'."""
    return dataclasses.replace(RULES, **{"baseline": PELLAM_BASELINE,
                                         "reattributed": {"PELLAM SOL": "Pellam Solutions"}, **changes})


def test_an_alias_the_owner_reattributed_is_held_by_its_company_and_todays_entity_keeps_its_name():
    assert lender_ledger.validate(pellam_ledger(), _reattributed()) == []
    assert lender_ledger.validate(pellam_ledger(), _reattributed(reattributed={})) == [
        "the ledger entity holding the first alias of today's 'Pellam' is named 'Pellam Solutions': keep today's "
        "name (S2's pins and the census compare entity names)",
        "today's LEASE_PROVIDER_ALIASES entity 'Pellam' moves from lease_or_equipment_financing to no table without "
        "a sentence starting 'Move:' in its notes",
        "today's LEASE_PROVIDER_ALIASES entity 'Pellam' loses 2 of today's aliases without a sentence starting "
        "'Move:' in its notes",
    ]


def test_the_aliases_an_entity_loses_beside_a_reattribution_need_its_move_sentence():
    assert lender_ledger.validate(pellam_ledger(notes="Fabricated: a lease-to-own company."), _reattributed()) == [
        "today's LEASE_PROVIDER_ALIASES entity 'Pellam' loses 1 of today's aliases without a sentence starting "
        "'Move:' in its notes"
    ]


SOLWAY = entity("Solway Advance", "confirmed_lender", ["SOL"], status="review", short_alias_reason="fabricated",
                evidence=[], verdicts=UNRESOLVED, notes="Fabricated: identity unconfirmed.")


@pytest.mark.parametrize("data,problem", [
    (pellam_ledger(aliases=["PELLAM LEASING", "PELLAM"]),
     "REATTRIBUTED_REGISTRY_ALIASES reattributes 'PELLAM SOL' to 'Pellam Solutions', but the registry reads it as "
     "'Pellam' (lease_or_rental)"),
    (pellam_ledger(extra=[SOLWAY]),
     "REATTRIBUTED_REGISTRY_ALIASES reattributes 'PELLAM SOL' to 'Pellam Solutions', but the registry reads it as "
     "'Solway Advance' (potential_lender)"),
])
def test_the_registry_reads_a_reattributed_alias_as_its_company_or_not_at_all(data, problem):
    assert lender_ledger.validate(data, _reattributed()) == [problem]


def test_a_reattributed_alias_may_render_under_its_company():
    data = pellam_ledger()
    data["entities"][19].update(status="review", group="confirmed_lender")
    assert lender_ledger.validate(data, _reattributed()) == []


@pytest.mark.parametrize("reattributed,problems", [
    ({"QUILLON FUNDING": "Quillon Funding"},
     ["REATTRIBUTED_REGISTRY_ALIASES reattributes 'QUILLON FUNDING', which is not an alias of today's registry"]),
    ({"OLDCO": "Oldco Bakery"},
     ["REATTRIBUTED_REGISTRY_ALIASES reattributes 'OLDCO' to 'Oldco Bakery', which is not a ledger entity"]),
    ({"OLDCO": "Tarnmoor Capital"},
     ["REATTRIBUTED_REGISTRY_ALIASES reattributes 'OLDCO' to 'Tarnmoor Capital', but 'Tarnmoor Capital' does not "
      "hold it",
      "REATTRIBUTED_REGISTRY_ALIASES reattributes 'OLDCO' to 'Tarnmoor Capital', but the registry reads it as "
      "'Oldco Funding' (confirmed_lender)"]),
])
def test_a_reattribution_names_an_alias_of_todays_registry_and_the_ledger_entity_that_holds_it(reattributed,
                                                                                              problems):
    assert _problems(rules=dataclasses.replace(RULES, reattributed=reattributed)) == problems


def test_no_reattribution_problem_quotes_a_run_of_five_or_more_digits():
    rules = dataclasses.replace(RULES, reattributed={"OLDCO 7777777": "Tarnmoor 4444444 Capital"})
    assert _problems(rules=rules) == [
        f"REATTRIBUTED_REGISTRY_ALIASES reattributes {WITHHELD}, which is not an alias of today's registry",
        f"REATTRIBUTED_REGISTRY_ALIASES reattributes {WITHHELD} to {WITHHELD}, which is not a ledger entity",
    ]


#: Entity 1 without the alias OLDCO, which the owner gave to a fabricated bakery (entity 18, rejected).
OLDCO_BAKERY = entity("Oldco Bakery", "potential_lender", ["OLDCO"], status="rejected", business_type="bakery",
                      evidence=[], verdicts=UNRESOLVED, notes="Fabricated: a bakery, not a funder.")


def _bakery_ledger():
    data = ledger((1, "aliases", ["OLDCO FUNDING"]))
    data["entities"].append(OLDCO_BAKERY)
    return data


def test_baseline_moves_show_a_reattributed_alias_beside_todays_entity_and_never_count_it_lost():
    rules = _reattributed()
    entities, problems = lender_ledger.parse_ledger(pellam_ledger())
    assert problems == []
    moves, missing = lender_ledger.baseline_moves(entities, rules.baseline, rules.merged, rules.reattributed)
    assert missing == []
    assert moves[-1] == lender_ledger.Move(
        "Pellam", "LEASE_PROVIDER_ALIASES", "lease_or_equipment_financing", "lease_or_rental", 1, "Pellam",
        "bare PELLAM names other companies.", reattributed=(("PELLAM SOL", "Pellam Solutions"),))


def test_a_reattribution_alone_is_a_move_that_needs_no_reason():
    rules = dataclasses.replace(RULES, reattributed={"OLDCO": "Oldco Bakery"})
    assert lender_ledger.validate(_bakery_ledger(), rules) == []
    assert lender_ledger.validate(_bakery_ledger(), RULES) == [
        "today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' loses 1 of today's aliases without a sentence "
        "starting 'Move:' in its notes"
    ]
    entities, _problems = lender_ledger.parse_ledger(_bakery_ledger())
    moves, _missing = lender_ledger.baseline_moves(entities, rules.baseline, rules.merged, rules.reattributed)
    assert moves[0] == lender_ledger.Move("Oldco Funding", "CONFIRMED_LENDER_ALIASES", "confirmed_lender",
                                          "confirmed_lender", 0, "Oldco Funding", "",
                                          reattributed=(("OLDCO", "Oldco Bakery"),))


def test_the_baseline_is_read_from_a_registry_source_without_importing_it():
    source = "".join(f"{table}: dict[str, tuple[str, ...]] = {entries!r}\n" for table, entries in BASELINE.items())
    assert lender_ledger.baseline_from_source("OTHER = 1\n" + source) == BASELINE
    with pytest.raises(ValueError, match="LEASE_PROVIDER_ALIASES"):
        lender_ledger.baseline_from_source("CONFIRMED_LENDER_ALIASES = {}\nPOTENTIAL_LENDER_ALIASES = {}\n")


def test_the_baseline_revision_holds_the_lists_the_classifier_reads_until_s2():
    from analysis import classification_registry as registry

    legacy = {
        "CONFIRMED_LENDER_ALIASES": getattr(registry, "LEGACY_CONFIRMED_LENDER_ALIASES", None),
        "POTENTIAL_LENDER_ALIASES": getattr(registry, "LEGACY_POTENTIAL_LENDER_ALIASES", None),
        "LEASE_PROVIDER_ALIASES": getattr(registry, "LEASE_PROVIDER_ALIASES", None),
    }
    baseline = lender_ledger.load_baseline()
    assert list(baseline) == list(lender_ledger.BASELINE_TABLES)
    if any(table is None for table in legacy.values()):
        pytest.skip("S2 removed the legacy lists; the baseline revision stays the validator's frozen input")
    for name, table in legacy.items():
        assert baseline[name] == table, name


def test_the_ledger_digest_ignores_formatting():
    data = ledger()
    assert lender_ledger.ledger_digest(data) == lender_ledger.ledger_digest(
        {"entities": data["entities"], "schema": 1})
    assert len(lender_ledger.ledger_digest(data)) == 64
    assert lender_ledger.ledger_digest(data) != lender_ledger.ledger_digest(ledger((0, "notes", "changed")))
```

- [ ] **Step 3: Run it to verify it fails**

Run: `C:\Python314\python.exe -m pytest tests/test_lender_ledger.py -q -p no:cacheprovider`
Expected: 1 error during collection: `ModuleNotFoundError: No module named 'tools.lender_ledger'`.

- [ ] **Step 4: Write the module**

Create `tools/lender_ledger.py`:

```python
"""The curated lender registry ledger (contract C10): its schema, its validator and its privacy review.

The lender research is consolidated into one entity per company OUTSIDE the code, by the orchestrator's
research workflow (consolidation, an adversarial check per entity, a completeness critic), and committed as
``docs/lender-registry-ledger.json``. This module never infers a name, a group or an alias from research
output. It reads the ledger and says what is wrong with it; ``tools/build_lender_registry.py`` renders the
registry and the evidence ledger from a ledger that passes.

The validator applies:
  * every rule contract C10 lists;
  * spec section 5's brand rule (a brand that also sells goods is an alias only with payment or loan wording);
  * the privacy constraints: no digit run of five or more outside a URL, unless today's registry already
    holds that alias; sources and "where looked" entries are public URLs without a query string, credentials
    or a local, private or undotted host;
  * contract C2's context-only tables: no entity of the card, card-issuer, bank-name or premium-finance
    groups is under review, and every card-payment alias carries card or payment wording;
  * the owner's premium-finance ruling: a premium-finance alias repeats a hand-kept insurer's alias only when
    PREMIUM_FINANCE_INSURER_ALIASES holds it;
  * the owner's payout-credit ruling: each name in PAYOUT_CREDIT_ENTITIES is an admitted ledger entity of a
    group whose credits D1 treats as financing proceeds (analysis.flag_groups.FINANCING_STATES);
  * spec section 9's rule that an entity of today's registry changes place, or loses an alias, only with a
    reason: a sentence of its notes that starts "Move:" (today's registry is read from git at
    BASELINE_REVISION); an entity the owner merged into a ledger entity (MERGED_REGISTRY_ENTITIES) is held by
    that entity, whose notes give the reason; an alias the owner ruled names another company
    (REATTRIBUTED_REGISTRY_ALIASES) is held by that company's ledger entity, the only entity the registry may read
    it as, and is neither lost nor the first alias of today's entity.
"""
from __future__ import annotations

import ast
import hashlib
import ipaddress
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.description_text import normalize_transaction_description as normalize  # noqa: E402
from analysis.flag_groups import FINANCING_STATES  # noqa: E402
from analysis.payee_matcher import RUN_TOGETHER_MIN_LENGTH, AliasIndex, registry_match  # noqa: E402

SCHEMA = 1
LEDGER_PATH = ROOT / "docs" / "lender-registry-ledger.json"
EMPTY_LEDGER: dict = {"schema": SCHEMA, "entities": []}

#: (group, table, heading): the ledger's groups, the contract C2 table each renders into, and the heading
#: the GENERATED block and the evidence ledger print, in their order.
TABLES: tuple[tuple[str, str, str], ...] = (
    ("confirmed_lender", "LENDER_ALIASES", "Lenders: MCA and revenue-based funders, equipment financing"),
    ("alternative_position", "ALTERNATIVE_POSITION_ALIASES", "Alternative positions"),
    ("line_of_credit", "LINE_OF_CREDIT_ALIASES", "Lines of credit"),
    ("credit_card_payment", "CARD_ISSUER_ALIASES", "Credit cards: aliases that carry card-payment wording"),
    ("card_issuer_context", "CARD_ISSUER_CONTEXT_ALIASES",
     "Card issuers: bare names, used only with card-payment wording"),
    ("vehicle_financing", "VEHICLE_FINANCE_ALIASES", "Vehicle loans & leases"),
    ("mortgage", "MORTGAGE_SERVICER_ALIASES", "Mortgages"),
    ("lease_or_rental", "LEASE_RENTAL_ALIASES", "Leases & rentals"),
    ("personal_loan", "PERSONAL_LOAN_ALIASES", "Personal loans"),
    ("floor_plan_financing", "FLOOR_PLAN_ALIASES", "Floor plan"),
    ("factoring", "FACTORING_ALIASES", "Factoring"),
    ("premium_financing", "PREMIUM_FINANCE_ALIASES",
     "Premium financing: premium-finance payees, read only by the insurance rule"),
    ("bank_name", "BANK_NAME_ALIASES", "Bank names: bank loans (D5)"),
    ("potential_lender", "POTENTIAL_LENDER_ALIASES", "Potential lenders: review, never counted"),
)
GROUPS = tuple(group for group, _table, _heading in TABLES)
TABLE_OF_GROUP = {group: table for group, table, _heading in TABLES}
#: The known-payee matcher's registries, in contract C2's PAYEE_GROUP_REGISTRIES order.
PAYEE_STATES = (
    "confirmed_lender", "alternative_position", "line_of_credit", "vehicle_financing", "mortgage",
    "personal_loan", "floor_plan_financing", "factoring", "lease_or_rental", "credit_card_payment",
)
STATUSES = ("admitted", "review", "owner_ruling", "rejected")
#: The statuses rendered into a table: admitted into its group's table, review into the potential table.
RENDERED = frozenset({"admitted", "review"})
ADMITTING_VERDICTS = frozenset({"upheld", "corrected"})
FIELDS = ("entity", "group", "business_type", "aliases", "status", "short_alias_reason", "evidence",
          "verdicts", "where_looked", "notes")
_ALIAS_CHARACTERS = re.compile(r"[A-Z0-9 &]+")
#: An alias of this many characters or fewer (spaces not counted) needs the entity's short_alias_reason.
SHORT_ALIAS = 4
#: C10: an alias made only of these words names no company.
GENERIC_WORDS = frozenset("""
ACH ADVANCE ADVANCES AND AUTO BANK BUSINESS CAPITAL CARD CO COMPANY CORP CORPORATION CREDIT DEBIT EQUIPMENT
FINANCE FINANCIAL FINANCING FUND FUNDING FUNDS GROUP HOLDINGS INC INSURANCE LEASE LEASING LENDER LENDING LLC
LOAN LOANS LTD MCA MERCHANT MORTGAGE OF PAYMENT PAYMENTS PMT SERVICES SERVICING SOLUTIONS THE
""".split())
#: Words that make a name an organisation's name. A name without one is read by a person before a commit.
ORG_CUES = frozenset("""
ACCEPTANCE ADVANCE BANK CAPITAL CO CORP CORPORATION CREDIT FACTORING FINANCE FINANCIAL FUND FUNDING GROUP
HOLDINGS INC LEASING LENDING LLC LOANS LTD MORTGAGE PARTNERS SERVICES SERVICING VENTURES
""".split())
_LONG_DIGITS = re.compile(r"\d{5,}")
#: What a message or a printed line shows in place of a run of five or more digits: the validator's messages,
#: the move lines and the privacy review never quote such a run (the numbered company's number).
WITHHELD = "(withheld: a run of digits)"
_URL_SCHEME = re.compile(r"https?://")
#: The groups whose tables the classifier reads only with context: card or payment wording, loan wording, or
#: the insurance rule. None of their entities is ever "review", because the potential tier (where C10 renders
#: every review entity) reads its aliases with no context at all.
CONTEXT_ONLY_GROUPS = frozenset({"credit_card_payment", "card_issuer_context", "bank_name", "premium_financing"})
#: The hand-kept insurer table. A premium-finance alias may repeat one of its aliases only on the owner's
#: ruling (``Rules.premium_insurer_aliases``, PREMIUM_FINANCE_INSURER_ALIASES).
INSURER_TABLE = "INSURANCE_PROVIDER_ALIASES"
#: The wording of S2's card-payment rule (spec section 4.3 step 8). C10: the aliases of credit_card_payment are
#: "already payment-specific", so each carries this wording; a bare issuer name belongs in card_issuer_context.
_CARD_PAYMENT_WORDING = re.compile(
    r"\b(?:CREDIT CARD|CRCARD|CRD|CARD|CARDMEMBER|AUTOPAY|AUTO PAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT)\b"
)
#: Spec section 9: the reason for a move from today's registry is a sentence of the ledger entity's notes that
#: starts with this marker. Any other text in notes never excuses a move.
MOVE_MARKER = "Move:"
_MOVE_REASON = re.compile(r"(?:^|(?<=[.!?;])\s+)" + re.escape(MOVE_MARKER) + r"\s*(\S.*)", re.DOTALL)
#: The last commit that changed today's registry. Today's three lists are read from git at this revision, so
#: the check survives S2 deleting the legacy lists and no second copy of them is ever committed.
BASELINE_REVISION = "693fd009c5c96a838ef47b61ba5b65a610ea5ba1"
BASELINE_TABLES = ("CONFIRMED_LENDER_ALIASES", "POTENTIAL_LENDER_ALIASES", "LEASE_PROVIDER_ALIASES")
#: The classification state each of today's lists gives its rows (spec section 4.1 retires the lease state).
BASELINE_STATE = {
    "CONFIRMED_LENDER_ALIASES": "confirmed_lender",
    "POTENTIAL_LENDER_ALIASES": "potential_lender",
    "LEASE_PROVIDER_ALIASES": "lease_or_equipment_financing",
}
#: The places an entity of today's lists may take without a reason: its own place, or, for the retired
#: lease state, the ones spec section 4.1 names.
UNRULED_PLACES = {
    "CONFIRMED_LENDER_ALIASES": frozenset({"confirmed_lender"}),
    "POTENTIAL_LENDER_ALIASES": frozenset({"potential_lender"}),
    "LEASE_PROVIDER_ALIASES": frozenset({"confirmed_lender", "lease_or_rental", "vehicle_financing"}),
}


@dataclass(frozen=True)
class Evidence:
    source: str
    note: str


@dataclass(frozen=True)
class Verdict:
    round: str
    verdict: str
    confirmed: bool


@dataclass(frozen=True)
class LedgerEntity:
    index: int
    entity: str
    group: str
    business_type: str
    aliases: tuple[str, ...]
    status: str
    short_alias_reason: str | None
    evidence: tuple[Evidence, ...]
    verdicts: tuple[Verdict, ...]
    where_looked: tuple[str, ...]
    notes: str

    @property
    def table(self) -> str | None:
        """The C2 table the entity renders into, or None."""
        if self.status == "admitted":
            return TABLE_OF_GROUP[self.group]
        if self.status == "review":
            return TABLE_OF_GROUP["potential_lender"]
        return None

    @property
    def place(self) -> str:
        """Where the entity's rows go: its group, "potential_lender" for review, or "no table"."""
        if self.status == "admitted":
            return self.group
        if self.status == "review":
            return "potential_lender"
        return "no table"


@dataclass(frozen=True)
class Rules:
    """The hand-kept inputs of the validator, all read from ``analysis/classification_registry.py``."""

    owner_named: Mapping[str, tuple[tuple[str, str], ...]]
    platforms: frozenset[str]
    brands: frozenset[str]
    hand_kept: Mapping[str, Mapping[str, tuple[str, ...]]]
    baseline: Mapping[str, Mapping[str, tuple[str, ...]]]
    #: Normalized premium-finance spellings that may equal a hand-kept insurer alias (owner ruling).
    premium_insurer_aliases: frozenset[str]
    #: Entity of today's registry -> the ledger entity that absorbs it (owner ruling).
    merged: Mapping[str, str]
    #: Ledger entities whose credits are the account holder's own sales, not financing proceeds (owner ruling).
    payout_credit: tuple[str, ...]
    #: Alias of today's registry -> the ledger entity of the other company it names (owner ruling).
    reattributed: Mapping[str, str]


@dataclass(frozen=True)
class Move:
    """An entity of today's registry whose place or aliases the ledger changes, that the owner merged into
    ``holder``, or an alias of which the owner gave to another company (``reattributed``: (alias, ledger entity)
    pairs). ``reason`` is the text of the holder's "Move:" sentence, or "" when its notes have none."""

    entity: str
    table: str
    was: str
    now: str
    lost: int
    holder: str
    reason: str
    merged: bool = False
    reattributed: tuple[tuple[str, str], ...] = ()


# --- reading -------------------------------------------------------------------------------------------------


def read_ledger(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def ledger_digest(data: object) -> str:
    """sha256 of the ledger's canonical JSON: the same on every checkout, whatever its line endings."""
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def mask_digit_runs(text: str) -> str:
    """``text`` with every run of five or more digits replaced by WITHHELD."""
    return _LONG_DIGITS.sub(WITHHELD, text)


def _shown(value: object) -> str:
    """The repr of a name or a value for a message, or WITHHELD when it carries a run of five or more digits."""
    text = repr(value)
    return WITHHELD if _LONG_DIGITS.search(text) else text


def _public_url(text: str) -> bool:
    """An http(s) URL without whitespace, a query string, a fragment, a '|' (it would split an evidence-ledger
    row) or credentials (userinfo), on a public host: a global IP address, or a dotted name that is not
    localhost and whose last label starts with a letter (so no private, loopback, undotted or numeric host)."""
    if not _URL_SCHEME.match(text) or any(char.isspace() or char in "?#|" for char in text):
        return False
    try:
        parts = urlsplit(text)
        host, _port = parts.hostname, parts.port
    except ValueError:
        return False
    if not host or "@" in parts.netloc:
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    labels = host.split(".")
    return len(labels) >= 2 and all(labels) and labels[-1] != "localhost" and labels[-1][0].isalpha()


def _texts(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _filled(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _shape_problems(index: int, record: object) -> list[str]:
    where = f"entity {index}"
    if not isinstance(record, dict):
        return [f"{where} is not an object"]
    missing = [name for name in FIELDS if name not in record]
    unknown = sorted(set(record) - set(FIELDS))
    problems = []
    if missing:
        problems.append(f"{where}: missing field(s) {', '.join(missing)}")
    if unknown:
        problems.append(f"{where}: unknown field(s) {mask_digit_runs(', '.join(unknown))}")
    if problems:
        return problems
    checks = (
        (_filled(record["entity"]), "entity is not a non-empty string"),
        (record["group"] in GROUPS, f"group {_shown(record['group'])} is not a C10 group"),
        (_filled(record["business_type"]), "business_type is not a non-empty string"),
        (_texts(record["aliases"]), "aliases is not a list of strings"),
        (record["status"] in STATUSES, f"status {_shown(record['status'])} is not one of {', '.join(STATUSES)}"),
        (record["short_alias_reason"] is None or _filled(record["short_alias_reason"]),
         "short_alias_reason is neither null nor a non-empty string"),
        (isinstance(record["evidence"], list), "evidence is not a list"),
        (isinstance(record["verdicts"], list), "verdicts is not a list"),
        (_texts(record["where_looked"]), "where_looked is not a list of strings"),
        (isinstance(record["notes"], str), "notes is not a string"),
    )
    problems = [f"{where}: {message}" for ok, message in checks if not ok]
    for number, item in enumerate(record["evidence"] if isinstance(record["evidence"], list) else []):
        if not (isinstance(item, dict) and set(item) == {"source", "note"}
                and all(isinstance(value, str) for value in item.values())):
            problems.append(f"{where}: evidence {number} is not an object of the strings 'source' and 'note'")
    for number, item in enumerate(record["verdicts"] if isinstance(record["verdicts"], list) else []):
        if not (isinstance(item, dict) and set(item) == {"round", "verdict", "confirmed"}
                and isinstance(item["round"], str) and isinstance(item["verdict"], str)
                and isinstance(item["confirmed"], bool)):
            problems.append(f"{where}: verdict {number} is not an object of the strings 'round' and 'verdict' "
                            f"and a true/false 'confirmed'")
    return problems


def parse_ledger(data: object) -> tuple[list[LedgerEntity], list[str]]:
    """The ledger's entities, or the problems with its shape (C10's schema)."""
    if not isinstance(data, dict) or set(data) != {"schema", "entities"}:
        return [], ["the ledger is not an object with exactly the keys 'schema' and 'entities'"]
    if data["schema"] is True or data["schema"] != SCHEMA:
        return [], [f"the ledger schema is {_shown(data['schema'])}; this validator reads schema {SCHEMA}"]
    if not isinstance(data["entities"], list):
        return [], ["the ledger's 'entities' is not a list"]
    entities: list[LedgerEntity] = []
    problems: list[str] = []
    for index, record in enumerate(data["entities"]):
        found = _shape_problems(index, record)
        if found:
            problems.extend(found)
            continue
        entities.append(LedgerEntity(
            index=index,
            entity=record["entity"],
            group=record["group"],
            business_type=record["business_type"],
            aliases=tuple(record["aliases"]),
            status=record["status"],
            short_alias_reason=record["short_alias_reason"],
            evidence=tuple(Evidence(item["source"], item["note"]) for item in record["evidence"]),
            verdicts=tuple(Verdict(item["round"], item["verdict"], item["confirmed"]) for item in record["verdicts"]),
            where_looked=tuple(record["where_looked"]),
            notes=record["notes"],
        ))
    return entities, problems


def render_tables(entities: list[LedgerEntity]) -> dict[str, dict[str, tuple[str, ...]]]:
    """Every C2 table, in TABLES order: entities in name order, aliases in ledger order."""
    tables: dict[str, dict[str, tuple[str, ...]]] = {table: {} for _group, table, _heading in TABLES}
    for entity in sorted(entities, key=lambda e: (e.entity.casefold(), e.entity)):
        if entity.table is not None:
            tables[entity.table][entity.entity] = tuple(dict.fromkeys(entity.aliases))
    return tables


# --- today's registry (spec section 9) ------------------------------------------------------------------------


def baseline_from_source(source: str) -> dict[str, dict[str, tuple[str, ...]]]:
    """Today's three lists (BASELINE_TABLES) from a registry source, read without importing it."""
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            name, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        else:
            continue
        if name in BASELINE_TABLES:
            found[name] = ast.literal_eval(value)
    missing = [name for name in BASELINE_TABLES if name not in found]
    if missing:
        raise ValueError(f"the baseline source has no {', '.join(missing)}")
    return {name: {entity: tuple(aliases) for entity, aliases in found[name].items()} for name in BASELINE_TABLES}


def load_baseline(revision: str = BASELINE_REVISION) -> dict[str, dict[str, tuple[str, ...]]]:
    """Today's registry as it stood at ``revision``, read from git."""
    shown = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{revision}:analysis/classification_registry.py"],
        check=True, capture_output=True,
    )
    return baseline_from_source(shown.stdout.decode("utf-8"))


def move_reason(notes: str) -> str:
    """The reason the ledger records for a move from today's registry: the text after the first sentence of
    ``notes`` that starts with MOVE_MARKER, or "" when no sentence does."""
    found = _MOVE_REASON.search(notes)
    return found.group(1).strip() if found else ""


def _holders(entities: list[LedgerEntity]) -> dict[str, LedgerEntity]:
    held: dict[str, LedgerEntity] = {}
    for entity in entities:
        for alias in entity.aliases:
            held.setdefault(normalize(alias), entity)
    return held


def _by_name(entities: list[LedgerEntity]) -> dict[str, LedgerEntity]:
    """Each entity name's first ledger entity (a name used twice is refused by the name rules)."""
    named: dict[str, LedgerEntity] = {}
    for entity in entities:
        named.setdefault(entity.entity, entity)
    return named


def baseline_moves(entities: list[LedgerEntity], baseline: Mapping[str, Mapping[str, tuple[str, ...]]],
                   merged: Mapping[str, str] | None = None,
                   reattributed: Mapping[str, str] | None = None) -> tuple[list[Move], list[tuple[str, str]]]:
    """(moves, missing). A move is an entity of today's lists whose place changes or that loses an alias; the
    ledger entity holding its first alias (else most of its aliases, else its name) decides. An entity the owner
    merged (``merged``, MERGED_REGISTRY_ENTITIES) is held by its target ledger entity instead, and is always a
    move. An alias the owner gave to another company (``reattributed``, REATTRIBUTED_REGISTRY_ALIASES) is left out
    of its entity's aliases: it decides nothing and is never lost, and its entity is always a move that shows it.
    Missing are the (table, entity) pairs of today's lists whose name and aliases no ledger entity holds."""
    merged = merged or {}
    given_to = {normalize(alias): target for alias, target in (reattributed or {}).items()}
    held = _holders(entities)
    named = _by_name(entities)
    moves: list[Move] = []
    missing: list[tuple[str, str]] = []
    for table in BASELINE_TABLES:
        for name, aliases in baseline.get(table, {}).items():
            normalized = list(dict.fromkeys(normalize(alias) for alias in aliases))
            given = tuple((alias, given_to[alias]) for alias in normalized if alias in given_to)
            own = [alias for alias in normalized if alias not in given_to]
            target = named.get(merged[name]) if name in merged else None
            holders = [held[alias] for alias in own if alias in held]
            if target is not None:
                primary = target
            elif holders:
                primary = held.get(own[0]) or max(holders, key=lambda e: (holders.count(e), -e.index))
            elif name in named:
                primary = named[name]
            else:
                missing.append((table, name))
                continue
            kept = {normalize(alias) for alias in primary.aliases} if primary.status in RENDERED else set()
            lost = sum(1 for alias in own if alias not in kept)
            move = Move(name, table, BASELINE_STATE[table], primary.place, lost, primary.entity,
                        move_reason(primary.notes), merged=target is not None, reattributed=given)
            if move.merged or move.reattributed or move.now != move.was or move.lost:
                moves.append(move)
    return moves, missing


def _merge_problems(entities: list[LedgerEntity], baseline: Mapping[str, Mapping[str, tuple[str, ...]]],
                    merged: Mapping[str, str]) -> list[str]:
    """MERGED_REGISTRY_ENTITIES names an entity of today's lists, merged into a ledger entity; no rendered ledger
    entity keeps the merged name."""
    today = {name for table in BASELINE_TABLES for name in baseline.get(table, {})}
    named = _by_name(entities)
    problems = []
    for name, target in merged.items():
        if name not in today:
            problems.append(f"MERGED_REGISTRY_ENTITIES merges {_shown(name)}, which is not an entity of today's "
                            f"registry")
        if target not in named:
            problems.append(f"MERGED_REGISTRY_ENTITIES merges {_shown(name)} into {_shown(target)}, which is not a "
                            f"ledger entity")
        kept = named.get(name)
        if kept is not None and kept.status in RENDERED:
            problems.append(f"MERGED_REGISTRY_ENTITIES merges {_shown(name)} into {_shown(target)}, but "
                            f"{_label(kept)} still renders under the merged name")
    return problems


def _reattribution_problems(entities: list[LedgerEntity], baseline: Mapping[str, Mapping[str, tuple[str, ...]]],
                            reattributed: Mapping[str, str]) -> list[str]:
    """REATTRIBUTED_REGISTRY_ALIASES names an alias of today's lists and the ledger entity that holds it, and the
    rendered registry reads that alias, without context, as that entity or not at all: the known-payee matcher
    (C3), else the potential table."""
    today = {normalize(alias) for table in BASELINE_TABLES for aliases in baseline.get(table, {}).values()
             for alias in aliases}
    held = _holders(entities)
    named = _by_name(entities)
    tables = render_tables(entities)
    index = AliasIndex({state: tables[TABLE_OF_GROUP[state]] for state in PAYEE_STATES})
    problems = []
    for alias, target in reattributed.items():
        norm = normalize(alias)
        if norm not in today:
            problems.append(f"REATTRIBUTED_REGISTRY_ALIASES reattributes {_shown(alias)}, which is not an alias of "
                            f"today's registry")
        if target not in named:
            problems.append(f"REATTRIBUTED_REGISTRY_ALIASES reattributes {_shown(alias)} to {_shown(target)}, which "
                            f"is not a ledger entity")
            continue
        if held.get(norm) is not named[target]:
            problems.append(f"REATTRIBUTED_REGISTRY_ALIASES reattributes {_shown(alias)} to {_shown(target)}, but "
                            f"{_shown(target)} does not hold it")
        payee = index.match(norm)
        potential = registry_match(norm, tables[TABLE_OF_GROUP["potential_lender"]])
        if payee is not None:
            reader = (payee.entity, payee.state)
        elif potential is not None:
            reader = (potential[0], "potential_lender")
        else:
            continue
        if reader[0] != target:
            problems.append(f"REATTRIBUTED_REGISTRY_ALIASES reattributes {_shown(alias)} to {_shown(target)}, but the "
                            f"registry reads it as {_shown(reader[0])} ({reader[1]})")
    return problems


def baseline_problems(entities: list[LedgerEntity], baseline: Mapping[str, Mapping[str, tuple[str, ...]]],
                      merged: Mapping[str, str] | None = None,
                      reattributed: Mapping[str, str] | None = None) -> list[str]:
    merged, reattributed = merged or {}, reattributed or {}
    moves, missing = baseline_moves(entities, baseline, merged, reattributed)
    marked = f"a sentence starting {MOVE_MARKER!r} in its notes"
    problems = _merge_problems(entities, baseline, merged)
    problems += _reattribution_problems(entities, baseline, reattributed)
    problems += [f"today's {table} entity {_shown(name)} is in no ledger entity: record it in its place, or "
                 f"moved or rejected with {marked}" for table, name in missing]
    held = _holders(entities)
    given = {normalize(alias) for alias in reattributed}
    for table in BASELINE_TABLES:
        for name, aliases in baseline.get(table, {}).items():
            own = [alias for alias in aliases if normalize(alias) not in given]
            first = held.get(normalize(own[0])) if own else None
            if name not in merged and first is not None and first.entity != name:
                problems.append(f"the ledger entity holding the first alias of today's {_shown(name)} is named "
                                f"{_shown(first.entity)}: keep today's name (S2's pins and the census compare "
                                f"entity names)")
    for move in moves:
        if move.reason:
            continue
        needs = (f"a sentence starting {MOVE_MARKER!r} in the notes of {_shown(move.holder)}, which absorbs it"
                 if move.merged else marked)
        if move.now not in UNRULED_PLACES[move.table]:
            problems.append(f"today's {move.table} entity {_shown(move.entity)} moves from {move.was} to "
                            f"{move.now} without {needs}")
        if move.lost:
            problems.append(f"today's {move.table} entity {_shown(move.entity)} loses {move.lost} of today's "
                            f"aliases without {needs}")
    return problems


# --- the rules ------------------------------------------------------------------------------------------------


def _label(entity: LedgerEntity) -> str:
    if _LONG_DIGITS.search(entity.entity):
        return f"entity {entity.index}"
    return f"entity {entity.index} ({entity.entity!r})"


def _alias_problems(entity: LedgerEntity, alias: str, rules: Rules, held: frozenset[str]) -> list[str]:
    label, shown = _label(entity), _shown(alias)
    if not alias:
        return [f"{label}: an alias is empty"]
    if "#" in alias:
        return [f"{label}: alias {shown} is masked ('#')"]
    if alias != alias.upper():
        return [f"{label}: alias {shown} has lowercase letters"]
    if not _ALIAS_CHARACTERS.fullmatch(alias):
        return [f"{label}: alias {shown} has characters outside A-Z, 0-9, space and '&'"]
    if alias != " ".join(alias.split()):
        return [f"{label}: alias {shown} has extra spaces"]
    problems = []
    if _LONG_DIGITS.search(alias) and alias not in held:
        problems.append(f"{label}: an alias carries a run of five or more digits that today's registry does not "
                        f"hold")
    if entity.status not in RENDERED:
        return problems
    norm = normalize(alias)
    if all(word in GENERIC_WORDS for word in norm.split(" ")):
        problems.append(f"{label}: alias {shown} is only generic words")
    if norm in rules.platforms:
        problems.append(f"{label}: alias {shown} is a bare platform name (spec section 5: the operating-revenue "
                        f"registry only)")
    for table, entries in rules.hand_kept.items():
        if table == INSURER_TABLE and entity.group == "premium_financing" and norm in rules.premium_insurer_aliases:
            continue  # the owner's ruling: this premium financier's rows print as the insurer
        for name, aliases in entries.items():
            if norm in {normalize(other) for other in aliases}:
                problems.append(f"{label}: alias {shown} is also an alias of the hand-kept {table} entity "
                                f"{_shown(name)}")
    if norm in rules.brands and entity.table not in (TABLE_OF_GROUP["card_issuer_context"],
                                                     TABLE_OF_GROUP["bank_name"]):
        problems.append(f"{label}: alias {shown} is a bare brand name; it belongs in card_issuer_context or "
                        f"bank_name (spec section 5)")
    if entity.table == TABLE_OF_GROUP["credit_card_payment"] and not _CARD_PAYMENT_WORDING.search(norm):
        problems.append(f"{label}: alias {shown} has no card or payment wording; a bare issuer name belongs in "
                        f"card_issuer_context (contract C10)")
    if len(alias.replace(" ", "")) <= SHORT_ALIAS and entity.short_alias_reason is None:
        problems.append(f"{label}: alias {shown} has {SHORT_ALIAS} characters or fewer and no short_alias_reason")
    return problems


def _entity_problems(entity: LedgerEntity, rules: Rules, held: frozenset[str]) -> list[str]:
    label = _label(entity)
    problems = []
    if entity.status == "admitted":
        if not entity.evidence:
            problems.append(f"{label} is admitted without evidence")
        if not any(v.verdict in ADMITTING_VERDICTS and v.confirmed for v in entity.verdicts):
            problems.append(f"{label} is admitted without an upheld or corrected verdict that confirms it")
    if entity.status in RENDERED and not entity.aliases:
        problems.append(f"{label} is {entity.status} but has no alias")
    if entity.status == "review" and entity.group in CONTEXT_ONLY_GROUPS:
        problems.append(f"{label} is review in {entity.group}, a table the classifier reads only with context, "
                        f"but the potential tier reads its aliases without that context: admit it, or record it "
                        f"as owner_ruling or rejected")
    for alias in entity.aliases:
        problems.extend(_alias_problems(entity, alias, rules, held))
    texts = [("entity", entity.entity), ("business_type", entity.business_type), ("notes", entity.notes),
             ("short_alias_reason", entity.short_alias_reason or "")]
    texts += [(f"evidence {number} note", item.note) for number, item in enumerate(entity.evidence)]
    texts += [(f"verdict {number}", f"{item.round} {item.verdict}") for number, item in enumerate(entity.verdicts)]
    for field_name, text in texts:
        if _LONG_DIGITS.search(text):
            problems.append(f"{label}: the {field_name} field carries a run of five or more digits")
    for number, item in enumerate(entity.evidence):
        if not _public_url(item.source):
            problems.append(f"{label}: evidence {number} source is not a public URL without a query string")
    for number, url in enumerate(entity.where_looked):
        if not _public_url(url):
            problems.append(f"{label}: where_looked {number} is not a public URL without a query string")
    return problems


def _name_problems(entities: list[LedgerEntity], rules: Rules) -> list[str]:
    problems = []
    first: dict[str, LedgerEntity] = {}
    for entity in entities:
        seen = first.setdefault(entity.entity, entity)
        if seen is not entity:
            problems.append(f"entity name {_shown(entity.entity)} appears more than once (entities {seen.index} "
                            f"and {entity.index})")
        for table, entries in rules.hand_kept.items():
            if entity.entity in entries:
                problems.append(f"{_label(entity)} has the name of an entity of the hand-kept {table}")
    return problems


def _collision_problems(entities: list[LedgerEntity]) -> list[str]:
    """C10: one alias, one entity (every status). Spec section 4.6: nor may a run-together form of a known
    payee's alias be another known payee's alias or run-together form."""
    problems = []
    owner: dict[str, LedgerEntity] = {}
    for entity in entities:
        for norm in dict.fromkeys(normalize(alias) for alias in entity.aliases if alias):
            first = owner.setdefault(norm, entity)
            if first is not entity:
                problems.append(f"alias {_shown(norm)} appears under {_label(first)} and {_label(entity)}")
    matcher = [e for e in entities if e.status == "admitted" and e.group in PAYEE_STATES]
    explicit: dict[str, LedgerEntity] = {}
    for entity in matcher:
        for alias in entity.aliases:
            explicit.setdefault(normalize(alias), entity)
    joined: dict[str, tuple[LedgerEntity, str]] = {}
    for entity in matcher:
        for alias in entity.aliases:
            norm = normalize(alias)
            words = norm.split(" ")
            form = "".join(words)
            if len(words) < 2 or len(form) < RUN_TOGETHER_MIN_LENGTH:
                continue
            other = explicit.get(form)
            if other is None:
                other, spelled = joined.setdefault(form, (entity, norm))
                if spelled == norm:
                    continue  # the same alias under two entities is reported above
            if other is not entity:
                problems.append(f"run-together form {_shown(form)} of {_label(entity)} is also claimed by "
                                f"{_label(other)}")
    return problems


def owner_named_problems(tables: Mapping[str, Mapping[str, tuple[str, ...]]],
                         owner_named: Mapping[str, tuple[tuple[str, str], ...]]) -> list[str]:
    """C10: every payee the owner named (spec section 2) is admitted in its group. A payee-matcher group must
    win the spelling in the known-payee matcher; a card issuer may instead be a bare issuer name of the
    context table; premium financing and bank names must be in their own table and no known payee."""
    index = AliasIndex({state: tables[TABLE_OF_GROUP[state]] for state in PAYEE_STATES})
    problems = []
    for group, pairs in owner_named.items():
        for label, spelling in pairs:
            text = normalize(spelling)
            payee = index.match(text)
            if group in PAYEE_STATES:
                if payee is not None and payee.state == group:
                    continue
                context = tables[TABLE_OF_GROUP["card_issuer_context"]]
                if group == "credit_card_payment" and payee is None and registry_match(text, context) is not None:
                    continue
            elif payee is None and registry_match(text, tables[TABLE_OF_GROUP[group]]) is not None:
                continue
            found = "nothing" if payee is None else f"{_shown(payee.entity)} ({payee.state})"
            problems.append(f"owner-named {mask_digit_runs(label)} is not admitted in {group}: {_shown(spelling)} "
                            f"matches {found}")
    return problems


def payout_credit_problems(entities: list[LedgerEntity], names: tuple[str, ...]) -> list[str]:
    """The owner's payout-credit ruling (PAYOUT_CREDIT_ENTITIES): S2 reads these entities' credits as the account
    holder's own sales, an exception to D1, so each is an admitted ledger entity of a group whose credits D1
    treats as financing proceeds (FINANCING_STATES)."""
    named = _by_name(entities)
    problems = []
    for name in names:
        entity = named.get(name)
        if entity is None:
            problems.append(f"PAYOUT_CREDIT_ENTITIES names {_shown(name)}, which is not a ledger entity")
        elif entity.status != "admitted" or entity.group not in FINANCING_STATES:
            problems.append(f"PAYOUT_CREDIT_ENTITIES names {_label(entity)}, {entity.status} in {entity.group}: a "
                            f"payout-credit exception needs an admitted entity of a group whose credits D1 treats "
                            f"as financing proceeds")
    return problems


def _unmasked_problems(data: object, rules: Rules) -> list[str]:
    entities, problems = parse_ledger(data)
    if problems:
        return problems
    held = frozenset(alias for table in rules.baseline.values() for aliases in table.values() for alias in aliases)
    problems.extend(_name_problems(entities, rules))
    for entity in entities:
        problems.extend(_entity_problems(entity, rules, held))
    problems.extend(_collision_problems(entities))
    problems.extend(owner_named_problems(render_tables(entities), rules.owner_named))
    problems.extend(payout_credit_problems(entities, rules.payout_credit))
    problems.extend(baseline_problems(entities, rules.baseline, rules.merged, rules.reattributed))
    return problems


def validate(data: object, rules: Rules) -> list[str]:
    """Every problem with the ledger, in a fixed order; an empty list means it may be rendered. Every rule
    masks the names and values it quotes; as a backstop, no returned message quotes a run of five or more
    digits."""
    return [mask_digit_runs(problem) for problem in _unmasked_problems(data, rules)]


# --- what the owner and a privacy reviewer read ---------------------------------------------------------------


def premium_insurer_overlaps(entities: list[LedgerEntity],
                             insurers: Mapping[str, tuple[str, ...]]) -> list[tuple[str, str]]:
    """(premium-finance entity, hand-kept insurer) pairs where a premium alias contains an insurer's alias as
    whole words. Not a problem: the insurance rule reads the premium table first (S2), so the financier keeps
    its own rows and rows naming only the insurer stay plain insurance. The owner rules on them. An insurer
    alias that a premium entity holds itself (the owner's ruling, PREMIUM_FINANCE_INSURER_ALIASES) is no
    overlap of any premium entity: the rows that print it are premium financing already."""
    premium = [entity for entity in entities if entity.status == "admitted" and entity.group == "premium_financing"]
    held = {normalize(alias) for entity in premium for alias in entity.aliases}
    pairs: list[tuple[str, str]] = []
    for entity in premium:
        texts = [normalize(alias) for alias in entity.aliases]
        for insurer, aliases in insurers.items():
            for alias in aliases:
                norm = normalize(alias)
                if norm in held:
                    continue
                inside = re.compile(rf"(?<![A-Z0-9]){re.escape(norm)}(?![A-Z0-9])")
                pair = (entity.entity, insurer)
                if pair not in pairs and any(inside.search(text) for text in texts):
                    pairs.append(pair)
    return pairs


def privacy_review(entities: list[LedgerEntity]) -> list[str]:
    """The lines a person reads for a person's or a customer's name before the ledger is committed: every
    entity name without an organisation word, and every alias that shares no word with its entity's name.
    Every status is listed, because the committed ledger carries them all. No line quotes a run of five or
    more digits."""
    lines = []
    for entity in entities:
        words = set(normalize(entity.entity).split(" "))
        if not words & ORG_CUES:
            lines.append(f"no organisation word in the name: {entity.entity} ({entity.status})")
        for alias in dict.fromkeys(entity.aliases):
            if not set(normalize(alias).split(" ")) & words:
                lines.append(f"alias shares no word with its name: {entity.entity} | {alias}")
    return [mask_digit_runs(line) for line in lines]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `C:\Python314\python.exe -m pytest tests/test_lender_ledger.py -q -p no:cacheprovider`
Expected: 140 passed. `test_the_baseline_revision_holds_the_lists_the_classifier_reads_until_s2` reads git. It proves that `BASELINE_REVISION` holds exactly the three lists the classifier reads today.

- [ ] **Step 6: Commit**

```powershell
git add tools/lender_ledger.py tests/lender_ledger_fixture.py tests/test_lender_ledger.py
git commit -m "tools: curated lender ledger schema and validator (contract C10)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 6: The deterministic renderer

> **Amended after review (fix round 1, 2026-09-25).** Spec section 5 governs the evidence ledger: the table rows carry a Group column, the rows awaiting an owner ruling and the rejected rows carry a Source column (the first source, else `none recorded`), every source and where-looked cell goes through `_cell`, and the moves table masks digit runs. Step 4 counts 11 tests.
>
> **Amended for the owner's ruling of 2026-09-25 (A2-A3).** The Admission section states the premium-finance insurer ruling (`PREMIUM_FINANCE_INSURER_ALIASES`) and how a merge (`MERGED_REGISTRY_ENTITIES`) is held; the moves table reads `rules.merged` and shows a merged entity's target in its "Now" column (`_now`). Step 4 counts 14 tests.
>
> **Amended after the review of A1-A4 (2026-09-25).** The Admission section states how an alias the owner reattributed (`REATTRIBUTED_REGISTRY_ALIASES`) is held; the moves table reads `rules.reattributed`, and `_now` shows each reattributed alias and its company in the "Now" column. Step 4 counts 15 tests.

**Files:**
- Create: `tools/build_lender_registry.py` (the renderer; Task 7 adds the command line)
- Test: `tests/test_build_lender_registry.py`

**Interfaces:**
- Consumes: `TABLES`, `LedgerEntity`, `Move`, `Rules` (with its `merged` and `reattributed`), `render_tables`, `baseline_moves` and `premium_insurer_overlaps` (Task 5).
- Produces:
  - `REGISTRY_PATH`, `EVIDENCE_PATH`, `BEGIN_MARKER`, `END_MARKER`, `HEADER`;
  - `render_block(tables) -> str`, the GENERATED block with `"\n"` line endings;
  - `current_block(source: str) -> str`, which reads a source's block;
  - `replace_block(source: str, block: str) -> str`, which keeps the file's line endings;
  - `render_evidence(entities, digest: str, rules: Rules) -> str`;
  - `render_tables`, re-exported from Task 5.

- [ ] **Step 1: Write the failing test**

Create `tests/test_build_lender_registry.py`:

```python
"""tools/build_lender_registry.py: the deterministic rendering of a curated ledger (contract C10)."""
from __future__ import annotations

import pytest

from tests.lender_ledger_fixture import RULES, ledger
from tools import build_lender_registry as builder
from tools import lender_ledger

TABLE_NAMES = [table for _group, table, _heading in lender_ledger.TABLES]


def _entities(*changes):
    entities, problems = lender_ledger.parse_ledger(ledger(*changes))
    assert problems == []
    return entities


# --- the tables and the GENERATED block ----------------------------------------------------------------------


def test_each_entity_renders_into_the_table_of_its_group_and_status():
    tables = builder.render_tables(_entities())
    assert list(tables) == TABLE_NAMES
    assert tables["LENDER_ALIASES"] == {
        "Oldco Funding": ("OLDCO FUNDING", "OLDCO"),
        "Quillon Funding": ("QUILLON FUNDING", "QUILLONFUND"),
    }
    assert tables["ALTERNATIVE_POSITION_ALIASES"] == {"Ruledco": ("RULEDCO CAPITAL",)}
    assert tables["CARD_ISSUER_ALIASES"] == {"Oxbow Card": ("OXBOW CARD PMT",)}
    assert tables["CARD_ISSUER_CONTEXT_ALIASES"] == {"Oxbow": ("OXBOW",)}
    assert tables["FLOOR_PLAN_ALIASES"] == {"Gantry Floorplan Credit": ("GANTRY FLOORPLAN",)}
    assert tables["FACTORING_ALIASES"] == {"Loxley Factoring": ("LOXLEY FACTORING",)}
    assert tables["PREMIUM_FINANCE_ALIASES"] == {
        "Brisk Mutual Funding": ("BRISK MUTUAL FUNDING",),
        "Hollin Premium Finance": ("HOLLIN PREMIUM FIN",),
    }
    assert tables["BANK_NAME_ALIASES"] == {"Brambleway Bank": ("BRAMBLEWAY BANK",)}
    assert tables["POTENTIAL_LENDER_ALIASES"] == {"Heldco Advance": ("HELDCO ADVANCE",)}
    rendered = {name for table in tables.values() for name in table}
    assert "Marsh Recovery" not in rendered and "Tarnmoor Capital" not in rendered


def test_an_entity_under_review_renders_into_the_potential_table_whatever_its_group():
    tables = builder.render_tables(_entities((3, "status", "review")))
    assert "Brambleway Capital" not in tables["LINE_OF_CREDIT_ALIASES"]
    assert tables["POTENTIAL_LENDER_ALIASES"]["Brambleway Capital"] == ("BRAMBLEWAY CAPITAL",)


def test_the_block_is_python_that_defines_exactly_the_rendered_tables():
    data = ledger((0, "aliases", ["QUILLON FUNDING", "QUILLONFUND", "QUILLON FUNDING GROUP", "QUILLON FNDG",
                                  "QUILLON FUNDING SERVICES", "QUILLON FUNDNG", "QUILLON FUNDING PAYMENTS"]))
    entities, _problems = lender_ledger.parse_ledger(data)
    tables = builder.render_tables(entities)
    block = builder.render_block(tables)
    assert block.startswith(builder.BEGIN_MARKER + "\n") and block.endswith("\n" + builder.END_MARKER)
    assert max(len(line) for line in block.split("\n")) <= 110
    namespace: dict = {}
    exec(compile(block, "block", "exec"), namespace)
    assert [name for name in namespace if name.isupper()] == TABLE_NAMES
    assert {name: namespace[name] for name in TABLE_NAMES} == tables


def test_the_block_of_an_empty_ledger_defines_fourteen_empty_tables():
    block = builder.render_block(builder.render_tables([]))
    namespace: dict = {}
    exec(compile(block, "block", "exec"), namespace)
    assert {name: namespace[name] for name in TABLE_NAMES} == {name: {} for name in TABLE_NAMES}
    assert "#: Floor plan.\nFLOOR_PLAN_ALIASES: dict[str, tuple[str, ...]] = {}\n" in block


def test_replace_block_keeps_everything_outside_the_markers_and_the_line_endings():
    block = builder.render_block(builder.render_tables(_entities()))
    source = f"HEAD = 1\r\n{builder.BEGIN_MARKER}\r\nOLD = 1\r\n{builder.END_MARKER}\r\n\r\nKEEP = 2\r\n"
    replaced = builder.replace_block(source, block)
    assert "OLD = 1" not in replaced and replaced.startswith("HEAD = 1\r\n") and replaced.endswith("KEEP = 2\r\n")
    assert "\n" not in replaced.replace("\r\n", "")
    assert builder.current_block(replaced) == block


# --- the evidence ledger -------------------------------------------------------------------------------------


@pytest.fixture
def evidence():
    return builder.render_evidence(_entities(), "a" * 64, RULES)


def test_the_evidence_ledger_names_its_ledger_digest_and_every_table(evidence):
    assert f"(ledger `sha256:{'a' * 64}`)" in evidence
    assert "| `LENDER_ALIASES` | 2 | 4 |" in evidence
    assert "| `POTENTIAL_LENDER_ALIASES` | 1 | 1 |" in evidence
    for _group, table, heading in lender_ledger.TABLES:
        assert f"\n## {heading} (`{table}`)\n" in evidence
    assert "## Mortgages (`MORTGAGE_SERVICER_ALIASES`)\n\n| Entity |" in evidence


def test_the_evidence_ledger_rows_carry_the_group_the_source_and_for_review_where_the_researchers_looked(evidence):
    assert ("| Quillon Funding | confirmed_lender | mca_or_revenue_based_funder | r1 upheld | admitted | "
            "QUILLON FUNDING, QUILLONFUND | https://quillon.example/ | - | - |") in evidence
    assert ("| Heldco Advance | confirmed_lender | mca_or_revenue_based_funder | r2 unresolved (not confirmed) | "
            "review | HELDCO ADVANCE | none recorded | https://registry.example/heldco, https://heldco.example/ | "
            "Fabricated: identity unconfirmed. |") in evidence


def test_an_entity_under_review_shows_its_researched_group_in_the_potential_table():
    evidence = builder.render_evidence(_entities((3, "status", "review")), "a" * 64, RULES)
    potential = evidence.split("(`POTENTIAL_LENDER_ALIASES`)\n", 1)[1].split("\n## ", 1)[0]
    assert ("| Brambleway Capital | line_of_credit | business_loc_provider | r1 upheld | review | "
            "BRAMBLEWAY CAPITAL | https://brambleway.example/ | https://brambleway.example/ | - |") in potential


def test_the_evidence_ledger_lists_moves_owner_rulings_overlaps_and_rejections(evidence):
    moves = evidence.split("## Moves from the registry as it stood before this ledger\n", 1)[1].split("\n## ", 1)[0]
    assert "| Ruledco | confirmed_lender | alternative_position | 0 | fabricated owner ruling, an alternative " \
           "position. |" in moves
    assert "| Westfen Leasing | lease_or_equipment_financing | lease_or_rental | 0 | - |" in moves
    waiting = evidence.split("## Awaiting an owner ruling\n", 1)[1].split("\n## ", 1)[0]
    assert ("| Marsh Recovery | potential_lender | servicer_or_processor_for_funders | r2 unresolved (not confirmed) "
            "| none recorded | https://marsh.example/, https://registry.example/marsh | Fabricated: a collector whose "
            "funder is unknown; the owner decides. |") in waiting
    assert ("- Brisk Mutual Funding (premium financing) has an alias that contains an alias of the hand-kept insurer "
            "Brisk Mutual (`INSURANCE_PROVIDER_ALIASES`).") in waiting
    rejected = evidence.split("## Rejected\n", 1)[1]
    assert ("| Tarnmoor Capital | confirmed_lender | mca_or_revenue_based_funder | r2 refuted (not confirmed) | "
            "https://tarnmoor.example/ | https://registry.example/tarnmoor | Fabricated: a bakery, not a funder. "
            "|") in rejected
    assert "TARNMOOR CAP" not in evidence and "MARSH RECOVERY" not in evidence


def test_the_evidence_ledger_states_the_owner_ruling_on_premium_aliases_that_repeat_an_insurer(evidence):
    admission = evidence.split("## Admission\n", 1)[1].split("\n## ", 1)[0]
    assert ("- A premium-finance alias equals an alias of a hand-kept insurer (`INSURANCE_PROVIDER_ALIASES`) only "
            "on the owner's ruling (`PREMIUM_FINANCE_INSURER_ALIASES`). The insurance rule reads the premium-finance "
            "table first, so rows that print that alias stay insurance and are also flagged premium financing, and "
            "no overlap with it awaits a ruling.") in admission


def test_the_evidence_ledger_states_how_a_merge_of_the_owner_is_held(evidence):
    admission = evidence.split("## Admission\n", 1)[1].split("\n## ", 1)[0]
    assert ("- An entity of that registry that the owner merged into a ledger entity (`MERGED_REGISTRY_ENTITIES`) "
            "is held by that entity under its name. The moves section shows the merge, and an alias the merge loses "
            "needs a `Move:` sentence in that entity's notes.") in admission


def test_the_evidence_ledger_states_how_an_alias_the_owner_reattributed_is_held(evidence):
    admission = evidence.split("## Admission\n", 1)[1].split("\n## ", 1)[0]
    assert ("- An alias of that registry that the owner ruled names another company (`REATTRIBUTED_REGISTRY_ALIASES`) "
            "is held by that company's ledger entity, and the known-payee and potential tables read it as that "
            "entity or not at all. The moves section shows it beside the entity that held it, and it is not counted "
            "as lost.") in admission


def test_an_insurer_alias_that_a_premium_entity_holds_awaits_no_owner_ruling():
    entities = _entities((13, "aliases", ["BRISK MUTUAL FUNDING", "BRISK MUTUAL"]))
    evidence = builder.render_evidence(entities, "a" * 64, RULES)
    waiting = evidence.split("## Awaiting an owner ruling\n", 1)[1].split("\n## ", 1)[0]
    assert "hand-kept insurer" not in waiting
    assert "| Marsh Recovery |" in waiting


def test_a_pipe_in_a_source_or_where_looked_never_splits_an_evidence_row():
    entities = _entities((0, "evidence", [{"source": "https://quillon.example/a|b", "note": "fabricated"}]),
                         (15, "where_looked", ["https://heldco.example/a|b"]),
                         (17, "where_looked", ["https://registry.example/t|x"]))
    evidence = builder.render_evidence(entities, "a" * 64, RULES)
    for section in evidence.split("\n## ")[1:]:
        rows = [line for line in section.splitlines() if line.startswith("|")]
        assert len({row.count("|") for row in rows}) <= 1, section.splitlines()[0]
    assert "| https://quillon.example/a/b | - | - |" in evidence
    assert "| none recorded | https://heldco.example/a/b |" in evidence
    assert "| https://tarnmoor.example/ | https://registry.example/t/x |" in evidence


def test_the_evidence_ledger_is_the_same_text_every_time(evidence):
    assert builder.render_evidence(_entities(), "a" * 64, RULES) == evidence
```

- [ ] **Step 2: Run it to verify it fails**

Run: `C:\Python314\python.exe -m pytest tests/test_build_lender_registry.py -q -p no:cacheprovider`
Expected: 1 error during collection: `ImportError: cannot import name 'build_lender_registry' from 'tools' (unknown location)`.

- [ ] **Step 3: Write the renderer**

Create `tools/build_lender_registry.py`:

```python
"""Render the lender registry from the curated ledger (contract C10), and check the ledger.

    python -m tools.build_lender_registry --check            validate docs/lender-registry-ledger.json
    python -m tools.build_lender_registry --write            validate, then render both outputs
    python -m tools.build_lender_registry --privacy-review   the lines a person reads before a commit

The ledger is curated outside the code; ``tools/lender_ledger.py`` holds its schema and its validator. This
tool renders, deterministically and without inferring anything:
  * the GENERATED block of ``analysis/classification_registry.py`` (the contract C2 tables);
  * ``docs/lender-registry-evidence.md``, the evidence ledger of spec section 5, for the owner to read.

Exit codes: 0 done; 1 the ledger has problems (nothing is written); 2 refused (no ledger, or not JSON).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import lender_ledger  # noqa: E402
from tools.lender_ledger import TABLES, LedgerEntity, Rules, render_tables  # noqa: E402

REGISTRY_PATH = ROOT / "analysis" / "classification_registry.py"
EVIDENCE_PATH = ROOT / "docs" / "lender-registry-evidence.md"
BEGIN_MARKER = "# --- BEGIN GENERATED: tools/build_lender_registry.py ---"
END_MARKER = "# --- END GENERATED: tools/build_lender_registry.py ---"
HEADER = (
    "# Rendered by tools/build_lender_registry.py from docs/lender-registry-ledger.json (contract C10).",
    "# Never edit by hand: change the ledger, then run python -m tools.build_lender_registry --write.",
)


# --- the GENERATED block -----------------------------------------------------------------------------------


def render_block(tables: dict[str, dict[str, tuple[str, ...]]]) -> str:
    """The GENERATED block: one typed dict literal per C2 table, in TABLES order, with "\\n" line endings."""
    lines = [BEGIN_MARKER, *HEADER, ""]
    for _group, table, heading in TABLES:
        lines.append(f"#: {heading}.")
        entries = tables[table]
        if not entries:
            lines += [f"{table}: dict[str, tuple[str, ...]] = {{}}", ""]
            continue
        lines.append(f"{table}: dict[str, tuple[str, ...]] = {{")
        for name, aliases in entries.items():
            inner = ", ".join(json.dumps(alias) for alias in aliases) + ("," if len(aliases) == 1 else "")
            line = f"    {json.dumps(name)}: ({inner}),"
            if len(line) <= 110:
                lines.append(line)
            else:
                lines.append(f"    {json.dumps(name)}: (")
                lines.extend(f"        {json.dumps(alias)}," for alias in aliases)
                lines.append("    ),")
        lines += ["}", ""]
    lines.append(END_MARKER)
    return "\n".join(lines)


def current_block(source: str) -> str:
    """The GENERATED block of a registry source, markers included, with "\\n" line endings."""
    text = source.replace("\r\n", "\n")
    start = text.index(BEGIN_MARKER)
    return text[start:text.index(END_MARKER, start) + len(END_MARKER)]


def replace_block(source: str, block: str) -> str:
    """The registry source with its GENERATED block replaced; the file keeps its own line endings."""
    newline = "\r\n" if "\r\n" in source else "\n"
    text = source.replace("\r\n", "\n")
    start = text.index(BEGIN_MARKER)
    end = text.index(END_MARKER, start) + len(END_MARKER)
    return (text[:start] + block + text[end:]).replace("\n", newline)


# --- the evidence ledger (spec section 5) ------------------------------------------------------------------


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\r", " ").replace("\n", " ").strip() or "-"


def _verdicts(entity: LedgerEntity) -> str:
    return "; ".join(f"{v.round} {v.verdict}" + ("" if v.confirmed else " (not confirmed)")
                     for v in entity.verdicts) or "none"


def _source(entity: LedgerEntity) -> str:
    return entity.evidence[0].source if entity.evidence else "none recorded"


def _looked(entity: LedgerEntity) -> str:
    return ", ".join(entity.where_looked) or "none recorded"


def _table_row(entity: LedgerEntity) -> str:
    looked = "-" if entity.status == "admitted" else _looked(entity)
    aliases = ", ".join(dict.fromkeys(entity.aliases))
    return (f"| {_cell(entity.entity)} | {entity.group} | {_cell(entity.business_type)} | "
            f"{_cell(_verdicts(entity))} | {entity.status} | {_cell(aliases)} | {_cell(_source(entity))} | "
            f"{_cell(looked)} | {_cell(entity.notes)} |")


def _now(move: lender_ledger.Move) -> str:
    """Where a moved entity of today's registry is now, the entity it merges into, if any, and each of its
    aliases that the owner gave to another company."""
    notes = [f"merged into {move.holder}"] if move.merged else []
    notes += [f"{alias} reattributed to {holder}" for alias, holder in move.reattributed]
    return f"{move.now} ({'; '.join(notes)})" if notes else move.now


def _listed_row(entity: LedgerEntity) -> str:
    return (f"| {_cell(entity.entity)} | {entity.group} | {_cell(entity.business_type)} | "
            f"{_cell(_verdicts(entity))} | {_cell(_source(entity))} | {_cell(_looked(entity))} | "
            f"{_cell(entity.notes)} |")


def render_evidence(entities: list[LedgerEntity], digest: str, rules: Rules) -> str:
    """The evidence ledger (spec section 5): every entity with its group, its verdicts, its first public source
    (else "none recorded") and, for anything not admitted, where the researchers looked. No statement text,
    amounts, account numbers or customer names."""
    tables = render_tables(entities)
    by_name = {entity.entity: entity for entity in entities}
    lines = [
        "# Lender registry evidence",
        "",
        f"Rendered by `tools/build_lender_registry.py` from `docs/lender-registry-ledger.json` (ledger "
        f"`sha256:{digest}`). Never edit by hand: change the ledger, then run "
        "`python -m tools.build_lender_registry --write`.",
        "",
        "The ledger is curated outside the code (contract C10): the orchestrator's research workflow consolidates "
        "the research into one entity per company, checks each entity adversarially and runs a completeness "
        "critic. The code only validates the ledger and renders this page and the GENERATED block of "
        "`analysis/classification_registry.py` from it. This page holds no statement text, amounts, account "
        "numbers or customer names.",
        "",
        "## Admission",
        "",
        "- An admitted entity is in its group's table. It has at least one public source, and an independent "
        "second agent's verdict of upheld or corrected that confirms it (spec section 5).",
        "- An entity under review is in `POTENTIAL_LENDER_ALIASES` (review, never counted), whatever its group. "
        "No entity of a table read only with context (credit cards, card issuers, bank names, premium financing) "
        "is under review.",
        "- An entity awaiting an owner ruling, or rejected, is in no table. This page lists it with its group, its "
        "public source and where the researchers looked.",
        "- Every payee the owner named in spec section 2 is admitted in its ruled group: the validator refuses a "
        "ledger in which one is not.",
        "- An entity of the registry as it stood before this ledger changes place, or loses an alias, only with a "
        "reason: a sentence of its notes that starts `Move:` (spec section 9). The moves section shows that reason.",
        "- A premium-finance alias equals an alias of a hand-kept insurer (`INSURANCE_PROVIDER_ALIASES`) only on the "
        "owner's ruling (`PREMIUM_FINANCE_INSURER_ALIASES`). The insurance rule reads the premium-finance table "
        "first, so rows that print that alias stay insurance and are also flagged premium financing, and no overlap "
        "with it awaits a ruling.",
        "- An entity of that registry that the owner merged into a ledger entity (`MERGED_REGISTRY_ENTITIES`) is held "
        "by that entity under its name. The moves section shows the merge, and an alias the merge loses needs a "
        "`Move:` sentence in that entity's notes.",
        "- An alias of that registry that the owner ruled names another company (`REATTRIBUTED_REGISTRY_ALIASES`) is "
        "held by that company's ledger entity, and the known-payee and potential tables read it as that entity or not "
        "at all. The moves section shows it beside the entity that held it, and it is not counted as lost.",
        "",
        "## Summary",
        "",
        "| Table | Entities | Aliases |",
        "|---|---:|---:|",
    ]
    for _group, table, _heading in TABLES:
        entries = tables[table]
        lines.append(f"| `{table}` | {len(entries)} | {sum(len(aliases) for aliases in entries.values())} |")
    for _group, table, heading in TABLES:
        lines += ["", f"## {heading} (`{table}`)", ""]
        if not tables[table]:
            lines.append("None.")
            continue
        lines += ["| Entity | Group | Business type | Verdicts | Status | Aliases | Source | Where the researchers "
                  "looked | Notes |", "|---|---|---|---|---|---|---|---|---|"]
        lines += [_table_row(by_name[name]) for name in tables[table]]
    moves, _missing = lender_ledger.baseline_moves(entities, rules.baseline, rules.merged, rules.reattributed)
    lines += ["", "## Moves from the registry as it stood before this ledger", ""]
    if moves:
        lines += ["| Entity | Was | Now | Aliases of today's registry lost | Why |", "|---|---|---|---:|---|"]
        lines += [f"| {_cell(lender_ledger.mask_digit_runs(m.entity))} | {m.was} | "
                  f"{_cell(lender_ledger.mask_digit_runs(_now(m)))} | {m.lost} | "
                  f"{_cell(lender_ledger.mask_digit_runs(m.reason))} |" for m in moves]
    else:
        lines.append("None.")
    lines += ["", "## Awaiting an owner ruling", ""]
    waiting = [entity for entity in entities if entity.status == "owner_ruling"]
    insurers = rules.hand_kept.get("INSURANCE_PROVIDER_ALIASES", {})
    overlaps = lender_ledger.premium_insurer_overlaps(entities, insurers)
    if waiting:
        lines += ["| Entity | Group | Business type | Verdicts | Source | Where the researchers looked | Notes |",
                  "|---|---|---|---|---|---|---|"]
        lines += [_listed_row(entity) for entity in waiting]
        if overlaps:
            lines.append("")
    for premium, insurer in overlaps:
        lines.append(f"- {premium} (premium financing) has an alias that contains an alias of the hand-kept "
                     f"insurer {insurer} (`INSURANCE_PROVIDER_ALIASES`). The insurance rule reads the premium-finance "
                     f"table first, so {premium} keeps its own rows, and rows that name only {insurer} stay plain "
                     "insurance, unflagged. The owner rules whether those rows are premium financing.")
    if not (waiting or overlaps):
        lines.append("None.")
    lines += ["", "## Rejected", ""]
    rejected = [entity for entity in entities if entity.status == "rejected"]
    if rejected:
        lines += ["| Entity | Group | Business type | Verdicts | Source | Where the researchers looked | Notes |",
                  "|---|---|---|---|---|---|---|"]
        lines += [_listed_row(entity) for entity in rejected]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `C:\Python314\python.exe -m pytest tests/test_build_lender_registry.py -q -p no:cacheprovider`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```powershell
git add tools/build_lender_registry.py tests/test_build_lender_registry.py
git commit -m "tools: deterministic rendering of the lender registry and its evidence ledger" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 7: The hand-kept inputs, the command line and the drift test

> **Amended after review (fix round 1, 2026-09-25).** The `move:` lines mask every run of five or more digits (`lender_ledger.mask_digit_runs`). The command-line tests gain `test_move_lines_and_the_evidence_ledger_never_quote_a_run_of_five_or_more_digits`, so Step 1 also imports `dataclasses`, `re` and the fixture's `BASELINE`. The counts in Steps 4 and 8 include it.
>
> **Amended for the owner's ruling of 2026-09-25 (A1-A4).** Step 5 respells BlueVine (`BLUEVINE CAPITAL`) and SmartPay (`SMARTPAY LEASING`) in `OWNER_NAMED_PAYEES` and adds three hand-kept constants: `PREMIUM_FINANCE_INSURER_ALIASES`, `MERGED_REGISTRY_ENTITIES` and `PAYOUT_CREDIT_ENTITIES`. `current_rules` reads them, and a merged entity's `move:` line says `merged into <target>`. The command-line tests gain the two merge tests and one test per new constant. The counts in Steps 4 and 8 include them.
>
> **Amended after the review of A1-A4 (2026-09-25).** Step 5 adds a seventh hand-kept constant, `REATTRIBUTED_REGISTRY_ALIASES`, which `current_rules` reads; a `move:` line lists each reattributed alias (`; <alias> reattributed to <target>`), and a move that is only a reattribution needs no reason. Step 1 also imports the fixture's `PELLAM_BASELINE`, `UNRESOLVED`, `entity` and `pellam_ledger`, and the command-line tests gain two reattribution tests and one test for the constant. The counts in Steps 4 and 8 include them.

**Files:**
- Modify: `analysis/classification_registry.py`. The seven hand-kept constants go after `PAYEE_GROUP_REGISTRIES`, before the Deprecated block.
- Modify: `tools/lender_ledger.py` (append `current_rules`)
- Modify: `tools/build_lender_registry.py` (import `argparse`; append `main`)
- Modify: `tests/test_build_lender_registry.py` (import `dataclasses`, `json`, `re` and the fixture's `BASELINE`, `PELLAM_BASELINE`, `UNRESOLVED`, `entity` and `pellam_ledger`; append the command-line tests)
- Create: `tests/test_lender_registry_drift.py`

**Interfaces:**
- Consumes: Tasks 5-6.
- Produces:
  - `analysis.classification_registry.OWNER_NAMED_PAYEES: dict[str, tuple[tuple[str, str], ...]]`, group → (label, spelling) pairs;
  - `BARE_PLATFORM_NAMES: tuple[str, ...]` and `BARE_BRAND_NAMES: tuple[str, ...]`;
  - `PREMIUM_FINANCE_INSURER_ALIASES: tuple[str, ...]`, `MERGED_REGISTRY_ENTITIES: dict[str, str]` (entity of today's registry → the ledger entity that absorbs it), `REATTRIBUTED_REGISTRY_ALIASES: dict[str, str]` (alias of today's registry → the ledger entity of the other company it names) and `PAYOUT_CREDIT_ENTITIES: tuple[str, ...]` (ledger entity names; S2 reads it as a D1 exception);
  - `tools.lender_ledger.current_rules() -> Rules`, which reads those constants, the two hand-kept tables and git;
  - `tools.build_lender_registry.main(argv: list[str] | None = None) -> int`:
    - one of `--check`, `--write` or `--privacy-review`, plus `--ledger`, `--registry` and `--evidence`;
    - `--check` and `--write` print `ledger ok: ...`, then one `move: ...` line per move from today's registry (Decision 3), with every run of five or more digits masked; a merged entity's line reads `move: <entity> (<table>): merged into <target>; <was> -> <now>, <n> of today's aliases lost; why: <the target's Move: sentence, else "none needed (the owner's merge, MERGED_REGISTRY_ENTITIES)">`; an entity with a reattributed alias adds `; <alias> reattributed to <target>` after the lost count, and when nothing else moved its reason, if none, reads `none needed (the owner's reattribution, REATTRIBUTED_REGISTRY_ALIASES)`;
    - exit codes 0 (done), 1 (the ledger has problems; nothing is written) and 2 (no ledger, or not JSON).

- [ ] **Step 1: Import `dataclasses`, `json`, `re` and the fixture's baselines and helpers in the builder test**

In `tests/test_build_lender_registry.py`, replace:

```python
from __future__ import annotations

import pytest

from tests.lender_ledger_fixture import RULES, ledger
```

with:

```python
from __future__ import annotations

import dataclasses
import json
import re

import pytest

from tests.lender_ledger_fixture import BASELINE, PELLAM_BASELINE, RULES, UNRESOLVED, entity, ledger, pellam_ledger
```

- [ ] **Step 2: Append the failing command-line tests**

Append to `tests/test_build_lender_registry.py`:

```python


# --- the command line --------------------------------------------------------------------------------------


def _registry_source() -> str:
    return (f'"""Fabricated registry."""\r\nHEAD = 1\r\n\r\n{builder.BEGIN_MARKER}\r\nOLD = 1\r\n'
            f"{builder.END_MARKER}\r\n\r\nKEEP = 2\r\n")


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(lender_ledger, "current_rules", lambda: RULES)
    ledger_file = tmp_path / "ledger.json"
    ledger_file.write_text(json.dumps(ledger(), indent=2), encoding="utf-8")
    registry_file = tmp_path / "registry.py"
    registry_file.write_bytes(_registry_source().encode("utf-8"))
    return {"ledger": ledger_file, "registry": registry_file, "evidence": tmp_path / "docs" / "evidence.md"}


def _args(paths, mode):
    return [mode, "--ledger", str(paths["ledger"]), "--registry", str(paths["registry"]),
            "--evidence", str(paths["evidence"])]


def test_check_accepts_a_clean_ledger_prints_every_move_and_writes_nothing(paths, capsys):
    assert builder.main(_args(paths, "--check")) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"ledger ok: 18 entities, sha256:{lender_ledger.ledger_digest(ledger())}",
        "move: Ruledco (CONFIRMED_LENDER_ALIASES): confirmed_lender -> alternative_position, 0 of today's aliases "
        "lost; why: fabricated owner ruling, an alternative position.",
        "move: Westfen Leasing (LEASE_PROVIDER_ALIASES): lease_or_equipment_financing -> lease_or_rental, 0 of "
        "today's aliases lost; why: none needed (spec section 4.1)",
    ]
    assert paths["registry"].read_bytes() == _registry_source().encode("utf-8")
    assert not paths["evidence"].exists()


def test_move_lines_and_the_evidence_ledger_never_quote_a_run_of_five_or_more_digits(paths, monkeypatch, capsys):
    baseline = {**BASELINE, "CONFIRMED_LENDER_ALIASES": {
        **BASELINE["CONFIRMED_LENDER_ALIASES"], "Oldco 7777777 Holdings": ("OLDCO HOLDINGS", "OLDCO FUNDING")}}
    monkeypatch.setattr(lender_ledger, "current_rules", lambda: dataclasses.replace(RULES, baseline=baseline))
    paths["ledger"].write_text(json.dumps(ledger((1, "notes", "Move: fabricated merger of two funders."))),
                               encoding="utf-8")
    assert builder.main(_args(paths, "--write")) == 0
    moves = [line for line in capsys.readouterr().out.splitlines() if line.startswith("move: ")]
    assert ("move: Oldco (withheld: a run of digits) Holdings (CONFIRMED_LENDER_ALIASES): confirmed_lender -> "
            "confirmed_lender, 1 of today's aliases lost; why: fabricated merger of two funders.") in moves
    section = paths["evidence"].read_text(encoding="utf-8").split("## Moves from the registry", 1)[1]
    assert "| Oldco (withheld: a run of digits) Holdings | confirmed_lender | confirmed_lender | 1 |" in section
    assert not re.search(r"\d{5}", "\n".join(moves) + section)


def _merge_rules():
    """RULES whose today's registry also holds 'Quillon Holdings', which the owner merged into 'Quillon Funding'."""
    baseline = {**BASELINE, "CONFIRMED_LENDER_ALIASES": {
        **BASELINE["CONFIRMED_LENDER_ALIASES"], "Quillon Holdings": ("QUILLON HOLDINGS", "QUILLON HLDG")}}
    return dataclasses.replace(RULES, baseline=baseline, merged={"Quillon Holdings": "Quillon Funding"})


def test_a_merge_prints_one_move_line_and_shows_in_the_evidence_moves(paths, monkeypatch, capsys):
    monkeypatch.setattr(lender_ledger, "current_rules", _merge_rules)
    paths["ledger"].write_text(json.dumps(ledger(
        (0, "aliases", ["QUILLON FUNDING", "QUILLONFUND", "QUILLON HOLDINGS"]),
        (0, "notes", "Move: fabricated merger; the short form prints on no row."))), encoding="utf-8")
    assert builder.main(_args(paths, "--write")) == 0
    moves = [line for line in capsys.readouterr().out.splitlines() if line.startswith("move: ")]
    assert ("move: Quillon Holdings (CONFIRMED_LENDER_ALIASES): merged into Quillon Funding; confirmed_lender -> "
            "confirmed_lender, 1 of today's aliases lost; why: fabricated merger; the short form prints on no "
            "row.") in moves
    assert len(moves) == 3
    section = paths["evidence"].read_text(encoding="utf-8").split("## Moves from the registry", 1)[1]
    assert ("| Quillon Holdings | confirmed_lender | confirmed_lender (merged into Quillon Funding) | 1 | fabricated "
            "merger; the short form prints on no row. |") in section


def test_a_merge_that_loses_nothing_needs_no_reason(paths, monkeypatch, capsys):
    monkeypatch.setattr(lender_ledger, "current_rules", _merge_rules)
    paths["ledger"].write_text(json.dumps(ledger(
        (0, "aliases", ["QUILLON FUNDING", "QUILLONFUND", "QUILLON HOLDINGS", "QUILLON HLDG"]))), encoding="utf-8")
    assert builder.main(_args(paths, "--check")) == 0
    assert ("move: Quillon Holdings (CONFIRMED_LENDER_ALIASES): merged into Quillon Funding; confirmed_lender -> "
            "confirmed_lender, 0 of today's aliases lost; why: none needed (the owner's merge, "
            "MERGED_REGISTRY_ENTITIES)") in capsys.readouterr().out.splitlines()


def _reattribution_rules():
    """RULES whose today's lease list also holds 'Pellam', whose first alias the owner gave to 'Pellam Solutions'."""
    return dataclasses.replace(RULES, baseline=PELLAM_BASELINE, reattributed={"PELLAM SOL": "Pellam Solutions"})


def test_a_reattribution_shows_beside_todays_entity_in_its_move_line_and_the_evidence_moves(paths, monkeypatch,
                                                                                          capsys):
    monkeypatch.setattr(lender_ledger, "current_rules", _reattribution_rules)
    paths["ledger"].write_text(json.dumps(pellam_ledger()), encoding="utf-8")
    assert builder.main(_args(paths, "--write")) == 0
    moves = [line for line in capsys.readouterr().out.splitlines() if line.startswith("move: ")]
    assert ("move: Pellam (LEASE_PROVIDER_ALIASES): lease_or_equipment_financing -> lease_or_rental, 1 of today's "
            "aliases lost; PELLAM SOL reattributed to Pellam Solutions; why: bare PELLAM names other "
            "companies.") in moves
    assert len(moves) == 3
    section = paths["evidence"].read_text(encoding="utf-8").split("## Moves from the registry", 1)[1]
    assert ("| Pellam | lease_or_equipment_financing | lease_or_rental (PELLAM SOL reattributed to Pellam Solutions) "
            "| 1 | bare PELLAM names other companies. |") in section


def test_a_reattribution_alone_needs_no_reason(paths, monkeypatch, capsys):
    monkeypatch.setattr(lender_ledger, "current_rules",
                        lambda: dataclasses.replace(RULES, reattributed={"OLDCO": "Oldco Bakery"}))
    data = ledger((1, "aliases", ["OLDCO FUNDING"]))
    data["entities"].append(entity("Oldco Bakery", "potential_lender", ["OLDCO"], status="rejected",
                                   business_type="bakery", evidence=[], verdicts=UNRESOLVED,
                                   notes="Fabricated: a bakery, not a funder."))
    paths["ledger"].write_text(json.dumps(data), encoding="utf-8")
    assert builder.main(_args(paths, "--check")) == 0
    assert ("move: Oldco Funding (CONFIRMED_LENDER_ALIASES): confirmed_lender -> confirmed_lender, 0 of today's "
            "aliases lost; OLDCO reattributed to Oldco Bakery; why: none needed (the owner's reattribution, "
            "REATTRIBUTED_REGISTRY_ALIASES)") in capsys.readouterr().out.splitlines()


def test_check_prints_every_problem_and_exits_1(paths, capsys):
    paths["ledger"].write_text(json.dumps(ledger((0, "evidence", []))), encoding="utf-8")
    assert builder.main(_args(paths, "--check")) == 1
    assert capsys.readouterr().out.splitlines() == [
        "problem: entity 0 ('Quillon Funding') is admitted without evidence",
        "refused: 1 problem(s); nothing was written",
    ]


def test_write_renders_the_block_and_the_evidence_ledger_the_same_way_twice(paths):
    assert builder.main(_args(paths, "--write")) == 0
    first = (paths["registry"].read_bytes(), paths["evidence"].read_bytes())
    assert builder.main(_args(paths, "--write")) == 0
    assert (paths["registry"].read_bytes(), paths["evidence"].read_bytes()) == first
    registry_text = first[0].decode("utf-8")
    assert "\n" not in registry_text.replace("\r\n", "") and "OLD = 1" not in registry_text
    assert registry_text.startswith('"""Fabricated registry."""\r\nHEAD = 1\r\n')
    assert registry_text.endswith("KEEP = 2\r\n")
    namespace: dict = {}
    exec(compile(registry_text, "registry.py", "exec"), namespace)
    entities, _problems = lender_ledger.parse_ledger(ledger())
    assert {name: namespace[name] for name in TABLE_NAMES} == builder.render_tables(entities)
    expected = builder.render_evidence(entities, lender_ledger.ledger_digest(ledger()), RULES)
    assert first[1].decode("utf-8") == expected


def test_write_refuses_a_ledger_with_problems_and_writes_nothing(paths):
    paths["ledger"].write_text(json.dumps(ledger((0, "aliases", ["QUILLON#FUND"]))), encoding="utf-8")
    assert builder.main(_args(paths, "--write")) == 1
    assert paths["registry"].read_bytes() == _registry_source().encode("utf-8")
    assert not paths["evidence"].exists()


def test_a_missing_or_unreadable_ledger_is_refused(paths, tmp_path):
    args = _args(paths, "--check")
    args[args.index("--ledger") + 1] = str(tmp_path / "absent.json")
    assert builder.main(args) == 2
    paths["ledger"].write_text("{not json", encoding="utf-8")
    assert builder.main(_args(paths, "--write")) == 2
    assert not paths["evidence"].exists()


def test_privacy_review_prints_the_lines_a_person_reads(paths, capsys):
    assert builder.main(_args(paths, "--privacy-review")) == 0
    entities, _problems = lender_ledger.parse_ledger(ledger())
    assert capsys.readouterr().out.splitlines() == lender_ledger.privacy_review(entities)


def test_the_rules_come_from_the_hand_kept_constants_of_the_registry():
    from analysis import classification_registry as registry

    rules = lender_ledger.current_rules()
    assert rules.owner_named is registry.OWNER_NAMED_PAYEES
    assert {"SQUARE", "SHOPIFY", "PAYPAL", "STRIPE", "INTUIT", "AMAZON"} <= rules.platforms
    assert {"CAPITAL ONE", "TOYOTA", "FORD", "APPLE"} <= rules.brands
    assert rules.hand_kept["INSURANCE_PROVIDER_ALIASES"] is registry.INSURANCE_PROVIDER_ALIASES
    assert rules.hand_kept["OPERATING_REVENUE_SOURCE_ALIASES"] is registry.OPERATING_REVENUE_SOURCE_ALIASES
    assert list(rules.baseline) == list(lender_ledger.BASELINE_TABLES)


def test_the_owner_named_payees_cover_every_group_spec_section_2_names():
    from analysis import classification_registry as registry

    assert set(registry.OWNER_NAMED_PAYEES) == {
        "confirmed_lender", "alternative_position", "line_of_credit", "credit_card_payment", "vehicle_financing",
        "bank_name", "lease_or_rental", "floor_plan_financing", "factoring", "premium_financing",
    }
    labels = {label for pairs in registry.OWNER_NAMED_PAYEES.values() for label, _spelling in pairs}
    assert {"OnDeck", "Bitty", "Legend", "LG Funding", "Hunter Caroline", "CAN Capital", "CanaCap"} <= labels
    for pairs in registry.OWNER_NAMED_PAYEES.values():
        for _label, spelling in pairs:
            assert spelling == spelling.upper() and spelling.replace(" ", "").isalnum(), spelling


def test_the_owner_ruling_of_2026_09_25_respells_bluevine_and_smartpay():
    from analysis import classification_registry as registry

    spelled = {label: spelling for pairs in registry.OWNER_NAMED_PAYEES.values() for label, spelling in pairs}
    assert spelled["BlueVine"] == "BLUEVINE CAPITAL"
    assert spelled["SmartPay"] == "SMARTPAY LEASING"


def test_the_premium_insurer_spellings_are_hand_kept_insurer_aliases_that_the_validator_reads():
    from analysis import classification_registry as registry
    from analysis.description_text import normalize_transaction_description as normalize

    insurers = {normalize(alias) for aliases in registry.INSURANCE_PROVIDER_ALIASES.values() for alias in aliases}
    ruled = frozenset(normalize(spelling) for spelling in registry.PREMIUM_FINANCE_INSURER_ALIASES)
    assert ruled and ruled <= insurers
    assert lender_ledger.current_rules().premium_insurer_aliases == ruled


def test_the_merged_entities_are_entities_of_todays_registry_that_the_validator_reads():
    from analysis import classification_registry as registry

    rules = lender_ledger.current_rules()
    today = {name for table in rules.baseline.values() for name in table}
    assert registry.MERGED_REGISTRY_ENTITIES and set(registry.MERGED_REGISTRY_ENTITIES) <= today
    assert rules.merged is registry.MERGED_REGISTRY_ENTITIES


def test_the_reattributed_aliases_are_aliases_of_todays_registry_that_the_validator_reads():
    from analysis import classification_registry as registry
    from analysis.description_text import normalize_transaction_description as normalize

    rules = lender_ledger.current_rules()
    today = {normalize(alias) for table in rules.baseline.values() for aliases in table.values() for alias in aliases}
    assert registry.REATTRIBUTED_REGISTRY_ALIASES == {"SMARTPAY SOL": "SmartPay Solutions, LLC"}
    assert {normalize(alias) for alias in registry.REATTRIBUTED_REGISTRY_ALIASES} <= today
    assert rules.reattributed is registry.REATTRIBUTED_REGISTRY_ALIASES


def test_the_payout_credit_entities_are_the_ones_the_validator_reads():
    from analysis import classification_registry as registry

    assert registry.PAYOUT_CREDIT_ENTITIES
    assert lender_ledger.current_rules().payout_credit is registry.PAYOUT_CREDIT_ENTITIES
```

- [ ] **Step 3: Write the failing drift test**

Create `tests/test_lender_registry_drift.py`:

```python
"""Contract C10: the committed registry block and evidence ledger are the rendering of the committed ledger."""
from __future__ import annotations

from analysis import classification_registry as registry
from tools import build_lender_registry as builder
from tools import lender_ledger


def _committed():
    """The committed ledger, or the empty ledger until the orchestrator commits it (S1 plan, Task 9)."""
    if lender_ledger.LEDGER_PATH.exists():
        data = lender_ledger.read_ledger(lender_ledger.LEDGER_PATH)
    else:
        data = lender_ledger.EMPTY_LEDGER
    entities, problems = lender_ledger.parse_ledger(data)
    assert problems == []
    return data, entities


def test_the_generated_block_is_the_rendering_of_the_committed_ledger():
    _data, entities = _committed()
    source = builder.REGISTRY_PATH.read_text(encoding="utf-8")
    assert builder.current_block(source) == builder.render_block(builder.render_tables(entities))


def test_the_registry_module_holds_exactly_the_rendered_tables():
    _data, entities = _committed()
    tables = builder.render_tables(entities)
    for _group, table, _heading in lender_ledger.TABLES:
        assert getattr(registry, table) == tables[table], table


def test_the_evidence_ledger_is_the_rendering_of_the_committed_ledger():
    if not lender_ledger.LEDGER_PATH.exists():
        assert not builder.EVIDENCE_PATH.exists()
        return
    data, entities = _committed()
    expected = builder.render_evidence(entities, lender_ledger.ledger_digest(data), lender_ledger.current_rules())
    assert builder.EVIDENCE_PATH.read_text(encoding="utf-8") == expected
```

- [ ] **Step 4: Run them to verify they fail**

Run: `C:\Python314\python.exe -m pytest tests/test_build_lender_registry.py tests/test_lender_registry_drift.py -q -p no:cacheprovider`
Expected: `7 failed, 18 passed, 11 errors`.
- The eleven tests that use the `paths` fixture error at setup, because `monkeypatch` finds no `current_rules` on `tools.lender_ledger`.
- `test_the_rules_come_from_the_hand_kept_constants_of_the_registry`, `test_the_merged_entities_are_entities_of_todays_registry_that_the_validator_reads` and `test_the_reattributed_aliases_are_aliases_of_todays_registry_that_the_validator_reads` fail with `AttributeError: module 'tools.lender_ledger' has no attribute 'current_rules'`.
- `test_the_owner_named_payees_cover_every_group_spec_section_2_names` and `test_the_owner_ruling_of_2026_09_25_respells_bluevine_and_smartpay` fail with `AttributeError: module 'analysis.classification_registry' has no attribute 'OWNER_NAMED_PAYEES'`.
- `test_the_premium_insurer_spellings_are_hand_kept_insurer_aliases_that_the_validator_reads` and `test_the_payout_credit_entities_are_the_ones_the_validator_reads` fail with an `AttributeError` for `PREMIUM_FINANCE_INSURER_ALIASES` and `PAYOUT_CREDIT_ENTITIES`.
- The fifteen tests of Task 6 pass. The three drift tests already pass, because Task 2's block is the rendering of the empty ledger. If the ledger is already on the branch (see "Before Task 1"), they fail instead, and the line reads `10 failed, 15 passed, 11 errors`.

- [ ] **Step 5: Add the hand-kept inputs to the registry**

In `analysis/classification_registry.py`, replace:

```python
    "lease_or_rental": LEASE_RENTAL_ALIASES,
    "credit_card_payment": CARD_ISSUER_ALIASES,
}
```

with:

```python
    "lease_or_rental": LEASE_RENTAL_ALIASES,
    "credit_card_payment": CARD_ISSUER_ALIASES,
}


# --- Hand-kept inputs of the ledger validator (tools/lender_ledger.py) ---

#: Spec section 2 (the owner's rulings of 2026-09-24 and the amendment): every payee the owner named, by
#: ledger group, with one public spelling of it. ``python -m tools.build_lender_registry --check`` refuses
#: a ledger that does not admit each one in its group (contract C10). Change it only on an owner ruling.
#: The owner ruling of 2026-09-25 respelled BlueVine and SmartPay (see their entries).
OWNER_NAMED_PAYEES: dict[str, tuple[tuple[str, str], ...]] = {
    "confirmed_lender": (
        ("OnDeck", "ONDECK"),
        ("Bitty", "BITTY ADVANCE"),
        ("Legend", "LEGEND ADVANCE FUNDING"),
        ("LG Funding", "LG FUNDING"),
        ("Hunter Caroline", "HUNTER CAROLINE"),
        ("CAN Capital", "CAN CAPITAL"),
        ("CanaCap", "CANACAP"),
        ("NMEF", "NMEF FUNDING"),
        ("Balboa", "BALBOA CAPITAL"),
        ("Navitas", "NAVITAS CREDIT CORP"),
        ("Deere", "JOHN DEERE FINANCIAL"),
    ),
    "alternative_position": (
        ("SBA/EIDL", "SBA EIDL"),
        ("BDC", "BDC"),
        ("Affirm", "AFFIRM"),
        ("Amex loans", "AMERICAN EXPRESS BUSINESS LOAN"),
        ("Intuit", "INTUIT FINANCING"),
        ("Square", "SQUARE CAPITAL"),
        ("Shopify", "SHOPIFY CAPITAL"),
        ("PayPal", "PAYPAL WORKING CAPITAL"),
        ("Stripe", "STRIPE CAPITAL"),
        ("Amazon financing", "AMAZON CAPITAL SERVICES"),
    ),
    "line_of_credit": (
        ("Fundbox", "FUNDBOX"),
        # Owner ruling 2026-09-25: bare BLUEVINE takes Bluevine Bill Pay and checking rows.
        ("BlueVine", "BLUEVINE CAPITAL"),
        ("Kabbage", "KABBAGE"),
    ),
    "credit_card_payment": (
        ("American Express", "AMEX EPAYMENT ACH PMT"),
        ("Capital One", "CAPITAL ONE ONLINE PMT"),
        ("Chase", "CHASE CREDIT CRD EPAY"),
        ("Credit One", "CREDIT ONE BANK PAYMENT"),
        ("Concora", "CONCORA CREDIT PAYMENT"),
    ),
    "vehicle_financing": (
        ("GM Financial", "GM FINANCIAL"),
        ("Ford Credit", "FORD CREDIT"),
        ("Toyota Financial", "TOYOTA FINANCIAL"),
        ("Ally", "ALLY FINANCIAL"),
    ),
    "bank_name": (
        ("Truist", "TRUIST LN PYMT"),
    ),
    "lease_or_rental": (
        ("Progressive", "PROGRESSIVE LEASING"),
        # Owner ruling 2026-09-25: SMARTPAY SOL is SmartPay Solutions premium billing.
        ("SmartPay", "SMARTPAY LEASING"),
        ("Snap", "SNAP FINANCE"),
    ),
    "floor_plan_financing": (
        ("NextGear Capital", "NEXTGEAR CAPITAL"),
        ("Westlake Flooring", "WESTLAKE FLOORING"),
    ),
    "factoring": (
        ("RTS Financial", "RTS FINANCIAL"),
        ("OTR Capital", "OTR CAPITAL"),
        ("Apex Capital", "APEX CAPITAL"),
        ("BC Factoring", "BC FACTORING"),
    ),
    "premium_financing": (
        ("IPFS", "IPFS"),
        ("First Insurance Funding", "FIRST INSURANCE FUNDING"),
    ),
}

#: Spec section 5: bare platform names appear only in OPERATING_REVENUE_SOURCE_ALIASES.
BARE_PLATFORM_NAMES: tuple[str, ...] = ("SQUARE", "SHOPIFY", "PAYPAL", "STRIPE", "INTUIT", "AMAZON", "AMZN")

#: Spec section 5: brands that also sell goods, and bare issuer and bank names. Alone, each may be an alias
#: only of CARD_ISSUER_CONTEXT_ALIASES or BANK_NAME_ALIASES, which the classifier reads only with payment or
#: loan wording. A known-payee or potential alias must name the financing business ("TOYOTA FINANCIAL").
BARE_BRAND_NAMES: tuple[str, ...] = (
    "ALLY", "AMERICAN EXPRESS", "AMEX", "APPLE", "BANK OF AMERICA", "BARCLAYS", "CAPITAL ONE", "CHASE", "CITI",
    "CITIBANK", "DEERE", "DISCOVER", "FORD", "GM", "HONDA", "HYUNDAI", "JOHN DEERE", "KIA", "NISSAN",
    "SYNCHRONY", "TOYOTA", "WELLS FARGO",
)

#: Owner ruling 2026-09-25: premium-finance spellings that may equal an alias of the hand-kept
#: INSURANCE_PROVIDER_ALIASES. The bare FIRST INSURANCE originator is FIRST Insurance Funding: its rows stay
#: insurance and are also flagged premium financing. The validator exempts exactly these spellings from its
#: hand-kept-alias rule, and only on a premium_financing entity.
PREMIUM_FINANCE_INSURER_ALIASES: tuple[str, ...] = ("FIRST INSURANCE",)

#: Owner ruling 2026-09-25: an entity of today's registry (the validator's BASELINE_REVISION) that a ledger
#: entity absorbs, mapped to that ledger entity. The validator reads the merged entity as held by its target:
#: it keeps no name of its own, and the aliases it loses need a "Move:" sentence in the target's notes.
MERGED_REGISTRY_ENTITIES: dict[str, str] = {"EBF HOLDINGS": "EVEREST BUSINESS FUNDING"}

#: Owner ruling 2026-09-25: an alias of today's registry (the validator's BASELINE_REVISION) that names a company
#: other than today's entity, mapped to the ledger entity of that company, which holds it. SMARTPAY SOL is
#: SmartPay Solutions premium billing, not the lease-to-own SmartPay. The validator leaves the alias out of today's
#: entity (it is neither lost nor that entity's first alias) and refuses a registry that reads it as any other
#: entity.
REATTRIBUTED_REGISTRY_ALIASES: dict[str, str] = {"SMARTPAY SOL": "SmartPay Solutions, LLC"}

#: Owner ruling 2026-09-25: ledger entities whose credits are the account holder's own sales, settled by the
#: platform: revenue, not financing proceeds. A D1 exception that S2 reads; their debits keep their group. The
#: validator refuses a name that is not an admitted ledger entity of a group whose credits D1 treats as
#: financing proceeds (analysis.flag_groups.FINANCING_STATES).
PAYOUT_CREDIT_ENTITIES: tuple[str, ...] = ("Sezzle Inc", "American First Finance, LLC", "PAYABILITY")
```

- [ ] **Step 6: Append `current_rules` to the ledger module**

Append to `tools/lender_ledger.py`:

```python


# --- the hand-kept inputs --------------------------------------------------------------------------------------


def current_rules() -> Rules:
    """The validator's inputs: the hand-kept constants of ``analysis/classification_registry.py`` and today's
    registry from git at BASELINE_REVISION."""
    from analysis import classification_registry as registry

    return Rules(
        owner_named=registry.OWNER_NAMED_PAYEES,
        platforms=frozenset(normalize(name) for name in registry.BARE_PLATFORM_NAMES),
        brands=frozenset(normalize(name) for name in registry.BARE_BRAND_NAMES),
        hand_kept={
            INSURER_TABLE: registry.INSURANCE_PROVIDER_ALIASES,
            "OPERATING_REVENUE_SOURCE_ALIASES": registry.OPERATING_REVENUE_SOURCE_ALIASES,
        },
        baseline=load_baseline(),
        premium_insurer_aliases=frozenset(normalize(name) for name in registry.PREMIUM_FINANCE_INSURER_ALIASES),
        merged=registry.MERGED_REGISTRY_ENTITIES,
        payout_credit=registry.PAYOUT_CREDIT_ENTITIES,
        reattributed=registry.REATTRIBUTED_REGISTRY_ALIASES,
    )
```

- [ ] **Step 7: Add the command line**

In `tools/build_lender_registry.py`, replace:

```python
import json
import sys
```

with:

```python
import argparse
import json
import sys
```

Then append to `tools/build_lender_registry.py`:

```python


# --- the command line ----------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate the ledger; write nothing")
    mode.add_argument("--write", action="store_true",
                      help="validate the ledger, then render the registry block and the evidence ledger")
    mode.add_argument("--privacy-review", action="store_true",
                      help="print the names and aliases a person reads before the ledger is committed")
    parser.add_argument("--ledger", type=Path, default=lender_ledger.LEDGER_PATH)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE_PATH)
    args = parser.parse_args(argv)
    if not args.ledger.is_file():
        print(f"refused: {args.ledger} does not exist; the orchestrator's consolidation workflow commits it "
              "(contract C10)", file=sys.stderr)
        return 2
    try:
        data = lender_ledger.read_ledger(args.ledger)
    except (OSError, ValueError) as error:
        print(f"refused: {args.ledger} is not readable JSON ({type(error).__name__})", file=sys.stderr)
        return 2
    if args.privacy_review:
        entities, problems = lender_ledger.parse_ledger(data)
        for line in [f"problem: {problem}" for problem in problems] or lender_ledger.privacy_review(entities):
            print(line)
        return 1 if problems else 0
    rules = lender_ledger.current_rules()
    problems = lender_ledger.validate(data, rules)
    if problems:
        for problem in problems:
            print(f"problem: {problem}")
        print(f"refused: {len(problems)} problem(s); nothing was written")
        return 1
    entities, _problems = lender_ledger.parse_ledger(data)
    digest = lender_ledger.ledger_digest(data)
    print(f"ledger ok: {len(entities)} entities, sha256:{digest}")
    moves, _missing = lender_ledger.baseline_moves(entities, rules.baseline, rules.merged, rules.reattributed)
    for move in moves:
        merge = f"merged into {move.holder}; " if move.merged else ""
        given = "".join(f"; {alias} reattributed to {holder}" for alias, holder in move.reattributed)
        if move.merged:
            unneeded = "the owner's merge, MERGED_REGISTRY_ENTITIES"
        elif move.now == move.was:
            unneeded = "the owner's reattribution, REATTRIBUTED_REGISTRY_ALIASES"
        else:
            unneeded = "spec section 4.1"
        print(lender_ledger.mask_digit_runs(
            f"move: {move.entity} ({move.table}): {merge}{move.was} -> {move.now}, {move.lost} of today's aliases "
            f"lost{given}; why: {move.reason or f'none needed ({unneeded})'}"))
    if args.check:
        return 0
    tables = render_tables(entities)
    source = args.registry.read_bytes().decode("utf-8")
    args.registry.write_bytes(replace_block(source, render_block(tables)).encode("utf-8"))
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_bytes(render_evidence(entities, digest, rules).encode("utf-8"))
    for _group, table, _heading in TABLES:
        entries = tables[table]
        print(f"{table}: {len(entries)} entities, {sum(len(aliases) for aliases in entries.values())} aliases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `C:\Python314\python.exe -m pytest tests/test_build_lender_registry.py tests/test_lender_registry_drift.py tests/test_lender_ledger.py -q -p no:cacheprovider`
Expected: 176 passed (33 + 3 + 140). If the ledger is already on the branch, the result is `3 failed, 173 passed`: the three drift tests fail until Task 9 renders the ledger. That is expected; go on.

Run: `C:\Python314\python.exe -m pytest tests/test_classification_registry_groups.py tests/test_no_statement_hardcodes.py -q -p no:cacheprovider`
Expected: `1 failed, 104 passed`. The failure is the known `test_no_literal_account_numbers_in_ocr`.

Run: `C:\Python314\python.exe -m tools.build_lender_registry --check; $LASTEXITCODE`
Expected, while the ledger is not on the branch: `refused: <repository>\docs\lender-registry-ledger.json does not exist; the orchestrator's consolidation workflow commits it (contract C10)`, then `2`.

- [ ] **Step 9: Commit**

```powershell
git add analysis/classification_registry.py tools/lender_ledger.py tools/build_lender_registry.py tests/test_build_lender_registry.py tests/test_lender_registry_drift.py
git commit -m "tools: lender ledger command line, hand-kept validator inputs and the drift test (contract C10)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 8: The alias-collision audit

> **Amended after review (fix round 1, 2026-09-25).** `payee_key` falls back to the fixed `NO_PAYEE_WORDS`, never to descriptor text, which could carry an account number. Step 4 counts 23 tests, and 243 for every S1 test so far (Tasks 5-7 as amended for the owner's ruling of 2026-09-25 and its review).

**Files:**
- Create: `tools/lender_alias_audit.py`
- Test: `tests/test_lender_alias_audit.py`

**Interfaces:**
- Consumes:
  - `AliasIndex` (Task 3);
  - `PAYEE_GROUP_REGISTRIES`, `PREMIUM_FINANCE_ALIASES`, `BANK_NAME_ALIASES`, `CARD_ISSUER_CONTEXT_ALIASES` and `POTENTIAL_LENDER_ALIASES` (Task 2's structure, Task 9's content);
  - `FINANCING_STATES` (Task 1) and `ORG_CUES` (Task 5);
  - `webapp.artifact_cache.ArtifactCache` (tests only, to write fabricated cache entries).
- Produces:
  - `EARLIER_RULE_STATES`, `VOCAB` and `NO_PAYEE_WORDS`;
  - `AuditPass(index: AliasIndex, needs: re.Pattern[str] | None = None)`;
  - `CachedRow(analysis: str, description: str, amount: float, stored: str, posted: bool = True)`;
  - `payee_key(text: str) -> str`, which returns `NO_PAYEE_WORDS` when no name word survives, never descriptor text;
  - `default_passes() -> tuple[AuditPass, ...]`, whose five passes are premium financing, the known-payee matcher, the bank name (needs loan wording), the card context (needs card or payment wording) and the potential registry;
  - `takes(state: str, row: CachedRow) -> bool`;
  - `cached_rows(data_dir: Path, limit: int | None = None) -> Iterator[CachedRow]`;
  - `audit(rows, passes) -> dict`, shaped `state -> alias -> {entity, keys: {key: {rows, taken_rows, debit_rows, credit_rows, analyses}}}`;
  - `needs_review(alias: str, entity: str, key: str) -> bool` (Decision 9);
  - `review(report: dict, decisions: dict) -> tuple[list[dict], list[dict]]`, which returns (denied, undecided);
  - `lost_matches(before: dict, after: dict, decisions: dict) -> list[dict]` (Decision 15), each `{entity, key, before, after}`;
  - `main(argv) -> int`, with the options `--data-dir`, `--review`, `--out`, `--strict`, `--limit` and `--before`, and exit codes 0, 1 and 2. The report file holds `aliases`, `denied`, `undecided` and `lost`.
  - The review file format: `{"deny": [{"key": str, "alias"?: str, "entity"?: str, "why"?: str}], "allow": [...]}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_lender_alias_audit.py`:

```python
"""tools/lender_alias_audit.py over a fabricated artifact cache (spec section 5)."""
from __future__ import annotations

import json

import pytest

from analysis.payee_matcher import AliasIndex
from tools import lender_alias_audit as audit_tool
from webapp.artifact_cache import ArtifactCache

PASSES = (
    audit_tool.AuditPass(AliasIndex({"premium_financing": {"Hollin Premium Finance": ("HOLLIN PFC",)}},
                                    run_together=False)),
    audit_tool.AuditPass(AliasIndex({
        "confirmed_lender": {"Quillon Funding": ("QUILLON FUNDING", "QUILLON")},
        "line_of_credit": {"Brambleway Capital": ("BRAMBLEWAY CAPITAL",)},
        "lease_or_rental": {"Westfen Leasing": ("WESTFEN LEASING",)},
    })),
    audit_tool.AuditPass(AliasIndex({"bank_name": {"Oxbow Bank": ("OXBOW",)}}, run_together=False),
                         audit_tool._LOAN_WORDING),
)
#: The same passes after the ledger dropped the bare alias QUILLON.
PASSES_WITHOUT_BARE_QUILLON = (
    PASSES[0],
    audit_tool.AuditPass(AliasIndex({
        "confirmed_lender": {"Quillon Funding": ("QUILLON FUNDING",)},
        "line_of_credit": {"Brambleway Capital": ("BRAMBLEWAY CAPITAL",)},
        "lease_or_rental": {"Westfen Leasing": ("WESTFEN LEASING",)},
    })),
    PASSES[2],
)
ALLOW_THE_REST = [{"key": "CORPORATE", "why": "channel words only"},
                  {"entity": "Oxbow Bank", "key": "OXBOW LOAN", "why": "the bank's own loan"}]
DENY_THE_BAKERY = [{"alias": "QUILLON", "entity": "Quillon Funding", "key": "QUILLON BAKERY",
                    "why": "a bakery, not the funder"}]


def _row(description, amount, classification="other", **extra):
    return {"original_description": description, "amount": amount, "classification": classification, **extra}


def _cache(tmp_path):
    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("a" * 64, "settings", {"classifications": [
        _row("ACH DEBIT QUILLON FUNDING DES PAYMENT", -100.0, "confirmed_lender"),
        _row("ORIG CO NAME QUILLON BAKERY ORIG ID 99", -12.0, "pos"),
        _row("QUILLON FUNDING DES TRANSFER FEE", -5.0, "fee"),
        _row("BRAMBLEWAY CAPITAL LOAN PROCEEDS", 900.0),
        _row("WESTFEN LEASING REFUND CREDIT", 40.0),
        _row("HOLLIN PFC PREMIUM", -80.0, "insurance"),
        _row("OXBOW LOAN PAYMENT", -60.0),
        _row("OXBOW MARKET GROCERIES", -9.0, "pos"),
        _row("MOBILE DEPOSIT", 40.0),
    ]})
    cache.put_analysis("b" * 64, "settings", {"accounts": [{"classifications": [
        _row("ACH DEBIT QUILLON FUNDING DES PAYMENT", -100.0, "confirmed_lender"),
        _row("CORPORATE ACH QUILLON FUNDING", -100.0, "confirmed_lender"),
        _row("ACH DEBIT QUILLON FUNDING DES PENDING", -100.0, "other", is_posted=False),
    ]}]})
    return tmp_path / "data"


def _report(tmp_path):
    return audit_tool.audit(audit_tool.cached_rows(_cache(tmp_path)), PASSES)


def test_payee_keys_skip_channel_words_and_stop_at_field_labels():
    assert audit_tool.payee_key("ACH DEBIT QUILLON FUNDING DES PAYMENT") == "QUILLON FUNDING"
    assert audit_tool.payee_key("ORIG CO NAME QUILLON BAKERY ORIG ID 99") == "QUILLON BAKERY"
    assert audit_tool.payee_key("CHECKCARD 0102 BRAMBLEWAY CAPITAL LOAN PROCEEDS") == "BRAMBLEWAY CAPITAL LOAN"


def test_a_descriptor_without_payee_words_gets_a_fixed_key_and_never_its_text():
    assert audit_tool.payee_key("ACH DEBIT 0012345678 PAYMENT") == "<no payee words>"
    row = audit_tool.CachedRow("c" * 64, "ORIG CO NAME 7777777 ORIG ID QUILLON FUNDING", -10.0, "other")
    report = audit_tool.audit([row], PASSES)
    assert list(report["confirmed_lender"]["QUILLON FUNDING"]["keys"]) == ["<no payee words>"]
    assert audit_tool.needs_review("QUILLON FUNDING", "Quillon Funding", "<no payee words>")


def test_the_audit_replays_the_rule_order_and_counts_only_taken_rows_as_taken(tmp_path):
    report = _report(tmp_path)
    assert report == {
        "bank_name": {"OXBOW": {"entity": "Oxbow Bank", "keys": {
            "OXBOW LOAN": {"rows": 1, "taken_rows": 1, "debit_rows": 1, "credit_rows": 0, "analyses": 1}}}},
        "confirmed_lender": {
            "QUILLON": {"entity": "Quillon Funding", "keys": {
                "QUILLON BAKERY": {"rows": 1, "taken_rows": 1, "debit_rows": 1, "credit_rows": 0, "analyses": 1}}},
            "QUILLON FUNDING": {"entity": "Quillon Funding", "keys": {
                "QUILLON FUNDING": {"rows": 4, "taken_rows": 2, "debit_rows": 4, "credit_rows": 0, "analyses": 2},
                "CORPORATE": {"rows": 1, "taken_rows": 1, "debit_rows": 1, "credit_rows": 0, "analyses": 1}}},
        },
        "lease_or_rental": {"WESTFEN LEASING": {"entity": "Westfen Leasing", "keys": {
            "WESTFEN LEASING REFUND": {"rows": 1, "taken_rows": 0, "debit_rows": 0, "credit_rows": 1,
                                       "analyses": 1}}}},
        "line_of_credit": {"BRAMBLEWAY CAPITAL": {"entity": "Brambleway Capital", "keys": {
            "BRAMBLEWAY CAPITAL LOAN": {"rows": 1, "taken_rows": 1, "debit_rows": 0, "credit_rows": 1,
                                        "analyses": 1}}}},
        "premium_financing": {"HOLLIN PFC": {"entity": "Hollin Premium Finance", "keys": {
            "HOLLIN PFC PREMIUM": {"rows": 1, "taken_rows": 1, "debit_rows": 1, "credit_rows": 0, "analyses": 1}}}},
    }


@pytest.mark.parametrize("alias,entity,key,expected", [
    ("QUILLON", "Quillon Funding", "QUILLON BAKERY", True),
    ("QUILLON", "Quillon Funding", "QUILLON FUNDING", True),
    ("QUILLON", "Quillon Funding", "QUILLON", False),
    ("QUILLON FUNDING", "Quillon Funding", "QUILLON FUNDING", False),
    ("QUILLON FUNDING", "Quillon Funding", "QUILLONFUNDING", False),
    ("QUILLON FUNDING", "Quillon Funding", "QUILLON FUNDING LLC", False),
    ("QUILLON FUNDING", "Quillon Funding", "QUILLON FUNDING BAKERY", True),
    ("QUILLON FUNDING", "Quillon Funding", "JOURNEY QUILLON FUNDING", True),
    ("QUILLON FUNDING", "Quillon Funding", "CORPORATE", True),
    ("QUILLON FUNDING", "Quillon Funding", "CORP", True),
    ("HOLLIN PFC", "Hollin Premium Finance", "HOLLIN PFC PREMIUM", False),
    ("BRAMBLEWAY CAPITAL", "Brambleway Capital", "BRAMBLEWAY CAPITAL LOAN", False),
])
def test_a_taken_match_needs_review_when_its_key_may_name_someone_else(alias, entity, key, expected):
    assert audit_tool.needs_review(alias, entity, key) is expected


def test_review_separates_denied_matches_from_undecided_matches_that_need_review(tmp_path):
    denied, undecided = audit_tool.review(_report(tmp_path), {"deny": DENY_THE_BAKERY,
                                                             "allow": [{"key": "CORPORATE"}]})
    assert [(row["alias"], row["key"], row["taken_rows"]) for row in denied] == [("QUILLON", "QUILLON BAKERY", 1)]
    assert [(row["alias"], row["key"], row["needs_review"]) for row in undecided] == [("OXBOW", "OXBOW LOAN", True)]


def _run(tmp_path, monkeypatch, decisions, *extra, passes=PASSES):
    monkeypatch.setattr(audit_tool, "default_passes", lambda: passes)
    review_file = tmp_path / "local" / "review.json"
    review_file.parent.mkdir(parents=True, exist_ok=True)
    review_file.write_text(json.dumps(decisions), encoding="utf-8")
    out = tmp_path / "local" / "audit.json"
    code = audit_tool.main(["--data-dir", str(_cache(tmp_path)), "--review", str(review_file),
                            "--out", str(out), *extra])
    return code, out


def test_a_denied_collision_that_still_takes_a_row_fails_the_audit(tmp_path, monkeypatch, capsys):
    code, out = _run(tmp_path, monkeypatch, {"deny": DENY_THE_BAKERY, "allow": []})
    assert code == 1
    printed = capsys.readouterr().out
    assert ("taken matches: 6, of which need review: 3; denied matches: 1; undecided: 2" in printed)
    assert "COLLISION 'QUILLON' (Quillon Funding, confirmed_lender) matches payee key 'QUILLON BAKERY'" in printed
    text = out.read_text(encoding="utf-8")
    assert "DES PAYMENT" not in text and "ORIG ID" not in text and "MOBILE DEPOSIT" not in text


def test_a_denied_pair_whose_rows_an_earlier_rule_keeps_does_not_fail(tmp_path, monkeypatch):
    decisions = {"deny": [{"alias": "WESTFEN LEASING", "key": "WESTFEN LEASING REFUND"}], "allow": []}
    assert _run(tmp_path, monkeypatch, decisions)[0] == 0


def test_strict_fails_until_every_match_that_needs_review_has_a_decision(tmp_path, monkeypatch):
    assert _run(tmp_path, monkeypatch, {"deny": [], "allow": []})[0] == 0
    assert _run(tmp_path, monkeypatch, {"deny": [], "allow": []}, "--strict")[0] == 1
    # QUILLON -> QUILLON BAKERY still needs a decision.
    assert _run(tmp_path, monkeypatch, {"deny": [], "allow": ALLOW_THE_REST}, "--strict")[0] == 1
    # Decided as a collision, but the alias still takes the bakery's row.
    assert _run(tmp_path, monkeypatch, {"deny": DENY_THE_BAKERY, "allow": ALLOW_THE_REST}, "--strict")[0] == 1
    # The ledger dropped the bare alias: zero denied and zero undecided.
    code, out = _run(tmp_path, monkeypatch, {"deny": DENY_THE_BAKERY, "allow": ALLOW_THE_REST}, "--strict",
                     passes=PASSES_WITHOUT_BARE_QUILLON)
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["denied"] == [] and report["undecided"] == []


def test_lost_matches_are_the_rows_an_entity_no_longer_takes_outside_denied_pairs():
    rows = [
        audit_tool.CachedRow("a" * 64, "ORIG CO NAME QUILLON BAKERY ORIG ID 99", -12.0, "pos"),
        audit_tool.CachedRow("a" * 64, "ACH DEBIT QUILLON LLC PAYMENT", -50.0, "other"),
        audit_tool.CachedRow("b" * 64, "ACH DEBIT QUILLON FUNDING DES PAYMENT", -100.0, "confirmed_lender"),
    ]
    before = audit_tool.audit(rows, PASSES)
    after = audit_tool.audit(rows, PASSES_WITHOUT_BARE_QUILLON)
    decisions = {"deny": DENY_THE_BAKERY, "allow": [{"entity": "Quillon Funding", "key": "QUILLON LLC"}]}
    assert audit_tool.lost_matches(before, after, decisions) == [
        {"entity": "Quillon Funding", "key": "QUILLON LLC", "before": 1, "after": 0}
    ]
    assert audit_tool.lost_matches(before, before, decisions) == []
    intended = {"deny": [*DENY_THE_BAKERY, {"entity": "Quillon Funding", "key": "QUILLON LLC"}], "allow": []}
    assert audit_tool.lost_matches(before, after, intended) == []


def test_a_ledger_change_that_takes_rows_from_an_entity_without_a_decision_fails(tmp_path, monkeypatch, capsys):
    decisions = {"deny": DENY_THE_BAKERY, "allow": ALLOW_THE_REST}
    _code, first = _run(tmp_path, monkeypatch, decisions, "--strict")
    previous = tmp_path / "local" / "previous.json"
    previous.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
    capsys.readouterr()
    code, out = _run(tmp_path, monkeypatch, decisions, "--strict", "--before", str(previous),
                     passes=PASSES_WITHOUT_BARE_QUILLON)
    assert code == 0 and json.loads(out.read_text(encoding="utf-8"))["lost"] == []
    assert "lost matches: 0" in capsys.readouterr().out
    allowed = {"deny": [], "allow": [*ALLOW_THE_REST, {"entity": "Quillon Funding", "key": "QUILLON BAKERY"}]}
    code, out = _run(tmp_path, monkeypatch, allowed, "--strict", "--before", str(previous),
                     passes=PASSES_WITHOUT_BARE_QUILLON)
    assert code == 1
    assert "LOST 'Quillon Funding' payee key 'QUILLON BAKERY': 1 taken rows before, 0 now" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))["lost"] == [
        {"entity": "Quillon Funding", "key": "QUILLON BAKERY", "before": 1, "after": 0}
    ]


def test_the_audit_refuses_a_report_inside_the_repository_and_a_directory_without_a_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_tool, "default_passes", lambda: PASSES)
    review_file = tmp_path / "review.json"
    review_file.write_text('{"deny": [], "allow": []}', encoding="utf-8")
    inside = audit_tool.ROOT / "alias-audit-must-not-exist.json"
    assert audit_tool.main(["--data-dir", str(_cache(tmp_path)), "--review", str(review_file),
                            "--out", str(inside)]) == 2
    assert not inside.exists()
    assert audit_tool.main(["--data-dir", str(_cache(tmp_path)), "--review", str(review_file),
                            "--out", str(tmp_path / "out.json"), "--before", str(inside)]) == 2
    assert not (tmp_path / "out.json").exists()
    assert audit_tool.main(["--data-dir", str(tmp_path / "empty"), "--review", str(review_file),
                            "--out", str(tmp_path / "out.json")]) == 2


def test_only_the_descriptor_rule_passes_need_loan_or_card_wording():
    passes = audit_tool.default_passes()
    assert [audit_pass.needs is not None for audit_pass in passes] == [False, False, True, True, False]
    assert passes[2].needs.search("OXBOW LOAN PAYMENT") and not passes[2].needs.search("OXBOW MARKET")
    assert passes[3].needs.search("OXBOW CARD PMT") and not passes[3].needs.search("OXBOW MARKET")
    # S2's own step-8 wording and order: an earlier descriptor rule decides the row before the bank-name
    # or the card-payment rule reads it, and the card rule reads S2's whole card-payment wording.
    assert passes[2].needs.search("OXBOW LOANS 0001")
    for decided_first in ("OXBOW LOC LOAN PAYMENT", "OXBOW LINE OF CREDIT LOAN", "OXBOW MORTGAGE LOAN",
                          "OXBOW AUTO LOAN PAYMENT", "OXBOW VEHICLE LOAN", "OXBOW LOANED"):
        assert not passes[2].needs.search(decided_first), decided_first
    for card_wording in ("KESTREL CRCARD 0001", "KESTREL AUTO PAY 0001", "KESTREL CREDIT CARD 0001",
                         "KESTREL EPAYMENT 0001", "KESTREL PROPERTY RENTAL PAYMENT"):
        assert passes[3].needs.search(card_wording), card_wording
    for decided_first in ("KESTREL LOC PAYMENT", "KESTREL LEASE PAYMENT", "KESTREL AUTO LEASE PMT",
                          "KESTREL RENTAL PMT", "KESTREL AUTO SHOP"):
        assert not passes[3].needs.search(decided_first), decided_first
```

- [ ] **Step 2: Run it to verify it fails**

Run: `C:\Python314\python.exe -m pytest tests/test_lender_alias_audit.py -q -p no:cacheprovider`
Expected: 1 error during collection: `ImportError: cannot import name 'lender_alias_audit' from 'tools' (unknown location)`.

- [ ] **Step 3: Write the implementation**

Create `tools/lender_alias_audit.py`:

```python
"""Alias collision audit over the local artifact cache (spec section 5). Local only; never run in CI.

Every alias the classifier consults is replayed over the cached rows, in the classifier's order
(spec section 4.3): premium financing (the insurance rule), the known-payee matcher, the bank-name
and card-issuer context tables (the descriptor rules, which need loan or card wording), and the
potential registry. For each alias the audit reports the payee keys whose rows it wins, with row and
analysis counts and no descriptor text. A row counts as taken when the rule order gives it to that
alias: rows a rule ahead of the matcher keeps (a fee, a transfer, insurance and the other states of
section 4.3 steps 1-6) are counted but never taken.

A taken match needs review (``needs_review``) when the payee key may name someone else:
  * the alias is a single word and the key is not exactly that word;
  * the key holds a word that is not in the alias, not in the entity's name (nor a run-together form of
    either), not a channel or descriptor word (VOCAB) and not an organisation word (ORG_CUES);
  * the key shares no word with the alias at all.
A reviewed allow/deny file records the decisions. The audit fails when a denied pair still wins a row,
and --strict also fails while a match that needs review has no decision. With --before <an earlier report
of the same cache>, it also fails on every (entity, payee key) that takes fewer rows than before, leaving out
denied pairs: a ledger change that dropped or narrowed an alias must not take the entity's own rows with it.
Payee keys come from customer statements, so the review file and the reports stay outside the repository.

Usage, from the repository root:
    python -m tools.lender_alias_audit --data-dir <webapp_data> --review <file> --out <file> [--strict]
        [--limit N] [--before <earlier report>]

Exit codes: 0 no denied match, no lost match (and, with --strict, nothing undecided); 1 otherwise; 2 refused.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.classification_registry import (  # noqa: E402
    BANK_NAME_ALIASES,
    CARD_ISSUER_CONTEXT_ALIASES,
    PAYEE_GROUP_REGISTRIES,
    POTENTIAL_LENDER_ALIASES,
    PREMIUM_FINANCE_ALIASES,
)
from analysis.description_text import normalize_transaction_description as normalize  # noqa: E402
from analysis.flag_groups import FINANCING_STATES  # noqa: E402
from analysis.payee_matcher import AliasIndex  # noqa: E402
from tools.lender_ledger import _CARD_PAYMENT_WORDING, ORG_CUES  # noqa: E402

#: Stored states that a rule ahead of the known-payee matcher keeps (spec section 4.3 steps 2-6). POS and
#: ATM are not here: a known payee paid by card bypasses them (D8).
EARLIER_RULE_STATES = frozenset(
    {"nsf_or_return", "refund_or_reversal", "insurance", "fee", "transfer", "tax", "payroll", "utility"}
)
#: S2's step-8 rules that decide a row before its bank-name rule (spec section 4.3 step 8): LOC, mortgage and
#: vehicle wording, as S2's _LINE_OF_CREDIT_PATTERNS, _MORTGAGE_PATTERNS and _VEHICLE_FINANCING_PATTERNS.
_DECIDED_BEFORE_BANK_NAME = (
    r"\bLOC\b|\bLINE OF CREDIT\b|\bMORTGAGES?\b"
    r"|\b(?:AUTO|CAR) (?:LOAN|LOANS|LEASE|FINANCE|FINANCING)\b"
    r"|\bVEHICLE (?:LOAN|LEASE|PAYMENT|PMT|PYMT|FINANCE|FINANCING)\b"
)
#: S2's step-8 rules that decide a row before its card-payment rule: the ones above, the statement bank's own
#: loan transfer and lease or rental wording (S2's _OWN_LOAN_TRANSFER_PATTERNS and _LEASE_RENTAL_PATTERNS).
_DECIDED_BEFORE_CARD = _DECIDED_BEFORE_BANK_NAME + (
    r"|\b(?:TRANSFER|TFR) TO (?:MY |YOUR )?LOAN\b|\bLOAN (?:TRANSFER|TFR)\b"
    r"|\bLEAS(?:E|ES|ED|ING)\b|(?<!PROPERTY )\bRENTALS?\b|\bEQUIPMENT (?:RENT|PAYMENT)\b"
)
#: S2's bank-name rule (D5): a listed bank with LOAN or LOANS (S2's _LOAN_WORD_PATTERNS; normalization has
#: already turned LN into LOAN), on a row that no earlier step-8 rule decided.
_LOAN_WORDING = re.compile(r"^(?!.*(?:" + _DECIDED_BEFORE_BANK_NAME + r")).*\bLOANS?\b")
#: S2's card-payment rule: a listed issuer with S2's card or payment wording (_CARD_PAYMENT_CONTEXT_PATTERNS,
#: the same words the validator requires of every CARD_ISSUER_ALIASES alias), on a row that no earlier
#: step-8 rule decided.
_CARD_WORDING = re.compile(r"^(?!.*(?:" + _DECIDED_BEFORE_CARD + r")).*" + _CARD_PAYMENT_WORDING.pattern)
#: Leading bank-channel words a payee key skips (the research payee index used the same rule).
_LEADING = re.compile(
    r"^(?:(?:CHECK ?CARD|CHECKCARD|PURCHASE|POS|DEBIT|CARD|ACH|WEB|PPD|CCD|TEL|ELECTRONIC|PREAUTHORIZED|"
    r"PRE AUTHORIZED|ONLINE|PAYMENT TO|PAYMENTS|PAYMENT|PMTS|PYMTS|PMT|BILL ?PAY(?:MENT)?|WITHDRAWAL|EXTERNAL|"
    r"RECURRING|AUTOPAY|AUTO PAY|DDA|TRANSACTION|WITHDRWL|WD|DIRECT DEBIT|DIRECT DEB|BUSINESS PAD|PAD|EFT|"
    r"PREAUTH|MISC|ELECTRONIC PMT|ELEC|SEND|TO|FROM|IAT|CORP|ACH DEBIT|ACH PMT|ACH PAYMENT|AUTHORIZED ON|"
    r"RECURRING PAYMENT|[0-9]+|[A-Z]?[0-9][A-Z0-9]*)\s+)+"
)
_CHASE_ORIGINATOR = re.compile(
    r"\bORIG CO NAME (.+?)(?: ORIG ID| DESC DATE| CO ENTRY| SEC| TRACE| EED| IND ID| IND NAME|$)"
)
_KEY_STOP = frozenset({
    "DES", "ID", "INDN", "ENTRY", "REF", "TRACE", "SEC", "ORIG", "CKCD", "CT", "CONF", "TRN", "IND", "EED",
    "PAYMENT", "PMT", "PYMT", "PAYMT", "DEBIT", "ACH", "WEB", "CCD", "PPD", "TEL", "PURCHASE", "AUTOPAY",
    "EPAY", "EPAYMENT", "DIRECT", "WITHDRAWAL", "SETTLEMENT", "COLLECTION", "DEBITS", "REMITTANCE", "XFER",
})
#: Channel and descriptor words that name no one: a payee key may hold them beside the payee's name.
VOCAB = frozenset("""
ACCEPTANCE ACH ADV ADVANCE ADVANCES AND AT AUTHORIZATION AUTHORIZED AUTO AUTOMATIQUE AUTOPAY BANK BANKING
BILL BILLPAY BUS BUSINESS BY CANADA CAP CAPITAL CARD CC CCD CHG CO COLL COLLECTION COLLECTIONS COM COMMERCIAL
COMPTE CORP CR CRD CREDIT D DB DD DEBIT DES DIRECT DIV DIVERS DPA DRAFT DRAFTS EDI EFT ENT ENTREPRISE ENTRY
EPAY EPAYMENT EQUIP EQUIPMENT FIN FINANCE FINANCIAL FINANCING FINL FOR FUND FUNDING GROUP HOLDINGS IN INC
INSTALLMENT INSTL INTEREST INTERNET ITEMS LEASE LEASING LENDING LL LLC LOAN LOANS LP LTD MC MCA MISC MORTGAGE
MOTOR MSP MTG NA NAME OF ON ONLINE ORIG PAD PAY PAYMENT PAYMENTS PAYOUT PMT PMTS PPD PRE PREAUTH PRELEVEMENT
PRET PROCEEDS PROGRAM PYMNT PYMNTS PYMT RECURRING REMIT RETAIL RLS SCHEDULED SERVICES SERVICING SVC SVCS TEL
THE TYPE US USA WEB WITHDRAWAL
""".split())
#: The payee key of a descriptor in which no name word survives: a fixed placeholder, never descriptor text
#: (which may carry an account number). ``needs_review`` flags it, so every such match gets a decision.
NO_PAYEE_WORDS = "<no payee words>"


@dataclass(frozen=True)
class AuditPass:
    """One rule of the classifier that reads a registry: its index and the wording it needs, if any."""

    index: AliasIndex
    needs: re.Pattern[str] | None = None


@dataclass(frozen=True)
class CachedRow:
    analysis: str
    description: str
    amount: float
    stored: str
    posted: bool = True


def payee_key(text: str) -> str:
    """The counterparty key of a normalized descriptor: up to three name words after the channel words, or
    NO_PAYEE_WORDS when none survives."""
    originator = _CHASE_ORIGINATOR.search(text)
    base = _LEADING.sub("", (originator.group(1) if originator else text) + " ").strip()
    words: list[str] = []
    for word in base.split():
        if word in _KEY_STOP or word.startswith("XXXX"):
            if words:
                break
            continue
        if any(char.isdigit() for char in word):
            continue
        words.append(word)
        if len(words) == 3:
            break
    return " ".join(words) or NO_PAYEE_WORDS


def default_passes() -> tuple[AuditPass, ...]:
    """The registries the classifier reads, in its rule order (spec section 4.3 steps 4, 7, 8 and 11)."""
    return (
        AuditPass(AliasIndex({"premium_financing": PREMIUM_FINANCE_ALIASES}, run_together=False)),
        AuditPass(AliasIndex(PAYEE_GROUP_REGISTRIES)),
        AuditPass(AliasIndex({"bank_name": BANK_NAME_ALIASES}, run_together=False), _LOAN_WORDING),
        AuditPass(AliasIndex({"card_context": CARD_ISSUER_CONTEXT_ALIASES}, run_together=False), _CARD_WORDING),
        AuditPass(AliasIndex({"potential_lender": POTENTIAL_LENDER_ALIASES}, run_together=False)),
    )


def takes(state: str, row: CachedRow) -> bool:
    """Whether the classifier's rule order gives the row to an alias of ``state`` (spec sections 4.3, 4.4)."""
    if not row.posted or row.stored in ("nsf_or_return", "refund_or_reversal"):
        return False
    if state == "premium_financing":
        return True
    if row.stored in EARLIER_RULE_STATES:
        return False
    if state in PAYEE_GROUP_REGISTRIES:
        return row.amount < 0 or state in FINANCING_STATES
    return row.amount < 0 and row.stored not in ("pos", "atm")


def _classification_lists(node) -> Iterator[list]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "classifications" and isinstance(value, list):
                yield value
            else:
                yield from _classification_lists(value)
    elif isinstance(node, list):
        for value in node:
            yield from _classification_lists(value)


def cached_rows(data_dir: Path, limit: int | None = None) -> Iterator[CachedRow]:
    """Every row of the latest cached analysis of each input. Opens the cache database read-only and never
    writes to the data directory."""
    database = data_dir / "webapp.db"
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    try:
        latest = connection.execute(
            "SELECT a.input_sha256, a.artifact_path FROM artifact_cache a JOIN ("
            " SELECT input_sha256, MAX(created_at) AS newest FROM artifact_cache"
            " WHERE stage = 'analysis' GROUP BY input_sha256) b"
            " ON a.input_sha256 = b.input_sha256 AND a.created_at = b.newest"
            " WHERE a.stage = 'analysis' ORDER BY a.input_sha256"
        ).fetchall()
    finally:
        connection.close()
    for number, (sha, relative) in enumerate(latest):
        if limit is not None and number >= limit:
            return
        try:
            payload = json.loads((data_dir / "artifacts" / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for rows in _classification_lists(payload.get("artifact")):
            for row in rows:
                amount = row.get("amount") if isinstance(row, dict) else None
                if isinstance(amount, (int, float)):
                    yield CachedRow(sha, str(row.get("original_description") or ""), float(amount),
                                    str(row.get("classification") or "other"), row.get("is_posted") is not False)


def audit(rows: Iterable[CachedRow], passes: tuple[AuditPass, ...]) -> dict:
    """state -> alias -> {entity, keys: {payee key: {rows, taken_rows, debit_rows, credit_rows, analyses}}}.
    The first pass that matches a row claims it, as the first rule that matches does. No descriptor text."""
    found: dict = {}
    analyses: dict = defaultdict(set)
    for row in rows:
        text = normalize(row.description)
        for audit_pass in passes:
            if audit_pass.needs is not None and not audit_pass.needs.search(text):
                continue
            match = audit_pass.index.match(text)
            if match is None:
                continue
            key = payee_key(text)
            entry = found.setdefault(match.state, {}).setdefault(match.alias, {"entity": match.entity, "keys": {}})
            counts = entry["keys"].setdefault(
                key, {"rows": 0, "taken_rows": 0, "debit_rows": 0, "credit_rows": 0, "analyses": 0})
            counts["rows"] += 1
            counts["taken_rows"] += int(takes(match.state, row))
            counts["debit_rows" if row.amount < 0 else "credit_rows"] += 1
            analyses[(match.state, match.alias, key)].add(row.analysis)
            counts["analyses"] = len(analyses[(match.state, match.alias, key)])
            break
    return {state: dict(sorted(aliases.items())) for state, aliases in sorted(found.items())}


def _fires(entry: dict, alias: str, entity: str, key: str) -> bool:
    return entry.get("key") == key and (
        entry.get("alias") is None or normalize(entry["alias"]) == normalize(alias)
    ) and (entry.get("entity") is None or entry["entity"] == entity)


def _joined_runs(words: list[str]) -> set[str]:
    """Every run-together form of two or more consecutive words."""
    return {"".join(words[start:end]) for start in range(len(words)) for end in range(start + 2, len(words) + 1)}


def needs_review(alias: str, entity: str, key: str) -> bool:
    """Whether the payee key of a taken match may name someone other than the entity (see the module doc)."""
    alias_words = normalize(alias).split(" ")
    name_words = normalize(entity).split(" ")
    key_words = key.split(" ")
    if len(alias_words) == 1 and key != alias_words[0]:
        return True
    known = set(alias_words) | set(name_words) | _joined_runs(alias_words) | _joined_runs(name_words)
    if any(word not in known and word not in VOCAB and word not in ORG_CUES for word in key_words):
        return True
    return not set(alias_words) & set(key_words) and "".join(alias_words) not in key.replace(" ", "")


def review(report: dict, decisions: dict) -> tuple[list[dict], list[dict]]:
    """(denied, undecided): the taken matches a deny decision names, and the taken matches that need review and
    have no decision. Each is {state, alias, entity, key, rows, taken_rows, analyses, needs_review}."""
    denied: list[dict] = []
    undecided: list[dict] = []
    for state, aliases in report.items():
        for alias, entry in aliases.items():
            for key, counts in entry["keys"].items():
                if not counts["taken_rows"]:
                    continue
                row = {"state": state, "alias": alias, "entity": entry["entity"], "key": key, "rows": counts["rows"],
                       "taken_rows": counts["taken_rows"], "analyses": counts["analyses"],
                       "needs_review": needs_review(alias, entry["entity"], key)}
                if any(_fires(d, alias, entry["entity"], key) for d in decisions.get("deny", [])):
                    denied.append(row)
                elif row["needs_review"] and not any(
                        _fires(a, alias, entry["entity"], key) for a in decisions.get("allow", [])):
                    undecided.append(row)
    return denied, undecided


def _taken_by_entity(report: dict, decisions: dict | None) -> dict[tuple[str, str], int]:
    """Taken rows per (entity, payee key); with ``decisions``, the rows of denied pairs are left out."""
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for aliases in report.values():
        for alias, entry in aliases.items():
            for key, counts in entry["keys"].items():
                if decisions is not None and any(
                        _fires(d, alias, entry["entity"], key) for d in decisions.get("deny", [])):
                    continue
                totals[(entry["entity"], key)] += counts["taken_rows"]
    return totals


def lost_matches(before: dict, after: dict, decisions: dict) -> list[dict]:
    """The (entity, payee key) pairs that take fewer rows in ``after`` than in ``before`` (two reports of the same
    cache), leaving out the rows of denied pairs: the rows a ledger change took from an entity without a
    decision. Each is {entity, key, before, after}, in entity and key order."""
    was = _taken_by_entity(before, decisions)
    now = _taken_by_entity(after, None)
    return [{"entity": entity, "key": key, "before": count, "after": now.get((entity, key), 0)}
            for (entity, key), count in sorted(was.items()) if now.get((entity, key), 0) < count]


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, required=True, help="the webapp data directory (read-only)")
    parser.add_argument("--review", type=Path, required=True, help="reviewed allow/deny file (outside the repo)")
    parser.add_argument("--out", type=Path, required=True, help="the report to write (outside the repo)")
    parser.add_argument("--strict", action="store_true",
                        help="also fail while a match that needs review has no decision")
    parser.add_argument("--limit", type=int, default=None, help="read only the first N analyses")
    parser.add_argument("--before", type=Path, default=None,
                        help="an earlier report of the same cache (outside the repo): fail on rows an entity lost")
    args = parser.parse_args(argv)
    for local in (args.review, args.out, *([args.before] if args.before else [])):
        if _inside(local, ROOT):
            print(f"refused: {local} is inside the repository; payee keys come from statements", file=sys.stderr)
            return 2
    if not (args.data_dir / "webapp.db").is_file():
        print(f"refused: {args.data_dir} holds no webapp.db", file=sys.stderr)
        return 2
    decisions = json.loads(args.review.read_text(encoding="utf-8"))
    report = audit(cached_rows(args.data_dir, args.limit), default_passes())
    denied, undecided = review(report, decisions)
    lost = []
    if args.before is not None:
        lost = lost_matches(json.loads(args.before.read_text(encoding="utf-8"))["aliases"], report, decisions)
    taken = [(alias, entry["entity"], key) for aliases in report.values() for alias, entry in aliases.items()
             for key, counts in entry["keys"].items() if counts["taken_rows"]]
    flagged = sum(needs_review(alias, entity, key) for alias, entity, key in taken)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"aliases": report, "denied": denied, "undecided": undecided, "lost": lost},
                                   indent=2, sort_keys=True) + "\n", encoding="utf-8")
    keys = sum(len(entry["keys"]) for aliases in report.values() for entry in aliases.values())
    print(f"aliases that matched: {sum(len(aliases) for aliases in report.values())}; payee keys: {keys}; "
          f"taken matches: {len(taken)}, of which need review: {flagged}; denied matches: {len(denied)}; "
          f"undecided: {len(undecided)}")
    for row in denied:
        print(f"COLLISION {row['alias']!r} ({row['entity']}, {row['state']}) matches payee key {row['key']!r}: "
              f"{row['taken_rows']} taken rows in {row['analyses']} analyses")
    if args.before is not None:
        print(f"lost matches: {len(lost)}")
        for row in lost:
            print(f"LOST {row['entity']!r} payee key {row['key']!r}: {row['before']} taken rows before, "
                  f"{row['after']} now")
    return 1 if denied or lost or (args.strict and undecided) else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `C:\Python314\python.exe -m pytest tests/test_lender_alias_audit.py -q -p no:cacheprovider`
Expected: 23 passed.

Run every S1 test so far: `C:\Python314\python.exe -m pytest tests/test_flag_groups.py tests/test_classification_registry_groups.py tests/test_payee_matcher.py tests/test_classifier_speed.py tests/test_lender_ledger.py tests/test_build_lender_registry.py tests/test_lender_registry_drift.py tests/test_lender_alias_audit.py -q -p no:cacheprovider`
Expected: 243 passed (5 + 21 + 15 + 3 + 140 + 33 + 3 + 23), or `3 failed, 240 passed` when the ledger is already on the branch (Task 7 Step 8). (Amended after the review of the owner's ruling of 2026-09-25; before the fix round and the ruling it read 197.)

- [ ] **Step 5: Commit**

```powershell
git add tools/lender_alias_audit.py tests/test_lender_alias_audit.py
git commit -m "tools: local alias-collision audit that replays the classifier rule order" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

---

### Task 9: Render the registry from the curated ledger

**Prerequisite:** "Prerequisite: the curated ledger" above. Without the ledger, or without the orchestrator's word that the owner has read the rendered lender list, stop and report; do not start this task.

**Files:**
- Add, when Step 1 brings it from `lender-detection`, or brings a revised ledger from the ref the orchestrator names: `docs/lender-registry-ledger.json`
- Modify (rendered): the GENERATED block of `analysis/classification_registry.py`
- Create (rendered): `docs/lender-registry-evidence.md`
- Test: `tests/test_lender_registry_content.py`

**Interfaces:**
- Consumes:
  - the ledger (the orchestrator's);
  - Tasks 5-7 (`validate`, `current_rules`, `owner_named_problems`, `main`);
  - `match_known_payee` and `registry_match` (Task 3);
  - `FINANCING_STATES` (Task 1).
- Produces:
  - the populated C2 tables, which S2 consumes;
  - the evidence ledger.

- [ ] **Step 1: Confirm the prerequisites**

Confirm that the orchestrator's message says the owner has read the rendered lender list. Then run:

```powershell
if (Test-Path docs/lender-registry-ledger.json) { "on this branch" } else { git cat-file -e lender-detection:docs/lender-registry-ledger.json 2>$null; if ($LASTEXITCODE -eq 0) { git checkout lender-detection -- docs/lender-registry-ledger.json; "brought from lender-detection" } else { "ledger absent" } }
```

Expected: `on this branch`, or `brought from lender-detection`.
- If it prints `ledger absent`, stop and report `Task 9 blocked: ledger absent` to the orchestrator.
- If the owner's read is not confirmed, stop and report `Task 9 blocked: owner read not confirmed`.

**On a rerun for a revised ledger** (Task 10 Step 4), the ledger is already on this branch, so the command above brings nothing. The orchestrator's message names the ref that holds the revised ledger, normally `lender-detection`, and confirms that the owner has read the changed entities. Bring it and check that it changed:

```powershell
git checkout <the ref the orchestrator named> -- docs/lender-registry-ledger.json
git diff --cached --stat -- docs/lender-registry-ledger.json
```

Expected: ` docs/lender-registry-ledger.json | <n> <+ and ->`, then ` 1 file changed, ...`. If nothing is printed, the ledger did not change: stop, and tell the orchestrator.

- [ ] **Step 2: Validate the ledger**

Run: `C:\Python314\python.exe -m tools.build_lender_registry --check; $LASTEXITCODE`
Expected:
- `ledger ok: <n> entities, sha256:<64 hex>`;
- one `move: <entity> (<today's list>): <was> -> <now>, <k> of today's aliases lost; why: <reason>` line per entity of today's registry that changes place or loses an alias;
- `0`.

Read every `move:` line. Each `why` must be about that move: the place it names, or the aliases it drops. If one is not, stop, and report the line to the orchestrator. The line carries ledger text only. Keep the `move:` lines for the hand-off (Task 10 Step 7).

If it exits `1`, stop, and report the `problem:` lines and the count to the orchestrator:
- The lines quote ledger names and aliases, which are the orchestrator's committed data, and they never quote a digit run.
- Do not edit the ledger to make it pass. The orchestrator fixes the ledger, and you rerun this task from Step 2.

- [ ] **Step 3: Watch the drift test fail**

Run: `C:\Python314\python.exe -m pytest tests/test_lender_registry_drift.py -q -p no:cacheprovider`
Expected: `3 failed`. The committed block is still the rendering of the empty ledger, and the evidence ledger does not exist yet.

On a rerun for a revised ledger, the committed files are the rendering of the previous ledger. At least `test_the_evidence_ledger_is_the_rendering_of_the_committed_ledger` fails, because the ledger's digest changed. The two block tests also fail when the revision changed a table. Skip Steps 4 and 5 on a rerun: the content test already exists.

- [ ] **Step 4: Write the content test**

The test restates "Prerequisite: the curated ledger" as the owner's rulings of 2026-09-25 amend it. Its `S2_TASK_0` rows are S2's Task 0 `OWNER_RULED` rows as the orchestrator amends them to those rulings (S1 never edits S2's plan): `AFC FUNDING CORP XPRESS PAY` is Floor plan, `SMARTPAY LEASING payment` replaces `SmartPay Sol debitpmt`, and `EBF HOLDINGS DEBIT 0001`, `CAPITAL INFUSION PAYMENT` and `BLUEVINE CAPITAL` are added. S2's amended `OWNER_RULED` also holds the Econolease, CMCA Finance and Lily Advance lender rows; the content test restates those three in `test_econolease_cmca_finance_and_lily_advance_are_counted_lenders_and_no_potential_alias`, which also checks that none is a potential alias. (Amended after the owner's rulings: the earlier version expected `AFC FUNDING CORP` as a lender, SmartPay on `SMARTPAY SOL`, Econolease and Clover Equipment as known payees outside the lenders, CMCA Finance and Lily Advance in the potential tier, and no premium alias equal to `FIRST INSURANCE`. Run on the ledger of those rulings, it failed those 7 cases; this version passes all 75.)

Create `tests/test_lender_registry_content.py`:

```python
"""Spec sections 2 and 5, and the S1 facts S2's Task 0 checks, on the registry rendered from the committed
ledger (contract C10), with the owner's rulings of 2026-09-25. The descriptors are fabricated around public
company names; none is statement text."""
from __future__ import annotations

import re

import pytest

from analysis import classification_registry as registry
from analysis.description_text import normalize_transaction_description as normalize
from analysis.flag_groups import FINANCING_STATES
from analysis.payee_matcher import match_known_payee, registry_match
from tools import build_lender_registry as builder
from tools import lender_ledger

DATA = lender_ledger.read_ledger(lender_ledger.LEDGER_PATH)
ENTITIES, SHAPE_PROBLEMS = lender_ledger.parse_ledger(DATA)
BY_NAME = {entity.entity: entity for entity in ENTITIES}
RULES = lender_ledger.current_rules()
EVIDENCE = builder.EVIDENCE_PATH.read_text(encoding="utf-8")
REGISTRY_TABLES = {table: getattr(registry, table) for _group, table, _heading in lender_ledger.TABLES}

#: The S2 plan's Task 0 Step 3 OWNER_RULED rows, as the owner's rulings of 2026-09-25 amend them (AFC FUNDING
#: CORP is floor plan; BLUEVINE CAPITAL and SMARTPAY LEASING are the owner-named spellings; EBF HOLDINGS is
#: merged into EVEREST BUSINESS FUNDING; CAPITAL INFUSION is an alternative position): (descriptor, entity, state).
S2_TASK_0 = (
    ("NMEF Funding 2025A payment", "NMEF", "confirmed_lender"),
    ("Navitas Credit Corp payment", "Navitas Credit Corp", "confirmed_lender"),
    ("Balboa Capital payment", "Balboa Capital", "confirmed_lender"),
    ("DIRECT DEB DELAGELANDEN LEASE", "De Lage Landen", "confirmed_lender"),
    ("CHECKCARD 0102 NMEF FUNDING", "NMEF", "confirmed_lender"),
    ("CHECK 1234 FORA FINANCIAL", "FORA FINANCIAL", "confirmed_lender"),
    ("CHECKCARD 0102 ONDECK CAPITAL", "ONDECK", "confirmed_lender"),
    ("Canacap payment", "CanaCap", "confirmed_lender"),
    ("CAN Capital loan payment", "CAN Capital", "confirmed_lender"),
    ("Direct Debit Business PAD Forward Funding", "Forward Funding", "confirmed_lender"),
    ("Direct Debit Business PAD Forward Financing", "Forward Financing", "confirmed_lender"),
    ("ACH DEBIT RAPID FINANCE PAYMENT", "RAPID FINANCE", "confirmed_lender"),
    ("Orig CO Name:Kapitus Descr:Payment ACH Debit", "KAPITUS", "confirmed_lender"),
    ("ACH DEBIT THE FUNDWORKS LLC PMT", "FUNDWORKS", "confirmed_lender"),
    ("EBF HOLDINGS DEBIT 0001", "EVEREST BUSINESS FUNDING", "confirmed_lender"),
    ("AFC FUNDING CORP XPRESS PAY", "AFC FUNDING CORP", "floor_plan_financing"),
    ("BDC loan payment", "BDC", "alternative_position"),
    ("CARD PURCHASE AFFIRMCOM 0001", "AFFIRM", "alternative_position"),
    ("ACH DEBIT INTUIT FINANCING 0001", "INTUIT FINANCING", "alternative_position"),
    ("SQUARE CAPITAL", "SQUARE CAPITAL", "alternative_position"),
    ("SHOPIFY CAPITAL PAYOUT", "SHOPIFY CAPITAL", "alternative_position"),
    ("PAYPAL WORKING CAPITAL", "PAYPAL WORKING CAPITAL", "alternative_position"),
    ("CAPITAL INFUSION PAYMENT", "CAPITAL INFUSION", "alternative_position"),
    ("BLUEVINE loan payment", "BLUEVINE", "line_of_credit"),
    ("BLUEVINE CAPITAL", "BLUEVINE", "line_of_credit"),
    ("FUNDBOX payment", "FUNDBOX", "line_of_credit"),
    ("KABBAGE payment", "KABBAGE", "line_of_credit"),
    ("External Withdrawal SNAP FINANCE - PAYMENT", "SNAP Finance", "lease_or_rental"),
    ("Progressive Leasing recurring purchase", "Progressive Leasing", "lease_or_rental"),
    ("SMARTPAY LEASING payment", "SmartPay", "lease_or_rental"),
)


def _known(descriptor):
    return match_known_payee(normalize(descriptor))


def _claimed_by(descriptor):
    """The rendered tables with an alias in the descriptor, whatever their context."""
    return [table for table, entries in REGISTRY_TABLES.items() if registry_match(normalize(descriptor), entries)]


def test_the_committed_ledger_passes_the_validator():
    assert SHAPE_PROBLEMS == []
    assert lender_ledger.validate(DATA, RULES) == []


def test_every_payee_the_owner_named_is_in_its_ruled_group_in_the_committed_registry():
    assert lender_ledger.owner_named_problems(REGISTRY_TABLES, registry.OWNER_NAMED_PAYEES) == []


@pytest.mark.parametrize("descriptor,entity,state", S2_TASK_0)
def test_the_known_payee_facts_s2_task_0_checks_hold(descriptor, entity, state):
    found = _known(descriptor)
    assert found is not None and (found.entity, found.state) == (entity, state), found


@pytest.mark.parametrize("descriptor", ["SBA LOAN PAYMENT", "SBA EIDL LOAN PAYMENT"])
def test_sba_loan_payments_are_alternative_positions(descriptor):
    found = _known(descriptor)
    assert found is not None and found.state == "alternative_position", found


@pytest.mark.parametrize("descriptor,state", [("NEXTGEAR CAPITAL PAYMENT", "floor_plan_financing"),
                                              ("RTS FINANCIAL PAYMENT", "factoring")])
def test_the_amendment_groups_s2_task_0_checks(descriptor, state):
    found = _known(descriptor)
    assert found is not None and found.state == state, found


@pytest.mark.parametrize("descriptor", ["IPFS CORP PMT", "FIRST INSURANCE FUNDING PMT"])
def test_premium_financiers_are_premium_finance_payees_and_no_known_payee(descriptor):
    assert registry_match(normalize(descriptor), registry.PREMIUM_FINANCE_ALIASES) is not None
    assert _known(descriptor) is None


@pytest.mark.parametrize("descriptor", ["SQUARE", "SHOPIFY", "PAYPAL", "STRIPE", "AMAZON",
                                        "CARD PURCHASE INTUIT QUICKBOOKS 0001"])
def test_bare_platform_names_are_no_known_payee(descriptor):
    assert _known(descriptor) is None


@pytest.mark.parametrize("descriptor", ["ACH Capital One TYPE: ONLINE PMT", "ATB Mastercard payment",
                                        "Office rent payment"])
def test_card_payments_and_rent_are_never_claimed_by_a_lender_or_financing_alias(descriptor):
    found = _known(descriptor)
    assert found is None or found.state == "credit_card_payment", found


def test_netcredit_is_a_financing_payee_named_netcredit():
    found = _known("NETCREDIT CCBANK-NTC loan proceeds")
    assert found is not None and found.entity == "NETCREDIT" and found.state in FINANCING_STATES, found


@pytest.mark.parametrize("descriptor,entity", [("VLFC-Econolease finance payment", "Econolease"),
                                               ("CMCA Finance BUS payment", "CMCA Finance"),
                                               ("Lily Advance", "Lily Advance")])
def test_econolease_cmca_finance_and_lily_advance_are_counted_lenders_and_no_potential_alias(descriptor, entity):
    found = _known(descriptor)
    assert found is not None and (found.entity, found.state) == (entity, "confirmed_lender"), found
    assert registry_match(normalize(descriptor), registry.POTENTIAL_LENDER_ALIASES) is None


def test_truist_is_on_the_bank_name_list():
    assert registry_match(normalize("TRUIST LN 0001 PYMT"), registry.BANK_NAME_ALIASES) is not None


@pytest.mark.parametrize("descriptor,entity", [("Clover equipment rent/leases", "Clover Equipment"),
                                               ("INVESTMENT MERCH PAD", "MERCH PAD (probably Merchant Growth)"),
                                               ("REWARDS NETWORK PAYMENT", "Rewards Network")])
def test_review_tier_payees_are_potential_lender_aliases_and_no_known_payee(descriptor, entity):
    assert _known(descriptor) is None
    found = registry_match(normalize(descriptor), registry.POTENTIAL_LENDER_ALIASES)
    assert found is not None and found[0] == entity, found
    assert BY_NAME[entity].status == "review"


@pytest.mark.parametrize("descriptor,entity", [("ACH DEBIT FORWARDFINANCING LLC", "Forward Financing"),
                                               ("ACH DEBIT EXPANSIONCAP", "EXPANSION CAPITAL")])
def test_the_run_together_spellings_spec_section_1_names_match_their_lender(descriptor, entity):
    found = _known(descriptor)
    assert found is not None and (found.entity, found.state) == (entity, "confirmed_lender"), found


@pytest.mark.parametrize("descriptor,wrong", [
    ("JOURNEY CAPITAL ONDECK CANADA BUS ENT", "ONDECK"),
    ("ONLINE BANKING PAYMENT 0102 ENOVA POWER CO", "ONDECK"),
    ("ACH WEB SMARTPAY ATLASFINANCIAL", "SmartPay"),
])
def test_the_collisions_spec_section_5_names_are_gone(descriptor, wrong):
    found = _known(descriptor)
    assert found is None or found.entity != wrong, found


def test_bluevine_is_bluevine_capital_and_bluevine_loan_without_the_bare_alias():
    # Owner ruling 2026-09-25: bare BLUEVINE takes Bluevine Bill Pay and Bluevine checking rows.
    assert registry.LINE_OF_CREDIT_ALIASES["BLUEVINE"] == ("BLUEVINE CAPITAL", "BLUEVINE LOAN")
    assert not [name for entries in REGISTRY_TABLES.values() for name, aliases in entries.items()
                if any(normalize(alias) == "BLUEVINE" for alias in aliases)]
    for descriptor in ("BLUEVINE", "BLUEVINE BILL PAY QUILLON BAKERY", "BLUEVINE ONLINE TRANSFER"):
        assert _known(descriptor) is None and _claimed_by(descriptor) == [], descriptor


def test_smartpay_is_smartpay_leasing_and_smartpay_sol_is_claimed_by_no_table():
    # Owner ruling 2026-09-25: SMARTPAY SOL is SmartPay Solutions' premium billing, not the lease-to-own SmartPay.
    assert registry.LEASE_RENTAL_ALIASES["SmartPay"] == ("SMARTPAY LEASING",)
    assert registry.REATTRIBUTED_REGISTRY_ALIASES == {"SMARTPAY SOL": "SmartPay Solutions, LLC"}
    solutions = BY_NAME["SmartPay Solutions, LLC"]
    assert solutions.status == "rejected" and "SMARTPAY SOL" in solutions.aliases
    for descriptor in ("SmartPay Sol debitpmt", "SMARTPAY SOL"):
        assert _known(descriptor) is None and _claimed_by(descriptor) == [], descriptor


def test_first_insurance_is_premium_financing_of_first_insurance_funding_on_the_owners_ruling():
    premium = registry.PREMIUM_FINANCE_ALIASES
    assert registry.PREMIUM_FINANCE_INSURER_ALIASES == ("FIRST INSURANCE",)
    for descriptor in ("FIRST INSURANCE FUNDING PMT", "FIRST INSURANCE PMT"):
        found = registry_match(normalize(descriptor), premium)
        assert found is not None and found[0] == "FIRST Insurance Funding", (descriptor, found)
        assert _known(descriptor) is None, descriptor
    found = registry_match(normalize("PAD FIRST INSURANCE LOAN"), premium)
    assert found is not None and found[0] == "FIRST Insurance Funding of Canada", found
    assert registry.INSURANCE_PROVIDER_ALIASES["First Insurance"] == ("FIRST INSURANCE",)
    insurer_aliases = {normalize(a) for aliases in registry.INSURANCE_PROVIDER_ALIASES.values() for a in aliases}
    premium_aliases = {normalize(a) for aliases in premium.values() for a in aliases}
    assert insurer_aliases & premium_aliases == {normalize(a) for a in registry.PREMIUM_FINANCE_INSURER_ALIASES}
    assert not set(premium) & set(registry.INSURANCE_PROVIDER_ALIASES)
    assert "only on the owner's ruling (`PREMIUM_FINANCE_INSURER_ALIASES`)" in EVIDENCE
    assert "has an alias that contains an alias of the hand-kept insurer" not in EVIDENCE


def test_ebf_holdings_is_merged_into_everest_business_funding_and_counts_once():
    assert registry.MERGED_REGISTRY_ENTITIES == {"EBF HOLDINGS": "EVEREST BUSINESS FUNDING"}
    assert "EBF HOLDINGS" not in BY_NAME
    assert not [table for table, entries in REGISTRY_TABLES.items() if "EBF HOLDINGS" in entries]
    assert {"EBF HOLDINGS", "EBF DEBIT", "HOLDINGS EBF"} <= set(registry.LENDER_ALIASES["EVEREST BUSINESS FUNDING"])
    found = _known("HOLDINGS EBF DEBIT")
    assert found is not None and (found.entity, found.state) == ("EVEREST BUSINESS FUNDING", "confirmed_lender")
    assert "| EBF HOLDINGS | confirmed_lender | confirmed_lender (merged into EVEREST BUSINESS FUNDING) |" in EVIDENCE


@pytest.mark.parametrize("descriptor,entity,state", [
    ("SEZZLE PAYMENT", "Sezzle Inc", "alternative_position"),
    ("AMERICAN FIRST FINANCE PAYMENT", "American First Finance, LLC", "alternative_position"),
    ("PAYABILITY PAYMENT", "PAYABILITY", "confirmed_lender"),
])
def test_the_payout_credit_entities_are_admitted_financing_payees_whose_debits_keep_their_group(
        descriptor, entity, state):
    # Owner ruling 2026-09-25: their credits are the holder's own sales settled by the platform, which S2 reads
    # as revenue (PAYOUT_CREDIT_ENTITIES, a D1 exception); the matcher still gives every row the entity's group.
    assert registry.PAYOUT_CREDIT_ENTITIES == ("Sezzle Inc", "American First Finance, LLC", "PAYABILITY")
    assert BY_NAME[entity].status == "admitted" and BY_NAME[entity].group in FINANCING_STATES
    found = _known(descriptor)
    assert found is not None and (found.entity, found.state) == (entity, state), found


@pytest.mark.parametrize("entity,group,status", [
    ("CAPITAL INFUSION", "alternative_position", "admitted"),
    ("MERCH PAD (probably Merchant Growth)", "confirmed_lender", "review"),
    ("Rewards Network", "confirmed_lender", "review"),
    ("MR BIZ CAPITAL", "confirmed_lender", "rejected"),
    ("Keep Technologies Corp", "credit_card_payment", "rejected"),
    ("LADCO Leasing", "lease_or_rental", "admitted"),
])
def test_the_owner_delegated_rulings_of_2026_09_25_file_each_payee_in_its_place(entity, group, status):
    assert (BY_NAME[entity].group, BY_NAME[entity].status) == (group, status)
    counted = entity in registry.LENDER_ALIASES
    assert counted == (group == "confirmed_lender" and status == "admitted"), entity


def test_the_numbered_ontario_company_waits_for_the_owner_unsearched_and_without_its_number():
    numbered = [entity for entity in ENTITIES if entity.status == "owner_ruling"
                and "numbered ontario company" in f"{entity.entity} {entity.notes}".lower()]
    assert numbered
    for entity in numbered:
        # Spec section 5: it is not searched anywhere, by rule. A URL is where the digit rule does not look.
        assert entity.evidence == () and entity.where_looked == (), entity.index
        assert not any(re.search(r"\d", alias) for alias in entity.aliases), entity.index


def test_no_digit_run_of_five_or_more_reaches_the_ledgers_outside_urls_and_todays_aliases():
    held = {run for table in RULES.baseline.values() for aliases in table.values() for alias in aliases
            for run in re.findall(r"\d{5,}", alias)}
    for text in (EVIDENCE, lender_ledger.LEDGER_PATH.read_text(encoding="utf-8")):
        stripped = re.sub(r"sha256:[0-9a-f]{64}", "", re.sub(r"https?://[^\s\"|,]+", "", text))
        assert set(re.findall(r"\d{5,}", stripped)) <= held
```

- [ ] **Step 5: Run it to verify it fails**

Run: `C:\Python314\python.exe -m pytest tests/test_lender_registry_content.py -q -p no:cacheprovider`
Expected: 1 error during collection: `FileNotFoundError: [Errno 2] No such file or directory: '<repository>\\docs\\lender-registry-evidence.md'`.

- [ ] **Step 6: Render**

Run: `C:\Python314\python.exe -m tools.build_lender_registry --write; $LASTEXITCODE`
Expected output:
- the `ledger ok: ...` line and the `move:` lines of Step 2;
- one line per table, from `LENDER_ALIASES: <n> entities, <m> aliases` to `POTENTIAL_LENDER_ALIASES: ...` (for the ledger of the owner's rulings of 2026-09-25, the lines listed in "Prerequisite: the curated ledger");
- `0`.

The tool has rewritten the GENERATED block of `analysis/classification_registry.py`, and has written `docs/lender-registry-evidence.md`.

**To undo the render** (Steps 7 and 8 say when), run:

```powershell
git checkout -- analysis/classification_registry.py; if (git ls-files docs/lender-registry-evidence.md) { git checkout -- docs/lender-registry-evidence.md } else { Remove-Item docs/lender-registry-evidence.md }
```

It restores the committed block, and it restores the committed evidence ledger, or removes the file when none is committed yet.

- [ ] **Step 7: Privacy review of every committed name**

Run: `C:\Python314\python.exe -m tools.build_lender_registry --privacy-review`

It prints two kinds of line, for every entity of every status:
- `no organisation word in the name: <entity> (<status>)`;
- `alias shares no word with its name: <entity> | <alias>`.

For the ledger of the owner's rulings of 2026-09-25 it printed 597 lines.

Read every line. Then read `docs/lender-registry-ledger.json` and `docs/lender-registry-evidence.md` from start to end. Look for:
- a person's or a customer's name, in an entity, an alias, `notes` or an evidence note;
- an alias that does not name its payee, such as an entry description, a loan-type code or channel words;
- anything copied from a statement: amounts, dates, account, reference or card numbers, or descriptor text.

Company names, their spellings, truncations and initialisms are expected.

If you find anything:
1. Undo the render (the command at the end of Step 6).
2. Stop.
3. Report the entity's index in the ledger and the field to the orchestrator, never the text.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `C:\Python314\python.exe -m pytest tests/test_lender_registry_content.py tests/test_lender_registry_drift.py tests/test_classification_registry_groups.py tests/test_payee_matcher.py -q -p no:cacheprovider`
Expected: 114 passed (75 + 3 + 21 + 15; amended to the owner's rulings of 2026-09-25).

If a content test fails:
1. Undo the render (the command at the end of Step 6). Step 3 then fails as it did before the render.
2. Stop, and report the test id to the orchestrator with the fact it checks. Each test maps to one item of "Prerequisite: the curated ledger", or to one of S2's facts.
3. The orchestrator fixes the ledger. Bring the revised ledger (Step 1), then rerun this task from Step 2, skipping Steps 4 and 5 because the content test already exists.

Never edit the ledger, the rendered block or the test to make it pass.

- [ ] **Step 9: Run every S1 test, the three selections and the benchmark**

Run: `C:\Python314\python.exe -m pytest tests/test_flag_groups.py tests/test_classification_registry_groups.py tests/test_payee_matcher.py tests/test_classifier_speed.py tests/test_lender_ledger.py tests/test_build_lender_registry.py tests/test_lender_registry_drift.py tests/test_lender_alias_audit.py tests/test_lender_registry_content.py -q -p no:cacheprovider`
Expected: 318 passed (243 + 75; amended to the owner's rulings of 2026-09-25).

Run the three commands from "Before Task 1".
Expected: the baseline counts, unchanged: `404 passed`; `146 passed, 1 failed` (the known failure); `306 passed`. The classifier still reads the legacy lists. (The counts of this step were measured on the ledger of the owner's rulings of 2026-09-25, rendered on this branch at `b69d12e` in a scratch clone.)

Run: `C:\Python314\python.exe -m tools.bench_classifier; $LASTEXITCODE`
Expected: a line `300 fabricated rows: legacy <a> s, compiled <b> s, <n>x faster (required: 10x)` with `<n>` of at least 10, then `0`.

- [ ] **Step 10: Acceptance**

Each check, and the evidence for it:

| Check | Evidence |
|---|---|
| The validator is clean | Step 2 exit `0`; `test_the_committed_ledger_passes_the_validator` |
| Every move from today's registry has a reason about that move | the `move:` lines of Step 2, each read |
| Every owner-named payee is present in its group | `test_every_payee_the_owner_named_is_in_its_ruled_group_in_the_committed_registry` |
| `FIRST INSURANCE` is FIRST Insurance Funding's premium alias on the owner's ruling, the only premium alias equal to an insurer alias, beside the unchanged hand-kept `First Insurance` | `test_first_insurance_is_premium_financing_of_first_insurance_funding_on_the_owners_ruling`; the ruling's line in the evidence ledger's Admission section, and no overlap line under "Awaiting an owner ruling" |
| The committed files are the rendering of the ledger | the three drift tests |
| S2's facts | the S2 Task-0 cases of the content test; the Econolease, CMCA Finance and Lily Advance lender cases; the review-tier cases |
| The owner's rulings of 2026-09-25: BlueVine without the bare alias, SmartPay Leasing and SmartPay Solutions, the EBF merge, the payout-credit entities, and the other delegated filings | `test_bluevine_is_bluevine_capital_and_bluevine_loan_without_the_bare_alias`; `test_smartpay_is_smartpay_leasing_and_smartpay_sol_is_claimed_by_no_table`; `test_ebf_holdings_is_merged_into_everest_business_funding_and_counts_once`; `test_the_payout_credit_entities_are_admitted_financing_payees_whose_debits_keep_their_group`; `test_the_owner_delegated_rulings_of_2026_09_25_file_each_payee_in_its_place` |
| Privacy | Step 7 read in full; `test_no_digit_run_of_five_or_more_reaches_the_ledgers_outside_urls_and_todays_aliases`; `test_the_numbered_ontario_company_waits_for_the_owner_unsearched_and_without_its_number` |

- [ ] **Step 11: Commit**

```powershell
git add docs/lender-registry-ledger.json analysis/classification_registry.py docs/lender-registry-evidence.md tests/test_lender_registry_content.py
git commit -m "registry: lender tables and evidence ledger rendered from the curated ledger (contract C10)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: <the Claude-Session URL from your system reminder>"
```

`git add` of an unchanged ledger adds nothing, which is expected when the ledger was already on the branch.

On a rerun for a revised ledger, use the same `git add` line with the subject `registry: re-render the lender tables from the revised curated ledger (contract C10)`. The content test is already committed, so `git add` adds nothing for it.

---

### Task 10: The reviewed collision audit (S1 acceptance) and the S2 hand-off

**Files:**
- Modify: nothing. S1 never edits the ledger (Decision 10). A revised ledger comes from the orchestrator, and Task 9 renders and commits it.
- Local, never committed: `$local\alias-review.json`, `$local\alias-audit.json`, `$local\alias-audit-previous.json`, `$local\s2_preconditions.py`

**Interfaces:**
- Consumes:
  - `tools.lender_alias_audit.main` (Task 8), including `--before` (Decision 15);
  - Task 9, which renders and commits a revised ledger;
  - the S2 plan's Task 0 script.
- Produces:
  - an audit with zero denied collisions and zero undecided matches that need review (spec §5: zero collisions; spec §9, acceptance 3). After a revised ledger, it also has zero rows that an entity lost without a decision;
  - the counts the orchestrator needs to start S2.

- [ ] **Step 1: Create the local review file (once), and look for a previous report**

```powershell
if (-not (Test-Path "$local\alias-review.json")) { Set-Content -Encoding utf8 -Path "$local\alias-review.json" -Value '{"deny": [], "allow": []}' }
Test-Path "$local\alias-audit-previous.json"
```

Expected: `False` the first time this task runs.
- It prints `True` only after Step 4 has sent a denial to the orchestrator. Step 2 then checks the revised ledger against that report.
- If it prints `True` on the first run, the file is left from an earlier trial. Delete it with `Remove-Item "$local\alias-audit-previous.json"`.

- [ ] **Step 2: Run the strict audit**

It reads the cache read-only, and takes three to nine minutes on the full cache. Add `--limit 300` for a quick look first, but never together with `--before`: a report of fewer analyses has fewer rows, and every missing row would read as lost. The first line builds the `--before` option only when a previous report exists.

```powershell
$before = @(); if (Test-Path "$local\alias-audit-previous.json") { $before = @("--before", "$local\alias-audit-previous.json") }
C:\Python314\python.exe -m tools.lender_alias_audit --data-dir $webappData --review "$local\alias-review.json" --out "$local\alias-audit.json" --strict @before; $LASTEXITCODE
```

Expected on the first run: one summary line, then `1`:

`aliases that matched: <a>; payee keys: <k>; taken matches: <t>, of which need review: <r>; denied matches: 0; undecided: <r>`

With a previous report, the summary line is followed by:
- `lost matches: <n>`;
- one `LOST '<entity>' payee key '<key>': <a> taken rows before, <b> now` line per pair.

About the counts:
- They depend on the ledger.
- For scale, the trial with this revision's stand-in ledger printed `taken matches: 166, of which need review: 119` at `--limit 300`, and `taken matches: 422, of which need review: 334` on the full cache (under three minutes).
- The ledger of the owner's rulings of 2026-09-25, rendered on this branch at `b69d12e`, printed `aliases that matched: 1136; payee keys: 2262; taken matches: 2063, of which need review: 1180` on the full cache. With the orchestrator's review file and the previous ledger's report as `--before`, it printed `denied matches: 1; undecided: 0` and `lost matches: 0`. The one deny is the Zip overdraft charge (Step 4).
- Most of them are one-word aliases whose payee key adds a word.

- [ ] **Step 3: Decide every row of `undecided`**

`$local\alias-audit.json` lists the rows under `undecided`. Each row has `state`, `alias`, `entity`, `key`, `rows`, `taken_rows`, `analyses` and `needs_review`.

Add one decision per row to `$local\alias-review.json`. When a decision holds for every alias of a key, one decision per key is enough. Write each `why` so that a reviewer who reads the key can check it (Step 7): say what K is.
- **Allow by key alone**, `{"key": K, "why": "channel words only"}`, when K holds only bank-channel or descriptor words and no business name. It allows K for every alias and every entity, so use it only then.
- **Allow for the entity**, `{"entity": E, "key": K, "why": "..."}`, when K is the entity itself: its name, a truncation or run-together form of it, its name with a legal suffix, or its servicer or funder as the ledger's `notes` record.
- **Deny**, `{"alias": A, "entity": E, "key": K, "why": "..."}`, when K names a different business or a person. S1 only records the deny here and sends it to the orchestrator (Step 4). S1 never edits the ledger to carry it out.

S1 may allow a row on any alias, including an alias of a payee in `OWNER_NAMED_PAYEES` and an entity's last alias.

**BlueVine.** The owner's ruling of 2026-09-25 dropped bare `BLUEVINE`. That carried out the five denies the review recorded on it: Bluevine Bill Pay payments and receipts between other businesses, and transfers to or from Bluevine checking accounts. Keep those deny entries in the review file. They name the bare alias, so they no longer fire, and the audit fails if a later ledger gives BlueVine the bare `BLUEVINE` again. BlueVine's aliases are now `BLUEVINE CAPITAL` and `BLUEVINE LOAN`, and a deny on either is marked as an alias of an owner-named payee.

A fabricated example of the file:

```json
{"allow": [{"key": "CORPORATE", "why": "channel words only"},
           {"entity": "Quillon Funding", "key": "QUILLON FUNDING LLC", "why": "the funder with its legal suffix"}],
 "deny": [{"alias": "QUILLON", "entity": "Quillon Funding", "key": "QUILLON BAKERY", "why": "a bakery, not the funder"}]}
```

For each deny, note two more facts for Step 4:
- **The mark.** Mark the deny when A is an alias of a payee in `OWNER_NAMED_PAYEES`, or E's last alias. For these, dropping A is not the fix, and the orchestrator must find another one.
- **The other keys of A.** Under `aliases.<state>.<A>.keys` in `$local\alias-audit.json`, count the other keys with `taken_rows` above 0 that no deny names. A drop of A would take their rows from E too, unless another alias of E matches them.

- [ ] **Step 4: Settle every denial with the orchestrator (only when Step 3 recorded one)**

1. Save the report of this ledger as the previous report, for the lost-rows check of the next ledger (Decision 15). Save it only from a run of the full cache (no `--limit`) that printed no `LOST` line:

   ```powershell
   Copy-Item "$local\alias-audit.json" "$local\alias-audit-previous.json"
   ```

2. Send the orchestrator one line per deny, in this form (ledger text and counts only):

   `deny: entity '<E>', alias '<A>', <kind of collision, e.g. an unrelated merchant's card purchases>; mark: <owner-named payee | last alias | none>; other keys of the alias with taken rows: <n>`

   The orchestrator reads the payee keys itself in `$local\alias-review.json` and `$local\alias-audit.json`. Both are local and outside the repository.
3. Stop until the orchestrator has answered every deny. Each answer is one of two:
   - **A ruling that allows the pair.** Move the entry from `deny` to `allow` in the review file, with `"why": "orchestrator ruling <date>: <its reason>"`. Then rerun Step 2.
   - **A revised ledger that the owner has read**, for example with a narrower alias, or with the other business admitted under a longer alias that wins. Run Task 9 from Step 1 through Step 11: the rerun path brings the ledger from the ref the orchestrator names, and skips Steps 4 and 5. Then rerun Step 2 here.

   Keep the deny entries. If the revised ledger still lets the alias take the key's rows, the audit fails on it.
4. On the rerun, each `LOST` line is a pair whose rows the revision took from the entity without a decision. Send each one to the orchestrator as `lost: entity '<E>', <a> taken rows before, <b> now`, never with the key. The orchestrator answers in one of two ways:
   - **The loss is intended.** Add `{"entity": E, "key": K, "why": "orchestrator ruling <date>: <its reason>"}` to `deny`, and rerun Step 2. The deny also makes the audit fail if E takes K again.
   - **The loss is not intended**, for example because a drop should have been a narrower alias. The orchestrator sends a further revised ledger: handle it as in item 3. The previous report stays the one saved in item 1.

**The Zip overdraft charge (the ledger of the owner's rulings of 2026-09-25).** That ledger leaves one deny: `ZIP APP PAY` (Zip Co US Inc) takes the bank's own overdraft charge for a Zip item. The charge prints the same truncated Zip spelling as Zip's own payments, so no ledger spelling can separate them, and a drop would lose Zip's own rows. The fix belongs to S2: its fee rule also reads `OVERDRAFT CHARGE` (step 6, ahead of the known-payee matcher), so under S2 the charge is a fee and Zip never takes it. The audit replays today's stored states, in which the charge is `other`, so it cannot see that rule. The orchestrator's answer to this deny is therefore a ruling: move the entry to `allow` in the entity-and-key form, `{"entity": "Zip Co US Inc", "key": <the denied key>, "why": ...}` (never the key alone, which would allow the key for every entity), with `"why": "orchestrator ruling 2026-09-25: the bank's overdraft charge for a Zip item; S2's fee rule reads OVERDRAFT CHARGE at step 6, and no ledger spelling separates it"`, then rerun Step 2. The census after S2 shows those rows as fees.

Step 5 is reached only when every deny and every `LOST` line has an answer.

- [ ] **Step 5: Acceptance**

Rerun Step 2. Expected:
- exit code `0`;
- the summary line ends `denied matches: 0; undecided: 0`;
- when a previous report exists, the next line is `lost matches: 0`.

Copy these lines for the hand-off.

- [ ] **Step 6: Run S2's preconditions against this branch (nothing is committed)**

Copy the Python script of the S2 plan's Task 0 Step 3 (`docs/superpowers/plans/2026-09-24-lender-detection-s2-classifier.md`) to `$local\s2_preconditions.py`. Run it from the repository root:

```powershell
C:\Python314\python.exe "$local\s2_preconditions.py"; $LASTEXITCODE
```

Expected: every check line `ok`, then `0 failure(s)` and `0`. Besides the checks it prints:
- three `info  ... still defined: True` lines;
- `info` lines for the card-issuer count on RBC Jan and Navy Fed June;
- `info  navigant: open loan debits naming a listed bank = <N>`.

The navigant line selects S2's pin variant (pin-ledger row 15), and the ledger decides it. The trial with the stand-in ledger printed `0 failure(s)`, card counts `3` and `0`, and navigant `0`; the S2 Task 0 of that time could also print a relay variant line, which it did not.

For the ledger of the owner's rulings of 2026-09-25, copy the script only once the orchestrator has amended S2's Task 0 to those rulings: its facts 3, 4, 6 and 9, its `OWNER_RULED` rows and its `EXPECTED` values. Run on that ledger before the amendment (in a scratch clone of this branch at `b69d12e`), the script printed `20 failure(s)`: the six facts the rulings changed (AFC FUNDING CORP, SmartPay, Econolease, Clover Equipment, CMCA Finance, Lily Advance) and 14 pinned-statement counts that the ledger moves, first_farmers' BlueVine-named row among them (no longer claimed). The orchestrator's amendment of S2's Task 0 re-pins all of them; the amended script, run on a scratch export of this branch at `b69d12e` with that ledger rendered, printed `0 failure(s)`, card counts `3` and `0`, and navigant `2`. Report any `FAIL` line of the amended script as usual.

A `FAIL` line means the ledger breaks a fact that S2 relies on. Report every `FAIL` line verbatim; the lines carry counts, fabricated descriptors and registry names only. S2 does not start until the orchestrator settles it, in the ledger (then rerun Task 9 from Step 1 and this task from Step 2) or by giving S2 ruled values.

- [ ] **Step 7: Hand off to the orchestrator (nothing is committed)**

Report:
- the ledger's `ledger ok` line (the entity count and the digest), and its `move:` lines;
- the per-table lines of the last `--write`;
- that the privacy review was read in full, and how many lines it printed;
- the audit summary lines of the first run (Step 2) and of the acceptance (Step 5), with the `lost matches` line when there is one;
- the number of allow and deny decisions in `$local\alias-review.json`, and how many allows are by key alone;
- every deny and `LOST` line sent in Step 4, with the orchestrator's answer (ledger text and counts only);
- S2's Task 0 output: the failure count, and every `FAIL` and `info` line;
- the local paths `$local\alias-review.json`, `$local\alias-audit.json` and, when it exists, `$local\alias-audit-previous.json`.

Do not quote any payee key.

**The check of S1's allow decisions (the orchestrator, or the independent reviewer of S1, before S2 starts).** One agent made every allow decision, so a second one checks them:
- Read `$local\alias-review.json` beside the `aliases` section of `$local\alias-audit.json`, which lists every alias with its entity and the keys it takes. The files are local and outside the repository, so reading them breaks no privacy rule.
- Check every allow by key alone, because each one allows its key for every alias and entity.
- Check at least 30 other allows, spread across entities, including every allow on a BlueVine alias (`BLUEVINE CAPITAL`, `BLUEVINE LOAN`; bare `BLUEVINE` is no longer an alias).
- A wrong allow becomes a deny, which goes through Step 4.
- The check's report names entities and counts, never a payee key.

---

## Notes for S2 and the orchestrator

- **S2's Task 0 on S1's output.** Expect `0 failure(s)`. The navigant bank-name count selects S2's one pin variant (pin-ledger row 15), and the ledger decides it; S1's Task 10 Step 6 reports it. The earlier draft of this plan expected three relay FAIL lines, and a later S2 Task 0 treated the relay reach as a variant. Since the owner's rulings of 2026-09-25, S2's Task 0 expects relay's reach exactly (pin-ledger row 17), so no relay variant line is printed.
- **The ledger belongs to the orchestrator, content and edits alike (Decision 10).**
  - A failed content fact, whether from S1's validator, S1's content test or S2's Task 0, is settled in the ledger.
  - So is every alias the audit denies. S1 sends each deny as entity, alias, kind and mark (Task 10 Step 4), and never edits the ledger.
  - The orchestrator answers with a ruling or a revised ledger. For a revised ledger, the owner reads the changed entities, and the orchestrator names the ref that holds it.
  - S1 then reruns Task 9 from Step 1 (its rerun path) and Task 10 from Step 2. The audit's `--before` check then catches rows that the revision took from an entity without a decision (Decision 15).
- **The orchestrator's checks before S2 starts:**
  - the `move:` lines of `--check` (Decision 3);
  - the check of S1's allow decisions in `$local\alias-review.json` (Task 10 Step 7), done by the orchestrator or the independent S1 reviewer.
- **The validator checks more than C10's first list** (Decision 3). The master plan's C10 now says so: it makes this validator normative for the ledger producer, and lists these rules there too:
  - `OWNER_NAMED_PAYEES` covers every group spec §2 names;
  - it adds the brand, context-only, card-wording, hand-kept, run-together, privacy and today's-registry rules;
  - a move needs a `Move:` sentence, not just any note.

  The owner's ruling of 2026-09-25 adds four more (Decision 3), which the master plan's C10 now lists too: a premium-finance alias repeats an insurer alias only as a `PREMIUM_FINANCE_INSURER_ALIASES` spelling; a `MERGED_REGISTRY_ENTITIES` entry names an entity of today's registry and a ledger entity that absorbs it; a `REATTRIBUTED_REGISTRY_ALIASES` entry names an alias of today's registry and the ledger entity of the other company, which holds it and alone may be read from it; every `PAYOUT_CREDIT_ENTITIES` name is an admitted entity of a financing group.

  S2's "Why Task 0 checks more than C10's validator" still holds for the entity spellings S2 pins and for the reach into real statements. The owner-named payees of the amendment groups, the equipment lenders and the lease-to-own names are now also refused by the validator when they are missing.
- **The legacy lists.**
  - S2's Task 6 deletes the three legacy tables and the Deprecated comment block above them, after its Task 5 has removed their last readers.
  - Afterwards `test_the_baseline_revision_holds_the_lists_the_classifier_reads_until_s2` skips by design, and `test_registry_match_agrees_with_the_legacy_matcher...` skips the removed names.
  - The validator keeps working, because it reads today's registry from git at `BASELINE_REVISION`. No baseline file is committed.
- **S1's hand-kept constants** (`OWNER_NAMED_PAYEES`, `BARE_PLATFORM_NAMES`, `BARE_BRAND_NAMES`, `PREMIUM_FINANCE_INSURER_ALIASES`, `MERGED_REGISTRY_ENTITIES`, `REATTRIBUTED_REGISTRY_ALIASES`, `PAYOUT_CREDIT_ENTITIES`) sit between `PAYEE_GROUP_REGISTRIES` and the Deprecated block. S2 must neither edit nor delete them. S2's deletion of the Deprecated block stops at `LEGACY_CONFIRMED_LENDER_ALIASES`, so they survive it.
  - S2 reads `PAYOUT_CREDIT_ENTITIES` as a D1 exception (the owner's ruling of 2026-09-25): those entities' credits are the account holder's own sales settled by the platform, so revenue, not financing proceeds; their debits keep their group.
  - S2's insurance rule reads `PREMIUM_FINANCE_ALIASES` first, so once the ledger gives `FIRST INSURANCE` to FIRST Insurance Funding, a row that prints only `FIRST INSURANCE` stays insurance and is also flagged premium financing (Decision 8).
- **The owner's merge and reattribution in S2's census compare.** Spec §9 reads every lost lender as a ruled move, so the orchestrator should expect these before reading `lender_census compare`:
  - The merge of `EBF HOLDINGS` into `EVEREST BUSINESS FUNDING` is silent: S2's `compare` reads `MERGED_REGISTRY_ENTITIES` and treats the two names as one lender, so `EBF HOLDINGS` shows neither as lost nor as gained. Its rows are still `confirmed_lender`, under `EVEREST BUSINESS FUNDING`.
  - The reattribution of `SMARTPAY SOL` to SmartPay Solutions takes those rows from SmartPay: SmartPay Solutions is a rejected entity (premium billing, not a lender, a lessor or a premium financier), and the validator refuses a registry whose known-payee or potential tables read `SMARTPAY SOL` as anyone else, so with bare `SMARTPAY` dropped those rows leave the lease state and no registry entity claims them. They were never lender rows, so the census shows no lender change for them; they become unflagged `other` rows. That is ruled (`REATTRIBUTED_REGISTRY_ALIASES`).
  - S2's plan names `SMARTPAY LEASING` as SmartPay's alias in its fact 4 (amended by the orchestrator to the owner's ruling).
- **The ledger's own words must match the owner's ruling.** The validator reads a move's reason from the holder's first `Move:` sentence, so the orchestrator rewrites these notes when it revises the ledger:
  - `EVEREST BUSINESS FUNDING`: its `Move:` sentence becomes the merge's reason on the `move:` line and the evidence page, so it must be about the merge. The current text says the `EBF HOLDINGS` spellings stay with a separate `EBF HOLDINGS`, which contradicts the merge.
  - SmartPay: it holds `SMARTPAY LEASING`; its notes say that `SMARTPAY SOL` went to SmartPay Solutions on the owner's ruling, and its `Move:` sentence explains why bare `SMARTPAY` is dropped.
  - SmartPay Solutions, LLC: it holds `SMARTPAY SOL` (with its fuller printed spelling), and its notes no longer say that `SMARTPAY SOL` stays on SmartPay.
- **Classifier edits S2 must expect.**
  - S2's Task 3 Step 3 replaces `_contains_alias` through S1's delegating `_registry_match`. In the replayed S1 tree, `def _contains_alias` is at line 173 and `    return registry_match(text, registry)` at line 188. S2 anchors on the text, so the line numbers are a guide only.
  - S2's Task 4 widens S1's `from .payee_matcher import registry_match`.
  - S2's Task 5 Step 3 replaces only the `from .classification_registry import (...)` block.
  - S1's two imports sit after `from .revenue import ...`, so they survive all three.
- **S1's test files.** S2's Task 6 Step 4 finds S1's test files with `git diff --diff-filter=A`, so it runs all nine without a list to keep up to date. All of them stay green after S2, with the legacy-list checks skipped.
- **The speed test after S2.** `tests/test_classifier_speed.py` keeps passing after S2, because it swaps whichever of `registry_match` and `match_known_payee` the classifier module holds.
- **A new ledger.** When the orchestrator changes the ledger (for example after a research round), whoever owns the branch at that time reruns Task 9 from Step 1 (its rerun path) and Task 10 from Step 2. The drift test fails until they do.
- **Planner decisions the owner should see:**
  - the "Awaiting an owner ruling" section of `docs/lender-registry-evidence.md`, including each premium/insurer overlap line that remains once a premium entity holds the ruled `FIRST INSURANCE` (Decision 8);
  - the spellings in `OWNER_NAMED_PAYEES`, for example Amex loans = `AMERICAN EXPRESS BUSINESS LOAN`, Amazon financing = `AMAZON CAPITAL SERVICES`, and, on the owner's ruling of 2026-09-25, BlueVine = `BLUEVINE CAPITAL` and SmartPay = `SMARTPAY LEASING`, with today's `SMARTPAY SOL` given to SmartPay Solutions (`REATTRIBUTED_REGISTRY_ALIASES`);
  - `BARE_BRAND_NAMES` (which includes `ALLY`, `DEERE` and `JOHN DEERE`) and `AMZN` in `BARE_PLATFORM_NAMES`;
  - the reading of "a bare generic word" as "only generic words" (Decision 3);
  - the three rules this revision adds to Decision 3:
    - no `review` entity in the context-only groups;
    - every card-payment alias carries card or payment wording;
    - a move from today's registry needs a `Move:` sentence.

  The earlier draft's planner readings (AFC FUNDING CORP, `SMARTPAY SOL`, bare `BLUEVINE` bill-pay rows, ACH CAPITAL, Nissan) are now for the ledger to record, in `notes` or as `owner_ruling` entities.

## Self-Review

**1. Spec coverage** (the sections S1 owns):

| Spec requirement | Where |
|---|---|
| §4.6 one index over every group registry, built at import time | Task 3 (`_DEFAULT_INDEX = AliasIndex(PAYEE_GROUP_REGISTRIES)`) |
| §4.6 longest alias across groups, the token-boundary rule, `(entity, group, alias)` | Task 3 (`PayeeMatch`, `AliasIndex.match`, the longest-alias and boundary tests) |
| §4.6 run-together forms of 8 characters or more | Task 3 (`RUN_TOGETHER_MIN_LENGTH`, two tests); Task 5 (no run-together form claimed twice); Task 9 (`FORWARDFINANCING`, `EXPANSIONCAP`) |
| §4.6 at least 10× faster on the same synthetic statement | Task 4 (`measure`, `test_three_hundred_fabricated_rows...`, `python -m tools.bench_classifier`); Task 9 Step 9 |
| §4.1/§4.2 (amended) the eleven groups: floor plan, factoring and premium financing (state None, not in `FLAG_GROUP_BY_STATE`); `FINANCING_STATES` with `floor_plan_financing` and `factoring` | Task 1 (C1 verbatim; five tests) |
| §5 (amended) `FLOOR_PLAN_ALIASES` and `FACTORING_ALIASES` in `PAYEE_GROUP_REGISTRIES`, between `personal_loan` and `lease_or_rental`; `PREMIUM_FINANCE_ALIASES` outside it, sharing no entity | Task 2 (structure tests); Task 5 (`TABLES`, one name per entity); Task 6 (rendering tests); Task 9 (content) |
| §5 the lists live only in `classification_registry.py`, one table per group, `CONFIRMED_LENDER_ALIASES` as a compatibility name | Task 2; Task 7 (hand-kept constants in the registry module); Task 9; the guard stays green |
| C10: consolidation outside the code; the code validates and renders only; a drift test | Tasks 5-7 (`validate`, `render_tables`, `render_block`, `render_evidence`, `--check`, `--write`, the drift test); Task 9 (rendered from the committed ledger) |
| C10: the orchestrator produces the ledger and S1 consumes it | Decision 10: S1 never edits the ledger. Its denials go to the orchestrator (Task 10 Step 4), and a revised ledger comes back through Task 9's rerun path |
| C2 and C10: card-payment aliases are payment-specific; bare issuer names and banks are read only with context | Decision 3; Task 5 (the card-wording rule and `CONTEXT_ONLY_GROUPS`, each with a failing-then-passing test) |
| C10: every validator rule, each a failing-then-passing test on fabricated ledgers | Task 5 (`tests/test_lender_ledger.py`: the schema, admission, the alias characters, generic words, platform names, short aliases, one alias per entity, the owner-named payees; red in Step 3, green in Step 5) |
| §5 admission: confirmed plus upheld or corrected; unresolved entities to the potential tier or the owner list | Task 5 (admission rules; `review` renders into `POTENTIAL_LENDER_ALIASES`; `owner_ruling` and `rejected` render nowhere); Task 6 (evidence sections) |
| §2 every payee the owner named, in every group, including the amendment's | Task 7 (`OWNER_NAMED_PAYEES`); Task 5 (`owner_named_problems`); Task 9 (committed registry) |
| §5 aliases: payee names only; no bare platform names; financing-specific, not brands; no `#`; no customer names | Task 5 (character, platform, hand-kept and brand rules); Task 7 (`BARE_PLATFORM_NAMES`, `BARE_BRAND_NAMES`); Task 9 Step 7 (privacy review of every committed name) |
| §5 BlueVine is `BLUEVINE CAPITAL` and `BLUEVINE LOAN`, with no bare `BLUEVINE` (owner, 2026-09-25); ENOVA must not catch Journey or NetCredit; SmartPay versus Atlas | Task 9 (content test: `BLUEVINE loan payment` and `BLUEVINE CAPITAL` are a line of credit, no table claims bare `BLUEVINE`, a Bluevine Bill Pay row or a Bluevine transfer, and the three collisions); Task 10 (the five BlueVine denies stay in the review file and fail the audit if the bare alias returns) |
| §5 collision audit: local only, reports every alias, zero collisions | Task 8 (the audit; the review rule of Decision 9, QUILLON → QUILLON BAKERY needs review; `lost_matches` and `--before`, Decision 15); Task 10 (zero denied and zero undecided, and zero lost after a revised ledger; a second agent checks the allows) |
| §9 every lost lender is a ruled move; gained lenders trace to admitted entities | Task 5 (today's-registry rules, `baseline_moves`, a move needs a `Move:` sentence); Task 6 (the moves section); Task 7 (the `move:` lines of `--check`); Task 10 (a revised ledger that loses an entity's rows fails the audit) |
| §5 evidence ledger: group, public source URL, verdict, where the researchers looked, no statement text; the owner-ruling list with the numbered company | Task 6 (`render_evidence`); Task 9 (rendered, read in full, the numbered-company test, the digit test) |
| Premium financing vs the hand-kept `First Insurance` | Decision 8; Task 5 (hand-kept duplicates refused except the owner-ruled `PREMIUM_FINANCE_INSURER_ALIASES` spellings on a premium entity; overlaps listed unless a premium entity holds the insurer alias); Task 6 (the Admission line); Task 9 (acceptance test) |
| The owner's ruling of 2026-09-25: two respelled owner-named payees, the premium-finance insurer spellings, the merged entities of today's registry, the alias of today's registry given to another company, the payout-credit entities | Decisions 3, 4 and 8; Task 5 (the rules and their tests); Task 6 (the Admission lines, the merge and the reattribution in the moves table); Task 7 (the seven hand-kept constants, `current_rules`, the merge and reattribution `move:` lines) |
| Reproducibility | Task 5 (`ledger_digest`); Task 6 (the digest in the evidence ledger); Task 7 (drift test) |
| The numbered Ontario company stays out | Task 5 (digit rule, messages never quote a digit run); Task 9 (the owner-ruling test also requires no evidence and no `where_looked`, since a URL escapes the digit rule; the digit test) |

**2. The verification findings on the earlier draft, and where each went:**

| Finding | Resolution |
|---|---|
| Major: the vocabulary rule dropped confirmed companies (DLP Funding, Business Credit & Capital, Premco...) | The builder is gone (C10). Names come from the ledger as written; nothing is split into vocabulary. |
| Major: unknown-typed research never attached as evidence | The builder is gone. Evidence, verdicts and `where_looked` come from the ledger, and the evidence ledger prints them for every status. |
| Major: `premium_finance` and `insurance` types unmapped | The builder is gone. The ledger's `group` is explicit, and `premium_financing` is one of C10's groups. |
| Major: the audit never suspected a same-name business | Decision 9. `needs_review` flags one-word aliases, and keys with a foreign word. The QUILLON test is flipped, and `--strict` fails until the pair is decided (Task 8). |
| Minor: descriptor text as name tokens and aliases | No name tokens are derived. The privacy review lists every alias that shares no word with its entity, and Task 9 Step 7 has the reader reject an alias that does not name its payee. |
| Minor: the privacy review skipped emptied entities | `privacy_review` covers every entity of every status, because the committed ledger carries them all. |
| Minor: a late research snapshot | No research is read. The committed ledger is the input, and its canonical digest is in the evidence ledger. |
| Minor: relay and S2's Task 0 | The hand-off expects `0 failure(s)`. The navigant line is a variant; since the owner's rulings of 2026-09-25, S2's Task 0 pins relay's reach exactly (Task 10 Step 6; Notes for S2). |
| Minor: stale S2 task numbers | Decisions 1, 11 and 14 and the Notes cite S2's current Tasks 3, 4, 5 and 6. |
| Minor: `First Insurance` versus `First Insurance Funding` | Decision 8; Task 5 rules; Task 6 owner line; Task 9 acceptance test. |

**The second verification (2026-09-25): no blocker, no major, seven minors. Each one was checked against the code and fixed:**

| Finding | Resolution |
|---|---|
| Task 10 had no path out for a deny that S1 may not carry out (an owner-named payee's alias, bare `BLUEVINE`, a last alias): 261 of the stand-in's 338 undecided rows sat in those groups | Decision 10 and Task 10 Steps 3-4. S1 may allow any row. Every deny goes to the orchestrator with its mark, and each answer is recorded: a ruling becomes an allow whose `why` starts `orchestrator ruling <date>:`, and a revised ledger goes through Task 9's rerun path and Task 10 from Step 2. Step 5 is reached only when every deny has an answer. |
| A deny carried out by dropping an alias could lose the entity's own rows unnoticed | Decision 15. `lost_matches` and the audit's `--before` fail on every (entity, key) whose taken rows fell without a deny. The rerun after a revised ledger compares with the previous ledger's report (Task 10 Steps 1, 2 and 4). For each deny, Step 3 counts the alias's other keys that take rows. Two new tests, and a mutation check showed both fail when the rule is taken out. |
| Any non-empty `notes` excused a move from today's registry | Decision 3. The reason must be a sentence that starts `Move:` (`MOVE_MARKER`, `move_reason`). An unrelated note now fails (a new parametrized case), and `--check`/`--write` print one `move:` line per move, which the orchestrator and S1 read (Task 7, Task 9 Step 2). |
| A `review` entity in a context-only group put bare bank or issuer names into the potential tier; a card alias needed no card wording | Decision 3. `CONTEXT_ONLY_GROUPS` refuses `review` in `credit_card_payment`, `card_issuer_context`, `bank_name` and `premium_financing` (four cases). Every `CARD_ISSUER_ALIASES` alias carries S2's card-payment wording (one test). The stand-in's two bare issuer names moved to `card_issuer_context`, and S2's Task 0 still printed `0 failure(s)` with the same info lines. |
| The numbered company's number could reach the ledger through a URL | Task 9's content test requires the numbered company's entity to have no evidence and no `where_looked` (spec §5: not searched, by rule). The test fails when a URL is added. Also in the Prerequisite and the S1-specific constraints. |
| S1 edited the orchestrator's ledger after the owner's read, and one agent made every allow decision | Decision 10: S1 never edits the ledger, and a revised ledger comes with the owner's read of the changed entities. Task 10 Step 7 adds a second agent's check of the allows: every allow by key alone, and at least 30 others. |
| Stale or unclear notes | (a) The `lender_registry_baseline.json` note is deleted. (b) The note on S2's test list now says that S2 finds S1's files with `git diff --diff-filter=A`. (c) Task 9 has one undo command, used by Steps 7 and 8, and a rerun path that skips Steps 4-5. (d) Task 3 Step 3 deletes the two blank lines as well, which leaves `_contains_alias` at line 173 and the return at 188 (replayed). (e) The Prerequisite gives the orchestrator a preview command for the owner's read. |

**3. Placeholder scan.**
- No "TBD" or "TODO" appears, and no step says "similar to Task N". Every code step shows the complete code, copied from the trial tree that produced the counts.
- The executor supplies only values found at run time:
  - review decisions (Task 10 Step 3);
  - the denials and `LOST` lines sent to the orchestrator, and its answers (Task 10 Step 4);
  - the ref of a revised ledger, which the orchestrator names (Task 9 Step 1);
  - the session URL of each commit.

  Each comes with an exact rule and a fabricated example or a fixed line format.
- The steps that leave the plan's reach say to stop and report to the orchestrator:
  - an absent ledger, or an owner read not confirmed;
  - a validator problem, or a `move:` line whose reason is not about its move;
  - a content-test failure;
  - a privacy finding;
  - every deny and every `LOST` line;
  - an S2 Task-0 FAIL.

**4. Contract-name consistency.**
- C1 matches the master plan verbatim:
  - `FlagGroup(state: str | None, key, setting, label)`;
  - the eleven `FLAG_GROUPS` in order, with `FlagGroup(None, "premium_financing", "flag_premium_financing", "Premium financing")` last;
  - `FLAG_GROUP_BY_STATE` filtered on `g.state is not None`;
  - `FLAG_GROUP_BY_KEY`, `FLAG_SETTING_KEYS`;
  - `FINANCING_STATES`, including `floor_plan_financing` and `factoring`.
- C2 matches it too:
  - the eleven group tables (`LENDER_ALIASES` … `PERSONAL_LOAN_ALIASES`, `FLOOR_PLAN_ALIASES`, `FACTORING_ALIASES`, `PREMIUM_FINANCE_ALIASES`);
  - `BANK_NAME_ALIASES`, `CARD_ISSUER_CONTEXT_ALIASES` and `POTENTIAL_LENDER_ALIASES`;
  - `CONFIRMED_LENDER_ALIASES = LENDER_ALIASES`;
  - the ten-key `PAYEE_GROUP_REGISTRIES` order, without `PREMIUM_FINANCE_ALIASES`.
- C3 matches the master plan. The one addition is the keyword-only `run_together` (Decision 12).
- C10:
  - the fourteen ledger groups are `lender_ledger.GROUPS`, `card_issuer_context` included;
  - the four statuses are `STATUSES`, and they render as C10's table says (`LedgerEntity.table`);
  - the ten fields are `FIELDS`;
  - the validator runs as `tools/build_lender_registry.py --check`;
  - the evidence ledger is `docs/lender-registry-evidence.md`.
- The names are used consistently across the tasks:
  - the ledger module (Tasks 5 and 7): `parse_ledger`, `validate`, `render_tables`, `owner_named_problems`, `move_reason`, `baseline_moves`, `baseline_problems`, `payout_credit_problems`, `premium_insurer_overlaps`, `privacy_review`, `ledger_digest`, `read_ledger`, `load_baseline`, `baseline_from_source`, `current_rules`, `mask_digit_runs`, and the constants `MOVE_MARKER`, `CONTEXT_ONLY_GROUPS`, `INSURER_TABLE` and `WITHHELD`;
  - the renderer (Tasks 6-7): `render_block`, `current_block`, `replace_block`, `render_evidence`, `main`;
  - the audit (Tasks 8 and 10): `AuditPass`, `CachedRow`, `NO_PAYEE_WORDS`, `payee_key`, `default_passes`, `takes`, `cached_rows`, `audit`, `needs_review`, `review`, `lost_matches`, `main` (with `--before`).
- The S2 Task-0 descriptors that S1's content test checks are copied verbatim from the current S2 plan.
