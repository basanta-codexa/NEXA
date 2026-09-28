from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Tenant
from schemas import CreateTenant    

from services.tenant_service import create_tenant_service

router = APIRouter(
    prefix="/tenants",
    tags=["Tenants"]
)

# Public onboarding endpoint:
# Create a new tenant before the first user/admin exists
@router.post("")
def create_tenant(tenant: CreateTenant, db: Session = Depends(get_db)): 

    new_tenant = create_tenant_service(db, tenant)  

    return {
        "message": "Tenant created successfully!",
        "tenant": {
            "id": new_tenant.id,
            "name": new_tenant.name,
            "description": new_tenant.description
        }
    }