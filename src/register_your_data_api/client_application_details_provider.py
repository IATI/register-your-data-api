from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, TypeAdapter


def check_uuid(v: str) -> str:
    try:
        UUID(v)
    except ValueError:
        raise ValueError("Invalid UUID string")
    return v


UUIDStr = Annotated[str, AfterValidator(check_uuid)]


class ClientApplicationDetails(BaseModel):
    client_id: str = Field(min_length=1)
    application_id: UUIDStr
    application_name: str


class ClientApplicationDetailsProvider:

    _CLIENT_APPLICATION_DETAILS: dict[str, ClientApplicationDetails] = {}

    def __init__(self, filename: str) -> None:
        """Initializes the provider by loading client application details from a JSON file."""

        try:
            with open(filename, "r") as file:
                data = file.read()
                type_adapter = TypeAdapter(list[ClientApplicationDetails])
                client_app_details_list = type_adapter.validate_json(data)

                for app_details in client_app_details_list:
                    if app_details.client_id in self._CLIENT_APPLICATION_DETAILS:
                        raise RuntimeError(f"Duplicate client_id found in {filename}: {app_details.client_id}")
                    self._CLIENT_APPLICATION_DETAILS[app_details.client_id] = app_details

        except Exception as e:
            raise RuntimeError(f"Failed to load client application details from {filename}: {e}")

    def get_client_application_details(self, client_id: str) -> ClientApplicationDetails:
        """Retrieves details about the client application given its client ID."""

        if client_id not in self._CLIENT_APPLICATION_DETAILS:
            raise ValueError("Unknown client application")

        return self._CLIENT_APPLICATION_DETAILS[client_id]
