import json
from typing import Any

from libsuitecrm import Filter  # type: ignore


class MockSuiteCRM:

    def __init__(self) -> None:
        pass

    def fetch_access_token(self) -> None:
        pass

    def set_response_file(self, response_file: str) -> None:
        self._response_file = response_file

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

        response = {}

        try:
            with open(f"tests/artefacts/suitecrm-mocked-responses/{self._response_file}", "r") as file:
                content = file.read()
                response = json.loads(content)
        except AttributeError:
            raise RuntimeError("You must call set_response_file() to set up the mocked response")

        return response
