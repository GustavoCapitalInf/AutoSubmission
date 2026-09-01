# Independent adversarial review — `wave20-artifacts` (P20-ARTIFACTS, Phase 2.0 cell C)

```
REVIEWER:        independent adversarial agent (did not write this code)
BRANCH:          wave20-artifacts @ 2cb1d9c   BASE: train10 @ bea06bc
DIFF:            git diff bea06bc..2cb1d9c  (12 files, +2178 / -158)
WORKTREE:        .claude/worktrees/rev20-artifacts (detached at 2cb1d9c; nothing committed, nothing pushed)
RUN OF RECORD:   discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a
CACHES:          .claude/recovery/webapp_data_train9_cold, …_train8_cold — opened sqlite mode=ro only
HOST PYTHON:     3.14.5 (CI pins 3.12)
TREE AFTER EVERY MUTATION RUN: `git status --porcelain` empty (verified after each harness)
VERDICT:         BLOCK — 2 BLOCK, 4 MAJOR, 6 MINOR. Every finding below was REPRODUCED, not inferred.
```

The engineering is of high quality and the central design is right: one selection policy,
row-driven, shared by both readers, with the reconstruction verified against the archive. Three of
the card's four headline claims reproduce exactly on my own measurements. What blocks is narrower
and specific: **one entry of the mutation table names a killer that does not kill (I applied the
mutant and the whole targeted suite stayed green), and five of the nine new v5 key members —
including the three F-6 binary versions the `OCR_STAGE_VERSION` 4→5 bump exists to carry — can be
deleted from the key with 101 tests still passing**; and **one test pins the ABSENCE of the two
constants cell B1 is chartered to add, and B1 composes before C**.

---

## 1. Claim-by-claim (claimed in W3 `§P20ARTIFACTS` vs measured here)

| # | claim | measured by me | verdict |
|---|---|---|---|
| 1 | reconstructed offline OCR key for the batch-9 run = `0F25500A3CADF72305575A198086A30A0C348656976954489591A58C9E303BE7` = the cache's SOLE ocr `settings_key` | `partitions_for_run(RUN, conn=<train9 cold ro>)` → `native`/`local_tesseract` = `0F25500A…`; `SELECT DISTINCT settings_key … stage='ocr'` → exactly 1 row, `0F25500A…` | **CONFIRMED** |
| 2 | reconstructed analysis key = `7799FEE4EC8BCAAA2A36A27FDDCCC0BECACD50DE5C908600DA2B88A6237C996E` = the cache's SOLE analysis key | same probe → `analysis_key = 7799FEE4…`; `SELECT DISTINCT … stage='analysis'` → exactly 1 row, identical | **CONFIRMED** |
| 3 | cold cache train9: OCR 3,364 rows / 3,364 inputs / 1 key; analysis 2,656 / 2,656 / 1 | `SELECT stage, COUNT(*), COUNT(DISTINCT input_sha256) GROUP BY stage` → `('analysis',2656,2656)`, `('ocr',3364,3364)` | **CONFIRMED** |
| 4 | `mode = scanned`, `origin = reconstructed` | `summary.json:mode = "scanned"`; `partitions.origin = "reconstructed"` | **CONFIRMED** |
| 5 | huntington `--expect-identical` exit 0; 54 population, 41/41 preserved identical, 13 unchanged non-validated | reran at 2cb1d9c: **exit 0**, population 54, replayed 54, preserved **41 of 41**, payload identical 41, unchanged non-validated 13, regressions 0 | **CONFIRMED** |
| 6 | a 100-sha random sample `--expect-identical` exit 0, 0 newly validated, 0 regressions | reran with an **independent** sample (my own seed 31337 over the same 3,380 distinct shas): **exit 0**, population 100, replayed 100, preserved **81 of 81** identical, newly validated 0, regressions 0 | **CONFIRMED (independently sampled)** |
| 7 | `guardian_cu` `--expect-identical` exits 3 at BOTH base and closure; 8/8 "changed" on document-level rollup fields; pre-existing, not introduced here | reran at tip: **exit 3**, 8/8 `validated/approved → validated/approved`, payload `changed`; every changed leaf path is under `document.*` (`document.account_count`, `document.rollup.rows`, `document.omitted_sections[*].reason`, …). `replay_one` and `analysis/serialization.py` are **not in the diff**, so the behaviour is pre-existing by construction | **CONFIRMED — and root-caused below (MAJOR-3); the cell reported the symptom without the cause** |
| 8 | targeted pytest → 0, **334 passed, 2 deselected** | reran the same 7 files: **334 passed, 2 deselected, exit 0** (64.5 s) | **CONFIRMED** |
| 9 | 5 canonical guards → 0, **255 passed** | reran: **255 passed, exit 0** (19.4 s) | **CONFIRMED** |
| 10 | `tests/test_l1s2_protected_carriers.py -m corpus` → 0, 1 passed | reran: **1 passed, exit 0** (39.0 s) | **CONFIRMED** |
| 11 | the two new test files: `test_run_of_record.py` 29 tests, `test_cohort_replay_selection.py` 24 tests | **53 passed** together, exit 0 (5.7 s); the batch-9 reconstruction test was NOT skipped on this host | **CONFIRMED** |
| 12 | mutation table: 8 mutants, all "killed" | I applied 8 mutants of my own (5 from the table + 3 more) and then 8 field-drop mutants. **7 of the table's 8 reproduce as killed. The 8th — "`tesseract_version` unobtainable → key omits it" — SURVIVES**: dropping the field leaves `tests/test_artifact_cache.py` + `tests/test_visual_rung.py` at **101 passed** | **FALSIFIED → BLOCK-1** |
| 13 | "new key material and its partition tests" (nine members) | drop-mutant sweep: `raster_version`, `extraction_schema_version`, `endpoint_class`, `postprocess_state` are KILLED. `extractor`, `postprocess_admitted`, `tesseract_version`, `poppler_version`, `pymupdf_version` **SURVIVE individually** | **PARTIALLY FALSIFIED → BLOCK-1** |
| 14 | the offline partition's key never imports `ocr.ocr_client` | verified in a fresh process: after an offline key, `'ocr.ocr_client' in sys.modules` is `False`; after a visual key it is `True`. The two pre-existing subprocess assertions (`tests/test_discovery.py:310-320`, `tests/test_visual_rung.py:260`) still pass | **CONFIRMED** — but the offline path now imports `ocr.rasterize` → `pdf2image` + PIL (MINOR-1) |
| 15 | `OCR_STAGE_VERSION` 4→5 lands in the same commit as the pin | `git show 5f7bd9f --stat` = `ocr/rasterize.py`, `tests/test_artifact_cache.py`, `webapp/artifact_cache.py` only; the constant (`webapp/artifact_cache.py:353`) and both pins (`tests/test_artifact_cache.py:329`, `:1038`) move in that one commit; bump-history comment present at `:336-352` | **CONFIRMED** |
| 16 | nothing else bumped | `CACHE_FORMAT_VERSION` 1, `ANALYSIS_STAGE_VERSION` 17, `REPORT_STAGE_VERSION` 1 unchanged; `EXTRACTION_SCHEMA_VERSION = 1` added. Invalidation only — no artifact-shape change | **CONFIRMED** |
| 17 | `tests/test_l1s2_protected_carriers.py` change is mechanical, weakens no pin | diff is exactly two call sites (`ColdCache(cache_dir, run)`, `cache.text(sha, rows[sha])`). `assert len(resolved) == 15`, `PINNED_CARRIER in resolved`, the ACCOUNT leg (`classify_outcome`) and the DOCUMENT leg (`document_outcome(document)`) are all untouched, as is the `leaf_diff` payload check | **CONFIRMED — no pin weakened** |
| 18 | the privacy/message scans needed `OCR_STAGE_VERSION` monkeypatched to 4; the default run is a vacuous `documents_read: 0` | reproduced at default: `tools/privacy_scan_branch.py … --where "folder_label=Huntington Bank"` → `"population": 54, "documents_read": 0, "hit_count": 0`, **exit 0**. 0 of the 8 live v5 keys exist in either cold cache; 1 of the 8 v4 keys does | **CONFIRMED — and it is a defect to fix now, not to defer (MAJOR-2)** |
| 19 | "~30 unrelated `tools/*.py` still call `ColdCache(data_dir)`" | measured: **33** call sites across 30 files still pass one argument; `ColdCache('x')` → `TypeError: ColdCache.__init__() missing 1 required positional argument: 'run_dir'`. None is on the standing proof floor; `tests/test_q3_corroboration_probe.py` (28 passed) does not reach those code paths | **CONFIRMED (33, not ~30)** |
| 20 | "runs record their partitions" (card item 3) | `tools/train/provenance.py` implements `--mode` correctly (probe argv indexing verified: `sys.argv[1]`=root, `sys.argv[2]`=mode). **No caller passes it.** `tools/train/coldrun.sh:65` and `:89` — the pre-run and post-run provenance calls that produce every run of record — have no `--mode` | **DELIVERABLE INERT → MAJOR-4** |
| 21 | full suite 7,878 passed / 44 skipped / 35 deselected; `corpus_gate.py` GREEN 105/3/1 | **NOT RE-RUN** (out of scope per the review brief — the train runs these) | not verified |
| 22 | privacy 0 (162 shas, `documents_read: 162` with the v4 patch); message scan 0 after one reword | **NOT RE-RUN** as recorded (would require reproducing the in-process monkeypatch); the *default* vacuity was reproduced, see #18 | not verified |

---

## 2. Findings

### BLOCK-1 — the mutation table names a killer that does not kill; five of the nine new v5 key members are unpinned, including all three F-6 binary versions

**Where.** `webapp/artifact_cache.py:806-815` (the `settings.update({...})` block);
`tests/test_artifact_cache.py:268-300` (`test_toolchain_versions_never_raise_and_partition_on_unknown`);
W3 `§P20ARTIFACTS` mutation table, last row.

**What the record claims.** `| tesseract_version unobtainable -> key omits it |
test_toolchain_versions_never_raise_and_partition_on_unknown | killed |`.

**What I measured.** I deleted `"tesseract_version": toolchain["tesseract_version"],` from the key
dict and ran the named killer's whole file plus `tests/test_visual_rung.py`:

```
drop_tesseract_version:      *** SURVIVED ***   101 passed
drop_poppler_version:        *** SURVIVED ***   101 passed
drop_pymupdf_version:        *** SURVIVED ***   101 passed
drop_postprocess_admitted:   *** SURVIVED ***   101 passed
drop_extractor:              *** SURVIVED ***   101 passed
drop_raster_version:         KILLED             test_raster_version_partitions_the_key
drop_extraction_schema_version: KILLED          test_extraction_schema_version_partitions_the_key
drop_endpoint_class:         KILLED             test_every_ocr_knob_partitions_the_key[changed9]
drop_all_three_toolchain:    KILLED             test_toolchain_versions_never_raise_and_partition_on_unknown
```

**Why the named test cannot bite.** It compares one key against a key computed with
`_toolchain_versions_cache` patched to `{"tesseract_version": "known 5.0", "poppler_version":
"unknown", "pymupdf_version": "unknown"}`. On this host all three versions are really obtainable
(`tesseract_version` 25 chars, `poppler_version` 24, `pymupdf_version` 8), so the patch changes
**three** fields at once. Removing any one of them still leaves two differing, and the assertion
`base != changed` passes. Only the simultaneous removal of all three is detected.

**Why this is BLOCK and not MINOR.** The entire justification for a GLOBAL `OCR_STAGE_VERSION`
4→5 bump — which forces a 3,364-document cold re-read — is F-6: *"the key gains the Tesseract,
Poppler and PyMuPDF versions so an upgraded local binary cannot silently reuse the previous
binary's artifacts."* As measured, a later edit can drop `tesseract_version` from the key and every
gate in this cell's proof floor stays green. BATCH9-RULES is explicit: *"every mutant applied
exactly as documented, every killer named — a test named after a gate is not a test of that gate."*
The record currently states a killer that I applied and it passed. `postprocess_admitted` carries
the same exposure: B1 can admit a postprocess function without changing `POSTPROCESS_STATE`, and
with the field dropped the key would not move.

**Exact fix I would accept.** One parametrized test, one case per field, each patching exactly one
input — the shape `tests/test_visual_rung.py:492-501` already uses per knob:

```python
@pytest.mark.parametrize("field,patched", [
    ("tesseract_version", {"tesseract_version": "tesseract 9.9.9", "poppler_version": "unknown", "pymupdf_version": "unknown"}),
    ("poppler_version",   {"tesseract_version": "unknown", "poppler_version": "pdftoppm version 9.9", "pymupdf_version": "unknown"}),
    ("pymupdf_version",   {"tesseract_version": "unknown", "poppler_version": "unknown", "pymupdf_version": "9.9.9"}),
])
def test_each_toolchain_member_partitions_the_key_on_its_own(field, patched):
    import webapp.artifact_cache as module
    baseline = {"tesseract_version": "unknown", "poppler_version": "unknown", "pymupdf_version": "unknown"}
    with unittest.mock.patch.object(module, "_toolchain_versions_cache", baseline):
        base = ocr_settings_key(ocr_settings=_OcrSettings())
    with unittest.mock.patch.object(module, "_toolchain_versions_cache", patched):
        changed = ocr_settings_key(ocr_settings=_OcrSettings())
    assert base != changed, f"{field} does not partition the OCR settings key"
```

plus, for `postprocess_admitted`, a visual-labelled key computed with
`unittest.mock.patch.object(ocr_client, "ADMITTED_POSTPROCESS", ("strip_det_tags",), create=True)`
asserted different from the default; and, for `extractor`, a key computed with
`unittest.mock.patch.object(module, "_ocr_extractor", lambda **_: "visual")` asserted different
from the unpatched offline key. Then correct the mutation table to name these killers.

*(Note on `extractor` specifically: `_ocr_extractor` is a total function of `force_ocr` and
`allow_visual_ocr`, both of which are ALREADY key material, so the field can never partition the
key on its own — it is a legibility/extensibility slot, not partitioning power. Say so in the
docstring rather than claiming a partition test that cannot exist; the function's truth table IS
pinned at `tests/test_artifact_cache.py:180-196`, which is the honest pin.)*

---

### BLOCK-2 — a test pins the ABSENCE of the two constants cell B1 is chartered to add, and B1 composes before C

**Where.** `tests/test_artifact_cache.py:219-220`

```python
assert not hasattr(ocr_client_module, "POSTPROCESS_STATE")
assert not hasattr(ocr_client_module, "ADMITTED_POSTPROCESS")
```

**The collision.** `docs/agent-handoffs/P20-POSTPROCESS.md:49-50` charters B1 to add exactly
`POSTPROCESS_STATE = "quarantined"` and `ADMITTED_POSTPROCESS: tuple[str, ...] = ()` to
`ocr/ocr_client.py`. `docs/agent-handoffs/PHASE2-0-SAFETY.md` fixes the composition order as
**B2 → B1 → A → C → D** — B1 lands first.

**Reproduction.** I appended B1's two constants to `ocr/ocr_client.py` (restored in a `finally`;
tree verified clean after):

```
exit: 1
FAILED tests/test_artifact_cache.py::test_postprocess_state_partitions_the_key_and_pins_the_quarantined_default
1 failed, 65 passed
```

The composed train fails on C's own test file. Note the *key value* is unaffected (B1's values
equal C's pinned defaults) — this is purely a test that asserts a temporary fact about another
cell's file as if it were a contract.

**Exact fix I would accept.** Replace the two absence assertions with a value assertion that is
correct in both worlds:

```python
from webapp.artifact_cache import ADMITTED_POSTPROCESS_DEFAULT, POSTPROCESS_STATE_DEFAULT, _ocr_postprocess_readout
# Correct before and after B1: whatever ocr.ocr_client declares, Phase 2.0's
# quarantine state is "quarantined" with an EMPTY admitted tuple.
assert getattr(ocr_client_module, "POSTPROCESS_STATE", POSTPROCESS_STATE_DEFAULT) == "quarantined"
assert tuple(getattr(ocr_client_module, "ADMITTED_POSTPROCESS", ADMITTED_POSTPROCESS_DEFAULT)) == ()
assert _ocr_postprocess_readout("visual") == ("quarantined", ())
assert _ocr_postprocess_readout("offline") == ("quarantined", ())
```

That keeps the "empty admission" pin the phase actually wants (P20-POSTPROCESS's own mutation table
row `ADMITTED_POSTPROCESS = ("strip_det_tags",)`) and survives composition in either order.

---

### MAJOR-1 — the partition record is verified by EXISTENCE only, and not at all for a RECORDED run; a wholly mis-partitioned replay exits 0

**Where.** `telemetry/run_of_record.py:318-319` (`if partitions.origin != ORIGIN_RECONSTRUCTED: return`),
`:327-339` (`_require_key_in_cache` — `SELECT 1 … WHERE stage=? AND settings_key=? LIMIT 1`);
`tools/cohort_replay.py:390` and `:455-457` (the `--expect-identical` drift filter excludes
`no_text`/`absent`).

**(a) A RECORDED run is never checked at all.** `tests/test_run_of_record.py:322-338`
(`test_verify_reconstruction_is_a_noop_for_a_recorded_run`) enshrines this with the reasoning *"a
RECORDED run's keys are, by construction, exactly what it wrote"*. That premise is false: those
keys come from an operator-supplied `--mode` on `tools/train/provenance.py` that is never
cross-checked against the run's own `summary.json:mode`.

**Reproduction.** A run directory carrying the real `rows.csv`/`summary.json` and a
`run_of_record.partitions` block naming three keys that exist nowhere:

```
python -m tools.cohort_replay --run <fakerun> --data-dir <train9 cold> \
    --folder "Huntington Bank" --expect-identical
EXIT=0
| population | 54 |
| replayed (text available) | 0 |
| previously validated preserved | **0** of 41 |
| no text / absent | 54 |
```

**Exit 0.** The branch's own fidelity gate reports green while reading nothing. `--expect-identical`
computes drift only over rows whose `after` is not `no_text`/`absent`, so a 100 % miss is silent.

**(b) The RECONSTRUCTED check is existence, not correspondence.** The card's design text says
*"every key it names must exist in the index **or be absent for every row that claims it**"*;
`_require_key_in_cache` implements only the first half. On a single-partition archive that is
harmless (the miss is `None`). On the multi-partition archive this cell exists to make safe, it
serves the **wrong** artifact.

**Reproduction** (tmp cache, both offline partitions present, `summary.json:mode` wrong):

```
verify_reconstruction RAISED? no — origin: reconstructed  mode: scanned
resolved key is the LOCAL tranche's: True
served page label: ['LOCAL-TRANCHE PAGE']          # the OTHER tranche's text, silently
```

**Exact fix I would accept (both halves).**
1. `verify_reconstruction` runs for **every** origin, RECORDED included — a run's own cache must
   hold its own declared keys, or the record is wrong and that is exit 5. Delete the
   `origin != ORIGIN_RECONSTRUCTED` early return; retarget
   `test_verify_reconstruction_is_a_noop_for_a_recorded_run` into
   `test_a_recorded_run_whose_keys_are_absent_from_its_cache_is_refused`.
2. Verify by **correspondence**, not existence: give `verify_reconstruction` the run's rows and
   require that the offline key resolves an artifact for every row whose `source_path` is
   `native`/`local_tesseract` **and** whose `outcome_class` shows text was read (a bounded sample —
   the first 50 such rows — is enough and costs one indexed lookup each). A key that exists in the
   index but resolves none of the run's own documents is a wrong guess.
3. `tools/cohort_replay.py`: refuse a vacuous green. Minimum —

```python
if args.expect_identical and len(table) and len(no_text) == len(table):
    print(f"BASELINE FIDELITY FAILED: 0 of {len(table)} shas resolved any cached text — "
          "the run's partitions do not describe this data directory")
    return 3
```

   Better: carry the run's own `source_path != none` count for the cohort and fail when the
   replayed count falls below it.

---

### MAJOR-2 — the `OCR_STAGE_VERSION` bump makes three named proof-floor instruments read ZERO documents and report a clean zero

**Where.** `tools/privacy_scan_branch.py:832-837` and `:109-131` (`cached_text`);
`tools/huntington_msg_privacy_scan.py:68-73`; `tools/regfp_zero_movement_sweep.py:120-124,150-195`.
All three enumerate the eight capability partitions with the **live** `ocr_settings_key(...)`, which
is now v5 and host-keyed.

**Reproduction.**

```
train9 cold: cache ocr keys = 1 | live(v5) keys intersecting cache = 0 | v4 keys intersecting cache = 1
train8 cold: cache ocr keys = 1 | live(v5) keys intersecting cache = 0 | v4 keys intersecting cache = 1

python tools/privacy_scan_branch.py --data-dir <train9 cold> --base bea06bc --ref 2cb1d9c \
    --rows <run>/rows.csv --where "folder_label=Huntington Bank"
{"population": 54, "documents_read": 0, "hit_count": 0, "raw_hit_count": 0, ...}   exit 0
```

**Why this is not "acceptable until the cold run" (my recommendation: fix now).**
- The Phase-2.0 **floor runs before the cold run** (`PHASE2-0-SAFETY.md` §Implementation sequence:
  floor → cold run). Every cell composing after C — and the train itself — must report a privacy
  count from an instrument that, at the composed tree, reads nothing.
- It does **not** self-resolve. The cold run writes a *new* cold cache; the two frozen archives that
  BATCH9-RULES names by path as the scanners' `--data-dir` stay v4 forever. The vacuity against
  `webapp_data_train8_cold` / `webapp_data_train9_cold` is permanent.
- The failure is silent by the exact signature BATCH9-RULES warns about (*"`population 0` reports a
  vacuous zero"*), reached by a new route: population 54, documents 0, exit 0.
- This cell has already built the correct answer. `telemetry/run_of_record.py` reconstructs a v4
  archive's key perfectly (claim #1 above) — that is precisely why `observe_run` survived the bump
  (I ran it at the tip: `documents 3384`, non-vacuous) while the scanners did not.

**Exact fix I would accept.** OQ10-correct: give `privacy_scan_branch.py`,
`huntington_msg_privacy_scan.py` and `regfp_zero_movement_sweep.py` a `--run` argument and resolve
their OCR text through `telemetry.run_of_record.partitions_for_run` +
`ocr_partition_for_row` + `select_artifact` — the same conversion this cell performed on the other
two readers, and it also retires their "the longest reconstruction wins" heuristic (an unratified
selection rule that OQ10 forbids). Minimum acceptable: both scanners exit non-zero when
`documents_read == 0` on a non-empty population, so the vacuity can never be recorded as a pass.

**Ownership.** None of the three is in C's ownership list. Ocean's call: extend C by one commit, or
card it as a blocking prerequisite before the train's floor. It must not compose unaddressed —
the next cell to run a privacy scan will record a zero that means nothing.

---

### MAJOR-3 — `cohort_replay.replay_one` replays a SINGLE-ACCOUNT projection against a DOCUMENT-shaped cached payload; `--expect-identical` is structurally unusable on 25 documents of the archive

**Where.** `tools/cohort_replay.py:204-215` (`replay_one` → `report_to_dict(analyze_markdown(...))`)
vs `discovery/runner.py:503` (`document_report_to_dict(analyze_document(...))`) — the runner of
record's exact call, which is what wrote the cached analysis artifacts.

**Root cause (hypothesis CONFIRMED).** `analysis/serialization.py:279-307`: for a single-account
document that established a document-level fact, `document_report_to_dict` returns
`{**report_to_dict(account), DOCUMENT_KEY: block}`; for a genuine multi-account document it returns
`{DOCUMENT_KEY: …, "accounts": [...]}` with **no** top-level `statement`. `replay_one` produces
`report_to_dict(...)` only, so the `document` block (and the whole `accounts` shape) can never
appear in the replay's side of the comparison.

**Reproduction (leaf paths only, no values).** `--group FAM:guardian_cu_statement_summary
--expect-identical` at the tip: **exit 3**, 8/8 `validated/approved → validated/approved`, payload
`changed`, and every changed path is under `document.` —
`document.account_count`, `document.boundary_mechanism`, `document.integrity_notes`,
`document.internal_transfers`, `document.omitted_sections[*].label`,
`document.omitted_sections[*].posting_count`, `document.omitted_sections[*].reason`,
`document.period_end`, `document.period_start`, `document.rollup.caption_class`,
`document.rollup.column_roles_printed`, `document.rollup.cross_account_total_printed`,
`document.rollup.rows`. No non-`document.` path moved on any of the eight.

**Blast radius, measured over the train9 cold cache** (all 2,656 analysis artifacts read, mapped
back to content shas through `analysis_input_sha`):

| shape | count |
|---|---:|
| analysis payloads carrying a top-level `document` block | **23** |
| of those, carrying the multi-account `accounts` list | **2** (`7C7956EB5E93DB1D`, `E38FA786106F752E` — both inside the guardian_cu 8) |
| total analysis artifacts | 2,656 |

So `--expect-identical` cannot reproduce 23 of 2,656 documents at ANY tree, and on the 2
multi-account documents the replay's `classify_outcome` is judging a single-account projection of
`accounts[0]` rather than the document the runner published. This is the instrument every Phase-2.0
cell uses for *"previously validated preserved = all, payload identical"*.

**Pre-existing?** Yes — `replay_one` and `analysis/serialization.py` are absent from
`git diff bea06bc..2cb1d9c`, so the behaviour is identical at base by construction, and the cell's
"present at base" claim stands.

**Does the fix belong in THIS cell?** **No — and I would refuse it here.** C owns
`tools/cohort_replay.py`, but switching `replay_one` to `document_report_to_dict(analyze_document(
markdown, parse_mode="deterministic", on_dispatch=collector, sheets=pages))` changes the replay's
*classification* for every document in the archive, not just the 25 — `classify_outcome` would be
handed a different shape everywhere, and the 23 document-block documents would move from `changed`
to `identical` in one step with no independent baseline to check that against. That is a
measurement change on the instrument the whole phase depends on, and it needs its own card, its own
base/closure numbers over the full 3,380 and its own hostile review. Regression risk if done here:
it would silently re-baseline every Phase-2.0 cell's fidelity claim mid-phase.

**What I DO require of this cell:** replace the W3's *"a pre-existing replay characteristic of this
newly-landed multi-account family"* with the diagnosed cause (`report_to_dict` +
`analyze_markdown` vs the runner's `document_report_to_dict` + `analyze_document`), the measured
blast radius (23 / 2 / 2,656), and an explicit statement that `--expect-identical` is **not a valid
fidelity gate for documents carrying a `document` block** until that card lands. "Recorded rather
than smoothed over" is not the same as root-caused, and P20-SURFACES hit the same wall independently
— two cells reporting the same undiagnosed exit 3 is how a defect becomes folklore.

---

### MAJOR-4 — "runs record their partitions" is inert: no caller passes `--mode`, and a v5 reconstruction is host-dependent

**Where.** `tools/train/coldrun.sh:65` (pre-run) and `:89` (post-run) — the only two producers of a
run-of-record `provenance.json` — invoke `tools/train/provenance.py` with no `--mode`. The run
itself is `python -m discovery --scanned` (`coldrun.sh:71`), so the mode is known at that line.

**Consequence, reproduced.** A v5 offline key embeds the run host's binary version strings:

```
v5 key differs across hosts: True   (32F00F243740802E… vs EC397774709F452C… with the probe patched)
v4 key differs across hosts: False
```

The Phase-2.0 cold run will therefore produce a run of record with **no** recorded partitions
(origin `reconstructed`) whose offline key is a v5 key. Reconstructing it anywhere but the machine
that produced it computes a different key, `verify_reconstruction` raises, and
`cohort_replay`/`observe_run` exit 5 against the new baseline. The batch-9 archive is unaffected
(v4 keys are host-independent) — the breakage lands squarely on the baseline this phase creates.

**Exact fix I would accept.** Two lines in `tools/train/coldrun.sh` — `--mode scanned` on both
provenance calls (or `--mode "${MODE:-scanned}"` beside the existing `--scanned` flag) — plus a
sentence in the W3 recording that the Phase-2.0 run of record is the first `origin="recorded"` run.
`coldrun.sh` is not in C's ownership list; a deliverable that no caller invokes is not delivered,
so I would have Ocean either grant the two lines to C or land them at composition.

Optional hardening worth one line: refuse in `_recorded_partitions` when the block's `mode`
disagrees with `summary.json:mode` (a `--mode` typo is then exit 5, not a silent wrong partition —
see MAJOR-1(b)).

---

### MINOR-1 — `ocr_settings_key` now raises `ModuleNotFoundError` when `pdf2image` is missing

`webapp/artifact_cache.py:801` does an unguarded `from ocr.rasterize import RASTER_VERSION`;
`ocr/rasterize.py:1-5` imports `PIL` and `pdf2image` at module level. Reproduced in a subprocess
with `pdf2image` blocked: `ocr_settings_key(force_ocr=False, allow_local_ocr=True,
allow_visual_ocr=False)` → `RAISED: ModuleNotFoundError No module named 'pdf2image'`. At base the
function imported only `ocr.config`. Both packages are hard requirements
(`requirements.txt`) and CI installs them, so this is robustness, not a live break — but it
contradicts the discipline the card sets for the sibling probe ("NEVER raises") and pulls PIL +
pdf2image into the import surface of every OCR cache lookup for the sake of one integer.
**Fix I would accept:** move `RASTER_VERSION` to a dependency-free module (or read it via
`importlib`-free `try/except ImportError` with the pinned constant duplicated and a test that the
two agree), so the key computation never depends on a rasterization backend being importable.

### MINOR-2 — the "byte-for-byte v4 reconstruction" has no host-independent pin

`tests/test_artifact_cache.py:315-334` asserts only `reconstructed_v4 != live_v5` and self-agreement
— it would pass if the v4 field set changed. The only real pin is
`tests/test_run_of_record.py:196` (`0F25500A…`), which is `skipif`-gated on the cold cache being
present and therefore **skipped in CI**. The pin is cheap and host-independent: the test file's own
`_OcrSettings()` stand-in reproduces the archive key exactly — I measured

```
ocr_settings_key(force_ocr=False, allow_local_ocr=True,  allow_visual_ocr=False, stage_version=4, ocr_settings=_OcrSettings())
    == 0F25500A3CADF72305575A198086A30A0C348656976954489591A58C9E303BE7   # the batch-9 archive's sole key
ocr_settings_key(force_ocr=False, allow_local_ocr=False, allow_visual_ocr=False, stage_version=4, ocr_settings=_OcrSettings())
    == 91937F817835CDAFFC67D66658625D874C58C697A16050EAAA4DBB58771BC671
```

**Fix:** assert those two literals in the unskippable test.

### MINOR-3 — `_ArtifactJoin` never closes its sqlite connection

`telemetry/stated_counts.py:884` opens a connection for the instance's lifetime; the class has no
`close()`/`__enter__`/`__del__` and `observe_run` does not release it. The old `_rows()` closed in a
`finally`. On Windows this holds a handle on `webapp.db` (a read-only URI, so the cold caches are
safe) and can defeat `tmp_path` cleanup. **Fix:** a `close()` and a `try/finally` in `observe_run`,
or make `_ArtifactJoin` a context manager.

### MINOR-4 — the `rows[0]` mutant's named killer asserts nothing about the mutant

`tests/test_cohort_replay_selection.py:201-223` ends at `assert len(rows) == 3`; it never shows the
mutant resolving the wrong artifact. The mutant IS killed — I applied it to
`tools/cohort_replay.py::_payload` and got **21 failed, 3 passed** on
`tests/test_cohort_replay_selection.py`, with the guaranteed killer being line 162
(`cold.text(SHA_X, ROW_VISUAL_ABSENT)` returning non-`None`). **Fix:** name the shuffle test as the
killer in the mutation table and either delete this test or make it assert that `rows[0]`'s pages
differ from the run's declared partition's pages under at least one insertion order.

### MINOR-5 — 33 old-signature `ColdCache(data_dir)` call sites remain (disclosed by the cell; verified)

Measured 33 sites in 30 files (the cell said "~30"); `ColdCache('x')` raises `TypeError`. I confirmed
none is exercised by the standing suite (`tests/test_q3_corroboration_probe.py` passes, 28 tests) and
none is a BATCH9-RULES instrument. Agreed: not this cell's scope. It should be a named backlog item,
because each of those tools also carries the "longest reconstruction wins" or `rows[0]` selection
OQ10 forbids.

### MINOR-6 — a global-state test without a fixture

`tests/test_artifact_cache.py:268-300` and `:302-313` assign
`webapp.artifact_cache._toolchain_versions_cache` directly and reset it to `None` on the happy path
only; a failure leaks a forced state into the rest of the session (and the reset forces a real
`subprocess` probe in whatever runs next). **Fix:** a small autouse fixture that saves and restores
the module global.

---

## 3. What I looked for and did NOT find

- **Cache partition ambiguity in the two converted readers.** None. `ColdCache._payload` and
  `_ArtifactJoin.payload_for` both go through `select_artifact` with a row-derived key; no
  `rows[0]`, no `ORDER BY`-free scan, no preference list, no offline-first or visual-first
  disposition survives in either. Confirmed by 20 shuffled insertion orders × 2 readers (all green)
  and by three mutants of my own (`M3` visual-first, `M9` offline-always, `M1` `rows[0]`) — all
  killed.
- **A fallback on a missing partition.** None. `ocr_partition_for_row` returns `None` for
  `source_path=none`, for an unknown source, and for a visual row on a run without a visual key
  (`tests/test_run_of_record.py:370-381`); `select_artifact` returns `None` on a miss and RAISES on
  two rows for one triple (mutant `M4` killed).
- **Any write to either cold cache.** None. Every connection in the diff is
  `file:…?mode=ro` with `uri=True`; `webapp.storage.Storage` (which migrates on open) is not used by
  either reader. I opened both archives read-only throughout.
- **A weakened pin in `tests/test_l1s2_protected_carriers.py`.** None — see claim #17. The 15-carrier
  population assertion, the pinned corpus carrier, the ACCOUNT leg and the DOCUMENT leg all stand
  unaltered, and the test passes under `-m corpus`.
- **A second competing selection mechanism (OQ8).** None — `telemetry/run_of_record.py` is the
  single policy and both readers import it rather than reimplementing.
- **Anything else bumped (OQ ruling: `OCR_STAGE_VERSION` 4→5 only, with its pin, in one
  composition).** Nothing. `ANALYSIS_STAGE_VERSION` 17, `REPORT_STAGE_VERSION` 1,
  `CACHE_FORMAT_VERSION` 1. Artifact content and envelope unchanged — invalidation, not corruption.
- **3.13+-only APIs** (CI pins 3.12). None in the diff: no `Path.read_text(newline=)`, no
  `itertools.batched`, no `copy.replace`, no `Path.walk`, no `typing.override`. All annotations are
  3.10-compatible.
- **Network, paid endpoints, or model calls.** None. `ocr_toolchain_versions` shells out only to
  local `tesseract`/`pdftoppm` (`shutil.which`-guarded, `timeout=10`, everything in `except
  Exception`) and imports `fitz`. `$0` vendor posture intact.
- **Statement-, bank- or benchmark-specific behaviour introduced anywhere.** None; the 5 canonical
  guards pass (255).
- **Newly validated documents.** 0 at every cohort I ran (huntington 54, guardian_cu 8, my
  independent 100-sha sample). 0 validated regressions in all three.
- **`ocr.ocr_client` reaching the offline key path.** It does not (claim #14). Both pre-existing
  subprocess assertions still hold, and the new subprocess test is a genuine addition.

---

## 4. Reproduction commands

All run with cwd = `.claude/worktrees/rev20-artifacts`;
`REPO=<repo root>`, `RUN=$REPO/discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a`,
`COLD=$REPO/.claude/recovery/webapp_data_train9_cold`.

```bash
# claims 1-4: the reconstruction, verified
PYTHONPATH="$PWD" python -c "
import sqlite3; from pathlib import Path
from telemetry.run_of_record import partitions_for_run
c = sqlite3.connect('file:$COLD/webapp.db?mode=ro', uri=True)
print(c.execute(\"SELECT stage, COUNT(*), COUNT(DISTINCT input_sha256), COUNT(DISTINCT settings_key) FROM artifact_cache GROUP BY stage\").fetchall())
print(partitions_for_run('$RUN', conn=c))"

# claims 5-7: fidelity, and the guardian_cu exit 3
python -m tools.cohort_replay --run "$RUN" --data-dir "$COLD" --folder "Huntington Bank" --expect-identical   # exit 0
python -m tools.cohort_replay --run "$RUN" --data-dir "$COLD" --group FAM:guardian_cu_statement_summary --expect-identical  # exit 3
python -m tools.cohort_replay --run "$RUN" --data-dir "$COLD" --shas <100 shas> --expect-identical            # exit 0

# claims 8-11 + 17: the proof floor I owed
python -m pytest -q tests/test_artifact_cache.py tests/test_run_of_record.py \
  tests/test_cohort_replay_selection.py tests/test_stated_counts.py tests/test_visual_rung.py \
  tests/test_discovery.py tests/test_telemetry.py                       # 334 passed, 2 deselected
python -m pytest -q tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py \
  tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py  # 255 passed
python -m pytest -q -m corpus tests/test_l1s2_protected_carriers.py     # 1 passed

# BLOCK-1: the surviving drop-mutants (harness restores in a finally, verifies the tree clean)
#   drop each of the nine v5 members from webapp/artifact_cache.py:806-815 in turn,
#   run tests/test_artifact_cache.py + tests/test_visual_rung.py, restore.
#   SURVIVED: extractor, postprocess_admitted, tesseract_version, poppler_version, pymupdf_version

# BLOCK-2: simulate B1
#   append POSTPROCESS_STATE = "quarantined" / ADMITTED_POSTPROCESS = () to ocr/ocr_client.py,
#   run tests/test_artifact_cache.py, restore.
#   -> 1 failed: test_postprocess_state_partitions_the_key_and_pins_the_quarantined_default

# MAJOR-1(a): the vacuous green
#   run dir = real rows.csv + summary.json + a provenance.json whose run_of_record.partitions
#   names three keys absent from the cache; then
python -m tools.cohort_replay --run <fakerun> --data-dir "$COLD" --folder "Huntington Bank" --expect-identical
#   -> EXIT=0, "replayed (text available) | 0", "previously validated preserved | 0 of 41"

# MAJOR-1(b): the wrong partition served
#   tmp cache with BOTH offline partitions for one input + a run whose summary.json mode is wrong
#   -> verify_reconstruction does not raise; the LOCAL tranche's artifact is served

# MAJOR-2: the vacuous privacy scan
python tools/privacy_scan_branch.py --data-dir "$COLD" --base bea06bc --ref 2cb1d9c \
    --rows "$RUN/rows.csv" --where "folder_label=Huntington Bank"
#   -> {"population": 54, "documents_read": 0, "hit_count": 0}, exit 0

# MAJOR-3: the blast radius
#   read all 2,656 analysis artifacts; count payloads with a top-level "document" / "accounts" key
#   -> 23 document-block, 2 multi-account, 2,656 total

# MAJOR-4: host-dependence of a v5 key
PYTHONPATH="$PWD" python -c "
import unittest.mock as m, webapp.artifact_cache as ac
a = ac.ocr_settings_key(allow_local_ocr=True, stage_version=5)
with m.patch.object(ac,'_toolchain_versions_cache',{'tesseract_version':'x','poppler_version':'y','pymupdf_version':'z'}):
    b = ac.ocr_settings_key(allow_local_ocr=True, stage_version=5)
print('v5 differs across hosts:', a != b)"
grep -n 'provenance.py' tools/train/coldrun.sh     # :65 and :89, neither passes --mode
```

---

## 5. Verdict

**BLOCK.**

Close before composition:

| id | finding | fix size |
|---|---|---|
| BLOCK-1 | the mutation table's `tesseract_version` killer does not kill; `extractor`, `postprocess_admitted` and all three binary versions are individually unpinned | one parametrized test + a corrected table row |
| BLOCK-2 | `tests/test_artifact_cache.py:219-220` pins the absence of B1's constants; B1 composes first | 4 lines |
| MAJOR-1 | RECORDED partitions are never verified; RECONSTRUCTED ones only by existence; `--expect-identical` exits 0 on a 100 % miss | ~15 lines across two files |
| MAJOR-2 | three named proof-floor instruments now read 0 documents and report a clean zero | 3 lines each (refuse), or the OQ10 conversion |
| MAJOR-3 | `replay_one`'s shape mismatch — root cause and blast radius must go in the record; the FIX belongs in its own card, not here | W3 text now; a card later |
| MAJOR-4 | `--mode` never passed by `coldrun.sh`; a v5 reconstruction is host-dependent | 2 lines in `coldrun.sh` |

MINOR-1…6 are accepted as findings; I would take MINOR-2 (the host-independent v4 literal pin,
`0F25500A…` / `91937F81…`) in the same pass as BLOCK-1 since it is one line and closes the only
gap in the reconstruction's CI coverage.

Everything else in this branch is sound, and the parts that matter most reproduce exactly: the
reconstruction is correct on both archives, both readers resolve row-by-row with no preference or
incidental order left anywhere, the fidelity numbers reproduce on an independently drawn sample,
the stage bump is invalidation-only and lands with its pin, and no pin outside the card's ownership
was weakened. Re-review after the six items above; I expect it to be short.
