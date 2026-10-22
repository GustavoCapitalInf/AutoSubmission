"""The statement downloads: the flat `(section, field, value)` sheet of a statement, its posted-credit and
posted-debit tables, and its CSV and XLSX. The package downloads reuse its section builders."""
from __future__ import annotations

import csv
import io
import json
import re

from analysis.adb import ADVISORY_VALIDATIONS as ADB_ADVISORY_VALIDATIONS
from analysis.flag_groups import FLAG_GROUP_BY_KEY
from analysis.holder_name import PREMIUM_TRUST_WORDS
from analysis.package.model import num, statement_currency
from analysis.package.publish import TIER_REASON_KEYS
from analysis.payload_shape import is_document_payload, payload_accounts, payload_document_block
from analysis.revenue_view import LARGE_UNSOURCED_DEPOSIT_FIELDS
from analysis.zelle_view import ZELLE_DEPOSITS_KEY, ZELLE_ROW_TAG

from .export_view import LARGE_UNSOURCED_DEPOSITS_KEY, downloads_view
from .spreadsheet import escaped_rows, rows_xlsx


def _adb_rows(metrics: dict) -> list[tuple[str, str, object]]:
    """The Average Daily Balance working, one row per calendar day, so an
    underwriter can re-add the column in a spreadsheet and land on the same
    figure. Kept out of the flattened `metrics` section, where the whole daily
    ledger would collapse into a single unreadable JSON cell.

    A validation reads "pass" or "FAIL"; one of `ADB_ADVISORY_VALIDATIONS`,
    which decides nothing, reads "advisory pass" or "advisory FAIL", so its
    False on a published ADB is not read as a failed required check."""
    adb = metrics.get("adb")
    if not isinstance(adb, dict):
        return []
    validated = (
        metrics.get("adb_ok") is True
        and metrics.get("average_daily_balance") is not None
        and adb.get("ok") is True
    )
    rows: list[tuple[str, str, object]] = []
    for key in (
        "period_start", "period_end", "calendar_day_count",
        "opening_balance", "opening_balance_source", "closing_balance",
        "computed_closing_balance", "total_credits", "total_debits",
        "ok", "reconciled",
    ):
        item = adb.get(key)
        rows.append(("adb", key, "" if item is None else item))
    if validated:
        rows.append(("adb", "daily_balance_sum", adb.get("daily_balance_sum", "")))
    for name, passed in (adb.get("validations") or {}).items():
        verdict = "pass" if passed else "FAIL"
        if name in ADB_ADVISORY_VALIDATIONS:
            verdict = f"advisory {verdict}"
        rows.append(("adb_validation", name, verdict))
    for warning in adb.get("warnings") or []:
        rows.append(("adb_warning", "", warning))
    if validated:
        for day in adb.get("daily_balances") or []:
            rows.append(("adb_daily_balance", day.get("date", ""), day.get("ending_balance", "")))
    return rows


#: Payload keys that exist for API compatibility and must NOT be flattened into
#: the analyst-facing exports.
#:
#: `statement.stated_average_balance` is the deprecated alias of
#: `statement.bank_reported_average_balance` and carries the identical number.
#: It stays in the JSON payload, where a consumer of the old name would
#: otherwise break — that is the whole point of the alias. A CSV or XLSX sheet
#: is not that contract: it is a flat sheet a human reads, and printing the
#: bank's figure on three rows (statement canonical, statement alias, metrics
#: echo) reads as an extraction fault rather than as a compatibility shim. The
#: canonical row and the long-standing `metrics` echo both remain, so nothing
#: an analyst needs is lost and no reader has to work out which of three
#: identical numbers is authoritative.
_EXPORT_SUPPRESSED_KEYS = {("statement", "stated_average_balance")}

#: §10.8, §17.1: the words that make a printed account title read as a bank's account designation in the statement
#: CSV/XLSX: analysis/holder_name.py's `_DESIGNATION_WORDS` (copied, not imported, so the reader stays private; a test
#: pins that every one of them is here), then the account words and the product words the banks print as a title ('US
#: BUSINESS ACCOUNT', 'CAD CHEQUING ACCOUNT', '(RECEIVABLES)'), then the Lloyd's market's name, which a bank prints as
#: the designation of an insurance agency's account holding Lloyd's premiums ('LLOYDS OF LONDON' after the agency's
#: legal form; Lloyd's of London, the public insurance market, requires its coverholders to keep the premiums they
#: collect in a separate trust account).
_EXPORT_DESIGNATION_WORDS = frozenset({
    "PREMIUM", "TRUST", "OPERATING", "WIRE", "PRODUCER", "PAYABLE", "ESCROW", "PAYROLL", "CLIENT", "CLIENTS",
    "CUSTOMER", "RESERVE", "TAX", "GENERAL", "SWEEP", "MAIN", "IOLTA", "DEPOSIT", "DISBURSEMENT", "COLLECTION",
    "ACCOUNT", "ACCT", "CHECKING", "CHEQUING", "SAVINGS", "RECEIVABLE", "RECEIVABLES",
    "LLOYDS", "LLOYD'S",
})
#: The premium-trust words (holder_name.PREMIUM_TRUST_WORDS, public: 'PREM TRST', 'PREMIUM FUNDS TRUST').
_EXPORT_PREMIUM_TRUST_TITLE = re.compile(PREMIUM_TRUST_WORDS)
#: The punctuation a title's word is trimmed of at either end, brackets included ('(RECEIVABLES)' is RECEIVABLES).
_TITLE_WORD_TRIM = "()[]{}<>.,;:!?'\"-/#*&"


def _designation_title(title: object) -> bool:
    """Whether a printed account title reads as a bank's account designation: a word of it, read upper case with its
    dots dropped and its brackets and punctuation trimmed, is in `_EXPORT_DESIGNATION_WORDS`, or it prints the
    premium-trust words. An owner's name or a legal-form fragment ('LIABILITY', 'BILLS') does not."""
    if not isinstance(title, str) or not title.strip():
        return False
    text = title.upper()
    if _EXPORT_PREMIUM_TRUST_TITLE.search(text):
        return True
    return any(token.replace(".", "").strip(_TITLE_WORD_TRIM) in _EXPORT_DESIGNATION_WORDS for token in text.split())


def _analysis_rows(analysis: dict) -> list[tuple[str, str, object]]:
    """The flat export sheet for one published payload.

    A document carrying several accounts renders EVERY account, each under its
    own section prefix in printed order, with the document's own facts in a
    `document` section of their own. Measured before this teaching, the same
    call returned ZERO rows for a document payload: an underwriter would have
    downloaded an empty sheet for a statement that reconciled.

    The section prefix is what keeps two accounts apart. The flat sheet is
    keyed on `(section, field)`, so two accounts writing `("statement",
    "ending_balance")` would collide and one would silently win.

    True revenue spec §2.2, §10.8: the payload is read as the downloads read it
    (`downloads_view`), with no Verified revenue and no "Counted, not
    verified".
    """
    analysis = downloads_view(analysis)
    if is_document_payload(analysis):
        surface = "webapp/app.py::_analysis_rows"
        rows: list[tuple[str, str, object]] = []
        for key, item in payload_document_block(analysis, surface=surface).items():
            if isinstance(item, (dict, list)):
                item = json.dumps(item)
            rows.append(("document", key, "" if item is None else item))
        for index, account in enumerate(
            payload_accounts(analysis, surface=surface), start=1
        ):
            rows.extend(
                (f"account_{index}.{section}", field, value)
                for section, field, value in _account_analysis_rows(account)
            )
        return rows
    return _account_analysis_rows(analysis)


def _account_analysis_rows(analysis: dict) -> list[tuple[str, str, object]]:
    """One ACCOUNT's rows — today's sheet, unchanged."""
    rows: list[tuple[str, str, object]] = []
    for section in ("statement", "metrics", "quality", "integrity", "reconciliation"):
        value = analysis.get(section)
        if isinstance(value, dict):
            for key, item in value.items():
                if (section, key) in _EXPORT_SUPPRESSED_KEYS:
                    continue
                # A printed title is written only where it reads as a bank's account designation; an owner's name or a
                # legal-form fragment read as the title is left out of the flat sheet (the JSON download and the served
                # payload keep it as read).
                if section == "statement" and key == "account_title" and not _designation_title(item):
                    continue
                if section == "metrics" and key in ("adb", *TIER_REASON_KEYS, ZELLE_DEPOSITS_KEY,
                                                    LARGE_UNSOURCED_DEPOSITS_KEY):
                    continue  # emitted as their own sections below
                if isinstance(item, (dict, list)):
                    item = json.dumps(item)
                rows.append((section, key, "" if item is None else item))
    metrics = analysis.get("metrics")
    if isinstance(metrics, dict):
        rows.extend(_adb_rows(metrics))
        rows.extend(tier_reason_rows(metrics))
        rows.extend(zelle_deposit_rows(metrics.get(ZELLE_DEPOSITS_KEY)))
        # §10.8: one section per large unsourced deposit the served copy flags (its count and total are metric rows
        # above); nothing where none is flagged.
        rows.extend(large_unsourced_deposit_rows(metrics.get(LARGE_UNSOURCED_DEPOSITS_KEY)))
    detection = analysis.get("detection")
    if isinstance(detection, dict):
        for key, item in detection.items():
            if key in ("flagged_positions", "lender_payment_changes"):
                continue  # emitted as readable rows below
            if isinstance(item, (dict, list)):
                item = json.dumps(item)
            rows.append(("detection", key, "" if item is None else item))
        rows.extend(_flagged_position_rows(detection.get("flagged_positions")))
        rows.extend(lender_payment_change_rows(detection.get("lender_payment_changes")))
    return rows


#: True revenue spec §10.8: the fields of a `lender_payment_change_<n>` section, in order; a field the item does not
#: carry is an empty cell. `first_after_kind`, `resumed_date` (a pause) and `last_step_percent` (a change through
#: unreported levels) describe the change; a pause's catch-up (`first_after_amount`, `first_after_multiple`) and its
#: debits of 2x or more inside the gap (`larger_debits_inside`, "2054-03-16 1300.0;..."); a Caught up item's fields
#: (`missed_payments` to `catch_up_amount`); a pause's catch-ups after the presence that ended it, before payments
#: resumed (`catch_ups_inside`, "2054-03-17 1700.0 2x; ...").
LENDER_PAYMENT_CHANGE_EXPORT_FIELDS = (
    "kind", "lender", "lender_label", "lender_label_after", "lender_state", "position", "positions",
    "cadence", "cadence_before", "cadence_after", "amount_before", "amount_after", "change_percent", "cadence_changed",
    "schedule_confirmed", "weekly_equivalent_before", "weekly_equivalent_after", "payments_before", "payments_after",
    "last_before_date", "first_after_date", "last_after_date", "first_after_kind", "resumed_date",
    "first_after_amount", "first_after_multiple", "larger_debits_inside", "catch_ups_inside", "restart",
    "pause_business_days", "back_to_earlier", "reverted", "reverted_date", "via", "last_step_percent",
    "weekly_total_before", "weekly_total_after", "alongside",
    "last_payment_date", "last_payment_amount", "payments", "last_presence_date", "quiet_business_days",
    "grace_business_days", "coverage_end", "coverage_end_source", "stop_confirmed",
    "missed_payments", "missed_first_date", "missed_last_date", "multiple", "catch_up_date", "catch_up_amount",
)
#: The nested notes, flattened with dots. A stop's `other_debits_after.catch_ups` and `payoff.earlier`, and a pause's
#: or a stop's `same_amount_debits`.
LENDER_PAYMENT_CHANGE_NOTE_FIELDS = (
    ("after_funding", ("date", "amount")),
    ("other_debits_after", ("count", "last_date", "catch_ups")),
    ("payoff", ("date", "amount", "earlier")),
    ("same_amount_debits", ("count", "first_date", "last_date")),
    ("continues_as", ("lender_label", "amount", "first_date")),
    ("new_lender_after", ("lender_label", "cadence", "amount", "first_date")),
    ("debt_relief_after", ("date",)),
    ("other_stream_continues", ("amount", "cadence")),
    ("last_attempt_returned", ("date",)),
)
#: The package's added fields.
LENDER_PAYMENT_CHANGE_PACKAGE_FIELDS = (
    "source_document", "from_document", "to_document", "cross_statement", "source_currency", "source_period_end",
)


def lender_payment_change_rows(items: object, *, package: bool = False) -> list[tuple[str, str, object]]:
    """One readable section per lender payment change, `lender_payment_change_<n>`, with
    LENDER_PAYMENT_CHANGE_EXPORT_FIELDS and the dotted notes (a package adds its source fields and the other-account
    note). A label is statement text: these rows reach a file only through `escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    for number, item in enumerate((entry for entry in items if isinstance(entry, dict))
                                  if isinstance(items, list) else (), start=1):
        section = f"lender_payment_change_{number}"
        for name in LENDER_PAYMENT_CHANGE_EXPORT_FIELDS:
            value = item.get(name)
            if name in ("alongside", "via") and isinstance(value, list):
                # A via level carries the step into it: "weekly 950.0 (-5%)".
                value = "; ".join(f"{entry.get('cadence')} {entry.get('amount')}"
                                  + (f" ({entry['change_percent']:+d}%)" if name == "via"
                                     and isinstance(entry.get("change_percent"), int) else "")
                                  for entry in value if isinstance(entry, dict))
            elif name == "larger_debits_inside" and isinstance(value, list):
                # "2054-03-16 1300.0; ...".
                value = "; ".join(f"{entry.get('date')} {entry.get('amount')}" for entry in value
                                  if isinstance(entry, dict))
            elif name == "catch_ups_inside" and isinstance(value, list):
                # "2054-03-17 1700.0 2x; ...".
                value = "; ".join(f"{entry.get('date')} {entry.get('amount')} {entry.get('multiple')}x"
                                  for entry in value if isinstance(entry, dict))
            rows.append((section, name, "" if value is None else value))
        # The package's reappearance note beside the continuation.
        notes = LENDER_PAYMENT_CHANGE_NOTE_FIELDS + ((
            ("continues_in_other_account", ("source_document", "first_date", "amount")),
            ("reappears_in_other_account", ("source_document", "first_date", "amount", "covered_business_days")),
        ) if package else ())
        for note, fields in notes:
            value = item.get(note)
            for name in fields:
                cell = value.get(name) if isinstance(value, dict) else None
                rows.append((section, f"{note}.{name}", "" if cell is None else cell))
        if package:
            for name in LENDER_PAYMENT_CHANGE_PACKAGE_FIELDS:
                value = item.get(name)
                rows.append((section, name, "" if value is None else value))
    return rows


def tier_reason_rows(figures: dict, section: str = "revenue_tier") -> list[tuple[str, str, object]]:
    """One row per tier, reason and figure: `(revenue_tier, <tier>.<reason>.count | .total, value)`. A reason code
    is a constant of analysis/revenue.py; the rows still reach a file only through `escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    for key in TIER_REASON_KEYS:
        reasons = figures.get(key)
        tier = key[: -len("_by_reason")]
        for reason, slot in (reasons.items() if isinstance(reasons, dict) else ()):
            for field in ("count", "total"):
                value = slot.get(field) if isinstance(slot, dict) else None
                rows.append((section, f"{tier}.{reason}.{field}", "" if value is None else value))
    return rows


def zelle_deposit_rows(
    figures: object, section: str = "revenue_tier", *, setting: bool | None = None,
) -> list[tuple[str, str, object]]:
    """Spec §10.8: the served Zelle figures (`zelle_deposits`, analysis/zelle_view.py) as readable rows of the
    revenue_tier section, only where the key is present: `zelle_deposits.setting` (Yes or No), `.count`, `.total`,
    `.<tier>.count`, `.<tier>.total` and `.setting_applied`. A money figure the package refuses is an empty cell.
    `setting` is the choice the figures were served under; an account's figures say it themselves (Yes exactly when
    the reading served is the one the setting asked for and counts, or is not and does not: `counted_as_true_revenue`
    equals `setting_applied`)."""
    if not isinstance(figures, dict):
        return []
    if setting is None:
        setting = figures.get("counted_as_true_revenue") is (figures.get("setting_applied") is not False)
    rows: list[tuple[str, str, object]] = [(section, "zelle_deposits.setting", "Yes" if setting else "No")]
    for field in ("count", "total"):
        value = figures.get(field)
        rows.append((section, f"zelle_deposits.{field}", "" if value is None else value))
    by_tier = figures.get("by_tier")
    for tier, slot in (by_tier.items() if isinstance(by_tier, dict) else ()):
        for field in ("count", "total"):
            value = slot.get(field) if isinstance(slot, dict) else None
            rows.append((section, f"zelle_deposits.{tier}.{field}", "" if value is None else value))
    rows.append((section, "zelle_deposits.setting_applied", figures.get("setting_applied") is not False))
    return rows


_LARGE_UNSOURCED_DEPOSIT_EXPORT_FIELDS = tuple(
    field for field in LARGE_UNSOURCED_DEPOSIT_FIELDS if field != "revenue_tier_reason")
PACKAGE_LARGE_UNSOURCED_DEPOSIT_FIELDS = (
    *_LARGE_UNSOURCED_DEPOSIT_EXPORT_FIELDS, "source_job", "source_document", "source_account", "source_currency",
)


def large_unsourced_deposit_rows(
    items: object, fields: tuple[str, ...] = _LARGE_UNSOURCED_DEPOSIT_EXPORT_FIELDS,
) -> list[tuple[str, str, object]]:
    """§10.8: one readable section per flagged credit, `large_unsourced_deposit_<n>`, in served order, its `fields` (an
    empty cell where the item has none). A description is statement text: these rows reach a file only through
    `escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    entries = [entry for entry in items if isinstance(entry, dict)] if isinstance(items, list) else []
    for number, item in enumerate(entries, start=1):
        for field in fields:
            value = item.get(field)
            rows.append((f"large_unsourced_deposit_{number}", field, "" if value is None else value))
    return rows


def _flagged_position_rows(positions: object) -> list[tuple[str, str, object]]:
    """An account's flagged positions, one readable section per payee (lender detection §8.4):
    `flagged_<group>_<n>` with the payee, its debit count, the total debited, the credits it paid in and their
    total, the cadence, and (5.3) whether the payee is unconfirmed (`review_required`).

    Served payloads hold only the ticked groups (analysis/flagged_view.py via `displayed`), so the sheet follows
    Settings. A payee name is statement text: these rows reach a file only through `escaped_rows`."""
    rows: list[tuple[str, str, object]] = []
    numbers: dict[str, int] = {}
    for entry in positions if isinstance(positions, list) else []:
        group = entry.get("group") if isinstance(entry, dict) else None
        if not isinstance(group, str) or group not in FLAG_GROUP_BY_KEY:
            continue
        numbers[group] = numbers.get(group, 0) + 1
        for field in ("payee", "count", "total_debited", "count_credited", "total_credited", "cadence",
                      "review_required"):
            value = entry.get(field)
            rows.append((f"flagged_{group}_{numbers[group]}", field, "" if value is None else value))
    return rows


#: The columns of the statement downloads' posted-credit table. True revenue spec §2.2, §10.8: no `state` column
#: (the 5.4 state, `verified_revenue` or `unverified_deposit`).
_POSTED_CREDIT_COLUMNS = ("date", "description", "amount", "currency", "tier", "reason", "review_status")


def tier_cell(record: dict) -> str:
    """A ledger row's `tier` cell, from a record as the downloads read it (`downloads_view`): its tier, or for a
    credit analysed before 5.6, which has none, its state in the page's words (`revenue`, `review_required` or
    `non_revenue`, as its tag reads); empty for a row with neither."""
    return record.get("revenue_tier") or record.get("revenue_classification") or ""


def _posted_credit_table(analysis: dict) -> list[tuple]:
    """One row per posted credit, so an underwriter can check, deposit by deposit, which credits make up True (the
    ledger otherwise sits in one JSON cell, over a spreadsheet's cell limit on most statements): a `columns` row, then
    `(section, n, date, description, amount, currency, tier, reason, review status)`. The tier and reason are the
    payload's codes (analysis/revenue.py), as the downloads read them (`downloads_view`: a credit in True revenue is
    `true_revenue`, with no reason; `tier_cell` before 5.6). Every account of a document payload has its own block,
    under its section prefix. A block written after the flat rows (`_analysis_rows` stays three columns for its
    readers); its statement text reaches a file only through `escaped_rows`."""
    analysis = downloads_view(analysis)
    if is_document_payload(analysis):
        accounts = payload_accounts(analysis, surface="webapp/app.py::_posted_credit_table")
        return [
            (f"account_{index}.{row[0]}", *row[1:])
            for index, account in enumerate(accounts, start=1)
            for row in _posted_credit_table(account)
        ]
    statement = analysis.get("statement") if isinstance(analysis, dict) else None
    if not isinstance(statement, dict):
        return []
    currency = statement_currency(analysis) or ""
    rows: list[tuple] = []
    tagged: list[bool] = []
    for transaction in statement.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        amount = num(transaction.get("amount"))
        record = transaction.get("classification") if isinstance(transaction.get("classification"), dict) else {}
        if amount <= 0 or record.get("is_posted") is False:
            continue
        rows.append(("posted_credit", len(rows) + 1, transaction.get("date") or "",
                     transaction.get("description") or "", amount, currency, tier_cell(record),
                     record.get("revenue_tier_reason") or "", record.get("revenue_review_status") or ""))
        tagged.append(transaction.get(ZELLE_ROW_TAG) is True)
    if not rows:
        return []
    # A trailing `zelle` column, only in a block where a row carries the served Zelle tag (Yes), 'Zelle' on those rows;
    # every other block is today's.
    if any(tagged):
        return [("posted_credit", "columns", *_POSTED_CREDIT_COLUMNS, "zelle"),
                *((*row, "Zelle" if zelle else "") for row, zelle in zip(rows, tagged))]
    return [("posted_credit", "columns", *_POSTED_CREDIT_COLUMNS), *rows]


#: The columns of the statement downloads' posted-debit table; the last, a confirmed funder's payment the bank
#: returned unpaid (the location of the credit that returned it, the record's `returned_funder_payment_by`).
_POSTED_DEBIT_COLUMNS = (
    "date", "description", "amount", "currency", "classification", "flagged_group", "canonical_entity",
    "review_required", "returned_funder_payment",
)


def _posted_debit_table(analysis: dict) -> list[tuple]:
    """One row per posted debit, the posted-credit table's twin, so the lender payments, the withholding and the NSFs
    read row by row (the ledger otherwise sits only in one JSON cell, over a spreadsheet's cell limit on most
    statements): a `columns` row, then `(posted_debit, n, date, description, amount (signed), currency, classification,
    flagged group, entity, review required, returned funder payment)`. The flag group is written only where Settings
    shows it (`flag_shown`, analysis/flagged_view.py), so an unticked group never leaks; the other fields are the
    record's as served (the last, `returned_funder_payment_by`: where a confirmed funder's payment came back
    unpaid, the location of the credit that returned it). Every account of a document payload has its own block, under
    its section prefix. Written after the credit table; its statement text reaches a file only through `escaped_rows`."""
    if is_document_payload(analysis):
        accounts = payload_accounts(analysis, surface="webapp/app.py::_posted_debit_table")
        return [
            (f"account_{index}.{row[0]}", *row[1:])
            for index, account in enumerate(accounts, start=1)
            for row in _posted_debit_table(account)
        ]
    statement = analysis.get("statement") if isinstance(analysis, dict) else None
    if not isinstance(statement, dict):
        return []
    currency = statement_currency(analysis) or ""
    rows: list[tuple] = []
    for transaction in statement.get("transactions") or []:
        if not isinstance(transaction, dict):
            continue
        amount = num(transaction.get("amount"))
        record = transaction.get("classification") if isinstance(transaction.get("classification"), dict) else {}
        if amount >= 0 or record.get("is_posted") is False:
            continue
        review = record.get("review_required")
        rows.append(("posted_debit", len(rows) + 1, transaction.get("date") or "",
                     transaction.get("description") or "", amount, currency, record.get("classification") or "",
                     (record.get("flagged_group") or "") if record.get("flag_shown") is True else "",
                     record.get("canonical_entity") or "", review if isinstance(review, bool) else "",
                     record.get("returned_funder_payment_by") or ""))
    if not rows:
        return []
    return [("posted_debit", "columns", *_POSTED_DEBIT_COLUMNS), *rows]


def analysis_csv(analysis: dict) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["section", "field", "value"])
    writer.writerows(escaped_rows(
        _analysis_rows(analysis) + _posted_credit_table(analysis) + _posted_debit_table(analysis)
    ))
    return buf.getvalue()


def analysis_xlsx(analysis: dict) -> bytes:
    return rows_xlsx(_analysis_rows(analysis) + _posted_credit_table(analysis) + _posted_debit_table(analysis))
