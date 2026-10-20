# Capital Infusion

Capital Infusion's tools for MCA underwriting and submission. Each project has its own folder, README and
dependencies. Run a project's commands from its folder.

| Folder | Project |
|---|---|
| [`packages/bank_statement_analysis/`](packages/bank_statement_analysis/README.md) | Bank statement analysis: reads business bank statement PDFs and computes what an underwriter needs. It holds the web app, the command-line tools, the tests, and the Docker and Fly.io configuration. |
| [`apps/auto_submission/`](apps/auto_submission/README.md) | Auto-Submission platform (planning). |

CI lives in `.github/workflows/`. The corpus gate and the Fly.io deploy run only for changes under
`packages/bank_statement_analysis/` or to their own workflow file.
