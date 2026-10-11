# True revenue: handoff (2026-10-10)

For the agent taking over the true-revenue work. Read this first, then the progress ledger
(`C:/Users/GustavoPrietodePaula/work/true-revenue/.superpowers/sdd/progress.md`, git-ignored, local only).
Everything below marked LOCAL lives only on the owner's office PC and holds masked corpus evidence: read it there, never commit it.

## 1. Where things stand

- **Branch:** `true-revenue`, worktree `C:/Users/GustavoPrietodePaula/work/true-revenue`.
  The audit round-3 fix run (R3-B01 to R3-B25, on top of `1a761de`) is complete: each batch was reviewed (Opus) and
  pushed to `origin/true-revenue` after it (fast-forward); R3-B25, the run's last batch, wrote the round's documents
  and made its single version move, and waits for its review and the run's push step. `1a761de` is round 2's accepted
  head (`283e90e`) with the final review's three fixes (F1 `7854cf1`, F2 `4cab9ef`) and that fix run's review round 1
  (`1dd3b64`, `7b7fb1e`, `2d81a43`, `80e3d4b`).
  It sits on `text-first-v1` = `c106634` (lender detection, classification 5.4). Nothing of this branch is merged or
  deployed: the Fly demo runs the hosting line below.
- **Versions:** classification **5.8**, analysis stage **37** (`webapp/artifact_cache.py`): R3-B25's versions
  commit, the run's last, set 5.8 and stage 36 once for the whole round (spec §9.3), and the hosting line's merge-back
  (R3-MERGE, merge commit `7e254cf`) moved the stage to 37 and the cache-bust to `true-revenue-11`; stages 34 and 35 and the cache-bust values
  `true-revenue-7` and `-8` are skipped (the hosting line below used them), so the page asked for `true-revenue-9`;
  the final review's fixes (R3-FF, folded into 5.8 and 36) changed app.js, so it asked for `true-revenue-10`; since the
  merge-back it asks for `true-revenue-11`.
  Neither is released.
- **The hosting line:** `fix/boa-nsf` = `f2e9ae1` (it holds `fix/capone-daily-ledger` `6c2eadb` and
  `ui/5.7-dashboard-clarity` `a858647`) is live on the Fly demo as release v21. It is round 2's code (classification
  5.7) plus the owner's reports of 2026-10-07 and 2026-10-08: analysis stages 34 (the Capital One carry-in fix) and 35
  (the Bank of America daily-ledger table), and the app.js cache-bust values `true-revenue-7` and `true-revenue-8` (the
  dashboard-clarity and monthly-chart changes). This branch never reuses those values: R3-B25 skips them. The hosting
  line is merged into `true-revenue` after this run, never back to those values: the merge commit moves the stage and
  the cache-bust value past both lines' (§4, item 5). **Merged** with the owner's approval of 2026-10-10 ("Merge, then
  audit"): R3-MERGE, merge commit `7e254cf` (stage 37, `true-revenue-11`); the Fly demo still runs v21 until the
  owner asks for a release.
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
| Audit round 3 | re-audit on `1a761de`: 91 issues verified; 89 fixed or recorded in R3-B01..R3-B24, 2 owner items (R3-28, R3-76); 14 owner decisions (R3-73, R3-79 and R3-25 answered by the owner on 2026-10-07; the others with their defaults in the code, R3-78's in the held patch, R3-07's a git question) | done (R3-B01..R3-B24); R3-B25 made the single version move (5.8 / 36) |
| Hosting line merge-back (R3-MERGE) | `fix/boa-nsf` (`f2e9ae1`) merged with `--no-ff` on the owner's approval of 2026-10-10; both sides' behaviour kept (round 3's lender lines in the hosting line's plain voice, the Withholding Rate column on the served rate); stage 37, `true-revenue-11`; census, G7 and the corpus gate equal to `a13464a` but for the stage | done (`7e254cf`; LOCAL `round3/reports/R3-MERGE-report.md`) |
| Acceptance of round 3 (the Accept phase) | census on both bases, G7, the full suite, a real browser; then the final review of `1a761de..HEAD` | pending |

Corpus figures (re-parsed basis, 2,513 accounts; shares of posted credits; Zelle setting Yes, the default, unless the row says No):

| Point | True | Verified | Held | Non-revenue | $0-True statements |
|---|---|---|---|---|---|
| round-1 accepted (`c486fd5`) | 66.78% | 28.69% | 18.42% | 14.80% | 139 |
| round-2 baseline (R2-B01) | 66.75% | 28.68% | 18.44% | 14.81% | 140 |
| **accepted head (`283e90e`)** | **67.58%** | **28.11%** | **17.40%** | **15.03%** | **148** |
| the same under the Zelle setting No | 66.75% | 28.11% | 16.77% | 16.48% | 171 |
| round-3 fix run head (before acceptance) | 67.73% | 28.11% | 17.25% | 15.03% | 147 |
| the same under the Zelle setting No | 66.91% | 28.11% | 16.62% | 16.48% | 170 |

At round 2's acceptance the cached basis read True 70.04% and Verified 28.06%; G7 held from `c106634` on both bases
(lenders gained 0, lost 0; the only lender-side moves were R2-OW13's declared returned-payment moves); the full suite
failed only the 16 known tests of `lender-research/census/failed-ld-final.txt`. Round 3 moved True by +$419,550.25
under Yes and +$430,640.25 under No, each the sum of the batches' recorded moves (spec §20, "Audit round 3 in all"),
and Verified by −0.006 points (28.1145% → 28.1084%: one declared demotion, 1 row, R3-B07); the per-batch sums
reconcile to the cent in R3-B25's LOCAL report (`round3/reports/R3-B25-report.md`), and no single statement's figure
is written here; on the debit and lender side its declared moves are
R3-B01's (the ODKRAOD alias, ONDECK under the R3-26 sign-off, and the bank charges naming a funder read as charges),
R3-B02's re-debited returned payments and R3-B03's worded lump-sum payoffs. The round-3 head's figures above are
R3-B25's measurement, before the Accept phase.

## 2. Owner instructions in force

- The goal (2026-10-01): audit True revenue strictly the way the MCA underwriting industry counts it, fix every bug or misstatement, and iterate until a fresh audit finds nothing new. Run autonomously. **End every run with three headings: Blocked on me / Changed / Found.**
- **Models (2026-10-03, again 2026-10-06): Opus only.** No Fable anywhere: implementers, fixers, reviewers and verifiers are all Opus.
- **Push `true-revenue` to GitHub periodically** (owner, 2026-10-02): after each batch, scan the new commit messages for statement values first, fast-forward only. Never force-push, never open a PR, merge or deploy without asking.
- Take your own recommendations; ask only when a call is genuinely split and high-impact. Always ask before a merge, a deploy or a force-push.
- The MCA principle (2026-09-30): True revenue is money the business earns from its operations. Government money unrelated to the business is never revenue; a government or insurer paying the business for its services still is.
- Rulings: spec `docs/superpowers/specs/2026-09-28-true-revenue-design.md` §2 (2026-09-28 Q1-Q8), §2.1 (2026-10-02 answers), §2.2 (2026-10-06 requests), §19.1 (owner decisions, the answers of 2026-10-07 among them), §17.1 (open questions), §20 (every amendment). The 2026-10-02 answers are written "Qn (2026-10-02)", never a bare Qn.
- Privacy: tests and docs use fabricated data only (CONTOSO / FABRIKAM / NORTHWIND / SAMPLE). Never put a real person's or private business's name, an account number, an amount or a date from a statement into code, tests, docs or commit messages. Quote corpus rows only with digits masked.

## 3. The owner's rulings and requests (summary)

LOCAL verbatim answers and readings: `lender-research/revenue/audit-archive/audit/round2/owner/answers.md`, plus `questions.pdf` beside it.

| Q | Ruling as built | Batch |
|---|---|---|
| 1 | No-sender wires stay held, plus a review aid: "recurring payments start after this deposit: possible funding" | OW12 |
| 2 | Insurers paid for the business's work are counted and flagged; a one-off claim on its own policy stays out | OW07, OW08 |
| 3 (amended 2026-10-06) | **Zelle follows the Settings choice "Mark Zelle Payments as True Revenue", Yes by default:** Yes counts every Zelle deposit as the rules read person-to-person money (counted and flagged "Zelle"; the owner's own name and repeated round sums from one sender held; refunds, returns and loan money out); No makes every Zelle deposit non-revenue (`zelle_excluded`) and shows the excluded total. Both readings are computed at analysis time; the setting picks one when served, with no re-analysis. The 2026-10-02 reading (every Zelle deposit excluded) is superseded | OW02, OW03, OW17 |
| 3b | No-sender e-Transfers repeating a round sum: ruled "Same rule as Q3", **not implemented** (it would move a real-statement pin); held for the owner (§6), with R3-B21's widened port | OW02 (held), R3-B21 (held) |
| 4 | Package: a deposit matching an exact-cents transfer from another of the business's accounts 0-2 days earlier is held and listed for release | OW16 |
| 5 | A bounced funder payment comes out of "paid to lenders" but stays in the withholding rate; the funder stays counted; a warning is shown. Since the final review (F2): a return reverses a payment dated on or before it only, and the package matches a return whose payment sits in the previous statement. Since 2026-10-07 (R3-73): a returned payment its funder re-debits counts once | OW13, final review F2, R3-B02 |
| 6 | Package: bounced deposits are matched across consecutive months and a redeposit counts once; unmatched returns and chargebacks are flagged, not deducted | OW15 |
| 7 | True revenue is the default withholding basis; ATM and cash deposits count. Since the final review (F1): a statement or package whose basis is not established (True or Verified reads N/A) publishes no rate and goes to review (a decision that read Approved reads Review required). Since R3-B03: a basis under $500 publishes no rate either | OW14, final review F1, R3-B03 |
| 8 | Lease-to-own and patient-financing payouts are counted and flagged, never verified; big one-off lumps stay held | OW04 |
| 9 | Finance-named customers, rent received and lenders paying for services are counted and flagged, with the hidden-loan guard | OW05, OW09 |
| 10 | Every deposit into an account titled "premium trust" is held | OW10 (parser), OW11 |
| 11 | Builder progress draws are counted and flagged; non-dealer asset sales are non_revenue | OW06 |
| 12 | Seven no-purpose government payments are non_revenue | OW01 |
| 13 | Stripe/Intuit debit-card payouts stay excluded (both switches off) | OW01 |
| Request 2026-10-06 | **Lender payment changes:** decreases, increases, schedule changes, pauses, new streams and stops of each confirmed and potential lender's regular payment, per statement and across a package's consecutive statements; information only (no lender, withholding, revenue or gate figure reads them) | OW18 |
| Answers 2026-10-07 (audit round 3) | R3-73 "Count it once": a re-debited returned payment leaves the withholding numerator once; R3-79 "Exclude worded payoffs": a confirmed funder's debit printing a payoff word leaves the rate; R3-25 "Add a 'Caught up' line" in the lender payment changes (spec §19.1) | R3-B02, R3-B03, R3-B05 |

Shared rules CR1-CR8 are in R2-OW01's notes. The main one: no owner batch bumps a version; the run's last batch bumps once (R2-B16 in round 2, R3-B25 in round 3).

## 4. What is left, in order

1. **The Accept phase** of the round-3 run: the census on both bases (re-parsed and cached, both Zelle readings) from
   `1a761de`, G7 from `1a761de`'s lender census with the owner's allowlist plus the R3-26 sign-off, the full suite and a
   real browser; it writes its own report (this document is not edited there). Known red for it:
   `tests/test_l1s3_census.py` since R3-B23 (its AST sweep reads `webapp/app.py::_account_analysis_rows`'s
   `section == "statement"` as a payload-key read; R3-B24's concern 1: an `EXCUSED` entry fixes it).
2. **The final review** of `1a761de..HEAD` (Opus), with its fix rounds.
3. **Push** after scanning the new commit messages for statement values (fast-forward only).
4. **The owner report** with the three headings (Blocked on me / Changed / Found), carrying §6.
5. **Merge the hosting line back** before any release of `true-revenue`, with the owner's OK: `fix/boa-nsf` = `f2e9ae1`
   (it holds `fix/capone-daily-ledger` `6c2eadb` and `ui/5.7-dashboard-clarity` `a858647`). Never resolve the versions
   toward the hosting line's values (stage 35, `true-revenue-8`). The merge changes analysis output (the Capital One
   carry-in and Bank of America daily-ledger parsers) and app.js (the dashboard-clarity and monthly-chart changes), so
   the merge commit itself moves the analysis stage and the cache-bust value to the next free values above both lines
   (stage 37 and `true-revenue-11` while neither line has moved past 36 and `-10`; it read `true-revenue-10` and `-9`
   until R3-FF's F6 took `-10`): an entry cached at 36, or a `-9` or `-10` app.js, served before the merge (the Accept
   phase's real-browser run serves 36 and `-9` locally) must never be read as the merged code's. Until then stage 36
   and `true-revenue-10` are this branch's (and `-9`, which it served): a further hosting-line change takes stage 37
   and `true-revenue-11` or above (and the merge then goes above those). Then ask the owner about the Fly release.
   **Done** (R3-MERGE, 2026-10-10): merge commit `7e254cf`, stage 37 and `true-revenue-11`; the Fly release still
   waits for the owner.
6. **The round-4 re-audit** of the branch (Opus), then fix and repeat until a round has no surviving non-owner issue.
   Templates: LOCAL `round2/handoff/templates/` and the round-3 workflow in `round3/handoff/`.

## 5. How to run it

- LOCAL script: `lender-research/revenue/audit-archive/audit/round3/handoff/round3-fixes-workflow.js` (round 2's is
  `round2/handoff/round2-fixes-workflow.js`). Its args: the `handoff_args*.json` beside it.
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
  - Version values used on another line (the hosting line's stages 34 and 35, its `true-revenue-7` and `-8`) are never reused here: a browser or a cache entry holding them would be served as this branch's. The reverse holds too: this branch's stage 36 and `true-revenue-9` and `-10` (R3-FF's F6) are reserved: a further hosting-line change takes 37 and `-11` or above, and the merge-back commit takes the next free values above both lines (§4, item 5).

## 6. Open owner items

- **Q3b, held:** the no-sender e-Transfer round repeats ruled "Same rule as Q3" are built and held back
  (LOCAL `round2/held/R2-OW02_q3b_no_sender_round_repeat.patch`, with the ATB pin it would move), and audit round 3
  (R3-B21, R3-78) ported and widened it to Zelle deposits that print no sender (LOCAL
  `round3/held/R3-B21_q3b_no_sender_zelle.patch`). The owner decides whether to apply it, and its scope (below).
- **Q13, asked and unanswered:** should Stripe/Intuit instant payouts that print "VISA DIRECT" (counted or verified today) be excluded like the plain debit-card ones? OW01 keeps both as today and records the question in §17.1.
- **Audit round 3's owner decisions** (spec §17.1, "Audit round 3 (2026-10-07): the owner decisions"; each default
  shipped, the owner may change it):
  - R3-86 (R3-B19): the package's revenue gate also reads the package's sums, per currency.
  - R3-21 (R3-B02): Confirm Revenue is refused on a credit matched as a confirmed funder payment's return.
  - R3-73 (R3-B02): answered "Count it once"; the orchestrator's defaults inside the answer, for confirmation.
  - R3-20 (R3-B03): the $500 withholding basis floor.
  - R3-79 (R3-B03): answered "Exclude worded payoffs"; the defaults inside the answer, for confirmation.
  - R3-25 (R3-B05): answered "Add a 'Caught up' line"; the implementer's defaults inside it (§17.1 (24)).
  - R3-84 (R3-B05): same-cents debits under another description are named, never attributed.
  - R3-51 (R3-B20): with Zelle on No, Confirm on a Zelle deposit the Yes rules hold stays one click and names the hold.
  - R3-78 (R3-B21): Q3b's scope (Zelle deposits with no sender in; wallet cash-outs, RTP and push rails out).
  - R3-92 (R3-B08): the page-furniture cut reads credits only until the owner admits the debit half's G7 move.
  - R3-16 (R3-B24): the large-unsourced-deposit flag (information only).
  - R3-62 (R3-B23): the account title in the flat downloads only where it reads as a bank designation.
  - R3-26 (R3-B01): ODKRAOD admitted as an ONDECK alias under the orchestrator's sign-off of the owner's delegations;
    the owner may hold it or make it a potential-lender alias instead.
  - The provenance of the 2026-10-07 answers (R3-73, R3-79, R3-25): they are recorded in the batch briefs' merge notes
    and in spec §19.1, not in `round2/owner/answers.md` (R3-B02's and R3-B03's concern 1); confirm them.
- **History, owner only (a force-push):** R3-07, commits `a93aedc` and `949b9e1` (on `origin/true-revenue`) carry copied
  test values and a single statement's figure; R3-B14 landed the forward fix. R3-B12's review round 1 asked the same
  about `9871cdf`'s spec text (per-statement figures, fixed forward), and R3-B25's review round 1 about `f72e1d9` and
  `e7d9737` (this handoff's round paragraph, §20's round line and a docs pin wrote one row's and one small batch's
  figures; fixed forward; unpushed when found, so whether history keeps them is the orchestrator's call before the
  push and the owner's after it). Rewriting a pushed commit needs the owner's OK. (R3-B15's
  review round 2 left the round-2 spec lines of `5ecb620` with their copy of one statement's figure, as its finding
  allowed; dropped forward by audit round 4, R4-40.) Audit round 4: R4-42, `c2bf1cf` (and `2b684b8`'s generic
  amount) put real premium amounts in tests/test_true_revenue_insurer_work.py, on origin/true-revenue,
  origin/hosting/true-revenue-5.8 and the Fly deploy branch (origin/cursor/intern-testing-host-d911); R4-40, the spec
  commits `70ebdd6`, `d7637c4`, `5ecb620`, `6d2d614`, `f8b5233`, `bffc560`, `efd82a5`, `3705347`, `67bcf6b`,
  `7bc1a24`, `8453ae9`, `2e60915`, `166cbe8`, `b0cf346`, `0d62f87`, `0633d9b`, `5a230b8` and `9871cdf` carry single
  rows' amounts (on the same three branches, most also on the older hosting and fix branches); both fixed forward in
  `16e5558` and `c9d65be` (R4-B01); a rewrite needs the owner's OK (default: no rewrite).
- **Owner items with evidence, no fix:** R3-28 (the daily core-processor template's unread credits counted in True:
  about $47K to $50K of $296K under blocks the MCA standard excludes; the block is stored since R3-B09; §17.1's
  "Readings the owner may convert") and R3-76 (a tax preparer's `TAX REFUND PROC DES:RE DISB` credits excluded as
  refunds; §17.1's unconfirmed rows, P18).
- **R3-75's parser re-orientation** of the TD e-Transfer ties waits inside I41's G7 admission (§17.1's G7 bullet).
- **R3-90 parts B and C** (R2-B05 owner items 1 and 5: the Desjardins holder reader, held, and holder readers for the
  parsers outside R2-B05).
- **R3-89's person-named company holder** (R2-B13 review round 1, RR1.4 item 1, now in §17.1).
- **The residuals the round-3 batches recorded in §17.1:** R3-50's Liberis receiver words, R3-57's and R3-11's I26
  residuals, R3-54's Cherry residual, R3-24's two known shapes, R3-45's arm S question (3), and the batches' own
  "for confirmation" items in their reports (R3-B02's §17.1 (9) defaults, R3-B04's returned-item fee stream, R3-B17's
  two deviations, R3-B18's shared-credit clause and its 32-35-day printout residual).
- **Found (not in scope):** a registry platform's `REBATE`, `INTEREST` or `DIVIDEND` credit reads
  `platform_unconfirmed`, counted (R3-B14's note); on Bank of America's `PMT INFO:` addenda the asset-sale purpose arm
  never reads, so a plain sale there stays counted (R3-B15's note); a lump sum dated the same day as the last regular
  payment gets no "(possible payoff)" note (R3-79's side observation; §17.1 lender payment changes (31)).
- **Each owner batch's open points** (R2-OW01..OW18 reports; R2-OW18's "Still open" defaults) and the 13 underwriter questions' recorded alternatives (§17.1).
- **The owner-convertible calls:** gambling, `payer_text_not_read` (with R3-28's evidence), the review floor, B7's consumer-shaped definition, I61, I37.
- **Held patches (LOCAL `round2/held/` and `round3/held/`, plus round 1's under `audit/`):** the Desjardins holder reader (failed hand review); the two Q3b patches above; the B10 core-processor/TD patches; B6's debit-side spellings and the G7 admissions held back from B6 and B10.
- **The final review's F2 calls, for ratification (LOCAL FINAL-FIX report, "Review round 1 fixes"; spec §17.1 (6)-(8)):** the package's cross-statement return match (pass 4) departs from rule D twice: it also reads a return naming the funder that the funder-name reader files as a lender credit (rule D never reads a lender credit; no corpus row moves through it), and it holds back a credit the revenue side paired only where that partner is dated on or before it (F2(a) makes this necessary). R2-OW18's package payment changes read a payment pass 4 matched as a returned attempt. F1's review decision is not an open item: a statement whose withholding basis is not established, and its package, go to review, as the ruling asked.
- **Pre-existing, on main:** an `analysis/rbc.py` comment (commit 99f480d) quotes a real statement's mailing line. Clean it up in its own change.

## 7. Where everything is (LOCAL, private)

- **Progress ledger:** worktree `.superpowers/sdd/progress.md`.
- **Audit archive:** `C:/Users/GustavoPrietodePaula/lender-research/revenue/audit-archive/`.
  - `audit/`, round 1: `standard.md` (the MCA industry standard), `system_map.md`, `issues_all.json`, `plan.json`, `batches/B01-B12.md`, `reports/`, `final_review.json`.
  - `audit/round2/`: `plan.json`, `cards.json`, `issues/`, `batches/`, `reports/` (`R2-B##-report.md`, `R2-OW##-report.md`, `R2-L01-report.md`, `ACCEPT-report.md`, `FINAL-FIX-report.md`), `owner/` (answers, plan, `batches/R2-OW##.md`), `held/`, `handoff/`, `fixprobes/` (each batch's probes; `accept/` the acceptance's; `final/` the final review's).
  - `audit/round3/`: `survivors_full.json` and `survivors_compact.json` (the 91 verified issues with every vote), `plan_round3.json`, `batches/` (the briefs R3-B01..R3-B25), `reports/` (`R3-B##-report.md`, each with its review rounds' fixes), `probes/` (the audit's and the verifiers' probes), `fixprobes/` (each batch's review probes), `held/` (`R3-B21_q3b_no_sender_zelle.patch`), `handoff/` (the round-3 workflow and its args).
- **Census:** `lender-research/revenue/census/` (s54..s58 snapshots, `g7_allowlist.json`, `lc_c106634.json`, `lc58_final.json`) and `lender-research/revenue/work/plan/`:
  - `accept2/` (the accepted head's re-parsed snapshots `s91_final*.json.gz`, `lc91_final.json`, the frozen trees, the Yes-marked copies);
  - `r2b01/r2_base.json.gz` (round-2 baseline), `b12/s90_head.json.gz` (round-1 final);
  - `final_fix/` (the final review's fix measurements) and `final_fix_r1/` (its review round 1's: the decision moves,
    the dated G7 snapshots and compares, the payment-change moves);
  - `r3b01/` .. `r3b25/` (each round-3 batch's snapshots, compares and probes; `r3b01/base_lc_yes.json` is `1a761de`'s
    re-parsed lender census, with `row_dates`, and `r3b01/admissions_r3b01.json` round 2's admissions plus ONDECK's
    R3-26 sign-off).
- **Corpus cache:** the main checkout's `webapp_data/` (read-only).
- **Tools (in the repo):**
  - `tools/revenue_census.py`: snapshot / compare / sweep, `--reparse`, `--zelle-true-revenue`, guards G1-G20 and G-Z;
  - `tools/lender_census.py`: G7 (legacy basis pinned; declared categories `returned_funder_moves`, `kept_in_count_returned`, `returned_funder_redirects`, the last only where the snapshots' `row_dates` (every row's date; the later snapshot's are read, else the earlier one's) show a payment dated after its return; since round 3 also `returned_funder_represented` (R3-B02) and `lump_sum_payoff_excluded` (R3-B03), each declared row by row; since R3-B01 (R3-22) its exit code alone carries the verdict; payment changes as new outputs);
  - `tools/build_lender_registry.py`: ledger -> registry; never hand-edit the GENERATED block.
- **Spec and plan (in the repo):** the spec above, and `docs/superpowers/plans/2026-09-28-true-revenue.md` (test selections SEL-CLASSIFIER / SEL-REGISTRY / SEL-WEBAPP / SEL-REVENUE; its withholding bullet is superseded by spec §11).
