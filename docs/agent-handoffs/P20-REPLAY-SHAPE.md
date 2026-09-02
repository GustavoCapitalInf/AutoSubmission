# Agent Handoff — P20-REPLAY-SHAPE (Phase 2.0 addendum cell E: the cohort replay replays through the runner's exact document call)

Cut by Ocean on 2026-09-01 from P20-ARTIFACTS review MAJOR-3 (`reviews/PHASE2_P20ARTIFACTS_REVIEW.md`),
corroborated by P20-SURFACES review MAJOR-1/MAJOR-3. Read `BATCH9-RULES.md`, `PHASE2-RULES.md`,
`PHASE2_RULINGS.md`, `PHASE2-0-SAFETY.md`, then this card. Ocean reviews and composes; you never
merge or push. **Hygiene card: `newly validated = 0`; previously validated preserved.** This card
changes an INSTRUMENT, not the analysis: `analysis/*` is not yours.

# Why
`tools/cohort_replay.py::replay_one` calls `analyze_markdown` + `report_to_dict` — the SINGLE-ACCOUNT
projection — while the runner of record (`discovery/runner.py::_analyse`) calls `analyze_document` +
`document_report_to_dict` and the cached analysis artifacts hold that DOCUMENT shape. Measured on the
train9 cold cache: 23 of 2,656 analysis payloads carry a top-level `document` block, 2 of them the
multi-account `accounts` list (both guardian_cu). On those 23 the replay's `--expect-identical` exits 3
at EVERY tree by construction, its `classify_outcome` judges `accounts[0]` rather than the document
the runner published, and — because `analyze_markdown` never opens the omission collector — the
replay cannot observe anything that lives at the omission publish seam (the Q3 native-only gate of
P20-SURFACES). Two cells reported the exit 3 as folklore before the review diagnosed it.

# Design (ruled)
1. `replay_one` replays with the runner's EXACT call: `document_report_to_dict(analyze_document(markdown,
   parse_mode="deterministic", on_dispatch=collector, sheets=pages))`, and classifies with the runner's
   exact rules — find how `discovery/runner.py` derives `outcome_class` / `outcome_reason` for a
   document payload (the document fold; `telemetry/record.py::classify_document` vs
   `classify_outcome`) and call the SAME function. The failure boundary stays the runner's
   (`_failure_reason`). Nothing about `flatten` / `leaf_diff` / the accounting changes.
2. The baseline payload comparison is then shape-for-shape: the 23 document-block documents must go
   from `changed` to `identical` at an unchanged analysis tree, and NO other document may change its
   `payload` disposition or its `after` class. That is the whole proof: a full-archive replay
   (`--shas` = all 3,380 distinct shas of the run of record, chunked with `--start/--end` if the host
   needs it; detached with an `EXIT=` log) at BASE (the instrument as it stands: record the 23 exit-3
   shas by sha16) and at CLOSURE (`--expect-identical` exit 0 over all 3,380; 0 newly validated; every
   previously validated preserved identical; the 23 named shas now identical; 0 other movement).
3. Keep the old single-account path available ONLY behind an explicit `--account-shape` flag whose
   help text says it does not reproduce the run of record (for historical instruments), default OFF —
   or delete it if no tool needs it (check the 33 old-signature callers named in P20-ARTIFACTS'
   W3 closure; they are backlog, not yours).
4. Tests: `tests/test_cohort_replay_shape.py` — a synthetic multi-account document whose cached
   payload is document-shaped reproduces `identical`; a mutant that reverts to `analyze_markdown` is
   killed; the Q3 gate of P20-SURFACES is OBSERVABLE through the replay (a local-tesseract-ocr header
   on a Q3-class fixture yields the fail-closed outcome through `replay_one`).

# Base and ownership
Base: `train10` AFTER P20-ARTIFACTS composes (the run-of-record selection must be in place); Ocean
tells you the commit. Branch `wave20-replayshape`, worktree `.claude/worktrees/mt20-replayshape`.
Own: `tools/cohort_replay.py`, `tests/test_cohort_replay_shape.py` (new), W3 `§P20REPLAYSHAPE`.
NOT yours: `analysis/*`, `discovery/*`, `telemetry/*` (read them; if the document classification
function is not importable without side effects, report it rather than copying it).

# Proof floor
Targeted tests + the existing `tests/test_cohort_replay_selection.py` + `tests/test_run_of_record.py`;
the 5 canonical guards; the full-archive replay at base and closure (exit codes verbatim, the 23
sha16s named); privacy scan 0 (the replay reports name shas and leaf paths only — never commit them);
message scan 0. Report per the batch-9 contract plus "replay-shape evidence".

# Exclusions
No change to any analysis, serialization, runner or telemetry code. No new selection policy (OQ10's
is in `telemetry/run_of_record.py`). No re-baselining of any other cell's numbers — you report what
the corrected instrument says and Ocean re-reads the cells' claims against it.

# Addendum (Ocean, 2026-09-01, from the P20-ARTIFACTS re-review MINOR-8)
Under `--expect-identical` the tool refuses only when ZERO of the cohort resolved (reproduced: 2 real
shas + 8 absent shas → exit 0, "replayed 2 / population 10"). This card also makes `--expect-identical`
refuse (exit 3) whenever `replayed < population` unless the caller passes an explicit
`--allow-unresolved` — "expect identical" over a named cohort means every member reproduced. Pin it.
