# BATCH9 — independent adversarial review of `wave9-l1s3` (`L1-S3-SURFACES-DARK`)

**Reviewer:** independent Opus cell. **Branch** `wave9-l1s3`, tip `70998a3`, base `train9` `4953806`.
**Composition target at review time:** `train9` `5c32046` (L1-S2 and Q3-CORROBORATION-PROBE composed).
Everything below was re-measured on this host. Nothing was accepted on the cell's word.

---

## VERDICT

# APPROVE WITH FINDINGS — 1 BLOCK · 4 MAJOR · 9 MINOR

The card's central claim is **confirmed**: the nine seams take the document entry point, the readers
are taught, and the stage is **dark and moves nothing**. I reproduced zero movement independently —
seam probe base-vs-tip `MOVED_TOTAL=0` over 232 documents / 80 registrations; a 350-document archive
sweep at **both** trees with all nine counts identical and `l1s3_sweep_attribution` exit 0 (0 tip-only
/ 0 base-only / 0 differing); corpus gate GREEN; full suite; guards; conformance; both censuses;
mutation table 6/6 — and I reproduced every Q10 semantic and every C18 property on constructed
payloads.

**The branch may not be composed as it stands.** BLOCK-1 is a *semantic* composition failure: at the
merged tree eleven of L1-S2's Q10 pins go red, because `classify_document` handed a `DocumentReport`
neither refuses nor answers — it dies with an `AttributeError` two frames down. I proved the fix and
proved it green. That is the only BLOCK.

| | finding | where |
|---|---|---|
| **BLOCK-1** | 11 S2 Q10 pins fail at the merged tree; `classify_document` fails deep instead of refusing at its door | §4 |
| **MAJOR-1** | the census's reverse direction is blind to the document shape's OWN key (`accounts`), to a non-literal `statement` subscript, and to an aliased account publisher — 7 undeclared readers, census exit 0 | §3.1 |
| **MAJOR-2** | `webapp/static/app.js` does not fully refuse: three other consumers of `currentAnalysis` / `modalAnalysis` answer a document payload quietly, one of them the copied credit-memo summary | §3.3 |
| **MAJOR-3** | the package's cross-account arithmetic counts one calendar period twice; design §6.5's fourth bullet — the check that would have caught it — is not implemented | §3.5 |
| **MAJOR-4** | **three of the eight refusals are untested.** A mutant that leaves the refusal in place but never runs it passes the WHOLE default suite and the census, at `adb_forensic_audit::audit_one`, `balance_forensic_audit::audit_source` and `corpus_gate::check_currency_source` — one of them the legacy-indexing path the card promised to pin | §5.7 |
| MINOR-1 | five of §6.5's seven per-account gate assertions are absent at this tip | §5.1 |
| MINOR-2 | `stated_counts.evaluate_accounts` has no caller; the module's own CLI still calls the refusing `evaluate` | §5.2 |
| MINOR-3 | the census's forward check is a NAME check, not a reachability check (mutant M7) | §5.3 |
| MINOR-4 | two refusal messages name the wrong surface | §5.4 |
| MINOR-5 | the privacy row's "raw 0" is wrong — raw was 21 at the cell's scan tree, 28 at the tip | §7.1 |
| MINOR-6 | `refuse_document_payload` / `is_document_payload` return silently on a non-Mapping; L1-C16's third clause is never reached by either outcome function | §4.3 |
| MINOR-7 | the mutation table scores any non-zero pytest exit as a kill (4/5 would count) | §5.5 |
| MINOR-8 | the guard count is reported over nine files; the canonical five reproduce at 255 | §6 |
| MINOR-9 | neither census can see inside `analysis/serialization.py` — both exclude it wholesale | §5.6 |
| COMP | composition map: two text conflicts, one line re-pin, one tripwire to retire | §4.4 |

---

## 1. What I reproduced, claim by claim

| the cell claimed | I measured | verdict |
|---|---|---|
| nine seams at the document entry point; by AST **eight** real calls, the ninth a docstring example | AST census prints exactly the eight, at `adb_forensic_audit.py:492`, `analyze.py:176`, `balance_forensic_audit.py:515`, `batch.py:185`, `benchmark/ourside.py:117`, `corpus_gate.py:1553`, `discovery/runner.py:503`, `webapp/worker.py:36`. `webapp/artifact_cache.py:215` read in place: it is inside that module's docstring | **CONFIRMED** |
| `tools/l1s3_surface_census.py` exit 0 both ways — 20 readers, 13 excused, 31 key-reads swept, 8 seams | exit 0, same four numbers | **CONFIRMED** |
| `tools.l1_design_reader_probe --census` exit 0 at the tip, exit 1 at the base | tip exit 0 (9 found / 0 undeclared / 0 missing); **base exit 1** — 12 found, `corpus_gate.py:1355` missing, four undeclared (three in `analysis/serialization.py`, one at `corpus_gate.py:1444`). Stale since S1, as claimed | **CONFIRMED** |
| a doctored census fails forward, reverse and on the seam half | reverting one seam to the account publisher → AST census exit 1 naming `webapp/worker.py:36`. Inserting one blank line above a seam → design probe exit 1 naming both `analyze.py:176` (missing) and `:177` (undeclared) while the AST census stays 0 | **CONFIRMED** |
| mutation table 6 / 6 killed | 6 / 6, each with **≥1 named FAILED test** (3, 1, 1, 1, 2, 1); M4 also census exit 1; tree clean after every mutant | **CONFIRMED** |
| zero movement at the pipeline seam | ran `tools/l1s1_seam_probe.py` at the tip and at `mt9-l1s3-base`, base capture compared against tip: 232 documents / 80 registrations; **document seam byte-identical 232**, account seam 232, **integrity flags list AND order 232**, ladder outcome unchanged 232, documents publishing exactly one account 232, `MOVED_TOTAL=0` | **CONFIRMED** |
| full suite 7,578 / 43 | **7,578 passed / 43 skipped**, exit 0, 219 s | **CONFIRMED** |
| conformance 1,270 | **1,270 passed / 40 skipped**, exit 0 | **CONFIRMED** |
| guards 349 (nine files) | canonical five (BATCH9-RULES): **255 passed**, exit 0 — the base floor exactly. The cell's 349 is a superset over nine files | CONFIRMED, see MINOR-8 |
| corpus gate GREEN 105 / 3 / 1 | **GREEN**, exit 0 — 105 PASS / 3 WITHHELD / 1 REFUSED; verdicts 1 refused / 3 review / 102 validated / 3 withheld; 108/108 currency; 108/108 currency provenance; 109 resolved offline; 664.8 s | **CONFIRMED** |
| C18 — the discovery row carries the DOCUMENT outcome and no account | on a constructed two-account payload: `account_last4 = None`, serialised to rows.csv as **empty**, `account_count = 2`, `outcome_class` = the **weakest** account's. Single-account row unchanged (`account_count = 1`, last4 present) | **CONFIRMED** |
| Q10 wired as ruled | ratified omission + one validated account → `('validated', 'approved')`; unratified omission → `('failed', 'document_omission_unratified')` and the account published as **excluded**, never as `partial`; today's package carries **no** Q10 key, **no** `account_index`, and unchanged member ids; the ratified-omission package publishes `sibling_account_omission_detected: true` / `completeness: partial` / `omitted_section_count` / `omitted_sections` | **CONFIRMED** |
| the review override NOT wired | `classify_document` wires two of the three overrides; the third is absent and two tests name Q10 | **CONFIRMED** |
| `count_semantics` is not a reader | no payload-key read anywhere in the module; every `statement` occurrence is prose in a docstring | **CONFIRMED** |
| register unchanged; the new tools need no key | `EXCLUDED_ANALYSIS_CALLERS` **byte-identical to the base**; none of the three new `tools/l1s3_*.py` calls `analyze_markdown`, `analyze_document` or `cached_analysis`; `train9` excuses no `l1s3` tool | **CONFIRMED** |
| privacy — messages MONEY / DIGITS / DATES 0, WORDS 2 | reproduced exactly: `hit_count 2`, `{"DATES": 0, "DIGITS": 0, "MONEY": 0, "WORDS": 2}`, the two named commits and the two named bigrams | **CONFIRMED** |
| privacy — added lines 0 / **raw 0** | `hit_count 0`, MONEY / DIGITS / DATES / WORDS all 0, residue files 0, residue sites 0 — but **raw 21** at the cell's own scan tree and **raw 28** at the tip, every one WORDS-class and discharged by the scanner's own `words_class` rule | CONFIRMED except "raw 0" — see MINOR-5 |
| archive sweep, 3,380 at both trees, nine counts identical, 70 findings attributed, 0 tip-only / 0 base-only / 0 differing | re-ran a **bounded slice** (documents 0-350) at both trees: **all nine aggregate counts identical**, and `tools/l1s3_sweep_attribution.py` **exit 0** — 6 findings at both trees identically, **0 differing / 0 tip-only / 0 base-only**. The method reproduces; the full 3,380 does not | **CONFIRMED on a slice** |
| 677-document wide seam probe; the 80-registration replay pair at both trees; the remaining archive sweep; the corpus-marked slice | **NOT re-run** — carried on the cell's evidence plus the equivalence argument in §6 | CARRIED |

---

## 2. The WORDS-2 judgement — DISCHARGED, and not for the cell's reason

The message scan is reproduced exactly: `commits_scanned 14`, population 3,380, `documents_read 3,351`,
**MONEY 0 · DIGITS 0 · DATES 0 · WORDS 2**, exit 1.

I read the scanner's WORDS rule before judging. `privacy_scan_branch.py` builds the WORDS class as
every alphabetic word of `--word-min` (default 4) characters or more **plus every adjacent bigram**
of those words, over both sides. The printed vocabulary it compares against is 416,756 WORDS tokens
across 3,351 documents. A class built from adjacent-pair coincidence over a vocabulary that large
will collide with ordinary English; the class is a screen, not a verdict, which is why BATCH9-RULES
already instructs a cell to report the WORDS count **with an attribution** while MONEY / DIGITS /
DATES must be hard zeros.

Both hits are bigrams, and I read each in its full message:

* `THOUGH THEY` — `661c005`, from *"the package — where a person reads a member's figures **as though
  they** were the member's whole banking — says a section was established and not published"*. A
  subordinate clause about what a package means.
* `NINE LINE` — `7b1250b`, from *"every one of its **nine line**-pinned sites moved to the document
  entry point"*. `nine` is the count of seams the design declares — a number this branch took from a
  design document, not from any statement — and `line` is the first half of `line-pinned`.

Neither is a value, a name, a date, an amount, an identifier, a label, or anything read out of a
document. Neither restates a redaction. The words were supplied by the author for their ordinary
English meaning and the pairing is coincidence with some statement's prose.

**Judgement: dischargeable. No history rewrite is required.**

One correction to the record. The W3 section justifies keeping the messages on the ground that *"a
reword would invalidate those citations to hide two common English words"*. That is not a good
reason — BATCH9-RULES says explicitly that on an unpushed branch a `--msg-filter` reword is cheap and
the sha references are remapped in the records. The correct reason, and the one I am recording, is
that **the two hits are not tokens**: had they been, the cost of the reword would have been
irrelevant.

---

## 3. The attacks

### 3.1 Attack 1 — MAJOR-1: the reverse census is blind to the key this stage introduced

The census's reverse direction is its only quantifier: the forward half checks *declared* readers,
so nothing but the reverse half makes "every reader is taught" falsifiable. Its predicate
(`_reads_statement_key`) matches exactly three shapes — a `Subscript` whose slice is the **constant**
`"statement"`, and `.get` / `.setdefault` / `.pop` whose **first positional argument** is that
constant.

I wrote a scratch module of seven readers at the repository root — a swept production path — each one
answering about ONE account, none declared and none excused:

| reader | how it reaches an account | swept? |
|---|---|---|
| `payload["accounts"][0]["metrics"]` | the document shape's own key | **no** |
| `next(iter(payload.get("accounts") or []), {})` | the same, through an iterator | **no** |
| `(payload.get("accounts") or [{}])[0].get("metrics", {})` | the pattern the cell's own risk list names | **no** |
| `_KEY = "statement"` … `payload[_KEY]` | the swept key itself, through a name | **no** |
| `for key, value in payload.items(): if key == "statement"` | a mapping walk | **no** |
| `report.statement` | attribute access on the parsed object | **no** |
| `from analysis.serialization import report_to_dict as _publish_one_account` … `_publish_one_account(report)` | the ACCOUNT publisher under an alias | **no** |

**Measured with all seven in the tree: `tools/l1s3_surface_census.py` exit 0, "payload-key reads
swept: 31" — unchanged. `tools.l1_design_reader_probe --census` exit 0 as well.** The aliased seam is
missed by both: the AST census matches the call *name*, the design probe greps the text
`report_to_dict(`, and an alias defeats each.

**How much does it matter.** I then swept the real tree for `accounts`-key reads with the census's own
machinery. There are exactly **two** production sites: `telemetry/record.py::classify_document`
(declared) and `benchmark/normalize.py::lenders` — which reads MoneyThumb's `scorecard` JSON, not our
payload. So **nothing is missed today**, and closing the gap costs one widened predicate plus one
excused entry. But the guarantee the census states — *"a new reader written tomorrow fails this"* — is
measurably false for the most natural new reader, one that reads `accounts`. **S4 is the stage that
writes exactly those readers.** Graded MAJOR for that reason, not for a live miss.

### 3.2 Attack 2 — the line-pinned census fails LOUDLY on drift

Inserting one blank line above `analyze.py`'s seam moved it from 176 to 177.
`tools.l1_design_reader_probe --census` → **exit 1**, naming both halves (`declared but NOT found: 1 —
analyze.py:176`, `found but NOT declared: 1 — analyze.py:177`). It does **not** pass silently. The AST
census, which pins by call rather than by line, stayed **exit 0** through the same edit. The cell's
characterisation is exactly right, and running both is the right answer.

The corollary is COMP-3 in §4.4: the line pin is red again at the composed tree.

### 3.3 Attack 3 — MAJOR-2: `app.js` refuses in two places and answers quietly in three

`node --check` passes. The two refusal branches are real and both key on
`Array.isArray(report.accounts)`, so neither can fire on a payload this tree publishes. But I traced
the render path rather than stopping at the two branches, and the refusal is not the whole surface:

* `renderAnalysis` assigns **`currentAnalysis = report` (line 1105) before returning at the refusal
  (line 1108)**;
* `openStatementModal` assigns **`modalAnalysis = payload.analysis` (line 1633) before calling
  `renderStatementModal`**.

Three other consumers read `.statement` off those globals and answer with an empty object:

1. **`generateSummary()` (line 1810)** — bound unconditionally at line 1896 to `els.summaryBtn`, and
   **not** gated by `setActions`, which only touches the download links. On a document payload it
   takes the non-package branch (`currentAnalysis.package` is absent), reads
   `currentAnalysis.statement || {}`, and writes into `els.summaryBox` a complete credit-memo sentence
   — issuer, period, average daily balance, ending balance, cash flow, NSF count, lender detections,
   exposure and a `Status:` — with every field rendered as its "N/A" placeholder. This is the
   artefact an analyst pastes into a memo. It is the quiet wrong answer this whole stage exists to
   remove, on the one surface the card admits it did not test.
2. **`mainTransactionContext()` → `renderMainTransactions()`** — reached by every
   `[data-transaction-filter]` handler, the sort control and the "show more" control. It reads
   `currentAnalysis?.statement || {}`, yields zero rows and labels the scope "This statement".
   `renderError` does not hide `els.transactionCard`, which `uploadFiles` has already set to
   `display: block`.
3. **`renderModalTransactions()`** — same shape, through `modalAnalysis`.

Dark today, and S4 owns the account selector. But the claim in W3 — *"`webapp/static/app.js` … refuses
in the UI"* — is broader than the code. Two of five reachable consumers refuse. The minimal correction
is to move the two global assignments **after** the refusal (or null them on the refusal path), which
turns the three quiet answers into the same loud one.

### 3.4 Attack 4 — `_RISK_ORDER` cannot reorder any existing gate outcome

`_RISK_ORDER = ("clear", "review", "high")` is reached only inside the
`is_document_payload(payload)` branch of `document_verdicts`; the account-shape path returns
`_account_verdict(payload, None)` immediately, built field-for-field as this gate always built one. No
published payload at this tree carries `accounts`, so the fold is unreachable. Measured on a
single-account payload: the document verdict is **identical to its account's verdict**, `account_index`
`None` on both.

The three tokens are also exactly the vocabulary `analysis/pipeline.py` emits (`high` / `review` /
`clear`, lines 621-625), so the "unknown ranks WORST" clause has no live input. `_Verdict`'s new sixth
field defaults to `None` and every pin in `PINNED_OUTCOMES` / `PUBLISHED_OUTCOME` is constructed as a
`_Verdict`, so both sides of every comparison gained the same default. **Not a movement risk.** The
policy is new and conservative; recorded, not flagged.

### 3.5 Attack 5 — MAJOR-3: members vs jobs is not merely "noted", it is arithmetically wrong

The cell records the divergence as a risk (`totals["completed"]` counts MEMBERS,
`totals["documents"]` counts JOBS) and adds a comment. I measured what the divergence does to the
published figures, on the cell's own fixtures, comparing three packages that hold the **same
banking**:

* **A** — one job, one account (today's shape);
* **B** — one job publishing **two different validated accounts** over **one** statement period;
* **C** — two **separate** jobs, one account each.

Measured: **B and C publish identical `months`, identical `avg_monthly_credits`,
`avg_monthly_debits` and `avg_monthly_cash_flow`.** For B, `totals["documents"] = 1` while
`totals["months"] = 2`, because `months = max(1, len(monthly))` (line 1341) counts **members** and
`_package_members` promotes each account to a member. The three per-month averages are
`total / months`, so a member whose one month of banking spans two accounts has every published
monthly average **halved**.

This is design §6.5's fourth bullet verbatim: *"**and no published average is computed over two
accounts of one document** — the arithmetic, not the field name. The package ADB's member set is
checked for two members sharing a `content_sha256`."* The card implemented a **duplicate-content-digest**
refusal instead, which by construction only catches two accounts publishing *identical* content; two
**different** accounts of one document pass it. I measured B's two member rows carrying **one shared
`content_sha256`** and the package publishing without complaint.

The duplicate-digest refusal is a good check and should stay. It is not the check §6.5 asked for, and
the check §6.5 asked for is the one that would have caught this. Dark today; **S4 must not light the
publisher without it.**

### 3.6 Attack 6 — C18 and the refusals, on a constructed payload

Reproduced through the production functions (results in §1). Two additions:

* **Every KeyError-capable `statement` subscript is accounted for.** I re-swept the tree with the
  census's own matcher and split the 31 sites by form: 19 are subscripts, and 17 of those read an
  **audit CSV's `statement` column** (a filename) or sit in `_rebuild_account_revenue_views`, which
  has exactly two callers, both inside the taught head. The only subscripts on a *payload* are
  `balance_forensic_audit.py:539-540`, and they sit **after** that function's
  `refuse_document_payload`. A `KeyError` into `statement` is not reachable.
* **`_adb_rows` and `_masked` are genuinely agnostic.** `_adb_rows` takes a **metrics** dict, not the
  payload, and is called from the per-account renderer (line 340), so a document payload reaches it
  once per account. `_masked` is a recursive key-name filter and descends `accounts` unchanged. On a
  two-account payload `_analysis_rows` produced 54 rows under sections `document`, `account_1`,
  `account_2` — the collision on `("statement", "ending_balance")` the design named is gone.

### 3.7 Attack 7 — Q10, both fixtures

Constructed on `tests/l1s3_payloads.py` after checking the fixture is one `classify_outcome` really
calls `validated` (it is: `('validated', 'approved')`).

| construction | measured |
|---|---|
| ratified-class omission + one validated account | `('validated', 'approved')` — **not demoted**, as Q10 rules |
| **un**ratified omission + one validated account | `('failed', 'document_omission_unratified')` — L1-C17, and consistent with §1.5's second override |
| two accounts, one withheld | `('withheld', 'account_withheld_adb')` — the weakest account, tie broken by printed order |
| today's package (two single-account jobs) | **no** `sibling_account_omission_detected`, **no** `completeness`, **no** `omitted_section_count`, **no** top-level `omitted_sections` or `excluded_accounts`, member ids unchanged, no `account_index` key |
| ratified-omission package | `sibling_account_omission_detected: true`, `completeness: partial`, `omitted_section_count: 1`, `omitted_sections` length 1 |
| unratified-omission package | **neither** Q10 key present; the account published under `excluded_accounts` with reason `document_omission_unratified`; no document row |

The "publish only when there is something to surface" property holds, and the unratified case is
excluded from membership rather than dressed as `partial` — exactly as the card claims and as Q10
requires.

---

## 4. Attack 8 — SEMANTIC COMPOSITION with L1-S2

Merged in a throwaway worktree (`train9` `5c32046`, `git merge --no-ff --no-commit wave9-l1s3`),
resolved, measured, then aborted and removed. Nothing was committed to either real branch.

### 4.1 BLOCK-1 — eleven S2 Q10 pins fail at the merged tree

```
FAILED tests/test_l1s2_omission_ruling.py  (11 of them)
FAILED tests/test_l1s2_document_outcome.py::test_this_tree_declares_no_document_fold_yet
12 failed, 60 passed
```

The tripwire is expected (§4.2). The eleven are not.

**Root cause, traced.** S2's resolver `tests/test_l1s2_document_outcome.py::document_outcome` is built
to survive S3 landing a fold: it discovers the fold by AST, then tries **two call shapes** —

```python
for argument in (report, document_report_to_dict(report)):
    try:
        verdict = fold(argument)
    except TypeError as exc:      # not this call shape; try the other
        refusals.append(...); continue
```

It tries the `DocumentReport` **object** first. `classify_document` gates on
`is_document_payload(payload)`, which is `False` for a non-Mapping, and therefore **delegates the
object to `classify_outcome`**, which dies at `telemetry/record.py:389` with
`AttributeError: 'DocumentReport' object has no attribute 'get'`. `AttributeError` is not `TypeError`,
so the resolver never reaches the payload leg and every Q10 pin that reads the document leg goes red.

**Proven resolution.** I made `classify_document` refuse a non-Mapping at its own door:

```python
if payload is not None and not isinstance(payload, Mapping):
    raise TypeError("classify_document reads a published PAYLOAD, not " + type(payload).__name__)
```

At the merged tree with that one clause: **71 passed, 1 failed** — and the one failure is the
intentional tripwire. All eleven Q10 pins go green through the payload leg.

This is a defect in `classify_document`, not only a test incompatibility: a function whose contract is
`payload: dict | None`, handed something else, should refuse rather than fail two frames down inside
another function. Widening the resolver's `except` would also make the pins pass, but it would leave
the production function failing deep. **I recommend the production fix**, with the resolver left as
S2 wrote it.

### 4.2 The tripwire — expected red, and nobody owns retiring it

`test_this_tree_declares_no_document_fold_yet` asserts `declared_document_folds() == []`. Its own
docstring says *"S3 landing the fold turns this red, which is the whole point"*. The composition must
retire or invert it; the pins that matter (`test_every_declared_document_fold_is_reachable_by_the_resolver`,
`test_l1s2_protected_carriers.py`, `test_l1s2_omission_ruling.py`) then read the fold, which is what
S2 built the resolver for. **`tests/test_l1s2_protected_carriers.py` passes at the merged tree** — the
15 protected carriers stay green once BLOCK-1 is fixed.

### 4.3 MINOR-6 — the shape helpers are silent on a non-Mapping

The mechanism behind BLOCK-1 generalises. Measured:

```
refuse_document_payload(None)   -> RETURNED (no refusal)
refuse_document_payload([])     -> RETURNED
refuse_document_payload(<obj>)  -> RETURNED
refuse_document_payload("str")  -> RETURNED
refuse_document_payload(3)      -> RETURNED
```

`assert_payload_shape` *does* refuse a non-Mapping (`payload_not_a_mapping`) — that is L1-C16's
third clause — but neither `classify_outcome` nor `classify_document` calls it; both call only
`refuse_document_payload`, which keys on `ACCOUNTS_KEY in payload` and returns for anything that is
not a Mapping. So the loudest of the three helpers is the one the outcome path never reaches.

### 4.4 The composition map for Ocean

| file | conflict | resolution |
|---|---|---|
| `docs/moneythumb-replacement/W3_TRACKA_LOG.md` | CONTENT, one hunk (`61432` / `62572` / `62877`) | append-only concatenation: train9's `§L1S2` + `§Q3PROBE` block, then this branch's `§L1S3`. The train helper's usual case |
| `tests/test_corpus_gate_outcomes.py` | CONTENT, one hunk | **both sides make the identical edit** — `WATCHED = {"analyze_markdown", "analyze_document", "cached_analysis"}` — with different comments. Keep train9's comment (S2's, which explains the gap rather than the tool); the code line is the same either way |
| `corpus_gate.py` | **auto-merges** | train9's `EXCLUDED_ANALYSIS_CALLERS` addition (`tools/l1s2_admission_probe.py`, ~line 832) and this branch's hunks (85-88, 205-225, 1400-1500, 1525-1560, 1709, 1792) are disjoint. **The register is byte-identical to the base on this branch** — the shared-append-surface collision Ocean warned about does not occur here |
| `analysis/pipeline.py` | none | train9 changed it (S2); this branch does not touch it |
| **BLOCK-1** | semantic | apply the `classify_document` non-Mapping `TypeError` clause **in the composition**, or the branch amends it before compose |
| **COMP-3** | semantic, MINOR | `tools/l1_design_reader_probe.py`'s `SEAMS` needs one line re-pinned: `corpus_gate.py` **1553 → 1564** (S2 added 11 lines above it). Without it `--census` is **exit 1** at the merged tree, and that census is one of the card's headline exits |
| **COMP-4** | semantic, MINOR | retire or invert `test_this_tree_declares_no_document_fold_yet` (§4.2) |

**Measured at the merged tree** (after resolving the two text conflicts):

| check | result |
|---|---|
| `tests/test_l1s2_omission_ruling.py` + `test_l1s2_document_outcome.py` + `test_l1s2_protected_carriers.py` + `test_sibling_omission.py` | 12 failed / 60 passed → **with the BLOCK-1 fix: 1 failed (the tripwire) / 71 passed** |
| `tools/l1s3_surface_census.py` | **exit 0** |
| `tools.l1_design_reader_probe --census` | **exit 1** — COMP-3 |
| `tests/test_l1s3_census.py`, `test_l1s3_readers.py`, `test_l1s3_surfaces.py`, `test_payload_shape.py`, `test_document_outcome.py`, `test_document_report.py` | **115 passed**, exit 0 |
| canonical guards (5) | **255 passed**, exit 0 |
| canonical conformance (7) | **1,270 passed / 40 skipped**, exit 0 |

---

## 5. The rest of the findings

### 5.1 MINOR-1 — §6.5's per-account gate assertions are mostly absent

§6.5 says its seven assertions are *"Added by stage S3, dark, and lit by S4"*, and §7's S4 row says
*"corpus gate's new per-account assertions lit"*. At this tip the gate gained `document_verdicts`,
`_account_verdict`, `_RISK_ORDER` and two refusals. It did **not** gain:

* the per-account verdicts **asserted both ways**, so a document verdict that does not follow from
  its accounts fails the gate (they are returned and discarded: `verdict, _accounts = document_verdicts(payload)`);
* `PINNED_CURRENCY` / `PINNED_CURRENCY_SOURCE` totality per `(path, account)` — replaced by a refusal,
  which is the fail-closed answer but not the assertion;
* the ADB basis / policy stamps on **every account** plus *"no document-level ADB field exists"*;
* the no-average-over-two-accounts member-set check (**MAJOR-3**);
* `document.omitted_sections` reasons asserted against L1-C17's vocabulary **at the gate** (it is
  asserted in `classify_document` instead);
* `document.internal_transfers` indices resolving one-to-one.

The card's own Scope names only two of the seven, so this is a design-vs-card scope question rather
than a broken promise — but S4 is told to *light* assertions that were never *added*. Ocean should
say which stage owns them.

Related and reconciled: §7's S3 row and §1.6 say `TELEMETRY_VERSION` is bumped by S3. It is **not**
bumped on this branch — correctly, because the card's Git-ownership section says *"no version
constant"* and the record shape does not move. Recording it so the discrepancy is on the record
rather than found later.

### 5.2 MINOR-2 — `evaluate_accounts` is written and unreachable

`telemetry/stated_counts.py::evaluate_accounts` has **no caller anywhere in the tree** outside its own
test. The module is deliberately unwired into production (`test_the_observer_is_not_wired_into_any_production_module`)
and is run as `python -m telemetry.stated_counts --run <run>` — and that CLI, at line 1007, calls
**`evaluate`**, which now *refuses* a document payload. So the count observer will **raise** on a
multi-account document rather than render one observation per account. Fail-closed, so not a quiet
answer; but the W3 table presents `evaluate_accounts` as a taught renders-per-account reader, and the
only entry point never reaches it. S4 must wire it.

### 5.3 MINOR-3 — `refuses` is a name check, not a reachability check

`_called_names` collects every `ast.Call` name under `ast.walk(node)` with no reachability analysis.
I wrote the mutant the cell's table does not have — **M7: the refusal moved into `if False:`** — and
applied it to each of the eight refusal call sites in turn.

**The census stayed exit 0 at all eight.** The unit tests are the killers. Per site, the named
specific killer (full default suite, one mutant at a time, tree verified clean after each):

| refusal site | census | named killer |
|---|---:|---|
| `telemetry/record.py::classify_outcome` | 0 | `test_classify_outcome_refuses_the_document_shape` |
| `telemetry/diagnostics.py::diagnose` | 0 | `test_diagnose_refuses_the_document_shape` |
| `telemetry/stated_counts.py::evaluate` | 0 | `test_evaluate_refuses_the_document_shape` |
| `benchmark/ourside.py::_account` | 0 | `test_the_benchmark_refuses_a_document_it_cannot_declare_a_second_value_for` |
| `corpus_gate.py::check_currency` | 0 | `test_the_gate_refuses_to_pin_a_denomination_it_cannot_key` |
| `adb_forensic_audit.py::audit_one` | 0 | **NONE** — §5.7 |
| `balance_forensic_audit.py::audit_source` | 0 | **NONE** — §5.7 |
| `corpus_gate.py::check_currency_source` | 0 | **NONE** — §5.7 |

The consequence for the record: the W3 sentence *"`refuses` must call the refusal"* should read *"must
mention the refusal"*. What proves the refusal fires is the per-reader test, and M7 is the mutant that
shows the difference. Worth adding to the table.

### 5.4 MINOR-4 — two refusal messages name the wrong surface

* `balance_forensic_audit.py::audit_source` passes `surface="balance_forensic_audit.py::audit_one"` —
  a function name that exists in the *other* audit;
* `benchmark/ourside.py::_account` passes `surface="benchmark/ourside.py::OurFileResult"` — the class,
  not the census key.

Both are constants of ours, so there is no privacy question; but the refusal message is the thing a
person reads when a document publisher first breaks, and naming a different function is a wrong
signpost. Neither census can catch it: the forward check looks at the call, never at its argument.

### 5.5 MINOR-7 — the mutation table's scoring would count a non-run as a kill

`killed = code != 0 or census != 0`. pytest exits 2 (interrupted), 3 (internal), 4 (usage) and 5 (no
tests collected) would all score as kills. **Discharged here**: I re-ran the table and every one of the
six mutants produced at least one named `FAILED` test (3 / 1 / 1 / 1 / 2 / 1), which is the evidence
the exit code alone would not have been. Recommend `killed = code == 1 and failing` (or an explicit
`DID_NOT_RUN` row) so the next table cannot be satisfied by a collection error.

### 5.6 MINOR-9 — both censuses are blind inside `analysis/serialization.py`

`tools/l1s3_surface_census.py` skips `PUBLISHER_MODULE` in its seam half, and this branch added the
same exclusion to `tools/l1_design_reader_probe.py` (which is what turns the base's four "undeclared"
findings into zero). The exclusion is right — the module that *defines* the publisher is not one of
its call sites — but it is wholesale, so a *new* single-account publish added inside
`analysis/serialization.py` would be invisible to both instruments. RULE S is covered instead by S1's
seam probe, which is the right coverage; recording the gap so nobody later reads "the census holds" as
covering the serialiser.

### 5.7 MAJOR-4 — three of the eight refusals have no test at all

Five of the eight refusal sites had a named specific killer in the fast run. For the other three I
re-ran M7 against the **whole default suite**, one mutant at a time, from a driver **outside** the
tree, restoring by writing the original bytes back and verifying `git status --porcelain` empty after
each:

```
BASELINE full suite exit 0   7578 passed, 43 skipped, 34 deselected   (288.96s)
M7 adb_forensic_audit.py::audit_one          census=0  suite=PASS  failing=0  clean=True
M7 balance_forensic_audit.py::audit_one      census=0  suite=PASS  failing=0  clean=True
M7 corpus_gate.py::check_currency_source     census=0  suite=PASS  failing=0  clean=True

HOLES: adb_forensic_audit.py::audit_one, balance_forensic_audit.py::audit_one,
       corpus_gate.py::check_currency_source
```

(The second row is `balance_forensic_audit.py::audit_source`; the mutant is located by the surface
string the code passes, which is misnamed — MINOR-4.)

**Three refusals can be neutralised with the whole 7,578-test suite green and the census green.** For
those three readers, the entire proof that they refuse is the census's name check — and §5.3 shows the
name check is satisfied by dead code. BATCH9-RULES requires "a MUTATION TABLE for every gate … every
killer named"; `refuse_document_payload` at each site is a gate this card added, and three of the
eight have no killer.

It matters most for `balance_forensic_audit.py::audit_source`. That is the **legacy indexing path** —
the one reader of the design's ten that raised at all, and the one the card's own Proof section
promises to pin ("the loud refusal on the legacy indexing path"). Its guard is now the only thing
standing between a document payload and the bare `KeyError` at `:539-540`, and nothing tests it.

Three small tests close this. It moves nothing.

**An aside worth recording**, because it cost me a re-run:
`tests/test_currency_source.py::test_only_the_readers_the_schema_and_the_gate_know_the_provenance_exists`
enumerates every production `*.py` whose text contains `currency_source`. My first M7 driver lived at
the repository root and listed `"tests/test_currency_source.py"` in a constant — which put the token in
a production-looking module and turned that guard red for every mutant, manufacturing a killer that
was mine, not the tree's. The guard is behaving exactly as designed; a harness that writes a file into
the tree under test is not.

---

## 6. The floor, and what I did not re-run

Reproduced at the tip, exit codes verbatim:

| proof | command | result |
|---|---|---|
| full default suite | `python -m pytest tests/ -q -p no:randomly` | **7,578 passed / 43 skipped / 34 deselected**, exit 0, 219 s |
| canonical guards (5, BATCH9-RULES) | the five named | **255 passed**, exit 0 |
| canonical conformance (7) | the seven named | **1,270 passed / 40 skipped**, exit 0 |
| the S3 surface census, both ways | `python tools/l1s3_surface_census.py` | **exit 0** — 20 / 13 / 31 / 8 |
| the design's seam census | `python -m tools.l1_design_reader_probe --census` | **exit 0** at tip, **exit 1** at base (verified stale) |
| the census's own tests + the reader tests | the six L1-S3 / L1-S1 test files | **115 passed**, exit 0 |
| the mutation table | `python -m tools.l1s3_mutation_table` | **6 / 6 killed**, exit 0, every killer named, tree clean after each |
| RULE S at the pipeline seam | `tools/l1s1_seam_probe.py`, base capture vs tip capture, `--per-parser 3`, `PYTHONHASHSEED=0` | 232 documents / 80 registrations; **document seam 232/232 byte-identical**, account seam 232/232, integrity flags list **and order** 232/232, ladder unchanged 232, **`MOVED_TOTAL=0`**, exit 0 |
| the corpus gate | `python corpus_gate.py` | **GREEN**, exit 0 — 105 / 3 / 1; verdicts 1 / 3 / 102 / 3; 108/108 currency; 108/108 provenance; 109 offline; 664.8 s |
| privacy — added lines | `tools/privacy_scan_branch.py --rows <run>/rows.csv --data-dir <cold> --base 4953806 --ref HEAD` | **hit_count 0**; MONEY / DIGITS / DATES / WORDS 0; residue files 0, residue sites 0; 3,510 added lines vs 3,380 documents (3,351 with cached text). **raw 28**, all `words_class` |
| privacy — messages | `tools/huntington_msg_privacy_scan.py`, same population | **exit 1** — MONEY 0 / DIGITS 0 / DATES 0 / **WORDS 2**; 14 commits scanned; both hits named and judged in §2 |
| **archive sweep, a bounded slice, at BOTH trees** | `tools.regfp_zero_movement_sweep --start 0 --end 350`, run at the tip and at `mt9-l1s3-base` over the identical population | **every one of the nine aggregate counts identical at both trees**: 350 documents, 280 compared, **277 identical**, 3 moved, 3 no-payload-now-publishes, **0 payload-now-raises**, 64 no-payload-raises-again, 3 no-OCR-artifact, 0 multi-artifact. Both exit 1 (the tool exits non-zero on any finding). 235 s / 226 s |
| **attribution of that slice** | `python -m tools.l1s3_sweep_attribution --base … --tip …` | **exit 0** — **6 findings at BOTH trees, identical** (same document, same verdict, same changed field names); **0 differing, 0 tip-only, 0 base-only**. Every finding is train9's composed movement against the batch-8 run of record; **none is this branch's** |
| composition | see §4 | two text conflicts; **BLOCK-1**; COMP-3; COMP-4 |

**The attribution instrument works, and it also refuses correctly.** My first attempt pointed it at the
sweep's `--out` *report* rather than its stdout log; it declined with *"one of the two sweeps produced
no findings at all, so a diff of the two would be a claim about a measurement that did not happen"* and
exit 2, rather than reporting a vacuous zero. That guard is the right one for an instrument whose
headline is a zero, and it fired on a reviewer's mistake, which is when such a guard is worth having.

**Not re-run, and why.** The 677-document wide seam probe, the 80-registration replay pair at both
trees, the remaining ~3,030 documents of the archive sweep, and the corpus-marked slice. The
equivalence argument I am relying on: the 232-document / 80-registration seam probe I *did* run is the
same instrument over the same seam and returns `MOVED_TOTAL=0` with the integrity-flag **order** held;
the 350-document sweep slice I *did* run at both trees reproduces the cell's method end to end and
attributes every finding away from this branch; the corpus gate — the pinned-surface oracle those
sweeps protect — is GREEN with all 108 currency and provenance pins intact; and the only mechanism
that could move a byte is `document_report_to_dict`'s RULE S branch, which the probe exercises on
every one of the 232 and the sweep on every one of the 280 compared. The wide probe and the
80-registration replay pair remain the cell's evidence.

**Host discipline.** One heavy proof at a time; `Get-CimInstance Win32_Process` checked before each;
detached runs with an `EXIT=` terminator on a durable log. The mutation table and my own M7 harness
both verified the tree clean after every mutant. One M7 run was killed by a tool timeout and left a
mutant in **my throwaway worktree** (not the branch); I restored it and verified
`git status --porcelain` empty in both `zz3` and `mt9-l1s3` before continuing. The branch worktree was
never modified.

---

## 7. Two corrections to the record

### 7.1 MINOR-5 — "raw 0" is not what the scanner says

The W3 privacy row reads *"**0 hits / raw 0** — 3,133 added lines"*. Measured at `081fd28`, the tree
with exactly 3,133 added lines: `hit_count 0`, **`raw_hit_count 21`**, `excluded_by_rule
{"words_class": 21}`. At the tip: `hit_count 0`, **`raw_hit_count 28`**, `{"words_class": 28}`. Every
raw hit is WORDS-class and discharged by the scanner's own documented exclusion; the substantive
numbers (MONEY / DIGITS / DATES 0, residue 0) reproduce exactly. BATCH9-RULES asks for the raw figure
specifically, so the row should read `0 hits / raw 28, all WORDS-class`.

### 7.2 MINOR-8 — the guard count

The W3 row reads *"canonical guards (9 files) … 349 passed"*. BATCH9-RULES' canonical guard set is
**five** files and reproduces at **255** — the base floor exactly. The cell's nine-file run is a
superset and green; the canonical figure should be the one stated so the floor is comparable across
cells.

---

## 8. What I would ask before compose

1. **Fix BLOCK-1** — `classify_document` refuses a non-Mapping with `TypeError` (proved green at the
   merged tree), and re-run the S2 pins there.
2. **Re-pin COMP-3** — `corpus_gate.py` `1553 → 1564` in `tools/l1_design_reader_probe.py::SEAMS`, at
   the composed tree.
3. **Retire COMP-4** — `test_this_tree_declares_no_document_fold_yet`, whose whole purpose was to go
   red here.
4. **MAJOR-3 is S4's gate condition.** The publisher may not light until the package refuses — or
   correctly divides for — two members sharing one `content_sha256`. §6.5 named this; it is not built.
5. **MAJOR-2** — move `currentAnalysis = report` and `modalAnalysis = payload.analysis` after their
   refusals, so the summary button and the transaction controls cannot answer a document payload.
6. **MAJOR-1** — widen the reverse sweep to the `accounts` key (cost measured: one excused entry for
   `benchmark/normalize.py::lenders`), before S4 writes readers that reach for it.
7. **MAJOR-4** — three tests, one per untested refusal, and M7 (the refusal in a dead branch) added to
   the mutation table so the next stage cannot re-open the hole. The `balance_forensic_audit` one is
   owed by the card's own Proof section.

None of 4-7 moves a document, and none is a reason to hold the *measurement*. 1-3 are.

---

## 9. What this review is not

I did not re-run the 677-document wide seam probe, the 80-registration replay pair, the remaining
~3,030 documents of the archive sweep, or the corpus-marked slice. Those four numbers are the cell's,
and §6 states the equivalence argument I am relying on instead. Everything else in this document was
measured on this host, and every measurement that disagreed with the W3 section is recorded as a
finding rather than smoothed over.

**This review's own scans**, reported the way MINOR-5 asks the cell to report its own. Branch scan
with this file committed: `hit_count 0`, MONEY / DIGITS / DATES / WORDS **0**, residue files 0,
residue sites 0, exit 0, over 4,118 added lines — **raw 49**, every one WORDS-class and discharged by
the scanner's `words_class` rule (this document adds 21 of them to the tip's 28). Message scan of this
review's own commit alone: `hit_count 0`, all four classes **0**, exit 0 — the first draft of that
message produced two WORDS bigrams, and since nothing cites an unpushed tip I reworded rather than
attribute them, which is the option §2 notes was available to the cell as well. The branch's message
scan is therefore unchanged at WORDS 2, both of them the cell's and both judged dischargeable in §2.

**Throwaway trees.** Two worktrees were created for the attacks (the composition merge; the census and
mutation scratch) and both were removed; `git worktree list` carries neither. `mt9-l1s3` was never
modified except by this one file, and `git status --porcelain` is empty at close.

---

# Re-review (closure `fc104c6`)

**Reviewer:** the same independent cell. **Branch** `wave9-l1s3`, closure tip `fc104c6`, 26 commits
from `4953806`. **Composition target now** `train9` `fe52365` (it was `5c32046` at the first review;
`80186ba` is an ancestor). Everything below was re-measured. The findings are mine; the closure is
theirs; nothing was accepted on their word.

## VERDICT

# CONFIRMED — COMPOSE

All fourteen findings are closed, and the one that gated composition is closed by the measurement
that decides it: **at the merged tree the S2 pins are 71 passed / 1 failed, and the single failure is
the intentional tripwire.** One new MINOR is raised below; it gates nothing.

## 0. The history rewrite — verified message-only, and this review passed through untouched

Seven messages were reworded with `git filter-branch`, so every sha I cited moved. I did not take
that on trust; the old objects are still reachable and I compared them:

| | old | new | |
|---|---|---|---|
| pre-closure tip | `70998a3` | `acfb529` | tree `159b23d4…` **on both** |
| this review's commit | `272b095` | `05251e0` | tree `9022d26a…` **on both** |
| `BATCH9_L1S3_REVIEW.md` blob | `5a16a85f…` | `5a16a85f…` | **and the same blob at the closure tip** |

The rewrite moved messages and nothing else, and this review's text is byte-identical to what I
committed. One bookkeeping correction to the handoff: `HEAD^{tree}` at the closure tip is
`98ebd27b…`, not `be54beb…`. The substantive claim was right; the anchor quoted for it was not.

## 1. The decisive measurement — BLOCK-1

Throwaway worktree, `train9 fe52365` merged with `wave9-l1s3`, resolved exactly as my §4.4 map said
(W3 concatenated; `tests/test_corpus_gate_outcomes.py` keeping train9's comment, the `WATCHED` line
being character-identical on both sides; `corpus_gate.py` auto-merges, register untouched):

    tests/test_l1s2_omission_ruling.py + test_l1s2_document_outcome.py
      + test_l1s2_protected_carriers.py + test_sibling_omission.py
    1 failed, 71 passed, 1 deselected
    FAILED tests/test_l1s2_document_outcome.py::test_this_tree_declares_no_document_fold_yet

**Eleven Q10 pins green; the 15 protected carriers green; the only red is S2's own tripwire**, whose
docstring says it exists to go red the day a fold lands. That is the same 71 / 1 my proposed fix
produced in the first review, reached by their implementation rather than by my patch.
**BLOCK-1 closed.**

Also measured at that merged tree: AST census **exit 0** (46 reads, 8 seams, publisher 2 of 2), the
six L1-S3 files **151 passed**, guards **255**, conformance **1,270 / 40**.

## 2. Per finding — claimed against measured

| finding | measured at `fc104c6` | verdict |
|---|---|---|
| **BLOCK-1** | `classify_document` raises `TypeError` naming `document_report_to_dict` on all five non-payload types I threw at it (`DocumentReport`, `list`, `str`, `int`, a bare object); `refuse_document_payload` raises `TypeError` one layer down on the same five; `is_document_payload` total (False on all five). `classify_document(None)` still returns the failed / no-analysis pair and an account payload still returns validated / approved — RULE S intact | **CLOSED** |
| **MAJOR-1** | re-ran my seven scratch readers verbatim: census **exit 1**, six named — the five payload readers by the widened reverse sweep, the aliased publisher by the seam half, which now says "aliased as". Swept reads 31 to **46**. All seven are committed as the `_SEVEN` vector in `tests/test_l1s3_census.py`, the sixth pinned as a boundary decision beside a `document.accounts[0]` positive control | **CLOSED** (see §3) |
| **MAJOR-2** | the three sites I named all clear their global **on** the refusal path, and they found a fourth I had not: the revenue-review refresh at :1994. `generateSummary` returns at its `if (!currentAnalysis)` guard; both transaction renderers read a nulled global rather than a document payload; the transaction card is hidden **in the refusal branch**, not in `renderError` — the correct scoping, since hiding it in `renderError` would change every other error's behaviour. `node --check` exit 0 | **CLOSED** |
| **MAJOR-3** | the refusal keys on the shared document identity (`content_sha256`, job id as fallback) — §6.5's and Q5's own wording. Measured on three packages holding the same banking: one job with two validated accounts publishes the three monthly averages and the package ADB as **None**, with `cross_account_averages_refused: true` and a reason; **the sums are untouched** (total credits identical to the two-separate-jobs package); a package of today's payloads carries **neither** key and keeps every figure. Killed by M7 | **CLOSED** — one residual, MINOR-10 |
| **MAJOR-4** | M8 / M9 / M10 each killed **twice** — a named test *and* a red census: `test_the_balance_audit_refuses_the_document_shape`, `test_the_adb_audit_refuses_the_document_shape`, `test_the_gate_refuses_to_pin_a_provenance_it_cannot_key`. The legacy-indexing path the card promised to pin is pinned | **CLOSED** |
| MINOR-1 | `_assert_document_verdict_follows(document, per)` built and called; it sits **inside the document branch**, past `document_verdicts`' single-account early return, so it is dark. The other four §6.5 assertions are named as owed by S4 or an Ocean ruling — honestly, in the closure section | **CLOSED as scoped** |
| MINOR-2 | `observe_run` — the observer's only entry point — now calls `evaluate_accounts`; for an account payload that is a one-element list, so today's output is one observation per document exactly as before | **CLOSED** |
| MINOR-3 | `test_a_refusal_in_a_dead_branch_no_longer_satisfies_the_forward_check`; my M7 satisfied the census at all eight refusal sites and now fails it | **CLOSED** |
| MINOR-4 | all eleven `surface=` strings match their own function; the balance audit's and the benchmark's are corrected | **CLOSED** |
| MINOR-5 | the branch scan reports **raw 68**, every one WORDS-class, `hit_count 0` | **CLOSED** |
| MINOR-6 | closed with BLOCK-1 | **CLOSED** |
| MINOR-7 | `DID_NOT_RUN_EXITS` is the set 2 through 5; a kill is exit 1 **with** at least one named failing test, or a red census — exactly the correction asked for | **CLOSED** |
| MINOR-8 | the canonical five are stated first at **255**, the superset kept as a second row | **CLOSED** |
| MINOR-9 | the publisher exclusion is now narrow: account-publisher calls inside `analysis/serialization.py` are pinned at **2 (declared 2)**, and a third fails the census | **CLOSED** |
| WORDS-2 | **the question is moot**: the message scan over all 26 commits is `hit_count 0` — MONEY, DIGITS, DATES and WORDS all **0**, exit 0. The reword removed both bigrams. My §2 said no rewrite was *required*; it also said the reason the cell gave for refusing one was the wrong reason. They rewrote | **CLOSED** |

## 3. The reader-6 adjudication — their decision is CORRECT, and my finding was over-broad

Their claim is that `report.statement` is out of scope **by decision**: a `Report` IS one account, so
reading its statement cannot select one account of several. I did not take the argument; I tested its
converse. Four scratch readers, same tree, same census:

| scratch reader | swept? |
|---|---|
| `document.accounts[0].statement` | **caught** |
| `next(iter(document.accounts)).statement` | **caught** |
| `len(document.accounts)` | **caught** |
| `report.statement` — my reader 6 | not swept |

**I accept the decision.** The L-1 defect is *selecting one account out of something that holds
several*, and on the object side that requires reaching `DocumentReport.accounts` — every spelling of
which the widened sweep catches. `report.statement` cannot commit the defect: by S1's data model a
`Report` is one account, so `.statement` on it is correctly scoped. Sweeping `.statement` on any
object would fire on every legitimate per-account body in the tree and force a page of excusals that
assert nothing. The narrowing is load-bearing precision, not a hole — and it is pinned as a decision
with its own positive control rather than left to memory, which is the right treatment. Reader 6 was
the one of my seven that did not describe a hazard.

## 4. The reachability argument for the carried pair — ACCEPTED

They ask to carry the 80-registration replay pair and the full 3,380-document sweep. **I accept**, on
three grounds I checked rather than assumed:

1. **The publisher is untouched by the closure.** Over production, `git diff --stat acfb529..HEAD`
   names `analysis/payload_shape.py`, `balance_forensic_audit.py` (2 lines), `benchmark/ourside.py`
   (2 lines), `corpus_gate.py`, `telemetry/record.py`, `telemetry/stated_counts.py`, `webapp/app.py`
   and `webapp/static/app.js` — and **not** `analysis/serialization.py`, **not**
   `analysis/pipeline.py`. The bytes those two instruments compare come from code identical to the
   tree where I already measured a 350-document sweep at **both** trees with all nine counts equal,
   and `MOVED_TOTAL=0` at the seam.
2. **Every closure edit is unreachable or inert.** The two new doors fire only on a non-Mapping, and
   production hands these functions a dict or `None` (the `None` answer measured identical). The
   gate's new assertion is inside the document branch, past the single-account early return. Two
   edits are `surface=` strings. The observer's loop yields exactly one observation for a
   single-account payload. The package refusal keys on members sharing a document identity, which
   today's one-member-per-job packages never produce — measured: a package of today's payloads is
   unchanged and carries neither new key.
3. **I re-ran the two instruments that would catch it anyway** — the corpus gate over all 109 pinned
   documents, which exercises `document_verdicts` on the pinned path, and the seam probe over 232
   documents and 80 registrations. Both are below, and both are clean.

## 5. MINOR-10 (new) — `months` still counts members, and the dashboard calls them periods

MAJOR-3's arithmetic is genuinely fixed: nothing divides by the member count any more. But
`months = max(1, len(monthly))` still counts **members**, so a package holding one two-account
document publishes a month count of two, and `webapp/static/app.js:1458` renders that as
"statement periods" — two of them, for one statement period of paper.

No money figure derives from it: the five per-period keys are `None` and the refusal reason is
published beside them. So this is a false label, not a false figure. It is dark, it is one line, and
it belongs in S4's lane beside the account selector. **It gates nothing.**

An observation in the same lane, not a finding: after the refusal, a transaction filter click calls
`renderMainTransactions`, which unconditionally re-shows the transaction card at :543. The table is
empty and the global is null, so no wrong figure is shown — but the card the refusal branch hid can
come back.

## 6. The floor reproduced at `fc104c6`

| proof | result |
|---|---|
| full default suite | **7,614 passed / 43 skipped / 34 deselected**, exit 0, 208 s |
| canonical guards (5) | **255 passed**, exit 0 |
| canonical conformance (7) | **1,270 passed / 40 skipped**, exit 0 |
| the six L1-S3 files | **151 passed**, exit 0 |
| AST surface census, both ways | **exit 0** — 20 readers / 20 excused / **46** key-reads swept / 8 seams / publisher **2 of 2** |
| the design's seam census | **exit 0** on the branch, their own moved line re-pinned |
| the census bites | my seven readers re-run: **exit 1**, six named; the three `document.accounts` probes caught; `report.statement` correctly not |
| mutation table | **10 / 10 killed**, exit 0, each by a NAMED failing test or a red census; **M8 / M9 / M10 killed twice**; tree clean after every mutant |
| `node --check webapp/static/app.js` | exit 0 |
| corpus gate | **GREEN**, exit 0 — 105 PASS / 3 WITHHELD / 1 REFUSED; verdicts 1 refused / 3 review / 102 validated / 3 withheld; 423.3 s. Identical to the first review's gate, so the new assertion on the pinned path moved nothing |
| RULE S at the pipeline seam, base against tip | 232 documents / 80 registrations; **document seam byte-identical 232 of 232**, account seam 232 of 232, **integrity flags list AND order 232 of 232**, ladder unchanged 232, **`MOVED_TOTAL=0`**, exit 0 |
| privacy — added lines | `hit_count 0`; MONEY / DIGITS / DATES / WORDS **0**; residue files 0, residue sites 0; exit 0; 5,196 added lines against 3,380 documents (3,351 with cached text); **raw 68**, all `words_class` |
| privacy — messages | **26 commits, `hit_count 0`, all four classes 0, exit 0** |
| the merged tree | S2 pins **71 passed / 1 failed** (the tripwire); census exit 0; six files 151; guards 255; conformance 1,270 |

Carried on the cell's evidence, under §4: the 677-document wide seam probe, the 80-registration
replay pair, the remaining sweep documents, and the corpus-marked slice.

## 7. The composition map, updated for `train9 fe52365`

| item | state | owner |
|---|---|---|
| `docs/moneythumb-replacement/W3_TRACKA_LOG.md` | CONTENT conflict, one hunk — append-only concatenation | Ocean, the train helper's usual case |
| `tests/test_corpus_gate_outcomes.py` | CONTENT conflict, comment only — the `WATCHED` line is character-identical on both sides; keep train9's comment | Ocean, trivial |
| `corpus_gate.py` | **auto-merges**; `EXCLUDED_ANALYSIS_CALLERS` untouched on the branch, so no shared-append collision | — |
| **BLOCK-1** | **CLOSED** — verified at the merged tree, 71 / 1 | done |
| **COMP-3** | still owed, and it has MOVED with the tree: `tools/l1_design_reader_probe.py`'s seam list needs the gate's self-check line **1597 to 1608** at the merged tree, S2 having added eleven lines above it. Measured: the probe's census is **exit 0 on the branch** and **exit 1 at the merged tree**, naming both halves. The branch correctly re-pinned only the line its own edit moved | **Ocean, at composition** |
| **COMP-4** | invert or retire `test_l1s2_document_outcome.py::test_this_tree_declares_no_document_fold_yet` — S2 wrote it to go red exactly here | **Ocean, at composition** |
| §6.5's remaining four assertions | named as owed in the closure section; MAJOR-3 remains S4's gate condition before the publisher lights | **S4, or an Ocean ruling** |
| MINOR-10 | the month count counts members; the dashboard calls them periods | **S4's lane** |

## 8. What this re-review is not

I did not re-run the four carried proofs of §4, and §4 says why I accept carrying them. Everything
else above was measured on this host at `fc104c6`. Both throwaway worktrees were created and removed;
`git worktree list` carries neither; `mt9-l1s3` was modified by nothing but this file.

**This re-review's own scans**, reported the way MINOR-5 asked the cell to report its own. With this
section committed, the branch scan is `hit_count 0` — MONEY, DIGITS, DATES and WORDS all 0, residue
files 0, residue sites 0, exit 0 — every raw hit WORDS-class and discharged by the scanner's own
`words_class` rule. The message scan over all 27 commits is `hit_count 0`, all four classes 0, exit 0.
My first draft of that commit message contributed one WORDS hit, an ordinary English noun I had chosen
freely; I reworded rather than attribute it, because §2 is the standard I held the cell to and nothing
cites an unpushed tip.

---

# Re-review (closure-2 `5bc8f37`)

**Reviewer:** the same independent cell. **Branch** `wave9-l1s3`, closure-2 tip `5bc8f37`, 30 commits
from `4953806`. **Composition target** `train9` `14f10a1` (`47d2f87` is an ancestor; I merged the
current tip, which is strictly the more faithful test).

## VERDICT

# CONFIRMED — COMPOSE

with the composition checklist in §7, and one condition on COMP-5 stated in §5.

## 0. First, what I got wrong

My CONFIRMED at closure-1 was reached with the S2 pins run at a merged tree and **the corpus gate not
run there**. The pins were the thing I had argued was decisive, and they were green; the gate was the
thing that was actually broken, and I never asked it. A merged tree is a tree, and the proof floor
that applies to a tree applies to it — I applied a subset of my own choosing and called the result
confirmed. That is the defect in my method, not in theirs, and this section exists so it is on the
record rather than absorbed. **This time the gate at my own merged tree is the first measurement in
this document, and `pytest -m corpus` is the second.**

## 1. THE DECISIVE MEASUREMENT — the gate, at my own merged tree

Throwaway worktree beneath `.claude/worktrees/` (the slice's archive-currency proof walks ancestors
for the OCR store and fails closed elsewhere), `train9 14f10a1` merged with `wave9-l1s3`, two
conflicts resolved per the map, then COMP-3, COMP-4 and COMP-5 applied — COMP-5 in my own words, not
copied from the cell (§5).

| measurement at the merged tree | result |
|---|---|
| **`python corpus_gate.py`** | **GREEN, exit 0** — 105 PASS / 3 WITHHELD / 1 REFUSED; verdicts 1 refused / 3 review / 102 validated / 3 withheld; 565.2 s |
| **`pytest -q -m corpus`** | **31 passed, exit 0**, 1,266 s — and I confirmed by collection that both previously-red tests are in that 31: `tests/test_corpus_gate.py::test_corpus_gate_is_green` and `tests/test_discovery.py::test_a_warm_rerun_reproduces_the_cold_run_with_identity_recovered` |
| full default suite | **7,715 passed / 43 skipped**, exit 0, 213 s |
| S2 pins — `test_sibling_omission.py`, `test_l1s2_document_outcome.py`, `test_l1s2_omission_ruling.py`, `test_l1s2_protected_carriers.py` | **72 passed, 0 failed** |
| `tools.l1_design_reader_probe --census` after COMP-3 | **exit 0** |

The `PayloadShapeError` from `balance_forensic_audit.py::audit_source` on a pinned document is gone,
and the two red slice tests are green. **The defect that discarded the last merge is closed.**

## 2. The clause — verified to be exactly what was claimed

`git diff 5ba2a38..HEAD` over production names **one file**: `analysis/serialization.py`, **one hunk**,
`_publishes_todays_payload`. The body goes from the four-way conjunction to
`return len(document.accounts) == 1`. I checked the neighbourhood explicitly: `report_to_dict`,
`document_report_to_dict`, `_account_content_digest` and both wrapper refusals
(`document_publishes_no_account`, the duplicate-content refusal) are **untouched** — no hunk reaches
them. The ownership exception is on the record in W3 under its own heading: `analysis/serialization.py`
and S1's RULE S tests are outside this card's declared ownership and Ocean directed the edit.

**The 0-to-6 flip, reproduced — and it is the fix's proof.** The flip is only observable at a tree
that carries S2's omissions, so I measured it at the merged tree against base `4953806`:

| merged tree, document seam vs base `4953806` | byte-identical | moved | `MOVED_TOTAL` | exit |
|---|---:|---:|---:|---:|
| **with the fix** (account count alone) | **232 / 232** | 0 | **0** | 0 |
| **with the PRE-FIX four-way clause restored** | **226 / 232** | **6** | **6** | 2 |

The **account seam is 232 / 232 in BOTH runs**. That is the part that makes this evidence rather than
a number: the six documents did not change what they say, only which *shape* the wrapper chose to say
it in. Six of the 232-document cohort are among L1-S2's fifteen carriers, and under the old clause
each flipped to `document` + `accounts` — which is precisely the payload the account-scope readers
refuse, and precisely why the gate died.

## 3. The field-set tripwire — a real one, in both directions

`test_every_document_level_field_is_declared_against_rule_s` asserts
`{f.name for f in fields(DocumentReport)} == set(DOCUMENT_LEVEL_FIELDS)`, and `DOCUMENT_LEVEL_FIELDS`
carries a sentence per field saying where a single-account document keeps that fact. Judged against
the two failures it is supposed to prevent:

* **a new undeclared document-level field** — red, on the set equality. A stage adding one must write
  down where it lives, which is the decision the conjunction used to force;
* **a silent payload lighting** — red twice over, and not by that test:
  `test_rule_s_adds_no_key_of_any_kind` asserts the published key set equals `report_to_dict`'s and
  that neither `document` nor `accounts` appears, and
  `test_a_single_account_document_publishes_todays_payload_whatever_it_carries` asserts full payload
  equality across three parametrisations (omission, roll-up, boundary mechanism). A single-account
  payload that quietly gained a document block fails both.

One gap I looked for and found covered: the field-set test compares NAMES, so *repurposing* an
existing field rather than adding one would slip past it — but
`test_analyze_document_fills_no_document_level_field` catches exactly that. **It is a real tripwire.**

## 4. The named cost — accepted, and it is a CARRY Ocean should not lose

Stated plainly, because the docstring states it a little generously. Under closure-2 a single-account
document that omitted a sibling publishes today's payload, so **the omission is on the object and in
no published payload at all** — not in a document block, and not in the package surface, which is
reached only by a multi-account payload. For the fifteen protected carriers that means Q10's
"surface the omission" is, today, satisfied on the object (where L1-S2's own pins read it) and **not
in anything a consumer is served**.

I accept this as the right trade for this stage, on the stage's own contract: lighting a single-account
payload's document block is a payload-shape change, it needs `ANALYSIS_STAGE_VERSION` bumped in the
same commit and a ceremony, and it would move all fifteen — which a ZERO-MOVEMENT stage may not do.
The alternative measured itself: it turns the gate red on a pinned document.

**But it is a carry, not a closure.** Q10's payload-level surfacing is now owed by S4, and the S4 card
should say so in those words. It is named in `DOCUMENT_LEVEL_FIELDS` and in the clause docstring, so
it is a named gap rather than a silent one — which is the standard this program holds; I am recording
it here so the obligation travels with the composition rather than living only in a docstring.

## 5. COMP-5 — ADJUDICATED: the direction is right, with one condition

I compared both replacements against S2's originals line by line, and I wrote my own replacement text
rather than take the cell's, because the cell's exact text is in its report and not on the branch.

**`test_the_document_carrying_an_omission_publishes_the_same_account_block`.** S2 asserted
`canonical(published["accounts"][0]) == canonical(report_to_dict(analyze_markdown(text)))` — the
NESTED account block is byte-identical to the account seam's. Under the ruled shape there is no nested
block to read. Asserting the WHOLE payload against the same right-hand side is **strictly stronger**:
S2's version permitted document-level keys to sit beside an identical account block, and this one
forbids any added key at all. Adding "`document` and `accounts` absent" pins the ruled shape too.
**No S2 assertion is weakened; one is strengthened.**

**`test_the_omission_is_the_only_document_level_fact_the_stage_fills`.** S2 asserted, on the payload's
`document` block: the omission's exact `label`, `reason` and `posting_count`; `account_count == 1`;
and `period_start`, `period_end`, `boundary_mechanism`, `rollup` all `None`. The replacement must read
those off the object — and **it must keep the content assertion.** A version that merely reads
`document.omissions` and checks that a list is there would drop S2's strongest clause, which is that
the omission is recorded with its printed label and its ratified reason. The text I applied keeps
every one:

    assert [(o.label, o.reason, o.posting_count) for o in document.omissions] == [
        ("Money Market", PRINTED_DORMANCY_DECLARATION, 0)]
    assert len(document.accounts) == 1
    assert document.document_period is None
    assert document.boundary_mechanism is None
    assert document.rollup is None
    assert "document" not in document_report_to_dict(document)

`document_period is None` is the object field that serialises into S2's `period_start` and
`period_end`, and `len(document.accounts) == 1` is what `account_count` was computed from, so the two
translations are exact rather than approximate. The final line is new and pins the ruled shape.

**Adjudication: COMP-5 preserves S2's intent and pins the ruled shape more strongly — CONDITIONAL on
the second test keeping the label / reason / posting-count assertion.** Ocean should apply the text
above (or the cell's, if it carries that assertion); a version without it is a weakening and I do not
confirm it. Measured with the text above in place: the four S2 pin files are **72 passed, 0 failed**.

## 6. The branch floor at `5bc8f37`

| proof | result |
|---|---|
| full default suite | **7,615 passed / 43 skipped**, exit 0, 201 s |
| canonical guards (5) | **255 passed**, exit 0 |
| canonical conformance (7) | **1,270 passed / 40 skipped**, exit 0 |
| the six L1-S3 files | **152 passed**, exit 0 |
| AST surface census | **exit 0** — 46 key-reads swept, 8 seams, publisher **2 of 2** |
| the design's seam census | **exit 0** |
| mutation table | **12 / 12 killed**, exit 0. **M11** — RULE S regains the omission clause, the composition defect itself — killed by `test_a_single_account_document_publishes_todays_payload_whatever_it_carries[omission]`. **M12** — RULE S loses the account count, so a two-account document publishes its first account as the whole document — killed by 10 named tests **and** a red census. Both are one-line exact edits to the real clause; both are faithful. Tree clean after every mutant |
| document seam vs base `4953806` | **232 / 232 byte-identical, `MOVED_TOTAL=0`** (measured at the merged tree, which subsumes the branch-alone run: the branch alone carries no document-level fact for the clause to decide on) |
| privacy — added lines | `hit_count 0`; MONEY / DIGITS / DATES / WORDS **0**; residue 0; exit 0. **raw 82**, all WORDS-class — the cell's row says 81; raw drifts with the tip and both are all-WORDS, so this is a figure to update rather than a finding |
| privacy — messages | **30 commits, `hit_count 0`, all four classes 0**, exit 0 |

## 7. The composition checklist for Ocean — exact edits

Everything below was applied in my throwaway and measured green together.

1. **Merge conflicts, two, both as before.**
   * `docs/moneythumb-replacement/W3_TRACKA_LOG.md` — CONTENT, one hunk, append-only concatenation.
   * `tests/test_corpus_gate_outcomes.py` — CONTENT, comment only; the `WATCHED` line is
     character-identical on both sides. Keep train9's comment.
   * `corpus_gate.py` **auto-merges**; `EXCLUDED_ANALYSIS_CALLERS` is untouched on the branch.
2. **COMP-3** — in `tools/l1_design_reader_probe.py::SEAMS`, `("corpus_gate.py", 1597, …)` becomes
   `("corpus_gate.py", 1608, …)`. Measured, not assumed: before the edit the probe is exit 1 naming
   1597 missing and 1608 undeclared; after it, exit 0.
3. **COMP-4** — `tests/test_l1s2_document_outcome.py`: invert the tripwire, do not delete it.
   `test_this_tree_declares_no_document_fold_yet` becomes
   `test_this_tree_declares_exactly_one_document_fold`, asserting
   `declared_document_folds() == ["telemetry/record.py::classify_document"]`. Pinning it by NAME keeps
   the guard live in both directions — a second fold, a rename, or a silent removal all stay red.
4. **COMP-5** — `tests/test_sibling_omission.py`, the two tests, per §5. **The condition in §5 binds.**
5. **Carried to S4** — Q10's payload-level surfacing for a single-account carrier (§4), and the four
   §6.5 assertions plus MAJOR-3's gate condition and MINOR-10 already carried from the earlier
   reviews.

## 8. What this re-review is not

I did not re-run the 80-registration replay pair, the full 3,380-document sweep, or the wide
677-document probe; §4 of the previous re-review states the reachability argument I accept for them,
and closure-2 narrows rather than widens it — one production hunk, in the wrapper, whose effect on the
232-document cohort I measured directly both ways. Everything else above was measured on this host.
Both throwaway worktrees were created beneath `.claude/worktrees/` and removed; `git worktree list`
carries neither; `mt9-l1s3` was modified by nothing but this file.

**This re-review's own scans**: with this section committed, the branch scan is `hit_count 0` — all
four classes 0, residue 0, exit 0, every raw hit WORDS-class — and the message scan over the branch is
`hit_count 0`, all four classes 0, exit 0.
