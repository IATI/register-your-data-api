import io
import logging
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import register_your_data_api.util as util


class MockKeyStore:
    """Class that mocks the functionality of the jwt.PyJWTClient key store

    This doesn't use unittest.Mock because we need to preserve functionality.

    Note I've explicitly ignored some type errors here, particularly around the typing
    of the dicts for this mock key store.
    """

    def __init__(self) -> None:
        self._keys = {}  # type: ignore

    def add_key(self, kid: str, alg: str, key: bytes) -> None:
        """Add a key to the key store.

        Parameters
        ----------
        kid : str
            Id of the key to add.
        alg : str
            Algorithm that the key uses.
        key : bytes
            The key itself.
        """
        self._keys[kid] = {"key": key, "alg": alg}

    def get_signing_key_from_jwt(self, token: str) -> str:
        """Get the signing key id from a JWT by examining the unverified header

        Parameters
        ----------
        token : str
            Access token.

        Returns
        -------
        str
            Key id.
        """
        unverified_header = jwt.get_unverified_header(token)
        return unverified_header.get("kid", None)  # type: ignore

    def get_signing_key(self, kid: str) -> dict:  # type: ignore
        """Get the signing key for a given key id.

        Parameters
        ----------
        kid : str
            The key id to fetch.

        Returns
        -------
        dict[str, bytes | str]
            Key dictionary, containig the key itself, and the algorithm.

        Raises
        ------
        jwt.PyJWKClientError
            If the key is not found in this key store.
        """
        if kid not in self._keys:
            raise jwt.PyJWKClientError("Key not found")
        return self._keys[kid]  # type: ignore


def make_context() -> util.Context:
    """Makes a mock context object for use in testing

    All required environment variables are defined in code but only
    a few are set (APP_LOG_LEVEL and AUDIT_LOG_PUBLIC_KEY_PATH) as
    these are required by the Context class to setup the loggers.
    Licences are not loaded.

    App and audit log streams are replaced with a string buffer that
    can be inspected in tests.  The key store is replaced with a mock key
    store class.

    Returns
    -------
    util.Context
    """
    context = util.Context(logs_to_stdout=True)

    # Create public key file.
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    public_key_fh = open("test-audit-log-public-key.pem", "wb")
    public_key_fh.write(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    public_key_fh.close()

    # Set all environment variables.
    context._env = {}  # notype
    for key in context._REQUIRED_ENV_VARS:
        context._env[key] = ""
    context.env["APP_LOG_LEVEL"] = "DEBUG"
    context.env["AUDIT_LOG_PUBLIC_KEY_PATH"] = "test-audit-log-public-key.pem"

    # Setup log handlers with string buffers we can examine.
    context._setup_loggers()
    context._app_logger.handlers.clear()
    context._app_log_file_handler = logging.StreamHandler(io.StringIO())
    context._app_log_file_handler.setFormatter(context._app_log_formatter)
    context._app_logger.addHandler(context._app_log_file_handler)

    context._audit_logger.handlers.clear()
    context._audit_log_file_handler = logging.StreamHandler(io.StringIO())
    context._audit_log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")  # type: ignore
    context._audit_log_file_handler.setFormatter(context._audit_log_formatter)
    context._audit_logger.addHandler(context._audit_log_file_handler)

    # Setup prom metrics.
    context._setup_prom_metrics()

    # Add mock key store.
    context._key_store = MockKeyStore()  # type: ignore

    return context


def make_claims(
    subject: str = "some_subject",
    audience: str = "some_audience",
    roles: str = "some_role",
    scopes: str = "some_scope",
    expiry_delta: int = 3600,
) -> dict[str, str | int]:
    """Make a mock claim to be encoded as an access token

    Parameters
    ----------
    audience : str, optional
        Audience for the claim, by default "rydapi"
    roles : str, optional
        Roles to add to the claim, by default ""
    scope : str, optional
        Scopes to add to the claim, by default ""
    expiry_delta : int, optional
        Time offset from the moment of invocation to add to the expiry time, by default +3600 seconds.

    Returns
    -------
    dict[str, str | int]
    """
    return {
        "sub": subject,
        "name": "some_user_name",
        "roles": roles,
        "aud": audience,
        "scope": scopes,
        "exp": int(time.time()) + expiry_delta,
    }
