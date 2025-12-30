from typing import Any

from ..auth.fga.models import FineGrainedAuthorisationRole
from .data_schemas import (
    DatasetActions,
    DatasetCreateModel,
    DatasetMetadata,
    DatasetReadModel,
    DatasetUpdateModel,
    DiscoverableReportingOrg,
    DiscoverableReportingOrgMetadata,
    ReportingOrgMetadata,
    ReportingOrgUpdateModel,
    ReportingOrgUserCreateModel,
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

RYD_API_TO_SUITECRM_DATASET_ACTION_FIELDS_LIST = [
    ["action_type", "iati_action_type"],
    ["created_date", "date_entered"],
    ["responsible_org_id", "iati_action_responsible_org_id"],
    ["responsible_org_name", "iati_action_responsible_org_name"],
    ["user_application_id", "iati_user_application_id"],
    ["user_application_name", "iati_user_application_name"],
    ["user_id", "iati_action_actor_id"],
    ["user_name", "iati_action_actor_name"],
]


RYD_API_TO_SUITECRM_REPORTING_ORG_FIELDS_LIST = [
    ["address", "jjwg_maps_address_c"],
    ["contact_email", "iati_admin_email"],
    ["created_date", "date_entered"],
    ["data_portal_url", "iati_data_portal_url"],
    ["default_licence_id", "iati_default_licence_id"],
    ["description", "description"],
    ["exclusions_policy_url", "iati_exclusions_policy_url"],
    ["fax", "phone_fax"],
    ["first_publication_date", "iati_first_publish_date"],
    ["hq_country", "iati_hq_country"],
    ["human_readable_name", "name"],
    ["iati_registry_discoverable", "iati_registry_discoverable"],
    ["number_of_published_datasets", "iati_num_published_datasets"],
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

SUITECRM_DATASET_ACTION_FIELDS = [f[1] for f in RYD_API_TO_SUITECRM_DATASET_ACTION_FIELDS_LIST]

SUITECRM_REPORTING_ORG_FIELDS = [f[1] for f in RYD_API_TO_SUITECRM_REPORTING_ORG_FIELDS_LIST]

RYD_API_TO_SUITECRM_DATASET_FIELD_MAP = {f[0]: f[1] for f in RYD_API_TO_SUITECRM_DATASET_FIELDS_LIST}

RYD_API_TO_SUITECRM_REPORTING_ORG_FIELD_MAP = {f[0]: f[1] for f in RYD_API_TO_SUITECRM_REPORTING_ORG_FIELDS_LIST}

SUITECRM_TO_RYD_API_DATASET_FIELD_MAP = {f[1]: f[0] for f in RYD_API_TO_SUITECRM_DATASET_FIELDS_LIST}

SUITECRM_TO_RYD_API_DATASET_ACTION_FIELD_MAP = {f[1]: f[0] for f in RYD_API_TO_SUITECRM_DATASET_ACTION_FIELDS_LIST}

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


def get_dataset_actions_from_suitecrm_response(suitecrm_response: dict[str, Any]) -> list[DatasetActions]:
    """Gets a list of native DatasetAction objects from a SuiteCRM response"""

    dataset_actions: list[DatasetActions] = []

    if "data" not in suitecrm_response:
        return dataset_actions

    for record in suitecrm_response["data"]:
        if "attributes" not in record:
            continue

        cleaned_response = get_dict_with_specified_fields(record["attributes"], SUITECRM_DATASET_ACTION_FIELDS)

        action_dict = {SUITECRM_TO_RYD_API_DATASET_ACTION_FIELD_MAP[k]: v for k, v in cleaned_response.items()}

        action_dict["id"] = record["id"]

        dataset_actions.append(DatasetActions(**action_dict))

    return dataset_actions


def get_discoverable_reporting_org_suitecrm_fields() -> list[str]:
    """Gets the list of SuiteCRM fields needed to fetch discoverable reporting orgs"""

    discoverable_org_fields = list(DiscoverableReportingOrgMetadata.model_fields.keys())

    return [RYD_API_TO_SUITECRM_REPORTING_ORG_FIELD_MAP[k] for k in discoverable_org_fields]


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


def get_discoverable_reporting_org_from_suitecrm_response(
    suitecrm_response_record: dict[str, Any],
) -> DiscoverableReportingOrg:
    """Gets a native DiscoverableReportingOrg object from a SuiteCRM response"""

    meta = get_discoverable_reporting_org_meta_from_suitecrm_response(suitecrm_response_record["attributes"])

    return DiscoverableReportingOrg(id=suitecrm_response_record["id"], metadata=meta)


def get_discoverable_reporting_org_meta_from_suitecrm_response(
    suitecrm_response_attribs: dict[str, Any],
) -> DiscoverableReportingOrgMetadata:
    """Gets a native DiscoverableReportingOrgMetadata object from a SuiteCRM response"""

    limited_fields = list(DiscoverableReportingOrgMetadata.model_fields.keys())

    cleaned_response = get_dict_with_specified_fields(suitecrm_response_attribs, SUITECRM_REPORTING_ORG_FIELDS)

    dict_with_ryd_api_field_names = {
        SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP[k]: v
        for k, v in cleaned_response.items()
        if SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP[k] in limited_fields
    }

    return DiscoverableReportingOrgMetadata(**dict_with_ryd_api_field_names)


def get_suitecrm_dict_from_dataset(dataset: DatasetCreateModel | DatasetUpdateModel) -> dict[str, Any]:
    suitecrm_dict = {RYD_API_TO_SUITECRM_DATASET_FIELD_MAP[k]: v for k, v in dataset}
    return suitecrm_dict


def get_suitecrm_dict_from_reporting_org(
    reporting_org: ReportingOrgMetadata | ReportingOrgUserCreateModel | ReportingOrgUpdateModel,
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
        case FineGrainedAuthorisationRole.CONTRIBUTOR_PENDING:
            return "contributor_pending"


def get_fga_role_from_str(role: str) -> FineGrainedAuthorisationRole:
    match role:
        case "admin":
            return FineGrainedAuthorisationRole.ADMIN
        case "contributor":
            return FineGrainedAuthorisationRole.CONTRIBUTOR
        case "editor":
            return FineGrainedAuthorisationRole.EDITOR
        case "provider_admin":
            return FineGrainedAuthorisationRole.PROVIDER_ADMIN
        case "super_admin":
            return FineGrainedAuthorisationRole.SUPER_ADMIN
        case "contributor_pending":
            return FineGrainedAuthorisationRole.CONTRIBUTOR_PENDING
    raise ValueError(f"Unknown role string: {role}")
