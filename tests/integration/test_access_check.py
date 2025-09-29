# https://fastapi.tiangolo.com/tutorial/testing/#extended-testing-file

import fastapi
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import tests.helpers.keys
import tests.helpers.prom
from main import app
from tests.helpers.mocking import MockKeyStore, make_claims

JWKS_KEYS = tests.helpers.keys.generate_keys(["key"])


@pytest.fixture(autouse=True)
def setup(request, monkeypatch, tmp_path) -> None:  # type: ignore
    monkeypatch.chdir(request.fspath.dirname)
    monkeypatch.setenv("APP_LOG_PATH", str(tmp_path / "app.log"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setenv("AUDIT_LOG_PUBLIC_KEY_PATH", str(tmp_path / "audit-log-public-key.pem"))
    audit_log_private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    audit_log_public_key = audit_log_private_key.public_key()
    fh = open(tmp_path / "audit-log-public-key.pem", "wb")
    fh.write(
        audit_log_public_key.public_bytes(
            encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )


def test_access_check() -> None:

    with TestClient(app) as client:
        app.state.context._key_store = MockKeyStore()
        app.state.context._key_store.add_keys_from_dict(JWKS_KEYS)

        prom_auth_validated_jwt = tests.helpers.prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_access_control_failed = tests.helpers.prom.MetricMonitor("rydapi_requests_access_control_failed_total")

        # Test all okay.
        claims = make_claims(
            subject="87ee2e6e-a637-483a-beb1-4895a13602d2",
            audience="iati_register_your_data",
            scopes="ryd",
        )
        access_token = jwt.encode(claims, JWKS_KEYS["key"]["private_key_object"], algorithm="RS256", headers={"kid": "key"})

        response = client.get("/api/v1/access-check", headers={"Authorization": "Bearer " + access_token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_200_OK
        assert response_json["status"] == "success"
        assert response_json["error"] is None
        assert response_json["data"].get("message", "") == "Access token is valid"
        assert prom_auth_validated_jwt.change() == pytest.approx(1.0)
        assert prom_access_control_failed.change() == pytest.approx(0.0)

        # Test missing scope.
        claims = make_claims(
            subject="87ee2e6e-a637-483a-beb1-4895a13602d2",
            audience="iati_register_your_data",
            scopes="wrong_scope",
        )
        access_token = jwt.encode(claims, JWKS_KEYS["key"]["private_key"], algorithm="RS256", headers={"kid": "key"})

        response = client.get("/api/v1/access-check", headers={"Authorization": "Bearer " + access_token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_403_FORBIDDEN
        assert response_json["status"] == "failed"
        assert response_json["error"]["status_code"] == 403
        assert "There is a problem with your credentials" in response_json["error"].get("error_msg", "")
        assert prom_auth_validated_jwt.change() == pytest.approx(1.0)
        assert prom_access_control_failed.change() == pytest.approx(1.0)
