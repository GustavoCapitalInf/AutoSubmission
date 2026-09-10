# PHASE2_P22FENCE_REVIEW — independent adversarial review of Phase 2.2 cell F (card P22-FENCE, ruling R9 + Ruling A in code)

```
REVIEWER:   independent (wrote none of the code); detached worktree .claude/worktrees/rev22-fence at c373957
BASE:       train12 b23cb50 (code tree 4f7d798)     CODE TIP: f9bb315 (tree ea0300d3; == 157e7e1's tree)
CLOSURE:    c373957 (fac80af + c373957 are W3 documentation only; `git diff --stat f9bb315 c373957` = W3_TRACKA_LOG.md alone)
VERDICT:    APPROVE WITH FINDINGS (0 BLOCK · 1 MAJOR · 5 MINOR)
```

## 1. Verdict and findings, ranked

| # | severity | finding |
|---|---|---|
| F1 | **MAJOR** | Tripwire (b) is name-bound and scope-bound: three in-module selection shapes pass `reconcile_selection_violations` — a nested closure that binds its own `reconcile(...)` result and reads the enclosing `recon`, a local alias `_r = reconcile`, and `from .reconcile import reconcile as verify`. Reviewer mutant R6 (the closure shape, a reconciliation-based selection with NO second extraction) SURVIVED the cell's entire killer set (402 passed). Tripwire (a) shares the alias-blindness (`_hosted = extract_statement`, `import … as _second`, `getattr`, `globals()` all count as ≤ 1 call node). §3. |
| F2 | MINOR | Three comment/docstring-only hunks in the protected module sit outside the two ruled edges (module docstring; the repair-seam comment; the BLOCK-2 comment), and `analysis/config.py` received comment edits where the card allowed "docstring only". Disclosed by the cell (deviations 3–4). Code-level diff (AST, docstrings stripped) is exactly the two edges plus their definitions; `config.py` is AST-identical. §4. |
| F3 | MINOR | The refusal record (`exc.hosted_extraction == "refused_no_opt_in"`) exists only on a transient exception: `webapp/worker.py::_analysis_failure` reduces it to the declared literal, `batch.py` to the class name; nothing durable records that an auto-mode refusal was for want of the opt-in. The card's "the payload records `hosted_extraction`" is unsatisfiable on a raise (the cell said so); the consequence — OQ3's "recorded opt-in" is not recorded anywhere a reader can find later — is a follow-up for the worker owner. Related: the auto-mode analysis cache key does not partition on the opt-in, so a payload produced under the literal is served later in auto mode without it (a cache hit, never a call). §5. |
| F4 | MINOR | The cell's Risks name only the webapp; `analyze.py` (`analyze_document(markdown)` — default `auto`), `batch.py` (default `auto`; "a production caller" by its own comment) and `adb_debug.py` (`--parse-mode` default `auto`; help text "deterministic refuses to fall back to the LLM extractor" is now half-stale) all changed behaviour the same way. Every one routes through `_analyse` and hits the fence — the surface list is incomplete, the fence is not. §5. |
| F5 | MINOR | `webapp/static/app.js:654-655` (`friendlyAnalysisError`) tells an AUTO-mode user "Use Auto mode for fallback extraction …" — wrong advice for an auto-mode user without the literal; it does not claim anything was extracted, so it does not mislead about safety. `README.md:228` still advertises `GEMINI_ESCALATION_MODEL` as a tuning knob; `tools/extractpriv_reachability.py`'s docstring describes the removed guard. Wording follow-ups outside cell F's ownership. |
| F6 | MINOR | The cell's M7 finding is CONFIRMED and is worth stating as a property: with the deterministic raise deleted and no literal set, the historical PRIVACY-3 dynamic tests still pass (the fence refuses with the identical message). "No hosted call in deterministic mode" now rests on two independent guards; the killers are the static ordering test and the opted-in deterministic test (3 failed / 399 passed, reproduced). The PRIVACY-3 dynamic test's docstring narrative ("mutant M23", a clause that no longer exists) is stale — disclosed by the cell. |

Nothing BLOCKS: no validator weakening, no new hosted route, no deterministic-mode payload movement, no privacy or message hit, no undisclosed code outside the two edges. F1 must be closed before composition per the review plan's BLOCK/MAJOR rule; F2–F6 are follow-ups.

## 2. What I reproduced (method 1: the cell's own claims)

### 2.1 Base characterisation and inversion
```
git worktree add --detach .claude/worktrees/rev22-fence-base b23cb50
git show 034a855:tests/test_pipeline_escalation_fence.py > tests/test_p22_char_034a855.py
python -m pytest tests/test_p22_char_034a855.py -q -p no:cacheprovider      -> 4 passed in 2.45s   EXIT=0
```
At `b23cb50` the four characterisation tests PASS on the unsafe behaviour (two hosted calls `[model-a, model-b]`, `model_used == escalation_model`, `escalated is True`, the reconciling alternate adopted; and auto mode reaching the fake extractor with nothing set for `unclaimed`, `parser_exception`, `ambiguous`). The tip's test file cannot even collect at base (`AttributeError` on the new module constants, EXIT=2), and at the tip the same edge-1 fixture yields exactly one call and the failed reconciliation standing:
```
python -m pytest tests/test_pipeline_escalation_fence.py tests/test_privacy3_boundaries.py tests/test_q3_native_only.py tests/test_analysis.py tests/test_escalation_router.py tests/test_escalation_tripwires.py -q -p no:cacheprovider
-> 498 passed, 2 deselected in 69.44s   EXIT=0
```

### 2.2 Mutation table, re-run by me (harness: exact textual edits on the review worktree, killer set = the fence file + privacy3 + q3 + test_analysis, no `-x`, `git checkout --` restore in `finally`, `git status --porcelain` empty and `pipeline.py` sha `4f2ec4ce7cfd` identical after every mutant; CRLF-aware anchors)

| mutant | applied | my result | cell's result | killers (named) |
|---|---|---|---|---|
| M1 | second `extract_statement(…, model=settings.escalation_model)` guarded by `not recon.ok` | KILLED 10 / 392 | 10 / 392 | tripwire (a); the ordering test; the inverted characterisation; pinned-False dynamic; privacy3 static + dynamic; q3; 3 incidental `test_analysis` |
| M2 | the selection re-added (`alt_recon = reconcile(alt)`, `if alt_recon.ok: stmt, recon, model_used, escalated = …`) | KILLED 12 / 390 | 12 / 390 | tripwire (b) B1/B2/B4; the inverted characterisation; (a); pinned-False static + dynamic; privacy3; q3 |
| M3 | `return bool(source.get(ENV))` | KILLED 10 / 392 | 10 / 392 | `test_only_the_exact_literal_opts_in[×9]`, `test_the_injection_seam_compares_exactly` |
| M4 | `_HOSTED_OPTED_IN_AT_IMPORT` at module level AND the helper returns it when `environ is None` (my "M4b"; my "M4" was the inert constant alone and survived, as an inert mutant must) | KILLED 9 / 393 | 9 / 393 | `test_the_literal_is_read_at_the_call_site_not_at_import` + every opted-in test |
| M5 | the two fence lines deleted | KILLED 16 / 386 | 16 / 386 | `test_without_the_literal…[×3]`, `…exact_literal…[×9]`, read-at-call-site, ordering, webapp equality, q3 |
| M6 | `escalated = not recon.ok` | KILLED 8 / 394 | 8 / 394 | pinned-False static + dynamic, the inverted characterisation (+ the anchor-artefact failures the cell named) |
| M7 | the deterministic-mode `raise RuntimeError(...)` deleted | KILLED 3 / 399 | 3 / 399 | `test_deterministic_mode_never_reaches…[unclaimed]`, the ordering test, `test_without_the_literal…[unclaimed]` — NOT the PRIVACY-3 dynamic test (F6) |
| R1 (mine) | the fence inverted (`if hosted_extraction_opted_in(): raise`) | KILLED 23 / 379 | — | every opted-in and every refusal test |
| R2 (mine) | `.strip().upper() ==` (case/whitespace-insensitive) | KILLED 5 / 397 | — | `[lowercase]`, `[trailing-newline]`, `[leading-space]`, `[trailing-space]`, the seam test |
| R3 (mine) | the OCR rung's literal accepted too | KILLED 1 / 401 | — | `test_only_the_exact_literal_opts_in[the-ocr-literal]` |
| R4 (mine) | the attribute no longer set on the refusal | KILLED 13 / 389 | — | `test_without_the_literal…[×3]`, `…exact_literal…[×9]`, q3 |
| R5 (mine) | the fence moved BEFORE the deterministic raise | KILLED 2 / 400 | — | the ordering test; `test_without_the_literal…[unclaimed]` (deterministic now carried the attribute) |
| **R6 (mine)** | a nested closure binding `alt_recon = reconcile(alt, …)` and returning `alt if alt_recon.ok and not recon.ok else stmt` — a reconciliation-based selection with NO second extraction | **SURVIVED 402 / 0** | — | none — F1 |

Every cell-claimed kill reproduces with the identical failed/passed counts.

### 2.3 Tripwire (b) attack (fifteen fresh shapes, in memory, `attack_tripwire_b.py`)
CAUGHT: ternary over `.ok` (B1) · `max()` over two reconcile results (B2+B3) · helper body in-module comparing two results (B1+B4) · list-indexed results (B3) · `sorted()` tuple (B3) · walrus in `if` (B2+B3) · for-loop search (B1) · method on the call (B3) · `IfExp` as an `_account_report` argument (B3) · keyword argument to `_account_report` (B3) · a lambda holding the second reconcile (B3) · `getattr(alt_recon, 'ok')` (B1).
**SURVIVED:** `nested-closure` · `aliased-reconcile` (`_r = reconcile`) · `foreign-verifier` (`from .reconcile import reconcile as verify`) · `helper-returns-better` (a call to a helper whose body is elsewhere — inherent to a single-module scan; today no module under `analysis/` other than `pipeline.py` imports `reconcile` or `extract_statement`, verified by `git grep` at c373957).

### 2.4 Tripwire (a) attack (`attack_tripwire_a.py`)
`second-direct-call` and `module-attribute` (`_ex.extract_statement(...)`) are CAUGHT (2 call nodes); `alias-name`, `import-as`, `getattr-string`, `globals-lookup` each count as 1 node and SURVIVE the static check. The dynamic inverted characterisation catches the alias and `globals()` shapes (they resolve to the monkeypatched name); `import-as`/`getattr` reach the REAL `analysis.extract.extract_statement` and would fail only through the missing API key — by accident, not by design.

### 2.5 The fence, attacked with my own inputs (`attack_fence.py`, 30 checks, 0 failures)
NUL-suffixed literal (refused by `os.environ` itself), BOM prefix, tab/CR suffix, full-width underscore, a Cyrillic homoglyph, quoted, doubled, empty, `0`, `True`, `1\n` — all refuse with the deterministic message and the attribute, zero calls · `os.putenv` alone does not opt in (call-site read of `os.environ`) · toggle sequence set/unset/set after import → `refuse, call, refuse, call` · `analyze_document` opted in: exactly one call, `escalated: False` and no `hosted_extraction` key in `document_report_to_dict` · deterministic mode WITH the literal through `analyze_document`: no call, no attribute · `parse_mode="AUTO"` refused (`ValueError`) before the fence · structurer on + auto + no literal: no hosted call · opted-in primary failing reconciliation: one call, failure stands, `escalated` False in `report_to_dict` · `model == escalation_model`: one call · the refusal carries no `__cause__`/`__context__` · a two-registration `ambiguous` dispatch in auto mode without the literal raises `AmbiguousParserError` with the attribute and the SAME message as deterministic mode.

### 2.6 Hunk-by-hunk check of the protected module (`hunk_check.py`: AST with docstrings stripped, unparsed, diffed)
Code-level diff = `import os` · the three constants · `hosted_extraction_opted_in` · `_hosted_extraction_refused` · the two fence lines between `if parse_mode == 'deterministic': raise` and the one `extract_statement` call · the removed escalation block (`needs_escalation`, the guarded second call, `alt_recon`, `better_summary`, `fewer_issues`, the tuple re-bind, the `issues.append`). Top-level names added: the five above; removed: none. The five textual hunks of `git diff b23cb50...f9bb315 -- analysis/pipeline.py`: (1) module docstring + `import os`, (2) the opt-in block, (3) the repair-seam comment (comment-only — F2), (4) the BLOCK-2 comment + THE FENCE, (5) the removed block + the pinned `escalated = False` with its R9 comment. `analysis/config.py`: `ast.dump` identical base vs tip (comments only). `Settings` gains no field.

### 2.7 Ownership, commits, trailers
`git diff --stat b23cb50...c373957`: `analysis/config.py`, `analysis/pipeline.py`, `tests/test_analysis.py`, `tests/test_pipeline_escalation_fence.py`, `tests/test_privacy3_boundaries.py`, `tests/test_q3_native_only.py`, `docs/moneythumb-replacement/W3_TRACKA_LOG.md` — all inside the card's list; `telemetry/**`, `tests/test_diagnostics.py`, `webapp/**`, `analysis/extract.py`, `analysis/bank_repairs.py` untouched. Five commits `034a855 → c5e28d8 → f9bb315 → fac80af → c373957`, each carrying `Co-Authored-By: Claude …` and `Claude-Session: https://claude.ai/code/session_…` (1/1 on every commit). Reword: `157e7e1` and `f9bb315` share parent `c5e28d8` and tree `ea0300d374fac7d492c8c3d11def844153e030b7`.

## 3. F1 in detail (MAJOR) — the tripwire that can be walked around

The rule set B1–B4 is per-scope and name-literal. Two consequences, each reproduced:

* **Scope.** `_scopes` excludes nested functions from the parent's node list, so B1 sees one reconcile-bound name in `_analyse` and one in `_prefer`; B4 builds `bound` per scope, so `alt_recon.ok and not recon.ok` inside `_prefer` reads only ONE bound name it knows (`recon` is the parent's). Reviewer mutant R6 is exactly this shape, sits in the protected module, compares two reconcile results, selects between two statements by reconciliation, and passes the tripwire AND all 402 killer tests (the alternate here is `normalize_statement(stmt)`, so no test can see it behaviourally — which is the point: a selection between two non-hosted candidates is the anti-optimizer pattern no dynamic test covers).
* **Name.** `_is_reconcile_call` matches the identifier `reconcile` (or `.reconcile`). `_r = reconcile` / `from .reconcile import reconcile as verify` rename it; `_calls_to(tree, "extract_statement")` has the same blindness.

Closing it (small, in the test file only): (1) treat a function and its nested scopes as one unit for B1/B4, or resolve free names to enclosing bindings; (2) refuse ANY binding of the names `reconcile` / `extract_statement` in the module other than the single `ImportFrom` at the top (Assign, `Import`/`ImportFrom` with `asname`, walrus, parameter names), and refuse `getattr`/`globals()` reaching either name; (3) a module-wide guard that `reconcile` and `extract_statement` are imported by no module under `analysis/` except `pipeline.py` (true at c373957). The card's own bar — "define the check concretely and show a mutant that re-adds the selection is caught" — is met for the verbatim base block; the reviewer's attack list required the check to hold against fresh shapes, and it does not.

## 4. F2 in detail (MINOR) — hunks outside the two edges
All three are comments/docstrings describing the removed block (the module docstring said "only a statement that fails reconciliation is re-extracted with the stronger model"; the repair-seam comment counted "two LLM-branch repair calls"; the BLOCK-2 comment said the `unclaimed` edge "is not touched"). Leaving them would have made the protected module lie about itself; the cell named each. Recorded because the reviewer's rule is "a hunk elsewhere is a finding", not because any of them should be reverted.

## 5. F3/F4 in detail (MINOR) — where the refusal goes, and who else changed
`_analysis_failure` (`webapp/worker.py:194-205`) publishes the declared literal; `batch.py:311+` publishes `type(e).__name__`; the `hosted_extraction` attribute is read by nothing but the tests. `cached_analysis` caches successes only and keys on `analysis_settings_key(parse_mode=…)` — the opt-in is not key material (by the card's "no `Settings` field"), so a hosted payload computed under the literal is a cache hit later without it. Callers in auto mode: `webapp/worker.py::_analyze_doc` (the card's), `analyze.py:188`, `batch.py:299`, `adb_debug.py:56` (default `auto`). Deterministic everywhere else (`discovery/runner.py`, `corpus_gate.py`, `benchmark/ourside.py`, every `tools/*` replay). No route reaches `extract_statement` except `analysis/pipeline.py:1033`; `analysis/extract.py::extract_statement` makes ONE `generate_content` call with no retry.

## 6. Diagnostics consequence (cell T)
`telemetry/diagnostics.py:184` keeps `("escalation extraction failed", None, "recon:escalation_extraction_failed")`; the count guard `tests/test_diagnostics.py::test_reconciliation_issue_sites_match_the_anchor_count` counts `issues.append(` in `reconcile.py` + `pipeline.py` against `len(RECON_ISSUE_ANCHORS) == 7`; `pipeline.py` now has 0 sites. Full-suite result below.

## 7. Heavy proofs (under `HARNESS.lock`; every step its own log under `discovery_reports/train12-logs/rev22-fence/` with an `EXIT=` line; `MASTER.log` records the lock window)

Lock window 02:07:39Z → 02:28:17Z (147 polls of 30 s waiting behind cells H/C/K; nothing ran beside another harness). Command per replay: `python -m tools.cohort_replay --run "discovery_reports/TRAIN11-4f7d798/2026-09-03T022827.644186-0000-331d9136" --data-dir .claude/recovery/webapp_data_train11_cold --expect-identical …`, base from `rev22-fence-base` (b23cb50), closure from `rev22-fence` (c373957, code tree ea0300d3).

| step | re-derived by me | claimed by the cell (§P22FENCE / -2) | EXIT |
|---|---|---|---:|
| chunk 01 `--parser chase`, base b23cb50 | population 504 · replayed 504 · newly validated 0 · other movement 0 · preserved **504 of 504**, payload identical 504, changed 0 · regressions 0 / 0 · unchanged non-validated 0 (0) — 420 s | 504 / 504 / 504 identical, 0 / 0 / 0 | 0 |
| chunk 01 `--parser chase`, closure c373957 | identical to base, every cell — 426 s | identical | 0 |
| no-parser `--shas no-parser-shas.txt --expect-unresolved 29`, base | population 685 · replayed 656 · unresolved 29 (= expected) · newly validated 0 · preserved 0 of 0 · regressions 0 / 0 · unchanged non-validated **656 (payload changed on 0)** — 13 s | 685 / 656 / 29 / 656 (0) | 0 |
| no-parser, closure | identical to base — 13 s | identical | 0 |
| full default suite at c373957 (`python -m pytest -q -p no:cacheprovider`) | **2 failed / 8,789 passed** / 45 skipped / 39 deselected in 325 s: `tests/test_diagnostics.py::test_reconciliation_issue_sites_match_the_anchor_count` (cell T's count guard, 7 anchors vs 6 sites — attributable to this diff) and `tests/test_run_of_record.py::test_provenance_paddle_key_note_never_leaks_a_raw_exception_message` (the KNOWN host effect of the main checkout's gitignored `.env`; fails at the untouched base too; cell K's; not counted) | 1 failed / 8,790 passed / 45 / 39 (the cell's host state lacked the `.env` effect: 8,789 + 1 = 8,790) | 1 |
| `tests/test_diagnostics.py` alone | 1 failed / 65 passed — the count guard only; `recon:escalation_extraction_failed` still at `telemetry/diagnostics.py:184` | same | 1 |
| privacy scan `tools/privacy_scan_branch.py --rows <run>/rows.csv --run <run> --data-dir <train11_cold> --base b23cb50 --ref c373957 --out <private>` | added_lines 1,337 · population 3,380 · documents_read 3,351 (29 no_cached_text = the no-text shas) · **hit_count 0** (raw 19, all `words_class` by rule) · residue_files 0 · residue_sites 0 | 1,337 / 3,351 / 0 (raw 19) / 0 / 0 | 0 |
| message scan `tools/huntington_msg_privacy_scan.py --data-dir <train11_cold> --base b23cb50 --ref c373957 --rows <run>/rows.csv --run <run>` (population = the run of record) | commits_scanned 5 · **hit_count 0** · MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0 | 5 / 0 / 0 0 0 0 | 0 |

The guards (275), conformance (1,282 / 41 skipped), `corpus_gate.py` (GREEN 105/3/1) and `pytest -m corpus` (34) were read from the cell's own logs under `discovery_reports/train12-logs/p22fence/` (`EXIT=0` each) and not re-run: none of the four exercises the changed lines (all deterministic-mode callers), the full suite above covers the same tree, and the host is shared. Every headline number the cell claims that I re-derived reproduces exactly.

## 8. Properties I attacked and could not break (named)
1. **Exact-literal opt-in** — 21 non-literal values (cell's 9 + my 12, including NUL, BOM, homoglyphs) refuse; R2/R3 mutants killed.
2. **Read at the call site** — set/unset after import, `putenv` bypass; M4(b) killed.
3. **Deterministic mode never reaches the fence** — with the literal, all three outcomes, via `analyze_markdown` and `analyze_document`; R5 (fence before the raise) killed; the PRIVACY-3 dynamic tests green.
4. **Exactly one hosted call, opted in** — unclaimed / parser_exception / ambiguous; primary failing reconciliation; `model == escalation_model`; the webapp seam.
5. **No selection remains in `analysis/`** — the only `reconcile(` sites are `pipeline.py:1040` (single-target) and `:1101` (positional argument, consumed); no `If` tests `escalation_model`; no attribute read of it in the module.
6. **`escalated` pinned False wherever serialized** — `serialization.py:195`, the sibling loop, `document_report_to_dict`, `report_to_dict`; `telemetry/record.py:533`'s `calls: 2 if escalated` is now always 1.
7. **The refusal is indistinguishable from deterministic mode by message** — same class, same text (pinned by `_DECLARED_ANALYSIS_REFUSALS` and the router tests); the attribute never enters a message.
8. **The literal is in no tracked file but its definition** (`git grep -c` at c373957: `analysis/pipeline.py` 1, two `docs/*.md` cards) — and not in the main checkout's gitignored `.env` (checked: no `HOSTED_EXTRACTION_OPT_IN`, no `GEMINI_API_KEY`).
9. **The base characterisation is genuine** — 4 tests PASS at b23cb50 on the unsafe behaviour; the inverted test passes at the tip on the same fixture.
10. **The reword is a reword** — identical trees and parents.
11. **Deterministic-mode identity** — §7.

## 9. Scratch instruments (untracked, under the session scratchpad; none written into the tree)
`attack_tripwire_b.py` · `attack_tripwire_a.py` · `attack_fence.py` · `mutants_p22fence.py` (+ `.log`, `_R5.log`) · `hunk_check.py` · `rev22_fence_heavy.sh` + `lock_wait.py`. Worktrees: `.claude/worktrees/rev22-fence` (c373957, detached; this file is its only untracked change) and `.claude/worktrees/rev22-fence-base` (b23cb50, detached, clean). Nothing merged, pushed, or committed; the cell's branch untouched.

## Re-review (closure tip 5c59524)

```
RE-REVIEWER: independent (wrote none of the code, none of the first review); detached worktree .claude/worktrees/rerev22-fence at 5c59524
CLOSURE:     5c59524 (docs) over code tip 2a73e77 (tree 16512161c935bdceda181b0adb16b6c41f5e0c1f); closure base c373957; cell base b23cb50
VERDICT:     APPROVE WITH FINDINGS (0 BLOCK · 2 MAJOR · 4 MINOR) — every first-review finding CLOSED in mechanism; two new MAJORs from the closure itself (§R3)
```

### R1. Per-finding status

| # | status | how verified |
|---|---|---|
| F1 | **CLOSED** — for the right reason | The reviewer's shapes re-applied as real textual mutants at 2a73e77 against the cell's killer set (421 tests, no `-x`, `git checkout --` in `finally`, sha256 `e598611fd277` identical after every mutant): **R6 KILLED 1 / 420** by `test_no_two_reconcile_results_are_compared_or_selected_between` (in-memory rules on the mutant text: B1 + B4 — the unit now spans the closure); **R7a KILLED 1 / 420** (N3), **R7b KILLED 1 / 420** (N1) by `test_name_integrity_holds_on_the_module`; **R8a 9 / 412** (N3 + the dynamic killers), **R8b 10 / 411** (N1), **R8c 10 / 411** (N1, N5, N6), **R8d 9 / 412** (N5, N6) — the static layer names each, no longer by accident. The residual walk-arounds are new findings, not F1's (§R3 N2). |
| F2 | **CLOSED** — recorded as disclosed | Nothing reverted, nothing to revert. The closure adds two more non-code hunks to the protected module (the `#:` block above the new constant; the builder's docstring) — `hunk_check.py` (AST, docstrings stripped, unparsed, diffed) between `f9bb315` and `2a73e77`: exactly `+HOSTED_EXTRACTION_REFUSAL_SUFFIX = f' (hosted extraction {…})'` and `+refusal.args = (f'{refusal}{HOSTED_EXTRACTION_REFUSAL_SUFFIX}',)`; top-level names added `['HOSTED_EXTRACTION_REFUSAL_SUFFIX']`, removed none. |
| F3 | **CLOSED IN MECHANISM — OPEN IN EFFECT** (§R3 N1) | `f3_check.py` at 2a73e77: for `unclaimed` / `parser_exception` / `ambiguous` the auto-mode exception is the SAME class, `str(auto).encode() == str(det).encode() + SUFFIX.encode()` (byte suffix, all three), `hosted_extraction == "refused_no_opt_in"`, no `__cause__`/`__context__`, the fake extractor never called; the deterministic exception carries neither. Deterministic mode never constructs it: `HOSTED_EXTRACTION_REFUSAL_SUFFIX` is read at one site (line 779, inside `_hosted_extraction_refused`), whose one call site (line 1043) is the statement after `if parse_mode == "deterministic": raise` — the ordering test and `test_deterministic_mode_never_reaches…[×3]` pin it. The seam test pins the CURRENT worker behaviour honestly: `auto_error == worker._stage_failure(_PHASE_ANALYSIS, RuntimeError())` with the docstring saying why. What that behaviour IS: `worker._analysis_failure(auto)` = `'analysis stage failed: RuntimeError (message withheld; …)'` where at c373957 it was the declared literal. |
| F4 | **CLOSED** | §P22FENCE-CLOSURE completes the surface list (`webapp/worker.py`, `analyze.py:188`, `batch.py:299`, `adb_debug.py:56`); `adb_debug.py --parse-mode` help rewritten (closure diff, help text only). |
| F5 | **CLOSED** for the two sites the cell owns | `README.md:228` no longer advertises the second model as a knob; `tools/extractpriv_reachability.py` docstring records the history (docstring-only hunk). `webapp/static/app.js:654` untouched (Ocean's) — and since F3 the auto-mode user no longer reaches that branch at all (§R3 N1). |
| F6 | **CLOSED** | `tests/test_privacy3_boundaries.py::test_the_parse_mode_clause…` — diff is the docstring alone (fixture and assertion byte-identical); it states the history, the present mechanism and the M7 property. M7 re-run: **KILLED 4 / 417** — `test_deterministic_mode_never_reaches…[unclaimed]`, the ordering test, `test_without_the_literal…[unclaimed]`, and (new since F3) the webapp equality test; the PRIVACY-3 dynamic test still does not kill it, as F6 states. |

### R2. Mutation table re-run at 2a73e77 (`mutants_rerev.py`; killer set = the fence file + privacy3 + q3 + test_analysis; baseline 421 passed in 57 s)

| mutant | mine (failed / passed) | cell's | static rule on the mutant text | killers |
|---|---:|---:|---|---|
| M1 | 10 / 411 | 10 / 411 | — | tripwire (a), ordering, inverted characterisation, pinned-False dynamic, privacy3 ×2, q3, 3 incidental `test_analysis` |
| M2 | 12 / 409 | 12 / 409 | B1, B2 | + tripwire (b), pinned-False static |
| M3 | 10 / 411 | 10 / 411 | — | `test_only_the_exact_literal_opts_in[×9]`, the seam test |
| M4 | 9 / 412 | 9 / 412 | — | read-at-call-site + every opted-in test + q3 |
| M5 | 16 / 405 | 16 / 405 | — | `test_without_the_literal…[×3]`, `…exact_literal…[×9]`, read-at-call-site, ordering, webapp equality, q3 |
| M6 | 18 / 403 | 18 / 403 | — | pinned-False static + dynamic, inverted characterisation (+ 15 anchor artefacts) |
| M7 | 4 / 417 | 4 / 417 | — | see F6 |
| R6 | **1 / 420** | 1 / 420 | B1, B4 | `test_no_two_reconcile_results…` |
| R7a | **1 / 420** | 1 / 420 | N3 | `test_name_integrity_holds_on_the_module` |
| R7b | **1 / 420** | 1 / 420 | N1 | same |
| R8a | 9 / 412 | 9 / 412 | N3 | name-integrity + inverted characterisation, pinned-False dynamic, privacy3 ×2, q3, 3 incidental |
| R8b | 10 / 411 | 10 / 411 | N1 | same + `test_analysis…manual_review` |
| R8c | 10 / 411 | 10 / 411 | N1, N5, N6 | same |
| R8d | 9 / 412 | 9 / 412 | N5, N6 | same |

14 / 14 killed; every count identical to the cell's `closure/mutants.log`; tree clean and `pipeline.py` byte-identical after each.

### R3. The name-integrity layer attacked with fresh shapes (real textual mutants, same harness, same killer set)

| shape | static rule | result |
|---|---|---|
| E1 `reconcile.__call__(…)` | N3 | KILLED 1 / 420 |
| E2 `functools.partial(reconcile, …)` | N3 | KILLED 1 / 420 |
| E3 `{"r": reconcile}["r"](…)` | N3 | KILLED 1 / 420 |
| E4 `operator.attrgetter("reconcile")(os.sys.modules[…])` | N5 | KILLED 1 / 420 |
| E5 `try: from .reconcile import reconcile / except ImportError` | N1 (2 canonical imports) | KILLED 1 / 420 |
| E6 `_r = lambda *a, **k: reconcile(*a, **k)` | B3 (call under a `Lambda`) | KILLED 1 / 420 |
| E7 `class _Verifier: fn = staticmethod(reconcile)` | N3 | KILLED 1 / 420 |
| E8a a decorator on `_analyse` re-invoking it and keeping the result whose `.reconciliation.ok` | — (blind) | KILLED 3 / 418 — dynamically only (the fake saw two calls) |
| **E8b** the same decorator, re-invoking only when `model_used.endswith("-deterministic")` | — (blind) | **SURVIVED 421 / 0** |
| E9a `sys.modules["analysis.reconcile"].reconcile` | N4, N6 | KILLED 1 / 420 |
| E9b `__builtins__["getattr"](os.sys.modules["analysis." + "reconcile"], "rec" + "oncile")` | N5 — on the `"reconcile"` fragment of the MODULE path, by luck of my spelling | KILLED 1 / 420 |
| E9c the same with `"analysis.recon" + "cile"` (in memory) | — (blind: N=[], B=[]) | not run; dynamically identical to E10 (no second extraction) |
| E9d `import sys as _s; _s.modules[…].__dict__["rec" + "oncile"]` (in memory) | — (blind) | not run; same |
| **E10** the ONE `recon = reconcile(…)` line moved into `for _candidate in (stmt, normalize_statement(stmt)): … if recon.ok: stmt = _candidate; break` | — (B1 one name, B2 one textual site, B3 permitted, B4 one root) | **SURVIVED 421 / 0** |
| **E11** `_alt = _account_report(alt, reconcile(alt, …), …); if _alt.reconciliation.ok and not recon.ok: stmt = alt` | — (the `_account_report` positional exemption; `.reconciliation` is not a guarded name) | **SURVIVED 421 / 0** |
| E10b `while not (recon := reconcile((stmt := next(_cands)), …)).ok` (in memory) | B3 | seen |
| extract.py exemption: `from .reconcile import reconcile` added to `analysis/extract.py` | the module-wide guard skips `extract.py` and `reconcile.py` wholesale | `test_no_other_module…` and `test_name_integrity…` both PASS (2 passed) |

What the layer honestly cannot see: (i) B2 counts textual binding sites, not executions — one reconcile-bound name re-assigned inside a loop is the idiomatic "try candidates until one reconciles" and passes B1–B4 (E10); (ii) a reconciliation result reached through `Report.reconciliation` / `_Analysed.accounts[i].reconciliation` rather than a `reconcile(` binding — re-invoking `_analyse` (E8) or consuming `reconcile(` into `_account_report` (E11, the B3 exemption); (iii) the N6 "dynamic doors closed as a class" are closed by NAME (`getattr`, `globals`, `sys.modules` as a Name attribute) — `__builtins__[…]`, an aliased `sys`, `os.sys.modules` and split string constants walk past it (E9c/E9d); (iv) `analysis/extract.py` and `analysis/reconcile.py` themselves, exempted wholesale by the module-wide guard, and any module outside `analysis/`. Of these, only a shape that makes a SECOND hosted call has a dynamic killer (E8a); a selection between non-hosted candidates (E8b, E10, E11) is seen by nothing in the killer set — only by the deterministic replay, and only where it changes a payload.

### R4. New findings from the closure, ranked

| # | severity | finding |
|---|---|---|
| N1 | **MAJOR** (composition-coupled) | The F3 closure changes what the webapp publishes for the default-mode user. At c373957 an auto-mode `unclaimed` refusal reached the job store as the declared literal `no deterministic parser matched this statement` (the ONE analysis error a user can act on — `tests/test_worker_privacy.py::test_the_declared_refusal_still_reaches_the_user`, D2) and `app.js` rendered its guidance. At 2a73e77 `_analysis_failure` (exact-match allow-list, by its own reviewed rule) reduces the suffixed message to `analysis stage failed: RuntimeError (message withheld; an exception message can quote statement text)` — a declared refusal now looks like a crash to the user, `friendlyAnalysisError`'s primary branch is unreachable in auto mode, and the fence file's seam test PINS that reduction, so a composed suite would defend it. Never less safe (no document text either way), strictly less informative, and it lands a change in the webapp's behaviour whose fix lives in a file the cell does not own. Closes with EITHER Ocean's one-line addition of the suffixed literal to `_DECLARED_ANALYSIS_REFUSALS` composed TOGETHER with an update of the seam test's pinned expectation (and the D2 test's rationale re-read against auto mode), OR reverting `2a73e77`'s message line and returning F3 to what the first review actually proposed — a follow-up for the worker owner. The auto-mode cache-key partition on the opt-in (F3, second half) remains open, recorded as Ocean's. |
| N2 | **MAJOR** | The strengthened tripwire (b) is walked around by the idiomatic loop form of the forbidden pattern (E10) and by the `_account_report`-positional route (E11); with the decorator re-invocation (E8b) that is 3 of 13 fresh shapes SURVIVING the whole killer set. F1 is closed for the shapes it named; the review plan's bar for a tripwire — hold against shapes it did not name — is not yet met. Small closure, tests only: B5 — a `Name = reconcile(…)` (or walrus) may not sit inside any `For`/`While`/comprehension/`Try` body of its unit; B3's positional exemption restricted to a `reconcile(` whose `_account_report(...)` call is itself the direct argument of `accounts.append(...)` inside the sibling `for`; and a guard that `Report.reconciliation` / `.accounts[…].reconciliation` is read in no `Compare`/`BoolOp`/`IfExp`/`Return` of `_analyse`, `analyze_markdown`, `analyze_document` or any decorator of them. |
| N3 | MINOR | The protected module now contradicts itself: the block comment at `analysis/pipeline.py:726-732` still says the refusal is recorded "never in the message, which `webapp/worker.py`'s declared-refusal allow-list and the router tests pin byte for byte", twelve lines above `HOSTED_EXTRACTION_REFUSAL_SUFFIX`. `adb_debug.py`'s new help ("refuses exactly as deterministic does") is true of class and outcome, not of the message. |
| N4 | MINOR | The module-wide import guard exempts `analysis/extract.py` and `analysis/reconcile.py` wholesale rather than exempting their DEFINITIONS (probe above: a `reconcile` import inside `extract.py` passes); N6 is name-based (E9c/E9d). Neither is exploited today (`git grep` at the tip: `extract.py` imports `genai`, `types`, `Settings`, `Statement` only). |
| N5 | MINOR (informational) | A FOURTH reword the W3 section could not record about itself: the docs commit was first `b0b91b4` (parent `2a73e77`, tree `ccff755d…`) and was reworded after a WORDS hit ("AFTER WORDS", `messages-final-b0b91b4.log`) into `5c59524` — tree identical, verified. The three remaps the section names are also tree-identical (`f298816…` / `201e476…` / `1651216…`) with parents rewritten in chain. Pre-existing and NOT the closure's: `ParserCrashError` / `AmbiguousParserError` do not survive a pickle round-trip (their `__init__` signatures), in deterministic mode too; nothing pickles them. |
| N6 | MINOR | The closure's own `2a73e77` message says "one new constant … nothing else"; textually the hunk also rewrites the builder's docstring and adds an eight-line `#:` block. AST-identical otherwise (F2), so recorded, not counted. |

### R5. Ownership, commits, trailers, W3

`git diff --stat c373957...5c59524`: `README.md` (+4/−1 prose), `adb_debug.py` (help text only), `analysis/pipeline.py` (23 lines; code = the constant + the message line, §F2), `tests/test_pipeline_escalation_fence.py` (+414/−… ; 54 tests), `tests/test_privacy3_boundaries.py` (docstring only), `tools/extractpriv_reachability.py` (docstring only), `W3_TRACKA_LOG.md` (one hunk, `@@ -70395,3 +70395,185 @@`, pure append; the two earlier sections untouched). Nothing under `webapp/**`, `telemetry/**`, `analysis/config.py`, `analysis/extract.py`. Four closure commits `4706404 → 94954f2 → 2a73e77 → 5c59524`, each with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_…` (4/4). The literal: `git grep -c` at 5c59524 = `analysis/pipeline.py` 1 + two `docs/*.md` cards; not in the main checkout's `.env`; `GEMINI_API_KEY` and the opt-in absent from my environment.

### R6. Scans and heavy proofs (lock window in `discovery_reports/train12-logs/rerev22-fence/MASTER.log`; every step its own log with `EXIT=`)

| step | re-derived by me | cell's | EXIT |
|---|---|---|---:|
| privacy scan `--base b23cb50 --ref 5c59524` (population = the run of record, 3,380) | added_lines **1,827** · documents_read 3,351 (29 no_cached_text) · **hit_count 0** (raw 25, all `words_class` by rule) · residue_files 0 · residue_sites 0 | 1,827 / 3,351 / 0 (raw 25) / 0 / 0 (`privacy-final-b0b91b4.log`, tree-identical) | 0 |
| message scan `b23cb50..5c59524` | commits_scanned **9** · **hit_count 0** · MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0 — 34 s | commits_scanned 9 · hit 0 · MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0 (`messages-final-5c59524.log`) | 0 |
| no-parser replay at the tip (`--shas` 685, `--expect-unresolved 29`) | population 685 · replayed 656 · unresolved 29 (= expected; the tool exits 3 otherwise) · newly validated 0 · other movement 0 · preserved 0 of 0 · regressions 0 / 0 · unchanged non-validated **656 (payload changed on 0)** — 20 s | 685 / 656 / 29 / 0 / 0 / 0 of 0 / 0 / 0 / 656 (0) | 0 |
| chunk 01 `--parser chase` at the tip | population 504 · replayed 504 · newly validated 0 · other movement 0 · preserved **504 of 504**, payload identical 504, changed 0 · regressions 0 / 0 · unchanged non-validated 0 (0) — 819 s | not re-run at the closure tree (ran at `ea0300d3` — §P22FENCE — and by the first reviewer at c373957; identical) | 0 |

**The cell's closure logs, read** (`discovery_reports/train12-logs/p22fence/closure/`, lock 02:25:23 → 02:36:10 after 20 polls): `mutants.log` 14/14 KILLED EXIT=0 (counts as in §R2); `guards.log` 275 passed EXIT=0; `conformance.log` 1,282 passed / 41 skipped EXIT=0; `replay-noparser-closure.log` 685 / 656 / 29 / 0 newly validated / 0 of 0 / 0 regressions / 656 (0) EXIT=0; `privacy.log` at 56859e7 added_lines 1,645 hit 0 EXIT=0; `messages.log` at 56859e7 EXIT=1 (WORDS 1 — `a314a65` "OVER UNITS", the disclosed reword); then `privacy-final-b0b91b4.log` hit 0 and `messages-final-5c59524.log` hit 0 over 9 commits, EXIT=0 each. Every number the section claims is in its log.

**Not re-running the union replay, the suite, the gate and the corpus slice — judged ACCEPTABLE.** The AST-level diff of the protected module is a module-level constant assignment (an f-string of another constant) and one statement inside a function with a single call site that textually and dynamically follows the deterministic-mode raise; no deterministic path executes a changed instruction, and the population that comes nearest the change (the no-parser 685) was replayed identical at the closure tree by the cell. Ocean's trigger ("beyond the message string") is met by the letter — a constant is not the message string — and not in substance. I ran chunk 01 and the no-parser replay at the tip anyway as a belt (table above), under the lock, one at a time.

**Lock window, recorded as it happened:** acquired 2026-09-10 08:54:47 (0 polls; `mkdir`); privacy 69 s, messages 34 s, no-parser 20 s, chunk 01 819 s (ended 09:10:29). At 09:10:06 cell H's closure-2 harness wrote `HARNESS.lock/holder.txt` INSIDE my held lock directory (a non-atomic acquisition on its side), so my `rmdir` failed (WinError 145) and the last 23 s of chunk 01 overlapped H's start; the lock is H's now and I did not remove it. The replay compares each payload against the run of record, so the overlap cannot change its verdict; it is disclosed because the rule is one harness at a time.

### R7. Instruments (scratchpad, untracked; nothing written into the tree but this section)
`mutants_rerev.py` (+ `.log`, `.json`) · `hunk_check.py` · `f3_check.py` · `rerev_heavy.py` · the extract.py probe (one-liner, restored with `git checkout --`). Worktree `.claude/worktrees/rerev22-fence` (5c59524, detached; this file is its only untracked change). Nothing merged, pushed or committed; `wave22-fence` untouched.
