from abc import ABC, abstractmethod
from uuid import UUID

from .models import FineGrainedAuthorisationRoleAssociation, FineGrainedAuthorisationTool


class FineGrainedAuthorisationIntegrityError(Exception):
    pass


class FineGrainedAuthorisationProvider(ABC):

    @abstractmethod
    def setup(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_user_fine_grained_permissions(self, user: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        """Returns a list of all the user's fine grained access roles"""
        raise NotImplementedError

    @abstractmethod
    def get_user_associations_for_org(self, reporting_org: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        """Returns a list of all the user-role-org associations for the specified reporting org"""
        raise NotImplementedError

    @abstractmethod
    def get_user_roles_for_org(self, user: UUID, org: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        """Returns a list of all the user's fine grained access roles for a specific organisation"""
        raise NotImplementedError

    @abstractmethod
    def get_admin_users_for_org(self, org: UUID) -> list[FineGrainedAuthorisationRoleAssociation]:
        """Returns a list of all the admin users for a specific organisation"""
        raise NotImplementedError

    @abstractmethod
    def is_user_a_superadmin(self, user: UUID) -> bool:
        """Returns True if the user is a superadmin, else False"""
        raise NotImplementedError

    @abstractmethod
    def create_user_fine_grained_authorisation(
        self, user_reporting_org_role_association: FineGrainedAuthorisationRoleAssociation
    ) -> None:
        """Creates a new user <-> reporting org fine grained role association"""
        raise NotImplementedError

    @abstractmethod
    def update_user_role_for_org(self, user_reporting_org_role: FineGrainedAuthorisationRoleAssociation) -> None:
        """Updates an existing user <-> reporting org fine grained role association"""
        raise NotImplementedError

    @abstractmethod
    def delete_user_role_for_org(self, user_reporting_org_role: FineGrainedAuthorisationRoleAssociation) -> None:
        """Deletes the user's role for the reporting org"""
        raise NotImplementedError

    @abstractmethod
    def delete_all_fine_grained_authorisations_for_user(self, user: UUID) -> None:
        """Deletes all fine grained role associations for a user"""
        raise NotImplementedError

    @abstractmethod
    def delete_all_fine_grained_authorisations_for_org(self, org: UUID) -> None:
        """Deletes all fine grained role associations for an organisation"""
        raise NotImplementedError

    @abstractmethod
    def get_all_tools(self) -> list[FineGrainedAuthorisationTool]:
        """Get a list of all the tools stored in the database."""
        raise NotImplementedError

    @abstractmethod
    def get_tools_for_user(self, user: UUID) -> list[FineGrainedAuthorisationTool]:
        """Get a list of all the tools for which the user is an admin user."""
        raise NotImplementedError
