from uuid import uuid4

import pytest
import sqlmodel

from register_your_data_api.auth.fga.fga_provider import FineGrainedAuthorisationIntegrityError
from register_your_data_api.auth.fga.fga_provider_db import (
    FineGrainedAuthorisationDbModel,
    FineGrainedAuthorisationProviderDb,
    SuperAdminUserDbModel,
    ToolAdminUserDbModel,
    ToolAuthorisationDbModel,
    ToolDbModel,
)
from register_your_data_api.auth.fga.models import (
    FineGrainedAuthorisationRole,
)

from ..helpers.setup_and_teardown import setup_db


def test_assignment_of_permissions() -> None:
    """Simple test of FGA provider DB using SQLite in-memory DB"""

    setup_db("sqlite:///test.db")

    fga = FineGrainedAuthorisationProviderDb("sqlite:///test.db")
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


def test_fga_fetch_admins() -> None:
    """Simple test of FGA provider DB using SQLite in-memory DB"""

    fga = FineGrainedAuthorisationProviderDb("sqlite:///:memory:")
    fga.setup()
    sqlmodel.SQLModel.metadata.create_all(fga._engine)

    u1, u2, u3 = uuid4(), uuid4(), uuid4()
    o1, o2 = uuid4(), uuid4()

    with sqlmodel.Session(fga._engine) as session:
        session.add(
            FineGrainedAuthorisationDbModel(
                user=u1, reporting_org=o1, role=FineGrainedAuthorisationRole.EDITOR, id=uuid4()
            )
        )
        session.add(
            FineGrainedAuthorisationDbModel(
                user=u1, reporting_org=o2, role=FineGrainedAuthorisationRole.CONTRIBUTOR, id=uuid4()
            )
        )

        session.add(
            FineGrainedAuthorisationDbModel(
                user=u2, reporting_org=o1, role=FineGrainedAuthorisationRole.ADMIN, id=uuid4()
            )
        )
        session.add(
            FineGrainedAuthorisationDbModel(
                user=u3, reporting_org=o1, role=FineGrainedAuthorisationRole.ADMIN, id=uuid4()
            )
        )
        session.commit()

    fga_admins_org_1 = fga.get_admin_users_for_org(o1)

    assert len(fga_admins_org_1) == 2

    fga_admins_org_2 = fga.get_admin_users_for_org(o2)

    assert len(fga_admins_org_2) == 0


def test_provider_users_cannot_have_role_for_org() -> None:
    """Test that a user for a tool cannot also have a role (e.g., ADMIN) for an org"""

    setup_db("sqlite:///test.db")

    fga = FineGrainedAuthorisationProviderDb("sqlite:///test.db")
    fga.setup()

    user_provider, user_org, user_both = uuid4(), uuid4(), uuid4()
    org = uuid4()
    tool = uuid4()

    with sqlmodel.Session(fga._engine) as session:
        session.add(
            FineGrainedAuthorisationDbModel(
                user=user_org, reporting_org=org, role=FineGrainedAuthorisationRole.ADMIN, id=uuid4()
            )
        )
        session.add(
            FineGrainedAuthorisationDbModel(
                user=user_both, reporting_org=org, role=FineGrainedAuthorisationRole.ADMIN, id=uuid4()
            )
        )

        session.add(ToolDbModel(id=tool, name="Tool 1", provider="Tool Maker"))
        session.add(ToolAuthorisationDbModel(tool=tool, reporting_org=org, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=tool, user=user_provider, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=tool, user=user_both, id=uuid4()))

        session.commit()

    assert len(fga.get_user_fine_grained_permissions(user_provider)) == 1
    assert len(fga.get_user_fine_grained_permissions(user_org)) == 1
    with pytest.raises(FineGrainedAuthorisationIntegrityError) as excinfo:
        fga.get_user_fine_grained_permissions(user_both)
    assert "User has both reporting org role(s) and is a tool user" in str(excinfo.value)

    with pytest.raises(FineGrainedAuthorisationIntegrityError) as excinfo:
        fga.get_user_associations_for_org(org)
    assert "Reporting org has user(s) that have multiple conflicting roles" in str(excinfo.value)

    association = fga.get_user_role_for_org(user_provider, org)
    assert association is not None
    assert association.role == FineGrainedAuthorisationRole.PROVIDER_ADMIN

    association = fga.get_user_role_for_org(user_org, org)
    assert association is not None
    assert association.role == FineGrainedAuthorisationRole.ADMIN

    with pytest.raises(FineGrainedAuthorisationIntegrityError) as excinfo:
        fga.get_user_role_for_org(user_both, org)
    assert "User has both reporting org role and a provider admin role" in str(excinfo.value)


def test_provider_roles_are_correctly_applied() -> None:
    """Test FGA provider authorisations using SQLite in-memory DB"""

    setup_db("sqlite:///test.db")

    fga = FineGrainedAuthorisationProviderDb("sqlite:///test.db")
    fga.setup()

    user_org1, user_tool1, user_tool2, user_both_tools, user_no_perms = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    org1, org2 = uuid4(), uuid4()
    tool1, tool2 = uuid4(), uuid4()

    with sqlmodel.Session(fga._engine) as session:
        session.add(
            FineGrainedAuthorisationDbModel(
                user=user_org1, reporting_org=org1, role=FineGrainedAuthorisationRole.ADMIN, id=uuid4()
            )
        )

        session.add(ToolDbModel(id=tool1, name="Tool 1", provider="Tool Maker"))
        session.add(ToolDbModel(id=tool2, name="Tool 2", provider="Tool Maker"))
        session.add(ToolAuthorisationDbModel(tool=tool1, reporting_org=org1, id=uuid4()))
        session.add(ToolAuthorisationDbModel(tool=tool2, reporting_org=org2, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=tool1, user=user_tool1, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=tool2, user=user_tool2, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=tool1, user=user_both_tools, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=tool2, user=user_both_tools, id=uuid4()))

        session.commit()

    # Check user permissions.
    associations = fga.get_user_fine_grained_permissions(user_org1)
    assert len(associations) == 1
    assert associations[0].reporting_org == org1
    assert associations[0].role == FineGrainedAuthorisationRole.ADMIN

    associations = fga.get_user_fine_grained_permissions(user_tool1)
    assert len(associations) == 1
    assert associations[0].reporting_org == org1
    assert associations[0].role == FineGrainedAuthorisationRole.PROVIDER_ADMIN

    associations = fga.get_user_fine_grained_permissions(user_tool2)
    assert len(associations) == 1
    assert associations[0].reporting_org == org2
    assert associations[0].role == FineGrainedAuthorisationRole.PROVIDER_ADMIN

    associations = fga.get_user_fine_grained_permissions(user_both_tools)
    assert len(associations) == 2
    assert all([association.role == FineGrainedAuthorisationRole.PROVIDER_ADMIN for association in associations])
    assert org1 in [association.reporting_org for association in associations]
    assert org2 in [association.reporting_org for association in associations]

    associations = fga.get_user_fine_grained_permissions(user_no_perms)
    assert len(associations) == 0

    # Check associations each user has for each org
    USER_ORG_ASSOCIATION_CHECKS = [
        (user_org1, org1, FineGrainedAuthorisationRole.ADMIN),
        (user_tool1, org1, FineGrainedAuthorisationRole.PROVIDER_ADMIN),
        (user_tool2, org1, None),
        (user_both_tools, org1, FineGrainedAuthorisationRole.PROVIDER_ADMIN),
        (user_no_perms, org1, None),
        (user_org1, org2, None),
        (user_tool1, org2, None),
        (user_tool2, org2, FineGrainedAuthorisationRole.PROVIDER_ADMIN),
        (user_both_tools, org2, FineGrainedAuthorisationRole.PROVIDER_ADMIN),
        (user_no_perms, org2, None),
    ]

    for check in USER_ORG_ASSOCIATION_CHECKS:
        association = fga.get_user_role_for_org(check[0], check[1])
        if check[2] is None:
            assert association is None
        else:
            assert association is not None
            assert association.user == check[0]
            assert association.reporting_org == check[1]
            assert association.role == check[2]

    # Check user associations for org.
    associations_by_user = {association.user: association for association in fga.get_user_associations_for_org(org1)}
    assert len(associations_by_user) == 3
    assert user_org1 in associations_by_user
    assert associations_by_user[user_org1].role == FineGrainedAuthorisationRole.ADMIN
    assert user_tool1 in associations_by_user
    assert associations_by_user[user_tool1].role == FineGrainedAuthorisationRole.PROVIDER_ADMIN
    assert user_both_tools in associations_by_user
    assert associations_by_user[user_both_tools].role == FineGrainedAuthorisationRole.PROVIDER_ADMIN

    associations_by_user = {association.user: association for association in fga.get_user_associations_for_org(org2)}
    assert len(associations_by_user) == 2
    assert user_tool2 in associations_by_user
    assert associations_by_user[user_tool2].role == FineGrainedAuthorisationRole.PROVIDER_ADMIN
    assert user_both_tools in associations_by_user
    assert associations_by_user[user_both_tools].role == FineGrainedAuthorisationRole.PROVIDER_ADMIN
