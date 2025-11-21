import time
from typing import Callable
from unittest import mock

from register_your_data_api.suitecrm_client_factory import SuiteCRMClientFactory

from ..helpers.mocking import StringContaining


def mock_token_creator_factory(suitecrm_client_factory: SuiteCRMClientFactory, expires_in: int) -> Callable[[], None]:
    def mock_fetch_token() -> None:
        suitecrm_client_factory._private_crm.export_access_token.return_value = {
            "access_token": "new-access-token",
            "expires_in": expires_in,
            "expires_at": time.time() + expires_in,
        }

    return mock_fetch_token


def test_token_created() -> None:

    access_token_cache = SuiteCRMClientFactory(
        app_logger=mock.Mock(),
        suitecrm_api_url="http://example.com",
        suitecrm_client_id="client-test-id",
        suitecrm_client_secret="client-test-secret",  # nosec B106
    )

    access_token_cache._private_crm = mock.Mock()

    access_token_cache._private_crm.export_access_token.return_value = None

    access_token_cache._private_crm.fetch_access_token.side_effect = mock_token_creator_factory(
        access_token_cache, 3600
    )

    access_token_cache.get_client()

    # check that log message reads "No token found"
    access_token_cache._app_logger.info.assert_called_with(StringContaining("Fetching new token."))  # type: ignore


def test_token_refreshed() -> None:

    access_token_cache = SuiteCRMClientFactory(
        app_logger=mock.MagicMock(),
        suitecrm_api_url="http://example.com",
        suitecrm_client_id="client-test-id",
        suitecrm_client_secret="client-test-secret",  # nosec B106
    )

    access_token_cache._private_crm = mock.MagicMock()

    access_token_cache._private_crm.export_access_token.return_value = None

    def mock_fetch_token() -> None:
        access_token_cache._private_crm.export_access_token.return_value = {
            "access_token": "new-access-token",
            "expires_in": 1,
            "expires_at": time.time() + 1,
        }

    access_token_cache._private_crm.fetch_access_token.side_effect = mock_token_creator_factory(access_token_cache, 1)

    access_token_cache.get_client()

    first_access_token = access_token_cache._private_crm.export_access_token()

    # check that log message reads "Fetching new token"
    access_token_cache._app_logger.info.assert_called_with(StringContaining("Fetching new token."))  # type: ignore

    time.sleep(2)

    access_token_cache.get_client()

    second_access_token = access_token_cache._private_crm.export_access_token()

    # check that log message includes "Refreshing token"
    access_token_cache._app_logger.info.assert_called_with(StringContaining("Refreshing token."))  # type: ignore

    # check that the access tokens are different
    assert first_access_token != second_access_token


def test_new_instance_of_client_returned_with_same_token() -> None:

    access_token_cache = SuiteCRMClientFactory(
        app_logger=mock.Mock(),
        suitecrm_api_url="http://example.com",
        suitecrm_client_id="client-test-id",
        suitecrm_client_secret="client-test-secret",  # nosec B106
    )

    access_token_cache._private_crm = mock.MagicMock()

    access_token_cache._private_crm.export_access_token.return_value = None

    access_token_cache._private_crm.export_access_token.return_value = {
        "access_token": "access-token",
        "expires_in": 3600,
        "expires_at": time.time() + 3600,
    }

    client1 = access_token_cache.get_client()
    client2 = access_token_cache.get_client()

    # check that the clients are different instances of SuiteCRM
    assert client1 is not client2

    # check that both clients have the same access token
    assert client1.export_access_token() == client2.export_access_token()
