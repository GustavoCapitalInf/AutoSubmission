# BATCH 8 REVIEW — HYGIENE-8a (`wave8-hygiene8`, tip `af98349`, base `10cc722`)

Independent adversarial review. The reviewer did not write this code and asked
the cell nothing; every headline number below was re-measured on this host,
one process at a time, each under `( ulimit -v 8000000; timeout … )` with
`MemAvailable` read before every run (never below 26.3 GB) and peak child RSS
recorded. Read: the card `docs/agent-handoffs/HYGIENE-8.md`, the whole branch
diff, `W3_TRACKA_LOG.md` §HYGIENE8 H0–H13 (lines 43708–44480),
`BATCH8_TRANSITION.md` from "Recovery on the Linux host", and
`reviews/BATCH8_SCANHYG_REVIEW.md` for shape. Nothing else.

**No archive content appears in this file.** No document needed naming (nothing
moved); magnitudes are classes; every token quoted below is from an invented
fixture (2031 dates, out-of-range month/day shapes) or from tracked source.

**Closed file list** (`git diff --stat 10cc722..af98349`) — **18 files,
+3,658 / −192**: `analysis/chase.py`, `columbia_bank.py`, `date_tokens.py`,
`extract.py`, `scanned_small_bank.py`, `scotia.py`; `webapp/app.py`;
`tests/test_no_statement_hardcodes.py`, `test_privacy3_boundaries.py`,
`test_queue_supervisor.py`, `test_raise_privacy3.py`; `tools/hygiene8_base_tree.py`,
`hygiene8_family_replay.py`, `hygiene8_mutation_table.py`,
`hygiene8_overflow_reach.py`, `hygiene8_pinned_replay.py`,
`hygiene8_poison_sweep.py`; `docs/moneythumb-replacement/W3_TRACKA_LOG.md`.
Sixteen commits, all listed in H11.

---

## VERDICT: **APPROVE WITH FINDINGS** — 0 BLOCK, 2 MAJOR, 4 MINOR

Every headline number in §HYGIENE8 reproduces, most of them to the digit, and
the three sub-cards are non-outcome on every surface this host can measure. The
two MAJORs are both defects of the *fix*, not of the measurement: the
worker-slot release re-arms a replacement without re-claiming the slot (so one
upload during the replacement's job produces two live workers — proved, not
argued), and the branch's own proof method, applied to the branch's own four
"chain-guarded" modules, finds four more raise sites of exactly the class the
card closed as "site 6". Neither touches a published financial figure, an
outcome class or a pinned document.

| claim (record) | re-measured at `af98349` | verdict |
|---|---|---|
| branch's four test files **253 passed / 3 skipped** (H6 row 1) | `253 passed, 3 skipped, 1 warning`, exit 0, 331.7 MB | reproduces |
| canonical guard set **253** at registry 75 (H0, H6 row 2) | `253 passed`, exit 0, 93.3 MB | reproduces |
| poison census **52 cells / base 24 leaking / branch 0**, 7 sites (H4.1, H6 row 3) | `{"base_cells": 52, "base_leaking_cells": 24, "branch_cells": 52, "branch_leaking_cells": 0, "sites": 7}`, exit 0 | reproduces |
| `OverflowError` census **11 public / 11 drives / 8 escaped at base in 7 functions / 0 at branch / 10 digits** (H4.2, H6 row 4) | identical, per-entry-point table identical to H4.2's, exit 0 | reproduces |
| archive-reach scan against run A **3,380 / 3,350 / 30 / longest 54 / 2,769 at or over 2,147,481,648** (H6.1) | identical, exit 0, 73.9 MB | reproduces |
| **PINNED 109 replayed, 108 identical, 1 refused both, movement 0 of every class, 14 claimed by a touched reader** (H0, H6 row 5) | `pinned 109 · replayed 109 · identical 108 · refused_on_both 1 · moved 0 · outcome_moved 0 · publish_boundary_moved 0 · refusal_class_moved 0 · unreadable 0 · claimed_by_a_touched_reader 14 · unclaimed 1`; `by_parser` has 43 parsers summing to **108** (+1 unclaimed = 109) | reproduces; attribution non-vacuous |
| family population **618** dispatched to the **seven** derived registrations; **26** quarantined (H1, H8 item 1) | re-derived independently from run A `rows.csv` + the 208-sha file on `train8` with my own reader: 618; per-registration apex 4 / chase 505 / chase_export 4 / columbia 4 / scotiabank 84 / southside 9 / texas_first 8 (sum 618); quarantined **26**, split apex 4 / chase_export 1 / columbia 4 / southside 9 / texas_first 8 | reproduces |
| family replay against run A **618 docs / 625 replays / 609 identical / 16 raised on both / movement 0** (H6 row 7) | not re-run (500 s; no finding depends on it — see "could not verify") | quoted, not verified |
| mutation table **30 / 30 killed / 0 survived / 0 not-applied** (H7) | `killed 30, mutants 30, not_applied 0, survived 0`, baseline exit 0, tree clean after, exit 0, 148.6 s, 332.3 MB; every `landed_in` matches H7's column | reproduces |
| 12 single-killer mutants: Q5, E3, E4, E5, R5, R6, R7, R8, R10, O1, O5, O6 (H7) | the same twelve rows carry exactly one killer | reproduces |
| `analysis/` at base imports nothing from the repository outside itself; no dynamic imports (H1, `hygiene8_base_tree` docstring) | AST over all 94 files at `10cc722` and at HEAD: absolute repo imports **0**, `import_module`/`__import__` **0** | reproduces |
| population "DERIVED, not typed" (H0) | derived from a **typed** constant (`CHANGED_PARSER_MODULES`, four paths + function names); checked against the diff by hand: it is complete for this branch. No registration outside those four modules imports `_money_required`, `_money` or `_iso`; five registrations in three other modules import `parsed_datetime` and are outside the population by the declared `date_tokens` rule | reproduces, with the scope caveat stated |
| privacy of the branch's added lines: MONEY 0 · DIGITS 0 · DATES 0 · WORDS 1 (H0, H9 — previous host's shared scanner) | cannot run the shared scanner (on `main`; reads the archive). My own census below: 3,658 added lines, exact-cent amounts 2 (one textbook placeholder, twice, in the harness), 9+-digit runs 0, 64-hex 0, 8–16-hex 0, insurer token **0**, dates: session dates + invented fixture dates only | consistent; not the same instrument |
| H8 item 6 shape census "2,884 lines outside the W3 log" | 3,658 − 774 = 2,884 | reproduces |

---

## FINDINGS

### 1. MAJOR — the re-arm hands the queue a second worker: the slot is released but never re-claimed

**Where.** `webapp/app.py:99–106` (`_release_worker_slot`), against
`webapp/app.py:130–138` (`_enqueue_job`).

**What.** `_enqueue_job` claims the slot under the lock (`_job_worker_active =
True`) *before* it spawns a worker. `_release_worker_slot` sets the flag
`False` under the lock, then spawns its replacement **with the flag left
`False`**. For the whole life of the replacement thread, the module says no
worker exists. The next upload therefore starts a second worker, and two
threads drain one queue concurrently — the "single worker slot" the flag
exists to enforce (and which, on this host after the 2026-08-28 memory
incident, is what keeps two OCR jobs from running at once) is broken until
both threads happen to exit.

**Measured** (`probe2_queue.py`, invented jobs, a temp `JobStore`, no archive;
exit 0, 83 MB). A one-job queue, `_release_worker_slot(False)`, the
replacement blocked inside `run_job`, then one `_enqueue_job`:

| implementation | flag while the replacement runs `run_job` | live `_process_job_queue` threads after the upload |
|---|---|---|
| shipped `af98349` | `False` | **2** |
| the one-line closure below | `True` | 1 |

Both jobs complete once in both cases (each pop is under the lock), so this is
double-booking of the *slot*, not double-processing of a job. There is a
second, narrower window of the same defect between the lock release and
`Thread.start()` even without the flag mistake.

**Why the tests cannot see it.** `test_the_re_arm_decision_is_the_two_conditions`
calls `_join_workers()` and only *then* asserts `_job_worker_active is False`
— by which time the replacement's own `return` has already set it `False`.
The flag is never observed *during* the replacement's life, and no test
enqueues while a replacement is running. Mutants Q1–Q7 all keep this shape, so
30/30 says nothing about it. H2's sentence "the re-arm decision is asserted,
not raced" is true of the decision and false of the slot.

**Closure.** Claim the slot for the replacement in the same critical section
that decides to start it:

```python
with _job_queue_lock:
    pending = bool(_job_queue)
    rearm = pending and not shutting_down
    _job_worker_active = rearm
if rearm:
    threading.Thread(target=_process_job_queue, daemon=True).start()
    return True
return False
```

plus one test that blocks `run_job` inside the replacement, enqueues, and
asserts one live worker and `_job_worker_active is True`; and a mutant (Q8)
that drops the claim. The probe above becomes that test.

### 2. MAJOR — four unguarded `date()` sites of the "site 6" class remain in the four modules the branch declares chain-guarded

**Where** (all four escape the reader unguarded; none is inside a `try`):

| site | reached from | regex that admits the shape | what the message quotes |
|---|---|---|---|
| `analysis/chase.py:178` `date(int(raw_year), …, int(raw_day))` | `_parse_chase_business_export` (registration `chase_export`) | `row_date_re` `(\d{1,2}),?\s*(\d{4})` | printed day, month and year |
| `analysis/columbia_bank.py:449` `date(period_end.year, int(month), int(day))` | the cheque loop of `parse_columbia_bank_statement` | `_CHEQUE_ROW` `(\d{2})-(\d{2})` | printed month (and day/year for a day-range failure) |
| `analysis/scotia.py:235` `date(int(m.group(3)), int(m.group(1)), int(m.group(2)))` | the posting-table loop of `parse_scotiabank_statement` | `_DATE_RE` `(\d{2})/(\d{2})/(\d{4})` | printed month/day/year |
| `analysis/scanned_small_bank.py:82` `date(year, month, day)` in `_date_from_mdyy` | `_parse_two_column_mdyy_rows` (`:597`, called with `(\d{1,2}/\d{2})` rows at `:608`) | `\d{1,2}/\d{2}` | printed month/day |

**What.** H4.1 site 6 is the branch's own discovery: `_MONTH_RE` "proves a
token's SHAPE and nothing more", so an out-of-range month or day reaches
`date()`, whose CPython message echoes the number (on this interpreter:
`month must be in 1..12, not 13`; `day 30 must be in range 1..28 for month 2
in year 2031`; `year 0 is out of range`). The branch fixed that one function
and wrote a 15-line comment about it. The same shape stands four more times in
the same four files, twenty lines below the fix in one case, and the record's
own lesson — "there is no `raise` here to grep for" — is exactly why the
branch's proof cannot see them: `CHAIN_GUARDED` (`test_privacy3_boundaries.py:553`)
inspects `raise` statements, and `columbia_bank.py` and `scotia.py` contain
**zero** `raise` statements at HEAD, so their registration is vacuous by
construction.

**Measured** (`probe3_sites.py`; invented fixtures built from the poison
sweep's own tracked markers, with a valid 2031 period and one out-of-range row;
each site driven through the real parser on **both** trees; exit 0, 101 MB):

| drive | base `10cc722` | branch `af98349` |
|---|---|---|
| `chase._parse_chase_business_export`, a `Feb 30, 2031` row | `ValueError` escapes; day, month and year all echoed; the poison sweep's own `_leaking_surfaces` flags `str`, `repr`, `args`, `traceback` | identical |
| `scotia.parse_scotiabank_statement`, a `13/40/2031` row | `ValueError` escapes; the month echoed | identical |
| `columbia_bank.parse_columbia_bank_statement`, a cheque row `13-40` (all five required blocks non-empty, one cheque row matched) | `ValueError` escapes; the month echoed | identical |
| `scanned_small_bank._parse_two_column_mdyy_rows`, a `13/40` row | `ValueError` escapes; the month echoed | identical |

A 40-line AST census (a conversion call — `date`, `int`, `float`, `Decimal`,
`strptime`, `fromisoformat` — lexically outside any handler that catches
`ValueError`) is what found them; it costs nothing and the branch did not run
it.

**Why MAJOR and not BLOCK.** These are base-inherited, unchanged by the
branch, and in production the dispatch seam reduces a parser crash to its
class name (`analysis/parser_registry.py:854`,
`ParserFailure(…, type(exc).__name__)`) and `webapp/worker.py:96–134`
withholds messages — so no user-facing surface carries the digits today. The
surviving sinks are `batch.py:266` and `coverage_audit.py:193`
(`f"{type(e).__name__}: {e}"` into a CSV cell) and any direct caller. That is
precisely the situation the six closed sites were in, and the card closed them
anyway under the exception-boundary law; the branch's standard applied to the
branch's own files finds four more. The headline "six sites rerouted" and
"`CHAIN_GUARDED` +4" therefore overstate what the four modules now guarantee.

**Closure.** Funnel each of the four through `date_tokens.iso_or_none` (or
`iso_from_month_day_year` / a period-bounded helper) and raise `date_refusal`
outside the funnel — the shape site 6 already has; add the four to the poison
sweep as parser-driven cells (the fixtures above are the cells); and add the
implicit-conversion census as a test over `CHAIN_GUARDED`'s modules so the
next `date()` on a regex group is visible. Base-inherited, so HYGIENE-8b or the
train's closure round; not a reason to hold the three landed sub-cards.

### 3. MINOR — the shutdown premise is wrong for a worker thread, and the record repeats it

**Where.** `webapp/app.py:58–66` (`_SHUTDOWN_SIGNALS` comment), `:69–98`
(docstring), record H2 (lines 43818–43822), `test_queue_supervisor.py:19–21`.

**What.** The design says a `SystemExit` or `KeyboardInterrupt` escaping
`run_job` means "the process is going away", so nothing is re-armed. In a
non-main thread neither ends the process: `threading` delivers both to the
thread's excepthook and the interpreter continues (measured: both raised in a
daemon thread; the process survives; `probe1_static.py`). A signal can only
reach the worker thread by being raised explicitly inside it. So on that path
the process lives on, the slot is released, and every job already queued sits
at `queued` with `error=None` — P8.1's exact symptom — until the next upload
arrives and its worker drains them. Not lost, and no new OCR is started on a
process that is in fact not stopping; but the rationale in three places is
false, and the "process where no further upload ever arrives" case H2 uses to
justify the re-arm is exactly the case this branch leaves stranded.

**Closure.** Two honest sentences in the docstring and H2 (a thread-raised
signal is a dead worker, not a dying process; queued work waits for the next
upload), or drop the shutdown exemption and always re-arm — Ocean's call. No
test change is needed for the first.

### 4. MINOR — the overflow bound is a C `int`; the record and the instrument explain it as a C `long`, and the instrument's own theory predicts a different number than it measured

**Where.** Record H4.2 (lines 43990–43994: "10 digits — a 32-bit C long"),
`analysis/date_tokens.py` docstring in the diff ("past a C long"),
`tools/hygiene8_overflow_reach.py:28` and `:73–77` ("a C long is 32-bit on
Windows and 64-bit elsewhere").

**Measured.** `ctypes.sizeof(c_long) == 8`, `sizeof(c_int) == 4` on this host;
`date(2026, 1, 2**31 - 1)` raises `ValueError`, `date(2026, 1, 2**31)` raises
`OverflowError: signed integer is greater than maximum`; only past `2**63`
does CPython say "too large to convert to C long". The reachable threshold the
tool reports, 2,147,481,648, is `2**31 − 2000`. The bound is the C `int` that
`date()` parses its arguments into, on every platform; the docstring's claim
that a 64-bit-`long` platform would move it is what its own bisection refuted,
and nobody noticed the contradiction. Bisecting at runtime was still the right
call — the number is correct because it was measured, not because it was
explained.

**Closure.** One word in three places. No behaviour change.

### 5. MINOR — fixture dates off the 2031 convention, one pair disclosed and one not

**Where.** `tests/test_raise_privacy3.py:198–202` (two invented 2019 tokens,
disclosed in H8 item 5); `tests/test_raise_privacy3.py:380` and
`tools/hygiene8_overflow_reach.py:133` (an invented but *valid* full date in
2026-05, undisclosed; "February 30, 2026" at `:174` is not a date and is fine).

**Ruling** (Ocean asked): closure item, test/tool-only, move all three to 2031.
The convention exists because the shared DATES scan cannot tell an invented
2019 or 2026 date from a printed one; a valid date in a year the archive
covers is the collision class regardless of intent.

### 6. MINOR — bookkeeping, four items

* `tools/hygiene8_mutation_table.py:150–153`: mutant **E3**'s `describes` text
  says "the value row loses its `<V1>..<V3>` ordering"; the edit deletes the
  `<V4> / <V5> / <V6>` continuation. H7.1 tells the story correctly; the
  harness row does not. **E4** (`:157–162`) calls itself "MUTANT E5 FROM THE
  COMMIT" — the commit's E5 is the table's E4, and the table's E5 is
  something else. Both `landed_in` and kills are right; the labels are not.
* `analysis/chase.py:57–59` (added) and `tests/test_raise_privacy3.py:4–6`
  (added) say the refusal message "crosses `webapp/worker.py`'s boundary into
  the durable store" and "three HTTP routes". Since batch 6's §WORKER-PRIVACY,
  `webapp/worker.py:96–134` (`_stage_failure`) withholds every message from
  the store; the surviving sinks are the two CSV writers named in finding 2.
  The reroute is still right; its stated reason is stale.
* `test_a_shutdown_signal_releases_the_slot_and_starts_nothing` still asserts
  `threading.active_count() == before` — the racy shape H2 says the branch
  replaced. Harmless here (the deterministic re-arm test also kills Q6), but
  the record's "not raced" claim should not be read as covering this test.
* H1/H0 "the population is DERIVED, not typed": it is derived from the typed
  `CHANGED_PARSER_MODULES` constant, which nothing checks against
  `git diff`. Correct for this branch (verified by hand); a future branch that
  changes a fifth module would derive a population from a stale list and
  print a comfortable zero.

---

## THE THREE SUB-CARDS

**QUEUE-SUPERVISOR.** The slot does come back on every death path of
`run_job`: the handler is `BaseException`, the release is under the lock, the
re-raise is bare (`caught.value is sentinel`, `__cause__ is None` — test 2
asserts it and Q2 kills it). The two death paths *outside* `run_job` — the
lock acquisition and `popleft` under a non-empty check — cannot raise.
Starvation is impossible for a failing document (each replacement pops one job
under the lock, `run_job`'s arm marks it, five-document chain measured in the
test and in my probe); double-booking is possible and is finding 1. The
fixtures are honest: a real `JobStore` on a temp path, the real supervisor, and
only `run_job` substituted — the one thing whose behaviour is not under test.
`_join_workers` matches threads on `_target`, which CPython deletes when
`run()` returns, so a finished thread cannot match and the loop terminates.

**EXTRACT-PROMPT.** `_INSTRUCTIONS` at HEAD: 13 digit characters, all of them
the placeholder indices `<V1>`…`<V6>` and "1st"; ten quoted examples, none
with a digit; `AMOUNT_RE` hits ≥ 1.0 none; `extract.py` out of
`PATTERN_SCAN_EXEMPT` and inside `_parser_modules()`. The remaining label
names (`Previous Balance`, `Deposits/Credits`, `Checks/Debits`, `Service
Charge`, `Interest Paid`, `Ending Balance`) are generic small-bank summary
furniture present at base. The insurer token: 0 occurrences in the 3,658
added lines; 1 in the tracked tree, the inherited §PRIVACY3 ledger line, as H8
item 4 counts (Ocean's ruling relayed below). The LLM branch is unreachable
offline by two independent walls, both verified: `_INSTRUCTIONS` has exactly
one use (`extract.py:219`, inside `client.models.generate_content`), and
`pipeline.py:687–689` raises before `extract_statement` in deterministic mode
while the escalation guard at `:726` is gated on `parse_mode !=
"deterministic"`. What a hosted model does with the placeholder wording is
unmeasured, as H3 and H12 say.

**RAISE-PRIVACY-3.** The six rerouted sites are private on every surface the
poison sweep checks (52 cells, 0 leaking at branch, reproduced). Site 6 is a
genuine find. `date_refusal` and `money_refusal` build a four-value class and
never interpolate the token (read: `date_tokens.py:70–113`,
`money.py:561–623`). The reader-name rule (R11) is real and its walk covers
`tools/` and `webapp/` as well as `analysis/`. The `OverflowError` contract is
closed at all eleven entry points (reproduced) and the eight O-mutants land in
eight distinct functions. What the branch's method missed is finding 2.

**H4.3 — honest or convenient?** Honest, and incomplete. The scan asks
whether any document prints a ≥10-digit run and 2,769 do, so it bounds
nothing; the record says so plainly and puts the contract on the train's
sweep. What it could have added, and I measured: the eight widened functions
have **73 call sites in 33 modules; 39 of 75 registrations** reach one.
Crash→refusal (`iso_from_month_day`, `iso_from_month_day_year`,
`parsed_datetime`) cannot move an outcome — a `ValueError` and an
`OverflowError` are the same `parser_exception` at the seam. Crash→`None`
(`iso_or_none`, `iso_from_named_month_day`, `iso_unique_in_period`,
`year_within_period`, `iso_within_period`) *can*: a row is dropped or a reader
declines where base crashed. That direction is reachable from **16
registrations in 13 modules**, of which the family replay covers the seven
touched readers and the pinned replay covers whatever the 109 exercise. That
is the population the train's `regfp_zero_movement_sweep` must actually
contain — 16 registrations, not "all over the registry" — and the sentence
belongs in H13.

---

## THE PINNED SURFACE

`python -m tools.hygiene8_pinned_replay --base 10cc722 --scratch <private>
--corpus "<worktree>/Bank Statements" --out <private>`, in full: **109
replayed, 108 identical leaf for leaf, 1 refused on both trees by the same
class, `moved` 0, `outcome_moved` 0, `publish_boundary_moved` 0,
`refusal_class_moved` 0, `unreadable` 0**, exit 0, 104.2 s, 165.2 MB. Fourteen
are claimed by a touched reader (chase 10, chase_export 1, apex_scanned 1,
southside_scanned 1, scotiabank 1); `by_parser` names 43 parsers and sums to
108, so `fb9a3c5`'s fix of the vacuous read holds — the attribution is read at
`on_dispatch` from the production seam and reconciles to the manifest. **No
pinned leaf moves.** The instrument computes the intake once and hands the same
markdown to both stacks, so what it compares is analysis; its base stack is a
byte-for-byte copy of `10cc722`'s `analysis/` under an alias package with no
absolute or dynamic imports on either tree (measured).

---

## THE MUTATION TABLE, ADJUDICATED

`python -m tools.hygiene8_mutation_table --timeout 1800 --out <private>`:
baseline green first, **30 / 30 killed**, tree clean before and after, exit 0.
Five mutant/killer pairs were hand-checked against the edit and the named
test's assertions rather than trusted: Q1 (release deleted ↔ eight tests
assert the flag), Q5 (`pending` dropped ↔ the `[0-False-False]` row),
R4 (the `iso_or_none` funnel reverted ↔ the two out-of-range shapes), E3 (the
continuation deleted ↔ the `<V4>.*<V5>.*<V6>` line assertion — the edit does
what H7.1 says, whatever the row's label says), O2 (`iso_or_none` narrowed ↔
four tests). Each documented edit is applied at its documented occurrence and
each named killer asserts the gate the row names. The twelve single-killer
rows are a structural fact, correctly carried; the mutants that would expose
findings 1 and 2 — "drop the slot claim" and "revert one of the four
remaining `date()` sites" — are not in the table because the gates they would
test do not exist.

---

## RE-RUN TABLE

All from the branch worktree at `af98349`, sequential, one process at a time,
each in `( ulimit -v 8000000; timeout … )` through a wrapper that refuses
below 8 GB `MemAvailable` and records `ru_maxrss` of the reaped children.
`git status --short` empty before every run and after the mutation harness.

| # | proof | result | exit | wall | peak RSS |
|---|---|---|---|---|---|
| 1 | `pytest -q --no-header -p no:cacheprovider tests/test_queue_supervisor.py tests/test_raise_privacy3.py tests/test_privacy3_boundaries.py tests/test_no_statement_hardcodes.py` | `253 passed, 3 skipped, 1 warning` | **0** | 4.8 s | 331.7 MB |
| 2 | canonical guard set (5 files) | `253 passed, 1 warning` | **0** | 4.9 s | 93.3 MB |
| 3 | `tools.hygiene8_poison_sweep --base 10cc722` | 52 / 24 / 52 / 0, 7 sites; 24 base-leak rows, 0 branch | **0** | 0.8 s | 98.9 MB |
| 4 | `tools.hygiene8_overflow_reach --base 10cc722 --rows <A>/rows.csv --data-dir <cache>` | census 11 / 11 / 8 / 7 / 0, 10 digits; archive 3,380 / 3,350 / 30 / 54 / 2,769 | **0** | 2.2 s | 73.9 MB |
| 5 | `tools.hygiene8_pinned_replay --base 10cc722 --corpus "<worktree>/Bank Statements"` | 109 / 108 / 1 / movement 0 of every class / 14 touched / `by_parser` sums to 108 | **0** | 104.2 s | 165.2 MB |
| 6 | `tools.hygiene8_mutation_table --timeout 1800` | 30 / 30 / 0 / 0, baseline exit 0, tree clean after | **0** | 148.6 s | 332.3 MB |
| 7 | reviewer probe 1 (static: overflow bound, thread signals, population derivation, base-tree isolation, implicit-raise census, 618/26, diff shape census) | see findings 2, 3, 4, 5 and the tables above | **0** | 1.2 s | 45.4 MB |
| 8 | reviewer probe 2 (queue double-booking, shipped vs closure) | shipped **2** live workers, closure 1 | **0** | 1.0 s | 83.3 MB |
| 9 | reviewer probe 3 (the four `date()` sites through the real readers, both trees; widened-function caller census; prompt digits) | 4 / 4 sites reached and echoing on both trees; 73 sites / 33 modules / 39 registrations; 16 in the outcome-moving direction | **0** | 0.8 s | 101.1 MB |

`MemAvailable` never fell below 26.3 GB. Nothing was written under the
worktree; all probes live in the session scratchpad.

---

## PRIVACY RE-MEASUREMENT (this reviewer's own)

Over every added line of `git diff 10cc722..af98349` (3,658 lines; 2,884
outside the W3 log):

* **exact-cent amounts:** 4 — one textbook placeholder value twice in the
  mutation harness (invented, E1/E2's payloads), and in the record a budget
  constant and a Python version. Analysis and test files: **0**.
* **≥9-digit runs:** 0. **64-hex:** 0. **8–16-hex:** 0.
* **ISO dates:** 6 session dates (2026-08) in the record; the invented 2019 token twice
  (finding 5). **US-form dates:** the two out-of-range poison shapes quoted in
  a `scanned_small_bank.py` comment (not dates). **Long-form dates:** 12, all
  invented — seven 2031 tokens in the poison sweep (out-of-range or period
  bounds), the 2019 pair, one invalid 2026 token and one valid 2026 token
  (finding 5).
* **The purged insurer token:** 0 lines. Counted by class marker; not quoted
  here.
* **Capitalised multi-word runs** (a payee/merchant proxy): 43, every one
  prose emphasis, a harness verdict word, or a detection marker already in
  tracked source at base (the poison sweep's five Columbia labels and four
  Scotiabank labels were each grep-verified in `10cc722`'s readers).
* **This review file:** 0 archive-sourced tokens; no document is named.

---

## CLAIMS I COULD NOT VERIFY

* **The family replay's zero movement against run A** (H6 row 7: 618 / 625 /
  609 / 16 / 0). Not re-run: 500 s, and no finding here turns on it — the
  population (618) and the quarantine intersection (26) reproduce with an
  independent reader, and the pinned replay reproduces in full. Its 16
  raised-on-both documents are counted and not named (H8 item 1 says so),
  and it cannot distinguish "both trees raise `ValueError`" from "both raise
  the same `ValueError`" — which for finding 2 is the relevant question and
  the instrument's answer is by class only, correctly.
* **H9's MONEY 0 · DIGITS 0 · DATES 0 · WORDS 1.** The shared scanner is on
  `main`, not this branch, and it reads the archive; both are outside my
  mandate. The shape census above is consistent with it and is not it.
* **Part 1's run-of-record numbers** (613 + 12; 2,765 / 3,351). The run is
  gone; only the run-A restatements in H6/H6.1 are checkable, and they check.
* **The train's four proofs** (full suite, corpus gate, corpus-marked slice,
  archive-wide sweep) — H13's, not mine. On this card's own surface the pinned
  replay is a stricter question than the gate asks, so what the train owes is
  confirmation, with the 16-registration population from H4.3 above named in
  advance.

---

## THE RECORD'S OWN RISKS AND QUESTIONS, RELAYED — AND OCEAN'S RULINGS ASSESSED

1. **Shared scanner on `main`; Ocean scans at the train.** Agreed; the census
   here is the interim evidence and is consistent.
2. **The specimen in the inherited §PRIVACY3 ledger line → batch-9
   FIXTURE-PRIVACY; the commit message is immutable history.** The branch's
   own files are clean (0 in added lines, verified). Agreed on both; nothing
   for this branch to do.
3. **The 2019 fixture → closure item.** Ruled above (finding 5), with the
   undisclosed 2026 token added to the same item.
4. **26 of 618 quarantined; the quarantined-movement table is empty.**
   Reproduced independently; under Option B nothing here counts either way.
5. **Twelve single-killer mutants — risk carried.** Confirmed; correctly
   characterised. The two mutants that matter are the ones not written
   (findings 1 and 2).
6. **DETECT-BUDGET-GATE first in HYGIENE-8b; `PLANNED_REGISTRATIONS = 80` is
   below the train's 83.** Assessed for THIS branch: nothing on
   `wave8-hygiene8` depends on it. The branch adds no registration (registry
   75, verified by the guard set's 253 and the pinned replay's 43 claiming
   parsers), touches no detector, and `tests/test_parser_parity.py` is
   absent from the diff. The gate's reading at 83 is a property of the composed
   tree and belongs to the pre-run summary, as Ocean says. One interaction is
   worth a sentence there: H10 row 6 (CHASE-SAVINGS-MARKER) re-touches
   `chase.py`, and finding 2's `chase.py:178` is in the same file — HYGIENE-8b
   should take both together.

H12's eleven risks are correctly stated; items 1, 2, 4 and 8 are confirmed
here, and item 8 ("proved by 16 tests and seven mutants only") is exactly
where finding 1 lives.

---

*Reviewed by an independent Fable 5 session. Verdict tally: 0 BLOCK, 2 MAJOR,
4 MINOR — matching findings 1–6 above.*
