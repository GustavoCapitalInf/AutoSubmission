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
  monthlyCard: document.getElementById("monthlyCard"),
  monthlyTable: document.getElementById("monthlyTable"),
  monthlyCount: document.getElementById("monthlyCount"),
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
  statementModalBackdrop: document.getElementById("statementModalBackdrop"),
  statementModalClose: document.getElementById("statementModalClose"),
  statementModalTitle: document.getElementById("statementModalTitle"),
  statementModalSubtitle: document.getElementById("statementModalSubtitle"),
  statementModalMetrics: document.getElementById("statementModalMetrics"),
  statementModalAccount: document.getElementById("statementModalAccount"),
  statementModalLenders: document.getElementById("statementModalLenders"),
  modalJsonDownload: document.getElementById("modalJsonDownload"),
  modalCopyData: document.getElementById("modalCopyData"),
  copyBuffer: document.getElementById("copyBuffer"),
};

let currentJobId = null;
let currentJobIds = [];
let currentAnalysis = null;
let currentMarkdown = "";
let currentFile = null;
let currentFiles = [];
let startedAt = null;
let pollTimer = null;
let modalAnalysis = null;
let modalLastFocus = null;
let modalScrollY = 0;

function selectedParseMode() {
  return document.querySelector('input[name="parseMode"]:checked')?.value || "auto";
}

function parseModeLabel(value) {
  return value === "deterministic" ? "Deterministic only" : "Auto";
}

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
  if (q.corporate_use === "manual_review_required") return 72;
  if (q.level === "needs_review") return 72;
  if (q.corporate_use === "summary_only" || q.level === "summary_only") return 72;
  return 80;
}

function packageConfidence(pkg = {}) {
  const totals = pkg.totals || {};
  if (totals.failed || totals.integrity_high || totals.manual_review) return 72;
  if (totals.summary_only || totals.integrity_review) return 86;
  return 98;
}

function derivedIntegrity(report = {}) {
  const integrity = report.integrity || {};
  if (integrity.risk_level) return integrity;
  const quality = report.quality || {};
  const reconciliation = report.reconciliation || {};
  const flags = [];
  if (reconciliation.summary_ok === false) flags.push("summary_math_inconsistent");
  if (Number.isFinite(Number(reconciliation.sum_delta)) && Math.abs(Number(reconciliation.sum_delta)) > 1) flags.push("ledger_sum_mismatch");
  if (Number(reconciliation.continuity_breaks || 0) > 0) flags.push("running_balance_breaks");
  if (quality.corporate_use === "summary_only" || quality.transaction_detail_reliable === false) flags.push("transaction_detail_not_corporate_reliable");
  const high = reconciliation.summary_ok === false || Number(reconciliation.continuity_breaks || 0) >= 3;
  return {
    risk_level: high ? "high" : flags.length ? "review" : "clear",
    flags,
    notes: [],
    possible_document_issue: high,
  };
}

function integrityLabel(integrity = {}) {
  const level = integrity.risk_level || "clear";
  if (level === "high") return "High review";
  if (level === "review") return "Review";
  return "Clear";
}

function friendlyAnalysisError(message) {
  const text = String(message || "");
  if (/no deterministic parser matched/i.test(text)) {
    return "No deterministic parser matched this statement. Use Auto mode for fallback extraction, or add a bank-specific deterministic parser before using Deterministic only.";
  }
  if (/native PDF text unavailable|too sparse|no native text/i.test(text)) {
    return "This PDF does not contain usable native text, and local OCR could not produce usable statement text. Turn on visual OCR or use Auto mode to retry with the OCR service.";
  }
  return text || "No analysis report was generated";
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
  if (els.monthlyCard) els.monthlyCard.style.display = "none";
  renderMetricSections(emptyMetricSections);
  renderAccountSummary(accountFieldRows());
  setBanner("pending", "Ready for extraction", "--");
  setStatusRows([
    ["OCR completed", "No"],
    ["Pages processed", "--"],
    ["Processing time", "--"],
    ["Parsing mode", parseModeLabel(selectedParseMode())],
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

function setPackageActions(jobIds) {
  const query = `ids=${encodeURIComponent(jobIds.join(","))}`;
  [
    [els.downloadJson, `json?${query}`],
    [els.downloadCsv, `csv?${query}`],
    [els.downloadExcel, `xlsx?${query}`],
  ].forEach(([link, target]) => {
    if (!link) return;
    link.href = `/package_download/${target}`;
    link.classList.remove("disabled");
    link.setAttribute("aria-disabled", "false");
  });
  [els.exportText, els.openTextBtn].forEach((link) => {
    if (!link) return;
    link.href = "#";
    link.classList.add("disabled");
    link.setAttribute("aria-disabled", "true");
  });
  [els.copyDataBtn, els.summaryBtn].forEach((button) => {
    if (!button) return;
    button.disabled = false;
    button.classList.remove("disabled");
  });
  if (els.copyTextBtn) {
    els.copyTextBtn.disabled = true;
    els.copyTextBtn.classList.add("disabled");
  }
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
  els.accountSummary.innerHTML = summaryRowsHtml(rows);
}

function summaryRowsHtml(rows) {
  return rows.map(([label, value]) => `
    <div class="summary-item">
      <div class="summary-key">${escapeHtml(label)}</div>
      <div class="summary-value">${escapeHtml(value || "N/A")}</div>
    </div>
  `).join("");
}

function renderAnalysis(report) {
  currentAnalysis = report;
  if (els.monthlyCard) els.monthlyCard.style.display = "none";
  const statement = report.statement || {};
  const metrics = report.metrics || {};
  const detection = report.detection || {};
  const quality = report.quality || {};
  const integrity = derivedIntegrity(report);
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
    ["Parsing mode", parseModeLabel(report.parse_mode || selectedParseMode())],
    ["Parser used", report.model_used || "N/A"],
    ["Document integrity", integrityLabel(integrity)],
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
        ["Document Integrity", integrityLabel(integrity), (integrity.flags || []).join(", ") || "No source contradictions detected", "DOC", integrity.risk_level === "high" ? "red" : integrity.risk_level === "review" ? "blue" : "green"],
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
  const files = currentFiles.length ? currentFiles : [file];
  els.filePreview.classList.add("show");
  els.fileName.textContent = files.length === 1
    ? `${file.name} - ${formatBytes(file.size)}`
    : `${files.length} PDF statements selected - ${files.map((item) => item.name).join(", ")}`;
  setStatusRows([
    ["OCR completed", "No"],
    ["Pages processed", "Queued"],
    ["Processing time", "Running"],
    ["Parsing mode", parseModeLabel(selectedParseMode())],
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
  currentJobIds = [];
  currentFiles = files;
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
  form.append("parse_mode", selectedParseMode());

  fetch("/upload", { method: "POST", body: form })
    .then((response) => {
      if (!response.ok) throw new Error(`Upload failed (${response.status})`);
      return response.json();
    })
    .then((payload) => {
      if (!payload.jobs || !payload.jobs.length) throw new Error(payload.error || "No processing job was created");
      currentJobIds = payload.jobs.map((job) => job.id);
      currentJobId = currentJobIds[0];
      const isPackage = currentJobIds.length > 1;
      els.statusHeading.textContent = isPackage ? "Processing package" : "Processing statement";
      setBanner("pending", isPackage ? "Package extraction started" : "Extraction started", "--");
      if (isPackage) pollPackage(currentJobIds);
      else pollJob(currentJobId);
    })
    .catch((error) => renderError(error.message || String(error)));
}

function pollPackage(jobIds) {
  if (pollTimer) clearTimeout(pollTimer);
  Promise.all(jobIds.map((jobId) => fetch(`/status/${jobId}`).then((response) => {
    if (!response.ok) throw new Error(`Status failed (${response.status})`);
    return response.json();
  })))
    .then((statuses) => {
      if (jobIds.join(",") !== currentJobIds.join(",")) return;
      const finished = statuses.filter((status) => status.status === "done" || status.status === "error").length;
      const errors = statuses.filter((status) => status.status === "error" || status.analysis_error).length;
      const totalPages = statuses.reduce((sum, status) => sum + (numberOrNull(status.page_count) || 0), 0);
      if (finished === statuses.length) {
        setProgress(false);
        loadPackage(jobIds);
        return;
      }
      els.statusHeading.textContent = "Processing package";
      setBanner("pending", `${finished} of ${statuses.length} statements completed`, "--");
      setStatusRows([
        ["Statements completed", `${finished} / ${statuses.length}`],
        ["Pages queued", formatNumber(totalPages)],
        ["Processing time", startedAt ? `${((Date.now() - startedAt) / 1000).toFixed(1)}s` : "Running"],
        ["Parsing mode", parseModeLabel(selectedParseMode())],
        ["Processing errors", formatNumber(errors)],
        ["File size", `${currentFiles.length} files`],
      ]);
      pollTimer = setTimeout(() => pollPackage(jobIds), 1400);
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
        ["Parsing mode", parseModeLabel(status.parse_mode || selectedParseMode())],
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
      if (!payload.analysis) throw new Error(friendlyAnalysisError(payload.analysis_error));
      currentMarkdown = markdown || "";
      renderAnalysis(payload.analysis);
      setActions(jobId, true);
      els.summaryBox.textContent = "Exports and copy actions are ready.";
    })
    .catch((error) => renderError(error.message || String(error)));
}

function packagePeriod(documents) {
  const starts = documents.map((doc) => doc.period_start).filter(Boolean).sort();
  const ends = documents.map((doc) => doc.period_end).filter(Boolean).sort();
  if (!starts.length && !ends.length) return "N/A";
  return `${starts[0] || "N/A"} to ${ends[ends.length - 1] || "N/A"}`;
}

function loadPackage(jobIds) {
  fetch(`/package_analysis?ids=${encodeURIComponent(jobIds.join(","))}`)
    .then((response) => {
      if (!response.ok) throw new Error(`Package analysis unavailable (${response.status})`);
      return response.json();
    })
    .then((pkg) => {
      if (jobIds.join(",") !== currentJobIds.join(",")) return;
      renderPackageAnalysis(pkg);
      setPackageActions(jobIds);
    })
    .catch((error) => renderError(error.message || String(error)));
}

function renderPackageAnalysis(pkg) {
  currentAnalysis = { package: pkg };
  currentMarkdown = "";
  const totals = pkg.totals || {};
  const documents = Array.isArray(pkg.documents) ? pkg.documents : [];
  const funders = Array.isArray(pkg.funders) ? pkg.funders : [];
  const confidence = packageConfidence(pkg);

  els.statusHeading.textContent = "Package completed";
  setBanner("done", "Package analysis completed", `${confidence}%`);
  els.decisionPill.textContent = labelize(totals.decision || "review required");
  els.decisionPill.className = `decision-pill ${totals.decision || ""}`.trim();
  setStatusRows([
    ["Statements completed", `${formatNumber(totals.completed)} / ${formatNumber(totals.documents)}`],
    ["Approved", formatNumber(totals.approved)],
    ["Manual review", formatNumber(totals.manual_review)],
    ["High integrity risk", formatNumber(totals.integrity_high)],
    ["Processing errors", formatNumber(totals.failed)],
    ["Package withholding", formatPercent(totals.package_withholding_rate)],
  ]);

  renderMetricSections([
    {
      title: "Package Revenue",
      sub: `${formatNumber(totals.months)} statement periods`,
      items: [
        ["Total Credits", formatMoney(totals.total_credits), "Combined incoming money", "CR", "green"],
        ["Avg Monthly Credits", formatMoney(totals.avg_monthly_credits), "Monthly revenue baseline", "AVG", "green"],
        ["Total Debits", formatMoney(totals.total_debits), "Combined outgoing money", "DB", "red"],
        ["Avg Monthly Debits", formatMoney(totals.avg_monthly_debits), "Monthly expense baseline", "AVG", "red"],
      ],
    },
    {
      title: "Cash Flow",
      sub: "Package-level affordability signals",
      items: [
        ["Total Cash Flow", formatMoney(totals.cash_flow), "Credits minus debits", "CF", totals.cash_flow < 0 ? "red" : "green"],
        ["Avg Monthly Cash Flow", formatMoney(totals.avg_monthly_cash_flow), "Average statement cash flow", "AVG", totals.avg_monthly_cash_flow < 0 ? "red" : "green"],
        ["Average Daily Balance", formatMoney(totals.average_daily_balance), "Weighted across statement periods", "ADB", "blue"],
        ["NSFs", formatNumber(totals.nsf_count), "Total returned items", "NSF", totals.nsf_count ? "red" : "green"],
        ["Package Withholding", formatPercent(totals.package_withholding_rate), "Lender debits as revenue share", "%", totals.package_withholding_rate ? "red" : "green"],
      ],
    },
    {
      title: "Quality",
      sub: "Corporate-use readiness",
      items: [
        ["Approved", formatNumber(totals.approved), "Corporate-approved statements", "OK", "green"],
        ["Manual Review", formatNumber(totals.manual_review), "Statements withheld from automated approval", "REV", totals.manual_review ? "red" : "green"],
        ["Integrity High", formatNumber(totals.integrity_high), "Possible document issue", "DOC", totals.integrity_high ? "red" : "green"],
        ["Failed", formatNumber(totals.failed), "Statements needing rerun", "ERR", totals.failed ? "red" : "green"],
      ],
    },
    {
      title: "Lenders",
      sub: "Known funding activity",
      items: [
        ["Lenders Detected", formatNumber(funders.length), "Unique lender names", "LEN", funders.length ? "red" : "green"],
        ["Total Lender Debits", formatMoney(totals.lender_debits), "Observed funding debits", "DB", totals.lender_debits ? "red" : "green"],
      ],
    },
  ]);

  renderAccountSummary([
    ["Package Decision", labelize(totals.decision || "review required")],
    ["Statements", `${formatNumber(totals.completed)} completed of ${formatNumber(totals.documents)}`],
    ["Period Range", packagePeriod(documents)],
    ["Average Daily Balance", formatMoney(totals.average_daily_balance)],
    ["Top Lenders", funders.length ? funders.slice(0, 3).map((f) => f.funder).join(", ") : "None detected"],
    ["Total Lender Debits", formatMoney(totals.lender_debits)],
  ]);
  renderPackageTables(pkg);
}

function renderPackageTables(pkg) {
  const documents = Array.isArray(pkg.documents) ? pkg.documents : [];
  const funders = Array.isArray(pkg.funders) ? pkg.funders : [];
  renderLenders(funders, "USD", packagePeriod(documents));
  if (els.monthlyCard) els.monthlyCard.style.display = "block";
  if (els.monthlyCount) {
    els.monthlyCount.textContent = `${documents.length} ${documents.length === 1 ? "statement" : "statements"}`;
  }
  if (!els.monthlyTable) return;
  if (!documents.length) {
    els.monthlyTable.innerHTML = `
      <tr>
        <td><strong>No statements</strong></td>
        <td>N/A</td>
        <td>N/A</td>
        <td>N/A</td>
        <td>N/A</td>
        <td>N/A</td>
        <td>N/A</td>
        <td><span class="status-badge">Review</span></td>
      </tr>
    `;
  } else {
    els.monthlyTable.innerHTML = documents.map((doc) => {
      const status = doc.status !== "done" ? "Failed" : labelize(doc.corporate_use || doc.quality || "review");
      return `
        <tr>
          <td><strong>${escapeHtml(doc.filename || "Statement")}</strong><br><span>${escapeHtml(doc.bank || "Unknown bank")}</span></td>
          <td>${escapeHtml(doc.period_start || "N/A")} to ${escapeHtml(doc.period_end || "N/A")}</td>
          <td>${escapeHtml(formatMoney(doc.credits))}</td>
          <td>${escapeHtml(formatMoney(doc.debits))}</td>
          <td>${escapeHtml(formatMoney(doc.cash_flow))}</td>
          <td>${escapeHtml(formatMoney(doc.average_balance))}</td>
          <td>${escapeHtml(formatNumber(doc.nsf_count))}</td>
          <td><button class="table-action statement-open" type="button" data-job-id="${escapeHtml(doc.id)}" ${doc.status === "done" ? "" : "disabled"}>${escapeHtml(status === "Failed" ? "Unavailable" : "Open")}</button></td>
        </tr>
      `;
    }).join("");
  }

  const lenderSummary = funders.length
    ? funders.map((funder) => `${funder.funder}: ${formatMoney(funder.total_debited)} across ${formatNumber(funder.documents)} statement(s)`).join("\n")
    : "No lenders detected across the package.";
  els.summaryBox.textContent = `Package lender summary:\n${lenderSummary}`;
}

function openStatementModal(jobId) {
  if (!els.statementModalBackdrop) return;
  modalLastFocus = document.activeElement;
  modalAnalysis = null;
  modalScrollY = window.scrollY || document.documentElement.scrollTop || 0;
  els.statementModalBackdrop.classList.add("show");
  els.statementModalBackdrop.setAttribute("aria-hidden", "false");
  document.documentElement.style.overflow = "hidden";
  document.body.style.overflow = "hidden";
  document.body.style.position = "fixed";
  document.body.style.top = `-${modalScrollY}px`;
  document.body.style.left = "0";
  document.body.style.right = "0";
  document.body.style.width = "100%";
  els.statementModalTitle.textContent = "Loading statement";
  els.statementModalSubtitle.textContent = "Fetching extracted information...";
  els.statementModalMetrics.innerHTML = "";
  els.statementModalAccount.innerHTML = "";
  els.statementModalLenders.innerHTML = `
    <tr>
      <td><strong>Loading</strong></td>
      <td>N/A</td>
      <td>N/A</td>
      <td><span class="status-badge">Pending</span></td>
    </tr>
  `;
  if (els.modalJsonDownload) {
    els.modalJsonDownload.href = "#";
    els.modalJsonDownload.classList.add("disabled");
    els.modalJsonDownload.setAttribute("aria-disabled", "true");
  }

  Promise.all([
    fetch(`/analysis/${jobId}`).then((response) => {
      if (!response.ok) throw new Error(`Analysis unavailable (${response.status})`);
      return response.json();
    }),
    fetch(`/markdown/${jobId}`).then((response) => response.ok ? response.text() : ""),
  ])
    .then(([payload, markdown]) => {
      if (!payload.analysis) throw new Error(friendlyAnalysisError(payload.analysis_error));
      modalAnalysis = payload.analysis;
      renderStatementModal(jobId, payload.analysis, markdown || "");
      if (els.statementModalClose) els.statementModalClose.focus();
    })
    .catch((error) => {
      els.statementModalTitle.textContent = "Statement unavailable";
      els.statementModalSubtitle.textContent = error.message || String(error);
      els.statementModalMetrics.innerHTML = "";
      els.statementModalAccount.innerHTML = "";
      els.statementModalLenders.innerHTML = `
        <tr>
          <td><strong>Unable to load statement</strong></td>
          <td>N/A</td>
          <td>N/A</td>
          <td><span class="status-badge">Review</span></td>
        </tr>
      `;
    });
}

function renderStatementModal(jobId, report, markdown) {
  const statement = report.statement || {};
  const metrics = report.metrics || {};
  const detection = report.detection || {};
  const quality = report.quality || {};
  const integrity = derivedIntegrity(report);
  const currency = statement.currency || "USD";
  const funders = Array.isArray(detection.known_funders) ? detection.known_funders : [];
  const title = statement.bank ? `${statement.bank} Statement` : "Bank Statement";

  els.statementModalTitle.textContent = title;
  els.statementModalSubtitle.textContent = `${period(statement)} - ${labelize(quality.corporate_use || quality.level || "review required")}`;
  els.statementModalMetrics.innerHTML = [
    ["Total Credits", formatMoney(metrics.effective_total_deposits, currency), "Incoming money", "CR", "green"],
    ["Total Debits", formatMoney(metrics.effective_total_withdrawals, currency), "Outgoing money", "DB", "red"],
    ["Cash Flow", formatMoney(metrics.cash_flow, currency), "Credits minus debits", "CF", metrics.cash_flow < 0 ? "red" : "green"],
    ["Average Daily Balance", formatMoney(metrics.average_balance, currency), "Daily ledger average", "AVG", "blue"],
    ["Ending Balance", formatMoney(statement.ending_balance, currency), "Statement close balance", "END", "blue"],
    ["NSFs", formatNumber(metrics.effective_nsf_count), "Returned items", "NSF", metrics.effective_nsf_count ? "red" : "green"],
    ["Withholding Rate", formatPercent(metrics.withholding_rate), "Lender debits vs credits", "%", metrics.withholding_rate ? "red" : "green"],
    ["Lenders Detected", formatNumber(funders.length), "Known funder matches", "LEN", funders.length ? "red" : "green"],
    ["Document Integrity", integrityLabel(integrity), (integrity.flags || []).join(", ") || "No source contradictions detected", "DOC", integrity.risk_level === "high" ? "red" : integrity.risk_level === "review" ? "blue" : "green"],
    ["Quality", labelize(quality.corporate_use || quality.level || "review"), "Corporate-use status", "OK", quality.corporate_use === "approved" ? "green" : "red"],
  ].map(renderMetricCard).join("");
  els.statementModalAccount.innerHTML = summaryRowsHtml(accountFieldRows(statement, markdown));

  if (!funders.length) {
    els.statementModalLenders.innerHTML = `
      <tr>
        <td><strong>No lenders detected</strong></td>
        <td>Bank statement</td>
        <td>N/A</td>
        <td><span class="status-badge">Clear</span></td>
      </tr>
    `;
  } else {
    els.statementModalLenders.innerHTML = funders.map((funder) => `
      <tr>
        <td><strong>${escapeHtml(funder.funder || funder.lender || "Unknown lender")}</strong></td>
        <td>${escapeHtml(funder.account_type || "Lender debit")}</td>
        <td>${escapeHtml(formatMoney(funder.total_debited ?? funder.balance, currency))}</td>
        <td><span class="status-badge">${escapeHtml(funder.status || "Detected")}</span></td>
      </tr>
    `).join("");
  }

  if (els.modalJsonDownload) {
    els.modalJsonDownload.href = `/download/${jobId}/json`;
    els.modalJsonDownload.classList.remove("disabled");
    els.modalJsonDownload.setAttribute("aria-disabled", "false");
  }
}

function closeStatementModal() {
  if (!els.statementModalBackdrop) return;
  els.statementModalBackdrop.classList.remove("show");
  els.statementModalBackdrop.setAttribute("aria-hidden", "true");
  document.documentElement.style.overflow = "";
  document.body.style.overflow = "";
  document.body.style.position = "";
  document.body.style.top = "";
  document.body.style.left = "";
  document.body.style.right = "";
  document.body.style.width = "";
  window.scrollTo(0, modalScrollY);
  if (modalLastFocus && typeof modalLastFocus.focus === "function") modalLastFocus.focus();
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
  if (currentAnalysis.package) {
    const pkg = currentAnalysis.package;
    const totals = pkg.totals || {};
    const funders = Array.isArray(pkg.funders) ? pkg.funders : [];
    els.summaryBox.textContent =
      `Package ${packagePeriod(pkg.documents || [])}: ${formatNumber(totals.completed)} of ${formatNumber(totals.documents)} statements completed, ` +
      `${formatMoney(totals.avg_monthly_credits)} average monthly credits, ${formatMoney(totals.avg_monthly_cash_flow)} average monthly cash flow, ` +
      `${formatNumber(totals.nsf_count)} NSF events, ${formatPercent(totals.package_withholding_rate)} package withholding, ` +
      `and ${formatNumber(funders.length)} lender detections. Decision: ${labelize(totals.decision || "review required")}.`;
    return;
  }
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
if (els.monthlyTable) {
  els.monthlyTable.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const button = target ? target.closest(".statement-open") : null;
    if (!button || button.disabled) return;
    const jobId = button.getAttribute("data-job-id");
    if (!jobId) return;
    openStatementModal(jobId);
  });
}
if (els.statementModalClose) {
  els.statementModalClose.addEventListener("click", closeStatementModal);
}
if (els.statementModalBackdrop) {
  els.statementModalBackdrop.addEventListener("click", (event) => {
    if (event.target === els.statementModalBackdrop) closeStatementModal();
  });
  els.statementModalBackdrop.addEventListener("wheel", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target || !target.closest(".modal-body")) event.preventDefault();
  }, { passive: false });
  els.statementModalBackdrop.addEventListener("touchmove", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target || !target.closest(".modal-body")) event.preventDefault();
  }, { passive: false });
}
if (els.modalCopyData) {
  els.modalCopyData.addEventListener("click", () => copyText(JSON.stringify(modalAnalysis || {}, null, 2)));
}
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && els.statementModalBackdrop?.classList.contains("show")) {
    closeStatementModal();
  }
});

setInitialState();
setActions(null, false);
