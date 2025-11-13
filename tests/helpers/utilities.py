import datetime
import uuid
from typing import Any


def find_record_in_response(resp_as_object: dict[str, Any], record_id: str) -> dict[str, Any] | None:
    """Finds a record with the given ID in the response object."""

    for record in resp_as_object["data"]:
        if record["id"] == record_id:
            return record  # type: ignore
    return None


def is_valid_uuid(s: str) -> bool:
    """Checks whether the given string is a valid UUID"""

    try:
        uuid.UUID(s)
    except ValueError:
        return False

    return True


def get_current_timestamp_as_str(format_with_z: bool = False) -> str:
    """Gets the current UTC timestamp in IS8601 format.

    Microseconds are zeroed.

    Keyword arguments:
    format_with_z -- If True, the standard '+00:00' for UTC is replaced with a Z.
        This is used for the CKAN metadata in the backwards compatible ZIP"""

    s = datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0).isoformat()

    if format_with_z:
        return s.replace("+00:00", "Z")

    return s
