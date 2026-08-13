# Agent Handoff — COMMSEC-GEN

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13 high-parallelism coverage wave.

# Identity
- **Agent:** COMMSEC-GEN · the community_section core-processor template
  generalization: Mission Valley product variants (19 docs detected at 0.5
  and declined at parse) + First Carolina Bank (2 unclaimed docs on the
  same template). This template will recur under other banks' names —
  build the capability, not the bank.

# Git ownership
- **Base:** current main (record the SHA) · **Branch:**
  `wave3-community-section` · **Worktree:** `.claude/worktrees/mt-commsec`.

# Context (read in-tree)
`PROJECT_STATUS.md` · `WAVE2_EXECUTION_LOG.md` 2026-08-13 entries ·
`W3_TRACKA_LOG.md` §CHASE-LAYOUTS families C and D3 (the characterization:
core template + `missionvalleybank.com` + `Business Analyzed/Interest/…
Checking` products; `fcbcarolinas.com` on the same template) · `R3_RFC.md`
/ `R4_CONFORMANCE_FINDINGS.md`. Baseline run `6893a75b` (main checkout,
read-only). Derive your populations exactly: failed docs with
mission_valley ≥0.5 in candidates/near_miss (19: 17 in `Chase/`, 2 in
`Mission Valley Bank/`), plus the 2 First Carolina docs in `Chase/`
(fcbcarolinas.com furniture); report exact counts + distinct hashes.

# Phase requirements (binding — same law as every cell)
1. Characterize structurally BEFORE code: which section names / products /
   issuer furniture differ from the layouts `community_section.py` already
   reads; classify each sub-family detection / extraction / both / unusable.
2. Structural capability over layout literals: generalize the section
   grammar (section naming, product headers) rather than enumerating
   product-name strings where a structural rule exists. New registrations
   (first_carolina; mission_valley variants if a new id is warranted) under
   the FULL R-3/R-4 standard; existing `mission_valley` and `dakota_west`
   claims must remain byte-identical — before/after sweep over their entire
   claimed populations (mission_valley 17 validated, dakota_west 3 per
   COUNTS data; derive exact sets from the run).
3. Claimed-but-not-validated is NOT success; per-document instrument first;
   fail closed with diagnoses where evidence is insufficient.
4. `analysis/count_semantics.py` is NOT yours: mission_valley is a
   COMPARABLE entry — if your change alters what its stated counts mean,
   STOP and report (Ocean owns the table). New registrations are UNSURVEYED
   by default, which is correct — do not add entries.

# Scope
- **Allowed:** `analysis/community_section.py`, new entry-point module(s)
  if the architecture wants them, `analysis/parser_registry_entries.py`
  (new registrations / supersedes edges only), tests
  (`tests/test_community_section_layouts.py` + conformance fixtures +
  count pins), `W3_TRACKA_LOG.md` (append §COMMSEC-GEN).
- **Protected:** everything else, same list as every cell. Archive
  read-only; synthetic fixtures; $0 vendor.

# Validation
Full default suite; corpus-marked; `corpus_gate.py` GREEN 106/3
byte-identical; guards; full conformance cross-product zero; the
mission_valley/dakota_west sweeps; a stratified probe (≥400 docs across all
folders) proving zero unexpected claims. Exit codes verbatim.
ANALYSIS_STAGE_VERSION bump is Ocean's at merge.

# Stop conditions
Registry-machinery or shared-util needs; ambiguity weakening; truth-set
movement; count-semantics implications (see req 4); evidence the template
sub-families are unusable-dominant.

# Final report to Ocean
Characterization table first; per sub-family: root-cause class, approach,
fixtures; verbatim diffs for `community_section.py`; sweeps; proofs with
exit codes; measurement preview vs `6893a75b`; commit list; risks;
unresolved questions.
