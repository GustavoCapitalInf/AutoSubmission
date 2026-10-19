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

---

# Phase 2 remainder — FULL EXECUTION AUTHORIZATION and rulings R1–R14 (Gustavo, 2026-09-03) — BINDING

```
STATUS: RULED — recorded by Ocean (Fable 5.1) on receipt, verbatim in meaning, before train12 opened
AUTHORITY: Gustavo, 2026-09-03, on approving the planning package
           docs/moneythumb-replacement/phase2_remainder/PHASE2_REMAINDER_PLAN.md ("approve its overall direction")
FROZEN REGRESSION FLOOR: 2,625 / 3,380 (phase2.1-final = d5d82e8; code tree 4f7d798)
```

## The authorization

* **The COMPLETE remainder of Phase 2 is authorized**: 2.2 Truth Instruments → 2.3 Broad Paddle Evidence
  Wave → 2.4 Generalized Reconstruction v1 → 2.5 Reconstruction v2 + Paddle production admission → 2.6
  Unlimited OCR go/no-go (+ implementation if justified) → 2.7 final Phase 2 closure. Ocean proceeds
  **autonomously** from one GREEN milestone to the next; no routine per-milestone approval is required.
  Every milestone keeps the established discipline (bounded card → implementation → focused tests →
  mutation/tripwire tests → corpus measurement → technically relevant performance measurement →
  independent adversarial review → reproduce findings → closure → independent re-review → composition →
  composed-tree proof → CI → durable documentation). **A RED gate is fixed, never passed.**
* **Orchestration**: `ORCHESTRATION-MODEL-POLICY.md` stands (Ocean = Fable 5.1 lead; roles and
  independence preserved; no historical model routing restored).
* **Preserve Phase 1 and Phase 2.1** in full (the 2,625 floor; native/deterministic first; the existing
  parsers; immutable evidence; canonical words/boxes; `DocumentGeometry`; the PaddleOCR 3.7 / PP-OCRv5
  baseline; the Vast worker architecture; provenance; run-of-record rules; the postprocess quarantine; the
  no-hardcode protections; the validator as the only truth authority). No rewrite of Phase 1; no regression
  to OCR → flattened text → bank-specific parsers. **Gain never cancels regression.**
* **Product goal**: substantial bank/layout agnosticism — for any sufficiently legible, sufficiently
  complete statement from an unseen layout: acquire evidence → understand layout → reconstruct
  transactions → account/period/currency context → ledger → metrics → the SAME validator → VALIDATED,
  without a new parser. REVIEW / REFUSED_NOT_STATEMENT / REFUSED_INCOMPLETE / REFUSED_UNREADABLE /
  REFUSED_CONTRADICTORY / REFUSED_INSUFFICIENT_EVIDENCE (or repository-native equivalents) are correct
  terminal outcomes. Never force a file to validate.
* **R = 13 is NOT Paddle's ceiling**; the research scope is the 755 unresolved (3,380 − 2,625). The
  finding that 583 / 755 are native-text PDFs makes generalized reconstruction a first-class objective;
  more OCR does not solve a structural problem. Research admission and production admission are
  different concepts; research is broad, production is evidence-derived, validation is unchanged.
* **The Ocrolus (primary) and MoneyThumb (secondary) research** stays an architectural input with its
  epistemic labels; fresh competitive research is authorized where it would materially improve a design.
* **Priorities**: 1 correctness · 2 generalized coverage · 3 reliability · 4 maintainability ·
  5 performance. **Billing / cost accounting is OUT OF SCOPE for Ocean** (Gustavo tracks Vast charges,
  rates, credits, spend); no time on rates, cost telemetry, billing fields, or cost gates; the earlier
  Vast hourly-rate ruling request is **WITHDRAWN**. Technical performance (latency, throughput, cold/warm
  inference, RAM, VRAM, GPU utilisation, request and transfer sizes, model load, timeout/failure) is
  measured where technically relevant, never for its own sake.
* **Phase 2.2 must account for all 755 exactly**: a disjoint primary classification summing to 755
  (conceptually COMPLETE/SUFFICIENT · PARTIAL/INCOMPLETE · NON_STATEMENT_BANK_DOCUMENT · NON_BANK ·
  UNREADABLE/CORRUPT · UNCERTAIN; better repository-supported terminology allowed); overlapping diagnostic
  labels (R, U, density, extraction/structural/financial failure) reported separately and never summed
  as if disjoint.
* **Phase 2.3** measures stages independently (attempted → Paddle execution → evidence → word/numeric
  fidelity → boxes/geometry usable → DocumentGeometry → reconstruction claim → validation →
  validated/review/refusal); never one "Paddle success" number; on the approved Vast.ai environment.
* **Phase 2.4** has a REAL generality gate: if reconstruction appears to memorise/tune to the development
  corpus, STOP the milestone internally, investigate, fix, re-review; never continue past a RED generality
  gate. DocumentGeometry stays evidence-level; a neutral LayoutModel carries structural interpretation;
  financial reconstruction produces evidence-grounded candidates; the validator stays separate.
* **Phase 2.5** derives the Paddle production-routing policy from measured evidence-quality /
  document-state conditions; "Phase 1 failed → always call Paddle" is not a policy.
* **Phase 2.6** — Unlimited OCR (the Baidu vision-language model) runs on a **DIFFERENT COMPUTER**: not
  the development machine, not the Vast Paddle instance; never moved onto Vast for convenience. It is an
  independently configured remote/self-hosted extractor endpoint whose provider / execution_class reflect
  its ACTUAL deployment (never labelled Vast unless it runs there). Extractor only; the path is
  Unlimited → immutable evidence → canonical evidence → geometry/region sidecar as supported →
  generalized reconstruction → the SAME validator; no Unlimited truth path. A Paddle *financial* failure
  never triggers Unlimited; Unlimited targets genuine EXTRACTION shortcomings (A), never structural (B) or
  financial (C) failures. NO-GO is a valid successful result. If the Unlimited computer is unreachable:
  implement and prove everything provable without it (interface, config contract, client, adapters,
  provenance, partitioning, routing, fail-closed behaviour, mocked contract tests, security boundaries,
  anti-optimizer tripwires), surface the external dependency, never fake a live proof, never claim
  production readiness; continue to 2.7 only if the milestone's gate permits closure without live
  admission, else wait on the dependency.
* **Phase 2.7** freezes the architecture and the evidence-derived router; reports the exact raw and
  complete-statement censuses, per-source contributions (Phase 1 / Paddle / generalized reconstruction /
  Unlimited if admitted), both coverages, every classification bucket, review/refusal population, false
  accepts, validated regressions, development-corpus and sealed-holdout performance, final Paddle (and
  Unlimited) triggers, the residual and WHY per category, runtime characteristics, and the Phase 3
  handoff; then freeze, tag, push, green CI, durable docs, clean worktree, STOP. **Phase 3 / Qwen is not
  begun** without explicit authorization; Phase 2 interfaces stay suitable for a future evidence-grounded
  VLM producer that returns candidates to the SAME validator.

## Customer-data authorization — Paddle (supersedes the Phase 2.1 privacy boundary for THIS path)

APPROVED. Real customer bank statements may be processed by the approved environment **provider =
Vast.ai · execution_class = remote_paid · extractor = PaddleOCR** for the remainder of Phase 2, for:
CTRL (validated customer statements used for calibration/control) · U755 (the unresolved corpus) · SLICE
(configuration A/B) · the broad research wave · unresolved customer statements · a bounded validated
control sample · later Paddle proof/measurement Phase 2 needs. Retention: the remote worker keeps
nothing unnecessary; temporary remote request artefacts are removed after processing; local research
partitions and rasters are permitted under the existing gitignored on-machine archive/research rules;
customer statements, rasters and sensitive extracted contents are never committed.
`PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` may be set explicitly in the environment of authorized
research/evaluation runs; never in a tracked file; never silently the default for ordinary auto mode.
Preserved: protected transport; loopback-bound worker; bounded payloads; no arbitrary filesystem access;
no public processing endpoint; no customer contents in ordinary logs; no customer documents or secrets
in Git; complete provenance; remote stays remote through localhost/SSH. Stopping the instance between
waves is operationally preferred, not a release gate.

## Customer-data authorization — the Unlimited computer

If the separate Unlimited computer is infrastructure we control and processing stays entirely on it,
real customer statements are authorized for the 2.6 evaluation there, labelled with its ACTUAL
provider/class. Any forwarding of customer contents to Baidu-hosted inference, another vendor API or any
third-party cloud endpoint is NOT authorized: STOP before transmitting and surface the exact data-flow
change for a ruling. Downloading weights is not transmitting customer data.

## Rulings R1–R14 (numbering per PHASE2_REMAINDER_PLAN.md §N)

| # | ruling |
|---|---|
| R1 | the operational scope of the Paddle customer-data authorization — as recorded above (populations, retention, opt-in rules, protections) |
| R2 | **WITHDRAWN** — no Vast rate; cost accounting is Gustavo's, never Ocean's |
| R3 | **Sealed truth / adjudication**: Gustavo is the final adjudication authority; Ocean prepares evidence packets, proposes labels, identifies conflicts and uncertain documents, prepares queues; an analyst may later be delegated with the same tooling. The sealed store lives on this machine outside the repository, inaccessible to implementation/tuning paths, keyed by content SHA, minimum truth metadata only, no unnecessary PDF duplication, never committed as readable truth, versioned/auditable, exposing only a non-sensitive manifest/hash/version to the repository. NEVER automatically labels: MoneyThumb outputs, folder names, historical census classifications, parser outputs, Paddle outputs, Unlimited outputs, prior model classifications — evidence for an adjudicator, never truth. Gustavo adjudicating the first slice through the CLI is approved in direction; slice mechanics are implementation decisions |
| R4 | **Unseen holdout APPROVED**: the 3,380 stay development/regression/historical; the primary holdout is genuinely new, production-representative statements unavailable to the implementation/tuning path (statements received after the reconstruction design freezes are preferred); staged growth ~30 → ~100 → 300+ as guidance; diversity across institutions, layouts, periods, page counts, account types, native vs scanned, formatting; implementation never inspects sealed truth before its evaluation event; an opened holdout that affects implementation is no longer unseen; DEVELOPMENT and SEALED-HOLDOUT performance reported separately |
| R5 | **PP-OCRv6 A/B YES**: separately pinned partitions; SLICE + ~200 pages as the starting sample (Ocean may improve); compare numeric and character fidelity, missing/extra tokens, geometry, completeness, scanned pages, downstream reconstruction, false evidence, stability, latency, VRAM; no production pin change without evidence and the reviewed milestone gate |
| R6 | **Orientation classifiers YES** as a SECOND separately pinned configuration for scanned/mixed/orientation-sensitive pages; baseline untouched; measured; identity explicit in provenance and partitions; Ocean chooses the components |
| R7 | **Unlimited**: runs on its own separate computer (see above); implementation authorized on go/no-go evidence without further approval; NO-GO valid; live admission only against the actual machine |
| R8 | **Production Paddle deployment class DEFERRED to 2.5 measurements** (reliability, latency, operational complexity, privacy/security, GPU, throughput, maintainability, runtime compatibility); never blocks research |
| R9 | **REMOVE OR HARD-FENCE** the hosted-extraction selection by reconciliation (`analysis/pipeline.py`, auto mode) during Phase 2: tripwire it unreachable immediately where practical; reproduce/characterise; remove or fully fence in Phase 2 hygiene work; preserve regression proof; surface any previously validated result that depended on it |
| R10 | **Schedule a Phase 1 hygiene ceremony** for the six bank-keyed `bank_repairs.py` rewrites at the safest Phase 2 milestone: inventory, independent reproduction, comparison with the repair doctrine, classification (safe evidence-preserving normalisation / unsafe rewrite / legacy needing replacement), tests/tripwires; delete nothing merely for being bank-specific, keep nothing merely for being old; no new bank-keyed repair logic as coverage strategy |
| R11 | **`refused` APPROVED** as a first-class terminal outcome (Ocean may improve vocabulary/ordering); ANY movement out of `validated` stays a regression unless independently proven a correction of an incorrect validation; comparison/reporting may widen to validated/review/withheld/refused/failed/classification outcomes but must preserve exact transition visibility; **two denominators**: RAW (validated / original corpus) and CONFIRMED-COMPLETE-LEGIBLE (validated / adjudicated complete, sufficiently legible target statements); both always reported, the raw never replaced |
| R12 | **CCL APPROVED**: adjudicated `STATEMENT_COMPLETE` AND sufficiently legible for a competent system to recover the evidence present; the primary CCL is the bank-account statement types the engine targets (deposit/checking/savings/business where in scope); credit-card and loan statements and other classes measured and reported separately until explicitly admitted; adjudication never excludes a difficult but valid target statement |
| R13 | **Declined branch YES**: the LayoutModel/structurer may run where a registration identified/claimed an issuer or family, the parser DECLINED, and no financial candidate was produced; detected issuer identity preserved as `bank` where evidence supports it; REQUIRED TRIPWIRE: withheld / review / validated documents are never routed into the generic path to search for another interpretation — validator failure never becomes a reconstruction retry; measured independently |
| R14 | **Chain-derived-direction integrity flag YES**, FLAG / MEASURE ONLY at first (never withhold/refuse on it alone until control measurements establish its meaning and false-positive behaviour); meaning: every debit/credit direction on the candidate was inferred through chain/balance relationships with no sufficiently independent direction evidence on the document; measured on CTRL and the unresolved populations (frequency, layout distribution, correlation with known-correct and with ambiguous/error cases, interaction with reconstruction, whether independent evidence was genuinely absent); Ocean then recommends diagnostic / review trigger / stricter gate; the flag never invents direction evidence |

## Anti-optimizer rule (restated, binding)

FORBIDDEN: several interpretations → test reconciliation → keep whichever balances · changing OCR
digits until totals reconcile · validator failure → keep invoking extractors/models until something
passes · using reconciliation as evidence that selects an otherwise unsupported candidate. The
validator is a VERIFIER — not an OCR corrector, candidate generator, search objective, model router or
optimizer. Candidates have independent evidentiary support BEFORE validation; several independently
plausible interpretations → REVIEW / REFUSE. The planned tripwires are kept and strengthened.

## STOP conditions (the only reasons to stop and ask)

Continuing would weaken the validator · a false accept cannot be confidently closed · a previously
validated result regresses without an independently proven correctness correction · customer data
would reach a NEW external provider · continuing requires abandoning Phase 1 or 2.1 architecture · a
fundamental security/privacy/legal issue exceeds the authorization · the sealed holdout reveals a
fundamental generalization failure requiring strategic redesign · a milestone premise is disproven and
a materially different program is required · continuing requires Phase 3 / Qwen · the final Unlimited
live proof needs the separate Unlimited computer and it is unavailable. Otherwise: continue.

## Immediate actions ordered (2026-09-03)

Privacy-scan the untracked planning package → commit it durably if clean → record this authorization
(this section) → open `train12` from `main` at `phase2.1-final` → the Phase 2.2 umbrella card in the
house format → begin Phase 2.2 → continue through 2.3–2.7 on GREEN gates without waiting for approval.

## R10 item S-5 — Truist legacy caller fence APPROVED (Gustavo, 2026-09-15)

Gustavo approved the concrete proposal with: **"Approve the fence and zero-change verification."**
This adds `repair_truist_converted_checks` to the four previously ruled caller fences.

Independent synthetic reproduction showed that the repair's duplicate-witness set includes the
same tilde-marked row it removes: a sole converted-check row can become an empty ledger. The paired
duplicate control remains evidence-preserving; that control does not justify the orphan deletion.
Classify the retained function as `legacy_needing_replacement`, not as an optimizer or a safe
normalization. Its original executable body stays as the historical record.

**Authorized change:** remove its analysis import and caller, extend the no-reference tripwire to
this fifth definition (including aliases/callbacks), pin its exact legacy classification, and retain
the paired, transfer-direction, orphan and unrelated-bank characterizations. Add the corresponding
caller-restoration and misclassification mutants. No replacement bank-keyed correction is authorized
by this ruling.

Existing completed evidence: disabling the repair on all 48 identified candidates preserved all 48
validated payloads identically; the independent 900-document instrument reached the Truist stage on
every document and observed no payload change. A deliberate perturbation control moved all 48
candidates, proving the instrument was sensitive. These are dormant-corpus observations, not a
claim that the retained function is safe on unseen inputs.

**Gate:** prove the final five-fence combination on the whole union before composition. Any payload
or outcome movement is a STOP. Preserve the earlier three completed four-fence chunks with their
original scope; they are not the five-fence proof. The root orchestrator independently reviews S-5
because the earlier P reviewer prepared its proposed patch; that reviewer's prior findings and
closures retain their stated independent scope.

Private proposal and exact patch: `discovery_reports/train13-logs/rev23-precision-closure/`
`TRUIST-FENCE-PROPOSAL.md` and `TRUIST-FENCE-PROPOSAL.patch`. The patch passed both index and worktree
apply checks before this approval. Existing dormancy, positive-control and counterexample logs are
linked in the proposal and remain preserved.


## R15 — step-05 double-read compilation rule APPROVED (Gustavo, 2026-09-17)

Context: the continuation segment of the v6 primary stage (48 V6-U755 documents; 10 dispatched-unqualified by the interrupted original run, 38 read in the continuation on the replacement endpoint) produced six documents read twice by the same pinned paddle-v6 pipeline (paired stage on the retired host, continuation on the replacement host; byte-identical page rasters, different cache partition key). Design, independent design review and independent source review are in `discovery_reports/train13-logs/p23config-prep/` (STEP05-DOUBLE-READ-DISPOSITION-DESIGN-ROOT.md and reviews; package `v6-step05-v2-source-01`).

Gustavo ruled: **"report the primary stage as 38/48 using the segment readings with the six flagged as double reads. Continue with phase 2.3."** The joined disposition v2 is frozen with `compilation_rule = "primary=segment; paired=step-02; double_read surfaced"`; the reader reports the primary metric over the 38 AND over the 32 non-double-read documents, surfaces the six with both bindings, and produces the content-level comparison of the six pairs as a required diagnostic before any cross-host comparability statement. The refused first inspection stays the permanent closure of its window; nothing is re-dispatched. Every consumer resolves readings by artifact binding (two paddle-v6 reads now exist for the six in store v6-2).


## R16 — Phase 3 ceiling experiment APPROVED with a USD 250 budget (Gustavo, 2026-09-17)

Gustavo, verbatim, after reading `docs/moneythumb-replacement/phase3/PHASE3-VLM-PROGRAM-PLAN-v1.md`:
"you are in control. I approve the $250 cost. Please proceed with implementation. Let me know what you
start with." His earlier message the same day (also verbatim, still in force): "Until I explicitly
approve otherwise, customer documents and derived training records must remain inside infrastructure
we control and must not be sent to third-party model APIs." and "Do not train anything or begin a
large-scale language migration until the ceiling experiment has been completed, reviewed, and
separately approved."

Root's reading of the scope (recorded so it can be vetoed before any customer page moves):
* Authorized: the two-week ceiling experiment of plan §11 — off-the-shelf models only, no fine-tuning,
  no training spend — on the SAME rented environment already authorized above for Paddle (provider
  Vast.ai, execution class `remote_paid`, the RTX 5090 host named in the private connection file),
  under the SAME protections (protected SSH transport, loopback-bound servers, bounded payloads, no
  public endpoint, no customer contents in ordinary logs, nothing customer-derived in Git, complete
  provenance, remote request artefacts removed after processing). Model weights are downloaded from
  Hugging Face to the host; downloading weights is not transmitting customer data.
* Populations: CTRL (validated control) and U755 (the unresolved corpus), exactly the populations the
  Paddle authorization names; plus synthetic pages and non-sensitive fixtures. The sealed holdout is
  never read. The 200-document calibration set of plan §11 is REPLACED by CTRL so no new population
  leaves the machine. The customer-data opt-in stays explicit per run, never in a tracked file.
* Extractors on that host now include PaddleOCR-VL-1.6 and a Qwen3.5 checkpoint served by vLLM
  (self-hosted on the rented GPU, not a third-party API). The Paddle authorization above named
  "extractor = PaddleOCR"; this ruling extends the extractor set for the ceiling experiment only.
* Budget: USD 250 of instance time for the experiment; hours recorded in every receipt; the hourly
  rate is still "rate not measured" until Gustavo supplies it.
* Not authorized by this ruling: training of any kind, data export to any other machine or vendor,
  any production change, any native-language rewrite, and any run on the holdout.
* Order of execution: synthetic-only live proof first, then independent review of the code that
  touches the boundary, then CTRL, then U755. Customer pages move only after the first two steps.


## R17 — LoRA fine-tuning APPROVED; the 27B second opinion and the 96 GB card (Gustavo, 2026-09-18)

Verbatim, in order, on 2026-09-18: "stop the current qwen 4b on the gpu and paddle and open space to
this model right here. I want you to start testing it right now, i am going to sleep now. Run
autonomously you have my permissions" (the model: Qwen3.8-27B); "i could go up to $1.8 an hour on
vast instead of our current $0.83cent/hr spend"; "alright we are going to set up the 6000 blackwell";
"Proceed with the next steps, also fine-tuning with LoRA is approved."

What this ruling authorizes:

* The Stage B model of the ceiling experiment is now `nvidia/Qwen3.8-27B-NVFP4` (Apache-2.0; NVIDIA's
  NVFP4/FP8 build of `Qwen/Qwen3.8-27B`), served on a rented RTX PRO 6000 Blackwell (96 GB) at up to
  USD 1.80 per hour, under the same boundary and protections as R16 (provider Vast.ai, execution class
  `remote_paid`, host named only in the private connection file, loopback servers, SSH transport, no
  customer contents in logs or Git). The 4B and the layout parser were stopped on Gustavo's instruction.
* Fine-tuning with LoRA of the Stage B model on customer-derived silver labels (plan v1 §10: pages of
  documents the deterministic reader validated, aligned to the reader's rows), plus synthetic pages,
  inside the same boundary: the training records, the page images and the resulting adapters are
  customer-derived and stay on the local machine and the rented instance only; adapters are never
  uploaded to any hub or vendor. Lineage per plan §9 in every training receipt.
* Partitions per plan §10: CTRL (114) and DEV (20) are never trained on (CTRL stays the test sample);
  a family-stratified VALIDATION slice of validated documents is held out and never trained on; the
  sealed holdout's content hashes are blacklisted from every training manifest (the store holds 0
  records today, so the blacklist is empty by construction, stated as such).
* Acceptance to go further (plan §12): improvement over the ceiling arm on VALIDATION with zero false
  accepts, no regression on CTRL, the same deterministic gate, and an independent review of the
  training manifest before any deployment stage.

Not authorized by this ruling: any data leaving the local machine and the rented instance, any
third-party model API, any production change, any run on the holdout. Budget: no new figure was
given; plan §18's M4 line (USD 200–600 of instance time) is the reference until Gustavo sets one.
Requirement noted: LoRA on the 27B needs the BF16 base (about 56 GB) on disk, so the training instance
needs roughly 200 GB of disk; the current 32 GB disk cannot hold it.


## R18 — NSF for underwriting = days ending negative (Gustavo, 2026-09-18)

Verbatim: "quick change to nsf logic. any day ending in the red (negative) is an NSF for underwriting
purposes. Still count the return items but add the ending negative days to them." then, minutes later:
"Actually dont count the returned items please. NSF is solely negative days".

Ruling as implemented (`analysis/metrics.py`): `effective_nsf_count` is the number of calendar days of the
statement period whose ending balance in the validated daily ledger is below zero (`nsf_source =
"negative_ending_days"`); a multi-day overdraft counts every day. Returned / NSF line items stay in
`nsf_count` as evidence and are not added. Without a validated daily ledger the figure is not computable:
`effective_nsf_count = 0` with `nsf_source = "negative_ending_days_unavailable"` and a note, never a silent
zero. The web app shows the source beside the number. Frozen batch results (batch9-final, phase2.2-final)
are historical and unchanged; every new run reports the R18 figure.

Evidence (2026-09-18, all 2,629 validated accounts of the run of record recomputed): every validated
account has a validated daily ledger, so the figure is computable on all of them; 1,722 accounts have
zero negative-ending days, 907 have at least one, 260 have ten or more. Where the bank prints its own
daily balance table (248 statements) the printed number of negative days equals the computed count in
202; in the remaining 46 the computed count is higher, and a day-by-day comparison on the printed dates
agrees in all 46: the extra days are quiet days (no activity) that the bank's activity-only table omits,
which the ruling counts by definition. 245 accounts carry returned items; 75 of them never end a day
negative and therefore report an NSF count of zero under this ruling (the items stay listed as evidence).


## R18 amended — NSF counts printed days by default; carry-over is a Settings option (Gustavo, 2026-09-22)

Verbatim: "alright before we keep working with this, the current way we get nsf count is negative ending
balance days. however, how we calculate ending balance is that a previous day ending balance carries over
inactive days. For example, 3/10 ending balance = -$10 3/12 ending balance = $20 since there is no activity
day 11 we currently rollover the tenth's ending balance over to day 11. So day 11's ending balance comes out
to be -$10 and the total number of negative days comes out to be 2. However, In this case i would want it
to just show 1 negative day. Do not throw away the current way we calculate this. Instead, keep it as a
secondary option as a toggle in a new settings page in the web app. Defaults to printed day no carry over
balance. And if i toggle on carry over it should turn on the functionality."

Ruling as implemented (f069a24; `analysis/nsf_days.py`, `analysis/metrics.py`, `webapp/settings.py`,
`webapp/app.py`):

* Default (`nsf_source = "negative_printed_days"`): `effective_nsf_count` counts the days whose ending
  balance the statement itself establishes — a posting day, or a day the bank printed in its daily balance
  table — and that end below zero. A day with no activity, which only carries the previous balance forward
  in the ledger, is not counted. Gustavo's example: 03-10 ends -$10, nothing posts on 03-11, 03-12 ends
  $20 → 1 negative day by default, 2 with carry-over. Every new analysis computes the default.
* The R18 calendar-day count (`nsf_source = "negative_ending_days"`, a quiet day carrying the previous
  balance) is kept unchanged as the option "Carry the balance over inactive days when counting NSFs" on the
  web app's Settings page. The choice is stored with the web app's data and applied whenever a result
  leaves the server (the analysis API, the revenue-review response, the JSON/CSV/XLSX downloads and the
  package analysis), so a saved statement changes basis without being reprocessed. A result saved before
  f069a24 carries no printed-day count and is re-counted from its stored daily ledger; with no ledger it
  keeps the count it was written with, under its own label.
* Unchanged from R18: returned / NSF line items stay in `nsf_count` as evidence and are not added; without
  a validated daily ledger the figure is not computable on either basis (`effective_nsf_count = 0`,
  `nsf_source = "negative_ending_days_unavailable"`, with a note); the daily ledger and the ADB are the
  same on both bases.

The R18 evidence above was measured on the carry-over basis and has not been re-measured on the
printed-day default. The 46 statements whose computed count exceeded the bank's printed table differed
only by quiet days, which are the days the default leaves out.
