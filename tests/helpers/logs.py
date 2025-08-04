import io

import register_your_data_api.util as util


def get_last_audit_log_string(context: util.Context) -> str:
    """Return the last audit log string from a string buffer file handler

    Trims empty lines and just returns the last non-empty line.  If we
    don't find a non-empty line we just return an empty string.

    Parameters
    ----------
    context : util.Context
        Context containing the required audit log file handler.

    Returns
    -------
    str

    Raises
    ------
    ValueError
        If the context object does not have a string buffer file handler for its audit log.
    """

    if not isinstance(context._audit_log_file_handler.stream, io.StringIO):
        raise ValueError("Audit log file handler is not a StringIO object")

    lines: list[str] = context._audit_log_file_handler.stream.getvalue().split("\n")
    lines.reverse()
    for line in lines:
        if not line == "":
            return line

    return ""
