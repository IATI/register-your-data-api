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

        return [FineGrainedAuthorisationRoleAssociation(**db_fga.model_dump()) for db_fga in user_db_fgas]

    def get_user_associations_for_org(self, reporting_org: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        with Session(self._engine) as session:
            user_db_fgas = session.exec(
                select(FineGrainedAuthorisationDbModel).where(
                    FineGrainedAuthorisationDbModel.reporting_org == reporting_org
                )
            ).all()

        return [FineGrainedAuthorisationRoleAssociation(**db_fga.model_dump()) for db_fga in user_db_fgas]

    def is_user_a_superadmin(self, user: UUID) -> bool:
        with Session(self._engine) as session:
            user_superadmin_record = session.exec(
                select(SuperAdminUserDbModel).where(SuperAdminUserDbModel.user == user)
            ).first()

        if user_superadmin_record is not None and user_superadmin_record.is_superadmin:
            return True

        return False

    def create_user_fine_grained_authorisation(
        self, user_reporting_org_role: FineGrainedAuthorisationRoleAssociation
    ) -> None:
        user_org_role_db = FineGrainedAuthorisationDbModel(**user_reporting_org_role.model_dump())
        with Session(self._engine) as session:
            session.add(user_org_role_db)
            session.commit()

    def delete_all_fine_grained_authorisations_for_user(self, user: UUID) -> None:
        """Deletes all fine grained role associations for a user"""
        # TODO: Implement this method
        return None
