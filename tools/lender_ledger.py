"""The curated lender registry ledger (contract C10): its schema, its validator and its privacy review.

The lender research is consolidated into one entity per company OUTSIDE the code, by the orchestrator's
research workflow (consolidation, an adversarial check per entity, a completeness critic), and committed as
``docs/lender-registry-ledger.json``. This module never infers a name, a group or an alias from research
output. It reads the ledger and says what is wrong with it; ``tools/build_lender_registry.py`` renders the
registry and the evidence ledger from a ledger that passes.

The validator applies:
  * every rule contract C10 lists;
  * spec section 5's brand rule (a brand that also sells goods is an alias only with payment or loan wording);
  * the privacy constraints: no digit run of five or more outside a URL, unless today's registry already
    holds that alias; sources and "where looked" entries are public URLs without a query string, credentials
    or a local, private or undotted host;
  * contract C2's context-only tables: no entity of the card, card-issuer, bank-name or premium-finance
    groups is under review, and every card-payment alias carries card or payment wording;
  * the owner's premium-finance ruling: a premium-finance alias repeats a hand-kept insurer's alias only when
    PREMIUM_FINANCE_INSURER_ALIASES holds it;
  * the owner's payout-credit ruling: each name in PAYOUT_CREDIT_ENTITIES is an admitted ledger entity of a
    group whose credits D1 treats as financing proceeds (analysis.flag_groups.FINANCING_STATES);
  * spec section 9's rule that an entity of today's registry changes place, or loses an alias, only with a
    reason: a sentence of its notes that starts "Move:" (today's registry is read from git at
    BASELINE_REVISION); an entity the owner merged into a ledger entity (MERGED_REGISTRY_ENTITIES) is held by
    that entity, whose notes give the reason; an alias the owner ruled names another company
    (REATTRIBUTED_REGISTRY_ALIASES) is held by that company's ledger entity, the only entity the registry may read
    it as, and is neither lost nor the first alias of today's entity.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import ipaddress
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.description_text import normalize_transaction_description as normalize  # noqa: E402
from analysis.flag_groups import FINANCING_STATES  # noqa: E402
from analysis.payee_matcher import RUN_TOGETHER_MIN_LENGTH, AliasIndex, registry_match  # noqa: E402

SCHEMA = 1
LEDGER_PATH = ROOT / "docs" / "lender-registry-ledger.json"
EMPTY_LEDGER: dict = {"schema": SCHEMA, "entities": []}

#: (group, table, heading): the ledger's groups, the contract C2 table each renders into, and the heading
#: the GENERATED block and the evidence ledger print, in their order.
TABLES: tuple[tuple[str, str, str], ...] = (
    ("confirmed_lender", "LENDER_ALIASES", "Lenders: MCA and revenue-based funders, equipment financing"),
    ("alternative_position", "ALTERNATIVE_POSITION_ALIASES", "Alternative positions"),
    ("line_of_credit", "LINE_OF_CREDIT_ALIASES", "Lines of credit"),
    ("credit_card_payment", "CARD_ISSUER_ALIASES", "Credit cards: aliases that carry card-payment wording"),
    ("card_issuer_context", "CARD_ISSUER_CONTEXT_ALIASES",
     "Card issuers: bare names, used only with card-payment wording"),
    ("vehicle_financing", "VEHICLE_FINANCE_ALIASES", "Vehicle loans & leases"),
    ("mortgage", "MORTGAGE_SERVICER_ALIASES", "Mortgages"),
    ("lease_or_rental", "LEASE_RENTAL_ALIASES", "Leases & rentals"),
    ("personal_loan", "PERSONAL_LOAN_ALIASES", "Personal loans"),
    ("floor_plan_financing", "FLOOR_PLAN_ALIASES", "Floor plan"),
    ("factoring", "FACTORING_ALIASES", "Factoring"),
    ("debt_relief", "DEBT_RELIEF_ALIASES",
     "Debt relief: debt-settlement account processors and debt-relief firms (flagged, never lender math)"),
    ("premium_financing", "PREMIUM_FINANCE_ALIASES",
     "Premium financing: premium-finance payees, read only by the insurance rule"),
    ("bank_name", "BANK_NAME_ALIASES", "Bank names: bank loans (D5)"),
    ("potential_lender", "POTENTIAL_LENDER_ALIASES", "Potential lenders: review, never counted"),
)
GROUPS = tuple(group for group, _table, _heading in TABLES)
TABLE_OF_GROUP = {group: table for group, table, _heading in TABLES}
#: The known-payee matcher's registries, in contract C2's PAYEE_GROUP_REGISTRIES order.
PAYEE_STATES = (
    "confirmed_lender", "alternative_position", "line_of_credit", "vehicle_financing", "mortgage",
    "personal_loan", "floor_plan_financing", "factoring", "lease_or_rental", "credit_card_payment",
)
STATUSES = ("admitted", "review", "owner_ruling", "rejected")
#: The statuses rendered into a table: admitted into its group's table, review into the potential table.
RENDERED = frozenset({"admitted", "review"})
ADMITTING_VERDICTS = frozenset({"upheld", "corrected"})
FIELDS = ("entity", "group", "business_type", "aliases", "status", "short_alias_reason", "evidence",
          "verdicts", "where_looked", "notes")
_ALIAS_CHARACTERS = re.compile(r"[A-Z0-9 &]+")
#: An alias of this many characters or fewer (spaces not counted) needs the entity's short_alias_reason.
SHORT_ALIAS = 4
#: C10: an alias made only of these words names no company.
GENERIC_WORDS = frozenset("""
ACH ADVANCE ADVANCES AND AUTO BANK BUSINESS CAPITAL CARD CO COMPANY CORP CORPORATION CREDIT DEBIT EQUIPMENT
FINANCE FINANCIAL FINANCING FUND FUNDING FUNDS GROUP HOLDINGS INC INSURANCE LEASE LEASING LENDER LENDING LLC
LOAN LOANS LTD MCA MERCHANT MORTGAGE OF PAYMENT PAYMENTS PMT SERVICES SERVICING SOLUTIONS THE
DEBT RELIEF SETTLEMENT CONSOLIDATION RESOLUTION NEGOTIATION PROGRAM LAW
""".split())
#: Words that make a name an organisation's name. A name without one is read by a person before a commit.
ORG_CUES = frozenset("""
ACCEPTANCE ADVANCE BANK CAPITAL CO CORP CORPORATION CREDIT FACTORING FINANCE FINANCIAL FUND FUNDING GROUP
HOLDINGS INC LEASING LENDING LLC LOANS LTD MORTGAGE PARTNERS SERVICES SERVICING VENTURES
""".split())
_LONG_DIGITS = re.compile(r"\d{5,}")
#: What a message or a printed line shows in place of a run of five or more digits: the validator's messages,
#: the move lines and the privacy review never quote such a run (the numbered company's number).
WITHHELD = "(withheld: a run of digits)"
_URL_SCHEME = re.compile(r"https?://")
#: The groups whose tables the classifier reads only with context: card or payment wording, loan wording, or
#: the insurance rule. None of their entities is ever "review", because the potential tier (where C10 renders
#: every review entity) reads its aliases with no context at all.
CONTEXT_ONLY_GROUPS = frozenset({"credit_card_payment", "card_issuer_context", "bank_name", "premium_financing"})
#: The hand-kept insurer table. A premium-finance alias may repeat one of its aliases only on the owner's
#: ruling (``Rules.premium_insurer_aliases``, PREMIUM_FINANCE_INSURER_ALIASES).
INSURER_TABLE = "INSURANCE_PROVIDER_ALIASES"
#: The wording of S2's card-payment rule (spec section 4.3 step 8). C10: the aliases of credit_card_payment are
#: "already payment-specific", so each carries this wording; a bare issuer name belongs in card_issuer_context.
_CARD_PAYMENT_WORDING = re.compile(
    r"\b(?:CREDIT CARD|CRCARD|CRD|CARD|CARDMEMBER|AUTOPAY|AUTO PAY|EPAYMENT|EPAY|PAYMENT|PMT|PYMT)\b"
)
#: Spec section 9: the reason for a move from today's registry is a sentence of the ledger entity's notes that
#: starts with this marker. Any other text in notes never excuses a move.
MOVE_MARKER = "Move:"
_MOVE_REASON = re.compile(r"(?:^|(?<=[.!?;])\s+)" + re.escape(MOVE_MARKER) + r"\s*(\S.*)", re.DOTALL)
#: The Move: sentence names a reason: a word before the sentence ends ("Move: ." gives no reason).
_WORDED_SENTENCE = re.compile(r"[^.!?]*\w")
#: The last commit that changed today's registry. Today's three lists are read from git at this revision, so
#: the check survives S2 deleting the legacy lists and no second copy of them is ever committed.
BASELINE_REVISION = "693fd009c5c96a838ef47b61ba5b65a610ea5ba1"
BASELINE_TABLES = ("CONFIRMED_LENDER_ALIASES", "POTENTIAL_LENDER_ALIASES", "LEASE_PROVIDER_ALIASES")
#: The classification state each of today's lists gives its rows (spec section 4.1 retires the lease state).
BASELINE_STATE = {
    "CONFIRMED_LENDER_ALIASES": "confirmed_lender",
    "POTENTIAL_LENDER_ALIASES": "potential_lender",
    "LEASE_PROVIDER_ALIASES": "lease_or_equipment_financing",
}
#: The places an entity of today's lists may take without a reason: its own place, or, for the retired
#: lease state, the ones spec section 4.1 names.
UNRULED_PLACES = {
    "CONFIRMED_LENDER_ALIASES": frozenset({"confirmed_lender"}),
    "POTENTIAL_LENDER_ALIASES": frozenset({"potential_lender"}),
    "LEASE_PROVIDER_ALIASES": frozenset({"confirmed_lender", "lease_or_rental", "vehicle_financing"}),
}


@dataclass(frozen=True)
class Evidence:
    source: str
    note: str


@dataclass(frozen=True)
class Verdict:
    round: str
    verdict: str
    confirmed: bool


@dataclass(frozen=True)
class LedgerEntity:
    index: int
    entity: str
    group: str
    business_type: str
    aliases: tuple[str, ...]
    status: str
    short_alias_reason: str | None
    evidence: tuple[Evidence, ...]
    verdicts: tuple[Verdict, ...]
    where_looked: tuple[str, ...]
    notes: str

    @property
    def table(self) -> str | None:
        """The C2 table the entity renders into, or None."""
        if self.status == "admitted":
            return TABLE_OF_GROUP[self.group]
        if self.status == "review":
            return TABLE_OF_GROUP["potential_lender"]
        return None

    @property
    def place(self) -> str:
        """Where the entity's rows go: its group, "potential_lender" for review, or "no table"."""
        if self.status == "admitted":
            return self.group
        if self.status == "review":
            return "potential_lender"
        return "no table"


@dataclass(frozen=True)
class Rules:
    """The hand-kept inputs of the validator, all read from ``analysis/classification_registry.py``."""

    owner_named: Mapping[str, tuple[tuple[str, str], ...]]
    platforms: frozenset[str]
    brands: frozenset[str]
    hand_kept: Mapping[str, Mapping[str, tuple[str, ...]]]
    baseline: Mapping[str, Mapping[str, tuple[str, ...]]]
    #: Normalized premium-finance spellings that may equal a hand-kept insurer alias (owner ruling).
    premium_insurer_aliases: frozenset[str]
    #: Entity of today's registry -> the ledger entity that absorbs it (owner ruling).
    merged: Mapping[str, str]
    #: Ledger entities whose credits are the account holder's own sales, not financing proceeds (owner ruling).
    payout_credit: tuple[str, ...]
    #: Alias of today's registry -> the ledger entity of the other company it names (owner ruling).
    reattributed: Mapping[str, str]
    #: Ledger entity -> its printed forms in the bank's field order (owner ruling 2026-09-27, classification 5.3).
    field_order: Mapping[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)


@dataclass(frozen=True)
class Move:
    """An entity of today's registry whose place or aliases the ledger changes, that the owner merged into
    ``holder``, or an alias of which the owner gave to another company (``reattributed``: (alias, ledger entity)
    pairs). ``reason`` is the text of the holder's "Move:" sentence, or "" when its notes have none."""

    entity: str
    table: str
    was: str
    now: str
    lost: int
    holder: str
    reason: str
    merged: bool = False
    reattributed: tuple[tuple[str, str], ...] = ()


# --- reading -------------------------------------------------------------------------------------------------


def read_ledger(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def ledger_digest(data: object) -> str:
    """sha256 of the ledger's canonical JSON: the same on every checkout, whatever its line endings."""
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def mask_digit_runs(text: str) -> str:
    """``text`` with every run of five or more digits replaced by WITHHELD."""
    return _LONG_DIGITS.sub(WITHHELD, text)


def _shown(value: object) -> str:
    """The repr of a name or a value for a message, or WITHHELD when it carries a run of five or more digits."""
    text = repr(value)
    return WITHHELD if _LONG_DIGITS.search(text) else text


def _public_url(text: str) -> bool:
    """An http(s) URL without whitespace, a query string, a fragment, a '|' (it would split an evidence-ledger
    row) or credentials (userinfo), on a public host: a global IP address, or a dotted name that is not
    localhost and whose last label starts with a letter (so no private, loopback, undotted or numeric host)."""
    if not _URL_SCHEME.match(text) or any(char.isspace() or char in "?#|" for char in text):
        return False
    try:
        parts = urlsplit(text)
        host, _port = parts.hostname, parts.port
    except ValueError:
        return False
    if not host or "@" in parts.netloc:
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    labels = host.split(".")
    return len(labels) >= 2 and all(labels) and labels[-1] != "localhost" and labels[-1][0].isalpha()


def _texts(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _filled(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _shape_problems(index: int, record: object) -> list[str]:
    where = f"entity {index}"
    if not isinstance(record, dict):
        return [f"{where} is not an object"]
    missing = [name for name in FIELDS if name not in record]
    unknown = sorted(set(record) - set(FIELDS))
    problems = []
    if missing:
        problems.append(f"{where}: missing field(s) {', '.join(missing)}")
    if unknown:
        problems.append(f"{where}: unknown field(s) {mask_digit_runs(', '.join(unknown))}")
    if problems:
        return problems
    checks = (
        (_filled(record["entity"]), "entity is not a non-empty string"),
        (record["group"] in GROUPS, f"group {_shown(record['group'])} is not a C10 group"),
        (_filled(record["business_type"]), "business_type is not a non-empty string"),
        (_texts(record["aliases"]), "aliases is not a list of strings"),
        (record["status"] in STATUSES, f"status {_shown(record['status'])} is not one of {', '.join(STATUSES)}"),
        (record["short_alias_reason"] is None or _filled(record["short_alias_reason"]),
         "short_alias_reason is neither null nor a non-empty string"),
        (isinstance(record["evidence"], list), "evidence is not a list"),
        (isinstance(record["verdicts"], list), "verdicts is not a list"),
        (_texts(record["where_looked"]), "where_looked is not a list of strings"),
        (isinstance(record["notes"], str), "notes is not a string"),
    )
    problems = [f"{where}: {message}" for ok, message in checks if not ok]
    for number, item in enumerate(record["evidence"] if isinstance(record["evidence"], list) else []):
        if not (isinstance(item, dict) and set(item) == {"source", "note"}
                and all(isinstance(value, str) for value in item.values())):
            problems.append(f"{where}: evidence {number} is not an object of the strings 'source' and 'note'")
    for number, item in enumerate(record["verdicts"] if isinstance(record["verdicts"], list) else []):
        if not (isinstance(item, dict) and set(item) == {"round", "verdict", "confirmed"}
                and isinstance(item["round"], str) and isinstance(item["verdict"], str)
                and isinstance(item["confirmed"], bool)):
            problems.append(f"{where}: verdict {number} is not an object of the strings 'round' and 'verdict' "
                            f"and a true/false 'confirmed'")
    return problems


def parse_ledger(data: object) -> tuple[list[LedgerEntity], list[str]]:
    """The ledger's entities, or the problems with its shape (C10's schema)."""
    if not isinstance(data, dict) or set(data) != {"schema", "entities"}:
        return [], ["the ledger is not an object with exactly the keys 'schema' and 'entities'"]
    if data["schema"] is True or data["schema"] != SCHEMA:
        return [], [f"the ledger schema is {_shown(data['schema'])}; this validator reads schema {SCHEMA}"]
    if not isinstance(data["entities"], list):
        return [], ["the ledger's 'entities' is not a list"]
    entities: list[LedgerEntity] = []
    problems: list[str] = []
    for index, record in enumerate(data["entities"]):
        found = _shape_problems(index, record)
        if found:
            problems.extend(found)
            continue
        entities.append(LedgerEntity(
            index=index,
            entity=record["entity"],
            group=record["group"],
            business_type=record["business_type"],
            aliases=tuple(record["aliases"]),
            status=record["status"],
            short_alias_reason=record["short_alias_reason"],
            evidence=tuple(Evidence(item["source"], item["note"]) for item in record["evidence"]),
            verdicts=tuple(Verdict(item["round"], item["verdict"], item["confirmed"]) for item in record["verdicts"]),
            where_looked=tuple(record["where_looked"]),
            notes=record["notes"],
        ))
    return entities, problems


def render_tables(entities: list[LedgerEntity]) -> dict[str, dict[str, tuple[str, ...]]]:
    """Every C2 table, in TABLES order: entities in name order, aliases in ledger order."""
    tables: dict[str, dict[str, tuple[str, ...]]] = {table: {} for _group, table, _heading in TABLES}
    for entity in sorted(entities, key=lambda e: (e.entity.casefold(), e.entity)):
        if entity.table is not None:
            tables[entity.table][entity.entity] = tuple(dict.fromkeys(entity.aliases))
    return tables


#: 5.3 (owner ruling 2026-09-27): the flag groups whose review entities take their flag on debits, marked
#: unconfirmed (REVIEW_FLAG_ENTITIES). A review entity of the lender, potential, alternative-position or factoring
#: group keeps the potential tier: each has a plausible counted reading.
ROUTED_REVIEW_GROUPS = ("vehicle_financing", "mortgage", "lease_or_rental", "personal_loan", "debt_relief")


def review_flag_entities(entities: list[LedgerEntity]) -> dict[str, str]:
    """5.3 (owner ruling 2026-09-27): entity -> group of each review entity of a routed flag group whose business
    type is known, in name order. The classifier sends such an entity's debits to its flag, marked unconfirmed; its
    aliases stay in POTENTIAL_LENDER_ALIASES, so its credits keep the potential tier's exclusion. A business type
    starting 'unknown' (a payee read from a payment code alone) is never routed."""
    routed = [
        entity for entity in entities
        if entity.status == "review" and entity.group in ROUTED_REVIEW_GROUPS
        and not entity.business_type.startswith("unknown")
    ]
    return {entity.entity: entity.group for entity in sorted(routed, key=lambda e: (e.entity.casefold(), e.entity))}


# --- today's registry (spec section 9) ------------------------------------------------------------------------


def baseline_from_source(source: str) -> dict[str, dict[str, tuple[str, ...]]]:
    """Today's three lists (BASELINE_TABLES) from a registry source, read without importing it."""
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            name, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        else:
            continue
        if name in BASELINE_TABLES:
            found[name] = ast.literal_eval(value)
    missing = [name for name in BASELINE_TABLES if name not in found]
    if missing:
        raise ValueError(f"the baseline source has no {', '.join(missing)}")
    return {name: {entity: tuple(aliases) for entity, aliases in found[name].items()} for name in BASELINE_TABLES}


def load_baseline(revision: str = BASELINE_REVISION) -> dict[str, dict[str, tuple[str, ...]]]:
    """Today's registry as it stood at ``revision``, read from git."""
    shown = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{revision}:analysis/classification_registry.py"],
        check=True, capture_output=True,
    )
    return baseline_from_source(shown.stdout.decode("utf-8"))


def move_reason(notes: str) -> str:
    """The reason the ledger records for a move from today's registry: the text after the first sentence of
    ``notes`` that starts with MOVE_MARKER, or "" when no sentence does or that sentence holds no word."""
    found = _MOVE_REASON.search(notes)
    reason = found.group(1).strip() if found else ""
    return reason if _WORDED_SENTENCE.match(reason) else ""


def _holders(entities: list[LedgerEntity]) -> dict[str, LedgerEntity]:
    held: dict[str, LedgerEntity] = {}
    for entity in entities:
        for alias in entity.aliases:
            held.setdefault(normalize(alias), entity)
    return held


def _by_name(entities: list[LedgerEntity]) -> dict[str, LedgerEntity]:
    """Each entity name's first ledger entity (a name used twice is refused by the name rules)."""
    named: dict[str, LedgerEntity] = {}
    for entity in entities:
        named.setdefault(entity.entity, entity)
    return named


def baseline_moves(entities: list[LedgerEntity], baseline: Mapping[str, Mapping[str, tuple[str, ...]]],
                   merged: Mapping[str, str] | None = None,
                   reattributed: Mapping[str, str] | None = None) -> tuple[list[Move], list[tuple[str, str]]]:
    """(moves, missing). A move is an entity of today's lists whose place changes or that loses an alias; the
    ledger entity holding its first alias (else most of its aliases, else its name) decides. An entity the owner
    merged (``merged``, MERGED_REGISTRY_ENTITIES) is held by its target ledger entity instead, and is always a
    move. An alias the owner gave to another company (``reattributed``, REATTRIBUTED_REGISTRY_ALIASES) is left out
    of its entity's aliases: it decides nothing and is never lost, and its entity is always a move that shows it.
    Missing are the (table, entity) pairs of today's lists whose name and aliases no ledger entity holds."""
    merged = merged or {}
    given_to = {normalize(alias): target for alias, target in (reattributed or {}).items()}
    held = _holders(entities)
    named = _by_name(entities)
    moves: list[Move] = []
    missing: list[tuple[str, str]] = []
    for table in BASELINE_TABLES:
        for name, aliases in baseline.get(table, {}).items():
            normalized = list(dict.fromkeys(normalize(alias) for alias in aliases))
            given = tuple((alias, given_to[alias]) for alias in normalized if alias in given_to)
            own = [alias for alias in normalized if alias not in given_to]
            target = named.get(merged[name]) if name in merged else None
            holders = [held[alias] for alias in own if alias in held]
            if target is not None:
                primary = target
            elif holders:
                primary = held.get(own[0]) or max(holders, key=lambda e: (holders.count(e), -e.index))
            elif name in named:
                primary = named[name]
            else:
                missing.append((table, name))
                continue
            kept = {normalize(alias) for alias in primary.aliases} if primary.status in RENDERED else set()
            lost = sum(1 for alias in own if alias not in kept)
            move = Move(name, table, BASELINE_STATE[table], primary.place, lost, primary.entity,
                        move_reason(primary.notes), merged=target is not None, reattributed=given)
            if move.merged or move.reattributed or move.now != move.was or move.lost:
                moves.append(move)
    return moves, missing


def _merge_problems(entities: list[LedgerEntity], baseline: Mapping[str, Mapping[str, tuple[str, ...]]],
                    merged: Mapping[str, str]) -> list[str]:
    """MERGED_REGISTRY_ENTITIES names an entity of today's lists, merged into a ledger entity; no rendered ledger
    entity keeps the merged name."""
    today = {name for table in BASELINE_TABLES for name in baseline.get(table, {})}
    named = _by_name(entities)
    problems = []
    for name, target in merged.items():
        if name not in today:
            problems.append(f"MERGED_REGISTRY_ENTITIES merges {_shown(name)}, which is not an entity of today's "
                            f"registry")
        if target not in named:
            problems.append(f"MERGED_REGISTRY_ENTITIES merges {_shown(name)} into {_shown(target)}, which is not a "
                            f"ledger entity")
        kept = named.get(name)
        if kept is not None and kept.status in RENDERED:
            problems.append(f"MERGED_REGISTRY_ENTITIES merges {_shown(name)} into {_shown(target)}, but "
                            f"{_label(kept)} still renders under the merged name")
    return problems


def _reattribution_problems(entities: list[LedgerEntity], baseline: Mapping[str, Mapping[str, tuple[str, ...]]],
                            reattributed: Mapping[str, str]) -> list[str]:
    """REATTRIBUTED_REGISTRY_ALIASES names an alias of today's lists and the ledger entity that holds it, and the
    rendered registry reads that alias, without context, as that entity or not at all: the known-payee matcher
    (C3), else the potential table."""
    today = {normalize(alias) for table in BASELINE_TABLES for aliases in baseline.get(table, {}).values()
             for alias in aliases}
    held = _holders(entities)
    named = _by_name(entities)
    tables = render_tables(entities)
    index = AliasIndex({state: tables[TABLE_OF_GROUP[state]] for state in PAYEE_STATES})
    problems = []
    for alias, target in reattributed.items():
        norm = normalize(alias)
        if norm not in today:
            problems.append(f"REATTRIBUTED_REGISTRY_ALIASES reattributes {_shown(alias)}, which is not an alias of "
                            f"today's registry")
        if target not in named:
            problems.append(f"REATTRIBUTED_REGISTRY_ALIASES reattributes {_shown(alias)} to {_shown(target)}, which "
                            f"is not a ledger entity")
            continue
        if held.get(norm) is not named[target]:
            problems.append(f"REATTRIBUTED_REGISTRY_ALIASES reattributes {_shown(alias)} to {_shown(target)}, but "
                            f"{_shown(target)} does not hold it")
        payee = index.match(norm)
        potential = registry_match(norm, tables[TABLE_OF_GROUP["potential_lender"]])
        if payee is not None:
            reader = (payee.entity, payee.state)
        elif potential is not None:
            reader = (potential[0], "potential_lender")
        else:
            continue
        if reader[0] != target:
            problems.append(f"REATTRIBUTED_REGISTRY_ALIASES reattributes {_shown(alias)} to {_shown(target)}, but the "
                            f"registry reads it as {_shown(reader[0])} ({reader[1]})")
    return problems


def baseline_problems(entities: list[LedgerEntity], baseline: Mapping[str, Mapping[str, tuple[str, ...]]],
                      merged: Mapping[str, str] | None = None,
                      reattributed: Mapping[str, str] | None = None) -> list[str]:
    merged, reattributed = merged or {}, reattributed or {}
    moves, missing = baseline_moves(entities, baseline, merged, reattributed)
    marked = f"a sentence starting {MOVE_MARKER!r} in its notes"
    problems = _merge_problems(entities, baseline, merged)
    problems += _reattribution_problems(entities, baseline, reattributed)
    problems += [f"today's {table} entity {_shown(name)} is in no ledger entity: record it in its place, or "
                 f"moved or rejected with {marked}" for table, name in missing]
    held = _holders(entities)
    given = {normalize(alias) for alias in reattributed}
    for table in BASELINE_TABLES:
        for name, aliases in baseline.get(table, {}).items():
            own = [alias for alias in aliases if normalize(alias) not in given]
            first = held.get(normalize(own[0])) if own else None
            if name not in merged and first is not None and first.entity != name:
                problems.append(f"the ledger entity holding the first alias of today's {_shown(name)} is named "
                                f"{_shown(first.entity)}: keep today's name (S2's pins and the census compare "
                                f"entity names)")
    for move in moves:
        if move.reason:
            continue
        needs = (f"a sentence starting {MOVE_MARKER!r} in the notes of {_shown(move.holder)}, which absorbs it"
                 if move.merged else marked)
        if move.now not in UNRULED_PLACES[move.table]:
            problems.append(f"today's {move.table} entity {_shown(move.entity)} moves from {move.was} to "
                            f"{move.now} without {needs}")
        if move.lost:
            problems.append(f"today's {move.table} entity {_shown(move.entity)} loses {move.lost} of today's "
                            f"aliases without {needs}")
    return problems


# --- the rules ------------------------------------------------------------------------------------------------


def _label(entity: LedgerEntity) -> str:
    if _LONG_DIGITS.search(entity.entity):
        return f"entity {entity.index}"
    return f"entity {entity.index} ({entity.entity!r})"


def _alias_problems(entity: LedgerEntity, alias: str, rules: Rules, held: frozenset[str]) -> list[str]:
    label, shown = _label(entity), _shown(alias)
    if not alias:
        return [f"{label}: an alias is empty"]
    if "#" in alias:
        return [f"{label}: alias {shown} is masked ('#')"]
    if alias != alias.upper():
        return [f"{label}: alias {shown} has lowercase letters"]
    if not _ALIAS_CHARACTERS.fullmatch(alias):
        return [f"{label}: alias {shown} has characters outside A-Z, 0-9, space and '&'"]
    if alias != " ".join(alias.split()):
        return [f"{label}: alias {shown} has extra spaces"]
    problems = []
    if _LONG_DIGITS.search(alias) and alias not in held:
        problems.append(f"{label}: an alias carries a run of five or more digits that today's registry does not "
                        f"hold")
    if entity.status not in RENDERED:
        return problems
    norm = normalize(alias)
    if all(word in GENERIC_WORDS for word in norm.split(" ")):
        problems.append(f"{label}: alias {shown} is only generic words")
    if norm in rules.platforms:
        problems.append(f"{label}: alias {shown} is a bare platform name (spec section 5: the operating-revenue "
                        f"registry only)")
    for table, entries in rules.hand_kept.items():
        if table == INSURER_TABLE and entity.group == "premium_financing" and norm in rules.premium_insurer_aliases:
            continue  # the owner's ruling: this premium financier's rows print as the insurer
        for name, aliases in entries.items():
            if norm in {normalize(other) for other in aliases}:
                problems.append(f"{label}: alias {shown} is also an alias of the hand-kept {table} entity "
                                f"{_shown(name)}")
    if norm in rules.brands and entity.table not in (TABLE_OF_GROUP["card_issuer_context"],
                                                     TABLE_OF_GROUP["bank_name"]):
        problems.append(f"{label}: alias {shown} is a bare brand name; it belongs in card_issuer_context or "
                        f"bank_name (spec section 5)")
    if entity.table == TABLE_OF_GROUP["credit_card_payment"] and not _CARD_PAYMENT_WORDING.search(norm):
        problems.append(f"{label}: alias {shown} has no card or payment wording; a bare issuer name belongs in "
                        f"card_issuer_context (contract C10)")
    if len(alias.replace(" ", "")) <= SHORT_ALIAS and entity.short_alias_reason is None:
        problems.append(f"{label}: alias {shown} has {SHORT_ALIAS} characters or fewer and no short_alias_reason")
    return problems


def _entity_problems(entity: LedgerEntity, rules: Rules, held: frozenset[str]) -> list[str]:
    label = _label(entity)
    problems = []
    if entity.status == "admitted":
        if not entity.evidence:
            problems.append(f"{label} is admitted without evidence")
        if not any(v.verdict in ADMITTING_VERDICTS and v.confirmed for v in entity.verdicts):
            problems.append(f"{label} is admitted without an upheld or corrected verdict that confirms it")
    if entity.status in RENDERED and not entity.aliases:
        problems.append(f"{label} is {entity.status} but has no alias")
    if entity.status == "review" and entity.group in CONTEXT_ONLY_GROUPS:
        problems.append(f"{label} is review in {entity.group}, a table the classifier reads only with context, "
                        f"but the potential tier reads its aliases without that context: admit it, or record it "
                        f"as owner_ruling or rejected")
    for alias in entity.aliases:
        problems.extend(_alias_problems(entity, alias, rules, held))
    texts = [("entity", entity.entity), ("business_type", entity.business_type), ("notes", entity.notes),
             ("short_alias_reason", entity.short_alias_reason or "")]
    texts += [(f"evidence {number} note", item.note) for number, item in enumerate(entity.evidence)]
    texts += [(f"verdict {number}", f"{item.round} {item.verdict}") for number, item in enumerate(entity.verdicts)]
    for field_name, text in texts:
        if _LONG_DIGITS.search(text):
            problems.append(f"{label}: the {field_name} field carries a run of five or more digits")
    for number, item in enumerate(entity.evidence):
        if not _public_url(item.source):
            problems.append(f"{label}: evidence {number} source is not a public URL without a query string")
    for number, url in enumerate(entity.where_looked):
        if not _public_url(url):
            problems.append(f"{label}: where_looked {number} is not a public URL without a query string")
    return problems


def _name_problems(entities: list[LedgerEntity], rules: Rules) -> list[str]:
    problems = []
    first: dict[str, LedgerEntity] = {}
    for entity in entities:
        seen = first.setdefault(entity.entity, entity)
        if seen is not entity:
            problems.append(f"entity name {_shown(entity.entity)} appears more than once (entities {seen.index} "
                            f"and {entity.index})")
        for table, entries in rules.hand_kept.items():
            if entity.entity in entries:
                problems.append(f"{_label(entity)} has the name of an entity of the hand-kept {table}")
    return problems


def _collision_problems(entities: list[LedgerEntity]) -> list[str]:
    """C10: one alias, one entity (every status). Spec section 4.6: nor may a run-together form of a known
    payee's alias be another known payee's alias or run-together form."""
    problems = []
    owner: dict[str, LedgerEntity] = {}
    for entity in entities:
        for norm in dict.fromkeys(normalize(alias) for alias in entity.aliases if alias):
            first = owner.setdefault(norm, entity)
            if first is not entity:
                problems.append(f"alias {_shown(norm)} appears under {_label(first)} and {_label(entity)}")
    matcher = [e for e in entities if e.status == "admitted" and e.group in (*PAYEE_STATES, "debt_relief")]
    explicit: dict[str, LedgerEntity] = {}
    for entity in matcher:
        for alias in entity.aliases:
            explicit.setdefault(normalize(alias), entity)
    joined: dict[str, tuple[LedgerEntity, str]] = {}
    for entity in matcher:
        for alias in entity.aliases:
            norm = normalize(alias)
            words = norm.split(" ")
            form = "".join(words)
            if len(words) < 2 or len(form) < RUN_TOGETHER_MIN_LENGTH:
                continue
            other = explicit.get(form)
            if other is None:
                other, spelled = joined.setdefault(form, (entity, norm))
                if spelled == norm:
                    continue  # the same alias under two entities is reported above
            if other is not entity:
                problems.append(f"run-together form {_shown(form)} of {_label(entity)} is also claimed by "
                                f"{_label(other)}")
    return problems


def owner_named_problems(tables: Mapping[str, Mapping[str, tuple[str, ...]]],
                         owner_named: Mapping[str, tuple[tuple[str, str], ...]]) -> list[str]:
    """C10: every payee the owner named (spec section 2) is admitted in its group. A payee-matcher group must
    win the spelling in the known-payee matcher; a card issuer may instead be a bare issuer name of the
    context table; premium financing and bank names must be in their own table and no known payee."""
    index = AliasIndex({state: tables[TABLE_OF_GROUP[state]] for state in PAYEE_STATES})
    problems = []
    for group, pairs in owner_named.items():
        for label, spelling in pairs:
            text = normalize(spelling)
            payee = index.match(text)
            if group in PAYEE_STATES:
                if payee is not None and payee.state == group:
                    continue
                context = tables[TABLE_OF_GROUP["card_issuer_context"]]
                if group == "credit_card_payment" and payee is None and registry_match(text, context) is not None:
                    continue
            elif payee is None and registry_match(text, tables[TABLE_OF_GROUP[group]]) is not None:
                continue
            found = "nothing" if payee is None else f"{_shown(payee.entity)} ({payee.state})"
            problems.append(f"owner-named {mask_digit_runs(label)} is not admitted in {group}: {_shown(spelling)} "
                            f"matches {found}")
    return problems


def payout_credit_problems(entities: list[LedgerEntity], names: tuple[str, ...]) -> list[str]:
    """The owner's payout-credit ruling (PAYOUT_CREDIT_ENTITIES): S2 reads these entities' credits as the account
    holder's own sales, an exception to D1, so each is an admitted ledger entity of a group whose credits D1
    treats as financing proceeds (FINANCING_STATES)."""
    named = _by_name(entities)
    problems = []
    for name in names:
        entity = named.get(name)
        if entity is None:
            problems.append(f"PAYOUT_CREDIT_ENTITIES names {_shown(name)}, which is not a ledger entity")
        elif entity.status != "admitted" or entity.group not in FINANCING_STATES:
            problems.append(f"PAYOUT_CREDIT_ENTITIES names {_label(entity)}, {entity.status} in {entity.group}: a "
                            f"payout-credit exception needs an admitted entity of a group whose credits D1 treats "
                            f"as financing proceeds")
    return problems


def field_order_problems(entities: list[LedgerEntity], forms: Mapping[str, tuple[str, ...]]) -> list[str]:
    """The owner's field-order ruling (FIELD_ORDER_PAYEE_FORMS, 2026-09-27): each entity is an admitted ledger entity
    of a known-payee group, and each form compiles."""
    named = _by_name(entities)
    problems = []
    for name, patterns in forms.items():
        entity = named.get(name)
        if entity is None or entity.status != "admitted" or entity.group not in PAYEE_STATES:
            problems.append(f"FIELD_ORDER_PAYEE_FORMS names {_shown(name)}, which is not an admitted ledger entity of "
                            f"a known-payee group")
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error:
                problems.append(f"FIELD_ORDER_PAYEE_FORMS has a form of {_shown(name)} that does not compile")
    return problems


def _unmasked_problems(data: object, rules: Rules) -> list[str]:
    entities, problems = parse_ledger(data)
    if problems:
        return problems
    held = frozenset(alias for table in rules.baseline.values() for aliases in table.values() for alias in aliases)
    problems.extend(_name_problems(entities, rules))
    for entity in entities:
        problems.extend(_entity_problems(entity, rules, held))
    problems.extend(_collision_problems(entities))
    problems.extend(owner_named_problems(render_tables(entities), rules.owner_named))
    problems.extend(payout_credit_problems(entities, rules.payout_credit))
    problems.extend(field_order_problems(entities, rules.field_order))
    problems.extend(baseline_problems(entities, rules.baseline, rules.merged, rules.reattributed))
    return problems


def validate(data: object, rules: Rules) -> list[str]:
    """Every problem with the ledger, in a fixed order; an empty list means it may be rendered. Every rule
    masks the names and values it quotes; as a backstop, no returned message quotes a run of five or more
    digits."""
    return [mask_digit_runs(problem) for problem in _unmasked_problems(data, rules)]


# --- what the owner and a privacy reviewer read ---------------------------------------------------------------


def premium_insurer_overlaps(entities: list[LedgerEntity],
                             insurers: Mapping[str, tuple[str, ...]]) -> list[tuple[str, str]]:
    """(premium-finance entity, hand-kept insurer) pairs where a premium alias contains an insurer's alias as
    whole words. Not a problem: the insurance rule reads the premium table first (S2), so the financier keeps
    its own rows and rows naming only the insurer stay plain insurance. The owner rules on them. An insurer
    alias that a premium entity holds itself (the owner's ruling, PREMIUM_FINANCE_INSURER_ALIASES) is no
    overlap of any premium entity: the rows that print it are premium financing already."""
    premium = [entity for entity in entities if entity.status == "admitted" and entity.group == "premium_financing"]
    held = {normalize(alias) for entity in premium for alias in entity.aliases}
    pairs: list[tuple[str, str]] = []
    for entity in premium:
        texts = [normalize(alias) for alias in entity.aliases]
        for insurer, aliases in insurers.items():
            for alias in aliases:
                norm = normalize(alias)
                if norm in held:
                    continue
                inside = re.compile(rf"(?<![A-Z0-9]){re.escape(norm)}(?![A-Z0-9])")
                pair = (entity.entity, insurer)
                if pair not in pairs and any(inside.search(text) for text in texts):
                    pairs.append(pair)
    return pairs


def privacy_review(entities: list[LedgerEntity]) -> list[str]:
    """The lines a person reads for a person's or a customer's name before the ledger is committed: every
    entity name without an organisation word, and every alias that shares no word with its entity's name.
    Every status is listed, because the committed ledger carries them all. No line quotes a run of five or
    more digits."""
    lines = []
    for entity in entities:
        words = set(normalize(entity.entity).split(" "))
        if not words & ORG_CUES:
            lines.append(f"no organisation word in the name: {entity.entity} ({entity.status})")
        for alias in dict.fromkeys(entity.aliases):
            if not set(normalize(alias).split(" ")) & words:
                lines.append(f"alias shares no word with its name: {entity.entity} | {alias}")
    return [mask_digit_runs(line) for line in lines]


# --- the hand-kept inputs --------------------------------------------------------------------------------------


def current_rules() -> Rules:
    """The validator's inputs: the hand-kept constants of ``analysis/classification_registry.py`` and today's
    registry from git at BASELINE_REVISION."""
    from analysis import classification_registry as registry

    return Rules(
        owner_named=registry.OWNER_NAMED_PAYEES,
        platforms=frozenset(normalize(name) for name in registry.BARE_PLATFORM_NAMES),
        brands=frozenset(normalize(name) for name in registry.BARE_BRAND_NAMES),
        hand_kept={
            INSURER_TABLE: registry.INSURANCE_PROVIDER_ALIASES,
            "OPERATING_REVENUE_SOURCE_ALIASES": registry.OPERATING_REVENUE_SOURCE_ALIASES,
        },
        baseline=load_baseline(),
        premium_insurer_aliases=frozenset(normalize(name) for name in registry.PREMIUM_FINANCE_INSURER_ALIASES),
        merged=registry.MERGED_REGISTRY_ENTITIES,
        payout_credit=registry.PAYOUT_CREDIT_ENTITIES,
        reattributed=registry.REATTRIBUTED_REGISTRY_ALIASES,
        field_order=registry.FIELD_ORDER_PAYEE_FORMS,
    )
