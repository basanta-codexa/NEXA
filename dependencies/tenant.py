from fastapi import HTTPException, Header, Depends

from dependencies.auth import get_current_user

def get_current_tenant_id(
        current_user = Depends(get_current_user)
):
    
    
    return current_user.tenant_id