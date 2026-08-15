# Agent Handoff - DETECT-BUDGET (batch 4, central triage - STOP-THE-LINE fix)
Ocean reviews and merges; you never merge or push.
**The detect-sweep affordability test (250 ms cap over the pinned corpus)
now fails on BASE at 68 registrations under load (measured: base 310.0 ms
median vs branch 306.4 on a loaded machine; ~203 ms quiet at 56 regs;
largest pinned doc 259.8 ms best-of-three moderately loaded). Every cell
is wasting an hour proving the red is not theirs. HUNT-CELL predicted
this at 55 registrations. DO NOT raise the constant - the budget protects
the discovery run's cost. Fix it structurally.**

# Identity
- **Agent:** DETECT-BUDGET - make the per-document detect sweep cheap
  enough that the budget holds with headroom at 80+ registrations, with
  PROVEN claim-equivalence.

# Git ownership
- Base: main `ba13ec3` - Branch: `wave4-detbudget` - Worktree:
  `.claude/worktrees/mt4-detbudget`. Own: analysis/parser_registry.py
  (the sweep path), a shared prescan seam if you build one, the
  affordability test (its MEASUREMENT DESIGN, not its constant), tests,
  W3 log (#DETBUDGET).

# Design candidates (characterize costs first; pick on evidence)
1. Two-tier detection: a cheap prescan (e.g. one pass of literal
   required-marker membership over the document, or an aggregated
   regex/Aho-Corasick over all registrations' required literals) gates
   which registrations run their full Detection. A registration whose
   required markers cannot all be present can never claim - skipping it
   is EXACT, not approximate. Compose carefully with regex-shaped
   markers (survey which registrations use non-literal required markers;
   they either join the prescan conservatively - always run - or expose
   a literal anchor).
2. Per-registration profiling: the top sweep cost is 8.6% for one
   registration (WOODFOREST-INIT measured; woodforest itself 2.8%, and
   JHA's clean-once precedent bought 5.9 points) - harvest the
   mechanical wins (single _clean per doc across ALL registrations,
   compiled-once patterns, early-exit ordering) but note shaving alone
   CANNOT close it (removing the 9th-most-expensive registration
   entirely still leaves ~254 ms).
3. The test itself: wall-clock on a shared loaded machine is the wrong
   instrument (three cells measured base-arm failures). Redesign the
   measurement to be load-robust (e.g. budget on OPERATIONS or on a
   paired base-vs-branch ratio, or best-of-N with a quiet-machine
   assertion) while KEEPING an absolute cost ceiling for the discovery
   run - state the new contract precisely.

# The equivalence proof (binding)
Whatever you build: full-archive claim-set equivalence over all 3,380
distinct shas - every document's (winning parser, claim set, scores for
claimants) IDENTICAL before and after; the conformance cross-product
green; zero behavior change anywhere outside sweep cost. Measure the
new sweep cost quiet + loaded, report both.
