"""Implementation for /reporting-orgs end points"""

import fastapi
import starlette
from fastapi import Security
from fastapi.responses import JSONResponse

import register_your_data_api.authn as authn

router = fastapi.APIRouter(prefix="/api/v1/reporting-orgs")


@router.get("/")
def get_reporting_orgs(
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org"]),
    include_meta: str = "no",
    include_actions: str = "no",
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.post("/")
def create_reporting_org(
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org", "ryd:reporting_org:create"]
    ),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.get("/{org_id}")
def get_reporting_org_detail(
    org_id: str,
    request: starlette.requests.Request,
    include_actions: str = "no",
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.patch("/{org_id}")
def update_reporting_org(
    org_id: str,
    request: starlette.requests.Request,
    include_actions: str = "no",
    user: authn.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org", "ryd:reporting_org:update"]
    ),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.delete("/{org_id}")
def delete_reporting_org(
    org_id: str,
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:delete"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.get("/{org_id}/users")
def get_reporting_org_users(
    org_id: str,
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:user"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.get("/{org_id}/datasets")
def get_reporting_org_datasets(
    org_id: str,
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:dataset"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )
