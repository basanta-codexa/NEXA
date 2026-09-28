from fastapi import Depends, HTTPException
from dependencies.auth import get_current_user

from dependencies.permissions import Permissions

# permission of each role
ROLE_PERMISSIONS = {
    "admin": {
        Permissions.AGENT_READ,
        Permissions.AGENT_CREATE,
        Permissions.AGENT_DELETE,
        Permissions.AGENT_UPDATE,
        Permissions.USER_READ,
        Permissions.USER_CREATE,
    },
    "manager": {
        Permissions.AGENT_READ,
        Permissions.AGENT_CREATE,
        Permissions.AGENT_UPDATE,
    },

    "member": {
        Permissions.AGENT_READ,
    },
}


def require_roles(*allowed_roles):

    def role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permisssion to perform this action"
            )
        return current_user

    return role_checker


def require_permission(required_permission: str):
    def permission_checker(current_user=Depends(get_current_user)):

        user_permissions = ROLE_PERMISSIONS.get(
            current_user.role,
            set()
        )

        if required_permission not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to perform this action."
            )

        return current_user

    return permission_checker
