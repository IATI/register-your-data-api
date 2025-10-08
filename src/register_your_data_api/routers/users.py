"""Implementation for /users end points"""

import fastapi
import starlette
from fastapi import Security
from fastapi.responses import JSONResponse

import register_your_data_api.auth.authn as authn
from register_your_data_api import auth

router = fastapi.APIRouter(prefix="/api/v1/users")


@router.post("/{user_id}/reporting-org")
def add_user_to_reporting_org(
    request: starlette.requests.Request,
    user: auth.models.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:user"]
    ),
) -> JSONResponse:
    # check token has required scopes
    # check roles
    # get user ID from the access token
    # make sure user exists in CRM and identity service
    # make sure reporting org exists
    # find user in CRM and add relationship
    # write fga token to identity service
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.put("/{user_id}/reporting-org/{org_id}")
def update_user_role_in_reporting_org(
    request: starlette.requests.Request,
    user: auth.models.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:user:update"]
    ),
) -> JSONResponse:
    # check token has required scopes
    # check roles
    # get user ID from the access token (the requester, "sub")
    # make sure user {user_id} exists in CRM and identity service
    # make sure reporting org exists
    # make sure "sub" has the permissions to set user authz for this reporting org
    # make sure user {user_id} and reporting org are related in CRM
    # make sure user {user_id} has an FGA token in the identity service
    # update token in the identity service
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.delete("/{user_id}/reporting-org/{org_id}")
def remove_user_from_reporting_org(
    request: starlette.requests.Request,
    user: auth.models.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:user:update"]
    ),
) -> JSONResponse:
    # check token has required scopes
    # check roles
    # get user ID from the access token (the requester, "sub")
    # make sure user {user_id} exists in CRM and identity service
    # make sure reporting org exists
    # make sure "sub" has the permissions to set user authz for this reporting org
    # make sure user {user_id} and reporting org are related in CRM
    # make sure user {user_id} has an FGA token in the identity service
    # update token in the identity service
    # remove relationship between user and reporting org in the CRM
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )
