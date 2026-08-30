# Agent Handoff — OCR-LEGACY-AUDIT (Phase 2, task 1; READ-ONLY audit; launches ONLY after the batch-9 freeze)

**Do not launch before BATCH9_TRANSITION records the deterministic-v1 / multi-account-v1 baseline
FROZEN** (§8.11 steps 1–7 complete). Read `docs/agent-handoffs/BATCH9-RULES.md` first (the
"Batch-9 final rulings" block: Phase 2 = Unlimited OCR + PaddleOCR as EXTRACTORS ONLY; no Phase-2
implementation until this audit is reviewed). Ocean reviews; you never merge or push. **No code
change. No OCR call. No paid call. Nothing implemented.**

# Why (Gustavo, 2026-08-30)
This repository originally used Unlimited OCR before the project shifted to deterministic parsing,
so legacy OCR infrastructure may already exist. Phase 2's first task is therefore an audit of what
is there, not a fresh OCR implementation.

# Audit — every item, file by file, with line anchors
* the existing Unlimited OCR integration;
* OCR provider adapters;
* OCR routing / fallback logic;
* rasterization / page-image generation;
* OCR caching and artifact formats (incl. the OCR-v4 cold cache the batch-8/9 proofs replay from);
* OCR normalization;
* Tesseract integration;
* the existing OCR stage / versioning (`OCR_STAGE_VERSION` and whatever keys the cache on it);
* OCR tests / fixtures (incl. `tests/test_native_rung_parity.py`);
* evidence / confidence plumbing;
* any existing path from OCR output into the canonical statement representation
  (`Statement` / `DocumentReport`) — the seam the SAME deterministic validator would consume.

Classify EVERY component as exactly one of: `active · reusable · obsolete · duplicate · unsafe ·
unknown`, each with the evidence for the label (who imports it, which test exercises it, when it
last changed — `git log --follow`, whether it can reach a production path today). `unsafe` means it
could bypass or weaken a check or leak a document; `unknown` is an honest label, not a default.
Do not read the archive's documents to do this; the audit is of CODE, tests and artifact FORMATS.

# Then propose (a design section, not code) the Phase-2 extraction architecture
```
native deterministic
        |
        +-> validates -> done
        |
        +-> insufficient extraction
                |
                v
       Unlimited OCR / PaddleOCR
                |
                v
       canonical statement/accounts
                |
                v
       SAME deterministic validator
                |
         validated / refuse
```
Unlimited OCR and PaddleOCR are extractors only. The proposal must show, check by check, that
they cannot bypass or weaken: reconciliation; ledger identity; transaction coverage; account
boundaries; page completeness; statement period; explicit currency evidence; ADB; integrity
checks; multi-account independent validation. Name what "insufficient extraction" is decided by
(a deterministic, recorded reason — never "try OCR and see"), what the cache key and stage version
become, how cost is bounded (zero recurring paid inference remains the default; paid OCR only for
residue, per Gustavo's cost-first doctrine), what provenance the payload carries (which extractor
produced which field), and how the batch-8/9 non-regression regime (`tools/cohort_replay.py`, the
cold run, `--fail-on-regression`) extends to an OCR-fed document.

# Deliverable
`docs/moneythumb-replacement/OCR_LEGACY_AUDIT.md` — the classification table (component · path ·
label · evidence), the reuse plan, the architecture proposal, the open questions for Gustavo. Plus
W3 `§OCRAUDIT`. Any census tooling you write (`tools/ocr_legacy_census.py`) is read-only over the
tree and registered if it calls the analysis. Privacy and message scans 0. An adversarial review
follows; Gustavo reviews the audit before any Phase-2 implementation card is cut.

# Git ownership
Base `main` at the frozen baseline (or `train9` if Ocean says so at launch). Branch
`wave10-ocraudit`, worktree `.claude/worktrees/mt10-ocraudit`. Own: the audit document, W3
`§OCRAUDIT`, `tools/ocr_legacy_census.py`. Nothing under `analysis/`, `ocr/`, `webapp/`.
