# PHASE 3.1 STEP 6 — THE REAL-STATEMENT JUDGEMENT RUN

Written 2026-09-22 for a fresh session with no prior history on this work.
Scope: two or three real bank statements, once. Nothing else.

## 0. What you are deciding

The pipeline is built, tested and wired into the web app. Everything so far has been proved on
fabricated pages. **The one open question is whether it reads real statements well enough to publish
a result.** You are answering that and nothing else. You are not improving the pipeline, not tuning
prompts, not re-running any benchmark, and not touching the model choice.

Three questions, in priority order:

1. **Do the reviewer's corrections help or hurt?** For every row the reviewer marked `corrected`,
   look at the page and judge whether the change improved the row or damaged it. This is the one
   that can fail. The failure mode is anchoring: a reviewer shown a wrong row may confirm it rather
   than catch it.
2. **Do the four publishable fields survive?** Period start, period end, printed opening balance,
   printed closing balance, and a usable daily ledger. Losing the opening balance alone produces a
   statement with no average daily balance and no NSF count, however perfect the transactions are.
3. **Are descriptions verbatim?** Lender, insurance, POS and revenue detection are all string
   matches. A tidied, truncated or re-worded description is a broken classification.

If the answer to question one is that corrections are not clearly net positive, **say so and stop.**
Reporting that is a successful outcome, not a failed one. Shipping a slower pipeline that is not
better is the failure.

## 1. The data boundary. Read before your first command.

This session handles real customer statements, so this is not boilerplate.

- **Never put document content into tool output.** Not a terminal, not a log, not a printed diff,
  not a test fixture, not a commit. Your transcript leaves the machine and is retained by whoever
  hosts you. A previous session on this work disclosed a customer page exactly this way, by running
  a recursive search that reached an evidence store.
- **Never search, grep, list or iterate** `webapp_data/`, `.claude/`, `discovery_reports/`,
  `Bank Statements/`, or the private artefact root. A recursive search from the repository root
  reaches several of these, so do not run one.
- **Report counts, hashes, field names, reason codes and page numbers. Never values.** To check a
  description survived verbatim, compare hashes or character counts. Do not echo the description.
- Human judgement on actual pages happens in the **offline viewer** described in section 4, in a
  browser, not by printing page text into your session.
- **If you do expose content, stop and say so immediately and precisely** — the command, the paths,
  how many documents and pages, whether anything was written to disk. Do not clean up first. An
  accurate report is worth far more than a tidy tree.

## 2. Preconditions that are Gustavo's, not yours

The pipeline is fenced closed. **Do not set, edit or work around either of these.** If they are not
set, stop and ask him.

| variable | meaning |
|---|---|
| `VISUAL_PAIR_REMOTE_CUSTOMER_DATA_OPT_IN` | must equal `I_AUTHORIZE_CUSTOMER_DOCUMENTS_TO_REMOTE_VISUAL_PAIR` |
| `VISUAL_PAIR_CUSTOMER_DOCUMENT_SHA256_ALLOWLIST` | comma-separated sha256 of **only** the documents in this run |

The allowlist is the important one. It authorises those specific statements and nothing else, and it
is checked on cache hits too. Authorising exactly the documents under test is the whole point, so
never widen it, and never remove it to make something work.

## 3. Where everything is

| item | location |
|---|---|
| branch | `phase3.1-quarantine`, tip `0d04b4a`. Work here. Do not push to `phase3-ceiling`, do not merge into it. |
| private artefact root | outside the checkout, at the path in `VISUAL_PAIR_PRIVATE_ROOT`. Never inside the repository. |
| models | already serving on the rented GPU: proposer on 18013, reviewer on 18022, both loopback only |
| tunnels | `ssh <alias> -L 127.0.0.1:18013:127.0.0.1:18013` and the same for 18022 |
| defaults | `VISUAL_PAIR_PROPOSER_URL=http://127.0.0.1:18013/v1`, `VISUAL_PAIR_REVIEWER_URL=http://127.0.0.1:18022/v1` |
| review policy | `always_review` — leave it there. Whether results may auto-publish is Gustavo's decision, and this run is the evidence for it. |

Connection details for the GPU are in the private annex, not in the repository. Ask Gustavo.

## 4. The run

Two tools already exist. Read their docstrings first; they were written for exactly this task.

**`tools/phase3_pair/check_judgment.py`** — checksum-bound run over exactly two or three real PDFs.
It requires `--manifest`, `--manifest-sha256` and `--source-root`. Output goes to a `judgment-checks`
directory under the external private artefact root. Only page images travel to the models, no remote
files are created, and no web app job is published.

Manifest shape:

```json
{"version": 1, "scope": "real_judgment", "documents": [
  {"id": "J01", "path": "relative/name.pdf", "sha256": "<64 lowercase hex>"}
]}
```

**`tools/phase3_pair/review_judgment.py`** — builds a private offline source viewer for one completed
run. Same manifest, plus `--run-dir`. It renders only those PDFs locally, makes no network request,
invokes no model, publishes nothing. Human verdicts stay in the browser until exported. **This is
where questions one and three get answered**, by a person looking at pages, not by you printing text.

Choose statements that stress the pipeline rather than easy ones. From the shootout, the hard cases
were dense multi-column tables and one document where the reviewer alone agreed on only 82% of
amounts while the proposer alone reached 100%. That last shape is the case the pair exists to fix.

Run the check once. If something is misconfigured, fix the configuration and run again; do not vary
prompts, models or settings between runs to chase a better number. That would be tuning against the
answer.

## 5. What to report

Counts and codes only.

- **Per reason code: the occurrence count and the page it came from.** Presence flags are not
  enough; a previous report gave all ones because reasons are deduplicated.
- **Row states per document**: how many `agreed`, `corrected`, `added`, `rejected`, `unresolved`.
- **Corrections, judged**: of the `corrected` rows, how many improved, how many damaged, how many
  were too unclear to call. This is the headline number.
- **The four publishable fields per document**: captured or not, one line each.
- **Descriptions**: how many sampled, how many byte-identical, how many differed, and for the
  differing ones whether classification would change. Counts, not text.
- **Whether each statement would publish** under the gate, and if not, which reason blocked it.
- Runtime per document and any page that truncated.

Write the detail into the private artefact root. Put counts in your report.

## 6. Stop conditions

Stop and report rather than pushing through, if any of these happen:

- Corrections are not clearly net positive.
- Either fence in section 2 is unset, or you find yourself wanting to widen the allowlist.
- A statement cannot be authorised, or its sha256 does not match the manifest.
- You are about to read, search or print anything under the private artefact root or the directories
  in section 1.
- The gate blocks both statements for reasons that look like pipeline defects rather than genuine
  evidence conflicts. Report the codes; do not start fixing the pipeline in this session.

## 7. Not in scope

No pipeline changes, no prompt tuning, no model comparison, no corpus run, no merge to
`phase3-ceiling`, no setting of the authorisation fences, no publishing a web app job, and no
widening of the allowlist. If this run says the pipeline needs work, that work is a separate session
with a separate brief.
