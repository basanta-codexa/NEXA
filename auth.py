from datetime import datetime, timedelta, timezone
import os

import jwt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30))


def create_access_token(user_id: int, tenant_id: int) -> str:
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY must be set in .env")

    expire = datetime.now(timezone.utc) + \
        timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "exp": expire
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")

        if user_id is None or tenant_id is None:
            return None

        return {"user_id": int(user_id), "tenant_id": int(tenant_id)}

    except jwt.InvalidTokenError:
        return None
