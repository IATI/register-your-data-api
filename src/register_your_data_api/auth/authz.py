from uuid import UUID

import starlette.requests
from fastapi import Security

from ..util import Context  # noqa
from .authn import parse_decoded_token
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

    users_fgas = context.fine_grained_auth_provider.get_user_fine_grained_permissions(current_user_id)

    is_superadmin = context.fine_grained_auth_provider.is_user_a_superadmin(current_user_id)

    user.fga_user_validator = FineGrainedAuthorisationUserValidator(
        user_id=current_user_id, fine_grained_authorisations=users_fgas, is_superadmin=is_superadmin
    )

    return user
