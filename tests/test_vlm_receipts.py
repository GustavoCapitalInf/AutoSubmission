import pytest

from vlm import receipts


def test_bound_and_checked_roundtrip(tmp_path):
    p = tmp_path / "a.json"
    p.write_bytes(b'{"x": 1}\n')
    b = receipts.bound(p)
    assert set(b) == {"path", "sha256"} and len(b["sha256"]) == 64
    assert receipts.checked(b) == b
    p.write_bytes(b'{"x": 2}\n')
    with pytest.raises(receipts.Refused) as exc:
        receipts.checked(b)
    assert exc.value.code == "binding_changed"


def test_bound_missing_refuses(tmp_path):
    with pytest.raises(receipts.Refused) as exc:
        receipts.bound(tmp_path / "missing.json")
    assert exc.value.code == "binding_missing"


def test_dump_new_is_exclusive_and_sorted(tmp_path):
    p = tmp_path / "r.json"
    receipts.dump_new(p, {"b": 1, "a": [1, 2]})
    assert p.read_text(encoding="utf-8") == '{\n  "a": [\n    1,\n    2\n  ],\n  "b": 1\n}\n'
    with pytest.raises(FileExistsError):
        receipts.dump_new(p, {"a": 1})


def test_dump_new_refuses_nan(tmp_path):
    with pytest.raises(ValueError):
        receipts.dump_new(tmp_path / "n.json", {"a": float("nan")})
    assert not (tmp_path / "n.json").exists()


def test_canonical_json_and_hash():
    assert receipts.canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert receipts.sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_need_raises_closed_code():
    with pytest.raises(receipts.Refused) as exc:
        receipts.need(False, "some_code")
    assert exc.value.code == "some_code" and str(exc.value) == "some_code"
