import base64
import uuid

import pytest

from tests.api_client import TOKEN, analysed, make_api, package_path, pdf, validated
from tests.test_webapp_studio_views import _single

PASSWORD = "fabricated-browser-password-0123456789"
BASIC = {"Authorization": "Basic " + base64.b64encode(f"intern:{PASSWORD}".encode()).decode()}
BEARER = {"Authorization": f"Bearer {TOKEN}"}
BROWSER_ROUTES = ["/", "/status/{job}", "/api/settings", "/package_analysis?ids={job}"]


@pytest.fixture
def api(tmp_path, monkeypatch):
    return make_api(tmp_path, monkeypatch)


def _job(api) -> str:
    job = api.store.create("march.pdf")
    api.store.set_result(job.id, "# Fabricated", "<p>Fabricated</p>", analysis=_single())
    return job.id


@pytest.mark.parametrize("token", [None, "", "short-fabricated-token", PASSWORD])
def test_every_api_request_is_refused_while_the_api_has_no_usable_token(api, monkeypatch, token):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", PASSWORD)
    if token is None:
        monkeypatch.delenv("WEBAPP_API_TOKEN")
    else:
        monkeypatch.setenv("WEBAPP_API_TOKEN", token)
    presented = token or TOKEN
    responses = [
        api.get(package_path(), token=presented),
        api.put(package_path(), [("a.pdf", pdf())], token=presented),
        api.get("/api/v1/no-such-route", token=presented),
        api.get("/api/v1", token=None),
    ]
    assert [(response.status_code, response.get_json()["error"]["code"]) for response in responses] == [
        (503, "api_disabled")] * 4


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer fabricated-wrong-token-0000000000000000"},
                                     {"Authorization": f"Basic {TOKEN}"}, BASIC, {"Authorization": TOKEN},
                                     {"Authorization": "Bearer"}])
def test_an_api_request_without_the_token_is_unauthorized(api, monkeypatch, headers):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", PASSWORD)
    for path in (package_path(), "/api/v1/no-such-route", "/api/v1"):
        response = validated(api.client.get(path, headers=headers))
        assert (response.status_code, response.get_json()["error"]["code"]) == (401, "unauthorized")
        assert response.headers["WWW-Authenticate"] == 'Bearer realm="bank-statement-analysis-api"'


@pytest.mark.parametrize("header", [f"bearer {TOKEN}", f"BEARER  {TOKEN}", f"Bearer\t{TOKEN}"])
def test_the_token_scheme_is_read_in_any_case_and_spacing(api, header):
    response = validated(api.client.get(package_path(), headers={"Authorization": header}))
    assert response.get_json()["error"]["code"] == "package_not_found"


@pytest.mark.parametrize("password", [PASSWORD, None])
@pytest.mark.parametrize("route", BROWSER_ROUTES + ["/upload"])
def test_the_token_never_opens_a_browser_route(api, monkeypatch, password, route):
    if password:
        monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", password)
    path = route.format(job=_job(api))
    response = api.client.open(path, method="POST" if route == "/upload" else "GET", headers=BEARER)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Basic realm="Intern testing"'


@pytest.mark.parametrize("route", BROWSER_ROUTES)
def test_the_browser_password_still_opens_the_browser_routes(api, monkeypatch, route):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", PASSWORD)
    assert api.client.get(route.format(job=_job(api)), headers=BASIC).status_code == 200
    assert api.client.get(route.format(job=_job(api))).status_code == 401


@pytest.mark.parametrize("headers", [{}, BEARER, BASIC])
def test_healthz_stays_open(api, monkeypatch, headers):
    monkeypatch.setenv("WEBAPP_AUTH_PASSWORD", PASSWORD)
    response = api.client.get("/healthz", headers=headers)
    assert (response.status_code, response.get_json()) == (200, {"ok": True})


def test_an_unknown_api_route_is_named_only_to_a_caller_with_the_token(api):
    assert api.get("/api/v1/no-such-route", token=None).status_code == 401
    for path in ("/api/v1/no-such-route", "/api/v1", "/api/v1/packages"):
        response = api.get(path)
        assert (response.status_code, response.get_json()["error"]["code"]) == (404, "route_not_found")


@pytest.mark.parametrize("path", ["/api/v1//packages/{id}", "/api/v1/packages//{id}", "/api/v1%2F%2Fpackages/{id}"])
@pytest.mark.parametrize("method", ["GET", "PUT", "HEAD", "POST"])
def test_a_doubled_slash_is_an_unknown_route_in_the_envelope_not_a_redirect(api, method, path):
    response = api.client.open(path.format(id=uuid.uuid4()), method=method, headers=BEARER)
    assert (response.status_code, response.mimetype, response.headers["Cache-Control"]) == (
        404, "application/json", "no-store")
    if method == "HEAD":
        assert response.get_data() == b""
    else:
        assert validated(response).get_json()["error"]["code"] == "route_not_found"


@pytest.mark.parametrize("method", ["POST", "DELETE", "PATCH", "OPTIONS"])
def test_a_method_the_package_route_does_not_take_is_not_allowed(api, method):
    response = api.call(method, package_path())
    assert (response.status_code, response.get_json()["error"]["code"]) == (405, "method_not_allowed")
    assert response.headers["Allow"] == "GET, HEAD, PUT"


def test_a_read_only_start_serves_packages_and_refuses_submissions(api, monkeypatch):
    from webapp import app as webapp_app

    api.outcomes["march.pdf"] = analysed(_single())
    path = package_path()
    ready = api.put(path, [("march.pdf", pdf())]).get_data()
    monkeypatch.setattr(webapp_app, "STORE_STATE", webapp_app.STORE_READ_ONLY)
    assert api.get(path).get_data() == ready
    refused = api.put(package_path(), [("april.pdf", pdf())])
    assert (refused.status_code, refused.get_json()["error"]["code"]) == (503, "storage_degraded")
    assert api.get(path, token=None).status_code == 401


def test_an_unavailable_start_refuses_every_api_request(api, monkeypatch):
    from webapp import app as webapp_app

    monkeypatch.setattr(webapp_app, "STORE_STATE", webapp_app.STORE_UNAVAILABLE)
    response = api.get(package_path())
    assert (response.status_code, response.get_json()["error"]["code"]) == (503, "storage_degraded")
    assert api.get(package_path(), token="fabricated-wrong-token-0000000000000000").status_code == 401
