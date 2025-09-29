import pytest
import sqlmodel
from uuid import uuid4, UUID

from register_your_data_api.authz.fga_provider_pgdb import (
    FineGrainedAuthorisationDbModel,
    FineGrainedAuthorisationProviderPgDb,
    Role,
    SuperAdminUserDbModel,
)


def test():
    """Simple test of FGA provider DB using SQLite in-memory DB"""
    fga = FineGrainedAuthorisationProviderPgDb("sqlite://")
    fga.setup()

    user1, user2, user3 = uuid4(), uuid4(), uuid4()
    org1, org2 = uuid4(), uuid4()

    with sqlmodel.Session(fga._engine) as session:
        # Add user 1 roles.
        session.add(FineGrainedAuthorisationDbModel(user=user1, reporting_org=org1, role=Role.EDITOR, id=uuid4()))
        session.add(FineGrainedAuthorisationDbModel(user=user1, reporting_org=org2, role=Role.ADMIN, id=uuid4()))

        # Add user 2 roles.
        session.add(FineGrainedAuthorisationDbModel(user=user2, reporting_org=org1, role=Role.ADMIN, id=uuid4()))

        # Add user 3 roles.
        session.add(SuperAdminUserDbModel(user=user3, id=uuid4(), is_superadmin=True))
        session.commit()

    # Check user 1 permissions.
    perm_check = fga.get_user_fine_grained_permissions(user1)
    assert len(perm_check) == 2
    if perm_check[0].reporting_org == org1:
        assert perm_check[0].role == Role.EDITOR
        assert perm_check[1].role == Role.ADMIN
        assert perm_check[1].reporting_org == org2
    elif perm_check[0].reporting_org == org2:
        assert perm_check[0].role == Role.ADMIN
        assert perm_check[1].role == Role.EDITOR
        assert perm_check[1].reporting_org == org1
    else:
        assert False
    assert fga.is_user_a_superadmin(user1) == False

    # Check user 2 permissions.
    perm_check = fga.get_user_fine_grained_permissions(user2)
    assert len(perm_check) == 1
    assert perm_check[0].reporting_org == org1
    assert perm_check[0].role == Role.ADMIN
    assert fga.is_user_a_superadmin(user2) == False

    # Check user 3 permissions
    perm_check = fga.get_user_fine_grained_permissions(user3)
    assert len(perm_check) == 0
    assert fga.is_user_a_superadmin(user3) == True
