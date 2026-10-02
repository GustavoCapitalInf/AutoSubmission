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
  flagSettingsList: document.getElementById("flagSettingsList"),
  flagSettingsStatus: document.getElementById("flagSettingsStatus"),
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
  flaggedTable: document.getElementById("flaggedTable"),
  flaggedCount: document.getElementById("flaggedCount"),
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
  monthlyHead: document.getElementById("monthlyHead"),
  monthlyDepositsView: document.getElementById("monthlyDepositsView"),
  bulkReviewBar: document.getElementById("bulkReviewBar"),
  bulkReviewCount: document.getElementById("bulkReviewCount"),
  bulkReviewStatus: document.getElementById("bulkReviewStatus"),
  bulkSelectAll: document.getElementById("bulkSelectAll"),
  transactionsTitle: document.getElementById("transactionsTitle"),
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
  statementModalFlagged: document.getElementById("statementModalFlagged"),
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
  rulesOutdatedNotice: document.getElementById("rulesOutdatedNotice"),
  duplicateNotice: document.getElementById("duplicateNotice"),
  duplicateNoticeText: document.getElementById("duplicateNoticeText"),
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
// The statement window's account: the one of the package row it was opened from (1-based; null opens the main
// account), and the one it shows, which its rows' reviews name (null for a statement of one account).
let modalAccount = null;
let modalReviewAccount = null;
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

// 5.6 (true revenue spec §10.5): the note under each revenue figure. Audit B11 (I53): the Counted note names every kind
// of counted credit (cash, checks and person-to-person were 55% of counted dollars; wires, unlabelled and numbered
// payers, factoring and platform payouts the rest) and says what is missing is proof of the sale, the payer being
// printed on most; the Verified note claims confirmed platform payouts only (an unconfirmed one is counted).
const REVENUE_METRIC_COPY = Object.freeze({
  totalCredits: "All posted credit transactions",
  trueRevenue: "Posted credits minus known non-revenue and the deposits held for review",
  verifiedRevenue: "Revenue with proof: card settlements, confirmed platform payouts, repeat or institutional payers, invoices, and deposits you confirmed",
  countedFlagged: "Counted in true revenue without proof of the sale: cash, checks, person-to-person, wires, one-off, unlabelled and numbered-company payers, factoring and platform payouts",
  heldForReview: "Kept out of true revenue until you confirm it",
  nonRevenue: "Own-account transfers, funding, refunds and other known non-revenue",
  // Audit B11 (I51): where revenue is not established, Non-Revenue is a figure of the captured rows only.
  nonRevenueCaptured: "Captured rows only: own-account transfers, funding, refunds and other known non-revenue",
  achCredits: "Posted ACH credit transactions",
});

// Audit B11 (I34, copy only; the basis is the owner's): the legacy withholding denominator is gross deposits less
// lender funding, never True revenue.
const LEGACY_ELIGIBLE_DEPOSITS_NOTE = "Gross deposits less lender funding (not True revenue)";

// 5.6 (true revenue spec §5.3, §10.6): the reason codes of the two middle tiers, code -> [tier, label, sentence]. It
// mirrors analysis/revenue.py REVENUE_TIER_REASONS (code -> tier and label); tests/test_webapp_true_revenue_ui.py
// holds the two equal. The sentence is the ledger's one line on the code.
const REVENUE_TIER_REASONS = Object.freeze({
  direction_conflict: ["excluded_pending_review", "Direction conflicts with the amount", "The bank prints this row in the other direction from its amount."],
  insurer_payer: ["excluded_pending_review", "Insurance carrier", "An insurance carrier paid it: a claim or a refund unless you confirm it pays for a sale."],
  insurer_named_payer: ["excluded_pending_review", "Payer name reads as an insurer", "The payer's name reads as an insurer."],
  possible_return: ["excluded_pending_review", "Possible return or adjustment", "The row reads as a return, a reversal or an adjustment of an earlier item."],
  financing_named_payer: ["excluded_pending_review", "Payer or entry suggests financing", "The payer or the entry names funding, a loan or an advance."],
  payer_debited_as_lender: ["excluded_pending_review", "Payer is also debited as a lender", "This payer is also debited from the account as a lender."],
  holder_name: ["excluded_pending_review", "From the holder's own name or brand", "The credit comes from the account holder's own name or brand."],
  payroll_or_salary: ["excluded_pending_review", "Payroll, salary or employee reimbursement", "The entry reads as payroll, salary or an employee reimbursement."],
  personal_income: ["excluded_pending_review", "Benefit or pension", "The entry reads as a benefit or a pension."],
  non_sale_purpose: ["excluded_pending_review", "Not a sale: owner money, investment, grant, refund, claim or interest", "The entry names owner money, an investment, a grant, a refund, a claim or interest."],
  payer_also_debited: ["excluded_pending_review", "Payer also debited this account", "The same payer is also debited from this account."],
  wire_no_sender: ["excluded_pending_review", "Wire, no sender printed", "A wire with no sender printed."],
  transfer_no_counterparty: ["excluded_pending_review", "Transfer, no counterparty", "A transfer that names no counterparty."],
  transfer_account_designation: ["excluded_pending_review", "Transfer naming an account", "A transfer that names an account, not a payer."],
  p2p_round_repeat: ["excluded_pending_review", "Repeated round sums from one sender", "Round sums repeated by one person-to-person sender."],
  wire_named_sender: ["counted_flagged", "Wire from a named sender", "A wire from a named sender, counted without proof of the sale."],
  check_deposit: ["counted_flagged", "Check deposit", "A check deposit: the payer is not printed."],
  no_payer_printed: ["counted_flagged", "No payer printed", "A cash, branch, ATM or bare deposit: no payer is printed."],
  payer_text_not_read: ["counted_flagged", "Payer text not read", "The statement prints a payer for this row that the reader could not read: counted without proof of the sale."],
  p2p: ["counted_flagged", "Person-to-person", "A person-to-person payment."],
  factoring_payout: ["counted_flagged", "Factoring payout", "A factor's payout of the business's own invoices."],
  payout_credit_entity: ["counted_flagged", "BNPL or marketplace settlement (payer also lends)", "A buy-now-pay-later or marketplace settlement of the business's own sales, counted; the payer also lends."],
  platform_unconfirmed: ["counted_flagged", "Platform payout, not confirmed", "A registered platform's payout without the context that confirms it."],
  numbered_company_payer: ["counted_flagged", "Numbered company payer", "A numbered company paid it: counted, never verified."],
  named_payer_purpose_refused: ["counted_flagged", "Named payer, purpose not accepted as proof", "A named payer whose printed purpose is not accepted as proof."],
  named_payer_one_off: ["counted_flagged", "One-off payer", "A named payer seen once on this statement."],
  named_payer_unlabelled: ["counted_flagged", "Payer named, channel not printed", "A named payer on a channel the bank does not print."],
});

function revenueReasonLabel(record) {
  const entry = REVENUE_TIER_REASONS[record && record.revenue_tier_reason];
  return entry ? entry[1] : "Reason not recorded";
}

// The revenue cards of true revenue spec §10.1, in order: True Revenue (the headline), Verified Revenue with its share
// of True, Counted, Held and Non-Revenue, each a button to its rows. `source` is a statement's metrics or a package's
// totals. A True, Counted or Held figure reads N/A unless `established`, a Verified one unless `verifiedEstablished`
// (§10.4). `note` wraps each note (a package's currency refusal replaces them); `unestablishedNote` replaces the True
// note where revenue is not established; `counts` prints "count / total", as the statement window does.
function revenueCardItems(source, currency, {
  established, verifiedEstablished, note = (text) => text, unestablishedNote = "", counts = false, facts = [],
}) {
  const figure = (kind, shown) => {
    if (!shown) return "N/A";
    const total = formatMoney(source[`${kind}_total`], currency);
    return counts ? `${formatNumber(source[`${kind}_count`])} / ${total}` : total;
  };
  const trueTotal = numberOrNull(source.true_revenue_total);
  const verifiedTotal = numberOrNull(source.verified_revenue_total);
  const share = established && verifiedEstablished && trueTotal !== null && trueTotal > 0 && verifiedTotal !== null
    ? `${((verifiedTotal / trueTotal) * 100).toFixed(1)}% of true revenue · ` : "";
  // Audit B11 (B9's I13, B10's I05): the statement integrity facts True rests on follow its note.
  const trueNote = [!established && unestablishedNote ? unestablishedNote : REVENUE_METRIC_COPY.trueRevenue,
    ...facts].join(" · ");
  // Audit B11 (I51): Non-Revenue stays a figure where revenue is not established, and says it covers the captured rows.
  const nonRevenueNote = established ? REVENUE_METRIC_COPY.nonRevenue : REVENUE_METRIC_COPY.nonRevenueCaptured;
  return [
    ["True Revenue", figure("true_revenue", established), note(trueNote), "REV", "green", { revenueFilter: "true_revenue", headline: true }],
    ["Verified Revenue", figure("verified_revenue", verifiedEstablished), note(share + REVENUE_METRIC_COPY.verifiedRevenue), "VER", "green", { revenueFilter: "verified_revenue" }],
    ["Counted, Not Verified", figure("counted_flagged", established), note(REVENUE_METRIC_COPY.countedFlagged), "CNT", "teal", { revenueFilter: "counted_flagged" }],
    ["Held for Review", figure("excluded_pending_review", established), note(REVENUE_METRIC_COPY.heldForReview), "?", "amber", { revenueFilter: "excluded_pending_review" }],
    ["Non-Revenue", figure("non_revenue", true), note(nonRevenueNote), "X", "neutral", { revenueFilter: "non_revenue" }],
  ];
}

// Audit B11 (I07): the revenue sentence of a copied summary (the credit-memo artefact): True revenue (the headline, Q1),
// Verified beside it and Non-revenue, each in total and per calendar month (`monthly`: {trueMonthly, verifiedMonthly,
// nonRevenueMonthly}); N/A where not established (§10.4), and Non-revenue named as captured rows only there.
function revenueSummarySentence(source = {}, currency = "USD", { established, verifiedEstablished } = {}, monthly = {}) {
  const pair = (total, perMonth, shown) => (shown
    ? `${formatMoney(total, currency)} (${formatMoney(perMonth, currency)} a month)` : "N/A");
  const nonRevenue = `${formatMoney(source.non_revenue_total, currency)} `
    + `(${formatMoney(monthly.nonRevenueMonthly, currency)} a month${established ? "" : ", captured rows only"})`;
  return `True revenue ${pair(source.true_revenue_total, monthly.trueMonthly, established === true)}, `
    + `verified revenue ${pair(source.verified_revenue_total, monthly.verifiedMonthly, verifiedEstablished === true)}, `
    + `non-revenue ${nonRevenue}.`;
}

// Audit B11 (I31): whether a statement's revenue reads "Balanced": its own rows reconcile to the bank's printed figures
// (`reconciliation.ok`) and its revenue is established. The four tiers summing to the posted credits
// (`revenue_tiers_sum_to_posted`, formerly read here as `revenue_reconciles`) holds on every tiered statement, so it
// said "Balanced" beside a shortfall or an unreconciled ledger.
function statementRevenueBalanced(report = {}) {
  const reconciliation = report.reconciliation || {};
  const metrics = report.metrics || {};
  return reconciliation.ok === true && metrics.revenue_established === true;
}

// The same for a package: every counted member reconciles (`unreconciled_documents` empty), the package's revenue is
// established, and its currencies are not refused (a refused package's judgement never reads as a pass).
function packageRevenueBalanced(pkg = {}) {
  const totals = pkg.totals || {};
  const unreconciled = Array.isArray(totals.unreconciled_documents) ? totals.unreconciled_documents : null;
  return unreconciled !== null && unreconciled.length === 0 && packageRevenueFlags(totals).revenue_established
    && !packageCurrencyInfo(pkg).refused;
}

// Audit B11 (B9's I13, B10's I05): what the True card says True rests on, from a statement's metrics: no holder's name
// read (the holds that keep the holder's own money out cannot see it), and the share of credits whose printed payer
// no parser read.
function statementRevenueFacts(metrics = {}) {
  const facts = [];
  if (metrics.holder_unscreened === true) facts.push("No holder name read: the holder's own deposits are not screened");
  if (metrics.payer_text_unread === true) {
    const count = numberOrNull(metrics.payer_text_unread_count);
    facts.push(`${count === null ? "Many" : formatNumber(count)} credits' payer text not read`);
  }
  return facts;
}

// The same facts for a package, from its totals' member lists.
function packageRevenueFacts(totals = {}) {
  const statements = (list) => new Set((Array.isArray(list) ? list : []).map((id) => String(id).split("#")[0])).size;
  const noun = (n) => (n === 1 ? "statement" : "statements");
  const facts = [];
  const unscreened = statements(totals.holder_unscreened_documents);
  if (unscreened) facts.push(`${formatNumber(unscreened)} ${noun(unscreened)} with no holder name read`);
  const unread = statements(totals.payer_text_unread_documents);
  if (unread) facts.push(`${formatNumber(unread)} ${noun(unread)} with payer text not read`);
  return facts;
}

// A package's two revenue flags (§10.4). The server nulls its True, Counted and Held counts only when a completed
// member is not established; a currency refusal (CURRENCY DOCTRINE §F) nulls their money and keeps the counts, so the
// True count says whether they are established, and the refused money still reads N/A (a null total formats so). The
// Verified total is nulled either way: under a refusal it is established when no member is listed as not established.
function packageRevenueFlags(totals = {}) {
  const present = (value) => value !== null && value !== undefined;
  const established = present(totals.true_revenue_count);
  const unestablished = Array.isArray(totals.revenue_unestablished_documents) ? totals.revenue_unestablished_documents : null;
  const verifiedEstablished = present(totals.verified_revenue_total)
    || (totals.cross_currency_totals_refused === true && unestablished !== null && unestablished.length === 0);
  return {
    ...totals,
    established,
    verifiedEstablished,
    revenue_established: established,
    verified_revenue_established: verifiedEstablished,
  };
}

// The note under a package's revenue totals: how many completed statements have no established revenue, and, for
// those analysed with older rules (their `documents` row's analysis_rules_outdated, §12), what to do about it. A
// statement whose revenue is not established for another reason (a summary-only one) is offered no remedy:
// re-analysis would not establish it. "" when every member is established.
function packageUnestablishedNote(totals = {}, documents = []) {
  const listed = Array.isArray(totals.revenue_unestablished_documents) ? totals.revenue_unestablished_documents : [];
  const statementOf = (id) => String(id).split("#")[0];
  const unestablished = new Set(listed.map(statementOf));
  const statements = unestablished.size;
  if (!statements) return "";
  const outdated = new Set((Array.isArray(documents) ? documents : [])
    .filter((doc) => doc && doc.analysis_rules_outdated === true && unestablished.has(statementOf(doc.id)))
    .map((doc) => statementOf(doc.id))).size;
  const completed = numberOrNull(totals.completed) ?? statements;
  const noun = completed === 1 ? "statement" : "statements";
  const remedy = !outdated ? ""
    : outdated === statements ? " · Re-analyze to compute true revenue"
      : ` · Re-analyze ${formatNumber(outdated)} of them to compute true revenue`;
  return `${formatNumber(statements)} of ${formatNumber(completed)} ${noun} ${statements === 1 ? "has" : "have"} no established revenue`
    + remedy;
}

// 5.6 (true revenue spec §10.7): what the review badge shows. It counts the held credits (`revenue_review_items`)
// where the held figure is established, and reads N/A where it is not: a statement whose revenue is not established,
// or a package whose Held count the server left N/A (a member not established), never a partial count. An analysis
// saved before 5.6 carries no held count (its served copy nulls it), and keeps counting its deposits left unverified.
function reviewBadgeValue(source = {}, established = false) {
  if (numberOrNull(source.revenue_review_items) === null) return source.unverified_deposit_count;
  return established ? source.revenue_review_items : "N/A";
}

const emptyMetricSections = [
  {
    title: "Credits",
    sub: "Posted credit transactions",
    items: [
      ["True Revenue", "N/A", REVENUE_METRIC_COPY.trueRevenue, "REV", "green", { headline: true }],
      ["Verified Revenue", "N/A", REVENUE_METRIC_COPY.verifiedRevenue, "VER", "green"],
      ["Counted, Not Verified", "N/A", REVENUE_METRIC_COPY.countedFlagged, "CNT", "teal"],
      ["Held for Review", "N/A", REVENUE_METRIC_COPY.heldForReview, "?", "amber"],
      ["Non-Revenue", "N/A", REVENUE_METRIC_COPY.nonRevenue, "X", "neutral"],
      ["Total Credits", "N/A", REVENUE_METRIC_COPY.totalCredits, "CR", "neutral"],
      ["ACH Credits", "N/A", REVENUE_METRIC_COPY.achCredits, "ACH", "neutral"],
    ],
  },
  {
    title: "Debits",
    sub: "Posted debit transactions",
    items: [
      ["Total Debits", "N/A", "All posted debit transactions", "DB", "neutral"],
      ["Confirmed Withholding", "N/A", "Confirmed lender debits as a share of eligible deposits", "%", "neutral"],
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
      ["Eligible Deposits", "N/A", LEGACY_ELIGIBLE_DEPOSITS_NOTE, "DEP", "neutral"],
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
  // A result saved before R18 (2026-09-18) with no daily ledger to re-count keeps its own figure, which counted
  // returned items; the label says so rather than pass it off as negative-ending days.
  classified_line_items: "Returned items (saved before the negative-day count)",
};

function nsfSourceLabel(source) {
  return NSF_SOURCE_LABELS[source] || (source ? labelize(source) : "Negative-ending days");
}

// Whether a label table defines `key` itself: never an inherited name such as "constructor" or "toString".
function ownKey(table, key) {
  return Object.prototype.hasOwnProperty.call(table, String(key ?? ""));
}

// The groups of obligations flagged outside lender math, in the analysis's order (analysis/flag_groups.py
// FLAG_GROUPS; tests/test_webapp_flagged_dashboard.py keeps the two alike). A group's settings key is flag_<group>.
// Premium financing is the one group with no classification state: its rows stay insurance and carry flagged_group.
const FLAG_GROUP_LABELS = Object.freeze({
  alternative_positions: "Alternative positions",
  lines_of_credit: "Lines of credit",
  credit_cards: "Credit cards",
  vehicle_financing: "Vehicle loans & leases",
  bank_loans: "Bank loans",
  mortgages: "Mortgages",
  leases_rentals: "Leases & rentals",
  personal_loans: "Personal loans",
  floor_plan: "Floor plan",
  factoring: "Factoring",
  premium_financing: "Premium financing",
  debt_relief: "Debt relief",
});

function flagGroupLabel(group) {
  return ownKey(FLAG_GROUP_LABELS, group) ? FLAG_GROUP_LABELS[group] : labelize(group);
}

// How often a flagged payee was paid, as the analysis describes it (analysis/cadence.py describe_cadence).
const CADENCE_LABELS = Object.freeze({
  daily: "Daily",
  weekly: "Weekly",
  biweekly: "Every two weeks",
  monthly: "Monthly",
  irregular: "Irregular",
  single: "Single payment",
});

function cadenceLabel(cadence) {
  return ownKey(CADENCE_LABELS, cadence) ? CADENCE_LABELS[cadence] : labelize(cadence);
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

// The Eligible Deposits card's note: the basis the withholding rates divide by. Audit B11 (I34): the default, legacy
// basis is named for what it is, gross deposits less lender funding and never True revenue; a selected Verified or True
// basis keeps the analysis's own definition.
function activeDenominatorNote(metrics = {}) {
  const mode = metrics.withholding_denominator_mode;
  if (!mode || mode === "legacy_eligible_deposits") return LEGACY_ELIGIBLE_DEPOSITS_NOTE;
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

// 5.6 (true revenue spec §10.6): a credit's tag is its tier, a middle tier naming its reason. An analysis saved before
// 5.6 carries no tier, so its credits keep their revenue state's tag.
const REVENUE_TIER_TAGS = Object.freeze({
  verified: () => ({ label: "Verified revenue", glyph: "VER", tone: "green" }),
  counted_flagged: (record) => ({ label: `Counted: ${revenueReasonLabel(record)}`, glyph: "CNT", tone: "teal" }),
  excluded_pending_review: (record) => ({ label: `Held: ${revenueReasonLabel(record)}`, glyph: "?", tone: "amber" }),
  non_revenue: () => ({ label: "Non-revenue", glyph: "X", tone: "neutral" }),
});

function transactionCategory(tx) {
  const record = transactionClassification(tx);
  const revenueState = record.revenue_classification;
  if (txAmount(tx) > 0 && REVENUE_TIER_TAGS[record.revenue_tier]) {
    return REVENUE_TIER_TAGS[record.revenue_tier](record);
  }
  if (txAmount(tx) > 0 && revenueState === "verified_revenue") {
    return { label: "Verified revenue", glyph: "VER", tone: "green" };
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
    confirmed_lender: { label: entity || "Confirmed lender", glyph: "LEN", tone: "violet" },
    potential_lender: { label: entity ? `${entity} (Potential)` : "Potential lender", glyph: "?", tone: "violet" },
    insurance: { label: entity || "Insurance", glyph: "INS", tone: "blue" },
    // Retired 2026-09-24 (lender detection): analyses saved before then still carry it.
    lease_or_equipment_financing: { label: "Lease / Equipment", glyph: "LSE", tone: "neutral" },
    alternative_position: { label: entity ? `${entity} (Alternative position)` : "Alternative position", glyph: "ALT", tone: "neutral" },
    line_of_credit: { label: entity ? `${entity} (Line of credit)` : "Line of credit", glyph: "LOC", tone: "neutral" },
    vehicle_financing: { label: entity ? `${entity} (Vehicle loan / lease)` : "Vehicle loan / lease", glyph: "VEH", tone: "neutral" },
    bank_loan: { label: entity ? `${entity} (Bank loan)` : "Bank loan", glyph: "BNK", tone: "neutral" },
    mortgage: { label: entity ? `${entity} (Mortgage)` : "Mortgage", glyph: "MTG", tone: "neutral" },
    lease_or_rental: { label: entity ? `${entity} (Lease / rental)` : "Lease / rental", glyph: "LSE", tone: "neutral" },
    personal_loan: { label: entity ? `${entity} (Personal loan)` : "Personal loan", glyph: "PLN", tone: "neutral" },
    floor_plan_financing: { label: entity ? `${entity} (Floor plan)` : "Floor plan", glyph: "FLR", tone: "neutral" },
    factoring: { label: entity ? `${entity} (Factoring)` : "Factoring", glyph: "FCT", tone: "neutral" },
    debt_relief: { label: entity ? `${entity} (Debt relief)` : "Debt relief", glyph: "DRP", tone: "neutral" },
    fee: { label: "Fee", glyph: "$", tone: "neutral" },
    transfer: { label: "Transfer", glyph: "TR", tone: "neutral" },
    credit_card_payment: { label: entity ? `${entity} (Credit card)` : "Credit Card Payment", glyph: "CC", tone: "neutral" },
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

// A row of a flagged group ticked in Settings: the server marks it (flag_shown) when it serves the analysis.
function flaggedChip(tx) {
  return transactionClassification(tx).flag_shown === true ? glassChip("FLG", "Flagged", "blue", "flag-chip") : "";
}

// 5.5 (true revenue spec §7.10, T15): a property-management platform's verified payout says so beside its tag.
function revenueSourceChip(tx) {
  const record = transactionClassification(tx);
  const signals = Array.isArray(record.revenue_context_signals) ? record.revenue_context_signals : [];
  return record.revenue_classification === "verified_revenue" && signals.includes("property_management_collections")
    ? glassChip("PM", "Property-management collections", "blue", "flag-chip") : "";
}

// 5.6 (true revenue spec §10.6): the revenue filters, value -> test of a row's classification record. A row analysed
// before 5.6 carries no tier (and its served copy no contributes_to_true_revenue), so only Verified and Non-Revenue
// find it.
const REVENUE_FILTERS = Object.freeze({
  true_revenue: (record) => record.contributes_to_true_revenue === true,
  verified_revenue: (record) => record.revenue_classification === "verified_revenue",
  counted_flagged: (record) => record.revenue_tier === "counted_flagged",
  excluded_pending_review: (record) => record.revenue_tier === "excluded_pending_review",
  non_revenue: (record) => record.revenue_classification === "non_revenue",
});

// The ledger filter behind one reason of the Held for Review view is "excluded_pending_review:<reason>". Null for any
// other filter.
function heldReasonFilter(filter) {
  const match = /^excluded_pending_review:([a-z_0-9]+)$/.exec(String(filter || ""));
  return match ? match[1] : null;
}

// Audit B11 (I53): the ledger filter behind one reason of the counted tier is "counted_flagged:<reason>". Null for any
// other filter.
function countedReasonFilter(filter) {
  const match = /^counted_flagged:([a-z_0-9]+)$/.exec(String(filter || ""));
  return match ? match[1] : null;
}

// T10, §10.7: an analysis saved before 5.6 carries no tier and is reviewed under the rules it was analysed with, so its
// review view lists the deposits it left unverified, the rows its badge counts. This filter has no pill.
const OLDER_REVIEW_FILTER = "unverified_deposit";

// Whether a ledger was analysed before 5.6: a credit carries a revenue state and none carries a tier.
function ledgerCarriesNoTier(transactions) {
  const credits = (Array.isArray(transactions) ? transactions : [])
    .filter((tx) => txAmount(tx) > 0 && typeof transactionClassification(tx).revenue_classification === "string");
  return credits.length > 0 && credits.every((tx) => typeof transactionClassification(tx).revenue_tier !== "string");
}

// 5.6 (true revenue spec §10.6): the ledger header names a revenue filter in the page's words, the credit mix's tier
// labels (CREDIT_MIX) and the held reasons' labels (REVENUE_TIER_REASONS), never the filter's value. Null for any
// other filter.
function revenueFilterLabel(filter, count) {
  const lower = (text) => text.charAt(0).toLowerCase() + text.slice(1);
  if (filter === "true_revenue") return "in true revenue";
  if (filter === OLDER_REVIEW_FILTER) return count === 1 ? "unverified deposit" : "unverified deposits";
  const heldReason = heldReasonFilter(filter);
  if (heldReason) return `held: ${lower(revenueReasonLabel({ revenue_tier_reason: heldReason }))}`;
  const countedReason = countedReasonFilter(filter);
  if (countedReason) return `counted: ${lower(revenueReasonLabel({ revenue_tier_reason: countedReason }))}`;
  const tier = CREDIT_MIX.find(([state]) => state === filter);
  return tier ? lower(tier[1]) : null;
}

// The ledger filter behind one row of the Flagged positions panel is "flagged:<group>": that group's rows that count,
// of the payee clicked. Null for any other filter.
function flaggedFilterGroup(filter) {
  const match = /^flagged:([a-z_]+)$/.exec(String(filter || ""));
  return match ? match[1] : null;
}

// Who a flagged row paid, as the panel names it: the payee the classifier named, else the row's group.
function flaggedPayeeOf(tx) {
  const record = transactionClassification(tx);
  return record.canonical_entity || (record.flagged_group ? flagGroupLabel(record.flagged_group) : null);
}

/* --- the NSFs and NSF fees chips -------------------------------------------------------------------------------
   R18 (2026-09-18): the underwriting NSF count is the number of days that END with a negative balance, on the basis
   Settings chooses (analysis/nsf_days.py). Owner request, 2026-09-27 ("Two chips"): the NSFs chip lists exactly those
   days, each shown by the posting that ended it (the server's metrics.nsf_days), so its header always counts the NSF
   tile's days; a row that ended several days is shown once. The bank's NSF fee and returned-item rows
   (nsf_or_return, evidence only since R18) are the NSF fees chip. */
const NSF_UNAVAILABLE = "negative_ending_days_unavailable";
const NSF_DAY_BASES = new Set(["negative_printed_days", "negative_ending_days"]);

// A row's location within its own account (`transaction:N`): its classification's, else its position in the
// account's ledger when that is known (the name the server gives it).
function rowSourceLocation(tx, position = null) {
  const location = transactionClassification(tx).source_location;
  if (typeof location === "string" && location.trim()) return location;
  return Number.isInteger(position) ? `transaction:${position + 1}` : null;
}

function nsfDayLocations(days) {
  return new Set((Array.isArray(days) ? days : [])
    .map((day) => (day && typeof day.source_location === "string" ? day.source_location : null))
    .filter(Boolean));
}

// One account's NSF days, from its served metrics: the tile's count, and the rows that ended them.
function statementNsfDays(metrics) {
  const m = metrics || {};
  const count = numberOrNull(m.effective_nsf_count);
  const days = Array.isArray(m.nsf_days) ? m.nsf_days : null;
  const locations = nsfDayLocations(days);
  return {
    count,
    source: m.nsf_source,
    unavailable: m.nsf_source === NSF_UNAVAILABLE || count === null,
    listed: days !== null && days.length === count,
    unavailableMembers: 0,
    has: (tx, position) => locations.has(rowSourceLocation(tx, position)),
  };
}

// A package's NSF days: each member account's own days (its row of `documents`), matched to the combined ledger's
// rows by the statement and account a row came from, since a location is numbered within its account. The count is
// the package tile's.
function packageNsfDays(pkg) {
  const totals = pkg?.totals || {};
  const documents = Array.isArray(pkg?.documents) ? pkg.documents : [];
  const keys = new Set();
  let listedDays = 0;
  documents.forEach((doc) => {
    const { jobId, account } = packageMember(doc.id);
    const days = Array.isArray(doc.nsf_days) ? doc.nsf_days : [];
    listedDays += days.length;
    nsfDayLocations(days).forEach((location) => keys.add(JSON.stringify([jobId, account, location])));
  });
  const count = numberOrNull(totals.nsf_count);
  return {
    count,
    source: totals.nsf_source,
    unavailable: totals.nsf_source === NSF_UNAVAILABLE || count === null,
    listed: listedDays === count,
    unavailableMembers: documents.filter((doc) => doc.nsf_source === NSF_UNAVAILABLE).length,
    has: (tx) => keys.has(JSON.stringify([String(tx.source_job ?? ""), tx.source_account ?? null,
      rowSourceLocation(tx)])),
  };
}

// The NSFs chip's header: the days, as the tile counts them, never the rows shown.
function nsfDaysLabel(nsfDays) {
  if (!nsfDays) return "NSF days not available";
  if (nsfDays.unavailable) return "NSF days not computable: no validated daily ledger";
  const count = nsfDays.count;
  if (nsfDays.source && !NSF_DAY_BASES.has(nsfDays.source) && nsfDays.source !== "mixed") {
    // Saved before R18 with no daily ledger to re-count: the tile's figure is not a count of days.
    return `${formatNumber(count)} NSFs: ${nsfSourceLabel(nsfDays.source)}`;
  }
  let label = `${formatNumber(count)} ${count === 1 ? "day" : "days"} ending negative`;
  if (nsfDays.unavailableMembers) {
    const k = nsfDays.unavailableMembers;
    label += `; ${formatNumber(k)} ${k === 1 ? "statement" : "statements"} not computable: no validated daily ledger`;
  }
  if (!nsfDays.listed) label += " (not listed: the daily ledger does not show them)";
  return label;
}

function nsfDaysEmptyNote(nsfDays) {
  if (!nsfDays || nsfDays.unavailable) return "No validated daily ledger, so no day can be counted.";
  if (nsfDays.count === 0) return "No day ended with a negative balance.";
  return "The days counted could not be matched to rows.";
}

function filterTransactions(transactions, filter, canonicalEntity = null, nsfDays = null) {
  let matched = transactions;
  const flagGroup = flaggedFilterGroup(filter);
  if (filter === "nsf") matched = nsfDays ? transactions.filter((tx, position) => nsfDays.has(tx, position)) : [];
  if (filter === "nsf_fees") {
    matched = transactions.filter((tx) => transactionClassification(tx).classification === "nsf_or_return");
  }
  if (filter === "lender") matched = transactions.filter((tx) => transactionClassification(tx).contributes_to_withholding_rate === true);
  if (filter === "potential") matched = transactions.filter(contributesToPotentialTotals);
  if (filter === "insurance") matched = transactions.filter((tx) => transactionClassification(tx).contributes_to_insurance_totals === true);
  if (filter === "pos") matched = transactions.filter((tx) => transactionClassification(tx).classification === "pos");
  if (filter === "flagged") matched = transactions.filter((tx) => transactionClassification(tx).flag_shown === true);
  if (flagGroup) {
    matched = transactions.filter((tx) => {
      const record = transactionClassification(tx);
      return record.flag_shown === true && record.flagged_group === flagGroup
        && record.contributes_to_flagged_totals === true;
    });
  }
  if (REVENUE_FILTERS[filter]) {
    matched = transactions.filter((tx) => txAmount(tx) > 0 && REVENUE_FILTERS[filter](transactionClassification(tx)));
  }
  const heldReason = heldReasonFilter(filter);
  if (heldReason) {
    matched = transactions.filter((tx) => {
      const record = transactionClassification(tx);
      return record.revenue_tier === "excluded_pending_review" && record.revenue_tier_reason === heldReason;
    });
  }
  const countedReason = countedReasonFilter(filter);
  if (countedReason) {
    matched = transactions.filter((tx) => {
      const record = transactionClassification(tx);
      return txAmount(tx) > 0 && record.revenue_tier === "counted_flagged" && record.revenue_tier_reason === countedReason;
    });
  }
  if (filter === OLDER_REVIEW_FILTER) {
    matched = transactions.filter((tx) => txAmount(tx) > 0
      && transactionClassification(tx).revenue_classification === "unverified_deposit");
  }
  if (!canonicalEntity) return matched;
  if (flagGroup) return matched.filter((tx) => flaggedPayeeOf(tx) === canonicalEntity);
  // 5.3: an unnamed potential payee is listed under its own label (potential_payee_label), one per payee key.
  return matched.filter((tx) => {
    const record = transactionClassification(tx);
    return (record.potential_payee_label || record.canonical_entity) === canonicalEntity;
  });
}

// The account a review of this row names: 1-based, in printed order, or null for a statement of one account. A row's
// location (`transaction:N`) is numbered within its account, so a statement of several accounts holds one
// `transaction:2` per account and the server refuses the location alone. A package row carries its own
// (`source_account`); a statement's rows are the account on screen's (`fallbackAccount`).
function reviewAccountOf(tx, fallbackAccount = null) {
  return tx.source_account ?? fallbackAccount ?? null;
}

// A deposit the classifier left for review and nobody has decided yet: its statement, account and row, or null. The
// row's own Confirm and Mark buttons and the multi-select's checkbox are offered for exactly these.
function pendingReviewTarget(tx, fallbackJobId = null, fallbackAccount = null) {
  const record = transactionClassification(tx);
  if (record.revenue_initial_classification !== "unverified_deposit") return null;
  if (record.revenue_review_status === "confirmed" || record.revenue_review_status === "rejected") return null;
  const jobId = tx.source_job || fallbackJobId;
  const sourceLocation = record.source_location;
  return jobId && sourceLocation ? { jobId, account: reviewAccountOf(tx, fallbackAccount), sourceLocation } : null;
}

// The review a credit may take (true revenue spec §10.7), as the server allows it: "both" (Confirm Revenue and Mark
// Non-Revenue) for a credit the classifier left unverified (held or counted), "reject" (Mark Non-Revenue only) for a
// credit a rule verified, "" for anything else. An analysis saved before 5.6 carries no tier and keeps its rules: only
// a credit left unverified is reviewed.
function revenueReviewKind(record) {
  if (record.revenue_initial_classification === "unverified_deposit") return "both";
  if (record.revenue_initial_classification === "verified_revenue" && typeof record.revenue_tier === "string") return "reject";
  return "";
}

function revenueReviewControls(tx, fallbackJobId = null, fallbackAccount = null) {
  const record = transactionClassification(tx);
  const kind = revenueReviewKind(record);
  if (!kind) return "";
  const jobId = tx.source_job || fallbackJobId;
  const sourceLocation = record.source_location;
  if (!jobId || !sourceLocation) return "";
  const account = reviewAccountOf(tx, fallbackAccount);
  // Drawn while the multi-select's batch is being saved (a sort, the statement window), a row's buttons are held
  // like the ones already on screen (holdRowReviews): its decision would wait for nothing.
  const common = `data-revenue-review-job="${escapeHtml(jobId)}" data-revenue-review-location="${escapeHtml(sourceLocation)}"`
    + (account === null ? "" : ` data-revenue-review-account="${escapeHtml(String(account))}"`)
    + (bulkBusy ? " disabled" : "");
  if (record.revenue_review_status === "confirmed" || record.revenue_review_status === "rejected") {
    const decision = record.revenue_review_status === "confirmed" ? "Confirmed as revenue" : "Marked non-revenue";
    return `
      <div class="revenue-review-actions review-note">
        <span>${decision}</span>
        <button class="table-action" type="button" ${common} data-revenue-review-action="reset">Reset Decision</button>
      </div>
    `;
  }
  const confirm = kind === "both"
    ? `<button class="table-action review-confirm" type="button" ${common} data-revenue-review-action="confirm" aria-label="Confirm this deposit as operating revenue">Confirm Revenue</button>`
    : "";
  return `
    <div class="revenue-review-actions">
      ${confirm}
      <button class="table-action review-reject" type="button" ${common} data-revenue-review-action="reject" aria-label="Exclude this deposit from operating revenue">Mark Non-Revenue</button>
    </div>
  `;
}

function revenueReviewReason(tx) {
  const record = transactionClassification(tx);
  if (txAmount(tx) <= 0) return "";
  // 5.6 (true revenue spec §10.6): a counted or held credit names its reason, and one sentence on it.
  const entry = REVENUE_TIER_REASONS[record.revenue_tier_reason];
  if (entry && (record.revenue_tier === "counted_flagged" || record.revenue_tier === "excluded_pending_review")) {
    return `${entry[1]}. ${entry[2]}`;
  }
  if (typeof record.revenue_tier === "string" || record.revenue_classification !== "unverified_deposit") return "";
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

// Draws the rows; returns the multi-select keys of the deposits it offered a checkbox for (none unless `selectable`).
function renderTransactionRows(tableEl, countEl, transactions, filter, currency = "USD", options = {}) {
  if (!tableEl || !countEl) return [];
  const {
    sort = "date",
    showSource = false,
    limit = TRANSACTION_PAGE,
    moreEl = null,
    canonicalEntity = null,
    reviewJobId = null,
    reviewAccount = null,
    selectable = false,
    nsfDays = null,
  } = options;
  const rows = Array.isArray(transactions) ? transactions : [];
  const matched = sortTransactions(filterTransactions(rows, filter, canonicalEntity, nsfDays), sort);
  const visible = matched.slice(0, limit);
  const showRunningBalance = matched.some((tx) => runningBalanceValue(tx) !== null);
  const runningBalanceHeader = tableEl.closest("table")?.querySelector("[data-running-balance-column]");
  if (runningBalanceHeader) runningBalanceHeader.hidden = !showRunningBalance;
  // The multi-select column shows only while a row shown can be picked (a deposit awaiting review).
  const targets = visible.map((tx) => (selectable ? pendingReviewTarget(tx, reviewJobId, reviewAccount) : null));
  const pickable = targets.some(Boolean);
  tableEl.closest("table")?.classList.toggle("has-select", pickable);
  const offered = targets.filter(Boolean).map((target) => bulkKey(target.jobId, target.account, target.sourceLocation));
  if (filter === "nsf" && !canonicalEntity) {
    // The header counts the DAYS, as the tile does; the rows are the postings that ended them.
    countEl.textContent = nsfDaysLabel(nsfDays) + (visible.length < matched.length
      ? ` · showing ${formatNumber(visible.length)} of ${formatNumber(matched.length)} rows` : "");
  } else {
    const filterLabel = canonicalEntity || (filter === "all" ? "transactions"
      : filter === "nsf_fees" ? (matched.length === 1 ? "NSF fee row" : "NSF fee rows")
        : revenueFilterLabel(filter, matched.length) || `${filter} matches`);
    countEl.textContent = visible.length < matched.length
      ? `${formatNumber(visible.length)} of ${formatNumber(matched.length)} ${filterLabel}`
      : `${formatNumber(matched.length)} ${filterLabel}`;
  }
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
    const columns = 5 + (showSource ? 1 : 0) + (showRunningBalance ? 1 : 0) + (pickable ? 1 : 0);
    const note = filter === "all" ? "No statement returned transaction rows."
      : filter === "nsf" && !canonicalEntity ? nsfDaysEmptyNote(nsfDays)
      : filter === OLDER_REVIEW_FILTER
        ? "No deposit is left unverified. Analysed with older classification rules: Re-analyze to compute true revenue."
      : "No rows matched this filter.";
    tableEl.innerHTML = `
      <tr>
        <td class="empty-cell" colspan="${columns}"><strong>No transactions found</strong>${escapeHtml(note)}</td>
      </tr>
    `;
    return offered;
  }
  const sourceLabels = showSource ? statementSourceLabels(rows) : null;
  tableEl.innerHTML = visible.map((tx, index) => {
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
    const target = targets[index];
    // Each box names its deposit, so a screen reader can tell twenty of them apart.
    const pickLabel = `Select the deposit of ${formatMoney(amount, rowCurrency)} on ${tx.date || "an unknown date"}: `
      + (txDescriptionRaw(tx) || "no description");
    const pick = !selectable ? "" : `<td class="tx-check">${target ? `<input type="checkbox" class="tx-select"
        data-bulk-job="${escapeHtml(target.jobId)}" data-bulk-location="${escapeHtml(target.sourceLocation)}"${
        target.account === null ? "" : ` data-bulk-account="${escapeHtml(String(target.account))}"`}
        aria-label="${escapeHtml(pickLabel)}"${bulkSelection.has(bulkKey(target.jobId, target.account, target.sourceLocation)) ? " checked" : ""}>` : ""}</td>`;
    return `
      <tr>
        ${pick}
        <td class="tx-date">${escapeHtml(tx.date || "N/A")}</td>
        ${source}
        <td class="tx-desc">${escapeHtml(txDescriptionRaw(tx) || "N/A")}</td>
        <td>${glassChip(category.glyph, category.label, category.tone)}${flaggedChip(tx)}${revenueSourceChip(tx)}${reviewReasonHtml}</td>
        <td class="amount-cell ${amount < 0 ? "amount-debit" : "amount-credit"}">${amount > 0 ? "+" : ""}${escapeHtml(formatMoney(amount, rowCurrency))}</td>
        ${runningBalance}
        <td class="tx-review">${revenueReviewControls(tx, reviewJobId, reviewAccount)}</td>
      </tr>
    `;
  }).join("");
  return offered;
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
      nsfDays: packageNsfDays(pkg),
    };
  }
  const statement = currentAnalysis?.statement || {};
  return {
    transactions: getTransactions(statement),
    currency: statement.currency || "USD",
    multi: false,
    nsfDays: statementNsfDays(currentAnalysis?.metrics),
  };
}

// The account of the statement on screen that its rows' reviews name (1-based, printed order): the account shown of a
// statement that publishes its accounts, null for a statement of one account and for a package (whose rows carry
// their own).
function shownReviewAccount() {
  if (currentAnalysis && currentAnalysis.package) return null;
  if (!currentDocument || !isDocumentPayload(currentDocument)) return null;
  return Number.isInteger(selectedAccountIndex) && selectedAccountIndex >= 0 ? selectedAccountIndex + 1 : null;
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
  // The ticks belong to the analysis and account on screen: another one (reopened, a new package, another account
  // picked) starts with none, even where it shows the same deposit.
  const scope = JSON.stringify([currentJobIds, currentJobId, shownReviewAccount()]);
  if (scope !== bulkScope) {
    bulkSelection.clear();
    bulkScope = scope;
  }
  const offered = renderTransactionRows(
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
      reviewAccount: shownReviewAccount(),
      selectable: true,
      nsfDays: ctx.nsfDays,
    }
  );
  // The selection is what is ticked on screen: a tick whose row is no longer shown (filtered out, on a page not
  // drawn, decided) is dropped, so the bar never acts on a deposit the analyst cannot see.
  const shown = new Set(offered);
  [...bulkSelection].forEach((key) => { if (!shown.has(key)) bulkSelection.delete(key); });
  syncBulkReview();
}

/* --- multi-select of deposits awaiting review ------------------------------
   The ticked deposits, by statement, account and row. The action bar shows only while at least one is ticked; its
   decision is saved one batch per statement (POST /analysis/<job>/revenue-reviews, all or nothing per statement). */
let bulkSelection = new Set();
let bulkScope = null;
let bulkBusy = false;
// Reviews of single rows still waiting for the server: the bar's decisions wait for them, and they for the bar's.
let rowReviewsInFlight = 0;
// A re-analysis of the statement on screen still waiting for the server (reanalyzeShownStatement): every review waits
// for it, since its answer replaces the rows a decision names; and it waits for them.
let reanalysisBusy = false;

function bulkKey(jobId, account, sourceLocation) {
  return JSON.stringify([jobId, account ?? null, sourceLocation]);
}

function boxKey(box) {
  const account = box.getAttribute("data-bulk-account");
  return bulkKey(box.getAttribute("data-bulk-job"), account === null ? null : Number(account),
    box.getAttribute("data-bulk-location"));
}

function bulkBoxes() {
  return [...(els.transactionTable?.querySelectorAll("input[data-bulk-job]") || [])];
}

// Row review buttons, in the ledger and the statement window, are held while a batch is being saved.
function holdRowReviews(held) {
  [els.transactionTable, els.statementModalTransactions].forEach((table) => {
    table?.querySelectorAll("[data-revenue-review-action]").forEach((button) => { button.disabled = held; });
  });
}

// `refocus`: the bar's own button started this, so when the bar goes away its focus moves to the select-all box (or the
// table's title when no box is left) instead of dropping to the page.
function syncBulkReview({ refocus = false } = {}) {
  const count = bulkSelection.size;
  if (els.bulkReviewBar) els.bulkReviewBar.hidden = count === 0;
  if (els.bulkReviewCount) els.bulkReviewCount.textContent = `${formatNumber(count)} selected`;
  // Announced from outside the bar: a live region inside it is not heard while the bar is hidden or appearing.
  if (els.bulkReviewStatus) els.bulkReviewStatus.textContent = count ? `${formatNumber(count)} selected` : "";
  const held = bulkBusy || rowReviewsInFlight > 0 || reanalysisBusy;
  els.bulkReviewBar?.querySelectorAll("button").forEach((button) => { button.disabled = held; });
  if (els.bulkSelectAll) {
    // Ticked when every deposit shown awaiting review is picked; mixed when only some are.
    const boxes = bulkBoxes();
    const picked = boxes.filter((box) => box.checked).length;
    els.bulkSelectAll.checked = boxes.length > 0 && picked === boxes.length;
    els.bulkSelectAll.indeterminate = picked > 0 && picked < boxes.length;
    els.bulkSelectAll.disabled = boxes.length === 0;
  }
  if (refocus && count === 0) {
    (els.bulkSelectAll && !els.bulkSelectAll.disabled ? els.bulkSelectAll : els.transactionsTitle)?.focus();
  }
}

function pickDeposit(box, on) {
  const key = boxKey(box);
  box.checked = on;
  if (on) bulkSelection.add(key);
  else bulkSelection.delete(key);
}

function clearBulkSelection({ refocus = false } = {}) {
  bulkSelection.clear();
  bulkBoxes().forEach((box) => { box.checked = false; });
  syncBulkReview({ refocus });
}

// A response's JSON body, or {} when it has none (an error page from a proxy, an empty body): the refusal then reads
// "Revenue review failed (status)" instead of a parser's complaint.
async function responseJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return {};
  }
}

// What a notification calls a statement of the package on screen: its month ("March 2031"), with its file when
// another statement of the package has the same month (as the Monthly Statements table tells them apart), else its
// file. Null for the one statement shown, which needs no name.
function reviewedStatementName(jobId) {
  const pkg = currentAnalysis && currentAnalysis.package;
  if (!pkg) return null;
  const documents = countedDocuments(pkg.documents);
  const doc = documents.find((item) => packageMember(item.id).jobId === jobId);
  const month = doc ? statementMonth(doc.period_start, doc.period_end) : null;
  if (!month) return (doc && doc.filename) || "a statement";
  const label = `${MONTH_NAMES[month.month]} ${month.year}`;
  const shared = documents.some((item) => {
    const other = statementMonth(item.period_start, item.period_end);
    return packageMember(item.id).jobId !== jobId && other && other.key === month.key;
  });
  return shared && doc.filename ? `${label} (${doc.filename})` : label;
}

function showNotifications() {
  if (els.notificationsPopover && els.notificationsPopover.hidden) togglePopover(els.notificationsPopover, els.notificationsBtn);
}

// Draws the analysis on screen again from what was saved: a package from the server's package, a statement from its
// saved analysis (`saved`: the last statement saved, {jobId, analysis}). The rows opened with Show more stay open, and
// the ticks are drawn from the selection. Throws when the package cannot be fetched. Only the analysis the review was
// made on is drawn: one opened while the package was being fetched is left as it is.
async function redrawAfterReview(saved) {
  const limit = transactionLimit;
  // The redraws below draw the first page of rows and so drop every tick past it; the ticks come back before the
  // rows opened with Show more are drawn again.
  const kept = [...bulkSelection];
  const scope = bulkScope;
  const shown = currentJobIds.join(",");
  try {
    if (currentJobIds.length > 1) {
      const response = await fetch(`/package_analysis?ids=${encodeURIComponent(shown)}`);
      if (!response.ok) throw new Error(`the page could not be refreshed (${response.status})`);
      const pkg = await response.json();
      if (currentJobIds.join(",") !== shown) return;
      renderPackageAnalysis(pkg);
      setPackageActions(currentJobIds);
      rememberPackage(currentJobIds, pkg);
    } else if (saved && currentJobId === saved.jobId) {
      renderAnalysis(saved.analysis);
      setActions(currentJobId, true);
      rememberShownStatement(currentJobId);
    }
  } finally {
    if (bulkScope === scope) {
      transactionLimit = limit;
      kept.forEach((key) => bulkSelection.add(key));
      // A statement shown without an account (its main account withheld) has no ledger on screen to draw.
      if (currentAnalysis) renderMainTransactions({ keepLimit: true });
    }
  }
}

async function submitBulkReview(decision) {
  if (bulkBusy || rowReviewsInFlight > 0 || reanalysisBusy || !bulkSelection.size) return;
  const byJob = new Map();
  [...bulkSelection].forEach((key) => {
    const [jobId, account, sourceLocation] = JSON.parse(key);
    if (!byJob.has(jobId)) byJob.set(jobId, []);
    byJob.get(jobId).push({ key, account, sourceLocation });
  });
  bulkBusy = true;
  syncBulkReview();
  holdRowReviews(true);
  const failures = [];
  let applied = 0;
  let latest = null;
  for (const [jobId, picks] of byJob) {
    try {
      const decisions = picks.map(({ account, sourceLocation }) => (
        account === null ? { source_location: sourceLocation, decision }
          : { source_location: sourceLocation, decision, account }));
      const response = await fetch(`/analysis/${encodeURIComponent(jobId)}/revenue-reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisions }),
      });
      const payload = await responseJson(response);
      if (!response.ok || !payload.analysis) throw new Error(payload.error || `Revenue review failed (${response.status})`);
      applied += picks.length;
      picks.forEach(({ key }) => bulkSelection.delete(key));
      latest = { jobId, analysis: payload.analysis };
      if (modalJobId === jobId) {
        setModalAnalysis(payload.analysis);
        renderStatementModal(jobId, payload.analysis, "");
      }
    } catch (error) {
      const name = reviewedStatementName(jobId);
      failures.push(`Not saved${name ? ` for ${name}` : ""}: ${error.message || String(error)}`);
    }
  }
  // The analysis on screen is drawn again once, from what was saved (the Monthly Statements' True deposits follow
  // from the new verified revenue); a statement refused keeps its ticks.
  let redrawFailure = null;
  if (applied) {
    try {
      await redrawAfterReview(latest);
    } catch (error) {
      redrawFailure = error.message || String(error);
    }
  }
  bulkBusy = false;
  holdRowReviews(false);
  syncBulkReview({ refocus: true });
  if (applied) {
    const noun = applied === 1 ? "deposit" : "deposits";
    notify(decision === "confirm" ? `${applied} ${noun} confirmed as revenue` : `${applied} ${noun} marked non-revenue`,
      "green");
  }
  failures.forEach((failure) => notify(failure, "red"));
  if (redrawFailure) {
    notify(`Saved, but ${redrawFailure}: open the statements again to see the decisions`, "red");
  }
  // A refusal is not left to a dot on the notifications button: the notifications open on it.
  if (failures.length || redrawFailure) showNotifications();
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
      reviewAccount: modalReviewAccount,
      nsfDays: statementNsfDays(modalAnalysis?.metrics),
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

// `tone` "review" marks a result that needs review (amber) rather than a failure (red, the default).
function setStatusMessage(message, tone = "error") {
  if (!els.statusMessage) return;
  els.statusMessage.textContent = message || "";
  els.statusMessage.hidden = !message;
  els.statusMessage.classList?.toggle("review", tone === "review");
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
  // Nothing on screen has deposits to review until an account is drawn (renderAccount sets the count again).
  setReviewCount(0);
  currentDocument = null;
  selectedAccountIndex = null;
  hideAccountsPanel();
  syncRulesOutdatedNotice(null);
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
  renderFlaggedPositions([], null, false);
  renderRevenueEvidence({
    total_posted_credit_count: 0,
    revenue_established: true,
    verified_revenue_established: true,
    true_revenue_count: 0,
    true_revenue_total: 0,
    verified_revenue_count: 0,
    verified_revenue_total: 0,
    counted_flagged_count: 0,
    counted_flagged_total: 0,
    excluded_pending_review_count: 0,
    excluded_pending_review_total: 0,
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
  VER: ["✓", "Verified"],
  CNT: ["+", "Counted"],
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

const CHIP_TONES = { green: "success", red: "error", blue: "info", amber: "warning", violet: "violet", teal: "teal", neutral: "neutral" };

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
  const headline = action && action.headline ? " metric-headline" : "";
  return `
    <${tag} class="metric${actionable ? " metric-action" : ""}${headline}"${attributes}>
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
  // 5.6 (true revenue spec §10.1): True Revenue is the headline, first and larger.
  const headline = action && action.headline ? " metric-headline" : "";
  return `
    <${tag} class="metric-row${headline}"${attributes}>
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

/* --- flagged positions ------------------------------------------------------
   Obligations outside lender math (analysis/flag_groups.py), one row per payee, for the groups ticked in Settings:
   the server leaves the other groups out when it serves the analysis. */

// The panel's rows. A statement serves one list (detection.flagged_positions, already in group order), a package one
// list per group (flagged_positions): either way they come out group by group, each group's own order kept. Null when
// the payload publishes none (an analysis saved before flagged positions existed): the panel then cannot say whether
// any group was paid.
function flaggedPositionEntries(positions) {
  const entries = (list) => (Array.isArray(list) ? list : []).filter((entry) => entry && typeof entry === "object");
  if (Array.isArray(positions)) return entries(positions);
  if (!positions || typeof positions !== "object") return null;
  const known = Object.keys(FLAG_GROUP_LABELS);
  const groups = [...known, ...Object.keys(positions).filter((group) => !known.includes(group))];
  return groups.flatMap((group) => entries(positions[group]).map((entry) => ({ ...entry, group })));
}

// `isPackage` adds the Statements column: how many of the package's statements paid the payee.
function flaggedPositionRowsHtml(entries, currency, isPackage = false) {
  const columns = isPackage ? 6 : 5;
  if (entries === null) {
    return `
      <tr>
        <td class="empty-cell" colspan="${columns}"><strong>Not available</strong>Analysed before flagged positions existed; re-analyze to see them.</td>
      </tr>
    `;
  }
  if (!entries.length) {
    return `
      <tr>
        <td class="empty-cell" colspan="${columns}"><strong>No flagged payments</strong>No group ticked in Settings has payments here.</td>
      </tr>
    `;
  }
  return entries.map((entry) => {
    const group = String(entry.group || "");
    const payee = String(entry.payee || flagGroupLabel(group));
    const span = entry.first_date && entry.last_date && entry.first_date !== entry.last_date
      ? `<div class="table-cell-detail">${escapeHtml(entry.first_date)} to ${escapeHtml(entry.last_date)}</div>`
      : "";
    const statements = isPackage ? `<td>${escapeHtml(formatNumber(entry.documents))}</td>` : "";
    // 5.3 (owner ruling 2026-09-27): a payee the ledger has not confirmed says so under its name.
    const unconfirmed = entry.review_required === true
      ? '<div class="table-cell-detail">Unconfirmed: identity under review</div>'
      : "";
    // Money the payee paid in (a factor's payouts, owner ruling 2026-09-26) is shown under the debits as received,
    // never added to them. A payee with no credit shows no such line.
    const received = Number(entry.count_credited) > 0;
    const receivedCount = received
      ? `<div class="table-cell-detail">${escapeHtml(formatNumber(entry.count_credited))} received</div>`
      : "";
    const receivedTotal = received
      ? `<div class="table-cell-detail">${escapeHtml(formatMoney(entry.total_credited, currency))} received</div>`
      : "";
    return `
      <tr>
        <td>${escapeHtml(flagGroupLabel(group))}</td>
        <td><button class="evidence-link" type="button" data-lender-evidence-filter="flagged:${escapeHtml(group)}" data-lender-evidence-entity="${escapeHtml(payee)}" aria-label="Show the transactions of ${escapeHtml(payee)}">${escapeHtml(payee)}</button>${unconfirmed}</td>
        <td>${escapeHtml(formatNumber(entry.count))}${receivedCount}</td>
        <td>${escapeHtml(formatMoney(entry.total_debited, currency))}${receivedTotal}</td>
        <td>${escapeHtml(cadenceLabel(entry.cadence))}${span}</td>
        ${statements}
      </tr>
    `;
  }).join("");
}

function renderFlaggedPositions(positions, currency, isPackage = false) {
  if (!els.flaggedTable || !els.flaggedCount) return;
  const entries = flaggedPositionEntries(positions);
  els.flaggedCount.textContent = entries === null
    ? "Not available"
    : `${formatNumber(entries.length)} ${entries.length === 1 ? "payee" : "payees"}`;
  els.flaggedTable.innerHTML = flaggedPositionRowsHtml(entries, currency, isPackage);
}

// 5.6 (true revenue spec §10.1, §10.7): the Revenue evidence rows, [filter, label, glyph, status, tone, which flag
// establishes the figure]. Held for Review is followed by its reasons, largest total first: the Held for Review view.
const revenueRows = [
  ["true_revenue", "True Revenue", "REV", "Revenue", "green", "revenue_established"],
  ["verified_revenue", "Verified Revenue", "VER", "Verified", "green", "verified_revenue_established"],
  ["counted_flagged", "Counted, Not Verified", "CNT", "Counted", "teal", "revenue_established"],
  ["excluded_pending_review", "Held for Review", "?", "Review Required", "amber", "revenue_established"],
  ["non_revenue", "Non-Revenue", "X", "Excluded", "neutral", null],
];

// The credits of one middle tier of a statement or a package by reason, largest total first (ties by code), or []
// where they are not established. `tier` is counted_flagged or excluded_pending_review.
function tierReasonEntries(source = {}, tier = "excluded_pending_review") {
  const key = `${tier}_by_reason`;
  const byReason = source && source.revenue_established === true && source[key]
    && typeof source[key] === "object" ? source[key] : {};
  return Object.entries(byReason)
    .map(([reason, figures]) => ({ reason, count: figures && figures.count, total: numberOrNull(figures && figures.total) }))
    .sort((a, b) => (b.total ?? 0) - (a.total ?? 0) || a.reason.localeCompare(b.reason));
}

// The held credits by reason: the Held for Review view.
function heldReasonEntries(source = {}) {
  return tierReasonEntries(source, "excluded_pending_review");
}

// The words naming one middle tier's reason rows in the evidence table.
const TIER_REASON_ROW_WORDS = Object.freeze({ counted_flagged: "counted", excluded_pending_review: "held" });

function revenueEvidenceRowsHtml(metrics = {}, currency = "USD", modal = false) {
  const filterAttribute = modal ? "data-modal-revenue-filter" : "data-revenue-filter";
  return revenueRows.map(([filter, label, glyph, status, tone, flag]) => {
    const shown = flag === null || metrics[flag] === true;
    const row = `
      <tr>
        <td><button class="evidence-link" type="button" ${filterAttribute}="${filter}" aria-label="Show exact ${escapeHtml(label)} transactions">${escapeHtml(label)}</button></td>
        <td>${escapeHtml(shown ? formatNumber(metrics[`${filter}_count`]) : "N/A")}</td>
        <td>${escapeHtml(shown ? formatMoney(metrics[`${filter}_total`], currency) : "N/A")}</td>
        <td>${glassChip(glyph, status, tone)}</td>
      </tr>
    `;
    // Audit B11 (I53): Counted is broken down by reason, as Held is, so the card that headlines it can be read.
    if (!TIER_REASON_ROW_WORDS[filter]) return row;
    return row + tierReasonEntries(metrics, filter).map(({ reason, count, total }) => `
      <tr class="evidence-subrow">
        <td><button class="evidence-link" type="button" ${filterAttribute}="${filter}:${escapeHtml(reason)}" aria-label="Show the ${TIER_REASON_ROW_WORDS[filter]} ${escapeHtml(revenueReasonLabel({ revenue_tier_reason: reason }))} transactions">${escapeHtml(revenueReasonLabel({ revenue_tier_reason: reason }))}</button></td>
        <td>${escapeHtml(formatNumber(count))}</td>
        <td>${escapeHtml(formatMoney(total, currency))}</td>
        <td></td>
      </tr>
    `).join("");
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

// The choice made on this page (null until one is); storage carries it to the next visit and, where storage is
// blocked, the choice still holds for the page.
let allAccountsChoice = null;

function allAccountsView() {
  if (allAccountsChoice !== null) return allAccountsChoice;
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

// Why the statement's main account was not verified, in the words the dashboard shows.
function unverifiedMainWhy(entry, currency) {
  return entry.status === "idle"
    ? `it printed no activity this period (balance ${formatMoney(entry.balance, currency)})`
    : accountReasonText(entry.reasons);
}

function unverifiedMainNote(report, currency) {
  // The sentence the summary leads with when the statement's main account was not verified and another, verified,
  // account is shown (All accounts); "" otherwise.
  const entry = report ? unverifiedMainAccount(accountRoster(report)) : null;
  return entry ? `Main account ${accountDisplayName({}, entry)} could not be verified: ${unverifiedMainWhy(entry, currency)}. ` : "";
}

// One account's own decision, as its pill shows it.
function accountDecision(report) {
  const metrics = report.metrics || {};
  const quality = report.quality || {};
  return hasMaterialPotentialLenderDebits(metrics) || metrics.revenue_review_required
    ? "review_required"
    : quality.corporate_use || quality.level || "review_required";
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
          tabindex="0"${isSelected ? ` aria-current="true"` : ""}>
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
  // setInitialState hid the notice; this statement's own analysis decides it. Re-analysis concerns the whole saved
  // statement, so the notice stays while the main account's metrics are withheld.
  syncRulesOutdatedNotice(report);
  currentDocument = report;
  currentAnalysis = null;
  setProgress(false);
  const name = accountDisplayName({}, entry);
  // The statement's own period, bank and denomination, read off a verified account of the same statement.
  const first = (published[0] || {}).statement || {};
  const currency = first.currency || null;
  const why = unverifiedMainWhy(entry, currency);
  const verified = published.length;
  const explanation = `${name} is this statement's main account and could not be verified: ${why}. `
    + "No metrics are shown for it.";
  els.statusHeading.textContent = "Main account needs review";
  setBanner("pending", "Main account not verified; its metrics withheld", "Review required");
  setStatusMessage(explanation, "review");
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

// 5.6 (true revenue spec §10.1): the four tiers of the posted credits.
const CREDIT_MIX = [
  ["verified_revenue", "Verified revenue", "dot-green"],
  ["counted_flagged", "Counted, not verified", "dot-teal"],
  ["excluded_pending_review", "Held for review", "dot-amber"],
  ["non_revenue", "Non-revenue", "dot-muted"],
];

// The four tiers of the posted credits, each as its share of the four together. A row is a button to that tier's
// transactions, like the Revenue evidence rows. Where revenue is not established the tiers are not known, so the
// counted and held rows read N/A and no share is drawn (§10.4).
function renderCreditMix(source = {}, currency = "USD") {
  const established = source.revenue_established === true;
  const parts = CREDIT_MIX.map(([state, label, dot]) => {
    const known = established || state === "non_revenue"
      || (state === "verified_revenue" && source.verified_revenue_established === true);
    return {
      state,
      label,
      dot,
      count: known ? source[`${state}_count`] : null,
      total: known ? source[`${state}_total`] : null,
      size: Math.max(numberOrNull(known ? source[`${state}_total`] : null) || 0, 0),
    };
  });
  const sum = established ? parts.reduce((total, part) => total + part.size, 0) : 0;
  const share = (part) => (sum > 0 ? `${((part.size / sum) * 100).toFixed(1)}%` : "N/A");
  els.creditMixBar.innerHTML = parts
    .filter((part) => sum > 0 && part.size > 0)
    .map((part) => `<span class="${part.dot}" style="width: ${((part.size / sum) * 100).toFixed(2)}%"></span>`)
    .join("");
  // Audit B11 (I53): each share is of the posted credits (the four tiers together), and says so.
  els.creditMixBar.setAttribute(
    "aria-label",
    sum > 0 ? `Credit mix, as a share of posted credits: ${parts.map((part) => `${share(part)} ${part.label.toLowerCase()}`).join(", ")}` : "Credit mix unavailable",
  );
  els.creditMixRows.innerHTML = parts.map((part) => `
    <button class="mix-row" type="button" data-revenue-filter="${part.state}" aria-label="Show exact ${escapeHtml(part.label)} transactions">
      <span class="mix-dot ${part.dot}"></span>
      <span class="mix-label">${escapeHtml(part.label)}</span>
      <span class="mix-count">${escapeHtml(formatNumber(part.count))}</span>
      <span class="mix-total">${escapeHtml(formatMoney(part.total, currency))}</span>
      <span class="mix-share" title="${escapeHtml(sum > 0 ? `${share(part)} of posted credits` : "Share of posted credits unavailable")}">${escapeHtml(share(part))}</span>
    </button>
  `).join("") + (sum > 0 ? `<p class="mix-caption">Shares of posted credits</p>` : "");
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

// Audit B11 (I06): the package's statements that count: every row but a repeated statement the server left out of
// its figures (`is_duplicate`), which the duplicate notice lists instead.
function countedDocuments(documents) {
  return (Array.isArray(documents) ? documents : []).filter((doc) => doc && doc.is_duplicate !== true);
}

// The rows a package lists as repeated statements, left out of its figures.
function duplicateDocuments(documents) {
  return (Array.isArray(documents) ? documents : []).filter((doc) => doc && doc.is_duplicate === true);
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

// The monthly chart follows the Monthly Statements basis (Settings) like the table beside it, so the page never shows
// two different figures as a month's deposits: Total deposits, True revenue, or both. 5.6 (true revenue spec §10.3):
// each Total bar holds its True part and the True part its Verified part, in three shades; in the True view the bar is
// True revenue with its Verified part shaded. A statement whose revenue is not established draws neither part.
// The monthly chart's geometry, as webapp/templates/index.html sets it: the plot box (.bar-chart, 190px border-box
// with a 1px baseline, so 189px of content), each value figure's line (.bar-value, 16px), the column's flex gap (8px)
// and the pull of each figure after the first (.bar-value-true and .bar-value-verified, margin-top -6px).
const MONTHLY_CHART_PLOT_PX = 189;
const MONTHLY_CHART_FIGURE_PX = 16;
const MONTHLY_CHART_GAP_PX = 8;
const MONTHLY_CHART_PULL_PX = 6;

function monthlyChartTallestBar(figures) {
  // Each figure takes its line and one gap (the last gap sits between the lowest figure and the bar); every figure
  // after the first is pulled up by its negative margin.
  return MONTHLY_CHART_PLOT_PX - figures * (MONTHLY_CHART_FIGURE_PX + MONTHLY_CHART_GAP_PX)
    + (figures - 1) * MONTHLY_CHART_PULL_PX;
}

// `unitsShown` is true for a package that refuses to combine its currencies (CURRENCY DOCTRINE §F: several currencies,
// or a member that declared none beside one that did). Audit B11 (I54): such a package's bars are scaled, and its peak
// chosen, within each currency (an undeclared member is a group of its own), never across them, and every bar names its
// unit, USD included; an undeclared member's stays undeclared.
function renderMonthlyChart(rows, unitsShown, view = "both") {
  if (!els.monthlyChart) return;
  const both = view === "both";
  const nested = view !== "total";
  const plotted = view === "true" ? trueDeposits : totalDeposits;
  const values = rows.map(({ doc }) => numberOrNull(plotted(doc)));
  const groupOf = (doc) => currencyOfDocument(doc) || "";
  const largestByGroup = new Map();
  rows.forEach(({ doc }, index) => {
    const value = values[index];
    if (value === null) return;
    largestByGroup.set(groupOf(doc), Math.max(largestByGroup.get(groupOf(doc)) ?? 0, value));
  });
  const years = new Set(rows.map((row) => row.month && row.month.year));
  const columns = `grid-template-columns: repeat(${Math.max(rows.length, 1)}, minmax(0, 1fr))`;
  // The tallest bar fills the plot box less the figures stacked above it (5.6, A4: the Verified figure is the third in
  // the Both view and the second in the True view), so the bar, its figures and the baseline fit exactly.
  const tallest = monthlyChartTallestBar(both ? 3 : nested ? 2 : 1);
  const bars = rows.map(({ doc }, index) => {
    const value = values[index];
    const currency = currencyOfDocument(doc);
    const largest = Math.max(0, largestByGroup.get(groupOf(doc)) ?? 0);
    const unit = unitsShown && currency ? ` ${currency}` : "";
    const withUnit = (text) => (text === "N/A" ? text : text + unit);
    const heightPx = largest > 0 && value !== null ? Math.max((Math.max(value, 0) / largest) * tallest, 2) : 0;
    const truePart = nested ? numberOrNull(trueDeposits(doc)) : null;
    // The Verified part stands only inside an established True part.
    const verifiedPart = truePart !== null ? numberOrNull(verifiedDeposits(doc)) : null;
    const shareOf = (part) => (part !== null && value > 0 ? Math.min(Math.max(part, 0) / value, 1) : 0);
    const trueShare = both ? shareOf(truePart) : 0;
    const verifiedShare = shareOf(verifiedPart);
    const verifiedLabel = nested ? withUnit(formatWhole(truePart !== null ? verifiedDeposits(doc) : null)) : null;
    return `
      <div class="bar-col">
        <span class="bar-value">${escapeHtml(withUnit(formatWhole(plotted(doc))))}</span>
        ${both ? `<span class="bar-value bar-value-true">${escapeHtml(withUnit(formatWhole(trueDeposits(doc))))}</span>` : ""}
        ${nested ? `<span class="bar-value bar-value-verified">${escapeHtml(verifiedLabel)}</span>` : ""}
        <div class="bar${both ? " bar-total" : value !== null && value === largest && largest > 0 ? " peak" : ""}" style="height: ${heightPx.toFixed(1)}px">${
          trueShare > 0 ? `<div class="bar-part" style="height: ${(trueShare * 100).toFixed(1)}%"></div>` : ""}${
          verifiedShare > 0 ? `<div class="bar-part bar-part-verified" style="height: ${(verifiedShare * 100).toFixed(1)}%"></div>` : ""}</div>
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
  const verifiedSwatch = `<span><i class="legend-swatch legend-swatch-verified" aria-hidden="true"></i>of which verified</span>`;
  const legend = both
    ? `<span><i class="legend-swatch" aria-hidden="true"></i>Total deposits</span>`
      + `<span><i class="legend-swatch legend-swatch-true" aria-hidden="true"></i>True revenue</span>` + verifiedSwatch
    : view === "true"
      ? `<span><i class="legend-swatch legend-swatch-true" aria-hidden="true"></i>True revenue</span>` + verifiedSwatch
        + "<span>and ledger (average daily balance) per statement</span>"
      : "<span>Total deposits (everything going in) and ledger (average daily balance) per statement</span>";
  const described = {
    both: "total deposits, true revenue and its verified part",
    true: "true revenue and its verified part",
    total: "total deposits",
  }[view] || "total deposits";
  els.monthlyChart.innerHTML = `
    <div class="chart-head">
      <span class="chart-title">Monthly deposits</span>
      <span class="chart-legend">${legend}</span>
    </div>
    <div class="bar-chart" style="${columns}" role="img" aria-label="Monthly deposits per statement: ${described}">${bars}</div>
    <div class="bar-labels" style="${columns}">${labels}</div>
  `;
}

function setReviewCount(value) {
  if (!els.reviewCount) return;
  // 5.6 (true revenue spec §10.4): a held count that is not established is shown as N/A, never as a partial count.
  if (value === "N/A") {
    els.reviewCount.textContent = "N/A";
    els.reviewCount.hidden = false;
    return;
  }
  const count = numberOrNull(value) || 0;
  els.reviewCount.textContent = formatNumber(count);
  els.reviewCount.hidden = count <= 0;
}

// A saved statement analysed with older lender rules says so (the server sets analysis_rules_outdated when it serves
// it), beside its Re-analyze button; a package or a statement of the current rules shows nothing. Kept in the block
// that tests/test_webapp_accounts_view.py runs with only the accounts panel: every element is looked up null-safe.
function syncRulesOutdatedNotice(report) {
  if (!els.rulesOutdatedNotice) return;
  els.rulesOutdatedNotice.hidden = !(report && report.analysis_rules_outdated === true);
}

function renderAnalysis(report) {
  if (els.monthlyCard) els.monthlyCard.style.display = "none";
  const published = publishedAccounts(report);
  const roster = accountRoster(report);
  // A payload with no account to show draws no statement, so it keeps no notice either.
  syncRulesOutdatedNotice(published.length ? report : null);
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
  if (unverified) {
    // All accounts on, and the user picked a verified account of a statement whose main account was not verified:
    // that account's own figures are shown, never as the main account's, and the statement still needs review.
    els.statusHeading.textContent = "Main account needs review";
    setBanner("pending", "Main account not verified; showing a verified account", "Review required");
    els.decisionPill.textContent = "Review required";
    els.decisionPill.className = "decision-pill review_required";
    const note = statusRowHtml(["Main account", "Not verified"]);
    [els.statusList, els.processingList].forEach((list) => list?.insertAdjacentHTML("afterbegin", note));
    els.heroChips?.insertAdjacentHTML("afterbegin", `<span class="hero-chip">Main account · Not verified</span>`);
  } else if (idleMain) {
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
  const decision = accountDecision(report);
  // Analysed with older rules (the server sets it at the top of the payload): of a statement of several accounts the
  // account drawn is its own payload, so the statement on screen (currentDocument) says it.
  const rulesOutdated = report.analysis_rules_outdated === true
    || Boolean(currentDocument && currentDocument.analysis_rules_outdated === true);

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
  // Audit B11 (I31): "Balanced" only where the statement's own rows reconcile to the bank's figures and its revenue is
  // established; the four tiers summing to the posted credits (`revenue_tiers_sum_to_posted`) holds by construction.
  const revenueBalanced = statementRevenueBalanced(report);
  renderHero({
    icon: BANK_ICON,
    kicker: [statement.bank || "Bank statement", accountName].filter(Boolean).join(" · "),
    title: month ? `${month} statement` : "Bank statement",
    chips: [
      [`Revenue · ${revenueBalanced ? "Balanced" : "Review required"}`],
      [`Integrity · ${integrityLabel(integrity)}`],
      [period(statement), true],
      [pageCount ? `${currency} · ${formatNumber(pageCount)} pages` : currency],
    ],
  });
  analysisCrumbs = ["Statements", statement.bank || "Statement", month || period(statement)];
  resultsCrumbs = analysisCrumbs;
  const revenueEstablished = metrics.revenue_established === true;
  renderCredits({
    label: "Total credits",
    value: formatMoney(totalCredits, currency),
    meta: `${escapeHtml(formatNumber(metrics.total_posted_credit_count))} credit transactions · True revenue `
      + `<span class="mono">${escapeHtml(revenueEstablished ? formatMoney(metrics.true_revenue_total, currency) : "N/A")}</span>`,
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
  // 5.6 (true revenue spec §10.7): the badge counts the held credits, N/A where they are not established; an analysis
  // saved before 5.6 has none, and keeps counting its deposits left unverified.
  setReviewCount(reviewBadgeValue(metrics, revenueEstablished));

  setStatusRows([
    ["OCR completed", "Yes"],
    ["Pages processed", formatNumber(statement.page_count || report.page_count || "--")],
    ["Processing time", elapsed],
    ["Parsing mode", parseModeLabel(report.parse_mode || selectedParseMode())],
    ["Parser used", report.model_used || "N/A"],
    ["Document integrity", integrityLabel(integrity)],
    ["Revenue reconciliation", revenueBalanced ? "Balanced" : "Review required"],
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
        ...revenueCardItems(metrics, currency, {
          established: revenueEstablished,
          verifiedEstablished: metrics.verified_revenue_established === true,
          unestablishedNote: rulesOutdated ? "Re-analyze to compute true revenue" : "",
          facts: statementRevenueFacts(metrics),
        }),
        ["Total Credits", formatMoney(totalCredits, currency), REVENUE_METRIC_COPY.totalCredits, "CR", "neutral"],
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
  renderFlaggedPositions(detection.flagged_positions, currency, false);
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
  // The same words as the status banner, the visual pair's page and part counters included.
  return { chip: "Processing", tone: "green", detail: processingStageLabel(entry.stage || entry.status), bar: "busy", width: 0 };
}

// Audit B11 (I06): the queue entry an entry repeats: the same bytes uploaded earlier in this batch (the server's
// `duplicate_of`), or null. A file uploaded on another day is not a repeat of this package.
function queueRepeatOf(entry) {
  if (!entry || !entry.duplicateOf) return null;
  return queueEntries.find((other) => other !== entry && other.jobId === entry.duplicateOf) || null;
}

function renderQueue() {
  if (!els.queueCard || !els.queueList) return;
  els.queueCard.hidden = !queueEntries.length;
  const pages = queueEntries.reduce((sum, entry) => sum + (numberOrNull(entry.pageCount) || 0), 0);
  const repeats = queueEntries.filter((entry) => queueRepeatOf(entry)).length;
  els.queueMeta.textContent = `${formatNumber(queueEntries.length)} ${queueEntries.length === 1 ? "file" : "files"}`
    + (pages ? ` · ${formatNumber(pages)} pages` : "")
    + (repeats ? ` · ${formatNumber(repeats)} repeated ${repeats === 1 ? "file" : "files"}, counted once` : "");
  els.queueList.innerHTML = queueEntries.map((entry, index) => {
    const state = queueState(entry);
    const repeat = queueRepeatOf(entry);
    const details = [
      repeat ? `Same file as ${repeat.name}: left out of the package figures` : "",
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
  // The reason, as a sentence of its own ahead of what to do about it.
  const reason = sentenceCase(friendlyAnalysisError(message)).replace(/([^.!?])$/, "$1.");
  const explanation = `${reason} Open Review extraction to inspect the reading and its review status. `
    + "No metrics have been published.";
  els.statusHeading.textContent = "Extraction needs review";
  setBanner("pending", "Extraction available; metrics withheld", "Review required");
  setStatusMessage(explanation, "review");
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
    duplicateOf: null,
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
  // Nothing in Recent is open while this upload runs; its own entry is marked when its result is drawn.
  setOpenAnalysis(null);
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
        // Audit B11 (I06): the earliest job holding these exact bytes; the queue names a repeat inside this batch.
        entry.duplicateOf = job.duplicate_of || null;
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
  shownAnalysis = { jobId: currentJobId, jobIds: currentJobIds.slice(), files: currentFiles, file: currentFile, startedAt,
                    selectedAccountIndex };
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
        openAnalysisKey = jobId;
        rememberHeldStatement(jobId, payload.analysis_error);
        // It opens no results page: its explanation is the New analysis page's status card, so it opens there.
        if (reveal) navigate("new");
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
      openAnalysisKey = jobId;
      rememberShownStatement(jobId);
      // A statement whose main account was not verified opens with its metrics withheld: not a green result.
      if (announce) notify(`${els.resultsTitle.textContent} analyzed`, currentAnalysis ? "green" : "amber");
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

// Audit B11 (I07, I33): "N statements · M months": the statements the package counts (one per document and printed
// cycle, `statement_periods`, published when it differs from the months) and the distinct calendar months they cover.
function packageSpanLabel(totals = {}, fallbackStatements = 0) {
  const months = numberOrNull(totals.months);
  const statements = numberOrNull(totals.statement_periods ?? totals.months) ?? fallbackStatements;
  const monthCount = months ?? statements;
  return `${formatNumber(statements)} ${statements === 1 ? "statement" : "statements"} · `
    + `${formatNumber(monthCount)} ${monthCount === 1 ? "month" : "months"}`;
}

// Audit B11 (I06): the package's repeated statements, which the server left out of every figure (MCA practice removes a
// duplicate statement, standard §4.6(3)): each named with the statement it repeats, and the package sent to review.
const DUPLICATE_REASON_WORDS = Object.freeze({
  same_content: "the same file",
  same_statement: "the same statement, downloaded again",
});

function renderDuplicateNotice(pkg = {}) {
  if (!els.duplicateNotice) return;
  const listed = Array.isArray(pkg.documents) ? pkg.documents : [];
  const repeats = duplicateDocuments(listed);
  const accounts = (Array.isArray(pkg.excluded_accounts) ? pkg.excluded_accounts : [])
    .filter((entry) => entry && entry.is_duplicate === true);
  const count = repeats.length + accounts.length;
  els.duplicateNotice.hidden = count === 0;
  if (!els.duplicateNoticeText) return;
  if (!count) {
    els.duplicateNoticeText.innerHTML = "";
    return;
  }
  const nameOf = (jobId) => {
    const doc = listed.find((item) => packageMember(item.id).jobId === String(jobId));
    return doc && doc.filename ? doc.filename : "an earlier statement";
  };
  const lines = [
    ...repeats.map((doc) => `${doc.filename || "A statement"} repeats ${nameOf(doc.duplicate_of)} `
      + `(${DUPLICATE_REASON_WORDS[doc.duplicate_reason] || "the same statement"})`),
    ...accounts.map((entry) => `account ${formatNumber(entry.account_index)} of ${nameOf(entry.job_id)} repeats `
      + `${nameOf(entry.duplicate_of)}`),
  ];
  els.duplicateNoticeText.innerHTML = `<strong>${escapeHtml(formatNumber(count))} repeated `
    + `${count === 1 ? "statement" : "statements"} left out of every figure.</strong> `
    + `${escapeHtml(lines.join("; "))}. The package needs review.`;
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
      openAnalysisKey = jobIds.join(",");
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
  syncRulesOutdatedNotice(null);
  els.resultsContent?.classList.remove("is-withheld");
  currentAnalysis = { package: pkg };
  currentMarkdown = "";
  renderMainTransactions();
  const totals = pkg.totals || {};
  // Audit B11 (I06): a repeated statement the server left out of every figure is listed by the duplicate notice, never
  // as a statement or a month of the package.
  const documents = countedDocuments(pkg.documents);
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
  renderDuplicateNotice(pkg);

  setResultsMode("package");
  showResultsContent();
  const monthRows = packageMonthRows(documents);
  const title = packageTitle(monthRows);
  const banks = [...new Set(documents.map((doc) => doc.bank).filter(Boolean))];
  const span = packageSpanLabel(totals, documents.length);
  // Audit B11 (I31): "Balanced" only where every statement reconciles to its bank's figures and revenue is established.
  const revenueBalanced = packageRevenueBalanced(pkg);
  renderHero({
    icon: PACKAGE_ICON,
    kicker: ["Package", `${formatNumber(documents.length)} ${documents.length === 1 ? "statement" : "statements"}`, banks.join(", ")]
      .filter(Boolean).join(" · "),
    title,
    chips: [
      [packagePeriod(documents), true],
      [packageCurrencyLabel(currencyInfo)],
      [`Revenue · ${revenueBalanced ? "Balanced" : "Review required"}`],
    ],
  });
  analysisCrumbs = ["Packages", title];
  resultsCrumbs = analysisCrumbs;
  // Audit B11 (I07, I33): "N statements · M months" (distinct calendar months), the gross monthly figure named gross,
  // and True per month beside the package's True: what an MCA advance is sized on.
  renderCredits({
    label: `Total credits · ${span}`,
    value: formatMoney(totals.total_credits, currency),
    meta: refusalNote
      ? escapeHtml(refusalNote)
      : `Avg monthly gross credits <span class="mono">${escapeHtml(formatMoney(totals.avg_monthly_credits, currency))}</span>`
        + ` · True revenue <span class="mono">${escapeHtml(formatMoney(totals.true_revenue_total, currency))}</span>`
        + ` · True per month <span class="mono">${escapeHtml(formatMoney(totals.avg_monthly_true_revenue, currency))}</span>`,
  });
  renderCreditMix(packageRevenueFlags(totals), currency);
  // The monthly chart is drawn with the Monthly Statements table (renderMonthlyStatements): both follow the basis
  // chosen in Settings.
  renderTotals([
    ["Total debits", formatMoney(totals.total_debits, currency)],
    ["Total cash flow", formatMoney(totals.cash_flow, currency), signTone(totals.cash_flow)],
    ["Avg monthly cash flow", formatMoney(totals.avg_monthly_cash_flow, currency), signTone(totals.avg_monthly_cash_flow)],
    ["Average daily balance", formatMoney(totals.average_daily_balance, currency)],
    ["NSFs", formatNumber(totals.nsf_count), countTone(totals.nsf_count)],
    ["Confirmed withholding", formatPercent(totals.package_withholding_rate), withholdingTone(totals.package_withholding_rate)],
  ]);
  // 5.6 (true revenue spec §10.7): the held credits; N/A with the Held figures (a member not established), never the
  // partial count of the members that are. A currency refusal keeps the count.
  setReviewCount(reviewBadgeValue(totals, packageRevenueFlags(totals).revenue_established));
  if (els.packageProcessingNote) {
    const failed = numberOrNull(totals.failed) || 0;
    els.packageProcessingNote.textContent = failed
      ? `${formatNumber(failed)} ${failed === 1 ? "statement" : "statements"} failed`
      : "All statements complete";
  }

  setStatusRows([
    // Audit B11 (I06): a repeated statement left out is no statement of the package.
    ["Statements completed", `${formatNumber(totals.completed)} / ${formatNumber(totals.distinct_documents ?? totals.documents)}`],
    ["Package currency", packageCurrencyLabel(currencyInfo)],
    ["Approved", formatNumber(totals.approved)],
    ["Manual review", formatNumber(totals.manual_review)],
    ["High integrity risk", formatNumber(totals.integrity_high)],
    ["Processing errors", formatNumber(totals.failed)],
    ["Confirmed withholding", formatPercent(totals.package_withholding_rate)],
    ["Potential exposure", formatPercent(totals.potential_withholding_exposure)],
    ["Revenue reconciliation", revenueBalanced ? "Balanced" : "Review required"],
    ["Eligible deposits basis", totals.withholding_denominator_label || "Eligible deposits"],
  ]);

  renderMetricSections([
    {
      title: "Package revenue",
      // Audit B11 (I07, I33): the statements and the distinct calendar months they cover (`months`); each per-month
      // figure is the package's total divided by those months.
      sub: [span, packageUnestablishedNote(totals, documents)].filter(Boolean).join(" · "),
      items: [
        ...revenueCardItems(totals, currency, {
          ...packageRevenueFlags(totals), note: moneyNote, facts: packageRevenueFacts(totals),
        }),
        ["True Revenue Per Month", formatMoney(totals.avg_monthly_true_revenue, currency), moneyNote("True revenue per calendar month, across the package's accounts"), "AVG", "green", { revenueFilter: "true_revenue" }],
        ["Verified Revenue Per Month", formatMoney(totals.avg_monthly_verified_revenue, currency), moneyNote("Verified revenue per calendar month, across the package's accounts"), "AVG", "green", { revenueFilter: "verified_revenue" }],
        ["Total Credits", formatMoney(totals.total_credits, currency), moneyNote(REVENUE_METRIC_COPY.totalCredits), "CR", "neutral"],
        ["Avg Monthly Gross Credits", formatMoney(totals.avg_monthly_credits, currency), moneyNote("Gross posted credits per calendar month (not True revenue)"), "AVG", "neutral"],
      ],
    },
    {
      title: "Cash flow",
      sub: "Package-level affordability signals",
      items: [
        ["Total Debits", formatMoney(totals.total_debits, currency), moneyNote("All posted debit transactions"), "DB", "neutral"],
        ["Avg Monthly Debits", formatMoney(totals.avg_monthly_debits, currency), moneyNote("Average posted debits per calendar month"), "AVG", "neutral"],
        ["Total Cash Flow", formatMoney(totals.cash_flow, currency), moneyNote("Credits minus debits"), "CF", negativeTone(totals.cash_flow)],
        ["Avg Monthly Cash Flow", formatMoney(totals.avg_monthly_cash_flow, currency), moneyNote("Average cash flow per calendar month"), "AVG", negativeTone(totals.avg_monthly_cash_flow)],
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
  const funders = Array.isArray(pkg.funders) ? pkg.funders : [];
  const potentialLenders = Array.isArray(pkg.potential_lenders) ? pkg.potential_lenders : [];
  const insuranceProviders = Array.isArray(pkg.insurance_providers) ? pkg.insurance_providers : [];
  // These rollups sum across the whole package, so they are denominated by the
  // package currency - null when there is not one, in which case the backend
  // has already refused their money and `formatMoney` renders "N/A".
  const currency = packageCurrencyInfo(pkg).currency;
  renderLenders(funders, potentialLenders, currency);
  renderInsurance(insuranceProviders, currency);
  renderFlaggedPositions(pkg.flagged_positions, currency, true);
  renderRevenueEvidence(packageRevenueFlags(pkg.totals || {}), currency);
  renderMonthlyStatements(pkg);
}

/* --- Monthly Statements deposits -----------------------------------------
   Which deposits the package's Monthly Statements table shows, chosen on the Settings page and kept in this browser
   only. Total is everything going in. True is True revenue (5.6): every posted credit except known non-revenue (an
   own-account transfer, lender funding, a refund) and the deposits held for review, with its Verified part beside it. */
const MONTHLY_DEPOSITS_KEY = "bsa-monthly-deposits";
const MONTHLY_DEPOSITS_VIEWS = ["both", "total", "true"];
// The choice made on this page. Storage only carries it to the next visit: where storage is blocked (a private
// window, a policy) the choice still holds for the page.
let monthlyDepositsChoice = null;

function monthlyDepositsView() {
  let value = monthlyDepositsChoice;
  if (value === null) {
    try { value = localStorage.getItem(MONTHLY_DEPOSITS_KEY); } catch (error) { /* private mode */ }
  }
  return MONTHLY_DEPOSITS_VIEWS.includes(value) ? value : "both";
}

// A figure of a statement's month, or null (shown N/A) for a statement that failed: its zeros are the absence of an
// analysis, not a month of nothing. The Monthly Statements table and its chart both read figures through it.
function monthFigure(doc, value) {
  return doc.status === "done" ? value : null;
}

// 5.6 (true revenue spec §10.2): a statement's True deposits (its True revenue), or null — shown N/A — unless the
// package established its revenue: not for a failed statement, nor for one analysed before 5.6, nor for one whose
// captured credits are not all tiered or are not the money its Total counts (webapp/app.py `revenue_established`; a
// payload that does not say reads as not established).
function trueDeposits(doc) {
  return doc.revenue_established === true ? monthFigure(doc, doc.true_revenue_total) : null;
}

function trueDepositCount(doc) {
  return doc.revenue_established === true ? monthFigure(doc, doc.true_revenue_count) : null;
}

// Its Verified part, established on its own condition (`verified_revenue_established`, the tier aside).
function verifiedDeposits(doc) {
  return doc.verified_revenue_established === true ? monthFigure(doc, doc.verified_revenue_total) : null;
}

function totalDeposits(doc) {
  return monthFigure(doc, doc.credits);
}

// The deposit columns, [header, value of a row, kind]: the CRM's own headers when one basis is shown, each basis
// named when both are.
function monthlyDepositColumns(view) {
  const total = [totalDeposits, (doc) => monthFigure(doc, doc.deposit_count)];
  const revenue = [trueDeposits, trueDepositCount];
  if (view === "total") return [["Monthly Deposits ($)", total[0], "amount"], ["Deposits Per Month", total[1], "count"]];
  if (view === "true") {
    return [["Monthly Deposits ($)", revenue[0], "amount"], ["Deposits Per Month", revenue[1], "count"],
      ["Verified ($)", verifiedDeposits, "amount"]];
  }
  return [
    ["Total Deposits ($)", total[0], "amount"], ["Total Deposits Per Month", total[1], "count"],
    ["True Deposits ($)", revenue[0], "amount"], ["True Deposits Per Month", revenue[1], "count"],
    ["Verified ($)", verifiedDeposits, "amount"],
  ];
}

const MONTHLY_DEPOSITS_NOTES = {
  total: "Total monthly deposits: everything going in",
  true: "True monthly deposits: revenue only",
};

function renderMonthlyStatements(pkg) {
  // Audit B11 (I06): a repeated statement left out of the package's figures is no month of its own.
  const documents = countedDocuments(pkg.documents);
  const view = monthlyDepositsView();
  const columns = monthlyDepositColumns(view);
  const currencyInfo = packageCurrencyInfo(pkg);
  renderMonthlyChart(packageMonthRows(documents), currencyInfo.refused || currencyInfo.currencies.length > 1, view);
  if (els.monthlyCard) els.monthlyCard.style.display = "block";
  if (els.monthlyCount) {
    const note = MONTHLY_DEPOSITS_NOTES[view];
    els.monthlyCount.textContent = `${documents.length} ${documents.length === 1 ? "statement" : "statements"}`
      + (note ? ` · ${note}` : "");
  }
  if (els.monthlyHead) {
    els.monthlyHead.innerHTML = `
      <tr>
        <th>Month</th>
        <th>Year</th>
        ${columns.map(([header]) => `<th>${escapeHtml(header)}</th>`).join("")}
        <th>Ledger ($)</th>
        <th>NSF</th>
        <th>Action</th>
      </tr>
    `;
  }
  if (!els.monthlyTable) return;
  if (!documents.length) {
    els.monthlyTable.innerHTML = `
      <tr>
        <td>No statements</td>
        <td>N/A</td>
        ${columns.map(() => "<td>N/A</td>").join("")}
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
          <td class="mono">${escapeHtml(month ? String(month.year) : "N/A")}</td>
          ${columns.map(([, value, kind]) => `<td class="mono">${escapeHtml(kind === "amount" ? amount(value(doc)) : formatWhole(value(doc)))}</td>`).join("")}
          <td class="mono">${escapeHtml(amount(monthFigure(doc, doc.average_daily_balance)))}</td>
          <td class="mono" title="${escapeHtml(nsfSourceLabel(doc.nsf_source))}">${escapeHtml(formatNumber(monthFigure(doc, doc.nsf_count)))}${mixedNsf ? `<div class="table-cell-detail">${escapeHtml(nsfSourceLabel(doc.nsf_source))}</div>` : ""}</td>
          <td><button class="statement-open" type="button" data-job-id="${escapeHtml(doc.id)}" ${doc.status === "done" ? "" : "disabled"}>${status === "Failed" ? "Unavailable" : `Open${OPEN_ICON}`}</button></td>
        </tr>
      `;
    }).join("");
  }
}

// A package row names one account of a multi-account statement `<job>#account_<n>` (webapp/app.py): the statement's
// job, and n, the account in printed order. Any other row is the job alone.
function packageMember(id) {
  const match = /^(.*)#account_(\d+)$/.exec(String(id ?? ""));
  return match ? { jobId: match[1], account: Number(match[2]) } : { jobId: String(id ?? ""), account: null };
}

function openStatementModal(memberId) {
  if (!els.statementModalBackdrop) return;
  // The statement's own job: the server knows no `#account_<n>` (and a `#` in a URL is not sent at all).
  const { jobId, account } = packageMember(memberId);
  modalLastFocus = document.activeElement;
  modalAnalysis = null;
  modalJobId = jobId;
  modalAccount = account;
  modalReviewAccount = null;
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
  if (els.statementModalFlagged) {
    els.statementModalFlagged.innerHTML = `
      <tr>
        <td colspan="5"><strong>Loading</strong></td>
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
    fetch(`/analysis/${encodeURIComponent(jobId)}`).then((response) => {
      if (!response.ok) throw new Error(`Analysis unavailable (${response.status})`);
      return response.json();
    }),
    fetch(`/markdown/${encodeURIComponent(jobId)}`).then((response) => response.ok ? response.text() : ""),
  ])
    .then(([payload, markdown]) => {
      if (!payload.analysis) throw new Error(friendlyAnalysisError(payload.analysis_error));
      // Same rule as `renderAnalysis`: the modal's transaction renderer reads
      // `.statement` off this global, so it holds ONE account's payload (the
      // account of the package row, or the main account of a statement holding
      // several), never the document.
      setModalAnalysis(payload.analysis);
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
      if (els.statementModalFlagged) {
        els.statementModalFlagged.innerHTML = `
          <tr>
            <td colspan="5"><strong>Unable to load statement</strong></td>
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

// Which published account of a statement holding several the statement window shows (0-based, printed order): the
// package row's own when it was opened from one, else the main account.
function modalShownIndex(report) {
  const published = publishedAccounts(report);
  if (modalAccount !== null && published[modalAccount - 1]) return modalAccount - 1;
  return mainAccountIndex(published, accountRoster(report));
}

function modalAccountPayload(report) {
  // The statement modal shows one account: of a statement holding several, the package row's own or the main
  // account; none when the main account (the business checking account) was not verified.
  const roster = accountRoster(report);
  if (unverifiedMainAccount(roster)) return null;
  if (!isDocumentPayload(report)) return report;
  const published = publishedAccounts(report);
  if (!published.length) return null;
  return { ...published[modalShownIndex(report)], parse_mode: report.parse_mode };
}

// The statement window's account payload, and the account its rows' reviews name.
function setModalAnalysis(report) {
  modalAnalysis = modalAccountPayload(report);
  modalReviewAccount = modalAnalysis && isDocumentPayload(report) ? modalShownIndex(report) + 1 : null;
}

function renderStatementModal(jobId, report, markdown) {
  let accountNote = "";
  // Read before an account of the statement stands in for it below: the server sets it at the top of the payload.
  const rulesOutdated = Boolean(report && report.analysis_rules_outdated === true);
  const unverifiedMain = unverifiedMainAccount(accountRoster(report));
  if (unverifiedMain) {
    els.statementModalTitle.textContent = "Main account needs review";
    els.statementModalSubtitle.textContent = `${accountDisplayName({}, unverifiedMain)} could not be verified: `
      + `${accountReasonText(unverifiedMain.reasons)}. No metrics are shown for it.`;
    els.statementModalMetrics.innerHTML = "";
    els.statementModalAccount.innerHTML = "";
    els.statementModalLenders.innerHTML = "";
    els.statementModalInsurance.innerHTML = "";
    els.statementModalFlagged.innerHTML = "";
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
      const index = modalShownIndex(report);
      accountNote = index === mainAccountIndex(publishedAccounts(report), accountRoster(report))
        ? `Main account of ${formatNumber(count)} - `
        : `Account ${formatNumber(index + 1)} of ${formatNumber(count)} - `;
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
    els.statementModalFlagged.innerHTML = "";
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
  const decision = accountDecision(report);

  els.statementModalTitle.textContent = title;
  els.statementModalSubtitle.textContent = `${accountNote}${period(statement)} - ${labelize(decision)}`;
  els.statementModalMetrics.innerHTML = [
    ...revenueCardItems(metrics, currency, {
      established: metrics.revenue_established === true,
      verifiedEstablished: metrics.verified_revenue_established === true,
      unestablishedNote: rulesOutdated ? "Re-analyze to compute true revenue" : "",
      counts: true,
      facts: statementRevenueFacts(metrics),
    }),
    ["Total Credits", formatMoney(metrics.effective_total_deposits, currency), REVENUE_METRIC_COPY.totalCredits, "CR", "neutral"],
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
  if (els.statementModalFlagged) {
    els.statementModalFlagged.innerHTML = flaggedPositionRowsHtml(
      flaggedPositionEntries(detection.flagged_positions), currency, false);
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
  modalAccount = null;
  modalReviewAccount = null;
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
    const counted = countedDocuments(pkg.documents);
    const repeats = duplicateDocuments(pkg.documents).length;
    // Audit B11 (I07): the memo carries True, Verified and Non-revenue, in total and per calendar month, ahead of the
    // gross figures, which are named gross; and the repeated statements left out (I06).
    els.summaryBox.textContent =
      `Package ${packagePeriod(counted)} (${packageSpanLabel(totals, counted.length)}): ` +
      `${formatNumber(totals.completed)} of ${formatNumber(totals.distinct_documents ?? totals.documents)} statements completed` +
      (repeats ? `, ${formatNumber(repeats)} repeated ${repeats === 1 ? "statement" : "statements"} left out` : "") + ". " +
      `${revenueSummarySentence(totals, currency, packageRevenueFlags(totals), {
        trueMonthly: totals.avg_monthly_true_revenue,
        verifiedMonthly: totals.avg_monthly_verified_revenue,
        nonRevenueMonthly: totals.avg_monthly_non_revenue,
      })} ` +
      `${formatMoney(totals.avg_monthly_credits, currency)} average monthly gross credits, ${formatMoney(totals.avg_monthly_cash_flow, currency)} average monthly cash flow, ` +
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
  // Likewise when the main account was not verified and another, verified, account was picked (All accounts).
  const unverifiedNote = idleNote ? "" : unverifiedMainNote(currentDocument, currency);
  const decision = idleNote || unverifiedNote || hasMaterialPotentialLenderDebits(m)
    ? "review_required"
    : q.corporate_use || q.level || "review_required";
  const lead = idleNote ? `${idleNote}Figures for the active account, ${accountDisplayName(s, null)}: `
    : unverifiedNote ? `${unverifiedNote}Figures for the selected account, ${accountDisplayName(s, null)}: ` : "";
  // Audit B11 (I07): the statement stands for one calendar month (the Monthly Statements rule), so its monthly figures
  // are its totals.
  const established = { established: m.revenue_established === true,
    verifiedEstablished: m.verified_revenue_established === true };
  els.summaryBox.textContent =
    lead +
    `${s.bank || "Statement"} ${period(s)}: ` +
    `${revenueSummarySentence(m, currency, established, {
      trueMonthly: m.true_revenue_total, verifiedMonthly: m.verified_revenue_total, nonRevenueMonthly: m.non_revenue_total,
    })} ` +
    `Average daily balance ${formatMoney(m.average_daily_balance, currency)}, ` +
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
  // A statement whose main account was not verified is open too: it shows its accounts (currentDocument), not one.
  const openStatement = Boolean((currentAnalysis && !currentAnalysis.package) || currentDocument);
  if (target === "review") {
    if (!currentAnalysis) {
      showResultsEmpty("review");
      return;
    }
    revealOpenAnalysis("review");
    // 5.6 (true revenue spec §10.7): what needs review now is the held credits. An analysis saved before 5.6 carries no
    // tier: its review opens on the deposits it left unverified, reviewed under its own rules (T10).
    showMainRevenueEvidence(ledgerCarriesNoTier(mainTransactionContext().transactions)
      ? OLDER_REVIEW_FILTER : "excluded_pending_review");
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
// The Recent entry of the analysis open now (its key), marked in the sidebar; null while nothing is open, as when
// an upload is under way.
let openAnalysisKey = null;

// A new analysis goes on top. One already listed (a reopen, a settings refresh, a review decision) is updated where
// it stands, so the list never reshuffles under the pointer and the mark moves to the entry that was clicked.
function rememberAnalysis(entry) {
  const index = recentAnalyses.findIndex((item) => item.key === entry.key);
  recentAnalyses = index >= 0
    ? recentAnalyses.map((item, position) => (position === index ? entry : item))
    : [entry, ...recentAnalyses].slice(0, RECENT_LIMIT);
  try { sessionStorage.setItem(RECENT_KEY, JSON.stringify(recentAnalyses)); } catch { /* storage unavailable */ }
  renderRecentAnalyses();
}

function setOpenAnalysis(key) {
  openAnalysisKey = key;
  renderRecentAnalyses();
}

function decisionDotTone(decision) {
  if (decision === "approved") return "green";
  if (decision === "error" || decision === "failed") return "red";
  return "amber";
}

function rememberStatement(jobId, report, tone = decisionDotTone(els.decisionPill.classList[1])) {
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
    tone,
  });
}

// The statement a multi-account document came from, by its period and bank only: no account's type or number.
function documentLabelReport(doc) {
  const first = (publishedAccounts(doc)[0] || {}).statement || {};
  return { statement: { bank: first.bank, period_start: first.period_start, period_end: first.period_end } };
}

// The Recent entry of the statement on screen. One that holds several accounts is named after the statement and
// carries the statement's own dot (review when its main account was not verified or had no activity, else its main
// account's decision): neither follows the account picked on screen, which a refresh or a revenue decision would
// otherwise record.
function rememberShownStatement(jobId) {
  if (!currentDocument) {
    if (currentAnalysis) rememberStatement(jobId, currentAnalysis);
    return;
  }
  const roster = accountRoster(currentDocument);
  const published = publishedAccounts(currentDocument);
  const main = published[mainAccountIndex(published, roster)];
  const needsReview = unverifiedMainAccount(roster) || idleMainAccount(roster) || !main;
  rememberStatement(jobId, documentLabelReport(currentDocument),
    needsReview ? "amber" : decisionDotTone(accountDecision(main)));
}

// A statement that opens no results page (a held read, a statement contradiction) is still one the sidebar reopens:
// it keeps the name it was listed under, or takes its file's name, and its dot says fail or review.
function rememberHeldStatement(jobId, message) {
  const listed = recentAnalyses.find((item) => item.key === jobId);
  rememberAnalysis({
    kind: "statement",
    key: jobId,
    ids: [jobId],
    label: listed ? listed.label : (currentFile && currentFile.name) || "Statement",
    meta: listed ? listed.meta : "",
    tone: sourceContradiction(message) ? "red" : "amber",
  });
}

function rememberPackage(jobIds, pkg) {
  const documents = countedDocuments(pkg.documents);
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
  const open = item.key === openAnalysisKey;
  return `
    <button class="side-link recent-item${open ? " active" : ""}" type="button" data-recent-key="${escapeHtml(item.key)}"
            title="${escapeHtml(item.label)}"${open ? ` aria-current="true"` : ""}>
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
  // The account chosen on another statement is not one of this statement's accounts.
  selectedAccountIndex = null;
  // A reopen that fails (the job is gone, the server is unreachable) must not leave the page pointing at
  // it: the analysis still on screen gets its own ids back, and the failure is reported beside it.
  const onError = (message) => {
    if (currentJobIds.join(",") !== item.ids.join(",")) return;  // something newer was opened meanwhile
    // A statement whose main account was not verified shows no account (currentAnalysis) but is on screen.
    if ((!currentAnalysis && !currentDocument) || !shownAnalysis) {
      renderError(message);
      return;
    }
    ({ jobId: currentJobId, files: currentFiles, file: currentFile, startedAt, selectedAccountIndex } = shownAnalysis);
    currentJobIds = shownAnalysis.jobIds.slice();
    // The filter was reset for the reopen; the ledger on screen is redrawn to match its buttons.
    renderMainTransactions();
    notify(`Could not reopen ${item.label}: ${message}`, "red");
    revealOpenAnalysis(currentAnalysis && currentAnalysis.package ? "packages" : "results");
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
  renderFlagSettings(flagSettingsSaved, true);
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
      flagSettingsSaved = settings;
      // A switch still being saved keeps the group held; its own save draws the group again when it settles.
      renderFlagSettings(settings, flagSettingsBusy);
      if (!flagSettingsBusy) setFlagSettingsStatus("");
    })
    .catch((error) => {
      setSettingsStatus(error.message || String(error), true);
      setFlagSettingsStatus(error.message || String(error), true);
    });
}

function refreshShownResults() {
  // A setting changes how a result is presented, so whatever is open is fetched again, in place. A statement whose
  // main account was not verified shows no account (currentAnalysis is null) but keeps its accounts
  // (currentDocument), and selecting one later renders from that copy, so it is fetched again too.
  if (currentJobIds.length > 1) loadPackage(currentJobIds, { reveal: false });
  else if (currentJobId && (currentAnalysis || currentDocument)) loadResults(currentJobId, { reveal: false });
}

/* Flagged positions: one switch per group (FLAG_GROUP_LABELS), each its own settings key, flag_<group>, on by default.
   The server applies them when it serves an analysis; a switch only hides or shows its group. */
let flagSettingsSaved = {};
let flagSettingsBusy = false;

function flagSettingKey(group) {
  return `flag_${group}`;
}

// A key the settings lack (a server older than the flags) reads as on, the default.
function renderFlagSettings(settings = {}, disabled = false) {
  if (!els.flagSettingsList) return;
  els.flagSettingsList.innerHTML = Object.entries(FLAG_GROUP_LABELS).map(([group, label]) => {
    const key = flagSettingKey(group);
    const id = `flagSetting-${group}`;
    return `
      <div class="setting-row">
        <label class="setting-title" for="${id}">${escapeHtml(label)}</label>
        <span class="switch">
          <input type="checkbox" role="switch" id="${id}" data-flag-setting="${key}" aria-describedby="flagSettingsHelp"${
            settings[key] === false ? "" : " checked"}${disabled ? " disabled" : ""}>
          <span class="switch-track" aria-hidden="true"></span>
        </span>
      </div>
    `;
  }).join("");
}

function setFlagSettingsStatus(message, error = false) {
  if (!els.flagSettingsStatus) return;
  els.flagSettingsStatus.textContent = message;
  if (error) els.flagSettingsStatus.setAttribute("data-state", "error");
  else els.flagSettingsStatus.removeAttribute("data-state");
}

// The ledger filtered to one flagged payee (a Flagged positions panel click) shows every row again once that payee's
// group is unticked: its rows are no longer flagged, so the filter would match none.
function releaseFlagFilter(group) {
  if (flaggedFilterGroup(transactionFilter) !== group) return;
  transactionFilter = "all";
  transactionEntityFilter = null;
  setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
}

function flagGroupOfSetting(key) {
  const group = String(key || "").replace(/^flag_/, "");
  return ownKey(FLAG_GROUP_LABELS, group) ? group : null;
}

// Saves one switch: that key alone (the server merges it), with the whole group held until the answer, so two quick
// changes never race two refreshes. The open statement or package is fetched again, as the server now serves it.
function saveFlagSetting(key, wanted) {
  const group = flagGroupOfSetting(key);
  if (!group || flagSettingsBusy) return;
  flagSettingsBusy = true;
  renderFlagSettings({ ...flagSettingsSaved, [key]: wanted }, true);
  setFlagSettingsStatus("Saving...");
  fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ [key]: wanted }),
  })
    .then((response) => responseJson(response).then((payload) => ({ response, payload })))
    .then(({ response, payload }) => {
      if (!response.ok || !payload.settings) throw new Error(payload.error || `Save failed (${response.status})`);
      flagSettingsSaved = payload.settings;
      const shown = payload.settings[key] !== false;
      setFlagSettingsStatus(`Saved. ${flagGroupLabel(group)}: ${shown ? "flagged" : "no longer flagged"}.`);
      if (!shown) releaseFlagFilter(group);
      refreshShownResults();
    })
    .catch((error) => {
      setFlagSettingsStatus(error.message || String(error), true);
    })
    .finally(() => {
      flagSettingsBusy = false;
      // Drawn from what the server holds, so a refused save puts the switch back.
      renderFlagSettings(flagSettingsSaved, false);
      document.getElementById(`flagSetting-${group}`)?.focus();
    });
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

els.flagSettingsList?.addEventListener("change", (event) => {
  const box = event.target instanceof Element ? event.target.closest("[data-flag-setting]") : null;
  if (box) saveFlagSetting(box.getAttribute("data-flag-setting"), box.checked === true);
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
// A statement whose main account was not verified has no account on screen: its data is the whole statement, and
// its summary is the explanation its view wrote (generateSummary leaves it).
els.copyDataBtn.addEventListener("click", () => copyText(JSON.stringify(currentAnalysis || currentDocument || {}, null, 2)));
els.summaryBtn.addEventListener("click", () => {
  generateSummary();
  if ((!currentAnalysis && !currentDocument) || !els.summaryPanel) return;
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
  const account = button.getAttribute("data-revenue-review-account");
  // While the multi-select's batch is being saved, a row's own decision waits: both would start from one analysis.
  // While the statement is re-analyzed it waits too: the row it names is about to be replaced.
  if (!jobId || !sourceLocation || !decision || bulkBusy || reanalysisBusy) return;
  button.disabled = true;
  rowReviewsInFlight += 1;
  syncBulkReview();
  let saved = null;
  try {
    const response = await fetch(`/analysis/${encodeURIComponent(jobId)}/revenue-review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(account === null ? { source_location: sourceLocation, decision }
        : { source_location: sourceLocation, decision, account: Number(account) }),
    });
    const payload = await responseJson(response);
    if (!response.ok || !payload.analysis) {
      throw new Error(payload.error || `Revenue review failed (${response.status})`);
    }
    saved = { jobId, analysis: payload.analysis };
    if (modalJobId === jobId) {
      // The refresh path, held to the same rule as the open path above.
      setModalAnalysis(payload.analysis);
      renderStatementModal(jobId, payload.analysis, "");
    }
    await redrawAfterReview(saved);
  } catch (error) {
    // A decision saved but not drawn keeps its button held: pressed again, it would record the decision twice.
    if (!saved) button.disabled = false;
    const message = error.message || String(error);
    window.alert(saved ? `Saved, but ${message}: open the statements again to see the decision` : message);
  } finally {
    rowReviewsInFlight -= 1;
    syncBulkReview();
  }
}

function handleRevenueReviewClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  const button = target ? target.closest("[data-revenue-review-action]") : null;
  if (button) submitRevenueReview(button);
}

els.transactionTable?.addEventListener("click", handleRevenueReviewClick);
els.statementModalTransactions?.addEventListener("click", handleRevenueReviewClick);

els.transactionTable?.addEventListener("change", (event) => {
  const box = event.target instanceof Element ? event.target.closest("input[data-bulk-job]") : null;
  if (!box) return;
  pickDeposit(box, box.checked);
  syncBulkReview();
});
els.bulkSelectAll?.addEventListener("change", () => {
  // Every deposit shown on this page of rows that awaits review (the selection is only ever what is shown).
  bulkBoxes().forEach((box) => pickDeposit(box, els.bulkSelectAll.checked));
  syncBulkReview();
});
els.bulkReviewBar?.addEventListener("click", (event) => {
  const button = event.target instanceof Element ? event.target.closest("[data-bulk-review]") : null;
  if (!button || button.disabled) return;
  const action = button.getAttribute("data-bulk-review");
  if (action === "clear") clearBulkSelection({ refocus: true });
  else submitBulkReview(action);
});

/* --- re-analysis of a saved statement ---------------------------------------
   The Re-analyze button of the outdated-rules notice (#reanalyzeButton; the results page draws the notice and decides
   when it shows) runs the statement on screen again under the current rules. POST /analysis/<job>/reanalyze replaces
   its saved analysis in place (the same statement, in the same place in Recent) and answers with the new one, so the
   page is drawn again from the answer. The analyst's revenue decisions come back where their row is unchanged; the
   notification says how many need redoing and how many a rule of the current analysis now decides. While it runs,
   every review waits (reanalysisBusy, declared beside bulkBusy). */
function reviewsLabel(count) {
  return `${formatNumber(count)} ${count === 1 ? "review" : "reviews"}`;
}

// [text, tone] of the notification a finished re-analysis leaves. A review that needs redoing, or that a rule now
// decides in the analyst's place, is news the analyst must see: amber, and the notifications open on it.
function reanalysisNotice(payload) {
  const kept = Number(payload.reviews_replayed) || 0;
  const redo = Number(payload.reviews_not_replayed) || 0;
  const ruled = Number(payload.reviews_decided_by_rules) || 0;
  const done = "Re-analyzed with the current rules";
  const news = [];
  if (redo) news.push(`${reviewsLabel(redo)} ${redo === 1 ? "needs" : "need"} redoing`);
  if (ruled) news.push(`${reviewsLabel(ruled)} ${ruled === 1 ? "is" : "are"} now decided by the rules`);
  if (news.length) return [`${done}; ${news.join("; ")}`, "amber"];
  return [kept ? `${done}; ${reviewsLabel(kept)} kept` : done, "green"];
}

async function reanalyzeShownStatement() {
  const jobId = currentJobId;
  // One statement on screen, and none of its decisions being saved: the answer would be drawn over them.
  if (reanalysisBusy || bulkBusy || rowReviewsInFlight > 0 || !jobId || currentJobIds.length > 1) return;
  reanalysisBusy = true;
  const button = document.getElementById("reanalyzeButton");
  const label = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = "Re-analyzing...";
  }
  // Every review waits for the answer: the bar's buttons and the rows' own are held.
  syncBulkReview();
  holdRowReviews(true);
  let saved = false;
  try {
    const response = await fetch(`/analysis/${encodeURIComponent(jobId)}/reanalyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const payload = await responseJson(response);
    if (!response.ok || !payload.analysis) {
      const reason = payload.reason ? ` (${payload.reason})` : "";
      throw new Error(payload.error ? `${payload.error}${reason}` : `status ${response.status}`);
    }
    saved = true;
    if (currentJobId === jobId && currentJobIds.length <= 1) {
      // The rows were read afresh: a tick made on the old rows could name another posting now.
      clearBulkSelection();
      renderAnalysis(payload.analysis);
      setActions(jobId, true);
      if (currentAnalysis || currentDocument) rememberShownStatement(jobId);
      else appendStatusExports(`/download/${encodeURIComponent(jobId)}`);
    }
    const [text, tone] = reanalysisNotice(payload);
    notify(text, tone);
    if (tone !== "green") showNotifications();
  } catch (error) {
    const message = error.message || String(error);
    notify(saved ? `Re-analyzed, but ${message}: open the statement again to see it` : `Not re-analyzed: ${message}`,
      "red");
    showNotifications();
  } finally {
    reanalysisBusy = false;
    // No batch and no row's decision can have started meanwhile (their guards read reanalysisBusy), so every review
    // button is given back.
    holdRowReviews(false);
    syncBulkReview();
    if (button) {
      button.disabled = false;
      button.textContent = label;
    }
  }
}

document.getElementById("reanalyzeButton")?.addEventListener("click", () => { reanalyzeShownStatement(); });

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

// A payee of the Flagged positions panel shows the ledger rows behind it.
if (els.flaggedTable) {
  els.flaggedTable.addEventListener("click", (event) => {
    const selection = lenderEvidenceSelection(event);
    if (!selection) return;
    transactionFilter = selection.filter;
    transactionEntityFilter = selection.entity;
    setTransactionFilterButtons("[data-transaction-filter]", "flagged");
    renderMainTransactions();
    els.transactionCard?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}
if (els.statementModalFlagged) {
  els.statementModalFlagged.addEventListener("click", (event) => {
    const selection = lenderEvidenceSelection(event);
    if (!selection) return;
    modalTransactionFilter = selection.filter;
    modalTransactionEntityFilter = selection.entity;
    setTransactionFilterButtons("[data-modal-transaction-filter]", "flagged");
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
}

function setAllAccountsView(on) {
  allAccountsChoice = Boolean(on);
  try { localStorage.setItem(ALL_ACCOUNTS_KEY, on ? "on" : "off"); } catch (error) { /* private mode: held for this page */ }
  syncAllAccountsToggle();
  // Only a statement on screen is redrawn: never a package, never a statement still processing.
  const statementShown = currentDocument && !(currentAnalysis && currentAnalysis.package) && currentJobIds.length <= 1;
  if (statementShown) {
    renderAnalysis(currentDocument);
    noteShownSelection();
  }
}

els.allAccountsToggle?.addEventListener("change", () => setAllAccountsView(els.allAccountsToggle.checked));
syncAllAccountsToggle();

function setMonthlyDepositsView(view) {
  const next = MONTHLY_DEPOSITS_VIEWS.includes(view) ? view : "both";
  monthlyDepositsChoice = next;
  try { localStorage.setItem(MONTHLY_DEPOSITS_KEY, next); } catch (error) { /* private mode: held for this page */ }
  if (els.monthlyDepositsView) els.monthlyDepositsView.value = next;
  // Only a package has the table and its chart: the one on screen is redrawn from the figures it already holds.
  if (currentAnalysis && currentAnalysis.package) renderMonthlyStatements(currentAnalysis.package);
}

els.monthlyDepositsView?.addEventListener("change", () => setMonthlyDepositsView(els.monthlyDepositsView.value));
if (els.monthlyDepositsView) els.monthlyDepositsView.value = monthlyDepositsView();

// The account on screen is part of what a failed reopen puts back (openRecent), so the record follows every
// selection made after the statement finished loading, and only for the statement that record describes.
function noteShownSelection() {
  if (shownAnalysis && shownAnalysis.jobId === currentJobId) shownAnalysis.selectedAccountIndex = selectedAccountIndex;
}

function selectAccountFrom(event) {
  const target = event.target instanceof Element ? event.target : null;
  const row = target ? target.closest("tr[data-account-index]") : null;
  if (!row || !currentDocument) return;
  const index = Number(row.getAttribute("data-account-index"));
  if (!Number.isInteger(index) || index === selectedAccountIndex) return;
  selectedAccountIndex = index;
  renderAnalysis(currentDocument);
  noteShownSelection();
  els.accountsPanel?.querySelector(`tr[data-account-index="${index}"]`)?.focus();
}

els.accountsPanel?.addEventListener("click", selectAccountFrom);
els.accountsPanel?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  // Only an account row is selected from the keyboard; any other control in the panel (the link to Settings)
  // keeps its own Enter and Space.
  const target = event.target instanceof Element ? event.target : null;
  if (!target || !target.closest("tr[data-account-index]")) return;
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
renderFlagSettings({}, true);
renderRecentAnalyses();
renderPreview();
showView("new");
syncPanelToggle();
setTransactionFilterButtons("[data-transaction-filter]", transactionFilter);
setTransactionFilterButtons("[data-transaction-sort]", transactionSort);
setTransactionFilterButtons("[data-modal-transaction-filter]", modalTransactionFilter);
setTransactionFilterButtons("[data-modal-transaction-sort]", modalTransactionSort);
setActions(null, false);
