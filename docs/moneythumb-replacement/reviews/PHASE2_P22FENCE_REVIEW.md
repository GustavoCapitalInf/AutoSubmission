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

## Re-review 2 (closure-2 tip fc65067)

```
RE-REVIEWER 2: independent (wrote none of the code, none of the first review, none of the re-review);
               detached worktree .claude/worktrees/rerev22-fence at fc65067
CLOSURE-2:     fc65067 (documentation only) over code tip 1c09faa
               code tree 2be2cd27d799dd7fbeb416ec51fc1c78655eaf9d · fc65067 tree 9edb9c978209ed3821a66f64391230451771f785
               `git diff --stat 1c09faa fc65067` = W3_TRACKA_LOG.md alone (+172/-0)
CLOSURE-2 BASE: 5c59524      CELL BASE: b23cb50
VERDICT:       APPROVE WITH FINDINGS (0 BLOCK · 1 MAJOR · 2 MINOR) — every re-review finding N1–N6 CLOSED
               and re-proven by me; the MAJOR is a FRESH shape the closure-2 did not name (§RR2.4 P1)
```

### RR2.1 Per-finding status (N1–N6)

| # | status | how verified (my command, my output) |
|---|---|---|
| N1 | **CLOSED** | `n1_check2.py` at fc65067, all three outcomes, 31 assertions, 0 failures: same class, `str(auto).encode() == str(det).encode()` BYTE FOR BYTE, `auto.hosted_extraction == "refused_no_opt_in"`, `hasattr(det,"hosted_extraction") is False`, `auto.__cause__ is auto.__context__ is None`, fake extractor `calls == []`. `worker._analysis_failure(auto) == worker._analysis_failure(det)` for all three; for `unclaimed` both return `'no deterministic parser matched this statement'`, which is in `worker._DECLARED_ANALYSIS_REFUSALS`. `HOSTED_EXTRACTION_REFUSAL_SUFFIX` is absent from the module object AND the module text. Deterministic mode WITH the literal raises with no attribute, still zero calls. `test_the_declared_refusal_still_reaches_the_user` → **1 passed**; the fence file → **64 passed** (seam test included). |
| N2 | **CLOSED for the shapes it names — the property is not yet whole** | E10 / E11 / E8b re-applied by me as REAL textual mutants at fc65067's code tree against the full killer set: **E10 KILLED 2/429** (`test_no_two_reconcile_results…` B5 + `test_the_reviewers_loop_form_is_caught_by_b5`), **E11 KILLED 1/430** (same test, B3-narrowed + B6), **E8b KILLED 6/425** (`…orchestration_functions_are_undecorated…` O1/O2, B6, + 4 `test_q3_native_only`). Ten of my twelve FRESH shapes die on the static layer; one does not — §RR2.4 **P1 (MAJOR)**. |
| N3 | **CLOSED** | `git diff 5c59524...1c09faa -- analysis/pipeline.py`: the `#:` clause now reads "…pin byte for byte (a closed suffix on the message was tried and reverted at the review's N1 …). A DURABLE record of the refusal is the worker owner's composition item: publish the attribute when present." True of the code at fc65067 (N1 above). The builder's docstring says the same. `adb_debug.py` untouched by closure-2 and now true of class, outcome AND message. |
| N4 | **CLOSED** | `module_guard_violations` runs over every `analysis/*.py` except `pipeline.py`, definers included. The cell's probe re-run by me as a REAL mutant: **N4m KILLED 3/428** — `test_a_definer_reaching_the_other_name_or_aliasing_its_own_is_caught[extract-imports-reconcile]`, `[extract-imports-module]`, `test_no_other_module_under_analysis_imports_reconcile_or_extract_statement`; four definer shapes are parametrised in the file (2 per definer), each asserting clean-then-dirty. Honest limit, correctly stated and confirmed: a helper under `tools/` or `webapp/` is OUTSIDE this guard — not new, not closed here. |
| N5 | **RECORDED** | The `b0b91b4 → 5c59524` reword is in the W3. Not re-derived (tree-identical, outside closure-2's diff). |
| N6 | **CLOSED as recorded** | The closure declines to reword `2a73e77` because the line it understated is reverted — defensible; the commit stands as history. Both closure-2 commits carry `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` **1/1** and a `Claude-Session:` line **1/1**. N6's other half — the name-based dynamic doors — is stated as an open limit; the compensating property holds (X12, §RR2.3). |

### RR2.2 Mutation table re-run — all 18 canonical rows, my counts vs the cell's `mutants_table.log`

Harness `mutants_rerev2.py` (my copy; `WT` = **my** worktree `rerev22-fence`, never the cell's): exact textual edits, killer set = the fence file + `test_privacy3_boundaries.py` + `test_q3_native_only.py` + `test_analysis.py`, **no `-x`**, `git checkout -- analysis/pipeline.py analysis/extract.py` in a `finally`, and after EVERY mutant `git status --porcelain` asserted empty (the one untracked review file filtered) **and** both files asserted sha256-identical (`pipeline.py d5209942268d5c30`, `extract.py 57ddacb11c6a276e`). Refuses to start on a dirty tree. Baseline 431 passed.

| mutant | mine (failed / passed) | cell's | static rule / killer |
|---|---:|---:|---|
| M1 | 10 / 421 | 10 / 421 | tripwire (a) + dynamic |
| M2 | 12 / 419 | 12 / 419 | B1/B2 + (a) + inverted characterisation |
| M3 | 10 / 421 | 10 / 421 | exact-literal ×9 + seam |
| M4 | 9 / 422 | 9 / 422 | read-at-call-site |
| M5 | 16 / 415 | 16 / 415 | fence ×3, literal ×9, ordering, webapp equality, q3 |
| M6 | 21 / 410 | 21 / 410 | pinned-False static + dynamic + inverted (the other 18 ARE the anchor artefact — verified: the in-memory shape tests anchored on `escalated = False`) |
| M7 | 3 / 428 | 3 / 428 | deterministic-never-reaches[unclaimed], ordering, without-the-literal[unclaimed] |
| R6 | 1 / 430 | 1 / 430 | B1+B4 |
| R7a | 1 / 430 | 1 / 430 | N3 |
| R7b | 1 / 430 | 1 / 430 | N1 |
| R8a | 9 / 422 | 9 / 422 | N3 + dynamic |
| R8b | 10 / 421 | 10 / 421 | N1 + dynamic |
| R8c | 10 / 421 | 10 / 421 | N1/N5/N6 + dynamic |
| R8d | 9 / 422 | 9 / 422 | N5/N6 + dynamic |
| **E10** | **2 / 429** | 2 / 429 | B5 |
| **E11** | **1 / 430** | 1 / 430 | B3-narrowed + B6 |
| **E8b** | **6 / 425** | 6 / 425 | O1/O2 + B6 + 4 q3 |
| **N4m** | **3 / 428** | 3 / 428 | definer guard ×2 + module-wide guard |

**18 / 18 KILLED. Every count is identical to `mutants_table.log`, row for row.** Named killers match the cell's for every row I spot-checked (E10, E11, E8b, N4m, M6). My table: `discovery_reports/train12-logs/rerev22-fence/closure2/mutants.log` / `mutants_table.log` (elapsed 1,468 s, `EXIT=1` because of X11 below).

### RR2.3 Fresh attack shapes (twelve, each a REAL textual mutant, same harness, same killer set)

| # | shape | static rule | result |
|---|---|---|---|
| X1 | a `while` with a walrus reconcile selecting on `.ok` against `recon` | B1, B3, B5 | KILLED 1 / 430 |
| X2 | a reconcile-bound name read inside a comprehension in a NESTED function | B5 | KILLED 1 / 430 |
| X3 | a generator expression holding the second `reconcile(...)` | B3 | KILLED 1 / 430 |
| X4 | a second `_account_report(...)` in a NEW `for` appending to a differently named list | B3, B6 | KILLED 1 / 430 |
| X5 | a decorator applied by assignment after the def (`_analyse = _wrap(_analyse)`) | N2, N3, B6 | KILLED 14 / 417 |
| X6 | a class with `__call__` wrapping `_analyse` | O2, B6 | KILLED 2 / 429 |
| X7 | a `wraps`-free closure inside `analyze_document` re-invoking `_analyse` | O2, B6 | KILLED 8 / 423 |
| X8 | `try/except` around the one `reconcile(` binding, re-bound in the `except` | B1, B2 | KILLED 2 / 429 |
| X9 | a `match` statement holding the second reconcile and the selection | B1 | KILLED 1 / 430 |
| X10 | the sibling `accounts.append(_account_report(...))` moved inside an `if` in the loop | B3 | KILLED 1 / 430 |
| **X11** | **a fresh `reconcile(...)` bound INSIDE `_account_report` and preferred over the passed-in `recon`** | **none (B=[], N=[], O=[])** | **SURVIVED 431 / 0** |
| X12 | a SECOND HOSTED CALL through `__builtins__["getattr"]` + `os.sys.modules` + split string constants (the re-review's E9c/E9d class) | none (blind, as the section admits) | KILLED 9 / 422 — **dynamically**: `test_analysis` ×4, the inverted characterisation, pinned-False dynamic, privacy3 ×2, q3 |

X12 settles the section's honest limit in its favour: a shape that makes a SECOND HOSTED CALL through the doors N6 cannot see still dies, and dies in eight independent places, not one.

### RR2.4 New findings, ranked (each reproduced by my own command)

| # | severity | finding |
|---|---|---|
| **P1** | **MAJOR** | **The strengthened tripwire (b) is UNIT-scoped in a way that exempts `_account_report`, and a reconciliation-based selection placed there survives everything.** B1/B2/B4/B5 operate on names *bound from a `reconcile(...)` call in the unit*; `_account_report(stmt, recon, …)` receives its `ReconResult` as a **parameter**, so `recon` is not a reconcile-bound name of that unit and nothing compares against it. Mutant X11 — `_alt = normalize_statement(stmt)` / `_alt_recon = reconcile(_alt, parser_id=claiming_parser_id(dispatch))` / `if _alt_recon.ok and not recon.ok: stmt, recon = _alt, _alt_recon`, inserted above `quality = assess_quality(...)` — is verbatim "prefer whichever candidate reconciles" inside the protected module, and it returns `[]` from `name_integrity_violations`, `reconcile_selection_violations` AND `orchestration_shape_violations`, then **SURVIVED the whole killer set 431 / 0**. Two things make it worse than E10/E11/E8b: `_account_report` runs in **every** parse mode, for **every** account (the deterministic path included, where E8b/E10/E11 could only bite in auto mode); and the file already has a test (`test_a_nested_parameter_shadowing_the_reconcile_result_is_caught`) proving the authors knew a parameter can carry a reconcile result — it catches that case only because the parameter sits inside `_analyse`'s unit. The card's tripwire (b) is "no comparison of two `reconcile(...)` results **anywhere in `analysis/pipeline.py`**"; that bar is not met. Closure is small and tests-only: treat a parameter whose annotation is `ReconResult` as a reconcile-bound name of its unit for B1/B4/B5, and/or add B7 — the unit `_account_report` contains no `reconcile(` call at all (it is handed one). |
| P2 | MINOR | **A number in `§P22FENCE-CLOSURE-2` that names no log and does not reproduce.** The record note says "a number with no log does not exist, and every number below names its log"; the four "Targeted (freely)" numbers name none, and `grep -rlE "243 passed\|540 passed"` over `train12-logs/p22fence/closure2/` returns nothing. Re-derived at fc65067: "the fence file + `test_q3_native_only.py` + `test_analysis.py` + `test_pipeline*.py` + `test_structurer_pipeline.py` **243 passed**" is in fact **307 passed** (64 + 48 + 151 + 6 + 21 + 17); 243 is that set **minus the fence file's own 64**, which the same sentence reports separately. The others reproduce — fence file **64 passed**; the eight-file set **1 failed / 540 passed / 3 skipped** (+2 deselected, unmentioned), the failure being cell T's count guard. "The PRIVACY-3 subset 3 passed" is uncheckable: the file alone is 168 passed and no `-k` is named. A record defect, not a proof defect. |
| P3 | MINOR | **The tripwire's own block comment claims a rule the tripwire does not implement** — the same class of contradiction N3 was raised for. `tests/test_pipeline_escalation_fence.py`, the RE-INVOCATION paragraph: "no other function or lambda is defined at module level between the three (a wrapper needs a home)". `orchestration_shape_violations` implements O1 (no decorators) and O2 (the two callers) and nothing about module-level definitions. Reproduced: inserting `def _module_level_helper(): return None` — and separately `_module_level_lambda = lambda: None` — between `_analyse` and `analyze_document` yields `orchestration_shape_violations(...) == []`. Either implement the clause or delete it. |

### RR2.5 Hunk-by-hunk check of the protected module (`hunk_check2.py`: AST, docstrings stripped, unparsed, diffed)

`5c59524 → 1c09faa`, code-level diff is **exactly two removed lines and nothing else**:
`-HOSTED_EXTRACTION_REFUSAL_SUFFIX = f' (hosted extraction {…})'` and `-refusal.args = (f'{refusal}{HOSTED_EXTRACTION_REFUSAL_SUFFIX}',)`. Top-level names removed `['HOSTED_EXTRACTION_REFUSAL_SUFFIX']`, **added: none**. `escalated` bindings at the tip: `['escalated = False']`. `extract_statement` call nodes: **1**, with the ordering test (green) pinning the deterministic raise before it and the fence immediately before it. Textually the hunks also revert one `#:` block, rewrite the builder's docstring and reword one comment clause (N3) — comments and docstrings, disclosed, already covered by F2's rule.

### RR2.6 Ownership, trailers, the literal

`git diff --numstat 5c59524...fc65067` = exactly `analysis/pipeline.py` (16/18), `tests/test_pipeline_escalation_fence.py` (302/124), `W3_TRACKA_LOG.md` (172/0). Nothing under `webapp/**`, `telemetry/**`, `analysis/extract.py`, `analysis/reconcile.py`, `analysis/config.py`. `git diff --stat 1c09faa fc65067` = the W3 alone, so **fc65067's code tree IS 1c09faa's** (`2be2cd27…`, re-derived). The W3 change is a single hunk `@@ -70577,3 +70577,175 @@` and `w3_tip.startswith(w3_base)` is **True** — a pure append; the three earlier `# §P22FENCE` sections are byte-identical (the third after normalising the one trailing newline the split marker consumes). Trailers 1/1 on both commits. `git grep -c I_ACCEPT_HOSTED_MODEL_EXTRACTION fc65067` = `analysis/pipeline.py` 1 + the two docs cards, nothing else. The main checkout's gitignored `.env` has neither the variable nor the literal (`grep -c` = 0); the variable is unset in my environment.

### RR2.7 Scans and heavy proofs (my lock window 2026-09-10 **18:57:18Z → 19:36:20Z**; logs under `discovery_reports/train12-logs/rerev22-fence/closure2/`, each ending `EXIT=`)

| step | mine | Ocean's final (`*-fc65067.log`) | cell's (`closure2/*.log`, at 1c09faa) | EXIT |
|---|---|---|---|---:|
| privacy `--base b23cb50 --ref fc65067` | added_lines **2,175** · documents_read 3,351 (29 no_cached_text) · population 3,380 · **hit_count 0** (raw 27, all `words_class`) · residue_files 0 · residue_sites 0 | 2,175 / 3,351 / 0 (raw 27) / 0 / 0 — identical | 2,003 / 3,351 / 0 (raw 27) / 0 / 0 | 0 |
| messages `b23cb50..fc65067` | commits_scanned **11** · **hit_count 0** · MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0 | 11 · 0 · 0/0/0/0 — identical | 10 commits · 0 · 0/0/0/0 | 0 |
| no-parser replay at **fc65067** (belt, 25 s) | 685 · replayed 656 · unresolved 29 (expected; the tool exits 3 otherwise) · newly validated 0 · movement 0 · preserved 0 of 0 · regressions 0 / 0 · unchanged non-validated **656 (payload changed on 0)** | — | identical at 1c09faa (25 s) | 0 |
| mutation table (30 rows) | §RR2.2 / §RR2.3 | — | 18 rows, 926 s | 1 (X11) |

**Chunk 01, the union replay, the full suite, the gate and the corpus slice — NOT re-run, judged ACCEPTABLE.** fc65067 is documentation over 1c09faa (verified), and 1c09faa's code-level delta is the removal of one module constant and one statement inside `_hosted_extraction_refused`, whose single call site is the statement after `if parse_mode == "deterministic": raise`. No deterministic instruction changed. The cell ran chunk 01 at 1c09faa (504 / 504 preserved, payload identical 504, 0 regressions, 586 s, `EXIT=0`); I re-derived the no-parser replay and both scans at fc65067. Guards (275) and conformance (1,282 / 41 skipped) were read from the cell's logs, not re-run — neither exercises a changed line. Cell T's `test_diagnostics` count guard and cell K's `.env`-sensitive run-of-record test fail on this branch as Ocean named; neither is this cell's.

### RR2.8 W3 transcription check (`§P22FENCE-CLOSURE-2` against its logs)

Verified against `MASTER.log`, `mutants.log`, `mutants_table.log`, `guards.log`, `conformance.log`, `replay-noparser-closure.log`, `replay-chunk01-closure.log`, `privacy.log`, `messages.log`:
lock acquired **09:53:27 after 15 polls of 120 s, first poll 09:23:26**, last step ended **10:20:33**, release `PermissionError` leaving an empty orphan — all four exact; mutation table **926 s, 18/18, survivors []**, and **every one of the 18 failed/passed pairs and every named killer** matches; guards **275**; conformance **1,282 / 41 skipped**; no-parser **685 / 656 / 29 / 0 / 0 / 0 of 0 / 0 / 656 (0), 25 s**; chunk 01 **504 / 504 / 504 identical / 0 / 0, 586 s**; privacy at 1c09faa **added_lines 2003, documents_read 3351, hit 0, raw 27, residue 0 / 0**; messages at 1c09faa **commits_scanned 10, hit 0, 0/0/0/0**. Code tip and tree hashes as written. **One discrepancy, §RR2.4 P2** — the "243 passed" targeted number (and the four targeted numbers' missing logs). Everything else transcribes correctly.

### RR2.9 Properties I attacked and could not break (named)

1. **Message identity after the revert** — same class, same message BYTES, all three outcomes, both entry points; the webapp publishes the declared literal again (31 assertions).
2. **The attribute is the only distinguishing mark** — on the auto refusal, absent on the deterministic one, in no message and no payload.
3. **Deterministic mode never constructs the refusal and never calls the extractor** — with the literal set, all three outcomes, zero calls; M7 KILLED 3 / 428.
4. **Exactly one `extract_statement` call node, behind the deterministic raise and immediately behind the fence** — M1 / M5 / R8a–R8d killed.
5. **`escalated` is the constant `False`**, the sole binding in the module — M6 KILLED 21 / 410.
6. **A SECOND HOSTED CALL dies even through doors the name layer cannot see** — X12 KILLED 9 / 422 by eight independent tests.
7. **The definer exemption is gone** — N4m KILLED 3 / 428.
8. **Re-invocation of `_analyse` is pinned** — E8b, X5, X6, X7 all killed.
9. **Ten of twelve fresh selection shapes die on the STATIC layer alone**, seven of them 1 failed / 430 passed — no dynamic help.
10. **Deterministic-mode identity at the closure-2 tree** — no-parser 656 payload-identical at fc65067 (mine); chunk 01 504 / 504 at 1c09faa (the cell's).
11. **Ownership, trailers, the literal, the pure W3 append** — §RR2.6.

### RR2.10 Instruments (untracked, in my session scratchpad; nothing written into the tree but this section)

`shapes_rerev2.py` (the twelve fresh shapes) · `static_probe2.py` (in-memory rule classification) · `mutants_rerev2.py` (+ `.log`/`.json`; 30 real mutants) · `hunk_check2.py` · `n1_check2.py` · `rerev2_heavy.py` (lock + heavy driver) · `private/` (replay and privacy-hit outputs). Worktree `.claude/worktrees/rerev22-fence` at fc65067, detached; `git status --porcelain` shows only this review file. Nothing merged, pushed or committed; `wave22-fence`, the main checkout, the archive and the caches untouched. **Lock incident, disclosed:** my release unlinked `holder.txt`, then `os.rmdir` returned `PermissionError` WinError 5 on the now-EMPTY directory for ~12 minutes (the driver's 300 s plus 40 further attempts); Git bash `rmdir HARNESS.lock` succeeded at once. The lock IS released; the host lesson is in my `MASTER.log`.

## Re-review 3 (closure-3 tip 26284bd)

```
RE-REVIEWER 2 (round 3): independent (wrote none of the code, none of the earlier reviews);
               detached worktree .claude/worktrees/rerev22-fence at 26284bd
CLOSURE-3:     26284bd (documentation only) over code tip 55ed07c
               26284bd tree d366e09f3933a1dc52690e28bb6d14d24c093399 · 55ed07c tree c224a3ad725f6bd7c4579f2d8665e53d10482647
               `git diff --numstat 55ed07c 26284bd` = W3_TRACKA_LOG.md alone (+237/-0)
CLOSURE-3 BASE: fc65067      CELL BASE: b23cb50
VERDICT:       APPROVE WITH FINDINGS (0 BLOCK · 0 MAJOR · 2 MINOR) — P1, P2 and P3 CLOSED and re-proven
               by me; 39/39 mutants killed, including nine FRESH shapes aimed at the closure-3 rules
```

### RR3.1 The central claim: the protected module is untouched

`git rev-parse <rev>:analysis/pipeline.py` = **`e7956e9417ae50b7d361750bffb630cfeeaf621c` at `fc65067`, `9909cbf`, `55ed07c` AND `26284bd`** — one blob, byte for byte, across the whole closure. `git diff --numstat fc65067...26284bd` = exactly `tests/test_pipeline_escalation_fence.py` (+237/−17) and `docs/moneythumb-replacement/W3_TRACKA_LOG.md` (+237/−0); nothing else, in particular nothing under `analysis/`, `webapp/`, `telemetry/`, `tools/`. **No replay, gate, corpus slice or suite is owed at this tip and I ran none** — there is no changed instruction for a deterministic path to execute. That is the cell's own reasoning and I checked the blob myself rather than accepting it.

### RR3.2 Per-finding status (P1, P2, P3)

| # | status | how verified (my command, my output) |
|---|---|---|
| **P1** | **CLOSED — and closed twice over, as claimed** | `static_probe3.py` at 55ed07c: the UNCHANGED module returns **CLEAN** from all three layers (no false positive from the new parameter mark). Exactly three units hold a marked parameter — `assess_quality`, `assess_document_integrity`, `_account_report`, each one `recon: ReconResult` — and exactly one unit contains a `reconcile(` call: **`_analyse`, with 2**; `UNITS_THAT_MAY_CALL_RECONCILE == {'_analyse'}`. X11 (the re-review-2 mutant, edit text mine, reused verbatim) now trips **B1 + B2 + B4 + B7** in `_account_report` — the four rules the section names — and as a REAL textual mutant is **KILLED 2 / 438** by `test_no_two_reconcile_results_are_compared_or_selected_between` and `test_reconcile_is_called_only_in_the_unit_the_rules_permit`. The "closed twice over" claim is literally true and I separated the two halves: **Y1** (the parameter RENAMED to `r` and UN-ANNOTATED, aliased back, then X11's selection) defeats the parameter mark exactly as the section's own Risks predict — and is still **KILLED 3 / 437**, static rule **B7 alone**. |
| **P2** | **CLOSED** | The "243" is corrected in the record with the arithmetic and the reason (the set reported without the file it names first). Every targeted set is re-run into its own named log, and I re-derived all of them at 26284bd myself: fence file **73 passed**, `test_privacy3_boundaries.py` **168 passed**, the killer set **440 passed** (= the mutation baseline in my own harness), the corrected pipeline set **316 passed** (= 307 + 9), guards **275 passed**; the eight-file webapp set is **1 failed / 540 passed / 3 skipped / 2 deselected** in `targeted-webapp-set.log`, the failure being cell T's `test_reconciliation_issue_sites_match_the_anchor_count` (`assert 6 == 7`). Each of the five `targeted-*.log` files and `guards.log` ends `EXIT=`. The uncheckable "PRIVACY-3 subset 3 passed" is dropped in favour of the whole file — the right call. |
| **P3** | **CLOSED** | The false clause is DELETED, not implemented, per Ocean's ruling; the RE-INVOCATION comment now states O1 and O2 and names what is deliberately unchecked. The premise is pinned rather than asserted: `test_a_module_level_definition_that_calls_nothing_is_inert_and_deliberately_uncaught` (def and lambda) plus the wrapper that DOES call `_analyse` → **O2**. The amend `9909cbf → 55ed07c` that restated those pins RELATIVELY (`== reconcile_selection_violations(source)` instead of `== []`) is a genuine fix, disclosed: `git diff 9909cbf 55ed07c` is that test alone (+18/−10). An absolute `== []` pin in a test that other mutants perturb is an anchor artefact killer, and it is right that it was caught and fixed before the table was believed. |

### RR3.3 Mutation table — 39 real textual mutants in MY worktree

`mutants_rerev3.py`: the 18 canonical rows and my twelve X shapes reused verbatim from my round-2 instruments, plus **nine FRESH Y shapes**. Killer set = fence + privacy3 + q3 + `test_analysis`, baseline **440 passed** (re-derived), **no `-x`**, `git checkout -- analysis/pipeline.py analysis/extract.py` in a `finally`, and after EVERY mutant `git status --porcelain` asserted empty (the one untracked review file filtered — I did not need to move it aside) **and** both files asserted sha256-identical. Each mutant's text is also run through the three checkers in memory, so my table names the rule as well as the killer. Unmutated module: **CLEAN**. Elapsed 1,690.8 s, `EXIT=0`, **survivors: none**.

**All 30 of the cell's rows reproduce its `mutants.log` count for count** — M1 10/430 · M2 13/427 · M3 10/430 · M4 9/431 · M5 16/424 · M6 21/419 · M7 3/437 · R6 2/438 · R7a 1/439 · R7b 1/439 · R8a 9/431 · R8b 10/430 · R8c 10/430 · R8d 9/431 · E10 2/438 · E11 2/438 · E8b 6/434 · N4m 3/437 · X1 2/438 · X2 1/439 · X3 2/438 · X4 2/438 · X5 14/426 · X6 2/438 · X7 8/432 · X8 3/437 · X9 2/438 · X10 1/439 · **X11 2/438** · X12 9/431 — and a programmatic diff of the W3 table against `mutants.log` reports **no mismatch on any of the 30 rows**.

### RR3.4 My nine fresh shapes against the closure-3 rules

| # | shape | static rule | result |
|---|---|---|---|
| **Y1** | the `ReconResult` parameter RENAMED and UN-ANNOTATED (`r`), aliased back, then X11's selection — the "third spelling" the section names as its own limit | **B7 alone** | KILLED 3 / 437 |
| Y2 | a helper defined INSIDE `_analyse` taking the result as a parameter (is a nested def part of the unit? yes) | B1, B2, B4 | KILLED 2 / 438 |
| Y3 | the sibling loop's permitted positional `reconcile(` bound first in a tuple-unpack | B3 | KILLED 1 / 439 |
| Y4 | the result stored on an OBJECT ATTRIBUTE (`self.value`) and compared in a unit that makes no call | B2, B3 | KILLED 2 / 438 |
| Y5 | `functools.partial(reconcile, …)` used for the second reconciliation | N3 | KILLED 1 / 439 |
| Y6 | a NESTED `def _analyse` shadow calling `reconcile` | B3, O2 | KILLED 3 / 437 |
| **Y7** | a SECOND TOP-LEVEL `def _analyse` before the real one, holding a reconciliation selection | **none — all three layers CLEAN** | KILLED 1 / 439 — by tripwire (a) only (§RR3.5 Q2) |
| Y8 | a `reconcile(` in the MODULE BODY unit under `if False:` | B7 | KILLED 2 / 438 |
| Y9 | the two-result delivery across the seam: the sibling loop hands the PRIMARY's `recon` on to `_account_report` beside the sibling's own | B5 | KILLED 1 / 439 |

Y1 and Y9 are the two that matter. **Y1** confirms the section's honest limit and its compensating argument in the same breath: the parameter mark IS defeated by a rename, and B7 alone still refuses the call that would have to make the second result. **Y9** is the shape that needs no call in the comparing unit at all — two results delivered across the `_account_report` seam — and it dies on **B5**, because the only place the module can hand the primary's result to the sibling's is inside the sibling `for` loop, where reading a reconcile-bound name is refused. The layer is genuinely layered: defeat one rule and the next one is already standing.

### RR3.5 New findings, ranked (each reproduced by my own command)

| # | severity | finding |
|---|---|---|
| **Q1** | MINOR | **The W3 claims two mutation tables survive in one log; only the second does.** §P22FENCE-CLOSURE-3 says of the superseded window-1 run "both are in `mutants_table.log`'s successive runs and in `MASTER.log`". The harness writes its log with `write_text`, so window 2 OVERWROTE window 1: `grep -c "mutation table" mutants_table.log` = **1** (header `HEAD 55ed07c…`, 30 rows) and `grep -c "^# mutants @" mutants.log` = **1** (`@ 2026-09-11T00:18:28Z`, window 2). The window-1 table — the one whose 20 artefact killers are the reason the amend happened — cannot be inspected by anyone, and `git merge-base --is-ancestor 9909cbf 26284bd` shows its commit is **dangling**, so it cannot be regenerated either. What DOES survive is `MASTER.log`'s `END mutants: EXIT=0 in 1366s` for window 1, which is what the section should have claimed. No proof in the section rests on the missing table (every number I checked is window 2's, at `55ed07c`), so this is a record defect of exactly the class P2 was, not a proof defect. |
| **Q2** | MINOR | **B7's permitted-unit set is keyed on a duplicable label, and the duplicate is killed only incidentally.** `_units` emits one entry per top-level function and does not refuse duplicate labels; B7 permits any unit labelled `_analyse`. Mutant Y7 — a SECOND top-level `def _analyse(markdown, r)` inserted before the real one, holding `_alt = reconcile(...)` / `if _alt.ok and not r.ok: return _alt` — makes all three layers report **CLEAN** (reproduced: `units labelled _analyse: 2`, `B7 violations: NONE`, `name/selection/orchestration: CLEAN`), and B7's own test still passes because its `callers` dict collapses the duplicate label so `len(callers["_analyse"]) == 2` holds. The mutant is KILLED **1 / 439** — by `test_at_most_one_extract_statement_call_in_the_module_inside_the_analysis_body`, whose helper `_function(tree, "_analyse")` returns the FIRST match and then finds 0 `extract_statement` calls in it. That is tripwire (a) catching a selection-layer shape by an accident of a helper written for another purpose. The hole is closed in both placements — before the real def by that accident, after it because the shadow would REPLACE `_analyse` and die dynamically — so nothing is exploitable today; but a rule whose whole job is "only the permitted unit may call reconcile" should not depend on a coincidence. One line closes it: assert exactly one top-level definition per orchestration name, or make `_units` refuse a duplicate label. |

### RR3.6 Ownership, rewords, trailers, the literal, the W3 append

Two commits on `fc65067`: `55ed07c` (the test file alone) and `26284bd` (the W3 alone). Both carry `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` **1/1** and a `Claude-Session:` line **1/1**. Both disclosed rewrites check out as described: **`9909cbf → 55ed07c`** is an AMEND, trees deliberately DIFFERENT (`2ea21f95…` → `c224a3ad…`), the delta being the P3 pins restated relatively (+18/−10 in the test file) — the section says so; **`bb23678 → 26284bd`** is a pure reword, trees IDENTICAL (`d366e09f…` both) with the same parent `55ed07c`. Both pre-rewrite commits are dangling (`--is-ancestor` false). `9909cbf` is named in the section only as history in the lock narrative; `bb23678` is not named (it could not be); **no proof, table or scan in the section is anchored on a dangling sha** — the table header and the scans name `55ed07c`. The W3 change is one hunk `@@ -70749,3 +70749,240 @@`, `w3_tip.startswith(w3_base)` is **True** (+237 lines), the appended text begins with the heading, and the **four earlier `# §P22FENCE` sections are byte-identical**. `git grep -c I_ACCEPT_HOSTED_MODEL_EXTRACTION 26284bd` = `analysis/pipeline.py` 1 + the two docs cards, nothing else.

### RR3.7 Scans, re-derived at BOTH tips (my lock window 2026-09-11 **01:49:29Z → 02:19:07Z**, 0 polls)

| scan | mine | the cell's | EXIT |
|---|---|---|---:|
| privacy `b23cb50..55ed07c` | added_lines **2,395** · documents_read 3,351 · population 3,380 · **hit_count 0** (raw 31) · residue_files 0 · residue_sites 0 | identical (`privacy.log`) | 0 |
| messages `b23cb50..55ed07c` | commits_scanned **12** · **hit 0** · MONEY/DIGITS/DATES/WORDS 0/0/0/0 | identical (`messages.log`) | 0 |
| privacy `b23cb50..26284bd` | added_lines **2,632** · **hit_count 0** (raw 35) · residue 0 / 0 | identical (`privacy-final.log`) | 0 |
| messages `b23cb50..26284bd` | commits_scanned **13** · **hit 0** · 0/0/0/0 | identical (`messages-final.log`) | 0 |

Note for the record, from `MASTER.log`: the cell's final scans ran TWICE — once at `bb23678` (01:01:23Z, messages `EXIT=1`, the WORDS 1 that caused the reword) and again at `26284bd` (01:40:18Z, `EXIT=0`), the second overwriting the first. The surviving `privacy-final.log` / `messages-final.log` are the `26284bd` pair, which is the correct pair, and my independent run at `26284bd` reproduces them. The section promised "a third short window"; there were in fact two more (windows 3 and 4), both after the section's commit and so outside it.

### RR3.8 W3 transcription check (`§P22FENCE-CLOSURE-3` against its logs)

Verified line by line against `MASTER.log`, `mutants.log`, `mutants_table.log`, the five `targeted-*.log`, `guards.log`, `privacy*.log`, `messages*.log`: **all 30 mutation rows** (programmatic diff, no mismatch), the static-rule column spot-checked (X11, E11, M2, X8) against the harness's own `static rules on the mutant text:` lines; targeted 73 / 168 / 440 / 316 / (1f 540p 3s 2d); guards 275; privacy 2,395 raw 31 residue 0 and messages 12 at `55ed07c`; privacy 2,632 raw 35 and messages 13 at `26284bd`; **window 1** 22:36:28Z → 23:00:59Z, first poll 20:00:28Z, **156 polls**, mutants **1,366 s** `EXIT=0`, privacy 24 s, messages 21 s **`EXIT=1`**; **window 2** 23:55:07Z → 00:20:12Z, first poll 23:03:07Z, **52 polls**, mutants **1,402 s** `EXIT=0`, messages **`EXIT=0`**; both releases `LOCK git-bash rmdir exit=0` then `directory present after release: False`; the blob hash and both tree hashes. **One discrepancy: §RR3.5 Q1** — the claim that both mutation tables survive in `mutants_table.log`. Everything else transcribes correctly.

### RR3.9 Properties I attacked and could not break (named)

1. **The protected module is byte-identical across the whole closure** — one blob at four commits, so deterministic behaviour cannot have moved.
2. **No false positive from the new rules** — the unmutated module is CLEAN from all three layers; exactly three units hold a marked parameter and exactly one unit makes a `reconcile(` call.
3. **P1's shape is dead** — X11 trips four rules and is killed by two tests; the rename walk-around (Y1) still dies on B7 alone.
4. **A second result cannot be DELIVERED across the seam either** — Y9 dies on B5; Y4's attribute route dies on B2/B3; Y3's tuple-unpack on B3.
5. **Nested scopes are part of their unit** — Y2 and Y6 die inside `_analyse`.
6. **The permitted-unit rule holds over the module body** — Y8 dies on B7 even under `if False:`.
7. **Name integrity still refuses the indirect handles** — Y5 (`functools.partial`), R7a/R7b, R8a–R8d.
8. **A second HOSTED call still dies through the doors the name layer cannot see** — X12 KILLED 9 / 431, dynamically, across four files.
9. **Every earlier round's shape stays dead at this tree** — 30 / 30, count for count.
10. **Ownership, trailers, the literal, the pure W3 append, both disclosed rewrites** — §RR3.6.

### RR3.10 Instruments (untracked, in my session scratchpad; nothing written into the tree but this section)

`shapes_rerev3.py` (the nine Y shapes) · `static_probe3.py` · `mutants_rerev3.py` (+ `.log`/`.json`; 39 real mutants, reusing `mutants_rerev2.py`'s canonical rows and `shapes_rerev2.py`'s X shapes) · `rerev3_heavy.py` (lock + heavy driver) · `private3/`. Logs under `discovery_reports/train12-logs/rerev22-fence/closure3/`, each ending `EXIT=`. Worktree `.claude/worktrees/rerev22-fence` detached at `26284bd`; `git status --porcelain` shows only this review file. Lock taken by `mkdir` alone, `holder.txt` written inside the directory I created, released by Git bash `rmdir` on the first attempt with the directory's absence confirmed — the round-2 OneDrive lesson applied, and no `PermissionError` loop this time. Nothing merged, pushed or committed; `wave22-fence`, the main checkout, the archive and the caches untouched.
