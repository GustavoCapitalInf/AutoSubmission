"""Alias collision audit over the local artifact cache (spec section 5). Local only; never run in CI.

Every alias the classifier consults is replayed over the cached rows, in the classifier's order
(spec section 4.3): premium financing (the insurance rule), the known-payee matcher, the bank-name
and card-issuer context tables (the descriptor rules, which need loan or card wording), and the
potential registry. For each alias the audit reports the payee keys whose rows it wins, with row and
analysis counts and no descriptor text. A row counts as taken when the rule order gives it to that
alias: rows a rule ahead of the matcher keeps (a fee, a transfer, insurance and the other states of
section 4.3 steps 1-6) are counted but never taken.

A credit follows S2's credit rule (``_classify_credit_revenue``, spec section 4.4), which reads the credit's own
words whatever rule stored the row: after a return or reversal and an insurer, a financing group's payee takes it,
unless the payee is a payout-credit entity (PAYOUT_CREDIT_ENTITIES), and else the potential registry takes it out
of revenue. So a credit that the bank-name or card-context rule (debits only) matches, or a payee outside the
financing groups or a payout-credit entity, goes on to the potential registry.

A taken match needs review (``needs_review``) when the payee key may name someone else:
  * the alias is a single word and the key is not exactly that word;
  * the key holds a word that is not in the alias, not in the entity's name (nor a run-together form of
    either), not a channel or descriptor word (VOCAB) and not an organisation word (ORG_CUES);
  * the key shares no word with the alias at all.
A reviewed allow/deny file records the decisions. The audit fails when a denied pair still wins a row,
and --strict also fails while a match that needs review has no decision. With --before <an earlier report
of the same cache>, it also fails on every (entity, payee key) that takes fewer rows than before, leaving out
denied pairs: a ledger change that dropped or narrowed an alias must not take the entity's own rows with it.
Payee keys come from customer statements, so the review file and the reports stay outside the repository.

Usage, from the repository root:
    python -m tools.lender_alias_audit --data-dir <webapp_data> --review <file> --out <file> [--strict]
        [--limit N] [--before <earlier report>]

Exit codes: 0 no denied match, no lost match (and, with --strict, nothing undecided); 1 otherwise; 2 refused.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.classification_registry import (  # noqa: E402
    BANK_NAME_ALIASES,
    CARD_ISSUER_CONTEXT_ALIASES,
    PAYEE_GROUP_REGISTRIES,
    PAYOUT_CREDIT_ENTITIES,
    POTENTIAL_LENDER_ALIASES,
    PREMIUM_FINANCE_ALIASES,
)
from analysis.description_text import normalize_transaction_description as normalize  # noqa: E402
from analysis.flag_groups import FINANCING_STATES  # noqa: E402
from analysis.payee_matcher import AliasIndex, PayeeMatch  # noqa: E402
from tools.lender_ledger import _CARD_PAYMENT_WORDING, ORG_CUES  # noqa: E402

#: Stored states that a rule ahead of the known-payee matcher keeps (spec section 4.3 steps 2-6). POS and
#: ATM are not here: a known payee paid by card bypasses them (D8).
EARLIER_RULE_STATES = frozenset(
    {"nsf_or_return", "refund_or_reversal", "insurance", "fee", "transfer", "tax", "payroll", "utility"}
)
#: Stored states of a credit that S2's credit rule decides before it reads a payee: a return or reversal, and an
#: insurer. The rule reads a credit's own words, so a credit stored as a fee, a transfer, a tax, payroll or a
#: utility still reaches a financing payee and the potential registry.
EARLIER_CREDIT_RULE_STATES = frozenset({"nsf_or_return", "refund_or_reversal", "insurance"})
#: The state of the potential registry's pass (spec section 4.3 step 11; S2's credit rule reads it too).
POTENTIAL_STATE = "potential_lender"
#: S2's step-8 rules that decide a row before its bank-name rule (spec section 4.3 step 8): LOC, mortgage and
#: vehicle wording, as S2's _LINE_OF_CREDIT_PATTERNS, _MORTGAGE_PATTERNS and _VEHICLE_FINANCING_PATTERNS.
_DECIDED_BEFORE_BANK_NAME = (
    r"\bLOC\b|\bLINE OF CREDIT\b|\bMORTGAGES?\b"
    r"|\b(?:AUTO|CAR) (?:LOAN|LOANS|LEASE|FINANCE|FINANCING)\b"
    r"|\bVEHICLE (?:LOAN|LEASE|PAYMENT|PMT|PYMT|FINANCE|FINANCING)\b"
)
#: S2's step-8 rules that decide a row before its card-payment rule: the ones above, the statement bank's own
#: loan transfer and lease or rental wording (S2's _OWN_LOAN_TRANSFER_PATTERNS and _LEASE_RENTAL_PATTERNS).
_DECIDED_BEFORE_CARD = _DECIDED_BEFORE_BANK_NAME + (
    r"|\b(?:TRANSFER|TFR) TO (?:MY |YOUR )?LOAN\b|\bLOAN (?:TRANSFER|TFR)\b"
    r"|\bLEAS(?:E|ES|ED|ING)\b|(?<!PROPERTY )\bRENTALS?\b|\bEQUIPMENT (?:RENT|PAYMENT)\b"
)
#: S2's bank-name rule (D5): a listed bank with LOAN or LOANS (S2's _LOAN_WORD_PATTERNS; normalization has
#: already turned LN into LOAN), on a row that no earlier step-8 rule decided.
_LOAN_WORDING = re.compile(r"^(?!.*(?:" + _DECIDED_BEFORE_BANK_NAME + r")).*\bLOANS?\b")
#: S2's card-payment rule: a listed issuer with S2's card or payment wording (_CARD_PAYMENT_CONTEXT_PATTERNS,
#: the same words the validator requires of every CARD_ISSUER_ALIASES alias), on a row that no earlier
#: step-8 rule decided.
_CARD_WORDING = re.compile(r"^(?!.*(?:" + _DECIDED_BEFORE_CARD + r")).*" + _CARD_PAYMENT_WORDING.pattern)
#: Leading bank-channel words a payee key skips (the research payee index used the same rule).
_LEADING = re.compile(
    r"^(?:(?:CHECK ?CARD|CHECKCARD|PURCHASE|POS|DEBIT|CARD|ACH|WEB|PPD|CCD|TEL|ELECTRONIC|PREAUTHORIZED|"
    r"PRE AUTHORIZED|ONLINE|PAYMENT TO|PAYMENTS|PAYMENT|PMTS|PYMTS|PMT|BILL ?PAY(?:MENT)?|WITHDRAWAL|EXTERNAL|"
    r"RECURRING|AUTOPAY|AUTO PAY|DDA|TRANSACTION|WITHDRWL|WD|DIRECT DEBIT|DIRECT DEB|BUSINESS PAD|PAD|EFT|"
    r"PREAUTH|MISC|ELECTRONIC PMT|ELEC|SEND|TO|FROM|IAT|CORP|ACH DEBIT|ACH PMT|ACH PAYMENT|AUTHORIZED ON|"
    r"RECURRING PAYMENT|[0-9]+|[A-Z]?[0-9][A-Z0-9]*)\s+)+"
)
_CHASE_ORIGINATOR = re.compile(
    r"\bORIG CO NAME (.+?)(?: ORIG ID| DESC DATE| CO ENTRY| SEC| TRACE| EED| IND ID| IND NAME|$)"
)
_KEY_STOP = frozenset({
    "DES", "ID", "INDN", "ENTRY", "REF", "TRACE", "SEC", "ORIG", "CKCD", "CT", "CONF", "TRN", "IND", "EED",
    "PAYMENT", "PMT", "PYMT", "PAYMT", "DEBIT", "ACH", "WEB", "CCD", "PPD", "TEL", "PURCHASE", "AUTOPAY",
    "EPAY", "EPAYMENT", "DIRECT", "WITHDRAWAL", "SETTLEMENT", "COLLECTION", "DEBITS", "REMITTANCE", "XFER",
})
#: Channel and descriptor words that name no one: a payee key may hold them beside the payee's name.
VOCAB = frozenset("""
ACCEPTANCE ACH ADV ADVANCE ADVANCES AND AT AUTHORIZATION AUTHORIZED AUTO AUTOMATIQUE AUTOPAY BANK BANKING
BILL BILLPAY BUS BUSINESS BY CANADA CAP CAPITAL CARD CC CCD CHG CO COLL COLLECTION COLLECTIONS COM COMMERCIAL
COMPTE CORP CR CRD CREDIT D DB DD DEBIT DES DIRECT DIV DIVERS DPA DRAFT DRAFTS EDI EFT ENT ENTREPRISE ENTRY
EPAY EPAYMENT EQUIP EQUIPMENT FIN FINANCE FINANCIAL FINANCING FINL FOR FUND FUNDING GROUP HOLDINGS IN INC
INSTALLMENT INSTL INTEREST INTERNET ITEMS LEASE LEASING LENDING LL LLC LOAN LOANS LP LTD MC MCA MISC MORTGAGE
MOTOR MSP MTG NA NAME OF ON ONLINE ORIG PAD PAY PAYMENT PAYMENTS PAYOUT PMT PMTS PPD PRE PREAUTH PRELEVEMENT
PRET PROCEEDS PROGRAM PYMNT PYMNTS PYMT RECURRING REMIT RETAIL RLS SCHEDULED SERVICES SERVICING SVC SVCS TEL
THE TYPE US USA WEB WITHDRAWAL
""".split())
#: The payee key of a descriptor in which no name word survives: a fixed placeholder, never descriptor text
#: (which may carry an account number). ``needs_review`` flags it, so every such match gets a decision.
NO_PAYEE_WORDS = "<no payee words>"


@dataclass(frozen=True)
class AuditPass:
    """One rule of the classifier that reads a registry: its index and the wording it needs, if any."""

    index: AliasIndex
    needs: re.Pattern[str] | None = None


@dataclass(frozen=True)
class CachedRow:
    analysis: str
    description: str
    amount: float
    stored: str
    posted: bool = True


def payee_key(text: str) -> str:
    """The counterparty key of a normalized descriptor: up to three name words after the channel words, or
    NO_PAYEE_WORDS when none survives."""
    originator = _CHASE_ORIGINATOR.search(text)
    base = _LEADING.sub("", (originator.group(1) if originator else text) + " ").strip()
    words: list[str] = []
    for word in base.split():
        if word in _KEY_STOP or word.startswith("XXXX"):
            if words:
                break
            continue
        if any(char.isdigit() for char in word):
            continue
        words.append(word)
        if len(words) == 3:
            break
    return " ".join(words) or NO_PAYEE_WORDS


def default_passes() -> tuple[AuditPass, ...]:
    """The registries the classifier reads, in its rule order (spec section 4.3 steps 4, 7, 8 and 11)."""
    return (
        AuditPass(AliasIndex({"premium_financing": PREMIUM_FINANCE_ALIASES}, run_together=False)),
        AuditPass(AliasIndex(PAYEE_GROUP_REGISTRIES)),
        AuditPass(AliasIndex({"bank_name": BANK_NAME_ALIASES}, run_together=False), _LOAN_WORDING),
        AuditPass(AliasIndex({"card_context": CARD_ISSUER_CONTEXT_ALIASES}, run_together=False), _CARD_WORDING),
        AuditPass(AliasIndex({POTENTIAL_STATE: POTENTIAL_LENDER_ALIASES}, run_together=False)),
    )


def takes(state: str, row: CachedRow, entity: str = "") -> bool:
    """Whether the classifier's rule order gives the row to ``entity``'s alias of ``state`` (spec sections 4.3,
    4.4). A credit follows S2's credit rule: a financing group's payee takes it unless ``entity`` is a payout-credit
    entity (PAYOUT_CREDIT_ENTITIES), and the potential registry takes it out of revenue."""
    if not row.posted or row.stored in ("nsf_or_return", "refund_or_reversal"):
        return False
    if state == "premium_financing":
        return True
    if row.amount > 0:
        if row.stored in EARLIER_CREDIT_RULE_STATES:
            return False
        if state in PAYEE_GROUP_REGISTRIES:
            return state in FINANCING_STATES and entity not in PAYOUT_CREDIT_ENTITIES
        return state == POTENTIAL_STATE
    if row.stored in EARLIER_RULE_STATES:
        return False
    if state in PAYEE_GROUP_REGISTRIES:
        return row.amount < 0 or state in FINANCING_STATES
    return row.amount < 0 and row.stored not in ("pos", "atm")


def _decides_credit(audit_pass: AuditPass, match: PayeeMatch) -> bool:
    """Whether the rule of ``audit_pass`` decides a credit it matches, so that no later rule reads the credit. The
    bank-name and card-context rules (the passes that need wording) read debits only, and S2's credit rule reads a
    payee only in a financing group and never a payout-credit entity's: the credit goes on to the potential
    registry."""
    if audit_pass.needs is not None:
        return False
    if match.state in PAYEE_GROUP_REGISTRIES:
        return match.state in FINANCING_STATES and match.entity not in PAYOUT_CREDIT_ENTITIES
    return True


def _classification_lists(node) -> Iterator[list]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "classifications" and isinstance(value, list):
                yield value
            else:
                yield from _classification_lists(value)
    elif isinstance(node, list):
        for value in node:
            yield from _classification_lists(value)


def cached_rows(data_dir: Path, limit: int | None = None) -> Iterator[CachedRow]:
    """Every row of the latest cached analysis of each input. Opens the cache database read-only and never
    writes to the data directory."""
    database = data_dir / "webapp.db"
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    try:
        latest = connection.execute(
            "SELECT a.input_sha256, a.artifact_path FROM artifact_cache a JOIN ("
            " SELECT input_sha256, MAX(created_at) AS newest FROM artifact_cache"
            " WHERE stage = 'analysis' GROUP BY input_sha256) b"
            " ON a.input_sha256 = b.input_sha256 AND a.created_at = b.newest"
            " WHERE a.stage = 'analysis' ORDER BY a.input_sha256"
        ).fetchall()
    finally:
        connection.close()
    for number, (sha, relative) in enumerate(latest):
        if limit is not None and number >= limit:
            return
        try:
            payload = json.loads((data_dir / "artifacts" / relative).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for rows in _classification_lists(payload.get("artifact")):
            for row in rows:
                amount = row.get("amount") if isinstance(row, dict) else None
                if isinstance(amount, (int, float)):
                    yield CachedRow(sha, str(row.get("original_description") or ""), float(amount),
                                    str(row.get("classification") or "other"), row.get("is_posted") is not False)


def audit(rows: Iterable[CachedRow], passes: tuple[AuditPass, ...]) -> dict:
    """state -> alias -> {entity, keys: {payee key: {rows, taken_rows, debit_rows, credit_rows, analyses}}}.
    The first pass that matches a row claims it, as the first rule that matches does, except that a credit goes on
    past a pass whose rule does not decide it (``_decides_credit``). No descriptor text."""
    found: dict = {}
    analyses: dict = defaultdict(set)
    for row in rows:
        text = normalize(row.description)
        for audit_pass in passes:
            if audit_pass.needs is not None and not audit_pass.needs.search(text):
                continue
            match = audit_pass.index.match(text)
            if match is None:
                continue
            key = payee_key(text)
            entry = found.setdefault(match.state, {}).setdefault(match.alias, {"entity": match.entity, "keys": {}})
            counts = entry["keys"].setdefault(
                key, {"rows": 0, "taken_rows": 0, "debit_rows": 0, "credit_rows": 0, "analyses": 0})
            counts["rows"] += 1
            counts["taken_rows"] += int(takes(match.state, row, match.entity))
            counts["debit_rows" if row.amount < 0 else "credit_rows"] += 1
            analyses[(match.state, match.alias, key)].add(row.analysis)
            counts["analyses"] = len(analyses[(match.state, match.alias, key)])
            if row.amount <= 0 or _decides_credit(audit_pass, match):
                break
    return {state: dict(sorted(aliases.items())) for state, aliases in sorted(found.items())}


def _fires(entry: dict, alias: str, entity: str, key: str) -> bool:
    return entry.get("key") == key and (
        entry.get("alias") is None or normalize(entry["alias"]) == normalize(alias)
    ) and (entry.get("entity") is None or entry["entity"] == entity)


def _joined_runs(words: list[str]) -> set[str]:
    """Every run-together form of two or more consecutive words."""
    return {"".join(words[start:end]) for start in range(len(words)) for end in range(start + 2, len(words) + 1)}


def needs_review(alias: str, entity: str, key: str) -> bool:
    """Whether the payee key of a taken match may name someone other than the entity (see the module doc)."""
    alias_words = normalize(alias).split(" ")
    name_words = normalize(entity).split(" ")
    key_words = key.split(" ")
    if len(alias_words) == 1 and key != alias_words[0]:
        return True
    known = set(alias_words) | set(name_words) | _joined_runs(alias_words) | _joined_runs(name_words)
    if any(word not in known and word not in VOCAB and word not in ORG_CUES for word in key_words):
        return True
    return not set(alias_words) & set(key_words) and "".join(alias_words) not in key.replace(" ", "")


def review(report: dict, decisions: dict) -> tuple[list[dict], list[dict]]:
    """(denied, undecided): the taken matches a deny decision names, and the taken matches that need review and
    have no decision. Each is {state, alias, entity, key, rows, taken_rows, analyses, needs_review}."""
    denied: list[dict] = []
    undecided: list[dict] = []
    for state, aliases in report.items():
        for alias, entry in aliases.items():
            for key, counts in entry["keys"].items():
                if not counts["taken_rows"]:
                    continue
                row = {"state": state, "alias": alias, "entity": entry["entity"], "key": key, "rows": counts["rows"],
                       "taken_rows": counts["taken_rows"], "analyses": counts["analyses"],
                       "needs_review": needs_review(alias, entry["entity"], key)}
                if any(_fires(d, alias, entry["entity"], key) for d in decisions.get("deny", [])):
                    denied.append(row)
                elif row["needs_review"] and not any(
                        _fires(a, alias, entry["entity"], key) for a in decisions.get("allow", [])):
                    undecided.append(row)
    return denied, undecided


def _taken_by_entity(report: dict, decisions: dict | None) -> dict[tuple[str, str], int]:
    """Taken rows per (entity, payee key); with ``decisions``, the rows of denied pairs are left out."""
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for aliases in report.values():
        for alias, entry in aliases.items():
            for key, counts in entry["keys"].items():
                if decisions is not None and any(
                        _fires(d, alias, entry["entity"], key) for d in decisions.get("deny", [])):
                    continue
                totals[(entry["entity"], key)] += counts["taken_rows"]
    return totals


def lost_matches(before: dict, after: dict, decisions: dict) -> list[dict]:
    """The (entity, payee key) pairs that take fewer rows in ``after`` than in ``before`` (two reports of the same
    cache), leaving out the rows of denied pairs: the rows a ledger change took from an entity without a
    decision. Each is {entity, key, before, after}, in entity and key order."""
    was = _taken_by_entity(before, decisions)
    now = _taken_by_entity(after, None)
    return [{"entity": entity, "key": key, "before": count, "after": now.get((entity, key), 0)}
            for (entity, key), count in sorted(was.items()) if now.get((entity, key), 0) < count]


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, required=True, help="the webapp data directory (read-only)")
    parser.add_argument("--review", type=Path, required=True, help="reviewed allow/deny file (outside the repo)")
    parser.add_argument("--out", type=Path, required=True, help="the report to write (outside the repo)")
    parser.add_argument("--strict", action="store_true",
                        help="also fail while a match that needs review has no decision")
    parser.add_argument("--limit", type=int, default=None, help="read only the first N analyses")
    parser.add_argument("--before", type=Path, default=None,
                        help="an earlier report of the same cache (outside the repo): fail on rows an entity lost")
    args = parser.parse_args(argv)
    for local in (args.review, args.out, *([args.before] if args.before else [])):
        if _inside(local, ROOT):
            print(f"refused: {local} is inside the repository; payee keys come from statements", file=sys.stderr)
            return 2
    if not (args.data_dir / "webapp.db").is_file():
        print(f"refused: {args.data_dir} holds no webapp.db", file=sys.stderr)
        return 2
    decisions = json.loads(args.review.read_text(encoding="utf-8"))
    report = audit(cached_rows(args.data_dir, args.limit), default_passes())
    denied, undecided = review(report, decisions)
    lost = []
    if args.before is not None:
        lost = lost_matches(json.loads(args.before.read_text(encoding="utf-8"))["aliases"], report, decisions)
    taken = [(alias, entry["entity"], key) for aliases in report.values() for alias, entry in aliases.items()
             for key, counts in entry["keys"].items() if counts["taken_rows"]]
    flagged = sum(needs_review(alias, entity, key) for alias, entity, key in taken)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"aliases": report, "denied": denied, "undecided": undecided, "lost": lost},
                                   indent=2, sort_keys=True) + "\n", encoding="utf-8")
    keys = sum(len(entry["keys"]) for aliases in report.values() for entry in aliases.values())
    print(f"aliases that matched: {sum(len(aliases) for aliases in report.values())}; payee keys: {keys}; "
          f"taken matches: {len(taken)}, of which need review: {flagged}; denied matches: {len(denied)}; "
          f"undecided: {len(undecided)}")
    for row in denied:
        print(f"COLLISION {row['alias']!r} ({row['entity']}, {row['state']}) matches payee key {row['key']!r}: "
              f"{row['taken_rows']} taken rows in {row['analyses']} analyses")
    if args.before is not None:
        print(f"lost matches: {len(lost)}")
        for row in lost:
            print(f"LOST {row['entity']!r} payee key {row['key']!r}: {row['before']} taken rows before, "
                  f"{row['after']} now")
    return 1 if denied or lost or (args.strict and undecided) else 0


if __name__ == "__main__":
    raise SystemExit(main())
