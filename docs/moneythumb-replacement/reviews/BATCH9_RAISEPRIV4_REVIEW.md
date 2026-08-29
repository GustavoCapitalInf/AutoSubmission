# BATCH9 · RAISE-PRIVACY-4 — independent adversarial review

Reviewer: an independent Opus cell. I did not write this code, I asked the cell
nothing, and every headline number below is my own re-measurement on this host.
Ocean composes; I never merge and never push.

| | |
|---|---|
| tree under review | `.claude/worktrees/mt9-raisepriv4`, branch `wave9-raisepriv4` |
| base | `2f24b06` (`git merge-base 2f24b06 ffa26d9` = `2f24b06`, verified) |
| tip | `ffa26d9` — 4 commits (`f75d4d4` reroute · `9a4dad0` drives + census · `05b8751` mutation table · `ffa26d9` W3) |
| my scratch (private, uncommitted) | `…/scratchpad/b9/review_raisepriv4/` and `%TEMP%/rp4rev/` |
| host | Windows 11, Python **3.14.5**, shared with one other reviewer |

**Read, in order:** `docs/agent-handoffs/BATCH9-RULES.md`;
`docs/agent-handoffs/RAISE-PRIVACY-4.md`; the whole diff `2f24b06..ffa26d9`
(the review package the brief named did not exist at its path — I built commit
list, `--numstat` and full diff myself); the cell's own report
(`…/scratchpad/b9/raisepriv4_cell_report.md`); W3 `§RAISEPRIV4`
(lines 54,967–55,370 on the branch); the precedent `git show 548e518 c7a42c9
c455de7` shapes as they stand in `analysis/date_tokens.py`; and
`tests/test_raise_privacy3.py` / `tests/test_privacy3_boundaries.py` as the
census this card had to keep truthful.

**Instruments used (absolute, passed explicitly):** run of record
`discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`;
cold cache `.claude/recovery/webapp_data_train8_cold` (read-only). I also built
a detached base worktree of `2f24b06` at `%TEMP%/rp4rev/base` so that every
both-tree comparison is between two checkouts rather than between two
descriptions of one.

---

## 1. Re-measurement table

Every row is a command I ran myself, in a single process, sequentially. "matched?"
compares my number with the cell's claim.

| # | measurement | my result | exit | cell claimed | matched? |
|---|---|---|---:|---|---|
| 1 | full default suite at tip | 2 failed, **6,856 passed**, 43 skipped, 34 deselected (217 s) | **1** | same | **yes** (both failures are the two KNOWN/EXCUSED ones and nothing else) |
| 2 | full default suite at base `2f24b06` | 2 failed, **6,740 passed**, 43 skipped, 34 deselected (192 s) | **1** | same | **yes** — 6,740 + 2 = 6,742 = the pinned floor; the branch adds 116 tests, all passing |
| 3 | canonical guards (5 files) | **255 passed** | **0** | 255 | **yes** |
| 4 | canonical conformance (7 files) | **1,270 passed**, 40 skipped | **0** | 1,270 | **yes** |
| 5 | the card's three gate files | **336 passed, 3 skipped** (0 skipped inside `test_raise_privacy4.py`: 109/109 ran) | **0** | — | the both-tree drive is NOT vacuous |
| 6 | `cohort_replay` base fidelity, `--parser td_canada_native --parser bmo --parser farmers_merchants --parser td_canada --expect-identical` at `2f24b06` | population 80 · 73/73 previously validated payload identical · 7 unchanged non-validated · 0 regressions | **0** | identical | **yes** |
| 7 | the same four cohorts at the **tip** | population 80 · newly validated **0** · preserved **73 of 73** · payload identical **73** · regressions **0** · unchanged non-validated 7 (payload changed on 0) | **0** | same | **yes** |
| 8 | `--group WH:bmo --group WH:farmers_merchants --group WH:td_us` at base | 10 members, all unchanged, payload changed on 0 | **0** | — | **yes** |
| 9 | the same three groups at the tip | 10 members, newly validated 0, unchanged 10, payload changed on 0, regressions 0 | **0** | — | **yes** |
| 9b | the card's full four groups (`WH:bmo`, `WH:farmers_merchants`, `DECL:bmo_ca_business`, `WH:td_us`) at the tip | **16** members, newly validated 0, preserved 0 of 0, **unchanged non-validated 16 (payload changed on 0)**, regressions 0 | **0** | 16 / 0 / 16 | **yes** |
| 10 | `tools/raisepriv4_mutation_table.py` (no `-x`, from a clean tree) | **10 mutants / 10 killed / 0 survived / 0 not applied**, 243 s; tree restored clean | **0** | 10/10, 219.7 s | **yes** |
| 11 | privacy scan of the branch's added lines, `--where parser_id=bmo,farmers_merchants,td_canada,td_canada_native`, `--base 2f24b06 --ref ffa26d9` | **hit_count 0** (MONEY 0 · DIGITS 0 · WORDS 0 · DATES 0) over **1,603 added lines**, 80 documents, 0 with no cached text | **0** | 0 hits / 1,199 added lines | **yes on the count that matters**; see MINOR-2 on the line count |
| 12 | `python corpus_gate.py` at the tip | **RESULT: GREEN** — 105 PASS / 3 WITHHELD / 1 REFUSED; verdicts 1 refused / 3 review / 102 validated / 3 withheld; 109 pinned PDFs (103 native + 6 committed OCR), 0 exclusions, 0 live OCR / 0 model calls; 592.9 s | **0** | GREEN, same split | **yes** |
| 13 | corpus-marked slice (`pytest -q -m corpus`) | **30 passed**, 6,905 deselected (1,623.3 s) | **0** | 30 passed | **yes** |
| 14 | archive sweep, **one chunk** `--start 0 --end 850` (spot check) | 850 documents · compared payload **658** · **identical 658** · **moved 0** · **no_payload_now_publishes 0** · **payload_now_raises 0** · no_payload_raises_again 186 · no_ocr_artifact 6 · multi_artifact 0 · **findings `[]`** (884.6 s) | **0** | chunk 0–850: 658/658 identical, 0/0/0, 186, 6, findings `[]` | **yes, field for field** |

The three remaining sweep chunks (850–3380) I did **not** re-run: my brief makes
the full sweep optional when the host is loaded, and it was for most of this
review (a second reviewer's `pytest -m corpus` held one core throughout). The
850–3380 range is therefore the one headline number in the cell's ledger I take
on its word rather than on my own measurement. Chunk 0–3380's first quarter is
my spot check, and it reproduced the cell's row **field for field** — 850 / 658
/ 658 / 0 / 0 / 0 / 186 / 6, findings `[]` — which is what gives me confidence
in the instrument, the settings key and the remaining three rows.

### 1b. Measurements the cell did not make, that I added

| # | measurement | result |
|---|---|---|
| A | **Differential fuzz, both trees, 3,346 cases** over the eight sites — every `MM/DD/YY` triple `mm∈0..13 × dd∈{0,1,28,29,30,31,32,40,99} × yy∈{00,28,31,32,99}` for `farmers_merchants`, 15 month words × 9 days × 5 years for both `td_can` period ends, `_date_tokens` and `_native_date_to_iso`, 15 month names × 8 printed years for `bmo`, plus 19 odd shapes (empty, blank, tab, superscripts `²³`, Arabic-Indic `١٠`, `OCTS`, a 40-char run, 40 embedded spaces) | **0 outcome differences.** Same kind, same exception class, same full payload (`model_dump` leaf for leaf) on every one of 3,346 cases. Mix: 1,850 returns · 1,388 `ValueError` · 108 `KeyError` |
| B | **Every tip refusal against the refusal template**, over the same 3,346 cases | all **1,388** tip `ValueError`s match `^date grammar refused a printed token \((the cell is empty\|no digits in the cell\|longer than the 32-character bound\|not a date in the reader's format); reader=<module>\.<function>\)$` exactly; `__cause__`, `__context__` and `__notes__` are `None`/`None`/`[]` on **all 1,388** |
| C | **Rendered-traceback check with reader source lines KEPT** (stricter than the tool the cell's drives use, which strips every frame's source line) | **0** reader-frame tracebacks carry the token or any 2+ digit run of it |
| D | **`iso_or_none` vs raw `date()`, exhaustive** over year ∈ {−2…5, 100, 400, 1582, 1900, 2000, 2031, 2032, 9998, 9999, 10000, 10⁶, 10¹²} × month −3…15 × day −3…35 (20 × 19 × 39 = **14,820** triples) | **0** disagreements — `iso_or_none` returns `None` on exactly the triples `date()` rejects and the ISO string on exactly those it accepts. `date.fromisoformat(date(y,m,d).isoformat()) == date(y,m,d)` on **all** of them (bmo's round trip is exact) |
| E | **`calendar.monthrange` over the whole reachable domain** — year 0…9999 × month 1…12 (120,000 calls) | **0 raises.** The bmo evaluation-order change cannot turn a refusal into a different exception |
| F | **The ninth site driven** — `bmo.parse_bmo_statement` with the row token `mm/dd` for `mm ∈ {0,7,…,98} ∪ {2,12,13,99}` × `dd ∈ {0,11,…,99} ∪ {29,30,31,32}` across 5 printed periods (19 × 14 × 5 = **1,330** documents) | **0 escapes** of any exception class |
| G | **Partial-mutation state on the RAISE path** of `farmers_merchants._parse_summary` (bad start / bad end / both bad), both trees | identical `Statement` state after the exception in all three: `account_number` set, `period_start` set only on the bad-end case, `period_end` never |
| H | **My own hostile mutant N11** — `td_can._date_tokens` reverted to a raw `date()` **while keeping the reader-name prefix** in the message | **killed**, by the drives themselves and not only by the structural census: `test_the_eight_sites_refuse_without_quoting_at_the_branch[td_can.date_tokens-…]` ×2 and `test_the_refusal_carries_no_digit_at_all_on_the_message_surfaces[…]` ×3 fired independently of `test_no_raw_date_is_constructed_from_components_in_the_rerouted_readers`. The drive checks the TOKEN's absence, not the message's shape |
| I | **Each of the ten mutants re-derived and diffed** against the tip source | all ten: target text occurs exactly as documented (`occurrences`, `nth`), the patch lands in the documented function (`_statement_period` ×2, `_parse_summary` ×2 + N9, `_parse_period` ×2 + N10, `_date_tokens`, `_native_date_to_iso`), each a single localized edit of 2–7 lines. N10 correctly targets the **first** of the two identical `raise` lines |
| J | **W3 append-only** | tip W3 = base W3 (3,308,714 bytes) **byte-exact prefix** + 404 appended lines carrying **exactly one** `# §` section (`§RAISEPRIV4`). No other section touched |
| K | **Literal scan of the 1,199 added code lines** | the only 4-digit years are `2031` (×13, the fixture convention) and `2000` (×8, `td_can`'s pre-existing century pivot); the only amount-shaped literal is `3.13` (a Python version); **no digit run ≥ 5**; the 404 W3 lines add only `2031`, `2000`, `4.10/4.11/4.12` (section numbers), `3.13/3.14` (Python versions) and `7185633` (the registry fingerprint). No sha, no archive token |
| L | **The population claim re-derived** — which registrations these three modules back, and how many shas the run of record dispatched to each | `analysis/parser_registry_entries.py` backs exactly **four** with these modules: `bmo`, `farmers_merchants`, `td_canada` and `td_canada_native` (the last two both on `td_can`). `bmo_ca_business`, `bmo_us_activity` and `td_canada_french` are separate modules and are untouched. From the run's `rows.csv`: bmo **4**, farmers_merchants **3**, td_canada_native **73**, td_canada **0** — total **80**, exactly the replay population |

---

## 2. Findings

### BLOCK — none.

### MAJOR — none.

I tried hard to produce one and failed. The refutation attempts that failed are
recorded above as A–I; the two that came closest are set out under §3(1) and
§3(2).

### MINOR-1 — an incorrect count survives in tracked source, disclosed only for the commit message

`tests/test_raise_privacy4.py:236-237`:

```
#: The (site, shape) CELLS, flattened, so the parametrisation is exactly the
#: sixteen drives that exist rather than a cross-product with holes in it.
```

`len(CELLS)` is **19** (bmo 1 + farmers_merchants 3 + 3 + td_can 3 + 3 + 3 + 3),
which I confirmed by importing the module. The cell's own concern 5 and W3
§RP4.10 attribute the wrong number **only to `9a4dad0`'s commit message** and
correct it there; the same wrong number in the committed test file is not
mentioned and not corrected. Concrete case: a reader who trusts the comment
believes three drives do not exist. One-line docs fix; no behaviour.

### MINOR-2 — the cell's privacy scan did not cover its own W3 section

W3 §RP4.8 quotes `--ref wave9-raisepriv4` and **1,199 added lines**, but §RP4.9
says the whole proof floor was run at `05b8751` — i.e. before `ffa26d9`
appended the 404-line W3 section. `git diff --numstat 2f24b06 ffa26d9` is
1,603 added lines, of which exactly 404 are the W3 section the cell never
scanned. Not a defect in the result: I re-ran the scan with `--ref ffa26d9`
and got **hit_count 0** over all 1,603 lines, 80 documents, 0 with no cached
text. Recorded so the ledger's own number is understood as a measurement at
`05b8751`, not at the tip.

### MINOR-3 — "no decimal digit at all" is a property of the 19 driven cells, not of the eight sites

`tests/test_raise_privacy4.py::test_the_refusal_carries_no_digit_at_all_on_the_message_surfaces`
and W3 §RP4.3's row "any decimal digit at all on the message surfaces | 0/19"
state the assertion as if it held of the refusal. It does not:
`analysis/date_tokens.py::_refusal_class` returns
`f"longer than the {MAX_DATE_TOKEN_CHARS}-character bound"` — a string carrying
`32` — for any token longer than 32 characters, and `td_can._parse_period`
passes `m.group(0)`, whose `\s*` runs are unbounded. Concrete failing case,
measured on the tip:

```
td._parse_period("FEB" + " " * 40 + "30/31 - MAR 28/31")
  -> ValueError: date grammar refused a printed token
     (longer than the 32-character bound; reader=td_can._parse_period)
```

`str`, `repr` and `args` all carry the digits `32`. This is **not a leak** —
`MAX_DATE_TOKEN_CHARS` is a module constant of this tree, the printed token is
absent, and the length branch is §PRIVACY3's ratified refusal-class design, not
this card's. It is a MINOR because the assertion is stronger than what the code
guarantees: the test passes only because no driven cell exceeds the bound, and
the day one does the test fails on a message that is perfectly private. Either
narrow the claim (to the driven cells) or exempt the constant explicitly.

### MINOR-4 — the stated reason for leaving the `KeyError` open is not the true constraint

W3 §RP4.12 item 4 and the cell's concern 3 justify not closing
`td_can._parse_period`'s `_MONTHS[sm]` / `_MONTHS[em]` (and
`_native_date_to_iso`'s `_MONTHS[m.group(1).upper()]`) partly on the ground that
"changing the class a reader raises is a movement-bearing edit". Closing this
site does **not** require changing the class. See §3(6) for my measurement and
my recommendation.

### MINOR-5 — the new enumeration guard's coverage boundary is wider than its claim

W3 §RP4.5 says of
`tests/test_privacy3_boundaries.py::test_no_raw_date_is_constructed_from_components_in_the_rerouted_readers`
that "every bare `date(...)` / `datetime(...)` construction built from anything
but literals is reported". `_raw_date_constructions` walks only
`FunctionDef` / `AsyncFunctionDef` bodies, so it does not. I probed the
boundary with seven synthetic shapes:

| shape | reported |
|---|---:|
| inside a nested `def` | 2 (once per enclosing function — harmless) |
| inside a method | 1 |
| `date(*parts)` | 1 |
| `date(year=y, month=1, day=1)` | 1 |
| **at module scope** | **0** |
| **inside a module-scope `lambda`** | **0** |
| `date.fromisoformat(token)` | 0 (deliberate — but see below) |

Module scope itself is not a plausible tenth site (a module body runs at import,
with no document in hand), but a module-level `lambda` helper called per row is,
and it would slip past. The gap is **inherited** — `implicit_conversion_census`
in `tests/test_raise_privacy3.py` walks functions the same way — so this card
did not introduce it; the claim is what overstates. `date.fromisoformat` is
correctly out of scope for *this* guard because the funnel the card installs
uses it, and it is not a hole: `fromisoformat` **is** in the older census's
`_CONVERSION_CALLS`, so `date.fromisoformat(<a tainted name>)` is reported
there, and bmo's `date.fromisoformat(start_iso)` is not, because `start_iso` is
bound from a `_FUNNELS` call and therefore untainted. I verified both.

Fix, if Ocean wants it: one sentence in §RP4.5, or walk the module body too.

---

## 3. The hostile questions, answered with evidence

### (1) Refusal semantics site by site, and the two evaluation-order changes

I built the four categories at BASE and re-ran them at TIP in two separate
checkouts, in two processes, and diffed the JSON:

| category | how I reached it | base → tip |
|---|---|---|
| **(a) returned `None`** | `bmo._statement_period("… Statement Period: Aprilx 2031 …")` (the `calendar.month_name` index raises and is caught → `None`); `td_can._parse_period("")`, `_parse_period("@@@@@@")`, `_date_tokens("")` → `[]`; `farmers_merchants._parse_summary` on a strip its regex does not match (returns having set nothing) | identical, all of them |
| **(b) raised `ValueError`** | 1,388 cases across the fuzz — `13/40/31`, `02/30/31`, `04/31/31`, `01/00/31`, `00/10/31`, `02/29/31`, `FEB 30/31`, `APR 31/31`, `JAN 0/31`, `FEB30`, `JAN0`, `April 0000`, `April ٠٠٠٠` (Arabic-Indic `\d` that `int()` accepts) | identical class at every one; message replaced by the template |
| **(c) raised `OverflowError`** | only `td_can._date_tokens(..., default_year=10**12)` and `_native_date_to_iso(..., default_year=10**12)` | **`OverflowError` → `ValueError`, the ruled `c455de7` contract, at exactly those two sites and nowhere else** |
| **(d) succeeded** | 1,850 returns across the fuzz, including the leap-day acceptances `02/29/32` and `FEB 29/32` and the year extremes `April 0001` / `April 9999` | identical payload, leaf for leaf |

**Why the class is the thing that had to be preserved, verified at the seam.**
`analysis/parser_registry.py:851-855` records
`ParserFailure(registration.id, stage, type(exc).__name__)` — the class name is
PUBLISHED and the message is dropped. So (i) the message rewrite this card
performs is invisible to the ladder, which is why zero movement is the expected
result rather than a lucky one; and (ii) a class change *would* be
movement-bearing, which is exactly why the `OverflowError → ValueError` item
had to be proved unreachable rather than merely argued. Note `except Exception`
catches `OverflowError` too, so at base it would have been recorded as
`OverflowError`.

**The two evaluation-order changes, found and attacked.**

1. `analysis/bmo.py:86-87` — `calendar.monthrange(year, month)` is now
   evaluated **before** the refusal, where at base the first `date()` raised
   first. To move an outcome, `monthrange` would have to raise on a pair that
   reaches the line. `month` is `list(calendar.month_name).index(...)`, so it is
   1..12 (index 0 is `''`, unreachable from `([A-Za-z]+).title()`), and `year`
   is `int` of `(\d{4})`, so 0..9999 — and `(\d{4})` on a printed `20315` yields
   `2031`, not `20315` (measured), so there is no wider year. I ran
   `calendar.monthrange` over **all 120,000** pairs in that domain: **zero
   raises**. `calendar.weekday` remaps a year outside `MINYEAR..MAXYEAR` rather
   than raising, which is why. The reordering cannot alter an outcome.
2. `analysis/farmers_merchants.py:68-76` and `analysis/td_can.py:136-140` —
   I checked these are **not** order changes: at base each site was two
   sequential statements, and a start-cell failure never reached the end cell's
   `date()` or `_MONTHS[...]`. The tip preserves that exactly. I tried the
   document-shaped attack the brief asks for — a period whose START cell is
   readable and whose END cell is not, and the mirror — and compared the
   **partial `Statement` state after the exception** on both trees
   (measurement G): identical in all three cases, including the one where
   `period_start` is published and `period_end` is not. There is no input at
   which a period read that used to fail at the second date now fails at the
   first, and no published field differs.

### (2) The ninth site, `analysis/bmo.py:215`

The cell's claim survives my attack.

* It stands inside `try: … except ValueError: continue`, so no `ValueError`
  escapes. Confirmed by driving `parse_bmo_statement` over ≈1,700 documents
  whose row token spans every `mm/dd` `_ROW_RE` admits, across five printed
  periods (1,330 documents): **0 escapes** (measurement F).
* `OverflowError` is the only class the handler misses, and it needs a year
  past a C `int`. `year` is `dates.resolve_year(...)`, which returns one of
  `{period_start.year, period_end.year}` — both from `_statement_period`, whose
  year is `int` of `(\d{4})`, so ≤ 9999. Verified the regex cannot widen:
  `Statement Period: April 20315` yields group 2 = `2031`, and
  `Statement Period: April 99999` yields `9999`.
* **Superscripts cannot reach it.** `re`'s `\d` matches Unicode category **Nd**
  only, and `²³¹` are **No**, so `\d{1,2}` never matches one — I confirmed
  `Statement Period: April ²³⁴⁵` does not match at all. Arabic-Indic digits DO
  match `\d` and `int()` accepts them (`April ٠٠٠٠` → year 0), which is a real
  path to the *first* bmo site — and it refuses through `date_refusal` at the
  tip, quoting nothing.
* A leap day (`02/29` in a common year) raises `ValueError` and is caught: the
  row is skipped and the document still publishes.

So the site cannot echo and cannot overflow. Rerouting it would be a **new
refusal** (a skipped row would become a crash), which this card may not
introduce. **The reconciliation "nine candidate lines, eight echoing sites" is
correct.**

### (3) No NEW refusal and no NEW acceptance

Three independent measurements, all negative:

* the funnel itself: `iso_or_none` disagrees with raw `date()` on **zero** of
  14,820 triples, including `date(2026, 2, 29)`-style leap handling, day 0,
  month 0, month 13, negative components and 10¹² years (measurement D). It is
  literally `date()` inside one `try`; there is no separate leap rule, no
  whitespace handling, no two-digit-year rule and no zero-padding rule to
  diverge;
* bmo's added round trip `date.fromisoformat(iso)` is exact on every triple
  `date()` accepts, including `0001-01-01` and `9999-12-31`;
* end to end: **3,346 differential cases, 0 outcome differences**
  (measurement A) — every token that was accepted is accepted with the same
  payload, and every token that was refused is refused with the same class.
  Zero-padded days (`01/01/31`), unpadded days (`JAN 0`), whitespace (`   `),
  tabs, the empty string, `OCTS`/`SEPS` normalisation, `jan 10/31` in lower
  case and a 40-character run are all in that set.

### (4) The tokens in the refusal

`date_refusal(reader, token)` (`analysis/date_tokens.py:88-113`) returns —
never raises — a `ValueError` whose message interpolates only
`_refusal_class(token)` (four fixed strings, chosen by "is it empty", "does it
hold a digit", "is it over 32 characters") and the reader name. Every call site
in the three readers raises it from **outside** the handler, so nothing is
chained. Measured, not read:

* over 1,388 tip refusals from the fuzz, **every** `str` matches the template
  exactly; `__cause__` is `None`, `__context__` is `None` and `__notes__` is
  `[]` on all 1,388 (measurement B);
* the rendered traceback carries no token and no 2+ digit run of it in any
  reader frame — and I checked this **keeping** the reader's source lines,
  which the cell's own helper (`tools.hygiene8_poison_sweep._leaking_surfaces`)
  strips (measurement C);
* the reader NAME and the refusal CLASS are all that varies:
  `reader=bmo._statement_period`, `farmers_merchants._parse_summary`,
  `td_can._parse_period`, `td_can._date_tokens`, `td_can._native_date_to_iso`;
* the `CHAIN_GUARDED` rule still holds for all three modules —
  `test_every_raise_in_a_guarded_grammar_is_the_constructor_and_is_unchained`
  collects 9 module parametrisations including `analysis/bmo.py`,
  `analysis/farmers_merchants.py` and `analysis/td_can.py`, and all 9 pass at
  the tip (exit 0). Mutants N9 (naked `ValueError(cell)`) and N10
  (`… from ValueError(cell)`) are killed by exactly that guard.

The one caveat is MINOR-3: the digits `32` appear when a token exceeds the
bound. That is the module's own constant, not the document.

### (5) The ownership breach — `tests/test_raise_privacy3.py::_CARRIED_ECHOING_SITES` emptied

**It is genuinely forced.**
`test_no_unguarded_conversion_of_a_document_token_is_unaccounted_for` computes
`stale = accounted - set(census)` and asserts `stale == []` with the message
"the census no longer finds these; drop them from the list". The eight entries
name calls that no longer exist in the source, so leaving them fails the test.
There is no way to close the eight sites and keep the entries. I verified the
assertion text and the set arithmetic in the file, and mutants N1–N8 each put
their site back into the census and are each killed by that same test, which is
the other direction of the same proof.

**It is not vacuous.** The emptied dict is still one half of
`accounted = set(_CANNOT_ECHO) | set(_CARRIED_ECHOING_SITES)`, so a new
unguarded conversion still fails as "unaccounted"; it is still covered by
`test_every_entry_of_the_conversion_allowlist_carries_a_reason`, so a site
cannot be parked in it silently; and the card **adds**
`test_the_disclosure_list_this_card_emptied_is_empty`, which fails the moment
anyone parks a site there instead of carding it. On top of that the card adds a
strictly stronger enumeration guard for these three readers
(`test_no_raw_date_is_constructed_from_components_in_the_rerouted_readers`,
allowlist of exactly one entry, watched failing on five synthetic shapes). Net
guard strength went **up**, not down.

**Adjudication: acceptable.** The edit is confined to the dict, its comment and
one word above it (`git diff` shows +20/−30 in that file and nothing else).
Ocean still owns the compose question against FIXTURE-PRIVACY, which sweeps
`tests/` concurrently; the cell says Ocean has already checked that file is
untouched there.

### (6) The disclosed-but-unclosed `KeyError('<printed word>')`

**Confirmed, on both trees, identical.** Driving
`td_can._parse_period("ZZZ 10/31 - MAR 28/31")`,
`_parse_period("JAN 10/31 - ZZZ 10/31")` and `_native_date_to_iso("ZZZ10")`:

| tree | class | `str(exc)` | `args` |
|---|---|---|---|
| base `2f24b06` | `KeyError` | `'ZZZ'` | `('ZZZ',)` |
| tip `ffa26d9` | `KeyError` | `'ZZZ'` | `('ZZZ',)` |

108 of my 3,346 fuzz cases land on it. The card neither introduced it nor
changed it, and the reachability analysis in W3 §RP4.12 is correct as far as it
goes: `_native_date_to_iso`'s lookup is unreachable from the production caller
(`_native_date_index` → `_native_date_token` tests `text[:3] in _MONTHS` first,
and a token needing the `OCTS`/`SEPS` rewrite fails the raw `fullmatch` and hits
the pre-existing shape refusal instead), so the document-reachable surface is
`_parse_period` on a period-shaped line whose three-letter word is not a month.

**Is the cell's reason correct? Partly, and the load-bearing half is wrong.**
Closing it does **not** require changing the raised class. The minimal fix is
class-preserving, order-preserving and token-free:

```python
start_month = _MONTHS.get(sm)
if start_month is None:
    raise KeyError("td_can._parse_period: the period's month word is not a month")
```

— evaluated exactly where `_MONTHS[sm]` was evaluated, raised from outside any
handler (so no `__context__`), same class, no printed word on any surface. Note
`raise … from None` would **not** do: it clears `__cause__` and leaves
`__context__` holding the `KeyError('ZZZ')`.

What the cell gets right is that it is a different construction (a lookup, not
a conversion), that **no census this tree runs reports it** — I checked:
`_CONVERSION_CALLS` is `{date, datetime, int, float, Decimal, strptime,
fromisoformat}` and `Subscript` nodes are not walked at all by either census —
and that the message a CSV sink renders (`f"{type(e).__name__}: {e}"`) would
change. That last point is a real, if small, movement argument, and it is the
same argument that applies to the eight sites this card did close, where the
cohort replay over all 80 documents of the four registrations showed no
document reaches them.

**My recommendation to Ocean:** *do not* reopen this card for it — the eight
`date()` sites are what the handoff named, the fix above is a different
function's control flow, and a hygiene card that grows its own scope after its
proofs are measured is worse than a second card. But **it must become a real
card, not a W3 paragraph**: the census that would have caught it does not exist
(a lookup census over `_MONTHS`-shaped subscripts of a regex group), and W3
§H14's own lesson is that a disclosed site with no guard is a site that comes
back. Recommend `RAISE-PRIVACY-5` (or a rider on WH-ROW-CAPTURE, which touches
`td_can.py` anyway): close both lookups class-preserving, add the subscript
census, drive both trees.

### (7) The mutation table

* **Applied as documented: yes, all ten.** I re-derived each mutant from
  `tools/raisepriv4_mutation_table.MUTANTS` and diffed the mutated source
  against the tip (measurement I). Every `old` text occurs exactly the
  documented number of times (nine at 1, N10 at 2 with `nth=1`), every patch
  lands in the documented function, and every patch is a single localized edit.
* **Each reverts exactly one site: yes.** N1 reverts bmo's START and leaves the
  END funnelled; N2 the reverse; N3/N4, N5/N6 likewise. The `nth=1` on N10
  targets the first of two identical `raise` lines, which is the start refusal.
* **Result: 10 killed / 0 survived / 0 not applied**, baseline green first, tree
  clean before and after (`git status --porcelain` empty both times). My run
  took 243 s against the cell's 219.7 s — the host was shared.
* **Is the drive checking the TOKEN's absence rather than the message's shape?
  Yes.** I wrote an eleventh mutant the cell did not: revert
  `td_can._date_tokens` to a raw `__import__("datetime").date(...)` but keep the
  reader-name prefix, appending CPython's own message. It was **killed by the
  drives**, not only by the census —
  `test_the_eight_sites_refuse_without_quoting_at_the_branch[td_can.date_tokens-day-30-in-february]`,
  `[…-day-31-where-30-is-the-last]` and three parametrisations of
  `test_the_refusal_carries_no_digit_at_all_on_the_message_surfaces` all fired.
  A correct-looking refusal that leaks does not survive.
* N2 is the honest row: no drive can reach bmo's second `date()` once the start
  date is readable, and its three killers are all structural. That is the case
  the enumeration census exists for, and the card says so out loud rather than
  padding the table.

### (8) Privacy of the added lines

* `tools/privacy_scan_branch.py` at `--ref ffa26d9`: **0 hits** over **1,603**
  added lines against 80 documents (6,382 MONEY / 975 DIGITS / 3,187 WORDS /
  25 DATES printed tokens, of which 5,940 / 946 / 2,446 / 21 are distinctive),
  0 documents with no cached text, exit 0.
* Independent literal scan (measurement K): the 1,199 added **code** lines carry
  only the years `2031` (fixture convention) and `2000` (`td_can`'s pre-existing
  `2000 + int(yy)` pivot), one amount-shaped token `3.13` which is a Python
  version, and **no digit run of 5 or more**. Fixture money is rendered at
  import time from whole units (`_UNITS`, `_figure`, `_whole`), so no
  amount-shaped literal is written down at all. Account digits are `'0' * 7`
  and `'0' * 6`.
* The 404 W3 lines carry `2031`, `2000`, the section numbers `4.10/4.11/4.12`,
  the Python versions `3.13/3.14` and the registry fingerprint `7185633`. No
  content sha, no folder label, no printed value.
* **No archive token in tracked source**, and no archive content in this review
  file.

### (9) W3 append-only

`git show 2f24b06:…/W3_TRACKA_LOG.md` is **3,308,714** bytes;
`git show ffa26d9:…` is **3,331,800**. The first 3,308,714 bytes of the tip file
are **byte-identical** to the base file (`cmp -s` on a `head -c` slice: equal).
The appended 404 lines contain exactly one `# §` heading, `§RAISEPRIV4`. No
existing section is edited.

---

## 4. The explicit answers

| question | answer |
|---|---|
| newly validated = 0? | **YES** — 0 on all four registrations and on the census groups, at the tip |
| preserved = all, with identical payloads? | **YES** — 73 of 73 previously validated preserved, payload identical 73 of 73; the 7 withheld members of `bmo` (4) and `farmers_merchants` (3) and all 16 members of the four census groups unchanged with payload changed on 0 |
| regressions = 0? | **YES** — `validated regressions (BLOCKING) 0`, `other ladder regressions 0`, exit 0 on every `--expect-identical` cohort at base and at tip |
| no new refusal / no new acceptance? | **YES**, with one named and ruled exception: `OverflowError → ValueError` at `td_can._date_tokens` and `td_can._native_date_to_iso`, which is #HYGIENE8's own `c455de7` contract, is unreachable from any document (every year at these sites is `(\d{4})`, `2000 + int(\d{2})` or `int(stmt.period_end[:4])`), and is asserted structurally as well as driven on both trees. Otherwise: 0 differences over 3,346 differential cases and 0 over 14,820 helper triples |
| tokens absent from every refusal surface? | **YES** — `str`, `repr`, `args`, `__notes__`, `__cause__`, `__context__` and the rendered traceback, over 1,388 measured refusals. Caveat MINOR-3: the module constant `32` appears in the over-long refusal class; the document's token never does |
| privacy of added lines = 0? | **YES** — 0 hits over 1,603 added lines (the cell measured 1,199 at `05b8751`; I extended it to the tip) |
| ownership respected? | **YES with one disclosed and adjudicated breach** — `tests/test_raise_privacy3.py` is edited outside the card's named files. It is FORCED by the census's own staleness assertion, the edit is confined to the disclosure dict and its comment, and the guard set is strictly stronger afterwards. Ocean owns the compose check against FIXTURE-PRIVACY |
| `$0`, no registry change, no version bump, no statement-specific constant? | **YES** — the diff touches no registry file, no `*_STAGE_VERSION`, and makes no network or model call; the mutation harness shells out only to `pytest` and `git` |

---

## 5. Verdict

# APPROVE WITH FINDINGS

0 BLOCK · 0 MAJOR · 5 MINOR (MINOR-1 a wrong count in a committed comment;
MINOR-2 the cell's privacy scan predates its own W3 section, re-measured clean
at the tip; MINOR-3 a test assertion stronger than the refusal it asserts about;
MINOR-4 an inaccurate reason for leaving the `KeyError` open; MINOR-5 a ledger
claim wider than the new guard's AST coverage). None of the five touches
behaviour and none needs to be fixed before composition — MINOR-1 is a one-line
comment, MINOR-2, MINOR-3 and MINOR-5 are ledger/assertion precision, and
MINOR-4 is answered by carding the `KeyError` properly.

This is a hygiene card that did what a hygiene card is supposed to do: it moved
nothing. I re-measured every headline number the cell published except the
archive sweep's last three chunks, and every one reproduced — including the
sweep chunk I did run, field for field. The
proofs I value most are the ones the cell built to make its own claim
falsifiable — the base-tree drive that would pass vacuously if the fixtures
never reached `date()` (they reach it: 19/19 echo at base), and mutant N2, whose
site no input can reach and which is therefore killed only by the structural
census the card added.

---

## 6. My opinion on each of the cell's six concerns

1. **"The suite's exit 1 is inherited."** Confirmed by re-measurement: the same
   two tests, and only those two, fail at `2f24b06` with none of this branch's
   changes present (6,740 + 2 = 6,742 = the pinned floor); the tip adds 116
   tests and every one passes. My brief records the fix already on train9
   (`dedc1c9`). **Accept as inherited; not a cell defect.**
2. **"One file outside named ownership."** Correct, forced, and adjudicated
   above (§3(5)). **Accept.** Ocean's only action is the compose check against
   FIXTURE-PRIVACY.
3. **"A `KeyError` disclosed and not closed."** The measurement is right and the
   reachability analysis is right; the reason given is partly wrong (§3(6),
   MINOR-4) — no class change is needed to close it. **Accept the decision not
   to close it in this card, reject the reason, and require a card.**
4. **"`analysis/td_can.py` is shared with later cells."** Agreed, and worth
   Ocean writing into the WH-ROW-CAPTURE / WH-NO-PERIOD handoffs verbatim: keep
   the funnel, keep the reader-name rule, keep `date_refusal` in
   `CHAIN_GUARDED`, and keep the raw-`date()` allowlist at exactly one entry.
   The new enumeration guard will catch a violation, which is the point of it.
5. **"`9a4dad0`'s message says sixteen; it is nineteen."** Correct to record
   rather than rewrite the commit. But the same wrong number is still in
   `tests/test_raise_privacy4.py:237` and the disclosure does not say so —
   MINOR-1.
6. **"The scratch report could not be written."** Immaterial: W3 §RAISEPRIV4
   carries the detail and every number in it reproduced for me from committed
   evidence.
