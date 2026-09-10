"""Tests for the Sentry error monitoring setup.

Mirrors the Bulk Data Service's tests of the same name, so that both services are held
to the same standard about what may leave the machine.
"""

import logging
import os
from typing import Any
from unittest import mock

import fastapi
import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from register_your_data_api.sentry import (
    AUDIT_LOGGER_NAME,
    DEFAULT_TRACES_SAMPLE_RATE,
    UNCONFIGURED_ENVIRONMENT,
    WITHHELD,
    before_breadcrumb,
    before_send_transaction,
    setup_sentry,
)
from register_your_data_api.util import Context

BASE_CONFIG = {
    "SENTRY_DSN": "https://examplekey@o0.ingest.sentry.io/1",
    "SENTRY_ENVIRONMENT": "dev",
    "SENTRY_TRACES_SAMPLE_RATE": "0.25",
}

# Configuration variable names which hold a credential, recognised by name.  A backstop
# against a new secret variable being added to Context without being scrubbed.
SECRET_NAME_FRAGMENTS = ("SECRET", "PASSWORD", "CONNECTION_STRING", "PRIVATE_KEY", "TOKEN", "DSN")


def initialise_with(config_overrides: dict[str, str]) -> dict[str, Any]:
    """Initialises Sentry with the base config plus the given overrides, and returns the
    keyword arguments which would have been passed to the SDK."""

    with mock.patch("register_your_data_api.sentry.sentry_sdk") as mocked_sdk:
        setup_sentry(BASE_CONFIG | config_overrides)

        if not mocked_sdk.init.called:
            return {}

        return dict(mocked_sdk.init.call_args.kwargs)


def test_sentry_not_initialised_when_no_dsn_configured() -> None:

    assert initialise_with({"SENTRY_DSN": ""}) == {}


def test_setup_sentry_reports_whether_it_initialised() -> None:
    """main.py calls this at import time; it must not raise when Sentry is switched off."""

    with mock.patch("register_your_data_api.sentry.sentry_sdk"):
        assert setup_sentry(BASE_CONFIG) is True
        assert setup_sentry(BASE_CONFIG | {"SENTRY_DSN": ""}) is False


def test_sentry_initialised_with_dsn_environment_and_release() -> None:

    init_args = initialise_with({})

    assert init_args["dsn"] == BASE_CONFIG["SENTRY_DSN"]
    assert init_args["environment"] == "dev"
    assert init_args["release"] is not None
    assert init_args["release"].startswith("register-your-data-api@")


def test_sentry_environment_not_reported_as_production_when_unconfigured() -> None:

    assert initialise_with({"SENTRY_ENVIRONMENT": ""})["environment"] == UNCONFIGURED_ENVIRONMENT


def test_sentry_does_not_send_stack_frame_variables() -> None:
    """The bearer token reaches the stack in forms the scrubber cannot match by name: an
    ASGI frame's locals hold the raw scope/request objects, whose headers are a list of
    (bytes, bytes) tuples, and the token is a local variable in auth.authn in its own
    right.  Sending no local variables is the only way to withhold all of them."""

    assert initialise_with({})["include_local_variables"] is False


def test_sentry_does_not_send_personally_identifying_information() -> None:

    assert initialise_with({})["send_default_pii"] is False


def test_sentry_ignores_interrupts() -> None:

    assert KeyboardInterrupt in initialise_with({})["ignore_errors"]


def test_sentry_marks_this_application_frames_as_in_app() -> None:

    assert "register_your_data_api" in initialise_with({})["in_app_include"]


def test_sentry_uses_configured_traces_sample_rate() -> None:

    assert initialise_with({})["traces_sample_rate"] == 0.25


def test_sentry_falls_back_to_default_traces_sample_rate_when_unset() -> None:

    assert initialise_with({"SENTRY_TRACES_SAMPLE_RATE": ""})["traces_sample_rate"] == DEFAULT_TRACES_SAMPLE_RATE


def test_sentry_falls_back_to_default_traces_sample_rate_when_not_a_number() -> None:

    assert initialise_with({"SENTRY_TRACES_SAMPLE_RATE": "lots"})["traces_sample_rate"] == DEFAULT_TRACES_SAMPLE_RATE


def test_sentry_falls_back_to_default_traces_sample_rate_when_out_of_range() -> None:

    assert initialise_with({"SENTRY_TRACES_SAMPLE_RATE": "50"})["traces_sample_rate"] == DEFAULT_TRACES_SAMPLE_RATE


def test_sentry_scrubs_secrets_nested_inside_collected_values() -> None:
    """The secret values sit inside dictionaries rather than being top-level fields, so
    scrubbing has to be recursive."""

    assert initialise_with({})["event_scrubber"].recursive is True


def test_sentry_scrubs_every_configuration_variable_which_looks_like_a_secret() -> None:
    """A backstop: if a new credential is added to Context's required variables, it has to
    be withheld by name too."""

    scrubber = initialise_with({})["event_scrubber"]

    secret_vars = [
        name
        for name in Context._REQUIRED_ENV_VARS
        if any(fragment in name.upper() for fragment in SECRET_NAME_FRAGMENTS)
    ]

    assert secret_vars, "the name-fragment backstop matched nothing, so this test proves nothing"

    for name in secret_vars:
        assert name.lower() in scrubber.denylist, f"{name} looks like a secret, but Sentry would not scrub it"


def test_sentry_is_given_the_request_url_hooks() -> None:

    init_args = initialise_with({})

    assert init_args["before_breadcrumb"] is before_breadcrumb

    assert init_args["before_send_transaction"] is before_send_transaction


def test_query_strings_are_withheld_from_request_breadcrumbs() -> None:
    """Sentry records query strings with their values, and this application queries
    SuiteCRM by building record IDs into the query string."""

    crumb = before_breadcrumb(
        {
            "type": "http",
            "data": {
                "method": "GET",
                "url": "https://dev.suitecrm.example.org/Api/V8/module/Contacts",
                "http.query": "filter[id][eq]=698e0c1f-4e80-faa9-6533-68de801d1735",
                "http.fragment": "somewhere",
                "status_code": 403,
            },
        },
        {},
    )

    assert crumb is not None

    assert crumb["data"]["http.query"] == WITHHELD
    assert crumb["data"]["http.fragment"] == WITHHELD

    # what is left has to be enough to say which request failed
    assert crumb["data"]["method"] == "GET"
    assert crumb["data"]["url"] == "https://dev.suitecrm.example.org/Api/V8/module/Contacts"
    assert crumb["data"]["status_code"] == 403


def test_breadcrumbs_without_request_data_are_left_alone() -> None:

    assert before_breadcrumb({"type": "log", "message": "a message"}, {}) == {
        "type": "log",
        "message": "a message",
    }

    assert before_breadcrumb({"type": "http", "data": None}, {}) == {"type": "http", "data": None}


def test_query_strings_are_withheld_from_transaction_spans() -> None:

    # typed loosely because the SDK's Event marks every key as optional, so reading one
    # back is a type error even where the test has just supplied it
    transaction: Any = {
        "type": "transaction",
        "spans": [
            {"op": "http.client", "data": {"url": "https://example.com/x", "http.query": "filter[id][eq]=abc"}},
            {"op": "db", "data": {"db.system": "postgresql"}},
        ],
    }

    event: Any = before_send_transaction(transaction, {})

    assert event is not None

    assert event["spans"][0]["data"]["http.query"] == WITHHELD
    assert event["spans"][0]["data"]["url"] == "https://example.com/x"
    assert event["spans"][1]["data"] == {"db.system": "postgresql"}


def test_transactions_whose_spans_sentry_has_trimmed_are_left_alone() -> None:
    """Sentry replaces a value it has trimmed with a marker object, so the spans are not
    necessarily a list.  The hook must not be the thing which raises."""

    trimmed: Any = {"type": "transaction", "spans": object()}

    assert before_send_transaction(trimmed, {}) is not None


def test_the_audit_log_is_ignored_for_sentry_logs_as_well_as_for_events() -> None:
    """The SDK keeps two separate ignore lists, and `ignore_logger` covers only events and
    breadcrumbs — its own docstring says it "does not affect Sentry Logs".  Sentry Logs are
    off today, so this changes nothing now; it exists so that enabling them later cannot
    silently start sending the audit log, whose records carry the Authorization header."""

    with (
        mock.patch("register_your_data_api.sentry.sentry_sdk"),
        mock.patch("register_your_data_api.sentry.ignore_logger") as ignore_for_events,
        mock.patch("register_your_data_api.sentry.ignore_logger_for_sentry_logs") as ignore_for_logs,
    ):
        setup_sentry(BASE_CONFIG)

    ignore_for_events.assert_called_once_with(AUDIT_LOGGER_NAME)

    ignore_for_logs.assert_called_once_with(AUDIT_LOGGER_NAME)


def test_sentry_does_not_send_request_bodies() -> None:
    """`send_default_pii` does not cover request bodies: the SDK collects them regardless
    of it, bounded by `max_request_body_size`.  Because tracing is enabled the body also
    rides out on the transaction event for SUCCESSFUL requests, so without this a POST to
    a reporting-org endpoint would transmit the contact email of every organisation
    created."""

    assert initialise_with({})["max_request_body_size"] == "never"


def test_a_malformed_dsn_disables_reporting_rather_than_raising() -> None:
    """setup_sentry runs at import time in src/main.py, so a DSN which sentry_sdk rejects
    would otherwise stop the API from starting, before there is a logger to report it
    to."""

    for malformed in ("https://sentry.example.org", "not-a-url", "https://key@host"):
        assert setup_sentry(BASE_CONFIG | {"SENTRY_DSN": malformed}) is False


def test_the_test_session_cannot_report_to_a_real_sentry_project() -> None:
    """The suite imports src/main.py through tests/helpers/mocking.py, which calls
    setup_sentry() at import time, and a developer's .env holds a working DSN.
    tests/conftest.py empties SENTRY_DSN so that reading the environment disables Sentry;
    this fails if that line is removed."""

    assert os.environ.get("SENTRY_DSN") == "", "tests/conftest.py should have emptied SENTRY_DSN"

    assert setup_sentry() is False


class CapturingTransport(Transport):
    """Captures the envelopes the SDK would have transmitted, so that what would have left
    the machine can be inspected.  Used in place of Sentry's own HTTP transport, so
    nothing is sent and no socket is opened."""

    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[Any] = []

    def capture_envelope(self, envelope: Any) -> None:
        self.envelopes.append(envelope)

    @property
    def transmitted(self) -> str:
        """What the SDK serialised for transmission, which is what has to be free of
        credentials."""

        return "\n".join(
            item.get_bytes().decode("utf-8", "replace") for envelope in self.envelopes for item in envelope.items
        )


def initialise_sentry_with_captured_transport(
    transport: CapturingTransport, config_overrides: dict[str, str] | None = None
) -> None:
    """Runs the application's own initialisation, substituting only the transport, so that
    the options under test are the ones the application really uses."""

    real_init = sentry_sdk.init

    with mock.patch(
        "register_your_data_api.sentry.sentry_sdk.init",
        lambda **kwargs: real_init(**{**kwargs, "transport": transport}),
    ):
        setup_sentry(BASE_CONFIG | {"SENTRY_DSN": "https://examplekey@example.invalid/1"} | (config_overrides or {}))


AUDIT_CANARY = "CANARY-audit-credential-8c1d4a"  # nosec B105


def test_audit_log_records_are_not_sent_to_sentry() -> None:
    """The audit log must not be duplicated to Sentry.  Sentry turns any record of ERROR
    or above into an event, and the audit log is written at CRITICAL for authentication
    failures, where the record carries the contents of the Authorization header including
    the credential itself.  The audit log has its own encrypted destination."""

    transport = CapturingTransport()
    initialise_sentry_with_captured_transport(transport)

    try:
        # the shape of what auth.authn logs when the authorisation scheme is not bearer
        logging.getLogger(AUDIT_LOGGER_NAME).critical(
            "Received request with malformed authorisation HTTP header.  "
            f"SCHEME=Token PARAM={AUDIT_CANARY}.  METHOD=GET"
        )
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_client().close()

    assert AUDIT_CANARY not in transport.transmitted

    assert not transport.envelopes, "the audit record produced an envelope, so it was not ignored"


BODY_CANARY = "CANARY-contact-email-4b7e2f@example.org"


def test_a_request_body_is_not_transmitted_even_when_the_request_succeeds() -> None:
    """The behavioural counterpart to test_sentry_does_not_send_request_bodies.

    Tracing is enabled, so a successful request produces a transaction event, and the SDK
    attaches the parsed request body to it.  A POST to a reporting-org endpoint carries a
    contact email, so this covers the successful path as well as the failing one."""

    transport = CapturingTransport()
    # every transaction must be sampled, or this test would pass whenever the sample rate
    # in BASE_CONFIG happened to discard the one transaction it depends on
    initialise_sentry_with_captured_transport(transport, {"SENTRY_TRACES_SAMPLE_RATE": "1.0"})

    probe = fastapi.FastAPI()

    @probe.post("/organisations")
    def _create() -> dict[str, str]:
        return {"status": "created"}

    try:
        with TestClient(probe) as client:
            response = client.post("/organisations", json={"contact_email": BODY_CANARY})
            assert response.status_code == 200, "the request must succeed, or this tests the wrong path"
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_client().close()

    assert transport.envelopes, "nothing was sent, so this test would pass for the wrong reason"

    assert "transaction" in transport.transmitted, "no transaction was sent, so the body had no carrier"

    assert BODY_CANARY not in transport.transmitted


def test_application_log_errors_are_still_sent_to_sentry() -> None:
    """Ignoring the audit logger must not silence the diagnostic log, which is how
    application code reports errors without referencing the SDK."""

    transport = CapturingTransport()
    initialise_sentry_with_captured_transport(transport)

    try:
        logging.getLogger("ryd-api").error("a diagnostic error worth reporting")
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_client().close()

    assert "a diagnostic error worth reporting" in transport.transmitted


def test_the_ignored_logger_is_the_one_the_context_actually_creates() -> None:
    """AUDIT_LOGGER_NAME is duplicated from util.Context, so a rename there would silently
    start sending audit records to Sentry."""

    context = Context(logs_to_stdout=True)
    # logs_to_stdout means no log files are opened; the key path is still read, and the
    # formatter that would consume it is stood in for
    context._env = {"APP_LOG_LEVEL": "DEBUG", "AUDIT_LOG_PUBLIC_KEY_PATH": "not-read"}
    with (
        mock.patch("register_your_data_api.util.EncryptedFormatter"),
        mock.patch("builtins.open", mock.mock_open(read_data=b"")),
    ):
        context._setup_loggers()

    assert context.audit_logger.name == AUDIT_LOGGER_NAME


BEARER_TOKEN_CANARY = "CANARY-bearer-token-3f9c1e7a5b2d"  # nosec B105


def test_a_failing_request_does_not_send_the_bearer_token() -> None:
    """The regression test for the whole arrangement.  Sentry would otherwise attach the
    local variables of every stack frame, and an ASGI frame's locals hold the request
    object, whose headers are a list of (bytes, bytes) tuples that the scrubber cannot
    match by name.

    This drives the real SDK and a real Starlette request rather than stand-ins, so it
    keeps testing the real behaviour if either changes how it holds the headers."""

    transport = CapturingTransport()

    real_init = sentry_sdk.init

    with mock.patch(
        "register_your_data_api.sentry.sentry_sdk.init",
        lambda **kwargs: real_init(**kwargs, transport=transport),
    ):
        setup_sentry(BASE_CONFIG | {"SENTRY_DSN": "https://examplekey@example.invalid/1"})

    try:
        # what a request handler does: the token is a local variable, and the request
        # object holding the raw header is a local of the frames above it
        def handler_frame(authorization: str) -> None:
            scope = {"type": "http", "headers": [(b"authorization", authorization.encode())]}
            raise RuntimeError(f"failed while handling request with scope containing {len(scope)} keys")

        try:
            handler_frame(f"Bearer {BEARER_TOKEN_CANARY}")
        except Exception:
            sentry_sdk.capture_exception()

        sentry_sdk.flush()
    finally:
        sentry_sdk.get_client().close()

    assert transport.envelopes, "the SDK sent nothing, so this test would pass for the wrong reason"

    # confirms the failure which was reported is the one this test is about
    assert "RuntimeError" in transport.transmitted, "the exception was not reported, so nothing was proved"

    assert BEARER_TOKEN_CANARY not in transport.transmitted
