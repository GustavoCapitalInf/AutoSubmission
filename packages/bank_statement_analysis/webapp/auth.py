"""The request gate: a shared password for the browser, a bearer token for the machine API.

This is a D-2b slice, not the production auth trio. Local development still
defaults to loopback with no login. Binding beyond loopback (Docker, a shared
VM, Codespaces port-forward) is refused unless `WEBAPP_AUTH_PASSWORD` is set.
When that password is set, every data-bearing browser route requires HTTP Basic.
The API under /api/v1 requires `WEBAPP_API_TOKEN` as a bearer token, and each
credential opens only its own routes (docs/api/v1.md). `/healthz` is the only
unauthenticated surface, and it returns no document data.
"""
from __future__ import annotations

import os
from hashlib import sha256
from secrets import compare_digest

from flask import Response, request

from .api.wire import error_response, is_api_path

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "::"})
DEFAULT_AUTH_USER = "intern"
HEALTHZ_PATH = "/healthz"
#: The shortest WEBAPP_API_TOKEN that turns the API on.
API_TOKEN_MIN_LENGTH = 32
API_CHALLENGE = 'Bearer realm="bank-statement-analysis-api"'


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


def api_token() -> str | None:
    """WEBAPP_API_TOKEN, or None when the API is off: unset, shorter than API_TOKEN_MIN_LENGTH, or equal to the browser
    password, so that each credential opens only its own routes."""
    token = os.environ.get("WEBAPP_API_TOKEN", "").strip()
    if len(token) < API_TOKEN_MIN_LENGTH or token == auth_password():
        return None
    return token


def _bearer() -> str | None:
    """The credentials of an Authorization header whose scheme is Bearer, in any case; None for any other header."""
    parts = request.headers.get("Authorization", "").split(None, 1)
    if not parts or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() if len(parts) > 1 else ""


def gate() -> Response | None:
    """The one request gate (webapp/app.py registers it before every other hook). `/healthz` is open. A path in the
    API's URL space needs the bearer token and accepts nothing else; while the API is off it answers `api_disabled`.
    Every other path keeps the Basic rule (`request_is_authorized`) and refuses a request carrying a bearer token,
    whether or not a browser password is set."""
    if request.path == HEALTHZ_PATH:
        return None
    if is_api_path(request.path):
        token = api_token()
        if token is None:
            return error_response("api_disabled")
        presented = _bearer()
        if presented is not None and compare_digest(sha256(presented.encode()).digest(),
                                                    sha256(token.encode()).digest()):
            return None
        return error_response("unauthorized", headers={"WWW-Authenticate": API_CHALLENGE})
    if _bearer() is not None or not request_is_authorized():
        return unauthorized()
    return None
