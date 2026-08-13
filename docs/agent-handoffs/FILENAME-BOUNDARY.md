# Agent Handoff — FILENAME-BOUNDARY

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13 coverage wave. **Single integration owner for
the provenance/evidence admissibility boundary — the wave's highest-leverage
platform fix.** Evidence: the F-PROVENANCE report (harnesses + verified
reproducers in the wave scratchpad: fuzz2-5.py, fp_probe.py; run the two
inline reproducers in the report first — they show identical statement
bytes producing three different published answers, and admissible_text()
neutralizing it).

# Identity
- **Agent:** FILENAME-BOUNDARY · apply the existing R-4b admissibility
  boundary to PARSING, fix the abbreviated-month KeyError, retire the
  stale filename input from the analysis cache key.

# Git ownership
- **Base:** current main (record the SHA) · **Branch:**
  `wave3-filename-boundary` · **Worktree:** `.claude/worktrees/mt-filename`.

# The measured defect (F-PROVENANCE, 4,000 + 1,800 trials)
Parse paths receive the whole markdown including the line-1 source-filename
comment. 7 of 10 sampled parsers read financial evidence from it: period
replacement recomputes ADB/daily balances silently (up to +521%, one sign
flip); period-windowing drops transactions and changes totals; wells'
`_infer_year` (analysis/wells.py) takes the FIRST word-bounded year token
in the document — the comment line; `date_tokens.period_from_long_dates`
(analysis/date_tokens.py:115) raises KeyError on abbreviated months
(ParserCrashError in deterministic mode; in webapp auto mode the crash
falls through to LLM extraction — an engine swap by filename). Live
census: 0/1,615 published records currently affected (naming-convention
luck). `admissible_text()` (analysis/parser_registry.py:190-204) already
neutralizes ALL of it and is applied only to detection today — its own
docstring ("Parsing is unaffected") is the vulnerability.

# Cards
1. **The boundary (pipeline).** Apply `admissible_text()` at the single
   parse seam in `analysis/pipeline.py::analyze_markdown` so every parser
   receives provenance-free text — one boundary, not per-parser
   exclusions. Keep line indices stable (admissible_text substitutes an
   empty line — verified). Detection path unchanged (already admissible).
   Update the parser_registry docstring line that documented the hole.
   Minimal diff, quoted verbatim in your report — pipeline changes get
   Ocean forensic review at merge.
2. **date_tokens crash.** `analysis/date_tokens.py:115`:
   `_MONTH_NAMES[sm]` → a miss must be a non-match (`None`), never a
   KeyError. Fixture: abbreviated month in a long-date phrase no longer
   crashes any consumer; genuine long dates unchanged.
3. **Cache key.** `webapp/artifact_cache.py:80-84` keeps the filename in
   the analysis-stage cache input with a justification R-4b obsoleted
   (detection is filename-blind now). With card 1, parsing is too. Remove
   the filename from the analysis-stage key input and update the comment
   to say WHY (each rename otherwise mints a separate durably-cached
   report). Note in your report: this alone re-keys every cached analysis
   (full recompute on next run, identical results expected) — Ocean
   handles the operational cost at merge alongside the stage bump.
4. **Permanent invariance test.** A default-suite test asserting the
   primary invariant on representative parsers (chase, wells_fargo,
   square_checking, bmo_ca_business minimum): identical statement body ×
   hostile filenames (the F-PROVENANCE mutation set: period grammars,
   through-phrases, bare years, abbreviated months) → byte-identical
   published analysis. This is the test that keeps the boundary closed.

# Proof contract
- Re-run the F-PROVENANCE harnesses post-fix from the scratchpad:
  fuzz2 and fuzz3 expect ZERO violated documents; fuzz5 parity expects
  0/200 output changes vs the boundary applied. Cite counts + exit codes.
- Full default suite; corpus-marked; corpus_gate.py GREEN 106/3
  byte-identical; guards; conformance cross-product zero (detection is
  untouched — prove score/claim invariance on the probe set anyway).
- Zero outcome movement expected archive-wide (census says nothing
  published changes). Ocean runs the instrument at merge; your preview
  must predict zero.

# Scope
- **Allowed:** `analysis/pipeline.py` (card 1 seam only),
  `analysis/date_tokens.py` (card 2 only), `webapp/artifact_cache.py`
  (card 3 comment + key-input lines only; do NOT touch
  ANALYSIS_STAGE_VERSION — Ocean's), `analysis/parser_registry.py`
  (docstring only), tests, `W3_TRACKA_LOG.md` (append §FILENAME-BOUNDARY).
- **Protected:** everything else. No parser edits (wells' _infer_year
  becomes unreachable-from-provenance via the boundary — do not also
  patch it; one fix, one seam). reconcile/adb/metrics/serialization
  untouched.

# Stop conditions
Any parser needing an edit for the boundary to hold (report it instead);
any fuzz harness still showing a violation post-fix; any output change on
the fuzz5 parity sweep; gate not byte-identical; line-index instability.

# Final report to Ocean
Verbatim diffs (pipeline hunk first); the four proof reruns with counts
and exit codes; the invariance test inventory; cache-key implications
stated; commit list; risks; unresolved questions.
