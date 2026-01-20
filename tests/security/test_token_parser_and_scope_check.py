"""Security test access token parsing and scope checking"""

import contextlib
from typing import AsyncIterator

import fastapi
import jwt
import pytest
import starlette.requests
from fastapi import FastAPI, Security
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import register_your_data_api.auth.authn as authn
import register_your_data_api.exception_handlers
import tests.helpers.keys as keys
import tests.helpers.logs as logs
import tests.helpers.mocking as mocking
import tests.helpers.prom as prom
from register_your_data_api.auth import models as auth_models

JWKS_KEYS = keys.generate_keys(["key"])


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    prom.reset_prom_registry()
    app.state.context = mocking.make_context()
    app.state.context.env["JWT_AUDIENCE"] = "register_your_data"
    app.state.context.key_store.add_keys_from_dict(JWKS_KEYS)

    yield


app = FastAPI(title="Register Your Data", lifespan=lifespan)
register_your_data_api.exception_handlers.add_exception_handlers(app)


@app.get("/test_require_scopes_1_and_2/")
def endpoint_test_parsed_token_req_scopes_1_and_2(
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["scope1", "scope2"]),
) -> JSONResponse:
    return JSONResponse(
        {"status": "success", "data": {"sub": user.sub, "audience": user.audience}, "error": None},
        status_code=fastapi.status.HTTP_200_OK,
    )


def test() -> None:
    with TestClient(app) as client:
        context = app.state.context
        prom_auth_validated_jwt = prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_access_control_failed = prom.MetricMonitor("rydapi_requests_access_control_failed_total")

        # Encode JWT with all the scopes.  Should return 200 and the user
        # fields should be correct.
        claims = mocking.make_access_token_payload(
            subject="some-subject", audience="register_your_data", scopes="scope1 scope2"
        )
        token = jwt.encode(claims, JWKS_KEYS["key"]["private_key"], algorithm="RS256", headers={"kid": "key"})
        response = client.get("/test_require_scopes_1_and_2", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_200_OK
        assert response_json["status"] == "success"
        assert response_json["data"]["sub"] == "some-subject"
        assert response_json["data"]["audience"] == ["register_your_data"]
        last_audit_string = logs.get_last_audit_log_string(context)
        assert "INFO" in last_audit_string
        assert "JWT validated." in last_audit_string
        assert prom_auth_validated_jwt.change() == pytest.approx(1.0)
        assert prom_access_control_failed.change() == pytest.approx(0.0)

        # Encode JWT missing scope2.  Should return 403.
        claims = mocking.make_access_token_payload(audience="register_your_data", scopes="scope1")
        token = jwt.encode(claims, JWKS_KEYS["key"]["private_key"], algorithm="RS256", headers={"kid": "key"})
        response = client.get("/test_require_scopes_1_and_2", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_403_FORBIDDEN
        assert response_json["status"] == "failed"
        last_audit_string = logs.get_last_audit_log_string(context)
        assert "CRITICAL" in last_audit_string
        assert "JWT is missing the required scope" in last_audit_string
        assert "scope2" in last_audit_string
        assert prom_auth_validated_jwt.change() == pytest.approx(1.0)
        assert prom_access_control_failed.change() == pytest.approx(1.0)

        # Encode JWT missing scope1.  Should return 403.
        claims = mocking.make_access_token_payload(audience="register_your_data", scopes="scope2")
        token = jwt.encode(claims, JWKS_KEYS["key"]["private_key"], algorithm="RS256", headers={"kid": "key"})
        response = client.get("/test_require_scopes_1_and_2", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_403_FORBIDDEN
        assert response_json["status"] == "failed"
        last_audit_string = logs.get_last_audit_log_string(context)
        assert "CRITICAL" in last_audit_string
        assert "JWT is missing the required scope" in last_audit_string
        assert "scope1" in last_audit_string
        assert prom_auth_validated_jwt.change() == pytest.approx(1.0)
        assert prom_access_control_failed.change() == pytest.approx(1.0)

        # Encode JWT missing scope1 but with additional scopes.  Should return 403.
        claims = mocking.make_access_token_payload(audience="register_your_data", scopes="scope2 unused:scope")
        token = jwt.encode(claims, JWKS_KEYS["key"]["private_key"], algorithm="RS256", headers={"kid": "key"})
        response = client.get("/test_require_scopes_1_and_2", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_403_FORBIDDEN
        assert response_json["status"] == "failed"
        last_audit_string = logs.get_last_audit_log_string(context)
        assert "CRITICAL" in last_audit_string
        assert "JWT is missing the required scope" in last_audit_string
        assert "scope1" in last_audit_string
        assert prom_auth_validated_jwt.change() == pytest.approx(1.0)
        assert prom_access_control_failed.change() == pytest.approx(1.0)
