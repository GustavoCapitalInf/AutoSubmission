# Agent Handoff — P22-FENCE (Phase 2.2 cell F, ruling R9: remove the reconciliation-based selection between two hosted extractions; fence the auto-mode Class-B → hosted edge behind an explicit opt-in; prove deterministic mode byte-identical)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `docs/agent-handoffs/PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (ALL of it — OQ3, Ruling A, the 2026-09-03 section's R9
and the anti-optimizer rule), then the umbrella `docs/agent-handoffs/PHASE2-2-TRUTH.md` (D11, case 22),
then `docs/moneythumb-replacement/phase2_remainder/research/REPO_VALIDATOR_MEMO.md` §9 rows 8 and
§10 (the site, characterised), then `analysis/pipeline.py` (ALL of `analyze_markdown` — especially the
escalation block around lines 918–1005 at `4f7d798`: `needs_escalation`, the second `extract_statement`
call, `alt_recon`, `better_summary`, `fewer_issues`, and the auto-mode fall-through to
`extract_statement` on `unclaimed` / `parser_exception`), `analysis/config.py` (`Settings.model`,
`escalation_model`, `parse_mode`), `analysis/extract.py` (the hosted call — read only), `webapp/worker.py`
(the auto-mode caller — read only), `tests/test_pipeline*.py` and any test that exercises escalation
(find them: `grep -rn "escalation" tests/`). Ocean reviews and composes; you never merge or push.
**Hygiene card: `newly validated = 0`; every previously validated document preserved payload-identical
(deterministic mode never reaches the code you change — prove it); no network; `analysis/pipeline.py` is
a PROTECTED module (MASTER_PLAN §4): the diff is minimal, pinned, and forensically justified.**

# Why
`analysis/pipeline.py` still carries, reachable in the webapp's default auto mode, the exact pattern the
doctrine forbids: run a second hosted extraction and "prefer whichever extraction's summary reconciles,
falling back to fewer overall issues". Gustavo's R9: "Do not leave reachable logic whose effective
behavior is: multiple extractions → compare financial reconciliation → prefer whichever extraction
reconciles. … make it unreachable immediately through a strong tripwire where practical; independently
reproduce/characterize the existing behavior; remove or fully fence the selection behavior … Do not defer
an actually reachable unsafe selection edge merely because it is old code. Preserve regression proof. If
removing it reveals that a previously validated result depended on this behavior, surface that result
explicitly." Ruling A additionally refused, as doctrine, the auto-mode hop from an unclaimed/crashed
dispatch to a hosted extractor; the code still has it. This cell puts both rulings in code.

# What you deliver (ruled — do not re-decide)
1. **Characterise BEFORE you change (a test written first, at base, that PASSES on the unsafe
   behaviour):** with `parse_mode="auto"`, a fake `extract_statement` (monkeypatched at the
   `analysis.pipeline` import site) whose PRIMARY result fails reconciliation and whose ALTERNATE
   (escalation model) reconciles, the base code adopts the alternate (`model_used ==
   settings.escalation_model`, `escalated is True`). Commit that test as the characterisation with a
   docstring saying it documents the removed behaviour; in the fix commit invert it: the alternate is
   NEVER adopted, the second `extract_statement` call NEVER happens (the fake counts calls: exactly one).
2. **Remove the selection.** Delete the escalation block: no second `extract_statement` call in
   `analyze_markdown`; no `alt_recon`, `better_summary`, `fewer_issues`; `escalated` is always False (keep
   the field in the payload for shape stability, pinned False, with a comment naming R9); the
   `escalation extraction failed …` issue string disappears — check `telemetry/diagnostics.py`'s
   reconciliation-issue anchors (`recon:escalation_extraction_failed`, W3-2 §3.3): the anchor STAYS in
   the vocabulary (a record written before this change must still classify) and its call-site count
   guard (`issues.append(` count in `reconcile.py` + `pipeline.py` == 7) will DROP — that guard is
   `tests/test_diagnostics.py`'s and `telemetry/diagnostics.py`'s; you may NOT edit them (cell T owns
   `telemetry/`): STOP and report the exact count change to Ocean, who will hand it to T; in the
   meantime keep the `issues.append(...)` call site count unchanged by leaving a dead-by-construction
   branch? NO — never dead code. The right move: report it, and Ocean sequences T's guard update at
   composition. Say so in your W3.
3. **Fence the hosted edge (Ruling A in code).** The auto-mode fall-through from `dispatch.outcome in
   {unclaimed, parser_exception}` to `extract_statement` requires
   `HOSTED_EXTRACTION_OPT_IN == "I_ACCEPT_HOSTED_MODEL_EXTRACTION"` read from the process environment
   at the call site (exact `==`, never truthy; the same idiom as `ocr/endpoint_policy.py`'s literal);
   absent → the document takes the deterministic-mode outcome for that dispatch (`failed /
   no_parser_matched` or `review / parser_exception` exactly as `parse_mode="deterministic"` produces
   today) and the payload records `hosted_extraction: "refused_no_opt_in"`; present → the existing single
   hosted extraction runs (no selection). `Settings` gains no field (an environment literal is a
   deliberate operator act, like the OCR opt-ins; document it in `analysis/config.py`'s docstring only
   if `Settings` is where the other opt-ins are documented — otherwise in `pipeline.py`).
4. **Tripwires:** (a) AST: `analyze_markdown` contains at most ONE call to `extract_statement`; (b) AST:
   no comparison of two `reconcile(...)` results anywhere in `analysis/pipeline.py` (no two names bound
   from `reconcile(` compared or selected between — define the check concretely and show a mutant that
   re-adds the selection is caught); (c) the literal is never present in any tracked file
   (`grep` in a test over the tree, like the Paddle opt-in test); (d) deterministic mode cannot reach
   `extract_statement` at all (the existing PRIVACY-3 property — keep its test green).
5. **Regression proof:** deterministic mode (every run of record, discovery, the gate, the corpus slice)
   never reaches the changed lines: `cohort_replay --expect-identical` at base AND closure over the
   UNION of every registration (`--parser` per id, chunked) — the full offline partition byte-identical;
   `python corpus_gate.py` GREEN; the webapp auto-mode tests updated to the fenced behaviour (a test
   that auto mode WITHOUT the literal equals deterministic mode on an unclaimed synthetic; a test that
   WITH the literal the single hosted extraction runs on a fake); surface in your W3 whether ANY test,
   fixture or documented behaviour depended on the removed selection.
6. **No hardcodes.**

# Files you own (exact; nothing else)
`analysis/pipeline.py` (the escalation block and the auto-mode fall-through ONLY; nothing else in the
file) · `analysis/config.py` (docstring only, if at all) · `tests/test_pipeline_escalation_fence.py`
(new: characterisation → inversion, the tripwires, the fence tests) · existing tests that asserted the
escalation behaviour (name each one you change and why) · your W3 section. `telemetry/**` and
`tests/test_diagnostics.py` are NOT yours (report the guard-count consequence to Ocean).

# Mutation table (run every mutant, name every killer)
M1 re-add a second `extract_statement` call guarded by `not recon.ok` → tripwire (a) · M2 re-add
`if alt_recon.ok: stmt = alt` → tripwire (b) and the inverted characterisation · M3 the literal compared
truthily (`if os.environ.get(...)`) → the exact-literal test (set the variable to `1`) · M4 the literal
read at import time instead of the call site → the test that sets it after import · M5 auto mode without
the literal still reaches `extract_statement` → the fence test (fake counts zero calls) · M6
`escalated` derived from anything → the pinned-False test · M7 deterministic mode reaching the hosted
call → the PRIVACY-3 test.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; the UNION cohort replay at base and closure (chunked; every exit
code in your W3); privacy scan 0 over your added lines against the run-of-record population
(`discovery_reports/TRAIN11-4f7d798/…-331d9136/rows.csv`, cold cache
`.claude/recovery/webapp_data_train11_cold`, READ-ONLY); message scan 0. Heavy proofs one at a time on
this host.

# Report contract (final message to Ocean AND your W3 section `# §P22FENCE — …`)
population (the union replay) · root cause (the two edges, characterised with the base test) ·
solution · newly validated (0) · other ladder movement (0) · previously validated preserved (all,
identical) · regressions (0) · correctness evidence (the inverted characterisation; the tripwires; the
fence) · escalation evidence (no validator → extractor edge remains in `analysis/`) · the diagnostics
guard-count consequence for cell T · commits · proof-floor exits · privacy count · risks last (the
webapp user-facing change in auto mode without the literal).

# Exclusions
No change outside the two edges · no `telemetry/` edit · no removal of `analysis/extract.py` · no change
to `bank_repairs.py` (R10 is 2.3) · no new opt-in for anything else · no cost field.
