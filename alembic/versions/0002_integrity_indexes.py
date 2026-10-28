"""enforce integrity and add tenant-scoped indexes

- Make ``users.password_hash`` non-nullable (matches the ORM).
- Cascade conversation rows when an agent is deleted.
- Set ``conversations.user_id`` to NULL when a user is deleted.
- Add the indexes and uniqueness constraints used by tenant-scoped queries.

Revision ID: 0002_integrity
Revises: c3d4e5f6a7b8
Create Date: 2026-10-28
"""
import secrets
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pwdlib import PasswordHash


# revision identifiers, used by Alembic.
revision: str = "0002_integrity"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Existing installations may contain passwordless rows. Give them an
    # unguessable hash so the NOT NULL constraint can be enforced safely.
    disabled_hash = PasswordHash.recommended().hash(secrets.token_urlsafe(32))
    bind.execute(
        sa.text("UPDATE users SET password_hash = :hash WHERE password_hash IS NULL"),
        {"hash": disabled_hash},
    )
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    # Deleting an agent removes its conversations (and messages via the
    # conversations -> messages cascade).
    op.drop_constraint(
        "conversations_agent_id_fkey", "conversations", type_="foreignkey"
    )
    op.create_foreign_key(
        "conversations_agent_id_fkey",
        "conversations",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "conversations_user_id_fkey", "conversations", type_="foreignkey"
    )
    op.create_foreign_key(
        "conversations_user_id_fkey",
        "conversations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Tenant-scoped lookups.
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])

    # A session id is unique per tenant + agent, and a role name is unique
    # per tenant. Both prevent duplicate rows under concurrent requests.
    op.create_unique_constraint(
        "uq_conversations_tenant_agent_session",
        "conversations",
        ["tenant_id", "agent_id", "session_id"],
    )
    op.create_unique_constraint(
        "uq_roles_tenant_name",
        "roles",
        ["tenant_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_roles_tenant_name", "roles", type_="unique"
    )
    op.drop_constraint(
        "uq_conversations_tenant_agent_session",
        "conversations",
        type_="unique",
    )

    op.drop_index("ix_messages_tenant_id", table_name="messages")
    op.drop_index("ix_roles_tenant_id", table_name="roles")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_index("ix_agents_tenant_id", table_name="agents")

    op.drop_constraint(
        "conversations_user_id_fkey", "conversations", type_="foreignkey"
    )
    op.create_foreign_key(
        "conversations_user_id_fkey",
        "conversations",
        "users",
        ["user_id"],
        ["id"],
    )

    op.drop_constraint(
        "conversations_agent_id_fkey", "conversations", type_="foreignkey"
    )
    op.create_foreign_key(
        "conversations_agent_id_fkey",
        "conversations",
        "agents",
        ["agent_id"],
        ["id"],
    )

    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
    )
