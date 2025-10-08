from .converters import SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP


def get_reporting_org_fields_to_fetch(include_meta: bool = False) -> list[str]:
    if include_meta:
        return list(SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP.keys())
    else:
        return ["iati_identifier", "iati_short_name", "name"]
