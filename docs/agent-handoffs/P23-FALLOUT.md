# Agent Handoff — P23-FALLOUT (Phase 2.3 cell B: the baseline stage-by-stage fallout with the existing structurer in research mode, per geometry source; the false-accept instrument on the control sample; "Paddle helped"; the truth table v2; adjudication slice 2)

**Launch base:** the `train13` tip Ocean names at launch, AFTER cells W, E and X have composed (their
partitions, metrics and agreement columns are your inputs). Worktree `.claude/worktrees/mt23-fallout`,
branch `wave23-fallout`.

Read `docs/agent-handoffs/BATCH9-RULES.md`, `PHASE2-RULES.md`, `docs/moneythumb-replacement/PHASE2_RULINGS.md`
(the anti-optimizer rule — no candidate is chosen by reconciliation; R3 — an adjudicator labels, never a
tool; R11 — any exit from validated is a regression; R13 — the declined branch is 2.4's, NOT yours; the
STOP conditions), the umbrella `docs/agent-handoffs/PHASE2-3-WAVE.md` (D8, D9, cases 9, 10, 13, the
exclusions), the plan §G.2.3 cell B and the adjudication slice 2, §H.3, §H.6, §I.6 (the L3 sub-classes
B1–B8), `docs/moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md`, then the Phase 2.2 instruments as composed:
the K, T and H sections `# §P22IDENTITY*`, `# §P22TRUTHTABLE*`, `# §P22HOLDOUT*` in `W3_TRACKA_LOG.md` (grep the
headings), `analysis/config.py` (`Settings.reconstruction_mode`, read from `RECONSTRUCTION_MODE`),
`analysis/structurer/` (`structurer_enabled`, `geometry.py::geometry_from_evidence`, the existing generic
rung — READ-ONLY; you change nothing in it), `discovery/runner.py` (the research mode; the geometry seam
`_geometry_for` passing `document_geometry` and `evidence_sha256` when the mode is not `off`; the funnel
columns `stage_*`; `_project_taxonomy`), `telemetry/unresolved_taxonomy.py` (L2 E0–E5, L3 B1–B8 — populated
from row facts only), `tools/truth_report.py`, `tools/holdout/` and `tools/adjudicate.py` (the sealed store,
the packets, the queues), `docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt`, `layout/document_class.py`,
cell W's partitions (`paddle-v5-prod`; V's two if composed) and the P23-WAVE / P23-EGATE / P23-AGREE W3 sections.
Ocean reviews and composes; you never merge or push. **Hygiene card: `newly validated = 0` OFFICIAL —
research-validated shas are NAMED, never counted; the structurer runs ONLY in research partitions with
`RECONSTRUCTION_MODE=research` in that run's environment, never in a run of record; no candidate selected by
reconciliation; no customer page leaves the machine (every read is a cache hit on W's partitions); no cost.**

# Why
2.4 will build the LayoutModel from the B-class fallout; 2.5 will admit Paddle where "Paddle helped" is
measured; the truth table v2 is what both are judged against. None exists. This cell runs the existing
structurer as the BASELINE reconstruction over the unresolved corpus, per geometry source, and records
where each document stops — and on the control sample it tests whether the Paddle path can produce a
candidate that disagrees with a validated payload, which is the one false-accept instrument the program has
before the holdout.

# What you deliver (ruled — do not re-decide)
1. **The research analysis runs** — the research mode with `RECONSTRUCTION_MODE=research` in the run's
   environment (T's seam; K's setting), over U755 in W's `paddle-v5-prod` partition (and V's partitions where
   composed), TWICE per document: geometry from NATIVE evidence and geometry from PADDLE evidence, as two
   research partitions of the ANALYSIS artifacts (the analysis key already carries the evidence sha and the
   mode — verify; if a second analysis partition needs a research id of its own, report to Ocean before
   adding one). Every read is a cache hit on the OCR partition (no page sent anywhere — assert zero Paddle
   requests). The structurer's code is untouched.
2. **The funnel per source** (`tools/fallout_report.py`, read-only over the run rows): E (attempted →
   evidence → E-class from cell E) → G (geometry built: pages, lines, words, frame, rotation) → L (furniture
   removed → ≥ 1 table region → column model → records → summary anchors → account partition; a B1–B8 code
   from the structurer's own refusal reasons into L3 — read from row facts only) → C (a candidate produced,
   with sign tier and grounding coverage) → V (the validator's verdict and the W3-2 class) → Δ (research-
   validated · review · refused · failed), per source (native | paddle | tesseract-text), as counts and as
   a per-sha private table; every research-validated sha NAMED in its own row and never counted; every
   refusal coded.
3. **"Paddle helped"** per document: the stage where the Paddle-geometry funnel went further than the
   native-geometry funnel (or the Tesseract-text funnel for scans), e.g. `native: B2; paddle: validated`;
   aggregated by census family and by modality; "no added value" where both reach the same stage.
4. **The false-accept instrument on CTRL** (D8, BLIND until comparison): the Paddle-geometry research run
   over CTRL produces candidates; `tools/false_accept_probe.py` records each candidate's key fields
   (opening, closing, transaction count, Σ debits, Σ credits) BEFORE it reads the validated payload from the
   run of record, then compares; any disagreement is a FALSE-ACCEPT CANDIDATE — a row in adjudication slice 2,
   never a label, never a fix. The instrument's blindness is structural (two passes, the second reading a
   file the first wrote) and pinned by a test.
5. **The truth table v2** — `tools/truth_report.py` extended: the classifier (`classify_document`) run on
   PADDLE evidence for every scanned/mixed document of U755 and CTRL (read-only from the partition), beside
   its Tesseract-text verdict; the disjoint sums; adjudicated verdicts (from the sealed store, tools-side
   only) beside classifier-proposed; every verdict CHANGE named by count and queued; the CCL forms printed
   beside the raw denominator, never instead of it.
6. **Adjudication slice 2** (`tools/adjudicate.py` queue — cell H's instrument, ownership widened for the
   queue builder only): every document whose classifier verdict changed between Tesseract text and Paddle
   evidence, every `KIND_UNCERTAIN`, every false-accept candidate, and a random 50 of the rest (a recorded
   seed); packets under the private on-machine directory outside OneDrive; the queue digest in your W3;
   nothing adjudicated by you.
7. **No hardcodes; no routing:** no code path chooses a source by its verdict; nothing reads `Δ` but the
   report; the OQ2 scans cover the tools.

# Files you own (exact; nothing else)
`tools/fallout_report.py` (new) · `tools/false_accept_probe.py` (new) · `tools/truth_report.py` (the v2
extension) · `tools/adjudicate.py` (the slice-2 queue builder ONLY) · `discovery/runner.py` (ONLY if the
research analysis partition needs a per-source id — report first) · `tests/test_fallout_report.py`,
`tests/test_false_accept_probe.py` (new) · `tests/test_truth_report.py`, `tests/test_adjudication.py` (APPEND) ·
`tests/test_no_statement_hardcodes.py` (the roots append) · your W3 section. `analysis/**` (the structurer
included), `layout/**`, `ocr/**`, `evidence/**`, `telemetry/**`, `webapp/**`, `tools/paddle_wave.py` are NOT
yours.

# Mutation table (run every mutant, name every killer)
M1 a research-validated sha counted into the headline → T's headline-exclusion test + your named-row test ·
M2 the probe reading the validated payload before recording the candidate → the blindness test (the order of
the two files' timestamps and a fake payload that would be preferred) · M3 a false-accept candidate written
as a verdict → the queue-row test · M4 the structurer run with `RECONSTRUCTION_MODE` unset → the mode-only
test (zero geometry passed) · M5 a Paddle request during the analysis runs → the zero-request test on the
fake worker · M6 a source chosen by its verdict (planted in a scratch copy) → the AST guard · M7 "Paddle
helped" reported where both sources reach the same stage → the no-added-value test · M8 a B-code inferred
rather than read from a row fact → the taxonomy drift guard (T's) · M9 the CCL printed without the raw
denominator → T's two-denominator test · M10 the slice-2 queue including a holdout sha → H's refusal.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; the research analysis runs (both sources; logs with `EXIT=`; zero Paddle
requests asserted); `cohort_replay --expect-identical` over the `--parser` chunks at base and closure if
`discovery/runner.py` changes at all; the fallout, "Paddle helped", the probe on CTRL, the truth table v2
and the slice-2 queue produced from committed instruments; privacy scan 0 over added lines; the message
scanner over every report you write (`--shas` = the populations) → 0; message scan 0 over commits. Heavy
proofs one at a time under `discovery_reports/train13-logs/HARNESS.lock` (mkdir-only; own-holder release;
Git bash `rmdir`).

# Report contract (final message to Ocean AND your W3 section `# §P23FALLOUT — …`)
population (U755 and CTRL per source; the partitions) · root cause · solution · newly validated 0 OFFICIAL
(research-validated shas NAMED per source) · ladder movement 0 · preserved all (the run of record untouched) ·
regressions 0 · the fallout funnel per source (counts) · "Paddle helped" by family and modality · the
false-accept candidates (count; queued) · the truth table v2 (disjoint sums; adjudicated beside proposed; the
verdict changes by count) · slice 2 (count; digest) · escalation evidence (no source chosen by a verdict; no
request) · commits · proof exits · privacy count · risks last (what 2.4 must not read as more than a baseline).

# Exclusions
No structurer change (2.4) · no routing (2.5) · no admission · no adjudication (R3) · no Paddle call · no
declined-branch run (R13 is 2.4's) · no cost.
