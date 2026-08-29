# BATCH9 · RAISE-PRIVACY-5 — independent adversarial review

Reviewer: the independent Opus cell that reviewed RAISE-PRIVACY-4 and raised the
`KeyError` finding this card closes. I did not write this code, I asked the cell
nothing, and every headline number below is my own re-measurement on this host.
Ocean composes; I never merge and never push.

| | |
|---|---|
| tree under review | `.claude/worktrees/mt9-raisepriv5`, branch `wave9-raisepriv5` |
| base | `897d69e` (`git merge-base 897d69e d5c3bd8` = `897d69e`, verified) |
| tip | `d5c3bd8` — 6 commits (`d68bd41` reader · `22f8887` censuses · `bdc5e27` mutation table · `0687511` `45f6c76` `d5c3bd8` W3) |
| host | Windows 11, Python **3.14.5**, shared with the PNC-LAYOUTS cell (`tasklist` checked before every heavy step; no two mutation harnesses ever ran together) |
| my scratch (private, uncommitted) | `%TEMP%/rp5rev/`, including a detached worktree of `897d69e` |

**Read, in order:** `docs/agent-handoffs/BATCH9-RULES.md` including its new
*"Surfaces the batch-9 reviews found unscanned"* section (commit messages;
mutation-harness restore discipline; report files);
`docs/agent-handoffs/RAISE-PRIVACY-5.md`; the whole diff `897d69e..d5c3bd8`
(six files, +1,630 / −40); W3 `§RAISEPRIV5` (384 appended lines); and, as the
thing being generalised, `tests/test_privacy3_boundaries.py` §4b/§4c and
`tests/test_raise_privacy4.py` §8.

**Instruments (absolute, passed explicitly):** run of record
`discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d`;
cold cache `.claude/recovery/webapp_data_train8_cold` (read-only). Every
both-tree comparison is between two real checkouts, not between a checkout and
a description of one.

---

## 1. Re-measurement table

| # | measurement | my result | exit | cell claimed | matched? |
|---|---|---|---:|---|---|
| 1 | full default suite at the tip | **7,385 passed**, 43 skipped, 34 deselected (224.3 s), **0 failed** | **0** | 7,385 | **yes** |
| 2 | full default suite at the base `897d69e` | **7,299 passed**, 43 skipped, 34 deselected (238.3 s), 0 failed | **0** | 7,299 | **yes** — +86, and both trees are fully green (RAISE-PRIVACY-4's two inherited failures are gone) |
| 3 | the +86, attributed | `tests/test_raise_privacy4.py` **109 → 175**, `tests/test_privacy3_boundaries.py` **143 → 163**; 252 → 338 | — | 252 → 338 | **yes**, and nothing else moved |
| 4 | canonical guards (5 files) | **255 passed** | **0** | 255 | **yes** |
| 5 | canonical conformance (7 files) | **1,270 passed**, 40 skipped | **0** | 1,270 | **yes** |
| 6 | the card's three gate files | **422 passed, 3 skipped** — the 3 skips are all the pre-existing named ones in `test_raise_privacy3.py`; both base-tree fixtures ran | **0** | — | the both-tree drives are NOT vacuous |
| 7 | `cohort_replay --parser td_canada_native --parser td_canada --group WH:td_us --expect-identical` at the **base** | 76 population · 76 replayed · newly validated 0 · preserved **73 of 73** · payload identical **73** · regressions **0** · unchanged non-validated 3 (payload changed on 0) | **0** | same | **yes** |
| 8 | the same at the **tip** | identical, field for field | **0** | same | **yes** |
| 9 | `tools/raisepriv5_mutation_table.py` (no `-x`, clean tree, host free) | **9 mutants / 9 killed / 0 survived / 0 not applied**, 262.1 s; tree proved clean before and after | **0** | 9/9, 258.0 s | **yes** |
| 10 | `tools/raisepriv4_mutation_table.py`, re-run whole at this tip | **10 / 10 killed / 0 survived / 0 not applied**, 293.4 s; tree clean | **0** | 10/10, 287.3 s | **yes** |
| 11 | `python corpus_gate.py` at the tip | **RESULT: GREEN** — 105 PASS / 3 WITHHELD / 1 REFUSED; verdicts 1 refused / 3 review / 102 validated / 3 withheld; 109 pinned PDFs (103 native + 6 committed OCR), 0 exclusions, 0 live OCR / 0 model calls; 677.7 s | **0** | GREEN, same split | **yes** |
| 12 | corpus-marked slice (`pytest -q -m corpus`) | **30 passed**, 7,432 deselected (2,190.9 s) | **0** | 30 passed | **yes** |
| 13 | branch privacy scan, `--where parser_id=td_canada,td_canada_native`, `--base 897d69e --ref d5c3bd8` | **hit_count 0**, raw_hit_count 0 (MONEY 0 · DIGITS 0 · WORDS 0 · DATES 0) over **1,630 added lines**, 73 documents, 0 with no cached text | **0** | 0 | **yes** |
| 13b | the same scan over the cell's own population — the **76 shas of the replayed cohort** (I rebuilt the sha file from my replay's per-sha table and mapped it to full 64-hex through the run's `rows.csv`) | **hit_count 0**, raw 0, 1,630 added lines, **76** documents, 0 with no cached text | **0** | 0 over 1,630 | **yes, exactly** |
| 14 | commit-message scan, `tools/huntington_msg_privacy_scan.py` over `git log 897d69e..d5c3bd8 --format=%B` | 6 commits scanned · **MONEY 0 · DIGITS 0 · DATES 0 · WORDS 0** | **0** | 0 in every class | **yes** — the reword landed |
| 15 | archive sweep — the cell's four per-chunk reports **exist and are readable**, one per chunk, each with its own `EXIT=0` | 0–845 655/655 · 845–1690 678/678 · 1690–2535 671/671 · 2535–3380 665/665 → **2,669 / 2,669 identical, 0 moved / 0 now-publishes / 0 now-raises, `findings: []` ×4**; `no_payload_raises_again` 682, `no_ocr_artifact` 29, `multi_artifact` 0 | 0 ×4 | **yes, field for field** |
| 15b | my own sweep spot check, chunk `--start 0 --end 845` at this tip | 845 documents · compared **655** · **identical 655** · moved **0** · no_payload_now_publishes **0** · payload_now_raises **0** · no_payload_raises_again 184 · no_ocr_artifact 6 · multi_artifact 0 · **findings `[]`** (1,066.3 s) | **0** | 845 / 655 / 655 / 0 / 0 / 0, findings `[]` | **yes, field for field** |
| 16 | W3 append-only | tip W3 = base W3 (**3,462,920** bytes) **byte-exact prefix** + **384** appended lines carrying **exactly one** `# §` heading (`§RAISEPRIV5`) | — | one section | **yes** |
| 17 | ownership | six files touched: `analysis/td_can.py`, `tests/test_raise_privacy4.py`, `tests/test_privacy3_boundaries.py`, `tools/raisepriv5_mutation_table.py`, W3 — **plus the one disclosed** `tools/raisepriv4_mutation_table.py`. Nothing else | — | same | **yes** |
| 18 | registry / versions | no registry file, no `*_STAGE_VERSION`, no fixture, no pinned surface in the diff | — | unchanged | **yes** |

### 1a. Measurements the cell did not make, that I added

| # | measurement | result |
|---|---|---|
| A | **Differential probe of all four lookup sites on both checkouts** — 19 month-word shapes (`JAN`/`MAR`/`DEC`; `Mar`/`mar`/`MaR`; `ZZZ`/`JUI`/`TOT`/`QQQ`; `MAR.`/`MA.`; a KELVIN-SIGN run `MAK` and `KKK`; a LONG-S run `MAſ`; `MAS`; `JA`/`JANU`/`J4N`; empty) × 6 entry points (`_parse_period` start and end, `_native_date_to_iso`, `_date_tokens`, `_native_date_token`, `_native_date_index`) plus 15 whole-period lines = **135 cases** | **0 outcome differences.** Same kind, same class, same full payload. 97 returns · 30 `KeyError` · 8 `ValueError` on **both** trees |
| B | **Base echo, measured** | **21** of those base `KeyError`s carry the printed word in `str` and as `args == ('<word>',)` — including the two non-ASCII runs, which `.upper()` does not fold and `[A-Z]{3}` under `IGNORECASE` still matches |
| C | **Tip surfaces** | **0 leaks** across `str`, `repr`, `args`, `__notes__`, `__cause__`, `__context__` **and the rendered traceback with the reader's own source lines KEPT** (stricter than the helper the cell's drives use, which strips frame source). Exactly **two** distinct tip `KeyError` messages exist, both fixed literals naming `td_can._parse_period` / `td_can._native_date_to_iso` |
| D | **The SECOND, unnamed evaluation-order change**, driven — `_native_date_to_iso`'s lookup also moved ahead of `int(m.group(2))`; 14 more cases with Arabic-Indic day digits and superscript days, readable and unreadable month words, on both trees | **0 differences** (see MINOR-2) |
| E | **Census evasion probes, static** — `.get` + a hand-written `raise KeyError(name)` / f-string / `'fixed ' + w`; a helper `lookup(T, w)`; `operator.getitem(T, w)`; `T.__getitem__(w)`; a **local alias** `t = T; t[w]`; `dict(T)[w]`; and the plain site as control | the lookup census reports **only** the control. The three hand-written re-echoes are caught instead by `_chain_offenders` (1 offender each). The other four shapes are reported by **neither** — see MINOR-1 |
| F | **Census evasion probes, dynamic, installed at the real START site and run against the whole gate set** — R1 a hand re-introduced `raise KeyError(sm)`, R2 the local-alias subscript, R3 a helper-mediated subscript | **all three killed** (exit 1; 6, 6 and 7 failures). R1 by the chain guard + the drives; R2 by the drives and the census's own non-vacuity test; R3 also by the lookup census itself — a helper that lives **inside** one of the three census modules is still reported. Tree restored clean |
| G | **Both censuses run by hand at the tip, per reader** | LOOKUP: `bmo` **0**, `farmers_merchants` **0** (4 tables resolved in each — so "they index no table" is a measurement, not an absence of vocabulary), `td_can` **1** (`_date_tokens: _MONTHS[mon]`); allowlist 1 entry, `unaccounted == []`, `stale == []`. RAW-DATE: `bmo` **1** (the ninth line), others 0; `unaccounted == []`, `stale == []`. The allowlist key format is unchanged by the new scope walker |
| H | **Was the one out-of-ownership edit forced, and does its absence fail open or closed?** I loaded the **pre-RP5** `tools/raisepriv4_mutation_table.py` from `897d69e` and counted its revert targets in the new reader | N5 **0/1**, N6 **0/1**, N8 **0/1** → the harness's `count != occurrences` branch → **NOT APPLIED**, and `main` returns **1**. **Fail-closed.** Symmetrically, the new revert text occurs 0× in the pre-RP5 source. So the edit was necessary, and omitting it would have produced a red, never a silent kill |
| I | **All 19 mutants (RP4's 10 + RP5's 9) re-derived and diffed** against the tip source | every one applies as documented (`occurrences`, `nth`), lands in the documented function (`_parse_period` ×2+M4+M5+M6, `_native_date_to_iso`, `_date_tokens`, `_statement_period` ×2, `_parse_summary` ×3, `_token_lookup_subscripts`, `_scoped_nodes`), each a single localized hunk of 2–7 lines |
| J | **Is anything a consumer of the `KeyError`'s key?** | No. `parser_registry._guarded` records `type(exc).__name__`; the three CSV sinks render `f"{type(e).__name__}: {e}"`; `webapp/worker.py` withholds the message. The tree's only `except KeyError` (`parser_registry.py:326`) is a memo-cache miss, unrelated. **No `.args[0]` consumer exists anywhere in `analysis/`, `webapp/` or the runners** |
| K | **Literal scan of the 1,246 added code lines** | 4-digit years: `2059` ×12 (the `tests/` convention FIXTURE-PRIVACY-2 established), `2000` ×9 (`td_can`'s pre-existing century pivot), `2031` ×1 (`test_raise_privacy4.py`'s own `_DEFAULT_YEAR`); one amount-shaped token `3.13`, a Python version; **no digit run ≥ 5**; no sha, no folder label |
| L | **Harness discipline against the new floor item** | `tools/raisepriv5_mutation_table.py` refuses on a dirty tree *or on a tree git will not describe* (exit 3), restores in a `finally` whose git stage cannot raise plus a byte restore from the pre-mutation text, verifies each file's bytes (exit 4) and proves `git status --porcelain` clean afterwards with retries (exit 5). This is the FIXTURE-PRIVACY-2 pattern, correctly applied |

---

## 2. Findings

### BLOCK — none.

### MAJOR — none.

I attacked the class change, the two evaluation-order changes, the census's
coverage, the allowlisted fourth subscript, the out-of-ownership edit and the
drives' honesty, and every attack failed. The two that came closest are
recorded as MINOR-1 and MINOR-2.

### MINOR-1 — the lookup census's "what it does not report" list is incomplete

`tests/test_privacy3_boundaries.py` §4c enumerates its own holes, which is the
right instinct and is exactly what my RAISE-PRIVACY-4 MINOR-5 asked for. The
enumeration is short by four measured shapes. Reported = 0 for each of:

```
t = _MONTHS            # a LOCAL alias of the table
return t[word]

operator.getitem(_MONTHS, word)
_MONTHS.__getitem__(word)
dict(_MONTHS)[word]
```

and for a helper that performs the subscript from **outside** the three census
modules. (A helper *inside* them is reported — I checked, and my R3 probe was
killed by the census itself.) The section's stated definition of "a mapping"
does exclude a local alias, so the *claim* is not wider than the *walk* — this
is a gap in the list of holes, not a false claim. Its practical bite is small
and measured: all three shapes I could install at a real site were killed by
the drives (measurement F). It matters for a **new** site nobody drives, which
is precisely the case the census exists for.

Fix: two clauses in the §4c comment and in W3 §RP5.4 — "an alias bound from
another name rather than from a dict literal; a subscript performed by a call
(`operator.getitem`, `__getitem__`, a helper outside these three modules)".

### MINOR-2 — a second evaluation-order change is unnamed and undriven

W3 §RP5.2 and the reader's own comment name **one** reordering: "the lookup is
read BEFORE `2000 + int(sy)`", and §RP5.3's Arabic-Indic drive covers
`_parse_period` (2/2 cells). But `_native_date_to_iso` moved its lookup too:

```python
# base:  iso = iso_or_none(default_year, _MONTHS[m.group(1).upper()], int(m.group(2)))
# tip:   month = _MONTHS.get(m.group(1).upper())   # ... now before int(m.group(2))
```

The justification is the same one and it holds — `(\d{1,2})` is Nd and `int()`
accepts every Nd character — but it is neither stated nor driven. I drove it:
14 cases (Arabic-Indic and superscript day glyphs × readable and unreadable
month words × `_native_date_to_iso` and `_date_tokens`), **0 differences on
both trees**. Ledger completeness, not a defect in the code.

### MINOR-3 — W3 §RP5.5 credits the harness with a host-wait it does not contain

> "the harness polled `tasklist` and did not start until the other cell's
> python had exited (101 polls, ~17 minutes)"

`grep -rln tasklist tools/` returns **nothing**: no instrument under `tools/`
polls `tasklist`. The waiting was done by the operator around the harness. The
result is fine — I confirmed the host was clear before each of my own two
harness runs — but a future cell reading this ledger would believe the
committed instrument protects it from the concurrency BATCH9-RULES now forbids,
and it does not. Either add the poll to `raisepriv5_mutation_table.main()`
(where the dirty-tree refusal already is) or reword the sentence to say who
waited.

### MINOR-4 — §RP5.9's "at `bdc5e27`" is not true of its own table

The proof-floor header pins one commit, but §RP5.7b says the sweep ran at
`0687511` and §RP5.8 says the privacy and message scans ran at the final tip —
both later than `bdc5e27`. The three later commits are docs-only, so every
number stands; I re-measured the entire floor at the true tip `d5c3bd8` and it
reproduced. This is the same class as my RAISE-PRIVACY-4 MINOR-2, which this
card adopted as a rule for the scans; the rule should extend to the header.

### MINOR-5 — the W3 section is out of order

`RP5.5` (the mutation table) stands **after** `RP5.6` and `RP5.7`, with an
`RP5.7b` wedged between them. A ledger read top to bottom should not need its
own index. Cosmetic; renumbering is an append-only-safe edit only before the
train composes.

---

## 3. The hostile questions, answered with evidence

### (1) Site by site: (a) raised `KeyError`, (b) returned None / continued, (c) succeeded

Built at the base checkout and re-run at the tip, in two processes, diffed as
JSON — **135 cases, 0 outcome differences** (measurement A).

| category | how I reached it, per site | base → tip |
|---|---|---|
| **(a) raised `KeyError`** | `_parse_period` start (`ZZZ`, `JUI`, `TOT`, `QQQ`, `MAK`, `MAſ`→`MAS`) and end (same words); `_native_date_to_iso` (`ZZZ10` …). **21 base cases carry the word as `args[0]`** | same class, same site, every time; the word is gone from every surface |
| **(b) returned `None` / continued** | `_parse_period("")`, `(None)`, a line the regex does not match, `MAR.`/`MA.` (the dot breaks `\s*(\d{1,2})`), `JA`/`JANU`/`J4N` (wrong `[A-Z]{3}` shape), superscript day glyphs (`\d` is Nd, `²³` is No → no match); `_date_tokens` returns `[]` for every non-month word — the guarded fourth subscript, **skipping and still reading its readable neighbour** | identical, all of them |
| **(c) succeeded** | `JAN`/`MAR`/`DEC`, and the case variants `Mar`/`mar`/`MaR` — `_parse_period` and `_date_tokens` `.upper()` the text and `_native_date_to_iso` `.upper()`s the token, so case never reaches the table | identical payload, leaf for leaf |

**The specific shapes you asked for.** *A month key in another case* (`Mar` vs
`MAR`): normalised before the lookup on all three paths, so it reads
identically on both trees — there is no case-sensitivity hazard left to close.
*A trailing dot* (`MAR.`, `MA.`): the regexes do not match, both trees return
`None`. *A non-ASCII uppercase run*: this one is real. `re`'s `[A-Z]` under
`IGNORECASE` matches U+212A KELVIN SIGN, and `.upper()` does not fold it, so
`MAK` reaches the table — at the base it raises `KeyError('MAK')`,
quoting a printed glyph; at the tip it takes the fixed refusal. (`MAſ` reaches
it too, via `.upper()` → `MAS`.) *Superscripts*: `\d` is category Nd and a
superscript is No, so they never reach the lookup at all; identical on both
trees.

**Only the message differs**, and I checked the whole surface: `str`, `repr`,
`args`, `__notes__`, `__cause__`, `__context__` and the rendered traceback with
the reader's own source lines kept. `__cause__`/`__context__` are `None` on
every tip refusal. Exactly two distinct tip messages exist, both fixed literals.

### (2) The evaluation-order change, attacked where it should be observable

| line | base | tip |
|---|---|---|
| `ZZZ 10/31 - QQQ 28/31` (**both** month words bad) | `KeyError('ZZZ')` — the START word, so the start is read first | `KeyError`, the fixed sentence |
| `JAN 10/31 - QQQ 28/31` (start good, end bad) | `KeyError('QQQ')` | `KeyError`, the same fixed sentence |
| `ZZZ 30/31 - MAR 28/31` (start month bad **and** start day impossible) | `KeyError` — the month before the date | `KeyError` |
| `FEB 30/31 - QQQ 28/31` (start month good, start **day** impossible, end month bad) | **`ValueError`** — `date_refusal` fires and the end month is never reached | **`ValueError`**, identical |
| the same lines with Arabic-Indic digits (`١٠/٣١`) | identical | identical |

So: which end raises first is unchanged; the class is unchanged; and no
published field differs (nothing is published — the reader crashes and
`_guarded` records the class name). **The one thing that changed is that the
two ends are now indistinguishable**, which is a *removal* of information about
the document, is deliberate, and is asserted by
`test_the_two_ends_of_the_period_still_refuse_indistinguishably`. The reorder
is unobservable for the stated reason, and I confirmed the reason rather than
accepting it: `int()` on a group `(\d{2})` cannot raise because `\d` is Nd and
`int()` accepts every Nd character — driven, not argued (measurements A, D).

### (3) The allowlisted `_date_tokens` subscript: is the allowlist keyed to the guard?

**No — and that is the honest answer, with a mitigation that holds.** The
allowlist key is `analysis/td_can.py:_date_tokens: _MONTHS[mon]`: a scope and a
subscript. Delete `if mon not in _MONTHS: continue` and the census still
matches the entry and still passes. What catches it is the **drive**, and the
cell built exactly that mutant: **M7** neuters the guard
(`if mon not in _MONTHS and False:`) and is killed by all three
parametrisations of
`test_the_guarded_row_date_lookup_skips_a_non_month_word_on_both_trees` **and
by nothing else** — which is the cleanest possible evidence that the
allowlist's reason is the thing being tested rather than a line being excused.
I re-ran the table and reproduced that row.

The residual exposure is narrow and worth Ocean knowing: if a future edit both
removes the guard *and* changes the loop so the drive's fixture stops reaching
it, nothing structural remains. A census keyed to the guard's presence (an AST
check that a `Compare(NotIn)` on the same table dominates the subscript in the
same block) would close it. Not this card's job; worth a line in the next
lookup-census card.

### (4) The RAISE-PRIVACY-4 mutation-table edit

* **Still the same mutants?** Yes. N5/N6/N8 each still revert exactly their own
  `date()` site to the raw constructor, in the same function
  (`_parse_period`, `_parse_period`, `_native_date_to_iso`), as a single hunk;
  only the six string literals moved, tracking the rename of `iso_or_none`'s
  second argument. Their `describes` prose still quotes the pre-RP5 spelling
  `date(2000 + int(sy), _MONTHS[sm], int(sd))`, which reads correctly because
  it is prefixed "§H14.3's" — it is provenance, not a claim about this tree.
  The whole table re-ran here: **10/10 killed, 0 not applied**.
* **Fail-closed or fail-open?** **Fail-closed, measured.** I loaded the
  pre-RP5 harness from `897d69e` and counted its targets in the new reader:
  N5 0/1, N6 0/1, N8 0/1. The harness's `count != mutant.occurrences` branch
  records `NOT APPLIED`, prints it, and `main` returns **1**. A stale revert
  text is a red row, never a silent `killed`. So the edit was necessary to keep
  a committed instrument honest, and its absence would have been visible.
* **Ownership:** it is the one file outside the card's list, disclosed in the
  cell's report, in the module's own docstring and in W3 §RP5.10. I agree with
  the trade: the alternative was a committed instrument with three dead rows.

### (5) Can the echo be re-introduced past the census?

**By hand in the `raise`: no.** `_chain_offenders` allows a raise only when its
callee is a declared constructor **or** every argument is a string `Constant`.
`raise KeyError(word)`, `raise KeyError(f"… {word}")` and
`raise KeyError("fixed " + word)` are each 1 offender statically, and installed
at the real site (probe R1) the gate set went red with 6 failures — the chain
guard **and** three drive parametrisations, independently. The lookup census
does not see these; `CHAIN_GUARDED` is the backstop, and it is registered for
all three readers.

**Through a helper or `operator.getitem`: yes, past the census — but not past
the drives at a live site.** Statically, `lookup(T, w)`, `operator.getitem`,
`T.__getitem__(w)`, `dict(T)[w]` and a **local alias** `t = T; t[w]` are all
reported 0 by §4c. Installed at the real `_parse_period` start site, the local
alias (R2) and the helper (R3) were both killed — R2 by the drives plus
`test_the_lookup_census_is_not_vacuous_on_the_reader_it_was_written_for`
(which pins the census's exact output on a synthetic revert), R3 by the lookup
census itself, because a helper living in one of the three census modules is
still walked. The uncovered case is therefore a *new, undriven* site using an
alias or a cross-module helper. That is MINOR-1.

### (6) Messages, W3, ownership, sweep logs

* **Commit messages:** `tools/huntington_msg_privacy_scan.py` over
  `897d69e..d5c3bd8`: 6 commits, **MONEY 0 · DIGITS 0 · DATES 0 · WORDS 0**.
  The cell disclosed that one WORDS hit fired earlier and was cleared by
  rewording an unpushed message; my scan is at the final tip and is 0 in every
  class, which is the state that matters. I did not read the intermediate hit
  file and no token appears in this review.
* **W3:** base 3,462,920 bytes; the tip file's first 3,462,920 bytes are
  **byte-identical** (`cmp -s`); 384 lines appended; exactly one `# §`
  heading. No existing section edited.
* **Ownership:** six files, five of them the card's, plus the one disclosed and
  adjudicated above. No registry, no version, no fixture, no pinned surface.
* **Sweep logs:** **all four per-chunk reports exist and are readable**, and I
  re-ran the first chunk myself at this tip and reproduced it field for field
  (845 / 655 / 655 / 0 / 0 / 0, `findings: []`), with
  their own `EXIT=0` lines and a fourth relaunched on its own after the
  background-limit kill the cell disclosed. They reconcile to
  655 + 678 + 671 + 665 = **2,669 identical of 2,669 compared**, 0 moved,
  0 `no_payload_now_publishes`, 0 `payload_now_raises`, `findings: []` in every
  chunk — and the ancillary totals (`no_payload_raises_again` 682,
  `no_ocr_artifact` 29) match RAISE-PRIVACY-4's sweep on the same archive,
  which is an independent cross-check of the settings key.

---

## 4. The explicit answers

| question | answer |
|---|---|
| newly validated = 0? | **YES** — 0 at both trees, on both registrations and the census group |
| preserved = all, with identical payloads? | **YES** — **73 of 73**, payload identical 73, at base and at tip; the 3 `WH:td_us` members unchanged with payload changed on 0 |
| regressions = 0? | **YES** — `validated regressions (BLOCKING) 0` and `other ladder regressions 0`, `--expect-identical` exit 0 at both trees; and 2,669/2,669 archive payloads identical with no finding of any class |
| refusal semantics preserved (class, control flow, published fields)? | **YES** — `KeyError` at both trees on all 30 raising cases; the first-failing end unchanged; the `date_refusal` path still pre-empts the end-month lookup; **0 differences over 149 differential cases** |
| no new refusal / no new acceptance? | **YES** — every shape that returned, still returns the same payload; every shape that raised, still raises the same class. The fourth subscript still SKIPS rather than raising, on both trees |
| the printed word absent from every refusal surface? | **YES** — `str`, `repr`, `args`, `__notes__`, `__cause__`, `__context__`, rendered traceback with reader source kept: **0 leaks**; and no decimal digit at all, since the message interpolates nothing |
| privacy of added lines = 0? | **YES** — 0 hits (raw 0) over 1,630 added lines, on both the 73-document parser population and the cell's own 76-sha cohort |
| commit messages = 0? | **YES** — 0 in every class including WORDS, at the final tip |
| ownership respected? | **YES with one disclosed breach**, and it is justified: `tools/raisepriv4_mutation_table.py` had to move or three of its ten rows would have gone `NOT APPLIED`. Measured fail-closed; edit is six literals; table re-run 10/10 |
| W3 = base + one section, byte-exact prefix? | **YES** |
| `$0`, no registry change, no version bump, no statement-specific constant? | **YES** |

---

## 5. Verdict

# APPROVE WITH FINDINGS

0 BLOCK · 0 MAJOR · 5 MINOR (MINOR-1 the census's hole-list is four shapes
short; MINOR-2 a second evaluation-order change unnamed and undriven, which I
drove; MINOR-3 the ledger credits the harness with a `tasklist` poll it does
not contain; MINOR-4 the proof-floor header pins a commit that is not true of
three of its own rows; MINOR-5 the section is out of numeric order). None of
the five touches behaviour; none needs fixing before composition. MINOR-1 and
MINOR-3 are the two worth actually doing, because both are about what the
*next* cell will believe.

This card did what my RAISE-PRIVACY-4 review asked and then did the harder
half: it closed the `KeyError` without moving the class, built the census that
would have found it, and — unusually — fixed all five of the previous review's
MINORs rather than the one that was a bug. The proofs I value most are the ones
built to be falsifiable: two different base trees loaded in one interpreter and
**asserted to be different trees**; M3, whose site no production caller can
reach and which is therefore killed only by the structural census; and M7,
killed by exactly the three drive parametrisations that carry the allowlist's
stated reason and by nothing else.

---

## 6. My opinion on each of the cell's six concerns

1. **"`KeyError` is a strange class for a refusal, and this card keeps it."**
   Right, and right to keep it. `parser_registry._guarded` publishes
   `type(exc).__name__`, so the class is exactly the thing a hygiene card may
   not move — mutant M6 proves the drives would catch a move. If the class
   should eventually change, that is a card that measures movement. **Accept.**
2. **"The CSV-sink message changes shape."** Accurate and unavoidable: the
   message *is* the leak. The cohort replay over all 76 shas and the four sweep
   chunks over all 3,380 say no document reaches any of the three sites, so no
   cell of the run of record changes. **Accept.**
3. **"The fourth subscript is still a subscript."** Correct disposition, and
   better evidenced than its RAISE-PRIVACY-4 twin because M7 drives the guard
   rather than asserting it. My one addition is §3(3): the allowlist is keyed
   to the *line*, not to the guard, so the drive is load-bearing. Worth a
   sentence in the next card. **Accept.**
4. **"The census's depth is one attribute level."** True and pinned by its own
   test. My finding is not about depth but about the *shapes* — alias, helper,
   `operator.getitem` — which the hole-list omits (MINOR-1). **Accept with
   MINOR-1.**
5. **"The census population is three readers, not the tree."** Agreed, and the
   reasoning matches §4b's. A `_MONTHS`-shaped lookup in a fourth reader is
   genuinely uncovered; that is a wider card, and Ocean should decide whether
   batch 9 wants it or whether the two censuses graduate to every
   `CHAIN_GUARDED` module at once. **Accept, and a ruling is owed.**
6. **"Two base trees are loaded in one pytest process."** The right worry, and
   it is closed the right way:
   `test_the_two_base_revisions_are_different_trees` asserts both the package
   name and the revision differ. I confirmed all 422 gate-file tests run with
   only the three pre-existing named skips, so neither vacuity check silently
   skipped. **Accept.**

---

## 7. Closure confirmation — `2f2ff51..d08876b` (5 commits, one per MINOR)

**CONFIRMED.** Bounded re-measurement at `d08876b`, on this host, with the
PNC-LAYOUTS cell's python running and no mutation harness of mine anywhere near
it. The three privacy test files: **444 passed, 3 skipped** (the same three
pre-existing named skips in `test_raise_privacy3.py`, so nothing was silently
suppressed), exit **0**. Canonical guards: **255 passed**, exit **0**.
`cohort_replay --parser td_canada_native --parser td_canada --group WH:td_us
--expect-identical` at the closure tip: population **76**, replayed **76**,
newly validated **0**, previously validated preserved **73 of 73**, payload
identical **73**, payload changed **0**, validated regressions **0**, other
ladder regressions **0**, unchanged non-validated **3 (payload changed on 0)**,
exit **0**. Branch privacy scan over the cell's own 76-sha cohort,
`--base 897d69e --ref d08876b`: **hit_count 0**, raw 0, MONEY 0 · DIGITS 0 ·
WORDS 0 · DATES 0, over **2,327 added lines**, 76 documents, 0 with no cached
text, exit **0**. Commit-message scan over the same range: **12 commits**
scanned — the six cell commits, my review commit and the five closure commits —
**0 in every class**, exit **0**. Every number matches what the closure claimed.

The two structural claims hold as stated, and one of them holds more strongly
than asked. `git diff bdc5e27..d08876b -- analysis/` is **11 added lines, 0
removed**, and **every added line is a comment**; beyond that, the non-comment
lines of `analysis/td_can.py` are identical in content and order at the two
commits and the two files' `ast.dump` are **byte-identical** — so the four
expensive rows §RP5.9 justifies at `bdc5e27` (suite, corpus gate, corpus-marked
slice, archive sweep) are measuring the same program the closure tip runs, and
the justification is sound rather than merely plausible. W3 blob to blob:
`897d69e`'s blob is **3,462,920** bytes and the first 3,462,920 bytes of
`d08876b`'s blob have the **same SHA-256** — a byte-exact prefix — followed by
**473** appended lines carrying **exactly one** top-level `# §` heading
(`§RAISEPRIV5`), whose sections now read `RP5.0 → RP5.10` in order. I confirmed
in passing that `_TOKEN_LOOKUP_UNREPORTED`'s four driven shapes are exactly the
four I measured as unreported (an alias bound from another name;
`operator.getitem`; the dunder spelling; a copy of the table), with the
cross-module-helper case named in the prose and the line-keyed allowlist
residue recorded per Ocean's ruling. Outside the bounded scope I re-ran
nothing — the full suite (claimed 7,407), conformance, the mutation tables, the
corpus gate, the corpus-marked slice and the archive sweep stand on the
closure's own measurement and on my earlier re-measurement of the same gates at
`d5c3bd8`. All five MINORs are closed; my verdict is unchanged and the branch
is, in my judgement, composable.
