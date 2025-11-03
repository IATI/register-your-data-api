from typing import Any

from ..auth.fga.models import FineGrainedAuthorisationRole
from .data_schemas import (
    DatasetCreateModel,
    DatasetMetadata,
    DatasetReadModel,
    DatasetUpdateModel,
    ReportingOrgCreateModel,
    ReportingOrgMetadata,
    ReportingOrgUpdateModel,
)

RYD_API_TO_SUITECRM_DATASET_FIELDS_LIST = [
    ["human_readable_name", "name"],
    ["last_url_update_date", "iati_url_update_date"],
    ["last_metadata_update_date", "iati_metadata_update_date"],
    ["licence_id", "iati_licence_id"],
    ["owner_organisation_id", "iati_dataset_owner_org_id"],
    ["short_name", "iati_short_name"],
    ["source_type", "iati_source_type"],
    ["url", "iati_dataset_url"],
    ["visibility", "iati_visibility"],
]

RYD_API_TO_SUITECRM_REPORTING_ORG_FIELDS_LIST = [
    ["address", "jjwg_maps_address_c"],
    ["contact_email", "email1"],
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

RYD_API_REPORTING_ORG_FIELDS = [f[0] for f in RYD_API_TO_SUITECRM_REPORTING_ORG_FIELDS_LIST]

SUITECRM_DATASET_FIELDS = [f[1] for f in RYD_API_TO_SUITECRM_DATASET_FIELDS_LIST]

SUITECRM_REPORTING_ORG_FIELDS = [f[1] for f in RYD_API_TO_SUITECRM_REPORTING_ORG_FIELDS_LIST]

RYD_API_TO_SUITECRM_DATASET_FIELD_MAP = {f[0]: f[1] for f in RYD_API_TO_SUITECRM_DATASET_FIELDS_LIST}

RYD_API_TO_SUITECRM_REPORTING_ORG_FIELD_MAP = {f[0]: f[1] for f in RYD_API_TO_SUITECRM_REPORTING_ORG_FIELDS_LIST}

SUITECRM_TO_RYD_API_DATASET_FIELD_MAP = {f[1]: f[0] for f in RYD_API_TO_SUITECRM_DATASET_FIELDS_LIST}

SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP = {f[1]: f[0] for f in RYD_API_TO_SUITECRM_REPORTING_ORG_FIELDS_LIST}


def get_dict_with_specified_fields(d: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Returns a new dictionary with the key:value pairs from d if key is in fields"""

    return {k: v for k, v in d.items() if k in fields}


def get_dataset_list_from_suitecrm_response(suitecrm_response: dict[str, Any]) -> list[DatasetReadModel]:
    """Gets a list of native DatasetReadModel objects from a SuiteCRM response"""

    return [
        DatasetReadModel(
            id=d["id"],
            owner_organisation_id=d["attributes"]["iati_dataset_owner_org_id"],
            metadata=get_dataset_meta_from_suitecrm_response(d["attributes"]),
        )
        for d in suitecrm_response["data"]
    ]


def get_dataset_meta_from_suitecrm_response(suitecrm_response: dict[str, Any]) -> DatasetMetadata:
    """Gets a native DatasetMetadata object from a SuiteCRM response"""

    cleaned_response = get_dict_with_specified_fields(suitecrm_response, SUITECRM_DATASET_FIELDS)
    dict_with_ryd_api_field_names = {SUITECRM_TO_RYD_API_DATASET_FIELD_MAP[k]: v for k, v in cleaned_response.items()}
    return DatasetMetadata(**dict_with_ryd_api_field_names)


def get_reporting_org_meta_from_suitecrm_response(suitecrm_response: dict[str, Any]) -> ReportingOrgMetadata:
    """Gets a native ReportingOrgMetadata object from a SuiteCRM response"""

    cleaned_response = get_dict_with_specified_fields(suitecrm_response, SUITECRM_REPORTING_ORG_FIELDS)
    dict_with_ryd_api_field_names = {
        SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP[k]: v for k, v in cleaned_response.items()
    }
    # Now fix the fields that are typed differently
    if "registry_approved" in dict_with_ryd_api_field_names:
        dict_with_ryd_api_field_names["registry_approved"] = dict_with_ryd_api_field_names["registry_approved"] == "1"
    return ReportingOrgMetadata(**dict_with_ryd_api_field_names)


def get_suitecrm_dict_from_dataset(dataset: DatasetCreateModel | DatasetUpdateModel) -> dict[str, Any]:
    suitecrm_dict = {RYD_API_TO_SUITECRM_DATASET_FIELD_MAP[k]: v for k, v in dataset}
    return suitecrm_dict


def get_suitecrm_dict_from_reporting_org(
    reporting_org: ReportingOrgMetadata | ReportingOrgCreateModel | ReportingOrgUpdateModel,
) -> dict[str, Any]:
    suitecrm_dict = {RYD_API_TO_SUITECRM_REPORTING_ORG_FIELD_MAP[k]: v for k, v in reporting_org}
    return suitecrm_dict


def get_fga_role_as_str(role: FineGrainedAuthorisationRole) -> str:
    match role:
        case FineGrainedAuthorisationRole.ADMIN:
            return "admin"
        case FineGrainedAuthorisationRole.CONTRIBUTOR:
            return "contributor"
        case FineGrainedAuthorisationRole.EDITOR:
            return "editor"
        case FineGrainedAuthorisationRole.PROVIDER_ADMIN:
            return "provider_admin"
        case FineGrainedAuthorisationRole.SUPER_ADMIN:
            return "super_admin"
