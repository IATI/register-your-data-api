import json

import pytest
from fastapi.testclient import TestClient

from ..helpers.mocking import MockedAppAndContext


@pytest.mark.parametrize(
    "invalid_short_name",
    [
        "invalid short name!",  # contains spaces and exclamation mark
        "invalid@name",  # contains special character '@'
        "name/with/slash",  # contains slash
        "name\\with\\backslash",  # contains backslash
        "name:with:colon",  # contains colon
        "name*with*asterisk",  # contains asterisk
        "name?with?question",  # contains question mark)
    ],
)
def test_dataset_create_with_invalid_short_name(invalid_short_name: str) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    new_dataset = {
        "human_readable_name": "Test Dataset 01",
        "licence_id": "cc-by",
        "owner_organisation_id": "552376ae-2aa7-98ab-d800-68daa9bfeb4a",
        "short_name": invalid_short_name,
        "source_type": "primary_source",
        "url": "http://www.example.com/dataset01",
        "visibility": "private",
    }

    with TestClient(fastAPIapp) as client:
        response = client.post(
            "/api/v1/datasets",
            headers=appAndContext.get_valid_authorization_header(0),
            content=json.dumps(new_dataset),
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
        "name?with?question",  # contains question mark)
        "nameWITH_UPPER_casecharacters",  # containers uppoer case chars
        "ALLUPPERNAME",  # all upper case chars
    ],
)
def test_dataset_update_with_invalid_short_name(invalid_short_name: str) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    dataset = {
        "human_readable_name": "Test Dataset 01",
        "licence_id": "cc-by",
        "owner_organisation_id": "552376ae-2aa7-98ab-d800-68daa9bfeb4a",
        "short_name": "valid_dataset_short_name",
        "source_type": "primary_source",
        "url": "http://www.example.com/dataset01",
        "visibility": "private",
    }

    with TestClient(fastAPIapp) as client:
        auth_header = appAndContext.get_valid_authorization_header(0)

        response_create = client.post(
            "/api/v1/datasets",
            headers=auth_header,
            content=json.dumps(dataset),
        )

        assert response_create.status_code == 201

        resp_create_obj = response_create.json()

        dataset["short_name"] = invalid_short_name

        response_update = client.patch(
            f"/api/v1/datasets/{resp_create_obj["data"]["id"]}",
            headers=auth_header,
            content=json.dumps(dataset),
        )

        assert response_update.status_code == 400

        response_obj = response_update.json()

        assert response_obj["status"] == "failed"


@pytest.mark.parametrize(
    "user,status_code",
    [
        (0, 403),  # Editor
        (1, 200),  # Admin
        (2, 200),  # Superadmin
        (3, 403),  # Contributor
        (4, 200),  # Provider admin
        (6, 500),  # Failure case, user is both provider admin and has an org role
    ],
)
def test_change_dataset_visibility(user: int, status_code: int) -> None:

    appAndContext = MockedAppAndContext()

    fastAPIapp = appAndContext.get_test_app()

    with TestClient(fastAPIapp) as client:

        # The dataset we try to patch is set to public in the suitecrm
        # artefacts, so here we try to change the visibility to private.
        response = client.patch(
            "/api/v1/datasets/52ac525f-6375-079b-977d-68ecf3be2868",
            headers=appAndContext.get_valid_authorization_header(user),
            content=json.dumps(
                {
                    "human_readable_name": "Aid Agency - Dataset 01",
                    "licence_id": "cc-zero",
                    "short_name": "aidagy-data-01",
                    "source_type": "primary_source",
                    "url": "http://aidagency.com/dataset-01.xml",
                    "visibility": "private",
                }
            ),
        )

        assert response.status_code == status_code
