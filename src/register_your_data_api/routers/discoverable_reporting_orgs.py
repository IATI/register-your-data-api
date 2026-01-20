"""Implementation for /discoverable-reporting-orgs end point"""

import fastapi
import starlette.requests
from fastapi import Security
from libsuitecrm import Filter, SuiteCRM  # type: ignore

from ..auth import authz
from ..auth import models as auth_models
from ..data_handling.converters import (
    get_discoverable_reporting_org_from_suitecrm_response,
    get_discoverable_reporting_org_suitecrm_fields,
)
from ..data_handling.data_schemas import (
    DiscoverableReportingOrg,
    PaginationQueryParams,
)
from ..response_schemas import PaginatedResultsPage
from ..util import Context

router = fastapi.APIRouter(prefix="/api/v1/discoverable-reporting-orgs")


@router.get("")
def get_discoverable_reporting_orgs(
    request: starlette.requests.Request,
    user: auth_models.UserAndCredentials = Security(authz.get_user_authnz, scopes=["ryd", "ryd:reporting_org"]),
    paging: PaginationQueryParams = fastapi.Depends(),
) -> PaginatedResultsPage[DiscoverableReportingOrg]:

    context: Context = request.app.state.context

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    fields = get_discoverable_reporting_org_suitecrm_fields()

    filters = Filter()
    filters.equal("iati_registry_discoverable", "1")
    suitecrm_reporting_orgs = crm.get_records(
        "Accounts",
        fields=fields,
        filters=filters,
        page_number=paging.page,
        page_size=paging.page_size,
        sort_dir="ascending",
        sort_field="name",
    )

    discoverable_orgs = [
        get_discoverable_reporting_org_from_suitecrm_response(org) for org in suitecrm_reporting_orgs["data"]
    ]

    # SuiteCRM doesn't return the total_records, so we set page size = 1, limit fields to id and fetch one record
    total_records_resp = crm.get_records("Accounts", filters=filters, fields=["id"], page_number=1, page_size=1)
    total_records = total_records_resp.get("meta", {}).get("total-pages", 1)

    return PaginatedResultsPage.create(discoverable_orgs, paging.page, paging.page_size, total_records, request)
