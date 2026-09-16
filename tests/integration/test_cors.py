"""Tests for the CORS support that lets browser based clients call the API.

CORS is enforced by the browser, not by the API.  These tests therefore check which
Access-Control-* headers come back, rather than whether a request succeeds: an origin we
do not allow is still served as normal, it just comes back without the headers the browser
needs in order to hand the response to the calling script.
"""

import importlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from register_your_data_api.cors import CORS_ALLOWED_ORIGINS_FILE, add_cors_middleware

from ..helpers.mocking import MockedAppAndContext

ALLOWED_ORIGIN = "https://client.example.org"

DISALLOWED_ORIGIN = "https://other.example.com"

TOOLS_ENDPOINT = "/api/v1/tools"


def preflight_headers(origin: str, method: str = "GET", request_headers: str = "authorization") -> dict[str, str]:
    """Build the headers a browser sends when it preflights a cross-origin request."""

    return {
        "Origin": origin,
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": request_headers,
    }


def test_preflight_succeeds_without_credentials() -> None:
    """A browser preflight carries no Authorization header, so it must not be made to authenticate."""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    with TestClient(fastAPIapp) as client:
        response = client.options(TOOLS_ENDPOINT, headers=preflight_headers(ALLOWED_ORIGIN))

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
        allowed_methods = {method.strip() for method in response.headers["access-control-allow-methods"].split(",")}
        assert allowed_methods == {"GET", "POST", "PATCH", "PUT", "DELETE"}
        assert "Authorization" in response.headers["access-control-allow-headers"]
        assert "Content-Type" in response.headers["access-control-allow-headers"]
        assert "access-control-allow-credentials" not in response.headers


def test_authenticated_request_from_an_allowed_origin() -> None:
    """A browser client sends a Bearer token on every call, and must be able to read the response."""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    with TestClient(fastAPIapp) as client:
        response = client.get(
            TOOLS_ENDPOINT,
            headers={"Origin": ALLOWED_ORIGIN, **appAndContext.get_valid_authorization_header(0)},
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
        assert "Origin" in response.headers["vary"]
        assert "data" in response.json()


def test_preflight_from_a_disallowed_origin_is_refused() -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    with TestClient(fastAPIapp) as client:
        response = client.options(TOOLS_ENDPOINT, headers=preflight_headers(DISALLOWED_ORIGIN))

        assert "access-control-allow-origin" not in response.headers


def test_request_from_a_disallowed_origin_is_still_served() -> None:
    """CORS is not server side access control: the response is produced, the browser blocks it."""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    with TestClient(fastAPIapp) as client:
        response = client.get(
            TOOLS_ENDPOINT,
            headers={"Origin": DISALLOWED_ORIGIN, **appAndContext.get_valid_authorization_header(0)},
        )

        assert response.status_code == 200
        assert "data" in response.json()
        assert "access-control-allow-origin" not in response.headers


def test_request_without_an_origin_is_unaffected() -> None:
    """Server to server clients send no Origin header and must see no change at all."""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    with TestClient(fastAPIapp) as client:
        response = client.get(TOOLS_ENDPOINT, headers=appAndContext.get_valid_authorization_header(0))

        assert response.status_code == 200
        assert "data" in response.json()
        assert "access-control-allow-origin" not in response.headers
        assert "vary" not in response.headers


def test_unauthenticated_request_carries_cors_headers() -> None:
    """A browser client needs to be able to read a 401 in order to handle an expired token."""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    with TestClient(fastAPIapp) as client:
        response = client.get(TOOLS_ENDPOINT, headers={"Origin": ALLOWED_ORIGIN})

        assert response.status_code == 401
        assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_error_response_carries_cors_headers() -> None:
    """Handled errors travel through ExceptionMiddleware, which sits inside CORSMiddleware.

    Note that a genuinely unhandled exception would NOT carry these headers: that 500 is
    produced by ServerErrorMiddleware, which Starlette places outside CORSMiddleware.
    """

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    # get_valid_authorization_header(6) gets Person Seven, a failure case: see mocking.py.
    with TestClient(fastAPIapp) as client:
        response = client.get(
            TOOLS_ENDPOINT,
            headers={"Origin": ALLOWED_ORIGIN, **appAndContext.get_valid_authorization_header(6)},
        )

        assert response.status_code == 500
        assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "PUT", "DELETE"])
def test_preflight_succeeds_for_every_method_the_api_serves(method: str) -> None:
    """These are the five verbs the routers actually serve, so a preflight for any of them
    has to succeed or that part of the API is unreachable from a browser.
    """

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    with TestClient(fastAPIapp) as client:
        response = client.options(TOOLS_ENDPOINT, headers=preflight_headers(ALLOWED_ORIGIN, method=method))

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_preflight_for_a_method_that_is_not_allowed() -> None:
    """The allowlist is a real allowlist: a verb outside it is still refused.

    HEAD is the useful case to pin.  None of the API's own endpoints serve it, because
    FastAPI - unlike bare Starlette, which adds HEAD alongside GET - does not do so for an
    APIRoute, so HEAD is correctly absent from ALLOWED_METHODS.  FastAPI's own /docs,
    /redoc and /openapi.json routes are plain Starlette Routes and do answer HEAD, but
    they are documentation pages rather than endpoints a browser client calls, so they are
    not a reason to widen the list.
    """

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    with TestClient(fastAPIapp) as client:
        response = client.options(TOOLS_ENDPOINT, headers=preflight_headers(ALLOWED_ORIGIN, method="HEAD"))

        # A preflight only succeeds on a 2xx, so a refusal status is what makes the browser
        # block the request.  The exact code and body are Starlette's choice, so assert on
        # the refusal and on the verb being unadvertised rather than on its wording.
        assert not response.is_success
        assert "HEAD" not in response.headers["access-control-allow-methods"]


def test_preflight_for_a_header_that_is_not_allowed() -> None:
    """A request header the API does not permit is refused, the same way a verb is."""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[ALLOWED_ORIGIN])

    with TestClient(fastAPIapp) as client:
        response = client.options(
            TOOLS_ENDPOINT, headers=preflight_headers(ALLOWED_ORIGIN, request_headers="X-Custom-Thing")
        )

        assert not response.is_success
        assert "x-custom-thing" not in response.headers["access-control-allow-headers"].lower()


def test_app_without_cors_configured_emits_no_cors_headers() -> None:
    """An API deployed without CORS_ALLOWED_ORIGINS_FILE set behaves exactly as it did before.

    The empty list is what production actually builds when the variable is unset, so that
    is what this test passes - not None, which would exercise a configuration the deployed
    application never has.
    """

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app(cors_allowed_origins=[])

    with TestClient(fastAPIapp) as client:
        response = client.get(
            TOOLS_ENDPOINT,
            headers={"Origin": ALLOWED_ORIGIN, **appAndContext.get_valid_authorization_header(0)},
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

        # No CORS middleware means preflights are not intercepted, so OPTIONS still falls
        # through to the router's 405 exactly as it did before this feature existed.
        preflight = client.options(TOOLS_ENDPOINT, headers=preflight_headers(ALLOWED_ORIGIN))

        assert preflight.status_code == 405


def test_cors_middleware_is_registered_only_when_origins_are_configured() -> None:
    """The empty case must register nothing, or an opted-out deployment still gets CORS."""

    configured = FastAPI()
    add_cors_middleware(configured, [ALLOWED_ORIGIN])

    unconfigured = FastAPI()
    add_cors_middleware(unconfigured, [])

    configured_classes: list[object] = [middleware.cls for middleware in configured.user_middleware]
    unconfigured_classes: list[object] = [middleware.cls for middleware in unconfigured.user_middleware]

    assert CORSMiddleware in configured_classes
    assert unconfigured_classes == []


def test_the_application_module_wires_cors_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main.py must actually call add_cors_middleware, not merely be able to.

    main does its CORS setup at import, so by now it has already been imported - via
    tests/helpers/mocking.py - under whatever the ambient .env says, which on a developer
    machine or in CI is usually no origins at all.  Reloading it with an origins file
    configured is what lets the real wiring run against a real configuration. It is reloaded
    again afterwards because main.app is module global and would otherwise leak into later tests.
    """

    origins_file = tmp_path / "cors-allowed-origins.json"
    origins_file.write_text(json.dumps([ALLOWED_ORIGIN]))
    monkeypatch.setenv(CORS_ALLOWED_ORIGINS_FILE, str(origins_file))

    import main

    try:
        reloaded = importlib.reload(main)

        middleware_classes: list[object] = [middleware.cls for middleware in reloaded.app.user_middleware]

        assert CORSMiddleware in middleware_classes
    finally:
        monkeypatch.delenv(CORS_ALLOWED_ORIGINS_FILE, raising=False)
        importlib.reload(main)
