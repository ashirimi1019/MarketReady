from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.auth import verify_auth_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_id(x_auth_token: str | None = Header(default=None)) -> str:
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Missing X-Auth-Token header")
    user_id = verify_auth_token(x_auth_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired auth token")
    return user_id


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=500, detail="Admin token not configured")
    if not x_admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
