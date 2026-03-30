from uuid import UUID, uuid4

import starlette.requests
from fastapi import Security

from register_your_data_api.exceptions import RYDUserException

from ..util import Context  # noqa
from .authn import parse_decoded_token
from .fga.fga_provider import FineGrainedAuthorisationIntegrityError
from .fga.fga_validator import FineGrainedAuthorisationUserValidator
from .models import UserAndCredentials


async def get_user_authnz(
    request: starlette.requests.Request,
    user: UserAndCredentials = Security(parse_decoded_token),
) -> UserAndCredentials:
    context = request.app.state.context  # type: Context

    if user.sub is None:
        raise RuntimeError  # TODO: handle in proper way

    current_user_id = UUID(user.user_id_crm)

    try:
        users_fgas = context.fine_grained_auth_provider.get_user_fine_grained_permissions(current_user_id)
    except FineGrainedAuthorisationIntegrityError as exc:
        trace_id: UUID = uuid4()
        raise RYDUserException(
            user.user_id_crm,
            user.client_id,
            500,
            app_msg=f"FGA Database integrity error with traceid={trace_id}",
            audit_msg=f"There is an integrity issue with the authorisations in the FGA databse {exc}.  "
            f"METHOD={request.method} URL={request.url} CLIENT={request.client} TRACE_ID={trace_id}",
            public_msg="There is a problem with your credentials.  Please report this error to the provider "
            f"of the tool you are using to access the IATI Registry quoting trace ID {trace_id}.",
        )

    is_superadmin = context.fine_grained_auth_provider.is_user_a_superadmin(current_user_id)

    user.fga_user_validator = FineGrainedAuthorisationUserValidator(
        user_id=current_user_id, fine_grained_authorisations=users_fgas, is_superadmin=is_superadmin
    )

    return user
