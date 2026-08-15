"""The registry's contents: one `Registration` per deterministic parser.

Kept apart from `analysis/parser_registry.py` so that the rules and the data
they operate on can be reviewed separately, and so `analysis/pipeline.py`
imports one symbol instead of forty-three parse functions.

Registration happens here and only here. Import order therefore cannot affect
dispatch order — that order is `(band, id)` over this data, and
`tests/test_parser_registry_entries.py` asserts it against a literal list.

Each entry names the parser's markers and its normalization, both defined in
the parser's own module: a bank's evidence lives with the bank's parser, and
this file stays a table of contents rather than a second place to look for
detection logic.

Ids follow the naming baseline of the reviewed prototype registry
(`git show 54a9e8d:analysis/parser_registry.py`, catalogued in
PROTOTYPE_REVIEW.md). That prototype's first-match dispatch is deliberately
not reused — see docs/moneythumb-replacement/R3_RFC.md §1.
"""
from __future__ import annotations

from . import (
    altana,
    amex,
    atb,
    b1,
    balance_by_date,
    banco_popular,
    bluevine,
    bmo,
    bmo_ca_business,
    bmo_us_activity,
    bofa,
    brex,
    burke_herbert,
    capital_one,
    chase,
    chase_savings,
    cibc,
    citibusiness,
    citizens,
    columbia_bank,
    community_section,
    consumers,
    core_processor_sectioned,
    demo_national,
    desjardins,
    farmers_merchants,
    fifth_third,
    first_citizens,
    first_community,
    first_farmers,
    fiserv_premier,
    found_lead,
    huntington,
    ibc,
    linkbank,
    mercury,
    midflorida,
    navigant,
    navy_federal,
    pnc,
    rbc,
    regions,
    relay,
    releve_facturation,
    santander,
    scanned_small_bank,
    scotia,
    secu,
    shopify_balance,
    square_checking,
    symitar,
    td_can,
    td_canada_french,
    td_us,
    texas_bank,
    truist,
    us_bank,
    wealthsimple,
    wells,
    wilson_muir,
    woodforest,
    zions,
)
from .parser_registry import Registration, register, registrations, validate_registry

__all__ = ["load", "registrations"]

#: Every deterministic parser, as (id, bank label, module, markers attribute,
#: normalize attribute or None, parse attribute). Alphabetical by id — dispatch
#: order is computed from the data, so the order of this table means nothing
#: beyond being easy to read.
_ENTRIES: tuple[tuple[str, str, object, str, str | None, str], ...] = (
    ("altana", "Altana Federal Credit Union", altana, "DETECTION_MARKERS", None, "parse_altana_statement"),
    ("american_express", "American Express", amex, "DETECTION_MARKERS", None, "parse_amex_statement"),
    ("apex_scanned", "Apex Bank", scanned_small_bank, "APEX_DETECTION_MARKERS", "detection_text", "parse_apex_scanned_statement"),
    ("atb", "ATB Financial", atb, "DETECTION_MARKERS", None, "parse_atb_statement"),
    ("b1", "B1Bank", b1, "DETECTION_MARKERS", None, "parse_b1_statement"),
    # Not a bank: a core processor's statement template, recognised by the
    # four-way summary partition and the daily grid it prints and by nothing
    # else (W3 §SCANC). The issuer is deliberately not published — this
    # template prints its wordmark as a graphic — so the label here names the
    # TEMPLATE, and `Statement.bank` stays None rather than carrying a guess.
    ("balance_by_date", "Balance By Date Statement Platform", balance_by_date, "DETECTION_MARKERS", None, "parse_balance_by_date_statement"),
    ("banco_popular", "Banco Popular", banco_popular, "DETECTION_MARKERS", None, "parse_banco_popular_statement"),
    ("bank_of_america", "Bank of America", bofa, "DETECTION_MARKERS", "detection_text", "parse_bofa_statement"),
    ("bluevine", "Bluevine", bluevine, "DETECTION_MARKERS", None, "parse_bluevine_statement"),
    ("bmo", "BMO", bmo, "DETECTION_MARKERS", "detection_text", "parse_bmo_statement"),
    ("bmo_ca_business", "BMO", bmo_ca_business, "DETECTION_MARKERS", "detection_text", "parse_bmo_ca_business_statement"),
    ("bmo_ca_business_french", "BMO", bmo_ca_business, "FRENCH_DETECTION_MARKERS", "detection_text", "parse_bmo_ca_business_french_statement"),
    ("bmo_us_activity", "BMO", bmo_us_activity, "DETECTION_MARKERS", "detection_text", "parse_bmo_us_activity_statement"),
    ("brex", "Brex", brex, "DETECTION_MARKERS", "detection_text", "parse_brex_statement"),
    ("burke_herbert", "Burke & Herbert Bank", burke_herbert, "DETECTION_MARKERS", "detection_text", "parse_burke_herbert_statement"),
    ("capital_one", "Capital One", capital_one, "DETECTION_MARKERS", None, "parse_capital_one_statement"),
    ("chase", "Chase", chase, "DETECTION_MARKERS", "detection_text", "parse_chase_statement"),
    ("chase_export", "Chase Transaction Export", chase, "EXPORT_DETECTION_MARKERS", "detection_text", "parse_chase_export_statement"),
    ("chase_savings", "Chase Savings", chase_savings, "DETECTION_MARKERS", "detection_text", "parse_chase_savings_statement"),
    ("cibc", "CIBC", cibc, "EN_DETECTION_MARKERS", "en_detection_text", "parse_cibc_statement"),
    ("cibc_french", "CIBC", cibc, "DETECTION_MARKERS", None, "parse_cibc_french_statement"),
    ("citibusiness", "Citibank", citibusiness, "DETECTION_MARKERS", "detection_text", "parse_citibusiness_statement"),
    ("citizens", "Citizens Bank", citizens, "DETECTION_MARKERS", None, "parse_citizens_statement"),
    ("columbia_bank", "Columbia Bank", columbia_bank, "DETECTION_MARKERS", "detection_text", "parse_columbia_bank_statement"),
    # Not a bank: a core processor's statement template, printed by 22 issuers
    # in the archive and read without naming any of them (W3 §JHA-CELL). The
    # issuer is read out of each document and published as `Statement.bank`,
    # so the label here names the PLATFORM - there is no one bank to name, and
    # inventing one would be the hardcode this registration exists to avoid.
    ("community_section", "Core Statement Platform", community_section, "PLATFORM_DETECTION_MARKERS", "detection_text", "parse_community_section_statement"),
    ("consumers", "Consumers Credit Union", consumers, "DETECTION_MARKERS", None, "parse_consumers_statement"),
    # A SECOND core processor's template, registered the way W3 §JHA-CELL
    # established for the first: on the template's own furniture, with the
    # issuer read out of each document and published as `Statement.bank`. The
    # label here names the PLATFORM - the archive prints this template under
    # five different issuers, several of which print their name only inside a
    # logo, and inventing one would be the hardcode this registration exists to
    # avoid.
    ("core_processor_sectioned", "Core Processor Sectioned Platform", core_processor_sectioned, "DETECTION_MARKERS", "detection_text", "parse_core_processor_sectioned_statement"),
    ("dakota_west", "Dakota West Credit Union", community_section, "DAKOTA_WEST_DETECTION_MARKERS", None, "parse_dakota_west_statement"),
    ("demo_national", "Demo National Bank", demo_national, "DETECTION_MARKERS", None, "parse_demo_national_statement"),
    ("desjardins", "Desjardins", desjardins, "DETECTION_MARKERS", None, "parse_desjardins_statement"),
    ("farmers_merchants", "Farmers & Merchants Bank", farmers_merchants, "DETECTION_MARKERS", "detection_text", "parse_farmers_merchants_statement"),
    ("fifth_third", "Fifth Third Bank", fifth_third, "DETECTION_MARKERS", "detection_text", "parse_fifth_third_statement"),
    ("first_citizens", "First Citizens Bank", first_citizens, "DETECTION_MARKERS", None, "parse_first_citizens_statement"),
    ("first_community", "First Community Credit Union", first_community, "DETECTION_MARKERS", "detection_text", "parse_first_community_statement"),
    ("first_farmers", "First Farmers Bank & Trust", first_farmers, "DETECTION_MARKERS", "detection_text", "parse_first_farmers_statement"),
    # Fiserv Premier is a platform, not a bank: `bank` here is the platform
    # label the registry needs, while `Statement.bank` carries the issuing
    # division read off the document itself.
    ("fiserv_premier", "Fiserv Premier", fiserv_premier, "DETECTION_MARKERS", "detection_text", "parse_fiserv_premier_statement"),
    # Found's two documents, one reader. The month-to-date view is a separate
    # registration because the issuer prints, on it and on nothing else, that
    # it "is not a bank statement" — see the `_OVERRIDES` entry below and
    # `analysis/found_lead.py`. The disclaimer is EXCLUDING on one and REQUIRED
    # on the other, so no `supersedes` edge is needed: they are disjoint by
    # construction and the conformance cross-product holds them apart.
    ("found_lead", "Lead Bank (Found)", found_lead, "DETECTION_MARKERS", "detection_text", "parse_found_lead_statement"),
    ("found_lead_activity", "Lead Bank (Found) Month-to-Date Activity", found_lead, "ACTIVITY_DETECTION_MARKERS", "detection_text", "parse_found_lead_statement"),
    ("huntington", "Huntington National Bank", huntington, "DETECTION_MARKERS", "detection_text", "parse_huntington_statement"),
    ("ibc", "IBC Bank", ibc, "DETECTION_MARKERS", None, "parse_ibc_statement"),
    ("linkbank", "LINKBANK", linkbank, "DETECTION_MARKERS", None, "parse_linkbank_statement"),
    ("mercury", "Mercury", mercury, "DETECTION_MARKERS", "detection_text", "parse_mercury_statement"),
    ("midflorida", "MIDFLORIDA Credit Union", midflorida, "DETECTION_MARKERS", None, "parse_midflorida_statement"),
    ("mission_valley", "Mission Valley Bank", community_section, "MISSION_VALLEY_DETECTION_MARKERS", None, "parse_mission_valley_statement"),
    ("navigant", "Navigant Credit Union", navigant, "DETECTION_MARKERS", "detection_text", "parse_navigant_statement"),
    ("navy_federal", "Navy Federal Credit Union", navy_federal, "DETECTION_MARKERS", None, "parse_navy_federal_statement"),
    ("pnc", "PNC Bank", pnc, "DETECTION_MARKERS", None, "parse_pnc_statement"),
    ("rbc", "Royal Bank of Canada", rbc, "DETECTION_MARKERS", "detection_text", "parse_rbc_statement"),
    ("rbc_french", "Banque Royale du Canada", rbc, "FRENCH_DETECTION_MARKERS", "french_detection_text", "parse_rbc_french_statement"),
    ("regions", "Regions Bank", regions, "DETECTION_MARKERS", "detection_text", "parse_regions_statement"),
    ("relay", "Thread Bank (Relay)", relay, "DETECTION_MARKERS", "detection_text", "parse_relay_statement"),
    # Not a bank, and not a platform we can name either: a French-language
    # statement template whose 16 archive documents name NO institution
    # anywhere (W3 §UNID-B UB5; honest-unknown-issuer ruling 2026-08-14). The
    # label here describes the printed template, because there is nothing else
    # honest to put in this column - and `Statement.bank` is `None` on every
    # document it publishes. Deliberately carries no institution word: this
    # string is normalised into `discovery.evidence.registered_bank_tokens`
    # and matched against folder labels by containment, so a label containing
    # "Unidentified" would report that folder as a bank we support.
    ("releve_facturation", "Releve de Compte Statement Template", releve_facturation, "DETECTION_MARKERS", "detection_text", "parse_releve_facturation_statement"),
    ("santander", "Santander Bank", santander, "DETECTION_MARKERS", None, "parse_santander_statement"),
    ("scotiabank", "Scotiabank", scotia, "DETECTION_MARKERS", "detection_text", "parse_scotiabank_statement"),
    ("secu", "SECU Maryland", secu, "DETECTION_MARKERS", None, "parse_secu_statement"),
    ("shopify_balance", "Shopify Balance", shopify_balance, "DETECTION_MARKERS", "detection_text", "parse_shopify_balance_statement"),
    ("southside_scanned", "Southside Bank", scanned_small_bank, "SOUTHSIDE_DETECTION_MARKERS", "detection_text", "parse_southside_scanned_statement"),
    ("square_checking", "Square", square_checking, "DETECTION_MARKERS", "detection_text", "parse_square_checking_statement"),
    ("symitar", "Symitar Credit Union", symitar, "DETECTION_MARKERS", None, "parse_symitar_statement"),
    ("td_canada", "TD Canada Trust", td_can, "DETECTION_MARKERS", None, "parse_td_canada_statement"),
    ("td_canada_native", "TD Canada Trust", td_can, "NATIVE_DETECTION_MARKERS", "detection_text", "parse_native_td_canada_statement"),
    # The Quebec issue of the same printed grid. No `supersedes` edge and no
    # band: it is not a narrower class of the English layouts but a disjoint
    # one, and the cross-product in tests/test_parser_conformance.py is what
    # holds that apart rather than a precedence rule.
    ("td_canada_french", "TD Canada Trust", td_canada_french, "DETECTION_MARKERS", "detection_text", "parse_td_canada_french_statement"),
    ("td_us", "TD Bank", td_us, "DETECTION_MARKERS", None, "parse_td_us_statement"),
    ("texas_bank", "Texas Bank and Trust", texas_bank, "DETECTION_MARKERS", None, "parse_texas_bank_statement"),
    ("truist", "Truist", truist, "DETECTION_MARKERS", None, "parse_truist_statement"),
    ("us_bank", "U.S. Bank", us_bank, "DETECTION_MARKERS", None, "parse_us_bank_statement"),
    ("wealthsimple", "Wealthsimple", wealthsimple, "DETECTION_MARKERS", None, "parse_wealthsimple_statement"),
    ("wells_fargo", "Wells Fargo", wells, "DETECTION_MARKERS", None, "parse_wells_statement"),
    ("wilson_muir", "Wilson & Muir Bank & Trust", wilson_muir, "DETECTION_MARKERS", None, "parse_wilson_muir_statement"),
    ("woodforest", "Woodforest National Bank", woodforest, "DETECTION_MARKERS", None, "parse_woodforest_statement"),
    ("zions", "Zions Bancorporation", zions, "DETECTION_MARKERS", "detection_text", "parse_zions_statement"),
)

#: Per-registration overrides for anything that is not the default. Kept as a
#: short, readable exception list rather than widening every row of the table.
_OVERRIDES: dict[str, dict] = {
    # The three sub-dispatches the or-chain hid inside a parser. Each is a
    # narrower document class of the same institution, so it takes the low band
    # and supersedes its general form outright - the precedence the nested
    # `if ... is not None: return ...` used to express by position.
    "chase_export": {
        "band": 10,
        "supersedes": frozenset({"chase"}),
        # A Chase online transaction export is not a bank statement: it has no
        # formal summary or period. The pipeline reads this instead of
        # comparing Statement.bank to a literal.
        "formal_statement": False,
        "informal_quality_note": (
            "Chase for Business transaction export lacks a formal statement summary/period"
        ),
        "informal_integrity_note": (
            "document is a Chase online transaction export, not a complete bank statement"
        ),
    },
    # Chase's savings product is a narrower document class of the same
    # institution, printed behind the same sentinels: `chase` detects every one
    # of these documents on its own two markers and then declines at parse,
    # because it hard-requires CHECKING SUMMARY. Without this edge the two
    # claims would resolve `ambiguous` and the document would go to review.
    # The edge is safe in the strong sense rather than the observed one:
    # `chase_savings` carries an EXCLUDING marker on CHECKING SUMMARY, so it
    # cannot claim — and therefore cannot shadow `chase` on — any document
    # printing the checking product.
    "chase_savings": {"band": 10, "supersedes": frozenset({"chase"})},
    "rbc_french": {"band": 10, "supersedes": frozenset({"rbc"})},
    # The four issuers that already had their own reader on the core-processor
    # template `community_section` now registers generically (W3 §JHA-CELL).
    # Each is a narrower document class of the same template - the general
    # reader claims all 45 of their archive documents on the template furniture
    # alone - so each supersedes it outright, exactly as the promoted
    # sub-dispatches above do. Without these edges those 45 documents would
    # resolve `ambiguous` and go to review.
    #
    # The edges are safe in the strong sense, not the observed one: each of the
    # four identifies its issuer by markers the general reader does not consult
    # at all, so the general reader can never shadow one of them, and none of
    # them can reach an issuer it was not registered for. Measured over the
    # archive: mission_valley 36, dakota_west 3, midflorida 3,
    # first_community 3, and not one of the four ever claims a document and
    # then declines it, so no edge can strand a document either.
    "mission_valley": {"band": 10, "supersedes": frozenset({"community_section"})},
    "dakota_west": {"band": 10, "supersedes": frozenset({"community_section"})},
    "midflorida": {"band": 10, "supersedes": frozenset({"community_section"})},
    "first_community": {"band": 10, "supersedes": frozenset({"community_section"})},
    # The same relationship one template over (W3 §SCANB). `first_farmers`
    # reads ONE issuer's running-balance issue of the second core-processor
    # template; `core_processor_sectioned` registers that template generically
    # and claims it on the furniture both printed issues share, so it claims
    # all 7 of this issuer's archive documents too. Without this edge the 6
    # that publish today would resolve `ambiguous` and go to review.
    #
    # The edge is safe in the strong sense, not the observed one: the general
    # reader consults nothing that identifies an issuer, and `first_farmers`
    # requires this issuer's own tele-banking domain and product name, which
    # the general reader cannot reach - so neither can shadow the other by
    # accident. The general reader also declines the running-balance issue at
    # parse, so the edge cannot strand a document either.
    "first_farmers": {"band": 10, "supersedes": frozenset({"core_processor_sectioned"})},
    # BMO prints a second summary block; where the two disagree the document
    # contradicts itself. Registered here so the orchestrator never names BMO.
    "bmo": {"integrity_checks": (bmo.summary_contradictions,)},
    # The other two BMO layouts each print one of their figures twice as well,
    # and each check reads only its own layout's second printing.
    "bmo_ca_business": {
        "integrity_checks": (bmo_ca_business.closing_totals_contradictions,)
    },
    "bmo_ca_business_french": {
        "integrity_checks": (bmo_ca_business.closing_totals_contradictions,)
    },
    "bmo_us_activity": {
        "integrity_checks": (bmo_us_activity.summary_row_contradictions,)
    },
    "td_canada_native": {"band": 10, "supersedes": frozenset({"td_canada"})},
    # Shopify prints the period's net movement and closing balance twice: in
    # the summary block that opens the statement and again in the grid's
    # closing `Totals` row. Where the two disagree the document contradicts
    # itself.
    "shopify_balance": {
        "integrity_checks": (shopify_balance.totals_contradictions,)
    },
    # Citibank reprints the checking product's closing balance in the
    # relationship block at the top of page 1.
    "citibusiness": {
        "integrity_checks": (citibusiness.closing_balance_contradictions,)
    },
    # A Zions statement of several accounts prints each closing balance and
    # their total; the total is what says the accounts read as inert were.
    "zions": {"integrity_checks": (zions.balance_summary_contradictions,)},
    # Square prints its activity count beside the two balances of the same
    # summary row, so a ledger that does not match it contradicts the document.
    "square_checking": {
        "integrity_checks": (square_checking.activity_count_contradictions,)
    },
    # Mercury closes its grid with the statement balance printed a second time
    # and states its own period length in days; neither is used to build the
    # statement, so both are free second opinions.
    "mercury": {"integrity_checks": (mercury.printed_total_contradictions,)},
    # Found prints its period twice: in the header block, and inside the label
    # of each summary balance.
    "found_lead": {"integrity_checks": (found_lead.printed_period_contradictions,)},
    # The month-to-date view. `formal_statement=False` is not our judgement of
    # the document — it is the issuer's, printed on the document itself, and
    # the notes below quote it. The consequence is the one the registry already
    # defines for a Chase transaction export: the figures are published, the
    # quality level is `needs_review`, and a human approves or does not.
    "found_lead_activity": {
        "integrity_checks": (found_lead.printed_period_contradictions,),
        "formal_statement": False,
        "informal_quality_note": (
            "Found month-to-date activity view; the issuer states it is not a bank "
            "statement and that pending transactions are shown but excluded from the balance"
        ),
        "informal_integrity_note": (
            "document declares itself not a bank statement and covers a partial period"
        ),
    },
    # Brex prints each direction's total three times — the summary group row,
    # its detail row, and the closing total of the matching activity grid — and
    # prints every posting in a grid whose heading declares its direction
    # independently of the sign on the amount.
    "brex": {"integrity_checks": (brex.printed_total_contradictions,)},
}

_loaded = False


def load() -> tuple[Registration, ...]:
    """Populate the registry once, and validate it. Idempotent."""
    global _loaded
    if _loaded:
        return registrations()

    for parser_id, bank, module, markers_attr, normalize_attr, parse_attr in _ENTRIES:
        register(
            Registration(
                id=parser_id,
                bank=bank,
                markers=tuple(getattr(module, markers_attr)),
                normalize=getattr(module, normalize_attr) if normalize_attr else None,
                parse=getattr(module, parse_attr),
                **_OVERRIDES.get(parser_id, {}),
            )
        )
    validate_registry()
    _loaded = True
    return registrations()


load()
