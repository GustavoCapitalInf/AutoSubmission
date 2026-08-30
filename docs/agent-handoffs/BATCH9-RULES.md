# Batch-9 standing rules (binding for every batch-9 cell; read before your card)

Ocean reviews and composes; you never merge or push.

## Base facts
- Batch 9 opened from `main` = tag `batch8-final` = `68110ce`. The train branch is
  `train9`; the planning source of truth is `docs/moneythumb-replacement/BATCH9_TRANSITION.md`
  + `CENSUS_BATCH9.md` + `census_batch9/{per_sha.csv, clusters.json, opportunity_estimates.json}`
  (train9 `3311a8a`). Your base is `train9` at your handoff's commit.
- Run of record: `discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d/`
  (pointer file `discovery_reports/train8-logs/train8_run_dir.txt`): 3,380 content shas;
  validated 2,596 / review 18 / withheld 55 / failed 698 / deferred 13. Its cold cache is
  `.claude/recovery/webapp_data_train8_cold` — one OCR partition (v4) and one analysis
  partition (v16, registry fingerprint at `7185633`, settings key
  `7652A5AFA29E4FAEECAA8BBA5E169C24F3346A546298547DE6A5A06771FC093D`). READ-ONLY; nothing writes there.
- Tree at base: registry 83, `ANALYSIS_STAGE_VERSION` 16, `OCR_STAGE_VERSION` 4. Floor: full
  suite 6,742 · canonical guards 255 (5 files) · canonical conformance 1,270 (7 files, 83 × 82)
  · `python corpus_gate.py` GREEN 105 PASS / 3 WITHHELD / 1 REFUSED · corpus-marked 30; the
  pinned currency / provenance surfaces as in PROJECT_STATUS.md's batch-8 milestone line.

## Gustavo's batch-9 doctrine (binding)
Priorities: (1) maximise DEFENSIBLE validated coverage; (2) preserve correctness and every
existing validated document; (3) deterministic / local, zero recurring paid inference;
(4) stronger free/local extraction only where it genuinely helps; (5) paid OCR / VLM only
for residue nothing cheaper can solve — NOT in this wave; (6) multi-model consensus
selective, never default; (7) the deterministic validator remains authoritative.

Non-regression: `newly supported -> validated` while `previously validated -> remain validated`.
Never gain coverage by relaxing reconciliation; weakening ledger identity; weakening page /
account completeness; weakening statement-period validation; weakening currency evidence;
accepting ambiguous account selection; lowering transaction-coverage requirements;
suppressing integrity flags; moving failed / withheld to validated without the same
deterministic proof standard; special-casing benchmark statements; rewriting source values
to force reconciliation. **Every previously validated batch-8 sha is protected**: any
`validated -> review / withheld / failed / deferred` is an unexpected regression that BLOCKS
composition unless explicit per-sha evidence shows the batch-8 validation was itself
incorrect — then STOP, document the correctness defect with exact per-sha evidence, and
report for a ruling (a correctness correction, never a silent excuse). A payload change on a
`validated -> validated` document must be proven semantically correct. **A gain never cancels
a regression** (`+10 / -2` is NOT ACCEPTABLE). No statement-specific hardcodes. Fail closed.
$0 vendor: no paid OCR, no VLM, no rented GPU, no ensemble, no hosted model call anywhere
(tests included).

## Checkpoint rulings (Gustavo, 2026-08-29 — binding; BATCH9_TRANSITION §8 is the record)
- **Official batch-9 coverage stays at 2,596** until a movement cell has passed closure,
  hostile re-review, composition and non-regression proof. A cell reports CANDIDATE numbers.
- **GL3 (category_partition's per-day-oracle refusal) is reversed** as a refinement of the
  doctrine — conditional on the date-rule BLOCK's closure and re-review; correctness over the
  count; the five pinned GLANCE documents and the protected GLANCE cohort preserved.
- **L-1 — the independent-account architecture proceeds** under these conditions: an idle
  sibling is admitted ONLY when explicit statement structure establishes the sibling AND its
  empty / silent state (absence of parsed activity alone is insufficient); each account
  reconstructs and validates independently by the unchanged validator; NO document-level
  combined ADB; inter-account transfers stay in each account's ledger and are identified as
  INTERNAL for package analytics (no double-counting); no arbitrary or memorised account
  selection; explicit currency evidence outranks defaults. Design first (`L1-ARCH-DESIGN`),
  reviewed, then implementation slices; `analysis/consumers.py:90` (a memorised
  product-name + account-number selector on a pinned document) is a CORRECTNESS hardcode
  and the first pinned test case — Consumers is not widened before it (`CONS-HARDCODE`).
- **Huntington's 3-document repair-doctrine exception is REFUSED**: never synthesise a dated
  debit from an undated bank-stated fee total. The rule generalises: a parser never writes
  an amount or a date the paper did not print.
- **WELCH** stays under the general DESC-COLUMNS / printed-row rung (`DESC-ROTATION`); no
  statement-specific fix anywhere, ever.
- **Privacy**: the 414 inherited production residue sites are CLASSIFIED before any is
  rewritten (`PROD-RESIDUE-CLASSIFY`); record redaction stays refused where it would destroy
  benchmark / provenance evidence; fixture / truth / name work continues in its own cards.

**Q10 (Gustavo, 2026-08-30) — sibling omission: SURFACE, DO NOT DEMOTE.** An explicit sibling omission beside an independently valid account keeps the account `validated` and surfaces the omission separately (document / package layer: `document.omissions`; `sibling_account_omission_detected: true`, `completeness: partial`). The account must still, on its own: have explicit / unambiguous boundaries; reconstruct correctly; pass the UNCHANGED validator; prove period, currency, opening / closing balances, transactions, ledger identity and ADB; carry nothing misattributed from the sibling. If the omission makes the boundaries ambiguous or prevents independent validation → FAIL CLOSED. The design's §1.5 `("review", "sibling_section_omitted")` override is SUPERSEDED — never wire it. The 15 protected carriers (W3 §L1S2) carry pinning coverage so no later stage can demote them silently.

**Batch-9 final rulings (Gustavo, 2026-08-30; BATCH9_TRANSITION §8.8–§8.12) — operative.**
* **Q3 — granted WITH CORROBORATION.** The omission class `printed_pair_coincides_and_no_row_printed` admits a section only under all seven: own opening caption + figure; own closing caption + figure; the two coincide to the cent; no dated ledger row in the section; no counts / totals for the section; no daily-balance table for the section; and, where the document prints a roll-up / enumerating table with identifiable column roles, that table independently reproduces the section's closing. The roll-up witness is MEASURED by the bounded `Q3-CORROBORATION-PROBE` over the six `guardian_cu` sections before S4 relies on the class; a section failing any condition stays outside the class and fail-closed unless another ratified class applies. Q10 applies to the published accounts.
* **Q9 — Option B.** S4 is judged against the existing production standard (reconcile + canonical ADB + `posting_dates_cover_source` + the section's own required printed counts / totals + unchanged account / period / currency / integrity validation). The strict after-chain bound is DIAGNOSTIC ONLY — never a refusal rule. S4 reports three figures every time: strict after-chain diagnostic · production-check population · Q3-eligible population. Demonstrated target = 2 before the probe, 2 + (Q3 documents passing every condition) after it, maximum 8, never forced.
* **Q10 — kept in force.** Omission = package / document completeness (`sibling_account_omission_detected: true`, `completeness: partial`), never an automatic account downgrade; the 15 protected carriers stay pinned — and the pin must bite on the DOCUMENT leg too (a document-level fold mutant must fail a pin).
* **SCOPE FREEZE.** Batch 9 finishes ONLY L1-S2 → L1-S3 → L1-S4; after S4 composes: no new deterministic coverage cells; `ANALYSIS_STAGE_VERSION` bump; full proof floor; frozen-corpus cold run; `--fail-on-regression` compare vs the batch-8 run of record; remote CI; freeze the deterministic-v1 / multi-account-v1 baseline. Exceptions only: a cold-run regression; a correctness defect affecting previously validated output; something strictly required for S4 to function safely. Everything else → `docs/moneythumb-replacement/BATCH9_BACKLOG.md`. Target = safe deterministic v1 + working multi-account v1 + zero unexpected validated regressions + frozen reproducible baseline.
* **PHASE 2** (after the freeze): Unlimited OCR + PaddleOCR as EXTRACTORS ONLY feeding the SAME deterministic validator; first task the read-only `OCR-LEGACY-AUDIT` card; no Phase-2 implementation until that audit is reviewed; the extractors may not bypass or weaken any check (reconciliation, ledger identity, transaction coverage, account boundaries, page completeness, period, explicit currency, ADB, integrity, multi-account independent validation).

**S4 rulings (Gustavo, 2026-08-30; BATCH9_TRANSITION §8.13–§8.16) — operative.**
* **Q1 (with Q5) — publish the independently validated account; surface incompleteness; the document outcome may reflect the weaker account without invalidating the one that passed. PACKAGE membership is ACCOUNT-based: membership iff the account's OWN outcome is `validated` — never the parent job / document status. No package analytic of any kind incorporates a non-validated account.**
* **Q2 — INTERNAL requires a printed designation on at least one leg (never arithmetic coincidence; P2P rails are not proof); counterparts on the SAME document only; ambiguity refuses the PACKAGE AGGREGATION of that document, never the account or its validation. Transfer flags touch package analytics only — both printed legs stay in their ledgers and ADB histories untouched.**
* **Q5 — one ACCOUNT → one ADB; members keep their own ADBs; `package_average_daily_balance: None` + `cross_account_averages_refused` for multi-member-same-document packages; additive fields stay where their rules permit; forbid the blending arithmetic, not the package.**
* **Q7 — a section that posts = at least TWO dated rows; unchanged through S4.**
* Combined: validated accounts publish and enter the package individually; non-validated accounts are excluded and do not contaminate siblings; the package surfaces `completeness: partial`, recognizes only evidenced transfers, refuses ambiguous aggregation, never blends ADBs. Q3 / Q9 / Q10 stay in force exactly as ruled.

## Instruments (committed — use them, do not rebuild them)
- **Targeted-cohort proof:** `python -m tools.cohort_replay --group <cluster_group|cluster>
  | --parser <registration id> | --family <b8 key> | --folder <label> | --shas <file>
  [--out <private>.md] [--json <private>.json] [--label "<tree, card>"] [--expect-identical]`.
  Replays the cohort from the run of record's own cached text through YOUR tree with the
  runner's exact call, classifies with the runner's exact rules, and reports
  `newly validated | other ladder movement | previously validated preserved (payload
  identical / changed, with leaf PATHS) | validated regressions (BLOCKING, exit 2)`.
  Run it at your BASE with `--expect-identical` first (fidelity: exit 0 — measured at
  `3311a8a`: huntington 38/38 identical; WH:rbc + DECL:core_processor_sectioned +
  FAM:pnc_core_commercial_checking + RV:linkbank 36/36 identical), then at every closure
  tree over (a) your target cohort and (b) the baseline cohort of EVERY registration of
  every module you touched (`--parser` per id). Reports are private (they name shas and
  paths only, never values); the NUMBERS go in your record.
- **Privacy scan:** `python tools/privacy_scan_branch.py --data-dir
  .claude/recovery/webapp_data_train8_cold --base <your base> --ref <your branch>
  --rows <run>/rows.csv --where parser_id=<ids>` or `--shas <population.txt>` — every
  branch's ADDED lines against the printed tokens of the documents it worked on; report
  the count (0), never commit the hit list. Write regex instruments with the Write tool and
  byte-check them (a heredoc once turned `\b` into 0x08 and the scan was vacuous).
- **Archive sweep (owed once per coverage card at its final tree):**
  `python -m tools.regfp_zero_movement_sweep --rows <run>/rows.csv --data-dir
  .claude/recovery/webapp_data_train8_cold --baseline-settings-key
  7652A5AFA29E4FAEECAA8BBA5E169C24F3346A546298547DE6A5A06771FC093D --start A --end B --out <private>`
  chunked; every `moved` / `no_payload_now_publishes` / `payload_now_raises` finding must be
  inside your NAMED population by sha or it is a regression you explain or remove.
- **Census:** `census_batch9/per_sha.csv` (77 columns per non-validated sha: outcome, reason,
  failure stage, folder, route, dispatch, reconciliation facts, ADB checks failed, integrity
  flags, batch-8 family / cause / movement, text metrics, cluster) and `clusters.json`
  (sha16 lists per group). Name every document by content sha; a folder label is not an
  issuer.

## Proof floor per branch (exit codes verbatim, durable logs with an `EXIT=` line)
Full default suite; canonical guards (`tests/test_no_statement_hardcodes.py
tests/test_no_parser_helper_clones.py tests/test_r1_hardcodes.py
tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py`); canonical
conformance (`tests/test_parser_conformance.py tests/test_parser_registry_entries.py
tests/test_parser_detection_markers.py tests/test_parser_registry.py
tests/test_parser_crash_shapes.py tests/test_parser_exception_boundary.py
tests/test_count_semantics.py`; registry pins updated in the SAME commit as any registration);
`python corpus_gate.py` GREEN; the corpus-marked slice; a MUTATION TABLE for every gate or
grammar you add or touch (every mutant applied exactly as documented, run without `-x`, every
killer named — a test named after a gate is not a test of that gate); `cohort_replay` at base
and at closure; privacy scan 0; the archive sweep at the final tree when a reader changed.
Every mover named by sha + outcome + field; zero movement outside your named population;
`claimed != validated`; ledgers record measurements, not inferences — every headline number
reproduces from committed evidence, and instruments that produce headline numbers are
committed under `tools/`. Characterise before code. Structural capability over literals
(institution furniture — phone ladders, PO boxes, routing numbers, domains — is allowed and
must be justified as furniture). Doctrine binding: the ADB doctrine (one calendar-day ADB over
the printed period; withheld when daily evidence does not cover it), `CURRENCY_DOCTRINE.md`
(native currency canonical; jurisdiction defaults are affirmative evidence; a new Canadian
reader publishes the schema default and names itself a future mover), the L-1 rule (never
publish one account and silently drop another), the repair doctrine (parsers never write an
amount). Truth-set / pinned-surface movement outside an approved ceremony = STOP and report.

## Surfaces the batch-9 reviews found unscanned (now part of every branch's proof floor)
- **Commit messages.** Three batch-9 branches carried archive tokens in commit MESSAGES
  (dates, small figures, an authorisation-code-shaped token, two money shapes restated from
  a redaction). Before you report, scan `git log <base>..HEAD --format=%B` against your
  population's universe (the same scanner over a temp file) → 0; write messages in CLASSES
  ("a fixture date", "an example figure"), never instances. A branch is unpushed until Ocean
  composes, so a message reword (`git filter-branch --msg-filter`, trees byte-identical,
  sha references remapped in your records) is cheap — a token in a pushed message is not.
  Use `tools/huntington_msg_privacy_scan.py` until it becomes a `--messages` mode of the
  branch scanner (FIXTURE-PRIVACY-3). Its WORDS class fires on the mandated co-authorship
  trailer when a population prints that vendor as a merchant description — report the
  WORDS count with that attribution; MONEY / DIGITS / DATES must be 0.
- **Mutation harnesses on a shared host.** A harness that restores with `git checkout --`
  can leave a MUTANT in the working tree when git dies mid-run (index.lock contention was
  seen once). Restore in a `finally` that ignores the exit code, verify `git status
  --porcelain` is clean before returning, refuse to start on a dirty tree, and never run two
  harnesses concurrently on this host (check `tasklist` for another python first).
- **Heredocs.** A shell heredoc turned `\b` into 0x08 (twice) and `\n` escapes into real
  newlines inside a mutation table (CP-DECLINES). Instruments, mutant tables and regexes are
  written and edited with a FILE tool only, then byte-checked; never through a heredoc.
- **Where the corpus-marked slice runs.** Its RBC archive-currency proof walks the checkout's
  ANCESTORS for the OCR store and fails closed when none is found — run `pytest -m corpus` from
  the repo tree or a worktree beneath `.claude/worktrees/`; a temp worktree elsewhere reads
  "1 failed" by design (WH-ROW-CAPTURE's reviewer, 2026-08-30).
- **Your W3 section starts with its own `# §<CARD> — …` heading** on the first appended line
  (a section committed without it reads as a continuation of the previous section and the
  train helper's one-appended-section check is what catches it).
- **Report files.** This harness refuses agent-written `.md` files in the scratch directory;
  your report is your final message plus your W3 section — put every number there.

## Report contract (your final message to Ocean AND your W3 section)
`population | root cause | solution | newly validated | other ladder movement | previously
validated preserved | regressions | correctness evidence | generalization evidence` — plus
commits, proof-floor exits, the privacy count, risks last. Coverage cards require
`newly validated > 0` AND `unexpected validated regressions = 0`; hygiene cards require
`newly validated = 0` AND `preserved = all, payload identical`. Never summarise a cell as
green on a net count.

## Git and host
Worktree `.claude/worktrees/mt9-<card>`, branch `wave9-<card>`, base `train9` at your
handoff's commit; own ONLY the files your card names; commit incrementally on a clean tree;
NEVER merge or push. Your W3 section `§<CARD>` is APPENDED to
`docs/moneythumb-replacement/W3_TRACKA_LOG.md` (append-only; never edit another section —
the train helper rebuilds the log byte-exact and refuses otherwise). Windows host: `tasklist`,
not MSYS `kill -0`; long proofs as SEQUENTIAL single commands or detached processes launched
via `C:\Program Files\Git\bin\bash.exe` with POSIX paths and an `EXIT=<code>` terminator on a
durable log (background tool commands die at ~10 minutes; a headline number with no log does
not exist); OneDrive `PermissionError`s are transient — retry, never score them; mutation
harnesses restore with `git checkout --` and are only correct on a CLEAN tree; archive and
caches READ-ONLY; keep probes light — the machine is shared with one other cell.

## Composition lessons (Ocean, 2026-08-30 — from composing L1-S1)
`corpus_gate.py`'s `EXCLUDED_ANALYSIS_CALLERS` register is a SHARED APPEND SURFACE: two cells
appending at its end collide at composition as a non-W3 conflict (`train_merge_one` aborts exit 3;
Ocean resolves by hand — ours + theirs MINUS every entry train9 already carries, a register-scoped
duplicate-key check, `ast.parse`, `import corpus_gate`, then the amend). Cells: before you report,
check that no tool you register is already excused on `train9` (`git show train9:corpus_gate.py |
grep -c '"tools/<name>.py"'`) — lift nothing from another branch into the register. Ocean: never
chain `git add` / `git commit` after a resolver write on this host — a OneDrive lock can fail the
write while the chain continues and COMMITS THE MARKERS; verify `git show HEAD:<file> | grep -c
'^<<<<<<<'` is 0 on the committed blob before running anything against the tree.
Two more from the RV-PAGE-COVERAGE re-review (2026-08-30): `tools/huntington_msg_privacy_scan.py`
run WITHOUT `--shas` reports `population 0` and a vacuous zero — every recorded message-scan
command names its population (the documents the branch worked on); and the one-harness-per-host
rule was not honoured (a second cell's `pytest -m corpus`, full suite, `corpus_gate.py` and
sweeps overlapped a reviewer's corpus slice, which took 1,973 s) — heavy proofs run ONE at a time
on this host; check `tasklist | findstr python` before launching one and wait if another cell's
harness is running.
