"""The unseen holdout cage (P22-HOLDOUT item 2; the accepted architecture
§12 made operational; R4).

`holdout.jsonl` in the sealed store is an append-only hash chain of EVENTS
(`added`, `evaluated`, `burned`, `graduated`); an item's current state is its
latest event; `holdout_manifest.json` remembers the chain's head and count and
every read or append first verifies the file against it (review MAJOR-1).
Every item carries its strata (a code per stratum, never a customer name),
the `not_in_dev_corpus` attestation — asserted at add time ONLY against the
run of record's sha set read from a `rows.csv`, and recorded with that
population's digest, size and row count so the assertion is auditable
(review MAJOR-3) — and a status whose transitions are exactly:

    unseen    -> evaluated   (the evaluation tool only: it names the engine
                              version and its run id)
    evaluated -> evaluated   (a later evaluation, a new engine version)
    evaluated -> burned      (explicit, with the card / commit that named it)
    evaluated -> graduated   (ONLY with a FREEZE tag — `*-final` — that exists
                              in the repository's real tag list AND points at
                              a commit whose committer date is AFTER the
                              item's last evaluation, plus the recorded
                              attestation that the engine version did not
                              change because of the item; review MAJOR-2)

Everything else refuses. There is no generic status setter.
"""
from __future__ import annotations

import csv
import re
import subprocess
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .store import (
    GENESIS,
    HOLDOUT_FILE,
    HOLDOUT_MANIFEST_FILE,
    MODALITIES,
    STORE_VERSION,
    ChainedJsonl,
    StoreError,
    _retry,
    normalize_utc,
    refuse_inside_checkout,
    resolve_store_dir,
    sha256_hex,
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
#: A freeze tag: the repository's freeze tags are `batch8-final`, `batch9-final`,
#: `phase2.0-final`, `phase2.1-final` — the shape is `*-final`.
FREEZE_TAG_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{0,78}-final")
#: The recipe behind `DevCorpus.digest` (stated so an auditor can recompute it).
DEV_CORPUS_DIGEST_RECIPE = "sha256 over the sorted distinct upper-hex content shas joined by LF, no trailing newline"

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


# --- the development corpus (MAJOR-3) ---------------------------------------


@dataclass(frozen=True)
class DevCorpus:
    """The run of record's sha population, read from its `rows.csv`."""

    shas: frozenset
    digest: str
    size: int
    rows: int
    source: str

    def record(self) -> dict:
        return {"digest": self.digest, "size": self.size, "rows": self.rows,
                "source": self.source, "recipe": DEV_CORPUS_DIGEST_RECIPE}


def dev_corpus_digest(shas) -> str:
    return sha256_hex("\n".join(sorted({str(s).strip().upper() for s in shas})))


def dev_corpus_from_rows(rows_csv: Path | str) -> DevCorpus:
    """The ONLY builder: a run's `rows.csv` (its `content_sha256` column)."""
    path = Path(rows_csv)
    if not path.is_file():
        raise HoldoutRefusal(f"dev corpus: not a rows.csv file: {path}")
    shas: set[str] = set()
    rows = 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "content_sha256" not in reader.fieldnames:
            raise HoldoutRefusal(f"dev corpus: {path.name} has no content_sha256 column")
        for row in reader:
            rows += 1
            value = (row.get("content_sha256") or "").strip().upper()
            if value:
                shas.add(validate_sha(value, what="dev corpus content_sha256"))
    if not shas:
        raise HoldoutRefusal(f"dev corpus: {path.name} names no content sha; an empty population is no attestation")
    source = f"{path.parent.name}/{path.name}" if path.parent.name else path.name
    return DevCorpus(shas=frozenset(shas), digest=dev_corpus_digest(shas), size=len(shas), rows=rows, source=source)


# --- freeze tags (MAJOR-2) ---------------------------------------------------


@dataclass(frozen=True)
class TagRef:
    """A repository tag resolved through git: the commit it points at (peeled
    for annotated tags) and that commit's committer date (ISO-8601, offset)."""

    tag: str
    commit: str
    committer_date: str


def freeze_tags_from_git(repo_dir: Path | str) -> dict[str, TagRef]:
    """Every tag of `repo_dir`, resolved through `git for-each-ref`; empty on
    any failure, which makes graduation refuse — fail closed."""
    fmt = "%(refname:short)%09%(objectname)%09%(*objectname)%09%(committerdate:iso-strict)%09%(*committerdate:iso-strict)"
    try:
        completed = subprocess.run(
            ["git", "for-each-ref", f"--format={fmt}", "refs/tags"], cwd=str(repo_dir),
            capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if completed.returncode != 0:
        return {}
    tags: dict[str, TagRef] = {}
    for line in completed.stdout.splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 5 or not parts[0]:
            continue
        name, obj, peeled, obj_date, peeled_date = parts
        commit = peeled or obj
        committer_date = peeled_date or obj_date
        if not commit or not committer_date:
            continue
        tags[name] = TagRef(tag=name, commit=commit, committer_date=committer_date)
    return tags


def _parse_when(value: str, *, what: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TransitionError(f"{what}: not an ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise TransitionError(f"{what}: timestamp carries no offset: {value!r}")
    return parsed


# --- strata -------------------------------------------------------------------


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
        self.manifest_path = self.directory / HOLDOUT_MANIFEST_FILE
        self._chain = ChainedJsonl(self.path, self.manifest_path)

    @classmethod
    def open(cls, env: Mapping[str, str] | None = None) -> "HoldoutManifest":
        return cls(resolve_store_dir(env))

    # --- reading -----------------------------------------------------------

    def events(self) -> list[dict]:
        return self._chain.read()

    def verify_chain(self) -> str:
        return self._chain.verify()

    def verify_against_manifest(self) -> str:
        return self._chain.verify_against_manifest()

    def manifest(self) -> dict:
        manifest = self._chain.read_manifest()
        if manifest is not None:
            return manifest
        return {"store_version": STORE_VERSION, "record_count": 0, "chain_head": GENESIS, "updated_at": None}

    def items(self) -> dict[str, dict]:
        """Current state per holdout id — only from a file that agrees with its manifest."""
        events = self.events()
        self._chain.verify_against_manifest(events)
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
        return _snapshot(self._chain.append(payload))  # the chain verifies against its manifest first

    def add(
        self,
        *,
        content_sha256,
        source_batch,
        strata,
        dev_corpus: DevCorpus,
        added_at: str | None = None,
    ) -> dict:
        try:
            sha = validate_sha(content_sha256)
        except StoreError as exc:
            raise HoldoutRefusal(str(exc)) from exc
        if not isinstance(dev_corpus, DevCorpus) or not dev_corpus.shas:
            raise HoldoutRefusal(
                "dev_corpus: the run of record's population (dev_corpus_from_rows(<rows.csv>)) is "
                "required; `not_in_dev_corpus` is asserted against it, never assumed"
            )
        if sha in dev_corpus.shas:
            raise HoldoutRefusal(
                f"{sha[:16]}: present in the development corpus ({dev_corpus.source}, "
                f"{dev_corpus.size} shas); a development document can never be unseen"
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
            "dev_corpus": dev_corpus.record(),
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
        freeze_tags: Mapping[str, TagRef],
        attest_engine_version_unchanged: bool,
        attested_by: str,
        at: str | None = None,
    ) -> dict:
        """`evaluated -> graduated`, only with (a) a tag of the freeze shape
        `*-final`, (b) present in the repository's git-resolved tag list, (c)
        pointing at a commit whose committer date is AFTER the item's last
        evaluation (§12: a SUBSEQUENT freeze; same-wave graduation is
        forbidden), and the explicit engine-version attestation."""
        item = self._current(holdout_id)
        self._check(item, "graduated")
        if attest_engine_version_unchanged is not True:
            raise TransitionError(
                f"{holdout_id}: graduation requires the explicit attestation that the engine "
                "version did not change because of the item"
            )
        tag = _label("graduated_at_tag", graduated_at_tag)
        if not FREEZE_TAG_RE.fullmatch(tag):
            raise TransitionError(f"{holdout_id}: {tag!r} is not a freeze tag (the shape is `*-final`)")
        if isinstance(freeze_tags, str) or not isinstance(freeze_tags, Mapping) or tag not in freeze_tags:
            raise TransitionError(f"{holdout_id}: {tag!r} is not in the repository's tag list")
        ref = freeze_tags[tag]
        if not isinstance(ref, TagRef) or ref.tag != tag or not ref.commit or not ref.committer_date:
            raise TransitionError(f"{holdout_id}: {tag!r} did not resolve through git to a commit and a date")
        if not item.get("last_engine_version") or not item.get("last_evaluated_at"):
            raise TransitionError(f"{holdout_id}: no recorded evaluation to attest about")
        evaluated = _parse_when(item["last_evaluated_at"], what="last_evaluated_at")
        frozen = _parse_when(ref.committer_date, what=f"{tag} committer date")
        if frozen <= evaluated:
            raise TransitionError(
                f"{holdout_id}: {tag!r} points at a commit dated {ref.committer_date}, not after the "
                f"item's last evaluation {item['last_evaluated_at']} (a SUBSEQUENT freeze is required)"
            )
        if not isinstance(attested_by, str) or not _ROLE_RE.fullmatch(attested_by.strip()):
            raise TransitionError(f"attested_by: a role code is required, got {attested_by!r}")
        attestation = {
            "engine_version_unchanged_because_of_item": True,
            "attested_by": attested_by.strip(),
            "engine_version": item["last_engine_version"],
            "tag_commit": ref.commit,
            "tag_committer_date": ref.committer_date,
        }
        updated = dict(item, status="graduated", graduated_at_tag=tag,
                       graduation_attestation=attestation)
        return self._emit("graduated", updated, at)


__all__ = [
    "ALLOWED_TRANSITIONS",
    "BANK_FAMILIARITY",
    "ACCOUNT_SHAPES",
    "DEV_CORPUS_DIGEST_RECIPE",
    "DevCorpus",
    "FREEZE_TAG_RE",
    "GENESIS",
    "HOLDOUT_STATUSES",
    "HoldoutManifest",
    "HoldoutRefusal",
    "PAGE_COUNT_BUCKETS",
    "STRATA_KEYS",
    "TABLE_SHAPES",
    "TagRef",
    "TransitionError",
    "build_strata",
    "dev_corpus_digest",
    "dev_corpus_from_rows",
    "freeze_tags_from_git",
    "page_count_bucket",
]
