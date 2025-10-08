import pydantic


class ReportingOrg(pydantic.BaseModel):

    address: str | None = pydantic.Field(None)
    contact_email: str | None = pydantic.Field(None)
    created_date: str | None = pydantic.Field(None)
    data_portal_url: str | None = pydantic.Field(None)
    default_licence_id: str | None = pydantic.Field(None)
    description: str | None = pydantic.Field(None)
    exclusions_policy_url: str | None = pydantic.Field(None)
    fax: str | None = pydantic.Field(None)
    first_publication_date: str | None = pydantic.Field(None)
    hq_country: str | None = pydantic.Field(None)
    human_readable_name: str
    number_of_published_datasets: str | None = pydantic.Field(None)
    organisation_identifier: str
    organisation_type: str | None = pydantic.Field(None)
    phone: str | None = pydantic.Field(None)
    region: str | None = pydantic.Field(None)
    registry_approved: str | None = pydantic.Field(None)
    reporting_source_type: str | None = pydantic.Field(None)
    short_name: str | None = pydantic.Field(None)
    website: str | None = pydantic.Field(None)


class UserReportingOrgRelation(pydantic.BaseModel):
    id: str
    metadata: ReportingOrg
    reporting_org_actions: list  # type: ignore
    user_role: str


class UserReportingOrgRelationSingleResponse(pydantic.BaseModel):

    data: UserReportingOrgRelation
    error: str | None = pydantic.Field(None)
    status: str


class UserReportingOrgRelationListResponse(pydantic.BaseModel):

    data: list[UserReportingOrgRelation]
    error: str | None = pydantic.Field(None)
    status: str
