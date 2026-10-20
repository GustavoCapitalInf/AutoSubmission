# Prototype Branch Review — Universal Statement Intelligence

Author: Ocean. Date: 2026-08-06. Status: review complete; incorporation in
progress (consumers listed per item). Final deletion recommendation is issued
when the last consumer (P2-1 investigation) has extracted what it needs.

Two remote branches predating Wave 0 hold unique prototypes of the
unknown-bank ("universal") path. Both fork from `f746b9f`; both are kept as
**read-only reference** by Gustavo's instruction (2026-08-06). Neither may be
merged wholesale; nothing is cherry-picked without review and adaptation.

| Ref | Commit | Date | Shape |
|---|---|---|---|
| `origin/cursor/cloud-agent-1785900428099-wlfy6` | `f14282e` | 2026-08-04 | "Frozen Analysis Contract + Universal Structurer" — 1,855 insertions |
| `origin/feature/universal-statement-intelligence` | `54a9e8d` | 2026-08-05 | "Universal Statement Intelligence" — 3,427 insertions; evolution of the same idea |

## Verdict in one paragraph

Both prototypes converge on the architecture MASTER_PLAN later adopted as AD-7:
*any* structurer (deterministic parser, model, or future layout engine) fills
the same `Statement` schema and faces the same deterministic
reconciliation/fail-closed gate; trust comes from the gate, never from the
extractor. The branches are unmergeable as-is (they edit protected modules —
`serialization.py`, `transaction_classifier.py`, `pipeline.py`, and a 508-line
`worker.py` rewrite that Wave 1's D-1/O-1 has since rebuilt differently — and
they center production routing on a budgeted Gemini fallback that
PROJECT_GOAL excludes from the production path). But four of their components
are genuinely valuable and are hereby catalogued for adapted reuse.

## Material worth preserving (consumer → when)

1. **`analysis/grounding.py` (54a9e8d, 517 lines + 322-line test suite) — the
   gem.** Source-grounding validation: every extracted transaction amount and
   date must appear on its claimed page; distinctive description tokens near
   the amount; span-uniqueness (one source span cannot justify two extracted
   rows); printed summary/average values must appear beside an appropriate
   label; daily-balance rows must match dated table rows; period and identity
   scoping; no provenance → fail. This is an extraction-method-agnostic second
   validation axis that catches self-consistent hallucinations arithmetic
   cannot. **Consumers:** P2-1 generic-understanding investigation (primary);
   R-5 deterministic-parse cross-check (comparison evidence); potentially
   DSC-2 adjudication of disputed extractions. Adapt, don't import: it must be
   rebuilt against the post-R-2 shared money/date utilities and reviewed
   heuristic-by-heuristic.
2. **`eval_unknown_banks.py` (f14282e, 392 lines) + recorded-fixture replay
   design.** Offline, deterministic replay harness over
   `tests/fixtures/unknown_banks/` (document markdown + recorded structurer
   output) measuring exactly the trust layer: reconcile → ADB → classification
   → approval gate, with a `--check` regression mode and CSV emission. The
   synthetic `heritage_valley_trust` fixture comes with it. **Consumers:**
   DSC-2 adjudication workflow and the P2-1 evaluation design — this is the
   template for "measure the gate, not the model."
3. **Bounded-retry-with-feedback loop (`analysis/universal.py`, f14282e).**
   `StatementStructurer` protocol; failed reconciliation produces structured
   feedback for one bounded retry; `_is_better` picks the best attempt by
   reconciliation quality; hard attempt budget with a `=0` kill-switch env
   contract; per-call token/cost telemetry with versioned price estimates.
   **Consumers:** H-3 telemetry field design (cost/attempt records) now; P2-1
   later; the kill-switch pattern is the model for DSC-2's "Gemini disabled"
   discovery mode.
4. **Contract documentation.** (a) f14282e's frozen-contract table maps ten
   financial contracts §1–§10 to their implementing modules — a sharper
   articulation of MASTER_PLAN §4's protected list, worth folding into the
   protected-modules documentation. (b) 54a9e8d's fail-closed API contract for
   withheld generic values (`authoritative=false`, machine-readable
   `unavailable_reason`, nulls never 0, empty evidence lists, package nulls)
   matches current serialization philosophy and is the wording DSC/D-6 should
   inherit. (c) `docs/production-dependency-licenses.md` (54a9e8d) — license
   inventory, useful for the eventual production-posture wave (D-7).

## Material examined and rejected

- **First-match ordered registry (`analysis/parser_registry.py`, 54a9e8d).**
  It validates R-3's premise (parser order is a real contract: "specific
  before broad", with an explicit inventory of all 43 parse functions and
  clean key names R-3 may reuse as its naming baseline) — but it has no
  detection scoring, no ambiguity outcome, and silent first-wins routing,
  which is precisely what R-3 exists to replace. Superseded by the R-3 RFC.
- **Protected-module edits** (serialization/classifier/pipeline rewrites in
  both branches): rejected on the preservation mandate; the same outcomes are
  achieved additively in the current architecture (Wave 1 did so for
  worker/storage).
- **Prototype `webapp/storage.py` + `webapp/config.py`** (f14282e):
  superseded by D-1's durable store and D-2a's configuration; no unique
  behavior worth porting.
- **Gemini-centric production routing:** contradicts the zero-vendor-cost
  production goal; retained only as the flagged, telemetered fallback story
  already in MASTER_PLAN (AD-7).

## Incorporation status & deletion recommendation

- Registry naming/ordering inventory → handed to the R-3 RFC review (now).
- Telemetry cost-record fields → handed to the H-3 schema review (this wave).
- Grounding + eval harness + fixtures → P2-1 investigation inputs (Wave 3+;
  R-7 task card updated implicitly by this document).
- Contract docs → to be folded into protected-module docs at the next docs
  pass.

**Provisional recommendation:** keep both branches until the P2-1
investigation has consumed items 1–2. When that lands, tag both commits
(e.g. `archive/universal-prototype-2026-08-04`, `…-08-05`) so the objects stay
reachable, then delete the branch refs. Final recommendation will be issued
with the P2-1 investigation report.
