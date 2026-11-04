"""Tenant creation and onboarding.

Tenant creation is invite-only. The invite is consumed in the same database
transaction as the tenant, default RBAC roles, and optional first admin, so a
failed signup never burns an invite.
"""

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from dependencies.permissions import ROLE_ADMIN
from models import Tenant, User
from security import hash_password
from services.rbac_service import get_role, seed_tenant_roles
from services.signup_invites import consume_tenant_invite


def create_tenant_service(db, tenant_data):
    """
    Creates a tenant from a valid invite, seeds its default roles/permissions,
    and optionally creates the first admin user.

    Returns (tenant, admin_user_or_none). The caller must provide an unexpired,
    unused invite code.
    """
    try:
        consume_tenant_invite(db, tenant_data.invite_code)

        new_tenant = Tenant(
            name=tenant_data.name,
            description=tenant_data.description,
        )
        db.add(new_tenant)
        db.flush()

        roles = seed_tenant_roles(db, new_tenant.id)
        admin_user = None

        if tenant_data.admin_email:
            admin_role = roles.get(ROLE_ADMIN) or get_role(
                db,
                new_tenant.id,
                ROLE_ADMIN,
            )
            admin_user = User(
                email=tenant_data.admin_email,
                password_hash=hash_password(tenant_data.admin_password),
                role=ROLE_ADMIN,
                role_id=admin_role.id if admin_role else None,
                tenant_id=new_tenant.id,
            )
            db.add(admin_user)
            db.flush()

        db.commit()
        db.refresh(new_tenant)
        if admin_user is not None:
            db.refresh(admin_user)

        return new_tenant, admin_user
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This email is already registered.",
        ) from exc
    except Exception:
        db.rollback()
        raise
