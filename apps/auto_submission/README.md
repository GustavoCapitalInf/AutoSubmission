# Auto-Submission platform (planning)

## Analysis results

Auto-Submission gets a deal's statement analysis from the bank statement analysis web app over HTTP only. It never
imports code from `packages/bank_statement_analysis/`. The contract is
[`docs/api/v1.md`](../../packages/bank_statement_analysis/docs/api/v1.md): submit the statement PDFs with
`PUT /api/v1/packages/<package_id>`, then read the package with `GET` until it is ready.

- Set `ANALYSIS_API_URL` to the app's API base URL (`https://<host>/api/v1`) and `ANALYSIS_API_TOKEN` to the token
  the app's operator set as `WEBAPP_API_TOKEN`.
- Save the package id with the application before the first `PUT`, so that a retry or a restart reaches the same
  package.
- Validate the fakes in this app's tests against
  [`v1.schema.json`](../../packages/bank_statement_analysis/docs/api/v1.schema.json). The analysis package's CI does
  not run this folder's tests.
