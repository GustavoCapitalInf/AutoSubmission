"""The sealed truth store (P22-HOLDOUT item 1; D9; R3).

Location
--------
`SEALED_TRUTH_DIR` in the process environment, REQUIRED — there is no default.
It must be an absolute directory OUTSIDE every repository checkout and ON THIS
MACHINE: not under this checkout's root, not under the main repository when
this is a worktree, not under any directory that carries a `.git` entry, never
under a `.claude` or `Bank Statements` path component, never an ancestor of a
checkout, never under a checkout's parent directory (the project folder and
its siblings), and never under a OneDrive root (R3: "on this machine" — a
synced folder is not this machine; roots come from the `OneDrive*`
environment variables and from the checkout's own ancestry). The directory is
created on first write.

Storage
-------
`truth.jsonl` — append-only; one record per adjudication EVENT (several per
sha are allowed; the LATEST event per sha is the current verdict). Every
record carries `prev` (the previous record's hash, `GENESIS` for the first)
and `hash` (sha256 over the canonical JSON of every field but `hash`), so the
file is a chain: `verify_chain()` refuses a rewritten, reordered, or
head-removed file. `manifest.json` remembers `store_version`, `record_count`,
`chain_head` and `updated_at`; EVERY append and every read that yields a
verdict first calls `verify_against_manifest()`, so a truncated tail is
refused, never re-sealed by the next append (review MAJOR-1).

What is never stored
--------------------
Free notes (only their sha256), a sampled row's description text (only its
sha256 over a normalised form), an adjudicator's email (a role code only).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

SEALED_TRUTH_DIR_ENV = "SEALED_TRUTH_DIR"
STORE_VERSION = 1
GENESIS = "GENESIS"
TRUTH_FILE = "truth.jsonl"
MANIFEST_FILE = "manifest.json"
HOLDOUT_FILE = "holdout.jsonl"
HOLDOUT_MANIFEST_FILE = "holdout_manifest.json"

#: The closed document-kind vocabulary (the umbrella's classifier contract; one per document).
KINDS = (
    "STATEMENT_COMPLETE",
    "STATEMENT_PARTIAL",
    "STATEMENT_ILLEGIBLE",
    "ACTIVITY_EXPORT",
    "NOT_A_STATEMENT",
    "FILE_INVALID",
    "KIND_UNCERTAIN",
)
ACCOUNT_KINDS = ("deposit", "card", "loan", "brokerage", "unknown")
MODALITIES = ("digital", "scanned", "mixed", "image_backed_text", "unknown")
COMPLETENESS_CODES = (
    "missing_pages",
    "missing_opening",
    "missing_closing",
    "missing_period",
    "missing_first_page",
    "table_truncated",
    "page_gap",
    "balance_discontinuity_at_page_break",
)
MAX_SAMPLED_ROWS = 3

#: Path components under which a store or a packet directory is never accepted.
FORBIDDEN_COMPONENTS = (".claude", "bank statements")
#: Environment variables (by upper-cased prefix) that name a synced OneDrive root.
ONEDRIVE_ENV_PREFIX = "ONEDRIVE"

_SHA256_RE = re.compile(r"[0-9A-Fa-f]{64}")
_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,39}")
_ROLE_RE = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_CHAIN_KEYS = ("seq", "prev", "hash")
_RETRIES = 5


class StoreError(Exception):
    """Base class for every refusal of this package."""


class StoreLocationError(StoreError):
    """The store (or a packet directory) would live somewhere it must not."""


class ChainError(StoreError):
    """The append-only file has been rewritten, reordered, truncated or removed."""


class RecordError(StoreError):
    """A record's field is outside its closed vocabulary or malformed."""


# --- location ---------------------------------------------------------------


def _this_checkout_root() -> Path:
    """The git checkout that holds this file, else the package folder."""
    package = Path(__file__).resolve().parents[2]
    return next((path for path in (package, *package.parents) if (path / ".git").exists()), package)


def _main_repository_root(checkout: Path) -> Path | None:
    """For a git worktree, the repository whose `.git/worktrees/` names it."""
    gitfile = checkout / ".git"
    try:
        if not gitfile.is_file():
            return None
        text = gitfile.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not text.startswith("gitdir:"):
        return None
    gitdir = Path(text[len("gitdir:"):].strip())
    for parent in gitdir.parents:
        if parent.name == ".git":
            return parent.parent.resolve()
    return None


def repository_roots() -> tuple[Path, ...]:
    """This checkout's root and, for a worktree, the main repository's root."""
    root = _this_checkout_root()
    roots = [root]
    main = _main_repository_root(root)
    if main is not None and main != root:
        roots.append(main)
    return tuple(roots)


def onedrive_roots(env: Mapping[str, str] | None = None) -> tuple[Path, ...]:
    """Synced roots: every `OneDrive*` environment variable's directory, plus
    every ancestor of a repository root whose name starts with `OneDrive`."""
    env = os.environ if env is None else env
    roots: list[Path] = []
    for name, value in env.items():
        if name.upper().startswith(ONEDRIVE_ENV_PREFIX) and value and value.strip():
            candidate = Path(value.strip())
            if candidate.is_absolute():
                roots.append(candidate.resolve())
    for root in repository_roots():
        for ancestor in root.parents:
            if ancestor.name.lower().startswith("onedrive"):
                roots.append(ancestor)
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return tuple(unique)


def forbidden_ancestor(path: Path) -> str | None:
    """Why `path` (already resolved) may not hold sealed material, or None."""
    for part in path.parts:
        if part.lower() in FORBIDDEN_COMPONENTS:
            return f"under a {part!r} path component"
        if part.lower().startswith("onedrive"):
            return f"under a {part!r} path component (a synced folder is not this machine)"
    for root in repository_roots():
        if path == root or root in path.parents:
            return f"inside the repository checkout {root}"
        if path in root.parents:
            return f"an ancestor of the repository checkout {root}"
        parent = root.parent
        if path == parent or parent in path.parents:
            return f"under the checkout's parent directory {parent}"
    for ancestor in (path, *path.parents):
        if (ancestor / ".git").exists():
            return f"inside a git checkout ({ancestor})"
    for synced in onedrive_roots():
        if path == synced or synced in path.parents:
            return f"under a OneDrive root ({synced}); the store lives on this machine, never in a synced folder"
    return None


def refuse_inside_checkout(path: Path | str, *, what: str) -> Path:
    """Resolve `path`, refusing anything relative or inside a checkout."""
    text = str(path).strip()
    if not text:
        raise StoreLocationError(f"{what}: an empty path is not a location")
    raw = Path(text)
    if not raw.is_absolute():
        raise StoreLocationError(f"{what}: must be an absolute path, got {raw!s}")
    resolved = raw.resolve()
    reason = forbidden_ancestor(resolved)
    if reason is not None:
        raise StoreLocationError(f"{what}: refused, {reason}: {resolved}")
    return resolved


def resolve_store_dir(env: Mapping[str, str] | None = None) -> Path:
    """`SEALED_TRUTH_DIR` from the environment, validated; never created here."""
    env = os.environ if env is None else env
    value = env.get(SEALED_TRUTH_DIR_ENV)
    if value is None or not value.strip():
        raise StoreLocationError(
            f"{SEALED_TRUTH_DIR_ENV} is not set; the sealed truth store has no default location"
        )
    return refuse_inside_checkout(value, what=SEALED_TRUTH_DIR_ENV)


# --- hashing and canonical forms --------------------------------------------


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def content_sha256_of(data: bytes) -> str:
    """UPPERCASE hex sha256 of raw file bytes — the repository's content-sha
    convention (`corpus_gate.sha256_upper`; `ocr/inspect.py::content_sha256`),
    restated here so this package imports nothing from production."""
    return hashlib.sha256(data).hexdigest().upper()


def record_hash(record: Mapping) -> str:
    return sha256_hex(canonical_json({k: v for k, v in record.items() if k != "hash"}))


def _normalize_text(text: str) -> str:
    return " ".join(str(text).split()).casefold()


def description_hash(text: str) -> str:
    """sha256 over a normalised description (whitespace-collapsed, casefolded)
    so a later ledger comparison can recompute it from the system's row."""
    return sha256_hex("description:" + _normalize_text(text))


def notes_hash(text: str | None) -> str | None:
    if text is None or not str(text).strip():
        return None
    return sha256_hex("notes:" + str(text).strip())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_utc(value: str | None, *, what: str) -> str:
    if value is None:
        return utc_now_iso()
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RecordError(f"{what}: not an ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise RecordError(f"{what}: must be UTC (+00:00): {value!r}")
    return parsed.replace(microsecond=0).isoformat()


def _retry(action):
    """OneDrive-style transient PermissionErrors are retried, never scored."""
    for attempt in range(_RETRIES):
        try:
            return action()
        except PermissionError:
            if attempt == _RETRIES - 1:
                raise
            time.sleep(0.2 * (attempt + 1))


# --- the append-only chain ---------------------------------------------------


class ChainedJsonl:
    """An append-only JSONL file whose records form a hash chain, with a
    sidecar manifest that remembers the head so a truncated tail is caught."""

    def __init__(self, path: Path, manifest_path: Path | None = None):
        self.path = path
        self.manifest_path = manifest_path

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        records: list[dict] = []
        text = _retry(lambda: self.path.read_text(encoding="utf-8"))
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ChainError(f"{self.path.name}: line {number} is not JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ChainError(f"{self.path.name}: line {number} is not a record")
            records.append(record)
        return records

    def verify(self, records: list[dict] | None = None) -> str:
        """Walk the chain; return its head; refuse any break."""
        records = self.read() if records is None else records
        previous = GENESIS
        for index, record in enumerate(records, 1):
            for key in _CHAIN_KEYS:
                if key not in record:
                    raise ChainError(f"{self.path.name}: record {index} lacks {key!r}")
            if record["seq"] != index:
                raise ChainError(
                    f"{self.path.name}: record {index} carries seq {record['seq']!r} "
                    f"(reordered, removed or inserted)"
                )
            if record["prev"] != previous:
                raise ChainError(
                    f"{self.path.name}: record {index} does not name the previous record's hash"
                )
            if record_hash(record) != record["hash"]:
                raise ChainError(f"{self.path.name}: record {index} was rewritten (hash mismatch)")
            previous = record["hash"]
        return previous

    def head(self) -> str:
        return self.verify()

    def read_manifest(self) -> dict | None:
        if self.manifest_path is None or not self.manifest_path.exists():
            return None
        return json.loads(_retry(lambda: self.manifest_path.read_text(encoding="utf-8")))

    def verify_against_manifest(self, records: list[dict] | None = None) -> str:
        """The chain must be intact AND agree with the sidecar manifest: a
        file whose tail was removed still chains, but its head and count no
        longer match what the manifest remembered."""
        records = self.read() if records is None else records
        head = self.verify(records)
        manifest = self.read_manifest()
        if manifest is None:
            if records:
                raise ChainError(
                    f"{self.path.name} has records but {self.manifest_path.name if self.manifest_path else 'the manifest'} is missing"
                )
            return head
        if manifest.get("chain_head") != head or manifest.get("record_count") != len(records):
            raise ChainError(
                f"{self.manifest_path.name} disagrees with {self.path.name} (truncated or replaced file): "
                f"manifest {manifest.get('record_count')} records / head "
                f"{str(manifest.get('chain_head'))[:12]}, file {len(records)} / {head[:12]}"
            )
        return head

    def write_manifest(self, records: list[dict] | None = None, *,
                       previous: tuple[str, int] | None = None) -> dict:
        """Write the sidecar — never as a re-seal of a file the existing sidecar
        disagrees with (review NEW-3). `previous` is the (head, count) the
        existing manifest must carry: the state before an append. Without it,
        the existing manifest must already agree with the file (a consistent
        store may be re-sealed; a truncated one is refused)."""
        if self.manifest_path is None:
            raise ChainError(f"{self.path.name}: no manifest path configured")
        records = self.read() if records is None else records
        head = self.verify(records)
        existing = self.read_manifest()
        if existing is not None:
            expected = previous if previous is not None else (head, len(records))
            if (existing.get("chain_head"), existing.get("record_count")) != expected:
                raise ChainError(
                    f"{self.manifest_path.name} disagrees with {self.path.name}; refusing to re-seal "
                    f"(manifest {existing.get('record_count')} records / head "
                    f"{str(existing.get('chain_head'))[:12]}, expected {expected[1]} / {expected[0][:12]})"
                )
        manifest = {
            "store_version": STORE_VERSION,
            "record_count": len(records),
            "chain_head": head,
            "updated_at": utc_now_iso(),
        }
        text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        target = self.manifest_path

        def _write():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".json.tmp")
            temporary.write_text(text, encoding="utf-8")
            os.replace(temporary, target)

        _retry(_write)
        return manifest

    def append(self, payload: Mapping, *, records: list[dict] | None = None) -> dict:
        """Append ONE record — only after the chain and its manifest agree
        (review MAJOR-1: a truncated tail is never re-sealed)."""
        records = self.read() if records is None else records
        head = self.verify_against_manifest(records)
        record = dict(payload)
        for key in _CHAIN_KEYS:
            if key in record:
                raise RecordError(f"{key!r} is assigned by the chain, never supplied")
        record["seq"] = len(records) + 1
        record["prev"] = head
        record["hash"] = record_hash(record)
        line = canonical_json(record) + "\n"

        def _write():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

        _retry(_write)
        if self.manifest_path is not None:
            self.write_manifest(records + [record], previous=(head, len(records)))
        return record


# --- record validation -------------------------------------------------------


def validate_sha(value, *, what: str = "content_sha256") -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value.strip()):
        raise RecordError(f"{what}: not a 64-hex sha256: {value!r}")
    return value.strip().upper()


def _choice(name: str, value, choices: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise RecordError(f"{name}: {value!r} is not one of {choices}")
    return value


def _code_or_none(name: str, value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _CODE_RE.fullmatch(value):
        raise RecordError(f"{name}: must be a lowercase code (never free text or a name): {value!r}")
    return value


def _bool(name: str, value) -> bool:
    if not isinstance(value, bool):
        raise RecordError(f"{name}: must be a boolean, got {value!r}")
    return value


def _count_or_none(name: str, value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RecordError(f"{name}: must be a non-negative integer or null, got {value!r}")
    return value


def _date_or_none(name: str, value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RecordError(f"{name}: must be an ISO date string or null, got {value!r}")
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError as exc:
        raise RecordError(f"{name}: not an ISO date (YYYY-MM-DD): {value!r}") from exc


def _money_or_none(name: str, value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise RecordError(f"{name}: must be a decimal figure or null, got {value!r}")
    try:
        figure = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise RecordError(f"{name}: not a plain decimal figure (no separators): {value!r}") from exc
    if not figure.is_finite():
        raise RecordError(f"{name}: not a finite figure: {value!r}")
    return format(figure, "f")


def _hex64(name: str, value) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value.strip()):
        raise RecordError(f"{name}: not a 64-hex digest: {value!r}")
    return value.strip().lower()


def _role(name: str, value) -> str:
    if not isinstance(value, str) or "@" in value or not _ROLE_RE.fullmatch(value.strip()):
        raise RecordError(f"{name}: must be a role code (never an email or a name): {value!r}")
    return value.strip()


def validate_role(value, *, what: str = "adjudicator") -> str:
    """A role code such as `principal_adjudicator`; never an email or a name."""
    return _role(what, value)


def _findings(value) -> list[str]:
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise RecordError("completeness_findings: must be a list of closed codes")
    codes = []
    for code in value:
        codes.append(_choice("completeness_findings", code, COMPLETENESS_CODES))
    return sorted(set(codes))


def _sampled_rows(value) -> list[dict]:
    if isinstance(value, (str, Mapping)) or not isinstance(value, Iterable):
        raise RecordError("sampled_rows: must be a list")
    rows = list(value)
    if len(rows) > MAX_SAMPLED_ROWS:
        raise RecordError(f"sampled_rows: at most {MAX_SAMPLED_ROWS} rows, got {len(rows)}")
    stored: list[dict] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise RecordError(f"sampled_rows[{index}]: must be a mapping")
        extra = set(row) - {"date", "description", "description_hash", "amount"}
        if extra:
            raise RecordError(f"sampled_rows[{index}]: unknown keys {sorted(extra)}")
        if ("description" in row) == ("description_hash" in row):
            raise RecordError(
                f"sampled_rows[{index}]: exactly one of description / description_hash"
            )
        if "date" not in row or "amount" not in row:
            raise RecordError(f"sampled_rows[{index}]: date and amount are required")
        if "description" in row:
            if not isinstance(row["description"], str) or not row["description"].strip():
                raise RecordError(f"sampled_rows[{index}]: description must be non-empty text")
            digest = description_hash(row["description"])
        else:
            digest = _hex64(f"sampled_rows[{index}].description_hash", row["description_hash"])
        stored.append({
            "date": _date_or_none(f"sampled_rows[{index}].date", row["date"]),
            "description_hash": digest,
            "amount": _money_or_none(f"sampled_rows[{index}].amount", row["amount"]),
        })
        if stored[-1]["date"] is None or stored[-1]["amount"] is None:
            raise RecordError(f"sampled_rows[{index}]: date and amount may not be null")
    return stored


def build_record(
    *,
    seq: int,
    content_sha256,
    kind,
    sub_kind,
    account_kind,
    modality,
    completeness_findings,
    legible,
    account_count,
    printed_period_start,
    printed_period_end,
    opening_balance,
    closing_balance,
    printed_transaction_count,
    sampled_rows,
    adjudicator,
    packet_digest,
    notes=None,
    adjudicated_at=None,
) -> dict:
    """Validate every field against its closed vocabulary; return the payload
    (without the chain fields, which the chain assigns)."""
    sha = validate_sha(content_sha256)
    start = _date_or_none("printed_period_start", printed_period_start)
    end = _date_or_none("printed_period_end", printed_period_end)
    if start is not None and end is not None and end < start:
        raise RecordError("printed_period_end precedes printed_period_start")
    return {
        "record_id": f"{seq:06d}-{sha[:16]}",
        "store_version": STORE_VERSION,
        "content_sha256": sha,
        "kind": _choice("kind", kind, KINDS),
        "sub_kind": _code_or_none("sub_kind", sub_kind),
        "account_kind": _choice("account_kind", account_kind, ACCOUNT_KINDS),
        "modality": _choice("modality", modality, MODALITIES),
        "completeness_findings": _findings(completeness_findings),
        "legible": _bool("legible", legible),
        "account_count": _count_or_none("account_count", account_count),
        "printed_period_start": start,
        "printed_period_end": end,
        "opening_balance": _money_or_none("opening_balance", opening_balance),
        "closing_balance": _money_or_none("closing_balance", closing_balance),
        "printed_transaction_count": _count_or_none(
            "printed_transaction_count", printed_transaction_count
        ),
        "sampled_rows": _sampled_rows(sampled_rows),
        "adjudicator": _role("adjudicator", adjudicator),
        "adjudicated_at": normalize_utc(adjudicated_at, what="adjudicated_at"),
        "packet_digest": _hex64("packet_digest", packet_digest),
        "notes_hash": notes_hash(notes),
    }


# --- the store ---------------------------------------------------------------


class TruthStore:
    """The sealed store: open, append, verify, aggregate. Nothing else."""

    def __init__(self, directory: Path | str):
        self.directory = refuse_inside_checkout(directory, what="the sealed truth store")
        self.truth_path = self.directory / TRUTH_FILE
        self.manifest_path = self.directory / MANIFEST_FILE
        self._chain = ChainedJsonl(self.truth_path, self.manifest_path)

    @classmethod
    def open(cls, env: Mapping[str, str] | None = None) -> "TruthStore":
        return cls(resolve_store_dir(env))

    def records(self) -> list[dict]:
        return self._chain.read()

    def verify_chain(self) -> str:
        return self._chain.verify()

    def verify_against_manifest(self) -> str:
        return self._chain.verify_against_manifest()

    def append_record(self, **fields) -> dict:
        records = self.records()
        self._chain.verify_against_manifest(records)  # MAJOR-1: never append to a truncated file
        payload = build_record(seq=len(records) + 1, **fields)
        return self._chain.append(payload, records=records)

    def latest_by_sha(self) -> dict[str, dict]:
        """Current verdict per sha — only from a store that agrees with its manifest."""
        records = self.records()
        self._chain.verify_against_manifest(records)
        latest: dict[str, dict] = {}
        for record in records:
            latest[record["content_sha256"]] = record
        return latest

    def counts_by_kind(self) -> dict[str, int]:
        counts = Counter(record["kind"] for record in self.latest_by_sha().values())
        return {kind: counts[kind] for kind in KINDS if counts[kind]}

    def adjudicated_sha16s(self) -> list[str]:
        return sorted(sha[:16] for sha in self.latest_by_sha())

    def manifest(self) -> dict:
        manifest = self._chain.read_manifest()
        if manifest is not None:
            return manifest
        return {
            "store_version": STORE_VERSION,
            "record_count": 0,
            "chain_head": GENESIS,
            "updated_at": None,
        }

    def write_manifest(self, records: list[dict] | None = None) -> dict:
        return self._chain.write_manifest(records)
