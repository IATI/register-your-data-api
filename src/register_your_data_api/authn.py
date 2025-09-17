from typing import Any

import fastapi
import jwt
import pydantic
import starlette.requests
from fastapi import Depends
from fastapi.security import SecurityScopes

from .util import Context  # noqa: F401


async def validate_auth_header(request: starlette.requests.Request) -> str:
    """Validates the authorisation header and returns the bearer token

    Parameters
    ----------
    request : starlette.requests.Request
        Request to validate.

    Returns
    -------
    str
        Bearer token.

    Raises
    ------
    fastapi.HTTPException
        If the request was not authorised.
    """

    context = request.app.state.context  # type: Context

    authorisation = request.headers.get("authorization")
    scheme, param = fastapi.security.utils.get_authorization_scheme_param(authorisation)

    if not authorisation:
        context.prom_counter_metric_inc("requests_auth_failed_http_header_total", "missing_auth")
        context.audit_logger.warning(
            "Received request with missing authorisation HTTP header.  "
            f"METHOD={request.method} URL={request.url} CLIENT={request.client}"
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail="No authorisation information provided.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    if scheme.lower() != "bearer":
        context.prom_counter_metric_inc("requests_auth_failed_http_header_total", "malformed_auth")
        context.audit_logger.fatal(
            f"Received request with malformed authorisation HTTP header.  SCHEME={scheme} "
            f"PARAM={param}.  METHOD={request.method} URL={request.url} CLIENT={request.client}"
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect authorisation information provided.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    return param


async def validate_and_decode_token(  # noqa: C901
    request: starlette.requests.Request, param: str = Depends(validate_auth_header)
) -> dict[str, Any]:
    """Validate and decode an access token

    Parameters
    ----------
    request : starlette.requests.Request
        Request that the token was provided in
    param : str, optional
        Access token, by default Depends(validate_auth_header)

    Returns
    -------
    dict[str, Any]
        Decoded access token

    Raises
    ------
    fastapi.HTTPException
        If the request was badly formatted (400), or the authorisation
        is not complete (401, 403), or we could not reach the key store
        and/or the key was not found (500).
    """
    context = request.app.state.context  # type: Context

    key = None

    try:
        # Get the key ID used to sign the header and try to get the public key.
        key = context.key_store.get_signing_key_from_jwt(param)
    except jwt.PyJWKClientError as err:
        context.prom_counter_metric_inc("requests_auth_failed_invalid_jwt_total", "unknown_signing_key")
        jwt_header = jwt.get_unverified_header(param)
        if "kid" in jwt_header:
            start_of_error_message = f"Key with key_id={jwt_header['kid']} was not found in JWKS."
        else:
            start_of_error_message = "The JWT header contained no 'kid' element."
        context.audit_logger.critical(
            f"{start_of_error_message} Details: {err}. "
            f"METHOD={request.method} URL={request.url} CLIENT={request.client}"
        )
        print(
            f"{start_of_error_message} Details: {err}. "
            f"METHOD={request.method} URL={request.url} CLIENT={request.client}"
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    try:
        decoded_token: dict[str, Any] = jwt.decode(param, key, audience=context.env["JWT_AUDIENCE"])
    except jwt.exceptions.InvalidSignatureError as err:
        context.prom_counter_metric_inc("requests_auth_failed_invalid_jwt_total", "invalid_signature")
        context.audit_logger.critical(
            f"JWT had invalid signature with error {err}.  METHOD={request.method} "
            f"URL={request.url} CLIENT={request.client}"
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )
    except jwt.exceptions.InvalidAudienceError as err:
        context.prom_counter_metric_inc("requests_auth_failed_invalid_jwt_total", "invalid_audience")
        context.audit_logger.critical(
            f"JWT had invalid audience with error {err}.  METHOD={request.method} "
            f"URL={request.url} CLIENT={request.client}"
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )
    except jwt.exceptions.ExpiredSignatureError as err:
        context.prom_counter_metric_inc("requests_auth_failed_invalid_jwt_total", "expired_signature")
        context.audit_logger.critical(
            f"JWT had expired signature with error {err}.  METHOD={request.method} "
            f"URL={request.url} CLIENT={request.client}"
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
            detail="There is a problem with your credentials.  Try logging out and logging back "
            "in again, or try again later.  If this persists please report error to the "
            "provider of the tool you are using to access the IATI Registry.",
        )

    REQUIRED_CLAIMS = set(["sub", "roles", "scope", "aud"])
    if len(REQUIRED_CLAIMS.difference(decoded_token)) > 0:
        context.prom_counter_metric_inc("requests_auth_failed_invalid_jwt_total", "missing_data")
        context.audit_logger.critical(
            f"JWT is malformed and is missing the {REQUIRED_CLAIMS.difference(decoded_token)} claim(s).  "
            f"METHOD={request.method} CLIENT={request.client}"
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    context.prom_counter_metric_inc("requests_auth_validated_jwt_total")
    context.audit_logger.info(
        f"JWT validated.  SUB={decoded_token["sub"]} AUDIENCE={decoded_token["aud"]} "
        f"ROLES={decoded_token["roles"]} SCOPE={decoded_token["scope"]} "
        f"METHOD={request.method} CLIENT={request.client}"
    )
    return decoded_token


class UserAndCredentials(pydantic.BaseModel):
    """Class to contain user information and credentials obtained from the access token, CRM and identity service"""

    sub: str  # User ID in the identity service.
    user_id_crm: str | None  # ID of Person in the CRM.
    roles: str  # Roles that the user has (from the identity service).
    scopes: str  # Scopes that the access token has (from the identity service).
    audience: str  # Audience from the access token (from the identity service).


async def parse_decoded_token(
    security_scopes: SecurityScopes, token: dict[str, str] = Depends(validate_and_decode_token)
) -> UserAndCredentials:
    """Dependency to parse a decoded token, check for scopes, and construct a user object

    Parameters
    ----------
    security_scopes : SecurityScopes
        Scopes required in this dependency chain.
    token : dict[str, str], optional
        Decoded access token.

    Returns
    -------
    UserAndCredentials
        User object containing user details and credentials.

    Raises
    ------
    fastapi.HTTPException
        If scopes are missing.
    """

    # Check the access token has all the required scopes.
    for req_scope in security_scopes.scopes:
        if req_scope not in token["scopes"]:
            # TODO: Need to add prom metric increment for missing scope.
            # TODO: Need to add audit log entry for missing scope.
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_403_FORBIDDEN,
                detail="There is a problem with your credentials.  If this persists please report "
                "error to the provider of the tool you are using to access the IATI Registry.",
            )

    # Make user object and return.
    user = UserAndCredentials(
        sub=token["sub"], scopes=token["scope"], roles=token["roles"], audience=token["aud"], user_id_crm=None
    )

    return user
