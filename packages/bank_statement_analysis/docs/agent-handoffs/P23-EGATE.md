# Agent Handoff — P23-EGATE (Phase 2.3 cell E: extraction-quality metrics v2 — measured, versioned, admitted as nothing)

**Launch base:** `train13` at its opening commit (= `phase2.2-final` `d84af95`). Worktree
`.claude/worktrees/mt23-egate`, branch `wave23-egate`. Synthetic fixtures only until cell W's partitions
exist; the census over real evidence is the last step and reads the research partition READ-ONLY.

Read `docs/agent-handoffs/BATCH9-RULES.md`, `PHASE2-RULES.md`, `docs/moneythumb-replacement/PHASE2_RULINGS.md`
(Ruling B — density SURFACE-ONLY; the anti-optimizer rule; cost out of scope), the umbrella
`docs/agent-handoffs/PHASE2-3-WAVE.md` (D7, cases 6, 13, 14, the exclusions), the plan
`phase2_remainder/PHASE2_REMAINDER_PLAN.md` §G.2.3 cell W's E-metric list and §H.4 (E0–E5, precisely),
`docs/moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md` (the three failure classes; no validator → extractor
path), then the code: `ocr/escalation.py` (`ExtractionQualityGate`, the parameter-free admitted triad and the
`evidence_quality` column — the v1 you do NOT change), `evidence/` (`ExtractionEvidence`, `PageFrame`,
`WordBox`, `LineBox`, `group_lines`), `ocr/rasterize.py` (the CropBox raster, RASTER_VERSION 2),
`layout/signals.py` (the closed EN/FR/ES lexicons and shape regexes — read-only, imported), `discovery/runner.py`
(`_project_funnel`, `ROW_FIELDS`, the row's single exit), `tests/paddle_synthetic.py` (the synthetic page
renderer), `tests/fixtures/paddle/paddle_demo_wordboxes_res.json`. Ocean reviews and composes; you never
merge or push. **Hygiene card: `newly validated = 0`; no metric reaches a trigger, a verdict or a router;
no customer page leaves the machine (you send nothing anywhere); no cost field.**

# Why
Phase 2.5 will derive Paddle's production triggers from MEASURED evidence-quality conditions. Those
measurements do not exist. Ruling B's discipline is labelled evidence first, review, then admission — so
2.3 measures every candidate metric on every page, versions the thresholds, and admits none.

# What you deliver (ruled — do not re-decide)
1. **`ocr/extraction_quality.py`** — `EXTRACTION_QUALITY_VERSION = 1`; pure functions over one page's
   `ExtractionEvidence` page (+ optionally its raster bytes): word count and density (words per page area
   in the frame's own units); rec-score distribution (mean, p10) — carried as PER-CONFIGURATION figures, never
   compared across configurations; money-shape parse rate over numeric tokens; lexicon rate over alphabetic
   tokens (EN/FR/ES, from `layout/signals.py`); garbage-token rate (> 20 chars or repeated letters); box
   regularity (line-height coefficient of variation; numeric right-edge residual in character widths);
   ink-versus-box coverage from the raster (share of dark pixels outside any word box; `None` without a
   raster); orientation votes (from the words' own geometry; `None` when the extractor gives none). Every
   metric a named closed field; every threshold a named versioned constant in ONE table; `e_class(page) ∈
   {"", "E0", "E1", "E2", "E3", "E5"}` exactly as §H.4 defines them (E4 is review evidence for cell X, not a
   class here); the module imports the standard library, `evidence` and `layout.signals` only (an AST test).
2. **Row columns, appended to `ROW_FIELDS` (never reordered):** `eq_version`, `eq_word_count`, `eq_density`,
   `eq_rec_mean`, `eq_rec_p10`, `eq_money_rate`, `eq_lexicon_rate`, `eq_garbage_rate`, `eq_line_height_cv`,
   `eq_right_edge_residual`, `eq_ink_outside_boxes`, `eq_orientation_votes`, `eq_class` — per DOCUMENT the
   page-level figures folded as `min` / `max` / `mean` where a fold is meaningful and the worst page's
   E-class as `eq_class` (state the fold per column in the docstring); projected at the row's single exit in
   `discovery/runner.py` from the document's evidence ONLY when it carries extractor evidence (Paddle rows);
   empty otherwise; the row-shape test updated in the same commit.
3. **Admitted as nothing:** `ocr/escalation.py` untouched — `ADMITTED_TRIGGERS`, `RouterInputs`,
   `ExtractionQualityGate` byte-identical (a test pins the module's blob against the base); no import of
   `ocr.extraction_quality` anywhere under `ocr/escalation.py`, `analysis/`, `webapp/` (an AST guard);
   nothing reads `eq_*` but the report.
4. **Synthetic defect pages** (`tests/paddle_synthetic.py` extended or a sibling module): a blank page, a
   half-covered page, a 90° page, a noise page, a page with digit-like glyph substitution (`O`/`0`, `l`/`1`),
   a page with garbage tokens, a page with a repeated-letter run — each moves exactly the metric it targets
   past its threshold (a table in the W3: page → metric → value → class) and no other class fires.
5. **`tools/extraction_quality_census.py`** — READ-ONLY over a research partition's cached OCR artifacts
   (`--data-dir <research dir> --research-partition <id>`; refuses a production cache by T's door): the
   per-page and per-document distribution of every metric and the E-class counts, per configuration;
   printed as counts and percentiles only — never a page's text, never a sha with a verdict; the committed
   instrument for the census numbers in your W3 (run it on cell W's `paddle-v5-prod` partition when it
   exists; until then on the synthetic partition the fake worker produces).
6. **No hardcodes:** the module and the tool in the OQ2 scan roots.

# Files you own (exact; nothing else)
`ocr/extraction_quality.py` (new) · `discovery/runner.py` (the `eq_*` projection and the `ROW_FIELDS` append
ONLY) · `tools/extraction_quality_census.py` (new) · `tests/test_extraction_quality.py` (new) ·
`tests/paddle_synthetic.py` (APPEND defect pages) · the row-shape test · `tests/test_no_statement_hardcodes.py`
(the roots append) · your W3 section. `ocr/escalation.py`, `evidence/**`, `layout/**`, `analysis/**`,
`telemetry/**`, `webapp/**`, `tools/paddle_wave.py` are NOT yours.

# Mutation table (run every mutant, name every killer)
M1 a threshold changed without the version → the version/threshold-table pin · M2 the money-shape rate
computed over ALL tokens → the numeric-token synthetic · M3 the garbage rate ignoring repeated letters → its
synthetic · M4 ink-outside-boxes computed inside boxes → the half-covered synthetic · M5 `eq_class` set from
rec-score alone → the "p10 is a proxy, never a gate" test · M6 an `eq_*` value read in `ocr/escalation.py` or
by the router (planted in a scratch copy) → the AST guard · M7 `ROW_FIELDS` reordered → the row-shape pin ·
M8 the projection reading native-only rows → the empty-on-native test · M9 the census printing a page's text
→ the output-shape test · M10 the module importing `analysis` or `ocr.paddle_client` → the boundary test.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; `cohort_replay --expect-identical` at base and closure over the
`--parser` chunks (the runner changed: the offline partition byte-identical — the projection is empty on
every production row); the synthetic table; the census on the fake-worker partition, then on W's real
partition (read-only; counts only); privacy scan 0 over added lines; message scan 0. Heavy proofs one at a
time under the lock (mkdir-only; own-holder release; Git bash `rmdir`).

# Report contract (final message to Ocean AND your W3 section `# §P23EGATE — …`)
population (synthetic pages; the partition censused) · root cause · solution · newly validated 0 · ladder
movement 0 · preserved all, identical · regressions 0 · correctness evidence (the synthetic table; every
threshold versioned; the fold per column) · escalation evidence (the router byte-identical; no `eq_*`
reader outside the report) · the census (per configuration, counts and percentiles) · commits · proof
exits · privacy count · risks last (what the metrics cannot say without cell X's agreement and cell B's
fallout).

# Exclusions
No trigger · no verdict · no router change · no threshold tuned to a document · no cross-configuration
comparison of rec-scores · no Paddle call (cell W) · no cost.
