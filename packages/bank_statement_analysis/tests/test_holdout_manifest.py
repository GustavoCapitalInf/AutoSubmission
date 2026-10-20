"""P22-HOLDOUT case 21: the unseen holdout cage.

`holdout.jsonl` in the sealed store, chained and witnessed by
`holdout_manifest.json`: strata fields; status transitions
`unseen -> evaluated` (the evaluation tool only), `evaluated -> burned`
(explicit, with the card name), `evaluated -> graduated` (only against a
freeze tag — `*-final` — resolved through git, pointing at a commit dated
AFTER the item's last evaluation, with the engine-version attestation);
anything else refuses; the development corpus is asserted ONLY against a
run's `rows.csv` and recorded with its digest; the refusal set covers every
item regardless of status. All shas synthetic.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.holdout import manifest as manifest_mod
from tools.holdout.manifest import (
    DevCorpus,
    HoldoutManifest,
    HoldoutRefusal,
    TagRef,
    TransitionError,
    build_strata,
    dev_corpus_digest,
    dev_corpus_from_rows,
    page_count_bucket,
)
from tools.holdout.store import ChainError, StoreLocationError

ROOT = Path(__file__).resolve().parents[1]


def synthetic_sha(label: str) -> str:
    return hashlib.sha256(f"synthetic-holdout:{label}".encode()).hexdigest().upper()


DEV_SHAS = sorted(synthetic_sha(f"dev-{i}") for i in range(5))
EVALUATED_AT = "2026-01-01T00:00:00+00:00"
FREEZE_TAGS = {
    "batch9-final": TagRef("batch9-final", "a" * 40, "2030-01-01T00:00:00+00:00"),
    "phase2.1-final": TagRef("phase2.1-final", "b" * 40, "2030-06-01T12:00:00-04:00"),
    "old-final": TagRef("old-final", "c" * 40, "2020-01-01T00:00:00+00:00"),
    "notfinal": TagRef("notfinal", "d" * 40, "2030-01-01T00:00:00+00:00"),
}


def write_rows(path: Path, shas) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path", "content_sha256", "outcome_class"])
        writer.writeheader()
        for sha in shas:
            writer.writerow({"relative_path": f"synthetic/{sha[:8]}.pdf", "content_sha256": sha,
                             "outcome_class": "validated"})
        # a duplicate path for the first sha: rows > distinct shas
        if shas:
            writer.writerow({"relative_path": "synthetic/duplicate.pdf", "content_sha256": shas[0],
                             "outcome_class": "failed"})
    return path


def strata(**overrides) -> dict:
    fields = dict(
        modality="digital", bank_familiarity="unknown_bank", account_shape="single",
        table_shape="table_heavy", currency="USD", page_count=4, layout_family_code="fam_a",
    )
    fields.update(overrides)
    return build_strata(**fields)


@pytest.fixture
def dev_corpus(tmp_path) -> DevCorpus:
    return dev_corpus_from_rows(write_rows(tmp_path / "dev_rows.csv", DEV_SHAS))


@pytest.fixture
def manifest(tmp_path, monkeypatch) -> HoldoutManifest:
    monkeypatch.setenv("SEALED_TRUTH_DIR", str(tmp_path / "sealed"))
    return HoldoutManifest.open()


def add(manifest: HoldoutManifest, dev_corpus: DevCorpus, label: str = "h-a", **overrides) -> dict:
    return manifest.add(
        content_sha256=synthetic_sha(label), source_batch="unseen-2031-01",
        strata=strata(), dev_corpus=dev_corpus, **overrides,
    )


def evaluate(manifest: HoldoutManifest, item: dict, version: str = "engine-v1",
             at: str = EVALUATED_AT) -> dict:
    return manifest.record_evaluation(
        item["holdout_id"], engine_version=version, evaluation_run_id="run-synthetic-1", evaluated_at=at,
    )


def graduate(manifest: HoldoutManifest, hid: str, tag: str = "phase2.1-final", **overrides) -> dict:
    kwargs = dict(graduated_at_tag=tag, freeze_tags=FREEZE_TAGS, attest_engine_version_unchanged=True,
                  attested_by="principal_adjudicator")
    kwargs.update(overrides)
    return manifest.graduate(hid, **kwargs)


# --- location and shape -----------------------------------------------------


def test_lives_only_under_the_sealed_dir(monkeypatch):
    monkeypatch.delenv("SEALED_TRUTH_DIR", raising=False)
    with pytest.raises(StoreLocationError):
        HoldoutManifest.open()
    monkeypatch.setenv("SEALED_TRUTH_DIR", str(ROOT / "holdout_probe"))
    with pytest.raises(StoreLocationError):
        HoldoutManifest.open()


def test_add_records_every_strata_field_and_the_attestation(manifest, dev_corpus, tmp_path):
    item = add(manifest, dev_corpus)
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
    assert (tmp_path / "sealed" / "holdout_manifest.json").is_file()
    assert manifest.verify_chain() != manifest_mod.GENESIS
    assert manifest.verify_against_manifest() == manifest.verify_chain()
    assert manifest.manifest()["record_count"] == 1


def test_the_holdout_file_is_a_hash_chain_of_events(manifest, dev_corpus, tmp_path):
    item = add(manifest, dev_corpus)
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


def test_a_truncated_holdout_file_refuses_every_read_and_write(manifest, dev_corpus, tmp_path):
    """Review MAJOR-1 on the holdout chain (M13's killer, manifest side):
    removing the last event would revert an item's status; every read and
    every event emission must refuse, and the witness must survive."""
    item = add(manifest, dev_corpus)
    evaluate(manifest, item)
    manifest.burn(item["holdout_id"], burned_by="P24-LAYOUT")
    path = tmp_path / "sealed" / "holdout.jsonl"
    witness = (tmp_path / "sealed" / "holdout_manifest.json").read_bytes()
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")  # the burn is gone
    before = path.read_bytes()
    with pytest.raises(ChainError):
        manifest.items()
    with pytest.raises(ChainError):
        manifest.by_sha()
    with pytest.raises(ChainError):
        manifest.holdout_shas_for_refusal()
    with pytest.raises(ChainError):
        manifest.burn(item["holdout_id"], burned_by="P24-LAYOUT")
    with pytest.raises(ChainError):
        manifest.record_evaluation(item["holdout_id"], engine_version="engine-v2", evaluation_run_id="r2")
    with pytest.raises(ChainError):
        add(manifest, dev_corpus, "h-b")
    assert path.read_bytes() == before
    assert (tmp_path / "sealed" / "holdout_manifest.json").read_bytes() == witness


# --- the development corpus (MAJOR-3) ---------------------------------------


def test_the_dev_corpus_comes_from_a_rows_csv_and_is_recorded(manifest, dev_corpus, tmp_path):
    assert dev_corpus.size == 5 and dev_corpus.rows == 6  # a duplicate path counts as a row, not a sha
    assert dev_corpus.digest == hashlib.sha256("\n".join(sorted(DEV_SHAS)).encode()).hexdigest()
    assert dev_corpus.digest == dev_corpus_digest(DEV_SHAS)
    assert dev_corpus.source.endswith("/dev_rows.csv")
    item = add(manifest, dev_corpus)
    assert item["dev_corpus"] == {
        "digest": dev_corpus.digest, "size": 5, "rows": 6, "source": dev_corpus.source,
        "recipe": manifest_mod.DEV_CORPUS_DIGEST_RECIPE,
    }
    assert "content_sha256" not in json.dumps(item["dev_corpus"])  # the population itself is not copied


def test_a_development_corpus_sha_is_refused(manifest, dev_corpus):
    for dev in (DEV_SHAS[0], DEV_SHAS[0].lower()):
        with pytest.raises(HoldoutRefusal):
            manifest.add(content_sha256=dev, source_batch="unseen-2031-01", strata=strata(),
                         dev_corpus=dev_corpus)
    assert manifest.items() == {}


def test_the_dev_corpus_is_required_and_must_come_from_rows(manifest, tmp_path):
    with pytest.raises(TypeError):
        manifest.add(content_sha256=synthetic_sha("h-a"), source_batch="unseen-2031-01", strata=strata())
    for bad in (None, set(DEV_SHAS), DEV_SHAS, "x"):
        with pytest.raises(HoldoutRefusal):
            manifest.add(content_sha256=synthetic_sha("h-a"), source_batch="unseen-2031-01",
                         strata=strata(), dev_corpus=bad)
    empty = write_rows(tmp_path / "empty_rows.csv", [])
    with pytest.raises(HoldoutRefusal):
        dev_corpus_from_rows(empty)
    with pytest.raises(HoldoutRefusal):
        dev_corpus_from_rows(tmp_path / "absent.csv")
    no_column = tmp_path / "no_column.csv"
    no_column.write_text("relative_path,sha\nx,y\n", encoding="utf-8")
    with pytest.raises(HoldoutRefusal):
        dev_corpus_from_rows(no_column)
    assert manifest.items() == {}


def test_a_duplicate_sha_is_refused(manifest, dev_corpus):
    add(manifest, dev_corpus)
    with pytest.raises(HoldoutRefusal):
        add(manifest, dev_corpus)


# --- transitions -------------------------------------------------------------


def test_unseen_to_evaluated_requires_the_engine_version_and_run_id(manifest, dev_corpus):
    item = add(manifest, dev_corpus)
    with pytest.raises(TransitionError):
        manifest.record_evaluation(item["holdout_id"], engine_version="", evaluation_run_id="r1")
    with pytest.raises(TransitionError):
        manifest.record_evaluation(item["holdout_id"], engine_version="engine-v1", evaluation_run_id="")
    updated = evaluate(manifest, item)
    assert updated["status"] == "evaluated"
    assert updated["last_engine_version"] == "engine-v1"
    assert updated["last_evaluated_at"] == EVALUATED_AT
    assert updated["evaluation_run_id"] == "run-synthetic-1"
    # A later evaluation is allowed and records the new version.
    again = evaluate(manifest, item, version="engine-v2")
    assert again["status"] == "evaluated" and again["last_engine_version"] == "engine-v2"


def test_evaluated_to_burned_requires_the_card_name(manifest, dev_corpus):
    item = add(manifest, dev_corpus)
    evaluate(manifest, item)
    with pytest.raises(TransitionError):
        manifest.burn(item["holdout_id"], burned_by="")
    burned = manifest.burn(item["holdout_id"], burned_by="P24-LAYOUT")
    assert burned["status"] == "burned" and burned["burned_by"] == "P24-LAYOUT"


def test_graduation_requires_an_existing_freeze_tag_and_the_attestation(manifest, dev_corpus):
    item = add(manifest, dev_corpus)
    evaluate(manifest, item)
    hid = item["holdout_id"]
    with pytest.raises(TransitionError, match="not in the repository"):
        graduate(manifest, hid, tag="phase9.9-final")
    with pytest.raises(TransitionError, match="attestation"):
        graduate(manifest, hid, attest_engine_version_unchanged=False)
    with pytest.raises(TransitionError):
        graduate(manifest, hid, freeze_tags={})
    with pytest.raises(TransitionError):
        graduate(manifest, hid, freeze_tags={"phase2.1-final"})  # a bare set is not git-resolved
    graduated = graduate(manifest, hid)
    assert graduated["status"] == "graduated"
    assert graduated["graduated_at_tag"] == "phase2.1-final"
    assert graduated["graduation_attestation"] == {
        "engine_version_unchanged_because_of_item": True,
        "attested_by": "principal_adjudicator",
        "engine_version": "engine-v1",
        "tag_commit": "b" * 40,
        "tag_committer_date": "2030-06-01T12:00:00-04:00",
        "consulted_repository": None,
    }


def test_graduation_requires_the_freeze_tag_shape(manifest, dev_corpus):
    """Review MAJOR-2 (a): `notfinal` exists in the tag list, is dated after
    the evaluation, and is still refused — it is not a freeze tag."""
    item = add(manifest, dev_corpus)
    evaluate(manifest, item)
    with pytest.raises(TransitionError, match="not a freeze tag"):
        graduate(manifest, item["holdout_id"], tag="notfinal")
    assert manifest.items()[item["holdout_id"]]["status"] == "evaluated"
    assert manifest_mod.FREEZE_TAG_RE.fullmatch("batch9-final")
    assert manifest_mod.FREEZE_TAG_RE.fullmatch("phase2.1-final")
    assert not manifest_mod.FREEZE_TAG_RE.fullmatch("archive/universal-prototype-2026-08-04")
    assert not manifest_mod.FREEZE_TAG_RE.fullmatch("mt9-l1s3-broken-compose")


def test_graduation_requires_a_subsequent_freeze(manifest, dev_corpus):
    """Review MAJOR-2 (c): the tag's commit must be dated AFTER the item's
    last evaluation (§12: same-wave graduation is forbidden)."""
    item = add(manifest, dev_corpus)
    evaluate(manifest, item)
    with pytest.raises(TransitionError, match="SUBSEQUENT"):
        graduate(manifest, item["holdout_id"], tag="old-final")
    # Evaluated after every freeze in the list: nothing is subsequent.
    later = add(manifest, dev_corpus, "h-b")
    evaluate(manifest, later, at="2031-01-01T00:00:00+00:00")
    for tag in ("batch9-final", "phase2.1-final"):
        with pytest.raises(TransitionError, match="SUBSEQUENT"):
            graduate(manifest, later["holdout_id"], tag=tag)
    assert manifest.items()[later["holdout_id"]]["status"] == "evaluated"
    # A tag dated exactly at the evaluation is not after it either.
    same = add(manifest, dev_corpus, "h-c")
    evaluate(manifest, same, at="2030-01-01T00:00:00+00:00")
    with pytest.raises(TransitionError, match="SUBSEQUENT"):
        graduate(manifest, same["holdout_id"], tag="batch9-final")


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
def test_every_other_transition_refuses(manifest, dev_corpus, path):
    start, target = path
    item = add(manifest, dev_corpus)
    hid = item["holdout_id"]
    if start in ("burned", "graduated"):
        evaluate(manifest, item)
    if start == "burned":
        manifest.burn(hid, burned_by="P24-LAYOUT")
    if start == "graduated":
        graduate(manifest, hid, tag="batch9-final")
    assert manifest.items()[hid]["status"] == start
    with pytest.raises(TransitionError):
        if target == "evaluated":
            evaluate(manifest, item)
        elif target == "burned":
            manifest.burn(hid, burned_by="P24-LAYOUT")
        else:
            graduate(manifest, hid, tag="batch9-final")
    assert manifest.items()[hid]["status"] == start


def test_the_transition_matrix_is_exactly_the_ruled_one():
    assert manifest_mod.ALLOWED_TRANSITIONS == frozenset({
        ("unseen", "evaluated"), ("evaluated", "evaluated"),
        ("evaluated", "burned"), ("evaluated", "graduated"),
    })
    assert manifest_mod.HOLDOUT_STATUSES == ("unseen", "evaluated", "burned", "graduated")


def test_there_is_no_generic_status_setter(manifest, dev_corpus):
    add(manifest, dev_corpus)
    for name in ("set_status", "update_status", "transition", "force_status"):
        assert not hasattr(manifest, name), name


# --- the refusal set and the digest material --------------------------------


def test_refusal_set_covers_every_item_regardless_of_status(manifest, dev_corpus):
    a = add(manifest, dev_corpus, "h-a")
    b = add(manifest, dev_corpus, "h-b")
    c = add(manifest, dev_corpus, "h-c")
    evaluate(manifest, b)
    evaluate(manifest, c)
    manifest.burn(b["holdout_id"], burned_by="P24-LAYOUT")
    graduate(manifest, c["holdout_id"], tag="batch9-final")
    assert manifest.holdout_shas_for_refusal() == frozenset(
        {a["content_sha256"], b["content_sha256"], c["content_sha256"]}
    )
    assert manifest.counts_by_status() == {"unseen": 1, "evaluated": 0, "burned": 1, "graduated": 1}
    assert manifest.sha16_statuses() == sorted(
        [(a["content_sha256"][:16], "unseen"), (b["content_sha256"][:16], "burned"),
         (c["content_sha256"][:16], "graduated")]
    )


# --- freeze tags from git ----------------------------------------------------


def test_freeze_tags_from_git_resolve_this_checkouts_real_tags():
    tags = manifest_mod.freeze_tags_from_git(ROOT)
    if not tags:
        pytest.skip("git tags not readable from this checkout")
    for name, ref in tags.items():
        assert ref.tag == name
        assert len(ref.commit) == 40
        assert "T" in ref.committer_date
    assert manifest_mod.freeze_tags_from_git(ROOT / "nowhere_probe") == {}


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


def test_repository_identity_names_the_consulted_repository(tmp_path):
    """Review NEW-2: the graduation attestation records WHICH repository the
    freeze tag was resolved in (its path digest and root commit)."""
    identity = manifest_mod.repository_identity(ROOT)
    if identity is None:
        pytest.skip("git not readable from this checkout")
    assert identity["path_digest"] == hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()
    assert len(identity["root_commit"]) == 40
    assert manifest_mod.repository_identity(tmp_path / "not_a_repo") is None


def test_graduation_records_the_consulted_repository_when_given(manifest, dev_corpus):
    item = add(manifest, dev_corpus)
    evaluate(manifest, item)
    identity = {"path_digest": "ab" * 32, "root_commit": "c" * 40}
    graduated = graduate(manifest, item["holdout_id"], consulted_repository=identity)
    assert graduated["graduation_attestation"]["consulted_repository"] == identity
    other = add(manifest, dev_corpus, "h-b")
    evaluate(manifest, other)
    assert graduate(manifest, other["holdout_id"])["graduation_attestation"]["consulted_repository"] is None
