<!-- Companion to PHASE2_REMAINDER_PLAN.md — research/audit memo produced 2026-09-03 by an independent Fable 5.1 agent under Ocean's direction; read-only investigation; verbatim except for privacy scrubbing of archive filename fragments. -->

# Repository memo — the deterministic validator, the parser landscape, and the contract a generalized reconstruction must satisfy

Read-only investigation at `train11` / `phase2.1-final` (HEAD `21e3163`). Every claim cites file:line as of that tree. No repository file was modified.

---

## 1. What "validated" actually means — the composite predicate

There is no single `validated` function. The verdict is a fold over five layers, each fail-closed. Reading bottom-up:

### 1.1 The outcome classifier (telemetry)

`telemetry/record.py:540-593` `classify_outcome`:

```python
    if metrics.get("average_daily_balance") is None:
        return "withheld", "withheld_adb"
    flags = list(integrity.get("flags") or [])
    if "parser_ambiguous" in flags:       return "review", "parser_ambiguous"
    if "parser_exception" in flags:       return "review", "parser_exception"
    if "integrity_check_exception" in flags: return "review", "integrity_check_exception"
    if flags:                             return "review", "integrity_flags"
    if quality.get("corporate_use") != "approved":
        return "review", "quality_needs_review"
    return "validated", "approved"
```

So **validated ⇔ ADB published ∧ zero integrity flags ∧ corporate_use == "approved"**.

Document fold: `telemetry/record.py:596-636` `classify_document` — "the WEAKEST account's, fail-closed"; a document with no account, or an omission outside `RATIFIED_OMISSION_REASONS`, is `failed`. "`validated` on a document therefore means every account validated".

### 1.2 ADB published (metrics)

`analysis/metrics.py:437-459`:

```python
    m.adb_ok = (trust_running_balances and adb.ok if adb.daily_balances else None)
    ...
    if balances: m.average_daily_balance = adb.underwriting_adb
```

where the caller (`analysis/pipeline.py:1085-1094`) passes
`trust_running_balances=recon.ok and not any("UNCAPTURED" in t.description.upper() ...)`.

### 1.3 `adb.ok` — the ledger-integrity predicate

`analysis/adb.py:611-793` `_validate`. The REQUIRED checks (`adb.py:774-793`), verbatim:

```
        "statement_period_dates_valid",      # printed period_start/end parse, ordered, == resolved period
        "all_transactions_dated",
        "transactions_within_period",
        "bank_daily_balance_dates_valid",
        "daily_balance_count_equals_calendar_days",
        "daily_balances_contiguous",
        "covers_opening_day",
        "covers_closing_day",
        "final_balance_matches_statement_closing",
        "opening_balance_matches_statement",   # H1: a PRINTED beginning balance is required
    + "ledger_reconciles_to_closing"           (when a closing is printed)
    + "running_balances_support_daily_ledger"  (when any row carries a printed running balance)
    + "posting_dates_cover_source"             (when source_markdown is supplied)
    result.ok = all(checks.get(name, False) for name in required)
```

Note `statement_period_dates_valid` (`adb.py:629-636`) requires `stmt.period_start`/`period_end` to be present AND equal to the resolved period — an inferred period cannot support an ADB. `opening_balance_matches_statement` (`adb.py:711-719`) requires a printed `beginning_balance`. `posting_dates_cover_source` (`adb.py:739-758`) compares parsed row dates with `source_posting_dates(source_markdown, ...)` — a TEXT heuristic (`analysis/dates.py:355-470`) unless the markdown carries a `SOURCE_POSTING_DATES_BEGIN … SOURCE_POSTING_DATE|…` block (`dates.py:398-418`), which a "layout-aware native extractor" may embed to give the ADB an authoritative posting-date list.

### 1.4 `recon.ok` — reconciliation

`analysis/reconcile.py:94-314`. `ok = not issues` (`:290`). Issues are appended when:

- no beginning (or implied beginning from stated totals) or no ending balance (`:127-128`);
- `|beginning + Σamount − ending| > 0.01` (`:116-126`, `_TOL = 0.01`);
- any running-balance continuity break (`:133-150`; first 5 append issues, all counted);
- the bank's own summary identity fails by > 1.00 under all four fixed identities (`:159-181`);
- credit or debit coverage vs stated totals outside `[0.98, 1.02]` (`:237-254`).

Count matches are computed (`:266-288`) but "Deliberately appends NO issue" (`:256-259`) — they become flags one layer up.

### 1.5 `corporate_use == "approved"` and the integrity flags

`analysis/pipeline.py:255-322` `assess_quality`: approved only when `recon.ok and aggregate_rows == 0` AND the claiming registration is `formal_statement` (`:265-275`).

`analysis/pipeline.py:431-661` `assess_document_integrity` — flags (any one blocks `validated`): `summary_math_inconsistent`, `ledger_sum_mismatch` (|sum_delta| > 1.0), `running_balance_breaks`, `credit/debit_detail_coverage_mismatch`, `transaction_detail_not_corporate_reliable`, `not_a_formal_statement`, `credit_count_mismatch` / `debit_count_mismatch` (only when `counts_comparable(claiming_parser, direction)` — `analysis/count_semantics.py:1364-1371`, default UNSURVEYED = not comparable), `parser_ambiguous`, `parser_exception`, `repair_exception`, `integrity_check_exception`, `conflicting_statement_summaries` (registered per-parser `integrity_checks`, `parser_registry.py:1030`), `missing_declared_statement_page` (`:574-651`, reads `Page N of M` from markdown + `sheets`).

### 1.6 The generic structurer's own pre-gates (when it is the producer)

`analysis/structurer/core.py:130-206`: refuses unless rows exist (`no_dated_rows`/`no_signable_rows`), a PRINTED period exists (`no_printed_period`, `:132-136`), every row is inside the period (`:176-183`), the ledger reaches the printed closing within 0.02 (`ledger_incomplete`, `:191-194`), and grounding passes (`ungrounded`, `:196-204`; grounding coverage 1.0 — W3_3C §8.4).

### 1.7 Summary of everything a candidate must carry to reach `validated`

| requirement | enforced at |
|---|---|
| printed beginning balance | `adb.py:711-719` (H1) |
| printed ending balance | `reconcile.py:127`; `adb.py:695-701` |
| printed period start AND end | `adb.py:629-636` |
| every row dated, inside the period | `adb.py:638-639` |
| Σ signed amounts closes the ledger to the cent (0.01) | `reconcile.py:121`; `adb.py:703-709` (0.00) |
| every printed running balance continuous | `reconcile.py:136-150`; `adb.py:721-737` |
| row dates cover every posting date the SOURCE TEXT prints | `adb.py:739-758` ← `dates.py:355` |
| stated totals (if printed) within 2 % and summary identity within 1.00 | `reconcile.py:159-181, 237-254` |
| stated counts (if printed and comparable) exact, keyed on `direction` | `reconcile.py:266-288`; `pipeline.py:513-519` |
| declared pages present | `pipeline.py:574-651` |
| no UNCAPTURED aggregate rows | `pipeline.py:259, 293-300` |
| registration is a formal statement | `pipeline.py:265-275, 498-500` |
| for the structurer: grounded on the page text; ledger reaches closing | `structurer/core.py:191-204` |
| currency: NOT gated for `validated`, but provenance-tracked (`currency_source`) and fail-closed at the package | `schema.py:85-101, 154-166`; PKG-CURRENCY |
| multi-account: each account independently; idle siblings only on printed evidence | `pipeline.py:1030-1060`; `sibling_omission.py:1-90` |

---

## 2. The candidate contract — what a producer hands the validator

### 2.1 The type, verbatim (`analysis/schema.py:104-224`)

```python
class Transaction(BaseModel):
    date: str            # ISO YYYY-MM-DD
    description: str
    amount: float        # Signed: negative for debits (money out), positive for credits (money in)
    direction: str       # 'Either "debit" or "credit".'
    running_balance: float | None = None

class Statement(BaseModel):
    # ONE ACCOUNT's statement — which is what this model has always meant.
    bank: str | None; account_name: str | None; account_number: str | None
    period_start: str | None; period_end: str | None
    beginning_balance: float | None; ending_balance: float | None
    currency: str = "USD"; currency_source: CurrencySource = "schema_default"
    days_in_period: int | None
    stated_total_credits / stated_total_debits: float | None     (POSITIVE magnitudes)
    stated_credit_count / stated_debit_count: int | None
    bank_reported_average_balance: float | None; bank_reported_average_label: str | None
    stated_service_charge / stated_interest_paid: float | None; stated_nsf_count: int | None
    stated_daily_balances: list[StatementDailyBalance]
    initialization_transaction_count: int = 0
    transactions: list[Transaction]
```

The schema docstring is a MODEL PROMPT (`schema.py:135-141`; `extract.py:222` passes it as `response_schema`), pinned by digest in `tests/test_extraction_schema_prompt_surface.py` — any field/description change is a red test.

### 2.2 The producer protocol

`analysis/parser_registry.py:456-473`:

```python
class Parser(Protocol):
    id: str; bank: str
    def detect(self, markdown: str) -> Detection: ...
    def parse(self, markdown: str) -> Statement | None: ...

@dataclass(frozen=True)
class Registration:
    id; bank; markers: tuple[Marker, ...]; parse: Callable[[str], Statement | None]
    normalize; band (10/100/900); supersedes; formal_statement: bool = True; integrity_checks
```

**A parser receives a markdown STRING and nothing else.** Markers are pure tests over the markdown (`:157-170`). Dispatch (`:949-1027`): every registration detects; `supersedes` prunes; **>1 survivor ⇒ `ambiguous` BEFORE any parse runs** ("so an ambiguous document can never be rescued by whichever parser happens to succeed"); survivors parsed best-first; a `None` is "declined"; a raise is a `ParserFailure` (class name only); nothing ⇒ `unclaimed` or `parser_exception`.

### 2.3 Multi-account contract

`analysis/multi_account.py:55-207`: a reader that establishes several accounts returns the FIRST via `parse` and calls
`publish_partition(accounts=[PublishedAccount(statement, section_text, label), ...], boundary_mechanism=..., document_period=..., rollup=RollupEvidence(caption_class, column_roles_printed, rows, cross_account_total_printed))`.
The pipeline settles the claimed partition BY IDENTITY of the returned statement (`:127-146`), validates each sibling with the unchanged validator against its OWN `section_text` (`pipeline.py:1030-1060`). `DocumentReport` (`pipeline.py:224-268`) carries accounts in printed order, `omissions`, `rollup` (a figure may be taken from it only when `column_roles_printed`), `internal_transfers` (arithmetic + document-wide uniqueness + printed designation, `pipeline.py:1190-1336`), and closed `integrity_notes`.

Omitted siblings: `analysis/sibling_omission.py:1-90` — closed evidence vocabulary (`printed_dormancy_declaration`, `printed_zero_activity_summary` [six clauses], `yield_only_arithmetic_with_summary_equality`); `absence_of_parsed_rows` "is not a member and cannot become one"; otherwise the whole document refuses.

### 2.4 Where direction comes from and how it is verified

- `direction` is DECLARED by the producer; the validator never infers it. `reconcile.py:42-47`: counts are "Keyed on Transaction.direction (the column the bank printed the row in), NOT on the sign of the amount". Sums use the sign (`:106, 186-187`). `adb.py:459-470` (initialization event) tests BOTH halves and calls a `+1000.00` row labelled `debit` a contradiction.
- Nothing in `reconcile`/`adb` checks `direction` against `sign(amount)` for ordinary rows — a producer that emits `amount=-50, direction="credit"` is only caught when a printed count exists and is comparable. **This is a contract gap a generalized producer must close on its own side** (emit both from one decision, and self-check).

### 2.5 Evidence the validator requires that is NOT a number

- **Text**: `markdown` (for `Page N of M`, registered integrity checks, `posting_dates_cover_source`, structurer grounding) — `pipeline.py:781, 796, 1074-1084`.
- **`sheets`**: the intake object's page list (`StatementMarkdown.pages`), NEVER re-split from markdown (`pipeline.py:431-457, 620-640`).
- **`source_markdown`** (per-account section scope) for the posting-date check (`pipeline.py:1008-1028`).
- **`Dispatch`** — the claiming registration id keys count semantics, summary repairs, integrity checks (`pipeline.py:243-252`; `count_semantics.py:1400-1419`).
- **`document_geometry`** — accepted (`pipeline.py:781, 800`) and forwarded to exactly one consumer, `structure_unclaimed` (`:843-848`). **No production or discovery caller passes it**: `webapp/worker.py:238-242`, `webapp/artifact_cache.py:255`, `discovery/runner.py:976-979` all call `analyze_document(markdown, parse_mode=…, on_dispatch=…, sheets=…)` with no geometry. The seam is still dark, as `DESIGN_GEOMETRY_INTEGRATION.md` §1 recorded on 2026-08-10 ("Nothing in production computes geometry").

---

## 3. The parser landscape

### 3.1 Numbers and dispatch

- **84 registrations** over ~73 modules (`analysis/parser_registry_entries.py:108-…`; `grep -c` = 84), ids alphabetical; order is `(band, id)` computed from data (`parser_registry.py:509-511`).
- Band 10 + `supersedes`: `burke_herbert`, `farmers_merchants`, `linkbank` ⊃ `core_processor_enclosures`; `td_canada_native` ⊃ `td_canada` (`entries.py:500-514`).
- `formal_statement=False`: `found_lead_activity` (month-to-date view) — the only informal class (`entries.py:564`).
- Registered integrity checks (contradiction oracles) on 15 registrations (bmo, bmo_ca_business ×2, bmo_us_activity, shopify_balance, citibusiness, zions, square_checking, columbia_bank, mercury, found_lead ×2, brex, eq_bank_scanned, citizens, scanned_small_bank).

### 3.2 The TEMPLATE families (issuer-agnostic, but not layout-agnostic)

These are the "generic" registrations. They are generic across ISSUERS on one core-processor PLATFORM, not across layouts:

| registration(s) | module | what it keys on | proof it demands before publishing |
|---|---|---|---|
| `core_processor_sectioned` | `core_processor_sectioned.py:1-40` | `LAST STATEMENT mm/dd/yy <fig> … N CREDITS … M DEBITS … THIS STATEMENT … TOTAL DAYS IN STATEMENT PERIOD` strip; `DEPOSITS/OTHER CREDITS/CHECKS/OTHER DEBITS` sections; `DAILY BALANCE` grid | "Five printed figures and one printed grid, all of them, exactly": counts per direction, totals per direction, `opening + credits − debits == closing`, every grid day equals the reconstructed ledger |
| `core_processor_daily` | `core_processor_daily.py:1-40` | `Last statement: <long date>` / `This statement:` / `Total days in statement period:` sentences; `Total additions/subtractions`; `DAILY BALANCES` | same discipline; a second grammar of the same platform — "Not one grammar is shared" |
| `core_processor_counted` | `core_processor_counted.py:1-40` | the period sentence pair + DATED `Beginning balance (m/d/yyyy)` / `Ending balance (…)`; a counted PARTITION (three categories per direction) | partition counts + totals + grid |
| `core_processor_enclosures` | `core_processor_enclosures.py:1-40` | one welded summary line `Number of Enclosures … Previous Balance … n Deposits/Credits … m Checks/Debits … Ending Balance`; `Date Balance` grid | same; the largest unclaimed identity in batch 8 (58 docs) |
| `core_processor_activity_summary` | `…activity_summary.py:1-40` | boxed `Activity Summary` + per-row running balance | running balance chain + summary |
| `core_processor_signed_counts` | `…signed_counts.py:1-40` | `Credits (N) +$ … Debits (M) -$` summary | signed partition + grid |
| `balance_by_date` | `balance_by_date.py:1-40` | six-row summary grid `PREVIOUS BALANCE / N CREDITS / M DEBITS / SERVICE CHARGES / INTEREST PAID / ENDING BALANCE` + `Balance By Date` grid | the six figures + the daily walk; "this reader refuses a document whose printed counts it cannot reproduce" |
| `category_partition` | `category_partition.py:1-45` | `Category Number Amount` line; signs read from a TRAILING PLUS on money-in categories, "no category label appears anywhere in this module's sign DECISION" | `Balance Forward + Σ(marked +) − Σ(unmarked) == Ending Balance` |
| `community_section` (+ `dakota_west`, `mission_valley`) | `community_section.py` | one printed date format `%m/%d/%Y`, `$` money, signed balances only | section ledgers + omissions via `sibling_omission` |
| `member_statement_rollup` | `member_statement.py:1-40` | enumerating table with a COLUMN CAPTION from a closed vocabulary; each enumerated identity reappears as a section heading | rollup oracle; refuses without caption (30 of 214 tables print one) |
| `symitar` | `symitar.py:1-40` | `ACCOUNT SUMMARY` + per-account deposit grid | per-section arithmetic; yield-only dormancy |
| `scanned_small_bank` (`apex_scanned`, `southside_scanned`, `texas_first_scanned`) | `scanned_small_bank.py:1-38` | Tesseract text of small-bank scans; check-image captions as independent amount evidence | daily-grid contradictions as a registered integrity check |
| `releve_facturation` | `releve_facturation.py:1-35` | French template, no issuer printed | grid identities |

**Hidden assumptions in the template families** (from the docstrings and regexes):
1. Every one keys on the FLATTENED TEXT ORDER of a specific PDF producer — e.g. enclosures' "the flattened text layer welds the platform's two columns into it, left cell then right cell, in this order". A different renderer (or OCR) of the same paper breaks the grammar.
2. Exact label grammars (`_PERIOD_RE`, `DEPOSITS/CREDITS (N)`, `Last statement:`), sometimes one character apart across siblings — each variant is a NEW registration by design (`core_processor_daily`: "widening … would have made it CLAIM these 20 documents … and then decline all 20 at parse, which is a detector that lies").
3. English/French label vocabularies (structurer too: `rows.py:52-60`, `summary.py:47-…`, `tokens.py:40-52`).
4. Direction from section headings or platform sign marks; row shape regexes per template.
5. Description attribution on flattened text was wrong 40 % of the time on the core-processor complex (DESC-ATTRIB) — fixed with line boxes (DESC-COLUMNS → `ocr/native_text.py:1453` `parse_native_printed_rows`), which proves the text layer alone cannot carry column identity.

**What they teach the generalized path**: the PRINTED-ORACLE discipline. Every template proves itself against what the bank printed — per-direction counts, per-direction totals, the opening/closing identity, and the daily-balance grid — and refuses otherwise. That discipline is layout-independent even though the readers are not. A generalized reconstruction should discover those oracles by LABEL CLASS + GEOMETRY rather than by exact grammar, and then apply the same identities. The count-semantics table (`count_semantics.py:1-70`) is the warning: printed counts do not all denote the same row set, so a generic count oracle must default to "not comparable" exactly as the table does (`:1364-1371`).

### 3.3 Geometry that already exists in the intake layer

`ocr/native_text.py` holds per-bank native rungs that read PyMuPDF line/word boxes: `parse_native_navy_federal` (:288), `parse_native_woodforest` (:500, via `ocr/column_grid.py` — "a column exists only where the document printed its name … It never decides what a column *means*"), `parse_native_first_citizens` (:801), `parse_native_desjardins` (:852), `parse_native_td_canada` (:884), `parse_native_wells_fargo` (:905, fixed x-bands `395–452 / 452–520 / ≥520` — the W-F7 "geometry read as constants" defect), and the generic `parse_native_printed_rows` (:1453, `get_text("dict")` line boxes → per-row descriptions, repeated-furniture removal). `DESIGN_GEOMETRY_INTEGRATION.md` §2 partitions the residual into **G1 (column identity discarded, rows intact — 14 docs: TD 10, Wells 4)** and **G2 (grid order destroyed — 9 docs: RBC 6, PNC 3)** and §3.1 REJECTS routing claimed documents to the structurer ("a 'withheld → try the structurer' retry branch … the platform would choose between two readings by which one passes the gate").

### 3.4 The archived universal prototype

`docs/moneythumb-replacement/PROTOTYPE_REVIEW.md` (tags `archive/universal-prototype-2026-08-04/-05`): both branches converged on AD-7 — "any structurer … fills the same `Statement` schema and faces the same deterministic reconciliation/fail-closed gate; trust comes from the gate, never from the extractor". Kept: `grounding.py` ("the gem" — rebuilt as `analysis/structurer/grounding.py`), the offline gate-measurement harness (`eval_unknown_banks.py`, the model for `tools/measure_structurer`), contract docs. **Rejected**: first-match registry (no ambiguity outcome), protected-module rewrites, Gemini-centric routing, and — relevant here — the "bounded-retry-with-feedback loop … `_is_better` picks the best attempt by reconciliation quality" (item 3), which is the validator-as-optimizer pattern by name. It was catalogued for telemetry field design only.

---

## 4. The generic structurer (`analysis/structurer/`, 1,951 lines) from the validator's side

### 4.1 Pipeline placement

`pipeline.py:836-848`: runs only when `deterministic_stmt is None and dispatch.outcome == "unclaimed"`; never for `ambiguous`/`parser_exception`; OFF unless `GENERIC_STRUCTURER_ENABLED` (`structurer/core.py:45, 63-64`); returns `None` rather than raising (`:216-233`). On the structurer branch `apply_statement_repairs` is NOT run (`pipeline.py:906-912`) — the bank-keyed rewrites cannot touch it. `model_used = "generic-structurer-deterministic"` (`core.py:53`). The flag partitions the analysis cache key (`webapp/artifact_cache.py:145-155, 916-930`).

### 4.2 What it produces

`core.py:138-160`: `Statement(bank=None, period_start, period_end, transactions=[Transaction(date, description, amount, direction, running_balance)], **summary fields, bank_reported_average_label)`. It does NOT produce: `account_number`, `currency` (schema default ⇒ `currency_source="schema_default"`), stated COUNTS (label list `summary.py:47-…` has totals/average/service charge/interest but no count labels), a multi-account partition, a per-account source scope, or a `SOURCE_POSTING_DATES` block. So it satisfies the single-account arithmetic contract and leaves the currency, count-oracle and multi-account requirements unmet.

### 4.3 How it decides rows, columns and signs (`rows.py`)

- Lines from `DocumentGeometry` (`source_lines_from_geometry`, `:155-161`) or flattened markdown with `<tr>` flattening (`:112-153`).
- Date column: x-position of the first date on each line, 1-D gap clustering (tolerance 6 pt), biggest cluster must hold ≥ `MIN_CHAIN_ROWS`=5 and ≥ 50 % of dated lines (`:186-212`); without geometry a date must lead the line (`:280-283`).
- Continuation lines: a non-dated, money-free line < 120 chars is appended to the previous row's description (`:288-293`).
- Summary furniture excluded by prefix regex (`:62-72`).
- Money columns: x-clustering (tolerance 12 pt, ≥5 per band) (`:215-229`).
- Hypothesis 1 (`_score_chain`, `:340-357`): last token = running balance, penultimate = amount; accepted iff `|Δbalance| == amount` on ≥ 90 % of ≥ 5 checked rows (`MIN_CHAIN_AGREEMENT=0.9`, `:44-51`).
- Debit/credit bands (`columns_debit_credit`, `:445-484`): votes from balance movement, ≥3 votes and 3:1 majority.
- Sign source precedence (`:395-427`): `balance_chain` → `credit_column`/`debit_column` → `section_heading` (only when NOT chained) → refuse the row.
- `RowCandidate.direction` is derived from the sign (`:118-121`) — one decision, both fields.

### 4.4 Summary, period, grounding

`summary.py:47-…` label→field table (EN + `SOLDE …`); period from an explicit range or the dates beside opening/closing labels, `balance forward + 1 day` convention with provenance and a refusal on a posting before the inferred start (W3_3C §8.2). `grounding.py:1-120`: re-locates every amount on its claimed page within 240 chars of its date and a distinctive description word; span uniqueness; summary values beside a label within 180 chars; printed period; "no provenance → not publishable". Coverage 1.0 required (W3_3C §8.4).

### 4.5 Measured limits (W3_3C_STRUCTURER.md §4, §4b, §7)

109 pinned: 6 published / 5 validated / 0 wrong; refusals `ledger_incomplete` 53, `no_printed_period` 19, `ungrounded` 12, `no_dated_rows` 11. 75 unclaimed archive docs: 4 validated (5.3 %). Sign provenance: 58–78 % heading, 21–42 % chain, < 1 % column. "The binding constraint is completeness": rows are missed. Known limits: small statements (< 5 rows) cannot establish signs; multi-account read as one ledger; scanned documents got no geometry (now addressable via Paddle evidence → `geometry_from_evidence`, `structurer/geometry.py:343-405`).

### 4.6 Structurer safety tests

`tests/test_structurer_safety.py:1-20`: "zero false validations · protected core intact · fail closed when evidence is insufficient … every test below therefore accepts 'no statement' as a pass and accepts a published statement ONLY when it is right"; synthetic documents dated 2054.

---

## 5. The text-first assumption, and what a geometry-native producer must bypass or adapt

1. **Registry dispatch is text-only** (`Registration.parse: Callable[[str], …]`, markers over markdown). A geometry-native producer cannot be a registration without widening the protocol; today the only geometry consumer is the unclaimed-branch structurer.
2. **The admissibility boundary is a text rebind** (`pipeline.py:757-780`, `prepare(markdown).admissible`); `DocumentGeometry` "is built from OCR word boxes, not from this string" — geometry is not filtered for the source-filename comment (no such comment exists in evidence, so no gap, but it must stay that way: filename metadata must never enter evidence).
3. **Four validator checks read TEXT**: page declarations (`pipeline.py:427-429, 574-651`), registered integrity checks (`:539-547`), `posting_dates_cover_source` (`dates.py:355`), structurer grounding (`grounding.py`). A geometry-native producer must either render its evidence to the markdown the pipeline consumes (the `SOURCE_POSTING_DATES_BEGIN` side-channel at `dates.py:398-418` is the existing precedent for injecting authoritative structure into the text stream) or supply geometry-aware equivalents — and the cache must know which.
4. **The analysis cache key is geometry-blind**: `webapp/artifact_cache.py` keys analysis on `(markdown, sheets, parse_mode, stage_version, registry fingerprint, structurer flag)` (`:136-160, 905-930`); `document_geometry` is not in the input hash. Wiring geometry into production without adding evidence identity (e.g. `ExtractionEvidence` sha) to the key would serve stale answers.
5. **Per-account source scope** is `section_text` (a substring of the markdown) — a geometry producer must produce a text scope (or an evidence-scoped date list) per account.
6. **`sheets`** must come from the intake object (`StatementMarkdown.pages`); an evidence page count is the same fact in another object — they must agree.
7. **`Dispatch` keys everything bank-specific** (count semantics, summary repairs, integrity checks). A generic producer has no registration ⇒ `counts_comparable` is False by default (no count flags), no repairs, no integrity checks — which is exactly the fail-closed default the tables intend, but it also means a generic producer gets NO printed-count oracle unless it declares its own comparable semantics.

---

## 6. Direction / sign — the crux, as the repository handles it today

| mechanism | where | note |
|---|---|---|
| explicit sign glyphs on the token (`-`, trailing `-`, `(…)`, `D/DR/OD`, U+2212, U+2013) | `analysis/money.py:1-50`; SIGN-READER fixed the structurer's `abs()` inversion (`tokens.py`) | a CLASS of glyphs, not a character |
| printed column named in the header | `ocr/column_grid.py:1-40` (Woodforest) — "It never decides what a column *means* and never repairs a row" | bands from header word boxes; unknown cell ⇒ `GridRefusal` |
| section headings (`DEPOSITS`, `CHECKS`, …) | every `core_processor_*`; structurer `_section_sign` (`rows.py:246-258`) | English/French furniture words |
| platform sign marks (trailing `+`) | `category_partition.py` | sign decided without any category label |
| balance-chain arithmetic | structurer `rows.py:340-357, 445-484`; `bank_repairs.py` sign repairs | arithmetic identifies a COLUMN ROLE, at high agreement thresholds |
| printed per-direction totals/counts as oracles | all template families; `reconcile.py:266-288` | counts keyed on `direction` |
| no direction ⇒ no row | structurer (`rows.py:427-429`), `column_grid` | fail closed |

Known geometry-class defects already named: TABLES-GRID-BALANCE (`tables.py:read_grid_rows` assigns a line-opening money cell to the PREVIOUS row's balance by adjacency — the RBC six; fix "by PRINTED structure (column position from the header, or the row's own date), never by adjacency"); WITHHELD-GRIDS (posting-date heuristic false positives on boundary rows, interest-rate lines, page-header dates, a second account's grid, marketing sentences — each rule measured on both axes, `dates.py:375-396`); DESC-ATTRIB/DESC-COLUMNS (descriptions welded to the wrong row on flattened text — solved with line boxes).

---

## 7. Multi-account and package rules a generalized reconstruction must honour

Rulings R-a…R-f (`L1_INDEPENDENT_ACCOUNT_DESIGN.md` §0): idle sibling only on explicit printed structure; each account validated independently by the UNCHANGED validator; no document-level combined ADB (roll-up is an oracle only); inter-account transfers stay in both ledgers and are flagged INTERNAL only under arithmetic + uniqueness + printed designation; no memorised account selection; one denomination per account, two currencies ⇒ two accounts or refuse.

Concretely a generalized reconstruction must: (a) find account SECTIONS from printed boundaries (headings, enumerating tables with printed column roles); (b) emit N `Statement`s + N `section_text` scopes + `boundary_mechanism` + `document_period` (+ `RollupEvidence` when a roll-up table is printed) via `publish_partition`; (c) admit an idle sibling only with one of the closed omission evidence classes, else refuse the DOCUMENT; (d) never fold two accounts into one ledger (the structurer does today and refuses on `ledger_incomplete` — "Correct, but crude", W3_3C §7.5); (e) publish a per-account currency with an earned `currency_source` (`schema.py:31-92` — "a reader may not set a source it did not earn").

---

## 8. Test infrastructure and fixture rules

- **Default suite**: `pytest -q` with `-m "not live and not corpus"` (`pytest.ini`); 182 entries under `tests/`; `conftest.py` routes `WEBAPP_DATA_DIR` to a temp dir.
- **Canonical guards (5 files, 275 tests)**: `test_no_statement_hardcodes.py` (AST + regex scans of `analysis/` AND `ocr/` (OQ2) for literal years, amounts, account-number runs, calendar literals, mojibake; layer-wide), `test_no_parser_helper_clones.py`, `test_r1_hardcodes.py`, `test_experiments_are_not_wired.py`, `test_filename_boundary.py` (PHASE2-RULES.md; PHASE2-RULES "No statement-specific hardcodes — now in `ocr/` too").
- **Canonical conformance (7 files, 1,282 tests)**: `test_parser_conformance.py` (per registration: detection-positive, detection-negative as an 84×83 cross product, self-invalidation, filename invariance), `test_parser_registry_entries.py`, `test_parser_detection_markers.py`, `test_parser_registry.py`, `test_parser_crash_shapes.py`, `test_parser_exception_boundary.py`, `test_count_semantics.py`.
- **Corpus gate** (`corpus_gate.py:1-120`): 109 pinned PDFs (105 PASS / 3 WITHHELD / 1 REFUSED), offline, pins verdict + whole integrity block + ADB basis + currency + currency_source; the 6 image-only statements served from committed OCR artifacts keyed by SHA; `pytest -m corpus` = the 34-test corpus slice.
- **Architectural tripwires**: `tests/test_escalation_tripwires.py` (router import boundary, `RouterInputs` field set and no-subclass pin), `tests/test_evidence_boundary.py` (`evidence/` stdlib-only), `tests/test_geometry_frames.py` (AST guard against a second line-grouping rule), `test_extraction_schema_prompt_surface.py` (schema digest).
- **Mutation tables**: `tools/*_mutation_table.py` + `*_mutants.py` (e.g. `tools/cpdecl_mutation_table.py:1-25`): exact-string mutants applied to production source, run WITHOUT `-x`, a NAMED test must fail, restore verified by `git status --porcelain`; refuses a dirty tree. PHASE2-RULES requires one "for every gate, router edge, charset, allowlist or selection rule you add … prefer tests that prove the ABSENCE of a forbidden edge".
- **Replay / sweep instruments**: `tools/cohort_replay.py` (`--expect-identical` at base, at closure over named cohorts), `tools/regfp_zero_movement_sweep`, `tools/privacy_scan_branch.py` (0 MONEY/DIGITS/DATES residue required), `tools/measure_structurer.py`.
- **Fixture privacy (FIXTURE-PRIVACY 1–3)**: **real customer statements may NOT be tracked fixtures.** Invented shapes only; dates in 2031 (paddle_synthetic) / 2054 (structurer safety) / +28-year shifts; money scaled on cents with tolerances kept absolute; identifiers invented and proven non-colliding by the scanner; the only tolerated archive text is `tests/corpus_cache/` (excluded by rule) and the three `docs/*-audit-results.csv` truth files (ruling R3). Reports never print document text or figures.
- **Synthetic fixture facilities**: `tests/paddle_synthetic.py` (`build_ledger_page` → `render_native_pdf` / `render_image_pdf` / `synthetic_paddle_result`, positions known up front — the same ground truth drives native, raster and Paddle-shaped results), `tests/paddle_fake_worker.py`, `tests/data/parser_conformance_fixtures.py` (a minimal document per registration + alternates), `tests/test_structurer_safety.py` adversarial documents, `tests/l1s3_payloads.py` / `l1s4_pages.py`.

---

## 9. Every place the validator could become an optimizer — and how it is guarded today

| # | site | what it does | guard / status |
|---|---|---|---|
| 1 | `analysis/bank_repairs.py:24-55` `repair_capital_one_running_amount` | computes `needed_delta = ending − (beginning + Σ)` and REWRITES the one row whose balance-implied amount closes it | bank-keyed (`"CAPITAL ONE" in bank`); live, wired at `pipeline.py:106-115` |
| 2 | `bank_repairs.py:58-84` `repair_regions_transactions` | sets a zero-amount `CARD TRANSACTION` row to `needed_delta` when exactly one exists and `|Δ| ≤ 100` | bank-keyed; live |
| 3 | `bank_repairs.py:115-159` `repair_chase_remote_deposit_count_column` | corrects a fused count digit when the identity demands exactly that correction | evidence-gated (digit-suffix proof); live |
| 4 | `bank_repairs.py:162-196` `repair_single_row_signs_from_balances` (CIBC/RBC), `:199-215` Scotiabank, `:218-238` Santander | flips one row's sign so the balance chain closes | balance-chain evidence, bank-keyed; live |
| 5 | `bank_repairs.py:87-112` `repair_truist_converted_checks`; `pipeline.py:99-104` `_SUMMARY_REPAIRS` (bofa, regions) | drop / rewrite rows and stated figures from labels | keyed on the CLAIMING registration (`pipeline.py:106-131`) |
| — | doctrine | REPAIR-DOCTRINE (Gustavo 2026-08-21): "Parsers must never rewrite transaction amounts just to force reconciliation. Replace repair-by-rewrite with discard-and-flag / fail-closed." Executed for `columbia_bank` only; `bank_repairs.py` predates it and remains. REPAIR-GUARD guards only RAISES (`pipeline.py:855-903`). | **the structurer branch skips `apply_statement_repairs` entirely (`pipeline.py:906-912`); any Phase 2 generic producer must stay on a branch these never reach** |
| 6 | `reconcile.py:159-181` | summary identity accepted under the closest of FOUR fixed identities (service charge / interest folded or not), `min(residuals, key=abs)` | bounded, doctrine-documented tolerance (not a candidate search); `_debit_coverage_target` (`:63-84`) likewise |
| 7 | `reconcile.py:197-235` | reversal-adjusted coverage picks the candidate nearer the stated totals | informational coverage only; feeds flags, never `ok` |
| 8 | `pipeline.py:940-990` LLM escalation | "prefer whichever extraction's summary reconciles, falling back to fewer overall issues" — `if alt_recon.ok or better_summary or fewer_issues: stmt = alt` | hosted-model branch only; unreachable in `parse_mode="deterministic"` (`:943-960`, PRIVACY-3); $0-vendor rule keeps it out of every run of record. **It is the exact pattern Phase 2 must never replicate.** |
| 9 | `structurer/rows.py:340-357, 445-484` | balance-chain / column votes use arithmetic to IDENTIFY a column role | accepted design (W3_3C §2) with high thresholds (≥90 % of ≥5 rows; 3:1 votes); the line not to cross is "try several full interpretations and keep the one that balances" |
| 10 | archived prototype `_is_better` retry loop | picks the best attempt by reconciliation quality | REJECTED for production (PROTOTYPE_REVIEW item 3) |
| 11 | `ocr/escalation.py:1-60` + `discovery/runner.py:335-370` | router cannot see `claimed`/`validated` (`RouterInputs` has no field; tripwires); `classify_failure` checks `validated` FIRST | structural: "Validator failure may NEVER START escalation" |
| 12 | `parser_registry.py:949-1027` | ambiguity decided BEFORE any parse | structural |
| 13 | `multi_account.py:127-146`, `sibling_omission` | losing candidates' partitions/omissions discarded by identity | structural |

---

## 10. What I could NOT determine

- I did not re-run the suite/gate; counts (8,756 / 275 / 1,282 / 105-3-1 / 34) are taken from the brief and PHASE2-RULES, not reproduced.
- I did not read the bodies of the 15 registered `integrity_checks` or `assign_transaction_years`; their contracts are inferred from call sites.
- Whether the webapp's default `parse_mode="auto"` path ever reaches `extract_statement` in production depends on `GEMINI_API_KEY` presence (`analysis/config.py:31`); the code path exists (`pipeline.py:936-937`) — I did not audit deployment configuration.
- The exact `analysis_input_sha` composition beyond the settings key (`webapp/artifact_cache.py`) was read only at the docstring level.
- Current corpus fallout for the structurer at `phase2.1-final` (W3_3C numbers are from 2026-08-07 at a much smaller registry).
