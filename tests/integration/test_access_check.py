import fastapi
import jwt
import pytest
from fastapi.testclient import TestClient

import tests.helpers.keys
import tests.helpers.prom
from tests.helpers.mocking import make_access_token_payload

from ..helpers.mocking import MockedAppAndContext

JWKS_KEYS = tests.helpers.keys.generate_keys(["key"])


@pytest.mark.skip
def test_access_check() -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        fastAPIapp.state.context._key_store.add_keys_from_dict(JWKS_KEYS)

        prom_auth_validated_jwt = tests.helpers.prom.MetricMonitor("rydapi_requests_auth_validated_jwt_total")
        prom_access_control_failed = tests.helpers.prom.MetricMonitor("rydapi_requests_access_control_failed_total")

        # Test all okay.
        claims = make_access_token_payload(
            subject="87ee2e6e-a637-483a-beb1-4895a13602d2",
            audience="iati_register_your_data",
            scopes="ryd",
        )
        access_token = jwt.encode(
            claims, JWKS_KEYS["key"]["private_key_object"], algorithm="RS256", headers={"kid": "key"}
        )

        response = client.get("/api/v1/access-check", headers={"Authorization": "Bearer " + access_token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_200_OK
        assert response_json["status"] == "success"
        assert response_json["error"] is None
        assert response_json["data"].get("message", "") == "Access token is valid"
        assert prom_auth_validated_jwt.change() == pytest.approx(1.0)
        assert prom_access_control_failed.change() == pytest.approx(0.0)

        # Test missing scope.
        claims = make_access_token_payload(
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
