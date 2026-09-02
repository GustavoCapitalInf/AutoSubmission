# PHASE2_P21PADDLE_REVIEW — independent adversarial review of `wave21-paddle` (cell P)

```
VERDICT: APPROVE WITH FINDINGS
BRANCH:  wave21-paddle  HEAD 2fe1876   BASE 888fb1c   (18 files, +3,900)
REVIEWER: independent Opus agent, detached worktree .claude/worktrees/rev21-paddle
DATE: 2026-09-02
FINDINGS: BLOCK 0 · MAJOR 4 · MINOR 12
LIVE CHECK OVER THE REAL TUNNEL: NOT PERFORMED — no finding required it (see §Live).
```

No BLOCK. The architecture the card asked for is present and, where I attacked it, it holds:
the URL never votes on execution class, the two opt-in literals exist and are checked before
any byte leaves, boxes are refused rather than clamped, lines come from geometry rather than
from `rec_texts`, confidence never filters or reaches page text, nothing is written to disk,
and nothing in `ocr/paddle_*.py` reasons about an amount, a date or a sign. All twelve mutants
in the card's table are genuinely killed — I re-applied every one myself and re-ran the named
killers. The four MAJOR findings are all cases where a stated guarantee is enforced by the
caller's or the worker's good behaviour rather than by structure, plus one place where the
tool prints the connection information it promises never to print. Each has a small, local fix.
They should close before cell R composes, because cell R is the caller that will supply the
settings object, store `evidence.runtime` on the artifact record and surface it in telemetry.

---

## Claim-by-claim table (claimed → what I measured)

| # | cell's claim | my measurement | verdict |
|---|---|---|---|
| 1 | Paddle tests 150 passed | `pytest tests/test_paddle_{worker,client,adapter,rung,vast_tool,live,config}.py -q` → **150 passed, 1 deselected**, 47.9 s | REPRODUCED |
| 2 | guards + conformance 1,549 | the 12 named files → **1,549 passed, 41 skipped**, 12.8 s | REPRODUCED |
| 3 | M1–M12 all killed | 13 mutant applications (M8 at both enforcement sites), each applied to the source as the card words it, killers run without `-x`, file restored in a `finally`, `git status --porcelain` empty after every one → **13/13 KILLED**; M2 kills 8 of 9 parametrisations (`contract` alone correctly passes); M6's new two-column test fails while the older ledger test still passes, exactly as the W3 section says | REPRODUCED |
| 4 | privacy scan 0 over 3,691 added lines | re-run at the tip against `webapp_data_train10_cold` + the Phase-2.0 run of record: `added_lines` **3,900** (the cell's 3,691 excludes its own W3 commit's 209 lines), `documents_read` 3,351, `raw_hit_count` 35, all WORDS-class excluded, **`hit_count` 0** | REPRODUCED AND WIDENED (their scope was 209 lines short of the tip; the result still holds) |
| 5 | secrets scan: 0 occurrences of the values of `PADDLE_VAST_HOST` / `_SSH_PORT` / `_SSH_USER` | independent scan of the whole diff **and** all 14 commit messages against `os.environ` at scan time: HOST **0/0/0** (diff/added/messages), SSH_PORT **0/0/0**, SSH_USER **0/0/1** — the single hit is the user value occurring inside ordinary English prose in one commit message (a WORDS-class coincidence; it carries no connection information). IPv4-shaped tokens in added lines: `127.0.0.1`, `0.0.0.0`, `192.168.1.5` (a bind-refusal test literal) only. No `user@host` shape. No port-shaped literal equal to the real SSH port | ESSENTIALLY REPRODUCED — the "0 occurrences" wording is not literally true; nothing sensitive is disclosed |
| 6 | `.env.paddle.example`, runbook, measurements carry no real value | confirmed by reading all three; `.paddle_runtime/` is gitignored (`git check-ignore` confirms `worker.token`) | REPRODUCED (but see MINOR-7) |
| 7 | measurements: bytes sent 253,799 "(PNG, base64-encoded, JSON-wrapped)" | rebuilt the same fixture (8 rows, 300 dpi): raster **2550 × 3300**, `len(png_bytes)` = **253,799** (exactly the claimed figure — it is the RAW PNG), actual `/ocr` request body = **338,480** bytes | NUMBER REPRODUCES, LABEL IS WRONG (MINOR-8) |
| 8 | measurements: GPU 7,692 / 32,607 MiB, 0 % utilisation, ~262 s worker wall-clock | `cmd_measure` has a `gpu_sampler` seam that `main()` never supplies, no `nvidia-smi` call, no RSS/`tracemalloc` sampling; on the CLI path `report["gpu"] is None`. These rows are not produced by any committed instrument | NOT REPRODUCIBLE FROM THE TOOL (MINOR-8) |
| 9 | latency figures (cold 5,087.5 / 3,981.0 ms; warm median 1,521.8, p95 1,590.1, n=20) | not re-measured (would require a paid live run); the code paths that produce them are correct (`statistics.median`; p95 = nearest-rank index 18 of 20) | NOT RE-MEASURED |
| 10 | live proof 1 passed (36 words / 7 lines) | not re-run — see §Live. The live test as written does NOT assert the card's "evidence sha stable across two runs"; it asserts only `document_sha256` equality and explains why. My MINOR-6 shows why it could not have asserted it | NOT RE-MEASURED; the card's LIVE requirement is partially unmet |
| 11 | full suite 8,528 passed / gate 105-3-1 / corpus slice 34 | not re-run (brief: only if a finding requires it; none did) | NOT RE-MEASURED |
| 12 | `ocr/paddle_config.py` APPENDED only | `git diff` on that file: 9 added lines — a 7-line comment plus two new members at the end of `REFUSAL_REASONS`; no existing value changed | REPRODUCED |
| 13 | worker/client/adapter/rung contain no financial reasoning | grep for `amount|balance|debit|credit|currency|decimal|re.compile|isdigit|strptime` across the four modules: two hits, both in prose comments | REPRODUCED |
| 14 | worktree left clean | `git status --porcelain` empty before and after all my work | REPRODUCED |

---

## Findings

### MAJOR-1 — the worker writes arbitrary provenance into the immutable evidence, and it is hashed

**Where.** `ocr/paddle_rung.py:77` (`block = dict(remote_identity)` in `_runtime_block`) together
with `ocr/paddle_client.py:208` (`mismatched = [name for name in IDENTITY_CHECK_FIELDS ...]`).

**What.** `verify_identity` compares the nine fields it knows about and ignores every other key in
`/version`. `_runtime_block` then copies the WHOLE `/version` payload verbatim into
`ExtractionEvidence.runtime`, which is deep-frozen and folded into `evidence_sha256` — the block the
card says must "NEVER" carry a URL, host, port, token or request id. Whether it does is decided by
the worker, not by this code. M10's mutant (our own code adding `worker_url`) is killed; the
equivalent real path — the worker adding it — is wide open, and CASE 11's assertion passes only
because `FakeWorker` happens not to send extra keys.

**Reproduction** (offline, `PYTHONPATH=. python`, review worktree):

```python
injected = {"worker_url": "http://198.51.100.7:8765",
            "ssh_host": "attacker.example",
            "operator_note": "PP-OCRv6 actually"}
with FakeWorker(identity_overrides=injected,
                result_for=lambda i, b: synthetic_paddle_result(page, dpi=150)) as fake:
    settings = load_paddle_settings(dict(VAST_ENV, PADDLE_WORKER_URL=fake.url))
    client = PaddleClient(settings)
    verify_identity(settings, client=client)          # ACCEPTS
    read = read_document(PDF, document_sha256=SHA, data_scope="synthetic",
                         settings=settings, client=client, dpi=150)
    print(canonical_json(read.evidence.runtime))
```

Observed:

```
verify_identity ACCEPTED a /version carrying unknown keys: ['operator_note','ssh_host','worker_url']
evidence.runtime = {...,"operator_note":"PP-OCRv6 actually",...,"ssh_host":"attacker.example",
                    ...,"worker_url":"http://198.51.100.7:8765"}
contains worker_url: True     contains an IP: True
evidence_sha256 hashes it: FCB9DF02652A981D...
```

**Fix required.** Build the runtime block from an explicit whitelist, not from the worker's reply:
take exactly `IDENTITY_CHECK_FIELDS` + `gpu` + `cuda_compiled` + `python_version` out of
`remote_identity`, then add `provider` / `execution_class` / `worker_contract` / `dpi`. A test that
asserts `set(evidence.runtime) == <the closed set>` against a `FakeWorker` echoing an extra key is
the killer, and it also kills M10 more honestly than the current substring assertion.

### MAJOR-2 — the remote and customer-data authorizations are caller-declared, not re-derived

**Where.** `ocr/paddle_config.py:314–337` (`check_remote_authorization` reads
`settings.remote_opt_in` / `settings.customer_data_opt_in`), `ocr/paddle_rung.py:111–112`,
`ocr/paddle_client.py:123–131` (the constructor re-derives the LOOPBACK property from the URL but
re-derives neither opt-in), `tools/paddle_vast.py:366`.

**What (two halves, one class).**

*(a) The env literals are not re-derived where it matters.* The client's constructor cites MINOR-2's
lesson — "never trust a hand-built settings object" — and applies it to the URL only. The two
literals that gate paid remote execution and customer-document transmission are plain booleans on a
frozen dataclass any in-process caller can set. With neither `PADDLE_REMOTE_OPT_IN` nor
`PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` present in the environment, a hand-built `PaddleSettings`
drives a full `data_scope="customer"` read to completion.

*(b) `data_scope` is an unbacked string.* Nothing ties the declared scope to the bytes actually
passed. `read_document(<archive bytes>, data_scope="synthetic", ...)` is accepted and transmitted.
So, stated plainly: **the DATA PRIVACY BOUNDARY as implemented guarantees that a caller who tells
the truth about its scope, and whose settings came from `load_paddle_settings()`, cannot send
customer bytes to a `remote_paid` worker without the second env literal. It guarantees nothing
against a caller that declares the wrong scope or builds its own settings.** In this tree there is
no such caller (there is no caller at all outside tests and the tool), which is why this is MAJOR
and not BLOCK — but cell R is precisely the caller that will construct both.

**Reproduction** (offline; the environment has neither literal set):

```
env PADDLE_REMOTE_OPT_IN set? False
env PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN set? False
check_remote_authorization(hand_built_settings, "customer") PASSED
read_document(..., data_scope="customer", settings=hand_built) SUCCEEDED; /ocr requests: 1
```

where `hand_built = PaddleSettings(provider="vast.ai", execution_class="remote_paid", ...,
remote_opt_in=True, customer_data_opt_in=True, worker_url=<fake worker>, ...)`.

**Fix required.** (a) `check_remote_authorization(settings, data_scope, *, environ=None)` must
require BOTH the settings flag AND the exact env literal, re-read at check time (`environ` is the
test seam the existing tests need); the same re-derivation belongs in `PaddleClient.__init__`
alongside the loopback re-check, so a client for a `remote_paid` worker cannot even be constructed
without the literal. (b) At minimum, record the declared scope in the evidence `runtime` so a
mis-declaration is auditable after the fact; better, have the rung accept the scope only from a
value the archive loader alone can produce, so "synthetic" cannot be asserted over archive bytes.

### MAJOR-3 — the lifecycle tool prints the host, SSH port and user on a routine failure path

**Where.** `tools/paddle_vast.py:191–201`, `227–234`, `271`, `282` (every `runner(...)` call passes
`timeout=`) and `tools/paddle_vast.py:466` (`main` catches only `PaddleVastError`, `PaddleRefused`,
`PaddleTransportError`).

**What.** `subprocess.TimeoutExpired.__str__` embeds the full command. An ssh call that hangs past
its timeout — a suspended instance, a dropped link — raises it, `main()` does not catch it, and the
unmasked traceback carries `-p <SSH PORT>` and `<USER>@<HOST>` to the terminal, into any log the
operator captured, and from there into anything pasted into a report. The card's §5 says values are
"NEVER printed"; the masking test only inspects the SUCCESS path's return value.

**Reproduction** (placeholder connection values only — never the real ones):

```python
def timing_out_runner(args, **kwargs):
    raise subprocess.TimeoutExpired(cmd=list(args), timeout=kwargs.get("timeout", 30))
vast.cmd_check(load_paddle_settings(PLACEHOLDER_ENV), runner=timing_out_runner)
```

Observed: `TimeoutExpired`, not caught by `main()`'s except clause; host present in the exception
text `True`, ssh port `True`, user `True`:
`Command '['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-p','<PORT>','<USER>@<HOST>', ...]' ...`

**Fix required.** Wrap every `runner(...)` / `popen(...)` call so `subprocess.SubprocessError` and
`OSError` become a `PaddleVastError` carrying only the exception class name, and add
`subprocess.SubprocessError` + `OSError` to `main()`'s except tuple with `mask_text` applied. Add a
test that a timing-out runner produces output containing the placeholder host, never the value.

### MAJOR-4 — the documented lifecycle cannot authenticate, so the measurement record does not reproduce

**Where.** `tools/paddle_vast.py:252–272` (`cmd_start`), `ocr/paddle_client.py:138–139` (the
`Authorization` header comes only from `settings.worker_token`), `docs/.../PADDLE_VAST_RUNBOOK.md`
§Lifecycle, `docs/.../PADDLE_MEASUREMENTS.md` §Commands run.

**What.** `cmd_start` ignores `settings.worker_token`, always mints a fresh
`secrets.token_urlsafe(32)`, exports it to the remote worker and writes it to
`<runtime_dir>/worker.token`. **Nothing in the repository ever reads that file back** (grep: one
write in `cmd_start`, two assertions in tests), and neither the runbook nor the recorded command
list tells the operator to export it. A client configured exactly as the runbook says therefore
sends no bearer token: `/version` answers anyway (see MINOR-1), so `probe()` and `status` report the
worker healthy — and then every `/ocr` returns 401, surfacing as `paddle_worker_unreachable`.

**Reproduction** (offline, against the REAL `ocr/paddle_worker.py` server):

```
settings.worker_token: None
probe() -> True ok          (/version needs no token, so the preflight looks healthy)
/ocr    -> PaddleTransportError paddle_worker_unreachable HTTPError
cmd_start consults settings.worker_token: False
```

**Why it matters beyond ergonomics.** The measurements file records a command sequence
(`start` → `tunnel-up` → live test → `stop && start` → `measure`) that, as written, cannot have
produced the reported numbers. Either an undocumented step exported the token, or the worker in the
measured runs was not token-protected at all. Under the standing rule that every headline number
reproduces from committed evidence, the record must say which.

**Fix required.** `cmd_start` should use `settings.worker_token` when set; when it generates one it
must be loadable — either `load_paddle_settings` reads `<runtime_dir>/worker.token` when
`PADDLE_WORKER_TOKEN` is unset, or `cmd_start` prints the one export line the operator must run
(the token is a per-session secret, so writing it to the gitignored runtime dir and having the
loader read it is the cleaner half). The runbook and the measurements' command list then need the
same step, and the W3 section should state which of the two explanations above is the true one.

---

### MINOR findings

**MINOR-1 — `/health` and `/version` are unauthenticated even when the token is set.**
`ocr/paddle_worker.py:483–491` (`do_GET`); the token check lives only in `handle_ocr_request`
(`:407–414`). The card §1 says "every request must carry `Authorization: Bearer <token>`".
Reproduced: with `build_server(..., token="the-session-token")`, `GET /health` → 200
`{"ok": true, "contract": 1}` and `GET /version` → 200 with the full identity block (GPU model,
driver, versions), both with no `Authorization` header; `POST /ocr` correctly → 401. Impact is
limited to anything with loopback access inside the rented container, but it also masks MAJOR-4.
Fix: apply the same `hmac.compare_digest` check in `do_GET`.

**MINOR-2 — the 30 MP pixel bound does not bite, and the side bound is applied AFTER a full decode.**
`ocr/paddle_worker.py:368–399`. Pillow only *warns* between `MAX_IMAGE_PIXELS` and 2× it; it raises
`DecompressionBombError` above 2×. So (a) a **6000 × 6000 = 36 MP** PNG (15,836 compressed bytes)
passes every bound and reaches the model call — reproduced: `handle_ocr_request` returns
`inference_failed`, i.e. all bounds passed; and (b) a 7000 × 7000 PNG is refused `image_too_large`
only after `Image.load()` has fully decoded it — reproduced with a spy on `PIL.Image.Image.load`:
`Image.load() calls BEFORE the refusal: [((7000,7000),'1'), ((7000,7000),'1')]`. A genuine >2×
bomb (8000 × 8000) IS refused correctly. This contradicts the module docstring's "every bound …
enforced BEFORE the corresponding decode step". Fix: read `Image.open(...).size` and refuse on
`w*h > MAX_IMAGE_PIXELS` and on either side before calling `.load()`.

**MINOR-3 — `measure`'s real-data refusal is case-sensitive, and `--fixture` does not exist.**
`tools/paddle_vast.py:78, 337–343, 430–439`. Reproduced: `'Bank Statements/x.pdf'` refused;
`'bank statements/x.pdf'`, `'BANK STATEMENTS/x.pdf'`, `r'C:\Users\me\Desktop\Bank statements\x.pdf'`
and `'tests/Corpus_Cache/x.pdf'` all ACCEPTED — Windows paths are case-insensitive, so the guard is
a spelling check. Separately, `fixture_path` is used for nothing but this check (`cmd_measure`
always builds the synthetic page in memory) and `main()` exposes no `--fixture` flag, so M12's
killer exercises a parameter no operator can supply. Fix: casefold both sides, add a resolved-path
check (`Path(p).resolve()` against the repo's archive directories) so a symlink or `..` cannot walk
in, and either implement `--fixture` or delete the parameter and say so in the card.

**MINOR-4 — the rung silently truncates a page-count disagreement.**
`ocr/paddle_rung.py:119` (`page_count = min(len(images), pdf_document.page_count)`). Reproduced with
a two-page image-only PDF whose rasteriser returns one image: `pages returned: 1`, `evidence pages: 1`,
`page_extractor: ['paddle-ocr+ppocrv5']`, no refusal — the document is published one page short.
Poppler and PyMuPDF normally agree, so the trigger is a damaged PDF one of them recovers differently
(or any future page cap), but page completeness is a protected invariant and the doctrine is fail
closed. Fix: refuse (`paddle_frame_mismatch` or a third appended reason) when
`len(images) != pdf_document.page_count`; keep the 0-page case as the card specifies.

**MINOR-5 — a contract-shaped-but-wrong 200 response escapes as a bare `KeyError`, and the echoed
`page_index` is never checked.** `ocr/paddle_rung.py:148` (`response["raw"]`), `:145–146`.
Reproduced: a client returning `{"image": {}, "timing": {}}` makes `read_document` raise
`KeyError: 'raw'` — not a `PaddleRefused` and not a `PaddleTransportError`, so a caller matching the
closed vocabulary will not classify it. The worker echoes `request_id` / `page_index` and the rung
ignores both, so a mis-ordered reply would be attached to the wrong page's frame. Fix: validate the
envelope (`raw` present and a mapping, `page_index == index`) and raise
`PaddleTransportError("paddle_worker_unreachable", "MalformedEnvelope")`.

**MINOR-6 — `evidence_sha256` is not reproducible for identical inputs.** Same line as MAJOR-1:
`runtime` carries the worker's `model_loaded` and `worker_started_at`. Reproduced: the same
document, the same words and the same pins produce
`67E41B23…` with `model_loaded=False/worker_started_at=100.0` and `33970CE7…` with
`True/200.0`, while `pages[0]` is byte-identical. On the real worker `model_loaded` flips False→True
at the first `/ocr`, so the first document of a session and every later one are hashed under
different provenance — which is why the live test could not assert the card's "evidence sha stable
across two runs". Fixed by MAJOR-1's whitelist (drop both volatile fields).

**MINOR-7 — the tracked env example pre-enables the remote paid opt-in.**
`.env.paddle.example` line `PADDLE_REMOTE_OPT_IN=I_ACCEPT_REMOTE_PAID_PADDLE_OCR` is uncommented,
while the customer-data literal beneath it is correctly commented out. The runbook tells the
operator to copy the example to a gitignored `.env`, and `ocr/config.py`'s dotenv load puts `.env`
into `os.environ` for every process that imports it — so following the documented setup leaves the
paid-remote opt-in permanently on, defeating the "set it only in the environment of the specific
command" discipline the W3 section claims. Fix: comment the line out and keep the literal in the
comment, exactly as the customer-data line is written.

**MINOR-8 — two measurement rows do not come from the instrument.** (a) `PADDLE_MEASUREMENTS.md`
labels 253,799 bytes as "PNG, base64-encoded, JSON-wrapped"; `tools/paddle_vast.py:380` sets
`bytes_sent = len(png_bytes)`, i.e. the raw PNG. I rebuilt the fixture: `len(png_bytes)` = **253,799**
(the claimed figure exactly), actual `/ocr` body = **338,480** bytes. The number is right; the label
overstates what was measured by understating the wire by 33 %. (b) The GPU rows (7,692 / 32,607 MiB,
0 % utilisation) and the "~262 s worker wall-clock" are not produced by `measure`: `main()` never
passes `gpu_sampler`, and `cmd_measure` contains no `nvidia-smi`, no RSS and no `tracemalloc`
(verified by inspection of the sources). The W3 "risks" paragraph describes "a single point-in-time
`nvidia-smi` read" the tool does not perform. The card's §6 list also lacks peak local RSS, remote
RAM and total GPU-attributable seconds. Fix: either wire the sampler (a `--gpu-sample` that runs the
tool's own ssh `nvidia-smi` and a `tracemalloc`/`psutil` peak) so every published row reproduces from
`measure-<utc>.json`, or label the hand-collected rows as hand-collected and record the exact
commands.

**MINOR-9 — `FakeWorker` does not enforce the contract the real worker does.**
`tests/paddle_fake_worker.py:157–193, 217–235`. Reproduced: a POST with `"contract": 99` and
`base64("not a png at all")` gets **HTTP 200** and a full result envelope from the fake, while the
real `handle_ocr_request` refuses the same body with `contract_mismatch`; the fake enforces no body
bound, no PNG magic, no side/pixel bound, and checks its token only after reading and parsing the
body (the real worker checks it first). `_empty_result` also leaves `"input_path": "fake.png"` in
`raw`, which the real worker pops — so evidence built in tests carries a key (and a path-shaped
string) the real path never produces, and it is inside the hashed `raw`. Cell R's tests will import
this double; the card promised "the SAME contract". Fix: give the fake the real worker's validation
front-end (import `parse_bounded_json` / the contract and PNG checks from `ocr.paddle_worker`) or
document precisely which checks it deliberately omits; drop `input_path` from `_empty_result`.

**MINOR-10 — the adapter coerces a non-string word entry instead of refusing.**
`ocr/paddle_adapter.py:98` (`text_str = str(text_value)`). Reproduced: `text_word = [[1234.56]]`
yields a `WordBox` whose text is `'1234.56'` and a page line `'1234.56'` — a number-shaped token
manufactured from a malformed result by `str()`. CASE 8 covers a non-list `text_word` but not a
non-string entry. Fix: refuse (`PaddleAdapterError`) unless the entry `isinstance(..., str)`.

**MINOR-11 — `test_m1_...` is a source-substring scan and can be satisfied by a comment.**
`tests/test_paddle_client.py:236–246` greps `inspect.getsource(read_document)` for three names.
Observed during my M1 run: the mutant's own comment mentioned `check_remote_authorization`, so this
test PASSED on a rung with the call deleted (the two rung tests killed the mutant, as claimed — the
mutation table's conclusion is unaffected). Fix: make it a runtime spy
(monkeypatch `paddle_rung.check_remote_authorization` and assert it was called before the client was
constructed), or delete it as redundant.

**MINOR-12 — two test-hygiene items.** (a) `tests/test_paddle_client.py:253–261` calls
`probe(settings=None)`, which reads the REAL `os.environ`; on a developer machine where the Paddle
config and the opt-in literal are both set, the default suite will open a loopback connection to the
tunnel port. Pass an explicit empty environ instead. Line 254
(`status = probe(...) if False else None`) is dead code. (b) `tests/test_paddle_live.py:35–51`
evaluates `_live_ready()` — and therefore `probe()` — at collection time, guarded first by the
literal; correct as written, but it means the default suite's behaviour depends on ambient env.

---

## What I attacked and could not break

* **Missing or bypassable remote opt-in on the loader path.** Every route into a request that starts
  from `load_paddle_settings()` passes `check_remote_authorization` first: the rung (order pinned by
  code and by the M1 mutant), `probe()` (before any socket), `cmd_measure` (before the client is
  built). No rasterisation, no PNG encoding and no `fitz.open` happens before the gate — I checked
  the ordering by mutation, not by reading. The visual rung's literal (`I_ACCEPT_REMOTE_PAID_OCR`)
  does not enable Paddle; the exact-`==` comparison rejects `"yes"` and every truthy value.
* **Localhost misclassified as local.** `classify_endpoint` is used in exactly two places and only
  ever to REFUSE a non-loopback URL; the execution class comes from the declaration and is
  corroborated by the worker. I could not find any code that reads the class off a hostname. The
  `vast.ai⇒remote_paid` / `local⇒local_free` pairing is enforced at both ends (`load_paddle_settings`
  and the worker's `resolve_identity`), and the M2 mutant proves all nine `/version` fields are
  compared independently.
* **A second host / a fallback / a redirect hop.** The M4 mutant (retry to
  `http://localhost:8000/v1`) is caught by a URL-spying opener that records every `open()`; redirects
  raise instead of following; `HTTPError` is never retried; the URL is rebuilt from
  `settings.worker_url` on every attempt and cannot be mutated in flight.
* **Hardcoded connection information or credentials.** Scanned the whole diff, the runbook, the
  example env, the measurements file, the W3 section and all 14 commit messages against the live
  values: host 0, port 0; the only user-value hit is ordinary English prose. No `user@host` shape, no
  API key, no private key, no token literal other than the obviously fake `s3cr3t-token` in tests.
  `.paddle_runtime/` (pidfiles, the session token, `measure-*.json`) is gitignored.
* **Production customer data reachable by this code.** There is no file read anywhere on the Paddle
  path: `cmd_measure` builds its page in memory, `paddle_synthetic` renders from literals, and
  nothing accepts a document path. The archive is unreachable from these modules as written. (What
  the boundary does and does not guarantee against a dishonest caller is MAJOR-2.)
* **Paddle becoming a financial parser or a confidence filter.** No amount, date, sign, balance or
  currency reasoning exists in the four modules. The M7 mutant (drop words below 0.5) dies at both
  score extremes; `page_text` is built from geometry and carries no score; `rec_texts` is
  length-checked and otherwise unused, and the M6 mutant that joins it dies on the two-column page.
* **Raw evidence mutation and box laundering.** `WordBox`/`PageEvidence` refuse inverted, degenerate
  and out-of-raster boxes, and the M5 clamping mutant dies on both the out-of-raster and the inverted
  test. `raw` is deep-frozen and hashed; the JSON round-trip reproduces both `raw_sha256` and
  `evidence_sha256`.
* **Worker hardening.** The loopback bind is enforced at two independent points (both mutated, both
  killed); `0.0.0.0`, `::`, `localhost` and a LAN address are all refused. The 32 MiB body bound is
  enforced from the `Content-Length` header before a byte is read (a request declaring 33 MiB and
  sending two bytes gets a prompt 413), the depth guard runs before `json.loads`, base64 uses
  `validate=True`, PNG magic is checked before Pillow sees the bytes, the token compare is
  `hmac.compare_digest`, error tokens are a closed set that refuses an unknown member at
  construction, no traceback or content ever reaches the wire, nothing is written to disk, and the
  one log line per request carries only ids, dimensions, status and milliseconds.
* **Statement-specific hardcodes.** The five canonical guards (OQ2 scan covers `ocr/*.py`) are green
  at this tip; guards + conformance = 1,549 passed, `tests/test_escalation_tripwires.py` and
  `tests/test_evidence_boundary.py` green (278 passed together with the guards).
* **`ocr/paddle_config.py`.** Purely additive: two members appended to `REFUSAL_REASONS` plus a
  comment. No existing constant, vocabulary or literal changed.

**Residual risk worth recording (not a finding).** Identity is verified once, before page 1;
per-page `/ocr` results are trusted thereafter, and the `"model"` block the worker attaches to each
`/ocr` response is never compared against the pins. A worker that answered `/version` honestly and
then ran a different model would not be detected within a document. That is inherent to the design
the card specifies; MAJOR-1's whitelist plus a cheap per-response check of the echoed `model` block
against the verified identity would close it.

## Live

I did **not** make a live check over the real tunnel. No finding required one: every finding above
reproduces offline against the real `ocr/paddle_worker.py` handler, the real client and the real
rung. MAJOR-4 is the one place where a live observation would settle a question — whether the
measured runs were token-protected — but that question is for the cell to answer in its record, not
for a second paid worker start. `PADDLE_REMOTE_OPT_IN` was never set in any command I ran, the
customer-data literal was never set, and nothing I ran opened a socket beyond `127.0.0.1` on
ephemeral ports.

## Re-review gate

MAJOR-1 through MAJOR-4 close pre-compose, each with the named test. MINOR-1, MINOR-2, MINOR-4,
MINOR-5, MINOR-7 and MINOR-9 should close with them (they are all one- to five-line changes and
MINOR-9 affects what cell R's tests can prove). MINOR-3, MINOR-6 (folded into MAJOR-1), MINOR-8,
MINOR-10, MINOR-11 and MINOR-12 may close in the same pass or be carried into cell R's card with a
line in the W3 record. Re-review must re-run the twelve Paddle test files, the mutation table and
the secrets scan.
