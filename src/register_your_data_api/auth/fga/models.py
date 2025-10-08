from enum import Enum, auto
from uuid import UUID

import pydantic


class FineGrainedAuthorisationRole(Enum):
    CONTRIBUTOR = auto()
    EDITOR = auto()
    PROVIDER_ADMIN = auto()
    ADMIN = auto()


class FineGrainedAuthorisationRoleAssociation(pydantic.BaseModel):
    id: UUID
    user: UUID
    reporting_org: UUID
    role: FineGrainedAuthorisationRole
