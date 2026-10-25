from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import CreateTenant
from services.tenant_service import create_tenant_service

router = APIRouter(
    prefix="/tenants",
    tags=["Tenants"],
)


# Public onboarding endpoint: creates a tenant, its default roles/permissions,
# and (optionally) the first admin user.
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
