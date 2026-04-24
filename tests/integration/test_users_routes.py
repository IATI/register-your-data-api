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
        (  # user 5 (tool user only) accessing user 0's reporting orgs
            4,
            "698e0c1f-4e80-faa9-6533-68de801d1735",
            [],
            403,
        ),
        (  # user 7 (provider admin and contributor) accessing their own reporting orgs
            6,
            "5c633101-42be-47ac-81e7-43d6ecb503e3",
            [],
            500,
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
        (4, 403),  # Person 5 (User index 4) is a PROVIDER_ADMIN - shouldn't be able to edit roles
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


def test_update_user_role_cannot_be_provider_admin() -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.put(
            "/api/v1/users/698e0c1f-4e80-faa9-6533-68de801d1735/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(1),
            json={"role": "provider_admin"},
        )

        assert response.status_code == 400


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

        roles = appAndContext._mocked_context.fine_grained_auth_provider.get_user_roles_for_org(
            uuid.UUID("698e0c1f-4e80-faa9-6533-68de801d1735"), uuid.UUID("552376ae-2aa7-98ab-d800-68daa9bfeb4a")
        )

        assert roles
        assert roles[0].role.name.lower() == new_role


def test_update_user_role_role_repaired() -> None:
    """Tests that if the target user has no entry in the FGA DB, one is created with the requested role"""
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    roles = appAndContext._mocked_context.fine_grained_auth_provider.get_user_roles_for_org(
        uuid.UUID("8c51d9bf-46c2-4d1d-869b-d9e2dd63ff48"), uuid.UUID("552376ae-2aa7-98ab-d800-68daa9bfeb4a")
    )

    assert len(roles) == 0  # pre-check - ensure no role exists before the update attempt

    with TestClient(fastAPIapp) as client:

        response = client.put(
            "/api/v1/users/8c51d9bf-46c2-4d1d-869b-d9e2dd63ff48/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(1),
            json={"role": "editor"},
        )

        assert response.status_code == 200

        roles = appAndContext._mocked_context.fine_grained_auth_provider.get_user_roles_for_org(
            uuid.UUID("8c51d9bf-46c2-4d1d-869b-d9e2dd63ff48"), uuid.UUID("552376ae-2aa7-98ab-d800-68daa9bfeb4a")
        )

        assert roles[0].role.name.lower() == "editor"


@pytest.mark.parametrize(
    "logged_in_user_idx,expected_status_code",
    [
        (0, 403),  # Person 1 (User index 0) is an EDITOR     - shouldn't be able to delete roles
        (1, 200),  # Person 2 (User index 1) is an ADMIN      - should be able to delete roles
        (3, 403),  # Person 4 (User index 3) is a CONTRIBUTOR - shouldn't be able to delete roles
        (4, 403),  # Person 5 (User index 4) is a PROVIDER_ADMIN - shouldn't be able to delete roles
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
    "logged_in_user_idx,expected_status_code",
    [
        (1, 400),  # Person 2 (User index 1) is an ADMIN - can delete roles, but should get 400 for last user
    ],
)
def test_delete_user_role_cannot_delete_last_user(logged_in_user_idx: int, expected_status_code: int) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.delete(
            "/api/v1/users/bea511d3-c7a7-4097-55ed-68de81e94921/reporting-org/da17734d-3926-47ef-8563-8a1b0247ed11",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
        )

        assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "logged_in_user_idx,expected_status_code",
    [
        (1, 400),  # Person 2 (User index 1) is an ADMIN - can delete roles, but should get 400 for last admin user
    ],
)
def test_delete_user_role_cannot_delete_last_admin_user(logged_in_user_idx: int, expected_status_code: int) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.delete(
            "/api/v1/users/bea511d3-c7a7-4097-55ed-68de81e94921/reporting-org/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
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

        roles = appAndContext._mocked_context.fine_grained_auth_provider.get_user_roles_for_org(
            uuid.UUID("698e0c1f-4e80-faa9-6533-68de801d1735"), uuid.UUID("552376ae-2aa7-98ab-d800-68daa9bfeb4a")
        )

        assert len(roles) == 0


@pytest.mark.parametrize(
    "logged_in_user_idx,user_id,expected_status_code",
    [
        (0, "698e0c1f-4e80-faa9-6533-68de801d1735", 200),  # Person One getting Person One roles
        (0, "bea511d3-c7a7-4097-55ed-68de81e94921", 403),  # Person One getting Person Two roles
        (0, "a1b191ee-4c12-461c-cbe1-68de8173f628", 403),  # Person One getting Person Three roles
        (0, "7625122c-f752-40dc-a577-5cb49e13de2a", 403),  # Person One getting Person Four roles
        (0, "b46b88bd-05e6-4cb8-8b6a-a2c47fcd666d", 403),  # Person One getting Person Five roles
        (0, "5c633101-42be-47ac-81e7-43d6ecb503e3", 403),  # Person One getting Person Seven roles
        (0, "1d973500-9c23-4f63-914c-c7f1d78fb756", 403),  # Person One getting non-existent user roles
        (1, "698e0c1f-4e80-faa9-6533-68de801d1735", 403),  # Person Two getting Person One roles
        (1, "bea511d3-c7a7-4097-55ed-68de81e94921", 200),  # Person Two getting Person Two roles
        (1, "a1b191ee-4c12-461c-cbe1-68de8173f628", 403),  # Person Two getting Person Three roles
        (1, "7625122c-f752-40dc-a577-5cb49e13de2a", 403),  # Person Two getting Person Four roles
        (1, "b46b88bd-05e6-4cb8-8b6a-a2c47fcd666d", 403),  # Person Two getting Person Five roles
        (1, "5c633101-42be-47ac-81e7-43d6ecb503e3", 403),  # Person Two getting Person Seven roles
        (1, "1d973500-9c23-4f63-914c-c7f1d78fb756", 403),  # Person Two getting non-existent user roles
        (2, "698e0c1f-4e80-faa9-6533-68de801d1735", 200),  # Person Three (s/admin) getting Person One roles
        (2, "bea511d3-c7a7-4097-55ed-68de81e94921", 200),  # Person Three (s/admin) getting Person Two roles
        (2, "a1b191ee-4c12-461c-cbe1-68de8173f628", 200),  # Person Three (s/admin) getting Person Three roles
        (2, "7625122c-f752-40dc-a577-5cb49e13de2a", 200),  # Person Three (s/admin) getting Person Four roles
        (2, "b46b88bd-05e6-4cb8-8b6a-a2c47fcd666d", 200),  # Person Three (s/admin) getting Person Five roles
        (2, "5c633101-42be-47ac-81e7-43d6ecb503e3", 200),  # Person Three (s/admin) getting Person Seven roles
        (2, "1d973500-9c23-4f63-914c-c7f1d78fb756", 404),  # Person Three (s/admin) getting non-existent user roles
        (3, "698e0c1f-4e80-faa9-6533-68de801d1735", 403),  # Person Four getting Person One roles
        (3, "bea511d3-c7a7-4097-55ed-68de81e94921", 403),  # Person Four getting Person Two roles
        (3, "a1b191ee-4c12-461c-cbe1-68de8173f628", 403),  # Person Four getting Person Three roles
        (3, "7625122c-f752-40dc-a577-5cb49e13de2a", 200),  # Person Four getting Person Four roles
        (3, "b46b88bd-05e6-4cb8-8b6a-a2c47fcd666d", 403),  # Person Four getting Person Five roles
        (3, "5c633101-42be-47ac-81e7-43d6ecb503e3", 403),  # Person Four getting Person Seven roles
        (3, "1d973500-9c23-4f63-914c-c7f1d78fb756", 403),  # Person Four getting non-existent user roles
        (4, "698e0c1f-4e80-faa9-6533-68de801d1735", 403),  # Person Five (p/admin) getting Person One roles
        (4, "bea511d3-c7a7-4097-55ed-68de81e94921", 403),  # Person Five (p/admin) getting Person Two roles
        (4, "a1b191ee-4c12-461c-cbe1-68de8173f628", 403),  # Person Five (p/admin) getting Person Three roles
        (4, "7625122c-f752-40dc-a577-5cb49e13de2a", 403),  # Person Five (p/admin) getting Person Four roles
        (4, "b46b88bd-05e6-4cb8-8b6a-a2c47fcd666d", 200),  # Person Five (p/admin) getting Person Five roles
        (4, "5c633101-42be-47ac-81e7-43d6ecb503e3", 403),  # Person Five (p/admin) getting Person Seven roles
        (4, "1d973500-9c23-4f63-914c-c7f1d78fb756", 403),  # Person Five (p/admin) getting non-existent user roles
        (6, "698e0c1f-4e80-faa9-6533-68de801d1735", 500),  # Person Seven (p/admin) getting Person One roles
        (6, "bea511d3-c7a7-4097-55ed-68de81e94921", 500),  # Person Seven (p/admin) getting Person Two roles
        (6, "a1b191ee-4c12-461c-cbe1-68de8173f628", 500),  # Person Seven (p/admin) getting Person Three roles
        (6, "7625122c-f752-40dc-a577-5cb49e13de2a", 500),  # Person Seven (p/admin) getting Person Four roles
        (6, "b46b88bd-05e6-4cb8-8b6a-a2c47fcd666d", 500),  # Person Seven (p/admin) getting Person Five roles
        (6, "5c633101-42be-47ac-81e7-43d6ecb503e3", 500),  # Person Seven (p/admin) getting Person Seven roles
        (6, "1d973500-9c23-4f63-914c-c7f1d78fb756", 500),  # Person Seven (p/admin) getting non-existent user roles
    ],
)
def test_user_role_access_permissions(logged_in_user_idx: int, user_id: str, expected_status_code: int) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.get(
            f"/api/v1/users/{user_id}/roles",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
        )

        assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "logged_in_user_idx,user_id,superadmin,tools,reporting_orgs",
    [
        (
            0,
            "698e0c1f-4e80-faa9-6533-68de801d1735",
            False,
            [],
            {
                "552376ae-2aa7-98ab-d800-68daa9bfeb4a": "editor",
                "ab851a83-a384-3eb9-caf0-68db8125b067": "admin",
            },
        ),
        (
            1,
            "bea511d3-c7a7-4097-55ed-68de81e94921",
            False,
            [],
            {
                "552376ae-2aa7-98ab-d800-68daa9bfeb4a": "admin",
                "da17734d-3926-47ef-8563-8a1b0247ed11": "admin",
                "0a3a9507-d674-480e-b625-7d190f4f3319": "admin",
            },
        ),
        (2, "a1b191ee-4c12-461c-cbe1-68de8173f628", True, [], {}),
        (
            3,
            "7625122c-f752-40dc-a577-5cb49e13de2a",
            False,
            [],
            {
                "552376ae-2aa7-98ab-d800-68daa9bfeb4a": "contributor",
                "ab851a83-a384-3eb9-caf0-68db8125b067": "contributor_pending",
                "0a3a9507-d674-480e-b625-7d190f4f3319": "contributor_pending",
            },
        ),
        (
            4,
            "b46b88bd-05e6-4cb8-8b6a-a2c47fcd666d",
            False,
            ["3a9d5496-77f4-497d-bb77-2bda91285111", "6a2d1ca1-b9c2-4bd3-a2a5-099178d1358d"],
            {
                "552376ae-2aa7-98ab-d800-68daa9bfeb4a": "provider_admin",
                "ab851a83-a384-3eb9-caf0-68db8125b067": "provider_admin",
            },
        ),
    ],
)
def test_user_roles_correctly_returned(
    logged_in_user_idx: int, user_id: str, superadmin: bool, tools: list[str], reporting_orgs: dict[str, str]
) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.get(
            f"/api/v1/users/{user_id}/roles",
            headers=appAndContext.get_valid_authorization_header(logged_in_user_idx),
        )

        assert response.status_code == 200

        resp_as_object = response.json()

        assert resp_as_object["data"]["superadmin"] == superadmin
        assert len(resp_as_object["data"]["tools"]) == len(tools)
        assert sorted(resp_as_object["data"]["tools"]) == sorted(tools)
        assert len(resp_as_object["data"]["reporting_orgs"]) == len(reporting_orgs)
        assert resp_as_object["data"]["reporting_orgs"] == reporting_orgs


def test_user_role_reporting_org_permissions_not_implemented() -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    # When implemented, this call should return a list of permissions matching "editor".
    with TestClient(fastAPIapp) as client:
        response = client.get(
            (
                "/api/v1/users/698e0c1f-4e80-faa9-6533-68de801d1735/roles/"
                "reporting-org-permissions/552376ae-2aa7-98ab-d800-68daa9bfeb4a"
            ),
            headers=appAndContext.get_valid_authorization_header(0),
        )

        assert response.status_code == 501
