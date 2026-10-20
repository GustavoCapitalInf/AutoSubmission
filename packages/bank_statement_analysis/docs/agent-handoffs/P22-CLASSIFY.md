# Agent Handoff — P22-CLASSIFY (Phase 2.2 cell C: the deterministic document classifier in the neutral `layout/` package — a disjoint kind with named evidence for every document, `KIND_UNCERTAIN` first-class, no routing, no truth)

Read `docs/agent-handoffs/BATCH9-RULES.md`, then `docs/agent-handoffs/PHASE2-RULES.md`, then
`docs/moneythumb-replacement/PHASE2_RULINGS.md` (ALL of it — the 2026-09-03 section: the authorization,
R3, R11, R12), then the umbrella `docs/agent-handoffs/PHASE2-2-TRUTH.md` (D1, D2, D10, the contract
§"Classifier", cases 1–5 and 24), then `docs/moneythumb-replacement/phase2_remainder/PHASE2_REMAINDER_PLAN.md`
§D.4 and §J (the taxonomy and the signals — your design), then
`phase2_remainder/research/LAYOUT_RECONSTRUCTION_MEMO.md` §D and §R.3 (the published signals and their
sources), `phase2_remainder/research/REPO_CORPUS_MEMO.md` §3.2 and §5 (what the 755 contain; that no
classifier exists), then `evidence/canonical.py` (your input type), `ocr/inspect.py` (the profile facts
you consume — read only; you copy the FACTS into your own frozen type, you never import `ocr`),
`tests/test_evidence_boundary.py` (the tripwire idiom you replicate), `tests/test_no_statement_hardcodes.py`
(the OQ2 scans you extend), `tests/paddle_synthetic.py` (the synthetic rendering facilities you reuse).
Ocean reviews and composes; you never merge or push. **Hygiene card: `newly validated = 0`; nothing
under `analysis/`, `ocr/`, `discovery/`, `webapp/`, `telemetry/`, `evidence/` is touched; no network; no
customer data; the classifier never routes and never grants anything.**

# Why
No document-type classification exists anywhere in the tree (`REPO_CORPUS_MEMO.md` §5): a voided cheque
saved as an image-only PDF is indistinguishable in every recorded column from an unseen-bank statement,
and 104 of the census's 117 "not-statements" have no per-document reason. Every later coverage claim
needs a disjoint, defensible kind per document with the evidence that produced it, and a second
denominator that is *confirmed*, not inferred. Ocrolus types a statement as a tuple and keeps UNKNOWN
first-class (DOCUMENTED); MoneyThumb exposes a layout-failure diagnostic of the form "N lines with a
date, M with a currency value, K with both" (DOCUMENTED). We build the deterministic version: signals
with word refs, tiers, and a refusal to guess.

# What you deliver (ruled — do not re-decide)
1. **`layout/__init__.py`, `layout/signals.py`, `layout/document_class.py`, `layout/refusals.py`** —
   stdlib + `evidence` only (a `tests/test_layout_boundary.py` tripwire in the exact idiom of
   `tests/test_evidence_boundary.py`, AST at any depth, no third-party import at all).
2. **The contract** exactly as the umbrella §"Classifier" prints it (`classify_document`,
   `DocumentProfileFacts`, `DocumentClass`, `Finding`, `EvidenceRef`, `KINDS`, `CLASSIFIER_VERSION = 1`).
   Frozen dataclasses; deterministic and pure (no clock, no randomness, no I/O); no document text in any
   `detail` or `signal` string (signal names are a closed vocabulary; details are counts/positions).
3. **Inputs.** `evidence` (native or Paddle `ExtractionEvidence`, words with boxes) when available, else
   `page_texts` (Tesseract-only pages) in a declared DEGRADED mode (`tier` can then be at most
   `lexical`, never `structural` for box-dependent signals; record `modality` accordingly); the profile
   facts (validity, encryption, page count, digital/scanned/mixed/unknown, per-page char counts, the
   first bytes' magic). `FILE_INVALID` derives from the facts alone (invalid PDF, encrypted, 0 pages, the
   Java object-serialisation magic `AC ED 00 05`).
4. **Signals (`layout/signals.py`) — closed, fixtured, three languages (EN/FR/ES), NEVER an issuer
   string:** period expressions ("statement period", "from … to", "du … au", "del … al"; two dates
   beside opening/closing labels); opening/closing balance labels ("beginning/opening/previous
   balance", "ending/closing/new balance", "solde d'ouverture/de clôture", "saldo inicial/final") with an
   adjacent amount; a transaction-table signal from evidence: a run of ≥ 5 lines each carrying a date
   token and a money token whose money tokens right-align within a tolerance derived from the page's
   median character width (a geometric signal; in degraded mode the line-count form without alignment);
   `Page X of Y` continuity in three languages (gaps, missing declared pages, monotonicity); MICR
   E-13B-shaped digit groups in the bottom 15 % of the page plus a page aspect ratio in [2.0, 2.6] →
   cheque image; "VOID"/"NUL"/"ANNULÉ" on such a page → voided cheque; deposit-slip and letter/notice
   lexicons with no table signal; card-statement lexicon ("minimum payment", "payment due", "credit
   limit", "crédit disponible") with a single amount column and no running-balance signal; loan lexicon
   ("principal", "interest", "escrow", "capital", "intérêts"); brokerage lexicon ("holdings",
   "positions", "market value"); screenshot: an OCR page whose raster dimensions are far from any paper
   size and no furniture repetition; activity export: dated ledger with amounts and NO period/opening/
   closing anchors plus reverse chronology or "pending" rows; running-balance discontinuity at a page
   break (last balance on page p vs first computed balance on page p+1) → a completeness finding.
   Money and date token shapes: reuse the platform's grammars only if importable without crossing a
   boundary — they are not (`analysis/money.py`, `analysis/date_tokens.py` live in `analysis/`), so
   `layout/signals.py` carries its OWN minimal, fixtured shape regexes (money with cents, four-digit
   year and short dates) and says so in its docstring; the LayoutModel (2.4) will unify them.
5. **Decision (`layout/document_class.py`):** `FILE_INVALID` first; then the cheque/voided/deposit/
   letter/card/loan/brokerage/screenshot sub-kinds when their structural or lexical signals fire WITHOUT
   a statement table signal; then `ACTIVITY_EXPORT`; then statements: `STATEMENT_COMPLETE` iff period AND
   opening AND closing anchors AND a table signal (or a printed zero-activity declaration in the exact
   sibling-omission vocabulary — copy the literal strings from `analysis/sibling_omission.py` into your
   lexicon by hand with a comment naming the source; do not import) AND no completeness finding;
   `STATEMENT_PARTIAL{findings}` when statement-shaped but a finding exists; `STATEMENT_ILLEGIBLE`
   when statement-shaped lexical signals exist but the evidence is below the usable floor (words per page
   far under the lexical hits' expectation — define it as a ratio, versioned) — an E-class placeholder for
   2.3; `KIND_UNCERTAIN` whenever signals conflict (a table signal AND a cheque signal; a card lexicon AND
   a running balance) or nothing fires. `tier`: `structural` when the deciding signal is geometric or a
   MICR/aspect/page-gap fact; `lexical` when keywords only; `uncertain`. Every verdict lists its
   `EvidenceRef`s.
6. **Fixtures (`tests/layout_fixtures/`, synthetic only, dates ≥ 2031, invented names/amounts):** one
   generator per kind rendering a native PDF via PyMuPDF AND, where a raster matters (cheque aspect,
   screenshot dimensions), an image PDF — reuse `tests/paddle_synthetic.py`'s rendering helpers (import
   from `tests/`, not from production); for each fixture the expected `kind`, `sub_kind`, `tier`, and the
   signal names. Include: complete statements in EN/FR/ES; a two-money-column and a single-signed-column
   statement; partials with a page removed, the opening removed, the closing removed, the period removed;
   a balance discontinuity at a page break; an activity export; a cheque image; a voided cheque; a
   deposit slip; a letter; a card statement; a loan statement; a brokerage page; a screenshot-shaped
   image; an invalid (Java-magic) file; a rotated complete statement (display-frame boxes from cell K's
   reader are NOT available on your branch — build your rotated fixture's evidence by hand in the
   display frame and say so); a conflicting fixture for `KIND_UNCERTAIN`.
7. **OQ2:** extend `tests/test_no_statement_hardcodes.py`'s scan roots to `layout/` (an APPEND to the
   roots tuple only; the guard file is a shared surface — check `train12` carries no other change to it
   before you report).
8. **Measurement instrument (committed, read-only): `tools/classify_census.py`** — walks a run of
   record's `rows.csv`, loads each document's cached evidence (`native_evidence` when cell K's schema-3
   artifacts exist; until then, and in your own measurement, the cached page TEXT from the cold cache in
   degraded mode — say which you used) and the profile facts, classifies, and writes a private per-sha
   CSV (sha, kind, sub_kind, modality, tier, signals) plus an AGGREGATE table to stdout: kind × modality
   × tier counts over the whole archive and over the unresolved set; the disjoint sum asserted; validated
   documents not classified `STATEMENT_COMPLETE` listed by sha16 with their kind (a named finding). Run
   it once on the run of record and put the aggregates in your W3 (never a name, never a value); compare
   against the census NOT-STATEMENT (117) and portal-export (13) sha lists from
   `docs/moneythumb-replacement/census_batch9/` as AGREEMENT counts only (they are evidence, never truth
   — R3).

# Files you own (exact; nothing else)
`layout/**` (new package) · `tests/test_layout_boundary.py` · `tests/test_layout_document_class.py` ·
`tests/test_layout_signals.py` · `tests/layout_fixtures/**` (new) · `tests/test_no_statement_hardcodes.py`
(the roots APPEND only) · `tools/classify_census.py` (new) · `corpus_gate.py`'s
`EXCLUDED_ANALYSIS_CALLERS` register — ONLY if your tool must be excused (check the register on `train12`
first; append at most one entry) · your W3 section.

# Mutation table (run every mutant, name every killer)
M1 drop the MICR rule → the cheque fixture must stop being `structural` (killed by its test) · M2 drop
the aspect-ratio bound → a cheque-shaped page with MICR and a portrait aspect must stop classifying as a
cheque · M3 drop `Page X of Y` gap detection → the page-gap partial fixture · M4 require only two of the
three anchors for `STATEMENT_COMPLETE` → the three "removed anchor" partial fixtures · M5 table signal
without the alignment test in evidence mode → the conflicting fixture (a letter whose dated lines do not
align must not become a statement) · M6 conflicting signals resolved by priority instead of
`KIND_UNCERTAIN` → the conflict fixture · M7 degraded mode allowed to emit `structural` → the text-only
fixture's tier assertion · M8 a random or time-dependent tie-break → the purity test (two calls equal) ·
M9 an issuer string added to a lexicon → the OQ2 guard (add a synthetic issuer-name mutant and show the
guard catches it) · M10 `FILE_INVALID` decided after a text signal → the Java-magic fixture · M11 the
activity-export rule requiring the anchors → the export fixture · M12 a third-party import in `layout/`
→ the boundary test.

# Proof floor
Full default suite; the 5 canonical guards (with your roots append); the 7 canonical conformance files;
`python corpus_gate.py` GREEN 105/3/1; `pytest -m corpus`; `cohort_replay --expect-identical` at base and
closure over two representative cohorts (you touch no production module — say so and replay
`guardian_cu` + `first_citizens` as the standing representatives); privacy scan 0 over your added lines
against the run-of-record population (`discovery_reports/TRAIN11-4f7d798/…-331d9136/rows.csv`, cold
cache `.claude/recovery/webapp_data_train11_cold`, READ-ONLY); message scan 0. Heavy proofs one at a
time on this host.

# Report contract (final message to Ocean AND your W3 section `# §P22CLASSIFY — …`)
population (fixtures by kind; the archive aggregates) · root cause · solution · newly validated (0) ·
other ladder movement (0) · previously validated preserved (all, identical) · regressions (0) ·
correctness evidence (per-kind fixture results; the disjoint sum on the archive; the validated
exceptions named by sha16) · generalization evidence (the FR/ES fixtures; the two layout archetypes) ·
classification evidence (kind × modality × tier tables; agreement with the census lists) · commits ·
proof-floor exits · privacy count · risks last (what the classifier cannot see without word boxes on
scanned pages — the 2.3 dependency).

# Exclusions
No routing of any kind · no import of `analysis`/`ocr`/`discovery`/`webapp`/`telemetry` · no learned
tier · no LayoutModel (rows/columns/regions beyond the one table signal) · no change to
`discovery/runner.py` (cell T wires your function) · no adjudication (cell H) · no truth (R3: your
verdicts are proposals) · no cost field.
