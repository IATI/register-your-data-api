# https://fastapi.tiangolo.com/tutorial/testing/#extended-testing-file

import fastapi
import jwt
from fastapi.testclient import TestClient

import tests.helpers.keys
from main import app
from tests.helpers.mocking import MockKeyStore, make_claims

JWKS_KEYS = tests.helpers.keys.generate_keys(["key"])


def test_access_check() -> None:
    with TestClient(app) as client:
        app.state.context._key_store = MockKeyStore()
        app.state.context._key_store.add_keys_from_dict(JWKS_KEYS)

        claims = make_claims(
            subject="87ee2e6e-a637-483a-beb1-4895a13602d2",
            audience="iati_register_your_data",
            scopes="ryd",
        )
        access_token = jwt.encode(claims, JWKS_KEYS["key"]["private_key"], algorithm="RS256", headers={"kid": "key"})

        response = client.get("/api/v1/access-check", headers={"Authorization": "Bearer " + access_token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_200_OK
        assert response_json["status"] == "success"
        assert response_json["error"] is None
        assert response_json["data"].get("message", "") == "Access token is valid"
