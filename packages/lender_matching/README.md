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
| Application PDFs | Reads merchant application PDFs into typed field readings, with pdfium in a child process | `application/` |

## Run it

Rust stable is the only requirement. SQLite is compiled in and TLS uses rustls, so Windows needs no system library.
Only `applications evaluate` also needs pdfium (see [Get pdfium](#get-pdfium)).

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
condition notes, no rules, no bucket and no submission channel.

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

## Readings

The owner confirmed these readings of the sheet and the application.

- A stated estimated FICO passes a credit-score minimum, labelled `stated`.
- Min Dep No. is the worst statement month, read like NSF Per Month. A month's deposits lie between its True revenue
  credits and all its credits, so a minimum between the two is `review`.
- Positions `A+` and `A-B+` admit positions from A to 7, or to the cell's last number when that is higher. A higher
  position fails the check. An explicit range such as `2-8` admits only its own positions.
- "Accept Default History? No" stays `review` until a person confirms the deal has no default history.
- Time in business counts from the business start month. The application gives only MM/YYYY, so a deal within a
  month of a minimum is `review`.
- A funding cap or minimum decides the match. An editor writes it as a Requested amount rule, guarded by a state or
  industry when the cap applies to one, so a deal asking for more than a cap, or less than a minimum, is `no_match`.
  A deal without a requested amount is `review` for that lender. The import leaves these limits in the Additional
  Info condition note, which holds the deal at review until the rule replaces it.

Negative days of several accounts in one month run from the largest account's count to their sum, since one day can
be negative in more than one account.

## Read application PDFs

The `application/` member (crate `lender_matching_application`) reads Capital Infusion's merchant application PDFs
into typed field readings. It reaches no store, network or log. Only `application/src/pdf.rs` calls pdfium, and
`lender-matching` runs it in a child process (the hidden `pdf-worker` command), so a crash or a hang in pdfium stops
only that process.

| Part | What it does | Where (`application/src/`) |
|---|---|---|
| Field catalog | `FieldId` names the 55 fields: business, principal owner, secondary owner, property and the two signature dates. `FieldId::spec` gives each field's kind, whether it is required, and whether it is identity data or derived | `fields.rs` |
| Value grammar | `FieldId::read` turns a field's text into a typed value or a closed refusal: `format`, `ambiguous`, `out_of_range`, `not_in_list`, `mark_unclear`, `undecodable` or `no_signing_date` | `values.rs` |
| Page model | Each page's characters with font, size and box, in points from the top-left of the displayed page | `page.rs` |
| Template | The form's known layouts (`word`, `pdfescape`) as static data: each one's label set, sections and sentinel offsets, and the label fonts | `template.rs` |
| Extraction | Classifies page 1, binds the labels, cuts the value regions and reads each field | `extract.rs` |
| Certificate | Reads the envelope id, the completion day and the signers under Signer Events, never the originator | `certificate.rs` |
| Worker | Supervises the pdfium process: a timeout per document, and a new process after a crash or a timeout | `worker.rs` |
| Tally | The counts `applications evaluate` prints | `tally.rs` |

A PDF reads by these rules:

- Page 1 decides the document. The RECEIVABLES PURCHASE AGREEMENT heading refuses it as a contract. A page without
  the form's headings is other paperwork, or a suspected scan when one image covers 80% of it or it holds fewer than
  300 characters. A page with both kinds of heading, a scan-like page, or labels that fit no single known layout
  sends the document to manual entry.
- Each layout prints its own label set, and the document must fit exactly one: its labels bind, and its sentinel
  labels sit within 3 pt of where pdfium measured them. The PDFescape version prints Email on the Phone row, and
  Type of Entity as a row of printed choices (Corporation, LLC, Other). A mark beside one choice picks it, a
  description typed on the row is read as the entity, and an unclear mark is refused. Its sales rep header above
  BUSINESS INFORMATION and its Fax and Email footer under the signature lines are form text, outside the form area.
- Labels are found by their printed text in Calibri or AdobeDevanagari, character by character, so a value typed into
  the label's own run splits after the label. Characters of other fonts are skipped while a label is matched, so a
  value that runs over the label to its right does not hide it. In each section the labels bind in reading order. A label that two
  equally long matchings place differently is out of place, never "the nearer one".
- A field's region lies on its label's row, with tops within −10 to +8 pt of the label's top, from the label's end
  to the next label on the row. Prior/Current Loan Company also takes the next line, which ends above the band of
  the next label row, so the two never share a character.
- Values are read as runs: characters consecutive in the PDF's content, in one font and size, on one baseline, with
  small gaps. A run belongs to the region that holds its first character, even where it runs on past the next label,
  and the next field does not get its characters.
- A field is in doubt, and gets no value, when its label's text occurs more often in its section than the form
  prints it, when other label text lies in its runs, or when one of its runs starts in two regions. A run inside the
  form that starts in no region is unplaced as a whole, whatever its font. The band between the last field row and
  the signature lines holds the certification paragraph and is not checked.
- A state is a postal code, with or without a trailing dot, or a full US, territory or Canadian province name in any
  case. A phone is 10 digits, or 11 with a leading 1, between spaces and `- . ( ) / =`. An SSN and a tax ID are 9
  digits in any grouping by spaces, `-` or `.`; the grouping only decides how they are written back. A Canadian
  business number may hold spaces. A zip code may end in a stray backtick, period or comma. The entity dropdown's
  texts read as the matcher's kinds: LLP, GP and LP are partnerships, PC is a corporation, and "S CORPORATION
  (C CORP)" is refused as ambiguous.
- Dates read month first. For a business outside the US, or one whose state did not read, a date whose month and
  day could swap is refused. The signing day is the certificate's completion day, else the PDF's creation date. A
  business or signature date after it, an owner outside 18 to 100 years old on it, and a six-digit date that reads
  both as MMYYYY and as MMDDYY are refused.
- Amounts keep their cents and their denomination: `USD`, `CAD`, a bare `$`, or none. `N/A` means nothing applies,
  except on the four history questions (open judgements, bankruptcy, tax liens, seasonal), where it means no.

### Get pdfium

`pdfium.lock` pins the pdfium build `chromium/7881` from bblanchon/pdfium-binaries, with one archive URL and SHA-256
per target. CI downloads the archive, checks its SHA-256, and sets `PDFIUM_LIBRARY` and `PDFIUM_REQUIRED=1`. To get
the Linux build:

```bash
gh release download chromium/7881 --repo bblanchon/pdfium-binaries --pattern pdfium-linux-x64.tgz --dir "<scratch folder>"
cd "<scratch folder>"
sha256sum --check <<<"1470e21b8b4a3b4ad7f85684e2da11d94f3b69a86d81dee11b9b6709d927ac1d  pdfium-linux-x64.tgz"
tar -xzf pdfium-linux-x64.tgz
export PDFIUM_LIBRARY="$PWD/lib/libpdfium.so"
```

On Windows the library is `bin\pdfium.dll` in `pdfium-win-x64.tgz`. `PDFIUM_LIBRARY` is an absolute path, and the
service looks nowhere else.

### Measure the parser on a folder

```bash
export PDFIUM_LIBRARY="<absolute path to libpdfium.so or pdfium.dll>"
lender-matching applications evaluate "<folder of application PDFs>" --offsets --shapes --json "<report file>"
```

The command reads every `.pdf` file under the folder in sorted order and keeps nothing. It prints counts and closed
reasons only: documents by kind, failures, layouts, where the signing day came from, certificate counts, the signer
check, unplaced text by the label before it, and for each field how often it was read, blank, not applicable,
refused, unlocated or in doubt. It never prints a value, a file name or a path inside the folder.

- `--offsets` adds, for each sentinel label, a histogram of its offset from the BUSINESS INFORMATION heading in
  whole points. Use it to measure a new layout.
- `--shapes` adds the shapes of refused structured values, with digits as `9` and letters as `A` or `a`. A shape
  seen fewer than 3 times for a field counts as `other`. Names, emails and other free text get no shape.
- `--json` also writes the counts to the file as JSON.

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
- Tests that need pdfium read `PDFIUM_LIBRARY`. Without it they print why they skip, and with `PDFIUM_REQUIRED=1`
  they fail. They read PDFs that `application/tests/support/` writes with `pdf-writer`; the service's tests include
  the same files.
- A change that makes the same PDF read differently bumps `PARSER_VERSION` (`application/src/lib.rs`).
- Tests and docs use fabricated names only (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE) and `example` domains.
- A changed verdict for the same inputs bumps `ENGINE_VERSION` (`src/matching.rs`). A changed stored JSON layout bumps
  `RECORD_FORMAT` (`src/criteria/mod.rs`) or `MATCH_FORMAT` (`src/matching.rs`) and needs a reader for the old one,
  since revisions and matches are immutable.
- CI (`.github/workflows/lender-matching.yml`) runs format, lint and tests on Ubuntu and Windows.
