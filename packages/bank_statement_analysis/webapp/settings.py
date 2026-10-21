"""Owner display settings for the web app, kept in ``<data_dir>/settings.json``.

A JSON file rather than a table on purpose: ``webapp/storage.py`` refuses a
database whose schema is newer than the running code, so a settings table
would lock the data directory against every older checkout. A settings file
changes nothing another checkout reads.

Settings change how a stored analysis is PRESENTED (served, exported and
packaged); they never rewrite the stored record, and flipping one takes effect
on every job at once, with no reprocessing.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path

from analysis.display_settings import DEFAULTS

SETTINGS_FILE = "settings.json"

_LOCK = threading.Lock()


def _path(data_dir: str | Path) -> Path:
    return Path(data_dir) / SETTINGS_FILE


def _replace(source: str, target: Path, attempts: int = 20) -> None:
    """os.replace, retried briefly: on Windows it fails while another thread has the target open for reading,
    and a reader holds it for microseconds. Anything still failing after that is raised."""
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.01)


def load_settings(data_dir: str | Path) -> dict[str, bool]:
    """The current settings. A missing, unreadable or malformed file, or a malformed value, reads as the
    default: a display preference must never stop the dashboard from serving."""
    settings = dict(DEFAULTS)
    raw = None
    for attempt in range(5):
        try:
            raw = json.loads(_path(data_dir).read_text(encoding="utf-8"))
            break
        except PermissionError:
            # Windows: a save is renaming over the file this instant. Retry briefly, as _replace does.
            time.sleep(0.01)
        except (OSError, ValueError):
            return settings
    if isinstance(raw, dict):
        for key, default in DEFAULTS.items():
            if isinstance(raw.get(key), type(default)):
                settings[key] = raw[key]
    return settings


def save_settings(data_dir: str | Path, updates: object) -> dict[str, bool]:
    """Apply ``updates`` and return the saved settings. Raises ``ValueError`` for anything but an object of
    known keys with values of the right type; nothing is written then."""
    if not isinstance(updates, dict) or not updates:
        raise ValueError("settings update must be a non-empty object")
    for key, value in updates.items():
        if key not in DEFAULTS:
            raise ValueError("unknown setting")  # fixed text: the key came from the request
        if not isinstance(value, type(DEFAULTS[key])):
            raise ValueError(f"setting {key} must be {type(DEFAULTS[key]).__name__}")
    with _LOCK:
        settings = {**load_settings(data_dir), **updates}
        target = _path(data_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename, so a reader never sees a half-written file.
        handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".settings-", suffix=".json")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(settings, stream, indent=2, sort_keys=True)
            _replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    return settings
