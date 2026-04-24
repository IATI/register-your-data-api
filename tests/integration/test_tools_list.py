import pytest
from fastapi.testclient import TestClient

from ..helpers.mocking import MockedAppAndContext


@pytest.mark.parametrize(
    "logged_in_user_idx,expected_status_code",
    [
        (0, 200),
        (1, 200),
        (2, 200),
        (3, 200),
        (4, 200),
        (6, 500),
    ],
)
def test_get_tool_list(logged_in_user_idx: int, expected_status_code: int) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.get(
            "/api/v1/tools",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
        )
        response_as_object = response.json()

        assert response.status_code == expected_status_code
        assert "data" in response_as_object

        if expected_status_code == 200:
            assert sorted(response_as_object["data"], key=lambda x: x["id"]) == sorted(
                [
                    {"id": "3a9d5496-77f4-497d-bb77-2bda91285111", "name": "Tool One", "provider": "Tool Maker"},
                    {"id": "6a2d1ca1-b9c2-4bd3-a2a5-099178d1358d", "name": "Tool Two", "provider": "Tool Maker"},
                ],
                key=lambda x: x["id"],
            )
