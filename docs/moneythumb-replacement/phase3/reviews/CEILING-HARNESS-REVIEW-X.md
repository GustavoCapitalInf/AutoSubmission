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

---

# Re-review 1

**VERDICT: APPROVE-WITH-FINDINGS**

The boundary is closed. BLOCK-1, BLOCK-2 and BLOCK-3 are all closed and I could not construct a
bypass of any of them, so the block on CTRL and U755 waves is **lifted**: customer pages may move.

Two MAJOR findings remain, both about whether the gate's admission means what the §11 thresholds
assume — not about the boundary. Neither is visible in the report, and each can admit a ledger that
is wrong in content:

* **MAJOR-2 STILL OPEN (narrowed)** — a matching printed count is a statement-wide amnesty for an
  unverifiable repeat, which is exactly the signature of one-row-dropped-one-row-duplicated.
* **RR-1 (new, MAJOR)** — the hybrid arm silently prefers the model's *claimed* anchor over the
  Stage A rule reading and records no disagreement, so an invented anchor reproduces MAJOR-1's
  tautology one level up.

Both are small fixes. They gate the **go/revise/stop recommendation**, not the runs: the §11
recommendation should not be written from a wave whose `admitted` figure still contains those two
classes uncounted.

Scope of this re-review: `git diff 8b0744c..5654bca` (23 files, +1573/-268), read against the same
constraints as the first pass. Tests: `tests/test_vlm_*.py` + `tests/test_truth_firewall.py` ->
**153 passed** (147 theirs + my 6 new re-review counterexamples). New tests added by this pass:
`tests/test_vlm_review_rereview1.py` (same characterisation convention: each asserts today's
behaviour, each docstring names the id and the assertion to invert). No non-test source file
modified; no customer document opened; no host detail printed.

## Per finding

| id | state |
|---|---|
| BLOCK-1 | CLOSED (residual MINOR RR-5) |
| BLOCK-2 | CLOSED |
| BLOCK-3 | CLOSED |
| MAJOR-1 | CLOSED (residual MAJOR RR-1) |
| GATE-3 | CLOSED |
| MAJOR-2 | **STILL OPEN (narrowed)** -> RR-2 |
| MAJOR-3 | CLOSED (residual MINOR RR-3) |
| MAJOR-4 | CLOSED (residual MINOR RR-6) |
| MAJOR-5 | CLOSED |
| MAJOR-6 | CLOSED |
| MAJOR-7 | CLOSED (residual MINOR RR-4) |
| MAJOR-8 | CLOSED |
| MAJOR-9 | CLOSED |
| MAJOR-10 | CLOSED |
| MINOR-1 | CLOSED |
| MINOR-2 | CLOSED |
| MINOR-3 | STILL OPEN |
| MINOR-4 | STILL OPEN |
| MINOR-5 | STILL OPEN |
| MINOR-6 | CLOSED |
| MINOR-7 | CLOSED |
| MINOR-8 | STILL OPEN in part (b closed; a and c open) |
| MINOR-9 | CLOSED in part (renamed; instance uptime still not recorded) |
| MINOR-10 | STILL OPEN |
| MINOR-11 | STILL OPEN |
| MINOR-12 | STILL OPEN in part (improved) |
| MINOR-13 | STILL OPEN |
| MINOR-14 | STILL OPEN |
| MINOR-15 / META-1 | CLOSED |
| NITs | STILL OPEN (all five; the `ps` one accepted as parity with the reference) |

### BLOCK-1 — CLOSED

`vlm/proposals.py:118-128`. `stats` now carries `account_last4_count` and
`account_last4_set_sha256`; `account_last4_values` is gone from the module, and the values remain in
the private receipt only. `_money` also now rejects `bool`, which stops `True` becoming `1.00`.
Verified: `test_public_stats_never_carry_the_extracted_account_last4` asserts the key is absent and
that the digits do not appear in the serialised stats. Residual: RR-5 below — hashing a four-digit
value is not de-identification.

### BLOCK-2 — CLOSED

`vlm/runner.py:81-97` (`verify_identity`), `:317-325` (called before `out.mkdir`),
`vlm/stage_a_worker.py:128-136` (`/version` echoes `PADDLE_PROVIDER` / `PADDLE_EXECUTION_CLASS`),
`tools/vlm_vast.py:155-158` (`cmd_start` exports them to the worker).

Bypasses I tried, all refused:

1. **Local declaration.** `PADDLE_PROVIDER=local` (`PROVIDER_CLASS` forces `local_free`, so
   `is_remote` is False) with the three loopback model endpoints ->
   `need(settings.is_remote, "local_declaration_with_model_endpoints")` refuses every model arm
   before `out.mkdir`. This was the live bypass in the first pass and it is gone. Pinned by
   `tests/test_vlm_runner.py::test_identity_refusals`.
2. **Spoofed echo.** A worker (or any loopback service) whose `/version` returns a different
   provider/execution_class -> `vlm_identity_mismatch`. A service that echoes `vast.ai`/`remote_paid`
   while actually being local *over*-declares, which is the conservative direction and still requires
   the operator to hold both real env literals to pass `check_remote_authorization`.
3. **`stage_b_only` with no worker.** `ctx.stage_a` is None for that arm, so the probe falls to
   `ctx.identity_client`; with neither, `identity_probe_missing` refuses. The CLI builds
   `identity_client` for every arm but `reader_baseline` (`tools/vlm_ceiling.py:52`), so the arm that
   sends pages to Stage B only still cannot run without an attested Stage A worker.
4. **Non-loopback endpoint.** Unchanged and still refused at `HttpJson.__init__`.

Accepted limitation, stated plainly because it is the same one the reference path has: the echo is
fed from the declaration `cmd_start` exported, so it proves "this is the worker I deployed under that
declaration", not "this process runs on the rented host". `cmd_attest` now also records
`provider` / `execution_class` (`tools/vlm_vast.py:232-234`), which is the independent-ish leg.
Parity with `ocr.paddle_client.verify_identity` is the right bar and it is met.

### BLOCK-3 — CLOSED

`vlm/partitions.py:119` and `:128-134` (`data_scope` stamped `customer` on every manifest built from
a population file; `manifest_scope()` refuses `manifest_scope_missing` rather than defaulting),
`tools/vlm_ceiling.py:56` (the scope is read from the manifest), `vlm/runner.py:315`
(`data_scope_disagrees_with_manifest`). **The `--data-scope` flag no longer exists**, which is what
made the first-pass bypass a one-word typo;
`tests/test_vlm_ceiling_cli.py::test_data_scope_flag_no_longer_exists` pins its absence and the
inverted `test_cli_scope_comes_from_the_manifest` shows a CTRL manifest now runs as `customer` with
`launch.manifest_scope == "customer"`.

Attempted: running a customer manifest under the synthetic scope. There is no CLI path to it. The
only route left is hand-editing `data_scope` in a private manifest — which `dump_new`'s exclusive
create prevents from happening by regeneration, and which the `manifest_binding` sha256 in
`launch.json` records. Cheap hardening worth taking anyway (NIT): refuse a `synthetic` manifest whose
`archive_root` resolves inside `DEFAULT_ARCHIVE_ROOT`, or whose members appear in a population file.

### MAJOR-1 — CLOSED

`vlm/gate.py:111-132`. With neither balance printed the gate refuses `anchors_underdetermined`; with
one printed the other may be derived but the verdict carries `anchor_derived` and is never admitted.
Admission now requires both anchors printed, which makes reconcile's sum check independent of the
row chain. Verified directly:

| proposal | verdict |
|---|---|
| rows 1-3 of a 6-row chain, no printed anchors | `('anchors_underdetermined',)` |
| rows 1-3, beginning printed only | `('anchor_derived',)` |
| rows 1-3, printed 500.00 / 710.00 (a real truncation) | `('sum_mismatch',)` — the first-pass hole |
| rows 1-6, printed 500.00 / 710.00 | admitted, `anchored == "both"` |

The first-pass counterexample (a statement and its own first half both admitted) is gone.

### GATE-3 — CLOSED

`vlm/gate.py:136-137`. Chain-derived directions are refused (`chain_direction_unanchored`) unless
both anchors are printed, and with both printed the sum check constrains the signs independently: the
transposed-balance counterexample now yields `('sum_mismatch',)` against the printed ending, and
`('anchors_underdetermined', 'chain_direction_unanchored')` with no anchors.

### MAJOR-2 — STILL OPEN (narrowed) -> RR-2 (MAJOR)

`vlm/gate.py:173-175`, `vlm/report.py:39-117`.

The first-pass counterexample is closed: `_duplicates` no longer skips balance-free rows, and a
repeat with no printed counts refuses (`duplicate_row`) — verified, and pinned by the inverted
`test_duplicate_row_masking_a_missing_row_is_refused_when_no_balances_are_printed`.

But `counts_vouch` is a **statement-wide amnesty**: `if unverifiable and not counts_vouch`. A printed
count that matches *because* one row was dropped and another duplicated is precisely the signature
the check should catch — had the model duplicated a row without dropping one, the count would be one
too high and `count_mismatch` would fire. So the condition under which the amnesty applies is the
condition under which the defect is most likely.

Reproduction (`test_counts_vouch_amnesties_an_unverifiable_repeat_and_the_report_never_sees_it`):
printed beginning 1000.00, ending 750.00, `stated_total_debits` 250.00, `stated_debit_count` 3,
`stated_credit_count` 0; the truth is RENT -100, INSURANCE -100, FEE -50; the model emits RENT twice
and FEE once. `gate(...)` returns `admitted=True`, `reasons=()`, and
`checks["repeats"] == {"distinguished": 0, "unverifiable": 1}`. The gate *knows* and admits.

Worse: `vlm/report.py` never reads `gate.repeats` (the string does not occur in the module), so the
class is admitted silently **and** reported silently. On CTRL, `false_accepts` does catch this
particular instance (the dates differ, so `match_rows` reports missing 1 / extra 1) — but only where
reader truth exists, i.e. never on U755, the population the GO threshold is defined on.

**Fix:** (a) never let a count match amnesty an *unexplained* repeat — require the repeat to be
explained structurally (adjacent locators on the same page, or a distinct `section_index`) and keep
`duplicate_row` otherwise; or (b) if the amnesty stays, admit with a recorded class and have
`report._metrics` count `admitted_with_unverifiable_repeat` and surface it in `REPORT-*.md`, so the
number is at least visible to whoever reviews the recommendation.

### RR-1 (new, MAJOR) — the model's claimed anchor silently overrides the rule-read one

`vlm/metadata.py::merge_meta`, `vlm/runner.py` hybrid branch (`meta = merge_meta(meta, a_meta)`).

MAJOR-1's closure stops the *harness* deriving an anchor from the rows. It does not stop the *model*
from emitting one: `meta.beginning_balance` is only *claimed* to be printed, and a model that reports
an anchor consistent with its own rows gets `anchored == "both"` and admission — the same tautology,
one level up. The prompt asks for null when the value is not on the page, which is the right
instruction and no check at all.

The hybrid arm already holds the independent second reading — the Stage A rule extraction — and
throws it away: `merge_meta` takes the first non-None, so Stage B's claim wins, the rule-read value
is discarded, and the union of `sources` shows *both* `meta:stage_b` and `beginning:rule` with
nothing saying they disagreed.

Reproduction (`test_hybrid_prefers_the_models_claimed_anchor_and_records_no_disagreement`): claimed
beginning 490.00 against rule-read 500.00 gives merged 490.00, `sources` contains both tokens, and
neither `anchor_disagreement` nor `meta_conflict` exists anywhere in `vlm/runner.py`.

**Fix:** in `merge_meta` (or a new `reconcile_meta`), record every field where two sources both hold
a value and disagree; make an anchor disagreement a gate reason for the hybrid arm, and count it in
the report. Cheap companion tripwire worth adding in the same edit: set
`checks["anchor_equals_row_derived"]` when a *claimed* beginning equals
`first.balance -/+ first.amount` exactly, so the report can count admissions whose claimed anchor
looks computed rather than read.

### MAJOR-3 — CLOSED

`vlm/report.py:34-36`, `:88-117`, `:120-134`. `false_accepts` (count plus a SHA list — content SHAs
only, no customer content), `admitted_strict`, `strict_admission_rate`,
`would_admit_with_derived_anchor`, `admitted_with_chain_directions`, `derived_anchors`,
`rows.validated_match_rate`, `primary_without_excluded` plus `excluded_documents`, and the markdown
table now prints strict admissions and false accepts on the front row. `--exclude-manifest` wires the
DEV slice in from the CLI, which also closes MINOR-6. Residual: RR-3 below.

### MAJOR-4 — CLOSED

`vlm/schema.py:45-62` (schema 2: `stated_total_credits`, `stated_total_debits`,
`stated_credit_count`, `stated_debit_count`, all required-and-nullable), `vlm/prompts.py:18`
(prompt 2 asks for them as printed-only values), `vlm/metadata.py:17-20` and `:56-95` (rule
extraction for the Stage A arm), `vlm/proposals.py:85-93`, `vlm/gate.py:78-79` and `:161-173`.
Verified end to end: `statement_from` now carries the four fields into `reconcile`, `summary_ok` and
both count-match fields come back non-None, and `summary_mismatch` / `count_mismatch` fire. The
inverted `test_the_gate_gives_reconcile_the_banks_printed_totals_and_counts` pins it.

Observation, not a finding: the protection is opt-in by the model — a proposal that leaves the four
fields null gets the weaker check (both printed balances and the sum identity). That is the honest
behaviour for statements that print no summary, and `meta_sources` shows which documents supplied
them. Residual: RR-6 below.

### MAJOR-5 — CLOSED

`vlm/runner.py:283-295` (`_completed_shas` parses each receipt and counts only those with
`failure is None` and a `sha`). Verified: a wave that aborts with three transport failures now resumes
with `skipped_existing == 0` (the inverted
`test_resume_retries_documents_that_only_have_a_failure_receipt`). Gate refusals are still treated as
done, which is correct.

### MAJOR-6 — CLOSED

`vlm/runner.py:380-384`: `except BaseException` sets `status="aborted"` with `failure_code`
`interrupted` / `controller_failure` and the exception class, then re-raises; the `finally` writes
`result.json` with that status and `release.json` with `controller_exit: 1`.

### MAJOR-7 — CLOSED

`vlm/prompts.py:43-53` (`prompt_manifest` hashes the `STAGE_B_PROMPT` and `HYBRID_PREFIX`
**templates**, so every rendering is covered), `tools/vlm_ceiling.py:33-45` (`_weights_bindings`
binds the latest non-FAILED fetch receipt per key with `receipts.bound` plus the recorded
`sha256sum` lines), `vlm/runner.py:330` (`"weights": weights or {}`). Residual: RR-4 below.

### MAJOR-8 — CLOSED

`vlm/proposals.py:46-63`: a `continues_previous` row that carries a positive amount is kept as a row,
the flag is ignored and counted as `continuation_rows_with_amount`; the drop ledger now separates
`nonpositive` / `continuation_merged` / `continuation_with_amount`, and the prompt tells the model
never to mark an amount-bearing line as a continuation. The inverted
`test_continues_previous_with_an_amount_keeps_the_row_and_counts_it` pins both the kept row and the
counter.

### MAJOR-9 — CLOSED

`tests/test_truth_firewall.py:48-50`: `"vlm"` is in both `PRODUCTION_ROOTS` and `REQUIRED_ROOTS`, and
the firewall passes with it (green in the 153).

### MAJOR-10 — CLOSED

`tools/vlm_vast.py:31-32` (`PORTS["b9"] = 18004`, `SERVER_KEYS`), `:164` (`stop all` becomes
`("worker", "b9", "b", "a")`), `:181-186` (`status` loops `a b b9 worker` and probes all four local
ports), `:64-68` (four tunnel forwards), `:186` and `:191` (the `ss` greps include 18004), `:196-198`
(the port-in-use check covers all four).

### MINOR closures

* **MINOR-1 CLOSED** — `tools/vlm_vast.py:84-91` adds a local `_mask` that also replaces the contents
  of the harness token file; every `cmd_*` returns through it, `cmd_start` masks `remote_pid`, and
  `main` prints `_mask(json.dumps(out), settings)` — so the whole printed surface, not just the parts
  someone remembered, is masked.
* **MINOR-2 CLOSED** — `vlm/stage_a_worker.py:50-55` uses `hmac.compare_digest` and type-checks the
  header; `:195-198` refuses to start without a token unless `--allow-no-token` is passed explicitly.
* **MINOR-6 CLOSED** — see MAJOR-3.
* **MINOR-7 CLOSED** — `vlm/runner.py:333-337`: `skipped_existing` is `len(members) - len(remaining)`
  and the limit is reported separately as `limited_out`.
* **MINOR-9 CLOSED in part** — the field is now `wave_wall_hours` everywhere (runner, report, CLI),
  which makes the receipt honest about what it measures. Instance uptime for the USD 250 budget is
  still not recorded, and `cost_usd` still flips between a float and the string
  `"rate not measured"`.
* **MINOR-15 / META-1 CLOSED** — `vlm/metadata.py:45-54`: `_money_after` takes the first money token
  at or after the label's own end offset. A summary line printing both labels now yields 500.00 and
  600.00 in the right fields.
* **MINOR-12 improved** — `verify_identity` probes `/version` before `out.mkdir`, so an unreachable
  Stage A worker no longer burns the wave directory. Still open for Stage B: `_model_identity(ctx)`
  calls `stage_b.models()` inside the `launch` dict, after `mkdir`, so a Stage B transport failure
  still leaves a directory with no receipts and `wave_already_attempted` forever.

### MINOR / NIT still open (unchanged from the first pass unless noted)

MINOR-3 (`vlm/stage_a_worker.py:213` still prints the port) · MINOR-4 (`vlm/assemble.py:78`,
`SKIP_DESCRIPTION` still consulted only on the description cell) · MINOR-5 (multi-account still not a
gate reason; `vlm/runner.py:232` promotes only `currency_conflict`, and `stats` now publishes
`account_last4_count`, which is exactly the signal that would drive it) · MINOR-8a
(`vlm/render.py:107`, `_fit` still sits between the two timing windows) and MINOR-8c (the §11
transfer / queue / prefill / decode split is still absent, and the worker's own `timing` block is
still discarded by `blocks_from_worker`) — MINOR-8b is closed (`stage_b_wall_ms` recorded and
reported per page) · MINOR-10 (`vlm/runner.py:114-117`, the 12000-character parser-context truncation
is still silent) · MINOR-11 (`vlm/report.py:165`, `REPORT-*.md` still uses `write_text`) · MINOR-13
(`tools/vlm_ceiling.py:180-186` still catches only `Refused` and `PaddleRefused`, so a missing
holdout digest is a traceback) · MINOR-14 (the Pillow version is still absent from
`render_settings()`) · the five NITs (the public `family` label; `consecutive_transport` not reset by
a non-transport failure; a single zero-amount row still refusing the whole statement; the producer
thread; `cmd_tunnel_up` still not confirming the forwards).

### New findings from this pass

* **RR-1 (MAJOR)** — above.
* **RR-2 (MAJOR)** — above, under MAJOR-2.
* **RR-3 (MINOR)** `vlm/report.py:34-36`. `_is_false_accept` reads only `missing` and `extra`, which
  `truth.match_rows` keys on (date, amount, direction), so an admitted statement carrying the wrong
  descriptions at the right dates and amounts is not counted as a false accept even though
  `exact_description < matched` says it is. Reproduction:
  `test_false_accept_test_ignores_a_same_date_same_amount_description_swap`. *Fix:* add
  `exact_description < matched` (or a `description_mismatches` figure) to the test. This is the one
  remaining row-content error that neither the gate nor the report sees, and it composes with RR-2.
* **RR-4 (MINOR)** `tools/vlm_ceiling.py:33-45` and `:62-63`. The weight pin is keyed on the **arm**
  (`"a"` if Stage A, `"b"` if Stage B), not on the served model, so a wave served by the 9B
  second-opinion model (key `b9`) binds the **4B** fetch receipt, and `launch.json` then contains a
  `models.stage_b_model` and a `weights.b.repo` naming different models with nothing refusing. And
  when no fetch receipt exists the key is silently omitted, so a wave can still run with
  `weights: {}`. `_weights_bindings` has no test. *Fix:* map the key from `ctx.stage_b_model` through
  `tools.vlm_vast.MODELS[*]["served"]`, refuse when the bound receipt disagrees with the served name,
  and refuse a model arm with no weight binding at all.
* **RR-5 (MINOR)** `vlm/proposals.py:124`. `account_last4_set_sha256` is a bare SHA-256 over a
  canonical list of four-digit strings: 10000 pre-images for one account. Reproduction
  (`test_account_last4_digest_is_brute_forceable`) recovers the digits from the published digest by
  exhaustive search in milliseconds. A hash of a low-entropy identifier is not de-identification.
  *Fix:* publish only `account_last4_count`, or HMAC the set with a per-wave secret kept out of the
  public receipt.
* **RR-6 (MINOR)** `vlm/metadata.py:58-64`. `_count_after` searches the whole tail (and then the whole
  line) for a parenthesised number, so a count belonging to a different column of the same joined
  summary row is attached to the total — and under MAJOR-4 a wrong printed count now **refuses** the
  statement. Reproduction (`test_printed_count_fallback_attaches_an_unrelated_paren_count`): a line
  printing a deposits total followed by a checks-paid count yields that count as
  `stated_credit_count`, and the gate then returns `count_mismatch`. Fail-closed, but it converts a
  metadata misread into a false reject and will depress the Stage A arm's measured ceiling. *Fix:*
  bound the count search to the label's own field — stop at the total's money token. The
  label-anchored path itself is right: a properly joined deposits/withdrawals summary row extracts
  both totals and both counts correctly; only the fallback over-reaches.
* **RR-7 (NIT)** `vlm/gate.py:165-166`. `not result.ok` folds every reconcile issue into
  `sum_mismatch`, including the informational credit/debit **coverage** issues, so the failure
  taxonomy attributes a coverage shortfall to the sum check. Reproduction
  (`test_coverage_shortfall_is_reported_as_sum_mismatch`). The refusal is right; the label is not.
  *Fix:* add a `coverage_mismatch` reason and key `sum_mismatch` on `sum_delta` alone.
* **RR-8 (NIT)** `vlm/report.py:128-131`. `primary_without_excluded`'s `attempted` counts successes
  only, while the main slice's `attempted` (from `result.json`) includes failures, so the two
  `strict_admission_rate` figures use different denominators and the excluded slice reads optimistic.

### Residual risk I am not filing as a finding

An error that is symmetric under sum, coverage and count is arithmetically undetectable, and the gate
is right not to pretend otherwise. Verified: two rows of **equal amount** with their directions
swapped — printed anchors, printed totals and printed counts all present and all matching — is
admitted, because the sum, the per-direction totals and the per-direction counts are identical either
way. The same holds for a dropped row replaced by an invented row of the same amount and direction.
Both are caught on CTRL by MAJOR-3's `false_accepts` (the match keys change, so missing and extra
rise) and by nothing on U755. This is the honest limit of a gate with no printed running balances to
check against, and it is why the report's `false_accepts` figure — and RR-3's blind spot in it —
matters.

### What I re-verified and found sound

* `verify_identity` runs before `out.mkdir`, after the authorization call, and its four refusal codes
  (`local_declaration_with_model_endpoints`, `identity_probe_missing`, `vlm_identity_echo_shape`,
  `vlm_identity_mismatch`) are closed tokens with tests.
* `manifest_scope` refuses a manifest with no declared scope rather than defaulting, and
  `data_scope_disagrees_with_manifest` is checked before the wave directory is even looked at
  (`tests/test_vlm_runner.py:150-151` asserts the directory is not created).
* The public receipt's new fields are all counts, hashes, closed codes or booleans: `gate.anchored`,
  `gate.repeats`, `gate.summary_ok`, `stats.account_last4_count`,
  `stats.continuation_rows_merged` / `..._with_amount`, `timings.stage_b_wall_ms`. Nothing new leaks.
* The report's `false_accepts.documents` lists content SHAs only; `render_markdown` still contains no
  SHA or description; `REPORT-*.md` carries no customer content.
* `tools/vlm_vast.py` still routes every printed value through masking (now including the harness
  token), `_run` / `_popen` still reduce subprocess exceptions to a class name, servers are still
  bound to `--host 127.0.0.1`, and `cmd_attest` still counts residue files and temporary images and
  now records the declaration alongside.
* `vlm/` passes the leakage firewall with `vlm` in both root tuples; `dump_new` is still the only
  JSON receipt writer; wave directories are still never reused.
* Schema 2 stays inside the grammar-safe subset (nullable unions, `additionalProperties: false`,
  `required` listing every property), so the structured-decoding contract is unchanged in kind.

### Reproducing this re-review

```
python -m pytest tests/test_vlm_review_rereview1.py -q -p no:cacheprovider
python -m pytest tests/test_vlm_*.py tests/test_truth_firewall.py -q -p no:cacheprovider
```

6 passed and 153 passed respectively.

| finding | test in `tests/test_vlm_review_rereview1.py` |
|---|---|
| MAJOR-2 residual / RR-2 | `test_counts_vouch_amnesties_an_unverifiable_repeat_and_the_report_never_sees_it` |
| RR-1 | `test_hybrid_prefers_the_models_claimed_anchor_and_records_no_disagreement` |
| RR-3 | `test_false_accept_test_ignores_a_same_date_same_amount_description_swap` |
| RR-5 | `test_account_last4_digest_is_brute_forceable` |
| RR-6 | `test_printed_count_fallback_attaches_an_unrelated_paren_count` |
| RR-7 | `test_coverage_shortfall_is_reported_as_sum_mismatch` |
