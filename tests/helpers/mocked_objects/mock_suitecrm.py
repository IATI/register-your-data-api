import json
import os
import uuid
from typing import Any

from libsuitecrm import Filter  # type: ignore

from register_your_data_api.data_handling.domain_logic import get_reporting_org_fields_to_fetch

from ..utilities import get_current_timestamp_as_str


class MockSuiteCRM:
    """Mock of the SuiteCRM library.

    It currently supports:
    - get_records()   - the ID is accepted as normal parameter, and the data returns is read from
                        appropriate file in tests/artefacts/suitecrm-mocked-responses
    - create_record() - it just returns the data it was passed in the format returned by SuiteCRM
    """

    def __init__(self) -> None:
        pass

    def fetch_access_token(self) -> None:
        pass

    def set_response_file(self, response_file: str) -> None:
        self._response_file = response_file

    def get_filter_value(self, filters: Filter, q: str, default: str) -> str:
        v = default
        for operator in filters._operations if filters is not None else []:
            if operator[0] == q:
                v = operator[1]
        return v

    def get_records(
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
        error_message = ""
        response = {"data": []}  # type: dict[str, Any]

        if module_name == "Accounts":
            num_fields_no_meta = len(get_reporting_org_fields_to_fetch(False))

            meta = "no_meta" if fields is None or len(fields) == num_fields_no_meta else "with_meta"

            reporting_org_id = self.get_filter_value(filters, "filter[id][eq]", "empty")

            file = (
                f"tests/artefacts/suitecrm-mocked-responses/get_records_reporting_orgs_{reporting_org_id}_{meta}.json"
            )
            error_message = f"There is no mocked SuiteCR Mresponse for reporting org ID {reporting_org_id}"

        elif module_name == "IATI_Datasets":

            reporting_org_id = self.get_filter_value(filters, "filter[iati_dataset_owner_org_id][eq]", "empty")

            file = f"tests/artefacts/suitecrm-mocked-responses/get_records_datasets_for_ro_{reporting_org_id}.json"
            error_message = f"There is no mocked SuiteCR Mresponse for reporting org ID {reporting_org_id}"

        else:

            file = f"tests/artefacts/suitecrm-mocked-responses/{self._response_file}"
            error_message = "You must call set_response_file() to set up the mocked response"

        try:
            if os.path.isfile(file):
                with open(file, "r") as fh:
                    content = fh.read()
                    response = json.loads(content)
        except AttributeError:
            raise RuntimeError(error_message)

        return response

    def create_record(self, module_name: str, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "attributes": {
                "created_date": get_current_timestamp_as_str(),
                "first_publication_date": "",
                "registry_approved": "0",
                **data,
            },
        }
