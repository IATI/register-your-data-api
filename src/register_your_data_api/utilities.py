import uuid
from typing import Any, Callable

from libsuitecrm import Filter, SuiteCRM  # type: ignore

from .auth.models import UserAndCredentials
from .exceptions import RYDUserException
from .util import Context


def assert_precondition_met(
    user: UserAndCredentials,
    condition_func: Callable[[], bool],
    public_msg: str,
    status_code: int,
    app_log_msg: str | None = None,
    audit_log_msg: str | None = None,
) -> None:
    """Asserts that a precondition is met, else raises an exception

    Parameters
    ----------
    user : UserAndCredentials
        The user and details about their credentials performing the action
    condition_func : Callable[[], bool]
        A function that returns True if the precondition is met
    public_msg : str
        The message to include in the exception if the precondition is not met
    status_code : int
        The HTTP status code to include in the exception if the precondition is not met
    app_log_msg : str | None, optional
        The application log message to include in the exception if the precondition is not met, by default None
    audit_log_msg : str | None, optional
        The audit log message to include in the exception if the precondition is not met, by

    Raises
    ------
    RYDUserException
        If the precondition is not met
    """
    if not condition_func():

        raise RYDUserException(
            user=user,
            status_code=status_code,
            app_msg=app_log_msg,
            audit_msg=audit_log_msg,
            public_msg=public_msg,
        )


def find_item_in_suitecrm_response(
    r: dict[str, Any] | None, id: str | None, id_field: str = "id"
) -> dict[str, Any] | None:
    """Finds an item with the specified id in a SuiteCRM response

    Parameters
    ----------
    r : dict[str, Any]
        The SuiteCRM response dictionary
    id : str
        The id to search for
    id_field : str, optional
        The field name to match the id against, by default "id"

    Returns
    -------
    dict[str, Any] | None
        The found item dictionary, or None if not found
    """
    if r is None:
        return None
    return next((item for item in r.get("data", []) if item.get(id_field) == id), None)


def check_crm_record_exists(crm: SuiteCRM, module: str, id: str) -> bool:
    """Checks if a record exists in the CRM module 'module' with id = 'id'

    Parameters
    ----------
    module : str
        The module name on SuiteCRM
    id : str
        The id of the record to check the existence of (UUID as str)

    Returns
    -------
    bool
        True if the record exists
    """
    filters = Filter()
    filters.equal("id", id)
    results = crm.get_records(module, filters=filters, fields=["id"])
    return "data" in results and len(results["data"]) == 1


def get_num_crm_records(crm: SuiteCRM, module: str, field_value_pairs: dict[str, Any]) -> int:
    """Gets the number of records from a specified module matching the criterion specified

    Parameters
    ----------
    module : str
        The module name on SuiteCRM
    field_value_pairs : dict[str, str]
        A dictionary containing the fields and their associated values to filter on.

    Returns
    -------
    int
        The number of matching records
    """
    filters = Filter()
    for field, value in field_value_pairs.items():
        filters.equal(field, value)
    results = crm.get_records(module, filters=filters, fields=["id"])
    return len(results["data"]) if "data" in results else 0


def perform_undo_actions(
    context: Context,
    undo_actions: list[tuple[str, Callable[[], Any]]],
    func_name: str,
    trace_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Runs the set of undo actions

    Parameters
    ----------
    context : Context
        The application context
    undo_actions : list[tuple[str, Callable[[], Any]]]
        A list of undo actions to perform. Each action is a tuple of (description, function)
    func_name : str
        The name of the function where the error occurred

    Returns
    -------
    uuid.UUID
        The error trace ID for the logged exception
    """

    error_id = uuid.uuid4() if trace_id is None else trace_id

    context.app_logger.exception(f"Unexpected error in {func_name}. Error trace id: {error_id}")

    while undo_actions:
        (undo_msg, undo_func) = undo_actions.pop()
        context.app_logger.error(f"For error id {error_id} running undo action: {undo_msg}")
        undo_func()

    return error_id
