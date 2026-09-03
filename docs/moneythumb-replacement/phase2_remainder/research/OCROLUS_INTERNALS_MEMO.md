<!-- Companion to PHASE2_REMAINDER_PLAN.md — research/audit memo produced 2026-09-03 by an independent Fable 5.1 agent under Ocean's direction; read-only investigation; verbatim except for privacy scrubbing of archive filename fragments. -->

# Ocrolus Internals: Reverse-Engineering Memo (INTERNALS angle)

Date of research: 2026-09-03. All fetches and searches performed today via WebSearch/WebFetch. A sibling agent covers the product docs/API schema; this memo prioritizes patents, engineering statements, hiring signals, operations, and stack signals, and only uses docs where they expose internals.

## 0. Epistemic key

- DOCUMENTED = stated by Ocrolus (docs, patent text, press release, executive quote) or by a primary third party who observed it, and fetched or quoted directly.
- STRONGLY INFERRED = not stated, but the only economical explanation of two or more documented facts.
- PLAUSIBLE HYPOTHESIS = consistent with the evidence; alternatives exist; I say which I favor and why.
- SNIPPET-ONLY = the page itself could not be fetched; the claim rests on a search-engine snippet of it. Treat as weaker than DOCUMENTED.

Nothing below should be read as knowledge of Ocrolus's code. Ocrolus has exactly one granted patent family and publishes no engineering blog or papers; the internal picture is assembled from a 2017-era patent, current docs behavior, hiring text, and executive statements.

## 1. Executive summary (the ten strongest findings)

1. Ocrolus holds ONE granted patent: US 11,087,409 B1, "Systems and methods for generating accurate transaction data and manipulation" (Bobley, Yang; priority 2016-01-29; filed 2017-01-30; granted 2021-08-10; 48 claims). A continuation (US 2021/0366055 A1) is listed as abandoned. Google Patents assignee and full-text queries for "Ocrolus" return nothing else. DOCUMENTED.
2. The patent describes the 2016-2017 system explicitly: proprietary OCR (Tesseract named as the reference engine), a knowledge base of financial-institution templates, generic-OCR-then-zoom-into-blocks, preprocessing DAG with caching, Celery/RabbitMQ-or-Redis task queue on AWS VPC with GPUs, transaction bounding boxes with a spatial index, a per-transaction "quality identifier" from character/word OCR confidence plus statement type and transaction type, balance reconciliation and running-balance chaining as autonomous OCR-error detectors, and a Back-Office Tool that decomposes verification into parallel microtasks ending in a subject-matter-expert page-by-page review. DOCUMENTED.
3. Current docs describe the capture engine as "machine learning, computer vision, and micro-templates" and say "each document is processed through the most suitable digitization tool to optimize both accuracy and efficiency" — i.e., a per-document digitization router exists. DOCUMENTED (existence); its members are inferred.
4. OCR/AI vendors: the May-2023 press release says the stack includes "subsystems from Amazon, Google and its own proprietary deep learning architectures" plus OpenAI GPT text embeddings; the security portal lists subprocessors OpenAI, Google Cloud, AWS, Snowflake; the 2026 platform page names OpenAI, Gemini, Anthropic and fine-tuned open-source models. No page names Textract, Vision, or Document AI explicitly. DOCUMENTED (vendors) / STRONGLY INFERRED (Textract and/or Google Document AI are the "subsystems").
5. Classification precedes extraction and is page-level with collation into forms; "Uniqueness Values" (extracted key fields such as employer/employee name) are used to split same-type forms and group pages; low-confidence pages come back UNKNOWN; "classifications with imperfect confidence are routed to Ocrolus data classification and verification specialists." DOCUMENTED.
6. Confidence is FIELD-level (0-1) on form fields and classification; transactions carry bbox/page/duplicate/transfer flags but no per-transaction confidence in the public schema. "Universal Calibration" (2025-2026) is described as calibrating heterogeneous model confidences onto one scale using human-verified ground truth, selecting the best model per task, and sending tasks that cannot be completed with perfect confidence to "multiple AI agents to check each other's work." DOCUMENTED (claims), mechanics inferred.
7. Reconciliation is a first-class gate AND a fraud signal AND (per the patent) an error-correction loop: rejection reason STATEMENT_UNRECONCILED, Detect ALGO signal unreconciled_bank_statement_balance, and patent claims 6-8 that use balances to "autonomously identify potential OCR conversion errors" and rank likely-erroneous transactions for human attention. DOCUMENTED.
8. Human review is confidence-gated and microtask-parallelized; the pipeline status sequence QUEUED -> CLASSIFIED -> PROCESSING -> GROOMING -> VERIFYING -> VERIFICATION_COMPLETE exposes a post-extraction "grooming" step before human verification; verifiers "correct or edit any incorrect details captured by the Ocrolus proprietary systems" and "perform reconciliation of various amounts." Worker accuracy is checked algorithmically. Verified outputs become labeled training data (240M+ pages claimed). DOCUMENTED.
9. Fraud detection is three-layer: Resistant AI (file/pixel forensics: metadata, producer, PDF structure, incremental-update diffs, fonts, overlays, screenshots, online generators, AI-generated artifacts), Ocrolus ALGO checks (reconciliation, date validity, IRS math, address validation, issuer fingerprinting for top banks), and a fusion layer (Authenticity Score 0-100, Status with highest-risk-wins). Detect runs on both parsable and image PDFs; Ocrolus samples flagged documents daily for ground truth and reports true-positive rate above 90%. DOCUMENTED.
10. Observable behavior supports a layout-coverage gradient: big-bank statements were fast/automatic while "credit unions and other unknown banks could take time" (2022 reviews), and Instant is offered only for select document types with an INSTANT NOT SUPPORTED rejection path. DOCUMENTED (reviews, docs); the inference that coverage is per-issuer-learned rather than universal is STRONGLY INFERRED.

## 2. Patents

### 2.1 Search coverage
- Google Patents XHR query assignee=Ocrolus: one hit (US20210366055A1, Ocrolus, LLC). Fetched OK.
- Google Patents XHR full-text q="ocrolus": one relevant hit (same family). Fetched OK.
- Google Patents XHR inventor="Sam Bobley": one hit (same family; status ACTIVE for the granted member). Fetched OK.
- Google Patents XHR inventor="Pieter Nel": four unrelated hits, none Ocrolus. Fetched OK.
- Google Patents XHR assignee="Ocrolus, Inc.": query parse returned unrelated design patents (no Ocrolus, Inc. filings surfaced). Fetched OK but uninformative.
- Justia assignee page (patents.justia.com/assignee/ocrolus-llc): HTTP 403. SNIPPET-ONLY: "a patent was assigned to Ocrolus, LLC on August 10, 2021 with inventors Sam Bobley and Michael Yang."
- USPTO image-ppubs PDFs (12354319, 12164657, 11087409): image-only CCITT PDFs; text not extractable via fetch. The Google Patents HTML pages were used instead.
- Conclusion: Ocrolus's public patent estate is a single family. No patents on layout models, confidence calibration, or fraud detection were found under Ocrolus. Several search mis-hits (below) belong to other companies and are useful comparators only.

### 2.2 US 11,087,409 B1 (granted) — "Systems and methods for generating accurate transaction data and manipulation"
Assignee Ocrolus LLC; inventors Sam Bobley, Michael Yang; filed 2017-01-30; priority 2016-01-29; granted 2021-08-10; 48 claims. Fetched OK (patents.google.com/patent/US11087409B1/en).

Independent claims (paraphrased closely):
- Claim 1 (method): receive image-based transactions over a network; store in a central data store associated with a unique user identifier; identify the transaction format; apply preprocessing based on that identification; process the preprocessed images into text-based transactions; store a plurality of data for each transaction; associate a quality identifier with each transaction based on the probability that it was processed correctly; apply an identifier based on the quality identifier; transmit the results.
- Claim 20 (system): processor + storage + instructions performing the same steps.

Dependent-claim map (claim numbers as reported by the Google Patents page): preprocessing 2, 3, 22, 23; templates 4, 5; reconciliation of beginning/ending balance 6, 8; running balance 7, 8; Celery task queue 10; GPU 11, 12; machine learning 13-15; bounding boxes 17, 18, 30, 31, 33; quality identifier/confidence 2, 3, 20, 21; microtasks 27, 28, 32, 33; multiple workers 27, 28, 33; duplicate detection 34, 35; transfer detection 36, 37.

Description highlights (quotes are as returned by the fetch):
- OCR: "a proprietary OCR system"; Tesseract is the named reference ("tesseract uses its dictionary to influence the character segmentation step, for improved accuracy"). No commercial engine named.
- Template knowledge base: "accumulating a knowledge base of templates used by financial institutions in the period of past 30 years ... to aid with the OCRing of a specific document." Strategy: "starts with a generic OCR approach to ensure good coverage on font, language character set, color, etc. next, the system takes a practical approach to narrow down OCR read on the identified blocks that are of interest."
- Preprocessing list: de-skewing, de-speckling, binarization, line removal, layout analysis/zoning, line detection, word detection, character isolation/segmentation, lexicon, near-neighbor analysis, grammatical analysis, Benford's law. FIG. 24 is a DAG of preprocessing steps with cached intermediates (binarize once, rotate and re-use).
- Layout: "layout analysis or zoning, which identifies columns, paragraphs, captions, or other features as distinct blocks. This is especially important when processing multi-column layouts and tables."
- Transaction objects: "individual financial transactions are identified by the bounding boxes"; "generates a spatial index linking the X and Y location of the information on the document to the transaction." Each transaction is "linked back to the original location on the original document image."
- Quality identifier: "based on the probability that the text based transaction was processed correctly," analyzing "OCR confidence on a character and word basis as well as the type of statement and type of transaction"; flagged items shaded red, "darker shade of red" for more likely errors; "Red Exclamation Point" for unreadable.
- Reconciliation as error detector: "the arithmetic difference between the ending balance and the beginning balance of a statement must equal the sum of the amounts of all transactions"; "the extracted bank statement or credit card statement account balances are used to autonomously identify potential OCR conversion errors"; "the system works most effectively on running balance statements, followed by daily balance statements and then monthly balance statements"; "It is more efficient to check for errors in the account balances before checking for errors in the transactions."
- Back-Office Tool microtasks: document type and page orientation; account metadata (account number, bank name, account type); transaction boundary identification and bounding-box placement; polarity (+/-); account assignment for multi-account statements ("bounding boxes ... shaded in different colors by account"); balance verification and reconciliation; missing-transaction addition ("NEW TXN"); false-transaction removal ("Not Txn"); final SME page-by-page review. "A hierarchy of bank statement data ... to optimize the parallelization of user tasks in order to achieve the fastest overall turnaround."
- Feedback: "the OCR engine 2203 is able to use transaction data after finishing the OCR 'reading', thereby using the detection results as a feedback mechanism to provide hints of how well OCR did"; "the newly corrected data is dynamically updated to the database and continuously incorporates user-entered information to eliminate the need to inspect certain transactions that were incorrectly flagged for review."
- Infrastructure (FIG. 21/22): AWS VPC, gateway, storage servers; "OCR Engine 2203 comprises a series of servers running an asynchronous task queue/job queue based on distributed message passing" (Celery; RabbitMQ/Redis broker); GPU and multi-core parallelism.
- Analytics: exact-amount transfer matching within seven days; fuzzy sliders (0-25% amount, date window); recurring-transaction search; "dupe" symbol for probable duplicates; a "deduction engine" and "high-order logic" for relationships (FIG. 26 described only "in abstract terms").
- Fraud: 2016-2017 text has search/investigation tooling, not tamper forensics.

### 2.3 US 2021/0366055 A1 (continuation, abandoned)
Same title, filed 2021-08-06, published 2021-11-25; Google Patents lists status Abandoned. Its published claims broaden to "identifies data subsets based on similarity to templates ... annotates findings, analyzes transactions for uniqueness, associates transactions with key identifiers (such as running balances or account numbers), and determines conversion accuracy through correlation analysis." Fetched OK.

### 2.4 Comparator patents surfaced by search (NOT Ocrolus)
- US 12,164,657 B2, LendingClub Bank (Mobley, Li, Mueller; 2022): classify document -> retrieve legitimate-sample features for that class -> metadata detectors (producer/creator, date mismatches, stripped metadata) and content detectors (/MP and TouchUp_TextEdit tags, overlapping text boxes, mixed embedded fonts, multiple fonts per element, annotations, prior PDF versions, tag counts) -> per-feature anomaly scores -> aggregated document anomaly score; cross-document background matching for photographed docs. This is the clearest public description of what a lender-side PDF-forensics stack looks like and matches the Resistant-AI-style signal list Ocrolus exposes.
- US 11,816,430 B2, Intuit (2023): "Metamodeling for confidence prediction" — base extraction model -> confidence features -> meta-model -> threshold routing to auto vs manual. A published template for the confidence-routing pattern Ocrolus describes.
- US 12,354,319 B2, Orbit Healthcare; US 11,195,006 B2, IBM/Gusto; US 8,249,399 B2, IBM (reCAPTCHA-style OCR verification). Unrelated to Ocrolus, though the IBM 2008 patent is the same idea Bobley cites as inspiration (Google Books / CAPTCHA).

## 3. Corporate and technical statement timeline

- 2016 (Sequence Inc review of PerfectAudit, fetched OK): OCR first; "overseas data entry clerks manually enter the data" when OCR fails; founder: "since we sync the transaction data to bank balances the data is guaranteed to be 100% accurate"; reviewer found missing and duplicated transactions and abbreviated descriptions; $0.40/page.
- 2016 (ReleaseWire, Michael Yang "Chairman of Technology"): ML "for efficiency improvement and financial transaction detection." SNIPPET-ONLY (fetch failed: certificate expired).
- 2018 (AlleyWatch Series A, fetched OK): "multiple layers of crowdsourced human micro-validation"; "Our AI will intelligently parse financial statements and pinpoint instances of potential inaccuracies"; inputs "e-statements, scans, and cell phone images."
- 2019 (Sequence Inc review): "OCR engine ... if the PDF quality is such that the OCR engine cannot accurately get the data, someone looks at the statements and enters the data manually, which is done through crowdsourcing overseas"; guarantee moved from 100% to "over 99%." SNIPPET-ONLY (three fetch variants returned the blog index).
- 2020 (Alldus podcast E122, CTO Pieter Nel, fetched description only): topics include "the Data Flywheel concept."
- 2021 (TechCrunch Series C, fetched OK): work the automated system cannot complete "is routed to its own team of analysts and quality control specialists to perform data verification," with "algorithmic checks validating worker accuracy"; Bobley: "clean document from Chase, or a blurry cell phone image from a community bank in Kansas — we'll be able to process it"; new "data quality control facility in Florida"; ML/data-science hiring focus.
- 2021 (Wharton FinTech, Apple Podcasts page fetched OK; Medium/LinkedIn mirrors blocked or thin): "nearly 1,000 employees across four global offices"; "human-in-the-loop infrastructure company."
- 2022-11 (PR Newswire, Detect launch, fetched OK): tampering via "metadata and file structure signatures, editing software fingerprints, font inconsistencies, pixel-level anomalies"; "visualizes tampering ... and often reconstructs original versions"; beta: 4x more potential fraud than a leading competitor.
- 2023-05 (PR Newswire, fetched OK): OpenAI GPT text embeddings "to process semi-structured and unstructured documents ... without human involvement"; stack "includes subsystems from Amazon, Google and its own proprietary deep learning architectures"; "unique ability to create accurate training data in-house"; Zach Haehn (SVP Engineering): "Today, most documents we receive are processed with no human interaction."
- 2023-09 (PR Newswire, Instant launch, fetched OK): "machine-only offering"; Complete "includes human data verification for lower quality documents"; both claim over 99%.
- 2023 (Fintech Blueprint podcast, fetched OK): "we do the human-in-the-loop validation, reconciliation checks, and we ensure that we get to 99 plus percent"; fraud "analyzes the metadata of a document"; roughly 6% of applications suspicious; four-hour turnaround cited.
- 2024-10 (Inspect; PR/HousingWire snippets): discrepancy detection between documents and application data; "over 1,600+ financial document types."
- 2025-03 (Ocrolus blog "keep up with advances in financial AI", fetched OK): "Using verified HiTL decision-ready data, we calibrate AI confidence scores on a standardized scale"; "inconsistent methods of confidence scoring between models mean comparing inches to centimeters"; "thousands of human-in-the-loop verifiers"; positions Ocrolus as an application layer over foundation models.
- 2026-03 (PR Newswire, automated conditioning, fetched OK): "deterministic by design, grounded in selling guide requirements" and "adapts over time to each lender's underwriting patterns."
- 2026-06 (platform page, fetched OK): "Universal Calibration ... selects the most accurate model based on the task at hand"; "Tasks that can't be completed with perfect confidence are routed to multiple AI agents to check each other's work"; partners OpenAI, Gemini, Anthropic plus "open-source models fine-tuned with proprietary training data"; "Ocrolus Data Professionals in SOC-compliant clean-room facilities resolve edge cases."
- 2026-08 (Key Executives / Shift Technology): CTO Zach Haehn departed for Shift Technology. TheOrg shows Ajay Shrivastava as COO & Country Head India (LinkedIn title "CTO"), who built the India GCC to "over 1,250 employees."

## 4. Documentation signals that expose internals (only those relevant to architecture)

- Pipeline stages (docs/how-ocrolus-works): Classify -> Capture -> Detect -> Analyze; processing types Classify, Instant, Complete; "when uncertainties arise, the system automatically routes documents to Ocrolus verifiers."
- Capture engine (docs/capture): "machine learning, computer vision, and micro-templates"; "each document is processed through the most suitable digitization tool to optimize both accuracy and efficiency"; when machine confidence is insufficient "for certain data fields" the document is escalated to human reviewers "followed by additional machine checks"; "Documents are divided into smaller tasks, allowing multiple human reviewers to work simultaneously"; "Each document verified contributes labeled data."
- Document status (reference/document-status): QUEUED, CLASSIFIED, PROCESSING ("automatically extracted"), GROOMING ("post-processing cleanup or refinement before final verification"), VERIFYING ("manual review"), VERIFICATION_COMPLETE, REJECTED, FAILED.
- Rejection reasons (docs/rejection-reasons): STATEMENT_UNRECONCILED ("sum of the transactions does not match the beginning and ending balances"), NO_PERIOD_SUMMARY, INCOMPLETE TRANSACTION DATA, NO_TRANSACTIONS, INSTANT NOT SUPPORTED ("Instant was unable to parse the document"), DOCUMENT IS UNREADABLE (illegible/password/corrupt), DOCUMENT TYPE NOT SUPPORTED, INVALID DOCUMENT, DOCUMENT DUPLICATE OF, UNEXPECTED PII.
- Classification (docs/classify, classify-first, uniqueness-value): page-level typing and collation into forms with UUIDs and page indexes; UNKNOWN for unrecognized/low-confidence pages; Uniqueness Values are "predefined field values" extracted at classification time (e.g., employer and employee name) used "to distinguish the form from other forms of the same type in the Book," and they decouple classification results from capture completion.
- Confidence (docs/confidence-score): per extracted field, 0 to 1, for Forms and Classification workflows; guidance: low -> reject Instant and use Complete; medium -> route to human review UI; high -> accept. No computation method disclosed.
- Validation (docs/validation-summary): field-level and document-level logic rules with passes_validation; described as "critical" for Instant beyond confidence; for Complete they act as alerts.
- Transactions (reference/transactions): bbox in pixels, page_idx, page_doc_pk, bank_account_pk, period_pk, txn_pk_duplicate_of, has_probable_transfers, tags; no per-transaction confidence field.
- Duplicates (docs/bank-statements): "a basic rule to spot duplicates" on date + description + amount within a Book.
- Turnaround (getting-started-bank-statements): "within a few minutes" but extended by "document quality, document source, and whether fraud or suspicious activity is detected."
- Detect (docs/detect, detect-signals, authenticity-score, authenticity-status): three layers (Resistant AI file/pixel forensics; Ocrolus ALGO content checks; Authenticity Status fusion, "highest-risk-wins"); signals listed in section 9; runs on "image-based and parsable PDFs"; score weighs "the context of what was tampered with and our confidence in the signal."
- Instant eligibility (docs/all-supported-documents): only bank statements carry the Instant asterisk in the fetched excerpt (press releases claim pay stubs and tax docs too; treat the docs as the narrower, current statement).
- Book upgrade (docs/book-upgrade): one-way Instant -> Complete; "eligible documents are requeued and reprocessed under the new Book class."
- Help center (help.ocrolus.com; all fetches 403; SNIPPET-ONLY): parsable PDF = "font, spacing, and alignment" extractable; image-based = flattened; "Instant Books are processed solely through automated means (AI-ML based models) without any human intervention."
- Security portal (security.ocrolus.com, fetched OK): hosted on AWS; subprocessors OpenAI, Snowflake, Google Cloud, AWS; RTO 4 hours; SOC 2/3, ISO 27001, PCI DSS.

## 5. Job-posting signals

- Staff Machine Learning Engineer (Built In, Remotive, Greenhouse 5545347004; fetched OK on Built In; Greenhouse listing since removed): "design, scale, and refine models that power core features — from document understanding and OCR to complex NLP and decision intelligence"; "lead model evaluation frameworks and continuous training strategies"; "A/B testing and monitoring"; PyTorch/TensorFlow; "Proven CV/OCR/NLP application experience at scale"; Docker, Kubernetes, Helm; AWS/GCP; ML infrastructure "to support multiple teams"; ~$200K base. Boilerplate: "state-of-the-art open- and closed-source AI models with a human-in-the-loop verification engine"; "nearly one million credit applications every month."
- Staff Software Engineer (Built In, fetched OK): Python and Golang; Flask; PostgreSQL/MySQL; distributed systems; Docker/Kubernetes; AWS/Azure/GCP; "1,500 employees."
- Senior Software Engineer, Backend (Golang) (Built In, fetched OK): "Design, implement, and maintain Microservices using Go, Python and/or Java"; Spring/Flask; Postgres/MySQL; "millions of transactions"; "online services and data pipelines."
- Application Support Engineer (Built In, fetched OK): SQL, Java/Python frameworks, JIRA, AWS; 24/7 rotational shifts.
- Data Verifier, Ocrolus East (Noida/Gurugram walk-ins; foundthejob fetched OK; Naukri 403; Greenhouse posting removed): "Review Documents of different formats and quality"; "Correct or Edit any incorrect details captured by the Ocrolus proprietary systems"; "Perform reconciliation of various amounts captured from reviewed documents to ensure high accuracy and identify discrepancies"; written test then technical/HR interview; typing test reported; 3-5 LPA; night shifts; volume-linked incentives.
- Absent from every posting found: LayoutLM/Donut/table-structure-recognition, annotation-tool engineering, active learning, "MLOps engineer" titles, and any named OCR vendor. The ML postings are generalist "CV/OCR/NLP at scale + K8s" roles, consistent with a small central ML platform team rather than a research group.
- Org shape (TheOrg): Software Development 29, Data Quality Assurance 27 (all titled "Data Verifier"), QA 22, Engineering 11, Mortgage Operations 15; leadership includes CEO Bobley, President Vikas Dua (operations background: McKinsey, Handy), COO/India head Ajay Shrivastava. The verifier org is flat in public data; no "SME/auditor/trainer" titles surfaced, though the patent describes an SME final-review role.

## 6. Talks, podcasts, interviews

- Alldus "AI in Action" E122 (2020), CTO Pieter Nel: agenda includes "Using the Data Flywheel concept"; no transcript available. Fetched description only.
- Fintech Blueprint (Lex Sokolin) with Sam Bobley: HITL + "reconciliation checks"; metadata-based fraud detection; ~6% suspicious; 4-hour turnaround. Fetched OK.
- Cohen Circle "5 Questions" (fetched OK): Google Books/CAPTCHA inspiration; "Our plan was to hire a bunch of people to do this verification"; Medicaid origin; pivot to SMB lending.
- Ocrolus blog "In conversation with Sam Bobley" (fetched OK): "blends artificial intelligence and crowdsourced data verification"; "we use the verified data to train our systems to become smarter, mitigating the need for human intervention."
- Wharton FinTech (Apple page fetched; Medium 403; LinkedIn mirror thin).
- Bank On It "nugget" page: fetch returned unrelated content (site apparently repurposed). Failed.
- FunderIntel and NY Startup podcast pages: video/audio only; no transcript. Failed for content.
- No conference talks by Ocrolus ML staff at document-AI venues (ICDAR, DAS), PyData, ODSC, re:Invent, or Google Next were found. No arXiv papers with an Ocrolus affiliation were found.

## 7. Verification-operations signals

- Workforce: "thousands of human-in-the-loop verifiers" (2025 blog); India GCC "over 1,250 employees" (Shrivastava profile); Florida QC facility (TechCrunch 2021); "SOC-compliant clean-room facilities" (platform page). DOCUMENTED.
- Task design: patent microtasks (section 2.2) and current docs ("divided into smaller tasks ... multiple human reviewers ... simultaneously"). DOCUMENTED. The ASSIST Software case study (fetched OK) says it built an Android micro-task app so "a distributed workforce" could "complete paid micro-tasks" for document validation, replacing "traditional offshore BPO operations," with "400,000 bank statement pages monthly" at that time — evidence that the crowd/microtask model was real product surface, not marketing.
- Worker QC: "algorithmic checks validating worker accuracy" (TechCrunch 2021); capture docs: human review is "followed by additional machine checks." DOCUMENTED. Consensus/double-entry between workers: not documented anywhere; PLAUSIBLE HYPOTHESIS only.
- Fraud ground truth: "daily random sampling of flagged documents to establish ground truth"; TPR "consistently hovers above 90%"; FP/FN tracked "through client reporting and systematic hit rate analysis segregated by institution details" (Ocrolus blog, fetched OK). DOCUMENTED.

## 8. Tech-stack signals

- GitHub org Ocrolus (fetched OK): forks of go-fitz (Go wrapper for MuPDF), sqlboiler (Go ORM generator), PyPDF2 (Python PDF), bazel-lib/rules_js (Bazel monorepo), material-ui, react-widget (TypeScript). Implies: PDF rendering/text-layer extraction in Go via MuPDF; Python PDF handling; Bazel-built monorepo; React front ends.
- Languages: Python + Go (+ some Java) from postings; Flask; Postgres/MySQL; Kubernetes/Helm; AWS primary, GCP secondary; Snowflake warehouse. Patent era: Celery + RabbitMQ/Redis, GPUs on AWS VPC.
- AI vendors: OpenAI (embeddings 2023; subprocessor), "Amazon" and "Google" subsystems (2023 PR), Gemini and Anthropic (2026 platform page), Resistant AI (Detect forensics), fine-tuned open-source models (2026). No StackShare/BuiltWith profile with ML detail; Slintel/RocketReach list only SaaS tools.
- Interview signals (InterviewQuery/Glassdoor snippets): system design, distributed systems, an "Elasticsearch-like" mock, SQL; no document-AI-specific questions surfaced.

## 9. Fraud/tamper signals exposed (from docs/detect-signals, fetched OK)

Resistant AI layer: anomalous_pdf_structure, suspicious_producer, overlapping_content, anomalous_font, digital_print, unusual_pdf_structure, content_tampering_suspected, image_of_known_document, document_from_online_generator, editing_software_detected, content_diff_between_versions (incremental-update diffing), has_only_images, has_piece_info, expected_pdf_structure, unmodified_per_metadata, screenshot.
Ocrolus ALGO layer: unreconciled_bank_statement_balance, invalid_bank_statement_txn_date, future_date, future_year; pay stub and W-2 arithmetic/IRS-rule checks (unreconciled_gross_pay, mismatched_pay_basis, missing Medicare/SS tax, wage base limits).
Fusion: Authenticity Score 0-100 (docs bands 0-55 LOW, 56-80 MEDIUM, 81-100 HIGH; the older blog/Argyle bands are 0-29/30-49/50-79/80+), Authenticity Status ternary or binary, reason codes with confidence levels, dashboard visualization of altered regions and (per 2022 PR) recovery of original values.

## 10. Observable behavior (independent)

- Capterra 2021-2022 reviews (fetched OK): "Chase, Bank of AM, Wells Fargo took no time, NOW it could take 30-1 hour"; "Credit Unions and other unknown banks could take time"; "The program often misses crucial information"; "Waiting times can be longer for more complicated bank statements."
- Sequence Inc 2016/2019: duplicates and omissions; manual-entry inconsistency.
- Ocrolus's own statements: 4-hour SLA-era turnaround (podcast), "few minutes" typical now, seconds for Instant.

## 11. Likely internal architecture (ASCII)

```
INTAKE                                                                    [DOCUMENTED]
  API / dashboard / widget / LOS connectors -> Book (case) -> Mixed Document -> pages
  md5 checksum; DOCUMENT DUPLICATE OF; unexpected-PII scan; QUEUED
        |
        v
PDF TRIAGE + PRE-DETECT CAPTURE                                           [STRONGLY INFERRED]
  parsable vs image-based decision (help center defines both)
  MuPDF (go-fitz) / PyPDF2-class parsing: text layer, fonts, producer,
  incremental-update history captured here for Detect; rasterize pages
        |
        v
PAGE CLASSIFICATION + COLLATION                                           [DOCUMENTED]
  ML page classifier (250+ mortgage types; 1,600+/2,100+ claimed overall)
  Uniqueness Values (key fields) split same-type forms, group pages -> forms
  UNKNOWN pages; "imperfect confidence" -> human classification specialists
  OpenAI text embeddings in the mix                                        [DOCUMENTED use; role INFERRED]
        | CLASSIFIED
        v
DIGITIZATION ROUTER  ("most suitable digitization tool")                  [DOCUMENTED existence]
  members: native text layer | Amazon OCR subsystem | Google OCR subsystem |
  proprietary DL OCR (Tesseract-lineage pre-processing DAG with caching)   [INFERRED members]
        | PROCESSING
        v
LOCALIZATION / FIELD LABELING                                             [MIXED]
  "proprietary ML and pattern recognition to localize each key element ...
   and label it with the proper context"                                   [DOCUMENTED]
  micro-templates: issuer/form-fragment region templates                   [term DOCUMENTED; semantics INFERRED]
  template knowledge base by financial institution (patent, 2017)          [DOCUMENTED, dated]
  zoning / line detection / word boxes -> spatial index                    [DOCUMENTED, dated]
        |
        v
TRANSACTION RECONSTRUCTION (bank statements)                              [MIXED]
  transaction = bounding box on page (bbox, page_idx) with date/desc/amount [DOCUMENTED]
  polarity assignment; account assignment on multi-account statements      [DOCUMENTED, patent]
  running-balance chaining; period summary (begin/end balance, dates)       [DOCUMENTED]
  model class (row-detector + column association vs token sequence
  labeling vs LLM-over-OCR)                                                 [HYPOTHESIS; see 12.6]
        | GROOMING
        v
ALGORITHMIC VALIDATION ("grooming")                                       [DOCUMENTED]
  reconciliation: end - begin == sum(txns) -> STATEMENT_UNRECONCILED /
    unreconciled_bank_statement_balance; date-in-period; future dates;
  duplicate rule (date+desc+amount); probable transfers; field/doc
  validation rules -> passes_validation; NO_PERIOD_SUMMARY etc.
        |
        v
CONFIDENCE -> UNIVERSAL CALIBRATION -> ROUTING                            [DOCUMENTED claims / INFERRED mechanics]
  field-level 0-1 confidence; calibrate heterogeneous model scores on one
  scale against HITL ground truth; pick model per task; "multiple AI agents
  check each other's work" for sub-threshold tasks; thresholds decide:
    Instant  -> return now (seconds) with confidence + validations
    Complete -> VERIFYING
        |                                   |
   high-confidence                     low-confidence fields / whole doc
        v                                   v
OUTPUT (Instant)                     HUMAN-IN-THE-LOOP MICROTASK ENGINE    [DOCUMENTED]
                                      task hierarchy: doc type/orientation,
                                      account metadata, txn boundaries,
                                      polarity, balances/reconciliation,
                                      add missing / remove false txns,
                                      SME page-by-page final review
                                      parallel verifiers (Noida, Gurugram,
                                      Florida clean rooms); algorithmic
                                      worker-accuracy checks; "additional
                                      machine checks" after human pass
        \___________________________________/
                        |
                        v
DETECT (on parsable and image PDFs)                                       [DOCUMENTED]
  L1 Resistant AI: metadata/producer, PDF structure, version diffs, fonts,
     overlays, screenshot, online generator, AI-generated, pixel forensics
  L2 Ocrolus ALGO: reconciliation, date validity, IRS/math rules, address
     validation, issuer fingerprinting (top banks / processors)
  L3 Authenticity Score/Status fusion (highest-risk-wins), reason codes,
     visualization + original-value recovery
        |
        v
ANALYZE                                                                   [DOCUMENTED]
  normalization; enriched-transaction tagging (~50 flags); transfers,
  recurring, NSF; ADB; income calcs; Snowflake warehouse
        |
        v
DATA FLYWHEEL                                                             [DOCUMENTED claims / INFERRED cadence]
  verified outputs -> labeled training data (240M+ pages);
  continuous training, evaluation frameworks, A/B tests, monitoring;
  daily sampled fraud ground truth; hit-rate tracking by institution
```

## 12. Component-by-component: evidence, alternatives, most likely

### 12.1 PDF triage and native-text handling
Evidence: help center distinguishes parsable vs image-based PDFs by whether "font, spacing, and alignment" can be extracted; Detect works on both; GitHub forks of go-fitz (MuPDF) and PyPDF2; Detect signals include has_only_images, digital_print, image_of_known_document, content_diff_between_versions.
Alternatives: (a) always rasterize and OCR everything, using the text layer only for forensics; (b) use the text layer as the primary token source when present and OCR only image pages; (c) run both and reconcile.
Most likely: (b)/(c) hybrid — STRONGLY INFERRED. The "most suitable digitization tool" sentence, the parsable/image distinction, and the fact that Instant is machine-only and fastest on clean e-statements all point to native-text extraction being one router branch, with OCR for image pages and a possible cross-check for suspected tampering (Detect's overlapping_content and content_diff_between_versions require text-layer parsing regardless).

### 12.2 Classification before extraction
Evidence: status sequence CLASSIFIED precedes PROCESSING; classify-first workflow; form-type routing; Uniqueness Values extracted at classification time; "Classifications with imperfect confidence are routed to ... specialists"; OpenAI embeddings added to handle "semi-structured and unstructured documents."
Alternatives: (a) a vision page classifier; (b) OCR-then-text classifier (embeddings/LLM); (c) both, with issuer identification (bank name/logo) as a sub-classifier feeding downstream templates.
Most likely: (c) — STRONGLY INFERRED. Uniqueness Values require field extraction at classification time (so OCR/text runs before or during classification), text embeddings are a documented input, and Detect's issuer-conditioned signals ("documents from this issuer typically follow a consistent structure") imply an issuer identity is known early. Classification is therefore a two-level result: form type + issuer/instance identity.

### 12.3 OCR
Evidence: patent (proprietary OCR, Tesseract lineage, preprocessing DAG, GPUs); 2023 PR ("subsystems from Amazon, Google and its own proprietary deep learning architectures"); subprocessors AWS and Google Cloud; FAQ ("OCR struggles to get much above 85% accuracy ... machine learning layer"); no vendor named in docs.
Alternatives: (a) single in-house OCR; (b) single cloud OCR; (c) multi-engine router/ensemble with in-house post-correction.
Most likely: (c) — STRONGLY INFERRED. The "most suitable digitization tool" language, two named cloud providers, and the survival of "proprietary deep learning architectures" only make sense as a router (per document or per page) plus a learned post-OCR layer. Which cloud services (Textract vs Document AI vs Vision) is unknown; the memo does not assert either.

### 12.4 Generalization across layouts
Evidence: "micro-templates" (docs); "template knowledge base by financial institution" (patent); "proprietary machine learning and pattern recognition to localize each key element ... and label it with the proper context"; FAQ claims format-agnostic extraction; 240M+ labeled pages; HITL "enables automation of tasks for which training data doesn't yet exist"; reviews show unknown banks slower; INSTANT NOT SUPPORTED exists; Instant limited to select types.
Alternatives: (a) per-bank templates only; (b) fully template-free learned layout models; (c) learned field/row localizers conditioned on issuer, backed by a library of issuer-specific micro-templates that are learned/curated from verified data, with HITL as the universal fallback that also mints training data.
Most likely: (c) — STRONGLY INFERRED. Pure templates cannot explain "cell phone image from a community bank in Kansas"; pure template-free models cannot explain why the company still names micro-templates in 2026 docs or why unknown banks take longer; the hybrid explains all observed behavior and the flywheel narrative. The practical mechanism for an unseen layout is: generic localization model attempts extraction; validation (reconciliation, period summary) decides whether the result is trustworthy; failures route to microtasks; verified output both ships to the customer and becomes a labeled example that, over enough volume, yields a micro-template/finetune for that issuer.

### 12.5 Micro-templates (what the term probably means)
Evidence: single documented term, no definition; patent's institution template base; Detect's per-issuer structure expectations; fingerprinting database "for top banks and payment processors."
Alternatives: (a) whole-page templates keyed by issuer; (b) region-level templates (header block, transaction table, period summary) reusable across issuers and page variants; (c) learned anchors (keywords/geometry) rather than fixed coordinates.
Most likely: (b)+(c) — PLAUSIBLE HYPOTHESIS. "Micro" strongly suggests sub-page fragments; anchor-based fragments are what survive the pagination and DPI variance of scans and phone photos.

### 12.6 Transaction reconstruction
Evidence: transaction = bbox + page_idx + date/description/amount + account + period (API); patent: zoning for tables, line detection, "transaction boundary identification and bounding box placement" as a human microtask, polarity as a separate step, running-balance chaining, "works most effectively on running balance statements"; Detect layout-anomaly category mentions "cloned tables, misaligned headers, spacing irregularities."
Alternatives: (a) explicit table-structure recognition (row/column detection) then cell OCR; (b) token-level sequence labeling of OCR words into date/description/amount/balance with row grouping by geometry; (c) LLM/VLM reading of the page or OCR text into JSON; (d) row-object detector (each transaction as a box) + column association + balance-chain solver.
Most likely: (d) with (b) inside the box for field parsing, and (c) as a 2023+ assist for unstructured/"semi-structured" cases — PLAUSIBLE HYPOTHESIS. The API's transaction-as-bbox model, the human "transaction boundary" microtask, and the balance-chain heuristics all match a row-object representation better than cell-grid tables (bank statements rarely have ruled grids; descriptions wrap). The 2023 embeddings note ("semi-structured and unstructured documents ... without human involvement") suggests LLM-class components entered for the long tail, not as the primary path.

### 12.7 Reconciliation
Evidence: STATEMENT_UNRECONCILED rejection; unreconciled_bank_statement_balance fraud signal; NO_PERIOD_SUMMARY; patent claims 6-8 and text using balances "to autonomously identify potential OCR conversion errors" and to rank likely-erroneous transactions; verifier duty "perform reconciliation of various amounts captured"; Bobley: "human-in-the-loop validation, reconciliation checks."
Alternatives: gate only; signal only; correction loop.
Most likely: all three at different stages — DOCUMENTED. Inside extraction/grooming it is an error detector that focuses machine and human attention (correction loop); at output it is a hard gate for the document (rejection) when unresolved; in Detect it is a fraud signal when the document is otherwise well-formed.

### 12.8 Confidence and human review integration
Evidence: field-level 0-1 confidence; classification confidence; "when machine confidence levels prove insufficient for certain data fields ... escalates ... followed by additional machine checks"; Universal Calibration statements; validation summary as a second axis; SME final review in patent; "algorithmic checks validating worker accuracy."
Alternatives: (a) document-level threshold routing; (b) field-level routing with document-level fallback; (c) sampling-based QA; (d) calibrated meta-model over heterogeneous model confidences (Intuit-style).
Most likely: (b)+(d) with (c) used for fraud ground truth — DOCUMENTED for (b), STRONGLY INFERRED for (d), DOCUMENTED for (c) in Detect. Human corrections feed: the delivered result, the labeled training set, the calibration set for Universal Calibration, and worker-accuracy scoring.

### 12.9 Fraud internals
Evidence: section 9 signals; Resistant AI partnership; ALGO checks; fingerprinting for top banks; address validation; original-value recovery; daily sampling; TPR>90%.
Alternatives: build in-house forensics vs partner.
Most likely: partner for file/pixel forensics (DOCUMENTED), in-house for content/arithmetic/issuer-fingerprint checks (DOCUMENTED), fusion in-house (DOCUMENTED). Cross-document consistency inside a Book (duplicate documents by md5/name, duplicate transactions across statements, transfers) is DOCUMENTED; cross-applicant consistency (same background/template reused across applications) is PLAUSIBLE HYPOTHESIS only (the platform page mentions "pattern recognition for repeat fraud across applications" without detail).

### 12.10 The flywheel and MLOps
Evidence: 240M+ pages; "each document verified contributes labeled data"; ML posting language ("continuous training strategies", "model evaluation frameworks", "A/B testing"); Alldus "Data Flywheel"; Universal Calibration uses HITL data.
Alternatives: periodic offline retraining vs continuous/online.
Most likely: scheduled retraining per model with continuous accumulation of labels and calibration data; A/B deployment via Kubernetes — STRONGLY INFERRED. No evidence of active-learning selection beyond confidence routing itself (which is a form of it).

## 13. The seven answers

1. Generalization across thousands of layouts: a mix. Learned localization/labeling models (documented) sit on top of an issuer-aware library of micro-templates (documented term, semantics inferred), with human microtask verification as the universal fallback that mints labels (documented). Unseen layouts are handled first by the generic path, judged by reconciliation and validation rules, and repaired by humans when confidence or validation fails; that repair becomes training data. The observable "big banks instant, credit unions slow" gradient is the signature of this design.

2. Classification before extraction: yes. Page-level form-type classification with collation into forms, plus instance-level Uniqueness Values, runs first (status CLASSIFIED precedes PROCESSING); low-confidence pages are UNKNOWN and are human-reviewed; issuer identity is very likely resolved at this stage (inferred from Detect's issuer-conditioned signals).

3. Native PDF vs scan: both are accepted; the platform distinguishes parsable from image-based PDFs and routes "each document through the most suitable digitization tool." Text-layer extraction (MuPDF/PyPDF2 lineage) is one branch; OCR (Amazon/Google subsystems and proprietary DL) is the other; the text layer and PDF structure are also parsed for forensics regardless of route. Whether native text is trusted as primary tokens or cross-checked against OCR is not documented; hybrid is the most likely.

4. Transaction reconstruction on unfamiliar layouts: transactions are row objects with bounding boxes and page indexes; polarity and account assignment are separate decisions; running-balance and period-balance arithmetic are used to chain rows and detect misreads. The underlying model class is not disclosed; the evidence favors a row-object detector with in-row field parsing and balance-chain solving, with LLM/embedding assistance for semi-structured cases since 2023, over a classic table-grid recognizer.

5. Reconciliation: all three roles. Error-correction loop inside extraction (patent), hard gate at output (STATEMENT_UNRECONCILED, NO_PERIOD_SUMMARY), and fraud signal in Detect (unreconciled_bank_statement_balance). It also directs human attention (check balances before transactions; rank likely-wrong rows).

6. Confidence and human review: field-level confidence (0-1) on fields and classification, complemented by rule-based validations; routing is per-field with whole-document fallback; Universal Calibration normalizes confidences across heterogeneous models using human-verified data and picks a model per task; sub-threshold tasks go to multi-agent cross-checking and then to human microtasks; a final SME page review exists in the patent-era design; worker accuracy is algorithmically checked. Human output feeds the delivered result, the training corpus, the calibration set, and fraud ground truth (daily sampling).

7. Fraud/tamper internals: file/pixel forensics outsourced to Resistant AI (metadata/producer anomalies, PDF structure, incremental-update diffs, fonts, overlays, screenshots, online generators, AI-generated artifacts); content-level checks in-house (arithmetic reconciliation, date validity, IRS rules, address validation, issuer fingerprinting for top banks, duplicate/transfer detection within a Book); fusion into Authenticity Score/Status with highest-risk-wins and reason codes; visual highlighting and original-value recovery. Cross-document consistency is documented within a Book; cross-applicant pattern detection is claimed without detail.

## 14. What this implies for a layout-agnostic bank-statement engine (brief)

- Treat classification as two outputs (form type, issuer/instance) and make issuer identity optional so unknown issuers still flow.
- Model transactions as row objects with geometry and provenance (bbox, page) rather than cell grids; keep polarity and account assignment as explicit, separately validated decisions.
- Make reconciliation a three-role primitive: in-loop error localization, output gate, and fraud signal; check period summaries before rows.
- Keep confidence at field level, calibrated against verified data, and pair it with rule validations; route fields, not documents, when possible.
- Design the human/agent fallback so that every correction is a labeled example with geometry, and let issuer-specific "micro-templates" be an output of that data rather than an input written by hand.
- Parse the PDF text layer and structure even when you OCR, because tamper evidence lives there.

## 15. Sources (URL — what it contained — fetch status)

Patents
- https://patents.google.com/patent/US11087409B1/en — Ocrolus granted patent; claims map and description details (Tesseract, templates, DAG, AWS/Celery, microtasks, reconciliation) — fetched OK (two prompts).
- https://patents.google.com/patent/US11087409B2/en — 404 (no B2). Failed.
- https://patents.google.com/patent/US11087409/en — resolved to B1 page; description summary — fetched OK.
- https://patents.google.com/patent/US20210366055A1/en — continuation; abstract, claims, figures, status Abandoned — fetched OK.
- https://patents.google.com/xhr/query?url=assignee%3DOcrolus... — one hit (US20210366055A1) — fetched OK.
- https://patents.google.com/xhr/query?url=q%3Docrolus... — one relevant hit — fetched OK.
- https://patents.google.com/xhr/query?url=inventor%3D%22Sam+Bobley%22... — one hit, status ACTIVE — fetched OK.
- https://patents.google.com/xhr/query?url=inventor%3D%22Pieter+Nel%22... — no Ocrolus hits — fetched OK.
- https://patents.google.com/xhr/query?url=assignee%3D%22Ocrolus%2C+Inc.%22... — unrelated results — fetched OK (uninformative).
- https://patents.justia.com/assignee/ocrolus-llc — 403. Failed (snippet: single 2021 patent, Bobley and Yang).
- https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12354319 — image-only PDF; unreadable — Failed (Google Patents page used: Orbit Healthcare, not Ocrolus).
- https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12164657 — image-only PDF — Failed (Google Patents page used: LendingClub Bank, not Ocrolus).
- https://patents.google.com/patent/US12164657B2/en — LendingClub fraudulent-document patent (comparator) — fetched OK.
- https://patents.google.com/patent/US11816430B2/en — Intuit confidence meta-model patent (comparator) — fetched OK.
- https://patents.google.com/patent/US11195006B2/en — IBM/Gusto multimodal features (not Ocrolus) — fetched OK.
- https://patents.google.com/patent/US8249399B2/en — IBM OCR verification (not Ocrolus) — fetched OK.

Ocrolus documentation
- https://docs.ocrolus.com/docs/how-ocrolus-works and .md — stages, processing types, verifier routing — fetched OK.
- https://docs.ocrolus.com/docs/capture and .md — micro-templates, "most suitable digitization tool", HITL microtasks, labeled data — fetched OK.
- https://docs.ocrolus.com/docs/classify.md — classification/collation — fetched OK.
- https://docs.ocrolus.com/docs/classify-first.md — classification precedes capture; UNKNOWN pages — fetched OK.
- https://docs.ocrolus.com/docs/instant-classify-with-uvcf.md — Instant Classify machine-only — fetched OK.
- https://docs.ocrolus.com/docs/uniqueness-value.md — Uniqueness Values — fetched OK.
- https://docs.ocrolus.com/docs/confidence-score — field-level 0-1 confidence; routing guidance — fetched OK.
- https://docs.ocrolus.com/docs/validation-summary.md — rule validations — fetched OK.
- https://docs.ocrolus.com/docs/normalization.md — normalization rules — fetched OK.
- https://docs.ocrolus.com/docs/rejection-reasons — rejection taxonomy — fetched OK.
- https://docs.ocrolus.com/reference/document-status.md — status sequence incl. GROOMING — fetched OK.
- https://docs.ocrolus.com/reference/transactions.md — transaction fields (bbox, page_idx, duplicate_of, probable transfers) — fetched OK.
- https://docs.ocrolus.com/reference/transaction-definition (and .md) — 404. Failed (snippet gave bbox definition).
- https://docs.ocrolus.com/docs/bank-statements.md — regions, duplicate rule — fetched OK.
- https://docs.ocrolus.com/docs/getting-started-bank-statements.md — workflow, turnaround caveats, Detect phase — fetched OK.
- https://docs.ocrolus.com/docs/accounts-section.md — account/period structure — fetched OK.
- https://docs.ocrolus.com/docs/transactions-section.md — UI fields, capture details panel — fetched OK.
- https://docs.ocrolus.com/docs/cash-flow-analytics.md — endpoints; no model detail — fetched OK.
- https://docs.ocrolus.com/docs/all-supported-documents — Instant asterisk on bank statements — fetched OK.
- https://docs.ocrolus.com/docs/book-upgrade.md — one-way upgrade, requeue — fetched OK.
- https://docs.ocrolus.com/docs/definitions.md — Book/Document/Form definitions — fetched OK.
- https://docs.ocrolus.com/docs/document.md — md5, status, rejection_reason — fetched OK.
- https://docs.ocrolus.com/docs/detect — three layers, categories, outputs — fetched OK.
- https://docs.ocrolus.com/docs/detect-signals — signal list — fetched OK.
- https://docs.ocrolus.com/docs/authenticity-score — score bands, weighting statement — fetched OK.
- https://docs.ocrolus.com/docs/authenticity-status.md — ternary/binary modes — fetched OK.
- https://docs.ocrolus.com/docs/processing-types — 404. Failed.
- https://docs.ocrolus.com/docs/instant.md — 404. Failed.
- https://docs.ocrolus.com/llms.txt — docs index — fetched OK.
- https://help.ocrolus.com/hc/en-us/articles/14992040193940-What-is-an-image-based-PDF — 403. Failed (snippet used).
- https://help.ocrolus.com/hc/en-us/articles/19405464241300-Instant-Overview — 403. Failed (snippet used: "AI-ML based models without any human intervention").
- https://security.ocrolus.com/ and /subprocessors — AWS hosting; subprocessors OpenAI, Snowflake, Google Cloud, AWS; certifications — fetched OK.
- https://docs.argyle.com/integrations/ocr/ocrolus — partner view: field confidences 0-1, authenticity bands, webhooks, rejection reasons — fetched OK.

Ocrolus site, blog, press
- https://www.ocrolus.com/platform/ — Universal Calibration, agentic cross-checking, model partners, clean rooms — fetched OK.
- https://www.ocrolus.com/faq/ — OCR ~85% claim, ML layer, tough documents, formats — fetched OK.
- https://www.ocrolus.com/blog/keep-up-with-advances-in-financial-ai/ — Universal Calibration definition — fetched OK.
- https://www.ocrolus.com/blog/the-role-humans-with-ai-document-automation/ — confidence routing to specialists; 250+ mortgage types; feedback loop — fetched OK.
- https://www.ocrolus.com/blog/training-data-for-ai-complete-document-automation/ — 240M pages; labels as byproduct — fetched OK.
- https://www.ocrolus.com/blog/automated-document-classification-use-cases-for-lenders/ — classification steps — fetched OK.
- https://www.ocrolus.com/blog/data-integrity-in-the-digital-age/ — "localize each key element and label it with the proper context"; trained on thousands of institutions — fetched OK.
- https://www.ocrolus.com/blog/revolutionizing-fraud-detection-with-automated-document-processing/ — editing-software detection, field-level alteration, address validation, fingerprinting for major banks, daily sampling, TPR>90% — fetched OK.
- https://www.ocrolus.com/blog/how-ocrolus-detect-uncovers-fraud-and-mitigates-losses/ — context weighting; planned fingerprinting — fetched OK.
- https://www.ocrolus.com/blog/ocrolus-detect-authenticity-score/ — score bands and inputs — fetched OK.
- https://www.ocrolus.com/blog/preventing-loan-fraud-10-important-visuals-on-file-tampering-detection/ — FTD statistics only — fetched OK.
- https://www.ocrolus.com/blog/ocrolus-vs-manual-document-review/ — three-step pipeline — fetched OK.
- https://www.ocrolus.com/blog/in-conversation-with-sam-bobley-co-founder-ceo-ocrolus/ — crowdsourced verification; verified data trains systems — fetched OK.
- https://www.ocrolus.com/blog/ocrolus-2024-wrapped-ai-document-automation-growth/ — milestones; no metrics — fetched OK.
- https://www.ocrolus.com/blog/author/vikas-dua/ — no article list rendered — fetched OK (uninformative).
- https://ocrolus.com/blog/ocrolus-adds-senior-technical-leadership — redirected to About page; no hires listed — fetched OK (uninformative).
- https://ocrolus.com/press/ocrolus-launches-comprehensive-fraud-detection-solution-for-lenders/ — redirected to newsroom; no content — Failed for content.
- https://www.prnewswire.com/news-releases/ocrolus-launches-comprehensive-fraud-detection-solution-for-lenders-301621362.html — Detect launch details — fetched OK.
- https://www.prnewswire.com/news-releases/ocrolus-adds-openai-gpt-embeddings-for-deeper-automation-in-financial-document-analysis-301817528.html — embeddings; Amazon/Google subsystems; Haehn quote — fetched OK.
- https://www.prnewswire.com/news-releases/ocrolus-launches-new-cost-effective-instant-solution-for-analyzing-financial-documents-301933096.html — Instant/Complete — fetched OK.
- https://www.prnewswire.com/news-releases/ocrolus-accelerates-automated-conditioning-for-mortgage-lenders-with-full-lifecycle-management-302715996.html — "deterministic by design" — fetched OK.
- https://www.prnewswire.com/news-releases/ocrolus-secures-4m-in-series-a-funding... (via AlleyWatch) — see below.
- https://www.abnewswire.com/pressreleases/perfectaudit-powered-by-ocrolus-... — 2016 PerfectAudit features; AWS storage — fetched OK.
- http://www.sbwire.com/press-releases/amp/michael-yang-chairman-of-technology-... — certificate expired. Failed (snippet used).

Press, podcasts, interviews
- https://techcrunch.com/2021/09/23/ocrolus-lands-80m-... — analysts/QC specialists; algorithmic worker checks; Florida facility — fetched OK.
- https://www.alleywatch.com/2018/04/ocrolus-raises-4m-... — crowdsourced micro-validation — fetched OK.
- https://lex.substack.com/p/podcast-using-ai-to-digitize-financial-b43 — reconciliation checks; metadata fraud; 6%; 4-hour — fetched OK.
- https://cohencircle.com/insight/5-questions-with-fintech-founders-ocrolus/ — Google Books/CAPTCHA origin; hiring verifiers — fetched OK.
- https://www.laconiacapitalgroup.com/blog/ocrolus-founder-sam-bobley-... — pointer only — fetched OK (thin).
- https://fintechleaders.substack.com/p/sam-bobley-co-founder-and-ceo-of — HITL boilerplate — fetched OK (thin).
- https://podcasts.apple.com/us/podcast/sam-bobley-co-founder-and-ceo-of-ocrolus/... — episode description; ~1,000 employees 2021 — fetched OK.
- https://medium.com/wharton-fintech/sam-bobley-... — 403. Failed.
- https://www.linkedin.com/pulse/sam-bobley-co-founder-ceo-ocrolus-transforming-documents-armaza — thin mirror — fetched OK (little content).
- https://podcasts.apple.com/ie/podcast/e122-pieter-nel-cto-at-ocrolus/... and https://alldus.com/podcast/ai-in-action-e122-pieter-nel-cto-at-ocrolus/ — description incl. "Data Flywheel" — fetched OK (no transcript).
- https://bankonitpodcast.com/nugget-of-the-week-... — page now unrelated content. Failed.
- https://www.funderintel.com/post/a-conversation-with-sam-bobley-ceo-of-ocrolus — video only. Failed for content.
- https://www.inman.com/2023/05/09/ocrolus-taps-openai-... — 403. Failed (snippets used).
- https://www.crowdfundinsider.com/2023/05/206930-... — 403. Failed.
- https://www.themortgagenote.org/ocrolus-adds-gpt-to-its-ai-powered-tech/ — 403. Failed.
- https://nationalmortgageprofessional.com/news/40-years-later-ai-finally-finds-housing — 403. Failed.
- https://www.cardrates.com/news/ocrolus-uses-ai-to-automate-document-capture/ — 403. Failed.
- https://www.pymnts.com/loans/2023/ocrolus-debuts-ai-powered-document-analyzer-instant/ — Instant coverage — fetched OK.
- https://www.housingwire.com/articles/financial-document-automation-platform-ocrolus-raises-80m/ — 403. Failed.
- https://www.fintechfutures.com/wealthtech/financial-document-processing-platform-ocrolus-secures-80m-series-c-round — 403. Failed.
- https://www.intelligentdocumentprocessing.com/idp-provider-ocrolus-introduces-a-new-machine-only-offering/ — certificate expired. Failed.
- https://www.thekeyexecutives.com/2026/08/27/shift-technology-hires-former-ocrolus-cto-zach-haehn-... — CTO departure — search result (not fetched).

Reviews and observers
- https://www.sequenceinc.com/fraudfiles/2016/04/ocrolus-perfect-audit-review-... — overseas manual entry; balance-sync guarantee; duplicates/missing — fetched OK.
- https://www.sequenceinc.com/fraudfiles/2019/08/ocrolus-software-review/ (three variants) — returned blog index. Failed (snippet used).
- https://www.capterra.com/p/232462/Ocrolus/reviews/ — turnaround by bank; misses — fetched OK.
- https://www.glassdoor.com/Reviews/Employee-Review-Ocrolus-E2857732-RVW51040250.htm — 403. Failed.
- https://medium.com/@juanpablo.lopez.95.27/daletguard-vs-ocrolus-... — 403. Failed (competitor piece; would have been treated as hostile anyway).
- https://assist-software.net/project/ocrolus — vendor case study: Android micro-task app, admin site, 400k pages/month — fetched OK.

Jobs and org
- https://builtin.com/job/staff-machine-learning-engineer/7938221 — Staff ML Engineer JD — fetched OK.
- https://remotive.com/remote/jobs/software-dev/staff-machine-learning-engineer-1687966 — 410 Gone. Failed (snippet used).
- https://job-boards.greenhouse.io/ocrolusinc/jobs/5545347004 — listing removed; board shows 14 openings — fetched OK (uninformative).
- https://builtin.com/job/staff-software-engineer/7989932 — Staff SWE JD — fetched OK.
- https://builtin.com/job/senior-software-engineer-backend/7626682 — Go backend JD — fetched OK.
- https://builtin.com/job/application-support-engineer/8012403 — support JD — fetched OK.
- https://startup.jobs/senior-machine-learning-engineer-at-ocrolus — 403. Failed.
- https://builtin.com/job/data-verifier/2559331 — 404. Failed.
- https://job-boards.greenhouse.io/ocrolusinc/jobs/4323118004 — removed. Failed.
- https://foundthejob.com/ocrulus-east-walk-in-interview/ — Data Verifier duties (correct/edit captured data; reconciliation) — fetched OK.
- https://www.naukri.com/job-listings-data-verifier-ocrolus-noida-... — 403. Failed.
- https://theorg.com/org/ocrolus, /teams/engineering-and-technical-roles, /teams/data-quality-assurance — leadership, team sizes, verifier titles — fetched OK.
- https://www.zippia.com/ocrolus-careers-1413766/executives/ — bot wall. Failed.
- https://www.interviewquery.com/interview-guides/ocrolus-data-scientist — 429 (twice). Failed.
- https://in.indeed.com/cmp/Ocrolus-East-Pvt-Ltd/interviews — 403. Failed.
- https://github.com/Ocrolus — public repos (go-fitz, sqlboiler, PyPDF2, Bazel, React widget) — fetched OK.

Search-only leads (not fetched; used as pointers): ReleaseWire Michael Yang 2016; Inman Sept 2023 mortgage offering; HousingWire Inspect; LinkedIn posts on Ajay Shrivastava appointment; Crunchbase profiles; Everest/Gartner IDP reports (no Ocrolus placement confirmed).
