import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth import verify_access_token
from database import get_db
from models import User

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
        credentials:HTTPAuthorizationCredentials = Depends(bearer_scheme),
        db:Session = Depends(get_db)
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail = "Authentication required."
        )
    token = credentials.credentials
    token_data = verify_access_token(token)

    if token_data is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user = db.query(User).filter(User.id == token_data["user_id"]).first()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    # A token is only valid for the tenant it was issued to. Without this
    # check, a token minted before a user was reassigned would silently grant
    # access to the user's new tenant.
    if user.tenant_id != token_data["tenant_id"]:
        logger.warning(
            "token_tenant_mismatch user_id=%s token_tenant_id=%s user_tenant_id=%s",
            user.id,
            token_data["tenant_id"],
            user.tenant_id,
        )
        raise HTTPException(
            status_code=401,
            detail="Token is not valid for this tenant."
        )

    return user