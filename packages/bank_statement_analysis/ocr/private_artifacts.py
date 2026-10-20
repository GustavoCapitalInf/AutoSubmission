"""Resolve private output locations without creating or reading files.

The web app's default data directory lives under this root (`webapp/storage.py`, the data-directory rule). The
`VISUAL_PAIR_PRIVATE_ROOT` name, the `phase31-private` default and the `visual_pair_private_*` error codes are
leftovers of the visual pair, which was removed (model-code removal, slice S4); they are kept unchanged for
compatibility, so an existing environment, `run.ps1` and every stored location resolve exactly as before.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

PRIVATE_ROOT_ENV = "VISUAL_PAIR_PRIVATE_ROOT"
CHECKOUT_ROOT = Path(__file__).resolve().parents[1]


class PrivateArtifactPathError(ValueError):
    """A closed configuration error that never includes a supplied path."""


def validate_private_artifact_path(path: str | Path) -> Path:
    """Require an absolute path outside the checkout, including symlink targets."""
    try:
        supplied = Path(path)
        if not supplied.is_absolute():
            raise PrivateArtifactPathError("visual_pair_private_path_must_be_absolute")
        lexical = Path(os.path.abspath(supplied))
        resolved = supplied.resolve()
        checkout = CHECKOUT_ROOT.resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        if isinstance(exc, PrivateArtifactPathError):
            raise
        raise PrivateArtifactPathError("visual_pair_private_path_invalid") from None
    if lexical.is_relative_to(checkout) or resolved.is_relative_to(checkout):
        raise PrivateArtifactPathError("visual_pair_private_path_must_be_outside_checkout")
    return resolved


def private_artifact_root(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    configured = env.get(PRIVATE_ROOT_ENV)
    default = Path.home() / ".local" / "share" / "bank-statement-analysis" / "phase31-private"
    return validate_private_artifact_path(default if configured is None else configured)


def private_artifact_path(*parts: str, environ: Mapping[str, str] | None = None) -> Path:
    """Resolve a purpose-specific child; recheck any existing child symlinks."""
    if any(Path(part).is_absolute() or ".." in Path(part).parts for part in parts):
        raise PrivateArtifactPathError("visual_pair_private_child_invalid")
    root = private_artifact_root(environ)
    target = validate_private_artifact_path(root.joinpath(*parts))
    if not target.is_relative_to(root):
        raise PrivateArtifactPathError("visual_pair_private_child_escapes_root")
    return target
