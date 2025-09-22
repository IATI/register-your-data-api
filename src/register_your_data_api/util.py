import importlib
import importlib.metadata
import json
import logging
import sys
import time
from typing import Any, Final, TextIO, Type

import dotenv
import jwt
from prometheus_client import Counter, Gauge, Info, disable_created_metrics

from .audit import EncryptedFormatter


class Context:
    """Holds configuration and setup for API"""

    _REQUIRED_ENV_VARS: Final[list[str]] = [
        "APP_LOG_LEVEL",
        "APP_LOG_PATH",
        "AUDIT_LOG_PATH",
        "AUDIT_LOG_PUBLIC_KEY_PATH",
        "JWKS_URI",
        "PROMETHEUS_PORT",
        "JWT_AUDIENCE",
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

    _env: dict[str, Any]
    _LICENCES: dict[str, str]

    _prom_metrics: dict[str, Counter | Info | Gauge]

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
            self._app_logger.info("Setting up JWK store")
            self._key_store = jwt.jwks_client.PyJWKClient(self._env["JWKS_URI"])
        except Exception as err:
            self._app_logger.fatal(f"Cannot not setup JWK key store ({err})")
            raise err

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
        self._prom_metrics["requests_auth_failed_invalid_jwt_total"].labels(failure_mode="missing_data")

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
        self._env = dotenv.dotenv_values(stream=file_handle)
        if len(self._env.keys()) == 0:
            print("No environment variables found")
            raise RuntimeError("No environment variables found")

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
    def env(self) -> dict[str, str]:
        """Get method to retrieve the environment variables.

        Returns
        -------
        dict[str, str]
        """
        return self._env

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
