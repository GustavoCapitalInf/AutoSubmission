# Phase 3 ceiling harness — independent adversarial review (reviewer X)

**VERDICT: BLOCK**

Scope of the block: the synthetic preflight (`vlm_ceiling preflight`, `--data-scope synthetic` over
`preflight-*/synthetic-archive`) may proceed as written. **No CTRL or U755 wave may run** until
BLOCK-1, BLOCK-2 and BLOCK-3 are closed, and the go/revise/stop numbers of plan §11 must not be
computed from this gate until MAJOR-1…MAJOR-4 are closed: as it stands the gate admits a statement on
the strength of the proposal's own arithmetic, so "residue statements fully reconciled" — the number
the GO threshold is defined on — is not the number this harness measures.

Reviewed: `git diff 76fee9e..HEAD` (b732c55, 5565f6d, bfaff31) — `vlm/` (16 modules),
`tools/vlm_ceiling.py`, `tools/vlm_vast.py`, `tests/test_vlm_*.py`, the four part-plans and
`LICENSES.md`. Read against part-1 Global Constraints, PHASE2_RULINGS R16 + the Paddle customer-data
authorization, plan v1 §4/§11, and the reference boundary (`ocr/paddle_config.py`,
`ocr/paddle_client.py`, `ocr/paddle_worker.py`, `tools/paddle_vast.py`, `discovery/runner.py`,
`tests/test_truth_firewall.py`).

Tests added by this review: `tests/test_vlm_review_findings.py` — 15 counterexamples, all passing
(`python -m pytest tests/test_vlm_review_findings.py -q -p no:cacheprovider` → `15 passed`). They are
**characterisation** tests: each asserts today's behaviour so the defect is reproducible and pinned,
and each docstring names the finding id and the assertion to INVERT when the fix lands. The whole
`tests/test_vlm_*.py` set plus `tests/test_truth_firewall.py` is green with them: `134 passed`.
No non-test source file was modified. No customer document was opened.

---

## BLOCK

### BLOCK-1 — extracted account digits reach the PUBLIC receipt
`vlm/proposals.py:94` → `vlm/runner.py:206`

`merge_pages` returns `stats["account_last4_values"]`, the last four digits of the account number as
read off the page, and `process_document` copies `stats` verbatim into the public half of the receipt
(`results/<SHA>.json`) for the `stage_b_only` and `hybrid` arms.

Reproduction (`test_public_receipt_carries_the_extracted_account_last4`): a page proposal with
`account.account_number_last4 = "4821"` yields `stats == {..., "account_last4_values": ["4821"], ...}`,
and `runner.py:206` writes that dict into the non-private receipt. The existing
`tests/test_vlm_proposals.py::test_merge_pages_roles_meta_and_conflicts` pins this value, so it is not
an accident of one path.

This is the constraint the part-1 plan states first — "no customer bytes, paths, names or extracted
contents in any public receipt … Public receipts carry counts, hashes, closed status codes and path
bindings" — and R1's "sensitive extracted contents are never committed". `discovery_reports/` being
gitignored limits the blast radius; it does not make the receipt public-safe, which is the whole point
of the public/private split.

**Fix:** keep only a count and a digest in `stats` — `{"account_last4_count": len(last4s),
"account_last4_set_sha256": sha256(canonical_json(sorted(last4s)))}` — and move the values to the
private receipt. While there, audit the same path for `meta`: `vlm/runner.py:209` correctly sends
`meta` (which carries `account_last4` and `bank`) to the private receipt only; keep it that way.

### BLOCK-2 — nothing makes the declared execution class checkable, so both opt-ins are bypassable
`vlm/runner.py:54-57`, `vlm/client.py:115-177`, `vlm/stage_a_worker.py:118-131`, `vlm/runner.py:217-223`

`default_authorize` is `check_remote_authorization(load_paddle_settings(), data_scope)`. That function
returns immediately when `settings.is_remote` is False (`ocr/paddle_config.py`, `if not
settings.is_remote: return`) — **neither opt-in literal is required for a `local`/`local_free`
declaration**. Every VLM endpoint is `http://127.0.0.1:1800x`, which is the local end of the SSH tunnel
to the rented RTX 5090. So `PADDLE_PROVIDER=local PADDLE_EXECUTION_CLASS=local_free` sends customer
pages to the rented GPU with no opt-in at all, and the receipt records the run as local and free.

This is exactly the D2 hazard `ocr/paddle_config.py` was written against ("a URL-based classification
would call a Vast.ai GPU local"), and the Paddle path closes it on the *other* side: the worker echoes
its own `PADDLE_PROVIDER`/`PADDLE_EXECUTION_CLASS` on `/version`, and
`ocr.paddle_client.verify_identity` refuses `paddle_runtime_mismatch` unless the echo matches the
client's declaration — "before a single image byte is sent" (`ocr/paddle_client.py:320-350`,
called at `ocr/paddle_rung.py:160`).

The VLM harness ships the declaration half and drops the checkable half:

* `vlm/stage_a_worker.py::version_payload` carries `contract`, `pipeline_version`,
  `served_model_name`, `backend`, `retention`, `predict_kwargs` — and no `provider` /
  `execution_class`.
* Neither `vlm/client.py` nor `vlm/runner.py` mentions `verify_identity` or `execution_class`;
  `_model_identity` stores `stage_a.version()` and `stage_b.models()` without comparing anything.
* Stage B is a bare vLLM OpenAI endpoint, which cannot echo anything, so it has no attestation at all.

Reproduction: `test_no_worker_identity_echo_exists_for_the_vlm_path` asserts the absent keys and the
absent call sites.

**Fix:** (a) add `provider`/`execution_class` to `version_payload` from the worker's own environment
(`tools/vlm_vast.cmd_start` must then export `PADDLE_PROVIDER`/`PADDLE_EXECUTION_CLASS` the way
`tools/paddle_vast._env_prefix:188-193` already does), and refuse in `run_wave` unless the echo equals
the local declaration, before the first page; (b) for Stage B, which cannot echo, bind the
`vlm_vast attest`/`check` receipt (which *does* carry `provider`/`execution_class`, `tools/vlm_vast.py:80`)
into `launch.json` via `receipts.bound`, and refuse when the bound receipt declares anything other than
what `load_paddle_settings()` declares; (c) belt and braces — refuse any wave whose endpoint is a
tunnel local port while the declaration says `local_free`, i.e. make the tunnel's own presence
(`_port_listening(PORTS[...])` plus a live `vlm_tunnel.pid`) contradict a `local` declaration.

### BLOCK-3 — `--data-scope` is an unbound operator declaration
`tools/vlm_ceiling.py:102` → `vlm/runner.py:243`

The scope handed to the authorization gate is a free CLI string with no relationship to the manifest
being run. `--data-scope synthetic` over `CTRL.manifest.private.json` sends real customer pages after
only `PADDLE_REMOTE_OPT_IN`, skipping `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` entirely, and writes
`"data_scope": "synthetic"` into `launch.json` and `result.json` — a receipt that falsely states no
customer data moved.

Reproduction (`test_cli_data_scope_is_an_unbound_operator_declaration`): a manifest named `CTRL` runs
with `--data-scope synthetic`; the recorded scope is `["synthetic"]` and `launch.json` agrees.

`ocr/paddle_config.check_remote_authorization`'s docstring is explicit that it "does NOT verify that
`data_scope` truthfully describes the bytes being sent — that remains a declaration the caller makes",
and that in the discovery runner the literal `data_scope="customer"` is pinned by that cell's tests.
Here nothing pins it. The default is `customer` (right direction), but a single flag defeats it.

**Fix:** put `data_scope` in the manifest. `partitions.build_manifest` stamps
`"data_scope": "customer"` for every manifest built from a population file, and only the preflight
synthesiser stamps `"synthetic"`; `_run` reads it from the manifest and refuses (closed code
`data_scope_disagrees_with_manifest`) if the flag disagrees. Then have `run_wave` re-assert it per
document — cheap, and it turns a wave-level declaration into a per-document one, which is what R1's
"the customer-data opt-in stays explicit per run" is trying to buy.

---

## MAJOR

### MAJOR-1 — self-derived anchors turn the gate into a self-consistency check
`vlm/gate.py:78-83`

When `meta.beginning_balance` is absent the gate derives it from the *first proposed row*, and when
`meta.ending_balance` is absent it derives it from the *last proposed row*. With both derived,
`reconcile`'s sum check becomes `first.balance − a₁ + Σaᵢ == last.balance`, which is algebraically the
same statement as its own continuity check — so a proposal is admitted for being internally consistent,
against no printed fact at all.

Reproduction (`test_gate_admits_a_truncated_statement_when_both_anchors_are_derived`): a six-row
statement and **its own first three rows** are *both* admitted with zero reasons, reporting ending
balances of `710.00` and `560.00`. A model that reads the first page and stops is counted as a
reconciled statement. `tests/test_vlm_gate.py::test_missing_balances_are_derived_from_chain` pins this
as intended behaviour, so this is a design decision to revisit, not a slip.

Consequence for the experiment: "coverage on the residue (statements fully reconciled)" and the
≥ 40 % GO threshold are measured on a check a truncated read passes. The residue is precisely the
population where the printed anchors are hardest to read, i.e. where derivation fires most.

**Fix:** derivation must not be able to supply *both* anchors. Require at least one printed anchor
(`meta`) and derive at most the other; when an anchor is derived, emit a distinct non-admitted status
(e.g. `admitted_unanchored`) that the report counts separately from `admitted`, and surface
`gate.derived` in `report.build_report` (it is written per document at `vlm/runner.py:205` and then
never aggregated). See MAJOR-4 for the anchor that should replace derivation.

### MAJOR-2 — the duplicate check is disabled exactly where it is the only check
`vlm/gate.py:102-110`

`for row in resolved: if row.balance is None: continue` — so on a statement that prints no running
balances the duplicate scan examines nothing. A model that emits one row twice and misses another row
of the same amount and direction reconciles to the cent and is admitted, with no continuity chain to
contradict it.

Reproduction (`test_duplicate_row_masking_a_missing_row_is_admitted_when_no_balances_are_printed`):
beginning `1000.00`, ending `800.00`, no balances; truth is `RENT −100` + `INSURANCE −100`; the model
emits `RENT −100` twice. Admitted, `duplicate_row` absent, and the admitted rows are
`["RENT 05", "RENT 05"]`. This is a **false accept of row content** — the class §11 puts at zero for
the GO threshold — and the harness has no way to see it (see MAJOR-3 for why the report cannot see it
either).

**Fix:** the balance-`None` skip exists to tolerate genuinely identical printed rows; replace it with
evidence rather than silence. Either (a) key the duplicate scan on
`(date, description, amount, direction, locator-adjacency)` and refuse a repeat that is not adjacent in
printed order, or (b) gate it on the printed per-direction counts from MAJOR-4 — a duplicate that
keeps the count right is a real pair, one that breaks it is a defect. In either case a repeat that
cannot be verified must be a reason code, not an admission; fail closed is the §4.7 invariant.

### MAJOR-3 — the report cannot answer the §11 threshold question
`vlm/report.py:29-87`

The GO/REVISE/STOP thresholds are defined on "no false accepts" and "row-level exact match … on
validated pages". `build_report` sums `match.{matched,missing,extra}` across all documents and computes
a global `match_rate`, but it **never joins admission with contradiction**: there is no per-document or
aggregate figure for "admitted AND `match.missing > 0` or `match.extra > 0`", which is the definition of
a false accept against reader truth. It also never aggregates `gate.derived` (MAJOR-1) and never splits
CTRL from the DEV slice that prompt design used (MINOR-6). `chain_derived_directions` is summed but
carries no threshold.

**Fix:** add `false_accepts` (admitted documents whose `match` shows any missing or extra row, listed
by SHA only), `admitted_with_derived_anchors`, `admitted_with_chain_directions`, and a
`row_exact_match_rate` restricted to `reader_outcome == "validated"` documents. Until those exist, the
report cannot be the §11 deliverable.

### MAJOR-4 — the gate throws away the bank's own printed totals and counts
`vlm/schema.py:40-55`, `vlm/gate.py:55-66`

`analysis.reconcile` already implements the two checks that would catch MAJOR-1 *and* MAJOR-2 without
new arithmetic: the bank-stated summary identity (`summary_ok`, `analysis/reconcile.py:159-181`) and
per-direction count coverage (`stated_credit_count_matches` / `stated_debit_count_matches`,
`:266-288`), plus credit/debit coverage ratios. The page schema never asks the model for
`stated_total_credits`, `stated_total_debits` or the printed credit/debit counts, so `statement_from`
leaves all four `None` and all of those checks are skipped on every document the harness will ever run.

Reproduction (`test_the_gate_never_gives_reconcile_the_banks_own_printed_totals_or_counts`):
`reconcile(statement_from(rows, meta)).summary_ok is None` and both count-match fields are `None`.

A truncated read (MAJOR-1) fails debit/credit coverage against the printed totals. A duplicate masking
a missing row (MAJOR-2) keeps the totals right but breaks the printed *count* — which is why
`reconcile` counts rows by the column they were printed in and not by sign. The reader's strongest
independent anchors are sitting unused.

**Fix:** add `stated_total_credits`, `stated_total_debits`, `stated_credit_count`,
`stated_debit_count` (and optionally `stated_service_charge`, `stated_interest_paid`) as nullable
fields to `_ACCOUNT`, ask for them in the Stage B prompt as printed-only values, extract them by rule
in `vlm/metadata.py` for the Stage A arm, pass them into `Statement`, and make a present-but-failing
`summary_ok` or count mismatch a gate reason. This is the single highest-value change in the review and
it subsumes most of MAJOR-1 and MAJOR-2. `SCHEMA_VERSION` and `PROMPT_VERSION` both move.

### MAJOR-5 — resume skips documents that only have a FAILURE receipt
`vlm/runner.py:247-248`

`existing = {p.name[:-5] for p in (resume_from/"results").glob("*.json") …}` treats any receipt as
done, including the failure receipts that `_failure_receipt` writes for transport failures, unreadable
documents and unexpected exceptions. The three transport failures that trigger the abort at
`:298-300` are therefore skipped forever by the resume wave that exists to pick them up.

Reproduction (`test_resume_skips_documents_that_only_have_a_FAILURE_receipt`): wave 1 aborts with
`failed: 3`; the resume wave reports `skipped_existing: 3` and retries none of them.

**Fix:** read each receipt and skip only those with `failure is None` (and, if you want resume to be
idempotent on gate refusals too, only those that also carry a `gate` block).

### MAJOR-6 — an interrupted wave is receipted as `complete`
`vlm/runner.py:276`, `:315-321`

`status` starts as `"complete"` and is only ever changed by the transport abort. Any `BaseException`
(Ctrl-C, a `SystemExit`, an `OSError` while writing the private receipt at `:307`, which is outside the
per-document `try`) unwinds through the loop to the `finally`, which writes `result.json` with
`"status": "complete"`, `"controller_exit": 0` and a truncated `counts`. A partial wave then looks
complete to `report.build_report`, whose `admission_rate` divides by that truncated `attempted`.

Reproduction (`test_interrupted_wave_is_receipted_as_complete`): a Stage A that raises
`KeyboardInterrupt` leaves `result.json` with `status: "complete"`, `attempted: 1` of 2, and
`release.json` with `controller_exit: 0`.

**Fix:** set `status = "aborted"` in an `except BaseException:` that re-raises, or (cleaner) set a
`finished = True` flag after the `while` loop and have the `finally` write
`status = "complete" if finished else "aborted"`.

### MAJOR-7 — weights and the hybrid prompt are not pinned by hash in the receipt
`vlm/runner.py:250-253`

Plan §4.10: "weights, prompts, schemas and gate versions are pinned by hash in every receipt";
§11 deliverables: "the pinned versions and weight hashes".

* `launch.json`'s `models` block records the served model *name*, `stage_a.version()` and the list of
  `models()` the server advertises — **no weight hash**, although `tools/vlm_vast.cmd_fetch:97-110`
  already computes and receipts `sha256sum config.json *.safetensors` and writes it to
  `discovery_reports/train13-logs/p3ceiling/fetch-<key>-<stamp>.json`. Nothing binds that receipt to the
  wave, so a wave cannot prove which weights served it.
* `prompt.sha256` hashes `stage_b_prompt(page_number=1, page_total=1)` — a formatted 1-of-1 instance
  that is **not** the text the hybrid arm sends, because `HYBRID_PREFIX` is absent from it.

Reproduction (`test_launch_receipt_pins_neither_the_weight_hashes_nor_the_hybrid_prompt`).

**Fix:** bind the fetch receipt with `receipts.bound(...)` into `launch.json["models"]`, and hash the
prompt *templates* (`STAGE_A_TABLE_PROMPT`, `STAGE_A_SPOTTING_PROMPT`, `STAGE_B_PROMPT`,
`HYBRID_PREFIX`) plus `PROMPT_VERSION`, not a formatted instance.

### MAJOR-8 — `continues_previous` silently discards a real amount, and the drop is not counted
`vlm/proposals.py:39-41`, `:90-91`

A row with a positive amount that the model *also* marked `continues_previous` is folded into the
description of the row above and its amount is dropped. `rows_dropped_nonpositive` stays `0` because
`:90-91` counts the row as a continuation, so the receipt records no loss. Combined with MAJOR-1, the
shortened ledger then reconciles against its own remaining chain and is **admitted**.

Reproduction (`test_continues_previous_discards_a_real_amount_and_the_drop_is_not_counted`): two
proposed rows (`+10.00` bal `510.00`, `+50.00` bal `560.00`, the second flagged
`continues_previous`) produce one candidate row, `rows_dropped_nonpositive == 0`, and
`gate(...).admitted is True` with `computed_ending == 510.00`. One boolean from the model deletes a
transaction and no receipt says so. `tests/test_vlm_proposals.py::test_continuation_rows_merge` pins
the merge (with `amount=1.0`) as intended.

**Fix:** a continuation line by definition has no amount. When `continues_previous` is true *and*
`amount > 0`, either keep the row (and let the gate judge it) or refuse the page with a closed code;
in both cases record `rows_continuation_with_amount` in `stats` so the report can see it. The prompt
(`vlm/prompts.py:16`) should also stop offering the model a way to emit a merged row at all.

### MAJOR-9 — `vlm/` is outside the leakage firewall
`tests/test_truth_firewall.py:48-50`

Part-1 Global Constraints state that "`vlm/` never imports `tools.holdout` or names the sealed-store
variable (`tests/test_truth_firewall.py`)". `PRODUCTION_ROOTS` is
`("analysis", "layout", "ocr", "evidence", "discovery", "webapp", "telemetry")` and `REQUIRED_ROOTS`
omits `vlm` as well, so the AST tripwire never looks at the new package. `vlm/` **is** clean today
(verified by grep: the only occurrences of "holdout" are the committed-digest helper names and
`DEFAULT_HOLDOUT_DIGEST`, which `discovery/runner.py` itself carries); nothing keeps it clean.

Reproduction (`test_truth_firewall_does_not_cover_the_vlm_package`).

**Fix:** add `"vlm"` to both tuples. One word, and the stated constraint becomes true.

### MAJOR-10 — `vlm_vast stop all` never stops the 9B server, and `status` reports it down
`tools/vlm_vast.py:27`, `:158`, `:167-174`

`PORTS["b"] == PORTS["b9"] == 18002`, but the two keys keep separate pid files. `cmd_stop(…, "all")`
iterates `("worker", "b", "a")` and `cmd_status` inspects `for k in a b worker`. So a started `b9`
(14.1 GB of weights, the largest GPU-memory footprint of the three) survives `stop all` and is reported
down by `status`, burning the USD 250 R16 budget silently. `cmd_attest` would catch it
(`SERVER_PROCESSES != 0` → `passed: false`) but only after the fact, and the shared port means starting
`b` while `b9` is up silently fails to bind and `cmd_start` still returns a pid and `started: b`.

Reproduction (`test_stop_all_never_stops_the_b9_server`).

**Fix:** give `b9` its own port, include it in the `stop all` key list and in `cmd_status`'s loop, and
have `cmd_start` verify the port is listening (or the pid still alive) before reporting success.

---

## MINOR

* **MINOR-1 — the VLM session token is invisible to `mask_text`.** `tools/vlm_vast.py:122-137` stores
  the harness token in `<runtime_dir>/vlm_worker.token`, but `tools/paddle_vast.mask_text:138-150`
  masks `settings.worker_token` only — the *Paddle* token. The constraint "masked output only through
  `tools.paddle_vast.mask_text`" is therefore not true for the token that matters here. No current call
  path prints it (`_run:116-128` reduces subprocess exceptions to a class name, and no command tails
  `worker.log`), so this is latent, not live. *Fix:* wrap `mask_text` locally with an extra
  `.replace(_token(settings), TOKEN_PLACEHOLDER)` and route every printed string through the wrapper.
* **MINOR-2 — the Stage A worker is unauthenticated when the token variable is unset, and compares
  tokens with `!=`.** `vlm/stage_a_worker.py:42-52`: `resolve_token` returns `None` when
  `VLM_A_WORKER_TOKEN` is absent and `check_bearer_token(None, …)` then returns silently, so a worker
  started by hand (not via `cmd_start`) serves `/parse` to anything on the host's loopback — on a
  shared rented container that is not nobody. The reference worker has the same `None` semantics but
  compares with `hmac.compare_digest` (`ocr/paddle_worker.py:461-476`); this one uses `!=`.
  *Fix:* `hmac.compare_digest`, and refuse to start without a token when
  `PADDLE_EXECUTION_CLASS=remote_paid`.
* **MINOR-3 — the worker prints its port.** `vlm/stage_a_worker.py:203` prints
  `{"listening": true, "port": …}`. It is a compiled-in loopback constant rather than a connection
  secret, but the Global Constraint says "Never print host, port, user or token" without an exception.
  *Fix:* print `{"listening": true}`.
* **MINOR-4 — totals rows become candidate transactions when no description column is classified.**
  `vlm/assemble.py:78` consults `SKIP_DESCRIPTION` on the description cell, which is `""` when
  `classify_columns` assigns no description column. Verified: the grid
  `2031-01-01|10.00|510.00 / 2031-01-02|20.00|530.00 / Total|30.00|` yields a third candidate row of
  `30.00`. It currently fails closed (the `Total` text lands in the date column → `date_unparsed`), but
  the protection is incidental. *Fix:* test `SKIP_DESCRIPTION` against every cell of the row, not just
  the description cell.
* **MINOR-5 — multi-account documents are collapsed into one statement with no distinct reason.**
  `vlm/proposals.py:83-84` and `merge_meta`'s first-non-None rule keep one account's anchors while rows
  from every account are concatenated; `runner.py:189` promotes `currency_conflict` to a gate reason but
  nothing promotes `len(account_last4_values) > 1`. `partitions` counts `multi_account_documents`
  deliberately, so these documents will be in every wave and will be taxonomised as `sum_mismatch`.
  *Fix:* promote a multi-account page set to its own reason code (or group rows per account and gate
  each account, which is what `analysis.pipeline.DocumentReport` does).
* **MINOR-6 — the DEV tuning slice is a subset of the CTRL measurement population.**
  `vlm/partitions.py:130` draws DEV from CTRL, and §11 says prompt and schema design uses DEV. The
  report has no CTRL-minus-DEV split, so the CTRL headline is partly measured on the documents the
  prompts were tuned against. *Fix:* report `CTRL \ DEV` as the primary CTRL figure and DEV separately,
  the way R4 separates development from evaluation.
* **MINOR-7 — `skipped_existing` counts documents skipped by `--limit`.** `vlm/runner.py:263-264`
  computes it after the limit truncation, so a first-ever wave of 4 documents with `--limit 1`
  receipts `skipped_existing: 3` — a receipt asserting work was already done that never was
  (`test_limit_is_counted_as_skipped_existing`). *Fix:* compute it from `existing` alone and add a
  separate `skipped_by_limit`.
* **MINOR-8 — timing attribution.** (a) `vlm/render.py:107` runs the LANCZOS resize between the
  `render_ms` and `encode_ms` windows, so the most expensive CPU-preprocessing step lands in neither.
  (b) `vlm/runner.py:124` sums per-call Stage B durations, which overlap when `concurrency > 1`, and
  `report.py:76` then divides by pages — `stage_b_ms_per_page` exceeds the real per-page wall latency
  at concurrency > 1, and `tests/test_vlm_runner.py::test_stage_b_concurrency_keeps_page_order` checks
  order and tokens but not timings. (c) §11 asks for transfer, queue wait, prefill and decode
  separately; only render / encode / stage_a / stage_b / gate / total exist, and the worker's own
  `timing.decode_ms` / `inference_ms` (`vlm/stage_a_worker.py:113-115`) is discarded by
  `blocks_from_worker`. *Fix:* time the fit inside `render_ms`, record a wall-clock Stage B span
  alongside the summed span, keep the worker's timing block, and take vLLM's per-request timing fields
  where the response carries them.
* **MINOR-9 — `instance_hours` is the controller's wall time, not the instance's.**
  `vlm/runner.py:316-319`. R16 requires hours recorded for the USD 250 budget; the instance bills while
  idle between waves, so this systematically understates spend. `cost_usd` is correctly
  `"rate not measured"` when no rate is given — but note the field's type then flips between `float`
  and `str` in the same receipt key, which `report.py:84` passes straight through. *Fix:* rename to
  `wave_wall_hours`, and record instance uptime from the host (`uptime -s` via `vlm_vast`) in the
  wave's own receipt.
* **MINOR-10 — the hybrid parser context is truncated silently.** `vlm/runner.py:76` cuts the parser
  context at `MAX_PARSER_CONTEXT_CHARS = 12000` with no record, so a long page's hybrid arm runs on a
  mid-table truncation and the receipt cannot distinguish that from a model failure. *Fix:* record
  `parser_context_chars` and `parser_context_truncated` per page in the private receipt and a count in
  the public one.
* **MINOR-11 — `REPORT-*.md` is not exclusive-create.** `vlm/report.py:112` uses `write_text` while the
  sibling JSON uses `dump_new`; the Global Constraint says a receipt is never overwritten. *Fix:*
  `open(path, "x")`.
* **MINOR-12 — an unreachable host burns the wave directory with no receipt.**
  `vlm/runner.py:244-258` creates `out/` and `out/results/` *before* `_model_identity` contacts the
  servers; a `TransportError` there leaves the directory in place with no `launch.json` and no
  `result.json`, and `wave_already_attempted` refuses it forever with nothing explaining why. *Fix:*
  probe the servers before `out.mkdir`, or write a `launch.json` refusal receipt on that path.
* **MINOR-13 — the holdout digest's refusal is an unhandled traceback at the CLI.**
  `discovery.runner.holdout_sha16s_from_digest` raises `ValueError` on a missing or unreadable digest
  (correctly — it must refuse), but `tools/vlm_ceiling.py:130-136` catches only `Refused` and
  `PaddleRefused`, so `vlm_ceiling partitions` on a missing digest exits with a traceback instead of a
  closed code. The refusal itself is sound; only its surface is. *Fix:* catch `ValueError` from the
  digest read and report `holdout_digest_unreadable`.
* **MINOR-14 — determinism inputs not fully pinned.** `vlm/render.py:53-62` records the pypdfium2 and
  pdfium versions but not Pillow's, and the JPEG bytes depend on Pillow's encoder and its LANCZOS
  implementation. §4.11 requires identical software versions to be part of the determinism claim.
  *Fix:* add `pillow_version` to `render_settings()`.
* **MINOR-15 — `_money_after` takes the last money token on the line.** `vlm/metadata.py:34-41` scans
  the whole matched line (and the next) and returns the *last* parseable token, so a summary row that
  prints both labels on one line — exactly the shape `text_lines_from_blocks` produces from an HTML
  summary table — assigns the ending balance to `beginning_balance`. Reproduction
  (`test_beginning_balance_takes_the_last_money_on_a_shared_summary_line`):
  `"Beginning balance 500.00 Ending balance 600.00"` → `beginning == ending == 600.00`. Fails closed at
  the gate, but it will depress the Stage A arm's measured ceiling on a very common layout. *Fix:*
  search from `match.end()` and stop at the next label keyword; take the first token, not the last.

---

## NIT

* `vlm/runner.py:153` puts `family = member.folder_label` — the archive's top-level folder name, an
  analyst-assigned bank label (`discovery/inventory.py:44-52`) — into the public receipt and into
  `report-*.json`'s `by_family`. It is admissible elsewhere in this tree
  (`discovery/evidence.py:71`), but it is a free-text folder name rather than a closed vocabulary, and
  it is the one field in the public receipt that is not a count, hash or closed code.
* `vlm/runner.py:302-305` does not reset `consecutive_transport` on a non-transport failure, so two
  transport failures separated by an unrelated one still abort. Conservative, but the field is called
  *consecutive*.
* `vlm/gate.py:74` turns a single zero-amount row into whole-statement `proposal_invalid`; a printed
  `$0.00` line (a reversal pair, a waived fee) is a real shape. `analysis.reconcile` handles it —
  that is why its count check is keyed on the printed column and not the sign.
* `vlm/runner.py:267-275`'s producer thread blocks on the bounded queue forever after the transport
  abort breaks the loop; daemonised, so harmless at exit, but it holds one document's bytes.
* `tools/vlm_vast.py:177-185` sleeps 2 s after `Popen` and never confirms the forwards came up (the
  `ExitOnForwardFailure=yes` failure mode is a dead pid, which is not checked).
* `tools/vlm_vast.py:150-154` puts the worker token on the remote process's command line, where
  `ps -eo cmd` shows it; `tools/paddle_vast._env_prefix` does the same, so it is not a regression —
  noted because `_ATTEST` itself runs `ps -eo cmd`.

---

## What I verified and found sound

* **No customer bytes on the wire to anywhere but loopback.** `vlm/client.py:46` refuses at
  construction unless `ocr.endpoint_policy.classify_endpoint(base_url) == "loopback"`, and that
  classifier is the reviewed one (explicit IPv4-mapped normalisation, IMDS and CGNAT forced to
  `remote`, control characters and both-end C0 stripping → `invalid`). Redirects are refused
  (`_NoRedirect` + the `300 ≤ code < 400` branch), responses are bounded at 16 MiB, retries go only to
  the same URL and only on connection-level errors, and `http_<code>` / `connection_failed:<class>` are
  the only messages that escape. There is no second endpoint, no fallback list and no env-var URL
  override anywhere in `vlm/`.
* **The Stage A worker binds loopback only.** `build_server` raises `bind_not_loopback` for any host
  but `127.0.0.1`, `main` passes the constant, `Transfer-Encoding` is refused outright, `Content-Length`
  is bounded before the read and again inside `parse_bounded_json`, image decode is bounded on both
  side length and total pixels, every failure is a closed token (`{"error": …, "class": <type name>}`),
  the request-line log is suppressed, and nothing writes the page to disk — `pipeline.predict` is
  handed an in-memory ndarray and no `save_to_*` is ever called. `cmd_attest` independently counts
  residue files and `/tmp` images.
* **Holdout handling.** `vlm/partitions.py:85-86` reads the holdout only through
  `discovery.runner.holdout_sha16s_from_digest` on the committed
  `docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt`, whose helper refuses a missing or unreadable
  digest ("'we could not read the holdout list' and 'the holdout list is empty' are the same silence")
  — and that digest is `bound()` by path+sha256 into the public manifest, so a wave can prove which
  cage it checked. Overlap refuses `population_overlaps_holdout` on sha16 prefixes, duplicates and an
  empty population refuse, and `read_population` refuses a malformed line rather than skipping it.
  `vlm/` names no sealed-store variable and imports neither `tools.holdout` nor `tools.adjudicate`
  (grep-verified). MAJOR-9 is about the *tripwire*, not about a leak.
* **Public/private receipt split** is real and mostly correct: `stage_a_blocks`, `stage_b` raw text,
  candidate `rows`, `meta` and `gate_checks` all go to `*.private.json`; `results/<SHA>.json` carries
  the SHA, page hashes, counts, closed reason codes and timings. `test_stage_a_rules_arm_admits_synthetic_ledger`
  asserts the archive path is absent from the public half. BLOCK-1 is the one field that escaped.
* **Gitignore coverage is real**, not assumed: `git check-ignore -v` confirms
  `discovery_reports/` (line 23) covers every wave receipt, private manifest and fetch receipt, and
  `.paddle_runtime/` (line 27) covers `vlm_worker.token`.
* **Receipt primitives.** `dump_new` serialises before `open(path, "x")`, so a refused value leaves no
  file; sorted keys, `allow_nan=False`, fsync. `bound`/`checked` refuse `binding_missing`,
  `binding_shape` and `binding_changed`. `Refused` carries a closed snake_case code and nothing else.
  Wave directories are never reused — `need(not os.path.lexists(out), "wave_already_attempted")` is
  checked before the authorization call and before any mkdir, and the CLI turns it into exit 2.
* **The authorization seam is called before any page moves** (`run_wave:243`, ahead of `out.mkdir` and
  the document loop) and `check_remote_authorization` itself re-derives both literals from the live
  environment, so a hand-built `PaddleSettings(remote_opt_in=True)` cannot lie. `--data-scope` defaults
  to `customer`, the fail-closed direction. BLOCK-2 and BLOCK-3 are about what the *declaration* is
  bound to, not about the gate being skipped.
* **The host tool's transport is the reviewed one.** `_run`/`_popen` reduce every `SubprocessError` /
  `OSError` to `PaddleVastError(type(exc).__name__)`, which is why no command line — host, SSH port,
  user, token — can reach a traceback; every returned string goes through `mask_text`; `PaddleConfigError`
  messages name a variable, never a value; `cmd_check`/`cmd_status`/`cmd_fetch`/`cmd_deploy` all mask
  remote stdout, and `tests/test_vlm_vast_tool.py` pins that the host literal is absent from the JSON
  and that the token is absent from `cmd_start`'s return. Servers are pinned to `--host 127.0.0.1`,
  the tunnel is three explicit `127.0.0.1:port:127.0.0.1:port` forwards with `BatchMode=yes` and
  `ExitOnForwardFailure=yes`, and `HF_HUB_OFFLINE=1 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1` is on every
  serve.
* **Reader truth is read-only.** `tools.cohort_replay.ColdCache` opens `webapp.db` with
  `?mode=ro` and resolves artifacts through `telemetry.run_of_record`'s single selection policy, so the
  frozen `webapp_data_train12_cold` cache cannot be mutated by this harness. `ReaderTruth.accounts`
  returns `None` rather than guessing when the reader produced no payload.
* **`analysis.reconcile` is genuinely the arithmetic authority** — `vlm/gate.py:115` calls it on a real
  `analysis.schema.Statement` and takes `ok`, `sum_delta`, `continuity_breaks` and `issues` from it
  rather than re-implementing any of it; `admitted_rows` is `()` unless the verdict is admitted, so
  there is no partial admission anywhere in the gate or the runner. The gate's own additions
  (date parse, period window with a 5-day grace, monotonicity, duplicates, direction) are all
  fail-closed reason codes. My MAJOR findings are about which facts reach `reconcile`, not about
  whether it decides.
* **Determinism of the model call** is correct where it is set: `temperature: 0`, `seed`,
  `chat_template_kwargs: {"enable_thinking": false}`, `response_format: {"type": "json_schema", …}`,
  canonical JSON bodies, and `request_sha256`/`response_sha256` on every `ChatResult`. `schema_sha256`
  is over canonical JSON. Renders are byte-deterministic per
  `tests/test_vlm_render.py::test_render_is_deterministic`.
* **No PyMuPDF** anywhere in `vlm/` (pypdfium2 only), and `LICENSES.md` records the new dependencies.
* **The 3-consecutive-transport-failure abort works** and is receipted (`status: "failed"`,
  `failure_code: "transport_failing"`, `release.json` `controller_exit: 1`); the counter resets on
  success. **The hourly rate is never guessed** — `cost_usd` is the literal string
  `"rate not measured"` unless a rate is passed, per R2/R16.

---

## Reproducing this review

```
python -m pytest tests/test_vlm_review_findings.py -q -p no:cacheprovider          # 15 passed
python -m pytest tests/test_vlm_*.py tests/test_truth_firewall.py -q -p no:cacheprovider  # 134 passed
```

Mapping from finding to test in `tests/test_vlm_review_findings.py`:

| finding | test |
|---|---|
| BLOCK-1 | `test_public_receipt_carries_the_extracted_account_last4` |
| BLOCK-2 | `test_no_worker_identity_echo_exists_for_the_vlm_path` |
| BLOCK-3 | `test_cli_data_scope_is_an_unbound_operator_declaration` |
| MAJOR-1 | `test_gate_admits_a_truncated_statement_when_both_anchors_are_derived` |
| MAJOR-1/3 | `test_chain_derived_directions_make_the_continuity_check_vacuous` |
| MAJOR-2 | `test_duplicate_row_masking_a_missing_row_is_admitted_when_no_balances_are_printed` |
| MAJOR-4 | `test_the_gate_never_gives_reconcile_the_banks_own_printed_totals_or_counts` |
| MAJOR-5 | `test_resume_skips_documents_that_only_have_a_FAILURE_receipt` |
| MAJOR-6 | `test_interrupted_wave_is_receipted_as_complete` |
| MAJOR-7 | `test_launch_receipt_pins_neither_the_weight_hashes_nor_the_hybrid_prompt` |
| MAJOR-8 | `test_continues_previous_discards_a_real_amount_and_the_drop_is_not_counted` |
| MAJOR-9 | `test_truth_firewall_does_not_cover_the_vlm_package` |
| MAJOR-10 | `test_stop_all_never_stops_the_b9_server` |
| MINOR-7 | `test_limit_is_counted_as_skipped_existing` |
| MINOR-15 | `test_beginning_balance_takes_the_last_money_on_a_shared_summary_line` |
