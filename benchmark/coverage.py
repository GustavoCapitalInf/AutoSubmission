"""MoneyThumb field-coverage proof.

EVERY JSON path observed in the MoneyThumb payloads must resolve to exactly
one disposition:

- ``compared``           - the path feeds one or more comparison rows;
- ``skipped_by_verdict`` - deliberately not compared, citing the
  FIELD_MAPPING.md verdict (IGNORE / ADOPT / DERIVE / HAVE-partial) that
  covers it;
- ``capability``         - recorded as a capability finding rather than a
  field comparison (multi-account emission, OCR-webhook stub, ...).

Any path matching no rule is reported as UNMAPPED, which fails the rollup's
completeness check - that is the "no silent omissions" guarantee.

Resolution is longest-matching-prefix, so specific paths always beat general
buckets.  Verdict citations refer to
``docs/moneythumb-replacement/FIELD_MAPPING.md`` sections.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CoverageRule:
    prefix: str
    disposition: str          # compared | skipped_by_verdict | capability
    verdict: str              # FIELD_MAPPING verdict (or "-" for compared)
    note: str


BASE_RULES: tuple[CoverageRule, ...] = (
    # ---------------- appinfo (FIELD_MAPPING section 1) ----------------
    CoverageRule("appinfo.webSearch", "skipped_by_verdict", "IGNORE",
                 "webSearch.* never populated in benchmark; separate product decision (s1)."),
    CoverageRule("appinfo.accountlist", "capability", "ADOPT",
                 "Multi-account list - we lack a multi-account schema; recorded as capability finding (s1)."),
    CoverageRule("appinfo.naccounts", "capability", "ADOPT",
                 "Multi-account count - capability finding: MT splits accounts, we analyze the primary account (s1)."),
    CoverageRule("appinfo.appid", "skipped_by_verdict", "ADOPT",
                 "Durable package/application entity not yet built (s1)."),
    CoverageRule("appinfo.appnumber", "skipped_by_verdict", "ADOPT",
                 "Durable package/application entity not yet built (s1)."),
    CoverageRule("appinfo.citystate", "skipped_by_verdict", "IGNORE",
                 "Redundant concatenation (s1)."),
    CoverageRule("appinfo.owner", "skipped_by_verdict", "ADOPT",
                 "Account-holder identity extraction not yet built; MT's own value misfires (bmo: 'Interest Earned') (s1)."),
    CoverageRule("appinfo.address", "skipped_by_verdict", "ADOPT",
                 "Holder identity fields - not yet extracted; never emitted into reports (s1)."),
    CoverageRule("appinfo.city", "skipped_by_verdict", "ADOPT",
                 "Holder identity fields - not yet extracted (s1)."),
    CoverageRule("appinfo.state", "skipped_by_verdict", "ADOPT",
                 "Holder identity fields - not yet extracted (s1)."),
    CoverageRule("appinfo.zip", "skipped_by_verdict", "ADOPT",
                 "Holder identity fields - not yet extracted (s1)."),
    CoverageRule("appinfo.totalstatements_reconciled", "skipped_by_verdict", "HAVE (partial)",
                 "Package completed/failed exists; explicit reconciled count is a small ADOPT (s1)."),
    CoverageRule("appinfo.totalstatements", "compared", "-",
                 "Feeds the package file-count comparison (package_file_count row)."),
    CoverageRule("appinfo.totaltax", "skipped_by_verdict", "IGNORE",
                 "Tax documents are out of scope (s1)."),
    CoverageRule("appinfo.expfactor", "skipped_by_verdict", "IGNORE",
                 "Empty/unclear in every benchmark run (s1)."),
    # ---------------- file_status (section 2) ----------------
    CoverageRule("file_status", "skipped_by_verdict", "HAVE (partial)",
                 "Ops/job status fields; needs durable IDs + error taxonomy, not a financial comparison (s2)."),
)


# The wrapper/results table is long; build it programmatically for clarity.
def _rules() -> tuple[CoverageRule, ...]:
    rules: list[CoverageRule] = list(BASE_RULES)

    results = "statement_summaries[].results[]."
    add = rules.append

    # --- document identification / results rows (section 3) ---
    for path in ("startDate", "endDate"):
        add(CoverageRule(results + path, "compared", "-", "Feeds period_start/period_end rows."))
    for path in ("firstDate", "lastDate"):
        add(CoverageRule(results + path, "skipped_by_verdict", "DERIVE",
                         "First/last transaction dates - trivial derive, not yet emitted (s3)."))
    for path in ("startBalance", "endBalance", "endBalanceCalc", "endBalancePDF"):
        add(CoverageRule(results + path, "compared", "-",
                         "Feeds beginning/ending balance rows (calc/PDF variants recorded as commentary)."))
    for path in ("balancesValid", "reconciled", "fail", "headerValid", "columnsValid", "donegate", "negate"):
        add(CoverageRule(results + path, "compared", "-",
                         "Feeds the reconciliation_verdict row (our ReconResult carries more detail, s3)."))
    for path in ("numCredits", "numDebits", "totCredits", "totDebits", "numTransactions", "nsfcount"):
        add(CoverageRule(results + path, "compared", "-", "Feeds volume/count/NSF rows."))
    add(CoverageRule(results + "accountNumber", "compared", "-",
                     "Feeds account_number row (masked to last-4 in all reports)."))
    add(CoverageRule(results + "isStrongAccountNo", "skipped_by_verdict", "ADOPT",
                     "Account-number confidence flag - planned alongside masking policy (s3)."))
    add(CoverageRule(results + "bankName", "compared", "-", "Feeds bank_name row."))
    add(CoverageRule(results + "bankURL", "skipped_by_verdict", "IGNORE",
                     "Cosmetic placeholder values even in MT (s3)."))
    add(CoverageRule(results + "bankphones", "skipped_by_verdict", "IGNORE",
                     "Cosmetic placeholder values even in MT (s3)."))
    add(CoverageRule(results + "fdic", "skipped_by_verdict", "ADOPT (P2)",
                     "FDIC registry enrichment - public dataset join, planned P2 (s3)."))
    for path in ("accounttype", "accounttypestr", "accounttitle", "accountOwner",
                 "company", "isBusiness", "name", "address1", "address2", "city",
                 "state", "postalcode", "country", "email"):
        add(CoverageRule(results + path, "skipped_by_verdict", "ADOPT",
                         "Account type / holder identity extraction - schema lacks it; MT's own lists are noisy (s3)."))
    for path in ("accountSequence", "numAccounts"):
        add(CoverageRule(results + path, "capability", "ADOPT",
                         "Multi-account segmentation metadata - capability finding (s3)."))
    for path in ("isMonthToDate", "numMonths", "monthSequence"):
        add(CoverageRule(results + path, "skipped_by_verdict", "DERIVE",
                         "Package coherence checks (G5) - not yet derived (s3)."))
    add(CoverageRule(results + "currencycode", "compared", "-", "Feeds currency row."))
    for path in ("language", "pagecount", "detectedDocType", "processedDocType", "docType"):
        add(CoverageRule(results + path, "skipped_by_verdict", "ADOPT",
                         "Document-inspection record (doc type/language/pages) - planned (s3)."))
    for path in ("producer", "cdate", "mdate", "image", "ocr", "maxResolution", "minResolution"):
        add(CoverageRule(results + path, "skipped_by_verdict", "ADOPT",
                         "PDF forensics inputs for the fraud/integrity subsystem (G6) (s3)."))
    add(CoverageRule(results + "uselessPages", "skipped_by_verdict", "DERIVE",
                     "Page-utility classification - small extension of missing-page detection (s3)."))
    for path in ("uncounted", "numTypos", "suspectCount", "likelyMissingTransactions", "nonTransactions"):
        add(CoverageRule(results + path, "skipped_by_verdict", "HAVE (partial)",
                         "Coverage bands + integrity flags cover most; typo/suspect signal is a DERIVE (s3)."))
    add(CoverageRule(results + "suggestion", "skipped_by_verdict", "ADOPT",
                     "Operator-facing next-step hints - high UX value, low cost (s3)."))
    for path in ("requiresRerunWithOCR", "previewRequired"):
        add(CoverageRule(results + path, "skipped_by_verdict", "HAVE (partial)",
                         "Worker ladder does this implicitly; explicit flag planned (s3)."))
    for path in ("fraudscore", "tpreasons", "tpreasonsIndexes"):
        add(CoverageRule(results + path, "skipped_by_verdict", "ADOPT",
                         "Composite tamper score with reasons (G6) - planned; score duplication not copied (s3)."))
    add(CoverageRule(results + "thumbprintData", "skipped_by_verdict", "IGNORE",
                     "Empty/dead in every benchmark payload (s3)."))
    add(CoverageRule(results + "filePreviouslySeen", "skipped_by_verdict", "ADOPT",
                     "Duplicate-submission detection via content hash (R-26) - planned (s2)."))
    add(CoverageRule(results + "webhook", "skipped_by_verdict", "ADOPT",
                     "Async completion callback for scanned documents (G7) (s2)."))
    for path in ("returnType", "remaining", "chargevalue"):
        add(CoverageRule(results + path, "skipped_by_verdict", "IGNORE",
                         "Billing units - not applicable in-house (s2)."))
    add(CoverageRule(results + "transactions", "capability", "IGNORE",
                     "Always null: MT omits the full transaction ledger from the response - capability finding "
                     "(our JSON carries the complete classified ledger, s2/s8)."))
    for path in ("statementid", "fileConversionId", "trackingId", "webReport",
                 "taxForms", "form", "financialResult", "accountInfo", "location",
                 "detectedDocTypeText", "processedDocTypeText"):
        add(CoverageRule(results + path, "skipped_by_verdict", "IGNORE",
                         "Internal IDs / dead or placeholder fields ('nullnull, null null') (s2/s3)."))
    add(CoverageRule(results + "overDraftLimit", "skipped_by_verdict", "IGNORE (P3)",
                     "Requires overdraft-limit extraction; niche (s5)."))

    # --- statement_summaries wrapper fields (section 2) ---
    wrapper = "statement_summaries[]."
    for path in ("logurl", "csvurl", "outputurl"):
        add(CoverageRule(wrapper + path, "skipped_by_verdict", "IGNORE",
                         "Deprecated in MT itself (s2)."))
    for path in ("error", "tid", "uniqueTid", "statementid", "statementseq",
                 "convertedstatements", "convertedtaxforms"):
        add(CoverageRule(wrapper + path, "skipped_by_verdict", "HAVE (partial)",
                         "Ops/job bookkeeping; durable IDs + error taxonomy planned (s2)."))
    for path in ("taxform", "taxsales", "taxgross", "taxincome", "taxableincome"):
        add(CoverageRule(wrapper + path, "skipped_by_verdict", "IGNORE",
                         "Tax documents are out of scope (s1)."))

    # ---------------- scorecard (sections 4-7) ----------------
    sc = "scorecard."
    add(CoverageRule(sc + "_metadata", "skipped_by_verdict", "HAVE (partial)",
                     "Processing warnings/ops metadata; our quality/integrity objects carry more detail (s6)."))

    # revenue_statistics: compared via the revenue rows; the loose-table format
    # itself is an IGNORE (s7: 'never a stringly stats table').
    add(CoverageRule(sc + "revenue_statistics", "compared", "-",
                     "27 label/monthly/annual rows recorded side-by-side; 'Total Revenue' row pre-ruled "
                     "DIFFERENT_DEFINITION (equals net cash flow); remaining rows map to ADOPT/DERIVE "
                     "underwriting stats per s7; the loose-table format itself is IGNORE."))

    # statements_summary (section 6) - compared core fields first.
    ss = sc + "statements_summary[]."
    for path in ("account", "start_date", "ending_date", "reconciled",
                 "starting_balance", "ending_balance", "total_credits",
                 "num_credits", "total_debits", "num_debits", "avg_balance",
                 "min_balance", "days_neg", "num_nsfs", "total_nsfs",
                 "net_cashflow", "bank_name", "true_credits", "nontrue_credits",
                 "other_credits", "num_true_credits", "num_nontrue_credits",
                 "num_other_credits", "true_debits", "nontrue_debits",
                 "num_true_debits", "num_nontrue_debits", "true_expenses",
                 "true_profit", "mca_debits", "mca_credits", "num_mcas",
                 "mca_withhold_percent", "num_of_mca_positions",
                 "mcas_with_deposits", "mca_deposit_dates",
                 "mca_credits_net_returns"):
        add(CoverageRule(ss + path, "compared", "-",
                         "Feeds statement-level / revenue-taxonomy / MCA comparison rows."))
    for path in ("statement_month", "statement_month_num",
                 "statement_month_num_and_name", "statement_month_name_and_year",
                 "statement_year", "accountidx", "statement_id", "balance_match",
                 "file_previously_seen"):
        add(CoverageRule(ss + path, "skipped_by_verdict", "IGNORE",
                         "Redundant renderings / positional-internal IDs / dead fields (s6); "
                         "file_previously_seen duplicated from results[] (ADOPT there)."))
    for path in ("fraud_score", "thumbprint_score"):
        add(CoverageRule(ss + path, "skipped_by_verdict", "ADOPT",
                         "Composite tamper score (G6); MT's score duplication is a schema defect (s6)."))
    add(CoverageRule(ss + "avg_true_balance", "skipped_by_verdict", "ADOPT",
                     "True-balance duality - planned derivation from our classification (s5)."))
    add(CoverageRule(ss + "low_days", "skipped_by_verdict", "DERIVE",
                     "Days below threshold - trivial over our validated ledger (s6)."))
    for path in ("num_ods", "total_overdraft_amount", "num_stops", "days_w_returns",
                 "total_returns", "num_of_returns"):
        add(CoverageRule(ss + path, "skipped_by_verdict", "ADOPT",
                         "OD events / stop payments / returns as distinct classifier states - planned (s6)."))
    for path in ("num_transfers", "num_incoming_transfers", "num_outgoing_transfers",
                 "transfers_total", "incoming_transfers_total", "outgoing_transfers_total"):
        add(CoverageRule(ss + path, "skipped_by_verdict", "ADOPT",
                         "Cross-account transfer matching (PARITY #14) requires multi-account entities (s4)."))
    add(CoverageRule(ss + "month_gap", "skipped_by_verdict", "DERIVE",
                     "Package coherence check (G5) (s3)."))
    for path in ("bank_address", "bank_zipcode", "bank_city", "bank_state", "fdic_bank_name"):
        add(CoverageRule(ss + path, "skipped_by_verdict", "ADOPT (P2)",
                         "FDIC registry enrichment (s3)."))
    add(CoverageRule(ss + "account_owner", "skipped_by_verdict", "ADOPT",
                     "Holder identity - MT's own value misfires ('Opening Balance') (s3)."))
    for path in ("recovery_debits", "recovery_credits"):
        add(CoverageRule(ss + path, "skipped_by_verdict", "IGNORE",
                         "Recovery structure empty/unknown in every benchmark payload (s5)."))
    # Category counters (~20) - ADOPT (selective) per s6.
    add(CoverageRule(ss, "skipped_by_verdict", "ADOPT (selective)",
                     "Category counters (payroll/insurance/factoring/processor/tolls/'nefarious'/...): "
                     "selective adoption per s6; 'nefarious' and niche verticals IGNORE."))

    # thumbprints (section 3/6).
    add(CoverageRule(sc + "thumbprints", "skipped_by_verdict", "ADOPT",
                     "Composite tamper score with contributing factors (G6) - planned (s3)."))

    # Transaction lists (section 4).
    for lst in ("credit_transactions", "true_credit_transactions", "nontrue_credit_transactions"):
        for path in ("date", "amount", "description", "accountidx"):
            add(CoverageRule(f"{sc}{lst}[].{path}", "compared", "-",
                             "Feeds the revenue-taxonomy comparison (our three-state classification vs "
                             "MT's binary true/non-true, s4)."))
        add(CoverageRule(f"{sc}{lst}[].memo", "skipped_by_verdict", "HAVE (partial)",
                         "Raw ACH detail retained in our description; subfield parsing is a later DERIVE (s4)."))
        for path in ("id", "number", "type"):
            add(CoverageRule(f"{sc}{lst}[].{path}", "skipped_by_verdict", "IGNORE",
                             "Always '0'/'' or internal id in MT output (s4)."))
        add(CoverageRule(f"{sc}{lst}[]", "compared", "-",
                         "Empty-list rendering of the same revenue-taxonomy comparison."))
    for path in ("lender", "date", "amount", "description", "accountidx"):
        add(CoverageRule(f"{sc}mca_transactions[].{path}", "compared", "-",
                         "Feeds the per-lender MCA comparison rows."))
    for path in ("id", "memo", "number", "type"):
        add(CoverageRule(f"{sc}mca_transactions[].{path}", "skipped_by_verdict", "IGNORE",
                         "Dead/internal transaction subfields (s4)."))
    add(CoverageRule(sc + "mca_transactions[]", "compared", "-",
                     "Empty-list rendering of the per-lender MCA comparison."))
    add(CoverageRule(sc + "incoming_transfers", "skipped_by_verdict", "ADOPT",
                     "Cross-account counterpart matching (PARITY #14) - requires package entities (s4)."))
    add(CoverageRule(sc + "outgoing_transfers", "skipped_by_verdict", "ADOPT",
                     "Cross-account counterpart matching (PARITY #14) (s4)."))
    add(CoverageRule(sc + "large_transactions", "skipped_by_verdict", "DERIVE",
                     "Trivial view over the ledger we already emit in full (s4)."))
    add(CoverageRule(sc + "repeating_transactions", "skipped_by_verdict", "HAVE (partial)",
                     "Our recurring detection is cadence-gated/lender-oriented; widening to a general "
                     "recurring view is planned (s4)."))
    add(CoverageRule(sc + "nsf_transactions", "compared", "-",
                     "Feeds the nsf_count row (list empty in every benchmark set)."))
    for lst in ("overdraft_transactions", "returned_transactions"):
        add(CoverageRule(sc + lst, "skipped_by_verdict", "HAVE",
                         "Classified rows with evidence exist on our side; MT's lists were empty in all "
                         "benchmark sets (s4)."))

    # Time series (section 5).
    add(CoverageRule(sc + "daily_balances[].balances[].od_balance", "skipped_by_verdict", "IGNORE (P3)",
                     "Requires overdraft-limit extraction; niche (s5)."))
    add(CoverageRule(sc + "daily_balances[].balances[].true_balance", "skipped_by_verdict", "ADOPT",
                     "True-balance daily series - planned derivation (s5)."))
    add(CoverageRule(sc + "daily_balances", "compared", "-",
                     "Feeds the daily_balance_series row: MT activity-day balances checked against our "
                     "validated per-calendar-day ledger (s5)."))
    for path in ("daily_cash_flows", "monthly_cash_flows"):
        add(CoverageRule(sc + path, "skipped_by_verdict", "DERIVE",
                         "Trivial from the ledger (s5)."))
    add(CoverageRule(sc + "monthly_negative_days[].negative_days[].negdayscount", "compared", "-",
                     "Feeds the negative_days row."))
    add(CoverageRule(sc + "monthly_negative_days[].negative_days[].negdays", "compared", "-",
                     "Feeds the negative_days row (per-day list)."))
    add(CoverageRule(sc + "monthly_negative_days", "skipped_by_verdict", "ADOPT/IGNORE",
                     "true-balance variant ADOPT; od variant IGNORE with od_balance (s5)."))
    add(CoverageRule(sc + "monthly_recovery", "skipped_by_verdict", "IGNORE",
                     "Empty in every benchmark payload; structure unknown (s5)."))
    add(CoverageRule(sc + "monthly_mca[].workdays", "skipped_by_verdict", "DERIVE",
                     "Workday count - trivial calendar derivation (s5)."))
    add(CoverageRule(sc + "monthly_mca", "compared", "-",
                     "Feeds per-lender funding-deposit and monthly-cadence comparison rows (s5)."))

    return tuple(rules)


RULES: tuple[CoverageRule, ...] = _rules()


#: Longest-prefix-first so specific paths always beat general buckets.
_RULES_BY_LENGTH: tuple[CoverageRule, ...] = tuple(
    sorted(RULES, key=lambda rule: len(rule.prefix), reverse=True)
)


def disposition_for(path: str) -> CoverageRule | None:
    for rule in _RULES_BY_LENGTH:
        if path.startswith(rule.prefix):
            return rule
    return None


def classify_paths(paths: Iterable[str]) -> dict[str, dict]:
    """Map every observed MT JSON path to its disposition; report unmapped."""
    mapped: dict[str, dict] = {}
    for path in sorted(paths):
        rule = disposition_for(path)
        if rule is None:
            mapped[path] = {"disposition": "UNMAPPED", "verdict": "", "note": ""}
        else:
            mapped[path] = {
                "disposition": rule.disposition,
                "verdict": rule.verdict,
                "note": rule.note,
            }
    return mapped


def coverage_summary(paths: Iterable[str]) -> dict:
    mapped = classify_paths(paths)
    counts: dict[str, int] = {}
    unmapped = []
    for path, entry in mapped.items():
        counts[entry["disposition"]] = counts.get(entry["disposition"], 0) + 1
        if entry["disposition"] == "UNMAPPED":
            unmapped.append(path)
    return {
        "total_paths": len(mapped),
        "counts": counts,
        "unmapped": unmapped,
        "complete": not unmapped,
        "paths": mapped,
    }
