import glob
import json
import os
import uuid
from typing import Any

from libsuitecrm import Filter  # type: ignore

from ..utilities import get_current_timestamp_as_str


class MockSuiteCRM:
    """Mock of the SuiteCRM library.

    It currently supports:
    - get_records()   - the ID is accepted as normal parameter, and the data returns is read from
                        appropriate file in tests/artefacts/suitecrm-mocked-responses
    - create_record() - it just returns the data it was passed in the format returned by SuiteCRM
    - update_record() - for IATI_Datasets it returns the data it was passed, in the format returned by SuiteCRM
    """

    def __init__(self) -> None:
        pass

    def fetch_access_token(self) -> None:
        pass

    def logout(self) -> None:
        pass

    def set_response_file(self, response_file: str) -> None:
        self._response_file = response_file

    def get_filter_value(self, filters: Filter, q: str, default: str) -> str:
        v = default
        for operator in filters._operations if filters is not None else []:
            if operator[0] == q:
                v = operator[1]
        return v

    def get_records(  # noqa: C901
        self,
        module_name: str,
        fields: list[str] | None = None,
        page_number: int | None = None,
        page_size: int | None = None,
        sort_dir: str = "ascending",
        sort_field: str | None = None,
        filters: Filter | None = None,
    ) -> Any:

        file = ""
        response: dict[str, Any] = {"data": []}

        if module_name == "Accounts":
            reporting_org_id = self.get_filter_value(filters, "filter[id][eq]", "empty")

            file = f"tests/artefacts/suitecrm-mocked-responses/get_records_reporting_orgs_{reporting_org_id}.json"

        elif module_name == "IATI_Datasets":

            reporting_org_id = self.get_filter_value(filters, "filter[iati_dataset_owner_org_id][eq]", "empty")
            dataset_id = self.get_filter_value(filters, "filter[id][eq]", "empty")

            # If we are provided with a dataset id to find then we have to parse all
            # the JSON responses for datasets (one response file per reporting org)
            # and find the requested id.  If it is found we put it directly in the response.
            if reporting_org_id == "empty" and dataset_id != "empty":
                for dataset_file in glob.glob(
                    "tests/artefacts/suitecrm-mocked-responses/get_records_datasets_for_ro_*.json"
                ):
                    try:
                        fh = open(dataset_file, "r")
                        for data in json.load(fh).get("data", []):
                            if data["type"] == "IATI_Dataset" and data["id"] == dataset_id:
                                response["data"].append(data)
                        fh.close()
                    except Exception:
                        raise RuntimeError(
                            "Unexpected error loading mocked SuiteCRM response from file {dataset_file}"
                        )

            else:
                file = f"tests/artefacts/suitecrm-mocked-responses/get_records_datasets_for_ro_{reporting_org_id}.json"

        elif module_name == "Contacts":

            contact_id = self.get_filter_value(filters, "filter[id][eq]", "empty")

            file = f"tests/artefacts/suitecrm-mocked-responses/get_records_contact_{contact_id}.json"

        else:

            file = f"tests/artefacts/suitecrm-mocked-responses/{self._response_file}"

        if not os.path.isfile(file):
            file = "tests/artefacts/suitecrm-mocked-responses/get_records_empty.json"

        if not response["data"]:
            try:
                with open(file, "r") as fh:
                    content = fh.read()
                    response = json.loads(content)
            except Exception:
                raise RuntimeError("Unexpected error loading mocked SuiteCRM response from file {file}")

        return response

    def create_record(
        self, module_name: str, data: dict[str, Any], headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        if "IATI_Dataset" in module_name:
            return {
                "id": str(uuid.uuid4()),
                "type": "IATI_Datasets",
                "attributes": {"iati_url_update_date": "", "iati_metadata_update_date": "", **data},
            }
        elif "Account" in module_name:
            return {
                "id": str(uuid.uuid4()),
                "attributes": {
                    "created_date": get_current_timestamp_as_str(),
                    "first_publication_date": "",
                    "registry_approved": "0",
                    "iati_url_update_date": "",
                    "iati_metadata_update_date": "",
                    **data,
                },
            }

        return {}

    def update_record(
        self, module_name: str, id: str, data: dict[str, Any], headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        if "IATI_Dataset" in module_name:
            return {
                "id": id,
                "type": "IATI_Datasets",
                "attributes": {"iati_url_update_date": "", "iati_metadata_update_date": "", **data},
            }

        return {}

    def delete_record(self, module_name: str, id: str, headers: dict[str, str] | None = None) -> None:
        return None

    def create_relationship(
        self,
        module_name: str,
        record_id: str,
        link_field_name: str,
        related_module_name: str,
        related_id: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        return None

    def get_relationship(
        self,
        module_name: str,
        id: str,
        link_field_name: str,
        sort_field: str | None = None,
        sort_dir: str = "ascending",
        page_number: int | None = None,
        page_size: int | None = None,
        filters: Filter | None = None,
    ) -> Any:

        response = None

        file = f"tests/artefacts/suitecrm-mocked-responses/get_relationship_{module_name.lower()}_id_{id}.json"
        if os.path.isfile(file):
            with open(file, "r") as fh:
                content = fh.read()
                response = json.loads(content)
        else:
            raise NotImplementedError()

        return response

    def delete_relationship(
        self, module_name: str, id: str, link_field_name: str, related_id: str, headers: dict[str, str] | None = None
    ) -> None:
        return None
