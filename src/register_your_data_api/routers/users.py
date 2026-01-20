"""Implementation for /users end points"""

import uuid
from typing import Any, Callable

import fastapi
import starlette.requests
from fastapi import Depends, Security
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from libsuitecrm import SuiteCRM  # type: ignore

from register_your_data_api.dependencies import get_suitecrm_audit_headers

from ..auth import authz
from ..auth.fga import models as fga_models
from ..auth.models import UserAndCredentials
from ..data_handling.converters import get_fga_role_from_str
from ..data_handling.data_schemas import (
    OrganisationId,
    UserRoleUpdateModel,
)
from ..util import Context
from ..utilities import (
    assert_precondition_met,
    check_crm_record_exists,
    find_item_in_suitecrm_response,
    perform_undo_actions,
)

router = fastapi.APIRouter(prefix="/api/v1/users")


@router.post("/{user_id}/reporting-org")
def add_user_to_reporting_org(
    user_id: uuid.UUID,
    payload: OrganisationId,
    request: starlette.requests.Request,
    user: UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:user"]),
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
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
    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    if not check_crm_record_exists(crm, "Accounts", payload.oid):
        raise HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail=f"There is no organisation with ID {payload.oid} in the Registry.",
        )

    undo_actions: list[tuple[str, Callable[[], Any]]] = []

    try:
        # 1. Create a relationship between the current user (Contacts) and the
        crm.create_relationship(
            "Accounts", payload.oid, "contacts", "Contacts", user.user_id_crm, headers=suitecrm_audit_headers
        )
        undo_msg = f"delete relationship between organisation id: {payload.oid} and user id: {user.user_id_crm}"
        undo_func: Callable[[], Any] = lambda: crm.delete_relationship(
            "Accounts", payload.oid, "contacts", user.user_id_crm, headers=suitecrm_audit_headers
        )
        undo_actions.append((undo_msg, undo_func))

        # 2. Create a fine-grained authorisation for this user to be CONTRIBUTOR of new reporting_org
        user_reporting_org_role = fga_models.FineGrainedAuthorisationRoleAssociation(
            user=uuid.UUID(user.user_id_crm),
            reporting_org=uuid.UUID(payload.oid),
            role=fga_models.FineGrainedAuthorisationRole.CONTRIBUTOR_PENDING,
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
    new_role: UserRoleUpdateModel,
    request: starlette.requests.Request,
    user: UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:user:update"]),
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
) -> JSONResponse:
    """Updates a user's role within a reporting organization"""

    context: Context = request.app.state.context

    # 1. Check if the requesting user has permission to update roles for this org
    assert_precondition_met(
        context,
        condition_func=lambda: user.validator.user_can_modify_user_roles_for_reporting_org(org_id),
        status_code=fastapi.status.HTTP_403_FORBIDDEN,
        public_msg=(
            "There is a problem with your credentials. If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry."
        ),
        audit_log_msg=(
            f"Request to change user id: {user_id}'s role in organisation with id: {org_id} "
            f"by unauthorised user with id: {user.user_id_crm}"
        ),
    )

    # Get SuiteCRM client and validate entities exist
    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    # 2. Check that the target user exists in CRM
    assert_precondition_met(
        context,
        condition_func=lambda: check_crm_record_exists(crm, "Contacts", str(user_id)),
        public_msg=f"There is no user with ID {str(user_id)} in the Registry.",
        status_code=fastapi.status.HTTP_400_BAD_REQUEST,
        app_log_msg=(
            f"User with id: {user.user_id_crm} attempted to change user id: {user_id}'s role "
            f"in organisation with id: {org_id} but user with id: {user_id} does not exist in CRM."
        ),
    )

    # 3. Check that the target user exists in the identity service
    # TODO: Implement

    # 4. Check that the reporting org exists in CRM
    assert_precondition_met(
        context,
        condition_func=lambda: check_crm_record_exists(crm, "Accounts", str(org_id)),
        public_msg=f"There is no organisation with ID {str(org_id)} in the Registry.",
        status_code=fastapi.status.HTTP_400_BAD_REQUEST,
        app_log_msg=(
            f"User with id: {user.user_id_crm} attempted to change user id: {user_id}'s role "
            f"in organisation with id: {org_id} but organisation with id {org_id} does not exist in CRM."
        ),
    )

    # 5. Check that the user to be modified is not a superadmin - this is important to do since, if the following
    # code does not find a relationship between the target user and the reporting org in the CRM, or a role
    # in the FGA database, it will try to create them, but this must not be allowed for superadmins
    assert_precondition_met(
        context,
        condition_func=lambda: not context.fine_grained_auth_provider.is_user_a_superadmin(user_id),
        public_msg=f"User id: {user_id} cannot be given a role in no organisation with ID {str(org_id)}.",
        status_code=fastapi.status.HTTP_400_BAD_REQUEST,
        app_log_msg=(
            f"User with id: {user.user_id_crm} attempted to change user id: {user_id}'s role "
            f"in organisation with id: {org_id} but user with id: {user_id} is a superadmin."
        ),
    )

    # 6. Check that the target user and reporting org are related in CRM
    users_for_org_from_suitecrm = crm.get_relationship("Accounts", str(org_id), "Contacts")

    user_related_to_org_in_crm = find_item_in_suitecrm_response(users_for_org_from_suitecrm, str(user_id))

    if user_related_to_org_in_crm is None:
        context.app_logger.error(
            f"Unexpected error: user with id: {user.user_id_crm} attempted to change user id: {user_id}'s role in "
            f"organisation with id: {org_id} but the user is not associated with the organisation in the CRM. "
            "Creating relationship in the CRM."
        )
        try:
            crm.create_relationship(
                "Accounts", str(org_id), "contacts", "Contacts", str(user_id), headers=suitecrm_audit_headers
            )
        except Exception as e:
            context.app_logger.exception(
                "Exception encountered when attempting to create the relationship in the CRM between "
                f"user id: {user_id} and organisation id: {org_id} failed with error: {str(e)}"
            )
            raise HTTPException(
                status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="There was a problem processing your request. Please contact support.",
            )

    # 7. Check whether there is an existing FGA entry for this user and reporting org
    user_role_for_org = context.fine_grained_auth_provider.get_user_role_for_org(user_id, org_id)

    if user_role_for_org is None:
        context.app_logger.error(
            f"Unexpected error: user with id: {user.user_id_crm} attempted to change user id: {user_id}'s role in "
            f"organisation with id: {org_id} but the user has no entry in the FGA DB for this organisation. "
            "Creating new entry in the FGA database."
        )

        user_role_for_org = fga_models.FineGrainedAuthorisationRoleAssociation(
            user=user_id,
            reporting_org=org_id,
            role=get_fga_role_from_str(new_role.role),
        )

        context.fine_grained_auth_provider.create_user_fine_grained_authorisation(user_role_for_org)

        return JSONResponse({"data": None, "error": None, "status": "success"}, 200)

    # Don't update if the role is the same
    if str(user_role_for_org.role.name) == new_role.role.upper():
        return JSONResponse({"data": None, "error": None, "status": "success"}, 200)

    # 8. Update the user's role in the FGA database
    # This is safe as new_role has been validated by Pydantic
    user_role_for_org.role = get_fga_role_from_str(new_role.role)

    context.fine_grained_auth_provider.update_user_role_for_org(user_role_for_org)

    context.audit_logger.info(
        f"Request to change user id: {user_id}'s role for organisation with id: {org_id} "
        f"to '{new_role.role}' by authorised user with id: {user.user_id_crm} succeeded."
    )

    return JSONResponse({"data": None, "error": None, "status": "success"}, 200)


@router.delete("/{user_id}/reporting-org/{org_id}")
def remove_user_from_reporting_org(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:user:update"]),
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
) -> JSONResponse:
    """Removes a user's role in a reporting organization"""

    context: Context = request.app.state.context

    # 1. Check if the requesting user has permission to update roles for this org
    assert_precondition_met(
        context,
        condition_func=lambda: user.validator.user_can_modify_user_roles_for_reporting_org(org_id),
        status_code=fastapi.status.HTTP_403_FORBIDDEN,
        public_msg=(
            "There is a problem with your credentials. If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry."
        ),
        audit_log_msg=(
            f"Request to remove user id: {user_id}'s role in organisation with id: {org_id} "
            f"by unauthorised user with id: {user.user_id_crm}"
        ),
    )

    # Get SuiteCRM client and validate entities exist
    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    # 2. Check that the target user exists in CRM
    assert_precondition_met(
        context,
        condition_func=lambda: check_crm_record_exists(crm, "Contacts", str(user_id)),
        public_msg=f"There is no user with ID {str(user_id)} in the Registry.",
        status_code=fastapi.status.HTTP_400_BAD_REQUEST,
        app_log_msg=(
            f"User with id: {user.user_id_crm} attempted to remove user id: {user_id}'s role "
            f"in organisation with id: {org_id} but user with id: {user_id} does not exist in CRM."
        ),
    )

    # 3. Check that the reporting org exists in CRM
    assert_precondition_met(
        context,
        condition_func=lambda: check_crm_record_exists(crm, "Accounts", str(org_id)),
        public_msg=f"There is no organisation with ID {str(org_id)} in the Registry.",
        status_code=fastapi.status.HTTP_400_BAD_REQUEST,
        app_log_msg=(
            f"User with id: {user.user_id_crm} attempted to change user id: {user_id}'s role "
            f"in organisation with id: {org_id} but organisation with id {org_id} does not exist in CRM."
        ),
    )

    user_role_for_org = context.fine_grained_auth_provider.get_user_role_for_org(user_id, org_id)

    assert_precondition_met(
        context,
        condition_func=lambda: user_role_for_org is not None,
        public_msg=f"User id: {user_id} has no role in organisation with id: {str(org_id)} in the Registry.",
        status_code=fastapi.status.HTTP_400_BAD_REQUEST,
        audit_log_msg=(
            f"Unexpected error: user with id: {user.user_id_crm} attempted to remove user id: {user_id}'s role in "
            f"organisation with id: {org_id} but the user has no entry in the FGA DB for this organisation. "
        ),
    )

    # 4. Delete the user's role in the FGA database
    try:
        context.fine_grained_auth_provider.delete_user_role_for_org(user_role_for_org)  # type: ignore

        context.audit_logger.info(
            f"Request to remove user id: {user_id}'s role for organisation with id: {org_id} "
            f"by authorised user with id: {user.user_id_crm} succeeded."
        )
    except Exception:
        context.app_logger.exception(
            f"Request to remove user id: {user_id}'s role for organisation with id: {org_id} "
            f"by authorised user with id: {user.user_id_crm} failed."
        )

        raise HTTPException(
            fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"There was a problem removing the user's role for organisation with id: {org_id}. "
                "Please contact support.",
            ),
        )

    return JSONResponse({"data": None, "error": None, "status": "success"}, 200)
