# Agent Handoff — PLATFORM-PROPOSALS

Complete self-contained brief. **DESIGN-ONLY CARD: no production code, no
test code, no protected-module edits. Two proposal documents are the entire
deliverable.** Ocean reviews; Gustavo signs off on A before any
implementation exists anywhere.

# Identity
- **Agent:** PLATFORM-PROPOSALS · Wave 3 parallel preparation (Gustavo directive 2026-08-10, items A and B)

# Git ownership
- **Base:** current main · **Branch:** `wave3-platform-proposals` · **Worktree:** `.claude/worktrees/mt-proposals`. Commit only there (docs only); never merge; never push.

# Deliverable A — `docs/moneythumb-replacement/PROPOSAL_STATED_COUNTS.md`
The platform-level stated-count integrity check, for Gustavo's architectural sign-off.
- Read first: `W3_2_TAXONOMY.md` (open question 1 — the original gap statement), `W3_TRACKA_LOG.md` (the witnesses: RBC §5.5 — 6 validated docs with wrong per-direction counts + 2 with wrong totals; §BOFA — stated per-direction counts extracted and never checked; §TRIO — PNC decisive: a swallowed section keeps money on the right side while moving rows, ONLY a count notices), `analysis/reconcile.py` + `analysis/pipeline.py::assess_document_integrity` + `analysis/adb.py` validation surfaces (READ-ONLY — understand where such a check would live and what shapes exist).
- The proposal must specify: the exact check semantics (stated credit/debit counts vs captured per-direction rows; when stated counts are absent → check not applicable, never fabricated); where it lives (reconcile vs integrity assessment — argue placement); its failure surface (new issue string + integrity flag + W3-2 taxonomy code and CLASS placement with precedence argument); fail-closed consequences (does a count mismatch withhold, or flag-to-review? — argue from the witnesses); the exact protected-module diff SHAPE (pinned as a written diff in the doc, NOT applied — W3-1b idiom); blast-radius analysis (which corpus documents and how many archive documents would change outcome — estimate from existing telemetry/diagnostics data, read-only); migration/re-baseline implications (could any of the 106 corpus PASS docs fail the new check? If yes, that is ceremony territory and must be stated); test plan; rollout order.
- Sensitivity: aggregates only.

# Deliverable B — `docs/moneythumb-replacement/DESIGN_GEOMETRY_INTEGRATION.md`
The geometry/structurer integration design for the residual class (text layer does not preserve grid order).
- Read first: `W3_3C_STRUCTURER.md` (esp. §5.1 discovery-hook spec and the geometry input design), `W3_TRACKA_LOG.md` (the residual populations: TD T-F4 10 docs · RBC F11 6 · PNC 3 · Wells W-F7 4 — note W-F7 is an `ocr/native_text.py` fixed-band geometry defect, arguably a different fix class; distinguish), the structurer's `analysis/structurer/geometry.py` (read-only).
- The design must cover: which consumers wire `document_geometry` and how (webapp worker, discovery runner — file-level touchpoints and diff shapes, not code); where PDF word boxes come from on each path (native PDFs vs OCR grids) and their cost; how the 19+4 residual documents route (structurer rung opt-in? a parser-level geometry assist? — argue, remembering Gustavo's constraint: existing reconciliation/grounding requirements must NOT be weakened to recover them); measurement plan (how success is proven against the frozen baseline); sequencing vs the W-F7 ocr-band fix; open questions for the 3b-style review this design will get.

# Validation
Docs build nothing, so: internal consistency, every claim sourced to a log section or file:line, both docs self-contained enough for Gustavo to rule on A and for a future implementing agent to execute B without your context.

# Stop conditions
Any urge to write code or tests; any protected file opened for anything but reading.

# Definition of done
Both documents committed on the branch; a short final report naming their key recommendations and open questions.

# Final report to Ocean
Per deliverable: the core recommendation in ≤5 sentences; the decisions Gustavo/Ocean must make; the risks; commit hash.
