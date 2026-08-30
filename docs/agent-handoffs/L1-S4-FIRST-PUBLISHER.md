# Agent Handoff — L1-S4-FIRST-PUBLISHER (batch 9, L-1 stage 4: the first multi-account publisher + internal transfers; the LAST coverage cell of batch 9)

**AMENDED 2026-08-30 with L1-S3's composed findings (see "Inherited from S3" below); NOT launched
until the four rulings in "Rulings required" are recorded in BATCH9_TRANSITION §8.** Read `docs/agent-handoffs/BATCH9-RULES.md` first — the "Batch-9 final
rulings" block binds (Q3 corroborated, Q9 option B, Q10, the SCOPE FREEZE: this is the last
deterministic coverage cell; after it composes, batch 9 closes). Then the reviewed design
`docs/moneythumb-replacement/L1_INDEPENDENT_ACCOUNT_DESIGN.md` — §2 (per-account reconstruction;
§2.3 the idle sibling; §2.6 what closes), §3 (transfers: R-d's four clauses, the INTERNAL vocabulary,
§3.3 ambiguity), §4 (fail-closed conditions L1-C1…C17), §6.3 (pinned exposure), §6.5 (the gate's
per-account assertions), the S4 row of §7 — and the three review files for S1 / S2 / S3 and
`reviews/BATCH9_Q3PROBE_REVIEW.md`. Ocean reviews and composes; you never merge or push.

# Scope (exactly the design's S4 row, under the rulings)
1. **The first publisher**: a shared CU member-statement template module for the `rollup-oracle`
   boundary mechanism (the `FAM:guardian_cu_statement_summary` family), its registration, per-account
   reconstruction and validation under the UNCHANGED validator (Q9 B: reconcile + canonical ADB +
   `posting_dates_cover_source` + the section's own required printed counts / totals + unchanged
   account / period / currency / integrity validation). The roll-up table is EVIDENCE only (L1-C5:
   no figure is taken from it unless `column_roles_printed`), never a source of value.
2. **The Q3 class as code**: `printed_pair_coincides_and_no_row_printed` added to
   `analysis/sibling_omission.py`'s L1-C17 vocabulary with ALL SEVEN conditions (the six printed
   conditions and the roll-up witness — the table's row for the section, located by the section's
   own label, reproducing its closing to the cent, read from the `close` role never a position).
   A section failing any condition is NOT admitted by this class (fail closed unless another ratified
   class applies). The probe `tools/q3_corroboration_probe.py` (composed) is your oracle: your
   implementation must admit exactly the sections it passes and refuse exactly the ones it fails,
   including under its five mutants.
3. **Internal transfers** (R-d, `analysis/pipeline.py`): a movement is INTERNAL only when ALL FOUR
   hold — same posting date, same magnitude to the cent, opposite sign in a sibling account on the
   SAME document; one-to-one document-wide; unique counterpart (§3.3: two or more admissible
   counterparts → no pairing, integrity note `ambiguous_internal_transfer`, the package refuses to
   aggregate that document); AND a printed INTERNAL-MOVEMENT designation on at least one leg, read by
   `analysis/transaction_classifier.py`'s `_INTERNAL_TRANSFER_CREDIT_PATTERNS` alone (the
   peer-to-peer rail vocabulary `_TRANSFER_PATTERNS` is REFUSED as evidence). Transfers stay in each
   account's ledger flagged INTERNAL (ruling condition 4); the package layer excludes them from gross
   deposits / counts / revenue / the withholding denominator ONLY when flagged.
4. **Package layer** (`webapp/app.py` `_package_analysis`): membership requires each account's own
   `validated` (never job status alone — `:661` today); `sibling_account_omission_detected` /
   `completeness: partial` published per Q10 (S3 wired the surface dark; you light it for the first
   real publisher); no published average over two members sharing one `content_sha256` (Q5).
5. **Q10 in force**: an admitted omission never demotes an independently validated account; the
   document outcome is the weakest ACCOUNT's with only the two `failed` overrides; the S2 pins
   (`tests/test_l1s2_*`, the document-outcome resolver + tripwire) must stay green — your classifier
   changes, if any, are named inside the tripwire's pattern and the carriers pin is extended
   explicitly (the S2 re-review's residual: a fold outside the pattern with a novel reason escapes).

# Population and the three figures (Q9 B — report ALL THREE every time)
- **strict after-chain diagnostic**: 0 documents (diagnostic only; never a refusal rule);
- **production-check population**: 2 documents close on every located section today;
- **Q3-eligible population**: 6 more — `333E226A75FE5441` `472A0966A5204513` `596804AA1ACD01EB`
  `C3D3E48F1E14AE2A` `F5BC9FB6D084559E` `FFAC0A88768A8A59` — all seven conditions PASS 6 / 6
  (probe 65041bf, review 1f81fbc, 42 / 42 independent agreement).
- **Demonstrated target = 8** (2 + 6), the maximum; report what you actually validate — if a
  document fails the unchanged validator on a published account it is NOT forced. Newly validated
  is counted ONLY by the deterministic validator at the composed tree (`cohort_replay --group
  <the census group>` and `--parser <your registration>`), never by this card's figure.
- Beyond this family: nothing. The freeze forbids widening; the design declines to number it.

# Known hazards you inherit (each needs a test or a recorded reason)
- Q3 review MINOR-1: all six documents are `native-pdf-text` — the witness was never exercised
  against OCR'd input; record it in W3 as a standing risk (Phase 2 re-measures). MINOR-3: the
  section ↔ roll-up link runs through `boundary=rollup-oracle` + `identity_index`; a mis-binding is
  invisible to the probe — bind by the section's printed label AND the identity token, and refuse
  when they disagree. MINOR-4: on `472A0966A5204513` the design's `find_rollup` loses the printed
  product name and the binding rests on the identity token alone — fix the reader or refuse, never
  guess.
- S2 review MINOR-3: three other `None` exits of `_parse_sectioned_statement` bypass the omission
  ledger (archive population 0; the "no sibling section LOCATED" class, 16 documents) — if your
  publisher reaches them, route them through the ledger with a test; else record.
- `dakota_west`'s derived section selection (design §9 F4) touches pinned `F748A799FDC7F25E` — do
  not change it here unless the rulings below require it, and then only as a named ceremony.
- L1-C1: an inferred boundary is refused before the validator sees it (`section-equation-scan`
  closes 0 by design). L1-C8: the section's own printed counts / totals / daily balances are FED to
  `reconcile` and the ADB — passing `None` disables the only checks that see a truncated ledger.

# Proof (BATCH9-RULES contract; exit codes verbatim; one heavy harness per host)
- `cohort_replay --expect-identical` at base over every registration you touch and over
  symitar / community_section / dakota_west / mission_valley / zions / guardian_cu; at closure the
  same WITHOUT `--expect-identical`: newly validated named per SHA with the validator's own evidence;
  previously validated ALL preserved; every changed leaf classified.
- The killer sets: the 47 transfer pairs on 7 documents (43 designated for the exclusion, 4 refused
  — 3 peer-to-peer, 1 nothing printed); a constructed ambiguous pair (0 in the archive) refusing the
  aggregation; mutation tables for L1-C1…C13 and for each of the seven Q3 conditions; the probe's
  five mutants re-run against your implementation.
- The corpus gate GREEN with its new per-account assertions lit (§6.5); the corpus-marked slice;
  the whole-archive sweep at the final tree (movers = exactly the named newly validated, 0 raises,
  0 regressions); guards, conformance, full suite; privacy and message scans 0 with the population
  named (`--shas` file). Register truthful; no key re-declared (`git show train9:corpus_gate.py`).
- W3 `§L1S4` with the three figures, the per-document table (published accounts, omitted sections
  by class, transfers flagged, package fields), and the Q10 / Q3 / Q9 rulings by number.

# Inherited from S3 (composed; the review map's S4 lane — each needs a test or a recorded reason)
- Your readers are now WATCHED: `tools/l1s3_surface_census.py` sweeps 46 read shapes (the
  `accounts` key, name-bound subscripts, comparisons in `.items()` walks, attribute access,
  aliased publisher imports) and the reviewer's seven evasions are its committed test vector.
  Every reader you add is either taught (renders per account under the weakest-account rule /
  refuses loudly) or truthfully excused BY NAME in the census — the census red is a floor failure.
- The document fold is `telemetry/record.py::classify_document` and it is PINNED:
  `tests/test_l1s2_document_outcome.py` asserts exactly one declared fold with that name, wired
  and callable, and the Q10 pins resolve through it. If you touch the classifier, the pins and the
  tripwire move WITH it in the same commit; a rename outside the `classify_document*` /
  `document_outcome*` stems is forbidden (the S2 re-review's residual).
- `classify_document` and `refuse_document_payload` raise `TypeError` at their doors on a
  non-Mapping — that TypeError IS the S2 resolver's contract; never broaden it to swallow shapes.
- Cross-account package math REFUSES: the member-set check keyed on the shared document identity
  publishes `None` + `cross_account_averages_refused` for the five per-period figures (sums
  untouched). Your publisher makes this branch REACHABLE for the first time — prove the refusal on
  a real two-account document and take §6.5's remaining four gate assertions (the review's
  MINOR-1 names them as owed).
- S3 review MINOR-10: `totals["months"]` counts MEMBERS and `app.js:1458` labels them "statement
  periods" — a two-account document reads as two periods. Dark today (all five per-period keys
  `None`); your publisher lights it — fix the count or the label in your lane, with a test.
- `webapp/artifact_cache.py`'s seam is prose; the real cache seam is `webapp/worker.py`'s
  `compute=` lambda. The seam census (`tools/l1_design_reader_probe.py::SEAMS`) pins LINE NUMBERS
  — corpus_gate.py is pinned at 1608 at this tree; if your edits move a pinned line, re-pin in the
  same commit and say so in W3.

# Rulings RECORDED (Gustavo, 2026-08-30; BATCH9_TRANSITION §8.13–§8.16 — binding; S4 is unblocked on the ruling side)
- **Q1 — Option A (with Q5).** Publish the independently validated account; surface the document /
  package incompleteness (`completeness: partial`); the document outcome may reflect the weaker
  account without invalidating the one that passed. **Package membership is ACCOUNT-based: an
  account enters the package iff its OWN outcome is `validated`** — never the parent job / document
  status. No package analytic of any kind (ADB, revenue, deposits, counts, withholding, transfers)
  incorporates a non-validated account.
- **Q2 — Option A on all three halves.** INTERNAL requires an admissible printed designation on at
  least one leg — arithmetic coincidence never suffices, the four refused pairs stay refused, and
  P2P rail vocabulary (ZELLE / VENMO / CASH APP) is not proof of same-customer ownership.
  Counterparts on the SAME document only (cross-document matching is a future architecture problem
  S4 must not infer). Ambiguity refuses the PACKAGE AGGREGATION of that document — the ledger, the
  account validation and the ADB history stay untouched; both printed legs remain in their ledgers.
  Transfer flags affect package analytics only.
- **Q5 — Option A (with Q1).** One ACCOUNT → one ADB, never one PDF → one blended ADB; each member
  keeps its own; for multiple members from one multi-account document,
  `package_average_daily_balance: None` + `cross_account_averages_refused`; legitimately additive
  fields stay where their own rules permit; do NOT refuse the whole package — forbid the blending
  arithmetic, not the field or the package; never reintroduce the halving defect.
- **Q7 — two dated rows.** "A section that posts" = at least TWO dated rows, unchanged through S4;
  the zero-row Q3 / yield-only classes unaffected.
- **Combined doctrine:** validated accounts publish and enter the package individually;
  non-validated accounts are excluded and do not contaminate validated siblings; the package
  surfaces partial completeness, recognizes only explicitly evidenced internal transfers, refuses
  ambiguous transfer aggregation, never blends separate account ADBs. Q3 / Q9 / Q10 in force as
  ruled. *Validation belongs to the account. Completeness and aggregation belong to the package.*
Q4 (two denominations) and Q6 (per-account activity range) remain NOT in S4's population: refuse
until ruled, as the design says — record the refusal count.

# Launch gate (the only remaining blocker)
The L1-S3 re-composition: closure-2 must land (the serializer shape decided by account count alone),
the same reviewer confirm, and Ocean compose with the gate and corpus slice GREEN at the composed
tree. Launch base is train9 AFTER that composition.

# Git ownership
Base `train9` after L1-S3 composes. Branch `wave9-l1s4`, worktree `.claude/worktrees/mt9-l1s4`. Own:
the template module and its registration, `analysis/sibling_omission.py` (the Q3 class only),
`analysis/pipeline.py` (transfer identification), `webapp/app.py` (`_package_analysis`), their
tests, `tools/l1s4_*.py`, W3 `§L1S4`. No version constant (Ocean's at the train).
