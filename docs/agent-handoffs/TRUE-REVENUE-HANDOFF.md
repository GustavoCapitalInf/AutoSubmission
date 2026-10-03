# True revenue: handoff (2026-10-03)

For the agent taking over the true-revenue work. Read this first, then the progress ledger
(`C:/Users/GustavoPrietodePaula/work/true-revenue/.superpowers/sdd/progress.md`, git-ignored, local only).
Everything below marked LOCAL lives only on the owner's office PC and holds masked corpus evidence: read it there, never commit it.

## 1. Where things stand

- **Branch:** `true-revenue`, worktree `C:/Users/GustavoPrietodePaula/work/true-revenue`, pushed to `origin/true-revenue`.
  The last code commit is `88e9007`; this document is the commit after it.
  It sits on `text-first-v1` = `c106634` (lender detection, classification 5.4). Nothing is merged or deployed: the Fly demo runs older code.
- **Main checkout** (the OneDrive folder) is on `lender-detection` and must stay untouched: `git -C <main> status` prints only `## lender-detection`.
- Nothing is running. The last workflow was stopped cleanly on 2026-10-03 at 18:44 local time; the worktree is clean.

| Stage | What | State |
|---|---|---|
| Feature (S1-S6) | True revenue (headline) and Verified revenue, per-credit tiers verified / counted_flagged / excluded_pending_review (held) / non_revenue; dashboard, package and exports; classification 5.5 and 5.6 | done 2026-09-30 |
| Audit round 1 | 62 verified issues, fixed in B01-B12 (`fa37907..c486fd5`) | accepted 2026-10-02 (census guards, G7, full suite, browser) |
| Audit round 2 | re-audit on `c486fd5`: 56 issues, all confirmed; 54 to fix in R2-B01..R2-B16 | B01-B11 approved; B12 implemented and fixed, re-review pending; B13-B16 to do |
| Owner rulings 2026-10-02 | the underwriter answered the 13 open questions; planned as R2-OW01..R2-OW16 | planned, not started |
| R2-L01 | Liberis ledger admission, carried over from R2-B03 | to do |

Corpus figures (re-parsed basis, about 2,508 accounts; True = share of posted credits):

| Point | True | Verified |
|---|---|---|
| round-1 accepted (`c486fd5`) | 66.78% | 28.69% |
| round-2 baseline (R2-B01) | 66.76% | 28.68% |
| after R2-B02 (processor payouts no longer held on the processor's own fee debits, +$5.24M) | 68.64% | 28.70% |
| after R2-B12 (current) | 68.07% | 28.61% |
| expected after the owner batches | about 64-66% | about 28.2% |

## 2. Owner instructions in force

- The goal (2026-10-01): audit True revenue strictly the way the MCA underwriting industry counts it, fix every bug or misstatement, and iterate until a fresh audit finds nothing new. Run autonomously. **End every run with three headings: Blocked on me / Changed / Found.**
- **Models (2026-10-03): Opus only.** No Fable anywhere: implementers, fixers, reviewers and verifiers are all Opus.
- **Push `true-revenue` to GitHub periodically** (owner, 2026-10-02): after each batch, scan the new commit messages for statement values first, fast-forward only. Never force-push, never open a PR, merge or deploy without asking.
- Take your own recommendations; ask only when a call is genuinely split and high-impact. Always ask before a merge, a deploy or a force-push.
- The MCA principle (2026-09-30): True revenue is money the business earns from its operations. Government money unrelated to the business is never revenue; a government or insurer paying the business for its services still is.
- Rulings: spec `docs/superpowers/specs/2026-09-28-true-revenue-design.md` §2 (2026-09-28 Q1-Q8), §19.1 (owner decisions), §17.1 (open questions), §20 (every amendment). The 2026-10-02 answers are written "Qn (2026-10-02)", never a bare Qn.
- Privacy: tests and docs use fabricated data only (CONTOSO / FABRIKAM / NORTHWIND / SAMPLE). Never put a real person's or private business's name, an account number, an amount or a date from a statement into code, tests, docs or commit messages. Quote corpus rows only with digits masked.

## 3. The owner's 2026-10-02 rulings (summary)

LOCAL verbatim answers and readings: `lender-research/revenue/audit-archive/audit/round2/owner/answers.md`, plus `questions.pdf` beside it.

| Q | Ruling | Batch |
|---|---|---|
| 1 | No-sender wires stay held, plus a review aid: "recurring payments start after this deposit: possible funding" | OW12 |
| 2 | Insurers paid for the business's work are counted and flagged; a one-off claim on its own policy stays out | OW07, OW08 |
| 3 | Every Zelle deposit is non_revenue, with the excluded total shown. No-sender e-Transfer round repeats are held (Q3b) | OW02, OW03 |
| 4 | Package: a deposit matching an exact-cents transfer from another of the business's accounts 0-2 days earlier is held and listed for release | OW16 |
| 5 | A bounced funder payment comes out of "paid to lenders" but stays in the withholding rate; the funder stays counted; a warning is shown | OW13 |
| 6 | Package: bounced deposits are matched across consecutive months and a redeposit counts once; unmatched returns and chargebacks are flagged, not deducted | OW15 |
| 7 | True revenue becomes the default withholding basis; ATM and cash deposits count | OW14 |
| 8 | Lease-to-own and patient-financing payouts are counted and flagged, never verified; big one-off lumps stay held | OW04 |
| 9 | Finance-named customers, rent received and lenders paying for services are counted and flagged, with the hidden-loan guard | OW05, OW09 |
| 10 | Every deposit into an account titled "premium trust" is held | OW10 (parser), OW11 |
| 11 | Builder progress draws are counted and flagged; non-dealer asset sales are non_revenue | OW06 |
| 12 | Seven no-purpose government payments are non_revenue | OW01 |
| 13 | Stripe/Intuit debit-card payouts stay excluded (both switches off) | OW01 |

Shared rules CR1-CR8 are in R2-OW01's notes. The main one: no owner batch bumps a version; R2-B16's single bump covers the run.

## 4. What is left, in order

1. **R2-B12 re-review (Opus).** B12 = `f2756ab..c169e67` implemented, `88e9007` fixed the round-1 review's findings. Its Fable re-review was cut off.
   Run the review again with the prior findings (LOCAL `round2/reports/R2-B12-review-r1.json`). The handoff workflow does this through the batch's `resume` field.
2. **R2-B13** (name-vs-purpose spares), **R2-B14** (package duplicates, interims, upload queue), **R2-B15** (package months, left-out accounts, empty packages, counts).
3. **R2-OW01..R2-OW16**, the owner rulings, in order.
4. **R2-L01**, Liberis: an independent verify round (public evidence) first, then apply the held patch (4 corpus credits leave True).
5. **R2-B16** last: Monthly Statements units, statement exports (debit table, cell limit), the CLI's labels, then `CLASSIFICATION_VERSION` 5.6 -> 5.7 plus the stage bump as the final commit. Its note lists the owner batches' shape changes.
6. **Acceptance:**
   - the census on both bases (re-parsed is primary; the round-2 baseline is `lender-research/revenue/work/plan/r2b01/r2_base.json.gz`), every guard (G18 explained);
   - G7 from `c106634` with the owner's allowlist;
   - the full suite: only the 16 known failures in `lender-research/census/failed-ld-final.txt` may fail;
   - a real-browser dashboard check covering the owner surfaces.
7. **Final whole-delta review** of `c486fd5..HEAD` (Opus).
8. **Round-3 re-audit**, then fix and repeat until a round has no surviving non-owner issue. Templates: `round2/handoff/templates/` (re-audit, finish, owner-rulings plan; their verifiers are already switched to Opus).
9. **Owner report** with the three headings. Then ask the owner about merging and the Fly release.

**Fix first, before the next parser batch (OW10):** the corpus extraction gate crashes at the branch head. `balance_forensic_audit.csv_rows` unpacks three columns, but B11's per-credit CSV ledger is wider. R2-B05/B06/B07 ran it from frozen copies with a scratch-only harness fix; see the R2-B05 report.

## 5. How to run it

- LOCAL script: `lender-research/revenue/audit-archive/audit/round2/handoff/round2-fixes-workflow.js`. Its args: `handoff_args.json` beside it, which lists 22 batches (B12 resume, B13-B15, OW01-OW16, L01, B16) and points every path at the archive.
- Launch with the Workflow tool: `scriptPath` = the .js and `args` = the whole JSON object.
  - Per batch: an Opus implementer, an Opus adversarial review, up to 3 fix rounds, then a push agent.
  - After the batches: acceptance, then the final review.
  - A failed agent stops the loop early (no cascade); rerun it after reading the journal.
- `resumeFromRunId` works only inside the session that launched the run. In a new session, drop the finished batches from `batches`. A half-done batch's implementer continues from its own partial commits (the prompt says so), or use `resume: {base, head, round, prior}` to go straight to review.
- Gotchas learned here:
  - Every subagent shell starts in the MAIN checkout: prompts make them `cd`/`git -C` into the worktree. Check main's status after each run.
  - Write Python and regex with the Write/Edit tools (Bash heredocs mangle backslashes); compile-check generated code.
  - Usage limits and app restarts kill background workflows (permission-mode changes restart the app); resume from the journal.
  - Session crons do not fire while a workflow keeps the session busy, which is why the push lives inside the workflow.
  - Census re-parses take about 12-18 minutes; never edit sources mid-run (the manifest hashes them).
  - The PowerShell/Bash tools time out at 2 minutes in the foreground; use background runs for census work.
  - Stop orphaned census processes (`tools.revenue_census` / `tools.lender_census`) after a killed agent.

## 6. Open owner items

- **Q13, asked and unanswered:** should Stripe/Intuit instant payouts that print "VISA DIRECT" (98 deposits, about $156K, counted or verified today) be excluded like the plain debit-card ones? Wells Fargo's Intuit card pushes (6 deposits) are held. OW01 keeps both as today and records the question in §17.1.
- **Defaults taken for points the owner's words did not settle**, to report:
  - Q3b no-sender round repeats are held, not excluded ($1.0M).
  - Q12 Wisconsin Shares EBT card payments stay counted.
  - Q10 IPFS fundings on trust accounts stay excluded.
  - Q11a a draw paid by a non-builder project LLC stays held.
  - Q2 widened insurer spellings for one-off claims are held (-$56K).
- **Held patches (LOCAL `round2/held/`, plus round 1's under `audit/`):**
  - the Desjardins holder reader (failed hand review);
  - the B10 core-processor/TD patches;
  - B6's debit-side spellings;
  - Liberis, if its verify round fails.
- **Owner-eyes notes from round 2 (`ROUND2-RESULTS-SO-FAR.md`):**
  - the P2P/wire round-trip hold now fires (362 credits / $453K held);
  - U.S. Bank Venmo cash-outs beside top-ups are counted again;
  - holder readers are still missing on 353 statements of unlisted parsers.
- **Pre-existing, on main:** an `analysis/rbc.py` comment (commit 99f480d) quotes a real statement's mailing line. Clean it up in its own change.

## 7. Where everything is (LOCAL, private)

- **Progress ledger:** worktree `.superpowers/sdd/progress.md`, holding every decision, figure and interruption.
- **Audit archive:** `C:/Users/GustavoPrietodePaula/lender-research/revenue/audit-archive/`.
  - `audit/`, round 1: `standard.md` (the MCA industry standard), `system_map.md`, `issues_all.json`, `plan.json`, `batches/B01-B12.md`, `reports/`, `final_review.json`.
  - `audit/round2/`: `plan.json`, `cards.json`, `issues/`, `batches/R2-B##.md`, `reports/` (`R2-B##-report.md`, `ROUND2-RESULTS-SO-FAR.md`, `round2_results_B01_B12.json`), `owner/` (answers, plan, `batches/R2-OW##.md`), `held/`, `handoff/`.
  - `sdd/`: the feature's task reports.
  - Older briefs cite the session-43065b93 Temp scratchpad; the same files are in this archive.
- **Census:** `lender-research/revenue/census/` (s54..s58 snapshots, `g7_allowlist.json`, `lc_c106634.json`) and `lender-research/revenue/work/plan/`:
  - `b12/s90_head.json.gz` (round-1 final, re-parsed);
  - `r2b01/r2_base.json.gz` (round-2 baseline);
  - `accept/tree_final` (frozen `c486fd5`).
- **Corpus cache:** the main checkout's `webapp_data/` (read-only).
- **Tools (in the repo):**
  - `tools/revenue_census.py`: snapshot / compare / sweep, `--reparse`, guards G1-G18;
  - `tools/lender_census.py`: G7;
  - `tools/build_lender_registry.py`: ledger -> registry; never hand-edit the GENERATED block.
- **Spec and plan (in the repo):** the spec above, and `docs/superpowers/plans/2026-09-28-true-revenue.md` (test selections SEL-CLASSIFIER / SEL-REGISTRY / SEL-WEBAPP / SEL-REVENUE).
