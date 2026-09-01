# PHASE2_RULINGS — Gustavo's rulings on OQ1–OQ11 (2026-09-01) — BINDING

```
STATUS: RULED — these close the eleven open questions of OCR_LEGACY_AUDIT.md §6
AUTHORITY: Gustavo, 2026-09-01, at the opening of Phase 2.0 implementation
RECORDED BY: Ocean (Fable 5.1), verbatim in meaning; the wording below is Gustavo's
FROZEN REGRESSION FLOOR: 2,625 / 3,380 (batch9-final = 819d97d)
```

The accepted architecture (`PHASE2_ARCHITECTURE_PLAN.md`) deliberately left OQ1–OQ11 unresolved. They are
ruled here. Every Phase 2 card inherits these rulings; no card may re-open one. Where a ruling and the
architecture plan's "architecture intent" agree, the ruling is the authority; where they differ, the
ruling wins.

## OQ1 = C — quarantine the entire legacy OCR postprocess chain initially

Quarantine the entire legacy OCR postprocess chain initially. Re-admit functions individually only
after their own census + synthetic fixtures establish exactly what they change and their safety is
independently reviewed. **The default is raw evidence.**

## OQ2 = YES — the no-hardcodes protection extends into `ocr/`

Extend the no-statement-hardcodes / value-meaning-hardcodes protection into `ocr/`. The existing TD
masking behavior may remain **only** as explicitly named intake behavior with structural justification
and dedicated fixtures. No customer-specific, account-specific, SHA-specific, benchmark-specific, or
statement-specific behavior.

## OQ3 = ALLOWLIST — the local / $0 endpoint policy is enforced in code

Enforce the local/$0 OCR endpoint policy in code. Approved local/private endpoints may be used by
default. Remote or paid processing requires explicit, deliberate, recorded opt-in. **A local extractor
failure must never silently trigger a remote or paid service.**

## OQ4 = TRIGGER T LATER — surface-only for now

Trigger T remains surface-only for now. Measure its population first. Potential admission belongs in
Phase 2.4, not Phase 2.0.

## OQ5 = PADDLE PRIMARY NEW VISUAL EXTRACTOR

Tesseract remains the existing first image rung. PaddleOCR will be the primary NEW visual extractor.
Unlimited OCR will be a bounded fallback after Paddle for remaining legitimate Class A extraction
failures. **Do not implement Paddle or Unlimited during Phase 2.0.**

## OQ6 = KEEP RUNPOD AS LABELED ESCAPE HATCH

RunPod may remain documented as an explicit optional/paid escape hatch. It must never become an
automatic production fallback.

## OQ7 = QUARANTINE / RETIRE LEGACY OCR SCRIPTS

Salvage genuinely reusable CHECKS, evidence, or test logic first. Then quarantine or retire
obsolete/uncontrolled legacy OCR entry points. Do not leave multiple uncontrolled ways to bypass the
canonical extraction router.

## OQ8 = YES — adopt `CachedArtifacts`

Adopt the existing `CachedArtifacts` deterministic artifact-selection machinery where appropriate. Do
not invent a second competing mechanism unless evidence proves the existing abstraction cannot safely
satisfy the requirement.

## OQ9 = RENAME / REMOVE FAKE "OCR CONFIDENCE"

The current UI value labeled "OCR confidence" is not OCR confidence. Rename or remove the misleading
presentation before multiple extractors exist. **Do not replace it with another fabricated score.**
Extractor confidence, when a real extractor provides it, may later be used for routing, analyst
highlighting, or diagnostics. It may never grant `validated`.

## OQ10 = RUN-OF-RECORD PARTITION

Replay/observer tooling must follow the artifact partition actually selected by the run of record. Do
not silently prefer: offline first · visual first · `rows[0]` · DB incidental order · hard-coded list
ordering. **Historical truth must follow the artifact actually consumed by the official run.**

## OQ11 = SUPERSEDE OLD STANDALONE PADDLE PARSER SPEC

Mark the old standalone Paddle parser/JSON architecture superseded. Preserve and reuse useful bbox, row,
column, and geometry ideas. PaddleOCR is an extractor that supplies evidence/geometry to the existing
architecture. **Paddle must not become its own independent financial parser or validator.**

---

## Phase 2.0 authorization that accompanies the rulings (Gustavo, 2026-09-01)

* **Scope:** Phase 2.0 — SAFETY FOUNDATIONS only. Not Phase 2.1; nothing PaddleOCR; nothing Unlimited;
  no coverage work. Expected coverage movement **+0**; if Phase 2.0 produces meaningful new validated
  coverage, STOP and determine why.
* **Objective:** make future OCR-fed and geometry-fed validation possible without weakening the frozen
  Batch 9 correctness model, and make "try extractors until something balances" architecturally
  impossible.
* **Core failure model:** A = extraction failure (may return to another extractor ONLY under an
  independent extraction trigger); B = structural/layout failure (must NOT trigger another OCR engine;
  its future fallback is geometry, Phase 2.2); C = financial validation failure (review or refuse;
  **there is NO C → OCR edge**).
* **Governing invariant:** validator success may STOP escalation; validator failure may NEVER START
  escalation. Structural enforcement, not comments.
* **Trigger U is split** into U-extract (Tesseract output does not meet usable-evidence requirements)
  and U-structure (usable evidence, parser/structurer does not understand it = Class B). Re-derived
  against the frozen batch-9 run of record; do NOT assume all 123 are OCR opportunity.
* **Postprocess:** census all NINE members with per-function synthetic fixtures; raw OCR evidence
  immutable; no candidate auto-adoption in Phase 2.0; the validator is not a candidate optimizer.
* **Provenance tokens** use a closed character set (no newline, CR, `-->`, `<`, `>`, money literals,
  parser-marker text); hostile regression tests; provenance preserved, never weakened.
* **Endpoint policy** enforced in code; no paid service enabled in Phase 2.0.
* **Artifacts / replay:** run-of-record selection; `OCR_STAGE_VERSION` 4 → 5 only in the same reviewed
  composition as the cache-behavior change and its pinned test.
* **Q3** remains native-only; the six `guardian_cu` cases are remeasured on OCR-fed evidence later, not
  now.
* **Floor:** 2,625 preserved; a gain never cancels a regression; no weakening of any of the ten
  protections; one account → one ADB; no invented values.
* **Models:** Ocean = Fable 5.1 (lead). Implementation agents = Claude Sonnet 5 at HIGH effort (the
  Phase 2.0 default). Independent review agents review every implementation branch; an implementation
  agent never approves its own work.
* **Completion gate and STOP:** the gate is enumerated in `docs/agent-handoffs/PHASE2-0-SAFETY.md`
  §Completion. When it is met, Phase 2.0 STOPS and the closure report goes to Gustavo; PaddleOCR
  (Phase 2.1) waits for his explicit approval.
