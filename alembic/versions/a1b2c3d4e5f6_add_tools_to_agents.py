"""add tools to agents

Revision ID: a1b2c3d4e5f6
Revises: d25f700689f3
Create Date: 2026-10-11 11:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd25f700689f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('tools', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('agents', 'tools')
