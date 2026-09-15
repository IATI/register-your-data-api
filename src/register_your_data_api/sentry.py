"""Sentry error monitoring and request tracing.

Sentry has to be initialised before the FastAPI application object is created, which is
earlier than the ``Context`` (created in the application lifespan) exists.  Configuration
is therefore read straight from the environment here rather than going through
``Context``, using the same precedence that ``Context`` uses: values from the ``.env``
file in the current directory, overridden by real environment variables.

This follows the same approach as the IATI Bulk Data Service's ``src/config/sentry.py``,
so that the two services withhold credentials from Sentry in the same way.
"""

import importlib.metadata
import os
from typing import Final

import dotenv
import sentry_sdk
from sentry_sdk.integrations.logging import ignore_logger, ignore_logger_for_sentry_logs
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

# Sentry's SDK sends no traces at all unless a sample rate is set, so a default is
# supplied here rather than leaving it to the SDK
DEFAULT_TRACES_SAMPLE_RATE: Final[float] = 1.0

# The audit logger, whose records must never be sent to Sentry.  Sentry turns any log
# record of ERROR or above into an event, and the audit log is written at CRITICAL for
# authentication failures; those records carry the contents of the Authorization header,
# including the credential itself (see auth/authn.py).  The audit log has its own
# encrypted destination and must not be duplicated to a third party in plain text.
# Must match the logger name used by util.Context._setup_loggers.
AUDIT_LOGGER_NAME: Final[str] = "ryd-api-audit"

# Used when SENTRY_ENVIRONMENT is not set, in preference to the SDK's own default of
# 'production', so that an unconfigured environment can never be mistaken for the live one
UNCONFIGURED_ENVIRONMENT: Final[str] = "local-development"

# Names of this application's own secrets and sensitive fields, withheld by name in
# addition to Sentry's own default denylist.  The audit log is deliberately encrypted at
# rest, so audit content must not be shipped to a third party in plain text either.
SENSITIVE_NAMES: Final[list[str]] = [
    "access_token",
    "audit_msg",
    "AUDIT_LOG_PRIVATE_KEY_PATH",
    "AZURE_COMMUNICATION_SERVICE_CONNECTION_STRING",
    "DATA_REGISTRY_SUITECRM_CLIENT_ID",
    "DATA_REGISTRY_SUITECRM_CLIENT_SECRET",
    "FGA_PROVIDER_CONNECTION_STRING",
    "SENTRY_DSN",
    "suitecrm_audit_headers",
    "USER_CRM_UUID_CONFIG_STRING",
]


def get_environment_config() -> dict[str, str]:
    """Reads configuration with the same precedence as ``Context``: ``.env`` then os.environ."""

    env: dict[str, str] = {k: v for k, v in dotenv.dotenv_values(".env").items() if v is not None}
    env.update(os.environ)
    return env


def get_release() -> str | None:
    """Builds the Sentry release identifier from the installed package version."""

    try:
        return f"register-your-data-api@{importlib.metadata.version('register-your-data-api')}"
    except importlib.metadata.PackageNotFoundError:
        return None


def setup_sentry(config: dict[str, str] | None = None) -> bool:
    """Initialises Sentry error reporting and tracing, if a DSN has been configured.

    The Sentry SDK does nothing when it has no DSN, so local development and test runs
    need no Sentry setup at all: leaving SENTRY_DSN unset means nothing is sent anywhere.
    Error reporting must also never be the reason the API fails to start.

    Parameters
    ----------
    config : dict[str, str] | None, optional
        Configuration to use.  Read from the environment when not supplied.

    Returns
    -------
    bool
        True if Sentry was initialised, False if it was skipped for want of a DSN.
    """

    settings = get_environment_config() if config is None else config

    if not settings.get("SENTRY_DSN", "").strip():
        print("Sentry: SENTRY_DSN is not set, so error reporting is disabled")
        return False

    environment = settings.get("SENTRY_ENVIRONMENT", "").strip() or UNCONFIGURED_ENVIRONMENT

    try:
        initialise_sdk(settings["SENTRY_DSN"].strip(), environment, get_traces_sample_rate(settings))
    except Exception as err:
        # A malformed DSN makes sentry_sdk.init raise BadDsn, and this runs at import time
        # in src/main.py, before there is a logger to report it to.  Error reporting must
        # never be the reason the API fails to start, so a DSN which cannot be used
        # disables reporting rather than killing the process.
        print(f"Sentry: could not initialise error reporting, so it is disabled ({err})")
        return False

    # Keep the audit log out of Sentry entirely.  See AUDIT_LOGGER_NAME above: these
    # records are written at CRITICAL and carry credentials, and they have their own
    # encrypted destination.  The application's diagnostic log is still reported.
    #
    # The SDK keeps two separate ignore lists, and ignore_logger covers only events and
    # breadcrumbs — its own docstring says it "does not affect Sentry Logs".  Sentry Logs
    # are off (`enable_logs` defaults to False) so the second call changes nothing today;
    # it is here so that enabling them later cannot silently start sending the audit log.
    ignore_logger(AUDIT_LOGGER_NAME)
    ignore_logger_for_sentry_logs(AUDIT_LOGGER_NAME)

    print(f"Sentry: error reporting enabled for environment '{environment}'")

    return True


def initialise_sdk(dsn: str, environment: str, traces_sample_rate: float) -> None:
    """Calls sentry_sdk.init with this application's options."""

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=get_release(),
        traces_sample_rate=traces_sample_rate,
        # this API serves end users and handles their personal data, so there is nothing
        # to be gained from letting the SDK attach identifying information to events
        send_default_pii=False,
        # Request bodies are NOT sent.  send_default_pii does not cover them: the SDK
        # collects bodies "regardless of PII today, bounded by max_request_body_size"
        # (sentry_sdk data collection defaults), and because tracing is enabled the body
        # rides out on the transaction event for SUCCESSFUL requests too.  Verified: a
        # POST to a reporting-org endpoint transmitted its contact_email on success.
        max_request_body_size="never",
        # Sentry attaches the local variables of every stack frame to an event, and this
        # application's credentials reach the stack in forms which cannot all be matched
        # by name: an ASGI frame's locals hold the raw scope/request objects, whose
        # headers are a list of (bytes, bytes) tuples rather than a named field, and the
        # bearer token is itself a local variable in auth.authn and a field of
        # UserAndCredentials.  Sending no local variables is the only way to withhold all
        # of them.
        include_local_variables=False,
        # kept as well, because it scrubs the values the SDK collects by other means
        event_scrubber=EventScrubber(
            denylist=DEFAULT_DENYLIST + SENSITIVE_NAMES,
            recursive=True,
        ),
        # the server is stopped by interrupting it, which is a normal way for the process
        # to end rather than a fault worth reporting
        ignore_errors=[KeyboardInterrupt],
        # mark this application's own frames as in-app so they stand out in a traceback
        in_app_include=["register_your_data_api", "main"],
    )


def get_traces_sample_rate(config: dict[str, str]) -> float:
    """Returns the configured trace sample rate, falling back to the default if it is
    unset or unusable.  A bad value here must not stop the app from starting, nor stop
    errors from being reported."""

    configured_rate = config.get("SENTRY_TRACES_SAMPLE_RATE", "").strip()

    if not configured_rate:
        return DEFAULT_TRACES_SAMPLE_RATE

    try:
        rate = float(configured_rate)
    except ValueError:
        print(
            f"Sentry: SENTRY_TRACES_SAMPLE_RATE '{configured_rate}' is not a number: "
            f"using {DEFAULT_TRACES_SAMPLE_RATE}"
        )
        return DEFAULT_TRACES_SAMPLE_RATE

    if not 0.0 <= rate <= 1.0:
        print(
            f"Sentry: SENTRY_TRACES_SAMPLE_RATE '{configured_rate}' is not between 0 and 1: "
            f"using {DEFAULT_TRACES_SAMPLE_RATE}"
        )
        return DEFAULT_TRACES_SAMPLE_RATE

    return rate
