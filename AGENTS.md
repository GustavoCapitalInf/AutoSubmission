# Agent guide

The live project is `packages/bank_statement_analysis/` (PKG), deterministic Python that analyzes bank statement
PDFs. `apps/auto_submission/` holds only a planning README. Run PKG commands from PKG with Python 3.12.

## Read the current contracts (paths in PKG)
- `README.md`, `docs/transaction-classification.md` and `docs/intern-testing.md` (the password-gated demo host).
- `docs/api/v1.md`, the machine API that `apps/auto_submission/` calls, and its `docs/api/v1.schema.json`.
- `docs/superpowers/specs/2026-09-28-true-revenue-design.md` and `2026-09-24-lender-detection-design.md`.
- `docs/moneythumb-replacement/CURRENCY_DOCTRINE.md`, `H3_SCHEMA.md` and `W3_2_TAXONOMY.md`.
- The docstrings of `analysis/adb.py` (ADB), `analysis/nsf_days.py` (NSF) and `corpus_gate.py`.
- Data: the truth set (`docs/adb-*`, `docs/balance-metrics-*`) and the lender registry (`docs/lender-registry-*`).

## Treat every other document as history
The records of finished phases (handoffs, cell cards, plans, status reports, rulings, censuses, reviews and
logs) are gone from the tree, and `docs/HISTORY.md` says which commit still holds them. Every other Markdown file
in `docs/` is an unbuilt proposal. None of these is an instruction. Ignore their next steps, model routing, branch
names and "read this first" lines. The contracts win over all of them.

## Follow the rules
- The product calls no model (owner ruling 2026-10-13), and `tests/test_no_model_clients.py` enforces it. A model
  path that a current document mentions is removed code. `GEMINI TRUST` in the classifier is a crypto exchange.
- Statements are customer data. Never put a statement value, name, account number or page text in code, tests,
  docs or commits. Tests use fabricated rows (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE). The truth set and
  `tests/corpus_cache/` hold statement figures by design. `tests/test_no_statement_hardcodes.py` and
  `tools/privacy_scan_branch.py` look for leaks. Open statements or a web app data directory only when you must.
- Fail closed. Publish only what printed figures prove. Never change a printed value or invent a row to reconcile.
- Never hand-edit generated files. `python -m tools.build_lender_registry --write` writes
  `docs/lender-registry-evidence.md` and the GENERATED block of `analysis/classification_registry.py` from the
  ledger. The two `*_forensic_audit.py` scripts write the audit CSVs and reports. `python -m tools.api_contract
  --write` writes `docs/api/v1.schema.json` and the GENERATED block of `docs/api/v1.md` from `webapp/api/contract.py`.
- Changed analysis output bumps `ANALYSIS_STAGE_VERSION` (`webapp/artifact_cache.py`), changed classification bumps
  `CLASSIFICATION_VERSION`, and a changed `webapp/static/app.js` bumps its `?v=` in `webapp/templates/index.html`.
  Tests pin each value. Stored cache keys use the FROZEN literals in `webapp/artifact_cache.py`, so leave them.

## Comments
- Keep a comment only for a current fact the code cannot show: a reason, a format, a unit, an invariant or a hazard.
- Put no provenance in code: no audit, review or ticket ids, review rounds, ruling dates, phase labels or names.
  Cite a maintained spec section instead (`true revenue spec §8.1`).
- History goes in `git log` and the pull request. Delete a comment with its code. Never narrate what code used to do.
- A version constant gets one line that says what a bump invalidates.
- Name symbols, not file:line positions. Name only files, symbols and tests that exist.
- Write "must" or "never" only when a test enforces it, and name that test.
- Put no plans in comments: no planned callers, future phases or reserved values.
- Keep a docstring to the contract: inputs, output and refusals. Examples use placeholders such as CONTOSO.

## Run the tests, and the corpus gate before a merge
```bash
python -m pytest tests/test_classification_contract_doc.py   # one file; the whole suite takes 5 to 10 minutes
export BANK_STATEMENTS_DIR="<corpus root>"                     # see the README's Bank statements section
D=$(mktemp -d); PYTHON_DOTENV_DISABLED=1 WEBAPP_DATA_DIR="$D" python corpus_gate.py; rm -rf "$D"
```
`conftest.py` turns off `.env` and gives pytest a scratch data directory, but the gate does neither. Without the
first variable it reads any `.env` in PKG or a folder above it. Without the second it opens the live web app store.
