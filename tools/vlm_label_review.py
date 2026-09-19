"""Local source-check viewer for the label-audit queue (Gustavo, 2026-09-19). Runs ON THE WORKSTATION only.

    python -m tools.vlm_label_review --dataset discovery_reports/train13-logs/p3silver/silver-02 \
        --queue discovery_reports/train13-logs/p3train/audits/label-audit-v1-queue.json \
        --out discovery_reports/train13-logs/p3train/audits/label-audit-v1-review.html

For every queue item the page shows: the source page image, its neighbours, the silver target of the page, the
reader rows whose amount AND date are printed on the page with the page silver assigned each of them to, and for
each such row whether the assigned page prints the amount, the date and a description token and on how many pages
the amount+date pair occurs (repeated amounts and repeated statement sections). Verdicts are recorded in the
browser and exported as label-audit-v1-results.json; nothing here changes the frozen dataset. The HTML holds
customer content and lives in the private tree; this module holds none.
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ocr.config  # noqa: E402,F401
from analysis.payload_shape import payload_accounts  # noqa: E402
from tools.cohort_replay import ColdCache  # noqa: E402
from tools.vlm_ceiling import DEFAULT_TRUTH_CACHE  # noqa: E402
from tools.vlm_label_audit import printed_on, screen  # noqa: E402
from vlm import partitions  # noqa: E402
from vlm.partitions import run_rows  # noqa: E402
from vlm.receipts import utc_now  # noqa: E402
from vlm.render import render_document  # noqa: E402
from vlm.silver import date_forms, desc_tokens, money_forms  # noqa: E402

VERDICTS = ("genuine transaction page, target wrongly empty", "legitimate zero-row page", "rows correctly placed", "rows misplaced", "uncertain")


def _key(r: dict) -> tuple:
    return (str(r.get("date")), float(abs(float(r.get("amount") or 0))), str(r.get("description") or "")[:40])


def row_evidence(tx: dict, page_texts: list[str], assigned: int | None) -> dict:
    forms, dforms, tokens = money_forms(tx.get("amount") or 0), date_forms(str(tx.get("date") or "")), desc_tokens(str(tx.get("description") or ""))
    occurrences = [i for i, t in enumerate(page_texts) if any(f in (t or "") for f in forms) and any(d in (t or "") for d in dforms)]
    text = (page_texts[assigned] if assigned is not None and assigned < len(page_texts) else "") or ""
    return {"assigned_page": assigned, "amount_on_assigned": any(f in text for f in forms), "date_on_assigned": any(d in text for d in dforms),
            "description_on_assigned": (sum(1 for k in tokens if k in text.lower()) >= 1) if tokens else None, "pages_printing_amount_and_date": occurrences}


def _rows_table(rows: list[dict], highlight: set | None = None) -> str:
    if not rows:
        return "<p class='muted'>target has no rows</p>"
    out = ["<table><tr><th>#</th><th>date</th><th>description</th><th>amount</th><th>dir</th><th>balance</th></tr>"]
    for i, r in enumerate(rows):
        cls = " class='hl'" if highlight and _key(r) in highlight else ""
        out.append(f"<tr{cls}><td>{i + 1}</td><td>{html.escape(str(r.get('date')))}</td><td>{html.escape(str(r.get('description') or ''))}</td>"
                   f"<td>{html.escape(str(r.get('amount')))}</td><td>{html.escape(str(r.get('direction') or ''))}</td><td>{html.escape(str(r.get('balance')))}</td></tr>")
    out.append("</table>")
    return "".join(out)


def build(dataset: Path, queue_path: Path, out_path: Path, pages_dir: Path, truth_cache: Path) -> dict:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))["items"]
    private = json.loads((dataset / "manifest.private.json").read_text(encoding="utf-8"))
    members = {d["sha"].upper(): d for d in private["documents"]}
    archive_root = Path(private["archive_root"])
    lines = collections.defaultdict(dict)
    for split in ("train", "validation"):
        for raw in (dataset / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            if raw.strip():
                line = json.loads(raw)
                lines[line["sha"].upper()][int(line["page"])] = line
    rows = run_rows(Path(partitions.DEFAULT_RUN_OF_RECORD))
    cache = ColdCache(truth_cache, Path(partitions.DEFAULT_RUN_OF_RECORD))
    pages_dir.mkdir(parents=True, exist_ok=True)
    sections = []
    stats = collections.Counter()
    try:
        for n, item in enumerate(queue, start=1):
            sha = item["sha"].upper()
            member = members[sha]
            doc_lines = lines[sha]
            text, page_texts = cache.text(sha, rows[sha])
            payload = cache.baseline_payload(text, page_texts) if text else None
            transactions = []
            if payload is not None:
                for account in payload_accounts(payload, surface="label_review"):
                    transactions += (account.get("statement") or {}).get("transactions") or []
            page_texts = page_texts or []
            n_pages = member["pages"]
            rendered = {}
            missing = [p for p in range(n_pages) if not (pages_dir / f"{sha[:12]}-p{p:03d}.jpg").is_file()]
            if missing:
                for p, page in enumerate(render_document((archive_root / member["relative_path"]).read_bytes(), long_edge=1540, quality=90)):
                    (pages_dir / f"{sha[:12]}-p{p:03d}.jpg").write_bytes(page.jpeg)
            for p in range(n_pages):
                rendered[p] = (pages_dir / f"{sha[:12]}-p{p:03d}.jpg").name
            page = int(item["page"])
            silver_page_of = {}
            for p, line in doc_lines.items():
                for r in line["target"]["rows"]:
                    silver_page_of.setdefault(_key(r), p)
            here = [tx for tx in transactions if printed_on(tx, page_texts[page] if page < len(page_texts) else "")]
            evidence = []
            receiving = collections.defaultdict(set)
            for tx in here:
                key = _key(tx)
                assigned = silver_page_of.get(key)
                ev = row_evidence(tx, page_texts, assigned)
                ev.update({"date": tx.get("date"), "description": str(tx.get("description") or ""), "amount": tx.get("amount")})
                evidence.append(ev)
                if assigned is not None and assigned != page:
                    receiving[assigned].add(key)
            looks, money, dates = screen(page_texts[page] if page < len(page_texts) else "")
            target = doc_lines[page]["target"] if page in doc_lines else {"page_role": "?", "rows": []}
            stats[item["stratum"]] += 1
            pages_html = "".join(f"<figure><figcaption>page {p + 1} of {n_pages}{' — THIS PAGE' if p == page else ''}"
                                 f"{' — receives ' + str(len(receiving[p])) + ' of its rows' if p in receiving else ''} · silver role "
                                 f"{html.escape(str(doc_lines[p]['target']['page_role'] if p in doc_lines else '?'))}, "
                                 f"{len(doc_lines[p]['target']['rows']) if p in doc_lines else '?'} rows</figcaption>"
                                 f"<a href='{pages_dir.name}/{rendered[p]}' target='_blank'><img src='{pages_dir.name}/{rendered[p]}' class='{'main' if p == page else 'thumb'}'></a></figure>"
                                 for p in sorted(set([page] + [q for q in (page - 1, page + 1) if 0 <= q < n_pages] + list(receiving))))
            ev_html = "<p class='muted'>no reader row prints both its amount and its date on this page</p>" if not evidence else (
                "<table><tr><th>reader row (date · description · amount)</th><th>silver page</th><th>amount there</th><th>date there</th><th>description there</th><th>pages printing amount+date</th></tr>" +
                "".join(f"<tr class='{'hl' if e['assigned_page'] not in (page, None) else ''}'><td>{html.escape(str(e['date']))} · {html.escape(e['description'][:60])} · {html.escape(str(e['amount']))}</td>"
                        f"<td>{'none' if e['assigned_page'] is None else e['assigned_page'] + 1}</td><td>{e['amount_on_assigned']}</td><td>{e['date_on_assigned']}</td>"
                        f"<td>{e['description_on_assigned']}</td><td>{', '.join(str(p + 1) for p in e['pages_printing_amount_and_date'])}</td></tr>" for e in evidence) + "</table>")
            recv_html = "".join(f"<h4>silver target of page {p + 1} (rows that this page's text also prints are highlighted)</h4>{_rows_table(doc_lines[p]['target']['rows'], receiving[p])}"
                                for p in sorted(receiving) if p in doc_lines)
            sections.append(f"""
<section id='item{n}'>
<h2>Item {n} · {html.escape(item['stratum'])} · {item['split']} · page {page + 1} of {n_pages}</h2>
<p>silver role <b>{html.escape(str(target.get('page_role')))}</b>, {len(target.get('rows') or [])} target rows · audit class <b>{html.escape(item['class'])}</b> ·
text screen: {money} money tokens, {dates} date tokens ({'transaction-like' if looks else 'furniture-like'}) · reader rows printed on this page: {len(here)},
of which assigned to another page: {sum(1 for e in evidence if e['assigned_page'] not in (page, None))} · document {sha[:12]}</p>
<div class='pages'>{pages_html}</div>
<h4>silver target of THIS page</h4>{_rows_table(target.get('rows') or [])}
<h4>reader rows printed on this page and where silver put them</h4>{ev_html}
{recv_html}
<div class='verdict'><b>Verdict</b> {' '.join(f"<label><input type='radio' name='v{n}' value='{html.escape(v)}'> {html.escape(v)}</label>" for v in VERDICTS)}
<br><textarea id='note{n}' placeholder='notes (what the page actually prints; which rows belong here)'></textarea></div>
</section>""")
    finally:
        cache.close()
    doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>Label audit v1 — source check</title>
<style>body{{font-family:system-ui,sans-serif;margin:16px;max-width:1500px}} .pages{{display:flex;flex-wrap:wrap;gap:12px}} figure{{margin:0}} figcaption{{font-size:12px;color:#444}}
img.main{{max-width:760px;border:3px solid #c00}} img.thumb{{max-width:360px;border:1px solid #999}} table{{border-collapse:collapse;font-size:12px;margin:6px 0}} td,th{{border:1px solid #ccc;padding:2px 6px}}
tr.hl td{{background:#fff3b0}} .muted{{color:#777}} section{{border-top:2px solid #333;padding:10px 0 24px}} .verdict{{background:#eef;padding:8px;margin-top:8px}} textarea{{width:100%;height:50px;margin-top:6px}}
#bar{{position:sticky;top:0;background:#fff;padding:8px;border-bottom:1px solid #999}}</style></head><body>
<div id='bar'><b>Label audit v1 — {len(queue)} items</b> · local file, private tree · verdicts stay in this browser until exported ·
<button onclick='exportVerdicts()'>Export verdicts (label-audit-v1-results.json)</button> · silver = reader-derived, not truth · generated {utc_now()}</div>
{''.join(sections)}
<script>
const N={len(queue)}; const items={json.dumps([{"item": i + 1, "sha": it["sha"], "page": it["page"], "split": it["split"], "stratum": it["stratum"], "class": it["class"]} for i, it in enumerate(queue)])};
function load(){{try{{const s=JSON.parse(localStorage.getItem('label-audit-v1')||'{{}}');for(let i=1;i<=N;i++){{const v=s['v'+i];if(v){{const el=document.querySelector(`input[name=v${{i}}][value="${{v}}"]`);if(el)el.checked=true;}}const t=document.getElementById('note'+i);if(t&&s['note'+i])t.value=s['note'+i];}}}}catch(e){{}}}}
function save(){{const s={{}};for(let i=1;i<=N;i++){{const el=document.querySelector(`input[name=v${{i}}]:checked`);if(el)s['v'+i]=el.value;const t=document.getElementById('note'+i);if(t&&t.value)s['note'+i]=t.value;}}try{{localStorage.setItem('label-audit-v1',JSON.stringify(s));}}catch(e){{}}return s;}}
document.addEventListener('change',save);document.addEventListener('input',save);load();
function exportVerdicts(){{const s=save();const out={{written_at:new Date().toISOString(),confirmed_by:'human source check (Gustavo)',items:items.map((it,i)=>Object.assign({{}},it,{{verdict:s['v'+(i+1)]||null,note:s['note'+(i+1)]||''}}))}};
const a=document.createElement('a');a.href='data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(out,null,1));a.download='label-audit-v1-results.json';a.click();}}
</script></body></html>"""
    out_path.write_text(doc, encoding="utf-8")
    return {"items": len(queue), "strata": dict(stats), "out": str(out_path), "pages_dir": str(pages_dir)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_label_review")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pages-dir", default=None, help="default: <out stem>-pages next to the HTML")
    parser.add_argument("--truth-cache", default=str(DEFAULT_TRUTH_CACHE))
    args = parser.parse_args(argv)
    out = Path(args.out)
    pages_dir = Path(args.pages_dir) if args.pages_dir else out.with_name(out.stem.replace("-review", "") + "-pages")
    print(json.dumps(build(Path(args.dataset), Path(args.queue), out, pages_dir, Path(args.truth_cache))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
