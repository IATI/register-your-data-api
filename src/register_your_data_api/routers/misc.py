import fastapi
import starlette.requests
from fastapi import Security
from fastapi.responses import JSONResponse
from fastapi.security import SecurityScopes

from ..auth.authn import parse_decoded_token
from ..auth.models import UserAndCredentials

router = fastapi.APIRouter()


@router.get("/api/v1/access-check")
async def access_check(
    request: starlette.requests.Request,
    security_scopes: SecurityScopes,
    user: UserAndCredentials = Security(parse_decoded_token, scopes=["ryd"]),
) -> JSONResponse:
    """Implements an endpoint for users to check they can access the API

    If an application wants to verify the logged in user can access the API
    it could just call /api/v1/reporting-orgs and check the result, but this
    would result in a call to the CRM.  This method (enabled through an
    environment variable) provides an ability for application to verify access
    without incurring a CRM call penalty.

    Parameters
    ----------
    request : starlette.requests.Request
        Request object.
    user : authn.UserAndCredentials, optional
        User model containing user details and credentials.

    Returns
    -------
    JSONResponse
    """
    return JSONResponse(
        {"status": "success", "data": {"message": "Access token is valid"}, "error": None},
        status_code=fastapi.status.HTTP_200_OK,
    )


@router.get("/licences")
def get_licences() -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )
