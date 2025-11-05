import pydantic


class OrganisationId(pydantic.BaseModel):
    oid: str


class CRMUser(pydantic.BaseModel):
    id: str
    name: str
    email: str
    role: str


class DatasetCreateModel(pydantic.BaseModel):
    human_readable_name: str
    licence_id: str
    owner_organisation_id: str
    short_name: str
    source_type: str
    url: str
    visibility: str


class DatasetUpdateModel(pydantic.BaseModel):
    human_readable_name: str
    licence_id: str
    short_name: str
    source_type: str
    url: str
    visibility: str


class DatasetMetadata(pydantic.BaseModel):
    human_readable_name: str
    short_name: str
    source_type: str
    url: str
    visibility: str
    licence_id: str
    last_url_update_date: str
    last_metadata_update_date: str


class DatasetReadModel(pydantic.BaseModel):
    id: str
    owner_organisation_id: str
    metadata: DatasetMetadata


class ReportingOrgCreateModel(pydantic.BaseModel):
    """Class for the data which comes from a POST to /reporting-orgs to create an org"""

    address: str | None
    contact_email: str = pydantic.Field(min_length=3)
    data_portal_url: str | None
    default_licence_id: str | None
    description: str | None
    exclusions_policy_url: str | None
    fax: str | None
    hq_country: str | None
    human_readable_name: str = pydantic.Field(min_length=1)
    organisation_identifier: str | None
    organisation_type: str | None
    phone: str | None
    region: str | None
    reporting_source_type: str | None
    short_name: str | None
    website: str | None


class ReportingOrgUpdateModel(pydantic.BaseModel):

    address: str | None = pydantic.Field(None)
    contact_email: str | None = pydantic.Field(None, min_length=1)
    data_portal_url: str | None = pydantic.Field(None)
    default_licence_id: str | None = pydantic.Field(None)
    description: str | None = pydantic.Field(None)
    exclusions_policy_url: str | None = pydantic.Field(None)
    fax: str | None = pydantic.Field(None)
    hq_country: str | None = pydantic.Field(None)
    human_readable_name: str | None = pydantic.Field(None, min_length=1)
    organisation_type: str | None = pydantic.Field(None)
    phone: str | None = pydantic.Field(None)
    region: str | None = pydantic.Field(None)
    reporting_source_type: str | None = pydantic.Field(None)
    website: str | None = pydantic.Field(None)


class ReportingOrgMetadata(pydantic.BaseModel):

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
    # number_of_published_datasets: str | None = pydantic.Field(None)
    organisation_identifier: str
    organisation_type: str | None = pydantic.Field(None)
    phone: str | None = pydantic.Field(None)
    region: str | None = pydantic.Field(None)
    registry_approved: bool | None = pydantic.Field(False)
    reporting_source_type: str | None = pydantic.Field(None)
    short_name: str | None
    website: str | None = pydantic.Field(None)


class ReportingOrgLimitedMetadata(pydantic.BaseModel):

    hq_country: str | None = pydantic.Field(None)
    human_readable_name: str
    organisation_identifier: str
    region: str | None = pydantic.Field(None)
    short_name: str | None
    website: str | None = pydantic.Field(None)


class ReportingOrgAction(pydantic.BaseModel):
    action_type: str
    user_application_name: str
    user_application_id: str
    user_name: str
    user_id: str
    created_date: str


class UserReportingOrgRelation(pydantic.BaseModel):
    id: str
    metadata: ReportingOrgMetadata | ReportingOrgLimitedMetadata
    reporting_org_actions: list  # type: ignore
    user_role: str


class UserReportingOrgLimitedMetadataRelation(pydantic.BaseModel):
    id: str
    metadata: ReportingOrgLimitedMetadata
    reporting_org_actions: list  # type: ignore
    user_role: str


class CRMUserListResponse(pydantic.BaseModel):
    data: list[CRMUser]
    error: str | None = pydantic.Field(None)
    status: str


class DatasetListResponse(pydantic.BaseModel):
    data: list[DatasetReadModel]
    error: str | None
    status: str


class DatasetSingleResponse(pydantic.BaseModel):
    data: DatasetReadModel
    error: str | None
    status: str


class UserReportingOrgRelationSingleResponse(pydantic.BaseModel):

    data: UserReportingOrgRelation
    error: str | None = pydantic.Field(None)
    status: str


class UserReportingOrgRelationListResponse(pydantic.BaseModel):

    data: list[UserReportingOrgRelation | UserReportingOrgLimitedMetadataRelation]
    error: str | None = pydantic.Field(None)
    status: str
