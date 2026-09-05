# PHASE2_P22HOLDOUT_REVIEW — independent adversarial review of cell H (P22-HOLDOUT)

```
VERDICT: APPROVE WITH FINDINGS — 0 BLOCK / 3 MAJOR / 6 MINOR
REVIEWED: branch wave22-holdout, closure tip 7173317 (base train12 b23cb50; diff b23cb50...7173317)
REVIEWER: an independent agent (Fable 5.1) that wrote none of the code; worktree .claude/worktrees/rev22-holdout (detached)
DATE: 2026-09-04
```

Every finding below was reproduced by the reviewer's own command (scratch instruments under the session
scratchpad; a synthetic sealed store under the system temp folder; the cell's real store and the private
packet directory were only listed and re-hashed). Nothing was committed, merged or pushed; the cell's
branch was not touched.

## 1. Findings

### MAJOR-1 — a tail truncation of `truth.jsonl` is laundered by the next append; no CLI path consults `manifest.json`
`TruthStore.append_record` verifies the chain (`_chain.verify`) but never `verify_against_manifest()`; after the
append it rewrites `manifest.json` from the (truncated) file, so the manifest that was the only witness to the
truncation now agrees with it. No command in `tools/adjudicate.py` (`run`, `status`, `export-digest`) and nothing in
`evaluate.py` calls `verify_against_manifest()` (`grep -c verify_against_manifest tools/adjudicate.py tools/holdout/evaluate.py` → 0, 0).
Because "the LATEST event per sha is the current verdict", deleting the last event for a sha silently reverts its
verdict, and the next adjudication re-seals the store. The store docstring's "so a truncated file is caught too" is
true only for a caller who invokes the check by hand.

Reproduction (`scratchpad/attack_chain.py`, synthetic store, 3 records → truncate to 2 → `append_record`):
```
E truncated to 2 records; verify_against_manifest before append -> ChainError (as designed)
E append after truncation: ACCEPTED (no manifest check on the append path)
[NOT DETECTED] E after the append: {'verify_chain': 'PASSES', 'verify_against_manifest': 'PASSES'}
E2 verdict for d0 after tail-delete + append: STATEMENT_COMPLETE (was NOT_A_STATEMENT) | verify_against_manifest: PASSES -> the reversion is sealed
F adjudicate.py calls verify_against_manifest: False / append_record calls verify_against_manifest: False
```
Fix: `append_record`, `status`, `export-digest` and `evaluate_run` must call `verify_against_manifest()` first and
refuse on disagreement; pin with a test that a tail-truncated store refuses the next `run`. (A whole-chain rewrite
that also rewrites `manifest.json` — case A3 — is detectable only against the committed `MANIFEST_DIGEST.txt`; a
`verify --against-digest` command is the natural home for that anchor and is worth adding in the same fix.)

### MAJOR-2 — the graduation freeze-tag condition is nominal (pre-dated tags, any tag, self-attested tag sets)
§12 rule (3): "at least one subsequent freeze elapsed … Same-wave graduation is forbidden." The card cites §12 as the
rule. Reproduced (`scratchpad/attack_manifest.py`):
```
2  graduate with a tag OLDER than the evaluation (batch9-final vs evaluated 2032-06-01): ALLOWED -> graduated
2b git_tags() count: 7; non-freeze tags admitted: archive/universal-prototype-2026-08-04, archive/universal-prototype-2026-08-05, mt9-l1s3-broken-compose
2c CLI graduate at a tag that exists ONLY in a caller-supplied --tags-from file: rc 0, state graduated | tag in git: False
```
`git_tags()` returns every tag, not freeze tags; `--tags-from` makes existence self-attested; nothing orders the tag
against `last_evaluated_at`. Fix: resolve the tag through git only (keep `--tags-from` for tests behind an explicit
flag or drop it), require an annotated tag whose creator date is later than `last_evaluated_at`, and record the tag's
object sha in `graduation_attestation`.

### MAJOR-3 — `not_in_dev_corpus` is asserted against whatever the caller supplies and recorded without its population
With `--dev-rows <run of record>` a run-of-record sha is refused (rc 1). With `--dev-shas <a one-line synthetic list>`
the SAME sha is admitted and the event records `not_in_dev_corpus: true` with no trace of what it was checked against:
```
3b holdout-add of a RUN-OF-RECORD sha with --dev-rows <run of record>: rc 1 items 0
3c holdout-add of the SAME sha with --dev-shas <one synthetic sha>: rc 0 items 1 | not_in_dev_corpus recorded as: [True]
```
The card says the attestation is "asserted by the CLI against the run of record's sha list". Fix: record
`dev_corpus_size` and a sha256 of the sorted supplied set in the `added` event (auditable), and refuse a set smaller
than the run-of-record population the card names (3,380) unless an explicit `--allow-small-dev-corpus` is passed.

### MINOR-1 — `run` records `queue.json`'s digest unverified and shows `EVIDENCE.txt` without binding it to the digest
```
5 tampered EVIDENCE.txt shown? True | record packet_digest == original queue digest: True | run re-verified the digest? False
6 queue.json packet_digest edited to ff..: record packet_digest == ffffffff (packet.json's real digest starts b8283aac)
```
"A verdict can be re-read against what the adjudicator saw" holds only if the private directory was not edited between
`queue` and `run`. Fix: recompute the digest from `packet.json` + page shas before showing, refuse on mismatch, render
the evidence text from `packet.json`.

### MINOR-2 — the location refusal accepts the checkout's ancestors and cloud-synced directories
Accepted: the repository's parent directory itself, a sibling under it, and a OneDrive path far from the checkout
(`scratchpad/attack_location.py`). The card's list (checkout root, `.claude/`, `Bank Statements/`) is satisfied; R3's
"on this machine" is not encoded, and the cell itself put the packets under Local AppData "outside OneDrive" for that
reason while the store has no such rule. Suggest refusing any ancestor of a repository root and refusing (or at least
warning on) a OneDrive root.

### MINOR-3 — evaluate skeleton edges
(a) a malformed value in `--figures` (`closing_balance: n/a`) is a contradiction → `false_accept` — a bad export can
manufacture a STOP-condition-shaped number; treat unparseable system figures as `not compared`. (b) `agree` is granted on
`account_count` alone (one non-money figure); the W3 documents it, but the label reads as oracle agreement — require
one money identity or name it `agree_partial`. (c) a system `refused` row (R11) classes as `unclassified` (expected on
this branch; cell T's reasons are not mapped yet). Reproduced in `scratchpad/attack_digest_eval.py`.

### MINOR-4 — writer identity is by convention
Any process that knows `SEALED_TRUTH_DIR` can append: `ChainedJsonl.append` bypasses `add()`'s refusals and the state
machine (a dev sha was written directly as `graduated`; a raw `added` event reset a `graduated` item to `unseen`), and
`record_evaluation` is callable outside `evaluate.py`. The firewall fences the production roots only; `tools/` and
`tests/` are not fenced. Consistent with the card's ruling (hashed, append-only, outside the checkout — no signing) and
with the cell's own "only as sealed as the machine" risk; recorded so it is not mistaken for enforcement.

### MINOR-5 — two small honesty items in the record
(a) three slice-1 packets are truncated at the 40-page default (`truncated: true` in 3 of 214 `packet.json`s) — the
adjudicator will see at most 40 pages of those; the W3 says "up to 40" but not that any were cut. (b) the W3's
"slice sha-list digest `14540440…`" reproduces only as sha256 over the sorted shas joined by LF with no trailing
newline (the file's bytes hash to `5cbb1a74…`); state the recipe.

### MINOR-6 — the firewall's docstring overclaims
`_findings` says "Every way a module could reach the store, at any AST depth". It is a literal / name / import scanner:
15 of 20 indirect shapes the reviewer injected are not seen (§4). Name the limit in the docstring and in the W3.

## 2. Mutation table re-run (all twelve, in the detached worktree, WITHOUT -x; `scratchpad/mutate.py`; tree clean after)
| # | result | killers (as re-derived) |
|---|---|---|
| M1 | KILLED 2 failed / 132 passed | `test_truth_store.py::test_refuses_every_ancestor_checkout_including_the_main_repository`, `::test_the_named_repository_roots_are_all_refused` |
| M2 | KILLED 1 / 133 | `test_truth_store.py::test_each_record_hash_covers_every_field_but_hash` |
| M3 | KILLED 3 / 131 | `test_truth_store.py::test_a_rewritten_earlier_record_is_detected`, `::test_a_first_record_whose_prev_is_not_genesis_is_refused`, `test_holdout_manifest.py::test_the_holdout_file_is_a_hash_chain_of_events` |
| M4 | KILLED 2 / 132 | `test_adjudicate_cli.py::test_run_never_prefills_the_kind_from_the_proposal`, `::test_run_interactive_asks_the_kind_with_no_default` |
| M5 | KILLED 2 / 132 | `test_holdout_manifest.py::test_every_other_transition_refuses[path1]`, `::test_the_transition_matrix_is_exactly_the_ruled_one` |
| M6 | KILLED 3 / 131 | `test_holdout_manifest.py::test_graduation_requires_an_existing_freeze_tag_and_the_attestation`, `test_adjudicate_cli.py::test_holdout_burn_and_graduate_follow_the_matrix`, `::test_holdout_graduate_reads_freeze_tags_from_git_by_default` |
| M7 | KILLED 2 / 132 | `test_holdout_manifest.py::test_a_development_corpus_sha_is_refused`, `test_adjudicate_cli.py::test_holdout_add_refuses_a_development_corpus_sha_and_accepts_a_new_one` |
| M8 | KILLED 10 / 124 | `test_truth_firewall.py::test_no_production_module_references_the_store` + the eight scratch-mutant cases + `::test_a_clean_scratch_copy_produces_no_finding` |
| M9 | KILLED 3 / 131 | `test_truth_firewall.py::test_a_digest_rendered_from_a_populated_store_is_non_sensitive`, `::test_the_digest_grammar_rejects_a_verdict_line`, `test_adjudicate_cli.py::test_export_digest_writes_the_non_sensitive_digest` |
| M10 | KILLED 2 / 132 | `test_truth_store.py::test_sampled_row_descriptions_are_stored_as_hashes_never_text`, `test_adjudicate_cli.py::test_run_with_answers_appends_records_with_the_packet_digest` |
| M11 | KILLED 2 / 132 | `test_holdout_evaluate.py::test_items_compared_are_marked_evaluated_with_the_engine_version`, `::test_a_second_evaluation_records_the_new_engine_version` |
| M12 | KILLED 5 / 129 | `test_holdout_evaluate.py::test_the_synthetic_evaluation_reports_each_judgement`, `::test_false_accept_needs_an_oracle_contradiction_never_the_verdict_alone`, `::test_stdout_carries_aggregates_only`, `::test_the_private_report_is_written_outside`, `::test_cli_entry_point_requires_the_store_and_prints_aggregates` |
12 / 12 killed; killers identical to the cell's table. Note: the mutation table has no mutant for MAJOR-1 (a
"manifest check removed" mutant would have survived, because there is no check to remove) nor for MAJOR-2's ordering.

## 3. Store-location attacks (`scratchpad/attack_location.py`, `attack_location2.py`; nothing created)
REFUSED: `..` segments resolving into the main checkout and into the worktree; a junction (`mklink /J`) and a directory
symlink under temp pointing into the checkout; `\\?\C:\…`, `\\localhost\C$\…`, `\\127.0.0.1\C$\…`, `\\?\UNC\…` forms; upper /
lower / mixed case; 8.3 short names (`C:\Users\GUSTAV~1\ONEDRI~1\…\BANKST~1`); forward slashes; trailing separator, trailing
dot, trailing space; the main `.git` directory; the user's `.claude` directory; `BANK STATEMENTS` in any case; a relative or
drive-relative path; whitespace padding. ACCEPTED (MINOR-2): the repository's parent directory, a sibling under it, a
OneDrive path. Controls: a sibling whose name prefixes the checkout's, and the scratchpad, are accepted correctly.

## 4. Firewall attack results (`scratchpad/attack_firewall.py`; one scratch copy per root: analysis/ ocr/ evidence/ discovery/ webapp/ telemetry/; `layout/` absent on this branch; 153 modules, 0 findings clean)
CAUGHT in every root — the cell's eight shapes (`os.environ.get`, `os.getenv`, lazy `from tools.holdout import`, lazy
`import tools.holdout.store`, `from tools import adjudicate`, `importlib.import_module("tools.holdout.store")`, `environ[...]`
three scopes deep, a docstring naming `HOLDOUT_STORE_DIR`), plus: a name in a variable passed to `os.environ.get` (the
literal is still a constant), implicit adjacent-literal concatenation (the parser folds it), `spec_from_file_location`
with a folded path literal, `subprocess.run([... "tools.adjudicate" ...])`, `getattr(os, "envi" "ron")`.
NOT SEEN (honestly): `"SEALED_" + "TRUTH_DIR"`, `"_".join([...])`, an f-string, `"sealed_truth_dir".upper()`, a reversed
literal, a base64 name, a SECOND env var carrying the store path, a pointer file named by another env var, `__import__`
/ `importlib.import_module` with a built name, a split subprocess argument, a hard-coded absolute path to `truth.jsonl`,
walking `os.environ` for keys containing `TRUTH`, `exec` of a built statement, reading the repository digest. The
firewall is a static literal/name/import tripwire; it cannot see a dynamically built name or a side channel by path.
That is the honest limit (MINOR-6); the review's own re-run of M8 against the real `discovery/runner.py` confirms the
literal case is caught.

## 5. Hash chain, manifest, CLI, digest, evaluate — attacked and could not break
Chain: editing an earlier field with its own hash recomputed → next link breaks; deleting a middle record → `seq`; swapping
two records → `seq`; a duplicated tail line → `seq`; editing `record_count` or `chain_head` in `manifest.json`, or deleting
it with records present → `verify_against_manifest` refuses; a whole-chain rewrite → the manifest refuses (A2). Only the
whole-chain rewrite that also rewrites `manifest.json` (A3) and the tail truncation followed by an append (MAJOR-1) pass.
Manifest: all 16 public start/target pairs behave exactly as the ruled matrix (the four allowed pairs allowed, the rest
refused with the state unchanged); an empty set / list / None / string dev corpus refused; a duplicate refused.
CLI: a packet directory inside the checkout refused direct, via `..`, via the junction and via `\\?\`; a sha-mismatched
PDF queued as `unavailable: pdf_sha_mismatch`; an answer with the kind omitted / blank / whitespace / the proposal
lowercased / `"None"` appends nothing (the entry stays pending); the interactive kind prompt carries no bracket and no
proposal; the packet carries no `outcome_class`; census / classifier / MoneyThumb blocks carry their EVIDENCE labels; an
`adjudicated_at` in an answer (back-dating) is refused as an unknown field; `status` prints no sha; the worktree and main
checkout `git status --porcelain` are unchanged by `queue`, `run`, `status`, `export-digest`.
Digest: the committed blob (`git cat-file -p 7173317:…/MANIFEST_DIGEST.txt`, 360 bytes, 0 CR) is byte-identical to
`render_digest(None, None)` (the working copy shows CRLF only because `core.autocrlf=true`; index `i/lf`). The grammar
rejects a `kind:` line, a status line carrying a kind or `validated`, a money shape in `record_count`, a full 64-hex
entry, a 32-hex entry, a lowercase or space-padded sha16, an empty line, a comment variant. It admits `store_version:
1000000` (an integer, harmless) and a lowercase 64-hex `chain_head` (a chain hash by construction). `parse_digest` skips
`#` lines before the grammar — irrelevant to the tool (`export_digest` always renders through the grammar; the firewall
test checks every committed line), noted for cell T's own reader. `write_digest(text)` does not validate; only
`export_digest` is reachable from the CLI.
Evaluate: validated + oracle with no figures → `not_judgeable`; validated + oracle figures + no system figures →
`not_judgeable`; validated + oracle `NOT_A_STATEMENT` / `STATEMENT_ILLEGIBLE` with no figures → `kind_conflict` (never
`false_accept`, never `agree`); burned and graduated items are absent from the details and untouched afterwards; stdout
carries no sha16 and no figure.

## 6. Ownership, production tree, commits
`git diff --name-status b23cb50...7173317`: 13 files (W3 M; 12 A: the digest file, five test files, `tools/adjudicate.py`,
`tools/holdout/{__init__,digest,evaluate,manifest,store}.py`) — every one on the card's list; `.gitignore` and
`corpus_gate.py` untouched. `git diff --stat b23cb50...7173317 -- analysis ocr discovery webapp telemetry evidence layout
corpus_gate.py` is EMPTY — the "no production module changed" claim holds. All four commits (`b68d0cf`, `38d3100`,
`aada75a`, `7173317`) carry both trailer lines.

## 7. Privacy and message scans (reviewer's run, under the host lock, log `discovery_reports/train12-logs/rev22holdout-scans.log`)
`privacy_scan_branch.py --base b23cb50 --ref 7173317` (population 3,380; 3,351 read; 29 without cached text): added
lines **4,123**; **MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0**; raw 43, all excused by `words_class` (the standing rule that
excuses the WORDS class wholesale — 18 distinct ordinary words across docs/tests/tools); every other rule 0; residue 0.
Message scan over `git log b23cb50..7173317` (4 commits): **0 / 0 / 0 / 0**. Identical to the cell's `p22holdout-finalscans-w3.log`.

## 8. Numbers re-derived vs claimed
| claim (W3 / card) | re-derived | match |
|---|---|---|
| 134 tests (43/34/19/19/19), all green | 134 passed in 6.73 s; collect counts 43/34/19/19/19 | yes |
| firewall 0 findings over 153 modules (107/20/2/9/6/9) | 153 (107/20/2/9/6/9), 0 findings | yes |
| slice-1: 214 shas, 214 packets, 0 unavailable | 214 entries all `pending`, 214 packet dirs | yes |
| queue digest `cd841c07…` | recomputed with `tools.adjudicate.queue_digest` over `queue.json`: `cd841c07…`; 214/214 packet digests recompute from `packet.json`; 1,086 page PNG shas match | yes |
| composition 117 + 51 + 16 + 30, 13 exports inside the 117 | census `cluster_group`: NOT-STATEMENT 117 (portal-export 13 ⊂), SCAN-UNCLAIMED thin 51 (of 89), PF-INVALID-PDF 16, FAM pick 30 = `random.Random(20260903).sample(sorted(FAM ∩ unresolved 322), 30)`; queue set == expected exactly | yes |
| all 214 in the run of record; 0 validated | 214 / 0 (run of record: 3,380 shas, 2,625 validated, 755 unresolved) | yes |
| sha-list digest `14540440…` | sha256 over sorted shas joined by LF, no trailing newline (MINOR-5b) | yes, recipe unstated |
| privacy 0/0/0/0 over 4,123 lines; 43 WORDS excused; message scan 0 over 4 commits | same | yes |
| mutation table 12/12 killed | 12/12, same killers | yes |
| committed digest = an empty store's | blob byte-identical to `render_digest(None, None)` | yes |
| proof floor at `38d3100`: suite 1 failed / 8,889 passed; guards 275; conformance 1,282; gate 105/3/1; corpus 34 | read from `p22holdout-floor.log` / `-proofs.log` (not re-run: heavy proofs one at a time; the tree has no production change); the one failure is the known `.env`/`PADDLE_*` host condition owned by cell K | consistent |
| cohort replay 47/47 identical, 0 regressions | `p22holdout-proofs.log` REPLAY_EXIT=0 | consistent |

## 9. Properties attacked and not broken (named)
Store location (checkout roots at both levels, junction/symlink/UNC/`\\?\`/case/8.3/`..`/trailing-char forms) · the
chain against edit / delete / swap / duplicate / manifest edit / whole-chain rewrite without manifest rewrite · the
ruled transition matrix on all sixteen public pairs · the empty-dev-corpus refusal and the run-of-record refusal with the
correct rows.csv · the CLI's no-default rule (answers and interactive) · EVIDENCE labelling · the packet directory
refusal · the sha-mismatch refusal · nothing written into either checkout · the digest grammar and the committed digest's
emptiness · the evaluate skeleton's `not_judgeable` / `kind_conflict` / burned-untouched properties · aggregates-only
stdout · ownership · the empty production diff · the two scans · the trailer lines · the twelve mutants.

## 10. Closure conditions for the MAJORs
MAJOR-1: manifest check on every read/append path + a truncation test. MAJOR-2: git-resolved annotated tag dated after
`last_evaluated_at`, tag sha recorded, `--tags-from` fenced. MAJOR-3: dev-corpus size + digest recorded in the `added`
event and a population floor. All three are contained in `tools/holdout/` + `tools/adjudicate.py` + their tests; no
production file is involved; the store is empty (record_count 0), so no existing record needs migration.
