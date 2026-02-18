import uuid

from libsuitecrm import Filter, RequestFailed, SuiteCRM  # type: ignore

from register_your_data_api.auth import models as auth_models
from register_your_data_api.auth.fga import models as fga_models
from register_your_data_api.auth.fga.fga_provider import FineGrainedAuthorisationProvider
from register_your_data_api.data_handling.converters import (
    get_discoverable_reporting_org_meta_from_suitecrm_response,
    get_fga_role_as_str,
    get_reporting_org_meta_from_suitecrm_response,
)
from register_your_data_api.data_handling.data_schemas import (
    DiscoverableReportingOrgMetadata,
    ReportingOrgMetadata,
    UserReportingOrgDiscoverableMetadataRelation,
    UserReportingOrgRelation,
)
from register_your_data_api.exceptions import RYDUserException
from register_your_data_api.util import Context


def get_reporting_orgs_for_user(
    context: Context,
    requesting_user: auth_models.UserAndCredentials,
    user_to_fetch: uuid.UUID,
    page_number: int,
    page_size: int,
) -> tuple[int, list[UserReportingOrgRelation | UserReportingOrgDiscoverableMetadataRelation]]:

    crm: SuiteCRM = context.suitecrm_client_factory.get_client()

    fga_provider: FineGrainedAuthorisationProvider = context.fine_grained_auth_provider

    user_to_fetch_str = str(user_to_fetch)

    try:
        orgs_for_user = crm.get_relationship(
            "Contacts",
            str(user_to_fetch),
            "Accounts",
            page_number=page_number,
            page_size=page_size,
            sort_field="name",
            sort_dir="ascending",
            filters=Filter().equal("iati_registry_discoverable", "1"),
        )
    except RequestFailed as e:
        error_id = uuid.uuid4()
        public_error_message = (
            f"There was a problem fetching the list of reporting orgs for user {user_to_fetch_str}. "
            f"Please try again later, or contact IATI Support quoting error id: {error_id}"
        )
        audit_message = (
            f"error_id: {error_id} - Problem when fetching the list of reporting organisations for user "
            f"{user_to_fetch_str} from SuiteCRM. Details: {str(e)}"
        )
        raise RYDUserException(
            requesting_user, 500, app_msg=None, audit_msg=audit_message, public_msg=public_error_message
        )

    total_records = orgs_for_user.get("meta", {}).get("total-records", 0)

    users_roles = fga_provider.get_user_fine_grained_permissions(user_to_fetch)

    reporting_orgs_list: list[UserReportingOrgRelation | UserReportingOrgDiscoverableMetadataRelation] = []

    for reporting_org_from_suitecrm in orgs_for_user["data"]:
        roles_for_org = list(filter(lambda x: str(x.reporting_org) == reporting_org_from_suitecrm["id"], users_roles))

        if len(roles_for_org) == 0:
            context.app_logger.info(
                f"user id: {requesting_user.user_id_crm} - GET /[users/USER_ID/]reporting-orgs - user "
                f"{user_to_fetch_str} is associated with organisation {reporting_org_from_suitecrm["id"]} in the CRM "
                "but has no role for that organisation in the FGA DB. Organisation was omitted from the list returned "
                "to the user."
            )
            continue

        reporting_org_obj: ReportingOrgMetadata | DiscoverableReportingOrgMetadata

        if roles_for_org[0].role == fga_models.FineGrainedAuthorisationRole.CONTRIBUTOR_PENDING:
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
                user_role=get_fga_role_as_str(roles_for_org[0].role),
                metadata=reporting_org_obj,
                reporting_org_actions=([]),
            )
        )

    reporting_orgs_list.sort(key=lambda org: (org.metadata.human_readable_name.lower(), org.id))

    return (total_records, reporting_orgs_list)
