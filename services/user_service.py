from models import User

from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from security import hash_password, verify_password

from auth import create_access_token

def create_user_service(db, user_data, tenant_id):
    # step 1: hash the user password
    hashed_password = hash_password(user_data.password)

    # create the user with the hashed password
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        tenant_id=tenant_id
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This Email id is already registered")
    return new_user

def get_users_service(db, tenant_id):
    users = db.query(User).filter(
        User.tenant_id == tenant_id
    ).all()

    return users

# verify user login
def login_user_service(db, user_data):
    user = db.query(User).filter(User.email == user_data.email).first()

    if user is None:
        return None

    password_is_correct = verify_password(user_data.password, user.password_hash)

    if not password_is_correct:
        return None

    access_token = create_access_token(user_id=user.id, tenant_id=user.tenant_id)

    return user, access_token


