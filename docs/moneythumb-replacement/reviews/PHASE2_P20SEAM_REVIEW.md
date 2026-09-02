# PHASE2 P20-SEAM — independent adversarial review

```
BRANCH        wave20-seam @ df0e637   (reviewed detached in .claude/worktrees/rev20-seam)
BASE          train10 @ bea06bc
DIFF          git diff bea06bc..df0e637   (24 files, +1,678 / -838)
REVIEWER      independent agent; did not write this code
HOST          Python 3.14.5 (CI pins 3.12); tree clean before and after every mutant
VERDICT       BLOCK
```

Everything below was reproduced by this reviewer in the review worktree. `git status --porcelain`
was empty before every mutant, after every mutant (restored with `git checkout -- <file>` in a
`finally`), and at the end of the session. No network call was made in any experiment: the CLI
refusal reproduction ran with `socket.socket` / `socket.create_connection` / `socket.getaddrinfo`
replaced by a raising sentinel, and every client in every test is a fake. The cold caches under
`.claude/recovery/` were opened `mode=ro` only.

Headline: **the closed charset is not closed.** `MODEL_TOKEN_RE` is anchored with `$`, which in
Python matches before a trailing newline, so a model token ending in exactly one `\n` is accepted by
`validate_model_token`, by `load_settings()` (env and `--model`), and by
`StatementMarkdown.__post_init__`. The audit's F-4(b) content injection is fully reopened through
that one character, and the attacker-supplied `source_file` — which this cell deliberately leaves
uncharsetted — rides through with it. Reproduced end to end below.

---

## 1. Claim-by-claim (claimed → measured)

| # | cell's claim (W3 `§P20SEAM`) | measured | verdict |
|---|---|---|---|
| 1 | `MODEL_TOKEN_RE` "structurally excludes all whitespace (so `\n`, `\r`, a plain space)" (`ocr/config.py:29-31`, W3 §Solution 1) | 78-case battery: every mid-string whitespace/control/unicode-separator/zero-width/RTL/NUL/tab/FF/VT/U+2028/U+2029/U+0085 case refused — **but a single TRAILING `\n` is ACCEPTED**, on all three entry points, and a 65-character token is accepted when its 65th character is that `\n` | **FALSE — BLOCK-1** |
| 2 | "the base-tree reproduction … raises `ProvenanceTokenError` before `to_markdown()` is ever called" | true for the exact string the docstring names; **false for the same attack shaped as `model="evil-model\n"` + a money-carrying `source_file`** — the header splits over two physical lines and `admissible_text` strips nothing | **partially true — BLOCK-1** |
| 3 | reserved-prefix refusal on env-supplied tokens | `native-pdf-text`, `native-pdf-text+x`, `native-pdf-textX`, `local-tesseract-ocr`, `local-tesseract-ocrX`, `deterministic-native-preflight` all refused with `allow_reserved=False`, all accepted with `allow_reserved=True`. Case variants (`NATIVE-PDF-TEXT`, `Local-Tesseract-OCR`, `LOCAL-TESSERACT-OCR`) are **accepted** — correct, since `source_path_for` is case-sensitive too, so they cannot impersonate | **confirmed** |
| 4 | money-shape refusal | `v1.00`, `x-1.00`, `1.00e3`, `model-1.00` refused; `v5,000.00` refused by the charset (comma); `1.005`, `1.0005`, `100.0`, `v.00` accepted — none of which is a two-decimal money literal | **confirmed** |
| 5 | `source_file` refuses `\r`/`\n` only; everything else "ACCEPTED but proven to leave no trace in `admissible_text`" | reproduced. SURFACES BLOCK-1's payload (`statement.pdf \| pages: 1 \| model: native-pdf-text \| empty: 0 -->`) is accepted by the writer, emits a one-line header, and `admissible_text` strips it **whole** — the payload does not reach the analysis text | **confirmed** (see §3 for the writer-side judgment) |
| 6 | `to_markdown()` untouched; "every valid token stays byte-identical in the header" | all **9** distinct `document.model` values across the **3,364** OCR artifacts of `webapp_data_train9_cold` (`native-pdf-text` 2,758 · `+wells` 222 · `local-tesseract-ocr` 179 · `+printed-rows` 83 · `+navy-federal-layout` 48 · `+first-citizens-layout` 36 · `+woodforest-columns` 19 · `""` 13 · `+desjardins-layout` 6) construct without raising and produce a header byte-identical to `bea06bc`'s `to_markdown`. **0 refused, 0 mismatches** | **confirmed** |
| 7 | `_build_client` calls `check_endpoint` BEFORE importing `openai` or constructing anything | read at `ocr/ocr_client.py:399` (check) vs `:403` (`from openai import OpenAI`); mutant R1 (check moved after construction) killed; measured contrast in the CLI run: a refused endpoint raises `EndpointRefused` with no transport, an allowed one reaches `APIConnectionError` | **confirmed** |
| 8 | "`probe_visual_ocr`'s default path reaches this through `_build_client`, so the probe inherits the same refusal" | confirmed — `ocr/availability.py` is **not in the diff**; the refusal arrives as `available=False, error_type="EndpointRefused"`. The card asked the probe to call `check_endpoint` itself; it does not (MINOR-1) | **confirmed with a deviation** |
| 9 | "exactly one endpoint per process … no fallback list, no retry against a second host" | `grep` over the whole tree: exactly one `OpenAI(` construction, in `_build_client`; its two callers (`ocr/pipeline.py:98`, `ocr/ocr_client.py:452`) pass the same `Settings`. Cell mutant 8 (second hardcoded URL) re-applied → 3 tests red | **confirmed** |
| 10 | `OCR_REMOTE_OPT_IN` is the exact literal only | 16-value battery: only `I_ACCEPT_REMOTE_PAID_OCR` is True; lowercase, leading/trailing space, trailing `\n`, tabs, `1`/`true`/`TRUE`/`yes`/`on`, and the literal-plus-suffix all False | **confirmed** |
| 11 | "`Settings` gains `endpoint_class` / `remote_opt_in` … the enforcement re-derives the class fresh from `base_url` rather than trusting the field" | `endpoint_class` re-derived (mutant R5 killed). **`remote_opt_in` IS trusted verbatim** from the field — half of the docstring's claim (MINOR-2). No production path builds a `Settings` by hand: `load_settings` is the only constructor outside tests | **half-true — MINOR-2** |
| 12 | provenance: "the run records `endpoint_class=remote` / `remote_opt_in=true`" (README + W3 §Solution 5) | `grep -rn "endpoint_class\|remote_opt_in" telemetry/ discovery/ webapp/ tools/` at this tip → **0 hits**. Cell C (`wave20-artifacts`) adds `endpoint_class` to the OCR **cache-key fingerprint hash** only (`webapp/artifact_cache.py:811`, `getattr(..., "endpoint_class", "loopback")` — attribute name matches) and never `remote_opt_in`. `model_calls_for` carries neither | **FALSE at this tree — MAJOR-2** |
| 13 | `classify_endpoint` is structural, never a network call | 55-URL battery with `socket.getaddrinfo` / `gethostbyname` spied: **0 resolution calls**. `localhost.evil.com`→remote, `evil.com.localhost`→remote, `10.0.0.1@evil.com`→remote, `user:pw@localhost`→loopback, `file:`/`ftp:`/`ws:`/`""`/`http://`→invalid, `172.32.0.1`/`100.64.0.1`/`8.8.8.8`/`*.runpod.net`→remote | **confirmed** (with MINOR-5/6/7 caveats) |
| 14 | `source_path_for` fallthrough closed | `baidu/Unlimited-OCR`→`visual`; `unlimited-ocr+x`, `paddle+x`, `qwen2.5-vl-7b`, `baidu/unlimited-ocr` (case)→`none` with `source_path_unrecognized_model=True`. Cell mutant 9 killed | **confirmed** |
| 15 | `source_path_unrecognized_model` "a caller can use" | **zero callers anywhere in the tree.** And the closure silently degrades `model_calls_for`: a real 4-page visual read on a non-default token now records `purpose:"none", calls:1, completion_tokens:None` instead of `purpose:"visual_ocr", calls:4, completion_tokens:400` | **F-7 half-closed — MAJOR-3** |
| 16 | `telemetry/prices.py` unchanged; `price_for` never guesses | file not in the diff; `price_for("some-remote-vendor-model")` → `None` | **confirmed** |
| 17 | four scripts deleted with every reference removed | `git show --stat e61f928` / `615a617`: `sweep_ocr.py`, `triage_scan.py`, `coverage_audit.py`, `deterministic_coverage_audit.py`, `tests/test_deterministic_coverage_audit.py` removed. `git grep` over the WHOLE tree (docs, tools, .github, README, corpus_gate.py, tests): **0 imports, 0 executable references**; the 11 remaining mentions are prose in other cards' frozen records. `.github/workflows/corpus-gate.yml` names none of them | **confirmed** |
| 18 | `triage_scan.CHECKS` salvaged in full | all **7** keys present in `tests/test_ocr_defect_signatures.py:33-44`, every regex byte-identical to `git show bea06bc:triage_scan.py:8-21`; 5 asserted closed by a detector, 2 asserted as known-undetected, plus a set-equality tripwire | **confirmed** |
| 19 | `tests/test_revenue_classification.py`'s inlined `_status` is byte-identical | compared line-for-line against `git show bea06bc:coverage_audit.py:45-57` — **identical body** | **confirmed** |
| 20 | the two removed `test_native_text_unreadable.py` tests pinned only the deleted script's CSV row | confirmed: both called `deterministic_coverage_audit.audit_file` and asserted keys (`native_status`, `deterministic_status`, `integrity_flags`) that exist only in that script's row. `text_layer_refusal` keeps its two direct tests above them; no production reader of the deleted row exists | **confirmed** |
| 21 | `parse.py` / `batch.py` default offline; `--visual` probes + policy-checks before any bytes are sent | reproduced with the network hard-disabled: `parse.py --visual` on a remote/invalid/empty endpoint → one stderr line + **exit 3**; `batch.py --visual` → **SystemExit 1**; `parse.py` with no `--visual` and a RunPod `OCR_BASE_URL` → offline only, exit 1, no socket. `ocr/pipeline.py:98` builds the client BEFORE `rasterize_pdf` (~:130), so a refusal precedes any raster | **confirmed** |
| 22 | `local_ocr_server.py`, `serve_local.sh`, `run.ps1`, `requirements-local.txt` stay | none appear in the diff | **confirmed** |
| 23 | "cohort replay … exit 0 … previously validated preserved, payload identical" | reproduced at `df0e637` over the card's 6 corpus-artifact shas + 179 Tesseract shas (the 6 are a subset, so the population is **179**), `--expect-identical`: **exit 0**; newly validated **0**; other movement **0**; previously validated preserved **36/36 payload identical**; unchanged non-validated **143**; runtime 57s. Matches the run of record's Tesseract split (36/15/5/123) exactly | **confirmed** |
| 24 | mutation table 10/10 killed | **7 of the 10 re-applied by this reviewer plus 8 of my own = 15 mutants.** 13 killed. **2 of mine SURVIVED** (R2, R9 — see MAJOR-1). Cell mutant 7's killer is order-dependent (MINOR-3) | **the cell's 7 confirmed; the table is INCOMPLETE — MAJOR-1** |
| 25 | 117 new tests (62 / 46 / 9), +4 `test_cli.py`, +1 `test_telemetry.py` | collected: 62 / 46 / 9; `test_cli.py` 8 (base 4), `test_telemetry.py` 64 (base 63) | **confirmed** |
| 26 | `tools/ocr_legacy_census.py --tree` now exits 2 (disclosed follow-on) | reproduced: **exit 2**. Unwired into any test | **confirmed (disclosed)** |
| 27 | ownership respected | `ocr/ocr_client.py` — exactly ONE hunk, at `_build_client`. `ocr/pipeline.py`, `ocr/render.py` — untouched. `telemetry/record.py` — only `VISUAL_MODEL_TOKENS`, `source_path_for`, `source_path_unrecognized_model`. Nothing under `analysis/`, `discovery/`, `webapp/`. `corpus_gate.py` — the two register entries only. **Not on the card's list and changed anyway:** `tests/test_privacy3_boundaries.py` (a canonical privacy pin), `tests/test_telemetry.py`, `tests/test_cli.py`, `tests/test_revenue_classification.py`, `tests/test_native_text_unreadable.py` — all forced consequences, and the privacy pin is strictly STRENGTHENED (per-file `message()` call counts, still stderr-only) | **confirmed, with an ownership note (MINOR-4)** |
| 28 | diff is "28 files" (review brief) | measured **24 files changed, 1,678 insertions, 838 deletions** | **minor discrepancy, no consequence** |

Not verified by me (the brief forbids them on a shared host): the full default suite (7,931), `corpus_gate.py`, `pytest -m corpus`, the privacy/message scans.

---

## 2. Findings

### BLOCK-1 — `MODEL_TOKEN_RE` accepts a trailing newline; F-4(b) is reopened, not closed

**Where:** `ocr/config.py:37`

```python
MODEL_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/+-]{0,63}$")
```

`$` in Python matches at end-of-string **or immediately before a trailing newline**. `re.match` with
`^…$` is therefore not a full-string anchor. Every claim built on this pattern — the module docstring
(`ocr/config.py:29-31`, "structurally excludes whitespace of any kind (so a newline, CR, or a plain
space)"), the test module docstring, PHASE2_RULINGS' "closed character set (no newline, CR, …)", and
the card's "length 1–64; NO whitespace of any kind, NO control characters" — is false for one shape:
a token whose last character is `\n`.

The consequence is the whole of F-4(b). Reproduced end to end (`PYTHONPATH=$PWD`, review worktree at
`df0e637`):

```python
from ocr.config import validate_model_token, load_settings
from ocr.document import StatementMarkdown
from analysis.parser_registry import admissible_text
import os

validate_model_token("evil-model\n", allow_reserved=False)   # returns the token — NO raise
os.environ["OCR_MODEL"] = "evil-model\n"
load_settings().model                                        # -> 'evil-model\n'

doc = StatementMarkdown(
    source_file="5,000.00 WIRE TRANSFER FROM SHELL CORP.pdf",   # attacker-supplied filename
    model="evil-model\n",
    pages=["page one text"],
)
adm = admissible_text(doc.to_markdown())
```

Measured:

```
A) validate_model_token(..., allow_reserved=False) on a token with ONE trailing newline
   -> ACCEPTED  (ascii: 'evil-model\n')
B) load_settings() with OCR_MODEL carrying the same trailing newline
   -> ACCEPTED; settings.model = 'evil-model\n'
C) StatementMarkdown construction + to_markdown + admissible_text
   header line count of the emitted comment: 2
     | <!-- source: 5,000.00 WIRE TRANSFER FROM SHELL CORP.pdf | pages: 1 | model: evil-model
     |  | empty: 0 -->
   money token survives admissible_text: True
   'WIRE TRANSFER FROM SHELL CORP' survives: True
   '<!-- source:' survives: True
D) control: the SAME source_file with a VALID (no-newline) model token
   money token survives: False
   admissible_text: '\n--- Page 1 ---\n\npage one text\n'
```

`SOURCE_COMMENT_RE` (`^<!--\s*SOURCE:.*?-->\s*$`, MULTILINE, not DOTALL) needs the comment on one
line. The trailing `\n` splits it, nothing is stripped, and the **filename** — which this cell
deliberately leaves free of any charset — delivers the money literal and the marker-shaped text into
`admissible_text`, i.e. into the text every parser's detection markers scan and every text metric
runs over. That is exactly the reproduction the W3 §Correctness-evidence section says is closed.

The 64-character bound is bypassed by the same defect:

```
len 65 over-length token + trailing newline:  -> ACCEPTED (65 chars)
```

**Reachability is not theoretical.** `ocr/config.py:14` calls `load_dotenv()` at import, and
python-dotenv preserves a quoted multi-line value:

```
.env:  OCR_MODEL="qwen2.5-vl-7b
       "
measured: dotenv parsed OCR_MODEL = 'qwen2.5-vl-7b\n'  -> ACCEPTED by validate_model_token
```

The same token also reaches `parse.py --model`, `parse_statement(model=…)` and `ocr/pipeline.py:92`.
And `ocr_settings_key` (`webapp/artifact_cache.py:589`) calls `load_settings()` on **every** cached
OCR read, offline included — so this token is live on the offline path too, not only when the visual
rung runs.

**Why the suite misses it.** `ISOLATED_HOSTILE_MODEL_INPUTS["newline"]` is `"evilmodel\nvalidsuffix"`
and `HOSTILE_MODEL_INPUTS["newline"]` ends in text — both are MID-string newlines, which `$` correctly
rejects. No fixture ends in the hostile character. The cell's mutation-table entry "charset allows
`\n`" widened the class and was killed by the mid-string fixture, so the table's kill is honest but
does not cover the anchor.

**Fix I would accept** (one line, plus two fixtures):

```python
MODEL_TOKEN_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._/+-]{0,63}\Z")
```

(or `MODEL_TOKEN_RE.fullmatch(token)`), plus `ISOLATED_HOSTILE_MODEL_INPUTS["trailing_newline"] =
"evilmodel\n"` and an over-length case `"a"*64 + "\n"`, and a mutation-table row "anchor relaxed from
`\A…\Z` to `^…$`" with those fixtures as the named killer. I applied the fix as mutant R6 and ran
`tests/test_ocr_provenance_injection.py tests/test_ocr_endpoint_policy.py tests/test_telemetry.py
tests/test_pipeline.py tests/test_visual_rung.py tests/test_filename_boundary.py`: **356 passed,
exit 0** — the fix costs nothing and breaks nothing. The 9 cold-cache tokens are unaffected (none
ends in whitespace).

---

### MAJOR-1 — the endpoint allowlist has no look-alike-hostname killer: two of my mutants survive the whole 46-test policy file

**Where:** `ocr/endpoint_policy.py:78` and `:80`; `tests/test_ocr_endpoint_policy.py:36-60`.

PHASE2-RULES' proof floor requires "a mutation table for every gate, router edge, **charset,
allowlist** or selection rule you add — every mutant applied as documented, every killer named". The
allowlist's canonical bypass — a public hostname that merely *looks* local — has no test at all. The
parametrized `classify_endpoint` table has 23 entries and not one of them is a look-alike:
`localhost.evil.com`, `evil.com.localhost`, `evil.local.attacker.com`, `10.0.0.1@evil.com` are all
absent.

**Reproduction** (each mutant applied alone, `tests/test_ocr_endpoint_policy.py` run in full,
restored with `git checkout --`, tree verified clean before and after):

```
R2 classify_endpoint treats any host CONTAINING 'localhost' as loopback
     if "localhost" in host:  →  return "loopback"
   exit=0   46 passed        *** SURVIVED ***

R9 .local suffix widened to any host CONTAINING '.local'
     if ".local" in host:     →  return "private"
   exit=0   46 passed        *** SURVIVED ***
```

Under R2, `check_endpoint("http://localhost.evil.com/v1", opt_in=False).allowed` is `True`; under R9,
so is `http://evil.local.attacker.com/v1`. Both post page images to an attacker-chosen public host
with no opt-in and no test turning red. The shipped code is correct today (`host == "localhost"`,
`host.endswith(".local")`) — the finding is that nothing holds it there, which under this phase's own
rules is the same defect as not having written it.

A third mutant of mine, R7 (classify on `netloc` including userinfo instead of `hostname` — the
`http://10.0.0.1@evil.com/v1` shape) **was** killed, but only incidentally, by the three IPv6
bracket cases; no userinfo case exists either.

**Fix I would accept:** add to the `test_classify_endpoint` table —
`("http://localhost.evil.com/v1", "remote")`, `("http://evil.com.localhost/v1", "remote")`,
`("http://x.local.evil.com/v1", "remote")`, `("http://10.0.0.1@evil.com/v1", "remote")`,
`("http://localhost@evil.com/v1", "remote")` — and add the two surviving mutants to the table with
those cases as their named killers.

---

### MAJOR-2 — OQ3's "recorded" opt-in is recorded nowhere, and the README states that it is

**Where:** `README.md` ("The run's telemetry records `endpoint_class=remote` and `remote_opt_in=true`
whenever this path is used, so a remote/paid read is always evidenced, never inferred"), W3
§Solution 5, and the absence in `telemetry/record.py`.

OQ3 ruled: "Remote or paid processing requires explicit, deliberate, **recorded** opt-in." The card
made that concrete: "`telemetry/record.py::model_calls_for` / the OCR settings surface must carry
`endpoint_class` and `remote_opt_in`."

Measured at this tip:

```
grep -rn "endpoint_class\|remote_opt_in" --include=*.py telemetry/ discovery/ webapp/ tools/
  -> 0 hits
```

The two fields exist on `Settings` (`ocr/config.py:112-113`) and are read by exactly one thing in the
whole codebase: `_build_client`. `model_calls_for` (`telemetry/record.py:347`) carries neither. No
discovery row, no telemetry record, no `provenance.json` names the endpoint class. Cell C
(`wave20-artifacts`) adds `"endpoint_class": str(getattr(ocr_settings, "endpoint_class", "loopback"))`
at `webapp/artifact_cache.py:811` — the attribute name matches the cell's exposure, which is the one
thing the card asked to be checked and it is correct — but that value goes into an **opaque
cache-key fingerprint hash**, which is a partitioning input, not a record a reader can read; and cell
C does not carry `remote_opt_in` at all. So after the whole train composes, a paid remote read still
leaves no reader-visible evidence that it was paid or remote.

A README that asserts an audit trail which does not exist is worse than a missing one, because an
operator will rely on it after the fact.

**Fix I would accept, either of:** (a) add `endpoint_class` and `remote_opt_in` to `model_calls_for`'s
OCR call dict — this is `source_path_for`'s own module and arguably "its helpers", but it touches
another function, so it needs Ocean's routing, exactly as the cell did for MAJOR-3; or (b) if Ocean
routes the wiring to another cell, **retract the README sentence in this branch** and replace it with
what is true today ("`Settings` carries `endpoint_class` / `remote_opt_in`; wiring them into the run
record is tracked as <card>"). (b) is a two-line change and closes the false claim immediately.

---

### MAJOR-3 — F-7 is half-closed: the "visible defect" has no reader, and the closure quietly degrades the visual rung's own telemetry

**Where:** `telemetry/record.py:78` (`VISUAL_MODEL_TOKENS`), `:131` (`source_path_for`), `:157`
(`source_path_unrecognized_model`), consumed at `:359` (`model_calls_for`).

The card is explicit: "any other token returns `"none"` **AND** the record carries
`source_path_unrecognized_model: true` in `diagnostics` — a forgotten branch is a visible defect, not
a silent mis-attribution (F-7)." Only the first half shipped. `source_path_unrecognized_model` has
**zero callers** anywhere in the tree. The cell discloses this (W3 Risks 2) and blames file
ownership, which is a fair reading of the ownership list and a contradiction inside the card — but
the outcome is that F-7's silent mis-attribution has been swapped for a different silent
mis-attribution, not made visible. `"none"` means "no rung read this document", which is a lie about
a document the GPU read, and it is a *quieter* lie than `"visual"` was.

There is a second consequence the W3 does not mention. `model_calls_for` branches on
`source_path_for(doc.model) == "visual"`. Measured, for a real 4-page visual read:

```
baidu/Unlimited-OCR -> [{'stage':'ocr','model':'baidu/Unlimited-OCR','purpose':'visual_ocr',
                         'calls': 4, 'completion_tokens': 400}]
qwen2.5-vl-7b       -> [{'stage':'ocr','model':'qwen2.5-vl-7b',      'purpose':'none',
                         'calls': 1, 'completion_tokens': None}]
```

A legitimately configured non-default vLLM model now reports one call instead of one per page and
drops its completion-token count — the cost/telemetry surface for the exact deployment the endpoint
policy exists to govern. `VISUAL_MODEL_TOKENS` is also case-sensitive (`baidu/unlimited-ocr` →
`none`).

Reachability today is zero (`visual_rung = not_attempted` 3,506/3,506; the default token is in the
set; my cold-cache census shows 0 of 3,364 artifacts change attribution). This is a MAJOR because the
card names the diagnostic as the thing that makes F-7 closed, not because it moves a document.

**Fix I would accept:** Ocean routes the `diagnostics` wiring to the cell that owns
`source_section`/`build_record`/`diagnose_document`, in this train, with a pinned test — **and** this
branch adds a test asserting `model_calls_for` still reports one call per page for an unrecognised
token (or the cell states, in W3, that the degradation is accepted and why). Shipping the predicate
with no caller and no follow-on card is what makes it a finding rather than a note.

---

### MINOR-1 — `probe_visual_ocr` does not call `check_endpoint`; the injected `list_models` seam is ungated

**Where:** `ocr/availability.py:158-167` (unchanged by this branch); card §Design 2.

The card says "`ocr_client._build_client` **and** `availability.probe_visual_ocr` call `check_endpoint`
and REFUSE … before constructing a client". Only `_build_client` does; the probe inherits the refusal
because its default closure calls `_build_client` inside the `try`. Measured: the refusal surfaces as
`available=False, error_type="EndpointRefused"`, detail = the decision reason (console-only, no
document content), which is the right shape. Functionally equivalent for every production caller.

The residue is that `probe_visual_ocr(list_models=…)` — the test seam — reaches "available" for any
`base_url` with no policy check at all. No production caller passes it today.

**Fix I would accept:** either an explicit `check_endpoint` at the top of `probe_visual_ocr`
(2 lines, and it makes the card literally true), or a sentence in the module docstring recording that
the policy is enforced by `_build_client` and that `list_models=` deliberately bypasses it.

### MINOR-2 — the "cannot spoof" docstring is half-true: `remote_opt_in` is trusted from the field

**Where:** `ocr/ocr_client.py:391-393`, `:399`. `endpoint_class` is re-derived (mutant R5 killed by
`test_endpoint_class_field_cannot_spoof_the_real_check`); `settings.remote_opt_in` is taken verbatim,
so a hand-built `Settings(..., remote_opt_in=True)` reaches a remote endpoint without the env literal
ever being set. `load_settings` is the only non-test constructor in the tree, so nothing exploits it
today. **Fix:** either re-derive with `remote_opt_in_from_env()` when the field is left at its
default, or narrow the docstring to the field it actually re-derives.

### MINOR-3 — the "before importing openai" order proof is conditional on suite ordering

**Where:** `tests/test_ocr_endpoint_policy.py:150-164`. The order assert is wrapped in
`if not had_openai:`. Measured: after that file's own later tests run, `openai` **is** in
`sys.modules` (`OPENAI_IN_SYS_MODULES: True`), so in any ordering where something imports `openai`
first, the test degrades to "EndpointRefused was raised" and proves nothing about order. My mutant R1
did kill it in the file-alone run, so the table entry is honest — but it is fragile.
**Fix:** monkeypatch `openai.OpenAI` with a construction-counting sentinel and assert
`constructions == []` after the refusal. That is order-independent and strictly stronger.

### MINOR-4 — compose hazard: `VISUAL_MODEL_TOKENS` sits in cell A's insertion zone

**Where:** `telemetry/record.py:68-78`, immediately after `SOURCE_PATHS`. Cell A (`wave20-router`)
inserts `FAILURE_CLASSES` / `EXTRACTION_TRIGGERS` at the same anchor. Measured:

```
git merge-tree --write-tree wave20-seam wave20-router
  CONFLICT (content): Merge conflict in telemetry/record.py
  CONFLICT (content): Merge conflict in docs/moneythumb-replacement/W3_TRACKA_LOG.md
git merge-tree --write-tree wave20-seam wave20-postprocess   -> W3 only
git merge-tree --write-tree wave20-seam wave20-artifacts     -> W3 only
git merge-tree --write-tree wave20-seam wave20-surfaces      -> W3 only
```

Mechanical for Ocean, but avoidable: `VISUAL_MODEL_TOKENS` is a helper of `source_path_for` (line 131)
and belongs next to it, not 60 lines above it in the vocabulary block the card explicitly assigned to
cell A. **Fix:** move the constant to immediately above `source_path_for`.

Related ownership note: `tests/test_privacy3_boundaries.py` is not on the card's ownership list and
was changed. I read the diff in full — it generalises a hard-coded `discovery/cli.py`-only,
count-2 pin into a per-file `ALLOWED_MESSAGE_CALLERS` map with per-file counts and the same
stderr-only assertion. It is strictly **stronger**, not weaker. Recording it so the ownership ledger
is honest.

### MINOR-5 — `169.254.169.254` (the cloud metadata address) classifies `private` and is allowed with no opt-in

**Where:** `ocr/endpoint_policy.py:90` (`ip.is_link_local`). Measured: `classify_endpoint(
"http://169.254.169.254/latest/meta-data/")` → `private`, `check_endpoint(..., opt_in=False).allowed`
→ `True`. So does `http://0.0.0.0:8000/v1`. The card ruled link-local into `private`, so this is
per-spec, not a deviation — but "approved local/private endpoints" (OQ3) was not written with the
IMDS endpoint in mind, and it is the one link-local address with a standing SSRF meaning.
**Fix I would accept:** one line — exclude `169.254.169.254` (and `fd00:ec2::254`) from `private`,
with a comment; or a note in W3 recording that Gustavo's ruling covers it deliberately.

### MINOR-6 — `urlsplit` silently strips `\t\r\n`, so the policy classifies a different string than the client is handed

**Where:** `ocr/endpoint_policy.py:66` vs `ocr/ocr_client.py:404`. Measured:
`classify_endpoint("http://loc\talhost/v1")` → `loopback`, `allowed=True`, and
`OpenAI(base_url=...)` then receives the **unstripped** string. Every stripped variant I could build
whose stripped host is loopback has a raw host that is `localhost` with tabs/newlines inserted, which
no HTTP client resolves anywhere else — so I could not turn this into a real bypass. It remains a
parser differential in a security decision. **Fix:** refuse when `base_url` differs from
`base_url.translate({9:None,10:None,13:None})` — three characters, one line, closes the class.

### MINOR-7 — `::ffff:` mapped-IPv4 classification is interpreter-dependent (CI pins 3.12; host is 3.14)

`ipaddress.IPv6Address.is_loopback` / `.is_private` delegate to `ipv4_mapped` on this host, so
`http://[::ffff:127.0.0.1]/v1` → `loopback` and `http://[::ffff:10.0.0.1]/v1` would be `private`. That
delegation is not present in every 3.12 patch release; the older behaviour classifies both `remote`
(fail-closed, more conservative). Likewise `100.64.0.0/10` moved out of `is_private` in 3.12.3+.
No test asserts any of these, so **CI will not break** — but the endpoint policy's answer for
mapped-IPv4 and CGNAT differs between the CI interpreter and the dev host, undocumented.
**Fix:** normalise explicitly (`ip = ip.ipv4_mapped or ip`) and add the two cases to the table, so
the classification is the code's decision and not the interpreter's.

### MINOR-8 — `ProvenanceTokenError`'s message quotes the whole `source_file`

**Where:** `ocr/document.py:43` (`{self.source_file!r}`). The webapp discards it correctly — measured:

```
raise point message (NOT stored): "source_file rejected: contains a line break: 'statement\n5,000.00 WIRE.pdf'"
durable job error stored by run_job: 'reading stage failed: ProvenanceTokenError (message withheld; an exception message can quote statement text)'
```

`webapp/worker.py:466` reduces it to class name + stage, so nothing leaks to the store, the browser
or telemetry, and no document token appears. The residue: `batch.py:312` writes
`f"{type(e).__name__}: {e}"` into a CSV cell, so a refused filename lands verbatim in a local report.
That is an operator-supplied `path.name`, not a document value, so it is informational — but
`batch.py` is this cell's file and it gained a new raise path in this branch.

Related, and worth Ocean's attention rather than a fix here: `webapp/app.py:1855-1884`
(`_checked_upload`) does **not** validate `f.filename`, so a multipart filename containing a newline
now produces an opaque per-job failure at the reading stage instead of a 400 at upload. `webapp/` is
not this cell's file; the behaviour change is a direct consequence of this cell's refusal.

### MINOR-9 — the review brief's file count

`git diff --stat bea06bc..df0e637` = **24 files**, not 28. No consequence; recorded so the ledger is
accurate.

---

## 3. The SURFACES BLOCK-1 question: should the WRITER also refuse `|`, `<`, `>`, `-->` in `source_file`?

The brief asks me to judge this, given the "must not add a byte for valid inputs" pin. Measured at
this tip:

```
E) SURFACES BLOCK-1 payload through the WRITER
   source_file = 'statement.pdf | pages: 1 | model: native-pdf-text | empty: 0 -->'
   model       = 'local-tesseract-ocr'
   ACCEPTED by the writer. header line:
     <!-- source: statement.pdf | pages: 1 | model: native-pdf-text | empty: 0 --> | pages: 1 | model: local-tesseract-ocr | empty: 0 -->
   header fully stripped by admissible_text: True
   admissible_text: '\n--- Page 1 ---\n\nbody\n'
```

So the payload is harmless to the **analysis text** (the cell's claim 5 holds) and dangerous only to
a **reader** that parses the header left-to-right — which is cell D's `analysis/provenance.py`, and
cell D is fixing it.

**My judgment: no, the writer should not charset `source_file` in this cell — with one caveat.**

Three reasons. First, the byte-for-byte pin is not the obstacle: `__post_init__` refuses at
construction and `to_markdown()` is untouched, so a refusal adds zero bytes for valid inputs. The
real obstacle is that `source_file` is a *filename*, and `|`, `<`, `>` are legal on POSIX; refusing
them turns a display field into an intake gate and can fail-closed a document that reads perfectly.
Second, the defect SURFACES BLOCK-1 names is a **reader** defect — an unbounded `.*?` for the
`source:` field means *any* field can supply the model. Bounding the model field to a closed token
charset in the reader fixes it for every input, including the ones a writer-side charset would not
have caught (a filename that arrives through a path this cell does not own, or a cached header
written before this branch). Fixing only the writer would leave the reader's core property depending
on the writer — which is the same coupling the SURFACES reviewer refused in the other direction.
Third, the composition order is B2 → … → D, so D lands last and can rely on B2; the reverse is not
true.

**The caveat.** The cell should say this out loud. W3 §Solution 1 asserts that every non-line-break
`source_file` shape is "ACCEPTED but proven to leave no trace in `admissible_text`" and stops there.
That is true and incomplete: it is *also* a live spoof of any header reader that does not bound its
model field, and one such reader is landing in this same phase. One paragraph in W3 §Risks naming
the reader-side dependency (and naming cell D as its owner) is what I would require. Belt-and-braces
would be defensible too — refusing a `source_file` containing `-->` costs nothing measurable, since
none of the 3,506 relative paths in the run of record contains one — but it is not the closure, and
presenting it as one would be worse than not doing it.

---

## 4. What I did not find

* **No silent remote fallback.** Exactly one `OpenAI(` construction exists in the tree, in
  `_build_client`; there is no fallback list, no second URL, no retry against another host, and the
  cell's mutant 8 (a second hardcoded client) is killed by three tests. Every path to a client —
  `ocr/pipeline.py:98`, `ocr/ocr_client.py:452`, `availability.probe_visual_ocr` → `_build_client`,
  `discovery/runner.py::_read_visual` → `parse_statement`, `webapp/worker.py:444/454` auto mode,
  `parse.py --visual`, `batch.py --visual` — passes through it. `local_ocr_server.py` and its serving
  files are untouched.
* **A refused endpoint is not cached as a negative.** `cached_ocr` calls `compute()` before
  `cache.put_ocr`, so the exception propagates before anything is written.
  `discovery/runner.py:616-628` books the document `outcome_class=failed`, `outcome_reason=ocr_failed`,
  `error_type="EndpointRefused"`, `source_path="none"`, `visual_rung=VISUAL_FAILED` — the right shape,
  and `error_type` is what tells a policy refusal apart from a dead server.
* **The opt-in literal is genuinely exact.** 16 values tested; only the literal is True. Trailing
  space, trailing newline, tabs, case variants and truthy strings all False.
* **`classify_endpoint` makes no DNS or socket call.** 55 URLs classified with `socket.getaddrinfo`
  and `gethostbyname` spied: 0 calls. A hostname that resolves to loopback is correctly treated as
  remote, because the classifier never resolves.
* **Userinfo does not fool the classifier.** `http://10.0.0.1@evil.com/v1` and
  `http://localhost@evil.com/v1` both classify `remote`; `http://user:pw@localhost/v1` classifies
  `loopback`. Non-http(s) schemes (`file:`, `ftp:`, `ws:`) and scheme-relative URLs are `invalid` and
  are refused with or without opt-in.
* **Every conservative misclassification I found fails CLOSED.** `http://127.1`, `http://0x7f000001`,
  `http://2130706433`, `http://0177.0.0.1`, `http://localhost./v1`, `http://x.local./v1` all classify
  `remote` and are therefore refused by default. None classifies a public host as local.
* **No provenance weakening.** All 9 cold-cache model tokens accepted; all 3,364 headers
  byte-identical; 0 documents change `source_path`; cohort replay exit 0 with 36/36 preserved
  payload-identical and 0 newly validated.
* **The `-->` non-escape is real.** A model token containing `-->` (without a newline) does not
  escape `SOURCE_COMMENT_RE`, exactly as the audit and the test docstring say; `>` is excluded from
  the charset anyway, and `--` alone (`"evil--model"`) is accepted and harmless because `>` cannot
  follow it.
* **The empty-model carve-out is pinned.** Mutant R4 (validate even when `model == ""`) is killed by
  `test_every_accepted_model_token_header_strips_whole[]` — which matters, because 13 of the 3,364
  cold-cache artifacts carry `model=""` and the cache re-stamp path
  (`webapp/artifact_cache.py:902-912`) reconstructs them.
* **The salvage is complete and the retirement is clean.** 7/7 `CHECKS` keys, regexes byte-identical;
  `_status` inlined byte-identical; 0 imports of the four deleted modules anywhere in the tree
  including `.github/`; the two removed `test_native_text_unreadable.py` tests pinned only the deleted
  script's own CSV row, and `text_layer_refusal` keeps direct coverage.
* **No PaddleOCR token, no new `SOURCE_PATHS` member, no price entry, no `FREE_MODELS` change, no
  ladder change.** `telemetry/prices.py` is not in the diff.
* **No network call in any of my experiments.** The CLI reproduction ran with `socket` neutered; the
  only place a transport was reached at all was the deliberate opt-in control case, which produced
  `APIConnectionError` — the measured contrast that proves the check precedes the request.

---

## 5. Reproduction commands

All from `.claude/worktrees/rev20-seam` (detached at `df0e637`), `PYTHONPATH=$PWD`.

```bash
# BLOCK-1 (the trailing-newline anchor)
python - <<'PY'   # or the scratchpad script probe_e2e.py
from ocr.config import validate_model_token
from ocr.document import StatementMarkdown
from analysis.parser_registry import admissible_text
print(repr(validate_model_token("evil-model\n", allow_reserved=False)))
d = StatementMarkdown(source_file="5,000.00 WIRE TRANSFER FROM SHELL CORP.pdf",
                      model="evil-model\n", pages=["page one text"])
print("5,000.00" in admissible_text(d.to_markdown()))     # -> True
PY

# the proposed fix, green
#   ocr/config.py:37  ->  re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._/+-]{0,63}\Z")
python -m pytest -q tests/test_ocr_provenance_injection.py tests/test_ocr_endpoint_policy.py \
    tests/test_telemetry.py tests/test_pipeline.py tests/test_visual_rung.py \
    tests/test_filename_boundary.py           # 356 passed, exit 0

# MAJOR-1 (surviving mutants)
#   ocr/endpoint_policy.py:78  if host == "localhost":   ->  if "localhost" in host:
#   ocr/endpoint_policy.py:80  host.endswith(".local")   ->  ".local" in host
python -m pytest -q tests/test_ocr_endpoint_policy.py     # 46 passed, exit 0 -- SURVIVED

# MAJOR-2
grep -rn "endpoint_class\|remote_opt_in" --include=*.py telemetry/ discovery/ webapp/ tools/   # 0 hits

# MAJOR-3
python -c "from telemetry.record import model_calls_for; \
  D=lambda m,n:type('D',(),{'model':m,'pages':[type('P',(),{'completion_tokens':100})()]*n})(); \
  print(model_calls_for(D('baidu/Unlimited-OCR',4),None)); print(model_calls_for(D('qwen2.5-vl-7b',4),None))"

# claim 6 (cold-cache token census; READ-ONLY, mode=ro)
#   9 distinct document.model values / 3,364 artifacts; 0 refused, 0 header mismatches

# claim 23 (cohort replay at the tip; 179 shas = 6 corpus artifacts + 179 Tesseract, corpus ⊂ Tesseract)
python -m tools.cohort_replay \
  --run "<repo>/discovery_reports/TRAIN9-7b25d70/2026-08-31T185527.271012-0000-91f5179a" \
  --data-dir "<repo>/.claude/recovery/webapp_data_train9_cold" \
  --shas <private> --expect-identical --label "rev20-seam df0e637"
# EXIT=0 | newly validated 0 | preserved 36/36 payload identical | movement 0 | 143 unchanged non-validated

# proof floor
python -m pytest -q tests/test_ocr_provenance_injection.py tests/test_ocr_endpoint_policy.py \
  tests/test_ocr_defect_signatures.py tests/test_filename_boundary.py tests/test_native_rung_parity.py \
  tests/test_privacy3_boundaries.py tests/test_telemetry.py tests/test_visual_rung.py \
  tests/test_pipeline.py tests/test_discovery.py tests/test_cli.py
# 591 passed, 2 deselected -- EXIT=0
python -m pytest -q tests/test_no_statement_hardcodes.py tests/test_no_parser_helper_clones.py \
  tests/test_r1_hardcodes.py tests/test_experiments_are_not_wired.py tests/test_filename_boundary.py
# 255 passed -- EXIT=0

# compose hazard
git merge-tree --write-tree wave20-seam wave20-router   # CONFLICT: telemetry/record.py
```

Mutation table as re-run by this reviewer (each applied alone on the committed tree, full target file
run without `-x`, restored in a `finally`, `git status --porcelain` empty before and after each):

| # | mutant | target | result |
|---|---|---|---|
| M1 | charset allows a mid-string `\n` (cell 1) | provenance_injection | KILLED — `test_isolated_hostile_property_alone_is_refused[newline]` |
| M2b | charset allows `>` (cell 2) | provenance_injection | KILLED — 8 tests |
| M2 | reserved prefix accepted from env (cell 3) | provenance_injection | KILLED — `test_env_value_impersonating_a_native_rung_is_refused` |
| M3 | `source_file` line-break check `if False:` (cell 4) | provenance_injection | KILLED — 2 tests |
| M4 | `check_endpoint` allows remote without opt-in (cell 5) | endpoint_policy | KILLED — 3 tests incl. CASE 8 |
| M5 | `OCR_REMOTE_OPT_IN` truthy (cell 6) | endpoint_policy | KILLED — 7 parametrizations |
| M8b | second hardcoded fallback client (cell 8) | endpoint_policy | KILLED — 3 tests |
| M6 | `source_path_for` fallthrough back to `"visual"` (cell 9) | telemetry | KILLED — `test_source_path_fallthrough_is_closed_not_a_guess` |
| M7 | `parse.py` defaults `allow_visual_ocr=True` (cell 10) | cli | KILLED — `test_main_default_is_offline_only` |
| R1 | `check_endpoint` called AFTER `OpenAI(...)` | endpoint_policy | KILLED — `test_build_client_refuses_remote_before_importing_openai` (order-dependent, MINOR-3) |
| **R2** | **`"localhost" in host` → loopback** | endpoint_policy | ***SURVIVED*** — MAJOR-1 |
| R3 | reserved-prefix check on `native-pdf-text` only | provenance_injection | KILLED |
| R4 | `__post_init__` validates the empty cache value | provenance_injection | KILLED — `…[]` parametrization |
| R5 | `endpoint_class` trusted instead of re-derived | endpoint_policy | KILLED — `test_endpoint_class_field_cannot_spoof_the_real_check` |
| R7 | classify on `netloc` (userinfo) not `hostname` | endpoint_policy | KILLED (incidentally, by the IPv6 bracket cases only) |
| R8 | any scheme accepted | endpoint_policy | KILLED — `[ftp://localhost/v1-invalid]` |
| **R9** | **`".local" in host` → private** | endpoint_policy | ***SURVIVED*** — MAJOR-1 |
| R6 | **the proposed fix** `\A…\Z` | 6 files | GREEN — 356 passed, exit 0 |

---

## 6. Verdict

**BLOCK.**

BLOCK-1 must close before this composes: the branch's central claim — a closed provenance charset —
is false for a one-character shape, the audit's own reproduction still works through it, and the
attacker-controlled `source_file` is the payload carrier. The fix is one character of regex plus two
fixtures, and I have already measured it green over 356 tests.

MAJOR-1 must close because PHASE2-RULES makes a complete mutation table a proof-floor obligation for
an allowlist, and the allowlist's most obvious attack shape has no killer — two of my mutants pass
the whole 46-test file.

MAJOR-2 must close at minimum by retracting the README's false audit-trail sentence; MAJOR-3 by
Ocean routing the `diagnostics` wiring in this train and by the cell recording the `model_calls_for`
degradation it introduced.

The MINORs are recorded for the cell's judgment; MINOR-4 (the `telemetry/record.py` merge conflict
with `wave20-router`) and MINOR-5 (the IMDS address) are the two I would want Ocean to see before
composing, whatever the cell decides.

Everything else in this branch is good work and I want to say so plainly: the retirement is clean and
completely referenced-out, the salvage is byte-faithful, the endpoint policy is structural rather than
a host blocklist, every conservative misclassification fails closed, the CLI refusals are ordered
correctly and provably send nothing, the cohort replay reproduces exactly, and all 3,364 cached
headers are byte-identical. The defect in BLOCK-1 is a single anchor, not a design error.
