# PHASE2 P20-SURFACES — independent adversarial review

```
BRANCH        wave20-surfaces @ ed269f4   (reviewed detached in .claude/worktrees/rev20-surfaces)
BASE          train10 @ bea06bc
DIFF          git diff bea06bc..ed269f4   (11 files, +857 / -27)
REVIEWER      independent agent; did not write this code
HOST          Python 3.14.5 (CI pins 3.12); Node v24 present
VERDICT       BLOCK
```

Everything below was reproduced by this reviewer in the review worktree. The tree was clean
(`git status --porcelain` empty) before and after every mutant; a throwaway base worktree at
`bea06bc` was created for the base replay and removed (`git worktree remove --force`) afterwards.

---

## 1. Claim-by-claim (claimed → measured)

| # | cell's claim (W3 `§P20SURFACES`) | measured | verdict |
|---|---|---|---|
| 1 | `confidenceFrom` / `packageConfidence` deleted; no number, no percentage survives | `grep -rni confidence webapp/` at `ed269f4` → **2 hits, both non-executable comments** (`app.js:595,602`); at `bea06bc` → 14 hits (12 `app.js`, 2 `index.html`) | **confirmed** |
| 2 | `validationLabel` / `packageValidationLabel` return words only | read + executed under Node via the cell's own tests; 15/15 pass; no digit in any output | **confirmed** |
| 3 | `extractor_model` reads the first line and only the first line | reproduced: header on line 2 → `None`; no header → `None`; empty model field → `None`; layout suffix returned whole | **confirmed for well-formed headers; DEFEATED by a hostile `source_file` — BLOCK-1** |
| 4 | non-native / absent provenance → "the document fails closed … in deterministic mode" | reproduced: `ParserCrashError` in `parse_mode="deterministic"` | **confirmed for deterministic only**; in the webapp's DEFAULT `parse_mode="auto"` it is **fail-open — BLOCK-2** |
| 5 | the refusal names `q3_class_requires_native_provenance` | reproduced: the token exists only in the raised message, which `_guarded` discards; the surfaced record is `('member_statement_rollup','parse','ValueError')` and `_failure_reason → parser_exception` | **not recorded anywhere a reader can see — MAJOR-2** |
| 6 | the other three ratified classes are not gated | mutant M4 (gate extended to `printed_dormancy_declaration`) killed by 2 tests | **confirmed** |
| 7 | cohort replay over the six omission-publishing registrations proves nothing else moves | the replay calls `analyze_markdown`, which never opens the omission collector; **the gate never executes during a replay** | **the evidence cannot observe the gate — MAJOR-1** |
| 8 | "128/128 replayed, newly validated 0, preserved 125/125, regressions 0, identical at base and closure" | reproduced at base `bea06bc` and tip `ed269f4`: 128 rows, `validated→validated` 125, `review→review` 2, `withheld→withheld` 1, `identical` 105, `changed` 23, `direction: unchanged` 128/128; **0 differences between the two runs' row records** | **confirmed** |
| 9 | "the 23 … every changed path is under `document.*`" | **false.** 21 of 23 are `document.*`-only (10 or 13 leaves). `7C7956EB5E93DB1D` (1,345 leaves) and `E38FA786106F752E` (1,347) — both on the card's own guardian_cu list — change `accounts`, `classifications`, `detection`, `escalated`, `integrity`, `metrics`, `model_used`, `quality`, `reconciliation`, `statement` (1,332 / 1,334 leaves outside `document.*`). Identical at base and tip. | **mis-stated — MAJOR-3** |
| 10 | (implicit) the replay is a fidelity pass | `--expect-identical` exits **3** at base AND at tip, on the same 23 shas. The W3 reports the run without its exit code. | **exit code omitted — folded into MAJOR-3** |
| 11 | the `tests/l1s4_pages.py` header stamp is "transparent to every existing assertion" | reverting the stamp fails exactly the 4 tests the cell names | **confirmed** — but the underlying behaviour change reaches production callers that pass headerless markdown (**MAJOR-4**) |
| 12 | mutation table: 7 mutants, all killed | 6 of the 7 re-applied by this reviewer plus 2 of my own; **all 8 killed**, tree restored clean | **confirmed** |
| 13 | 5 canonical guards 255 passed | reproduced: **255 passed, exit 0** | **confirmed** |
| 14 | OQ11 banners prepended, bodies untouched | diff read: both banners present, no body line changed | **confirmed** (one wording nit, MINOR-6) |
| 15 | `newly validated = 0` | 0 at base and tip | **confirmed** |

Provenance census I ran independently against the read-only cold cache
(`.claude/recovery/webapp_data_train9_cold`, `mode=ro`) and the run of record's `rows.csv`:

| population | extractor-model tokens |
|---|---|
| the six omission-publishing registrations (132 rows) | `native-pdf-text` 122 · `native-pdf-text+printed-rows` 10 · nothing else |
| whole run (3,506 rows) | `native-pdf-text` 2,871 · `+wells` 234 · `local-tesseract-ocr` 179 · `+printed-rows` 83 · `+navy-federal-layout` 48 · `+first-citizens-layout` 36 · `+woodforest-columns` 19 · `+desjardins-layout` 6 · no-artifact 17 · no-document 13 |

So the gate moves **nothing** on the run of record today. Every finding below is about what the
gate does on inputs the run of record does not contain — which is the whole point of the gate.

---

## 2. Findings

### BLOCK-1 — an OCR-fed document reaches the Q3 admission by injecting the header into `source_file`

**Where:** `analysis/provenance.py:41-43` (`_HEADER_RE`), consumed at
`analysis/sibling_omission.py:536-545`.

```
_HEADER_RE = re.compile(
    r"\A<!--\s*source:.*?\|\s*pages:.*?\|\s*model:\s*(?P<model>.*?)\s*\|\s*empty:.*?-->"
)
```

`source:` is matched with `.*?`, deliberately, "because `source_file` is operator/OCR supplied text
and is not guaranteed to be free of the pipe character" (the module's own comment,
`analysis/provenance.py:33-40`). That choice lets the **source field supply the model**: a
`source_file` containing `| pages: 1 | model: native-pdf-text | empty: 0 -->` closes the header
early, and the reader hands back `native-pdf-text` for a document whose real model field says
`local-tesseract-ocr`.

`source_file` is the uploaded multipart filename, unsanitised: `webapp/app.py:1907-1927`
(`f.filename` → `_enqueue_job`) → `webapp/worker.py:323,333` (`parse_statement(source_file=filename)`)
→ `ocr/document.py:38-41` (raw f-string interpolation into the header). `webapp/app.py:237` states
in its own words that "filename is attacker-supplied". `webapp/artifact_cache.py:902-906` **re-stamps
`source_file` from the current request even on a cache hit** ("the markdown header must name the file
being processed now"), so the injection also works against already-cached OCR bytes.

**Reproduction** (review worktree, `PYTHONPATH=$PWD`):

```python
from ocr.document import StatementMarkdown
from analysis.provenance import extractor_model
from analysis.pipeline import analyze_document
from tests.l1s4_pages import document, idle_account, posting_account

body = document([idle_account(), posting_account()]).split("\n\n", 1)[1]
evil = "statement.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
md = StatementMarkdown(source_file=evil, model="local-tesseract-ocr", pages=[body]).to_markdown()
print(extractor_model(md))                                   # -> 'native-pdf-text'
print([o.reason for o in analyze_document(md, parse_mode="deterministic").omissions])
# -> ['printed_pair_coincides_and_no_row_printed']    and classify_outcome -> 'validated'
```

Measured output:

```
line1: <!-- source: statement.pdf | pages: 1 | model: native-pdf-text | empty: 0 --> | pages: 1 | model: local-tesseract-ocr | empty: 0 -->
extractor_model: 'native-pdf-text'
omissions: ['printed_pair_coincides_and_no_row_printed']
```

This is exactly the leakage the umbrella review plan names ("Q3 OCR leakage"). The cell's W3 discloses
only the `OCR_MODEL=native-pdf-text` env spoof and defers it to P20-SEAM's reserved-prefix refusal —
that refusal is on the **model** token and does not address a filename that carries a whole header.
Even if P20-SEAM closes the `source_file` charset at the writer, this cell composes **last**
(B2 → B1 → A → C → D) and must not ship a provenance reader whose core property depends on an
unlanded cell; the module's own justification ("a gate keyed on 'found the header somewhere' could be
satisfied by a header a page printed as ordinary text, and a gate keyed on line one cannot") is
violated by a header a *filename* printed.

**Fix I would accept** — bound the model field to a closed token charset so no other field can supply
it, and pin it:

```python
_HEADER_RE = re.compile(
    r"\A<!--\s*source:(?P<source>[^\n]*?)\|\s*pages:\s*\d+\s*"
    r"\|\s*model:\s*(?P<model>[^|<>\s]*)\s*\|\s*empty:\s*\d+\s*-->\s*$"
)
```

(or, equivalently, parse the fields from the RIGHT: `empty:` is the last field and `model:` the one
before it). Plus a hostile test in `tests/test_q3_native_only.py`: a `StatementMarkdown` whose
`source_file` carries `| pages: 1 | model: native-pdf-text | empty: 0 -->` and whose `model` is
`local-tesseract-ocr` must yield `extractor_model(...) != "native-pdf-text"` and must fail closed —
and the same for a `source_file` containing `-->`, a newline, `<`, `>`.

---

### BLOCK-2 — the refusal is fail-OPEN in the webapp's default `parse_mode="auto"`, and drops the sibling silently

**Where:** `analysis/pipeline.py:911-919`. Only `parse_mode == "deterministic"` raises on a
`parser_exception` dispatch; every other mode falls through to
`stmt = normalize_statement(extract_statement(markdown, settings=settings, model=model_used))` — the
hosted-model extraction branch. `webapp/app.py:1897` defaults `parse_mode` to `"auto"`.

**Reproduction** (hosted call replaced by a local sentinel — nothing left this host):

```
mode=deterministic  model=native-pdf-text      -> ok, omissions=['printed_pair_coincides_and_no_row_printed']
mode=deterministic  model=local-tesseract-ocr  -> ParserCrashError
mode=auto           model=native-pdf-text      -> ok, omissions=['printed_pair_coincides_and_no_row_printed']
mode=auto           model=local-tesseract-ocr  -> HOSTED EXTRACTION BRANCH REACHED (model='gemini-3.5-flash-lite')
```

And when the fallthrough SUCCEEDS (stand-in returns the statement the native twin published):

```
native/deterministic:              accounts=1 omissions=['printed_pair_coincides_and_no_row_printed']
ocr/auto (fallthrough succeeded):  accounts=1 omissions=[]
```

Three consequences, all measured:

1. A **provenance-policy refusal starts an extractor escalation.** Phase 2.0's stated objective is to
   "make 'try extractors until something balances' architecturally impossible"
   (`PHASE2-0-SAFETY.md` §Objective); `PHASE2-RULES.md` §Gustavo's rulings states the governing
   invariant. This cell adds a refusal that, on the product's default path, does the opposite.
2. It reaches a **hosted model call** (`gemini-3.5-flash-lite` measured) on a document refused for OCR
   provenance — against the spirit of OQ3 ("a local extractor failure must never silently trigger a
   remote or paid service") and of `PHASE2-RULES.md` "$0 vendor stays".
3. If that extraction succeeds the document publishes **one account with `omissions == []`** — no
   `sibling_account_omission_detected`, no `completeness: partial`. That is the L-1 defect
   `analysis/sibling_omission.py:1-25` exists to prevent ("never publish one account and silently
   drop another"), reached through a gate whose whole purpose is safety.

I checked whether this asymmetry is new: it is not, for `unclaimed` —

```
deterministic  RuntimeError  no deterministic parser matched this statement
auto           <sentinel>    extract_statement reached
```

— so the mode asymmetry is a pre-existing property of `analysis/pipeline.py:911-919`, and
`SectionLedger.refuse()`'s "return `None`" shape would land in the same place. What is **new** is the
population routed into it: before this branch, no non-native member statement took that path; after
it, every one does, plus every headerless one.

**Fix I would accept** (any one of):
* raise the refusal where `parse_mode` is visible so it is unconditional — e.g. have the gate record
  the refusal on the collector and let `analyze_document` refuse the DOCUMENT in every mode, rather
  than raising inside `parse` where the mode decides what happens next; or
* keep the seam, and add an explicit, tested clause in `analysis/pipeline.py` that a
  `parser_exception` carrying the Q3 provenance refusal never reaches `extract_statement` in any mode
  (with the reason surfaced, see MAJOR-2); or
* if Ocean judges the auto-mode hole to be out of this cell's ownership, then the cell must at minimum
  MEASURE and DISCLOSE it in `§P20SURFACES`, name the owning cell, and pin the current behaviour with
  a test — a Phase-2.0 safety card may not leave its own fail-closed claim true in one mode and false
  in the product's default mode without saying so.

---

### MAJOR-1 — the cohort-replay evidence cannot observe the gate at all

**Where:** `tools/cohort_replay.py:159-167` calls `analyze_markdown`;
`analysis/pipeline.py:1163-1164` opens `_collecting_omissions(markdown)` inside `analyze_document`
only; `analysis/sibling_omission.py:544-545` returns at `sink is None or not omissions` before the
gate loop.

**Reproduction:**

```
analyze_markdown(local-tesseract-ocr Q3 doc): NO RAISE -> gate not reached
analyze_document(local-tesseract-ocr Q3 doc): ParserCrashError
```

Therefore the headline correctness evidence — "the six omission-publishing registrations, 128
replayed, identical at base and closure" — is byte-identical **by construction**, and would remain so
if the gate refused every document or if it did not exist. The same is true of the Phase-2.0 proof
floor's "the cohort replay proves the OFFLINE partition byte-identical" for any change at this seam.
(Production is unaffected: `discovery/runner.py:503`, `webapp/worker.py:186`, `batch.py:260`,
`analyze.py:188` and `corpus_gate.py:1738` all call `analyze_document`.)

**Fix I would accept:** state the limitation in `§P20SURFACES` (the replay is a no-movement proof for
the OTHER surfaces, not a proof of the gate) **and** add a document-level replay of the eight named
guardian_cu shas through `analyze_document` — `tools/l1s4_document_replay.py` already does exactly
that (`tools/l1s4_document_replay.py:59-68`) — reporting outcome + omission reasons per sha at base
and tip.

---

### MAJOR-2 — the refusal is filed as a parser crash, and its reason token is recorded nowhere

**Where:** `analysis/sibling_omission.py:537-545` raises `ValueError`;
`analysis/parser_registry.py:839-855` (`_guarded`) stores `ParserFailure(id, stage, type(exc).__name__)`
— class name only, by the module's own privacy discipline (`analysis/parser_registry.py:822-836`).

**Reproduction:**

```
exception: ParserCrashError
dispatch.outcome: parser_exception
dispatch.exceptions: [('member_statement_rollup', 'parse', 'ValueError')]
_failure_reason -> parser_exception
message contains token: False
```

Two problems:

1. **Vocabulary honesty.** `ParserCrashError`'s own docstring (`analysis/parser_registry.py:127-140`)
   reserves this outcome for "our own code broke on a document we already claim to know" and says
   that finding and "no parser matched" "must never be confused in a triage queue". A *policy* refusal
   is now a third thing wearing the crash label. Discovery rows will carry
   `dispatch_outcome=parser_exception`, `parser_exceptions ≥ 1`, `outcome_class=failed`,
   `outcome_reason=parser_exception` for a document that is not broken. No new vocabulary is
   introduced and no count moves on the run of record today (all 132 rows of the six registrations
   are `native-pdf-text*`), so this is a latent, not an active, telemetry defect — but it is exactly
   the kind that becomes active the moment Phase 2.1 feeds OCR text to these readers.
2. **The card's own requirement is unmet.** `P20-SURFACES.md:50-52`: record
   `q3_class_requires_native_provenance` "in the closed omission-refusal vocabulary if one exists,
   else as the `SiblingOmission` diagnostics note — name what you did." What was done is neither: the
   token lives in a message that is provably discarded. The cell's test
   `tests/test_q3_native_only.py:180-192` asserts it *below* `_guarded`, i.e. it pins a string that
   nothing in production keeps. The W3 calls this "satisfying the card's requirement"; it does not.

**Fix I would accept:** carry the refusal as data, not as a message — e.g. a dedicated
`Q3ProvenanceRefused(ValueError)` subclass so `ParserFailure.exception` records
`Q3ProvenanceRefused` (still a class name, still no document text), plus a `_failure_reason` mapping
to a distinct reason token so `rows.csv` can tell a policy refusal from a crash. If Ocean prefers not
to widen the reason vocabulary in this cell, then the honest minimum is to say plainly in
`§P20SURFACES` that the refusal is indistinguishable from a crash in every reader, and to name the
cell that will separate them.

---

### MAJOR-3 — the W3's characterisation of the 23 replay deltas is wrong, and the exit code is missing

**Claimed:** "the 23 predate this card: every changed path is under `document.*`".

**Measured** (`--json` from both runs, leaf paths only):

| sha16 | changed leaves | roots | leaves outside `document.*` |
|---|---|---|---|
| 21 shas | 10 or 13 | `document` | 0 |
| `7C7956EB5E93DB1D` | 1,345 | `accounts`, `classifications`, `detection`, `document`, `escalated`, `integrity`, `metrics`, `model_used`, `quality`, `reconciliation`, `statement` | **1,332** |
| `E38FA786106F752E` | 1,347 | same | **1,334** |

Both are on the card's own list of the 8 guardian_cu documents; both are `validated → validated`,
`member_statement_rollup → member_statement_rollup`, `approved → approved`, and **identical at base
`bea06bc` and tip `ed269f4`** (my A-vs-B comparison of `before/after/payload/direction/after_reason/
after_parser/changed_paths` across all 128 rows: **0 differences**). So this is a base-fidelity
property of the replay tool against the run of record — the tool compares an ACCOUNT payload
(`analyze_markdown → report_to_dict`) with the run's DOCUMENT payload — not a regression from this
branch.

Also: `--expect-identical` exits **3** at base and **3** at tip
(`BASELINE FIDELITY FAILED on 23 shas`, runtimes 242 s / 233 s). The W3 reports the replay's counts
without its exit code; `BATCH9-RULES.md` §Proof floor requires "exit codes verbatim".

**Fix I would accept:** correct the sentence to "21 of 23 are `document.*`-only; 2 (`7C7956EB5E93DB1D`,
`E38FA786106F752E`) are whole-payload deltas caused by the replay tool comparing an account payload
with a document payload", state `EXIT=3` at both trees, and say plainly that `--expect-identical` does
not pass at this base for this cohort.

---

### MAJOR-4 — the out-of-ownership fixture stamp masks a live behaviour change for headerless production callers

**Where:** `tests/l1s4_pages.py:140-215` (the `_NATIVE_HEADER` prepend).

**Reproduction:** revert the prepend, run the L1-S4 pins:

```
FAILED tests/test_l1s4_publisher.py::test_an_idle_sibling_is_omitted_on_printed_evidence_and_the_account_still_validates
FAILED tests/test_l1s4_publisher.py::test_the_omitted_sections_label_is_the_printed_role_and_never_a_number
FAILED tests/test_l1s4_transfers.py::test_a_package_of_todays_payloads_is_untouched_by_any_of_this
FAILED tests/test_l1s4_transfers.py::test_the_gate_answers_a_single_account_payload_exactly_as_it_always_did
4 failed, 109 passed
```

(`ParserCrashError: deterministic parser crashed: member_statement_rollup (parse: ValueError)`.)

The cell disclosed the edit. What it did not do is answer the question the edit raises: **do production
callers ever present these texts headerless?** They do:

* `analyze.py:186-188` — `open(args.markdown).read()` → `analyze_document(markdown)`; the CLI's own
  help calls its argument "Path to the OCR markdown file", and a hand-saved or post-stripped markdown
  carries no header.
* `batch.py:59-75, 245-262` — `_read_source` returns `path.read_text()` verbatim for a non-`.pdf`
  input, and the call site's own comment declares "this CLI … is a production caller (W3 §WIRING W4)".

On both, every Q3-class document now fails closed where it previously validated. The direction is
safe, but it is unmeasured, untested and unreported ladder movement on a self-declared production
caller, in a card whose contract is "previously validated preserved = all, payload identical".

**Fix I would accept:** a paragraph in `§P20SURFACES` naming `analyze.py` and `batch.py`'s `.md` path
as the headerless callers and stating the fail-closed consequence, plus one test that pins it (a
headerless Q3 document through `analyze_document` refuses — the cell already has
`test_header_removed_refuses_and_fails_closed`; what is missing is the statement that this is a
production path, not only a fixture shape).

---

### MINOR findings

| # | finding | file:line | fix |
|---|---|---|---|
| M-1 | `startswith("native-pdf-text")` admits `native-pdf-textXYZ` (measured: admitted, `printed_pair_coincides_and_no_row_printed`). The only tokens `ocr/native_text.py` writes are the bare token and `+suffix` forms. | `analysis/sibling_omission.py:139, 541` | `model == PREFIX or model.startswith(PREFIX + "+")`, and add the mutant to the table. (`telemetry/record.py:127` uses the same loose form — precedent, not justification.) |
| M-2 | the bare-score guard runs over `app.js` only (module-level `APP_JS`), not over `STATIC_JS_FILES` as the card words it. No hole today (`webapp/static/` holds one `.js`). | `tests/test_webapp_confidence_label.py:76-83` | parametrize over `STATIC_JS_FILES` like the sibling tests. |
| M-3 | the guard is text-shaped, not AST-shaped: it misses `return 94.0;`, `return 0.94;`, `const S = 94; return S;`, `return 100 - 6;`. The card said "AST/text guard". | same file, `_BARE_SCORE_RETURN_RE` | either widen the pattern to numeric literals generally in a `return`, or say in the docstring which mutants it does not kill. |
| M-4 | `validationLabel` drops `quality.transaction_detail_reliable` from the decision and renders `corporate_use === "approved"` as **"Validated"** — a stronger word than the payload's own `approved`, and not the platform's `classify_outcome` verdict. Cosmetically, `packageValidationLabel` renders `labelize(totals.decision)` lowercase ("approved") beside it. | `webapp/static/app.js:604-609, 613-620` | render the payload's own word ("Approved") rather than promoting it to the outcome-class word, or derive from the document outcome as OQ9 permits — either way, one vocabulary across the two labels. |
| M-5 | `.confidence-value` → `.validation-value` renames a CSS rule no element uses (dead at base and at tip). | `webapp/templates/index.html:460` | delete the rule, or apply the class to `#validationValue`. |
| M-6 | the Nanonets banner says "on the same grounds it superseded the PaddleOCR design **below**" — the PaddleOCR design is a different file. | `docs/superpowers/specs/2026-07-22-…:2-5` | name the file. |
| M-7 | the card's own instrument line `--folder guardian_cu` selects **0 rows** on this run of record (`folder_label` is `Unidentified`) and exits **4** ("empty cohort"). The six `--parser` selectors do cover the 8 named shas. | `tools/cohort_replay.py:99-101`; run-of-record `rows.csv` | record the correct selector in the W3 so a later reader does not re-run a vacuous command. |

---

## 3. What I did NOT find

* **No fake confidence surviving under another name.** `grep -rni confidence` over `webapp/` at the tip
  returns two comment lines and nothing else; no template, JS identifier, CSS class, banner string,
  status row or package label carries a number, percentage, ordinal or ranking derived from the
  validator verdict. The CSV/XLSX exports never carried one either — `webapp/app.py:293-347` writes
  payload fields only, and no `confidence` key is among them (`analysis/transaction_classifier.py`'s
  `confidence_score` is a classification-rule field that predates this card and never reached the
  removed surface).
* **No ContextVar staleness, leakage or cross-document read.** `collecting()`
  (`analysis/sibling_omission.py:476-499`) sets both vars and resets both in a `finally`; the gate runs
  only while `_COLLECTING` is open; a thread that did not open it sees the ContextVar defaults
  (`None`), which refuses; no production caller nests `analyze_document`; the raw markdown is captured
  before `_analyse` rebinds it to the admissible text, which is what the gate needs. The default
  `markdown=None` parameter fails closed if a future caller forgets it.
* **No "the next claimant publishes without the omission" hole.** `resolve`
  (`analysis/parser_registry.py:993-995`) returns `ambiguous` whenever more than one registration
  survives detection, so at most one `parse` runs and a raise cannot hand the document to a second
  reader that would publish it without the gap.
* **The other three ratified classes are genuinely ungated** — mutant M4 (extend the gate to
  `printed_dormancy_declaration`) is killed by two tests, and those tests run through a *different*
  module (`symitar.py`) from the gated-class tests (`member_statement.py`).
* **No Q3 leak from a header that is not on line one.** Header on line 2 → `None`; a second,
  hostile header later in the document with a native line 1 → admitted (correct: line 1 is the
  authority); a forged header inside page text is stripped by `admissible_text` for parsing and
  ignored by the provenance reader. The only line-1 leak is BLOCK-1.
* **No movement on the run of record.** All 132 rows of the six omission-publishing registrations
  carry `native-pdf-text*`; the 179 `local-tesseract-ocr` rows in the run are on other registrations.
* **No statement-specific hardcode introduced.** The 5 canonical guards pass (255).
* **cohort_replay reconstructions are provenance-honest**: `tools/cohort_replay.py:135-137` and
  `telemetry/stated_counts.py:924-928` both take `model` from the cached artifact (they re-stamp only
  `source_file`), so a replay's provenance is the run's provenance — which is also why the re-stamp is
  the vector in BLOCK-1.

---

## 4. Reproduction commands

All from `.claude/worktrees/rev20-surfaces` with `PYTHONPATH="$PWD"`.

```sh
# provenance census (read-only sqlite, mode=ro; tokens and counts only)
python <scratch>/model_census.py

# BLOCK-1
python -c "from ocr.document import StatementMarkdown; from analysis.provenance import extractor_model; \
 from analysis.pipeline import analyze_document; from tests.l1s4_pages import document, idle_account, posting_account; \
 body=document([idle_account(),posting_account()]).split(chr(10)*2,1)[1]; \
 md=StatementMarkdown(source_file='statement.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->', \
 model='local-tesseract-ocr', pages=[body]).to_markdown(); print(extractor_model(md)); \
 print([o.reason for o in analyze_document(md, parse_mode='deterministic').omissions])"

# BLOCK-2  (extract_statement replaced by a local sentinel; no network call)
python <scratch>/e4_auto.py
python <scratch>/e5_l1.py

# MAJOR-1 / MAJOR-2
python <scratch>/e1_e2.py

# MAJOR-3 — replay at base and tip
git worktree add --detach .claude/worktrees/rev20-base bea06bc      # throwaway, removed after
python -m tools.cohort_replay --run "<repo>/discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a" \
  --data-dir "<repo>/.claude/recovery/webapp_data_train9_cold" \
  --parser community_section --parser dakota_west --parser mission_valley \
  --parser member_statement_rollup --parser symitar --parser zions \
  --expect-identical --json <scratch>/base_six.json        # EXIT=3, 23 shas, runtime 242s
#   ... same command at ed269f4 ...                        # EXIT=3, 23 shas, runtime 233s
python <scratch>/summarize2.py <scratch>/tip_six2.json      # per-sha leaf counts and roots
python <scratch>/summarize.py  <scratch>/tip_six2.json <scratch>/base_six.json   # A-vs-B differences: 0
git worktree remove .claude/worktrees/rev20-base --force

# MAJOR-3 nit / MINOR-7
python -m tools.cohort_replay --run <run> --data-dir <cache> --folder guardian_cu --expect-identical   # EXIT=4

# MAJOR-4
python <scratch>/mutate.py tests/l1s4_pages.py <scratch>/m1_old.txt <scratch>/m1_new.txt
python -m pytest tests/test_l1s4_publisher.py tests/test_l1s4_transfers.py tests/test_l1s2_omission_ruling.py -q
git checkout -- tests/l1s4_pages.py

# mutation table (8 mutants, applied and restored in a finally; tree verified clean after each)
python <scratch>/mutants.py "$PWD"

# proof floor I ran
python -m pytest tests/test_q3_native_only.py tests/test_webapp_confidence_label.py \
  tests/test_l1s2_*.py tests/test_l1s3*.py tests/test_l1s4*.py tests/test_pipeline.py -q   # 234 passed, 1 deselected, EXIT=0
python -m pytest tests/test_webapp*.py -q                                                  # 162 passed, EXIT=0
python -m pytest tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py \
  tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py -q  # 255 passed, EXIT=0
```

The full default suite and `corpus_gate.py` were deliberately NOT run (the umbrella brief reserves
them for the composed train; `tasklist | findstr python` showed 7 other python processes on this
shared host throughout).

### Mutation table re-run by this reviewer

| mutant | applied to | killer(s) fired | result |
|---|---|---|---|
| M1 admit on model `""` | `analysis/sibling_omission.py` | `test_empty_model_token_refuses_and_fails_closed`, `test_header_removed_refuses_and_fails_closed` | **killed** (exit 1) |
| M2 admit on `local-tesseract-ocr` | same | `test_local_tesseract_ocr_refuses_and_fails_closed` + 2 | **killed** |
| M3 `extractor_model` reads line 2 | `analysis/provenance.py` | `test_extractor_model_never_reads_past_the_first_line` + 4 | **killed** |
| M4 gate extended to `printed_dormancy_declaration` | `analysis/sibling_omission.py` | both dormancy-ungated tests | **killed** |
| M5 `return 94` under a renamed function | `webapp/static/app.js` | numeric-literal guard + proximity guard | **killed** |
| M6 `"OCR confidence"` restored in the template | `webapp/templates/index.html` | string guard `[index.html]` | **killed** |
| M7 *(added)* gate removed entirely (`if False:`) | `analysis/sibling_omission.py` | 5 CASE-10 tests | **killed** |
| M8 *(added)* `startswith` → equality | same | `test_a_native_layout_suffix_is_still_admitted` | **killed** (and the L1-S4 publisher pins stayed green — see M-1) |

Tree clean after every mutant (`final clean: True`). **Missing from the cell's table and mine could
not kill:** a header supplied by `source_file` (BLOCK-1 — no test exists), and a model token
`native-pdf-textXYZ` (M-1 — admitted, no test pins the boundary).

---

## 5. Verdict

**BLOCK.**

The three ruled objectives are implemented and, on the run of record, nothing moves: OQ9's fabricated
score is genuinely gone with no substitute number anywhere in the webapp or its exports; OQ11's
banners are correct and non-destructive; the Q3 gate refuses `local-tesseract-ocr`, `""` and an absent
header in deterministic mode; the other three ratified classes are untouched; the guards, the targeted
suites and the cell's mutation table all reproduce; the replay is identical at base and tip.

It blocks on two reproduced defects in the one thing the card exists to guarantee:

* **BLOCK-1** — the provenance reader can be handed `native-pdf-text` by an attacker-supplied
  filename, so an OCR-fed document reaches the Q3 admission and classifies `validated`. That is Q3 OCR
  leakage, end to end, through the webapp's own upload path.
* **BLOCK-2** — in the webapp's default `parse_mode="auto"` the refusal does not fail closed: it
  routes the document to the hosted extractor and, on success, publishes one account with the printed
  sibling silently dropped. A policy refusal that starts an extractor escalation is the exact
  behaviour Phase 2.0 was opened to make impossible.

MAJOR-1 to MAJOR-4 must close with them: the replay evidence must stop being presented as proof of a
gate it cannot execute, the refusal reason must be recorded somewhere a reader can see (and stop
wearing the parser-crash label unqualified), the 23-delta characterisation and the exit code must be
corrected in `§P20SURFACES`, and the headerless production callers must be named and pinned. The
MINORs are cheap and I would accept them in the same pass.
