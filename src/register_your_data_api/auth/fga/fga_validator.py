import collections
import functools
from uuid import UUID

import pydantic

from .models import FineGrainedAuthorisationRole, FineGrainedAuthorisationRoleAssociation, FineGrainedAuthorisationTool


class FineGrainedAuthorisationUserValidator(pydantic.BaseModel):

    user_id: UUID

    client_id: str

    fine_grained_authorisations: list[FineGrainedAuthorisationRoleAssociation] | None

    is_superadmin: bool

    tools: list[FineGrainedAuthorisationTool]

    @functools.cached_property
    def _tool_id_map(self) -> dict[UUID, int]:
        return {tool.id: index for index, tool in enumerate(self.tools)}

    def get_tool_by_id(self, id: UUID) -> FineGrainedAuthorisationTool:
        return self.tools[self._tool_id_map[id]]

    def is_tool_same_as_client(self, tool_id: UUID) -> bool:
        if self.get_tool_by_id(tool_id).client_id == self.client_id:
            return True
        return False

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
        associations = []  # type: list[FineGrainedAuthorisationRoleAssociation]
        if self.fine_grained_authorisations is not None:
            id_as_uuid = reporting_org_id if isinstance(reporting_org_id, UUID) else UUID(reporting_org_id)
            associations = list(filter(lambda x: x.reporting_org == id_as_uuid, self.fine_grained_authorisations))

        if self.is_superadmin:
            return FineGrainedAuthorisationRole.SUPER_ADMIN

        if len(associations) == 0:
            return None

        if len(associations) == 1 and associations[0].role != FineGrainedAuthorisationRole.PROVIDER_ADMIN:
            return associations[0].role

        # Remaining associations should all be provider_admin.  Do a quick check that this is the case.
        if collections.Counter([association.role for association in associations])[
            FineGrainedAuthorisationRole.PROVIDER_ADMIN
        ] != len(associations):
            raise RuntimeError("Validator in an unknown state")

        # If any role has a tool that matches the one the user is logged into then return provider admin.
        if any(
            [
                self.is_tool_same_as_client(association.restricted_to_tool)
                for association in associations
                if association.restricted_to_tool is not None
            ]
        ):
            return FineGrainedAuthorisationRole.PROVIDER_ADMIN

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
        return list(set([fga.reporting_org for fga in self.fine_grained_authorisations]))

    def get_users_provider_admin_tools(self) -> list[FineGrainedAuthorisationTool]:
        return self.tools
