# PHASE2_P21ROUTING_REVIEW — independent adversarial review of `wave21-routing` (cell R, P21-ROUTING)

```
VERDICT: APPROVE WITH FINDINGS
REVIEWER: an independent Opus agent that did not write this branch
TIP REVIEWED: d2098c2   BASE: 6749627   DIFF: 25 files, +2,095 / -150 (1,878 added lines outside docs/)
WORKTREE: .claude/worktrees/rev21-routing (detached at d2098c2; clean but for this file)
HOST: Windows, Git Bash, Python 3.14.5 (CI pins 3.12); PaddleOCR NOT installed locally
NETWORK: the Vast host was never contacted. Every probe below ran against loopback or nothing at all.
FINDINGS: 0 BLOCK · 4 MAJOR · 7 MINOR
```

The routing safety properties this card exists to establish — **no Class B → Paddle edge, no Class C →
Paddle edge, no validator-driven escalation, no auto-mode / `force_ocr` → Paddle hop, no customer
document to a remote worker, no Paddle material in the offline cache key** — I attacked directly and
could not break. Every one reproduced under my own instrumentation, including a socket-level egress
spy that recorded **zero** connections on the customer-scope refusal path, and a 32-shape sweep of
`parse_statement`'s flag space. **All sixteen of the cell's mutants are genuinely killed**, which I
re-applied and re-measured myself.

The four MAJORs are **unpinned or mis-stated protection**, not broken protection. Three of my own
thirteen mutants survive the entire relevant suite because the artifact-record contract D6 specifies
has no test at all; a fourth survives because the gate the card names as CASE 9's killer is unpinned;
a repo-wide tripwire's stated property is false in the tree it guards; and a ruled design item is
implemented for one rung of four while the code's own docstring claims all four.

---

## 1. Claim-by-claim (claimed → what I measured)

| # | the cell claims | what I measured | verdict |
|---|---|---|---|
| 1 | cases 1–4, 9, 10, 12, 14, 15, 18, 19, 20 proved through the real `DiscoveryRunner` with the in-process fake worker | `pytest tests/test_paddle_routing.py -q` → **21 passed** in 19.39 s. CASE 14 is a unit test in `test_q3_native_only.py` and CASE 15 is the guard file (both as the card directs); CASE 9's adoption leg is a directly-mocked `read_document` (the cell declares this in its Risks); CASE 19 is the replay, which I did not re-run | TRUE, with the cell's own declared narrowing |
| 2 | `RouterInputs.enabled` as a sixth field with a repo-wide AST tripwire that every `enabled=` is `self.<attr>` or a module constant | field set is exactly the six names; `router_inputs` is keyword-only with six parameters; `test_every_enabled_argument_is_a_mode_fact_never_a_per_document_expression` exists and **kills** my M3 mutant | TRUE (see MINOR-6 for what the tripwire does *not* see) |
| 3 | `parse_statement(allow_paddle_ocr, paddle_data_scope)` on the forced path only; the non-forced ladder byte-identical and never importing `ocr.paddle_rung` | I drove **all 32 combinations** of `(force_ocr, allow_local_ocr, allow_visual_ocr, allow_paddle_ocr) × (paddle_data_scope ∈ {None, "customer"})` through `parse_statement` with `sys.modules` cleared between calls. `ocr.paddle_rung` / `ocr.paddle_client` are imported in **exactly the 2 of 32** shapes that are `force_ocr ∧ allow_paddle_ocr ∧ ¬allow_visual_ocr ∧ scope≠None`; `allow_paddle_ocr=True` with `force_ocr=False` is inert in all 8 of its shapes; both extractors together → `ValueError`; scope `None` → `ValueError` before any import. The `git diff` of `ocr/escalation.py` touches only `EXTRACTOR_ORDER`, the sixth field, the constructor and `decide`'s list comprehension — `ADMITTED_TRIGGERS`, `ALL_TRIGGERS`, `TRIGGER_REPORT_PRIORITY`, `CHAR_FLOOR`, `ALNUM_DENSITY_FLOOR` and `ExtractionQualityGate` are unchanged | TRUE |
| 4 | `--scanned-paddle` mode | mode wired; in `LOCAL_OCR_MODES`; mutually exclusive argparse group; preflight refuses with a closed token and **never prints a host** (measured: `paddle_remote_opt_in_required`, `paddle_config_missing`, rc 2 both times; `--no-visual-escalation --digital` → the new combined message, rc 2) | TRUE (untested — MINOR-4) |
| 5 | `_read_paddle` with the AST-pinned literal `"customer"` | pin present and AST-real: killed by a `"synthetic"` swap (M4), by a string built from parts (`"synth" + "etic"`, a `BinOp` — RX7) and by a module-level `Name` (RX8) | TRUE |
| 6 | `StatementMarkdown.page_extractor` / `evidence` with construction-time consistency | all five hostile shapes refuse at construction (`pages ≠ evidence.page_texts()`, page-count mismatch, `page_extractor` length mismatch, invalid token, wrong evidence type). **But** `page_extractor` is populated only by the Paddle rung | PARTLY TRUE — MAJOR-3 |
| 7 | `EXTRACTION_SCHEMA_VERSION` 1→2 with the Paddle truth-table branch and key block | version is 2; `_ocr_extractor` measured over all 8 boolean combinations; the paddle key block contains only the D5 pins + provider + execution class + extractor identity | TRUE |
| 8 | the offline key changed — and only by the new field and the schema version, not by any Paddle material | reproduced exactly: rebuilding today's offline key material with `allow_paddle_ocr` removed and `extraction_schema_version` set back to 1 yields **`32F00F24…`** — the Phase 2.0 cold cache's recorded offline key. Today's is `B3F8D008…`. Neither the offline nor the visual key material carries a `paddle` block | TRUE |
| 9 | the Paddle key refuses when Paddle settings cannot load and NEVER contains host/port/token/url | with no `PADDLE_*` env: `PaddleConfigError: required Paddle configuration variable PADDLE_PROVIDER is not set`. With a fabricated env (host `probe-host.invalid`, port `31337`, user `probe-user`, token `PROBE-TOKEN-XYZ`) the serialized key material contains **none** of the four | TRUE |
| 10 | `"paddle"` source path without touching `FREE_MODELS` | `SOURCE_PATHS == ("native","local_tesseract","paddle","visual","none")`; only the exact token maps to `"paddle"`; `"paddle"`, `"paddle+x"`, `"paddle-ocr+ppocrv5x"` and the upper-cased token all → `"none"` + `source_path_unrecognized_model=True`. `FREE_MODELS` unchanged (4 members); `price_for(token)` → `None` | TRUE |
| 11 | `WORKER_ENABLED_EXTRACTORS == {"visual"}` | confirmed; no `allow_paddle_ocr` keyword anywhere in `webapp/worker.py`; the webapp's one `decide(` site passes the module constant | TRUE |
| 12 | M1–M16 all killed | **reproduced: 16/16 KILLED**, every one re-applied by me as the card words it (§4). I added 13 mutants of my own: 8 killed, **5 survived** | TRUE, and incomplete — §4 |
| 13 | guards + conformance 1,557 | **reproduced exactly**: 5 canonical guards **275 passed**; 7 canonical conformance files **1,282 passed, 41 skipped**; 275 + 1,282 = **1,557** | TRUE |
| 14 | full suite 8,663 · gate 105/3/1 · corpus slice 34 · cohort replay 2,625/2,625 at base and closure | not re-run (the brief forbids it without cause). The nine named files → **438 passed, 3 deselected**; the eleven-file mutation baseline → **507 passed, 5 deselected** | not contradicted |
| 15 | privacy 0 over 2,095 added lines | re-run by me against the Phase 2.0 run of record and the read-only `webapp_data_train10_cold`: `added_lines: 2095`, `documents_read: 3351`, `population: 3380`, printed tokens `MONEY 354,835 / DIGITS 208,695 / WORDS 416,756 / DATES 3,211`, **`hit_count: 0`** (`raw_hit_count: 7`, all seven excluded by `words_class`), `residue_files: 0`, exit 0. The cell's `1878` is the same scan over added lines outside `docs/`; `git diff --numstat` gives 2,095 total and 1,878 excluding `docs/` — both figures are correct and mean different things | TRUE |
| 16 | secrets 0 | reproduced independently: `PADDLE_VAST_HOST` (14 chars) **0** hits in the diff and **0** in the four commit messages; `PADDLE_VAST_SSH_PORT` (5 chars) **0** / **0**; `PADDLE_VAST_SSH_USER` is 4 characters and is not scannable without pure noise (the same limitation the cell reported honestly). The only IPv4 literal in any added line is `127.0.0.1` (×1). `.env.paddle.example` carries no secret value | TRUE |
| 17 | `tests/test_visual_rung.py` 32/32 unchanged in meaning | `^def test_` in `git show 6749627:tests/test_visual_rung.py` = **32**; at `d2098c2` = **32**; one `@pytest.mark.parametrize` in each; pytest collects **35 passed** at the tip. The diff touches one assertion inside one existing test | TRUE |

---

## 2. Findings

### MAJOR-1 — the D6 artifact record has no test at all, and a drifted cached read is a *silent, self-erasing* miss

`webapp/artifact_cache.py:1209-1214` (the `except` clause around the `StatementMarkdown`
reconstruction in `cached_ocr`) and `webapp/artifact_cache.py:1076-1077` (`put_ocr`).

The card's design item 5 requires that `cached_ocr` "restores both … a drifted cached copy raises, and
THAT is surfaced as a cache **miss-with-finding**, never served"; D6's test list requires "round-trip
`put_ocr`/`cached_ocr` with evidence; a cache hit reproduces `evidence` sha byte-for-byte"; and case 19
requires that a schema-1 record "must still load them (`page_extractor` absent → `[]`, `evidence`
absent → `None`), **which is itself a test**."

**None of those three tests exists.** `git diff 6749627..d2098c2 -- tests/test_artifact_cache.py` adds
the `_ocr_extractor` Paddle truth table, `allow_paddle_ocr` partitioning, the paddle key block, the
paddle key's refusal, a source-order scan, the `EXTRACTION_SCHEMA_VERSION == 2` pin and the
`FREE_MODELS` pin — plus one line inside `test_round_trip_for_every_stage` that pins the two new keys
as `[]` / `None` on a document that has neither. Nothing anywhere under `tests/` puts a real
`ExtractionEvidence` through `put_ocr`/`cached_ocr`, stores a drifted blob, or restores a schema-1
record.

**Reproduction — the behaviour is correct, it is simply unpinned.** I wrote the three missing proofs
myself against the real `ArtifactCache(Storage(tmp))`:

```
== round-trip with evidence ==
  computes: 1   second cached: True
  restored page_extractor: ['paddle-ocr+ppocrv5']
  restored evidence is not None: True
  evidence sha reproduces: True
  stored record keys: ['evidence', 'model', 'page_extractor', 'page_integrity', 'pages']
== schema-1 record (no page_extractor / evidence keys) still loadable ==
  cached: True  computes: 0  pages: ['legacy page']  page_extractor: []  evidence: None
== drifted cached evidence blob (stored pages != stored evidence) ==
  cached: False computes: 1  pages served: ['HELLO WORLD']   # the fresh compute, not the drifted record
== corrupt evidence blob (bad json shape) ==   cached: False computes: 1
== evidence blob that is a list / a string ==  LISTKEY: cached=False computes=1 ; STRKEY: cached=False computes=1
```

Nothing raised out of `cached_ocr` in any of the five hostile shapes. And three mutants confirm the
consequence — each ran against the eleven-file set whose clean baseline is 507 passed:

* **RX1** — the `except` clause serves the drifted record instead of falling through: **SURVIVED,
  507 passed.**
* **RX2** — `cached_ocr` never restores `evidence` (always `evidence=None`): **SURVIVED, 507 passed.**
* **RX3** — `put_ocr` never stores `page_extractor` (always `[]`): **SURVIVED, 507 passed.**

Second half of the finding, independent of the tests: the card asks for a **finding**; the code
produces **silence**. `except (EvidenceError, ProvenanceTokenError, TypeError, KeyError): pass` emits
nothing — no counter, no row field, no log — and the very next statement, `cache.put_ocr(...)`,
**overwrites the drifted entry**, destroying the only evidence that a drift ever existed. A caller
cannot distinguish "this artifact was corrupt" from "this artifact was never cached". For a cache
whose contents feed the deterministic validator, "we silently repaired a corrupted artifact and erased
the proof" is exactly the shape this project refuses everywhere else.

**Fix required.** (a) Add the three tests the card names — round-trip with evidence and sha
reproduction; drift → miss, never served, never raised out of the runner; a schema-1 record restoring
as `[]` / `None`. (b) Make the drift a *finding*: carry it out of `cached_ocr` (a `CacheResult` field,
or a distinct disposition beside `hit`/`miss`/`bypass` that `_disposition` can render on the row) so a
drifted artifact is counted rather than silently overwritten.

### MAJOR-2 — the repo-wide `allow_paddle_ocr=True` tripwire is blind to `tools/train/provenance.py`, which contains a second real call site; the assertion is true only by that blindness

`tests/test_paddle_routing.py:407-420`
(`test_case12_allow_paddle_ocr_true_appears_only_at_the_one_reviewed_call_site`) vs
`tools/train/provenance.py:113-116`, inside the `_TREE_PROBE` string that begins at
`tools/train/provenance.py:65`.

The test asserts `offending_files == {"discovery/runner.py"}` and its docstring states "the ONLY file
that ever passes `allow_paddle_ocr=True` is `discovery/runner.py`". That statement is **false in this
tree**: the same cell added

```
        partitions["paddle_ocr_key"] = ac.ocr_settings_key(
            force_ocr=True, allow_local_ocr=False, allow_visual_ocr=False,
            allow_paddle_ocr=True,
        )
```

at `tools/train/provenance.py:113-116`. The test does not see it because that code lives inside
`_TREE_PROBE`, a raw string holding a whole program that `provenance.py` executes in a subprocess with
`cwd=<checkout>`, i.e. with the tree's full code importable.

**Reproduction** — the file *is* inside the scan's scope; this is a parser blind spot, not an
exclusion:

```
files scanned: 303
tools/train/provenance.py in scan: True
grep -c allow_paddle_ocr tools/train/provenance.py   ->  1   (line 115)
ast.parse(...)  ->  ast.keyword nodes named 'allow_paddle_ocr': 0
offending files: {'discovery/runner.py'}
```

The same blindness covers the inherited `decide(` call-site scan and `EXPECTED_DECIDE_CALL_SITES`: a
`decide(...)`, a `router_inputs(...)`, or a `parse_statement(..., allow_paddle_ocr=True,
paddle_data_scope="synthetic")` written inside `_TREE_PROBE` is invisible to every tripwire this cell
and P20-ROUTER rely on.

The existing call is benign — `ocr_settings_key(allow_paddle_ocr=True)` computes a key, reads no
document and opens no socket (I verified: it reaches `load_paddle_settings` and
`paddle_settings_key_material` only). The defect is the tripwire's, and it is precisely the "a test
named after a gate is not a test of that gate" failure BATCH9-RULES warns about — with the
counter-example created in the same commit range as the tripwire.

**Fix required.** Either (a) extend the repo-wide scan to also `ast.parse` embedded program strings
(`_TREE_PROBE` is the only one today, so a small named list suffices), or (b) change the assertion to
the two reviewed call sites *by name and by reason* — `discovery/runner.py::_read_paddle` (the only
site that reads a document) and `tools/train/provenance.py::_TREE_PROBE` (key computation only, no
document, no socket) — **and** add a scan of the probe string so a third site cannot appear inside it
unnoticed. Leaving a tripwire whose docstring is falsified by the tree it guards is the worst of the
three options.

### MAJOR-3 — `page_extractor` is populated for the Paddle rung only; design item 3 says every rung, and the record's own docstring claims every rung

`ocr/pipeline.py:142` (Paddle) vs `ocr/pipeline.py:88-104` (native / Tesseract) and
`ocr/pipeline.py:207-209` (visual); `webapp/artifact_cache.py:510`.

P21-ROUTING design item 3 is explicit: "The ladder sets `page_extractor` for EVERY rung: native → the
native model token per page, Tesseract → `"local-tesseract-ocr"` per page, visual → `settings.model`
per page, Paddle → the read's list." Only the Paddle arm does it.

**Reproduction:** `grep -rn page_extractor --include=*.py .` outside `tests/` returns writes in exactly
two places — `ocr/paddle_rung.py:234` and `ocr/pipeline.py:142`. The native rung returns
`_native_statement(...)`'s object untouched, the Tesseract rung returns `parse_local_tesseract(...)`'s,
and the visual rung's `StatementMarkdown(...)` at `ocr/pipeline.py:207` passes no `page_extractor`.
Every non-Paddle read therefore stores `"page_extractor": []` — which the record's own docstring at
`webapp/artifact_cache.py:510` describes as "`page_extractor` (per-page provenance, **every rung**)".

No correctness consequence today (the field is write-only; nothing reads it back yet, and
`to_markdown()` does not touch it) — which is exactly why it is worth fixing **now**:
`EXTRACTION_SCHEMA_VERSION` 2 is already invalidating the whole OCR partition at the train's cold run,
so populating the other three rungs costs one cold run instead of two. Left as is, schema 2
permanently means "per-page provenance exists for Paddle and is empty for everything else", and the
later card that fills it needs its own schema bump and its own cold run.

The cell's W3 §Risks names three deviations honestly (the `offline_source_model` widening, the CASE 9
mock, the cold-run cost). This one is not among them.

**Fix required.** Either set `page_extractor` on the three remaining rungs as the card specifies (with
a pin per rung), or record the narrowing explicitly in the W3 section **and** correct the
`EXTRACTION_SCHEMA_VERSION` docstring so it stops claiming a property the code does not have.

### MAJOR-4 — `_upgrade_eligible` — the gate the card names as CASE 9's killer — is unpinned; `return True` survives the whole relevant suite

`discovery/runner.py:854-880` (the gate) and `tests/test_paddle_routing.py:311-326` (the test that
claims it).

The card's design item 8 says: "a mutant that adopts the Paddle read when the offline one had a
payload is killed by the `stop`/`_upgrade_eligible` tests: a claimed offline read is never escalated."
`test_case9_a_claimed_offline_read_is_never_escalated_to_paddle`'s docstring repeats it:
"`_upgrade_eligible` (unchanged by this cell) refuses on `payload is not None` alone."

**Reproduction (RX5).** I replaced the whole body of `_upgrade_eligible` with `return True` and ran the
nine-file set whose clean baseline is 387 passed: **SURVIVED, 387 passed, 4 deselected.** Not one test
in `tests/test_paddle_routing.py`, `tests/test_visual_rung.py`, `tests/test_escalation_router.py`,
`tests/test_discovery.py` or the rest notices.

The reason is instructive, and it is good news for the invariant even as it falsifies the claimed
killer: with the claimable Tesseract fixture the evidence is **usable**, so `upgrade_triggers` is empty
and the **router** refuses with `no_admitted_trigger` long before eligibility is consulted. The
property CASE 9 asserts is real; the mechanism the card credits is not the one enforcing it in any
test.

What is therefore untested is exactly the combination `_upgrade_eligible` exists for: **unusable
evidence *and* an already-claimed payload** — the one shape where a Class-A trigger *is* admitted and
only this gate stops the escalation. That is the "validator success may STOP escalation" half of the
governing invariant, at its only implementation site, with no killer. The same run also leaves the
gate's two documented exclusions (a D-3 analysis cache hit; a parser crash) unpinned for the Paddle
path.

**Fix required.** Add a test that reaches the gate: a below-floor Tesseract read (so the router admits
`extractor_output_unusable`) whose analysis nonetheless yields a payload — monkeypatch
`DiscoveryRunner._analyse` to return one, or drive a `DispatchCollector` that reports `claimed` — and
assert `paddle_rung == "not_attempted"` with the fake worker at zero requests. Then correct
`test_case9_a_claimed_offline_read_is_never_escalated_to_paddle`'s docstring to say what it actually
proves (the router's trigger set refuses it) so the two mechanisms are not conflated again.

### MINOR-1 — `DiscoveryRunner.allow_paddle_ocr` is dead, and its comment describes behaviour it does not have

`discovery/runner.py:613-619`. The comment says `allow_paddle_ocr` "gates the offline read's cache-key
shape exactly as `allow_visual_ocr` does for the visual mode". It does not: `_read` passes neither it
nor anything derived from it (correctly — the offline partition must not vary by mode), and
`grep -rn allow_paddle_ocr` shows the attribute is assigned and never read anywhere in the repo. Fix:
delete the attribute, or keep it and say what it is (a mode predicate nothing consumes yet).

### MINOR-2 — eight of the nine closed `REFUSAL_REASONS` never reach a row

`discovery/runner.py:816-819` (`_read_paddle`'s error mapping), `discovery/runner.py:1059-1067`
(recovery) and `discovery/runner.py:1177-1180` (upgrade). Only `remote_customer_data_refused` gets its
own row token. Every other `PaddleRefused` — `paddle_config_missing`, `paddle_remote_opt_in_required`,
**`paddle_runtime_mismatch`** (the silent-PP-OCRv6 hazard D5 exists to catch),
`paddle_worker_url_not_loopback`, `paddle_frame_mismatch`, `paddle_evidence_malformed` — collapses to
`paddle_rung=failed`, `outcome_reason=ocr_failed`, `error_type="PaddleRefused"`. **Measured** on the
real runner with a `remote_paid` config and no opt-in literal: `paddle_rung: failed  outcome: failed
ocr_failed  error_type: PaddleRefused`. The class name distinguishes a refusal from a transport
failure, but the *reason* — the point of a closed vocabulary — is lost. The card mandated only the one
token, so this is a diagnostic gap, not a deviation. Fix: carry `exc.reason` into `error_type` (or a
new column) for every `PaddleRefused`.

### MINOR-3 — the paddle branch of `model_calls_for` has no test

`telemetry/record.py:490-506`. `tests/test_telemetry.py` gains two tests (the `source_path_for`
fallthrough and the literal-mirror pin) and neither touches `model_calls_for`'s new `elif path ==
"paddle"` arm, which design item 4 names explicitly ("one call per Paddle page, `purpose:
"paddle_ocr"`, the unpriced model named"). `source_section`'s three new fields
(`telemetry/record.py:308-310`) are covered indirectly through the runner by
`test_case9_upgrade_adopts_a_paddle_read_no_fusion` (and my RX13 mutant confirms that projection is
pinned); `model_calls_for`'s arm is covered by nothing.

### MINOR-4 — the `--scanned-paddle` CLI preflight has no test

`discovery/cli.py:243-255`. I verified the behaviour myself: with a `vast.ai` declaration and no opt-in
literal it prints `discovery: --scanned-paddle cannot start. paddle_remote_opt_in_required` and returns
2; with no Paddle config at all, `paddle_config_missing` and 2; and `--no-visual-escalation --digital`
prints the new combined message and returns 2. **No host, port or user appears in any of them**, and
`probe()` returns only closed vocabulary tokens. But `grep -rn scanned_paddle tests/` finds no CLI test
at all, so a regression that skipped the probe, or printed `<HOST>` beside the reason, would be caught
by nothing.

### MINOR-5 — `tools/train/provenance.py` writes `str(exc)` verbatim into the run record

`tools/train/provenance.py:117-118`: `partitions["paddle_ocr_key_note"] = f"not recorded:
{type(exc).__name__}: {exc}"` under a bare `except Exception`. Today's realistic exception is
`PaddleConfigError`, whose messages name variables only ("required Paddle configuration variable
PADDLE_PROVIDER is not set" — I reproduced it), so nothing leaks now. The clause is unbounded, though:
any other exception's message goes verbatim into `provenance.json`, the durable run record
`telemetry/run_of_record.py` reads and closure reports quote. Fix: record `type(exc).__name__` plus
`exc.reason` / `exc.args[0]` only when it belongs to a closed vocabulary.

### MINOR-6 — the `enabled=` tripwire is shape-only; a per-document reassignment of `self.enabled_extractors` satisfies it

`tests/test_escalation_tripwires.py:166-206` (`_is_self_attribute` at 167,
`_is_module_level_constant_name` at 175). The latter accepts **any** SCREAMING_SNAKE bare `Name`
regardless of its value, its module, or whether it is module-level at all; the former accepts any
`self.<attr>` regardless of where that attribute was last assigned. Neither pins that
`self.enabled_extractors` is assigned only in `__init__`.

**Reproduction.** RX4 reassigns `self.enabled_extractors` inside `process()` on a per-document basis:
**SURVIVED, 507 passed.** By contrast RX10 — both `decide(` call sites pointed at a wrong module
constant `frozenset({"paddle","visual"})`, which the tripwire happily accepts — is **KILLED (12
failures)** by the visual-rung and escalation-router runner suites.

The exposure is genuinely small, and I want to say so precisely: `enabled` can only ever **narrow**
(`decide` intersects it with `EXTRACTOR_ORDER`, and admission has already happened above it), so a
smuggled per-document fact can *stop* an escalation that was already admitted — it cannot *start* one,
which is the invariant that matters. Two-engine escalation is separately impossible because
`attempted` is fixed and `decide` is called at most once per path. Recorded so a later card does not
mistake the tripwire for more than it is.

### MINOR-7 — the "at most one enabled extractor" pin covers 4 of the 6 modes

`tests/test_paddle_routing.py:423-433` constructs runners for `scanned-visual`, `scanned-paddle`,
`scanned` and `digital` and asserts `len(runner.enabled_extractors) <= 1`. `profile-only` and `dry-run`
are not exercised. The `__init__` expression is structurally ≤1 for every mode, so this is
completeness, not risk.

---

## 3. What I attacked and could not break

* **Class B → Paddle.** A long, legible, genuinely usable, unclaimed Tesseract read
  (`USABLE_UNCLAIMABLE`) through the real runner in `--scanned-paddle` with a live `local_free` fake
  worker: `paddle_rung="not_attempted"`, `escalation_extractor=""`,
  `escalation_refused="no_admitted_trigger"`, `failure_class="B"`, and the fake worker recorded
  **zero** `/ocr` requests. Mutating the upgrade trigger to admit unconditionally (M1) is killed by six
  tests.
* **Class C → Paddle.** A claimed reconstruction forced to fail financial validation:
  `dispatch_outcome="claimed"`, `failure_class="C"`, `paddle_rung="not_attempted"`, zero requests. I
  read every `decide(` argument by AST and found no path by which a financial fact can reach the
  router: both runner call sites pass `stop=False` and a trigger set derived from `EvidenceQuality`
  alone; the webapp's one site passes `stop=analysis is not None`, which is a *stop*, in the permitted
  direction (RX6, removing it, is KILLED by
  `test_force_ocr_decision_stops_the_moment_analysis_exists`).
* **Density and Trigger T.** `PADDED_TABULAR` (density-surfaced, usable) → zero requests,
  `evidence_quality="usable"`, `no_admitted_trigger`. `ADMITTED_TRIGGERS` still excludes
  `TRUNCATION_FLAGGED`; `BELOW_ALNUM_DENSITY_FLOOR` is still a `signals` member only. Ruling B holds.
* **The non-forced ladder.** 32 flag combinations (§1 claim 3). `ocr.paddle_rung` and
  `ocr.paddle_client` are absent from `sys.modules` after an offline-only run, now asserted by
  `tests/test_discovery.py` in a subprocess.
* **The webapp.** No `allow_paddle_ocr` keyword in `webapp/worker.py` (AST); `WORKER_ENABLED_EXTRACTORS`
  is a frozenset literal pinned by two tests; the worker's `decide(` site passes it as a module
  constant; auto mode gains no Paddle arm. Ruling A holds.
* **The privacy boundary, end to end, with a socket-level spy.** I patched `socket.socket.connect` to
  record every address, configured a `vast.ai` / `remote_paid` worker **with** the remote opt-in
  literal set, pointed `PADDLE_WORKER_URL` at a loopback port with nothing listening (so a real request
  would have been recorded even as it failed), and ran the real `DiscoveryRunner` in `--scanned-paddle`
  over an image-only PDF:

  ```
  paddle_rung: refused_customer_data
  outcome: failed paddle_refused PaddleRefused
  escalation_extractor: paddle
  source_path: none
  socket connects observed during the run: []
  ```

  Zero connections — not even `/version`, because `check_remote_authorization` runs before the client
  is constructed. Repeating it with the remote opt-in removed: same zero connections, a different named
  refusal. The second literal (`PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN`) is absent from this session's
  environment and is set by no test; I re-verified it directly. I never contacted the Vast host.
* **The `"customer"` literal pin.** Killed by a `"synthetic"` swap (M4), by a string built from parts
  (`"synth" + "etic"` — RX7) and by a module-level `Name` (RX8). The pin is AST-real, not a grep.
* **`_ocr_extractor` truth table.** All 8 boolean combinations measured: `"paddle"` only under
  `force_ocr ∧ allow_paddle_ocr`; `"visual"` only under `force_ocr ∧ allow_visual_ocr ∧ ¬paddle`;
  everything else `"offline"`.
* **Cache-key separation.** offline `B3F8D008…`, visual `42B2E385…`, paddle `E21326DD…` — all distinct;
  the offline and visual key material carries no `paddle` block, and the paddle-labelled call is the
  only one that touches `ocr.paddle_config`'s loader (pinned by a source-order test).
* **`run_of_record` partitioning.** Measured over 9 row shapes × 2 partition sets: `paddle_rung ∈
  {recovered, upgraded}` → the paddle key and never the visual one; `visual_rung ∈ {recovered,
  upgraded}` → the visual key and never the paddle one; a paddle row on a run with no paddle key →
  `None` (never a fallback to offline or visual); a row with no `paddle_rung` column at all (every
  historical run) → unchanged behaviour. `tools/cohort_replay.py` goes through the same function, so
  historical replays are inert to the change — which is why the base and closure replays are
  structurally identical, exactly as the cell says. Reconstruction for pre-v5 runs is unaffected
  (`stage_version=4` excludes the new key material entirely).
* **Provenance vocabulary.** `RESERVED_MODEL_PREFIXES` gains the token (M15 killed); an env `OCR_MODEL`
  cannot impersonate the rung; `source_path_for` maps only the exact token; a `paddle`-shaped impostor
  is `"none"` + unrecognised; `FREE_MODELS` untouched.
* **Q3.** A Paddle-fed provenance header still refuses (`test_paddle_ocr_refuses_and_fails_closed`), no
  OCR carve-out.
* **CASE 18.** All three transport shapes (connection refused, HTTP 500, malformed JSON) →
  `paddle_rung="failed"`, `outcome_reason="ocr_failed"`, `error_type="PaddleTransportError"`,
  `source_path="none"`, with `_read_visual` monkeypatched to `pytest.fail` — never called. M14 (hop to
  `_read_visual` on transport failure) is killed by all three parametrizations.
* **Row surface.** The seven new columns are appended at the end of `ROW_FIELDS`, in the same order as
  `DocumentRow`, pinned by `ROW_FIELDS[-7:]` and `[-11:-7]`; `as_dict` enforces the closed `paddle_rung`
  and `escalation_extractor` vocabularies; `summarize` counts both like `visual_rung`.
* **Ownership.** All 25 changed files are inside the card's ownership list (12 source, 12 test, the W3
  section). Nothing under `analysis/`, `evidence/`, `ocr/paddle_{client,worker,adapter,rung}.py` or
  `tools/paddle_vast.py` was touched.
* **Statement-specific hardcodes.** The 5 canonical guards → 275 passed. The CASE 15 extension scans
  `evidence/*.py` + `tools/paddle_vast.py` with the same pattern classes and carries a
  non-vacuous-scope test; `ocr/paddle_*.py` was already inside the pre-existing `ocr/*.py` glob.
* **Vacuous-test sweep.** Every mutant in §4 that the cell claims a killer for genuinely fails that
  named killer; no killer I checked passes for an unrelated reason.

---

## 4. Mutation table — every mutant re-applied by me

Harness: exact single-occurrence textual edits, restored in a `finally`, `git status --porcelain`
verified between mutants, one harness at a time on this host. Batch 1 ran the eleven files
`test_paddle_routing · test_escalation_router · test_escalation_tripwires · test_visual_rung ·
test_artifact_cache · test_run_of_record · test_telemetry · test_pipeline · test_q3_native_only ·
test_ocr_provenance_injection · test_discovery` (clean baseline **507 passed, 5 deselected**); batch 2
ran nine of them (clean baseline **387 passed, 4 deselected**); batch 3 ran two.

| # | mutant as I applied it | result | the killer(s) I observed |
|---|---|---|---|
| M1 | `upgrade_triggers` admits `EXTRACTOR_OUTPUT_UNUSABLE` unconditionally (over-admission) | **KILLED** (6 failed) | `test_case2_usable_unclaimed_never_escalates_to_paddle`, `test_case4_density_surfaced_but_usable_never_escalates`, `test_m1_upgrade_triggers_never_admit_on_dispatch_outcome`, `test_case1_usable_unclaimed_tesseract_text_never_escalates`, `test_a_density_surfaced_but_usable_tesseract_read_never_escalates`, `test_usable_evidence_reports_the_same_refusal_whether_or_not_it_was_claimed` |
| M2 | `decide` drops `e in inputs.enabled` | **KILLED** (22 failed) | `test_enabled_narrows_to_paddle_only`, `…_to_visual_only`, `test_an_admitted_trigger_with_nothing_enabled_refuses`, `test_enabled_does_not_add_an_extractor_the_order_does_not_already_name`, + 18 runner/visual-rung tests |
| M3 | the recovery call site computes `enabled` from `recovery_evidence.usable` | **KILLED** (13 failed) | `test_every_enabled_argument_is_a_mode_fact_never_a_per_document_expression` (the AST tripwire) + 12 behavioural |
| M4 | `_read_paddle` passes `"synthetic"` | **KILLED** (2) | `test_read_paddle_passes_the_literal_customer_scope_by_ast`, `test_case1_refusal_leg_remote_paid_refuses_customer_scope` |
| M5 | Paddle branch guard becomes `if allow_paddle_ocr:` (drops `force_ocr and`) | **KILLED** (1) | `test_allow_paddle_ocr_is_inert_on_the_non_forced_path` |
| M6 | Paddle branch gains `from .ocr_client import apply_admitted` | **KILLED** (2) | `test_case10_paddle_branch_never_references_the_postprocess_chain` (AST) **and** `test_case10_a_paddle_read_never_touches_ocr_client_at_runtime` (runtime spy) |
| M7 | `page_extractor` length check disabled | **KILLED** (1) | `test_a_page_extractor_length_mismatch_refuses_at_construction` |
| M8 | `evidence.page_texts() != pages` accepted | **KILLED** (1) | `test_a_drifted_evidence_page_texts_refuses_at_construction` |
| M9 | `_ocr_extractor` returns `"visual"` for the paddle shape | **KILLED** (3) | `test_extractor_is_paddle_only_for_the_forced_paddle_shape`, `test_paddle_labelled_key_carries_the_paddle_settings_block`, `test_a_paddle_labelled_key_refuses_when_paddle_settings_cannot_load` |
| M10 | `EXTRACTION_SCHEMA_VERSION = 1` | **KILLED** (1) | `test_extraction_schema_version_is_pinned_at_2` |
| M11 | `ocr_partition_for_row` returns the visual key for a paddle row | **KILLED** (3) | `test_ocr_partition_for_row_paddle[row0]`, `[row1]`, `test_a_paddle_row_never_resolves_to_the_visual_key` |
| M12 | `source_path_for("paddle-ocr+ppocrv5")` → `"visual"` | **KILLED** (2) | `test_case9_upgrade_adopts_a_paddle_read_no_fusion`, `test_source_path_fallthrough_is_closed_not_a_guess` |
| M13 | `PADDLE_MODEL_TOKEN` added to `FREE_MODELS` | **KILLED** (1) | `test_paddle_model_token_is_not_in_free_models` |
| M14 | `_read_paddle` returns `self._read_visual(...)` on any non-refusal exception | **KILLED** (3) | all three parametrizations of `test_case18_transport_failures_fail_closed_with_no_second_attempt` |
| M15 | `RESERVED_MODEL_PREFIXES` without the Paddle token | **KILLED** (1) | `test_env_value_impersonating_the_paddle_rung_is_refused` |
| M16 | `WORKER_ENABLED_EXTRACTORS = {"visual", "paddle"}` | **KILLED** (4) | `test_case12_worker_enabled_extractors_is_visual_only`, `test_m16_two_engines_enabled_at_once_is_never_constructed`, `test_force_ocr_decision_admits_when_the_offline_ladder_produced_nothing`, `…_when_analysis_did_not_claim` |
| **RX1** | `cached_ocr`'s `except` serves the drifted record instead of falling through | **SURVIVED** (507 passed) | **none** → MAJOR-1 |
| **RX2** | `cached_ocr` never restores `evidence` (`evidence=None`) | **SURVIVED** (507 passed) | **none** → MAJOR-1 |
| **RX3** | `put_ocr` never stores `page_extractor` (always `[]`) | **SURVIVED** (507 passed) | **none** → MAJOR-1 |
| **RX4** | `self.enabled_extractors` reassigned per document inside `process()` | **SURVIVED** (507 passed) | **none** → MINOR-6 |
| **RX5** | `_upgrade_eligible` → `return True` | **SURVIVED** (387 passed) | **none** → MAJOR-4 |
| RX6 | the webapp's `stop=analysis is not None` → `stop=False` | **KILLED** (1) | `test_force_ocr_decision_stops_the_moment_analysis_exists` |
| RX7 | `paddle_data_scope="synth" + "etic"` (an `ast.BinOp`, not a `Constant`) | **KILLED** (2) | the AST literal pin + the refusal leg |
| RX8 | `paddle_data_scope=_SCOPE` (a module-level `ast.Name`) | **KILLED** (2) | the same two |
| RX9 | `GATE_ASSESSED_SOURCES` loses `"paddle"` | **KILLED** (1) | `test_gate_assessed_sources_are_exactly_tesseract_visual_and_paddle` |
| RX10 | both `decide(` call sites take a wrong module constant `frozenset({"paddle","visual"})` (shape-legal for the tripwire) | **KILLED** (12) | the visual-rung and escalation-router runner suites |
| RX11 | `visual_escalation` no longer gated on `enabled_extractors` | **KILLED** (2) | `test_the_dry_run_reads_scanned_statements_from_committed_artifacts`, `test_a_real_account_number_never_reaches_the_row` |
| RX12 | the `refused_customer_data` row branch removed (folded into the generic failure) | **KILLED** (1) | `test_case1_refusal_leg_remote_paid_refuses_customer_scope` |
| RX13 | `evidence_sha256` never projected onto the row | **KILLED** (1) | `test_case9_upgrade_adopts_a_paddle_read_no_fusion` |

**Totals: the card's 16/16 killed (the cell's claim reproduced). Of my 13: 8 killed, 5 survived.**
The tree was `git status --porcelain` clean after every batch (this review file excepted).

---

## 5. Proof floor I re-ran myself

| proof | command | result |
|---|---|---|
| the cell's own test file | `pytest tests/test_paddle_routing.py -q` | **21 passed**, 19.39 s |
| the nine named files | `pytest tests/test_escalation_router.py tests/test_escalation_tripwires.py tests/test_visual_rung.py tests/test_artifact_cache.py tests/test_run_of_record.py tests/test_telemetry.py tests/test_pipeline.py tests/test_q3_native_only.py tests/test_ocr_provenance_injection.py -q` | **438 passed, 3 deselected**, 26.46 s |
| `tests/test_visual_rung.py` alone | `pytest tests/test_visual_rung.py -q` | **35 passed** (32 functions, one parametrized) |
| 5 canonical guards | `pytest tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py -q` | **275 passed** |
| 7 canonical conformance files | `pytest tests/test_parser_conformance.py tests/test_parser_registry_entries.py tests/test_parser_detection_markers.py tests/test_parser_registry.py tests/test_parser_crash_shapes.py tests/test_parser_exception_boundary.py tests/test_count_semantics.py -q` | **1,282 passed, 41 skipped** (275 + 1,282 = **1,557**, the cell's figure) |
| mutation baseline (11 files) | as §4 | **507 passed, 5 deselected** |
| privacy scan | `python tools/privacy_scan_branch.py --data-dir <main>/.claude/recovery/webapp_data_train10_cold --base 6749627 --ref d2098c2 --rows <run>/rows.csv --run <run>` | **`hit_count: 0`** (`raw_hit_count: 7`, all 7 `words_class`); `added_lines: 2095`; `documents_read: 3351` of `population: 3380`; `residue_files: 0`; exit 0 |
| secrets scan (mine) | added lines and `git log 6749627..d2098c2 --format=%B` vs every `PADDLE_VAST_*` value in the environment | `PADDLE_VAST_HOST` **0/0**; `PADDLE_VAST_SSH_PORT` **0/0**; `PADDLE_VAST_SSH_USER` 4 chars, unscannable; only IPv4 in added lines is `127.0.0.1` |
| not re-run (per the review brief) | full suite · `corpus_gate.py` · `pytest -m corpus` · the cohort replays | — |

No `discovery_reports/` artifact, cold cache, or archive file was written by anything I ran; the two
cold caches were opened read-only by the privacy scan only.

---

## 6. Verdict

**APPROVE WITH FINDINGS.**

Nothing I could construct made a Class-B or Class-C document reach PaddleOCR, made the auto path or
the webapp reach it, made a customer-scope document leave the machine, or put Paddle material into the
offline cache key. The router's `enabled` field is a narrowing filter — the safe direction; the
ladder's Paddle arm is unreachable without `force_ocr`; the refusal fires before any socket is opened;
and the offline key's change reproduces, exactly, as the two new non-Paddle fields. The card's sixteen
mutants are all genuinely killed, and the guards/conformance and privacy numbers reproduce to the unit.

All four MAJORs are *proof* defects rather than *behaviour* defects, and each has a bounded fix: add
the three artifact-record tests D6 names and make the cache drift a counted finding instead of a silent
overwrite (MAJOR-1); make the `allow_paddle_ocr=True` tripwire see — or honestly name — the second call
site the same cell created inside `_TREE_PROBE` (MAJOR-2); implement design item 3's `page_extractor`
for the other three rungs while the cache is going cold anyway, or declare the narrowing and correct
the docstring that claims otherwise (MAJOR-3); and pin `_upgrade_eligible` with the one shape that
actually reaches it, then stop crediting it for a refusal the router performs (MAJOR-4). None blocks
composition on safety grounds; all four should close before the train, because each is a place where
this branch's own documentation currently promises more than the branch delivers.

---

## Re-review

```
VERDICT: APPROVE WITH FINDINGS
RE-REVIEWER: an independent agent that wrote neither the branch nor the first review
TIP RE-REVIEWED: 97ab9cb (closure)   REVIEWED TIP: d2098c2   BASE: 6749627
CLOSURE DIFF: d2098c2..97ab9cb — 15 files, +1,046 / -59 (3 commits: 5767910, db0071e, 97ab9cb)
WORKTREE: .claude/worktrees/rev21-routing (detached at 97ab9cb; `git status --porcelain` clean but for this file after every mutant and every script)
HOST: Windows, Git Bash, Python 3.14.5 (CI pins 3.12); PaddleOCR NOT installed; the Vast host was never contacted — every Paddle request went to the in-process fake worker on loopback
RESIDUAL FINDINGS: 0 BLOCK · 1 MAJOR · 3 MINOR
```

Every one of the first review's five surviving mutants (RX1, RX2, RX3, RX4, RX5) now dies, each re-applied by
me as a textual edit, restored in a `finally`, with a clean `git status --porcelain` verified after each. The
four MAJORs and seven MINORs are genuinely closed as *claimed*. Attacking the closure itself found one new
defect in the code the closure added: the `cache_finding` column it introduced for MAJOR-1 **leaks a drift
observed on one document onto every later document in the same run** that does not re-run that rung — a
false finding on the wrong row, reproduced through the real `DiscoveryRunner`. No safety property is touched
by it (it changes no routing, no escalation, no payload); it is the MAJOR-1 fix being wrong on the second
document, not the first.

### 1. Finding-by-finding: first-review finding → the cell's closure → what I measured

| first-review finding | the cell's closure | what I measured at 97ab9cb |
|---|---|---|
| **MAJOR-1** D6 record untested; drift a silent, self-erasing miss (RX1/RX2/RX3 survived 507) | `CacheResult.finding` + `CACHE_FINDING_EVIDENCE_DRIFT`; `DocumentRow.cache_finding` projected after all five `_read*` sites; three artifact-cache tests + one runner test | **RX1** (serve the drifted record) → **KILLED**, 2 failed / 108 passed (`test_cached_ocr_treats_a_drifted_evidence_blob_as_a_miss_with_a_finding`, `test_a_drifted_cache_entry_surfaces_as_cache_finding_on_the_row`). **RX2** (`evidence=None` on restore) → **KILLED**, 2 failed (round-trip + drift tests). **RX3** (`put_ocr` stores `[]`) → **KILLED**, 1 failed (round-trip test). By AST I found exactly 5 `self._read*(` call sites in `process()` (lines 1034, 1118, 1140, 1234, 1267 — and none elsewhere in the class); all 5 are immediately followed by `self._project_cache_finding(row)`. The `drifted` flag is set before `put_ocr` overwrites the entry and the finding is returned on the same `CacheResult`. A record whose stored `page_extractor` has the wrong length, or carries a money-shaped token, is likewise refused-and-recomputed with the finding (measured: `cached=False recomputed=1 finding=cached_evidence_drift` for both). **But see residual MAJOR-A below: the projection leaks across documents.** |
| **MAJOR-2** the `allow_paddle_ocr=True` tripwire blind to `_TREE_PROBE` | `_embedded_program_asts` / `_all_asts_for_file`; both repo-wide scans widened; `EXPECTED_ALLOW_PADDLE_OCR_TRUE_SITES` names both files with reasons | The probe IS detected (E6, indenting the existing `_TREE_PROBE` so it no longer parses → **KILLED**, 2 failed: the case-12 pin and `test_the_tree_probe_is_detected_as_an_embedded_program_string`). A clean triple-quoted third site in a fresh file (`discovery/cli.py`, E7b) → **KILLED**; a `+`-concatenated one (E4b) → **KILLED**. Tree measurement: 303 files scanned, 15 carry ≥1 embedded program (14 pre-existing `tools/*` instruments + `tools/train/provenance.py`), none of the 14 contains the keyword. **What the scan does NOT cover** (residual MINOR-B): indented / dedent-style strings, f-strings, `%`-templates, bytes literals, nested programs, and — at direct sites — `**{"allow_paddle_ocr": True}` and non-`Constant` truthy values; and the assertion is per-FILE, so a second site inside an already-named file passes (E7). |
| **MAJOR-3** `page_extractor` populated for Paddle only | native/Tesseract: `[native.model] * len(native.pages)` at the offline ladder's one exit; visual: `[settings.model] * len(pages_out)`; four pipeline assertions; no schema change | Native rung with pages `["native text page", "", "third"]` → `page_extractor == ['native-pdf-text'] * 3`, one token per page including the empty page (measured). A 3-page visual `StatementMarkdown` (with an empty middle page) through `put_ocr`/`cached_ocr` → `cached=True`, `page_extractor` restored as the 3-element list, stored record keys `['evidence','model','page_extractor','page_integrity','pages']`. `EXTRACTION_SCHEMA_VERSION` stays 2 (pin unchanged). Replay: see §4. |
| **MAJOR-4** `_upgrade_eligible` unpinned; `return True` survived 387 | docstring corrected; `escalation_refused == "no_admitted_trigger"` asserted; a standing negative control; the real killer with a below-floor read + monkeypatched `_analyse` | **RX5** (`return True`) → **KILLED**, 1 failed / 28 passed in `tests/test_paddle_routing.py` (`test_upgrade_eligible_refuses_an_unusable_but_already_claimed_read`). **Instrumented**: with the real gate wrapped by a spy under exactly that fixture shape, the gate was called once with `collector.seen=False, payload is not None=True` and returned `False`; row `trigger='extractor_output_unusable'`, `paddle_rung='not_attempted'`, `escalation_extractor=''`, fake `/ocr` requests **0**. Forcing the gate to `True` flips the same run to `paddle_rung='upgraded'`, `escalation_extractor='paddle'`, **3** fake requests. The killer reaches the gate and its assertion is load-bearing. |
| **MINOR-1** dead `allow_paddle_ocr` attribute | removed | `grep -rn "\.allow_paddle_ocr\b" discovery/` → the attribute no longer exists; the closure diff removes the six-line block and adds no reader. |
| **MINOR-2** eight of nine `REFUSAL_REASONS` never reached a row | `paddle_refusal_reason` column, closed-vocabulary validated in `as_dict`; two tests incl. a `paddle_runtime_mismatch` reproduction | `DocumentRow.as_dict()` refuses `'bogus'`, `'PaddleRefused'`, `'paddle_runtime_mismatch\n'`, `'12.34'` (all `ValueError`); accepts all 9 `REFUSAL_REASONS` members and `''`. Non-Paddle rows through the real runner (a recovered Paddle read; a Class-B unclaimed read) carry `''`. The attribute is reset at the top of every `_read_paddle` and projected only after `_read_paddle` — no cross-document leak for THIS column. |
| **MINOR-3** `model_calls_for` paddle arm untested | two telemetry tests | present in the diff; `tests/test_telemetry.py` in the nine-file run (404 passed). Not independently re-attacked. |
| **MINOR-4** CLI preflight untested | `probe_paddle_ocr` imported at module level; three tests | the three tests pass in the nine-file run; the refusal-token test asserts no `127.0.0.1`/`http://`/`ssh`/`.invalid`/`@` in stderr. Not independently re-attacked beyond reading the diff (the import move is behaviour-neutral: same function, same call). |
| **MINOR-5** `str(exc)` verbatim into `provenance.json` | class name only, plus a `.reason` only when it is a `REFUSAL_REASONS` member; a real `collect()` test | read the fix: `reason in REFUSAL_REASONS` is a membership test on the closed tuple, never the message. Observation (pre-existing, outside this closure's scope): the probe's generic `attempt()` wrapper at `tools/train/provenance.py:70` still writes `f"{type(exc).__name__}: {exc}"` for every OTHER probed value; a failure of `run_of_record_partitions` outside the Paddle `try` would still go verbatim. Not a regression of this closure. |
| **MINOR-6** `enabled=` tripwire shape-only (RX4 survived) | AST pin: `self.enabled_extractors` assigned only in `__init__` | **RX4a** (plain `self.enabled_extractors = …` in `process()`) → **KILLED** (`['process:...']`), and a helper METHOD that assigns it (RX4d) → **KILLED**. **Six spellings SURVIVE** the pin: `setattr(self, "enabled_extractors", …)` (RX4b), `self.__dict__["enabled_extractors"] = …` (RX4c), tuple-unpack target (RX4e), `for self.enabled_extractors in (…):` (RX4f), `vars(self)[…] = …` (RX4g), a module-level helper function `_tune_runner(self)` (RX4h) — each 12 passed / 0 failed over `tests/test_escalation_tripwires.py`. Residual MINOR-C. As the first review said, `enabled` can only narrow. |
| **MINOR-7** one-extractor pin over 4 of 6 modes | all six modes iterated | present in the diff; passes. |

### 2. Residual findings

#### MAJOR-A — `cache_finding` leaks from one document onto every later document in the same run (a false finding on the wrong row)

`discovery/runner.py:888-903` (`_project_cache_finding`), with the resets at `discovery/runner.py:727`
(`_read`), `:785` (`_read_visual`), `:848` (`_read_paddle`), and the projection call at `:1035` (after
`_read`, executed for EVERY document).

`_project_cache_finding` reads `self._last_ocr_finding or self._last_visual_finding or
self._last_paddle_finding`. Only `_last_ocr_finding` is reset on every document (inside `_read`);
`_last_visual_finding` / `_last_paddle_finding` are reset only when their own rung runs. `process()` calls
`_project_cache_finding(row)` right after `_read` for every document, so a drift recorded by the Paddle (or
visual) rung on document A is projected onto document B, C, … for as long as that rung does not run again.
`discovery/cli.py:130-139` constructs ONE `DiscoveryRunner` and calls `process()` on it for the whole run, so
this is the production shape, not a test artefact. The method's own docstring ("at most one of the three is
ever truthy for a single call") is true for one document and false for a run.

**Reproduction (real `DiscoveryRunner`, real `ArtifactCache`, `--scanned-paddle`, `local_free` fake
worker, one runner instance, two distinct PDFs — the second is the same fixture with a trailing comment so
its sha differs):**

```
A first pass:            paddle_rung=recovered  cache_finding=''
A second pass (drifted): paddle_rung=recovered  cache_finding='cached_evidence_drift'
   runner state after A: _last_ocr_finding=None  _last_paddle_finding='cached_evidence_drift'
B on the SAME runner (Class B, no escalation, _read_paddle never called):
   paddle_rung=not_attempted  escalation_refused='no_admitted_trigger'  cache_paddle='bypass'
   cache_finding='cached_evidence_drift'          <-- a finding about A, on B's row
B on a FRESH runner:     cache_finding=''
```

No routing, escalation, payload, or `validated` value is affected (the column is write-only diagnostics);
the harm is that the counter MAJOR-1 was fixed to provide now over-counts, and a reader of `rows.csv` will
attribute a drift to documents whose artifacts were never touched.

**Fix.** Reset all three `_last_*_finding` at the top of `process()` — or have
`_project_cache_finding(row, rung)` read only the attribute of the rung that just ran, with `_read`
projecting `_last_ocr_finding` alone. Add a two-document test on ONE runner instance: document A drifted →
finding; document B (no escalation) → `cache_finding == ""`. The existing
`test_a_drifted_cache_entry_surfaces_as_cache_finding_on_the_row` cannot see this because it builds a fresh
runner per `process()` call.

#### MINOR-B — the embedded-program scan and the site pin: what they do not cover

`tests/test_escalation_tripwires.py:381-404` (`_embedded_program_asts`) and
`tests/test_paddle_routing.py:485-506` (`EXPECTED_ALLOW_PADDLE_OCR_TRUE_SITES` + the case-12 pin).

Measured over synthetic shapes and then as live mutants (a third `ocr_settings_key(..., allow_paddle_ocr=True)`
site added to `discovery/cli.py`, a file NOT in the expected set): a clean triple-quoted program → **seen**
(E7b killed); a `+`-concatenation whose fragment is ≥40 chars with a trailing newline → **seen** (E4b
killed); **invisible**: a string with a leading indent (the `textwrap.dedent` style; E2b **survived** —
`IndentationError` is swallowed as `SyntaxError`), an f-string program (E3b **survived**; `JoinedStr` is not
`Constant`), a `%`-format template, a bytes literal, a program nested inside an embedded program (the walk
is one level deep), and — at a DIRECT, non-embedded site — `**{"allow_paddle_ocr": True}` (E8b
**survived**; `keyword.arg is None`) and any non-`Constant` truthy value (`bool(1)`). Separately, the pin is
per-FILE: a second clean site inside `tools/train/provenance.py` (E7) **survived** because that file is
already in the expected set. Tree numbers: 303 files; 1,677 long multi-line string constants the scan cannot
parse; 42 multi-line f-strings never inspected. All of these require a deliberate author, and the one
realistic accident — refactoring `_TREE_PROBE` to a dedented string — is caught by the equality (E6 killed,
2 failed). **Fix:** assert site COUNTS per file (`{"discovery/runner.py": 1, "tools/train/provenance.py":
1}`); `textwrap.dedent` before `ast.parse`; include `JoinedStr` by joining its constant parts with a
placeholder name; treat a `**{...}` dict literal carrying the key with a non-`False` value, and a
non-`Constant` value for the keyword, as offenders.

#### MINOR-C — the `enabled_extractors` assignment pin is spelling-dependent

`tests/test_escalation_tripwires.py:210-252`. Six re-spellings of RX4 survive it (RX4b/c/e/f/g/h above,
each 12 passed / 0 failed), two die (plain attribute assignment; a helper method). The exposure is the one
the first review sized: `enabled` narrows an already-admitted decision and cannot start one. **Fix:** walk
assignment targets recursively (`Tuple`/`List`/`Starred`), include `For`/`With`/`NamedExpr`/comprehension
targets, walk module-level functions as well as the class body, and refuse the string constant
`"enabled_extractors"` anywhere in `discovery/runner.py` outside `__init__` (this kills `setattr`,
`__dict__` and `vars` at once).

#### MINOR-D — a drift followed by a failed recompute loses the finding (and keeps the drifted entry)

`webapp/artifact_cache.py:1241-1248`. When `cached_ocr` detects a drift and `compute()` then raises, no
`CacheResult` is constructed, so the drift is never reported; `_read_visual` / `_read_paddle` catch the
exception and the row shows `error_type` with `cache_finding=""`. Measured: `RuntimeError` propagates,
and afterwards `get_ocr` still returns the drifted pages (`hit=True pages=['drifted']`). The entry is
therefore found again on the next run rather than lost — acceptable, but undocumented in the docstring that
now describes the finding path. **Fix:** either document it, or attach the finding to the raised exception
and let `_read_*` project it from the `except` branch.

### 3. Proof floor I re-ran myself (all at 97ab9cb; `tasklist | findstr python` empty before each harness; one harness at a time)

| proof | result |
|---|---|
| the nine named files: `tests/test_paddle_routing.py tests/test_artifact_cache.py tests/test_escalation_router.py tests/test_escalation_tripwires.py tests/test_visual_rung.py tests/test_pipeline.py tests/test_discovery.py tests/test_run_of_record.py tests/test_telemetry.py` | **404 passed, 4 deselected**, 73.06 s, exit 0 |
| mutation baselines | `test_artifact_cache + test_paddle_routing` **110**; `test_paddle_routing` alone **29**; `test_escalation_tripwires` alone **12**; the case-12 pin alone **1** |
| the 5 canonical guards | **275 passed**, 10.50 s, exit 0 |
| privacy scan (`tools/privacy_scan_branch.py --data-dir <main>/.claude/recovery/webapp_data_train10_cold --base d2098c2 --ref 97ab9cb --rows <run>/rows.csv --run <run>`) | `added_lines: 1046`, `documents_read: 3351` of `population: 3380`, **`hit_count: 0`** (`raw_hit_count: 9`, all 9 `words_class`), `residue_files: 0`, exit 0 |
| secrets scan (mine): the closure diff's 1,046 added lines and the 3 commit messages vs the `PADDLE_VAST_*` values in `os.environ` | `PADDLE_VAST_HOST` (14 chars) **0 / 0**; `PADDLE_VAST_SSH_PORT` (5 chars) **0 / 0**; `PADDLE_VAST_SSH_USER` (4 chars, an all-lowercase common word) 9 whole-word coincidences in added lines and 1 in a message — every one is the ordinary word inside `--<word>`, `<word>.mkdir`, `empty-<word>` (a CLI path argument and a test label), never an assigned value; the only IPv4 literal is `127.0.0.1`; no `user@host` shape; no port near an `ssh`/`port` word |
| ownership | all 15 closure files and all 25 cell files are inside the card's list; `ocr/config.py` diff = `RESERVED_MODEL_PREFIXES` + its one import; `webapp/worker.py` diff = the constant + the `enabled=` argument; no Phase 2.0 tripwire allowlist (`EXCLUDED_FROM_REPO_SCAN`, `EXCLUDED_TREES_FROM_REPO_SCAN`, the `decide(` call-site set) changed; the ONE widened set is `EXPECTED_ALLOW_PADDLE_OCR_TRUE_SITES` (1 → 2 files, with reasons — the first review's fix option) |
| not re-run (per the brief; no finding required it) | the full suite · `corpus_gate.py` · `pytest -m corpus` · the cohort replay |

### 4. The replay numbers under MAJOR-3

`tools/cohort_replay.py:247-249` (`ColdCache.text()`) rebuilds each replayed document from
`document["pages"]` and `document["model"]` only, and it reads the Phase 2.0 cold cache, whose schema-1
records have no `page_extractor` key at all — so a per-page provenance list written by a new read can neither
be read by the replay nor alter a replayed page string, and 3,351 replayed / 2,625-of-2,625 identical / 0
newly validated is the only number the closure replay could have produced.

### 5. Mutation table — every mutant I applied (textual edit; restored in `finally`; `git status --porcelain` clean after each)

| # | mutant | result | killer(s) I observed |
|---|---|---|---|
| RX1 | `cached_ocr`'s `except` returns the drifted record as a hit | **KILLED** (2) | `test_cached_ocr_treats_a_drifted_evidence_blob_as_a_miss_with_a_finding`, `test_a_drifted_cache_entry_surfaces_as_cache_finding_on_the_row` |
| RX2 | `cached_ocr` restores `evidence=None` | **KILLED** (2) | `test_cached_ocr_round_trips_evidence_and_reproduces_its_sha`, the drift test |
| RX3 | `put_ocr` stores `"page_extractor": []` | **KILLED** (1) | the round-trip test |
| RX5 | `_upgrade_eligible` → `return True` | **KILLED** (1) | `test_upgrade_eligible_refuses_an_unusable_but_already_claimed_read` |
| RX4a | `self.enabled_extractors = frozenset({"paddle"})` at the top of `process()` | **KILLED** (1) | `test_discovery_runner_enabled_extractors_is_assigned_only_in_init` |
| RX4d | a helper method `_tune()` assigns it; `process()` calls it | **KILLED** (1) | the same |
| RX4b | `setattr(self, "enabled_extractors", …)` | **SURVIVED** (12 passed) | none → MINOR-C |
| RX4c | `self.__dict__["enabled_extractors"] = …` | **SURVIVED** | none → MINOR-C |
| RX4e | `self.enabled_extractors, _unused = …, None` | **SURVIVED** | none → MINOR-C |
| RX4f | `for self.enabled_extractors in (…): pass` | **SURVIVED** | none → MINOR-C |
| RX4g | `vars(self)["enabled_extractors"] = …` | **SURVIVED** | none → MINOR-C |
| RX4h | module-level `_tune_runner(runner)` assigns it; `process()` calls it | **SURVIVED** | none → MINOR-C |
| E6 | the existing `_TREE_PROBE` indented so it no longer parses (hidden from the widened scan) | **KILLED** (2) | the case-12 pin (found set ≠ expected), `test_the_tree_probe_is_detected_as_an_embedded_program_string` |
| E7 | a second clean-string site inside `tools/train/provenance.py` | **SURVIVED** (per-file pin) | none → MINOR-B |
| E7b | a clean-string site in `discovery/cli.py` | **KILLED** (1) | the case-12 pin |
| E4b | a `+`-concatenated site in `discovery/cli.py` | **KILLED** (1) | the case-12 pin |
| E2b | an indented (dedent-style) string site in `discovery/cli.py` | **SURVIVED** | none → MINOR-B |
| E3b | an f-string site in `discovery/cli.py` | **SURVIVED** | none → MINOR-B |
| E8b | a direct `**{"allow_paddle_ocr": True}` site in `discovery/cli.py` | **SURVIVED** | none → MINOR-B |

### 6. What I attacked and could not break

* **The five read sites.** By AST, `process()` contains exactly five `self._read*(` calls and no other
  method of the class calls one; each is followed by `_project_cache_finding(row)`. The drift IS carried
  out of `cached_ocr` (a `CacheResult` field, set from a flag captured before `put_ocr` overwrites the
  entry) and onto the row of the document whose read drifted. Wrong-length and money-shaped
  `page_extractor` records are refused-and-recomputed with the same finding, never served, never raised
  out. A schema-1 record loads as `[]` / `None` with `cached=True`.
* **`page_extractor` on every rung.** Native: one token per page including an empty page, equal to the
  document's `model`. Visual: a 3-token list survives `put_ocr` → `cached_ocr` byte-for-byte, with an empty
  middle page. Paddle: the read's own list (the first review's round-trip, now pinned).
* **The MAJOR-4 killer is honest.** Instrumented: the gate is reached once with `payload is not None` and
  `collector.seen=False`, returns `False`, zero fake requests; forced `True` → `upgraded`, 3 requests.
* **Closed vocabularies.** `cache_finding` and `paddle_refusal_reason` are enforced at `as_dict()`;
  hostile tokens (a newline suffix, a money shape, the class name, a case change) are refused; all nine
  `REFUSAL_REASONS` accepted; empty on every non-Paddle row and after a successful Paddle read.
* **The router and the ladder** are untouched by the closure diff (`ocr/escalation.py`, `ocr/document.py`,
  `telemetry/*`, `webapp/worker.py` do not appear in `d2098c2..97ab9cb`); the first review's routing
  attacks therefore stand as measured there.
* **Nothing left the machine.** The suite's Paddle traffic went to `tests.paddle_fake_worker.FakeWorker`
  on an ephemeral loopback port; `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` is absent from this session's
  environment; I never contacted the Vast host; no `discovery_reports/` artifact, cold cache, or archive
  file was written by anything I ran (the cold cache was opened read-only by the privacy scan only; every
  runner I drove wrote to a `tempfile.mkdtemp` directory).

### 7. Verdict

**APPROVE WITH FINDINGS.** The first review's five surviving mutants are dead, the four MAJORs are closed as
specified, and nothing in the closure diff touches a routing, admission, validation or privacy mechanism.
One defect was introduced by the closure itself — MAJOR-A, a cross-document leak of the new `cache_finding`
column — with a one-line fix and a two-document test; it should close before the train because the column's
whole purpose is to be countable. MINOR-B/C/D bound what the new tripwires and the finding path do not cover
and are recorded so no later card mistakes them for more than they are.
