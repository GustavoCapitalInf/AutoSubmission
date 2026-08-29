# Batch-9 standing rules (binding for every batch-9 cell; read before your card)

Ocean reviews and composes; you never merge or push.

## Base facts
- Batch 9 opened from `main` = tag `batch8-final` = `68110ce`. The train branch is
  `train9`; the planning source of truth is `docs/moneythumb-replacement/BATCH9_TRANSITION.md`
  + `CENSUS_BATCH9.md` + `census_batch9/{per_sha.csv, clusters.json, opportunity_estimates.json}`
  (train9 `3311a8a`). Your base is `train9` at your handoff's commit.
- Run of record: `discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d/`
  (pointer file `discovery_reports/train8-logs/train8_run_dir.txt`): 3,380 content shas;
  validated 2,596 / review 18 / withheld 55 / failed 698 / deferred 13. Its cold cache is
  `.claude/recovery/webapp_data_train8_cold` — one OCR partition (v4) and one analysis
  partition (v16, registry fingerprint at `7185633`, settings key
  `7652A5AFA29E4FAEECAA8BBA5E169C24F3346A546298547DE6A5A06771FC093D`). READ-ONLY; nothing writes there.
- Tree at base: registry 83, `ANALYSIS_STAGE_VERSION` 16, `OCR_STAGE_VERSION` 4. Floor: full
  suite 6,742 · canonical guards 255 (5 files) · canonical conformance 1,270 (7 files, 83 × 82)
  · `python corpus_gate.py` GREEN 105 PASS / 3 WITHHELD / 1 REFUSED · corpus-marked 30; the
  pinned currency / provenance surfaces as in PROJECT_STATUS.md's batch-8 milestone line.

## Gustavo's batch-9 doctrine (binding)
Priorities: (1) maximise DEFENSIBLE validated coverage; (2) preserve correctness and every
existing validated document; (3) deterministic / local, zero recurring paid inference;
(4) stronger free/local extraction only where it genuinely helps; (5) paid OCR / VLM only
for residue nothing cheaper can solve — NOT in this wave; (6) multi-model consensus
selective, never default; (7) the deterministic validator remains authoritative.

Non-regression: `newly supported -> validated` while `previously validated -> remain validated`.
Never gain coverage by relaxing reconciliation; weakening ledger identity; weakening page /
account completeness; weakening statement-period validation; weakening currency evidence;
accepting ambiguous account selection; lowering transaction-coverage requirements;
suppressing integrity flags; moving failed / withheld to validated without the same
deterministic proof standard; special-casing benchmark statements; rewriting source values
to force reconciliation. **Every previously validated batch-8 sha is protected**: any
`validated -> review / withheld / failed / deferred` is an unexpected regression that BLOCKS
composition unless explicit per-sha evidence shows the batch-8 validation was itself
incorrect — then STOP, document the correctness defect with exact per-sha evidence, and
report for a ruling (a correctness correction, never a silent excuse). A payload change on a
`validated -> validated` document must be proven semantically correct. **A gain never cancels
a regression** (`+10 / -2` is NOT ACCEPTABLE). No statement-specific hardcodes. Fail closed.
$0 vendor: no paid OCR, no VLM, no rented GPU, no ensemble, no hosted model call anywhere
(tests included).

## Instruments (committed — use them, do not rebuild them)
- **Targeted-cohort proof:** `python -m tools.cohort_replay --group <cluster_group|cluster>
  | --parser <registration id> | --family <b8 key> | --folder <label> | --shas <file>
  [--out <private>.md] [--json <private>.json] [--label "<tree, card>"] [--expect-identical]`.
  Replays the cohort from the run of record's own cached text through YOUR tree with the
  runner's exact call, classifies with the runner's exact rules, and reports
  `newly validated | other ladder movement | previously validated preserved (payload
  identical / changed, with leaf PATHS) | validated regressions (BLOCKING, exit 2)`.
  Run it at your BASE with `--expect-identical` first (fidelity: exit 0 — measured at
  `3311a8a`: huntington 38/38 identical; WH:rbc + DECL:core_processor_sectioned +
  FAM:pnc_core_commercial_checking + RV:linkbank 36/36 identical), then at every closure
  tree over (a) your target cohort and (b) the baseline cohort of EVERY registration of
  every module you touched (`--parser` per id). Reports are private (they name shas and
  paths only, never values); the NUMBERS go in your record.
- **Privacy scan:** `python tools/privacy_scan_branch.py --data-dir
  .claude/recovery/webapp_data_train8_cold --base <your base> --ref <your branch>
  --rows <run>/rows.csv --where parser_id=<ids>` or `--shas <population.txt>` — every
  branch's ADDED lines against the printed tokens of the documents it worked on; report
  the count (0), never commit the hit list. Write regex instruments with the Write tool and
  byte-check them (a heredoc once turned `\b` into 0x08 and the scan was vacuous).
- **Archive sweep (owed once per coverage card at its final tree):**
  `python -m tools.regfp_zero_movement_sweep --rows <run>/rows.csv --data-dir
  .claude/recovery/webapp_data_train8_cold --baseline-settings-key
  7652A5AFA29E4FAEECAA8BBA5E169C24F3346A546298547DE6A5A06771FC093D --start A --end B --out <private>`
  chunked; every `moved` / `no_payload_now_publishes` / `payload_now_raises` finding must be
  inside your NAMED population by sha or it is a regression you explain or remove.
- **Census:** `census_batch9/per_sha.csv` (77 columns per non-validated sha: outcome, reason,
  failure stage, folder, route, dispatch, reconciliation facts, ADB checks failed, integrity
  flags, batch-8 family / cause / movement, text metrics, cluster) and `clusters.json`
  (sha16 lists per group). Name every document by content sha; a folder label is not an
  issuer.

## Proof floor per branch (exit codes verbatim, durable logs with an `EXIT=` line)
Full default suite; canonical guards (`tests/test_no_statement_hardcodes.py
tests/test_no_parser_helper_clones.py tests/test_r1_hardcodes.py
tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py`); canonical
conformance (`tests/test_parser_conformance.py tests/test_parser_registry_entries.py
tests/test_parser_detection_markers.py tests/test_parser_registry.py
tests/test_parser_crash_shapes.py tests/test_parser_exception_boundary.py
tests/test_count_semantics.py`; registry pins updated in the SAME commit as any registration);
`python corpus_gate.py` GREEN; the corpus-marked slice; a MUTATION TABLE for every gate or
grammar you add or touch (every mutant applied exactly as documented, run without `-x`, every
killer named — a test named after a gate is not a test of that gate); `cohort_replay` at base
and at closure; privacy scan 0; the archive sweep at the final tree when a reader changed.
Every mover named by sha + outcome + field; zero movement outside your named population;
`claimed != validated`; ledgers record measurements, not inferences — every headline number
reproduces from committed evidence, and instruments that produce headline numbers are
committed under `tools/`. Characterise before code. Structural capability over literals
(institution furniture — phone ladders, PO boxes, routing numbers, domains — is allowed and
must be justified as furniture). Doctrine binding: the ADB doctrine (one calendar-day ADB over
the printed period; withheld when daily evidence does not cover it), `CURRENCY_DOCTRINE.md`
(native currency canonical; jurisdiction defaults are affirmative evidence; a new Canadian
reader publishes the schema default and names itself a future mover), the L-1 rule (never
publish one account and silently drop another), the repair doctrine (parsers never write an
amount). Truth-set / pinned-surface movement outside an approved ceremony = STOP and report.

## Report contract (your final message to Ocean AND your W3 section)
`population | root cause | solution | newly validated | other ladder movement | previously
validated preserved | regressions | correctness evidence | generalization evidence` — plus
commits, proof-floor exits, the privacy count, risks last. Coverage cards require
`newly validated > 0` AND `unexpected validated regressions = 0`; hygiene cards require
`newly validated = 0` AND `preserved = all, payload identical`. Never summarise a cell as
green on a net count.

## Git and host
Worktree `.claude/worktrees/mt9-<card>`, branch `wave9-<card>`, base `train9` at your
handoff's commit; own ONLY the files your card names; commit incrementally on a clean tree;
NEVER merge or push. Your W3 section `§<CARD>` is APPENDED to
`docs/moneythumb-replacement/W3_TRACKA_LOG.md` (append-only; never edit another section —
the train helper rebuilds the log byte-exact and refuses otherwise). Windows host: `tasklist`,
not MSYS `kill -0`; long proofs as SEQUENTIAL single commands or detached processes launched
via `C:\Program Files\Git\bin\bash.exe` with POSIX paths and an `EXIT=<code>` terminator on a
durable log (background tool commands die at ~10 minutes; a headline number with no log does
not exist); OneDrive `PermissionError`s are transient — retry, never score them; mutation
harnesses restore with `git checkout --` and are only correct on a CLEAN tree; archive and
caches READ-ONLY; keep probes light — the machine is shared with one other cell.
