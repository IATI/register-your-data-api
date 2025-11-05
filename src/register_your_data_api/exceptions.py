import fastapi
import fastapi.responses
import starlette.exceptions
import starlette.requests
from fastapi.exceptions import RequestValidationError

from .util import Context  # noqa: F401


def add_exception_handlers(app: fastapi.FastAPI) -> None:
    """Add custom exception handlers to FastAPI app instance

    Parameters
    ----------
    app : fastapi.FastAPI
    """

    @app.exception_handler(starlette.exceptions.HTTPException)
    async def http_exception_handler(
        request: starlette.requests.Request, exc: starlette.exceptions.HTTPException
    ) -> fastapi.responses.JSONResponse:
        """Exception handler for catching HTTP Exceptions and returning formatted JSON response

        Parameters
        ----------
        request : starlette.requests.Request
            Request that was processing when the exception occurred.
        exc : starlette.exceptions.HTTPException
            Exception that was raised.

        Returns
        -------
        fastapi.responses.JSONResponse
            Formatted JSON response
        """
        return fastapi.responses.JSONResponse(
            {"status": "failed", "data": None, "error": {"status_code": exc.status_code, "error_msg": exc.detail}},
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: starlette.requests.Request, exc: RequestValidationError
    ) -> fastapi.responses.JSONResponse:
        msg = ""
        for validation_error in exc._errors:
            match validation_error["type"]:
                case "literal_error":
                    msg = f"Field '{validation_error["loc"][1]}' contains an invalid value: {validation_error["msg"]}."
                case "string_too_short":
                    msg = f"Field '{validation_error["loc"][1]}' cannot be null or empty."
                case "missing":
                    msg = f"There is a missing field. {validation_error["msg"]}: {validation_error["loc"][1]}"
                case "uuid_parsing":
                    msg = f"At location: {validation_error["loc"]} validation failed: {validation_error["msg"]}"
        return fastapi.responses.JSONResponse(
            {"status": "failed", "data": None, "error": {"status_code": 400, "error_msg": msg}},
            status_code=400,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: starlette.requests.Request, exc: Exception
    ) -> fastapi.responses.JSONResponse:
        """Catches all unhandled exceptions and returns a generic 500 server error with a simple error message"""

        context = request.app.state.context  # type: Context

        context.app_logger.error(f"An unhandled exception occurred: {exc}", exc_info=True)

        return fastapi.responses.JSONResponse(
            {"status": "failed", "data": None, "error": {"status_code": 500, "error_msg": "Internal Server Error"}},
            status_code=500,
        )
