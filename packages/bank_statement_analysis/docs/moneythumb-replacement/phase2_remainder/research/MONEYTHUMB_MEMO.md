<!-- Companion to PHASE2_REMAINDER_PLAN.md — research/audit memo produced 2026-09-03 by an independent Fable 5.1 agent under Ocean's direction; read-only investigation; verbatim except for privacy scrubbing of archive filename fragments. -->

# MoneyThumb — external research memo

Prepared 2026-09-03 for the bank-statement intelligence engine team (comparison baseline: MoneyThumb outputs; design target: a layout-agnostic reconstruction path where a deterministic financial validator is the only authority).

Evidence discipline used throughout:
- **DOCUMENTED** = quoted from a fetched primary page (MoneyThumb site, docs.moneythumb.com, MoneyThumb Javadoc) or a fetched third-party page, with URL.
- **THIRD-PARTY / UNVERIFIED** = competitor pages, review sites, forum snippets. Reported as claims, not facts.
- **STRONGLY INFERRED** = follows from several documented facts taken together; not stated by MoneyThumb.
- **PLAUSIBLE HYPOTHESIS** = consistent with the evidence but not established; could be wrong.

Unless stated otherwise, "MoneyThumb" below means the lender product line (PDF Insights / PDF Insights with Thumbprint / Thumbprint / PDF Convert Server / Insights API v1.5). The accountant converters (2Convert line: 2qbo/2ofx/2csv Convert Pro, pdf2qbo, MoneyThumb Online) share the same parsing engine and are cited where they expose engine behaviour that the lender docs do not.

---

## 0. SOURCES

Fetch status is as of 2026-09-03. "Search-snippet only" means the page itself could not be fetched and only a search engine excerpt was available.

### MoneyThumb primary pages (fetched OK)

| # | URL | What it contained |
|---|-----|-------------------|
| S1 | https://www.moneythumb.com/ | Product list; "The only OCR/IDR technology built for bank statements"; "99% Accuracy"; "Machine Learning — Corrects and flags questionable transactions with ease"; "works with most of the banks around the world". |
| S2 | https://www.moneythumb.com/pdf-insights/ | Scorecard in "under 5 seconds"; "Recognizes 95% of U.S. bank statements, through intelligent document recognition algorithms"; "The Power to Analyze Statements for 99% of U.S. Banks"; scanned/faxed/image support; template-free claim; metrics list; Thumbprint "flags missing pages through arithmetic checks". |
| S3 | https://www.moneythumb.com/thumbprint/ | Two verification methods + reconciliation; score 1–1000; "database of thousands of financial institutions and hundreds of data points". |
| S4 | https://www.moneythumb.com/pricing/ | Consumption model; "Starting at $599.95 per year"; conversion = one account-month; tiers PDF Server / PDF Insights / Enterprise; no charge for repeat uploads or <5-transaction statements; 12-month expiry. |
| S5 | https://www.moneythumb.com/frequently-asked-questions/ | PDF+ definition; 300-dpi "100% accuracy" claim; per-account reconciliation and conversion counting; unreconciled handling ("highlight … exactly which values are in question"); FID workaround; "thousands of banks". |
| S6 | https://www.moneythumb.com/about-pdf-plus/ | PDF+ pipeline (OCR → reconcile → context re-recognition → manual flags); dust/comma and "5 looked like S" examples; supports scanned, image, searchable, encrypted PDFs; Pro+/Express "Currently Windows only". |
| S7 | https://www.moneythumb.com/blog/moneythumb-welcomes-ocr-to-the-family/ | 2015-09-24 OCR launch; proprietary; no third-party engine named. |
| S8 | https://www.moneythumb.com/2qbo-convert-pro-help/ | Desktop engine knobs and messages: balance column ignored, Preview Mode column memory, "Switch signs of amounts", combine multi-line descriptions, US/EU dates, "??" column, Advanced PDF options for section text, diagnostic "Found 100 lines with a date…", Spacing Factor, page range, year override, multiple statements. |
| S9 | https://www.moneythumb.com/proven-banks/ | "verified" banks list; "we haven't met one that doesn't"; "notify us immediately and we will work toward a solution!". |
| S10 | https://www.moneythumb.com/identify-fraudulent-bank-statements/ | Thumbprint mechanics: "hundreds of data points", font/position "1 ten-thousands of an inch", arithmetic test, "thumbprints for thousands of banks … millions of processed PDF bank statements". |
| S11 | https://www.moneythumb.com/blog/bank-statement-pdf-validation-guide-how-to-stop-loan-fraud-before-it-happens/ | 2026-07-14; forensic checklist (fonts, PDF version, object hierarchy, metadata history, incremental edits, producer); synthetic-document signs; "AI-assisted PDF analysis". |
| S12 | https://www.moneythumb.com/blog/fraud-detection-using-machine-learning-what-lenders-need-to-know/ | 2026-08-04; generic ML discussion; no specifics about MoneyThumb's own models. |
| S13 | https://www.moneythumb.com/privacy-policy/ | Retention "as long as reasonably necessary"; processors AWS, SendGrid, WordPress, WooCommerce, Google Analytics, osTicket; no statement on training use or document deletion. |
| S14 | https://www.moneythumb.com/lender/ | Scorecard metrics (ADB, NSF, deposits, true revenue, MCA); "95% reconciliation rate" vs competitors' 80%; "smart algorithms" rather than AI; eConvert (email intake). |
| S15 | https://www.moneythumb.com/moneythumb-online-pdf-insights/ | "proprietary algorithms to identify bank or bank statement formats"; "correctly processes over 99% of U.S. bank statements"; "automatically recognizes multiple monthly statements in a PDF and multiple accounts in each statement"; "totals the transactions and reconciles them against the starting and ending balance"; side-by-side review. |
| S16 | https://www.moneythumb.com/mca/ | Non-true-revenue removal; "non-reconciled summaries" as a risk signal; "3-5% of applications are fraudulent"; 50+ summary fields. |
| S17 | https://www.moneythumb.com/about-us/ | Timeline: 2015 rebrand (founder Ralph Mayer), 2017 PDF Insights, 2018 MoneyThumb Online, 2020 Thumbprint + AWS migration, 2021 SOC 2; 10,000 customers (2018), 25,000 (2021). |
| S18 | https://www.moneythumb.com/news/ | Press: Thumbprint patent 2025-04-23; deBanked fraud survey 2025-09-16; Onyx IQ integration. |
| S19 | https://www.moneythumb.com/blog/leading-fintech-moneythumb-acquired-by-iron-creek/ | 2024-08 acquisition by Iron Creek Partners (with Main Street Capital); CEO Ryan Campbell; Encinitas, CA; "100% year-over-year annual growth". |
| S20 | https://www.moneythumb.com/blog/moneythumbs-thumbprint-secures-patent-for-fraud-detection-technology-in-document-authentication/ | Patent (number not given): "structural, metadata, and content-based patterns within PDF files"; "reviewed more than 10M statements and identified over 500,000 fraudulent or altered documents". |
| S21 | https://www.moneythumb.com/blog/moneythumb-and-debanked-release-survey-findings-on-fraud-trends-among-small-business-funders/ | 2025-09 survey stats; "88% of funders are still reviewing documents manually". |
| S22 | https://www.moneythumb.com/blog/the-hidden-cost-of-fraud-detection-software-every-business-should-know/ | 2026-09-01; false-positive cost arithmetic; Thumbprint compares "columns, date formats, text fonts, positioning, and PDF creation information". |
| S23 | https://www.moneythumb.com/blog/lenders-make-instant-credit-decisions-using-thumbprint-from-moneythumb/ | 2021-12-28; "1-1000 genuineness score"; "Thumbprint database based on millions of documents". |
| S24 | https://www.moneythumb.com/blog/bank-statement-conversion-financial-lenders/ | 2021-06-11; IDR/template-free quote; "over 99% of U.S. statements". |
| S25 | https://www.moneythumb.com/blog/10-best-bank-statement-extraction-software-for-faster-data-extraction/ | 2026-06-23; MoneyThumb's own framing vs Ocrolus. |
| S26 | https://www.moneythumb.com/security/ | SOC 2 Type 2; five trust criteria; no encryption/retention specifics. |
| S27 | https://www.moneythumb.com/blog/moneythumb-is-soc-2-compliant-and-how-that-benefits-our-customers/ | 2022-01-15; third-party audit; "SaaS company that store customer data in the cloud". |
| S28 | https://www.moneythumb.com/pdf-types/ | Four PDF types (text, image/scanned, searchable, encrypted) and which product handles each; OCR-layer error example "so" vs "50". |
| S29 | https://www.moneythumb.com/what-scans-work-best-with-pdf/ | 300 dpi, no skew, 50% brightness; poor scans → manual fixing "can be too much". |
| S30 | https://www.moneythumb.com/sophisticated-ocr-accuracy/ | "99% Accuracy"; "Machine Learning"; no mechanism detail. |
| S31 | https://www.moneythumb.com/shop/pdf-convert-server-thumbprint/ | PDF Convert Server: Java API + CLI; "installed on customer servers" or hosted; includes PDF+; "$0.60 per statement conversion". |
| S32 | https://www.moneythumb.com/api/pdfserver-v0/ and https://www.moneythumb.com/swagger/pdfserver/ and https://www.moneythumb.com/swagger/pdfinsights/ | Marketing shells; JSON skeleton `{statement_summmaries, appinfo, scorecard, transactions}` (typo in "summmaries" is theirs); the pdfserver-v0 page carries the phrase "human reviewed for accuracy" with no context. |
| S33 | https://www.moneythumb.com/help-center/ | Help index (converter tutorials only; no PDF Insights articles). |
| S34 | https://www.moneythumb.com/pdf2qbo-convert-help/ | Entry-level converter: no reconciliation feature. |
| S35 | https://www.moneythumb.com/2ofx-convert-pro-help/ | "??" markers in CSV, yellow highlight in Preview; balance column "should be blank (to ignore it)". |
| S36 | https://www.moneythumb.com/blog/why-accountants-love-moneythumbs-2qbo-convert-pro/ | 2019-03-29; "reconcile feature that will try to reconcile the credits/debits found with the starting and ending balances printed on the bank statement". |
| S37 | https://www.moneythumb.com/shop/pdf-insights-thumbprint/ | Password-protected content area; only headline copy visible. |

### docs.moneythumb.com (fetched OK)

| # | URL | What it contained |
|---|-----|-------------------|
| D1 | https://docs.moneythumb.com/ and https://docs.moneythumb.com/welcome/0_welcome | Overview; "a single API call"; 75+ categories; nav links to guides. |
| D2 | https://docs.moneythumb.com/welcome/core-concepts | Five stages (Intake, Conversion, Tagging, Scorecard, Output); reconciliation formula; 75+ categories incl. "Casino Payments"; "Image-based PDFs are 'routed through OCR'". |
| D3 | https://docs.moneythumb.com/welcome/thumbprint | Score bands −1…1000; "signals that survive metadata scrubbing"; new-template false positives; Known Limitations. |
| D4 | https://docs.moneythumb.com/api/pdf-insights/0_overview | Three products; API additive-change policy. |
| D5 | https://docs.moneythumb.com/api/pdf-insights/1_quickstart | Endpoints; headers (`MT-Product`); async OCR via webhook; Thumbprint-only does not OCR. |
| D6 | https://docs.moneythumb.com/api/pdf-insights/3_authentication | Session token expires after 24 hours; product header values. |
| D7 | https://docs.moneythumb.com/pdf-insights/api-reference | Endpoint list (23 endpoints). |
| D8 | https://docs.moneythumb.com/pdf-insights/api-reference/other/uploadpdfs | Full request/response schema (the key source for §8). |
| D9 | https://docs.moneythumb.com/pdf-insights/api-reference/other/makecsv.md | Single-document endpoint; `alloweddiff`, `doocrfile`, `neverocr`, `asyncocr`, `spacingfactor`, `combinelines`, `accountseqno`, `monthseqno`; `file_status` fields incl. `endBalanceCalc`, `endBalancePDF`, `donegate`. |
| D10 | https://docs.moneythumb.com/api/pdf-insights/api-reference/other/transactions.md | Transaction fields (`possible`, `trueval`, `balance`, `tags`). |
| D11 | https://docs.moneythumb.com/api/pdf-insights/api-reference/other/updatesummary.md | User may overwrite `startbalance`, `debits`, `credits`, `endbalance`. |
| D12 | https://docs.moneythumb.com/api/pdf-insights/api-reference/other/getresults.md | Definitions of `ocr`, `numTypos`, `suspectCount`, `previewRequired`, `reconciled`, `balancesValid`, `likelyMissingTransactions`, `requiresRerunWithOCR`; "Any changes made to the data won't be reflected in the results data". |
| D13 | https://docs.moneythumb.com/api/pdf-insights/api-reference/other/checkprogress.md | 206 "Complete 73" progress semantics. |
| D14 | https://docs.moneythumb.com/api/pdf-insights/api-reference/other/prequalify.md | APPROVED / DECLINED / NO_DECISION. |
| D15 | https://docs.moneythumb.com/api/pdf-insights/api-reference/other/scorecard.md | `sections` parameter; scorecard object families. |
| D16 | https://docs.moneythumb.com/api/pdf-insights/api-reference/other/remaining | Remaining-conversions endpoint. |
| D17 | https://docs.moneythumb.com/api/pdf-insights/scorecard.md | Scorecard Reference (metric definitions; see §7). |
| D18 | https://docs.moneythumb.com/release_notes and https://docs.moneythumb.com/release-notes | 2026 entries (May–Aug 2026). |
| D19 | https://docs.moneythumb.com/api/pdf-insights/migrating-to-1.5/migrating_from_v0.0.md | v0→1.5 changes (ids, `accountidx`, `tpreasons` text, dates yyyy-mm-dd). |
| D20 | https://docs.moneythumb.com/guides/mtjson-example | MoneyThumb JSON (MTJson) input schema. |
| D21 | https://docs.moneythumb.com/guides/read-only-review-signed-url | SIGNED_REVIEW read-only transactions view. |
| D22 | https://docs.moneythumb.com/guides/ui-embedding-guide | SIGNED_SCORECARD; `readOnlyCustomMode`. |

### MoneyThumb Java engine Javadoc (fetched OK)

| # | URL | What it contained |
|---|-----|-------------------|
| J1 | https://www.moneythumb.com/enterprise/doc/api/index-all.html | Index: `com.moneythumb.server.PDFConvertServer`, `com.moneythumb.convert.util.ConverterResults`, `OptionsPDF`, `BankTransaction`; methods `isReconciled`, `isBalancesValid`, `isHeaderValid`, `isColumnsValid`, `isPreviewRequired`, `getSuspectCount`, `getNumTypos`, `getNSFcount`, `isImage`, `isOCR`, `isSuspectOCR`, `isPartialOCR`, `setDoOCR`, `setDoOCRnr`, `setRunOCRThread`. |
| J2 | https://www.moneythumb.com/enterprise/doc/api/com/moneythumb/convert/util/ConverterResults.html | Method descriptions (quoted in §3–§6). |
| J3 | https://www.moneythumb.com/enterprise/doc/api/com/moneythumb/convert/util/OptionsPDF.html | Parser options (quoted in §2–§3). |

### Third-party pages (fetched OK)

| # | URL | What it contained |
|---|-----|-------------------|
| T1 | https://www.trustpilot.com/review/www.moneythumb.com (+ `?stars=1`, `?page=2`) | 90 reviews, 3.1/5 at fetch time; dated quotes (see §9). |
| T2 | https://capyparse.com/blog/moneythumb-review | 2026-03-18 competitor-adjacent review; pricing table; "does not automatically detect and separate multiple accounts"; Trustpilot 3.9/87 and G2 4.0/25 at that time. |
| T3 | https://scoopreview.com/money-thumb-review | 2025-04-10; cloud tiers $24.95/$49.95/$99.95 per month for 5/20/60 conversions. |
| T4 | https://www.docuclipper.com/blog/moneythumb-alternatives/ | Competitor: "MoneyThumb is primarily US"; "Desktop software"; accuracy "Not published". |
| T5 | https://www.lido.app/blog/best-bank-statement-ocr-software | Competitor (2026-09-02): "Accuracy inconsistent across different bank formats". |
| T6 | https://hyperverge.co/blog/bank-statement-analysis-software/ | Competitor: groups MoneyThumb with conversion tools. |
| T7 | https://www.cbinsights.com/compare/moneythumb-vs-ocrolus | Founding/funding data. |
| T8 | https://debanked.com/2025/09/the-merchants-paying-the-bank-statements-were-fraudulent-talking-with-moneythumb/ | 2025-09-16 CEO interview: "sub-5% that I can identify just with the human eye". |
| T9 | https://www.ocrolus.com/ and https://www.ocrolus.com/blog/key-applications-human-in-the-loop-machine-learning-lending/ | Ocrolus's own HITL description; "over 99+% accuracy"; "under 15 minutes". |

### Failed / blocked / empty

| URL | Status |
|-----|--------|
| https://www.g2.com/products/moneythumb-moneythumb/reviews ; https://www.g2.com/sellers/moneythumb | HTTP 403. Only a search snippet available (see §9). |
| https://dailyfunder.com/showthread.php/22149-Ocrolus-feedback ; …/22936-Bank-Statement-Software ; …/19478-Statement-Analysis-Software ; …/16481-Ocrio-com-gt-Ocrolus-alternative | HTTP 403; web.archive.org not reachable from this tool; r.jina.ai proxy 401. Search snippets only. |
| https://ca.trustpilot.com/review/www.moneythumb.com | 403 (the .com mirror worked). |
| https://www.docuclipper.com/comparisons/docuclipper-vs-moneythumb/ | 403. |
| https://www.herondata.io/blog/ocrolus-competitors | 404. |
| https://docs.moneythumb.com/pdf-insights/quickstarts/quickstart_insights ; …/pdf-insights/scorecard ; …/migrating_from_v1.2 ; API "Best Practices" page (three path guesses) | 404 at these paths (the `/api/...` and `.md` variants that worked are listed above). |
| https://www.moneythumb.com/moneythumb-online-help/ | 404. |
| Reddit (`site:reddit.com moneythumb`), Capterra | No relevant results returned. |
| Google Patents (Thumbprint patent number) | Not located; only press releases. |

---

## 1. Native PDFs vs scanned statements — OCR

### DOCUMENTED

- Four input classes (S28): "Most PDF statements that you download from a bank are text based PDF's" (parsed directly). Image-based/scanned ("You can only select a region. You cannot select lines of text."), searchable PDFs ("image-based content with an OCR text layer … may contain OCR errors — 'the amount of cents was incorrectly recognized as "so" rather than "50"'"), and encrypted PDFs ("When you copy/paste text from them into another document, you get what looks like gibberish characters") all require PDF+ (OCR) or the cloud product.
- OCR is proprietary and branded: "PDF+ is MoneyThumb's OCR option to handle scanned documents and other image based PDF's" using "proprietary PinPoint OCR technology" (S5, S6). The 2015 launch post names no third-party engine (S7). Marketing: "The only OCR/IDR technology built for bank statements" (S1).
- PDF+ pipeline (S6): "Like other OCR, it does an optical recognition process first … however it will then also attempt to reconcile it to verify that all transactions have been found." If reconciliation fails it "analyzes column context to re-recognize missed or misread values" (e.g. "a period had a spec of dust that caused it to be recognized as a comma, or the number '5' looked like the letter 'S'"), then highlights values requiring manual correction.
- Accuracy conditioned on scan quality (S5): "A clean document, scanned at 300 dpi, should produce 100% accuracy." Scan guidance: 300 dpi, no tilt, 50% brightness, no markup (S29). "when you begin with a poor quality scan, the time and effort involved to manually fix OCR errors can be too much" (S29).
- Platform: desktop OCR add-on is "Currently Windows only" (S6); cloud/API OCR is platform-independent.
- API controls (D8, D9): `doocrfile` ("Run OCR when initial processing fails"), `neverocr`, `asyncocr` (email on completion), `requiresRerunWithOCR` ("Shows whether OCR is required to process the file. Only use when `neverocr=true`"). Java engine: `setDoOCR` ("whether OCR should always be run, even if the PDF appears to be text based"), `setDoOCRnr` ("always running OCR if the statement did not reconcile with text processing"), `setRunOCRThread` (J3).
- Async behaviour (D5): "Image documents are converted asynchronously and their results returned by callback." Sync mode is deprecated; OCR files return 202 and require polling (D8, D13).
- OCR provenance in output (D8, D12, J1/J2): `ocr` ("Shows whether it was processed using OCR"), `image` ("PDF was image-based"), `numTypos` ("The number of typos fixed by PDF+ PinPoint"), `suspectCount` ("The number of currency values with low-confidence digits"), `previewRequired` ("due to typos found or if `suspectCount` is more than 0"); Java also exposes `isSuspectOCR()` and `isPartialOCR()`.
- Thumbprint-only product does not OCR: "OCR is not performed and image documents return with a `requires OCR` message" (D5); score −1 = "Not scorable. Typically, an image-based PDF rather than a native document." (D3).
- Image files (JPG/PNG) as input: `pdf-filename` "Accepts all supported file types" (D8) but no page fetched enumerates image formats. Not documented either way.

### STRONGLY INFERRED

- The text path and the OCR path share one downstream parser; OCR is a fallback invoked on (a) no text layer, or (b) reconciliation failure (`setDoOCRnr`, `doocrfile`). Reconciliation is therefore the trigger for OCR, not just a check after it.
- "Encrypted" PDFs are handled by rendering-and-OCR rather than by decoding custom font encodings (they are grouped with scanned PDFs as "requires PDF+").
- `numTypos` counts corrections made to satisfy reconciliation ("typos fixed by PDF+ PinPoint"); i.e. the engine edits recognised digits when a candidate substitution makes the statement reconcile.

### PLAUSIBLE HYPOTHESIS

- PinPoint is a post-processing layer (digit-confusion tables, column-aware re-recognition, reconciliation-guided search) over a general-purpose OCR core. MoneyThumb never names a core engine; there is no evidence either way.

---

## 2. Unknown / unseen bank layouts

### DOCUMENTED

- Template-free positioning: "Unlike template-dependent processes, our software doesn't need to be told upfront what bank statement format is being used" (S24); "proprietary algorithms to identify bank or bank statement formats … correctly processes over 99% of U.S. bank statements" (S15); "Recognizes 95% of U.S. bank statements, through intelligent document recognition algorithms" (S2, S23). Both 95% and 99% figures appear on current pages.
- Coverage claims: "MoneyThumb works with thousands of banks and financial institutions" (S5); "Many more banks than listed work with our converters - in fact, we haven't met one that doesn't" (S9); "works with most of the banks around the world" (S1). The "Proven Banks" list is of banks "whose PDF Statements have been verified" (S9). Unlisted bank: "contact support@moneythumb.com for verification" (S5); "please notify us immediately and we will work toward a solution!" (S9).
- No user column-mapping or "teach a layout" feature exists in PDF Insights docs. The nearest is in the desktop converters: "Whenever you use Preview Mode when running a PDF or CSV conversion, the column names are saved and automatically assigned to subsequent conversions" (S8); "Advanced PDF options to specify the text which identifies the start of the different statement sections" (S8); `setStartAccount`/`setEndAccount` regex "defining account boundaries", `setSpacing` 0.5–5.0, `setPagewidth`, `setNeedAlphas`, `setNosepdates` (J3); `spacingfactor` is also an API parameter (D9).
- Failure diagnostics (S8): "No transactions found" is accompanied by "Found 100 lines with a date, 90 lines with a currency value, 80 lines with both."; "If all your transactions are positive numbers, then 2QBO Convert Pro was unable to recognize the sections correctly".
- Layout validity flags (J2, D8): `isHeaderValid()` "flag as to whether a header row was found"; `isColumnsValid()` "flag as to whether the existing column setup is valid for the statement found"; API `columnsValid` "Column consistency across statements".
- Thumbprint depends on per-bank baselines: "When a bank changes its template, or a new bank is introduced, early scores may run higher than warranted" … "Until ThumbPrint learns the new baseline—expect some early false positives on genuinely new formats" (D3).
- Language: `language` accepts "en, es, fr, de, ln, pt, it" (D8/D9). Geography: a competitor says "MoneyThumb is primarily US" (T4); MoneyThumb's own bank-verification fields are FDIC-based (`fdicaddress`, `fdiccity`, `fdicstate`, `fdiczipcode`) (D8). No Canadian bank appeared in the fetched "Proven Banks" excerpt (search-only; not verified).
- Machine learning: home page says "Machine Learning — Corrects and flags questionable transactions" (S1); the lender page says the platform uses "smart algorithms" rather than AI (S14); the 2026 ML blog makes no claim about MoneyThumb's own models (S12).

### STRONGLY INFERRED

- The parser is a generic, heuristic line/column model (date token + currency token per line; section detection; header-row detection) rather than a per-bank template library. Evidence: the diagnostics count "lines with a date"/"lines with a currency value"; the generic knobs (spacing factor, section-start text, account-boundary regex); the "we haven't met one that doesn't" claim; and the fact that the same engine converts credit-card, brokerage, tax and P&L documents (`setDocType` PDF_STATEMENT/PDF_TAX/PDF_PL/PDF_BAL, J3).
- Per-bank knowledge exists, but for fraud (Thumbprint baselines of fonts/column positions from "millions of processed PDF bank statements", S10) and for bank identification (`bankName`, `bankURL`, FDIC lookups), not as a required parsing template.
- Unknown-layout handling is: run the generic parser → reconcile → if it fails, flag/OCR/preview; there is no documented "learning" from user corrections in PDF Insights.

### PLAUSIBLE HYPOTHESIS

- Bank-specific tuning (section keywords, date/amount formats) is accumulated inside the generic engine as rules, released as software updates ("we will work toward a solution"), which would explain both the "any bank" claim and third-party reports of "Accuracy inconsistent across different bank formats" (T5).

---

## 3. Transaction reconstruction

### DOCUMENTED

- Line model and sections (S8): credits/debits are recognised by statement sections; "If separate credits and debits sections were not found, then the preview screen may show credits as negative. In this case the checkbox for Switch signs of amounts should be selected." Credit-card polarity: "Most credit card statements have the signs of amounts reversed so that credits are a minus amount, and charges are positive."
- Sign handling in API/engine: `donegate` "Values require negation for reconciliation" (D8, D9); `isNegate()` "flag if all values should be switched in sign (i.e. a creditcard)" (J2).
- Multi-line descriptions: `combinelines` "Merges multi-line descriptions" (D9); desktop "Combine multiple description lines into the payee name" (S8); `setCombineLines` "combine description lines" into payee vs memo field (J3). Output has separate `description` and `memo` (D10).
- Running balance: the converters explicitly ignore the statement's balance column — "If your statement has a Balance column, it should not be used—the entry in the pull down list should be blank. QuickBooks will calculate the balance" (S8); "the column selection should be blank (to ignore it)" (S35). The API offers `includebalance` "Include running balance per transaction" and the transaction field `balance` (D8, D10).
- Dates: US or European order (`readUSdates`/`writeUSdates`), `yearoverride` (D8); desktop can read dates "without any separator" at the cost that "non-date values such as check numbers to be interpreted as dates" (S8).
- Check numbers: `checknumber` (integer) (D10); `number` in scorecard detail rows (D8).
- Multi-account / multi-month: "automatically recognizes multiple monthly statements in a PDF and multiple accounts in each statement" (S15); `accountseqno`/`monthseqno` select one or "-1" for all (D9); `numAccounts`, `accountSequence`, `numMonths`, `monthSequence`, `isMonthToDate` (D8). A third-party reviewer says the (desktop) product "does not automatically detect and separate multiple accounts" (T2) — contradicts S15; likely product-line specific.
- Positional provenance: `setCreateMap` "create a .map file with page number and position of each transaction" (J3).
- Transaction identity: each transaction has a unique `id` since v1.5 (D19); `possible` is "Internal use only" (D10).

### STRONGLY INFERRED

- The API's per-transaction `balance` is computed (start balance ± cumulative amounts), not read from the printed balance column, since the engine treats the balance column as ignorable and reconciliation is totals-based (see §4). Therefore MoneyThumb's running balance carries no independent evidential value against the printed running balance.
- `possible` marks candidate lines the parser was unsure were transactions (name + "Internal use"); the count of such lines is not exposed.

### PLAUSIBLE HYPOTHESIS

- Multi-line assembly is anchor-based: a line with a date and an amount starts a transaction; following date-less lines attach as description/memo until the next anchor. The `setNeedAlphas` option ("Allow transaction descriptions containing only account numbers without letters") suggests a "description must contain letters" heuristic used to reject noise lines.

---

## 4. Reconciliation / statement validation

### DOCUMENTED

- Definition: "starting balance + deposits − withdrawals = ending balance" (D2); "compares transaction totals to summary information on the statement. If everything checks out, the statement is identified as reconciled" (S2, S24); the converter "will try to reconcile the credits/debits found with the starting and ending balances printed on the bank statement" (S36).
- Granularity: "Each account in each monthly statement in a PDF counts as a conversion. Each of those accounts also gets reconciled separately." (S5).
- Output fields (D8, D9, D12, J2): `reconciled` ("Shows whether the statement reconciles"); `balancesValid` ("Both starting and ending balances were found"); `startBalance`, `endBalance` ("from the account summary, if found"); `endBalanceCalc` ("the calculated ending balance. If the statement was not reconciled this value is likely different than the end balance found from the pdf"); `endBalancePDF` (deprecated); `totCredits`, `totDebits`, `numCredits`, `numDebits`; `likelyMissingTransactions` ("Shows whether we detect transactions are missing"); application-level `totalstatements` and `totalstatements_reconciled`.
- Tolerance: `alloweddiff` "Tolerance for balance discrepancies (default 0)"; "a value such as 100 would mark the statement as reconciled if the balances were accurate within $100.00" (D9 / search excerpt of the same page).
- Unreconciled path: OCR loop "if the statement does not reconcile, PDF+ will go back through the statement looking for values that might have been missed" then "highlight for the user exactly which values are in question and in need of manual attention" (S5, S6). Unreconciled statements are still delivered; "non-reconciled summaries" are listed as a risk signal on the scorecard (S16). Scorecard `_metadata.someTransactionsExcludedDueToValidationFailures` (boolean) and `_metadata.warnings` exist (D8, D15).
- Human override of the summary: `/updatesummary` lets the client overwrite `startbalance`, `debits`, `credits`, `endbalance` for a statement (D11). `/getresults` preserves originals: "Any changes made to the data won't be reflected in the results data" (D12).
- Cross-statement checks (D17, D8): `balance_match` "Indicates if the starting balance of this statement matches the ending balance of the previous one"; `month_gap` "Indicates if there is a gap in dates between this statement and the previous one"; `daysMissing` "The number of business days missing transactions for the month"; `columnsValid` across statements; `filePreviouslySeen.numInLast3Days`; HTTP 429 for "Duplicate file uploaded too frequently".
- Claims: "MoneyThumb reports a 95% reconciliation rate with 99.9% accuracy, compared to competitors' 80% rates" (S14); the lender page (search excerpt) adds that "competitor claims of 99% are ONLY on the percentage that reconcile".

### STRONGLY INFERRED

- Reconciliation is totals-only: one equation per account-statement. It does not check the printed per-line running balance (the balance column is ignored in the converters), so compensating errors (two mis-read amounts that cancel; a credit mis-signed and a debit mis-signed by the same amount) pass as "reconciled".
- `reconciled` is a gate for the OCR retry and for the reviewer's attention, not a gate for output: the scorecard, tags and prequalification are produced regardless, with warnings.
- Because `/updatesummary` edits the summary side of the equation, a client can make a statement "reconcile" by editing the totals rather than the transactions; the originals survive only in `/getresults`.

---

## 5. Fraud / integrity — Thumbprint

### DOCUMENTED

- Mechanisms (S3, S10, S22): (1) internal consistency — "checks for inconsistencies within the document such as columns, date formats, text fonts, and other data points"; "is all the text in a given column the same font, size, and at the same position? … measured to an accuracy of 1 ten-thousands of an inch"; (2) comparison "against the financial institution's unique 'thumbprint'" built from "thousands of banks by analyzing data from millions of processed PDF bank statements"; (3) arithmetic — "total up all the deposits, withdrawals, checks, and fees and see if the totals match the balances printed on the statement. A high percentage of fraudulent statements don't pass this test."; plus "PDF creation information" (S22). Output exposes `cdate`, `mdate`, `producer` (D8).
- Score: marketing "authenticity score of 1 to 1000 where 1 indicates no evidence of tampering and 1000 shows 100% certainty of alterations" (S3). Docs: −1 "Not scorable" (image PDF); 0 "No abnormalities"; 1–299 low; 300–700 "Flag for a closer look"; 701–999 "Escalate to manual review"; 1000 "Confirmed alteration" (D3). "Any score above 0 comes with a list of the specific factors that contributed to it" (D3): `tpreasons` (text, since v1.5, D19), `fraudscore` per statement summary, `thumbprints.contributing_factors` ("Newline-delimited reasons") in the scorecard (D8).
- Metadata stance is mixed: D3 says it catches "Structural tampering and fabrication signals that survive metadata scrubbing" and lists "Anything where metadata has been scrubbed or the file re-saved" as a signal; S11 and S22 list metadata/producer among the checks.
- Known limitations (D3): cannot detect cherry-picked statements; "Cannot score fabricated institutions without baseline data"; statement-level only (no identity/ATO); new templates cause early false positives.
- Cross-statement: ThumbPrint "scores each PDF statement for tampering and inconsistencies, both within a single statement and across statements" (D2); "flags missing pages through arithmetic checks" (S2).
- Synthetic/AI-generated: "AI-assisted PDF analysis helps identify PDFs that appear to have been generated or altered using synthetic document creation techniques" (S2/S11); warning signs listed: "Repeated formatting patterns, Artificial font consistency, Unrealistic spacing, Suspicious metadata, Generated object structures, Image-based reconstruction, Inconsistent digital signatures" (S11).
- Scale and patent: US patent 2025-04-23 (number not published in the fetched pages); "reviewed more than 10M statements and identified over 500,000 fraudulent or altered documents" in a year (S20, S21). CEO on human detection: "Now it's sub-5% that I can identify just with the human eye" vs 80–85% in 2020 (T8).

### STRONGLY INFERRED

- Thumbprint is a per-bank layout fingerprint (font set, glyph positions/columns at 1/10,000-inch precision, date formats, producer strings) compared against a learned baseline, plus the reconciliation arithmetic. Its coverage is bounded by the baseline corpus, which is why it cannot score image PDFs (no text objects to measure) or unseen institutions.
- The "AI" in Thumbprint is a scoring model over hand-built structural features rather than an end-to-end learned detector (the patent press describes "structural, metadata, and content-based patterns"; the docs describe explicit factor lists).

---

## 6. Review / exception handling and confidence

### DOCUMENTED

- Signals: `previewRequired`, `suspectCount` (currency digits with low confidence), `numTypos`, `likelyMissingTransactions`, `requiresRerunWithOCR`, `reconciled`, `balancesValid`, `columnsValid`, `_metadata.warnings`, `_metadata.someTransactionsExcludedDueToValidationFailures`, Thumbprint bands (D8, D12, D3). Desktop: OCR-suspect lines "identified in the CSV file with an extra column containing a double question mark—'??'" and yellow-highlighted in Preview (S8, S35).
- Review UI: "side-by-side feature" to compare the PDF with extracted data (S15); embedded SIGNED_SCORECARD / SIGNED_REVIEW views; `readOnlyCustomMode` (D21, D22). Edits: `/updatesummary` (four totals), `/deletestatement`, Underwriter Settings ("Automatically find Untrue transactions", June 2026, D18). Prequalify rules with `actual`/`threshold` reasons (D14).
- No per-transaction numeric confidence is exposed; only statement-level counts/booleans and the "internal use" `possible` flag (D10). AI web-search industry classification carries "confidence: Low | Medium | High" (D8, D18) — the only field literally named confidence.
- MoneyThumb does not operate a human review service. The docs describe customer-side review; the only "human reviewed for accuracy" phrase found is uncontextualised copy on the legacy PDF Server page (S32).

### STRONGLY INFERRED

- Exception handling is advisory: the API always returns a result; the client decides whether `previewRequired`/`reconciled=false` blocks decisioning. Fail-closed behaviour is not built in.

---

## 7. Normalisation (dates, amounts, categories, ADB, NSF, true revenue)

### DOCUMENTED

- Dates: responses use "yyyy-mm-dd strings" (D19); statement `startDate`/`endDate` and transaction `firstDate`/`lastDate` (D8). Amounts: signed by default; "All transaction amounts can be shown as positive with debit/credit indicated in the type field" (`type`: "Debit"|"Credit", D8/D10). `currencycode` and `language` per statement (D8). MTJson: "Currency values cannot contain more than two decimal points" (D20).
- Categories: "75+ categories including Revenue, Debt Obligations, NSFs, MCA Positions, Transfers, Payroll, and Casino Payments" (D2); per-transaction `tags[] {tagName, metadata, company}` where `tagName` is a "Scorecard section reference" (D8). The full category list is not published.
- True revenue: "True Revenue includes auto-assisted cleanup to remove non-qualifying transactions like transfers, loans and other items that would not qualify as merchant revenue" (search excerpt of S2/S14); "Identify and remove transactions that should not be included as revenue such as MCAs, loans, and recovery companies" (S16); per-transaction `trueval` "Shows whether the transactions are considered true revenue" (D10); scorecard `true_credits` "The total currency value of all true credits", `non-true_credits`, `other_credits` "The total amount of untrue credits excluding MCA credits" (D17).
- ADB: `avg_balance` "The average daily balance during the statement period"; `avg_true_balance` "The average daily true balance during the statement period"; `min_balance` "The minimum daily balance during the statement period" (D17). The day basis (calendar vs business days) is not stated anywhere fetched. Adjacent fields lean business-day: `workdays` "The number of workdays in the month"; `daysMissing` "The number of business days missing transactions for the month"; `monthlynegativedays.{acct}_weekdays_with_negative_balance` (D8, D17).
- NSF/OD: statement `nsfcount` "NSF/overdraft transactions" (D8); scorecard `num_nsfs`, `total_nsfs`, `num_ods`, `total_overdraft_amount`, `num_stops`, `num_of_returns`, `days_w_returns` (D8, D17). `days_neg` "days with a negative balance"; `low_days` "days with a low balance" — the low threshold is not documented (D17).
- MCA: `num_of_mca_positions` "The number of MCAs with deposits in the statement"; `mca_withhold_percent` "The percentage of total number of withdrawals from true revenue"; `mcacompanies.withdrawal_frequency` ("Daily", "Every Other Day", "Weekly", "Monthly"); "MCA Changes" section (May 2026) (D8, D17, D18). Transfer matching across accounts via `matches {date, amount, accountLabel}` (July 2026, D18).
- Other: `isBusiness` "Inferred business vs. personal"; `expfactor` (undocumented meaning); NAICS via `dowebsearch` (D8).

### STRONGLY INFERRED

- Daily-balance series are reconstructed from start balance plus dated transactions (the engine ignores the printed balance column), so `avg_balance` inherits any date-attribution error and any unreconciled residual.
- Category tagging is rule/lexicon-driven with maintained company lists (MCA lenders, recovery companies, payment processors): `tags.company`, `mcacompanies.lender`, and the "Casino Payments" category all point at keyword/merchant dictionaries rather than a learned classifier. Not stated by MoneyThumb.

---

## 8. API / output schema (Insights API v1.5)

### DOCUMENTED

- Base: `https://insights.moneythumb.com/api/v1.5/…`; `GET /authenticate` (Basic → 24-hour session token); header `MT-Product: pdfinsights | pdfinsightstp | thumbprint` (D5, D6). Endpoints (D7): `/getapps`, `/new`, `/scorecard`, `/makexls`, `/scorecard/signedUrl`, `/makecsv`, `/uploadpdfs`, `/updatesummary`, `/googlesheets`, `/transactions`, `/deletestmt`, `/deletestatement`, `/getresults`, `/checkprogress`, `/remaining`, `/prequalify`, `/ziparchive`, `/briefcase/*`.
- `POST /uploadpdfs` request (D8): `pdf-filename` (repeatable), `fileurl` (ZIP), `jsondata` (Plaid or MTJson), `appnumber`/`appid`/`owner`, `accounttype` ("Bank", "CCard", "taxform", "financialStatement", "MTJson", "Plaid", "applicationForm", "autoDetect"), `schema`, `doocrfile`, `neverocr`, `language`, `readUSdates`, `writeUSdates`, `yearoverride`, `webhook`, `whonlynotify`, `includescorecard`, `includetransactions`, `includebalance`, `format` ("default"|"jsonobject"), `dowebsearch`, `userdata` (≤250 chars JSON). `/makecsv` adds `alloweddiff`, `spacingfactor`, `combinelines`, `accountseqno`, `monthseqno`, `asyncocr` (D9).
- Response envelope: `{ statement_summmaries: [], appinfo: {}, scorecard: {}, transactions: [] }` (S32, D5; the triple-m spelling is MoneyThumb's).
- `statement_summaries[]` (D8): `detectedDocTypeText`, `processedDocTypeText`, `reconciled`, `donegate`, `accountNumber`, `bankName`, `bankURL`, `accountOwner[]`, address fields, `accounttypestr`, `isBusiness`, `startBalance`, `endBalance`, `endBalanceCalc`, `totCredits`, `totDebits`, `numTransactions`, `numCredits`, `numDebits`, `balancesValid`, `nsfcount`, `overDraftLimit`, `ocr`, `image`, `pagecount`, `numTypos`, `suspectCount`, `previewRequired`, `likelyMissingTransactions`, `requiresRerunWithOCR`, `firstDate`, `lastDate`, `startDate`, `endDate`, `numMonths`, `monthSequence`, `isMonthToDate`, `fraudscore`, `tpreasons[]`, `numAccounts`, `accountSequence`, `columnsValid`, `fdicaddress`…, `bankphones[]`, `cdate`, `mdate`, `producer`, `currencycode`, `language`, `filePreviouslySeen.numInLast3Days`, `tid`, `uniqueTid`, `form.*` (application form extraction incl. `owner1SSN`), tax fields, `financialResult`.
- `transactions[]` (D8, D10): `Account Name`, `Account Number`, `Statements[] { statementid, startdate, enddate, Transactions[] { date, description, amount, memo, checknumber, type, id, possible, trueval, balance, customerId, tags[] {tagName, metadata, company} } }`.
- `scorecard` (D8, D15, D17): `_metadata`, `metrics.metricdata`, `prequalifyrules`, `prequalifypassedrules`, `debtsummary`, `operatingexpenses`, `accountslist` (per account-statement: `reconciled`, `fraud_score`, `balance_match`, `month_gap`, `total_credits`, `true_credits`, `net_cashflow`, `avg_balance`, `min_balance`, `avg_true_balance`, `days_neg`, `low_days`, NSF/OD/stop/return counts, MCA/recovery/transfer/payroll/ATM/etc. counts and totals), `combinedsummary` (monthly, with `daysMissing`), `truerev6mo`, `taxscorelist`, `thumbprints` (`thumbprint_score`, `contributing_factors`, `statement_id`), `monthlymca`, `mcachanges`, `mcacompanies`, `recoverycompanies`, `dailybalance` (`{acct}_balance`, `{acct}_true_balance`), `dailycashflow`, `monthlycashflow`, `monthlynegativedays`, `monthlyrecovery`, `debittrans`, `utilities`, `declinelist`.
- `appinfo`: `appnumber`, `appid`, `naccounts`, `owner`, `totalstatements`, `totalstatements_reconciled`, `totaltaxforms`, `totaltaxreturns`, `accountlist[]`, `expfactor`, `webSearch.*` (D8).
- `prequalify[]`: `result` APPROVED | DECLINED | NO_DECISION; `reasons[] {name, actual, threshold}` (D8, D14).
- Status codes: 200; 202 accepted (async/OCR); 206 "Complete 73" progress; 400 "No file found to process"; 401 "Bad token"; 429 duplicate upload; 500 with `requestId`; 503 (D8, D13). Webhook `User-Agent: MoneyThumbWebhook/<version>` (D19).
- MTJson input schema (D20): account `{bank_name*, account_number*, account_name, account_type, account_owner, account_address}` → statements `{start_date*, end_date*, start_balance*, end_balance*, customer_id}` → transactions `{date*, description*, amount*, type, balance, check_number, memo, customer_id}`; YYYY-MM-DD; ≤2 decimals.
- Stability policy: "We won't change or remove existing fields or endpoints without prior notice" but "frequent additions to the API without advance notice" (D4).
- Release cadence (D18): May–Aug 2026 entries only in the fetched view (MCA Changes; AI web-search confidence; auto-find untrue; Briefcase sharing; Financial Statement doc type; transfer matching; `customer_id`).

---

## 9. Accuracy claims, limitations, complaints

### DOCUMENTED (MoneyThumb)

- "99% Accuracy" (S1, S30); "99.9% accuracy" and "95% reconciliation rate" vs competitors' "80%" (S14); "A clean document, scanned at 300 dpi, should produce 100% accuracy" (S5); "Recognizes 95%" / "over 99%" of U.S. statements (S2, S15).
- Self-acknowledged limits: poor scans (S29); dust/transposition errors "cause transactions to be missed or value transposed" (search excerpt of S6); Thumbprint limitations (D3); desktop OCR Windows-only (S6); balance column ignored (S8, S35).

### THIRD-PARTY / UNVERIFIED

- Trustpilot (T1, fetched 2026-09-03): 90 reviews, 3.1/5. Negative, dated: "a month of transactions were missing" and "when manually tried correct errors, caused other acco[unt issues]" (Philip Czapla, 2★, 2025-09-10); "only half of them converted and manually figure out the differences" (Ghiyath Al Najjar, 1★, 2022-12-13); "pricing deceptive … required me to purchase more credits" for multiple accounts in one PDF (TX, 1★, 2026-02-12); "program does not recognize the file" (Kevin, 1★, 2025-05-16); support unresponsive (several, 2023–2026). Positive: "converted 13 statements (perfectly) in under 7 minutes" (Connie Sinasac, 5★, 2024-10-02); "flawless in converting bank and credit card statements" (Tom Bass, 5★, 2025-08-01). Note the 3.1/90 figure differs from the 3.9/87 reported by T2 in March 2026; both are as observed.
- G2 (blocked; snippet only): rating 4.0/25 per T2; a G2 reviewer says the application "sometimes tends to miss converted/processed files in the desired container"; another calls the experience "Horrible from start to finish" (search excerpt).
- DailyFunder MCA forum (blocked; search snippets only; unverified, undated): "the most cost effective approach is moneythumb and if their system can't read it, then use Ocrolus. Ocrolus has an offshore team that picks up the slack"; "all theyre doing is money thumb + outsourcing"; Ocrolus "the first time they see a deal … using their 'human in the loop' to correct their software" then "almost immediately" returns results on repeat submissions; "MoneyThumb is way more elite than Ocrolus and won't break the bank".
- Competitor pages: "does not automatically detect and separate multiple accounts within a single PDF" (T2); "Accuracy inconsistent across different bank formats" (T5); "template-based tool, struggles more with scanned inputs because noise, skew, and resolution issues break their pattern matching" (Lido search excerpt); "MoneyThumb is primarily US", accuracy "Not published" (T4). Treat as marketing.

---

## 10. Pricing, cost, data handling, privacy

### DOCUMENTED

- Lender platform (S4): "Starting at $599.95 per year"; bundles ("The more conversions you purchase up front, the lower your cost per conversion (ranges up to 60% off)"); "A conversion is one monthly statement processed"; multi-month PDFs "split by month and charge one conversion per month"; multi-account PDFs charge per account (S5); "We do not charge for repeat uploads or statements with fewer than 5 transactions"; "We do not charge specifically for API calls"; seats "free and unlimited"; balance auto-renews when below 1% or after 12 months; "Unused balance expires after 12 months". PDF Convert Server: "$0.60 per statement conversion" (S31).
- Converter lines (third-party, T2/T3): desktop $59.95–$599+ one-time; PDF+ add-on ≈$99/year; cloud $24.95/$49.95/$99.95 per month for 5/20/60 conversions (as of 2025-04).
- Security: SOC 2 Type 2 (S26, S27; achieved 2021 per S17); AWS since 2020 (S17); "SaaS company that store customer data in the cloud" (S27). No published encryption, retention or deletion specifics for uploaded statements; retention "as long as reasonably necessary", details "available in our retention policy which you can request" (S13). No statement on whether customer documents train models. Sub-processors listed in S13.
- Data minimisation is absent by design: the API extracts and returns `owner1SSN`, `owner1DOB`, `federalTaxId` from application forms (D8); `ziparchive` returns all PDFs "with optional watermarking" (D7); Briefcase shares applications between brokers and funders (D18).
- On-premise option: PDF Convert Server "may be accessed as a web service on MoneyThumb's server or installed on customer servers" (Java API / CLI) (S31). Thumbprint and the scorecard are cloud (Insights) features; the on-prem package is the conversion engine plus (per S31) Thumbprint.

---

## 11. MoneyThumb vs Ocrolus — architecture

### DOCUMENTED

- Lineage: MoneyThumb began as accountant converters (2015), added PDF Insights for lenders (2017), cloud (2018), Thumbprint (2020) (S17); Java engine (`com.moneythumb.*`) shipped as desktop, on-prem server and hosted API (J1, S31). Turnaround "under 5 seconds" for text PDFs; OCR async (S2, D5). Uses "smart algorithms" rather than AI per its own lender page (S14) while the home page says "Machine Learning" (S1).
- Ocrolus: "AI-powered systems as well as human-in-the-loop systems"; "over 99+% accuracy"; processing "reduced to under 15 minutes" (T9); "human experts validate a machine learning model on the fly" (T9, 2021). Founded 2014, $137.9M raised vs MoneyThumb 2012/2015 and an $11.2M Main Street Capital note in the 2024 recap (T7, S19).
- MoneyThumb's own framing (S25): MoneyThumb = "extraction and document analysis within a single workflow" with Thumbprint; Ocrolus = "artificial intelligence with validation processes".

### STRONGLY INFERRED

- MoneyThumb is a deterministic single-pass engine: no human labour in the loop, so accuracy is bounded by the parser and the reconciliation retry; residual errors are surfaced as flags for the customer's underwriter. Ocrolus amortises a human-corrected first pass across repeat submissions (forum claim) and sells the result as 99%+.
- Consequently MoneyThumb's "95% reconciled" is the honest ceiling of automation on its corpus; the other 5% are delivered unreconciled with warnings, not withheld.

---

## 12. Likely MoneyThumb architecture (sketch; inferred unless cited)

```
Intake (API / email eConvert / web UI / LendSaaS / Salesforce)            [D2]
  └─ Document typing: text | image | searchable | encrypted; docType
     Bank/CCard/tax/P&L/application; autoDetect                          [S28, D8, J3]
  └─ Duplicate check (filePreviouslySeen, 429)                            [D8]
Conversion (Java engine com.moneythumb.convert.*)                         [J1]
  ├─ Text path: PDF text + glyph positions → lines → date/currency
  │   tokens → header row + column setup → section detection
  │   (credits/debits; negate flag) → transaction assembly
  │   (multi-line combine; check numbers; page/position map)              [S8, J2, J3]
  ├─ Summary extraction: start/end balance, totals, period, account
  │   numbers, bank name (FDIC lookup)                                    [D8]
  ├─ Reconcile: start + credits − debits == end (± alloweddiff)           [D2, D9]
  │     fail → OCR re-pass with context-guided digit correction
  │            (numTypos, suspectCount) → re-reconcile → flags
  │            (previewRequired, likelyMissingTransactions)               [S6, D12, J3]
  └─ Statement summaries (reconciled, balancesValid, endBalanceCalc…)     [D8]
Tagging: 75+ categories via lexicons/company lists; trueval               [D2, D10]  (inferred mechanism)
Scorecard: daily balance series from start balance + transactions;
  ADB/min/neg/low days; NSF/OD; MCA positions & withhold; transfers
  matching; cross-statement balance_match/month_gap/daysMissing;
  prequalify rules                                                        [D8, D17]
Thumbprint: per-bank baseline (fonts, column x-positions at 1e-4 in,
  date formats, producer) + arithmetic + cross-statement consistency →
  −1/0–1000 score + reasons; image PDFs unscorable                        [S10, D3]
Output: JSON envelope; XLS/CSV; embedded UI; signed review URL;
  webhook; human edits via updatesummary (originals kept in getresults)   [D8, D11, D12]
```

---

## 13. Design lessons for a correctness-first, fail-closed engine

The engine's rule is that the deterministic financial validator is the only authority. Against that rule, MoneyThumb is useful both as a pattern library and as a list of things not to copy.

### Adopt (documented MoneyThumb behaviour worth mirroring)

1. **Reconciliation as a first-class, per-account, per-statement object** with explicit fields: found vs computed ending balance (`endBalance` vs `endBalanceCalc`), `balancesValid` (both anchors found), `donegate` (polarity resolved), `likelyMissingTransactions`, and application-level `totalstatements_reconciled`. Publish the residual (found − computed), not only a boolean.
2. **Cross-statement continuity checks**: `balance_match`, `month_gap`, `daysMissing`, `columnsValid` across statements, `filePreviouslySeen`. These are cheap, deterministic, and catch omitted pages and cherry-picking that a single-statement reconcile cannot.
3. **Explicit document typing and routing** (text / image / searchable / encrypted / OCR-layer-untrusted) with provenance flags (`ocr`, `image`, `requiresRerunWithOCR`) carried into every downstream number.
4. **Layout-failure telemetry** in the style of "Found N lines with a date, M with a currency value, K with both" and header/column validity flags. For a layout-agnostic path this is the minimum evidence for an explicit "layout unresolved" outcome.
5. **Positional provenance per transaction** (their `.map` of page + position). Keep page, bbox and source-line ids on every reconstructed transaction so the validator's findings can be pointed at the page.
6. **Sign/section semantics as data**: whether credits/debits came from separate sections, a signed column, or a debit/credit pair of columns; and the "all amounts positive" failure signature. Never infer polarity silently.
7. **Originals are immutable**: their `/getresults` keeps the engine's original output separate from human edits. Any override must be a separate, attributed layer.
8. **Reconciliation-guided OCR retry as a *search* heuristic only** — use the validator's residual to rank candidate re-recognitions (5↔S, period↔comma, dropped digits), but see "Avoid" item 2.
9. **Thumbprint's structural features** (font consistency per column, glyph x-position variance, producer/creation-vs-modification dates, missing-page arithmetic) as *evidence* inputs that do not require a per-bank baseline. Their documented limitation — false positives until a bank baseline exists — is exactly the failure a layout-agnostic engine must avoid.
10. **Duplicate/re-upload detection** and the "fewer than 5 transactions" special-case as explicit outcomes rather than silent handling.

### Avoid (documented MoneyThumb behaviour that conflicts with fail-closed correctness)

1. **Totals-only reconciliation as the correctness signal.** One equation per statement passes compensating errors. Add per-line running-balance verification against the *printed* balance column wherever one exists, date monotonicity, and section subtotal checks. MoneyThumb ignores the balance column; that is the single largest evidential gap to exploit in a comparison baseline.
2. **"Fixing typos" to reach reconciliation.** `numTypos` counts values the engine changed so the statement reconciles. A fail-closed validator must never accept a value edited to fit; a reconciliation achieved via substitutions must be reported as *unreconciled-with-candidate-fix*, with the candidate shown, not as `reconciled=true`.
3. **Tolerance knobs that flip the flag.** `alloweddiff` "would mark the statement as reconciled if the balances were accurate within $100.00". Keep tolerance at zero in the authority; if a caller needs a tolerance, record it in provenance and never rename the outcome.
4. **Client-editable summaries feeding the check.** `/updatesummary` lets a caller rewrite start/end/debits/credits. Do not allow overrides on the summary side of the equation without an attributed override record and a re-validation that reports "reconciled under override".
5. **Emitting a scorecard for unreconciled statements** with only a metadata warning (`someTransactionsExcludedDueToValidationFailures`). In a fail-closed engine, ADB/NSF/true-revenue on an unreconciled or partially-OCR'd statement are withheld or tagged unusable, not delivered with a footnote.
6. **Counts instead of per-item confidence.** `suspectCount` and `previewRequired` are statement-level; the per-transaction `possible` flag is "internal use". Expose per-field evidence (which digit, which page, which rule) so the reviewer is pointed at the item.
7. **Undisclosed day basis and thresholds.** `avg_balance` is "the average daily balance during the statement period" with no calendar/business-day statement; `low_days` has no published threshold; `expfactor` is undefined. Every metric definition in the engine should state its denominator; MoneyThumb's ADB must not be treated as truth (consistent with the ADB doctrine already ratified for this project).
8. **Computed running balance presented as a transaction attribute.** Their `balance` is derived from the start balance; it cannot validate anything. Distinguish `printed_balance` (evidence) from `computed_balance` (derived) in the schema.
9. **"Any bank" claims without an unknown-layout outcome.** MoneyThumb's answer to a new format is support tickets and engine updates. The layout-agnostic path should return an explicit, machine-readable "layout unresolved / partially resolved" state with the telemetry from item 4 above.
10. **Per-bank baselines as the only fraud path.** Keep bank-agnostic structural checks separate from bank-baseline checks, and label which one fired.
11. **Over-collection in the output.** SSNs, DOBs and tax IDs in the response body, plus archive download of all PDFs, are the opposite of the privacy boundary this project operates under. Keep extraction of identity fields opt-in and out of the default envelope.

### Positioning notes for using MoneyThumb as a baseline

- Compare only on statements where MoneyThumb reports `reconciled=true`, `balancesValid=true`, `ocr=false`, `suspectCount=0`, `numTypos=0`; anything else is a noisy baseline by MoneyThumb's own signals.
- Where the printed running balance exists, the engine can be strictly stronger than MoneyThumb by validating per line; that is the demonstrable edge.
- Expect MoneyThumb's ADB and negative-day counts to shift with business-day conventions (`workdays`, `weekdays_with_negative_balance`); do not calibrate the calendar-day ADB against them.
- Version drift: MoneyThumb adds fields "without advance notice" (D4) and changes behaviour via Underwriter Settings (auto-find untrue, June 2026); pin the API version and the settings snapshot used for any baseline run.
