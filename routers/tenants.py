from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from dependencies.roles import require_roles
from dependencies.permissions import ROLE_ADMIN
from schemas import CreateTenant, CreateSignupInvite
from services.tenant_service import create_tenant_service
from services.signup_invites import (
    create_tenant_invite,
    list_invites,
    revoke_invite,
)

router = APIRouter(
    prefix="/tenants",
    tags=["Tenants"],
)


# Invite-only onboarding endpoint: the caller must provide a valid,
# server-created, one-time invite code. Creates a tenant, its default
# roles/permissions, and (optionally) the first admin user.
@router.post("", status_code=201)
def create_tenant(tenant: CreateTenant, db: Session = Depends(get_db)):
    new_tenant, admin_user = create_tenant_service(db, tenant)

    response = {
        "message": "Tenant created successfully!",
        "tenant": {
            "id": new_tenant.id,
            "name": new_tenant.name,
            "description": new_tenant.description,
        },
        "roles_seeded": ["admin", "member"],
    }

    if admin_user is not None:
        response["admin_user"] = {
            "id": admin_user.id,
            "email": admin_user.email,
            "role": admin_user.role,
        }

    return response


# Admin-only: create a one-time tenant signup invite. The plaintext code is
# returned exactly once and never stored.
@router.post("/invites", status_code=201)
def create_signup_invite(
    body: CreateSignupInvite,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN)),
):
    invite, code = create_tenant_invite(
        db,
        description=body.description,
        expires_in_days=None if body.expires_in_days == 0 else body.expires_in_days,
    )

    return {
        "message": "Invite created. Store the code now; it will not be shown again.",
        "invite_code": code,
        "expires_in_days": None if body.expires_in_days == 0 else body.expires_in_days,
        "description": invite.description,
    }


# Admin-only: list every invite with its status. Codes are never returned —
# only hashes are stored, so plaintext invite codes cannot appear here.
@router.get("/invites")
def get_signup_invites(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN)),
):
    return {"invites": list_invites(db)}


# Admin-only: revoke an unused invite. Used invites cannot be revoked.
@router.delete("/invites/{invite_id}")
def delete_signup_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN)),
):
    revoke_invite(db, invite_id)
    return {"message": "Invite revoked."}
