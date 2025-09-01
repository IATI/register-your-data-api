"""Implementation for /users end points"""

import fastapi
import starlette
from fastapi import Security
from fastapi.responses import JSONResponse

import register_your_data_api.authn as authn

router = fastapi.APIRouter(prefix="/api/v1/users")


@router.post("/{user_id}/reporting-org")
def add_user_to_reporting_org(
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:user"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.put("/{user_id}/reporting-org/{org_id}")
def update_user_role_in_reporting_org(
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:user:update"]
    ),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.delete("/{user_id}/reporting-org/{org_id}")
def remove_user_from_reporting_org(
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:user:update"]
    ),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )
