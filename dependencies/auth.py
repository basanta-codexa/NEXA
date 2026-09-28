from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from sqlalchemy.orm import Session

from auth import verify_access_token
from database import get_db
from models import User

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
            detail="Invalid or expaired token"
        )

    user = db.query(User).filter(User.id == token_data["user_id"]).first()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user