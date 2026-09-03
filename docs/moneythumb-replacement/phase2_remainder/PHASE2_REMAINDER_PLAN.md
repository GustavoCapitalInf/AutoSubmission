# PHASE 2 REMAINDER — PLANNING PACKAGE

```
STATUS:      PROPOSED PLAN — for Gustavo's review; NOTHING IMPLEMENTED
DATE:        2026-09-03
AUTHOR:      Ocean (Fable 5.1, lead orchestrator), from eight independent Fable 5.1 research/audit
             agents (four read-only repository audits, four external research tracks) — the memos are
             in ./research/ and every factual claim below cites one of them or a repository path
BASE:        phase2.1-final (composed code tree 4f7d798 on train11; docs tip 21e3163); main = phase2.1-final
FLOOR:       2,625 / 3,380 validated (77.66 %); 0 validated regressions; 0 false accepts on evaluated truth
BINDING:     PHASE2_RULINGS.md (OQ1–OQ11, Ruling A, Ruling B, the Vast.ai authorization),
             PHASE2_ARCHITECTURE_PLAN.md (governing invariant), ORCHESTRATION-MODEL-POLICY.md,
             BATCH9-RULES.md + PHASE2-RULES.md, ADB / currency / repair doctrines, and Gustavo's
             2026-09-03 planning brief (sections 0–30), which this package answers section by section
```

## 0. How to read this package

This is the durable planning package the brief asked for (brief §28, items A–O), plus the answers to
the twenty research questions (§27), the evaluation of the five Phase 2.1 prerequisites (§23) and the
three-way comparison (§22). It proposes; it does not implement. Every milestone below waits for
Gustavo's approval of this package and then of its own umbrella card.

Companion documents (verbatim agent memos, privacy-scrubbed): `research/OCROLUS_PRODUCT_MEMO.md`,
`research/OCROLUS_INTERNALS_MEMO.md`, `research/MONEYTHUMB_MEMO.md`,
`research/LAYOUT_RECONSTRUCTION_MEMO.md`, `research/UNLIMITED_OCR_MEMO.md`, and the four repository
audits `research/REPO_CORPUS_MEMO.md`, `research/REPO_GEOMETRY_MEMO.md`,
`research/REPO_VALIDATOR_MEMO.md`, `research/REPO_LEGACY_RULINGS_MEMO.md`. Citations of the form
`memo:REPO_CORPUS §3.2` point into them; `file:line` citations are against `4f7d798`.

Epistemic labels used throughout for external claims: **DOCUMENTED** (a fetched primary source says it),
**STRONGLY INFERRED** (the only economical explanation of two or more documented facts), **PLAUSIBLE
HYPOTHESIS** (consistent with the evidence; alternatives exist), **OUR DESIGN CHOICE** (what we should do
regardless of what anyone else does).

Nothing in this package re-opens a ruled question. Where a new decision is genuinely Gustavo's, it is
in §N and nowhere else.

---

## A. EXECUTIVE ARCHITECTURE SUMMARY

**The residue is a layout problem wearing an OCR costume.** Of the 755 unresolved documents at the
Phase 2.1 run of record, 583 (77 %) are native-text digital PDFs with usable text (median 2,024
characters per page), 131 are scanned PDFs Tesseract read but no parser understood, 12 are mixed, 16
are not PDFs at all (Java-serialisation portal artefacts), and 13 have no text (the R population Paddle
is currently allowed to read). The failure-class split is B 656 / C 70 / none 29; row-level Class A is
zero (`memo:REPO_CORPUS §3.1`). The prior census tags 117 of the 755 as not statements at all, 322 as
members of 91 known layout families, 119 as claimed-then-declined by a template reader, 89 as scans
no reader claims, 52 as ADB-withheld and 18 as review (`memo:REPO_CORPUS §3.2`). No Paddle or visual
escalation has ever run on a real document in any run of record.

**Therefore the strategic lever is generalized layout understanding on canonical geometry, and Paddle's
strategic role is evidence acquisition for pages whose text layer is absent or unreliable, plus a
controlled research reading of everything else so that production triggers are derived from
measurement rather than assumed.** This is Gustavo's ladder with two corrections and three additions:

* Correction 1 — *in production*, native geometry comes before Paddle on native-text pages, because
  PyMuPDF word boxes are exact and free; Paddle reads native-text pages only under measured,
  pre-financial extraction-quality triggers (text-layer defects, image-backed text layers, orientation
  anomalies). *In the research wave*, Paddle reads every unresolved page regardless (brief §13), which is
  how those triggers get measured instead of guessed.
* Correction 2 — document classification is not one gate before Paddle; it runs on the best evidence
  available at each rung, so a voided cheque is refused at the free Tesseract rung and never leaves the
  machine, while an UNCERTAIN scan is re-classified after Paddle.
* Addition 1 — the **holdout cage and a sealed human-adjudication store**, which the accepted
  architecture called operational and which was never built (no module mentions a holdout;
  `memo:REPO_CORPUS §6`). Without it, "false accepts 0" can only ever be measured on synthetic
  fixtures and the 80 pinned documents inside the denominator.
* Addition 2 — a **LayoutModel** layer between `DocumentGeometry` (lines of words, which is all it is:
  `memo:REPO_GEOMETRY §2`) and the structurer: furniture, page continuity, table regions, column
  models, records with continuation lines, section semantics, account sections and summary blocks,
  each with word-id provenance and a closed refusal vocabulary. This is where bank-agnostic behaviour
  is built; the structurer becomes its consumer and the existing `Statement` / `publish_partition`
  contract is the unchanged exit into the SAME validator (`memo:REPO_VALIDATOR §2`).
* Addition 3 — a **layered unresolved-reason taxonomy** (file → document kind → extraction → structure →
  financial → doctrine) and two honest denominators, so "755 unresolved" becomes counts with names.

**What stays exactly as it is:** Phase 1's 84 registrations and their printed-oracle discipline; every
Phase 2.0/2.1 invariant (A/B/C separation, the router that cannot see the verdict, the postprocess
quarantine, the endpoint policy, run-of-record artifact selection, the pinned Paddle identity, the
evidence contract); the validator and its five-layer `validated` predicate; the 2,625 floor; the rule
that a coverage gain never cancels a regression; the rule that the validator is not an optimizer — which
this package makes structural for the new layer (§E.4).

**Milestones (six, replacing the old 2.2–2.5; mapping in §F):**

| # | Name | Delivers | Coverage movement | Customer data off-machine |
|---|---|---|---|---|
| 2.2 | TRUTH INSTRUMENTS | document classifier v1, unresolved taxonomy, holdout cage + sealed adjudication store, funnel/cost telemetry, geometry-aware analysis key, native evidence sha + rotation frame, research run-mode wiring | +0 | none |
| 2.3 | BROAD PADDLE EVIDENCE WAVE | Paddle over all 755 unresolved (5,110 pages) + a validated control sample, immutable research partition, extraction-quality gate v2 calibrated, native↔Paddle agreement, corpus truth table, baseline fallout with the existing structurer | +0 official (research gains named, not admitted) | yes — under the §6 authorization, recorded first |
| 2.4 | GENERALIZED RECONSTRUCTION v1 | `layout/` package + structurer v2 on native geometry and Paddle geometry; synthetic layout archetypes + mutation tables; first holdout pass | native-geometry gains admitted; Paddle-fed gains named, pending routing | research only |
| 2.5 | RECONSTRUCTION v2 + PADDLE PRODUCTION ADMISSION | hardening on measured fallout; measured pre-financial triggers admitted; page-level/mixed routing; disagreement → review; evidence_refs lineage; local_free measurement | Paddle-fed gains admitted under the measured triggers | production policy decided by ruling |
| 2.6 | UNLIMITED OCR (go/no-go) | research spike on the residual Class-A population; extractor-only integration with region sidecar and the four-identity bar — only if the residual justifies it | thin tail | requires its own ruling |
| 2.7 | PHASE 2 CLOSURE | routing frozen from evidence, both denominators, cost/latency, runbooks, Phase 3 seam pinned, tag `phase2-final` | none new | — |

**Honest expectation.** The population addressable by generalized reconstruction on native geometry is
roughly the 583 native-text unresolved minus the ~117 non-statements, minus the 8 text-layer defects,
minus the 50 native Class C, i.e. about 400 documents, plus 123 scanned/mixed Class B via Paddle
geometry. The existing structurer, measured 2026-08-07, validated 5.3 % of unclaimed documents with
"published implies correct" and named completeness (missed rows) as the binding constraint; the
LayoutModel is aimed at exactly that constraint. No coverage number is promised. Milestone 2.4 carries
the accepted architecture's rule: if the layout model does not move documents through the gate, STOP
and report rather than write parsers to hide the result.

---

## B. OCROLUS RESEARCH MEMO (condensed; full detail in `research/OCROLUS_PRODUCT_MEMO.md` and `research/OCROLUS_INTERNALS_MEMO.md`)

Two agents fetched roughly 200 primary pages on 2026-09-03: the entire public docs.ocrolus.com tree
(the site exposes an `llms.txt` index and markdown for every page), the security and sub-processor
portals, the single granted patent family, press releases, podcasts, job postings, the GitHub
organisation, TheOrg, Capterra reviews, and a vendor case study. Gated sources (help centre, G2,
Glassdoor, Medium, web.archive.org) are recorded as failed and used only as labelled snippets.

### B.1 Documented behaviour (what the pages say)

**Object model and intake.** A *Book* is the container for a case; a *Document* is "a single sequence of
Bank Statement pages" that "can contain pages from multiple Bank Statements, including different Bank
Accounts and Account Holders"; a *Mixed Document* is a PDF of several form types that Ocrolus splits,
giving each found form its own UUID. Limits: 200 MB per file, 3,000 pages per document, 40,000 pages
per Book, 75 MP per image. Regions US/CA/MX/UK; English only. Duplicates by MD5 at file level and by
`date + description + amount` at transaction level, linked (`txn_pk_duplicate_of`) rather than deleted.
[DOCUMENTED — memo:OCROLUS_PRODUCT §2.1, §2.10]

**Classification precedes extraction.** Status sequence `QUEUED → CLASSIFIED → PROCESSING → GROOMING →
VERIFYING → VERIFICATION_COMPLETE | REJECTED | FAILED`. "Over 2,100 form types"; many are classify-only
(the supported-documents table has separate *classification* and *extraction* columns). A bank statement
is typed as a tuple `form_type{name: BANK_ACCOUNT, account_type: CHECKING, account_source:
STANDARD_STATEMENT}`. Classification returns *uniqueness values* (holder, bank, period) with confidence,
used to group and de-duplicate statements before capture; unknown pages are UNKNOWN and "classifications
with imperfect confidence are routed to Ocrolus data classification and verification specialists".
[DOCUMENTED — §2.2]

**Rejection reasons (eleven, enumerated).** INCOMPLETE TRANSACTION DATA; NO_TRANSACTIONS; DOCUMENT
CONTAINS UNEXPECTED PII DATA; DOCUMENT IS UNREADABLE (illegibility, password, corruption); DOCUMENT TYPE
NOT SUPPORTED; INVALID DOCUMENT; DOCUMENT DUPLICATE OF; INSTANT NOT SUPPORTED; NO_PERIOD_SUMMARY ("No
period-level information such as opening balance, closing balance, statement start date, and end
date"); STATEMENT_UNRECONCILED ("The sum of the transactions does not match the beginning and ending
balances stated on the statement"); Customer Requested Cancellation. **There is no "missing pages"
reason.** [DOCUMENTED — §2.3]

**Native PDF versus image.** `is_image_based_pdf` flags a document that is "not a parseable electronic
PDF issued by a financial institution"; Detect signals name `has_only_images`, `image_of_known_document`,
`digital_print`, `screenshot`. Capture "uses machine learning, computer vision, and micro-templates" and
"each document is processed through the most suitable digitization tool". Rotation/deskew is documented
nowhere. [DOCUMENTED — §2.4]

**Tiers.** INSTANT = "fully automated AI/OCR extraction, typically returned in seconds"; COMPLETE = "AI
extraction plus human-in-the-loop verification when needed". Upgrades are forward-only and re-queue the
document; a statement Instant cannot parse is rejected `INSTANT NOT SUPPORTED` or promoted. No SLA is
documented; 2022 reviews say big-bank statements were instant while "credit unions and other unknown
banks could take time". [DOCUMENTED — §2.5]

**Human-in-the-loop.** Sub-processor "Ocrolus East Private Limited — Human-in-the-loop (HITL) for data
processing — India"; a Florida QC facility; "thousands of human-in-the-loop verifiers"; a Data Verifier
job description says "Correct or Edit any incorrect details captured by the Ocrolus proprietary systems"
and "Perform reconciliation of various amounts captured"; worker accuracy is checked algorithmically;
verified output becomes labelled training data (240M+ pages claimed). Other sub-processors: AWS, GCP,
Snowflake, OpenAI, Anthropic, Extend AI, Resistant AI. [DOCUMENTED — memo:OCROLUS_INTERNALS §3, §5, §7]

**Output schema.** Per bank account: `bank_name, account_type, account_holder(s), periods[{begin_date,
end_date, begin_balance, end_balance, primary/secondary_recon_error_reason, uploaded_doc_pk}]`,
`activity_info{active[], missing[]}`. Per raw transaction: `page_idx, page_doc_pk, bank_account_pk,
period_pk, amount (signed string), txn_date, description, bbox [pixels], txn_pk_duplicate_of,
has_probable_transfers, tags{}`. Enriched transactions add ~60 boolean tags and `counterparty`. **No
running balance, no debit/credit flag, no per-transaction confidence, no currency field.** Field-level
confidence (0–1) exists only for forms and classification. July 2026 exposed period-level `reconciled,
recon_error_absolute_amount, recon_error_pct_of_average_daily_balance`. [DOCUMENTED — memo:OCROLUS_PRODUCT §2.7, §2.12]

**Detect.** Two engines — Resistant AI (file/pixel forensics: metadata, producer, PDF structure,
incremental-update diffs `content_diff_between_versions`, fonts, overlays, screenshots, online
generators) and Ocrolus ALGO (reconciliation `unreconciled_bank_statement_balance` with `delta`,
date-in-period, future dates, issuer fingerprinting for top banks) — fused into an Authenticity Score
0–100 with reason codes; 43 stable signal identifiers, page numbers and (since July 2026) bounding
boxes; the visualisation "recovers the original document" and highlights edits. [DOCUMENTED — §2.9]

**The patent.** Exactly one family: US 11,087,409 B1 (Bobley, Yang; priority 2016-01-29; granted
2021-08-10; 48 claims), continuation abandoned. It names Tesseract as the reference engine under "a
proprietary OCR system", a "knowledge base of templates used by financial institutions", a
generic-OCR-then-zoom-into-blocks strategy, a preprocessing DAG with cached intermediates, Celery on AWS
with GPUs, transactions as bounding boxes in a spatial index, a per-transaction "quality identifier" from
character/word confidence plus statement and transaction type, balance reconciliation and running-balance
chaining "to autonomously identify potential OCR conversion errors" ("check for errors in the account
balances before checking for errors in the transactions"), and a Back-Office Tool that decomposes
verification into parallel microtasks (document type/orientation → account metadata → transaction
boundaries → polarity → balances/reconciliation → add-missing/remove-false → SME page review).
[DOCUMENTED, dated 2016–17 — memo:OCROLUS_INTERNALS §2]

**Stack signals.** "Subsystems from Amazon, Google and its own proprietary deep learning architectures"
plus OpenAI embeddings (2023); Gemini/Anthropic and fine-tuned open-source models (2026 platform page);
"Universal Calibration" that "calibrates AI confidence scores on a standardized scale" using
human-verified data and "selects the most accurate model based on the task"; GitHub forks of go-fitz
(MuPDF), PyPDF2, Bazel; ML job postings are generalist "CV/OCR/NLP at scale + Kubernetes"; no
engineering blog, no papers, no document-AI conference talks. [DOCUMENTED — §3, §5, §8]

### B.2 Inferred internals (labelled)

1. **Reconciliation, not page counting, is the acceptance gate** — every terminal rejection is
   arithmetic or structural; completeness across time is a separate account-level `missing[]` /
   month-gap model. STRONGLY INFERRED.
2. **Pipeline = ML extract → automated grooming → human queue → complete**; humans review a normalised
   draft, and reconciliation is used three ways: in-loop error localiser (patent), hard output gate
   (`STATEMENT_UNRECONCILED`), fraud signal (Detect). DOCUMENTED for the three roles; the ordering is
   STRONGLY INFERRED from the status sequence.
3. **Modality triage drives tiering** — Instant depends on a text layer plus issuer "micro-templates";
   image-based and off-template files fall to OCR + humans. STRONGLY INFERRED (the 2022 "big banks fast,
   credit unions slow" reviews are this design's fingerprint).
4. **Generalisation across layouts is a hybrid**: learned localisation/labelling models over an
   issuer-aware library of micro-templates (region-level fragments with learned anchors rather than
   fixed coordinates), with human microtasks as the universal fallback that also mints labels, so a new
   issuer's template is an *output of verified data*, not hand-written code. STRONGLY INFERRED for the
   hybrid; PLAUSIBLE HYPOTHESIS for the fragment/anchor semantics of "micro-template".
5. **Transaction reconstruction is row-object based**, not cell-grid based: a transaction is a bounding
   box with page index; polarity and account assignment are separate decisions; running-balance
   chaining links rows and catches misreads; LLM/embedding components entered for the semi-structured
   long tail from 2023. PLAUSIBLE HYPOTHESIS (favoured over a table-grid recogniser because bank
   statements rarely have ruled grids, descriptions wrap, and the human microtask is literally
   "transaction boundary identification and bounding-box placement").
6. **Confidence is field-level and calibrated across heterogeneous models against human ground truth;
   transactions are binary-trusted** (status + reason codes, never a float). DOCUMENTED claims;
   mechanics STRONGLY INFERRED (the Intuit meta-model patent is the public template for the pattern).
7. **Pages are first-class rasterised entities** (`page_doc_pk`, pixel `bbox`), and the
   Account → Period → Transaction graph is independent of file boundaries. STRONGLY INFERRED.
8. **Tamper evidence relies on the PDF text layer and version history**, so it exists only for native
   PDFs; image PDFs get an INFO-type modality signal instead. STRONGLY INFERRED.

### B.3 Likely Ocrolus internal architecture

```
INTAKE  API / dashboard / LOS -> Book -> Mixed Document -> pages; MD5 dedupe; PII scan          [DOCUMENTED]
   |
PDF TRIAGE  parsable vs image-based; text layer, fonts, producer, incremental-update history
            parsed regardless (kept for Detect); pages rasterised to canonical images            [STRONGLY INFERRED]
   |
PAGE CLASSIFICATION + COLLATION  ML page typer over 2,100+ types; uniqueness values split
   same-type forms and group pages into statements; UNKNOWN pages -> human classifiers;
   issuer identity resolved here (Detect's issuer-conditioned signals need it)                   [DOCUMENTED / issuer INFERRED]
   |
DIGITIZATION ROUTER  "the most suitable digitization tool": native text | Amazon OCR |
   Google OCR | proprietary DL OCR with a cached preprocessing DAG                                 [DOCUMENTED exists / members INFERRED]
   |
LOCALISATION / LABELLING  "proprietary ML and pattern recognition to localize each key element
   and label it with the proper context"; micro-templates = issuer/fragment region templates
   with learned anchors; zoning, word boxes -> spatial index                                      [term DOCUMENTED / semantics HYPOTHESIS]
   |
TRANSACTION RECONSTRUCTION  row objects (bbox, page_idx); polarity; account assignment;
   running-balance chaining; period summary (begin/end balance, dates)                            [DOCUMENTED fields / model class HYPOTHESIS]
   |
GROOMING  end - begin == sum(txns); date-in-period; duplicates (date+desc+amount); probable
   transfers; field and document validation rules -> NO_PERIOD_SUMMARY etc.                       [DOCUMENTED]
   |
CONFIDENCE -> UNIVERSAL CALIBRATION -> ROUTING  field-level 0-1; calibrate heterogeneous models
   on HITL ground truth; pick model per task; "multiple AI agents check each other's work";
   thresholds: INSTANT returns in seconds | COMPLETE -> VERIFYING                                 [DOCUMENTED claims / mechanics INFERRED]
   |                                  \
OUTPUT (Instant)                       HITL MICROTASK ENGINE  task hierarchy from the patent;
                                       parallel verifiers in India and Florida clean rooms;
                                       algorithmic worker-accuracy checks; "additional machine
                                       checks" after the human pass; SME page review              [DOCUMENTED]
   |
DETECT  L1 Resistant AI file/pixel forensics | L2 Ocrolus ALGO content/arithmetic/issuer
        fingerprints | L3 Authenticity Score/Status fusion, reason codes, edit overlays           [DOCUMENTED]
   |
ANALYZE  normalisation; ~60 transaction tags; transfers, recurring, NSF; ADB; income; Snowflake   [DOCUMENTED]
   |
DATA FLYWHEEL  verified output -> labels (240M+ pages) + calibration set; continuous training,
   A/B; daily sampled fraud ground truth; hit rates by institution                                 [DOCUMENTED claims / cadence INFERRED]
```

### B.4 Sources

Complete URL tables with fetch status are in the two memos (`research/OCROLUS_PRODUCT_MEMO.md` §1, 93
entries; `research/OCROLUS_INTERNALS_MEMO.md` §15, ~105 entries). The load-bearing ones:
docs.ocrolus.com/docs/definitions, /docs/rejection-reasons, /docs/document-status.md,
/docs/book-upgrade.md, /docs/capture, /docs/classify-first.md, /docs/confidence-score.md,
/reference/transactions.md, /reference/book-info, /reference/mixed-doc-classification-summary.md,
/reference/doc-fraud-signals.md, /reference/signal-definition.md, /changelog/july-2026;
legal.ocrolus.com (sub-processors); security.ocrolus.com; patents.google.com/patent/US11087409B1/en;
the 2023 OpenAI-embeddings and 2023 Instant press releases; ocrolus.com/platform/ (2026);
techcrunch.com (2021 Series C); assist-software.net/project/ocrolus (micro-task app);
capterra.com Ocrolus reviews; github.com/Ocrolus.

### B.5 Lessons for us

* **Adopt** the *statement type as a tuple* with page-level UNKNOWN; *enumerated* rejection/refusal
  reasons; the *raw versus enriched* transaction split; `page + bbox` provenance on every published
  figure; per-account *activity/missing* coverage across statements; reconciliation exposed as a
  structured residual (opening, closing, Σ, delta, delta/ADB) rather than a boolean; separate
  lifecycle events for classify / capture / integrity / analytics.
* **Fill their gaps**, which are our strengths: running balance per row, explicit debit/credit
  direction, currency with provenance, per-row grounding, replayable determinism. Their published
  number is "the model that finally balanced, then a human looked"; ours is a bbox-attributable proof.
* **Do not cargo-cult** the human clean room, the confidence-routed tiering as a coverage strategy, or
  reconciliation as an in-loop *corrector*. The patent's use of balances "to autonomously identify
  potential OCR conversion errors" is exactly the validator-as-optimizer edge our doctrine forbids;
  we may use the same arithmetic to *localise* a refusal for a human, never to *select* a value.
* **The one inferred idea worth building**: their micro-templates are an *output of verified data*.
  Our analogue, without humans in the loop, is the sealed adjudication store (§G 2.2) feeding
  classifier tests and reconstruction refusal analysis — labels drive tests and thresholds, never
  parsers.

---

## C. MONEYTHUMB COMPARISON (full detail in `research/MONEYTHUMB_MEMO.md`)

**Lineage and shape (DOCUMENTED).** Accountant converters (2015) → PDF Insights for lenders (2017) →
cloud (2018) → Thumbprint fraud (2020) → acquired by Iron Creek Partners (2024). A Java converter engine
shipped as desktop, on-prem "PDF Convert Server" and a hosted Insights API. Four input classes: text,
image/scanned, "searchable" (OCR-layer errors like "so" for "50") and encrypted. OCR is proprietary
"PinPoint", Windows-only on desktop. No human review service.

**Unknown layouts (DOCUMENTED).** "Our software doesn't need to be told upfront what bank statement
format is being used"; "over 99% of U.S. bank statements"; unlisted banks go to support. Generic knobs
exist (`spacingfactor`, account-boundary regexes, `combinelines`), plus validity flags `isHeaderValid`
("whether a header row was found") and `isColumnsValid`, and a failure diagnostic of the form "Found 100
lines with a date, 90 lines with a currency value, 80 lines with both". Thumbprint needs per-bank
baselines and warns that new templates score high "than warranted".

**Reconstruction and reconciliation (DOCUMENTED).** Polarity from statement sections with a
"switch signs" fallback; multi-line descriptions combined by rule; **the printed balance column is
deliberately ignored** by the converters ("QuickBooks will calculate the balance"); reconciliation is
`starting + deposits − withdrawals = ending` per account per statement with fields `reconciled`,
`balancesValid`, `endBalance` vs `endBalanceCalc`, `likelyMissingTransactions`, `alloweddiff` (a
tolerance knob, default 0); a `/updatesummary` endpoint lets the client overwrite the summary figures.

**The documented anti-pattern.** "If the statement does not reconcile, PDF+ will go back through the
statement looking for values that might have been missed"; `numTypos` counts "typos fixed by PDF+
PinPoint". STRONGLY INFERRED: OCR digits are changed until the totals reconcile and the count of changes
is reported as a quality metric. That is the validator-as-optimizer by name, and it explains both the
"95 % reconciliation rate" claim and the Trustpilot complaints about missing months and half-converted
statements.

**Where we resemble Ocrolus more than MoneyThumb.** Immutable evidence with page/box provenance;
classification and enumerated refusal reasons; account → period → transaction as a graph independent of
files; per-row running-balance validation; integrity checks as first-class outputs. **Where MoneyThumb
still teaches us.** Per-account-per-statement reconciliation objects with found-versus-computed
residuals; cross-statement continuity (`balance_match`, `month_gap`, `daysMissing`, duplicates); layout
telemetry as an explicit "layout unresolved" outcome (their date-line / currency-line / both counts are
a good structural-refusal diagnostic); OCR provenance on every number (`ocr`, `suspectCount`); the
Thumbprint idea that bank-agnostic *structural* features (font/position variance, producer metadata,
missing-page arithmetic) are evidence — for a later phase.

**What to avoid, explicitly.** Totals-only reconciliation (compensating errors pass); editing values to
reach reconciliation; tolerance knobs that rename the outcome; client-editable summaries without
attributed re-validation; scorecards on unreconciled statements; ADB with an undisclosed day basis
(their `avg_balance` sits next to business-day fields and must never be used to calibrate our
calendar-day ADB). Baseline hygiene for any future MoneyThumb comparison: compare only where
`reconciled=true`, `balancesValid=true`, `ocr=false`, `suspectCount=0`, `numTypos=0`.

---

## D. CURRENT CORPUS FAILURE TAXONOMY — what we know and what we must measure

### D.1 What the run of record already says (distinct SHAs; `memo:REPO_CORPUS §3.1`)

| outcome / reason | digital·native | scanned·Tesseract | mixed·Tesseract | no text | invalid | total |
|---|---:|---:|---:|---:|---:|---:|
| failed / no_parser_matched | 448 | 78 | 11 | | | 537 |
| failed / parser_declined | 85 | 33 | 1 | | | 119 |
| withheld / withheld_adb | 34 | 15 | | | | 49 |
| review / integrity_flags | 16 | 5 | | | | 21 |
| failed / invalid_pdf | | | | | 16 | 16 |
| deferred / deferred_visual_ocr | | | | 13 | | 13 |
| **total** | **583** | **131** | **12** | **13** | **16** | **755** |

Failure class B 656 / C 70 / none 29. Pages 5,110 (digital 4,513, scanned 545, mixed 52); median 5,
maximum 55; 118 single-page. Row-level Class A = 0; `evidence_quality = usable` on every Tesseract read.
Seven of the 755 are pinned-corpus documents with adjudicated fail-closed outcomes and must stay where
they are.

### D.2 What the batch-9 census adds (agent judgement over cached text, not verified per document; `memo:REPO_CORPUS §3.2`)

| census cluster | docs | what it means | current class |
|---|---:|---|---|
| FAM:* | 322 | unclaimed SHA under one of 91 batch-8 layout families (37 credit-union families = 176 docs) | B |
| DECL:* | 119 | a registration claimed at detection and `parse` returned None (core_processor_sectioned 22, huntington 12, lili 9, community_section 9, …) | B 116 / C 3 |
| NOT-STATEMENT | 117 | 104 "not statements" (a bare SHA list, no per-document reason) + 13 portal/range exports (described) — all digital, 61 of them 1–2 pages | B |
| SCAN-UNCLAIMED | 89 | scans Tesseract read that no reader claims: thin 51 (42 single-page; "screenshots, photos, partial pages"), medium 13, dense 25 ("a reader problem") | B |
| WH:* | 52 | ADB withheld (frost 9 = period not printed; rbc 6; southside 5; …) | C 49 / B 3 |
| RV:* | 18 | review: informal exports (chase_export 4, found_lead 3) and missing declared pages (11) | C |
| PF-INVALID-PDF | 16 | Java object-serialisation magic bytes, 0 pages — portal download artefacts, not documents | none |
| OCR-NEGATIVE | 13 | Tesseract produced no text (= R = deferred 13; 11 single-page; 17 pages) | none |
| TEXT-LAYER-DEFECT | 8 | subset fonts decoding to a substitution alphabet, digits included (RBC 4, Chase 1, …) | B |
| NO-TEXT | 1 | a digital PDF with 0 characters | B |

Two facts shape everything downstream. First, the archive's image files (png 68, jpg 36, jpeg 20) and
spreadsheets are outside the 3,380 by construction — only `.pdf` is enumerated — so every "voided
cheque / screenshot" inside the denominator is a PDF, most plausibly among the 51 thin scans and the
104 unexplained not-statements. Second, there is no document-type classifier, no text-layer-defect
detector, and no per-document reason for the 104 (`memo:REPO_CORPUS §5`).

### D.3 What must be measured (the gap this package closes)

1. **Document kind per SHA with named evidence** (the classifier, §J) — sealed by human adjudication
   for the 755, so the second denominator is *confirmed*, not inferred.
2. **Extraction quality per page per extractor** without ground truth (§H.4) — today the only gate is
   the parameter-free triad (no text / < 200 chars / all pages empty).
3. **Structural refusal sub-classes** (§I.6) — today Class B is one bucket of 656; the structurer's
   four refusal reasons are the only finer signal and they were last measured 2026-08-07.
4. **False accepts on real documents** — today measurable only on the 80 pinned SHAs inside the
   denominator; the holdout cage (§G 2.2) is the instrument.
5. **Per-document cost, bytes, GPU-seconds, RAM/VRAM** (§G 2.2 telemetry cell) — today only run-level
   peaks and synthetic Paddle figures exist (`memo:REPO_CORPUS §7`).

### D.4 The proposed layered reason vocabulary (OUR DESIGN CHOICE; final shape ruled at 2.2)

A document carries **one code per layer**, and the *primary* reason is the highest non-empty layer, so
"why does this file not validate" always has one defensible answer and the finer layers stay visible.

```
L0 FILE        FILE_INVALID (corrupt / not a PDF / 0 pages) · FILE_ENCRYPTED
L1 KIND        NOT_A_STATEMENT{sub_kind: cheque_image | voided_cheque | deposit_slip | letter_or_notice |
               card_statement | loan_statement | brokerage | tax_or_id | other_bank_doc | non_bank}
               · ACTIVITY_EXPORT (dated ledger without period/opening/closing anchors)
               · STATEMENT_PARTIAL{missing: pages | opening | closing | period | first_page | table_truncated}
               · STATEMENT_ILLEGIBLE{E-class} · KIND_UNCERTAIN
L2 EXTRACTION  (Class A) E0 no evidence · E1 coverage gap · E2 recognition quality · E3 frame/orientation
               · E5 truncation/bleed — per extractor attempted; E4 cross-engine disagreement is review evidence
L3 STRUCTURE   (Class B) B1 no table region · B2 column model unresolved (role_conflict | straddle |
               too_few_members | header_absent_and_unconfirmed) · B3 records unassembled (orphan_amount |
               continuation_ambiguous | two_dates_in_row) · B4 summary anchors not found (period |
               opening | closing) · B5 account partition ambiguous · B6 cross-page continuity broken
               · B7 grounding failed · B8 sign undeterminable
L4 FINANCIAL   (Class C) the existing W3-2 classes unchanged: source_contradiction · period_integrity ·
               summary_field_missing · summary_identity · detail_coverage · posting_date_coverage ·
               balance_continuity · ledger_identity · daily_ledger_structure · page_coverage · adb_not_computable
L5 DOCTRINE    Q3/sibling-omission refusal · currency/package refusal · not_a_formal_statement ·
               declined_by_claiming_reader (until R13 is ruled) · pinned adjudicated refusal
L6 UNKNOWN     the taxonomy saw nothing — itself a finding, never nulled
```

This maps the brief's suggested list one-to-one (NOT_A_BANK_STATEMENT → L1, INCOMPLETE_STATEMENT →
L1 STATEMENT_PARTIAL, UNREADABLE → L0/L1 ILLEGIBLE, EXTRACTION_FAILURE → L2, STRUCTURAL_FAILURE → L3,
FINANCIAL_RECONSTRUCTION_FAILURE → L4, ACCOUNT/PERIOD/CURRENCY_FAILURE → L4/L5, INTEGRITY_FAILURE →
L4, UNKNOWN → L6) while keeping "unreadable file" and "illegible statement" apart, because one is a
transport artefact and the other is a legitimate customer document that needs a better extractor.

---

## E. COMPLETE RECOMMENDED PHASE 2 ARCHITECTURE

### E.1 End-to-end diagram

```
                                   PDF bytes (content sha)
                                            |
                          inspect_and_profile  (existing; ocr/inspect.py)
                          + NEW: native-layer probes: cid/garbage ratio, vowel share,
                            money-shape parse rate, image-backed text layer, /Rotate    ------ L0 FILE codes
                                            |
                 +--------------------------+---------------------------+
                 | native text present                                  | image-only / mixed pages
                 v                                                      v
   NATIVE EXTRACTOR (PyMuPDF words)                    LOCAL TESSERACT (text; $0, first image rung)
   -> ExtractionEvidence (NEW: sha recorded,           -> text evidence  (boxes: deferred option)
      rotation applied to display frame)                                |
                 |                                                      v
                 |                                    EscalationRouter (existing; verdict-blind)
                 |                                      admitted triggers only (pre-financial):
                 |                                      R image-only · U-extract · NEW measured:
                 |                                      native_text_unreliable · image_backed_text ·
                 |                                      orientation_anomaly · E-gate v2 classes
                 |                                                      |
                 |                                                      v
                 |                                    PADDLEOCR PP-OCRv5 (primary visual extractor;
                 |                                    Vast remote_paid under authorization, or local_free)
                 |                                    -> ExtractionEvidence (immutable, per-page frames)
                 |                                                      |
                 |                                                      v  (E0–E3 only; go/no-go; own ruling)
                 |                                    UNLIMITED OCR (generative; region sidecar, no word boxes)
                 |                                    -> ExtractionEvidence(words=(), regions, raw text)
                 |                                                      |
                 +------------------------+-----------------------------+
                                          v
                        ExtractionQualityGate v2 (existing gate + NEW measured E-metrics)  --- L2 codes
                                          |  usable
                                          v
                        DOCUMENT CLASSIFIER (NEW, layout/document_class.py; deterministic tier-1;
                        runs at every rung on the best evidence; never edits the denominator)  --- L1 codes
                                          |  STATEMENT_* or KIND_UNCERTAIN
                                          v
                        DocumentGeometry (existing; lines of words; one grouping rule)
                                          |
                                          v
                        LAYOUT MODEL (NEW package layout/: furniture, continuity, regions, columns,
                        records, sections, accounts, summary blocks; word-id provenance;
                        closed refusal vocabulary B1–B8; byte-stable JSON; RECON_PARAMS_VERSION) --- L3 codes
                                          |
                    +---------------------+----------------------+
                    | registry claims (84 readers, unchanged)    | unclaimed (and, if R13 rules, declined)
                    v                                            v
          PHASE 1 PARSERS -> Statement(s)             STRUCTURER v2 (analysis/structurer, consumes the
          (+ bank repairs, as today)                  LayoutModel; ONE candidate out or a named refusal;
                                                      no oracle inputs; grounding v2 on word ids)
                    |                                            |
                    +---------------------+----------------------+
                                          v
                        THE SAME DETERMINISTIC VALIDATOR (reconcile · adb · integrity · quality ·
                        multi-account independence · package) — unchanged; grants `validated`      --- L4/L5 codes
                                          |
                    validated -> STOP      |      withheld / review / refused -> review or refuse; NEVER an extractor
                                          |
                        publish with evidence_refs[] (page, word ids, evidence sha) -> UI / packages / audit
                                          |
                        TELEMETRY: funnel stages, both denominators, cost/bytes/GPU-s/RAM/VRAM,
                        unresolved taxonomy L0–L6, holdout false-accept report
```

The only edges that start an extractor come from the profile, the quality gate or an operator's
research-mode constant. The classifier can refuse (a cheque image is not sent to Paddle); it cannot
start an extractor. The LayoutModel and the structurer cannot see reconciliation, ADB or printed totals.
The validator cannot see the router. Those four "cannot"s are tripwires, not comments (§E.4).

### E.2 Components and ownership

| Component | Status | Package | Owner cell | Notes |
|---|---|---|---|---|
| intake profile + native-layer probes | extend | `ocr/inspect.py` | 2.2-K | probes are pre-financial facts about the text layer, recorded on the row; not triggers until measured (Ruling B discipline) |
| native evidence with sha + display frame | extend | `ocr/native_text.py`, `analysis/structurer/geometry.py`, `evidence/` | 2.2-K | closes two of the five Phase 2.1 prerequisites (§Q) |
| geometry-aware analysis key | fix | `webapp/artifact_cache.py`, `telemetry/run_of_record.py` | 2.2-K | the third prerequisite; blocks any cached geometry-fed run |
| document classifier | new | `layout/document_class.py`, `layout/signals.py` | 2.2-C | deterministic tier-1; sub-kinds; completeness findings; evidence refs; KIND_UNCERTAIN allowed |
| unresolved taxonomy + funnel + cost telemetry | new | `telemetry/unresolved_taxonomy.py`, `discovery/report.py`, `rows.csv` columns | 2.2-T | L0–L6; both denominators; per-document bytes/GPU-s/VRAM/RAM |
| holdout cage + sealed adjudication store | new | `tools/holdout/`, `tools/adjudicate.py` | 2.2-H | outside the corpus; leakage firewall tripwire |
| research run mode + customer-data authorization wiring | new/config | `discovery/runner.py`, `ocr/paddle_config.py`, runbook, PHASE2_RULINGS.md | 2.2-A | mode constant; research cache partition; the second literal set only per run |
| extraction-quality gate v2 | extend | `ocr/extraction_quality.py`, `ocr/escalation.py` | 2.3-W | E-metrics measured first, admitted as triggers only in 2.5 |
| Paddle wave runner + agreement instrument | new | `tools/paddle_wave.py`, `layout/agreement.py` | 2.3-W, 2.3-X | resumable; per-page telemetry; native↔Paddle alignment |
| LayoutModel | new | `layout/` (stdlib + `evidence` only) | 2.4-L1 | §I |
| structurer v2 | rewrite of `rows.py`, extend `core.py`/`summary.py`/`grounding.py` | `analysis/structurer/` | 2.4-L2 | consumes LayoutModel; emits Statement(s) + partition + scopes + posting-date block |
| synthetic layout archetypes + mutation tables | new | `tests/layout_synthetic/`, `tools/layout_mutation_table.py` | 2.4-S | the test bed (real statements may never be fixtures) |
| production wiring of geometry | wire | `analysis/pipeline.py`, `discovery/runner.py`, `webapp/worker.py` | 2.4-R | `reconstruction_mode ∈ {off, research, production}` in the settings key |
| measured production triggers + page-level routing + disagreement → review | extend | `ocr/escalation.py`, `discovery/runner.py` | 2.5-P2 | each trigger with labelled evidence + mutation table |
| evidence_refs lineage | new | `analysis/serialization.py`, `webapp/` | 2.5-D | fail-closed on unbacked fields on the generic path |
| Unlimited extractor + region sidecar | new (gated) | `ocr/unlimited_rung.py`, `evidence/` (regions) | 2.6-U1 | only after the spike and a ruling |
| routing freeze, dashboards, Phase 3 seam | docs/config | `docs/`, `telemetry/` | 2.7 | `ReconstructionRequest/Result` pinned |

### E.3 Is DocumentGeometry the right abstraction? (brief §11, §27 Q9)

Yes, as the **evidence-side** representation, and it should not grow semantics. What it is today —
pages of visual lines of words with boxes in one declared frame, produced by exactly one grouping rule
from either native or Paddle evidence, byte-identical to Phase 2.0 on 830 pages (`memo:REPO_GEOMETRY
§2`) — is precisely the neutral input a layout algorithm wants. What it lacks (rows, columns, regions,
tables, headers, cross-page and account notions) belongs in a separate **understanding-side**
representation, the LayoutModel, because those are *inferences with refusal states*, not evidence.
Keeping them apart is what lets the same LayoutModel code run on native and Paddle geometry, lets Phase
3 consume geometry without inheriting our inferences, and keeps the "one grouping rule" tripwire
meaningful.

Three concrete evolutions of DocumentGeometry are recommended, all additive: (1) carry `word_id` and
`line_ref` through to `GeoLine.words` so LayoutModel provenance is by id, not by offset; (2) carry the
frame's rotation *applied* (display frame) with `rotation_deg` recorded; (3) optionally carry the page's
vector ruling lines from native PDFs as a separate `rules[]` list (an extra alignment-edge source;
pdfplumber's `lines` strategy) — never required. The three parallel geometric readers that exist today
(`ocr/column_grid.py`, `ocr/native_text.py::parse_native_printed_rows`, the structurer) are not
unified by force: their *mechanisms* (header-named bands, right-edge money snapping, anchor-to-anchor
rows, split-cell refusals) are re-implemented as pure functions in `layout/`; the per-bank native rungs
keep their code paths because the import boundary forbids `ocr → analysis` and the analysis allowlist
is pinned empty (`tests/test_escalation_tripwires.py:52`).

### E.4 The anti-optimizer rule, made structural for the new layer (brief §16)

Formal rule: **no decision inside classification, layout or reconstruction may be conditioned on a
document-level oracle** (opening/closing identity, printed totals, printed counts, printed ADB, the
daily grid). Those belong to the validator. Layout and reconstruction may use **table-local
regularities only**: x-alignment, header semantics, section headings, adjacent-row balance deltas,
date monotonicity, page-continuity markers. If table-local evidence leaves more than one admissible
structure, the module **refuses with the ambiguity named** (B2/B3/B5/B8). It never returns a list of
candidates for something downstream to try.

Enforcement (each is a test, and each gets a mutation-table entry):

1. `layout/` imports only the standard library and `evidence`; `analysis/structurer` imports `layout`
   but never `analysis.reconcile`, `analysis.adb`, `analysis.metrics` (AST tripwire, like
   `tests/test_evidence_boundary.py`).
2. The LayoutModel builder and the structurer's table-role and record-assembly functions have
   signatures with **no summary, totals, counts or grid parameters** (signature pin, like
   `RouterInputs`).
3. The public surface stays `structure_unclaimed(...) -> Statement | DocumentPartition | None` — one
   candidate out; a `list` return type is a red test.
4. Sign provenance is tiered and recorded per row: **Tier 1** debit/credit column band or section
   heading (independent of arithmetic); **Tier 2** chain-derived sign corroborated by a printed
   per-direction total or count that the validator will check; **chain-only** signs with no
   corroboration available on the document → the candidate is emitted with `direction_provenance =
   chain_only` and the validator's existing gates decide — the plan additionally proposes (as a
   protected-module ceremony, R14) an integrity flag when *every* sign is chain-derived and no
   independent direction evidence exists, because in that case `opening + Σsigned = closing` is
   tautological and only the printed closing-versus-last-row check and the amount-versus-delta
   agreement remain independent.
5. The existing Ocean-approved chain test (one fixed hypothesis "last money token is the balance",
   accepted only at ≥ 90 % agreement over ≥ 5 rows) is the pattern to keep: a *single-hypothesis
   corroboration* on many rows, never a search over full interpretations.
6. Two pre-existing sites are named in the risk register (§M) and get rulings (§N R9, R10): the
   hosted-extraction selection in webapp auto mode that "prefers whichever extraction's summary
   reconciles" (`analysis/pipeline.py:940-990`), and the six bank-keyed `bank_repairs.py` rewrites that
   predate the repair doctrine. Neither can reach the generic branch today
   (`analysis/pipeline.py:906-912` skips repairs on it); the tripwire pins that.

### E.5 The Phase 3 seam (brief §25)

Phase 3 is not built here, but the seam is pinned in 2.4 and documented in 2.7 so nothing has to be
thrown away:

```python
@dataclass(frozen=True)
class ReconstructionRequest:      # what any producer — deterministic today, evidence-grounded model later — receives
    evidence: ExtractionEvidence                # immutable words/boxes/frames (or regions), sha'd
    geometry: DocumentGeometry                  # one grouping rule
    layout: LayoutModel | None                  # the deterministic layer's understanding, with refusals
    document_class: DocumentClass               # kind, sub-kind, modality, completeness findings
    page_rasters: tuple[RasterRef, ...]         # sha + dpi (+ retained PNG only in research partitions)
    context: ReconstructionContext              # prior refusal codes (L1–L3), settings key, provenance
@dataclass(frozen=True)
class ReconstructionResult:
    candidate: Statement | DocumentPartition | None
    evidence_refs: Mapping[FieldPath, tuple[WordRef, ...]]   # every published figure -> word ids / raw span
    refusal: RefusalCode | None                # closed vocabulary
    producer: ProducerIdentity                 # deterministic structurer v2 today
```

The structurer v2 implements this; a future model would implement it too and would still hand a
`Statement` to the same validator, with `evidence_refs` that grounding v2 checks against the same word
boxes. What Phase 3 needs that Phase 2 must therefore keep: persisted page rasters (a research
partition policy, §G 2.3), word-id provenance end to end, and a cache key that describes geometry- and
image-fed analysis (2.2-K).

---

## F. REVISED REMAINING PHASE 2 MILESTONES

### F.1 Why the old decomposition changes

The accepted plan's 2.2 (geometry experiments) → 2.3 (Unlimited) → 2.4 (page routing) → 2.5
(productionisation) was written before three things were known: that 77 % of the residue is native-text
Class B; that no classifier, no taxonomy and no holdout exist; and that Gustavo wants a broad, measured
Paddle evaluation rather than the 13-document population. Two milestones are therefore inserted in front
(truth instruments; the evidence wave), reconstruction is split into a v1 that must prove generality
before hardening, Unlimited becomes go/no-go, and page-level routing folds into the milestone that
admits Paddle triggers into production, where it belongs.

| old | new | what moved |
|---|---|---|
| — | **2.2 Truth instruments** | new: classifier, taxonomy, holdout, telemetry, key/frame fixes, research mode |
| — | **2.3 Broad Paddle evidence wave** | new: the brief's §5/§12/§13 measurement, +0 official coverage |
| 2.2 geometry experiments | **2.4 Generalized reconstruction v1** | same intent, now with a LayoutModel, synthetic archetypes, holdout, and admission of native-geometry gains |
| 2.4 page routing / mixed / disagreement | **2.5 Reconstruction v2 + Paddle production admission** | plus measured triggers and evidence_refs |
| 2.3 Unlimited | **2.6 Unlimited (go/no-go)** | moved after the measurements it depends on |
| 2.5 productionisation | **2.7 Phase 2 closure** | routing freeze, Phase 3 seam, tag |

### F.2 Sequencing rules

* One train per milestone (`train12` … `train17`), each from `origin/main` at the previous tag; cells
  on disjoint file ownership; Ocean composes and merges; every cell gets an independent adversarial
  review in the Fable 5.1 environment (roles and independence per `ORCHESTRATION-MODEL-POLICY.md`).
* Every milestone ends with the batch-9 floor (full suite, 5 guard files, 7 conformance files, corpus
  gate GREEN, cohort replay, privacy scan 0, message scan 0), a cold run versus the previous run of
  record with `--fail-on-regression`, CI green with its run id read, docs durable, then STOP and a
  closure report.
* 2.3 may open the day 2.2's gate is met (its code lands in 2.2; 2.3 is a run and a measurement). 2.4
  may not open until 2.3's truth table exists, because the archetype set and the refusal sub-classes are
  derived from it. 2.6 opens only if its go/no-go threshold (§K) is met; otherwise it closes as
  "deferred with evidence" and 2.7 follows.
* Research partitions never become the run of record; a research-validated document is *named*, never
  *counted*, until the routing that produced it is admitted.

---

## G. MILESTONE CARDS

Each card follows the house umbrella format (objective → baseline → cells → design decisions →
contracts → tests/mutation/tripwires → corpus measurement → performance/cost → floor → adversarial
review → completion gate → exclusions → dependencies). Numbers marked *baseline* are the Phase 2.1
run-of-record values and will be re-verified before each train opens.

### G.2.2 — TRUTH INSTRUMENTS

**Objective.** Make the rest of Phase 2 measurable and honest before any customer page leaves the
machine: a document classifier with named evidence, the layered unresolved taxonomy and both
denominators, the holdout cage and a sealed adjudication store, funnel and cost telemetry, the three
cache/frame prerequisites, and the research run mode that 2.3 will execute. Expected coverage movement
**+0**; OCR-fed validated **0**; nothing remote.

**Inputs.** `phase2.1-final`; the Phase 2.1 cold run and its read-only cold cache; the batch-9 census
(`census_batch9/per_sha.csv`) as a *comparison*, never as truth; Gustavo's §6 authorization text.

**Outputs.** `layout/` package (classifier only at this milestone), `telemetry/unresolved_taxonomy.py`,
new `rows.csv` columns (`document_class`, `class_sub_kind`, `class_evidence`, `class_tier`,
`completeness_findings`, `reason_l0…l6`, `stage_*`, `bytes_up`, `bytes_down`, `gpu_ms`, `peak_rss_mb`,
`vram_mb`, `cost`), the holdout manifest and adjudication CLI, the research run mode, the ruling
recorded, the corpus truth table v0 (classifier-only, unadjudicated) and v1 (first adjudicated slice).

**Architecture / cells (disjoint ownership).**

* **Cell K — keys and frames.** (a) `analysis_input_sha` gains the evidence identity: for a
  geometry-fed analysis the key includes `evidence_sha256` and `reconstruction_mode`; for a text-only
  analysis it includes the literal `no-geometry`; `ANALYSIS_STAGE_VERSION 17 → 18` in the same commit
  as its pin; `telemetry/run_of_record.py` learns the new partition. (b) The native rung builds
  `ExtractionEvidence` from PyMuPDF words once per document, records `evidence_sha256` in the OCR
  record's existing `evidence` field (schema 2 already carries it; a native `extractor_id` token is
  added to the closed vocabulary) — the ~2.7× recomputation disappears because evidence is built once
  and the sha is computed once. (c) Rotation: native word boxes are transformed into the display frame
  with the page's rotation matrix; `PageFrame.rotation_deg` records what was applied; a `pdf_point`
  frame gains the bounds check pixel frames already have; synthetics at 0/90/180/270 pin it; a
  read-only census of `/Rotate` over the 755 and the 2,625 is reported.
* **Cell C — document classifier v1** (`layout/signals.py`, `layout/document_class.py`): deterministic
  tier-1 only (§J). Input: `ExtractionEvidence` (native or Paddle) or, for Tesseract-only pages, page
  text in a declared degraded mode. Output: `DocumentClass{kind, sub_kind, modality, language,
  completeness: tuple[Finding,...], evidence: tuple[WordRef|SpanRef,...], tier ∈ {structural, lexical,
  uncertain}}`. Wired into `discovery/runner.py` as a recorded fact only — no routing change in 2.2.
* **Cell T — taxonomy and telemetry** (`telemetry/unresolved_taxonomy.py`, `discovery/report.py`,
  `tools/train8_compare.py`): the L0–L6 vocabulary with drift guards in the W3-2 idiom; the two
  denominators in `summary.json` and the report; funnel columns; per-document bytes/GPU-ms/VRAM/RSS
  from the Paddle client's existing per-request timing (today measured only by `paddle_vast measure`);
  cost from a ruled rate or the literal `rate not measured`; a new terminal outcome `refused`
  (reason-coded) that is *unranked* against failed/withheld/review in `discovery/compare.py` but is a
  **regression when a validated SHA moves into it** (the validated set is protected in every direction).
* **Cell H — holdout cage and sealed adjudication store** (`tools/holdout/`, `tools/adjudicate.py`):
  the §12 manifest schema of the accepted architecture (holdout_id, sha, strata, layout_family code,
  human oracle fields, status unseen/evaluated/burned/graduated), stored outside the repository at a
  path known only through `HOLDOUT_STORE_DIR`; the adjudication CLI renders pages locally, asks the
  human for kind/sub-kind/completeness and the five oracle figures (account count, printed period,
  opening, closing, printed transaction count) plus three random rows, and appends an immutable,
  timestamped record keyed by sha; a leakage firewall: an AST tripwire that no module under `analysis/`,
  `layout/`, `ocr/`, `evidence/`, `discovery/` references the store path or environment variable, and
  a test that the store is not importable from those packages.
* **Cell A — authorization and research mode.** The §6 ruling recorded verbatim in
  `PHASE2_RULINGS.md` §"Phase 2.2–2.7" with its operational scope (populations, retention, lifecycle,
  provenance ruling id); the runbook's data-boundary section rewritten; `discovery --research-paddle
  --population <sha-list> --research-partition <id>`: `enabled = {"paddle"}` as a MODE constant (the D4
  tripwire stands), forced path, a research cache directory that `run_of_record` refuses to treat as a
  run of record, `data_scope="customer"` declared, both literals required from the process environment,
  never from a tracked file; the mode is proven end to end on synthetic fixtures in 2.2 (no customer
  page leaves in 2.2). Also in this cell: the `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` literal remains
  absent from every test environment (existing assertion kept).

**Material design decisions (expected → changed → why → risks → tests).**

* D1 *Classifier placement.* Expected: `ocr/` or `analysis/`. Changed: the neutral `layout/` package
  (stdlib + `evidence`). Why: the classifier reads evidence from any extractor and its verdict is
  consumed by both the ladder (refusal before a paid rung) and analysis (formal-statement semantics);
  neither side may import the other. Risk: a third home for lexicons. Test: import tripwire.
* D2 *Classification never edits the denominator.* Expected: a "not a statement" list removes documents
  from coverage. Changed: `refused` is an outcome; the raw denominator stays 3,380; the CCL denominator
  is computed from sealed adjudications only. Test: `summary.json` carries both, and the compare tool
  refuses a base/candidate pair whose raw denominators differ.
* D3 *Adjudication is sealed and one-way.* Labels never feed code; they feed tests and reports; a
  document that changes a threshold or a rule is marked `burned`. Test: the firewall tripwire.
* D4 *Native evidence is persisted, not recomputed.* The OCR artifact for a native document carries its
  evidence (raw words, frames, sha); `to_markdown()` stays byte-identical (the committed corpus
  artifacts pin it); the offline OCR partition is rebuilt at the train's cold run (~74 min, acceptable).

**Tests.** Classifier: a synthetic corpus of cheque images, voided cheques, deposit slips, activity
exports, card statements, letters, partial statements (pages removed, opening removed, closing
removed), complete statements in EN/FR/ES, rotated pages, screenshots-as-PDF — every one refuses or
classifies with named evidence; a KIND_UNCERTAIN case exists and is asserted. Taxonomy: drift guards
that fail when `analysis/`, `ocr/` or `layout/` grow a code the vocabulary does not know; the
precedence table asserted equal to the code. Keys: two analyses of identical markdown, one with and one
without evidence, produce different keys; a schema-1 record restored from cache still analyses. Frames:
rotation synthetics at four angles round-trip byte-identically through `geometry_from_evidence`; an
out-of-bounds `pdf_point` box is refused. Research mode: refuses without both literals; refuses in auto
mode; writes only to the research partition; `run_of_record` never selects it; the D4 AST tripwire
still passes.

**Mutation / tripwire tables.** One mutant per classifier gate (drop the MICR rule → the cheque fixture
must stop refusing; drop the `Page X of Y` rule → the partial fixture must stop finding its gap; invert
the period rule → the complete fixture must become UNCERTAIN); one per key field (remove
`evidence_sha256` from the key → the "different keys" test must fail); one per firewall edge (add a store
import to `layout/` → tripwire must fail); one per research-mode refusal (drop one literal → the
refusal test must fail). Every mutant applied as documented, killer named, tree restored.

**Corpus measurement (offline, existing evidence).** Classifier over all 3,380: every validated SHA must
classify `STATEMENT_COMPLETE` (any exception is a classifier defect or a finding, reported by SHA);
agreement with the census NOT-STATEMENT list (117) and the portal-export list (13) reported as
agreement, never adopted; the first adjudication slice = the 117 + the 51 thin scans + the 13 exports +
the 16 invalid files + a random 30 of the FAM cluster (≈ 227 documents) → truth table v1 with the
classifier's precision/recall on that slice. Rotation census. Funnel columns populated for the existing
ladder (Paddle stages `not_attempted`).

**Performance / cost.** Classifier < 50 ms per document on native evidence (pure Python over words);
native evidence build once per document (replaces the 2.7× recomputation); cold run peak RSS must stay
within the 2.0 GB floor / 4 GB cap; $0.

**Regression floor.** 2,625 preserved, payload-identical on the offline partition (cohort replay
`--expect-identical` at base and closure); newly validated 0; OCR-fed validated 0; gate 105/3/1; CI
green.

**Adversarial review (attack list).** Can a classification label ever change a financial verdict? Can
the sealed store be reached from any production import? Is the new key over-partitioning safe and
under-partitioning impossible? Does the native evidence build change any markdown byte? Do the
rotation transforms agree with Poppler's display orientation on the same page? Does the research mode
have any path into auto mode or into the run of record? Are any statement literals in the lexicons
(OQ2 guard extended to `layout/`)?

**Completion gate.** All cells reviewed → closed → re-reviewed; floor green; cold run 2,625 → 2,625;
classifier measured with the slice-1 truth table published; holdout manifest schema and CLI proven on
synthetic pages; the ruling recorded; research mode proven synthetic-only; docs durable; STOP; closure
report; 2.3 requests the go.

**Explicit exclusions.** Any Paddle run on customer data; any routing change from classification; any
ML classifier tier; structurer enablement; Unlimited; PP-OCRv6; new parsers; page-level routing;
evidence_refs on published values; a `local_free` install.

**Dependencies.** None beyond `phase2.1-final`.

---

### G.2.3 — BROAD PADDLE EVIDENCE WAVE

**Objective.** Give PaddleOCR its controlled, explicit opportunity (brief §5, §12, §13): read every
unresolved page and a validated control sample on the approved Vast RTX 5090, store immutable evidence
in a research partition, measure extraction quality without ground truth, measure native↔Paddle
agreement, re-classify scans on real word evidence, seal the corpus truth table, and record the first
stage-by-stage fallout using the existing structurer as the baseline reconstruction. Expected official
coverage movement **+0** (research-validated SHAs named, not admitted).

**Inputs.** 2.2's instruments; the §6 ruling as recorded; the population lists: `U755` (all
unresolved SHAs, 5,110 pages), `CTRL` (a stratified control sample of validated documents: all 36
Tesseract-validated scans + 114 native-validated documents stratified by layout family and page count
≈ 150 documents, ≈ 1,000 pages), and `SLICE` (the 34-document corpus slice already used for Paddle
synthetic proofs, for the optional configuration A/B).

**Outputs.** Research partition `research/paddle-v5-prod/` (the pinned production configuration) with
one immutable `ExtractionEvidence` per page; optional partitions `research/paddle-v5-orient/`
(orientation classifiers on) and `research/paddle-v6-medium/` (only if R5 is ruled); the E-metric
census; the agreement report; the truth table v2 (classifier on Paddle evidence for scans + the second
adjudication slice); the baseline fallout table; the cost report with the ruled rate; the retention
attestation.

**Architecture / cells.**

* **Cell W — wave runner and E-gate v2** (`tools/paddle_wave.py`, `ocr/extraction_quality.py`):
  resumable by SHA; instance up → tunnel → identity verified against the pins → pages sent one at a
  time (existing bounds) → evidence stored → per-page `bytes_up/bytes_down/inference_ms/vram_sample`
  written to rows → instance stopped. E-metrics per page: word count and density; rec-score
  distribution (mean, p10) *calibrated per configuration*; money-shape parse rate over numeric tokens;
  lexicon rate over alphabetic tokens (EN/FR/ES); garbage-token rate (> 20 chars, repeated letters);
  box regularity (line-height CV; numeric right-edge residual in character widths); ink-versus-box
  coverage from the raster (share of dark pixels outside any word box); orientation votes. These are
  **measured and versioned, not admitted as triggers** in 2.3 (Ruling B's discipline: labelled
  evidence first, then review, then admission in 2.5).
* **Cell X — agreement and geometry census** (`layout/agreement.py`): for every page with both native
  and Paddle words, greedy IoU ≥ 0.5 alignment after frame normalisation; matched ratio each way;
  normalised character agreement on matches; exact agreement of parsed amounts and dates; unmatched
  density inside candidate table regions; page-size, rotation and skew census. On the control sample
  this yields the calibration of "what agreement looks like on known-good documents".
* **Cell V — configuration A/B (only if R5/R6 are ruled)**: a second pinned configuration
  (`use_doc_orientation_classify=True`, `use_textline_orientation=True`) on the scanned/mixed
  population, and `PP-OCRv6_medium` versus `PP-OCRv5_server` on `SLICE` + a 200-page stratified sample.
  Each configuration is its own pin block and partition; the production pin does not change in 2.3.
* **Cell B — baseline fallout**: the existing structurer (opt-in, research partition, geometry from
  native and from Paddle evidence separately, `reconstruction_mode=research`) over `U755`, producing
  the first funnel table E → G → L (existing `rows.py`) → C → V per geometry source, with every
  research-validated SHA named and every refusal coded; on `CTRL`, the Paddle-path candidate's key
  fields (opening, closing, count, Σ) compared to the recorded validated payload — any disagreement is
  a *false-accept candidate* sent to adjudication.
* **Adjudication slice 2**: every document whose classifier verdict changed between Tesseract text and
  Paddle evidence, every KIND_UNCERTAIN, every false-accept candidate, and a random 50 of the rest.

**Material design decisions.**

* D1 *Research partitions are immutable and excluded from the run of record by construction* (a
  partition id in the OCR settings key plus `run_of_record`'s refusal); a research evidence file is
  never rewritten; a second run with the same configuration is a cache hit with sha equality asserted.
* D2 *Page rasters are retained in the research partition* (PNG at 300 dpi, sha-named, gitignored, under
  the same retention rule as the archive) so 2.4's LayoutModel and a future Phase 3 can be measured on
  the same pixels without re-rasterising; production partitions keep only `raster_sha256` as today.
* D3 *Control sample first.* The wave runs `CTRL` before `U755`, so the agreement baseline and the
  false-accept instrument exist before any unresolved document is read.
* D4 *Every page is attempted or refused with a reason* (E0 with the worker's error class); no silent
  skips; the escalation count equals the population size by construction.
* D5 *Cost is computed, never estimated*: GPU-seconds from worker wall time × the ruled rate; if the
  rate is not ruled, the report prints `rate not measured` and the GPU-seconds.

**Tests.** Runner resumability and idempotence on the fake worker; every E-metric on synthetic pages
with known defects (blank page, half-covered page, 90° page, noise page, a page with digit-like glyph
substitution); agreement on synthetic native+raster pairs (identical → 1.0; shifted → known drop;
perturbed amounts → exact-agreement drop); the research partition's exclusion from `run_of_record`;
the retention attestation test (the worker's `/version` reports `retention: none` and the lifecycle
tool's stop leaves no files on the instance — proven on the real instance during the wave, recorded in
the closure).

**Mutation tables.** Each E-metric threshold has a mutant that must be caught by its synthetic; the
partition-exclusion rule has a mutant (drop the research id from the key → the exclusion test fails);
the "attempted or refused" invariant has a mutant (skip on exception → the population-count test
fails).

**Corpus measurement (the deliverable).** Per document and per page, in `rows.csv` and the report:
Paddle attempted / evidence produced / E-gate v2 pass; agreement statistics; classifier verdict on
Paddle evidence; funnel stages for the baseline structurer on both geometries; research-validated SHAs
(named); false-accept candidates (named, adjudicated); the **corpus truth table v2**:

```
3,380 raw = 2,625 validated + 755 unresolved
755 = FILE_INVALID a · NOT_A_STATEMENT b (by sub-kind) · ACTIVITY_EXPORT c · STATEMENT_PARTIAL d (by missing element)
    · STATEMENT_ILLEGIBLE e · STATEMENT_COMPLETE f · KIND_UNCERTAIN g            (adjudicated: yes/no per SHA)
CCL = 2,625 + f (+ the adjudicated share of g)
for the f complete legible statements: E-class / B-class (B1..B8) / C-class / doctrine, per geometry source
```

**Performance / cost.** Expected volume ≈ 5,110 + ≈ 1,000 control (+ ≈ 600 orientation pages, + ≈ 250
A/B pages if ruled) ≈ 7,000 pages; at the synthetic warm median of 1.9 s/page (real pages are denser;
budget 3 s) ≈ 4–6 GPU-hours serial; ≈ 340 KB up and 12 KB down per page ≈ 2.4 GB up; the VRAM footprint
measured at 7.7 GB of 32 GB; local peak RSS measured with `psutil` installed (the "not measured" fallback
is retired). Cost = GPU-hours × the ruled rate.

**Regression floor.** The production run of record is untouched by construction (no production
partition is written); the floor is re-proven by the train's cold run (2,625 → 2,625) because the 2.2
code composes on the same train sequence; gate 105/3/1; CI green.

**Adversarial review (attack list).** Can any research artifact be selected by a production replay?
Does any page leave the machine without both literals in the process environment of *that* run? Does
any log, row or report carry document text (privacy scan over the wave outputs)? Are the E-metrics
parameter-free where the doctrine requires, and are the thresholds versioned where they are not? Is the
control sample's "false-accept candidate" logic itself blind to the validated payload until
comparison? Does the retention attestation actually inspect the instance?

**Completion gate.** Every page of `CTRL` and `U755` attempted-or-refused; the truth table v2 published
with adjudication status per SHA; the agreement and E-metric reports published; the baseline fallout
table published with named research-validated SHAs and zero *admitted* coverage movement; cost and
privacy attestations recorded; floor green; STOP; closure report; **2.4 requests the go with the
archetype list derived from the B-class fallout.**

**Explicit exclusions.** Any production routing change; admission of any E-metric as a trigger;
structurer changes; a production pin change (v6 or orientation) — those are separate partitions with
their own ruling; Unlimited; new parsers; running the wave in auto mode; sending any page without the
recorded ruling.

**Dependencies.** 2.2 complete; R1 (scope recorded) and R2 (rate) ruled; R5/R6 optional.

---

### G.2.4 — GENERALIZED RECONSTRUCTION v1 (the LayoutModel)

**Objective.** Turn words and coordinates into financially neutral structure without a parser per bank:
the `layout/` package (furniture, continuity, regions, columns, records, sections, accounts, summary
blocks; word-id provenance; closed refusals B1–B8) and a structurer v2 that consumes it and hands the
SAME validator one candidate or a named refusal — on native geometry and on Paddle geometry alike.
Coverage movement: **native-geometry gains admitted** (the unclaimed branch in `reconstruction_mode =
production`); **Paddle-fed gains named, pending 2.5's routing admission.** This is the strategic
milestone; it carries the accepted plan's rule: if the layout model does not move documents through
the gate, STOP and report rather than write parsers to hide the result.

**Inputs.** 2.3's truth table v2 and B-class fallout (the archetype list is derived from it: which
layouts are two-money-column, single signed column, sectioned, check-grid, multi-account, French,
daily-grid-bearing, page-break-continued); 2.2's holdout cage (first unseen batch provisioned per R4);
research partitions with retained rasters.

**Outputs.** `layout/` (≈ 10 modules, §I), structurer v2, the synthetic archetype generator and
mutation tables, production wiring of geometry, the fallout table v3 on both geometries, the first
holdout pass, the admitted native-geometry newly-validated set (named by SHA with evidence refs).

**Architecture / cells.**

* **Cell L1 — LayoutModel** (`layout/normalize.py`, `lines.py` (delegates to `evidence.group_lines`),
  `furniture.py`, `continuity.py`, `regions.py`, `columns.py`, `records.py`, `roles.py`,
  `sections.py`, `accounts.py`, `summary_blocks.py`, `model.py`, `refusals.py`, `params.py` with
  `RECON_PARAMS_VERSION`). Pure functions of `DocumentGeometry`; byte-stable JSON; every cell carries
  word ids; every threshold in one versioned module; no randomness. Algorithms in §I.
* **Cell L2 — structurer v2** (`analysis/structurer/`): `rows.py` rewritten as a consumer of
  `LayoutModel.tables`; `summary.py` reads `LayoutModel.summary_blocks`; `grounding.py` v2 grounds by
  word ids (span uniqueness becomes word-id uniqueness) while the text-based checks the validator
  reads (page declarations, posting dates, registered integrity checks) are served by rendering the
  geometrically derived page text plus a `SOURCE_POSTING_DATES` block; multi-account via
  `publish_partition` with per-account section scopes derived from account sections; a generic
  count-semantics declaration (comparable only when the header/label class is in a closed set, else
  not comparable — the `count_semantics` default); currency evidence from symbols/codes near amounts or
  in the header → an earned `currency_source`, else schema default (the package layer refuses as
  today); `direction` and `amount` sign emitted from one decision with `direction_provenance`
  recorded.
* **Cell S — synthetic archetypes and mutation tables** (`tests/layout_synthetic/`,
  `tools/layout_mutation_table.py`): a generator that renders each archetype to native PDF *and* image
  PDF with known truth (extending `tests/paddle_synthetic.py`), in EN/FR/ES, with wrapped descriptions,
  repeated headers/footers, `Page X of Y`, a daily balance table, a check grid, two accounts, a rotated
  page, a page-break continuation; mutation table: 8↔3, 0↔6, drop decimal, drop minus, swap the debit
  and credit headers, shift a column by one character width (straddle), duplicate a row, drop a row,
  permute dates, remove the header line, remove the closing balance, fold two accounts into one region —
  every mutant must kill `validated` or produce the named refusal.
* **Cell R — wiring** (`analysis/pipeline.py`, `discovery/runner.py`, `webapp/worker.py`,
  `webapp/artifact_cache.py`, `analysis/config.py`): `document_geometry` built from the artifact's
  evidence and passed on the unclaimed branch for every read (native, Tesseract-text-only → no
  geometry, Paddle); `GENERIC_STRUCTURER_ENABLED` replaced by `Settings.reconstruction_mode ∈ {off,
  research, production}` in the analysis key; the branch still skips `apply_statement_repairs`; the
  declined branch stays out unless R13 is ruled (then it is a one-line change with its own test).

**Material design decisions.**

* D1 *A neutral `layout/` package rather than growing the structurer.* Why: the layout algorithms serve
  the classifier (2.2), the agreement instrument (2.3), the structurer (2.4) and a future Phase 3
  producer; the import boundaries forbid any of the existing homes. Risk: two places for lexicons —
  mitigated by one `layout/signals.py`.
* D2 *Header first, structure confirms.* Column roles come from the header lexicon when a header exists;
  the structural tests (balance-difference identity on ≥ 60 % of consecutive anchors, debit/credit
  mutual exclusivity ≥ 95 %, sign markers, check-number shape) can *confirm* or raise `role_conflict`;
  they never override a header. Headerless inference is labelled `role_inferred_without_header` and
  requires the structural tests to be unanimous. Why: this keeps arithmetic as corroboration of a single
  hypothesis, the pattern Ocean approved in W3-3c, and makes every headerless case visible in the
  funnel.
* D3 *Records are anchor plus continuation by x-position*, not by regex: an anchor has a date inside the
  date column's range and an amount in an amount/balance column; a continuation has neither and sits
  inside the description range within two line heights; a date-like token inside the description range
  is text by construction (the known trap). Page-break continuation only when the two regions' column
  models match within one character width.
* D4 *One candidate out.* The structurer returns a `Statement`, a `DocumentPartition`, or `None` with a
  refusal code. Ambiguity (two admissible column models; two account partitions) is a refusal, never a
  list.
* D5 *Grounding by word id.* Every published figure points to the words that printed it; a figure with no
  word parent is not publishable on this path (serialization fail-closes it, as it already does for
  unproven ADB).
* D6 *Admission is by geometry source.* Native-geometry validations on the unclaimed branch are
  production (no extractor ran; the router is untouched); Paddle-geometry validations are research
  until 2.5 admits the trigger that produced the evidence. Why: honest coverage accounting; the routing
  question stays open as the brief requires.

**Tests.** Every `layout/` stage on the archetypes, native and image renderings, asserting the
LayoutModel JSON byte-for-byte against pinned expectations; every refusal code reachable by a fixture;
structurer v2 on every archetype validates through the real validator and reproduces the known truth
on every audited field; the existing 109-corpus measurement re-run (`tools/measure_structurer`)
with "published implies correct" preserved; the pipeline test that the claimed set is identical with
and without geometry (geometry never reaches detection); the key test; the holdout evaluation
harness on synthetic manifests.

**Tripwires.** `layout/` imports stdlib + `evidence` only; `analysis/structurer` never imports
`reconcile`/`adb`/`metrics`; the table-role and record-assembly signatures carry no oracle parameters;
return type pinned to a single candidate; no `enabled=`/router change; the OQ2 no-hardcodes guard
extended to `layout/` (lexicons are declared vocabularies with fixtures, never issuer strings); the
repairs skip on the generic branch pinned.

**Mutation tables.** The archetype mutation table above (every mutant kills or names); one mutant per
refusal edge (remove the `role_conflict` raise → the swapped-header mutant must stop being caught);
one per tripwire.

**Corpus measurement.** The funnel table v3 over `U755` on native geometry and on Paddle geometry (from
the 2.3 partition): regions found → column model resolved → records assembled → summary anchors →
partition → candidate → verdict, with B-sub-class counts; `layout_generalization` = unclaimed native →
validated with no new registration, broken down by the 91 census families so generality is visible
(a gain concentrated in one family is a finding, not a success); the control sample through the generic
path: key-field agreement with recorded payloads; the **first holdout pass**: every evaluated holdout
item's A/B/C class and the false-accept count (release-blocking if > 0 without a named SHA exception
proving the oracle wrong); every newly validated SHA named with its evidence refs and its sign
provenance tier.

**Performance / cost.** LayoutModel ≤ 200 ms per page in pure Python on native geometry (target; the
109-corpus timing is reported); no GPU; cold run within the memory cap; $0 for the admitted path.

**Regression floor.** 2,625 preserved payload-identical; gains never net against regressions; every
newly validated SHA is on the unclaimed branch with `reconstruction_mode=production` and native
geometry; Paddle-fed candidates counted under "research-validated, pending admission".

**Adversarial review (attack list).** Find a document where two column models are both admissible and
the code picked one. Find a headerless table where the chain test alone decided signs and no printed
total exists. Find a continuation line that carries an amount. Find a page-break where the column model
changed. Find a two-account statement folded into one ledger. Find a published figure without a word
parent. Find a date-like token in a description treated as a date. Find any path from the validator's
verdict back into `layout/`. Find any lexicon entry that is an issuer name.

**Completion gate.** Cells reviewed → closed → re-reviewed; archetype suite and mutation tables green;
floor green; cold run vs the 2.3 run of record with named gains and 0 regressions; holdout first pass
recorded with false accepts 0; fallout table v3 published; docs durable; STOP; closure report with the
explicit answer "does geometry generalise?" and the B-sub-class residue that 2.5 will target.

**Explicit exclusions.** New registrations as a coverage strategy; PP-Structure tables as truth; any
extractor routing change; Unlimited; character-level fusion; confidence arbitration; the declined
branch (unless R13); evidence_refs in the published UI (2.5); a learned classifier tier.

**Dependencies.** 2.3 complete (archetypes derived from its fallout); R4 (holdout batch) provisioned;
R13/R14 ruled or explicitly deferred.

---

### G.2.5 — RECONSTRUCTION v2 + PADDLE PRODUCTION ADMISSION

**Objective.** Harden the LayoutModel on the measured B-sub-class residue, admit the measured
pre-financial Paddle triggers into production routing, make routing page-level for mixed PDFs, turn
engine disagreement into review evidence, and publish evidence_refs lineage. Coverage movement:
**Paddle-fed gains admitted** under the measured triggers, named by SHA; further native gains from
hardening.

**Inputs.** 2.4's fallout v3 and B-sub-class residue; 2.3's E-metric census and agreement calibration;
the holdout (second batch if available); the 2.4 closure's answer on generality.

**Outputs.** `layout/` v2 (the mechanisms named by the residue, each with an archetype); admitted
triggers in `ocr/escalation.py`; page-level routing; disagreement review class; `evidence_refs[]` on
published values; the `local_free` latency measurement; the fallout table v4; the admitted Paddle-fed
newly-validated set.

**Architecture / cells.**

* **Cell L3 — hardening from measured fallout.** Only layout *mechanisms*, each justified by a
  B-sub-class count from 2.4 and each with a synthetic archetype: check grids (repeated
  `number | date | amount` triplets per line → a grid region type whose cells are transactions in
  reading order); section-scoped signs (a section title's direction word applies to every anchor
  until the next title; conflict with a column band → `role_conflict`); daily-balance tables detected
  as `daily_grid` regions and emitted as `stated_daily_balances` (an oracle for the validator, never a
  transaction source); summary anchors with the long tail of labels (a closed, fixtured lexicon in
  three languages); page-break continuation with header re-detection; account sections with the
  closed sibling-omission vocabulary; multi-line amounts (debit and balance on separate lines) under
  the orphan-amount rule. No branch keyed on a bank or a template string — the OQ2 guard on `layout/`
  enforces it.
* **Cell P2 — production triggers and page-level routing** (`ocr/escalation.py`, `ocr/inspect.py`,
  `discovery/runner.py`): each candidate trigger from 2.3 (`native_text_unreliable` from the
  native-layer probes; `image_backed_text_layer`; `orientation_anomaly`; the E-gate v2 classes on
  Tesseract output) is admitted **only** with (a) its labelled evidence from the wave (how many pages,
  what Paddle changed on them, what the validator then did), (b) an independent review, (c) a mutation
  table proving it cannot be started by a verdict; `RouterInputs` gains the page-level fields it needs
  (`page_triggers`) as mode-independent, pre-financial facts; native pages are never rasterised; the
  document classifier's `NOT_A_STATEMENT{structural}` verdict at the Tesseract rung refuses before any
  paid rung (a refusal, not a trigger); the pin `validated ∩ class-A = 0` becomes `validated ∩
  class-A ⊆ the named Paddle-fed set`.
* **Cell G2 — disagreement as review.** When two extractors were *independently* triggered on the same
  page (Tesseract then Paddle; later Paddle then Unlimited), the agreement instrument's exact
  amount/date disagreement on any published figure is an integrity note routed to review; both
  evidences are stored; no merge, no vote (accepted architecture §3).
* **Cell D — evidence_refs lineage** (`analysis/serialization.py`, `webapp/`): every published
  transaction, balance, date and summary figure carries `evidence_refs[]` (document sha, page, word ids
  or raw span, extractor id, evidence sha, settings key); the analyst UI shows the parent boxes;
  serialization fail-closes a generic-path figure with no parent (parsers on the registry path keep
  their span-based provenance).
* **Cell F — `local_free` measurement.** PaddleOCR 3.7.0 / PP-OCRv5 installed locally (CPU, or a local
  GPU if present) behind the same worker contract; identity pins verified; latency and RSS measured
  on the archetype pages and on the 34-slice; no routing change — the measurement informs R8.

**Material design decisions.**

* D1 *Triggers are admitted one at a time, each with its own population count.* Escalation count in any
  run must equal the precomputed trigger population; a trigger whose measured population is zero is
  not admitted.
* D2 *Page-level routing is a routing-grain change, not a doctrine change.* A mixed document's native
  pages keep their native evidence; only pages with an open pre-financial trigger are read by Paddle;
  the page provenance list already exists (`page_extractor`).
* D3 *Disagreement never selects.* A published figure disagreeing between engines is reviewed with both
  boxes shown; the candidate is not re-run on the other engine's text.
* D4 *The classifier can refuse before paying but cannot start.* Structural non-statement verdicts stop
  the ladder; uncertain verdicts do nothing to the ladder.

**Tests.** Each admitted trigger: fires on its synthetic; does not fire on a validated document; cannot
be started from a Class B or C outcome (the forbidden-edge tests, extended); page-level: a mixed
synthetic (native cover + image ledger) reads exactly the image pages; disagreement: a two-engine
synthetic with one perturbed amount lands in review with both evidences; lineage: every figure in the
published JSON has refs on the generic path and the UI renders them; `local_free`: the worker contract
test passes against the local install.

**Mutation tables.** One mutant per admitted trigger (make it verdict-conditioned → the forbidden-edge
test fails); one per refusal-before-paid edge; one per lineage fail-close; one for the class-A pin.

**Corpus measurement.** Fallout v4 on both geometries; admitted Paddle-fed newly validated named by
SHA with trigger, evidence sha and sign tier; escalation count = trigger population; disagreement rate
on dual-engine pages; holdout second pass with false accepts 0; cost per admitted Paddle-fed
validation (GPU-seconds × rate); latency p50/p95 per rung; `local_free` latency versus Vast.

**Performance / cost.** Production Paddle adds ≈ 2–3 s per triggered page on Vast (measured) or the
`local_free` figure; the funnel reports both; bytes per page as measured.

**Regression floor.** 2,625 + 2.4's admitted gains preserved payload-identical; no B/C → extractor
escalation in any run log (the runner asserts it); gate 105/3/1; CI green.

**Adversarial review (attack list).** Any trigger that correlates with a financial outcome? Any way a
`NOT_A_STATEMENT` refusal could suppress a genuine statement (adjudication precision on that
sub-kind)? Any page-level splice that blends a native page and an OCR page into one ledger without the
completeness oracles seeing mixed provenance? Any figure published without refs on the generic path?
Does `local_free` share the customer-data literal (it must not need it)?

**Completion gate.** Cells reviewed and re-reviewed; floor green; cold run vs 2.4's run of record;
every admitted trigger's population and mutation table published; holdout false accepts 0; lineage in
the UI; `local_free` measured; docs durable; STOP; closure report; the residual Class-A population
after Paddle (the input to 2.6's go/no-go) named.

**Explicit exclusions.** Unlimited; any confidence-based arbitration; character fusion; new
registrations; PP-Structure; a production pin change without its own measurement and ruling;
distributed workers; Kubernetes.

**Dependencies.** 2.4 complete with a positive generality answer (if 2.4 STOPPED negative, 2.5 is
re-planned rather than opened); R8 informs but does not block.

---

### G.2.6 — UNLIMITED OCR (go/no-go)

**Objective.** Investigate and, if justified, integrate the current `baidu/Unlimited-OCR` model as a
bounded, page-scoped, extractor-only fallback for pages where Paddle's extraction genuinely failed
(E0–E3), feeding the same canonical evidence (as a region sidecar plus text), the same reconstruction
and the SAME validator with the four-identity extra bar. Never a response to Class B or C. Coverage
movement: a thin tail; measured, not forecast.

**Go/no-go input (from 2.5's closure).** The residual population `RES_A` = genuine
`STATEMENT_COMPLETE` documents (adjudicated) with at least one page in E0–E3 after Paddle. Proposed
threshold (R7): open 2.6 only if `|RES_A| ≥ 10` documents *and* adjudication says their pages are
legible to a human; otherwise 2.6 closes as "deferred with evidence" and Phase 2 proceeds to 2.7.

**Research facts that shape it (`research/UNLIMITED_OCR_MEMO.md`).** DOCUMENTED: MIT-licensed,
released 2026-06-22, a vision-language OCR (DeepEncoder + 3B MoE decoder with sliding-window
attention), region-level `<|det|>` boxes only, no confidence, markdown with HTML tables, known
repetition and truncation failure modes, trained partly on PaddleOCR-labelled pages (correlated
lineage), hosted API with unspecified input retention (not usable for customer data), self-hosting via
vLLM ≥ 0.25 on NVIDIA. The repository's serving path is the DeepSeek-era prompt on an AMD box at ≈ 23 s
per page and a RunPod template with no rate recorded; pinned weights match upstream `main` exactly.

**Cells.**

* **Cell U0 — spike (before any integration; non-sensitive fixtures first, then `RES_A` only under R7).**
  Serve the pinned revision on the approved Vast RTX 5090 via vLLM (same host, same tunnel, same
  bounds); measure: prompt behaviour (`Free OCR.` versus the vendor's `document parsing.`), box scale
  (0–999 versus 0–1000), truncation at 4,096 versus 8,192 tokens, repetition incidence, latency per
  page, E-metrics of its text on the same pages as Paddle, and — the decisive number — how many `RES_A`
  pages become E-gate-usable. Output: a measurement memo and the go/no-go for U1.
* **Cell U1 — integration (only on go).** `unlimited` fills the commented slot after `paddle` in
  `EXTRACTOR_ORDER`; page-scoped; started only by E0–E3 on the Paddle read of that page (never by
  Class B/C, never by density, never by a verdict); canonical evidence with `words=()`, a lossless
  `regions[]` sidecar (label, box in the page frame, raw span), the immutable raw completion, and the
  existing postprocess quarantine (`ADMITTED_POSTPROCESS = ()`); `EVIDENCE_SCHEMA_VERSION` bump; pins:
  HF revision, weight sha, Docker digest, vLLM version, prompt; provenance and cost as for Paddle;
  the text feeds the same page-text path the validator reads; the LayoutModel runs in *text mode with
  region hints* (no word boxes → no column model; regions may delimit furniture/sections only);
  Unlimited-only figures reach `validated` only under the accepted plan's §7 bar: printed transaction
  count agreement AND running-balance continuity AND printed total or opening/closing identity AND
  account-summary agreement when printed, all on raw text; any missing identity cannot be waived.
* **Cell U2 — disagreement and hallucination class.** On pages where Paddle produced *some* words and
  Unlimited produced text, alignment by containment yields agreement flags; "reconciles but disagrees
  with Paddle words on a published figure" is the hallucination-suspect class → review, never
  validated.

**Design decisions.** D1 *No word-box adapter* — fabricating word boxes from region text would be
invented evidence; the region sidecar is lossless and honest. D2 *Same environment, own ruling* — the
approved Vast instance is the least-new-surface place to run it, but the §6 authorization names the
PaddleOCR path, so U0 on customer pages needs R7. D3 *`FREE_MODELS` is corrected*: the Unlimited token is
$0 only on a loopback host; on Vast it is `remote_paid` and priced like Paddle.

**Tests.** The rung refuses without E0–E3 on the Paddle read; refuses on Class B/C; refuses in auto mode
without the literals; the region sidecar round-trips; the four-identity bar is a single predicate with
a mutant per identity (drop one → the "Unlimited-only field validated" test must fail); truncation and
repetition are flags, never rewrites; the injection guards (existing) hold on the new raw text.

**Corpus measurement.** `RES_A` pages attempted; usable after Unlimited; reconstruction stages; validator
verdicts; Unlimited-attributed validated named by SHA with the four identities shown; hallucination
suspects named; latency, VRAM, bytes, GPU-seconds, cost.

**Floor.** As every milestone; plus "Unlimited-attributed validated only via the SAME validator and the
extra bar".

**Adversarial review.** Can an Unlimited HTML table ever become structure (PP-Structure-as-truth by
another name)? Can the region sidecar be mistaken for word geometry downstream? Is there any edge from a
failed reconciliation to this rung? Is the hosted API reachable from any configuration?

**Completion gate.** U0 memo; if go: U1/U2 reviewed and re-reviewed, floor green, named tail, cost;
if no-go: the deferral recorded with the residual named; STOP.

**Exclusions.** Unlimited as a default second pass; Unlimited on native-text pages; the hosted API;
prompting it for structure; any use of its tables as cells; RunPod (stays the labelled escape hatch).

**Dependencies.** 2.5 closure (the `RES_A` count); R7.

---

### G.2.7 — PHASE 2 CLOSURE

**Objective.** Freeze the production routing policy from evidence, ship the telemetry that reports the
truth (both denominators, funnel, A/B/C counts, cost, latency), write the runbooks, pin the Phase 3
seam, and tag `phase2-final`. Coverage movement: none new.

**Cells.** **Cell R — routing freeze**: the policy table (§L) rewritten with the measured numbers;
every admitted trigger listed with its population and its ruling; the deployment class for production
Paddle recorded per R8; the research modes documented as research. **Cell T — telemetry and report**:
`python -m telemetry.report --phase2` prints the truth table, the funnel, the two coverage figures, the
holdout summary, cost and latency percentiles; dashboards are class counts, never a fabricated
confidence. **Cell P3 — Phase 3 seam**: `ReconstructionRequest/Result` pinned by signature and digest;
the raster retention policy documented; the "what a future producer receives and must return"
contract written for the Phase 3 planning session; nothing model-related built. **Cell D — docs**:
`PROJECT_STATUS.md`, `PHASE2_STATE.md`, `PHASE2_RULINGS.md` (index of Phase 2 rulings),
`PADDLE_VAST_RUNBOOK.md`, `PARITY_MATRIX.md` re-scored against Ocrolus and MoneyThumb on the axes in
§R, `BATCH9_TRANSITION.md` §7 closure entry; the memory notes.

**Completion gate.** Floor green; cold run vs 2.6's (or 2.5's) run of record; CI green; both
denominators published with the adjudication ledger; the routing table and the ruling index; tag
`phase2-final` pushed; STOP; Phase 3 planning is a separate session with a separate authorization.

**Exclusions.** Anything that changes a verdict; Qwen; any multimodal model; fraud/tamper ML;
scorecards; distributed workers.

---

## H. BROAD PADDLE COVERAGE PLAN

### H.1 Populations and order

| set | definition | size (baseline) | purpose |
|---|---|---|---|
| CTRL | 36 Tesseract-validated scans + 114 native-validated documents stratified by census family and page-count bucket | ≈ 150 docs / ≈ 1,000 pages | agreement calibration on known-good documents; false-accept instrument for the Paddle path; recall of the generic path against the validator's own verdicts |
| U755 | every unresolved SHA at the run of record | 755 docs / 5,110 pages | the evaluation population; includes non-statements deliberately (their Paddle evidence is what the classifier needs; cost is trivial; the truth table must cover all 755) |
| SLICE | the 34-document corpus slice | 34 docs | configuration A/B (orientation on; v6 medium) if ruled |
| HOLD | the unseen holdout batch (R4) | 30 → 100 → 300+ over time | never sent to research runs that could burn it; evaluated only through the production ladder |

Order: CTRL → U755 → SLICE A/B → (later) HOLD through production only. Every page is attempted or
refused with an E0 reason. A page is never sent twice under the same configuration (cache hit with sha
equality).

### H.2 The one Paddle configuration that counts, and the ones that are measured

Production configuration = the Phase 2.1 pins (`PP-OCRv5_server_det` + `en_PP-OCRv5_mobile_rec`,
orientation classifiers off, `return_word_box=True`, 300 dpi). Measured configurations are separate
pinned partitions: orientation classifiers on (cheap, deterministic, the layout memo's first
recommendation) on the scanned/mixed pages; `PP-OCRv6_medium` on SLICE + 200 stratified pages (Baidu's
claimed +4.6 det / +5.1 rec, unproven on statements). Neither changes the production pin in 2.3; a pin
change is its own reviewed edit and partition (Phase 2.1 D5) and, for v6, its own ruling (R5).

### H.3 Stage-by-stage fallout (the shape of the deliverable; brief §12)

```
per document, per geometry source (native | paddle | tesseract-text):
  E  attempted -> evidence produced -> E-gate v2 pass (E-class if not)
  G  geometry built (pages, lines, words; frame; rotation)
  L  furniture removed -> >=1 table region -> column model resolved -> records assembled
     -> summary anchors (period, opening, closing) -> account partition          (B1..B8 if not)
  C  candidate produced (one) with sign tier and grounding coverage
  V  validator verdict + W3-2 class (+ doctrine refusal)
  Δ  newly validated vs floor · research-validated pending admission · review · refused
```

The report prints this as a funnel per source with counts, and as a per-SHA table (rows.csv). "Paddle
success" is never one number.

### H.4 Extraction failure, precisely (brief §17; Q14)

A Paddle read of a page is an **extraction failure** iff one of these holds, each measurable without
labels and recorded as an E-class:

* **E0** no evidence: worker error, raster failure, timeout, refusal, empty word list.
* **E1** coverage gap: the share of ink pixels outside any word box exceeds the calibrated threshold on
  a page whose ink coverage says it is not blank (Paddle missed regions).
* **E2** recognition quality: the money-shape parse rate over numeric tokens, the lexicon rate over
  alphabetic tokens, or the garbage-token rate fails the per-configuration calibration; the rec-score
  p10 is used *only* as a per-configuration proxy, never as a gate on its own (the literature warns it
  must be recalibrated per engine setup).
* **E3** frame/orientation: unanimous orientation votes disagree with the frame (page rotated), skew
  above the calibrated angle, box regularity (line-height CV, numeric right-edge residual) outside
  calibration.
* **E5** truncation/bleed: the existing page-integrity flags.
* **E4** cross-engine disagreement (native versus Paddle exact amount/date agreement below calibration)
  is **review evidence**, not an extraction failure, and never starts a third engine.

A structural refusal (B*) is *not* an extraction failure; a validator refusal (C*) is *not* an extraction
failure. Only E0–E3 (and E5) may open an extractor fallback, and only for that page.

### H.5 Should Paddle read every unresolved genuine statement even when native text exists? (Q11)

**In the research wave: yes**, for three reasons — the cost is a few GPU-hours, the evidence is
immutable and reusable by 2.4/2.5/Phase 3, and it is the only way to *measure* rather than assume the
classes where Paddle beats a native layer (text-layer defects, image-backed text layers, native words
with broken spacing or reversed strings, invisible duplicate text layers). **In production: no by
default.** Native geometry is exact and free; Paddle on native pages runs only under the measured
pre-financial triggers 2.5 admits. The wave decides which triggers those are; the plan does not.

### H.6 What "Paddle helped" will mean

For each document, "Paddle helped" is recorded at the stage where the Paddle-geometry funnel went
further than the native-geometry funnel (or than the Tesseract text funnel for scans), e.g. "native:
B2 role_conflict; paddle: validated". Aggregated by census family and by the native-layer probes, this
is the evidence for production triggers. A Paddle-fed validation that the native path also achieves is
"no added value" and is reported as such.

### H.7 Metrics (brief §21), where each lives

Phase-1-only success (rows: `source_path` native/tesseract, verdict) · Paddle attempted (`paddle_rung`)
· extraction success (E-class empty) · geometry success (G stage) · reconstruction success (L/C stages)
· deterministic validation success (V) · newly validated from Paddle (Δ, named) · review · refused ·
non-statement / incomplete / illegible classifications (L1) · false accepts (holdout + CTRL
adjudication) · validated regressions (compare, exit 2) · latency (`elapsed_ms`, per-rung ms,
percentiles in the report) · RAM (`peak_rss_mb` per document with psutil; run peak as today) · VRAM
(`vram_mb` sampled per request) · transferred bytes (`bytes_up/down`) · GPU seconds (`gpu_ms`) · paid
cost (`cost` from the ruled rate).

---

## I. GENERALIZED RECONSTRUCTION PLAN — how geometry becomes bank-agnostic structure

### I.1 Principles

Deterministic, reproducible, traceable to word ids; pure functions with versioned constants; failures
are crisp refusals, not plausible guesses; the ledger identity is computed once, by the validator,
after the structure exists (research memo R.1: "nothing in the literature supports an optimizer that
selects whichever reconstruction reconciles; TabSniper and bankstatementparser use the ledger identity
strictly as a post-hoc check"). Learned image table models are not on the path: they are strong on
report tables and weak on page-sized borderless statement bodies, annotation-convention-sensitive, and
opaque (research memo B.4); the only statement-trained model in the literature still relies on
OCR-word row separators and rule post-processing.

### I.2 The LayoutModel stages (from `research/LAYOUT_RECONSTRUCTION_MEMO.md` R.1, adapted to our contracts)

0. **Normalise.** One frame per page (display orientation, PDF points; pixel frames scaled by the
   recorded dpi); for OCR pages estimate skew from word-baseline segments and rotate boxes back; page
   units `h` = median word height, `cw` = median character width.
1. **Lines.** The existing one grouping rule (`evidence.group_lines`, y-overlap with 0.6·median height)
   — no second rule (the tripwire exists).
2. **Furniture and continuity.** A line is furniture if its digit-masked text recurs at the same
   page-normalised y (±0.5·h) on ≥ 2 pages (headers, footers, account masks, "Statement period"
   banners); `Page X of Y` in EN/FR/ES → `PageContinuity{observed, declared, gaps}`; single-page
   documents fall back to a keyword rule.
3. **Table regions.** Vertical alignment edges from x0/x1/centre clusters (tolerance 0.5·cw, ≥ 3
   members) extended through consecutive lines while gaps ≤ 4·h; a region = a maximal run of lines
   touching ≥ 2 distinct edges and containing ≥ 1 amount token; split on a new header line, on a
   *projected row header* (one text cell spanning ≥ 2 column extents with no amount — the section
   title / account heading shape), or on a gap > 2.5·h. Native vector rules, when present, are an
   additional edge source.
4. **Column model.** Numeric tokens clustered by **right edge**, text tokens by left edge (0.5·cw);
   amount grammar fixed per statement by separator majority (`1,234.56` / `1 234,56` / `1.234,56` /
   `(123.45)` / `123.45-` / `-123.45` / `123.45 CR|DR` / currency prefixes); boundaries at midpoints; a
   straddling token is a hard `straddle` flag; header = nearest lexicon line above the first
   amount-bearing line (multi-line headers within 1.5·h); header tokens map to columns by x-overlap
   ≥ 0.5.
5. **Records.** Anchor = date inside the date column range (or the leftmost text cluster when
   headerless) AND ≥ 1 amount in an amount/balance column; continuation = no date in the date range,
   no amount in amount ranges, all words inside the description range, within 2·h below the previous
   line, left edge ≥ description x0 − 0.5·cw; an amount-only line attaches to the previous anchor only
   into an empty column, else `orphan_amount`; a date-like token inside the description range is text;
   page-break continuation only when the two regions' column models match within 1·cw; section titles
   and balance blocks are emitted as their own objects.
6. **Roles.** Header lexicon first (Date/Datum/Fecha; Description/Libellé/Concepto; Debit/Withdrawals/
   Débit/Retrait/Cargo; Credit/Deposits/Crédit/Dépôt/Abono; Balance/Solde/Saldo; Amount/Montant/
   Importe; Check/Chèque — a fixtured, closed vocabulary in `layout/signals.py`, never an issuer
   string). Structural tests in fixed order **confirm or flag**: balance = the rightmost amount column
   present on ≥ 80 % of anchors whose row-to-row difference equals ± another column's value on ≥ 60 %
   of consecutive pairs; debit/credit = two amount columns mutually exclusive on ≥ 95 % of anchors;
   signed amount = one amount column with sign/bracket/CR-DR markers; check number = separator-free
   3–8-digit integers. A header contradicted by the tests → `role_conflict` (refuse). No header →
   `role_inferred_without_header`, admitted only when the tests are unanimous.
7. **Sections and accounts.** Section titles carry a direction word or none; account sections are
   detected from account-number patterns plus account-type words plus a following table region; each
   table region belongs to the nearest preceding account section; two candidate partitions → B5.
8. **Summary blocks.** Opening/closing/period/totals/counts/ADB labels (closed lexicon, three languages)
   with the nearest amount on the same line or right-aligned within the block; word refs on each.
9. **Output.** `LayoutModel{pages, furniture, continuity, regions[{kind: transaction_table |
   check_grid | daily_grid | summary_block | section_title | account_header}], tables[{columns[{role,
   x-range, header words}], records[{anchor line, continuation lines, cells{role → words}}]}],
   accounts[], refusals[]}`; byte-stable JSON; `RECON_PARAMS_VERSION`.

### I.3 The structurer v2 (consumer)

Reads `LayoutModel`; emits `Transaction(date, description, signed amount, direction, running_balance)`
from cells; direction from the role (Tier 1) or, for a single amount column without markers, from the
section direction (Tier 1) or from the chain (Tier 2/chain-only, recorded); period, opening, closing
from summary blocks; `stated_daily_balances` from daily grids; `stated_*` totals/counts when the
label class is in the closed set, with the count-semantics declaration defaulting to *not comparable*;
currency evidence; multi-account partition via `publish_partition` with section scopes; the
`SOURCE_POSTING_DATES` block rendered for the ADB's posting-date check; grounding v2 by word id with
uniqueness; one candidate or a coded refusal. It does not read reconciliation, ADB, or metrics.

### I.4 Confidence and ambiguity representation

No floats grant anything. Each LayoutModel decision carries a *provenance kind* (header / structural /
section / chain / inferred_without_header) and each refusal a code; the structurer passes sign tiers
and grounding coverage through to the payload as annotations; the report aggregates them. Where the
brief asks for "multiple candidate structures", the answer is: hypotheses exist inside a stage (e.g.
two column-model candidates) but the stage must resolve to one by table-local evidence or refuse; a
candidate list never leaves `layout/`.

### I.5 What is deliberately not built

Learned table-structure models (SLANet/SLANeXt: off-domain, wireless metrics unpublished, cells
"invalid" for SLANeXt); RT-DETR cell detection; PaddleOCR-VL / HPD-Parsing (vision-language models,
boundary-excluded, non-deterministic); per-bank templates in `layout/`. Optional, advisory only, never
gating a row: `PP-DocLayout_plus-L` region labels as classifier features and a Stage-3 cross-check on a
sample (its training mix contains no statements).

### I.6 Structural refusal sub-classes (L3)

B1 no table region · B2 column model unresolved (`role_conflict`, `straddle`, `too_few_members`,
`header_absent_and_unconfirmed`) · B3 records unassembled (`orphan_amount`, `continuation_ambiguous`,
`two_dates_in_row`) · B4 summary anchors not found (period / opening / closing) · B5 account partition
ambiguous · B6 cross-page continuity broken · B7 grounding failed · B8 sign undeterminable. Every code
is reachable by a synthetic, counted in the funnel, and is the unit of 2.5's hardening.

---

## J. DOCUMENT CLASSIFICATION PLAN

### J.1 Taxonomy (OUR DESIGN CHOICE; vocabulary ruled at 2.2)

`STATEMENT_COMPLETE` · `STATEMENT_PARTIAL{missing}` · `STATEMENT_ILLEGIBLE{E-class}` ·
`ACTIVITY_EXPORT` · `NOT_A_STATEMENT{sub_kind}` · `FILE_INVALID` · `KIND_UNCERTAIN`, with orthogonal
axes `modality ∈ {digital, scanned, mixed, image_backed_text}`, `language`, `account_kind ∈ {deposit,
card, loan, brokerage, unknown}` and an optional issuer identity (never from folder or filename —
UNKNOWN-ISSUER ruling). The brief's six-class sketch maps onto this with two refinements: "partial"
carries *which element* is missing, and "unreadable" splits into an invalid file and an illegible
statement. `ACTIVITY_EXPORT` is separate from `STATEMENT_PARTIAL` because it never had the anchors (the
13 portal exports and the existing informal `chase_export` / `found_lead` class).

### J.2 Signals (deterministic tier-1; research memo R.3)

Complete statement: a printed period expression (EN "statement period / from … to", FR "du … au", ES
"del … al", or two dates beside opening/closing labels); opening and closing balance lexicon hits with
an amount; ≥ 1 transaction-table region with a date column and an amount column (or a printed
zero-activity declaration in the sibling-omission vocabulary); `Page X of Y` complete when printed.
Partial: page gaps; a missing anchor; a running-balance discontinuity at a page boundary; a table that
begins mid-way with no header block on page 1. Cheque image: MICR E-13B-shaped digit groups in the
bottom 15 % of the page and a page aspect ratio in [2.0, 2.6]; voided: "VOID"/"NUL"/"ANNULÉ" lexicon on
such a page. Deposit slip, letter/notice: their lexicons plus the absence of a table region. Card
statement: "minimum payment / payment due / credit limit / crédit disponible" with a single amount
column and no running balance. Loan: "principal / interest / escrow / capital / intérêts". Screenshot:
an OCR page whose pixel dimensions are far from any paper size, with no furniture repetition. Activity
export: a dated ledger with amounts but no period/opening/closing anchors and reverse chronology or
"pending" rows. Invalid: preflight (already exists) plus the Java-serialisation magic.

### J.3 Tiers and defensibility

Tier `structural` (a MICR line; a table region; a `Page X of Y` gap) beats tier `lexical` (keywords
only); `uncertain` is a first-class outcome. Every verdict lists its signals with word refs. A learned
tier (TF-IDF + logistic on the sealed labels with a held-out split) is *optional in 2.5* if the
deterministic tier leaves too many `KIND_UNCERTAIN`; it may route to review or refuse-with-reason,
never gate a financial decision, and must be deterministic at inference with pinned weights. LayoutLM /
Donut / VLM classifiers are unjustified for an eight-class lexically separable problem with no public
benchmark and would add a model with no statement-specific evaluation (research memo D).

### J.4 Placement and effect

Runs at every rung on the best evidence available (native evidence; Tesseract text in degraded mode;
Paddle evidence). Effects: in 2.2 and 2.3 recorded only; from 2.5, `NOT_A_STATEMENT{structural}` and
`FILE_INVALID` refuse before any paid rung (privacy-positive and cost-positive), `STATEMENT_PARTIAL`
proceeds (the validator's completeness oracles will refuse; the classifier's finding explains why),
`KIND_UNCERTAIN` never changes routing. Classification never changes the raw denominator and never
grants anything.

### J.5 Human adjudication

The sealed store (2.2-H) is the only truth for L1. Slices: 2.2 (≈ 227), 2.3 (changed verdicts,
uncertain, false-accept candidates, +50 random), 2.4/2.5 (every refused-as-non-statement document is
adjudicated before the refusal is admitted to production — precision on that sub-kind must be 100 % on
the adjudicated set). The classifier's tests are generated from adjudications *only as synthetic
re-creations of the shape*, never as the documents themselves (fixture privacy).

---

## K. UNLIMITED OCR PLAN

### K.1 Research requirements (before design; brief §18)

Verified in `research/UNLIMITED_OCR_MEMO.md`: what it accepts (images; PDFs only rasterised; one page
per request in our contract; multi-page one-shot exists but misses small text), what it returns
(markdown + HTML tables + region `<|det|>` boxes; **no word boxes, no confidence**), engine (a VLM;
materially independent of PP-OCRv5's detection+CTC physics but with correlated label lineage), version
behaviour (pinned weights identical to upstream `main`; README-only changes since), latency (≈ 23 s/page
on the old AMD shim; RTX 5090/vLLM unmeasured), cost ($0 weights; GPU time), data handling (self-hosted:
none leaves the host; hosted API: unspecified input retention — excluded), constraints (vLLM ≥ 0.25,
`trust_remote_code`, the n-gram logits processor, empty output without the `<image>` prefix), and the
failure modes it could plausibly improve (pages where Paddle's detector finds nothing or garbles:
low-contrast, faxed, skewed, unusual fonts) versus those it cannot (structure, columns).

### K.2 Fallback criteria (Q15)

Exactly: a page whose Paddle read is E0–E3 (or E5), on a document classified `STATEMENT_COMPLETE` or
`KIND_UNCERTAIN`, with the customer-data ruling for this path in force, and never because a
reconstruction refused (B) or a validator refused (C). Independently measurable extraction-quality
cases where Unlimited may provide evidence Paddle missed (brief §17): E1 coverage gaps (Paddle's
detector missed ink), E2 recognition failures on unusual fonts, E3 orientation where Paddle's
orientation-off pin lost the page (though the orientation configuration in 2.3 may close most of these
more cheaply). These are the triggers; they are designed explicitly and each gets its population count.

### K.3 What Unlimited contributes that Paddle does not (Q16), and its own geometry adapter (Q17)

A second, differently-failing reading of *pixels Paddle could not read*, plus region-level layout
labels. Not: word geometry, column models, confidence, or structure. Hence **no word-box adapter**
(fabrication is forbidden); **yes** a lossless region-evidence adapter (`regions[]` sidecar with page
frames, `words=()`), which lets the same `ExtractionEvidence` type carry it, lets `DocumentGeometry`
report "no word geometry" honestly, and lets the LayoutModel use regions for furniture and section
hints only. Reconstruction then runs in text mode; Unlimited-only figures reach `validated` only under
the four-identity bar.

### K.4 Integration architecture and proof requirements

As in G.2.6: the commented slot in `EXTRACTOR_ORDER`; the pinned identity (revision, weight sha, Docker
digest, vLLM, prompt) verified before any page; the same bounds, tunnel, loopback and no-retention
rules as Paddle; the existing postprocess quarantine; immutable raw completion; truncation and
repetition as flags; the hallucination-suspect class; mutation tables for every identity in the extra
bar and for every forbidden edge; provenance and cost as for Paddle. Go/no-go on the measured residual
(R7).

---

## L. FINAL PRODUCTION ROUTING PROPOSAL (to be adjusted by the measurements; frozen only at 2.7)

```
document arrives
  -> preflight; FILE_INVALID / encrypted -> refuse (reason)
  -> native text present?
       yes -> native evidence + geometry; classifier
              NOT_A_STATEMENT{structural} -> refuse (reason)                   [no extractor]
              registry claims -> Phase 1 parser -> validator -> validated: STOP
              unclaimed (and declined if R13) -> LayoutModel -> structurer v2 -> validator
                    validated: STOP · B*: review/refuse (reason) · C*: review/refuse (reason)
              native-layer probes say unreliable (text-layer defect / image-backed text /
              orientation anomaly) -> PADDLE on those pages (pre-financial trigger; admitted in 2.5)
       no / image-only / mixed pages -> Tesseract (text; $0)
              classifier on text: NOT_A_STATEMENT{structural} -> refuse         [never leaves the machine]
              Tesseract usable & claimed -> parser -> validator (as today: 36 validated)
              Tesseract unusable (U-extract, E-gate v2) or no text (R) -> PADDLE (production class per R8)
                    Paddle evidence -> classifier -> LayoutModel -> structurer v2 -> validator
                    Paddle E0–E3 on a page -> UNLIMITED (if 2.6 went go; own ruling) -> same path + extra bar
  every B* -> review/refuse with the sub-class; every C* -> review/refuse; NO edge to any extractor
  disagreement between independently triggered engines on a published figure -> review with both boxes
```

Expected shape of the measured trigger table (to be filled by 2.3/2.5; the plan does not presume the
numbers): image-only (13 today), U-extract (0 today under the triad; possibly > 0 under E-gate v2),
text-layer defects (8 known), image-backed text layers (unknown until censused), orientation anomalies
(unknown), mixed pages without text (14 documents' worth today). Deployment class for production Paddle
is Gustavo's decision (R8): `local_free` keeps customer pages on-machine and needs no remote-data
ruling; Vast needs a production ruling distinct from the research authorization.

---

## M. RISKS

| # | Risk | Where it bites | Mitigation in this plan |
|---|---|---|---|
| M1 | **False positives** — a reconstruction that sums and is wrong (debit/credit swap, subtotal ingested as a posting, duplicated row that a dropped row compensates) | 2.4/2.5 | header-first roles with structural confirmation; straddle and two-dates hard flags; word-id grounding with uniqueness; the archetype mutation table (every mutant must kill); holdout false accepts release-blocking; CTRL key-field agreement |
| M2 | **Hidden bank-specific assumptions** leaking into `layout/` (an issuer word in a lexicon; a threshold tuned to one family) | 2.4/2.5 | OQ2 guard extended to `layout/`; per-family breakdown of gains (a gain concentrated in one family is a finding); burned-item rule for the holdout; lexicons are declared vocabularies with fixtures |
| M3 | **Geometry ambiguity** (two admissible column models; a section title that is also a row) | 2.4 | refusal codes B2/B5 instead of a choice; adversarial fixtures; the report counts ambiguity as its own bucket |
| M4 | **OCR disagreement** treated as a vote or a merge | 2.5/2.6 | disagreement is review evidence with both boxes; no fusion; no vote (accepted architecture §3) |
| M5 | **Validator-as-optimizer leakage** through a new path | all | the four structural "cannot"s (§E.4) as tripwires; one-candidate-out; signature pins; the two pre-existing sites named and ruled (R9, R10) |
| M6 | **Corpus-label leakage** — the census SHA lists, folder labels, the cold-cache validated payloads, or the pinned audit CSVs shaping thresholds or tests | 2.2 onward | sealed store outside the repo with an import firewall; census lists used only as agreement comparisons; folder labels barred (existing ruling); holdout burned/graduated rules; thresholds versioned and set on synthetics, then measured |
| M7 | **Tautological arithmetic** — chain-derived signs make `opening + Σ = closing` self-fulfilling | 2.4 | sign tiers recorded; chain-only candidates flagged; R14 proposes an integrity flag when no independent direction evidence exists |
| M8 | **Cost** — an unpriced Vast rate; runaway re-reads | 2.3 | cost computed, never estimated; cache hits by sha; population lists fixed before the run; the wave is a few GPU-hours by measurement |
| M9 | **Latency** — Paddle on every scanned page in production | 2.5/2.7 | triggers admitted with populations; page-level routing; `local_free` measured; percentiles reported |
| M10 | **Remote privacy** — customer pages on a marketplace GPU host | 2.3 (and 2.5/2.6 if ruled) | the recorded ruling; loopback worker; no retention; content-free logs; bounded payloads; retention attestation on the real instance; the classifier refusing non-statements before any paid rung; `local_free` as the privacy-preferred production class (R8) |
| M11 | **Cache / provenance correctness** — a geometry-fed answer served to a text-only run, or a research artifact selected as the run of record | 2.2 | the geometry-aware key + stage bump; research partitions refused by `run_of_record`; over-partitioning-is-safe doctrine |
| M12 | **Model/version drift** — a silent v6, a Paddle weight change on the host, an Unlimited revision | all | identity pins verified per field before any image; separate partitions per configuration; weight sha pins for Unlimited (host-side weight checksums for Paddle remain an open gap, noted) |
| M13 | **Rotation-frame mismatch** on the unresolved set (0/830 measured only on the pinned corpus) | 2.2 | census first; boxes transformed to the display frame; four-angle synthetics |
| M14 | **The "declined" population** (119) stays invisible to reconstruction | 2.4 | R13 |
| M15 | **Adjudication bottleneck** — one human, ~500 documents over the phase | 2.2–2.5 | slices sized per milestone; the CLI; structural-tier verdicts need less review; UNCERTAIN is allowed |
| M16 | **A negative generality answer** at 2.4 | 2.4 | STOP and report is a planned outcome, not a failure of process; 2.5 is re-planned, not opened |

---

## N. USER RULINGS NEEDED

Not re-asked: OQ1–OQ11, Ruling A, Ruling B, the Vast.ai authorization's terms, the orchestration
override, the §6 customer-data authorization itself (granted in the brief). What follows is what the
brief did not decide.

**Blocking before 2.3 (2.2 can start without them):**

* **R1 — Operational scope of the §6 authorization**, to be recorded verbatim in `PHASE2_RULINGS.md`:
  (a) populations: `CTRL` (validated customer statements, for calibration) and `U755`, plus `SLICE`
  for configuration A/B — confirm the control sample of *validated* statements is inside the
  authorization; (b) retention: worker none; local research partitions and retained rasters under the
  same gitignored, on-machine rule as the archive; (c) instance lifecycle: stopped after each wave,
  attestation recorded; (d) confirmation that `PADDLE_REMOTE_CUSTOMER_DATA_OPT_IN` may be set only in
  the environment of research runs, never in a tracked file or in auto mode.
* **R2 — The Vast hourly rate** (still owed from Phase 2.1), so cost is computed rather than `rate not
  measured`.
* **R3 — Adjudication**: who adjudicates (Gustavo, an analyst, or both), where the sealed store lives
  (a path on this machine outside the repository), and the rule that MoneyThumb outputs, folder
  labels and census lists are never used as labels. Recommendation: Gustavo adjudicates slice 1
  (≈ 227) with the CLI; later slices may be delegated with the same CLI.
* **R4 — Holdout source**: a batch of statements not in the archive (e.g. uploads received after
  2026-09-01), target 30 directional → 100 first bank mix → 300+ before any generality claim, provided
  under the holdout manifest's attestation.

**Ruled at the opening of the milestone that needs them:**

* **R5 — PP-OCRv6 A/B measurement** on `SLICE` + 200 pages as a separate pinned partition (the Phase 2.1
  ruling says any v6 evaluation is a separate ruling). Recommendation: yes — highest-leverage lever if
  the claims hold; no production pin change without a further ruling.
* **R6 — Orientation classifiers ON as a second pinned configuration** for scanned/mixed pages (a pin
  change → its own partition). Recommendation: yes.
* **R7 — Unlimited**: (a) extend the remote-data authorization to the Unlimited model on the same Vast
  instance for U0/U1 (the §6 text names the Paddle path only); (b) the go/no-go threshold
  (recommendation: ≥ 10 adjudicated complete statements with E0–E3 pages after Paddle).
* **R8 — Production deployment class for Paddle after Phase 2**: `local_free` (privacy-preferred; latency
  measured in 2.5) versus Vast under a production ruling. Can wait for 2.5's measurement.
* **R9 — The hosted-extraction selection in webapp auto mode** (`analysis/pipeline.py:940-990`, "prefer
  whichever extraction's summary reconciles"): pin it unreachable in deterministic mode now (a
  tripwire) and schedule removal or fencing — Ruling A closed the *routing* edge, not this *selection*.
  Recommendation: remove in 2.2 or 2.7 (Phase 1 hygiene, no coverage effect).
* **R10 — `bank_repairs.py`'s six bank-keyed rewrites** versus the 2026-08-21 repair doctrine: out of
  Phase 2 scope (they cannot reach the generic branch, pinned), but a doctrine inconsistency; ruling on
  whether a Phase 1 hygiene ceremony is scheduled.
* **R11 — The `refused` outcome class** (unranked against failed/withheld/review; any move *out of*
  validated stays a regression) and the two-denominator report — an acknowledgment that the compare
  tool's semantics widen.
* **R12 — The CCL denominator definition**: `STATEMENT_COMPLETE ∧ legible`, any account kind the engine
  targets, adjudicated only. Card and loan statements reported separately.
* **R13 — The declined branch**: allow the LayoutModel/structurer on documents a registration claimed
  at detection but declined at parse (119 today; 85 native) — the parser produced no candidate, so
  this is not a withheld-retry; the issuer identity from detection is preserved as `bank`. Touches the
  claim doctrine (W3-3c ruling 2), so it is Gustavo's call. Recommendation: yes, with a tripwire that
  `withheld`/`review` documents never reach the generic path.
* **R14 — A new integrity flag** (protected module, ceremony) when every sign on a candidate is
  chain-derived and no independent direction evidence exists on the document. Recommendation: yes,
  flag-never-withhold at first, measured on CTRL.

---

## O. FINAL ROADMAP

```
PHASE 1  deterministic-v1 / multi-account-v1 — FROZEN at batch9-final (2,625 / 3,380)
   |
PHASE 2.0  safety foundations — COMPLETE (A/B/C, verdict-blind router, quarantine, endpoint policy, run of record)
   |
PHASE 2.1  PaddleOCR 3.7 / PP-OCRv5 on Vast, canonical evidence, DocumentGeometry — COMPLETE, phase2.1-final
   |
PHASE 2.2  TRUTH INSTRUMENTS  classifier · taxonomy · holdout + sealed store · telemetry · key/frames · research mode   (+0)
   |
PHASE 2.3  BROAD PADDLE EVIDENCE WAVE  CTRL + U755 (+ A/B) · E-gate v2 · agreement · truth table v2 · baseline fallout (+0 official)
   |
PHASE 2.4  GENERALIZED RECONSTRUCTION v1  layout/ + structurer v2 · archetypes · holdout pass · native gains admitted
   |            (STOP-and-report if geometry does not generalise)
PHASE 2.5  RECONSTRUCTION v2 + PADDLE PRODUCTION ADMISSION  measured triggers · page-level · disagreement · lineage · local_free
   |
PHASE 2.6  UNLIMITED OCR  go/no-go on the residual Class-A population · extractor-only · region sidecar · four-identity bar
   |
PHASE 2.7  PHASE 2 CLOSURE  routing frozen from evidence · both denominators · runbooks · Phase 3 seam · phase2-final
   |
PHASE 3  (separate authorization) an evidence-grounded multimodal producer behind ReconstructionRequest/Result,
         returning candidates to the SAME validator; page rasters + evidence + geometry + LayoutModel + refusals as input
```

---

## P. THE TWENTY RESEARCH QUESTIONS, ANSWERED

1. **How does Ocrolus generalise across formats?** A hybrid: learned localisation/labelling models over
   an issuer-aware micro-template library, with human microtasks as the universal fallback that also
   mints labels; unseen layouts go through the generic path, are judged by reconciliation, repaired by
   humans, and the repair becomes training data (STRONGLY INFERRED; the big-bank-fast / credit-union-slow
   gradient is the fingerprint).
2. **Likely internal abstractions:** Book → Document → PageDoc; form type as a tuple; uniqueness values;
   transactions as row objects with pixel bbox and page; Account → Period → Transaction independent of
   files; field-level calibrated confidence; enumerated rejection reasons; a digitisation router.
3. **Classification before extraction?** Yes, documented: `CLASSIFIED` precedes `PROCESSING`; page-level
   typing with UNKNOWN and human fallback; issuer identity very likely resolved there.
4. **Native versus scan:** both accepted; parsable versus image-based is a documented distinction;
   "the most suitable digitization tool" per document; the text layer is parsed regardless for
   forensics; hybrid most likely.
5. **Reconstruction on unfamiliar layouts:** row objects with bounding boxes; polarity and account
   assignment as separate decisions; running-balance chaining; LLM assistance for the semi-structured
   tail since 2023 (PLAUSIBLE HYPOTHESIS for the model class).
6. **Reconciliation's role:** gate (`STATEMENT_UNRECONCILED`), fraud signal (Detect), and in-loop error
   localiser (patent) — the last is the edge we forbid.
7. **Confidence and human review:** field-level 0–1 on fields and classification, calibrated across
   models on human-verified data; per-field routing with document fallback; microtasks; algorithmic
   worker checks; human output feeds delivery, training, calibration and fraud ground truth.
8. **How our architecture compares:** §R. In one line: we already have the stronger correctness core
   (per-row balance validation, provenance, determinism, fail-closed) and lack their breadth, their
   classifier, their completeness model across statements, and their human tail; this plan builds the
   first three without the fourth.
9. **Is DocumentGeometry right?** Yes as evidence; add a LayoutModel for understanding (§E.3).
10. **Best way to evaluate Paddle broadly:** §H — CTRL first, then U755, immutable research partitions,
    E-metrics without labels, native↔Paddle agreement, the funnel per geometry source, false-accept
    candidates adjudicated.
11. **Paddle on every unresolved genuine statement even with native text?** Research yes; production
    only under measured triggers (§H.5).
12. **Which reconstruction algorithms:** §I.2 — alignment edges, right-edge numeric clustering,
    anchor/continuation by x-position, header-first roles with structural confirmation, projected row
    headers for sections/accounts, furniture by cross-page recurrence, page continuity, word-id
    provenance; no learned TSR on the path.
13. **How to classify non-statements / partials:** §J — deterministic structural and lexical signals in
    tiers, sub-kinds, missing-element findings, sealed adjudication, never a denominator edit.
14. **A true Paddle extraction failure:** E0–E3 (+E5) on a page, measured without labels (§H.4); never a
    structural or financial refusal.
15. **When to invoke Unlimited:** only on E0–E3 pages after Paddle, on complete/uncertain statements,
    under its own ruling, page-scoped (§K.2).
16. **What Unlimited contributes:** a differently-failing reading of pixels Paddle could not read, plus
    region labels; not geometry, not structure, not confidence (§K.3).
17. **Its own geometry adapter?** A lossless region sidecar, yes; a word-box adapter, no (§K.3).
18. **Final production routing:** §L, frozen at 2.7 from the measured trigger table.
19. **Near-bank-agnostic behaviour without sacrificing correctness:** understand layouts with
    deterministic geometry that refuses on ambiguity; keep the validator the only authority; keep the
    printed-oracle discipline of Phase 1 but discover the oracles by label class and geometry instead of
    exact grammar; prove generality per family and on an unseen holdout; never let a label become a
    parser.
20. **Is any part of the brief's strategy materially inferior to an alternative?** Four places, each
    adopted above: (a) "Paddle first" for native-text documents in production — inferior to native
    geometry first with Paddle under measured defect triggers; (b) a single classification gate before
    Paddle — inferior to classification at every rung on the best evidence (a non-statement never leaves
    the machine); (c) Unlimited as a full milestone regardless of the residual — inferior to a go/no-go
    gated on the measured Class-A residue; (d) the ladder omits the false-accept instrument — the
    holdout cage and sealed adjudication are the most important addition in this package. One more,
    offered as R13: leaving the 119 declined documents outside generalized reconstruction is inferior to
    admitting them under a tripwire, since a decline is a structural non-fit, not a financial failure.

---

## Q. PHASE 2.1 DOCUMENTED PREREQUISITES — EVALUATION (brief §23; detail in `research/REPO_GEOMETRY_MEMO.md` §5)

| Prerequisite | Blocks broad Paddle / reconstruction? | Correctness | Reproducibility / cache | Performance | Belongs in Phase 2? | When |
|---|---|---|---|---|---|---|
| Rotation-frame mismatch (native geometry vs display raster) | Not the wave itself (Paddle frames are display-consistent); **yes** for native reconstruction on rotated pages and for any native↔Paddle overlay | latent (0/830 on the pinned corpus; the 755 not censused); wrong bands on a rotated native page | changes native evidence only on rotated pages | none | yes | **2.2-K**: census first, transform boxes into the display frame, add the `pdf_point` bounds check, four-angle synthetics |
| Discarded native `evidence_sha256` (~2.7× recomputation) | no | none | becomes load-bearing once native evidence is persisted (lineage, replay) | ≈ 0.06 s/doc today | yes, low effort | **2.2-K**: build once, persist in the OCR record, sha computed once |
| `analysis_input_sha` geometry-blind | **YES** — any cached geometry-fed run would be served stale text-only answers | stale-answer hazard | reviewed key change + `ANALYSIS_STAGE_VERSION` 17→18 + `run_of_record` | none | yes | **2.2-K**, first task |
| Tesseract word boxes (`--psm 6`, `.txt` only) | no | none | OCR stage bump; corpus-cache manifest change | re-run | defer | revisit only as a $0 disagreement instrument or a `local_free` geometry source if R8 makes Vast unavailable in production; not before 2.5 |
| `local_free` worker deployment | no (Vast is authorized for the evaluation) | none | separate partition by design | CPU latency unknown | yes, as a **measurement** | **2.5-F**; production choice is R8 |

Also noted as an open pin gap: host-side Paddle weight checksums are not verified (only versions and
model names are); recorded in M12, not scheduled.

---

## R. COMPARATIVE ANALYSIS — our system vs likely Ocrolus vs MoneyThumb

| Axis | Ours (phase2.1-final) | Likely Ocrolus | MoneyThumb | Verdict / action |
|---|---|---|---|---|
| Intake and modality triage | inspect profile (digital/scanned/mixed/unknown), preflight | parsable vs image-based; mixed-doc splitting; page-level UNKNOWN | four input classes; OCR only for scans | add native-layer probes and page-level classification (2.2, 2.5) |
| Document classification | none | 2,100+ types; tuple form type; uniqueness values; human fallback | none published (bank ID lookup) | build the deterministic classifier with sealed adjudication (2.2) |
| Extraction | native words; Tesseract text; Paddle words+boxes (pinned) | digitisation router over native/Amazon/Google/proprietary OCR | proprietary PinPoint OCR | keep; measure Paddle broadly; Unlimited gated (2.3, 2.6) |
| Layout generality | 84 template readers + a line-based structurer (5.3 % on unclaimed) | learned localisation + micro-templates + humans | one generic line/column heuristic + engine rules | build the LayoutModel (2.4/2.5) — the strategic gap |
| Transaction reconstruction | grammar per template; structurer chain test | row objects with bbox; polarity separate; balance chaining | date/currency anchors; sections; balance column ignored | row objects with word ids; header-first roles (2.4) |
| Reconciliation | per row and per statement: ledger identity to the cent, running-balance continuity, stated totals/counts, daily grid, page completeness, period, printed anchors | gate + signal + in-loop corrector; period-level residual and delta/ADB | totals-only; `alloweddiff`; values changed to reconcile | **we are ahead**; expose the residual structurally; never adopt the corrector |
| Confidence / review | verdict words; no fabricated score (OQ9) | field-level calibrated 0–1; humans; transactions binary-trusted | statement-level counts; "??" highlights | keep verdicts + reason codes; annotations only (all phases) |
| Provenance | spans; evidence sha; page tokens; word boxes (Paddle/native) | pixel bbox per transaction; page PK | `.map` page/position per transaction | evidence_refs on every published figure (2.5) |
| Completeness across statements | package layer (month map open, L-2) | activity active/missing; month gaps; BSIC | `balance_match`, `month_gap`, `daysMissing` | later phase (not Phase 2), noted for the package roadmap |
| Multi-account | independent validation; sibling omission with printed evidence; package membership by account | Account → Period → Transaction graph across files | auto-detected sequences | keep; the LayoutModel emits partitions (2.4) |
| Fraud / integrity | integrity checks; source contradiction; page coverage | Resistant AI forensics + ALGO + score | Thumbprint per-bank baselines + arithmetic | later phase; structural features as evidence (noted) |
| Determinism / replay | deterministic, cached, replayable, fail-closed | model + human, not replayable | deterministic engine, but value-editing | **our moat**; protect it with the tripwires in §E.4 |
| Human tail | refuse/review, no clean room | thousands of verifiers | none | do not imitate; refuse honestly |

What we already do similarly to Ocrolus: immutable page-level evidence with boxes; classification of
modality; enumerated outcomes; account/period/transaction independence; reconciliation as a gate. What
Ocrolus does better: breadth, classification, completeness across time, tamper forensics, throughput
with a human tail. What we do better: per-row proof, explicit direction, currency provenance,
determinism, replay, fail-closed publishing. Capabilities we are missing that this plan builds:
classification, layout generality, lineage in the UI, an honest second denominator, a holdout. Ideas
that would conflict with correctness-first and are rejected: reconciliation as an in-loop corrector;
confidence-routed acceptance; value edits to reconcile; a human clean room as the coverage strategy.

---

## Appendix — companion documents in this package

`PHASE2_REMAINDER_PLAN.md` (this file) · `research/OCROLUS_PRODUCT_MEMO.md` ·
`research/OCROLUS_INTERNALS_MEMO.md` · `research/MONEYTHUMB_MEMO.md` ·
`research/LAYOUT_RECONSTRUCTION_MEMO.md` · `research/UNLIMITED_OCR_MEMO.md` ·
`research/REPO_CORPUS_MEMO.md` · `research/REPO_GEOMETRY_MEMO.md` · `research/REPO_VALIDATOR_MEMO.md`
· `research/REPO_LEGACY_RULINGS_MEMO.md`.

Nothing in this package has been implemented. No repository code changed. The package is uncommitted
on `train11` pending Gustavo's review.
