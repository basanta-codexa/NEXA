from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from auth import create_access_token
from dependencies.permissions import ROLE_MEMBER
from models import User
from security import hash_password, verify_password
from services.rbac_service import get_role


def create_user_service(db, user_data, tenant_id):
    role_name = getattr(user_data, "role", None) or ROLE_MEMBER
    role = get_role(db, tenant_id, role_name)

    if role is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown role '{role_name}' for this tenant.",
        )

    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role=role.name,
        role_id=role.id,
        tenant_id=tenant_id,
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This email is already registered",
        ) from exc

    return new_user


def get_users_service(db, tenant_id):
    return db.query(User).filter(User.tenant_id == tenant_id).all()


def login_user_service(db, user_data):
    user = db.query(User).filter(User.email == user_data.email).first()

    if user is None:
        return None

    if not verify_password(user_data.password, user.password_hash):
        return None

    access_token = create_access_token(user_id=user.id, tenant_id=user.tenant_id)

    return user, access_token
