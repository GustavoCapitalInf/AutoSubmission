# BATCH9 L1-S1-WRAPPER — independent adversarial review

Reviewer: an independent Opus cell (the same reviewer as the L-1 design's two passes). It did
not write the cell's code, asked the cell nothing, and re-measured every load-bearing claim with
the cell's own instruments and with four of its own. Branch `wave9-l1s1`, base `train9`
`d533e55`, tip `02526e3`, 6 commits, worktree `.claude/worktrees/mt9-l1s1`. Run of record
`discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`; cold cache
`.claude/recovery/webapp_data_train8_cold`, read-only throughout. A base worktree was registered
BENEATH the repo (`.claude/worktrees/mt9-l1s1-rvbase`, detached at `d533e55`) for the cross-tree
comparison and removed afterwards.

**VERDICT: APPROVE WITH FINDINGS — 0 BLOCK / 2 MAJOR / 3 MINOR.**

**Zero movement is confirmed, and it is stronger than measured — it is structural.** The
production diff is purely additive (`analyze_markdown` and `report_to_dict` are byte-identical
to base; the single deletion in the whole branch is one import line), and **no production seam
calls the new function**. Every claim the cell makes reproduced at this base, including the three
it corrected itself on. The two MAJORs are gaps in what the branch *guards*, not in what it does:
a third mutant of the class the cell honestly flagged survives everything, and the prompt-injection
hazard the cell discovered is documented in a comment and pinned by no test while the composed
design still instructs the change that would trigger it.

**S2 and S3 may launch on this base.** Both findings are one-line fixes and neither blocks them;
S2 is *served* by this card's field-set test rather than blocked by it.

---

## 1. Re-measurement

Every row was produced by this reviewer at this base. `tools/l1s1_*` are the cell's instruments
run unchanged; the `REVIEW` rows are this reviewer's own, kept in private scratch and unwired.

### 1.1 The cell's claims, re-run

| claim | claimed | this re-run | agrees |
|---|---|---|---|
| RULE S at the pipeline seam, base -> tip, cohort | 232 documents / 80 registrations, **232/232** byte-identical | 232 / 80, **232/232** | **yes** |
| the account seam | 232/232 | **232/232** | **yes** |
| the integrity flag list AND published order | 232/232 | **232/232** | **yes** |
| ladder outcome unchanged | 232/232 | **232/232** | **yes** |
| documents publishing exactly one account | 232 | **232** | **yes** |
| documents carrying any integrity flag | 15 | **15** | **yes** |
| ... of them carrying a DOCUMENT-scope flag | 3 | **3** | **yes** |
| `ANALYSIS_STAGE_VERSION` not bumped | 16 | **16 at both trees** | **yes** |
| analysis settings key vs base and vs the run of record | identical | `analysis_settings_key(parse_mode="deterministic")` = `7652A5AF…FC093D` at **both** trees, and byte-identical to the cold cache's / run of record's key; the `auto` key identical too | **yes** |
| `registry_fingerprint()` — no registration touched | unchanged | `C7AB510E…43E5` at both trees | **yes** |
| corpus gate | GREEN 105 PASS / 3 WITHHELD / 1 REFUSED | **GREEN — 105 / 3 / 1**, verdicts 1 refused / 3 review / 102 validated / 3 withheld, 691s, **EXIT 0** | **yes** |
| canonical conformance | 1,270 | **1,270 passed**, 40 skipped, **EXIT 0** | **yes** |
| canonical guards | 255 | **255 passed, EXIT 0** | **yes** |
| the cell's own unit file | — | **25 passed** | **yes** |
| privacy scan of added lines | 0 over 1,736 | **hit_count 0** over **1,736** added lines, 3,351 documents read; MONEY / DIGITS / DATES / WORDS all 0; raw 25, all `words_class` | **yes** |
| commit-message scan | 0 over 6 | **hit_count 0** over **6** commits, all classes 0; `refs/original` removed; both cited shas resolve on the branch | **yes** |
| the base suite was RED (inherited) | 1 failed | **confirmed**: `test_every_production_caller_of_the_analysis_is_classified` FAILS at `d533e55` and PASSES at the tip | **yes** |
| W3 append-only | this section appended, no earlier line touched | base blob is a **byte-exact prefix** of the tip blob; **+265 / −0** | **yes** |
| production diff shape | additive | **167 + 21 + 120 + 37 insertions, 1 deletion** — and the one deletion is `from .pipeline import Report` becoming `from .pipeline import DocumentReport, Report` | **yes** |

### 1.2 This reviewer's own measurements

| REVIEW measurement | result |
|---|---|
| **RULE S over a population the cell did NOT pick** — the cell's cohort is chosen by registration coverage; mine by OUTCOME CLASS: every `review` (9), every `withheld` (40), every `deferred` (13), plus 80 `failed` and 80 `validated` outside the cohort — **222 documents**, captured at both trees with `PYTHONHASHSEED=0` | of the 222, **129 are analysable at both trees** and **129/129 are byte-identical** at the seam — and identical on the account seam, the integrity flag list and order, and the ladder outcome. **0 moved.** Combined with the cohort: **361 / 361** |
| ... by outcome class (extension only) | `validated` 80/80, `withheld` 37/37 analysable, `review` 9/9, `failed` 3/3 analysable, `deferred` 0 analysable |
| ... and the document-scope population | my population carries **18** documents with a DOCUMENT-scope flag against the cohort's **3** — a **six-fold** larger killer population for mutant M3, and all 18 byte-identical |
| **is a REFUSAL preserved too?** — the wrapper must not change which exception escapes, or `discovery/runner` classifies the document differently | **93** documents refuse at one or both trees (79 `RuntimeError`, 14 no cached text). **93/93 raise the SAME error class at both trees; 0 differ** |
| every analysed row at the tip went through the DOCUMENT seam | **361/361** `seam == "document"`, `account_count == 1` — the identity is measured through `analyze_document` -> `document_report_to_dict`, not through a fallback |
| **does any production seam call the new function?** (grep of all nine seams the design's census names) | **none.** `analyze_document` / `document_report_to_dict` appear outside `analysis/` only in `corpus_gate.py`'s declaration string and in the cell's own probe. The new path is unreached by production |
| **is the integrity split reachable from any published byte?** | **no.** `split_integrity_flags` is referenced only by `DocumentReport.document_scope_flags()`; `document_report_to_dict` does not reference it (verified against the function's own code object) |
| **the pydantic hazard, verified** | `analysis/extract.py`:222 passes `Statement` as `response_schema`; a pydantic docstring **does** become the schema's `description` (demonstrated on a probe model); `Statement.__doc__` **is None** at the tip, so the schema carries no class-level description and is unchanged; `DocumentReport` is a plain dataclass and no `response_schema` anywhere takes it |
| ... and its real extent | **three** models are reachable from the extraction schema — `Statement`, `Transaction`, `StatementDailyBalance` — and none carries a class docstring today. The 21 field-level descriptions are the deliberate channel and are untouched |
| **the pinned field-set test, mutated** | adding a field (`internal_transfers`, the exact case S4 will bring) makes the pinned set unequal — the assertion detects it |
| **`analyze_document`'s forwarding** | all six parameters, identical names and identical defaults, each forwarded by name — so the corpus-gate declaration's premise (it forwards `sheets`) holds, and geometry, settings and the dispatch hook are not lost either |
| **the third mutant** (§3, MAJOR-1) | **M11 SURVIVES** every fixture and every canonical guard |

---

## 2. Answers to the seven hostile questions

### (1) RULE S "no added key of any kind" — general, or cohort-luck? And does any consumer see `DocumentReport` today?

**General.** The cell's 232 reproduce exactly, and I extended the population by 222 documents it
did not pick — chosen by outcome class rather than by registration, so the shapes the cohort
under-represents are over-represented in mine: every `review` document in the run (notes and a
blocked approval), every `withheld` one (the nulled `ending_balance` and the emptied ADB block),
every `deferred` one, and slices of `failed` and `validated`. **129 of those 222 are analysable
at both trees and all 129 are byte-identical at the seam**, together with the account seam, the
flag list and order, and the ladder outcome. Totals: **361 documents byte-identical, 0 moved.**

Two things make this more than a bigger number. First, my population carries **18** documents
with a document-scope integrity flag against the cohort's 3 — so the mutant the cohort catches
with 3 killers is caught with 18 here, and the tip still drops none of them. Second, a **refusal
is preserved as exactly**: 93 documents raise at one or both trees and **93/93 raise the same
error class**, so the wrapper does not change what `discovery/runner` would record for a document
the parser refuses.

Registrations cannot be extended: the cell's cohort already covers all **80** registrations that
claim any document in the run (the registry's other 3 claim none), so "a registration not in the
cohort" does not exist. The extension is therefore in documents, which is where the risk was.

**No consumer sees `DocumentReport` today.** Grepping all nine seams the design's census names,
plus the whole tree: `analyze_document` and `document_report_to_dict` appear outside `analysis/`
only in `corpus_gate.py`'s declaration string and in the cell's own probe. So RULE S has no seam
to hold at yet — and **that is the intended shape**, stated in `analyze_document`'s own docstring
and in the design's staging: nine payload readers answer the document shape wrongly rather than
refusing it, so no seam may move before S3 teaches them. The new function is dead code in
production and live in tests, which is exactly the "dark" state S3's readers will be in. Calling
it dead code is not a criticism here; shipping it live would have been the defect.

### (2) The integrity scope split: reproduce "the literal reading moves 3 of 232", and show the tip preserves order on exactly those 3

Reproduced, twice over. The design's own payload probe reports `integrity_split_dropped` = **229
of 232**, i.e. **3 move** — the same 3 I measured in the design re-review. At the pipeline seam,
the cell's cohort carries **15** documents with any integrity flag and **3** with a
document-scope flag, and the tip's published flag list and its ORDER are identical to base on
**232 of 232** — so those 3 keep every flag they publish today, in the order they publish it.
My extension raises the document-scope population to **18** and the identity holds on all of them.

The implementation reaches that result by not taking the risk at all: **the split publishes
nothing.** `split_integrity_flags` is a partition into two subsequences, and its only caller is
`DocumentReport.document_scope_flags()`, a view; `document_report_to_dict` never references it.
So the hazard the design flagged — a naive concatenation moving a tuple `corpus_gate.py` pins in
"Published ORDER, not sorted" — is structurally absent at this stage rather than merely avoided,
and it becomes live only in whichever stage first assembles a published block from the split.
That is the right shape, and the cell's M2/M3 mutants prove the byte comparison would see M3 (3
movers) and would *not* see M2 (0), which is the honest half.

### (3) The settings key and the registry fingerprint

| | base `d533e55` | tip `02526e3` | the run of record / cold cache |
|---|---|---|---|
| `ANALYSIS_STAGE_VERSION` | 16 | 16 | 16 |
| `analysis_settings_key(parse_mode="deterministic")` | `7652A5AF…FC093D` | `7652A5AF…FC093D` | `7652A5AF…FC093D` |
| `analysis_settings_key(parse_mode="auto")` | `14DE0339…3F9B` | `14DE0339…3F9B` | — |
| `registry_fingerprint()` | `C7AB510E…43E5` | `C7AB510E…43E5` | — |

Byte-identical on every row. **No cache entry is invalidated and no bump is owed**, and the
`deterministic` key matching the cold cache's exactly is the same statement in the form the
archive can check. `registry_fingerprint()` unchanged confirms no registration was touched, which
is also visible in the diff: no file under `analysis/` other than `schema.py`, `pipeline.py` and
`serialization.py` is modified, and none of the three registers anything.

### (4) The pydantic-docstring finding

**Verified, and the cell's refusal to follow the design was correct.** `analysis/extract.py`:222
passes `Statement` itself as the extraction call's `response_schema`. Pydantic publishes a
model's docstring as its JSON-schema `description`, which I demonstrated on a throwaway model
rather than assumed. So a docstring on `Statement` is prompt text sent to the extractor, and the
design's instruction — *"what changes is its docstring"* — would have put prose addressed to
implementers into a model's instructions.

`Statement.__doc__` is `None` at the tip, the schema carries no class-level `description`, and
the diff to `schema.py` is a comment only, so **the schema the extractor receives is unchanged**.
`DocumentReport` is a plain dataclass, is passed to nothing as a schema, and `response_schema`
occurs at exactly one call site — so its docstring reaches no prompt.

One correction to the finding's scope, and it matters for the fix: the hazard is not
`Statement`'s alone. **Three** models are reachable from that schema — `Statement`, `Transaction`
and `StatementDailyBalance` — and a docstring on any of them becomes a nested `description` in
the same payload. None carries one today. See MAJOR-2 for what is missing.

### (5) The two uncohort-killed mutants, and a third

I ran the constructed fixtures: **25 pass**, and each of M2's and M4's named killers is a real
assertion over a real shape (`test_the_published_account_block_keeps_every_flag_in_published_order`
pins the published list against an interleaved input; `test_analyze_document_fills_no_document_level_field`
pins the seam's document fields empty, and the sibling test even asserts the account's printed
period string does not occur anywhere in the canonicalised document block). The cell's declaration
that these two move 0 of 232 is accurate and is stated up front in the harness itself
(`expect_cohort_movers="none — the fixture is the killer"`).

**A third mutant of the same class exists, and nothing kills it.** See MAJOR-1.

### (6) The pinned field-set test — does it fail on an added field, and does it block S2?

**It fails on an added field.** Adding `internal_transfers` — the exact field S4 will bring, and
the one the cell deliberately left out — makes the pinned set unequal and the assertion fire.

**S2 is served by this test, not blocked by it.** `omissions` is already a field of
`DocumentReport` and already a clause of RULE S (`not document.omissions`), and
`SiblingOmission` is already defined with the `{label, reason, posting_count}` shape S2 needs.
S2 *populates* that field at the three skip sites; it adds none. The test's whole purpose is the
case S4 will hit, and it will hit it correctly: a field added without a RULE S clause becomes a
red test rather than a document that carries a fact no payload shows.

### (7) Ownership, declarations, W3, messages, scans

**`corpus_gate.py` is outside the card's stated ownership**, which lists `analysis/schema.py`,
`analysis/pipeline.py`, `analysis/serialization.py`, their tests, `tools/l1s1_*.py` and W3. The
cell disclosed the departure and the change is declarations only — two lists neither of which the
gate's verdict logic reads. It splits into two parts and both check out:

* adding `("analysis/pipeline.py", "analyze_document")` to `ANALYSIS_CALL_SITES` is **required**,
  not optional: `tests/test_corpus_gate_outcomes.py` fails on any production caller of the
  analysis that is neither declared nor excused, and declaring rather than excusing it is the
  stronger choice — the register then asserts that the document entry point forwards `sheets`,
  which I verified it does (all six parameters, by name, with identical defaults);
* the four `EXCLUDED_ANALYSIS_CALLERS` entries: one is the cell's own probe, and **three are the
  design cell's instruments, which made that test RED at this card's base**. I confirmed the red
  directly — `test_every_production_caller_of_the_analysis_is_classified` fails at `d533e55` and
  passes at `02526e3`. Ocean has lifted the same three onto `train9` at `473be2c` ("the entries
  lifted verbatim from wave9-l1s1 so its merge stays clean"), which is not an ancestor of this
  card's base; `train9` now carries 3, the base carries 0 and this branch carries 4, so the
  compose adds one entry and re-states three identically.

**W3** is append-only: the base blob is a byte-exact prefix of the tip blob, `+265 / −0`. But see
MINOR-1 for its heading level. **Messages**: 6 commits, scan 0, `refs/original` removed after the
`--msg-filter` reword, and both shas the record cites resolve on the branch. **Scans**: privacy
`hit_count 0` over 1,736 added lines with every class 0; message scan 0 over 6.

---

## 3. Findings

### MAJOR-1 — a third mutant of the cohort-and-fixture-invisible class survives everything: `DOCUMENT_SCOPE_FLAGS` has its membership *predicate* pinned but not its *set*

The cell names two mutants its archive-scale byte comparison cannot see and says so plainly. The
hostile question is whether a mutant exists that the fixtures miss as well. One does.

**M11: add an account-scope flag to `DOCUMENT_SCOPE_FLAGS`.** I used
`summary_math_inconsistent` — a ledger-arithmetic flag about one account if ever there was one,
raised by `analysis/pipeline.py`, and named nowhere in the fixture file.

| target | unmutated | mutated |
|---|---|---|
| `tests/test_document_report.py` (the 25 fixtures) | 25 passed | **25 passed** |
| `tests/test_corpus_gate_outcomes.py` | 24 passed | **24 passed** |
| the 5 canonical guards | — | **255 passed** |
| the 232-document byte comparison | — | **0 movers, structurally** |

**M11 survives.** The tree was restored byte-for-byte and came back clean.

Why nothing catches it: the split publishes no byte at this stage, so no comparison at any scale
can see it; `test_split_integrity_flags_partitions_without_reordering` asserts against a fixed
`INTERLEAVED_FLAGS` list that does not contain the added flag; and
`test_every_document_scope_flag_is_one_the_pipeline_actually_raises` asserts only
`DOCUMENT_SCOPE_FLAGS <= raised` and `!= raised` — both still true of a set with an extra real
flag in it. Seven of the fifteen flags the pipeline raises can be added this way undetected
(`conflicting_statement_summaries`, `credit_count_mismatch`, `debit_count_mismatch`,
`debit_detail_coverage_mismatch`, `not_a_formal_statement`, `summary_math_inconsistent`,
`transaction_detail_not_corporate_reliable`).

**Why it matters, given it moves nothing today.** It is harmless at S1 precisely because the view
is unread — and S3 is where readers start consuming `document_scope_flags()`. From then on, a
mutation of this kind silently promotes one account's ledger failure to a fact about the whole
PDF, which is the exact scope error the partition exists to prevent, on a document carrying
several accounts where "which account failed" is the question.

**The fix is one line, and the cell already invented it.** `test_every_document_level_field_is_a_clause_of_rule_s`
pins a *set* by equality with a message telling the next implementer what to do. The scope table
deserves the same treatment: assert `DOCUMENT_SCOPE_FLAGS == {the five}` beside the two
predicates that are there now. Owed by this card, not by S3, because this card owns the set.

### MAJOR-2 — the prompt-injection hazard is guarded by a comment, while the composed design still instructs the change that triggers it

This is the cell's own finding and it is a good one: a docstring on `Statement` is not
documentation, it is text sent to the extraction model. The cell refused the design's instruction
and wrote a comment explaining why. What is missing is everything that would keep the property
true:

1. **No test pins it.** Nothing in `tests/` asserts `Statement.__doc__ is None`, or that the
   extraction schema carries no class-level `description`. The property currently rests on the
   next implementer reading a comment.
2. **The instruction that would break it is still live.** The composed design on `train9` says
   the docstring changes in three places — §1.1 (*"What changes is its docstring"*), §5's
   `analysis/schema.py` row (*"only its docstring says 'one account'"*), and §7's S1 row
   (*"docstring of `analysis/schema.py`"*). A cell reading the design as its card — which is what
   the staging tells it to do — is being told to do the harmful thing.
3. **The hazard is wider than the comment says.** `Transaction` and `StatementDailyBalance` are
   also reachable from the same schema and would also publish a class docstring as a nested
   `description`. The comment sits only on `Statement`.

Nothing published moves today, which is why this is MAJOR and not BLOCK. But the discovery is
this card's, the fix is small, and the window in which it is cheap is now: a test over all three
models, and a correction to the design's three mentions so the next cell is not instructed into
the defect this one found.

### MINOR-1 — the W3 record is an H2 and nests under another cell's section

Every prior cell's record is a top-level `# §NAME` heading — `# §CPDECL`, `# §RAISEPRIV5`,
`# §PNC9`, `# §COMMSEC9`, `# §L1DESIGN`. This card's is **`## §L1S1`**, an H2, appended after
`# §L1DESIGN`. Structurally the L1-S1 record is therefore a subsection of the *design cell's*
section, so anything that splits the log by top-level heading attributes this card's work to
`§L1DESIGN`. (The design cell's own `## §L1DESIGN.2` is a correct H2 — it is that cell extending
its own section.) The contract for this card was a `# §L1S1` heading. Append-only is not
violated and no earlier line is touched; the fix is one character.

### MINOR-2 — a deregistered worktree directory survives on disk

`.claude/worktrees/mt9-l1s1-base` remains as a full tree copy after `git worktree remove` failed
against a OneDrive handle. Disclosed by the cell. It is inside the gitignored `.claude/`, the main
repo's status is clean, and `git worktree list` does not carry it, so there is no repository
effect — it is disk hygiene only.

**I reproduced the failure and it is the host, not the cell.** Removing my own review worktree
hit the identical error (`failed to delete … Permission denied`, on both the tree and its
`.git/worktrees/` metadata), which deregistered it while leaving the directory behind — exactly
the state the cell reported. **A plain retry cleared it on the first attempt**, which is the
standing rule for OneDrive `PermissionError`s applied to `worktree remove`. So the residue is
transient-lock debris and the remedy is one retry; the cell's own leftover is left in place for
Ocean to sweep rather than removed by a reviewer.

### MINOR-3 — `corpus_gate.py` is outside the card's stated ownership

Disclosed, declarations only, and justified on both halves (§2.7). Recorded as a departure rather
than a defect because the card's ownership list did not anticipate that adding a production
caller of the analysis obliges a declaration, and because three of the four entries repair an
inherited red rather than serving this card. Ocean's `473be2c` already carries those three on
`train9`, so the note for compose is simply that the merge adds one entry and re-states three.

---

## 4. Proof floor, re-run by this reviewer

| proof | result | exit |
|---|---|---:|
| corpus gate at the tip | **GREEN — 105 PASS / 3 WITHHELD / 1 REFUSED**; verdicts 1 refused / 3 review / 102 validated / 3 withheld; 109 pinned, 0 exclusions | **0** |
| canonical conformance (7 files) | **1,270 passed**, 40 skipped | **0** |
| canonical guards (5 files) | **255 passed** | **0** |
| the cell's unit file | **25 passed** | **0** |
| the caller-register test at BASE | **1 failed** — the inherited red the cell fixed | 1 |
| the same at the tip | **24 passed** | **0** |
| RULE S at the pipeline seam, base -> tip, `PYTHONHASHSEED=0` | **361 / 361** byte-identical (232 cohort + 129 of my 222); account seam, flag list and order, ladder outcome all 361/361; 0 movers | **0** |
| refusals preserved | **93 / 93** the same error class at both trees | — |
| settings key and registry fingerprint | identical at both trees; the `deterministic` key equals the run of record's | — |
| privacy scan of the branch's added lines | **hit_count 0** over 1,736 added lines | **0** |
| commit-message scan | **hit_count 0** over 6 commits | **0** |
| M11, the third mutant | **SURVIVES**; tree restored byte-for-byte and clean | — |
| privacy scan of THIS review's added lines vs the whole population | **hit_count 0** over **352** added lines; MONEY / DIGITS / DATES / WORDS all 0; raw 7, all `words_class` | **0** |
| commit-message scan of this review's commit | **hit_count 0**, all classes 0, clean on the first pass | **0** |
| the base worktree this review registered | `.claude/worktrees/mt9-l1s1-rvbase`, detached at `d533e55`, beneath the repo, **removed after the run** | — |

---

## 5. Explicit answers

* **Zero movement confirmed — every registration, every document, byte-identical at the seam?**
  **Yes.** The cell's own evidence is 2,669 documents replayed at both trees with 0 per-sha
  differences and an archive sweep whose 66 findings are all attributed by sha to compositions
  already on `train9` and reproduce at the base tree. My independent evidence is 361 documents
  byte-identical at the pipeline seam across five outcome classes, 93 refusals preserved by error
  class, and the structural fact that carries the rest: `analyze_markdown` and `report_to_dict`
  are unchanged and **no production seam calls the new function**, so production's executed path
  at this tree is the base's path.
* **Settings key identical?** **Yes** — at both trees and equal to the run of record's
  `7652A5AF…FC093D`. Stage version 16, unbumped; registry fingerprint unchanged. No cache entry
  invalidated, no bump owed.
* **Privacy 0?** **Yes** — 0 over 1,736 added lines, every class 0; messages 0 over 6.
* **May S2 and S3 launch on this base?** **Yes.** S2 is served by the field-set test rather than
  blocked by it (`omissions` already exists and already has its RULE S clause). S3's ordering
  premise is intact and now verified: no seam has moved, and the readers are still untaught.
  Carry MAJOR-1 into whichever card next touches `DOCUMENT_SCOPE_FLAGS` — or better, close it
  here, since this card owns the set — and carry MAJOR-2 as a correction to the design plus a
  test over the three schema models before any cell is told again to change a docstring.
