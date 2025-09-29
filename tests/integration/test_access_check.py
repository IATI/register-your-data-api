# https://fastapi.tiangolo.com/tutorial/testing/#extended-testing-file

import fastapi
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from main import app
from tests.helpers.mocking import MockKeyStore, make_claims

PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=4096)
PUBLIC_KEY = PRIVATE_KEY.public_key()
PUBLIC_KEY_PEM = PUBLIC_KEY.public_bytes(
    encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
)


def test_access_check() -> None:
    with TestClient(app) as client:
        app.state.context._key_store = MockKeyStore()
        app.state.context._key_store.add_key("key1", "RS256", PUBLIC_KEY)
        claims = make_claims(
            subject="87ee2e6e-a637-483a-beb1-4895a13602d2",
            audience="iati_register_your_data",
            scopes="ryd",
        )
        access_token = jwt.encode(claims, PRIVATE_KEY, algorithm="RS256", headers={"kid": "key1"})

        response = client.get("/api/v1/access-check", headers={"Authorization": "Bearer " + access_token})
        response_json = response.json()

        assert response.status_code == fastapi.status.HTTP_200_OK
        assert response_json["status"] == "success"
        assert response_json["error"] is None
        assert response_json["data"].get("message", "") == "Access token is valid"
