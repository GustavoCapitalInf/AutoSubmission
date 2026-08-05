"""Ordered registry for deterministic statement parsers.

Parsers remain useful accelerators for certified layouts, but routing should not
depend on a growing boolean expression in the pipeline. Every parser follows the
same contract: return one normalized Statement when its source markers match,
otherwise return None without mutating shared state.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .altana import parse_altana_statement
from .amex import parse_amex_statement
from .atb import parse_atb_statement
from .b1 import parse_b1_statement
from .banco_popular import parse_banco_popular_statement
from .bluevine import parse_bluevine_statement
from .bmo import parse_bmo_statement
from .bofa import parse_bofa_statement
from .capital_one import parse_capital_one_statement
from .chase import parse_chase_statement
from .cibc import parse_cibc_french_statement
from .citizens import parse_citizens_statement
from .columbia_bank import parse_columbia_bank_statement
from .community_section import parse_dakota_west_statement, parse_mission_valley_statement
from .consumers import parse_consumers_statement
from .demo_national import parse_demo_national_statement
from .desjardins import parse_desjardins_statement
from .farmers_merchants import parse_farmers_merchants_statement
from .first_citizens import parse_first_citizens_statement
from .first_community import parse_first_community_statement
from .first_farmers import parse_first_farmers_statement
from .ibc import parse_ibc_statement
from .linkbank import parse_linkbank_statement
from .midflorida import parse_midflorida_statement
from .navigant import parse_navigant_statement
from .navy_federal import parse_navy_federal_statement
from .pnc import parse_pnc_statement
from .rbc import parse_rbc_statement
from .regions import parse_regions_statement
from .relay import parse_relay_statement
from .santander import parse_santander_statement
from .scanned_small_bank import parse_apex_scanned_statement, parse_southside_scanned_statement
from .schema import Statement
from .scotia import parse_scotiabank_statement
from .secu import parse_secu_statement
from .td_can import parse_td_canada_statement
from .td_us import parse_td_us_statement
from .texas_bank import parse_texas_bank_statement
from .truist import parse_truist_statement
from .us_bank import parse_us_bank_statement
from .wells import parse_wells_statement
from .wilson_muir import parse_wilson_muir_statement


Parser = Callable[[str], Statement | None]


@dataclass(frozen=True)
class ParserRegistration:
    key: str
    parse: Parser


# Order is part of the routing contract because some institutions share generic
# table vocabulary. More specific layouts stay before broader parsers.
PARSER_REGISTRY: tuple[ParserRegistration, ...] = (
    ParserRegistration("columbia_bank", parse_columbia_bank_statement),
    ParserRegistration("first_farmers", parse_first_farmers_statement),
    ParserRegistration("navigant", parse_navigant_statement),
    ParserRegistration("relay", parse_relay_statement),
    ParserRegistration("td_canada", parse_td_canada_statement),
    ParserRegistration("td_us", parse_td_us_statement),
    ParserRegistration("altana", parse_altana_statement),
    ParserRegistration("american_express", parse_amex_statement),
    ParserRegistration("atb", parse_atb_statement),
    ParserRegistration("b1", parse_b1_statement),
    ParserRegistration("banco_popular", parse_banco_popular_statement),
    ParserRegistration("bluevine", parse_bluevine_statement),
    ParserRegistration("cibc_french", parse_cibc_french_statement),
    ParserRegistration("consumers", parse_consumers_statement),
    ParserRegistration("demo_national", parse_demo_national_statement),
    ParserRegistration("desjardins", parse_desjardins_statement),
    ParserRegistration("ibc", parse_ibc_statement),
    ParserRegistration("mission_valley", parse_mission_valley_statement),
    ParserRegistration("dakota_west", parse_dakota_west_statement),
    ParserRegistration("linkbank", parse_linkbank_statement),
    ParserRegistration("midflorida", parse_midflorida_statement),
    ParserRegistration("navy_federal", parse_navy_federal_statement),
    ParserRegistration("santander", parse_santander_statement),
    ParserRegistration("southside_scanned", parse_southside_scanned_statement),
    ParserRegistration("apex_scanned", parse_apex_scanned_statement),
    ParserRegistration("texas_bank", parse_texas_bank_statement),
    ParserRegistration("truist", parse_truist_statement),
    ParserRegistration("us_bank", parse_us_bank_statement),
    ParserRegistration("rbc", parse_rbc_statement),
    ParserRegistration("scotiabank", parse_scotiabank_statement),
    ParserRegistration("secu", parse_secu_statement),
    ParserRegistration("wells_fargo", parse_wells_statement),
    ParserRegistration("wilson_muir", parse_wilson_muir_statement),
    ParserRegistration("bank_of_america", parse_bofa_statement),
    ParserRegistration("regions", parse_regions_statement),
    ParserRegistration("pnc", parse_pnc_statement),
    ParserRegistration("farmers_merchants", parse_farmers_merchants_statement),
    ParserRegistration("first_community", parse_first_community_statement),
    ParserRegistration("first_citizens", parse_first_citizens_statement),
    ParserRegistration("bmo", parse_bmo_statement),
    ParserRegistration("capital_one", parse_capital_one_statement),
    ParserRegistration("chase", parse_chase_statement),
    ParserRegistration("citizens", parse_citizens_statement),
)


def parse_deterministic_statement(markdown: str) -> Statement | None:
    for registration in PARSER_REGISTRY:
        statement = registration.parse(markdown)
        if statement is not None:
            return statement
    return None
