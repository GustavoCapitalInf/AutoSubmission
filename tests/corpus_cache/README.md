# Committed OCR source artifacts

Source text for the six image-only corpus statements, so the corpus gate runs
offline and deterministically.

103 of the 109 corpus PDFs carry native text, which extracts identically on any
machine. The other 6 have no text layer. Re-OCRing them on every gate run would
make the gate depend on a `tesseract` binary whose output varies with version,
language data, and platform — a corpus audit that changes when a Docker base
image changes proves nothing. Their OCR markdown is therefore produced once and
committed.

## Layout

- `manifest.json` — one entry per artifact: the statement, its corpus-relative
  path, the SHA-256 of the **source PDF**, the artifact file, the SHA-256 of
  the **artifact text**, the page-list file and the SHA-256 of **its** text.
- `ocr/<PDF-SHA256>.md` — the markdown, named after the source PDF's digest.
- `pages/<PDF-SHA256>.json` — the same intake run's page list, one entry per
  rasterised sheet.

Keying by the source digest is what makes the pairing safe: an artifact can
never be served for a document it was not produced from, because a changed PDF
produces a different key and simply has no artifact — which the gate reports as
a failure, not a skip. The artifact digest is verified on every read, so an
edited artifact raises rather than quietly changing what the audit sees.

### Why the page list is committed separately

`analysis/pipeline.py` refuses to recover page structure by splitting the
markdown on its own `--- Page N ---` separators: the separator is an unescaped
text convention and a page's content is OCR output of whatever the document
printed, so a statement printing that line would manufacture a sheet — and one
manufactured unlabelled sheet is exactly what it takes to withdraw a genuine
`missing_declared_statement_page` finding (W3 §PIPEFIX P4b.1). The count has to
come from the object that knows how many sheets were rasterised, so that
object's page list is committed as its own hash-pinned file.

The two halves are one artifact and must agree:
`test_the_committed_page_list_rejoins_to_the_committed_markdown` re-renders each
committed page list through `StatementMarkdown.to_markdown()` and requires the
result to equal the committed markdown byte for byte. Before this existed, the
six image-only statements were analysed offline with no page list at all, so the
page-declaration check fail-closed for them — keeping the flag for want of
evidence rather than because a page was absent.

## These are inputs, not answers

An artifact is transcribed source text. It contains no expected value, no
balance, and no verdict. The truth set is `docs/adb-audit-results.csv` and
`docs/balance-metrics-audit-results.csv`, and the gate reproduces those from
these inputs. Editing an artifact to make a gate failure disappear would be
falsifying evidence, not fixing a test.

## Rebuilding

Requires a local `tesseract`. Never runs in CI.

```bash
python build_corpus_cache.py     # refuses to overwrite on OCR drift
python corpus_gate.py            # must still reproduce both audits exactly
```

If a rebuild reports drift, the local Tesseract does not reproduce the audited
source text. Investigate that before considering `--allow-drift`; the gate
staying green afterwards is the only evidence that new artifacts are faithful.
