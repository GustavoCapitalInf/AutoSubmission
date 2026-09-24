"""Build a private offline source viewer for one completed judgment-check run.

Requires the same checksum-bound 2–3-document manifest as check_judgment, an
exact --run-dir containing its summary/document JSON files. --output-dir defaults
to a new judgment-reviews directory under the external private artifact root.
Only those PDFs are rendered locally. No network request, model invocation,
job publication, or metric report is performed. Human verdicts stay in the
browser until the reviewer exports their private JSON file.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import html
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.phase3_pair.check_judgment import _private_output, _write_private, checked_documents
from ocr.private_artifacts import private_artifact_path, validate_private_artifact_path
from uuid import uuid4
from vlm.receipts import canonical_json, need, sha256_bytes, sha256_file, utc_now


def _esc(value: object) -> str:
    if value is None:
        return "<span class='absent'>not supplied</span>"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    return html.escape(str(value), quote=True)


def _json_script(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c").replace(
        ">", "\\u003e").replace("&", "\\u0026")


def _run_file(run_dir: Path, name: str) -> Path:
    path = (run_dir / name).resolve(strict=True)
    need(path.is_relative_to(run_dir) and path.is_file(), "review_document_path_invalid")
    return path


def _verdict_control(key: str, *, page: bool = False) -> str:
    # key is generated from document IDs and integer indices, never model text.
    label = "Page evidence" if page else "Source judgment"
    options = [("", "Not reviewed"), ("source_match", "Matches source"),
               ("source_mismatch", "Does not match source"), ("improved", "Correction improves row"),
               ("damaged", "Correction damages row"), ("unchanged", "No material change"),
               ("uncertain", "Uncertain / needs review")]
    select = "".join(f'<option value="{value}">{text}</option>' for value, text in options)
    return (f'<div class="human-review" data-review-key="{key}"><label>{label}'
            f'<select aria-label="{label}">{select}</select></label>'
            '<label>Review note<textarea rows="2" placeholder="Record what the source page prints."></textarea>'
            '</label></div>')


def _row_html(row: dict, index: int, document_id: str, native: dict | None) -> str:
    original, corrected, effective = (row.get(name) for name in ("original", "corrected", "row"))
    records = [item if isinstance(item, dict) else {} for item in (original, corrected, effective)]
    defaults = ["date", "date_text", "description", "amount", "direction", "balance", "printed_amount", "bbox"]
    fields = defaults + sorted(set().union(*(item.keys() for item in records)) - set(defaults))
    body = []
    for field in fields:
        values = [item.get(field) for item in records]
        changed = original is not None and corrected is not None and values[0] != values[1]
        css = ' class="changed"' if changed else ""
        body.append(f'<tr{css}><th scope="row">{_esc(field)}</th>' +
                    "".join(f'<td><pre>{_esc(value)}</pre></td>' for value in values) + '</tr>')
    controls = _verdict_control(f"{document_id}-r{index}")
    corroboration = (f'<details><summary>Native text corroboration (not ground truth)</summary>'
                     f'<pre>{_esc(native)}</pre></details>') if native else ""
    return (f'<article class="row-card" id="{document_id}-r{index}" data-row-state="{html.escape(str(row.get("state", "unknown")), quote=True)}">'
            f'<h4>Row {index + 1} <span class="badge">{_esc(row.get("state"))}</span></h4>'
            f'<p class="small">Candidate {_esc(row.get("candidate_id"))} · '
            f'locator {_esc(row.get("locator"))} · review verdict {_esc(row.get("review_verdict"))}</p>'
            f'<p>Reason: {_esc(row.get("reason"))}</p>'
            f'<div class="table-scroll"><table><thead><tr><th>Field</th><th>Original candidate</th>'
            '<th>Corrected candidate</th><th>Effective / retained evidence</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            f'<details open><summary>Reviewer observation and every proposed field change</summary>'
            f'<p class="preserve">Observed description: {_esc(row.get("observed_description"))}</p>'
            f'<pre>{_esc(row.get("corrections", []))}</pre></details>'
            f'<details><summary>Complete row evidence, including provenance</summary><pre>{_esc(row)}</pre></details>'
            f'{corroboration}{controls}</article>')


_CSS = """
:root{font-family:system-ui,sans-serif;color:#202b39;background:#f3f5f7;color-scheme:light}
*{box-sizing:border-box}body{margin:0}header{padding:24px 28px;background:#12283e;color:#fff}
h1{font-size:25px;margin:0 0 8px}h2{font-size:21px}h3{font-size:18px}h4{font-size:16px;margin:0 0 8px}
p{line-height:1.5}a{color:#135693}header p{margin:5px 0}.bar{position:sticky;top:0;z-index:5;display:flex;gap:18px;
align-items:center;flex-wrap:wrap;padding:12px 24px;background:#fff;border-bottom:1px solid #cad3dc}
button,select,textarea{font:inherit}button{padding:8px 14px;border:0;border-radius:5px;background:#174d78;color:#fff;cursor:pointer}
select,textarea{border:1px solid #aab9c8;border-radius:4px;padding:6px;background:#fff}select{display:block;width:100%;margin-top:5px}
textarea{display:block;width:100%;margin-top:5px}main{padding:10px 24px 40px}.document{margin:24px 0 40px}
.gate{border-left:5px solid #b14616;background:#fff2e9;padding:12px 16px}.gate.admitted{border-color:#19724e;background:#e8f4ec}
.page{margin-top:20px;background:#fff;border:1px solid #cad3dc;border-radius:7px;padding:14px}
.page>summary{font-weight:650;cursor:pointer}.workbench{display:grid;grid-template-columns:minmax(380px,44%) minmax(0,1fr);gap:18px;margin-top:14px}
figure{margin:0;position:sticky;top:82px;align-self:start}figure img{display:block;width:100%;max-height:calc(100vh - 120px);object-fit:contain;object-position:top;border:1px solid #cad3dc}
figcaption{font-size:13px;margin-bottom:6px}.row-card{border:1px solid #bccbd7;border-radius:5px;padding:12px;margin-bottom:16px;overflow:hidden}
.badge{background:#e9edf2;padding:3px 7px;border-radius:4px;font-size:12px;margin-left:8px}.small,.absent{font-size:12px;color:#607182}
.table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}th,td{border:1px solid #d4dde5;text-align:left;vertical-align:top;padding:6px}
th:first-child{width:15%}thead{background:#edf2f6}.changed{background:#fff3cf}pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.45 ui-monospace,monospace}
details details{margin-top:10px}details details>summary{font-size:13px;cursor:pointer;margin-bottom:7px}.preserve{white-space:pre-wrap;overflow-wrap:anywhere}
.human-review{background:#edf3fb;border-radius:5px;padding:10px;margin-top:12px;display:grid;gap:10px}.human-review label{font-size:13px;font-weight:550}
.empty{padding:20px;color:#607182;background:#f7f9fb}.nav{display:flex;gap:14px;flex-wrap:wrap}.page-evidence{padding:10px;background:#f5f7fa;margin-bottom:14px}
.filter-hidden{display:none}.row-card:target{outline:3px solid #347bae}#save-status{font-size:12px;color:#607182}
@media(max-width:1050px){.workbench{grid-template-columns:1fr}figure{position:static}figure img{max-height:80vh}.bar{position:static}main{padding:10px}}
"""


_SCRIPT = """
'use strict';
const binding = JSON.parse(document.getElementById('review-binding').textContent);
const storageKey = 'phase31-source-review-' + binding.binding_sha256;
const controls = Array.from(document.querySelectorAll('[data-review-key]'));
const status = document.getElementById('save-status');
let saved = {};
try { saved = JSON.parse(localStorage.getItem(storageKey) || '{}'); }
catch (_) { status.textContent = 'Browser storage unavailable; export your verdicts before closing.'; }
for (const control of controls) {
  const prior = saved[control.dataset.reviewKey] || {};
  control.querySelector('select').value = prior.verdict || '';
  control.querySelector('textarea').value = prior.note || '';
}
function collect() {
  return Object.fromEntries(controls.map(control => [control.dataset.reviewKey, {
    verdict: control.querySelector('select').value || null,
    note: control.querySelector('textarea').value
  }]));
}
function save() {
  const values = collect();
  try { localStorage.setItem(storageKey, JSON.stringify(values)); status.textContent = 'Saved in this browser only.'; }
  catch (_) { status.textContent = 'Browser storage unavailable; export to keep your verdicts.'; }
  return values;
}
document.addEventListener('input', save);
document.addEventListener('change', save);
document.getElementById('export').addEventListener('click', () => {
  const values = save();
  const output = {version: 1, purpose: 'human_source_judgment', written_at: new Date().toISOString(),
    binding, items: binding.items.map(item => ({...item, ...(values[item.key] || {verdict:null,note:''})}))};
  const blob = new Blob([JSON.stringify(output, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = 'judgment-verdicts.private.json';
  document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
document.getElementById('row-filter').addEventListener('change', event => {
  const filter = event.target.value;
  for (const row of document.querySelectorAll('[data-row-state]')) {
    row.classList.toggle('filter-hidden', filter !== 'all' && row.dataset.rowState !== filter);
  }
});
"""


def build(args: argparse.Namespace) -> dict:
    from vlm.render import render_pages

    documents = checked_documents(args.manifest, args.manifest_sha256, args.source_root)
    run_dir = validate_private_artifact_path(args.run_dir).resolve(strict=True)
    summary_path = _run_file(run_dir, "summary.private.json")
    summary = json.loads(summary_path.read_bytes())
    need(summary.get("scope") == "real_judgment" and summary.get("manifest_sha256") == args.manifest_sha256,
         "review_run_manifest_mismatch")
    need(summary.get("documents") == len(documents), "review_run_document_count_mismatch")
    selected_ids = {item["id"] for item in documents}
    need({item.get("document_id") for item in summary.get("runs", [])} == selected_ids,
         "review_run_document_ids_mismatch")
    records, bindings = [], []
    # Validate every input and every saved document before rendering anything.
    for item in documents:
        path = _run_file(run_dir, item["id"] + "-document.private.json")
        raw = path.read_bytes()
        doc = json.loads(raw)
        need(doc.get("pdf_sha256") == item["sha256"], "review_document_source_mismatch")
        pair = doc.get("visual_pair")
        need(isinstance(pair, dict) and isinstance(pair.get("row_evidence"), list)
             and isinstance(pair.get("gate"), dict), "review_document_invalid")
        native_name = item["id"] + "-native-check.private.json"
        native = json.loads(_run_file(run_dir, native_name).read_bytes()) if (run_dir / native_name).exists() else {}
        records.append((item, doc, native))
        bindings.append({"document_id": item["id"], "pdf_sha256": item["sha256"],
                         "document_sha256": sha256_bytes(raw),
                         "receipt_sha256": pair.get("receipt_sha256")})
    output = _private_output(
        args.output_dir if args.output_dir is not None
        else private_artifact_path("judgment-reviews", uuid4().hex), args.source_root)
    need(not (output / "review.html").exists(), "review_output_already_exists")
    images = output / "pages"
    images.mkdir(mode=0o700)  # Exclusive: a build never overwrites previous source pages.
    sections, verdict_items = [], []
    totals = {"documents": len(records), "pages": 0, "rows": 0, "held_documents": 0}
    for item, doc, native in records:
        document_id, pair = item["id"], doc["visual_pair"]
        raw = item["path"].read_bytes()
        need(sha256_bytes(raw) == item["sha256"], "review_document_changed")
        pages = render_pages(raw, long_edge=2200)
        need(len(pages) == len(doc.get("pages", [])), "review_page_count_mismatch")
        admitted = pair["gate"].get("admitted") is True
        totals["held_documents"] += not admitted
        totals["pages"] += len(pages)
        totals["rows"] += len(pair["row_evidence"])
        native_rows = {row.get("row_index"): row for row in native.get("rows", [])}
        page_sections, seen_rows = [], set()
        page_notes = {entry.get("page"): entry for entry in pair.get("pages", [])}
        for rendered in pages:
            page = rendered.index + 1
            image_name = f"{document_id}-p{page:03}.jpg"
            image_path = images / image_name
            with image_path.open("xb") as handle:
                handle.write(rendered.jpeg)
            image_path.chmod(0o600)
            rows_html = []
            for index, row in enumerate(pair["row_evidence"]):
                if row.get("page") != page:
                    continue
                seen_rows.add(index)
                rows_html.append(_row_html(row, index, document_id, native_rows.get(index)))
                verdict_items.append({"key": f"{document_id}-r{index}", "document_id": document_id,
                                      "page": page, "row_index": index, "candidate_id": row.get("candidate_id"),
                                      "state": row.get("state"), "kind": "row"})
            fields = [field for field in pair.get("field_evidence", []) if field.get("page") == page]
            page_key = f"{document_id}-p{page}"
            verdict_items.append({"key": page_key, "document_id": document_id, "page": page, "kind": "page"})
            notes = {"page_audit": page_notes.get(page), "printed_field_evidence": fields}
            page_sections.append(
                f'<details class="page" id="{page_key}" open><summary>{document_id} · Page {page} of {len(pages)}'
                f' · {len(rows_html)} row records</summary><div class="workbench"><figure>'
                f'<figcaption>Source page · <a href="pages/{image_name}" target="_blank" rel="noopener">Open full image</a></figcaption>'
                f'<a href="pages/{image_name}" target="_blank" rel="noopener"><img src="pages/{image_name}" '
                f'alt="Source page {page} of {document_id}" loading="lazy"></a></figure><div class="evidence">'
                f'<details class="page-evidence"><summary>Page status and printed statement fields</summary><pre>{_esc(notes)}</pre>'
                f'{_verdict_control(page_key, page=True)}</details>'
                f'{"".join(rows_html) or "<p class=empty>No proposed or added rows on this page. Inspect its printed fields and page status.</p>"}'
                '</div></div></details>')
        unassigned = []
        for index, row in enumerate(pair["row_evidence"]):
            if index not in seen_rows:
                unassigned.append(_row_html(row, index, document_id, native_rows.get(index)))
                verdict_items.append({"key": f"{document_id}-r{index}", "document_id": document_id,
                                      "page": row.get("page"), "row_index": index, "candidate_id": row.get("candidate_id"),
                                      "state": row.get("state"), "kind": "row"})
        if unassigned:
            page_sections.append('<section><h3>Rows without a valid source page</h3>' + "".join(unassigned) + '</section>')
        label = "GATE ADMITTED · offline source review" if admitted else "HELD · not admitted for publication"
        gate_class = "gate admitted" if admitted else "gate"
        sections.append(f'<section class="document" id="{document_id}"><h2>{document_id}</h2>'
                        f'<div class="{gate_class}"><strong>{label}</strong><p>Gate reasons: {_esc(pair["gate"].get("reasons", []))}</p>'
                        '<p>This viewer shows source evidence only. No metrics or customer-facing report are published here.</p></div>'
                        f'<p>Recorded row states: {_esc(pair.get("confidence", {}).get("counts", {}))}</p>'
                        f'{"".join(page_sections)}</section>')
    binding = {"version": 1, "manifest_sha256": args.manifest_sha256,
               "summary_sha256": sha256_file(summary_path), "documents": bindings, "items": verdict_items}
    binding["binding_sha256"] = sha256_bytes(canonical_json(binding).encode())
    script_digest = base64.b64encode(hashlib.sha256(_SCRIPT.encode()).digest()).decode()
    csp = (f"default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src 'sha256-{script_digest}'; "
           "connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'")
    nav = "".join(f'<a href="#{item["id"]}">{item["id"]}</a>' for item in documents)
    html_doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                f'<meta http-equiv="Content-Security-Policy" content="{html.escape(csp, quote=True)}">'
                f'<title>Private statement source review</title><style>{_CSS}</style></head><body>'
                f'<header><h1>Private statement source review</h1><p>{totals["documents"]} documents · {totals["pages"]} pages · '
                f'{totals["rows"]} row records · {totals["held_documents"]} held documents</p>'
                '<p>Compare the source image with both readers. Agreement and native text matches are not proof of correctness.</p></header>'
                f'<div class="bar"><nav class="nav">{nav}</nav><label>Show rows <select id="row-filter">'
                '<option value="all">All states</option>' +
                ''.join(f'<option value="{state}">{state}</option>' for state in ("agreed", "corrected", "added", "rejected", "unresolved")) +
                '</select></label><button id="export" type="button">Export private verdicts</button>'
                '<span id="save-status">Verdicts stay in this browser; export to keep a separate copy.</span></div>'
                f'<main>{"".join(sections)}</main><script id="review-binding" type="application/json">{_json_script(binding)}</script>'
                f'<script>{_SCRIPT}</script></body></html>')
    target = output / "review.html"
    with target.open("x", encoding="utf-8") as handle:
        handle.write(html_doc)
    target.chmod(0o600)
    _write_private(output / "viewer-binding.private.json", {**binding, "created": utc_now(), "counts": totals})
    return {"status": "created", "path": str(target)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path,
                        help="absolute external output directory (default: new private root/judgment-reviews run)")
    args = parser.parse_args(argv)
    try:
        # Rendering/library diagnostics never enter a shared terminal.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = build(args)
    except Exception as exc:
        print(canonical_json({"status": "failed", "error_type": type(exc).__name__}), flush=True)
        return 1
    print(canonical_json(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
