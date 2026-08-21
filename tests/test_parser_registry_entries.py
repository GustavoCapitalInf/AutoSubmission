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
    # The issuer-specific reader of the THIRD core-processor template's
    # running-balance issue, which `core_processor_daily` now registers
    # generically (W3 §LCPERIOD).
    "b1",
    "chase_export",
    "chase_savings",
    # The four issuer-specific readers of the core-processor template that
    # `community_section` now registers generically (W3 §JHA-CELL).
    "dakota_west",
    "first_community",
    # The issuer-specific reader of the SECOND core-processor template's
    # running-balance issue, which `core_processor_sectioned` now registers
    # generically (W3 §SCANB).
    "first_farmers",
    "midflorida",
    "mission_valley",
    "rbc_french",
    "td_canada_native",
    # band 100 — everything else, alphabetically
    "altana",
    "american_express",
    "apex_scanned",
    "atb",
    "balance_by_date",
    "banco_popular",
    "bank_of_america",
    "bluevine",
    "bmo",
    "bmo_ca_business",
    "bmo_ca_business_french",
    "bmo_us_activity",
    "brex",
    "burke_herbert",
    "capital_one",
    "chase",
    "cibc",
    "cibc_french",
    "citibusiness",
    "citizens",
    "columbia_bank",
    "community_section",
    "consumers",
    # The fourth summary grammar of the third core processor (W3 §GRAM4).
    # Disjoint from `core_processor_daily` below by its two required markers,
    # not by precedence, so it takes the ordinary band.
    "core_processor_counted",
    "core_processor_daily",
    "core_processor_sectioned",
    "demo_national",
    "desjardins",
    "farmers_merchants",
    "fifth_third",
    "first_citizens",
    "fiserv_premier",
    "found_lead",
    "found_lead_activity",
    "huntington",
    "ibc",
    "linkbank",
    "mercury",
    "navigant",
    "navy_federal",
    "pnc",
    "rbc",
    "regions",
    "relay",
    "releve_facturation",
    "santander",
    "scotiabank",
    "secu",
    "shopify_balance",
    "southside_scanned",
    "square_checking",
    "symitar",
    "td_canada",
    "td_canada_french",
    "td_us",
    "texas_bank",
    "truist",
    "us_bank",
    "wealthsimple",
    "wells_fargo",
    "wilson_muir",
    "woodforest",
    "zions",
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
    BMO layouts (W3 §BMO-LAYOUTS), the Square Checking layout
    (W3 §CHASE-LAYOUTS), the Chase savings product (W3 §CHASE-CLOSURE), the
    TD Canada Trust French layout (W3 §TD-FRENCH), the English CIBC
    layout (W3 §RBCCIBC), and the batch-3 train: Huntington and the
    Burke & Herbert grid (W3 §HUNT-CELL); Shopify Balance, CitiBusiness
    and the Zions Bancorporation Statement of Accounts (W3 §CITI3);
    Mercury, Brex, and Found's two documents — the closed statement and
    the month-to-date view the issuer prints a disclaimer on
    (W3 §FINTECH); and the Woodforest, Wealthsimple and Symitar layouts
    (W3 §UNID-PACK-A); and the Fifth Third commercial print stream and
    the Fiserv Premier parenthesised-counts issue (W3 §UNID-B); and the issuer-agnostic core-processor template
    (W3 §JHA-CELL); the French-language `Relevé de compte` template whose
    documents name no institution at all (W3 §UNKISSUER, UB5); the second
    core processor's sectioned template, likewise issuer-agnostic
    (W3 §SCANB); and the four-way partitioned-summary core-processor
    template (W3 §SCANC); and the batch-5 train: the THIRD core processor's
    template, whose period sentence is the only thing it shares with the
    second's and which prints no institution field at all (W3 §LCPERIOD);
    and the batch-6 card: that third processor's FOURTH summary grammar,
    whose summary is a counted partition and whose two balances are dated
    (W3 §GRAM4)."""
    assert len(pr.registrations()) == 73


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
        "community_section": "detect_platform",
        "southside_scanned": "detect_southside",
        "apex_scanned": "detect_apex",
        "found_lead_activity": "activity_detect",
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
def test_each_registrations_normalization_returns_an_exact_str(registration):
    """The conformance side of the sweep's interning contract.

    `PreparedDocument` interns each normalization's output so that two
    registrations agreeing on a document share one string — which trusts the
    value the normalizer returns. An unhashable return would raise where the
    or-chain merely handed the object to the markers, and a `str` subclass
    carrying its own `__eq__`/`__hash__` could compare equal to another
    normalizer's text and be silently swapped for it. The seam already refuses
    to intern anything that is not an exact `str`, so neither can happen; this
    is the assertion that says no registered normalizer ever needs that
    fallback, which is the stronger and more useful statement.

    Checked here rather than in `validate_registry` deliberately: the check
    needs a document to run the normalizer on, and `validate_registry` runs at
    import of `analysis.parser_registry_entries` — putting every parser's
    normalization on the import path of `analysis` to satisfy a type contract
    is a worse trade than a test that runs in milliseconds.
    """
    if registration.normalize is None:
        pytest.skip("no normalization")
    for document in ("", "nothing here", "Statement of account",
                     "BANK OF AMERICA ACCOUNT SUMMARY", "<!-- SOURCE: x.pdf -->\nAccount"):
        produced = registration.normalize(document)
        assert type(produced) is str, (
            f"{registration.id}: normalize returned {type(produced).__name__}, "
            "not an exact str — the sweep cannot intern it (see "
            "PreparedDocument.text_for)"
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
        # W3 §LCPERIOD: the same relationship a THIRD template over.
        # `core_processor_daily` registers the third core-processor template on
        # the period furniture its two printed issues share, so it claims every
        # document of the issuer whose running-balance issue `b1` reads.
        # Evidence, measured over the D-3 artifact store (3,396 documents with
        # offline text) and named in the commit message: the general reader
        # detects exactly the 20 documents that print the template, of which
        # `b1` holds 3 — all three validated today. Without the edge those 3
        # resolve `ambiguous`, which is a regression. All three are ALSO in the
        # pinned corpus (`Others/B1/`), measured both ways: with the edge the
        # claimant set is exactly `['b1']`, without it all three are
        # `ambiguous` and the gate's per-document verdict check goes red.
        "b1": ["core_processor_daily"],
        "chase_export": ["chase"],
        # W3 §CHASE-CLOSURE: `chase` detects every Chase savings statement on
        # its own two markers and declines all of them at parse. The evidence
        # for this edge is the 10 savings documents of the
        # `Chase x failed x chase:0.5` cell in discovery run `6893a75b`, named
        # in the commit message; there is no such document in the pinned corpus.
        "chase_savings": ["chase"],
        # W3 §JHA-CELL: `community_section` registers the core-processor
        # template these four issuers print, and claims it on the template
        # furniture alone — so it claims every one of their documents too.
        # Evidence for the edges, measured over discovery run `88be9dd3` and
        # named in the commit message: the general reader detects exactly the
        # 115 archive documents that print the template, of which
        # mission_valley holds 36, dakota_west 3, midflorida 3 and
        # first_community 3. Without the edges those 45 resolve `ambiguous`.
        # The pinned corpus holds one document of each of the four.
        "dakota_west": ["community_section"],
        "first_community": ["community_section"],
        # W3 §SCANB: the same relationship one template over.
        # `core_processor_sectioned` registers the SECOND core-processor
        # template on the furniture its two printed issues share, so it claims
        # every document of the issuer whose running-balance issue
        # `first_farmers` reads. Evidence, measured over the D-3 artifact store
        # (3,396 documents with offline text, run of record `d5c75ff6`) and
        # named in the commit message: the general reader detects exactly the
        # 39 documents that print the template, of which first_farmers holds 7
        # (6 validated, 1 that first_farmers itself declines). Without the edge
        # those 6 resolve `ambiguous`. The pinned corpus holds one of them.
        "first_farmers": ["core_processor_sectioned"],
        "midflorida": ["community_section"],
        "mission_valley": ["community_section"],
        "rbc_french": ["rbc"],
        "td_canada_native": ["td_canada"],
    }, (
        "supersedes edges changed; each new edge needs the corpus document that "
        "proved it necessary, recorded in the commit message"
    )


def test_the_registrations_that_are_not_formal_statements_are_exactly_these_two():
    """`formal_statement=False` is a claim about a DOCUMENT CLASS, and it costs
    every document of that class its automatic approval — so the set is pinned
    literally and grows only with the evidence that justified each member.

    * `chase_export` — an online transaction export with no summary and no
      period (R-3).
    * `found_lead_activity` — a month-to-date view carrying the issuer's own
      printed sentence that it "is not a bank statement and therefore should
      not be relied upon as a bank statement" (W3 §FINTECH). This is not our
      reading of a partial period: it is the document's own declaration, and
      it appears on 3 of the 15 surveyed Found documents and on none of the 12
      closed statements.
    """
    informal = {reg.id for reg in pr.registrations() if not reg.formal_statement}
    assert informal == {"chase_export", "found_lead_activity"}
