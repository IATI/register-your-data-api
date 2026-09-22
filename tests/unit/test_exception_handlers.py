"""Tests for the application's exception handlers."""

import asyncio
import json
from unittest import mock

import sqlalchemy.exc

from register_your_data_api import exception_handlers


def test_db_error_handler_logs_and_returns_service_unavailable() -> None:
    """A dropped/unavailable database connection (e.g. psycopg.errors.AdminShutdown surfacing as a
    sqlalchemy.exc.OperationalError) must be logged clearly, distinct from other unhandled errors,
    and reported to the client as a 503."""

    exc = sqlalchemy.exc.OperationalError(
        statement="SELECT 1",
        params=None,
        orig=Exception("terminating connection due to administrator command"),
    )

    request = mock.MagicMock()
    context = request.app.state.context

    response = asyncio.run(exception_handlers.db_error_handler(request, exc))

    assert response.status_code == 503
    assert json.loads(bytes(response.body)) == {
        "status": "failed",
        "data": None,
        "error": {"status_code": 503, "error_msg": "Service Unavailable"},
    }

    context.app_logger.error.assert_called_once_with(f"A database error occurred: {exc}", exc_info=True)


def test_db_error_handler_registered_for_dbapierror() -> None:
    """The handler must be registered against sqlalchemy.exc.DBAPIError (the common base for
    OperationalError and other driver-level errors), not just the specific OperationalError
    subclass, so connection failures of any flavour are handled consistently."""

    app = mock.MagicMock()

    exception_handlers.add_exception_handlers(app)

    app.add_exception_handler.assert_any_call(sqlalchemy.exc.DBAPIError, exception_handlers.db_error_handler)
