const els = {
  newView: document.getElementById("newView"),
  resultsView: document.getElementById("resultsView"),
  resultsEmpty: document.getElementById("resultsEmpty"),
  resultsEmptyTitle: document.getElementById("resultsEmptyTitle"),
  resultsEmptyCopy: document.getElementById("resultsEmptyCopy"),
  resultsContent: document.getElementById("resultsContent"),
  breadcrumb: document.getElementById("breadcrumb"),
  topbarHint: document.getElementById("topbarHint"),
  topbarNew: document.getElementById("topbarNew"),
  notificationsAnchor: document.getElementById("notificationsAnchor"),
  notificationsBtn: document.getElementById("notificationsBtn"),
  notificationsPopover: document.getElementById("notificationsPopover"),
  notificationsList: document.getElementById("notificationsList"),
  notifyDot: document.getElementById("notifyDot"),
  helpBtn: document.getElementById("helpBtn"),
  helpPopover: document.getElementById("helpPopover"),
  sidebarSearch: document.getElementById("sidebarSearch"),
  railSearch: document.getElementById("railSearch"),
  panelToggle: document.getElementById("panelToggle"),
  collapseSidebar: document.getElementById("collapseSidebar"),
  recentStatements: document.getElementById("recentStatements"),
  recentPackages: document.getElementById("recentPackages"),
  statementCount: document.getElementById("statementCount"),
  packageCount: document.getElementById("packageCount"),
  reviewCount: document.getElementById("reviewCount"),
  heroKicker: document.getElementById("heroKicker"),
  resultsTitle: document.getElementById("resultsTitle"),
  heroChips: document.getElementById("heroChips"),
  summaryPanel: document.getElementById("summaryPanel"),
  copySummaryBtn: document.getElementById("copySummaryBtn"),
  closeSummaryBtn: document.getElementById("closeSummaryBtn"),
  creditsLabel: document.getElementById("creditsLabel"),
  creditsValue: document.getElementById("creditsValue"),
  creditsMeta: document.getElementById("creditsMeta"),
  creditMixBar: document.getElementById("creditMixBar"),
  creditMixRows: document.getElementById("creditMixRows"),
  balanceChart: document.getElementById("balanceChart"),
  monthlyChart: document.getElementById("monthlyChart"),
  totalsGrid: document.getElementById("totalsGrid"),
  processingList: document.getElementById("processingList"),
  packageSummaryList: document.getElementById("packageSummaryList"),
  packageProcessingList: document.getElementById("packageProcessingList"),
  packageProcessingNote: document.getElementById("packageProcessingNote"),
  queueCard: document.getElementById("queueCard"),
  queueMeta: document.getElementById("queueMeta"),
  queueList: document.getElementById("queueList"),
  pagePreview: document.getElementById("pagePreview"),
  previewPrev: document.getElementById("previewPrev"),
  previewNext: document.getElementById("previewNext"),
  previewLabel: document.getElementById("previewLabel"),
  nsfExampleDays: document.getElementById("nsfExampleDays"),
  nsfExampleTotal: document.getElementById("nsfExampleTotal"),
  settingsView: document.getElementById("settingsView"),
  nsfCarryOverToggle: document.getElementById("nsfCarryOverToggle"),
  settingsStatus: document.getElementById("settingsStatus"),
  fileInput: document.getElementById("fileInput"),
  uploadBtn: document.getElementById("uploadBtn"),
  forceOcrToggle: document.getElementById("forceOcrToggle"),
  dropzone: document.getElementById("dropzone"),
  progressTrack: document.getElementById("progressTrack"),
  statusCard: document.getElementById("statusCard"),
  statusBanner: document.getElementById("statusBanner"),
  statusMark: document.getElementById("statusMark"),
  statusHeading: document.getElementById("statusHeading"),
  statusCopy: document.getElementById("statusCopy"),
  statusMessage: document.getElementById("statusMessage"),
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
// The view on screen: "new" (upload), "results" (a statement or package) or "settings".
let currentView = "new";
// One entry per uploaded file: its job once the server has created one, and the last status polled for it.
let queueEntries = [];
let previewJobId = null;
let previewPage = 0;

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
      ["NSFs", "N/A", "Days ending with a negative balance", "NSF", "neutral"],
      ["Average Daily Balance", "N/A", "Average of daily ending balances for the statement period", "AVG", "neutral"],
      ["Ending Balance", "N/A", "Closing balance for the statement period", "END", "neutral"],
      ["Lowest Balance", "N/A", "Lowest daily ending balance", "LOW", "neutral"],
      ["Highest Balance", "N/A", "Highest daily ending balance", "HIGH", "neutral"],
    ],
  },
  {
    title: "Lenders",
    layout: "wide",
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
  // Reject an impossible date (2026-02-30, month 13) rather than letting Date roll it into another month.
  if (Number.isNaN(day.getTime()) || day.getUTCMonth() !== Number(match[2]) - 1 || day.getUTCDate() !== Number(match[3])) {
    return null;
  }
  return day;
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
  return (Math.round(number) || 0).toLocaleString("en-US");  // `|| 0` turns a rounded -0 into 0
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
    ["Bank Name", statement.bank || "N/A"],
    ["Account Type", accountType || "N/A"],
    ["Account Number (masked)", maskAccount(accountNumber)],
    ["Routing Number", routing || "N/A"],
    ["Statement Period", period(statement)],
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
    confirmed_lender: { label: entity || "Confirmed lender", glyph: "LEN", tone: "violet" },
    potential_lender: { label: entity ? `${entity} (Potential)` : "Potential lender", glyph: "?", tone: "violet" },
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
    const decision = record.revenue_review_status === "confirmed" ? "Confirmed as revenue" : "Marked non-revenue";
    return `
      <div class="revenue-review-actions review-note">
        <span>${decision}</span>
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
  if (!visible.length) {
    // Date, Description, Category, Amount and Review, plus the optional Statement and Running Balance columns.
    const columns = 5 + (showSource ? 1 : 0) + (showRunningBalance ? 1 : 0);
    tableEl.innerHTML = `
      <tr>
        <td class="empty-cell" colspan="${columns}"><strong>No transactions found</strong>${escapeHtml(filter === "all" ? "No statement returned transaction rows." : "No rows matched this filter.")}</td>
      </tr>
    `;
    return;
  }
  const sourceLabels = showSource ? statementSourceLabels(rows) : null;
  tableEl.innerHTML = visible.map((tx) => {
    const amount = txAmount(tx);
    const category = transactionCategory(tx);
    // The combined package ledger interleaves rows from every statement, so a
    // row is denominated by the statement it came from, never by a package-wide
    // label that a mixed package does not have (CURRENCY DOCTRINE §F).
    const rowCurrency = "source_currency" in tx ? tx.source_currency : currency;
    const sourceName = tx.source_document || tx.source_bank || "Statement";
    const source = showSource
      ? `<td class="transaction-source"><span class="source-tag" title="${escapeHtml(sourceName)}">${escapeHtml(sourceLabels.get(tx.source_job) || sourceName)}</span></td>`
      : "";
    const reviewReason = revenueReviewReason(tx);
    const reviewReasonHtml = reviewReason
      ? `<div class="tx-reason"><strong>Reason:</strong> ${escapeHtml(reviewReason)}</div>`
      : "";
    const balance = runningBalanceValue(tx);
    const runningBalance = showRunningBalance
      ? `<td class="amount-cell tx-balance${balance !== null && balance < 0 ? " balance-negative" : ""}">${escapeHtml(formatMoney(balance, rowCurrency))}</td>`
      : "";
    return `
      <tr>
        <td class="tx-date">${escapeHtml(tx.date || "N/A")}</td>
        ${source}
        <td class="tx-desc">${escapeHtml(txDescriptionRaw(tx) || "N/A")}</td>
        <td>${glassChip(category.glyph, category.label, category.tone)}${reviewReasonHtml}</td>
        <td class="amount-cell ${amount < 0 ? "amount-debit" : "amount-credit"}">${amount > 0 ? "+" : ""}${escapeHtml(formatMoney(amount, rowCurrency))}</td>
        ${runningBalance}
        <td class="tx-review">${revenueReviewControls(tx, reviewJobId)}</td>
      </tr>
    `;
  }).join("");
}

// The combined ledger's Statement column names each row's statement by its month ("March 2026"). Two
// statements for one month (two accounts) would read the same, so those fall back to their file name.
function statementSourceLabels(transactions) {
  const months = new Map();
  transactions.forEach((tx) => {
    if (!tx.source_job || months.has(tx.source_job)) return;
    months.set(tx.source_job, statementMonth(tx.source_period_start, tx.source_period_end));
  });
  const perMonth = new Map();
  months.forEach((month) => { if (month) perMonth.set(month.key, (perMonth.get(month.key) || 0) + 1); });
  const labels = new Map();
  months.forEach((month, job) => {
    if (month && perMonth.get(month.key) === 1) labels.set(job, `${MONTH_NAMES[month.month]} ${month.year}`);
  });
  return labels;
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
  els.statusCard?.classList.toggle("busy", active);
}

function setBanner(state, title, meta) {
  els.statusBanner.className = `status-banner ${state || "pending"}`.trim();
  els.statusMark.textContent = state === "done" ? "✓" : state === "error" ? "!" : "·";
  els.statusCopy.textContent = title;
  els.validationValue.textContent = meta;
  if (state !== "error") setStatusMessage("");
}

function setStatusMessage(message) {
  if (!els.statusMessage) return;
  els.statusMessage.textContent = message || "";
  els.statusMessage.hidden = !message;
}

function kvRowsHtml(rows) {
  return rows.map(([key, value]) => `
    <div class="kv">
      <span class="kv-key">${escapeHtml(key)}</span>
      <span class="kv-value" title="${escapeHtml(value || "N/A")}">${escapeHtml(value || "N/A")}</span>
    </div>
  `).join("");
}

// One processing row, for a note placed ahead of the rows setStatusRows wrote.
function statusRowHtml(row) {
  return kvRowsHtml([row]);
}

// The processing rows show on the New analysis page while a job runs, and again beside the account details
// (a statement) or in the package's Processing card once it has finished.
function setStatusRows(rows) {
  const html = kvRowsHtml(rows);
  [els.statusList, els.processingList, els.packageProcessingList].forEach((list) => {
    if (list) list.innerHTML = html;
  });
}

function setInitialState() {
  if (els.monthlyCard) els.monthlyCard.style.display = "none";
  els.resultsContent?.classList.remove("is-withheld");
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

const CHIP_TONES = { green: "success", red: "error", blue: "info", amber: "warning", violet: "violet", neutral: "neutral" };

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

function toneClass(tone) {
  return tone && tone !== "neutral" ? ` tone-${escapeHtml(tone)}` : "";
}

// One figure as a row: its label and note on the left, the value on the right. A revenue figure is a button
// that filters the ledger to the transactions behind it.
function metricRowHtml([label, value, sub, , tone, action]) {
  const actionable = action && action.revenueFilter;
  const tag = actionable ? "button" : "div";
  const attributes = actionable
    ? ` type="button" data-revenue-filter="${escapeHtml(action.revenueFilter)}" aria-label="Show exact ${escapeHtml(label)} transactions"`
    : "";
  return `
    <${tag} class="metric-row"${attributes}>
      <span class="metric-text">
        <span class="metric-label">${escapeHtml(label)}</span>
        ${sub ? `<span class="metric-note">${escapeHtml(sub)}</span>` : ""}
      </span>
      <span class="metric-value${toneClass(tone)}">${escapeHtml(value)}</span>
    </${tag}>
  `;
}

function metricPanelHeadHtml(section) {
  return `
    <div class="panel-head">
      <h3>${escapeHtml(section.title)}</h3>
      <span class="panel-sub">${escapeHtml(section.sub || "")}</span>
    </div>
  `;
}

// Plain sections sit side by side; a "wide" section (lenders) spans the page in two columns and a "strip"
// section (package quality) reads across as one row of large figures.
function renderMetricSections(sections) {
  const plain = sections.filter((section) => !section.layout);
  const grid = plain.length
    ? `<div class="metric-groups" style="--cols: ${plain.length}">${plain.map((section) => `
        <section class="panel">
          ${metricPanelHeadHtml(section)}
          ${(section.items || []).map(metricRowHtml).join("")}
        </section>
      `).join("")}</div>`
    : "";
  const others = sections.filter((section) => section.layout).map((section) => {
    const items = section.items || [];
    if (section.layout === "strip") {
      return `
        <section class="panel quality-strip" style="--cols: ${items.length}">
          <div class="quality-head">
            <h3>${escapeHtml(section.title)}</h3>
            <span class="panel-sub">${escapeHtml(section.sub || "")}</span>
          </div>
          ${items.map(([label, value, sub, , tone]) => `
            <div class="quality-cell" title="${escapeHtml(sub || "")}">
              <span class="total-label">${escapeHtml(label)}</span>
              <span class="quality-value${toneClass(tone)}">${escapeHtml(value)}</span>
              <span class="metric-note">${escapeHtml(sub || "")}</span>
            </div>
          `).join("")}
        </section>
      `;
    }
    return `
      <section class="panel">
        ${metricPanelHeadHtml(section)}
        <div class="metric-wide-grid">${items.map(metricRowHtml).join("")}</div>
      </section>
    `;
  }).join("");
  els.metricsGrid.innerHTML = grid + others;
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
  // A package's lender rows say how many of its statements the lender appears in.
  const statements = numberOrNull(funder.documents);
  const statementsDetail = statements !== null
    ? `<div class="table-cell-detail">Across ${escapeHtml(formatNumber(statements))} ${statements === 1 ? "statement" : "statements"}</div>`
    : "";
  return `
    <tr>
      <td>${lenderEvidenceControl(funder, isPotential)}${statementsDetail}</td>
      <td>${escapeHtml(isPotential ? "Potential lender" : "Confirmed lender")}</td>
      <td>${escapeHtml(formatNumber(count))}</td>
      <td>${escapeHtml(formatMoney(total, currency))}</td>
      <td>${potentialWithholding}</td>
      <td>${glassChip(isPotential ? "?" : "LEN", isPotential ? "Review required" : "Confirmed", isPotential ? "amber" : "violet")}</td>
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

// A statement shows these rows in its Account & processing grid, a package in its Package summary card.
function renderAccountSummary(rows) {
  const html = kvRowsHtml(rows);
  [els.accountSummary, els.packageSummaryList].forEach((list) => {
    if (list) list.innerHTML = html;
  });
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
        <td class="num">${money(statement.beginning_balance)}</td>
        <td class="num">${money(statement.ending_balance)}</td>
        <td class="num">${money(metrics.effective_total_deposits)}</td>
        <td class="num">${money(metrics.effective_total_withdrawals)}</td>
        <td class="num">${money(metrics.average_daily_balance)}</td>
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
        <td class="num">${balance}</td>
        <td class="num">${balance}</td>
        <td class="num">${zero}</td>
        <td class="num">${zero}</td>
        <td class="num">${balance}</td>
      </tr>`;
  }
  return `
    <tr>
      <td><strong>${escapeHtml(name)}</strong>${isUnverifiedMain ? `<span class="main-badge">MAIN</span>` : ""}<span class="account-reason">${escapeHtml(kind)} · ${escapeHtml(accountReasonText(entry.reasons))}</span></td>
      <td>${glassChip("◐", "Needs review", "amber")}</td>
      <td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num">—</td>
    </tr>`;
}

// Where the All accounts switch lives, as a link that opens that page.
const ALL_ACCOUNTS_SETTING_LINK = `<button class="link-btn" type="button" data-nav="settings">All accounts in Settings</button>`;

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
      <p class="accounts-note">This statement holds <strong>${escapeHtml(formatNumber(entries.length))} accounts</strong>.
        ${lead}
        ${others > 0 ? `Turn on ${ALL_ACCOUNTS_SETTING_LINK} to review the other ${others === 1 ? "account" : `${escapeHtml(formatNumber(others))} accounts`}.` : ""}
      </p>`;
    els.accountsPanel.hidden = false;
    return;
  }
  els.accountsPanel.innerHTML = `
    <div class="panel-head">
      <h3>Accounts in this statement</h3>
      <span class="panel-sub">${escapeHtml(formatNumber(entries.length))} accounts · select one to analyze</span>
    </div>
    <div class="table-wrap">
      <table class="data-table accounts-table">
        <thead>
          <tr>
            <th>Account</th>
            <th>Status</th>
            <th class="num">Beginning</th>
            <th class="num">Ending</th>
            <th class="num">Deposits</th>
            <th class="num">Withdrawals</th>
            <th class="num">Avg daily balance</th>
          </tr>
        </thead>
        <tbody>${entries.map((entry) => accountPanelRowHtml(entry, published, idleMain ? -1 : main, selected, currency, entry === unverifiedMain || entry === idleMain)).join("")}</tbody>
      </table>
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
  // The statement's own period, bank and denomination, read off a verified account of the same statement.
  const first = (published[0] || {}).statement || {};
  const currency = first.currency || null;
  const why = entry.status === "idle"
    ? `it printed no activity this period (balance ${formatMoney(entry.balance, currency)})`
    : accountReasonText(entry.reasons);
  const verified = published.length;
  const explanation = `${name} is this statement's main account and could not be verified: ${why}. `
    + "No metrics are shown for it.";
  els.statusHeading.textContent = "Main account needs review";
  setBanner("pending", "Main account not verified; its metrics withheld", "Review required");
  setStatusMessage(explanation);
  els.decisionPill.textContent = "Review required";
  els.decisionPill.className = "decision-pill review_required";
  els.summaryBox.textContent = explanation;
  setStatusRows([
    ["OCR completed", "Yes"],
    ["Validation", "Review required"],
    ["Main account", "Not verified"],
    ["Metrics", "Withheld"],
  ]);
  // The results page keeps the statement's header, its accounts and the summary; every metric panel is withheld.
  setResultsMode("single");
  showResultsContent();
  els.resultsContent?.classList.add("is-withheld");
  const month = monthLabel(statementMonth(first.period_start, first.period_end));
  renderHero({
    icon: BANK_ICON,
    kicker: [first.bank || "Bank statement", `${formatNumber(roster.length)} accounts`].join(" · "),
    title: month ? `${month} statement` : "Bank statement",
    chips: [["Main account · Not verified"], [period(first), true], ...(currency ? [[currency]] : [])],
  });
  analysisCrumbs = ["Statements", first.bank || "Statement", month || period(first)];
  resultsCrumbs = analysisCrumbs;
  if (els.transactionCard) els.transactionCard.style.display = "none";
  if (allAccountsView()) {
    // Every account on the table, the main one marked and held; nothing selected until the user picks one.
    selectedAccountIndex = null;
    renderAccountsPanel(published, roster, -1, null, entry);
    return;
  }
  if (!els.accountsPanel) return;
  els.accountsPanel.innerHTML = `
    <p class="accounts-note">This statement holds <strong>${escapeHtml(formatNumber(roster.length))} accounts</strong>.
      The main account, <strong>${escapeHtml(name)}</strong>, could not be verified: ${escapeHtml(why)}.
      ${verified ? `${escapeHtml(formatNumber(verified))} other ${verified === 1 ? "account was" : "accounts were"} verified: turn on ${ALL_ACCOUNTS_SETTING_LINK} to review ${verified === 1 ? "it" : "them"}.` : ""}
    </p>`;
  els.accountsPanel.hidden = false;
}

function hideAccountsPanel() {
  if (!els.accountsPanel) return;
  els.accountsPanel.hidden = true;
  els.accountsPanel.innerHTML = "";
}

/* --- results page: header, credits, charts and totals ----------------
   Everything here lays out figures the API already published. The charts
   only scale and place them; no figure is derived from another. */
const BANK_ICON = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" aria-hidden="true"><path d="M3 10h18L12 4z"/><path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/></svg>`;
const PACKAGE_ICON = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/></svg>`;
const OPEN_ICON = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8"/></svg>`;

// The breadcrumb of the analysis that is open, and the one the results page shows now (an empty state
// replaces it while nothing of the kind asked for is open).
let analysisCrumbs = ["Statements"];
let resultsCrumbs = analysisCrumbs;

function sentenceCase(text) {
  const value = String(text || "");
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function signTone(value) {
  const n = numberOrNull(value);
  if (n === null || n === 0) return "neutral";
  return n > 0 ? "green" : "red";
}

function monthLabel(month) {
  return month ? `${MONTH_NAMES[month.month]} ${month.year}` : null;
}

function setResultsMode(mode) {
  els.resultsContent?.classList.toggle("is-package", mode === "package");
}

function showResultsContent() {
  if (els.resultsEmpty) els.resultsEmpty.hidden = true;
  if (els.resultsContent) els.resultsContent.hidden = false;
}

// A summary describes one analysis, so it closes when another one starts to open; while its analysis is
// redrawn (a review decision or a setting changed a figure) an open summary is written again.
function closeSummary() {
  if (els.summaryPanel) els.summaryPanel.hidden = true;
}

function refreshOpenSummary() {
  if (els.summaryPanel && !els.summaryPanel.hidden) generateSummary();
}

function renderHero({ icon, kicker, title, chips }) {
  els.heroKicker.innerHTML = `${icon}<span>${escapeHtml(kicker)}</span>`;
  els.resultsTitle.textContent = title;
  els.heroChips.innerHTML = chips
    .map(([text, mono]) => `<span class="hero-chip${mono ? " mono" : ""}">${escapeHtml(text)}</span>`)
    .join("");
}

function renderCredits({ label, value, meta }) {
  els.creditsLabel.textContent = label;
  els.creditsValue.textContent = value;
  // `meta` is built from escaped pieces by the two callers.
  els.creditsMeta.innerHTML = meta;
}

const CREDIT_MIX = [
  ["verified_revenue", "Verified revenue", "dot-green"],
  ["unverified_deposit", "Unverified deposits", "dot-amber"],
  ["non_revenue", "Non-revenue", "dot-muted"],
];

// The three revenue classes of the posted credits, each as its share of the three together. A row is a
// button to that class's transactions, like the Revenue evidence rows.
function renderCreditMix(source = {}, currency = "USD") {
  const parts = CREDIT_MIX.map(([state, label, dot]) => ({
    state,
    label,
    dot,
    count: source[`${state}_count`],
    total: source[`${state}_total`],
    size: Math.max(numberOrNull(source[`${state}_total`]) || 0, 0),
  }));
  const sum = parts.reduce((total, part) => total + part.size, 0);
  const share = (part) => (sum > 0 ? `${((part.size / sum) * 100).toFixed(1)}%` : "N/A");
  els.creditMixBar.innerHTML = parts
    .filter((part) => sum > 0 && part.size > 0)
    .map((part) => `<span class="${part.dot}" style="width: ${((part.size / sum) * 100).toFixed(2)}%"></span>`)
    .join("");
  els.creditMixBar.setAttribute(
    "aria-label",
    sum > 0 ? `Credit mix: ${parts.map((part) => `${share(part)} ${part.label.toLowerCase()}`).join(", ")}` : "Credit mix unavailable",
  );
  els.creditMixRows.innerHTML = parts.map((part) => `
    <button class="mix-row" type="button" data-revenue-filter="${part.state}" aria-label="Show exact ${escapeHtml(part.label)} transactions">
      <span class="mix-dot ${part.dot}"></span>
      <span class="mix-label">${escapeHtml(part.label)}</span>
      <span class="mix-count">${escapeHtml(formatNumber(part.count))}</span>
      <span class="mix-total">${escapeHtml(formatMoney(part.total, currency))}</span>
      <span class="mix-share">${escapeHtml(share(part))}</span>
    </button>
  `).join("");
}

function renderTotals(items) {
  els.totalsGrid.innerHTML = items.map(([label, value, tone]) => `
    <div class="total-item">
      <span class="total-label">${escapeHtml(label)}</span>
      <span class="total-value${toneClass(tone)}" title="${escapeHtml(value)}">${escapeHtml(value)}</span>
    </div>
  `).join("");
}

// The balance a statement prints after each posting day's last row -- the Running Balance column, one point
// per day. A statement that prints no running balance has no line to draw; nothing is reconstructed here.
function printedDailyBalances(transactions) {
  const printed = transactions.filter((tx) => txDateValue(tx) !== null && runningBalanceValue(tx) !== null);
  if (printed.length < 2) return [];
  // A ledger printed newest first lists each day's last posting first.
  const newestFirst = txDateValue(printed[0]) > txDateValue(printed[printed.length - 1]);
  const byDay = new Map();
  printed.forEach((tx) => {
    const day = txDateValue(tx);
    if (newestFirst && byDay.has(day)) return;
    byDay.set(day, runningBalanceValue(tx));
  });
  return [...byDay.entries()].map(([day, balance]) => ({ day, balance })).sort((a, b) => a.day - b.day);
}

// The smallest round multiple of a power of ten at or above `value`: a readable axis bound.
function niceCeiling(value) {
  if (!(value > 0)) return 0;
  const power = 10 ** Math.floor(Math.log10(value));
  const step = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find((multiple) => multiple * power >= value);
  return step * power;
}

function formatAxisMoney(value, currency) {
  try {
    return new Intl.NumberFormat("en-US", {
      notation: "compact",
      maximumFractionDigits: 1,
      ...(currency ? { style: "currency", currency } : {}),
    }).format(value);
  } catch {
    return String(Math.round(value));
  }
}

function chartDayLabel(day) {
  const date = new Date(day);
  return `${MONTH_NAMES[date.getUTCMonth()].slice(0, 3)} ${date.getUTCDate()}`;
}

function renderBalanceChart(transactions, metrics = {}, currency = "USD") {
  if (!els.balanceChart) return;
  const points = printedDailyBalances(transactions);
  const adb = numberOrNull(metrics.average_daily_balance);
  // Named for what it plots -- the printed running balance -- and carrying no count or extreme of its own:
  // the NSF count and the lowest and highest balances are the API's, shown in Risk signals.
  const head = (legend) => `
    <div class="chart-head">
      <span class="chart-title" title="The running balance the statement prints, at the last posting of each day">Running balance</span>
      <div class="chart-legend">${legend}</div>
    </div>
  `;
  if (points.length < 2) {
    els.balanceChart.innerHTML = `
      ${head(adb === null ? "" : `<span><span class="legend-dash"></span>ADB ${escapeHtml(formatMoney(metrics.average_daily_balance, currency))}</span>`)}
      <div class="chart-empty">This statement does not print a running balance on its transactions, so there is no daily line to draw.</div>
    `;
    return;
  }
  const balances = points.map((point) => point.balance);
  const high = Math.max(...balances, adb ?? -Infinity, 0);
  const low = Math.min(...balances, adb ?? Infinity, 0);
  const bottom = low < 0 ? -niceCeiling(-low) : 0;
  const top = high > 0 ? niceCeiling(high) : (bottom < 0 ? 0 : 1);
  const width = 1000;
  const height = 176;
  const first = points[0].day;
  const span = points[points.length - 1].day - first || 1;
  const x = (day) => ((day - first) / span) * width;
  const y = (value) => ((top - value) / (top - bottom)) * height;
  const line = points.map((point) => `${x(point.day).toFixed(1)},${y(point.balance).toFixed(1)}`).join(" ");
  const area = `M${x(first).toFixed(1)},${height} L${line.replace(/ /g, " L")} L${width},${height} Z`;
  const belowZero = points.filter((point) => point.balance < 0);
  const marker = (point) => `<span class="chart-point" style="left: ${(x(point.day) / 10).toFixed(2)}%; top: ${y(point.balance).toFixed(1)}px" title="Printed running balance on ${escapeHtml(chartDayLabel(point.day))}: ${escapeHtml(formatMoney(point.balance, currency))}"></span>`;
  const gridLine = (value, stroke) => `<line x1="0" x2="${width}" y1="${y(value).toFixed(1)}" y2="${y(value).toFixed(1)}" stroke="${stroke}" stroke-width="1" vector-effect="non-scaling-stroke"/>`;
  const ticks = [top, (top + bottom) / 2, bottom];
  const labels = [0, 1, 2, 3, 4].map((step) => chartDayLabel(first + (span * step) / 4));
  const legend = [
    `<span><span class="legend-line"></span>Balance</span>`,
    adb === null ? "" : `<span><span class="legend-dash"></span>ADB ${escapeHtml(formatMoney(metrics.average_daily_balance, currency))}</span>`,
    belowZero.length ? `<span><span class="legend-dot"></span>Below zero</span>` : "",
  ].join("");
  els.balanceChart.innerHTML = `
    ${head(legend)}
    <div class="chart-body">
      <div class="chart-axis" aria-hidden="true">${ticks.map((tick) => `<span>${escapeHtml(formatAxisMoney(tick, currency))}</span>`).join("")}</div>
      <div class="chart-plot" role="img" aria-label="Printed running balance from ${escapeHtml(chartDayLabel(first))} to ${escapeHtml(chartDayLabel(points[points.length - 1].day))}">
        <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
          ${gridLine(top, "var(--grid)")}
          ${gridLine((top + bottom) / 2, "var(--grid)")}
          ${gridLine(0, "var(--border-2)")}
          <path d="${area}" fill="var(--chart-fill)" stroke="none"/>
          <polyline points="${line}" fill="none" stroke="var(--accent)" stroke-width="1.8" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
          ${adb === null ? "" : `<line x1="0" x2="${width}" y1="${y(adb).toFixed(1)}" y2="${y(adb).toFixed(1)}" stroke="var(--text-3)" stroke-width="1" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/>`}
        </svg>
        ${belowZero.map(marker).join("")}
      </div>
    </div>
    <div class="chart-x" aria-hidden="true">${labels.map((label) => `<span>${escapeHtml(label)}</span>`).join("")}</div>
  `;
}

// A package member's own currency; a member that never declared one stays undeclared (CURRENCY DOCTRINE §F).
function currencyOfDocument(doc) {
  return "currency" in doc ? doc.currency : "USD";
}

// A package's statements in calendar order, each with the month it stands for.
function packageMonthRows(documents) {
  const rows = documents.map((doc) => ({ doc, month: statementMonth(doc.period_start, doc.period_end) }));
  rows.sort((a, b) => (a.month ? a.month.key : Infinity) - (b.month ? b.month.key : Infinity));
  return rows;
}

function packageTitle(rows) {
  const months = rows.map((row) => row.month).filter(Boolean);
  if (!months.length) return "Statement package";
  const first = months[0];
  const last = months[months.length - 1];
  if (first.key === last.key) return monthLabel(first);
  return first.year === last.year
    ? `${MONTH_NAMES[first.month]} – ${MONTH_NAMES[last.month]} ${last.year}`
    : `${monthLabel(first)} – ${monthLabel(last)}`;
}

function renderMonthlyChart(rows, mixedCurrencies) {
  if (!els.monthlyChart) return;
  const values = rows.map(({ doc }) => numberOrNull(doc.credits));
  const largest = Math.max(0, ...values.filter((value) => value !== null));
  const years = new Set(rows.map((row) => row.month && row.month.year));
  const columns = `grid-template-columns: repeat(${Math.max(rows.length, 1)}, minmax(0, 1fr))`;
  const tallest = 150;
  const bars = rows.map(({ doc }, index) => {
    const value = values[index];
    const currency = currencyOfDocument(doc);
    const unit = mixedCurrencies && currency && currency !== "USD" ? ` ${currency}` : "";
    const text = formatWhole(doc.credits);
    const heightPx = largest > 0 && value !== null ? Math.max((Math.max(value, 0) / largest) * tallest, 2) : 0;
    return `
      <div class="bar-col">
        <span class="bar-value">${escapeHtml(text === "N/A" ? text : text + unit)}</span>
        <div class="bar${value !== null && value === largest && largest > 0 ? " peak" : ""}" style="height: ${heightPx.toFixed(1)}px"></div>
      </div>
    `;
  }).join("");
  // Two statements for one month would read alike, so those bars also name their file (as the table does).
  const monthCounts = new Map();
  rows.forEach(({ month }) => { if (month) monthCounts.set(month.key, (monthCounts.get(month.key) || 0) + 1); });
  const labels = rows.map(({ doc, month }) => {
    const docCurrency = currencyOfDocument(doc);
    const shared = month && monthCounts.get(month.key) > 1;
    return `
      <div class="bar-label" title="${escapeHtml(doc.filename || "Statement")}">
        <strong>${escapeHtml(month ? (years.size > 1 ? monthLabel(month) : MONTH_NAMES[month.month]) : "N/A")}</strong>
        ${shared ? `<span class="bar-file">${escapeHtml(doc.filename || "Statement")}</span>` : ""}
        <span>Ledger ${escapeHtml(formatMoney(doc.average_daily_balance, docCurrency))}</span>
      </div>
    `;
  }).join("");
  els.monthlyChart.innerHTML = `
    <div class="chart-head">
      <span class="chart-title">Monthly deposits</span>
      <span class="chart-legend">Deposits and ledger (average daily balance) per statement</span>
    </div>
    <div class="bar-chart" style="${columns}" role="img" aria-label="Monthly deposits per statement">${bars}</div>
    <div class="bar-labels" style="${columns}">${labels}</div>
  `;
}

function setReviewCount(value) {
  if (!els.reviewCount) return;
  const count = numberOrNull(value) || 0;
  els.reviewCount.textContent = formatNumber(count);
  els.reviewCount.hidden = count <= 0;
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
    els.decisionPill.textContent = "Review required";
    els.decisionPill.className = "decision-pill review_required";
    // Above the shown account's own rows (its "Validation" is that account's), on both pages that list them.
    const note = statusRowHtml(["Main account", "No activity; needs review"]);
    [els.statusList, els.processingList].forEach((list) => list?.insertAdjacentHTML("afterbegin", note));
    els.heroChips?.insertAdjacentHTML("afterbegin", `<span class="hero-chip">Main account · No activity</span>`);
  }
}

function renderAccount(report) {
  currentAnalysis = report;
  els.resultsContent?.classList.remove("is-withheld");
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
  els.decisionPill.textContent = sentenceCase(labelize(decision));
  els.decisionPill.className = `decision-pill ${decision}`.trim();

  setResultsMode("single");
  showResultsContent();
  const account = Object.fromEntries(accountFieldRows(statement, currentMarkdown));
  const month = monthLabel(statementMonth(statement.period_start, statement.period_end));
  const pageCount = numberOrNull(statement.page_count || report.page_count);
  const accountName = [account["Account Type"], account["Account Number (masked)"]]
    .filter((value) => value && value !== "N/A")
    .join(" ");
  renderHero({
    icon: BANK_ICON,
    kicker: [statement.bank || "Bank statement", accountName].filter(Boolean).join(" · "),
    title: month ? `${month} statement` : "Bank statement",
    chips: [
      [`Revenue · ${metrics.revenue_reconciles ? "Balanced" : "Review required"}`],
      [`Integrity · ${integrityLabel(integrity)}`],
      [period(statement), true],
      [pageCount ? `${currency} · ${formatNumber(pageCount)} pages` : currency],
    ],
  });
  analysisCrumbs = ["Statements", statement.bank || "Statement", month || period(statement)];
  resultsCrumbs = analysisCrumbs;
  renderCredits({
    label: "Total credits",
    value: formatMoney(totalCredits, currency),
    meta: `${escapeHtml(formatNumber(metrics.total_posted_credit_count))} credit transactions · Revenue upper bound `
      + `<span class="mono">${escapeHtml(formatMoney(metrics.maximum_revenue, currency))}</span>`,
  });
  renderCreditMix(metrics, currency);
  renderBalanceChart(transactions, metrics, currency);
  renderTotals([
    ["Total debits", formatMoney(totalDebits, currency)],
    ["Cash flow", formatMoney(metrics.cash_flow, currency), signTone(metrics.cash_flow)],
    ["Average daily balance", formatMoney(metrics.average_daily_balance, currency), averageBalanceTone(metrics)],
    ["Ending balance", formatMoney(statement.ending_balance, currency), negativeTone(statement.ending_balance)],
    ["NSFs", formatNumber(metrics.effective_nsf_count), countTone(metrics.effective_nsf_count)],
    ["Confirmed withholding", formatPercent(metrics.withholding_rate), withholdingTone(metrics.withholding_rate)],
  ]);
  setReviewCount(metrics.unverified_deposit_count);

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
        ["Total Credits", formatMoney(totalCredits, currency), REVENUE_METRIC_COPY.totalCredits, "CR", "neutral"],
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
      title: "Risk signals",
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
      layout: "wide",
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
  refreshOpenSummary();
}

// A failure is reported on the New analysis page, beside the upload it belongs to.
function renderError(message) {
  setProgress(false);
  els.statusHeading.textContent = "Processing failed";
  setBanner("error", "Processing failed", "Failed");
  setStatusMessage(message);
  els.decisionPill.textContent = "Review required";
  els.decisionPill.className = "decision-pill error";
  renderAccountSummary(accountFieldRows());
  notify(`Processing failed: ${message}`, "red");
  navigate("new");
}

/* --- the upload queue and page preview ------------------------------ */
const PREVIEW_PLACEHOLDER = els.pagePreview ? els.pagePreview.innerHTML : "";
let previewPageCount = 0;

function queueState(entry) {
  if (entry.status === "error") return { chip: "Failed", tone: "red", detail: "Failed", bar: "error", width: 100 };
  if (entry.status === "interrupted") return { chip: "Interrupted", tone: "amber", detail: "Interrupted", bar: "error", width: 100 };
  if (entry.status === "done") return { chip: "Done", tone: "neutral", detail: "Complete", bar: "done", width: 100 };
  if (!entry.jobId) return { chip: "Uploading", tone: "green", detail: "Uploading", bar: "busy", width: 0 };
  if (entry.status === "queued") return { chip: "Queued", tone: "amber", detail: "Waiting", bar: "", width: 0 };
  return { chip: "Processing", tone: "green", detail: labelize(entry.stage || entry.status), bar: "busy", width: 0 };
}

function renderQueue() {
  if (!els.queueCard || !els.queueList) return;
  els.queueCard.hidden = !queueEntries.length;
  const pages = queueEntries.reduce((sum, entry) => sum + (numberOrNull(entry.pageCount) || 0), 0);
  els.queueMeta.textContent = `${formatNumber(queueEntries.length)} ${queueEntries.length === 1 ? "file" : "files"}`
    + (pages ? ` · ${formatNumber(pages)} pages` : "");
  els.queueList.innerHTML = queueEntries.map((entry, index) => {
    const state = queueState(entry);
    const details = [
      sentenceCase(state.detail),
      numberOrNull(entry.pageCount) ? `${formatNumber(entry.pageCount)} pages` : "",
      formatBytes(entry.size),
    ].filter(Boolean).join(" · ");
    const selected = entry.jobId && entry.jobId === previewJobId;
    return `
      <button class="queue-row${selected ? " selected" : ""}" type="button" data-queue-index="${index}" ${entry.jobId ? "" : "disabled"} aria-label="Preview ${escapeHtml(entry.name)}">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="color: var(--text-3)"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>
        <span style="min-width: 0">
          <span class="queue-name">${escapeHtml(entry.name)}</span>
          <span class="queue-detail">${escapeHtml(details)}</span>
        </span>
        <span class="queue-bar ${state.bar}"><span style="width: ${state.width}%"></span></span>
        ${glassChip("", state.chip, state.tone)}
      </button>
    `;
  }).join("");
}

// Folds a /status reply into the queue entry for that job.
function updateQueueEntry(jobId, status) {
  const entry = queueEntries.find((item) => item.jobId === jobId);
  if (!entry || !status) return;
  entry.status = status.status;
  entry.stage = status.stage;
  if (numberOrNull(status.page_count)) entry.pageCount = status.page_count;
  if (jobId === previewJobId && numberOrNull(status.page_count) && !previewPageCount) {
    previewPageCount = status.page_count;
    renderPreview();
  }
}

function setPreviewJob(jobId, pageCount) {
  previewJobId = jobId;
  previewPageCount = numberOrNull(pageCount) || 0;
  previewPage = 0;
  renderPreview();
  renderQueue();
}

// The page itself, rendered by the server from the uploaded PDF.
function renderPreview() {
  if (!els.pagePreview) return;
  const ready = previewJobId && previewPageCount > 0;
  els.previewPrev.disabled = !ready || previewPage <= 0;
  els.previewNext.disabled = !ready || previewPage >= previewPageCount - 1;
  if (!ready) {
    els.pagePreview.innerHTML = PREVIEW_PLACEHOLDER;
    els.previewLabel.textContent = "p. – / –";
    return;
  }
  const source = `/page/${encodeURIComponent(previewJobId)}/${previewPage}`;
  els.pagePreview.innerHTML = `
    <a href="${source}" target="_blank" rel="noopener" title="Open page ${previewPage + 1} full size">
      <img src="${source}" alt="Page ${previewPage + 1} of the uploaded statement">
    </a>
  `;
  els.previewLabel.textContent = `p. ${formatNumber(previewPage + 1)} / ${formatNumber(previewPageCount)}`;
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
  // The explanation goes where this page shows it (the status card), and into the summary box as before.
  if (contradiction) {
    const explanation = `${contradiction}. The statement's own printed figures contradict the transactions `
      + "it lists. Every listed transaction was read and checked against the PDF's own text, so this is a failure "
      + "of the statement, not of the reading. No metrics have been published.";
    els.statusHeading.textContent = contradiction;
    setBanner("error", "Statement does not add up; metrics withheld", "Failed");
    setStatusMessage(explanation);
    els.decisionPill.textContent = "Fail";
    els.decisionPill.className = "decision-pill failed";
    els.summaryBox.textContent = explanation;
    setStatusRows([
      ["OCR completed", "Yes"],
      ["Validation", "Failed: statement contradiction"],
      ["Metrics", "Withheld"],
    ]);
    return;
  }
  const explanation = `${friendlyAnalysisError(message)} Open Review extraction to inspect the reading and its `
    + "review status. No metrics have been published.";
  els.statusHeading.textContent = "Extraction needs review";
  setBanner("pending", "Extraction available; metrics withheld", "Review required");
  setStatusMessage(explanation);
  els.decisionPill.textContent = "Review required";
  els.decisionPill.className = "decision-pill review_required";
  els.summaryBox.textContent = explanation;
  setStatusRows([
    ["OCR completed", "Yes"],
    ["Validation", "Review required"],
    ["Metrics", "Withheld"],
  ]);
}

// A link placed after the status card's message, for a result that never reaches the results page.
function appendStatusLink(href, text) {
  if (!els.statusMessage) return;
  els.statusMessage.insertAdjacentHTML(
    "beforeend",
    ` <a href="${escapeHtml(href)}" target="_blank" rel="noopener">${escapeHtml(text)}</a>`,
  );
}

function showSelectedFile(file) {
  currentFile = file;
  queueEntries = currentFiles.map((item) => ({
    name: item.name,
    size: item.size,
    jobId: null,
    status: "uploading",
    stage: null,
    pageCount: null,
  }));
  setPreviewJob(null, 0);
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
  closeSummary();
  showSelectedFile(file);
  setActions(null, false);
  setProgress(true);
  els.statusHeading.textContent = "Uploading PDF";
  setBanner("pending", "Uploading PDF", "--");
  renderAccountSummary(accountFieldRows());
  renderMainTransactions();

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
      // One job per uploaded file, in upload order.
      payload.jobs.forEach((job, index) => {
        const entry = queueEntries[index];
        if (!entry) return;
        entry.jobId = job.id;
        entry.status = "queued";
        entry.pageCount = job.page_count;
      });
      setPreviewJob(payload.jobs[0].id, payload.jobs[0].page_count);
      const isPackage = currentJobIds.length > 1;
      els.statusHeading.textContent = isPackage ? "Processing package" : "Processing statement";
      setBanner("pending", isPackage ? "Package extraction started" : "Extraction started", "--");
      if (isPackage) pollPackage(currentJobIds);
      else pollJob(currentJobId);
    })
    .catch((error) => {
      queueEntries.forEach((entry) => { if (!entry.jobId) entry.status = "error"; });
      renderQueue();
      renderError(error.message || String(error));
    });
}

function pollPackage(jobIds) {
  if (pollTimer) clearTimeout(pollTimer);
  Promise.all(jobIds.map((jobId) => fetch(`/status/${jobId}`).then((response) => {
    if (!response.ok) throw new Error(`Status failed (${response.status})`);
    return response.json();
  })))
    .then((statuses) => {
      if (jobIds.join(",") !== currentJobIds.join(",")) return;
      statuses.forEach((status, index) => updateQueueEntry(jobIds[index], status));
      renderQueue();
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
      updateQueueEntry(jobId, status);
      renderQueue();
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

// The job ids and upload details of the analysis on screen, recorded whenever one finishes drawing. A reopen
// that fails goes back to these: a copy taken at the click would be another reopen's ids while that one is
// still in flight.
let shownAnalysis = null;

function recordShownAnalysis() {
  shownAnalysis = { jobId: currentJobId, jobIds: currentJobIds.slice(), files: currentFiles, file: currentFile, startedAt };
}

// `reveal` opens the results page once they are drawn; a settings refresh redraws them where they are.
// `announce` adds a notification (a fresh upload, not a reopen); `onError` replaces the failure page.
function loadResults(jobId, { reveal = true, announce = reveal, onError = renderError } = {}) {
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
        appendStatusLink(`/result/${encodeURIComponent(jobId)}`, "Review extraction");
        return;
      }
      renderAnalysis(payload.analysis);
      setActions(jobId, true);
      if (!currentAnalysis && !currentDocument) {
        // Nothing could be shown (renderAnalysis reported why): the exports sit under that message.
        appendStatusExports(`/download/${encodeURIComponent(jobId)}`);
        return;
      }
      recordShownAnalysis();
      // A statement whose main account was not verified has no account on screen (its metrics are withheld), so the
      // Recent entry names the statement, never one of its other accounts.
      rememberStatement(jobId, currentAnalysis || documentLabelReport(currentDocument));
      if (announce) notify(`${els.resultsTitle.textContent} analyzed`, "green");
      if (reveal) openResultsPage("results");
    })
    .catch((error) => onError(error.message || String(error)));
}

function appendStatusExports(base) {
  if (!els.statusMessage) return;
  els.statusMessage.insertAdjacentHTML(
    "beforeend",
    ` <a href="${base}/csv">Download CSV</a> · <a href="${base}/xlsx">Download XLSX</a>`,
  );
}

function packagePeriod(documents) {
  const starts = documents.map((doc) => doc.period_start).filter(Boolean).sort();
  const ends = documents.map((doc) => doc.period_end).filter(Boolean).sort();
  if (!starts.length && !ends.length) return "N/A";
  return `${starts[0] || "N/A"} to ${ends[ends.length - 1] || "N/A"}`;
}

function loadPackage(jobIds, { reveal = true, announce = reveal, onError = renderError } = {}) {
  fetch(`/package_analysis?ids=${encodeURIComponent(jobIds.join(","))}`)
    .then((response) => {
      if (!response.ok) throw new Error(`Package analysis unavailable (${response.status})`);
      return response.json();
    })
    .then((pkg) => {
      if (jobIds.join(",") !== currentJobIds.join(",")) return;
      renderPackageAnalysis(pkg);
      setPackageActions(jobIds);
      recordShownAnalysis();
      rememberPackage(jobIds, pkg);
      if (announce) notify(`Package ${els.resultsTitle.textContent} analyzed`, "green");
      if (reveal) openResultsPage("packages");
    })
    .catch((error) => onError(error.message || String(error)));
}

function renderPackageAnalysis(pkg) {
  // A package is several statements, never one statement's accounts: the account view and its selection go.
  currentDocument = null;
  selectedAccountIndex = null;
  hideAccountsPanel();
  els.resultsContent?.classList.remove("is-withheld");
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
  els.decisionPill.textContent = `Package decision · ${sentenceCase(labelize(totals.decision || "review required"))}`;
  els.decisionPill.className = `decision-pill ${totals.decision || ""}`.trim();

  setResultsMode("package");
  showResultsContent();
  const monthRows = packageMonthRows(documents);
  const title = packageTitle(monthRows);
  const banks = [...new Set(documents.map((doc) => doc.bank).filter(Boolean))];
  const periods = numberOrNull(totals.statement_periods ?? totals.months) ?? documents.length;
  renderHero({
    icon: PACKAGE_ICON,
    kicker: ["Package", `${formatNumber(documents.length)} ${documents.length === 1 ? "statement" : "statements"}`, banks.join(", ")]
      .filter(Boolean).join(" · "),
    title,
    chips: [
      [packagePeriod(documents), true],
      [packageCurrencyLabel(currencyInfo)],
      [`Revenue · ${totals.revenue_reconciles ? "Balanced" : "Review required"}`],
    ],
  });
  analysisCrumbs = ["Packages", title];
  resultsCrumbs = analysisCrumbs;
  renderCredits({
    label: `Total credits · ${formatNumber(periods)} ${periods === 1 ? "month" : "months"}`,
    value: formatMoney(totals.total_credits, currency),
    meta: refusalNote
      ? escapeHtml(refusalNote)
      : `Avg monthly credits <span class="mono">${escapeHtml(formatMoney(totals.avg_monthly_credits, currency))}</span>`
        + ` · Revenue upper bound <span class="mono">${escapeHtml(formatMoney(totals.maximum_revenue, currency))}</span>`,
  });
  renderCreditMix(totals, currency);
  renderMonthlyChart(monthRows, currencyInfo.currencies.length > 1);
  renderTotals([
    ["Total debits", formatMoney(totals.total_debits, currency)],
    ["Total cash flow", formatMoney(totals.cash_flow, currency), signTone(totals.cash_flow)],
    ["Avg monthly cash flow", formatMoney(totals.avg_monthly_cash_flow, currency), signTone(totals.avg_monthly_cash_flow)],
    ["Average daily balance", formatMoney(totals.average_daily_balance, currency)],
    ["NSFs", formatNumber(totals.nsf_count), countTone(totals.nsf_count)],
    ["Confirmed withholding", formatPercent(totals.package_withholding_rate), withholdingTone(totals.package_withholding_rate)],
  ]);
  setReviewCount(totals.unverified_deposit_count);
  if (els.packageProcessingNote) {
    const failed = numberOrNull(totals.failed) || 0;
    els.packageProcessingNote.textContent = failed
      ? `${formatNumber(failed)} ${failed === 1 ? "statement" : "statements"} failed`
      : "All statements complete";
  }

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
      title: "Package revenue",
      // MINOR-10 (the L1-S3 review): `months` counts MEMBERS and this label
      // says PERIODS. They are the same number until a document publishes two
      // accounts, and two accounts of one document are one statement period.
      // The server publishes `statement_periods` only when the two differ, so
      // this reads the honest count where there is one and the old one where
      // nothing changed.
      sub: `${formatNumber(totals.statement_periods ?? totals.months)} statement periods`,
      items: [
        ["Total Credits", formatMoney(totals.total_credits, currency), moneyNote(REVENUE_METRIC_COPY.totalCredits), "CR", "neutral"],
        ["Verified Revenue", formatMoney(totals.verified_revenue_total, currency), moneyNote(REVENUE_METRIC_COPY.verifiedRevenue), "REV", "green", { revenueFilter: "verified_revenue" }],
        ["Unverified Deposits", formatMoney(totals.unverified_deposit_total, currency), moneyNote(REVENUE_METRIC_COPY.unverifiedDeposits), "?", "amber", { revenueFilter: "unverified_deposit" }],
        ["Non-Revenue", formatMoney(totals.non_revenue_total, currency), moneyNote(REVENUE_METRIC_COPY.nonRevenue), "X", "neutral", { revenueFilter: "non_revenue" }],
        ["Revenue Upper Bound", formatMoney(totals.maximum_revenue, currency), moneyNote(REVENUE_METRIC_COPY.revenueUpperBound), "MAX", "neutral"],
        ["Avg Monthly Credits", formatMoney(totals.avg_monthly_credits, currency), moneyNote("Average posted credits per statement period"), "AVG", "neutral"],
      ],
    },
    {
      title: "Cash flow",
      sub: "Package-level affordability signals",
      items: [
        ["Total Debits", formatMoney(totals.total_debits, currency), moneyNote("All posted debit transactions"), "DB", "neutral"],
        ["Avg Monthly Debits", formatMoney(totals.avg_monthly_debits, currency), moneyNote("Average posted debits per statement period"), "AVG", "neutral"],
        ["Total Cash Flow", formatMoney(totals.cash_flow, currency), moneyNote("Credits minus debits"), "CF", negativeTone(totals.cash_flow)],
        ["Avg Monthly Cash Flow", formatMoney(totals.avg_monthly_cash_flow, currency), moneyNote("Average statement cash flow"), "AVG", negativeTone(totals.avg_monthly_cash_flow)],
        ["Average Daily Balance", formatMoney(totals.average_daily_balance, currency), moneyNote(packageAverageBalanceNote(documents)), "ADB", currencyInfo.refused ? "amber" : packageAverageBalanceTone(documents)],
        ["NSFs", formatNumber(totals.nsf_count), totals.nsf_source === "mixed" ? "Members counted on different bases" : nsfSourceLabel(totals.nsf_source), "NSF", countTone(totals.nsf_count)],
        ["Confirmed Withholding", formatPercent(totals.package_withholding_rate), moneyNote(withholdingAuditNote(totals, currency)), "%", withholdingTone(totals.package_withholding_rate)],
      ],
    },
    {
      title: "Quality",
      layout: "strip",
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
      layout: "wide",
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
  refreshOpenSummary();
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
    const rows = packageMonthRows(documents);
    // Each row is denominated by its OWN statement (CURRENCY DOCTRINE §F). The column names say ($) as the
    // CRM does; when the package mixes currencies (the server's list, which counts only statements that
    // contribute money), a non-USD row names its unit so no figure passes for USD. An undeclared currency
    // stays undeclared.
    const mixedCurrencies = packageCurrencyInfo(pkg).currencies.length > 1;
    // Two statements for one month (two accounts, or checking and savings) would be indistinguishable rows,
    // so those rows alone name their file under the month.
    const monthCounts = new Map();
    rows.forEach(({ month }) => { if (month) monthCounts.set(month.key, (monthCounts.get(month.key) || 0) + 1); });
    // Members counted on different NSF bases (one saved before the printed-day basis existed) would show counts that
    // cannot be compared, so each NSF cell then names its basis; the tooltip always does.
    const mixedNsf = new Set(rows.map(({ doc }) => doc.nsf_source).filter(Boolean)).size > 1;
    els.monthlyTable.innerHTML = rows.map(({ doc, month }) => {
      const status = doc.status !== "done" ? "Failed" : labelize(doc.corporate_use || doc.quality || "review");
      const docCurrency = currencyOfDocument(doc);
      const unit = mixedCurrencies && docCurrency && docCurrency !== "USD" ? ` ${docCurrency}` : "";
      const amount = (value) => {
        const text = formatWhole(value);
        return text === "N/A" ? text : text + unit;
      };
      const shared = month && monthCounts.get(month.key) > 1;
      return `
        <tr title="${escapeHtml(doc.filename || "Statement")}">
          <td>${escapeHtml(month ? MONTH_NAMES[month.month] : "N/A")}${shared ? `<div class="table-cell-detail">${escapeHtml(doc.filename || "Statement")}</div>` : ""}</td>
          <td>${escapeHtml(month ? String(month.year) : "N/A")}</td>
          <td>${escapeHtml(amount(doc.credits))}</td>
          <td>${escapeHtml(formatWhole(doc.deposit_count))}</td>
          <td>${escapeHtml(amount(doc.average_daily_balance))}</td>
          <td title="${escapeHtml(nsfSourceLabel(doc.nsf_source))}">${escapeHtml(formatNumber(doc.nsf_count))}${mixedNsf ? `<div class="table-cell-detail">${escapeHtml(nsfSourceLabel(doc.nsf_source))}</div>` : ""}</td>
          <td><button class="statement-open" type="button" data-job-id="${escapeHtml(doc.id)}" ${doc.status === "done" ? "" : "disabled"}>${status === "Failed" ? "Unavailable" : `Open${OPEN_ICON}`}</button></td>
        </tr>
      `;
    }).join("");
  }
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
    ["Status", labelize(decision), "Corporate-use and lender-review status", decision === "approved" ? "OK" : "REVIEW", decision === "approved" ? "green" : "amber"],
  ].map(renderMetricCard).join("");
  els.statementModalAccount.innerHTML = kvRowsHtml(accountFieldRows(statement, markdown));

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
    const lenderSummary = funders.length
      ? funders.map((funder) => `${funder.funder}: ${formatMoney(funder.total_debited, currency)} across ${formatNumber(funder.documents)} statement(s)`).join("\n")
      : "No lenders detected across the package.";
    els.summaryBox.textContent =
      `Package ${packagePeriod(pkg.documents || [])}: ${formatNumber(totals.completed)} of ${formatNumber(totals.documents)} statements completed, ` +
      `${formatMoney(totals.avg_monthly_credits, currency)} average monthly credits, ${formatMoney(totals.avg_monthly_cash_flow, currency)} average monthly cash flow, ` +
      `${formatNumber(totals.nsf_count)} NSF events, ${formatPercent(totals.package_withholding_rate)} confirmed withholding, ` +
      `${formatMoney(potentialLenderDebitTotal(totals), currency)} potential lender debits and ${formatPercent(totals.potential_withholding_exposure)} potential exposure. ` +
      `${formatNumber(funders.length)} confirmed lender detections. Decision: ${labelize(totals.decision || "review required")}.` +
      `\n\nPackage lender summary:\n${lenderSummary}`;
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

/* --- views and navigation --------------------------------------------
   Three pages share the shell: New analysis, the results of whatever is
   open (a statement or a package) and Settings. The sidebar entries
   Statements, Packages and Revenue review all land on the results page. */
let activeNav = "new";

function setBreadcrumb(parts) {
  els.breadcrumb.innerHTML = parts.map((part, index) => {
    const separator = index ? `<span class="crumb-sep" aria-hidden="true">/</span>` : "";
    const current = index === parts.length - 1 ? ` class="crumb-current" aria-current="page"` : "";
    return `${separator}<span${current}>${escapeHtml(part)}</span>`;
  }).join("");
}

function syncNav() {
  document.querySelectorAll(".rail-btn[data-nav], .side-link[data-nav]").forEach((item) => {
    const active = item.getAttribute("data-nav") === activeNav;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  const openKey = currentJobIds.join(",");
  document.querySelectorAll("[data-recent-key]").forEach((item) => {
    item.classList.toggle("active", currentView === "results" && item.getAttribute("data-recent-key") === openKey);
  });
}

function showView(view) {
  currentView = view;
  els.newView.hidden = view !== "new";
  els.resultsView.hidden = view !== "results";
  els.settingsView.hidden = view !== "settings";
  // The top bar carries the upload hint on New analysis and the appearance, notifications and New analysis
  // controls over results; Settings has its own appearance choice.
  els.topbarHint.hidden = view !== "new";
  [els.appearanceToggle, els.notificationsAnchor, els.topbarNew].forEach((item) => {
    if (item) item.hidden = view !== "results";
  });
  setBreadcrumb(
    view === "new" ? ["Statements", "New analysis"]
      : view === "settings" ? ["Workspace", "Settings"]
        : resultsCrumbs,
  );
  syncNav();
  closePopovers();
  closePanelOverlay();
  if (view === "settings") loadSettings();
}

function openResultsPage(nav) {
  activeNav = nav;
  showView("results");
  window.scrollTo(0, 0);
}

// Back to the analysis already open, after an empty state may have replaced it on the results page.
function revealOpenAnalysis(nav) {
  els.resultsEmpty.hidden = true;
  els.resultsContent.hidden = false;
  resultsCrumbs = analysisCrumbs;
  openResultsPage(nav);
}

function showResultsEmpty(kind) {
  const copy = {
    results: ["No statement open", "Upload a statement, or several at once to build a package, and its analysis opens here."],
    packages: ["No package open", "Upload two or more statements at once to build a package."],
    review: ["Nothing to review", "Open a statement or package to review its unverified deposits."],
  }[kind];
  els.resultsEmptyTitle.textContent = copy[0];
  els.resultsEmptyCopy.textContent = copy[1];
  els.resultsEmpty.hidden = false;
  els.resultsContent.hidden = true;
  resultsCrumbs = [kind === "packages" ? "Packages" : "Statements"];
  openResultsPage(kind);
}

function navigate(target) {
  if (target === "new" || target === "settings") {
    activeNav = target;
    showView(target);
    window.scrollTo(0, 0);
    return;
  }
  const openPackage = Boolean(currentAnalysis && currentAnalysis.package);
  const openStatement = Boolean(currentAnalysis && !currentAnalysis.package);
  if (target === "review") {
    if (!currentAnalysis) {
      showResultsEmpty("review");
      return;
    }
    revealOpenAnalysis("review");
    showMainRevenueEvidence("unverified_deposit");
    return;
  }
  const wantPackage = target === "packages";
  if ((wantPackage && openPackage) || (!wantPackage && openStatement)) {
    revealOpenAnalysis(target);
    return;
  }
  const latest = recentAnalyses.find((item) => item.kind === (wantPackage ? "package" : "statement"));
  if (latest) openRecent(latest.key);
  else showResultsEmpty(target);
}

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target.closest("[data-nav]") : null;
  if (target) navigate(target.getAttribute("data-nav"));
});

/* --- recent analyses ---------------------------------------------------
   What this tab has analyzed, newest first, so the sidebar can reopen it.
   Held for the browser tab only (sessionStorage), and only the job ids and
   the labels the sidebar prints. */
const RECENT_KEY = "ocr-recent-analyses";
const RECENT_LIMIT = 12;

function loadRecentAnalyses() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(RECENT_KEY) || "[]");
    return Array.isArray(saved)
      ? saved.filter((item) => item && Array.isArray(item.ids) && item.ids.length && typeof item.key === "string")
      : [];
  } catch {
    return [];
  }
}

let recentAnalyses = loadRecentAnalyses();

function rememberAnalysis(entry) {
  recentAnalyses = [entry, ...recentAnalyses.filter((item) => item.key !== entry.key)].slice(0, RECENT_LIMIT);
  try { sessionStorage.setItem(RECENT_KEY, JSON.stringify(recentAnalyses)); } catch { /* storage unavailable */ }
  renderRecentAnalyses();
}

function decisionDotTone(decision) {
  if (decision === "approved") return "green";
  if (decision === "error" || decision === "failed") return "red";
  return "amber";
}

function rememberStatement(jobId, report) {
  const statement = report.statement || {};
  const account = Object.fromEntries(accountFieldRows(statement, currentMarkdown));
  const month = monthLabel(statementMonth(statement.period_start, statement.period_end));
  const accountType = account["Account Type"] !== "N/A" ? account["Account Type"] : "";
  const digits = String(account["Account Number (masked)"] || "").replace(/[^0-9]/g, "");
  rememberAnalysis({
    kind: "statement",
    key: jobId,
    ids: [jobId],
    label: [month || statement.bank || "Statement", accountType || (month ? statement.bank : "")].filter(Boolean).join(" · "),
    meta: digits.slice(-4),
    tone: decisionDotTone(els.decisionPill.classList[1]),
  });
}

// The statement a multi-account document came from, by its period and bank only: no account's type or number.
function documentLabelReport(doc) {
  const first = (publishedAccounts(doc)[0] || {}).statement || {};
  return { statement: { bank: first.bank, period_start: first.period_start, period_end: first.period_end } };
}

function rememberPackage(jobIds, pkg) {
  const documents = Array.isArray(pkg.documents) ? pkg.documents : [];
  rememberAnalysis({
    kind: "package",
    key: jobIds.join(","),
    ids: jobIds.slice(),
    label: packageTitle(packageMonthRows(documents)),
    meta: String(documents.length),
    tone: decisionDotTone((pkg.totals || {}).decision),
  });
}

function recentItemHtml(item) {
  const mark = item.kind === "package"
    ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/></svg>`
    : `<span class="recent-dot tone-${escapeHtml(item.tone)}" aria-hidden="true"></span>`;
  return `
    <button class="side-link recent-item" type="button" data-recent-key="${escapeHtml(item.key)}" title="${escapeHtml(item.label)}">
      ${mark}
      <span class="side-link-label">${escapeHtml(item.label)}</span>
      <span class="side-count">${escapeHtml(item.meta || "")}</span>
    </button>
  `;
}

function renderRecentAnalyses() {
  const query = (els.sidebarSearch?.value || "").trim().toLowerCase();
  const matches = (item) => !query || `${item.label} ${item.meta}`.toLowerCase().includes(query);
  const statements = recentAnalyses.filter((item) => item.kind === "statement");
  const packages = recentAnalyses.filter((item) => item.kind === "package");
  els.statementCount.textContent = formatNumber(statements.length);
  els.packageCount.textContent = formatNumber(packages.length);
  const listHtml = (items, empty) => {
    const shown = items.filter(matches);
    if (shown.length) return shown.map(recentItemHtml).join("");
    return `<div class="side-empty">${escapeHtml(query ? "No matches" : empty)}</div>`;
  };
  els.recentStatements.innerHTML = listHtml(statements, "None yet");
  els.recentPackages.innerHTML = listHtml(packages, "None yet");
  syncNav();
}

function openRecent(key) {
  const item = recentAnalyses.find((entry) => entry.key === key);
  if (!item) return;
  if (els.progressTrack.classList.contains("show")) {
    // An upload is still running and opens its own results when it finishes; switching the open analysis
    // now would drop it, so the analyst is shown its progress instead.
    navigate("new");
    return;
  }
  if (pollTimer) clearTimeout(pollTimer);
  currentJobIds = item.ids.slice();
  currentJobId = currentJobIds[0];
  currentFiles = [];
  currentFile = null;
  startedAt = null;
  transactionFilter = "all";
  transactionEntityFilter = null;
  setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
  closeSummary();
  // A reopen that fails (the job is gone, the server is unreachable) must not leave the page pointing at
  // it: the analysis still on screen gets its own ids back, and the failure is reported beside it.
  const onError = (message) => {
    if (currentJobIds.join(",") !== item.ids.join(",")) return;  // something newer was opened meanwhile
    if (!currentAnalysis || !shownAnalysis) {
      renderError(message);
      return;
    }
    ({ jobId: currentJobId, files: currentFiles, file: currentFile, startedAt } = shownAnalysis);
    currentJobIds = shownAnalysis.jobIds.slice();
    // The filter was reset for the reopen; the ledger on screen is redrawn to match its buttons.
    renderMainTransactions();
    notify(`Could not reopen ${item.label}: ${message}`, "red");
    revealOpenAnalysis(currentAnalysis.package ? "packages" : "results");
    togglePopover(els.notificationsPopover, els.notificationsBtn);
  };
  if (item.kind === "package") loadPackage(currentJobIds, { announce: false, onError });
  else loadResults(currentJobId, { announce: false, onError });
}

[els.recentStatements, els.recentPackages].forEach((list) => {
  list?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target.closest("[data-recent-key]") : null;
    if (target) openRecent(target.getAttribute("data-recent-key"));
  });
});
els.sidebarSearch?.addEventListener("input", renderRecentAnalyses);

/* The sidebar panel. On a wide screen it sits beside the page and can be collapsed to the rail (remembered);
   below 1120px it does not fit, so the logo or Search opens it over the page until something is chosen. */
const PANEL_KEY = "ocr-sidebar-panel";
const NARROW_SCREEN = window.matchMedia("(max-width: 1120px)");

function setPanelCollapsed(collapsed) {
  document.documentElement.classList.toggle("panel-collapsed", collapsed);
  try { localStorage.setItem(PANEL_KEY, collapsed ? "collapsed" : "open"); } catch { /* storage unavailable */ }
}

function panelVisible() {
  const root = document.documentElement;
  return NARROW_SCREEN.matches ? root.classList.contains("panel-open") : !root.classList.contains("panel-collapsed");
}

function syncPanelToggle() {
  els.panelToggle?.setAttribute("aria-expanded", panelVisible() ? "true" : "false");
}

function setPanelVisible(visible) {
  if (NARROW_SCREEN.matches) document.documentElement.classList.toggle("panel-open", visible);
  else setPanelCollapsed(!visible);
  syncPanelToggle();
}

function closePanelOverlay() {
  document.documentElement.classList.remove("panel-open");
  syncPanelToggle();
}

function focusSearch() {
  setPanelVisible(true);
  els.sidebarSearch?.focus();
}

els.panelToggle?.addEventListener("click", () => setPanelVisible(!panelVisible()));
els.collapseSidebar?.addEventListener("click", () => setPanelVisible(false));
els.railSearch?.addEventListener("click", focusSearch);
document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (!document.documentElement.classList.contains("panel-open") || (target && target.closest(".sidebar"))) return;
  closePanelOverlay();
});
NARROW_SCREEN.addEventListener?.("change", syncPanelToggle);
document.addEventListener("keydown", (event) => {
  if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
  const target = event.target instanceof Element ? event.target : null;
  if (target && target.closest("input, textarea, select, [contenteditable='true']")) return;
  if (els.statementModalBackdrop?.classList.contains("show")) return;
  event.preventDefault();
  focusSearch();
});

/* --- notifications and help ------------------------------------------ */
let notifications = [];

function notify(text, tone) {
  notifications = [{ text, tone, at: new Date() }, ...notifications].slice(0, 20);
  els.notificationsList.innerHTML = notifications.map((item) => `
    <div class="popover-item">
      <span class="recent-dot tone-${escapeHtml(item.tone)}" aria-hidden="true"></span>
      <span>${escapeHtml(item.text)}</span>
      <span class="popover-item-time">${escapeHtml(item.at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</span>
    </div>
  `).join("");
  if (els.notificationsPopover.hidden) els.notifyDot.hidden = false;
}

function closePopovers() {
  [[els.notificationsPopover, els.notificationsBtn], [els.helpPopover, els.helpBtn]].forEach(([popover, button]) => {
    if (!popover || popover.hidden) return;
    popover.hidden = true;
    button?.setAttribute("aria-expanded", "false");
  });
}

function togglePopover(popover, button) {
  const opening = popover.hidden;
  closePopovers();
  if (!opening) return;
  popover.hidden = false;
  button.setAttribute("aria-expanded", "true");
  if (popover === els.notificationsPopover) els.notifyDot.hidden = true;
}

els.notificationsBtn?.addEventListener("click", () => togglePopover(els.notificationsPopover, els.notificationsBtn));
els.helpBtn?.addEventListener("click", () => togglePopover(els.helpPopover, els.helpBtn));
document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target && target.closest(".popover-anchor")) return;
  closePopovers();
});

/* --- settings ---------------------------------------------------------- */
// The worked example under the NSF switch: the 10th ends at -$10, nothing posts on the 11th, the 12th ends
// at $20. Printed days count one negative day; carrying the balance over counts two.
function renderNsfExample(carryOver) {
  const days = [
    ["10th", "Activity", "-$10.00", true],
    ["11th", "No activity", carryOver ? "-$10.00" : "—", carryOver],
    ["12th", "Activity", "$20.00", false],
  ];
  els.nsfExampleDays.innerHTML = days.map(([day, activity, balance, counted]) => `
    <div class="example-day${counted ? " counted" : ""}">
      <div class="example-day-top"><span>${day}</span><span>${activity}</span></div>
      <span class="example-day-balance">${balance}</span>
      <span class="example-day-count">${counted ? "Counts as negative" : "Not counted"}</span>
    </div>
  `).join("");
  els.nsfExampleTotal.textContent = carryOver ? "2" : "1";
}

function setSettingsStatus(message, error = false) {
  els.settingsStatus.textContent = message;
  if (error) els.settingsStatus.setAttribute("data-state", "error");
  else els.settingsStatus.removeAttribute("data-state");
}

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
      renderNsfExample(els.nsfCarryOverToggle.checked);
      setSettingsStatus("");
    })
    .catch((error) => {
      setSettingsStatus(error.message || String(error), true);
    });
}

function refreshShownResults() {
  // A setting changes how a result is presented, so whatever is open is fetched again, in place. A statement whose
  // main account was not verified shows no account (currentAnalysis is null) but keeps its accounts
  // (currentDocument), and selecting one later renders from that copy, so it is fetched again too.
  if (currentJobIds.length > 1) loadPackage(currentJobIds, { reveal: false });
  else if (currentJobId && (currentAnalysis || currentDocument)) loadResults(currentJobId, { reveal: false });
}

els.nsfCarryOverToggle.addEventListener("change", () => {
  const wanted = els.nsfCarryOverToggle.checked;
  els.nsfCarryOverToggle.disabled = true;
  renderNsfExample(wanted);
  setSettingsStatus("Saving...");
  fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nsf_carry_over: wanted }),
  })
    .then((response) => response.json().then((payload) => ({ response, payload })))
    .then(({ response, payload }) => {
      if (!response.ok || !payload.settings) throw new Error(payload.error || `Save failed (${response.status})`);
      els.nsfCarryOverToggle.checked = payload.settings.nsf_carry_over === true;
      renderNsfExample(els.nsfCarryOverToggle.checked);
      setSettingsStatus(payload.settings.nsf_carry_over
        ? "Saved. NSF counts now carry the balance over inactive days."
        : "Saved. NSF counts now use printed days only.");
      refreshShownResults();
    })
    .catch((error) => {
      els.nsfCarryOverToggle.checked = !wanted;
      renderNsfExample(!wanted);
      setSettingsStatus(error.message || String(error), true);
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
els.summaryBtn.addEventListener("click", () => {
  generateSummary();
  if (!currentAnalysis || !els.summaryPanel) return;
  els.summaryPanel.hidden = false;
  els.summaryPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
});
els.copySummaryBtn?.addEventListener("click", () => copyText(els.summaryBox.textContent));
els.closeSummaryBtn?.addEventListener("click", closeSummary);
els.queueList?.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target.closest("[data-queue-index]") : null;
  const entry = target ? queueEntries[Number(target.getAttribute("data-queue-index"))] : null;
  if (entry && entry.jobId) setPreviewJob(entry.jobId, entry.pageCount);
});
els.previewPrev?.addEventListener("click", () => {
  if (previewPage <= 0) return;
  previewPage -= 1;
  renderPreview();
});
els.previewNext?.addEventListener("click", () => {
  if (previewPage >= previewPageCount - 1) return;
  previewPage += 1;
  renderPreview();
});
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
els.creditMixRows?.addEventListener("click", (event) => {
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
      const pkg = await packageResponse.json();
      renderPackageAnalysis(pkg);
      setPackageActions(currentJobIds);
      rememberPackage(currentJobIds, pkg);
    } else if (currentJobId === jobId) {
      renderAnalysis(payload.analysis);
      setActions(jobId, true);
      if (currentAnalysis) rememberStatement(jobId, currentAnalysis);
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

/* --- All accounts ---------------------------------------------------------
   A preference kept in this browser only, switched on the Settings page. It
   changes what the results page shows of a statement that holds several
   accounts, never what was read. */
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
// Arrow keys move between the choices of each appearance control (the top bar's and the Settings cards),
// matching a native radio group: only the chosen one is in the tab order.
document.querySelectorAll("#appearanceToggle, .theme-cards").forEach((group) => {
  group.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const next = event.key === "ArrowLeft" ? "dark" : "light";
    setAppearance(next);
    group.querySelector(`[data-appearance="${next}"]`)?.focus();
  });
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
  if (event.key !== "Escape") return;
  if (els.statementModalBackdrop?.classList.contains("show")) {
    closeStatementModal();
    return;
  }
  closePopovers();
  closePanelOverlay();
});

setInitialState();
renderNsfExample(false);
renderRecentAnalyses();
renderPreview();
showView("new");
syncPanelToggle();
setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
setTransactionFilterButtons("[data-transaction-sort]", transactionSort);
setTransactionFilterButtons("[data-modal-transaction-filter]", modalTransactionFilter);
setTransactionFilterButtons("[data-modal-transaction-sort]", modalTransactionSort);
setActions(null, false);
