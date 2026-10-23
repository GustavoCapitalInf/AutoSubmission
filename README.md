# Capital Infusion

Capital Infusion's tools for MCA underwriting and submission. Each project has its own folder, README and
dependencies. Run a project's commands from its folder.

| Folder | Project |
|---|---|
| [`packages/bank_statement_analysis/`](packages/bank_statement_analysis/README.md) | Bank statement analysis: reads business bank statement PDFs and computes what an underwriter needs. It holds the web app, the command-line tools, the tests, and the Docker and Fly.io configuration. |
| [`apps/auto_submission/`](apps/auto_submission/README.md) | Auto-Submission platform (planning). |

CI lives in `.github/workflows/`. The corpus gate runs for pull requests and pushes to `main` that change
`packages/bank_statement_analysis/`, its own workflow file or `.gitattributes`. The Fly.io deploy runs from `main`
after the corpus gate passes for a push to `main`. It builds the image and smoke-tests it before it deploys. You can
also start either one by hand from the Actions tab. A deploy started by hand on another branch only builds and
smoke-tests the image.
