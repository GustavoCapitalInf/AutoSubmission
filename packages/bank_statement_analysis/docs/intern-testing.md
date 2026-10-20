# Intern testing host

A shared staging URL for intern QA of the bank-statement webapp. This is not
production: there are no per-user accounts, no tenant isolation, and no public
internet default. The intern gate is a **shared HTTP Basic password** that the
server **requires** before it will bind anywhere except loopback.

## What interns can test

| Statement type | Works on this stack? |
|---|---|
| Native-text PDFs of supported banks | Yes, offline |
| Scanned / image PDFs (local Tesseract) | Yes, quality varies |
| Layouts no parser recognises | Refused with the reason (no model is used) |

The app uses no model (owner ruling 2026-10-13): everything runs in the container,
and no statement data leaves it.

Do **not** upload live customer statements to a host you do not control. Use
synthetic or already-authorized intern fixtures.

Run every command below from `packages/bank_statement_analysis/`.

## Fastest path — Docker Compose on a machine you control

Needs Docker Engine + Compose v2, Python is inside the image.

```bash
cp .env.intern.example .env
# edit .env: set WEBAPP_AUTH_PASSWORD to a real shared secret
docker compose up --build
```

Then:

- Local to that machine: `http://127.0.0.1:5000`
- Other machines on the same network: `http://<that-machine-ip>:5000`

Browser prompt: username `intern` (or `WEBAPP_AUTH_USER`), password from `.env`.

`docker compose` **exits before build** if `WEBAPP_AUTH_PASSWORD` is unset.

Probe that does not require the password (no document data):

```bash
curl -sS http://127.0.0.1:5000/healthz
# {"ok":true}
```

Stop:

```bash
docker compose down
```

Job state lives in the `intern-data` volume (`/data` inside the container,
outside the checkout at `/app`, where the app refuses to keep customer data).
Wipe it with `docker compose down -v` when the intern round is over.

Docker names that volume `bankstatementanalysis_intern-data`. Before the
monorepo move, Compose named it after the checkout folder instead. If your
checkout folder had another name, `docker volume ls` shows the old volume as
`<folder>_intern-data`, in lowercase. To keep that job history, set
`COMPOSE_PROJECT_NAME=<folder>` (in lowercase) in `.env`.

## Same machine, no Docker

Install Poppler + Tesseract, then the Python deps, then:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-analysis.txt
WEBAPP_AUTH_PASSWORD='...' ./scripts/run_intern.sh
```

`scripts/run_intern.sh` binds `0.0.0.0:5000` and refuses to start without the
password.

## GitHub Codespaces (one environment per intern)

A `.devcontainer` config is in the repo. Opening the repository in Codespaces
installs Poppler, Tesseract, and the Python deps, and forwards port 5000 as
**org-private** (not public).

In the Codespace terminal, which opens at the repository root:

```bash
cd packages/bank_statement_analysis
WEBAPP_AUTH_PASSWORD='...' ./scripts/run_intern.sh
```

Set port visibility to the organization, not Public. Share the Codespace
forwarded URL plus the password. Still fail-closed: the app will not bind
`0.0.0.0` without `WEBAPP_AUTH_PASSWORD`.

## Putting it on a cloud VM (Render / Railway / Fly / a company box)

1. Build from `packages/bank_statement_analysis/`, the folder that holds the `Dockerfile` (it already binds `0.0.0.0`).
2. Set `WEBAPP_AUTH_PASSWORD` as a **secret**. The process exits on boot if it
   is missing.
3. Map container port `5000`. Put TLS in front (the platform's HTTPS, Caddy,
   or nginx). HTTP Basic is not a substitute for TLS on a public hostname.

The image does **not** copy `Bank Statements/` (see `.dockerignore`). Interns
upload PDFs through the UI; they are stored under `WEBAPP_DATA_DIR`.

## What this is not

- Not D-2b production auth (API keys, per-user accounts, rate limits, tenants).
- Not a reason to send customer statements to a random public tunnel.
- Not a model host: no OCR service or language model is used anywhere.
