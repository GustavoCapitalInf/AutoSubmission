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

---

## Re-review (closure 2cb4c0e)

```
RE-REVIEWED   wave20-surfaces @ 2cb4c0e   (5 commits on ed269f4: 76b6ee9, 63cb8b6, c88090b, 0300a06, 2cb4c0e)
DIFF          git diff ed269f4..2cb4c0e   (10 files, +1217 / -96)
METHOD        every finding re-measured, never read off the closure's claims
VERDICT       BLOCK  (one finding re-opened by the fix that closed it; everything else closed)
```

Nine of the eleven findings are genuinely closed, several of them better than I asked for. The
closure is honest about what it did not do and volunteers two defects of its own. **BLOCK-1 is not
closed.** Its fix replaced an attacker-controlled *filename* vector with an attacker-controlled
*page-text* vector, which I reproduced end-to-end through the real
`StatementMarkdown.to_markdown()` writer, and the new module docstring asserts in so many words the
property the new code does not have.

### Per-finding verdicts

| finding | closure's claim | my re-measurement | verdict |
|---|---|---|---|
| **BLOCK-1** `source_file` supplies the model | CLOSED; parse from the RIGHT; "backtracking … always finds the LAST, trusted, code-appended run, never an earlier attacker-supplied one" | the *filename* vector is closed (A1/B1/B2 below all return `local-tesseract-ocr` and fail closed). But "the last run in the document" is not "the last run in the header": the pattern is unbounded on the right, so a run printed in the **page body** — which comes *after* the genuine fields — wins. Reproduced 4 ways, `validated`. | **RE-OPENED — BLOCK-1R** |
| **BLOCK-2** fail-open in `parse_mode="auto"` | CLOSED; unconditional refusal in every mode | reproduced with the sentinel: `local-tesseract-ocr`, `""` and headerless all raise `ParserCrashError` in **both** `deterministic` and `auto`; `extract_statement` reached **0** times across all 8 combinations | **CLOSED** |
| — the pre-existing `unclaimed → auto` edge | "explicitly left untouched and pinned" | measured unchanged: `deterministic` → `RuntimeError("no deterministic parser matched…")`, `auto` → `extract_statement` reached (1 call, `gemini-3.5-flash-lite`), identical to `ed269f4` | **CONFIRMED UNCHANGED** |
| **MAJOR-1** replay evidence cannot observe the gate | DISCLOSED, plus `tools/l1s4_document_replay.py` over the 8 `guardian_cu` shas at base and tip | re-ran it myself at `bea06bc` (throwaway worktree `.claude/worktrees/rev20-base`, removed after) and at `2cb4c0e`: `COHORT=8 REPLAYED=8 NEWLY_VALIDATED=0 OTHER_MOVEMENT=0 REGRESSIONS=0`, exit 0 both trees; `diff` of the two outputs = **0 lines**. All 8 `validated → validated (approved)`; 6 publish 1 account with `printed_pair_coincides_and_no_row_printed`; `7C7956EB5E93DB1D` and `E38FA786106F752E` publish 3 accounts each (27 and 7 internal transfers) and carry no omission | **CLOSED** (disclosure + the right instrument) |
| **MAJOR-2** refusal recorded nowhere a reader can see | CLOSED to the class-name level; `_failure_reason` split left to Ocean | measured through `DispatchCollector`: `dispatch.exceptions = [('member_statement_rollup','parse','Q3ProvenanceRefused')]` in both modes; `discovery/runner.py:693` formats that into `parser_exceptions` as `member_statement_rollup:parse:Q3ProvenanceRefused`, and `discovery/report.py:190` clusters on it — a reader of `rows.csv` **can** now tell the policy refusal from a crash. `_failure_reason` still returns `parser_exception` (measured), exactly as the closure states | **CLOSED** (residual noted below) |
| **MAJOR-3** 23-delta characterisation + missing exit code | CORRECTED to 21/23 `document.*`-only + 2 whole-payload; `EXIT=3` at both trees | matches my own measurement exactly (21 at 10-or-13 leaves; `7C7956EB5E93DB1D` 1,332 and `E38FA786106F752E` 1,334 leaves outside `document.*`; base exit 3 / tip exit 3, same 23 shas, 0 row-record differences). The root cause the closure gives (both publish 3 accounts, replayed at the ACCOUNT seam) is now independently corroborated by the document-seam replay above | **CLOSED** |
| **MAJOR-4** headerless production callers | DISCLOSED and pinned | `analyze.py` and `batch.py` named in the W3 with the fail-closed consequence stated; `test_the_headerless_case_above_is_a_live_production_path_not_only_a_fixture_shape` exists and is killed by the BLOCK-2 mutant (measured) | **CLOSED** |
| **M-1** `native-pdf-textXYZ` | CLOSED (`== token or startswith(token + "+")`) | measured: `native-pdf-textXYZ` → `ParserCrashError`; `native-pdf-text` and `native-pdf-text+guardian` still admitted; mutant R4 (revert to bare `startswith`) killed by `test_a_bare_concatenation_with_no_plus_is_refused` | **CLOSED** |
| **M-2** guard scoped to `app.js` only | CLOSED (parametrized over `STATIC_JS_FILES`) | confirmed in the diff; mutants R10-R12 fire on the parametrized id `[app.js]` | **CLOSED** |
| **M-3** text-shaped guard misses float / fraction / assignment | CLOSED for those three; arithmetic honestly documented as uncaught statically | mutants R11 (`return 0.94`) and R12 (`const S = 94; return S;`) both **killed**; the residual (`return 100 - 6`) is named in the source rather than glossed | **CLOSED** |
| **M-4** "Validated" promoted over the payload's own word | CLOSED (`labelize(q.corporate_use \|\| q.level \|\| "review")`) | one vocabulary across `validationLabel`, `packageValidationLabel` and `decisionPill`; Node tests updated to the payload's own tokens | **CLOSED** |
| **M-5** dead `.validation-value` rule | CLOSED (class applied to `#validationValue`) | confirmed in the diff | **CLOSED** |
| **M-6** ambiguous "the PaddleOCR design below" | CLOSED (names the file) | confirmed | **CLOSED** |
| **M-7** `--folder guardian_cu` selects 0 rows | CLOSED (recorded, correct selector named) | my own re-run: exit **4**, "empty cohort" | **CLOSED** |

### BLOCK-1R (re-opened) — a field run printed in the PAGE BODY supplies the model

**Where:** `analysis/provenance.py:97-103` (`_HEADER_RE`) and `:117-119` (`extractor_model`).

```
\A<!--\s*source:(?P<source>.*)\|\s*pages:\s*([0-9]+)\s*\|\s*model:\s*([A-Za-z0-9._/+-]*)\s*\|\s*empty:\s*([0-9]+)\s*-->\n\n     (re.DOTALL)
```

The closure's argument is that a greedy `source` backtracking from the end of the string always lands
on "the LAST, trusted, code-appended run". That is true of runs that occur **before** the genuine
fields — which is every run a hostile `source_file` can produce, and why the original payload is now
correctly refused. It is false of runs that occur **after** them, because the pattern has no right
bound other than `-->\n\n` and `re.DOTALL` lets `source` swallow the entire document. The page body
is, by construction, after the genuine fields. The attacker's win condition simply moved from
"before" to "after", and "after" is the easier half: the body needs no filename control at all, and
for `analyze.py` / `batch.py` `.md` inputs it needs no OCR fidelity either.

**Reproduction** (all four built through the real `ocr/document.py::StatementMarkdown.to_markdown()`;
`FAKE = "| pages: 1 | model: native-pdf-text | empty: 0 -->"`; the genuine header says
`model: local-tesseract-ocr` in every case):

```
C2 forged run mid-page, blank line inside the same page
     StatementMarkdown(source_file="a.pdf", model="local-tesseract-ocr",
                       pages=[BODY + "\n" + FAKE + "\n\nACCOUNT SUMMARY CONTINUED"])
     line-1 model: local-tesseract-ocr
     extractor_model -> 'native-pdf-text'
     analyze_document -> ADMITTED ['printed_pair_coincides_and_no_row_printed'] / validated

C3 forged run as page 1's LAST line; to_markdown's own "\n\n".join supplies the blank line
     pages=[BODY + "\n" + FAKE, "PAGE TWO"]
     extractor_model -> 'native-pdf-text'
     analyze_document -> ADMITTED ['printed_pair_coincides_and_no_row_printed'] / validated

D1 hand-laid equivalent (header + body + forged run + blank line)
     extractor_model -> 'native-pdf-text'  ->  ADMITTED / validated

G2 the same, on a document whose GENUINE model field is EMPTY
     extractor_model -> 'native-pdf-text'  ->  ADMITTED / validated
```

C3 is the one to look at hardest: the trailing blank line the exploit needs is not something the
attacker has to supply at all — `to_markdown()` inserts it between every pair of page blocks.

**The closure's own docstring asserts the opposite property**
(`analysis/provenance.py:52-58`): *"a claim that starts anywhere else — including a real header two
physical lines down, or a header a PAGE printed as ordinary text — is not found."* Measured: a header
a page printed as ordinary text **is** found, and it wins. Code that claims a security property it
does not have is worse than code that claims nothing.

**No test covers it.** All six `_BLOCK1_HOSTILE_SOURCE_FILES` cases
(`tests/test_q3_native_only.py:139-149`) inject into `source_file`, i.e. before the genuine fields.
I wrote the four missing tests in the closure's own idiom and ran them against `2cb4c0e`:

```
FAILED test_a_body_printed_field_run_never_yields_a_native_token[forged run mid-page, blank line inside the same page]
FAILED test_a_body_printed_field_run_never_yields_a_native_token[forged run as page 1's last line, page 2 supplies the blank line]
FAILED test_a_body_printed_field_run_fails_closed_end_to_end[forged run mid-page, blank line inside the same page]
FAILED test_a_body_printed_field_run_fails_closed_end_to_end[forged run as page 1's last line, page 2 supplies the blank line]
4 failed
```

**The fix I would accept — and the one I would NOT.** I prototyped both.

*Rejected: bound the header region on the left instead of the right* (`markdown.partition("\n\n")[0]`,
`\Z`-anchored). Measured: it closes the body vector (C2/C3/D1/G2 all refuse) but **re-opens** the
`source_file`-with-embedded-`\n\n` vector (B1/B2 return `native-pdf-text` and are admitted
`validated`). The two vectors are genuinely in tension: once `source_file` may contain a newline, a
forged run plus `\n\n` makes physical line one a complete, well-formed header that no reader can
distinguish from the real one. **There is no "pick the right run" rule that is safe in both
directions.**

*Accepted: ambiguity refuses.* Do not pick a winner — require the document to contain **exactly one**
well-formed `| pages: N | model: T | empty: N -->` run, and require that run to terminate physical
line one. Zero runs = no header. More than one = ambiguous. Both answer `None`, and `None` already
refuses. This is the platform's own direction (`analysis/sibling_omission.py`'s "absence refuses";
S4's "ambiguity refuses the aggregation"). Prototyped and measured over 16 cases — every hostile case
in this review and in the closure's own table, plus honest single-page, multi-page, empty-page,
layout-suffix and tesseract controls: **16/16 correct, 0 failures.** Applied in-tree it also passes
my 4 new tests and every L1-S2/L1-S4 pin: **151 passed, 1 failed.**

The one failure is instructive and must be part of the fix:
`tests/test_q3_native_only.py::test_a_hostile_source_file_still_reports_the_true_model_when_it_is_native`
asserts that an ambiguous document whose real model happens to be native is still **admitted**. That
test encodes a preference for admitting in the ambiguous case, which is the wrong direction for a
fail-closed provenance gate — the honest native document with a hostile filename should be refused,
not rescued. Re-point it to assert refusal.

Sketch (the whole change is in `analysis/provenance.py`):

```python
_FIELD_RUN_RE = re.compile(
    r"\|\s*pages:\s*[0-9]+\s*"
    r"\|\s*model:\s*(?P<model>" + _MODEL_CHARSET + r"*)\s*"
    r"\|\s*empty:\s*[0-9]+\s*-->"
)

def extractor_model(markdown: str | None) -> str | None:
    if not markdown or not markdown.startswith("<!-- source:"):
        return None
    first_line, newline, rest = markdown.partition("\n")
    if not newline or not rest.startswith("\n"):   # the mandatory blank line
        return None
    runs = list(_FIELD_RUN_RE.finditer(markdown))
    if len(runs) != 1 or runs[0].end() != len(first_line):
        return None                                 # zero, or ambiguous -> refuse
    return runs[0].group("model").strip() or None
```

If Ocean would rather not carry this in cell D at all, the alternative is to make the ambiguity
impossible at the writer — cell **P20-SEAM**'s declared scope is exactly "`source_file` provenance-token
injection closed (closed charset …)", and with a `source_file` that cannot contain `|`, `<`, `>`,
`-->` or a newline the original `ed269f4` first-line reader was already correct. That is a legitimate
resolution, but then D must say so, must not ship a docstring claiming a property it is borrowing,
and should carry a reader-side assertion that fails loudly if a header ever contains a second run.

### New findings introduced by the closure

* **MINOR-8 (new).** The `-->\n\n` right anchor is byte-exact, so a **CRLF** document no longer
  parses. Measured: header + `\r\n\r\n` → new reader `None`, `ed269f4` reader `'native-pdf-text'`.
  Direction is fail-closed and the affected callers are the same `.md` inputs MAJOR-4 already names
  (`analyze.py`, `batch.py`), but it is a new, undisclosed behaviour change. Fix: accept `\r?\n\r?\n`
  (my accepted fix above inherits the same nit — use `rest.startswith(("\n", "\r\n"))`).
* **MINOR-9 (new).** `analysis/provenance.py:52-58` states a security property the code does not have
  (see BLOCK-1R). Whatever fix lands, that paragraph must be rewritten to describe what the reader
  actually guarantees.
* **Residual on MAJOR-2 (not a new finding, correctly deferred).** `discovery/runner.py::_failure_reason`
  still maps the refusal to the reason token `parser_exception`, so `rows.csv`'s `outcome_reason`
  cannot separate policy refusal from crash; only `parser_exceptions` can. Measured; the closure
  states it plainly and assigns it to Ocean/cell A. I agree with that disposition.

### Proof floor I re-ran at 2cb4c0e

| proof | result |
|---|---|
| `tests/test_q3_native_only.py` | **35 passed** |
| `tests/test_webapp_confidence_label.py` | **16 passed** (51 together — matches the closure's claim) |
| `test_q3_native_only + test_webapp_confidence_label + test_l1s2_* + test_l1s3* + test_l1s4* + test_pipeline + test_sibling_omission` | **294 passed, 1 deselected, EXIT=0** |
| `tests/test_webapp*.py` | **163 passed** |
| 5 canonical guards | **255 passed** |
| `tools/l1s4_document_replay.py`, 8 `guardian_cu` shas, base `bea06bc` vs tip `2cb4c0e` | exit 0 both; output diff **0 lines**; `NEWLY_VALIDATED=0 OTHER_MOVEMENT=0 REGRESSIONS=0` |
| `cohort_replay --expect-identical`, six registrations | base **EXIT=3**, tip **EXIT=3**, same 23 shas (from my first-round runs; unchanged by this closure, which touches no seam the account replay reaches) |
| regex performance (greedy + DOTALL) | 4.3 MB document 0.027 s; 720 KB decoy-pipe document 0.011 s — no catastrophic backtracking |
| ownership footprint `bea06bc..2cb4c0e` | 12 files, all on the card's list except `tests/l1s4_pages.py` (disclosed in round 1, unchanged this round) and the review file itself |
| worktree after every experiment | `git status --porcelain` clean; throwaway base worktree removed |

### Mutation table (13 mutants, all re-applied by me, tree restored clean after each)

| mutant | killer(s) | result |
|---|---|---|
| R1 admit on model `""` | CASE-10 empty/headerless | killed |
| R2 admit on `local-tesseract-ocr` | 12 tests | killed |
| R3 gate removed entirely | 17 tests | killed |
| R4 MINOR-1 reverted to bare `startswith` | `test_a_bare_concatenation_with_no_plus_is_refused` | killed |
| R5 gate extended to `printed_dormancy_declaration` | both dormancy-ungated tests | killed |
| R6 BLOCK-1 regex reverted to the `ed269f4` pattern | 5 tests | killed |
| R7 `extractor_model` reads line 2 | 5 tests | killed |
| R8 BLOCK-2 mode-independent check removed | 4 tests (3 × "extract_statement reached", 1 production-path) | killed |
| R9 `Q3ProvenanceRefused` downgraded to bare `ValueError` | 7 tests incl. `test_dispatch_records_the_refusal_class_name_not_a_generic_parser_crash` | killed |
| R10 `return 94` under a renamed function | numeric-literal + proximity guards | killed |
| R11 `return 0.94` under a renamed function | same | killed |
| R12 `const S = 94; return S;` | `test_no_score_shaped_literal_assigned_anywhere_in_a_static_js_file` | killed |
| R13 `"OCR confidence"` restored in the template | string guard `[index.html]` | killed |
| **R14 (the mutant that cannot be written)** — a field run in the PAGE BODY | **nothing kills it; there is no such test, and the live code admits it** | **SURVIVES** |

### Re-review verdict

**BLOCK.**

The closure is, on every other axis, the best kind: each finding reproduced as a failing case before
any fix, each fix mutation-tested by reverting it, two self-found defects volunteered, the wrong
sentence in the record corrected rather than argued with, the instrument I asked for actually built
and run at both trees, and the one thing outside the cell's ownership left alone and named. BLOCK-2,
MAJOR-1 through MAJOR-4 and all seven MINORs are closed and re-measured closed by me.

It blocks on one thing only, and it is the same thing it blocked on before: **an OCR-fed document can
still reach the Q3 admission and classify `validated`.** The fix moved the vector from the uploaded
filename to the page text, which is a weaker position than before — the body needs no filename
control, and `to_markdown()` supplies the blank line the exploit needs between page blocks. The
accepted fix is small, prototyped, and measured green over 16 hostile and honest cases plus the
closure's own suite; it needs one existing test re-pointed from "admit" to "refuse", which is the
right direction for this gate anyway. With BLOCK-1R closed and MINOR-8/MINOR-9 folded in, I would
sign this off.

---

## Second re-review (closure 45c69f4)

```
RE-REVIEWED   wave20-surfaces @ 45c69f4   (3 commits on 2cb4c0e: 9a558dc, 912026f, 45c69f4)
DIFF          git diff 2cb4c0e..45c69f4   (4 files, +580 / -92; code change confined to analysis/provenance.py)
METHOD        every claim re-measured; 38 hostile/honest reader cases, 24 mutants, a corpus-wide census
VERDICT       APPROVE WITH FINDINGS
```

BLOCK-1R is closed. The cell took the accepted "ambiguity refuses" design, implemented it exactly,
re-pointed the one test whose direction I said was wrong, and rewrote the docstring that made a false
claim. I tried to break the new reader 38 ways — including every shape the coordinator named and
several the closure did not anticipate — and could not. The one finding that remains is a
test-coverage gap, not a behaviour gap: four clauses of the reader's own stated property are
unpinned, and I killed all four surviving mutants with four one-line tests that already pass at HEAD.

### Per-finding verdicts

| finding | closure's claim | my re-measurement | verdict |
|---|---|---|---|
| **BLOCK-1R** a field run in the PAGE BODY supplies the model | CLOSED by ambiguity-refuses | C2, C3, D1 and G2 all `extractor_model -> None` and `ParserCrashError` end-to-end, with `Q3ProvenanceRefused` named in `dispatch.exceptions`. Also refused: three body runs; a body run on an *honest native* document; a body run in a CRLF document; a body run when the genuine model field is empty | **CLOSED** |
| **BLOCK-1** (round 1) hostile `source_file` | must stay closed | A1, B1, B2, the nested-second-header case and the embedded-newline case all `None` + `ParserCrashError`; `evil-->`, `evil<`, `evil>` filenames still correctly report the genuine `local-tesseract-ocr` (one run, line-one-terminating) | **STILL CLOSED** |
| **the re-pointed direction test** | `test_a_hostile_source_file_on_an_honest_native_document_is_refused_not_rescued` now asserts refusal | read in the diff; measured `None` + `ParserCrashError`; and mutant S2 ("take the LAST run", i.e. reproduce BLOCK-1R) is killed by that test *by name* | **CONFIRMED RE-POINTED** |
| **MINOR-8** CRLF silently refused | CLOSED | CRLF header + LF body: `extractor_model -> 'native-pdf-text'` and the document is **ADMITTED / validated** — at `2cb4c0e` the same document answered `None` and refused. CRLF honest native / tesseract / layout-suffix all return their token; CRLF + body run still refuses; mixed LF-header/CRLF-body works. (A *fully* CRLF document reads its provenance correctly but no parser claims it — pre-existing parser behaviour on CRLF text, untouched by and out of scope for this card.) | **CLOSED** |
| **MINOR-9** docstring claimed a property the code lacked | CLOSED; rewritten as "THE PROPERTY, EXACTLY" | I tested each of the four stated clauses (a) `<!-- source:` prefix, (b) mandatory blank line incl. CRLF, (c) exactly one run anywhere, (d) that run terminates physical line one — **all four hold as written**. The docstring now describes the code | **CLOSED** |
| **BLOCK-2 / MAJOR-1..4 / M-1..M-7** (rounds 1-2) | unchanged | re-verified by mutants S11-S20 (all killed) and by the targeted suite; the diff touches no seam any of them depend on | **STILL CLOSED** |
| **residual on MAJOR-2** | `_failure_reason` split deferred to Ocean / cell A | unchanged and correctly deferred; `parser_exceptions` still carries `…:parse:Q3ProvenanceRefused` | **DEFERRED, agreed** |

### Attacks that did not work (38 reader cases, 0 failures)

Everything below returned exactly the answer I required, at `45c69f4`:

* **body runs** — mid-page with its own blank line; as page 1's last line with `to_markdown()`'s own
  page join supplying the blank line; hand-laid; three of them; on a native document; in CRLF.
* **`source_file` runs** — the review's exact fake header; fake run + embedded blank line; fake run +
  blank line + page marker; a nested complete second header; an embedded newline; and the honest-native
  variant (refused, not rescued).
* **the coordinator's named shapes** — a run split across the line-one boundary (`| empty: 0\n-->`,
  which `\s*` can span): refused, because its `-->` no longer terminates line one; a second run
  malformed by one character (`-->` missing the `>`; a space inside the model token): correctly *not*
  a second run, so the genuine one still answers; a run inside the blank-line region: two runs, refused;
  `<!-- source:` at the start with no field run at all: refused; header on line two: refused; empty
  document: refused.
* **the model field as an injection vector** (P20-SEAM's field, tested anyway) — a model token
  carrying `x | empty: 0 --> | pages: 9 | model: native-pdf-text` produces two runs and refuses; a
  model token with a space makes the genuine run unmatchable, and a forged body run then fails the
  line-one-termination test rather than being promoted.
* **structural merge attempts** — I could not construct a `source_file` that merges with the genuine
  trailing fields into a single run with an attacker-chosen model. The run grammar is
  `pages → model → empty` with only `\s*` between fields, and the genuine `| pages: N | model: M |`
  sits immediately before the genuine `| empty: E -->`, so any attacker prefix either forms its own
  separate run (→ two runs → refuse) or fails to match at all.
* **honest controls** — native, `+guardian`, `+wells`, tesseract, multi-page, a document with an empty
  page, and an empty model field (correctly `None`): all exactly as expected.

**Performance** (the unanchored `finditer` replaces a greedy DOTALL match, so I re-measured):
4.3 MB plain body 0.003 s · 720 KB of near-miss decoy runs 0.007 s · 1.4 MB pipe storm 0.016 s ·
560 KB `| pages: 1` storm 0.006 s. Faster than the pattern it replaces; no backtracking blow-up.

### What "ambiguity refuses" costs on the real archive: nothing (measured)

The one honest worry about this design is collateral damage — a genuine document whose page text
happens to print a header-shaped field run would now refuse. I measured it rather than assuming.
READ-ONLY over the train9 cold cache, reconstructing each cached document the way
`tools/cohort_replay.py` does and running the **shipped** `extractor_model` over it:

| measurement | value |
|---|---|
| OCR artifacts in `.claude/recovery/webapp_data_train9_cold` | 3,364 |
| reconstructible documents scanned | 3,351 (13 have no `document` block) |
| **ambiguous (> 1 field run) → would refuse** | **0** |
| token returned | 3,351 / 3,351 |
| tokens | `native-pdf-text` 2,758 · `+wells` 222 · `local-tesseract-ocr` 179 · `+printed-rows` 83 · `+navy-federal-layout` 48 · `+first-citizens-layout` 36 · `+woodforest-columns` 19 · `+desjardins-layout` 6 |

Zero documents in the entire cold cache are ambiguous. The collateral-damage concern is real in
principle and empty in practice on this corpus.

### MINOR-10 (new, and the only open finding) — four clauses of the stated property are unpinned

I applied 20 mutants. **16 were killed. 4 survived**, each disabling one clause of the property the
module docstring now states:

| surviving mutant | what it disables | why it is not caught |
|---|---|---|
| **S3** `if len(runs) != 1 or runs[0].end() != line_end:` → `if len(runs) != 1:` | clause (d), line-one termination | every shipped test that would notice also trips clause (a) or (c) first |
| **S7** drop `markdown.startswith("<!-- source:")` | clause (a) | `test_extractor_model_returns_none_without_a_header` uses text with *no* run, so the prefix guard is never the thing that refuses |
| **S8** drop `rest.startswith(("\n", "\r\n"))` | clause (b), the mandatory blank line | no test uses a header followed by a single newline |
| **S9** `_MODEL_CHARSET` → `[^\|]` | the closed model charset | no test asserts that a whitespace/angle-bracket model token is rejected |

None is a live defect — I verified all four clauses hold at `45c69f4`. But the mutation table is the
Phase-2 proof floor's own instrument ("a test named after a gate is not a test of that gate"), and
these four are exactly the case it exists to catch: a later edit could delete any of them and the
suite would stay green. S3 and S7 are the ones that would matter — under S3, a document whose line
one is `<!-- source: … | model: deterministic-native-preflight -->` (a header shape
`webapp/worker.py:427` really writes) plus one body run yields the *body's* model; under S7, a page
whose own first line ends in a well-formed run is read as a header.

**Fix I would accept** — four one-line tests. I wrote them, they **pass at HEAD**, and each kills its
mutant (verified: all four survivors go from `exit=0 SURVIVED` to `exit=1 KILLED` with these added):

```python
def test_a_lone_body_run_is_refused_when_the_header_prints_no_fields():      # kills S3
    assert extractor_model("<!-- source: a.pdf | model: deterministic-native-preflight -->\n\n"
                           "content\n| pages: 1 | model: native-pdf-text | empty: 0 -->\n") is None

def test_a_document_that_does_not_begin_with_the_source_marker_is_refused(): # kills S7
    assert extractor_model("STATEMENT OF ACCOUNT | pages: 1 | model: native-pdf-text | empty: 0 -->"
                           "\n\ncontent\n") is None

def test_a_header_without_the_mandatory_blank_line_is_refused():             # kills S8
    assert extractor_model("<!-- source: a.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->"
                           "\ncontent\n") is None

def test_the_model_charset_excludes_whitespace_and_angle_brackets():         # kills S9
    assert extractor_model("<!-- source: a.pdf | pages: 1 | model: nat ive | empty: 0 -->\n\nx\n") is None
    assert extractor_model("<!-- source: a.pdf | pages: 1 | model: <script> | empty: 0 -->\n\nx\n") is None
```

This does not block: the code is correct today, the finding is that nothing stops it from silently
becoming incorrect tomorrow.

### Proof floor I re-ran at 45c69f4

| proof | result |
|---|---|
| `tests/test_q3_native_only.py` | **43 passed** (35 → 43, +8 — matches the closure's claim) |
| `tests/test_webapp_confidence_label.py` | **16 passed** |
| `test_q3_native_only + test_webapp_confidence_label + test_l1s2_* + test_l1s3* + test_l1s4* + test_pipeline + test_sibling_omission` | **302 passed, 1 deselected, EXIT=0** (was 294 at `2cb4c0e`; +8, no other count moved) |
| `tests/test_webapp*.py` | **163 passed** |
| 5 canonical guards | **255 passed** |
| `tools/l1s4_document_replay.py`, 8 `guardian_cu` shas | exit 0; `COHORT=8 REPLAYED=8 NEWLY_VALIDATED=0 OTHER_MOVEMENT=0 REGRESSIONS=0`; output **byte-identical** (`diff` = 0 lines) to my `2cb4c0e` run, which was itself byte-identical to my `bea06bc` base run — so base ≡ closure-1 ≡ closure-2 at the seam production reads. No throwaway base worktree was needed this round |
| corpus census (read-only, cold cache) | 3,351 documents, **0 ambiguous**, 3,351 tokens returned |
| reader hostile/honest cases | **38 / 38 correct** |
| mutation table | 20 applied, **16 killed**, 4 survived (MINOR-10) — then all 4 killed with the four tests above |
| reader performance | 0.003-0.016 s over 0.5-4.3 MB documents, including adversarial decoy input |
| ownership footprint `bea06bc..45c69f4` | 12 files — all on the card's list except `tests/l1s4_pages.py` (disclosed round 1, unchanged since) and the review file Ocean owns |
| worktree | `git status --porcelain` clean before and after every mutant and every probe; final state clean apart from this uncommitted review file |

I did not re-run `cohort_replay --expect-identical` this round: it exercises `analyze_markdown`, which
never opens the omission collector (MAJOR-1), so it cannot observe any part of the change under
review. The document-seam replay above is the instrument that can, and it is byte-identical across all
three trees.

### Second re-review verdict

**APPROVE WITH FINDINGS.**

The one BLOCK is closed, and closed properly: not patched around the reviewer's four reproductions but
by adopting the design principle behind them, including the part that costs the cell something (an
honest native document behind a hostile filename is now refused rather than rescued, and the test that
asserted the opposite was re-pointed rather than deleted). The docstring now states a property I could
verify clause by clause; the rejected alternative is recorded with the reason it was rejected; the
CRLF fix is real end-to-end, not just at the reader; and the design's one theoretical cost is measured
at zero across all 3,351 documents in the cold cache. Thirty-eight hostile shapes and twenty mutants
found no way through.

MINOR-10 is the only thing outstanding and it is four one-line tests I have already written and
verified. I would accept it in this cell or as a follow-up at composition — Ocean's call. Nothing here
warrants holding the branch.
