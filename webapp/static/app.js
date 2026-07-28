const els = {
  fileInput: document.getElementById("fileInput"),
  uploadBtn: document.getElementById("uploadBtn"),
  forceOcrToggle: document.getElementById("forceOcrToggle"),
  dropzone: document.getElementById("dropzone"),
  filePreview: document.getElementById("filePreview"),
  fileName: document.getElementById("fileName"),
  progressTrack: document.getElementById("progressTrack"),
  statusBanner: document.getElementById("statusBanner"),
  statusMark: document.getElementById("statusMark"),
  statusHeading: document.getElementById("statusHeading"),
  statusCopy: document.getElementById("statusCopy"),
  confidenceValue: document.getElementById("confidenceValue"),
  statusList: document.getElementById("statusList"),
  metricsGrid: document.getElementById("metricsGrid"),
  decisionPill: document.getElementById("decisionPill"),
  lenderTable: document.getElementById("lenderTable"),
  lenderCount: document.getElementById("lenderCount"),
  accountSummary: document.getElementById("accountSummary"),
  copyTextBtn: document.getElementById("copyTextBtn"),
  openTextBtn: document.getElementById("openTextBtn"),
  downloadJson: document.getElementById("downloadJson"),
  downloadCsv: document.getElementById("downloadCsv"),
  downloadExcel: document.getElementById("downloadExcel"),
  exportText: document.getElementById("exportText"),
  copyDataBtn: document.getElementById("copyDataBtn"),
  summaryBtn: document.getElementById("summaryBtn"),
  summaryBox: document.getElementById("summaryBox"),
  copyBuffer: document.getElementById("copyBuffer"),
};

let currentJobId = null;
let currentAnalysis = null;
let currentMarkdown = "";
let currentFile = null;
let startedAt = null;
let pollTimer = null;

const emptyMetricSections = [
  {
    title: "Credits",
    sub: "Incoming money",
    items: [
      ["Total Credits", "N/A", "All inflows", "CR", "green"],
      ["Deposits", "N/A", "Total deposit volume", "DEP", "green"],
      ["ACH Credits", "N/A", "Incoming ACH items", "ACH", "green"],
    ],
  },
  {
    title: "Debits",
    sub: "Outgoing money",
    items: [
      ["Total Debits", "N/A", "All outflows", "DB", "red"],
      ["Withholding Rate", "N/A", "Lender debits as a share of revenue", "%", "red"],
      ["ACH Debits", "N/A", "Outgoing ACH items", "ACH", "blue"],
      ["POS Transactions", "N/A", "Card-present debits", "POS", "blue"],
      ["ATM Withdrawals", "N/A", "ATM cash activity", "ATM", "blue"],
      ["Checks Detected", "N/A", "Check payments found", "CHK", "blue"],
    ],
  },
  {
    title: "Risk Signals",
    sub: "Balance and NSF indicators",
    items: [
      ["NSFs", "N/A", "Returned or insufficient funds", "NSF", "red"],
      ["Average Daily Balance", "N/A", "Computed from daily ledger", "AVG", "blue"],
      ["Ending Balance", "N/A", "Statement close balance", "END", "blue"],
      ["Lowest Balance", "N/A", "Lowest daily balance", "LOW", "red"],
      ["Highest Balance", "N/A", "Highest daily balance", "HIGH", "green"],
    ],
  },
  {
    title: "Lenders",
    sub: "Funding activity",
    items: [
      ["Lenders Detected", "N/A", "Known funder matches", "LEN", "blue"],
      ["Monthly Cash Flow", "N/A", "Credits minus debits", "CF", "blue"],
    ],
  },
];

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function labelize(value) {
  return String(value || "N/A").replace(/_/g, " ");
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function formatMoney(value, currency = "USD") {
  const n = numberOrNull(value);
  if (n === null) return "N/A";
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n);
  } catch {
    return `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
}

function formatNumber(value) {
  const n = numberOrNull(value);
  if (n === null) return "N/A";
  return n.toLocaleString("en-US");
}

function formatPercent(value) {
  const n = numberOrNull(value);
  if (n === null) return "N/A";
  return `${Number.isInteger(n) ? n.toFixed(0) : n.toFixed(2)}%`;
}

function formatBytes(value) {
  const n = numberOrNull(value);
  if (n === null) return "N/A";
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function maskAccount(value) {
  const raw = String(value || "").replace(/\s+/g, "");
  if (!raw) return "N/A";
  const tail = raw.slice(-4);
  return `•••• ${tail}`;
}

function firstMatch(text, patterns) {
  const source = String(text || "");
  for (const pattern of patterns) {
    const match = source.match(pattern);
    if (match && match[1]) return match[1].trim();
  }
  return "";
}

function accountFieldRows(statement = {}, markdown = "") {
  const routing = statement.routing_number || firstMatch(markdown, [
    /\bRouting(?:\s+Transit)?(?:\s+(?:Number|No\.?|#))?\s*[:#]?\s*([0-9]{9})\b/i,
    /\bRTN\s*[:#]?\s*([0-9]{9})\b/i,
  ]);
  const accountNumber = statement.account_number || firstMatch(markdown, [
    /\bAccount(?:\s+(?:Number|No\.?|#))\s*[:#]?\s*([*xX.\-\s]*\d[\d*Xx.\-\s]{2,})/i,
    /\bAcct(?:\.|ount)?\s*#?\s*[:#]?\s*([*xX.\-\s]*\d[\d*Xx.\-\s]{2,})/i,
  ]);
  const accountType = statement.account_type || statement.account_name || firstMatch(markdown, [
    /\bAccount\s+Type\s*[:#]?\s*([^\n\r|]+)/i,
    /\bProduct\s+Name\s*[:#]?\s*([^\n\r|]+)/i,
  ]);

  return [
    ["Account Type", accountType || "N/A"],
    ["Statement Period", period(statement)],
    ["Routing Number", routing || "N/A"],
    ["Account Number (masked)", maskAccount(accountNumber)],
    ["Bank Name", statement.bank || "N/A"],
  ];
}

function period(statement) {
  if (statement.period_start || statement.period_end) {
    return `${statement.period_start || "N/A"} to ${statement.period_end || "N/A"}`;
  }
  return statement.statement_period || "N/A";
}

function getTransactions(statement) {
  return Array.isArray(statement.transactions) ? statement.transactions : [];
}

function txDescription(tx) {
  return String(tx.description || tx.memo || tx.name || tx.details || "").toUpperCase();
}

function txAmount(tx) {
  const candidates = [tx.amount, tx.value, tx.credit, tx.debit];
  for (const candidate of candidates) {
    const n = numberOrNull(candidate);
    if (n !== null) return n;
  }
  return 0;
}

function countTransactions(transactions, matcher) {
  return transactions.reduce((count, tx) => count + (matcher(txDescription(tx), txAmount(tx), tx) ? 1 : 0), 0);
}

function confidenceFrom(report) {
  const q = report.quality || {};
  if (q.transaction_detail_reliable && q.corporate_use === "approved") return 98;
  if (q.transaction_detail_reliable) return 94;
  if (q.corporate_use === "summary_trusted") return 86;
  if (q.level === "summary_only") return 72;
  return 80;
}

function setProgress(active) {
  els.progressTrack.classList.toggle("show", active);
  els.progressTrack.classList.toggle("indeterminate", active);
}

function setBanner(state, title, meta) {
  els.statusBanner.className = `status-banner ${state || "pending"}`.trim();
  els.statusMark.textContent = state === "done" ? "✓" : state === "error" ? "!" : "·";
  els.statusCopy.textContent = title;
  els.confidenceValue.textContent = meta;
}

function setStatusRows(rows) {
  els.statusList.innerHTML = rows.map(([key, value]) => `
    <div class="status-row">
      <div class="status-key">${escapeHtml(key)}</div>
      <div class="status-value">${escapeHtml(value)}</div>
    </div>
  `).join("");
}

function setInitialState() {
  renderMetricSections(emptyMetricSections);
  renderAccountSummary(accountFieldRows());
  setBanner("pending", "Ready for extraction", "--");
  setStatusRows([
    ["OCR completed", "No"],
    ["Pages processed", "--"],
    ["Processing time", "--"],
    ["OCR confidence", "--"],
    ["Text blocks detected", "--"],
    ["File size", "--"],
  ]);
  renderLenders([]);
}

function setActions(jobId, ready) {
  const links = [
    [els.downloadJson, "json"],
    [els.downloadCsv, "csv"],
    [els.downloadExcel, "xlsx"],
    [els.exportText, "md"],
    [els.openTextBtn, "md"],
  ];
  links.forEach(([link, fmt]) => {
    if (!link) return;
    if (ready) {
      link.href = `/download/${jobId}/${fmt}`;
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
    } else {
      link.href = "#";
      link.classList.add("disabled");
      link.setAttribute("aria-disabled", "true");
    }
  });
  [els.copyDataBtn, els.summaryBtn, els.copyTextBtn].forEach((button) => {
    if (!button) return;
    button.disabled = !ready;
    button.classList.toggle("disabled", !ready);
  });
}

function renderMetricCard([label, value, sub, icon, tone]) {
  return `
    <article class="metric">
      <div class="metric-top">
        <div class="metric-label">${escapeHtml(label)}</div>
        <div class="metric-icon ${escapeHtml(tone || "blue")}">${escapeHtml(icon || "")}</div>
      </div>
      <div class="metric-value">${escapeHtml(value)}</div>
      <div class="metric-sub">${escapeHtml(sub || "")}</div>
    </article>
  `;
}

function renderMetricSections(sections) {
  els.metricsGrid.innerHTML = sections.map((section) => `
    <section class="metric-section">
      <div class="metric-section-head">
        <div class="metric-section-title">${escapeHtml(section.title)}</div>
        <div class="metric-section-sub">${escapeHtml(section.sub || "")}</div>
      </div>
      <div class="metric-section-grid">
        ${(section.items || []).map(renderMetricCard).join("")}
      </div>
    </section>
  `).join("");
}

function renderLenders(funders, currency = "USD", dateReported = "N/A") {
  const lenders = Array.isArray(funders) ? funders : [];
  els.lenderCount.textContent = `${lenders.length} ${lenders.length === 1 ? "record" : "records"}`;
  if (!lenders.length) {
    els.lenderTable.innerHTML = `
      <tr>
        <td><strong>No lenders detected</strong></td>
        <td>Bank statement</td>
        <td>N/A</td>
        <td>${escapeHtml(dateReported)}</td>
        <td><span class="status-badge">Clear</span></td>
      </tr>
    `;
    return;
  }
  els.lenderTable.innerHTML = lenders.map((funder) => `
    <tr>
      <td><strong>${escapeHtml(funder.funder || funder.lender || "Unknown lender")}</strong></td>
      <td>${escapeHtml(funder.account_type || "Lender debit")}</td>
      <td>${escapeHtml(formatMoney(funder.total_debited ?? funder.balance, currency))}</td>
      <td>${escapeHtml(funder.date_reported || dateReported)}</td>
      <td><span class="status-badge">${escapeHtml(funder.status || "Detected")}</span></td>
    </tr>
  `).join("");
}

function renderAccountSummary(rows) {
  if (!els.accountSummary) return;
  els.accountSummary.innerHTML = rows.map(([label, value]) => `
    <div class="summary-item">
      <div class="summary-key">${escapeHtml(label)}</div>
      <div class="summary-value">${escapeHtml(value || "N/A")}</div>
    </div>
  `).join("");
}

function renderAnalysis(report) {
  currentAnalysis = report;
  const statement = report.statement || {};
  const metrics = report.metrics || {};
  const detection = report.detection || {};
  const quality = report.quality || {};
  const transactions = getTransactions(statement);
  const currency = statement.currency || "USD";
  const funders = detection.known_funders || [];

  const achCredits = countTransactions(transactions, (desc, amount) => amount > 0 && desc.includes("ACH"));
  const achDebits = countTransactions(transactions, (desc, amount) => amount < 0 && desc.includes("ACH"));
  const atms = countTransactions(transactions, (desc, amount) => amount < 0 && desc.includes("ATM"));
  const checks = countTransactions(transactions, (desc) => desc.includes("CHECK"));
  const totalCredits = metrics.effective_total_deposits;
  const totalDebits = metrics.effective_total_withdrawals;
  const confidence = confidenceFrom(report);
  const elapsed = startedAt ? `${((Date.now() - startedAt) / 1000).toFixed(1)}s` : "Complete";

  els.statusHeading.textContent = "OCR completed";
  setBanner("done", "Extraction completed", `${confidence}%`);
  els.decisionPill.textContent = labelize(quality.corporate_use || quality.level || "review required");
  els.decisionPill.className = `decision-pill ${quality.corporate_use || quality.level || ""}`.trim();

  setStatusRows([
    ["OCR completed", "Yes"],
    ["Pages processed", formatNumber(statement.page_count || report.page_count || "--")],
    ["Processing time", elapsed],
    ["OCR confidence", `${confidence}%`],
    ["Text blocks detected", formatNumber(transactions.length || metrics.effective_num_deposits || "--")],
    ["File size", formatBytes(currentFile && currentFile.size)],
  ]);

  renderMetricSections([
    {
      title: "Credits",
      sub: "Incoming money",
      items: [
        ["Total Credits", formatMoney(totalCredits, currency), "All credit inflows", "CR", "green"],
        ["Deposits", formatMoney(totalCredits, currency), `${formatNumber(metrics.effective_num_deposits)} deposit items`, "DEP", "green"],
        ["ACH Credits", formatNumber(metrics.ach_credit_count ?? achCredits), "Incoming ACH deposits", "ACH", "green"],
      ],
    },
    {
      title: "Debits",
      sub: "Outgoing money",
      items: [
        ["Total Debits", formatMoney(totalDebits, currency), "All debit outflows", "DB", "red"],
        ["Withholding Rate", formatPercent(metrics.withholding_rate), "Lender debits as a share of revenue", "%", "red"],
        ["ACH Debits", formatNumber(metrics.ach_debit_count ?? achDebits), "Outgoing ACH debits", "ACH", "blue"],
        ["POS Transactions", formatNumber(metrics.pos_count), "Card point-of-sale debits", "POS", "blue"],
        ["ATM Withdrawals", formatNumber(metrics.atm_withdrawal_count ?? atms), "ATM cash withdrawals", "ATM", "blue"],
        ["Checks Detected", formatNumber(metrics.check_count ?? checks), "Check transactions found", "CHK", "blue"],
      ],
    },
    {
      title: "Risk Signals",
      sub: "NSFs and balances",
      items: [
        ["NSFs", formatNumber(metrics.effective_nsf_count), metrics.nsf_source || "Returned item detection", "NSF", "red"],
        ["Average Daily Balance", formatMoney(metrics.average_balance, currency), metrics.average_balance_source || "Daily balance calculation", "AVG", "blue"],
        ["Ending Balance", formatMoney(statement.ending_balance, currency), "Statement close balance", "END", "blue"],
        ["Lowest Balance", formatMoney(metrics.min_balance, currency), "Lowest daily balance", "LOW", "red"],
        ["Highest Balance", formatMoney(metrics.max_balance, currency), "Highest daily balance", "HIGH", "green"],
      ],
    },
    {
      title: "Lenders",
      sub: "Funding activity",
      items: [
        ["Lenders Detected", formatNumber(funders.length), "Known funder keyword matches", "LEN", "blue"],
        ["Monthly Cash Flow", formatMoney(metrics.cash_flow, currency), "Credits minus debits", "CF", "blue"],
      ],
    },
  ]);
  renderAccountSummary(accountFieldRows(statement, currentMarkdown));
  renderLenders(funders, currency, statement.period_end || "N/A");
}

function renderError(message) {
  setProgress(false);
  els.statusHeading.textContent = "Processing failed";
  setBanner("error", "Processing failed", "--");
  els.decisionPill.textContent = "review required";
  els.decisionPill.className = "decision-pill error";
  els.summaryBox.textContent = message;
  renderAccountSummary(accountFieldRows());
}

function showSelectedFile(file) {
  currentFile = file;
  els.filePreview.classList.add("show");
  els.fileName.textContent = `${file.name} · ${formatBytes(file.size)}`;
  setStatusRows([
    ["OCR completed", "No"],
    ["Pages processed", "Queued"],
    ["Processing time", "Running"],
    ["OCR confidence", "--"],
    ["Text blocks detected", "--"],
    ["File size", formatBytes(file.size)],
  ]);
}

function uploadFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;
  const nonPdf = files.find((file) => file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf"));
  if (nonPdf) {
    renderError("Only PDF bank statements are supported.");
    return;
  }

  const file = files[0];
  currentJobId = null;
  currentAnalysis = null;
  currentMarkdown = "";
  startedAt = Date.now();
  showSelectedFile(file);
  setActions(null, false);
  setProgress(true);
  els.statusHeading.textContent = "Uploading PDF";
  setBanner("pending", "Uploading PDF", "--");
  renderAccountSummary(accountFieldRows());
  els.summaryBox.textContent = "Processing statement...";

  const form = new FormData();
  files.forEach((item) => form.append("files", item));
  if (els.forceOcrToggle && els.forceOcrToggle.checked) form.append("force_ocr", "1");

  fetch("/upload", { method: "POST", body: form })
    .then((response) => {
      if (!response.ok) throw new Error(`Upload failed (${response.status})`);
      return response.json();
    })
    .then((payload) => {
      if (!payload.jobs || !payload.jobs.length) throw new Error(payload.error || "No processing job was created");
      currentJobId = payload.jobs[0].id;
      els.statusHeading.textContent = "Processing statement";
      setBanner("pending", "Extraction started", "--");
      pollJob(currentJobId);
    })
    .catch((error) => renderError(error.message || String(error)));
}

function pollJob(jobId) {
  if (pollTimer) clearTimeout(pollTimer);
  fetch(`/status/${jobId}`)
    .then((response) => {
      if (!response.ok) throw new Error(`Status failed (${response.status})`);
      return response.json();
    })
    .then((status) => {
      if (jobId !== currentJobId) return;
      const stage = status.stage ? labelize(status.stage) : labelize(status.status);
      if (status.status === "done") {
        setProgress(false);
        loadResults(jobId);
        return;
      }
      if (status.status === "error") {
        renderError(status.error || "Processing failed");
        return;
      }
      els.statusHeading.textContent = "Processing statement";
      setBanner("pending", stage, "--");
      setStatusRows([
        ["OCR completed", "No"],
        ["Pages processed", formatNumber(status.page_count || "--")],
        ["Processing time", startedAt ? `${((Date.now() - startedAt) / 1000).toFixed(1)}s` : "Running"],
        ["OCR confidence", "--"],
        ["Text blocks detected", stage],
        ["File size", formatBytes(currentFile && currentFile.size)],
      ]);
      pollTimer = setTimeout(() => pollJob(jobId), 1400);
    })
    .catch((error) => renderError(error.message || String(error)));
}

function loadResults(jobId) {
  Promise.all([
    fetch(`/analysis/${jobId}`).then((response) => {
      if (!response.ok) throw new Error(`Analysis unavailable (${response.status})`);
      return response.json();
    }),
    fetch(`/markdown/${jobId}`).then((response) => response.ok ? response.text() : ""),
  ])
    .then(([payload, markdown]) => {
      if (jobId !== currentJobId) return;
      if (!payload.analysis) throw new Error(payload.analysis_error || "No analysis report was generated");
      currentMarkdown = markdown || "";
      renderAnalysis(payload.analysis);
      setActions(jobId, true);
      els.summaryBox.textContent = "Exports and copy actions are ready.";
    })
    .catch((error) => renderError(error.message || String(error)));
}

function copyText(value) {
  const text = String(value || "");
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  els.copyBuffer.value = text;
  els.copyBuffer.select();
  document.execCommand("copy");
  return Promise.resolve();
}

function generateSummary() {
  if (!currentAnalysis) return;
  const s = currentAnalysis.statement || {};
  const m = currentAnalysis.metrics || {};
  const d = currentAnalysis.detection || {};
  const q = currentAnalysis.quality || {};
  const currency = s.currency || "USD";
  const lenders = Array.isArray(d.known_funders) ? d.known_funders.length : 0;
  els.summaryBox.textContent =
    `${s.bank || "Statement"} ${period(s)}: average daily balance ${formatMoney(m.average_balance, currency)}, ` +
    `ending balance ${formatMoney(s.ending_balance, currency)}, cash flow ${formatMoney(m.cash_flow, currency)}, ` +
    `${formatNumber(m.effective_nsf_count)} NSF events, and ${formatNumber(lenders)} lender detections. ` +
    `Quality status: ${labelize(q.corporate_use || q.level || "review required")}.`;
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
  });
});

els.uploadBtn.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", () => {
  uploadFiles(els.fileInput.files);
  els.fileInput.value = "";
});

["dragenter", "dragover"].forEach((eventName) => {
  els.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropzone.classList.add("drag");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  els.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropzone.classList.remove("drag");
    if (eventName === "drop" && event.dataTransfer) uploadFiles(event.dataTransfer.files);
  });
});

if (els.copyTextBtn) els.copyTextBtn.addEventListener("click", () => copyText(currentMarkdown));
els.copyDataBtn.addEventListener("click", () => copyText(JSON.stringify(currentAnalysis || {}, null, 2)));
els.summaryBtn.addEventListener("click", generateSummary);

setInitialState();
setActions(null, false);
