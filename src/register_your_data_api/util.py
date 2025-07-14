import importlib
import json
import logging
import sys
import time
from typing import Any, BinaryIO, Final, TextIO

import dotenv
import jwt


class Context:
    """Holds configuration and setup for API"""

    _REQUIRED_ENV_VARS: Final[list[str]] = [
        "ACCESS_CHECK_ENDPOINT",
        "APP_LOG_LEVEL",
        "APP_LOG_PATH",
        "JWKS_URI",
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

    _env: dict[str, Any]
    _LICENCES: dict[str, str]

    def __init__(self, logs_to_stdout: bool = False) -> None:
        self._LOGS_TO_STDOUT: Final = logs_to_stdout
        self.VERSION = importlib.metadata.version("register-your-data-api")

    def setup(self) -> None:
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
            print(f"Could not setup loggers")
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

    def __del__(self) -> None:
        try:
            self._app_log_fh.close()
        except AttributeError:
            pass

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
            self._app_log_fh = open(self._env["APP_LOG_PATH"], "w")
            self._app_log_file_handler = logging.StreamHandler(self._app_log_fh)
        else:
            self._app_log_file_handler = logging.StreamHandler(sys.stdout)
        self._app_log_file_handler.setFormatter(self._app_log_formatter)
        self._app_logger.addHandler(self._app_log_file_handler)

    @property
    def app_logger(self) -> logging.Logger | None:
        """Get method for the app-level logger.

        Returns
        -------
        logging.Logger
        """
        return self._app_logger

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
