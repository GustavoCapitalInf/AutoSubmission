"""Intern-testing host gate — a D-2b slice, not the full auth trio.

The webapp still defaults to loopback with no login (D-2a). Intern staging
binds beyond loopback on purpose, so it must refuse to start without a shared
password and must 401 every data-bearing route until that password is
presented. `/healthz` is the only unauthenticated surface, and it returns
no document data.
"""
from __future__ import annotations

import os
import sys
import types
from base64 import b64encode

import pytest

from webapp.app import app, main
from webapp.auth import refuse_unauthenticated_bind


def _basic(user: str, password: str) -> dict[str, str]:
    token = b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_refuse_unauthenticated_bind_allows_loopback_without_password(monkeypatch):
    monkeypatch.delenv("WEBAPP_AUTH_PASSWORD", raising=False)
    refuse_unauthenticated_bind("127.0.0.1")
    refuse_unauthenticated_bind("localhost")
    refuse_unauthenticated_bind("::1")


def test_refuse_unauthenticated_bind_rejects_non_loopback_without_password(monkeypatch):
    monkeypatch.delenv("WEBAPP_AUTH_PASSWORD", raising=False)
    with pytest.raises(SystemExit) as exc:
        refuse_unauthenticated_bind("0.0.0.0")
    assert "WEBAPP_AUTH_PASSWORD" in str(exc.value)


def test_refuse_unauthenticated_bind_allows_non_loopback_with_password(monkeypatch):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", "intern-secret")
    refuse_unauthenticated_bind("0.0.0.0")


def test_main_refuses_non_loopback_without_password(monkeypatch):
    monkeypatch.setenv("WEBAPP_HOST", "0.0.0.0")
    monkeypatch.delenv("WEBAPP_AUTH_PASSWORD", raising=False)

    def explode(*_args, **_kwargs):  # pragma: no cover - guard
        raise AssertionError("waitress must not start without a password")

    monkeypatch.setitem(sys.modules, "waitress", types.SimpleNamespace(serve=explode))
    with pytest.raises(SystemExit) as exc:
        main()
    assert "WEBAPP_AUTH_PASSWORD" in str(exc.value)


def test_main_serves_non_loopback_when_password_is_set(monkeypatch):
    calls = {}

    def fake_serve(wsgi_app, **kwargs):
        calls["app"] = wsgi_app
        calls["kwargs"] = kwargs

    monkeypatch.setitem(sys.modules, "waitress", types.SimpleNamespace(serve=fake_serve))
    monkeypatch.setenv("WEBAPP_HOST", "0.0.0.0")
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", "intern-secret")
    main()
    assert calls["app"] is app
    assert calls["kwargs"]["host"] == "0.0.0.0"


def test_loopback_without_password_does_not_require_auth(monkeypatch):
    monkeypatch.delenv("WEBAPP_AUTH_PASSWORD", raising=False)
    resp = app.test_client().get("/")
    assert resp.status_code == 200


def test_unauthenticated_request_is_401_when_password_set(monkeypatch):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", "intern-secret")
    resp = app.test_client().get("/")
    assert resp.status_code == 401
    assert "Basic" in resp.headers.get("WWW-Authenticate", "")


def test_wrong_password_is_401(monkeypatch):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", "intern-secret")
    resp = app.test_client().get("/", headers=_basic("intern", "nope"))
    assert resp.status_code == 401


def test_correct_password_reaches_the_dashboard(monkeypatch):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", "intern-secret")
    resp = app.test_client().get("/", headers=_basic("intern", "intern-secret"))
    assert resp.status_code == 200
    assert "<title>Capital Infusion</title>" in resp.get_data(as_text=True)


def test_auth_user_override_is_honoured(monkeypatch):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", "intern-secret")
    monkeypatch.setenv("WEBAPP_AUTH_USER", "qa")
    denied = app.test_client().get("/", headers=_basic("intern", "intern-secret"))
    allowed = app.test_client().get("/", headers=_basic("qa", "intern-secret"))
    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_healthz_is_unauthenticated_and_carries_no_document_data(monkeypatch):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", "intern-secret")
    resp = app.test_client().get("/healthz")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"ok": True}


def test_upload_without_password_is_401_when_auth_is_on(monkeypatch):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", "intern-secret")
    resp = app.test_client().post("/upload")
    assert resp.status_code == 401
