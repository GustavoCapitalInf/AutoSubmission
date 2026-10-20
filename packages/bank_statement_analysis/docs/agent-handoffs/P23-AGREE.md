# Agent Handoff — P23-AGREE (Phase 2.3 cell X: native↔Paddle agreement, the geometry census, the two latent native-reader defects)

**Launch base:** `train13` at its opening commit (= `phase2.2-final` `d84af95`). Worktree
`.claude/worktrees/mt23-agree`, branch `wave23-agree`. Synthetic native+raster pairs first; the census over
real evidence reads cell W's research partition READ-ONLY, CTRL before U755 (the calibration comes from
known-good documents).

Read `docs/agent-handoffs/BATCH9-RULES.md`, `PHASE2-RULES.md`, `docs/moneythumb-replacement/PHASE2_RULINGS.md`
(the anti-optimizer rule — E4 cross-engine disagreement is REVIEW EVIDENCE, never a third engine; cost out
of scope), the umbrella `docs/agent-handoffs/PHASE2-3-WAVE.md` (D3, cases 7, 13, the exclusions), the plan
§G.2.3 cell X and §H.4 (E4), the K sections `§P22IDENTITY*` in `W3_TRACKA_LOG.md` (the display frame, ruling (c)
— a `pdf_point` frame is a viewport, out-of-frame words noted; the four-angle pin) and the K re-review
`reviews/PHASE2_P22IDENTITY_REVIEW.md` §Re-review N-1 / N-2 (the two latent MINORs you close), then the
code: `evidence/` (`ExtractionEvidence`, `PageFrame` with the two spaces `pdf_point` / `pixel`, `WordBox`,
`LineBox`, `group_lines`), `evidence/native.py` (`native_evidence_from_pdf`, `_raw_rotate`, the CropBox
frame), `ocr/rasterize.py` (RASTER_VERSION 2 — the same CropBox rectangle), `ocr/document.py`
(`StatementMarkdown.evidence` / `.native_evidence`), `analysis/structurer/geometry.py`
(`geometry_from_evidence` — read-only), `tests/test_native_evidence.py` (the four-angle Poppler pin),
`tests/test_geometry_frames.py`. Ocean reviews and composes; you never merge or push. **Hygiene card:
`newly validated = 0`; no agreement statistic reaches a verdict or a router; no customer page leaves the
machine; no cost field.**

# Why
2.4's LayoutModel will build structure from geometry that comes from two sources — native words and Paddle
words — and 2.5 will admit Paddle only where it is measured to add evidence. Neither can be judged without
knowing what agreement between the two sources looks like on known-good documents, and where they disagree
on the unresolved ones. That calibration is this cell's; it decides nothing.

# What you deliver (ruled — do not re-decide)
1. **`layout/agreement.py`** — `AGREEMENT_VERSION = 1`; pure functions over one page's two
   `ExtractionEvidence` pages: frame normalisation (both into the display frame in points: a `pixel` frame
   scaled by 72 / dpi; a `pdf_point` frame as is; the page rotation already applied by both readers —
   assert the two frames describe the same rectangle within 1 % or record `frame_mismatch`); greedy
   alignment of word boxes by IoU ≥ 0.5 (highest IoU first, each box used once); matched ratio each way;
   normalised character agreement on matched pairs (case-folded, whitespace-collapsed; a versioned
   normaliser); exact agreement of parsed amounts and dates over matched pairs (the money shape and the
   date shapes from `layout/signals.py`, imported); unmatched-word density inside candidate table regions
   (a region = the union of lines whose words carry ≥ 2 money shapes — a named, versioned heuristic, not a
   layout model); the page-size, rotation and skew census (skew = the median angle of the lines' baselines
   from the native words; rotation from the frames). The module imports the standard library, `evidence`
   and `layout.signals` only (an AST test). E4 (cross-engine disagreement below calibration) is RECORDED as
   review evidence on the row and starts nothing.
2. **Row columns, appended to `ROW_FIELDS`:** `agree_version`, `agree_pages`, `agree_matched_native`,
   `agree_matched_paddle`, `agree_char`, `agree_amounts`, `agree_dates`, `agree_unmatched_table_density`,
   `agree_frame_mismatch`, `geom_rotation`, `geom_skew_deg`, `geom_page_size` — per document the per-page
   figures folded (state the fold per column); projected at the row's single exit in `discovery/runner.py`
   ONLY when the document carries BOTH native evidence and extractor evidence; empty otherwise; the
   row-shape test updated in the same commit.
3. **`tools/agreement_census.py`** — READ-ONLY over a research partition (`--data-dir --research-partition`;
   T's door): the distribution of every statistic on CTRL (the calibration: what agreement looks like on
   known-good documents, by census family and by modality) and on U755; the rotation / skew / page-size
   census over both; counts and percentiles only, never text, never a sha with a verdict. Run it on cell W's
   `paddle-v5-prod` partition when it exists (CTRL first); until then on the fake-worker partition.
4. **The K latents (N-1, N-2), closed in `evidence/native.py`:** N-1 — a page whose CropBox OVERHANGS its
   MediaBox and carries a `/Rotate`: build the display transform from the CLAMPED rectangle PyMuPDF actually
   reports for `page.rect` and the words, so boxes land where the raster puts them (pin with a synthetic
   overhanging-CropBox page at 0/90/180/270 against the rasteriser's pixels, the same method as the
   four-angle pin); N-2 — a `/Rotate` written as an INDIRECT reference: resolve it (`xref` → integer) before
   the mod-90 check, refuse an invalid resolved value by name (pin with a synthetic PDF whose `/Rotate` is
   indirect). Unrotated pages stay byte-identical (the 12-PDF pin); `EXTRACTION_SCHEMA_VERSION` does not
   move unless the evidence bytes of an existing corpus page change — measure the census of both shapes over
   the 3,380 (count only) and say whether any real page moves; if one does, STOP and report before bumping.
5. **Synthetic pairs:** a native page and its 300-dpi raster read by the fake worker's evidence (identical
   words → matched 1.0 / char 1.0 / amounts 1.0); the same shifted by a known offset → the matched ratio
   drops exactly as computed; perturbed amounts (one digit) → exact-agreement drop by the perturbed count;
   a rotated pair at each angle → rotation census correct; a skewed synthetic → skew within 0.5°.
6. **No hardcodes:** the module and the tool in the OQ2 scan roots.

# Files you own (exact; nothing else)
`layout/agreement.py` (new) · `evidence/native.py` (N-1 / N-2 ONLY) · `discovery/runner.py` (the `agree_*` /
`geom_*` projection and the `ROW_FIELDS` append ONLY) · `tools/agreement_census.py` (new) ·
`tests/test_agreement.py` (new) · `tests/test_native_evidence.py` (APPEND the N-1 / N-2 pins) · the row-shape
test · `tests/test_no_statement_hardcodes.py` (the roots append) · your W3 section. `layout/document_class.py`,
`layout/signals.py`, `ocr/**`, `analysis/**`, `telemetry/**`, `webapp/**` are NOT yours (a needed lexicon
addition is reported to Ocean).

# Mutation table (run every mutant, name every killer)
M1 IoU threshold 0.5 → 0.1 without a version bump → the version/threshold pin + the shifted-pair synthetic ·
M2 a box matched twice → the one-use test · M3 the pixel frame not scaled by 72 / dpi → the identical-pair
test at 300 dpi (matched 0 instead of 1.0) · M4 char agreement without the normaliser → the case/whitespace
synthetic · M5 amount agreement over unmatched pairs → the perturbed synthetic · M6 `agree_*` read in
`ocr/escalation.py` or `analysis/` (scratch copy) → the AST guard · M7 the projection on a document with one
evidence source → the empty test · M8 N-1's transform from the unclamped height → the overhanging synthetic
pin · M9 N-2's indirect `/Rotate` treated as absent → the indirect synthetic pin · M10 the census printing a
word → the output-shape test.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; the 12-PDF unrotated pin and the four-angle pin unchanged; the union
`cohort_replay --expect-identical` at base and closure (`evidence/native.py` changed: the whole offline
partition must replay byte-identical, chunked `--parser`); the N-1 / N-2 census over the 3,380 (counts); the
synthetic pair table; the census on the fake-worker partition, then on W's real CTRL and U755 partitions
(read-only); privacy scan 0 over added lines; message scan 0. Heavy proofs one at a time under the lock.

# Report contract (final message to Ocean AND your W3 section `# §P23AGREE — …`)
population (synthetic pairs; the partitions censused; the 3,380 for the N-1 / N-2 census) · root cause ·
solution · newly validated 0 · ladder movement 0 · preserved all, identical (the union replay) · regressions 0
· correctness evidence (the pair table; the pins) · agreement evidence (the CTRL calibration by family and
modality; the U755 distribution; E4 population) · identity evidence (unrotated byte-identical; the two
latents' corpus population) · commits · proof exits · privacy count · risks last.

# Exclusions
No layout model (2.4) · no routing · no third engine · no verdict from agreement · no Paddle call (cell W) ·
no `EXTRACTION_SCHEMA_VERSION` bump without Ocean's ruling · no cost.
