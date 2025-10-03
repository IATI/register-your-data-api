from typing import Any

from ..auth.fga.models import FineGrainedAuthorisationRole
from .data_schemas import ReportingOrg

RYD_API_TO_SUTIECRM_REPORTING_ORG_FIELDS_LIST = [
    ["address", "billing_address_street"],
    ["contact_email", "email_addresses_primary"],
    ["created_date", "date_entered"],
    ["data_portal_url", "iati_data_portal_url"],
    ["default_licence_id", "iati_default_licence_id"],
    ["description", "description"],
    ["exclusions_policy_url", "iati_exclusions_policy_url"],
    ["fax", "phone_fax"],
    ["first_publication_date", "iati_first_publish_date"],
    ["hq_country", "iati_hq_country"],
    ["human_readable_name", "name"],
    # TODO: uncomment below (and verify correct) once the derived field exists in SuiteCRM again
    # ["number_of_published_datasets", "iati_num_published_datasets"],
    ["organisation_identifier", "iati_identifier"],
    ["organisation_type", "iati_org_type"],
    ["phone", "phone_office"],
    ["region", "iati_region"],
    ["registry_approved", "iati_registry_approved"],
    ["reporting_source_type", "iati_reporting_source_type"],
    ["short_name", "iati_short_name"],
    ["website", "website"],
]

RYD_API_REPORTING_ORG_FIELDS = [f[0] for f in RYD_API_TO_SUTIECRM_REPORTING_ORG_FIELDS_LIST]

SUITECRM_REPORTING_ORG_FIELDS = [f[1] for f in RYD_API_TO_SUTIECRM_REPORTING_ORG_FIELDS_LIST]

RYD_API_TO_SUITECRM_REPORTING_ORG_FIELD_MAP = {f[0]: f[1] for f in RYD_API_TO_SUTIECRM_REPORTING_ORG_FIELDS_LIST}

SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP = {f[1]: f[0] for f in RYD_API_TO_SUTIECRM_REPORTING_ORG_FIELDS_LIST}


def get_dict_with_specified_fields(d: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k in fields}


def get_reporting_org_from_suitecrm_response(suitecrm_response: dict[str, Any]) -> ReportingOrg:
    cleaned_response = get_dict_with_specified_fields(suitecrm_response, SUITECRM_REPORTING_ORG_FIELDS)
    dict_with_ryd_api_field_names = {
        SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP[k]: v for k, v in cleaned_response.items()
    }
    return ReportingOrg(**dict_with_ryd_api_field_names)


def get_fga_role_as_str(role: FineGrainedAuthorisationRole) -> str:
    match role:
        case FineGrainedAuthorisationRole.CONTRIBUTOR:
            return "contributor"
        case FineGrainedAuthorisationRole.EDITOR:
            return "editor"
        case FineGrainedAuthorisationRole.PROVIDER_ADMIN:
            return "provider_admin"
        case FineGrainedAuthorisationRole.ADMIN:
            return "admin"
