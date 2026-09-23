from __future__ import annotations
from typing import Optional
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise UnauthorizedException("Bearer token is required")
    payload = decode_access_token(credentials.credentials)
    user = db.scalar(select(User).where(User.id == payload["sub"]))
    if not user:
        raise UnauthorizedException("User no longer exists")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "ADMIN":
        raise UnauthorizedException("Admin access is required")
    return user
