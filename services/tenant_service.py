from models import Tenant

def create_tenant_service(db, tenant_data):
    new_tenant = Tenant(
        name=tenant_data.name,
        description=tenant_data.description
    )
    db.add(new_tenant)

    db.commit()

    db.refresh(new_tenant)

    return new_tenant