# Agent Handoff — L1-ARCH-DESIGN (batch 9, architecture DESIGN cell for the independent-account model; no production change)

Read `docs/agent-handoffs/BATCH9-RULES.md` first (its "Checkpoint rulings" section binds this
card). Ocean reviews and composes; you never merge or push. This card produces a reviewed
DESIGN; implementation cells follow it.

# Ruling (Gustavo, 2026-08-29)
Proceed with the independent-account architecture — the packet's Option C, chosen because it
IS the separate-account / independent-validation architecture: each account on a statement is
reconstructed as its own Statement and validated independently by the UNCHANGED validator
(`reconcile` + the ADB checks). Conditions: (1) an idle sibling is admitted only when explicit
statement structure establishes the sibling AND its empty / silent state — absence of parsed
activity alone is insufficient; (2) each account reconstructs and validates independently;
(3) NO document-level combined ADB — the ADB is per account; the roll-up / cross-account
total are consistency ORACLES only; (4) inter-account transfers remain in each account's
ledger and are identified as INTERNAL for package-level analytics so nothing is
double-counted; (5) no arbitrary or memorised account selection; (6) explicit currency
evidence outranks defaults (CURRENCY_DOCTRINE: one denomination per account; a document
printing two currencies publishes two accounts or refuses — never aggregates).

# Inputs
`docs/moneythumb-replacement/L1_CU_SUFFIX_RULING_PACKET.md` (the measured structural census:
62 structural families, 4 boundary mechanisms, 9 caption classes, 5 identity forms, 4
equation forms, 13 grid tokens; 29 sections genuinely closing; 2 documents fully closing
today, 8 if empty-and-silent siblings are omitted; 7 documents / 47 transfer pairs; 19
roll-ups listing a facility; 12 pinned multi-posting documents) and its review;
`tools/l1_*.py`; `analysis/schema.py` (the single-account `Statement`); `analysis/pipeline.py`
(`analyze_markdown`, `reconcile`, the integrity assessment); `analysis/adb.py` (the ratified
calendar-day doctrine); `analysis/symitar.py` (the ratified idle-sibling predicates);
`analysis/consumers.py` (CONS-L1: the pinned document with three posting accounts and a
memorised selector at `:90`); the package / webapp / corpus-gate surfaces that read a
Statement (`webapp/`, `benchmark/`, `corpus_gate.py`, `telemetry/record.py`,
`analysis/serialization.py`); the readers carrying an L-1 refusal today (huntington `:662`,
community_section `:896`, navy_federal `:127`, capital_one, consumers, symitar).

# Deliverable — `docs/moneythumb-replacement/L1_INDEPENDENT_ACCOUNT_DESIGN.md`
1. **Data model.** How a multi-account document is represented without breaking every
   single-account consumer: e.g. an `AccountStatement` (today's `Statement`) per account and
   a `DocumentStatement` carrying `accounts: list[...]`, the printed roll-up as an oracle
   record, the document-level period, and provenance — with the exact rule for what a
   single-account document publishes (unchanged payload, byte-identical for the 2,596 —
   state how that is guaranteed and proved). Where `classify_outcome`, the corpus gate, the
   discovery rows and the compare ladder read ONE outcome per document today, define the
   document outcome as a function of per-account outcomes (fail closed: any account not
   validated → the document is not validated; say what review / withheld mean per account).
2. **Per-account reconstruction and validation.** For each boundary mechanism the packet
   measured (roll-up-oracle, section-identity, section-equation-scan, none): what printed
   evidence establishes a section's period, opening, closing, counts, totals, ledger, daily
   balances; how the UNCHANGED `reconcile` + ADB run per account; the ratified idle-sibling
   predicates as the ONLY admission of an omitted section, with the omission SURFACED
   (SIBLING-OMISSION-SURFACE: a payload field + an integrity note); the roll-up oracle:
   each account's closing must equal the roll-up's figure and the cross-account total must
   sum — a mismatch refuses the document.
3. **Transfers.** The deterministic identification of internal transfers (same-day
   opposite-signed pairs across the document's accounts with matching amounts and a printed
   transfer designation where the paper prints one) — kept in both ledgers, flagged
   `internal_transfer` with the counterpart account, excluded from package deposit /
   withdrawal analytics; the fail-closed rule when a candidate pair is ambiguous (never guess).
4. **Fail-closed conditions**, complete and testable: printed partition only; distinct
   account identities; every posting section accounted for; per-account pair agreeing with
   the roll-up; reconcile.ok and adb.ok per account; one currency per account with explicit
   evidence outranking defaults; no memorised or arbitrary selection; loan facilities on a
   roll-up never read as deposit accounts (the packet's condition 12); a section whose
   boundary is inferred → refuse.
5. **Surfaces touched** (file by file): schema, pipeline, serialization, telemetry record,
   corpus gate, discovery rows / compare, packages, webapp routes / renderers, the CSV /
   XLSX exports — with what changes for single-account documents (nothing) and what a
   multi-account document renders.
6. **Regression surface and proof plan.** The protected 2,596 (byte-identical payloads by
   `cohort_replay` for every reader and the whole archive sweep); the 109 pinned incl. the
   12 multi-posting and the CONS-L1 document (a truth-set ceremony: name the exact expected
   movement for each); the readers with L-1 refusals (which refusals become independent
   accounts, which stay refusals); mutation tables per gate; the corpus gate's new
   per-account assertions.
7. **Staged delivery** as separate implementation cards, each independently provable:
   (a) the data model + single-account no-op proof; (b) SIBLING-OMISSION-SURFACE; (c) the
   CU member-statement template reader for the roll-up-oracle mechanism (the packet's
   `guardian_cu` family first — 8 documents demonstrated); (d) CONS-HARDCODE — Consumers on
   the new model, the pinned document's movement ruled; (e) transfers + package analytics;
   (f) the surfaces. Expected safely recoverable count per stage FROM THE PACKET'S MEASURED
   TABLES, never an estimate.

# Method
Read-only; you may prototype in a scratch tool under `tools/l1_design_*.py` (unregistered,
unimported by production — the experiments guard applies) to verify a design claim (e.g.
that a `DocumentStatement` wrapper leaves every single-account payload byte-identical). Every
number in the design comes from the packet's instruments or your own committed instrument.
Privacy scan of added lines (0); commit-message scan (0); guards (255).

# Git ownership
Base `train9` at launch. Branch `wave9-l1design`, worktree `.claude/worktrees/mt9-l1design`.
Own: the design document, `tools/l1_design_*.py`, W3 `§L1DESIGN` (append-only). No production
change, no registration, no test wiring.

# Report
Status; commit range; the design's one-paragraph summary; the staged-delivery table with the
measured expected count per stage; the open questions that need Gustavo (if any); privacy
and message-scan counts.
