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

    # Read the user's details from Asgardeo to get their SuiteCRM UUID
    # user.user_id_crm = context._crm_uuid_provider.get_crm_uuid(user)

    # Read the user's fine grained authorisations
    users_fgas = context.fine_grained_auth_provider.get_user_fine_grained_permissions(UUID(user.user_id_crm))

    is_superadmin = context.fine_grained_auth_provider.is_user_a_superadmin(UUID(user.user_id_crm))

    user.fga_user_validator = FineGrainedAuthorisationUserValidator(
        fine_grained_authorisations=users_fgas, is_superadmin=is_superadmin
    )

    return user
