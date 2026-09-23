"""Tests for the application entry point."""

import asyncio
import logging
from unittest import mock

import pytest

import main


def test_a_failed_startup_is_logged_with_the_exception_attached() -> None:
    """A service which will not start is worth being told about. `SystemExit` is
    a `BaseException`, so nothing downstream of `sys.exit` would see it, and error
    monitoring picks up records of ERROR and above.

    The record must carry `exc_info`, because without it the event reaching Sentry would
    say only that startup failed and not why."""

    async def enter_lifespan() -> None:
        async with main.prod_lifespan(mock.MagicMock()):
            pass

    with mock.patch("register_your_data_api.util.Context", side_effect=RuntimeError("no AUDIT_LOG_PUBLIC_KEY_PATH")):
        with mock.patch.object(logging.getLogger("main"), "error") as logged:
            with pytest.raises(SystemExit):
                asyncio.run(enter_lifespan())

    # exc_info is what attaches the exception; without it the reported event would say
    # only that startup failed and not why.  Logger.exception delegates to Logger.error
    # with exc_info=True, which is why the assertion is on `error`.
    logged.assert_called_once_with("Could not initialise application - error setting up context", exc_info=True)


def test_a_failed_cors_configuration_is_logged_with_the_exception_attached() -> None:
    """The CORS allowlist is read at import, so the failure is carried into the lifespan.

    It is reported the same way as a failed context setup: an application which will not
    start because its CORS configuration is broken is exactly as worth being told about,
    and without `exc_info` the reported event would not say which origin was at fault.
    """

    cors_error = RuntimeError("CORS allowed origins file origins.json contains invalid origins")

    async def enter_lifespan() -> None:
        async with main.prod_lifespan(mock.MagicMock()):
            pass

    with mock.patch.object(main, "_cors_configuration_error", cors_error):
        with mock.patch.object(logging.getLogger("main"), "error") as logged:
            with pytest.raises(SystemExit):
                asyncio.run(enter_lifespan())

    logged.assert_called_once_with("Could not initialise application - error configuring CORS", exc_info=cors_error)
