from uuid import UUID

import pydantic

from .models import FineGrainedAuthorisationRole, FineGrainedAuthorisationRoleAssociation


class FineGrainedAuthorisationUserValidator(pydantic.BaseModel):

    fine_grained_authorisations: list[FineGrainedAuthorisationRoleAssociation] | None

    is_superadmin: bool

    def get_permissions_for_role(self, user_role: FineGrainedAuthorisationRole) -> list[str]:
        permissions = {
            FineGrainedAuthorisationRole.CONTRIBUTOR: ["read-org", "read-dataset", "update-dataset", "delete-dataset"]
        }  # type: dict[FineGrainedAuthorisationRole, list[str]]
        permissions[FineGrainedAuthorisationRole.EDITOR] = [
            *permissions[FineGrainedAuthorisationRole.CONTRIBUTOR],
            "update-org",
            "delete-dataset",
        ]
        permissions[FineGrainedAuthorisationRole.PROVIDER_ADMIN] = [
            *permissions[FineGrainedAuthorisationRole.EDITOR],
            "update-dataset-visibility",
        ]
        permissions[FineGrainedAuthorisationRole.ADMIN] = [
            *permissions[FineGrainedAuthorisationRole.EDITOR],
            "update-org",
            "delete-org",
            "set-org-user-authz",
            "update-dataset-visibility",
        ]
        return permissions[user_role]

    def get_user_role_for_reporting_org(self, reporting_org_id: str | UUID) -> FineGrainedAuthorisationRole:
        reporting_orgs = []  # type: list[FineGrainedAuthorisationRoleAssociation]
        if self.fine_grained_authorisations is not None:
            id_as_uuid = reporting_org_id if isinstance(reporting_org_id, UUID) else UUID(reporting_org_id)
            reporting_orgs = list(filter(lambda x: x.reporting_org == id_as_uuid, self.fine_grained_authorisations))
        if len(reporting_orgs) == 0:
            raise ValueError("User has no association with that reporting_org")
        return reporting_orgs[0].role

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
            permissions_for_org = self.get_permissions_for_role(role_for_org)

            if "read-org" in permissions_for_org:
                return True

        return False

    def get_users_fine_grained_associations(self) -> list[FineGrainedAuthorisationRoleAssociation]:
        if self.fine_grained_authorisations is None:
            return []
        return self.fine_grained_authorisations

    def get_users_reporting_orgs(self) -> list[UUID]:
        if self.fine_grained_authorisations is None:
            return []
        return [fga.reporting_org for fga in self.fine_grained_authorisations]

    def is_user_authorized_for_dataset(self, permission: str, dataset: UUID) -> bool:
        """Verifies whether the user has access to perform the operation described by 'scope' on the dataset"""

        # TODO: lookup the reporting org of the dataset
        # dataset_reporting_org = UUID("01234567-0123-0123-0123-012345678901")

        is_authorised = False

        match permission:
            case "":

                pass
            case "":
                pass

        return is_authorised

    def is_user_authorized_for_reporting_org(self, permission: str, reporting_org: UUID) -> bool:
        """Verifies whether the user is authorised to perform the specified  on the reporting_org"""

        is_authorised = False

        return is_authorised

    def is_user_authorized_for_user(self, permission: str, user_to_act_on: UUID) -> bool:
        """Verifies whether a user has access to perform the operation described by 'scope' on the the user"""
        raise NotImplementedError
