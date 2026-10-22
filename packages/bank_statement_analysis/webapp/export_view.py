"""A served payload on its way out of the web app: account numbers masked (every route), a package without its
dashboard-only fields (the package downloads), and the copy the CSV and XLSX downloads read, which names no
hidden revenue tier (`downloads_view`)."""
from __future__ import annotations

import re

from analysis.package.model import is_count, is_money_value
from analysis.revenue import REVENUE_TIER_REASONS
from analysis.revenue_view import UNESTABLISHED_WITHHOLDING_BASIS_KEYS, WITHHOLDING_BASIS_UNESTABLISHED


# Every payload key that carries the account number as printed. `account` is
# what the transaction classifier stamps onto each classification record;
# `account_number` is the statement field and the package document column.
_ACCOUNT_KEYS = frozenset({"account", "account_number"})


def _mask_account(value: object) -> str | None:
    """Last four digits only — `****1234`. Applied at the webapp boundary and
    nowhere else: `analysis/serialization.py` keeps emitting the number as
    printed, because the CLI and the forensic oracles reconcile against it."""
    if value is None:
        return None
    text = str(value)
    if not text.strip():
        return None
    digits = "".join(character for character in text if character.isdigit())
    return "****" + digits[-4:]


#: What a package and its member rows carry for the dashboard alone, left out of the package downloads (the
#: re-analyze note's flag, S6 review, reads off the served copies and names no figure).
_PACKAGE_DISPLAY_ONLY_KEYS = ("nsf_days", "analysis_rules_outdated")


def package_for_export(package: dict) -> dict:
    """A copy of a package payload without the fields only the dashboard reads: from the package itself and from
    its member rows, which it lists twice (`documents`, and `monthly` for the members with a period)."""
    exported = {key: value for key, value in package.items() if key not in _PACKAGE_DISPLAY_ONLY_KEYS}
    for section in ("documents", "monthly"):
        rows = package.get(section)
        if isinstance(rows, list):
            exported[section] = [
                _export_document_revenue(
                    {key: value for key, value in row.items() if key not in _PACKAGE_DISPLAY_ONLY_KEYS}
                ) if isinstance(row, dict) else row
                for row in rows
            ]
    # The package's counted-plus-held figures, and the held count, are partial when a member's revenue is not
    # established (its True, Counted and Held totals are already None, §10.4), so a download leaves them empty too.
    # So does a package that analyses no statement (R54: its True, Verified, Counted and Held are already None),
    # whose revenue counts are left empty too, never the 0.0 or 0 an underwriter would read as a measured decline.
    # The served totals keep them: the dashboard's review badge reads its null True count as N/A, and would read a
    # null held count as a payload analysed before 5.6.
    totals = package.get("totals")
    no_analysis = isinstance(totals, dict) and totals.get("completed") == 0
    if isinstance(totals, dict) and (totals.get("revenue_unestablished_documents") or no_analysis):
        emptied = (*_PACKAGE_PARTIAL_REVENUE_KEYS, *(_PACKAGE_NO_ANALYSIS_COUNT_KEYS if no_analysis else ()))
        totals = exported["totals"] = {**totals, **{key: None for key in emptied if key in totals}}
    # §10.4, §11: the withholding basis summed over a member whose basis is not established is an empty cell, as
    # the dashboard reads it N/A. So is the sum of members analysed under different bases, which is no basis at
    # all.
    if isinstance(totals, dict) and (totals.get(WITHHOLDING_BASIS_UNESTABLISHED) is True
                                     or totals.get("withholding_basis_mixed") is True):
        exported["totals"] = {
            **totals, **{key: None for key in UNESTABLISHED_WITHHOLDING_BASIS_KEYS if key in totals},
        }
    return exported


#: The package totals built from every member's counted and held credits, and the held count.
_PACKAGE_PARTIAL_REVENUE_KEYS = ("maximum_revenue", "potential_revenue_total", "unverified_deposit_total",
                                 "revenue_review_items")
#: The package's revenue counts, which a download also leaves empty when the package analyses no statement
#: (`completed` 0: every job failed, was interrupted, is still on its way or holds no analysis, or every account was
#: left out), beside R54's empty True, Verified, Counted and Held.
_PACKAGE_NO_ANALYSIS_COUNT_KEYS = ("unverified_deposit_count", "potential_revenue_count", "verified_revenue_count",
                                   "confirmed_true_revenue_count")


def _export_document_revenue(row: dict) -> dict:
    """A member's row as the package downloads print it: its Verified figure (and the alias of it) empty unless
    established, and its counted-plus-held figures empty unless its revenue is. A left-out repeat's row carries no
    figure and is unchanged."""
    if row.get("is_duplicate") is True:
        return row
    nulled = {}
    if row.get("verified_revenue_established") is False:
        nulled.update({key: None for key in ("verified_revenue_total", "confirmed_true_revenue_total") if key in row})
    if row.get("revenue_established") is False:
        nulled.update({key: None for key in ("unverified_deposit_total", "potential_revenue_total", "maximum_revenue")
                       if key in row})
    # §10.4, §11: a member whose withholding basis is not established prints no basis.
    if row.get(WITHHOLDING_BASIS_UNESTABLISHED) is True:
        nulled.update({key: None for key in UNESTABLISHED_WITHHOLDING_BASIS_KEYS if key in row})
    return {**row, **nulled} if nulled else row


def masked(payload: object) -> object:
    """A masked copy of a served payload. Copies rather than mutates — the job
    store holds the analyst's authoritative record and must not be rewritten by
    the act of serving it."""
    if isinstance(payload, dict):
        return {
            key: _mask_account(value)
            if key in _ACCOUNT_KEYS and not isinstance(value, (dict, list))
            else masked(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [masked(item) for item in payload]
    return payload


#: True revenue spec §9.1, §9.2: the served list of large unsourced deposits (a statement's metrics key, a package's
#: top-level key).
LARGE_UNSOURCED_DEPOSITS_KEY = "large_unsourced_deposits"


#: True revenue spec §2.2, §10.8: "Can you get rid of verified revenue from the fronted end please and "counted, not
#: verified" still keep them in the backend but don't show it", the CSV and Excel downloads included ("Hide them there
#: too"). These downloads name no Verified revenue and no "Counted, not verified" (the tiers `verified` and
#: `counted_flagged`) as things of their own: True revenue, their sum, Held for review and Non-revenue stay, and no
#: figure moves. The served payload, the JSON download, the CLI and every stored analysis keep both tiers: only the CSV
#: and XLSX row builders (`_analysis_rows`, `_posted_credit_table`, `_package_rows` and `_package_transaction_table`)
#: read a payload through `downloads_view`, so every CSV and XLSX download does.
_HIDDEN_TIERS = frozenset({"verified", "counted_flagged"})
#: The tier a credit of a hidden tier is written as: True revenue, of which each is a part.
_TRUE_REVENUE_TIER = "true_revenue"
#: Every key that names a hidden tier, its figures or an alias of them, left out wherever it sits: `verified_revenue_*`
#: (with `avg_monthly_verified_revenue` and the records' `contributes_to_verified_revenue`), `counted_flagged_*`,
#: `unverified_deposit_*` (5.4's name for counted plus held), `potential_revenue*` and `confirmed_true_revenue*` (the
#: aliases of those two) and the Zelle figures' `verified` and `counted_flagged` slots (merged first, below). A payload
#: analysed before 5.6 has no tier: its 5.4 lists and its deposits to review are renamed first (`_OLDER_KEY_WORDS`).
_HIDDEN_TIER_KEY = re.compile(r"verified|counted_flagged|potential_revenue|confirmed_true_revenue")
#: A classification record's 5.4 state (`verified_revenue`, `unverified_deposit` or `non_revenue`), current and initial.
#: On a credit with a tier (5.6 on), the tier says what the state says without the verified and counted split, so the
#: state is left out unless it is `non_revenue`; on a credit analysed before 5.6 (no tier) the state is its only revenue
#: reading and is written in the page's words (`_OLDER_STATE_WORDS`).
_STATE_KEYS = frozenset({"revenue_classification", "revenue_initial_classification"})
#: The page's words for a pre-5.6 credit's state, as its tag reads (app.js transactionCategory: "Revenue", "Review
#: required", "Non-revenue"): never 5.4's `verified_revenue` or `unverified_deposit`.
_OLDER_STATE_WORDS = {
    "verified_revenue": "revenue", "unverified_deposit": "review_required", "non_revenue": "non_revenue",
}
#: A pre-5.6 account's revenue view (`_older_revenue_view`) writes its 5.4 lists under the page's words, and its
#: deposits to review (what its review view lists and its badge counts) with their count and total. A 5.6 view's
#: `unverified_deposit_*` is counted plus held, an alias of a hidden tier, and is left out.
_OLDER_KEY_WORDS = {
    "verified_revenue_evidence": "revenue_evidence",
    "unverified_deposit_evidence": "review_required_evidence",
    "unverified_deposit_count": "review_required_count",
    "unverified_deposit_total": "review_required_total",
}
#: A record's rule and its sentence (`revenue_matched_rule`, `revenue_reason`): why the rules read it as they did. A
#: credit in True revenue carries neither (a counted one's says the source is not confirmed); a held or non-revenue
#: one keeps both, the words naming a hidden tier rewritten (`_SENTENCE_REWRITES`, `_ZELLE_READING`), and a rule or
#: sentence that still names one after that is left out.
_RULE_KEYS = frozenset({"revenue_matched_rule", "revenue_reason"})
_HIDDEN_TIER_WORDS = re.compile(r"verified|counted and flagged|counted_flagged|counted, not verified", re.IGNORECASE)
#: The rewrites of a held or non-revenue sentence, in order: the hold of a counted re-statement ("never verified,
#: and held for review (<label>)"), the $1 floor's hold of a verified credit ("is never verified and never counted") and
#: the holder's own push a rule verified ("never revenue and never verified;").
_SENTENCE_REWRITES = (
    ("never verified, and held for review (", "held for review ("),
    ("is never verified and never counted", "is never counted in True revenue"),
    (" and never verified;", ";"),
)
#: Q3's sentence on a Zelle deposit the policy excluded ends on the rules' reading (analysis/true_revenue.py
#: `_zelle_excluded`): "...; the rules read it as: <label>." A reading in a hidden tier ("Verified revenue", a counted
#: reason's label) is written "True revenue.", as the page says it (app.js zellePriorSentence); a held one keeps its
#: label.
_ZELLE_READING = "the rules read it as: "
#: The counted tier's reason codes (analysis/revenue.py REVENUE_TIER_REASONS), left out wherever a record carries one:
#: on a credit counted in True revenue, on one a reviewer confirmed and on one a reviewer rejected (which keeps it).
_COUNTED_REASONS = frozenset(code for code, (tier, _label) in REVENUE_TIER_REASONS.items() if tier == "counted_flagged")
#: The lender classifier's sentence on a row no lender, insurance or category rule read (most credits,
#: analysis/transaction_classifier.py), whose "verified" is a lender's, never a revenue tier, written without the word.
_UNMATCHED_ROW_REASONS = {
    "No verified lender, insurance, or operational-category rule matched.":
        "No lender, insurance, or operational-category rule matched.",
}
#: The verified withholding basis (WITHHOLDING_DENOMINATOR_MODE=verified_revenue; never chosen on screen), as the page
#: names it (app.js WITHHOLDING_BASIS_LABELS): its mode (`narrower_revenue_basis`, a downloads-only code naming no tier;
#: the backend's mode stays `verified_revenue`), its label and its definition, and in a note's sentence, in lower case
#: as the page's rate note names it; the True basis's definition in the page's words. Its figures are unchanged.
_NARROWER_BASIS_MODE = "narrower_revenue_basis"
_NARROWER_BASIS_LABEL = "Narrower revenue basis"
_NARROWER_BASIS_IN_A_NOTE = "the narrower revenue basis"
_BASIS_DEFINITIONS = {
    "verified_revenue": "a part of true revenue only",
    "true_revenue": "true revenue: posted credits minus known non-revenue and the deposits held for review",
}
#: The context signal that keeps a Zelle deposit's reading with Zelle counted (analysis/true_revenue.py `_ZELLE_PRIOR`).
_ZELLE_PRIOR = "zelle_prior:"


def _true_revenue_slot(slots: list) -> dict | None:
    """The Zelle figures' slot of True revenue: the `verified` and `counted_flagged` slots (`{count, total}`) added up, a
    count or a total empty (None) where a slot's is, as an unestablished or refused part is. None where neither is."""
    present = [slot for slot in slots if isinstance(slot, dict)]
    if not present:
        return None
    counts = [slot.get("count") for slot in present]
    totals = [slot.get("total") for slot in present]
    return {
        "count": sum(counts) if all(is_count(count) for count in counts) else None,
        "total": round(sum(totals), 2) if all(is_money_value(total) for total in totals) else None,
    }


def _zelle_by_tier_without_hidden_tiers(by_tier: dict) -> dict:
    """`zelle_deposits.by_tier` as the downloads read it: the `verified` and `counted_flagged` slots as one
    `true_revenue` slot, first, then the held and non-revenue slots as served."""
    slot = _true_revenue_slot([by_tier.get(tier) for tier in ("verified", "counted_flagged")])
    rest = {tier: value for tier, value in by_tier.items() if tier not in _HIDDEN_TIERS}
    return {_TRUE_REVENUE_TIER: slot, **rest} if slot is not None else rest


def _context_signals_without_hidden_tiers(signals: object) -> object:
    """A record's `revenue_context_signals` as the downloads read them: a Zelle deposit's prior reading in a hidden tier
    (`zelle_prior:verified`, `zelle_prior:counted_flagged:<reason>`) is `zelle_prior:true_revenue`, and any other signal
    naming a hidden tier is left out."""
    if not isinstance(signals, (list, tuple)):
        return signals
    kept = []
    for signal in signals:
        if isinstance(signal, str) and signal.startswith(_ZELLE_PRIOR):
            tier = signal[len(_ZELLE_PRIOR):].split(":", 1)[0]
            if tier in _HIDDEN_TIERS:
                signal = f"{_ZELLE_PRIOR}{_TRUE_REVENUE_TIER}"
        elif isinstance(signal, str) and _HIDDEN_TIER_KEY.search(signal):
            continue
        kept.append(signal)
    return tuple(kept) if isinstance(signals, tuple) else kept


def _older_revenue_view(node: dict) -> bool:
    """Whether `node` is an account's revenue view (its metrics or detection) analysed before 5.6: it lists 5.4's
    unverified deposits and no held tier (5.6's `excluded_pending_review_evidence` is a list; before it, None or
    absent). A package's lists always carry the held tier, so a package is never read as one."""
    return "unverified_deposit_evidence" in node and not isinstance(node.get("excluded_pending_review_evidence"), list)


def _zelle_prior_tier(signals: object) -> str | None:
    """The tier the rules gave a Zelle deposit the policy excluded (its `zelle_prior:<tier>:<reason>` signal), or
    None."""
    for signal in signals if isinstance(signals, (list, tuple)) else ():
        if isinstance(signal, str) and signal.startswith(_ZELLE_PRIOR):
            return signal[len(_ZELLE_PRIOR):].split(":", 1)[0]
    return None


def _reason_without_hidden_tiers(key: str, value: object, record: dict) -> object:
    """A held or non-revenue record's rule or sentence as the downloads write it: the sentence with the words that name
    a hidden tier rewritten (`_SENTENCE_REWRITES`; a Zelle deposit's reading in a hidden tier as "True revenue."), and
    None (left out) where the rule or the rewritten sentence still names one."""
    if not isinstance(value, str):
        return value
    if key == "revenue_reason":
        for old, new in _SENTENCE_REWRITES:
            value = value.replace(old, new)
        reading = value.rfind(_ZELLE_READING)
        if reading >= 0 and _zelle_prior_tier(record.get("revenue_context_signals")) in _HIDDEN_TIERS:
            value = f"{value[:reading + len(_ZELLE_READING)]}True revenue."
    return None if _HIDDEN_TIER_WORDS.search(value) else value


def posted_row_key(job: object, account: object, location: object) -> tuple:
    """A posted row's key, `(statement job, account, location)`, as app.js `debitFlagKey` keys a large
    unsourced deposit, a record and a package ledger row. A statement's items and records name neither job nor account
    (they sit under the account that lists them); a package's name both, its account absent (None) for a one-account
    member."""
    return (job or None, account, location)


def large_deposit_keys(node: dict) -> frozenset | None:
    """The keys (`posted_row_key`) of the large unsourced deposits that `node` serves: a statement account's, in its
    `metrics`, or a package's, at its top level beside its combined ledger; None where `node` is neither."""
    metrics = node.get("metrics")
    if isinstance(metrics, dict):
        items = metrics.get(LARGE_UNSOURCED_DEPOSITS_KEY)
    elif isinstance(node.get("transactions"), list) and "totals" in node:
        items = node.get(LARGE_UNSOURCED_DEPOSITS_KEY)
    else:
        return None
    return frozenset(
        posted_row_key(item.get("source_job"), item.get("source_account"), item.get("source_location"))
        for item in (items if isinstance(items, (list, tuple)) else ()) if isinstance(item, dict))


def downloads_view(node: object, *, flagged: frozenset = frozenset(), scope: tuple = (None, None)) -> object:
    """A served payload (statement, document or package), or any part of it, as the CSV and XLSX downloads write it: a
    copy in which no key names a hidden tier (`_HIDDEN_TIER_KEY`), a classification record's hidden tier reads
    `true_revenue` (current and initial, and a package pass's `tier_before`), its counted reason is left out, its 5.4
    state is left out (a tier says it) or, before 5.6, written in the page's words (`_STATE_KEYS`), its rule and sentence
    are kept only out of True revenue, and without a hidden tier's words (`_RULE_KEYS`), a counted credit awaits no
    review unless it is a large deposit to source, a pre-5.6 view's lists are renamed (`_OLDER_KEY_WORDS`), the Zelle
    figures carry one True revenue slot, and the verified withholding basis reads as the page names it. Every figure is
    unchanged; the input is never mutated.

    A counted credit the payload flags as a large deposit to source keeps `pending`, as its row on the page keeps
    Confirm Revenue. `flagged` holds the flagged credits' keys (`large_deposit_keys`, read from a statement account or
    a package as the walk reaches it, or passed in for a part of one) and `scope` the statement job and account the
    walk is under (a package row or record names its own)."""
    if isinstance(node, (list, tuple)):
        items = [downloads_view(item, flagged=flagged, scope=scope) for item in node]
        return tuple(items) if isinstance(node, tuple) else items
    if not isinstance(node, dict):
        return node
    served_flags = large_deposit_keys(node)
    if served_flags is not None:
        flagged, scope = served_flags, (None, None)
    if node.get("source_job"):
        scope = (node["source_job"], node.get("source_account"))
    record = "revenue_classification" in node
    tiered = isinstance(node.get("revenue_tier"), str)
    older = _older_revenue_view(node)
    out: dict = {}
    for key, value in node.items():
        if older and key in _OLDER_KEY_WORDS:
            out[_OLDER_KEY_WORDS[key]] = downloads_view(value, flagged=flagged, scope=scope)
            continue
        if key == "by_tier" and isinstance(value, dict):
            value = _zelle_by_tier_without_hidden_tiers(value)
        if record and key in _STATE_KEYS:
            if not tiered:
                out[key] = _OLDER_STATE_WORDS.get(value, value)
            elif value == "non_revenue":
                out[key] = value
            continue
        if record and key in _RULE_KEYS:
            if node.get("revenue_tier") in _HIDDEN_TIERS:
                continue
            if value is not None:
                value = _reason_without_hidden_tiers(key, value, node)
                if value is None:
                    continue
            out[key] = value
            continue
        if _HIDDEN_TIER_KEY.search(str(key)):
            continue
        if key in ("revenue_tier", "revenue_initial_tier", "tier_before") and value in _HIDDEN_TIERS:
            value = _TRUE_REVENUE_TIER
        elif key in ("revenue_tier_reason", "reason_before") and value in _COUNTED_REASONS:
            value = None
        elif (key == "revenue_review_status" and value == "pending" and node.get("revenue_tier") == "counted_flagged"
              and posted_row_key(*scope, node.get("source_location")) not in flagged):
            # A counted credit is in True revenue; the page offers it no review a verified one lacks, unless it is a
            # large deposit to source, whose row keeps Confirm Revenue.
            value = "not_required"
        elif key == "reason" and value in _UNMATCHED_ROW_REASONS:
            value = _UNMATCHED_ROW_REASONS[value]
        elif key == "revenue_context_signals":
            value = _context_signals_without_hidden_tiers(value)
        elif key in ("withholding_denominator_mode", "mode") and value == "verified_revenue":
            value = _NARROWER_BASIS_MODE
        elif key in ("withholding_denominator_label", "label") and value == "Verified revenue":
            value = _NARROWER_BASIS_LABEL
        elif key == "eligible_deposit_definition" and node.get("withholding_denominator_mode") in _BASIS_DEFINITIONS:
            value = _BASIS_DEFINITIONS[node["withholding_denominator_mode"]]
        elif key == "withholding_denominator_options" and isinstance(value, (list, tuple)):
            # Nothing on screen offers the verified basis, so it is no option, except on a statement analysed on it,
            # whose options list its own mode as the downloads name it.
            own = node.get("withholding_denominator_mode") == "verified_revenue"
            modes = [_NARROWER_BASIS_MODE if mode == "verified_revenue" else mode for mode in value
                     if mode != "verified_revenue" or own]
            value = tuple(modes) if isinstance(value, tuple) else modes
        elif key == "notes" and isinstance(value, (list, tuple)):
            # A withholding note names its basis by its label mid-sentence ("... because Verified revenue is zero or
            # missing"), so the narrower basis is named there in lower case.
            notes = [note.replace("Verified revenue", _NARROWER_BASIS_IN_A_NOTE) if isinstance(note, str) else note
                     for note in value]
            value = tuple(notes) if isinstance(value, tuple) else notes
        else:
            value = downloads_view(value, flagged=flagged, scope=scope)
        out[key] = value
    return out
