"""Security test validation of Authorization HTTP header"""

import contextlib
from typing import AsyncIterator

import fastapi
import pytest
import starlette.requests
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import register_your_data_api.auth.authn as authn
import register_your_data_api.exception_handlers
import tests.helpers.logs as logs
import tests.helpers.mocking as mocking
import tests.helpers.prom as prom


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    prom.reset_prom_registry()
    app.state.context = mocking.make_context()

    yield


app = FastAPI(title="Register Your Data", lifespan=lifespan)
register_your_data_api.exception_handlers.add_exception_handlers(app)


@app.get("/test_auth_header")
def endpoint_test_auth_header(
    request: starlette.requests.Request, token: str = Depends(authn.validate_auth_header)
) -> JSONResponse:
    return JSONResponse(
        {"status": "success", "data": {"token": token}, "error": None}, status_code=fastapi.status.HTTP_200_OK
    )


def test_validate_auth_header() -> None:
    with TestClient(app) as client:

        context = app.state.context
        prom_auth_validated_jwt = prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_auth_failed_missing_auth = prom.MetricMonitor(
            "rydapi_requests_auth_failed_http_header_total", {"failure_mode": "missing_auth"}
        )
        prom_auth_failed_malformed = prom.MetricMonitor(
            "rydapi_requests_auth_failed_http_header_total", {"failure_mode": "malformed_auth"}
        )

        # Request doesn't contain an Authorization header and should return 401.
        response = client.get("/test_auth_header")

        assert response.status_code == fastapi.status.HTTP_401_UNAUTHORIZED
        assert response.json()["status"] == "failed"
        assert response.json()["data"] is None
        assert response.json()["error"]["status_code"] == fastapi.status.HTTP_401_UNAUTHORIZED
        assert "No authorisation information provided" in response.json()["error"]["error_msg"]

        last_audit_string = logs.get_last_audit_log_string(context)
        assert "Received request with missing authorisation HTTP header." in last_audit_string

        assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
        assert prom_auth_failed_missing_auth.change() == pytest.approx(1.0)
        assert prom_auth_failed_malformed.change() == pytest.approx(0.0)

        # Request contains an Authorization header with the wrong parameter and should return 401.
        response = client.get("/test_auth_header", headers={"Authorization": "Wrong 0123456789abcdef"})

        assert response.status_code == fastapi.status.HTTP_401_UNAUTHORIZED
        assert response.json()["status"] == "failed"
        assert response.json()["data"] is None
        assert response.json()["error"]["status_code"] == fastapi.status.HTTP_401_UNAUTHORIZED
        assert "Incorrect authorisation information provided" in response.json()["error"]["error_msg"]

        last_audit_string = logs.get_last_audit_log_string(context)
        assert "Received request with malformed authorisation HTTP header." in last_audit_string
        assert "SCHEME=Wrong" in last_audit_string
        assert "PARAM=0123456789abcdef" in last_audit_string

        assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
        assert prom_auth_failed_missing_auth.change() == pytest.approx(0.0)
        assert prom_auth_failed_malformed.change() == pytest.approx(1.0)

        # Request contains an Authorization header with the correct parameter and should be okay.
        response = client.get("/test_auth_header", headers={"Authorization": "Bearer 0123456789abcdef"})

        assert response.status_code == fastapi.status.HTTP_200_OK
        assert response.json()["status"] == "success"
        assert response.json()["data"]["token"] == "0123456789abcdef"
        assert response.json()["error"] is None

        assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
        assert prom_auth_failed_missing_auth.change() == pytest.approx(0.0)
        assert prom_auth_failed_malformed.change() == pytest.approx(0.0)
