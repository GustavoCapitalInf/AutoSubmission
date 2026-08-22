# Agent Handoff - CURRENCY-SOURCE (batch 7, card 4 - currency provenance: every published currency says where it came from)

Ocean reviews and merges; you never merge or push.
**Gustavo's ruling (2026-08-21): "Keep the three hardcoded CAD pins for now
but improve provenance. Do not add FX conversion or cross-currency
aggregation yet; preserve native currency and fail closed across units."**

# Identity
- **Agent:** CURRENCY-SOURCE - add `currency_source` to the published
  Statement: the evidence class that produced `statement.currency`,
  CURRENCY_DOCTRINE.md §B's hierarchy made explicit in data rather than in
  prose. Additive; no currency VALUE moves anywhere.

# Git ownership
- Base: main (this handoff's commit) - Branch: `wave7-currsrc` - Worktree:
  `.claude/worktrees/mt7-currsrc`. Own: analysis/schema.py (the field),
  the currency-ASSIGNMENT lines of every reader that sets `currency` (ONLY
  those lines - DECLINES-F edits bmo_ca_business.py / capital_one.py /
  first_citizens.py in parallel, DECLINES-G edits scotia.py, and
  REPAIR-DOCTRINE owns columbia_bank.py; keep your hunks to the assignment
  sites so the train composes), the pinned currency surface in
  corpus_gate.py (extend it with the source - `PINNED_CURRENCY` values
  become `(currency, source)` or a sibling total map; your call, justified;
  RED on movement in either direction), serialization / package / UI code
  ONLY to carry the field, tests, W3 log (#CURRSRC).

# The vocabulary (closed; an enum, not free text; finalize and justify)
- `printed` - explicit currency wording read from the document.
- `product` - a printed product/account designation that fixes the
  currency (rbc.py's `CAD CHEQUING ACCOUNT` map; Desjardins' explicit USD
  product).
- `jurisdiction_default` - the ratified RBC Canada rule (rbc.py:322/:829 -
  the affirmative four-proof conjunction).
- `institution_default` - the reader asserts the currency from the
  institution's identity without reading it. Census every site:
  scotia.py:154, cibc.py:184/:410, td_canada_french.py:357,
  releve_facturation.py:441, bmo_ca_business.py:351, bmo.py:133 (fallback
  arm), td_can.py:488 (fallback arm)/:623, wealthsimple.py:235 - the
  batch-6 pinned census found 3 institution-hardcoded CAD among the 14
  pinned CAD; the archive-wide count is yours to measure.
- `schema_default` - `Statement.currency`'s default "USD": every publisher
  that never sets currency (fiserv_premier, the core-processor complex,
  the 94 schema-default pinned USD, ATB...).
A reader may not set a source it did not earn: one test per class that
feeds a printing lacking the evidence and asserts the class is refused.

# The work
1. Census on the base tree: every publisher of `currency` and its class;
   the per-class counts over the 3,380 (recompute at HEAD by the sweep
   tool's method) and over the 109 - enumerate BEFORE pinning; a surprise
   is reported, never blessed by baseline generation.
2. The field, additive, default `schema_default`, so a reader that never
   sets currency publishes the truth about it. The hardcoded CAD sites KEEP
   their value and declare `institution_default` (ruling).
3. The pinned surface: pin `currency_source` for all 109 next to the
   currency; gate RED on movement.
4. Consumers: PKG-CURRENCY's buckets (doctrine §F) and the package's one
   denominated ADB are unchanged in behaviour - prove with their existing
   tests untouched and green. No FX, no conversion, no cross-currency
   rollup, no UI conversion. Serialization carries the field; nothing else
   changes shape.
5. Archive differential: every stored payload differs from the recompute
   ONLY by the new field. The sweep will report `moved` with
   `fields: ['statement']` for every publisher - expected; prove the inside
   with a leaf-diff that masks `currency_source` (-> identical) and then
   shows it alone.

# Expected archive movement
A new field on every published statement; NO value of `currency` moves
anywhere (PINNED_CURRENCY 109/109 unchanged; the 151 RBC movers unchanged;
the nine CURRENCY-1 corrections unchanged; ATB stays USD pending its
packet). Outcomes / verdicts / every other field byte-identical. Ocean bumps
ANALYSIS_STAGE_VERSION at the train.

# Proof floor
The standing floor + the census + the pinned-surface enumeration + the
masked/unmasked leaf-diff over the full archive + the per-class refusal
tests + the mutation table (remove a class assignment -> a named test
fails; publish `printed` without evidence -> a named test fails).

# Report
The census (per class, archive and pinned); the vocabulary and its
justification; hunks verbatim (grouped by reader); the pinned surface; the
differential; proofs with exit codes; commits; risks - including any site
where the class was ambiguous and what you chose.

# Standing wave rules (binding)
Read PROJECT_STATUS.md + the 08-20 batch-6 entry in WAVE2_EXECUTION_LOG.md
first; your predecessors' W3_TRACKA_LOG.md sections are the standard. Base:
main at this handoff's commit (ANALYSIS_STAGE_VERSION 14, OCR v3, registry
74, suite 5,374, corpus-marked 29, `python corpus_gate.py` GREEN 106/3 with
verdicts 102 validated / 4 review / 3 withheld and the pinned currency
surface 109/109 = 14 CAD / 95 USD). Run of record: `discovery_reports/2026-08-21T014415.938236-0000-7a317445` (mode --scanned;
validated 2,456 / review 16 / withheld 63 / failed 832 / deferred 13 over
3,380 distinct shas; analysis regenerated cold at v14 under the deterministic
settings key `D3370EEBDCB87892A2739BCB0D882A66E72DCBFAB2553101111157B5A231DE24`).

THE ARCHIVE INSTRUMENT IS COMMITTED - use it, do not rebuild it:
`python -m tools.regfp_zero_movement_sweep --rows discovery_reports/2026-08-21T014415.938236-0000-7a317445/rows.csv --data-dir
webapp_data --baseline-settings-key D3370EEBDCB87892A2739BCB0D882A66E72DCBFAB2553101111157B5A231DE24 --start A --end B --out <private>`
run at your branch HEAD (chunk with --start/--end; the counts add). Every
`moved` / `no_payload_now_publishes` / `payload_now_raises` finding must be
inside your NAMED population by content_sha256, or it is a regression you
must explain or remove. The tool reports field NAMES only; where your card
moves a field on purpose, prove what moved INSIDE it with your own leaf-diff
(never print document text or figures into a report).

Archive + caches READ-ONLY; OCR artifacts by DIRECT file path only (never
the webapp_data sqlite index); enumerate per document by the run's own keys
(the sweep tool shows how) - never by one settings_key; $0 vendor (no hosted
model call anywhere, tests included); private uniquely-named scratchpad
subdir. Family populations by live detection replay or artifact-store
enumeration, NEVER rows.csv parser_id alone. Long proofs as SEQUENTIAL
single commands, or detached processes launched via `C:\Program
Files\Git\bin\bash.exe` with POSIX paths and tracked via `tasklist` (never
MSYS `kill -0`; the PATH `bash` is the WSL launcher and exits silently);
background tool commands die at ~10 minutes; a completion signal must be
producible only by completion (append your own `EXIT=<code>` terminator to a
durable log; "log non-empty" is pytest's progress dots).

Proof floor per branch (exit codes verbatim): full default suite;
corpus-marked slice; `python corpus_gate.py` GREEN (106/3; verdicts 102/4/3;
currency 109/109) unless your card is a ceremony that enumerates otherwise;
the CANONICAL guard set (tests/test_no_statement_hardcodes.py
tests/test_no_parser_helper_clones.py tests/test_r1_hardcodes.py
tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py -
242 at registry 74 before your changes) and the CANONICAL conformance set
(tests/test_parser_conformance.py tests/test_parser_registry_entries.py
tests/test_parser_detection_markers.py tests/test_parser_registry.py
tests/test_parser_crash_shapes.py tests/test_parser_exception_boundary.py
tests/test_count_semantics.py - 1,151 at 74 x 73; registry pins updated in
the SAME commit as any registration); a MUTATION TABLE for every gate you
add or touch - a test named after a gate is not a test of that gate: weaken
or revert each gate and name the test that fails; the archive sweep above.
Every mover named by content_sha256 + outcome + field; claimed != validated;
zero movement outside your named populations; ledgers record measurements,
not inferences (every headline number must reproduce from committed
evidence); characterize before code; structural capability over literals
(no statement-specific constants - guard-enforced; no merchant/lender
vocabularies); commit incrementally, clean tree; NEVER merge or push - Ocean
runs the train; ANALYSIS_STAGE_VERSION bump is Ocean's at merge. Fail-closed
everywhere.

Doctrine binding: the ADB doctrine (08-16 batch-5 entry, ADB-SPLIT: one
user-facing calendar-day ADB over the printed period; bank averages are
evidence-only; MoneyThumb's banking-day figure is never truth) and
docs/moneythumb-replacement/CURRENCY_DOCTRINE.md (native currency canonical;
no FX; no cross-currency aggregation; fail closed across units; jurisdiction
defaults are affirmative evidence, never absence rules). Truth-set movement
outside an approved ceremony = STOP and report. The machine is shared with
the other batch-7 cells - keep probes light and sequential.

# Final report to Ocean
The card's own report section, plus the W3 section in the shape your
predecessors set - measurements, not inferences; every number reproducible
from committed evidence.
