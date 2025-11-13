from .converters import SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP


def get_reporting_org_fields_to_fetch() -> list[str]:
    return list(SUITECRM_TO_RYD_API_REPORTING_ORG_FIELD_MAP.keys())
