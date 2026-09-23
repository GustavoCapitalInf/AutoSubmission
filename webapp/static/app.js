const els = {
  settingsView: document.getElementById("settingsView"),
  nsfCarryOverToggle: document.getElementById("nsfCarryOverToggle"),
  settingsStatus: document.getElementById("settingsStatus"),
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
  validationValue: document.getElementById("validationValue"),
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
  modalExtractionReview: document.getElementById("modalExtractionReview"),
  modalCopyData: document.getElementById("modalCopyData"),
  copyBuffer: document.getElementById("copyBuffer"),
  appearanceToggle: document.getElementById("appearanceToggle"),
  settingsBtn: document.getElementById("settingsBtn"),
  settingsPanel: document.getElementById("settingsPanel"),
  allAccountsToggle: document.getElementById("allAccountsToggle"),
  accountsPanel: document.getElementById("accountsPanel"),
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
// A statement holding several accounts: the payload, and which of its published accounts the panels show.
let currentDocument = null;
let selectedAccountIndex = null;
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

const REVENUE_METRIC_COPY = Object.freeze({
  totalCredits: "All posted credit transactions",
  verifiedRevenue: "Confirmed operating revenue",
  unverifiedDeposits: "Deposits requiring analyst review",
  nonRevenue: "Excluded from revenue analysis",
  revenueUpperBound: "Upper-bound estimate: verified revenue plus unverified deposits",
  achCredits: "Posted ACH credit transactions",
});

const emptyMetricSections = [
  {
    title: "Credits",
    sub: "Posted credit transactions",
    items: [
      ["Total Credits", "N/A", REVENUE_METRIC_COPY.totalCredits, "CR", "green"],
      ["Verified Revenue", "N/A", REVENUE_METRIC_COPY.verifiedRevenue, "REV", "green"],
      ["Unverified Deposits", "N/A", REVENUE_METRIC_COPY.unverifiedDeposits, "?", "amber"],
      ["Non-Revenue", "N/A", REVENUE_METRIC_COPY.nonRevenue, "X", "neutral"],
      ["Revenue Upper Bound", "N/A", REVENUE_METRIC_COPY.revenueUpperBound, "MAX", "neutral"],
      ["ACH Credits", "N/A", REVENUE_METRIC_COPY.achCredits, "ACH", "neutral"],
    ],
  },
  {
    title: "Debits",
    sub: "Posted debit transactions",
    items: [
      ["Total Debits", "N/A", "All posted debit transactions", "DB", "neutral"],
      ["Confirmed Withholding", "N/A", "Confirmed lender debits as a share of revenue", "%", "neutral"],
      ["ACH Debits", "N/A", "Posted ACH debit transactions", "ACH", "neutral"],
      ["POS Transactions", "N/A", "Card purchase transactions", "POS", "neutral"],
      ["ATM Withdrawals", "N/A", "Posted ATM withdrawals", "ATM", "neutral"],
      ["Checks Detected", "N/A", "Posted check transactions", "CHK", "neutral"],
    ],
  },
  {
    title: "Risk Signals",
    sub: "Balance and NSF indicators",
    items: [
      ["NSFs", "N/A", "Returned or insufficient funds", "NSF", "neutral"],
      ["Average Daily Balance", "N/A", "Average of daily ending balances for the statement period", "AVG", "neutral"],
      ["Ending Balance", "N/A", "Closing balance for the statement period", "END", "neutral"],
      ["Lowest Balance", "N/A", "Lowest daily ending balance", "LOW", "neutral"],
      ["Highest Balance", "N/A", "Highest daily ending balance", "HIGH", "neutral"],
    ],
  },
  {
    title: "Lenders",
    sub: "Lender and insurance transaction analysis",
    items: [
      ["Confirmed Lenders", "N/A", "Lenders confirmed from statement transactions", "LEN", "neutral"],
      ["Potential Lenders", "N/A", "Possible lenders requiring analyst review", "?", "neutral"],
      ["Confirmed Lender Debit Count", "N/A", "Transactions paid to confirmed lenders", "DB", "neutral"],
      ["Confirmed Lender Debits", "N/A", "Total paid to confirmed lenders", "$", "neutral"],
      ["Potential Lender Debit Count", "N/A", "Transactions linked to possible lenders", "DB", "neutral"],
      ["Potential Lender Debits", "N/A", "Excluded until lender status is confirmed", "$", "neutral"],
      ["Eligible Deposits", "N/A", "Deposits used to calculate withholding rates", "DEP", "neutral"],
      ["Potential Withholding Exposure", "N/A", "Possible lender debits as a share of eligible deposits", "%", "neutral"],
      ["Insurance Debits", "N/A", "Insurance debit transactions", "INS", "neutral"],
      ["Insurance Total", "N/A", "Excluded from lender payment totals", "$", "neutral"],
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

function processingStageLabel(value) {
  const match = /^(visual_pair_proposing|visual_pair_reviewing):(\d+)\/(\d+)(?::(batch|crop):(\d+)\/(\d+)|:(discovery))?$/.exec(String(value || ""));
  if (match) {
    const label = `${match[1] === "visual_pair_proposing" ? "Reading" : "Checking"} page ${match[2]} of ${match[3]}`;
    if (match[7]) return `${label} for missing rows`;
    if (match[4] === "crop") return `${label} again, region ${match[5]} of ${match[6]}`;
    if (match[4] === "batch") return `${label}, part ${match[5]} of ${match[6]}`;
    return label;
  }
  if (value === "visual_pair_rendering") return "Preparing statement pages";
  if (value === "visual_pair_gating") return "Checking statement totals";
  return labelize(value);
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function formatMoney(value, currency = "USD") {
  const n = numberOrNull(value);
  if (n === null) return "N/A";
  const amount = n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  // An explicit null currency means the document never declared one. Printing
  // a dollar sign there would assert a denomination nobody proved
  // (CURRENCY DOCTRINE §A), so the magnitude is shown without a unit. Callers
  // that omit the argument still get the USD default they always had.
  if (!currency) return amount;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n);
  } catch {
    return `$${amount}`;
  }
}

// Owner ruling, 2026-09-22: the NSF count is negative-ending days on the basis chosen in Settings.
const NSF_SOURCE_LABELS = {
  negative_printed_days: "Negative-ending days (printed days only)",
  negative_ending_days: "Negative-ending days (balance carried over inactive days)",
  negative_ending_days_unavailable: "Not computable: no validated daily ledger",
};

function nsfSourceLabel(source) {
  return NSF_SOURCE_LABELS[source] || (source ? labelize(source) : "Negative-ending days");
}

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

function isoDay(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) return null;
  const day = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return Number.isNaN(day.getTime()) ? null : day;
}

// The calendar month a statement stands for: the one holding most of its period's days, the earlier on a
// tie. A statement running 2026-03-02 to 2026-04-01 is March 2026; 2025-12-01 to 2026-01-02 is December 2025.
function statementMonth(periodStart, periodEnd) {
  const start = isoDay(periodStart);
  const end = isoDay(periodEnd);
  if (!start && !end) return null;
  const month = (day) => ({ month: day.getUTCMonth(), year: day.getUTCFullYear(),
    key: day.getUTCFullYear() * 12 + day.getUTCMonth() });
  if (!start || !end || end < start) return month(start || end);
  const days = new Map();
  for (let day = new Date(start), n = 0; day <= end && n < 400; day.setUTCDate(day.getUTCDate() + 1), n += 1) {
    const key = day.getUTCFullYear() * 12 + day.getUTCMonth();
    days.set(key, (days.get(key) || 0) + 1);
  }
  let best = null;
  for (const [key, count] of days) {
    if (!best || count > best.count || (count === best.count && key < best.key)) best = { key, count };
  }
  return { month: best.key % 12, year: Math.floor(best.key / 12), key: best.key };
}

// Whole numbers with thousands separators, as the CRM shows them: 186523.4 -> "186,523".
function formatWhole(value) {
  if (value === null || value === undefined || value === "") return "N/A";
  const number = Number(value);
  if (!Number.isFinite(number)) return "N/A";
  return Math.round(number).toLocaleString("en-US");
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
  if (metrics.withholding_review_required) return "Eligible deposits are unavailable; analyst review is required";
  const numerator = formatMoney(metrics.withholding_numerator ?? metrics.lender_debits, currency);
  const denominator = formatMoney(metrics.withholding_denominator ?? metrics.eligible_deposits, currency);
  const label = metrics.withholding_denominator_label || "Eligible deposits";
  return `${numerator} confirmed lender debits divided by ${denominator} ${label.toLowerCase()}`;
}

function activeDenominatorNote(metrics = {}) {
  return metrics.eligible_deposit_definition || "Deposits used to calculate withholding rates";
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
  if (numberOrNull(total) === null) return "Potential lender debits are unavailable; analyst review is required";
  const reviewSuffix = hasMaterialPotentialLenderDebits(metrics) ? "; analyst review is required" : "";
  if ((numberOrNull(denominator) ?? 0) <= 0) {
    return `${formatMoney(total, currency)} potential lender debits; eligible deposits are unavailable${reviewSuffix}`;
  }
  return `${formatMoney(total, currency)} potential lender debits divided by ${formatMoney(denominator, currency)} eligible deposits${reviewSuffix}`;
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
    return { label: "Verified Revenue", glyph: "REV", tone: "green" };
  }
  if (txAmount(tx) > 0 && revenueState === "unverified_deposit") {
    return { label: "Unverified Deposit", glyph: "?", tone: "amber" };
  }
  if (txAmount(tx) > 0 && revenueState === "non_revenue") {
    return { label: "Non-Revenue", glyph: "X", tone: "neutral" };
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
        <button class="table-action" type="button" ${common} data-revenue-review-action="reset">Reset Decision</button>
      </div>
    `;
  }
  return `
    <div class="revenue-review-actions">
      <button class="table-action review-confirm" type="button" ${common} data-revenue-review-action="confirm" aria-label="Confirm this deposit as operating revenue">Confirm Revenue</button>
      <button class="table-action review-reject" type="button" ${common} data-revenue-review-action="reject" aria-label="Exclude this deposit from operating revenue">Mark Non-Revenue</button>
    </div>
  `;
}

function revenueReviewReason(tx) {
  const record = transactionClassification(tx);
  if (txAmount(tx) <= 0 || record.revenue_classification !== "unverified_deposit") return "";
  const reasons = {
    deposit_source_requires_review: "Generic deposit with insufficient source information.",
    unknown_credit_source_requires_review: "Unable to determine whether this deposit represents operating revenue.",
    operating_source_without_payout_context: "Recognized source without enough evidence to confirm operating revenue.",
    source_direction_conflicts_with_signed_amount: "Transaction direction conflicts with the posted credit amount.",
  };
  return reasons[record.revenue_matched_rule]
    || "Unable to determine whether this deposit represents operating revenue.";
}

function runningBalanceValue(tx) {
  return numberOrNull(tx && tx.running_balance);
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
  const showRunningBalance = matched.some((tx) => runningBalanceValue(tx) !== null);
  const runningBalanceHeader = tableEl.closest("table")?.querySelector("[data-running-balance-column]");
  if (runningBalanceHeader) runningBalanceHeader.hidden = !showRunningBalance;
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
  const runningBalanceEmptyCell = showRunningBalance ? "<td>N/A</td>" : "";
  if (!visible.length) {
    tableEl.innerHTML = `
      <tr>
        <td><strong>No transactions found</strong></td>
        <td>${escapeHtml(filter === "all" ? "No statement returned transaction rows." : "No rows matched this filter.")}</td>
        ${sourceHead}
        <td>${glassChip("", "Empty", "neutral")}</td>
        <td>N/A</td>
        ${runningBalanceEmptyCell}
      </tr>
    `;
    return;
  }
  tableEl.innerHTML = visible.map((tx) => {
    const amount = txAmount(tx);
    const category = transactionCategory(tx);
    // The combined package ledger interleaves rows from every statement, so a
    // row is denominated by the statement it came from, never by a package-wide
    // label that a mixed package does not have (CURRENCY DOCTRINE §F).
    const rowCurrency = "source_currency" in tx ? tx.source_currency : currency;
    const source = showSource
      ? `<td class="transaction-source">${escapeHtml(tx.source_document || tx.source_bank || "Statement")}</td>`
      : "";
    const reviewReason = revenueReviewReason(tx);
    const reviewReasonHtml = reviewReason
      ? `<div class="table-head-scope"><strong>Reason:</strong> ${escapeHtml(reviewReason)}</div>`
      : "";
    const runningBalance = showRunningBalance
      ? `<td class="amount-cell">${escapeHtml(formatMoney(runningBalanceValue(tx), rowCurrency))}</td>`
      : "";
    return `
      <tr>
        <td><strong>${escapeHtml(tx.date || "N/A")}</strong></td>
        <td class="transaction-desc">${escapeHtml(txDescriptionRaw(tx) || "N/A")}</td>
        ${source}
        <td>${glassChip(category.glyph, category.label, category.tone)}${reviewReasonHtml}${revenueReviewControls(tx, reviewJobId)}</td>
        <td class="amount-cell ${amount < 0 ? "amount-debit" : "amount-credit"}">${escapeHtml(formatMoney(amount, rowCurrency))}</td>
        ${runningBalance}
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
      // The package currency when there is one; each row still overrides with
      // its own `source_currency`, so a mixed package's rows stay denominated
      // individually instead of all being relabelled as one unit.
      currency: packageCurrencyInfo(pkg).currency,
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

// OQ9 (PHASE2_RULINGS.md): the UI used to show a value labelled "OCR
// confidence" that was in fact four hard-coded percentage tiers re-encoding
// the validator's own `quality` verdict -- not a measurement of any
// extractor's output, and misleading the day a second extractor exists.
// Removed with no substitute score: `validationLabel` / `packageValidationLabel`
// return WORDS only, taken from the closed vocabulary the payload already
// carries (`quality.corporate_use`, `quality.level`, `pkg.totals.decision` /
// `.completeness` / `.cross_account_averages_refused`) -- never a percentage,
// never a number of any kind. `tests/test_webapp_confidence_label.py` is the
// guard that keeps it that way.
function validationLabel(report = {}) {
  // MINOR-4 (PHASE2_P20SURFACES_REVIEW.md): render the payload's OWN word
  // through the same `labelize` every other status label in this file already
  // uses (decisionPill, packageValidationLabel below) rather than promoting
  // `corporate_use === "approved"` to the stronger, invented word "Validated"
  // -- one vocabulary across both labels, and never a word `quality` did not
  // itself carry. `assess_quality` (analysis/pipeline.py) always sets
  // `corporate_use` to one of "approved" / "summary_only" / "manual_review_
  // required" on every real payload; `level` and the literal fallback exist
  // only for a malformed or missing `quality` object.
  const q = report.quality || {};
  return labelize(q.corporate_use || q.level || "review");
}

function packageValidationLabel(pkg = {}) {
  const totals = pkg.totals || {};
  const words = [labelize(totals.decision || "review_required")];
  if (totals.completeness === "partial") words.push("completeness: partial");
  if (totals.cross_account_averages_refused) words.push("cross-account averages refused");
  return words.join(" · ");
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
    return "No deterministic parser matched this statement. Enable the configured visual fallback or select Force visual OCR to request a reviewed extraction.";
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
  els.validationValue.textContent = meta;
}

function statusRowHtml([key, value]) {
  return `
    <div class="status-row">
      <div class="status-key">${escapeHtml(key)}</div>
      <div class="status-value">${escapeHtml(value)}</div>
    </div>
  `;
}

function setStatusRows(rows) {
  els.statusList.innerHTML = rows.map(statusRowHtml).join("");
}

function setInitialState() {
  if (els.monthlyCard) els.monthlyCard.style.display = "none";
  currentDocument = null;
  selectedAccountIndex = null;
  hideAccountsPanel();
  if (els.transactionCard) els.transactionCard.style.display = "block";
  renderMetricSections(emptyMetricSections);
  renderAccountSummary(accountFieldRows());
  setBanner("pending", "Ready for extraction", "--");
  setStatusRows([
    ["OCR completed", "No"],
    ["Pages processed", "--"],
    ["Processing time", "--"],
    ["Parsing mode", parseModeLabel(selectedParseMode())],
    ["Validation", "--"],
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

function setActions(jobId, ready, textReady = ready) {
  const links = [
    [els.downloadJson, "json", ready],
    [els.downloadCsv, "csv", ready],
    [els.downloadExcel, "xlsx", ready],
    [els.exportText, "md", textReady],
    [els.openTextBtn, "result", textReady],
  ];
  links.forEach(([link, fmt, enabled]) => {
    if (!link) return;
    if (enabled) {
      link.href = fmt === "result" ? `/result/${jobId}` : `/download/${jobId}/${fmt}`;
      link.classList.remove("disabled");
      link.setAttribute("aria-disabled", "false");
    } else {
      link.href = "#";
      link.classList.add("disabled");
      link.setAttribute("aria-disabled", "true");
    }
  });
  [[els.copyDataBtn, ready], [els.summaryBtn, ready], [els.copyTextBtn, textReady]].forEach(([button, enabled]) => {
    if (!button) return;
    button.disabled = !enabled;
    button.classList.toggle("disabled", !enabled);
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
  REV: ["◐", "Revenue"],
  REVIEW: ["◐", "Review"],
  MAX: ["", "Upper Bound"],
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
    return "Unavailable because daily balances could not be verified";
  }
  return `Average of daily ending balances across ${span}`;
}

function averageBalanceTone(metrics = {}) {
  return metrics.average_daily_balance === null || metrics.average_daily_balance === undefined ? "amber" : "neutral";
}

/* CURRENCY DOCTRINE §F. A package that mixes currencies, or that contains a
   statement which never declared one, publishes its cross-currency totals as
   null. `formatMoney` already renders those "N/A"; these say WHY, so an
   underwriter does not read a refusal as missing data. */
const CURRENCY_REFUSAL_COPY = {
  multiple_currencies:
    "Refused: this package mixes currencies and adding them would be a unit error. Each statement's own figures are unaffected.",
  undetermined_statement_currency:
    "Refused: a statement in this package does not declare its currency, so its figures cannot be pooled with the rest.",
};

function packageCurrencyInfo(pkg = {}) {
  const info = pkg.currency || {};
  const totals = pkg.totals || {};
  const currencies = Array.isArray(info.currencies) ? info.currencies : [];
  const refused =
    info.cross_currency_totals_refused === true ||
    totals.cross_currency_totals_refused === true;
  return {
    currency: info.currency ?? totals.currency ?? null,
    currencies,
    refused,
    reason: info.refusal_reason ?? totals.currency_refusal_reason ?? null,
  };
}

function packageCurrencyLabel(info) {
  if (info.currency) return info.currency;
  if (info.currencies.length) return `Mixed (${info.currencies.join(", ")})`;
  return "Not declared";
}

function packageCurrencyRefusalNote(info) {
  const copy =
    CURRENCY_REFUSAL_COPY[info.reason] ||
    "Refused: this package's currency could not be proven, so its figures cannot be combined.";
  return info.currencies.length ? `${copy} Currencies present: ${info.currencies.join(", ")}.` : copy;
}

/* Package rollup: days-weighted validated statement ADB values from the API. */
function packageAverageBalanceNote(documents = []) {
  const ready = documents.filter((doc) => doc && doc.average_daily_balance !== null && doc.average_daily_balance !== undefined);
  if (!ready.length) return "Unavailable because daily balances could not be verified";
  const days = ready.reduce((sum, doc) => sum + (numberOrNull(doc.adb_calendar_days) || 0), 0);
  const span = days ? `${formatNumber(days)} calendar days` : "statement periods";
  return `Days-weighted average across ${span}`;
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
  ["verified_revenue", "Verified Revenue", "REV", "Verified", "green"],
  ["unverified_deposit", "Unverified Deposits", "?", "Review Required", "amber"],
  ["non_revenue", "Non-Revenue", "X", "Excluded", "neutral"],
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
  els.revenueCount.textContent = `${formatNumber(metrics.total_posted_credit_count)} credit transactions`;
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

function isDocumentPayload(report) {
  // The multi-account shape: `document` + `accounts`, and deliberately no
  // top-level `statement`. Keyed on the account list and nothing else, so
  // every payload this dashboard is served today takes the path it always did.
  return Boolean(report) && Array.isArray(report.accounts);
}

/* --- accounts of one statement ---------------------------------------
   A statement can hold several accounts (a business checking account beside
   savings shares). Each published account is its own complete analysis, and
   the panels show ONE of them at a time: by default the main account a lender
   funds -- the business checking account with the most deposits -- and, with
   the "All accounts" setting on, a table of every account the statement
   prints, each selectable. Nothing is ever added up across accounts. */
const ALL_ACCOUNTS_KEY = "bsa-all-accounts";
const ACCOUNT_KINDS = [
  ["checking", /\b(checking|chequing|share\s+drafts?|demand\s+deposits?)\b/i],
  ["money_market", /\bmoney\s*market\b/i],
  ["certificate", /\b(certificates?|cds?)\b/i],
  ["savings", /\b(savings?|shares?|club|membership)\b/i],
];
const ACCOUNT_KIND_LABELS = {
  checking: "Checking",
  savings: "Savings",
  money_market: "Money market",
  certificate: "Certificate",
  retirement: "Retirement",
  loan: "Loan",
  credit_card: "Credit card",
};
const ACCOUNT_REASON_LABELS = {
  page_unresolved: "a page could not be verified",
  rows_unplaced: "some rows could not be placed in an account",
  no_rows: "its transactions could not be verified",
  sum_mismatch: "transactions do not add up to the printed balances",
  continuity_break: "running balances do not follow",
  anchors_underdetermined: "opening or closing balance not found",
  anchor_derived: "opening or closing balance not printed",
  direction_unknown: "a deposit could not be told from a withdrawal",
  date_unparsed: "a date could not be read",
  period_mismatch: "the statement period could not be read",
  daily_ledger_not_validated: "its daily balances did not validate",
  source_statement_invalid: "its reading did not validate",
};

function allAccountsView() {
  try { return localStorage.getItem(ALL_ACCOUNTS_KEY) === "on"; } catch (error) { return false; }
}

function accountRoster(report) {
  const doc = report && report.document;
  return doc && Array.isArray(doc.account_roster) ? doc.account_roster.filter((entry) => entry && typeof entry === "object") : [];
}

function publishedAccounts(report) {
  if (!isDocumentPayload(report)) return report ? [report] : [];
  return report.accounts.filter((account) => account && typeof account === "object");
}

function rosterEntryFor(roster, publishedIndex) {
  return roster.find((entry) => entry.status === "published" && entry.published_index === publishedIndex) || null;
}

function accountKindOf(statement = {}, entry = null) {
  if (entry && entry.kind) return entry.kind;
  const name = String(statement.account_name || "");
  const found = ACCOUNT_KINDS.find(([, pattern]) => pattern.test(name));
  return found ? found[0] : null;
}

function isBusinessAccount(statement = {}, entry = null) {
  return /\b(business|commercial|corporate)\b/i.test(`${(entry && entry.title) || ""} ${statement.account_name || ""}`);
}

function lastFour(number) {
  const digits = String(number || "").replace(/\D/g, "");
  return digits ? digits.slice(-4) : "";
}

function accountDisplayName(statement = {}, entry = null) {
  const title = (entry && entry.title) || statement.account_name
    || ACCOUNT_KIND_LABELS[accountKindOf(statement, entry)] || "Account";
  const four = (entry && entry.number_last4) || lastFour(statement.account_number);
  return four ? `${title} ••${four}` : title;
}

function mainAccountRank(kind, business) {
  // How likely an account is the one a lender funds (webapp/app.py main_account_rank): a checking account first,
  // then one whose title names no kind (a product name such as "... Plus Banking" can be the operating account), then
  // any other deposit account; a business title one higher within its tier; a card or a loan never.
  if (kind === "credit_card" || kind === "loan") return -1;
  return (kind === "checking" ? 4 : !kind ? 2 : 0) + (business ? 1 : 0);
}

function mainAccountIndex(accounts, roster = []) {
  // The account a lender funds: a business checking account, and among several the one with the most deposits.
  // A display default only: every account stays one click away with "All accounts" on.
  let best = null;
  accounts.forEach((account, index) => {
    const statement = account.statement || {};
    const entry = rosterEntryFor(roster, index);
    const rank = mainAccountRank(accountKindOf(statement, entry), isBusinessAccount(statement, entry));
    const deposits = Number((account.metrics || {}).effective_total_deposits) || 0;
    if (!best || rank > best.rank || (rank === best.rank && deposits > best.deposits)) best = { index, rank, deposits };
  });
  return best ? best.index : 0;
}

function unverifiedMainAccount(roster = []) {
  // The main account among EVERY account the statement prints: its rank decides first (mainAccountRank). A HELD
  // account of the best rank leaves the account a lender funds undetermined: it is the main one and it is not
  // verified, and another account must never be shown in its place. null when no account of the best rank is held.
  if (!roster.length) return null;
  const rank = (entry) => mainAccountRank(entry.kind, /\b(business|commercial|corporate)\b/i.test(entry.title || ""));
  const best = Math.max(...roster.map(rank));
  if (best < 0) return null;  // cards and loans only: no account a lender funds
  return roster.find((entry) => rank(entry) === best && entry.status === "held") || null;
}

function idleMainAccount(roster = []) {
  // Owner ruling, 2026-09-23: when the main account (the business checking account) printed no activity this period,
  // the dashboard says so and that it needs review, and keeps showing the active account(s). The idle account of the
  // best rank, when no account of that rank was verified or held; null otherwise (webapp/app.py _idle_main_account).
  if (!roster.length) return null;
  const rank = (entry) => mainAccountRank(entry.kind, /\b(business|commercial|corporate)\b/i.test(entry.title || ""));
  const best = Math.max(...roster.map(rank));
  if (best < 0) return null;
  const top = roster.filter((entry) => rank(entry) === best);
  if (top.some((entry) => entry.status === "published" || entry.status === "held")) return null;
  return top.find((entry) => entry.status === "idle") || null;
}

function idleMainText(entry, currency) {
  return `${accountDisplayName({}, entry)} had no activity this period (balance ${formatMoney(entry.balance, currency)})`
    + " and needs review";
}

function idleMainNote(report, currency) {
  // The sentence the summary box leads with when the statement's main account printed no activity; "" otherwise.
  const idleMain = report ? idleMainAccount(accountRoster(report)) : null;
  return idleMain ? `Main account ${idleMainText(idleMain, currency)}. ` : "";
}

function mainAccountReason(account = {}, entry = null) {
  const statement = account.statement || {};
  const checking = accountKindOf(statement, entry) === "checking";
  if (checking && isBusinessAccount(statement, entry)) return "the business checking account with the most deposits";
  if (checking) return "the checking account with the most deposits";
  return "the account with the most deposits";
}

function accountReasonText(reasons = []) {
  const words = [...new Set((reasons || []).map((code) => ACCOUNT_REASON_LABELS[code]).filter(Boolean))];
  return words.length ? words.slice(0, 2).join("; ") : "not verified";
}

function accountPanelEntries(published, roster) {
  // Every account the statement prints, in printed order: the roster when the reader judged the statement account
  // by account, else the published accounts themselves.
  if (roster.length) return roster;
  return published.map((account, index) => ({
    title: (account.statement || {}).account_name || null,
    kind: null,
    number_last4: lastFour((account.statement || {}).account_number) || null,
    status: "published",
    published_index: index,
    balance: null,
    reasons: [],
  }));
}

function accountPanelRowHtml(entry, published, main, selected, currency, isUnverifiedMain = false) {
  const account = entry.status === "published" ? published[entry.published_index] : null;
  const statement = (account && account.statement) || {};
  const metrics = (account && account.metrics) || {};
  const name = accountDisplayName(statement, entry);
  const kind = ACCOUNT_KIND_LABELS[entry.kind || accountKindOf(statement, entry)] || "Account";
  if (account) {
    const money = (value) => escapeHtml(formatMoney(value, statement.currency || currency));
    const isSelected = entry.published_index === selected;
    const count = (statement.transactions || []).length;
    return `
      <tr data-account-index="${escapeHtml(String(entry.published_index))}" class="${isSelected ? "is-selected" : ""}"
          tabindex="0" aria-selected="${isSelected ? "true" : "false"}">
        <td><strong>${escapeHtml(name)}</strong>${entry.published_index === main ? `<span class="main-badge">MAIN</span>` : ""}
          <span class="account-reason">${escapeHtml(kind)} · ${escapeHtml(formatNumber(count))} ${count === 1 ? "transaction" : "transactions"}</span></td>
        <td>${glassChip("✓", "Verified", "green")}</td>
        <td>${money(statement.beginning_balance)}</td>
        <td>${money(statement.ending_balance)}</td>
        <td>${money(metrics.effective_total_deposits)}</td>
        <td>${money(metrics.effective_total_withdrawals)}</td>
        <td>${money(metrics.average_daily_balance)}</td>
      </tr>`;
  }
  if (entry.status === "idle") {
    // An unchanged printed balance over the whole period: its daily balance is that balance every day.
    const balance = escapeHtml(formatMoney(entry.balance, currency));
    const zero = escapeHtml(formatMoney(0, currency));
    return `
      <tr>
        <td><strong>${escapeHtml(name)}</strong>${isUnverifiedMain ? `<span class="main-badge">MAIN</span>` : ""}<span class="account-reason">${escapeHtml(kind)} · no transactions</span></td>
        <td>${glassChip("·", "No activity", "neutral")}</td>
        <td>${balance}</td>
        <td>${balance}</td>
        <td>${zero}</td>
        <td>${zero}</td>
        <td>${balance}</td>
      </tr>`;
  }
  return `
    <tr>
      <td><strong>${escapeHtml(name)}</strong>${isUnverifiedMain ? `<span class="main-badge">MAIN</span>` : ""}<span class="account-reason">${escapeHtml(kind)} · ${escapeHtml(accountReasonText(entry.reasons))}</span></td>
      <td>${glassChip("◐", "Needs review", "amber")}</td>
      <td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>
    </tr>`;
}

function renderAccountsPanel(published, roster, main, selected, unverifiedMain = null, idleMain = null) {
  if (!els.accountsPanel) return;
  const entries = accountPanelEntries(published, roster);
  const mainAccount = published[main] || {};
  const mainEntry = rosterEntryFor(roster, main);
  const mainName = accountDisplayName(mainAccount.statement || {}, mainEntry);
  const others = entries.length - 1;
  // The statement's own denomination; never an assumed one (an account without figures shows none).
  const currency = (mainAccount.statement || {}).currency || null;
  if (!allAccountsView()) {
    const lead = idleMain
      ? `This statement's main account, <strong>${escapeHtml(accountDisplayName({}, idleMain))}</strong>, had no activity`
        + ` this period (balance ${escapeHtml(formatMoney(idleMain.balance, currency))}) and needs review.`
        + ` Showing the active account, <strong>${escapeHtml(mainName)}</strong>.`
      : `Showing the main account, <strong>${escapeHtml(mainName)}</strong>: ${escapeHtml(mainAccountReason(mainAccount, mainEntry))}.`;
    els.accountsPanel.innerHTML = `
      <div class="accounts-note">This statement holds <strong>${escapeHtml(formatNumber(entries.length))} accounts</strong>.
        ${lead}
        ${others > 0 ? `Turn on <strong>All accounts</strong> in Settings to review the other ${others === 1 ? "account" : `${escapeHtml(formatNumber(others))} accounts`}.` : ""}
      </div>`;
    els.accountsPanel.hidden = false;
    return;
  }
  els.accountsPanel.innerHTML = `
    <div class="table-card">
      <div class="table-head">
        <h3>Accounts in this statement</h3>
        <span class="section-label">${escapeHtml(formatNumber(entries.length))} accounts · select one to analyze</span>
      </div>
      <div class="table-wrap">
        <table class="accounts-table">
          <thead>
            <tr>
              <th>Account</th>
              <th>Status</th>
              <th>Beginning</th>
              <th>Ending</th>
              <th>Deposits</th>
              <th>Withdrawals</th>
              <th>Avg Daily Balance</th>
            </tr>
          </thead>
          <tbody>${entries.map((entry) => accountPanelRowHtml(entry, published, idleMain ? -1 : main, selected, currency, entry === unverifiedMain || entry === idleMain)).join("")}</tbody>
        </table>
      </div>
    </div>`;
  els.accountsPanel.hidden = false;
}

function renderUnverifiedMain(published, roster, entry) {
  // The main account (the business checking account) was not verified. Its metrics are withheld, and no other
  // account stands in for it; the verified ones stay one setting away.
  const report = currentDocument;
  setInitialState();
  currentDocument = report;
  currentAnalysis = null;
  setProgress(false);
  const name = accountDisplayName({}, entry);
  const why = entry.status === "idle"
    ? `it printed no activity this period (balance ${formatMoney(entry.balance, ((published[0] || {}).statement || {}).currency || null)})`
    : accountReasonText(entry.reasons);
  const verified = published.length;
  if (allAccountsView()) {
    // Every account on the table, the main one marked and held; nothing selected until the user picks one.
    selectedAccountIndex = null;
    renderAccountsPanel(published, roster, -1, null, entry);
  }
  els.statusHeading.textContent = "Main account needs review";
  setBanner("pending", "Main account not verified; its metrics withheld", "Review required");
  els.decisionPill.textContent = "review required";
  els.decisionPill.className = "decision-pill";
  els.summaryBox.textContent = `${name} is this statement's main account and could not be verified: ${why}. `
    + "No metrics are shown for it.";
  setStatusRows([
    ["OCR completed", "Yes"],
    ["Validation", "Review required"],
    ["Main account", "Not verified"],
    ["Metrics", "Withheld"],
  ]);
  if (els.transactionCard) els.transactionCard.style.display = "none";
  if (!els.accountsPanel || allAccountsView()) return;
  els.accountsPanel.innerHTML = `
    <div class="accounts-note">This statement holds <strong>${escapeHtml(formatNumber(roster.length))} accounts</strong>.
      The main account, <strong>${escapeHtml(name)}</strong>, could not be verified: ${escapeHtml(why)}.
      ${verified ? `${escapeHtml(formatNumber(verified))} other ${verified === 1 ? "account was" : "accounts were"} verified: turn on <strong>All accounts</strong> in Settings to review ${verified === 1 ? "it" : "them"}.` : ""}
    </div>`;
  els.accountsPanel.hidden = false;
}

function hideAccountsPanel() {
  if (!els.accountsPanel) return;
  els.accountsPanel.hidden = true;
  els.accountsPanel.innerHTML = "";
}

function renderAnalysis(report) {
  if (els.monthlyCard) els.monthlyCard.style.display = "none";
  const published = publishedAccounts(report);
  const roster = accountRoster(report);
  if (!published.length) {
    // Three other consumers read `.statement` off `currentAnalysis` (the summary button and both transaction
    // renderers), so a payload with no account to show must never reach them.
    currentAnalysis = null;
    currentDocument = null;
    hideAccountsPanel();
    if (els.transactionCard) els.transactionCard.style.display = "none";
    renderError("This statement published no account to show.");
    return;
  }
  if (!isDocumentPayload(report) && roster.length < 2) {
    currentDocument = null;
    selectedAccountIndex = null;
    hideAccountsPanel();
    renderAccount(report);
    return;
  }
  currentDocument = report;
  const unverified = unverifiedMainAccount(roster);
  if (unverified && (!allAccountsView() || selectedAccountIndex === null || !published[selectedAccountIndex])) {
    // The business checking account was not verified: no other account stands in for it. With All accounts on,
    // the table lists every account and the one the user selects is shown, never as the main account.
    renderUnverifiedMain(published, roster, unverified);
    return;
  }
  const main = unverified ? -1 : mainAccountIndex(published, roster);
  // The main account printed no activity: it needs review, and the active account (the best-ranked verified one)
  // stays shown.
  const idleMain = unverified ? null : idleMainAccount(roster);
  if (!allAccountsView() || selectedAccountIndex === null || !published[selectedAccountIndex]) {
    selectedAccountIndex = main;
  }
  renderAccountsPanel(published, roster, main, selectedAccountIndex, unverified, idleMain);
  const shown = published[selectedAccountIndex];
  // One account's own payload: every panel below, the summary and the transaction list describe that account.
  renderAccount(isDocumentPayload(report) ? { ...shown, parse_mode: report.parse_mode } : report);
  if (idleMain) {
    // The summary box is the actions' (idleMainNote says it there); this runs again on every account selection and
    // settings change, so it only sets.
    els.statusHeading.textContent = "Main account needs review";
    setBanner("pending", "Main account had no activity; showing the active account", "Review required");
    els.decisionPill.textContent = "review required";
    els.decisionPill.className = "decision-pill";
    // Above the shown account's own rows (its "Validation" is that account's).
    els.statusList.insertAdjacentHTML("afterbegin", statusRowHtml(["Main account", "No activity; needs review"]));
  }
}

function renderAccount(report) {
  currentAnalysis = report;
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
  const validation = validationLabel(report);
  const elapsed = startedAt ? `${((Date.now() - startedAt) / 1000).toFixed(1)}s` : "Complete";
  const decision = hasMaterialPotentialLenderDebits(metrics) || metrics.revenue_review_required
    ? "review_required"
    : quality.corporate_use || quality.level || "review_required";

  els.statusHeading.textContent = "OCR completed";
  setBanner("done", "Extraction completed", validation);
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
    ["Eligible deposits basis", metrics.withholding_denominator_label || "Eligible deposits"],
    ["Validation", validation],
    ["Text blocks detected", formatNumber(transactions.length || metrics.effective_num_deposits || "--")],
    ["File size", formatBytes(currentFile && currentFile.size)],
  ]);

  renderMetricSections([
    {
      title: "Credits",
      sub: "Posted credit transactions",
      items: [
        ["Total Credits", formatMoney(totalCredits, currency), REVENUE_METRIC_COPY.totalCredits, "CR", "green"],
        ["Verified Revenue", formatMoney(metrics.verified_revenue_total, currency), REVENUE_METRIC_COPY.verifiedRevenue, "REV", "green", { revenueFilter: "verified_revenue" }],
        ["Unverified Deposits", formatMoney(metrics.unverified_deposit_total, currency), REVENUE_METRIC_COPY.unverifiedDeposits, "?", "amber", { revenueFilter: "unverified_deposit" }],
        ["Non-Revenue", formatMoney(metrics.non_revenue_total, currency), REVENUE_METRIC_COPY.nonRevenue, "X", "neutral", { revenueFilter: "non_revenue" }],
        ["Revenue Upper Bound", formatMoney(metrics.maximum_revenue, currency), REVENUE_METRIC_COPY.revenueUpperBound, "MAX", "neutral"],
        ["ACH Credits", formatNumber(metrics.ach_credit_count), REVENUE_METRIC_COPY.achCredits, "ACH", "neutral"],
      ],
    },
    {
      title: "Debits",
      sub: "Posted debit transactions",
      items: [
        ["Total Debits", formatMoney(totalDebits, currency), "All posted debit transactions", "DB", "neutral"],
        ["Confirmed Withholding", formatPercent(metrics.withholding_rate), withholdingAuditNote(metrics, currency), "%", withholdingTone(metrics.withholding_rate)],
        ["ACH Debits", formatNumber(metrics.ach_debit_count), "Posted ACH debit transactions", "ACH", "neutral"],
        ["POS Transactions", formatNumber(metrics.pos_count), "Card purchase transactions", "POS", "neutral"],
        ["ATM Withdrawals", formatNumber(metrics.atm_withdrawal_count), "Posted ATM withdrawals", "ATM", "neutral"],
        ["Checks Detected", formatNumber(metrics.check_count), "Posted check transactions", "CHK", "neutral"],
      ],
    },
    {
      title: "Risk Signals",
      sub: "NSFs and balances",
      items: [
        ["NSFs", formatNumber(metrics.effective_nsf_count), nsfSourceLabel(metrics.nsf_source), "NSF", countTone(metrics.effective_nsf_count)],
        ["Document Integrity", integrityLabel(integrity), (integrity.flags || []).join(", ") || "No source contradictions detected", "DOC", integrityTone(integrity)],
        ["Average Daily Balance", formatMoney(metrics.average_daily_balance, currency), averageBalanceNote(metrics), "AVG", averageBalanceTone(metrics)],
        ["Ending Balance", formatMoney(statement.ending_balance, currency), "Closing balance for the statement period", "END", "neutral"],
        ["Lowest Balance", formatMoney(metrics.min_balance, currency), "Lowest daily ending balance", "LOW", negativeTone(metrics.min_balance)],
        ["Highest Balance", formatMoney(metrics.max_balance, currency), "Highest daily ending balance", "HIGH", "neutral"],
      ],
    },
    {
      title: "Lenders",
      sub: "Lender and insurance transaction analysis",
      items: [
        ["Confirmed Lenders", formatNumber(metrics.lenders_detected), "Lenders confirmed from statement transactions", "LEN", presenceTone(metrics.lenders_detected)],
        ["Potential Lenders", formatNumber(metrics.potential_lenders_detected), "Possible lenders requiring analyst review", "?", countTone(metrics.potential_lenders_detected)],
        ["Confirmed Lender Debit Count", formatNumber(metrics.lender_debit_count), "Transactions paid to confirmed lenders", "DB", "neutral"],
        ["Confirmed Lender Debits", formatMoney(metrics.lender_debits, currency), "Total paid to confirmed lenders", "$", "neutral"],
        ["Potential Lender Debit Count", formatNumber(metrics.potential_lender_debit_count), "Transactions linked to possible lenders", "DB", countTone(metrics.potential_lender_debit_count)],
        ["Potential Lender Debits", formatMoney(potentialLenderDebitTotal(metrics), currency), "Excluded until lender status is confirmed", "$", countTone(metrics.potential_lender_debit_count)],
        ["Eligible Deposits", formatMoney(metrics.potential_withholding_denominator ?? metrics.eligible_deposits, currency), activeDenominatorNote(metrics), "DEP", "neutral"],
        ["Potential Withholding Exposure", formatPercent(metrics.potential_withholding_exposure), potentialWithholdingAuditNote(metrics, currency), "%", hasMaterialPotentialLenderDebits(metrics) ? "amber" : "neutral"],
        ["Insurance Debits", formatNumber(metrics.insurance_count), "Insurance debit transactions", "INS", "neutral"],
        ["Insurance Total", formatMoney(metrics.insurance_total, currency), "Excluded from lender payment totals", "$", "neutral"],
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
  setBanner("error", "Processing failed", "Failed");
  els.decisionPill.textContent = "review required";
  els.decisionPill.className = "decision-pill error";
  els.summaryBox.textContent = message;
  renderAccountSummary(accountFieldRows());
}

function sourceContradiction(message) {
  // A verified contradiction in the statement itself (vlm/source_contradiction.py is_source_contradiction): the
  // statement's own printed figures contradict the transactions it lists, every one of which was read and checked
  // against the PDF's text. A valid failure of the statement, not of the reading (owner ruling, 2026-09-23).
  const text = String(message || "");
  return /^Fail: Statement (?:debit total|credit total|ending balance) \([^()]{1,80}\) contradiction$/.test(text)
    ? text : null;
}

function renderExtractionReview(message) {
  // A completed read can require review without admitting any metrics. Clear
  // the previous statement's cards before exposing this read's source actions.
  currentAnalysis = null;
  setInitialState();
  setProgress(false);
  const contradiction = sourceContradiction(message);
  if (contradiction) {
    els.statusHeading.textContent = contradiction;
    setBanner("error", "Statement does not add up; metrics withheld", "Failed");
    els.decisionPill.textContent = "fail";
    els.decisionPill.className = "decision-pill";
    els.summaryBox.textContent = `${contradiction}. The statement's own printed figures contradict the transactions `
      + "it lists. Every listed transaction was read and checked against the PDF's own text, so this is a failure "
      + "of the statement, not of the reading. No metrics have been published.";
    setStatusRows([
      ["OCR completed", "Yes"],
      ["Validation", "Failed: statement contradiction"],
      ["Metrics", "Withheld"],
    ]);
    return;
  }
  els.statusHeading.textContent = "Extraction needs review";
  setBanner("pending", "Extraction available; metrics withheld", "Review required");
  els.decisionPill.textContent = "review required";
  els.decisionPill.className = "decision-pill";
  els.summaryBox.textContent = `${friendlyAnalysisError(message)} Open Review extraction to inspect the reading and its review status. No metrics have been published.`;
  setStatusRows([
    ["OCR completed", "Yes"],
    ["Validation", "Review required"],
    ["Metrics", "Withheld"],
  ]);
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
    ["Validation", "--"],
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
  currentDocument = null;
  selectedAccountIndex = null;
  hideAccountsPanel();
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
      if (!response.ok) {
        // Server-side upload validation replies {"error": ..., "filename": ...}.
        // Showing the bare status code would hide which file was refused and why.
        const fallback = `Upload failed (${response.status})`;
        return response.json().then(
          (body) => {
            const reason = body.error || fallback;
            throw new Error(body.filename ? `${reason}: ${body.filename}` : reason);
          },
          () => { throw new Error(fallback); },
        );
      }
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
      const stage = processingStageLabel(status.stage || status.status);
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
        ["Validation", "--"],
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
      currentMarkdown = markdown || "";
      if (!payload.analysis) {
        renderExtractionReview(payload.analysis_error);
        setActions(jobId, false, true);
        return;
      }
      renderAnalysis(payload.analysis);
      setActions(jobId, true);
      // A statement whose main account was not verified keeps its explanation in the summary; one whose main account
      // printed no activity says so first.
      if (currentAnalysis) {
        const currency = (currentAnalysis.statement || {}).currency || null;
        els.summaryBox.textContent = `${idleMainNote(currentDocument, currency)}Exports and copy actions are ready.`;
      }
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
  // A package is several statements, never one statement's accounts: the account view and its selection go.
  currentDocument = null;
  selectedAccountIndex = null;
  hideAccountsPanel();
  currentAnalysis = { package: pkg };
  currentMarkdown = "";
  renderMainTransactions();
  const totals = pkg.totals || {};
  const documents = Array.isArray(pkg.documents) ? pkg.documents : [];
  const funders = Array.isArray(pkg.funders) ? pkg.funders : [];
  const potentialLenders = Array.isArray(pkg.potential_lenders) ? pkg.potential_lenders : [];
  const insuranceProviders = Array.isArray(pkg.insurance_providers) ? pkg.insurance_providers : [];
  const validation = packageValidationLabel(pkg);
  // CURRENCY DOCTRINE §D: ONE denominated set of package figures. §F: none at
  // all when the package could not prove a single currency.
  const currencyInfo = packageCurrencyInfo(pkg);
  const currency = currencyInfo.currency;
  const refusalNote = currencyInfo.refused ? packageCurrencyRefusalNote(currencyInfo) : null;
  const moneyNote = (note) => refusalNote || note;

  els.statusHeading.textContent = "Package completed";
  setBanner("done", "Package analysis completed", validation);
  els.decisionPill.textContent = labelize(totals.decision || "review required");
  els.decisionPill.className = `decision-pill ${totals.decision || ""}`.trim();
  setStatusRows([
    ["Statements completed", `${formatNumber(totals.completed)} / ${formatNumber(totals.documents)}`],
    ["Package currency", packageCurrencyLabel(currencyInfo)],
    ["Approved", formatNumber(totals.approved)],
    ["Manual review", formatNumber(totals.manual_review)],
    ["High integrity risk", formatNumber(totals.integrity_high)],
    ["Processing errors", formatNumber(totals.failed)],
    ["Confirmed withholding", formatPercent(totals.package_withholding_rate)],
    ["Potential exposure", formatPercent(totals.potential_withholding_exposure)],
    ["Revenue reconciliation", totals.revenue_reconciles ? "Balanced" : "Review required"],
    ["Eligible deposits basis", totals.withholding_denominator_label || "Eligible deposits"],
  ]);

  renderMetricSections([
    {
      title: "Package Revenue",
      // MINOR-10 (the L1-S3 review): `months` counts MEMBERS and this label
      // says PERIODS. They are the same number until a document publishes two
      // accounts, and two accounts of one document are one statement period.
      // The server publishes `statement_periods` only when the two differ, so
      // this reads the honest count where there is one and the old one where
      // nothing changed.
      sub: `${formatNumber(totals.statement_periods ?? totals.months)} statement periods`,
      items: [
        ["Total Credits", formatMoney(totals.total_credits, currency), moneyNote(REVENUE_METRIC_COPY.totalCredits), "CR", "green"],
        ["Verified Revenue", formatMoney(totals.verified_revenue_total, currency), moneyNote(REVENUE_METRIC_COPY.verifiedRevenue), "REV", "green", { revenueFilter: "verified_revenue" }],
        ["Unverified Deposits", formatMoney(totals.unverified_deposit_total, currency), moneyNote(REVENUE_METRIC_COPY.unverifiedDeposits), "?", "amber", { revenueFilter: "unverified_deposit" }],
        ["Non-Revenue", formatMoney(totals.non_revenue_total, currency), moneyNote(REVENUE_METRIC_COPY.nonRevenue), "X", "neutral", { revenueFilter: "non_revenue" }],
        ["Revenue Upper Bound", formatMoney(totals.maximum_revenue, currency), moneyNote(REVENUE_METRIC_COPY.revenueUpperBound), "MAX", "neutral"],
        ["Avg Monthly Credits", formatMoney(totals.avg_monthly_credits, currency), moneyNote("Average posted credits per statement period"), "AVG", "neutral"],
        ["Total Debits", formatMoney(totals.total_debits, currency), moneyNote("All posted debit transactions"), "DB", "neutral"],
        ["Avg Monthly Debits", formatMoney(totals.avg_monthly_debits, currency), moneyNote("Average posted debits per statement period"), "AVG", "neutral"],
      ],
    },
    {
      title: "Cash Flow",
      sub: "Package-level affordability signals",
      items: [
        ["Total Cash Flow", formatMoney(totals.cash_flow, currency), moneyNote("Credits minus debits"), "CF", negativeTone(totals.cash_flow)],
        ["Avg Monthly Cash Flow", formatMoney(totals.avg_monthly_cash_flow, currency), moneyNote("Average statement cash flow"), "AVG", negativeTone(totals.avg_monthly_cash_flow)],
        ["Average Daily Balance", formatMoney(totals.average_daily_balance, currency), moneyNote(packageAverageBalanceNote(documents)), "ADB", currencyInfo.refused ? "amber" : packageAverageBalanceTone(documents)],
        ["NSFs", formatNumber(totals.nsf_count), totals.nsf_source === "mixed" ? "Members counted on different bases" : nsfSourceLabel(totals.nsf_source), "NSF", countTone(totals.nsf_count)],
        ["Confirmed Withholding", formatPercent(totals.package_withholding_rate), moneyNote(withholdingAuditNote(totals, currency)), "%", withholdingTone(totals.package_withholding_rate)],
      ],
    },
    {
      title: "Quality",
      sub: "Corporate-use readiness",
      items: [
        ["Approved", formatNumber(totals.approved), "Corporate-approved statements", "OK", totals.approved ? "green" : "neutral"],
        ["Manual Review", formatNumber(totals.manual_review), "Statements requiring analyst review", "REVIEW", totals.manual_review ? "amber" : "neutral"],
        ["Integrity High", formatNumber(totals.integrity_high), "Possible document issue", "DOC", countTone(totals.integrity_high)],
        ["Failed", formatNumber(totals.failed), "Statements needing rerun", "ERR", countTone(totals.failed)],
      ],
    },
    {
      title: "Lenders",
      sub: "Lender and insurance transaction analysis",
      items: [
        ["Confirmed Lenders", formatNumber(totals.lenders_detected), "Lenders confirmed from statement transactions", "LEN", presenceTone(totals.lenders_detected)],
        ["Potential Lenders", formatNumber(totals.potential_lenders_detected), "Possible lenders requiring analyst review", "?", countTone(totals.potential_lenders_detected)],
        ["Confirmed Lender Debit Count", formatNumber(totals.lender_debit_count), "Transactions paid to confirmed lenders", "DB", "neutral"],
        ["Confirmed Lender Debits", formatMoney(totals.lender_debits, currency), moneyNote("Total paid to confirmed lenders"), "$", "neutral"],
        ["Potential Lender Debit Count", formatNumber(totals.potential_lender_debit_count), "Transactions linked to possible lenders", "DB", countTone(totals.potential_lender_debit_count)],
        ["Potential Lender Debits", formatMoney(potentialLenderDebitTotal(totals), currency), moneyNote("Excluded until lender status is confirmed"), "$", countTone(totals.potential_lender_debit_count)],
        ["Eligible Deposits", formatMoney(totals.potential_withholding_denominator ?? totals.eligible_deposits, currency), moneyNote(activeDenominatorNote(totals)), "DEP", "neutral"],
        ["Potential Withholding Exposure", formatPercent(totals.potential_withholding_exposure), moneyNote(potentialWithholdingAuditNote(totals, currency)), "%", hasMaterialPotentialLenderDebits(totals) ? "amber" : "neutral"],
        ["Insurance Debits", formatNumber(totals.insurance_count), "Insurance debit transactions", "INS", "neutral"],
        ["Insurance Total", formatMoney(totals.insurance_total, currency), moneyNote("Excluded from lender payment totals"), "$", "neutral"],
      ],
    },
  ]);

  renderAccountSummary([
    ["Package Decision", labelize(totals.decision || "review required")],
    ["Statements", `${formatNumber(totals.completed)} completed of ${formatNumber(totals.documents)}`],
    ["Currency", packageCurrencyLabel(currencyInfo)],
    ["Period Range", packagePeriod(documents)],
    ["Average Daily Balance", formatMoney(totals.average_daily_balance, currency)],
    ["Top Lenders", funders.length ? funders.slice(0, 3).map((f) => f.funder).join(", ") : "None detected"],
    ["Confirmed Lender Debits", formatMoney(totals.lender_debits, currency)],
    ["Potential Lender Debits", formatMoney(potentialLenderDebitTotal(totals), currency)],
    ["Potential Exposure", formatPercent(totals.potential_withholding_exposure)],
  ]);
  renderPackageTables(pkg);
}

function renderPackageTables(pkg) {
  const documents = Array.isArray(pkg.documents) ? pkg.documents : [];
  const funders = Array.isArray(pkg.funders) ? pkg.funders : [];
  const potentialLenders = Array.isArray(pkg.potential_lenders) ? pkg.potential_lenders : [];
  const insuranceProviders = Array.isArray(pkg.insurance_providers) ? pkg.insurance_providers : [];
  // These rollups sum across the whole package, so they are denominated by the
  // package currency - null when there is not one, in which case the backend
  // has already refused their money and `formatMoney` renders "N/A".
  const currency = packageCurrencyInfo(pkg).currency;
  renderLenders(funders, potentialLenders, currency);
  renderInsurance(insuranceProviders, currency);
  renderRevenueEvidence(pkg.totals || {}, currency);
  if (els.monthlyCard) els.monthlyCard.style.display = "block";
  if (els.monthlyCount) {
    els.monthlyCount.textContent = `${documents.length} ${documents.length === 1 ? "statement" : "statements"}`;
  }
  if (!els.monthlyTable) return;
  if (!documents.length) {
    els.monthlyTable.innerHTML = `
      <tr>
        <td>No statements</td>
        <td>N/A</td>
        <td>N/A</td>
        <td>N/A</td>
        <td>N/A</td>
        <td>N/A</td>
        <td>${glassChip("◐", "Review", "amber")}</td>
      </tr>
    `;
  } else {
    // The CRM's seasonality layout: one row per statement month, in calendar order.
    const rows = documents.map((doc) => ({ doc, month: statementMonth(doc.period_start, doc.period_end) }));
    rows.sort((a, b) => (a.month ? a.month.key : Infinity) - (b.month ? b.month.key : Infinity));
    // Each row is denominated by its OWN statement (CURRENCY DOCTRINE §F). The column names say ($) as the
    // CRM does; when one package mixes currencies, a non-USD row names its unit so no figure passes for USD.
    const currencies = new Set(documents.map((doc) => ("currency" in doc ? doc.currency : "USD") || "USD"));
    els.monthlyTable.innerHTML = rows.map(({ doc, month }) => {
      const status = doc.status !== "done" ? "Failed" : labelize(doc.corporate_use || doc.quality || "review");
      const docCurrency = ("currency" in doc ? doc.currency : "USD") || "USD";
      const unit = currencies.size > 1 && docCurrency !== "USD" ? ` ${docCurrency}` : "";
      const amount = (value) => {
        const text = formatWhole(value);
        return text === "N/A" ? text : text + unit;
      };
      return `
        <tr title="${escapeHtml(doc.filename || "Statement")}">
          <td>${escapeHtml(month ? MONTH_NAMES[month.month] : "N/A")}</td>
          <td>${escapeHtml(month ? String(month.year) : "N/A")}</td>
          <td>${escapeHtml(amount(doc.credits))}</td>
          <td>${escapeHtml(formatWhole(doc.deposit_count))}</td>
          <td>${escapeHtml(amount(doc.average_daily_balance))}</td>
          <td>${escapeHtml(formatNumber(doc.nsf_count))}</td>
          <td><button class="table-action statement-open" type="button" data-job-id="${escapeHtml(doc.id)}" ${doc.status === "done" ? "" : "disabled"}>${escapeHtml(status === "Failed" ? "Unavailable" : "Open")}</button></td>
        </tr>
      `;
    }).join("");
  }

  const lenderSummary = funders.length
    ? funders.map((funder) => `${funder.funder}: ${formatMoney(funder.total_debited, currency)} across ${formatNumber(funder.documents)} statement(s)`).join("\n")
    : "No lenders detected across the package.";
  els.summaryBox.textContent = `Package lender summary:\n${lenderSummary}`;
}

function openStatementModal(jobId) {
  if (!els.statementModalBackdrop) return;
  modalLastFocus = document.activeElement;
  modalAnalysis = null;
  modalJobId = jobId;
  if (els.modalExtractionReview) {
    els.modalExtractionReview.href = `/result/${encodeURIComponent(jobId)}`;
  }
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
      // Same rule as `renderAnalysis`: the modal's transaction renderer reads
      // `.statement` off this global, so it holds ONE account's payload (the
      // main account of a statement holding several), never the document.
      modalAnalysis = modalAccountPayload(payload.analysis);
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

function modalAccountPayload(report) {
  // The statement modal shows one account: of a statement holding several, its main account; none when the main
  // account (the business checking account) was not verified.
  const roster = accountRoster(report);
  if (unverifiedMainAccount(roster)) return null;
  if (!isDocumentPayload(report)) return report;
  const published = publishedAccounts(report);
  if (!published.length) return null;
  const main = mainAccountIndex(published, accountRoster(report));
  return { ...published[main], parse_mode: report.parse_mode };
}

function renderStatementModal(jobId, report, markdown) {
  let accountNote = "";
  const unverifiedMain = unverifiedMainAccount(accountRoster(report));
  if (unverifiedMain) {
    els.statementModalTitle.textContent = "Main account needs review";
    els.statementModalSubtitle.textContent = `${accountDisplayName({}, unverifiedMain)} could not be verified: `
      + `${accountReasonText(unverifiedMain.reasons)}. No metrics are shown for it.`;
    els.statementModalMetrics.innerHTML = "";
    els.statementModalAccount.innerHTML = "";
    els.statementModalLenders.innerHTML = "";
    els.statementModalInsurance.innerHTML = "";
    els.statementModalRevenue.innerHTML = "";
    els.statementModalTransactions.innerHTML = "";
    els.statementModalTransactionCount.textContent = "";
    return;
  }
  // Owner ruling, 2026-09-23: an idle main account needs review; the active account stays shown.
  const idleMain = idleMainAccount(accountRoster(report));
  if (isDocumentPayload(report)) {
    const count = Math.max(publishedAccounts(report).length, accountRoster(report).length);
    const shown = modalAccountPayload(report);
    if (shown) {
      accountNote = `Main account of ${formatNumber(count)} - `;
      report = shown;
    }
  }
  if (idleMain) {
    accountNote = `Main account ${accountDisplayName({}, idleMain)} had no activity and needs review; `
      + "showing the active account - ";
  }
  if (isDocumentPayload(report)) {
    els.statementModalTitle.textContent = "Multi-account statement";
    els.statementModalSubtitle.textContent = "This statement published no account to show.";
    els.statementModalMetrics.innerHTML = "";
    els.statementModalAccount.innerHTML = "";
    els.statementModalLenders.innerHTML = "";
    els.statementModalInsurance.innerHTML = "";
    els.statementModalRevenue.innerHTML = "";
    els.statementModalTransactions.innerHTML = "";
    els.statementModalTransactionCount.textContent = "";
    // The modal is already open -- `openStatementModal` ran before the fetch
    // that produced this payload, and calling it again would clear the job it
    // was opened for.
    return;
  }
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
  els.statementModalSubtitle.textContent = `${accountNote}${period(statement)} - ${labelize(decision)}`;
  els.statementModalMetrics.innerHTML = [
    ["Total Credits", formatMoney(metrics.effective_total_deposits, currency), REVENUE_METRIC_COPY.totalCredits, "CR", "green"],
    ["Verified Revenue", `${formatNumber(metrics.verified_revenue_count)} / ${formatMoney(metrics.verified_revenue_total, currency)}`, REVENUE_METRIC_COPY.verifiedRevenue, "REV", "green", { revenueFilter: "verified_revenue" }],
    ["Unverified Deposits", `${formatNumber(metrics.unverified_deposit_count)} / ${formatMoney(metrics.unverified_deposit_total, currency)}`, REVENUE_METRIC_COPY.unverifiedDeposits, "?", "amber", { revenueFilter: "unverified_deposit" }],
    ["Non-Revenue", `${formatNumber(metrics.non_revenue_count)} / ${formatMoney(metrics.non_revenue_total, currency)}`, REVENUE_METRIC_COPY.nonRevenue, "X", "neutral", { revenueFilter: "non_revenue" }],
    ["Revenue Upper Bound", formatMoney(metrics.maximum_revenue, currency), REVENUE_METRIC_COPY.revenueUpperBound, "MAX", "neutral"],
    ["Total Debits", formatMoney(metrics.effective_total_withdrawals, currency), "All posted debit transactions", "DB", "neutral"],
    ["Cash Flow", formatMoney(metrics.cash_flow, currency), "Credits minus debits", "CF", negativeTone(metrics.cash_flow)],
    ["Average Daily Balance", formatMoney(metrics.average_daily_balance, currency), averageBalanceNote(metrics), "AVG", averageBalanceTone(metrics)],
    ["Ending Balance", formatMoney(statement.ending_balance, currency), "Closing balance for the statement period", "END", "neutral"],
    ["NSFs", formatNumber(metrics.effective_nsf_count), nsfSourceLabel(metrics.nsf_source), "NSF", countTone(metrics.effective_nsf_count)],
    ["Confirmed Withholding", formatPercent(metrics.withholding_rate), withholdingAuditNote(metrics, currency), "%", withholdingTone(metrics.withholding_rate)],
    ["Confirmed Lenders", formatNumber(metrics.lenders_detected), "Lenders confirmed from statement transactions", "LEN", presenceTone(metrics.lenders_detected)],
    ["Potential Lenders", formatNumber(metrics.potential_lenders_detected), "Possible lenders requiring analyst review", "?", countTone(metrics.potential_lenders_detected)],
    ["Confirmed Lender Debits", `${formatNumber(metrics.lender_debit_count)} / ${formatMoney(metrics.lender_debits, currency)}`, "Transaction count and total paid to confirmed lenders", "DB", "neutral"],
    ["Potential Lender Debits", `${formatNumber(metrics.potential_lender_debit_count)} / ${formatMoney(potentialLenderDebitTotal(metrics), currency)}`, "Transaction count and total linked to possible lenders", "?", countTone(metrics.potential_lender_debit_count)],
    ["Eligible Deposits", formatMoney(metrics.potential_withholding_denominator ?? metrics.eligible_deposits, currency), activeDenominatorNote(metrics), "DEP", "neutral"],
    ["Potential Withholding Exposure", formatPercent(metrics.potential_withholding_exposure), potentialWithholdingAuditNote(metrics, currency), "%", hasMaterialPotentialLenderDebits(metrics) ? "amber" : "neutral"],
    ["Insurance", `${formatNumber(metrics.insurance_count)} / ${formatMoney(metrics.insurance_total, currency)}`, "Transaction count and total excluded from lender payments", "INS", "neutral"],
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
    // The copied summary is the artefact an analyst pastes into a credit memo,
    // so it must carry the package's real denomination — or none at all when
    // the package has no single one (CURRENCY DOCTRINE §D/§F).
    const currency = packageCurrencyInfo(pkg).currency;
    els.summaryBox.textContent =
      `Package ${packagePeriod(pkg.documents || [])}: ${formatNumber(totals.completed)} of ${formatNumber(totals.documents)} statements completed, ` +
      `${formatMoney(totals.avg_monthly_credits, currency)} average monthly credits, ${formatMoney(totals.avg_monthly_cash_flow, currency)} average monthly cash flow, ` +
      `${formatNumber(totals.nsf_count)} NSF events, ${formatPercent(totals.package_withholding_rate)} confirmed withholding, ` +
      `${formatMoney(potentialLenderDebitTotal(totals), currency)} potential lender debits and ${formatPercent(totals.potential_withholding_exposure)} potential exposure. ` +
      `${formatNumber(funders.length)} confirmed lender detections. Decision: ${labelize(totals.decision || "review required")}.`;
    return;
  }
  const s = currentAnalysis.statement || {};
  const m = currentAnalysis.metrics || {};
  const d = currentAnalysis.detection || {};
  const q = currentAnalysis.quality || {};
  const currency = s.currency || "USD";
  const lenders = Array.isArray(d.known_funders) ? d.known_funders.length : 0;
  // The statement's main account printed no activity: the summary an analyst pastes says so, and whose figures follow;
  // the statement needs review, as the dashboard says.
  const idleNote = idleMainNote(currentDocument, currency);
  const decision = idleNote || hasMaterialPotentialLenderDebits(m)
    ? "review_required"
    : q.corporate_use || q.level || "review_required";
  els.summaryBox.textContent =
    (idleNote ? `${idleNote}Figures for the active account, ${accountDisplayName(s, null)}: ` : "") +
    `${s.bank || "Statement"} ${period(s)}: average daily balance ${formatMoney(m.average_daily_balance, currency)}, ` +
    `ending balance ${formatMoney(s.ending_balance, currency)}, cash flow ${formatMoney(m.cash_flow, currency)}, ` +
    `${formatNumber(m.effective_nsf_count)} NSF events, ${formatNumber(lenders)} confirmed lender detections, ` +
    `${formatMoney(m.lender_debits, currency)} confirmed lender debits, and ` +
    `${formatMoney(potentialLenderDebitTotal(m), currency)} potential lender debits at ${formatPercent(m.potential_withholding_exposure)} exposure. ` +
    `Status: ${labelize(decision)}.`;
}

const pageTitle = document.querySelector(".page-title h1");
const pageSubtitle = document.querySelector(".page-title p");
const dashboardTitle = { title: pageTitle.textContent, subtitle: pageSubtitle.textContent };

function showView(view) {
  const settings = view === "settings";
  document.querySelector(".top-grid").hidden = settings;
  document.querySelector(".main-grid").hidden = settings;
  els.settingsView.hidden = !settings;
  document.querySelector(".workspace").classList.toggle("settings-open", settings);
  pageTitle.textContent = settings ? "Settings" : dashboardTitle.title;
  pageSubtitle.textContent = settings ? "How results are calculated and shown" : dashboardTitle.subtitle;
  if (settings) loadSettings();
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.remove("active");
      item.removeAttribute("aria-current");
    });
    button.classList.add("active");
    button.setAttribute("aria-current", "page");
    showView(button.dataset.view);
  });
});

function loadSettings() {
  els.nsfCarryOverToggle.disabled = true;
  fetch("/api/settings")
    .then((response) => {
      if (!response.ok) throw new Error(`Settings unavailable (${response.status})`);
      return response.json();
    })
    .then(({ settings }) => {
      els.nsfCarryOverToggle.checked = settings.nsf_carry_over === true;
      els.nsfCarryOverToggle.disabled = false;
      els.settingsStatus.textContent = "";
    })
    .catch((error) => {
      els.settingsStatus.textContent = error.message || String(error);
    });
}

function refreshShownResults() {
  // A setting changes how a result is presented, so whatever is open is fetched again.
  if (currentJobIds.length > 1) loadPackage(currentJobIds);
  else if (currentJobId && currentAnalysis) loadResults(currentJobId);
}

els.nsfCarryOverToggle.addEventListener("change", () => {
  const wanted = els.nsfCarryOverToggle.checked;
  els.nsfCarryOverToggle.disabled = true;
  els.settingsStatus.textContent = "Saving...";
  fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nsf_carry_over: wanted }),
  })
    .then((response) => response.json().then((payload) => ({ response, payload })))
    .then(({ response, payload }) => {
      if (!response.ok || !payload.settings) throw new Error(payload.error || `Save failed (${response.status})`);
      els.nsfCarryOverToggle.checked = payload.settings.nsf_carry_over === true;
      els.settingsStatus.textContent = payload.settings.nsf_carry_over
        ? "Saved. NSF counts now carry the balance over inactive days."
        : "Saved. NSF counts now use printed days only.";
      refreshShownResults();
    })
    .catch((error) => {
      els.nsfCarryOverToggle.checked = !wanted;
      els.settingsStatus.textContent = error.message || String(error);
    })
    .finally(() => {
      els.nsfCarryOverToggle.disabled = false;
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
      // The refresh path, held to the same rule as the open path above.
      modalAnalysis = modalAccountPayload(payload.analysis);
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

/* --- settings -----------------------------------------------------------
   Page preferences, kept in this browser only. "All accounts" changes what the
   panels show of a statement that holds several accounts, never what was read. */
function syncAllAccountsToggle() {
  if (!els.allAccountsToggle) return;
  const on = allAccountsView();
  els.allAccountsToggle.checked = on;
  els.allAccountsToggle.setAttribute("aria-checked", on ? "true" : "false");
}

function setAllAccountsView(on) {
  try { localStorage.setItem(ALL_ACCOUNTS_KEY, on ? "on" : "off"); } catch (error) { /* private mode */ }
  syncAllAccountsToggle();
  // Only a statement on screen is redrawn: never a package, never a statement still processing.
  const statementShown = currentDocument && !(currentAnalysis && currentAnalysis.package) && currentJobIds.length <= 1;
  if (statementShown) renderAnalysis(currentDocument);
}

function setSettingsOpen(open) {
  if (!els.settingsPanel || !els.settingsBtn) return;
  els.settingsPanel.hidden = !open;
  els.settingsBtn.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) els.allAccountsToggle?.focus();
}

els.settingsBtn?.addEventListener("click", (event) => {
  event.stopPropagation();
  setSettingsOpen(els.settingsPanel.hidden);
});
els.settingsPanel?.addEventListener("click", (event) => event.stopPropagation());
document.addEventListener("click", () => {
  if (els.settingsPanel && !els.settingsPanel.hidden) setSettingsOpen(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && els.settingsPanel && !els.settingsPanel.hidden) {
    setSettingsOpen(false);
    els.settingsBtn?.focus();
  }
});
els.allAccountsToggle?.addEventListener("change", () => setAllAccountsView(els.allAccountsToggle.checked));
syncAllAccountsToggle();

function selectAccountFrom(event) {
  const target = event.target instanceof Element ? event.target : null;
  const row = target ? target.closest("tr[data-account-index]") : null;
  if (!row || !currentDocument) return;
  const index = Number(row.getAttribute("data-account-index"));
  if (!Number.isInteger(index) || index === selectedAccountIndex) return;
  selectedAccountIndex = index;
  renderAnalysis(currentDocument);
  els.accountsPanel?.querySelector(`tr[data-account-index="${index}"]`)?.focus();
}

els.accountsPanel?.addEventListener("click", selectAccountFrom);
els.accountsPanel?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  selectAccountFrom(event);
});

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
