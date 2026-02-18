from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.ratelimit import auth_login_rate_limiter
from app.models.entities import AuthAuditLog, AuthSession, StudentAccount
from app.schemas.api import (
    AuthActionOut,
    AuthLoginIn,
    AuthLogoutIn,
    AuthOut,
    AuthPasswordForgotIn,
    AuthPasswordResetIn,
    AuthRefreshIn,
    AuthRegisterIn,
    AuthResendVerificationIn,
    AuthVerifyEmailIn,
)
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    expiry_from_now,
    hash_password,
    hash_token,
    one_time_code,
    verify_password,
)
from app.services.mailer import (
    mail_is_configured,
    send_password_reset_email,
    send_verification_code_email,
)

router = APIRouter(prefix="/auth")


def _normalize_username(value: str) -> str:
    return value.strip().lower()


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    email = value.strip().lower()
    return email or None


def _request_context(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent


def _audit(
    db: Session,
    *,
    action: str,
    status: str,
    request: Request,
    user_id: str | None = None,
    detail: dict | None = None,
) -> None:
    ip_address, user_agent = _request_context(request)
    db.add(
        AuthAuditLog(
            user_id=user_id,
            action=action,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            detail=detail,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()


def _send_code_email(
    db: Session,
    *,
    request: Request,
    user_id: str,
    email: str | None,
    kind: str,
    code: str,
) -> tuple[bool, str]:
    if not email:
        return False, "missing_email"
    if not mail_is_configured():
        _audit(
            db,
            action=f"{kind}_email",
            status="skipped",
            request=request,
            user_id=user_id,
            detail={"reason": "mail_not_configured"},
        )
        return False, "mail_not_configured"

    ttl_minutes = (
        max(1, settings.auth_email_code_ttl_seconds // 60)
        if kind == "verification"
        else max(1, settings.auth_password_reset_ttl_seconds // 60)
    )
    try:
        send_result = None
        if kind == "verification":
            send_result = send_verification_code_email(
                to_email=email,
                username=user_id,
                code=code,
                ttl_minutes=ttl_minutes,
            )
        else:
            send_result = send_password_reset_email(
                to_email=email,
                username=user_id,
                code=code,
                ttl_minutes=ttl_minutes,
            )
        provider = send_result.provider if send_result else "unknown"
        _audit(
            db,
            action=f"{kind}_email",
            status="success",
            request=request,
            user_id=user_id,
            detail={
                "to_email": email,
                "provider": provider,
                "provider_message_id": (send_result.provider_message_id if send_result else None),
            },
        )
        return True, provider
    except Exception as exc:
        _audit(
            db,
            action=f"{kind}_email",
            status="failed",
            request=request,
            user_id=user_id,
            detail={"to_email": email, "reason": str(exc)},
        )
        return False, "send_failed"


def _issue_session_tokens(db: Session, *, user_id: str, request: Request) -> dict:
    refresh_raw = create_refresh_token()
    refresh_hash = hash_token(refresh_raw)
    now = datetime.utcnow()
    refresh_expires_at = expiry_from_now(settings.auth_refresh_token_ttl_seconds)
    ip_address, user_agent = _request_context(request)

    db.add(
        AuthSession(
            user_id=user_id,
            refresh_token_hash=refresh_hash,
            created_at=now,
            expires_at=refresh_expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    db.commit()

    return {
        "auth_token": create_access_token(user_id),
        "refresh_token": refresh_raw,
        "access_expires_at": expiry_from_now(settings.auth_token_ttl_seconds),
        "refresh_expires_at": refresh_expires_at,
    }


@router.post("/register", response_model=AuthOut)
def register(payload: AuthRegisterIn, request: Request, db: Session = Depends(get_db)):
    username = _normalize_username(payload.username)
    email = _normalize_email(payload.email)
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if settings.auth_require_email_verification and not email:
        raise HTTPException(status_code=400, detail="Email is required for account verification")

    existing = db.query(StudentAccount).filter(StudentAccount.username == username).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    if email:
        existing_email = db.query(StudentAccount).filter(StudentAccount.email == email).one_or_none()
        if existing_email:
            raise HTTPException(status_code=409, detail="Email already exists")

    salt, digest = hash_password(payload.password)
    account = StudentAccount(
        username=username,
        email=email,
        email_verified=not settings.auth_require_email_verification,
        password_salt=salt,
        password_hash=digest,
        created_at=datetime.utcnow(),
    )
    dev_code = None
    if settings.auth_require_email_verification:
        code = one_time_code()
        account.email_verification_code = code
        account.email_verification_expires_at = expiry_from_now(settings.auth_email_code_ttl_seconds)
        if settings.auth_dev_return_codes:
            dev_code = code

    db.add(account)
    db.commit()

    _audit(
        db,
        action="register",
        status="success",
        request=request,
        user_id=username,
        detail={"email_provided": bool(email)},
    )

    if settings.auth_require_email_verification:
        delivered = False
        delivery_state = "missing_email"
        if account.email_verification_code:
            delivered, delivery_state = _send_code_email(
                db,
                request=request,
                user_id=username,
                email=account.email,
                kind="verification",
                code=account.email_verification_code,
            )

        if delivered:
            message = "Account created. Check your email for the verification code before login."
        elif delivery_state == "mail_not_configured":
            message = (
                "Account created, but email delivery is not configured yet. "
                "Configure SMTP and resend verification code."
            )
        else:
            message = (
                "Account created, but we could not send a verification email. "
                "Use resend verification code."
            )
        return {
            "user_id": username,
            "email_verification_required": True,
            "message": message,
            "dev_code": dev_code,
        }

    tokens = _issue_session_tokens(db, user_id=username, request=request)
    return {
        "user_id": username,
        **tokens,
        "email_verification_required": False,
    }


@router.post("/login", response_model=AuthOut)
def login(payload: AuthLoginIn, request: Request, db: Session = Depends(get_db)):
    username = _normalize_username(payload.username)
    ip_address, _ = _request_context(request)
    throttle_key = f"{username}:{ip_address}"
    auth_login_rate_limiter.check(throttle_key)

    account = db.query(StudentAccount).filter(StudentAccount.username == username).one_or_none()
    if not account or not account.is_active:
        _audit(
            db,
            action="login",
            status="failed",
            request=request,
            user_id=username,
            detail={"reason": "unknown_or_inactive_user"},
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not verify_password(payload.password, account.password_salt, account.password_hash):
        _audit(
            db,
            action="login",
            status="failed",
            request=request,
            user_id=username,
            detail={"reason": "bad_password"},
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if settings.auth_require_email_verification and not account.email_verified:
        if (
            not account.email_verification_code
            or not account.email_verification_expires_at
            or account.email_verification_expires_at < datetime.utcnow()
        ):
            account.email_verification_code = one_time_code()
            account.email_verification_expires_at = expiry_from_now(settings.auth_email_code_ttl_seconds)
            db.commit()
        _audit(
            db,
            action="login",
            status="blocked",
            request=request,
            user_id=username,
            detail={"reason": "email_not_verified"},
        )
        raise HTTPException(status_code=403, detail="Email verification required")

    auth_login_rate_limiter.clear(throttle_key)
    account.last_login_at = datetime.utcnow()
    db.commit()

    tokens = _issue_session_tokens(db, user_id=username, request=request)
    _audit(
        db,
        action="login",
        status="success",
        request=request,
        user_id=username,
    )
    return {"user_id": username, **tokens}


@router.post("/verify-email", response_model=AuthActionOut)
def verify_email(payload: AuthVerifyEmailIn, request: Request, db: Session = Depends(get_db)):
    username = _normalize_username(payload.username)
    account = db.query(StudentAccount).filter(StudentAccount.username == username).one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.email_verified:
        return {"ok": True, "message": "Email already verified."}
    if not account.email_verification_code or not account.email_verification_expires_at:
        raise HTTPException(status_code=400, detail="No active verification code")
    if account.email_verification_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification code expired")
    if payload.code.strip() != account.email_verification_code:
        _audit(
            db,
            action="verify_email",
            status="failed",
            request=request,
            user_id=username,
            detail={"reason": "bad_code"},
        )
        raise HTTPException(status_code=400, detail="Invalid verification code")

    account.email_verified = True
    account.email_verification_code = None
    account.email_verification_expires_at = None
    db.commit()
    _audit(db, action="verify_email", status="success", request=request, user_id=username)
    return {"ok": True, "message": "Email verified. You can now login."}


@router.post("/resend-verification", response_model=AuthActionOut)
def resend_verification(
    payload: AuthResendVerificationIn,
    request: Request,
    db: Session = Depends(get_db),
):
    username = _normalize_username(payload.username)
    account = db.query(StudentAccount).filter(StudentAccount.username == username).one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.email_verified:
        return {"ok": True, "message": "Email already verified."}

    account.email_verification_code = one_time_code()
    account.email_verification_expires_at = expiry_from_now(settings.auth_email_code_ttl_seconds)
    db.commit()
    dev_code = account.email_verification_code if settings.auth_dev_return_codes else None
    delivered, delivery_state = _send_code_email(
        db,
        request=request,
        user_id=username,
        email=account.email,
        kind="verification",
        code=account.email_verification_code,
    )
    _audit(
        db,
        action="resend_verification",
        status="success",
        request=request,
        user_id=username,
        detail={"email_delivery": delivery_state},
    )
    message = "Verification code re-issued."
    if delivered:
        message = "Verification code sent to your email."
    elif delivery_state == "mail_not_configured":
        message = (
            "Verification code generated, but email delivery is not configured. "
            "Configure SMTP to receive codes by email."
        )
    elif delivery_state == "send_failed":
        message = "Verification code generated, but email delivery failed. Try again."
    return {
        "ok": True,
        "message": message,
        "dev_code": dev_code,
    }


@router.post("/password/forgot", response_model=AuthActionOut)
def forgot_password(payload: AuthPasswordForgotIn, request: Request, db: Session = Depends(get_db)):
    username = _normalize_username(payload.username) if payload.username else None
    email = _normalize_email(payload.email)
    account = None
    if username:
        account = db.query(StudentAccount).filter(StudentAccount.username == username).one_or_none()
    elif email:
        account = db.query(StudentAccount).filter(StudentAccount.email == email).one_or_none()

    dev_code = None
    message = "If the account exists, a reset code has been issued."
    if account:
        account.password_reset_code = one_time_code()
        account.password_reset_expires_at = expiry_from_now(settings.auth_password_reset_ttl_seconds)
        db.commit()
        if settings.auth_dev_return_codes:
            dev_code = account.password_reset_code
        delivered, delivery_state = _send_code_email(
            db,
            request=request,
            user_id=account.username,
            email=account.email,
            kind="password_reset",
            code=account.password_reset_code,
        )
        if delivered:
            message = "If the account exists, a reset code has been sent to email."
        elif delivery_state == "mail_not_configured":
            message = (
                "If the account exists, a reset code was created but email delivery is not configured."
            )
        elif delivery_state == "send_failed":
            message = (
                "If the account exists, a reset code was created but email send failed. Try again."
            )
        _audit(
            db,
            action="forgot_password",
            status="success",
            request=request,
            user_id=account.username,
            detail={"email_delivery": delivery_state},
        )
    return {
        "ok": True,
        "message": message,
        "dev_code": dev_code,
    }


@router.post("/password/reset", response_model=AuthActionOut)
def reset_password(payload: AuthPasswordResetIn, request: Request, db: Session = Depends(get_db)):
    username = _normalize_username(payload.username)
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    account = db.query(StudentAccount).filter(StudentAccount.username == username).one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not account.password_reset_code or not account.password_reset_expires_at:
        raise HTTPException(status_code=400, detail="No active reset code")
    if account.password_reset_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset code expired")
    if payload.code.strip() != account.password_reset_code:
        _audit(
            db,
            action="reset_password",
            status="failed",
            request=request,
            user_id=username,
            detail={"reason": "bad_code"},
        )
        raise HTTPException(status_code=400, detail="Invalid reset code")

    salt, digest = hash_password(payload.new_password)
    account.password_salt = salt
    account.password_hash = digest
    account.password_reset_code = None
    account.password_reset_expires_at = None
    db.query(AuthSession).filter(AuthSession.user_id == username).filter(
        AuthSession.revoked_at.is_(None)
    ).update({"revoked_at": datetime.utcnow()})
    db.commit()
    _audit(db, action="reset_password", status="success", request=request, user_id=username)
    return {"ok": True, "message": "Password reset complete. Please login again."}


@router.post("/refresh", response_model=AuthOut)
def refresh_token(payload: AuthRefreshIn, request: Request, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    session = (
        db.query(AuthSession)
        .filter(AuthSession.refresh_token_hash == token_hash)
        .one_or_none()
    )
    if not session or session.revoked_at is not None or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = session.user_id
    session.revoked_at = datetime.utcnow()
    db.commit()
    tokens = _issue_session_tokens(db, user_id=user_id, request=request)
    _audit(db, action="refresh_token", status="success", request=request, user_id=user_id)
    return {"user_id": user_id, **tokens}


@router.post("/logout", response_model=AuthActionOut)
def logout(payload: AuthLogoutIn, request: Request, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    session = (
        db.query(AuthSession)
        .filter(AuthSession.refresh_token_hash == token_hash)
        .one_or_none()
    )
    if not session:
        return {"ok": True, "message": "Session already ended."}
    session.revoked_at = datetime.utcnow()
    db.commit()
    _audit(db, action="logout", status="success", request=request, user_id=session.user_id)
    return {"ok": True, "message": "Logged out."}
