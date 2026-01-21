import fastapi
import fastapi.responses
import starlette.exceptions
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from .auth.models import UserAndCredentials
from .exceptions import RYDUserException  # noqa: F401
from .util import Context  # noqa: F401


def format_log_msg(
    request: Request, user: UserAndCredentials, msg: str | None, include_client_id: bool = False
) -> str | None:
    if msg is None:
        return None
    client_prefix: str = f"client id: {user.client_id} - " if include_client_id else ""
    return client_prefix + f"user id: {user.user_id_crm} - " f"{request.method} {request.url.path} - {msg}"


async def ryd_user_exception_handler(request: Request, exc: RYDUserException) -> fastapi.responses.JSONResponse:
    """Exception handler for app exceptions raised after a user has been successfully authenticated

    Parameters
    ----------
    request : starlette.requests.Request
        Request that was processing when the exception occurred.
    exc : RYDUserException
        The exception that was raised.

    Returns
    -------
    fastapi.responses.JSONResponse
        Formatted JSON response
    """

    context: Context = request.app.state.context

    app_log_msg = format_log_msg(request, exc.user, exc.app_msg)

    audit_log_msg = format_log_msg(request, exc.user, exc.audit_msg, include_client_id=True)

    if app_log_msg is not None:
        context.app_logger.error(app_log_msg)

    if audit_log_msg is not None:
        context.audit_logger.error(audit_log_msg)

    return fastapi.responses.JSONResponse(
        {"status": "failed", "data": None, "error": {"status_code": exc.status_code, "error_msg": exc.public_msg}},
        status_code=exc.status_code,
    )


async def http_exception_handler(
    request: Request, exc: starlette.exceptions.HTTPException
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


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> fastapi.responses.JSONResponse:

    context: Context = request.app.state.context

    context.app_logger.warning(f"Validation error: {exc} for request: {request.url}")

    msg = "Data validation error: "

    msg += " ".join([f"Field '{err['loc'][-1]}': {err['msg']}." for err in exc.errors()])

    return fastapi.responses.JSONResponse(
        {"status": "failed", "data": None, "error": {"status_code": 400, "error_msg": msg}},
        status_code=400,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> fastapi.responses.JSONResponse:
    """Catches all unhandled exceptions and returns a generic 500 server error with a simple error message"""

    context = request.app.state.context  # type: Context

    context.app_logger.error(f"An unhandled exception occurred: {exc}", exc_info=True)

    return fastapi.responses.JSONResponse(
        {"status": "failed", "data": None, "error": {"status_code": 500, "error_msg": "Internal Server Error"}},
        status_code=500,
    )


def add_exception_handlers(app: fastapi.FastAPI) -> None:
    """Add custom exception handlers to FastAPI app instance

    Parameters
    ----------
    app : fastapi.FastAPI
    """

    app.add_exception_handler(RYDUserException, ryd_user_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(starlette.exceptions.HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
