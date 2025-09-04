"""Register Your Data API"""

import contextlib
import sys
from typing import AsyncIterator

import fastapi
import prometheus_client
import starlette.requests
from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import JSONResponse

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

    # Enable the access check endpoint if required (set in the
    # ACCESS_CHECK_ENDPOINT environment variable.)
    if context.env["ACCESS_CHECK_ENDPOINT"].lower() in ("true", "1"):
        app.state.check_router = APIRouter()
        context.app_logger.info("Setting up access check endpoint")
        app.state.check_router.add_api_route("/api/v1/access-check", endpoint=access_check)
        app.include_router(app.state.check_router)

    yield


app = FastAPI(title="Register Your Data", lifespan=lifespan)
register_your_data_api.exceptions.add_exception_handlers(app)


async def access_check(
    request: starlette.requests.Request, token: dict[str, str] = Depends(authn.validate_and_decode_token)
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
    token : dict, optional
        Validated and decoded access token.

    Returns
    -------
    JSONResponse
    """
    return JSONResponse(
        {"status": "success", "data": {"message": "Access token is valid"}, "error": None},
        status_code=fastapi.status.HTTP_200_OK,
    )
