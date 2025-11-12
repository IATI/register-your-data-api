"""Added CONTRIBUTOR_PENDING state

Revision ID: ec6411d99e0b
Revises: 3f9b7ff8bb73
Create Date: 2025-11-04 13:34:40.859834

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ec6411d99e0b"
down_revision: Union[str, Sequence[str], None] = "3f9b7ff8bb73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE finegrainedauthorisationrole ADD VALUE 'CONTRIBUTOR_PENDING'")


def downgrade() -> None:
    """Downgrade schema."""
    # Note: PostgreSQL doesn't support removing enum values from an enum field.
    pass
