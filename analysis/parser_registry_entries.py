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
    core_processor_activity_summary,
    core_processor_counted,
    core_processor_daily,
    core_processor_sectioned,
    core_processor_signed_counts,
    demo_national,
    desjardins,
    eq_bank_scanned,
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
    welch_state_bank,
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
    # A core processor's `Activity Summary` running-balance issue (W3
    # §COREISS2, census rank 11). Registered as a SIBLING rather than as an
    # extension of any of the four readers of the LEADING-counts summary:
    # three of those (`linkbank`, `farmers_merchants`, `capital_one`) are
    # issuer-keyed and this template prints no institution at all, and the
    # fourth (`fiserv_premier`) requires `Previous Balance` and the
    # PARENTHESISED counts, neither of which this issue prints. `Days in
    # Cycle` inside an `Activity Summary` box is the anti-collision clause
    # against the archive's large `Days in the statement period` cohort, and
    # the two vocabularies meet on 0 of 3,396 documents - so the
    # registrations are disjoint by construction, with no `supersedes` edge
    # and no band, and the conformance cross-product is what holds them
    # apart. The label names the TEMPLATE: what this one prints for an
    # issuer is a letterhead post-office box with its US city, state and ZIP
    # and a telephone number - a jurisdiction, never a name.
    ("core_processor_activity_summary", "Core Processor Activity Summary Platform", core_processor_activity_summary, "DETECTION_MARKERS", "detection_text", "parse_core_processor_activity_summary_statement"),
    # The FOURTH summary grammar of that same third core processor
    # (W3 §GRAM4, carded at §LCPERIOD L7.3). It shares the period SENTENCE
    # with the entry below and prints no `Total days` line, no
    # `Total additions` and no undated `Beginning balance $`: its summary is a
    # counted PARTITION - three printed categories per direction, each with
    # its own count and total - and its two balances are DATED. Those dated
    # balances are the marker that separates it from the three sibling
    # grammars that share its period sentence, so the two registrations are
    # DISJOINT by construction rather than by precedence: no `supersedes` edge
    # and no band, exactly as `td_canada_french` stands beside the English TD
    # layouts, and the conformance cross-product is what holds them apart.
    # The label names the PLATFORM because this template prints no institution
    # field either - what it prints under `Contact us:` is a BRANCH office,
    # which is where §LCPERIOD L4's evidence came from.
    ("core_processor_counted", "Core Processor Counted Summary Platform", core_processor_counted, "DETECTION_MARKERS", None, "parse_core_processor_counted_statement"),
    # A THIRD core processor's template (W3 §LCPERIOD), registered the same
    # way and for the same reason - the archive prints it under four issuers,
    # one of which already has its own reader. It is NOT a printed variant of
    # the sectioned template below: it shares that template's period VOCABULARY
    # and not one of its grammars (sentence case, long-form dates, totals with
    # no counts, `mm-dd` rows, its own section names). The label names the
    # PLATFORM because this template prints no institution FIELD at all -
    # `Statement.bank` is None on every document it publishes, under the
    # honest-unknown-issuer ruling.
    ("core_processor_daily", "Core Processor Daily Balances Platform", core_processor_daily, "DETECTION_MARKERS", None, "parse_core_processor_daily_statement"),
    # A SECOND core processor's template, registered the way W3 §JHA-CELL
    # established for the first: on the template's own furniture, with the
    # issuer read out of each document and published as `Statement.bank`. The
    # label here names the PLATFORM - the archive prints this template under
    # five different issuers, several of which print their name only inside a
    # logo, and inventing one would be the hardcode this registration exists to
    # avoid.
    ("core_processor_sectioned", "Core Processor Sectioned Platform", core_processor_sectioned, "DETECTION_MARKERS", "detection_text", "parse_core_processor_sectioned_statement"),
    # A core processor's SIGNED-COUNTS issue (W3 §COREISS2, census rank 5).
    # The census filed it as `fiserv_premier`'s parenthesised-counts issue and
    # it is a SIBLING instead: of that registration's three required markers
    # this issue prints only `Statement of Account`, and the two it does not
    # print include the ANTI-COLLISION clause (`Previous Balance`) that keeps
    # 216 Wells Fargo documents out of it. Its own summary states each
    # direction's count in parentheses with a SIGNED total, over two DATED
    # balances - measured on 8 of 3,396 documents, and on none of
    # `fiserv_premier`'s fourteen. Disjoint by construction, so no
    # `supersedes` edge and no band. The label names the TEMPLATE: this one
    # prints no institution anywhere in its text layer.
    ("core_processor_signed_counts", "Core Processor Signed Counts Platform", core_processor_signed_counts, "DETECTION_MARKERS", "detection_text", "parse_core_processor_signed_counts_statement"),
    ("dakota_west", "Dakota West Credit Union", community_section, "DAKOTA_WEST_DETECTION_MARKERS", None, "parse_dakota_west_statement"),
    ("demo_national", "Demo National Bank", demo_national, "DETECTION_MARKERS", None, "parse_demo_national_statement"),
    ("desjardins", "Desjardins", desjardins, "DETECTION_MARKERS", None, "parse_desjardins_statement"),
    # A scanned Canadian direct-bank statement (W3 §TANGERINE). The SN3 census
    # filed this family under the working name `tangerine`; the cached OCR
    # text of all five archive documents names THIS issuer instead, and the
    # string "tangerine" occurs in none of them — so the label here is the one
    # the page furniture prints (contact domain, head-office footer,
    # copyright line), as always. `Statement.currency` is deliberately left at
    # the schema default: see the §CURRENCY note in the parser's module.
    ("eq_bank_scanned", "EQ Bank", eq_bank_scanned, "EQ_BANK_DETECTION_MARKERS", "detection_text", "parse_eq_bank_scanned_statement"),
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
    # A THIRD scanned small-bank reader in the same module as `apex_scanned`
    # and `southside_scanned` (W3 §SCANNEXT). The issuer IS printed here - in
    # the page furniture of every page - so `Statement.bank` names it, unlike
    # the core-processor templates above.
    ("texas_first_scanned", "Texas First Bank", scanned_small_bank, "TEXAS_FIRST_DETECTION_MARKERS", "detection_text", "parse_texas_first_scanned_statement"),
    ("truist", "Truist", truist, "DETECTION_MARKERS", None, "parse_truist_statement"),
    ("us_bank", "U.S. Bank", us_bank, "DETECTION_MARKERS", None, "parse_us_bank_statement"),
    ("wealthsimple", "Wealthsimple", wealthsimple, "DETECTION_MARKERS", None, "parse_wealthsimple_statement"),
    # A one-institution registration whose evidence is the masthead the
    # bank prints on every page: its home-office PO box and the
    # multi-branch contact ladder beside it. The wordmark is printed only
    # on the trailing check-image page, which not every statement has
    # (W3 §WELCH).
    ("welch_state_bank", "Welch State Bank", welch_state_bank, "WELCH_DETECTION_MARKERS", None, "parse_welch_state_bank_statement"),
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
    # The same relationship a THIRD template over (W3 §LCPERIOD). `b1` reads
    # ONE issuer's running-balance issue of the third core-processor template;
    # `core_processor_daily` registers that template generically and claims it
    # on the period furniture BOTH printed issues share, so it claims all 3 of
    # this issuer's archive documents too. Without this edge those 3 - all
    # validated today - resolve `ambiguous` and go to review, which is a
    # regression.
    #
    # The edge is safe in one direction in the STRONG sense and in the other
    # in the OBSERVED one, and the difference is worth stating: the general
    # reader consults nothing that identifies an issuer at all (it publishes
    # `bank=None` by construction), and `b1` requires this issuer's own name,
    # which the general reader never looks for - so neither can shadow the
    # other by accident.
    #
    # Stranding is the observed half. Every archive document `b1` claims is
    # the running-balance issue, which the general reader declines at parse
    # anyway (it prints no `Total additions` summary), so no document is lost
    # today. A document carrying `b1`'s markers AND a sectioned summary would
    # be routed to `b1` and never offered to the reader that could publish it
    # - the archive holds none, and the same is true of every supersedes edge
    # already shipped. Named, not claimed away.
    #
    # The PINNED CORPUS holds all three, and the edge is load-bearing there:
    # with it the claimant set is exactly `['b1']` on each; without it all
    # three resolve `ambiguous` and the gate's per-document verdict check goes
    # red. Measured both ways.
    "b1": {"band": 10, "supersedes": frozenset({"core_processor_daily"})},
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
    # Columbia's Daily Balances grid reprints, for a subset of the period's
    # days, a balance the ledger above it already determines. The reader
    # publishes the printed CELL and never its own arithmetic, so where the two
    # disagree the document contradicts itself and the disagreement is the
    # finding (W3 §REPAIRDOC). Registered rather than resolved in the parser:
    # preferring the reconstruction is exactly what this card removed.
    "columbia_bank": {
        "integrity_checks": (columbia_bank.daily_grid_contradictions,)
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
    # EQ Bank posts the following cycle's opening interest credit into this
    # statement, dates it `period_end + 1`, and includes it in its own printed
    # closing balance. The page states the size of that accrual twice more —
    # the `Total interest earned` term, and the gap between the printed closing
    # balance and the balance the in-period ledger reaches. Where the three
    # disagree the page contradicts itself about what those trailing rows are.
    # (The seam that would let `adb.py` publish these averages is Gustavo's
    # bundled ruling, W3 §TANGERINE TG9 + TG10, and is not implemented.)
    "eq_bank_scanned": {
        "integrity_checks": (eq_bank_scanned.closing_accrual_contradictions,)
    },
    # Citizens prints a total for each of its three activity sections beside
    # the balance strip. Where the strict and the widened reading of a section
    # BOTH disagree with it the reader keeps the strict one and said nothing —
    # including on one archive statement where the strict cheque grid takes
    # more money than the page states (W3 §SCANFINISH SF10 1b, closed as part
    # of SCAN-HYGIENE). Which section, and in which direction, is the finding.
    "citizens": {
        "integrity_checks": (citizens.printed_section_total_contradictions,)
    },
    # Southside's `DAILY BALANCE SUMMARY` prints an end-of-day balance for each
    # day the account moved, so consecutive cells partition the period and each
    # step is the bank's own statement of what the account did between them.
    # The reader consults that grid about DATES and never asked it about
    # AMOUNTS — the gap that let one archive statement publish a FOUR-FIGURE
    # amount more debit money than the bank states (W3 §SCANFINISH SF2, closed here as
    # SS-GRID-AMOUNTS). Registered rather than resolved in the parser, for the
    # repair doctrine's reason: neither printing is preferred.
    "southside_scanned": {
        "integrity_checks": (scanned_small_bank.daily_grid_amount_contradictions,)
    },
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
