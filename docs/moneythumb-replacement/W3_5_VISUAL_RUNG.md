# W3-5 — Visual-OCR rung in the discovery ladder

Agent D / SONAR. Branch `wave3-visual-ocr`. Date 2026-08-07.
Scope: composition only. No OCR code was written; the rung already existed for
the webapp path and is reached here as a library call.

---

## 1. What this is, and what it deliberately is not

Discovery's tranches 1 and 2 measured the archive through the production intake
ladder with its last rung switched off. Two findings in
`DISCOVERY_COMBINED_REPORT.md` are direct consequences:

* **13 documents** no offline rung could read at all — recorded as
  `deferred_visual_ocr`, i.e. *work we chose not to do*.
* **159 documents** (failure class 5) where local Tesseract produced text and
  no parser could claim it. The report's own diagnosis: *"Distinct mechanism
  from #1: text quality, not layout knowledge."*

W3-5 turns the rung on for exactly those two populations, behind D-3's cache,
O-3's truncation assessment and H-3's telemetry, at `$0` vendor cost (the local
Unlimited-OCR server on our own GPU).

It is **not** a new provider, a new OCR implementation, or a change to how the
webapp resolves anything. `ocr/pipeline.py` is untouched: the same
`parse_statement` call the dashboard makes is what discovery now makes, with
different capability flags.

---

## 2. CLI shape — a fourth mode, not a modifier

```
python -m discovery --scanned-visual [--no-visual-escalation]
```

**Why a mode rather than `--scanned --visual`.** Tranche 2's numbers are of
record. A modifier makes `--scanned` ambiguous — the same flag would name two
different measurements, and a run's identity would depend on reading the whole
command line. A distinct mode keeps `mode=scanned-visual` in `summary.json`, in
`report.txt` and in every operator's shell history, and it keeps the existing
mode's code path literally unchanged. It also reads correctly as *tranche 3*,
which is what it is.

`--no-visual-escalation` is a policy knob on top of the rung: recover the
documents nothing could read, but do not re-read unclaimed Tesseract output.
That is the cheap first run (13 documents rather than ~172) and the natural way
to sequence GPU time.

---

## 3. Ladder composition

Offline-first is preserved. Two — and only two — entry points to the GPU:

| Path | Trigger | Adoption rule |
|---|---|---|
| **recovery** | the offline rungs returned no document (`markdown is None`) | unconditional: there is no alternative read |
| **upgrade** | the offline read is `local_tesseract` **and** no parser claimed it | adopt only if the visual read analyses |

Both call:

```python
parse_statement(raw, source_file=…, profile=profile,
                force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True)
```

`force_ocr=True` skips straight to the visual rung — the offline rungs have
already run on this document (upgrade) or provably cannot serve it (recovery),
so re-running them would only burn time — and it is simultaneously what puts
this read in its own cache partition (§5).

**The adoption rule is one line because deterministic mode makes it one line.**
In `parse_mode="deterministic"` a payload exists *if and only if* a parser
claimed the document (no match raises, ambiguity raises). So "the visual read
produced a payload" IS "the visual read claimed", and — crucially — that test
stays correct on a D-3 analysis cache hit, where no `Dispatch` is observable at
all. Comparing dispatch outcomes would have been wrong on exactly those rows.

**Three deliberate narrowings of the upgrade trigger**, each with a cost behind
it:

1. **Tesseract-read documents only.** An unclaimed *native-text* document is
   discovery failure class 1 (a layout problem, ~660 documents). Re-reading
   perfect native text with a GPU cannot conjure a parser that does not exist;
   it would spend hours of GPU time to reproduce the same `unclaimed`.
2. **A live dispatch only.** On a D-3 analysis cache hit no dispatch exists this
   run. Treating "no dispatch" as "unclaimed" would escalate the entire archive
   to the GPU on every re-run — the same class of bug DSC-1b fixed in the
   coverage denominator.
3. **Not for parser crashes.** A document that was *claimed* and whose parser
   then threw is a parser defect (W3-1's territory), not an OCR defect.

---

## 4. Availability and failure semantics

**Before the run.** `--scanned-visual` probes `GET /v1/models`
(`ocr/availability.py`) and refuses to start (exit 2, actionable message) when
the endpoint is unreachable *or* advertises a non-empty model list that does not
contain the configured `OCR_MODEL` — every completion would 404, which is a
certain-failure configuration. An endpoint that advertises **nothing** is not
second-guessed: an empty list is an absence of evidence. The probe sends no
image, costs no GPU time, uses a 10 s timeout rather than inheriting
`OCR_TIMEOUT` (120 s), and never raises — it returns a status and lets the
caller set policy. The tesseract binary check still runs first: this mode is
`--scanned` *plus* a rung, not instead of one.

**During the run.** `ocr_page` retries and then re-raises. That exception is
caught at the discovery seam, so **that document** fails closed —
`failed` / `ocr_failed`, `error_type` = the exception **class** name (never the
message: a message can quote the document) — and the run continues. A failure is
never cached, so a transient outage cannot pin a permanent "this document is
dead".

**The deferral taxonomy does not soften.** A document the visual rung also
cannot serve is no longer `deferred`; it is terminal and explicit:

| Situation | Outcome |
|---|---|
| visual read raised | `failed` / `ocr_failed`, `error_type` set |
| visual read produced text nobody claimed | `failed` / `no_parser_matched` |
| upgrade attempted, visual did not claim | offline read stays of record; `visual_rung = no_upgrade` |

`deferred` continues to mean exactly what H3_SCHEMA says it means: work the
tranche *chose* not to do.

---

## 5. Cache-key treatment of the visual knobs — surveyed, unchanged

D-3's `ocr_settings_key` already enumerates every knob that can change the
output of an intake-ladder run:

```
force_ocr, allow_local_ocr, allow_visual_ocr,        # which rung produces text
dpi, fallback_dpi,                                    # rasterization + retry
ocr_model, ocr_base_url, ngram_size, window_size,     # the visual service
stage_version
```

So the two reads of the same bytes land in disjoint partitions **without a
single change to the cache**:

| Read | `force_ocr` | `allow_local_ocr` | `allow_visual_ocr` |
|---|---|---|---|
| offline (tranches 1–3) | `False` | mode-dependent | `False` |
| visual (tranche 3) | `True` | `False` | `True` |

Changing `OCR_MODEL` or `OCR_BASE_URL` repartitions, so a read from a different
model or endpoint can never be served as this one's. Tested per knob. The one
knob outside the key is `max_workers`, which `ocr/config.py` documents as not
affecting output.

Consequences worth stating: the recovery path and the upgrade path share one
partition (same function of the same bytes and settings), so a document that is
recovered in one run and escalated in another is read once; and a re-run of
tranche 3 touches the GPU zero times.

`row.cache_visual` and `stages.visual_ocr.cache` report the disposition from
`CacheResult.cached`, the same source H-3 uses everywhere else.

---

## 6. Truncation and telemetry — consumed, not extended

**O-3.** `ocr/pipeline.py` already calls `assess_pages` on the visual rung's
kept reads (after the mis-segmentation and TD recoveries have chosen), and D-3b
round-trips `page_integrity` through the cache. So every visual read is
assessed, on a hit as well as a miss, with no new code. Both are tested.

**H-3.** Zero telemetry changes. The record already carries everything the brief
asks for:

* `source.path = "visual"`, `source.model` = the model id — derived from
  `StatementMarkdown.model` by `source_path_for`, unchanged.
* `models.calls[]` — one `visual_ocr` entry with `calls` = pages sent and the
  model id, which is exactly the throughput denominator.
* `stages.visual_ocr` / `stages.visual_analysis` — new stage KEYS, not new
  fields: `StageTimer` is an open dict by design, and `stages.ocr` keeps
  meaning "the offline attempt".
* `outcome.fallback_reason` — an existing, previously unused record field whose
  meaning is precisely *the ladder did not stop where it normally stops*. It
  carries `visual_ocr_recovered` / `_upgraded` / `_no_upgrade` / `_failed`.

**Cost.** Per §9 of H3_SCHEMA: a model with no published price contributes
nothing to `amount`, is named in `unpriced_models`, and sets `complete = false`.
The local endpoint therefore reports **`$— (unpriced: baidu/Unlimited-OCR)`**
with the page count beside it. That is the documented convention and it is the
honest one — no vendor is billed (`$0` vendor, which is what the tranche report
states), and the *infrastructure* cost of our own GPU is not metered anywhere in
this platform, so reporting `0.00` would assert a measurement we did not make.
**Open question for Ocean** in §8.

---

## 7. Parity

No existing resolution path changed. `_read` (the offline read) is
byte-identical; `--dry-run`, `--profile-only`, `--digital` and `--scanned` reach
exactly the code they reached before, with the visual branches gated on
`self.allow_visual_ocr`, which only `--scanned-visual` sets. Proven by:

* corpus gate **GREEN, 106 PASS / 3 WITHHELD**, unchanged;
* `pytest -m corpus` — the dry-run anchor reproducing 109/109 claims, the
  `validated 100 / review 6 / withheld 3` split, and the telemetry corpus anchor;
* explicit parity tests that `--scanned` and `--digital` still defer, with the
  visual rung wired to fail the test if it is entered.

---

## 8. Open questions for Ocean

1. **Vendor-cost line.** Should the local visual endpoint join
   `telemetry/prices.py::FREE_MODELS` so a tranche-3 run reports `$0.0000`
   instead of `$unpriced`? It is defensible ("this call was free" is a fact) but
   it contradicts the ruling written into `prices.py` and the sample output in
   H3_SCHEMA §10, so SONAR did not make the call unilaterally. Zero telemetry
   files were modified.
2. **Circuit breaker.** Today a dead server produces one recorded failure per
   document for the rest of the run. The brief specifies "run continues", so no
   breaker was added — but on 3,506 documents an operator may prefer "stop after
   N consecutive visual failures". One flag, if wanted.
3. **Withheld-but-claimed Tesseract reads.** The upgrade trigger is *no claim*.
   A Tesseract read that claims but withholds on ADB (incomplete extraction) is
   arguably also a text-quality failure. Left out deliberately — it overlaps
   W3-2's withheld-diagnostics platform, which will rank those by check-class.
4. **Sequencing.** Recommend `--scanned-visual --no-visual-escalation` first
   (the 13, minutes of GPU) to validate the path end-to-end before the ~159-doc
   escalation run.
