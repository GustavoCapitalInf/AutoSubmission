# BATCH9 HUNT9 — independent adversarial review of `wave9-huntington`

Reviewer: independent Opus cell. Base `52f1d03`, tip `c963c5c`, worktree
`.claude/worktrees/mt9-huntington`. Run of record
`TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`, cold cache
`.claude/recovery/webapp_data_train8_cold` (read-only). Nothing was asked of the cell;
every number below was re-measured. Private artefacts in the reviewer's scratch; the
review prints classes, counts, booleans and masked shapes only.

## Verdict

**CONFIRMED WITH FINDINGS.** 0 BLOCK · 2 MAJOR · 4 MINOR.

`newly validated = 0` is the correct and defensible outcome for `DECL:huntington`, and the
opportunity should be **retired to 0**. Every headline the cell reports reproduces exactly.
But the RECORD's account of *why* nothing can be done is wrong in two places, and both
corrections matter to Gustavo: the ceiling bounds relaxations, not readings, and a reading
the cell did not test reaches `validated` on three documents — barred by the repair
doctrine, not by the platform. The cell's own carried finding names a platform change that,
measured, would publish nothing at all.

## 1. Re-measurement table

| claim in W3 §HUNT9 | re-measured | agrees |
|---|---|---|
| no production file differs from base | `git diff --stat 52f1d03 c963c5c -- analysis ocr webapp discovery telemetry benchmark corpus_gate.py` → **empty**; whole-branch name-status = W3 + `tests/test_huntington.py` + the two `tools/huntington_*.py` | ✔ |
| instruments unwired | 0 references to either module anywhere outside `tools/` and `docs/`; no `import tools` in any production package; `test_experiments_are_not_wired.py` green | ✔ |
| population 12, gate table 4 L-1 / 8 `_validate` / 0 grammar | probe re-run at the tip: **IDENTITY 8, L1 4**, no other class; the 4 L-1 shas are the 4 named | ✔ |
| per-sha identity failures (3 fee+balances, 3 +section sums, 2 +summary) | reproduces sha-for-sha: `_validate:fee_net,balance_activity` ×3 · `+section_sums` ×3 · `+summary_identity` ×2 | ✔ |
| unitemised non-zero service charge on 8/8 | stated charge non-zero on **8 of 8**; no `Service Charge Detail` / `Service Charge Summary` phrase on any | ✔ |
| no `Balance Activity` on 8/8 | 0 of 8 print either phrase; all 38 validated print `Balance Activity` | ✔ |
| unread-money bound: 2 figures ×6 docs, 4 ×2 docs, 0 in row tails | reproduced, **and independently re-derived by full token accounting** (§3) | ✔ (strengthened) |
| not truncated: footers `1 … N of N` | page sequence complete on **12 of 12** declines; the extra cached sheets are the issuer's boilerplate legal pages | ✔ |
| 11 validated of the same product print both tables | same product as all 8 = `Huntington Unlimited Checking`, **11 validated**, `Balance Activity` 11/11, `Service Charge Detail` 11/11 | ✔ |
| the 8 are two accounts × four statements | **2** distinct account fingerprints, 4 each; the 11 same-product validated are **2 other** accounts, fingerprint overlap **0** | ✔ |
| ceiling `absent_evidence` → 0 validated | re-run: **0 validated**, 12 `failed / parser_declined` | ✔ |
| ceiling `all_identities` → 0 validated (8 withheld_adb, 4 declined) | re-run: **0 validated**, 8 `withheld / withheld_adb`, 4 `failed / parser_declined` | ✔ |
| `cohort_replay --group DECL:huntington --expect-identical` | at the tip: population 12, **newly validated 0**, 12 unchanged non-validated, payload changed 0, regressions 0 — **EXIT=0** | ✔ |
| `cohort_replay --parser huntington --expect-identical` 38/38 | at the tip: **preserved 38 of 38, payload identical 38**, regressions 0 — **EXIT=0** | ✔ |
| canonical guards 255 | **255 passed — EXIT=0** | ✔ |
| canonical conformance 1,270 / 40 skipped | **1,270 passed, 40 skipped — EXIT=0** | ✔ |
| `tests/test_huntington.py` 39 → 40 (+1) | 40 collected at the tip; base file has 36 `def test_`, tip 37 (+1) | ✔ |
| privacy scan: 828 added lines, 50 documents, hit_count 0 | **`hit_count 0`**, `added_lines 828`, `population 50`, `documents_read 50`, `no_cached_text []`, MONEY/DIGITS/DATES/WORDS all 0 — EXIT=0 | ✔ (file lines only — see MINOR-1) |
| archive sweep 0 moved | spot-check `[0,120)`: 120 documents, 91 compared, **91 identical, moved 0**, `no_payload_now_publishes 0`, `payload_now_raises 0` — EXIT=0. Full sweep not re-run: with a byte-empty production diff zero movement is structurally entailed, and the host is shared | ✔ (partial, by design) |
| instruments carry no control byte | 0 on both files and on the test file | ✔ |
| W3 = base + one appended section | base is a **byte-exact prefix** of the tip (3,363,705 → 3,378,865 bytes); `# §` headings 87 → 88; the new one is §HUNT9, last | ✔ |

## 2. The hostile questions, answered

**(1) Is the ceiling instrument honest?** Half yes, and the half that fails is MAJOR-1.
It is honest about what it does: `all_identities` replaces `_validate` with an
unconditional `True` — every identity, gone — the patch is installed on the module global
that `parse_huntington_statement` resolves at call time (so it really takes effect: the 8
move `failed → withheld` under it), the tree on disk is untouched, and it is removed in a
`finally`. It feeds `reconcile` **the same statement the reader would publish**, not an
impoverished one: `parse_huntington_statement` builds the `Statement` normally and only the
verdict is bypassed. That is exactly the limitation. The instrument bounds the space of
**relaxations** — what the platform does with *today's payload*, unchecked. It does not
bound the space of **readings** — what the platform does with a *different* payload. The
record claims the second bound. See MAJOR-1.

**(2) The three "carried finding" documents — is a reconciler tolerance what publishing
needs?** No. Measured, that is the one thing it does not need, and would not get.
See MAJOR-2. And no, there is no printed date or itemisation the reader misses: on all
three the fee's itemisation is absent as a *phrase*, and the token accounting in §3 leaves
no unread figure anywhere on the document.

**(3) Print variant or truncated upload?** Print variant, confirmed on the strongest
available evidence. All 12 declines carry a complete printed page sequence `1 … N of N`
with no gap; the surplus sheets in the cache are the issuer's standard legal-notice pages
(byte-length-identical across different documents). The 8 are the **same product** as 11
validated documents that print BOTH tables; the 8 are two account fingerprints × four
statements and the 11 are two *different* accounts, overlap 0. A truncation story would
have to explain a missing table on eight consecutive statements of two unrelated accounts
while the page numbering closes — it does not survive.

**(4) Archive token in the section or a commit?** The **section** is clean — 0 money
shapes, 0 date shapes, 0 long digit runs, nine sub-sections `HUNT9.1 … HUNT9.9`, and the
added-lines privacy scan is 0 at the tip. The fix is confirmed. A **commit message** is
not. See MINOR-1.

**(5) Does anything in this branch's tools reach production?** No. 0 references from
`analysis`, `ocr`, `webapp`, `discovery`, `telemetry`, `benchmark`, `tests` or
`corpus_gate.py`; no registration; the unwired-experiments guard is green.

## 3. What I confirmed more strongly than the cell (the unread-money bound)

The cell's bound counts money in two places: on a line no block claimed, and inside the
TAIL of a booked row. Two further hiding places exist, and the record does not mention
them:

* money printed on a booked line **before the first row group opens**, or between two
  groups in a position the tail slice does not cover;
* money printed **without cents**, which neither `_FIGURE` nor either of the cell's
  counters can see at all.

I closed both. Full token accounting over each of the 8 — every money-shaped token in the
document, assigned to the summary grid, to a booked row (figure or tail), or to the
off-block residue — **balances exactly on all eight, with residue 0**:

| sha16 | money tokens | summary grid | booked rows | off-block | on-line residue | no-cents money |
|---|---:|---:|---:|---:|---:|---:|
| `0DCABEBAE6D99BE0` | 114 | 10 | 102 | 2 | **0** | **0** |
| `7C351D71B06A3E10` | 99 | 11 | 86 | 2 | **0** | **0** |
| `F14DAFC2118B3058` | 47 | 9 | 36 | 2 | **0** | **0** |
| `4AF6AB4A97E468F3` | 68 | 10 | 54 | 4 | **0** | **0** |
| `5D52C3A69E5A7FA9` | 29 | 9 | 18 | 2 | **0** | **0** |
| `89F586D7BA16DC32` | 70 | 9 | 59 | 2 | **0** | **0** |
| `1EEC7DABB4AB35E0` | 100 | 10 | 86 | 4 | **0** | **0** |
| `F7C683846985F86D` | 100 | 11 | 87 | 2 | **0** | **0** |

Every summary-line money token is matched to a printed label (unmatched 0 on all eight).
The off-block residue is the two service-charge-cycle averages, plus on two documents two
figures inside a fee-schedule sentence on a legal page. **There is no unread section, no
unread continuation, and no unread activity figure on any of the eight.** The claim
"the grammar reads everything these statements print" is correct, and the three routes the
review brief asked about — a running balance printed elsewhere, the missing debits in an
unread section, an unread fee itemisation — are all refuted by this table before any
grammar argument is needed.

## 4. Findings

### MAJOR-1 — the ceiling's stated reach is false; a reading the cell did not test validates three documents

W3 §HUNT9.5 states: *"Not one document reaches `validated` with every oracle removed. **No
change to this reader — no widening, no relaxation, nothing** — can produce a validated
document in this population, because what blocks it is downstream of the parser."*

The opening claim is true and I reproduced it. The one that follows is false, and its
"because" is the wrong diagnosis. Measured, with `_validate` relaxed AND the bank-stated
`Total Service Charges (-)` published as a debit posting dated the LAST DAY OF THE PERIOD —
a change entirely inside the reader, touching no platform file:

| sha16 | outcome | recon.ok | adb_ok | integrity flags | corporate_use |
|---|---|---|---|---|---|
| `0DCABEBAE6D99BE0` | **validated / approved** | True | True | none | approved |
| `7C351D71B06A3E10` | **validated / approved** | True | True | none | approved |
| `F14DAFC2118B3058` | **validated / approved** | True | True | none | approved |
| the other 5 | withheld / withheld_adb | False | False | `ledger_sum_mismatch` (+ `summary_math_inconsistent` ×2, `debit_detail_coverage_mismatch` ×3) | manual_review_required |

**Three of the eight reach `validated`.** They are exactly the three the cell itself
identified as "the only three where every available identity closes". So what blocks them
is NOT downstream of the parser: it is upstream, in the payload the parser chooses to
build, and it is the **repair doctrine** — *a parser never writes an amount* — ratified in
batch 7 with a pinned-document ceremony, and the reason a fee whose DATE the statement
never prints cannot be placed on a day of the reader's choosing without corrupting every
daily balance from that day forward, and the ADB with them.

The card's conclusion survives intact — this widening is barred, and barred by name. The
ceiling *measurement* is sound. What is wrong is the **claim built on it**: the instrument
bounds relaxations of `_validate` over an unchanged payload, and the record promotes that
to a bound over every possible reader change. A future cell reading §HUNT9.5 would
conclude the population is architecturally impossible when it is in fact
doctrine-forbidden, which is a different — and much more useful — fact.

**Required correction (record only, no code):** restate §HUNT9.5 as the bound it is
("no relaxation of the identities can beat this; the one reading that can — writing the
stated fee into the ledger on an unprinted date — is barred by the repair doctrine"), and
record the measurement above so the next cell does not have to rediscover it.

### MAJOR-2 — the carried finding names a mechanism that publishes nothing, and the wrong owner

W3 §HUNT9.7 finding 1 states that publishing the three *"would need `reconcile`'s sum check
to tolerate a ledger short by exactly `stated_service_charge`, which is a platform-level
ruling this card does not own (`analysis/reconcile.py` is outside its ownership)"*.

I granted exactly that tolerance and more — `_validate` fully relaxed AND `recon.ok` and
`recon.summary_ok` both forced True, with **no amount written**:

| sha16 | outcome | adb_ok | integrity flags | corporate_use |
|---|---|---|---|---|
| `0DCABEBAE6D99BE0` | withheld / **withheld_adb** | False | `ledger_sum_mismatch` | approved |
| `7C351D71B06A3E10` | withheld / **withheld_adb** | False | `ledger_sum_mismatch` | approved |
| `F14DAFC2118B3058` | withheld / **withheld_adb** | False | `ledger_sum_mismatch`, `debit_detail_coverage_mismatch` | approved |

**Validated: 0.** The reconciler tolerance the finding asks for is neither sufficient nor
even close: `analysis/adb.py` requires `final_balance_matches_statement_closing` among its
`required` checks, and a ledger short by the fee does not reach the stated closing balance
no matter what `reconcile` says about it. The integrity flag the fee raises survives too.

So the finding, as recorded, invites a ruling on a platform change that would move **zero**
documents, while the change that actually moves three is a parser-level repair-doctrine
exception the record does not name. That is the opposite of the routing it proposes:
`analysis/reconcile.py` is not the owner; the repair doctrine is.

**Required correction (record only, no code):** rewrite carried finding 1 to name the
repair doctrine as the barrier, cite the ADB `final_balance_matches_statement_closing`
requirement, and carry both measured counts — *reconciler tolerance alone: 0 validated,
3 withheld; tolerance plus a written fee: 3 validated*. The cell's instinct is right that
this should be argued against the ADB doctrine before it is argued for coverage; the
argument just has to be aimed at the right doctrine.

### MINOR-1 — the redaction commit restates the shapes it redacts, on a surface no scan reads

Commit `29ab66b` removes two money-shaped sub-section numbers from §HUNT9 — and its own
message quotes both of them verbatim and states that they are figures this issuer's
documents print. Measured against the cold cache over the 50-document population, each of
the two tokens occurs **once, in one document**: the same two hits the cell's first scan
reported. (They are not repeated here.)

The branch privacy scan reads **added file lines** — 828 of them, hit 0 — and cannot see a
commit message. So the branch's own proof floor is structurally blind to this, and the
tokens merge permanently. The amounts are sub-dollar and non-identifying, and the cell's
own judgement ("neither is archive text") is defensible; but the standard it invoked in the
same breath is "a zero, not an adjudication", and by that standard the redaction is
incomplete. Ocean may reword the message at compose time (it is docs-only history) or
accept it explicitly.

**Generalizes beyond this card:** commit messages are an unscanned privacy surface for
every batch-9 cell, and this is the second time a cell has written a redacted shape into
the very commit that redacts it. Worth a standing line in BATCH9-RULES.

### MINOR-2 — `huntington_identity_ceiling.py --group` cannot be repointed

`ap.add_argument("--group", action="append", default=["DECL:huntington"])`: with
`action="append"` and a non-empty default, `--group OTHER` yields
`['DECL:huntington', 'OTHER']`, never `['OTHER']`. Verified. The instrument can be widened
but never aimed elsewhere. `huntington_decline_probe.py` gets this right (empty default,
filled in after parsing) — the ceiling should copy it.

### MINOR-3 — the record's "closure tree" is not the branch tip

§HUNT9.8 attributes both closure replays to `e23107e`; the tip is `c963c5c`, three
docs-only commits later. Immaterial to the result — I re-ran both at the tip and got the
same numbers — but the record should say which tree its exit codes belong to, and it is the
tip that Ocean composes.

### MINOR-4 — the added test cannot distinguish its two causes (noted, not a defect)

`test_the_print_that_itemises_neither_its_fees_nor_its_daily_balances_is_refused` asserts a
refusal on a fixture with `fee_detail=""`, `fee_summary=""` and `balances=""` at once, so it
would pass if only one of the two absences refused. It IS load-bearing — I mutated
`_validate` to an unconditional `True` and the test **fails**, so it kills the mutant a
widening would be — and the one-at-a-time refusals are already pinned by existing tests.
Recorded so nobody later mistakes it for a two-cause guard.

## 5. Explicit answers

| question | answer |
|---|---|
| newly validated 0 confirmed? | **YES.** `cohort_replay --group DECL:huntington --expect-identical` at the tip: population 12, newly validated **0**, other ladder movement 0, 12 unchanged non-validated, payload changed 0, regressions 0, **EXIT=0**. Both ceiling modes independently: **0 validated**. |
| previously validated preserved 38/38 identical? | **YES.** `cohort_replay --parser huntington --expect-identical` at the tip: preserved **38 of 38**, payload identical **38**, payload changed 0, validated regressions 0, **EXIT=0**. |
| no production change? | **YES.** Restricted-path diff **empty**; the branch touches only W3, `tests/test_huntington.py` and two `tools/huntington_*.py`; 0 references to either instrument from any production tree; unwired-experiments guard green. All four files are inside the card's declared ownership. |
| privacy 0? | **YES for the added lines**: `hit_count 0` over **828** added lines against **50** documents, MONEY/DIGITS/DATES/WORDS all 0, `no_cached_text []`, EXIT=0. **NOT for commit messages** — see MINOR-1; that surface is outside every instrument the proof floor runs. |
| should `DECL:huntington` be retired to 0? | **YES** — with the corrected reason on the record. |

## 6. Recommendation to Ocean

Accept the branch. It is a hygiene-shaped closure of a coverage card, and the closure is
correct: twelve honest refusals, no grammar gap, no truncation, no unread money, nothing
preserved-and-broken, an empty production diff. The two MAJORs are **record corrections,
not code**: §HUNT9.5's ceiling claim must be narrowed to the bound the instrument actually
establishes, and carried finding 1 must be re-aimed from `analysis/reconcile.py` to the
repair doctrine with both measured counts attached. Neither changes a single number the
cell reported; both change what a future reader would conclude from them, and one of them
would otherwise put a null proposal in front of Gustavo.

Retire the `DECL:huntington` opportunity to **0**. The three-document residue is real, is
now measured, and is a repair-doctrine question — not a coverage one.

## 7. Sha remap — MINOR-1 was closed by rewording, and rewording moves shas

MINOR-1 asked for a commit MESSAGE change, and a message is part of a commit's identity, so
closing it re-created that commit and every commit after it. `git filter-branch -f
--msg-filter` was run over `52f1d03..` with a filter that rewrites exactly one message and
passes every other through byte-for-byte; **every tree in the range is unchanged** (the
list of tree ids over the range hashes identically before and after, and the tip tree is
the same object).

The shas in this file above have been remapped to the rewritten history so they still
resolve:

| before | after | commit |
|---|---|---|
| `afc18d0` | `29ab66b` | the redaction commit whose message MINOR-1 named |
| `d48293f` | `9535372` | the privacy number recorded at the tip |
| `22d3ea2` | `c963c5c` | the tip this review was measured at |
| `5235f6e` | `1d9fc30` | **this review** |
| `0b742ac` | `40a9a8d` | the review's own one-phrase reword |

The last two are this review's own commits: they were written before the rewrite and now
carry different shas. Nothing in their content changed. Commits at or before `0f0686f`
keep their original shas — their trees, messages and parents are untouched.
