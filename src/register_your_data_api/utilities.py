from libsuitecrm import Filter, SuiteCRM  # type: ignore


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
