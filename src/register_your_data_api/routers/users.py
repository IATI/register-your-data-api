"""Implementation for /users end points"""

import uuid
from typing import Any, Callable

import fastapi
import starlette
from fastapi import Security
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from libsuitecrm import SuiteCRM  # type: ignore

from ..auth import authz
from ..auth.fga import models as fga_models
from ..auth.models import UserAndCredentials
from ..data_handling.data_schemas import (
    OrganisationId,
)
from ..util import Context
from ..utilities import check_crm_record_exists, perform_undo_actions

router = fastapi.APIRouter(prefix="/api/v1/users")


@router.post("/{user_id}/reporting-org")
def add_user_to_reporting_org(
    user_id: uuid.UUID,
    payload: OrganisationId,
    request: starlette.requests.Request,
    user: UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:user"]),
) -> JSONResponse:
    """Handles a request by the logged in user to be associated with the specified reporting_org"""

    context: Context = request.app.state.context

    user_id_to_add_as_str = str(user_id)

    if user_id_to_add_as_str != user.user_id_crm:
        context.audit_logger.error(
            f"Request to associate user with id: {user_id_to_add_as_str} to organisation with id: {payload.oid} "
            f"by user with non-matching id: {user.user_id_crm}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="You cannot request a different user be associated with a reporting organisation.",
        )

    # Superadmins shouldn't be allowed to request association with any organisations
    if user.validator.is_superadmin:
        raise HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail="Superadmins cannot associate themselves with organisations.",
        )

    # Query SuiteCRM to check that the reporting_org exists
    crm: SuiteCRM = context.get_suitecrm_client()

    crm.fetch_access_token()

    if not check_crm_record_exists(crm, "Accounts", payload.oid):
        raise HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail=f"There is no organisation with ID {payload.oid} in the Registry.",
        )

    undo_actions: list[tuple[str, Callable[[], Any]]] = []

    try:
        # 1. Create a relationship between the current user (Contacts) and the
        crm.create_relationship("Accounts", payload.oid, "contacts", "Contacts", user.user_id_crm)
        undo_msg = f"delete relationship between organisation id: {payload.oid} and user id: {user.user_id_crm}"
        undo_func: Callable[[], Any] = lambda: crm.delete_relationship(
            "Accounts", payload.oid, "contacts", user.user_id_crm
        )
        undo_actions.append((undo_msg, undo_func))

        # 2. Create a fine-grained authorisation for this user to be CONTRIBUTOR of new reporting_org
        # TODO: Change CONTRIBUTOR to CONTRIBUTOR_PENDING when that role is available
        #       which will be after alembic has been added to facilitate changes to to FGA models
        user_reporting_org_role = fga_models.FineGrainedAuthorisationRoleAssociation(
            user=uuid.UUID(user.user_id_crm),
            reporting_org=uuid.UUID(payload.oid),
            role=fga_models.FineGrainedAuthorisationRole.CONTRIBUTOR,
        )
        context.fine_grained_auth_provider.create_user_fine_grained_authorisation(user_reporting_org_role)

    except Exception:
        error_trace_id: uuid.UUID = perform_undo_actions(context, undo_actions, "add_user_to_reporting_org")

        raise HTTPException(
            fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"There was a problem requesting access to the organisation. Error id: {error_trace_id}",
        )

    return JSONResponse({"data": None, "error": None, "status": "success"}, 200)


@router.put("/{user_id}/reporting-org/{org_id}")
def update_user_role_in_reporting_org(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:user:update"]),
) -> JSONResponse:

    # check token has required scopes
    # check roles
    # get user ID from the access token (the requester, "sub")
    # make sure user {user_id} exists in CRM and identity service
    # make sure reporting org exists
    # make sure "sub" has the permissions to set user authz for this reporting org
    # make sure user {user_id} and reporting org are related in CRM
    # make sure user {user_id} has an FGA token in the identity service
    # update token in the identity service
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.delete("/{user_id}/reporting-org/{org_id}")
def remove_user_from_reporting_org(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:user:update"]),
) -> JSONResponse:
    # check token has required scopes
    # check roles
    # get user ID from the access token (the requester, "sub")
    # make sure user {user_id} exists in CRM and identity service
    # make sure reporting org exists
    # make sure "sub" has the permissions to set user authz for this reporting org
    # make sure user {user_id} and reporting org are related in CRM
    # make sure user {user_id} has an FGA token in the identity service
    # update token in the identity service
    # remove relationship between user and reporting org in the CRM
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )
