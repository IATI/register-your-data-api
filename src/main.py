"""Register Your Data API"""

import contextlib
import sys
from typing import AsyncIterator

from fastapi import FastAPI

import register_your_data_api.exceptions
import register_your_data_api.util as util


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        context = util.Context()
        context.setup()
    except Exception as err:
        print(f"Could not initialise application - error setting up context {err}")
        sys.exit("Could not startup")

    app.state.context = context
    yield


app = FastAPI(title="Register Your Data", lifespan=lifespan)
register_your_data_api.exceptions.add_exception_handlers(app)
