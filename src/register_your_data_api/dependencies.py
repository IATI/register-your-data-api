import starlette.requests
from fastapi import Security

from register_your_data_api.auth import authz
from register_your_data_api.util import Context


def get_suitecrm_audit_headers(
    request: starlette.requests.Request,
    user: authz.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd"]),  # type: ignore
) -> dict[str, str]:
    """Get the set of custom headers for submitting a write-request to SuiteCRM"""

    context: Context = request.app.state.context

    client_app_details = context.get_client_application_details(user.client_id)

    return {
        "IATI-Person-ID": user.user_id_crm,
        "IATI-UserApplication-ID": client_app_details.application_id,
        "IATI-UserApplication-Name": client_app_details.application_name,
    }
