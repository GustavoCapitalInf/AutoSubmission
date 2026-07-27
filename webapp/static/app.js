const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const docSelect = document.getElementById("docSelect");
const statusPill = document.getElementById("statusPill");
const modePill = document.getElementById("modePill");
const dlMd = document.getElementById("dlMd");
const dlHtml = document.getElementById("dlHtml");
const dlJson = document.getElementById("dlJson");
const docEl = document.getElementById("doc");
const sourceEl = document.getElementById("source");
const renderedEl = document.getElementById("rendered");
const analysisEl = document.getElementById("analysis");
const body = document.body;

const jobs = {};
let currentJobId = null;
let liveTimer = null;
let renderTimer = null;
let renderReady = false;
let skeletonHtml = null;

const boxToggle = document.getElementById("boxToggle");
boxToggle.addEventListener("change", () => {
  docEl.classList.toggle("hide-boxes", !boxToggle.checked);
});

const renderBoxToggle = document.getElementById("renderBoxToggle");
function applyRenderBoxes() {
  const doc = renderedEl.contentDocument;
  if (doc && doc.body) doc.body.classList.toggle("hide-regions", !renderBoxToggle.checked);
}
renderBoxToggle.addEventListener("change", applyRenderBoxes);
const forceOcrToggle = document.getElementById("forceOcrToggle");

const BOX_COLORS = {
  title: "#ff5c5c", header: "#ffb020", text: "#5c8cff", table: "#23c4a8",
  footer: "#8b8b95", figure: "#c77dff", list: "#9d7bff", image: "#c77dff",
  page_number: "#8b8b95", caption: "#23c4a8",
};
const _BOX_RE = /<\|det\|>(\w+)\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]/g;

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
             `border-color:${color};background:${color}22">` +
             `<span class="box-label" style="background:${color}">${b.label}</span></div>`;
    }).join("");
  }
}

let lastActivePage = -1;
function followActivePage(byPage) {
  const pages = Object.keys(byPage)
    .map(Number)
    .filter((p) => byPage[p] && byPage[p].length > 0);
  if (!pages.length) return;
  const active = Math.max(...pages);
  if (active > lastActivePage) {
    lastActivePage = active;
    const overlay = document.getElementById(`boxes-${active}`);
    const wrap = overlay && overlay.parentElement;
    if (wrap) wrap.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatMoney(value, currency = "USD") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(value));
  } catch {
    return `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "N/A";
  return Number(value).toLocaleString();
}

function pct(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return `${Math.round(Number(value) * 100)}%`;
}

function labelize(value) {
  return escapeHtml(String(value || "N/A").replace(/_/g, " "));
}

function metric(label, value, sub = "") {
  return `<div class="metric-card"><div class="metric-label">${escapeHtml(label)}</div>` +
         `<div class="metric-value">${escapeHtml(value)}</div>` +
         (sub ? `<div class="metric-sub">${escapeHtml(sub)}</div>` : "") +
         `</div>`;
}

function kv(label, value) {
  return `<div class="key">${escapeHtml(label)}</div><div class="value">${escapeHtml(value ?? "N/A")}</div>`;
}

function renderAnalysisPayload(payload) {
  if (!analysisEl) return;
  const report = payload && payload.analysis;
  if (!report) {
    const err = payload && payload.analysis_error;
    analysisEl.innerHTML = `<div class="analysis-banner error">` +
      `<div class="quality-line"><div class="quality-title">Analysis unavailable</div>` +
      `<div class="quality-chip">error</div></div>` +
      `<div class="metric-sub">${escapeHtml(err || "No analysis report was generated.")}</div></div>`;
    if (dlJson) dlJson.disabled = true;
    return;
  }

  const s = report.statement || {};
  const m = report.metrics || {};
  const r = report.reconciliation || {};
  const q = report.quality || {};
  const d = report.detection || {};
  const currency = s.currency || "USD";
  const useClass = q.corporate_use || "review";
  const knownFunders = d.known_funders || [];
  const recurring = d.recurring_debits || [];
  const issues = r.issues || [];
  const notes = m.notes || [];
  const isApproved = q.corporate_use === "approved" && q.transaction_detail_reliable;
  const headline = isApproved
    ? "Corporate approved"
    : q.corporate_use === "summary_only"
      ? "Summary only - not transaction approved"
      : labelize(q.level);
  const detailLine = isApproved
    ? "Transaction-level detail reconciled. Bank summary totals reconciled."
    : `Transaction detail: ${q.transaction_detail_reliable ? "reliable" : "not approved"}; ` +
      `bank summary totals: ${q.summary_totals_reliable ? "reliable" : "review"}`;

  const issueItems = issues.slice(0, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join("") ||
    `<li>No reconciliation issues.</li>`;
  const noteItems = notes.slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const funderItems = knownFunders.slice(0, 5).map((f) =>
    `<li><strong>${escapeHtml(f.funder)}</strong> - ${formatMoney(f.total_debited, currency)} debited ` +
    `across ${formatNumber((f.transactions || []).length)} matches</li>`
  ).join("");
  const recurringItems = recurring.slice(0, 5).map((item) =>
    `<li><strong>${formatMoney(item.amount, currency)} x${formatNumber(item.count)}</strong> ` +
    `${escapeHtml(item.cadence)} - ${escapeHtml(item.description_key)}</li>`
  ).join("");
  const detectionHtml = (funderItems || recurringItems)
    ? `${funderItems}${recurringItems}`
    : `<li>No known funders or regular recurring debits detected.</li>`;

  analysisEl.innerHTML =
    `<div class="analysis-banner ${escapeHtml(useClass)}">` +
      `<div class="quality-line"><div class="quality-title">${headline}</div>` +
      `<div class="quality-chip">${labelize(q.corporate_use)}</div></div>` +
      `<div class="metric-sub">${detailLine}</div>` +
    `</div>` +
    `<div class="meta-grid">` +
      metric("Average balance", formatMoney(m.average_balance, currency), m.average_balance_source || "") +
      metric("True revenue", formatMoney(m.true_revenue, currency), `lender credits ${formatMoney(m.lender_credits, currency)}`) +
      metric("Cash flow", formatMoney(m.cash_flow, currency), "credits minus debits") +
      metric("Lender debits", formatMoney(m.lender_debits, currency), `monthly ${formatMoney(m.monthly_lender_debits, currency)} / withholding ${m.withholding_rate ?? "N/A"}%`) +
      metric("NSF / returns", formatNumber(m.effective_nsf_count), m.nsf_source || "line_items") +
      metric("POS / loans", `${formatNumber(m.pos_count)} / ${formatNumber(m.loan_count)}`, "matched transaction counts") +
      metric("Deposits", formatMoney(m.effective_total_deposits, currency), `${formatNumber(m.effective_num_deposits)} items - ${m.deposits_source}`) +
      metric("Withdrawals", formatMoney(m.effective_total_withdrawals, currency), `${formatNumber(m.effective_num_withdrawals)} items - ${m.withdrawals_source}`) +
      metric("Min balance", formatMoney(m.min_balance, currency), `${formatNumber(m.negative_days)} negative days`) +
      metric("Transactions", formatNumber((s.transactions || []).length), `credit ${pct(r.credit_coverage)} / debit ${pct(r.debit_coverage)}`) +
    `</div>` +
    `<div class="analysis-section"><div class="section-title">Statement</div><div class="kv">` +
      kv("Bank", s.bank) +
      kv("Account", s.account_number) +
      kv("Account name", s.account_name) +
      kv("Period", `${s.period_start || "N/A"} to ${s.period_end || "N/A"}`) +
      kv("Beginning", formatMoney(s.beginning_balance, currency)) +
      kv("Ending", formatMoney(s.ending_balance, currency)) +
    `</div></div>` +
    `<div class="analysis-section"><div class="section-title">Reconciliation</div><ul class="issue-list">${issueItems}</ul></div>` +
    `<div class="analysis-section"><div class="section-title">Detections</div><ul class="detection-list">${detectionHtml}</ul></div>` +
    (noteItems ? `<div class="analysis-section"><div class="section-title">Notes</div><ul class="issue-list">${noteItems}</ul></div>` : "");
  if (dlJson) dlJson.disabled = false;
}

function loadAnalysis(jobId) {
  if (!analysisEl) return;
  analysisEl.innerHTML = '<div class="analysis-empty">Analyzing statement...</div>';
  fetch(`/analysis/${jobId}`)
    .then((r) => r.json())
    .then((payload) => {
      if (currentJobId === jobId) renderAnalysisPayload(payload);
    })
    .catch(() => {
      if (currentJobId === jobId) {
        analysisEl.innerHTML = '<div class="analysis-empty">Analysis unavailable.</div>';
        if (dlJson) dlJson.disabled = true;
      }
    });
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
  statusPill.textContent = "uploading";
  statusPill.className = "pill processing";
  const form = new FormData();
  for (const f of fileList) form.append("files", f);
  if (forceOcrToggle && forceOcrToggle.checked) form.append("force_ocr", "1");
  fetch("/upload", { method: "POST", body: form })
    .then((r) => {
      if (!r.ok) throw new Error(`upload failed (${r.status})`);
      return r.json();
    })
    .then((data) => {
      if (!data.jobs || !data.jobs.length) throw new Error(data.error || "upload returned no jobs");
      let firstNew = null;
      for (const job of data.jobs) {
        jobs[job.id] = {
          filename: job.filename,
          status: "queued",
          page_count: job.page_count,
          force_ocr: job.force_ocr,
          parse_model: null,
        };
        addOption(job.id, job.filename, "queued");
        pollJob(job.id);
        if (firstNew === null) firstNew = job.id;
      }
      if (firstNew && currentJobId === null) {
        docSelect.value = firstNew;
        selectDoc(firstNew);
      }
    })
    .catch((err) => {
      statusPill.textContent = "upload error";
      statusPill.className = "pill error";
      sourceEl.textContent = err.message || String(err);
      if (analysisEl) analysisEl.innerHTML = '<div class="analysis-empty">Upload failed.</div>';
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
        job.stage = data.stage;
        job.error = data.error;
        job.analysis_ready = data.analysis_ready;
        job.analysis_error = data.analysis_error;
        job.parse_model = data.parse_model;
        job.force_ocr = data.force_ocr;
        if (data.page_count) job.page_count = data.page_count;

        const opt = docSelect.querySelector(`option[value="${jobId}"]`);
        if (opt) opt.textContent = `${job.filename}  (${data.status})`;

        if (jobId === currentJobId) {
          refreshStatusUI(jobId);
          if (changed) selectDoc(jobId);
        }
        if (data.status === "done" || data.status === "error") clearInterval(interval);
      });
  }, 2000);
}

function stopLivePoll() {
  if (liveTimer) { clearInterval(liveTimer); liveTimer = null; }
}

function stopRenderPoll() {
  if (renderTimer) { clearInterval(renderTimer); renderTimer = null; }
}

function injectRender(fragment) {
  if (!renderReady || !renderedEl.contentDocument) return;
  const root = renderedEl.contentDocument.getElementById("live-root");
  if (root) root.innerHTML = fragment;
  applyRenderBoxes();
}

function renderTick(jobId) {
  fetch(`/render/${jobId}`)
    .then((r) => r.json())
    .then((data) => {
      if (currentJobId !== jobId) return;
      injectRender(data.fragment);
      if (data.status === "done" || data.status === "error") stopRenderPoll();
    })
    .catch(() => {});
}

async function startRenderPoll(jobId) {
  stopRenderPoll();
  renderReady = false;
  if (skeletonHtml === null) {
    try { skeletonHtml = await fetch("/rendered_skeleton").then((r) => r.text()); }
    catch { skeletonHtml = "<div id='live-root'></div>"; }
  }
  if (currentJobId !== jobId) return;
  renderedEl.removeAttribute("src");
  renderedEl.onload = () => { renderReady = true; renderTick(jobId); };
  renderedEl.srcdoc = skeletonHtml;
  renderTimer = setInterval(() => {
    if (currentJobId !== jobId) { stopRenderPoll(); return; }
    renderTick(jobId);
  }, 1000);
}

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
          sourceEl.textContent = data.live_text || "Reading...";
          if (atBottom) mid.scrollTop = mid.scrollHeight;
          const byPage = parseBoxes(data.live_text);
          drawBoxes(byPage);
          followActivePage(byPage);
        } else {
          stopLivePoll();
          selectDoc(jobId);
        }
      });
  }, 400);
}

function refreshStatusUI(jobId) {
  const job = jobs[jobId];
  if (!job) return;
  statusPill.textContent = job.status;
  statusPill.className = `pill ${job.status}`;
  if (modePill) {
    const model = job.parse_model || (job.force_ocr ? "visual OCR" : "auto");
    const stage = job.stage ? ` - ${job.stage.replace(/_/g, " ")}` : "";
    modePill.textContent = `mode: ${model}${stage}`;
  }
  const done = job.status === "done";
  dlMd.disabled = !done;
  dlHtml.disabled = !done;
  if (dlJson) dlJson.disabled = !done || !job.analysis_ready;
  dlMd.onclick = done ? () => (window.location = `/download/${jobId}/md`) : null;
  dlHtml.onclick = done ? () => (window.location = `/download/${jobId}/html`) : null;
  if (dlJson) dlJson.onclick = done && job.analysis_ready ? () => (window.location = `/download/${jobId}/json`) : null;
}

function selectDoc(jobId) {
  const job = jobs[jobId];
  if (!jobId || !job) return;
  stopLivePoll();
  stopRenderPoll();
  lastActivePage = -1;
  currentJobId = jobId;
  if (docSelect.value !== jobId) docSelect.value = jobId;
  refreshStatusUI(jobId);

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

  fetch(`/live/${jobId}`).then((r) => r.json()).then((data) => {
    if (currentJobId === jobId) drawBoxes(parseBoxes(data.live_text));
  }).catch(() => {});

  if (job.status === "done") {
    fetch(`/markdown/${jobId}`)
      .then((r) => r.text())
      .then((md) => { if (currentJobId === jobId) sourceEl.textContent = md; });
    startRenderPoll(jobId);
    loadAnalysis(jobId);
  } else if (job.status === "error") {
    sourceEl.textContent = "Error: " + (job.error || "unknown");
    if (analysisEl) analysisEl.innerHTML = '<div class="analysis-empty">Analysis unavailable.</div>';
    if (dlJson) dlJson.disabled = true;
    renderedEl.removeAttribute("srcdoc");
    renderedEl.removeAttribute("src");
  } else {
    sourceEl.textContent = job.force_ocr ? "Reading pages with visual OCR..." : "Reading statement...";
    if (analysisEl) analysisEl.innerHTML = '<div class="analysis-empty">Analysis will appear after processing.</div>';
    if (dlJson) dlJson.disabled = true;
    startLivePoll(jobId);
    startRenderPoll(jobId);
  }
}
