from fastapi import Depends, HTTPException
from dependencies.auth import get_current_user

from database import get_db
from models import Role


def require_roles(*allowed_roles):

    def role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action"
            )
        return current_user

    return role_checker


def require_permission(required_permission: str):
    def permission_checker(current_user=Depends(get_current_user), db=Depends(get_db)):

        # check wheather the user has a role assigned or not
        if current_user.role_id is None:
            raise HTTPException(
                status_code=403,
                detail="No role assigned to this user."
            )
        # fetch permission assigned to the user's role

        role = db.query(Role).filter(Role.id == current_user.role_id,
                                     Role.tenant_id == current_user.tenant_id,).first()

        if role is None:
            raise HTTPException(
                status_code=403,
                detail="Role not found for this user."
            )
        # 3. Get permission names from the user role.
        permission_names = {
            permission.name
            for permission in role.permissions
        }

        # 4. Check whether the required permission exists.
        if required_permission not in permission_names:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action."
            )

        # 5. Allow the request to continue.

        return current_user

    return permission_checker
