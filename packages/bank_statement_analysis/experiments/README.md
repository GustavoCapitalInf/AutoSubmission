# experiments/ — measurement spikes, never production

Everything under this directory is **investigation code**. It exists to produce
numbers for a design decision and is deliberately not wired into anything:

- no module under `analysis/`, `ocr/`, `webapp/`, `discovery/`, `telemetry/` or
  any top-level entry point imports from `experiments/`, and
  `tests/test_experiments_are_not_wired.py` fails if one ever does;
- nothing here is on the dispatch or pipeline path, and nothing here can affect
  the corpus gate;
- the code is written to be readable and reproducible, not to be robust,
  complete, or maintained. When a spike's question is answered, the spike is
  either promoted (rewritten inside the production tree, with its own review
  and tests) or deleted.

It is committed rather than gitignored on purpose: a measurement nobody else
can reproduce is not evidence, and the reviewer of the design document has to
be able to read what produced its numbers.

## Current spikes

| Path | Question | Document |
|---|---|---|
| `w3_3a/` | Can a layout-agnostic structurer over native/OCR text fill the same `Statement` schema well enough to pass the same reconciliation gate on documents no parser claims? | `docs/moneythumb-replacement/W3_3A_INVESTIGATION.md` |
