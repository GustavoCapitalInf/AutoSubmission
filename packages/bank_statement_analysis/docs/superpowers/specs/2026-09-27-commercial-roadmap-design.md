# Commercial roadmap: from statement analyzer to lender software — design

- **Date:** 2026-09-27
- **Code read:** branch `lender-detection` in the main checkout, read only: tip `305a03a` when the first draft was written, `7c616f4` (the same code plus the merged NSF chips) at this revision. No git command was used to change anything, and neither `webapp_data` nor the Bank Statements folder was opened.
- **Owner:** Gustavo
- **Status:** third draft, written while the owner was asleep and revised twice after an independent review. Nothing here is approved. §12 lists every question the author would have asked, each with a recommended answer.
- **Revision 2 (2026-09-27):** L1's matching rules now require a direction witness (§5.4); L2 counts stacking across distinct lenders only and pools a lender's payments across its payment changes (§6.4); L1 stores its output in the artifact cache, so only L5a needs a schema migration (§4.2); all three model channels are fenced (§2, §7.4.9, §9.2); a cost model (§10.4) and a pilot operations section (§9.3) are new; the California source is corrected (§8.5, §10.1). In §12, Q4, Q11, Q16 and Q30–Q33 are new, Q10, Q20, Q27 and Q28 are revised, and the list is renumbered. (These are revision 2's numbers.)
- **Revision 3 (2026-09-27):** the rest of the review. §9.3 "Pilot operations" gains the coverage check, the security questionnaire, insurance, documentation, an availability statement and proven deletion; §9.2 names the privacy laws counsel covers. L1's dependency pin, page raster and export rows are stated exactly (§4.2, §5.4, §5.6, §5.7). The v5 migration moves existing statement content out from under the append-only triggers (§7.4.4, §7.6). Key rotation and secrets have a home (§7.4.5). L3's wait for L5a and the timing of L2's balance estimate are now owner choices (§4.2). Business types are counted on the 286 counted lenders (§6.2). The California attribution is corrected again (§8.5, §10.1). Doc paths are repository-relative. §12 is regrouped into "needed before §4.3 step 2 starts" (§12.1) and "can wait" (§12.2 before the pilot gate, §12.3 later) and renumbered: Q17 (L3 timing), Q27 (availability) and Q31 (coverage check) are new; Q13 (estimate timing), Q20, Q25 (monthly minimum) and Q30 (data return) are revised.
- **Kind:** an umbrella spec. It splits the roadmap into sub-projects. Each sub-project later gets its own spec, plan and implementation, the way lender detection did.
- **Citation note:** paths are relative to the repository root. `webapp/app.py` and `webapp/static/app.js` were being edited in the main checkout while this was written (their line numbers moved during the session). They are cited by function or route name. Every other file is cited by line, as read on 2026-09-27.

The program records this document cites (logs, rulings, reviews, plans, handoffs) were removed from the tree. [`docs/HISTORY.md`](../../HISTORY.md) says how to read them.

## 1. Why

The owner wants to license the analyzer to other lenders: MCA funders, equipment financiers and their brokers. Today it is an in-house tool. It reads statements, proves them against their own printed figures, computes the underwriting metrics under the ratified doctrines, and classifies every transaction. It has no users, no tenants and no access control, and its live PDF reader depends on an AGPL library.

Lenders pay for four things (market research, §10):
- catching forged statements at intake;
- true revenue, not total deposits;
- the merchant's existing positions and stacking;
- speed to an offer.

An orchestrator proposed ten "leaps". This spec:
1. turns them into independent sub-projects with dependencies and an order (§4);
2. gives a first-pass design for the three recommended first: evidence on the page (§5), position intelligence (§6), and accounts, tenants and security (§7);
3. sketches the other leaps (§8);
4. lays out a 12-month roadmap that makes a first paying pilot possible (§9);
5. adds business notes from the market research (§10), the risks (§11) and the owner's decisions (§12).

## 2. Where the product stands (verified in the code)

| Area | Today | Where |
|---|---|---|
| Reading | Phase 1 bank parsers over native PDF text; local Tesseract for scans. Three model channels, each off by default and behind its own switch: the legacy visual OCR rung (`baidu/Unlimited-OCR`), the visual pair, and hosted extraction (table below) | `ocr/native_text.py`, `webapp/worker.py:675-683` |
| Coverage | 2,625 of 3,380 archive statements validated (77.66%) at the batch-9 freeze; unchanged through Phase 2.2 | `docs/moneythumb-replacement/PROJECT_STATUS.md` |
| Text-first reader | **Spec only.** No `textfirst` package exists in this checkout | `docs/superpowers/specs/2026-09-24-text-first-reader-design.md` |
| Proof | Reconciliation and document-integrity flags; fail closed | `analysis/reconcile.py`, `analysis/pipeline.py:472` (`assess_document_integrity`), `:1227` ("not proof of fraud") |
| Metrics | Calendar-day ADB, NSF as negative printed days, withholding, eligible deposits, lender and flag-group totals, `monthly_lender_debits` | `analysis/metrics.py:36-157` (`Metrics`), `analysis/nsf_days.py`, `analysis/adb.py:207-241` |
| Classification | Research ledger of 1,085 entities (733 admitted, 99 review, 252 rejected, 1 owner ruling); 286 admitted counted lenders; eleven flag groups; D6 recurrence | `docs/lender-registry-ledger.json` (counted with a script), `analysis/classification_registry.py`, `analysis/transaction_classifier.py:95` (`CLASSIFICATION_VERSION = "5.2"`) |
| Evidence | Figure → exact rows (lender, potential-lender and flagged buttons filter the ledger). A page image preview at 100 dpi. **No link from a row to its page** | `webapp/app.py` route `page`; `app.js` `renderPreview`, `lenderEvidenceControl`; `analysis/transaction_classifier.py:125` (`source_page`, never set), `:2142` (`source_location="transaction:N"`) |
| Positions | Per lender: count and total only. Cadence exists only for flagged positions | `analysis/detect.py:19-32`, `:108-149`, `:196-246`; `analysis/cadence.py:15-36` |
| Storage | SQLite (WAL), schema v4, PDFs on disk by content hash, append-only `review_decisions`, `audit_log` and `telemetry` | `webapp/storage.py:70`, `:109-138`, `:169-252` |
| Access control | **None.** A job's uuid4 is the only secret. No users, no tenants; Settings is one file for everyone | `webapp/jobs.py:146`, `webapp/settings.py:23-34`, `webapp/app.py` `_server_config` ("no authentication (that is D-2b)") |
| Serving | waitress on loopback by default; account numbers masked in structured payloads; the source views stay unmasked by an accepted Wave 0 exception | `webapp/app.py` `main`, `_masked`, route `markdown` |
| Worker | One in-process thread, one job at a time | `webapp/app.py` `_process_job_queue`, `_enqueue_job` |
| API | The JSON routes work as an API with polling; `POST /package` takes a caller `reference` | `webapp/app.py` routes; `webapp/storage.py:205-209` (`packages.caller_reference`) |
| Licences | **PyMuPDF (AGPL-3.0 or a paid Artifex licence) is in the live native path** and in `requirements.txt`. Page images go through pdf2image and **poppler (GPL)**. pypdfium2 is used only by `vlm/` | `requirements.txt`; `import fitz` at `ocr/native_text.py:116` (and six more sites in that file), `ocr/inspect.py:197`, `webapp/artifact_cache.py:900`, `evidence/native.py:437`, `ocr/paddle_rung.py:37`; `ocr/rasterize.py:5`; `vlm/render.py:14`, `vlm/native_text.py:283` |

**The three model channels.** Each one can send page images or statement text to a model. A tenant rule must name all three (§7.4.9).

| Channel | Switch | Endpoint and fence | Where |
|---|---|---|---|
| Legacy visual OCR (default model `baidu/Unlimited-OCR`) | `OCR_VISUAL_PAIR_LEGACY_VISUAL=1` turns it on for Auto mode and for a forced OCR request | `OCR_BASE_URL`, default `http://localhost:8000/v1`. The endpoint policy allows loopback and private hosts by default and remote hosts only with `OCR_REMOTE_OPT_IN` set to its literal. The client is the `openai` package (Apache-2.0) | `ocr/config.py:139`, `:149-150`, `:171`; `webapp/worker.py:127`, `:682`; `ocr/endpoint_policy.py:41-48`; `ocr/ocr_client.py:560-567` |
| Visual pair (dots.mocr proposer, Qwen reviewer) | `OCR_ALLOW_VISUAL_PAIR=1`; a forced OCR request also reaches it when the legacy rung is off | Loopback URLs only (`:62-72`), which in practice are SSH tunnels to a rented GPU (`:3-4`). `execution_class="remote_paid"`; customer documents need `VISUAL_PAIR_REMOTE_CUSTOMER_DATA_OPT_IN` set to its literal | `ocr/config.py:169`; `webapp/worker.py:675-677`; `ocr/visual_pair_config.py:17-22`, `:43-44`, `:105-118` |
| Hosted extraction (Gemini) | `HOSTED_EXTRACTION_OPT_IN` set to its literal, plus `GEMINI_API_KEY` | Google's API | `analysis/pipeline.py:770-771`; `analysis/config.py:73-75` |

A loopback URL is not proof of local execution: the visual-pair module says so itself (`ocr/visual_pair_config.py:3-4`). The endpoint class therefore cannot be the tenant fence.

Two premises of the proposal did not hold:
- **The text-first reader is not built.** Only its spec exists.
- **There is no `webapp/auth.py`.** The Fly tryout's shared password is said to live on the Fly branch. That could not be confirmed, because git was off limits for this task.

The installed PyMuPDF reports its own licence as "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License". Both options are excluded by the owner's licensing ruling.

## 3. Rules this roadmap keeps

Every sub-project inherits these. None may be reopened by a sub-project spec; only the owner can change them.

- **ADB doctrine** (Gustavo, 2026-08-15; `docs/agent-handoffs/ADB-SPLIT.md:8-20`). One canonical underwriting ADB: the sum of end-of-day balances over every calendar day of the printed period, divided by the number of those days. Bank-reported averages are evidence only. One user-facing ADB. No funder-specific denominator profiles.
- **NSF** (R18 amended, 2026-09-22; `docs/moneythumb-replacement/PHASE2_RULINGS.md:507-540`). NSF = days that end negative, counting printed days by default. Carry-over is a Settings option. Returned items are evidence only.
- **Currency doctrine** (`docs/moneythumb-replacement/CURRENCY_DOCTRINE.md`). Native currency is canonical. No FX in the analysis layer. FX, if ever needed, happens in a separate lender layer that keeps the original amount, currency, rate, rate source and timestamp (§E). No cross-currency package math (§F).
- **MoneyThumb is a benchmark, never truth** (`docs/moneythumb-replacement/PROJECT_STATUS.md`, standing rules).
- **Anti-optimizer rule** (`docs/moneythumb-replacement/PHASE2_RULINGS.md:348-355`). The validator verifies; it never chooses among readings. Several plausible readings mean review or refuse.
- **Repair doctrine.** Parsers never write an amount.
- **L-1.** Never publish one account and silently drop another.
- **Ruling A** (`docs/moneythumb-replacement/PHASE2_RULINGS.md:137-151`). No automatic hop from a local reader to a hosted or remote extractor.
- **Customer-data authorizations are Capital Infusion's.** The Paddle, Unlimited and Vast rulings cover Capital Infusion's own statements. They do not extend to a licensee's customers.
- **Lender rulings** (`docs/superpowers/specs/2026-09-24-lender-detection-design.md` §2-§3). Flag groups never enter lender math or the package decision (D7). A stored record is never rewritten when it is served, and older analyses keep their labels until re-analysed (D12).
- **Protected modules** (`docs/moneythumb-replacement/MASTER_PLAN.md` §4): `analysis/adb.py`, `reconcile.py`, `metrics.py`, the classifier's precedence and evidence contract, `serialization.py`'s nulling rules, and the withholding-denominator contract. A change needs the owner's review and a green forensic audit.
- **Licensing** (owner, 2026-09-24). No AGPL/GPL and no paid-licence dependencies. Moving Phase 1 off PyMuPDF (and reviewing pdf2image/poppler) is a separate project. It starts after text-first's single-account slice passes zero wrong (text-first spec, ruling 12).
- **Privacy.** Statement text, customer names, account numbers and amounts never go into commits, commit messages, logs, tests, web searches or reports. Tests use fabricated data only.
- **How work runs.** For each service, one Opus 5.5 agent implements, an independent reviewer checks, and the orchestrator checks every report's evidence. The owner merges.

## 4. Sub-projects, dependencies and order

### 4.1 The sub-projects

Sizes are rough calendar estimates for one orchestrated team. Each sub-project's own spec re-estimates.

| ID | Sub-project | Leap | What it delivers | Rough size | Needed for the first external pilot? |
|---|---|---|---|---|---|
| T | Text-first reader | 9 | Spec approved; slices 0 and A, then B and C | ~3 weeks for 0+A (spec §10) | No, but it gates L0 |
| L0 | Licence clean-up | — | Phase 1 native text and page rasters on pypdfium2; PyMuPDF and poppler out of the served path; a licence check in CI | 3–6 weeks | **Yes** |
| L1 | Evidence on the page | 1 | Every row and headline figure opens on the PDF page with its line boxed; a reconciliation proof panel | ~4 weeks | Yes (differentiator) |
| L2 | Position intelligence | 2 | Per-lender payment streams, funding dates, status, stacking signals; balance estimates only under stated assumptions | 3–4 weeks | Yes (differentiator) |
| L5a | Identity, roles, tenancy, audit events | 5 | Sign-in, roles, `tenant_id` on every record (schema v5), tenant-scoped reads, per-tenant settings files, CSRF, audit events | 4–6 weeks | **Yes** |
| L5b | Encryption, retention, logging, hosting | 5 | Envelope encryption, retention and deletion, privacy-safe logging, backups, the `TENANT_MODE=external` egress fence, a dedicated-instance deployment | 3–4 weeks | **Yes** |
| L5c | SOC 2 programme | 5 | Policies, controls, evidence; Type I, then a Type II window | Months elapsed; mostly process | Readiness only |
| L5d | Pooled multi-tenancy | 5 | Shared database and workers for many small tenants | 6–10 weeks | No |
| L3 | Learning loop | 3 | Analyst decisions on potential lenders; per-tenant aliases; a reviewed path into the shared registry | 3–4 weeks | No |
| L4 | Fraud and tampering signals | 4 | Structural PDF forensics, revision recovery with the edit boxed on the page, package balance continuity | 3–5 weeks (v1) | No (parity item) |
| L6 | Integrations | 6 | API v1 with keys, OpenAPI and webhooks; then email intake, a CRM connector, open banking | 2–3 weeks for API v1; each connector 2–4 weeks | API v1 by the second pilot |
| L7 | Lender rules and offer calculator | 7 | Per-tenant credit-box rules on canonical metrics; offer and estimated-APR calculator | 3–5 weeks + counsel review | No |
| L8 | Published accuracy benchmark | 8 | A reproducible method, a sealed-holdout exam, a public summary | 3–4 weeks + adjudication time | No |
| L9 | Coverage and cost per page | 9 | Per-tenant coverage and cost telemetry; text-first slices B and C; scan-path economics | Ongoing | No |
| L10 | Verified revenue | 10 | The owner's next project; its own spec | Its own spec | No |

### 4.2 Dependencies

- **T (slice A) → L0.** Text-first spec, ruling 12.
- **L0 → any external pilot.** The owner has ruled PyMuPDF a no-go for licensing. Hosting AGPL code for another company is the case the AGPL's network clause targets (counsel to confirm). Poppler is GPL.
- **L1** waits for no other sub-project. It needs one line in `requirements.txt`: pypdfium2 is listed today only in `requirements-vlm.txt`, as `>=5.8`. Text-first slice 0 adds `pypdfium2==5.8.0` (text-first spec, §4.4 and §10). L1 carries the same pin itself, so it does not wait for slice 0; whichever merges second finds the line already there. Its display raster change can land before L0.
- **L2 v1** depends on lender detection (merged on this branch). **L2's balance estimate** needs a factor the tenant sets. On a dedicated instance (§12 Q3 (a)), today's global Settings already belong to one tenant, so the estimate can ship in L2 v1. On a shared host or a pooled service it needs L5a's per-tenant settings files. Lender-specific factors need L7. When it ships is an owner choice (§12 Q13).
- **L5b → L5a.** **L5c** needs L5a and L5b in place, because they are the controls it audits. **L5d → L5a, L5b.**
- **L3 after L5a** is a product choice, not a technical dependency. `review_decisions.actor` is free text today (`webapp/storage.py:223`; `webapp/app.py` `_review_actor`, "Free text until authentication exists (D-2b)"), and revenue review already ships on it. L3 v1 could start now on the house tenant with the same free-text actor, and gain signed-in actors when L5a lands. The recommendation waits for L5a, so that every lender decision a licensee sees carries a real actor from its first day (§12 Q17). L3 is better with L1, because the analyst sees the row on the page before deciding.
- **L4 → L1** for "show the edit on the page". Its forensics use pypdfium2, so they do not wait for L0.
- **L6 (API v1) → L5a** for API keys. **Email intake and CRM connectors → API v1.**
- **L7 → L2, L5a** and the currency doctrine §E.
- **L8 →** the sealed holdout and adjudication (R3, R4), and **L0**, so the benchmark measures the engine that ships.
- **L10 → L1, L3** (the owner's spec decides).

**Schema migrations are assigned here.** `SCHEMA_VERSION` is one integer (`webapp/storage.py:70`), the migrations form a forward-only chain (`:155-162`), and a store refuses a schema newer than its code (`:323-327`). Two branches that each ship "v5" cannot both merge. So:
- **L5a takes v5.** It is the only sub-project in §4.3 step 2 that needs a migration.
- **L1 needs none.** It stores its output as a new artifact-cache stage (§5.4). The cache index accepts any stage name (`webapp/artifact_cache.py:719`, `webapp/storage.py:80-96`).
- **L2 needs none.** It computes at serve time (§6.3).
- Any later sub-project that needs a migration takes the next free number when its plan is approved, and only one schema-changing branch is open at a time.

### 4.3 Order

1. **Now:** the owner reads this spec and the text-first spec. Text-first slices 0 and A proceed as planned.
2. **In parallel, starting now** (no dependency on T): L1, L2 v1, L5a. Then L5b.
3. **After text-first slice A passes zero wrong:** L0.
4. **Pilot gate** (§9.2): L0, L5a, L5b, L1 v1 and L2 v1 done, plus the legal and operations items. The first external pilot starts.
5. **Months 3–6:** L6 API v1, L4 v1, L3 v1, the L5c Type I report, L8 method and first sealed exam.
6. **Months 6–12:** L7, the L8 publication, L6 connectors and email intake, the shared-host shape and then L5d if the tenant count warrants it (§10.4), Type II, L10.

The critical path to a pilot is **T slice A → L0 → pilot gate**. Everything else in §4.3 step 2 fits inside it.

## 5. L1 — Evidence on the page

### 5.1 Goal

Every published row and every headline figure opens on the original PDF page, with the printed line boxed. The statement's own proof is shown: opening balance + credits − debits = closing balance, with each term boxed where the statement prints it.

Non-goals for v1:
- boxes on scanned pages (they get the page only, when it is known);
- annotating or exporting the PDF;
- fraud edit highlights (L4 reuses this overlay).

### 5.2 What exists

- **Page images.** Route `page` in `webapp/app.py` returns a 100-dpi PNG of the stored PDF through `ocr.rasterize.rasterize_page`, which uses pdf2image and poppler (`ocr/rasterize.py:5`) and renders the CropBox (RASTER_VERSION 2 note, `ocr/rasterize.py:21-32`). The dashboard shows it in `renderPreview` (`app.js`), with previous and next buttons.
- **OCR region boxes.** Route `render` draws the legacy visual OCR's detected regions (`ocr/render.py`). It applies to that reader only.
- **Figure → rows.** `lenderEvidenceControl` and the flagged table filter the ledger to the exact rows (`app.js`). Package rows carry `source_job`, `source_document` and, for multi-account members, `source_account` (`webapp/app.py` `_package_analysis`).
- **Row identity is an ordinal.** `source_location="transaction:N"` within its account (`analysis/transaction_classifier.py:2142`). `TransactionClassification.source_page` exists (`:125`) but no caller sets it. `Transaction` has no page or box. It does carry a signed `amount`, a `direction` ("debit" or "credit") and an optional printed `running_balance` (`analysis/schema.py:104-113`).
- **Geometry exists but is not linked to rows:**
  - the canonical word and line contract, with `pdf_point` frames and 0-based `page_index` (`evidence/canonical.py:1-58`);
  - PyMuPDF word boxes attached to native reads (`ocr/pipeline.py:110-112`, `evidence/native.py:400-412`) and cached (`webapp/artifact_cache.py:1240-1268`). This path is AGPL, so L1 must not build on it;
  - visual-pair rows carry `page`, `locator` and the **table block's** bbox (`vlm/assemble.py:23-35`, `:476`). This provenance stays in private audit evidence (`vlm/pair_adapter.py:7`);
  - markdown pages are separated by `--- Page N ---` (`ocr/document.py`).
- **A money grammar** for printed amounts, including comma-decimal forms, already reads the text layer through pypdfium2 (`vlm/native_text.py:30-40`, `:281-297`).
- **Daily balances** carry their source: `bank_daily_summary`, `reconstructed` or `carried` (`analysis/adb.py:207-213`).
- `docs/moneythumb-replacement/MASTER_PLAN.md` P3 already names "dashboard source-document viewer using the existing (currently dead) page-image endpoints".

### 5.3 Approaches

**A. Parsers record where each row came from.** Each Phase 1 parser (about 80 modules under `analysis/`) would carry a page for every row, as `docs/moneythumb-replacement/MASTER_PLAN.md` AD-2 planned.
- For: exact where it works.
- Against:
  - it touches every parser and the protected `Transaction` schema, and every change needs the byte-identical corpus proof;
  - parsers read markdown text, not geometry, so they could give a page but never a box;
  - months of work.

**B. A locator that runs after analysis (recommended).** A new module reads the PDF's own text layer with pypdfium2. It finds each published row's printed amount, and its date or running balance, on one line.
- For:
  - it changes no parser, no figure and no stored record;
  - it works for any reader whose PDF has a text layer: Phase 1, text-first, and the visual pair on mixed documents;
  - it is licence-clean.
- Against:
  - it can fail to decide, when the same key is printed twice or a line holds no date. The rule is then "no box", never a guess.

**C. The browser finds rows.** Ship the PDF to the dashboard and search its text layer with PDF.js (Apache-2.0).
- For: no server change.
- Against:
  - the matching rules live in JavaScript, outside the Python test floor;
  - the whole PDF, with the unmasked account number in its text layer, goes to every browser;
  - a package needs every member's PDF.

**Recommendation: B.** PDF.js stays a candidate for a later, richer viewer.

### 5.4 Design

**Components**

| Component | Owns |
|---|---|
| `locator/` (new top-level package). It imports only the standard library and pypdfium2, and nothing from any repository package. `evidence/` is the model for the boundary, not for the import: its one third-party import is `fitz`, lazily inside `native_evidence_from_pdf` (`evidence/native.py:437`), pinned by an AST test (`tests/test_evidence_boundary.py:30-32`). An AST test pins `locator/`'s pypdfium2 import the same way | `text_layer.py`: per page, characters with loose boxes → words → lines, in the page's display frame. `tokens.py`: money and date tokens. `match.py`: the rules below. `model.py`: the output types |
| `webapp/row_locations.py` | Runs the locator for a job, stores the result, serves it |
| Storage | A fourth artifact-cache stage, `STAGE_LOCATIONS = "locations"`, beside the three at `webapp/artifact_cache.py:574-576`. Input: a SHA-256 over the PDF's content hash and the analysis JSON's hash. Settings key: `locator_version` and the stage version. The output is derived and recomputable, so it is not append-only. No schema migration is needed (§4.2) |
| Route `GET /locations/<job_id>` | Returns the cached locations; computes them on a miss, within a time budget. A job analysed before L1 is served the same way |
| `requirements.txt` | Gains `pypdfium2==5.8.0`, the version text-first slice 0 pins. Today pypdfium2 is only in `requirements-vlm.txt` (`>=5.8`). L1 carries the pin itself, so it does not wait for slice 0 (§4.2) |
| Route `page` | Renders with pypdfium2 instead of poppler, keeping today's 100 dpi (a scale of 100/72 on the page's size in points). pypdfium2 is already the renderer in `vlm/render.py`, which sizes pages to a 1,540-px long edge by default (`DEFAULT_LONG_EDGE`, `vlm/render.py:19`) and uses a dpi only when one is passed (`:126`). The route renders the CropBox at the page's display rotation, the frame the locator uses. The OCR rasters are left to L0 |
| Dashboard | Row page links, the box overlay, summary-tile anchors, the proof panel, and links from the daily-balance list |
| Exports | The CSV/XLSX sheet has three columns, `section, field, value` (`webapp/app.py` `_analysis_csv`, `_analysis_rows`; the header is pinned in `tests/test_webapp_app.py:123`). So the page arrives as rows, not as a column: a `locations` section, one row per located or page-only posting, with the row key as the field and the 1-based page as the value. The header does not change. Export tests that pin a whole sheet gain these rows and are updated in the same change |

**Data flow**
1. The worker finishes the analysis (`webapp/worker.py` `run_job` → `store.set_result`).
2. The adapter calls `locate(pdf_bytes, rows, figures)`:
   - `rows`: for each account and posting, the account index, `source_location`, date, signed amount, direction, description and printed running balance, read from the stored payload;
   - `figures`: opening and closing balance, the stated totals the payload carries, and the daily balances whose source is `bank_daily_summary`.
3. The result goes into the `locations` cache stage, keyed by the PDF's hash and the analysis JSON's hash. A re-analysis changes the analysis hash, so its locations are recomputed. After L5a the tenant joins the key material, like every other stage (§7.4.3).
4. The dashboard fetches `/locations/<job_id>` when the preview opens. `/analysis/<job_id>` is unchanged, byte for byte, so no payload pin moves.
5. In a package, each row's `source_job` selects the member whose locations and page to show.

**Matching rules (v1)**
1. Only pages with a text layer take part. Characters in invisible render mode never count.
2. **Key.** A row's key is its amount to the cent, its direction and its date. Its candidate lines are the lines, on any page, that hold a money token equal to the amount. Many layouts print debits without a sign, so the token alone does not say the direction.
3. **Direction witness.** A candidate line has a direction when one of these holds:
   - the money token sits inside the x-range of a column whose header, on that page, is a credit header (deposits, credits, additions, and the French forms) or a debit header (withdrawals, debits, payments, checks, and the French forms), from a closed vocabulary;
   - the line sits under a section heading from a closed vocabulary ("deposits and other credits", "withdrawals and other debits", "checks paid", and the French forms). The heading is found above the line on the same page, or carried over from the previous page when no other heading comes between;
   - the money token prints its own sign, or a CR or DR marker.

   A candidate whose direction contradicts the row's is dropped. A candidate with no direction witness stays a candidate for rows of **either** direction.
4. **Strong.** A candidate is strong when the same line also holds:
   - the row's printed running balance, when the row has one; or
   - a date token equal to the row's date (month and day; the year when printed); or
   - for layouts that print the date once per group: at least two of the first four normalized description tokens.
5. **Accept** only when exactly one strong candidate remains for the row. When several remain, the description may break the tie: if exactly one of them also holds at least two of the row's first four normalized description tokens, that one is accepted. There is one further exception. When k rows are identical in every published field (date, signed amount, direction, description, and running balance or its absence), and exactly k strong candidates remain with the same direction witness, the rows take those lines in reading order. Every one of those lines prints the same posting, so no assignment can show a different one. In every other case the status is `ambiguous` and no box is drawn. In particular:
   - a credit and a debit of the same amount on the same date, on lines with no direction witness, are both `ambiguous`;
   - rows that share a key but differ in description are never assigned by reading order. Parsers emit a date-ordered ledger, which need not follow page order: sectioned layouts list credits and debits apart, and some list checks by number.
6. **Self-check.** Re-read the text inside the chosen box (`get_text_bounded`). It must contain the tokens that made the match, or the location is dropped. This check cannot tell two lines that both hold the tokens apart; rules 3 and 5 exist for that.
7. **Box.** The union of the matched tokens on that line, padded by 2 pt. It is never the whole line, so a table printed two-up still boxes the right half.
8. **Summary anchors.** A figure is anchored on the one line holding its money token and a label from a closed vocabulary: beginning, opening, previous, ending or closing balance; total deposits or credits; total withdrawals or debits; and the French forms such as `SOLDE`, as in `vlm/assemble.py:15-20`. Two such lines means no anchor.
9. **Daily balances.**
   - A `bank_daily_summary` day is located like a row: date and amount on one line.
   - A `reconstructed` day points at the last row of that day.
   - A `carried` day points at the previous established day.
10. **Page only.**
    - A scan read by Tesseract: the row's amount found exactly once in one page's markdown gives the page and no box.
    - A visual-pair row: its `CandidateRow.page` passes through the adapter, if the plan finds it reachable, and gives the page. Its bbox is the table block, so it is not drawn as a row box.
11. The locator never changes an amount, a date or a description. It never uses reconciliation to choose (anti-optimizer rule).

**Frame.** pypdfium2 character boxes are in PDF user space, with the origin at the bottom left. The locator converts them to the CropBox display frame: origin at the top left, y growing downward, page rotation applied. This is the `pdf_point` convention of `evidence/canonical.py`, and the frame the page raster shows. Each page records its width and height in points. The dashboard places a box as percentages of the page's width and height, so the raster's dpi never matters.

**Output contract (per job)**
```
{
  "locator_version": 1,
  "analysis_sha256": "<hex>",
  "pages": [{"index": 0, "width": 612.0, "height": 792.0, "text_layer": true}],
  "rows": {"<account>|transaction:<n>": {"status": "located", "page": 0,
            "box": [x0, y0, x1, y1], "matched": ["amount", "running_balance"]}},
  "anchors": {"<account>|opening_balance": {"status": "located", "page": 0, "box": [...]}},
  "daily": {"<account>|<yyyy-mm-dd>": {"row": "<account>|transaction:<n>"}},
  "counts": {"located": 0, "page_only": 0, "ambiguous": 0, "not_found": 0, "no_text_layer": 0}
}
```
Status is one of `located`, `page_only`, `ambiguous`, `not_found`, `no_text_layer`. The account key is the account's index in `payload_accounts` order (`analysis/payload_shape.py`). A single-account payload uses `0`. The contract holds no text and no amounts: nothing in it needs masking.

**Dashboard**
- **Ledger rows.** A located or page-only row shows a "p. N" link. Clicking it moves the preview to that job and page and draws one box. A page-only row shows the page with the note "This row is on this page; its line could not be boxed."
- **Summary tiles.** Opening, closing and total-deposit tiles link to their anchors.
- **Proof panel.** "Opening + credits − debits = closing", each term linked to its anchor, beside the reconciliation checks the analysis already publishes.
- **ADB.** The tile opens the daily-balance list, and each day links to its evidence. The ADB value itself does not change.
- **Accessibility.** The overlay colour is a theme token that works in dark mode, and every link is keyboard reachable.

### 5.5 Error handling

- **Advisory only.** Any exception leaves the job and its analysis untouched. The locations record says `unavailable` with the exception's class name only, following `webapp/worker.py` `_stage_failure`.
- **Time budget.** A per-document budget (for example 10 s, configurable) is enforced. Rows not reached are `not_found`, and the counts say so.
- **Odd page geometry.** Rotated pages, a CropBox offset from the MediaBox, and text outside the crop box go through the frame conversion. A box outside the page is never drawn.
- **Stale locations.** A hash mismatch recomputes them. They are never served against a different analysis.
- **Bad files.** Encrypted or unreadable PDFs never reach the locator; they are refused at upload.

### 5.6 Testing

- **Fabricated PDFs only**, built without PyMuPDF (text-first slice 0 plans such a builder; share it). Cases:
  - one row per line;
  - the date printed once per group;
  - identical rows on one day (reading-order assignment allowed);
  - two rows with the same date, amount and direction but different descriptions (both `ambiguous` unless the description separates them);
  - a sectioned layout (credits listed, then debits) with a credit and a debit of the same amount on the same date: `ambiguous` with no column headers or section headings, `located` when either is printed;
  - a section heading that carries over to the next page;
  - a checks section listed by check number rather than by date;
  - a two-up table;
  - a rotated page and a CropBox offset;
  - comma-decimal amounts;
  - French month names;
  - invisible text that must not anchor;
  - a label printed twice (no anchor).
- **Frame agreement.** The `page` raster renders the CropBox at the page's display rotation: on a fabricated page with `/Rotate 90` and a CropBox offset from its MediaBox, the raster's size matches the display frame's width and height at the route's scale, and the box drawn on it covers the glyphs.
- **Payload pin.** `/analysis` is byte-identical with and without L1.
- **Export.** The CSV and XLSX sheets equal today's plus the `locations` rows, and nothing else moves.
- **Dashboard.** The overlay and links are tested through `tests/webapp_js_harness.py`.
- **Local, read-only measurement** on the validated archive, reporting counts only and never committed:
  - located, page-only, ambiguous and not-found shares by bank family;
  - a hand check of a stratified sample of 300 located rows across at least 30 banks.

### 5.7 Success criteria

1. **Zero wrong boxes** in the hand-checked sample. A wrong box is one whose line differs from the row in any printed field: date, amount, direction, description or running balance. The sample over-weights sectioned layouts and days with repeated amounts.
2. On validated digital statements, **at least 95% of rows located** and at least 98% at least page-located. These are targets; the first measurement may reset them, with the owner's approval.
3. No published figure moves: every metric, total and decision, the `/analysis` payload, the corpus-gate result and the cold-run result stay byte-identical. The export sheets change only by the added `locations` rows (§5.4), and their pins are updated for those rows alone.
4. The display raster no longer calls poppler.
5. In a browser check, an underwriter reaches the boxed debit lines behind a lender total in two clicks.

Services: S1 the `locator/` package; S2 the adapter, storage, route and raster; S3 the dashboard; then the measurement.

## 6. L2 — Position intelligence

### 6.1 Goal

For every counted lender an account pays, show the position:
- the payment amount and rhythm;
- first and last payment;
- the funding credit, when the statements show it;
- whether it is still running at the end of the statements.

Across the package, show signals for new and stacked positions. Estimate a remaining balance only when the funding is visible and the tenant has stated a factor.

Non-goals: predicting default; lender-specific offer math (L7); any cross-customer position database (§8.3, §12 Q34).

### 6.2 What exists

- **Confirmed lenders.** `FunderMatch` holds funder, alias, rows, evidence, `debit_count` and `total_debited` (`analysis/detect.py:19-32`). It is built by `_group_funders` from rows with `contributes_to_lender_totals` (`:108-149`) and serialized by `_funder_dict` (`analysis/serialization.py:31-73`).
- **The package roll-up** keeps documents, count and total per funder (`webapp/app.py` `_package_analysis`, the `known_funders` loop). The lender table shows count, total and "Across N statements" (`app.js` `lenderRowHtml`).
- **Cadence.** `describe_cadence` (daily, weekly, biweekly, monthly, irregular, single; `analysis/cadence.py:15-36`) serves only flagged positions (`analysis/detect.py:196-246`, `webapp/app.py` `_add_flagged_rows`). `classify_cadence` (daily or weekly) gates promotion and must not move (`analysis/transaction_classifier.py:1817-1828`).
- **Funding credits (D1).** A financing-group credit is `non_revenue` with match method `financing_proceeds_credit` (`analysis/transaction_classifier.py:773-793`). It sets `contributes_to_lender_credit_exclusion` (`:1048-1053`). Its entity is `revenue_canonical_entity` (`:139`). Credits and debits use the same `match_known_payee`, so a funder's credit and its debits carry the same entity name (`:1186-1205`). Payout-credit entities and factoring are excluded by ruling.
- **Business type** lives in the ledger as free text. The validator checks only that it is a non-empty string (`tools/lender_ledger.py:294`), and the ledger's 1,085 entities hold 164 distinct values. For L2 the number that matters is the **286 admitted counted lenders** (group `confirmed_lender`, status `admitted`). They use exactly three values: 186 `mca_or_revenue_based_funder`, 80 `equipment_finance` and 20 `online_business_term_lender` (counted with a script on 2026-09-27). Business type never reaches the runtime registry: `tools/build_lender_registry.py:104` writes it only into the evidence markdown.

### 6.3 Approaches

**A. Extend analysis-time detection** (`FunderMatch`, `analysis/serialization.py`).
- Against:
  - saved statements need re-analysis before they show positions;
  - `serialization.py` is protected;
  - a tenant's assumptions (a factor) would be frozen into stored records.

**B. A serve-time position engine (recommended).** A pure module computes positions from the rows the stored payload already carries, when a statement or package is served. This is the pattern `analysis/flagged_view.py` and `analysis/nsf_days.py` already use through `_displayed`.
- For:
  - every saved statement gets positions at once;
  - a tenant's settings apply without re-analysis;
  - no protected module changes.

**C. Package only.** Compute positions in `_package_analysis` alone.
- Against:
  - a single statement shows nothing;
  - the logic grows inside the Flask module that `docs/moneythumb-replacement/MASTER_PLAN.md` AD-3 wants to move out.

**Recommendation: B.** One pure module serves both the statement and the package paths.

### 6.4 Design

**Component.** `analysis/positions.py`: pure functions over plain payload dicts, with no I/O. It imports `analysis/cadence.py`, `analysis/dates.py`, `analysis/payload_shape.py` and a new registry table of business types.
- `positions_for_rows(rows, *, coverage, settings)` returns positions (each with its streams and links), unconfirmed streams and signals.
- `apply_positions_to_payload(payload, settings)` returns a copy with `positions` on each account. `_displayed` calls it after the flag groups.
- `_package_analysis` groups member rows by account key and lender, then calls `positions_for_rows`.

**Inputs**
- **Debits:** rows with `contributes_to_lender_totals`, keyed by `canonical_entity`. These are the same rows today's totals use.
- **Funding credits:** rows with `contributes_to_lender_credit_exclusion` whose `revenue_canonical_entity` is a counted-lender entity.
- **Unconfirmed:** rows with `contributes_to_potential_lender_totals`. They are shown apart and never counted.

**Definitions**
- **Account key:** the bank plus the account number's digits, read from the stored payload before masking. A statement without an account number is its own key. Streams never merge across keys. Package signals count across all keys.
- **Stream:** one lender's debits on one account key with the same amount to the cent, on at least three different dates. A lender's other debits are "other payments". A stream carries:
  - lender and business type;
  - amount;
  - cadence and average gap (`describe_cadence`);
  - count and distinct dates;
  - first and last date;
  - total paid;
  - share of eligible deposits over the same statements (the withholding formula, per stream);
  - source locations.
- **Position:** one lender's streams on one account key, linked in date order. A lender that changes its payment amount produces a new stream, not a new position. Two consecutive streams of the same lender on the same key are **linked** when the later stream's first payment comes no later than the earlier stream's active window after its last payment (the status table below), and the two share at most two dates. A link is:
  - a **renewal** when a funding credit from that lender on that key falls inside the funding window before the later stream's first payment;
  - otherwise a **payment change**: a true-up, a hardship reduction, or a renewal whose funding went to another account. The product shows the change and never guesses its reason.

  Two streams of one lender on one key that share more than two dates are **concurrent**: two positions with the same lender. They show as two positions with the note "same lender, two payments at once", and never as stacking.

  A lender's debits that belong to no stream ("other payments") are attached to that lender's position on the same key whose first-to-last span holds their date. Otherwise they are listed apart.
- **Funding link:** the latest funding credit from the same lender on the same account key, dated on or before the first payment it funds, and no more than 10 days before it (a setting; §12 Q14). It gives `funded_on` and `funded_amount`. A funding credit with no stream after it is reported as "funded, no payments seen yet".
- **Status** of a position is the status of its latest stream, at the end of the account's latest statement:

  | Cadence | `active` when the last payment is within |
  |---|---|
  | daily | 7 days |
  | weekly | 10 days |
  | biweekly | 18 days |
  | monthly | 35 days |
  | irregular or single | 30 days |

  Otherwise the stream is `stopped`, with its last date. The product never says why a stream stopped (paid off, refinanced, or a stop-payment).
- **Estimated remaining balance.** Shown only when the position's latest funding link gives `funded_amount` **and** the tenant has set `position_factor_rate`:
  - payback = funded amount × factor;
  - paid = **every** debit from that lender on that account key dated on or after `funded_on`: all the position's streams after a payment change, and its other payments;
  - remaining = max(payback − paid, 0);
  - payments left = ⌈remaining ÷ the latest stream's amount⌉;
  - estimated payoff = last date + payments left × the latest stream's average gap.

  It is always labelled "Estimate", with the factor shown. After a renewal it adds "the credited amount may be net of an earlier balance", because a renewal often pays off the old balance out of the new funding. Otherwise the field reads "Not estimable from these statements".
- **Signals.** They are advisory and never touch the package decision (the D7 analogue; `webapp/app.py` `_package_analysis`, the `decision` rule):
  - `active_positions`: active confirmed positions, counted per lender and account key;
  - `new_positions`: a position whose first stream starts after the first 14 days of its account's coverage, or a funding link inside the coverage that starts a position. A payment change or a renewal is never a new position;
  - `renewals`: renewal links inside the coverage;
  - `stacking`: a new position from one lender that starts on a date when a position from a **different** lender is active. A position is active on a date when its first payment is on or before that date and its last payment is no earlier than that date minus its active window. The count is over distinct lenders. One lender's payment changes, renewals and concurrent streams never raise it. Equipment financing is left out by default (§12 Q16);
  - `unconfirmed_active`: active potential-lender streams.

**Currency.** Every stream is in its account's currency. Package-level sums across currencies are refused, the way `_CROSS_CURRENCY_TOTAL_KEYS` already works (currency doctrine §F). The factor is unitless.

**Registry.** `tools/build_lender_registry.py` renders a new `LENDER_BUSINESS_TYPES` table into `analysis/classification_registry.py`, the one module the no-hardcode guard exempts. The build normalises the free-text field to a closed vocabulary before it renders: `mca_or_revenue_based`, `equipment_finance` and `online_term`, the three values the counted lenders use today. The table covers counted lenders only. A counted lender whose value maps to none of the three fails the build, so a new free-text value cannot slip in and change what `stacking` counts; widening the vocabulary is a reviewed change.

**Settings.** These are global until L5a makes settings per tenant. On a dedicated instance, global already means one tenant (§4.2):
- `position_factor_rate` (none by default);
- `position_funding_window_days` (10);
- whether equipment financing counts toward `stacking` (§12 Q16).

`webapp/settings.py` `DEFAULTS` is `dict[str, bool]` today (`:26-34`), so it grows a typed schema with range checks.

**Payload (served copy, additive)**
- Per account: `positions: {"positions": [{..., "streams": [...], "links": [...]}], "unconfirmed": [...], "signals": {...}}`.
- Per package: the same shape. Each position adds `documents`, and its evidence carries `source_job` and `source_account`.

**Dashboard.** A Positions panel beside the lender table:
- one row per position; columns: Lender, Type, Payment (the latest amount and rhythm, with earlier amounts listed as payment changes), First–last, Paid, Funded (date and amount), Status, and Est. remaining when available;
- one plain signal line, for example "2 active positions; a new position started while another was active". It never says approve or decline;
- clicking a position or one of its streams filters the ledger, and with L1 opens the page.

**Exports.** `position_<n>` rows go through the escaped-row path of the CSV/XLSX writers.

### 6.5 Error handling

- **Never refuses.** It is a presentation step, like `flagged_view`. A payload in neither published shape passes through unchanged.
- **Bad dates.** Rows with unparseable dates count in the totals but not in cadence, first or last.
- **Settings.** A factor outside a sane range (for example below 1.0 or above 3.0) is refused when Settings is saved, never at serve time.
- **Mixed currencies.** A package with mixed currencies shows positions per account and refuses the package-wide sums.

### 6.6 Testing

- **Fabricated rows:**
  - daily and weekly streams with weekend and holiday gaps;
  - one lender lowering its daily amount (a hardship reduction): one position, one payment change, no `new_positions`, no `stacking`;
  - one lender raising its amount with a one-day overlap (a true-up): the same result;
  - a renewal with its funding credit: one position, one renewal, no `stacking`, and an estimate that carries the renewal note;
  - a renewal whose funding went to another account: a payment change, no `stacking`;
  - the balance estimate across a payment change: paid counts both streams from `funded_on`;
  - two concurrent streams from one lender: two positions, the same-lender note, no `stacking`;
  - a second lender starting while the first is active: `stacking`;
  - the same with an equipment lender: no `stacking` under the default;
  - funding with and without a stream;
  - a multi-account document;
  - a cross-currency package.
- **Rulings:**
  - payout-credit entities and factoring credits never become funding;
  - potential lenders are never counted;
  - the package decision is byte-identical with positions on and off.
- **Settings:** a round trip, and range refusals.
- **Dashboard:** the panel, through the JS harness.
- **Local census,** read-only and counts only:
  - active positions per package;
  - funding links found;
  - renewals and payment changes;
  - `stacking` signals, each hand-checked on a sample for a second, distinct lender;
  - a check that streams plus other payments equal today's `total_debited` for every lender.

### 6.7 Success criteria

1. For every statement and package, a lender's streams plus its other payments equal today's `total_debited`. No money is created or lost.
2. Lender count, lender totals, withholding and the package decision do not change.
3. On a sample of 100 packages, the owner's underwriters agree with status, links and funding in at least 95% of positions (a target the owner sets).
4. An estimate never appears without both inputs, and it is always labelled.
5. **No signal from a single lender's amount change.** In the fabricated cases and in the census, a payment change, a renewal or a concurrent stream from one lender never raises `stacking` or `new_positions`.

## 7. L5 — Accounts, tenants and security

### 7.1 Goal

Another lender can use the product safely:
- every request is authenticated;
- every record belongs to one tenant;
- roles decide what each person can do;
- there is a complete audit trail;
- data is encrypted at rest;
- there are retention and deletion, logging and backups;
- the evidence a SOC 2 auditor asks for exists.

Non-goals for v1: self-service sign-up and billing, SCIM provisioning, and pooled scaling beyond a handful of tenants (L5d).

### 7.2 What exists and what is missing

- **Exists:**
  - durable SQLite with forward-only migrations (`webapp/storage.py:1-49`, `:70`, `:73-162`);
  - append-only review decisions, audit log and telemetry (`:109-138`, `:228-251`);
  - export events logged;
  - the data directory kept outside the checkout (`:268-275`, `ocr/private_artifacts.py`);
  - account numbers masked in structured payloads (`webapp/app.py` `_mask_account`, `_masked`);
  - error text withheld from responses and the job store (`webapp/worker.py:169`, `_stage_failure`);
  - upload limits of 100 MB, 25 files and 500 pages (`webapp/app.py` `MAX_UPLOAD_*`);
  - waitress on loopback, JSON-only mutating routes;
  - a fence on each of the three model channels (§2): the endpoint policy (`ocr/endpoint_policy.py:159-182`), the visual pair's customer-data opt-in (`ocr/visual_pair_config.py:105-118`) and the hosted-extraction opt-in (`analysis/pipeline.py:770-771`).
- **Missing:**
  - any sign-in;
  - users, roles and tenants: no table has an owner column (`webapp/storage.py:169-235`);
  - the Recent list lives in the browser's `sessionStorage` (`app.js` `loadRecentAnalyses`);
  - Settings is one file (`webapp/settings.py:23`);
  - encryption at rest;
  - retention and deletion;
  - an application logger (`webapp/worker.py:190`: "This module has no logger");
  - CSRF protection on the multipart `/upload`;
  - rate limits;
  - a secrets store (`.env`, `analysis/config.py:9`, `:73`).
- **Would leak between tenants if hosted as is:**
  - upload returns `duplicate_of`, the earliest *other* job with the same bytes (`webapp/app.py` `upload`, `webapp/storage.py:516`);
  - the artifact cache is keyed by content hash only;
  - settings are shared.
- **Blocks deletion:**
  - a re-analysis writes the whole previous analysis, verbatim and unmasked, into the append-only `audit_log` (`webapp/storage.py:631-656`, `record_reanalysis`);
  - `review_decisions.prior_state` holds the posting's account number and description (`:686-716`).

  The append-only triggers make both undeletable (`:237-251`).

### 7.3 Approaches

**A. A dedicated instance per tenant, with minimal auth.** Add sign-in to today's app and give each lender its own container, disk and database.
- For: isolation by infrastructure; quick.
- Against:
  - the code stays tenant-blind, so pooling later means a second rewrite;
  - every instance must be patched and watched.

**B. One pooled multi-tenant service now.** Postgres, object storage, `tenant_id` everywhere, shared workers.
- For: scales to many small tenants.
- Against:
  - the largest change;
  - a single isolation bug exposes every tenant;
  - it delays the first pilot.

**C. Tenant-aware code, dedicated deployments first (recommended).**
- The code carries `tenant_id`, roles and tenant-scoped reads from day one.
- Each early customer runs on its own instance.
- Pooling (L5d) later becomes mostly a deployment change.
- It also supports the private-cloud or on-premise licence that the market research flags as rare (§10).

**Recommendation: C.**

### 7.4 Design

**7.4.1 Identity** (`webapp/auth.py`, new)
- **Sign-in:** OIDC single sign-on through Authlib (BSD-3-Clause) for Microsoft Entra ID, Google Workspace and Okta. Each tenant's OIDC client secret lives in the secrets store (§7.4.5). Local accounts serve as break-glass admins only, with argon2-cffi (MIT) password hashes and TOTP (pyotp, MIT). §12 Q4 asks the owner to choose.
- **Sessions** are server-side, in a `sessions` table. The cookie holds only a random id, with `Secure`, `HttpOnly` and `SameSite=Lax`. Idle timeout 30 minutes; absolute timeout 12 hours.
- **API keys** (for L6) are stored hashed, carry a visible prefix, are scoped to one tenant and a role, and can be revoked.

**7.4.2 Authorization**

| Role | Can |
|---|---|
| Admin | Manage users and roles, Settings, retention, deletion; everything an underwriter can |
| Underwriter | Upload, review, re-analyse, build packages, export, open source views (markdown, result, page images) |
| Viewer | Read analyses and packages; no source views, no exports |
| Auditor | Read the audit events |

- A `before_request` hook enforces a route → permission map. Unknown routes are denied.
- A test walks `app.url_map` and fails when any route lacks an entry.
- A foreign or unknown id returns 404, never 403, so ids cannot be probed.

**7.4.3 Tenancy.** Schema v5, the number §4.2 assigns to L5a (`webapp/storage.py` `_MIGRATIONS`, `:158-162`):
- adds `tenants`, `users`, `memberships`, `sessions`, `api_keys` and `data_keys`;
- adds `tenant_id NOT NULL` to `documents`, `jobs`, `packages`, `review_decisions`, `audit_log`, `telemetry` and `artifact_cache`;
- assigns existing rows to a "house" tenant (Capital Infusion).

Every `Storage` and `JobStore` read takes the tenant and filters on it. Per tenant:
- duplicate detection;
- artifact-cache keys, for every stage including L1's `locations` (no reuse across tenants: a cache hit would reveal that another lender holds the same statement);
- Settings, as one file per tenant under the tenant's directory. `webapp/settings.py:3-6` keeps settings in a file on purpose, so that a settings table does not lock the data directory against older code; per-tenant files keep that property. The `DEFAULTS` stay the defaults;
- the PDF directory;
- the queue's fairness.

The Recent list moves to a server-side, per-user list.

**7.4.4 Audit.** The audit log splits in two:
- **Events** are append-only and hold no statement content: actor, tenant, action, object ids, time. They are recorded for sign-in and sign-out, failed sign-in, role changes, upload, source views, exports, reviews, re-analysis, Settings changes, deletion, retention purges, and API-key creation and revocation.
- **Content** moves to encrypted, deletable tables: `analysis_versions` holds the previous analyses a re-analysis keeps, and `review_snapshots` holds the reviews' prior states.

The existing append-only triggers stay on events. No statement content lives under them again.

**Moving the house tenant's existing content.** A v4 store already holds statement content under the triggers: each re-analysis audit row carries `previous_analysis_json` and `previous_analysis_error` in its `detail` (`webapp/storage.py:646-650`), and each review decision carries `prior_state` (`:706-708`, and `:738-740` for batch reviews). Four triggers block any UPDATE or DELETE on both tables (`:240-251`). The v5 migration therefore runs these steps in one transaction:
1. Drop the four triggers on `review_decisions` and `audit_log`.
2. Copy every previous analysis into `analysis_versions` and every prior state into `review_snapshots`, each linked by the old row's id. These content tables carry no trigger, so their rows can be deleted.
3. Rebuild both tables without content: every other column kept as it was, and `prior_state` and the content keys of `detail` replaced by a reference to the new content row.
4. Recreate the triggers on the rebuilt tables.

The content tables are encrypted with the rest of the stored content when L5b lands; L5b's first start encrypts the rows already there.

After the transaction, the migration checkpoints the WAL and runs `VACUUM`, so the freed pages that held the plaintext leave the database file. Backups taken before v5 still hold that content in plaintext. They follow the house tenant's retention rule (§12 Q10) and are destroyed when it expires.

**7.4.5 Encryption at rest.** Envelope encryption with `cryptography` (installed 48.0.0; "Apache-2.0 OR BSD-3-Clause"):
- each document gets its own AES-256-GCM data key;
- that key is wrapped by a per-tenant key held in the cloud key service (a key file or HSM for on-premise);
- encrypted: PDFs, markdown, HTML, analysis JSON, artifact files, analysis versions, review snapshots and **filenames**, which often carry business names;
- disk encryption sits underneath.

If the key service is unavailable, the app fails closed: 503, and never a plaintext fallback.

- **Rotation.** The tenant key is rotated once a year, and at once on any suspicion of compromise. The key service creates a new key version, and a background job re-wraps every document's data key under it; the documents themselves are not re-encrypted. The old version is disabled when no wrapped data key refers to it, and destroyed when the last backup made under it expires. Each re-wrap is counted, and the job's completion is an audit event. A data key never changes in place: a document re-encrypted for any reason gets a new one.
- **Secrets.** The OIDC client secrets, the credentials for the key service, the backup store and the mail provider, and the webhook signing keys (L6) live in the cloud's secrets store: Azure Key Vault under §12 Q18 (a). The instance reaches it through its managed identity, so no secret sits in `.env`, in the data directory or in the image. `.env` stays for local development only.

**7.4.6 Retention and deletion**
- Each tenant sets a policy (§12 Q10).
- A nightly purge deletes files and content columns and **destroys the document's data key**. This crypto-shredding also covers backups.
- The store runs with SQLite's `secure_delete` on, so a deleted row's bytes are overwritten rather than left in free pages.
- Events keep only ids and actions.
- Admins can delete a document or package at once, through the same path.

**7.4.7 Logging and monitoring**
- Standard-library `logging`, one JSON line per event, with a request id and tenant id.
- A privacy filter keeps only exception class names and stage names, the worker's existing rule.
- Security events also go to audit events.
- Metrics and alerts cover queue depth, job failures, and sign-in failures.

**7.4.8 Web security**
- A CSRF token header on every mutating route, the multipart `/upload` included.
- CSP, HSTS and `frame-ancestors 'none'`.
- Rate limits per tenant and per IP.
- TLS at the edge.
- Upload limits unchanged.

**7.4.9 Data egress.** For an external tenant, all three model channels in §2 are off: the legacy visual OCR rung, the visual pair and hosted extraction.
- **Capability, not endpoint.** A tenant instance runs with a new `TENANT_MODE=external` switch. Under it, the worker's extractor sets (`webapp/worker.py:126-128`) hold neither `visual` nor `visual_pair`, and every place that can build a model client (`ocr/ocr_client.py:560-567`, the visual-pair reader, the hosted-extraction call in `analysis/pipeline.py`) checks the mode first. Neither Auto mode nor a forced OCR request can then reach a model. The endpoint policy is not enough on its own: it allows loopback and private hosts by default (`ocr/endpoint_policy.py:159-172`), and a loopback URL may be an SSH tunnel (`ocr/visual_pair_config.py:3-4`).
- **Refuse to start.** Under `TENANT_MODE=external` the process refuses to start when any of these is set: `OCR_VISUAL_PAIR_LEGACY_VISUAL`, `OCR_REMOTE_OPT_IN`, `OCR_ALLOW_VISUAL_PAIR`, `VISUAL_PAIR_REMOTE_CUSTOMER_DATA_OPT_IN`, `HOSTED_EXTRACTION_OPT_IN` or a non-empty `GEMINI_API_KEY` (§2 table). The error names the variable, never its value.
- **Network.** The host allows only listed outbound destinations: the key service, the backup store, the identity provider and the mail provider.
- **Test.** A test sets each variable in turn under `TENANT_MODE=external` and expects the refusal; another sends a scan-only fabricated PDF, in Auto mode and with a forced OCR request, and expects local Tesseract, review or a safe refusal, with no model client ever built. Today a forced request with the legacy rung off goes straight to the visual pair (`webapp/worker.py:675-677`); under `TENANT_MODE=external` it must be refused or routed to local OCR. §12 Q8 asks which; L5b implements it.

**7.4.10 Hosting and operations**
- One container per tenant, on its own managed disk. Each pilot gets its own VM; later tenants may share a host (§10.4, §12 Q32).
- Daily encrypted backups through SQLite's online backup, with a restore drill.
- A runbook and a named on-call contact.
- Fly stays a demo host.

**7.4.11 SOC 2 programme (L5c, process)**
- Policies, access reviews, and change management. The repository's independent-review practice is a head start.
- A sub-processor list (cloud, email), incident response and a risk assessment.
- A readiness assessment, then Type I, then a Type II observation window.

**Upload data flow after L5**
1. The browser, with a session, calls `POST /upload` with its CSRF token.
2. The role check requires underwriter.
3. `_checked_upload` runs unchanged.
4. `store.create` records the job under the tenant, generates a data key and stores the encrypted PDF.
5. The job is queued with its tenant.
6. The worker decrypts in memory, reads and analyses, and encrypts the outputs.
7. `set_result` stores them under the tenant, and an audit event is written.

**Serving an analysis after L5**
1. `GET /analysis/<id>` passes the auth check.
2. The job is read with its tenant; a foreign id is a 404.
3. The record is decrypted.
4. `_displayed` applies that tenant's Settings.
5. `_masked` masks the account numbers, and the JSON is returned.

### 7.5 Error handling

- **Not signed in:** a browser is redirected to sign-in; the API gets 401 JSON.
- **Wrong tenant or unknown id:** 404.
- **Missing permission:** 403 and an audit event.
- **Key service down:** 503. Nothing is written in plaintext.
- **Decryption failure:** the job is marked unreadable, with an audit event and no partial data.
- **Purge failure:** an alert and a retry. A purge is never skipped silently.
- **Mid-transaction failure:** a migration refuses to start the app; there is no half-migrated store.

### 7.6 Testing

- **Coverage:** the route inventory test, and a role matrix test for every route.
- **Cross-tenant:** tenant B gets 404 for every route called with tenant A's ids. This covers `page`, `render`, `markdown`, `result`, the downloads, the package routes, reviews and re-analysis. Duplicates and cache reuse do not cross tenants.
- **Web security:** CSRF, session expiry, and API-key revocation.
- **Encryption:** after a run with a fabricated statement carrying a unique marker string, a byte scan of the whole data directory finds no plaintext marker.
- **Retention:** after expiry, content is unreadable and the event ids remain.
- **Migration:** v4 → v5 on a copy of a fabricated store that holds a re-analysis and a review, each carrying a unique marker string. Existing rows land in the house tenant. After the migration, no row of `audit_log` or `review_decisions` holds the marker, and their triggers are back. The marker lives only in the content tables. Deleting those rows through the purge path succeeds, and afterwards a byte scan of the database file, its WAL and the data directory finds no plaintext marker. With L5b in place, the scan finds none even before the deletion.
- **Logs:** the marker never appears in logs.
- **Egress:** the `TENANT_MODE=external` tests of §7.4.9.
- **Licences:** a check that fails on any AGPL, GPL or (per §12 Q6) LGPL distribution in the runtime set, using a permissive tool such as pip-licenses (MIT).

### 7.7 Success criteria

1. Every route requires a permission, and the cross-tenant suite passes.
2. No plaintext statement bytes exist on disk. Deletion is proven, backups included.
3. Capital Infusion's house tenant runs on the new stack for two weeks with the corpus gate green and a cold run identical (2,625 → 2,625).
4. An external penetration test closes with no open high findings (§12 Q19).
5. A restore drill completes within the documented time.

## 8. The other sub-projects

### 8.1 L0 — Licence clean-up

- **What:**
  - move Phase 1's native text reading, the preflight and the artifact cache's native read from PyMuPDF to pypdfium2 (`ocr/native_text.py`, `ocr/inspect.py:197`, `webapp/artifact_cache.py:900`, `evidence/native.py:437`, `ocr/paddle_rung.py:37`);
  - move page rasters from pdf2image/poppler to pypdfium2 (`ocr/rasterize.py`, with a `RASTER_VERSION` bump that repartitions the OCR cache);
  - remove PyMuPDF from `requirements.txt`;
  - check the licences of every model's weights before any tenant uses them: the visual pair's proposer and reviewer (`ocr/visual_pair_config.py:17-20`) and the legacy visual OCR default, `baidu/Unlimited-OCR` (`ocr/config.py:150`);
  - ship PDFium's third-party notices, including FreeType's credit under its FTL option.
- **Why it matters to lenders:** they cannot license a product whose core is AGPL without the whole product becoming AGPL.
- **Depends on:** text-first slice A (ruling 12).
- **Proof:** corpus gate GREEN 105/3/1 and a cold run 2,625 → 2,625 identical. Any movement goes to a ceremony.
- **Risk:** the two engines may extract text slightly differently and move parsers. That is why it is sized at 3–6 weeks.

### 8.2 L3 — Learning loop

- **What:**
  - an append-only lender-review decision on potential-lender rows (lender, alternative position, LOC, another flag group, or not a lender), keyed on the normalized payee tokens D6 already groups by (`analysis/transaction_classifier.py:2173`), never on amounts or names;
  - per-tenant aliases applied at analysis time with `match_method="tenant_alias"` (§12 Q35 decides whether they can count);
  - a local export that turns aggregated decisions into draft ledger entries with status `review`, feeding the existing validate-then-build pipeline (`tools/lender_ledger.py`, `tools/build_lender_registry.py`);
  - the registry moved from compiled tables to a versioned, hashed data file, so an on-premise customer can receive registry updates without a code release.
- **Why lenders pay:** fewer misses each month. MCA Track sells exactly this, a funder-editable list of competitor descriptors ([S9]).
- **Depends on:** nothing technical; waiting for L5a, so decisions carry signed-in actors, is the recommended product choice (§4.2, §12 Q17). Better with L1.
- **Size:** 3–4 weeks.
- **Rulings:** admission to a counted global list still needs the two-agent research verdict (lender spec §5). A tenant's decision never enters the shared registry without it. The lender spec already names this as its next project (§11).

### 8.3 L4 — Fraud and tampering signals

- **What:**
  - an advisory forensics block in the preflight, built on pypdfium2: incremental-save trail (trailer ends and `%%EOF` count), producer and creator, creation versus modification date, font inventory, overlay rectangles, invisible text;
  - revision recovery with a render diff, drawn on the page with L1's overlay;
  - a package check that, for consecutive statements of the same account, the previous closing balance equals the next opening balance;
  - near-duplicate detection within a tenant (a keyed hash of account digits, period and balances).
- **Research check:** a synthetic probe confirmed that pypdfium2 5.8.0 exposes the needed PDFium entry points and can recover a prior revision ([S17], [S18]).
- **Presentation:** reason codes with their evidence and boxes. Every finding is a review flag, never a refusal. This matches the existing "not proof of fraud" note (`analysis/pipeline.py:1227`) and R14's flag-first precedent.
- **Why lenders pay:** 90% of surveyed funders name forgery as their top concern ([S5]). This is parity, not a differentiator: every competitor sells it.
- **Depends on:** L1 for the overlay.
- **Size:** 3–5 weeks for v1.
- **Blind spots to state to customers:** a statement fabricated from scratch or re-printed to PDF shows no edit trail.

### 8.4 L6 — Integrations

- **What:**
  - **API v1** (after L5a): a frozen `/api/v1` over today's routes, per-tenant API keys, an OpenAPI document, an idempotency key on upload, a job-list endpoint, and one HMAC-signed webhook when a job ends. The webhook carries only the id and status (`webapp/worker.py` terminal writes). The package `reference` holds the CRM deal id.
  - **Email intake:** a per-tenant inbound address, PDF attachments only, and a sender allow-list. The mail provider becomes a named sub-processor.
  - **CRM connectors:** the first one is chosen by the first pilot, for example LendSaaS, or Salesforce, which Cloudsquare and Fundingo build on.
  - **Open banking** (Plaid, Flinks, DecisionLogic): an optional connector the tenant contracts for. The core never needs it (§12 Q38).
- **Why lenders pay:** analysts spend much of a file assembling it. Heron's pitch is email to CRM in minutes ([S7]).
- **Size:** API v1 2–3 weeks; each connector 2–4 weeks.

### 8.5 L7 — Lender rules and offer calculator

- **What:**
  - per-tenant, versioned credit-box rules over the canonical metrics, for example minimum ADB, maximum NSF days, minimum months, maximum withholding and maximum active positions;
  - each evaluation logged with the rule version;
  - an offer calculator (advance, factor, term, holdback) and an estimated-APR helper for disclosure states, reviewed by counsel.
- **Doctrine limits:**
  - rules read the one canonical ADB and never redefine its denominator (ADB doctrine: no funder denominator profiles);
  - the NSF basis stays the ruled Settings option;
  - any USD conversion happens only here, with full provenance (currency doctrine §E);
  - package figures across currencies stay refused.
- **Why lenders pay:** speed to offer, and a defensible decision trail. California's SB 362 (approved by the Governor and chaptered on 6 October 2025, chapter 352) amends the marketing and APR wording rules: a provider that states a specific offer's charge or pricing metric during the application must state the APR too, and misleading uses of "interest" and "rate" are barred, factor rates included ([S15], bill text read on 2026-09-27). The bill text carries no dollar threshold and no effective date; §10.1 says where those come from. Texas HB 700 requires registration by 31 December 2026 ([S16]).
- **Depends on:** L2, L5a.
- **Size:** 3–5 weeks plus counsel.

### 8.6 L8 — Published accuracy benchmark

- **What:**
  - a written, reproducible method;
  - an exam on a sealed holdout that implementation never saw (R4), against truth the owner adjudicates (R3);
  - metrics:
    - the **false-accept rate** (validated but wrong), which is the headline;
    - coverage on both denominators (R11, R12);
    - per-field exact match;
    - agreement with MoneyThumb, reported as agreement and never as accuracy;
  - a public summary by bank family, with no statement data;
  - the scoring code and synthetic fixtures published.
- **Why lenders pay:** every vendor claims 99% or more, and none publishes how it was measured (market research, §10).
- **Depends on:** L0, the holdout and adjudication time.
- **Size:** 3–4 weeks plus adjudication.

### 8.7 L9 — Coverage and cost per page

- **What:**
  - per-tenant coverage and cost dashboards over the existing telemetry table (`webapp/storage.py:109-138`);
  - text-first slices B and C;
  - a self-hosted GPU option for scans, since a tenant's statements cannot go to a marketplace GPU (§7.4.9);
  - new parsers chosen by tenant demand.
- **Why it matters:** refusals are honest, but a lender sees them as "didn't work". The deterministic path costs about $0 per statement, against the roughly $3 per statement Capital Infusion pays MoneyThumb (`PROJECT_GOAL.md`). The last recorded scan speed was about 23 s per page (`docs/moneythumb-replacement/PRODUCTION_GAPS.md` G7), and it needs re-measuring.
- **Size:** ongoing.

### 8.8 L10 — Verified revenue

This is the owner's next project, with its own spec. It builds on the existing revenue review (`analysis/revenue.py`, the `revenue-review` routes), on L1 (revenue rows on the page) and on L3 (decisions with real actors). This roadmap only reserves its place (§9).

## 9. Phased roadmap

### 9.1 Phases and milestones

Month 0 is October 2026.

| Window | Work | Milestone |
|---|---|---|
| **0–3 months** | Text-first slices 0+A; **L1 v1**; **L2 v1**, with balance estimates under §12 Q13 (a); **L5a**; **L5b**; then **L0**; SOC 2 readiness starts; pilot paperwork, pricing and operations (§9.3, §10.4, §10.5) | **M1 (~month 2): customer zero.** Capital Infusion's underwriters use L1 and L2 on the house tenant of the new stack, beside MoneyThumb. **M2 (~month 3): pilot-ready.** The §9.2 gate passes and the first paying design partner starts on a dedicated instance |
| **3–6 months** | L6 API v1 and webhooks; the first CRM connector (the pilot's choice); L4 v1; L3 v1 (per tenant; under §12 Q17 (b) it starts in months 0–3 on the house tenant); L2 balance estimates, if §12 Q13 (b) defers them to per-tenant settings; L8 method frozen and first sealed exam; SOC 2 Type I | **M3 (~month 6):** 2–3 paying pilots; Type I report; API documented |
| **6–12 months** | L7 rules and offer calculator; L8 publication; email intake; the shared-host shape, then L5d, if small funders beyond the pilots are wanted (their volumes do not carry a dedicated VM, §10.4); SOC 2 Type II window; open banking if pilots ask; a Canadian region if a Canadian lender signs; L10 | **M4 (~month 9):** pilots convert to annual contracts; benchmark published. **M5 (~month 12):** pooled option live or not needed; Type II under way |

The months assume L0 takes no more than six weeks and that text-first slice A lands in October. If L0 moves pinned figures, M2 moves with it.

### 9.2 Pilot gate

All of these must hold before any external lender's statement is uploaded:
1. **Licences.** No AGPL/GPL (and, per §12 Q6, no LGPL) distribution in the served path. The CI licence check is green.
2. **Access.** L5a done: sign-in, roles, tenant scoping, audit events, and the cross-tenant suite green.
3. **Data at rest.** L5b done: encryption, retention and deletion proven, logs privacy-filtered, and a restore drill passed.
4. **No egress.** All three model channels off for the tenant: the legacy visual OCR rung, the visual pair and hosted extraction (§2, §7.4.9). `TENANT_MODE=external` is set, its start-up refusal tests are green, and the host allows only listed outbound destinations.
5. **Differentiators.** L1 v1 and L2 v1 are live, and their success criteria (§5.7, §6.7) are met.
6. **Security test.** An external penetration test with no open high findings, or the pilot lender's written acceptance (§12 Q19).
7. **Legal.** A pilot agreement, a data processing agreement, the sub-processor list, and the entity and brand decision (§12 Q22). Counsel also covers the privacy laws the pilot's data falls under:
   - the Gramm-Leach-Bliley Act and its Safeguards Rule, where a sole proprietor's statements are a consumer's financial data and a lender flows its obligations down by contract;
   - PIPEDA and Quebec's Law 25, for a Canadian lender or Canadian merchants;
   - US state privacy and breach-notification laws in the lender's and its merchants' states.
8. **Operations.** Every item of §9.3 is in place: the coverage check on the pilot lender's bank mix is done; the security-questionnaire answer set exists and the pilot lender's questionnaire is answered; insurance is bound; the user and admin guides exist; the availability statement is in the pilot agreement; and the onboarding, support, release and offboarding procedures are written and rehearsed once on a fabricated tenant, including an export and a proven crypto-shredding deletion.
9. **Price.** The pilot price and its monthly minimum (the floor) are set from the cost model (§10.4, §12 Q25).

### 9.3 Pilot operations

What a paying pilot needs beyond the code. §9.2 item 8 requires every item here before the first external upload.

**Before the contract**
- **Coverage check on the lender's bank mix.** The archive validates 77.66%, but a pilot lender's merchants may bank elsewhere.
  1. The lender lists the banks behind a recent period of its files, as bank names and file counts only. No statement changes hands.
  2. For each bank we report whether a validated reader exists and the archive's validation counts for it. The weighted result is the share of the lender's files expected to validate; the rest go to review.
  3. We also check the lender's monthly volume and its share of scans against one worker thread (§11, Throughput).
  4. The lender sees these numbers before it signs. They become the scorecard's baseline for "validated versus review" (§10.5).
  5. The shadow period (onboarding step 6) measures the real share from telemetry counts inside the lender's instance. A gap of more than 10 points is reviewed with the lender (§12 Q31).
- **Security questionnaire.** Lenders send a vendor security questionnaire (SIG Lite or CAIQ style) long before a SOC 2 report exists. We keep one answer set, built from §7 and the L5c policies, with the penetration-test summary letter. Every answer points at a control that exists, never at a plan. The owner signs it off.
- **Insurance.** Cyber-liability and technology errors-and-omissions cover is bound before the first external upload, at the limits the pilot agreement names. Lenders may ask for the certificate (UNVERIFIED). The cost is in §10.4.

**Onboarding** (about two weeks per lender; an estimate)
1. The contract is signed: the pilot agreement, the data processing agreement, the sub-processor list, the availability statement below, and the scorecard (§10.5).
2. An operator script provisions the tenant: the instance, the tenant key, a data directory outside the checkout, the retention policy, the outbound allow-list, and `TENANT_MODE=external`.
3. Sign-in: the lender's identity provider is connected by OIDC, with the client secret in the secrets store (§7.4.5). Its first admin is invited, adds the lender's users and gives each a role (§7.4.2). The break-glass admin account belongs to the lender, not to us.
4. Settings are reviewed with the lender's admin: flag groups, NSF carry-over, and the factor rate and funding window for positions. Once L3 ships, the tenant's own payee aliases are added here too (§8.2).
5. A smoke test runs with fabricated statements only. Then the lender uploads.
6. A two-week shadow period: the lender keeps its current process beside ours and records the scorecard baseline.
7. One training session for underwriters, held on fabricated statements and recorded for later hires: the proof panel, page boxes, positions, refusals and review.

**Documentation**
- A user guide: sign-in, upload, the proof panel and page boxes, positions and what an estimate means, refusals and review, exports.
- An admin guide: users and roles, Settings, retention, the support-access grant, export and deletion.
- A one-page note on what the product does not claim: signals are advisory, estimates are estimates, the fraud checks have blind spots (§8.3), and a refusal is not a verdict on the merchant.

**Support**
- One channel (a shared mailbox or a ticket queue), open in US business hours, Eastern time (§12 Q26).
- Severity levels and first-response targets:

  | Severity | Examples | First response |
  |---|---|---|
  | S1 | Suspected data exposure; instance down | 1 hour, any day |
  | S2 | A wrong published figure; a box on the wrong line | 1 business day |
  | S3 | A refused statement; a new bank; a question | 3 business days |

- **Wrong-figure reports carry no statement data.** The lender reports the job id and the field. Support never asks for a PDF by email. Support staff read tenant data only through a time-limited grant that the tenant's admin approves, and each read is an audit event (§12 Q28).
- **Refusals and new banks.** Support sees counts and refusal classes from telemetry, never content. A new parser built from a licensee's statement needs that lender's written permission for each document. The parser rules still hold: fixtures are fabricated, and no statement value enters a commit or a test (§12 Q29).
- **Incidents.** An S1 follows L5c's incident-response procedure, including notice to the lender within the contract's deadline.

**Availability**
- A pilot runs on one instance with one worker thread (§11, Throughput). There is no second instance to fail over to, and one job runs at a time.
- The pilot agreement therefore states a target, not an SLA with service credits: the service is available in support hours, outside the announced release window, about 99% of the time in a month (§12 Q27).
- A VM or disk failure means a restore from the last daily backup onto a new VM. Up to a day of work can be lost: the lender re-sends the statements it uploaded since that backup. The restore takes no longer than the drill's measured time (§7.7 #5).
- Jobs running when the instance stopped are marked `interrupted` at restart, never silently lost (`webapp/storage.py:658`, `mark_interrupted_jobs`), and the lender re-runs them.

**Releases**
- A monthly release window per instance, announced a week ahead, with release notes.
- Every release passes the corpus gate and the cold run before it ships, as today.
- Registry updates travel with releases until L3 turns the registry into a data file.
- A stage-version bump makes cached artifacts recompute. Stored analyses keep their labels until re-analysed (D12), and the release notes say when a re-analysis would change them.
- Fixes for S1 and S2 ship outside the window.

**Offboarding**
- **Data return.** At the end of the contract the lender has 30 days to export its analyses and packages (CSV, XLSX and JSON, through the existing downloads), its audit events and, on request, its original PDFs (the last two through a new admin export, part of L5a).
- **Deletion.** Then the tenant key is destroyed, which also makes the backups unreadable (§7.4.6). The instance and its disks are deleted, the sign-in connection and the tenant's secrets are removed, and a deletion certificate is sent within 30 days (§12 Q30).
- **Proof.** Before the certificate is sent, the last backup is restored into a scratch instance, and the check confirms that no document decrypts. The certificate records that check, as §7.7 #2 requires.
- Audit events hold no statement content. A copy is kept for the retention period the contract states, as evidence for the SOC 2 audit.
- A licensee's data never moves into Capital Infusion's house tenant, and house data never moves into a licensee's instance.

## 10. Business notes (research; not verified by the author unless marked)

The facts in this section come from public web sources gathered on 2026-09-26 and 2026-09-27, and most of them are vendor marketing. The author's recommendations (§10.2, §10.3, §10.5) and cost estimates (§10.4) are built on them and marked as such. Tags:
- **[self]:** the vendor says it about itself;
- **[comp]:** a competitor says it;
- **[3p]:** a third party says it;
- **UNVERIFIED:** no primary source was confirmed.

The author re-checked the MetrikData and ClearStaq pricing pages, Vendr's Ocrolus and Inscribe pages, the MoneyThumb/deBanked survey, the Ocrolus authenticity-score documentation, and the state-law sources on 2026-09-27. For [S15] only the bill text and its chaptering lines were read, and they do not answer every question (§10.1). The cost sources [S21]–[S24] were seen as search-result summaries, not read in full; they are third-party price guides, and §10.4 treats them as ranges to replace with quotes.

### 10.1 The market

| Group | Examples | What they sell | Price signals |
|---|---|---|---|
| Incumbent | MoneyThumb (PDF Insights, Thumbprint) | Statement conversion and analysis; a tamper score of 1–1000 with reasons [self, S12]; "identifies MCA stacking" [self, S13]; desktop, web and API; SOC 2 Type 2 [self] | Capital Infusion pays about $3 per statement (`PROJECT_GOAL.md`) |
| Enterprise | Ocrolus; Inscribe | Ocrolus: human-checked and machine reading, Detect with a 0–100 authenticity score, lender-set cut-offs [self, S10, S11]. Inscribe: document forensics, trust score [self, S20] | Ocrolus: Vendr median $98,250 a year, range $48,000–$463,500 [3p, S3]. Inscribe: median $24,500, range $1,000–$58,638 [3p, S4] |
| MCA automation | Heron Data | Email intake, statement analysis, CRM sync, lender matching; "tracks every position from funded to paid off" [self, S7]; the engine inside Cloudsquare's IntelliParse since April 2025 [3p, S8]. Customer counts differ between Heron's own pages (150+ and 200+) | Not public |
| MCA newcomers | MetrikData, ClearStaq, Kaaj, StatementScrub, LenderAnalyzer | Model-based reading in seconds; fraud checks; MetrikData types positions by payment rhythm and repayment burden, without a balance estimate [self] | MetrikData $99–$599 a month, $0.86–$1.32 per credit, 1–2 credits per statement, 3 for long ones, +1 for scans [self, S1]. ClearStaq $99–$699 a month, about $0.35–$0.66 per document [self, S2] |
| CRMs and servicing | LendSaaS, Onyx IQ, Cloudsquare, Centrex, OrgMeter, MCA Track, Dragin | Origination, servicing, syndication. Statement analysis is bought in (Ocrolus, Heron, DecisionLogic) or built in. MCA Track matches recurring debits against a funder-editable list of competitor descriptors [self, S9] | Cloudsquare from $75 per user per month [self]; others not public |
| Bank data | Plaid, Flinks (Canada), DecisionLogic, Inverite | Statements fetched from the bank, so they cannot be forged; some attributes include stacking [self] | Usage-based; not public |

**What underwriters say they need** [research]:
- **Fraud at intake.**
  - 90% of surveyed funders name forgery as the top issue;
  - 88% still review documents by hand;
  - funders with fewer than 100 applications a month report fraud in 11.8% of applications, against 5.6% at larger funders (MoneyThumb and deBanked survey, September 2025 [S5]).
- **True revenue.** Transfers, loan proceeds, owner money and refunds removed.
- **Existing positions.** "A deal that looks affordable in isolation can be unfundable once existing advances are counted" [S9].
- **Speed.** Manual review is quoted at 30–45 minutes per submission [UNVERIFIED].
- **Reasons that can be audited.** Figures that open onto their source transactions.
- **Compliance.** Ten states have commercial-financing disclosure laws (Venable, March 2026 [S14]). California's SB 362 requires the APR beside any charge or pricing metric quoted during the application, factor rates included [S15]. The bill amends the wording rules inside the Financial Code's commercial financing disclosure division: it renumbers §22806 to §22805, repeals the old §22805 and adds §22807. A licensed provider's violation counts as a violation of the California Financing Law. The bill text carries no dollar threshold and no effective date. Two statements are therefore the author's inference, not read in the bill: that its reach follows the $500,000 ceiling of the disclosure statute it amends (enacted by SB 1235 in 2018), and that it took effect on 1 January 2026, California's default start for a statute passed in the 2025 regular session. Both are UNVERIFIED until counsel confirms them. Texas regulates sales-based financing and requires registration by 31 December 2026 [S16].

### 10.2 Positioning (the author's recommendation, built on the research)

- **"Proof, not a score."** Every figure reconciles to the statement's own printed totals, and every row and total opens on the page (L1). No surveyed vendor was found showing each figure boxed on the original PDF together with a reconciliation proof. That is an absence the research failed to find, not a verified fact.
- **Positions with dates.** Payment streams, funding dates and stacking signals (L2). No vendor was found publishing a per-position funding date or remaining-balance estimate; Heron's "funded to paid off" is the closest. This is also an unverified absence.
- **Your data stays yours.**
  - The deterministic path reads statements without any model and with no data leaving the lender's instance.
  - Dedicated and on-premise deployments are offered; only MoneyThumb's desktop product is offline today [research].
  - This is also the answer to the conflict of interest in §11.
- **Honest numbers.** A published false-accept rate (L8) against competitors' unmeasured "99%".
- **Canada.** Native CAD under the currency doctrine, with readers for Canadian banks already in `analysis/` (RBC, TD, BMO, CIBC, Scotiabank, Desjardins, ATB).
- **Parity, not the pitch:** fraud checks (L4), email intake and CRM sync (L6). Buyers expect them. They do not win deals alone.

### 10.3 Pricing units

- **The market's units** are per page (Ocrolus's billing units [comp, UNVERIFIED]), per statement or credit (MetrikData, ClearStaq), per report (StatementScrub, DecisionLogic), annual enterprise contracts (Ocrolus, Inscribe), and per seat for CRMs.
- **Recommendation:** per statement, above a monthly floor that includes a volume; a surcharge for scans once a scan path exists (they cost GPU time; MetrikData charges one extra credit); and an annual licence with a floor fee for dedicated or on-premise instances. The floor covers the tenant's own hosting and support; the fixed costs (§10.4) are spread over tenants.
- **Per page is not recommended.** The deterministic path's cost does not grow with pages, and buyers compare per statement.
- **Level:** the published band for model-based newcomers is about $0.35–$2.64 per statement. MoneyThumb costs Capital Infusion about $3. §10.4 shows why a per-statement price needs a monthly floor. §12 Q24 and Q25 ask the owner to set the unit and the pilot price.

### 10.4 Cost model (estimates)

Every figure here is the author's estimate in US dollars, built from third-party price guides ([S21]–[S24]) where one was found and marked UNVERIFIED where not. They are orders of magnitude for the pricing questions in §12, not quotes. Before a price is offered, they should be replaced with the cloud provider's calculator and two quotes each for the auditor and the penetration test.

**Run cost of one dedicated instance, per month**

| Item | Assumption | Estimate |
|---|---|---|
| Compute | One VM with 4 vCPU and 16 GiB, on demand [S21]. The one worker thread and local Tesseract fit | about $140 |
| Disk and backups | 256 GB managed disk; daily encrypted backups kept 35 days in a second region | $30–$60 (UNVERIFIED) |
| Key service | One tenant key; a few thousand wrap and unwrap calls | under $10 (UNVERIFIED) |
| Network | Deny-all outbound with listed destinations, through security-group rules; no managed firewall | $0–$40 (UNVERIFIED) |
| Logs and monitoring | Privacy-filtered logs kept 90 days | $10–$40 (UNVERIFIED) |
| **Infrastructure** | | **about $200–$300** |
| Support during a pilot | 4–8 hours a month at a loaded $100 an hour | $400–$800 (UNVERIFIED) |
| **Per pilot tenant** | | **about $600–$1,100** |

- **A shared host** cuts the infrastructure line. One VM can carry three or four tenant containers, each with its own disk, database, key, settings file and process. That brings infrastructure to about $70–$100 per tenant. The code is the same, because it is tenant-aware (§7.3 C).
- **Processing cost per statement** stays close to zero on the deterministic path: seconds of CPU, plus L1's locator budget (§5.5).
- **A self-hosted GPU for scans** costs hundreds to a few thousand dollars a month when always on (UNVERIFIED). It pays only above a scan volume no pilot has shown yet. Until then scans stay on local Tesseract or go to review.

**Fixed costs shared by all tenants, first year**

| Item | Estimate | Basis |
|---|---|---|
| External penetration test | $8,000–$18,000 | [S24] |
| SOC 2 Type I audit (once) | $7,500–$20,000 | [S22], [S23] |
| SOC 2 Type II audit (yearly) | $15,000–$50,000 | [S23] |
| Compliance-automation tooling | $10,000–$25,000 a year | UNVERIFIED |
| Counsel: pilot agreement, data processing agreement, terms (once) | $10,000–$25,000 | UNVERIFIED |
| Cyber and professional-liability insurance | $5,000–$15,000 a year | UNVERIFIED |
| **Total** | **about $55,000–$150,000** | The Type II fee may fall in year 2, depending on when its window starts |

This excludes engineering time and the owner's time.

**Break-even**
- **Volume of a small funder.** The survey's small funders take fewer than 100 applications a month [S5]. Funders read 3–6 months of statements per file (market research, UNVERIFIED as a count per file). That is up to about 300–600 statements a month.
- **Per-statement price alone does not carry a dedicated VM for a small funder.** At $1.25 a statement, 600 statements bring $750 a month, against $600–$1,100 of per-tenant cost during a pilot.
- **So the price needs a monthly floor** that covers the per-tenant cost, with a volume of statements included: about $1,500 a month on a dedicated VM, or about $750 on a shared host.
- **Fixed costs** of about $55,000–$150,000 in year 1 are about $4,600–$12,500 a month. After a pilot, support should fall to 2–4 hours a month, so a dedicated tenant at a $1,500 floor contributes about $800–$1,100 a month above its own cost. Covering the fixed costs then takes roughly 5–15 such tenants. On a shared host at $750, each tenant contributes about $250–$480, and it takes roughly 10–50. With 2–3 pilots, year 1 runs at a loss. The owner decides whether to fund it (§12 Q20).
- **Against the market:** MetrikData's and ClearStaq's top published tiers are $599 and $699 a month [S1, S2]. A $1,500 floor sits well above them, and even $750 sits above them. Design partners who get a dedicated instance and direct support can accept it; many small funders at scale will not. Selling to them at scale needs the shared host first and pooled tenancy (L5d) later, or a focus on mid-sized funders whose volume carries the floor.
- **Capital Infusion as customer zero** pays nothing and replaces a cost of about $3 a statement (`PROJECT_GOAL.md`). Its saving depends on its monthly volume, which this spec did not read.

### 10.5 Pilot strategy

1. **Customer zero.** Capital Infusion's own underwriting on the house tenant (M1). It proves the stack and measures time per file against MoneyThumb.
2. **Design partners.** 2–3 small or mid-sized MCA funders, paid, for 60–90 days, each on a dedicated instance with every model channel off (§7.4.9). The survey says small funders see twice the fraud rate and still review by hand; they are price-sensitive and underserved by enterprise contracts.
3. **Scorecard,** agreed before the start:
   - minutes per file;
   - positions found against the funder's own analyst;
   - the share of statements validated versus sent to review;
   - wrong figures found by the funder's staff (target zero);
   - requested features.
4. **Conversion.** An annual contract at the end, with the pilot fee credited.
5. **Channel later.** CRMs buy statement analysis in (LendSaaS integrates Ocrolus, Heron and DecisionLogic; IntelliParse runs on Heron). A CRM partnership is the scale channel after API v1.

### 10.6 Sources

- [S1] MetrikData pricing — https://www.metrikdata.com/pricing
- [S2] ClearStaq pricing — https://clearstaq.com/pricing
- [S3] Vendr, Ocrolus — https://www.vendr.com/marketplace/ocrolus
- [S4] Vendr, Inscribe — https://www.vendr.com/marketplace/inscribe
- [S5] MoneyThumb and deBanked survey, September 2025 — https://debanked.com/2025/09/moneythumb-and-debanked-release-survey-findings-on-fraud-trends-among-small-business-funders/
- [S6] deBanked interview with MoneyThumb — https://debanked.com/2025/09/the-merchants-paying-the-bank-statements-were-fraudulent-talking-with-moneythumb/
- [S7] Heron — https://www.herondata.io/
- [S8] Cloudsquare IntelliParse powered by Heron — https://debanked.com/2025/04/cloudsquare-launches-intelliparse-to-automate-application-intake-and-financial-analysis-powered-by-heron/
- [S9] MCA Track, stacking detection — https://mca-track.com/mca-stacking-detection/
- [S10] Ocrolus authenticity score — https://docs.ocrolus.com/docs/authenticity-score
- [S11] Ocrolus Detect signals — https://docs.ocrolus.com/docs/detect-signals
- [S12] MoneyThumb Thumbprint — https://www.moneythumb.com/thumbprint/
- [S13] MoneyThumb for MCA — https://www.moneythumb.com/mca/
- [S14] Venable, state commercial financing disclosure laws (March 2026) — https://www.venable.com/insights/publications/2026/03/state-commercial-financing-disclosure-laws
- [S15] California SB 362 (Grayson), "Commercial financing: disclosures", approved and chaptered 6 October 2025 (chapter 352) — https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202520260SB362
- [S16] Holland & Knight on Texas HB 700 — https://www.hklaw.com/en/insights/publications/2025/06/texas-governor-signs-commercial-sales-based-financing-legislation
- [S17] HTPBE, binary PDF modification detection — https://htpbe.tech/blog/binary-pdf-modification-detection-technical-approach
- [S18] pypdfium2 — https://github.com/pypdfium2-team/pypdfium2
- [S19] Resistant AI, document fraud templates — https://resistant.ai/blog/document-fraud-templates
- [S20] Inscribe — https://www.inscribe.ai/industries/banks
- [S21] Vantage, Azure D4s v5 pricing (4 vCPU, 16 GiB; about $0.192 an hour, about $140 a month on demand in East US) — https://instances.vantage.sh/azure/vm/d4s-v5
- [S22] Drata, SOC 2 audit cost — https://drata.com/learn/soc-2/cost
- [S23] SOC2Auditors.org, SOC 2 audit cost (September 2026) — https://soc2auditors.org/soc-2-audit-cost/
- [S24] SecureLeap, penetration testing cost for startups — https://www.secureleap.tech/blog/penetration-testing-cost-startup-pricing

## 11. Risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| **Licence** | PyMuPDF (AGPL) and poppler (GPL) are in the served path. Model-weight licences are unchecked for all three model channels (the visual pair's two models and `baidu/Unlimited-OCR`). The `openai` client package in `requirements.txt` is Apache-2.0 and not a problem. psycopg, a common Postgres driver, is LGPL-3.0 (installed version reports so) | L0 before any external pilot; a CI licence check; every model channel off for tenants (§7.4.9) until its weights are checked; a BSD or Apache Postgres driver (pg8000, asyncpg) if L5d needs Postgres, unless the owner accepts LGPL (§12 Q6) |
| **Unit economics** | A dedicated instance costs more per month than a small funder's statements bring at newcomer prices (§10.4). The floor that covers it sits above the newcomers' top tiers | A monthly floor for design partners; the shared-host shape, then L5d, before selling to many small funders; or a focus on mid-sized funders |
| **Model egress by configuration** | One environment variable can turn on a model channel: the legacy visual OCR rung (`OCR_VISUAL_PAIR_LEGACY_VISUAL`), the visual pair or hosted extraction. A loopback URL may be a tunnel to a remote GPU | `TENANT_MODE=external` removes the capability and refuses to start with any channel switch set (§7.4.9) |
| **Conflict of interest** | Capital Infusion is itself a funder (it is admitted under Alternative positions). Competing funders may refuse to send deal flow to a competitor's software | A separate brand and entity; contract terms that Capital Infusion's lending side never sees tenant data; dedicated instances; no cross-customer data use without opt-in (§12 Q22, Q34) |
| **Coverage perception** | 77.66% of the archive validates; the rest goes to review. Competitors claim 99%. A pilot lender's merchants may bank outside the validated banks. For external tenants every model channel is off, the legacy visual OCR rung included, so their scans read only through local Tesseract | A coverage check on each pilot lender's bank mix before it signs, then measured in the shadow period (§9.3); text-first; the scan path; honest refusal messages; per-tenant coverage reporting; the benchmark's false-accept rate |
| **A security incident** | Real bank statements from other companies' customers, on a product that has no sign-in today | Rulings in §7; the pilot gate; a penetration test; least privilege; encryption with crypto-shredding |
| **A wrong box, estimate or signal** | A box on the wrong line, an estimate read as a fact, or a stacking alert raised by one lender's payment change destroys trust or misleads a credit decision | Unique-match rules with a direction witness and a self-check (§5.4); estimates only with both inputs, always labelled, and pooled across a lender's payment changes; stacking counted across distinct lenders only (§6.4); advisory signals only |
| **Fraud false positives** | Honest merchants flagged | Flags only, reason codes with evidence, never refusals; blind spots stated |
| **Throughput** | One worker thread; scans were last measured at about 23 s per page. One instance per pilot means no failover | Dedicated instances per tenant; queue fairness; a volume check before each pilot and an availability target, not an SLA (§9.3); L5d workers; a self-hosted GPU for scans |
| **Capacity** | One owner and orchestrated agents; SOC 2 needs named human owners for controls | Stage the work (§9); buy a compliance-automation service if the owner chooses (a vendor, not a code dependency) |
| **Regulation** | Disclosure laws; an APR helper that computes wrongly carries liability | Counsel review of L7; the lender stays responsible for disclosures; the calculator is labelled as an aid |
| **Registry drift** | Funders appear monthly; each tenant's market differs | L3 tenant aliases and the review path into the shared ledger |
| **Data residency and privacy law** | Canadian lenders may require Canadian hosting (UNVERIFIED). Statements can be personal data under GLBA, PIPEDA, Quebec's Law 25 and state laws | A Canadian-region instance when a Canadian lender signs (§12 Q40); counsel covers the privacy laws before the pilot (§9.2 item 7) |
| **Concurrent edits** | `webapp/app.py` and `app.js` were changing during this session | Each sub-project spec re-reads the code on its own base commit |

## 12. Owner decisions needed

Each question lists the recommended option first. The questions are grouped by when the owner's answer is needed, so the first group can be settled in one sitting.

### 12.1 Needed before §4.3 step 2 starts

These shape L1, L2 v1 and L5a, which start now, and L5b, which follows them.

**Q1. Which sub-projects go first?**
- (a) **Recommended:** L1 evidence on the page, L2 position intelligence and L5 accounts and security, with L0 on the critical path.
- (b) Parity first: L4 fraud, L6 integrations and L5.
- (c) L2, L4 and L7, and postpone security until a pilot is signed.

**Q2. Keep the ruled order for the licence migration?**
- (a) **Recommended:** keep ruling 12. L0 starts after text-first slice A passes zero wrong, and no external pilot starts before L0 ends.
- (b) Allow a read-only measurement of pypdfium2 against PyMuPDF text on the archive now, with the migration itself still after slice A.
- (c) Start L0 now, in parallel with text-first.

**Q3. Deployment model for the first pilots?**
- (a) **Recommended:** tenant-aware code, one dedicated instance (its own VM) per pilot lender in our cloud.
- (b) One pooled multi-tenant service from the start.
- (c) An on-premise install at the lender.

**Q4. How do users sign in?**
- (a) **Recommended:** SSO through OIDC (Entra ID, Google Workspace, Okta), with local break-glass admin accounts using MFA.
- (b) Email and password with MFA only.
- (c) Both for every user.

**Q5. Which roles?**
- (a) **Recommended:** Admin, Underwriter, Viewer, Auditor (§7.4.2).
- (b) Admin and User only.
- (c) Per-permission custom roles.

**Q6. Which licences are allowed for new dependencies?**
- (a) **Recommended:** permissive licences (MIT, BSD, Apache-2.0, ISC, ZPL, and similar), and MPL-2.0 only when used unmodified. No GPL, AGPL or LGPL.
- (b) Also allow LGPL libraries used unmodified (psycopg, for example).
- (c) Permissive licences only, with no MPL-2.0.

**Q7. Model channels for external tenants (the legacy visual OCR rung, the visual pair and hosted extraction)?**
- (a) **Recommended:** all three off in the pilot, enforced by `TENANT_MODE=external` (§7.4.9). Scans go to local Tesseract, else review. Revisit any model rung only on a GPU we host, under a data processing agreement, after its weights' licence is checked.
- (b) All three off permanently for external tenants.
- (c) The visual pair allowed on the current Vast host with the tenant's opt-in.

**Q8. Under `TENANT_MODE=external`, what does a forced OCR request do?**
- (a) **Recommended:** it runs local Tesseract, and the statement goes to review when that fails.
- (b) It is refused with a plain message.
- (c) The option is hidden from external tenants.

**Q9. Unmasked source views (markdown, result, md/html downloads) after sign-in exists?**
- (a) **Recommended:** Underwriter and Admin only, each view an audit event.
- (b) Mask everywhere except the page image.
- (c) Admin only.

**Q10. Default retention?**
- (a) **Recommended:** the tenant sets it. By default, documents and analyses are deleted 180 days after the last access. Audit events, which hold no statement content, are kept 7 years.
- (b) Keep until the tenant deletes.
- (c) 30 days by default.

**Q11. Evidence locator scope for v1?**
- (a) **Recommended:** boxes for digital statements; page only for scans and the visual pair when the page is known.
- (b) Wait until scans can be boxed too.
- (c) Page only everywhere, with no boxes.

**Q12. Should L1 and L2 targets be fixed now?**
- (a) **Recommended:** keep the proposed targets (zero wrong boxes; 95% of rows located; 95% underwriter agreement on positions) and let the first measurement propose changes for the owner to approve.
- (b) Set targets only after the first measurement.
- (c) Stricter: 98% located before release.

**Q13. Remaining-balance estimates: when shown, and when shipped?**
- (a) **Recommended:** only when the funding credit is in the statements and the tenant has set a factor rate; always labelled "Estimate". Shipped in L2 v1: on a dedicated instance (Q3 (a)) today's global Settings already belong to one tenant, and the factor has no default, so nothing shows until the tenant's admin sets one (§4.2).
- (b) The same rule, shipped in months 3–6, after L5a's per-tenant settings files (§9.1).
- (c) Never estimate; show observed payments only.
- (d) Always estimate, with a default factor and a typical term.

**Q14. When is a position "active", what is the funding window, and when do two streams of one lender form one position?**
- (a) **Recommended:** the cadence table in §6.4 (daily 7 days, weekly 10, biweekly 18, monthly 35, else 30); a 10-day funding window; and two streams of one lender on one account linked when the later one starts within the earlier one's active window and they share at most two dates. All three become tenant settings later.
- (b) One 30-day window for every cadence.
- (c) The tenant must set them before positions show.

**Q15. Do position signals change the package decision?**
- (a) **Recommended:** no. They are advisory, like flag groups (D7).
- (b) A stacking signal moves the package to review.
- (c) The tenant chooses, through L7 rules.

**Q16. Does equipment financing count toward stacking signals?**
- (a) **Recommended:** no. It stays a counted lender with its type shown, but stacking counts MCA, revenue-based and online term lenders only.
- (b) Yes, every counted lender.
- (c) A tenant setting.

**Q17. When does the learning loop (L3) start?**
- (a) **Recommended:** months 3–6, after L5a, so every lender decision a licensee sees carries a signed-in actor from its first day.
- (b) Now, on the house tenant, with the free-text actor revenue review already uses (§4.2); signed-in actors follow when L5a lands.
- (c) After the first pilot asks for it.

### 12.2 Can wait: needed before the pilot gate

These can wait while step 2 runs, but the pilot gate (§9.2) needs each answer, and counsel, the penetration test and insurance take weeks to arrange.

**Q18. Which cloud hosts pilots?**
- (a) **Recommended:** Azure, which matches the company's Microsoft sign-in and gives Entra ID single sign-on and Key Vault.
- (b) AWS.
- (c) Google Cloud.
- (d) Fly, which the owner has ruled demo-only.

**Q19. Penetration test before the first external pilot?**
- (a) **Recommended:** yes, a scoped external test before the first external upload.
- (b) Within the pilot's first month.
- (c) Only when SOC 2 requires it.

**Q20. Fund the first-year fixed costs (about $55,000–$150,000, §10.4)?**
- (a) **Recommended:** yes, staged. Counsel, the penetration test and insurance before the first pilot; compliance tooling when the pilot starts; the Type I audit around month 6.
- (b) Only counsel and the penetration test until a pilot converts to an annual contract.
- (c) No external pilot until a lender prepays enough to cover them.

**Q21. SOC 2 path?**
- (a) **Recommended:** start readiness now, Type I around month 6, then a Type II window.
- (b) Wait until a customer asks.
- (c) ISO 27001 instead.

**Q22. Brand and legal entity?**
- (a) **Recommended:** a separate brand and legal entity, with contract terms that Capital Infusion's lending side never sees tenant data.
- (b) Sell under the Capital Infusion name.
- (c) Decide after the first pilot.

**Q23. Pilot shape?**
- (a) **Recommended:** 2–3 small or mid-sized MCA funders as paid design partners, 60–90 days, with the scorecard in §10.5.
- (b) One large funder.
- (c) ISOs and brokers first.

**Q24. Pricing unit?**
- (a) **Recommended:** per statement above a monthly floor that includes a volume; a scan surcharge once a scan path exists; an annual licence with a floor fee for dedicated or on-premise instances.
- (b) Per page.
- (c) Per seat.

**Q25. Pilot price level and monthly minimum?**
- (a) **Recommended:** a monthly minimum (the floor) of about $1,500 on a dedicated instance, with a volume included, and about $1–$1.50 per statement above it; the pilot fee credited to an annual contract. The floor covers the pilot tenant's estimated $600–$1,100 a month (§10.4). The per-statement rate sits inside the newcomers' band and below MoneyThumb.
- (b) About $2–$3 per statement with no floor, matching MoneyThumb. At a small funder's 300–600 statements a month this may not cover a dedicated instance.
- (c) Free pilots.

**Q26. Support hours and response targets?**
- (a) **Recommended:** US business hours, Eastern time; first response within 1 hour any day for S1 (suspected exposure, instance down), 1 business day for S2 (a wrong figure or box), 3 business days for S3 (§9.3).
- (b) Business hours for every severity, S1 included.
- (c) Around the clock.

**Q27. What availability does a pilot agreement promise?**
- (a) **Recommended:** a target, not an SLA with service credits: available in support hours, outside the announced release window, about 99% of the time in a month; up to one day of uploads re-sent after a restore; the restore within the drill's measured time (§9.3).
- (b) A formal SLA with service credits. It needs a second instance to fail over to, which the pilot cost model does not include (§10.4).
- (c) No availability promise during the pilot.

**Q28. May our support staff read a tenant's data?**
- (a) **Recommended:** only through a time-limited grant that the tenant's admin approves, with every read an audit event.
- (b) Never. The lender reproduces problems with fabricated statements.
- (c) Standing access for named staff, under the contract.

**Q29. May a licensee's statements be used to build a new bank parser?**
- (a) **Recommended:** only with that lender's written permission for each document. The work happens inside the lender's instance, fixtures stay fabricated, and no statement value enters a commit or test.
- (b) Never. New parsers come only from Capital Infusion's own statements.
- (c) Under a blanket clause in the pilot agreement.

**Q30. Data return and deletion at the end of a pilot?**
- (a) **Recommended:** 30 days to export the analyses, packages and audit events, and the original PDFs on request; then deletion by destroying the tenant key within 30 days, proven by a restore check, with a deletion certificate (§9.3).
- (b) Deletion immediately at contract end.
- (c) 90 days to export.

**Q31. How is coverage checked before a pilot signs?**
- (a) **Recommended:** the lender lists the banks behind a recent period of its files (names and counts only); we report the share expected to validate from the archive's per-bank counts; the shadow period measures the real share inside the lender's instance, and a gap of more than 10 points is reviewed with the lender (§9.3). The 10-point threshold is the author's proposal; the owner sets it.
- (b) The lender sends sample statements for a test run before signing. That needs the instance, the data processing agreement and the pilot gate first.
- (c) No check before signing; the shadow period is the first measurement.

### 12.3 Can wait: later

These can wait for the months §9.1 gives them.

**Q32. How do tenants run after the pilots?**
- (a) **Recommended:** per-tenant containers on a shared host, each with its own disk, database, key, settings file and process; a dedicated VM for a lender that pays for one; L5d pooling when tenants number in the dozens. This cuts infrastructure from about $200–$300 to about $70–$100 per tenant a month (§10.4).
- (b) A dedicated VM for every tenant, priced to cover it.
- (c) Move L5d pooled tenancy into months 3–6.

**Q33. Database when pooling (L5d)?**
- (a) **Recommended:** SQLite per dedicated instance now; Postgres with a BSD or Apache driver (pg8000 or asyncpg) when pooling.
- (b) Postgres now, for every instance.
- (c) Stay on SQLite until a tenant forces a change.

**Q34. Learning-loop scope?**
- (a) **Recommended:** decisions stay within the tenant. Only payee aliases may be shared: opt-in, stripped of personal names (D11), and admitted to the shared registry only through the existing two-agent research.
- (b) No cross-customer learning ever.
- (c) A pooled network of positions and merchants across customers.

**Q35. Can a tenant's own alias make a payee a counted lender for that tenant?**
- (a) **Recommended:** yes, for that tenant only, marked `tenant_alias` in the evidence.
- (b) Tenant aliases only reach the review tier.
- (c) No tenant aliases.

**Q36. Fraud output format (L4)?**
- (a) **Recommended:** reason codes with evidence and boxes on the page; no single score in v1.
- (b) A 0–100 score, like competitors.
- (c) Both.

**Q37. First integration?**
- (a) **Recommended:** API v1 with webhooks, plus one CRM connector chosen by the first pilot lender.
- (b) LendSaaS first.
- (c) Salesforce first.

**Q38. Open banking?**
- (a) **Recommended:** an optional connector the tenant contracts for, never required by the core. It is a paid service, not a code dependency.
- (b) We resell a provider.
- (c) Out of scope for 12 months.

**Q39. Publish the benchmark?**
- (a) **Recommended:** publish the method, the scoring code and aggregate sealed-holdout results by bank family, with MoneyThumb shown as agreement and never as truth.
- (b) Share privately with prospects only.
- (c) Do not publish.

**Q40. Canadian data residency?**
- (a) **Recommended:** offer a Canadian-region instance when a Canadian lender signs.
- (b) United States only.
- (c) Canada from the start.

## 13. Out of scope

- Implementation plans. Each sub-project writes its own spec and plan.
- Any change to the ADB, NSF, currency, repair or anti-optimizer doctrines, or to the lender rulings.
- Legal advice. §10 and the L7 notes are research, and counsel must review contracts, disclosures and data processing terms.
- Hosting pilots on Fly.
- Sending any licensee's statements to a hosted model or a marketplace GPU.
