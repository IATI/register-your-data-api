from uuid import uuid4

import sqlmodel

from register_your_data_api.auth.fga.fga_provider_db import (
    FineGrainedAuthorisationDbModel,
    FineGrainedAuthorisationProviderDb,
    SuperAdminUserDbModel,
)
from register_your_data_api.auth.fga.models import (
    FineGrainedAuthorisationRole,
)


def test_assignment_of_permissions() -> None:
    """Simple test of FGA provider DB using SQLite in-memory DB"""
    fga = FineGrainedAuthorisationProviderDb("sqlite://")
    fga.setup()

    user1, user2, user3 = uuid4(), uuid4(), uuid4()
    org1, org2 = uuid4(), uuid4()

    with sqlmodel.Session(fga._engine) as session:
        # Add user 1 roles.
        session.add(
            FineGrainedAuthorisationDbModel(
                user=user1, reporting_org=org1, role=FineGrainedAuthorisationRole.EDITOR, id=uuid4()
            )
        )
        session.add(
            FineGrainedAuthorisationDbModel(
                user=user1, reporting_org=org2, role=FineGrainedAuthorisationRole.ADMIN, id=uuid4()
            )
        )

        # Add user 2 roles.
        session.add(
            FineGrainedAuthorisationDbModel(
                user=user2, reporting_org=org1, role=FineGrainedAuthorisationRole.ADMIN, id=uuid4()
            )
        )

        # Add user 3 roles.
        session.add(SuperAdminUserDbModel(user=user3, id=uuid4(), is_superadmin=True))
        session.commit()

    # Check user 1 permissions.
    perm_check = fga.get_user_fine_grained_permissions(user1)
    assert len(perm_check) == 2
    if perm_check[0].reporting_org == org1:
        assert perm_check[0].role == FineGrainedAuthorisationRole.EDITOR
        assert perm_check[1].role == FineGrainedAuthorisationRole.ADMIN
        assert perm_check[1].reporting_org == org2
    elif perm_check[0].reporting_org == org2:
        assert perm_check[0].role == FineGrainedAuthorisationRole.ADMIN
        assert perm_check[1].role == FineGrainedAuthorisationRole.EDITOR
        assert perm_check[1].reporting_org == org1
    else:
        assert False
    assert fga.is_user_a_superadmin(user1) is False

    # Check user 2 permissions.
    perm_check = fga.get_user_fine_grained_permissions(user2)
    assert len(perm_check) == 1
    assert perm_check[0].reporting_org == org1
    assert perm_check[0].role == FineGrainedAuthorisationRole.ADMIN
    assert fga.is_user_a_superadmin(user2) is False

    # Check user 3 permissions
    perm_check = fga.get_user_fine_grained_permissions(user3)
    assert len(perm_check) == 0
    assert fga.is_user_a_superadmin(user3) is True
