from uuid import uuid4

from register_your_data_api.auth.fga.fga_validator import FineGrainedAuthorisationUserValidator
from register_your_data_api.auth.fga.models import (
    FineGrainedAuthorisationRole,
    FineGrainedAuthorisationRoleAssociation,
    FineGrainedAuthorisationTool,
)

from ..helpers.utilities import association_lists_equal_ignore_id, gen_random_client_id


def test_editor() -> None:
    """Test validator responses for the editor role"""

    user, org1, org2 = uuid4(), uuid4(), uuid4()
    users_fgas = [
        FineGrainedAuthorisationRoleAssociation(
            user=user,
            reporting_org=org1,
            role=FineGrainedAuthorisationRole.EDITOR,
        ),
    ]

    v = FineGrainedAuthorisationUserValidator(
        user_id=user,
        fine_grained_authorisations=users_fgas,
        is_superadmin=False,
        tools=[],
        client_id=gen_random_client_id(),
    )

    assert v.get_user_role_for_reporting_org(org1) == FineGrainedAuthorisationRole.EDITOR
    assert v.get_user_role_for_reporting_org(org2) is None

    assert v.user_can_create_reporting_org()

    assert v.user_can_read_reporting_org(org1)
    assert not v.user_can_read_reporting_org(org2)

    assert v.user_can_update_reporting_org(org1)
    assert not v.user_can_update_reporting_org(org2)

    assert not v.user_can_delete_reporting_org(org1)
    assert not v.user_can_delete_reporting_org(org2)

    assert v.user_can_create_reporting_org_datasets(org1)
    assert not v.user_can_create_reporting_org_datasets(org2)

    assert v.user_can_read_reporting_org_datasets(org1)
    assert not v.user_can_read_reporting_org_datasets(org2)

    assert v.user_can_update_reporting_org_datasets(org1)
    assert not v.user_can_update_reporting_org_datasets(org2)

    assert v.user_can_update_reporting_org_dataset_visibility(org1)
    assert not v.user_can_update_reporting_org_dataset_visibility(org2)

    assert v.user_can_delete_reporting_org_datasets(org1)
    assert not v.user_can_delete_reporting_org_datasets(org2)

    assert not v.user_can_modify_user_roles_for_reporting_org(org1)
    assert not v.user_can_modify_user_roles_for_reporting_org(org2)

    assert v.user_can_read_users_reporting_orgs(user)
    assert not v.user_can_read_users_reporting_orgs(uuid4())


def test_provider_admin() -> None:
    """Test validator responses for a provider admin role"""

    # This user has access to org1 via two tools, and no access to org 2.
    user, org1, org2 = uuid4(), uuid4(), uuid4()
    tool1 = FineGrainedAuthorisationTool(
        id=uuid4(), name="Tool 1", provider="Tool Maker", client_id=gen_random_client_id()
    )
    tool2 = FineGrainedAuthorisationTool(
        id=uuid4(), name="Tool 1", provider="Tool Maker", client_id=gen_random_client_id()
    )
    users_fgas = [
        FineGrainedAuthorisationRoleAssociation(
            user=user,
            reporting_org=org1,
            role=FineGrainedAuthorisationRole.PROVIDER_ADMIN,
            restricted_to_tool=tool1.id,
        ),
        FineGrainedAuthorisationRoleAssociation(
            user=user,
            reporting_org=org1,
            role=FineGrainedAuthorisationRole.PROVIDER_ADMIN,
            restricted_to_tool=tool2.id,
        ),
    ]

    # Test validator when the end user is accessing RYD via the same client ID as tool 1.
    v = FineGrainedAuthorisationUserValidator(
        user_id=user,
        fine_grained_authorisations=users_fgas,
        is_superadmin=False,
        tools=[tool1, tool2],
        client_id=tool1.client_id,
    )

    assert v.get_user_role_for_reporting_org(org1) == FineGrainedAuthorisationRole.PROVIDER_ADMIN
    assert v.get_user_role_for_reporting_org(org2) is None

    assert v.user_can_create_reporting_org()

    assert v.user_can_update_reporting_org(org1)
    assert not v.user_can_update_reporting_org(org2)

    assert not v.user_can_delete_reporting_org(org1)
    assert not v.user_can_delete_reporting_org(org2)

    assert v.user_can_create_reporting_org_datasets(org1)
    assert not v.user_can_create_reporting_org_datasets(org2)

    assert v.user_can_update_reporting_org_datasets(org1)
    assert not v.user_can_update_reporting_org_datasets(org2)

    assert v.user_can_update_reporting_org_dataset_visibility(org1)
    assert not v.user_can_update_reporting_org_dataset_visibility(org2)

    assert v.user_can_delete_reporting_org_datasets(org1)
    assert not v.user_can_delete_reporting_org_datasets(org2)

    assert not v.user_can_modify_user_roles_for_reporting_org(org1)
    assert not v.user_can_modify_user_roles_for_reporting_org(org2)

    assert v.user_can_read_users_reporting_orgs(user)
    assert not v.user_can_read_users_reporting_orgs(uuid4())

    # Test validator when the end user is accessing RYD via the same client ID as tool 2.
    v = FineGrainedAuthorisationUserValidator(
        user_id=user,
        fine_grained_authorisations=users_fgas,
        is_superadmin=False,
        tools=[tool1, tool2],
        client_id=tool2.client_id,
    )

    assert v.get_user_role_for_reporting_org(org1) == FineGrainedAuthorisationRole.PROVIDER_ADMIN
    assert v.get_user_role_for_reporting_org(org2) is None

    assert v.user_can_create_reporting_org()

    assert v.user_can_update_reporting_org(org1)
    assert not v.user_can_update_reporting_org(org2)

    assert not v.user_can_delete_reporting_org(org1)
    assert not v.user_can_delete_reporting_org(org2)

    assert v.user_can_create_reporting_org_datasets(org1)
    assert not v.user_can_create_reporting_org_datasets(org2)

    assert v.user_can_update_reporting_org_datasets(org1)
    assert not v.user_can_update_reporting_org_datasets(org2)

    assert v.user_can_update_reporting_org_dataset_visibility(org1)
    assert not v.user_can_update_reporting_org_dataset_visibility(org2)

    assert v.user_can_delete_reporting_org_datasets(org1)
    assert not v.user_can_delete_reporting_org_datasets(org2)

    assert not v.user_can_modify_user_roles_for_reporting_org(org1)
    assert not v.user_can_modify_user_roles_for_reporting_org(org2)

    assert v.user_can_read_users_reporting_orgs(user)
    assert not v.user_can_read_users_reporting_orgs(uuid4())

    # Test validator when the end user is accessing RYD via a client id that doesn't
    # match either of the provider admin tools.
    v = FineGrainedAuthorisationUserValidator(
        user_id=user,
        fine_grained_authorisations=users_fgas,
        is_superadmin=False,
        tools=[tool1, tool2],
        client_id=gen_random_client_id(),
    )

    assert v.get_user_role_for_reporting_org(org1) is None
    assert v.get_user_role_for_reporting_org(org2) is None

    assert v.user_can_create_reporting_org()

    assert not v.user_can_update_reporting_org(org1)
    assert not v.user_can_update_reporting_org(org2)

    assert not v.user_can_delete_reporting_org(org1)
    assert not v.user_can_delete_reporting_org(org2)

    assert not v.user_can_create_reporting_org_datasets(org1)
    assert not v.user_can_create_reporting_org_datasets(org2)

    assert not v.user_can_update_reporting_org_datasets(org1)
    assert not v.user_can_update_reporting_org_datasets(org2)

    assert not v.user_can_update_reporting_org_dataset_visibility(org1)
    assert not v.user_can_update_reporting_org_dataset_visibility(org2)

    assert not v.user_can_delete_reporting_org_datasets(org1)
    assert not v.user_can_delete_reporting_org_datasets(org2)

    assert not v.user_can_modify_user_roles_for_reporting_org(org1)
    assert not v.user_can_modify_user_roles_for_reporting_org(org2)

    assert v.user_can_read_users_reporting_orgs(user)
    assert not v.user_can_read_users_reporting_orgs(uuid4())

    assert association_lists_equal_ignore_id(v.get_users_fine_grained_associations(), users_fgas)

    reporting_orgs = v.get_users_reporting_orgs()
    assert len(reporting_orgs) == 1
    assert reporting_orgs[0] == org1
