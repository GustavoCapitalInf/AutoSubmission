# P20-ROUTER — independent adversarial review (Phase 2.0, cell A)

```
BRANCH        wave20-router @ aaa513f (reviewed detached in .claude/worktrees/rev20-router)
BASE          train10 @ bea06bc
REVIEWER      independent adversarial agent; did not write this code
DATE          2026-09-01
HOST          Python 3.14.5 (CI pins 3.12 — checked; no 3.13+ API in the diff)
RUN OF RECORD discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a
COLD CACHE    .claude/recovery/webapp_data_train9_cold (sqlite mode=ro, never written)
VERDICT       BLOCK — 1 BLOCK, 3 MAJOR, 9 MINOR. The escalation edges themselves are
              sound and every named killer reproduces; the FAILURE-CLASS LABEL is not.
```

Worktree state: `git status --porcelain` empty before, between and after every mutant
(each applied individually, reverted with `git checkout --` in a `finally`, cleanliness
asserted before the next). Nothing committed, nothing pushed, no network call, no write
to either cold cache.

---

## 1. Claim-by-claim (claimed → measured)

| # | claim (W3 §P20ROUTER / the card) | measured by me | verdict |
|---|---|---|---|
| 1 | R = 13 | 13 (own `rows.csv` read, and `tools.phase2_trigger_split`) | ✅ |
| 2 | U = 123 (89 `no_parser_matched` + 34 `parser_declined`; 111 scanned + 12 mixed) | 123 (89 / 34; 111 / 12) | ✅ |
| 3 | `U(dispatch≠claimed)` ≡ `U(outcome=failed)` | identical sets, 123 | ✅ |
| 4 | overlap 0, `validated ∩ (R∪U)` 0 | 0, 0 | ✅ |
| 5 | Tesseract split 36 validated / 15 withheld / 5 review / 123 failed (179) | identical | ✅ |
| 6 | T surface = 3, of which 1 in U | 3, 1 (own `rows.csv` read, independent of the instrument) | ✅ |
| 7 | U-extract = 23, U-structure = 100, 23+100 = 123 | 23 / 100 / 123 | ✅ |
| 8 | legal escalation population (R + U-extract) = 36 | 36 | ✅ |
| 9 | min alnum density among the 56 claimed Tesseract reads = 0.7075; min among the 36 validated = 0.7433 | 0.7075 / 0.7433 | ✅ |
| 10 | "the gate classifies all 36 validated Tesseract reads as usable" | 36/36 usable | ✅ |
| 11 | **"`validated ∩ class-A = 0` pinned"** (card scope line; umbrella completion criterion) | **FALSE on the run of record: 79 `validated` documents classify `failure_class="A"`**; the pin test only looks at Tesseract reads | ❌ **BLOCK-1** |
| 12 | "the decision is identical whether or not the analysis ran" | reproduced: identical `RouterInputs` + `Escalation` under a normal analysis and a D-3 cache hit; nothing in the decision path reads a dispatch or payload | ✅ |
| 13 | CASE 1 / 2 / 3 / 4 proved through the real `DiscoveryRunner` | all 4 present and green; CASE 1 and CASE 2 each kill a real mutant | ✅ |
| 14 | `ocr/escalation.py` + `ocr/pipeline.py` import nothing from `analysis`/`discovery`/`webapp`/`telemetry` | confirmed by AST test and by direct grep (`ocr/escalation.py` imports only `dataclasses`) | ✅ |
| 15 | `analysis/` → `ocr` import allowlist is empty | confirmed; mutant 9 killed by two tests | ✅ |
| 16 | `RouterInputs` field pin kills a `payload` field | killed in both files | ✅ (but see MAJOR/MINOR on subclasses) |
| 17 | "endpoint policy … B2's module is consulted when present" | **NOT consulted**: with cell B2's documented module (`check_endpoint(base_url,*,opt_in) -> EndpointDecision`) present and REFUSING everything, `decide` still returns `visual` | ❌ **MAJOR-1** |
| 18 | `ALNUM_DENSITY_FLOOR` "measured … never tuned toward a target split size" | it is a **fitted** threshold: chosen as a round number 0.0075 below the observed claimed minimum; the floor can be moved anywhere in [0.20, 0.74] with the ENTIRE suite (incl. the corpus slice) green, changing the escalation population from 13 to 48 | ❌ **MAJOR-2** |
| 19 | `telemetry/record.py`: "a row or record token from outside either vocabulary is refused by the `discovery.runner` row projection" | **no such refusal exists**; both tuples are dead constants read by nothing but tests, and are not even exported from `telemetry/__init__.py` (contrast `DEFERRED_REASONS`, enforced at `telemetry/record.py:399`) | ❌ **MAJOR-3** |
| 20 | `--densities` is the flag that produced the floor's provenance (`ocr/escalation.py:164`) | the flag does not exist; `python -m tools.phase2_trigger_split --densities` → exit 2 | ❌ MINOR-1 |
| 21 | new row columns appended at the END; readers by name unaffected | confirmed: `discovery.evidence.load_run` and `telemetry.stated_counts.load_run_rows` both load the frozen `rows.csv` (3,506 rows / 3,380 shas) AND a synthesized `rows.csv` carrying the 4 new columns; `tools/train8_compare.py`, `discovery/compare.py`, `tools/cohort_replay.py`, `tools/batch9_census.py` all read via `csv.DictReader` + `.get` | ✅ |
| 22 | `telemetry/record.py` — nothing but the two vocabularies changed | confirmed (single additive hunk; `source_path_for` untouched) | ✅ |
| 23 | ownership: nothing outside the card's list | `discovery/cli.py` (25 lines) is changed and is NOT on the card's or the umbrella's ownership list for cell A | ⚠ MINOR-2 |
| 24 | nothing under `analysis/`, `ocr/ocr_client.py`, `ocr/pipeline.py`, `ocr/config.py`, `ocr/document.py`, `webapp/artifact_cache.py` | confirmed by `git diff --stat` | ✅ |
| 25 | cohort replay at the tip, `--expect-identical`, exit 0, 0 newly validated, preserved identical | reproduced on my own 192-sha cohort (179 Tesseract + 13 R): exit 0, replayed 179, **newly validated 0**, preserved **36 of 36 payload-identical**, validated regressions 0, other ladder movement 0, 83 s | ✅ |
| 26 | targeted proof floor "252 passed, 3 deselected" | measured **253 passed, 3 deselected**, exit 0 | ⚠ MINOR-3 |
| 27 | 5 canonical guards "255 passed" | 255 passed, exit 0 | ✅ |
| 28 | "`tests/test_escalation_router.py` — 45 tests (44 default + 1 corpus)" | **39 collected** (37 `def test_`, 38 default + 1 corpus); the section's own itemisation adds to 37 | ⚠ MINOR-4 |
| 29 | mutation table 9/9 killed, killers named | 8 of the 9 re-applied here + 5 new ones; every named killer reproduces. Mutant 5's killer only passes against a **fictional** API (see MAJOR-1) | ⚠ (see MAJOR-1) |
| 30 | "Auto mode … a tripwire test proves it stays A-only" | no auto-mode test was added; the property is in fact covered — by the `ocr/pipeline.py` import guard, which is the real proof. Wording overstates what exists | ⚠ MINOR-5 |

---

## 2. Findings

### BLOCK-1 — `validated` documents are labelled Class A. The card's own pin is false on the run of record (79 documents), and the dry run labels every committed-artifact row an extraction failure.

**Where.** `discovery/runner.py:820` (`evidence = ExtractionQualityGate.assess(document, profile)` — run for EVERY document, native included), `discovery/runner.py:225-245` (`classify_failure`, which returns `A` before it ever looks at `validated`), `ocr/escalation.py:226-228` (the alnum-density criterion), `tests/test_escalation_router.py:590-619` (the pin, scoped to Tesseract reads only).

**What is wrong.**

1. `classify_failure` short-circuits on `not evidence.usable` → `A_EXTRACTION`, *before* `claimed`/`validated`. A `validated` document therefore gets `failure_class="A"`, contradicting `ocr/escalation.py:57-60`'s own definition of `NO_FAILURE` ("the document is `validated` … there is nothing to classify") and the card's scope line "`validated ∩ class-A = 0` pinned".
2. The fourth gate criterion (`ALNUM_DENSITY_FLOOR`) was measured on 179 **Tesseract** reads and is then applied to all 3,172 **native** reads, where it was never measured and where the architecture plan is explicit: unclaimed native text is Class B, "re-reading perfect text with a GPU cannot invent a parser."
3. On the dry-run rung `_read` legitimately returns `(None, markdown, sheets, "committed_artifact")` (`discovery/runner.py:548-551`). `assess(None, …)` answers `no_text_produced`, so **every committed-artifact row** — text present, parser claimed, document `validated` — is recorded `evidence_quality=unusable`, `failure_class="A"`.
4. The card's pin test (`test_validated_tesseract_reads_are_never_classified_class_a`) only measures `validated_shas & tesseract_shas`. It cannot see any of this. The card says the pin is "over the run of record's `rows.csv` + the gate" — not over one source path.

**Measured (real `ExtractionQualityGate` + real `classify_failure`, over the run of record's `rows.csv` + the read-only cold cache; `claimed` taken from `dispatch_outcome`, which is immaterial because `A` is returned before `claimed` is read):**

| source_path | failure_class | validated | n |
|---|---|---|---:|
| local_tesseract | `""` | yes | 36 |
| local_tesseract | A | no | 23 |
| local_tesseract | B | no | 100 |
| local_tesseract | C | no | 20 |
| native | `""` | yes | 2,510 |
| native | **A** | **yes** | **79** |
| native | A | no | 74 |
| native | B | no | 482 |
| native | C | no | 27 |

Total Class-A rows the runner would publish over the run of record: **176** — against the cell's own reported legal escalation population of **36**. 51 of them are *unclaimed native* documents, i.e. exactly the Class-B population the architecture forbids ever treating as A.

**What the criterion actually measures** (aggregate character-class shares, no content):

| population | n | median alnum | median whitespace | median punct/other |
|---|---:|---:|---:|---:|
| validated native, gate says UNUSABLE | 79 | 0.565 | **0.321** | 0.079 |
| validated native, gate says usable | 2,510 | 0.777 | 0.157 | 0.061 |
| validated Tesseract | 36 | 0.783 | 0.161 | 0.064 |

The separator is **whitespace**, not noise (punctuation share barely moves). `below_alnum_density_floor` is a wide-column / padded-tabular-layout detector. That is the answer to "what happens to a legitimately-claimable page with dense tabular text": it is called an extraction failure — 79 times, on documents that reconcile.

**Reproduction (both through the real `DiscoveryRunner`, no cache, no OCR):**

```
# 1. a validated, claimed, NATIVE document -> failure_class A
sha16 E3C98E2252BE3E70  (BMO/…, from the run of record)
  source_path native | dispatch claimed | outcome_class validated
  evidence_quality unusable | failure_class 'A'

# 2. the dry-run committed-artifact rung -> every row an "extraction failure"
DiscoveryRunner(CORPUS, mode=MODE_DRY_RUN, …).process("Misc/First Farmers 2026 01-document.pdf","Misc")
  source_path committed_artifact | dispatch claimed | outcome_class validated
  evidence_quality unusable | failure_class 'A'
```

**Why this is BLOCK and not MAJOR.** Nothing escalates today — the runner's upgrade branch is additionally guarded by `source_path_for(document.model) == "local_tesseract"` (`discovery/runner.py:822-824`), so the safety of the *edge* does not depend on the *label*. But the label is the durable interface: it goes on `rows.csv`, into `summary.json`'s `failure_class` rollup, and into whatever Phase 2.1 reads to decide "which documents are Class A and may return to another extractor" (the architecture's own definition of A). A phase whose entire purpose is to make "Class B treated as A" impossible must not ship a row vocabulary in which 153 native documents — 79 of them validated — are stamped A. It also falsifies a criterion the umbrella lists under "Phase 2.0 is complete only when ALL hold".

**Fix I would accept (all four parts):**

1. `classify_failure`: check `validated` FIRST — `if validated: return NO_FAILURE` — then the evidence, then claimed. A document the deterministic validator proved cannot be an extraction failure by definition.
2. Assess the gate only on evidence an EXTRACTOR produced. Either pass the source path into the assessment site and leave `evidence_quality="none"` / `failure_class` from `claimed`/`validated` alone for `native` and `committed_artifact` rows, or gate the density criterion on OCR-sourced reads only (it is the only population it was measured on). A `document is None` with a non-`None` `markdown` must never be reported as `no_text_produced`.
3. Widen the pin: `test_validated_tesseract_reads_are_never_classified_class_a` becomes a pin over **every** row of the run of record — `{sha : classify_failure(...) == "A" and outcome_class == "validated"} == set()` — with the same corpus mark. That test must fail on today's tree before the fix and pass after.
4. Re-run `tools/phase2_trigger_split` and republish the Class-A population in the W3 section (the reported 36 is the Tesseract-only number; the row-level number is what the next phase will consume).

---

### MAJOR-1 — the endpoint-policy seam is inert against cell B2's real contract, and its mutation killer only proves a fictional API

**Where.** `ocr/escalation.py:318-333` (`_endpoint_policy_allows`), consulted at `:306`; `tests/test_escalation_router.py:258-272` (the killer for mutation-table row 5).

**What is wrong.** The guard does `from ocr.endpoint_policy import extractor_allowed`. `docs/agent-handoffs/P20-SEAM.md` §2 defines that module's API as `classify_endpoint(base_url)` and `check_endpoint(base_url, *, opt_in) -> EndpointDecision(allowed, klass, reason)`; there is no `extractor_allowed`. A `from … import <missing name>` raises `ImportError`, which the guard catches and turns into `return True, ""` — **fail-open**. Composition order at the train is **B2 → B1 → A**, so at the composed tree the policy module is guaranteed present and guaranteed never consulted. The mutation-table entry "router returns a remote/paid extractor id → killed by the endpoint-policy guard test" is true only because the test injects a stub exporting the invented name.

**Reproduction.** With a module exporting exactly P20-SEAM's contract (`check_endpoint`, `classify_endpoint`, `EndpointDecision`, `EndpointRefused`) installed in `sys.modules` and refusing every endpoint:

```
decision  : Escalation(extractor='visual', trigger='extractor_output_unusable', refused=())
policy consulted? False   (check_endpoint was never called)
```

**Fix I would accept.** Import the MODULE, not a name, and fail **closed** on a contract mismatch:

```python
try:
    from ocr import endpoint_policy
except ImportError:
    return True, ""                      # B2 has not composed — documented baseline
check = getattr(endpoint_policy, "check_endpoint", None)
if check is None:
    return False, "endpoint_policy_contract_mismatch"
```

plus a decision on which URL the router hands it (the router has no `Settings`; either the call site passes the base URL through `RouterInputs.profile`'s sibling — no, that widens the pinned field set — or B2 exposes the extractor-level helper this branch assumed and P20-SEAM is amended in the same composition). Either way: a test that stubs **P20-SEAM's own signature** and asserts refusal, and a test that asserts a present-but-mismatched module refuses. This must be settled before B2 and A are composed together, not after.

---

### MAJOR-2 — `ALNUM_DENSITY_FLOOR = 0.70` is a fitted threshold, and it is unpinned across the whole band that matters

**Where.** `ocr/escalation.py:161-173`, `:226-228`.

**Judgement asked for by the card ("measure and justify, not tune").** The floor is *derived from the answer*: it is "a round number just below the minimum density among the reads a parser happened to claim" (0.7075). That is the definition of fitting a threshold to the sample. A structural criterion would state a property of unreadable text (e.g. "no line contains a token of ≥N alphanumeric characters", "the ratio of dictionary-shaped tokens to total tokens", "a page whose character histogram is dominated by a single glyph class") and would then be *tested* against the corpus. This one has the corpus baked in. The composition measurement above shows what it keys on — whitespace share — which is a layout property, not an evidence-quality property.

**Reproduced fragility.** Applying the floor as a mutant, one at a time, running the full owned test set INCLUDING the corpus-marked slice:

| floor | U-extract (legal escalation population) | suite result |
|---:|---:|---|
| 0.20 | 0 → population 13 | **all green** (default + corpus slice) |
| 0.70 (shipped) | 23 → population 36 | green |
| 0.74 | 35 → population 48 | **all green** (corpus pin still passes; min validated is 0.7433) |
| 0.75 | — | corpus pin FAILS (`test_validated_tesseract_reads_are_never_classified_class_a`) |

So the pin the card asked for exists and does fire — but only above 0.7433, and only in the `@pytest.mark.corpus` slice that the default suite deselects (`addopts = -m "not live and not corpus"`). Anywhere inside [0.20, 0.74] the floor moves silently, and the "legal escalation population" — the number the runner's budget and the next phase both key on — moves from 13 to 48 with every test green. 16 documents sit within ±0.02 of the line (8 U-extract in [0.68,0.70), 8 U-structure in [0.70,0.72)); 5 of the 56 claimed reads sit in [0.70,0.72), i.e. within 0.0075–0.02 of being declared unusable.

**What evidence would justify a floor.** Either (a) a labelled sample: N Tesseract reads a human confirmed are unreadable vs N confirmed readable-but-unparsed, with the criterion separating them and the boundary documented as an error rate in both directions; or (b) a criterion with no free parameter at all (the existing `no_text_produced` / `below_char_floor` / `all_pages_empty` triad has none — and, measured, the triad already fires 0 times on the 179 Tesseract reads, so the density criterion is doing 100% of the separating work on a 56-document justification).

**Fix I would accept (minimum, if the floor stays).** (i) A test in the DEFAULT suite that pins both the floor's value and the resulting split (`U-extract == 23`, `U-structure == 100`, `legal escalation population == 36`) against the run of record, so any move in either direction is a visible, reviewed change; (ii) the density criterion restricted to OCR-sourced evidence (also required by BLOCK-1); (iii) the W3 wording corrected from "never tuned" to what it is — a corpus-fitted floor with a 0.0075 margin below the claimed minimum and a 0.0433 margin below the validated minimum — so Gustavo rules on it with the real characterisation in front of him.

---

### MAJOR-3 — the two new vocabularies enforce nothing; the comment says they do

**Where.** `telemetry/record.py:68-84`.

The comment states: *"A row or record token from outside either vocabulary is refused by the `discovery.runner` row projection."* Grepping the tree, `FAILURE_CLASSES` and `EXTRACTION_TRIGGERS` are read by **nothing** outside tests; `DocumentRow.as_dict` (`discovery/runner.py:215-221`) performs no validation; neither name is exported from `telemetry/__init__.py`. The sibling vocabulary `DEFERRED_REASONS` *is* enforced — `telemetry/record.py:399` raises `ValueError` on an unknown token — which is the pattern the card asked for ("so a row/record token from outside the vocabulary is refused"). PHASE2-RULES is explicit that comments do not count as enforcement.

**Fix I would accept.** Validate at the projection: in `DocumentRow.as_dict` (or at `write_rows`), raise on `failure_class not in FAILURE_CLASSES` and on `escalation_trigger not in ("",) + EXTRACTION_TRIGGERS`; export both from `telemetry/__init__.py` beside `DEFERRED_REASONS`; add a test that an out-of-vocabulary token raises. Or delete the false sentence and stop claiming the refusal. The first is what the card asked for.

---

### MINOR-1 — the floor's cited provenance command does not exist
`ocr/escalation.py:164` cites `tools/phase2_trigger_split.py --densities` as the measurement that produced 0.7075. That flag is not in the parser (`--run`, `--data-dir`, `--out` only). Reproduced: `python -m tools.phase2_trigger_split --densities` → `error: unrecognized arguments: --densities`, exit **2**. The one numeric threshold in the module cannot be reproduced by the command that documents it. **Fix:** add the flag (print the density distribution and the claimed/validated minima) or cite the command that actually produces the number.

### MINOR-2 — `discovery/cli.py` is outside the card's declared ownership
`git diff --stat` shows 25 changed lines in `discovery/cli.py`. It is on neither the card's Ownership list nor the umbrella's "Expected files / modules touched" for cell A. The change is necessary (item 2f's budget cannot be wired without it) and collides with no other cell's list, but the card says an overlap "is reported to Ocean, never resolved by a cell". **Fix:** Ocean records the ownership extension; no code change needed.

### MINOR-3 — targeted proof-floor count is off by one
Claimed 252 passed / 3 deselected; measured **253 passed, 3 deselected, exit 0** at `aaa513f` over the same eight files (no test file changed between `6d7704d` and `aaa513f`).

### MINOR-4 — the test-count arithmetic in the W3 section does not add up
Claimed "45 tests (44 default + 1 corpus)" for `tests/test_escalation_router.py`; measured **39 collected** (37 `def test_`, one parametrized ×3; 38 default + 1 corpus). The section's own itemised list sums to 37. `tests/test_escalation_tripwires.py` = 6, as claimed.

### MINOR-5 — "a tripwire test proves auto mode stays A-only" names a test that was not added
No auto-mode test appears in either new file, and nothing was added to `tests/test_webapp_worker.py`. The property IS covered — by `test_escalation_and_pipeline_import_nothing_forbidden`, which proves `ocr/pipeline.py` cannot see a verdict — but the report should cite that, not an imagined dedicated test.

### MINOR-6 — the tripwires stop at `discovery/` and `webapp/`; a verdict-driven escalation outside those two trees is caught by nothing
Two attacks, both reproduced, both leaving the full owned test set green (44 passed):

* **Subclass:** `@dataclass(frozen=True) class SmuggledInputs(RouterInputs): payload: object = None; dispatch_outcome: str = ""` is accepted by `EscalationRouter.decide` and returns `visual`. The field pin checks `RouterInputs.__dataclass_fields__` only.
* **Foreign call site:** a scratch `tools/_reviewer_attack_callsite.py` that hand-rolls `RouterInputs(...)`, derives `triggers` from `dispatch_outcome != "claimed"` and `stop` from a reconciliation flag, escalates to `visual` — `tests/test_escalation_tripwires.py` never looks at `tools/`, `ocr/`, `telemetry/` or the root scripts. (Removed; `git status --porcelain` verified empty.)

This is within the card's letter (it names `discovery/` and `webapp/`), and `analysis/` — the dangerous tree — IS covered by the import guard (mutant 9 killed by two tests). **Fix I would accept (cheap):** scan the whole repo, excluding `ocr/escalation.py` and `tests/`, for `decide(` call sites and for `RouterInputs(` constructions, and assert both sets are exactly the three known sites / zero; and assert `RouterInputs.__subclasses__() == []`.

### MINOR-7 — the escalation budget's population predicate is not a superset of the router's admission predicate
`estimate_class_a_population` (`discovery/runner.py:262-286`) counts `classification in ("scanned","mixed")`; the router admits on `classification == "scanned" or native_text_total_chars == 0` (`_profile_triggers`, `:248-260`). Reproduced at the function level: a valid, unencrypted, **zero-page** PDF profiles `unknown` with `native_text_total_chars == 0` → the router admits `image_only_document`, the estimator counts 0. It also `except OSError: continue`s — on this host OneDrive `PermissionError` (an `OSError`) is a documented recurring failure, so a transient read error at preflight silently lowers the ceiling and converts a later legitimate escalation into a terminal `failed / escalation_refused` row on a *different* document. On the run of record the ceiling over-counts safely (192 scanned+mixed ≥ 136 R∪U; all 13 R and all 179 Tesseract reads are scanned/mixed; the 16 `unknown` are all invalid PDFs that return before the router), so this is latent. The docstring's "sound OVER-count" is nonetheless false in general. **Fix:** make the estimator's predicate literally `_profile_triggers(profile) & ADMITTED_TRIGGERS` (one shared predicate, no drift), and count an unreadable file toward the ceiling rather than skipping it.

### MINOR-8 — a recovery escalation records `image_only_document`, so trigger R never appears on any row
`EscalationRouter.decide` picks the reported trigger as the first member of `ALL_TRIGGERS`'s declared order present in the admitted set (`ocr/escalation.py:314`), and `IMAGE_ONLY_DOCUMENT` is declared first. Reproduced on a real recovery through `DiscoveryRunner`: `visual_rung=recovered`, `escalation_trigger='image_only_document'` — never `offline_rungs_produced_no_text`, which the card defines as "the recovery path's trigger" and which the whole R population is named after. The rows therefore cannot distinguish R from a profile-level admission. **Fix:** report the most SPECIFIC admitted trigger (evidence-level before profile-level: `extractor_output_unusable` → `offline_rungs_produced_no_text` → `operator_forced_visual` → profile triggers), or record the whole admitted set.

### MINOR-9 — three smaller things in the same area
* `row.escalation_refused` is populated only when `_upgrade_eligible` is also true, so a Class-B document that claimed carries an empty refusal while a Class-B document that did not carries `no_admitted_trigger` — the column is not comparable across rows.
* The recovery branch's `attempted=("local_tesseract",) if self.allow_local_ocr else ()` would, in a mode with visual-but-not-local OCR, make `decide` name `local_tesseract`, and the `!= "visual"` test then writes a **terminal `failed / escalation_refused`** row instead of doing the visual read. Unreachable today (`MODE_SCANNED_VISUAL ∈ LOCAL_OCR_MODES`), but it is a fail-*closed*-into-a-wrong-outcome shape, not a refusal.
* `classify_failure(evidence, claimed=payload is not None, …)`: a parser that claims and then crashes has a dispatch outcome of `claimed` but no payload, so it is graded **B** (structure) rather than **C**. Population on the run of record: 0. Worth a docstring note, not a code change.

---

## 3. What I did NOT find (checked, and clean)

* **No validator-driven escalation on any live path.** Every `decide(` call site (2 in `discovery/runner.py`, 1 in `webapp/worker.py`) builds its `RouterInputs` from profile + evidence + a literal trigger set. The upgrade path's trigger set is `{EXTRACTOR_OUTPUT_UNUSABLE}` *iff the evidence is unusable*, computed at `discovery/runner.py:820-831` before `_analyse` at `:833`. No dispatch, payload, outcome, reason, parser id, reconciliation or ADB state reaches a trigger anywhere.
* **The "frozen before analysis" claim holds under attack.** Recording the actual `RouterInputs`/`Escalation` through the real runner under (a) a normal analysis and (b) a D-3 analysis cache hit gives byte-identical triggers, `attempted`, `stop`, evidence and extractor. A parser crash and an exception inside `_analyse` cannot reach the decision either: `_analyse` catches `Exception` and the decision is already computed.
* **Class B never escalates.** CASE 1 through the real runner: usable, unclaimed, high-density synthetic text → `visual_rung=not_attempted`, `failure_class=B`, `escalation_refused=no_admitted_trigger`, `_forbid_visual` never trips. Mutant M1 (unconditional upgrade trigger) and my new mutant N1 (the literal reading of the card's `operator_forced_visual` sentence applied to the UPGRADE path) are both killed by it — **the cell's flagged reading of §5 is the correct one**, and I would rule the same way: `--scanned-visual` is a mode flag constant across the whole run, so admitting it on the upgrade path admits all 123 U documents (every one profiles scanned or mixed). The conservative direction wins, and it is the direction the card's own CASE 1 and mutation table require. Keeping it as the sole trigger at the worker's per-document `force_ocr` site is right for the opposite reason: there it really is one human instruction about one document, and `stop` is checked before it.
* **Class C never escalates.** CASE 2 through the real runner. My own mutant — a C→OCR edge inserted after `classify_failure`, keyed on `outcome_class != "validated" and dispatch_outcome == "claimed"` — is killed by `test_case2_claimed_but_financially_failing_never_escalates`. The discovery runner is additionally stricter than the literal `stop=validated` wording (`_upgrade_eligible` refuses ANY claimed document), which is the safe direction; I agree with the cell's second flagged reading.
* **A native unclaimed document never escalates** — `source_path_for(document.model) == "local_tesseract"` gates the upgrade candidate. (Its *label* is the BLOCK, not its routing.)
* **`stop` is the only verdict-shaped input, and it is monotone.** `stop=True` returns `stopped_by_validated` before any trigger is examined; mutant M3 killed by two tests. There is no way to make `stop` cause an escalation.
* **T is defined and refused** (OQ4): `ADMITTED_TRIGGERS` excludes it, mutant M4 killed by two tests, and T's population (3, 1 in U) is measured, never routed.
* **No PaddleOCR id, no page-level routing, no network call, no new parser, no hardcode.** `EXTRACTOR_ORDER == ("local_tesseract","visual")`, pinned; the 5 canonical guards pass (255).
* **The regression floor holds.** Cohort replay at `aaa513f` over 179 Tesseract + 13 R shas: exit 0, newly validated **0**, previously validated preserved **36/36 payload-identical**, validated regressions 0, other ladder movement 0.
* **Row schema is backward and forward compatible** (item 21 above), and `telemetry/record.py` carries no change but the two additive constants.
* **No 3.13+-only API** anywhere in the diff (checked `batched`, `override`, `read_text(newline=)`, `warnings.deprecated`, `Path.walk`, `TypeIs`, `ReadOnly`); the module uses `from __future__ import annotations` throughout, so the PEP-604 annotations are inert on 3.12.
* **The instrument is genuinely read-only** — `sqlite3` `mode=ro`, `artifact_cache` SELECT only, no analysis call, sha16 lists only to a private `--out`; its `rows[0]` artifact pick is the known pre-cell-C behaviour and is correct on this cache by measurement (1 artifact per input).

---

## 4. Mutation table — re-applied by me

Each mutant applied alone; `python -m pytest … -q --no-header`; reverted with `git checkout --` in a `finally`; `git status --porcelain` asserted empty before the next.

| # | mutant | file | expected killer | measured killer(s) | result |
|---|---|---|---|---|---|
| M1 | upgrade trigger unconditional (`dispatch≠claimed` shape) | `discovery/runner.py` | CASE 1 | `test_case1_usable_unclaimed_tesseract_text_never_escalates` | KILLED |
| M2 | a C → OCR edge (re-escalate a claimed, non-validated Tesseract read after classification) | `discovery/runner.py` | CASE 2 | `test_case2_claimed_but_financially_failing_never_escalates` | KILLED |
| M3 | `stop` ignored (`if inputs.stop` → `if False`) | `ocr/escalation.py` | CASE 4 stop | `test_stop_refuses_regardless_of_any_trigger`, `test_force_ocr_decision_stops_the_moment_analysis_exists` | KILLED |
| M4 | `truncation_flagged` admitted | `ocr/escalation.py` | T refusal (OQ4) | `test_truncation_flagged_alone_is_refused_oq4`, `test_all_triggers_and_admitted_triggers` | KILLED |
| M6 | `attempted` filter removed | `ocr/escalation.py` | CASE 3b | `test_every_extractor_already_attempted_refuses_case_3b` + 5 more | KILLED |
| M7 | budget ceiling never trips | `discovery/runner.py` | counter refusal | `test_the_escalation_budget_refuses_past_its_ceiling` | KILLED |
| M8 | `RouterInputs` gains `payload` | `ocr/escalation.py` | field pin | `test_router_inputs_field_set_is_pinned` (both files) | KILLED |
| M9 | `analysis/pipeline.py` imports `ocr.escalation` | `analysis/pipeline.py` | import guard | `test_analysis_ocr_imports_match_the_pinned_allowlist_exactly`, `test_no_analysis_module_imports_the_forbidden_ocr_or_discovery_modules` | KILLED |
| M5 | *(endpoint bypass)* | — | endpoint-policy guard | **superseded**: the guard is inert against B2's real contract — see MAJOR-1 | **NOT PROVEN** |
| **N1** *(new)* | `OPERATOR_FORCED_VISUAL` added to the UPGRADE trigger set (the card's literal §5 reading) | `discovery/runner.py` | — | `test_case1_usable_unclaimed_tesseract_text_never_escalates` | KILLED (confirms the cell's reading) |
| **N2** *(new)* | `ALNUM_DENSITY_FLOOR` 0.70 → **0.20** (escalation population 36 → 13) | `ocr/escalation.py` | — | none — default suite AND the corpus slice stay green | **SURVIVES** (MAJOR-2) |
| **N3** *(new)* | `ALNUM_DENSITY_FLOOR` 0.70 → **0.74** (escalation population 36 → 48) | `ocr/escalation.py` | — | none — corpus pin still passes | **SURVIVES** (MAJOR-2) |
| **N4** *(new)* | `ALNUM_DENSITY_FLOOR` 0.70 → 0.75 | `ocr/escalation.py` | — | `test_validated_tesseract_reads_are_never_classified_class_a` (corpus-marked only) | KILLED |
| **N5** *(new)* | budget counter never incremented (increment after the escalation) | `discovery/runner.py` | — | `test_the_escalation_budget_permits_exactly_its_ceiling`, `test_cli_run_computes_and_publishes_the_escalation_budget` | KILLED |
| **A1** *(attack)* | `RouterInputs` **subclass** carrying `payload` + `dispatch_outcome` | — | — | none | **SURVIVES** (MINOR-6) |
| **A2** *(attack)* | new `decide(` call site in `tools/`, hand-rolled `RouterInputs`, `stop` from a reconciliation flag | — | — | none | **SURVIVES** (MINOR-6) |
| **A3** *(attack)* | B2's REAL `endpoint_policy` present and refusing | — | — | none | **SURVIVES** (MAJOR-1) |

---

## 5. Reproduction commands

All from `.claude/worktrees/rev20-router` (`<repo>` = the parent checkout; `<scr>` = a private scratch dir).

```bash
# targeted proof floor  -> 253 passed, 3 deselected, exit 0
python -m pytest tests/test_escalation_router.py tests/test_escalation_tripwires.py \
  tests/test_visual_rung.py tests/test_discovery.py tests/test_telemetry.py \
  tests/test_pipeline.py tests/test_webapp_worker.py tests/test_worker_privacy.py -q

# 5 canonical guards -> 255 passed, exit 0
python -m pytest tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py \
  tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py \
  tests/test_filename_boundary.py -q

# the corpus pin -> 1 passed, 38 deselected, exit 0
python -m pytest tests/test_escalation_router.py -m corpus -q

# the instrument -> every headline number reproduced, exit 0
python -m tools.phase2_trigger_split
python -m tools.phase2_trigger_split --densities        # exit 2 — the flag does not exist (MINOR-1)

# regression floor -> exit 0, newly validated 0, preserved 36/36 payload-identical
python -m tools.cohort_replay \
  --run "<repo>/discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a" \
  --data-dir "<repo>/.claude/recovery/webapp_data_train9_cold" \
  --shas <scr>/cohort_shas.txt --expect-identical      # 179 Tesseract + 13 R shas

# BLOCK-1, reproduction 1 (real runner, native validated document)
python - <<'PY'
import discovery.runner as R
from discovery.inventory import DedupIndex
from pathlib import Path
row = R.DiscoveryRunner(Path("<repo>/Bank Statements"), mode=R.MODE_DIGITAL, run_id="review",
                        sink=None, cache=None, dedup=DedupIndex(), visual_escalation=False
                        ).process("<a low-density BMO native statement>", "BMO")
print(row.content_sha256[:16], row.source_path, row.dispatch_outcome,
      row.outcome_class, row.evidence_quality, repr(row.failure_class))
# -> E3C98E2252BE3E70 native claimed validated unusable 'A'
PY

# BLOCK-1, reproduction 2 (dry-run committed-artifact rung)
#   DiscoveryRunner(CORPUS, mode=MODE_DRY_RUN, ...).process("Misc/First Farmers 2026 01-document.pdf","Misc")
#   -> source_path committed_artifact | outcome_class validated | evidence_quality unusable | failure_class 'A'

# BLOCK-1, the census (real gate + real classify_failure over rows.csv + the read-only cold cache)
#   -> 79 validated documents with failure_class == "A"; 176 Class-A rows in total

# MAJOR-1: install a module exporting P20-SEAM's real contract, refusing everything
#   EscalationRouter.decide(...) -> Escalation(extractor='visual', ...), check_endpoint never called
```

---

## 6. Verdict

**BLOCK.**

The architecture this card exists to build is, in its load-bearing part, correct and genuinely
enforced: the router is blind to the validator by type and by import graph; `stop` is the only
verdict-shaped input and is monotone; Class B and Class C cannot reach a trigger on any live path;
T is defined and refused; every escalation edge I could invent is killed by a named test; the
frozen 2,625 are untouched (36/36 preserved payload-identical on the OCR cohort, 0 newly
validated). The cell's two flagged readings of ambiguous card text are both the right call, and I
would rule the same way in both directions.

What blocks is the **label**, not the edge. `classify_failure` grades evidence before it grades
the validator's verdict, and the gate's fourth criterion — measured on 179 Tesseract reads —
is applied to 3,172 native reads and to the dry run's committed-artifact rung, where a
document with no `StatementMarkdown` object is reported as `no_text_produced`. The result,
reproduced twice through the real `DiscoveryRunner` and measured across the whole run of
record, is 176 Class-A rows where the cell reports a legal escalation population of 36 — including
**79 documents that the deterministic validator proved**. That is precisely the row vocabulary
Phase 2.1 will read to decide what may return to an extractor, and it falsifies a completion
criterion the umbrella card lists as binding.

Close BLOCK-1 and the three MAJORs (the endpoint seam's real contract before B2 and A meet at
the train; the density floor pinned in the default suite and honestly characterised for Gustavo;
the vocabularies actually enforced or the claim withdrawn), then re-review. The MINORs are
cheap and should ride along, MINOR-6 and MINOR-7 in particular, because both are one-line
widenings of guards that already exist.
