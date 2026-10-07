# True revenue: handoff (2026-10-07)

For the agent taking over the true-revenue work. Read this first, then the progress ledger
(`C:/Users/GustavoPrietodePaula/work/true-revenue/.superpowers/sdd/progress.md`, git-ignored, local only).
Everything below marked LOCAL lives only on the owner's office PC and holds masked corpus evidence: read it there, never commit it.

## 1. Where things stand

- **Branch:** `true-revenue`, worktree `C:/Users/GustavoPrietodePaula/work/true-revenue`.
  The audit round-2 fix run is complete through `283e90e` (pushed to `origin/true-revenue`), and the final review's
  three findings are fixed on top of it (F1 `7854cf1`, F2 `4cab9ef`, and the docs commits after them, this document
  among them), then the fix run's own review round 1 (`1dd3b64`, `7b7fb1e`, `2d81a43`, `80e3d4b` and the docs
  commit after them; local, not pushed yet).
  It sits on `text-first-v1` = `c106634` (lender detection, classification 5.4). Nothing is merged or deployed: the Fly demo runs older code.
- **Versions:** classification **5.7**, analysis stage **33** (`webapp/artifact_cache.py`). Neither is released, so the
  final review's fixes are folded into 5.7 / 33 (the cache held no stage-33 analysis; spec §9.3).
- **Main checkout** (the OneDrive folder) is on `lender-detection` and must stay untouched: `git -C <main> status` prints only `## lender-detection`.
- Nothing is running.

| Stage | What | State |
|---|---|---|
| Feature (S1-S6) | True revenue (headline) and Verified revenue, per-credit tiers verified / counted_flagged / excluded_pending_review (held) / non_revenue; dashboard, package and exports; classification 5.5 and 5.6 | done 2026-09-30 |
| Audit round 1 | 62 verified issues, fixed in B01-B12 (`fa37907..c486fd5`) | accepted 2026-10-02 |
| Audit round 2 | re-audit on `c486fd5`: 56 issues, all confirmed; 54 fixed in R2-B01..R2-B16 | done; R2-B16 made the single version move (5.7 / 33) |
| Owner rulings 2026-10-02 | the underwriter's answers to the 13 open questions, R2-OW01..R2-OW16 | done (Q3b held back, §6) |
| Owner requests 2026-10-06 | Q3 amended (the Zelle setting, R2-OW17); lender payment changes (R2-OW18) | done |
| R2-L01 | Liberis ledger admission, carried over from R2-B03 | done |
| Acceptance of the round (`283e90e`) | census on both bases, G7, full suite, real browser | ACCEPTED 2026-10-07 (LOCAL `round2/reports/ACCEPT-report.md`) |
| Final review of `c486fd5..283e90e` | three findings (F1 important, F2 and F3 minor) | fixed (LOCAL `round2/reports/FINAL-FIX-report.md`) |
| Review round 1 of that fix run | one important finding (the review decision) and three minor ones | fixed (the same report, "Review round 1 fixes") |

Corpus figures at the accepted head (re-parsed basis, 2,513 accounts; shares of posted credits; Zelle setting Yes, the default):

| Point | True | Verified | Held | Non-revenue | $0-True statements |
|---|---|---|---|---|---|
| round-1 accepted (`c486fd5`) | 66.78% | 28.69% | 18.42% | 14.80% | 139 |
| round-2 baseline (R2-B01) | 66.75% | 28.68% | 18.44% | 14.81% | 140 |
| **accepted head (`283e90e`)** | **67.58%** | **28.11%** | **17.40%** | **15.03%** | **148** |
| the same under the Zelle setting No | 66.75% | 28.11% | 16.77% | 16.48% | 171 |

On the cached basis the accepted head reads True 70.04% and Verified 28.06%. G7 holds from `c106634` on both bases
(lenders gained 0, lost 0; the only lender-side moves are R2-OW13's declared returned-payment moves). The full suite
fails only the 16 known tests of `lender-research/census/failed-ld-final.txt`. The final review's fixes move no
revenue figure; their lender and withholding moves are declared in the FINAL-FIX report.

## 2. Owner instructions in force

- The goal (2026-10-01): audit True revenue strictly the way the MCA underwriting industry counts it, fix every bug or misstatement, and iterate until a fresh audit finds nothing new. Run autonomously. **End every run with three headings: Blocked on me / Changed / Found.**
- **Models (2026-10-03): Opus only.** No Fable anywhere: implementers, fixers, reviewers and verifiers are all Opus.
- **Push `true-revenue` to GitHub periodically** (owner, 2026-10-02): after each batch, scan the new commit messages for statement values first, fast-forward only. Never force-push, never open a PR, merge or deploy without asking.
- Take your own recommendations; ask only when a call is genuinely split and high-impact. Always ask before a merge, a deploy or a force-push.
- The MCA principle (2026-09-30): True revenue is money the business earns from its operations. Government money unrelated to the business is never revenue; a government or insurer paying the business for its services still is.
- Rulings: spec `docs/superpowers/specs/2026-09-28-true-revenue-design.md` §2 (2026-09-28 Q1-Q8), §2.1 (2026-10-02 answers), §2.2 (2026-10-06 requests), §19.1 (owner decisions), §17.1 (open questions), §20 (every amendment). The 2026-10-02 answers are written "Qn (2026-10-02)", never a bare Qn.
- Privacy: tests and docs use fabricated data only (CONTOSO / FABRIKAM / NORTHWIND / SAMPLE). Never put a real person's or private business's name, an account number, an amount or a date from a statement into code, tests, docs or commit messages. Quote corpus rows only with digits masked.

## 3. The owner's rulings and requests (summary)

LOCAL verbatim answers and readings: `lender-research/revenue/audit-archive/audit/round2/owner/answers.md`, plus `questions.pdf` beside it.

| Q | Ruling as built | Batch |
|---|---|---|
| 1 | No-sender wires stay held, plus a review aid: "recurring payments start after this deposit: possible funding" | OW12 |
| 2 | Insurers paid for the business's work are counted and flagged; a one-off claim on its own policy stays out | OW07, OW08 |
| 3 (amended 2026-10-06) | **Zelle follows the Settings choice "Mark Zelle Payments as True Revenue", Yes by default:** Yes counts every Zelle deposit as the rules read person-to-person money (counted and flagged "Zelle"; the owner's own name and repeated round sums from one sender held; refunds, returns and loan money out); No makes every Zelle deposit non-revenue (`zelle_excluded`) and shows the excluded total. Both readings are computed at analysis time; the setting picks one when served, with no re-analysis. The 2026-10-02 reading (every Zelle deposit excluded) is superseded | OW02, OW03, OW17 |
| 3b | No-sender e-Transfers repeating a round sum: ruled "Same rule as Q3", **not implemented** (it would move a real-statement pin); held for the owner (§6) | OW02 (held) |
| 4 | Package: a deposit matching an exact-cents transfer from another of the business's accounts 0-2 days earlier is held and listed for release | OW16 |
| 5 | A bounced funder payment comes out of "paid to lenders" but stays in the withholding rate; the funder stays counted; a warning is shown. Since the final review (F2): a return reverses a payment dated on or before it only, and the package matches a return whose payment sits in the previous statement | OW13, final review F2 |
| 6 | Package: bounced deposits are matched across consecutive months and a redeposit counts once; unmatched returns and chargebacks are flagged, not deducted | OW15 |
| 7 | True revenue is the default withholding basis; ATM and cash deposits count. Since the final review (F1): a statement or package whose basis is not established (True or Verified reads N/A) publishes no rate and goes to review (a decision that read Approved reads Review required) | OW14, final review F1 |
| 8 | Lease-to-own and patient-financing payouts are counted and flagged, never verified; big one-off lumps stay held | OW04 |
| 9 | Finance-named customers, rent received and lenders paying for services are counted and flagged, with the hidden-loan guard | OW05, OW09 |
| 10 | Every deposit into an account titled "premium trust" is held | OW10 (parser), OW11 |
| 11 | Builder progress draws are counted and flagged; non-dealer asset sales are non_revenue | OW06 |
| 12 | Seven no-purpose government payments are non_revenue | OW01 |
| 13 | Stripe/Intuit debit-card payouts stay excluded (both switches off) | OW01 |
| Request 2026-10-06 | **Lender payment changes:** decreases, increases, schedule changes, pauses, new streams and stops of each confirmed and potential lender's regular payment, per statement and across a package's consecutive statements; information only (no lender, withholding, revenue or gate figure reads them) | OW18 |

Shared rules CR1-CR8 are in R2-OW01's notes. The main one: no owner batch bumps a version; R2-B16's single bump covers the run.

## 4. What is left, in order

1. **Push** the final-review commits after scanning their messages for statement values (fast-forward only).
2. **Round-3 re-audit** of `c486fd5..HEAD` (Opus), then fix and repeat until a round has no surviving non-owner issue.
   Templates: LOCAL `round2/handoff/templates/` (re-audit, finish, owner-rulings plan; their verifiers are already switched to Opus).
3. **Owner report** with the three headings, carrying the open owner items of §6. Then ask the owner about merging and the Fly release.

## 5. How to run it

- LOCAL script: `lender-research/revenue/audit-archive/audit/round2/handoff/round2-fixes-workflow.js`. Its args: `handoff_args.json` beside it. The round-3 templates sit in `templates/` beside it.
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
  - Census re-parses take about 12-18 minutes; never edit sources mid-run (the manifest hashes them): measure from a frozen tree.
  - The PowerShell/Bash tools time out at 2 minutes in the foreground; use background runs for census work.
  - Stop orphaned census processes (`tools.revenue_census` / `tools.lender_census`) after a killed agent.
  - Snapshots written before the Zelle setting are compared as copies marked `zelle_true_revenue: true` (LOCAL `work/plan/accept2/mark_yes.py`).

## 6. Open owner items

- **Q3b, held:** the no-sender e-Transfer round repeats ruled "Same rule as Q3" are built and held back
  (LOCAL `round2/held/R2-OW02_q3b_no_sender_round_repeat.patch`, with the ATB pin it would move). The owner decides
  whether to apply it.
- **Q13, asked and unanswered:** should Stripe/Intuit instant payouts that print "VISA DIRECT" (counted or verified today) be excluded like the plain debit-card ones? OW01 keeps both as today and records the question in §17.1.
- **Each owner batch's open points** (R2-OW01..OW18 reports; R2-OW18's 28 "Still open" defaults) and the 13 underwriter questions' recorded alternatives (§17.1).
- **The owner-convertible calls:** gambling, `payer_text_not_read`, the review floor, B7's consumer-shaped definition, I61, I37.
- **Held patches (LOCAL `round2/held/`, plus round 1's under `audit/`):** the Desjardins holder reader (failed hand review); the B10 core-processor/TD patches; B6's debit-side spellings and the G7 admissions held back from B6 and B10.
- **The final review's F2 calls, for ratification (LOCAL FINAL-FIX report, "Review round 1 fixes"; spec §17.1 (6)-(8)):** the package's cross-statement return match (pass 4) departs from rule D twice: it also reads a return naming the funder that the funder-name reader files as a lender credit (rule D never reads a lender credit; no corpus row moves through it), and it holds back a credit the revenue side paired only where that partner is dated on or before it (F2(a) makes this necessary). R2-OW18's package payment changes read a payment pass 4 matched as a returned attempt. F1's review decision is not an open item: a statement whose withholding basis is not established, and its package, go to review, as the ruling asked.
- **Pre-existing, on main:** an `analysis/rbc.py` comment (commit 99f480d) quotes a real statement's mailing line. Clean it up in its own change.

## 7. Where everything is (LOCAL, private)

- **Progress ledger:** worktree `.superpowers/sdd/progress.md`.
- **Audit archive:** `C:/Users/GustavoPrietodePaula/lender-research/revenue/audit-archive/`.
  - `audit/`, round 1: `standard.md` (the MCA industry standard), `system_map.md`, `issues_all.json`, `plan.json`, `batches/B01-B12.md`, `reports/`, `final_review.json`.
  - `audit/round2/`: `plan.json`, `cards.json`, `issues/`, `batches/`, `reports/` (`R2-B##-report.md`, `R2-OW##-report.md`, `R2-L01-report.md`, `ACCEPT-report.md`, `FINAL-FIX-report.md`), `owner/` (answers, plan, `batches/R2-OW##.md`), `held/`, `handoff/`, `fixprobes/` (each batch's probes; `accept/` the acceptance's; `final/` the final review's).
- **Census:** `lender-research/revenue/census/` (s54..s58 snapshots, `g7_allowlist.json`, `lc_c106634.json`, `lc58_final.json`) and `lender-research/revenue/work/plan/`:
  - `accept2/` (the accepted head's re-parsed snapshots `s91_final*.json.gz`, `lc91_final.json`, the frozen trees, the Yes-marked copies);
  - `r2b01/r2_base.json.gz` (round-2 baseline), `b12/s90_head.json.gz` (round-1 final);
  - `final_fix/` (the final review's fix measurements) and `final_fix_r1/` (its review round 1's: the decision moves,
    the dated G7 snapshots and compares, the payment-change moves).
- **Corpus cache:** the main checkout's `webapp_data/` (read-only).
- **Tools (in the repo):**
  - `tools/revenue_census.py`: snapshot / compare / sweep, `--reparse`, `--zelle-true-revenue`, guards G1-G20 and G-Z;
  - `tools/lender_census.py`: G7 (legacy basis pinned; declared categories `returned_funder_moves`, `kept_in_count_returned`, `returned_funder_redirects`, the last only where the snapshots' `row_dates` (every row's date; the later snapshot's are read, else the earlier one's) show a payment dated after its return; payment changes as new outputs);
  - `tools/build_lender_registry.py`: ledger -> registry; never hand-edit the GENERATED block.
- **Spec and plan (in the repo):** the spec above, and `docs/superpowers/plans/2026-09-28-true-revenue.md` (test selections SEL-CLASSIFIER / SEL-REGISTRY / SEL-WEBAPP / SEL-REVENUE; its withholding bullet is superseded by spec §11).
