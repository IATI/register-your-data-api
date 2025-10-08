"""Implementation for /reporting-orgs end points"""

import uuid

import fastapi
import starlette
from fastapi import Security
from fastapi.responses import JSONResponse
from libsuitecrm import Filter  # type: ignore

import register_your_data_api.auth.authn as authn

from ..auth import authz
from ..auth import models as auth_models
from ..data_handling.converters import (
    get_fga_role_as_str,
    get_reporting_org_from_suitecrm_response,
)
from ..data_handling.data_schemas import (
    UserReportingOrgRelation,
    UserReportingOrgRelationListResponse,
    UserReportingOrgRelationSingleResponse,
)
from ..data_handling.domain_logic import get_reporting_org_fields_to_fetch
from ..util import Context  # noqa

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
        filters = Filter()
        filters.op_or()

        for user_reporting_org_association in user_reporting_org_associations:
            filters.equal("id", str(user_reporting_org_association.reporting_org))

        crm = context.get_suitecrm_client()

        crm.fetch_access_token()

        fields = get_reporting_org_fields_to_fetch(include_meta == "yes")

        crm_reporting_orgs = crm.get_records("Accounts", page_number=1, page_size=1000, fields=fields, filters=filters)

        # TODO: query SuiteCRM to get the list of reporting org actions
        if include_actions == "yes":
            pass

        for reporting_org_from_suitecrm in crm_reporting_orgs["data"]:
            reporting_org_obj = get_reporting_org_from_suitecrm_response(reporting_org_from_suitecrm["attributes"])

            role_for_org = user.validator.get_user_role_for_reporting_org(reporting_org_from_suitecrm["id"])

            reporting_orgs_list.append(
                UserReportingOrgRelation(
                    id=reporting_org_from_suitecrm["id"],
                    user_role=get_fga_role_as_str(role_for_org),  # type: ignore
                    metadata=reporting_org_obj,
                    reporting_org_actions=[],
                )
            )

    return UserReportingOrgRelationListResponse(status="success", error=None, data=reporting_orgs_list)


@router.post("/")
def create_reporting_org(
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org", "ryd:reporting_org:create"]
    ),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.get("/{org_id}")
def get_reporting_org_detail(
    org_id: str,  # TODO: validate as UUID
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org"]),
    include_actions: str = "no",
) -> UserReportingOrgRelationSingleResponse:

    context = request.app.state.context  # type: Context

    if not user.validator.user_can_read_reporting_org(uuid.UUID(org_id)):
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_403_FORBIDDEN,
            detail="There is a problem with your credentials.  If this persists please report "
            "error to the provider of the tool you are using to access the IATI Registry.",
        )

    filters = Filter()
    filters.equal("id", org_id)

    crm = context.get_suitecrm_client()

    crm.fetch_access_token()

    fields = get_reporting_org_fields_to_fetch(True)

    crm_reporting_orgs = crm.get_records("Accounts", page_number=1, page_size=1000, fields=fields, filters=filters)

    # TODO: query SuiteCRM to get the list of reporting org actions
    if include_actions == "yes":
        pass

    if len(crm_reporting_orgs["data"]) == 0:
        raise fastapi.HTTPException(status_code=fastapi.status.HTTP_404_NOT_FOUND, detail="No such reporting org")

    reporting_org = get_reporting_org_from_suitecrm_response(crm_reporting_orgs["data"][0]["attributes"])

    user_reporting_org_relation = UserReportingOrgRelation(
        id=org_id,
        user_role=get_fga_role_as_str(user.validator.get_user_role_for_reporting_org(org_id)),  # type: ignore
        metadata=reporting_org,
        reporting_org_actions=[],
    )

    return UserReportingOrgRelationSingleResponse(status="success", error=None, data=user_reporting_org_relation)


@router.patch("/{org_id}")
def update_reporting_org(
    org_id: str,
    request: starlette.requests.Request,
    include_actions: str = "no",
    user: auth_models.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org", "ryd:reporting_org:update"]
    ),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.delete("/{org_id}")
def delete_reporting_org(
    org_id: str,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:delete"]
    ),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.get("/{org_id}/users")
def get_reporting_org_users(
    org_id: str,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(
        authn.parse_decoded_token, scopes=["ryd", "ryd:reporting_org:user"]
    ),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )


@router.get("/{org_id}/datasets")
def get_reporting_org_datasets(
    org_id: str,
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authn.parse_decoded_token, scopes=["ryd", "ryd:dataset"]),
) -> JSONResponse:
    raise fastapi.HTTPException(
        status_code=fastapi.status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not yet implemented",
    )
