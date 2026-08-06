# Wave 1 — Agent B Implementation Prompt: D-1 Durable Persistence

Issued by Ocean (Lead Architect), 2026-08-06. Wave 1 approved as written in
WAVE1_BRIEF.md. You are Agent B. Your first and ONLY authorized task is D-1.
O-1 is NOT authorized until D-1 is completed and reviewed by Ocean.

## Where you work

- Worktree: `C:\Users\GustavoPrietodePaula\OneDrive - Capital Infusion\Desktop\Capital Infusion Projects\bankStatementAnalysis\.claude\worktrees\mt-universal-extraction`
  (the name is historical; ignore it — you are the serving-track agent)
- Branch: `wave1-serving` (already checked out, based on main @ c3030b0, which
  includes Wave 0's D-2a hardening — your baseline `webapp/app.py` already has
  masking, upload validation, and waitress; build on it, never regress it).
- Python for all runs/tests: `C:/Python314/python.exe`.
- Required reading: `...\bankStatementAnalysis\.claude\worktrees\mt-lead\docs\moneythumb-replacement\WAVE1_BRIEF.md` (D-1 task card), current `webapp/jobs.py`, `webapp/app.py`, `webapp/worker.py`, `tests/test_webapp_*.py`.

## Objective

The smallest production-appropriate persistence layer: jobs and results survive
restart; analyst review decisions are recorded with actor, timestamp, and prior
value; packages become durable records. EXPLICITLY OUT OF SCOPE: authentication,
rate limiting, external queues/brokers, cloud deployment, multi-tenancy, and any
change to analysis output content. Do not drift into D-2b or O-1.

## Design (Ocean-decided; deviations require asking first)

- **Engine:** stdlib `sqlite3`. No new dependencies. Single-writer discipline
  matching the existing one-worker queue (state this constraint in a code comment).
  Use WAL mode; handle cross-thread access safely (per-connection-per-call or a
  locked connection — your choice, justified in code).
- **New module `webapp/storage.py`** — schema + all data access:
  - `schema_version` (single row; forward-only migration hook; v1 ships fresh — no
    importer exists because no durable data predates this task; that IS the
    migration/back-compat answer, record it in the module docstring)
  - `documents`: id, content_sha256 (UPPERCASE hex of raw PDF bytes — the exact
    convention of `corpus_gate.sha256_upper`; this definition is shared with the
    upcoming O-1 and must not differ), original filename, byte size, page count,
    uploaded_at (UTC ISO)
  - `jobs`: id (keep uuid4 strings), document ref, status, stage, parse settings
    (force_ocr, parse_mode), parse_model, error, analysis_error, timestamps
    (created/started/finished), result payload = the `report_to_dict` JSON stored
    VERBATIM and UNMASKED as opaque text (masking remains a serve-time concern in
    `app.py` — never bake masking into storage), markdown and html artifacts
  - `packages` + `package_members`: durable package id, optional caller reference,
    created_at, ordered member job ids
  - `review_decisions` (APPEND-ONLY — no UPDATE/DELETE statements on this table):
    id, job id, source_location, decision, actor (free-text until auth exists;
    default "local-analyst"), decided_at (UTC), prior_state JSON
  - `audit_log` (APPEND-ONLY): event type (upload / status_change / review /
    export / package_created), job/package ref, detail JSON, at (UTC)
- **PDF bytes live on DISK, not in SQLite and not in RAM after processing:** a data
  directory holding `<content_sha256>.pdf`. Endpoints that need bytes after
  completion (`/page`, `/render`) load from disk on demand. After a job finishes
  processing, its in-memory `pdf_bytes` is released.
- **Data directory:** env `WEBAPP_DATA_DIR`, default `webapp_data/` at repo root;
  contains the SQLite file + PDF store; gitignored.
- **`webapp/jobs.py`** becomes a thin facade over storage (keep the public surface
  the routes/worker use; in-flight working state may stay in memory, but every
  terminal state and every served artifact must come from storage).
- **`webapp/app.py` wiring:** startup re-hydration (jobs that were queued/processing
  when the process died are re-queued or marked `interrupted` with an explanatory
  error — NEVER silently lost); `/upload` records document + job rows and detects
  nothing new beyond that (duplicate-detection UX is O-1's; storing content_sha256
  now is required); package endpoints mint/accept a durable package id while keeping
  the existing comma-separated-ids form working unchanged; the revenue-review
  endpoint writes a `review_decisions` row (actor, timestamp, prior value) in the
  same operation that mutates the stored analysis; exports/downloads log an
  `audit_log` row.
- **`webapp/worker.py`:** persist every status/stage transition and the final
  result; on completion, write artifacts to storage and release `pdf_bytes`.

## File allowlist (exhaustive — nothing else)

1. `webapp/storage.py` — new
2. `webapp/jobs.py`
3. `webapp/app.py`
4. `webapp/worker.py`
5. `tests/test_webapp_storage.py` — new
6. `tests/test_webapp_jobs.py`, `tests/test_webapp_app.py`, `tests/test_webapp_worker.py`
   — updates only where the in-memory assumption was the thing under test; every
   changed assertion documented in the commit message as an intentional delta
7. `.gitignore` — one line: `webapp_data/`
8. `run.ps1` — ONLY if a data-dir env line is needed

## Protected (do not touch; stop and ask Ocean if you believe you must)

Everything else. Explicitly: ALL of `analysis/` (the stored payload is consumed
verbatim — zero serialization changes), ALL of `ocr/`, `tests/test_webapp_security.py`
(the D-2a contract: it must pass UNMODIFIED — if any change there seems necessary,
stop and ask), `Bank Statements/`, `docs/`, both audit CSVs, `corpus_gate.py` and the
audit scripts, `tests/corpus_cache/`, `conftest.py`, `pytest.ini`, `requirements.txt`
(stdlib only — adding a dependency requires Ocean approval), `.github/`,
`templates/`/`static/` (no UI changes in D-1). If ANY non-allowlisted file seems
necessary, STOP WORK on that thread and put the question in your final report
instead of touching the file.

## Acceptance criteria

1. **Restart survival:** kill and restart the server mid-queue → completed jobs
   serve their full analysis/downloads from storage; queued/processing jobs resume
   or are explicitly `interrupted`; nothing silently lost. (Proven by tests that
   tear down and reopen the store — no real process kill needed.)
2. **Review durability:** decisions survive restart; the full history (actor,
   timestamp, prior value, decision) is queryable; the table is append-only.
3. **Package durability:** a package created before "restart" reproduces the same
   payload by durable id afterwards; comma-id form still works.
4. **Memory:** a completed job holds no `pdf_bytes` in RAM; `/page` and `/render`
   still work (disk-backed).
5. **D-2a intact:** `tests/test_webapp_security.py` passes UNCHANGED — all 70.
6. Full default suite green (`C:/Python314/python.exe -m pytest -q`).
7. Corpus gate green: run `C:/Python314/python.exe corpus_gate.py` once before
   handoff and attach the tail (your change must be invisible to it).
8. No new dependencies; no auth/queue/cloud/tenancy scope creep.

## Required tests

`tests/test_webapp_storage.py`: schema creation + version row; job round-trip
(create → transitions → result → reopen store → served intact); interruption
marking; review append-only + history + restart survival; package round-trip;
PDF disk store round-trip + RAM release; audit-log rows for upload/review/export.
Plus the documented updates to the three existing webapp test files.

## Commit requirements

- Commit ONLY on `wave1-serving`. Small logical commits, messages prefixed `D-1:`.
  End each message with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- DO NOT merge into main. DO NOT push. DO NOT touch any other branch or worktree.
  Ocean performs all merges. (Merge order for the wave is H-2 → D-1 → R-1 → O-1.)

## Handoff requirements (your final report to Ocean)

1. Commit list (hash + subject) and complete file list.
2. Schema summary (tables + key columns) and the storage-module docstring's
   migration/back-compat statement.
3. Test output tails: `tests/test_webapp_storage.py`, `tests/test_webapp_security.py`
   (must be 70 passed, file untouched), full `pytest -q`, corpus-gate tail.
4. Every intentional assertion delta in the three updated test files, with reasons.
5. The exact content_sha256 definition you implemented (for the O-1 handshake).
6. Any deviation from this prompt, any file you wanted but was not allowlisted, and
   any open questions. Do not start O-1 or any other task.
