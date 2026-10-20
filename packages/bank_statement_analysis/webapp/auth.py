"""Shared-password gate for intern staging.

This is a D-2b slice, not the production auth trio. Local development still
defaults to loopback with no login. Binding beyond loopback (Docker, a shared
VM, Codespaces port-forward) is refused unless `WEBAPP_AUTH_PASSWORD` is set.
When that password is set, every data-bearing route requires HTTP Basic.
`/healthz` is the only unauthenticated surface, and it returns no document
data.
"""
from __future__ import annotations

import os
from secrets import compare_digest

from flask import Response, request

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "::"})
DEFAULT_AUTH_USER = "intern"
HEALTHZ_PATH = "/healthz"


def auth_password() -> str:
    return os.environ.get("WEBAPP_AUTH_PASSWORD", "").strip()


def auth_user() -> str:
    return os.environ.get("WEBAPP_AUTH_USER", "").strip() or DEFAULT_AUTH_USER


def is_loopback_host(host: str) -> bool:
    return host.strip().lower() in LOOPBACK_HOSTS


def refuse_unauthenticated_bind(host: str) -> None:
    """Fail closed when exposing the unauthenticated app off this machine."""
    if is_loopback_host(host):
        return
    if auth_password():
        return
    raise SystemExit(
        "WEBAPP_HOST is not loopback and WEBAPP_AUTH_PASSWORD is unset. "
        "Refusing to expose the unauthenticated webapp. Set "
        "WEBAPP_AUTH_PASSWORD or bind WEBAPP_HOST=127.0.0.1."
    )


def unauthorized() -> Response:
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Intern testing"'},
    )


def request_is_authorized() -> bool:
    password = auth_password()
    if not password:
        return True
    if request.path == HEALTHZ_PATH:
        return True
    auth = request.authorization
    if auth is None:
        return False
    user_ok = compare_digest(auth.username or "", auth_user())
    password_ok = compare_digest(auth.password or "", password)
    return user_ok and password_ok
