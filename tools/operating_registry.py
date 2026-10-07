"""The operating-revenue registry's validator (true revenue spec §7.4).

The operating registry (`OPERATING_REVENUE_SOURCE_ALIASES` and its types, the sixteen-character cuts, the payout and
card-settlement forms) and the 5.6 tables (`HEALTHCARE_PAYER_ALIASES`, `DEALER_FUNDING_PAYERS`,
`FACTORING_PAYOUT_PAYERS`, `OWNER_MONEY_PLATFORMS`, `SECTION_15_DEFERRED_PAYERS`, `P2P_SENDING_BANK_NAMES`,
`STATEMENT_BANK_PRINTED_NAMES`) are hand-kept in `analysis/classification_registry.py`. This module says what is
wrong with them:

* every operating entity has a source type, and every typed entity has aliases;
* every payout form and card form compiles, and the entity it names is typed;
* no operating alias, cut or form equals (or, for a form, matches) a financing alias of the ledger or an insurer's;
* a cut equals no other registry or ledger alias;
* a processor's bare alias waits for its advance product (`PROCESSOR_ADVANCE_PRODUCTS`): it is in the registry only
  when the ledger admits that product or the processor is in `PROCESSORS_WITHOUT_ADVANCE_PRODUCT`;
* `HEALTHCARE_PAYER_ALIASES` collides with no ledger alias and no insurer alias;
* `DEALER_FUNDING_PAYERS` collides with no ledger alias outside the vehicle-financing group, which Q7 names on purpose;
* `FACTORING_PAYOUT_PAYERS` collides with no ledger, operating or insurer alias (true revenue final review M3);
* `OWNER_MONEY_PLATFORMS`, `SECTION_15_DEFERRED_PAYERS` and (audit B6) `LENDING_BANK_CREDIT_PAYERS` and
  `EARNED_WAGE_ACCESS_PAYERS` compile and read no operating alias;
* (owner ruling 2026-10-02, Q8) each `CUSTOMER_FINANCING_PAYERS` spelling and `CUSTOMER_FINANCING_NAMES` compile and
  read no operating alias, no insurer alias and no rendered ledger alias of an entity other than the financiers';
* `P2P_SENDING_BANK_NAMES` and `STATEMENT_BANK_PRINTED_NAMES` are normalized, and name no form twice.

It also WARNS (never fails) when a multi-word operating alias spans the originator/entry boundary a bank prints between
two fields ('HEARTLAND PAYMENT SYSTEMS' printed as 'HEARTLAND DES:PAYMENT'), which a contiguous alias cannot match.

Usage: python -m tools.operating_registry --check   (exit 0 when there is no problem, 1 otherwise)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis import classification_registry as registry  # noqa: E402
from analysis.description_text import normalize_transaction_description as normalize  # noqa: E402
from analysis.flag_groups import FINANCING_STATES  # noqa: E402

#: The entry words a bank prints in its own field after the originator (Bank of America's DES, Chase's CO ENTRY DESCR).
_ENTRY_WORDS = frozenset({"DEPOSIT", "DEP", "PAYMENT", "PAYMENTS", "SETTLEMENT", "PAYOUT", "TRANSFER", "TXNS"})


def _aliases(table: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """{normalized alias: entity} of one table."""
    return {normalize(alias): entity for entity, aliases in table.items() for alias in aliases}


def _financing_aliases() -> dict[str, str]:
    table: dict[str, str] = {}
    for state, group in registry.PAYEE_GROUP_REGISTRIES.items():
        if state in FINANCING_STATES:
            table.update(_aliases(group))
    table.update(_aliases(registry.POTENTIAL_LENDER_ALIASES))
    return table


def _insurer_aliases() -> dict[str, str]:
    return {**_aliases(registry.INSURANCE_PROVIDER_ALIASES), **_aliases(registry.PREMIUM_FINANCE_ALIASES)}


def _ledger_aliases() -> dict[str, tuple[str, str]]:
    """{normalized alias: (group, entity)} of every table the ledger renders."""
    table: dict[str, tuple[str, str]] = {}
    for state, group in registry.PAYEE_GROUP_REGISTRIES.items():
        for alias, entity in _aliases(group).items():
            table[alias] = (state, entity)
    for state, group in (("potential_lender", registry.POTENTIAL_LENDER_ALIASES),
                         ("bank_name", registry.BANK_NAME_ALIASES),
                         ("card_issuer_context", registry.CARD_ISSUER_CONTEXT_ALIASES),
                         ("debt_relief", registry.DEBT_RELIEF_ALIASES),
                         ("premium_financing", registry.PREMIUM_FINANCE_ALIASES)):
        for alias, entity in _aliases(group).items():
            table[alias] = (state, entity)
    return table


def problems() -> list[str]:
    """Every problem of the hand-kept operating registry and the 5.6 payer tables, as sentences."""
    found: list[str] = []
    aliases = registry.OPERATING_REVENUE_SOURCE_ALIASES
    types = registry.OPERATING_REVENUE_SOURCE_TYPES
    for entity in aliases:
        if entity not in types:
            found.append(f"operating entity {entity!r} has no source type")
    for entity in types:
        if entity not in aliases:
            found.append(f"source type of {entity!r} names no operating entity")
    financing = _financing_aliases()
    insurers = _insurer_aliases()
    ledger = _ledger_aliases()
    own = _aliases(aliases)
    for entity, forms in registry.OPERATING_SOURCE_PAYOUT_FORMS.items():
        if entity not in types:
            found.append(f"payout form entity {entity!r} is not a typed operating entity")
        for label, pattern in forms:
            _check_form(found, f"payout form {label!r}", pattern, financing, insurers)
    for form in registry.CARD_SETTLEMENT_CREDIT_FORMS:
        if form.entity is not None and form.entity not in types:
            found.append(f"card form {form.label!r} names {form.entity!r}, which is not a typed operating entity")
        _check_form(found, f"card form {form.label!r}", form.pattern, financing, insurers)
        if form.refusal is not None:
            _compiles(found, f"card form {form.label!r} refusal", form.refusal)
    for alias, entity in own.items():
        if alias in financing:
            found.append(f"operating alias {alias!r} of {entity!r} is a financing alias of {financing[alias]!r}")
        if alias in insurers:
            found.append(f"operating alias {alias!r} of {entity!r} is an insurer alias of {insurers[alias]!r}")
    for entity, cuts in registry.OPERATING_REVENUE_TRUNCATIONS.items():
        for cut in cuts:
            other = own.get(cut)
            if other is not None and other != entity:
                found.append(f"the cut {cut!r} of {entity!r} is an operating alias of {other!r}")
            if cut in ledger:
                group, holder = ledger[cut]
                found.append(f"the cut {cut!r} of {entity!r} is a {group} alias of {holder!r}")
            if cut in insurers:
                found.append(f"the cut {cut!r} of {entity!r} is an insurer alias of {insurers[cut]!r}")
    admitted = {
        entity for group in registry.PAYEE_GROUP_REGISTRIES.values() for entity in group
    }
    for processor, (bare, product) in registry.PROCESSOR_ADVANCE_PRODUCTS.items():
        present = [alias for alias in bare if normalize(alias) in own]
        if not present:
            continue
        cleared = (product is not None and product in admitted) or processor in registry.PROCESSORS_WITHOUT_ADVANCE_PRODUCT
        if not cleared:
            found.append(
                f"the bare alias {present[0]!r} of {processor!r} is in the registry before its advance product is in "
                "the lender ledger (PROCESSOR_ADVANCE_PRODUCTS)"
            )
    for alias, entity in _aliases(registry.HEALTHCARE_PAYER_ALIASES).items():
        if alias in ledger:
            group, holder = ledger[alias]
            found.append(f"healthcare payer alias {alias!r} of {entity!r} is a {group} alias of {holder!r}")
        if alias in insurers:
            found.append(f"healthcare payer alias {alias!r} of {entity!r} is an insurer alias of {insurers[alias]!r}")
    for alias, entity in _aliases(registry.DEALER_FUNDING_PAYERS).items():
        if alias in ledger and ledger[alias][0] != "vehicle_financing":
            group, holder = ledger[alias]
            found.append(f"dealer-funding payer alias {alias!r} of {entity!r} is a {group} alias of {holder!r}")
    _check_56_tables(found, own, ledger, insurers)
    return found


def _check_56_tables(
    found: list[str], own: dict[str, str], ledger: dict[str, tuple[str, str]], insurers: dict[str, str]
) -> None:
    """True revenue final review M3: the five other 5.6 tables. A factoring payer's alias collides with no ledger,
    operating or insurer alias; the owner-money and deferred-source patterns compile and read no operating alias (a
    platform that pays a business its sales is neither); the sending banks' and the statement banks' printed names
    are normalized and unique. Owner ruling 2026-10-02 (Q8): the lease-to-own and patient financiers' payer spellings
    (CUSTOMER_FINANCING_PAYERS) and their name sweep (CUSTOMER_FINANCING_NAMES) compile and read no operating alias, no
    insurer alias and no rendered ledger alias of another entity (a spelling may read its own entity's)."""
    for alias, entity in _aliases(registry.FACTORING_PAYOUT_PAYERS).items():
        if alias in ledger:
            group, holder = ledger[alias]
            found.append(f"factoring payer alias {alias!r} of {entity!r} is a {group} alias of {holder!r}")
        if alias in own:
            found.append(f"factoring payer alias {alias!r} of {entity!r} is an operating alias of {own[alias]!r}")
        if alias in insurers:
            found.append(f"factoring payer alias {alias!r} of {entity!r} is an insurer alias of {insurers[alias]!r}")
    # Audit B6 (I23, I49): the lending banks and the earned-wage access providers likewise.
    for name in ("OWNER_MONEY_PLATFORMS", "SECTION_15_DEFERRED_PAYERS", "LENDING_BANK_CREDIT_PAYERS",
                 "EARNED_WAGE_ACCESS_PAYERS"):
        compiled = _compiles(found, name, getattr(registry, name))
        if compiled is None:
            continue
        for alias, entity in own.items():
            if compiled.search(alias):
                found.append(f"{name} reads the operating alias {alias!r} of {entity!r}")
    # Owner ruling 2026-10-02 (Q8): the lease-to-own and patient financiers' payer spellings and their name sweep compile,
    # read no operating or insurer alias, and read no rendered ledger alias of an entity other than the financiers'.
    financiers = getattr(registry, "CUSTOMER_FINANCING_PAYERS", {})
    readers = [(f"CUSTOMER_FINANCING_PAYERS[{entity!r}]", pattern, {entity}) for entity, pattern in financiers.items()]
    if hasattr(registry, "CUSTOMER_FINANCING_NAMES"):
        readers.append(("CUSTOMER_FINANCING_NAMES", registry.CUSTOMER_FINANCING_NAMES, set(financiers)))
    for name, pattern, allowed in readers:
        compiled = _compiles(found, name, pattern)
        if compiled is None:
            continue
        for alias, entity in own.items():
            if compiled.search(alias):
                found.append(f"{name} reads the operating alias {alias!r} of {entity!r}")
        for alias, entity in insurers.items():
            if compiled.search(alias):
                found.append(f"{name} reads the insurer alias {alias!r} of {entity!r}")
        for alias, (group, holder) in ledger.items():
            if holder not in allowed and compiled.search(alias):
                found.append(f"{name} reads the {group} alias {alias!r} of {holder!r}")
    # Audit B3 (I11): the card-payout processors' names are normalized and name no ledger or insurer alias (the
    # release reads them beside the processor's own ACH activity only).
    for entity, card_names in getattr(registry, "CARD_PAYOUT_PROCESSOR_NAMES", {}).items():
        for name in card_names:
            if not name or normalize(name) != name:
                found.append(f"card-payout processor name {name!r} of {entity!r} is not normalized")
            if name in ledger:
                group, holder = ledger[name]
                found.append(f"card-payout processor name {name!r} of {entity!r} is a {group} alias of {holder!r}")
            if name in insurers:
                found.append(f"card-payout processor name {name!r} of {entity!r} is an insurer alias of {insurers[name]!r}")
    names = list(registry.P2P_SENDING_BANK_NAMES)
    for name in names:
        if not name or normalize(name) != name:
            found.append(f"sending bank name {name!r} is not normalized")
    if len(names) != len(set(names)):
        found.append("P2P_SENDING_BANK_NAMES lists a name twice")
    for words, forms in registry.STATEMENT_BANK_PRINTED_NAMES:
        for printed in (*words, *forms):
            if not printed or normalize(printed) != printed:
                found.append(f"statement bank name {printed!r} is not normalized")
        if not words or not forms or len(set(forms)) != len(forms):
            found.append(f"statement bank entry {words!r} names no bank word, no form, or a form twice")


def warnings() -> list[str]:
    """The operating aliases that span a bank's originator/entry boundary (never a failure)."""
    return [
        f"operating alias {alias!r} of {entity!r} spans the originator/entry boundary"
        for alias, entity in _aliases(registry.OPERATING_REVENUE_SOURCE_ALIASES).items()
        if len(alias.split()) > 1 and any(word in _ENTRY_WORDS for word in alias.split()[1:])
    ]


def _compiles(found: list[str], name: str, pattern: str) -> re.Pattern[str] | None:
    try:
        return re.compile(pattern)
    except re.error as error:
        found.append(f"{name} does not compile: {error}")
        return None


def _check_form(found: list[str], name: str, pattern: str, financing: dict[str, str], insurers: dict[str, str]) -> None:
    compiled = _compiles(found, name, pattern)
    if compiled is None:
        return
    for alias, entity in (*financing.items(), *insurers.items()):
        if compiled.fullmatch(alias):
            found.append(f"{name} reads the financing or insurer alias {alias!r} of {entity!r}")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["--check"]:
        print(__doc__)
        return 2
    for line in warnings():
        print(f"warning: {line}")
    found = problems()
    for line in found:
        print(f"problem: {line}")
    print(f"{len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
