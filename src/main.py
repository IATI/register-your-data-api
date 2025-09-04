"""Register Your Data API"""

import contextlib
import sys
from typing import AsyncIterator

import fastapi
import prometheus_client
import starlette.requests
from fastapi import FastAPI, Security
from fastapi.responses import JSONResponse
from fastapi.security import SecurityScopes

import register_your_data_api.authn as authn
import register_your_data_api.exceptions
import register_your_data_api.util as util


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        context = util.Context()
        context.setup()
        prometheus_client.start_http_server(int(context.env["PROMETHEUS_PORT"]))

    except Exception as err:
        print(f"Could not initialise application - error setting up context {err}")
        sys.exit("Could not startup")

    app.state.context = context

    yield


app = FastAPI(title="Register Your Data", lifespan=lifespan)
register_your_data_api.exceptions.add_exception_handlers(app)


@app.get("/api/v1/access-check")
async def access_check(
    request: starlette.requests.Request,
    security_scopes: SecurityScopes,
    user: authn.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd"]),
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
