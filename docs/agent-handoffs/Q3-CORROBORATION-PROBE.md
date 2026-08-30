# Agent Handoff — Q3-CORROBORATION-PROBE (batch 9, L-1; bounded, READ-ONLY; gates S4's Q3-eligible population)

Read `docs/agent-handoffs/BATCH9-RULES.md` first — the "Batch-9 final rulings" block binds: Q3 was
GRANTED WITH CORROBORATION (BATCH9_TRANSITION §8.8) and Gustavo's instruction is literal: *"Before S4
relies on this class, run the bounded corroboration probe over the six measured `guardian_cu`
sections. Do not assume the roll-up witness. Measure it."* Ocean reviews and composes; you never
merge or push. **No production change of any kind.** This is a measurement, not a feature.

# The question (exactly)
For each of the SIX idle sibling sections the design measured (§2.3 of
`docs/moneythumb-replacement/L1_INDEPENDENT_ACCOUNT_DESIGN.md`: six sections on six documents, all
`FAM:guardian_cu_statement_summary`, both figures from the section's own captions, 0 printing a
dated row / counts / totals / daily table), decide the SEVEN conditions of the ruled class
`printed_pair_coincides_and_no_row_printed`, each from the OCR-v4 artifact in the cold cache
(`.claude/recovery/webapp_data_train8_cold`), each PASS / FAIL / UNDECIDABLE with the printed
evidence quoted by its location (page, line index) — never by copying statement text into the
report:

1. the section prints its own opening caption AND figure;
2. the section prints its own closing caption AND figure;
3. opening and closing coincide to the cent;
4. no dated ledger row is printed in that section;
5. no counts / totals are printed for that section;
6. no daily-balance table is printed for that section;
7. **the roll-up witness** — where the document prints an account roll-up / enumerating table with
   IDENTIFIABLE column roles (the design's L1-C5 `column_roles_printed`), that table's row for the
   section independently reproduces the section's closing balance to the cent. If the document
   prints no such table, or its column roles are not identifiable, condition 7 is FAIL for this
   probe's purpose (the ruling's "where … prints" clause is satisfied only by a witness that exists
   and reads) — report the reason separately so the ruling's intent can be re-read against it.

# Identify the six
Use the design's own instruments, unchanged: `tools/l1_design_idle_evidence.py` /
`tools/l1_split_prototype.py --idle-siblings` at your base — they emit the six sections (SHA prefix,
section label, opening / closing provenance). Their output is your population; do not choose
documents by hand. If the instruments emit a different count at your base, STOP and report it.

# Instrument
`tools/q3_corroboration_probe.py` — read-only; consumes the cached OCR-v4 artifact and the design
instruments' section spans; reuses the design's caption / roll-up readers (import them, do not
clone them — `tests/test_no_parser_helper_clones.py` will catch a clone); emits a per-section table
(6 rows × 7 conditions) and a JSON record with the evidence locations; exit 0 when every cell is
decided (PASS or FAIL are both results), exit 3 on any UNDECIDABLE. Register it in
`corpus_gate.py`'s `EXCLUDED_ANALYSIS_CALLERS` if it calls the analysis (check
`git show train9:corpus_gate.py` first; never re-declare a key). Mutation table: a deliberately
mis-read roll-up figure must flip condition 7 to FAIL; a synthetic section with one dated row must
flip condition 4.

# Report (your final message AND W3 `§Q3PROBE`, appended with its own `# §Q3PROBE — …` heading)
- The 6 × 7 table; **N = the number of sections passing all seven**; therefore **S4 demonstrated
  target = 2 + N (maximum 8)**, stated exactly and never rounded up.
- For each FAIL: which condition, and whether another already-ratified class
  (`printed_dormancy_declaration`, `printed_zero_activity_summary`, `yield_only_arithmetic_with_summary_equality`)
  applies instead — the section stays fail-closed otherwise.
- Any section where the roll-up prints the closing but under a column whose role is NOT
  identifiable — reported as FAIL with the reason (this is the case the ruling's wording turns on).
- Privacy scan (`tools/privacy_scan_branch.py`) and message scan (`tools/huntington_msg_privacy_scan.py`
  with `--shas` the six) both 0; guards; the register test. Population 6, no other document read.

# Git ownership
Base `train9` at launch. Branch `wave9-q3probe`, worktree `.claude/worktrees/mt9-q3probe`. Own:
`tools/q3_corroboration_probe.py`, its test, W3 `§Q3PROBE`, the register entry. Nothing else.
