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

## Re-review (closure tip ed618cb)

```
VERDICT: APPROVE WITH FINDINGS — 0 BLOCK / 1 MAJOR (new; pre-existing in the evaluate skeleton, not a closure regression) / 4 MINOR (new) / 2 nits
RE-REVIEWED: branch wave22-holdout at ed618cb. Ocean's note named 6752e43 as the closure tip and ed618cb as its reword;
  precisely: 6d3810d^{tree} == 6752e43^{tree} (a21d6e0…) and dd790e6^{tree} == 635853d^{tree} (64c2ebe…) — the reword is
  tree-preserving — and ed618cb is ONE docs commit on top of 6d3810d (one W3 line: the sha-remap note; `git diff 6752e43 ed618cb`
  touches only W3_TRACKA_LOG.md). The code tree reviewed here (worktree detached at 6752e43) is byte-identical to ed618cb's.
RE-REVIEWER: an independent agent (Fable 5.1) that wrote none of the code and none of the first review;
  worktree .claude/worktrees/rerev22-holdout (detached). Nothing committed, merged or pushed; the cell's branch untouched.
DATE: 2026-09-05
```

Every status below was established by the re-reviewer's own instruments (`rr_*.py` under the session scratchpad; a
synthetic store and a real temporary git repository under a short system-temp directory; the first reviewer's
`attack_*.py` re-run verbatim with only the worktree path retargeted). The cell's real store was never opened; the
private slice-1 packet directory was read only (digests recomputed, counts taken). All dates in the synthetic
fixtures are 2031+; no archive text and no run-of-record sha appears in this document.

### R1. Per-finding status

**MAJOR-1 — CLOSED, for the right reason.** Truth chain: three records, the tail removed (the reversal of a sha's
verdict). `append_record` → `ChainError: manifest.json disagrees with truth.jsonl (truncated or replaced file)`; the raw
`ChainedJsonl.append` (the MINOR-4 path) refuses the same way; `latest_by_sha` / `counts_by_kind` / `adjudicated_sha16s`
refuse; `truth.jsonl` and `manifest.json` byte-identical afterwards (the witness survives). CLI on the same store:
`run` rc 1 with **zero bytes on stdout** (refused before any packet is shown), nothing appended, the queue entry still
`pending`; `status` rc 1; `export-digest --out` rc 1 and **no file written**; `verify` rc 1; `evaluate_run` →
`ChainError`. Records present + `manifest.json` deleted → refused; `truth.jsonl` deleted + manifest present → refused.
Holdout chain (new sidecar `holdout_manifest.json`): two items, one evaluated then burned, the burn removed →
`items` / `by_sha` / `holdout_shas_for_refusal` / `sha16_statuses` / `counts_by_status` / `add` / `record_evaluation`
/ `burn` / `graduate` / raw `_emit` / `evaluate_run` all `ChainError`; CLI `holdout-list` / `status` / `verify` /
`export-digest` / `holdout-burn` / `holdout-graduate` rc 1; both files byte-identical afterwards; events present +
sidecar deleted → refused (a pre-closure store shape is refused, not migrated — the real store is empty, so nothing
needs migrating). The two chains are independent (a truncated truth chain does not block `holdout-add`; a truncated
holdout chain does not block `run`). The first reviewer's `attack_chain.py` retargeted: `E append after truncation:
refused: manifest.json disagrees…` and the script dies at E2's `append_record` with the same refusal — the laundering
is gone. Killer verified by mutant M13 (below).

**MAJOR-2 — CLOSED; two residuals recorded as NEW-2.** A real temporary repository (`git init`, `GIT_COMMITTER_DATE`
set per commit): `old-final` on a 2031 commit, `equal-final` on a commit dated exactly at the evaluation instant,
`latetag-final` (annotated in 2098, pointing at the 2031 commit), `new-final` and a lightweight `lw-final` on a 2033
commit, `notfinal` on the same commit, `future-final` on a 2099 commit, `blob-final` (an annotated tag on a blob).
Item evaluated 2032-06-01: `old-final` refused `SUBSEQUENT`; `equal-final` refused; `latetag-final` refused (the
peeled commit's committer date is used, the tagger date is not — the cell's stated conservative rule holds);
`notfinal` refused `not a freeze tag`; `absent-final` refused `not in the repository's tag list`; `blob-final` absent
from the git-resolved mapping (no commit, no date) → refused; a bare set, a list, a mapping to a non-`TagRef`, a
`TagRef` with an empty date, no `--attest`, an e-mail `attested_by` → each refused with the state still `evaluated`;
`new-final` → graduated with `tag_commit` = the 2033 commit and its date; `lw-final` → graduated (a lightweight tag of
the shape counts; the date is the commit's). Real checkout: `freeze_tags_from_git` resolves `batch8/9-final`,
`phase2.0/2.1-final`; `batch9-final` (dated 2026) against a 2032 evaluation → refused `SUBSEQUENT`. CLI: `--tags-from`
→ argparse rc 2; `git_tags()` no longer exists; the default `--repo` (this checkout) refuses `new-final`; `--repo` at a
plain directory → empty mapping → rc 1 (fail closed); `--repo <temp repo> --tag new-final` → rc 0, graduated, the
attestation names the commit. Killers verified by M14 / M15 / M16 / M6.

**MAJOR-3 — CLOSED; one API residual under NEW-4.** `--dev-shas` → argparse rc 2 (the flag does not exist);
`--dev-rows` absent → rc 2 (required); a run-of-record sha with `--dev-rows <run of record>` → rc 1, 0 items (the same
sha lowercased → rc 1); a synthetic sha → rc 0 and the `added` event carries `dev_corpus = {digest, size 3380, rows
3506, source <run dir>/rows.csv, recipe}`; the digest recomputed independently (sha256 over the sorted distinct upper
shas joined by LF, no trailing newline) equals the recorded one; stdout names no sha. Fresh inputs: a `rows.csv` with
a duplicated sha, a lowercase copy and a blank cell → size 3 distinct / rows 6, digest over the 3; a malformed sha →
refused at the API and rc 1 at the CLI; no `content_sha256` column → rc 1; an absent file → rc 1; a set / list /
`None` / string as `dev_corpus` → refused. A ONE-row `rows.csv` is accepted and recorded as size 1 — the reviewer's
population floor was not adopted (the cell's Deviation 4; the recorded size makes it auditable, it does not prevent
it). Killers verified by M7 / M17.

**MINOR-1 — CLOSED.** With `--max-pages 2` over a 2-page and a 3-page synthetic PDF: (a) an edited `EVIDENCE.txt`
is never shown (the evidence is rendered from `packet.json`), the record's `packet_digest` == recomputed == the
queue's; (b) an edited `packet.json` evidence value → `packet digest mismatch`, nothing appended, entry pending; (c)
an edited `page-001.png` → refused; (d) `queue.json`'s digest set to `ff…` → refused, no record carries it; (e)
`packet.json`'s own `packet_digest` field edited → refused; (f) `content_sha256` swapped inside `packet.json` →
refused; (g) an extra page file not named by `packet.json` → no effect; (h) a traversal name (`../../x.png`) in
`pages` → `packet unreadable`, nothing appended. Killer verified by M18. Nit NEW-5 (header decorations outside the
digest).

**MINOR-2 — CLOSED.** Refused: the checkout's parent (the project folder), a sibling under it, a sibling whose name
prefixes the checkout's, the worktree's parent, `Desktop`, `C:\`, `C:\Users` and the user profile (true ancestors),
the `OneDrive` environment root, a OneDrive path far from the checkout, a lowercase `onedrive_local` component, an
`OneDriveTemp` component, a root named ONLY by an `OneDriveRR` variable (accepted again once the variable is gone),
and the CLI packet directory under the OneDrive root / the checkout's parent (rc 1, nothing created). Accepted, by
design: Local AppData, the system temp directory, `ProgramData`, a `NotOneDrive` component, and local unsynced
directories that sit under an ancestor without being one (`C:\sealed`, `C:\Users\<profile>\sealed`). The first
reviewer's `attack_location.py` / `attack_location2.py` retargeted: every previously-refused form still refused
(junction, symlink, `\\?\`, UNC, case, 8.3, `..`, trailing dot/space, NUL); the three formerly-accepted MINOR-2 paths
now refused. Killer verified by M19. Note: on this host every path under the checkout is refused first by the
OneDrive component rule, so M1 is killed only through the new ancestor rule (the cell says so); on a non-synced host
the parent rule subsumes the checkout-root rule, so the property is pinned everywhere.

**MINOR-3 — CLOSED for (a), (b), (c); a sibling defect of (a) found and ranked NEW-1.** (a) `closing_balance: n/a`
→ listed under `unparseable`, contradictions empty, never `false_accept`; a date export in a non-ISO shape → both
period fields `unparseable`, no contradiction. (b) `account_count` alone → `agree_partial`; opening + closing + one
ledger row → `agree` with `money_compared 3`; nothing comparable → `not_judgeable`. (c) a system `refused` row vs a
complete oracle → `false_refusal` / `unclassified` (documented, not mapped — cell T's vocabulary). Killers verified
by M20 / M21.

**MINOR-4 — CLOSED as documented convention** (the W3 records why no signing is built and what the chain, the
sidecars and the digest make detectable). Re-confirmed: the raw chain writer and `record_evaluation` remain callable
from any process that knows the path; the closure adds two more API-only shapes (NEW-4) that belong to the same class.

**MINOR-5 — CLOSED.** (a) `queue` prints and writes `truncated: N (page cap M)` (verified: `truncated: 1 (page cap
2)` in stdout and `QUEUE_DIGEST.txt`; `packet.json` `render.truncated: true`, 2 rendered of 3; `EVIDENCE.txt` says
`(cut at the 2-page cap)`). Against the REAL slice-1 queue (read-only): 214 entries, 214/214 packet digests recompute
with the closure code to `queue.json`'s and `packet.json`'s (the digest recipe did not change: `packet_content` is
the old inline dict factored out), exactly 3 packets cut at the 40-page cap with page counts 42 / 43 / 43, 1,086 page
images, `evidence_text` renders for all 214 — the closure's `run` accepts the pre-closure queue as it stands. The
queue on disk was NOT rebuilt at the closure (its `QUEUE_DIGEST.txt` carries no `truncated:` line; queue digest
unchanged), which is consistent with the W3. (b) the sha-list digest recipe is stated; the dev-corpus recipe is in
the record itself.

**MINOR-6 — CLOSED.** The docstring names the tripwire's class and its limits; the first reviewer's
`attack_firewall.py` retargeted: the cell's 8 shapes caught in all 6 roots; of the 20 indirect shapes **14 caught**
(was 5): `+`-concatenation, `join`, adjacent literals, a name passed through a helper, `.upper()`, a reversed slice,
a pointer-file variable named `TRUTH_POINTER_FILE`, a second variable `SEALED_TRUTH_PATH`, `__import__` /
`importlib` / `spec_from_file_location` with folded names, a split `subprocess` argument, `getattr(os, "envi" "ron")`.
Still NOT SEEN, every one inside the docstring's stated limits and pinned as such by
`test_the_firewall_names_its_limits_truthfully`: an f-string with a VARIABLE part, a base64 name, a hard-coded
absolute path, a walk over `os.environ`, `exec` of a string whose content is not folded, and reading the repository
digest (allowed by design — cell T reads it). 153 production modules, 0 findings.

### R2. New findings from the closure (ranked)

**NEW-1 (MAJOR; pre-existing in `tools/holdout/evaluate.py`, exposed by attacking the closure's `compare_figures` /
`load_ledger`; not a regression).** Money is compared as canonical STRINGS that preserve decimal scale
(`format(Decimal(x), "f")`): oracle `100` vs export `100.00` → `opening_balance` contradiction; oracle `0.00` vs
export `-0.00` → contradiction; a ledger amount carrying one more decimal than the sampled row → `sampled_row_absent`.
Each yields **`false_accept`** — the STOP-condition-shaped number — from formatting alone, silently (unlike `n/a`,
which is now listed). `Decimal("100") == Decimal("100.00")` is true; the code never compares the values. The store's
own `_money_or_none` keeps the typed scale, so an adjudicator typing `100` against any two-decimal export will fire
this on the first real evaluation. Fix (small, inside the cell's ownership): compare `Decimal` values numerically in
`compare_figures`; build the ledger key from a normalised decimal (and map negative zero to zero); pin with a test in
`test_holdout_evaluate.py` whose fixture mixes scales. Non-blocking for composition because no real evaluation has
run (the first is 2.4's); it must be closed before one does.

**NEW-2 (MINOR).** `holdout-graduate --repo` is a caller-chosen repository: a fabricated repository carrying a
`*-final` tag on a commit with a future committer date (dates are self-reported to git) graduates an item, and the
attestation records `tag_commit` / `tag_committer_date` but not WHICH repository was consulted. The recorded commit is
the only audit hook (a fabricated commit does not exist in the real repository — detectable, not prevented). Suggest
recording the consulted repository's identity (its root commit) in the attestation, or fencing `--repo` to tests.

**NEW-3 (MINOR).** `TruthStore.write_manifest()` is a public, unguarded re-seal: it verifies the CHAIN only and
rewrites `manifest.json` from whatever the file holds. On a tail-truncated store, one call makes `latest_by_sha` and
`append_record` succeed again — the module itself offers the launder the sidecar was built to refuse. It is the same
class as hand-editing `manifest.json` (A3; only `verify --digest` sees it) and has no caller in `tools/` or `tests/`.
Suggest removing it from `TruthStore`'s public surface (the chain writes its own sidecar) or making it refuse when an
existing manifest disagrees.

**NEW-4 (MINOR, API-only; MINOR-4 class).** (a) `HoldoutManifest.add` accepts a hand-built `DevCorpus` with a forged
digest — `dev_corpus_from_rows` is the CLI's convention, not the manifest's check; (b) `record_evaluation` accepts any
UTC `evaluated_at`, so an API caller can back-date an evaluation before an old freeze and graduate at it (the CLI has
no such command). Recorded so neither is mistaken for enforcement.

**NEW-5 (nit).** `packet.json`'s `sha16`, `max_pages`, `dpi` and `relative_path` are shown in the evidence header but
lie outside the digest; the content sha and everything substantive are verified, so only decoration is forgeable.

**NEW-6 (nit / observation).** Concurrent append: the wide race (B holds a stale read, A's append AND manifest landed)
is now REFUSED outright by the sidecar check — better than the W3's "detected, not prevented"; the narrow window (A's
line landed, A's manifest not yet) still produces a duplicate `seq` and a permanently refusing chain until repaired
by hand. Detected in every interleaving, prevented in the common one; single-writer operation remains the ruled use.

Also verified: a hand-rewritten `manifest.json` matching a truncated file passes `verify` (the sidecar cannot see
it) and is caught by `verify --digest <fresh export>` on `record_count`, `chain_head`, `adjudicated_sha16`; the
COMMITTED digest (an empty store's, unchanged since 7173317) anchors nothing for a populated store until an export
is committed — the cell's stated risk, restated. The PF-INVALID census finding reproduced read-only by count: the 16
census `PF-INVALID-PDF` documents are all `valid_pdf = False` in the run of record, all begin with the four-byte
serialisation magic and all carry `%PDF-` at byte offset 27.

### R3. Mutation table re-run (all 21 at the closure tip, detached worktree, WITHOUT -x; `rr_mutate21.py`, log `discovery_reports/train12-logs/rerev22holdout-mutation-table.log`; restored with `git checkout --` in a `finally`; tree clean after)
Every mutant re-derived from the closure log's row description and applied to the closure-tip source (sites re-located
where the closure moved them); each run is the five cell test files (165). **21 / 21 KILLED**; killers identical to the
cell's table in every row.
| # | mutant (as applied here) | result | killers |
|---|---|---|---|
| M1 | the repository-root / ancestor / parent / `.git` block of `forbidden_ancestor` removed | KILLED 1 / 164 | `test_truth_store.py::test_refuses_the_checkout_parent_its_siblings_and_every_ancestor` |
| M2 | `record_hash` excludes `prev` | KILLED 1 / 164 | `::test_each_record_hash_covers_every_field_but_hash` |
| M3 | `verify` skips the first record | KILLED 3 / 162 | `::test_a_rewritten_earlier_record_is_detected`, `::test_a_first_record_whose_prev_is_not_genesis_is_refused`, `test_holdout_manifest.py::test_the_holdout_file_is_a_hash_chain_of_events` |
| M4 | `run` fills an empty kind from the packet's classifier proposal (answers + interactive) | KILLED 2 / 163 | `test_adjudicate_cli.py::test_run_never_prefills_the_kind_from_the_proposal`, `::test_run_interactive_asks_the_kind_with_no_default` |
| M5 | `("unseen","graduated")` added; the evaluation precondition dropped; the date check tolerates a missing evaluation | KILLED 2 / 163 | `test_holdout_manifest.py::test_every_other_transition_refuses[path1]`, `::test_the_transition_matrix_is_exactly_the_ruled_one` |
| M6 | the tag-list membership check removed; an absent tag fabricated as a 2099 ref | KILLED 3 / 162 | `::test_graduation_requires_an_existing_freeze_tag_and_the_attestation`, `test_adjudicate_cli.py::test_holdout_graduate_resolves_the_tag_through_a_real_git_repository`, `::test_holdout_graduate_has_no_self_attested_tag_list` |
| M7 | the development-corpus refusal removed | KILLED 2 / 163 | `test_holdout_manifest.py::test_a_development_corpus_sha_is_refused`, `test_adjudicate_cli.py::test_holdout_add_refuses_a_run_of_record_sha_and_accepts_a_new_one` |
| M8 | `os.environ.get("SEALED_TRUTH_DIR")` appended to the REAL `discovery/runner.py` | KILLED 19 / 146 | `test_truth_firewall.py::test_no_production_module_references_the_store` + the 18 scratch-mutant cases' clean-source precondition + `::test_a_clean_scratch_copy_produces_no_finding` |
| M9 | a `kind:` line per adjudicated document rendered AND admitted by the grammar | KILLED 3 / 162 | `test_truth_firewall.py::test_a_digest_rendered_from_a_populated_store_is_non_sensitive`, `::test_the_digest_grammar_rejects_a_verdict_line`, `test_adjudicate_cli.py::test_export_digest_writes_the_non_sensitive_digest` |
| M10 | the sampled-row description stored as text beside its hash | KILLED 2 / 163 | `test_truth_store.py::test_sampled_row_descriptions_are_stored_as_hashes_never_text`, `test_adjudicate_cli.py::test_run_with_answers_appends_records_with_the_packet_digest` |
| M11 | `evaluate_run` emits `evaluated` through `_emit` without an engine version | KILLED 2 / 163 | `test_holdout_evaluate.py::test_items_compared_are_marked_evaluated_with_the_engine_version`, `::test_a_second_evaluation_records_the_new_engine_version` |
| M12 | every validated item a FALSE ACCEPT | KILLED 7 / 158 | the five evaluate tests of the cell's table + `::test_an_unparseable_system_figure_is_never_a_contradiction`, `::test_agree_requires_a_money_identity` |
| M13 | both pre-append manifest verifications (`ChainedJsonl.append`, `TruthStore.append_record`) replaced by chain-only verification | KILLED 2 / 163 | `test_truth_store.py::test_a_tail_truncation_is_never_resealed_by_the_next_append`, `::test_records_without_a_manifest_are_refused` |
| M14 | the freeze-tag shape check removed | KILLED 2 / 163 | `test_holdout_manifest.py::test_graduation_requires_the_freeze_tag_shape`, `test_adjudicate_cli.py::test_holdout_graduate_resolves_the_tag_through_a_real_git_repository` |
| M15 | the tag-existence check removed (absent tag fabricated as a far-future ref) — the same site as M6 | KILLED 3 / 162 | the three M6 killers |
| M16 | the subsequent-freeze date ordering removed | KILLED 2 / 163 | `test_holdout_manifest.py::test_graduation_requires_a_subsequent_freeze`, `test_adjudicate_cli.py::test_holdout_graduate_refuses_a_freeze_older_than_the_evaluation` |
| M17 | the `added` event records only the dev corpus' source (no digest / size / rows) | KILLED 2 / 163 | `test_holdout_manifest.py::test_the_dev_corpus_comes_from_a_rows_csv_and_is_recorded`, `test_adjudicate_cli.py::test_holdout_add_refuses_a_run_of_record_sha_and_accepts_a_new_one` |
| M18 | `run` takes `queue.json`'s digest and skips the mismatch check | KILLED 1 / 164 | `test_adjudicate_cli.py::test_run_recomputes_the_packet_digest_and_refuses_an_edited_packet` |
| M19 | the OneDrive-component, ancestor / parent and OneDrive-root refusals removed | KILLED 4 / 161 | `test_truth_store.py::test_refuses_the_checkout_parent_its_siblings_and_every_ancestor`, `::test_refuses_a_onedrive_root_named_by_the_environment`, `::test_refuses_a_path_with_a_onedrive_component`, `::test_the_checkouts_own_onedrive_ancestry_is_a_refused_root` |
| M20 | an unparseable figure appended to `contradictions` | KILLED 5 / 160 | `test_holdout_evaluate.py::test_an_unparseable_system_figure_is_never_a_contradiction`, `::test_the_synthetic_evaluation_reports_each_judgement`, `::test_stdout_carries_aggregates_only`, `::test_the_private_report_is_written_outside`, `::test_cli_entry_point_requires_the_store_and_prints_aggregates` |
| M21 | `agree` granted on `compared > 0` alone | KILLED 5 / 160 | `::test_agree_requires_a_money_identity`, `::test_false_accept_needs_an_oracle_contradiction_never_the_verdict_alone`, `::test_an_unparseable_system_figure_is_never_a_contradiction`, `::test_the_synthetic_evaluation_reports_each_judgement`, `::test_stdout_carries_aggregates_only` |
Notes: M6 and M15 are one site (the cell's table lists both; both kill). On this host M1 dies only through the new
ancestor rule (the OneDrive component rule refuses every path under the checkout first); removing only the
checkout-root check would be an equivalent mutant everywhere, because the parent rule subsumes it. No mutant exists for
NEW-1 (the scale comparison) — the evaluate fixtures never mix decimal scales.

### R4. Scans (re-reviewer's run under the host lock; log `discovery_reports/train12-logs/rerev22holdout-scans.log`, JSON `rerev22holdout-privacy.json`)
`privacy_scan_branch.py --base b23cb50 --ref ed618cb` (population 3,380; 3,351 read; 29 without cached text): added lines
**5,212**; **MONEY 0 / DIGITS 0 / DATES 0 / WORDS 0**; raw 56, all excused by `words_class`; every other rule 0;
residue sites 0 / files 0. Message scan over `git log b23cb50..ed618cb` (**7 commits**): **MONEY 0 / DIGITS 0 / DATES 0 /
WORDS 0**. The cell's earlier single WORDS hit was the two-word English sequence `otherwise agree` in the closure fix
commit's own body (its MINOR-3 line) — the cell's prose, not the co-authorship trailer; the reword to "without one the
judgement is agree_partial" (`635853d` → `dd790e6`, tree-preserving) removed it, and the trailer lines are untouched.

### R5. Proof exits, ownership, trailers
`p22holdout-closure-proofs.log` (tree `635853d`, `PRODDIFF_LINES=0`): `CELLTESTS_EXIT=0` (165 passed) · `GUARDS_EXIT=0`
(275) · `CONFORMANCE_EXIT=0` (1,282 / 41 skipped) · `WALKERS_EXIT=0` (358 / 3 / 10 deselected) · `REPLAY_EXIT=0` ·
`PRIVACY_EXIT=0` · `MSGSCAN_EXIT=1` (the one WORDS hit, attributed above) · `EXIT=0`; `p22holdout-closure-chain.log`
`EXIT=0`; `p22holdout-closure-mutation-table.log` `EXIT=0` (21/21); `p22holdout-closure-finalscans.log` (tree
`6752e43`) `PRIVACY_EXIT=0` over 5,211 lines, `MSGSCAN_EXIT=1` (6 commits, WORDS 1), `EXIT=0`. Re-derived here: the five
cell test files **165 passed** at the tip; firewall 153 modules / 0 findings. `git diff --stat b23cb50...ed618cb`: 13
files, every one on the card's list (the W3, the digest file, five tests, `tools/adjudicate.py`, five `tools/holdout/`
files); `.gitignore` and `corpus_gate.py` untouched; the diff over `analysis ocr discovery webapp telemetry evidence
layout corpus_gate.py` is EMPTY. Closure diff `7173317...ed618cb`: 11 files, all owned. All seven commits, including
the three rewritten / added ones (`dd790e6`, `6d3810d`, `ed618cb`), carry both trailer lines.

### R6. Overall
The closure introduced nothing that breaks a ruled property: the store is still outside every checkout (now also
outside every synced root), the chains refuse what they could not see before, graduation is git-resolved and ordered,
the attestation is auditable, no production module changed, the digest is still an empty store's. NEW-1 is the one
item that must close before the evaluate skeleton is used for a real evaluation; NEW-2 and NEW-3 are small and inside
the cell's ownership.
