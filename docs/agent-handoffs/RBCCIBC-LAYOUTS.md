# Agent Handoff — RBCCIBC-LAYOUTS

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the coverage wave. The largest measured tranche of the wave:
**64-65 of 79 unclaimed RBC/CIBC docs prototype-measured recoverable** with
the SHIPPED helpers (SC-RBCCIBC report — its prototypes and per-doc results
are the evidence base; verify, don't trust).

# Identity
- **Agent:** RBCCIBC-LAYOUTS · four interlocking cards on one ownership:
  D (rbc.py money-grammar hardening — the gate), B (rbc English personal
  layout, 12 docs), C (rbc_french business layout, 18-19 docs), A (new
  English `cibc` registration, 34 docs) + F1 (mangled-font guard, 4 docs).

# Git ownership
- **Base:** current main (record the SHA) · **Branch:**
  `wave3-rbccibc-layouts` · **Worktree:** `.claude/worktrees/mt-rbccibc`.
  You own `analysis/rbc.py`, `analysis/cibc.py` (card E hygiene ONLY if
  needed for A; else leave), new `analysis/cibc_en.py` (or extend cibc.py —
  your structural call, stated), `analysis/parser_registry_entries.py`
  (new registrations/markers only), tests, `W3_TRACKA_LOG.md` (§RBCCIBC).

# CARD D FIRST — it gates everything (scout-measured deltas per fix)
All in `analysis/rbc.py`, each with a named-doc evidence trail:
- `_SUMMARY_MONEY` (:41): cannot read `- $2.55` (minus space dollar) —
  reads POSITIVE. 6 of 12 personal docs print negative closing balances
  this way; this fix alone took R2 6/12 → 12/12.
- `_MONEY_RE` (:23): same hole in the grid (`194.82 - 192.33`).
- `_FR_MONEY_RE` (:501): `\)?` cannot span `(77,76 )` — bracket-negative
  becomes POSITIVE (9 R1 docs, R1 10/19 → 18/19); lookbehind admits `+`
  so `ARCHIVE+8 129,14` glues to 8129.14 (4 docs).
- French summary regexes (:600-609): unanchored `([\d ]+,\d{2})` absorbs
  the printed YEAR (`… le 23 juillet 2025 801,53 $` → 2 025 801,53); the
  total-row wordings at :603/:606 match 0 of 19 real docs (both stated
  totals silently None → identity check skipped). Fix wording + anchor +
  read the two printed COUNTS the French path never assigns.
- `_read_grid_rows` (:161-165): when the opening-label entry carries more
  than the opening cell, the rest of the line is DISCARDED — CIBC prints
  its first real row on that line. Fix structurally (card A depends on it).
- `_grid_cells` (:60-85): `/`-rate (`2.25/1,000`) and trailing ISO code
  (`450000.00 PKR`) guards.
- Silent row drops (:465, :667): dropped rows must be counted/diagnosable,
  not vanish.
CRITICAL: card D alone must leave all 153 currently-claimed rbc docs and
2 cibc_french docs BYTE-IDENTICAL (the fixed shapes don't occur in the
claimed population — scout scanned all 155: 0 hits; your sweep proves it).

# CARD B — rbc English personal (12 docs, measured 12/12)
Second detection marker (`DETAILS OF YOUR ACCOUNT ACTIVITY`), second
activity gate, personal summary grammar (`Total deposits into your
account +` etc., NO counts), `Your opening balance $X` dateless form.
Registry: extend rbc's markers or add a sibling registration — your call
under R-3/R-4, zero cross-claims, no weakening of existing precedence.

# CARD C — rbc_french business (19 docs, measured 18/19 + cheque-serial rule → 19)
Business activity gate (`Date Description Chèques et débits ($)…`),
business summary grammar WITH both printed counts. This resurrects a
currently-DEAD registration (rbc_french: 0 claims corpus-wide; its marker
matches no real document — fix the marker to the real furniture). The
cheque-serial residual (54003F2D588C: `Chèque - 253 127,40`; the cheque
image pages print `No de série: 253 Montant: 127,40 $`) may use the
in-document serial oracle structurally; if too fiddly, 18/19 with the one
named fail-closed is acceptable.

# CARD A — CIBC English Account Statement (34 docs, measured 34/34)
No English CIBC parser exists. New registration under full R-3/R-4:
markers from the issuer furniture (`CIBC Account Statement`, `Transaction
details`, the grid header — NOT the bank word alone), positive+negative
fixtures, zero cross-claims (incl. vs cibc_french's 2 claims — scout
verified 0 collisions). Reuse `rbc._read_grid_rows` by IMPORT (the
no-parser-helper-clones guard forbids copying; if the import crosses
modules awkwardly, lift the helper to a shared module and have rbc import
it too — state which you did). Handle: `Balance forward` continuation
resets, header-line row compression, USD accounts (`Closing balance … USD
= $X` — currency must be USD), FX rows (`450000.00 PKR @.005`),
deposit-note-fee rates (`2.25/1,000`).

# CARD F1 — mangled-font guard (4 docs)
Broken-CMap text layers (`Bu-in0-- A11ount 4t5t060nt`) still print intact
`ROYAL BANK OF CANADA` — a widened gate would claim them and ship
corrupted money. Add a structural admissibility check (digit-integrity of
money-shaped tokens, or CMap-damage signal) so these NEVER claim. Fixture
from the real shape (synthetic reproduction).

# Expected result (honest accounting)
~64 failed→validated (A 34, B 12, C 18-19), 4 protected by F1, zero
regressions across rbc 153 / cibc_french 2 / all pinned docs. Per-document
instrument (summary identity, balance walk, counts where printed) before
claiming anything. Claimed-but-not-validated is not success.

# Scope guards
count_semantics: rbc is COMPARABLE both directions — your changes must not
alter what its stated counts mean (the French path GAINS count assignment;
that is new data for an existing comparable id — flag it in your report
for Ocean's table review, do NOT edit the table). New registrations are
UNSURVEYED — correct. Protected: everything else. Archive read-only via
direct artifact paths (a discovery run may be writing the cache — NEVER
the sqlite index). $0 vendor. Machine under load — generous timeouts.

# Validation
Full default suite; corpus-marked; corpus_gate.py GREEN 106/3
byte-identical; guards (esp. no_parser_helper_clones); full conformance
cross-product zero; stratified non-RBC/CIBC probe (≥400 docs) proving zero
unexpected claims; the 155-doc byte-identity sweep for card D; per-family
instruments. Exit codes verbatim. Stage bump is Ocean's.

# Final report to Ocean
Card D diffs + 155-doc sweep first; per-card family results with named
fail-closed docs; registration decisions stated; fixtures; proofs with
exit codes; commits; risks; unresolved questions (incl. the rbc_french
count-assignment note for the semantics table).
