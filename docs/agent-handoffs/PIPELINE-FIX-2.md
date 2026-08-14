# Agent Handoff - PIPELINE-FIX-2

Ocean reviews and merges; you never merge or push. Coverage-wave batch 3.
**Protected-module cell: analysis/pipeline.py. Pinned-diff discipline -
minimal hunks, quoted verbatim in your report, Ocean forensic review at
merge (the FIXUPS-1 and FILENAME-BOUNDARY entries in
WAVE2_EXECUTION_LOG.md are your template).**

# Identity
- **Agent:** PIPELINE-FIX-2 - two evidence-backed pipeline cards, both
  counterfactually proven by HUNT-CELL (+8 validated combined), one card
  inherited from the FILENAME-BOUNDARY survey.

# Git ownership
- Base: current main (record SHA) - Branch: `wave3-pipeline-fix-2` -
  Worktree: `.claude/worktrees/mt-pipefix`. Own: `analysis/pipeline.py`
  (the two hunks ONLY), `analysis/regions.py` + `analysis/bofa.py`
  (repair-gate signatures ONLY if card 1's design lands there), tests,
  W3 log (#PIPEFIX section).

# Card 1 - repairs keyed on the claiming registration (+5 proven)
`apply_statement_repairs` gates bank repairs on markdown substrings
(`"REGIONS" in markdown.upper()` etc., pipeline.py ~:75-91). HUNT-CELL
proved counterfactually: five Huntington statements that merely PAY a
bill to Regions Bank get their balances and totals rewritten by
`repair_regions_summary` (analysis/regions.py:243) and fail; with the
repair suppressed they validate. The F-PROVENANCE survey flagged the
same class for the BofA repair. Fix per the standing design ruling: key
each repair on the CLAIMING registration id (dispatch is in scope at the
call site), never on markdown substrings. LLM-path documents (no
claiming registration) get repairs by bank-label lookup through the
registry (the R-3 ruling pattern), not by substring. Every existing
repair consumer must keep firing exactly where it fired legitimately:
sweep the full claimed populations of regions and bank_of_america
(byte-identical), plus the five named Huntington docs (now validate).

# Card 2 - a deposit-image sheet is not a missing page (+3 proven)
The page-declaration integrity check (pipeline.py ~:306) treats an
unlabelled deposit-image sheet as a missing declared page on three
Huntington docs. This is the same check FIXUPS-1 restricted with a
lookbehind (see its entry: "a continuation footer is not a page
declaration"). Characterize the printed shape of the image sheets from
the three named docs (HUNT §H log has hashes), then restrict the
declaration set structurally (what counts as a page declaration), never
by issuer literals. The FILENAME-BOUNDARY invariance tests must stay
green (page-declaration fabrication/suppression fixtures exist - run
them explicitly).

# Card 3 (inherited, small) - wells year-inference residual
analysis/wells.py takes the statement year from the first year token in
the BODY by position (the boundary removed the filename instance; the
survey's F2 noted the body-position residual). ONLY if cheap and
structural: anchor the year read to the printed period label rather than
document position. If not cheap, report the card back with what you
found - do not force it.

# Hard rules
Fail-closed preserved everywhere; no repair may fire where its
registration did not claim (or its bank-label did not resolve on the LLM
path); zero movement outside the named populations (archive-wide
containment sweep: the only movers are the 5 regions-payment Huntington
docs + the 3 page-declaration docs + any legitimately-affected LLM-path
docs, each named); pinned corpus byte-identical (regions + bofa pinned
docs are the exposure - check them FIRST, the scotia standard).

# Standing wave rules (binding)
As in every batch-3 handoff: read PROJECT_STATUS.md + the 08-13/14 log
entries first; run of record 88be9dd3; archive/cache read-only, direct
artifact paths only; $0 vendor; private scratchpad subdir; long shells
die - sequential proofs; suite/corpus-marked/gate GREEN 106/3 + guards +
conformance; every mover named; exit codes verbatim; commit incrementally;
never merge or push. ANALYSIS_STAGE_VERSION bump is Ocean's.

# Final report to Ocean
Pinned-exposure check first; the two pipeline hunks verbatim; the repair
containment sweep; the named movers; proofs with exit codes; commits;
risks; unresolved questions.
