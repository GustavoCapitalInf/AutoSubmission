# Agent Handoff — TD-FRENCH

Complete self-contained brief. Ocean reviews and merges; you never merge or
push. Part of the 2026-08-13/14 coverage wave. Scout-characterized family
with a working prototype (SC-TDCAN report; prototypes + diagnostics in
`<session scratchpad>/sc_tdcan/` — fr_proto.py, fr_v2/v3.py, fr_diag.py,
md dumps; verify everything yourself, the prototype is evidence not code).

# Identity
- **Agent:** TD-FRENCH · the TD Canada Trust French (Québec) printed
  statement family: 13 docs, all in the TD Bank folder, zero elsewhere
  (corpus-wide marker scan of 3,409 artifacts found exactly 13).

# Git ownership
- **Base:** current main (record the SHA) · **Branch:** `wave3-td-french`
  · **Worktree:** `.claude/worktrees/mt-tdfrench`.

# The family (scout-measured)
Byte-identical physical grid to the layout td_canada_native already
validates 63 docs of, localized: `Relevé de compte`, grid `DESCRIPTION
RETRAITS DEPOTS DATE SOLDE`, `SOLDE REPORTE`, issuer line `Comptes émis
par : LA BANQUE TORONTO-DOMINION`, page footers `Crédits <n> <montant>` /
`Débits <n> <montant>`, `SOLDE CREDITEUR MENS MOYEN`, `SOLDE MIN MENSUEL`.
Day-first dates (`01MAI`), FR-CA money (`1 021,00` — use
`analysis/money.py:parse_french_amount`, precedent cibc_french/
bmo_ca_business/rbc), `DC` overdrawn suffix. **All 13 stated summaries
reconcile to 0.00**; 2,227 rows; feeding the existing
`_credit_counts_from_balances` solver unchanged reproduces printed counts
and totals exactly on **9/13**; the other 4 land in the known antisymmetric
wrong-side class (withheld_adb, never wrong published numbers). Expected:
**13 claimed / 9 validated / 4 withheld** with honest diagnoses.

# Requirements
1. New module `analysis/td_canada_french.py` + NEW registration under the
   FULL R-3/R-4 standard: issuer-furniture markers only (the French grid
   header + the issuer line class — NOT the bank name alone),
   detection-positive AND negative fixtures, zero cross-claims over the
   full conformance cross-product, single-marker invariant, SOURCE-comment
   invariance. Must not weaken or collide with td_canada_native/td_us
   precedence (supersedes only if genuinely narrower — likely unnecessary:
   the English markers cannot fire on these docs).
2. Reuse td_can's solver helpers CONSUME-ONLY (`_credit_counts_from_
   balances`, `_directions_from_credit_counts`); if a helper needs
   changing, STOP (TDFIX-1 owns td_can.py this cycle).
3. The scout's implementation caution is binding: a description ending in
   1-3 digits before a 3-digit-integer amount is ambiguous with FR space
   thousands (`PETRO-CANADA 30 145,55`); absorb a left group only when the
   decimal group is exactly 3 digits, and let the balance chain fail-close
   the rest. Fixture this shape both ways.
4. Per-document instrument before claiming success: page-footer counts,
   summary identity, balance walk. Claimed-but-not-validated is not
   success; expect 9/13 with the 4 named.
5. count_semantics: your new id is UNSURVEYED by default — correct;
   do not add entries (the table is Ocean's).

# Scope
- **Allowed:** `analysis/td_canada_french.py` (new),
  `analysis/parser_registry_entries.py` (NEW registration only), tests
  (`tests/test_td_french_layouts.py` + conformance fixture + count pins),
  `W3_TRACKA_LOG.md` (append §TD-FRENCH).
- **Protected:** everything else incl. td_can.py/td_us.py (TDFIX-1 owns
  them this cycle). Archive read-only; direct artifact paths only, never
  the sqlite index; $0 vendor. A full archive discovery run may be
  executing — expect load.

# Validation
Full default suite; corpus-marked; corpus_gate.py GREEN 106/3
byte-identical; guards; full conformance cross-product zero; a stratified
non-TD probe (≥400 docs across all folders) proving zero new-registration
claims outside the family; before/after over the td_canada_native 73 and
td_us 40 populations proving byte-identity (your registration must not
touch them). Exit codes verbatim. Stage bump is Ocean's.

# Final report to Ocean
Characterization confirmation first (13/13 derived from the run,
hashes); verbatim registration + module structure; fixtures; instrument
results per document; sweeps; proofs with exit codes; commits; risks;
unresolved questions.
