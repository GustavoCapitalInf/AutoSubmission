# Agent Handoff - SIGN-READER (batch 6, card 3 - the structurer's sign inversion, fixed before the path turns on)

Ocean reviews and merges; you never merge or push.
**Financial-semantic card: protected-cell discipline, pinned diffs, Ocean
forensic review at merge.**

# Identity
- **Agent:** SIGN-READER - `analysis/structurer/tokens.py` inverts BOTH
  attested minus glyphs on its live path. It CALLS the shared grammar and
  then discards its answer. The structurer is the generic unclaimed-layout
  reader: this is the sign rule for every document no registration claims,
  and it must be correct BEFORE the path is ever enabled, not after.

# Git ownership
- Base: main `eef77c6` - Branch: `wave6-signreader` - Worktree:
  `.claude/worktrees/mt6-signreader`. Own: analysis/structurer/tokens.py,
  analysis/structurer/summary.py (finding 2 disposition),
  analysis/regions.py:40 (finding 3 disposition), tests, W3 log (#SIGNREADER).

# The evidence base (read first: W3 §MGD10, the private-opinions ledger)
1. **tokens.py:139 `money_value`** tests `text.startswith("-")` ASCII-only,
   then ends `return -abs(value) if negative else abs(value)`.
   `parse_money` had already recovered the sign; the `abs()` throws it away:
   U+2212 and U+2013 tokens invert (+ for -). `MONEY_RE` (:65) admits ASCII
   and parentheses only, so the tokenizer path inverts identically.
2. **summary.py:127 `_RANGE_RE`** - a FOURTH date-range class mixing dashes
   with words; carries U+2013/U+2014 but not U+2212. MG-D's guard is silent
   on it by design (it needs word alternatives, so it is a genuine local
   superset, not a copy). Decide: repoint what is dash-only onto the canon
   (PERIOD_DASH) while keeping the word alternation local, or record why not.
3. **regions.py:40** re-implements half of `normalize_sign_glyphs`
   (`replace("–","-")` - U+2013 only, misses U+2212). Regions is
   offline-inexecutable (§WIRING), so an end-to-end proof is impossible;
   fix by differential against the shared helper + unit proof, and say so.

# The work
The fix wants a DIFFERENTIAL against the shared grammar, reader by reader:
for each touched reader, a table of token -> (before, after, parse_money)
proving after == parse_money on every attested glyph class, ASCII/paren
behaviour byte-identical. The structurer is opt-in OFF - keep it off; your
proof is unit/differential-level plus the standard zero-movement sweep.
Mutation-kill the sign rule (flip the abs, drop the U+2212 branch - each
dies).

# Expected archive movement
ZERO on the 3,380 (structurer off; the one archive document in its reach
already fails for other reasons - name it, show it unmoved). Any mover is a
hard stop.

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-16 batch-5 entry in WAVE2_EXECUTION_LOG.md
first. Base main `eef77c6` (v13, OCR v3, registry 72, suite 4,511,
corpus-marked 27). Run of record:
`discovery_reports/2026-08-16T000943.012887-0000-2e3ea385` (validated 2,430 /
review 15 / withheld 63 / failed 859 / deferred 13; 3,380 distinct shas;
analysis regenerated cold at v13). Archive + caches READ-ONLY; OCR artifacts
by DIRECT file path only (never the webapp_data sqlite index); $0 vendor;
private uniquely-named scratchpad subdir. Long background shells get killed -
run long proofs as SEQUENTIAL single commands; detached-process aliveness via
`tasklist`, never MSYS `kill -0`. Family populations: derive by live
detection replay or artifact-store enumeration, NEVER from rows.csv parser_id
alone. Proof floor per branch: full default suite + corpus-marked slice +
`python corpus_gate.py` GREEN (106/3; verdicts 102 validated / 4 review / 3
withheld) + guards + conformance cross-product (72x71); exit codes verbatim;
every mover named by content_sha256 + outcome + field; claimed != validated;
zero movement outside your named populations; commit incrementally, clean
tree; NEVER merge or push - Ocean runs the train. ANALYSIS_STAGE_VERSION bump
is Ocean's at merge. Fail-closed everywhere.

# Final report to Ocean
The differential tables per reader; dispositions for findings 2 and 3 with
measurement; mutation-kill evidence; zero-movement sweep; hunks verbatim;
proofs with exit codes; commits; risks.
