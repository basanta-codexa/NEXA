from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from dependencies.tenant import get_current_tenant_id
from schemas import CreateUser, UserLogin
from services.user_service import create_user_service, get_users_service, login_user_service

from dependencies.auth import get_current_user
from models import User

from dependencies.roles import require_permission
from dependencies.permissions import Permissions

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.post("")
def create_user(user: CreateUser, db=Depends(get_db), tenant_id: int = Depends(get_current_tenant_id), current_user=Depends(require_permission(Permissions.USER_CREATE))
                ):

    new_user = create_user_service(db, user, tenant_id)

    return {
        "message": "User created successfully!",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "tenant_id": new_user.tenant_id
        }
    }


@router.post("/login")
def login_user(user: UserLogin, db=Depends(get_db)):

    login_result = login_user_service(db, user)

    if login_result is None:
        raise HTTPException(
            status_code=401, detail="Invalid email or password")

    logged_in_user, access_token = login_result

    return {
        "message": "login successfully!",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": logged_in_user.id,
            "email": logged_in_user.email,
            "tenant_id": logged_in_user.tenant_id,
            "role": logged_in_user.role
        }
    }


@router.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "tenant_id": current_user.tenant_id,
        "role": current_user.role
    }


@router.get("")
def get_users(db=Depends(get_db), tenant_id: int = Depends(get_current_tenant_id), current_user=Depends(require_permission(Permissions.USER_READ))):

    users = get_users_service(db, tenant_id)

    return {
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "tenant_id": user.tenant_id
            }
            for user in users
        ]
    }
