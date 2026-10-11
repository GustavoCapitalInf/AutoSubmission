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
  // The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): "Mark Zelle Payments as True Revenue".
  zelleTrueRevenueYes: document.getElementById("zelleTrueRevenueYes"),
  zelleTrueRevenueNo: document.getElementById("zelleTrueRevenueNo"),
  zelleSettingStatus: document.getElementById("zelleSettingStatus"),
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
  // Audit round 2, R2-B15 (R15): the accounts a package left out of every figure for another reason than a repeat.
  excludedNotice: document.getElementById("excludedNotice"),
  excludedNoticeText: document.getElementById("excludedNoticeText"),
  // Owner ruling 2026-10-02 (the underwriter's Q6; R2-OW15): what the package passes matched across its statements.
  packageMatchNotice: document.getElementById("packageMatchNotice"),
  packageMatchNoticeText: document.getElementById("packageMatchNoticeText"),
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
// Audit round 2, R2-B14 (R16): once this batch's package arrives, the rows it left out of its figures (job id -> the
// job kept in their place); null until then.
let queuePackageDuplicates = null;
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
  // R2-OW03 (owner ruling 2026-10-02, the underwriter's Q3): the note names the Zelle deposits the policy excludes.
  nonRevenue: "Own-account transfers, funding, refunds and other known non-revenue, Zelle deposits included",
  // Audit B11 (I51): where revenue is not established, Non-Revenue is a figure of the captured rows only.
  nonRevenueCaptured: "Captured rows only: own-account transfers, funding, refunds and other known non-revenue, Zelle deposits included",
  achCredits: "Posted ACH credit transactions",
});

// Audit B11 (I34, copy only; the basis is the owner's): the legacy withholding denominator is gross deposits less
// lender funding, never True revenue.
const LEGACY_ELIGIBLE_DEPOSITS_NOTE = "Gross deposits less lender funding (not True revenue)";
// Owner ruling 2026-10-02 (the underwriter's Q7, audit I34; true revenue spec §10.1, §10.5, §11; R2-OW14): True revenue
// is the default withholding basis; the legacy and verified bases stay selectable. Each basis's label and definition,
// for a payload that carries its mode but not its words.
const WITHHOLDING_BASIS_LABELS = Object.freeze({
  legacy_eligible_deposits: "Legacy eligible deposits",
  verified_revenue: "Verified revenue",
  true_revenue: "True revenue",
});
// Audit round 3, R3-B03 (R3-20; true revenue spec §10.1, §11): a True or Verified withholding basis under this many
// units of the statement's own currency publishes no rate (analysis/revenue.py WITHHOLDING_BASIS_FLOOR, which a test
// pins equal to this mirror). The note names the floor; nothing that decides a review reads it.
const WITHHOLDING_BASIS_FLOOR = 500;
// Audit round 3, final review (R3-FF), F6: the large unsourced deposits' floor, compared in the statement's own unit
// (analysis/revenue_view.py LARGE_UNSOURCED_DEPOSIT_FLOOR, which a test pins equal to this mirror); largeDepositFacts
// writes it in that unit, never "$" on a CAD statement.
const LARGE_UNSOURCED_DEPOSIT_FLOOR = 10000;
const WITHHOLDING_BASIS_DEFINITIONS = Object.freeze({
  verified_revenue: "verified classified revenue",
  true_revenue: "verified plus counted credits",
});
const DEFAULT_WITHHOLDING_BASIS_NOTE = "True revenue by default: verified plus counted credits";

// 5.6 (true revenue spec §5.3, §10.6): the reason codes of the two middle tiers, code -> [tier, label, sentence], and
// (the owner's rulings of 2026-10-02) the non_revenue codes: the Zelle policy's and Q12's display reason (R2-OW03), and
// Q11's non-dealer asset sales (R2-OW06). It
// mirrors analysis/revenue.py REVENUE_TIER_REASONS (code -> tier and label); tests/test_webapp_true_revenue_ui.py holds
// the two equal. The sentence is the ledger's one line on the code.
const REVENUE_TIER_REASONS = Object.freeze({
  direction_conflict: ["excluded_pending_review", "Direction conflicts with the amount", "The bank prints this row in the other direction from its amount."],
  insurer_payer: ["excluded_pending_review", "Insurance carrier", "An insurance carrier paid it: a claim or a refund unless you confirm it pays for a sale."],
  insurer_named_payer: ["excluded_pending_review", "Payer name reads as an insurer", "The payer's name reads as an insurer."],
  possible_return: ["excluded_pending_review", "Possible return or adjustment", "The row reads as a return, a reversal or an adjustment of an earlier item."],
  financing_named_payer: ["excluded_pending_review", "Payer or entry suggests financing", "The payer or the entry names funding, a loan or an advance."],
  // Owner ruling 2026-10-02 (Q8): a lease-to-own or patient financier's one-off lump sum, held until sourced.
  customer_financing_lump_sum: ["excluded_pending_review", "One-off lump sum from a lease-to-own or patient financier", "A lease-to-own or patient-financing company paid a one-off lump sum ($10,000 or more; by wire, in whole thousands or half the statement's credits; not one of three or more payouts of its size): held until its source is confirmed."],
  unread_run_names_financing: ["excluded_pending_review", "A lender is printed among this credit's unread payer blocks", "The statement prints a lender's or a lending bank's block among payer blocks the reader could not attribute to one row: held until you confirm whose credit this is."],
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
  // Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: a deposit a rule verified or counted, into an account
  // titled as an insurance premium trust account; the end of the held group.
  premium_trust_account: ["excluded_pending_review", "Deposit into a premium trust account", "The account is titled as an insurance premium trust account: its deposits are insureds' premiums held for the carriers, not the agency's revenue. Only commissions paid to the operating account count."],
  // Owner ruling 2026-10-02 (the underwriter's Q4), R2-OW16: within a package, a deposit that prints no payer matched to
  // a transfer out of another of the business's accounts; package-only, the end of the held group.
  own_account_transfer_matched: ["excluded_pending_review", "Matches a transfer out of another account in this package", "A deposit that prints no payer, of the same cents as a transfer out of another of the business's accounts 0 to 2 days before it: the business's own money moving between its accounts, held so it is not counted twice. Confirm Revenue releases it into True and marks it Verified."],
  wire_named_sender: ["counted_flagged", "Wire from a named sender", "A wire from a named sender, counted without proof of the sale."],
  check_deposit: ["counted_flagged", "Check deposit", "A check deposit: the payer is not printed."],
  no_payer_printed: ["counted_flagged", "No payer printed", "A cash, branch, ATM or bare deposit: no payer is printed."],
  payer_text_not_read: ["counted_flagged", "Payer text not read", "The statement prints a payer for this row that the reader could not read: counted without proof of the sale."],
  p2p: ["counted_flagged", "Person-to-person", "A person-to-person payment."],
  factoring_payout: ["counted_flagged", "Factoring payout", "A factor's payout of the business's own invoices."],
  // Owner ruling 2026-10-02 (the underwriter's Q9, part (c)), R2-OW05: a lender paying for services, never verified.
  lender_paid_for_services: ["counted_flagged", "Lender paid for services", "A lender paid the business for its services (a repair, a recovery, a commission): counted, never verified."],
  // Owner ruling 2026-10-02 (the underwriter's Q11 (a)), R2-OW06: a builder's progress draw, never verified.
  construction_progress_draw: ["counted_flagged", "Builder's progress draw", "A builder paid the business a progress draw for its work: counted, never verified."],
  // Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08: an insurer paying for the business's work, never verified.
  insurer_paid_for_services: ["counted_flagged", "Insurer paid for the business's work", "An insurer paid the business for its work: a repair, a commission, or claims it billed. Counted, never Verified. Check it is not a claim on the business's own policy."],
  // Owner ruling 2026-10-02 (the underwriter's Q9 (a), (b)), R2-OW09: released from the financing-name hold, never verified.
  finance_named_customer: ["counted_flagged", "Customer with a finance word in its name, paying an invoice", "A customer whose name carries a finance word paid an invoice or a vendor payment, and no debit names it: counted, never verified."],
  lessor_rent: ["counted_flagged", "Rent received by a leasing or property business", "A tenant paid lease rent to a leasing or property business, and no debit names the payer: counted, never verified."],
  payout_credit_entity: ["counted_flagged", "BNPL or marketplace settlement (payer also lends)", "A buy-now-pay-later or marketplace settlement of the business's own sales, counted; the payer also lends."],
  // Owner ruling 2026-10-02 (Q8): a lease-to-own or patient financier's merchant payout, counted, never verified.
  customer_financing_payout: ["counted_flagged", "Lease-to-own or patient-financing payout", "A lease-to-own or patient-financing company paid the business for a customer's financed purchase: counted, never verified."],
  platform_unconfirmed: ["counted_flagged", "Platform payout, not confirmed", "A registered platform's payout without the context that confirms it."],
  numbered_company_payer: ["counted_flagged", "Numbered company payer", "A numbered company paid it: counted, never verified."],
  named_payer_purpose_refused: ["counted_flagged", "Named payer, purpose not accepted as proof", "A named payer whose printed purpose is not accepted as proof."],
  named_payer_one_off: ["counted_flagged", "One-off payer", "A named payer seen once on this statement."],
  named_payer_unlabelled: ["counted_flagged", "Payer named, channel not printed", "A named payer on a channel the bank does not print."],
  // The owner's rulings of 2026-10-02: the non_revenue codes (true revenue spec §5.3), the underwriter's Q3's Zelle
  // policy, then Q12's display reason (R2-OW03).
  zelle_excluded: ["non_revenue", "Zelle deposit (excluded by policy)", "A Zelle deposit, excluded from true revenue by policy; confirm it if this business takes customer payments by Zelle."],
  government_no_purpose: ["non_revenue", "Government payment, no purpose printed", "A government payment that prints no purpose (MN State MMB, the VA's 36 TREAS 310 MISC PAY, Wisconsin DCF WIDCF DD, BC provincial payment, WSIB, Gouv. Quebec MSP, North Dakota Workforce Safety): excluded by the owner's ruling of 2026-10-02 (Q12)."],
  // The owner's ruling of 2026-10-02 (the underwriter's Q11 (b)), R2-OW06: a non-dealer's asset sale, no review path.
  asset_sale_proceeds: ["non_revenue", "Sale of equipment or vehicles (not a dealer)", "An equipment auction's or a car buyer's seller payout, or a printed sale of a truck, trailer, vehicle or equipment, on a statement that shows no dealer: excluded (owner ruling of 2026-10-02, Q11)."],
});

// R2-OW03 (true revenue spec §10.7; the underwriter's Q3, "I can review"): the non_revenue codes the underwriter may
// confirm back into revenue. It mirrors analysis/revenue.py REVIEWABLE_NON_REVENUE_REASONS.
const REVIEWABLE_NON_REVENUE_REASONS = Object.freeze(["zelle_excluded"]);

function revenueReasonLabel(record) {
  const entry = REVENUE_TIER_REASONS[record && record.revenue_tier_reason];
  return entry ? entry[1] : "Reason not recorded";
}

// R2-OW03 (§5.3): whether a reason code is one REVENUE_TIER_REASONS files under non_revenue (the non-revenue
// breakdown's codes). A reviewer's rejection keeps its counted or held code, which is none.
function nonRevenueReason(code) {
  const entry = REVENUE_TIER_REASONS[code];
  return Boolean(entry) && entry[0] === "non_revenue";
}

// R2-OW03 (the underwriter's Q3): the Zelle deposits the owner's policy excluded, {count, total} (the total null where a
// package refuses its currencies), or null when none were.
function zelleExcluded(source = {}) {
  const byReason = source && source.non_revenue_by_reason;
  const slot = byReason && typeof byReason === "object" ? byReason.zelle_excluded : null;
  const count = numberOrNull(slot && slot.count);
  return count ? { count, total: numberOrNull(slot.total) } : null;
}

// The True card's fact: "Zelle deposits excluded: <money> (<n>)", or the count alone when the money is refused.
function zelleExcludedFact(source, currency) {
  const zelle = zelleExcluded(source);
  if (!zelle) return null;
  return zelle.total === null
    ? `Zelle deposits excluded: ${formatNumber(zelle.count)}`
    : `Zelle deposits excluded: ${formatMoney(zelle.total, currency)} (${formatNumber(zelle.count)})`;
}

// The owner's amendment of 2026-10-06 to the underwriter's Q3 (true revenue spec §10.1, §10.2, §10.5; R2-OW17): the
// served Zelle figures (a statement's metrics.zelle_deposits, a package's totals or a member row's), in the parts every
// surface prints: in True (verified plus counted), held, out (non-revenue), and the verified and counted parts apart.
// Each part is {count, total}, its total null where the package refuses its currencies. Null where the payload carries
// no figures: the display is then today's (the exclusion, read from non_revenue_by_reason).
function zelleDeposits(source = {}) {
  const figures = source && source.zelle_deposits;
  if (!figures || typeof figures !== "object") return null;
  const byTier = figures.by_tier && typeof figures.by_tier === "object" ? figures.by_tier : {};
  const refused = figures.total === null;
  const part = (...tiers) => {
    const slots = tiers.map((tier) => byTier[tier]).filter((slot) => slot && typeof slot === "object");
    const count = slots.reduce((sum, slot) => sum + (numberOrNull(slot.count) || 0), 0);
    if (refused || slots.some((slot) => numberOrNull(slot.total) === null)) return { count, total: null };
    return { count, total: Math.round(slots.reduce((sum, slot) => sum + numberOrNull(slot.total), 0) * 100) / 100 };
  };
  return {
    counted: figures.counted_as_true_revenue === true,
    applied: figures.setting_applied !== false,
    count: numberOrNull(figures.count) || 0,
    // Audit round 3, R3-B20 (R3-48): the captured Zelle rows' total, null where the package refuses its currencies.
    total: numberOrNull(figures.total),
    inTrue: part("verified", "counted_flagged"),
    verified: part("verified"),
    countedFlagged: part("counted_flagged"),
    held: part("excluded_pending_review"),
    out: part("non_revenue"),
  };
}

// The True card's Zelle fact (R2-OW17), every non-zero part, the count alone where the money is refused. Yes: "Zelle
// deposits in True revenue: $C (n)" always, then the held and non-revenue parts; No: "Zelle deposits excluded: $N (k)"
// then the parts a review or an older analysis left counted or held. A statement or a package member analysed before the
// setting says it is shown as analysed. Without served figures, today's fact. Audit round 3, R3-B20 (R3-48; §10.4's
// I51): where the revenue is not `established`, the captured rows only: "Zelle deposits captured: $T (n), captured rows
// only", then the non-revenue part where there is some, never a part in True revenue, counted or held.
function zelleFact(source, currency, { package: isPackage = false, established = true } = {}) {
  const zelle = zelleDeposits(source);
  if (!zelle) return zelleExcludedFact(source, currency);
  const money = (part) => (part.total === null ? formatNumber(part.count)
    : `${formatMoney(part.total, currency)} (${formatNumber(part.count)})`);
  const parts = [];
  if (established === false) {
    parts.push(`Zelle deposits captured: ${money({ count: zelle.count, total: zelle.total })}, captured rows only`);
    if (zelle.out.count > 0) parts.push(`non-revenue: ${money(zelle.out)}`);
  } else if (zelle.counted) {
    parts.push(`Zelle deposits in True revenue: ${money(zelle.inTrue)}`);
    if (zelle.held.count > 0) parts.push(`held for review: ${money(zelle.held)}`);
    if (zelle.out.count > 0) parts.push(`non-revenue: ${money(zelle.out)}`);
  } else {
    parts.push(`Zelle deposits excluded: ${money(zelle.out)}`);
    if (zelle.verified.count > 0) parts.push(`counted after review: ${money(zelle.verified)}`);
    if (zelle.countedFlagged.count > 0) parts.push(`counted: ${money(zelle.countedFlagged)}`);
    if (zelle.held.count > 0) parts.push(`held for review: ${money(zelle.held)}`);
  }
  if (!zelle.applied) {
    parts.push(isPackage ? "a statement analysed before the Zelle setting is shown as analysed"
      : "analysed before the Zelle setting: shown as analysed");
  }
  return parts.join(" · ");
}

// R2-OW17 (§10.5): whether the served account or package says its Zelle deposits count in True revenue (Yes, with
// Zelle). The Non-Revenue note then no longer says Zelle deposits are among it; a payload without the figures cannot
// say the mode and keeps today's note. Audit round 3, R3-B20 (R3-19): a package's flag is its members' served reading.
function zelleCountedInTrue(source = {}) {
  const figures = source && source.zelle_deposits;
  return Boolean(figures) && figures.counted_as_true_revenue === true;
}

// A ledger row the served payload tags as a Zelle deposit under Yes: the owner's "flagged 'Zelle'", beside its reason.
function zelleChip(tx) {
  return tx && tx.zelle_deposit === true ? glassChip("Z", "Zelle", "blue", "flag-chip") : "";
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
  // R2-OW17: it names no Zelle deposits where the served figures say they count in True revenue.
  const nonRevenueCopy = established ? REVENUE_METRIC_COPY.nonRevenue : REVENUE_METRIC_COPY.nonRevenueCaptured;
  const nonRevenueNote = zelleCountedInTrue(source)
    ? nonRevenueCopy.replace(", Zelle deposits included", "") : nonRevenueCopy;
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
// nonRevenueMonthly}); N/A where not established (§10.4), and Non-revenue named as captured rows only there. Audit
// round 3, R3-B20 (R3-19; §10.5): `package` picks the notice's words for a package's memo. Audit round 3, R3-B22 (R3-01;
// §10.1): and the money held for review, between the verified pair and non-revenue.
function revenueSummarySentence(source = {}, currency = "USD", { established, verifiedEstablished } = {}, monthly = {},
  { package: isPackage = false } = {}) {
  const pair = (total, perMonth, shown) => (shown
    ? `${formatMoney(total, currency)} (${formatMoney(perMonth, currency)} a month)` : "N/A");
  // R3-01: the credits held for review, which the average daily balance, the ending balance and the cash flow include
  // and True does not: "held for review $H (n credits)", the count alone where a package refuses its money; only where
  // the revenue is established (the Held card reads N/A otherwise, as True does) and something is held.
  const heldCount = numberOrNull(source.excluded_pending_review_count);
  const heldTotal = numberOrNull(source.excluded_pending_review_total);
  const heldCredits = heldCount === null ? "" : `${formatNumber(heldCount)} ${heldCount === 1 ? "credit" : "credits"}`;
  const held = established === true && heldCount !== null && heldCount > 0
    ? `held for review ${heldTotal === null ? heldCredits : `${formatMoney(heldTotal, currency)} (${heldCredits})`}, `
    : "";
  const nonRevenue = `${formatMoney(source.non_revenue_total, currency)} `
    + `(${formatMoney(monthly.nonRevenueMonthly, currency)} a month${established ? "" : ", captured rows only"})`;
  // R2-OW03 (the underwriter's Q3): the memo states the Zelle deposits the owner's policy excluded. R2-OW17 (the owner's
  // amendment of 2026-10-06): under Yes it states the Zelle deposits counted as True revenue and the parts held or out;
  // under No with figures served, the excluded part and the part a review counted.
  const served = zelleDeposits(source);
  const excluded = zelleExcluded(source);
  let zelleNote = excluded ? `, of which Zelle deposits excluded ${formatMoney(excluded.total, currency)}` : "";
  if (served && established !== true) {
    // Audit round 3, R3-B20 (R3-48; §10.4's I51): where the revenue is not established, the captured Zelle rows only,
    // and their non-revenue part where there is some; no part in True revenue or held for review.
    zelleNote = `; Zelle deposits captured ${formatMoney(served.total, currency)} (captured rows only)`
      + (served.out.count > 0 ? `, non-revenue ${formatMoney(served.out.total, currency)}` : "");
  } else if (served && served.counted) {
    zelleNote = `; Zelle deposits counted as True revenue ${formatMoney(served.inTrue.total, currency)}`
      + (served.held.count > 0 ? `, held for review ${formatMoney(served.held.total, currency)}` : "")
      + (served.out.count > 0 ? `, non-revenue ${formatMoney(served.out.total, currency)}` : "");
  } else if (served) {
    // Audit round 3, R3-B20 (R3-19): every part zelleFact names, so a package mixing members served counted and
    // excluded, or a legacy member under No, says where each part sits: the part a review counted, then the parts
    // counted and held.
    const parts = [
      ...(served.verified.count > 0 ? [`counted after review ${formatMoney(served.verified.total, currency)}`] : []),
      ...(served.countedFlagged.count > 0 ? [`counted ${formatMoney(served.countedFlagged.total, currency)}`] : []),
      ...(served.held.count > 0 ? [`held for review ${formatMoney(served.held.total, currency)}`] : []),
    ];
    zelleNote = `, of which Zelle deposits excluded ${formatMoney(served.out.total, currency)}`
      + (parts.length ? `; Zelle deposits ${parts.join(", ")}` : "");
  }
  // R3-19: a statement or a member analysed before the setting says it is shown as analysed, as the True card does.
  if (served && !served.applied) {
    zelleNote += isPackage ? "; a statement analysed before the Zelle setting is shown as analysed"
      : "; analysed before the Zelle setting: shown as analysed";
  }
  return `True revenue ${pair(source.true_revenue_total, monthly.trueMonthly, established === true)}, `
    + `verified revenue ${pair(source.verified_revenue_total, monthly.verifiedMonthly, verifiedEstablished === true)}, `
    + `${held}non-revenue ${nonRevenue}${zelleNote}.`;
}

// Audit round 3, R3-B24 (R3-16; true revenue spec §10.1; standard G7, P22): the copied memo's clause after the revenue
// sentence, only where the served payload flags a large unsourced deposit. A statement: "1 large deposit to source: $X,
// S% of True revenue (counted, not verified). " or "N large deposits to source: $X (each over 25% of True revenue;
// counted, not verified). "; a package: "N large deposits to source: $X (each over 25% of its statement's True revenue;
// counted, not verified). ", the count alone where it refuses its money. "" otherwise.
function largeDepositSummary(source = {}, currency = "USD", { package: isPackage = false } = {}) {
  const count = numberOrNull(source && source.large_unsourced_deposit_count);
  if (!count) return "";
  const total = numberOrNull(source.large_unsourced_deposit_total);
  const head = `${formatNumber(count)} ${count === 1 ? "large deposit" : "large deposits"} to source`
    + (total === null ? "" : `: ${formatMoney(total, currency)}`);
  const items = Array.isArray(source.large_unsourced_deposits) ? source.large_unsourced_deposits : [];
  const share = count === 1 && items.length === 1 ? numberOrNull(items[0] && items[0].share_of_true_percent) : null;
  if (!isPackage && share !== null) {
    return `${head}, ${share.toFixed(1)}% of True revenue (counted, not verified). `;
  }
  const of = isPackage ? "its statement's True revenue" : "True revenue";
  return `${head} (${count === 1 ? "" : "each "}over 25% of ${of}; counted, not verified). `;
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
// established, and its currencies are not refused (a refused package's judgement never reads as a pass). Audit round 2,
// R2-B15 (R15, R54): and it counted a statement at all: a package whose every account was left out, or none of whose
// statements was analysed, reconciles nothing and never reads "Balanced".
function packageRevenueBalanced(pkg = {}) {
  const totals = pkg.totals || {};
  const unreconciled = Array.isArray(totals.unreconciled_documents) ? totals.unreconciled_documents : null;
  return countedDocuments(pkg.documents).length > 0 && (numberOrNull(totals.completed) || 0) > 0
    && unreconciled !== null && unreconciled.length === 0 && packageRevenueFlags(totals).revenue_established
    && !packageCurrencyInfo(pkg).refused;
}

// Audit B11 (B9's I13, B10's I05): what the True card says True rests on, from a statement's metrics: no holder's name
// read (the holds that keep the holder's own money out cannot see it), and the share of credits whose printed payer
// no parser read. R2-OW03 (the underwriter's Q3): and the Zelle deposits the owner's policy excluded, so True can be
// read against the Monthly Statements' total deposits. R2-OW11 (the underwriter's Q10): and a premium trust account,
// whose deposits that would count are held. Audit round 3, R3-B11 (R3-30): a statement with no holder line read
// publishes no account title either, so its premium-trust title is not read (a title in its account name still is).
function statementRevenueFacts(metrics = {}, currency = "USD") {
  const facts = [];
  if (metrics.holder_unscreened === true) {
    facts.push("No holder name read: the holder's own deposits are not screened, nor is a premium-trust account title read");
  }
  if (metrics.payer_text_unread === true) {
    const count = numberOrNull(metrics.payer_text_unread_count);
    facts.push(`${count === null ? "Many" : formatNumber(count)} credits' payer text not read`);
  }
  // Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: a statement of a premium trust account says why its
  // True is held.
  if (metrics.premium_trust_account === true) {
    facts.push("Premium trust account: deposits that would count are held (insureds' premiums, not revenue); non-revenue deposits stay excluded");
  }
  // R2-OW17: where the Zelle money sits, in the reading served (zelleFact). Audit round 3, R3-B20 (R3-48): the captured
  // rows only where the statement's revenue is not established.
  const zelle = zelleFact(metrics, currency, { established: metrics.revenue_established === true });
  if (zelle) facts.push(zelle);
  // Audit round 3, R3-B24 (R3-16): the large unsourced deposits, before the debit flags.
  return [...facts, ...largeDepositFacts(metrics, currency), ...debitFlagFacts(metrics, currency)];
}

// Audit round 3, R3-B24 (R3-16; true revenue spec §10.1, §17.1's default D1; standard G7, "COUNT+FLAG, and source them
// when large", P22): the True card's line for the counted credits whose source the statement does not prove that are
// 10,000 or more of the statement's unit and over 25% of True, from a statement's served metrics or a package's totals,
// only where the count is: "Large deposits to source: N · $X (each $10,000.00 or more and over 25% of True; counted,
// not verified)", a package's share being each statement's own True as the package counts it (the True Deposits its row shows on the package page,
// its holds applied; R3-B24 review round 1), and the count alone where a package refuses its money. Information only:
// no figure, badge, gate or decision reads it. Audit round 3, final review (R3-FF), F6: the floor is written in the
// unit it is compared in, as the withholding floor's note writes its floor (formatMoney): the statement's, a package's
// where its members share one, none where they differ ("$10,000.00", "CA$10,000.00", "10,000.00").
function largeDepositFacts(source = {}, currency = "USD", { package: isPackage = false } = {}) {
  const count = numberOrNull(source && source.large_unsourced_deposit_count);
  if (!count) return [];
  const total = numberOrNull(source.large_unsourced_deposit_total);
  return [`${LARGE_DEPOSIT_WORDS}: ${formatNumber(count)}${total === null ? "" : ` · ${formatMoney(total, currency)}`} `
    + `(each ${formatMoney(LARGE_UNSOURCED_DEPOSIT_FLOOR, currency)} or more and over 25% of `
    + `${isPackage ? "its statement's True" : "True"}; counted, not verified)`];
}

// Owner ruling 2026-10-02 (the underwriter's Q6, "Flag, but do not deduct, returns that cannot be matched and processor
// chargebacks"; true revenue spec §10.1; R2-OW15): the True card's flag lines, a statement's (its served metrics) or a
// package's (its totals), each only where its count is: "Returned deposits not matched: N · $X (not deducted)" and
// "Processor chargebacks and adjustments: N · $X (not deducted)"; the count alone where a package refuses its money.
function debitFlagFacts(source = {}, currency = "USD") {
  return Object.entries(DEBIT_FLAG_WORDS).flatMap(([kind, words]) => {
    const count = numberOrNull(source && source[`${kind}_count`]);
    if (!count) return [];
    const total = numberOrNull(source[`${kind}_total`]);
    return [`${words}: ${formatNumber(count)}${total === null ? "" : ` · ${formatMoney(total, currency)}`} (not deducted)`];
  });
}

// The same facts for a package, from its totals' member lists and its non-revenue breakdown.
function packageRevenueFacts(totals = {}, currency = "USD") {
  const statements = (list) => new Set((Array.isArray(list) ? list : []).map((id) => String(id).split("#")[0])).size;
  const noun = (n) => (n === 1 ? "statement" : "statements");
  const facts = [];
  const unscreened = statements(totals.holder_unscreened_documents);
  // Audit round 3, R3-B11 (R3-30): nor a premium-trust title read from them.
  if (unscreened) {
    facts.push(`${formatNumber(unscreened)} ${noun(unscreened)} with no holder name read (nor a premium-trust title)`);
  }
  const unread = statements(totals.payer_text_unread_documents);
  if (unread) facts.push(`${formatNumber(unread)} ${noun(unread)} with payer text not read`);
  // Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: the members that are premium trust accounts.
  const premiumTrust = statements(totals.premium_trust_documents);
  if (premiumTrust) facts.push(`${formatNumber(premiumTrust)} ${noun(premiumTrust)} of a premium trust account: deposits that would count are held`);
  // Audit round 3, R3-B20 (R3-48): the captured rows only where the package's revenue is not established.
  const zelle = zelleFact(totals, currency, { package: true, established: packageRevenueFlags(totals).established });
  if (zelle) facts.push(zelle);
  // Audit round 3, R3-B24 (R3-16): the members' large unsourced deposits, before the debit flags.
  return [...facts, ...largeDepositFacts(totals, currency, { package: true }), ...debitFlagFacts(totals, currency)];
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
  const rows = (Array.isArray(documents) ? documents : []).filter(Boolean);
  const outdated = new Set(rows
    .filter((doc) => doc.analysis_rules_outdated === true && unestablished.has(statementOf(doc.id)))
    .map((doc) => statementOf(doc.id))).size;
  // Audit round 2, R2-B15 (R50): statements over statements. A package holding an account of a document counts its
  // completed statements (the distinct jobs of the counted rows that are done), never its completed accounts; never
  // fewer than the statements it names.
  const multi = rows.some((doc) => packageMember(doc.id).account !== null);
  const completed = multi
    ? Math.max(new Set(rows.filter((doc) => doc.status === "done").map((doc) => statementOf(doc.id))).size, statements)
    : numberOrNull(totals.completed) ?? statements;
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
      ["Confirmed Withholding", "N/A", "Confirmed lender debits as a share of the withholding basis (True revenue by default)", "%", "neutral"],
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
      ["Withholding Basis", "N/A", DEFAULT_WITHHOLDING_BASIS_NOTE, "DEP", "neutral"],
      ["Potential Withholding Exposure", "N/A", "Possible lender debits as a share of the withholding basis (True revenue by default)", "%", "neutral"],
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

// Audit round 2, R2-B15 (R13): how many calendar months a statement's printed period covers: its days, first and last
// included (at most 400, as the server reads them, webapp/app.py _covered_days), over 30.4375 (an average month), half
// up, at least one; one when either day does not read or the end is before the start.
function statementMonthsCovered(statement = {}) {
  const start = isoDay(statement.period_start);
  const end = isoDay(statement.period_end);
  if (!start || !end || end < start) return 1;
  const days = Math.min(Math.round((end - start) / 86400000) + 1, 400);
  return Math.max(1, Math.floor(days / 30.4375 + 0.5));
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

// The basis the withholding rates divide by, as the payload names it (R2-OW14): its own label, else its mode's (a payload
// with no mode was analysed on the legacy basis), else a package's mixed configuration's.
function withholdingBasisLabel(metrics = {}) {
  if (metrics.withholding_denominator_label) return metrics.withholding_denominator_label;
  const mode = metrics.withholding_denominator_mode || "legacy_eligible_deposits";
  return WITHHOLDING_BASIS_LABELS[mode] || "Withholding basis";
}

// Audit round 3 (R3-68): the basis the copied memos' rates divide by, as the Withholding Basis card names it.
function withholdingBasisWords(source = {}) {
  return `withholding basis: ${withholdingBasisLabel(source).toLowerCase()}`
    + (withholdingBasisUnestablished(source) ? ", not established" : "");
}

// The final review of round 2, F1 (true revenue spec §10.1, §10.4, §11): the basis the withholding mode divides by is
// not established (True revenue where the revenue is not, Verified where Verified is not; the server publishes the
// flag only where it is set), so no rate is published over it and the basis reads N/A, as True does.
function withholdingBasisUnestablished(metrics = {}) {
  return metrics.withholding_basis_unestablished === true;
}

// Audit round 3, R3-B03 (R3-27; true revenue spec §10.1, §11): a package whose statements were analysed under
// different withholding bases (the server publishes the flag only there) publishes no rate over their sum.
function withholdingBasisMixed(metrics = {}) {
  return metrics.withholding_basis_mixed === true;
}

// R3-27: "1 on legacy eligible deposits, 1 on true revenue", the members counted per basis, in the bases' own order.
function withholdingBasisMembersWords(metrics = {}) {
  const members = Array.isArray(metrics.withholding_basis_by_member) ? metrics.withholding_basis_by_member : [];
  const counts = new Map();
  for (const member of members) {
    if (member && typeof member === "object") counts.set(member.mode, (counts.get(member.mode) || 0) + 1);
  }
  const order = Object.keys(WITHHOLDING_BASIS_LABELS);
  return [...counts.entries()]
    .sort(([left], [right]) => (order.indexOf(left) + 1 || order.length + 1) - (order.indexOf(right) + 1 || order.length + 1))
    .map(([mode, count]) => `${formatNumber(count)} on ${(WITHHOLDING_BASIS_LABELS[mode] || String(mode)).toLowerCase()}`)
    .join(", ");
}

// Audit round 3, R3-B03 (R3-20): the basis is above $0 and under the floor (the server's flag), so no rate is published.
function withholdingBasisBelowFloor(metrics = {}) {
  return metrics.withholding_basis_below_floor === true;
}

// R3-20: "true revenue, $1.00", the basis and its amount, as the floor's notes name them.
function withholdingBasisWithAmount(metrics = {}, currency = "USD") {
  const amount = metrics.potential_withholding_denominator ?? metrics.withholding_denominator ?? metrics.eligible_deposits;
  return `${withholdingBasisLabel(metrics).toLowerCase()}, ${formatMoney(amount, currency)}`;
}

// The Withholding Basis card's value: the basis the rates divide by, N/A where it is not established (F1) or where a
// package sums members analysed under different bases (R3-27).
function withholdingBasisAmount(metrics = {}) {
  if (withholdingBasisUnestablished(metrics) || withholdingBasisMixed(metrics)) return null;
  return metrics.potential_withholding_denominator ?? metrics.eligible_deposits;
}

function withholdingAuditNote(metrics = {}, currency = "USD") {
  // Audit round 3, R3-B03 (R3-27): a package whose statements were analysed under different bases names them.
  if (withholdingBasisMixed(metrics)) {
    return `The statements were analysed on different withholding bases (${withholdingBasisMembersWords(metrics)}), so `
      + "no package rate is published; re-analyze them on one basis; analyst review is required";
  }
  // F1 (final review of round 2): say why no rate is published: a statement's basis, or a package member's, is not
  // established.
  if (withholdingBasisUnestablished(metrics)) {
    const scope = Object.prototype.hasOwnProperty.call(metrics, "package_withholding_rate") ? " on every statement" : "";
    return `The withholding basis (${withholdingBasisLabel(metrics).toLowerCase()}) is not established${scope}, so no `
      + "rate is published; analyst review is required";
  }
  // Audit round 3, R3-B03 (R3-20): a revenue basis under the floor publishes no rate, as $0 does.
  if (withholdingBasisBelowFloor(metrics)) {
    return `The withholding basis (${withholdingBasisWithAmount(metrics, currency)}) is under `
      + `${formatMoney(WITHHOLDING_BASIS_FLOOR, currency)}, so no rate is published; analyst review is required`;
  }
  // Owner ruling 2026-10-02 (the underwriter's Q7; R2-OW14): the note names the basis, True revenue by default.
  if (metrics.withholding_review_required) {
    return `The withholding basis (${withholdingBasisLabel(metrics).toLowerCase()}) is unavailable; analyst review is required`;
  }
  const numerator = formatMoney(metrics.withholding_numerator ?? metrics.lender_debits, currency);
  const denominator = formatMoney(metrics.withholding_denominator ?? metrics.eligible_deposits, currency);
  const label = withholdingBasisLabel(metrics);
  // Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the numerator keeps the funder payments returned unpaid.
  // The owner's answer of 2026-10-07 to audit round 3's R3-73 (R3-B02): except those the same funder re-debited, which
  // the re-debit counts once (the numerator is paid plus the returned payments still standing).
  const returned = returnedFunderPaymentTotal(metrics);
  const standing = returnedStandingTotal(metrics);
  const parts = [];
  if (standing !== null && Math.abs(standing) > 0) parts.push(`incl. ${formatMoney(standing, currency)} returned unpaid`);
  const reDebited = returned === null || standing === null ? 0 : Math.round((returned - standing) * 100) / 100;
  if (reDebited > 0) parts.push(`${formatMoney(reDebited, currency)} returned and re-debited, counted once`);
  // The owner's answer of 2026-10-07 to audit round 3's R3-79 ("Exclude worded payoffs"; R3-B03): the lump sums in paid
  // to lenders and out of the numerator.
  const lumpSum = lumpSumPayoffTotal(metrics);
  if (lumpSum !== null) {
    const count = numberOrNull(metrics.lump_sum_payoff_count) ?? 1;
    parts.push(`${formatMoney(lumpSum, currency)} lump-sum ${count === 1 ? "payoff" : "payoffs"} not included`);
  }
  const included = parts.length ? ` (${parts.join("; ")})` : "";
  return `${numerator} confirmed lender debits${included} divided by ${denominator} ${label.toLowerCase()}`;
}

// The returned funder payments still in the withholding numerator (R2-OW13), null when there is none: the numerator less
// paid to lenders (audit round 3, R3-B02: a returned payment its funder re-debited is no longer in it; R3-B03: paid
// counts the lump-sum payoffs the numerator leaves out), else the whole returned total where either figure is missing
// (a payload analysed before the numerator).
function returnedStandingTotal(metrics = {}) {
  const returned = returnedFunderPaymentTotal(metrics);
  if (returned === null) return null;
  const numerator = numberOrNull(metrics.withholding_numerator);
  const paid = numberOrNull(metrics.lender_debits);
  if (numerator === null || paid === null) return returned;
  const standing = Math.round((numerator - paid + (lumpSumPayoffTotal(metrics) ?? 0)) * 100) / 100;
  return standing >= 0 && standing <= returned ? standing : returned;
}

// The owner's answer of 2026-10-07 to audit round 3's R3-79 ("Exclude worded payoffs (Recommended)"; true revenue spec
// §10.1, §11; R3-B03): the paid payoff-worded debits to confirmed funders, in paid to lenders and out of the withholding
// numerator, null when there is none (or the package refused the money across currencies).
function lumpSumPayoffTotal(metrics = {}) {
  const total = numberOrNull(metrics.lump_sum_payoff_total);
  return total !== null && Math.abs(total) > 0 ? total : null;
}

// R3-79: one information note per lump-sum payoff, its money in its own statement's unit (a package item's
// source_currency, R2-OW13's rule), quoting the payoff word as the bank printed it. Audit round 3, R3-MERGE: in the
// plain voice and layout of the owner's request of 2026-10-07 (lenderNote): a headline, its sentences and, on a package
// page, the statement it comes from (`sources`, paymentChangeSources), never a job id.
function lumpSumPayoffNote(item, currency = "USD", sources = null) {
  const unit = "source_currency" in item ? item.source_currency : currency;
  const amount = numberOrNull(item.amount);
  const words = item.words ? ` (the bank printed: "${item.words}")` : "";
  return lenderNote(`${item.funder || "Confirmed lender"}: a lump-sum payoff`, [
    `The ${formatMoney(amount === null ? null : Math.abs(amount), unit)} payment on ${readableDate(item.date)} is worded `
      + `as a payoff${words}.`,
    "It counts in paid to lenders, but not in the withholding rate.",
  ], [], paymentChangeSourceLine(item, sources));
}

// R3-79: the note as one line of text, as the copied summaries carry it.
function lumpSumPayoffLine(item, currency = "USD", sources = null) {
  return lenderNoteText(lumpSumPayoffNote(item, currency, sources));
}

// R3-79: the lines the copied summaries carry, one per item.
function lumpSumPayoffLines(items, currency = "USD", sources = null) {
  return (Array.isArray(items) ? items : [])
    .filter((item) => item && typeof item === "object")
    .map((item) => lumpSumPayoffLine(item, currency, sources));
}

// R3-79: the lender table's notes (statement page, package page, statement modal), each with its "Lump sum" chip.
function lumpSumPayoffRowsHtml(items, currency = "USD", sources = null) {
  return (Array.isArray(items) ? items : [])
    .filter((item) => item && typeof item === "object")
    .map((item) => lenderNoteRowHtml(glassChip("Σ", "Lump sum", "blue"), lumpSumPayoffNote(item, currency, sources)))
    .join("");
}

// Owner ruling 2026-10-02 (the underwriter's Q5, "take the bounced amount out of "paid to lenders" but keep it in the
// withholding rate"; true revenue spec §10.1; R2-OW13): the funder payments the bank returned unpaid, null when there
// is none (or the package refused the money across currencies), so every sentence below reads as before.
function returnedFunderPaymentTotal(metrics = {}) {
  const total = numberOrNull(metrics.returned_funder_payment_total);
  return total !== null && Math.abs(total) > 0 ? total : null;
}

// The Confirmed Lender Debits card's note: what paid leaves out.
function paidLendersNote(metrics = {}, currency = "USD", lead = "Total paid to confirmed lenders") {
  const returned = returnedFunderPaymentTotal(metrics);
  return returned === null ? lead : `${lead}; ${formatMoney(returned, currency)} returned unpaid not included`;
}

// The summary sentence's lender debits: paid, then the returned payments beside it. Audit round 4, R4-50: a package
// that refuses its money across currencies keeps the count and nulls the total, so the clause prints the count alone,
// as the held clause does ("(2 returned funder payments)"), never "N/A" inside it.
function lenderDebitsSummary(metrics = {}, currency = "USD") {
  const paid = formatMoney(metrics.lender_debits, currency);
  const count = numberOrNull(metrics.returned_funder_payment_count) ?? 0;
  if (count <= 0) return `${paid} confirmed lender debits`;
  const total = numberOrNull(metrics.returned_funder_payment_total);
  return `${paid} confirmed lender debits paid (${formatNumber(count)} returned funder `
    + `${count === 1 ? "payment" : "payments"}${total === null ? "" : `, ${formatMoney(total, currency)}`})`;
}

/* --- lender notes -------------------------------------------------------------
   The owner's request of 2026-10-07 (dashboard clarity; display only; true revenue spec §10.1, §20): "make this writing
   more clear ... these notes on the lenders". Every note of the lender table, R2-OW13's returned funder payments and
   R2-OW18's lender payment changes, reads as a short headline ("KAPITUS: payment went down 30%"), one or two plain
   sentences under it, an "Also:" sentence per extra note, and the statement it comes from ("From: June 2026
   statement"), never a job id or a "<uuid>_<file>" name. The copied memo prints the same words as one line. */
const SHORT_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const ORDINAL_WORDS = ["first", "second", "third", "fourth", "fifth"];

// "Jun 22, 2026"; a value that is no ISO day reads as it was given (N/A when missing).
function readableDate(value) {
  const day = isoDay(value);
  if (!day) return value ? String(value) : "N/A";
  return `${SHORT_MONTH_NAMES[day.getUTCMonth()]} ${day.getUTCDate()}, ${day.getUTCFullYear()}`;
}

// "Mar 20 and Apr 1, 2026": the first day names its year only where the two years differ. Audit round 3, R3-MERGE:
// `joiner` "to" reads a span ("Mar 3 to Mar 17, 2054", the missed payments of a Caught up note).
function readableDateRange(first, last, joiner = "and") {
  const start = isoDay(first);
  const end = isoDay(last);
  if (start && end && start.getUTCFullYear() === end.getUTCFullYear()) {
    return `${SHORT_MONTH_NAMES[start.getUTCMonth()]} ${start.getUTCDate()} ${joiner} ${readableDate(last)}`;
  }
  return `${readableDate(first)} ${joiner} ${readableDate(last)}`;
}

// "1 business day", "8 business days".
function countWords(count, one, many = `${one}s`) {
  return `${formatNumber(count)} ${numberOrNull(count) === 1 ? one : many}`;
}

// "A", "A and B", "A, B and C".
function listWords(parts) {
  if (parts.length < 2) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

// A file's name as it was uploaded, any leading job id or UUID (and the separator after it) removed; "" when nothing
// else is left.
const STATEMENT_ID_PREFIX = /^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})(?:[_\s-]+|$)/i;

function statementFileName(name) {
  let text = String(name ?? "").trim();
  while (text && STATEMENT_ID_PREFIX.test(text)) text = text.replace(STATEMENT_ID_PREFIX, "").trim();
  return text;
}

// The statements a package page's notes can name, from its rows (`documents`): each counted member by the month its
// printed period stands for ("April 2054 statement"), with its file (and its account, for an account of a document)
// where two members share that month, else by its file where it printed no period. `count` is how many members the
// package counts: a package of one needs no source line, as a statement's own page needs none.
function paymentChangeSources(documents) {
  const rows = countedDocuments(documents);
  const months = rows.map((doc) => monthLabel(statementMonth(doc.period_start, doc.period_end)));
  const shared = new Map();
  months.forEach((month) => { if (month) shared.set(month, (shared.get(month) || 0) + 1); });
  const members = new Map();
  rows.forEach((doc, index) => {
    const month = months[index];
    const { account } = packageMember(doc.id);
    const which = [statementFileName(doc.filename), account === null ? "" : `account ${formatNumber(account)}`]
      .filter(Boolean).join(", ");
    const crowded = Boolean(month) && shared.get(month) > 1;
    const named = crowded && which;
    members.set(String(doc.id), {
      month,
      crowded,
      label: month ? `${month} statement${named ? `, ${which}` : ""}` : (which || "a statement"),
    });
  });
  return { count: rows.length, members };
}

// The statement an item's `<prefix>_job`, `_account` and `_document` name: the page's member, else its file's name.
function paymentChangeMember(fields, prefix, sources) {
  const job = fields[`${prefix}_job`];
  const account = fields[`${prefix}_account`];
  const id = account === undefined || account === null ? String(job ?? "") : `${job}#account_${account}`;
  const member = sources && sources.members ? sources.members.get(id) : null;
  if (member) return member;
  return { month: null, label: statementFileName(fields[`${prefix}_document`]) || "a statement" };
}

// A note's source line: none on a statement's own page (its items name no statement) or in a package of one member;
// "From: March 2054 → April 2054 statements" for an item seen across two statements (`across`, the two field prefixes)
// whose months each name one member, else the two members' own labels (review round 1: where another account prints
// the same month, the bare months would not say which account); else "From: <its statement>".
function paymentChangeSourceLine(fields, sources, across = null) {
  if (fields.scope === "statement" || (!("source_job" in fields) && !("source_document" in fields))) return "";
  if (sources && sources.count <= 1) return "";
  if (across) {
    const from = paymentChangeMember(fields, across[0], sources);
    const to = paymentChangeMember(fields, across[1], sources);
    if (from.month && to.month && from.month !== to.month && !from.crowded && !to.crowded) {
      return `From: ${from.month} → ${to.month} statements`;
    }
    return `From: ${from.label} → ${to.label}`;
  }
  return `From: ${paymentChangeMember(fields, "source", sources).label}`;
}

// A note: its headline, its plain sentences (`details`), its "Also:" sentences and its source line, each plain text.
function lenderNote(headline, details = [], also = [], source = "") {
  return { headline, details: details.filter(Boolean), also: also.filter(Boolean), source };
}

// The note as one line of text, for the copied memo.
function lenderNoteText(note) {
  return [`${note.headline}.`, ...note.details, ...note.also, note.source ? `${note.source}.` : ""]
    .filter(Boolean).join(" ");
}

// One warning row of the lender table: the chip and the bold headline, then the details, each "Also:" sentence and the
// source line, each on its own line; every value escaped.
function lenderNoteRowHtml(chip, note) {
  const line = (part, text) => `<div class="lender-note-${part}">${escapeHtml(text)}</div>`;
  const details = note.details.length ? line("detail", note.details.join(" ")) : "";
  const also = note.also.map((text) => line("also", text)).join("");
  return `
      <tr class="lender-warning">
        <td colspan="6"><div class="lender-note"><div class="lender-note-head">${chip}<strong class="lender-note-headline">${escapeHtml(note.headline)}</strong></div>${details}${also}${note.source ? line("source", note.source) : ""}</div></td>
      </tr>
    `;
}

// Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): one note per returned funder payment, quoting the bank's own
// words, so a business's reversal of the debit reads apart from a bank's bounce (the headline, review round 1 of the
// 2026-10-07 change, says "was returned", true of both). A package's item is in its statement's unit and names its
// statement; the final review of round 2's F2(b) item, a payment the package matched to a return in the next statement,
// names both.
function returnedFunderPaymentNote(item, currency = "USD", sources = null) {
  const unit = "source_currency" in item ? item.source_currency : currency;
  const amount = numberOrNull(item.amount);
  const words = item.credit_description ? ` (the bank printed: "${item.credit_description}")` : "";
  const details = [
    `The ${formatMoney(amount === null ? null : Math.abs(amount), unit)} payment on ${readableDate(item.debit_date)} `
      + `was returned unpaid on ${readableDate(item.credit_date)}${words}.`,
  ];
  // The owner's answer of 2026-10-07 to audit round 3's R3-73 ("Count it once"; R3-B02), in the plain voice of the
  // owner's request of 2026-10-07 (R3-MERGE): a payment the same funder re-debited (the same cents off its cycle, or an
  // exact 2x catch-up) is out of the withholding rate, its re-debit counting the obligation once; a package's re-debit
  // in another statement names that statement (its month, as the source line names statements).
  if (item.represented_date) {
    const where = item.represented_job || item.represented_document
      ? ` (${paymentChangeMember(item, "represented", sources).label})` : "";
    const caughtUp = item.represented_kind === "caught_up";
    // Audit round 4, R4-75: a catch-up of 3 to 6 times the payment names its multiple (an item stored without
    // `represented_multiple` reads 2, "twice the payment", as before).
    const multiple = typeof item.represented_multiple === "number" && Number.isInteger(item.represented_multiple)
      ? item.represented_multiple : 2;
    const times = multiple === 2 ? "twice the payment" : `${multiple} times the payment`;
    const day = readableDate(item.represented_date);
    // Audit round 4, R4-76: a note never states a collection the statement does not show. Where the bank returned the
    // re-debit too (`represented_returned`, read when served by withReDebitReturns), the note says so; it still counts
    // the obligation once, by the bounced re-debit's own attempt (§17.1's R2-OW13 default (9)). The paid case keeps
    // R3-MERGE's words ("taken again" is the owner's, R3-MERGE owner item 2).
    const returnedToo = item.represented_returned === true;
    details.push(caughtUp
      ? (returnedToo ? `A catch-up of ${times} was debited on ${day}${where}, and that debit was also returned.`
        : `It was caught up on ${day}${where}, by one debit of ${times}.`)
      : (returnedToo ? `It was debited again on ${day}${where}, and that debit was also returned.`
        : `It was taken again on ${day}${where}.`));
    details.push("It isn't counted as paid; it is counted once in the withholding rate, by the "
      + `${caughtUp ? "catch-up" : "second debit"}.`);
  } else {
    details.push("It isn't counted as paid, but it still counts in the withholding rate.");
  }
  return lenderNote(`${item.funder || "Confirmed lender"}: a payment was returned`, details, [],
    paymentChangeSourceLine(item, sources, item.cross_statement === true ? ["source", "credit"] : null));
}

// The note as one line of text: the copied package memo's line (R3-B22's R3-67).
function returnedFunderPaymentWarning(item, currency = "USD", sources = null) {
  return lenderNoteText(returnedFunderPaymentNote(item, currency, sources));
}

// Audit round 4, R4-76: the served returned funder payments, each item whose re-debit the bank returned too copied with
// `represented_returned: true`, read wherever the list's notes are written (the lender table of a statement and of a
// package, the copied package memo). Computed when served, never stored: the re-debit is another item of the same
// list printing this item's `represented_location` as its `debit_location`, in the re-debit's statement (the item's
// `represented_job` and `represented_account` where it names them, else its own `source_job` and `source_account`; on
// a statement's page, where no item names a source, the location alone). webapp/app.py _re_debit_returned reads the
// same for the package downloads.
function withReDebitReturns(items) {
  const list = Array.isArray(items) ? items : [];
  const isItem = (value) => Boolean(value) && typeof value === "object";
  const returned = (item) => {
    if (!item.represented_date || !item.represented_location) return false;
    const named = item.represented_job !== undefined && item.represented_job !== null;
    const job = (named ? item.represented_job : item.source_job) ?? null;
    const account = (named ? item.represented_account : item.source_account) ?? null;
    return list.some((other) => isItem(other) && other !== item
      && other.debit_location === item.represented_location
      && (other.source_job ?? null) === job && (other.source_account ?? null) === account);
  };
  return list.map((item) => (isItem(item) && returned(item) ? { ...item, represented_returned: true } : item));
}

// Audit round 3, R3-B22 (R3-67; §10.1's R2-OW13 copy line, the owner's Q5): a package memo's funder line, its paid
// total and statements, then its payments returned unpaid, which paid leaves out and the withholding rate keeps, so the
// line explains the rate ("ONDECK: $0.00 across 1 statement(s), 1 returned unpaid ($1,200.00, still in the withholding
// rate)"). R3-B02 (the owner's answer of 2026-10-07 to R3-73, "Count it once"): a return the funder re-debited (its
// served item names the re-debit) is out of the rate, the re-debit in paid counting it once, so the line says so.
// Audit round 4, R4-50: in a package that refuses its money across currencies (the funder's `returned_payment_total`
// null, its count kept), the money and its separator are left out of every branch, the count alone, as the held clause
// prints it: "1 returned unpaid (still in the withholding rate)".
function packageFunderSummaryLine(funder, currency = "USD", returnedPayments = []) {
  const line = `${funder.funder}: ${formatMoney(funder.total_debited, currency)} across `
    + `${formatNumber(funder.documents)} statement(s)`;
  const count = numberOrNull(funder.returned_payment_count) ?? 0;
  if (count <= 0) return line;
  const total = numberOrNull(funder.returned_payment_total);
  const money = total === null ? null : formatMoney(total, currency);
  const reDebited = Math.min(count, (Array.isArray(returnedPayments) ? returnedPayments : [])
    .filter((item) => item && typeof item === "object" && item.funder === funder.funder && item.represented_date)
    .length);
  const rate = reDebited === 0 ? "still in the withholding rate"
    : reDebited === count ? "re-debited: counted once in the withholding rate"
      : `${formatNumber(reDebited)} re-debited, counted once in the withholding rate; `
        + `${formatNumber(count - reDebited)} still in it`;
  const clause = money === null ? rate : `${money}${reDebited > 0 && reDebited < count ? "; " : ", "}${rate}`;
  return `${line}, ${formatNumber(count)} returned unpaid (${clause})`;
}

// The owner's request of 2026-10-06 (lender payment changes; R2-OW18): why a package member's lender payments were not
// compared across statements, in the dashboard's plain words (the exports keep webapp/app.py
// LENDER_PAYMENT_UNCHECKED_WORDS).
const LENDER_PAYMENT_UNCHECKED_WORDS = {
  not_ready: "not analysed yet",
  analysed_before_check: "analysed before the check; re-analyze it to include it",
  no_currency: "no currency declared, so it was checked on its own",
  no_period: "no statement period printed, so it was checked on its own",
  no_account_number: "fewer than 4 account digits and no balance chain, so it was checked on its own",
};
const PAYMENT_CADENCE_WORDS = { semimonthly: "semi-monthly", daily_irregular: "irregular daily" };

function paymentCadenceWords(cadence) {
  return PAYMENT_CADENCE_WORDS[cadence] || String(cadence || "");
}

// "a weekly schedule", "an irregular daily schedule": the schedule a grace window belongs to.
function scheduleWords(cadence) {
  const words = paymentCadenceWords(cadence) || "payment";
  return `${/^[aeiou]/i.test(words) ? "an" : "a"} ${words} schedule`;
}

function signedPercent(value) {
  const number = numberOrNull(value) ?? 0;
  return `${number > 0 ? "+" : number < 0 ? "-" : ""}${Math.abs(number)}%`;
}

// The owner's request of 2026-10-06 (lender payment changes; R2-OW18, G3), in the words of the owner's request of
// 2026-10-07: one note of the lender table. Information only. Money is in the item's own unit (a package item's
// source_currency, R2-OW13's rule); `sources` (paymentChangeSources) names a package item's statements.
function lenderPaymentChangeNote(item, currency = "USD", sources = null) {
  const unit = "source_currency" in item ? item.source_currency : currency;
  const money = (value) => formatMoney(value, unit);
  const day = readableDate;
  const cadence = paymentCadenceWords;
  // Review round 3 of the 2026-10-07 change: a potential lender is named "potential lender <label>" (the headline
  // "Potential lender <label>: ..."), never "<label> (potential lender)", whose label often ends in parentheses.
  const nameOf = (name, state) => (state === "potential" ? `potential lender ${name}` : name);
  const label = item.lender_label || item.lender || "Lender";
  const percent = numberOrNull(item.change_percent);
  const details = [];
  const also = [];
  let headline = "payment changed";
  let across = null;
  // Audit round 3, R3-84: debits no rule claimed at the series' exact cents, on its schedule, inside a pause's gap or
  // after a stop's last presence (a processor rail the registry refuses as an alias): named, never counted. R3-MERGE:
  // an "Also:" sentence, in the plain voice of the owner's request of 2026-10-07.
  const sameAmount = (amount) => {
    const same = item.same_amount_debits;
    if (!same || typeof same !== "object") return [];
    const when = same.first_date && same.last_date && same.first_date !== same.last_date
      ? `from ${readableDateRange(same.first_date, same.last_date, "to")}` : `on ${day(same.first_date || same.last_date)}`;
    return [`Also: ${countWords(same.count, "debit")} of exactly ${money(amount)} came on the same ${cadence(item.cadence)} `
      + `schedule under another description, ${when}; this may be the lender collecting under another name.`];
  };
  if (["decrease", "increase", "cadence_change"].includes(item.kind)) {
    if (item.cross_statement === true) across = ["from", "to"];
    const before = cadence(item.cadence_before);
    const after = cadence(item.cadence_after);
    const starting = `starting ${day(item.first_after_date)}`;
    const amounts = `from ${before} ${money(item.amount_before)} to ${after} ${money(item.amount_after)} ${starting}`;
    // Review round 1 of the 2026-10-07 change: the counts are the level's own, never "so far" (a later change may have
    // replaced it).
    if (item.kind === "cadence_change") {
      headline = "payment schedule changed";
      details.push(`Payments changed ${amounts} (${countWords(item.payments_after, "payment")} on the new schedule, `
        + `after ${formatNumber(item.payments_before)} on the old).`);
      details.push(`The weekly total stayed about the same (${money(item.weekly_equivalent_before)} before, `
        + `${money(item.weekly_equivalent_after)} after${percent ? `, ${signedPercent(percent)}` : ""}).`);
    } else {
      const possible = item.schedule_confirmed === false;
      const size = percent === null ? "" : ` ${Math.abs(percent)}%`;
      const way = item.kind === "decrease" ? "down" : "up";
      // Across schedules the percentage is the weekly total's (B1), so the headline names it and its sentence leads.
      const what = item.cadence_changed === true ? "weekly payment total" : "payment";
      headline = possible ? `${what} may have gone ${way}${size}` : `${what} went ${way}${size}`;
      const counts = `(${countWords(item.payments_after, "payment")} at the new amount, after `
        + `${formatNumber(item.payments_before)} at the old)`;
      if (item.cadence_changed === true) {
        details.push(`The weekly total went from ${money(item.weekly_equivalent_before)} to `
          + `${money(item.weekly_equivalent_after)}.`);
        details.push(`Payments changed ${amounts} ${counts}.`);
      } else {
        details.push(`The ${before} payment went from ${money(item.amount_before)} to ${money(item.amount_after)} `
          + `${starting} ${counts}.`);
      }
    }
    if (item.schedule_confirmed === false) details.push("The new schedule isn't confirmed yet.");
    // R2-OW18 review round 1: each unreported level with the step into it, then the last step; never a claim about the
    // steps' size (an abrupt last step after a small drift reads as such). An item stored without the step fields names
    // its levels alone. A level names its schedule where the change crosses schedules.
    const levels = (Array.isArray(item.via) ? item.via : []).filter((entry) => entry && typeof entry === "object");
    if (levels.length) {
      const crossing = item.cadence_before !== item.cadence_after;
      const step = (value) => (numberOrNull(value) === null ? "" : ` (${signedPercent(value)})`);
      const level = (schedule, amount, change) => `${crossing ? `${cadence(schedule)} ` : ""}${money(amount)}${step(change)}`;
      const last = numberOrNull(item.last_step_percent) === null ? ""
        : `, then to ${level(item.cadence_after, item.amount_after, item.last_step_percent)}`;
      details.push(`It stepped through ${listWords(levels.map((entry) => level(entry.cadence, entry.amount,
        entry.change_percent)))} on the way${last}.`);
    }
    // Review round 2 of the 2026-10-07 change: a potential lender's label carries its schedule and amount, so the new
    // payments are listed in the lender table under another label; the note names it.
    const labelAfter = item.lender_label_after ? String(item.lender_label_after) : "";
    if (labelAfter && labelAfter !== label) details.push(`The new payments are listed as ${labelAfter}.`);
    if (item.restart === true) {
      also.push(`Also: the new amount started after a pause of ${countWords(item.pause_business_days, "business day")} `
        + "with no payment.");
    }
    if (item.back_to_earlier === true) also.push(`Also: this is back to the earlier ${money(item.amount_after)} payment.`);
    if (item.reverted === true) {
      also.push(`Also: this was temporary; the payment went back to ${money(item.amount_before)} on `
        + `${day(item.reverted_date)}.`);
    }
    if (item.after_funding) {
      // isoDay gives Dates, so the days compare by their time; review round 2: B3's window holds the first day itself.
      const funded = isoDay(item.after_funding.date);
      const started = isoDay(item.first_after_date);
      const when = funded && started && funded.getTime() === started.getTime() ? "the same day the new amount started"
        : funded && started && funded > started ? "just after" : "just before";
      also.push(`Also: ${item.lender || label} deposited ${money(item.after_funding.amount)} on `
        + `${day(item.after_funding.date)}, ${when}; this may be a renewal.`);
    }
  } else if (item.kind === "pause") {
    // R2-OW18 review round 1: a bounced attempt or a payment at another amount can end the pause before the regular
    // payment resumes; the note then says so and names the date payments resumed. Audit round 3, R3-25: so can a
    // catch-up (an exact 2x to 6x debit), named with its multiple, and every other debit of 2x or more inside the gap
    // is named (R3-B05 review round 1: a catch-up after the presence that ended the pause, before payments resumed, is
    // this note's too, one note per event); R3-84's same-amount debits too. R3-MERGE: each in the plain voice.
    headline = "payments paused, then resumed";
    const attempt = item.first_after_kind === "attempt";
    const same = `at the same ${cadence(item.cadence)} ${money(item.last_payment_amount)}`;
    // Review round 1: the grace window is the threshold the pause passed, not the payments' normal rhythm.
    details.push(`No payment${attempt ? " or payment attempt" : ""} between `
      + `${readableDateRange(item.last_before_date, item.first_after_date)} `
      + `(${countWords(item.pause_business_days, "business day")}, more than the `
      + `${formatNumber(item.grace_business_days)} ${scheduleWords(item.cadence)} allows).`);
    if (attempt) {
      details.push(`The attempt on ${day(item.first_after_date)} was returned unpaid, and payments resumed ${same} on `
        + `${day(item.resumed_date)}.`);
    } else if (item.first_after_kind === "catch_up") {
      details.push(`A debit of ${money(item.first_after_amount)} on ${day(item.first_after_date)}, `
        + `${formatNumber(item.first_after_multiple)} times the payment, may be a catch-up, and payments resumed ${same} `
        + `on ${day(item.resumed_date)}.`);
    } else if (item.first_after_kind === "other_amount") {
      details.push(`A payment of another amount came on ${day(item.first_after_date)}, and payments resumed ${same} `
        + `on ${day(item.resumed_date)}.`);
    } else {
      details.push(`Payments then resumed ${same}.`);
    }
    const entries = (list) => (Array.isArray(list) ? list : []).filter((entry) => entry && typeof entry === "object");
    entries(item.catch_ups_inside).forEach((entry) => also.push(`Also: a debit of ${money(entry.amount)} on `
      + `${day(entry.date)}, ${formatNumber(entry.multiple)} times the payment, came before payments resumed; this may `
      + "be a catch-up."));
    entries(item.larger_debits_inside).forEach((entry) => also.push(`Also: a debit of ${money(entry.amount)} on `
      + `${day(entry.date)}, inside the gap, was more than twice the payment.`));
    also.push(...sameAmount(item.last_payment_amount));
  } else if (item.kind === "catch_up") {
    // The owner's answer of 2026-10-07 to audit round 3's R3-25 ("Add a 'Caught up' line"): an exact multiple of the
    // payment after one or more missed scheduled payments, where no pause or stop note names it; its amber "Caught up"
    // chip (lenderPaymentChangeChip). R3-MERGE: in the plain voice of the owner's request of 2026-10-07.
    headline = "missed payments caught up";
    const missed = numberOrNull(item.missed_payments) ?? 0;
    const every = cadence(item.cadence);
    const span = item.missed_last_date && item.missed_first_date && item.missed_last_date !== item.missed_first_date
      ? readableDateRange(item.missed_first_date, item.missed_last_date, "to") : day(item.missed_first_date);
    details.push(`${countWords(missed, `scheduled ${every} payment`)} ${missed === 1 ? "was" : "were"} missed `
      + `(${span}).`);
    details.push(`Then one debit of ${money(item.catch_up_amount)} on ${day(item.catch_up_date)} came to `
      + `${formatNumber(item.multiple)} times the ${every} ${money(item.last_payment_amount)} payment.`);
  } else if (item.kind === "new_stream") {
    const position = numberOrNull(item.position);
    const ordinal = position !== null && position >= 2 ? ORDINAL_WORDS[position - 1] : null;
    headline = ordinal ? `a ${ordinal} payment started` : "another payment started";
    const alongside = (Array.isArray(item.alongside) ? item.alongside : [])
      .filter((other) => other && typeof other === "object")
      .map((other) => `${cadence(other.cadence)} ${money(other.amount)}`);
    details.push(`${ordinal ? `A ${ordinal}` : "Another"} ${cadence(item.cadence_after)} payment of `
      + `${money(item.amount_after)} started on ${day(item.first_after_date)}, alongside the existing `
      + `${alongside.length ? listWords(alongside) : "payments"}.`);
    details.push(`The weekly total went from ${money(item.weekly_total_before)} to ${money(item.weekly_total_after)} `
      + `(${signedPercent(item.change_percent)}).`);
  } else if (item.kind === "stop") {
    // R2-OW18 review round 1: when the last presence is a bounced attempt (and no debit at another amount follows the
    // last payment), the quiet days run from the attempt, and the note says "no payment or payment attempt".
    const others = item.other_debits_after;
    const attempt = !others && Boolean(item.last_attempt_returned);
    const schedule = cadence(item.cadence);
    const quiet = countWords(item.quiet_business_days, "business day");
    const through = day(item.coverage_end);
    // Review round 1: one debit reads in the singular, dated on its own ("on", not "the last on").
    const single = others && numberOrNull(others.count) === 1;
    const later = !others ? "" : single ? "1 debit at another amount"
      : `${countWords(others.count, "debit")} at other amounts`;
    // Audit round 3, R3-25: the later debits that are exact multiples of the payment (2x to 6x) are possible
    // catch-ups, presence like a payment-sized debit; R3-MERGE: named after them, in the plain voice.
    const catchUps = others ? numberOrNull(others.catch_ups) : null;
    const multiples = !catchUps ? ""
      : `; ${single ? "it is" : `${formatNumber(catchUps)} of them ${catchUps === 1 ? "is" : "are"}`} `
        + `${catchUps === 1 ? "an exact multiple" : "exact multiples"} of the payment, which may be a catch-up`;
    const lastOther = !others ? "" : `${single ? "on" : "the last on"} ${day(others.last_date)}${multiples}`;
    // Audit round 3, R3-85: the quiet business days are counted from the last presence, which the note names where it
    // is not the last payment ("after <day>"), as the hosting line's plain voice already reads.
    if (item.stop_confirmed === true) {
      headline = "payments stopped";
      details.push(`Last ${others ? "regular " : ""}${schedule} payment: ${money(item.last_payment_amount)} on `
        + `${day(item.last_payment_date)}.`);
      const presence = item.last_presence_date && item.last_presence_date !== item.last_payment_date
        ? day(item.last_presence_date) : "it";
      if (others) {
        details.push(`After it came only ${later}, ${lastOther}.`);
        details.push(`No payment in the ${quiet} after ${presence}, through ${through}.`);
      } else {
        details.push(`No ${attempt ? "payment or payment attempt" : "payments"} in the ${quiet} after ${presence}, `
          + `through ${through}.`);
      }
    } else {
      headline = "payments may have stopped";
      if (others) {
        // Review round 3 of the 2026-10-07 change: as the confirmed stop reads, the last regular payment once, the
        // debits after it, then the quiet business days that raised the note, counted from the last presence.
        details.push(`Last regular ${schedule} payment: ${money(item.last_payment_amount)} on `
          + `${day(item.last_payment_date)}.`);
        details.push(`After it came only ${later}, ${lastOther}.`);
        const end = item.scope === "package" ? `through ${through}` : "to the end of this statement";
        details.push(`No payment in the ${quiet} after ${day(item.last_presence_date || others.last_date)}, ${end}.`);
      } else {
        const span = item.scope === "package" ? `the last ${quiet}, through ${through}` : `the last ${quiet} of this statement`;
        details.push(`No ${attempt ? "payment or payment attempt" : "payment"} in ${span}.`);
      }
      // Review round 1: the grace window is the threshold of a possible stop, not the payments' normal rhythm.
      details.push(`${sentenceCase(scheduleWords(item.cadence))} allows up to `
        + `${countWords(item.grace_business_days, "business day")} without a payment.`);
      if (!others) details.push(`Last payment: ${money(item.last_payment_amount)} on ${day(item.last_payment_date)}.`);
    }
    if (item.payoff) {
      // Audit round 3, R3-25: the payoff note reads only a debit of 2x or more that is no exact multiple, and counts
      // the earlier ones (R3-MERGE: in the same "Also:" sentence).
      const earlier = numberOrNull(item.payoff.earlier);
      const count = earlier
        ? `, after ${countWords(earlier, "earlier debit")} of twice the payment or more` : "";
      also.push(`Also: a final debit of ${money(item.payoff.amount)} on ${day(item.payoff.date)} may be a payoff${count}.`);
    }
    also.push(...sameAmount(item.last_payment_amount));
    if (item.continues_as) {
      const next = item.continues_as;
      also.push(`Also: payments of ${money(next.amount)} continue under `
        + `${nameOf(next.lender_label || next.lender || "another lender", next.lender_state)} from `
        + `${day(next.first_date)}; this may be a buyout or refinance.`);
    }
    if (item.new_lender_after) {
      const next = item.new_lender_after;
      also.push(`Also: ${nameOf(next.lender_label || next.lender || "another lender", next.lender_state)} started `
        + `${cadence(next.cadence)} payments of ${money(next.amount)} on ${day(next.first_date)}; it may have taken over `
        + "this advance.");
    }
    if (item.debt_relief_after) {
      also.push(`Also: a debt-relief program's payments start on ${day(item.debt_relief_after.date)}; this may mean a `
        + "default or settlement.");
    }
    if (item.continues_in_other_account) {
      const other = item.continues_in_other_account;
      also.push(`Also: payments to ${label} continue from another account `
        + `(${paymentChangeMember(other, "source", sources).label}) from ${day(other.first_date)} at `
        + `${money(other.amount)}.`);
    }
    if (item.reappears_in_other_account) {
      // Audit round 3, R3-83: the funder's first payment or attempt in another account of the deal comes after the
      // stop's grace window, counted in the business days the two accounts' statements cover: named, the stop kept.
      // R3-MERGE: the other account's statement named as continues_in_other_account names it (its month or file).
      const other = item.reappears_in_other_account;
      also.push(`Also: payments to ${label} reappear in another account `
        + `(${paymentChangeMember(other, "source", sources).label}) from ${day(other.first_date)} at `
        + `${money(other.amount)}, after ${countWords(other.covered_business_days, "business day")} without one in the `
        + "statements provided.");
    }
    if (item.other_stream_continues) {
      also.push(`Also: another ${label} payment of ${money(item.other_stream_continues.amount)} `
        + `${cadence(item.other_stream_continues.cadence)} continues.`);
    }
    if (item.last_attempt_returned) {
      also.push(`Also: the last attempt, on ${day(item.last_attempt_returned.date)}, was returned unpaid.`);
    }
  }
  // A lender taking two payments or more: which one the note is about (a new stream's own sentence says so). Review
  // round 1: concurrent streams, not payments in all, and the headline already names the lender.
  const positions = numberOrNull(item.positions);
  if (positions !== null && positions > 1 && item.kind !== "new_stream") {
    const position = numberOrNull(item.position);
    details.push(`This lender has ${formatNumber(positions)} separate payment streams; this note is about the `
      + `${(position !== null && ORDINAL_WORDS[position - 1]) || `number ${formatNumber(item.position)}`}.`);
  }
  const named = item.lender_state === "potential" ? `Potential lender ${label}` : label;
  return lenderNote(`${named}: ${headline}`, details, also, paymentChangeSourceLine(item, sources, across));
}

// The note as one line of text: the copied package memo's line.
function lenderPaymentChangeWarning(item, currency = "USD", sources = null) {
  return lenderNoteText(lenderPaymentChangeNote(item, currency, sources));
}

// R2-OW18 (G2): the chip of a lender payment change; every potential lender's line in the neutral tone.
function lenderPaymentChangeChip(item) {
  const possible = item.schedule_confirmed === false;
  const chips = {
    decrease: ["↓", possible ? "Possible decrease" : "Decreased", "amber"],
    increase: ["↑", possible ? "Possible increase" : "Increased", "blue"],
    cadence_change: ["↻", "Schedule", "blue"],
    pause: ["‖", "Paused", "amber"],
    catch_up: ["↺", "Caught up", "amber"],
    new_stream: ["+", "New stream", "blue"],
    stop: ["■", item.stop_confirmed === true ? "No payments" : "Possible stop", "amber"],
  };
  const [glyph, text, tone] = chips[item.kind] || ["·", "Payment change", "neutral"];
  return glassChip(glyph, text, item.lender_state === "potential" ? "neutral" : tone);
}

// R2-OW18 (G1): the lender table's payment-change notes, above its rows. `paymentChanges` null or undefined is "not
// computed" (an analysis saved before the check), never "no change": with lender rows it shows one neutral note, whose
// words depend on the page. An empty list shows nothing. A package's members not compared across statements show one
// neutral note naming each (by its month or its file, never its job id) with its reason.
function lenderPaymentChangeRowsHtml(paymentChanges, unchecked, currency, hasLenders, isPackage, sources = null) {
  const notChecked = () => glassChip("·", "Not checked", "neutral");
  const lines = [];
  if (Array.isArray(paymentChanges)) {
    paymentChanges.filter((item) => item && typeof item === "object").forEach((item) => lines.push(
      lenderNoteRowHtml(lenderPaymentChangeChip(item), lenderPaymentChangeNote(item, currency, sources))));
  } else if (hasLenders) {
    lines.push(lenderNoteRowHtml(notChecked(), lenderNote("Payment changes not checked", [isPackage
      ? "No statement in this package has been checked yet."
      : "This statement was analysed before the check. Re-analyze it to see payment changes."])));
  }
  const left = (Array.isArray(unchecked) ? unchecked : []).filter((entry) => entry && typeof entry === "object");
  if (isPackage && left.length && hasLenders) {
    const named = left.map((entry) => `${paymentChangeMember(entry, "source", sources).label} `
      + `(${LENDER_PAYMENT_UNCHECKED_WORDS[entry.reason] || labelize(entry.reason)})`);
    lines.push(lenderNoteRowHtml(notChecked(), lenderNote("Payment changes not checked across statements", [
      `${left.length === 1 ? "This statement was" : `These ${formatNumber(left.length)} statements were`} not compared `
        + `with the others: ${named.join("; ")}.`])));
  }
  return lines.join("");
}

// R2-OW18 (G5): the copied statement summary's sentence; empty when the list is empty or missing.
function lenderPaymentChangesSummary(items) {
  const list = (Array.isArray(items) ? items : []).filter((item) => item && typeof item === "object");
  if (!list.length) return "";
  const kinds = [
    ["decrease", (item) => item.kind === "decrease" && item.schedule_confirmed !== false, "decrease", "decreases"],
    ["possible_decrease", (item) => item.kind === "decrease" && item.schedule_confirmed === false, "possible decrease", "possible decreases"],
    ["increase", (item) => item.kind === "increase" && item.schedule_confirmed !== false, "increase", "increases"],
    ["possible_increase", (item) => item.kind === "increase" && item.schedule_confirmed === false, "possible increase", "possible increases"],
    ["cadence_change", (item) => item.kind === "cadence_change", "schedule change", "schedule changes"],
    ["pause", (item) => item.kind === "pause", "pause", "pauses"],
    ["catch_up", (item) => item.kind === "catch_up", "catch-up", "catch-ups"],
    ["new_stream", (item) => item.kind === "new_stream", "new stream", "new streams"],
    ["stop", (item) => item.kind === "stop" && item.stop_confirmed !== true, "possible stop", "possible stops"],
    ["confirmed_stop", (item) => item.kind === "stop" && item.stop_confirmed === true, "stop with no payments", "stops with no payments"],
  ];
  const parts = kinds.map(([, test, one, many]) => {
    const count = list.filter(test).length;
    return count ? `${count} ${count === 1 ? one : many}` : "";
  }).filter(Boolean);
  const potential = list.filter((item) => item.lender_state === "potential").length;
  return `Lender payment changes: ${parts.join(", ")}${potential ? ` (${potential} potential)` : ""}.`;
}

// The Withholding Basis card's note: the basis the withholding rates divide by. Audit B11 (I34): the legacy basis is
// named for what it is, gross deposits less lender funding and never True revenue (a payload with no mode was analysed
// on it). Owner ruling 2026-10-02 (the underwriter's Q7; R2-OW14): True revenue is the default; a revenue basis reads
// '<label>: <definition>' ('True revenue: verified plus counted credits'), the definition's own leading label dropped.
function activeDenominatorNote(metrics = {}) {
  const mode = metrics.withholding_denominator_mode;
  if (!mode || mode === "legacy_eligible_deposits") return LEGACY_ELIGIBLE_DEPOSITS_NOTE;
  const label = withholdingBasisLabel(metrics);
  let definition = metrics.eligible_deposit_definition || WITHHOLDING_BASIS_DEFINITIONS[mode]
    || "deposits used to calculate withholding rates";
  if (definition.toLowerCase().startsWith(`${label.toLowerCase()}:`)) {
    definition = definition.slice(label.length + 1).trim();
  }
  return `${label}: ${definition}`;
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
  // R2-OW14 (Q7): the note names the basis, True revenue by default.
  const label = withholdingBasisLabel(metrics).toLowerCase();
  // Audit round 3, R3-B03 (R3-27): no exposure over the sum of members analysed under different bases.
  if (withholdingBasisMixed(metrics)) {
    return `${formatMoney(total, currency)} potential lender debits; the statements were analysed on different `
      + "withholding bases, so no exposure is published; analyst review is required";
  }
  // F1 (final review of round 2): no exposure over a basis that is not established.
  if (withholdingBasisUnestablished(metrics)) {
    return `${formatMoney(total, currency)} potential lender debits; the withholding basis (${label}) is not `
      + "established, so no exposure is published; analyst review is required";
  }
  // Audit round 3, R3-B03 (R3-20): nor over a revenue basis under the floor.
  if (withholdingBasisBelowFloor(metrics)) {
    return `${formatMoney(total, currency)} potential lender debits; the withholding basis `
      + `(${withholdingBasisWithAmount(metrics, currency)}) is under ${formatMoney(WITHHOLDING_BASIS_FLOOR, currency)}, so `
      + "no exposure is published; analyst review is required";
  }
  if ((numberOrNull(denominator) ?? 0) <= 0) {
    return `${formatMoney(total, currency)} potential lender debits; the withholding basis (${label}) is unavailable${reviewSuffix}`;
  }
  return `${formatMoney(total, currency)} potential lender debits divided by ${formatMoney(denominator, currency)} ${label}${reviewSuffix}`;
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
// 5.6 carries no tier, so its credits keep their revenue state's tag. R2-OW03: a non_revenue row that carries a
// non-revenue code (the Zelle policy's, Q12's display reason) names it too; a reviewer's rejection keeps its counted or
// held code, which is none, and reads "Non-revenue".
const REVENUE_TIER_TAGS = Object.freeze({
  verified: () => ({ label: "Verified revenue", glyph: "VER", tone: "green" }),
  counted_flagged: (record) => ({ label: `Counted: ${revenueReasonLabel(record)}`, glyph: "CNT", tone: "teal" }),
  excluded_pending_review: (record) => ({ label: `Held: ${revenueReasonLabel(record)}`, glyph: "?", tone: "amber" }),
  non_revenue: (record) => ({
    label: nonRevenueReason(record && record.revenue_tier_reason) ? `Non-revenue: ${revenueReasonLabel(record)}` : "Non-revenue",
    glyph: "X",
    tone: "neutral",
  }),
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

// R2-OW03 (owner ruling 2026-10-02): the ledger filter behind one code of the non-revenue breakdown is
// "non_revenue:<code>". Null for any other filter.
function excludedReasonFilter(filter) {
  const match = /^non_revenue:([a-z_0-9]+)$/.exec(String(filter || ""));
  return match ? match[1] : null;
}

// Owner ruling 2026-10-02 (the underwriter's Q6; R2-OW15): the ledger filter behind a package match's kind is
// "packageMatch:<kind>" (the rows the package passes matched, both legs), and the one behind a debit flag
// "debitFlag:<kind>" (the debits flagged, never deducted). Null for any other filter.
function packageMatchFilter(filter) {
  const match = /^packageMatch:([a-z_]+)$/.exec(String(filter || ""));
  return match ? match[1] : null;
}

function debitFlagFilter(filter) {
  const match = /^debitFlag:([a-z_]+)$/.exec(String(filter || ""));
  return match ? match[1] : null;
}

// The words of each debit flag (webapp/app.py debit_side_flags' kinds), on the True card, the Revenue evidence table and
// the ledger's header.
const DEBIT_FLAG_WORDS = Object.freeze({
  unmatched_deposit_return: "Returned deposits not matched",
  processor_chargeback: "Processor chargebacks and adjustments",
});
// Audit round 3, R3-B24 (R3-16; true revenue spec §10.1, §10.6; standard G7, P22): the large unsourced deposits' words,
// on the True card, the Revenue evidence table and the ledger's header, and their ledger filter (information only).
const LARGE_DEPOSIT_WORDS = "Large deposits to source";
const LARGE_DEPOSIT_FILTER = "largeDeposit";
const PACKAGE_MATCH_WORDS = Object.freeze({
  returned_deposit: "bounced deposits matched across statements",
  // R2-OW16 (the underwriter's Q4): both legs of each transfer between the business's accounts.
  own_account_transfer: "rows of transfers between the business's accounts",
});

// The debit flags of the rows on screen: a statement's, from its served metrics (`<kind>_locations`), or a package's,
// from its `debit_flags` (each naming its statement, account and location). `has(tx, kind, position)` and `entry(tx)`.
// Audit round 3, R3-B24 (R3-16): and `largeDeposit(tx, position)`, the served large unsourced deposit a credit row is (a
// statement's `metrics.large_unsourced_deposits` by location, a package's `large_unsourced_deposits` by statement,
// account and location), or null.
function statementDebitFlags(metrics) {
  const m = metrics || {};
  const locations = Object.fromEntries(Object.keys(DEBIT_FLAG_WORDS)
    .map((kind) => [kind, new Set(Array.isArray(m[`${kind}_locations`]) ? m[`${kind}_locations`] : [])]));
  const large = new Map((Array.isArray(m.large_unsourced_deposits) ? m.large_unsourced_deposits : [])
    .filter((item) => item && typeof item === "object").map((item) => [item.source_location, item]));
  return {
    has: (tx, kind, position = null) => Boolean(locations[kind]) && locations[kind].has(rowSourceLocation(tx, position)),
    entry: () => null,
    largeDeposit: (tx, position = null) => (txAmount(tx) > 0 && large.get(rowSourceLocation(tx, position))) || null,
  };
}

function debitFlagKey(job, account, location) {
  return `${job ?? ""}|${account ?? ""}|${location ?? ""}`;
}

function packageDebitFlags(pkg) {
  const flags = new Map();
  (Array.isArray(pkg && pkg.debit_flags) ? pkg.debit_flags : []).forEach((flag) => {
    if (flag && typeof flag === "object") flags.set(debitFlagKey(flag.source_job, flag.source_account, flag.source_location), flag);
  });
  const entry = (tx) => flags.get(debitFlagKey(tx.source_job, tx.source_account, transactionClassification(tx).source_location)) || null;
  // R3-B24 (R3-16): the members' large unsourced deposits, keyed as the debit flags are.
  const large = new Map();
  (Array.isArray(pkg && pkg.large_unsourced_deposits) ? pkg.large_unsourced_deposits : []).forEach((item) => {
    if (item && typeof item === "object") large.set(debitFlagKey(item.source_job, item.source_account, item.source_location), item);
  });
  const largeDeposit = (tx) => (txAmount(tx) > 0
    && large.get(debitFlagKey(tx.source_job, tx.source_account, transactionClassification(tx).source_location))) || null;
  return { has: (tx, kind) => (entry(tx) || {}).kind === kind, entry, largeDeposit };
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
  const excludedReason = excludedReasonFilter(filter);
  if (excludedReason) return `excluded: ${lower(revenueReasonLabel({ revenue_tier_reason: excludedReason }))}`;
  // R2-OW15: the package passes' matches and the debit flags.
  const matchKind = packageMatchFilter(filter);
  if (matchKind) return PACKAGE_MATCH_WORDS[matchKind] || "rows matched across statements";
  const flagKind = debitFlagFilter(filter);
  if (flagKind) return lower(DEBIT_FLAG_WORDS[flagKind] || "flagged debits");
  // Audit round 3, R3-B24 (R3-16): "large deposits to source", one "large deposit to source".
  if (filter === LARGE_DEPOSIT_FILTER) {
    return count === 1 ? lower(LARGE_DEPOSIT_WORDS).replace("deposits", "deposit") : lower(LARGE_DEPOSIT_WORDS);
  }
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

function filterTransactions(transactions, filter, canonicalEntity = null, nsfDays = null, debitFlags = null) {
  let matched = transactions;
  const flagGroup = flaggedFilterGroup(filter);
  // Owner ruling 2026-10-02 (the underwriter's Q6; R2-OW15): a package match's rows, and a debit flag's rows.
  const matchKind = packageMatchFilter(filter);
  if (matchKind) {
    matched = transactions.filter((tx) => (transactionClassification(tx).package_match || {}).kind === matchKind);
  }
  const flagKind = debitFlagFilter(filter);
  if (flagKind) {
    matched = debitFlags ? transactions.filter((tx, position) => debitFlags.has(tx, flagKind, position)) : [];
  }
  // Audit round 3, R3-B24 (R3-16): the large unsourced deposits the statement or package serves.
  if (filter === LARGE_DEPOSIT_FILTER) {
    matched = debitFlags && typeof debitFlags.largeDeposit === "function"
      ? transactions.filter((tx, position) => Boolean(debitFlags.largeDeposit(tx, position))) : [];
  }
  if (filter === "nsf") matched = nsfDays ? transactions.filter((tx, position) => nsfDays.has(tx, position)) : [];
  if (filter === "nsf_fees") {
    matched = transactions.filter((tx) => transactionClassification(tx).classification === "nsf_or_return");
  }
  // The withholding flag, and (audit round 3, R3-B02: R3-73) a returned funder payment its funder re-debited, which
  // left the rate but is still a lender row, and (R3-B03: R3-79) a lump-sum payoff, paid and out of the rate.
  if (filter === "lender") {
    matched = transactions.filter((tx) => transactionClassification(tx).contributes_to_withholding_rate === true
      || Boolean(transactionClassification(tx).returned_funder_payment_by)
      || (Boolean(transactionClassification(tx).lump_sum_payoff)
        && transactionClassification(tx).contributes_to_lender_totals === true));
  }
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
  const excludedReason = excludedReasonFilter(filter);
  if (excludedReason) {
    matched = transactions.filter((tx) => {
      const record = transactionClassification(tx);
      return txAmount(tx) > 0 && record.revenue_tier === "non_revenue" && record.revenue_tier_reason === excludedReason;
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
  // Audit round 3, R3-B02 (R3-21; spec §10.7): a credit that returns a confirmed funder's payment is never confirmed,
  // so it has no multi-select box: a bulk Confirm never carries it, and the all-or-nothing batch never refuses on it.
  if (record.returns_funder_payment) return null;
  if (record.revenue_review_status === "confirmed" || record.revenue_review_status === "rejected") return null;
  const jobId = tx.source_job || fallbackJobId;
  const sourceLocation = record.source_location;
  return jobId && sourceLocation ? { jobId, account: reviewAccountOf(tx, fallbackAccount), sourceLocation } : null;
}

// The review a credit may take (true revenue spec §10.7), as the server allows it: "both" (Confirm Revenue and Mark
// Non-Revenue) for a credit the classifier left unverified (held or counted), "reject" (Mark Non-Revenue only) for a
// credit a rule verified, "" for anything else. An analysis saved before 5.6 carries no tier and keeps its rules: only
// a credit left unverified is reviewed. R2-OW03 (the underwriter's Q3, "I can review"): "confirm" (Confirm Revenue only)
// for a Zelle deposit the owner's policy excluded; the server refuses a reject on it, the row being non-revenue already.
function revenueReviewKind(record) {
  // Audit round 3, R3-B02 (R3-21): a credit that returns a confirmed funder's payment (rule D's pair) is the business's
  // own payment coming back: the server refuses its Confirm, so a held or counted one shows Mark Non-Revenue only and a
  // Zelle deposit the policy excluded, whose only control is Confirm, shows none. Any other keeps its kind (review
  // round 1: a credit a rule verified keeps Mark Non-Revenue).
  if (record.returns_funder_payment) {
    if (record.revenue_initial_classification === "unverified_deposit") return "reject";
    if (record.revenue_initial_classification === "non_revenue" && typeof record.revenue_tier === "string"
      && REVIEWABLE_NON_REVENUE_REASONS.includes(record.revenue_tier_reason)) return "";
  }
  if (record.revenue_initial_classification === "unverified_deposit") return "both";
  if (record.revenue_initial_classification === "verified_revenue" && typeof record.revenue_tier === "string") return "reject";
  if (record.revenue_initial_classification === "non_revenue" && typeof record.revenue_tier === "string"
    && REVIEWABLE_NON_REVENUE_REASONS.includes(record.revenue_tier_reason)) return "confirm";
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
  const confirm = kind === "both" || kind === "confirm"
    ? `<button class="table-action review-confirm" type="button" ${common} data-revenue-review-action="confirm" aria-label="Confirm this deposit as operating revenue">Confirm Revenue</button>`
    : "";
  // R2-OW03: a Zelle deposit the owner's policy excluded is non-revenue already, so it shows Confirm Revenue only.
  const reject = kind === "confirm"
    ? ""
    : `<button class="table-action review-reject" type="button" ${common} data-revenue-review-action="reject" aria-label="Exclude this deposit from operating revenue">Mark Non-Revenue</button>`;
  return `
    <div class="revenue-review-actions">
      ${confirm}
      ${reject}
    </div>
  `;
}

// Audit round 3, R3-B20 (R3-51; true revenue spec §10.6, §10.7): the context signal that keeps the rules' own
// reading of a Zelle deposit the policy excluded ('zelle_prior:<tier>:<reason>'); analysis/true_revenue.py
// `_ZELLE_PRIOR`.
const ZELLE_PRIOR_SIGNAL = "zelle_prior:";

// R3-51: the tier and reason the rules gave a Zelle deposit the policy excluded, {tier, reason} (reason null where none
// was recorded), or null for any other row. It mirrors analysis/true_revenue.py `zelle_prior_reading`: the first signal
// with the prefix, split at its first colon.
function zellePriorReading(record) {
  const signals = record && Array.isArray(record.revenue_context_signals) ? record.revenue_context_signals : [];
  const signal = signals.find((entry) => typeof entry === "string" && entry.startsWith(ZELLE_PRIOR_SIGNAL));
  if (signal === undefined) return null;
  const rest = signal.slice(ZELLE_PRIOR_SIGNAL.length);
  const colon = rest.indexOf(":");
  if (colon < 0) return { tier: rest, reason: null };
  return { tier: rest.slice(0, colon), reason: rest.slice(colon + 1) || null };
}

// R3-51: under No, the sentence an excluded Zelle deposit adds on the reading the rules give it with Zelle counted,
// so a reviewer sees a hold before the one-click Confirm releases it (in both settings, §17.1 default (4)); "" without
// a prior. The label is the reason's (REVENUE_TIER_REASONS), or the code itself where the table lacks it, as
// true_revenue `_zelle_excluded` names it.
function zellePriorSentence(record) {
  const prior = zellePriorReading(record);
  if (!prior) return "";
  const entry = REVENUE_TIER_REASONS[prior.reason];
  const label = entry ? entry[1] : (prior.reason || prior.tier);
  if (prior.tier === "excluded_pending_review") {
    return ` With Zelle counted (Yes), the rules hold it for review: ${label}.`
      + " Confirm Revenue releases it in both settings.";
  }
  if (prior.tier === "counted_flagged") return ` With Zelle counted (Yes), it counts as: ${label}.`;
  if (prior.tier === "verified") return " With Zelle counted (Yes), it is Verified revenue.";
  return "";
}

function revenueReviewReason(tx) {
  const record = transactionClassification(tx);
  if (txAmount(tx) <= 0) return "";
  // 5.6 (true revenue spec §10.6): a counted or held credit names its reason, and one sentence on it.
  const entry = REVENUE_TIER_REASONS[record.revenue_tier_reason];
  // R2-OW03: so does a non_revenue row that carries a non-revenue code (the Zelle policy's, Q12's display reason).
  // Audit round 3, R3-B20 (R3-51): a Zelle deposit the policy excluded adds the rules' reading with Zelle counted.
  if (entry && record.revenue_tier === "non_revenue" && entry[0] === "non_revenue") {
    const prior = record.revenue_tier_reason === "zelle_excluded" ? zellePriorSentence(record) : "";
    return `${entry[1]}. ${entry[2]}${prior}`;
  }
  if (entry && (record.revenue_tier === "counted_flagged" || record.revenue_tier === "excluded_pending_review")) {
    // Audit round 2, R2-B07 (R07): a credit the reader marked unread carries the payer blocks it could not attribute
    // to one row (unread_payer_text), printed so a reviewer can release a customer's row a lender's block held.
    const unread = typeof tx.unread_payer_text === "string" ? tx.unread_payer_text.trim() : "";
    // Audit round 3, R3-B09 (R3-91): a held wire or bare transfer whose reader kept a payer line it could not
    // attribute says so, never that no sender was printed; the reason code, its tag and the hold are unchanged.
    const unattributed = {wire_no_sender: "Wire", transfer_no_counterparty: "Transfer"}[record.revenue_tier_reason];
    if (unread && unattributed && record.revenue_tier === "excluded_pending_review") {
      return `${unattributed}, payer line not read. The statement prints a payer line under this row that the reader `
        + `could not attribute to it; it stays held for review. Unread payer text: ${unread}`;
    }
    return unread ? `${entry[1]}. ${entry[2]} Unread payer blocks: ${unread}` : `${entry[1]}. ${entry[2]}`;
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

// Owner ruling 2026-10-02 (the underwriter's Q1, "look at the day $ amount got deposited and see if there is a frequent
// payment following the deposit"; true revenue spec §8.5, §10.7; R2-OW12): a held wire with no sender printed names
// each Lenders or Potential Lenders series that starts after it (`revenue_funding_series`), one line each, beside
// R2-B07's unread payer blocks under the reason. A review aid read after the tier: a decided row, any other row and a
// payload analysed before the field show none, and the badge, the Held for Review grouping and the gate never read it.
function fundingSeriesNotes(tx, currency = "USD") {
  const record = transactionClassification(tx);
  if (record.revenue_tier !== "excluded_pending_review" || record.revenue_tier_reason !== "wire_no_sender") return [];
  const series = Array.isArray(record.revenue_funding_series) ? record.revenue_funding_series : [];
  return series.filter((item) => item && typeof item === "object").map((item) => {
    const cadence = String(item.cadence || "");
    const days = Number(item.days_after) || 0;
    const payments = Number(item.payments) || 0;
    const detail = `${cadence.charAt(0).toUpperCase()}${cadence.slice(1)} ${formatMoney(item.amount, currency)} to `
      + `${item.payee} from ${item.first_date} (${days} ${days === 1 ? "day" : "days"} after, `
      + `${payments} ${payments === 1 ? "payment" : "payments"})`;
    return item.start_observed
      ? `Recurring payments start after this deposit: possible funding. ${detail}.`
      : `Recurring payments follow this deposit: possible funding. ${detail}; the statement begins too close to this `
        + "deposit to show whether they ran before it.";
  });
}

// Owner ruling 2026-10-02 (the underwriter's Q5; true revenue spec §10.6; R2-OW13): a confirmed funder's payment the
// bank returned unpaid carries a Returned chip in the ledger (out of paid, still in the withholding rate).
function returnedFunderChip(tx) {
  const record = transactionClassification(tx);
  return txAmount(tx) < 0 && record.returned_funder_payment_by ? glassChip("↩", "Returned", "amber") : "";
}

// The return credit names the payment it returns, read from the debit among the rows drawn from (the same statement
// and account in a package), so a held one says why it is held; its tier and reason are its own, unchanged.
function returnedFunderNotes(tx, rows = []) {
  const record = transactionClassification(tx);
  const location = record.returns_funder_payment;
  if (!location || txAmount(tx) <= 0) return [];
  const debit = rows.find((row) => row && transactionClassification(row).source_location === location
    && (row.source_job ?? null) === (tx.source_job ?? null) && (row.source_account ?? null) === (tx.source_account ?? null));
  if (!debit) return [`Returns a confirmed funder's payment (${location})`];
  const line = `Returns the ${debit.date || "undated"} payment to ${transactionClassification(debit).canonical_entity || "a confirmed funder"}`;
  // Audit round 3, R3-B02 (R3-21): a credit a reviewer could otherwise confirm (left unverified, or a Zelle deposit the
  // policy excluded) says why its Confirm is gone; a credit a non-revenue rule decided reads as before.
  const reviewable = record.revenue_initial_classification === "unverified_deposit"
    || (record.revenue_initial_classification === "non_revenue" && typeof record.revenue_tier === "string"
      && REVIEWABLE_NON_REVENUE_REASONS.includes(record.revenue_tier_reason));
  return [reviewable ? `${line}: the business's own payment coming back, so it cannot be confirmed as revenue` : line];
}

// Owner ruling 2026-10-02 (the underwriter's Q6; true revenue spec §10.6, §10.7; R2-OW15): what the package passes say on
// a row of the package ledger: a deposit they took out of True names its return (Confirm Revenue still overrides the
// match), the return names the deposit, and a return they could not match because the analyst confirmed its nearest
// deposit names that deposit. A statement viewed alone shows none.
function packageMatchNotes(tx, debitFlags = null) {
  const match = transactionClassification(tx).package_match;
  const notes = [];
  if (match && match.kind === "returned_deposit") {
    if (match.debit && txAmount(tx) > 0) {
      notes.push(`Returned on ${match.debit.date || "an unknown date"} (${match.debit.filename || "another statement"}): `
        + "not counted. Confirm Revenue overrides the match.");
    } else if (match.credit && txAmount(tx) < 0) {
      notes.push(`Returns the ${match.credit.date || "undated"} deposit in ${match.credit.filename || "another statement"}.`);
    }
  }
  // Owner ruling 2026-10-02 (the underwriter's Q4; true revenue spec §10.6, §10.7; R2-OW16): a deposit pass 2 held names
  // the transfer out of the other account and how its release works, an already-held deposit names the transfer it
  // also matches (nothing about it moved), and the transfer out names the deposit.
  if (match && match.kind === "own_account_transfer") {
    if (match.debit && txAmount(tx) > 0) {
      const debit = match.debit;
      const from = `${debit.bank || "another account"}${debit.last4 ? ` ••${debit.last4}` : ""} on `
        + `${debit.date || "an unknown date"} (${debit.filename || "another statement"})`;
      if (match.moved === true) {
        const gap = numberOrNull(match.gap_days);
        const when = gap === 0 ? "the same day" : gap === 1 ? "1 day earlier" : `${gap ?? "some"} days earlier`;
        notes.push(`Transfer out of ${from}, ${when}. Confirm Revenue releases it into True and marks it Verified; `
          + "Mark Non-Revenue keeps it out.");
      } else {
        notes.push(`Also matches a transfer out of ${from}.`);
      }
    } else if (match.credit && txAmount(tx) < 0) {
      notes.push(`Matched to the ${match.credit.date || "undated"} deposit into `
        + `${match.credit.last4 ? `••${match.credit.last4}` : "another account"} `
        + `(${match.moved === true ? "held" : "already held"}).`);
    }
  }
  // The final review of round 2, F2(b) (the underwriter's Q5 across statements): a confirmed funder's payment returned
  // in the next statement names the return, and the return names the payment.
  if (match && match.kind === "returned_funder_payment") {
    if (match.credit && txAmount(tx) < 0) {
      // Audit round 3, R3-B02 (review round 1): one the package's pass 5 found re-debited is out of the rate, its
      // re-debit counting the obligation once.
      const rate = transactionClassification(tx).represented_by
        ? "counted once in the withholding rate, by its re-debit." : "still in the withholding rate.";
      notes.push(`Returned unpaid on ${match.credit.date || "an unknown date"} (${match.credit.filename || "the next statement"}): `
        + `out of paid to lenders, ${rate}`);
    } else if (match.debit && txAmount(tx) > 0) {
      notes.push(`Returns the ${match.debit.date || "undated"} payment to ${match.debit.funder || "a confirmed funder"} in `
        + `${match.debit.filename || "the previous statement"}.`);
    }
  }
  const flag = debitFlags && txAmount(tx) < 0 ? debitFlags.entry(tx) : null;
  const decided = flag && flag.candidate_decided;
  if (decided && decided.decision === "confirmed") {
    notes.push(`Matches the ${decided.date || "undated"} deposit you confirmed in ${decided.filename || "another statement"}; review.`);
  }
  return notes;
}

// Audit round 3, R3-B24 (R3-16; true revenue spec §10.6; standard G7, P22): a credit the served payload flags as a large
// unsourced deposit asks for its source under its reason, on the statement page, the statement window and the package
// ledger: "Large deposit: S% of True revenue, counted without proof of the sale. Ask for its source." (a package's
// share is of its statement's True as the package counts it, the True Deposits its row shows on the package page, and
// says so). Information only: its tier, tag and review controls are unchanged.
function largeDepositNotes(tx, debitFlags = null) {
  const item = debitFlags && typeof debitFlags.largeDeposit === "function" ? debitFlags.largeDeposit(tx) : null;
  if (!item) return [];
  const share = numberOrNull(item.share_of_true_percent);
  const of = "source_job" in item ? "its statement's True revenue" : "True revenue";
  return [`Large deposit: ${share === null ? "N/A" : `${share.toFixed(1)}%`} of ${of}, counted without proof of the `
    + "sale. Ask for its source."];
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
    debitFlags = null,
  } = options;
  const rows = Array.isArray(transactions) ? transactions : [];
  const matched = sortTransactions(filterTransactions(rows, filter, canonicalEntity, nsfDays, debitFlags), sort);
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
    // R2-OW12 (the underwriter's Q1): a held no-sender wire's funding aid, one line per series under the reason.
    const reviewReasonHtml = (reviewReason
      ? `<div class="tx-reason"><strong>Reason:</strong> ${escapeHtml(reviewReason)}</div>`
      : "") + fundingSeriesNotes(tx, rowCurrency)
      .map((line) => `<div class="tx-reason tx-funding">${escapeHtml(line)}</div>`).join("")
      // R2-OW13 (the underwriter's Q5): a return credit names the funder payment it returns.
      + returnedFunderNotes(tx, rows)
        .map((line) => `<div class="tx-reason tx-returned">${escapeHtml(line)}</div>`).join("")
      // R2-OW15 (the underwriter's Q6): the package passes' notes.
      + packageMatchNotes(tx, debitFlags)
        .map((line) => `<div class="tx-reason tx-package-match">${escapeHtml(line)}</div>`).join("")
      // Audit round 3, R3-B24 (R3-16): a large unsourced deposit asks for its source.
      + largeDepositNotes(tx, debitFlags)
        .map((line) => `<div class="tx-reason tx-large-deposit">${escapeHtml(line)}</div>`).join("");
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
        <td>${glassChip(category.glyph, category.label, category.tone)}${zelleChip(tx)}${flaggedChip(tx)}${returnedFunderChip(tx)}${revenueSourceChip(tx)}${reviewReasonHtml}</td>
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
      // R2-OW15 (the underwriter's Q6): the package's debit flags, each naming its statement.
      debitFlags: packageDebitFlags(pkg),
    };
  }
  const statement = currentAnalysis?.statement || {};
  return {
    transactions: getTransactions(statement),
    currency: statement.currency || "USD",
    multi: false,
    nsfDays: statementNsfDays(currentAnalysis?.metrics),
    debitFlags: statementDebitFlags(currentAnalysis?.metrics),
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
      debitFlags: ctx.debitFlags,
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
      debitFlags: statementDebitFlags(modalAnalysis?.metrics),
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
      <div class="table-cell-detail">${escapeHtml(formatMoney(denominator, currency))} withholding basis</div>
    `
    : isPotential ? "N/A" : "--";
  // A package's lender rows say how many of its statements the lender appears in.
  const statements = numberOrNull(funder.documents);
  const statementsDetail = statements !== null
    ? `<div class="table-cell-detail">Across ${escapeHtml(formatNumber(statements))} ${statements === 1 ? "statement" : "statements"}</div>`
    : "";
  // Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): a confirmed funder's payments returned unpaid, never in
  // its count or total (paid), named beside them; the funder stays listed when every payment bounced.
  const returnedCount = isPotential ? 0 : (numberOrNull(funder.returned_payment_count) ?? 0);
  const returnedDetail = returnedCount > 0
    ? `<div class="table-cell-detail">${escapeHtml(`${formatNumber(returnedCount)} returned `
      + `${returnedCount === 1 ? "payment" : "payments"}, ${formatMoney(funder.returned_payment_total, currency)}, `
      + "not in paid")}</div>`
    : "";
  return `
    <tr>
      <td>${lenderEvidenceControl(funder, isPotential)}${statementsDetail}</td>
      <td>${escapeHtml(isPotential ? "Potential lender" : "Confirmed lender")}</td>
      <td>${escapeHtml(formatNumber(count))}</td>
      <td>${escapeHtml(formatMoney(total, currency))}${returnedDetail}</td>
      <td>${potentialWithholding}</td>
      <td>${glassChip(isPotential ? "?" : "LEN", isPotential ? "Review required" : "Confirmed", isPotential ? "amber" : "violet")}${returnedCount > 0 ? glassChip("↩", "Returned", "amber") : ""}</td>
    </tr>
  `;
}

function renderLenders(funders, potentialLenders = [], currency = "USD", returnedPayments = [], paymentChanges = null,
  unchecked = [], isPackage = false, documents = null, lumpSums = []) {
  const confirmed = Array.isArray(funders) ? funders : [];
  const potential = Array.isArray(potentialLenders) ? potentialLenders : [];
  const lenders = [
    ...confirmed.map((item) => ({ ...item, classification: "confirmed_lender" })),
    ...potential.map((item) => ({ ...item, classification: "potential_lender" })),
  ];
  els.lenderCount.textContent = `${confirmed.length} confirmed, ${potential.length} potential`;
  // R2-OW13 (the underwriter's Q5): one amber note per returned funder payment, above the lender rows. R2-OW18 (the
  // owner's request of 2026-10-06): then one note per lender payment change, or the neutral not-checked note. Both
  // render above "No lenders detected" too (the early return used to drop R2-OW13's lines). The owner's request of
  // 2026-10-07: a package's notes name their statements from its rows (`documents`).
  const sources = Array.isArray(documents) ? paymentChangeSources(documents) : null;
  // Audit round 4, R4-76: each note reads whether its re-debit was returned too (withReDebitReturns).
  const warnings = withReDebitReturns(returnedPayments)
    .filter((item) => item && typeof item === "object")
    .map((item) => lenderNoteRowHtml(glassChip("!", "Returned", "amber"), returnedFunderPaymentNote(item, currency, sources)))
    .join("")
    // Audit round 3, R3-B03 (R3-79): one information note per lump-sum payoff, after the returned notes.
    + lumpSumPayoffRowsHtml(lumpSums, currency, sources)
    + lenderPaymentChangeRowsHtml(paymentChanges, unchecked, currency, lenders.length > 0, isPackage, sources);
  if (!lenders.length) {
    els.lenderTable.innerHTML = warnings + `
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
  els.lenderTable.innerHTML = warnings + lenders.map((funder) => lenderRowHtml(funder, currency)).join("");
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
// Counted (audit B11) and Non-Revenue (R2-OW03: its codes, the Zelle policy's and Q12's) are broken down the same way.
const revenueRows = [
  ["true_revenue", "True Revenue", "REV", "Revenue", "green", "revenue_established"],
  ["verified_revenue", "Verified Revenue", "VER", "Verified", "green", "verified_revenue_established"],
  ["counted_flagged", "Counted, Not Verified", "CNT", "Counted", "teal", "revenue_established"],
  ["excluded_pending_review", "Held for Review", "?", "Review Required", "amber", "revenue_established"],
  ["non_revenue", "Non-Revenue", "X", "Excluded", "neutral", null],
];

// The credits of one middle tier of a statement or a package by reason, largest total first (ties by code), or []
// where they are not established. `tier` is counted_flagged or excluded_pending_review. R2-OW03 (owner ruling
// 2026-10-02): or non_revenue, the non-revenue breakdown, read whenever it is an object (Non-revenue stays where
// revenue is not established, §10.4).
function tierReasonEntries(source = {}, tier = "excluded_pending_review") {
  const key = `${tier}_by_reason`;
  const shown = tier === "non_revenue" || (source && source.revenue_established === true);
  const byReason = source && shown && source[key] && typeof source[key] === "object" ? source[key] : {};
  return Object.entries(byReason)
    .map(([reason, figures]) => ({ reason, count: figures && figures.count, total: numberOrNull(figures && figures.total) }))
    .sort((a, b) => (b.total ?? 0) - (a.total ?? 0) || a.reason.localeCompare(b.reason));
}

// The held credits by reason: the Held for Review view.
function heldReasonEntries(source = {}) {
  return tierReasonEntries(source, "excluded_pending_review");
}

// The words naming one middle tier's reason rows in the evidence table. R2-OW03: and the non-revenue breakdown's,
// filtered as "non_revenue:<code>".
const TIER_REASON_ROW_WORDS = Object.freeze({
  counted_flagged: "counted", excluded_pending_review: "held", non_revenue: "excluded",
});

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
    `).join("")
      // Audit round 3, R3-B24 (R3-16): after the counted and held reasons, the large unsourced deposits' row.
      + (filter === "excluded_pending_review" ? largeDepositEvidenceRowHtml(metrics, currency, filterAttribute) : "");
  }).join("") + debitFlagEvidenceRowsHtml(metrics, currency, filterAttribute);
}

// Audit round 3, R3-B24 (R3-16; true revenue spec §10.1, §10.6, §10.7; standard G7, P22): one row, where a statement or
// package serves a large unsourced deposit, whose button filters the ledger to the flagged rows ("largeDeposit"); its
// count, its total (N/A where a package refuses its money) and a "Source it" chip. The reviewer's path to them: the
// badge, the Held for Review view and the decisions never read it.
function largeDepositEvidenceRowHtml(source = {}, currency = "USD", filterAttribute = "data-revenue-filter") {
  const count = numberOrNull(source && source.large_unsourced_deposit_count);
  if (!count) return "";
  return `
      <tr class="evidence-flag-row">
        <td><button class="evidence-link" type="button" ${filterAttribute}="${LARGE_DEPOSIT_FILTER}" aria-label="Show the ${escapeHtml(LARGE_DEPOSIT_WORDS.toLowerCase())}">${escapeHtml(LARGE_DEPOSIT_WORDS)}</button></td>
        <td>${escapeHtml(formatNumber(count))}</td>
        <td>${escapeHtml(formatMoney(source.large_unsourced_deposit_total, currency))}</td>
        <td>${glassChip("!", "Source it", "amber")}</td>
      </tr>
    `;
}

// Owner ruling 2026-10-02 (the underwriter's Q6; true revenue spec §10.1, §10.6; R2-OW15): after the credits, a row per
// debit flag the statement or package carries, each filtering the ledger to its debits ("debitFlag:<kind>"); never a
// figure of True, so it reads "Not deducted".
function debitFlagEvidenceRowsHtml(source = {}, currency = "USD", filterAttribute = "data-revenue-filter") {
  return Object.entries(DEBIT_FLAG_WORDS).map(([kind, words]) => {
    const count = numberOrNull(source && source[`${kind}_count`]);
    if (!count) return "";
    return `
      <tr class="evidence-flag-row">
        <td><button class="evidence-link" type="button" ${filterAttribute}="debitFlag:${kind}" aria-label="Show the ${escapeHtml(words.toLowerCase())}">${escapeHtml(words)}</button></td>
        <td>${escapeHtml(formatNumber(count))}</td>
        <td>${escapeHtml(formatMoney(source[`${kind}_total`], currency))}</td>
        <td>${glassChip("!", "Not deducted", "amber")}</td>
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

// The decisions that already ask for review: a withholding basis that is not established keeps their words.
const REVIEW_DECISIONS = new Set(["review_required", "manual_review_required"]);

// The final review of round 2, F1 (review round 1 of its fix run; true revenue spec §10.1, §11): a statement whose
// withholding basis is not established (the served flag) goes to review, as the ruling asks. A decision that already
// reads a review keeps its words ("manual review required" where the ledger does not reconcile); the legacy basis never
// sets the flag.
function withholdingReviewDecision(decision, metrics = {}) {
  return withholdingBasisUnestablished(metrics) && !REVIEW_DECISIONS.has(decision) ? "review_required" : decision;
}

// One account's own decision, as its pill shows it.
function accountDecision(report) {
  const metrics = report.metrics || {};
  const quality = report.quality || {};
  return withholdingReviewDecision(hasMaterialPotentialLenderDebits(metrics) || metrics.revenue_review_required
    ? "review_required"
    : quality.corporate_use || quality.level || "review_required", metrics);
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

// The hero's lines under its big figure, each on its own line; each line is HTML built from escaped pieces, and an
// empty one is left out.
function creditsMetaLines(...lines) {
  return lines.filter(Boolean).map((line) => `<span class="credits-meta-line">${line}</span>`).join("");
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
// True revenue with its Verified part shaded. A statement whose revenue is not established draws neither part. The
// owner's follow-up of 2026-10-07 ("there are like 4 different colors while the color key contains only two"): a bar
// takes only colours its key shows, so no bar is highlighted: every Total bar (Both and Total views) is the Total
// swatch's neutral, every True bar (True view) the True revenue swatch's accent, and the Total view's key names its
// swatch too.
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
// or a member that declared none beside one that did). Audit B11 (I54): such a package's bars are scaled within each
// currency (an undeclared member is a group of its own), never across them, and every bar names its unit, USD
// included; an undeclared member's stays undeclared.
function renderMonthlyChart(rows, unitsShown, view = "both") {
  if (!els.monthlyChart) return;
  const both = view === "both";
  const nested = view !== "total";
  const plotted = view === "true" ? trueDeposits : totalDeposits;
  // Every bar of a view in its key's colour (webapp/templates/index.html: .bar.bar-total, .bar.bar-true).
  const barClass = view === "true" ? "bar bar-true" : "bar bar-total";
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
        <div class="${barClass}" style="height: ${heightPx.toFixed(1)}px">${
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
  const totalSwatch = `<span><i class="legend-swatch" aria-hidden="true"></i>Total deposits</span>`;
  const trueSwatch = `<span><i class="legend-swatch legend-swatch-true" aria-hidden="true"></i>True revenue</span>`;
  const verifiedSwatch = `<span><i class="legend-swatch legend-swatch-verified" aria-hidden="true"></i>of which verified</span>`;
  const ledgerNote = "<span>and ledger (average daily balance) per statement</span>";
  const legend = both
    ? totalSwatch + trueSwatch + verifiedSwatch
    : view === "true" ? trueSwatch + verifiedSwatch + ledgerNote : totalSwatch + ledgerNote;
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
  // The owner's request of 2026-10-07 (dashboard clarity): the big figure is True revenue and Total credits sits on the
  // line below it; where True revenue is not established the figure reads N/A and the line above Total credits says why.
  const unestablishedReason = revenueEstablished ? ""
    : `True revenue is not established for this statement${rulesOutdated ? " · Re-analyze to compute true revenue" : ""}`;
  renderCredits({
    label: "True revenue",
    value: revenueEstablished ? formatMoney(metrics.true_revenue_total, currency) : "N/A",
    meta: creditsMetaLines(escapeHtml(unestablishedReason),
      `Total credits <span class="mono">${escapeHtml(formatMoney(totalCredits, currency))}</span> · `
      + `${escapeHtml(formatNumber(metrics.total_posted_credit_count))} credit transactions`),
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
    ["Withholding basis", withholdingBasisLabel(metrics)],
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
          facts: statementRevenueFacts(metrics, currency),
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
        ["Confirmed Lender Debits", formatMoney(metrics.lender_debits, currency), paidLendersNote(metrics, currency), "$", "neutral"],
        ["Potential Lender Debit Count", formatNumber(metrics.potential_lender_debit_count), "Transactions linked to possible lenders", "DB", countTone(metrics.potential_lender_debit_count)],
        ["Potential Lender Debits", formatMoney(potentialLenderDebitTotal(metrics), currency), "Excluded until lender status is confirmed", "$", countTone(metrics.potential_lender_debit_count)],
        ["Withholding Basis", formatMoney(withholdingBasisAmount(metrics), currency), activeDenominatorNote(metrics), "DEP", "neutral"],
        ["Potential Withholding Exposure", formatPercent(metrics.potential_withholding_exposure), potentialWithholdingAuditNote(metrics, currency), "%", hasMaterialPotentialLenderDebits(metrics) ? "amber" : "neutral"],
        ["Insurance Debits", formatNumber(metrics.insurance_count), "Insurance debit transactions", "INS", "neutral"],
        ["Insurance Total", formatMoney(metrics.insurance_total, currency), "Excluded from lender payment totals", "$", "neutral"],
      ],
    },
  ]);
  renderAccountSummary(accountFieldRows(statement, currentMarkdown));
  renderRevenueEvidence(metrics, currency);
  // R2-OW13 (the underwriter's Q5): the returned funder payments' warning lines; R2-OW18: the lender payment changes.
  renderLenders(funders, potentialLenders, currency, detection.returned_funder_payments, detection.lender_payment_changes,
    [], false, null, detection.lump_sum_payoffs);
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

// Audit B11 (I06), audit round 2, R2-B14 (R49): the queue entry an entry repeats: the same bytes earlier in this
// batch, matched on the content hash the /upload reply carries, or null. An upload from an earlier batch does not
// count (the server's `duplicate_of` names the earliest job holding the bytes anywhere, so it is never read here), and
// an entry before the reply (no job id or no hash) repeats nothing. R16: once the package arrives, only a row it marks
// `is_duplicate` repeats, and it names the copy the package kept in its place.
function queueRepeatOf(entry) {
  if (!entry || !entry.jobId || !entry.contentSha256) return null;
  if (queuePackageDuplicates) {
    const kept = queuePackageDuplicates.get(entry.jobId);
    if (!kept) return null;
    return queueEntries.find((other) => other !== entry && other.jobId === kept
      && other.contentSha256 === entry.contentSha256) || null;
  }
  const first = queueEntries.find((other) => other.jobId && other.contentSha256 === entry.contentSha256);
  return first !== entry ? first : null;
}

// Audit round 2, R2-B14 (R16): the package of this upload batch tells the queue which rows it left out.
function markQueueFromPackage(jobIds, pkg = {}) {
  const batch = queueEntries.map((entry) => entry.jobId);
  if (!batch.length || batch.join(",") !== jobIds.join(",")) return;
  queuePackageDuplicates = new Map((Array.isArray(pkg.documents) ? pkg.documents : [])
    .filter((doc) => doc && doc.is_duplicate === true && doc.duplicate_of)
    .map((doc) => [String(doc.id), String(doc.duplicate_of)]));
  renderQueue();
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
    contentSha256: null,
  }));
  queuePackageDuplicates = null;
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
        // Audit B11 (I06): the earliest job holding these exact bytes anywhere in the store, kept as the reply says it.
        entry.duplicateOf = job.duplicate_of || null;
        // Audit round 2, R2-B14 (R49): the bytes' hash, which the queue matches inside this batch.
        entry.contentSha256 = job.content_sha256 || null;
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
  // Audit round 2, R2-B15 (R54): with no statement analysed the server's one month is the floor of a division, not a
  // month the package covers.
  if (numberOrNull(totals.completed) === 0) return "No statements analysed";
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
  // Audit round 2, R2-B14 (R14): an interim, month-to-date or custom-range printout another statement covers.
  superseded_interim: "a shorter printout of days another statement covers",
  // R2-B14 review round 1: a quarterly printout or multi-month export whose rows the monthly statements print.
  superseded_long_printout: "a printout of more than a month whose every row other statements of the account print",
});
// The reasons a statement the account's other statements print is left out for (webapp/app.py SUPERSEDED_REASON_WORDS).
const SUPERSEDED_REASONS = Object.freeze(["superseded_interim", "superseded_long_printout"]);

// Audit round 2, R2-B14 (R16): why the package kept another copy in a left-out repeat's place.
const DUPLICATE_KEPT_BECAUSE_WORDS = Object.freeze({
  has_analysis: "a completed analysis",
  current_rules: "current rules",
  has_review_decisions: "the review decisions",
});

// Audit round 2, R2-B14 (R14): a pair of overlapping statements of one account and the credits both print, counted in
// both (the package downloads print the same words, webapp/app.py _overlap_words). Audit round 3, R3-B18 (R3-04): a
// pair named although it shares no credit (a period inside the other, or more than three common days) reads the days
// the two cover.
function overlappingStatementWords(pair, nameOf, money) {
  const count = numberOrNull(pair.shared_credit_count) || 0;
  if (!count) {
    return `${nameOf(pair.job)} and ${nameOf(pair.other)} cover ${formatNumber(numberOrNull(pair.days_shared))} `
      + "of the same days of one account";
  }
  return `${nameOf(pair.job)} and ${nameOf(pair.other)} share ${formatNumber(count)} `
    + `${count === 1 ? "credit" : "credits"} (${money}) in the days both cover, counted in both`;
}

function renderDuplicateNotice(pkg = {}) {
  if (!els.duplicateNotice) return;
  const listed = Array.isArray(pkg.documents) ? pkg.documents : [];
  const repeats = duplicateDocuments(listed);
  const accounts = (Array.isArray(pkg.excluded_accounts) ? pkg.excluded_accounts : [])
    .filter((entry) => entry && entry.is_duplicate === true);
  const overlaps = (Array.isArray((pkg.totals || {}).overlapping_statements) ? pkg.totals.overlapping_statements : [])
    .filter((pair) => pair && typeof pair === "object");
  const count = repeats.length + accounts.length;
  els.duplicateNotice.hidden = count === 0 && overlaps.length === 0;
  if (!els.duplicateNoticeText) return;
  if (!count && !overlaps.length) {
    els.duplicateNoticeText.innerHTML = "";
    return;
  }
  const memberOf = (jobId) => listed.find((item) => packageMember(item.id).jobId === String(jobId));
  const nameOf = (jobId) => {
    const doc = memberOf(jobId);
    return doc && doc.filename ? doc.filename : "an earlier statement";
  };
  const lines = [
    ...repeats.map((doc) => {
      const kept = DUPLICATE_KEPT_BECAUSE_WORDS[doc.duplicate_kept_because];
      if (kept && (doc.duplicate_reason === "same_content" || doc.duplicate_reason === "same_statement")) {
        // R16: a later copy was kept in this one's place; the notice says which and why.
        return `${doc.filename || "A statement"} left out: ${nameOf(doc.duplicate_of)} is the same `
          + `${doc.duplicate_reason === "same_content" ? "file" : "statement"} and has ${kept}`;
      }
      return `${doc.filename || "A statement"} repeats ${nameOf(doc.duplicate_of)} `
        + `(${DUPLICATE_REASON_WORDS[doc.duplicate_reason] || "the same statement"})`;
    }),
    ...accounts.map((entry) => `account ${formatNumber(entry.account_index)} of ${nameOf(entry.job_id)} repeats `
      + `${nameOf(entry.duplicate_of)}`
      + (SUPERSEDED_REASONS.includes(entry.reason) ? ` (${DUPLICATE_REASON_WORDS[entry.reason]})` : "")),
  ];
  const parts = [];
  if (count) {
    parts.push(`<strong>${escapeHtml(formatNumber(count))} repeated `
      + `${count === 1 ? "statement" : "statements"} left out of every figure.</strong> `
      + `${escapeHtml(lines.join("; "))}.`);
  }
  if (overlaps.length) {
    // R14: never netted; each pair's shared credits are in its own account's currency, which the pair names (R2-B14
    // review round 1; null when the two statements declare different ones), else its member's row.
    const overlapLines = overlaps.map((pair) => {
      const member = memberOf(pair.job);
      const currency = pair.currency !== undefined ? pair.currency
        : member && member.currency !== undefined ? member.currency : packageCurrencyInfo(pkg).currency;
      return overlappingStatementWords(pair, nameOf, formatMoney(pair.shared_credit_total, currency));
    });
    // R3-B18 (R3-04): the header says the pairs share credits only when every pair does.
    const allShare = overlaps.every((pair) => (numberOrNull(pair.shared_credit_count) || 0) > 0);
    const header = allShare
      ? `${overlaps.length === 1 ? "pair of overlapping statements shares" : "pairs of overlapping statements share"} `
        + "credits."
      : `${overlaps.length === 1 ? "pair" : "pairs"} of overlapping statements of one account.`;
    parts.push(`<strong>${escapeHtml(formatNumber(overlaps.length))} ${header}</strong> `
      + `${escapeHtml(overlapLines.join("; "))}.`);
  }
  els.duplicateNoticeText.innerHTML = `${parts.join(" ")} The package needs review.`;
}

// Audit round 2, R2-B15 (R15): why an account was left out of every figure for another reason than a repeat
// (webapp/app.py `_package_members`); any other reason is an account that did not validate on its own.
const EXCLUDED_ACCOUNT_WORDS = Object.freeze({
  main_account_unverified: "main account not verified",
  main_account_idle: "main account printed no activity",
  document_transfer_pairing_ambiguous: "transfers between its accounts could not be paired",
  document_omission_unratified: "a section left out without proof",
});

// The accounts the server left out of every figure for another reason than a repeat (the repeats have their notice).
function leftOutAccounts(pkg = {}) {
  return (Array.isArray(pkg.excluded_accounts) ? pkg.excluded_accounts : [])
    .filter((entry) => entry && typeof entry === "object" && entry.is_duplicate !== true);
}

// R15: the notice beside the repeats' one. Leaving these accounts out is ruled (Q1/Q2, the 2026-09-23 main-account
// ruling); the package says which, and why, and needs review.
function renderExcludedNotice(pkg = {}) {
  if (!els.excludedNotice) return;
  const entries = leftOutAccounts(pkg);
  els.excludedNotice.hidden = entries.length === 0;
  if (!els.excludedNoticeText) return;
  if (!entries.length) {
    els.excludedNoticeText.innerHTML = "";
    return;
  }
  const lines = entries.map((entry) => {
    const account = numberOrNull(entry.account_index);
    const of = numberOrNull(entry.account_count);
    return `${entry.filename || "A statement"}`
      + (account === null ? "" : `, account ${formatNumber(account)}${of === null ? "" : ` of ${formatNumber(of)}`}`)
      + ` (${EXCLUDED_ACCOUNT_WORDS[entry.reason] || "account not validated"})`;
  });
  els.excludedNoticeText.innerHTML = `<strong>${escapeHtml(formatNumber(entries.length))} `
    + `${entries.length === 1 ? "account" : "accounts"} left out of every figure. The package needs review.</strong> `
    + `${escapeHtml(lines.join("; "))}.`;
}

// Owner ruling 2026-10-02 (the underwriter's Q6, "2"; true revenue spec §10.1; R2-OW15): beside the repeats' and the
// left-out accounts' notices, what the package passes matched across its statements, each pair listed with its dates
// and money and a button to its rows ("packageMatch:<kind>"), and the statements they could not read (analysed with
// older rules or with no currency). A statement viewed alone keeps its own figures, so the notice says the figures
// are the package's.
function renderPackageMatchNotice(pkg = {}) {
  if (!els.packageMatchNotice) return;
  const totals = pkg.totals || {};
  const listed = (Array.isArray(pkg.package_matches) ? pkg.package_matches : [])
    .filter((match) => match && match.credit && match.debit);
  const matches = listed.filter((match) => match.kind === "returned_deposit" && match.moved === true);
  // R2-OW16 (the underwriter's Q4): the deposits pass 2 held, and the already-held deposits it only annotated.
  const transfers = listed.filter((match) => match.kind === "own_account_transfer");
  const held = transfers.filter((match) => match.moved === true);
  const alreadyHeld = transfers.filter((match) => match.moved !== true);
  const statementsMarked = (...markers) => new Set(countedDocuments(pkg.documents)
    .filter((doc) => markers.includes(doc.package_match_unchecked))
    .map((doc) => packageMember(doc.id).jobId)).size;
  const unchecked = statementsMarked("older_rules", "no_currency");
  const noNumber = statementsMarked("no_account_number");
  els.packageMatchNotice.hidden = !matches.length && !transfers.length && !unchecked && !noNumber;
  if (!els.packageMatchNoticeText) return;
  const parts = [];
  const currency = packageCurrencyInfo(pkg).currency;
  const money = (match) => formatMoney(Math.abs(numberOrNull(match.credit.amount) ?? 0), match.credit.currency ?? currency);
  const heads = [];
  if (held.length) {
    heads.push(`${formatNumber(held.length)} ${held.length === 1 ? "transfer" : "transfers"} between the business's `
      + `accounts held (${formatMoney(totals.own_account_transfer_held_total, currency)})`);
  }
  if (alreadyHeld.length) {
    heads.push(`${formatNumber(alreadyHeld.length)} already-held `
      + `${alreadyHeld.length === 1 ? "deposit also matches" : "deposits also match"} a transfer `
      + `(${formatMoney(totals.own_account_transfer_already_held_total, currency)})`);
  }
  if (matches.length) {
    heads.push(`${formatNumber(matches.length)} bounced ${matches.length === 1 ? "deposit" : "deposits"} taken out of `
      + `True (${formatMoney(totals.returned_deposit_cross_statement_total, currency)})`);
  }
  if (heads.length) {
    // One button per kind; "Show them" where the notice lists one kind only (as R2-OW15 rendered it).
    const both = transfers.length && matches.length;
    const button = (kind, label) => `<button class="btn-quiet" type="button" data-revenue-filter="packageMatch:${kind}">`
      + `${both ? label : "Show them"}</button>`;
    parts.push(`<strong>Matched across statements: ${escapeHtml(heads.join(" · "))}.</strong>`);
    if (transfers.length) {
      const pairs = transfers.map((match) => `${match.credit.filename || "a statement"} ${match.credit.date || "undated"} `
        + `deposit ${money(match)} matches the transfer out of ${match.debit.filename || "a statement"} on `
        + `${match.debit.date || "an unknown date"}${match.moved === true ? "" : " (already held)"}`);
      parts.push(`${escapeHtml(pairs.join("; "))}. ${button("own_account_transfer", "Show the transfers")}`);
    }
    if (matches.length) {
      const pairs = matches.map((match) => `${match.credit.filename || "a statement"} ${match.credit.date || "undated"} `
        + `deposit ${money(match)} returned ${match.debit.date || "undated"} (${match.debit.filename || "a statement"})`);
      parts.push(`${escapeHtml(pairs.join("; "))}. ${button("returned_deposit", "Show the bounced deposits")}`);
    }
  }
  if (noNumber) {
    parts.push(`Transfers between accounts not checked for ${escapeHtml(formatNumber(noNumber))} `
      + `${noNumber === 1 ? "statement" : "statements"}: no account number read.`);
  }
  if (unchecked) {
    parts.push(`Not matched across statements: ${escapeHtml(formatNumber(unchecked))} `
      + `${unchecked === 1 ? "statement" : "statements"} analysed with older rules or with no currency.`);
  }
  els.packageMatchNoticeText.innerHTML = parts.join(" ");
}

// Audit round 2, R2-B15 (R50): a package's counts on one footing. `statements`: the statements it lists, its repeats
// left out (distinct_documents); `accounts`: its members, each analysed, failed or still pending (completed + failed +
// pending: an account a document publishes is a member of its own, Q1/Q5); `multi`: a counted row is an account of a
// document, so a statement and an account differ and every surface says which it counts.
function packageCounts(pkg = {}) {
  const totals = pkg.totals || {};
  const completed = numberOrNull(totals.completed) || 0;
  return {
    statements: numberOrNull(totals.distinct_documents ?? totals.documents) || 0,
    completed,
    accounts: completed + (numberOrNull(totals.failed) || 0) + (numberOrNull(totals.pending) || 0),
    multi: countedDocuments(pkg.documents).some((doc) => packageMember(doc.id).account !== null),
  };
}

// "1 statement · 2 accounts".
function statementsAndAccounts(counts) {
  return `${formatNumber(counts.statements)} ${counts.statements === 1 ? "statement" : "statements"} · `
    + `${formatNumber(counts.accounts)} ${counts.accounts === 1 ? "account" : "accounts"}`;
}

// R15: what True revenue covers when an account was left out: the statements with a counted, analysed account of the
// statements the package lists ("" when nothing was left out). Since the owner's request of 2026-10-07 True revenue is
// the hero's big figure, so the line under it names it.
function packageCoverage(pkg = {}) {
  if (!leftOutAccounts(pkg).length) return "";
  const counts = packageCounts(pkg);
  const covered = new Set(countedDocuments(pkg.documents).filter((doc) => doc.status === "done")
    .map((doc) => packageMember(doc.id).jobId)).size;
  return ` · True revenue covers ${formatNumber(covered)} of ${formatNumber(counts.statements)} `
    + `${counts.statements === 1 ? "statement" : "statements"}`;
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
      markQueueFromPackage(jobIds, pkg);
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
  renderExcludedNotice(pkg);
  renderPackageMatchNotice(pkg);

  setResultsMode("package");
  showResultsContent();
  const monthRows = packageMonthRows(documents);
  const title = packageTitle(monthRows);
  const banks = [...new Set(documents.map((doc) => doc.bank).filter(Boolean))];
  const span = packageSpanLabel(totals, documents.length);
  // Audit round 2, R2-B15 (R50): a package holding an account of a document counts its statements and its accounts
  // apart; one of single-account statements reads as before.
  const counts = packageCounts(pkg);
  // Audit B11 (I31): "Balanced" only where every statement reconciles to its bank's figures and revenue is established.
  const revenueBalanced = packageRevenueBalanced(pkg);
  renderHero({
    icon: PACKAGE_ICON,
    kicker: ["Package", counts.multi ? statementsAndAccounts(counts)
      : `${formatNumber(documents.length)} ${documents.length === 1 ? "statement" : "statements"}`, banks.join(", ")]
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
  // and True per month beside the package's True: what an MCA advance is sized on. The owner's request of 2026-10-07
  // (dashboard clarity): the big figure is the package's True revenue and Total credits leads the line below it; where
  // True revenue is N/A (not established) a line above says why (with no statement analysed the label already does).
  const trueRevenue = formatMoney(totals.true_revenue_total, currency);
  const unestablishedReason = refusalNote || trueRevenue !== "N/A" || numberOrNull(totals.completed) === 0 ? ""
    : (packageUnestablishedNote(totals, documents) || "True revenue is not established for this package");
  renderCredits({
    label: `True revenue · ${span}`,
    value: trueRevenue,
    meta: refusalNote
      ? creditsMetaLines(escapeHtml(refusalNote))
      : creditsMetaLines(escapeHtml(unestablishedReason),
        `Total credits <span class="mono">${escapeHtml(formatMoney(totals.total_credits, currency))}</span>`
        + ` · Avg monthly gross credits <span class="mono">${escapeHtml(formatMoney(totals.avg_monthly_credits, currency))}</span>`
        + ` · True per month <span class="mono">${escapeHtml(formatMoney(totals.avg_monthly_true_revenue, currency))}</span>`
        // Audit round 2, R2-B15 (R15): the statements True covers, when an account was left out of every figure.
        + escapeHtml(packageCoverage(pkg))),
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
    // Audit round 2, R2-B15 (R54): a job still queued or processing is pending, never failed.
    const pending = numberOrNull(totals.pending) || 0;
    const notes = [
      ...(failed ? [`${formatNumber(failed)} ${failed === 1 ? "statement" : "statements"} failed`] : []),
      ...(pending ? [`${formatNumber(pending)} still processing`] : []),
    ];
    els.packageProcessingNote.textContent = notes.length ? notes.join(" · ") : "All statements complete";
  }

  setStatusRows([
    // Audit B11 (I06): a repeated statement left out is no statement of the package. Audit round 2, R2-B15 (R50): a
    // package holding an account of a document counts its accounts here (completed counts accounts).
    counts.multi
      ? ["Accounts completed", `${formatNumber(counts.completed)} / ${formatNumber(counts.accounts)}`]
      : ["Statements completed", `${formatNumber(totals.completed)} / ${formatNumber(totals.distinct_documents ?? totals.documents)}`],
    ["Package currency", packageCurrencyLabel(currencyInfo)],
    ["Approved", formatNumber(totals.approved)],
    ["Manual review", formatNumber(totals.manual_review)],
    ["High integrity risk", formatNumber(totals.integrity_high)],
    ["Processing errors", formatNumber(totals.failed)],
    ["Confirmed withholding", formatPercent(totals.package_withholding_rate)],
    ["Potential exposure", formatPercent(totals.potential_withholding_exposure)],
    ["Revenue reconciliation", revenueBalanced ? "Balanced" : "Review required"],
    ["Withholding basis", withholdingBasisLabel(totals)],
  ]);

  renderMetricSections([
    {
      title: "Package revenue",
      // Audit B11 (I07, I33): the statements and the distinct calendar months they cover (`months`); each per-month
      // figure is the package's total divided by those months.
      sub: [span, packageUnestablishedNote(totals, documents)].filter(Boolean).join(" · "),
      items: [
        ...revenueCardItems(totals, currency, {
          ...packageRevenueFlags(totals), note: moneyNote, facts: packageRevenueFacts(totals, currency),
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
        ["Confirmed Lender Debits", formatMoney(totals.lender_debits, currency), moneyNote(paidLendersNote(totals, currency)), "$", "neutral"],
        ["Potential Lender Debit Count", formatNumber(totals.potential_lender_debit_count), "Transactions linked to possible lenders", "DB", countTone(totals.potential_lender_debit_count)],
        ["Potential Lender Debits", formatMoney(potentialLenderDebitTotal(totals), currency), moneyNote("Excluded until lender status is confirmed"), "$", countTone(totals.potential_lender_debit_count)],
        ["Withholding Basis", formatMoney(withholdingBasisAmount(totals), currency), moneyNote(activeDenominatorNote(totals)), "DEP", "neutral"],
        ["Potential Withholding Exposure", formatPercent(totals.potential_withholding_exposure), moneyNote(potentialWithholdingAuditNote(totals, currency)), "%", hasMaterialPotentialLenderDebits(totals) ? "amber" : "neutral"],
        ["Insurance Debits", formatNumber(totals.insurance_count), "Insurance debit transactions", "INS", "neutral"],
        ["Insurance Total", formatMoney(totals.insurance_total, currency), moneyNote("Excluded from lender payment totals"), "$", "neutral"],
      ],
    },
  ]);

  renderAccountSummary([
    ["Package Decision", labelize(totals.decision || "review required")],
    // Audit round 2, R2-B15 (R50): of the statements the package counts (a repeat is none of them), and, for a package
    // holding an account of a document, its statements and its accounts apart.
    ["Statements", counts.multi
      ? `${formatNumber(counts.statements)} ${counts.statements === 1 ? "statement" : "statements"} · `
        + `${formatNumber(counts.completed)} of ${formatNumber(counts.accounts)} `
        + `${counts.accounts === 1 ? "account" : "accounts"} completed`
      : `${formatNumber(totals.completed)} completed of ${formatNumber(counts.statements)}`],
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
  // R2-OW13: each warning line names its own statement's unit. R2-OW18: the lender payment changes across the
  // package's statements, and the members not checked across them.
  renderLenders(funders, potentialLenders, currency, pkg.returned_funder_payments, pkg.lender_payment_changes,
    pkg.lender_payment_changes_unchecked, true, Array.isArray(pkg.documents) ? pkg.documents : [], pkg.lump_sum_payoffs);
  renderInsurance(insuranceProviders, currency);
  renderFlaggedPositions(pkg.flagged_positions, currency, true);
  renderRevenueEvidence(packageRevenueFlags(pkg.totals || {}), currency);
  renderMonthlyStatements(pkg);
}

/* --- Monthly Statements deposits -----------------------------------------
   Which deposits the package's Monthly Statements table shows, chosen on the Settings page and kept in this browser
   only. Total is everything going in. True is True revenue (5.6): every posted credit except known non-revenue (an
   own-account transfer, lender funding, a refund) and the deposits held for review; the chart shades its Verified part.
   Every view also shows each statement's confirmed withholding rate (the owner's request of 2026-10-07). */
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

// Audit round 2, R2-B15 (R54): the job statuses still on their way (webapp/app.py _PENDING_JOB_STATUSES).
const PENDING_JOB_STATUSES = Object.freeze(["queued", "processing"]);

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
// named when both are. The owner's request of 2026-10-07: no Verified ($) column (the chart keeps its Verified part).
function monthlyDepositColumns(view) {
  const total = [totalDeposits, (doc) => monthFigure(doc, doc.deposit_count)];
  const revenue = [trueDeposits, trueDepositCount];
  if (view === "total") return [["Monthly Deposits ($)", total[0], "amount"], ["Deposits Per Month", total[1], "count"]];
  if (view === "true") return [["Monthly Deposits ($)", revenue[0], "amount"], ["Deposits Per Month", revenue[1], "count"]];
  return [
    ["Total Deposits ($)", total[0], "amount"], ["Total Deposits Per Month", total[1], "count"],
    ["True Deposits ($)", revenue[0], "amount"], ["True Deposits Per Month", revenue[1], "count"],
  ];
}

// The owner's request of 2026-10-07 ("add witholding rate"), review round 3: a statement's confirmed withholding rate on
// the figures its row shows. Audit round 3, R3-MERGE: the row's served `withholding_rate`, which the server owns: since
// round 3 (R3-72, and the final review's F2) a package member row's rate is its own served `withholding_numerator` over
// its own served `withholding_denominator` (the basis after the package passes, as its True Deposits are) wherever the
// package moved either, else the statement's stored rate over the same figures; it carries R3-20's basis floor (a
// near-zero True publishes no rate), F1's unestablished basis, R3-73's re-debited bounce counted once and R3-79's worded
// payoff out of the numerator, so the page never recomputes a rule the server owns (the hosting line divided the two
// figures itself, before the server's member row read them). Null (shown N/A) for a statement that did not complete,
// where the package publishes no rate for the member (F1's flag, or no served rate), and, as a guard on the row's own
// figures, where either figure is not served or the basis is 0 or less.
function monthlyWithholdingRate(doc) {
  if (monthFigure(doc, true) === null || doc.withholding_basis_unestablished === true) return null;
  const rate = numberOrNull(doc.withholding_rate);
  if (rate === null) return null;
  const numerator = numberOrNull(doc.withholding_numerator);
  const basis = numberOrNull(doc.withholding_denominator);
  if (numerator === null || basis === null || basis <= 0) return null;
  return rate;
}

// "76.49%", always two decimals; N/A for none.
function formatRateTwoDecimals(value) {
  const n = numberOrNull(value);
  return n === null ? "N/A" : `${n.toFixed(2)}%`;
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
  // Audit round 2, R2-B16 (R51): the chart and the table beside it name units on one condition, a package that refuses
  // to combine its currencies (several, or a member that declared none beside one that did).
  const unitsShown = currencyInfo.refused || currencyInfo.currencies.length > 1;
  renderMonthlyChart(packageMonthRows(documents), unitsShown, view);
  if (els.monthlyCard) els.monthlyCard.style.display = "block";
  if (els.monthlyCount) {
    const note = MONTHLY_DEPOSITS_NOTES[view];
    // Audit round 2, R2-B15 (R50): one row per account; a package holding an account of a document names its
    // statements and its accounts apart.
    const counts = packageCounts(pkg);
    els.monthlyCount.textContent = (counts.multi ? statementsAndAccounts(counts)
      : `${documents.length} ${documents.length === 1 ? "statement" : "statements"}`)
      + (note ? ` · ${note}` : "");
  }
  if (els.monthlyHead) {
    els.monthlyHead.innerHTML = `
      <tr>
        <th>Month</th>
        <th>Year</th>
        ${columns.map(([header]) => `<th>${escapeHtml(header)}</th>`).join("")}
        <th>Withholding Rate</th>
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
        <td>N/A</td>
        <td>${glassChip("◐", "Review", "amber")}</td>
      </tr>
    `;
  } else {
    // The CRM's seasonality layout: one row per statement month, in calendar order.
    const rows = packageMonthRows(documents);
    // Each row is denominated by its OWN statement (CURRENCY DOCTRINE §F). The column names say ($) as the
    // CRM does, and a single-currency package's figures are bare. Audit round 2, R2-B16 (R51): in a package that
    // refuses to combine its currencies (`unitsShown`, the chart's rule: several currencies, or a member that
    // declared none beside one that did), every declared row names its unit on its amount cells, USD included, as
    // its chart bar does; an undeclared row stays bare (§B fails closed), so there a bare figure means undeclared,
    // never USD. Count and NSF cells carry no unit.
    // Two statements for one month (two accounts, or checking and savings) would be indistinguishable rows,
    // so those rows alone name their file under the month.
    const monthCounts = new Map();
    rows.forEach(({ month }) => { if (month) monthCounts.set(month.key, (monthCounts.get(month.key) || 0) + 1); });
    // Members counted on different NSF bases (one saved before the printed-day basis existed) would show counts that
    // cannot be compared, so each NSF cell then names its basis; the tooltip always does.
    const mixedNsf = new Set(rows.map(({ doc }) => doc.nsf_source).filter(Boolean)).size > 1;
    els.monthlyTable.innerHTML = rows.map(({ doc, month }) => {
      // Audit round 2, R2-B15 (R54): a statement still queued or processing reads Processing, never Failed.
      const status = PENDING_JOB_STATUSES.includes(doc.status) ? "Processing"
        : doc.status !== "done" ? "Failed" : labelize(doc.corporate_use || doc.quality || "review");
      const docCurrency = currencyOfDocument(doc);
      const unit = unitsShown && docCurrency ? ` ${docCurrency}` : "";
      const amount = (value) => {
        const text = formatWhole(value);
        return text === "N/A" ? text : text + unit;
      };
      const shared = month && monthCounts.get(month.key) > 1;
      // The owner's follow-up of 2026-10-07: a cell is its figure alone; the month's Zelle line (R2-OW03's, then
      // R2-OW17's) is no longer drawn under the True cell. The True card keeps the Zelle fact.
      return `
        <tr title="${escapeHtml(doc.filename || "Statement")}">
          <td>${escapeHtml(month ? MONTH_NAMES[month.month] : "N/A")}${shared ? `<div class="table-cell-detail">${escapeHtml(doc.filename || "Statement")}</div>` : ""}</td>
          <td class="mono">${escapeHtml(month ? String(month.year) : "N/A")}</td>
          ${columns.map(([, value, kind]) => `<td class="mono">${escapeHtml(kind === "amount" ? amount(value(doc)) : formatWhole(value(doc)))}</td>`).join("")}
          <td class="mono">${escapeHtml(formatRateTwoDecimals(monthlyWithholdingRate(doc)))}</td>
          <td class="mono">${escapeHtml(amount(monthFigure(doc, doc.average_daily_balance)))}</td>
          <td class="mono" title="${escapeHtml(nsfSourceLabel(doc.nsf_source))}">${escapeHtml(formatNumber(monthFigure(doc, doc.nsf_count)))}${mixedNsf ? `<div class="table-cell-detail">${escapeHtml(nsfSourceLabel(doc.nsf_source))}</div>` : ""}</td>
          <td><button class="statement-open" type="button" data-job-id="${escapeHtml(doc.id)}" ${doc.status === "done" ? "" : "disabled"}>${status === "Failed" ? "Unavailable" : status === "Processing" ? "Processing" : `Open${OPEN_ICON}`}</button></td>
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
      facts: statementRevenueFacts(metrics, currency),
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
    ["Confirmed Lender Debits", `${formatNumber(metrics.lender_debit_count)} / ${formatMoney(metrics.lender_debits, currency)}`, paidLendersNote(metrics, currency, "Transaction count and total paid to confirmed lenders"), "DB", "neutral"],
    ["Potential Lender Debits", `${formatNumber(metrics.potential_lender_debit_count)} / ${formatMoney(potentialLenderDebitTotal(metrics), currency)}`, "Transaction count and total linked to possible lenders", "?", countTone(metrics.potential_lender_debit_count)],
    ["Withholding Basis", formatMoney(withholdingBasisAmount(metrics), currency), activeDenominatorNote(metrics), "DEP", "neutral"],
    ["Potential Withholding Exposure", formatPercent(metrics.potential_withholding_exposure), potentialWithholdingAuditNote(metrics, currency), "%", hasMaterialPotentialLenderDebits(metrics) ? "amber" : "neutral"],
    ["Insurance", `${formatNumber(metrics.insurance_count)} / ${formatMoney(metrics.insurance_total, currency)}`, "Transaction count and total excluded from lender payments", "INS", "neutral"],
    ["Document Integrity", integrityLabel(integrity), (integrity.flags || []).join(", ") || "No source contradictions detected", "DOC", integrityTone(integrity)],
    ["Status", labelize(decision), "Corporate-use and lender-review status", decision === "approved" ? "OK" : "REVIEW", decision === "approved" ? "green" : "amber"],
  ].map(renderMetricCard).join("");
  els.statementModalAccount.innerHTML = kvRowsHtml(accountFieldRows(statement, markdown));

  // R2-OW18 (G4): the statement's own lender payment change lines, above its lender rows (R2-OW13's returned lines stay
  // absent here, as before).
  // Audit round 3, R3-B03 (R3-79): and the lump-sum payoffs' information lines above them.
  const paymentChangeRows = lumpSumPayoffRowsHtml(detection.lump_sum_payoffs, currency)
    + lenderPaymentChangeRowsHtml(detection.lender_payment_changes, [], currency, lenderRows.length > 0, false);
  if (!lenderRows.length) {
    els.statementModalLenders.innerHTML = paymentChangeRows + `
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
    els.statementModalLenders.innerHTML = paymentChangeRows + lenderRows
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
    // Audit round 4, R4-76: each warning line reads whether its re-debit was returned too (withReDebitReturns).
    const returnedPayments = withReDebitReturns(pkg.returned_funder_payments)
      .filter((item) => item && typeof item === "object");
    // Audit round 3, R3-B22 (R3-67): each funder line names its payments returned unpaid.
    const lenderSummary = funders.length
      ? funders.map((funder) => packageFunderSummaryLine(funder, currency, returnedPayments)).join("\n")
      : "No lenders detected across the package.";
    // The owner's request of 2026-10-07: the memo's notes name their statements from the package's rows, as the lender
    // table's notes do.
    const sources = paymentChangeSources(pkg.documents);
    // R3-67 (the owner's Q5, "show a 'returned funder payment' warning"): one "- <note>" line per returned funder
    // payment, in served order, as the Lenders tab words it (its own unit; a cross-statement match names both
    // statements; R3-MERGE: in the lender table's plain words), before the payment changes.
    const returnedLines = returnedPayments.map((item) => `\n- ${returnedFunderPaymentWarning(item, currency, sources)}`)
      .join("");
    // R3-67: the sentence names the returned payments before the rate that keeps them, as the statement's memo does.
    const returnedSummary = (numberOrNull(totals.returned_funder_payment_count) ?? 0) > 0
      ? `${lenderDebitsSummary(totals, currency)}, ` : "";
    // R2-OW18 (G5): one "- <note>" line per lender payment change across the package's statements, in the lender
    // table's words (the owner's request of 2026-10-07).
    const paymentChangeLines = (Array.isArray(pkg.lender_payment_changes) ? pkg.lender_payment_changes : [])
      .filter((item) => item && typeof item === "object")
      .map((item) => `\n- ${lenderPaymentChangeWarning(item, currency, sources)}`).join("")
      // Audit round 3, R3-B03 (R3-79): one "- <note>" per lump-sum payoff, each in its own statement's unit.
      + lumpSumPayoffLines(pkg.lump_sum_payoffs, currency, sources).map((line) => `\n- ${line}`).join("");
    const counted = countedDocuments(pkg.documents);
    const repeats = duplicateDocuments(pkg.documents).length;
    // Audit round 2, R2-B15 (R50): a package holding an account of a document says how many of its accounts completed.
    const counts = packageCounts(pkg);
    // Audit B11 (I07): the memo carries True, Verified and Non-revenue, in total and per calendar month, ahead of the
    // gross figures, which are named gross; and the repeated statements left out (I06).
    els.summaryBox.textContent =
      `Package ${packagePeriod(counted)} (${packageSpanLabel(totals, counted.length)}): ` +
      (counts.multi
        ? `${formatNumber(counts.completed)} of ${formatNumber(counts.accounts)} `
          + `${counts.accounts === 1 ? "account" : "accounts"} completed`
        : `${formatNumber(totals.completed)} of ${formatNumber(totals.distinct_documents ?? totals.documents)} statements completed`) +
      (repeats ? `, ${formatNumber(repeats)} repeated ${repeats === 1 ? "statement" : "statements"} left out` : "") + ". " +
      `${revenueSummarySentence(totals, currency, packageRevenueFlags(totals), {
        trueMonthly: totals.avg_monthly_true_revenue,
        verifiedMonthly: totals.avg_monthly_verified_revenue,
        nonRevenueMonthly: totals.avg_monthly_non_revenue,
      }, { package: true })} ` +
      // Audit round 3, R3-B24 (R3-16): the members' large unsourced deposits, after the revenue sentence.
      largeDepositSummary(totals, currency, { package: true }) +
      `${formatMoney(totals.avg_monthly_credits, currency)} average monthly gross credits, ${formatMoney(totals.avg_monthly_cash_flow, currency)} average monthly cash flow, ` +
      `${formatNumber(totals.nsf_count)} NSF events, ${returnedSummary}${formatPercent(totals.package_withholding_rate)} confirmed withholding, ` +
      // Audit round 3, R3-B22 (R3-68): the basis the rates divide by, the label the package serves.
      `${formatMoney(potentialLenderDebitTotal(totals), currency)} potential lender debits and ${formatPercent(totals.potential_withholding_exposure)} potential exposure (${withholdingBasisWords(totals)}). ` +
      `${formatNumber(funders.length)} confirmed lender detections. Decision: ${labelize(totals.decision || "review required")}.` +
      `\n\nPackage lender summary:\n${lenderSummary}${returnedLines}${paymentChangeLines}`;
    return;
  }
  const s = currentAnalysis.statement || {};
  const m = currentAnalysis.metrics || {};
  const d = currentAnalysis.detection || {};
  const currency = s.currency || "USD";
  const lenders = Array.isArray(d.known_funders) ? d.known_funders.length : 0;
  // The statement's main account printed no activity: the summary an analyst pastes says so, and whose figures follow;
  // the statement needs review, as the dashboard says.
  const idleNote = idleMainNote(currentDocument, currency);
  // Likewise when the main account was not verified and another, verified, account was picked (All accounts).
  const unverifiedNote = idleNote ? "" : unverifiedMainNote(currentDocument, currency);
  // Audit round 3 (R3-01): the memo's decision is the pill's (accountDecision: T7's revenue gate, material potential
  // lender debits, the quality word and F1's basis flag); an idle or unverified main account still sends it to review.
  const decision = idleNote || unverifiedNote ? "review_required" : accountDecision(currentAnalysis);
  const lead = idleNote ? `${idleNote}Figures for the active account, ${accountDisplayName(s, null)}: `
    : unverifiedNote ? `${unverifiedNote}Figures for the selected account, ${accountDisplayName(s, null)}: ` : "";
  // Audit round 2, R2-B15 (R13): the statement's monthly figures are its totals over the calendar months its period
  // covers (statementMonthsCovered): one for a statement of a month, two for one of 59 days. B11 (I07) read every
  // statement as one month, so a statement longer than a month printed its whole total as "a month".
  const established = { established: m.revenue_established === true,
    verifiedEstablished: m.verified_revenue_established === true };
  const months = statementMonthsCovered(s);
  const perMonth = (value) => (months === 1 || numberOrNull(value) === null ? value : numberOrNull(value) / months);
  els.summaryBox.textContent =
    lead +
    `${s.bank || "Statement"} ${period(s)}: ` +
    `${revenueSummarySentence(m, currency, established, {
      trueMonthly: perMonth(m.true_revenue_total), verifiedMonthly: perMonth(m.verified_revenue_total),
      nonRevenueMonthly: perMonth(m.non_revenue_total),
    })} ` +
    // Audit round 3, R3-B24 (R3-16): the statement's large unsourced deposits, after the revenue sentence.
    largeDepositSummary(m, currency) +
    `Average daily balance ${formatMoney(m.average_daily_balance, currency)}, ` +
    `ending balance ${formatMoney(s.ending_balance, currency)}, cash flow ${formatMoney(m.cash_flow, currency)}, ` +
    `${formatNumber(m.effective_nsf_count)} NSF events, ${formatNumber(lenders)} confirmed lender detections, ` +
    `${lenderDebitsSummary(m, currency)}, and ` +
    // Audit round 3, R3-B22 (R3-68): the basis the rates divide by.
    `${formatMoney(potentialLenderDebitTotal(m), currency)} potential lender debits at ${formatPercent(m.potential_withholding_exposure)} exposure (${withholdingBasisWords(m)}). ` +
    (lenderPaymentChangesSummary(d.lender_payment_changes) ? `${lenderPaymentChangesSummary(d.lender_payment_changes)} ` : "") +
    // Audit round 3, R3-B03 (R3-79): each lump-sum payoff's line.
    lumpSumPayoffLines(d.lump_sum_payoffs, currency).map((line) => `${line} `).join("") +
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
  setZelleChoiceEnabled(false);
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
      // R2-OW17: a missing key reads Yes, the default; a choice being saved keeps its own pair.
      if (!zelleSettingBusy) {
        zelleSettingSaved = settings.zelle_true_revenue !== false;
        drawZelleChoice(zelleSettingSaved);
        setZelleChoiceEnabled(true);
        setZelleSettingStatus("");
      }
    })
    .catch((error) => {
      setSettingsStatus(error.message || String(error), true);
      setFlagSettingsStatus(error.message || String(error), true);
      // R2-OW17: the pair stays disabled and unticked, visibly unavailable, never shown as if a choice were made.
      if (!zelleSettingBusy) {
        drawZelleChoice(null);
        setZelleSettingStatus(error.message || String(error), true);
      }
    });
}

/* The owner's amendment of 2026-10-06 to the underwriter's Q3 (true revenue spec §10; R2-OW17): "Mark Zelle Payments as
   True Revenue", Yes (the default) or No, exactly one ticked: two labelled checkboxes driven as a radio pair (the owner's
   "check box"). The server applies the choice whenever it serves an analysis; nothing is reprocessed. */
let zelleSettingSaved = null;  // the choice the server holds, once read
let zelleSettingBusy = false;
let zelleSettingPending = null;  // the choice being saved

// Ticks Yes (true) or No (false), the other unticked; null unticks both (the choice could not be read).
function drawZelleChoice(yes) {
  [[els.zelleTrueRevenueYes, yes === true], [els.zelleTrueRevenueNo, yes === false]].forEach(([box, ticked]) => {
    if (!box) return;
    box.checked = ticked;
    box.setAttribute("aria-checked", ticked ? "true" : "false");
  });
}

function setZelleChoiceEnabled(enabled) {
  [els.zelleTrueRevenueYes, els.zelleTrueRevenueNo].forEach((box) => { if (box) box.disabled = !enabled; });
}

function setZelleSettingStatus(message, error = false) {
  if (!els.zelleSettingStatus) return;
  els.zelleSettingStatus.textContent = message;
  if (error) els.zelleSettingStatus.setAttribute("data-state", "error");
  else els.zelleSettingStatus.removeAttribute("data-state");
}

// The Recent entries other than the open one lose their decision dot until reopened: the Zelle choice moves the review
// decision, so the dots this tab remembered could be stale. The open one is redrawn by refreshShownResults.
function clearRecentDecisionDots() {
  recentAnalyses = recentAnalyses.map((item) => (item.key === openAnalysisKey ? item : { ...item, tone: "neutral" }));
  try { sessionStorage.setItem(RECENT_KEY, JSON.stringify(recentAnalyses)); } catch { /* storage unavailable */ }
  renderRecentAnalyses();
}

function chooseZelleSetting(wanted, element) {
  if (zelleSettingBusy) {
    // A change while saving is ignored: the boxes are held where the save drew them.
    drawZelleChoice(zelleSettingPending);
    return;
  }
  const current = zelleSettingSaved;
  if (element && !element.checked) {
    // The ticked box was clicked: it stays ticked (never neither), and nothing is saved.
    drawZelleChoice(current);
    return;
  }
  zelleSettingBusy = true;
  zelleSettingPending = wanted;
  drawZelleChoice(wanted);
  setZelleChoiceEnabled(false);
  setZelleSettingStatus("Saving…");
  fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zelle_true_revenue: wanted }),
  })
    .then((response) => responseJson(response).then((payload) => ({ response, payload })))
    .then(({ response, payload }) => {
      if (!response.ok || !payload.settings) throw new Error(payload.error || `Save failed (${response.status})`);
      zelleSettingSaved = payload.settings.zelle_true_revenue !== false;
      drawZelleChoice(zelleSettingSaved);
      setZelleSettingStatus(zelleSettingSaved ? "Saved: Zelle deposits count as True revenue."
        : "Saved: Zelle deposits are non-revenue.");
      clearRecentDecisionDots();
      refreshShownResults();
    })
    .catch((error) => {
      drawZelleChoice(current);
      setZelleSettingStatus(error.message || String(error), true);
    })
    .finally(() => {
      zelleSettingBusy = false;
      zelleSettingPending = null;
      setZelleChoiceEnabled(true);
    });
}

els.zelleTrueRevenueYes?.addEventListener("change", () => chooseZelleSetting(true, els.zelleTrueRevenueYes));
els.zelleTrueRevenueNo?.addEventListener("change", () => chooseZelleSetting(false, els.zelleTrueRevenueNo));

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
// R2-OW15 (the underwriter's Q6): the package-match notice's button shows the matched rows.
els.packageMatchNotice?.addEventListener("click", (event) => {
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
