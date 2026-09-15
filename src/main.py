"""Register Your Data API"""

import contextlib
import logging
import sys
from typing import AsyncIterator

import prometheus_client
from fastapi import FastAPI

import register_your_data_api.exception_handlers
import register_your_data_api.util as util
from register_your_data_api.routers import datasets, discoverable_reporting_orgs, misc, reporting_orgs, users
from register_your_data_api.sentry import setup_sentry


@contextlib.asynccontextmanager
async def prod_lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        context = util.Context()
        context.setup()
        prometheus_client.start_http_server(int(context.env["PROMETHEUS_PORT"]))

    except Exception:
        # Logged rather than printed so that it reaches error monitoring: a service which
        # will not start is the failure most worth being told about, and SystemExit is a
        # BaseException, so nothing downstream of this would report it.  With no handlers
        # configured — Context, and therefore the application logger, is what just failed —
        # logging still writes the message and traceback to stderr via its last-resort
        # handler.  The SDK flushes on process exit.
        logging.getLogger(__name__).exception("Could not initialise application - error setting up context")
        sys.exit("Could not startup")

    app.state.context = context

    yield


def add_routers_and_general_exception_handling(app: FastAPI) -> None:
    app.include_router(discoverable_reporting_orgs.router)
    app.include_router(reporting_orgs.router)
    app.include_router(datasets.router)
    app.include_router(users.router)
    app.include_router(misc.router)
    register_your_data_api.exception_handlers.add_exception_handlers(app)


# Sentry must be initialised before the application object below is created, so that its
# Starlette/FastAPI integrations are in place for it.  The integrations patch modules that
# are already imported, so only the object's creation has to come after this, not the
# imports.  A no-op when no DSN is configured.
setup_sentry()

app = FastAPI(title="Register Your Data", lifespan=prod_lifespan, redirect_slashes=False)

add_routers_and_general_exception_handling(app)
