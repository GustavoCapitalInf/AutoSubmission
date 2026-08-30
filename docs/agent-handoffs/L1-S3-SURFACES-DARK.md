# Agent Handoff — L1-S3-SURFACES-DARK (batch 9, L-1 stage 3: every payload reader taught the multi-account shape, DARK; ZERO movement)

Read `docs/agent-handoffs/BATCH9-RULES.md` first (the six L-1 conditions bind; the document outcome
is the weakest account's; NO document-level combined ADB; package membership requires the account's
own `validated`; a per-document field holding one account's value is EMPTY with `account_count`
carrying the fact — L1-C18 binds surfaces). Then the reviewed design
`docs/moneythumb-replacement/L1_INDEPENDENT_ACCOUNT_DESIGN.md` — §5 (surfaces: the reader census of
11 — 9 quiet, 1 loud; the seam census of 9 incl. the CLI and the cache; the two-way `--census` mode
of `tools/l1_design_surface_census.py` that exits non-zero on any drift), §4 (the document outcome
under `classify_outcome`, the discovery ladder and the corpus gate's verdict vocabulary), §6 (S3 row
and the C-conditions whose killer is a surface), and `reviews/BATCH9_L1DESIGN_REVIEW.md` ("the
untaught failure is quiet, not loud"). Requires S1 composed. Ocean reviews and composes; you never
merge or push.

# Scope (exactly the design's S3)
Teach every reader of the payload — the 11: telemetry `build_record` / `diagnostics.diagnose`,
revenue, count_semantics / `stated_counts.evaluate`, corpus_gate + `production_verdict._Verdict`,
discovery (runner, compare, report, rows.csv), webapp (routes, renderers, CSV / XLSX exports),
benchmark (`expectations`, `ourside`), batch, the forensic audits — and every one of the 9
`analyze_markdown → report_to_dict` seams (incl. `analyze.py`, `webapp/worker.py`,
`adb_forensic_audit.py`, `artifact_cache`) the multi-account shape (`document` + `accounts`, no
top-level `statement`): each reader either renders per account with the document outcome as the
weakest account's, or REFUSES loudly (never publishes nothing quietly, never indexes `statement`
into a KeyError). Every branch is UNREACHABLE in production at this tree (no reader publishes
multi-account until S4): prove it dark. The discovery row carries the DOCUMENT outcome and no
account (C18). Package analytics: membership requires each account's own `validated`; the
no-average-over-one-content-digest property is enforced where the package math lives.

# Proof
- The surface census mode: declared == tree both ways, exit 0, at your final tip; a doctored
  reader fails it (the re-review proved the census fails both directions when doctored — keep that
  test).
- Per-reader unit tests on a constructed multi-account payload (never a real document): the
  weakest-account rule, the empty per-document field + `account_count`, the loud refusal on the
  legacy indexing path, the package membership rule, the exports' shape.
- Shape assertion + mutants: a reader that silently drops the accounts; one that averages two
  accounts; one that takes the first account as the document (C18's killer — owed by this card per
  the re-review); one that indexes `statement`.
- Zero movement: `cohort_replay --parser <id> --expect-identical` over EVERY registration (chunked)
  with the fixed replay tool; the archive sweep over all 3,380 at the final tree (0 moved, 0
  now-publishes, 0 raises beyond the attributed compositions); corpus gate GREEN with every pinned
  verdict and every audited field unchanged; guards, conformance, suite; privacy and message scans 0.

# Git ownership
Base `train9` after S1 composes (S2 may run concurrently — disjoint files; say so in W3). Branch
`wave9-l1s3`, worktree `.claude/worktrees/mt9-l1s3`. Own: the 11 readers and the 9 seams named by
the design's census (file by file in W3), their tests, `tools/l1s3_*.py`, W3 `§L1S3`. No reader
under `analysis/` beyond the seams; no version constant.

# Findings from S1 that bind this card
- `Statement`'s class docstring (and its field descriptions) are published by pydantic as the
  extraction call's `response_schema` — a MODEL PROMPT. Never edit them to document the model.
- S1 introduced `analyze_document` / `document_report_to_dict` beside the legacy seam and a
  pinned field-set test on `DocumentReport`. Teaching a seam means moving it to the document
  functions with RULE S intact (byte-identical single-account payloads — re-run S1's
  `tools/l1s1_seam_probe.py` at your tip); a document-level field you need must gain its RULE S
  clause and the field-set test in the same commit.
- `corpus_gate.py`'s caller register already declares `analyze_document` and the design's three
  probes (train9 473be2c); keep the register truthful for every seam you move.

# Report
BATCH9-RULES contract: newly validated 0 · other movement 0 · preserved ALL byte-identical ·
regressions 0 · correctness (the census both ways; the per-reader tests; the mutants) ·
generalization (every surface, every seam).

# Q10 ruling (Gustavo, 2026-08-30) — binds this card
Surface the omission, do not demote. The document outcome is the weakest ACCOUNT's, with only the two `failed`
overrides (no account; an omission whose reason is not a ratified class). An omission on ratified evidence beside an
independently validated account leaves the document `validated`; the omission is surfaced at the document / package
layer (`document.omissions`; package `sibling_account_omission_detected: true`, `completeness: partial`) — DARK here,
unit-tested on constructed payloads. Never wire the design's §1.5 `("review", "sibling_section_omitted")` override.
Pin it: a constructed document with a ratified-class omission and one validated account classifies `validated`; the
15 protected carriers S2 pins at the seam stay green at your tip and at composition.
