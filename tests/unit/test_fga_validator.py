from uuid import uuid4

from register_your_data_api.auth.fga.fga_validator import FineGrainedAuthorisationUserValidator
from register_your_data_api.auth.fga.models import (
    FineGrainedAuthorisationRole,
    FineGrainedAuthorisationRoleAssociation,
)


def test_provider_admin() -> None:
    """Test validator responses for a provider admin role"""

    user, org1, org2 = uuid4(), uuid4(), uuid4()

    users_fgas = [
        FineGrainedAuthorisationRoleAssociation(
            user=user,
            reporting_org=org1,
            role=FineGrainedAuthorisationRole.PROVIDER_ADMIN,
        )
    ]
    v = FineGrainedAuthorisationUserValidator(
        user_id=user, fine_grained_authorisations=users_fgas, is_superadmin=False
    )

    assert v.get_user_role_for_reporting_org(org1) == FineGrainedAuthorisationRole.PROVIDER_ADMIN
    assert v.get_user_role_for_reporting_org(org2) is None

    assert v.user_can_create_reporting_org()

    assert not v.user_can_update_reporting_org(org1)
    assert not v.user_can_update_reporting_org(org2)

    assert not v.user_can_delete_reporting_org(org1)
    assert not v.user_can_delete_reporting_org(org2)

    assert not v.user_can_create_reporting_org_datasets(org1)
    assert not v.user_can_create_reporting_org_datasets(org2)

    assert v.user_can_update_reporting_org_datasets(org1)
    assert not v.user_can_update_reporting_org_datasets(org2)

    assert v.user_can_update_reporting_org_dataset_visibility(org1)
    assert not v.user_can_update_reporting_org_dataset_visibility(org2)

    assert not v.user_can_delete_reporting_org_datasets(org1)
    assert not v.user_can_delete_reporting_org_datasets(org2)

    assert not v.user_can_modify_user_roles_for_reporting_org(org1)
    assert not v.user_can_modify_user_roles_for_reporting_org(org2)

    assert v.user_can_read_users_reporting_orgs(user)
    assert not v.user_can_read_users_reporting_orgs(uuid4())

    associations = v.get_users_fine_grained_associations()
    assert len(associations) == 1
    assert associations[0].user == user
    assert associations[0].reporting_org == org1
    assert associations[0].role == FineGrainedAuthorisationRole.PROVIDER_ADMIN

    reporting_orgs = v.get_users_reporting_orgs()
    assert len(reporting_orgs) == 1
    assert reporting_orgs[0] == org1
