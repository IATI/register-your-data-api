import json

import pytest
from fastapi.testclient import TestClient

from ..helpers.mocking import MockedAppAndContext


@pytest.mark.parametrize(
    "user,response_file,reporting_org_id,reporting_org_short_name,has_meta",
    [
        (
            1,
            "get_records_reporting_orgs_01_org_1_no_meta.json",
            "552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            "aid-agency-01",
            False,
        ),
        (
            1,
            "get_records_reporting_orgs_02_org_1_with_meta.json",
            "552376ae-2aa7-98ab-d800-68daa9bfeb4a",
            "aid-agency-01",
            True,
        ),
    ],
)
def test_reporting_orgs_lists_correct_user_to_org_associations(
    user: int, response_file: str, reporting_org_id: str, reporting_org_short_name: str, has_meta: bool
) -> None:

    # TODO: add test case cover Person One (user index 0) who is associated with two reporting orgs
    # Not currently added as parameter set because this fails on SuiteCRM and so I haven't pulled
    # correct response format.

    # TODO: consume 'has_meta' flag to check additional fields are set when that is True

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    appAndContext.set_suitecrm_mocked_response_file(response_file)

    with TestClient(fastAPIapp) as client:
        response = client.get("/api/v1/reporting-orgs", headers=appAndContext.get_valid_authorization_header(user))

        assert response.status_code == 200
        resp_as_object = json.loads(response.content)

        assert resp_as_object["data"][0]["id"] == reporting_org_id
        assert resp_as_object["data"][0]["metadata"]["short_name"] == reporting_org_short_name


@pytest.mark.skip
def test_reporting_org_detail_user_has_access() -> None:
    pass


@pytest.mark.skip
def test_reporting_org_detail_user_not_allowed() -> None:
    pass


@pytest.mark.skip
def test_reporting_org_detail_no_reporting_org() -> None:
    pass
