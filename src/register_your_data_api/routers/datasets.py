"""Implementation for /reporting-org end points"""

import fastapi
import starlette
from fastapi import Security
from fastapi.responses import JSONResponse

import register_your_data_api.authn as authn

router = fastapi.APIRouter(prefix="/api/v1/datasets")


@router.post("/")
def create_dataset(
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:dataset"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.get("/{dataset_id}")
def get_dataset_detail(
    dataset_id: str,
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:dataset"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.patch("/{dataset_id}")
def update_dataset(
    dataset_id: str,
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:dataset", "ryd:dataset:update"]
    ),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    request: starlette.requests.Request,
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:dataset:delete"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )
