<!-- Companion to PHASE2_REMAINDER_PLAN.md — research/audit memo produced 2026-09-03 by an independent Fable 5.1 agent under Ocean's direction; read-only investigation; verbatim except for privacy scrubbing of archive filename fragments. -->

# Ocrolus — Product, API, Schema and Observable-Behavior Research Memo

Fetch date for every source: **2026-09-03**. Angle: product/API/docs/schemas/observable behavior, from the perspective of a team building a bank-statement intelligence engine that must accept unseen bank layouts without a parser per bank.

Conventions in this memo:
- **SAYS** = quoted or closely paraphrased from a fetched page (URL given).
- **STRONGLY INFERRED** / **PLAUSIBLE HYPOTHESIS** = my inference; labeled as such.
- Where a page could not be fetched, that is stated; nothing is invented for it.

---

## 1. SOURCES

### 1.1 Fetched successfully (docs.ocrolus.com — public, no gate; `.md` suffix returns markdown)

| # | URL | What it contained |
|---|-----|-------------------|
| 1 | https://docs.ocrolus.com/ | Landing; "Ocrolus supports over 2,100 form types"; nav to guides, API reference, forms directory, status page, help center; points to `/llms.txt`. |
| 2 | https://docs.ocrolus.com/llms.txt | Full documentation index (635 lines; every guide and reference URL). |
| 3 | https://docs.ocrolus.com/docs/definitions | Glossary: Book, Document, Form Type, Uploaded Document, Mixed Document, Uploaded Mixed Document, Uploaded Form, Image Group, PK, NSF, YTD. |
| 4 | https://docs.ocrolus.com/docs/how-ocrolus-works | Four stages (Classify, Capture, Detect, Analyze); three workflows (Classify / Instant / Complete); upgrade rules. |
| 5 | https://docs.ocrolus.com/docs/ocrolus-api-flow | Plaid + PDF "docs_to_digital" flow; `upload_intent`; mismatched transactions review. |
| 6 | https://docs.ocrolus.com/docs/document | Document object attributes (`pk`, `name`, `page_count`, `status`, `md5`, `rejection_reason`). |
| 7 | https://docs.ocrolus.com/docs/rejection-reasons | Full list of 11 rejection reasons with descriptions. |
| 8 | https://docs.ocrolus.com/docs/code-types | Index of code-type pages (bank account category/type, book status, document status, extra fields, rejection reasons). |
| 9 | https://docs.ocrolus.com/docs/dashboard-instant | Instant definition; Instant→Complete auto-transition; document-level upgrade (Feb 14 2024); Instant document statuses. |
| 10 | https://docs.ocrolus.com/reference/book-info | Full example JSON for Book information (docs, mixed_docs, bank_accounts, periods, status_tags, book_class). |
| 11 | https://docs.ocrolus.com/reference/book-summary(.md) | Cash Flow Analytics summary endpoint: params, response outline, async, transaction limits. |
| 12 | https://docs.ocrolus.com/docs/detect-signals(.md) | Detect signal catalogue (Resistant AI metadata/forensic signals; Ocrolus algorithmic signals); red/green/blue legend. |
| 13 | https://docs.ocrolus.com/docs/authenticity-score | Score 0–100; LOW 0–55, MEDIUM 56–80, HIGH 81–100; `form_authenticity` structure; workflow guidance. |
| 14 | https://docs.ocrolus.com/docs/authenticity-status.md | High/Medium/Low; ternary vs binary mode; config not self-service. |
| 15 | https://docs.ocrolus.com/docs/detect | Detect overview; Resistant AI + Ocrolus ALGO; signal categories; webhook events; supported docs. |
| 16 | https://docs.ocrolus.com/docs/webhook-overview | 5-second webhook timeout; org- vs account-level; event table. |
| 17 | https://docs.ocrolus.com/docs/organization-level-webhook.md | 33 org-level events with descriptions; max five webhooks. |
| 18 | https://docs.ocrolus.com/docs/account-level-webhook.md | 31 account-level events (e.g., `BOOK_VERIFIED`, `DOC_VERIFIED`, `ANALYTICS_COMPLETED`); payload field names. |
| 19 | https://docs.ocrolus.com/docs/cash-flow-analytics(.md) | Pointer to endpoints and a Google-Sheets data dictionary (URL captured; sheet itself not fetched). |
| 20 | https://docs.ocrolus.com/docs/bank-statements | Supported regions (US, CA, MX, UK); workflow; duplicate-transaction rule. |
| 21 | https://docs.ocrolus.com/docs/getting-started-bank-statements(.md) | Workflow; processing-time sentence; full enriched-transaction JSON; BSIC analytics JSON. |
| 22 | https://docs.ocrolus.com/docs/image-groups | Image group workflow; formats (JPEG, PNG, BMP, single-image TIFF). |
| 23 | https://docs.ocrolus.com/docs/capture | Capture description ("machine learning, computer vision, and micro-templates"). |
| 24 | https://docs.ocrolus.com/docs/classify.md | Classify description; forms array structure; "avoid the complexity of exception handling". |
| 25 | https://docs.ocrolus.com/docs/classify-first.md | Classify-first workflow; upgrade paths; uniqueness values with confidence. |
| 26 | https://docs.ocrolus.com/docs/instant-classify-with-uvcf.md | Instant Classify = ML-only categorization. |
| 27 | https://docs.ocrolus.com/docs/pdf-mixed-documents.md | Mixed-PDF workflow; results split into Forms vs Bank Statements. |
| 28 | https://docs.ocrolus.com/docs/all-supported-documents(.md) | Table of document types with "Document classification" and "Data extraction" Yes/No; asterisk = Instant; only "Bank Statements*" carries the asterisk. |
| 29 | https://docs.ocrolus.com/docs/forms-directory.md | 11 form categories. |
| 30 | https://docs.ocrolus.com/docs/document-status.md | Capture-workflow and classification-workflow document statuses with descriptions. |
| 31 | https://docs.ocrolus.com/docs/book-status-code.md | Book statuses CREATED/UPLOAD/VERIFYING/VERIFIED/DELETED. |
| 32 | https://docs.ocrolus.com/docs/polling-for-completion.md | Monitoring guidance (poll with back-off; webhooks). |
| 33 | https://docs.ocrolus.com/docs/confidence-score.md | Field-level confidence 0–1 for Forms/Classification endpoints; routing guidance. |
| 34 | https://docs.ocrolus.com/docs/bank-account.md | Bank account object incl. `activity_info` {active, missing}. |
| 35 | https://docs.ocrolus.com/docs/period.md | Period object incl. `primary_recon_error_reason`, `secondary_recon_error_reason`. |
| 36 | https://docs.ocrolus.com/docs/form-data.md | Form data object (`raw_fields`, `value`, `is_empty`, `alias_used`, `source_filename`). |
| 37 | https://docs.ocrolus.com/docs/bank-account-category.md | BUSINESS ACCOUNT / PERSONAL ACCOUNT / UNKNOWN. |
| 38 | https://docs.ocrolus.com/docs/bank-account-type.md | SAVINGS, CHECKING, CREDITCARD, SWEEP, IOLTA, RESERVE, CASH MANAGEMENT. |
| 39 | https://docs.ocrolus.com/docs/extra-fields.md | Analytics `extra_fields` (weekday balances, NSF counts, txn summaries, MCA, etc.). |
| 40 | https://docs.ocrolus.com/docs/bank-statement-income-calculator.md | BSIC: included/excluded deposits; large-deposit threshold; NSF/overdraft day counts; up to 36 months; "Missing: Jan 2023 for [Account Name]". |
| 41 | https://docs.ocrolus.com/docs/accounts-section.md | Dashboard Accounts page: organized by statement periods. |
| 42 | https://docs.ocrolus.com/docs/transactions-section.md | Dashboard Transactions columns; tag editing; bulk actions. |
| 43 | https://docs.ocrolus.com/docs/book-overview.md | Bank accounts widget ("Statement date ranges", "Total statement months"); link to metrics sheet. |
| 44 | https://docs.google.com/spreadsheets/d/1KIM6qISE96V3gw_d59ZpnWQk3yjV3vvRjtRptBE6yqg/edit | Book Overview metrics definitions (ADB, NSF count, DCR, etc.). |
| 45 | https://docs.ocrolus.com/docs/book-upgrade.md | INSTANT vs COMPLETE definitions; forward-only; requeue on upgrade. |
| 46 | https://docs.ocrolus.com/reference/upgrade-doc.md | Document upgrade endpoint; restrictions; example (`document_status: GROOMING`, `processing_type: STANDARD`). |
| 47 | https://docs.ocrolus.com/reference/upgrade-mixed-doc.md | Mixed-doc upgrade; forward-only. |
| 48 | https://docs.ocrolus.com/reference/cancel-file-verification.md | Cancel only in VERIFYING; `accept_charges`. |
| 49 | https://docs.ocrolus.com/reference/create-a-book.md | `book_class` allowed values COMPLETE / INSTANT / INSTANT_CLASSIFY_ONLY / INSTANT_CLASSIFY_ISO_CAPTURE; `book_type` DEFAULT/OPTIMA/WIDGET; `xid`. |
| 50 | https://docs.ocrolus.com/reference/upload-document.md | Upload PDF to Book: `form_type` required; 200 MB; response `uploaded_docs[]`. |
| 51 | https://docs.ocrolus.com/reference/upload-mixed-document.md | Upload mixed PDF; no `form_type`; error scenarios. |
| 52 | https://docs.ocrolus.com/reference/upload-image.md | Image upload; formats; `image_group_pk`. |
| 53 | https://docs.ocrolus.com/reference/multipartform-data-payloads.md | multipart rules; filename rules. |
| 54 | https://docs.ocrolus.com/reference/mixed-document-status.md | Mixed doc status JSON incl. `pages[{page_idx, doc_type}]`. |
| 55 | https://docs.ocrolus.com/reference/book-classification-summary.md | `process_unknowns` ("unknown page reassignment and checksum-based duplicate detection"); forms array fields. |
| 56 | https://docs.ocrolus.com/reference/mixed-doc-classification-summary.md | Full example JSON incl. `form_type{name, account_type, account_source, display_name}`, `uniqueness_values`. |
| 57 | https://docs.ocrolus.com/reference/grouped-mixed-doc-classification-summary.md | `split_unknowns`, `group_bank_statements`; groups with `pages[]`. |
| 58 | https://docs.ocrolus.com/reference/book-status.md | Book status endpoint; `book_class`; docs/mixed_docs arrays. |
| 59 | https://docs.ocrolus.com/reference/transactions.md | `/v1/transaction` raw transactions; full transaction JSON incl. `bbox`, `page_doc_pk`, `period_pk`; `uploaded_docs`, `bank_accounts`, `bank_checks`. |
| 60 | https://docs.ocrolus.com/reference/enriched-transactions.md | Enriched transactions; async; 100k/1M transaction limits. |
| 61 | https://docs.ocrolus.com/reference/form-field-data.md | Form field example with `confidence`. |
| 62 | https://docs.ocrolus.com/reference/bsic.md | BSIC JSON endpoint example. |
| 63 | https://docs.ocrolus.com/reference/cash-flow-features.md | Cash flow features / summary params. |
| 64 | https://docs.ocrolus.com/reference/ocrolus-status-codes-api.md | All Ocrolus error codes (e.g., 1504 PageDoc not found, 1512 max pages, 1513 instant ML error, 9004 analytics still processing). |
| 65 | https://docs.ocrolus.com/reference/api-rate-limit-policy.md | 20 rps/org; 200 MB; 3,000 pages/document; 2,000 docs/Book; 40,000 pages/Book; 75,000,000-pixel image cap. |
| 66 | https://docs.ocrolus.com/docs/endpoint-categories.md | Command/Upload/Query/Download endpoint types. |
| 67 | https://docs.ocrolus.com/reference/suspicious-activity.md | Legacy Suspicious Activity Flags (FILE_TAMPERING) — "superseded by our new Detect offering". |
| 68 | https://docs.ocrolus.com/reference/doc-fraud-signals.md | Document-level Detect JSON (signals, visualizations, form_authenticity, `is_image_based_pdf`). |
| 69 | https://docs.ocrolus.com/reference/book-fraud-signals.md | Book-level Detect JSON (same shape, plus `authenticity_status`). |
| 70 | https://docs.ocrolus.com/reference/signal-definition.md | Signal object; 43 `identifier` enum values. |
| 71 | https://docs.ocrolus.com/reference/documentanalysis-definition.md | `uploaded_doc_type` BANK_STATEMENT/PAYSTUB/FORM; `detect_status` PENDING/COMPLETED/UNABLE_TO_PROCESS/UNSUPPORTED/DELETED; `is_image_based_pdf`. |
| 72 | https://docs.ocrolus.com/reference/formanalysis-definition.md | FormAnalysis object. |
| 73 | https://docs.ocrolus.com/reference/visualizationregion-definition.md | Visualization region (overlay image URL). |
| 74 | https://docs.ocrolus.com/reference/supportingdata-definition.md, .../supportingdatavalues-definition.md | Supporting data keys per signal (e.g., `unreconciled_bank_statement_balance_data`: period_pk, page_number, period_opening_balance, period_ending_balance, total_txn_sum, delta). |
| 75 | https://docs.ocrolus.com/reference/signalanalysis-definition.md | SignalAnalysis object. |
| 76 | https://docs.ocrolus.com/changelog and month pages /changelog/september-2026, august-2026, july-2026, june-2026, may-2026, april-2026 | Release notes: webhook replay (Sep 26); Detect `signal_type`/`description`/`bbox` and Book Summary period-level reconciliation fields (Jul 26); Authenticity Status (Apr 26); async analytics; etc. |
| 77 | https://docs.ocrolus.com/docs/changelog.md | (Not release notes) the Dashboard "Changelog" audit-trail feature for income calculations. |
| 78 | https://docs.ocrolus.com/docs/encompass-getting-started.md, .../encompass-classify.md | Encompass setup; Classify statuses in Encompass (Processing / Rejected / Unknown / Classified); eFolder routing. |
| 79 | https://docs.ocrolus.com/docs/getting-started-with-smb-lending.md | SMB workflow; endpoints; `book_class: INSTANT` example; REJECTED example for unknown doc. |
| 80 | https://docs.ocrolus.com/docs/product-sku-smb.md | SMB SKUs ("SMB CASH FLOW APP ... in under 10 seconds", DOCS2DIGITAL, etc.). |
| 81 | https://docs.ocrolus.com/docs/receivers.md | Encore kickout fields; Book copy statuses. |
| 82 | https://docs.ocrolus.com/docs/income-alerts.md, .../automated-conditions.md | Alerts/conditions framework (alert catalogue lives in an external sheet; not fetched). |
| 83 | https://docs.ocrolus.com/docs/getting-started-in-mortgage.md, .../plaid.md, .../ingesting-plaid-json-reports.md | Fetched; contained only form lists / Plaid setup — no schema details. |
| 84 | https://security.ocrolus.com/ | Certifications (SOC 2, SOC 3, ISO/IEC 27001, PCI DSS, CSA STAR L1; GDPR/CCPA/CPRA/GLBA/PIPEDA/VCDPA/23 NYCRR 500); half-yearly SOC audit; subprocessors; BitSight 760; RTO 4 h. |
| 85 | https://legal.ocrolus.com/ (+ sub-processor list https://legal.ocrolus.com/sub-processors/list-of-ocrolus-sub-processors-f51b4947) | Sub-processor table incl. "Ocrolus East Private Limited — Human-in-the-loop (HITL) for data processing and operational and technical support — India"; OpenAI, Anthropic, Extend AI, Resistant AI, Smarty, Snowflake, AWS, GCP, Tableau (all US). |
| 86 | https://www.ocrolus.com/ ; https://www.ocrolus.com/product/analyze/ ; https://www.ocrolus.com/supported-documents/bank-statements ; https://www.ocrolus.com/fraud-detection-ai/ (renders platform page) | Marketing claims ("99+% accuracy"; fraud detection "powered by Resistant AI"; testimonials). |
| 87 | https://www.ocrolus.com/faq/ | FAQ (2,100 docs; English-only; formats JPEG/PNG/BMP/GIF/TIFF; HITL rationale). |
| 88 | https://www.ocrolus.com/blog/the-role-humans-with-ai-document-automation/ ; https://www.ocrolus.com/blog/ocrolus-vs-manual-document-review/ | HITL routing statements; "99% success rate across over 2100 document types" (classification). |
| 89 | https://www.ocrolus.com/blog/introducing-instant/ ; https://www.prnewswire.com/news-releases/ocrolus-launches-new-cost-effective-instant-solution-for-analyzing-financial-documents-301933096.html ; https://www.pymnts.com/loans/2023/ocrolus-debuts-ai-powered-document-analyzer-instant/ | Instant launch (Sep 20 2023): "machine-only", "returns insights in seconds", Complete "includes human data verification for lower quality documents". |
| 90 | https://www.ocrolus.com/blog/ocrolus-detect-authenticity-score/ ; https://www.ocrolus.com/blog/how-ocrolus-detect-uncovers-fraud-and-mitigates-losses/ | Authenticity Score bands (0–29/30–49/50–79/80+ in the blog); fingerprinting roadmap. |
| 91 | https://docs.argyle.com/integrations/ocr/ocrolus | Partner view: authenticity bands; error statuses FAILED/REJECTED; rejection reasons surfaced. |
| 92 | https://www.ocrolus.com/customer-stories/fora-financial-small-business-lending-automation/ ; https://www.ocrolus.com/customer-stories/tab-bank-reduces-bank-statement-review-from-30-minutes-to-seconds-with-ocrolus/ | Case-study turnaround claims. |
| 93 | https://www.capterra.com/p/232462/Ocrolus/reviews/ ; https://www.softwareadvice.com/data-extraction/ocrolus-profile/ | User reviews (2022) on turnaround and missed data. |

### 1.2 Failed / gated (content NOT used)

| URL | Result |
|-----|--------|
| https://docs.ocrolus.com/reference/api-overview | 404 |
| https://docs.ocrolus.com/docs/period-analytics (and .md) | 404 (listed in search results, page gone) |
| https://docs.ocrolus.com/reference/activityinfo-definition (and .md) | 404 |
| https://docs.ocrolus.com/docs/transactions-type.md | Returned only an overview table (uploaded_docs / bank_accounts / txns), not the field list. |
| https://docs.ocrolus.com/ocrolus-api/docs/suspicious-activity-flags | 404 (legacy path referenced by period.md) |
| help.ocrolus.com articles: 8511628423572 (Uploading new Bank Statements), 14992040193940 (What is an image-based PDF), 360059233851 (Plaid and PDF flow), 360058224292 (Dashboard vs API analytics), 19405464241300 (Instant Overview) | HTTP 403 (Zendesk bot block). Only search-snippet text available; used sparingly and marked. |
| https://www.g2.com/products/ocrolus/reviews | 403 |
| https://www.inman.com/2023/09/27/... | 403 |
| https://fintract.ai/blog/ocrolus-alternatives-bank-statement/ | 403 (competitor page; would have been low-trust anyway) |
| https://legal.ocrolus.com/privacy-policy | 404 (real URL is /legal/privacy-policy-958a2463; not fetched) |
| web.archive.org | Tool cannot fetch web.archive.org. |
| Google Sheet cash-flow data dictionary (1DfsvHbx5QB76IYxhY5hi1UkYtVsaOb4z) | URL captured; not fetched. |
| YouTube transcripts | No transcript located; only ocrolus.com video landing pages found (not fetched). |

---

## 2. DOCUMENTED BEHAVIOR (what the pages SAY)

### 2.1 Intake / upload

- **Container model.** SAYS (definitions): Book = "A container for all Documents in a Case or Loan Application. This container primarily serves as a boundary to correlate data." Document = "A single sequence of Bank Statement pages. The sequence can contain pages from multiple Bank Statements, including different Bank Accounts and Account Holders." Uploaded Document = "Contains pages with only one form type ... either created as a child of an uploaded mixed document or as a standalone document." Mixed Document = "A single-page PDF or multi-page PDF containing different form types that you prefer Ocrolus to classify." Uploaded Mixed Document: "Each form type that is found within the mixed PDF will be broken out and given an Uploaded Document UUID and a Form UUID."
- **Book creation** (create-a-book): `book_class` "Can be either 'COMPLETE' or 'INSTANT'"; allowed values in the schema: `COMPLETE`, `INSTANT`, `INSTANT_CLASSIFY_ONLY`, `INSTANT_CLASSIFY_ISO_CAPTURE`. `book_type` `DEFAULT`/`OPTIMA`/`WIDGET` ("This feature is in beta"). `xid`: "A free form field that can be used to associate a Book with some identity outside of Ocrolus."
- **Three upload doors.**
  - Upload PDF to Book (`/v1/book/upload`): `form_type` = "The code identifying the type of Document that you're uploading." Response: `uploaded_docs[{pk, uuid, name, page_count, checksum, created_ts, id}]`.
  - Upload Mixed Document PDF (`/v1/book/upload/mixed`): no `form_type`; response `mixed_uploaded_docs[...]`. Errors: "Invalid PDF format", "Document already exists in the Book", 1401 Book not found, 1103 missing param, 2102 permission.
  - Upload Image to Book → `image_group_pk`; then "Finalize Image Group". Formats: "JPEG, PNG, BMP, and TIFF (only single-image TIFF file)".
  - Upload aggregator JSON (Plaid Asset Report / Transactions JSON) with `upload_intent=docs_to_digital` to trigger mismatch detection; "If upload_intent is not specified, the system considers default as add_analytics."
- **Limits** (api-rate-limit-policy): "The rate limit is set at 20 requests per second per organization"; "File upload requests can not exceed over 200 MB"; "the number of documents in a book can not exceed 2000"; "the total number of pages in a single document can not exceed 3000"; "the total number of pages in a book can not exceed 40,000"; "The image dimensions in the PDF should not exceed a maximum of 75,000,000 pixels". Error 1512: "Document contains more than the maximum allowed pages"; 8002: "This book has reached the maximum allowable uploads".
- **Regions/languages.** SAYS (bank-statements): "We currently support bank statements from the United States, Canada, Mexico, and the United Kingdom." FAQ: "Currently Ocrolus processes English-language documents".
- **Duplicates at file level.** Rejection reason `DOCUMENT DUPLICATE OF {}`: "An identical document with the given name has already been uploaded to this Book." Document object carries `md5` "MD5 Checksum of file"; upload response carries `checksum`. Book classification summary `process_unknowns=true` "performs unknown page reassignment and checksum-based duplicate detection" and adds `is_original` / `form_uuid_duplicate_of`.

### 2.2 Classification & document types

- **Taxonomy size.** "over 2,100 form types"; forms directory has 11 categories (Assets, Closing, Credit, Disclosure, Identification, Income/Employment, Legal, Mortgage specific forms, Other, Property, Tax forms). The all-supported-documents table has two capability columns per type: "Document classification" (Yes/No) and "Data extraction" (Yes/No) — many types are classification-only (e.g., "Form 1006 - Request for Verification of Deposit | Yes | No"). Legend: "An asterisk (*) next to the document type indicates that it can be processed in an instant manner." In the fetched table only **"Bank Statements\*"** carries the asterisk.
- **Form type object for bank statements** (mixed-doc classification summary):
  ```json
  "form_type": {
    "name": "BANK_ACCOUNT",
    "account_type": "CHECKING",
    "account_source": "STANDARD_STATEMENT",
    "display_name": "BANK STATEMENT"
  }
  ```
  Elsewhere the same document is typed `uploaded_doc_type: "BANK_STATEMENT"` (transactions endpoint, Detect) and `doc_type: "BANK_ACCOUNT"` (mixed-document status `pages[]`). Other names seen: `PAYSTUB`, `W2`, `A_1040_2023`, `INVOICE`, `DRIVERS_LICENSE`, `UNKNOWN`.
- **Classification output** (book-classification-summary): `forms[]` with `form_uuid`, `upload_origin` (`MIXED` | `PRE_IDENTIFIED`), `status` (`COMPLETED` | `REJECTED` | `CLASSIFIED`), `form_type{...}`, `is_original`, `form_uuid_duplicate_of`, `uniqueness_values[{display_name, raw_field_key, value, confidence}]`, `rejection_reason`. Example uniqueness value: `{"display_name": "Account Holder", "raw_field_key": "bank_account:accountHolder", "value": "ALEXANDER HAMILTON", "confidence": 1}`. `upload_details` carries `mixed_doc_page_indexes: [0]` and `confidence: null`.
- **Grouped summary**: `split_unknowns` (each unclassified form its own group vs one consolidated UNKNOWN group); `group_bank_statements` — "When true, bank statements sharing account holder, bank name, and period automatically group together." Each group has `pages: [0,1,2,3]`.
- **Human review in classification.** SAYS (how-ocrolus-works): Classify routes uncertain documents "to Ocrolus verifiers for human review". Blog: "Classifications with imperfect confidence are routed to Ocrolus data classification and verification specialists for data labeling and quality control." Instant Classify: "an automated, machine-learning-based solution to categorize uploaded PDFs and images into distinct document types" (machine-only).
- **Encompass Classify statuses**: Processing; Rejected ("unsupported document file formats or sizes, illegible content"); Unknown ("unable to be classified by Ocrolus because the document (or certain pages in the documents) is not a supported form type"); Classified. Attachment "segments are put into the document container appropriate to their classification."
- **Rejection reasons tied to classification**: `DOCUMENT TYPE NOT SUPPORTED` — "The document is not of the form_type that was set during upload and cannot be captured." `INVALID DOCUMENT` — "The document type could not be identified or is not supported for the given account."

### 2.3 Page handling (mixed / multi-doc uploads, rotation, missing pages)

- **Pages are addressable.** Transactions carry `page_idx` and `page_doc_pk` ("Unique ID of the specific page within a Document from which transaction details are retrieved"). Error codes 1504 "PageDoc not found", 1508 "Page index out of range", 2105 "No permission to access this page", 7004 "Page index missing from uploaded images in the image bucket". Mixed-doc status returns `pages: [{"page_idx": 0, "doc_type": "BANK_ACCOUNT"}]`. Child uploaded-doc names encode source pages: `"name": "july.pdf(0,1,2,3)"`.
- **Unknown pages**: `process_unknowns` triggers "unknown page reassignment".
- **Rotation / deskew**: **not documented anywhere fetched.** (Stated as a gap.)
- **Missing pages**: there is **no rejection reason or signal literally named "missing pages"**. What exists:
  - Rejection reasons: `INCOMPLETE TRANSACTION DATA` — "Bank statement transactional data does not contain the expected information."; `NO_TRANSACTIONS` — "No transactions were found on the statement."; `NO_PERIOD_SUMMARY` — "No period-level information such as opening balance, closing balance, statement start date, and end date were found on the document."; `STATEMENT_UNRECONCILED` — "The sum of the transactions does not match the beginning and ending balances stated on the statement."
  - Detect signal `txn_data_unavailable` with supporting keys `period_pk, page_number, period_being_date [sic], period_end_date`; `incomplete_bank_statement_txn_data` with keys `page_number, txn_pk, txn_date, description, amount`.
  - Bank account `activity_info`: `active` — "Series of date ranges during which this Bank Account shows activity"; `missing` — "Series of date ranges during which this Bank Account does **not** show activity".
  - BSIC: "if the system detects statements for December 2022 and February 2023, but not January 2023, BSIC flags 'Missing: Jan 2023 for [Account Name]'".
  - Book Overview widget shows "Statement date ranges" and "Total statement months".

### 2.4 Native PDF vs scanned/image handling

- SAYS (DocumentAnalysis): `is_image_based_pdf` — "A field to identify that the document is an image-based PDF, and not a parseable electronic PDF issued by a financial institution/payroll provider."
- Detect signals that name the modality: `image_of_known_document` — "The document is submitted as an image of a type typically available as a native PDF, limiting access to metadata and structural details needed for verification."; `has_only_images` — "The document contains only images, possibly due to scanning or conversion, limiting the ability to extract and verify text."; `digital_print` — "exported from a digital source, such as a PDF converted into an image"; `screenshot`.
- Instant rejection: `INSTANT NOT SUPPORTED` — "Instant was unable to parse the document and could not capture and return data." Press release: Complete "includes human data verification for lower quality documents." Blog: "some more complex or lower quality documents will require Complete".
- Capture page: "each document is processed through the most suitable digitization tool"; uses "machine learning, computer vision, and micro-templates".
- Help-center article "What is an image-based PDF?" exists (gated 403); the search snippet says parsable PDFs allow extraction of "font, spacing, and alignment" while image-based PDFs are "flattened" and "not all data information can be extracted" (snippet only).

### 2.5 Processing tiers and turnaround

- SAYS (book-upgrade): INSTANT — "Fully automated AI/OCR extraction, typically returned in seconds"; COMPLETE — "AI extraction plus human-in-the-loop verification when needed. Highest accuracy". "Book class changes only go in one direction: INSTANT ──► COMPLETE"; "Existing documents are requeued and reprocessed under the new Book class."; "All documents in the Book must finish their current processing" before upgrade.
- SAYS (dashboard-instant): "Instant Books are processed solely through automated means without any human intervention." Auto-fallback: "In case any bank statements in the Book cannot be processed via Instant, the entire Book transitions to the Complete". Since Feb 14 2024, document-level upgrade within an Instant Book. Instant document statuses: "Completed, Completed with Detect signals found, Rejected, Rejected: Instant not supported, Rejected: Invalid document, Processing, Processing: Instant not supported."
- Classify-first: `INSTANT_CLASSIFY_ONLY` Books; upgrade endpoints take `upgrade_type: INSTANT | COMPLETE`; "Document upgrades are forward-only"; "Child documents that belong to a mixed document cannot be upgraded with this endpoint" (use the mixed-doc upgrade). Upgrade response shows `"document_status": "GROOMING", "processing_type": "STANDARD"` (doc) and `"processing_type": "INSTANT"` (mixed).
- **Turnaround statements**: "Document analysis generally takes a few minutes, although factors such as document quality, source, and suspected fraud or suspicious activity can cause analysis to take longer." (getting-started-bank-statements). SMB SKU: "processes bank statement data into a standardized cash flow picture in under 10 seconds". Case studies: Fora — "Turnaround times for data extraction reduced to under 15 minutes"; TAB Bank — "we now get with Ocrolus basically instantly". Reviews (Capterra/SoftwareAdvice, 2022): "Chase, Bank of AM, Wells Fargo took no time, NOW it could take 30-1 hour to extract"; "Waiting times can be longer for more complicated bank statements"; "it doesn't even verify the statements within an hour". **No SLA is documented.** Security portal lists RTO 4 hours (disaster recovery, not processing).

### 2.6 Human-in-the-loop / verification

- Document status `VERIFYING`: "The document is under manual review to ensure data accuracy and integrity." `GROOMING`: "post-processing cleanup or refinement before final verification." `VERIFICATION_COMPLETE`: "successfully processed and verified. Extracted data is now available."
- Cancel verification: only "while in the `VERIFYING` state"; requires `accept_charges`; "Cancellation permanently deletes all associated data". Rejection reason "Customer Requested Cancellation (not billable)".
- Where: sub-processor list — "Ocrolus East Private Limited — Human-in-the-loop (HITL) for data processing and operational and technical support — India". Search results reference "Verifiers on the platform (Ocrolus east and U.S.)" (job listing snippet) and walk-in "Data Verifier" hiring in Gurugram.
- Feedback loop: verified data "feeds back into the system to continuously train models" (blog).
- Accuracy claims: "over 99+% accuracy" (marketing); "99% success rate across over 2100 document types" (classification, blog).

### 2.7 Output schema (real field names)

**Book info** (`/v1/book/info`, abridged, verbatim keys):
```json
"docs": [{"pk": 56253658, "status": "VERIFICATION_COMPLETE", "name": "bankstatementexample.pdf", "pages": 1, "md5": "...", "image_group_pk": null, "mixed_uploaded_doc_pk": null, "document_class": "COMPLETE"}],
"mixed_docs": [{"pk": 11602174, "status": "COMPLETED", "name": "...pdf", "pages": 1, "md5": "...", "image_group_pk": null, "rejection_reason": null, "document_class": "COMPLETE"}],
"bank_accounts": {"14359008": {"pk": 14359008, "book_pk": 34653848, "name": "111234567890 FIRST CITIZENS BANK CHECKING", "bank_name": "FIRST CITIZENS BANK", "account_type": "CHECKING", "account_holder": "ALEXANDER HAMILTON", "account_number": "111234567890", "holder_zip": "78521", "holder_country": "US", "holder_state": "TX", "holder_city": "Brownsville", "holder_address_1": "2450 COURAGE ST", "holder_address_2": "STE 108", "account_category": "PERSONAL ACCOUNT",
  "periods": [{"pk": 41907910, "uuid": "...", "bank_account_pk": 14359008, "begin_date": "04/01/2021", "end_date": "04/15/2021", "begin_balance": "10000", "end_balance": "10000", "primary_recon_error_reason": null, "secondary_recon_error_reason": null, "uploaded_doc_pk": 56193560}],
  "account_holders": ["ALEXANDER HAMILTON"]}},
"status_tags": {...}, "book_class": "COMPLETE"
```
**Raw transaction** (`/v1/transaction`, verbatim):
```json
{"page_idx": 0, "bank_account_pk": 12942296, "amount": "-299.35", "bbox": [142, 2971, 2208, 3021], "txn_date": "09/10/2020", "page_doc_pk": 304060599, "pk": 3573037068, "uploaded_doc_pk": 50867399, "description": "AMERICAN EXPRES DES: PAYMENT ...", "txn_pk_duplicate_of": null, "comment": "", "explanation": "", "has_probable_transfers": false, "tags": {}, "period_pk": 37445192}
```
`bbox`: "The bounding box (bbox) coordinates are the pixel units that enclose the text data on a page." Note: **no running balance, no txn_type/credit-debit flag, no per-transaction confidence** in the transaction object; direction is the sign of `amount` (a string here, a number in enriched output). Supporting objects: `uploaded_docs{pk: {name, status, pages, pk, uuid, rejection_reason, uploaded_doc_type}}`, `bank_accounts{pk: {account_holder, periods[...]}}`, `bank_checks[{uuid, bank_account_pk, amount, pay_to, txn_date, check_number}]`.

**Enriched transaction** (`/v2/book/{uuid}/enriched_txns`): `txn_pk, txn_date ("2021-04-30"), description, bank_account_pk, uploaded_doc_pk, uploaded_doc_name, amount (-1000), counterparty, fintech_loan_source, fintech_mca_source, comment, is_noteworthy, page_idx` plus ~60 boolean tags (`atm, bank_loan, checks, credit_card, deposits, expense, fintech_loan, fintech_mca, internal_transfer, nsf, nsf_paid_or_negative_balance, nsf_returned_or_not_paid, overdraft, payroll, probable_recurring_txns, returned_item, revenue, revenue_deduction, reversed, sba, venmo_zelle_cashapp, wire_transfer, withdrawals, txn_four_zeros, txn_five_zeros, ...`). May 2026: `include_pending_plaid_transactions` param.

**Form field** (non-bank-statement forms): `"drivers_license-General:dob": {"value": "01/06/1958", "is_empty": false, "alias_used": null, "source_filename": "DRIVING-LICENSE.pdf", "confidence": 1}` — no page/bbox on form fields in the documented example.

**Period recon fields** (Book Summary, July 2026): `reconciled`, `recon_error_absolute_amount`, `recon_error_pct_of_average_daily_balance`, `primary_recon_error_reason`, `secondary_recon_error_reason`, `high_amount_average_daily_balance`, `balance_ending_with_zero`, `high_txns_count_atm_over_cash`, `has_weekend_transactions`, `no_txn_in_weekdays_within_period`, `high_txns_amount_atm_over_cash`. The enumerated values of `*_recon_error_reason` link to a legacy "Suspicious Activity Flags" page that now 404s; a search snippet says these attributes "have been deprecated and superseded by ... Document-Level Fraud Signals". Not resolvable from live docs.

**BSIC / bank-statement income** JSON: per account `deposits[{date, description, amount, exclude, is_large}]`, `nsf_transactions[]`, `calculations{nsf_count, statement_summary[{begin_date, end_date, total_deposits, total_nsf_count, beginning_balance, ending_balance}], large_deposit_summary{average_deposit, percentage_amount, deposit_threshold}, total_deposit_summary{deposits, included_deposits, excluded_deposits}, total_included_months, qualifying_income_average}`.

### 2.8 Status / webhook lifecycle

- **Book**: `CREATED` → `UPLOAD` → `VERIFYING` → `VERIFIED` (→ `DELETED`). "VERIFIED: Indicates that the processing of all the documents uploaded to this book is complete."
- **Document (capture workflow)**: `QUEUED`, `PROCESSING`, `FAILED` ("most likely due to an invalid format or file error"), `GROOMING`, `VERIFYING`, `VERIFICATION_COMPLETE`, `REJECTED` ("likely because it is unsupported or failed validation checks"), `DELETING`, `DELETED`. **Classification workflow**: `CLASSIFIED` ("type has been identified ... Processing will begin shortly"), `COMPLETED`, plus the shared ones. "VERIFICATION_COMPLETE and COMPLETED statuses return extracted data."
- **Detect status** per document: `PENDING`, `COMPLETED`, `UNABLE_TO_PROCESS`, `UNSUPPORTED`, `DELETED`.
- **Webhooks**: 33 org-level events including `book.classified`, `book.verified` ("Capture process completed, all docs verified/rejected"), `book.completed` ("triggers when Capture, Detect, Income, Analytics complete"), `book.analytics_v2.generated`, `document.classification_succeeded` / `document.classification_failed` ("File is corrupt"), `document.verification_succeeded` / `document.verification_failed`, `document.detect.signal_found` / `signal_not_found` / `unable_to_process`, `book.detect.signal_found`, `mixed_document.rejected`, `image_group.*`, `plaid.upload_*`, `book.pacing.discrepancies_found`, `book.copy.*`. Account-level names: `BOOK_VERIFIED`, `DOC_VERIFIED` ("A single document within a book has been verified or rejected"), `ANALYTICS_COMPLETED`. "Webhook requests sent by Ocrolus have a timeout of 5 seconds." Up to five org webhooks. Sept 2026: Dashboard delivery monitoring and replay of failed deliveries.
- Analytics gating: "every Document in a Book must achieve VERIFICATION_COMPLETE status before you can request analytics"; 425/9004 "Analytics are still being processed, please check back momentarily"; `async=true` → `202` + `job_id`; async mandatory over 100,000 transactions; >1,000,000 rejected (422/1100).

### 2.9 Detect (fraud/tamper) signals

- Two engines: "Resistant AI: document fraud detection, which operates at the file and pixel level, detecting metadata anomalies, digital modifications, suspicious PDF structure" and "Ocrolus Algorithmic (ALGO)" content-level checks. Platform page: fraud detection "powered by Resistant AI"; Resistant AI is a listed sub-processor.
- **Signal object**: `identifier` ("stable and can be relied upon in your application logic"), `display_name`, `signal_count`, `page_number` ("one-indexed ... null if the fraud signal isn't specific to any particular page"), `signal_type` (`RISK` | `INFO` | `TRUST`, added Jul 2026), `description`, `supporting_data[{values[{key, value, data_type}]}]`; Jul 2026: "Tampering and content signals also now include bounding box (`bbox`) coordinates".
- **43 stable identifiers** include bank-statement-relevant: `account_holder_address_edits, account_holder_edits, account_number_edits, account_type_edits, date_edits, dollar_amount_edits, transaction_description_edits, other_edits, page_edited, misaligned_text, suspected_template, suspicious_address, fingerprint_match, future_date, future_year, invalid_date, invalid_year, invalid_bank_statement_txn_date, txn_data_unavailable, unreconciled_bank_statement_balance_data` (+ paystub/W-2 ones). `*_edits` supporting keys: `field_name, original_text, tampered_text`. `page_edited`: `edit_source`. `unusual_document_source`: `doc_origin`. `fingerprint_match`: `source`. `suspected_template`: `confidence`.
- Resistant-AI group identifiers seen in JSON: `rai_grp_sample_content_page`, `rai_grp_template_farmed_document`, `rai_grp_interactive_document_page`, `rai_has_known_producer_document` ("Produced in PDFium"). Catalogue names: `anomalous_pdf_structure, suspicious_producer, overlapping_content, anomalous_font, digital_print, unusual_pdf_structure, content_tampering_suspected, image_of_known_document, document_from_online_generator, editing_software_detected, content_diff_between_versions, has_only_images, has_piece_info, expected_pdf_structure (trust), unmodified_per_metadata (trust), screenshot`.
- **Visualization**: `visualizations[{page_number, page_visualizations[{visual_type: "edit_regions", display_name: "Received Document", description: "The original document was recovered. Changes between the received document and the original document are highlighted in red to reveal edits.", image_url}]}]`; image "is the analyzed page with translucent colored squares overlaid on the regions of suspected fraud."
- **Authenticity**: `form_authenticity{version: "1.0", score: 25, reason_codes[{code: "FARMED_TEMPLATE", confidence: "MEDIUM", description}], authenticity_status: "LOW"}`. Docs thresholds: 0–55 LOW, 56–80 MEDIUM, 81–100 HIGH; blog and Argyle docs give 0–29 / 30–49 / 50–79 / 80+ (older or partner-specific banding). "thresholds can be customized"; Authenticity Status "not self-service". Reason code example `PROCESSED_DOCUMENT` ("Document was resaved using common document tools", MEDIUM).
- ALGO bank-statement signals: `unreconciled_bank_statement_balance` — "The bank statement's beginning and ending balances do not reconcile based on the transactions for the given period."; `invalid_bank_statement_txn_date` — "The transaction date does not fall within the statement period."; `future_date`; `future_year`. Supporting keys for the unreconciled signal: `period_pk, page_number, period_opening_balance, period_ending_balance, total_txn_sum, delta`.
- Supported for Detect: bank statements, pay stubs, W-2s; "Upcoming: tax forms (1040, 1099), identity documents, utility bills."
- Legacy endpoint (Suspicious Activity Flags) returned only `reason: "FILE_TAMPERING"` with `suspicious_activity_page_indexes[]`; "superseded by our new Detect offering".

### 2.10 Analyze analytics fields

- Book summary: `daily_balances`, `daily_cash_flows`, `net_cash_flows_by_month`, `minimum_balance_by_month`, `maximum_balance_by_month`, `average_daily_balance_by_month`, `expense_by_month`, `revenue_by_month`, `deposits_by_month`, `negative_balances_by_month`, category time series (payroll, insurance, ATM, tolls, PayPal, checks, fintech/bank/other loans, MCA, cards, merchant services, crypto, gambling, investments, taxes, transfers, NSF/overdraft fees), counterparties, NAICS/business verification, loan inquiries; params `exclude_bank_account_pks`, `exclude_months`.
- `extra_fields`: `weekday_balances` → `average_daily_balance_weekday`, `negative_balances_by_month_weekday`; `nsf_count` → `nsf_count_by_month`; `nsf_transactions_returned_or_not_paid`, `nsf_transactions_paid_or_negative_balance`; `txn_summary` → `deposit_sum, deposit_count, withdrawal_count, withdrawal_sum, txn_count`; period-analytics variants prefixed `period_analytics` incl. `average_daily_balance`, `average_deposit`.
- Book Overview sheet definitions: "Average Daily Balance — Mean of balance amount for each day"; "NSF Count — Count of transfactions tagged as NSF"; "Debt Coverage Ratio — (total revenue - total expense + total loan payments) / total loan payments".
- Duplicate-transaction rule: "if two transactions that happened on the same date, have the same description, and the same amount in the same Book, then Ocrolus considers one as a copy of the other" with "Description matching flexibility"; retained via `txn_pk_duplicate_of`.
- Aug 2026: "industry-aware analytics"; "BNPL transaction tag"; automatic business verification.

### 2.11 Multi-account handling

- Document definition explicitly allows "pages from multiple Bank Statements, including different Bank Accounts and Account Holders"; search snippet of the same page: "During data capture, Ocrolus attributes the Account Holder, Bank Account, and Period information to each processed Transaction therein."
- Output: `bank_accounts` keyed by PK, each with `periods[]`, each period with `uploaded_doc_pk`; transactions carry `bank_account_pk` and `period_pk`. `account_holders[]` is a list; `account_type` enum includes SWEEP, IOLTA, RESERVE, CASH MANAGEMENT, CREDITCARD; `account_category` BUSINESS ACCOUNT / PERSONAL ACCOUNT / UNKNOWN ("cannot be readily classified ... often requiring further investigation").
- Grouping at classification: `group_bank_statements` by "account holder, bank name, and period".

### 2.12 Reconciliation / balance verification

- Hard gate: rejection `STATEMENT_UNRECONCILED` and `NO_PERIOD_SUMMARY` (see 2.3). Detect `unreconciled_bank_statement_balance` with `delta`. Period-level `reconciled`, `recon_error_absolute_amount`, `recon_error_pct_of_average_daily_balance` (Jul 2026). Dashboard: "Account data is organized by statement periods rather than a single continuous date range."

### 2.13 Accuracy / SLA claims

- "Analyze financial documents with over 99+% accuracy, every time" (marketing); "99% success rate across over 2100 document types" (classification, blog); "Better: Over 95% of documents that we have are processed through Ocrolus" (testimonial). No documented processing SLA; status page at status.ocrolus.com.

### 2.14 Security / data handling

- security.ocrolus.com: SOC 2, SOC 3, ISO/IEC 27001, PCI DSS, CSA STAR Level 1; GDPR, CCPA, CPRA, GLBA, PIPEDA, VCDPA, 23 NYCRR 500; "half-yearly audit period"; BitSight 760; Qualys A+; RTO 4 hours; "Data Access Level: Restricted".
- Sub-processors (legal.ocrolus.com): AWS ("hosting ... data storage and processing"), Google Cloud, Snowflake ("Data storage"), OpenAI ("Cloud infrastructure for data processing"), Anthropic ("data processing and analysis"), Smarty (US address validation), Salesforce/Tableau, Resistant AI ("Enhancement of document fraud analysis"), Extend AI ("Enhancement of document processing results and data analysis") — all US; Ocrolus East Private Limited — HITL — India.
- **Retention periods: not found** on any fetched page (privacy policy not fetched).

---

## 3. OBSERVED-BEHAVIOR INFERENCES

1. **Pipeline shape = ML extract → automated grooming → human queue → complete.** STRONGLY INFERRED from the ordered statuses `QUEUED → PROCESSING → GROOMING → VERIFYING → VERIFICATION_COMPLETE`, GROOMING defined as "post-processing cleanup or refinement before final verification", and cancel being allowed only in VERIFYING. Humans review an already-normalized draft; the machine stage (with reconciliation/dedupe checks) runs before routing.

2. **Reconciliation is the acceptance gate for a statement, not page counting.** STRONGLY INFERRED: the terminal rejections `STATEMENT_UNRECONCILED`, `NO_PERIOD_SUMMARY`, `NO_TRANSACTIONS`, `INCOMPLETE TRANSACTION DATA` are all arithmetic/structural, and no "missing pages" reason exists. A statement whose opening + Σtxns ≠ closing is not returned partially — it is rejected (at least in Instant). PLAUSIBLE HYPOTHESIS: in Complete, verifiers repair such cases and the recon fields (`reconciled=false`, `delta`) survive as flags rather than rejections; the July 2026 exposure of `recon_error_pct_of_average_daily_balance` implies they tolerate small deltas by ratio.

3. **Completeness is modelled at two layers, both time-based.** STRONGLY INFERRED: per-statement (period summary + reconciliation) and per-account-over-time (`activity_info.missing`, BSIC "Missing: Jan 2023"). A "page 3 of 7" check is not surfaced anywhere. PLAUSIBLE HYPOTHESIS: they may use page-of-N internally, but the product contract is "period coverage", which generalizes across banks that do not print page counts.

4. **Front-door modality triage (native text vs image) drives tiering.** STRONGLY INFERRED from `is_image_based_pdf` ("not a parseable electronic PDF issued by a financial institution"), the Resistant signals `image_of_known_document`/`has_only_images`, and `INSTANT NOT SUPPORTED`. Instant is built on the text layer plus issuer-specific "micro-templates"; anything image-based or off-template falls to OCR + HITL. The 2022 reviewer remark that Chase/BofA/Wells "took no time" while others took 30–60 min is consistent with issuer templates for large banks and human fallback for the long tail (PLAUSIBLE HYPOTHESIS as to cause).

5. **Classification performs a light "identity extraction" before full capture.** STRONGLY INFERRED from `uniqueness_values` (account holder, bank, period; SSN/name for other forms) with confidence returned at classification time, and from grouping "by account holder, bank name, and period". This is what lets them dedupe forms (`is_original`, `form_uuid_duplicate_of`) and assemble multi-file statements before extraction.

6. **The bank-statement type is a tuple, not a label.** STRONGLY INFERRED from `form_type{name: BANK_ACCOUNT, account_type: CHECKING, account_source: STANDARD_STATEMENT}`: family × account type × source variant. PLAUSIBLE HYPOTHESIS: other `account_source` values exist (e.g., transaction-history printouts, aggregator-derived) that get different completeness rules.

7. **Transactions are "verified or rejected", never probabilistic.** STRONGLY INFERRED: field-level `confidence` exists only for Forms/Classification endpoints (doc says so explicitly); the transaction object has no confidence, no running balance, no debit/credit flag. Quality is expressed through statuses, rejection reasons, and reconciliation flags — a design consistent with HITL making the output binary-trusted. Instant customers are told to use classification confidence to "reject Instant responses in favor of the Complete mode."

8. **Pages are first-class entities and provenance is pixel-based.** STRONGLY INFERRED from `page_doc_pk`, `page_idx`, `bbox` in "pixel units", error codes about PageDoc, and child doc names like `july.pdf(0,1,2,3)`: every page is rasterized to a canonical image with its own PK; a "Document" is a sequence of PageDocs; mixed-doc splitting reassigns PageDocs to child uploaded docs ("unknown page reassignment"). Detect visualizations are overlays on that same raster.

9. **Account → Period → Transaction is independent of file boundaries.** STRONGLY INFERRED: `period.uploaded_doc_pk` links a period back to its source file, but transactions attach to `period_pk` and `bank_account_pk`, so multi-account and multi-period files are decomposed into a graph, and analytics are computed on the graph, not per file.

10. **Duplicates are linked, not deleted.** STRONGLY INFERRED from `txn_pk_duplicate_of` and `form_uuid_duplicate_of`; analytics skip the copies while preserving the audit trail.

11. **Tamper detection exploits PDF version history on native files only.** STRONGLY INFERRED from `content_diff_between_versions`, the "original document was recovered" visualization, `original_text`/`tampered_text` supporting keys and `has_piece_info`; these are impossible on scanned images, which is why image-based PDFs get an INFO-type modality signal instead.

12. **Capture and analytics are separate asynchronous stages.** STRONGLY INFERRED from `book.verified` (capture done) vs `book.completed` (capture + Detect + income + analytics), the 425/9004 "still being processed" code, and `async=true` jobs.

13. **Authenticity bands are tenant-configurable and have drifted.** STRONGLY INFERRED from the mismatch between docs (0–55/56–80/81–100) and blog/Argyle (0–29/30–49/50–79/80+), plus "thresholds can be customized" and "not self-service".

14. **`processing_type: STANDARD` is the internal name for Complete.** PLAUSIBLE HYPOTHESIS from the upgrade-doc example returning `STANDARD` after a COMPLETE upgrade.

---

## 4. LESSONS FOR OUR ENGINE

**Document classification taxonomy**
- Model bank statements as a tuple `{family: BANK_STATEMENT, account_type, source_variant}` with `UNKNOWN` as a first-class outcome at page level, not just document level (Encompass: "certain pages in the documents" can be Unknown).
- Record `upload_origin` (pre-identified by caller vs classified by us) — Ocrolus keeps both and rejects with different reasons (`DOCUMENT TYPE NOT SUPPORTED` vs `INVALID DOCUMENT`).
- Emit a few "uniqueness values" (holder, bank, account tail, period) with confidence at classification time; use them to group pages/files into statements before extraction and to dedupe (`is_original`, `duplicate_of`).
- Keep per-type capability flags (classify-only vs extract-capable) so unseen layouts can still be classified and routed even when extraction is not trusted.

**Completeness / partial-statement detection**
- Make reconciliation the primary per-statement completeness test and give it structured supporting data: `period_opening_balance, period_ending_balance, total_txn_sum, delta, page_number`, plus a relative measure (`delta / average_daily_balance`).
- Distinguish reasons exactly as Ocrolus does: no period summary found; no transactions found; transactions found but incomplete; unreconciled. Each is a different failure mode for an unseen layout.
- Add account-level coverage: `activity_info{active[], missing[]}` and month-gap flags per account ("Missing: Jan 2023 for [Account]"); expose "statement date ranges" and "total statement months" per account.
- Add a date-in-period check per transaction (`invalid_bank_statement_txn_date`) — cheap, layout-agnostic, and catches page mix-ups.
- Do not depend on printed "page x of y"; Ocrolus does not expose it.

**Transaction schema**
- Adopt: `pk, txn_date, description, amount (signed), bank_account_pk, period_pk, uploaded_doc_pk, page_idx, page_doc_pk, bbox, duplicate_of, tags{}, comment/explanation`. Keep raw (`/v1/transaction`) and enriched (`enriched_txns`) as separate layers.
- Note Ocrolus's gaps you may choose to fill: running balance per line, explicit debit/credit type, per-line confidence, currency (no currency field anywhere in the documented schema — relevant to our currency doctrine).

**Confidence representation**
- Field-level 0–1 confidence for header/period fields; for transactions, prefer status + reason codes + reconciliation flags over floats, and expose `is_image_based_pdf` and a modality signal so downstream can set expectations.
- Provide a documented "confidence → route" table (reject / human review / accept) as Ocrolus does.

**Exception routing**
- Two-tier, forward-only processing classes (machine-only vs machine+HITL) with document-level upgrade; automatic promotion when machine-only fails; cancellation semantics only while in the human queue; "not billable" reason for client cancels.
- Enumerated rejection reasons (11 in Ocrolus) rather than free text; a distinct `FAILED` (file-level) vs `REJECTED` (content-level) status.
- Separate lifecycle events for classify, verify, detect, analytics; a `book.verified` vs `book.completed` distinction; webhook replay.

**Provenance to page/box**
- Rasterize each page to a canonical image with a stable page ID; store `bbox` in that image's pixel space for every transaction and (ideally) every header field; carry source page indexes in child-document names or metadata when splitting mixed files.
- For tamper/anomaly evidence, emit both machine data (`original_text`/`tampered_text`, `field_name`, `bbox`) and an overlay image per page.

---

## 5. NOTABLE GAPS (documented nowhere fetched)
Rotation/deskew handling; per-bank Instant eligibility list; page-of-N checks; per-transaction confidence; running balance; currency field; processing SLA; data-retention periods; the enumerated values of `primary_recon_error_reason` (legacy page 404); Complete-tier human review percentage.
