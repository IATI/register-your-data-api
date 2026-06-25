import json

import pytest
from fastapi.testclient import TestClient

from register_your_data_api.data_handling.data_schemas import (
    DiscoverableReportingOrgMetadata,
    ReportingOrgMetadata,
)

from ..helpers.mocking import MockedAppAndContext
from ..helpers.utilities import find_record_in_response, is_valid_uuid


@pytest.mark.parametrize(
    "user,reporting_org_details,status_code",
    [
        (
            0,
            [
                ("552376ae-2aa7-98ab-d800-68daa9bfeb4a", "aid-agency-01"),
                ("ab851a83-a384-3eb9-caf0-68db8125b067", "agency-02"),
            ],
            200,
        ),
        (
            1,
            [
                ("552376ae-2aa7-98ab-d800-68daa9bfeb4a", "aid-agency-01"),
                ("da17734d-3926-47ef-8563-8a1b0247ed11", "gov-agency-03"),
            ],
            200,
        ),
        (
            2,
            [],
            200,
        ),
        (
            4,
            [],
            200,
        ),
        (
            6,
            [],
            500,
        ),
    ],
)
def test_reporting_orgs_fetch_correct_orgs_for_user(
    user: int, reporting_org_details: list[tuple[str, str]], status_code: int
) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.get(
            "/api/v1/reporting-orgs",
            headers=appAndContext.get_valid_authorization_header(user),
            params={},
        )

        assert response.status_code == status_code

        if response.status_code != 500:
            resp_as_object = json.loads(response.content)

            assert len(resp_as_object["data"]) == len(reporting_org_details)

            for reporting_org in reporting_org_details:
                reporting_org_response_object = find_record_in_response(resp_as_object, reporting_org[0])

                assert reporting_org_response_object is not None
                assert reporting_org_response_object["metadata"]["short_name"] == reporting_org[1]


def test_reporting_orgs_fetch_correct_org_info_for_admin_and_editor() -> None:

    reporting_org_details = [
        ("552376ae-2aa7-98ab-d800-68daa9bfeb4a", "aid-agency-01", "Aid Agency 01", "GB", "Test agency 01"),
        ("ab851a83-a384-3eb9-caf0-68db8125b067", "agency-02", "Agency 02", "LV", ""),
    ]

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.get(
            "/api/v1/reporting-orgs",
            headers=appAndContext.get_valid_authorization_header(0),
            params={},
        )

        assert response.status_code == 200

        resp_as_object = json.loads(response.content)

        assert len(resp_as_object["data"]) == len(reporting_org_details)

        for reporting_org in reporting_org_details:
            reporting_org_response_object = find_record_in_response(resp_as_object, reporting_org[0])

            assert reporting_org_response_object is not None
            assert "metadata" in reporting_org_response_object

            assert len(reporting_org_response_object["metadata"]) == len(ReportingOrgMetadata.model_fields.keys())

            assert reporting_org_response_object["metadata"]["short_name"] == reporting_org[1]
            assert reporting_org_response_object["metadata"]["human_readable_name"] == reporting_org[2]
            assert reporting_org_response_object["metadata"]["hq_country"] == reporting_org[3]
            assert reporting_org_response_object["metadata"]["description"] == reporting_org[4]


def test_reporting_orgs_fetch_correct_org_info_for_contributor_pending() -> None:

    reporting_org_details = {
        "id": "ab851a83-a384-3eb9-caf0-68db8125b067",
        "short_name": "agency-02",
        "human_readable_name": "Agency 02",
        "hq_country": "LV",
        "region": "89",
        "website": "http://",
        "organisation_identifier": "XI-012345-6789",
    }

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.get(
            "/api/v1/reporting-orgs",
            headers=appAndContext.get_valid_authorization_header(3),
            params={},
        )

        assert response.status_code == 200

        resp_as_object = json.loads(response.content)

        org_user_is_pending_for = find_record_in_response(resp_as_object, reporting_org_details["id"])

        assert org_user_is_pending_for is not None
        assert "metadata" in org_user_is_pending_for

        assert len(org_user_is_pending_for["metadata"]) == len(DiscoverableReportingOrgMetadata.model_fields.keys())

        assert org_user_is_pending_for["metadata"]["short_name"] == reporting_org_details["short_name"]
        assert (
            org_user_is_pending_for["metadata"]["human_readable_name"] == reporting_org_details["human_readable_name"]
        )
        assert org_user_is_pending_for["metadata"]["hq_country"] == reporting_org_details["hq_country"]
        assert org_user_is_pending_for["metadata"]["region"] == reporting_org_details["region"]
        assert org_user_is_pending_for["metadata"]["website"] == reporting_org_details["website"]
        assert (
            org_user_is_pending_for["metadata"]["organisation_identifier"]
            == reporting_org_details["organisation_identifier"]
        )


def test_reporting_org_detail_handles_non_uuid() -> None:
    """Tests that /reporting_orgs/{oid} returns 400 when {oid} is not a UUID"""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.get(
            "/api/v1/reporting-orgs/INVALID", headers=appAndContext.get_valid_authorization_header(2)
        )

        assert response.status_code == 400

        resp_as_object = json.loads(response.content)

        assert resp_as_object["error"]["error_msg"].find("Data validation error") == 0


@pytest.mark.parametrize(
    "user,reporting_org_id,client_id,status_code",
    [
        (0, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 200),
        (0, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 200),
        (0, "01234567-0000-1111-2222-0123456789ab", "some_client", 403),
        (1, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 200),
        (1, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 403),
        (1, "01234567-0000-1111-2222-0123456789ab", "some_client", 403),
        (2, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 200),
        (2, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 200),
        (2, "01234567-0000-1111-2222-0123456789ab", "some_client", 404),
        (4, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "wUtu4EuLSlstjasC", 200),
        (4, "ab851a83-a384-3eb9-caf0-68db8125b067", "wUtu4EuLSlstjasC", 200),
        (4, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 403),
        (4, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 403),
        (4, "da17734d-3926-47ef-8563-8a1b0247ed11", "some_client", 403),
        (4, "01234567-0000-1111-2222-0123456789ab", "some_client", 403),
        (6, "da17734d-3926-47ef-8563-8a1b0247ed11", "some_client", 500),
        (6, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 500),
        (6, "01234567-0000-1111-2222-0123456789ab", "some_client", 500),
    ],
)
def test_reporting_org_detail_check_user_access(
    user: int, reporting_org_id: str, client_id: str, status_code: int
) -> None:
    """Tests the user's access to /reporting_orgs/{oid}"""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.get(
            f"/api/v1/reporting-orgs/{reporting_org_id}",
            headers=appAndContext.get_valid_authorization_header(user, client_id=client_id),
        )

        assert response.status_code == status_code


@pytest.mark.parametrize(
    "users,reporting_org_id,reporting_org_details",
    [
        (
            [0, 1, 2, 4],
            "552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            {
                "data_portal_url": "http://data-portal.com",
                "default_licence_id": "cc-zero",
                "description": "Test agency 01",
                "exclusions_policy_url": "http://exclusions-policy.com",
                "hq_country": "GB",
                "human_readable_name": "Aid Agency 01",
                "organisation_identifier": "GB-TEST-AGENCY-01",
                "organisation_type": "21",
                "region": "89",
                "short_name": "aid-agency-01",
                "website": "http://aid-agency.org",
            },
        ),
        (
            [0, 2, 4],
            "ab851a83-a384-3eb9-caf0-68db8125b067",
            {
                "data_portal_url": "",
                "default_licence_id": "cc-by-sa",
                "description": "",
                "exclusions_policy_url": "",
                "hq_country": "LV",
                "human_readable_name": "Agency 02",
                "organisation_identifier": "XI-012345-6789",
                "organisation_type": "",
                "region": "89",
                "short_name": "agency-02",
                "website": "http://",
            },
        ),
    ],
)
def test_reporting_org_detail_check_values(
    users: list[int], reporting_org_id: str, reporting_org_details: dict[str, str]
) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    for user in users:
        with TestClient(fastAPIapp) as client:
            response = client.get(
                f"/api/v1/reporting-orgs/{reporting_org_id}",
                headers=appAndContext.get_valid_authorization_header(user, client_id="wUtu4EuLSlstjasC"),
                params={},
            )

            assert response.status_code == 200

            resp_as_object = json.loads(response.content)

            reporting_org_response_object = resp_as_object["data"]

            assert reporting_org_response_object is not None
            assert (
                reporting_org_response_object["metadata"]["human_readable_name"]
                == reporting_org_details["human_readable_name"]
            )
            assert (
                reporting_org_response_object["metadata"]["organisation_identifier"]
                == reporting_org_details["organisation_identifier"]
            )
            assert reporting_org_response_object["metadata"]["short_name"] == reporting_org_details["short_name"]

            assert reporting_org_response_object["metadata"]["data_portal_url"] is not None
            assert reporting_org_response_object["metadata"]["default_licence_id"] is not None
            assert reporting_org_response_object["metadata"]["description"] is not None
            assert reporting_org_response_object["metadata"]["exclusions_policy_url"] is not None
            assert reporting_org_response_object["metadata"]["hq_country"] is not None
            assert reporting_org_response_object["metadata"]["organisation_type"] is not None
            assert reporting_org_response_object["metadata"]["region"] is not None
            assert reporting_org_response_object["metadata"]["website"] is not None


@pytest.mark.parametrize(
    "user,status_code,expect_success",
    [
        (0, 201, True),
        (1, 201, True),
        (2, 201, True),  # TODO: we should prevent this in the future.
        (4, 201, True),  # TODO: we should prevent this in the future.
    ],
)
def test_reporting_org_create(user: int, status_code: int, expect_success: bool) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    new_reporting_org = {
        "address": "Fake Address",
        "contact_email": "org.admin@example.org",
        "data_portal_url": "https://www.example.org/data-portal",
        "default_licence_id": "gpl-3.0",
        "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "exclusions_policy_url": "https://www.example.org/exclusions-policy",
        "fax": "456-7890-1234",
        "hq_country": "CO",
        "human_readable_name": "Aid Agency",
        "organisation_identifier": "CO-ABC-123456",
        "organisation_type": "Regional NGO",
        "phone": "123-4567-8901",
        "region": "489",
        "reporting_source_type": "primary_source",
        "short_name": "aidagy",
        "website": "https://www.example.org/",
    }

    with TestClient(fastAPIapp) as client:
        response = client.post(
            "/api/v1/reporting-orgs/",
            headers=appAndContext.get_valid_authorization_header(user),
            content=json.dumps(new_reporting_org),
        )

        assert response.status_code == status_code

        response_obj = json.loads(response.content)

        if expect_success:
            assert response_obj["status"] == "success"

            assert is_valid_uuid(response_obj["data"]["id"])
            assert response_obj["data"]["user_role"] == "admin"

            for field in new_reporting_org.keys():
                assert response_obj["data"]["metadata"][field] == new_reporting_org[field]

            for derived_field in [
                "created_date",
                "first_publication_date",
                "number_of_published_datasets",
                "registry_approved",
            ]:
                assert derived_field in response_obj["data"]["metadata"].keys()

            assert isinstance(response_obj["data"]["metadata"]["registry_approved"], bool)


@pytest.mark.parametrize("user", [0, 1, 2, 4])
def test_reporting_org_create_with_missing_fields(user: int) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    reporting_org = {
        "address": "Fake Address",
        "contact_email": "org.admin@example.org",
        "data_portal_url": "https://www.example.org/data-portal",
        "default_licence_id": "gpl-3.0",
        "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "exclusions_policy_url": "https://www.example.org/exclusions-policy",
        "fax": "456-7890-1234",
        "hq_country": "CO",
        "human_readable_name": "Aid Agency",
        "organisation_identifier": "CO-ABC-123456",
        "organisation_type": "Regional NGO",
        "phone": "123-4567-8901",
        "region": "489",
        "reporting_source_type": "primary_source",
        "short_name": "aidagy",
        "website": "https://www.example.org/",
    }

    with TestClient(fastAPIapp) as client:

        for reporting_org_with_a_missing_field in map(
            lambda x: {k: v for k, v in reporting_org.items() if k != x}, list(reporting_org.keys())
        ):

            response = client.post(
                "/api/v1/reporting-orgs/",
                headers=appAndContext.get_valid_authorization_header(user),
                content=json.dumps(reporting_org_with_a_missing_field),
            )

            assert response.status_code == 400

            response_obj = json.loads(response.content)

            assert response_obj["status"] == "failed"


@pytest.mark.parametrize(
    "invalid_short_name",
    [
        "invalid short name!",  # contains spaces and exclamation mark
        "invalid@name",  # contains special character '@'
        "name/with/slash",  # contains slash
        "name\\with\\backslash",  # contains backslash
        "name:with:colon",  # contains colon
        "name*with*asterisk",  # contains asterisk
        "name?with?question",  # contains question mark
        "nameWITH_UPPER_casecharacters",  # containers uppoer case chars
        "ALLUPPERNAME",  # all upper case chars
    ],
)
def test_reporting_org_create_with_invalid_short_name(invalid_short_name: str) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    new_reporting_org = {
        "address": "Fake Address",
        "contact_email": "org.admin@example.org",
        "data_portal_url": "https://www.example.org/data-portal",
        "default_licence_id": "gpl-3.0",
        "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "exclusions_policy_url": "https://www.example.org/exclusions-policy",
        "fax": "456-7890-1234",
        "hq_country": "CO",
        "human_readable_name": "Aid Agency",
        "organisation_identifier": "CO-ABC-123456",
        "organisation_type": "Regional NGO",
        "phone": "123-4567-8901",
        "region": "489",
        "reporting_source_type": "primary_source",
        "short_name": invalid_short_name,
        "website": "https://www.example.org/",
    }

    with TestClient(fastAPIapp) as client:
        response = client.post(
            "/api/v1/reporting-orgs/",
            headers=appAndContext.get_valid_authorization_header(0),
            content=json.dumps(new_reporting_org),
        )

        assert response.status_code == 400

        response_obj = json.loads(response.content)

        assert response_obj["status"] == "failed"


@pytest.mark.parametrize(
    "user,status_code,organisation_id",
    [
        (0, 200, "552376ae-2aa7-98ab-d800-68daa9bfeb4a"),  # Editor of org
        (1, 200, "552376ae-2aa7-98ab-d800-68daa9bfeb4a"),  # Admin of org
        (2, 200, "552376ae-2aa7-98ab-d800-68daa9bfeb4a"),  # Superadmin
        (3, 403, "552376ae-2aa7-98ab-d800-68daa9bfeb4a"),  # Contributor of org
        (3, 403, "ab851a83-a384-3eb9-caf0-68db8125b067"),  # Contributor pending in org
        (4, 200, "552376ae-2aa7-98ab-d800-68daa9bfeb4a"),  # Provider admin via Tool One
        (4, 403, "da17734d-3926-47ef-8563-8a1b0247ed11"),  # Provider admin but Tool has no permission for org
        (6, 500, "552376ae-2aa7-98ab-d800-68daa9bfeb4a"),  # Failure: has provider admin and org role
    ],
)
def test_reporting_org_update(user: int, status_code: int, organisation_id: str) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        # Get the organisation record using the superadmin user, so we have the record
        # to tweak and test the actual user.
        response = client.get(
            f"/api/v1/reporting-orgs/{organisation_id}",
            headers=appAndContext.get_valid_authorization_header(2),
        )

        assert response.status_code == 200

        payload = response.json()
        payload["contact_email"] = "changed.email@example.org"

        response = client.patch(
            f"/api/v1/reporting-orgs/{organisation_id}",
            headers=appAndContext.get_valid_authorization_header(user, client_id="wUtu4EuLSlstjasC"),
            content=json.dumps(payload),
        )


@pytest.mark.parametrize("user,status_code", [(0, 403), (1, 200), (2, 200), (3, 403), (4, 403)])
def test_reporting_org_delete(user: int, status_code: int) -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        response = client.delete(
            "/api/v1/reporting-orgs/552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            headers=appAndContext.get_valid_authorization_header(user, client_id="wUtu4EuLSlstjasC"),
        )

        assert response.status_code == status_code


@pytest.mark.parametrize(
    "user,reporting_org_id,client_id,status,status_s,num_datasets",
    [
        (0, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 200, "success", 1),
        (0, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 200, "success", 2),
        (0, "da17734d-3926-47ef-8563-8a1b0247ed11", "some_client", 403, "failed", -1),
        (0, "92f398c1-6163-f097-3ded-68e9138bb9c8", "some_client", 403, "failed", -1),
        (1, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 200, "success", 1),
        (1, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 403, "failed", -1),
        (1, "da17734d-3926-47ef-8563-8a1b0247ed11", "some_client", 200, "success", 0),
        (2, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 200, "success", 1),
        (2, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 200, "success", 2),
        (2, "92f398c1-6163-f097-3ded-68e9138bb9c8", "some_client", 404, "failed", -1),
        (2, "da17734d-3926-47ef-8563-8a1b0247ed11", "some_client", 200, "success", 0),
        (4, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "wUtu4EuLSlstjasC", 200, "success", 1),
        (4, "ab851a83-a384-3eb9-caf0-68db8125b067", "wUtu4EuLSlstjasC", 200, "success", 2),
        (4, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "invalid_client", 403, "failed", -1),
        (4, "ab851a83-a384-3eb9-caf0-68db8125b067", "invalid_client", 403, "failed", -1),
        (4, "92f398c1-6163-f097-3ded-68e9138bb9c8", "some_client", 403, "failed", -1),
        (4, "da17734d-3926-47ef-8563-8a1b0247ed11", "some_client", 403, "failed", -1),
        (6, "da17734d-3926-47ef-8563-8a1b0247ed11", "some_client", 500, "failed", -1),
        (6, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 500, "failed", -1),
        (6, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 500, "failed", -1),
        (6, "92f398c1-6163-f097-3ded-68e9138bb9c8", "some_client", 500, "failed", -1),
    ],
)
def test_reporting_org_list_datasets(
    user: int, reporting_org_id: str, client_id: str, status: int, status_s: str, num_datasets: int
) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:

        response = client.get(
            f"/api/v1/reporting-orgs/{reporting_org_id}/datasets",
            headers=appAndContext.get_valid_authorization_header(user, client_id=client_id),
        )

        assert response.status_code == status

        resp_json = response.json()

        assert resp_json["status"] == status_s

        if status == 200:
            assert len(resp_json["data"]) == num_datasets


# Note: Testing of paging is extremeley limited unless we implement paging on
# the SuiteCR mock object or switch to using a real SuiteCRM instance for
# testing. (Using Mockoon here wouldn't provide a quick solution because while
# their CRUD routes support paging, it does not use the JSON:API paging schema
# that SuiteCRM uses.)
@pytest.mark.parametrize(
    "user,reporting_org_id,page,num_pages,links",
    [
        (0, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", 1, 1, (True, True, False, False)),
        (0, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", 500, 1, (True, True, False, True)),
        (1, "da17734d-3926-47ef-8563-8a1b0247ed11", 1, 1, (True, True, False, False)),
    ],
)
def test_reporting_org_list_datasets_paging(
    user: int, reporting_org_id: str, page: int, num_pages: int, links: tuple[bool, bool, bool, bool]
) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:

        response = client.get(
            f"/api/v1/reporting-orgs/{reporting_org_id}/datasets?page={page}",
            headers=appAndContext.get_valid_authorization_header(user),
        )

        pagination = response.json()["pagination"]

        assert pagination["total_pages"] == num_pages
        assert pagination["page"] == page

        assert (pagination["links"]["first"] is not None) == links[0]
        assert (pagination["links"]["last"] is not None) == links[1]
        assert (pagination["links"]["next"] is not None) == links[2]
        assert (pagination["links"]["prev"] is not None) == links[3]


@pytest.mark.parametrize(
    (
        "user,reporting_org_id,dataset_idx,dataset_id,human_readable_name,"
        "licence_id,short_name,source_type,url,visibility"
    ),
    [
        (
            0,
            "552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            0,
            "52ac525f-6375-079b-977d-68ecf3be2868",
            "Aid Agency - Dataset 01",
            "cc-zero",
            "aidagy-data-01",
            "primary_source",
            "http://aidagency.com/dataset-01.xml",
            "public",
        ),
        (
            0,
            "ab851a83-a384-3eb9-caf0-68db8125b067",
            1,
            "6f0616d2-1a3a-0545-a495-68ecf41bb123",
            "Aid Agency 2 - South Dataset",
            "odc-odbl",
            "aid-agency-02-south",
            "primary_source",
            "http://aidagency.com/south-dataset.xml",
            "public",
        ),
    ],
)
def test_reporting_org_list_datasets_detail(
    user: int,
    reporting_org_id: str,
    dataset_idx: int,
    dataset_id: str,
    human_readable_name: str,
    licence_id: str,
    short_name: str,
    source_type: str,
    url: str,
    visibility: str,
) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:

        response = client.get(
            f"/api/v1/reporting-orgs/{reporting_org_id}/datasets",
            headers=appAndContext.get_valid_authorization_header(user),
        )

        assert response.status_code == 200

        resp_as_obj = response.json()

        dataset = resp_as_obj["data"][dataset_idx]

        assert dataset["id"] == dataset_id
        assert dataset["owner_organisation_id"] == reporting_org_id
        assert dataset["metadata"]["licence_id"] == licence_id
        assert dataset["metadata"]["short_name"] == short_name
        assert dataset["metadata"]["source_type"] == source_type
        assert dataset["metadata"]["url"] == url
        assert dataset["metadata"]["visibility"] == visibility


@pytest.mark.parametrize(
    "user,reporting_org_id,expect_unauthorised,visible_users",
    [
        (
            0,  # user 0 / person 1 is EDITOR for 552376ae-2aa7-98ab-d800-68daa9bfeb4a
            "552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            False,
            {
                "698e0c1f-4e80-faa9-6533-68de801d1735",
                "bea511d3-c7a7-4097-55ed-68de81e94921",
                "7625122c-f752-40dc-a577-5cb49e13de2a",
            },
        ),
        (
            2,  # user 2 / person 3 is SUPER_ADMIN
            "552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            False,
            {
                "698e0c1f-4e80-faa9-6533-68de801d1735",
                "bea511d3-c7a7-4097-55ed-68de81e94921",
                "7625122c-f752-40dc-a577-5cb49e13de2a",
                "b46b88bd-05e6-4cb8-8b6a-a2c47fcd666d",
                "5c633101-42be-47ac-81e7-43d6ecb503e3",
            },
        ),
        (
            4,  # user 4 / person 5 is PROVIDER_ADMIN for Tool 1 with access to 552376ae-2aa7-98ab-d800-68daa9bfeb4a
            "552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            False,
            {
                "698e0c1f-4e80-faa9-6533-68de801d1735",
                "bea511d3-c7a7-4097-55ed-68de81e94921",
                "7625122c-f752-40dc-a577-5cb49e13de2a",
            },
        ),
        (0, "da17734d-3926-47ef-8563-8a1b0247ed11", True, []),
    ],
)
def test_reporting_org_list_users(
    user: int, reporting_org_id: str, expect_unauthorised: bool, visible_users: set[str]
) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:

        response = client.get(
            f"/api/v1/reporting-orgs/{reporting_org_id}/users",
            headers=appAndContext.get_valid_authorization_header(user, client_id="wUtu4EuLSlstjasC"),
        )

        if expect_unauthorised:
            assert response.status_code == 403
        else:
            assert response.status_code == 200

            resp_json = response.json()

            users_returned = {user["id"] for user in resp_json["data"]}

            assert users_returned == visible_users


def test_reporting_org_tool_management_not_implemented() -> None:
    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:
        # When implemented, this call should authorise a tool to have permission to edit
        # records for this organisation.
        response = client.post(
            "/api/v1/reporting-orgs/ab851a83-a384-3eb9-caf0-68db8125b067/tools",
            headers=appAndContext.get_valid_authorization_header(0),
            json={"tid": "6a2d1ca1-b9c2-4bd3-a2a5-099178d1358d"},
        )

        assert response.status_code == 501

        # When implemented, this call should revoke permission for this tool to have
        # permission to edit records for this organisation.
        response = client.delete(
            "/api/v1/reporting-orgs/ab851a83-a384-3eb9-caf0-68db8125b067/tools/6a2d1ca1-b9c2-4bd3-a2a5-099178d1358d",
            headers=appAndContext.get_valid_authorization_header(0),
        )

        assert response.status_code == 501


def test_reporting_org_tool_list_returns_authorised_tools() -> None:
    """Tests that GET /reporting-orgs/{oid}/tools returns the tools authorised for that org.

    Tool One (configured in tests/helpers/mocking.py) is authorised for org
    552376ae-2aa7-98ab-d800-68daa9bfeb4a; Tool Two has no authorisation for any
    org and so must not be returned.
    """

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    org_id = "552376ae-2aa7-98ab-d800-68daa9bfeb4a"

    with TestClient(fastAPIapp) as client:
        response = client.get(
            f"/api/v1/reporting-orgs/{org_id}/tools",
            headers=appAndContext.get_valid_authorization_header(0),
        )

        assert response.status_code == 200

        resp_json = response.json()

        assert resp_json["status"] == "success"

        tools_by_id = {tool["id"]: tool for tool in resp_json["data"]}

        tool_one_id = str(appAndContext._mocked_tool_ids[0])
        tool_two_id = str(appAndContext._mocked_tool_ids[1])

        # Tool One is authorised for this org and should be returned.
        assert tool_one_id in tools_by_id
        assert tools_by_id[tool_one_id]["name"] == "Tool One"
        assert tools_by_id[tool_one_id]["provider"] == "Tool Maker"

        # Tool Two has no authorisation for any org and should not be returned.
        assert tool_two_id not in tools_by_id


def test_reporting_org_tool_list_forbidden_for_provider_admin() -> None:
    """A provider admin must not be able to read an org's authorised tool list.

    User 4 is a provider admin for Tool One, which is authorised for org
    552376ae-2aa7-98ab-d800-68daa9bfeb4a.  Although they can act on that org through their
    tool, they do not belong to it, so reading its tool authorisations is forbidden.
    """

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    org_id = "552376ae-2aa7-98ab-d800-68daa9bfeb4a"

    with TestClient(fastAPIapp) as client:
        response = client.get(
            f"/api/v1/reporting-orgs/{org_id}/tools",
            headers=appAndContext.get_valid_authorization_header(4, client_id="wUtu4EuLSlstjasC"),
        )

        assert response.status_code == 403


def test_reporting_org_authorise_tool_adds_tool() -> None:
    """A tool can be authorised for an organisation via POST /reporting-orgs/{oid}/tools.

    Tool Two is not authorised for any org in the mock data (tests/helpers/mocking.py).
    After authorising it for org 552376ae-2aa7-98ab-d800-68daa9bfeb4a it should appear in
    that org's authorised tool list.
    """

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    org_id = "552376ae-2aa7-98ab-d800-68daa9bfeb4a"
    tool_two_id = str(appAndContext._mocked_tool_ids[1])

    with TestClient(fastAPIapp) as client:
        # User 1 is an ADMIN of this org and so may authorise tools for it.
        response = client.post(
            f"/api/v1/reporting-orgs/{org_id}/tools",
            headers=appAndContext.get_valid_authorization_header(1),
            json={"tid": tool_two_id},
        )

        assert response.status_code == 201
        assert response.json()["status"] == "success"

        # The newly authorised tool should now appear in the org's tool list.
        response = client.get(
            f"/api/v1/reporting-orgs/{org_id}/tools",
            headers=appAndContext.get_valid_authorization_header(1),
        )

        assert response.status_code == 200
        authorised_tool_ids = {tool["id"] for tool in response.json()["data"]}
        assert tool_two_id in authorised_tool_ids


@pytest.mark.parametrize(
    "user,reporting_org_id,client_id,status_code",
    [
        (0, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 201),  # EDITOR of org
        (1, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 201),  # ADMIN of org
        (2, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 201),  # Superadmin
        (1, "ab851a83-a384-3eb9-caf0-68db8125b067", "some_client", 403),  # Not a member of this org
        (4, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "wUtu4EuLSlstjasC", 403),  # Provider admin - not an org member
        (6, "552376ae-2aa7-98ab-d800-68daa9bfeb4a", "some_client", 500),  # Integrity error: org role + provider admin
    ],
)
def test_reporting_org_authorise_tool_permissions(
    user: int, reporting_org_id: str, client_id: str, status_code: int
) -> None:
    """Only users belonging to the org, or superadmins, may authorise a tool for it.

    Provider admins (user 4) are deliberately excluded: although they can act on an org
    through their tool, they do not belong to the org and so must not be able to authorise
    further tools.  Tool Two is used because it is not authorised for any org, so each
    request exercises the permission check rather than the already-authorised path.
    """

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    tool_two_id = str(appAndContext._mocked_tool_ids[1])

    with TestClient(fastAPIapp) as client:
        response = client.post(
            f"/api/v1/reporting-orgs/{reporting_org_id}/tools",
            headers=appAndContext.get_valid_authorization_header(user, client_id=client_id),
            json={"tid": tool_two_id},
        )

        assert response.status_code == status_code


def test_reporting_org_authorise_tool_already_authorised() -> None:
    """Authorising a tool that is already authorised for the org returns 409 Conflict."""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    # Tool One is already authorised for org 552376ae-2aa7-98ab-d800-68daa9bfeb4a.
    org_id = "552376ae-2aa7-98ab-d800-68daa9bfeb4a"
    tool_one_id = str(appAndContext._mocked_tool_ids[0])

    with TestClient(fastAPIapp) as client:
        response = client.post(
            f"/api/v1/reporting-orgs/{org_id}/tools",
            headers=appAndContext.get_valid_authorization_header(1),  # ADMIN of org
            json={"tid": tool_one_id},
        )

        assert response.status_code == 409
        assert response.json()["status"] == "failed"


def test_reporting_org_authorise_tool_nonexistent() -> None:
    """Authorising a tool that does not exist returns 404 Not Found."""

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    org_id = "552376ae-2aa7-98ab-d800-68daa9bfeb4a"
    nonexistent_tool_id = "00000000-0000-0000-0000-000000000000"

    with TestClient(fastAPIapp) as client:
        response = client.post(
            f"/api/v1/reporting-orgs/{org_id}/tools",
            headers=appAndContext.get_valid_authorization_header(1),  # ADMIN of org
            json={"tid": nonexistent_tool_id},
        )

        assert response.status_code == 404
        assert response.json()["status"] == "failed"
