"""add client id to tooldbmodel

Revision ID: b2c6d1170383
Revises: 22951c5f0f0c
Create Date: 2026-04-27 13:06:36.123347

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c6d1170383"
down_revision: Union[str, Sequence[str], None] = "22951c5f0f0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("tooldbmodel", sa.Column("client_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tooldbmodel", "client_id")
