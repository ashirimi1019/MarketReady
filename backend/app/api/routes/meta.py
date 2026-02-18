from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.services.ai import ai_is_configured, get_active_ai_model, get_active_ai_provider
from app.services.storage import s3_is_enabled, storage_self_test

router = APIRouter(prefix="/meta")


@router.get("/ai")
def ai_meta():
    return {
        "ai_enabled": ai_is_configured(),
        "model": get_active_ai_model(),
        "provider": get_active_ai_provider(),
    }


@router.get("/storage")
def storage_meta():
    return {
        "s3_enabled": s3_is_enabled(),
        "s3_bucket": settings.s3_bucket,
        "s3_region": settings.s3_region,
        "local_enabled": True,
    }


@router.get("/storage/test")
def storage_test():
    return storage_self_test()


@router.get("/health")
def health_meta():
    db_ok = False
    db_error = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)
    return {
        "ok": db_ok,
        "database": {"ok": db_ok, "error": db_error},
        "ai": {
            "enabled": ai_is_configured(),
            "provider": get_active_ai_provider(),
            "model": get_active_ai_model(),
        },
        "storage": {
            "s3_enabled": s3_is_enabled(),
            "s3_bucket": settings.s3_bucket,
            "local_enabled": True,
        },
    }
