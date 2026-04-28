from uuid import UUID, uuid4

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
    FineGrainedAuthorisationRoleAssociation,
    FineGrainedAuthorisationTool,
)

from ..helpers.setup_and_teardown import setup_db
from ..helpers.utilities import association_lists_equal_ignore_id, gen_random_client_id


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

        session.add(ToolDbModel(id=tool, name="Tool 1", provider="Tool Maker", client_id="JnZ63UFhp03LY5N6"))
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
    assert "Reporting org has user(s) with both provider admin and reporting org roles" in str(excinfo.value)

    associations = fga.get_user_roles_for_org(user_provider, org)
    assert associations
    assert associations[0].role == FineGrainedAuthorisationRole.PROVIDER_ADMIN

    associations = fga.get_user_roles_for_org(user_org, org)
    assert associations
    assert associations[0].role == FineGrainedAuthorisationRole.ADMIN

    with pytest.raises(FineGrainedAuthorisationIntegrityError) as excinfo:
        fga.get_user_roles_for_org(user_both, org)
    assert "User has both reporting org role and a provider admin role" in str(excinfo.value)


def test_provider_roles_are_correctly_applied() -> None:

    setup_db("sqlite:///test.db")

    fga = FineGrainedAuthorisationProviderDb("sqlite:///test.db")
    fga.setup()

    u_o1, u_t1, u_t2, u_bothtools, u_noperms = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    o1, o2 = uuid4(), uuid4()
    t1, t2 = uuid4(), uuid4()
    t1_clientid, t2_clientid = gen_random_client_id(), gen_random_client_id()

    with sqlmodel.Session(fga._engine) as session:
        session.add(
            FineGrainedAuthorisationDbModel(
                user=u_o1, reporting_org=o1, role=FineGrainedAuthorisationRole.ADMIN, id=uuid4()
            )
        )

        session.add(ToolDbModel(id=t1, name="Tool 1", provider="Tool Maker", client_id=t1_clientid))
        session.add(ToolDbModel(id=t2, name="Tool 2", provider="Tool Maker", client_id=t2_clientid))
        session.add(ToolAuthorisationDbModel(tool=t1, reporting_org=o1, id=uuid4()))
        session.add(ToolAuthorisationDbModel(tool=t2, reporting_org=o1, id=uuid4()))
        session.add(ToolAuthorisationDbModel(tool=t2, reporting_org=o2, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=t1, user=u_t1, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=t2, user=u_t2, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=t1, user=u_bothtools, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=t2, user=u_bothtools, id=uuid4()))

        session.commit()

    # fga.get_user_fine_grained_permissions(u_bothtools)

    # Check associations by user.
    ASSOCIATIONS_BY_USER_CHECKS = {
        u_o1: [
            (o1, FineGrainedAuthorisationRole.ADMIN, None),
        ],
        u_t1: [
            (o1, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t1),
        ],
        u_t2: [
            (o1, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2),
            (o2, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2),
        ],
        u_bothtools: [
            (o1, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t1),
            (o1, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2),
            (o2, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2),
        ],
        u_noperms: [],
    }
    for u, data in ASSOCIATIONS_BY_USER_CHECKS.items():
        expected_associations = [
            FineGrainedAuthorisationRoleAssociation(user=u, reporting_org=o, role=r, restricted_to_tool=t, id=uuid4())
            for o, r, t in data  # type: ignore[attr-defined]
        ]
        assert association_lists_equal_ignore_id(fga.get_user_fine_grained_permissions(u), expected_associations)

    # Check associations by org.
    ASSOCIATIONS_BY_ORG_CHECKS = {
        o1: [
            (u_o1, FineGrainedAuthorisationRole.ADMIN, None),
            (u_t1, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t1),
            (u_t2, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2),
            (u_bothtools, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t1),
            (u_bothtools, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2),
        ],
        o2: [
            (u_t2, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2),
            (u_bothtools, FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2),
        ],
    }
    for o, data in ASSOCIATIONS_BY_ORG_CHECKS.items():
        expected_associations = [
            FineGrainedAuthorisationRoleAssociation(user=u, reporting_org=o, role=r, restricted_to_tool=t, id=uuid4())
            for u, r, t in data  # type: ignore[attr-defined]
        ]
        assert association_lists_equal_ignore_id(fga.get_user_associations_for_org(o), expected_associations)

    # Check associations by user and org
    ASSOCIATIONS_BY_USER_AND_ORG_CHECKS = {
        (u_o1, o1): [(FineGrainedAuthorisationRole.ADMIN, None)],
        (u_t1, o1): [(FineGrainedAuthorisationRole.PROVIDER_ADMIN, t1)],
        (u_t2, o1): [(FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2)],
        (u_t2, o2): [(FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2)],
        (u_bothtools, o1): [
            (FineGrainedAuthorisationRole.PROVIDER_ADMIN, t1),
            (FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2),
        ],
        (u_bothtools, o2): [(FineGrainedAuthorisationRole.PROVIDER_ADMIN, t2)],
        (u_noperms, o1): [],
        (u_noperms, o2): [],
    }
    for (u, o), data in ASSOCIATIONS_BY_USER_AND_ORG_CHECKS.items():
        expected_associations = [
            FineGrainedAuthorisationRoleAssociation(user=u, reporting_org=o, role=r, restricted_to_tool=t, id=uuid4())
            for r, t in data  # type: ignore[attr-defined]
        ]
        assert association_lists_equal_ignore_id(fga.get_user_roles_for_org(u, o), expected_associations)


def test_tool_lists_correctly_fetched() -> None:
    setup_db("sqlite:///test.db")

    fga = FineGrainedAuthorisationProviderDb("sqlite:///test.db")
    fga.setup()

    tool1, tool2 = UUID("0415675e-8767-42e2-9f51-b44211b09aa8"), UUID("d3ef34c9-3dd2-445e-aeff-644853753c43")
    user_tool1, user_tool2, user_both_tools = uuid4(), uuid4(), uuid4()

    with sqlmodel.Session(fga._engine) as session:
        session.add(ToolDbModel(id=tool1, name="Tool 1", provider="Tool Maker", client_id="JnZ63UFhp03LY5N6"))
        session.add(ToolDbModel(id=tool2, name="Tool 2", provider="Tool Maker", client_id="v4amDn43kirvBmB9"))
        session.add(ToolAdminUserDbModel(tool=tool1, user=user_tool1, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=tool2, user=user_tool2, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=tool1, user=user_both_tools, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=tool2, user=user_both_tools, id=uuid4()))

        session.commit()

    # Check all tool list.
    tools = fga.get_all_tools()
    tools.sort(key=lambda x: x.id)

    assert len(tools) == 2
    assert tools[0] == FineGrainedAuthorisationTool(
        id=tool1, name="Tool 1", provider="Tool Maker", client_id="JnZ63UFhp03LY5N6"
    )
    assert tools[1] == FineGrainedAuthorisationTool(
        id=tool2, name="Tool 2", provider="Tool Maker", client_id="v4amDn43kirvBmB9"
    )

    # Check tool list for each user.
    tools = fga.get_tools_for_user(user_tool1)
    assert len(tools) == 1
    assert tools[0] == FineGrainedAuthorisationTool(
        id=tool1, name="Tool 1", provider="Tool Maker", client_id="JnZ63UFhp03LY5N6"
    )

    tools = fga.get_tools_for_user(user_tool2)
    assert len(tools) == 1
    assert tools[0] == FineGrainedAuthorisationTool(
        id=tool2, name="Tool 2", provider="Tool Maker", client_id="v4amDn43kirvBmB9"
    )

    tools = fga.get_tools_for_user(user_both_tools)
    tools.sort(key=lambda x: x.id)
    assert len(tools) == 2
    assert tools[0] == FineGrainedAuthorisationTool(
        id=tool1, name="Tool 1", provider="Tool Maker", client_id="JnZ63UFhp03LY5N6"
    )
    assert tools[1] == FineGrainedAuthorisationTool(
        id=tool2, name="Tool 2", provider="Tool Maker", client_id="v4amDn43kirvBmB9"
    )


def test_tool_admin_users_can_be_detected() -> None:

    setup_db("sqlite:///test.db")

    fga = FineGrainedAuthorisationProviderDb("sqlite:///test.db")
    fga.setup()

    u_o1, u_t1, u_t2, u_bothtools, u_noperms = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    o1, o2 = uuid4(), uuid4()
    t1, t2 = uuid4(), uuid4()
    t1_clientid, t2_clientid = gen_random_client_id(), gen_random_client_id()

    with sqlmodel.Session(fga._engine) as session:
        session.add(
            FineGrainedAuthorisationDbModel(
                user=u_o1, reporting_org=o1, role=FineGrainedAuthorisationRole.ADMIN, id=uuid4()
            )
        )

        session.add(ToolDbModel(id=t1, name="Tool 1", provider="Tool Maker", client_id=t1_clientid))
        session.add(ToolDbModel(id=t2, name="Tool 2", provider="Tool Maker", client_id=t2_clientid))
        session.add(ToolAuthorisationDbModel(tool=t1, reporting_org=o1, id=uuid4()))
        session.add(ToolAuthorisationDbModel(tool=t2, reporting_org=o1, id=uuid4()))
        session.add(ToolAuthorisationDbModel(tool=t2, reporting_org=o2, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=t1, user=u_t1, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=t2, user=u_t2, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=t1, user=u_bothtools, id=uuid4()))
        session.add(ToolAdminUserDbModel(tool=t2, user=u_bothtools, id=uuid4()))

        session.commit()

    assert not fga.is_user_a_tool_adminuser(u_o1)
    assert fga.is_user_a_tool_adminuser(u_t1)
    assert fga.is_user_a_tool_adminuser(u_t2)
    assert fga.is_user_a_tool_adminuser(u_bothtools)
    assert not fga.is_user_a_tool_adminuser(u_noperms)
