"""Security test JWT decoding and validation"""

import contextlib
import itertools
from typing import AsyncIterator

import fastapi
import jwt
import pytest
import starlette.requests
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import register_your_data_api.authn as authn
import register_your_data_api.exceptions
import tests.helpers.keys
import tests.helpers.logs as logs
import tests.helpers.mocking as mocking
import tests.helpers.prom as prom

JWKS_KEYS = tests.helpers.keys.generate_keys(["key1", "key2"])


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    prom.reset_prom_registry()
    app.state.context = mocking.make_context()
    app.state.context.env["JWT_AUDIENCE"] = "some_audience"
    app.state.context.key_store.add_keys_from_dict(JWKS_KEYS)

    yield


app = FastAPI(title="Register Your Data", lifespan=lifespan)
register_your_data_api.exceptions.add_exception_handlers(app)


@app.get("/test_validate_and_decode_token")
def endpoint_test_validate_and_decode_token(
    request: starlette.requests.Request, token: str = Depends(authn.validate_and_decode_token)
) -> JSONResponse:
    return JSONResponse(
        {"status": "success", "data": {"token": token}, "error": None}, status_code=fastapi.status.HTTP_200_OK
    )


def test_okay() -> None:
    with TestClient(app) as client:
        context = app.state.context
        prom_auth_validated_jwt = prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")

        # Encode the JWT with a matching key.  Should return 200.
        claims = mocking.make_claims()
        token = jwt.encode(
            claims, JWKS_KEYS["key1"]["private_key"], algorithm="RS256", headers={"kid": "key1"}
        )
        response = client.get("/test_validate_and_decode_token", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_200_OK
        assert response_json["status"] == "success"
        assert response_json["error"] is None

        assert prom_auth_validated_jwt.change() == pytest.approx(1.0)

        last_audit_string = logs.get_last_audit_log_string(context)
        assert "JWT validated." in last_audit_string
        assert "SUB=some_subject" in last_audit_string
        assert "AUDIENCE=some_audience" in last_audit_string
        assert "SCOPE=some_scope" in last_audit_string

        assert response_json["data"]["token"]["sub"] == claims["sub"]
        assert response_json["data"]["token"]["aud"] == claims["aud"].split()  # type: ignore
        assert response_json["data"]["token"]["scope"] == claims["scope"]


def test_jwt_decode_error() -> None:
    with TestClient(app) as client:
        context = app.state.context
        prom_auth_validated_jwt = prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_auth_decode_error = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "jwt_decode_error"}
        )
        prom_auth_unknown_key = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "unknown_signing_key"}
        )
        prom_auth_invalid_sig = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "invalid_signature"}
        )

        # Encode the JWT with a valid key, correctly identified, but then modify the token
        token = jwt.encode(
            mocking.make_claims(),
            JWKS_KEYS["key1"]["private_key"],
            algorithm="RS256",
            headers={"kid": "key1"},
        )
        token = "d" + token  # this is enough to break the JWT header and so get the JWTDecodeError
        response = client.get("/test_validate_and_decode_token", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_401_UNAUTHORIZED
        assert response_json["status"] == "failed"
        assert response_json["error"]["status_code"] == 401
        assert "There is a problem with your credentials." in response_json["error"]["error_msg"]

        assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
        assert prom_auth_decode_error.change() == pytest.approx(1.0)
        assert prom_auth_unknown_key.change() == pytest.approx(0.0)
        assert prom_auth_invalid_sig.change() == pytest.approx(0.0)

        last_audit_string = logs.get_last_audit_log_string(context)
        assert "CRITICAL" in last_audit_string
        assert "JWT could not be decoded." not in last_audit_string


def test_jwt_signed_with_missing_key() -> None:
    with TestClient(app) as client:
        context = app.state.context
        prom_auth_validated_jwt = prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_auth_unknown_key = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "unknown_signing_key"}
        )
        prom_auth_invalid_sig = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "invalid_signature"}
        )

        # Encode the JWT with an invalid key id.  Should return a 500.
        token = jwt.encode(
            mocking.make_claims(),
            JWKS_KEYS["key1"]["private_key"],
            algorithm="RS256",
            headers={"kid": "key3"},
        )
        response = client.get("/test_validate_and_decode_token", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response_json["status"] == "failed"
        assert response_json["error"]["status_code"] == 500
        assert "There is a problem with your credentials." in response_json["error"]["error_msg"]

        assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
        assert prom_auth_unknown_key.change() == pytest.approx(1.0)
        assert prom_auth_invalid_sig.change() == pytest.approx(0.0)

        last_audit_string = logs.get_last_audit_log_string(context)
        assert "CRITICAL" in last_audit_string
        assert "JWT validated." not in last_audit_string
        assert "Key not found" in last_audit_string
        assert "key_id=key3" in last_audit_string


def test_jwt_signed_with_wrong_key() -> None:
    with TestClient(app) as client:
        context = app.state.context
        prom_auth_validated_jwt = prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_auth_unknown_key = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "unknown_signing_key"}
        )
        prom_auth_invalid_sig = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "invalid_signature"}
        )

        # Encode the JWT with the wrong key (using key1 but claim it's key2).  Should return a 401.
        token = jwt.encode(
            mocking.make_claims(),
            JWKS_KEYS["key1"]["private_key"],
            algorithm="RS256",
            headers={"kid": "key2"},
        )
        response = client.get("/test_validate_and_decode_token", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_401_UNAUTHORIZED
        assert response_json["status"] == "failed"
        assert response_json["error"]["status_code"] == 401
        assert "There is a problem with your credentials." in response_json["error"]["error_msg"]

        assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
        assert prom_auth_unknown_key.change() == pytest.approx(0.0)
        assert prom_auth_invalid_sig.change() == pytest.approx(1.0)

        last_audit_string = logs.get_last_audit_log_string(context)
        assert "CRITICAL" in last_audit_string
        assert "JWT validated." not in last_audit_string
        assert "JWT had invalid signature with error Signature verification failed" in last_audit_string

        # Encode the JWT with the wrong key (using key2 but claim it's key1).  Should return a 401.
        token = jwt.encode(
            mocking.make_claims(),
            JWKS_KEYS["key2"]["private_key"],
            algorithm="RS256",
            headers={"kid": "key1"},
        )
        response = client.get("/test_validate_and_decode_token", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_401_UNAUTHORIZED
        assert response_json["status"] == "failed"
        assert response_json["error"]["status_code"] == 401
        assert "There is a problem with your credentials." in response_json["error"]["error_msg"]

        assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
        assert prom_auth_unknown_key.change() == pytest.approx(0.0)
        assert prom_auth_invalid_sig.change() == pytest.approx(1.0)

        last_audit_string = logs.get_last_audit_log_string(context)
        assert "CRITICAL" in last_audit_string
        assert "JWT validated." not in last_audit_string
        assert "JWT had invalid signature with error Signature verification failed" in last_audit_string


def test_wrong_token_audience() -> None:
    with TestClient(app) as client:
        context = app.state.context
        prom_auth_validated_jwt = prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_auth_invalid_aud = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "invalid_audience"}
        )

        token = jwt.encode(
            mocking.make_claims(audience="wrong_audience"),
            JWKS_KEYS["key1"]["private_key"],
            algorithm="RS256",
            headers={"kid": "key1"},
        )
        response = client.get("/test_validate_and_decode_token", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_401_UNAUTHORIZED
        assert response_json["status"] == "failed"
        assert response_json["error"]["status_code"] == 401
        assert "There is a problem with your credentials." in response_json["error"]["error_msg"]

        assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
        assert prom_auth_invalid_aud.change() == pytest.approx(1.0)

        last_audit_string = logs.get_last_audit_log_string(context)
        assert "CRITICAL" in last_audit_string
        assert "JWT validated." not in last_audit_string
        assert "JWT had invalid audience" in last_audit_string
        assert "Audience doesn't match" in last_audit_string


def test_expired_token() -> None:
    with TestClient(app) as client:
        context = app.state.context
        prom_auth_validated_jwt = prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_auth_expired_sig = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "expired_signature"}
        )

        token = jwt.encode(
            mocking.make_claims(expiry_delta=-3600),
            JWKS_KEYS["key1"]["private_key"],
            algorithm="RS256",
            headers={"kid": "key1"},
        )
        response = client.get("/test_validate_and_decode_token", headers={"Authorization": "Bearer " + token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_401_UNAUTHORIZED
        assert response_json["status"] == "failed"
        assert response_json["error"]["status_code"] == 401
        assert "There is a problem with your credentials." in response_json["error"]["error_msg"]

        assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
        assert prom_auth_expired_sig.change() == pytest.approx(1.0)

        last_audit_string = logs.get_last_audit_log_string(context)
        assert "CRITICAL" in last_audit_string
        assert "JWT validated." not in last_audit_string
        assert "JWT had expired signature" in last_audit_string
        assert "Signature has expired" in last_audit_string


def test_missing_claims() -> None:
    with TestClient(app) as client:
        context = app.state.context
        prom_auth_validated_jwt = prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_auth_missing_data = prom.MetricMonitor(
            "rydapi_requests_auth_failed_invalid_jwt_total", {"failure_mode": "missing_data"}
        )

        # Test removing different combinations of required claims from the token.  Each time
        # we should get a 400 and a list of the missing claims in the audit log.
        REQUIRED_CLAIMS = ["sub", "scope"]
        CLAIM_COMBINATIONS_TO_REMOVE = list(itertools.combinations(REQUIRED_CLAIMS, 1)) + list(
            itertools.combinations(REQUIRED_CLAIMS, 2)
        )

        for claims_to_remove in CLAIM_COMBINATIONS_TO_REMOVE:
            claims = mocking.make_claims()
            for key in claims_to_remove:
                claims.pop(key, None)

            token = jwt.encode(
                claims, JWKS_KEYS["key1"]["private_key"], algorithm="RS256", headers={"kid": "key1"}
            )
            response = client.get("/test_validate_and_decode_token", headers={"Authorization": "Bearer " + token})
            response_json = response.json()

            assert response.status_code == fastapi.status.HTTP_400_BAD_REQUEST
            assert response_json["status"] == "failed"
            assert response_json["error"]["status_code"] == 400
            assert "There is a problem with your credentials." in response_json["error"]["error_msg"]

            assert prom_auth_validated_jwt.change() == pytest.approx(0.0)
            assert prom_auth_missing_data.change() == pytest.approx(1.0)

            last_audit_string = logs.get_last_audit_log_string(context)
            assert "CRITICAL" in last_audit_string
            assert "JWT validated." not in last_audit_string
            assert "JWT is malformed and is missing the" in last_audit_string
            for key in claims_to_remove:
                assert f"'{key}'" in last_audit_string
