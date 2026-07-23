const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const docSelect = document.getElementById("docSelect");
const statusPill = document.getElementById("statusPill");
const dlMd = document.getElementById("dlMd");
const dlHtml = document.getElementById("dlHtml");
const docEl = document.getElementById("doc");
const sourceEl = document.getElementById("source");
const renderedEl = document.getElementById("rendered");
const body = document.body;

// jobId -> {filename, status, error, page_count}
const jobs = {};
let currentJobId = null;
let liveTimer = null;

const boxToggle = document.getElementById("boxToggle");
boxToggle.addEventListener("change", () => {
  docEl.classList.toggle("hide-boxes", !boxToggle.checked);
});

const BOX_COLORS = {
  title: "#ff5c5c", header: "#ffb020", text: "#5c8cff", table: "#23c4a8",
  footer: "#8b8b95", figure: "#c77dff", list: "#9d7bff", image: "#c77dff",
  page_number: "#8b8b95", caption: "#23c4a8",
};
const _BOX_RE = /<\|det\|>(\w+)\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]/g;

// Parse detected-region boxes out of the raw live output, grouped by 0-indexed page.
// Coordinates are 0-1000 per-axis normalized, so they map to CSS percentages directly.
function parseBoxes(liveText) {
  const byPage = {};
  const parts = (liveText || "").split(/---\s*Page\s+(\d+)\s*---/);
  for (let i = 1; i < parts.length; i += 2) {
    const page = parseInt(parts[i], 10) - 1;
    const boxes = [];
    let m;
    _BOX_RE.lastIndex = 0;
    while ((m = _BOX_RE.exec(parts[i + 1] || "")) !== null) {
      boxes.push({ label: m[1], x0: +m[2], y0: +m[3], x1: +m[4], y1: +m[5] });
    }
    byPage[page] = boxes;
  }
  return byPage;
}

function drawBoxes(byPage) {
  for (const page in byPage) {
    const overlay = document.getElementById(`boxes-${page}`);
    if (!overlay) continue;
    overlay.innerHTML = byPage[page].map((b) => {
      const color = BOX_COLORS[b.label] || "#5c8cff";
      const left = b.x0 / 10, top = b.y0 / 10;
      const w = (b.x1 - b.x0) / 10, h = (b.y1 - b.y0) / 10;
      return `<div class="box" style="left:${left}%;top:${top}%;width:${w}%;height:${h}%;` +
             `border-color:${color}"><span class="box-label" style="background:${color}">` +
             `${b.label}</span></div>`;
    }).join("");
  }
}

uploadBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  uploadFiles(fileInput.files);
  fileInput.value = "";
});

["dragover", "dragenter"].forEach((ev) =>
  window.addEventListener(ev, (e) => { e.preventDefault(); body.classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  window.addEventListener(ev, (e) => {
    e.preventDefault();
    if (ev === "drop" && e.dataTransfer) uploadFiles(e.dataTransfer.files);
    if (ev === "drop") body.classList.remove("drag");
  })
);

docSelect.addEventListener("change", () => selectDoc(docSelect.value));

function uploadFiles(fileList) {
  if (!fileList || !fileList.length) return;
  const form = new FormData();
  for (const f of fileList) form.append("files", f);
  fetch("/upload", { method: "POST", body: form })
    .then((r) => r.json())
    .then((data) => {
      let firstNew = null;
      for (const job of data.jobs) {
        jobs[job.id] = { filename: job.filename, status: "queued", page_count: job.page_count };
        addOption(job.id, job.filename, "queued");
        pollJob(job.id);
        if (firstNew === null) firstNew = job.id;
      }
      if (firstNew && currentJobId === null) {
        docSelect.value = firstNew;
        selectDoc(firstNew);
      }
    });
}

function addOption(jobId, filename, status) {
  const placeholder = docSelect.querySelector('option[value=""]');
  if (placeholder) placeholder.remove();
  const opt = document.createElement("option");
  opt.value = jobId;
  opt.textContent = `${filename}  (${status})`;
  docSelect.appendChild(opt);
}

function pollJob(jobId) {
  const interval = setInterval(() => {
    fetch(`/status/${jobId}`)
      .then((r) => r.json())
      .then((data) => {
        const job = jobs[jobId];
        if (!job) return;
        const changed = job.status !== data.status;
        job.status = data.status;
        job.error = data.error;
        if (data.page_count) job.page_count = data.page_count;

        const opt = docSelect.querySelector(`option[value="${jobId}"]`);
        if (opt) opt.textContent = `${job.filename}  (${data.status})`;

        if (jobId === currentJobId && changed) selectDoc(jobId);
        if (data.status === "done" || data.status === "error") clearInterval(interval);
      });
  }, 2000);
}

function stopLivePoll() {
  if (liveTimer) { clearInterval(liveTimer); liveTimer = null; }
}

// Poll the live buffer fast so the raw OCR output streams into the middle panel.
function startLivePoll(jobId) {
  stopLivePoll();
  liveTimer = setInterval(() => {
    if (currentJobId !== jobId) { stopLivePoll(); return; }
    fetch(`/live/${jobId}`)
      .then((r) => r.json())
      .then((data) => {
        const job = jobs[jobId];
        if (!job) return;
        job.status = data.status;
        job.error = data.error;
        if (data.status === "processing" || data.status === "queued") {
          const mid = sourceEl.parentElement;
          const atBottom = mid.scrollTop + mid.clientHeight >= mid.scrollHeight - 40;
          sourceEl.textContent = data.live_text || "Reading…";
          if (atBottom) mid.scrollTop = mid.scrollHeight;  // follow the stream
          drawBoxes(parseBoxes(data.live_text));           // boxes appear as detected
        } else {
          stopLivePoll();
          selectDoc(jobId);  // done/error -> load final panels
        }
      });
  }, 400);
}

function refreshStatusUI(jobId) {
  const job = jobs[jobId];
  if (!job) return;
  statusPill.textContent = job.status;
  statusPill.className = `pill ${job.status}`;
  const done = job.status === "done";
  dlMd.disabled = !done;
  dlHtml.disabled = !done;
  dlMd.onclick = done ? () => (window.location = `/download/${jobId}/md`) : null;
  dlHtml.onclick = done ? () => (window.location = `/download/${jobId}/html`) : null;
}

function selectDoc(jobId) {
  const job = jobs[jobId];
  if (!jobId || !job) return;
  stopLivePoll();
  currentJobId = jobId;
  if (docSelect.value !== jobId) docSelect.value = jobId;
  refreshStatusUI(jobId);

  // Left panel: original page images + region-overlay containers.
  docEl.innerHTML = "";
  if (job.page_count > 0) {
    for (let n = 0; n < job.page_count; n++) {
      const wrap = document.createElement("div");
      wrap.className = "page-wrap";
      wrap.innerHTML =
        `<img src="/page/${jobId}/${n}" alt="Page ${n + 1}">` +
        `<div class="overlay" id="boxes-${n}"></div>`;
      docEl.appendChild(wrap);
    }
  } else {
    docEl.innerHTML = '<div class="placeholder">No pages.</div>';
  }

  // Draw whatever boxes exist so far (works for done, and seeds the live view).
  fetch(`/live/${jobId}`).then((r) => r.json()).then((data) => {
    if (currentJobId === jobId) drawBoxes(parseBoxes(data.live_text));
  }).catch(() => {});

  if (job.status === "done") {
    fetch(`/markdown/${jobId}`)
      .then((r) => r.text())
      .then((md) => { if (currentJobId === jobId) sourceEl.textContent = md; });
    renderedEl.src = `/result/${jobId}`;
  } else if (job.status === "error") {
    sourceEl.textContent = "Error: " + (job.error || "unknown");
    renderedEl.removeAttribute("src");
  } else {
    // Queued/processing: stream the raw OCR output live into the middle panel.
    sourceEl.textContent = "Reading…";
    renderedEl.removeAttribute("src");
    startLivePoll(jobId);
  }
}
