# Agent Handoff — P22-HOLDOUT (Phase 2.2 cell H: the sealed truth store, the adjudication CLI, the unseen holdout cage, and the leakage firewall)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `docs/agent-handoffs/PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (ALL of it — the 2026-09-03 section: R3 sealed truth
and adjudication, R4 the unseen holdout, R11/R12 the denominators), then the umbrella
`docs/agent-handoffs/PHASE2-2-TRUTH.md` (D9, D10, cases 18–21, 24), then
`docs/moneythumb-replacement/PHASE2_ARCHITECTURE_PLAN.md` §12 (the holdout protocol this cell makes
operational: manifest fields, strata, human oracle fields, false-accept/false-refusal metrics, burned vs
graduated), then `docs/moneythumb-replacement/phase2_remainder/PHASE2_REMAINDER_PLAN.md` §G.2.2 cell H
and §J.5, `phase2_remainder/research/REPO_CORPUS_MEMO.md` §6 (what human truth exists and the leakage
surfaces), `tests/test_evidence_boundary.py` (the tripwire idiom), `ocr/inspect.py` (content sha
convention; read only), `corpus_gate.py` (how the pinned truth CSVs are consumed — the discipline, not
the code). Ocean reviews and composes; you never merge or push. **Hygiene card: `newly validated = 0`;
nothing under `analysis/`, `ocr/`, `discovery/`, `webapp/`, `telemetry/`, `evidence/`, `layout/` is
touched; no network; the store lives OUTSIDE the checkout; nothing customer-derived enters a tracked
file.**

# Why
There is no human label for ≈ 3,270 of the 3,380 documents; "validated" is the validator's own verdict;
a false accept is measurable today only on the 80 pinned documents inside the denominator, and the
holdout cage the accepted architecture called operational was never built (`REPO_CORPUS_MEMO.md` §6).
Gustavo is the final adjudication authority (R3); MoneyThumb outputs, folder names, census
classifications, parser and OCR outputs may be presented as EVIDENCE to an adjudicator and may never
become labels by themselves. This cell builds the sealed store those verdicts live in, the CLI that
collects them, the holdout manifest that keeps unseen documents unseen, and the firewall that keeps all
of it out of every implementation and tuning path.

# What you deliver (ruled — do not re-decide)
1. **`tools/holdout/store.py` — the sealed truth store.** Location: `SEALED_TRUTH_DIR` from the process
   environment, REQUIRED (no default); the path must be an absolute directory OUTSIDE the repository
   checkout (refuse any path under the checkout root, under `.claude/`, or under `Bank Statements/`);
   created on first write. Storage: `truth.jsonl` append-only; one record per adjudication event
   (several events per sha are allowed; the LATEST event per sha is the current verdict); each record:
   `record_id`, `content_sha256` (upper hex), `kind`, `sub_kind`, `account_kind`, `modality`,
   `completeness_findings` (closed codes), `legible: bool`, the five oracle figures (`account_count`,
   `printed_period_start`, `printed_period_end`, `opening_balance`, `closing_balance`,
   `printed_transaction_count` — each MAY be null), `sampled_rows` (up to three `{date, description_hash,
   amount}` — the description is stored as a sha256, never as text), `adjudicator` (a role string, not an
   email), `adjudicated_at` (UTC ISO), `packet_digest` (sha256 of the evidence packet shown),
   `notes_hash` (sha256 of free notes; the notes themselves are NOT stored — say so in the CLI), `prev`
   (the previous record's hash) and `hash` (sha256 over the canonical JSON of every field but `hash`) —
   a chain; `verify_chain()` walks it and refuses a rewritten or reordered file. `manifest.json` in the
   store: `store_version`, `record_count`, `chain_head`, `updated_at`. **The repository-side export**:
   `tools/holdout/digest.py` writes `docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt` containing
   ONLY `store_version`, `record_count`, `chain_head`, the sorted list of sha16 prefixes of adjudicated
   documents (no verdicts), and the holdout manifest's sha16 list with statuses — the non-sensitive
   manifest Gustavo's ruling permits (R3: "expose only a non-sensitive manifest/hash/version to the
   repository where reproducibility requires one").
2. **`tools/holdout/manifest.py` — the unseen holdout cage.** `holdout.jsonl` in the same store:
   `holdout_id`, `content_sha256`, `added_at`, `source_batch` (a batch label, e.g. `unseen-2026-09`),
   `not_in_dev_corpus: bool` (asserted by the CLI against the run of record's sha list at add time —
   a sha present in the development corpus is REFUSED), strata (`modality`, `known_bank | unknown_bank`,
   `single | multi_account`, `table_heavy | summary_only`, `currency`, `page_count_bucket`,
   `layout_family_code` — a code, never a customer name), `status ∈ {unseen, evaluated, burned,
   graduated}`, `last_evaluated_at`, `last_engine_version` (a settings key or tag), `burned_by` (the
   card/commit that named it), `graduated_at_tag`. Transitions enforced: `unseen → evaluated` (by the
   evaluation tool only), `evaluated → burned` (explicit, with the card name), `evaluated → graduated`
   ONLY when `graduated_at_tag` names a freeze tag that exists AND `last_engine_version` did not change
   because of the item (the CLI records the attestation; the rule is the accepted architecture §12's);
   anything else refuses. `holdout_shas_for_refusal()` returns the sha set for the runner's research-mode
   refusal (cell T reads the DIGEST file in the repository, not the store — write the digest, and put
   the sha16 list there).
3. **`tools/adjudicate.py` — the adjudication CLI.** `python -m tools.adjudicate queue --rows
   <run>/rows.csv --slice <name> --shas <file> --packets <private dir>` builds the evidence packet per
   sha: page images rendered locally with PyMuPDF at a modest dpi into the PRIVATE packet directory
   (outside the checkout; the CLI refuses a packet dir inside it), the classifier's proposed verdict and
   signals IF a per-sha classification CSV is supplied (`--classification <csv>`; cell C's
   `tools/classify_census.py` output; optional), the prior census tag from `census_batch9/per_sha.csv`
   labelled `EVIDENCE (census, agent-derived, not truth)`, the MoneyThumb comparison ONLY if explicitly
   supplied and labelled likewise (default: absent), and the packet digest. `python -m tools.adjudicate
   run --slice <name>` walks the queue: shows the packet path and the evidence, asks kind / sub_kind /
   account_kind / modality / legible / completeness findings / the five oracle figures / three sampled
   rows / notes, PROPOSES NOTHING as a default (the human types the kind; the proposal is displayed as
   evidence only), appends the record, verifies the chain, advances. `python -m tools.adjudicate status`
   prints counts by kind for the store (aggregates only). `python -m tools.adjudicate export-digest`
   writes the repository digest. Non-interactive mode for tests: `--answers <json>` (synthetic).
4. **`tools/holdout/evaluate.py`** — the evaluation event (design + a working skeleton; the first real
   evaluation is 2.4's): given a run's `rows.csv` and the sealed store, for every holdout item in
   `unseen|evaluated`: compare the system's verdict and key figures with the oracle; classify each miss
   by A/B/C using the row's `failure_class` and reasons; emit FALSE ACCEPT (system `validated`, oracle
   contradicts a money identity or a sampled row), FALSE REFUSAL (oracle complete+legible statement,
   system not validated), and `layout_generalization` counts; mark items `evaluated` with the engine
   version; print aggregates only; write a private report. Prove it on a synthetic store + a synthetic
   rows.csv.
5. **The firewall — `tests/test_truth_firewall.py`:** AST at any depth over every module under
   `analysis/ layout/ ocr/ evidence/ discovery/ webapp/ telemetry/`: no string literal
   `SEALED_TRUTH_DIR`, no `os.environ`/`getenv` access naming it, no import of `tools.holdout` or
   `tools.adjudicate`; `tools/holdout` itself imports nothing from `analysis/ ocr/ discovery/ webapp/
   telemetry/ layout/` (it consumes CSVs and PDFs only, plus `evidence` is NOT needed — keep it out);
   the store refuses a path inside the checkout; the digest file contains no kind/verdict/figure (a test
   greps it for the closed kind vocabulary and for money shapes and asserts none).
6. **Slice 1 queue prepared (measurement, not a gate):** using the run of record's `rows.csv` and the
   census lists, build the slice-1 sha file (the 117 census NOT-STATEMENT + the 51 SCAN-UNCLAIMED thin +
   the 13 portal exports + the 16 PF-INVALID-PDF + 30 random FAM chosen with a fixed seed = ≈ 227) and
   the packets into a private directory named in your W3 by count only; DO NOT adjudicate anything
   yourself — Gustavo is the adjudicator (R3). The queue's existence and packet digest go in the W3.
7. **No hardcodes; no customer data in tracked files** (fixtures are synthetic PDFs and synthetic shas;
   the store and packets never enter the checkout; the digest carries sha16 prefixes only — the
   privacy scanner's `hex_sha_substring` rule already excuses those).

# Files you own (exact; nothing else)
`tools/holdout/__init__.py`, `tools/holdout/store.py`, `tools/holdout/manifest.py`,
`tools/holdout/digest.py`, `tools/holdout/evaluate.py` (new) · `tools/adjudicate.py` (new) ·
`docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt` (new; produced by the tool; initial content =
an EMPTY store's digest, record_count 0) · `tests/test_truth_store.py`, `tests/test_holdout_manifest.py`,
`tests/test_adjudicate_cli.py`, `tests/test_holdout_evaluate.py`, `tests/test_truth_firewall.py` (new) ·
`corpus_gate.py`'s `EXCLUDED_ANALYSIS_CALLERS` register ONLY if a tool of yours must be excused (check
`train12` first; append at most the entries you need) · `.gitignore` (only if a private packet path
default lands inside the checkout — it must not; prefer refusing) · your W3 section.

# Mutation table (run every mutant, name every killer)
M1 the store accepts a path under the checkout → the location test · M2 a record's `hash` omits `prev`
→ the chain-rewrite test · M3 `verify_chain` skips the first record → the reorder test · M4 the CLI
pre-fills the kind with the classifier's proposal → the "no default" test · M5 the manifest allows
`unseen → graduated` → the transition test · M6 `graduated` without a freeze tag → the tag test · M7 a
dev-corpus sha accepted into the holdout → the refusal test · M8 a production module reads
`SEALED_TRUTH_DIR` (inject a line into a scratch copy of `discovery/runner.py` under the test) → the
firewall · M9 the digest includes a kind → the digest test · M10 the description stored as text →
the sampled-rows test · M11 the evaluation marks an item `evaluated` without recording the engine
version → the evaluate test · M12 FALSE ACCEPT computed from the verdict alone without an oracle
contradiction → the evaluate test.

# Proof floor
Full default suite; the 5 canonical guards; the 7 canonical conformance files; `python corpus_gate.py`
GREEN 105/3/1; `pytest -m corpus`; `cohort_replay --expect-identical` at base and closure over
`guardian_cu` + `first_citizens` (you touch no production module — say so); privacy scan 0 over your
added lines against the run-of-record population (`discovery_reports/TRAIN11-4f7d798/…-331d9136/rows.csv`,
cold cache `.claude/recovery/webapp_data_train11_cold`, READ-ONLY) — the sha16 digest lines are
excused by rule, report the class counts; message scan 0. Heavy proofs one at a time on this host.

# Report contract (final message to Ocean AND your W3 section `# §P22HOLDOUT — …`)
population (synthetic store fixtures; the slice-1 queue by count and packet digest) · root cause ·
solution · newly validated (0) · other ladder movement (0) · previously validated preserved (all,
identical) · regressions (0) · correctness evidence (chain, transitions, refusals) · firewall evidence
(the AST scan's scope and a demonstrated catch) · commits · proof-floor exits · privacy count · risks
last (the adjudication bottleneck; what the evaluate tool cannot judge without sampled rows).

# Exclusions
No adjudication performed by you · no truth values in any tracked file · no import of production
packages from `tools/holdout` · no change to `discovery/` (cell T reads your digest) · no MoneyThumb
comparison by default · no learned anything · no cost field.
