from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from dependencies.auth import get_current_user
from dependencies.permissions import Permissions
from dependencies.roles import require_permission
from dependencies.tenant import get_current_tenant_id
from models import User
from schemas import CreateUser, UserLogin
from services.user_service import (
    create_user_service,
    get_users_service,
    login_user_service,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post("", status_code=201)
def create_user(
    user: CreateUser,
    db=Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.USER_CREATE)),
):
    new_user = create_user_service(db, user, tenant_id)

    return {
        "message": "User created successfully!",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "role": new_user.role,
            "tenant_id": new_user.tenant_id,
        },
    }


@router.post("/login")
def login_user(user: UserLogin, db=Depends(get_db)):
    login_result = login_user_service(db, user)

    if login_result is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    logged_in_user, access_token = login_result

    return {
        "message": "Login successful!",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": logged_in_user.id,
            "email": logged_in_user.email,
            "tenant_id": logged_in_user.tenant_id,
            "role": logged_in_user.role,
        },
    }


@router.get("/me")
def get_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "tenant_id": current_user.tenant_id,
        "role": current_user.role,
    }


@router.get("")
def get_users(
    db=Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.USER_READ)),
):
    users = get_users_service(db, tenant_id)

    return {
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "tenant_id": user.tenant_id,
            }
            for user in users
        ]
    }
