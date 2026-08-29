# L-1 independent-account architecture — DESIGN (batch 9, cell `L1-ARCH-DESIGN`)

DESIGN ONLY. No production file changed, nothing registered, no test wired. Ocean reviews and
composes; implementation cells follow this document, one slice at a time.

Every number here is produced by a committed instrument and reproduces from the run of record
`discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d` and its cold cache
`.claude/recovery/webapp_data_train8_cold`, both read-only. The instruments are
`tools/l1_census.py`, `tools/l1_structure_census.py`, `tools/l1_split_prototype.py` (the L1INV
cell's, re-run at THIS base — §10.1 is the reproduction ledger) and this cell's own
`tools/l1_design_payload_probe.py`, `tools/l1_design_surface_census.py`,
`tools/l1_design_reader_probe.py`. No printed value, name, account number, amount or date
appears anywhere in this document or in the instruments: the tables count shapes, gates,
sections, closures, registrations and content sha16s.

**Read §9 before §7 if you are deciding what to build.** Four defects this design found in
production code decide the delivery order, and one of them says the platform is already doing
something the checkpoint ruling forbids.

---

## 0. What binds this design

Gustavo's checkpoint ruling of 2026-08-29 (`BATCH9-RULES.md`, "Checkpoint rulings"; the record
is `BATCH9_TRANSITION.md` §8). Six conditions, and every section below cites the one it serves:

| | condition, as ruled |
|---|---|
| **R-a** | an idle sibling is admitted ONLY when explicit statement structure establishes the sibling AND its empty / silent state — absence of parsed activity alone is insufficient |
| **R-b** | each account reconstructs and validates independently by the UNCHANGED validator |
| **R-c** | NO document-level combined ADB — the ADB is per account; the roll-up / cross-account total are consistency ORACLES only |
| **R-d** | inter-account transfers remain in each account's ledger and are identified as INTERNAL for package-level analytics so nothing is double-counted |
| **R-e** | no arbitrary or memorised account selection |
| **R-f** | explicit currency evidence outranks defaults; one denomination per account; a document printing two currencies publishes two accounts or refuses — never aggregates |

And the standing law they sit inside: the ADB doctrine (one calendar-day ADB over the printed
period, withheld when daily evidence does not cover it), `CURRENCY_DOCTRINE.md`, the repair
doctrine (a parser never writes an amount or a date the paper did not print), R-1 (no
statement-specific constant), and batch 9's non-regression rule — every one of the 2,596
validated documents is protected, and a gain never cancels a regression.

**What this design is not.** It is not a claim that the independent-account model is worth a
large coverage number. The measured population that closes today is **2 documents**, and **8**
under one ruling. §7 states that in the same table as the work, because the ruling that
matters — is this correctness work worth doing at this price — is Gustavo's, and it cannot be
made from an adjective.

---

## 1. Data model

### 1.1 Three objects, and one of them is unchanged

```
Statement              — analysis/schema.py:121-221.  UNCHANGED.  One account.
Report                 — analysis/pipeline.py:153-163. UNCHANGED.  One account's analysis.
DocumentReport         — NEW.  N accounts plus the document's own printed facts.
```

`Statement` is **not renamed** to `AccountStatement`. A rename would touch all 83
registrations, every test and every fixture, move no evidence, and force the byte-identity
proof of §1.2 to be re-argued for a cosmetic reason. What changes is its docstring, which will
say what it has always meant: *one account*. The word "statement" keeps meaning "one account's
statement", and the new word for "one PDF" is **document**.

```python
# analysis/pipeline.py — new, additive
@dataclass
class SiblingOmission:
    label: str | None          # the section's own printed identity token
    reason: str                # a CLOSED vocabulary — §4, L1-C17
    posting_count: int         # dated rows the omitted section printed

@dataclass
class RollupOracle:
    caption_class: str                    # one of the 9 measured classes
    column_roles_printed: bool            # condition L1-C5
    rows: int
    cross_account_total_printed: bool

@dataclass
class DocumentReport:
    accounts: list[Report]                # printed order, NEVER sorted
    document_period: tuple[str, str] | None
    rollup: RollupOracle | None           # evidence, never a value
    omissions: list[SiblingOmission]
    boundary_mechanism: str | None        # one of the 4 measured mechanisms
    internal_transfers: list[InternalTransfer]   # §3
```

`SiblingOmission` is the batch-8 `SIBLING-OMISSION-SURFACE` shape (`HYGIENE-8.md`:8-14,
`unpublished_sibling_sections: list[{label, reason, posting_count}]` plus an integrity NOTE),
moved from `Statement` to `DocumentReport` — see §1.2 for the measured reason.

`RollupOracle` carries the printed enumerating table as **evidence**, never as a source of
value. No figure is taken from it unless `column_roles_printed` is true (L1-C5). It is stored
because the roll-up is the one cross-account oracle this population prints — on 103 of 214
documents — and an oracle that is not recorded cannot be audited.

### 1.2 RULE S — what a single-account document publishes

> **RULE S.** A `DocumentReport` publishes exactly today's payload, with no added key of any
> kind, when all four clauses hold: it carries exactly one account; it omitted nothing; it read
> no roll-up; and it recorded no boundary mechanism.

All four, because each is a way the document could carry a fact the single-account payload has
nowhere to put. A document meeting all four is one about which the new model learned nothing
the old payload could not say — so it says it the old way, byte for byte.

**Measured** (`tools/l1_design_payload_probe.py`, at this base, over 208 validated
documents spanning 71 distinct registrations — the first three validated documents
of every registration in the run of record; each analysed ONCE and serialised four ways from
the same in-memory `Report`, so nothing in the comparison can move except the shape under
test):

| variant | payload byte-identical | payload differs | document outcome unchanged |
|---|---:|---:|---:|
| **`wrapper_conditional`** — RULE S | **208** | **0** | 208 |
| `wrapper_unconditional` — `accounts` + `document` on every document | 0 | **208** | 208 |
| `omission_field_always` — the omission record as a plain `Statement` field | 0 | **208** | 208 |
| **`omission_field_elided`** — the same field, elided when empty | **208** | **0** | 208 |

Two of those four are the shapes a reader reaches for first, and both cost the whole archive:

* **`wrapper_unconditional`** — emitting `accounts` and `document` on every document — changes
  every payload in the archive. The changed leaf paths are every leaf of the payload, re-rooted
  under `accounts[*]`.
* **`omission_field_always`** — `SIBLING-OMISSION-SURFACE` as a plain `Statement` field, which
  is what `HYGIENE-8.md` proposed and what pydantic would dump on every document whether or not
  anything was omitted — changes every payload in the archive **while adding no leaf**.

That second one is why this design puts the omission record on `DocumentReport` and elides it
from the payload when it is empty: as a `Statement` field it would have made batch 9's cheapest
correctness card an archive-wide payload migration.

### 1.3 A blind spot in the proof instrument every coverage cell reports under

`tools/cohort_replay.py` reports `payload identical` from a LEAF projection (`flatten`,
`leaf_diff`), and **an empty list contributes no leaf**. A change that adds a key whose value
is `[]` therefore moves the payload BYTES while the projection every coverage cell reports
under sees nothing at all. Measured on the same pairs:

| variant | byte-identical | leaf-projection identical | the gap |
|---|---:|---:|---:|
| `wrapper_conditional` | 208 | 208 | 0 |
| `wrapper_unconditional` | 0 | 0 | 0 |
| **`omission_field_always`** | **0** | **208** | **208** |
| `omission_field_elided` | 208 | 208 | 0 |

The third row is the finding, and it is total: **on all 208 documents the byte comparison says
the payload changed and the leaf projection says it did not.** A cell landing
`SIBLING-OMISSION-SURFACE` as a plain `Statement` field and proving it with `cohort_replay`
alone would have reported `previously validated preserved, payload identical` for an
archive-wide payload migration.

**Consequence for the proof plan (§6).** Every stage of this design that touches the payload
shape must prove its claim by BYTE comparison, not by `cohort_replay`'s `payload identical`
line alone. The line is not wrong — it answers the question it asks — but on this class of
change it is not the question. This is carded as a finding against `cohort_replay`, not fixed
here: this cell owns no shared instrument.

### 1.4 The multi-account payload, and why it has no `statement` key

```jsonc
{
  "document": {
    "period_start": ..., "period_end": ...,
    "boundary_mechanism": "rollup-oracle",
    "account_count": 3,
    "rollup": { "caption_class": ..., "column_roles_printed": true,
                "rows": 3, "cross_account_total_printed": true },
    "omitted_sections": [ { "label": ..., "reason": ..., "posting_count": 0 } ],
    "internal_transfers": [ { "a": [0, 17], "b": [1, 4], "basis": "..." } ]
  },
  "accounts": [ { /* exactly today's payload, per account */ }, ... ]
}
```

**There is deliberately no top-level `statement`.** A consumer that reads
`payload["statement"]` on a three-account document reads ONE account and calls it the
document — which is the L-1 defect itself, moved out of the parser and into the payload. Its
absence is what makes such a consumer stop.

Except that most of them do not stop. **Measured** (`tools/l1_design_reader_probe.py`: one real
validated document, analysed once, offered to every payload reader that is a pure function of
the payload dict, in three shapes — today's, the document shape, and the Option-D shim that
promotes the first account back under `statement`):

| payload reader | `baseline` | `document` shape | Option-D `shim` |
|---|---|---|---|
| `telemetry/record.py::classify_outcome` | `validated/approved` | **`withheld/withheld_adb`** | `validated/approved` |
| *(this design)* `classify_document` | `validated/approved` | `validated/approved` | `validated/approved` |
| `analysis/revenue.py::rebuild_serialized_revenue_views` | rebuilt over 27 transactions | **rebuilt over 0 transactions** | rebuilt over 27 transactions |
| `webapp/app.py::_analysis_rows` (CSV / XLSX export) | 211 export rows | **0 export rows** | 211 export rows |
| `webapp/app.py::_adb_rows` (ADB export) | 0 ADB rows | 0 ADB rows | 0 ADB rows |
| `webapp/app.py::_masked` (the `/analysis` route) | 9 top-level keys | **2 top-level keys** | 9 top-level keys |

| measure | value |
|---|---:|
| payload readers probed | 6 |
| ... that REFUSE the document shape (loud, fail-closed) | **0** |
| ... that ANSWER a shape they were not taught (quiet, wrong) | **6** |
| ... that refuse the Option-D shim | **0** |

Two findings, and both are load-bearing:

1. **The untaught failure is quiet, not loud.** `telemetry/record.py::classify_outcome`
   (:349-351) reads `payload.get("metrics") or {}` and returns `("withheld", "withheld_adb")`
   for a payload that has no top-level `metrics` — so a perfectly valid three-account document
   would be filed WITHHELD with a reason that names a check nobody ran (measured above: a
   `validated/approved` document becomes `withheld/withheld_adb` under the document shape).
   `analysis/revenue.py::rebuild_serialized_revenue_views` (:55-56) does
   `analysis.setdefault("statement", {})` and rebuilds every revenue view over an empty ledger.
   Neither raises. **Therefore: no document may publish two accounts until every payload reader
   has been taught the shape.** That is the ordering constraint §7 is built around, and it is a
   correction to the delivery order the card sketched.
2. **The Option-D shim is refused on evidence.** Under the shim every untaught reader answers,
   and answers about one account of several, silently, on every surface, forever. The shim is
   exactly what makes the defect invisible.

The design therefore adds a **shape assertion** (L1-C16): a payload carrying `accounts` may
never also carry `statement`, and every reader taught the shape raises `ValueError` on a
payload carrying neither. The assertion is what converts the quiet failure above into a loud
one for every reader written after this design.

### 1.5 The document outcome

`classify_outcome` (`telemetry/record.py`:322-370) produces one `(class, reason)` per document
and is read by `discovery/runner.py`:661-665, `corpus_gate.py`:1358 and `build_record`:390-392.
`discovery/compare.py` ranks on `LADDER = ("failed", "withheld", "review", "validated")` (:37)
keyed on `content_sha256` alone (:73). One outcome per document is therefore not a convenience:
it is the ladder the whole non-regression regime is measured on, and it stays.

> **The document outcome is the WEAKEST account's outcome.**
> ```
> rank = {failed: 0, withheld: 1, review: 2, validated: 3}
> document = min(classify_outcome(account) for account in accounts)   # by rank
> reason   = "account_" + that account's reason      # printed order breaks ties
> ```
> with three document-level overrides, each of which can only LOWER the result:
> * no account at all → `("failed", "document_publishes_no_account")`;
> * an omission whose `reason` is not a ratified evidence class → `("failed", ...)`; it should
>   never have been published (L1-C17);
> * an omission on ratified evidence → the document may not be `validated`; it is
>   `("review", "sibling_section_omitted")`.

Fail-closed by construction: `validated` on a document now means *every account validated and
nothing was omitted*. It is strictly stronger than today's meaning, and on a single-account
document it IS today's meaning — measured, not asserted: the function reproduced
`classify_outcome` exactly on 208 of 208 documents in the cohort,
including under the document shape.

**Movement this creates.** A document whose account A validates and whose account B withholds
is `withheld` today-and-tomorrow at the document level, but today it is `failed` — the reader
refuses it outright (§9, the six refusal sites). `failed → withheld` is a ladder IMPROVEMENT
and counts as "other ladder movement", never as newly validated. **Ruling needed** (§8, Q1):
whether such a document should publish account A's figures at all, or refuse until every
account validates.

### 1.6 Cache and version keys

`webapp/artifact_cache.py`:436 `ANALYSIS_STAGE_VERSION = 16` is the analysis-cache key, and
:150-151/:165 state the rule: a payload-shape change must bump it **in the same commit**, or a
warm cache serves old-shape payloads for a new-shape build. This design's operational rule:

* a stage that moves **no** payload byte (proved by §1.2's byte comparison over its cohort) does
  **not** bump it;
* a stage that moves **any** payload byte on **any** document bumps it in the same commit, and
  its proof includes the archive sweep.

`webapp/storage.py`:70 `SCHEMA_VERSION = 4` needs no migration (:24-30, :591: the payload is
stored as opaque text). `telemetry/record.py`:42 `TELEMETRY_VERSION = 1` is bumped by the stage
that adds the per-account record projection (§5).

### 1.7 The multi-account signal the archive already carries and reads nowhere

`rows.csv` carries `likely_account_count` (`discovery/runner.py`:136, :519, `discovery/report.py`
:445) from `ocr/inspect.py::_account_count`:161-170, and `telemetry/record.py`:121/:130
annotates it *"ADVISORY — consumed by nothing"*. Measured over the whole run of record:

| `likely_account_count` | documents | of them `validated` |
|---:|---:|---:|
| 0 | 496 | 159 |
| 1 | 2,700 | 2,281 |
| 2 | 167 | 148 |
| 3 | 6 | 5 |
| 4 | 1 | 0 |
| 5 or more | 10 | 3 |
| **2 or more — the advisory L-1 exposure** | **184** | **156** |

It is a BOUND, not a partition — it counts distinct printed account-number VALUES, so a
document reprinting one account's number in two forms counts two, and a sibling printed without
a number counts one. It is reported here because it is the only archive-wide multi-account
signal that exists, and because it sizes the *outer* edge of the population any
publication-model change could touch. Nothing in this design consumes it, and nothing should:
the boundary layer establishes accounts from PRINTED PARTITION evidence (L1-C1), never from a
count of number-shaped tokens.

---

## 2. Per-account reconstruction and validation

### 2.1 The rule

Each account is reconstructed as its own `Statement` and handed to the **unchanged** validator:
`analysis/reconcile.py::reconcile` and `analysis/adb.py::compute_average_daily_balance`, called
exactly as `analysis/pipeline.py` calls them today (:696, and :745-754 →
`analysis/metrics.py`:437-458). **Not one line of either is touched** — only what they are
called on. That is R-b, and it is also what makes the measurement in §2.6 mean anything: the
2 documents that close, close under the validator the 2,596 were validated by.

### 2.2 Per boundary mechanism — what printed evidence establishes what

Four mechanisms, measured over 214 documents (`tools/l1_structure_census.py`, re-run at this
base):

| mechanism | documents | cross-account oracle | admissible under L1-C1? |
|---|---:|---|---|
| `rollup-oracle` — the document enumerates its accounts with a balance each, and each enumerated identity reappears as a section heading | **103** | **YES** | yes |
| `section-identity` — no enumerating table, but each section opens with a heading carrying its own identity | **38** | no | yes |
| `section-equation-scan` — no identity; boundaries inferred from the sections' own opening figures | **35** | no | **NO — refused** |
| `none` — no partition established | **38** | n/a | n/a; fails closed |

Fail-closed reasons for the 38 `none`: `no-rollup-caption` 22,
`rollup-enumerated-but-no-section-reappearance` 11, `rollup-enumerates-one-account` 5 — and the
last five are a correct answer, not a failure: the document really does cover one account.

For each admissible mechanism, the evidence ladder, in strict precedence order. **A section
that cannot fill a row from the sources listed for it is REFUSED, never defaulted.**

| what must be established | `rollup-oracle` | `section-identity` |
|---|---|---|
| **identity** | the enumerating table's row identity, which must reappear as the section heading (that reappearance IS the boundary) | the section heading's own identity token |
| **period** | the DOCUMENT's — `find_period` resolved once and handed to every section (§2.4) | the same |
| **opening** | the section's own printed opening caption; else the table's opening column **only where the table prints a column caption naming it** (L1-C5) | the section's own printed opening caption; there is no fallback |
| **closing** | the section's own printed closing caption; else the table's closing column under L1-C5 | the section's own printed closing caption |
| **ledger** | the section's own grid, bounded by its heading and the next section heading | the same |
| **stated counts / totals** | the section's own printed counts and totals where it prints them, fed to `reconcile` — never `None` where they are printed (L1-C8) | the same |
| **daily balances** | the section's own printed daily-balance TABLE where it prints one | the same |
| **cross-check** | every published section's closing must appear in that account's roll-up row under L1-C5's column roles, and where a cross-account total is printed the published sections must sum to it (L1-C10) | none exists; the section stands on its own printed pair |

Measured evidence availability over the 442 located sections — this is what the ladder above
has to work with, and it is the reason the demonstrated population is small:

| the section prints ... | sections | share |
|---|---:|---:|
| its own opening AND closing | 208 | 47.1% |
| its own ledger grid header | 273 | 61.8% |
| at least one dated row | 327 | 74.0% |
| its own counts / totals | 79 | 17.9% |
| **its own daily-balance TABLE** | **24** | **5.4%** |
| an explicit no-activity declaration | 31 | 7.0% |

And the roll-up, measured as an oracle: it states two balances per account on 60 documents, at
least one on 117, closes with a cross-account total on 37 — and **prints a COLUMN CAPTION
saying which figure is which on only 30 of 214**. That last number is L1-C5's whole reason for
existing: on the other 184 the enumerating table prints a name and some figures and never says
which is the opening. One issue in this population prints the ENDING figure first, and the
first version of the L1INV prototype assumed position; that assumption produced 23 false
closures and a headline four times too large.

### 2.3 The idle sibling — the ONLY admission of an omitted section

R-a: explicit structure must establish the sibling **and** its empty/silent state; absence of
parsed activity alone is insufficient. The ratified predicates are `analysis/symitar.py`'s own
`_DORMANT_RE` (:116) and `_yield_only` (:264-269, its four conditions at :329-346 including the
platform's six-figure equation row at :339-345). Applied section by section by calling that
module's own code (`tools/l1_split_prototype.py --idle-siblings`, re-run at this base):

| the 103 sibling sections of the 86 single-posting documents | sections |
|---|---:|
| print the ratified declaration | **4** |
| satisfy the yield-only arithmetic as written | **0** |
| POSTED a dated row and declare nothing | **30** |
| empty and silent — no declaration of any kind | 62 |
| declare idle in some other wording | 7 |

| the Stage-1 question | documents |
|---|---:|
| **EVERY sibling satisfies the ratified rule as written** | **0** |
| carry a sibling that POSTED and declares nothing (the L-1 defect itself) | **26** |
| no sibling section LOCATED at all — which is not "no sibling" | 16 |

**The population that needs no ruling is zero documents.** Under R-a as written, an
empty-and-silent section — a heading printed, no rows, no declaration — is *absence of parsed
activity* and may NOT be omitted. That reading is what makes the demonstrated population 2
rather than 8, and §8 Q3 is where it is put to Gustavo, with the one argument that could
defensibly move it: on the family that closes, the sibling is not merely silent — the
enumerating table prints a row for it, and the table's own closing column reproduces (§2.6).
Whether *"the table prints this account with a stated pair"* counts as explicit structure
establishing the empty state is a ruling, not a measurement.

**When a section IS omitted, the omission is SURFACED** — never silently:
`DocumentReport.omissions` carries `{label, reason, posting_count}`, the payload carries it
under `document.omitted_sections`, `assess_document_integrity` adds the note, and §1.5 forbids
such a document from being `validated`. `reason` comes from a closed vocabulary (L1-C17) in
which **`absence_of_parsed_rows` is not a member**.

### 2.4 The period, and why 27 documents lose every section at once

`find_period` is resolved ONCE per document and the same pair is handed to every section. That
is defensible on a member statement printing one cycle for all of a member's accounts, and it
is why **27 documents lose every section at once** — they print no resolvable period, so all 77
sections they carry are never offered (442 − 77 + 27 pseudo-sections = 392 objects offered; the
reconciliation is the instrument's own).

Where an issue prints a per-account activity RANGE instead of one document cycle, this rule
must say whose period it means before it becomes code. **Ruling needed** (§8, Q6). Until it is
answered, a document printing per-account ranges is refused under L1-C1's spirit: the period is
not established.

### 2.5 The ADB — per account, no document figure

R-c is unambiguous and this design does not soften it:

* every published account gets its own `compute_average_daily_balance`, calendar days over the
  printed period, with the production `posting_dates_cover_source` check applied against **that
  section's** text, and with the section's own printed daily balances supplied where it prints
  them (24 of 442 sections do — so **95% of sections rest on a reconstructed series**, which is
  a fact the ruling was made in the knowledge of);
* **there is no document-level ADB.** No sum of per-account ADBs, no ADB of summed daily
  balances, no field for either. `_metrics_dict` (`analysis/serialization.py`:102-133) already
  publishes exactly one ADB per payload and nulls it when the ledger is not validated; under
  this design there is one such block per ACCOUNT and none at document level;
* the roll-up's figures and the cross-account total are **oracles**: they refuse a document
  (L1-C10), and they never become a published value.

`analysis/adb.py`'s docstring says *"One statement or package yields exactly ONE user-facing
Average Daily Balance"*. Under this design a three-account document yields three. That is not a
contradiction if the doctrine's unit is read as the ACCOUNT rather than the PDF — which is the
reading R-c forces — but the docstring says "statement" and the word now means one account. It
must be amended to say so **in the same commit** as the first multi-account publisher, and the
amendment is a one-line doctrine clarification, not a policy change. **Ruling needed** (§8, Q5)
only to confirm that reading, and to say what a PACKAGE containing a multi-account document
publishes.

### 2.6 What closes today — measured, at this base

`tools/l1_split_prototype.py`, re-run at `ac1d034`. A section CLOSES when its chain is
non-empty, accounts for every dated row inside the span it walked, rests on a PRINTED boundary,
had its own stated evidence readable and fed, and both `reconcile` and the ADB return ok.

| rung | sections |
|---|---:|
| the walk reached the section's own printed closing | 109 |
| ... arriving with an EMPTY chain, no dated row printed — trivially idle, never a closure | 21 |
| ... arriving with an EMPTY chain over PRINTED dated rows — the false closure | 23 |
| non-empty chain | 65 |
| + no dated row unaccounted for INSIDE the span the chain walked | 54 |
| + boundary PRINTED rather than inferred (L1-C1) | 48 |
| + its own stated counts / totals / daily balances readable and fed (L1-C8) | 48 |
| + `reconcile.ok` | 37 |
| + `adb.ok`, source-coverage check applied | **29** |
| + nothing dated printed AFTER the chain reached the closing (a STRICTER bound, reported) | **16** |

| headline | value |
|---|---:|
| sections that CLOSE | **29** |
| **documents whose EVERY LOCATED section closes** | **2** |
| ... whose table's own CLOSING column reproduces every section's closing | **2** |
| documents where every section either closes or is trivially idle (i.e. under the ruling of §8 Q3) | **8** |
| ... with the table's closing column reproducing over the sections that would be PUBLISHED | **8** |

| by mechanism | docs | sections offered | closed | docs fully closing |
|---|---:|---:|---:|---:|
| `rollup-oracle` | 103 | 212 | 19 | **2** |
| `section-identity` | 38 | 89 | 10 | 0 |
| `section-equation-scan` | 35 | 84 | **0** | 0 |
| `none` | 38 | 7 | 0 | 0 |

`section-equation-scan` closing nothing is L1-C1 doing its work rather than an accident: an
inferred boundary is refused before the validator sees it.

The two oracles are not two: the walk accepts a movement only where the paper prints the
balance it lands on, so continuity and the closing identity hold BY CONSTRUCTION. `reconcile`
refused 11 of the 48 it was handed and the ADB refused 10 — and it can refuse *only* because
the sections' own printed counts, totals and daily balances are fed (L1-C8). Passing `None`
there disables the only checks capable of seeing a truncated ledger; the first prototype did,
and `reconcile` refused 0 of 105.

---

## 3. Transfers between a member's own accounts

### 3.1 What the paper prints

Measured (`tools/l1_split_prototype.py`, this base): **11 documents** reconstruct two or more
non-empty ledgers; **7 of them** carry same-day, same-magnitude, opposite-signed pairs across
two of those ledgers; **47 pairs** in total. The same money stands in two ledgers of one
document. A package that sums per-account deposits over such a document counts it twice — in
gross deposits, deposit counts, and every revenue, denominator and NSF derivation built on
them.

### 3.2 The rule (R-d)

> **A movement is INTERNAL when, and only when, a movement in a SIBLING account published on the
> SAME document has the same posting date, the same magnitude to the cent, and the opposite
> sign, and that pairing is one-to-one.**
> Where the paper prints a transfer designation on either leg, the designation must not
> contradict the pairing; where it prints one on neither, the arithmetic signature stands alone.

* **Both legs stay in their ledgers.** Removing either would break the account's own
  reconciliation and its ADB — the money really was in that account on that day. R-d says
  "remain in each account's ledger", and this is also the only way `reconcile` stays unchanged.
* **The flag lives at document level**, in `document.internal_transfers`, as an index pair
  `{a: [account_index, posting_index], b: [...], basis}`. Not on `Transaction`, and not on
  `TransactionClassification`: either would add a key to every transaction dict of every payload
  in the archive — the archive-wide cost §1.2 measured — to record a fact that cannot exist on
  a single-account document. It is a document-level fact and it is stored as one.
* **Package analytics exclude it.** `webapp/app.py::_package_analysis` (:579-1397) sums across
  members at :875-923 (credits, posted credits and counts, verified/unverified revenue,
  non-revenue, debits, cash flow, lender and potential-lender debits and counts, insurance,
  the withholding denominator, NSF count), builds a flattened combined ledger at :1042-1070, and
  takes a days-weighted ADB mean at :1152-1164. A posting indexed by
  `document.internal_transfers` is excluded from **every one of those**, and from
  `package_transactions`. The **per-account ADB is unaffected** — the balance was real.

### 3.3 Fail-closed on ambiguity

> If a candidate movement has **more than one** possible counterpart under §3.2 — two sibling
> postings of the same date and magnitude and opposite sign — **no pairing is recorded**, an
> integrity note `ambiguous_internal_transfer` is attached, and the package layer **refuses to
> aggregate that document** rather than aggregating it wrongly.

Never guess: a wrong pairing silently removes a real deposit from a package total, which is
worse than refusing the package. **Ruling needed** (§8, Q2): whether ambiguity refuses only the
aggregation (this design's proposal) or the whole document.

**Ruling needed** (§8, Q2, second half): whether a counterpart must be on the SAME document.
This design says yes — a counterpart on another document in the same package is not printed
evidence of an internal movement, it is a coincidence of date and amount, and pairing across
documents would let two unrelated statements cancel each other's deposits.

### 3.4 What exists today

There is **no transfer or self-pair detection anywhere** in `webapp/app.py`.
`_package_duplicates` (:542-576) dedups by `content_sha256` only — two accounts of one PDF do
not present as duplicates. The cross-currency refusal (:1242-1263 with
`_CROSS_CURRENCY_TOTAL_KEYS` :465-498) counts currency **per member**, not per account, so two
differently denominated accounts inside one document are invisible to it today. Both are named
in §5 as surfaces this design changes.

---

## 4. Fail-closed conditions — complete, and testable

Every condition below is a predicate with an exact refusal, a measured killer population, and
the mutant that must be killed. **L1-C1 … L1-C7 and L1-C10 … L1-C14 are PARSE-TIME gates**: a
failing condition means the reader returns `None`, the document is unclaimed, and its outcome
is exactly what it is today (`failed`). Only L1-C8 and L1-C9 are post-parse, and those two are
already expressed by the per-account `classify_outcome`. **No condition below can promote a
document.**

`L1-C1` … `L1-C15` restate the L1INV packet's thirteen plus its two standing conditions, with
the refusal and the killer made explicit. `L1-C16` … `L1-C18` are new, and each was found by
this cell.

| id | predicate | refusal | measured killer population |
|---|---|---|---|
| **L1-C1** | every published section's boundary is PRINTED — an enumerating roll-up whose identities reappear as section headings, or section headings each carrying their own identity | reader returns `None` | 35 documents are `section-equation-scan`; they close **0** sections today |
| **L1-C2** | the published sections are disjoint and cover the document's ledger region completely | `None` | a page-break reprint that omits the continuation word satisfies C1 and nothing else forbids publishing it twice — the mutant is a duplicated section |
| **L1-C3** | the identities are distinct; two sections resolving to one token, or a `product_name_only` identity shared by two sections, refuses | `None` | 0 documents violate it today; **44 enumerating tables print a repeated token** — a hazard for the LOCATOR, not for this condition |
| **L1-C4** | every posting section is accounted for; a section with a dated ledger row may not be dropped. Omission ONLY under §2.3, and always SURFACED | `None`, or an omission record | **26** documents carry a sibling that posted and declares nothing; **0** documents have every sibling satisfying the ratified rule |
| **L1-C5** | where a section takes its opening or closing from the enumerating table, the table must print a COLUMN CAPTION naming which column is which; position is never evidence | `None` | **30** of 214 documents print such a caption; **184 print none**; this condition's absence produced 23 false closures |
| **L1-C6** | each published section states its own opening and closing, or the table states them under C5; where both are printed they agree to the cent | `None` | **2** sections fail exactly here |
| **L1-C7** | no published section closes on an empty or partial ledger: a section printing a dated row may not publish zero transactions, and the published ledger accounts for every dated row inside the span it read | `None` | **23** sections would close vacuously without it; **11** more leave a hole inside their own span |
| **L1-C8** | `reconcile(section).ok`, with the section's own stated counts and totals supplied wherever it prints them — never `None` where they are printed | not validated (per-account outcome) | 79 of 442 sections print them; `reconcile` refuses **11 of 48** when they are fed and **0 of 105** when they are not |
| **L1-C9** | `compute_average_daily_balance(section).ok` under the ratified calendar-day doctrine, `posting_dates_cover_source` applied against the SECTION's text, the section's own printed daily balances supplied where printed | not validated (per-account outcome) | the ADB refuses **10 of 48**; **24 of 442** sections print a daily table |
| **L1-C10** | the roll-up reproduces: every published section's closing appears in that account's row under C5's roles, and where a cross-account total is printed the published sections sum to it. A mismatch refuses the DOCUMENT, not the section | `None` | 43 documents print a cross-account total; the table reproduces on the **2** that close |
| **L1-C11** | no money moved between the member's own accounts is counted twice (§3) | package refuses to aggregate | **7** documents, **47** pairs |
| **L1-C12** | a facility enumerated on the table is never published as a deposit section, and C10's cross-account total is neither required nor satisfiable where the total includes one. The class of a row is established from the ROW, not from a word in it | `None` for the section; C10 suspended for the document | **19** documents enumerate one; **4** of them carry two or more posting sections (all one family); **7** of the 19 also print a cross-account total |
| **L1-C13** | one currency per section, established at SECTION level by the doctrine's hierarchy; a document printing two denominated columns refuses | `None` | **4** documents, one census group, **12** sections |
| **L1-C14** | no statement-specific constant anywhere in the split: an account number, a product name or a memorised heading is R-1 | test failure (`tests/test_no_statement_hardcodes.py`) | `analysis/consumers.py`:88-94 today (§9, F3) |
| **L1-C15** | zero inference — deterministic, $0, no model call | — | standing |
| **L1-C16** | *(new)* a payload carrying `accounts` never also carries `statement`; a reader given a payload with neither raises `ValueError` | `ValueError` at the reader | measured: **6 of 6** probed readers ANSWER the untaught shape today instead of refusing it (§1.4) |
| **L1-C17** | *(new)* an omission's `reason` is from a CLOSED vocabulary, every member of which names PRINTED evidence: `printed_dormancy_declaration`, `yield_only_arithmetic_with_summary_equality`. **`absence_of_parsed_rows` is not a member** | `None` — the document may not publish | §9 F1/F2: the two skips production performs today are absence-based, on the cohorts §6.2 sizes |
| **L1-C18** | *(new)* no reader selects an account by a DERIVED quantity — most transactions, largest balance, first printed. Selection is by printed partition or there is no selection (R-e) | `None` | §9 F4: `analysis/community_section.py`:731-733 selects the busiest section today, on a cohort that includes a pinned document |

**Currency, at section level (L1-C13, serving R-f).** The doctrine resolves a denomination per
DOCUMENT today and `jurisdiction_default` is affirmative evidence at the INSTITUTION level. Per
section:

* `printed` and `product` evidence must be read from the SECTION's own text; a section may
  **not** inherit a sibling's `printed` evidence — that is exactly the silent denomination R-f
  forbids;
* `jurisdiction_default` and `institution_default` are document/institution facts and are
  inherited by every section that earned no stronger class of its own;
* two published sections resolving to different denominations → **ruling needed** (§8, Q4):
  R-f says "publishes two accounts or refuses", and both are consistent with the currency
  doctrine's ban on cross-currency package math. The measured population is 4 documents / 12
  sections, all one census group.

**Mutation tables.** Every condition that becomes code gets a mutant that removes it and a named
killer test, and the killers of C4/C5/C6/C7/C10/C11/C12/C13 are drawn by sha from the
populations above. A test named after a gate is not a test of that gate.

---

## 5. Surfaces touched, file by file

`nothing` in the middle column means: byte-identical payload, unchanged behaviour, proved by
§1.2's byte comparison plus the archive sweep. Line numbers are at this base.

| file | single-account document | multi-account document |
|---|---|---|
| `analysis/schema.py`:121-221 | nothing — `Statement` unchanged; only its docstring says "one account" | unchanged; one instance per account |
| `analysis/pipeline.py`:153-163, :515-519 | nothing — `analyze_markdown` keeps returning one `Report` for a one-account document | new `DocumentReport` (§1.1); a document-level entry point returning it; RULE S at the seam |
| `analysis/pipeline.py`:260-512 `assess_document_integrity` | nothing | split by scope: `missing_declared_statement_page` (:409-486), `parser_ambiguous`/`parser_exception` (:345-358) and `repair_exception` (:388-395) are DOCUMENT facts and move to the document block; the reconciliation, coverage and count flags (:288-344) and all of `assess_quality` (:179-240) are per ACCOUNT and stay there |
| `analysis/reconcile.py`, `analysis/adb.py`, `analysis/metrics.py` | nothing | **nothing** — called per account, unchanged (R-b). `adb.py`'s docstring gains the one-line unit clarification of §2.5 |
| `analysis/serialization.py`:136-194 | nothing — RULE S returns `report_to_dict(accounts[0])` verbatim | a `document_report_to_dict`; per-account payloads are today's payload each; the per-account `ending_balance` nulling (:146-151) becomes a per-account decision |
| `analysis/revenue.py`:53-173 | nothing | runs PER ACCOUNT; `setdefault("statement", {})` (:55-56) becomes a shape assertion (L1-C16) — today it silently rebuilds every view over an empty ledger |
| `analysis/count_semantics.py` | nothing | any per-section stated-count reading declares its mapping here; `tests/test_count_semantics.py` is in the canonical conformance set |
| `analysis/transaction_classifier.py` | nothing | classification runs per account; no field added (§3.2) |
| `telemetry/record.py`:322-370 | nothing — `classify_outcome` unchanged and still the answer | `classify_document` (§1.5) in front of it; `TELEMETRY_VERSION` (:42) bumped by the stage that adds the per-account projection |
| `corpus_gate.py`:1298-1370 `production_verdict` | nothing | returns one verdict per ACCOUNT plus a document verdict; `_Verdict` (:202-210) gains an account discriminator |
| `corpus_gate.py`:217 `PINNED_OUTCOMES`, :424 `PINNED_CURRENCY`, :594 `PINNED_CURRENCY_SOURCE` | nothing | all three are keyed by corpus-relative PATH only; a multi-account pinned document needs a path+account key, and the totality subtractions at :1503-1513 / :1572-1582 follow |
| `corpus_gate.py`:1213-1268 `check_outcomes`, :1651-1733 `check_outcome_classes` | nothing | one row per document stays; the per-account assertions are new checks beside them |
| `docs/balance-metrics-audit-results.csv`, `docs/adb-audit-results.csv` | nothing | both are path-keyed with no account column — a multi-account pinned document cannot declare a second opening/ending/ADB until they gain one. **A truth-set ceremony** |
| `discovery/runner.py`:119-176, :654-657, :661-665 | nothing | `statement_bank` (:162) and `account_last4` (:163) are the only two Statement-derived columns; they become the FIRST account's, plus a new `account_count`. One row per document stays |
| `discovery/report.py`:443-453 `ROW_FIELDS`, :31-106 `folder_agreement` | nothing | one bank label per document is `folder_agreement`'s assumption (:95-106); a document whose accounts share an issuer is unaffected, and one whose accounts do not is a refusal (they are one member statement) |
| `discovery/compare.py`:37-52, :71-160 | nothing | **nothing** — the ladder stays keyed on `content_sha256` with one outcome per document, which `classify_document` supplies (§1.5). This is why the document outcome is a fold and not a list |
| `discovery/evidence.py`:94-121 | nothing | `Document` is per-sha and stays |
| `webapp/app.py`:1577-1585 `/analysis`, :1808-1841 `/download` | nothing | serve the document payload; `_masked` (:182-195) is key-name based and already account-count agnostic |
| `webapp/app.py`:285-307 `_analysis_rows` | nothing | **hard one-account assumption**: it iterates the literal section list at :287 and two accounts collide on `("statement", "ending_balance")`. The section key gains the account index |
| `webapp/app.py`:235-266 `_adb_rows` | nothing | one ADB block today; one per account, no document block (R-c) |
| `webapp/app.py`:579-1397 `_package_analysis` | nothing | each account enters the package as its own member (§8 Q5); every sum at :875-923, the flattened ledger at :1042-1070 and the weighted ADB at :1152-1164 exclude postings indexed by `document.internal_transfers`; `_package_duplicates` (:542-576) learns that two accounts of one sha are not duplicates; `_statement_currency` (:519-539) counts per ACCOUNT |
| `webapp/app.py`:318-362 `_package_rows` | nothing | `document_{idx}` (:330-332) is per JOB; it becomes per account with the document named |
| `webapp/jobs.py`:61-66 `_classification_for` | nothing | reaches `analysis["statement"]["transactions"]`; takes the account path |
| `webapp/storage.py`:70, :591, :614-616 | nothing — payload stored as opaque text, no migration | nothing |
| `webapp/artifact_cache.py`:436 | nothing — not bumped by a byte-identical stage | `ANALYSIS_STAGE_VERSION` bumped in the SAME commit as any payload-shape change (:150-151, :165) |
| `webapp/static/app.js`:1078-1177, :256-277 | nothing | one statement panel today; an account selector, one panel per account, and the omission note rendered |
| `benchmark/expectations.py`:23-54, :62-103 | nothing | one expected value per field per document; a multi-account document has nowhere to declare a second opening/ending/ADB. Follows the two CSVs |
| `benchmark/ourside.py`:88-113, `batch.py`:87-176 | nothing | one row per document today; one per account |
| `balance_forensic_audit.py`:650-700 | nothing | asserts `document_{index}` package rows; follows `_package_rows` |

---

## 6. Regression surface and proof plan

### 6.1 The protected archive

| surface | scale | proof |
|---|---:|---|
| every document in the run of record | **3,380** | archive sweep `tools/regfp_zero_movement_sweep` over the WHOLE range at the final tree of any stage that moves a payload byte |
| the protected `validated` set | **2,596** | `cohort_replay` per touched registration + the sweep; any `validated → anything` is BLOCKING |
| the pinned corpus | 109 listed, all 109 digested, **80 present in the run**, 29 not | `corpus_gate.py` GREEN 105 PASS / 3 WITHHELD / 1 REFUSED, unmoved |
| the corpus-marked slice | 30 | unmoved |

### 6.2 The cohorts, named and sized

Every registration whose module carries an L-1 gate or a silent sibling skip. These are the
`cohort_replay --parser <id>` populations. `community_section` is ONE module under THREE
registration ids and each id is its own population.

| registration | module | documents in the run | `validated` (protected) | other outcomes |
|---|---|---:|---:|---|
| `huntington` | `huntington` | 38 | **38** | — |
| `community_section` | `community_section` | 61 | **59** | `review` 2 |
| `dakota_west` | `community_section` | 3 | **3** | — |
| `mission_valley` | `community_section` | 36 | **36** | — |
| `navy_federal` | `navy_federal` | 52 | **52** | — |
| `capital_one` | `capital_one` | 22 | **21** | `withheld` 1 |
| `consumers` | `consumers` | 2 | **2** | — |
| `symitar` | `symitar` | 7 | **7** | — |
| `zions` | `zions` | 13 | **12** | `withheld` 1 |
| **total** | | **234** | **230** | |

The 24 documents these readers REFUSE today (huntington 4, community_section 7, navy_federal 4,
capital_one 6, consumers 3) are not in the table above — a refused document is claimed by
nobody. They are the population any stage that opens a refusal must name, and the L1INV packet
measures them from each reader's own gate.

### 6.3 The pinned exposure

| measure | value |
|---|---:|
| pinned documents listed in the manifest | 109 |
| ... whose bytes were read and digested | 109 |
| ... present in the run of record | 80 |
| ... NOT in the run, so not surveyable through it | 29 |

| registration | pinned documents it claims in the run |
|---|---:|
| `navy_federal` | 4 |
| `capital_one` | 4 |
| `dakota_west` | 1 |
| `consumers` | 1 |
| **total pinned on an L-1 module** | **10** |

Structurally, 12 of the 80 pinned documents present in the run print two or more posting
sections — 4 established by `rollup-oracle` (strong), 1 by `section-identity` (strong), and **7
by `section-equation-scan`, which L1-C1 refuses outright**, so those 7 are unproven and are
treated as unproven. `05E246C0ED6678E6`, the CONS-L1 / CONS-HARDCODE document, is in the strong
class.

**The truth-set ceremony.** Exactly one pinned document is expected to move under this design,
and it moves in stage S5:

| pinned sha16 | registration | today | after S5 | why it is a ceremony |
|---|---|---|---|---|
| `05E246C0ED6678E6` | `consumers` | published under a memorised product-name + account-number slice (`consumers.py`:88-94) | either published from the printed partition, or REFUSED under L1-C1/C4 | the PUBLISHED LEDGER changes — a different set of postings, a different opening and closing, a different ADB. Not a parser fix: the audit CSVs' expected values for this path must be re-derived and re-approved before the change lands |

Every other pinned document is expected to be **byte-identical**, and that expectation is the
gate: a pinned mover outside this table is a STOP-and-report.

### 6.4 Per stage

Every stage owes, at its closure tree, in this order:

1. `cohort_replay --expect-identical` at BASE over its target cohort and over the baseline
   cohort of every registration of every module it touched (fidelity: exit 0);
2. the same at the closure tree — `newly validated | other ladder movement | previously
   validated preserved (payload identical / changed, with leaf PATHS) | validated regressions
   (BLOCKING, exit 2)`;
3. **a BYTE comparison alongside it** (§1.3) — `cohort_replay`'s leaf projection cannot see an
   added empty-list key, and this design's payload-shape stages add exactly that class of key;
4. a MUTATION TABLE for every condition of §4 that became code in that stage: each mutant
   applied exactly as documented, run without `-x`, every killer named, killers drawn by sha
   from the measured populations in §4;
5. the archive sweep, at the final tree, whenever a payload byte moved or a reader changed —
   every `moved` / `no_payload_now_publishes` / `payload_now_raises` finding inside the stage's
   NAMED population by sha, or it is a regression to explain or remove;
6. full default suite; canonical guards (255, 5 files); canonical conformance (1,270, 7 files);
   `python corpus_gate.py` GREEN 105/3/1; the corpus-marked 30;
7. privacy scan of added lines against the whole named population = 0; commit-message scan = 0.

### 6.5 The corpus gate's new per-account assertions

Added by stage S3, dark, and lit by S4:

* every account of a published document has its own `_Verdict`, and the document verdict is the
  fold of §1.5 — asserted both ways, so a document verdict that does not follow from its
  accounts fails the gate;
* `PINNED_CURRENCY` / `PINNED_CURRENCY_SOURCE` totality holds per (path, account);
* the ADB basis and policy stamps (`calendar_day_printed_period`, `canonical_v1`) are asserted
  on **every account** and **no document-level ADB field exists** — a gate that goes red if a
  document ADB is ever reintroduced (R-c, made mechanical);
* a published document's `document.omitted_sections` reasons are all in L1-C17's vocabulary;
* `document.internal_transfers` indices resolve, are one-to-one, and are excluded from the
  package totals `balance_forensic_audit.apply_package_results` asserts.

---

## 7. Staged delivery

Six stages. Each is an independently provable card with its own base, its own cohort, its own
mutation table and its own hostile review. **The order is not the card's suggested order**, and
the two changes are both forced by measurement:

* **the surfaces are taught BEFORE the first publisher, not after** (§1.4: the untaught failure
  is quiet — a valid multi-account document would be filed `withheld` with a reason naming a
  check nobody ran, and every revenue view would be rebuilt over an empty ledger);
* **transfers land WITH the first publisher, not after it** (§3: the moment two ledgers exist on
  one document, package math double-counts; the 47 pairs are S4's live killers).

| stage | files | expected safely recoverable, MEASURED | pinned movement | proof plan |
|---|---|---|---|---|
| **S1 — the wrapper and RULE S** | `analysis/pipeline.py` (the three dataclasses + the document seam), `analysis/serialization.py` (`document_report_to_dict`, RULE S), docstring of `analysis/schema.py` | **0 newly validated. 0 documents move.** `accounts` is length 1 on every document by construction; RULE S returns today's dict verbatim — measured byte-identical on 208 of 208 documents across 71 registrations | **none** | `cohort_replay --expect-identical` over every registration + BYTE comparison (§1.3) + archive sweep (0 findings expected, and 0 is the pass condition). `ANALYSIS_STAGE_VERSION` NOT bumped |
| **S2 — SIBLING-OMISSION-SURFACE** | `analysis/pipeline.py` (`SiblingOmission`, the integrity note), `analysis/symitar.py`, `analysis/community_section.py`, `analysis/zions.py` — the skip SITES only | **0 newly validated.** Payload movement on the documents whose reader skips a section today. Measured over the four probed registrations: **105** validated documents read, **15** print two or more of their OWN module's section marks while publishing one account (symitar 7 of 7, `dakota_west` 3 of 3, `community_section` 5 of 59, `mission_valley` 0 of 36), and only **4** print the ratified declaration — all four symitar. §9 F1/F2: on today's evidence most of these skips have no member of L1-C17's vocabulary to name, which is what makes this stage a correctness card and not a cosmetic one | **none expected** — a pinned mover is a STOP | mutation table on the omission-reason vocabulary; `cohort_replay --parser` for symitar / community_section ×3 / zions; BYTE comparison; archive sweep with every mover named by sha. `ANALYSIS_STAGE_VERSION` bumped (payload bytes move on the named documents) |
| **S3 — the surfaces, taught DARK** | `telemetry/record.py`, `analysis/revenue.py`, `analysis/count_semantics.py`, `corpus_gate.py`, `discovery/runner.py`, `discovery/report.py`, `webapp/app.py`, `webapp/jobs.py`, `webapp/static/app.js`, `benchmark/expectations.py`, `benchmark/ourside.py`, `batch.py`, `balance_forensic_audit.py` | **0 newly validated. 0 documents move** — production emits no multi-account payload at this tree, so every branch added here is unreachable in production and exercised only by unit tests and a gate fixture | **none** | unit tests per reader over synthetic document payloads; the shape assertion (L1-C16) with a mutation table; `cohort_replay --expect-identical` over EVERY registration; BYTE comparison; archive sweep 0 findings. `TELEMETRY_VERSION` bumped |
| **S4 — the first publisher + transfers** | a new shared CU member-statement template module (the `rollup-oracle` mechanism), its registration, `analysis/pipeline.py` (transfer identification), `webapp/app.py` (`_package_analysis` exclusions) | **2 documents** close on every located section today, both one census group, both with the enumerating table's own closing column reproducing. **8** if §8 Q3 is granted (a section that prints no dated row and reads nothing may be OMITTED rather than counted) — all eight the same family, all eight with the table reproducing over the sections that would be published. Beyond that family the reachable set depends on per-family row grammars and a better boundary layer, and this design declines to put a number on it | **none** | mutation tables for L1-C1…C13; the 47 transfer pairs on 7 documents as the package exclusion's named killers; `cohort_replay --group` per census group claimed; the whole-archive sweep; corpus gate's new per-account assertions lit |
| **S5 — CONS-HARDCODE** | `analysis/consumers.py` (:88-94 and the second copy at :115-123) | **0 newly validated** — the `DECL-L1-CANDIDATE` band closes **0** of 16 multi-posting documents today. This is a CORRECTNESS card: it removes an R-1 hardcode that publishes one memorised account of a member's several | **1 — `05E246C0ED6678E6`** (§6.3). Ceremony required BEFORE the change lands | truth-set ceremony; `cohort_replay --parser consumers` (2 documents in the run, both `validated`, one of them the pinned one); corpus gate; the audit CSVs re-derived and re-approved |
| **S6 — the remaining mechanisms** | per-family row grammars on the shared template | **an ESTIMATE, and it is not offered.** What is measured: 29 of 392 sections close today; `section-identity` closes 10 sections and 0 documents; `section-equation-scan` closes 0 and always will (L1-C1) | unknown; each family carded separately | as S4, per family |

**The honest total.** Across all six stages the measured newly-validated count is **2**
documents today and **8** under one ruling — out of a run of 3,380 with 2,596 validated. The
work is worth doing for what it fixes, not for what it adds: four production defects (§9), two
silent skips the platform carries today with nothing in the payload to show for them, a
memorised account number selecting the ledger on an audited pinned document, and a publication
model that cannot say "this statement covers three accounts". If
that trade is not worth it, the place to stop is **after S2** — S1 and S2 together repay the
standing debt, move nothing, and leave the rest carded.

---

## 8. Rulings still needed

| | question | what it decides | measured population |
|---|---|---|---|
| **Q1** | When one account validates and another does not, does the document publish the validating account's figures (as `withheld`/`review` at document level) or refuse entirely? | whether the model produces `failed → withheld` improvements or nothing at all until every account closes | every multi-account document that partially closes; today all such documents are `failed` |
| **Q2** | Must a transfer's counterpart be on the SAME document to be INTERNAL (this design says yes)? And does an AMBIGUOUS pair refuse only the package aggregation (this design's proposal) or the whole document? | §3.2, §3.3 | 7 documents, 47 pairs |
| **Q3** | May a section that prints no dated row and reads nothing be OMITTED rather than counted — where the enumerating table prints a row for it and the table's own closing column reproduces? R-a says absence of parsed activity alone is insufficient; the question is whether a printed table row stating that account's pair IS explicit structure establishing the empty state | **2 documents → 8**; and beyond that family, whether 44 of the 86 single-posting documents (siblings empty-and-silent, or declaring idle in a wording symitar does not read) are reachable at all | 8 documents on one family; 62 empty-and-silent sibling sections and 7 in other wording across the population |
| **Q4** | Two published sections in two denominations: publish two accounts, or refuse the document? R-f allows both | L1-C13 | 4 documents, one census group, 12 sections |
| **Q5** | Does each account of a multi-account document enter a PACKAGE as its own member? And is `analysis/adb.py`'s "one statement yields one ADB" read as one ACCOUNT yields one ADB (which R-c forces)? | §2.5, §3.2, `_package_analysis` | the package layer; 95% of sections print no daily table of their own |
| **Q6** | Where an issue prints a per-account activity RANGE rather than one document cycle, whose period does L1-C9 mean? | §2.4 | 27 documents lose every section today for printing no resolvable period at all; the per-account-range class is not separately measured |
| **Q7** | The posting threshold: is "a section that posts" one dated row or two? | the whole population's size | at two rows: 86 single-posting / 81 multi-posting. At one row: 59 / 111. The 2 documents that close, close at BOTH |
| **Q8** | §9 F1/F2: symitar and community_section skip sections on the ABSENCE of parsed rows today, which R-a names insufficient. Does R-a apply to those EXISTING skips (which would move already-validated documents), or only to new admissions? | whether S2 is a payload-only card or a correctness card that can REMOVE validated documents | the cohorts of §6.2 |

**Q8 is the one to answer first.** It is the only question here whose answer can subtract from
2,596.

---

## 9. Four defects in production code, found by this cell

Each was verified by reading the code at this base, and each is a fact about what the platform
does today — not a proposal.

**F1 — the ratified dormancy predicate is not the one production runs.**
`analysis/symitar.py`:116 defines `_DORMANT_RE`, and the module's docstring (13-48) ratifies the
skip it licenses. Measured by grep at this tree: **`_DORMANT_RE` is referenced by no code in
`analysis/` or `tests/`.** Its only consumers in the repository are `tools/l1_split_prototype.py`
and prose. What production actually executes for the dormant skip is `symitar.py`:421-422
`if not rows: continue` — a skip on the ABSENCE of parsed rows, which R-a names insufficient on
its own. The yield-only skip at :425 IS on printed evidence and IS the ratified predicate,
including its fourth condition. So one of the module's two ratified skips is implemented as
ratified and the other is not.

**F2 — the same shape in `community_section`.** `analysis/community_section.py`:984 counts a
section only `if stmt is not None and stmt.transactions`, and :988's `len(parsed) != 1` gate
then decides the document. A section that parses but posts nothing is silently not counted —
absence of parsed activity again, and the document publishes as if the section were not there.

**F1/F2, sized** (`tools/l1_design_surface_census.py`, each module probed with its OWN
committed patterns — `symitar._SECTION_MARK_RE`, `community_section._PLATFORM_ACCOUNT_RE` /
`_ACCOUNT_HEADING_RE`, and `symitar._DORMANT_RE` for the declaration):

| registration | `validated` documents read | print 2+ of their own section marks while publishing ONE account | print the ratified declaration |
|---|---:|---:|---:|
| `symitar` | 7 | **7** | 4 |
| `community_section` | 59 | **5** | 0 |
| `dakota_west` | 3 | **3** | 0 |
| `mission_valley` | 36 | 0 | 0 |
| **total** | **105** | **15** | **4** |

A section-mark count is a BOUND, not a partition: a document printing two distinct section
marks and publishing one account either dropped a section or reprinted a heading, and no
instrument outside the reader itself can tell those apart. That is precisely why the design
makes the omission a PAYLOAD FIELD written by the reader that made the skip, rather than a
count in a report — the reader is the only thing that knows.

**F3 — a memorised account number selects the ledger on a pinned audited document.**
`analysis/consumers.py`:88-94 slices the document between a memorised product-name-plus-
account-number literal and a memorised end caption; :115-123 restates the same literal in the
summary regex. It is R-1 in its purest form: the reader publishes exactly one account of one
member and is unusable for any other customer of that institution. Its detection markers claim
the document on its ALL-ACCOUNTS summary caption. This is CONS-HARDCODE and it is S5.

**F4 — an arbitrary account selection is already in production.**
`analysis/community_section.py`:701-735 `parse_dakota_west_statement` selects "the section with
the most transactions" (:731-733, and its docstring calls this "primary-account semantics"). It
is a derived selection — R-e's "no arbitrary selection" — on a registration that claims a
pinned document. It replaced an earlier hardcoded account number, so it was an improvement; it
is still not printed evidence of which account the document is about. L1-C18 forbids it, and
removing it moves that document. Related and smaller: `parse_mission_valley_statement`
(:682-691) hardcodes `account_name="Business Checking"` and keys its account-number pattern on
that literal.

**F5 (an instrument discrepancy, not a defect in production).** `tools/l1_split_prototype.py`
:1246 prints the first ladder rung as `len(walked) + empty_idle + empty_vacuous`, which
double-counts the two empty-arrival classes it then lists as sub-rows of that rung. At this
base it prints **153** where the published packet's §5.2 table prints **109**. 109 is
`len(walked)` and is the semantically correct figure (109 − 21 − 23 = 65 = the "non-empty
chain" row, which reconciles). No conclusion in the packet or in this design depends on the
printed value — every downstream rung is computed from `walked` and `non_empty`, not from the
sum — but the packet's claim that every number in it reproduces from its instruments is not
true of that one cell. Reported, not fixed: this cell owns no L1INV file.

---

## 10. Provenance and proof floor

### 10.1 The L1INV packet's numbers, re-run at this base

Every load-bearing figure of `L1_CU_SUFFIX_RULING_PACKET.md` was re-measured at `ac1d034` by
re-running its own three instruments against the run of record and its cold cache.

| figure | packet | this base | agrees |
|---|---:|---:|---|
| boundary mechanisms (rollup-oracle / section-identity / section-equation-scan / none) | 103 / 38 / 35 / 38 | 103 / 38 / 35 / 38 | yes |
| sections located / offered | 442 / 392 | 442 / 392 | yes |
| sections that CLOSE | 29 | 29 | yes |
| documents whose every located section closes | 2 | 2 | yes |
| ... under omission of a trivially idle sibling | 8 | 8 | yes |
| `reconcile` / ADB refusals of the 48 | 11 / 10 | 11 / 10 | yes |
| multi-posting documents (2-row / 1-row threshold) | 81 / 111 | 81 / 111 | yes |
| transfer documents / pairs | 7 / 47 | 7 / 47 | yes |
| sibling sections (declaration / yield-only / posted-and-silent / empty-and-silent / other) | 4 / 0 / 30 / 62 / 7 | 4 / 0 / 30 / 62 / 7 | yes |
| documents where every sibling satisfies the ratified rule | 0 | 0 | yes |
| documents carrying a sibling that posted and declares nothing | 26 | 26 | yes |
| sections printing their own daily-balance table | 24 (5.4%) | 24 (5.4%) | yes |
| roll-ups printing a COLUMN CAPTION | 30 of 214 | 30 of 214 | yes |
| roll-ups enumerating a facility / of them multi-posting / with a total | 19 / 4 / 7 | 19 / 4 / 7 | yes |
| two-denomination documents / sections | 4 / 12 | 4 / 12 | yes |
| the first ladder rung (§5.2 row 1) | 109 | **153 printed** | **no — F5**, a display double-count; 109 is correct |

### 10.2 This cell's instruments

* `tools/l1_design_payload_probe.py` — the four payload variants, byte-compared and
  leaf-compared, over a per-registration cohort; the document outcome function.
* `tools/l1_design_surface_census.py` — the regression-surface census: run scale, the advisory
  account-count signal, the per-registration cohorts, the silent-skip probe on each module's own
  patterns, the pinned exposure.
* `tools/l1_design_reader_probe.py` — every payload reader that is a pure function of the
  payload dict, in three shapes.

All three are unregistered, imported by nothing outside `tools/`, and reach no network.

### 10.3 Proof floor at this tree

| proof | result |
|---|---|
| canonical guards (5 files), with the three prototypes present | **255 passed — EXIT=0** |
| `tests/test_experiments_are_not_wired.py` | passes; it guards `experiments/` and says nothing about `tools/` — the property here is held by a GREP, not by a gate, exactly as the L1INV packet's MINOR-4 recorded. A `tools/` clause in that guard is a production-test change this card does not own |
| the instruments are unwired | nothing outside `tools/` references any of the three, verified at this tip |
| no production file differs from base | `git diff --stat ac1d034 -- analysis ocr webapp discovery telemetry corpus_gate.py benchmark` — **empty** |
| branch privacy scan vs the whole population | **hit_count 0** over 1,922 added lines and 3,351 documents read (population 3,380; the 29 with no cached text are the same 29 the pinned survey cannot reach). MONEY / DIGITS / DATES / WORDS all 0. Raw scan 22, every one of them class WORDS, discarded by `words_class` — the standing exclusion applied at the batch-8 train, whose own docstring says the tree is unaudited for customer names by construction. This document names no census family and no institution outside a registration id |
| commit-message scan | **hit_count 0**, MONEY / DIGITS / DATES / WORDS all 0 |
| the three L1INV instruments re-run from the run of record | EXIT=0 each; §10.1 is the ledger |

No mutation table and no archive sweep are owed: this card adds no gate and no grammar to
production. The full suite, the canonical conformance set and the corpus gate are not re-run —
the diff against base is this document, the W3 section and three files under `tools/`. That is
a structural argument, and it is offered as one.
