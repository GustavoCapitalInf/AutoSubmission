# Agent Handoff — P20-SURFACES (Phase 2.0 cell D: the fabricated "OCR confidence" removed, the Q3 omission class gated native-only, the standalone Paddle spec superseded)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (OQ9, OQ11), then `OCR_LEGACY_AUDIT.md` §2.7 / F-8 /
§5.8 and the review's MAJOR-4 / MAJOR-5, then `PHASE2_ARCHITECTURE_PLAN.md` §6 (last paragraph) and
§14, then `BATCH9-RULES.md`'s Q3 ruling, then the umbrella `PHASE2-0-SAFETY.md`. Ocean reviews and
composes; you never merge or push. **Hygiene card: `newly validated = 0`; previously validated
preserved, payload identical** — including all 8 `guardian_cu` documents / 12 accounts of L1-S4 and
the 15 protected carriers (`tests/test_l1s2_protected_carriers.py`).

# Why
`webapp/static/app.js:594-609` renders a hard-coded 98 / 94 / 80 / 72 (and 98 / 86 / 72 for packages)
under the label "OCR confidence" — a re-encoding of the validator's `quality` verdict wearing an
extractor's label. The day a second extractor exists the number tells the operator something false
about which read they are looking at. The corroborated Q3 omission class
(`printed_pair_coincides_and_no_row_printed`) was proven 6/6 on `native-pdf-text` documents only and
exists to bound OCR row-loss — the failure mode it has never met. Gustavo ruled: remove/rename the
label with no substitute score; Q3 stays native-only until remeasured; the 2026-07 Paddle spec is
superseded, its geometry ideas preserved.

# Design (ruled — do not re-decide)
1. **UI (OQ9).** Delete `confidenceFrom` and `packageConfidence`. Replace every "OCR confidence" cell
   and the banner meta with a **validation verdict label** derived from words the payload already
   carries — `quality.level` / `quality.corporate_use` / the document outcome (e.g. "validated",
   "needs review", "summary only", "manual review required", "failed") — rendered as text, NO
   percentage, NO numeric score of any kind, under the label **"Validation"** (banner:
   `Extraction completed — validation: <label>`). The package banner likewise shows the package's
   completeness/verdict words (`completeness: partial`, `cross_account_averages_refused` surfaced as
   text where present), never a number. `index.html:1010` "<span id=confidenceValue>--</span>
   confidence" becomes the validation slot. Grep the templates and JS for every `confidence` and
   leave none that describes OCR. Add `tests/test_webapp_confidence_label.py`: an AST/text guard over
   `webapp/static/*.js` and `webapp/templates/*.html` asserting no `OCR confidence` string, no
   `confidenceFrom`/`packageConfidence`, and no numeric literal in the 60–99 range adjacent to the
   word `confidence` (a mutant re-adding `return 94` under a renamed function is killed); plus a
   rendering test through the existing webapp test harness (see `tests/test_webapp*.py`) that the
   results table shows the verdict words for a validated and a needs-review fixture.
2. **Q3 native-only gate (F-8 / §5.8 step 6).** New `analysis/provenance.py::extractor_model(markdown)
   -> str | None`: reads ONLY the first line if it matches the header comment
   `<!-- source: … | model: <token> | … -->` written by `StatementMarkdown.to_markdown()`; returns
   the token or `None`. It is a provenance reader, not admissible text — assert it never reads past
   the first line and never returns anything for a document whose first line is not the header.
   At the omission publish site (`analysis/pipeline.py` where `SiblingOmission`s from
   `sibling_omission.collecting` are published — find the exact seam; if the cleaner place is
   `analysis/sibling_omission.py::publish_omissions`, use it), an omission whose `reason` is
   `printed_pair_coincides_and_no_row_printed` is ADMITTED only when `extractor_model(markdown)`
   starts with `native-pdf-text`; otherwise (any other token, `""`, or `None`) the omission is
   REFUSED and the document fails closed exactly as L1-C17 does for an unratified reason (the
   section is not published, the outcome is the fail-closed one the design already specifies — cite
   it). Direction: absence of provenance refuses. The other three ratified classes are NOT gated
   (they were not ruled OCR-sensitive). Record the refusal reason token
   `q3_class_requires_native_provenance` in the closed omission-refusal vocabulary if one exists, else
   as the `SiblingOmission` diagnostics note — name what you did.
   Tests (`tests/test_q3_native_only.py`, CASE 10): the L1-S4 `guardian_cu` fixtures with their
   `native-pdf-text` header → admitted (the existing pins stay green byte-identical); the SAME text
   with the header's model rewritten to `local-tesseract-ocr` → refused, document fails closed; with
   the header removed → refused; with model `native-pdf-text+guardian` (a layout suffix) → admitted.
   A mutant that admits on `""` and a mutant that admits `local-tesseract-ocr` are both killed. Note
   the spoof hole and its owner: an env `OCR_MODEL=native-pdf-text` would pass this gate — cell B2
   refuses reserved prefixes at `load_settings`; reference that test by name in your W3 section.
   Prove nothing else moves: `tools/cohort_replay.py --parser <every registration id that publishes
   omissions>` and `--folder guardian_cu` at base (`--expect-identical`) and at closure (exit 0; 0
   newly validated; preserved identical), plus `python -m pytest tests/test_l1s2_*.py tests/test_l1s4*.py
   tests/test_l1s3*.py -q`.
3. **Specs superseded (OQ11).** Prepend to `docs/superpowers/specs/2026-07-21-paddleocr-bank-statement-parser-design.md`
   and `…2026-07-22-nanonets-vlm-bank-statement-parser-design.md` a `STATUS: SUPERSEDED (2026-09-01,
   PHASE2_RULINGS.md OQ11)` block: the standalone parser / own-JSON / own-validator architecture is
   superseded by `PHASE2_ARCHITECTURE_PLAN.md` (extractors only, into the SAME deterministic
   validator); the bbox row/column/geometry reconstruction ideas are PRESERVED for reuse as the
   filling of `document_geometry` (`analysis/structurer/geometry.py`) in Phase 2.1; `parse.py` is no
   longer a front door (cell B2). Do not delete the specs; do not edit their bodies.

# Mutation table (minimum)
| mutant | killer |
|---|---|
| `return 94` under a renamed function | the numeric-literal guard |
| "OCR confidence" string restored in a template | the string guard |
| Q3 admitted on model `""` | CASE 10 |
| Q3 admitted on `local-tesseract-ocr` | CASE 10 |
| `extractor_model` reads line 2 | the first-line-only test |
| `extractor_model` returns a token from a document without the header | the no-header test |
| gate applied to `printed_dormancy_declaration` | the other-classes-ungated test |

# Measurements to report
Every `confidence` occurrence before/after (file:line) · CASE 10 · the guardian_cu / omission-publisher
replay at base and closure (exit 0; 0 newly validated; preserved identical; the 8 L1-S4 documents
named by sha16) · L1-S2/S3/S4 test files green · mutation table · privacy 0 · tests added · targeted
suite · guards.

# Ownership
`webapp/static/app.js`, `webapp/templates/index.html`, `analysis/provenance.py` (new),
`analysis/pipeline.py` or `analysis/sibling_omission.py` (the ONE seam you choose — say which),
`tests/test_q3_native_only.py` (new), `tests/test_webapp_confidence_label.py` (new), existing
`tests/test_webapp*.py` where a rendering pin lives, the two spec files (banner only), W3
`§P20SURFACES`. NOT yours: `ocr/*` (B1, B2), `discovery/*`, `webapp/worker.py` (A),
`webapp/artifact_cache.py`, `telemetry/*` (A, B2, C), any parser module.

# Exclusions
No real extractor confidence plumbing (nothing provides one yet). No new score. No Q3 remeasurement
on OCR input (Phase 2.4 / the archive-present card). No change to the seven conditions or to any
other omission class. No `document_geometry` wiring.

# Git
Base `train10` at your handoff's commit. Branch `wave20-surfaces`, worktree
`.claude/worktrees/mt20-surfaces`.
