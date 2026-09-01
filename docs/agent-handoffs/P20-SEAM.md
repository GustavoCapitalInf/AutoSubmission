# Agent Handoff — P20-SEAM (Phase 2.0 cell B2: provenance-token injection closed, the endpoint allowlist / $0 default enforced, legacy OCR entry points retired)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (OQ3 = ALLOWLIST, OQ6, OQ7), then
`OCR_LEGACY_AUDIT.md` F-4 / F-7 / §2.4 and the review's MAJOR-2 / MINOR-3, then
`PHASE2_ARCHITECTURE_PLAN.md` §5 and §15, then the umbrella `PHASE2-0-SAFETY.md`. Ocean reviews and
composes; you never merge or push. **Hygiene card: `newly validated = 0`; previously validated
preserved, payload identical.** Nothing makes a network call; no paid service is enabled.

# Why
`OCR_MODEL` is a plain env read (`ocr/config.py:29`) stamped into the first line of the analysis input
(`ocr/document.py:38-41`); `SOURCE_COMMENT_RE` is MULTILINE not DOTALL, so a newline in the token
injects arbitrary text — a money token included — into `admissible_text` (reproduced end to end).
`OCR_BASE_URL` is a plain env read with no allowlist, so the "$0 / no paid vendor" invariant asserted
by `ocr/availability.py:5-6` is enforced by nothing, and four entry points default `allow_visual_ocr
=True`. `source_path_for`'s fallthrough is `"visual"`. Gustavo ruled: closed charset, allowlist in
code, explicit recorded opt-in for remote/paid, no silent hop, legacy entry points retired.

# Design (ruled — do not re-decide)
1. **Closed provenance tokens (`ocr/config.py` + `ocr/document.py`).**
   * `MODEL_TOKEN_RE`: first character alphanumeric; then only `[A-Za-z0-9._/+-]`; length 1–64; NO
     whitespace of any kind, NO control characters, NO `<`, `>`, `!`, `$`, `,`, quotes, backslash. It
     therefore cannot contain a newline, CR, `-->`, HTML/markup, a `<|det|>`-style marker, or a
     `[\d,]+\.\d{2}` money token with a thousands separator; additionally REFUSE any token containing
     a money-shaped substring `\d+\.\d{2}(?!\d)` (e.g. `v1.00`) and any token equal to or starting
     with a RESERVED deterministic-rung prefix: `native-pdf-text`, `local-tesseract-ocr`,
     `deterministic-native-preflight` (an env value must not impersonate a native read — that would
     spoof `source_path_for`, the cost table, and cell D's Q3 native-only gate).
   * `load_settings()` VALIDATES `model` (env or override) and raises a typed `ProvenanceTokenError`;
     `probe_visual_ocr` reports it as `usable=False` with `error_type` = the class name (console-only
     detail, as today); the ladder treats it as the rung being unavailable (fail closed: no read).
   * `StatementMarkdown`: `to_markdown()` must still not add a byte for VALID inputs (the corpus
     artifacts pin it), so validation lives in `__post_init__`: `model` must be `""` (the cache
     reconstruction's empty value) or match the charset (reserved prefixes are ALLOWED here — the
     native rungs set them legitimately); `source_file` must contain no `\r`/`\n` (raise — a filename
     with a line break is not a filename). A test proves every committed corpus artifact and every
     `native-pdf-text+<layout>` / `local-tesseract-ocr` token passes unchanged.
   * **Hostile regression tests** (`tests/test_ocr_provenance_injection.py`) — for BOTH `OCR_MODEL`
     and `source_file`, inputs containing: `\n`, `\r\n`, `-->`, `<`, `>`, a money literal, a
     bank/parser-like marker (use the registry's own detection-marker text of one parser), a
     `<|det|>` tag, a `<!-- source:` fragment, whitespace, an over-length token. Each must be REFUSED
     at the point the token is set; and an end-to-end proof that `admissible_text(to_markdown())`
     for every accepted token contains no character of the token (the header is stripped whole).
     Reproduce the audit's injection FIRST on the base tree (a failing test), then close it.
2. **Endpoint policy (`ocr/endpoint_policy.py`, new).** `classify_endpoint(base_url) ->
   EndpointClass` over the URL's scheme + host: `loopback` (`localhost`, `127.0.0.0/8`, `::1`),
   `private` (RFC 1918 / link-local / ULA / a `.local` name — http or https), `remote` (anything
   else, including every public name such as `*.runpod.net`), `invalid` (unparseable, non-http(s)).
   `check_endpoint(base_url, *, opt_in: bool) -> EndpointDecision(allowed, klass, reason)`: loopback
   and private are allowed by default; remote is allowed ONLY when `opt_in` is True; invalid is never
   allowed. `opt_in` is read from ONE env var `OCR_REMOTE_OPT_IN` whose accepted value is the exact
   literal `I_ACCEPT_REMOTE_PAID_OCR` (anything else is False) — deliberate, not `1`. Enforcement
   points: `load_settings()` records `endpoint_class` and `remote_opt_in` on `Settings`;
   `ocr_client._build_client` and `availability.probe_visual_ocr` call `check_endpoint` and REFUSE
   (typed `EndpointRefused`) before constructing a client or sending anything; `ocr/pipeline.py`'s
   visual rung is reached only through `_build_client`, so a refusal there ends the rung (fail
   closed). There is exactly ONE visual endpoint per process: no second URL, no fallback list, no
   retry against another host — a test proves that a failing loopback endpoint yields the rung's
   failure and never a request elsewhere (a fake client counts constructions per base_url).
   Provenance: `telemetry/record.py::model_calls_for` / the OCR settings surface must carry
   `endpoint_class` and `remote_opt_in` (the cache key already carries `ocr_base_url`; cell C adds
   the key material — you expose the values on `Settings`, C keys on them). `FREE_MODELS` unchanged;
   `price_for` on a remote endpoint returns `None` (unknown) unless a cited price exists — do not add
   one.
3. **`source_path_for` fallthrough closed.** The final branch returns `"visual"` ONLY for the
   configured Unlimited model token class (`baidu/Unlimited-OCR` and any token registered in a new
   closed `VISUAL_MODEL_TOKENS` set); any other token returns `"none"` AND the record carries
   `source_path_unrecognized_model: true` in `diagnostics` — a forgotten branch is a visible defect,
   not a silent mis-attribution (F-7). `SOURCE_PATHS` itself is unchanged in 2.0 (PaddleOCR adds its
   member in 2.1). Cell A owns `FAILURE_CLASSES` / `EXTRACTION_TRIGGERS` in the same module; touch
   ONLY `source_path_for` and its helpers.
4. **Legacy entry points (OQ7).** Salvage first: `triage_scan.py`'s `CHECKS` dict becomes
   `tests/test_ocr_defect_signatures.py` — each signature as a synthetic fixture asserting the
   detector that replaces it (`looks_missegmented`, the truncation signals, or a documented "no
   detector; recorded as a known visual-output defect" note). Then: `parse.py` and `batch.py` default
   to `allow_visual_ocr=False` (the offline ladder only) and gain an explicit `--visual` flag that
   goes through `probe_visual_ocr` + the endpoint policy (a refusal prints one console line and exits
   non-zero; nothing is sent); `sweep_ocr.py`, `triage_scan.py`, `coverage_audit.py`,
   `deterministic_coverage_audit.py` are DELETED (`git rm`) with their `corpus_gate.EXCLUDED_ANALYSIS_CALLERS`
   entries removed and `tests/test_native_rung_parity.py`'s `LADDER_BINDINGS` updated (it pins
   `deterministic_coverage_audit.py` as a ladder consumer — the guard must still assert the remaining
   consumers exactly). `local_ocr_server.py`, `serve_local.sh`, `run.ps1`, `requirements-local.txt`
   stay (the $0 vendor). Confirm with `git grep` that nothing imports the deleted modules.
5. **README (OQ6).** The RunPod section is retitled "Optional PAID remote escape hatch — never
   automatic" and states the opt-in literal, that the run records `endpoint_class=remote`, and that
   no production mode reaches it; the local server section becomes the documented default.

# Mutation table (minimum)
| mutant | killer |
|---|---|
| charset allows `\n` | the newline hostile test |
| charset allows `>` | the `-->` hostile test |
| reserved prefix accepted from env | the impersonation test (`OCR_MODEL=native-pdf-text`) |
| `source_file` with `\n` accepted | the filename hostile test |
| `check_endpoint` returns allowed for `remote` without opt-in | CASE 8 |
| `OCR_REMOTE_OPT_IN=1` accepted | the exact-literal test |
| `_build_client` constructed before `check_endpoint` | the refusal-before-request test |
| loopback failure retried against a second URL | the single-endpoint test |
| `source_path_for` returns `"visual"` for `paddle+x` | the fallthrough test |
| `parse.py` defaults `allow_visual_ocr=True` | the CLI default test |

# Measurements to report
Hostile inputs tested (list) · endpoint classes tested (list) · the audit injection reproduced at
base then killed · cohort replay at base (`--expect-identical`) and at closure over the 6 committed
corpus artifacts' shas + the 179 Tesseract shas + a 50-sha native sample (private list; exit 0; 0
newly validated; preserved identical — `to_markdown` byte-identical for every valid token) · the
deleted scripts and every reference removed · mutation table · privacy 0 · message scan 0 · tests
added · targeted suite · guards.

# Ownership
`ocr/config.py`, `ocr/document.py`, `ocr/availability.py`, `ocr/endpoint_policy.py` (new),
`ocr/ocr_client.py` ONLY at `_build_client` (B1 owns the rest of that file — coordinate through
Ocean if the hunk must grow), `telemetry/prices.py`, `telemetry/record.py` ONLY `source_path_for`
and its helpers, `parse.py`, `batch.py`, `sweep_ocr.py`, `triage_scan.py`, `coverage_audit.py`,
`deterministic_coverage_audit.py`, `README.md`, `corpus_gate.py` (register entries for the deleted
scripts only), `tests/test_native_rung_parity.py` (binding list), `tests/test_ocr_provenance_injection.py`
(new), `tests/test_ocr_endpoint_policy.py` (new), `tests/test_ocr_defect_signatures.py` (new),
`tests/test_filename_boundary.py` (if a pin moves), W3 `§P20SEAM`. NOT yours: `ocr/pipeline.py`,
`ocr/render.py` (B1); `discovery/*`, `webapp/*` (A, C, D); `analysis/*`.

# Exclusions
No PaddleOCR token or `SOURCE_PATHS` member. No paid price entry. No remote endpoint exercised in any
test (fake clients only). No change to the ladder. No weakening of provenance: every token that is
valid today stays valid and byte-identical in the header.

# Git
Base `train10` at your handoff's commit. Branch `wave20-seam`, worktree `.claude/worktrees/mt20-seam`.
