# L-1 independent-account architecture — DESIGN (batch 9, cell `L1-ARCH-DESIGN`)

DESIGN ONLY. No production file changed, nothing registered, no test wired. Ocean reviews and
composes; implementation cells follow this document, one slice at a time.

Every number here is produced by a committed instrument and reproduces from the run of record
`discovery_reports/TRAIN8-7185633/2026-08-28T224640.553059-0000-cda8882d` and its cold cache
`.claude/recovery/webapp_data_train8_cold`, both read-only. The instruments are
`tools/l1_census.py`, `tools/l1_structure_census.py`, `tools/l1_split_prototype.py` (the L1INV
cell's, re-run at THIS base — §10.1 is the reproduction ledger) and this cell's own
`tools/l1_design_payload_probe.py`, `tools/l1_design_surface_census.py`,
`tools/l1_design_reader_probe.py` and `tools/l1_design_idle_evidence.py`.
No printed value, name, account number, amount or date
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
proof of §1.2 to be re-argued for a cosmetic reason. What changes is a COMMENT above it, which
will say what it has always meant: *one account*. The word "statement" keeps meaning "one
account's statement", and the new word for "one PDF" is **document**.

> **A COMMENT, NEVER THE DOCSTRING — the docstring is a model prompt.** *(Corrected by S1, which
> found it while implementing this paragraph; the first version of this design said "docstring"
> here and in two more places.)* `analysis/extract.py`:222 passes `Statement` as the extraction
> call's `response_schema`, and pydantic publishes a model's docstring as its JSON-schema
> `description`. Prose written here is therefore not a note to the next implementer: it is text
> handed to a language model in the one call this platform makes about a document's own figures.
> The hazard is the schema's REACH, not this one class — `Transaction` and
> `StatementDailyBalance` are nested in the same schema and publish their docstrings under
> `$defs` in exactly the same way. `tests/test_extraction_schema_prompt_surface.py` pins all
> three and the whole schema by digest, so a docstring or a field-description edit is a red test
> rather than a silent change to what a model is told.

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

**Measured** (`tools/l1_design_payload_probe.py`, at this base, over **232 documents spanning
80 distinct registrations** — the first three `validated` documents of every registration in
the run of record, PLUS the first three of every registration that claims documents and holds
no validated one at all. The extension matters: on those 9 registrations' documents
`report_to_dict` takes its OTHER branches — `ending_balance` nulled (`serialization.py`
:146-151) and the ADB block emptied by `_metrics_dict` (:102-133) — and a byte-identity claim
that never exercised them would be a claim about the happy path. Each document is analysed ONCE
and serialised seven ways from the same in-memory `Report`, so nothing in the comparison can
move except the shape under test):

| variant | payload byte-identical | payload differs | document outcome unchanged |
|---|---:|---:|---:|
| **`wrapper_conditional`** — RULE S | **232** | **0** | 232 |
| `wrapper_unconditional` — `accounts` + `document` on every document | 0 | **232** | 232 |
| `omission_field_always` — the omission record as a plain `Statement` field | 0 | **232** | 232 |
| **`omission_field_elided`** — the same field, elided when empty | **232** | **0** | 232 |
| `integrity_split_order_preserved` — the scope split, re-assembled in PUBLISHED order | **232** | **0** | 232 |
| `integrity_split_naive_order` — the scope split, the two scopes concatenated | **232** | **0** | 232 |
| `integrity_split_dropped` — the scope split read literally: the document-scope flags LEAVE the account payload | 229 | **3** | 229 |

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

**And the last three rows are the risk RULE S is offered against, which RULE S does not
address.** Byte-identity here is a property of the SERIALISER, and it is close to a tautology at
that seam: the probe compares `report_to_dict(report)` with a wrapper that, under RULE S,
returns `report_to_dict(doc.accounts[0])` where `doc.accounts[0] is report`. What the 232 proves
is that the serialiser is deterministic over one object — worth knowing, and not what "state
how that is guaranteed and PROVED" asks for. The risk lives one layer up, in the
`assess_document_integrity` scope split §5 prescribes (`pipeline.py`:260-512), where
`missing_declared_statement_page` (:481), `parser_ambiguous` / `parser_exception` (:346, :353),
`repair_exception` (:389) and `integrity_check_exception` (:400) move to the document block
while the reconciliation, coverage and count flags (:289-343) and all of `assess_quality`
(:179-240) stay per account. On a single-account document those flags must land in exactly the
payload keys they land in today — a property of the PIPELINE change, not of the serialiser — and
the three variants measure the three ways an implementer assembles it:

* **`integrity_split_order_preserved`** — split by scope, re-assemble in PUBLISHED order:
  **232 / 232 byte-identical.** This is the rule S1 must implement.
* **`integrity_split_naive_order`** — the two scopes concatenated, document-scope leading:
  **232 / 232 identical here too**, because no document in this cohort carries flags of both
  scopes in an order the concatenation would change. That is a fact about the cohort and not
  about the rule: `corpus_gate.py`:1360-1362 pins the flag tuple in *"Published ORDER, not
  sorted"*, so the assembly is one document away from moving a pinned tuple, and S1 must
  preserve order because the order is pinned — not because this cohort caught it.
* **`integrity_split_dropped`** — the design's own prose read literally, the document-scope
  flags LEAVING the account payload: **3 of 232 documents move.** Those 3 are the cohort's
  document-scope carriers, and they are the measured size of the mistake the prose invites.

**S1's proof plan therefore names the pipeline seam and the integrity split as what it is
proving**, and its byte comparison runs over a tree that actually carries them — not over the
serialiser alone.

### 1.3 A blind spot in the proof instrument every coverage cell reports under

`tools/cohort_replay.py` reports `payload identical` from a LEAF projection (`flatten`,
`leaf_diff`), and **an empty list contributes no leaf**. A change that adds a key whose value
is `[]` therefore moves the payload BYTES while the projection every coverage cell reports
under sees nothing at all. Measured on the same pairs:

| variant | byte-identical | leaf-projection identical | the gap |
|---|---:|---:|---:|
| `wrapper_conditional` | 232 | 232 | 0 |
| `wrapper_unconditional` | 0 | 0 | 0 |
| **`omission_field_always`** | **0** | **232** | **232** |
| `omission_field_elided` | 232 | 232 | 0 |
| `integrity_split_order_preserved` | 232 | 232 | 0 |
| `integrity_split_naive_order` | 232 | 232 | 0 |
| `integrity_split_dropped` | 229 | 229 | 0 |

The third row is the finding, and it is total: **on all 232 documents the byte comparison says
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
| `telemetry/diagnostics.py::diagnose` — called by `build_record`:417, so it rides in EVERY discovery telemetry record | 0 codes, `evaluated=False` | **0 codes, `evaluated=True`** — an empty diagnosis that says it evaluated | 0 codes, `evaluated=False` |
| `telemetry/stated_counts.py::evaluate` | 27 transactions, `semantics_incomparable` | **0 transactions, `check_unavailable/statement_absent`** | 27 transactions, `semantics_incomparable` |
| `analysis/revenue.py::rebuild_serialized_revenue_views` | rebuilt over 27 transactions | **rebuilt over 0 transactions** | rebuilt over 27 transactions |
| `webapp/app.py::_analysis_rows` (CSV / XLSX export) | 211 export rows | **0 export rows** | 211 export rows |
| `webapp/app.py::_adb_rows` (ADB export) | 0 ADB rows | 0 ADB rows | 0 ADB rows |
| `webapp/app.py::_masked` (the `/analysis` route) | 9 top-level keys | **2 top-level keys** | 9 top-level keys |
| `benchmark/ourside.py::OurFileResult.statement/.metrics/.reconciliation` | 23 / 91 / 22 keys | **0 / 0 / 0 keys** | 23 / 91 / 22 keys |
| `balance_forensic_audit.py`:528-529 — indexes `payload["statement"]` rather than `.get()`s it | opening and ending present | **RAISES `KeyError`** | opening and ending present |
| `corpus_gate.py::production_verdict` → `_Verdict` | `_Verdict('validated', flags 0, 'clear')` | **`_Verdict('withheld', flags 0, '')`** — which mismatches `PUBLISHED_OUTCOME` and turns the gate red | `_Verdict('validated', flags 0, 'clear')` |
| *(this design)* `classify_document`, for contrast — it is taught the shape | `validated/approved` | `validated/approved` | `validated/approved` |

| measure | value |
|---|---:|
| payload readers probed (excluding this design's own) | **10** |
| ... that REFUSE the document shape (loud, fail-closed) | **1** |
| ... that ANSWER a shape they were not taught (quiet, wrong) | **9** |
| ... that refuse the Option-D shim | **0** |

Two findings, and both are load-bearing:

1. **The untaught failure is quiet, not loud.** `telemetry/record.py::classify_outcome`
   (:349-351) reads `payload.get("metrics") or {}` and returns `("withheld", "withheld_adb")`
   for a payload that has no top-level `metrics` — so a perfectly valid three-account document
   would be filed WITHHELD with a reason that names a check nobody ran (measured above: a
   `validated/approved` document becomes `withheld/withheld_adb` under the document shape).
   `analysis/revenue.py::rebuild_serialized_revenue_views` (:55-56) does
   `analysis.setdefault("statement", {})` and rebuilds every revenue view over an empty ledger.
   `telemetry/diagnostics.py::diagnose` returns an empty diagnosis marked `evaluated=True` and
   rides in every discovery telemetry record. **9 of the 10 answer; 1 raises.** The one that
   raises (`balance_forensic_audit.py`:528-529) does so only because it INDEXES the key where
   the others `.get()` it — the loudness is an accident of style, not a guard.
   **Therefore: no document may publish two accounts until every payload reader on the list
   below has been taught the shape.** That is the ordering constraint §7 is built around, and it
   is a correction to the delivery order the card sketched.
2. **The Option-D shim is refused on evidence.** Under the shim every untaught reader answers,
   and answers about one account of several, silently, on every surface, forever. The shim is
   exactly what makes the defect invisible.

The design therefore adds a **shape assertion** (L1-C16): a payload carrying `accounts` may
never also carry `statement`, and every reader taught the shape raises `ValueError` on a
payload carrying neither. The assertion is what converts the quiet failure above into a loud
one for every reader written after this design.

**The census, and why it is a list rather than a quantifier.** The first version of this table
measured six readers, and the design then stated its ordering constraint over "every payload
reader" — a universal quantifier over an unstated set, which is not a criterion a stage can be
held to. The set is now enumerated and CHECKED: eleven readers above, and nine production seams
below. `tools/l1_design_reader_probe.py --census` compares the declared seam list against the
tree in BOTH directions and **exits non-zero** if a declared seam has moved or an undeclared one
appears; a list that cannot fail is not an exit criterion. Measured at this base: 9 found, 0
undeclared, 0 missing — **the census holds**.

| seam: `analyze_markdown` → `report_to_dict` | what it feeds |
|---|---|
| `discovery/runner.py`:452 | the discovery run |
| `corpus_gate.py`:1355 | `production_verdict` — the pinned corpus |
| `benchmark/ourside.py`:99 | the benchmark's production side |
| `batch.py`:181 | the batch CLI |
| `balance_forensic_audit.py`:516 | the balance forensic audit |
| `webapp/artifact_cache.py`:215 | the analysis cache — every web upload |
| `analyze.py`:175 | **the CLI** |
| `webapp/worker.py`:29 | the web worker |
| `adb_forensic_audit.py`:493 | the ADB forensic audit |

Each must move to the document entry point, or a multi-account document publishes ONE account
through the old seam. Four of the nine — the CLI, the worker, the ADB forensic audit and the
cache — were absent from §5 in the first version, and the cache is the one every web upload goes
through.

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
`classify_outcome` exactly on 232 of 232 documents in the cohort,
including under the document shape.

**Movement this creates.** A document whose account A validates and whose account B withholds
would be `withheld` at the document level under this fold. Today it is not on the ladder at
all in that way: the reader refuses it outright, no registration claims it, and it lands
`failed`. Such a move is a ladder IMPROVEMENT and counts as "other ladder movement", never as
newly validated. **Ruling needed** (§8, Q1): whether such a document should publish account A's
figures at all, or refuse until every account validates.

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
| satisfy the yield-only arithmetic (see the disclosure below) | **0** |
| POSTED a dated row and declare nothing | **30** |
| empty and silent — no declaration of any kind | 62 |
| declare idle in some other wording | 7 |

| the Stage-1 question | documents |
|---|---:|
| **EVERY sibling satisfies the ratified rule** | **0** |
| carry a sibling that POSTED and declares nothing (the L-1 defect itself) | **26** |
| no sibling section LOCATED at all — which is not "no sibling" | 16 |

**The yield-only row carries a disclosure, and the design's first version dropped it.**
`tools/l1_split_prototype.py::classify_sibling` calls `_yield_only(rows, opening, closing,
None)` — the THREE-condition relaxed form. The fourth ratified condition (`symitar.py`:339-345,
the platform's six-figure equation row accounting for every skipped posting with its deposit
column at zero) is an artefact of one platform's layout that a generic probe does not read, so
it is not applied. The direction is safe and is why the 0 stands: a RELAXED test that admits
nothing proves the strict test admits nothing. But "as written" was the wrong phrase for a
predicate running in its relaxed form, and a future non-zero here would have to supply that row
before it could be trusted.

**The population that needs no ruling is zero documents.** Under R-a as written, an
empty-and-silent section — a heading printed, no rows, no declaration — is *absence of parsed
activity* and may NOT be omitted. That reading is what makes the demonstrated population 2
rather than 8, and §8 Q3 is where it is put to Gustavo.

**What the paper actually prints on those sections, measured** — the fact the ruling turns on,
and one the packet computed and dropped. `tools/l1_split_prototype.py` records where every
section's opening and closing came from (`section` = the section's own printed caption,
`rollup` = the enumerating table's row under L1-C5) and emits that provenance only for
non-empty walks, so for a trivially idle section it is lost.
`tools/l1_design_idle_evidence.py` re-runs that instrument's own `run_document` and reports the
two fields it already produced:

| the 21 trivially idle sections in the whole population | sections |
|---|---:|
| opening AND closing both read from the SECTION's own printed captions | **21** |
| either figure read from the enumerating table instead | **0** |
| also printing a dated row somewhere in the section | 3 |
| also printing a dated row in its LEDGER region | **0** |
| also printing their own counts or totals | **7** |

| the 6 sections the ruling would license (on 6 documents; the other 2 of the 8 close already) | sections |
|---|---:|
| opening AND closing both read from the SECTION's own printed captions | **6** |
| printing a dated row anywhere, or counts, or totals, or a daily table | **0** |

The 7 that print their own counts or totals are among the OTHER 15; on the six the ruling would
license the figure is 0, which is why nothing downstream moves — but the population's other
sections are described completely now rather than by the rows that suited the argument.

So the evidence on those six is not silence and not a missing table row. **The section prints
its own opening caption and its own closing caption and the two figures coincide** — a printed
statement by the paper about that account. Whether that satisfies R-a's "explicit statement
structure establishes the sibling AND its empty state" is a ruling; what it is NOT is "absence
of parsed activity alone", because the paper printed two figures and they agree.

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
amendment is a one-line doctrine clarification, not a policy change.

**And R-c has a leak the payload rule does not close.** §8 Q5 proposes that each account enters
a PACKAGE as its own member. `webapp/app.py`:1152-1164 then publishes
`package_average_daily_balance` as the days-weighted mean of its members' ADBs — so a package
holding exactly one multi-account document publishes **one figure averaged over that document's
accounts**, which is a document-level combined ADB by another name. §6.5's gate assertion cannot
see it: that assertion forbids a document-level FIELD, and this is a package field computed
from per-account ones. Three consequences, and the design takes all three:

* the gate assertion is widened (§6.5) so it is a property of the ARITHMETIC and not of a field
  name: **no published average may be computed over two accounts of the same document.** The
  package ADB's member set is checked for two members sharing a `content_sha256`, and the check
  is red if it finds any;
* **a package member is an account whose OWN outcome is `validated`** — see Q1. Today
  `_package_analysis` gates a member on `ready = job.status == "done" and job.analysis is not
  None` (:661) and never on `classify_outcome`, so "publish it and mark the document `withheld`"
  would silently mean "aggregate it anyway";
* Q5 must be ruled explicitly and is restated to ask it (§8).

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
| **... under the STRICTER test as well** | **0** |
| ... whose table's own CLOSING column reproduces every section's closing | **2** |
| documents where every section either closes or is trivially idle (i.e. under the ruling of §8 Q3) | **8** |
| ... with the table's closing column reproducing over the sections that would be PUBLISHED | **8** |

**The 0 is on the line after the 2 in the instrument's own output, and it belongs here.** The
strict test asks that a section print nothing dated AFTER its chain reached the closing, and at
document level no document passes it. The design carries 2 as the headline for the reason the
instrument gives for itself (`l1_split_prototype.py`:528-537): a section's span runs to the next
section heading, so the LAST section of a document runs to the end of the document and carries
its trailing tables, and the dated-row pattern cannot tell a trailing fee table from a truncated
ledger. That is a good reason to prefer 2 and a bad reason to omit 0. **The honest range this
evidence supports is 0 to 8** — 0 if the strict bound is taken at face value, 2 under the
production checks that were designed for exactly this furniture
(`posting_dates_cover_source`, plus the sections' own printed counts), 8 if §8 Q3 is granted.
Every count in §7 says which test it is measured under.

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

### 2.7 What the platform skips TODAY, and what those sections print — Q8, answered

The design's first version bounded this population with each module's own section-mark pattern
and said, correctly, that a mark count cannot tell a dropped section from a reprinted heading:
*"no instrument outside the reader itself can tell those apart."* The answer to that is to
instrument the reader itself, and `tools/l1_design_skip_probe.py` does. It runs each reader over
its own `validated` documents through `analyze_markdown(parse_mode="deterministic")` — the
production dispatch path — and watches the skip execute, with each watched line verified against
the source text it must sit on before any document is read.

| registration | `validated` documents read | documents where a skip FIRES | sections skipped |
|---|---:|---:|---:|
| `symitar` | 7 | **4** | 7 |
| `community_section` | 59 | **5** | 6 |
| `dakota_west` | 3 | **2** | 2 |
| `mission_valley` | 36 | 0 | 0 |
| `zions` | 12 | **1** | 1 |
| **total** | **117** | **12** | **16** |

| skip site | sections |
|---|---:|
| `symitar.py`:419-420 `if not rows: continue` | 7 |
| `community_section.py`:621-622 `if not txns: return None`, inside `_parse_sectioned_statement` | 8 |
| `community_section.py`:984, the `stmt.transactions` clause at the CALL SITE | **0** |
| `zions.py`:248-250 `_inert` — no row AND every printed summary column zero | 1 |

**And what the paper printed on each of those 16 sections**, classified only by a module's own
committed pattern or helper (`symitar._DORMANT_RE`, `zions._NO_ACTIVITY_RE`,
`community_section._summary`, which is fail-closed by its own docstring):

| evidence class | sections |
|---|---:|
| `printed_dormancy_declaration` — the section prints a no-activity declaration | **8** (7 `symitar`, 1 `zions`) |
| `printed_zero_activity_summary` — its own opening, its own closing coinciding to the cent, zero credit total, zero debit total, zero credit count, zero debit count | **8** (6 `community_section`, 2 `dakota_west`) |
| ... each of those seven clauses, satisfied | **8 of 8**, every clause |
| **`no_printed_evidence` — the class R-a refuses** | **0** |

> **Q8 is answered by measurement: applying R-a to the existing skips removes 0 validated
> documents.** The exposure the design warned about does not exist. What exists is 12 documents
> whose skip must be RE-FOUNDED on the evidence already printed, and 16 sections that must
> become visible in the payload — and a vocabulary (L1-C17) that has to be able to name that
> evidence, which the first version's could not.

**`zions` is in this table because it was in no instrument before.** The design named it an S2
skip site and never probed it. Its skip is not absence-based at all: `_inert` (`zions.py`
:248-250) requires `not rows` **and** every printed summary column to be `0.0`, which is the
`printed_zero_activity_summary` class arriving through a different reader; and `_NO_ACTIVITY_RE`
(`zions.py`:78, live at :200) is a printed dormancy declaration in a wording symitar's pattern
does not read. Both are printed grounds, neither was nameable by L1-C17's first vocabulary, and
`zions` carries 12 protected documents.

**Two corrections this probe made to itself, both caught by running it.** They are recorded
because a probe that once over-counted has to carry the reason it no longer does.

* `analysis/parser_registry.py::resolve` (:998-1024) calls `parse` on EVERY candidate
  registration, and three of these registrations route into the same module function. Counting
  line hits without asking whose parse attempt they belong to attributed losing candidates'
  drops to the winner — 71 sections where the claiming parser drops 6. Only skips inside the
  CLAIMING registration's own entry point are counted.
* `community_section.py`:984 is an `if`, not a skip: counting its executions counts blocks
  (65), and counting `stmt is None` counts blocks already recorded at `:622` a second time. Its
  own contribution is the second operand alone — a statement that parsed and carries no
  transaction — and that is **0**.

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

> **A movement is INTERNAL when, and only when, ALL FOUR hold:** a movement in a SIBLING account
> published on the SAME document has the same posting date, the same magnitude to the cent and
> the opposite sign; that pairing is one-to-one, checked DOCUMENT-WIDE; the counterpart is
> unique (a posting with two or more admissible counterparts pairs with none — §3.3); **and the
> paper PRINTS an INTERNAL-MOVEMENT designation on at least one of the two legs** - a printed
> row naming one of the member's OWN accounts as the source or the destination.
> An arithmetic coincidence alone never sets INTERNAL, and neither does a payment rail.

**The fourth clause is new, and it is the one that matters.** The first version said "where the
paper prints one on neither, the arithmetic signature stands alone" — so a member who deposits a
sum into checking on the day they withdraw the same sum from savings for an unrelated purpose
produced a unique, unambiguous, entirely non-internal pair; §3.2 flagged it; and §3.2's own
consequence then removed that deposit from package gross deposits, deposit counts, revenue and
the withholding denominator. That is money the paper printed, deleted from a funder's view of
the business by an inference — the same class of error the repair doctrine forbids, pointing the
other way. R-d says transfers are "identified as INTERNAL"; it does not license identifying them
from a coincidence.

**Which vocabulary decides it, and why only one of them can.** The designation is read by
`analysis/transaction_classifier.py`'s **`_INTERNAL_TRANSFER_CREDIT_PATTERNS` alone**
(:433-465, 13 patterns): `TRANSFER FROM <CHECKING|SAVINGS|SHARE|...>`, `SH TO SH`,
`ACCOUNT TO ACCOUNT`, `TRANSFER FROM <masked account> TO <masked account>`. Every member of it
names one member's OWN accounts as the source or the destination.

> **A peer-to-peer rail vocabulary can never be transfer evidence for this clause.**

The module's other tuple, `_TRANSFER_PATTERNS` (:300-308), is **refused**, and the reason is not
a preference. It has exactly one use in production - at :976-981, to build a
`strong_non_lender_exclusion` whose own reason string says the descriptor identifies "an
account, online, or **person-to-person** transfer" - so it answers "this row is not a lender
debit", never "this row is an internal movement". It contains `ZELLE`, `VENMO`, `CASH APP`,
`E TRANSFER`, `ETRANSFER` and `XFER`; the first three are third-party rails by definition, and
an Interac e-Transfer on the Canadian issuers in this archive is ordinarily a payment from
someone else. A payment to or from another PERSON is not evidence that money moved inside one
member's ledger set, and admitting it flags the pair INTERNAL and then removes the matching
printed deposit from package gross deposits, deposit counts, revenue and the withholding
denominator - **the exact failure this clause was added to prevent, re-admitted through the
vocabulary it was founded on.**

**What the clause costs, measured** (`tools/l1_design_transfer_probe.py`, same population, same
reconstruction, the designation decided by that single committed vocabulary — 13 internal-transfer credit patterns and 7 transfer patterns; this instrument
writes no transfer grammar):

| population | pairs | with a PRINTED internal designation on either leg |
|---|---:|---:|
| the published greedy rule | 47 | **43**, on **5** documents |
| the unique-counterpart rule | 47 | **43** |

| which vocabulary admitted the pair | pairs |
|---|---:|
| the INTERNAL vocabulary alone | **41** |
| both | 2 |
| **the GENERIC peer-to-peer vocabulary alone - REFUSED** | **3** |
| **neither - nothing printed at all** | **1** |

**Four pairs of 47 are refused, not one.** Three are admitted only by the peer-to-peer
vocabulary - all three by one pattern, on one document - and one prints nothing at all. The
first version of this design counted 46 designated because it ORed the two vocabularies, and
that number is WITHDRAWN. Under the corrected rule none of the four is flagged, and the document
refuses package aggregation for that pair rather than having a printed deposit removed on an
inference.

| how many legs carry the designation | pairs |
|---|---:|
| **ONE leg only** | **42** |
| both legs | 1 |

**"At least one of the two legs" is load-bearing, not a formality**: it decides 42 of the 43 on
the words of a single printed row. That is also why the choice of vocabulary matters as much as
it does - on 42 pairs there is no second row to contradict a wrong reading.

**And the two pairing defects the first version's killer population carried**, both re-measured:

| rule | pairs | documents |
|---|---:|---:|
| greedy — first admissible counterpart, `taken` re-initialised per ledger pair (the published 47) | 47 | 7 |
| document-wide one-to-one — one `taken` for the whole document | **47** | 7 |
| unique counterpart — §3.3's own fail-closed rule, mutual and document-wide | **47** | 7 |

The three agree. `_transfer_pairs` (`l1_split_prototype.py`:861-888) takes the FIRST admissible
counterpart and breaks, which is the opposite of §3.3, and it re-initialises `taken` per ledger
pair, so on a document with three or more live ledgers one posting can be counted twice —
**3 documents reconstruct three or more live ledgers**, so the defect is reachable. Both are
real defects in that instrument and **neither bites on this archive**: postings with two or more
admissible counterparts number **0**, so the greedy choice never chooses and the document-wide
match never differs. The 47 is therefore usable as a killer population, which the design could
not claim before and can now.

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
worse than refusing the package. Measured: **0** postings in this population have two or more
admissible counterparts, so the ambiguity branch is unexercised by the archive and its killer
must be a constructed fixture rather than a sha. **Ruling needed** (§8, Q2): whether ambiguity
refuses only the aggregation (this design's proposal) or the whole document.

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
| **L1-C4** | every posting section is accounted for; a section with a dated ledger row may not be dropped. Omission ONLY under §2.3, and always SURFACED. **This condition's truth depends on Q7**: at the two-row threshold a section printing ONE dated row is not a posting section and C4 permits dropping it; at one row it does not. The condition is not implementable until Q7 is ruled, and it is written here at the ONE-row threshold, which is the stricter of the two | `None`, or an omission record | **26** documents carry a sibling that posted and declares nothing; **0** documents have every sibling satisfying the ratified rule |
| **L1-C5** | where a section takes its opening or closing from the enumerating table, the table must print a COLUMN CAPTION **from the closed vocabulary below**, and the role map is what says which column is which; position is never evidence | `None` | **30** of 214 documents print such a caption — `type_prev_dep_wd_end` 15, `type_begin_end` 8, `begin_end` 7 — and **184 print none**. The role map is `tools/l1_split_prototype.py`:132. Without the vocabulary the condition is not yet a predicate: a table printing an ambiguous caption satisfies the letter and is mapped by position after all. This condition's absence produced 23 false closures |
| **L1-C6** | each published section states its own opening and closing, or the table states them under C5; where both are printed they agree to the cent | `None` | **2** sections fail exactly here |
| **L1-C7** | no published section closes on an empty or partial ledger: a section printing a dated row may not publish zero transactions, and the published ledger accounts for every dated row inside the span it read | `None` | **23** sections would close vacuously without it; **11** more leave a hole inside their own span |
| **L1-C8** | `reconcile(section).ok`, with the section's own stated counts and totals supplied wherever it prints them — never `None` where they are printed | not validated (per-account outcome) | 79 of 442 sections print them; `reconcile` refuses **11 of 48** when they are fed and **0 of 105** when they are not |
| **L1-C9** | `compute_average_daily_balance(section).ok` under the ratified calendar-day doctrine, `posting_dates_cover_source` applied against the SECTION's text, the section's own printed daily balances supplied where printed | not validated (per-account outcome) | the ADB refuses **10 of 48**; **24 of 442** sections print a daily table |
| **L1-C10** | the roll-up reproduces: every published section's closing appears in that account's row under C5's roles, and where a cross-account total is printed the published sections sum to it. A mismatch refuses the DOCUMENT, not the section | `None` | **43** documents print a cross-account total *over all 214*; **37** do *over the documents with a LOCATED roll-up* (§2.2). Both reproduce and they are different denominators, not a disagreement. The table reproduces on the **2** that close |
| **L1-C11** | no money moved between the member's own accounts is counted twice, and **nothing is called INTERNAL without a printed INTERNAL-MOVEMENT designation on at least one leg** - read from a vocabulary naming the member's OWN accounts, never from a payment-rail vocabulary. An arithmetic coincidence never removes a printed deposit from a package total, and neither does a peer-to-peer rail | the pair is not flagged; the package refuses to aggregate that document | **7** documents, **47** pairs - the killer set. **43** carry a printed internal designation (on 5 documents; **42 of the 43 on ONE leg only**) and **4 do not**: 3 admitted only by the refused peer-to-peer vocabulary, on one document, and 1 with nothing printed at all. Those **4 are the condition's live killers**. **0** ambiguous postings, so the ambiguity branch's killer is a constructed fixture, named as one |
| **L1-C12** | a facility enumerated on the table is never published as a deposit section, and C10's cross-account total is neither required nor satisfiable where the total includes one. The class of a row is established from the ROW, not from a word in it | `None` for the section; C10 suspended for the document | **19** documents enumerate one; **4** of them carry two or more posting sections (all one family); **7** of the 19 also print a cross-account total. **That 19 is the COUNTED classes only** — `loan` 14, `mortgage` 5, `brand_row` 4. Three further classes fire and are deliberately not counted: `debit_card` on **15** documents (**5** multi-posting) and `card_network` on **6** (0 multi-posting), because a debit card is how a member reaches a deposit account rather than a facility of its own, and a brand word alone is not proof of an account row. The condition's real REACH is therefore wider than its counted population, which is the doctrine in the cell doing its work — and an implementation must confirm what a row IS before excluding it |
| **L1-C13** | one currency per section, established at SECTION level by the doctrine's hierarchy; a document printing two denominated columns refuses | `None` | **4** documents, one census group, **12** sections |
| **L1-C14** | no statement-specific constant anywhere in the split: an account number, a product name or a memorised heading is R-1 | test failure (`tests/test_no_statement_hardcodes.py`) | `analysis/consumers.py`:88-94 today (§9, F3) |
| **L1-C15** | zero inference — deterministic, $0, no model call | — | standing |
| **L1-C16** | *(new)* a payload carrying `accounts` never also carries `statement`; a reader given a payload with neither raises `ValueError` | `ValueError` at the reader | measured: **6 of 6** probed readers ANSWER the untaught shape today instead of refusing it (§1.4) |
| **L1-C17** | *(new)* an omission's `reason` is from a CLOSED vocabulary, every member of which names PRINTED evidence — see the vocabulary below. **`absence_of_parsed_rows` is not a member and cannot become one**, and the vocabulary is closed against ABSENCE, never against evidence: a class the archive prints and this list cannot name is a defect in the list | `None` — the document may not publish | §2.7: the skips production performs today fire on 16 sections and **16 of 16 print evidence in this vocabulary; 0 print none**. §2.3: the Q3 member's population is 6 sections on 6 documents |
| **L1-C18** | *(new)* no reader, and no SURFACE, selects one account to stand for a document — not by a derived quantity (most transactions, largest balance) and not by printed position (the first account). A per-document field that can hold only one account's value is left EMPTY on a multi-account document; it is never filled from a chosen account (R-e) | `None` at a reader; an EMPTY column at a surface | §9 F4: `analysis/community_section.py`:731-734 selects the busiest section today, on a cohort that includes a pinned document. And §5's own `discovery/runner.py` row, which this condition caught |

**L1-C17's vocabulary, widened to the evidence the archive prints.** The first version admitted
three tokens, and §2.7 measures that they name NONE of what 8 of the 16 skipped sections
actually print, and nothing at all of what `zions` reads. A closed vocabulary that cannot name
printed evidence does not fail closed — it forces an implementer either to invent a token
(which C17 forbids) or to refuse 12 protected documents. The vocabulary is therefore closed
against ABSENCE and open to EVIDENCE, and its members are:

| member | what the reader must have | measured population (§2.7) |
|---|---|---:|
| `printed_dormancy_declaration` | the section prints a no-activity declaration. **Wording-independent**: `symitar._DORMANT_RE` and `zions._NO_ACTIVITY_RE` (`zions.py`:78) are two printings of one fact, and a vocabulary keyed on one issuer's phrasing is an R-1 vocabulary. A new wording is admitted by adding the pattern, never by relaxing the class | **8** (7 `symitar`, 1 `zions`) |
| `printed_zero_activity_summary` | the section prints its OWN opening balance, its OWN closing balance coinciding to the cent, a zero credit total, a zero debit total, a zero credit count and a zero debit count. All six, read fail-closed: a grid missing either balance or either count yields nothing rather than a partial answer. This is also exactly what `zions._inert` (:248-250) requires — no row AND every printed summary column zero — so that reader's skip is a member of this class rather than an exception to the list | **8** (6 `community_section`, 2 `dakota_west`); every one of the six clauses satisfied on 8 of 8 |
| `yield_only_arithmetic_with_summary_equality` | the ratified `symitar._yield_only` predicate, applied AS WRITTEN with its fourth condition | 0 sections in this population satisfy it (§2.3) |
| `printed_pair_coincides_and_no_row_printed` | **only if §8 Q3 is granted** — the section prints its own opening and closing captions, the two coincide, and it prints no dated row, no counts, no totals and no daily table | 6 sections on 6 documents |

Two rules govern the list itself. **Nothing may be added for absence** — a member must name
something the paper printed, and `absence_of_parsed_rows` is the class this condition exists to
refuse. And **a member is the EVIDENCE, not the reader**: `zions._inert` gets no token of its
own because what it reads is `printed_zero_activity_summary` arriving through a different
module, and giving each reader its own token would rebuild the per-issuer vocabulary R-1 forbids.

**Currency, at section level (L1-C13, serving R-f).** The doctrine resolves a denomination per
DOCUMENT today and `jurisdiction_default` is affirmative evidence at the INSTITUTION level. Per
section:

* `printed` and `product` evidence must be read from the SECTION's own text; a section may
  **not** inherit a sibling's `printed` evidence — that is exactly the silent denomination R-f
  forbids;
* **a DOCUMENT-level printed statement of denomination — a masthead or footer line stating the
  currency, not attached to any section — is explicit evidence and outranks BOTH defaults for
  every section that earned nothing of its own.** The first version of this rule was right about
  siblings and silent about the document, and the silence inverted R-f: a statement printing its
  denomination once and then printing two sections neither of which repeats it would have
  resolved both sections to a DEFAULT, with the printed statement outranked by an assumption.
  R-f is "explicit currency evidence outranks defaults", without qualification as to where on
  the page it is printed. The class published is the class actually earned — `printed`, because
  the page printed it — and only a section that CONTRADICTS the document-level statement
  refuses;
* the precedence is therefore, strongest first: the section's own `printed`, the section's own
  `product`, the document's own `printed`, then `jurisdiction_default`, then
  `institution_default`, then `schema_default`;
* `jurisdiction_default` and `institution_default` are document/institution facts and are
  inherited by every section that earned no stronger class of its own;
* the population of the new rung is not measured here: the two-denomination class is 4 documents
  / 12 sections, and the single-denomination document-level class is measured by nothing in this
  packet or this design. An implementation card owns measuring it before it writes the rung;
* two published sections resolving to different denominations → **ruling needed** (§8, Q4):
  R-f says "publishes two accounts or refuses", and both are consistent with the currency
  doctrine's ban on cross-currency package math. The measured population is 4 documents / 12
  sections, all one census group.

**Mutation tables.** Every condition that becomes code gets a mutant that removes it and a named
killer test, and the killers of C4/C5/C6/C7/C10/C11/C12/C13/C17 are drawn by sha from the
populations above. A test named after a gate is not a test of that gate.

**Four of the eighteen have no measured killer population, and they are in THREE different
situations.** The preamble above should not have implied all eighteen had one, and the first
closure should not have flattened the four into one class: an implementer reading "each needs a
constructed fixture" builds one thing where two are wanted and none is.

| condition | what it actually needs | who owns it |
|---|---|---|
| **L1-C15** — zero inference, deterministic, $0 | **nothing of its own.** It is a standing property already enforced by the batch rule and by the registry and experiments guards. It is not an owed fixture and should not be carried as one | — |
| **L1-C14** — no statement-specific constant | it already HAS a live killer in the canonical 255: `tests/test_no_statement_hardcodes.py`. What it lacks is a killer that catches the instance this design MEASURED (`consumers.py`:90). Its work is an **EXTENSION of an existing guard**, not a new fixture — and it is the extension S5 needs anyway | **S5** |
| **L1-C2** — disjoint sections, complete coverage | a constructed synthetic document with a DUPLICATED section | **S4** |
| **L1-C18** — no chosen account | a constructed two-account payload, with every per-document single-value field asserted EMPTY. Cheap, and it belongs where the surfaces learn the rule | **S3** |
| *(and)* **L1-C11's ambiguity branch** | a constructed synthetic posting with TWO admissible counterparts — the archive prints none (§3.3) | **S4** |

**Each fixture is a CONDITION OF CLOSING the card that writes its rule, not a backlog item.**
The card's mutation table is not accepted without it. The failure mode is named in the batch
rules already — *"a test named after a gate is not a test of that gate"* — and the way it slips
through is a card closing on the strength of the other seventeen conditions' killers.

---

## 5. Surfaces touched, file by file

`nothing` in the middle column means: byte-identical payload, unchanged behaviour, proved by
§1.2's byte comparison plus the archive sweep. Line numbers are at this base.

**One rule governs every per-document field in this table**, and the design's first version
broke it in the row it is most tempting to break: *a field that can hold one account's value is
left EMPTY on a multi-account document, never filled from a chosen account.* `account_last4` is
the column by which a person identifies a document; making it "the FIRST account's" is L1-C18's
forbidden selection wearing printed order as a disguise, and it puts the L-1 defect in the
discovery row after the design has removed it from the payload. Printed ORDER is printed
evidence about a SEQUENCE — which is why `accounts` is a list in printed order and why §1.5
breaks outcome ties by it — and it is not evidence that the first element represents the whole.
A surface that needs one value per document gets `account_count` and an empty column; a surface
that needs the values gets the account list.

| file | single-account document | multi-account document |
|---|---|---|
| `analysis/schema.py`:121-221 | nothing — `Statement` unchanged; only a COMMENT says "one account", **never the docstring, which pydantic publishes to the extraction model as the schema's `description`** (§1.1; pinned by `tests/test_extraction_schema_prompt_surface.py`) | unchanged; one instance per account |
| `analysis/pipeline.py`:153-163, :515-519 | nothing — `analyze_markdown` keeps returning one `Report` for a one-account document | new `DocumentReport` (§1.1); a document-level entry point returning it; RULE S at the seam |
| `analysis/pipeline.py`:260-512 `assess_document_integrity` | **nothing — and this is the row S1 has to PROVE, not assume** (§1.2): the account payload keeps every flag it carries today, in PUBLISHED order. Reading the split literally moves 3 of 232 cohort documents; concatenating the two scopes is one document away from moving a flag tuple `corpus_gate.py`:1360-1362 pins | split by scope: `missing_declared_statement_page` (:481), `parser_ambiguous`/`parser_exception` (:346, :353), `integrity_check_exception` (:400) and `repair_exception` (:389) are DOCUMENT facts and are ALSO carried in the document block; the reconciliation, coverage and count flags (:289-343) and all of `assess_quality` (:179-240) are per ACCOUNT |
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
| `discovery/runner.py`:119-176, :452, :654-657, :661-665 | nothing | `statement_bank` (:162) and `account_last4` (:163) are the only two Statement-derived columns. On a multi-account document **`account_last4` is EMPTY and a new `account_count` carries the fact instead** — see the note below; `statement_bank` is the document's issuer, which every published section of a member statement shares (a document whose sections disagree about the issuer refuses under L1-C3's spirit). One row per document stays, carrying the DOCUMENT outcome (§1.5). The `analyze_markdown` → `report_to_dict` seam at :452 moves to the document entry point |
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
| `webapp/artifact_cache.py`:436, **and the seam at :215-216** | nothing — not bumped by a byte-identical stage | `ANALYSIS_STAGE_VERSION` bumped in the SAME commit as any payload-shape change (:150-151, :165); the seam at :215-216 is the one EVERY web upload passes through and was unnamed in the first version |
| **`analyze.py`:175/187 — the CLI** | nothing | unnamed in the first version, while §1.1's own rationale cites the CLI as a `report_to_dict` consumer. Takes the document entry point |
| **`webapp/worker.py`:29** | nothing | unnamed in the first version. Takes the document entry point |
| **`adb_forensic_audit.py`:480/493** | nothing | unnamed in the first version. Takes the document entry point |
| `telemetry/diagnostics.py`:455-... `diagnose` | nothing | called by `build_record`:417, so it rides in every discovery telemetry record; takes the account path, or the document branch that says a document-shaped payload is not diagnosable |
| `telemetry/stated_counts.py`:390-... `evaluate` | nothing | reads `payload["statement"]`; takes the account path |
| `webapp/static/app.js`:1078-1177, :256-277 | nothing | one statement panel today; an account selector, one panel per account, and the omission note rendered |
| `benchmark/expectations.py`:23-54, :62-103 | nothing | one expected value per field per document; a multi-account document has nowhere to declare a second opening/ending/ADB. Follows the two CSVs |
| `benchmark/ourside.py`:88-113 (seam at :99), `batch.py`:87-176 (**seam at :181**, outside the range the first version cited) | nothing | one row per document today; one per account |
| `balance_forensic_audit.py`:650-700, **and the payload read at :516-529** (the seam plus the one reader on this list that RAISES on the document shape, because it indexes rather than `.get()`s) | nothing | asserts `document_{index}` package rows; follows `_package_rows` |

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

**And the subset S2 actually touches**, measured on the dispatch path rather than bounded
(§2.7) — this is the population Q8 is decided on:

| registration | `validated` (protected) | documents where a skip FIRES | sections skipped | sections with printed evidence | sections with NONE |
|---|---:|---:|---:|---:|---:|
| `symitar` | 7 | 4 | 7 | 7 | **0** |
| `community_section` | 59 | 5 | 6 | 6 | **0** |
| `dakota_west` | 3 | 2 | 2 | 2 | **0** |
| `mission_valley` | 36 | 0 | 0 | 0 | 0 |
| `zions` | 12 | 1 | 1 | 1 | **0** |
| **total** | **117** | **12** | **16** | **16** | **0** |

**R-a removes 0 validated documents.** Every skipped section on this archive prints the evidence
the condition demands; none rests on absence alone. The exposure is a vocabulary that has to
name it (L1-C17) and a payload field that has to show it (S2) — not a subtraction from 2,596.

**AMENDED 2026-08-30 — the population S2 DELIVERED is 15 documents / 19 sections.** The table
above measures the three ABSENCE-shaped sites and stays exactly as measured. What it does not
count is `symitar._yield_only` (:425), the second skip in a file S2 rewrites, which §9 F1 already
records as resting on printed evidence and on the ratified predicate — and which L1-C17's
vocabulary already names, `yield_only_arithmetic_with_summary_equality`. S2 surfaced it too
rather than leave one silent drop in a file it had just made evidence-based. Measured on the
dispatch path at the S2 tree:

| the S2 population, delivered | documents | sections |
|---|---:|---:|
| the three absence-shaped sites, as measured above | 12 | 16 |
| `symitar._yield_only`, on documents disjoint from those | **3** | **3** |
| **total** | **15** | **19** |

The three are `3600FE7830C4A484`, `9C5B7D628D7511EE` and `C067BE96F6B0BE0F`, one omitted section
each, admitted by `yield_only_arithmetic_with_summary_equality`. Movement is **0** on all three:
`validated` before and after, payload byte-identical, and the archive sweep finds no mover.
**S3 prices 15 protected-and-pinned carriers, not 12 — and it prices them as documents that
KEEP their account `validated`.** Gustavo's Q10 ruling (2026-08-30, `BATCH9_TRANSITION.md`
§8.7) supersedes §1.5's omission override: an explicit sibling omission beside an
independently valid account does not demote it. What S3 wires for these 15 is the SURFACE —
`sibling_account_omission_detected: true` and `completeness: partial` at the document /
package layer — not a fold. See the dated note in §7.

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
and it moves in stage S5 — but it does not move alone, and the movement is not a disjunction:

| sha16 | registration | pinned? | today | after S5 | evidence |
|---|---|---|---|---|---|
| `05E246C0ED6678E6` | `consumers` | **yes** | `validated`, published from a memorised product-name + account-number slice (`consumers.py`:90) | **`failed`** | see below |
| the second `consumers` document | `consumers` | no | `validated`, same slice | **`failed`** | the same argument; §6.2 measures that `consumers` claims exactly 2 documents in the run and both are `validated` |

**Why `failed` and not "either published or refused".** The design's first version stated this
as a disjunction, which is not a movement. Two measurements in this document decide it:

* `_primary_checking_section` (`consumers.py`:88-94) finds its start ONLY at the memorised
  literal; `parse_consumers_statement`:111-112 returns `None` when the slice is empty. So
  removing the literal — which is the whole point of the card — makes the reader refuse unless
  a printed partition replaces it;
* §7's S5 row measures that the `DECL-L1-CANDIDATE` band closes **0** of its 16 multi-posting
  documents today. On today's evidence the printed partition does not close, so the branch taken
  is REFUSED, and it is taken for **both** documents or neither: one literal is what makes the
  reader return anything at all.

This is a `validated → failed` on two protected shas, one of them pinned. BATCH9-RULES makes
that a STOP-and-report requiring explicit per-sha evidence that the batch-8 validation was
itself incorrect — **and the evidence is exactly what F3 states**: the published ledger today is
one memorised account of a member with several, and the document's own summary caption says so.
The ceremony must approve that argument, and the audit CSVs must be re-derived for **both**
paths, before the card is cut.

Every other pinned document is expected to be **byte-identical**, and that expectation is the
gate: a pinned mover outside this table is a STOP-and-report.

**One more pinned exposure, named because §6.2 measures it.** `dakota_west` claims **3**
documents and holds **1** pinned one. Of the three, **2** carry the S2 skip (§2.7) and **1** is
the document on which F4's derived selection actually chooses among two or more candidate
sections. So every `dakota_west` document is inside S2's or S5's blast radius, and "no pinned
movement expected" for S2 is not established until the implementation card names which of the
three the pinned one is and what happens to it.

### 6.4 Per stage

Every stage owes, at its closure tree, in this order:

1. `cohort_replay --expect-identical` at BASE over its target cohort and over the baseline
   cohort of every registration of every module it touched (fidelity: exit 0);
2. the same at the closure tree — `newly validated | other ladder movement | previously
   validated preserved (payload identical / changed, with leaf PATHS) | validated regressions
   (BLOCKING, exit 2)`;
3. **a BYTE comparison alongside it** (§1.3) — `cohort_replay`'s leaf projection cannot see an
   added empty-list key, and this design's payload-shape stages add exactly that class of key.
   **This survives the fix.** Ocean's `train9` change to `flatten` — "an EMPTY container is a
   leaf too" — closes the empty-container half of the gap, and a stage should rebase onto it.
   Two things follow and both belong in a stage's plan. First, the fix is BROAD: the baseline
   payloads already carry thousands of empty containers, so the projection now compares leaves
   it did not before, and **every cell's `--expect-identical` fidelity control must be
   re-established at `train9` `7755665` or later before it is used as a control** — a fidelity
   run from before the fix is not a control for a tree after it. Second, the gap is narrowed and
   not closed: `flatten` still compares an all-scalar list as a sorted multiset, deliberately,
   so a payload whose scalar-list ORDER changes still moves bytes and no leaves. The byte
   comparison stays;
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
* **and no published average is computed over two accounts of one document** — the arithmetic,
  not the field name. The package ADB's member set is checked for two members sharing a
  `content_sha256`. Without this the R-c assertion above is satisfiable by a package that
  averages a document's three accounts and calls the result a package figure (§2.5);
* a package member's own outcome is `validated`, asserted at the member set rather than
  inferred from the document's;
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
| **S1 — the wrapper and RULE S** | `analysis/pipeline.py` (the three dataclasses + the document seam), `analysis/serialization.py` (`document_report_to_dict`, RULE S), a COMMENT in `analysis/schema.py` — **never its docstring, which is a model prompt** (§1.1) | **0 newly validated. 0 documents move.** `accounts` is length 1 on every document by construction; RULE S returns today's dict verbatim — measured byte-identical on **232 of 232** documents across **80** registrations, including the 9 that hold no validated document and whose payloads take the nulled-balance and emptied-ADB branches | **none** | **The proof is of the PIPELINE SEAM and the `assess_document_integrity` scope split, not of the serialiser** (§1.2): the byte comparison runs over a tree that carries both, and the split is re-assembled in PUBLISHED order — the literal reading of the prose moves 3 of 232, and the concatenated assembly is one document away from moving a tuple the corpus gate pins. Plus `cohort_replay --expect-identical` over every registration + archive sweep (0 findings expected, and 0 is the pass condition). `ANALYSIS_STAGE_VERSION` NOT bumped |
| **S2 — SIBLING-OMISSION-SURFACE** | `analysis/pipeline.py` (`SiblingOmission`, the integrity note); the skip SITES only — **`analysis/symitar.py`:419-420, `analysis/community_section.py`:621-622 (INSIDE `_parse_sectioned_statement`, not at its call site), `analysis/zions.py`:248-250** | **0 newly validated, and 0 validated LOST.** Measured on the dispatch path (§2.7): the skips fire on **12** validated documents / **16** sections across 117 read, and **16 of 16 print evidence L1-C17 can name — 0 print none**. So this stage re-founds 12 documents' skips on printed evidence and surfaces 16 sections; it removes nothing. Payload bytes move on those 12 documents and on no others | **1 named exposure, not "none".** `dakota_west` holds a pinned document and has 3 documents in the run: 2 carry this skip and the third carries F4's live derived selection (§6.3). The card must name which is pinned before it claims no pinned movement | mutation table on the omission-reason vocabulary, with killers drawn by sha from the 12; `cohort_replay --parser` for symitar / community_section ×3 / zions; BYTE comparison; archive sweep with every mover named by sha. `ANALYSIS_STAGE_VERSION` bumped (payload bytes move on the named documents) |
| **S3 — the surfaces, taught DARK** | the **11 readers** and the **9 seams** of §1.4, by name: `telemetry/record.py`, `telemetry/diagnostics.py`, `telemetry/stated_counts.py`, `analysis/revenue.py`, `analysis/count_semantics.py`, `corpus_gate.py`, `discovery/runner.py`, `discovery/report.py`, `webapp/app.py`, `webapp/jobs.py`, `webapp/artifact_cache.py`, `webapp/worker.py`, `webapp/static/app.js`, `benchmark/expectations.py`, `benchmark/ourside.py`, `batch.py`, `analyze.py`, `balance_forensic_audit.py`, `adb_forensic_audit.py` | **0 newly validated. 0 documents move** — production emits no multi-account payload at this tree, so every branch added here is unreachable in production and exercised only by unit tests and a gate fixture | **none** | **Exit criterion, checkable:** every one of the 11 readers has a document branch with a unit test over a synthetic document payload, AND `l1_design_reader_probe --census` exits 0 (the 9 seams are the tree's, both ways), AND each of the 9 seams calls the document entry point. Plus: the shape assertion (L1-C16) with a mutation table; `cohort_replay --expect-identical` over EVERY registration; BYTE comparison; archive sweep 0 findings. `TELEMETRY_VERSION` bumped |
| **S4 — the first publisher + transfers** | a new shared CU member-statement template module (the `rollup-oracle` mechanism), its registration, `analysis/pipeline.py` (transfer identification), `webapp/app.py` (`_package_analysis` exclusions) | **0 to 8, and the test decides which.** **0** documents pass the STRICT after-chain bound; **2** close on every located section under the production checks (both one census group, both with the enumerating table's own closing column reproducing); **8** if §8 Q3 is granted (a section that prints its own opening and closing captions with the two figures coinciding, and prints no dated row, may be OMITTED rather than counted) — all eight the same family, all eight with the table reproducing over the sections that would be published, and all six of the omitted sections measured to take both figures from their own printed captions (§2.3). Beyond that family the reachable set depends on per-family row grammars and a better boundary layer, and this design declines to put a number on it | **none** | mutation tables for L1-C1…C13; the **47 pairs on 7 documents** as the killer set - the **43** designated (on 5 documents) for the package exclusion, and the **4** refused for the printed-evidence clause: 3 that only a peer-to-peer vocabulary would admit, and 1 with nothing printed; `cohort_replay --group` per census group claimed; the whole-archive sweep; corpus gate's new per-account assertions lit |
| **S5 — CONS-HARDCODE** | `analysis/consumers.py` (:88-94, and :115-123, which restates the product designation but NOT the account number) | **0 newly validated, and −2 validated.** The `DECL-L1-CANDIDATE` band closes **0** of 16 multi-posting documents today, and removing the literal makes the reader refuse (§6.3). This is a CORRECTNESS card whose measured effect on the count is negative: it removes an R-1 hardcode that publishes one memorised account of a member's several | **2 validated → failed, 1 of them pinned** (§6.3). STOP-and-report with per-sha evidence, and the ceremony, BEFORE the change lands | truth-set ceremony over BOTH paths; `cohort_replay --parser consumers` (2 documents, both `validated`); corpus gate; both audit CSVs' rows re-derived and re-approved |
| **S6 — the remaining mechanisms** | per-family row grammars on the shared template | **an ESTIMATE, and it is not offered.** What is measured: 29 of 392 sections close today; `section-identity` closes 10 sections and 0 documents; `section-equation-scan` closes 0 and always will (L1-C1) | unknown; each family carded separately | as S4, per family |

**NOTE 2026-08-30 — S2's population is 15 / 19, and who decided that.** The S2 row above says
"12 validated documents / 16 sections" and "payload bytes move on those 12 documents and on no
others". The card as delivered surfaces **15 documents / 19 sections**: the three absence-shaped
sites the row names, plus `symitar._yield_only` on three further documents (§6.2, amended). The
widening was proposed by the implementation cell on the authority of the symitar module's own
docstring ("SIBLING-OMISSION-SURFACE … owns both together"), was measured at **0 movement** — 0
newly validated, 0 validated lost, 117 of 117 payloads byte-identical, 0 archive movers over
3,380 — was adjudicated legitimate rather than absence-shaped by the independent review of
`wave9-l1s2` (`reviews/BATCH9_L1S2_REVIEW.md` §2, MAJOR-1), and was **accepted by Ocean**.
It was NOT a decision of this design cell, and it is recorded here so S3 prices the right number:
**15** protected batch-8 shas carry a surfaced omission, not 12.

**And it prices them the way Gustavo ruled.** When this note was first written the consequence
was open and it said so. It is open no longer: **Q10 (2026-08-30, `BATCH9_TRANSITION.md` §8.7)**
supersedes §1.5's omission override — see the annotation there — and the 15 do **NOT** fold to
`review`. Each keeps its account `validated`, having on its own unambiguous boundaries, a
correct reconstruction, the unchanged validator's verdict and nothing misattributed from the
omitted sibling; the omission is surfaced beside it at the document / package layer
(`sibling_account_omission_detected: true`, `completeness: partial`). Fail-closed is unchanged:
an omission that makes the boundaries ambiguous or prevents independent validation refuses the
document. S3's obligation on these 15 is therefore to WIRE THE SURFACE and to leave the account
outcome alone, and `tests/test_l1s2_protected_carriers.py` pins all fifteen against a fold that
forgets it.

**The honest total.** Across all six stages the measured newly-validated count is **0 to 8**,
and the three points of that range are three different tests, all printed by the same
instrument (§2.6): **0** under the strict after-chain bound, **2** under the production checks
built for the furniture that bound cannot tell apart, **8** if §8 Q3 is granted. The design
recommends 2 as the planning figure and says so with the reason; it does not offer 2 as the
only number its evidence supports. Out of a run of 3,380 with 2,596 validated. The
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
| **Q1** | When one account validates and another does not, does the document publish the validating account's figures (as `withheld`/`review` at document level) or refuse entirely? **And whichever is ruled, is a PACKAGE member an account whose own outcome is `validated`?** The design's answer to the second half is yes, and it must be ruled because today `_package_analysis` gates a member on job status alone (`webapp/app.py`:661) and never on `classify_outcome` — so "publish it and mark the document `withheld`" would silently mean "aggregate it anyway" | whether the model produces `failed → withheld` improvements or nothing at all until every account closes; and what a package does with a partially-closing document | every multi-account document that partially closes; today all such documents are `failed` |
| **Q2** | **The prior question, which the first version did not ask: may an arithmetic coincidence set INTERNAL at all, with nothing printed?** This design now says NO — a printed transfer designation on at least one leg is required, and a pair without one refuses the aggregation rather than being flagged. Then: must the counterpart be on the SAME document (this design says yes)? And does an AMBIGUOUS pair refuse only the package aggregation (this design's proposal) or the whole document? | §3.2, §3.3 — whether a printed deposit can be removed from a funder's view of the business by an inference | 7 documents, 47 pairs; **43 of the 47 carry a printed INTERNAL designation** and 4 do not - 3 of them admitted only by a peer-to-peer vocabulary this design refuses - so the requirement costs **4 pairs**, and **42 of the 43 rest on ONE printed leg**; **0** postings are ambiguous, so that branch's killer must be a constructed fixture |
| **Q3** | May a section be OMITTED rather than counted when it prints its OWN opening caption and its OWN closing caption, the two figures coincide, and it prints no dated row, no counts, no totals and no daily table? R-a says absence of parsed activity alone is insufficient — and this is not that: the paper printed two figures about that account and they agree. Is that "explicit statement structure establishing its empty state"? | **2 documents → 8**; and beyond that family, whether 44 of the 86 single-posting documents (siblings empty-and-silent, or declaring idle in a wording symitar does not read) are reachable at all | 6 idle sections on 6 documents, all one census group, **all six with both figures from the section's own captions and 0 of them printing a dated row, counts, totals or a daily table**; 21 such sections in the whole population, every one of them on the same provenance; 62 empty-and-silent sibling sections and 7 in other wording |
| **Q4** | Two published sections in two denominations: publish two accounts, or refuse the document? R-f allows both. **Ruling it needs §4's new rung first**: a document-level printed statement of denomination outranks a jurisdiction or institution default, or the question is being asked about a hierarchy that inverts R-f | L1-C13 | 4 documents, one census group, 12 sections; the single-denomination document-level class is measured by nothing yet |
| **Q5** | Does each account of a multi-account document enter a PACKAGE as its own member? And is `analysis/adb.py`'s "one statement yields one ADB" read as one ACCOUNT yields one ADB (which R-c forces)? **And, the part R-c does not settle: a package holding one multi-account document publishes `package_average_daily_balance` as the days-weighted mean of its members — which is one average over that document's accounts. Is that permitted?** "A package of one document is still a package" is defensible; so is refusing it. It must be ruled, not left to fall out of the surface table, and §6.5 now carries a gate for whichever way it goes | §2.5, §3.2, `webapp/app.py`:1152-1164 | the package layer; 95% of sections print no daily table of their own |
| **Q6** | Where an issue prints a per-account activity RANGE rather than one document cycle, whose period does L1-C9 mean? | §2.4 | 27 documents lose every section today for printing no resolvable period at all; the per-account-range class is not separately measured |
| **Q7** | The posting threshold: is "a section that posts" one dated row or two? | the whole population's size | at two rows: 86 single-posting / 81 multi-posting. At one row: 59 / 111. The 2 documents that close, close at BOTH |
| **Q8** | §9 F1/F2: symitar, community_section and zions skip sections today. Does R-a apply to those EXISTING skips, or only to new admissions? | whether S2 is a payload-only card or a correctness card that can REMOVE validated documents | **ANSWERED BY MEASUREMENT — §2.7. The skips fire on 12 validated documents / 16 sections, and 16 of 16 print the evidence R-a demands. Applying R-a to the existing skips removes 0 validated documents.** What remains for Gustavo is the vocabulary widening L1-C17 now carries |
| **Q9** | Which point of the measured range is the planning figure: **0** (the strict after-chain bound), **2** (the production checks), or **8** (with Q3)? | what S4 is judged against | §2.6: the same instrument prints all three |

**Q8 was the one to answer first, and it is now answered.** The design said it was the only
question whose answer could subtract from 2,596; measured on the dispatch path, it subtracts
nothing (§2.7). The question that remains under it is not a risk but a vocabulary: L1-C17 has
to be able to NAME the evidence the platform's own skipped sections print, and §4 now does.

### 8.1 The independent reviewer's opinion on each ruling

Carried verbatim from the re-review (`docs/moneythumb-replacement/reviews/BATCH9_L1DESIGN_REVIEW.md`),
marked as the reviewer's and not as this design's. They are recorded because Gustavo is
deciding, and a second independent reading of the same measurements is evidence about them.

| | the reviewer's opinion, verbatim |
|---|---|
| **Q8** | "Answer it YES; it costs nothing, and that is now measured twice. The closure's probe reports 12 documents / 16 sections / 0 with no printed evidence, on the dispatch path, with the watched lines verified and the refusing class shown reachable by nine constructed fixtures. My own independent instrument, written before `zions` was probed by anyone, reported 11 documents / 15 sections with the same per-registration split — the difference is `zions`, which the closure added. Q8 goes to Gustavo as a measurement, not a risk, and the only work it creates is re-founding 12 documents' skips on evidence already printed" |
| **Q9** | "Plan against 2; report 0-8; judge S4 against 2, or against 8 if Q3 is granted. **Not 0**: the strict after-chain bound counts any printed date-plus-figure as an unaccounted row, and the instrument's own docstring (`l1_split_prototype.py`:528-537) says the last section of a document runs to the end of the page and carries its trailing tables — so the 0 refuses work the production validator accepts. **Not 8 by default**: that is Q3's to grant. **2** is what `reconcile`, the ADB and `posting_dates_cover_source` actually accept today, which is the standard every other batch-9 number is measured against. Carry 0 in the same table as the reason it is pessimistic" |
| **Q3** | "Grant it. The closure strengthens the case rather than restating it: the platform already relies on the same evidence class one level up — 8 sections whose printed summary shows an opening, a coinciding closing, and zero totals AND zero counts — and granting Q3 is the same act as the C17 widening that keeps 12 protected documents. Worth 2 -> 8, all one census family" |
| **Q1** | "Rule the second half explicitly and YES. The design's answer is right and the reason is measured: `_package_analysis` gates on job status alone (`webapp/app.py`:661), so 'publish it and mark the document `withheld`' silently means 'aggregate it anyway'" |
| **Q2** | "Both of the design's answers are right. **But settle RR-MAJOR-1 first** — the designation vocabulary decides 45 of 46 pairs, and three of them on a third-party rail. Ambiguity refusing only the aggregation is correct and its killer is a constructed fixture (0 in the archive)." *(RR-MAJOR-1 is now settled: the vocabulary is the internal one alone, and the corrected figures are 43 designated / 4 refused, 42 of the 43 on one leg — §3.2.)* |
| **Q4** | "Rule after the new document-level rung's population is measured — the design says an implementation card owns measuring it, and that ordering is right. The two-denomination class is 4 documents / 12 sections" |
| **Q5** | "Yes to both, and the mechanism the closure chose is the right one: forbid the ARITHMETIC (no published average over two members sharing a `content_sha256`), not the field name" |
| **Q6** | "No objection; refuse until ruled. Unmeasured by anyone, correctly" |
| **Q7** | "Rule at **two**, which is what every table in the packet, the design and the closure uses. Low stakes for S4 (the 2 close at both) and high for what L1-C4 means" |

### 8.2 Which cards may be cut — the reviewer's verdict

| stage | verdict | what is owed at the card |
|---|---|---|
| **S1** | **may be cut now** | — |
| **S2** | **may be cut now** | name which of the three `dakota_west` documents is the pinned one, before the card claims no pinned movement |
| **S3** | **may be cut now** | L1-C18's constructed fixture — a two-account payload with every per-document single-value field asserted EMPTY (§4) |
| **S4** | **not until RR-MAJOR-1 is closed** — its named killer population was the thing that finding was about. *(Closed at this tip: the vocabulary is the internal one alone and the population is re-measured — §3.2.)* | L1-C2's and L1-C11's ambiguity fixtures (§4) |
| **S5** | **waits on Gustavo** — a `validated → failed` on two protected shas, one pinned | the ceremony (§6.3), and L1-C14's guard extension (§4) |


---

## 9. Four defects in production code, found by this cell

Each was verified by reading the code at this base, and each is a fact about what the platform
does today — not a proposal.

**F1 — the ratified dormancy predicate is not the one production runs.**
`analysis/symitar.py`:116 defines `_DORMANT_RE`, and the module's docstring (13-48) ratifies the
skip it licenses. Measured by grep at this tree: **`_DORMANT_RE` is referenced by no code in
`analysis/` or `tests/`.** Its only consumers in the repository are `tools/l1_split_prototype.py`
and prose. What production actually executes for the dormant skip is **`symitar.py`:419-420**
`if not rows: continue` — a skip on the ABSENCE of parsed rows, which R-a names insufficient on
its own. (`:421-423` is the comment that follows it; the design's first version cited the
comment. `tools/l1_design_skip_probe.py` now verifies the watched line against the source text
it must sit on before it reads a document, so this class of citation error fails loudly.) The
yield-only skip at :425 IS on printed evidence and IS the ratified predicate, including its
fourth condition. So one of the module's two ratified skips is implemented as ratified and the
other is not.

**F2 — the same shape in `community_section`, at the site the reader takes.**
The design's first version named `community_section.py`:984 —
`if stmt is not None and stmt.transactions` at the call site. Measured on the dispatch path
(§2.7): that clause drops **0** sections on this archive. The drop production actually takes is
**`community_section.py`:621-622**, `if not txns: return None` INSIDE
`_parse_sectioned_statement`, which fires **8** times. The substance of F2 survives untouched —
the drop is on absence of parsed rows and it is silent — and two things follow from the
correction:

* S2's file list must name `:621-622`, not `:984`. An implementation card told to instrument
  `:984` would surface nothing at all.
* the omission record must be written where the reader that made the skip can see the block,
  which is INSIDE `_parse_sectioned_statement`, not at its call site. The call site has already
  lost the block by then.

**F3 — a memorised account number selects the ledger on a pinned audited document.**
`analysis/consumers.py`:88-94 slices the document between a memorised product-name-plus-
account-number literal and a memorised end caption. The account NUMBER appears once, at `:90`;
`:116` restates the product designation and its suffix but captures the number rather than
naming it (`(\d+)`), so "the same literal twice" over-stated it. One literal is enough: it is
the only thing that finds the slice, and `:111-112` refuses when the slice is empty. It is R-1
in its purest form — the reader publishes exactly one account of one
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
chain" row, which reconciles). `result.reached` is set before the empty-arrival classification,
so the 21 + 23 empty arrivals are already inside `walked` and adding them again is the
double-count. The print line has read that way since the BLOCK-1 commit, which precedes the
packet's final version, so the packet's 109 is a correct figure that its own instrument does
not print rather than a stale transcription. No conclusion in the packet or in this design
depends on the printed value — every downstream rung is computed from `walked` and `non_empty`,
not from the sum — but the packet's claim that every number in it reproduces from its
instruments is not true of that one cell. Reported, not fixed: this cell owns no L1INV file.

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
* `tools/l1_design_idle_evidence.py` — where every trivially idle section's opening and closing
  came from. It re-runs `tools/l1_split_prototype.py`'s own `run_document` and reports two
  fields that instrument computes and does not emit; it writes no grammar of its own.
* `tools/l1_design_skip_probe.py` — the silent skip on the DISPATCH PATH: which sections each
  reader actually drops, and what those sections print, classified only by the modules' own
  committed patterns. Every watched line is verified against the source text it must sit on
  before a document is read, so its zeros cannot be a refactor going unnoticed.
* `tools/l1_design_transfer_probe.py` — the internal-transfer pairs under three pairing rules,
  and how many carry a printed transfer designation, decided by
  `analysis/transaction_classifier.py`'s own committed vocabularies.

All six are unregistered, imported by nothing outside `tools/`, and reach no network.

### 10.3 Proof floor at this tree

| proof | result |
|---|---|
| canonical guards (5 files), with the **six** prototypes present | **255 passed — EXIT=0** |
| `tests/test_experiments_are_not_wired.py` | passes; it guards `experiments/` and says nothing about `tools/` — the property here is held by a GREP, not by a gate, exactly as the L1INV packet's MINOR-4 recorded. A `tools/` clause in that guard is a production-test change this card does not own |
| the instruments are unwired | nothing outside `tools/` references any of the **six**, verified at this tip |
| no production file differs from base | `git diff --stat ac1d034 -- analysis ocr webapp discovery telemetry corpus_gate.py benchmark` — **empty** |
| branch privacy scan vs the whole population | **hit_count 0** over 2,396 added lines and 3,351 documents read (population 3,380; the 29 with no cached text are the same 29 the pinned survey cannot reach). MONEY / DIGITS / DATES / WORDS all 0. Raw scan 28, every one of them class WORDS, discarded by `words_class` — the standing exclusion applied at the batch-8 train, whose own docstring says the tree is unaudited for customer names by construction. This document names no census family and no institution outside a registration id |
| commit-message scan | **hit_count 0** over every commit on this branch, MONEY / DIGITS / DATES / WORDS all 0 — WORDS included, with the mandated co-authorship trailer on every one. It was not 0 the first two times: twice, an ordinary English word this archive prints was caught by the WORDS class. The messages were rewritten (once over the whole branch with `--msg-filter`, trees verified byte-identical and no record here citing a commit sha; once at the tip) and the scan re-run after each |
| the three L1INV instruments re-run from the run of record | EXIT=0 each; §10.1 is the ledger |

No mutation table and no archive sweep are owed: this card adds no gate and no grammar to
production. The full suite, the canonical conformance set and the corpus gate are not re-run —
the diff against base is this document, the W3 section, the review, and **six** files under
`tools/`. That is a structural argument, and it is offered as one.
