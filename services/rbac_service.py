"""Role/permission seeding.

Permissions are global; roles are per-tenant. Seeding is idempotent so it is
safe to run on every deploy or tenant signup.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from dependencies.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    ROLE_ADMIN,
    ROLE_MEMBER,
    Permissions,
)
from models import Permission, Role, Tenant, User

logger = logging.getLogger(__name__)

PERMISSION_DESCRIPTIONS = {
    Permissions.AGENT_READ: "View agents",
    Permissions.AGENT_CREATE: "Create agents",
    Permissions.AGENT_UPDATE: "Update agents and lifecycle status",
    Permissions.AGENT_DELETE: "Delete agents",
    Permissions.USER_READ: "View users in the tenant",
    Permissions.USER_CREATE: "Invite/create users",
    Permissions.USER_UPDATE: "Update users",
    Permissions.DOCUMENT_READ: "View and search knowledge documents",
    Permissions.DOCUMENT_CREATE: "Upload knowledge documents",
    Permissions.DOCUMENT_DELETE: "Delete knowledge documents",
}


def seed_permissions(db: Session) -> dict[str, Permission]:
    """Create any missing permission rows and return them by name."""
    existing = {p.name: p for p in db.query(Permission).all()}

    for name in sorted(Permissions.ALL):
        if name not in existing:
            permission = Permission(
                name=name,
                description=PERMISSION_DESCRIPTIONS.get(name),
            )
            db.add(permission)
            existing[name] = permission

    db.commit()
    return existing


def seed_tenant_roles(db: Session, tenant_id: int) -> dict[str, Role]:
    """Ensure the default roles exist for a tenant and have the right grants."""
    permissions = seed_permissions(db)
    roles: dict[str, Role] = {}

    for role_name, permission_names in DEFAULT_ROLE_PERMISSIONS.items():
        role = db.query(Role).filter(
            Role.tenant_id == tenant_id,
            Role.name == role_name,
        ).first()

        if role is None:
            role = Role(name=role_name, tenant_id=tenant_id)
            db.add(role)
            db.flush()

        role.permissions = [
            permissions[name]
            for name in sorted(permission_names)
            if name in permissions
        ]
        roles[role_name] = role

    db.flush()

    # Users created before RBAC was introduced only have the legacy ``role``
    # string. Backfill their role_id so permission checks work.
    for role_name, role in roles.items():
        db.query(User).filter(
            User.tenant_id == tenant_id,
            User.role == role_name,
            User.role_id.is_(None),
        ).update({User.role_id: role.id}, synchronize_session=False)

    db.commit()
    return roles


def get_role(db: Session, tenant_id: int, name: str) -> Role | None:
    return db.query(Role).filter(
        Role.tenant_id == tenant_id,
        Role.name == name,
    ).first()


def seed_all_tenants(db: Session) -> int:
    """Backfill roles/permissions for every existing tenant."""
    tenant_ids = [row[0] for row in db.query(Tenant.id).all()]
    for tenant_id in tenant_ids:
        seed_tenant_roles(db, tenant_id)
    logger.info("RBAC seeded for %d tenant(s)", len(tenant_ids))
    return len(tenant_ids)
