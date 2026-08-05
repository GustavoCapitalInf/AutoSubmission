"""Environment-driven settings for the underwriter web app and the versioned API.

Every production control (durable store location, upload limits, retention,
rate limits, credentials) is read from the environment so the same image can run
on company-controlled infrastructure without code changes. Defaults are the safe
ones: no credentials configured means the `/v1` API refuses to serve rather than
serving anonymously.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_TENANT = "default"

#: Bumped only when a `/v1` response shape changes in a backwards-compatible
#: way; breaking changes get a new URL prefix instead.
API_VERSION = "v1"
SCHEMA_VERSION = "1.0"


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_json(name: str) -> object | None:
    value = _env(name)
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


@dataclass(frozen=True)
class Settings:
    job_store: str
    database_path: Path
    max_upload_bytes: int
    max_pages: int
    worker_threads: int
    lease_seconds: int
    max_attempts: int
    retention_days: int
    api_rate_limit_per_minute: int
    upload_rate_limit_per_minute: int
    ui_auth_required: bool
    secret_key: str | None
    api_key_specs: tuple[dict, ...]
    ui_user_specs: tuple[dict, ...]

    @property
    def auth_configured(self) -> bool:
        return bool(self.api_key_specs)

    @property
    def retention_seconds(self) -> int:
        return self.retention_days * 86400


def _credential_specs(env_name: str, file_env_name: str, secret_field: str) -> tuple[dict, ...]:
    """Credentials come from a JSON list (inline or in a file) or from a compact
    `secret:tenant:role` list. The compact form keeps a single-tenant deployment
    to one environment variable; the JSON form carries stable principal ids and
    pre-hashed secrets for anything larger."""
    payload = _env_json(env_name)
    if payload is None:
        path = _env(file_env_name)
        if path:
            try:
                payload = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
    if isinstance(payload, list):
        return tuple(item for item in payload if isinstance(item, dict))

    raw = _env(env_name)
    if not raw:
        return ()
    specs: list[dict] = []
    for entry in raw.replace("\n", ",").split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = [part.strip() for part in entry.split(":")]
        if secret_field == "secret":
            secret, tenant, role = (parts + [DEFAULT_TENANT, "underwriter"])[:3]
            if not secret:
                continue
            specs.append({"secret": secret, "tenant": tenant, "role": role})
        else:
            username, secret, tenant, role = (parts + ["", DEFAULT_TENANT, "underwriter"])[:4]
            if not username or not secret:
                continue
            specs.append(
                {"username": username, "password": secret, "tenant": tenant, "role": role}
            )
    return tuple(specs)


def load_settings() -> Settings:
    database_path = Path(_env("BSA_JOB_DB") or (REPO_ROOT / "var" / "jobs.db"))
    return Settings(
        job_store=(_env("BSA_JOB_STORE") or "sqlite").lower(),
        database_path=database_path,
        max_upload_bytes=_env_int("BSA_MAX_UPLOAD_MB", 25) * 1024 * 1024,
        max_pages=_env_int("BSA_MAX_PAGES", 200),
        worker_threads=max(1, _env_int("BSA_WORKER_THREADS", 1)),
        lease_seconds=_env_int("BSA_JOB_LEASE_SECONDS", 900),
        max_attempts=max(1, _env_int("BSA_JOB_MAX_ATTEMPTS", 3)),
        retention_days=_env_int("BSA_RETENTION_DAYS", 90),
        api_rate_limit_per_minute=_env_int("BSA_RATE_LIMIT_PER_MINUTE", 120),
        upload_rate_limit_per_minute=_env_int("BSA_UPLOAD_RATE_LIMIT_PER_MINUTE", 30),
        ui_auth_required=_env_bool("BSA_UI_AUTH_REQUIRED", False),
        secret_key=_env("BSA_SECRET_KEY"),
        api_key_specs=_credential_specs("BSA_API_KEYS", "BSA_API_KEYS_FILE", "secret"),
        ui_user_specs=_credential_specs("BSA_UI_USERS", "BSA_UI_USERS_FILE", "password"),
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reload_settings() -> Settings:
    """Re-read the environment. Used by tests and by an operator-triggered
    credential rotation; nothing caches a Settings instance beyond this module."""
    global _settings
    _settings = load_settings()
    return _settings
