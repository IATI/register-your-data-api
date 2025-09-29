"""Helper to generate a set of keys for encoding JWTs in tests"""

from typing import TypedDict

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KeyDict = TypedDict(
    "KeyDict",
    {
        "private_key_object": rsa.RSAPrivateKey,
        "private_key": bytes,
        "public_key_object": rsa.RSAPublicKey,
        "public_key": bytes,
    },
)


def generate_keys(key_ids: list[str]) -> dict[str, KeyDict]:
    """Generate public/private key pairs for JWT encoding/decoding in unit tests

    Parameters
    ----------
    key_ids : list[str]
        List of key id strings, one key pair will be generated per entry in this list.

    Returns
    -------
    dict[str, dict[str, KeyDict]]
        Each entry in this dictionary will contain private_key (bytes),
        private_key_object (RSAPrivateKey), public_key (bytes) and
        public_key_object (RSAPublicKey).
    """
    jwks_keys: dict[str, KeyDict] = {}

    for key in key_ids:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        public_key = private_key.public_key()
        jwks_keys[key] = {
            "private_key_object": private_key,
            "private_key": private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ),
            "public_key": public_key.public_bytes(
                encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
            ),
            "public_key_object": public_key,
        }

    return jwks_keys
