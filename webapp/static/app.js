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
  insuranceTable: document.getElementById("insuranceTable"),
  insuranceCount: document.getElementById("insuranceCount"),
  revenueTable: document.getElementById("revenueTable"),
  revenueCount: document.getElementById("revenueCount"),
  transactionTable: document.getElementById("transactionTable"),
  transactionCount: document.getElementById("transactionCount"),
  transactionCard: document.getElementById("transactionCard"),
  transactionScope: document.getElementById("transactionScope"),
  transactionMore: document.getElementById("transactionMore"),
  statementModalTransactionMore: document.getElementById("statementModalTransactionMore"),
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
  statementModalInsurance: document.getElementById("statementModalInsurance"),
  statementModalRevenue: document.getElementById("statementModalRevenue"),
  statementModalTransactions: document.getElementById("statementModalTransactions"),
  statementModalTransactionCount: document.getElementById("statementModalTransactionCount"),
  modalJsonDownload: document.getElementById("modalJsonDownload"),
  modalCopyData: document.getElementById("modalCopyData"),
  copyBuffer: document.getElementById("copyBuffer"),
  appearanceToggle: document.getElementById("appearanceToggle"),
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
let modalJobId = null;
let modalLastFocus = null;
let modalScrollY = 0;
let transactionFilter = "all";
let modalTransactionFilter = "all";
let transactionEntityFilter = null;
let modalTransactionEntityFilter = null;
let transactionSort = "date";
let modalTransactionSort = "date";
// Ledgers can run to thousands of rows across a package, so render in pages.
const TRANSACTION_PAGE = 100;
let transactionLimit = TRANSACTION_PAGE;
let modalTransactionLimit = TRANSACTION_PAGE;

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
      ["Verified Revenue", "N/A", "Verified operating credits", "REV", "green"],
      ["Unverified Deposits", "N/A", "Deposits requiring review", "?", "amber"],
      ["Non-Revenue", "N/A", "Excluded credit inflows", "X", "neutral"],
      ["Maximum Revenue", "N/A", "Verified plus unverified deposits", "MAX", "neutral"],
      ["ACH Credits", "N/A", "Incoming ACH items", "ACH", "neutral"],
    ],
  },
  {
    title: "Debits",
    sub: "Outgoing money",
    items: [
      ["Total Debits", "N/A", "All outflows", "DB", "neutral"],
      ["Confirmed Withholding", "N/A", "Confirmed lender debits as a share of revenue", "%", "neutral"],
      ["ACH Debits", "N/A", "Outgoing ACH items", "ACH", "neutral"],
      ["POS Transactions", "N/A", "Card-present debits", "POS", "neutral"],
      ["ATM Withdrawals", "N/A", "ATM cash activity", "ATM", "neutral"],
      ["Checks Detected", "N/A", "Check payments found", "CHK", "neutral"],
    ],
  },
  {
    title: "Risk Signals",
    sub: "Balance and NSF indicators",
    items: [
      ["NSFs", "N/A", "Returned or insufficient funds", "NSF", "neutral"],
      ["Average Daily Balance", "N/A", "Daily ending balances across the statement period", "AVG", "neutral"],
      ["Ending Balance", "N/A", "Statement close balance", "END", "neutral"],
      ["Lowest Balance", "N/A", "Lowest daily balance", "LOW", "neutral"],
      ["Highest Balance", "N/A", "Highest daily balance", "HIGH", "neutral"],
    ],
  },
  {
    title: "Lenders",
    sub: "Classified funding and insurance activity",
    items: [
      ["Confirmed Lenders", "N/A", "Distinct confirmed entities", "LEN", "neutral"],
      ["Potential Lenders", "N/A", "Distinct entities requiring review", "?", "neutral"],
      ["Confirmed Lender Debit Count", "N/A", "Qualifying confirmed debit rows", "DB", "neutral"],
      ["Confirmed Lender Debits", "N/A", "Confirmed withholding numerator", "$", "neutral"],
      ["Potential Lender Debit Count", "N/A", "Exact candidate evidence rows", "DB", "neutral"],
      ["Potential Lender Debits", "N/A", "Excluded from confirmed lender metrics", "$", "neutral"],
      ["Eligible Deposits", "N/A", "Confirmed and potential denominator", "DEP", "neutral"],
      ["Potential Withholding Exposure", "N/A", "Candidate debit exposure", "%", "neutral"],
      ["Insurance Debits", "N/A", "Posted insurance debit rows", "INS", "neutral"],
      ["Insurance Total", "N/A", "Insurance debits excluded from lenders", "$", "neutral"],
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

function withholdingAuditNote(metrics = {}, currency = "USD") {
  if (metrics.withholding_review_required) return "Eligible deposits unavailable - review required";
  const numerator = formatMoney(metrics.withholding_numerator ?? metrics.lender_debits, currency);
  const denominator = formatMoney(metrics.withholding_denominator ?? metrics.eligible_deposits, currency);
  const label = metrics.withholding_denominator_label || "Legacy eligible deposits";
  return `${numerator} lender debits / ${denominator} ${label.toLowerCase()}`;
}

function activeDenominatorNote(metrics = {}) {
  const label = metrics.withholding_denominator_label || "Legacy eligible deposits";
  const definition = metrics.eligible_deposit_definition || "Effective credits minus lender funding";
  return `${label} - ${definition}`;
}

function potentialLenderDebitTotal(metrics = {}) {
  return metrics.potential_lender_debit_total ?? metrics.potential_lender_debits;
}

function hasMaterialPotentialLenderDebits(metrics = {}) {
  if (metrics.potential_withholding_review_required === true) return true;
  const total = numberOrNull(potentialLenderDebitTotal(metrics));
  return total !== null && Math.abs(total) > 0;
}

function potentialWithholdingAuditNote(metrics = {}, currency = "USD") {
  const total = potentialLenderDebitTotal(metrics);
  const denominator = metrics.potential_withholding_denominator ?? metrics.eligible_deposits;
  if (numberOrNull(total) === null) return "Potential debit amount unavailable - review required";
  const reviewSuffix = hasMaterialPotentialLenderDebits(metrics) ? " - review required" : "";
  if ((numberOrNull(denominator) ?? 0) <= 0) {
    return `${formatMoney(total, currency)} potential lender debits / eligible deposits unavailable${reviewSuffix}`;
  }
  return `${formatMoney(total, currency)} potential lender debits / ${formatMoney(denominator, currency)} eligible deposits${reviewSuffix}`;
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

function txDescriptionRaw(tx) {
  return String(tx.description || tx.memo || tx.name || tx.details || "");
}

function txAmount(tx) {
  const candidates = [tx.amount, tx.value, tx.credit, tx.debit];
  for (const candidate of candidates) {
    const n = numberOrNull(candidate);
    if (n !== null) return n;
  }
  return 0;
}

function transactionClassification(tx) {
  return tx && typeof tx.classification === "object" && tx.classification
    ? tx.classification
    : { classification: "other" };
}

function transactionCategory(tx) {
  const record = transactionClassification(tx);
  const revenueState = record.revenue_classification;
  if (txAmount(tx) > 0 && revenueState === "verified_revenue") {
    return { label: "Verified revenue", glyph: "REV", tone: "green" };
  }
  if (txAmount(tx) > 0 && revenueState === "unverified_deposit") {
    return { label: "Unverified deposit", glyph: "?", tone: "amber" };
  }
  if (txAmount(tx) > 0 && revenueState === "non_revenue") {
    return { label: "Non-revenue", glyph: "X", tone: "neutral" };
  }
  const state = record.classification || "other";
  const entity = record.canonical_entity || "";
  const categories = {
    confirmed_lender: { label: entity || "Confirmed lender", glyph: "LEN", tone: "amber" },
    potential_lender: { label: entity ? `${entity} (Potential)` : "Potential lender", glyph: "?", tone: "amber" },
    insurance: { label: entity || "Insurance", glyph: "INS", tone: "blue" },
    lease_or_equipment_financing: { label: "Lease / Equipment", glyph: "LSE", tone: "neutral" },
    fee: { label: "Fee", glyph: "$", tone: "neutral" },
    transfer: { label: "Transfer", glyph: "TR", tone: "neutral" },
    credit_card_payment: { label: "Credit Card Payment", glyph: "CC", tone: "neutral" },
    payroll: { label: "Payroll", glyph: "PAY", tone: "neutral" },
    tax: { label: "Tax", glyph: "TAX", tone: "neutral" },
    utility: { label: "Utility", glyph: "UTL", tone: "neutral" },
    rent: { label: "Rent", glyph: "RNT", tone: "neutral" },
    pos: { label: "Point of Sale", glyph: "POS", tone: "neutral" },
    atm: { label: "ATM", glyph: "ATM", tone: "neutral" },
    nsf_or_return: { label: "NSF / Return", glyph: "!", tone: "red" },
    refund_or_reversal: { label: "Refund / Reversal", glyph: "REV", tone: "green" },
  };
  if (categories[state]) return categories[state];
  const credit = txAmount(tx) >= 0;
  return { label: credit ? "Other Credit" : "Other Debit", glyph: credit ? "+" : "-", tone: "neutral" };
}

function contributesToPotentialTotals(tx) {
  const record = transactionClassification(tx);
  if (record.contributes_to_potential_lender_totals !== undefined) {
    return record.contributes_to_potential_lender_totals === true;
  }
  return record.contributes_to_potential_lender_count === true;
}

function filterTransactions(transactions, filter, canonicalEntity = null) {
  let matched = transactions;
  if (filter === "nsf") matched = transactions.filter((tx) => transactionClassification(tx).classification === "nsf_or_return");
  if (filter === "lender") matched = transactions.filter((tx) => transactionClassification(tx).contributes_to_withholding_rate === true);
  if (filter === "potential") matched = transactions.filter(contributesToPotentialTotals);
  if (filter === "insurance") matched = transactions.filter((tx) => transactionClassification(tx).contributes_to_insurance_totals === true);
  if (filter === "pos") matched = transactions.filter((tx) => transactionClassification(tx).classification === "pos");
  if (["verified_revenue", "unverified_deposit", "non_revenue"].includes(filter)) {
    matched = transactions.filter(
      (tx) => transactionClassification(tx).revenue_classification === filter
    );
  }
  if (!canonicalEntity) return matched;
  return matched.filter((tx) => transactionClassification(tx).canonical_entity === canonicalEntity);
}

function revenueReviewControls(tx, fallbackJobId = null) {
  const record = transactionClassification(tx);
  if (record.revenue_initial_classification !== "unverified_deposit") return "";
  const jobId = tx.source_job || fallbackJobId;
  const sourceLocation = record.source_location;
  if (!jobId || !sourceLocation) return "";
  const common = `data-revenue-review-job="${escapeHtml(jobId)}" data-revenue-review-location="${escapeHtml(sourceLocation)}"`;
  if (record.revenue_review_status === "confirmed" || record.revenue_review_status === "rejected") {
    return `
      <div class="revenue-review-actions">
        <button class="table-action" type="button" ${common} data-revenue-review-action="reset">Reset review</button>
      </div>
    `;
  }
  return `
    <div class="revenue-review-actions">
      <button class="table-action review-confirm" type="button" ${common} data-revenue-review-action="confirm">Confirm</button>
      <button class="table-action review-reject" type="button" ${common} data-revenue-review-action="reject">Reject</button>
    </div>
  `;
}

function txDateValue(tx) {
  const raw = String(tx.date || "").trim();
  if (!raw) return null;
  const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return Date.UTC(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
  const us = raw.match(/^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?/);
  if (us) {
    const year = us[3] ? Number(us[3]) : 2000;
    return Date.UTC(year < 100 ? 2000 + year : year, Number(us[1]) - 1, Number(us[2]));
  }
  const parsed = Date.parse(raw);
  return Number.isNaN(parsed) ? null : parsed;
}

// Stable: rows that cannot be ordered keep their original ledger position.
function sortTransactions(transactions, sort) {
  const decorated = transactions.map((tx, index) => ({ tx, index }));
  if (sort === "credits" || sort === "debits") {
    const direction = sort === "credits" ? -1 : 1;
    decorated.sort((a, b) => (txAmount(a.tx) - txAmount(b.tx)) * direction || a.index - b.index);
  } else {
    decorated.sort((a, b) => {
      const av = txDateValue(a.tx);
      const bv = txDateValue(b.tx);
      if (av === null || bv === null) return a.index - b.index;
      return av - bv || a.index - b.index;
    });
  }
  return decorated.map((entry) => entry.tx);
}

function renderTransactionRows(tableEl, countEl, transactions, filter, currency = "USD", options = {}) {
  if (!tableEl || !countEl) return;
  const {
    sort = "date",
    showSource = false,
    limit = TRANSACTION_PAGE,
    moreEl = null,
    canonicalEntity = null,
    reviewJobId = null,
  } = options;
  const rows = Array.isArray(transactions) ? transactions : [];
  const matched = sortTransactions(filterTransactions(rows, filter, canonicalEntity), sort);
  const visible = matched.slice(0, limit);
  const filterLabel = canonicalEntity || (filter === "all" ? "transactions" : `${filter} matches`);
  countEl.textContent = visible.length < matched.length
    ? `${formatNumber(visible.length)} of ${formatNumber(matched.length)} ${filterLabel}`
    : `${formatNumber(matched.length)} ${filterLabel}`;
  if (moreEl) {
    const remaining = matched.length - visible.length;
    moreEl.hidden = remaining <= 0;
    if (remaining > 0) {
      const next = Math.min(remaining, TRANSACTION_PAGE);
      moreEl.innerHTML = `
        <button class="table-action" type="button" data-more-step="${next}">Show ${formatNumber(next)} more</button>
        <button class="table-action" type="button" data-more-step="all">Show all ${formatNumber(matched.length)}</button>
      `;
    } else {
      moreEl.innerHTML = "";
    }
  }
  const sourceHead = showSource ? "<td>N/A</td>" : "";
  if (!visible.length) {
    tableEl.innerHTML = `
      <tr>
        <td><strong>No transactions found</strong></td>
        <td>${escapeHtml(filter === "all" ? "No statement returned transaction rows." : "No rows matched this filter.")}</td>
        ${sourceHead}
        <td>${glassChip("", "Empty", "neutral")}</td>
        <td>N/A</td>
        <td>N/A</td>
      </tr>
    `;
    return;
  }
  tableEl.innerHTML = visible.map((tx) => {
    const amount = txAmount(tx);
    const category = transactionCategory(tx);
    const source = showSource
      ? `<td class="transaction-source">${escapeHtml(tx.source_document || tx.source_bank || "Statement")}</td>`
      : "";
    return `
      <tr>
        <td><strong>${escapeHtml(tx.date || "N/A")}</strong></td>
        <td class="transaction-desc">${escapeHtml(txDescriptionRaw(tx) || "N/A")}</td>
        ${source}
        <td>${glassChip(category.glyph, category.label, category.tone)}${revenueReviewControls(tx, reviewJobId)}</td>
        <td class="amount-cell ${amount < 0 ? "amount-debit" : "amount-credit"}">${escapeHtml(formatMoney(amount, currency))}</td>
        <td class="amount-cell">${escapeHtml(formatMoney(tx.running_balance, currency))}</td>
      </tr>
    `;
  }).join("");
}

// Single source of truth for the main ledger table: a package shows every
// statement's rows combined, a single upload shows just its own.
function mainTransactionContext() {
  const pkg = currentAnalysis?.package;
  if (pkg) {
    return {
      transactions: Array.isArray(pkg.transactions) ? pkg.transactions : [],
      currency: "USD",
      multi: true,
    };
  }
  const statement = currentAnalysis?.statement || {};
  return {
    transactions: getTransactions(statement),
    currency: statement.currency || "USD",
    multi: false,
  };
}

function renderMainTransactions({ keepLimit = false } = {}) {
  if (!keepLimit) transactionLimit = TRANSACTION_PAGE;
  const ctx = mainTransactionContext();
  if (els.transactionCard) {
    els.transactionCard.style.display = "block";
    els.transactionCard.classList.toggle("multi-statement", ctx.multi);
  }
  if (els.transactionScope) {
    els.transactionScope.textContent = ctx.multi ? "All statements" : "This statement";
  }
  renderTransactionRows(
    els.transactionTable,
    els.transactionCount,
    ctx.transactions,
    transactionFilter,
    ctx.currency,
    {
      sort: transactionSort,
      showSource: ctx.multi,
      limit: transactionLimit,
      moreEl: els.transactionMore,
      canonicalEntity: transactionEntityFilter,
      reviewJobId: currentJobId,
    }
  );
}

function renderModalTransactions({ keepLimit = false } = {}) {
  if (!keepLimit) modalTransactionLimit = TRANSACTION_PAGE;
  const statement = modalAnalysis?.statement || {};
  renderTransactionRows(
    els.statementModalTransactions,
    els.statementModalTransactionCount,
    getTransactions(statement),
    modalTransactionFilter,
    statement.currency || "USD",
    {
      sort: modalTransactionSort,
      limit: modalTransactionLimit,
      moreEl: els.statementModalTransactionMore,
      canonicalEntity: modalTransactionEntityFilter,
      reviewJobId: modalJobId,
    }
  );
}

function setTransactionFilterButtons(selector, activeValue) {
  const attribute = selector.replace(/^\[|\]$/g, "");
  document.querySelectorAll(selector).forEach((button) => {
    const isActive = button.getAttribute(attribute) === activeValue;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
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
  if (els.transactionCard) els.transactionCard.style.display = "block";
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
  renderInsurance([]);
  renderRevenueEvidence({
    total_posted_credit_count: 0,
    verified_revenue_count: 0,
    verified_revenue_total: 0,
    unverified_deposit_count: 0,
    unverified_deposit_total: 0,
    non_revenue_count: 0,
    non_revenue_total: 0,
  });
  renderMainTransactions();
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

// Legacy metric codes -> [monochrome glyph, plain-language label]
const CHIP_VOCABULARY = {
  CR: ["↑", "Credits"],
  DB: ["↓", "Debits"],
  DEP: ["↧", "Deposits"],
  AVG: ["◎", "Average"],
  ADB: ["◎", "Daily Average"],
  CF: ["⇄", "Cash Flow"],
  ACH: ["⇄", "ACH"],
  NSF: ["⚠", "NSF"],
  OK: ["✓", "Approved"],
  REV: ["◐", "Review"],
  ERR: ["✕", "Error"],
  DOC: ["◈", "Integrity"],
  LEN: ["⌂", "Lender"],
  POS: ["▤", "Point of Sale"],
  ATM: ["▣", "ATM"],
  CHK: ["✎", "Checks"],
  END: ["◍", "Ending"],
  HIGH: ["▲", "Highest"],
  LOW: ["▼", "Lowest"],
  "%": ["%", "Rate"],
};

const CHIP_TONES = { green: "success", red: "error", blue: "info", amber: "warning", neutral: "neutral" };

/* Colour restraint: a chip is tinted only when it reports something the
   reviewer should act on. Anything purely informational stays neutral
   frosted glass, so an accent colour anywhere on screen means "look here". */
function countTone(value) {
  return numberOrNull(value) ? "red" : "neutral";
}

function presenceTone(value) {
  return numberOrNull(value) ? "amber" : "neutral";
}

function negativeTone(value) {
  const n = numberOrNull(value);
  return n !== null && n < 0 ? "red" : "neutral";
}

function withholdingTone(value) {
  const n = numberOrNull(value);
  if (n === null || n <= 0) return "neutral";
  return n >= 20 ? "red" : "amber";
}

function integrityTone(integrity = {}) {
  if (integrity.risk_level === "high") return "red";
  if (integrity.risk_level === "review") return "amber";
  return "neutral";
}

/* Average Daily Balance is supplied by the validated backend daily ledger. */
function averageBalanceNote(metrics = {}) {
  const days = numberOrNull(metrics.calendar_day_count);
  const span = days ? `${formatNumber(days)} calendar days` : "the statement period";
  if (metrics.average_daily_balance === null || metrics.average_daily_balance === undefined) {
    return "No average balance available";
  }
  return `Daily ending balances across ${span}`;
}

function averageBalanceTone(metrics = {}) {
  return metrics.average_daily_balance === null || metrics.average_daily_balance === undefined ? "amber" : "neutral";
}

/* Package rollup: days-weighted validated statement ADB values from the API. */
function packageAverageBalanceNote(documents = []) {
  const ready = documents.filter((doc) => doc && doc.average_daily_balance !== null && doc.average_daily_balance !== undefined);
  if (!ready.length) return "Days-weighted across statement periods";
  const days = ready.reduce((sum, doc) => sum + (numberOrNull(doc.adb_calendar_days) || 0), 0);
  const span = days ? `${formatNumber(days)} calendar days` : "statement periods";
  return `Days-weighted across ${span}`;
}

function packageAverageBalanceTone() {
  return "neutral";
}

function chipTone(tone) {
  return CHIP_TONES[tone] || "neutral";
}

function glassChip(glyph, text, tone, extraClass = "") {
  const classes = ["glass-chip", chipTone(tone), extraClass].filter(Boolean).join(" ");
  const mark = glyph ? `<span class="chip-glyph" aria-hidden="true">${escapeHtml(glyph)}</span>` : "";
  return `<span class="${escapeHtml(classes)}">${mark}<span class="chip-text">${escapeHtml(text)}</span></span>`;
}

function metricChip(icon, tone) {
  if (!icon) return "";
  const [glyph, text] = CHIP_VOCABULARY[icon] || ["", icon];
  return glassChip(glyph, text, tone, "metric-chip");
}

function renderMetricCard([label, value, sub, icon, tone, action]) {
  const actionable = action && action.revenueFilter;
  const tag = actionable ? "button" : "article";
  const attributes = actionable
    ? ` type="button" data-revenue-filter="${escapeHtml(action.revenueFilter)}" aria-label="Show exact ${escapeHtml(label)} transactions"`
    : "";
  return `
    <${tag} class="metric${actionable ? " metric-action" : ""}"${attributes}>
      <div class="metric-top">
        <div class="metric-label">${escapeHtml(label)}</div>
        ${metricChip(icon, tone)}
      </div>
      <div class="metric-value">${escapeHtml(value)}</div>
      <div class="metric-sub">${escapeHtml(sub || "")}</div>
    </${tag}>
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

function lenderEvidenceControl(funder, potential) {
  const entity = funder.funder || funder.lender || "";
  if (!entity) return "<strong>Unknown lender</strong>";
  const filter = potential ? "potential" : "lender";
  return `
    <button
      class="evidence-link"
      type="button"
      data-lender-evidence-filter="${filter}"
      data-lender-evidence-entity="${escapeHtml(entity)}"
      aria-label="Show exact transaction evidence for ${escapeHtml(entity)}"
    >${escapeHtml(entity)}</button>
  `;
}

function lenderRowHtml(funder, currency = "USD") {
  const isPotential = funder.classification === "potential_lender";
  const count = isPotential
    ? funder.potential_lender_debit_count
      ?? funder.debit_count
      ?? (Array.isArray(funder.transactions) ? funder.transactions.length : null)
    : funder.debit_count
      ?? (Array.isArray(funder.transactions) ? funder.transactions.length : null);
  const total = isPotential
    ? funder.potential_lender_debit_total ?? funder.total_debited ?? funder.balance
    : funder.total_debited ?? funder.balance;
  const denominator = isPotential
    ? funder.eligible_deposit_denominator ?? funder.potential_withholding_denominator
    : null;
  const totalNumber = numberOrNull(total);
  const denominatorNumber = numberOrNull(denominator);
  let exposure = isPotential ? funder.potential_withholding_exposure : null;
  if (
    isPotential
    && numberOrNull(exposure) === null
    && totalNumber !== null
    && (denominatorNumber ?? 0) > 0
  ) {
    exposure = Math.abs(totalNumber) / denominatorNumber * 100;
  }
  const potentialWithholding = isPotential && (denominatorNumber ?? 0) > 0
    ? `
      <strong>${escapeHtml(formatPercent(exposure))}</strong>
      <div class="table-cell-detail">${escapeHtml(formatMoney(denominator, currency))} eligible deposits</div>
    `
    : isPotential ? "N/A" : "--";
  return `
    <tr>
      <td>${lenderEvidenceControl(funder, isPotential)}</td>
      <td>${escapeHtml(isPotential ? "Potential lender" : "Confirmed lender")}</td>
      <td>${escapeHtml(formatNumber(count))}</td>
      <td>${escapeHtml(formatMoney(total, currency))}</td>
      <td>${potentialWithholding}</td>
      <td>${glassChip(isPotential ? "?" : "LEN", isPotential ? "Review required" : "Confirmed", "amber")}</td>
    </tr>
  `;
}

function renderLenders(funders, potentialLenders = [], currency = "USD") {
  const confirmed = Array.isArray(funders) ? funders : [];
  const potential = Array.isArray(potentialLenders) ? potentialLenders : [];
  const lenders = [
    ...confirmed.map((item) => ({ ...item, classification: "confirmed_lender" })),
    ...potential.map((item) => ({ ...item, classification: "potential_lender" })),
  ];
  els.lenderCount.textContent = `${confirmed.length} confirmed, ${potential.length} potential`;
  if (!lenders.length) {
    els.lenderTable.innerHTML = `
      <tr>
        <td><strong>No lenders detected</strong></td>
        <td>Bank statement</td>
        <td>0</td>
        <td>${escapeHtml(formatMoney(0, currency))}</td>
        <td>--</td>
        <td>${glassChip("✓", "Clear", "green")}</td>
      </tr>
    `;
    return;
  }
  els.lenderTable.innerHTML = lenders.map((funder) => lenderRowHtml(funder, currency)).join("");
}

function renderInsurance(providers, currency = "USD") {
  if (!els.insuranceTable || !els.insuranceCount) return;
  const rows = Array.isArray(providers) ? providers : [];
  const count = rows.reduce((total, item) => total + Number(item.count || 0), 0);
  els.insuranceCount.textContent = `${formatNumber(count)} ${count === 1 ? "debit" : "debits"}`;
  if (!rows.length) {
    els.insuranceTable.innerHTML = `
      <tr>
        <td><strong>No insurance debits detected</strong></td>
        <td>0</td>
        <td>${escapeHtml(formatMoney(0, currency))}</td>
        <td>${glassChip("INS", "Clear", "green")}</td>
      </tr>
    `;
    return;
  }
  els.insuranceTable.innerHTML = rows.map((provider) => `
    <tr>
      <td><strong>${escapeHtml(provider.provider || "Insurance provider not identified")}</strong></td>
      <td>${escapeHtml(formatNumber(provider.count))}</td>
      <td>${escapeHtml(formatMoney(provider.total_debited, currency))}</td>
      <td>${glassChip("INS", "Insurance", "blue")}</td>
    </tr>
  `).join("");
}

const revenueRows = [
  ["verified_revenue", "Verified revenue", "REV", "Verified", "green"],
  ["unverified_deposit", "Unverified deposits", "?", "Review required", "amber"],
  ["non_revenue", "Non-revenue", "X", "Excluded", "neutral"],
];

function revenueEvidenceRowsHtml(metrics = {}, currency = "USD", modal = false) {
  return revenueRows.map(([state, label, glyph, status, tone]) => {
    const countKey = state === "verified_revenue"
      ? "verified_revenue_count"
      : `${state}_count`;
    const totalKey = state === "verified_revenue"
      ? "verified_revenue_total"
      : `${state}_total`;
    const filterAttribute = modal ? "data-modal-revenue-filter" : "data-revenue-filter";
    return `
      <tr>
        <td><button class="evidence-link" type="button" ${filterAttribute}="${state}" aria-label="Show exact ${escapeHtml(label)} transactions">${escapeHtml(label)}</button></td>
        <td>${escapeHtml(formatNumber(metrics[countKey]))}</td>
        <td>${escapeHtml(formatMoney(metrics[totalKey], currency))}</td>
        <td>${glassChip(glyph, status, tone)}</td>
      </tr>
    `;
  }).join("");
}

function renderRevenueEvidence(metrics = {}, currency = "USD") {
  if (!els.revenueTable || !els.revenueCount) return;
  els.revenueTable.innerHTML = revenueEvidenceRowsHtml(metrics, currency, false);
  els.revenueCount.textContent = `${formatNumber(metrics.total_posted_credit_count)} posted credits`;
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
  const potentialLenders = detection.potential_lenders || [];
  const insuranceProviders = detection.insurance_providers || [];
  const totalCredits = metrics.effective_total_deposits;
  const totalDebits = metrics.effective_total_withdrawals;
  const confidence = confidenceFrom(report);
  const elapsed = startedAt ? `${((Date.now() - startedAt) / 1000).toFixed(1)}s` : "Complete";
  const decision = hasMaterialPotentialLenderDebits(metrics) || metrics.revenue_review_required
    ? "review_required"
    : quality.corporate_use || quality.level || "review_required";

  els.statusHeading.textContent = "OCR completed";
  setBanner("done", "Extraction completed", `${confidence}%`);
  els.decisionPill.textContent = labelize(decision);
  els.decisionPill.className = `decision-pill ${decision}`.trim();

  setStatusRows([
    ["OCR completed", "Yes"],
    ["Pages processed", formatNumber(statement.page_count || report.page_count || "--")],
    ["Processing time", elapsed],
    ["Parsing mode", parseModeLabel(report.parse_mode || selectedParseMode())],
    ["Parser used", report.model_used || "N/A"],
    ["Document integrity", integrityLabel(integrity)],
    ["Revenue reconciliation", metrics.revenue_reconciles ? "Balanced" : "Review required"],
    ["Withholding denominator", metrics.withholding_denominator_label || "Legacy eligible deposits"],
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
        ["Verified Revenue", formatMoney(metrics.verified_revenue_total, currency), `${formatNumber(metrics.verified_revenue_count)} verified credits`, "REV", "green", { revenueFilter: "verified_revenue" }],
        ["Unverified Deposits", formatMoney(metrics.unverified_deposit_total, currency), `${formatNumber(metrics.unverified_deposit_count)} deposits require review`, "?", "amber", { revenueFilter: "unverified_deposit" }],
        ["Non-Revenue", formatMoney(metrics.non_revenue_total, currency), `${formatNumber(metrics.non_revenue_count)} excluded credits`, "X", "neutral", { revenueFilter: "non_revenue" }],
        ["Maximum Revenue", formatMoney(metrics.maximum_revenue, currency), "Verified plus unverified deposits", "MAX", "neutral"],
        ["ACH Credits", formatNumber(metrics.ach_credit_count), "Incoming ACH deposits", "ACH", "neutral"],
      ],
    },
    {
      title: "Debits",
      sub: "Outgoing money",
      items: [
        ["Total Debits", formatMoney(totalDebits, currency), "All debit outflows", "DB", "neutral"],
        ["Confirmed Withholding", formatPercent(metrics.withholding_rate), withholdingAuditNote(metrics, currency), "%", withholdingTone(metrics.withholding_rate)],
        ["ACH Debits", formatNumber(metrics.ach_debit_count), "Outgoing ACH debits", "ACH", "neutral"],
        ["POS Transactions", formatNumber(metrics.pos_count), "Card point-of-sale debits", "POS", "neutral"],
        ["ATM Withdrawals", formatNumber(metrics.atm_withdrawal_count), "ATM cash withdrawals", "ATM", "neutral"],
        ["Checks Detected", formatNumber(metrics.check_count), "Check transactions found", "CHK", "neutral"],
      ],
    },
    {
      title: "Risk Signals",
      sub: "NSFs and balances",
      items: [
        ["NSFs", formatNumber(metrics.effective_nsf_count), metrics.nsf_source || "Returned item detection", "NSF", countTone(metrics.effective_nsf_count)],
        ["Document Integrity", integrityLabel(integrity), (integrity.flags || []).join(", ") || "No source contradictions detected", "DOC", integrityTone(integrity)],
        ["Average Daily Balance", formatMoney(metrics.average_daily_balance, currency), averageBalanceNote(metrics), "AVG", averageBalanceTone(metrics)],
        ["Ending Balance", formatMoney(statement.ending_balance, currency), "Statement close balance", "END", "neutral"],
        ["Lowest Balance", formatMoney(metrics.min_balance, currency), "Lowest daily balance", "LOW", negativeTone(metrics.min_balance)],
        ["Highest Balance", formatMoney(metrics.max_balance, currency), "Highest daily balance", "HIGH", "neutral"],
      ],
    },
    {
      title: "Lenders",
      sub: "Classified funding and insurance activity",
      items: [
        ["Confirmed Lenders", formatNumber(metrics.lenders_detected), "Distinct confirmed entities", "LEN", presenceTone(metrics.lenders_detected)],
        ["Potential Lenders", formatNumber(metrics.potential_lenders_detected), "Distinct entities requiring review", "?", countTone(metrics.potential_lenders_detected)],
        ["Confirmed Lender Debit Count", formatNumber(metrics.lender_debit_count), "Qualifying confirmed debit rows", "DB", "neutral"],
        ["Confirmed Lender Debits", formatMoney(metrics.lender_debits, currency), "Confirmed withholding numerator", "$", "neutral"],
        ["Potential Lender Debit Count", formatNumber(metrics.potential_lender_debit_count), "Exact candidate evidence rows", "DB", countTone(metrics.potential_lender_debit_count)],
        ["Potential Lender Debits", formatMoney(potentialLenderDebitTotal(metrics), currency), "Excluded from confirmed lender metrics", "$", countTone(metrics.potential_lender_debit_count)],
        ["Active Withholding Denominator", formatMoney(metrics.potential_withholding_denominator ?? metrics.eligible_deposits, currency), activeDenominatorNote(metrics), "DEP", "neutral"],
        ["Potential Withholding Exposure", formatPercent(metrics.potential_withholding_exposure), potentialWithholdingAuditNote(metrics, currency), "%", hasMaterialPotentialLenderDebits(metrics) ? "amber" : "neutral"],
        ["Insurance Debits", formatNumber(metrics.insurance_count), "Posted insurance debit rows", "INS", "neutral"],
        ["Insurance Total", formatMoney(metrics.insurance_total, currency), "Insurance debits excluded from lenders", "$", "neutral"],
      ],
    },
  ]);
  renderAccountSummary(accountFieldRows(statement, currentMarkdown));
  renderRevenueEvidence(metrics, currency);
  renderLenders(funders, potentialLenders, currency);
  renderInsurance(insuranceProviders, currency);
  renderMainTransactions();
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
  transactionFilter = "all";
  transactionEntityFilter = null;
  setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
  startedAt = Date.now();
  showSelectedFile(file);
  setActions(null, false);
  setProgress(true);
  els.statusHeading.textContent = "Uploading PDF";
  setBanner("pending", "Uploading PDF", "--");
  renderAccountSummary(accountFieldRows());
  renderMainTransactions();
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
  renderMainTransactions();
  const totals = pkg.totals || {};
  const documents = Array.isArray(pkg.documents) ? pkg.documents : [];
  const funders = Array.isArray(pkg.funders) ? pkg.funders : [];
  const potentialLenders = Array.isArray(pkg.potential_lenders) ? pkg.potential_lenders : [];
  const insuranceProviders = Array.isArray(pkg.insurance_providers) ? pkg.insurance_providers : [];
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
    ["Confirmed withholding", formatPercent(totals.package_withholding_rate)],
    ["Potential exposure", formatPercent(totals.potential_withholding_exposure)],
    ["Revenue reconciliation", totals.revenue_reconciles ? "Balanced" : "Review required"],
    ["Withholding denominator", totals.withholding_denominator_label || "Legacy eligible deposits"],
  ]);

  renderMetricSections([
    {
      title: "Package Revenue",
      sub: `${formatNumber(totals.months)} statement periods`,
      items: [
        ["Total Credits", formatMoney(totals.total_credits), "Combined incoming money", "CR", "green"],
        ["Verified Revenue", formatMoney(totals.verified_revenue_total), `${formatNumber(totals.verified_revenue_count)} verified credits`, "REV", "green", { revenueFilter: "verified_revenue" }],
        ["Unverified Deposits", formatMoney(totals.unverified_deposit_total), `${formatNumber(totals.unverified_deposit_count)} deposits require review`, "?", "amber", { revenueFilter: "unverified_deposit" }],
        ["Non-Revenue", formatMoney(totals.non_revenue_total), `${formatNumber(totals.non_revenue_count)} excluded credits`, "X", "neutral", { revenueFilter: "non_revenue" }],
        ["Maximum Revenue", formatMoney(totals.maximum_revenue), "Verified plus unverified deposits", "MAX", "neutral"],
        ["Avg Monthly Credits", formatMoney(totals.avg_monthly_credits), "Monthly revenue baseline", "AVG", "neutral"],
        ["Total Debits", formatMoney(totals.total_debits), "Combined outgoing money", "DB", "neutral"],
        ["Avg Monthly Debits", formatMoney(totals.avg_monthly_debits), "Monthly expense baseline", "AVG", "neutral"],
      ],
    },
    {
      title: "Cash Flow",
      sub: "Package-level affordability signals",
      items: [
        ["Total Cash Flow", formatMoney(totals.cash_flow), "Credits minus debits", "CF", negativeTone(totals.cash_flow)],
        ["Avg Monthly Cash Flow", formatMoney(totals.avg_monthly_cash_flow), "Average statement cash flow", "AVG", negativeTone(totals.avg_monthly_cash_flow)],
        ["Average Daily Balance", formatMoney(totals.average_daily_balance), packageAverageBalanceNote(documents), "ADB", packageAverageBalanceTone(documents)],
        ["NSFs", formatNumber(totals.nsf_count), "Total returned items", "NSF", countTone(totals.nsf_count)],
        ["Confirmed Withholding", formatPercent(totals.package_withholding_rate), withholdingAuditNote(totals), "%", withholdingTone(totals.package_withholding_rate)],
      ],
    },
    {
      title: "Quality",
      sub: "Corporate-use readiness",
      items: [
        ["Approved", formatNumber(totals.approved), "Corporate-approved statements", "OK", totals.approved ? "green" : "neutral"],
        ["Manual Review", formatNumber(totals.manual_review), "Statements withheld from automated approval", "REV", totals.manual_review ? "amber" : "neutral"],
        ["Integrity High", formatNumber(totals.integrity_high), "Possible document issue", "DOC", countTone(totals.integrity_high)],
        ["Failed", formatNumber(totals.failed), "Statements needing rerun", "ERR", countTone(totals.failed)],
      ],
    },
    {
      title: "Lenders",
      sub: "Classified funding and insurance activity",
      items: [
        ["Confirmed Lenders", formatNumber(totals.lenders_detected), "Distinct confirmed entities", "LEN", presenceTone(totals.lenders_detected)],
        ["Potential Lenders", formatNumber(totals.potential_lenders_detected), "Distinct entities requiring review", "?", countTone(totals.potential_lenders_detected)],
        ["Confirmed Lender Debit Count", formatNumber(totals.lender_debit_count), "Qualifying confirmed debit rows", "DB", "neutral"],
        ["Confirmed Lender Debits", formatMoney(totals.lender_debits), "Confirmed withholding numerator", "$", "neutral"],
        ["Potential Lender Debit Count", formatNumber(totals.potential_lender_debit_count), "Exact candidate evidence rows", "DB", countTone(totals.potential_lender_debit_count)],
        ["Potential Lender Debits", formatMoney(potentialLenderDebitTotal(totals)), "Excluded from confirmed lender metrics", "$", countTone(totals.potential_lender_debit_count)],
        ["Active Withholding Denominator", formatMoney(totals.potential_withholding_denominator ?? totals.eligible_deposits), activeDenominatorNote(totals), "DEP", "neutral"],
        ["Potential Withholding Exposure", formatPercent(totals.potential_withholding_exposure), potentialWithholdingAuditNote(totals), "%", hasMaterialPotentialLenderDebits(totals) ? "amber" : "neutral"],
        ["Insurance Debits", formatNumber(totals.insurance_count), "Posted insurance debit rows", "INS", "neutral"],
        ["Insurance Total", formatMoney(totals.insurance_total), "Excluded from lender metrics", "$", "neutral"],
      ],
    },
  ]);

  renderAccountSummary([
    ["Package Decision", labelize(totals.decision || "review required")],
    ["Statements", `${formatNumber(totals.completed)} completed of ${formatNumber(totals.documents)}`],
    ["Period Range", packagePeriod(documents)],
    ["Average Daily Balance", formatMoney(totals.average_daily_balance)],
    ["Top Lenders", funders.length ? funders.slice(0, 3).map((f) => f.funder).join(", ") : "None detected"],
    ["Confirmed Lender Debits", formatMoney(totals.lender_debits)],
    ["Potential Lender Debits", formatMoney(potentialLenderDebitTotal(totals))],
    ["Potential Exposure", formatPercent(totals.potential_withholding_exposure)],
  ]);
  renderPackageTables(pkg);
}

function renderPackageTables(pkg) {
  const documents = Array.isArray(pkg.documents) ? pkg.documents : [];
  const funders = Array.isArray(pkg.funders) ? pkg.funders : [];
  const potentialLenders = Array.isArray(pkg.potential_lenders) ? pkg.potential_lenders : [];
  const insuranceProviders = Array.isArray(pkg.insurance_providers) ? pkg.insurance_providers : [];
  renderLenders(funders, potentialLenders, "USD");
  renderInsurance(insuranceProviders, "USD");
  renderRevenueEvidence(pkg.totals || {}, "USD");
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
        <td>${glassChip("◐", "Review", "amber")}</td>
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
          <td>${escapeHtml(formatMoney(doc.average_daily_balance))}</td>
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
  modalJobId = jobId;
  modalTransactionFilter = "all";
  modalTransactionEntityFilter = null;
  setTransactionFilterButtons("[data-modal-transaction-filter]", modalTransactionFilter);
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
      <td>N/A</td>
      <td>N/A</td>
      <td>${glassChip("◐", "Pending", "blue")}</td>
    </tr>
  `;
  if (els.statementModalInsurance) {
    els.statementModalInsurance.innerHTML = `
      <tr>
        <td><strong>Loading</strong></td>
        <td>N/A</td>
        <td>N/A</td>
        <td>${glassChip("INS", "Pending", "blue")}</td>
      </tr>
    `;
  }
  if (els.statementModalRevenue) {
    els.statementModalRevenue.innerHTML = `
      <tr>
        <td><strong>Loading</strong></td>
        <td>N/A</td>
        <td>N/A</td>
        <td>${glassChip("REV", "Pending", "blue")}</td>
      </tr>
    `;
  }
  renderTransactionRows(els.statementModalTransactions, els.statementModalTransactionCount, [], modalTransactionFilter, "USD", { sort: modalTransactionSort });
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
          <td>N/A</td>
          <td>N/A</td>
          <td>${glassChip("◐", "Review", "amber")}</td>
        </tr>
      `;
      if (els.statementModalInsurance) {
        els.statementModalInsurance.innerHTML = `
          <tr>
            <td><strong>Unable to load statement</strong></td>
            <td>N/A</td>
            <td>N/A</td>
            <td>${glassChip("INS", "Review", "amber")}</td>
          </tr>
        `;
      }
      if (els.statementModalRevenue) {
        els.statementModalRevenue.innerHTML = `
          <tr>
            <td><strong>Unable to load revenue evidence</strong></td>
            <td>N/A</td>
            <td>N/A</td>
            <td>${glassChip("REV", "Review", "amber")}</td>
          </tr>
        `;
      }
      renderTransactionRows(els.statementModalTransactions, els.statementModalTransactionCount, [], modalTransactionFilter, "USD", { sort: modalTransactionSort });
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
  const potentialLenders = Array.isArray(detection.potential_lenders) ? detection.potential_lenders : [];
  const insuranceProviders = Array.isArray(detection.insurance_providers) ? detection.insurance_providers : [];
  const lenderRows = [
    ...funders.map((item) => ({ ...item, classification: "confirmed_lender" })),
    ...potentialLenders.map((item) => ({ ...item, classification: "potential_lender" })),
  ];
  const title = statement.bank ? `${statement.bank} Statement` : "Bank Statement";
  const decision = hasMaterialPotentialLenderDebits(metrics) || metrics.revenue_review_required
    ? "review_required"
    : quality.corporate_use || quality.level || "review_required";

  els.statementModalTitle.textContent = title;
  els.statementModalSubtitle.textContent = `${period(statement)} - ${labelize(decision)}`;
  els.statementModalMetrics.innerHTML = [
    ["Total Credits", formatMoney(metrics.effective_total_deposits, currency), "Incoming money", "CR", "green"],
    ["Verified Revenue", `${formatNumber(metrics.verified_revenue_count)} / ${formatMoney(metrics.verified_revenue_total, currency)}`, "Verified operating credits", "REV", "green", { revenueFilter: "verified_revenue" }],
    ["Unverified Deposits", `${formatNumber(metrics.unverified_deposit_count)} / ${formatMoney(metrics.unverified_deposit_total, currency)}`, "Review required", "?", "amber", { revenueFilter: "unverified_deposit" }],
    ["Non-Revenue", `${formatNumber(metrics.non_revenue_count)} / ${formatMoney(metrics.non_revenue_total, currency)}`, "Excluded credits", "X", "neutral", { revenueFilter: "non_revenue" }],
    ["Maximum Revenue", formatMoney(metrics.maximum_revenue, currency), "Verified plus unverified deposits", "MAX", "neutral"],
    ["Total Debits", formatMoney(metrics.effective_total_withdrawals, currency), "Outgoing money", "DB", "neutral"],
    ["Cash Flow", formatMoney(metrics.cash_flow, currency), "Credits minus debits", "CF", negativeTone(metrics.cash_flow)],
    ["Average Daily Balance", formatMoney(metrics.average_daily_balance, currency), averageBalanceNote(metrics), "AVG", averageBalanceTone(metrics)],
    ["Ending Balance", formatMoney(statement.ending_balance, currency), "Statement close balance", "END", "neutral"],
    ["NSFs", formatNumber(metrics.effective_nsf_count), "Returned items", "NSF", countTone(metrics.effective_nsf_count)],
    ["Confirmed Withholding", formatPercent(metrics.withholding_rate), withholdingAuditNote(metrics, currency), "%", withholdingTone(metrics.withholding_rate)],
    ["Confirmed Lenders", formatNumber(metrics.lenders_detected), "Distinct confirmed entities", "LEN", presenceTone(metrics.lenders_detected)],
    ["Potential Lenders", formatNumber(metrics.potential_lenders_detected), "Distinct entities requiring review", "?", countTone(metrics.potential_lenders_detected)],
    ["Confirmed Lender Debits", `${formatNumber(metrics.lender_debit_count)} / ${formatMoney(metrics.lender_debits, currency)}`, "Count and confirmed numerator", "DB", "neutral"],
    ["Potential Lender Debits", `${formatNumber(metrics.potential_lender_debit_count)} / ${formatMoney(potentialLenderDebitTotal(metrics), currency)}`, "Exact candidate evidence rows and total", "?", countTone(metrics.potential_lender_debit_count)],
    ["Active Withholding Denominator", formatMoney(metrics.potential_withholding_denominator ?? metrics.eligible_deposits, currency), activeDenominatorNote(metrics), "DEP", "neutral"],
    ["Potential Withholding Exposure", formatPercent(metrics.potential_withholding_exposure), potentialWithholdingAuditNote(metrics, currency), "%", hasMaterialPotentialLenderDebits(metrics) ? "amber" : "neutral"],
    ["Insurance", `${formatNumber(metrics.insurance_count)} / ${formatMoney(metrics.insurance_total, currency)}`, "Count and total excluded from lenders", "INS", "neutral"],
    ["Document Integrity", integrityLabel(integrity), (integrity.flags || []).join(", ") || "No source contradictions detected", "DOC", integrityTone(integrity)],
    ["Status", labelize(decision), "Corporate-use and lender-review status", "OK", decision === "approved" ? "green" : "amber"],
  ].map(renderMetricCard).join("");
  els.statementModalAccount.innerHTML = summaryRowsHtml(accountFieldRows(statement, markdown));

  if (!lenderRows.length) {
    els.statementModalLenders.innerHTML = `
      <tr>
        <td><strong>No lenders detected</strong></td>
        <td>Bank statement</td>
        <td>0</td>
        <td>${escapeHtml(formatMoney(0, currency))}</td>
        <td>--</td>
        <td>${glassChip("✓", "Clear", "green")}</td>
      </tr>
    `;
  } else {
    els.statementModalLenders.innerHTML = lenderRows
      .map((funder) => lenderRowHtml(funder, currency))
      .join("");
  }
  if (els.statementModalInsurance) {
    els.statementModalInsurance.innerHTML = insuranceProviders.length
      ? insuranceProviders.map((provider) => `
        <tr>
          <td><strong>${escapeHtml(provider.provider || "Insurance provider not identified")}</strong></td>
          <td>${escapeHtml(formatNumber(provider.count))}</td>
          <td>${escapeHtml(formatMoney(provider.total_debited, currency))}</td>
          <td>${glassChip("INS", "Insurance", "blue")}</td>
        </tr>
      `).join("")
      : `
        <tr>
          <td><strong>No insurance debits detected</strong></td>
          <td>0</td>
          <td>${escapeHtml(formatMoney(0, currency))}</td>
          <td>${glassChip("INS", "Clear", "green")}</td>
        </tr>
      `;
  }
  if (els.statementModalRevenue) {
    els.statementModalRevenue.innerHTML = revenueEvidenceRowsHtml(metrics, currency, true);
  }
  renderModalTransactions();

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
  modalJobId = null;
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
      `${formatNumber(totals.nsf_count)} NSF events, ${formatPercent(totals.package_withholding_rate)} confirmed withholding, ` +
      `${formatMoney(potentialLenderDebitTotal(totals))} potential lender debits and ${formatPercent(totals.potential_withholding_exposure)} potential exposure. ` +
      `${formatNumber(funders.length)} confirmed lender detections. Decision: ${labelize(totals.decision || "review required")}.`;
    return;
  }
  const s = currentAnalysis.statement || {};
  const m = currentAnalysis.metrics || {};
  const d = currentAnalysis.detection || {};
  const q = currentAnalysis.quality || {};
  const currency = s.currency || "USD";
  const lenders = Array.isArray(d.known_funders) ? d.known_funders.length : 0;
  const decision = hasMaterialPotentialLenderDebits(m)
    ? "review_required"
    : q.corporate_use || q.level || "review_required";
  els.summaryBox.textContent =
    `${s.bank || "Statement"} ${period(s)}: average daily balance ${formatMoney(m.average_daily_balance, currency)}, ` +
    `ending balance ${formatMoney(s.ending_balance, currency)}, cash flow ${formatMoney(m.cash_flow, currency)}, ` +
    `${formatNumber(m.effective_nsf_count)} NSF events, ${formatNumber(lenders)} confirmed lender detections, ` +
    `${formatMoney(m.lender_debits, currency)} confirmed lender debits, and ` +
    `${formatMoney(potentialLenderDebitTotal(m), currency)} potential lender debits at ${formatPercent(m.potential_withholding_exposure)} exposure. ` +
    `Status: ${labelize(decision)}.`;
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

/* Gentle parallax: the illustration leans a few pixels toward the pointer
   while a file is being dragged over the zone, so it reads as a physical
   object floating above the surface rather than a flat graphic. */
const PARALLAX_RANGE = 7;
function setDropzoneParallax(event) {
  const bounds = els.dropzone.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const x = (event.clientX - bounds.left) / bounds.width - 0.5;
  const y = (event.clientY - bounds.top) / bounds.height - 0.5;
  els.dropzone.style.setProperty("--tilt-x", `${(x * PARALLAX_RANGE).toFixed(2)}px`);
  els.dropzone.style.setProperty("--tilt-y", `${(y * PARALLAX_RANGE * 0.6).toFixed(2)}px`);
}

function clearDropzoneParallax() {
  els.dropzone.style.removeProperty("--tilt-x");
  els.dropzone.style.removeProperty("--tilt-y");
}

["dragenter", "dragover"].forEach((eventName) => {
  els.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropzone.classList.add("drag");
    setDropzoneParallax(event);
  });
});

["dragleave", "drop"].forEach((eventName) => {
  els.dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropzone.classList.remove("drag");
    clearDropzoneParallax();
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

function revenueFilterFromEvent(event, attribute = "data-revenue-filter") {
  const target = event.target instanceof Element ? event.target : null;
  const control = target ? target.closest(`[${attribute}]`) : null;
  return control ? control.getAttribute(attribute) : null;
}

function showMainRevenueEvidence(filter) {
  if (!filter) return;
  transactionFilter = filter;
  transactionEntityFilter = null;
  setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
  renderMainTransactions();
  els.transactionCard?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showModalRevenueEvidence(filter) {
  if (!filter) return;
  modalTransactionFilter = filter;
  modalTransactionEntityFilter = null;
  setTransactionFilterButtons("[data-modal-transaction-filter]", modalTransactionFilter);
  renderModalTransactions();
  els.statementModalTransactions?.closest(".modal-panel")?.scrollIntoView({ block: "start" });
}

els.metricsGrid?.addEventListener("click", (event) => {
  showMainRevenueEvidence(revenueFilterFromEvent(event));
});
els.revenueTable?.addEventListener("click", (event) => {
  showMainRevenueEvidence(revenueFilterFromEvent(event));
});
els.statementModalMetrics?.addEventListener("click", (event) => {
  showModalRevenueEvidence(revenueFilterFromEvent(event));
});
els.statementModalRevenue?.addEventListener("click", (event) => {
  showModalRevenueEvidence(revenueFilterFromEvent(event, "data-modal-revenue-filter"));
});

async function submitRevenueReview(button) {
  const jobId = button.getAttribute("data-revenue-review-job");
  const sourceLocation = button.getAttribute("data-revenue-review-location");
  const decision = button.getAttribute("data-revenue-review-action");
  if (!jobId || !sourceLocation || !decision) return;
  button.disabled = true;
  try {
    const response = await fetch(`/analysis/${encodeURIComponent(jobId)}/revenue-review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_location: sourceLocation, decision }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.analysis) {
      throw new Error(payload.error || `Revenue review failed (${response.status})`);
    }

    if (currentJobIds.length > 1) {
      const packageResponse = await fetch(
        `/package_analysis?ids=${encodeURIComponent(currentJobIds.join(","))}`
      );
      if (!packageResponse.ok) throw new Error("Package refresh failed");
      renderPackageAnalysis(await packageResponse.json());
      setPackageActions(currentJobIds);
    } else if (currentJobId === jobId) {
      renderAnalysis(payload.analysis);
      setActions(jobId, true);
    }

    if (modalJobId === jobId) {
      modalAnalysis = payload.analysis;
      renderStatementModal(jobId, payload.analysis, "");
    }
  } catch (error) {
    button.disabled = false;
    window.alert(error.message || String(error));
  }
}

function handleRevenueReviewClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  const button = target ? target.closest("[data-revenue-review-action]") : null;
  if (button) submitRevenueReview(button);
}

els.transactionTable?.addEventListener("click", handleRevenueReviewClick);
els.statementModalTransactions?.addEventListener("click", handleRevenueReviewClick);

document.querySelectorAll("[data-transaction-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    transactionFilter = button.getAttribute("data-transaction-filter") || "all";
    transactionEntityFilter = null;
    setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
    renderMainTransactions();
  });
});
document.querySelectorAll("[data-transaction-sort]").forEach((button) => {
  button.addEventListener("click", () => {
    transactionSort = button.getAttribute("data-transaction-sort") || "date";
    setTransactionFilterButtons("[data-transaction-sort]", transactionSort);
    renderMainTransactions();
  });
});
document.querySelectorAll("[data-modal-transaction-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    modalTransactionFilter = button.getAttribute("data-modal-transaction-filter") || "all";
    modalTransactionEntityFilter = null;
    setTransactionFilterButtons("[data-modal-transaction-filter]", modalTransactionFilter);
    renderModalTransactions();
  });
});
document.querySelectorAll("[data-modal-transaction-sort]").forEach((button) => {
  button.addEventListener("click", () => {
    modalTransactionSort = button.getAttribute("data-modal-transaction-sort") || "date";
    setTransactionFilterButtons("[data-modal-transaction-sort]", modalTransactionSort);
    renderModalTransactions();
  });
});

function lenderEvidenceSelection(event) {
  const target = event.target instanceof Element ? event.target : null;
  const button = target ? target.closest("[data-lender-evidence-filter]") : null;
  if (!button) return null;
  const filter = button.getAttribute("data-lender-evidence-filter");
  const entity = button.getAttribute("data-lender-evidence-entity");
  if (!filter || !entity) return null;
  return { filter, entity };
}

if (els.lenderTable) {
  els.lenderTable.addEventListener("click", (event) => {
    const selection = lenderEvidenceSelection(event);
    if (!selection) return;
    transactionFilter = selection.filter;
    transactionEntityFilter = selection.entity;
    setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
    renderMainTransactions();
    els.transactionCard?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}
if (els.statementModalLenders) {
  els.statementModalLenders.addEventListener("click", (event) => {
    const selection = lenderEvidenceSelection(event);
    if (!selection) return;
    modalTransactionFilter = selection.filter;
    modalTransactionEntityFilter = selection.entity;
    setTransactionFilterButtons("[data-modal-transaction-filter]", modalTransactionFilter);
    renderModalTransactions();
    els.statementModalTransactions?.closest(".modal-panel")?.scrollIntoView({ block: "start" });
  });
}

/* --- appearance ------------------------------------------------------
   The theme is resolved inline in the document head before first paint;
   this only handles switching it afterwards. */
const APPEARANCE_KEY = "ocr-appearance";
let appearanceShiftTimer = null;

function currentAppearance() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function syncAppearanceButtons(theme) {
  document.querySelectorAll("[data-appearance]").forEach((button) => {
    const isActive = button.getAttribute("data-appearance") === theme;
    button.setAttribute("aria-checked", isActive ? "true" : "false");
    button.tabIndex = isActive ? 0 : -1;
  });
}

function setAppearance(theme, { persist = true } = {}) {
  const next = theme === "dark" ? "dark" : "light";
  const root = document.documentElement;
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (next !== currentAppearance() && !reduced) {
    // crossfade the whole interface, then hand timing back to the components
    root.classList.add("appearance-shift");
    clearTimeout(appearanceShiftTimer);
    appearanceShiftTimer = setTimeout(() => root.classList.remove("appearance-shift"), 320);
  }
  root.setAttribute("data-theme", next);
  if (persist) {
    try { localStorage.setItem(APPEARANCE_KEY, next); } catch (error) { /* private mode */ }
  }
  syncAppearanceButtons(next);
}

document.querySelectorAll("[data-appearance]").forEach((button) => {
  button.addEventListener("click", () => setAppearance(button.getAttribute("data-appearance")));
});
if (els.appearanceToggle) {
  // arrow keys move between segments, matching a native segmented control
  els.appearanceToggle.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const next = event.key === "ArrowLeft" ? "light" : "dark";
    setAppearance(next);
    els.appearanceToggle.querySelector(`[data-appearance="${next}"]`)?.focus();
  });
}
// keep following the system until the user makes an explicit choice
const appearanceQuery = window.matchMedia?.("(prefers-color-scheme: dark)");
appearanceQuery?.addEventListener?.("change", (event) => {
  let stored = null;
  try { stored = localStorage.getItem(APPEARANCE_KEY); } catch (error) { /* private mode */ }
  if (!stored) setAppearance(event.matches ? "dark" : "light", { persist: false });
});
syncAppearanceButtons(currentAppearance());

function moreStepFrom(event) {
  const target = event.target instanceof Element ? event.target : null;
  const button = target ? target.closest("[data-more-step]") : null;
  return button ? button.getAttribute("data-more-step") : null;
}

if (els.transactionMore) {
  els.transactionMore.addEventListener("click", (event) => {
    const step = moreStepFrom(event);
    if (!step) return;
    transactionLimit = step === "all" ? Number.MAX_SAFE_INTEGER : transactionLimit + Number(step);
    renderMainTransactions({ keepLimit: true });
  });
}
if (els.statementModalTransactionMore) {
  els.statementModalTransactionMore.addEventListener("click", (event) => {
    const step = moreStepFrom(event);
    if (!step) return;
    modalTransactionLimit = step === "all" ? Number.MAX_SAFE_INTEGER : modalTransactionLimit + Number(step);
    renderModalTransactions({ keepLimit: true });
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
setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
setTransactionFilterButtons("[data-transaction-sort]", transactionSort);
setTransactionFilterButtons("[data-modal-transaction-filter]", modalTransactionFilter);
setTransactionFilterButtons("[data-modal-transaction-sort]", modalTransactionSort);
setActions(null, false);
