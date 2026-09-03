"""P22-HOLDOUT case 21: the unseen holdout cage.

`holdout.jsonl` in the sealed store: strata fields; status transitions
`unseen -> evaluated` (the evaluation tool only), `evaluated -> burned`
(explicit, with the card name), `evaluated -> graduated` (only against an
existing freeze tag with the engine-version attestation); anything else
refuses; a development-corpus sha is refused at add time; the refusal set
covers every item regardless of status. All shas synthetic.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.holdout import manifest as manifest_mod
from tools.holdout.manifest import (
    HoldoutManifest,
    HoldoutRefusal,
    TransitionError,
    build_strata,
    page_count_bucket,
)
from tools.holdout.store import ChainError, StoreLocationError

ROOT = Path(__file__).resolve().parents[1]


def synthetic_sha(label: str) -> str:
    return hashlib.sha256(f"synthetic-holdout:{label}".encode()).hexdigest().upper()


DEV_CORPUS = frozenset(synthetic_sha(f"dev-{i}") for i in range(5))
FREEZE_TAGS = frozenset({"batch9-final", "phase2.1-final"})


def strata(**overrides) -> dict:
    fields = dict(
        modality="digital", bank_familiarity="unknown_bank", account_shape="single",
        table_shape="table_heavy", currency="USD", page_count=4, layout_family_code="fam_a",
    )
    fields.update(overrides)
    return build_strata(**fields)


@pytest.fixture
def manifest(tmp_path, monkeypatch) -> HoldoutManifest:
    monkeypatch.setenv("SEALED_TRUTH_DIR", str(tmp_path / "sealed"))
    return HoldoutManifest.open()


def add(manifest: HoldoutManifest, label: str = "h-a", **overrides) -> dict:
    return manifest.add(
        content_sha256=synthetic_sha(label), source_batch="unseen-2031-01",
        strata=strata(), dev_corpus_shas=DEV_CORPUS, **overrides,
    )


def evaluate(manifest: HoldoutManifest, item: dict, version: str = "engine-v1") -> dict:
    return manifest.record_evaluation(
        item["holdout_id"], engine_version=version, evaluation_run_id="run-synthetic-1",
    )


# --- location and shape -----------------------------------------------------


def test_lives_only_under_the_sealed_dir(monkeypatch):
    monkeypatch.delenv("SEALED_TRUTH_DIR", raising=False)
    with pytest.raises(StoreLocationError):
        HoldoutManifest.open()
    monkeypatch.setenv("SEALED_TRUTH_DIR", str(ROOT / "holdout_probe"))
    with pytest.raises(StoreLocationError):
        HoldoutManifest.open()


def test_add_records_every_strata_field_and_the_attestation(manifest, tmp_path):
    item = add(manifest)
    assert item["holdout_id"] == "H000001"
    assert item["content_sha256"] == synthetic_sha("h-a")
    assert item["source_batch"] == "unseen-2031-01"
    assert item["not_in_dev_corpus"] is True
    assert item["status"] == "unseen"
    assert item["added_at"].endswith("+00:00")
    assert item["last_evaluated_at"] is None
    assert item["last_engine_version"] is None
    assert item["burned_by"] is None
    assert item["graduated_at_tag"] is None
    assert item["strata"] == {
        "modality": "digital", "bank_familiarity": "unknown_bank", "account_shape": "single",
        "table_shape": "table_heavy", "currency": "USD", "page_count_bucket": "2-5",
        "layout_family_code": "fam_a",
    }
    assert (tmp_path / "sealed" / "holdout.jsonl").is_file()
    assert manifest.verify_chain() != manifest_mod.GENESIS


def test_the_holdout_file_is_a_hash_chain_of_events(manifest, tmp_path):
    item = add(manifest)
    evaluate(manifest, item)
    events = manifest.events()
    assert [e["event"] for e in events] == ["added", "evaluated"]
    assert events[1]["prev"] == events[0]["hash"]
    path = tmp_path / "sealed" / "holdout.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["status"] = "graduated"
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ChainError):
        manifest.verify_chain()
    with pytest.raises(ChainError):
        manifest.items()


# --- the development corpus is refused --------------------------------------


def test_a_development_corpus_sha_is_refused(manifest):
    dev = sorted(DEV_CORPUS)[0]
    with pytest.raises(HoldoutRefusal):
        manifest.add(content_sha256=dev, source_batch="unseen-2031-01", strata=strata(),
                     dev_corpus_shas=DEV_CORPUS)
    with pytest.raises(HoldoutRefusal):
        manifest.add(content_sha256=dev.lower(), source_batch="unseen-2031-01", strata=strata(),
                     dev_corpus_shas=DEV_CORPUS)
    assert manifest.items() == {}


def test_the_dev_corpus_set_is_required_not_defaulted(manifest):
    with pytest.raises(TypeError):
        manifest.add(content_sha256=synthetic_sha("h-a"), source_batch="unseen-2031-01",
                     strata=strata())
    with pytest.raises(HoldoutRefusal):
        manifest.add(content_sha256=synthetic_sha("h-a"), source_batch="unseen-2031-01",
                     strata=strata(), dev_corpus_shas=set())  # an empty attestation set is no attestation


def test_a_duplicate_sha_is_refused(manifest):
    add(manifest)
    with pytest.raises(HoldoutRefusal):
        add(manifest)


# --- transitions -------------------------------------------------------------


def test_unseen_to_evaluated_requires_the_engine_version_and_run_id(manifest):
    item = add(manifest)
    with pytest.raises(TransitionError):
        manifest.record_evaluation(item["holdout_id"], engine_version="", evaluation_run_id="r1")
    with pytest.raises(TransitionError):
        manifest.record_evaluation(item["holdout_id"], engine_version="engine-v1", evaluation_run_id="")
    updated = evaluate(manifest, item)
    assert updated["status"] == "evaluated"
    assert updated["last_engine_version"] == "engine-v1"
    assert updated["last_evaluated_at"].endswith("+00:00")
    assert updated["evaluation_run_id"] == "run-synthetic-1"
    # A later evaluation is allowed and records the new version.
    again = evaluate(manifest, item, version="engine-v2")
    assert again["status"] == "evaluated" and again["last_engine_version"] == "engine-v2"


def test_evaluated_to_burned_requires_the_card_name(manifest):
    item = add(manifest)
    evaluate(manifest, item)
    with pytest.raises(TransitionError):
        manifest.burn(item["holdout_id"], burned_by="")
    burned = manifest.burn(item["holdout_id"], burned_by="P24-LAYOUT")
    assert burned["status"] == "burned" and burned["burned_by"] == "P24-LAYOUT"


def test_graduation_requires_an_existing_freeze_tag_and_the_attestation(manifest):
    item = add(manifest)
    evaluate(manifest, item)
    hid = item["holdout_id"]
    with pytest.raises(TransitionError):
        manifest.graduate(hid, graduated_at_tag="phase9.9-final", freeze_tags=FREEZE_TAGS,
                          attest_engine_version_unchanged=True, attested_by="principal_adjudicator")
    with pytest.raises(TransitionError):
        manifest.graduate(hid, graduated_at_tag="phase2.1-final", freeze_tags=FREEZE_TAGS,
                          attest_engine_version_unchanged=False, attested_by="principal_adjudicator")
    with pytest.raises(TransitionError):
        manifest.graduate(hid, graduated_at_tag="phase2.1-final", freeze_tags=set(),
                          attest_engine_version_unchanged=True, attested_by="principal_adjudicator")
    graduated = manifest.graduate(hid, graduated_at_tag="phase2.1-final", freeze_tags=FREEZE_TAGS,
                                  attest_engine_version_unchanged=True,
                                  attested_by="principal_adjudicator")
    assert graduated["status"] == "graduated"
    assert graduated["graduated_at_tag"] == "phase2.1-final"
    assert graduated["graduation_attestation"] == {
        "engine_version_unchanged_because_of_item": True,
        "attested_by": "principal_adjudicator",
        "engine_version": "engine-v1",
    }


@pytest.mark.parametrize(
    "path",
    [
        ("unseen", "burned"),
        ("unseen", "graduated"),
        ("burned", "evaluated"),
        ("burned", "graduated"),
        ("graduated", "evaluated"),
        ("graduated", "burned"),
    ],
)
def test_every_other_transition_refuses(manifest, path):
    start, target = path
    item = add(manifest)
    hid = item["holdout_id"]
    if start in ("burned", "graduated"):
        evaluate(manifest, item)
    if start == "burned":
        manifest.burn(hid, burned_by="P24-LAYOUT")
    if start == "graduated":
        manifest.graduate(hid, graduated_at_tag="batch9-final", freeze_tags=FREEZE_TAGS,
                          attest_engine_version_unchanged=True, attested_by="principal_adjudicator")
    assert manifest.items()[hid]["status"] == start
    with pytest.raises(TransitionError):
        if target == "evaluated":
            evaluate(manifest, item)
        elif target == "burned":
            manifest.burn(hid, burned_by="P24-LAYOUT")
        else:
            manifest.graduate(hid, graduated_at_tag="batch9-final", freeze_tags=FREEZE_TAGS,
                              attest_engine_version_unchanged=True,
                              attested_by="principal_adjudicator")
    assert manifest.items()[hid]["status"] == start


def test_the_transition_matrix_is_exactly_the_ruled_one():
    assert manifest_mod.ALLOWED_TRANSITIONS == frozenset({
        ("unseen", "evaluated"), ("evaluated", "evaluated"),
        ("evaluated", "burned"), ("evaluated", "graduated"),
    })
    assert manifest_mod.HOLDOUT_STATUSES == ("unseen", "evaluated", "burned", "graduated")


def test_there_is_no_generic_status_setter(manifest):
    item = add(manifest)
    for name in ("set_status", "update_status", "transition", "force_status"):
        assert not hasattr(manifest, name), name


# --- the refusal set and the digest material --------------------------------


def test_refusal_set_covers_every_item_regardless_of_status(manifest):
    a = add(manifest, "h-a")
    b = add(manifest, "h-b")
    c = add(manifest, "h-c")
    evaluate(manifest, b)
    evaluate(manifest, c)
    manifest.burn(b["holdout_id"], burned_by="P24-LAYOUT")
    manifest.graduate(c["holdout_id"], graduated_at_tag="batch9-final", freeze_tags=FREEZE_TAGS,
                      attest_engine_version_unchanged=True, attested_by="principal_adjudicator")
    assert manifest.holdout_shas_for_refusal() == frozenset(
        {a["content_sha256"], b["content_sha256"], c["content_sha256"]}
    )
    assert manifest.counts_by_status() == {"unseen": 1, "evaluated": 0, "burned": 1, "graduated": 1}
    assert manifest.sha16_statuses() == sorted(
        [(a["content_sha256"][:16], "unseen"), (b["content_sha256"][:16], "burned"),
         (c["content_sha256"][:16], "graduated")]
    )


# --- strata vocabulary -------------------------------------------------------


@pytest.mark.parametrize("n,bucket", [(1, "1"), (2, "2-5"), (5, "2-5"), (6, "6-15"), (15, "6-15"), (16, "16+"), (400, "16+")])
def test_page_count_buckets(n, bucket):
    assert page_count_bucket(n) == bucket


@pytest.mark.parametrize(
    "bad",
    [
        dict(modality="native"),
        dict(bank_familiarity="known"),
        dict(account_shape="two"),
        dict(table_shape="tables"),
        dict(currency="us dollars"),
        dict(page_count=0),
        dict(layout_family_code="Acme Bank Statement"),
        dict(layout_family_code="ACME"),
    ],
)
def test_strata_are_closed_vocabularies_and_codes(bad):
    with pytest.raises(ValueError):
        strata(**bad)


def test_currency_is_an_upper_iso_code_or_unknown():
    assert strata(currency="cad")["currency"] == "CAD"
    assert strata(currency="unknown")["currency"] == "unknown"
