"""Implementation for /reporting-orgs end points"""

import uuid
from typing import Any, Callable

import fastapi
import starlette
from fastapi import Depends, Security
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from libsuitecrm import Filter, RequestFailed, SuiteCRM  # type: ignore

from register_your_data_api.dependencies import get_suitecrm_audit_headers

from ..auth import authz
from ..auth import models as auth_models
from ..auth.fga import models as fga_models
from ..data_handling.converters import (
    SUITECRM_REPORTING_ORG_FIELDS,
    get_dataset_actions_from_suitecrm_response,
    get_dataset_list_from_suitecrm_response,
    get_discoverable_reporting_org_meta_from_suitecrm_response,
    get_fga_role_as_str,
    get_reporting_org_meta_from_suitecrm_response,
    get_suitecrm_dict_from_reporting_org,
)
from ..data_handling.data_schemas import (
    CRMUser,
    CRMUserListResponse,
    DatasetReadModel,
    DiscoverableReportingOrgMetadata,
    PaginationQueryParams,
    ReportingOrgAction,
    ReportingOrgCreateModel,
    ReportingOrgMetadata,
    ReportingOrgUpdateModel,
    ReportingOrgUserCreateModel,
    UserReportingOrgDiscoverableMetadataRelation,
    UserReportingOrgRelation,
    UserReportingOrgRelationSingleResponse,
)
from ..response_schemas import PaginatedResultsPage
from ..util import Context
from ..utilities import assert_precondition_met, check_crm_record_exists, get_num_crm_records, perform_undo_actions

router = fastapi.APIRouter(prefix="/api/v1/reporting-orgs")


@router.get("")
def get_reporting_orgs(
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org"]),
    paging: PaginationQueryParams = fastapi.Depends(),
    include_actions: str = "no",
) -> PaginatedResultsPage[UserReportingOrgRelation | UserReportingOrgDiscoverableMetadataRelation]:

    context: Context = request.app.state.context

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    try:
        orgs_for_user = crm.get_relationship(
            "Contacts",
            user.user_id_crm,
            "Accounts",
            page_number=paging.page,
            page_size=paging.page_size,
            sort_field="name",
            sort_dir="ascending",
            filters=Filter().equal("iati_registry_discoverable", "1"),
        )
    except RequestFailed as e:
        error_id = uuid.uuid4()
        public_error_message = (
            "There was a problem fetching the list of reporting orgs you are associated with. "
            f"Please try again later, or contact IATI Support quoting error id: {error_id}"
        )
        context.app_logger.error(
            f"Error: error id: {error_id} - user id: {user.user_id_crm} - GET /reporting-orgs - Problem when fetching "
            "the list of reporting organisations for this user from SuiteCRM. "
            f"Details: {str(e)}"
        )
        raise HTTPException(status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR, detail=public_error_message)

    total_records = orgs_for_user.get("meta", {}).get("total-records", 0)

    reporting_orgs_list: list[UserReportingOrgRelation | UserReportingOrgDiscoverableMetadataRelation] = []

    for reporting_org_from_suitecrm in orgs_for_user["data"]:
        role_for_org = user.validator.get_user_role_for_reporting_org(reporting_org_from_suitecrm["id"])

        if role_for_org is None:
            context.app_logger.info(
                f"Info: user id: {user.user_id_crm} - GET /reporting-orgs - user is associated with organisation "
                f"{reporting_org_from_suitecrm["id"]} in the CRM but has no role for that organisation in the FGA DB. "
                "Organisation was omitted from the list returned to the user."
            )
            continue

        reporting_org_obj: ReportingOrgMetadata | DiscoverableReportingOrgMetadata

        if role_for_org == fga_models.FineGrainedAuthorisationRole.CONTRIBUTOR_PENDING:
            reporting_org_obj = get_discoverable_reporting_org_meta_from_suitecrm_response(
                reporting_org_from_suitecrm["attributes"]
            )
        else:
            reporting_org_obj = get_reporting_org_meta_from_suitecrm_response(
                reporting_org_from_suitecrm["attributes"]
            )

        reporting_orgs_list.append(
            UserReportingOrgRelation(
                id=reporting_org_from_suitecrm["id"],
                user_role=get_fga_role_as_str(role_for_org),
                metadata=reporting_org_obj,
                reporting_org_actions=(
                    get_reporting_org_actions(crm, reporting_org_from_suitecrm["id"])
                    if include_actions == "yes"
                    else []
                ),
            )
        )

    reporting_orgs_list.sort(key=lambda org: org.metadata.human_readable_name.lower())

    return PaginatedResultsPage.create(reporting_orgs_list, paging.page, paging.page_size, total_records, request)


@router.get("/{org_id}")
def get_reporting_org_detail(
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org"]),
    include_actions: str = "no",
) -> UserReportingOrgRelationSingleResponse:

    context: Context = request.app.state.context

    if not user.validator.user_can_read_reporting_org(org_id):
        context.audit_logger.error(
            f"Request to get reporting org details for org id: {org_id} "
            f"by unauthorised user id: {user.user_id_crm}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    filters = Filter()
    filters.equal("id", str(org_id))
    filters.equal("iati_registry_discoverable", "1")

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    fields = SUITECRM_REPORTING_ORG_FIELDS

    crm_reporting_orgs = crm.get_records("Accounts", page_number=1, page_size=10, fields=fields, filters=filters)

    if len(crm_reporting_orgs["data"]) == 0:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"There is no organisation with ID {str(org_id)} in the Registry.",
        )

    reporting_org = get_reporting_org_meta_from_suitecrm_response(crm_reporting_orgs["data"][0]["attributes"])

    user_reporting_org_relation = UserReportingOrgRelation(
        id=str(org_id),
        user_role=get_fga_role_as_str(user.validator.get_user_role_for_reporting_org(org_id)),  # type: ignore
        metadata=reporting_org,
        reporting_org_actions=get_reporting_org_actions(crm, str(org_id)) if include_actions == "yes" else [],
    )

    return UserReportingOrgRelationSingleResponse(status="success", error=None, data=user_reporting_org_relation)


@router.post("", status_code=201)
def create_reporting_org(
    request: starlette.requests.Request,
    reporting_org: ReportingOrgUserCreateModel,
    user: auth_models.UserAndCredentials = Security(
        authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org", "ryd:reporting_org:create"]
    ),
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
) -> UserReportingOrgRelationSingleResponse:

    context: Context = request.app.state.context

    assert_precondition_met(
        context,
        condition_func=lambda: user.validator.user_can_create_reporting_org(),
        status_code=fastapi.status.HTTP_403_FORBIDDEN,
        audit_log_msg=(f"Request to create reporting org by unauthorised user id: {user.user_id_crm}"),
        public_msg=(
            "There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry."
        ),
    )

    undo_actions: list[tuple[str, Callable[[], Any]]] = []

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    # Check that the short name is unique
    assert_precondition_met(
        context,
        condition_func=lambda: get_num_crm_records(
            crm, "Accounts", {"iati_short_name": reporting_org.short_name, "iati_registry_discoverable": 1}
        )
        == 0,
        status_code=fastapi.status.HTTP_409_CONFLICT,
        audit_log_msg=(
            f"Request to create reporting org by user id: {user.user_id_crm} "
            f"with non-unique short name: {reporting_org.short_name}"
        ),
        public_msg=(
            "Unable to create reporting org as there is already a reporting org with short_name "
            f"'{reporting_org.short_name}' in the Registry."
        ),
    )

    try:
        # 1. Create the reporting on SuiteCRM
        reporting_org_to_create = ReportingOrgCreateModel(**reporting_org.model_dump())
        reporting_org_for_suitecrm = get_suitecrm_dict_from_reporting_org(reporting_org_to_create)
        suitecrm_reporting_org = crm.create_record(
            "Accounts", reporting_org_for_suitecrm, headers=suitecrm_audit_headers
        )
        new_reporting_org = get_reporting_org_meta_from_suitecrm_response(suitecrm_reporting_org["attributes"])
        undo_actions.append(
            (
                f"delete organisation with id: {suitecrm_reporting_org["id"]}",
                lambda: crm.delete_record("Accounts", suitecrm_reporting_org["id"], headers=suitecrm_audit_headers),
            )
        )

        # 2. Create a relationship between the current user (Contacts) and the
        # reporting org (Accounts) in SuiteCRM, but only if user is not
        # operating in the capacity as a super_admin
        if not user.validator.is_superadmin:
            crm.create_relationship(
                "Accounts",
                suitecrm_reporting_org["id"],
                "contacts",
                "Contacts",
                user.user_id_crm,
                headers=suitecrm_audit_headers,
            )
            undo_msg = (
                "delete relationship between organisation id: "
                f"{suitecrm_reporting_org["id"]} and user id: {user.user_id_crm}"
            )
            undo_func: Callable[[], Any] = lambda: crm.delete_relationship(
                "Accounts", suitecrm_reporting_org["id"], "contacts", user.user_id_crm, headers=suitecrm_audit_headers
            )
            undo_actions.append((undo_msg, undo_func))

        # 3. Create a fine-grained authorisation for this user to be ADMIN of new reporting_org
        user_reporting_org_role = fga_models.FineGrainedAuthorisationRoleAssociation(
            user=uuid.UUID(user.user_id_crm),
            reporting_org=uuid.UUID(suitecrm_reporting_org["id"]),
            role=fga_models.FineGrainedAuthorisationRole.ADMIN,
        )
        context.fine_grained_auth_provider.create_user_fine_grained_authorisation(user_reporting_org_role)

    except Exception:
        error_trace_id: uuid.UUID = perform_undo_actions(context, undo_actions, "create_reporting_org")

        raise HTTPException(
            fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"There was a problem creating the reporting org. Error id: {error_trace_id}",
        )

    user_reporting_org = UserReportingOrgRelation(
        id=suitecrm_reporting_org["id"],
        user_role=get_fga_role_as_str(fga_models.FineGrainedAuthorisationRole.ADMIN),
        metadata=new_reporting_org,
        reporting_org_actions=[],
    )

    return UserReportingOrgRelationSingleResponse(status="success", error=None, data=user_reporting_org)


@router.patch("/{org_id}")
def update_reporting_org(
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    updated_reporting_org: ReportingOrgUpdateModel,
    include_actions: str = "no",
    user: auth_models.UserAndCredentials = Security(
        authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org", "ryd:reporting_org:update"]
    ),
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
) -> UserReportingOrgRelationSingleResponse:

    context: Context = request.app.state.context

    if not user.validator.user_can_update_reporting_org(org_id):
        context.audit_logger.error(
            f"Request to update reporting org details for org id: {org_id} "
            f"by unauthorised user id: {user.user_id_crm}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    # 1. Query SuiteCRM to check that the reporting_org exists
    if not check_crm_record_exists(crm, "Accounts", str(org_id)):
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=f"There is no organisation with ID {str(org_id)} in the Registry.",
        )

    # 2. Make request to SuiteCRM to update reporting_org
    reporting_org_for_suitecrm = get_suitecrm_dict_from_reporting_org(updated_reporting_org)
    try:
        suitecrm_reporting_org = crm.update_record(
            "Accounts", str(org_id), reporting_org_for_suitecrm, headers=suitecrm_audit_headers
        )
        updated_reporting_org_from_suitecrm = get_reporting_org_meta_from_suitecrm_response(
            suitecrm_reporting_org["attributes"]
        )
    except Exception:
        error_id = uuid.uuid4()
        context.app_logger.exception(f"Unexpected error in update_reporting_org. Error trace id: {error_id}")
        public_error_message = f"There was a problem updating the reporting org. Error id: {error_id}"
        raise HTTPException(status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR, detail=public_error_message)

    user_reporting_org_relation = UserReportingOrgRelation(
        id=str(org_id),
        user_role=get_fga_role_as_str(user.validator.get_user_role_for_reporting_org(org_id)),  # type: ignore
        metadata=updated_reporting_org_from_suitecrm,
        reporting_org_actions=get_reporting_org_actions(crm, str(org_id)) if include_actions == "yes" else [],
    )

    return UserReportingOrgRelationSingleResponse(status="success", error=None, data=user_reporting_org_relation)


@router.delete("/{org_id}")
def delete_reporting_org(
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:delete"]),
    suitecrm_audit_headers: dict[str, str] = Depends(get_suitecrm_audit_headers),
) -> JSONResponse:

    context: Context = request.app.state.context

    # 1. Check that the user has permissions to delete (mark as not on RYD) the reporting org
    assert_precondition_met(
        context,
        condition_func=lambda: user.validator.user_can_delete_reporting_org(org_id),
        status_code=fastapi.status.HTTP_403_FORBIDDEN,
        audit_log_msg=(
            f"Request to delete reporting org for org id: {str(org_id)} "
            f"by unauthorised user id: {user.user_id_crm}"
        ),
        public_msg=(
            "There is a problem with your credentials. If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry."
        ),
    )

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    # 1. Query SuiteCRM to check that the reporting_org exists. We just fetch the item, because
    # we need to update it later on, and we need to know what its current state is for undo purposes.
    filters = Filter()
    filters.equal("id", org_id)
    crm_reporting_org = crm.get_records(
        "Accounts",
        page_number=1,
        page_size=1,
        fields=["id", "iati_registry_approved", "iati_registry_discoverable"],
        filters=filters,
    )

    assert_precondition_met(
        context,
        condition_func=lambda: len(crm_reporting_org["data"]) == 1,
        status_code=fastapi.status.HTTP_404_NOT_FOUND,
        public_msg=f"There is no organisation with ID {str(org_id)} in the Registry.",
        audit_log_msg=(
            f"Request to delete reporting org for org id: {str(org_id)} by user id: {user.user_id_crm} "
            f"but the orgganisation does not exist in SuiteCRM."
        ),
    )

    error_trace_id: uuid.UUID
    undo_actions: list[tuple[str, Callable[[], Any]]] = []

    try:
        # 2. Set iati_registry_approved and iati_registry_discoverable to 0
        crm.update_record("Accounts", str(org_id), {"iati_registry_approved": "0", "iati_registry_discoverable": "0"})

        # TODO: 2b. Set iati_registry_discoverable to False when that new field is
        # available on SuiteCRM.
        crm.update_record("Accounts", str(org_id), {"iati_registry_approved": False})

        if crm_reporting_org["data"][0].get("attributes", {}).get("iati_registry_approved") is True:
            # Only need to add undo action if the field was previously True
            undo_actions.append(
                (
                    f"Set iati_registry_approved back to True for organisation with id: {str(org_id)}",
                    lambda: crm.update_record("Accounts", str(org_id), {"iati_registry_approved": True}),
                )
            )

        # 3. Delete user-org role associations in the FGA database
        context.fine_grained_auth_provider.delete_all_fine_grained_authorisations_for_org(org_id)

        # 4. Delete the datasets
        filters = Filter()
        filters.equal("iati_dataset_owner_org_id", str(org_id))
        datasets_from_suitecrm = crm.get_records("IATI_Datasets", filters=filters, fields=["id"], page_size=1500)
        for dataset in datasets_from_suitecrm.get("data", []):
            dataset_id = dataset["id"]
            crm.delete_record("IATI_Datasets", dataset_id, headers=suitecrm_audit_headers)

        context.audit_logger.info(
            f"User {user.user_id_crm} deleted reporting org {org_id} with its "
            f"{len(datasets_from_suitecrm.get('data', []))} associated datasets"
        )

    except Exception:
        error_trace_id = perform_undo_actions(context, undo_actions, "delete_reporting_org")

        raise HTTPException(
            fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"There was a problem deleting the reporting org. Error id: {error_trace_id}",
        )

    return fastapi.responses.JSONResponse({"status": "success", "data": None, "error": None})


@router.get("/{org_id}/users")
def get_reporting_org_users(
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:user"]),
) -> CRMUserListResponse:

    context: Context = request.app.state.context

    if not user.validator.user_can_read_reporting_org(org_id):
        context.audit_logger.error(
            f"Request to read reporting org users for org id: {org_id} by unauthorised user id: {user.user_id_crm}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    current_user_role_for_ro = user.validator.get_user_role_for_reporting_org(org_id)

    users_for_org_from_suitecrm = crm.get_relationship("Accounts", str(org_id), "Contacts")

    users_for_org_from_fga = context._fga_provider.get_user_associations_for_org(org_id)

    user_ids_from_fga = {str(u.user) for u in users_for_org_from_fga}

    names_emails_from_suitecrm = {
        u["id"]: (u["attributes"]["last_name"], u["attributes"]["email1"])
        for u in users_for_org_from_suitecrm["data"]
        if u["id"] in user_ids_from_fga
    }

    user_ids_in_fga_not_suitecrm = user_ids_from_fga - {*names_emails_from_suitecrm.keys()}

    # iterate over the provider admins, and add their names/emails to the dict
    for provider_admin in users_for_org_from_fga:
        if provider_admin.role == fga_models.FineGrainedAuthorisationRole.PROVIDER_ADMIN:
            filters = Filter()
            filters.equal("id", str(provider_admin.user))
            crm_user = crm.get_records("Contacts", fields=["last_name", "email1"], filters=filters)
            if "data" in crm_user and len(crm_user["data"]) > 0:
                names_emails_from_suitecrm[crm_user["data"][0]["id"]] = (
                    crm_user["data"][0]["attributes"]["last_name"],
                    crm_user["data"][0]["attributes"]["email1"],
                )

    if user_ids_in_fga_not_suitecrm:
        error_message = (
            f"GET request to reporting-orgs/{org_id}/users by user id: {user.user_id_crm} "
            f"but the following users associated with reporting org {org_id} in the FGA data "
            f"store are not associated with that org in SuiteCRM: {user_ids_in_fga_not_suitecrm}"
        )
        context.app_logger.error(error_message)
        context.audit_logger.error(error_message)
        raise fastapi.HTTPException(500)

    users_for_org = [
        CRMUser(
            id=str(u.user),
            name=names_emails_from_suitecrm[str(u.user)][0],
            email=names_emails_from_suitecrm[str(u.user)][1],
            role=get_fga_role_as_str(u.role),
        )
        for u in users_for_org_from_fga
        if (
            u.role != fga_models.FineGrainedAuthorisationRole.PROVIDER_ADMIN
            or current_user_role_for_ro == fga_models.FineGrainedAuthorisationRole.PROVIDER_ADMIN
            or user.validator.is_superadmin
        )
    ]

    users_for_org.sort(key=lambda u: u.name.lower())

    return CRMUserListResponse(data=users_for_org, status="success", error=None)


@router.get("/{org_id}/datasets")
def get_reporting_org_datasets(
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:dataset"]),
    include_actions: str = "no",
    paging: PaginationQueryParams = fastapi.Depends(),
) -> PaginatedResultsPage[DatasetReadModel]:

    context: Context = request.app.state.context

    assert_precondition_met(
        context,
        condition_func=lambda: user.validator.user_can_read_reporting_org_datasets(org_id),
        status_code=fastapi.status.HTTP_403_FORBIDDEN,
        audit_log_msg=(
            f"Request to get reporting org datasets for org id: {org_id} "
            f"by unauthorised user id: {user.user_id_crm}"
        ),
        public_msg=(
            "There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry."
        ),
    )

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    # 1. Check that the Reporting Org exists in the CRM
    assert_precondition_met(
        context,
        condition_func=lambda: check_crm_record_exists(crm, "Accounts", str(org_id)),
        status_code=fastapi.status.HTTP_404_NOT_FOUND,
        public_msg=f"There is no organisation with ID {str(org_id)} in the Registry.",
    )

    # 2. Fetch the datasets
    filters = Filter().equal("iati_dataset_owner_org_id", str(org_id))
    datasets_from_suitecrm = crm.get_records(
        "IATI_Datasets",
        filters=filters,
        page_number=paging.page,
        page_size=paging.page_size,
        sort_dir="ascending",
        sort_field="name",
    )

    # 3. SuiteCRM doesn't tell us the total number of records, so we set page size = 1 and make a request
    total_records_resp = crm.get_records("IATI_Datasets", filters=filters, fields=["id"], page_number=1, page_size=1)
    total_records = total_records_resp.get("meta", {}).get("total-pages", 1)

    datasets = get_dataset_list_from_suitecrm_response(datasets_from_suitecrm)

    for dataset in datasets:
        if include_actions == "yes":
            suitecrm_actions = crm.get_relationship("IATI_Datasets", str(dataset.id), "iati_dataset_actions")
            dataset.actions = get_dataset_actions_from_suitecrm_response(suitecrm_actions)

    return PaginatedResultsPage.create(datasets, paging.page, paging.page_size, total_records, request)


def get_reporting_org_actions(crm: SuiteCRM, org_id: str) -> list[ReportingOrgAction]:
    # TODO:
    return []
