"""The registry's contents are complete, consistent, and ordered by data.

Fast and offline — no corpus document is read. This is the file that fails when
someone adds a parser and forgets to register it, or registers it twice, or
lets a module's `detect` drift away from the `Registration` that represents it.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis import parser_registry as pr
from analysis import parser_registry_entries as entries

ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "analysis"

#: Dispatch order, written out. It is a pure function of `(band, id)` over the
#: registration data, so it can be asserted literally — which is the whole
#: point of R-3: the routing contract is readable and reviewable, instead of
#: being the line order of a 43-term boolean expression.
EXPECTED_ORDER = [
    # band 10 — narrower document classes that supersede their general form
    "chase_export",
    "rbc_french",
    "td_canada_native",
    # band 100 — everything else, alphabetically
    "altana",
    "american_express",
    "apex_scanned",
    "atb",
    "b1",
    "banco_popular",
    "bank_of_america",
    "bluevine",
    "bmo",
    "bmo_ca_business",
    "bmo_ca_business_french",
    "bmo_us_activity",
    "capital_one",
    "chase",
    "cibc_french",
    "citizens",
    "columbia_bank",
    "consumers",
    "dakota_west",
    "demo_national",
    "desjardins",
    "farmers_merchants",
    "first_citizens",
    "first_community",
    "first_farmers",
    "ibc",
    "linkbank",
    "midflorida",
    "mission_valley",
    "navigant",
    "navy_federal",
    "pnc",
    "rbc",
    "regions",
    "relay",
    "santander",
    "scotiabank",
    "secu",
    "southside_scanned",
    "square_checking",
    "td_canada",
    "td_us",
    "texas_bank",
    "truist",
    "us_bank",
    "wells_fargo",
    "wilson_muir",
]


def test_dispatch_order_is_exactly_this_list():
    assert [reg.id for reg in pr.registrations()] == EXPECTED_ORDER


def test_dispatch_order_is_derived_from_band_and_id_alone():
    keys = [reg.sort_key for reg in pr.registrations()]
    assert keys == sorted(keys)


def test_the_registry_validates():
    pr.validate_registry()


def test_every_parse_entry_point_in_analysis_is_registered():
    """Counts the `parse_*_statement` functions on disk and demands one
    registration each. Adding parser #47 without registering it fails here."""
    on_disk = set()
    for path in sorted(ANALYSIS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("parse_") and node.name.endswith("_statement"):
                on_disk.add((path.name, node.name))
    registered = {
        (Path(module.__file__).name, parse_attr)
        for _id, _bank, module, _markers, _norm, parse_attr in entries._ENTRIES
    }
    # The three promoted sub-dispatches register public aliases of private
    # functions, so they are registered under a name `ast` does not see as a
    # module-level `parse_*_statement` def; exclude them from the disk side.
    aliases = {"parse_chase_export_statement", "parse_rbc_french_statement", "parse_native_td_canada_statement"}
    missing = on_disk - registered
    assert not missing, f"parse entry points with no registration: {sorted(missing)}"
    unknown = {name for _file, name in registered} - {name for _file, name in on_disk} - aliases
    assert not unknown, f"registrations naming unknown parse functions: {sorted(unknown)}"


def test_registration_count_matches_the_documented_decision_points():
    """43 registry entry points, the three promoted sub-dispatches, the three
    BMO layouts (W3 §BMO-LAYOUTS) and the Square Checking layout
    (W3 §CHASE-LAYOUTS), both opened by the unclaimed-layout phase."""
    assert len(pr.registrations()) == 50


def test_ids_and_bank_labels_are_unique_enough_to_dispatch_on():
    ids = [reg.id for reg in pr.registrations()]
    assert len(set(ids)) == len(ids)
    # Bank labels may repeat (a layout variant of the same bank); the lookup
    # resolves deterministically by (band, id), so pin what it resolves to.
    assert pr.by_bank_label("TD Canada Trust").id == "td_canada_native"
    # Four registrations now carry the BMO label. The lookup is used only for
    # documents no parser claimed, and it must keep resolving to the same one.
    assert pr.by_bank_label("BMO").id == "bmo"
    assert pr.by_bank_label("Chase Transaction Export").id == "chase_export"
    assert pr.by_bank_label("Chase").id == "chase"


@pytest.mark.parametrize("registration", pr.registrations(), ids=lambda r: r.id)
def test_each_registration_detects_the_same_way_its_module_does(registration):
    """`Registration.detect` and the parser module's `detect` must be one
    computation, not two copies of it."""
    module = next(
        module for _id, _bank, module, _m, _n, _p in entries._ENTRIES if _id == registration.id
    )
    module_detect = {
        "chase_export": "detect_export",
        "rbc_french": "detect_french",
        "td_canada_native": "detect_native",
        "mission_valley": "detect_mission_valley",
        "dakota_west": "detect_dakota_west",
        "southside_scanned": "detect_southside",
        "apex_scanned": "detect_apex",
    }.get(registration.id, "detect")
    detect = getattr(module, module_detect)
    for document in ("", "nothing here", "Statement of account", "BANK OF AMERICA ACCOUNT SUMMARY"):
        detection = registration.detect(document)
        # The return TYPE is part of the contract: W3-1's seam scores anything
        # else as 0.0 without recording a failure (it did not raise, so there
        # is no exception class to name), which would make a broken detect look
        # like a document nobody recognised. This is where that is caught.
        assert isinstance(detection, pr.Detection), f"{registration.id}: detect returned {detection!r}"
        assert detection == detect(document), (
            f"{registration.id}: registration and {module.__name__}.{module_detect} disagree"
        )


@pytest.mark.parametrize("registration", pr.registrations(), ids=lambda r: r.id)
def test_each_registration_declares_at_least_one_required_marker(registration):
    kinds = {marker.kind for marker in registration.markers}
    assert "required" in kinds or "exclusive" in kinds, (
        f"{registration.id} can never claim: markers are {kinds}"
    )


@pytest.mark.parametrize("registration", pr.registrations(), ids=lambda r: r.id)
def test_no_registration_claims_an_empty_or_unrelated_document(registration):
    """The cheapest possible detection-negative: nothing claims nothing."""
    for document in ("", "   ", "This document is a lease agreement, not a bank statement."):
        assert not registration.detect(document).claims, (
            f"{registration.id} claims {document!r}"
        )


def test_marker_ids_are_unique_within_a_registration():
    for registration in pr.registrations():
        ids = [marker.id for marker in registration.markers]
        assert len(set(ids)) == len(ids), f"{registration.id} repeats a marker id"


def test_only_the_promoted_sub_dispatches_supersede_anything():
    superseding = {reg.id: sorted(reg.supersedes) for reg in pr.registrations() if reg.supersedes}
    assert superseding == {
        "chase_export": ["chase"],
        "rbc_french": ["rbc"],
        "td_canada_native": ["td_canada"],
    }, (
        "supersedes edges changed; each new edge needs the corpus document that "
        "proved it necessary, recorded in the commit message"
    )


def test_only_the_chase_export_is_not_a_formal_statement():
    informal = {reg.id for reg in pr.registrations() if not reg.formal_statement}
    assert informal == {"chase_export"}
