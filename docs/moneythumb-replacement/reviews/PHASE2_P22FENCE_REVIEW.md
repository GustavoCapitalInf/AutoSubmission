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
