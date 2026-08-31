# BATCH9 — L1-S4-FIRST-PUBLISHER, independent adversarial review

**Branch** `wave9-l1s4`, base `train9` `eeaf566`, tip `e8f0ab4` (21 commits, clean tree).
**The decisive tree** is a throwaway worktree merging `train9` `f068b35` with the branch —
`.claude/worktrees/rev-l1s4-merged` at `5ec8a1a`. **The merge is CLEAN: 0 conflicts, 30 files**
(train9's only movement since the base is docs, and its `W3_TRACKA_LOG.md` is byte-identical to
the base's).

Everything below marked **measured** was re-run by this reviewer. Everything marked
**reproduced** was folded by this reviewer from the cell's stored per-chunk artifacts with the
reviewer's own arithmetic — not read off the cell's summary. A claim I did not reproduce is a
claim I do not confirm; there are none of those.

# VERDICT: APPROVE WITH FINDINGS

**BLOCK: none. MAJOR: none. MINOR: 9** (listed in §7). Every headline number reproduced, at the
merged tree wherever a tree could be chosen. No regression; no account published without its own
validation; no transfer flagged without a printed designation; no blended ADB; no demoted
carrier; no number I could not reproduce. The nine findings are precision, record and
docstring-truth defects plus one carried ruling gap — none of them changes a payload, a verdict
or a count.

---

## 1. Claim by claim — claimed vs measured

| # | the cell's claim | what I measured | verdict |
|---|---|---|---|
| 1 | **+8 newly validated, 12 accounts**, `FAM:guardian_cu_statement_summary`, `failed → validated` | re-derived every one through the PRODUCTION document seam at the merged tree (`document_report_to_dict(analyze_document(…, parse_mode="deterministic", sheets=…))`, folded by `telemetry.record.classify_document`): 8 documents `validated/approved`, **12 accounts** (1·1·1·**3**·1·**3**·1·1), all twelve `validated/approved`. Independent 40-document spot replay at the merged tree: 8 newly validated | **REPRODUCED** |
| 2 | the population is the whole census group, all previously `failed` | `census_batch9/clusters.json` → `FAM:guardian_cu_statement_summary` = exactly those 8 shas, `failed/no_parser_matched` 8, route `native` 8. Marker sweep re-run at the merged tree: 3,351 read · **8 claimed · 8 published · 0 refused · 0 claimed that were not `failed`** | **REPRODUCED** |
| 3 | Q9's three figures: strict 0 · production 2 · Q3-eligible 6 → 8, reached not forced | the composed `q3_corroboration_probe`, unchanged, re-run at the merged tree: **N = 6**, demonstrated target 2 + 6 = 8. The 2 are the two documents that close on every located section (`7C7956EB5E93DB1D`, `E38FA786106F752E`); the 6 are the Q3 documents. 8 published, 8 claimed, none forced | **REPRODUCED** |
| 4 | archive replay: 3,380 at both trees, **exactly 8 rows differ**, 3,372 byte-identical, **2,596 / 2,596 preserved at both**, 0 regressions | folded the four stored per-chunk JSONs myself at each tree: 3,380 rows at both over an identical sha set; previously validated **2,596** at both, preserved **2,596** at both, **regressions 0 at both**; newly validated **21 → 29**; rows differing ignoring `ms` = **8**, and they are the eight, each `failed → validated`, reader `member_statement_rollup`; 3,380 − 8 = **3,372** unchanged | **REPRODUCED** |
| 5 | prediction **+1 / +3 / +0 / +4** per chunk | chunk 0 6→7, chunk 1 3→6, chunk 2 8→8, chunk 3 4→8 = **+1 / +3 / +0 / +4** | **REPRODUCED** |
| 6 | sweep attribution: 70 findings identical at both · 0 differing · **8 tip-only** · 0 base-only | folded `sweep_base_0..3` / `sweep_tip_0..3` myself: every field equal at both trees except `no_payload_now_publishes` 21 → 29 and `no_payload_raises_again` 661 → 653; finding sets **70 at both / 8 tip-only / 0 base-only / 0 same-sha-different-verdict**, and the eight tip-only shas are the eight. Then ran `tools.l1s3_sweep_attribution` myself over both stored sets — same table, exit 1 (movers present, by design) | **REPRODUCED** |
| 7 | replay attribution: 3,380 at both, exactly 8 rows differ | ran `tools.l1s3_sweep_attribution --replay-*` myself: 3,380 replayed at both, **8** rows differ, the same eight, on `after` / `after_reason` / `after_parser` / `direction` / `payload` / `changed_paths` | **REPRODUCED** |
| 8 | Q3 class equivalent to the composed probe: 6/6, 30/30 mutants both refuse, 0 disagreements | `tools.l1s4_q3_oracle` re-run at the merged tree: sections 6/6 · probe passes 6 · **production admits 6** · five mutants × six sections = **30 applied, 30 both refuse** · **DISAGREEMENTS = 0**, exit 0. The oracle feeds the PRODUCTION reader's own readings (`reader._DATED_LINE_RE`, `_COUNTS_ROW_RE`, `_prints_daily_table`, `_witness_for`), so this is the reader and not only the predicate | **REPRODUCED** |
| 9 | transfers: 47 pairs / 43 flagged / 4 refused / constructed ambiguous pair refused | `tools.l1s4_transfer_killers` re-run at the merged tree: **7 documents · 47 pairs · 43 flagged · 4 refused · 0 postings whose text could not be recovered**; the constructed ambiguous pair flags 0 and notes `ambiguous_internal_transfer`; agrees with the design, exit 0 | **REPRODUCED** |
| 10 | the 15 protected carriers unchanged; the seam's six movers gain ONLY the `document` key | `l1s2_admission_probe` re-run at the merged tree: 117 validated documents read across the five omission-publishing registrations, **15 carrying an omission, 19 sections, 0 refused, account block byte-identical to the run of record on 15 / 15, 0 documents this tree no longer publishes**. Independently, my own probe over five sampled carriers (incl. the pinned `F748A799FDC7F25E`) compared the published account block against the run of record's cached payload: **byte-identical on 5 / 5, 0 leaves added, 0 removed**. And `tests/test_l1s2_protected_carriers.py` — which asserts the ACCOUNT outcome, the DOCUMENT outcome and the account block for all fifteen — is green inside the merged tree's corpus slice | **REPRODUCED** |
| 11 | leaf classification: 23 documents carry the block, 15 × 10 / 8 × 13, 18 distinct paths | `l1s4_document_replay --leaves` at the merged tree over the 8: 8 carry the block, 13 leaves each, 17 distinct paths across those 8 (the cell's 18 is the union with the carriers' `rollup -> null`). The counts are of INDEX-COLLAPSED paths — see MINOR-4 | **REPRODUCED**, with a precision finding |
| 12 | mutation table 32 / 32, HOLES = 0, after rebuilding C13 | `python -m tools.l1s4_mutation_table` re-run **at the merged tree**: **MUTANTS=32 KILLED=32 HOLES=0**, exit 0, every kill by a named failing test, `git status --porcelain` clean afterwards. I read the scoring first: `DID_NOT_RUN = {2,3,4,5}` is scored for nothing and reported as `DID NOT RUN`, so the S3 review's MINOR-7 (any non-zero counting as a kill) does not apply here | **REPRODUCED** |
| 13 | `PLANNED_REGISTRATIONS` 83 → 84 is a re-measurement, not a silent edit | read the diff: `tests/test_parser_parity.py:207-222` carries a nine-line note giving the rule, the reason it was missed and the three pins that move together; the assertion is `PLANNED_REGISTRATIONS >= len(registrations)` (a FLOOR, `:381`), and the projection at `:392`. Conformance 84 and registry entries 84 moved in the same branch. Marked slice green at 84 at the merged tree | **REPRODUCED**, with MINOR-5 |
| 14 | no version constant bumped | `ANALYSIS_STAGE_VERSION` 16, `OCR_STAGE_VERSION` 4 (`webapp/artifact_cache.py`, not in the diff), `TELEMETRY_VERSION` 1 (`telemetry/record.py:51`, unchanged). Correct per the card; the bump is named for Ocean | **REPRODUCED** |
| 15 | register truthful, nothing re-declared | set-difference of `"tools/*.py"` keys between `train9:corpus_gate.py` and `HEAD:corpus_gate.py`: **exactly one addition** (`tools/l1s4_document_replay.py`), **0 removals**, 27 → 28. `git show train9:corpus_gate.py \| grep -c 'tools/l1s4'` = **0** | **REPRODUCED**, with MINOR-1 on two docstrings |
| 16 | W3 append arithmetic, prefix byte-identical | byte-exact: base 3,878,079 B, tip 3,922,375 B, **`theirs.startswith(base)` True**, appended **44,296 B / 734 lines**; `train9`'s W3 is byte-identical to the base's, so `train_merge_one` rebuilds `ours + section` byte-exact | **REPRODUCED**, with MINOR-9 |
| 17 | the run of record's own ladder | folded `rows.csv` by content sha myself: **3,380 unique shas — validated 2,596 / failed 698 / withheld 55 / review 18 / deferred 13**, and `all_shas.txt` is 3,380 lines | **REPRODUCED** |
| 18 | both logs carry every terminator | `base.log`: 11 terminators, `SEAM_BASE_EXIT=0`, `REPLAY_GROUP_BASE_EXIT=0`, `REPLAY_ALL_BASE_{0..3}_EXIT=0`, `SWEEP_BASE_{0..3}_EXIT=1` (findings present, by the sweep's own convention), `EXIT=0`. `tip.log`: 28 terminators, all present, `SEAM_COMPARE_EXIT=2` and `SWEEP_TIP_*_EXIT=1` by design, and **`MUTATION_TABLE_EXIT=1` / `CORPUS_SLICE_EXIT=1` at `b91f348`** — the two closure findings the W3 reports, both re-run green at `c4b451c` (`mutation_final.log` `MUTATION_EXIT=0`; `rerun.log` `31 passed`, `CORPUS2_EXIT=0`) and both re-run green by me at the merged tree | **REPRODUCED** — the two non-zero tip-run stages are disclosed in the W3 and are the findings it reports, not hidden failures |

---

## 2. The eight documents — the validator's own evidence, re-derived

Re-derived by this reviewer at the merged tree through the production document seam, not read from
the cell's report. Every account below: `validated / approved` · `reconcile.ok=True` · `adb.ok=True` ·
basis `calendar_day_printed_period` · policy `canonical_v1` · `posting_dates_cover_source=True` ·
**no failed ADB check of any kind** · `integrity_flags=[]` · `currency='USD'` ·
`currency_source='schema_default'` · `bank=None` · `account_number=null` · opening, closing, period
start and period end all set.

| document | shape | published accts | sections printed | omitted (class) | transfers | boundary | rollup rows / roles / cross-total | doc outcome |
|---|---|---:|---:|---|---:|---|---|---|
| `333E226A75FE5441` | ACCOUNT + block | 1 | 2 | `printed_pair_coincides_and_no_row_printed` | 0 | `rollup-oracle` | 2 / printed / printed | validated/approved |
| `472A0966A5204513` | ACCOUNT + block | 1 | 2 | `printed_pair_coincides_and_no_row_printed` | 0 | `rollup-oracle` | 2 / printed / printed | validated/approved |
| `596804AA1ACD01EB` | ACCOUNT + block | 1 | 2 | `printed_pair_coincides_and_no_row_printed` | 0 | `rollup-oracle` | 2 / printed / **not printed** | validated/approved |
| `7C7956EB5E93DB1D` | DOCUMENT | **3** | 3 | — | **27** | `rollup-oracle` | 3 / printed / printed | validated/approved |
| `C3D3E48F1E14AE2A` | ACCOUNT + block | 1 | 2 | `printed_pair_coincides_and_no_row_printed` | 0 | `rollup-oracle` | 2 / printed / printed | validated/approved |
| `E38FA786106F752E` | DOCUMENT | **3** | 3 | — | **7** | `rollup-oracle` | 3 / printed / printed | validated/approved |
| `F5BC9FB6D084559E` | ACCOUNT + block | 1 | 2 | `printed_pair_coincides_and_no_row_printed` | 0 | `rollup-oracle` | 2 / printed / printed | validated/approved |
| `FFAC0A88768A8A59` | ACCOUNT + block | 1 | 2 | `printed_pair_coincides_and_no_row_printed` | 0 | `rollup-oracle` | 2 / printed / printed | validated/approved |

**The account arithmetic reconciles independently.** 18 printed sections (2+2+2+3+2+3+2+2), 12
published (1+1+1+3+1+3+1+1), 6 omitted — one per Q3 document, none on the two multi-account ones.
The cell's "twelve accounts across eight documents" is correct, and the per-document counts above
are mine.

### L1-C8, pressed on directly

The card told me to verify the section's own printed counts / totals are FED and **not `None`**.
They ARE `None` on all twelve — and that is correct rather than a skipped check, because **0 of the
12 published sections prints any counts or totals**. Measured with the reader's own
`_COUNTS_ROW_RE` over every located section of all eight documents: `PUBLISHED SECTIONS=12`,
`PUBLISHED SECTIONS PRINTING COUNTS/TOTALS=0`. The design's wording is "the section's own printed
counts and totals **where it prints them** — never `None` where they are printed" (§4, L1-C8), so
nothing is withheld from `reconcile`. The same run shows **0 of the 12 prints a daily-balance
table**, which makes L1-C9's "daily balances supplied where printed" vacuous here too (and see
MINOR-3: that is not recorded anywhere).

What stands in for the coverage check is stronger, and I verified it is applied to **every**
published section and refuses: `analysis/member_statement.py:686-708` compares the table's
deposits and withdrawals columns against the ledger **column by column and to the cent**
(`> _CENT` → `return None`); `:558` refuses unless the section's printed dated-line count equals
the rows read (measured: `rows_read == printed_dated_lines` on all 12, e.g. 155/155, 211/211);
`:539-541` refuses any row whose printed running balance does not follow; `:560` refuses unless the
walk lands on the printed closing. `reconcile`'s coverage tolerance is two per cent; this is a cent.

### The Q3 documents' omitted sections, from the paper

For all six omitted sections, measured directly from the cold-cache text with the reader's own
readers: **printed dated lines = 0**, `prints_counts_or_totals = False`,
`prints_daily_balance_table = False`, **opening coincides with closing to the cent = True**. That
is conditions 3, 4, 5 and 6 read off the paper by me; conditions 1, 2 and 7 are the probe's, and
the probe and the production class agree 6/6 with 0 disagreements under 30 mutant applications.
The roll-up witness does the arithmetic in every case (`rollup.column_roles_printed = True`,
`caption_class = 'type_prev_dep_wd_end'`), and the class binds by BOTH printed handles with
`locators_agree` required (`analysis/sibling_omission.py:231-268`) — the Q3PROBE review's MINOR-3
and MINOR-4 answered in code, and killed by mutants `Q3C7b`, `Q3C7c`, `Q3C7d`.

### Transfers, on the two multi-account documents

I re-derived the designation myself rather than trusting the flag: for all **34** flagged pairs on
`7C7956EB5E93DB1D` (27) and `E38FA786106F752E` (7) —

* **34 / 34 carry a printed INTERNAL designation on at least one leg**
  (`prints_internal_transfer_designation`, `_INTERNAL_TRANSFER_CREDIT_PATTERNS` alone);
* **0 flagged on the peer-to-peer vocabulary alone**;
* **34 / 34** published `basis` strings reproduce from the two legs;
* every pair is same posting date, opposite sign, equal to the cent, and **cross-account**;
* every leg resolves into an account this payload publishes and a posting that account's own
  ledger holds, and **no posting is a leg of two transfers** (one-to-one, checked by me over both
  documents);
* both legs remain in their ledgers — the ledger lengths above (1 / 30 / 211 and 7 / 8 / 32) are
  the full published ledgers, and every account reconciles and carries a clean ADB with them in.

**No document-level ADB key exists on any of the eight**, checked by a DEEP sweep of the whole
block at every depth for `average_daily_balance` / `adb` / `daily_balance` / `average_balance`:
`document_level_adb_keys=none` on all 8.

---

## 3. The sampled leaf walk (5 carriers + 4 published)

Sample: `037774298FE1CD66`, `0A14AC169DEA62D4`, `59DA140E7579A851`, `9C5B7D628D7511EE`,
**`F748A799FDC7F25E`** (the pinned dakota_west carrier) + `333E226A75FE5441`, `472A0966A5204513`,
**`7C7956EB5E93DB1D`** (three accounts) and `E38FA786106F752E` (three accounts). Every leaf of the
`document` block walked against the paper in the cold cache.

| leaf | walked against | result |
|---|---|---|
| `account_count` | the number of accounts the payload publishes | **9 / 9 equal** (1,1,1,1,1,1,1,3,3) |
| `account_count` vs the paper | published + omitted = the enumerated rows | **8 / 8** on this card's documents (1+1=2, 3+0=3, …) |
| `period_start` / `period_end` | **every** account's own `statement.period_start` / `_end`, and the paper's own printed statement-dates line | **equal on every account of all 8**, and the line is printed on all 8. `null` on all 5 carriers — correct: no reader established a document period for them |
| `boundary_mechanism` | the mechanism the reader partitioned by | `rollup-oracle` on all 8; **`None` on all 5 carriers** |
| `rollup.caption_class` | the caption the paper prints | `type_prev_dep_wd_end` on 8 / 8, and it is the caption my own read of the paper found |
| `rollup.column_roles_printed` | L1-C5 | `True` on 8 / 8 |
| `rollup.rows` | the enumerated rows I counted from the paper | 2,2,2,3,2,3,2,2 — **8 / 8 equal** |
| `rollup.cross_account_total_printed` | whether the paper prints one | `True` on 7, **`False` on `596804AA1ACD01EB`** — and my own read of that paper finds none. The oracle is applied where the paper prints one and is not required otherwise |
| `rollup` | on a carrier | `null` on 5 / 5 — those papers print no enumerating table |
| `omitted_sections[].reason` | L1-C17's vocabulary | every one ratified: `printed_pair_coincides_and_no_row_printed` ×6 (this card), `printed_zero_activity_summary`, `printed_dormancy_declaration`, `yield_only_arithmetic_with_summary_equality` (carriers) |
| `omitted_sections[].posting_count` | the omitted section's printed dated rows | **0** on all six Q3 omissions, and I measured **0 printed dated lines** in each of those sections |
| `omitted_sections[].label` | the section's printed ROLE, never a number | set on every one; `account_number` is `null` on every published account |
| `internal_transfers` | see §2 | 34 / 34 resolve, one-to-one, designated; **empty list (not an absent key)** on all 5 carriers and all 6 Q3 documents |
| `integrity_notes` | the closed document-scope vocabulary | **empty list on all 9**; no archive document reaches `ambiguous_internal_transfer` |
| the ACCOUNT block | the run of record's own cached payload | **byte-identical on 5 / 5 carriers, 0 leaves added, 0 removed** — including the pinned `F748A799FDC7F25E`. The 4 published documents have no cached baseline, correctly: they were `failed` in the run of record |

**The added key is the only change.** On the carriers the whole payload is today's payload plus
one top-level `document` key; `is_document_payload` still answers False
(`analysis/payload_shape.py:126-129` keys on `accounts` alone), `statement` stays at the top level,
and L1-C16 is untouched.

---

## 4. Rulings checklist

| ruling | check | line reference | verdict |
|---|---|---|---|
| **Q1** — document outcome may reflect the weaker account without invalidating the passed one | `telemetry/record.py:525-532`: `weakest = min(per, …)`; a ratified omission does **not** lower a document whose weakest account is `validated`; per-account outcomes are published unchanged beside it. The only two `failed` overrides are `document_publishes_no_account` (`:502`) and `document_omission_unratified` (`:491`, `:521`) | `telemetry/record.py:491,502,521,525-532` | **PASS** |
| **Q1** — package membership on OWN `validated` (the gating line) | `webapp/app.py:814` — `if outcome != "validated": excluded.append(…); continue`, inside `_package_members`'s document-shape branch, with the excluded set RETURNED not dropped | `webapp/app.py:735, 814` | **PASS on the document path**; see **MINOR-7** for the single-account path at `:767` |
| **Q2** — printed designation on at least one leg | `analysis/pipeline.py:1286` `if not any(designations): continue`, designation read by `analysis/transaction_classifier.py:548-586` from `_INTERNAL_TRANSFER_CREDIT_PATTERNS` alone. Measured: 34 / 34 archive-published pairs designated, 4 / 47 candidates refused | `analysis/pipeline.py:1286`, `analysis/transaction_classifier.py:585` | **PASS** |
| **Q2** — P2P vocabulary REFUSED | grep of the whole tree: `_TRANSFER_PATTERNS` has exactly **one** use outside its own definition and the docstring that refuses it — `analysis/transaction_classifier.py:1017`, the pre-existing `strong_non_lender_exclusion`. It appears **nowhere** in the transfer path. Killed by mutant `Rd4b` (3 named tests) | `analysis/transaction_classifier.py:300, 1017` | **PASS** |
| **Q2** — counterparts on the SAME document only | `analysis/pipeline.py:1268` builds `postings` from `accounts` of one `DocumentReport`; nothing crosses a document. `admissible` requires `left[0] != right[0]` (a sibling ACCOUNT) | `analysis/pipeline.py:1268-1281` | **PASS** |
| **Q2** — ambiguity refuses the AGGREGATION, never the account | `analysis/pipeline.py:1294-1300` returns `([], [AMBIGUOUS_INTERNAL_TRANSFER])`; `webapp/app.py:781, 793-806` excludes the members with reason `document_transfer_pairing_ambiguous` and touches no outcome, ledger or ADB. Killed by `Rd2` and `PK2` | `analysis/pipeline.py:280, 1294`, `webapp/app.py:781` | **PASS** |
| **Q5** — no blended ADB anywhere (key-name sweep) | repo-wide grep for `package_average_daily_balance` / `document_average_daily_balance` / `combined_adb` / `document_adb` across `analysis/`, `telemetry/`, `webapp/`, `corpus_gate.py`: the only hits are the package figure that Q5 refuses and the gate comment about it. `DocumentReport` carries no ADB field. Deep sweep of the published block on all 8: **no ADB key at any depth** | `corpus_gate.py:1502-1512`, `webapp/app.py:1556` | **PASS** |
| **Q5** — `cross_account_averages_refused` on the five figures | `_PER_PERIOD_AVERAGE_KEYS` is exactly five (`webapp/app.py:509-515`); the member-set check is keyed on the shared document identity (`:1518-1527`); `package_average_daily_balance = None` (`:1556`); the flag and its reason are published only when the refusal fires (`:1692-1699`); the five are nulled at `:1753`. Killed by `PK2` / `PK3` and the L1-S3 tests | `webapp/app.py:509, 1518, 1556, 1692, 1753` | **PASS** |
| **Q7** — two dated rows, unchanged through S4 | the branch touches **no** file carrying the rule: `analysis/community_section.py`, `analysis/symitar.py`, `analysis/zions.py`, `analysis/consumers.py`, `analysis/dakota_west.py` are all absent from `git diff --name-only eeaf566..HEAD`; the three existing evidence classes in `analysis/sibling_omission.py` are untouched (the diff adds a fourth and nothing else) | `git diff --name-only eeaf566..HEAD` | **PASS** (see OBS-2) |
| **Q3** — all seven conditions, fail-closed | `analysis/sibling_omission.py:231-268`: `opening`/`closing` `None` → refuse; `> CENT` → refuse; `dated_row_count is None or != 0` → refuse; `prints_counts_or_totals is None or True` → refuse; `prints_daily_balance_table is None or True` → refuse; `rollup is None or not printed` → refuse; `not column_roles_printed` → refuse; not both handles → refuse; `not locators_agree` → refuse; `closing is None` → refuse; then `<= CENT`. **Nine mutants (Q3C1…Q3C7d) all killed.** The class is unreachable for every older reader — all four new arguments default to absent and each refuses (`:501` test) | `analysis/sibling_omission.py:102, 231-268, 330-344` | **PASS** |
| **Q9** — three figures reported every time | W3 §L1S4's first table gives strict 0 / production 2 / Q3-eligible 6 / target 8 / **newly validated 8**; `N = 6` reproduced by me from the composed probe at the merged tree | W3 §L1S4 | **PASS** |
| **Q10** — no demotion; the S2 pins and the S3 tripwire green at the tip | run at the **merged** tree (stronger than the tip): `tests/test_l1s2_document_outcome.py` (the tripwire), `tests/test_l1s2_omission_ruling.py`, `tests/test_l1s2_protected_carriers.py`, `tests/test_l1s3_*` and both L1-S4 files — **302 passed, 11 deselected, exit 0**; and the corpus-marked slice, which is where `test_the_fifteen_carriers_surface_their_omission_and_stay_validated` actually runs — **31 passed, exit 0**. That test asserts, for all fifteen: an omission recorded, every reason ratified, the ACCOUNT outcome `validated`, the DOCUMENT outcome `validated` through the declared fold, and the account block leaf-identical to the run of record | `tests/test_l1s2_protected_carriers.py:110-187` | **PASS** |
| **Q4 / Q6** — refused as unruled, refusal costed | `analysis/member_statement.py:638-642` refuses a document naming two currency codes outright (mutant `C13`, killed). W3 records the refusal count in this population as **0** and the measured class (4 documents / 12 sections) as another census group's. I confirmed none of the eight prints a currency code: all twelve publish `currency_source='schema_default'` | `analysis/member_statement.py:638` | **PASS** |
| the card's Git ownership — no version constant | `ANALYSIS_STAGE_VERSION` 16 / `OCR_STAGE_VERSION` 4 / `TELEMETRY_VERSION` 1, all unchanged | — | **PASS** |

### The gate's new `_assert_document_facts` — does it bite?

I read it (`corpus_gate.py:1505-1600`) and then doctored a payload one property at a time against
a control that must pass. **BITE: 13 / 13.**

| doctored payload | result |
|---|---|
| CONTROL — a well-formed two-account block | **PASS** (does not raise) |
| a document-level `average_daily_balance` | raises `no_document_level_adb` |
| a document-level `members_daily_balance_mean` | raises `no_document_level_adb` |
| a document-level `blended_average_balance` | raises `no_document_level_adb` |
| an omission naming an unratified reason | raises `omission_reason_not_ratified` |
| a transfer leg naming an account out of range | raises `internal_transfer_account_out_of_range` |
| a transfer leg naming a posting out of range | raises `internal_transfer_posting_out_of_range` |
| one posting a leg of two transfers | raises `internal_transfer_pairing_not_one_to_one` |
| a malformed transfer record | raises `internal_transfer_record_malformed` |
| an account missing the canonical ADB basis stamp | raises `adb_stamps_missing_on_an_account` |
| an account missing the canonical ADB policy stamp | raises `adb_stamps_missing_on_an_account` |
| LIMIT — `combined_balance_mean` (no stem in `_ADB_WORDS`) | does **not** raise |
| LIMIT — a nested `rollup.average_daily_balance` | does **not** raise |

The eleven properties it claims all bite. The two limits are measured, not assumed, and are
**MINOR-8**.

---

## 5. The proof repairs

**The C13 differential fixture is genuine.** I read `6fbf772`'s diff. The old fixture edited two
ENUMERATING ROWS by string replace, one of them the idle section's — which carries the printed
LABEL the Q3 witness binds by, so the document was refused for an unadmitted omission whether or
not the denomination guard existed. The rebuilt test
(`tests/test_l1s4_publisher.py:392-418`) builds two pages from the generator differing by **exactly
one printed line**, placed inside the POSTING section's ledger region so no label binding moves,
**and asserts the single-code page is publishable as the control**
(`assert parse_member_statement(one) is not None`) before asserting the two-code page is refused.
The refusal is attributable to the second code and to nothing else. Mutant `C13` is killed by name
in my own run of the table at the merged tree.

**`PLANNED_REGISTRATIONS` is a re-measurement, not a silent edit.** The diff is nine lines of note
plus the constant. The assertion it guards is `PLANNED_REGISTRATIONS >= len(registrations)` — a
FLOOR that exists so the cost projection can never scale DOWN — so raising it at a larger registry
is what the constant's own rule requires. The note records the rule, why the miss survived (the
pin sits behind `-m corpus`, which the default suite deselects), and that the three pins move
together. See **MINOR-5** for the one thing in it I could not verify.

**The `floor.sh` shared-log terminator bug**: the tip run's log carries every stage terminator
(`GUARDS_EXIT` … `CORPUS_SLICE_EXIT`, then `FLOOR_EXIT`), including the two non-zero ones. Nothing
is masked.

---

## 6. The merged tree — decisive

`train9` `f068b35` + `wave9-l1s4` `e8f0ab4` = `5ec8a1a`, **merged with 0 conflicts**. Every proof
below run by me in that worktree, one harness at a time on this host.

| proof | result | exit |
|---|---|---:|
| canonical guards (5 files) | **255 passed** | 0 |
| canonical conformance (7 files) | **1,282 passed**, 41 skipped | 0 |
| the S2 pins + the S3 tripwire + every L1 file (12 files) | **302 passed**, 11 deselected | 0 |
| `tools/l1s3_surface_census.py` | no unexcused surface | 0 |
| `tools/l1_design_reader_probe --census` | the seam census holds — including the line pin re-measured at the **merged** line numbers | 0 |
| `node --check webapp/static/app.js` | parses | 0 |
| the FULL default suite | **7,815 passed, 44 skipped, 35 deselected** | 0 |
| **`python corpus_gate.py`** | **GREEN** — 109 pinned PDFs (103 native, 6 committed OCR), 0 exclusions · **105 PASS / 3 WITHHELD / 1 REFUSED** · verdicts **1 refused / 3 review / 102 validated / 3 withheld** · ADB doctrine **108/108** canonical · currency **108/108** (14 CAD / 94 USD) · currency_source **108/108** · oracle independence held · runtime 515.9 s | 0 |
| the corpus-marked slice | **31 passed, 7,863 deselected** — this is where the fifteen-carrier pin runs | 0 |
| `tools.l1s4_mutation_table` | **32 mutants · 32 killed · HOLES = 0**; tree clean afterwards | 0 |
| `tools.l1s4_marker_sweep` | 3,351 read · 8 claimed · 8 published · 0 refused · 0 not-`failed` | 0 |
| `tools.l1s4_q3_oracle` | 6 / 6 · 30 / 30 · **0 disagreements** | 0 |
| `tools.l1s4_transfer_killers` | 7 · 47 · 43 · 4 · ambiguous fixture refused · agrees with the design | 0 |
| `tools.q3_corroboration_probe` (composed, unchanged) | **N = 6** | 0 |
| `tools.l1s2_admission_probe` | 117 read · 15 carriers · 19 sections · **15/15 account blocks byte-identical** · 0 no longer published | 0 |
| `tools.l1s4_document_replay --leaves` | 8 replayed · **8 newly validated · 0 regressions** · 8 carry the block · 13 leaves each | 0 |
| **spot replay, 40 documents of my own choosing** (the 8 + 10 carriers + 22 validated documents picked deterministically across the archive) | population 40 · replayed 40 · **newly validated 8 · previously validated preserved 32 / 32 · payload identical 32 · payload changed 0 · validated regressions 0** | 0 |
| that spot replay vs the cell's stored TIP rows | **0 of 40 rows differ** (ignoring `ms`) — the stored tip results reproduce, and the merge changed nothing | — |

Every number the cell claimed for the floor reproduces exactly at the merged tree.

---

## 7. Findings

All MINOR. None changes a payload, a verdict or a count.

**MINOR-1 — two committed instruments claim a register entry they do not hold, and one misdescribes
what it calls.** `tools/l1s4_marker_sweep.py:17-19` and `tools/l1s4_transfer_killers.py:30-32` both
say *"Registered in `corpus_gate.py`'s caller register"*. `corpus_gate.py` registers **only**
`tools/l1s4_document_replay.py` (measured: one `tools/l1s4` key). The marker sweep's sentence goes
further and says it *"reaches the analysis through the DOCUMENT entry point"*; it calls
`analysis.member_statement.parse_member_statement` directly (`:50`, `:69`) and reaches no analysis
entry point at all. W3 §L1S4 states the correct fact — that both are deliberately absent from both
lists — so the code and the record disagree. A stale declaration is what
`tests/test_corpus_gate_outcomes.py` refuses in the other direction, and these are the same defect
pointing the other way. **Fix: reword both docstrings. No behaviour change.**

**MINOR-2 — a comment describing a seam this branch removed.** `analysis/pipeline.py:781` still
reads *"Re-entrant: `analyze_document` opens the same collection around this call, so there is one
collection per document."* Commit `6f031d4` removed exactly that collector from `analyze_document`,
and the same branch's `analyze_document` docstring now explains the asymmetry deliberately.
`collecting()` remains re-entrant by its own construction (`analysis/multi_account.py`), so the
claim is true and its stated reason is not.

**MINOR-3 — L1-C9 and L1-C12 have no mutant, no implementation and no recorded reason.** The
design's S4 proof plan asks for *"mutation tables for L1-C1…C13"*. The delivered table covers C1,
C2, C3, C5, C6, C7, C8, C10, C13 (+ C17, + C11 as R-d's five, + the package's three) — 32 mutants,
all killed. **L1-C9 and L1-C12 appear nowhere**: not in `analysis/member_statement.py`, not in the
table, not in W3 §L1S4. C9 is vacuous on this population and I measured that it is (0 of 12
published sections prints a daily-balance table), but the record does not say so. C12 — *"a facility
enumerated on the table is never published as a deposit section"* — is a live generalization
hazard: the reader holds it closed only as a side effect of L1-C1's `set(identities) ==
set(row_identities)` (`analysis/member_statement.py:661`), which refuses a document whose table
enumerates a row with no matching section; a template printing a loan section with this template's
own furniture would be published as a deposit account. The design measures 19 documents enumerating
a facility, 4 of them multi-posting, all one family. **Fix: a paragraph in W3 naming C9 as
vacuous-and-measured and C12 as CARRIED with that measurement** (it is out of scope under the
freeze; it should not be silent).

**MINOR-4 — "exactly two shapes" is two leaf COUNTS, not two shapes, and the counts are of
collapsed paths.** W3 §L1S4 says the leaf enumeration found *"exactly two shapes"*: 15 × 10 and
8 × 13. Measured: there are **three** distinct leaf-path SETS — the carriers, the six Q3 documents
and the two multi-account documents — which happen to fall into two cardinalities (the Q3 set and
the multi-account set are both 13 and share only 9 members). And the 10 / 13 are **index-collapsed**
paths (`omitted_sections[*].reason`); under an indexed reading the four two-omission carriers carry
13, which I measured on `59DA140E7579A851`. The instrument is right; the prose over-reads it.

**MINOR-5 — a cross-reference to a reading that is not in the record.**
`tests/test_parser_parity.py:218-221` licenses the `PLANNED_REGISTRATIONS` raise on the ground that
*"the sweep was re-timed at this size through the same seam, best of `SWEEP_SAMPLES`, and the
reading is recorded in W3 §L1S4's proof floor."* W3 §L1S4's proof floor carries no timing reading
(grep for `SWEEP_SAMPLES`, `re-timed`, `ms per`: 0 hits in the section). The raise is sound on its
own terms — the assertion is a floor and the marked slice is green at 84 at the merged tree — but a
note that points at absent evidence is the shape of defect this branch otherwise hunts.

**MINOR-6 — the entry's own privacy figures stop two commits short of the branch.** W3 §L1S4
reports the branch scan over **5,318 added lines** and the message scan over **19 commits**, and
says both were re-run after the entry was committed. The branch is **21 commits** and **5,326 added
lines** (`git diff --numstat eeaf566..HEAD`); `0b142bd` and `e8f0ab4` edited the entry after the
last recorded scan, and the scratchpad carries no scan after them. The figure is a fixed point and
the entry says so — but the stated numbers are then not the branch's. I re-ran both scans myself
over the whole branch **including my own review commit**: see the line at the end of this section.

**MINOR-7 — Q1's account-based membership is implemented on the document-shape path only
(pre-existing, disclosed, carried).** `webapp/app.py:767` admits a job publishing today's payload as
a member with no consultation of its own outcome —
`members.append((job, analysis, None, 1)); continue` — while the `outcome != "validated"` gate sits
at `:814` inside the document-shape branch. The line is **unchanged from the base**, so this is not
a regression and not something this cell introduced, and W3 §L1S4 names the decision and prices it
("Reading the ruling literally onto the single-account path would exclude every non-validated
single-account job from every package this platform produces — a large behaviour change on a
surface the run of record does not cover… Named, not widened"). Q1 as ruled carries no shape
qualifier. Under the scope freeze this is correctly out of scope; it should go to
`BATCH9_BACKLOG.md` with a ruling rather than resting on a W3 paragraph.

**MINOR-8 — the gate's document-ADB sweep is narrower than its docstring.** `corpus_gate.py:1502`
`_ADB_WORDS` is four stems, matched against **top-level key names of the block only**. Measured
(§4): `combined_balance_mean` and a nested `rollup.average_daily_balance` both pass. The block's
shape is written by one function (`analysis/serialization.py::_document_block`) so nothing can
arrive there today, and the assertion is still far better than a single-field check — but the
docstring's *"asserted as a property of the document BLOCK's key names"* reads wider than what runs.

**MINOR-9 — the W3 section does not begin on its first appended line.** The appended bytes start
`\n\n# §L1S4 —`, so the heading is the third appended line. BATCH9-RULES asks for the heading *"on
the first appended line"*. `tools/train_merge_one.py` checks a byte prefix
(`theirs.startswith(base)`), which holds, and train9's W3 is byte-identical to the base's, so the
rebuild is byte-exact and the composition is unaffected. Cosmetic; noted because prior sections in
the same log use 0 or 1 blank lines and this one uses 2.

### Observations (not findings)

**OBS-1 — the archive-wide instruments are ACCOUNT-surface, and that is disclosed but worth
restating.** `tools/cohort_replay.py` and `tools/regfp_zero_movement_sweep.py` both call
`analyze_markdown` → `report_to_dict`, so **neither can see the added `document` key**; the
2,596-preserved figure is measured on that surface. Production is the DOCUMENT surface
(`discovery/runner.py:503` + `:713`, `webapp/worker.py:36`, `webapp/artifact_cache.py:215`). The
document surface is covered instead by four measurements — the seam probe over 232 documents / 80
registrations, the admission probe over the 117 validated documents of the five omission-publishing
registrations, the leaf replay over all 23 documents that carry the block, and
`tests/test_l1s2_protected_carriers.py` in the corpus slice — and for a single-account document with
no block the two surfaces are the same object by construction
(`analysis/serialization.py:277-283`). The claim "23 documents and no others gain the key" then
rests on a code argument I checked: `_document_block` returns `None` unless a reader established a
document fact, and the only `publish_omissions` call sites are `analysis/community_section.py`
(×3), `analysis/symitar.py` and `analysis/member_statement.py`, with one `publish_partition`
caller. The argument holds. No instrument sweeps the document surface over all 3,380, and that is
the one thing in this card's evidence that is an argument rather than a measurement.

**OBS-2 — one published account has a ONE-row ledger** (`7C7956EB5E93DB1D`, account 1). Under Q7's
two-row threshold that section does not "post", and design L1-C4 would then PERMIT dropping it; the
reader publishes it instead, which is the stricter choice, and it reconciles and carries a clean
canonical ADB on its own. Named so a later stage does not read it as a Q7 breach.

**OBS-3 — `classify_document` gained a new raise path.** The L1-C17 pre-check
(`telemetry/record.py:485-491`) calls `payload_document_block`, which calls `assert_payload_shape`,
for any Mapping carrying a `document` key. A payload carrying `document` but neither `statement`
nor `accounts` would now raise `PayloadShapeError` out of the fold where it previously reached
`classify_outcome`. Unreachable from anything this platform publishes, and raising is the
fail-closed direction; noted because the module's own comment two functions down says an outcome
function that raises inside a run kills the record.

### The scans, re-run by me at the tip over the whole branch

Both run by me at the tip **with this review already committed**, and over the cell's own
population file widened to its full 28-document universe rather than the 23 the entry names — a
stricter scan, not a comparable one.

| scan | population | measured | exit |
|---|---:|---|---:|
| `privacy_scan_branch.py --shas … --base eeaf566 --ref HEAD` | 28 documents · 9,134 printed WORDS / 8,314 MONEY / 1,482 DIGITS / 307 DATES | **hit_count 0** — MONEY 0 · DIGITS 0 · DATES 0 · WORDS 0, over **5,765 added lines**; raw 15, every one discharged by a standing exclusion (14 `words_class`, 1 `round_money`); **residue files 0, residue sites 0** | 0 |
| `huntington_msg_privacy_scan.py --shas … --base eeaf566 --ref HEAD` | the same 28 | **hit_count 0** across all four classes, over **22 commits** (the branch's 21 plus this review) | 0 |

The added-line count is a fixed point — writing this table adds lines — so the quantity that does
not drift is the one the floor actually claims: **the hit count is 0, and 0 does not drift.**

---

## 8. Composition checklist for Ocean

1. **The merge is clean today.** `train9` `f068b35` + `wave9-l1s4` `e8f0ab4` merged with **0
   conflicts**, 30 files. Nothing needed resolving. If train9 advances before you compose, the two
   surfaces to watch are the ones the composition lessons name:
   * **`corpus_gate.py`'s `EXCLUDED_ANALYSIS_CALLERS`** — a shared append surface. This branch adds
     **exactly one** entry at its end (`tools/l1s4_document_replay.py`), removes none, and lifts
     nothing: `git show train9:corpus_gate.py | grep -c 'tools/l1s4'` is **0**. A second cell
     appending there would collide as a non-W3 conflict (`train_merge_one` exit 3);
   * **`docs/moneythumb-replacement/W3_TRACKA_LOG.md`** — byte-prefix append verified
     (`theirs.startswith(base)` True, 44,296 B / 734 lines, and train9's copy is byte-identical to
     the base's), so `train_merge_one` rebuilds it byte-exact.
2. **BUMP `ANALYSIS_STAGE_VERSION` 16 → 17 IN THE COMPOSING COMMIT.** This is the one thing that
   must not be forgotten. The payload shape changes on **21** documents batch 8 already
   published — 15 of them protected carriers — and a warm analysis cache keyed on 16 would serve
   the old-shape payload for them to a new-shape build. The branch correctly bumps nothing
   (`webapp/artifact_cache.py` is not in its diff).
3. **`TELEMETRY_VERSION` stays 1.** The telemetry record's shape does not change; L1-S3 already
   bumped it.
4. **Three registration pins move together, and one of them is behind `-m corpus`.**
   `tests/test_parser_conformance.py` (84, and 84 × 83 negatives),
   `tests/test_parser_registry_entries.py` (84) and `tests/test_parser_parity.py`'s
   `PLANNED_REGISTRATIONS` (84). The third is deselected by the default suite — a green suite does
   not prove it moved.
5. **After composition, the batch-9 close-out per the SCOPE FREEZE**: full proof floor, frozen-corpus
   cold run, `--fail-on-regression` against the batch-8 run of record
   (`discovery_reports/TRAIN8-7185633/…-cda8882d`), remote CI, then freeze the
   deterministic-v1 / multi-account-v1 baseline. The cold run is the first time the DOCUMENT surface
   is measured over all 3,380 (see OBS-1); expect the same eight movers and no others.
6. **Expected cold-run delta**: `2,596 → 2,604`. Eight documents `failed → validated`, twelve
   accounts, zero regressions. The two multi-account documents are the first in this platform's
   history to publish more than one account, so the runner's per-document row carries a document
   fold for the first time on real data (`discovery/runner.py:713`).
7. **The nine MINOR findings** in §7 are all safe to land as-is. MINOR-1, MINOR-2, MINOR-4 and
   MINOR-5 are one-line documentation corrections; MINOR-3 and MINOR-6 want a short W3 amendment;
   MINOR-7 wants a line in `BATCH9_BACKLOG.md` and a ruling; MINOR-8 and MINOR-9 are notes. None of
   them blocks composition and none of them is worth reopening the branch for on its own — fold
   them into the composing commit's message or a follow-up hygiene card as you prefer.
8. **Carried forward, already disclosed by the cell and confirmed by me**: the Q3 class has still
   never been exercised against OCR'd input (all eight documents are `native-pdf-text`, confirmed
   from `clusters.json`: `routes {native: 8}`) — Phase 2's `OCR-LEGACY-AUDIT` must re-measure before
   the class is relied on there; `PINNED_CURRENCY` / `PINNED_CURRENCY_SOURCE` totality per
   `(path, account)` is not built and needs a truth-set ceremony (no pinned document publishes more
   than one account at this tree, so nothing is unguarded today); the three other `None` exits of
   `community_section::_parse_sectioned_statement` and `dakota_west`'s derived section selection are
   untouched, correctly.

---

*Reviewer's own artifacts are in this session's scratchpad (`rev_evidence.py`, `rev_l1c8.py`,
`rev_gate_bite.py`, `rev_measure.sh`, `rev_measure2.sh`, `rev_merged_floor.sh` and their logs); the
throwaway merged worktree was removed after the run. No document text, figure, date, description or
name appears in this file.*
