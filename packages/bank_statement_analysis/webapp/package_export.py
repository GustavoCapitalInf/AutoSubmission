"""The package downloads: the package's flat sheet with the dashboard's words for its notices, its combined
ledger table, and its CSV and XLSX."""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime

from analysis.package.model import is_money_value, num
from analysis.package.publish import TIER_REASON_KEYS
from analysis.zelle_view import ZELLE_DEPOSITS_KEY, ZELLE_ROW_TAG

from .export_view import LARGE_UNSOURCED_DEPOSITS_KEY, downloads_view, large_deposit_keys, posted_row_key
from .spreadsheet import escaped_rows, rows_xlsx
from .statement_export import (
    PACKAGE_LARGE_UNSOURCED_DEPOSIT_FIELDS,
    large_unsourced_deposit_rows,
    lender_payment_change_rows,
    tier_cell,
    tier_reason_rows,
    zelle_deposit_rows,
)


#: A package member's id: a job's id, or `<job id>#account_<n>` for an account of a document (app.js packageMember).
_PACKAGE_MEMBER_ID = re.compile(r"(.*)#account_\d+")
#: The fields of an `excluded_account_<n>` section of the package downloads, in order.
_EXCLUDED_ACCOUNT_FIELDS = ("job_id", "filename", "account_index", "account_count", "outcome", "reason")
#: The fields of a `repeated_account_<n>` section of the package downloads, in order, before its words: an account
#: of a kept document the package leaves out as a repeat (B11's `duplicate_statement`) or as a superseded printout
#: (R14's `superseded_interim` or `superseded_long_printout`).
_REPEATED_ACCOUNT_FIELDS = ("job_id", "filename", "account_index", "account_count", "outcome", "reason",
                            "duplicate_of")


def _repeated_account_words(entry: dict, filenames: dict[str, str]) -> str:
    """A repeated account of a document as the dashboard's duplicate notice names it (app.js renderDuplicateNotice):
    "account <n> of <file> repeats <file>", then the reason's words in parentheses for a superseded printout (none for a
    B11 repeat). A job is named by its listed row's filename, "an earlier statement" where none is listed (app.js
    nameOf)."""
    def name(job_id: object) -> str:
        return (filenames.get(str(job_id)) if job_id is not None else None) or "an earlier statement"

    index = entry.get("account_index")
    shown = f"{index:,}" if isinstance(index, int) and not isinstance(index, bool) else "N/A"
    words = f"account {shown} of {name(entry.get('job_id'))} repeats {name(entry.get('duplicate_of'))}"
    reason = entry.get("reason")
    return f"{words} ({SUPERSEDED_REASON_WORDS[reason]})" if reason in SUPERSEDED_REASON_WORDS else words


#: The fields of a `returned_funder_payment_<n>` section of the package downloads, in order, before its words: the
#: served warning item's, then the re-debit's of a payment the funder re-debited.
_RETURNED_FUNDER_PAYMENT_FIELDS = (
    "funder", "amount", "debit_date", "debit_location", "credit_date", "credit_location", "credit_description",
    "source_job", "source_document", "source_account", "source_currency", "cross_statement", "credit_job",
    "credit_document", "credit_account", "represented_date", "represented_location", "represented_kind",
    "represented_job", "represented_document", "represented_account",
)


#: The readable day and the uploaded file's name as app.js writes them in the lender notes of the owner's request
#: (readableDate, statementFileName), so the download's words are the dashboard's.
_READABLE_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_STATEMENT_ID_PREFIX = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})(?:[_\s-]+|$)", re.IGNORECASE)


def _readable_date(value) -> str:
    """app.js readableDate: "Jun 22, 2026" for an ISO day; any other value as given; N/A when missing."""
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(value or ""))
    if match:
        try:
            day = datetime(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            day = None
        if day is not None:
            return f"{_READABLE_MONTHS[day.month - 1]} {day.day}, {day.year}"
    return str(value) if value else "N/A"


def _statement_file_name(name) -> str:
    """app.js statementFileName: the uploaded file's name, any leading job id or UUID (and its separator) removed."""
    text = str(name if name is not None else "").strip()
    while text and _STATEMENT_ID_PREFIX.match(text):
        text = _STATEMENT_ID_PREFIX.sub("", text, count=1).strip()
    return text


def _returned_funder_payment_source(item: dict) -> str:
    """app.js paymentChangeSourceLine for a returned funder payment's note, read without a package page's rows (the
    downloads name each statement by its file, as the dashboard does where it has no rows): none on a statement's own
    item (it names no source; a returned payment's item carries no `scope`, which only a payment change's does), "From:
    <file> → <file>" for a match across statements, else "From: <file>"."""
    if "source_job" not in item and "source_document" not in item:
        return ""

    def label(prefix: str) -> str:
        return _statement_file_name(item.get(f"{prefix}_document")) or "a statement"

    if item.get("cross_statement") is True:
        return f"From: {label('source')} → {label('credit')}"
    return f"From: {label('source')}"


def _returned_funder_payment_words(item: dict) -> str:
    """A returned funder payment as the dashboard's warning reads it (app.js returnedFunderPaymentWarning, §10.1), its
    money as the downloads write money: the amount, then the item's own unit where it names one (the overlapping
    statements' words; no unit when it is unknown). A payment matched to its return across statements names both
    documents; a payment the funder re-debited names the re-debit and is counted once in the withholding rate. In the
    plain voice of the owner's request that the dashboard now writes (a headline, its sentences, the statements it
    comes from), so the download's words are the dashboard's."""
    amount = item.get("amount")
    money = (f"{abs(float(amount)):,.2f}" + (f" {item['source_currency']}" if item.get("source_currency") else "")
             if is_money_value(amount) else "N/A")
    quoted = f' (the bank printed: "{item["credit_description"]}")' if item.get("credit_description") else ""
    sentences = [f"{item.get('funder') or 'Confirmed lender'}: a payment was returned.",
                 f"The {money} payment on {_readable_date(item.get('debit_date'))} was returned unpaid on "
                 f"{_readable_date(item.get('credit_date'))}{quoted}."]
    if item.get("represented_date"):
        where = (f" ({_statement_file_name(item.get('represented_document')) or 'a statement'})"
                 if item.get("represented_job") or item.get("represented_document") else "")
        caught_up = item.get("represented_kind") == "caught_up"
        day = _readable_date(item["represented_date"])
        sentences.append(f"It was caught up on {day}{where}, by one debit of twice the payment." if caught_up
                         else f"It was taken again on {day}{where}.")
        sentences.append("It isn't counted as paid; it is counted once in the withholding rate, by the "
                         f"{'catch-up' if caught_up else 'second debit'}.")
    else:
        sentences.append("It isn't counted as paid, but it still counts in the withholding rate.")
    source = _returned_funder_payment_source(item)
    if source:
        sentences.append(f"{source}.")
    return " ".join(sentences)


def _package_rows(package: dict) -> list[tuple[str, str, object]]:
    """The package's flat export sheet, read as the downloads read it."""
    evidence_sections = _package_evidence_sections(package)
    # The sections are read apart from the package, so they take its large deposits to source.
    flagged = large_deposit_keys(package) or frozenset()
    package = downloads_view(package)
    rows: list[tuple[str, str, object]] = []
    totals = package.get("totals") or {}
    for key, value in totals.items():
        if key in (*TIER_REASON_KEYS, ZELLE_DEPOSITS_KEY):
            continue  # emitted as readable rows below
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("totals", key, "" if value is None else value))
    rows.extend(tier_reason_rows(totals))
    # The package's Zelle figures. The setting row reads the setting the package was built under (`setting`; its
    # `counted_as_true_revenue` is the members' reading), or, on a package built before the key, its
    # `counted_as_true_revenue`, which was the setting.
    package_zelle = totals.get(ZELLE_DEPOSITS_KEY)
    package_setting = None
    if isinstance(package_zelle, dict):
        package_setting = package_zelle["setting"] if isinstance(package_zelle.get("setting"), bool) else (
            package_zelle.get("counted_as_true_revenue") is True)
    rows.extend(zelle_deposit_rows(package_zelle, setting=package_setting))
    # CURRENCY DOCTRINE §F: a refusal that only exists in the JSON payload is
    # invisible to the underwriter reading the sheet, who would see the empty
    # money cells and read them as missing data rather than as refused units.
    for key, value in (package.get("currency") or {}).items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        rows.append(("currency", key, "" if value is None else value))
    for idx, document in enumerate(package.get("documents") or [], start=1):
        for key, value in document.items():
            if key in (*TIER_REASON_KEYS, ZELLE_DEPOSITS_KEY):
                continue  # emitted as readable rows below
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            rows.append((f"document_{idx}", key, "" if value is None else value))
        if document.get("duplicate_reason") in SUPERSEDED_REASON_WORDS:
            # The words the dashboard's notice gives a left-out shorter printout or printout of more than a month.
            rows.append((f"document_{idx}", "duplicate_reason_words",
                         SUPERSEDED_REASON_WORDS[document["duplicate_reason"]]))
        rows.extend(tier_reason_rows(document, f"document_{idx}.revenue_tier"))
        rows.extend(zelle_deposit_rows(document.get(ZELLE_DEPOSITS_KEY), f"document_{idx}.revenue_tier"))
    # D-3: duplicate content must survive into the export an underwriter reads,
    # not only the JSON payload the dashboard renders.
    for idx, duplicate in enumerate(package.get("duplicates") or [], start=1):
        for key, value in duplicate.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            rows.append((f"duplicate_{idx}", key, "" if value is None else value))
    # Each listed job's filename by its id: a member id's job part to its row's filename, kept members and left-out
    # repeat rows alike, the first row of a job winning (app.js renderDuplicateNotice's nameOf), for the words below.
    filenames: dict[str, str] = {}
    for document in package.get("documents") or []:
        member = _PACKAGE_MEMBER_ID.fullmatch(str(document.get("id") or ""))
        filenames.setdefault(member[1] if member else str(document.get("id") or ""), document.get("filename"))
    # Each account left out of every figure for a reason other than a repeat (`excluded_account_<n>`), so the sheet
    # an underwriter reads names it. A repeated account of a document, a B11 repeat or an R14 superseded printout,
    # has its own `repeated_account_<n>` section below, and a whole repeated job its document row and duplicate group
    # above.
    excluded = [entry for entry in package.get("excluded_accounts") or [] if isinstance(entry, dict)]
    left_out = [entry for entry in excluded if entry.get("is_duplicate") is not True]
    for idx, entry in enumerate(left_out, start=1):
        for key in _EXCLUDED_ACCOUNT_FIELDS:
            value = entry.get(key)
            rows.append((f"excluded_account_{idx}", key, "" if value is None else value))
    # Each account of a kept document left out as a repeat, in listed order, its fields and then the dashboard
    # notice's words for it.
    repeated = [entry for entry in excluded if entry.get("is_duplicate") is True]
    for idx, entry in enumerate(repeated, start=1):
        for key in _REPEATED_ACCOUNT_FIELDS:
            value = entry.get(key)
            rows.append((f"repeated_account_{idx}", key, "" if value is None else value))
        rows.append((f"repeated_account_{idx}", "words", _repeated_account_words(entry, filenames)))
    # Each pair of overlapping statements that share credits, and the notice's words for it.
    for idx, pair in enumerate(totals.get("overlapping_statements") or [], start=1):
        for key, value in pair.items():
            rows.append((f"overlapping_statement_{idx}", key, "" if value is None else value))
        total = pair.get("shared_credit_total")
        # The shared money is the pair's account's, and its words say so; a pair whose currency is unknown prints no
        # unit, as the dashboard does.
        money = (f"{float(total):,.2f}" + (f" {pair['currency']}" if pair.get("currency") else "")
                 if is_money_value(total) else "N/A")
        rows.append((f"overlapping_statement_{idx}", "words", _overlap_words(pair, filenames, money)))
    # Each match the package passes made across its statements (`package_match_<n>`, its credit and debit as JSON) and
    # each debit they flag (`debit_flag_<n>`), the statement's words written through the escaped-row path like every
    # other cell.
    for section, entries in (("package_match", package.get("package_matches")), ("debit_flag", package.get("debit_flags"))):
        for idx, entry in enumerate(entries or [], start=1):
            for key, value in entry.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                rows.append((f"{section}_{idx}", key, "" if value is None else value))
    # §10.8: after the debit flags, each member's large unsourced deposit (`large_unsourced_deposit_<n>`),
    # its statement, account and unit named, its share its own statement's.
    rows.extend(large_unsourced_deposit_rows(package.get(LARGE_UNSOURCED_DEPOSITS_KEY),
                                              PACKAGE_LARGE_UNSOURCED_DEPOSIT_FIELDS))
    # Each lump-sum payoff (in paid to lenders, out of the withholding rate), `lump_sum_payoff_<n>`, its words the bank's,
    # through the escaped-row path.
    for idx, item in enumerate(package.get("lump_sum_payoffs") or [], start=1):
        if isinstance(item, dict):
            for key, value in item.items():
                rows.append((f"lump_sum_payoff_{idx}", key, "" if value is None else value))
    for idx, funder in enumerate(package.get("funders") or [], start=1):
        for key, value in funder.items():
            rows.append((f"funder_{idx}", key, "" if value is None else value))
    # Each funder payment the bank returned unpaid, as the package serves it, its fields and then the dashboard's
    # warning line, each in its own statement's unit (a refused package sums none of them).
    returned = [item for item in package.get("returned_funder_payments") or [] if isinstance(item, dict)]
    for idx, item in enumerate(returned, start=1):
        for key in _RETURNED_FUNDER_PAYMENT_FIELDS:
            value = item.get(key)
            rows.append((f"returned_funder_payment_{idx}", key, "" if value is None else value))
        rows.append((f"returned_funder_payment_{idx}", "words", _returned_funder_payment_words(item)))
    for idx, funder in enumerate(package.get("potential_lenders") or [], start=1):
        for key, value in funder.items():
            rows.append((f"potential_lender_{idx}", key, "" if value is None else value))
    # Each lender payment change across the package's statements, and each member not checked across statements with
    # its reason.
    rows.extend(lender_payment_change_rows(package.get("lender_payment_changes"), package=True))
    for idx, entry in enumerate(package.get("lender_payment_changes_unchecked") or [], start=1):
        for key in ("source_document", "reason"):
            value = entry.get(key) if isinstance(entry, dict) else None
            rows.append((f"lender_payment_unchecked_{idx}", key, "" if value is None else value))
    # §10.8: each month's active and possible positions, the accounts added up, as the copied memo names them
    # (`active_positions_month_<n>`); N/A an empty cell.
    for idx, entry in enumerate(package.get("active_positions_by_month") or [], start=1):
        for key in ("month", "active_positions", "possible_positions"):
            value = entry.get(key) if isinstance(entry, dict) else None
            rows.append((f"active_positions_month_{idx}", key, "" if value is None else value))
    for idx, provider in enumerate(package.get("insurance_providers") or [], start=1):
        for key, value in provider.items():
            rows.append((f"insurance_provider_{idx}", key, "" if value is None else value))
    # Lender detection §8.4: one section per flagged payee, `flagged_<group>_<n>`. The package holds only the
    # groups Settings ticks, so the sheet follows Settings.
    for group, items in (package.get("flagged_positions") or {}).items():
        for idx, item in enumerate(items, start=1):
            for key, value in item.items():
                rows.append((f"flagged_{group}_{idx}", key, "" if value is None else value))
    for idx, evidence in enumerate(package.get("lender_evidence") or [], start=1):
        for key, value in evidence.items():
            rows.append((f"lender_evidence_{idx}", key, "" if value is None else value))
    for idx, evidence in enumerate(package.get("potential_lender_evidence") or [], start=1):
        for key, value in evidence.items():
            rows.append((f"potential_lender_evidence_{idx}", key, "" if value is None else value))
    for idx, evidence in enumerate(package.get("insurance_evidence") or [], start=1):
        for key, value in evidence.items():
            rows.append((f"insurance_evidence_{idx}", key, "" if value is None else value))
    # One evidence section per tier, so credits in True and held ones (out of it) never share a section
    # (`_package_evidence_sections`), each record read as the downloads read it.
    for section, records in evidence_sections:
        for idx, evidence in enumerate(downloads_view(records, flagged=flagged), start=1):
            for key, value in evidence.items():
                rows.append((f"{section}_{idx}", key, "" if value is None else value))
    return rows


def _package_evidence_sections(package: dict) -> tuple[tuple[str, list], ...]:
    """The package's revenue evidence, one section per tier, from the served lists, every posted credit of every member
    in exactly one. Per true revenue spec §2.2 and §10.8, the credits in True revenue are one
    section, `true_revenue_evidence` (the members' verified credits and their counted ones), where they were a Verified
    and a Counted section, written even where the package's True is N/A (a member analysed before 5.6), so a 5.6
    member's credits are never in no section; then the held credits; a member analysed before 5.6 (no tier) has its
    credits under its states in the page's words, `revenue_evidence` and `review_required_evidence` (5.4's unverified
    deposits, its review set); then every member's non-revenue credits. The True section is in the package ledger's
    order (`transactions`: each member's rows as printed, the members in the package's order), as a statement's True
    evidence is in its ledger's, where the served lists put every verified credit before every counted one, so that the
    point where its dates went back marked the counted tier."""
    verified = [record for record in package.get("verified_revenue_evidence") or [] if isinstance(record, dict)]
    unverified = [record for record in package.get("unverified_deposit_evidence") or [] if isinstance(record, dict)]

    def tiered(record: dict) -> bool:
        return isinstance(record.get("revenue_tier"), str)

    transactions = package.get("transactions") or []
    ledger: dict[tuple, int] = {}
    for position, transaction in enumerate(transactions):
        if isinstance(transaction, dict) and isinstance(transaction.get("classification"), dict):
            key = posted_row_key(transaction.get("source_job"), transaction.get("source_account"),
                                  transaction["classification"].get("source_location"))
            ledger.setdefault(key, position)

    def ledger_position(record: dict) -> int:
        # A record the ledger does not list (none is expected) follows those it does, in served order (a stable sort).
        return ledger.get(posted_row_key(record.get("source_job"), record.get("source_account"),
                                          record.get("source_location")), len(transactions))

    in_true = sorted([record for record in verified if tiered(record)]
                     + [record for record in unverified if record.get("revenue_tier") == "counted_flagged"],
                     key=ledger_position)
    return (
        ("true_revenue_evidence", in_true),
        ("excluded_pending_review_evidence",
         [record for record in unverified if record.get("revenue_tier") == "excluded_pending_review"]),
        ("revenue_evidence", [record for record in verified if not tiered(record)]),
        ("review_required_evidence", [record for record in unverified if not tiered(record)]),
        ("non_revenue_evidence", package.get("non_revenue_evidence") or []),
    )


#: The columns of the package downloads' ledger table. True revenue spec §2.2, §10.8: no `state` column (the 5.4 state,
#: `verified_revenue` or `unverified_deposit`); the tier and reason are read through `downloads_view`.
_PACKAGE_TRANSACTION_COLUMNS = ("source_document", "source_account", "source_currency", "date", "description",
                                "amount", "classification", "tier", "reason", "review_status")


def _package_transaction_table(package: dict) -> list[tuple]:
    """The package's combined ledger (`transactions`), one row per posting, each naming its statement, account and
    currency: a `columns` row, then `(package_transaction, n, ...)`, its tier and reason as the downloads read them
    (`downloads_view`). Written after the flat rows; its statement text reaches a file only through `escaped_rows`."""
    package = downloads_view(package)
    rows: list[tuple] = []
    tagged: list[bool] = []
    for transaction in package.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        record = transaction.get("classification") if isinstance(transaction.get("classification"), dict) else {}
        rows.append(("package_transaction", len(rows) + 1, transaction.get("source_document") or "",
                     "" if transaction.get("source_account") is None else transaction["source_account"],
                     transaction.get("source_currency") or "", transaction.get("date") or "",
                     transaction.get("description") or "", num(transaction.get("amount")),
                     record.get("classification") or "", tier_cell(record),
                     record.get("revenue_tier_reason") or "", record.get("revenue_review_status") or ""))
        tagged.append(transaction.get(ZELLE_ROW_TAG) is True)
    if not rows:
        return []
    # The trailing `zelle` column, only where a row carries the served Zelle tag.
    if any(tagged):
        return [("package_transaction", "columns", *_PACKAGE_TRANSACTION_COLUMNS, "zelle"),
                *((*row, "Zelle" if zelle else "") for row, zelle in zip(rows, tagged))]
    return [("package_transaction", "columns", *_PACKAGE_TRANSACTION_COLUMNS), *rows]


def package_csv(package: dict) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    writer.writerows(escaped_rows(_package_rows(package) + _package_transaction_table(package)))
    return buf.getvalue()


def package_xlsx(package: dict) -> bytes:
    return rows_xlsx(_package_rows(package) + _package_transaction_table(package))


#: The words a left-out shorter printout reads in the package downloads, as the dashboard's duplicate notice reads them
#: (app.js DUPLICATE_REASON_WORDS).
SUPERSEDED_INTERIM_WORDS = "a shorter printout of days another statement covers"
#: The words a left-out printout of more than a month reads (app.js DUPLICATE_REASON_WORDS), whose rows
#: the account's other statements print.
SUPERSEDED_LONG_PRINTOUT_WORDS = "a printout of more than a month whose every row other statements of the account print"
#: Each reason `package_superseded` leaves a statement out for, and its words.
SUPERSEDED_REASON_WORDS = {
    "superseded_interim": SUPERSEDED_INTERIM_WORDS,
    "superseded_long_printout": SUPERSEDED_LONG_PRINTOUT_WORDS,
}


def _overlap_words(pair: dict, filenames: dict[str, str], money: str) -> str:
    """A pair of overlapping statements as the package names it (app.js overlappingStatementWords reads the same
    words). A pair named although it shares no credit (a period inside the other, or more than three common days)
    reads the days the two cover."""
    count = pair.get("shared_credit_count") or 0
    names = (f"{filenames.get(pair.get('job'), pair.get('job'))} and "
             f"{filenames.get(pair.get('other'), pair.get('other'))}")
    if not count:
        return f"{names} cover {pair.get('days_shared')} of the same days of one account"
    return (f"{names} share {count} {'credit' if count == 1 else 'credits'} ({money}) in the days both cover, "
            "counted in both")
