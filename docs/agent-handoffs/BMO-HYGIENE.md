# Agent Handoff — BMO-HYGIENE (batch 9, hygiene: an explicit refusal and a keyword hardcode in analysis/bmo.py)

Read `docs/agent-handoffs/BATCH9-RULES.md` first; it binds (never synthesise a date; a refusal is an
answer and silence is not; no statement-specific constants). Ocean reviews and composes; you never
merge or push. The bmo reader's whole cohort is WITHHELD today (0 validated, 4 withheld) — this card
moves no outcome; it makes the reader say what it does.

# Findings (W3 §ROWCAP, carried concerns 3 and 4)
1. `analysis/bmo.py` SILENTLY drops a printed row whose date does not exist (two rows dated a 29
   February of a non-leap year on one withheld document). Refusing the date is right (the Huntington
   ruling forbids inventing one); the silence is not — the reader must record the refusal (an
   integrity note / the omission surface the L-1 design provides once S2 lands, or a fail-closed
   decline of the document if a printed posting cannot be published) so a short ledger is never a
   quiet ledger.
2. `analysis/bmo.py:_WITHDRAWAL_KEYS` is a description keyword list whose every entry is printed by
   the same four-document cohort the reader was written on — a statement-specific constant (R-1
   class). Replace with structural capability (the printed column, section, or sign the layout
   carries) or, if the layout carries none, refuse rather than infer direction from vocabulary.

# Proofs
`cohort_replay --parser bmo --group WH:bmo --group DECL:bmo_ca_business --expect-identical` at base
and at closure (the 4 withheld stay withheld — payload changes only in the refusal record, classified
leaf by leaf; bmo_ca_business is a different module — confirm untouched); the RAISE-PRIVACY-4 funnel
and CHAIN_GUARDED registration for bmo survive; the canonical hardcode guards pass with the list
removed; mutation table; privacy and message scans 0; guards, conformance, suite, corpus gate.

# Git ownership
Base `train9` at launch (after L1-S2 composes if the omission surface is used). Branch
`wave9-bmohyg`, worktree `.claude/worktrees/mt9-bmohyg`. Own: `analysis/bmo.py`, its tests,
`tools/bmohyg_*.py`, W3 `§BMOHYG`.
