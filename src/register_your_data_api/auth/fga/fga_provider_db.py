from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from .fga_provider import FineGrainedAuthorisationProvider
from .models import FineGrainedAuthorisationRole, FineGrainedAuthorisationRoleAssociation


class FineGrainedAuthorisationDbModel(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=lambda: uuid4())
    user: UUID = Field(index=True)
    reporting_org: UUID = Field(index=True)
    role: FineGrainedAuthorisationRole


class SuperAdminUserDbModel(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=lambda: uuid4())
    user: UUID = Field(index=True)
    is_superadmin: bool


class FineGrainedAuthorisationProviderDb(FineGrainedAuthorisationProvider):

    _connection_str: str
    _engine: Engine

    def __init__(self, connection_str: str):
        self._connection_str = connection_str

    def setup(self) -> None:
        self._engine = create_engine(self._connection_str, echo=True)
        SQLModel.metadata.create_all(self._engine)

    def get_user_fine_grained_permissions(self, user: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        with Session(self._engine) as session:
            user_db_fgas = session.exec(
                select(FineGrainedAuthorisationDbModel).where(FineGrainedAuthorisationDbModel.user == user)
            ).all()

        user_fgas = [FineGrainedAuthorisationRoleAssociation(**db_fga.model_dump()) for db_fga in user_db_fgas]

        return user_fgas

    def is_user_a_superadmin(self, user: UUID) -> bool:
        with Session(self._engine) as session:
            user_superadmin_record = session.exec(
                select(SuperAdminUserDbModel).where(SuperAdminUserDbModel.user == user)
            ).first()

        if user_superadmin_record is not None and user_superadmin_record.is_superadmin:
            return True

        return False
