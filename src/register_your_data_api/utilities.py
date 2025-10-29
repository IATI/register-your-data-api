import uuid
from typing import Any, Callable

from libsuitecrm import Filter, SuiteCRM  # type: ignore

from .util import Context


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
    results = crm.get_records(module, filters=filters, fields=[])
    return "data" in results and len(results["data"]) == 1


def perform_undo_actions(
    context: Context, undo_actions: list[tuple[str, Callable[[], Any]]], func_name: str
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

    error_id = uuid.uuid4()

    context.app_logger.exception(f"Unexpected error in {func_name}. Error trace id: {error_id}")

    while undo_actions:
        (undo_msg, undo_func) = undo_actions.pop()
        context.app_logger.error(f"For error id {error_id} running undo action: {undo_msg}")
        undo_func()

    return error_id
