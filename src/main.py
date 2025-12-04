"""Register Your Data API"""

import contextlib
import sys
from typing import AsyncIterator

import prometheus_client
from fastapi import FastAPI

import register_your_data_api.exceptions
import register_your_data_api.util as util
from register_your_data_api.routers import datasets, discoverable_reporting_orgs, misc, reporting_orgs, users


@contextlib.asynccontextmanager
async def prod_lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        context = util.Context()
        context.setup()
        prometheus_client.start_http_server(int(context.env["PROMETHEUS_PORT"]))

    except Exception as err:
        print(f"Could not initialise application - error setting up context {err}")
        sys.exit("Could not startup")

    app.state.context = context

    yield


def add_routers_and_general_exception_handling(app: FastAPI) -> None:
    app.include_router(discoverable_reporting_orgs.router)
    app.include_router(reporting_orgs.router)
    app.include_router(datasets.router)
    app.include_router(users.router)
    app.include_router(misc.router)
    register_your_data_api.exceptions.add_exception_handlers(app)


app = FastAPI(title="Register Your Data", lifespan=prod_lifespan, redirect_slashes=False)

add_routers_and_general_exception_handling(app)
