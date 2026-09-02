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
* **Models** *(SUPERSEDED 2026-09-02 by `docs/agent-handoffs/ORCHESTRATION-MODEL-POLICY.md` — the
  model names below are the 2026-09-01 record, not an instruction; the roles and independence
  requirements stand):* Ocean = Fable 5.1 (lead). Implementation agents = Claude Sonnet 5 at HIGH effort (the
  Phase 2.0 default). Independent review agents review every implementation branch; an implementation
  agent never approves its own work.
* **Completion gate and STOP:** the gate is enumerated in `docs/agent-handoffs/PHASE2-0-SAFETY.md`
  §Completion. When it is met, Phase 2.0 STOPS and the closure report goes to Gustavo; PaddleOCR
  (Phase 2.1) waits for his explicit approval.

---

# Phase 2.1 rulings and authorization (Gustavo, 2026-09-02) — BINDING

```
STATUS: RULED — recorded by Ocean (Fable 5.1) at the opening of Phase 2.1, before any implementation
AUTHORITY: Gustavo, 2026-09-02, on approving the Phase 2.0 closure report (phase2.0-final = fc09631)
FROZEN REGRESSION FLOOR: 2,625 / 3,380 (unchanged; batch9-final = 819d97d; Phase 2.0 cold run 2,625 -> 2,625)
```

Phase 2.0 is accepted, frozen, pushed, tagged and CI-green. Every Phase 2.0 invariant stays binding
through Phase 2.1: the A/B/C failure separation; the independent `EscalationRouter`; the
`ExtractionQualityGate`; the postprocess quarantine; the provenance-token restrictions; the endpoint
policy; run-of-record artifact selection; the Q3 native-only gate; the no-hardcode protections; the
SAME deterministic validator; the 2,625 floor. **Validator success may STOP escalation; validator
failure may NEVER START escalation.**

## RULING A — automatic hosted extraction: REFUSED

Production auto mode may NOT route a Class B document to a hosted or remote extractor merely because
dispatch was unclaimed, a parser declined, a parser crashed, the layout is unknown, the bank is
unknown, or deterministic validation failed. This closes the ruling owed from Phase 2.0 on the
pre-existing webapp auto-mode edge (`dispatch unclaimed / parser_exception -> extract_statement`):
that edge is a Class B -> hosted-model path and is REFUSED as doctrine. Routing doctrine:

* **Class A** (extraction failure) -> another explicitly allowed extractor may run ONLY because of an
  independent extraction-quality trigger.
* **Class B** (usable evidence, structural/layout failure) -> geometry / generalized reconstruction
  on the SAME evidence. NOT another extractor.
* **Class C** (financial validator failure) -> review / refuse. NO extractor escalation.

No automatic local -> remote hop. No "parser failure -> hosted model" hop.

## RULING B — the density criterion: SURFACE-ONLY

The 23 density-surfaced documents remain SURFACE-ONLY. `density-surfaced != Class A`; a
density-surfaced document MUST NOT schedule PaddleOCR. A future density trigger requires labelled
evidence demonstrating a parameter-independent extraction-quality criterion, followed by independent
review. (Continues the P20-ROUTER MAJOR-2 ruling of 2026-09-01.)

## Current measurements that bind Phase 2.1 (Phase 2.0 run of record `TRAIN10-941918f/…-ef34ee30`)

R = 13 · U = 123 · U-extract = 0 · U-structure = 123 · density-surfaced = 23 (surface-only, not
routed) · **currently admitted extraction-escalation population = 13**. All 123 historical U documents
are Class B under the admitted criteria. **The 123 U documents are NOT sent to Paddle because they are
unclaimed. Paddle is not a retry mechanism for Class B.**

## Phase 2.1 authorization — PADDLEOCR + CANONICAL WORD BOXES + DOCUMENTGEOMETRY, and nothing else

Authorized: Phase 2.1 only. NOT authorized: Phase 2.2, Phase 2.3, Unlimited OCR, a generic parser
expansion wave, processing the 123 U-structure population as a coverage wave, Trigger T live, the
density criterion live, automatic hosted extraction, automatic Vast fallback, other automatic
paid/cloud extractors, PP-Structure as truth, a silent PP-OCRv6 switch, character-level OCR fusion,
confidence arbitration, validator-selected candidate values, candidate auto-adoption, new bank-specific
parsers as the coverage strategy, distributed OCR workers, Kubernetes, unrelated product work.

Objective: PaddleOCR -> immutable OCR evidence -> canonical word geometry -> `DocumentGeometry` ->
reconstruction where appropriate -> the SAME deterministic validator; and native PDF word geometry ->
the SAME `DocumentGeometry`. Paddle is an EXTRACTOR ONLY: it never decides transactions, signs,
debit/credit, balances, ADB, account or statement validity, currency, financial confidence or
`validated`. OCR confidence is annotation / routing / review highlighting only; it may never grant
`validated`, override reconciliation, select a value, or choose whichever interpretation balances.
Raw Paddle evidence is immutable; the postprocess quarantine stays; no candidate auto-adoption; the
validator is not an optimizer. Q3 remains native-only. Model policy: PaddleOCR 3.7.0, PP-OCRv5, word
boxes enabled; any v6 evaluation is a separate measurement/ruling.

## The explicit Vast.ai authorization (Phase 2.1 development endpoint)

* Provider **Vast.ai**; execution class **`remote_paid`**; GPU **NVIDIA GeForce RTX 5090 (32 GB)**;
  PaddleOCR **3.7.0** on the PaddlePaddle GPU runtime; **PP-OCRv5**; `return_word_box=True`
  PROVEN by a real inference (rec_texts / rec_scores / dt_polys / rec_polys / rec_boxes /
  text_word_boxes / text_word; warm inference ~0.8 s). Not to be re-proven.
* **Explicit opt-in only.** REMOTE + PAID + EXPLICITLY OPTED IN. Never automatic fallback: no silent
  local -> Vast hop; no Class B -> Vast/Paddle routing; no Class C -> Vast/Paddle routing. The prior
  "$0 paid inference" requirement does NOT apply to this explicitly approved development endpoint;
  actual paid GPU usage is MEASURED instead.
* **Connection configuration is runtime configuration, never source.** Host, SSH port and SSH user
  come from the process environment (`PADDLE_VAST_HOST`, `PADDLE_VAST_SSH_PORT`,
  `PADDLE_VAST_SSH_USER`, with `PADDLE_PROVIDER=vast.ai` and `PADDLE_EXECUTION_CLASS=remote_paid`);
  they are never committed, never placed in tracked configuration or examples with real values, and
  the runtime FAILS CLOSED when a required variable is absent — no guessed or default remote host.
  SSH authentication uses the developer machine's existing key; no key is copied into the repository.
* **Localhost does not mean local execution.** Through an SSH tunnel the client sees
  `http://127.0.0.1:<port>`; the inference is still provider = Vast.ai, execution_class =
  `remote_paid`. Execution class is never inferred from a URL's hostname; provenance describes where
  inference physically occurred.
* **Data privacy boundary.** No production customer bank statements are transmitted to Vast.ai
  during Phase 2.1 unless Gustavo authorizes it separately. Remote integration and measurement use
  synthetic fixtures, non-sensitive fixtures, public test images, or specifically approved development
  data. SSH tunnelling does not change Vast.ai's classification as a third-party remote environment.
  If real-customer remote processing becomes necessary: STOP and surface the requirement for a
  separate remote-data / privacy / retention ruling. Authorization is never broadened independently.
* Provenance / telemetry for every remote Paddle execution records where appropriate: provider,
  execution class, GPU model, PaddleOCR version, PaddlePaddle version, OCR model / version, settings
  key, extractor identity, remote execution status, runtime, usage, and cost where measurable.

## Completion gate and STOP

The Phase 2.1 completion gate is enumerated in `docs/agent-handoffs/PHASE2-1-PADDLE.md` §Completion.
When it is met, Phase 2.1 STOPS and the closure report goes to Gustavo. Phase 2.2 does not begin.
Unlimited OCR is not enabled.
