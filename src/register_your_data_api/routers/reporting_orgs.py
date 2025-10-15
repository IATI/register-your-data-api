"""Implementation for /reporting-orgs end points"""

import uuid
from typing import Any, Callable  # noqa

import fastapi
import starlette
from fastapi import Security
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from libsuitecrm import Filter, SuiteCRM  # type: ignore
from libsuitecrm.exceptions import CreateRecordFailed, UpdateRecordFailed  # type: ignore

from ..auth import authz
from ..auth import models as auth_models
from ..auth.fga import models as fga_models
from ..data_handling.converters import (
    get_fga_role_as_str,
    get_reporting_org_from_suitecrm_response,
    get_suitecrm_dict_from_reporting_org,
)
from ..data_handling.data_schemas import (
    CRMUser,
    CRMUserListResponse,
    DatasetListResponse,
    DatasetMetadata,
    DatasetReadModel,
    ReportingOrgAction,
    ReportingOrgCreateModel,
    ReportingOrgUpdateModel,
    UserReportingOrgRelation,
    UserReportingOrgRelationListResponse,
    UserReportingOrgRelationSingleResponse,
)
from ..data_handling.domain_logic import get_reporting_org_fields_to_fetch
from ..util import Context  # noqa
from ..utilities import check_crm_record_exists

router = fastapi.APIRouter(prefix="/api/v1/reporting-orgs")


@router.get("/")
def get_reporting_orgs(
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org"]),
    include_meta: str = "no",
    include_actions: str = "no",
) -> UserReportingOrgRelationListResponse:
    context = request.app.state.context  # type: Context

    user_reporting_org_associations = user.validator.get_users_fine_grained_associations()

    reporting_orgs_list = []

    if len(user_reporting_org_associations) > 0:

        crm = context.get_suitecrm_client()

        crm.fetch_access_token()

        fields = get_reporting_org_fields_to_fetch(include_meta == "yes")

        # The OR search in SuiteCRM appears to be broken; you can't search for items where id = 'A' OR id = 'B' OR ...
        # It appears this doesn't work when the field being searched on is the same in each case. So we have to fetch
        # the details for reporting orgs the user is associated with one at a time.
        suitecrm_collected_responses = []  # type: list[dict[str, Any]]
        for user_reporting_org_association in user_reporting_org_associations:
            filters = Filter()
            filters.equal("id", str(user_reporting_org_association.reporting_org))
            crm_reporting_org = crm.get_records("Accounts", fields=fields, filters=filters)
            suitecrm_collected_responses.append(*crm_reporting_org["data"])

        for reporting_org_from_suitecrm in suitecrm_collected_responses:
            reporting_org_obj = get_reporting_org_from_suitecrm_response(reporting_org_from_suitecrm["attributes"])

            role_for_org = user.validator.get_user_role_for_reporting_org(reporting_org_from_suitecrm["id"])

            reporting_orgs_list.append(
                UserReportingOrgRelation(
                    id=reporting_org_from_suitecrm["id"],
                    user_role=get_fga_role_as_str(role_for_org),  # type: ignore
                    metadata=reporting_org_obj,
                    reporting_org_actions=(
                        get_reporting_org_actions(crm, reporting_org_from_suitecrm["id"])
                        if include_actions == "yes"
                        else []
                    ),
                )
            )

    return UserReportingOrgRelationListResponse(status="success", error=None, data=reporting_orgs_list)


@router.get("/{org_id}")
def get_reporting_org_detail(
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org"]),
    include_actions: str = "no",
) -> UserReportingOrgRelationSingleResponse:

    context = request.app.state.context  # type: Context

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

    crm = context.get_suitecrm_client()

    crm.fetch_access_token()

    fields = get_reporting_org_fields_to_fetch(True)

    crm_reporting_orgs = crm.get_records("Accounts", page_number=1, page_size=10, fields=fields, filters=filters)

    if len(crm_reporting_orgs["data"]) == 0:
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail="Organisation UUID is not known in the registry."
        )

    reporting_org = get_reporting_org_from_suitecrm_response(crm_reporting_orgs["data"][0]["attributes"])

    user_reporting_org_relation = UserReportingOrgRelation(
        id=str(org_id),
        user_role=get_fga_role_as_str(user.validator.get_user_role_for_reporting_org(org_id)),  # type: ignore
        metadata=reporting_org,
        reporting_org_actions=get_reporting_org_actions(crm, str(org_id)) if include_actions == "yes" else [],
    )

    return UserReportingOrgRelationSingleResponse(status="success", error=None, data=user_reporting_org_relation)


@router.post("/", status_code=201)
def create_reporting_org(
    request: starlette.requests.Request,
    reporting_org: ReportingOrgCreateModel,
    user: auth_models.UserAndCredentials = Security(
        authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org", "ryd:reporting_org:create"]
    ),
) -> UserReportingOrgRelationSingleResponse:

    context = request.app.state.context  # type: Context

    if not user.validator.user_can_create_reporting_org():
        context.audit_logger.error(f"Request to create reporting org by unauthorised user id: {user.user_id_crm}")
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    undo_actions = []  # type: list[Callable[[None],None]]

    crm = context.get_suitecrm_client()  # type: SuiteCRM

    crm.fetch_access_token()

    try:
        # 1. Create the reporting on SuiteCRM
        reporting_org_for_suitecrm = get_suitecrm_dict_from_reporting_org(reporting_org)
        suitecrm_reporting_org = crm.create_record("Accounts", reporting_org_for_suitecrm)
        new_reporting_org = get_reporting_org_from_suitecrm_response(suitecrm_reporting_org["attributes"])
        undo_actions.append(lambda: crm.delete_record("Accounts", suitecrm_reporting_org["id"]))  # type: ignore

        # 2. TODO: Create a relationship between the current user and the
        # reporting org in SuiteCRM, but only if user is not operating in the
        # capacity as a super_admin

        # 3. Create a fine-grained authorisation for this user to be ADMIN of new reporting_org
        user_reporting_org_role = fga_models.FineGrainedAuthorisationRoleAssociation(
            user=uuid.UUID(user.user_id_crm),
            reporting_org=uuid.UUID(suitecrm_reporting_org["id"]),
            role=fga_models.FineGrainedAuthorisationRole.ADMIN,
        )
        context.fine_grained_auth_provider.create_user_fine_grained_authorisation(user_reporting_org_role)

    except Exception as e:
        # TODO: call each of the callbacks

        match e:
            case CreateRecordFailed():
                # TODO: add logging
                raise HTTPException(status_code=fastapi.status.HTTP_400_BAD_REQUEST, detail=e.msg)
            case _:
                # TODO: add logging
                raise e

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
) -> UserReportingOrgRelationSingleResponse:

    context = request.app.state.context  # type: Context

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

    crm: SuiteCRM = context.get_suitecrm_client()

    crm.fetch_access_token()

    # 1. Query SuiteCRM to check that the reporting_org exists
    if not check_crm_record_exists(crm, "Accounts", str(org_id)):
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail="Organisation UUID is not known in the registry."
        )

    # 2. Make request to SuiteCRM to update reporting_org
    reporting_org_for_suitecrm = get_suitecrm_dict_from_reporting_org(updated_reporting_org)
    try:
        suitecrm_reporting_org = crm.update_record("Accounts", str(org_id), reporting_org_for_suitecrm)
        updated_reporting_org_from_suitecrm = get_reporting_org_from_suitecrm_response(
            suitecrm_reporting_org["attributes"]
        )
    except UpdateRecordFailed as e:
        raise HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail=e.msg,
        )

    user_reporting_org_relation = UserReportingOrgRelation(
        id=str(org_id),
        user_role=get_fga_role_as_str(user.validator.get_user_role_for_reporting_org(org_id)),  # type: ignore
        metadata=updated_reporting_org_from_suitecrm,
        reporting_org_actions=get_reporting_org_actions(crm, str(org_id)) if include_actions == "yes" else [],
    )

    return UserReportingOrgRelationSingleResponse(status="success", error=None, data=user_reporting_org_relation)


@router.delete("/{org_id}")
def delete_reporting_org(
    org_id: str,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:delete"]),
) -> JSONResponse:

    raise HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.get("/{org_id}/users")
def get_reporting_org_users(
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org:user"]),
) -> CRMUserListResponse:

    context = request.app.state.context  # type: Context

    if not user.validator.user_can_read_reporting_org(org_id):
        context.audit_logger.error(
            f"Request to read reporting org users for org id: {org_id} " f"by unauthorised user id: {user.user_id_crm}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    crm: SuiteCRM = context.get_suitecrm_client()

    crm.fetch_access_token()

    users_for_org_from_suitecrm = crm.get_relationship("Accounts", str(org_id), "Contacts")

    users_for_org_from_fga = context._fga_provider.get_user_associations_for_org(org_id)

    user_ids_from_fga = {str(u.user) for u in users_for_org_from_fga}

    names_emails_from_suitecrm = {
        u["id"]: (u["attributes"]["last_name"], u["attributes"]["email1"])
        for u in users_for_org_from_suitecrm["data"]
        if u["id"] in user_ids_from_fga
    }

    user_ids_in_fga_not_suitecrm = user_ids_from_fga - {*names_emails_from_suitecrm.keys()}

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
    ]

    return CRMUserListResponse(data=users_for_org, status="success", error=None)


@router.get("/{org_id}/datasets")
def get_reporting_org_datasets(
    org_id: uuid.UUID,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:dataset"]),
) -> DatasetListResponse:

    context = request.app.state.context  # type: Context

    if not user.validator.user_can_read_reporting_org_datasets(org_id):
        context.audit_logger.error(
            f"Request to get reporting org datasets for org id: {org_id} "
            f"by unauthorised user id: {user.user_id_crm}"
        )
        raise HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    crm: SuiteCRM = context.get_suitecrm_client()

    crm.fetch_access_token()

    # 1. Check that the Reporting Org exists in the CRM
    if not check_crm_record_exists(crm, "Accounts", str(org_id)):
        raise HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND, detail="Organisation UUID is not known in the registry."
        )

    # 2. Fetch the datasets
    filters = Filter()
    filters.equal("iati_dataset_owner_org_id", str(org_id))
    datasets_from_suitecrm = crm.get_records("IATI_Datasets", filters=filters)

    datasets = [
        DatasetReadModel(
            id=d["id"],
            owner_organisation_id=d["attributes"]["iati_dataset_owner_org_id"],
            metadata=DatasetMetadata(
                short_name=d["attributes"]["iati_short_name"],
                source_type=d["attributes"]["iati_source_type"],
                url=d["attributes"]["iati_dataset_url"],
                visibility=d["attributes"]["iati_visibility"],
                licence_id=d["attributes"]["iati_licence_id"],
                last_url_update_date=d["attributes"]["iati_url_update_date"],
                last_metadata_update_date=d["attributes"]["iati_metadata_update_date"],
            ),
        )
        for d in datasets_from_suitecrm["data"]
    ]

    return DatasetListResponse(data=datasets, error=None, status="success")


def get_reporting_org_actions(crm: SuiteCRM, org_id: str) -> list[ReportingOrgAction]:
    # TODO:
    return []
