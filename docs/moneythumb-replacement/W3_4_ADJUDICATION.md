# W3-4 — cluster adjudication, routing, and coverage movement

Agent B (HARBOR), 2026-08-07. Branch `wave3-diagnostics`.
Card: `WAVE3_BRIEF.md` §W3-4, under Gustavo's ruling 6 (**systemic
adjudication, never statement-specific remediation**).
Depends on: W3-2 (`W3_2_TAXONOMY.md`) for the ranked failure classes, DSC-1 for
the run artifacts, W3-1 for the crash clusters.

---

## 1. What this is for

Discovery produced 3,506 dispositions and `DISCOVERY_COMBINED_REPORT.md`
ranked them into six failure classes. What it could not do is say, for each
cluster, **which remediation mechanism should own it**. That decision was going
to be made in conversation, once, over a report — and then be unreproducible.

W3-4 makes it a tool. Two commands over finished run directories:

```bash
python -m discovery.adjudication <run_dir> [--enrich <run_dir> ...] [--write]
python -m discovery.compare <baseline_run_dir> <candidate_run_dir>
```

The first produces the **adjudication workspace**: one masked evidence card per
cluster, each carrying a proposed disposition and the rule that proposed it.
The second is how every Track A / W3-3c improvement gets measured against the
frozen baseline from now on.

Neither re-runs anything. Both read the gitignored artifacts a discovery run
already wrote, so adjudication costs nothing and can be redone whenever the
evidence or the rules change.

**Systemic by construction.** The unit is a cluster, never a statement. No card
names a document: documents appear only as content hashes, and only as a
sample of five. Work aimed at a card is work aimed at a layout family.

## 2. Evidence, and what may cross into a card

`discovery/evidence.py` loads a run as masked, hash-keyed documents.

| Source | Used for | Sensitivity |
|---|---|---|
| `telemetry.jsonl` | everything: outcome, dispatch, W3-2 diagnostics, structural profile, near-miss vector, W3-1 exceptions | non-sensitive by construction (H3_SCHEMA I1) |
| `rows.csv` | `folder_label`, `dedup_status` — **and nothing else** | the file also holds `relative_path`, `statement_bank` and `account_last4`; none of the three is ever read |

`ADMISSIBLE_ROW_COLUMNS` is a three-element tuple and a test asserts that a
workspace built from a row carrying a customer-shaped path, an extracted bank
label and an account fragment contains none of them.

Folder labels are admissible because they are **analyst-assigned bank names**,
already published in `DISCOVERY_COMBINED_REPORT.md` §2. Paths are not, because
customer names live in them.

**Identity is `content_sha256`, everywhere.** That is what makes two runs
comparable without caring about ordering, run ids, timings, record ids, or
which tranche mode produced them. One consequence is reported rather than
hidden: the archive holds the same bytes under more than one path, so 3,506
telemetry records collapse to **3,380 distinct documents**, and the workspace
header says so.

### 2.1 The cache-hit hole, and the cross-run join

H3_SCHEMA §5.4 declared this and accepted it: on a D-3 analysis cache hit
`analyze_markdown` never runs, so the record carries no `parser_id`. Benign for
coverage. **Fatal for W3-4**, because "failure class × parser" needs the parser.
Measured on the archive runs:

| Run | Withheld | With a `parser_id` | Diagnosed |
|---|---:|---:|---:|
| `ec400125` (tranche 1, first pass) | 608 | **608** | 0 (pre-W3-2) |
| `0fd1bc0b` (tranche 2) | 614 | 6 | 0 (pre-W3-2) |
| `02e90a86` (the W3-2 baseline) | 614 | **0** | **614** |

So the baseline **cannot answer its own question alone**: the run that has the
diagnoses has no parsers, and the run that has the parsers has no diagnoses.

`--enrich` fixes it by joining a companion run on the content hash. The
justification is that a parser claim is a property of the document and the
registry, **not** of the run that happened to observe it, so recovering it from
another run over the same bytes is sound. It is declared in the output
(`NOTE parser identity joined by content hash from: …`) and counted per card
(`evidence.parser_enriched`), never silently merged.

The dispatch **outcome** travels with the parser id. Recovering `parser_id`
alone leaves a document looking like it never dispatched, and every cluster
keyed on "was this claimed" — label disagreements, claims in unlabelled folders
— then silently fails to form. That was a real bug during development: the
first working version produced zero of both.

**Recommendation for Ocean:** the next baseline should be captured with
`--no-cache` so it is self-sufficient, or H3_SCHEMA §5.4's declared hole should
be closed by persisting the dispatch projection into the cached artifact
(which costs an `ANALYSIS_STAGE_VERSION` bump — the tradeoff H-3 declined for a
re-run-only benefit that is no longer re-run-only). *Ruled: a canonical
`--no-cache` baseline is being re-captured.*

### 2.2 Loud, never silent (W3-2b, ruling 2)

Asking for a failure-class × parser view over a run with unattributed
documents now **raises** `UnattributedParsers` (CLI exit 2) with a message
naming both remedies:

```
N of M diagnosed documents carry no parser_id, so a failure-class x parser
view cannot be built.
This is the H3_SCHEMA 5.4 cache-hit hole: a run served from the analysis cache
never re-dispatched, so it has the diagnoses and not the claims.
  --enrich <run_dir>        recover parser identity by content hash from a run
                            that dispatched these documents live
  --allow-unattributed      build the view anyway; the affected rows are
                            labelled '(parser unknown)' explicitly
```

The failure this prevents is silent: a cache-served run produced a
complete-*looking* table in which every row read `(parser unknown)`, with
nothing in the output saying the question had not been answered. That is
exactly the shape of the archive's W3-2 baseline, so the footgun was loaded.

`--allow-unattributed` is the deliberate escape hatch. It labels the affected
rows `(parser unknown)` and adds a `WARNING --allow-unattributed: N diagnosed
documents … answer no class x parser question` line to the header, so the
degradation is stated in the artifact rather than inferred from it.

The gate is **any** unattributed diagnosed document, not a fraction over a
threshold: a threshold would be a magic number, and the honest signal is "this
view is not complete", which is true at one document.

## 3. Cluster kinds

| Kind | Grouped by | Source of the cluster |
|---|---|---|
| `withheld_check_cell` | (W3-2 primary class, parser) | the ranked queue W3-2 exists to produce |
| `unclaimed_bank_folder` | folder label | `DISCOVERY_COMBINED_REPORT` §2 classes 1 and 4 |
| `unclaimed_unlabelled` | all unlabelled folders together | class 2, the Unidentified mix |
| `label_disagreement` | (folder → parser) pair | §4 adjudication queue |
| `unlabelled_folder_claims` | one cluster | §4, the 225 |
| `parser_crash` | (parser, exception class) | class 6, W3-1's ranking |
| `advisory_flag` | one cluster | §4, the 4 truncation flags |
| `unusable_document` | one cluster | class 7 |

Clusters below `MIN_CLUSTER` (5) roll into a per-rule `(tail: …)` card, so a
400-line workspace does not bury the ten clusters that matter.

## 4. The disposition vocabulary and the routing rules

Closed vocabulary, exactly as dispatched:

```
variant_completeness | generic_structurer | new_parser_candidate
| misfiled | junk_unusable | parser_defect | needs_human_review
```

`parser_defect` was added in **W3-2b** (Ocean ruling 1). Parser crashes were
routed to `needs_human_review`, which made the human queue look like it
contained a taste question when it contained a bug. They now route
mechanically, out of the queue, with the card stating that **W3-1's exception
ranking owns the remediation** — the card exists to account for the documents,
not so anyone fixes them from here.

A rule is only allowed to exist if **the evidence alone decides it**.

| Rule | Disposition | Why it is mechanical |
|---|---|---|
| `R1_claimed_but_withheld` | `variant_completeness` | a parser claimed it and the platform withheld: detection is already right, so the gap is extraction completeness. True by definition |
| `R2_known_bank_unseen_layout` | `variant_completeness` | unclaimed, but the registry already has a parser for this bank |
| `R3_unregistered_bank_volume` | `new_parser_candidate` | unclaimed, no registered parser, volume clears the floor — **proposal only** |
| `R4_unregistered_bank_tail` | `generic_structurer` | unclaimed, no registered parser, volume does not justify one — the AD-7 case |
| `R5_unlabelled_mix` | `generic_structurer` | a human could not even sort these into a bank folder, so only a layout-agnostic mechanism applies |
| `R7_unusable_document` | `junk_unusable` | not a readable PDF, or encrypted |
| `R6_label_disagreement` | `needs_human_review` | see §4.2 |
| `R8_parser_defect` | `parser_defect` | our defect, not a layout family and not an adjudication question; W3-1's ranking owns the fix |
| `R9_advisory_flag` | `needs_human_review` | a policy question Ocean already queued |
| `R10_unlabelled_folder_claims` | `needs_human_review` | no label to check the claim against |

"Do we already have a parser for this bank" is answered by reading the **live
registry** (`registration.id` and `registration.bank`), never by a list in this
file — so it cannot drift, and no bank name becomes a constant here (the R-1
rule).

### 4.1 `misfiled` is reachable only by a human

No rule proposes it, and a test asserts that. Nothing in the evidence separates
a genuinely misfiled document from an alias the matcher cannot see through. The
vocabulary member stays, because `misfiled` is what a human writes into the
worksheet's `adjudicated_disposition` column.

### 4.2 The false-misfiled trap, found and fixed

The first version of R6 proposed `misfiled` whenever the folder label did not
contain the parser id. On the archive it produced **65 documents across several
pairs**, headed by `TD Bank -> td_us` (28) and `Thread Bank -> relay` (17).

Both are wrong. `td_us` is *registered as* "TD Bank"; `relay` is registered
against Thread Bank. Those documents are in exactly the right folder. This is
precisely the failure `discovery.report.folder_agreement`'s docstring warns
about — *"calling them disagreements would manufacture a detection-accuracy
problem out of a string-matching limitation"* — and a `misfiled` verdict would
have sent a human to "fix" 28 correctly-parsed statements.

Two changes:

1. A parser answers to its **registered bank name** as well as its id. Both are
   our constants, so both are admissible where `Statement.bank` (read out of the
   document, forbidden by I1) is not. This is what `folder_agreement` was using
   `statement_bank` for, obtained legitimately.
2. R6 proposes `needs_human_review`, not `misfiled`. A label disagreement is a
   **question**, and it is ranked by distinct pair so the answer is given once
   and applies to every document in it.

Result on the archive: from 65 false positives down to **3 pairs / 24
documents**, all genuine questions (`Chase -> mission_valley` 16,
`Chase -> relay` 4, and one smaller).

**Finding for Ocean:** `DISCOVERY_COMBINED_REPORT` §4's "21 misfiled documents"
came from a matcher that consulted `statement_bank`. The number is not
reproducible from telemetry, and the registry-label matcher above gets 24 —
close, differently derived, and worth reconciling before anyone acts on either.

### 4.3 The new-parser floor

`NEW_PARSER_VOLUME_FLOOR = 50`. A **policy** threshold, not a
statement-specific constant: it encodes the argument
`DISCOVERY_COMBINED_REPORT` §2 class 4 makes — per-bank volume must justify
parser #47 — and Huntington (54) is the case it was built to catch. CLI-overridable.

Volume is the only half it can measure. **Layout stability is not observable
from telemetry**, so every card records `layout_stability: unmeasured` and the
rule text says `PROPOSAL ONLY`. WAVE3_BRIEF gate 3 makes any new parser
Gustavo's call, and the tool does not pre-empt it.

## 5. The worksheet

`--write` produces two files in the run directory (gitignored, like every other
run artifact):

- `adjudication.json` — the full cards, including per-cluster evidence.
- `adjudication.csv` — the worksheet: `kind, cluster, documents,
  proposed_disposition, rule, adjudicated_disposition, adjudicator, note`.

The last three columns are written **empty** and nothing in the tool ever fills
them. A human fills `adjudicated_disposition` and the file becomes the record
of the ruling. That separation is the whole design: the tool produces the
queue, the human produces the verdict.

## 6. Coverage movement

```bash
python -m discovery.compare <baseline> <candidate> [--enrich …] [--fail-on-regression]
```

Two commitments:

**Keyed on content hashes, never on ordering.** Run ids, timings, record ids,
row order, tranche mode and the wall clock all differ between any two runs and
none of them is a difference in what the platform did. A test compares a run to
its own reversed copy and asserts `identical: true`.

**Asymmetry is reported, never averaged.** `improved` and `regressed` are
separate lines, with a sample of each and a per-family breakdown. A comparison
that printed only a net delta would let a real regression hide inside a bigger
win — the one thing a merge gate must not do. `--fail-on-regression` exits 2,
so this can become a gate.

The outcome ladder is `failed < withheld < review < validated`. **`deferred`
sits outside it deliberately**: "this tranche chose not to try" is a statement
about the run, not about the document, so moving in or out of it is neither an
improvement nor a regression and is reported as `unranked`. That is exactly
what the tranche-1 → tranche-2 demo shows: 179 documents moved out of
`deferred`, and calling those 159 `deferred -> failed` transitions "regressions"
would be false.

Movement is reported three ways: by outcome transition, **by W3-2 failure
class** (`left detail_coverage`, `entered period_integrity`), and **by parser
family** — which is what "fix the top failing check-class for chase variants"
needs in order to be checkable afterwards.

## 7. Baseline (run `02e90a86`, enriched from `ec400125`)

3,380 distinct documents.

| Disposition | Documents | Share |
|---|---:|---:|
| `variant_completeness` | 1,286 | 38.0% |
| `generic_structurer` | 916 | 27.1% |
| `needs_human_review` | 246 | 7.3% |
| `new_parser_candidate` | 54 | 1.6% |
| `junk_unusable` | 16 | 0.5% |

Two thirds of the archive routes to two mechanisms, and the largest single
addressable cell in the whole corpus is
**`detail_coverage × chase` = 213 documents**. The human queue is 246
documents in 4 clusters, and 222 of those are one question ("are claims in
unlabelled folders trustworthy?").

## 8. Test inventory

`tests/test_adjudication.py`, 38 tests, all fast and default-run:

- **Evidence** — hash keying and duplicate collapse; the three admissible row
  columns with a leak assertion on a customer-shaped path, an extracted bank
  label and an account fragment; a run without `rows.csv` still loads.
- **The join** — parser identity and dispatch outcome recovered from a
  companion run; enrichment never overwrites a real claim; first run wins.
- **The registry** — registered banks read live; a parser answers to its
  registered bank name (the `TD Bank`/`td_us` guard).
- **Every routing rule** — one test each, plus: `misfiled` is proposed by no
  rule; every rule's disposition is in the closed vocabulary; unusable
  documents are not also counted as layout clusters; small clusters roll into
  the tail.
- **The workspace** — no card carries anything but aggregates and hashes; the
  worksheet's adjudication columns are empty; ASCII only.
- **Movement** — the ladder, `deferred` outside it, a run vs its reversed self
  is zero movement, class and family breakdowns, a regression is not averaged
  away, differing document sets are reported not intersected, and the
  `--fail-on-regression` exit code.

## 9. Rulings received (W3-2b) and open questions

**Ruling 1 — CLOSED.** `parser_defect` added to the vocabulary; `R8` routes
crash clusters to it mechanically, out of the human queue, with W3-1's
exception ranking named as the owner of remediation (§4).

**Ruling 2 — CLOSED.** Silent degradation removed: an unattributed
class × parser view raises and names both remedies (§2.2). A canonical
`--no-cache` baseline is being re-captured, which removes the underlying cause.

Still open:

1. **"21 misfiled" is not reproducible from telemetry** (§4.2). The
   registry-label matcher gets 24 in 3 pairs. Worth reconciling before the
   adjudication session.
2. **`NEW_PARSER_VOLUME_FLOOR = 50`** is my proposal, calibrated so Huntington
   (54) clears it and Mercury (31) does not. It is the one number in W3-4 that
   is a judgement rather than a measurement.
3. **Should `--fail-on-regression` become a CI gate** once a post-W3-3c run
   exists? The machinery is there; making it authoritative is a policy call.
