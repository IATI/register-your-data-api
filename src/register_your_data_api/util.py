import importlib
import importlib.metadata
import json
import logging
import os
import sys
import time
from typing import Any, Final, TextIO, Type

import dotenv
import jwt
from prometheus_client import Counter, Gauge, Info, disable_created_metrics

from register_your_data_api.client_application_details_provider import (
    ClientApplicationDetails,
    ClientApplicationDetailsProvider,
)
from register_your_data_api.email_generator import EmailGenerator
from register_your_data_api.email_sender import AzureEmailSender, EmailSender
from register_your_data_api.suitecrm_client_factory import SuiteCRMClientFactory

from .audit import EncryptedFormatter
from .auth.fga.fga_provider import FineGrainedAuthorisationProvider
from .auth.fga.fga_provider_db import FineGrainedAuthorisationProviderDb
from .auth.user_crm_uuid_provider import UserCRMUUIDProvider


class Context:
    """Holds configuration and setup for API"""

    _REQUIRED_ENV_VARS: Final[list[str]] = [
        "APP_LOG_LEVEL",
        "APP_LOG_PATH",
        "AUDIT_LOG_PATH",
        "AUDIT_LOG_PUBLIC_KEY_PATH",
        "AZURE_COMMUNICATION_SERVICE_CONNECTION_STRING",
        "CLIENT_APPLICATION_DETAILS_FILE",
        "DATA_REGISTRY_SUITECRM_API_URL",
        "DATA_REGISTRY_SUITECRM_CLIENT_ID",
        "DATA_REGISTRY_SUITECRM_CLIENT_SECRET",
        "EMAIL_ADDRESS_FOR_IATI_SUPPORT_APPROVALS",
        "EMAIL_SENDER_RYD_FROM_NAME",
        "EMAIL_SENDER_RYD_FROM_EMAIL",
        "EMAIL_TEMPLATES_DIR",
        "FGA_PROVIDER",
        "FGA_PROVIDER_CONNECTION_STRING",
        "IATI_ACCOUNT_INSTANCE_BASE_URL",
        "JWKS_URI",
        "JWT_AUDIENCE",
        "PROMETHEUS_PORT",
        "USER_CRM_UUID_CONFIG_STRING",
    ]

    LOG_LEVELS: Final[dict[str, int]] = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    _app_logger: logging.Logger
    _app_log_formatter: logging.Formatter
    _app_log_fh: TextIO
    _app_log_file_handler: logging.StreamHandler[TextIO]

    _audit_logger: logging.Logger
    _audit_log_formatter: EncryptedFormatter
    _audit_log_fh: TextIO
    _audit_log_file_handler: logging.StreamHandler[TextIO]

    _email_address_for_iati_support_approvals: str
    _email_generator: EmailGenerator
    _email_sender_ryd_from_name: str
    _email_sender_ryd_from_email: str
    _email_sender: EmailSender

    _env: dict[str, Any]

    _iati_account_instance_base_url: str

    _LICENCES: dict[str, str]

    _prom_metrics: dict[str, Counter | Info | Gauge]

    _fga_provider: FineGrainedAuthorisationProvider

    _suitecrm_api_url: str
    _suitecrm_client_id: str
    _suitecrm_client_secret: str

    _crm_uuid_provider: UserCRMUUIDProvider

    def __init__(self, logs_to_stdout: bool = False) -> None:
        self._LOGS_TO_STDOUT: Final = logs_to_stdout
        self.VERSION = importlib.metadata.version("register-your-data-api")

    def setup(self) -> None:  # noqa: C901
        try:
            disable_created_metrics()  # type: ignore
            self._setup_prom_metrics()
            if isinstance(self._prom_metrics["version"], Info):
                self._prom_metrics["version"].info({"version": self.VERSION})
        except Exception as err:
            print("Could not setup prom metrics")
            raise err

        try:
            env_fh = open(".env", "r")
            self._load_and_validate_env(env_fh)
            env_fh.close()
        except OSError as err:
            print(f"Could not load environment variables file {err}")
            raise err
        except RuntimeError as err:
            print(f"Could not load environment variables file {err}")
            raise err

        try:
            self._setup_loggers()
        except Exception as err:
            print("Could not setup loggers")
            raise err

        self._app_logger.info(f"Register Your Data {self.VERSION}")

        try:
            self._app_logger.info("Setting up client application details provider")
            self._setup_client_application_details_provider()
        except Exception as err:
            self._app_logger.fatal(f"Cannot setup client application details provider ({err})")
            raise err

        self._email_address_for_iati_support_approvals = self._env["EMAIL_ADDRESS_FOR_IATI_SUPPORT_APPROVALS"]

        self._email_sender_ryd_from_email = self._env["EMAIL_SENDER_RYD_FROM_EMAIL"]

        self._email_sender_ryd_from_name = self._env["EMAIL_SENDER_RYD_FROM_NAME"]

        self._iati_account_instance_base_url = self._env["IATI_ACCOUNT_INSTANCE_BASE_URL"]

        try:
            self._app_logger.info("Setting up email generator")
            self._email_generator = EmailGenerator(self._env["EMAIL_TEMPLATES_DIR"])
        except Exception as err:
            self._app_logger.fatal(f"Cannot setup email generator ({err})")
            raise err

        try:
            self._app_logger.info("Setting up an Azure Communications Service email sender")
            self._email_sender = AzureEmailSender(self._env["AZURE_COMMUNICATION_SERVICE_CONNECTION_STRING"])
        except Exception as err:
            self._app_logger.fatal(f"Cannot setup email sender ({err})")
            raise err

        try:
            self._app_logger.info("Setting up JWK store")
            self._setup_key_store()
        except Exception as err:
            self._app_logger.fatal(f"Cannot setup JWK key store ({err})")
            raise err

        try:
            self._app_logger.info("Setting up Fine Grained Authorisation provider")
            match self._env["FGA_PROVIDER"]:
                case "FineGrainedAuthorisationProviderPgDb":
                    self._fga_provider = FineGrainedAuthorisationProviderDb(
                        self._env["FGA_PROVIDER_CONNECTION_STRING"]
                    )
                    self._fga_provider.setup()
            if self._fga_provider is None:
                raise RuntimeError("No FineGrainedAuthorisationProvider has been configured")
        except Exception as err:
            self._app_logger.fatal(f"Cannot not setup Fine Grained Authorisation provider ({err})")
            raise err

        self._suitecrm_api_url = self._env["DATA_REGISTRY_SUITECRM_API_URL"]
        self._suitecrm_client_id = self._env["DATA_REGISTRY_SUITECRM_CLIENT_ID"]
        self._suitecrm_client_secret = self._env["DATA_REGISTRY_SUITECRM_CLIENT_SECRET"]

        self._suitecrm_client_factory = SuiteCRMClientFactory(
            self._app_logger, self._suitecrm_api_url, self._suitecrm_client_id, self._suitecrm_client_secret
        )

        # self._crm_uuid_provider = UserCRMUUIDProviderAsgardeo(self._env["USER_CRM_UUID_CONFIG_STRING"])

        try:
            self._app_logger.info("Loading licences")
            fh = open("licences.json", "r")
            self.LICENCES = json.load(fh)
        except Exception as err:
            self._app_logger.fatal(f"Cannot not load licences ({err})")
            raise err

    def prom_counter_metric_inc(self, metric_name: str, failure_mode_label: str | None = None) -> None:
        metric = self._prom_metrics[metric_name]
        if isinstance(metric, Counter):
            if failure_mode_label is None:
                metric.inc()
            else:
                metric.labels(failure_mode=failure_mode_label).inc()

    def __del__(self) -> None:
        try:
            self._app_log_fh.close()
        except AttributeError:
            pass

    def _setup_client_application_details_provider(self) -> None:
        self._client_app_details = ClientApplicationDetailsProvider(
            self._env["CLIENT_APPLICATION_DETAILS_FILE"], self._app_logger, self._audit_logger
        )

    def _setup_prom_metrics(self) -> None:
        """Add all the prometheus metrics"""

        # The first metric is setup manually so that we don't have to start with
        # an empty dictionary for typing purposes.
        self._prom_metrics = {"version": Info("rydapi_version", "Register Your Data API application version")}

        self._add_prom_metric(
            "requests_auth_failed_http_header_total",
            Counter,
            "Number of requests received that are missing an authorisation HTTP header",
            ["failure_mode"],
        )
        self._prom_metrics["requests_auth_failed_http_header_total"].labels(failure_mode="missing_auth")
        self._prom_metrics["requests_auth_failed_http_header_total"].labels(failure_mode="malformed_auth")

        self._add_prom_metric(
            "requests_auth_failed_invalid_jwt_total",
            Counter,
            "Number of requests received that had an invalid JWT for some reason",
            ["failure_mode"],
        )
        self._prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="unknown_signing_key")
        self._prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="invalid_signature")
        self._prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="invalid_audience")
        self._prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="expired_signature")
        self._prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="jwt_decode_error")
        self._prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="missing_data")

        self._add_prom_metric(
            "requests_access_control_failed_total",
            Counter,
            "Number of requests received that had a valid JWT but were missing required scope(s)",
        )
        self._add_prom_metric(
            "requests_auth_validated_jwt_total", Counter, "Number of requests received that had validated JWT"
        )

    def _add_prom_metric(
        self,
        name: str,
        cls: Type[Counter] | Type[Info] | Type[Gauge] | Type[Info],
        desc: str,
        labels: list[str] = [],
    ) -> None:
        """Adds a metric to the prometheus registry, prefixing the name with the application name

        Parameters
        ----------
        name : str
            Name for the metric.
        cls : Type[Counter] | Type[Info] | Type[Gauge] | Type[Info]
            The type of metric to create.
        desc : str
            Description of the metric.
        labels : list[str] | None
            List of labels to add to this metric.
        """
        self._prom_metrics[name] = cls(f"rydapi_{name}", desc, labelnames=labels)

    def _load_and_validate_env(self, file_handle: TextIO) -> None:
        """Load .env configuration variables, augment with defaults and validate

        Parameters
        ----------
        file_handle : IO[AnyStr]
            Stream object to load environment variables from.
        """
        print("Loading environment variables")
        self._env = {**dotenv.dotenv_values(stream=file_handle), **os.environ}

        for key in self._REQUIRED_ENV_VARS:
            if key not in self._env:
                print(f"Environment variables missing {key} variable")
                raise RuntimeError(f"Environment variables missing {key} variable")

    def _setup_loggers(self) -> None:
        print("Setting up application logger")
        self._app_logger = logging.getLogger("ryd-api")
        self._app_logger.setLevel(self.LOG_LEVELS[self._env["APP_LOG_LEVEL"]])
        self._app_log_formatter = logging.Formatter(fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self._app_log_formatter.default_time_format = "%Y-%m-%dT%H:%M:%S"
        self._app_log_formatter.default_msec_format = "%s,%03dZ"
        self._app_log_formatter.converter = time.gmtime
        if not self._LOGS_TO_STDOUT:
            self._app_log_fh = open(self._env["APP_LOG_PATH"], "a")
            self._app_log_file_handler = logging.StreamHandler(self._app_log_fh)
        else:
            self._app_log_file_handler = logging.StreamHandler(sys.stdout)
        self._app_log_file_handler.setFormatter(self._app_log_formatter)
        self._app_logger.addHandler(self._app_log_file_handler)

        print("Setting up audit logger")
        self._audit_logger = logging.getLogger("ryd-api-audit")
        self._audit_logger.setLevel(logging.INFO)
        fh = open(self._env["AUDIT_LOG_PUBLIC_KEY_PATH"], "rb")
        self._audit_log_formatter = EncryptedFormatter(fh, fmt="%(asctime)s - %(levelname)s - %(message)s")
        fh.close()
        self._audit_log_formatter.default_time_format = "%Y-%m-%dT%H:%M:%S"
        self._audit_log_formatter.default_msec_format = "%s,%03dZ"
        self._audit_log_formatter.converter = time.gmtime
        if not self._LOGS_TO_STDOUT:
            self._audit_log_fh = open(self._env["AUDIT_LOG_PATH"], "a")
            self._audit_log_file_handler = logging.StreamHandler(self._audit_log_fh)
        else:
            self._audit_log_file_handler = logging.StreamHandler(sys.stdout)
        self._audit_log_file_handler.setFormatter(self._audit_log_formatter)
        self._audit_logger.addHandler(self._audit_log_file_handler)

    def _setup_key_store(self) -> None:
        self._key_store = jwt.jwks_client.PyJWKClient(self._env["JWKS_URI"])

    @property
    def app_logger(self) -> logging.Logger:
        """Get method for the app-level logger.

        Returns
        -------
        logging.Logger
        """
        return self._app_logger

    @property
    def audit_logger(self) -> logging.Logger:
        """Get method for the audit logger.

        Returns
        -------
        logging.Logger
        """
        return self._audit_logger

    @property
    def email_address_for_iati_support_approvals(self) -> str:
        """Get method for the IATI Support email address to which Secretariat approvals will be sent

        Returns
        -------
        str
        """
        return self._email_address_for_iati_support_approvals

    @property
    def email_generator(self) -> EmailGenerator:
        """Get method to retrieve the email generator.

        Returns
        -------
        EmailGenerator
        """
        return self._email_generator

    @property
    def email_sender(self) -> EmailSender:
        """Get method to retrieve the email sender.

        Returns
        -------
        EmailSender
        """
        return self._email_sender

    @property
    def email_sender_ryd_from_email(self) -> str:
        """Get method for the IATI email address from which to send notification emails

        Returns
        -------
        str
        """
        return self._email_sender_ryd_from_email

    @property
    def email_sender_ryd_from_name(self) -> str:
        """Get method for the IATI name from which to send notification emails

        Returns
        -------
        str
        """
        return self._email_sender_ryd_from_name

    @property
    def env(self) -> dict[str, str]:
        """Get method to retrieve the environment variables.

        Returns
        -------
        dict[str, str]
        """
        return self._env

    @property
    def iati_account_instance_base_url(self) -> str:
        """Get method for the IATI Account instance base URL

        Returns
        -------
        str
        """
        return self._iati_account_instance_base_url

    @property
    def key_store(self) -> jwt.jwks_client.PyJWKClient:
        """Get method to access the JWT keystore.

        Returns
        -------
        jwt.jwks_client.PyJWKClient
        """
        return self._key_store

    @property
    def prom_metrics(self) -> dict[str, Counter | Info | Gauge]:
        """Get method to access prom metrics.

        Returns
        -------
        dict[str, Counter | Info | Gauge]
        """
        return self._prom_metrics

    @property
    def fine_grained_auth_provider(self) -> FineGrainedAuthorisationProvider:
        return self._fga_provider

    @property
    def suitecrm_api_url(self) -> str:
        return self._suitecrm_api_url

    @property
    def suitecrm_client_id(self) -> str:
        return self._suitecrm_client_id

    @property
    def suitecrm_client_secret(self) -> str:
        return self._suitecrm_client_secret

    @property
    def suitecrm_client_factory(self) -> SuiteCRMClientFactory:
        return self._suitecrm_client_factory

    def get_client_application_details(self, client_id: str) -> ClientApplicationDetails:
        """Retrieves details about the client application given its client ID."""

        return self._client_app_details.get_client_application_details(client_id)
