"""Tests for the application's exception handlers."""

import asyncio
import json
from unittest import mock

import fastapi
import sqlalchemy.exc
from fastapi.testclient import TestClient

from register_your_data_api import exception_handlers


def test_db_operational_error_handler_logs_and_returns_service_unavailable() -> None:
    """A dropped/unavailable database connection (e.g. psycopg.errors.AdminShutdown surfacing as a
    sqlalchemy.exc.OperationalError) is a runtime condition a retry is likely to resolve, so it must
    be logged clearly, distinct from other unhandled errors, and reported to the client as a 503."""

    exc = sqlalchemy.exc.OperationalError(
        statement="SELECT 1",
        params=None,
        orig=Exception("terminating connection due to administrator command"),
    )

    request = mock.MagicMock()
    context = request.app.state.context

    response = asyncio.run(exception_handlers.db_operational_error_handler(request, exc))

    assert response.status_code == 503
    assert json.loads(bytes(response.body)) == {
        "status": "failed",
        "data": None,
        "error": {"status_code": 503, "error_msg": "Service Unavailable"},
    }

    context.app_logger.error.assert_called_once_with(f"A database connectivity error occurred: {exc}", exc_info=True)


def test_db_error_handler_logs_and_returns_internal_server_error() -> None:
    """A database error that isn't a connectivity problem (e.g. IntegrityError from bad data) will
    not be fixed by the client retrying, so it must be reported as a 500, while still being logged
    clearly as a database error rather than falling through to the generic unhandled handler."""

    exc = sqlalchemy.exc.IntegrityError(
        statement="INSERT INTO foo VALUES (1)",
        params=None,
        orig=Exception("duplicate key value violates unique constraint"),
    )

    request = mock.MagicMock()
    context = request.app.state.context

    response = asyncio.run(exception_handlers.db_error_handler(request, exc))

    assert response.status_code == 500
    assert json.loads(bytes(response.body)) == {
        "status": "failed",
        "data": None,
        "error": {"status_code": 500, "error_msg": "Internal Server Error"},
    }

    context.app_logger.error.assert_called_once_with(f"A database error occurred: {exc}", exc_info=True)


def test_handlers_registered_for_operational_error_and_dbapierror() -> None:
    """Both handlers must be registered: the specific OperationalError handler for connectivity
    errors, and the DBAPIError handler for other database errors (e.g. IntegrityError, which is a
    DBAPIError but not an OperationalError)."""

    app = mock.MagicMock()

    exception_handlers.add_exception_handlers(app)

    app.add_exception_handler.assert_any_call(
        sqlalchemy.exc.OperationalError, exception_handlers.db_operational_error_handler
    )
    app.add_exception_handler.assert_any_call(sqlalchemy.exc.DBAPIError, exception_handlers.db_error_handler)


def test_operational_error_and_dbapierror_use_different_handlers() -> None:
    """End-to-end check of FastAPI's exception dispatch (not just the handler bodies in isolation):
    since OperationalError is itself a DBAPIError subclass, registering a handler for each only
    behaves correctly if FastAPI picks the most specific match. An OperationalError must be routed
    to the 503 handler, while a sibling DBAPIError subclass (IntegrityError, not fixed by retrying)
    must fall through to the 500 handler rather than both being treated the same."""

    app = fastapi.FastAPI()
    app.state.context = mock.MagicMock()
    exception_handlers.add_exception_handlers(app)

    @app.get("/operational-error")
    def raise_operational_error() -> None:
        raise sqlalchemy.exc.OperationalError(statement="SELECT 1", params=None, orig=Exception("connection lost"))

    @app.get("/integrity-error")
    def raise_integrity_error() -> None:
        raise sqlalchemy.exc.IntegrityError(statement="INSERT INTO foo VALUES (1)", params=None, orig=Exception("x"))

    client = TestClient(app, raise_server_exceptions=False)

    assert client.get("/operational-error").status_code == 503
    assert client.get("/integrity-error").status_code == 500
