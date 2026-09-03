"""P22-HOLDOUT case 18: the sealed truth store.

Append-only, hash-chained JSONL keyed by content sha, living ONLY under
`SEALED_TRUTH_DIR` (an absolute directory outside every checkout); refuses
without the variable and refuses a path inside the checkout. Every fixture
here is synthetic: shas are sha256 digests of literal strings, figures are
plain example numbers, dates are in 2031+.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from tools.holdout import store as store_mod
from tools.holdout.store import (
    ChainError,
    RecordError,
    StoreLocationError,
    TruthStore,
    description_hash,
    notes_hash,
)

ROOT = Path(__file__).resolve().parents[1]


def synthetic_sha(label: str) -> str:
    return hashlib.sha256(f"synthetic:{label}".encode()).hexdigest().upper()


def packet_digest(label: str) -> str:
    return hashlib.sha256(f"packet:{label}".encode()).hexdigest()


def minimal_fields(label: str = "doc-a", **overrides) -> dict:
    fields = dict(
        content_sha256=synthetic_sha(label),
        kind="STATEMENT_COMPLETE",
        sub_kind=None,
        account_kind="deposit",
        modality="digital",
        completeness_findings=[],
        legible=True,
        account_count=1,
        printed_period_start="2031-01-01",
        printed_period_end="2031-01-31",
        opening_balance="100.00",
        closing_balance="150.25",
        printed_transaction_count=3,
        sampled_rows=[
            {"date": "2031-01-05", "description": "SYNTHETIC ROW ONE", "amount": "-12.34"},
        ],
        adjudicator="principal_adjudicator",
        packet_digest=packet_digest(label),
        notes="a synthetic free note that must never be stored",
    )
    fields.update(overrides)
    return fields


@pytest.fixture
def store_dir(tmp_path, monkeypatch) -> Path:
    target = tmp_path / "sealed"
    monkeypatch.setenv("SEALED_TRUTH_DIR", str(target))
    return target


# --- location ---------------------------------------------------------------


def test_refuses_without_the_variable(monkeypatch):
    monkeypatch.delenv("SEALED_TRUTH_DIR", raising=False)
    with pytest.raises(StoreLocationError):
        TruthStore.open()


def test_refuses_an_empty_or_relative_path(monkeypatch):
    monkeypatch.setenv("SEALED_TRUTH_DIR", "")
    with pytest.raises(StoreLocationError):
        TruthStore.open()
    monkeypatch.setenv("SEALED_TRUTH_DIR", "relative/sealed")
    with pytest.raises(StoreLocationError):
        TruthStore.open()


@pytest.mark.parametrize(
    "inside",
    [
        ROOT / "sealed_truth",
        ROOT / "docs" / "moneythumb-replacement" / "truth" / "sealed_probe",
        ROOT / ".claude" / "sealed",
        ROOT / "Bank Statements" / "sealed",
    ],
)
def test_refuses_a_path_inside_the_checkout(monkeypatch, inside):
    monkeypatch.setenv("SEALED_TRUTH_DIR", str(inside))
    with pytest.raises(StoreLocationError):
        TruthStore.open()
    # The constructor is not a bypass.
    with pytest.raises(StoreLocationError):
        TruthStore(inside)
    assert not inside.exists()


def test_refuses_every_ancestor_checkout_including_the_main_repository(monkeypatch):
    """A worktree under `.claude/worktrees/` has TWO checkouts above it: its
    own root and the main repository's. Every ancestor that carries a `.git`
    entry is a checkout, and a store under any of them is refused."""
    checkouts = [p for p in [ROOT, *ROOT.parents] if (p / ".git").exists()]
    assert checkouts, "the test must run inside a git checkout"
    for checkout in checkouts:
        monkeypatch.setenv("SEALED_TRUTH_DIR", str(checkout / "sealed_truth_probe"))
        with pytest.raises(StoreLocationError):
            TruthStore.open()


def test_the_named_repository_roots_are_all_refused():
    for root in store_mod.repository_roots():
        with pytest.raises(StoreLocationError):
            store_mod.refuse_inside_checkout(root / "anything", what="probe")


def test_opens_and_creates_outside_the_checkout_on_first_write(store_dir):
    store = TruthStore.open()
    assert not store_dir.exists()  # nothing is created by opening
    assert store.records() == []
    assert store.verify_chain() == store_mod.GENESIS
    store.append_record(**minimal_fields())
    assert store_dir.is_dir()
    assert (store_dir / "truth.jsonl").is_file()
    assert (store_dir / "manifest.json").is_file()


# --- records and the chain --------------------------------------------------


def test_append_builds_a_chain_and_verify_walks_it(store_dir):
    store = TruthStore.open()
    first = store.append_record(**minimal_fields("doc-a"))
    second = store.append_record(**minimal_fields("doc-b"))
    assert first["seq"] == 1 and second["seq"] == 2
    assert first["prev"] == store_mod.GENESIS
    assert second["prev"] == first["hash"]
    assert store.verify_chain() == second["hash"]
    manifest = store.manifest()
    assert manifest["store_version"] == store_mod.STORE_VERSION
    assert manifest["record_count"] == 2
    assert manifest["chain_head"] == second["hash"]
    assert manifest["updated_at"].endswith("+00:00")


def test_each_record_hash_covers_every_field_but_hash(store_dir):
    store = TruthStore.open()
    record = store.append_record(**minimal_fields())
    without_hash = {k: v for k, v in record.items() if k != "hash"}
    expected = hashlib.sha256(
        json.dumps(without_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    assert record["hash"] == expected
    # `prev` is inside the hashed material: changing it changes the hash.
    tampered = dict(without_hash, prev="0" * 64)
    assert store_mod.record_hash(tampered) != record["hash"]


def test_a_rewritten_earlier_record_is_detected(store_dir):
    store = TruthStore.open()
    store.append_record(**minimal_fields("doc-a"))
    store.append_record(**minimal_fields("doc-b"))
    lines = (store_dir / "truth.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["kind"] = "NOT_A_STATEMENT"  # a rewrite that keeps the stored hash
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    (store_dir / "truth.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ChainError):
        store.verify_chain()
    with pytest.raises(ChainError):
        store.append_record(**minimal_fields("doc-c"))  # never appends to a broken chain


def test_a_rewritten_record_with_a_recomputed_hash_breaks_the_next_link(store_dir):
    store = TruthStore.open()
    store.append_record(**minimal_fields("doc-a"))
    store.append_record(**minimal_fields("doc-b"))
    lines = (store_dir / "truth.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["kind"] = "NOT_A_STATEMENT"
    first.pop("hash")
    first["hash"] = store_mod.record_hash(first)
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    (store_dir / "truth.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ChainError):
        store.verify_chain()


def test_reordered_records_are_detected_including_the_first(store_dir):
    store = TruthStore.open()
    store.append_record(**minimal_fields("doc-a"))
    store.append_record(**minimal_fields("doc-b"))
    lines = (store_dir / "truth.jsonl").read_text(encoding="utf-8").splitlines()
    (store_dir / "truth.jsonl").write_text("\n".join([lines[1], lines[0]]) + "\n", encoding="utf-8")
    with pytest.raises(ChainError):
        store.verify_chain()


def test_a_first_record_whose_prev_is_not_genesis_is_refused(store_dir):
    store = TruthStore.open()
    store.append_record(**minimal_fields("doc-a"))
    store.append_record(**minimal_fields("doc-b"))
    lines = (store_dir / "truth.jsonl").read_text(encoding="utf-8").splitlines()
    # Drop the first record: the file now opens with a record whose `prev`
    # names a hash that is nowhere in the file. Skipping the first record's
    # check would let this pass.
    (store_dir / "truth.jsonl").write_text(lines[1] + "\n", encoding="utf-8")
    with pytest.raises(ChainError):
        store.verify_chain()


def test_a_truncated_file_disagrees_with_the_manifest_head(store_dir):
    store = TruthStore.open()
    store.append_record(**minimal_fields("doc-a"))
    store.append_record(**minimal_fields("doc-b"))
    lines = (store_dir / "truth.jsonl").read_text(encoding="utf-8").splitlines()
    (store_dir / "truth.jsonl").write_text(lines[0] + "\n", encoding="utf-8")
    assert store.verify_chain()  # the shortened chain is internally consistent ...
    with pytest.raises(ChainError):
        store.verify_against_manifest()  # ... but the manifest remembers the head


def test_the_latest_event_per_sha_is_the_current_verdict(store_dir):
    store = TruthStore.open()
    store.append_record(**minimal_fields("doc-a", kind="KIND_UNCERTAIN"))
    store.append_record(**minimal_fields("doc-b", kind="NOT_A_STATEMENT", sub_kind="cheque_image"))
    store.append_record(**minimal_fields("doc-a", kind="STATEMENT_COMPLETE"))
    latest = store.latest_by_sha()
    assert set(latest) == {synthetic_sha("doc-a"), synthetic_sha("doc-b")}
    assert latest[synthetic_sha("doc-a")]["kind"] == "STATEMENT_COMPLETE"
    assert latest[synthetic_sha("doc-a")]["seq"] == 3
    assert store.counts_by_kind() == {"STATEMENT_COMPLETE": 1, "NOT_A_STATEMENT": 1}
    assert store.adjudicated_sha16s() == sorted(
        [synthetic_sha("doc-a")[:16], synthetic_sha("doc-b")[:16]]
    )


# --- field discipline -------------------------------------------------------


def test_record_carries_the_minimum_fields_and_no_text(store_dir):
    store = TruthStore.open()
    record = store.append_record(**minimal_fields())
    expected_keys = {
        "record_id", "seq", "store_version", "content_sha256", "kind", "sub_kind",
        "account_kind", "modality", "completeness_findings", "legible", "account_count",
        "printed_period_start", "printed_period_end", "opening_balance", "closing_balance",
        "printed_transaction_count", "sampled_rows", "adjudicator", "adjudicated_at",
        "packet_digest", "notes_hash", "prev", "hash",
    }
    assert set(record) == expected_keys
    assert record["record_id"] == f"000001-{record['content_sha256'][:16]}"
    assert record["adjudicated_at"].endswith("+00:00")


def test_sampled_row_descriptions_are_stored_as_hashes_never_text(store_dir):
    store = TruthStore.open()
    text = "SYNTHETIC ROW ONE"
    store.append_record(**minimal_fields(sampled_rows=[
        {"date": "2031-01-05", "description": text, "amount": "-12.34"},
    ]))
    raw = (store_dir / "truth.jsonl").read_text(encoding="utf-8")
    assert text not in raw
    assert text.lower() not in raw.lower()
    row = store.records()[0]["sampled_rows"][0]
    assert set(row) == {"date", "description_hash", "amount"}
    assert row["description_hash"] == description_hash(text)
    assert len(row["description_hash"]) == 64
    # The hash is over a normalised form so a later ledger comparison can match it.
    assert description_hash("  synthetic   row one ") == description_hash(text)


def test_a_sampled_row_with_a_description_text_key_stored_verbatim_is_refused(store_dir):
    store = TruthStore.open()
    with pytest.raises(RecordError):
        store.append_record(**minimal_fields(sampled_rows=[
            {"date": "2031-01-05", "description_text": "X", "amount": "1.00"},
        ]))
    with pytest.raises(RecordError):
        store.append_record(**minimal_fields(sampled_rows=[
            {"date": "2031-01-05", "amount": "1.00"},  # neither description nor hash
        ]))
    with pytest.raises(RecordError):
        store.append_record(**minimal_fields(sampled_rows=[
            {"date": "2031-01-0%d" % d, "description": "R", "amount": "1.00"} for d in range(1, 5)
        ]))  # more than three


def test_notes_are_hashed_never_stored(store_dir):
    store = TruthStore.open()
    note = "a synthetic free note that must never be stored"
    record = store.append_record(**minimal_fields(notes=note))
    raw = (store_dir / "truth.jsonl").read_text(encoding="utf-8")
    assert note not in raw
    assert "notes" not in record
    assert record["notes_hash"] == notes_hash(note)
    empty = store.append_record(**minimal_fields("doc-b", notes=""))
    assert empty["notes_hash"] is None


@pytest.mark.parametrize(
    "bad",
    [
        dict(kind="statement_complete"),
        dict(kind="VALIDATED"),
        dict(account_kind="checking"),
        dict(modality="native"),
        dict(completeness_findings=["missing_everything"]),
        dict(legible="yes"),
        dict(account_count=-1),
        dict(printed_period_start="01/05/2031"),
        dict(printed_period_start="2031-02-01", printed_period_end="2031-01-01"),
        dict(opening_balance="1,000.00"),
        dict(opening_balance="NaN"),
        dict(printed_transaction_count=1.5),
        dict(adjudicator="someone@example.com"),
        dict(adjudicator=""),
        dict(packet_digest="not-a-digest"),
        dict(content_sha256="ABC"),
        dict(sub_kind="Customer Name Inc"),
    ],
)
def test_out_of_vocabulary_or_malformed_fields_are_refused(store_dir, bad):
    store = TruthStore.open()
    with pytest.raises(RecordError):
        store.append_record(**minimal_fields(**bad))
    assert store.records() == []


def test_null_oracle_figures_are_allowed(store_dir):
    store = TruthStore.open()
    record = store.append_record(**minimal_fields(
        kind="NOT_A_STATEMENT", sub_kind="deposit_slip", account_count=None,
        printed_period_start=None, printed_period_end=None, opening_balance=None,
        closing_balance=None, printed_transaction_count=None, sampled_rows=[],
    ))
    assert record["opening_balance"] is None and record["sampled_rows"] == []


def test_figures_are_canonical_decimal_strings(store_dir):
    store = TruthStore.open()
    record = store.append_record(**minimal_fields(opening_balance="0100.5", closing_balance=150))
    assert record["opening_balance"] == "100.5"
    assert record["closing_balance"] == "150"
    assert isinstance(record["closing_balance"], str)


def test_the_file_is_only_ever_appended_to(store_dir):
    store = TruthStore.open()
    store.append_record(**minimal_fields("doc-a"))
    before = (store_dir / "truth.jsonl").read_bytes()
    store.append_record(**minimal_fields("doc-b"))
    after = (store_dir / "truth.jsonl").read_bytes()
    assert after.startswith(before)
    assert not hasattr(store, "rewrite") and not hasattr(store, "delete_record")


def test_store_module_exposes_only_the_closed_kind_vocabulary():
    assert store_mod.KINDS == (
        "STATEMENT_COMPLETE", "STATEMENT_PARTIAL", "STATEMENT_ILLEGIBLE", "ACTIVITY_EXPORT",
        "NOT_A_STATEMENT", "FILE_INVALID", "KIND_UNCERTAIN",
    )
    assert "validated" not in {k.lower() for k in store_mod.KINDS}


def test_env_is_read_from_the_process_environment_at_open_time(store_dir):
    assert os.environ["SEALED_TRUTH_DIR"] == str(store_dir)
    store = TruthStore.open()
    assert store.directory == store_dir.resolve()
