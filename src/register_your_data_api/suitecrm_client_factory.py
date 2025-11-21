import logging
import random
import threading
import time
import uuid

from libsuitecrm import AuthorisationFailed, SuiteCRM  # type: ignore


class SuiteCRMClientFactory:
    """A SuiteCRM client factory that creates clients using a cached access token and refreshes the token as needed"""

    def __init__(
        self,
        app_logger: logging.Logger,
        suitecrm_api_url: str,
        suitecrm_client_id: str,
        suitecrm_client_secret: str,
        suitecrm_client_secure: bool = True,
    ) -> None:
        self._app_logger = app_logger
        self._suitecrm_api_url = suitecrm_api_url
        self._suitecrm_client_id = suitecrm_client_id
        self._suitecrm_client_secret = suitecrm_client_secret
        self._suitecrm_client_secure = suitecrm_client_secure

        # config
        self._buffer_seconds = 60

        # token details
        self._expires_at = 0

        # lock for thread-safe access
        self._lock = threading.Lock()

        # A private SuiteCRM instance used to refresh the access token, which is shared as needed
        self._private_crm = SuiteCRM(
            self._suitecrm_api_url,
            self._suitecrm_client_id,
            self._suitecrm_client_secret,
            self._suitecrm_client_secure,
        )

    def get_client(self) -> SuiteCRM:
        """Gets a new SuiteCRM client using cached access token, refreshing the access token first if necessary"""

        if self._private_crm.export_access_token() is not None and time.time() < self._expires_at:
            self._app_logger.info(f"Thread {threading.get_ident()}: SuiteCRM access token ok, making new client.")
            return self._get_new_suitecrm_client()

        with self._lock:
            if self._private_crm.export_access_token() is not None and time.time() < self._expires_at:
                return self._private_crm

            self._refresh_token()

        return self._get_new_suitecrm_client()

    def _get_new_suitecrm_client(self) -> SuiteCRM:
        """Creates a new instance of the SuiteCRM client using the cached access token"""

        access_token_dict = self._private_crm.export_access_token()

        return SuiteCRM(
            self._suitecrm_api_url,
            self._suitecrm_client_id,
            self._suitecrm_client_secret,
            self._suitecrm_client_secure,
            access_token_dict,
        )

    def _refresh_token(self) -> None:
        """Fetch a token from SuiteCRM and adjust the refresh time"""

        # NOTE: The strings 'Fetching new token' and 'Refreshing token' are used in unit tests
        if self._private_crm.export_access_token() is None:
            self._app_logger.info(
                f"Thread {threading.get_ident()}: No SuiteCRM access token found. Fetching new token."
            )
        else:
            self._app_logger.info(
                f"Thread {threading.get_ident()}: SuiteCRM access token has expired. Refreshing token."
            )

        try:
            self._private_crm.fetch_access_token()
        except AuthorisationFailed as e:
            error_id = uuid.uuid4()
            self._app_logger.error(
                f"Thread {threading.get_ident()}: Failed to refresh SuiteCRM "
                f"access token: {str(e)}. Error id: {error_id}"
            )
            raise RuntimeError(f"There was a problem completing this request. Error trace id: {error_id}") from e

        jitter = random.randint(0, 30)  # nosec

        self._expires_at = (
            time.time() + self._private_crm.export_access_token().get("expires_in", 0) - self._buffer_seconds - jitter
        )
