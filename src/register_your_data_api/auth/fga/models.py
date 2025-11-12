from enum import Enum, auto
from uuid import UUID, uuid4

import pydantic


class FineGrainedAuthorisationRole(Enum):
    CONTRIBUTOR = auto()
    EDITOR = auto()
    PROVIDER_ADMIN = auto()
    ADMIN = auto()
    SUPER_ADMIN = auto()
    CONTRIBUTOR_PENDING = auto()


class FineGrainedAuthorisationRoleAssociation(pydantic.BaseModel):
    id: UUID = pydantic.Field(default_factory=lambda: uuid4())
    user: UUID
    reporting_org: UUID
    role: FineGrainedAuthorisationRole
