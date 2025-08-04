import fastapi
import fastapi.responses
import starlette.exceptions
import starlette.requests


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
