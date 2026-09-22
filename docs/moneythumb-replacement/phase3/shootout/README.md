# Extraction shootout — the evidence behind the Phase 3.1 model picks

Run on 2026-09-20 and 2026-09-21 on rented Vast GPUs. Nine candidates, inference only, no training,
no prompt tuning against the references. 16 statements, 151 pages, image-only input rendered at
300 DPI, one frozen run per candidate. Read `docs/agent-handoffs/PHASE3-VISUAL-FALLBACK.md` for what
was decided from it.

| file | what it holds |
|---|---|
| `LEADERBOARD.md` | the per-candidate table, both tracks, plus per-document money-token recall |
| `DOCUMENT_FINDINGS.md` | per document and per candidate: misses, extras, truncated pages, CER, worst pages |
| `leaderboard.json` | the same figures as data |
| `review-breakdown.json` | the bounded disagreement review: 400 of 1,977 disputes read against the page images |

## How to read these numbers, and how not to

**They measure agreement with ChatGPT reference answers, not correctness.** The references are
themselves model output over the same documents (`reference_unverified`, a hybrid route of embedded
PDF text, rendered pages and manual additions). In the bounded review recorded in
`review-breakdown.json`, **90 of the 400 examined disagreements went against the reference**, not
against the candidate. Treat differences under about one point as noise, and never quote a figure
here as an accuracy rate.

No universal winner is claimed. A candidate that wins on this corpus of 16 statements has not been
shown to win generally.

Other things worth knowing before citing a row:

- Truncated pages hit the output cap, usually because the model fell into a repetition loop. They
  stay in every denominator rather than being dropped.
- `separator-only` misses are the same digits with different thousands or decimal separators. They
  inflate raw miss counts, so the strict and separator-adjusted numbers are both published.
- CER and WER are computed over a whitespace and markup normalised pass. Page-level edit distance
  also charges reading order and line segmentation, so a model that reads every character correctly
  in the wrong order still scores badly.
- Per-document recall is money-token recall specifically. A document can score 100% on amounts while
  losing the printed opening balance, which is the field that decides whether an average daily
  balance is publishable at all.

## What is deliberately not in this repository

The source PDFs, the rendered page images, the reference answers, every candidate's raw output and
the per-page diffs are customer statement content. They stay in the private working tree and on the
instance, and they are never committed. These four files carry counts, ratios and status only.
