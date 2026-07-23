from __future__ import annotations
import io
import threading
from flask import Flask, request, jsonify, render_template, Response, abort

from ocr.rasterize import pdf_page_count, rasterize_page
from .jobs import JobStore
from .worker import run_job

app = Flask(__name__)
store = JobStore()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no files uploaded"}), 400

    jobs = []
    for f in files:
        pdf_bytes = f.read()
        job = store.create(f.filename)
        job.pdf_bytes = pdf_bytes
        try:
            job.page_count = pdf_page_count(pdf_bytes)
        except Exception:
            job.page_count = 0
        thread = threading.Thread(
            target=run_job, args=(job.id, pdf_bytes, f.filename, store), daemon=True,
        )
        thread.start()
        jobs.append({"id": job.id, "filename": job.filename, "page_count": job.page_count})
    return jsonify({"jobs": jobs})


@app.route("/status/<job_id>")
def status(job_id):
    job = store.get(job_id)
    if job is None:
        abort(404)
    return jsonify({"status": job.status, "error": job.error, "page_count": job.page_count})


@app.route("/markdown/<job_id>")
def markdown(job_id):
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    return Response(job.markdown, mimetype="text/plain; charset=utf-8")


@app.route("/page/<job_id>/<int:n>")
def page(job_id, n):
    job = store.get(job_id)
    if job is None or job.pdf_bytes is None or n < 0 or n >= job.page_count:
        abort(404)
    image = rasterize_page(job.pdf_bytes, n, dpi=100)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png")


@app.route("/result/<job_id>")
def result(job_id):
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    return job.html


@app.route("/download/<job_id>/<fmt>")
def download(job_id, fmt):
    if fmt not in ("md", "html"):
        abort(400)
    job = store.get(job_id)
    if job is None or job.status != "done":
        abort(404)
    content = job.markdown if fmt == "md" else job.html
    mimetype = "text/markdown" if fmt == "md" else "text/html"
    base_name = job.filename.rsplit(".", 1)[0]
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{base_name}.{fmt}"'},
    )


if __name__ == "__main__":
    app.run(debug=True)
