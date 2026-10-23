# Capital Infusion: lender matching

Holds each lender's criteria and details, lets admins edit them in a browser, and answers, for one deal, which
lenders' current criteria the deal meets and why. A deal is its application facts and its bank statement analysis
package. Everything is deterministic Rust: no model is called. It fails closed: a fact that is missing or unproven
never lets a deal pass a check, so such a check is `unproven` and the lender's verdict is `review`.

This package lives in `packages/lender_matching/` of the Capital Infusion monorepo ([root README](../../README.md)).
Run every command below from this folder. The machine API is specified in [`docs/api/v1.md`](docs/api/v1.md).

## How it works

| Part | What it does | Where |
|---|---|---|
| Facts | Each fact is known (a value, or an inclusive interval for a number) or unknown with a reason. The analysis package is fetched and parsed by the server; application values are stated; the industry, default history, home-based status and open lawsuits need a person's confirmation | `src/facts/` |
| Criteria | A rule is `when [conditions] require [condition]` over one typed predicate language. A note is text no rule captures: a `condition` note holds a deal at review, an `info` note never changes a verdict | `src/criteria/` |
| Evaluation | Three-valued: a check passes only when every value the facts allow passes it | `src/criteria/eval.rs` |
| Store | One SQLite database. Every save is a new, immutable lender revision; a save on a stale revision is refused. A match records the revision each verdict read | `src/store/` |
| Info Hub import | Seeds lenders from the "Lenders Module" sheet; rerunnable | `src/info_hub.rs` |
| Server | `/api/v1` for machine clients with named bearer tokens; `/admin` pages for people with accounts | `src/web/` |
| Wire types | The v1 request and response types, shared with clients | `wire/` |

## Run it

Rust stable is the only requirement. SQLite is compiled in and TLS uses rustls, so Windows needs no system library.

```bash
cargo build --release
```

The binary is `target/release/lender-matching` (`.exe` on Windows). Every command takes `--data-dir`, or reads
`LENDER_MATCHING_DATA_DIR`, or uses the OS data directory: `%APPDATA%\CapitalInfusion\LenderMatching` on Windows,
`$XDG_DATA_HOME/lender-matching` on Linux. The commands refuse a data directory inside a git work tree or on a
network share.

**1. Accounts.** Roles are `viewer` (reads everything), `reviewer` (also confirms facts and waives checks on a match)
and `editor` (also edits, activates and pauses lenders and manages industries).

```bash
lender-matching user add sample.editor --role editor        # prompts for a password of 12 characters or more
```

**2. Seed the lenders.** The Info Hub export holds lender contacts, so it stays outside the checkout. The import is
a dry run unless `--apply`, and it prints its report.

```bash
lender-matching import-info-hub "<path to the Info Hub .xlsx>"            # dry run: shows what it would do
lender-matching import-info-hub "<path to the Info Hub .xlsx>" --apply
```

Every imported lender starts as a draft offering MCA, so it matches nothing until an editor activates it. A cell
the import cannot read becomes a `condition` note quoting the cell. A rerun of an unchanged sheet writes only its log
row. A rerun updates a lender whose current revision the import wrote, and leaves alone a lender a person has saved.
A row without a name, or two rows with one key (the Record Id, else the name), refuses `--apply` with nothing
written.

**3. Tokens for machine clients.**

```bash
lender-matching token create auto-submission --scope match --scope read   # prints the token once
lender-matching token revoke auto-submission
```

**4. Serve.**

```bash
export ANALYSIS_API_URL="https://<analysis host>/api/v1"
export ANALYSIS_API_TOKEN="<the analysis app's WEBAPP_API_TOKEN>"
lender-matching serve --bind 127.0.0.1:8080
```

| Variable | Meaning |
|---|---|
| `ANALYSIS_API_URL`, `ANALYSIS_API_TOKEN` | The bank statement analysis API, as in [`apps/auto_submission/README.md`](../../apps/auto_submission/README.md). Set both or neither. Without them, a match that names a package answers 503 `analysis_not_configured`. The URL must be `https://` unless it names this machine |
| `PUBLIC_URL` | The address people open. It must be `https://` unless the server binds a loopback address, and session cookies are `Secure` when it is. A non-loopback bind needs it |

One server process owns the database. Every person and every app is a client of that process, so every copy of a
client sees the same criteria.

## The admin's work

Sign in at `/login`. The lender list shows each lender's status, bucket, revision and attention badges: draft,
condition notes, no rules, no bucket, no submission channel, and an import reading that uses an unconfirmed default.

- **Review and activate** shows the lender's Info Hub row cell by cell beside its rules, with each empty criteria
  column marked "no requirement". Activation refuses a lender with no rules, which would match every deal. Check the
  products there: the import sets MCA only.
- **Edit** has base fields (one rule each that applies to every deal), rule rows, note rows and the profile (bucket,
  products, submission channel, contacts, terms). "Add rule", "Add note" and "Add a rule from this note" re-render
  the form with a blank row. Rules only add requirements: to loosen a base field for one state, clear the field and
  add one rule for that state and one for the others.
- A save records a reason and becomes the next revision. If another editor saved first, the page shows both changes
  and a form on the newer revision; nothing is overwritten. Saving an unchanged form writes nothing.
- **History** shows every revision with its diff.
- On a **match** page, a reviewer can confirm the industry, default history, home-based status and open lawsuits, and
  waive a check or a condition note with a reason. Submitting makes a new match that supersedes the old one, with the
  analysis fetched again and every lender's current revision. A waiver holds only for the lender revision and the
  analysis revision it was given on.

## Readings the owner has not confirmed

These defaults are in the code and the import report labels each use of one.

- Min Dep No. is the worst statement month, read like NSF Per Month. A month's deposits lie between its True revenue
  credits and all its credits, so a minimum between the two is `review`.
- Positions `A-B+` match positions A to B and hold higher positions at review.
- "Accept Default History? No" stays `review` until a person confirms the deal has no default history.
- A stated estimated FICO passes a credit-score minimum, labelled `stated`.
- Negative days of several accounts in one month run from the largest account's count to their sum.
- Time in business counts from the business start month. The application gives only MM/YYYY, so a deal within a
  month of a minimum is `review`.

## Develop

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
cargo run -p lender_matching_wire --example write_contract   # rewrites docs/api/v1.schema.json and the v1.md reference
```

- The integration tests in `tests/` run the built binary. They serve fabricated v1 packages
  (`tests/fixtures/analysis/`) from a fake analysis service, and check those fixtures against the analysis package's
  `docs/api/v1.schema.json`. They build Info Hub workbooks inside the tests and drive the admin pages as a browser
  without JavaScript would.
- API responses in the tests are checked against this package's own `docs/api/v1.schema.json`, and
  `contract_files_are_current` fails when the schema or the reference block of `docs/api/v1.md` is stale.
- `no_model_crate_is_locked` fails when `Cargo.lock` holds a model or ML crate.
- Tests and docs use fabricated names only (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE) and `example` domains.
- A changed verdict for the same inputs bumps `ENGINE_VERSION` (`src/matching.rs`). A changed stored JSON layout bumps
  `RECORD_FORMAT` (`src/criteria/mod.rs`) or `MATCH_FORMAT` (`src/matching.rs`) and needs a reader for the old one,
  since revisions and matches are immutable.
- CI (`.github/workflows/lender-matching.yml`) runs format, lint and tests on Ubuntu and Windows.
