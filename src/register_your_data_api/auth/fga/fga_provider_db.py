from collections import Counter
from uuid import UUID, uuid4

from sqlalchemy import Engine, delete
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from .fga_provider import FineGrainedAuthorisationIntegrityError, FineGrainedAuthorisationProvider
from .models import FineGrainedAuthorisationRole, FineGrainedAuthorisationRoleAssociation, FineGrainedAuthorisationTool


class FineGrainedAuthorisationDbModel(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=lambda: uuid4())
    user: UUID = Field(index=True)
    reporting_org: UUID = Field(index=True)
    role: FineGrainedAuthorisationRole


class SuperAdminUserDbModel(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=lambda: uuid4())
    user: UUID = Field(index=True)
    is_superadmin: bool


class ToolDbModel(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=lambda: uuid4())
    name: str
    provider: str
    client_id: str


class ToolAuthorisationDbModel(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=lambda: uuid4())
    tool: UUID = Field(foreign_key="tooldbmodel.id", index=True)
    reporting_org: UUID = Field(index=True)


class ToolAdminUserDbModel(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=lambda: uuid4())
    tool: UUID = Field(foreign_key="tooldbmodel.id", index=True)
    user: UUID = Field(index=True)


class FineGrainedAuthorisationProviderDb(FineGrainedAuthorisationProvider):

    _connection_str: str
    _engine: Engine

    def __init__(self, connection_str: str):
        self._connection_str = connection_str

    def setup(self) -> None:
        self._engine = create_engine(self._connection_str, echo=True)

    def get_user_fine_grained_permissions(self, user: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        with Session(self._engine) as session:
            user_db_fgas = session.exec(
                select(FineGrainedAuthorisationDbModel).where(FineGrainedAuthorisationDbModel.user == user)
            ).all()

            providers_reporting_orgs = session.exec(
                select(ToolAuthorisationDbModel.reporting_org, ToolAdminUserDbModel.user, ToolDbModel.id)
                .join(ToolAdminUserDbModel, col(ToolAdminUserDbModel.tool) == col(ToolAuthorisationDbModel.tool))
                .join(ToolDbModel, col(ToolDbModel.id) == col(ToolAuthorisationDbModel.tool))
                .where(ToolAdminUserDbModel.user == user)
            ).all()

        if user_db_fgas and providers_reporting_orgs:
            raise FineGrainedAuthorisationIntegrityError("User has both reporting org role(s) and is a tool user")

        associations = [FineGrainedAuthorisationRoleAssociation(**db_fga.model_dump()) for db_fga in user_db_fgas]
        associations += [
            FineGrainedAuthorisationRoleAssociation(
                reporting_org=x[0],
                user=x[1],
                role=FineGrainedAuthorisationRole.PROVIDER_ADMIN,
                restricted_to_tool=x[2],
            )
            for x in providers_reporting_orgs
        ]

        return associations

    def get_user_associations_for_org(self, reporting_org: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        with Session(self._engine) as session:
            user_db_fgas = session.exec(
                select(FineGrainedAuthorisationDbModel).where(
                    FineGrainedAuthorisationDbModel.reporting_org == reporting_org
                )
            ).all()

            tool_admin_users_for_org = session.exec(
                select(ToolAuthorisationDbModel.reporting_org, ToolAdminUserDbModel.user, ToolDbModel.id)
                .join(ToolAdminUserDbModel, col(ToolAdminUserDbModel.tool) == col(ToolAuthorisationDbModel.tool))
                .join(ToolDbModel, col(ToolDbModel.id) == col(ToolAuthorisationDbModel.tool))
                .where(ToolAuthorisationDbModel.reporting_org == reporting_org)
            ).all()

        regular_associations = [
            FineGrainedAuthorisationRoleAssociation(**db_fga.model_dump()) for db_fga in user_db_fgas
        ]
        if max(Counter([association.user for association in regular_associations]).values(), default=0) > 1:
            raise FineGrainedAuthorisationIntegrityError(
                "Reporting org has user(s) that have multiple reporting org roles"
            )

        # Check that provider admin users are unique for this reporting org - each user can only have provider
        # admin by each tool (we cannot have two accesses via provider admin by the same tool).
        provider_admin_associations = [
            FineGrainedAuthorisationRoleAssociation(
                user=tool_admin_user_for_org[1],
                reporting_org=reporting_org,
                role=FineGrainedAuthorisationRole.PROVIDER_ADMIN,
                restricted_to_tool=tool_admin_user_for_org[2],
            )
            for tool_admin_user_for_org in tool_admin_users_for_org
        ]
        if (
            max(
                Counter(
                    [(association.user, association.restricted_to_tool) for association in provider_admin_associations]
                ).values(),
                default=0,
            )
            > 1
        ):
            raise FineGrainedAuthorisationIntegrityError(
                "Reporting org has provider admins with multiple conflicting tool admin roles"
            )

        # Check that a provider admin is not in the list of regular associations.
        if set([x.user for x in regular_associations]) & set([x.user for x in provider_admin_associations]):
            raise FineGrainedAuthorisationIntegrityError(
                "Reporting org has user(s) with both provider admin and reporting org roles"
            )

        return regular_associations + provider_admin_associations

    def get_user_roles_for_org(self, user: UUID, org: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        with Session(self._engine) as session:
            user_roles_for_org = session.exec(
                select(FineGrainedAuthorisationDbModel).where(
                    (FineGrainedAuthorisationDbModel.user == user)
                    & (FineGrainedAuthorisationDbModel.reporting_org == org)
                )
            ).all()

            tool_admin_users_for_org = session.exec(
                select(ToolAuthorisationDbModel.reporting_org, ToolAdminUserDbModel.user, ToolDbModel.id)
                .join(ToolAdminUserDbModel, col(ToolAdminUserDbModel.tool) == col(ToolAuthorisationDbModel.tool))
                .join(ToolDbModel, col(ToolDbModel.id) == col(ToolAuthorisationDbModel.tool))
                .where((ToolAuthorisationDbModel.reporting_org == org) & (ToolAdminUserDbModel.user == user))
            ).all()

        if tool_admin_users_for_org and user_roles_for_org:
            raise FineGrainedAuthorisationIntegrityError("User has both reporting org role and a provider admin role")

        if not user_roles_for_org and not tool_admin_users_for_org:
            return []

        if tool_admin_users_for_org:
            associations = [
                FineGrainedAuthorisationRoleAssociation(
                    user=user,
                    reporting_org=org,
                    role=FineGrainedAuthorisationRole.PROVIDER_ADMIN,
                    restricted_to_tool=tool_admin_user_for_org[2],
                )
                for tool_admin_user_for_org in tool_admin_users_for_org
            ]

        if len(user_roles_for_org) > 1:
            raise FineGrainedAuthorisationIntegrityError("User has multiple roles for this reporting org")

        if user_roles_for_org:
            associations = [FineGrainedAuthorisationRoleAssociation(**user_roles_for_org[0].model_dump())]

        return associations

    def get_admin_users_for_org(self, org: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        with Session(self._engine) as session:
            admin_user_db_fgas = session.exec(
                select(FineGrainedAuthorisationDbModel).where(
                    (FineGrainedAuthorisationDbModel.reporting_org == org)
                    & (FineGrainedAuthorisationDbModel.role == FineGrainedAuthorisationRole.ADMIN)
                )
            ).all()

        return [FineGrainedAuthorisationRoleAssociation(**db_fga.model_dump()) for db_fga in admin_user_db_fgas]

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
        # TODO: Check user doesn't have provider admin

    def update_user_role_for_org(self, user_reporting_org_role: FineGrainedAuthorisationRoleAssociation) -> None:
        user_org_role_db = FineGrainedAuthorisationDbModel(**user_reporting_org_role.model_dump())
        with Session(self._engine) as session:
            session.merge(user_org_role_db)
            session.commit()
        # TODO: Check user doesn't have provider admin

    def delete_user_role_for_org(self, user_reporting_org_role: FineGrainedAuthorisationRoleAssociation) -> None:
        with Session(self._engine) as session:
            user_role_db = session.exec(
                select(FineGrainedAuthorisationDbModel).where(
                    (FineGrainedAuthorisationDbModel.user == user_reporting_org_role.user)
                    & (FineGrainedAuthorisationDbModel.reporting_org == user_reporting_org_role.reporting_org)
                )
            ).first()

            if user_role_db:
                session.delete(user_role_db)
                session.commit()

    def delete_all_fine_grained_authorisations_for_user(self, user: UUID) -> None:
        """Deletes all fine grained role associations for a user"""
        # TODO: Implement this method
        return None

    def delete_all_fine_grained_authorisations_for_org(self, org: UUID) -> None:
        """Deletes all fine grained role associations for an organisation"""

        delete_cmd = delete(FineGrainedAuthorisationDbModel).where(
            FineGrainedAuthorisationDbModel.reporting_org == org  # type: ignore
        )

        with Session(self._engine) as session:
            session.exec(delete_cmd)
            session.commit()

        return None

    def get_all_tools(self) -> list[FineGrainedAuthorisationTool]:
        """Get a list of all the tools stored in the database."""
        with Session(self._engine) as session:
            db_tools = session.exec(select(ToolDbModel)).all()

            return [FineGrainedAuthorisationTool(**db_tool.model_dump()) for db_tool in db_tools]

        return []

    def get_tools_for_user(self, user: UUID) -> list[FineGrainedAuthorisationTool]:
        """Get a list of all the tools for which the user is an admin user."""

        with Session(self._engine) as session:
            db_tools = session.exec(
                select(ToolDbModel).join(ToolAdminUserDbModel).where(ToolAdminUserDbModel.user == user)
            ).all()

            return [FineGrainedAuthorisationTool(**db_tool.model_dump()) for db_tool in db_tools]

        return []

    def is_user_a_tool_adminuser(self, user: UUID) -> bool:
        return len(self.get_tools_for_user(user)) > 0

    def get_tools_for_organisation(self, org: UUID) -> list[FineGrainedAuthorisationTool]:
        """Get a list of the tools authorised by the reporting organisation."""

        with Session(self._engine) as session:
            db_tools = session.exec(
                select(ToolDbModel).join(ToolAuthorisationDbModel).where(ToolAuthorisationDbModel.reporting_org == org)
            ).all()

            return [FineGrainedAuthorisationTool(**db_tool.model_dump()) for db_tool in db_tools]

        return []

    def get_tool_by_id(self, tool_id: UUID) -> FineGrainedAuthorisationTool | None:
        """Get a tool by its id, or None if no such tool exists."""

        with Session(self._engine) as session:
            db_tool = session.exec(select(ToolDbModel).where(ToolDbModel.id == tool_id)).first()

            if db_tool is None:
                return None

            return FineGrainedAuthorisationTool(**db_tool.model_dump())

    def authorise_tool_for_organisation(self, tool_id: UUID, reporting_org_id: UUID) -> None:
        """Authorise a tool to act for a reporting organisation."""

        tool_authorisation_db = ToolAuthorisationDbModel(tool=tool_id, reporting_org=reporting_org_id)
        with Session(self._engine) as session:
            session.add(tool_authorisation_db)
            session.commit()

    def revoke_tool_authorisation_for_organisation(self, tool_id: UUID, reporting_org_id: UUID) -> None:
        """Revoke a tool's authorisation to act for a reporting organisation."""

        delete_cmd = delete(ToolAuthorisationDbModel).where(
            (ToolAuthorisationDbModel.tool == tool_id)  # type: ignore
            & (ToolAuthorisationDbModel.reporting_org == reporting_org_id)
        )

        with Session(self._engine) as session:
            session.exec(delete_cmd)
            session.commit()
