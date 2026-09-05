# PHASE2_P22IDENTITY_REVIEW — independent adversarial review of Phase 2.2 cell K (P22-IDENTITY)

```
REVIEWER: an independent Fable 5.1 agent (wrote none of the code); detached worktree
          `.claude/worktrees/rev22-identity` at the cell's FINAL closure tip 301cefd (code tree 01c2d19)
BASE:     train12 at b23cb50; diff under review `git diff b23cb50...301cefd` (9 commits)
VERDICT:  APPROVE WITH FINDINGS (no BLOCK, no MAJOR; four MINOR findings, three known items verified closed)
DATE:     2026-09-05
```

Every finding below was reproduced by my own command; every approved property was attacked with inputs the
cell did not use (synthetic only; dates ≥ 2031; no archive text anywhere in this file). Heavy proofs ran one at a
time under `discovery_reports/train12-logs/HARNESS.lock`; targeted tests and mutants ran freely. Scratch
instruments and logs: the session scratchpad `…/scratchpad/rev22/` (`rev22_rotation_overlay.py`,
`rev22_outside_frame.py`, `rev22_pin109.py`, `rev22_census.py`, `rev22_mutants.py`, `rev22_heavy.sh` +
`heavy_301cefd.log`, `targeted2.log`, `mutants_301cefd.log`, `rotation_overlay2.log`, `overlays2/*.png`).

## 1. Verdict and findings (ranked)

**Verdict: APPROVE WITH FINDINGS (no BLOCK, no MAJOR; four MINOR findings, three known items verified closed)**

| # | severity | finding (one line) |
|---|---|---|
| F-1 | MINOR | The native DISPLAY frame is PyMuPDF's `page.rect` (= CropBox) but the repo's Poppler raster (`ocr/rasterize.py`, pdf2image default) renders the MediaBox: on a page whose CropBox ≠ MediaBox the native word boxes are offset from the raster ink by the CropBox origin and the frame size disagrees with the raster (measured below); the transform itself is correct. Archive population: 7 pages in 7 documents (3 validated) of the 3,380 / 25,528 — all unrotated, CropBox the same size as the MediaBox but shifted in y by twenty-four points (3 pages) or eleven and a half points (4 pages), 3,585 words on them; on a SAME-size shift the Paddle rung's scale check does NOT refuse, so a 2.3 Paddle read of those pages would carry a pixel frame in the MediaBox raster while the native frame is the CropBox — a fixed vertical offset (the shift above) between the two evidences, not a transform error (0 of the 82 rotated pages are affected). The Paddle rung already fails closed on such pages (`paddle_frame_mismatch`), so no Paddle evidence exists for them; the fix belongs to `ocr/rasterize.py` (`use_cropbox=True` + `RASTER_VERSION` bump), outside this card. |
| F-2 | MINOR | An INVALID page-level `/Rotate` (not a multiple of 90, e.g. 45): PyMuPDF reports `page.rotation == 0` and an identity `rotation_matrix` but a swapped `page.rect` and rotated word coordinates; the reader declares a 792×612 frame at rotation 0 whose boxes miss the ink of Poppler's 612×792 raster on every word. Latent — archive population 0 of 25,528 pages carry a page-level `/Rotate` that is not a multiple of 90, and 0 pages report a rotation that disagrees with their rect orientation (my census, both counters); the reader's `_VALID_ROTATIONS` clamp does not help because PyMuPDF has already normalised the value. |
| F-3 | MINOR | `tools/train/provenance.py --research-partition "<malformed id>"`: the probe's `ValueError` is swallowed by `attempt`, the whole `run_of_record` block is dropped, and `telemetry.run_of_record.partitions_for_run` then RECONSTRUCTS the run as a production-shaped record (`origin=reconstructed`, `research_partition=""`); only the cache-existence verification stands between a research cache and a production reading. The id should be validated up front (`_validate_research_partition` at `collect`/`main`) and refused. |
| F-4 | MINOR | `ocr_settings_key(stage_version=4, research_partition="x")` silently drops the partition (the field is added only at `version >= 5`); reachable only through reconstruction of pre-v5 runs, which never carry one — latent, should refuse rather than drop. |
| K-1 | closed | Hermeticity of the provenance tests (Gustavo's ruling): reproduced at b483930 (`KeyError: 'paddle_ocr_key_note'` with the real `.env`; root cause `ocr/config.py::load_dotenv()` re-injecting `PADDLE_*` in the probe subprocess), fixed at 01c2d19 — verified in four environments (§5). |
| K-2 | closed | DEV-3 (`tests/test_parser_registry_fingerprint.py` pinned the retired contract): reproduced at b483930, fixed at 12286e3 — the test now pins the setting and the inert variable; green at 301cefd. |
| K-3 | closed | The `pdf_point` bounds refusal (the cell's own ruling request): Ocean's option (c) applied at 0a590e7; the unrotated byte-identity pin is unconditional again — re-derived over all 109 manifest documents (§4). |

## 2. Rotation transform — overlay measurements against the repo's own Poppler raster

Instrument `rev22_rotation_overlay.py`: synthetic one-page PDFs (letter and A4; words near three corners so a
90/270 or axis mix-up cannot score by accident), five shapes × `/Rotate` 0/90/180/270, rasterised with
`ocr.rasterize.rasterize_pdf` at 72 and 144 dpi, boxes overlaid (PNGs in `overlays2/`). Metrics per case:
`boxes_with_ink` (fraction of word boxes, grown 1 px, containing ink), `ink_covered` (fraction of raster ink
inside the union of boxes +2 px), mean and max (ink-centroid − box-centre) offsets. Controls on the SAME raster:
PyMuPDF's raw untransformed boxes and the three wrong-angle formulas.

| shape | angles | raster = frame | boxes_with_ink | ink_covered | mean offset (px @72) | max | controls (raw / wrong angles) |
|---|---|---|---|---|---|---|---|
| S1 `/Rotate` on an upright page (display sideways) | 0/90/180/270 | yes, all | 1.0 all | 1.0 all | ≤ 0.710 | ≤ 2.380 | raw 0.0–0.290; wrong 0.0–0.140 |
| S2 the cell's shape (landscape underneath, content pre-rotated, display upright) | 0/90/180/270 | yes | 1.0 | 1.0 | ≤ 0.410 | 2.010 | raw 0.0–0.140; wrong ≤ 0.140 |
| S4 A4 (fractional dims) sideways | 0/90/180/270 | yes (±1 px) | 1.0 | 1.0 | ≤ 1.150 | ≤ 3.980 | raw ≤ 0.240; wrong 0.0 |
| S5 odd `/Rotate` values −90 / 450 / 360 written into the page object | → 270 / 90 / 0 | yes | 1.0 | 1.0 | ≤ 0.710 | ≤ 2.010 | as S1 |
| **S3 CropBox (15,25)–(560,700) ≠ MediaBox** | 0/90/180/270 | **NO** (frame 545×675 vs raster 612×792) | **0.0–0.750** | **0.000–0.300** | **3–20 px systematic** | 25–52 | raw equally wrong |

At 144 dpi every S1/S2/S4/S5 case repeats with offsets ≤ 1.5 px (scaled). A page with a non-zero MediaBox origin
(−30, −40) at 0 and 90 lands on the ink (boxes verified individually). **No systematic offset or axis swap in the
rotation transform** — S3 is a frame-convention disagreement (F-1), not a transform defect: PyMuPDF words are
CropBox-relative and `page.rect` is the CropBox; `pdf2image.convert_from_bytes` defaults to the MediaBox. The
independent formula check (`(x,y)→(H−y,x)` etc.) agreed with the reader to 0.0 on every rotated case.

## 3. Out-of-frame notes (closure ruling c) — exactness

`rev22_outside_frame.py`: eight words injected through a patched `get_text("words")` straddling the left, right, top
and bottom edges, a corner, wholly off-page, and two exactly ON the edges (closed interval), on top of two in-frame
words, at `/Rotate` 0 and 90. Result at both angles: exactly six `outside_frame:<id>` notes whose ids equal an
independent computation, `words_outside_frame=6` as the last note, every noted word present with its transformed
box VERBATIM (equal to the independent rotation formula), the on-edge words inside, the retired
`native_word_outside_frame` never emitted, `rotation_applied` iff rotated; a clean page carries NO count note
(absence = 0, `words_outside_frame()` returns 0). The same overshoot REFUSES a `pixel` frame (`MalformedGeometry`)
and constructs in a `pdf_point` frame. `inside_frame` is the ONE predicate: defined once (`evidence/canonical.py`),
called at exactly two sites (the `PageEvidence` pixel check and the reader's note builder); no other bounds
arithmetic in `evidence/`, `analysis/structurer/geometry.py`, `ocr/paddle_adapter.py`, `ocr/paddle_rung.py`. VERDICT OK.

## 4. Byte-identity on unrotated pages — ALL 109 manifest documents

`rev22_pin109.py` (under the lock; read-only over `corpus_gate`'s pinned manifest; the legacy Phase 2.0 copy from
`tests/test_geometry_frames.py` vs `geometry_from_pdf` at 301cefd, page by page, line by line, word by word):

| measure | result |
|---|---|
| manifest documents | 109 (14.6 s under the lock) |
| documents with native words | 103 — **801 pages, 261,526 words, byte-identical on every page** (page/width/height, every line's text and spans, every word's text and box): 0 divergent pages, 0 divergent documents |
| documents where the legacy copy answers `None` (no placeable word — Tesseract-read scans) | 6 — the new reader answers `None` on all 6 too |
| out-of-frame words (kept and noted) | 7 documents / 33 pages / 66 words in the legacy geometry; 66 `outside_frame:` notes; the count note equals the id count on every page; every noted id present with its box verbatim and outside the frame; max overshoot 7.750 pt; 0 pages carry a retired note; 0 rotated pages in the manifest |

This is the claim the umbrella makes ("the 109-document / 830-page pin stands") and the closure's `test_geometry_from_pdf_is_byte_identical_on_the_pinned_corpus` makes for 12 — re-derived for all 109 at 301cefd. The cell's first-section figure "7 documents / 33 of 830 pages" is exactly reproduced.

## 5. Hermeticity of the provenance tests (K-1) — four environments

`tests/test_run_of_record.py -k provenance` (5 tests) run in a subprocess: (A) worktree under the checkout, where
`find_dotenv` finds the real `.env`, with `PADDLE_*` stripped from the environment; (B) same worktree, environment
inherited (this host's shell carries the five real `PADDLE_*` variables); (C) a detached worktree OUTSIDE the checkout
(no `.env` in any ancestor — verified), `PADDLE_*` stripped; (D) that worktree, environment inherited. **5 passed in
all four** (20–23 s each). The real `.env` was never moved. At b483930 the same test failed on this host
(`KeyError: 'paddle_ocr_key_note'`); I proved the mechanism directly: a probe subprocess started with `PADDLE_*`
absent reports `PADDLE_PROVIDER in os.environ` False before and True after `import webapp.artifact_cache`.

## 6. Identity, keys, partitions — attacked

* **Analysis key.** Identical markdown with/without `evidence_sha256` → different `analysis_input_sha`; two shas →
  two entries; the same sha → a hit; `""`, non-hex, 63/65 chars refused (`test_two_analyses_…`, `test_a_malformed_…`,
  reproduced in my targeted run). `reconstruction_mode` partitions the settings key (three modes → three keys) and
  `generic_structurer` is derived from the SAME settings object. My own command: setting `GENERIC_STRUCTURER_ENABLED=1`
  leaves the key byte-identical, `structurer_enabled()` False and `structure_unclaimed()` None on a synthetic
  unclaimed statement; `RECONSTRUCTION_MODE=research` changes the key and runs the rung; `ON` refuses at load.
  Under-partitioning: the sha is over the whole canonical evidence (frames, words, lines, notes, runtime) from which
  `DocumentGeometry` is a pure function, so two geometries with one sha cannot exist; a change to
  `geometry_from_evidence` itself is the stage-version discipline, not key material — accepted. DEV-1 (no
  `"no-geometry"` literal) is justified: both `tools/cohort_replay.py::ColdCache.baseline_payload` and
  `telemetry/stated_counts.py::_ArtifactJoin.payload_for` look historical artifacts up with the unversioned two-field
  composition (read); the text-only hash is pinned byte-identical to the Phase 2.1 formula.
* **OCR key.** `research_partition=""`/`None` → the production key byte-identical (my command); a non-empty id is
  its own partition for every extractor label; the closed charset refuses whitespace, `/`, leading `-`, 65 chars,
  `\n` (fullmatch). Recorded run-of-record keys: offline `B3F8D008…` (mode `scanned`, schema 2 / stage 5), analysis
  `7799FEE4…` (stage 17). At this tree: offline(scanned) `A84D4BD7…`, analysis `E6572BB1…` — both DIFFER, as
  they must (schema 3 / stage 18 are key material); the cell states the rotation of both partitions in its W3
  (it does not print the new key values — acceptable, the cold run records them).
* **Run of record.** My own fake research run (provenance with `research_partition: "rev22-fake"`, keys present in a
  fake cache): `partitions_for_run` raises `ResearchPartitionRefused` naming the partition (a `RunOfRecordError`);
  `python -m tools.cohort_replay … --expect-identical` on it exits **5** with the refusal text. Empty/absent field →
  production selection unchanged. Note F-3 above for the malformed-id path.
* **OCR record.** End to end on a synthetic two-page native PDF through `ocr.pipeline.parse_statement`: the native
  rung attaches `native_evidence` (189 words, 2 pages); `to_markdown()` byte-identical to the same read without
  the field; a real `ArtifactCache` round trip hits and reproduces the sha and the object; the record carries
  `native_evidence` + `native_evidence_sha256` beside the schema-2 keys (42,416 B for 189 words ≈ 224 B/word — the
  cell measured 214.8). Schema-2 restore → `native_evidence=None`, analyses (cell test, reproduced). Tampered sidecar
  sha, tampered blob, sha without blob → miss-with-finding (reproduced).
* **Version pins.** `EXTRACTION_SCHEMA_VERSION 2→3` and `ANALYSIS_STAGE_VERSION 17→18` both land in `0e3218a` with
  their pins (`git show 0e3218a`: the constants and `test_…_pinned_at_3` / `_at_18` in the same commit).
* **Evidence boundary.** `import evidence` with `sys.modules["fitz"]=None` succeeds and the reader answers `None`;
  the injections T1 (module-level `import fitz` in a scratch module), T2 (lazy `import numpy` in a function), T3
  (`import ocr`), T4 (a second lazy `import fitz` in another function of `native.py`), T5 (`from fitz import open`
  in `canonical.py`) each fail the tripwire (§7).
* **Second reader / second grouping rule.** AST/grep over the tree: the only `get_text("words")` readers are
  `evidence/native.py` and the PRE-EXISTING `ocr/column_grid.py` / `ocr/native_text.py` printed-rows reader
  (memo §2; untouched by this diff) plus a tool; `analysis/structurer/geometry.py` defines no reader and imports no
  `fitz` (M13 killed); the 0.6×median grouping exists in `evidence.group_lines` and the pre-existing
  `ocr/native_text.py:385` — nothing new.

## 7. Mutation table re-run (scratch worktree at 301cefd; tree verified clean after every row)

`rev22_mutants.py` — each mutant applied as the closure table words it (exact single-occurrence edits), the named killer tests run without `-x`, `git checkout --` in a `finally`, `git status --porcelain` clean after every row; baseline for every test set green first. **22/22 killed** (`mutants_301cefd.log`):

| mutant | killers observed (first named) | result |
|---|---|---|
| M1 rotation matrix not applied | four-angle pin 90/180/270, Poppler cross-check 90/180/270 (9 failed) | killed |
| M2 module-level `import fitz` in `native.py` · M3 in `canonical.py` | the third-party-site set test + `import evidence` without fitz | killed |
| M4 (redefined) the container rule re-applied to `pdf_point` | kept-and-noted 0/90, retired-notes, the two 12-PDF pins on the pinned document that carries out-of-frame words, the viewport test (7 failed) | killed |
| M5 `EXTRACTION_SCHEMA_VERSION` 3→2 · M9 `ANALYSIS_STAGE_VERSION` 18→17 | the two pins | killed |
| M6 restore without re-verifying the claimed sha | tampered-sidecar test | killed |
| M7 `analysis_input_sha` ignores the evidence sha · M8 `reconstruction_mode` absent from the key | case-12 tests | killed |
| M10 retired variable re-honoured | inert-variable tests, the pipeline refusal test (3 failed) | killed |
| M11 `run_of_record` selects a research partition | the four refusal tests | killed |
| M12 `research_partition` omitted from the OCR key | partition tests, provenance test (3 failed) | killed |
| M13 a local reader in `geometry.py` | the AST re-export test | killed |
| M14 `to_markdown()` extra byte | the committed corpus-artifact pin | killed |
| M15 (closure) per-word notes not recorded · M16 (closure) out-of-frame word silently dropped | kept-and-noted 0/90, the same two pins (3 and 4 failed) | killed |
| M17 (closure) success-path note omitted | the configured-Paddle provenance test | killed |
| T1–T5 (reviewer) module-level `import fitz` / lazy `import numpy` / `import ocr` in scratch modules, a second lazy `fitz` site in `native.py`, `from fitz import open` in `canonical.py` | the boundary tripwire (site-set inequality; T3 also the repository-package test) | killed |

## 8. Proof-floor numbers re-derived vs claimed

| item | cell's claim (W3 / closure) | re-derived by me |
|---|---|---|
| targeted tests at 301cefd | (all green) | 338 passed / 0 failed (`targeted2.log`, real `.env` present) |
| full suite at 01c2d19 | 8,830 passed / 45 skipped / 39 deselected / 0 failed (`SUITE_EXIT=0`) | log `p22identity_closure_floor.log` line 146: `8830 passed, 45 skipped, 39 deselected` at `TREE=01c2d19`; guards 275; conformance 1,282/41; gate 105/3/1 GREEN; corpus 34 — matches |
| union replay at 01c2d19 (4 chunks) | 2,695 replayed; 2,625/2,625 identical; 0 regressions | chunk logs: 700/700/700/595 replayed; preserved 680+681+679+585 = 2,625 identical; regressions 0 — matches |
| privacy scan at 2760d6d | residue 0 (raw 26, all `words_class`) | `p22identity_privacy_scan_final3.log`: hit_count 0, raw 26, excluded words_class 26 — matches; note it ran at `2760d6d` (8 commits), NOT at 301cefd (the appended closure section) |
| message scan at 2760d6d | 0/0/0/0 over 8 commits | `p22identity_message_scan_final3.log`: commits 8, hits 0 — matches |
| my privacy scan at 301cefd | — | `tools/privacy_scan_branch.py --base b23cb50 --ref 301cefd` over the 3,380-sha population (3,351 with cached text): added lines 2,844; raw hits 26, all 26 excluded by `words_class`; **residue 0** (MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0) — this covers the appended closure W3 section the cell's own final scan (at 2760d6d) did not; private report `discovery_reports/train12-logs/rev22-identity-privacy.md` |
| my message scan at 301cefd | — | `tools/huntington_msg_privacy_scan.py --run … --base b23cb50 --ref 301cefd` (population 3,380): commits scanned 9; **MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0** |
| `/Rotate` census (cell) | 82 rotated pages / 13 docs (90→19, 270→63; no 180); 1,514 out-of-frame words on 467 pages in 140 docs | my census (`rev22_census.py`, 77.6 s, read-only, counts only): 3,380 documents, 25,528 pages, 12 unreadable pages, 8,074,636 non-blank words; rotated pages 82 in 13 documents, histogram 0→25,434 / 90→19 / 270→63, no 180 — **identical to the cell's**; rotated words 8,135, 0 outside the display frame after the transform (matches); the 109-manifest out-of-frame population 7 docs / 33 pages reproduced (§4); NEW counters: CropBox≠MediaBox 7 pages / 7 documents (F-1), raw non-90 `/Rotate` 0, rect-orientation disagreements 0 |
| cohort replay chunks (my re-run) | — | `--parser td_canada_native`: population 73, replayed 73, newly validated 0, preserved **73 of 73 identical**, regressions 0 (exit 0); `--parser huntington`: 38/38 replayed, preserved **38 of 38 identical**, regressions 0 (exit 0) — both at 301cefd, reading the run of record's RECORDED partitions (schema-2 offline key, stage-17 analysis key) through `telemetry/run_of_record.py`; identity is proven under the new keys because the replay looks the baseline payload up with the unversioned text-only `analysis_input_sha` (DEV-1) and re-analyses in-process — the new OCR/analysis partitions are never consulted |
| empty-cohort behaviour (CRLF id) | `empty cohort`, exit 4 | reproduced: `--parser $(printf 'huntington
')` → `empty cohort`, exit 4 (the instrument selects nothing and measures nothing — the cell's first-attempt artefact, correctly re-run with an LF-clean list) |

## 9. Ownership, commits, scans

* Files in `b23cb50...301cefd`: 21 — every one on the card's list, plus `tests/test_parser_registry_fingerprint.py`
  whose ownership Ocean widened for DEV-3 (recorded in the closure W3 and in Ocean's direction); `tools/cohort_replay.py`
  and `webapp/worker.py` untouched (correctly). Content scope: `geometry.py` — the reader body removed, the re-export,
  docstrings, a dead `import hashlib`; `core.py` — `structurer_enabled` and a dead `import os`; `config.py` — the setting;
  `document.py` — the field, its rule `native_evidence_describes`, the sha property; `pipeline.py` — the attach.
* All 9 commit messages carry `Co-Authored-By: Claude Fable 5.1 …` and `Claude-Session: …` (checked per commit).
* Privacy / message scans: privacy residue **0** over 2,844 added lines at 301cefd (raw 26, all `words_class`); message scan **0/0/0/0** over 9 commits; both under the lock (`heavy_301cefd.log`, `messages_301cefd.log`).

## 10. Properties attacked and not broken (named)

the rotation transform vs Poppler's display orientation (S1/S2/S4/S5, 72 and 144 dpi, controls discriminate) ·
odd `/Rotate` values (−90, 450, 360) · a shifted MediaBox origin · the out-of-frame notes' exactness at 0/90 ·
the pixel container rule · `inside_frame` as the one predicate · the unrotated byte-identity pin on all 109 ·
`import evidence` without PyMuPDF · the boundary tripwire (T1–T5) · the geometry-aware analysis key and its refusal
of malformed shas · the inert retired variable · the closed `reconstruction_mode` vocabulary · the production OCR
key unchanged by an empty partition · the research-partition refusal by name and through `cohort_replay` (exit 5) ·
the native-evidence cache round trip and the three drift directions · `to_markdown()` byte-identity (M14 and the
committed corpus pin) · the two version pins in one commit · hermetic provenance tests in four environments ·
previously validated preserved payload-identical (the cell's four chunks, re-verified from logs; my two chunks).
