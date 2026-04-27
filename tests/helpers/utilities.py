import datetime
import secrets
import string
import uuid
from typing import Any

from register_your_data_api.auth.fga.models import FineGrainedAuthorisationRoleAssociation


def find_record_in_response(resp_as_object: dict[str, Any], record_id: str) -> dict[str, Any] | None:
    """Finds a record with the given ID in the response object."""
    records: list[dict[str, Any]] = resp_as_object["data"]
    for record in records:
        if record["id"] == record_id:
            return record
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


def gen_random_client_id(size: int = 16) -> str:
    """Generates a random client ID"""
    return "".join([secrets.choice(string.ascii_letters + string.digits) for _ in range(size)])


def association_lists_equal_ignore_id(
    assocs1: list[FineGrainedAuthorisationRoleAssociation], assocs2: list[FineGrainedAuthorisationRoleAssociation]
) -> bool:
    """Test two lists of FineGrainedAuthorisationRoleAssociations are equal (excluding ids)

    Parameters
    ----------
    assocs1 : list[FineGrainedAuthorisationRoleAssociation]
        First list of associations.
    assocs2 : list[FineGrainedAuthorisationRoleAssociation]
        Second list of associations.

    Returns
    -------
    bool
    """

    _a1 = [x.model_dump(exclude={"id"}) for x in assocs1]
    _a2 = [x.model_dump(exclude={"id"}) for x in assocs2]

    def _sortfun(x: dict[str, uuid.UUID | str | None]) -> str:
        return str(x["user"]) + str(x["reporting_org"]) + str(x["role"]) + str(x["restricted_to_tool"])

    _a1.sort(key=_sortfun)
    _a2.sort(key=_sortfun)

    return _a1 == _a2
