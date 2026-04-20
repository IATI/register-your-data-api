from uuid import UUID

import pydantic

from .models import FineGrainedAuthorisationRole, FineGrainedAuthorisationRoleAssociation


class FineGrainedAuthorisationUserValidator(pydantic.BaseModel):

    user_id: UUID

    fine_grained_authorisations: list[FineGrainedAuthorisationRoleAssociation] | None

    is_superadmin: bool

    def get_permissions_for_role(self, user_role: FineGrainedAuthorisationRole) -> list[str]:
        permissions: dict[FineGrainedAuthorisationRole, list[str]] = {
            FineGrainedAuthorisationRole.CONTRIBUTOR_PENDING: [],
            FineGrainedAuthorisationRole.CONTRIBUTOR: ["read-org", "create-dataset", "read-dataset", "update-dataset"],
        }
        permissions[FineGrainedAuthorisationRole.EDITOR] = [
            *permissions[FineGrainedAuthorisationRole.CONTRIBUTOR],
            "update-org",
            "delete-dataset",
        ]
        permissions[FineGrainedAuthorisationRole.PROVIDER_ADMIN] = [
            "read-org",
            "update-org",
            "read-dataset",
            "create-dataset",
            "update-dataset",
            "update-dataset-visibility",
            "delete-dataset",
        ]
        permissions[FineGrainedAuthorisationRole.ADMIN] = [
            *permissions[FineGrainedAuthorisationRole.EDITOR],
            "update-org",
            "delete-org",
            "set-org-user-authz",
            "update-dataset-visibility",
        ]
        return permissions[user_role]

    def get_user_role_for_reporting_org(self, reporting_org_id: str | UUID) -> FineGrainedAuthorisationRole | None:
        reporting_orgs = []  # type: list[FineGrainedAuthorisationRoleAssociation]
        if self.fine_grained_authorisations is not None:
            id_as_uuid = reporting_org_id if isinstance(reporting_org_id, UUID) else UUID(reporting_org_id)
            reporting_orgs = list(filter(lambda x: x.reporting_org == id_as_uuid, self.fine_grained_authorisations))

        if len(reporting_orgs) >= 1:
            return reporting_orgs[0].role

        if self.is_superadmin:
            return FineGrainedAuthorisationRole.SUPER_ADMIN

        return None

    def user_can_create_reporting_org(self) -> bool:
        return True

    def user_can_read_reporting_org(self, reporting_org_id: UUID) -> bool:

        if self.is_superadmin:
            return True

        role_for_org = self.get_user_role_for_reporting_org(reporting_org_id)

        if role_for_org is not None:
            # given the current mapping between roles and permissions, we could
            # just check the user is associated with a reporting_org, but to
            # accommodate future roles that may give users permission to (say)
            # delete without reading, we pull in permissions and check for
            # read-org
            if "read-org" in self.get_permissions_for_role(role_for_org):
                return True

        return False

    def user_can_update_reporting_org(self, reporting_org_id: UUID) -> bool:

        if self.is_superadmin:
            return True

        role_for_org = self.get_user_role_for_reporting_org(reporting_org_id)

        if role_for_org is not None:
            if "update-org" in self.get_permissions_for_role(role_for_org):
                return True

        return False

    def user_can_delete_reporting_org(self, reporting_org_id: UUID) -> bool:

        if self.is_superadmin:
            return True

        role_for_org = self.get_user_role_for_reporting_org(reporting_org_id)

        if role_for_org is not None:
            if "delete-org" in self.get_permissions_for_role(role_for_org):
                return True

        return False

    def user_can_create_reporting_org_datasets(self, reporting_org_id: UUID) -> bool:

        if self.is_superadmin:
            return True

        role_for_org = self.get_user_role_for_reporting_org(reporting_org_id)

        if role_for_org is not None:
            if "create-dataset" in self.get_permissions_for_role(role_for_org):
                return True

        return False

    def user_can_read_reporting_org_datasets(self, reporting_org_id: UUID) -> bool:

        if self.is_superadmin:
            return True

        role_for_org = self.get_user_role_for_reporting_org(reporting_org_id)

        if role_for_org is not None:
            if "read-dataset" in self.get_permissions_for_role(role_for_org):
                return True

        return False

    def user_can_update_reporting_org_datasets(self, reporting_org_id: UUID) -> bool:

        if self.is_superadmin:
            return True

        role_for_org = self.get_user_role_for_reporting_org(reporting_org_id)

        if role_for_org is not None:
            if "update-dataset" in self.get_permissions_for_role(role_for_org):
                return True

        return False

    def user_can_update_reporting_org_dataset_visibility(self, reporting_org_id: UUID) -> bool:

        if self.is_superadmin:
            return True

        role_for_org = self.get_user_role_for_reporting_org(reporting_org_id)

        if role_for_org is not None:
            if "update-dataset-visibility" in self.get_permissions_for_role(role_for_org):
                return True

        return False

    def user_can_delete_reporting_org_datasets(self, reporting_org_id: UUID) -> bool:

        if self.is_superadmin:
            return True

        role_for_org = self.get_user_role_for_reporting_org(reporting_org_id)

        if role_for_org is not None:
            if "delete-dataset" in self.get_permissions_for_role(role_for_org):
                return True

        return False

    def user_can_modify_user_roles_for_reporting_org(self, reporting_org_id: UUID) -> bool:
        if self.is_superadmin:
            return True

        role_for_org = self.get_user_role_for_reporting_org(reporting_org_id)

        if role_for_org is not None:
            if "set-org-user-authz" in self.get_permissions_for_role(role_for_org):
                return True

        return False

    def user_can_read_users_reporting_orgs(self, user_id: UUID) -> bool:
        if self.is_superadmin:
            return True

        return self.user_id == user_id

    def get_users_fine_grained_associations(self) -> list[FineGrainedAuthorisationRoleAssociation]:
        if self.fine_grained_authorisations is None:
            return []
        return self.fine_grained_authorisations

    def get_users_reporting_orgs(self) -> list[UUID]:
        if self.fine_grained_authorisations is None:
            return []
        return [fga.reporting_org for fga in self.fine_grained_authorisations]
