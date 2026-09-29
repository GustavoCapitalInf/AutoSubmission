"""Revenue census over the local artifact cache or a copy of the tryout host's job store (true revenue spec §14.2).
Local only; never run in CI.

`snapshot` re-classifies every reconciled, de-duplicated cached analysis with the `analysis` package of one checkout
(`--code-root`) and records, per account, every posted credit's revenue decision (state, method, rule, tier, reason,
entity, amount in cents, the digit-masked normalized text) and, where the checkout has them, the guard facts of
§14.3 read with that checkout's readers. `compare` reads a base snapshot and one or two later ones and reports the
shares, the tiers and reasons, the move matrix, every row that left `non_revenue` (by the narrowing of §6.3 that moved
it), every verified row that lost its verification (by declared cause), the lender-credit and eligible-deposit moves
by cause, the package gate, and the guards G1 to G17 (G7 is tools/lender_census.py; G15 to G17 are the review's
refund, tax-refund and own-account-transfer guards). Every figure it prints is a count, a share or a total;
descriptors stay in the output file, digit-masked, outside the repository.

Usage, from the repository root of the checkout that holds this tool:
    python -m tools.revenue_census snapshot --data-dir <webapp_data> --out <file> [--code-root <checkout>] [--limit N]
                                            [--basis input|pdf]
    python -m tools.revenue_census snapshot --jobs-db <webapp.db copy> --out <file> [--code-root <checkout>]
                                            [--basis input|pdf]
    python -m tools.revenue_census compare --base <file> --after <file> [--after <file>] --out <file>
    python -m tools.revenue_census sample --snapshot <5.6 file> --out <file>

`--basis` (S3.1): `input` (the default, the plan's census) reads the latest analysis of every cached analysis input.
An analysis input is a digest over the OCR markdown and its page partition (webapp.artifact_cache.analysis_input_sha),
so one PDF read by two OCR routes (native text, Tesseract, Paddle) that disagree by a byte is two inputs, and the
input basis counts it twice unless the two reads extract the same statement fingerprint. `pdf` reads one analysis per
source PDF: each PDF's OCR artifacts are re-hashed into the analysis inputs they are analysed under, and the newest
route that has an analysis is taken; an analysis no cached OCR artifact reaches (its OCR route is no longer cached) is
kept only when no statement already kept has its identity (bank, the account number's last four digits, the printed
period). Of a job store, `pdf` keeps each PDF's newest job. A snapshot records its basis, and `compare` refuses to
compare two bases.

`sample` draws §14.5's precision sample (up to 20 Verified rows of each stratum, the Verified rows the holder test
matches, and the 50 largest counted rows), digit-masked, with an empty `sort` for the reviewer.

Exit codes: snapshot and sample 0, or 2 when refused. compare 0 when every guard holds, 1 when one fails, 2 when
refused.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_DIGITS = re.compile(r"\d")

#: The non-revenue rules whose rows G1 follows (§14.3): reversal, insurer, D1, descriptor proceeds, potential
#: lender, strong non-revenue and duplicates.
NON_REVENUE_METHODS = frozenset({
    "reversal_cancellation_exclusion", "insurance_provider_credit_exclusion", "financing_proceeds_credit",
    "potential_lender_registry_credit_exclusion", "strong_non_revenue_rule", "duplicate_credit_exclusion",
    "matched_reversal_pair",
})
#: §6.3's narrowings, plus the owner's OQ2 ruling (BNPL settlements join PAYOUT_CREDIT_ENTITIES), in the order the
#: census tests them. Each is (name, whether it may lead to True).
NARROWINGS = (
    ("1_reimbursement_claim_signal", True),
    ("2_hcclaimpmt_insurer", True),
    ("3_insurer_customer_payment", False),
    ("4_book_or_funds_transfer", True),
    ("5_street_ln", True),
    ("6_card_credit_release", True),
    ("7_q7_dealer_funding", True),
    ("8_oq2_bnpl_settlement", True),
)
#: OQ2 (§19): the five BNPL providers whose settlements left D1, by their ledger entity names.
BNPL_ENTITIES = frozenset({"AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit"})
#: The declared causes of a verified row losing its verification (§7.0, §7.11, §7.7), and the two consequences of the
#: recurrence fixes this plan declares (Decisions): a pool that one of its members' re-reading splits between two
#: entities, and a pool left below the recurrence count once a declared veto takes a member out. S3.1 (the owner's
#: delegated review fixes of S2.2 and S2.3): a verified wire that the §7.9 wire vetoes now refuse (they read step 11's
#: descriptors on a wire, and a row whose reference is glued to WIRE), and a row whose verification read an operating
#: alias or a customer descriptor only inside the receiver field's value, the holder's name (§5.2). Any other cause
#: fails.
DECLARED_DEMOTIONS = (
    "square_capital", "square_payroll", "acctverify", "channel_gate", "holder_veto", "customer_id",
    "claim_first_off", "recurrence_veto", "sq_cap_or_sba", "new_non_revenue_marker", "reversal_pair",
    "entity_split", "direction_conflict_pool", "micro_deposit_floor", "pool_below_recurrence_after_a_declared_veto",
    "wire_veto", "receiver_value",
)
#: The operating-registry methods (§8.9).
REGISTRY_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "wholesale_auction_payout_form",
})
#: G10: the methods that may verify a real-time or push-rail row (step 10, the registry, §6.1 step 9b).
REGISTRY_VERIFYING_METHODS = REGISTRY_METHODS - {"operating_source_requires_context"}
#: G3: the rules that verify on the payer's identity or remittance (step 11's descriptors, steps 12 to 14, Q5, Q6).
IDENTITY_METHODS = frozenset({
    "payer_remittance_descriptor", "public_payer_remittance", "wire_remittance_purpose", "repeat_wire_sender",
    "named_payer_repeats", "named_payer_company_form", "public_or_healthcare_payer",
})
#: G9: the four tiers and the state each goes with (§5.4).
TIER_STATES = {"verified": {"verified_revenue"}, "non_revenue": {"non_revenue"},
               "counted_flagged": {"unverified_deposit"}, "excluded_pending_review": {"unverified_deposit"}}
#: G12: a credit union's dealer funding needs this many such credits in the statement (§8.7).
CREDIT_UNION_DEALER_MIN_CREDITS = 2
#: The snapshot skips that are the credit census's filter, not a failure (§14.2).
FILTER_SKIPS = frozenset({"unreconciled", "duplicate"})
#: S3.1: the snapshot bases (see the module docstring).
BASES = ("input", "pdf")
#: S3.1: §6.1 steps 15 and 16, where a credit lands when every rule before them refuses it.
FALLBACK_METHODS = frozenset({"ambiguous_credit_descriptor", "unidentified_posted_credit"})
#: S3.1 (wire_veto): the rules the §7.9 wire vetoes govern since the S2.3 review: step 11's customer and invoice
#: descriptors on a wire (before 5.5 inside operating_income_descriptor's verified_operating_income_descriptor rule),
#: the AP remittance (§7.5) and the invoice wire (§7.9).
WIRE_VETOED_METHODS = frozenset({"operating_income_descriptor", "payer_remittance_descriptor", "wire_remittance_purpose"})
#: S3.1: the rows the BNPL listing (addition 3) names one by one; every shape is counted.
BNPL_LISTED_ROWS = 50
_CLAIM_SIGNAL = re.compile(
    r"\b(?:MEDICAID|MEDICARE|MEDI CAL|TRICARE|CHAMPVA|GEMT|EMS|PROV(?:IDER)? ?PAY(?:MENTS?)?|EDI PYMNTS|CLAIM PMT)\b"
    r"|(?:\bH[CE]?|HC)CLAIMPMT"
)
#: The census's own readers (independent of the code under test): the receiver fields, the ACH originator fields.
_RECEIVER = re.compile(r"\b(?:INDN|IND NAME|IND ID|RECEIVER NAME)\b")
_ACH_FIELD = re.compile(r"\b(?:DES|CO ENTRY DESCR|ORIG CO NAME)\b")
#: S3.1 (receiver_value): a receiver field with its value, up to the next ACH field, as the classifier's
#: _CREDIT_RECEIVER_VALUE reads it (§5.2). Before 5.5 the operating alias and step 11 read the whole row, this value
#: (the holder's name) included.
_RECEIVER_VALUE = re.compile(
    r"\b(?:INDN|IND NAME|IND ID|RECEIVER NAME)\b.*?(?=\b(?:CO ID|TRN|TRACE|PPD|CCD|WEB|CTX|TEL|ARC|BOC)\b|$)"
)
#: S3.1 (receiver_value): classification 5.4's customer, invoice and receivable descriptors (its
#: _VERIFIED_REVENUE_CREDIT_PATTERNS), which it read on the whole row.
_PRE_55_CUSTOMER_DESCRIPTORS = (
    re.compile(r"\bCUSTOMER\b.*\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b"),
    re.compile(r"\b(?:ACH|PAYMENT|DEPOSIT|CHECK|CHEQUE)\b.*\bCUSTOMER\b"),
    re.compile(r"\bINVOICE (?:PAYMENT|PAID|DEPOSIT)\b"),
    re.compile(r"\bACCOUNTS? RECEIVABLE\b"),
)
#: §7.0 (recurrence_veto): the recurrence veto's words, read on the digit-masked row before its receiver fields when a
#: snapshot carries no `recurrence_veto_wording` fact (a checkout before 5.5). S2.2 review (item A): a veto word of four
#: letters or more (all its words counted) reads through a glued digit, (?<![A-Z]) (a masked digit is '#'); a word of
#: three letters or fewer keeps the classifier's \b on the unmasked row, which (?<![A-Z#]) is on the masked one (a
#: digit glued to it is an ID's suffix, 'ID 1234FIN').
_RECURRENCE_VETO_WORDS = re.compile(
    r"(?<![A-Z])(?:LOANS?\b|CAPITAL\b|CAPI(?:T|TA)?\b|CAPSEC\b|ADVANCE\b|CASH ADV|FINANC|LEND|PAYROLL|PAYRL|DIR ?DEP"
    r"|DIRECT DEP|SALAR|WAGE|NET ?PAY|BONUS|REIMB|VERIF|INSUR|DEBIT CARD CREDIT|POS CREDIT)"
    r"|(?<![A-Z#])(?:CAP#*(?:SEC)?|ADV|FIN|MCA)\b"
)
#: §7.0 (review C2): FUNDING vetoes recurrence too, except on the settlements of the platforms that print it there.
_FUNDING_WORDS = re.compile(r"(?<![A-Z])(?:FUNDING|FUNDED)\b")
_FUNDING_SETTLEMENT_ENTITIES = frozenset({"TapGoods Payments", "Braintree", "Buildium"})
#: G15 (review C1): a refund word, glued or not.
_REFUND_WORD = re.compile(r"[A-Z]*REFUND\w*|\bRFND\w*|\bREFND\w*|\bRFD\b")
#: G16 (review I6): a tax refund or an earned-income credit, glued or not.
_TAX_REFUND_WORD = re.compile(r"[A-Z]*TAXRFD\b|\bTAX ?REF\w*|\bTAX ?EIC\b|\bTAX RFD\b")
#: S3.1 (addition 3): the words a BNPL row's public shape keeps. A word that holds a BNPL provider's name or a debt
#: collector's (AFFIRMCARD, TRUEACCORD) is kept whole; so are the registry's other BNPL alias words (SP AFF, AFFIRM
#: COM, AFFIRM PAY, AFFIRM CANADA), the consumer-side words S3.2 looks for, and the banks' channel, field and template
#: words. Any other word (a person's or a private business's name) prints '*', and a word that holds a digit '#'.
_PUBLIC_NAME = re.compile(r"AFFIRM|AFTERPAY|GREENSKY|KLARNA|SUNBIT|TRUEACCORD")
_PUBLIC_WORDS = frozenset({
    # The registry's BNPL alias words, and the consumer-side forms' words.
    "SP", "AFF", "COM", "PAY", "CANADA", "CARD", "BALANCE", "WITHDRAWAL", "WITHDRAW", "REFUND", "REFUNDS", "RFND",
    "REFND", "RFD", "RETURN", "RETURNED", "REVERSAL", "LOAN", "LOANS", "FUNDING", "FUNDED", "FINANCING", "FINANCE",
    "CAPITAL", "CASHOUT", "INSTANT", "PURCHASE", "POS", "PAYOFF", "COLLECTION", "COLLECTIONS",
    # The banks' ACH, wire and transfer fields and template words.
    "ACH", "CCD", "PPD", "WEB", "CTX", "TEL", "SEC", "DES", "DESC", "DESCR", "INDN", "IND", "ID", "NAME", "CO",
    "ORIG", "ENTRY", "DATE", "TRN", "TRACE", "EED", "REF", "RMR", "OBI", "BNF", "PMT", "DET", "INFO", "RECEIVER",
    "CREDIT", "CR", "DEBIT", "DR", "DEPOSIT", "DEP", "PAYMENT", "PAYMENTS", "PYMT", "PMNT", "RCVD", "RECEIVED",
    "PAYOUT", "PAYOUTS", "SETTLEMENT", "SETTLEMENTS", "SETTLEMNT", "SETTLE", "SETL", "STLMT", "SETTL", "TRANSFER",
    "XFER", "TFR", "FUNDS", "FUND", "DISBURSEMENT", "DISB", "ELECTRONIC", "EFT", "CORP", "CORPORATE", "BUSINESS",
    "MERCHANT", "MERCH", "WIRE", "FEDWIRE", "TYPE", "IN", "OUT", "BOOK", "DIRECT", "MISC", "ONLINE", "INTERNET",
    "BANKING", "BANK", "PREAUTHORIZED", "PREAUTH", "RTP", "REAL", "TIME", "SAME", "DAY", "FROM", "TO", "FOR", "BY",
    "OF", "THE", "AND", "INC", "LLC", "LTD", "CORPORATION", "COMPANY", "USA", "US", "NA", "VIA", "SALE", "SALES",
})


def mask(text: object) -> str:
    return _DIGITS.sub("#", " ".join(str(text or "").split()))


def public_shape(text: object) -> str:
    """S3.1 (addition 3): a row's public shape: digits masked, the public words kept (_PUBLIC_WORDS, a BNPL provider's
    or a debt collector's name), a word that holds a digit printed '#', any other word '*', and a run of one mark
    printed once."""
    words: list[str] = []
    for token in mask(text).split():
        if _PUBLIC_NAME.search(token) or token in _PUBLIC_WORDS:
            word = token
        elif "#" in token:
            word = "#"
        else:
            word = "*"
        if not (word in {"#", "*"} and words and words[-1] == word):
            words.append(word)
    return " ".join(words)


def _before_receiver(text: str) -> str:
    return _RECEIVER.split(text, 1)[0]


def _account_payloads(node: object) -> Iterator[dict]:
    """Every account payload (a dict whose `statement` holds a `transactions` list), in order."""
    if isinstance(node, dict):
        statement = node.get("statement")
        if isinstance(statement, dict) and isinstance(statement.get("transactions"), list):
            yield node
            return
        for value in node.values():
            yield from _account_payloads(value)
    elif isinstance(node, list):
        for value in node:
            yield from _account_payloads(value)


def _read_only(database: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)


def _artifact(data_dir: Path, relative: str) -> dict | None:
    """A cached artifact's payload, or None when it cannot be read. The index stores the path with the separators of
    the host that wrote it (a Windows cache stores backslashes)."""
    try:
        payload = json.loads((data_dir / "artifacts" / relative.replace("\\", "/")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def cached_accounts(
    data_dir: Path, limit: int | None = None, *, basis: str = "input", stats: dict | None = None
) -> Iterator[tuple[str, dict]]:
    """(id, account payload) for the latest cached analysis of each input (basis `input`), or of each source PDF
    (basis `pdf`, S3.1); the cache is opened read-only. `stats`, when given, receives the basis's counts."""
    if basis not in BASES:
        raise ValueError(f"unknown basis {basis!r}")
    stats = {} if stats is None else stats
    connection = _read_only(data_dir / "webapp.db")
    try:
        latest = connection.execute(
            "SELECT a.input_sha256, a.artifact_path, a.created_at FROM artifact_cache a JOIN ("
            " SELECT input_sha256, MAX(created_at) AS newest FROM artifact_cache"
            " WHERE stage = 'analysis' GROUP BY input_sha256) b"
            " ON a.input_sha256 = b.input_sha256 AND a.created_at = b.newest"
            " WHERE a.stage = 'analysis' ORDER BY a.input_sha256"
        ).fetchall()
        routes: dict[str, list[str]] = defaultdict(list)
        if basis == "pdf":
            # Each PDF's OCR artifacts (one per route), newest first.
            for pdf, relative in connection.execute(
                "SELECT input_sha256, artifact_path FROM artifact_cache WHERE stage = 'ocr'"
                " ORDER BY input_sha256, created_at DESC, cache_key"
            ):
                routes[pdf].append(relative)
    finally:
        connection.close()
    stats["analysis_inputs"] = len({sha for sha, _relative, _created in latest})
    if basis == "pdf":
        newest = {sha: (relative, created) for sha, relative, created in latest}
        yield from _pdf_accounts(data_dir, newest, routes, limit, stats)
        return
    for number, (sha, relative, _created) in enumerate(latest):
        if limit is not None and number >= limit:
            return
        payload = _artifact(data_dir, relative)
        if payload is None:
            continue
        for index, account in enumerate(_account_payloads(payload.get("artifact"))):
            yield f"c{sha[:12]}.{index}", account


def _analysis_inputs_of(document: dict) -> list[str]:
    """S3.1: the analysis inputs an OCR artifact's document is analysed under, by the one derivation of them
    (webapp.artifact_cache.analysis_input_sha, over the markdown and the page partition): text-only, and fed the
    native evidence the document carries (P22-IDENTITY), if it carries any."""
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import analysis_input_sha

    pages = [str(page) for page in document.get("pages") or []]
    markdown = StatementMarkdown(
        source_file="census.pdf", model=str(document.get("model") or ""), pages=pages
    ).to_markdown()
    shas = [analysis_input_sha(markdown, pages)]
    native = document.get("native_evidence_sha256")
    if isinstance(native, str) and len(native) == 64:
        try:
            shas.append(analysis_input_sha(markdown, pages, evidence_sha256=native))
        except (TypeError, ValueError):
            pass
    return shas


def _statement_identity(account: dict) -> tuple | None:
    """S3.1 (the pdf basis): a statement's identity read from its payload: the bank, the account number's last four
    digits and the printed period. None when the payload prints no period or fewer than four account digits: such an
    account is never merged with another."""
    statement = account.get("statement") or {}
    digits = re.sub(r"\D", "", str(statement.get("account_number") or ""))
    start, end = statement.get("period_start"), statement.get("period_end")
    if len(digits) < 4 or not start or not end:
        return None
    return " ".join(str(statement.get("bank") or "").upper().split()), digits[-4:], str(start), str(end)


def _pdf_accounts(
    data_dir: Path, latest: dict[str, tuple[str, str]], routes: dict[str, list[str]], limit: int | None, stats: dict
) -> Iterator[tuple[str, dict]]:
    """S3.1: the pdf basis. Each PDF (in hash order) yields the latest analysis of the analysis input its newest OCR
    route with an analysis is analysed under, once (two PDFs that read to one markdown share one analysis, which the
    first yields). Then every analysis input no cached OCR route reaches (an orphan: its route is no longer cached),
    newest first, yields each account whose statement identity no account yielded before holds (an account without
    an identity is always yielded). `limit` caps the analyses read."""
    for name in ("pdfs_joined", "pdfs_joined_on_newest_route", "pdfs_without_an_analysis", "pdfs_sharing_an_analysis",
                 "analysis_inputs_joined", "orphan_inputs", "orphan_accounts_kept",
                 "orphan_accounts_matching_a_kept_statement", "orphan_accounts_without_identity"):
        stats[name] = 0
    stats["pdfs"] = len(routes)
    reached: set[str] = set()
    taken: set[str] = set()
    identities: set[tuple] = set()
    read = 0
    for pdf in sorted(routes):
        chosen: tuple[str, int] | None = None
        for position, relative in enumerate(routes[pdf]):
            document = ((_artifact(data_dir, relative) or {}).get("artifact") or {}).get("document")
            if not isinstance(document, dict):
                continue
            for sha in _analysis_inputs_of(document):
                if sha in latest:
                    reached.add(sha)
                    if chosen is None:
                        chosen = (sha, position)
        stats["analysis_inputs_joined"] = len(reached)
        if chosen is None:
            stats["pdfs_without_an_analysis"] += 1
            continue
        stats["pdfs_joined"] += 1
        stats["pdfs_joined_on_newest_route"] += chosen[1] == 0
        if chosen[0] in taken:
            stats["pdfs_sharing_an_analysis"] += 1
            continue
        taken.add(chosen[0])
        if limit is not None and read >= limit:
            stats["limit_reached"] = True
            return
        read += 1
        payload = _artifact(data_dir, latest[chosen[0]][0])
        if payload is None:
            continue
        for index, account in enumerate(_account_payloads(payload.get("artifact"))):
            identity = _statement_identity(account)
            if identity is not None:
                identities.add(identity)
            yield f"p{pdf[:12]}.{index}", account
    orphans = sorted((sha for sha in latest if sha not in reached), key=lambda sha: (latest[sha][1], sha), reverse=True)
    stats["orphan_inputs"] = len(orphans)
    for sha in orphans:
        if limit is not None and read >= limit:
            stats["limit_reached"] = True
            return
        read += 1
        payload = _artifact(data_dir, latest[sha][0])
        if payload is None:
            continue
        for index, account in enumerate(_account_payloads(payload.get("artifact"))):
            identity = _statement_identity(account)
            if identity is None:
                stats["orphan_accounts_without_identity"] += 1
            elif identity in identities:
                stats["orphan_accounts_matching_a_kept_statement"] += 1
                continue
            else:
                identities.add(identity)
            stats["orphan_accounts_kept"] += 1
            yield f"o{sha[:12]}.{index}", account


def job_accounts(database: Path, *, basis: str = "input", stats: dict | None = None) -> Iterator[tuple[str, dict]]:
    """(id, account payload) for every saved job of a copy of the tryout host's job store, opened read-only; with the
    pdf basis (S3.1), only each PDF's newest job (a job without a document is kept)."""
    if basis not in BASES:
        raise ValueError(f"unknown basis {basis!r}")
    stats = {} if stats is None else stats
    connection = _read_only(database)
    try:
        if basis == "pdf":
            rows = connection.execute(
                "SELECT j.id, j.analysis_json, d.content_sha256 FROM jobs j LEFT JOIN documents d"
                " ON d.id = j.document_id WHERE j.analysis_json IS NOT NULL ORDER BY j.created_at DESC, j.id DESC"
            ).fetchall()
        else:
            rows = [(job_id, text, None) for job_id, text in connection.execute(
                "SELECT id, analysis_json FROM jobs WHERE analysis_json IS NOT NULL").fetchall()]
    finally:
        connection.close()
    stats["jobs"] = len(rows)
    seen: set[str] = set()
    for job_id, text, pdf in rows:
        if pdf is not None:
            if pdf in seen:
                stats["jobs_repeating_a_pdf"] = stats.get("jobs_repeating_a_pdf", 0) + 1
                continue
            seen.add(pdf)
            stats["pdfs"] = len(seen)
        try:
            analysis = json.loads(text)
        except ValueError:
            continue
        for index, account in enumerate(_account_payloads(analysis)):
            yield f"j{job_id[:8]}.{index}", account


def _fingerprint(statement) -> tuple:
    return (statement.bank, statement.period_start, statement.period_end, statement.beginning_balance,
            statement.ending_balance, len(statement.transactions), statement.account_number)


def _pool_threshold(classifier, record) -> int:
    """§7.0: the recurrence count of the entity's pool: two on a business account (a customer-payment platform reads
    only the business words), three otherwise."""
    from analysis.classification_registry import OPERATING_REVENUE_SOURCE_TYPES

    if OPERATING_REVENUE_SOURCE_TYPES.get(record.revenue_canonical_entity or "") == "customer_payment_platform":
        business = classifier._matches_any(
            classifier.account_name_text(record.account_name), classifier._BUSINESS_ACCOUNT_PATTERNS
        )
    else:
        business = classifier._business_account(record.account_name)
    return classifier._RECURRENCE_MIN_BUSINESS_CREDITS if business else classifier._RECURRENCE_MIN_CREDITS


def _guard_facts(record, text: str) -> dict:
    """The §14.3 guard facts of one posted credit, read with the checkout's own readers when it has them."""
    from analysis import transaction_classifier as classifier

    facts: dict = {}
    if not hasattr(classifier, "revenue_text"):
        return facts
    revenue = classifier.revenue_text(text)
    region = classifier.payer_region(revenue)
    row = _before_receiver(revenue)
    facts["gate"] = classifier.channel_gate(revenue)
    facts["holder"] = classifier.holder_named(region, record.account_name)
    facts["numbered"] = classifier.numbered_company(revenue, region)
    # G1 (review I1): narrowing 4 needs a third-party originator.
    facts["third_party_originator"] = classifier._third_party_originator(revenue) is not None
    # G17 (review C3): the holder's own transfer, read on its ACH originator whatever the payer region says.
    facts["own_transfer"] = bool(
        classifier._TRANSFER_WORDING.search(row) and _ACH_FIELD.search(row)
        and classifier.holder_named(classifier._ach_payer_region(revenue), record.account_name)
    )
    # G14 (review I1): the rows that count toward an entity's recurrence pool, and the count it needs.
    facts["pool_candidate"] = classifier._in_operating_pool(record)
    facts["pool_vetoed"] = bool(classifier._recurrence_vetoed(record, revenue) or facts["gate"] == "closed")
    facts["pool_threshold"] = _pool_threshold(classifier, record)
    # S3.1 (wire_veto): the §7.9 wire vetoes as the S2.3 review applies them (step 11 on a wire, a reference glued to
    # WIRE), read with the checkout's own code on the text and payer region the credit decision reads.
    if hasattr(classifier, "_wire_vetoes_apply"):
        facts["wire_vetoed"] = bool(
            classifier._wire_vetoes_apply(revenue) and classifier._wire_vetoed(revenue, region, record.account_name)
        )
    # S3.1 (recurrence_veto): the worded recurrence veto (§7.0, S2.2-A, S2.4), read with the checkout's own code.
    if hasattr(classifier, "_recurrence_veto_wording"):
        facts["recurrence_veto_wording"] = bool(classifier._recurrence_veto_wording(record, revenue))
    try:
        from analysis import true_revenue
    except ImportError:
        return facts
    facts.update(true_revenue.guard_facts(record, revenue))
    return facts


def account_snapshot(account: dict) -> dict:
    """Re-classify one account payload with the `analysis` package on sys.path."""
    from analysis.metrics import compute_metrics
    from analysis.schema import Statement
    from analysis.transaction_classifier import classify_statement_transactions

    statement = Statement.model_validate(account["statement"])
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    credits = []
    posted = [record for record in records if record.amount > 0 and record.is_posted]
    for index, record in enumerate(records):
        if record.amount <= 0 or not record.is_posted or record.revenue_classification is None:
            continue
        credits.append({
            "i": index,
            "cents": round(record.amount * 100),
            "state": record.revenue_classification,
            "method": record.revenue_match_method,
            "rule": record.revenue_matched_rule,
            "entity": record.revenue_canonical_entity,
            "alias": record.revenue_matched_alias,
            "tier": getattr(record, "revenue_tier", None),
            "reason": getattr(record, "revenue_tier_reason", None),
            "class": record.classification,
            "lender_credit": bool(getattr(record, "contributes_to_lender_credit_exclusion", False)),
            "text": mask(record.normalized_description),
            "facts": _guard_facts(record, record.normalized_description),
        })
    tier_totals = None
    if hasattr(metrics, "counted_flagged_total"):
        tier_totals = {
            "verified": round(metrics.verified_revenue_total * 100),
            "counted_flagged": round(metrics.counted_flagged_total * 100),
            "excluded_pending_review": round(metrics.excluded_pending_review_total * 100),
            "non_revenue": round(metrics.non_revenue_total * 100),
        }
    return {
        "bank": statement.bank,
        "rows": len(records),
        "credits": credits,
        "posted_cents": sum(credit["cents"] for credit in credits),
        # G9 (review I1): every posted credit, whatever its state, counted apart from the rows the census kept.
        "posted_credit_count": len(posted),
        "posted_credit_cents": sum(round(record.amount * 100) for record in posted),
        "tier_totals": tier_totals,
        "lender_credits": metrics.lender_credits,
        "eligible_deposits": metrics.legacy_eligible_deposits,
        "revenue_review_required": metrics.revenue_review_required,
    }


def snapshot(accounts: Iterable[tuple[str, dict]], *, basis: str = "input", basis_stats: dict | None = None) -> dict:
    """{"classification_version", "basis", "basis_stats", "accounts": {id: account snapshot}, "skipped": {reason: n}},
    over the reconciled, de-duplicated accounts (the credit census's filter). `basis_stats` is the dict the account
    reader fills (S3.1); it is read once every account is read."""
    from analysis.schema import Statement
    from analysis.transaction_classifier import CLASSIFICATION_VERSION

    result: dict = {"classification_version": CLASSIFICATION_VERSION, "basis": basis, "accounts": {}, "skipped": {}}
    skipped: Counter = Counter()
    seen: set = set()
    for key, account in accounts:
        if not bool((account.get("reconciliation") or {}).get("ok")):
            skipped["unreconciled"] += 1
            continue
        try:
            fingerprint = _fingerprint(Statement.model_validate(account["statement"]))
        except Exception:  # noqa: BLE001  (a stored payload the schema no longer reads)
            skipped["unreadable"] += 1
            continue
        if fingerprint in seen:
            skipped["duplicate"] += 1
            continue
        seen.add(fingerprint)
        try:
            result["accounts"][key] = account_snapshot(account)
        except Exception as error:  # noqa: BLE001
            skipped[type(error).__name__] += 1
    result["skipped"] = dict(sorted(skipped.items()))
    result["basis_stats"] = dict(basis_stats or {})
    return result


def _share(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 2) if whole else 0.0


def _summary(snap: dict) -> dict:
    """True and Verified shares, $0 statements, the median statement shares, the tiers and reasons."""
    totals: Counter = Counter()
    rows: Counter = Counter()
    tiers: Counter = Counter()
    reasons: dict = defaultdict(lambda: [0, 0])
    zero_verified = zero_true = with_credits = gated = 0
    true_shares, verified_shares = [], []
    for account in snap["accounts"].values():
        posted = account["posted_cents"]
        if posted <= 0:
            continue
        with_credits += 1
        verified = sum(c["cents"] for c in account["credits"] if c["state"] == "verified_revenue")
        counted = sum(c["cents"] for c in account["credits"] if c.get("tier") == "counted_flagged")
        true = verified + counted
        zero_verified += verified == 0
        zero_true += true == 0
        true_shares.append(true / posted)
        verified_shares.append(verified / posted)
        gated += bool(account.get("revenue_review_required"))
        for credit in account["credits"]:
            totals[credit["state"]] += credit["cents"]
            rows[credit["state"]] += 1
            if credit.get("tier"):
                tiers[credit["tier"]] += credit["cents"]
            if credit.get("reason"):
                slot = reasons[f"{credit['tier']}/{credit['reason']}"]
                slot[0] += 1
                slot[1] += credit["cents"]
        totals["posted"] += posted
    true_total = totals["verified_revenue"] + tiers["counted_flagged"]
    return {
        "version": snap.get("classification_version"),
        "statements_with_credits": with_credits,
        "posted_dollars": round(totals["posted"] / 100, 2),
        "verified_share": _share(totals["verified_revenue"], totals["posted"]),
        "unverified_share": _share(totals["unverified_deposit"], totals["posted"]),
        "non_revenue_share": _share(totals["non_revenue"], totals["posted"]),
        "true_share": _share(true_total, totals["posted"]) if tiers else None,
        "held_share": _share(tiers["excluded_pending_review"], totals["posted"]) if tiers else None,
        "zero_verified_statements": zero_verified,
        "zero_true_statements": zero_true if tiers else None,
        "median_statement_true_share": round(100 * statistics.median(true_shares), 1) if tiers and true_shares else None,
        "median_statement_verified_share": round(100 * statistics.median(verified_shares), 1) if verified_shares else None,
        "gated_statements": gated,
        "gated_share": _share(gated, with_credits),
        "rows": dict(rows),
        "reasons": {key: {"rows": value[0], "dollars": round(value[1] / 100, 2)} for key, value in sorted(reasons.items())},
    }


def _narrowing(base: dict, after: dict) -> str | None:
    """Which §6.3 narrowing (or the OQ2 ruling) moved a base non_revenue row out of non_revenue; None for none."""
    text, base_method = after["text"], base["method"]
    facts = after.get("facts") or {}
    if base_method == "reversal_cancellation_exclusion" and "REIMBURSEMENT" in text and _CLAIM_SIGNAL.search(text):
        return "1_reimbursement_claim_signal"
    if base_method == "insurance_provider_credit_exclusion":
        if after["method"] == "insurer_customer_payment" and not re.search(r"H[CE]?CLAIMPMT", after["text"]):
            return "3_insurer_customer_payment"
        if re.search(r"H[CE]?CLAIMPMT", after["text"]):
            return "2_hcclaimpmt_insurer"
        return "3_insurer_customer_payment"
    # Review I1: a book or funds transfer leaves only on a printed third-party originator (T19, §7.11).
    if (
        base_method == "strong_non_revenue_rule"
        and re.search(r"\b(?:BOOK|FUNDS?) TRANSFER\b", text)
        and facts.get("third_party_originator")
    ):
        return "4_book_or_funds_transfer"
    if facts.get("street_ln") or (base["text"] != after["text"] and " LN " in f" {after['text']} "):
        return "5_street_ln"
    if base_method == "reversal_cancellation_exclusion" and re.search(r"\b(?:DEBIT CARD CREDIT|POS CREDIT)\b", text):
        return "6_card_credit_release"
    if base_method == "financing_proceeds_credit" and after["method"] == "auto_lender_dealer_funding":
        return "7_q7_dealer_funding"
    # Review I1: only the five BNPL providers' settlements leave D1 by the OQ2 ruling.
    if (
        base_method == "financing_proceeds_credit"
        and after["method"] != "financing_proceeds_credit"
        and base.get("entity") in BNPL_ENTITIES
    ):
        return "8_oq2_bnpl_settlement"
    return None


def _wire_veto_demotion(base: dict, after: dict) -> bool:
    """S3.1 (wire_veto): a verified row of a rule the §7.9 wire vetoes govern (WIRE_VETOED_METHODS; of step 11 only its
    customer and invoice descriptors, not a card form) that the checkout's own wire vetoes refuse (the snapshot's
    `wire_vetoed` fact), and that therefore fell to steps 15 and 16. A snapshot without the fact declares none."""
    facts = after.get("facts") or {}
    if not facts.get("wire_vetoed") or after["method"] not in FALLBACK_METHODS:
        return False
    if base["method"] == "operating_income_descriptor":
        return (base.get("rule") or "verified_operating_income_descriptor") == "verified_operating_income_descriptor"
    return base["method"] in WIRE_VETOED_METHODS


def _read_only_in_receiver_value(base: dict) -> bool:
    """S3.1 (receiver_value): the base row's verification read its operating alias (a registry method's alias) or a
    customer, invoice or receivable descriptor (step 11 before 5.5) only inside a receiver field's value, which the
    5.5 readers no longer read (§5.2): it is read on the whole row and not on the row without the receiver values."""
    text = base["text"]
    without = _RECEIVER_VALUE.sub(" ", text)
    if without == text:
        return False
    if base["method"] in REGISTRY_METHODS and base.get("alias"):
        alias = re.compile(rf"(?<!\S){re.escape(mask(base['alias']))}(?!\S)")
        return alias.search(text) is not None and alias.search(without) is None
    if (
        base["method"] == "operating_income_descriptor"
        and (base.get("rule") or "verified_operating_income_descriptor") == "verified_operating_income_descriptor"
    ):
        return any(pattern.search(text) for pattern in _PRE_55_CUSTOMER_DESCRIPTORS) and not any(
            pattern.search(without) for pattern in _PRE_55_CUSTOMER_DESCRIPTORS
        )
    return False


def _recurrence_vetoed_wording(after: dict) -> bool:
    """§7.0 (recurrence_veto): the snapshot's `recurrence_veto_wording` fact (the checkout's own reading, which spares
    a store-name platform's holder words and FUNDING on the three platforms that print it) when it carries one;
    otherwise the veto words on the digit-masked row before its receiver fields."""
    facts = after.get("facts") or {}
    if "recurrence_veto_wording" in facts:
        return bool(facts["recurrence_veto_wording"])
    row = _before_receiver(after["text"])
    if _RECURRENCE_VETO_WORDS.search(row):
        return True
    return after.get("entity") not in _FUNDING_SETTLEMENT_ENTITIES and _FUNDING_WORDS.search(row) is not None


def _demotion_cause(base: dict, after: dict) -> str:
    """The declared cause of a base verified row that is no longer verified (§7.0, §7.11), or 'undeclared'."""
    text, method, rule = after["text"], after["method"], after["rule"] or ""
    facts = after.get("facts") or {}
    if after["cents"] < 100:
        return "micro_deposit_floor"
    if rule == "square_capital_credit" or rule == "sba_disbursement_credit":
        return "sq_cap_or_sba"
    if method == "matched_reversal_pair":
        return "reversal_pair"
    if method in {"reversal_cancellation_exclusion", "strong_non_revenue_rule"}:
        return "new_non_revenue_marker"
    if re.search(r"\bACCT ?VERIFY", text):
        return "acctverify"
    if method == "holder_named_payer" or facts.get("holder"):
        return "holder_veto"
    if facts.get("gate") == "closed" or (facts.get("gate") == "push" and base["method"] == "operating_income_descriptor"):
        return "channel_gate"
    if re.search(r"\bCUSTOMER ID\b", text):
        return "customer_id"
    if method == "insurer_customer_payment":
        return "claim_first_off"
    if _wire_veto_demotion(base, after):
        return "wire_veto"
    if _read_only_in_receiver_value(base):
        return "receiver_value"
    if re.search(r"\bPAYROLL|\bPAYRL|\bDIR ?DEP|\bSALAR|\bWAGE|\bBONUS", text) and "SQ" in text or "SQUARE" in text and re.search(r"PAYROLL", text):
        return "square_payroll"
    if _recurrence_vetoed_wording(after):
        return "recurrence_veto"
    if base.get("entity") and after.get("entity") and base["entity"] != after["entity"]:
        return "entity_split"
    if base["method"] == "recurring_operating_source" and method == "operating_source_requires_context":
        return "pool_below_recurrence_after_a_declared_veto"
    return "undeclared"


def _lender_move_cause(base: dict, after: dict) -> str:
    """M2 (§14.2, §11): why a credit entered or left the lender-credit exclusion (and so moved eligible deposits)."""
    if not after.get("lender_credit"):
        return _narrowing(base, after) or f"left:{after['method']}"
    if base["state"] == "verified_revenue":
        return _demotion_cause(base, after)
    return f"entered:{after['rule'] or after['method']}"


class BasisMismatch(ValueError):
    """S3.1: a compare of snapshots taken on two bases (their account ids name different things)."""


def _basis(snap: dict) -> str:
    return snap.get("basis") or "input"


def compare(base: dict, afters: list[dict]) -> dict:
    """The census report of §14.2 and the guards of §14.3 (G7 excepted), base against each later snapshot, all of one
    basis (S3.1: a mix raises BasisMismatch)."""
    basis = _basis(base)
    for after in afters:
        if _basis(after) != basis:
            raise BasisMismatch(
                f"the base snapshot reads the {basis} basis and a later one the {_basis(after)} basis;"
                " a census compares snapshots of one basis"
            )
    report: dict = {"basis": basis, "basis_stats": {"base": base.get("basis_stats"),
                                                    "after": [after.get("basis_stats") for after in afters]},
                    "base": _summary(base), "runs": []}
    for after in afters:
        moves: dict = defaultdict(lambda: [0, 0, set()])
        left_non_revenue: dict = defaultdict(lambda: [0, 0, set()])
        demoted: dict = defaultdict(lambda: [0, 0, set()])
        deposits: Counter = Counter()
        lender_moves: dict = defaultdict(lambda: [0, 0, set()])
        failures: dict = defaultdict(list)
        street_ln: list = []
        gate: Counter = Counter()
        q6_unlabelled = [0, 0]
        g13_apart: dict = defaultdict(lambda: [0, 0, set()])
        bnpl_shapes: Counter = Counter()
        bnpl_listed: list = []
        unmatched = 0
        tiered = any(credit.get("tier") for account in after["accounts"].values() for credit in account["credits"])
        # G9 (review I1): an account that failed to classify, or that the base holds and this run lost, fails.
        for reason, count in (after.get("skipped") or {}).items():
            if reason not in FILTER_SKIPS and count != (base.get("skipped") or {}).get(reason, 0):
                failures["G9"].append({"skipped": reason, "count": count})
        for key, old in base["accounts"].items():
            new = after["accounts"].get(key)
            if new is None or new["rows"] != old["rows"]:
                unmatched += 1
                failures["G9"].append({"account": key, "unmatched": True})
                continue
            old_by_index = {credit["i"]: credit for credit in old["credits"]}
            old_deposits, new_deposits = old.get("eligible_deposits"), new.get("eligible_deposits")
            if old_deposits is not None and new_deposits is not None:
                delta = round(new_deposits - old_deposits, 2)
                deposits["unchanged" if delta == 0 else ("up" if delta > 0 else "down")] += 1
            for credit in new["credits"]:
                prior = old_by_index.get(credit["i"])
                if prior is None:
                    continue
                target = credit.get("tier") or credit["state"]
                slot = moves[(f"{prior['state']}|{prior['method']}", f"{target}|{credit.get('reason') or credit['method']}")]
                slot[0] += 1
                slot[1] += credit["cents"]
                slot[2].add(key)
                in_true = credit["state"] == "verified_revenue" or credit.get("tier") == "counted_flagged"
                if prior["state"] == "non_revenue" and credit["state"] != "non_revenue":
                    cause = _narrowing(prior, credit) or "outside_the_narrowings"
                    entry = left_non_revenue[cause]
                    entry[0] += 1
                    entry[1] += credit["cents"]
                    entry[2].add(key)
                    allowed = dict(NARROWINGS).get(cause)
                    if cause == "outside_the_narrowings" or (in_true and allowed is False):
                        failures["G1"].append({"account": key, "i": credit["i"], "cause": cause, "text": credit["text"]})
                    if cause == "8_oq2_bnpl_settlement":
                        # S3.1 (addition 3): each OQ2 row's public shape, so S3.2 can check that no consumer-side
                        # form (AFFIRMCARD, SP AFF, TRUEACCORD KLARNA, BALANCE WITHDRAWAL, REFUND) left D1.
                        shape = public_shape(credit["text"])
                        bnpl_shapes[shape] += 1
                        if len(bnpl_listed) < BNPL_LISTED_ROWS:
                            bnpl_listed.append({"account": key, "i": credit["i"], "entity": prior.get("entity"),
                                                "after": f"{target}|{credit.get('reason') or credit['method']}",
                                                "shape": shape})
                if prior["state"] == "verified_revenue" and credit["state"] != "verified_revenue":
                    cause = _demotion_cause(prior, credit)
                    entry = demoted[cause]
                    entry[0] += 1
                    entry[1] += credit["cents"]
                    entry[2].add(key)
                    if cause == "undeclared":
                        failures["undeclared_demotion"].append({"account": key, "i": credit["i"],
                                                                "text": credit["text"]})
                if "lender_credit" in prior and bool(prior["lender_credit"]) != bool(credit.get("lender_credit")):
                    entry = lender_moves[_lender_move_cause(prior, credit)]
                    entry[0] += 1
                    entry[1] += credit["cents"] if credit.get("lender_credit") else -credit["cents"]
                    entry[2].add(key)
                for guard, failed in _row_guards(credit).items():
                    if failed:
                        failures[guard].append({"account": key, "i": credit["i"], "text": credit["text"]})
                if prior["text"] != credit["text"]:
                    # G7b: the street-LN guard is the only 5.5 change to the normalized text.
                    street_ln.append({"account": key, "i": credit["i"], "base": f"{prior['state']}|{prior['method']}",
                                      "after": f"{credit.get('tier') or credit['state']}|{credit['method']}",
                                      "text": credit["text"]})
                    if prior["method"] == "financing_proceeds_credit" and in_true:
                        failures["G7b"].append({"account": key, "i": credit["i"], "text": credit["text"]})
            for failure in _account_guards(new, tiered):
                failures[failure["guard"]].append({"account": key, **failure})
            if new.get("revenue_review_required"):
                for reason in {c["reason"] for c in new["credits"] if c.get("tier") == "excluded_pending_review"}:
                    gate[reason] += 1
            for credit in new["credits"]:
                facts = credit.get("facts") or {}
                if credit.get("reason") == "named_payer_unlabelled" and facts.get("q6_shape"):
                    q6_unlabelled[0] += 1
                    q6_unlabelled[1] += credit["cents"]
                if credit["state"] == "verified_revenue" and facts.get("numbered") and not _row_guards(credit)["G13"]:
                    entry = g13_apart[credit["method"]]
                    entry[0] += 1
                    entry[1] += credit["cents"]
                    entry[2].add(key)
        report["runs"].append({
            "summary": _summary(after),
            "accounts_unmatched": unmatched,
            "move_matrix": [
                {"from": source, "to": target, "rows": value[0], "dollars": round(value[1] / 100, 2),
                 "statements": len(value[2])}
                for (source, target), value in sorted(moves.items(), key=lambda item: -item[1][1])
            ],
            "left_non_revenue": {
                cause: {"rows": value[0], "dollars": round(value[1] / 100, 2), "statements": len(value[2])}
                for cause, value in sorted(left_non_revenue.items())
            },
            # S3.1 (addition 3): the OQ2 rows by public shape (every shape counted, the first rows listed).
            "bnpl_settlements": {"rows": sum(bnpl_shapes.values()), "shapes": dict(bnpl_shapes.most_common()),
                                 "listed": bnpl_listed},
            "verified_demotions": {
                cause: {"rows": value[0], "dollars": round(value[1] / 100, 2), "statements": len(value[2])}
                for cause, value in sorted(demoted.items())
            },
            "eligible_deposits": dict(deposits),
            # M2 (§14.2, §11): lender credits (so eligible deposits, the other way) by the cause that moved each row.
            "lender_credit_moves_by_cause": {
                cause: {"rows": value[0], "lender_credit_dollars": round(value[1] / 100, 2),
                        "eligible_deposit_dollars": round(-value[1] / 100, 2), "statements": len(value[2])}
                for cause, value in sorted(lender_moves.items())
            },
            "street_ln_changes": street_ln,
            "gated_statements_by_held_reason": dict(gate.most_common()),
            "named_payer_unlabelled_with_q6_shape": {"rows": q6_unlabelled[0],
                                                     "dollars": round(q6_unlabelled[1] / 100, 2)},
            # G13 (review I1): Verified rows the numbered-company template matches that a processor's registry or
            # card form verified (its payer is the processor, §5.2); the precision sample reads them.
            "g13_listed_apart": {
                method: {"rows": value[0], "dollars": round(value[1] / 100, 2), "statements": len(value[2])}
                for method, value in sorted(g13_apart.items())
            },
            "guards": {guard: {"failures": len(items), "sample": items[:25]} for guard, items in sorted(failures.items())},
        })
    return report


def _account_guards(account: dict, tiered: bool) -> list[dict]:
    """The account-level guards of §14.3: G9 (the four-tier identity, each tier with its state, every posted credit
    kept, and the metrics' tier totals), G12's credit-union count and G14's recurrence pools."""
    found: list[dict] = []
    credits = account["credits"]
    posted_count = account.get("posted_credit_count")
    if posted_count is not None and (posted_count != len(credits)
                                     or account.get("posted_credit_cents") != account["posted_cents"]):
        found.append({"guard": "G9", "posted_credits_without_a_revenue_state": posted_count - len(credits)})
    if tiered:
        by_tier: Counter = Counter()
        for credit in credits:
            tier = credit.get("tier")
            if tier not in TIER_STATES or credit["state"] not in TIER_STATES[tier]:
                found.append({"guard": "G9", "i": credit["i"], "tier": tier, "state": credit["state"]})
            by_tier[tier] += credit["cents"]
        if sum(by_tier.values()) != account["posted_cents"]:
            found.append({"guard": "G9", "identity": "rows"})
        totals = account.get("tier_totals")
        if totals is not None and (
            any(abs(totals[tier] - by_tier[tier]) > 1 for tier in TIER_STATES)
            or abs(sum(totals.values()) - account["posted_cents"]) > len(TIER_STATES)
        ):
            found.append({"guard": "G9", "identity": "metrics"})
    unions = [c for c in credits if c["method"] == "auto_lender_dealer_funding"
              and (c.get("facts") or {}).get("q7_credit_union") and not (c.get("facts") or {}).get("q7_listed")]
    if 0 < len(unions) < CREDIT_UNION_DEALER_MIN_CREDITS:
        found.extend({"guard": "G12", "i": c["i"], "credit_union_rows": len(unions)} for c in unions)
    pools: dict = defaultdict(list)
    lifted: dict = defaultdict(list)
    for credit in credits:
        facts = credit.get("facts") or {}
        if credit.get("entity") and facts.get("pool_candidate") and not facts.get("pool_vetoed"):
            pools[credit["entity"]].append(credit)
        if credit["method"] == "recurring_operating_source" and credit.get("entity"):
            lifted[credit["entity"]].append(credit)
    for entity, rows in lifted.items():
        needed = min((row.get("facts") or {}).get("pool_threshold", 2) for row in rows)
        if len(pools.get(entity, [])) < needed:
            found.extend({"guard": "G14", "i": row["i"], "pool": len(pools.get(entity, [])), "needed": needed}
                         for row in rows)
    return found


#: §14.5's Verified strata: stratum -> the revenue methods that fill it.
PRECISION_STRATA = {
    "q5_repeat_wires": lambda credit: credit["method"] == "repeat_wire_sender",
    "q6a_repeats": lambda credit: credit["method"] == "named_payer_repeats",
    "q6b_company_form": lambda credit: credit["method"] == "named_payer_company_form",
    "q6c_government_healthcare": lambda credit: credit["method"] == "public_or_healthcare_payer",
    "ap_remittance": lambda credit: credit["method"] == "payer_remittance_descriptor",
    "public_payers": lambda credit: credit["method"] == "public_payer_remittance",
    "invoice_wires": lambda credit: credit["method"] == "wire_remittance_purpose",
    # §7.1 card forms (rule card_settlement_form_<label>), §7.2 payout forms (alias <platform>_..._form), §7.8.
    "card_and_payout_forms": lambda credit: (
        (credit.get("rule") or "").startswith("card_settlement_form_")
        or (credit.get("alias") or "").endswith("_form")
        or credit["method"] == "wholesale_auction_payout_form"
    ),
    "q7_dealer_funding": lambda credit: credit["method"] == "auto_lender_dealer_funding",
}


def precision_sample(snap: dict, *, per_stratum: int = 20, largest_counted: int = 50, seed: int = 55) -> dict:
    """§14.5: a stratified sample of a 5.6 snapshot, digit-masked: `per_stratum` Verified rows of each stratum
    (every row when it holds fewer), the Verified rows G3 lists (the holder test matched) and G13 lists apart (the
    numbered-company template on a processor's settlement), and the `largest_counted` largest counted rows. Each row carries an empty `sort` for the reviewer: revenue, loan, own_money, refund,
    transfer, insurance, other or cannot_tell."""
    import random

    pools: dict = defaultdict(list)
    counted: list = []
    for key, account in snap["accounts"].items():
        for credit in account["credits"]:
            row = {"account": key, "i": credit["i"], "dollars": round(credit["cents"] / 100, 2),
                   "method": credit["method"], "tier": credit.get("tier"), "reason": credit.get("reason"),
                   "text": credit["text"], "sort": ""}
            if credit["state"] == "verified_revenue":
                for stratum, belongs in PRECISION_STRATA.items():
                    if belongs(credit):
                        pools[stratum].append(row)
                if (credit.get("facts") or {}).get("holder"):
                    pools["holder_test_rows"].append(row)
                if (credit.get("facts") or {}).get("numbered"):
                    pools["numbered_template_rows"].append(row)
            elif credit.get("tier") == "counted_flagged":
                counted.append(row)
    chooser = random.Random(seed)
    sample = {stratum: (rows if len(rows) <= per_stratum else chooser.sample(rows, per_stratum))
              for stratum, rows in sorted(pools.items())}
    sample["largest_counted"] = sorted(counted, key=lambda row: -row["dollars"])[:largest_counted]
    return sample


def _row_guards(credit: dict) -> dict[str, bool]:
    """The row-level guards of §14.3 and the review's G15 to G17 (True means the guard failed)."""
    facts = credit.get("facts") or {}
    tier = credit.get("tier")
    in_true = credit["state"] == "verified_revenue" or tier == "counted_flagged"
    verified = credit["state"] == "verified_revenue"
    method = credit["method"]
    row = _before_receiver(credit["text"])
    guards = {
        # A registry row reads the root with the holder's own words and §7.0's FUNDING settlements aside (review I1).
        "G2": verified and method != "auto_lender_dealer_funding" and bool(
            facts.get("registry_root") if method in REGISTRY_METHODS else facts.get("financing_root")
        ),
        "G3": bool(facts.get("holder")) and (
            (verified and method in IDENTITY_METHODS)
            or (verified and method == "operating_income_descriptor" and bool(facts.get("customer_descriptor")))
            or tier == "counted_flagged"
        ),
        "G4": in_true and bool(facts.get("transfer_no_counterparty")),
        "G6": in_true and method == "direction_conflict",
        # G10 (review I1): a closed row never verifies; a push-rail row verifies through the registry only.
        "G10": verified and (
            facts.get("gate") == "closed" or (facts.get("gate") == "push" and method not in REGISTRY_VERIFYING_METHODS)
        ),
        "G11": in_true and bool(facts.get("pay_or_personal")),
        "G12": method == "auto_lender_dealer_funding" and (
            not facts.get("q7_payer_ok", True) or bool(facts.get("q7_veto_word"))
        ),
        # G13 (review I1): the full numbered-company guard, the DIRECT DEPOSIT <digits> template included, on the
        # rules that read it (§5.2: steps 11 to 14, Q5, Q6); the region form on every Verified row. A processor's
        # settlement printed after BMO's template (MISC PAYMENT <digits> GBL VI) is listed apart (g13_listed_apart).
        "G13": verified and (
            bool(facts.get("numbered_region"))
            or (bool(facts.get("numbered")) and (
                method in IDENTITY_METHODS
                or (method == "operating_income_descriptor" and bool(facts.get("customer_descriptor")))
            ))
        ),
        "G14": bool(facts.get("pooled_while_vetoed")),
        "G15": in_true and _REFUND_WORD.search(row) is not None,
        "G16": in_true and _TAX_REFUND_WORD.search(row) is not None,
        "G17": in_true and bool(facts.get("own_transfer")),
    }
    if facts.get("known_financing") and in_true and method not in {"auto_lender_dealer_funding"}:
        guards["G5"] = not facts.get("payout_or_factoring")
    return guards


def _print(report: dict) -> None:
    def line(summary: dict) -> str:
        parts = [f"classification {summary['version']}", f"statements {summary['statements_with_credits']}",
                 f"verified {summary['verified_share']}%", f"$0-verified {summary['zero_verified_statements']}"]
        if summary.get("true_share") is not None:
            parts += [f"true {summary['true_share']}%", f"held {summary['held_share']}%",
                      f"$0-true {summary['zero_true_statements']}",
                      f"median true {summary['median_statement_true_share']}%"]
        parts.append(f"gated {summary['gated_share']}%")
        return "; ".join(parts)

    print(f"basis: {report['basis']}")
    print("base: " + line(report["base"]))
    for run in report["runs"]:
        print("after: " + line(run["summary"]) + f"; unmatched {run['accounts_unmatched']}")
        print("  left non_revenue: " + ", ".join(
            f"{cause} {value['rows']} rows/${value['dollars']:,.2f}/{value['statements']} st"
            for cause, value in run["left_non_revenue"].items()))
        print(f"  OQ2 BNPL rows: {run['bnpl_settlements']['rows']} in "
              f"{len(run['bnpl_settlements']['shapes'])} public shapes")
        print("  verified demotions: " + ", ".join(
            f"{cause} {value['rows']} rows/${value['dollars']:,.2f}/{value['statements']} st"
            for cause, value in run["verified_demotions"].items()))
        print("  eligible deposits: " + ", ".join(f"{name} {count}" for name, count in run["eligible_deposits"].items()))
        print("  lender credits by cause: " + ", ".join(
            f"{cause} {value['rows']} rows/${value['lender_credit_dollars']:,.2f}"
            for cause, value in run["lender_credit_moves_by_cause"].items()))
        print("  guards: " + (", ".join(f"{guard} FAILED {value['failures']}" for guard, value in run["guards"].items())
                              or "all hold"))


def _use_code_root(code_root: Path) -> bool:
    """Put the checkout's `analysis` package first on sys.path; False if another one is already loaded."""
    sys.path.insert(0, str(code_root.resolve()))
    import analysis

    return Path(analysis.__file__).resolve().is_relative_to(code_root.resolve())


def _read(path: Path) -> dict:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="re-classify the cache with one checkout's code")
    snap.add_argument("--data-dir", type=Path, help="the webapp data directory (read-only)")
    snap.add_argument("--jobs-db", type=Path, help="a copy of the tryout host's job store (read-only)")
    snap.add_argument("--out", type=Path, required=True, help="the snapshot to write (outside the repo)")
    snap.add_argument("--code-root", type=Path, default=ROOT, help="the checkout whose analysis package classifies")
    snap.add_argument("--limit", type=int, default=None, help="read only the first N analyses")
    snap.add_argument("--basis", choices=BASES, default="input",
                      help="input: every cached analysis input (the default); pdf: one analysis per source PDF")
    comp = commands.add_parser("compare", help="compare a base snapshot with later ones")
    comp.add_argument("--base", type=Path, required=True)
    comp.add_argument("--after", type=Path, required=True, action="append")
    comp.add_argument("--out", type=Path, required=True, help="the report to write (outside the repo)")
    samp = commands.add_parser("sample", help="draw the precision sample of a 5.6 snapshot (§14.5)")
    samp.add_argument("--snapshot", type=Path, required=True)
    samp.add_argument("--out", type=Path, required=True, help="the sample to write (outside the repo)")
    args = parser.parse_args(argv)

    if args.out.resolve().is_relative_to(ROOT.resolve()):
        print(f"refused: {args.out} is inside the repository; the census holds statement figures", file=sys.stderr)
        return 2
    if args.command == "snapshot":
        if (args.data_dir is None) == (args.jobs_db is None):
            print("refused: name exactly one of --data-dir and --jobs-db", file=sys.stderr)
            return 2
        if args.data_dir is not None and not (args.data_dir / "webapp.db").is_file():
            print(f"refused: {args.data_dir} holds no webapp.db", file=sys.stderr)
            return 2
        if not _use_code_root(args.code_root):
            print(f"refused: another analysis package is already loaded, not {args.code_root}", file=sys.stderr)
            return 2
        stats: dict = {}
        if args.data_dir is not None:
            accounts = cached_accounts(args.data_dir, args.limit, basis=args.basis, stats=stats)
        else:
            accounts = job_accounts(args.jobs_db, basis=args.basis, stats=stats)
        result = snapshot(accounts, basis=args.basis, basis_stats=stats)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(gzip.compress(json.dumps(result).encode("utf-8")))
        print(f"classification {result['classification_version']} ({result['basis']} basis): "
              f"{len(result['accounts'])} accounts; skipped: {result['skipped']}; basis: {result['basis_stats']}")
        return 0
    if args.command == "sample":
        sample = precision_sample(_read(args.snapshot))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(sample, indent=1) + "\n", encoding="utf-8")
        print("; ".join(f"{stratum} {len(rows)}" for stratum, rows in sample.items()))
        return 0
    try:
        report = compare(_read(args.base), [_read(path) for path in args.after])
    except BasisMismatch as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, default=list) + "\n", encoding="utf-8")
    _print(report)
    return 1 if any(run["guards"] for run in report["runs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
