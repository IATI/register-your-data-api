import json
import uuid

import pytest
from fastapi.testclient import TestClient

from ..helpers.mocking import MockedAppAndContext
from ..helpers.utilities import find_record_in_response


@pytest.mark.parametrize(
    "requesting_user,user_whose_orgs_to_fetch,reporting_org_details,status_code",
    [
        (  # user 0 accessing their own reporting orgs
            0,
            "698e0c1f-4e80-faa9-6533-68de801d1735",
            [
                ("552376ae-2aa7-98ab-d800-68daa9bfeb4a", "aid-agency-01"),
                ("ab851a83-a384-3eb9-caf0-68db8125b067", "agency-02"),
            ],
            200,
        ),
        (0, "bea511d3-c7a7-4097-55ed-68de81e94921", [], 403),  # user 0 accessing user 1's reporting orgs
        (
            1,
            "bea511d3-c7a7-4097-55ed-68de81e94921",
            [
                ("552376ae-2aa7-98ab-d800-68daa9bfeb4a", "aid-agency-01"),
                ("da17734d-3926-47ef-8563-8a1b0247ed11", "gov-agency-03"),
            ],
            200,
        ),
        (  # user 2 accessing their own reporting orgs - as a super admin, they shouldn't have any
            2,
            "a1b191ee-4c12-461c-cbe1-68de8173f628",
            [],
            200,
        ),
        (  # user 2 accessing user 0's reporting orgs
            2,
            "698e0c1f-4e80-faa9-6533-68de801d1735",
            [
                ("552376ae-2aa7-98ab-d800-68daa9bfeb4a", "aid-agency-01"),
                ("ab851a83-a384-3eb9-caf0-68db8125b067", "agency-02"),
            ],
            200,
        ),
        (  # user 0 accessing unknown user's reporting orgs
            0,
            "01234567-0123-0123-0123-012345678901",
            [],
            404,
        ),
        (  # user 2 (superadmin) accessing unknown user's reporting orgs
            0,
            "01234567-0123-0123-0123-012345678901",
            [],
            404,
        ),
    ],
)
def test_get_users_reporting_orgs(
    requesting_user: int, user_whose_orgs_to_fetch: str, reporting_org_details: list[tuple[str, str]], status_code: int
) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.get(
            f"/api/v1/users/{user_whose_orgs_to_fetch}/reporting-orgs",
            headers=appAndContext.get_valid_authorization_header(requesting_user),
            params={},
        )

        assert response.status_code == status_code

        if response.status_code == 200:

            resp_as_object = json.loads(response.content)

            assert len(resp_as_object["data"]) == len(reporting_org_details)

            for reporting_org in reporting_org_details:
                reporting_org_response_object = find_record_in_response(resp_as_object, reporting_org[0])

                assert reporting_org_response_object is not None
                assert reporting_org_response_object["metadata"]["short_name"] == reporting_org[1]


@pytest.mark.parametrize(
    "logged_in_user_idx,expected_status_code",
    [
        (0, 403),  # Person 1 (User index 0) is an EDITOR     - shouldn't be able to edit roles
        (1, 200),  # Person 2 (User index 1) is an ADMIN      - should be able to edit roles
        (3, 403),  # Person 4 (User index 3) is a CONTRIBUTOR - shouldn't be able to edit roles
    ],
)
def test_update_user_role_permissions_check(logged_in_user_idx: int, expected_status_code: int) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.put(
            "/api/v1/users/7625122c-f752-40dc-a577-5cb49e13de2a/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
            json={"role": "editor"},
        )

        assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "logged_in_user_idx,user_to_modify,expected_status_code",
    [
        (2, "7625122c-f752-40dc-a577-5cb49e13de2a", 200),
        (2, "01234567-0123-0123-0123-012345678901", 400),  # target is not-existent user, should be 400
        (2, "a1b191ee-4c12-461c-cbe1-68de8173f628", 400),  # target is super admin user, should be 400
    ],
)
def test_update_user_role_user_exists_in_crm_check(
    logged_in_user_idx: int, user_to_modify: str, expected_status_code: int
) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.put(
            f"/api/v1/users/{user_to_modify}/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
            json={"role": "editor"},
        )

        assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "logged_in_user_idx,reporting_org,expected_status_code",
    [
        (1, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", 200),
        (1, "0a3a9507-d674-480e-b625-7d190f4f3319", 400),  # reporting org w/no entry in MockCRM
    ],
)
def test_update_user_role_org_exists_in_crm_check(
    logged_in_user_idx: int, reporting_org: str, expected_status_code: int
) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.put(
            f"/api/v1/users/7625122c-f752-40dc-a577-5cb49e13de2a/reporting-org/{reporting_org}",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
            json={"role": "editor"},
        )

        assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "new_role",
    [
        "admin",
        "editor",
        "contributor",
    ],
)
def test_update_user_role_role_updated(new_role: str) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.put(
            "/api/v1/users/698e0c1f-4e80-faa9-6533-68de801d1735/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(1),
            json={"role": new_role},
        )

        assert response.status_code == 200

        role = appAndContext._mocked_context.fine_grained_auth_provider.get_user_role_for_org(
            uuid.UUID("698e0c1f-4e80-faa9-6533-68de801d1735"), uuid.UUID("552376ae-2aa7-98ab-d800-68daa9bfeb4a")
        )

        assert role is not None
        assert role.role.name.lower() == new_role


def test_update_user_role_role_repaired() -> None:
    """Tests that if the target user has no entry in the FGA DB, one is created with the requested role"""
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    role = appAndContext._mocked_context.fine_grained_auth_provider.get_user_role_for_org(
        uuid.UUID("8c51d9bf-46c2-4d1d-869b-d9e2dd63ff48"), uuid.UUID("552376ae-2aa7-98ab-d800-68daa9bfeb4a")
    )

    assert role is None  # pre-check - ensure no role exists before the update attempt

    with TestClient(fastAPIapp) as client:

        response = client.put(
            "/api/v1/users/8c51d9bf-46c2-4d1d-869b-d9e2dd63ff48/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(1),
            json={"role": "editor"},
        )

        assert response.status_code == 200

        role = appAndContext._mocked_context.fine_grained_auth_provider.get_user_role_for_org(
            uuid.UUID("8c51d9bf-46c2-4d1d-869b-d9e2dd63ff48"), uuid.UUID("552376ae-2aa7-98ab-d800-68daa9bfeb4a")
        )

        assert role is not None
        assert role.role.name.lower() == "editor"


@pytest.mark.parametrize(
    "logged_in_user_idx,expected_status_code",
    [
        (0, 403),  # Person 1 (User index 0) is an EDITOR     - shouldn't be able to delete roles
        (1, 200),  # Person 2 (User index 1) is an ADMIN      - should be able to delete roles
        (3, 403),  # Person 4 (User index 3) is a CONTRIBUTOR - shouldn't be able to delete roles
    ],
)
def test_delete_user_role_permissions_check(logged_in_user_idx: int, expected_status_code: int) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.delete(
            "/api/v1/users/7625122c-f752-40dc-a577-5cb49e13de2a/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
        )

        assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "logged_in_user_idx,user_to_modify,expected_status_code",
    [
        (2, "7625122c-f752-40dc-a577-5cb49e13de2a", 200),
        (2, "01234567-0123-0123-0123-012345678901", 400),  # target is not-existent user, should be 400
        (2, "a1b191ee-4c12-461c-cbe1-68de8173f628", 400),  # target is super admin user, should be 400
    ],
)
def test_delete_user_role_user_exists_in_crm_check(
    logged_in_user_idx: int, user_to_modify: str, expected_status_code: int
) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.delete(
            f"/api/v1/users/{user_to_modify}/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
        )

        assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "logged_in_user_idx,reporting_org,expected_status_code",
    [
        (1, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", 200),
        (1, "0a3a9507-d674-480e-b625-7d190f4f3319", 400),  # reporting org w/no entry in MockCRM
    ],
)
def test_delete_user_role_org_exists_in_crm_check(
    logged_in_user_idx: int, reporting_org: str, expected_status_code: int
) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.delete(
            f"/api/v1/users/7625122c-f752-40dc-a577-5cb49e13de2a/reporting-org/{reporting_org}",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
        )

        assert response.status_code == expected_status_code


def test_delete_user_role_role_delete() -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.delete(
            "/api/v1/users/698e0c1f-4e80-faa9-6533-68de801d1735/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(1),
        )

        assert response.status_code == 200

        role = appAndContext._mocked_context.fine_grained_auth_provider.get_user_role_for_org(
            uuid.UUID("698e0c1f-4e80-faa9-6533-68de801d1735"), uuid.UUID("552376ae-2aa7-98ab-d800-68daa9bfeb4a")
        )

        assert role is None
