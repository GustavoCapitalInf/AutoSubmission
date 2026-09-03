"""The unseen holdout cage (P22-HOLDOUT item 2; the accepted architecture
§12 made operational; R4).

`holdout.jsonl` in the sealed store is an append-only hash chain of EVENTS
(`added`, `evaluated`, `burned`, `graduated`); an item's current state is its
latest event. Every item carries its strata (a code per stratum, never a
customer name), the `not_in_dev_corpus` attestation — asserted at add time
against the development corpus's sha set, which the caller MUST supply — and
a status whose transitions are exactly:

    unseen    -> evaluated   (the evaluation tool only: it names the engine
                              version and its run id)
    evaluated -> evaluated   (a later evaluation, a new engine version)
    evaluated -> burned      (explicit, with the card / commit that named it)
    evaluated -> graduated   (ONLY with a freeze tag that exists AND the
                              recorded attestation that the engine version did
                              not change because of the item)

Everything else refuses. There is no generic status setter.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Mapping
from pathlib import Path

from .store import (
    GENESIS,
    HOLDOUT_FILE,
    MODALITIES,
    STORE_VERSION,
    ChainedJsonl,
    StoreError,
    normalize_utc,
    refuse_inside_checkout,
    resolve_store_dir,
    validate_sha,
)

HOLDOUT_STATUSES = ("unseen", "evaluated", "burned", "graduated")
ALLOWED_TRANSITIONS = frozenset({
    ("unseen", "evaluated"),
    ("evaluated", "evaluated"),
    ("evaluated", "burned"),
    ("evaluated", "graduated"),
})
BANK_FAMILIARITY = ("known_bank", "unknown_bank")
ACCOUNT_SHAPES = ("single", "multi_account")
TABLE_SHAPES = ("table_heavy", "summary_only")
PAGE_COUNT_BUCKETS = ("1", "2-5", "6-15", "16+")
STRATA_KEYS = (
    "modality",
    "bank_familiarity",
    "account_shape",
    "table_shape",
    "currency",
    "page_count_bucket",
    "layout_family_code",
)

_CURRENCY_RE = re.compile(r"[A-Za-z]{3}")
_LAYOUT_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,39}")
_BATCH_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{0,39}")
_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:+/-]{0,79}")
_ROLE_RE = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_EVENT_KEYS = ("seq", "prev", "hash", "event", "event_at")


class HoldoutRefusal(StoreError):
    """A document may not enter the holdout (development corpus, duplicate, malformed)."""


class TransitionError(StoreError):
    """A status transition outside the ruled matrix, or without its evidence."""


def page_count_bucket(page_count) -> str:
    if isinstance(page_count, bool) or not isinstance(page_count, int) or page_count < 1:
        raise ValueError(f"page_count: must be a positive integer, got {page_count!r}")
    if page_count == 1:
        return "1"
    if page_count <= 5:
        return "2-5"
    if page_count <= 15:
        return "6-15"
    return "16+"


def _choice(name: str, value, choices: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{name}: {value!r} is not one of {choices}")
    return value


def _currency(value) -> str:
    if not isinstance(value, str):
        raise ValueError(f"currency: must be a 3-letter code or 'unknown', got {value!r}")
    text = value.strip()
    if text.lower() == "unknown":
        return "unknown"
    if not _CURRENCY_RE.fullmatch(text):
        raise ValueError(f"currency: must be a 3-letter code or 'unknown', got {value!r}")
    return text.upper()


def build_strata(
    *,
    modality,
    bank_familiarity,
    account_shape,
    table_shape,
    currency,
    page_count,
    layout_family_code,
) -> dict:
    """The §12 strata as closed codes. `ValueError` on anything outside them."""
    if not isinstance(layout_family_code, str) or not _LAYOUT_CODE_RE.fullmatch(layout_family_code):
        raise ValueError(
            "layout_family_code: a lowercase code (a processor/template class), "
            f"never a customer or bank name: {layout_family_code!r}"
        )
    return {
        "modality": _choice("modality", modality, MODALITIES),
        "bank_familiarity": _choice("bank_familiarity", bank_familiarity, BANK_FAMILIARITY),
        "account_shape": _choice("account_shape", account_shape, ACCOUNT_SHAPES),
        "table_shape": _choice("table_shape", table_shape, TABLE_SHAPES),
        "currency": _currency(currency),
        "page_count_bucket": page_count_bucket(page_count),
        "layout_family_code": layout_family_code,
    }


def _validate_strata(strata) -> dict:
    if not isinstance(strata, Mapping) or set(strata) != set(STRATA_KEYS):
        raise HoldoutRefusal(f"strata: expected exactly the keys {STRATA_KEYS}")
    try:
        _choice("modality", strata["modality"], MODALITIES)
        _choice("bank_familiarity", strata["bank_familiarity"], BANK_FAMILIARITY)
        _choice("account_shape", strata["account_shape"], ACCOUNT_SHAPES)
        _choice("table_shape", strata["table_shape"], TABLE_SHAPES)
        _choice("page_count_bucket", strata["page_count_bucket"], PAGE_COUNT_BUCKETS)
        currency = _currency(strata["currency"])
    except ValueError as exc:
        raise HoldoutRefusal(str(exc)) from exc
    if strata["currency"] != currency:
        raise HoldoutRefusal(f"currency: not canonical: {strata['currency']!r}")
    code = strata["layout_family_code"]
    if not isinstance(code, str) or not _LAYOUT_CODE_RE.fullmatch(code):
        raise HoldoutRefusal(f"layout_family_code: not a code: {code!r}")
    return {key: strata[key] for key in STRATA_KEYS}


def _label(name: str, value, *, error=TransitionError) -> str:
    if not isinstance(value, str) or not _LABEL_RE.fullmatch(value.strip()):
        raise error(f"{name}: a non-empty label is required, got {value!r}")
    return value.strip()


def _snapshot(event: Mapping) -> dict:
    return {key: value for key, value in event.items() if key not in _EVENT_KEYS}


class HoldoutManifest:
    def __init__(self, directory: Path | str):
        self.directory = refuse_inside_checkout(directory, what="the holdout manifest")
        self.path = self.directory / HOLDOUT_FILE
        self._chain = ChainedJsonl(self.path)

    @classmethod
    def open(cls, env: Mapping[str, str] | None = None) -> "HoldoutManifest":
        return cls(resolve_store_dir(env))

    # --- reading -----------------------------------------------------------

    def events(self) -> list[dict]:
        return self._chain.read()

    def verify_chain(self) -> str:
        return self._chain.verify()

    def items(self) -> dict[str, dict]:
        """Current state per holdout id (the chain is verified first)."""
        events = self.events()
        self._chain.verify(events)
        current: dict[str, dict] = {}
        for event in events:
            current[event["holdout_id"]] = _snapshot(event)
        return current

    def by_sha(self) -> dict[str, dict]:
        return {item["content_sha256"]: item for item in self.items().values()}

    def holdout_shas_for_refusal(self) -> frozenset[str]:
        """Every holdout sha, whatever its status: once in the cage, never in
        a research or development population (the runner refuses them via
        the repository digest's sha16 list)."""
        return frozenset(self.by_sha())

    def counts_by_status(self) -> dict[str, int]:
        counts = Counter(item["status"] for item in self.items().values())
        return {status: counts[status] for status in HOLDOUT_STATUSES}

    def sha16_statuses(self) -> list[tuple[str, str]]:
        return sorted((item["content_sha256"][:16], item["status"]) for item in self.items().values())

    # --- writing -----------------------------------------------------------

    def _emit(self, event: str, item: Mapping, at: str | None = None) -> dict:
        payload = dict(item)
        payload["event"] = event
        payload["event_at"] = normalize_utc(at, what="event_at")
        return _snapshot(self._chain.append(payload))

    def add(
        self,
        *,
        content_sha256,
        source_batch,
        strata,
        dev_corpus_shas: Collection[str],
        added_at: str | None = None,
    ) -> dict:
        try:
            sha = validate_sha(content_sha256)
        except StoreError as exc:
            raise HoldoutRefusal(str(exc)) from exc
        if dev_corpus_shas is None or isinstance(dev_corpus_shas, str) or not len(dev_corpus_shas):
            raise HoldoutRefusal(
                "dev_corpus_shas: the development corpus's sha set is required and must not be "
                "empty; `not_in_dev_corpus` is asserted against it, never assumed"
            )
        if sha in {str(value).strip().upper() for value in dev_corpus_shas}:
            raise HoldoutRefusal(
                f"{sha[:16]}: present in the development corpus; a development document can "
                "never be unseen"
            )
        if not isinstance(source_batch, str) or not _BATCH_RE.fullmatch(source_batch):
            raise HoldoutRefusal(f"source_batch: a batch label is required, got {source_batch!r}")
        items = self.items()
        if sha in {item["content_sha256"] for item in items.values()}:
            raise HoldoutRefusal(f"{sha[:16]}: already in the holdout manifest")
        item = {
            "holdout_id": f"H{len(items) + 1:06d}",
            "store_version": STORE_VERSION,
            "content_sha256": sha,
            "added_at": normalize_utc(added_at, what="added_at"),
            "source_batch": source_batch,
            "not_in_dev_corpus": True,
            "strata": _validate_strata(strata),
            "status": "unseen",
            "last_evaluated_at": None,
            "last_engine_version": None,
            "evaluation_run_id": None,
            "burned_by": None,
            "graduated_at_tag": None,
            "graduation_attestation": None,
        }
        return self._emit("added", item, item["added_at"])

    def _current(self, holdout_id: str) -> dict:
        items = self.items()
        if holdout_id not in items:
            raise TransitionError(f"unknown holdout id {holdout_id!r}")
        return items[holdout_id]

    @staticmethod
    def _check(item: Mapping, to_status: str) -> None:
        if (item["status"], to_status) not in ALLOWED_TRANSITIONS:
            raise TransitionError(
                f"{item['holdout_id']}: {item['status']} -> {to_status} is not a ruled "
                f"transition (allowed: {sorted(ALLOWED_TRANSITIONS)})"
            )

    def record_evaluation(
        self,
        holdout_id: str,
        *,
        engine_version: str,
        evaluation_run_id: str,
        evaluated_at: str | None = None,
    ) -> dict:
        """`unseen|evaluated -> evaluated`; called by the evaluation tool only —
        the adjudication CLI exposes no command that supplies a run id."""
        item = self._current(holdout_id)
        self._check(item, "evaluated")
        version = _label("engine_version", engine_version)
        run_id = _label("evaluation_run_id", evaluation_run_id)
        at = normalize_utc(evaluated_at, what="evaluated_at")
        updated = dict(item, status="evaluated", last_engine_version=version,
                       last_evaluated_at=at, evaluation_run_id=run_id)
        return self._emit("evaluated", updated, at)

    def burn(self, holdout_id: str, *, burned_by: str, at: str | None = None) -> dict:
        """`evaluated -> burned`: someone changed extractor, parser, structurer
        or validator IN RESPONSE to this item; `burned_by` names the card."""
        item = self._current(holdout_id)
        self._check(item, "burned")
        card = _label("burned_by", burned_by)
        return self._emit("burned", dict(item, status="burned", burned_by=card), at)

    def graduate(
        self,
        holdout_id: str,
        *,
        graduated_at_tag: str,
        freeze_tags: Collection[str],
        attest_engine_version_unchanged: bool,
        attested_by: str,
        at: str | None = None,
    ) -> dict:
        """`evaluated -> graduated`, only with an EXISTING freeze tag and the
        explicit attestation that `last_engine_version` did not change because
        of the item (§12: same-wave graduation is forbidden)."""
        item = self._current(holdout_id)
        self._check(item, "graduated")
        if attest_engine_version_unchanged is not True:
            raise TransitionError(
                f"{holdout_id}: graduation requires the explicit attestation that the engine "
                "version did not change because of the item"
            )
        tag = _label("graduated_at_tag", graduated_at_tag)
        if isinstance(freeze_tags, str) or tag not in set(freeze_tags):
            raise TransitionError(f"{holdout_id}: {tag!r} names no existing freeze tag")
        if not item.get("last_engine_version"):
            raise TransitionError(f"{holdout_id}: no recorded engine version to attest about")
        if not isinstance(attested_by, str) or not _ROLE_RE.fullmatch(attested_by.strip()):
            raise TransitionError(f"attested_by: a role code is required, got {attested_by!r}")
        attestation = {
            "engine_version_unchanged_because_of_item": True,
            "attested_by": attested_by.strip(),
            "engine_version": item["last_engine_version"],
        }
        updated = dict(item, status="graduated", graduated_at_tag=tag,
                       graduation_attestation=attestation)
        return self._emit("graduated", updated, at)


__all__ = [
    "ALLOWED_TRANSITIONS",
    "BANK_FAMILIARITY",
    "ACCOUNT_SHAPES",
    "GENESIS",
    "HOLDOUT_STATUSES",
    "HoldoutManifest",
    "HoldoutRefusal",
    "PAGE_COUNT_BUCKETS",
    "STRATA_KEYS",
    "TABLE_SHAPES",
    "TransitionError",
    "build_strata",
    "page_count_bucket",
]
