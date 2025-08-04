from typing import Any

import fastapi
import jwt
import starlette.requests
from fastapi import Depends


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

    context = request.app.state.context

    authorisation = request.headers.get("authorization")
    scheme, param = fastapi.security.utils.get_authorization_scheme_param(authorisation)

    if not authorisation:
        context.prom_metrics["requests_auth_failed_http_header_total"].labels(failure_mode="missing_auth").inc()
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
        context.prom_metrics["requests_auth_failed_http_header_total"].labels(failure_mode="malformed_auth").inc()
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
    context = request.app.state.context

    # Get the key ID used to sign the header and try to get the public key.
    key_id = context.key_store.get_signing_key_from_jwt(param)
    try:
        key = context.key_store.get_signing_key(key_id)
    except jwt.PyJWKClientError as err:
        context.prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="unknown_signing_key").inc()
        context.audit_logger.critical(
            f"Key with key_id={key_id} was not found in JWKS with error "
            f"{err}. METHOD={request.method} URL={request.url} CLIENT={request.client}"
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    try:
        decoded_token: dict[str, Any] = jwt.decode(
            param, key["key"], audience=context.env["JWT_AUDIENCE"], algorithms=key["alg"]
        )
    except jwt.exceptions.InvalidSignatureError as err:
        context.prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="invalid_signature").inc()
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
        context.prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="invalid_audience").inc()
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
        context.prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="expired_signature").inc()
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

    REQUIRED_CLAIMS = set(["sub", "roles", "scope"])
    if len(REQUIRED_CLAIMS.difference(decoded_token)) > 0:
        context.prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="missing_data").inc()
        context.audit_logger.critical(
            f"JWT is malformed and is missing the {REQUIRED_CLAIMS.difference(decoded_token)} claim(s).  "
            f"METHOD={request.method} CLIENT={request.client}"
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    context.prom_metrics["requests_auth_validated_jwt_total"].inc()
    context.audit_logger.info(
        f"JWT validated.  SUB={decoded_token["sub"]} AUDIENCE={decoded_token["aud"]} "
        f"ROLES={decoded_token["roles"]} SCOPE={decoded_token["scope"]} "
        f"METHOD={request.method} CLIENT={request.client}"
    )
    return decoded_token
