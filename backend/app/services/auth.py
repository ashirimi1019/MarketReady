import base64
import hashlib
import hmac
import json
import os
import secrets
import string
import time
from datetime import datetime, timedelta
import re

from app.core.config import settings

PBKDF2_ITERATIONS = 120_000
SPECIAL_CHAR_PATTERN = re.compile(r"[^A-Za-z0-9]")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def hash_password(password: str) -> tuple[str, str]:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return _b64url_encode(salt), _b64url_encode(digest)


def password_policy_issues(password: str) -> list[str]:
    issues: list[str] = []
    if len(password) < 8:
        issues.append("at least 8 characters")
    if not any(ch.isupper() for ch in password):
        issues.append("at least one uppercase letter")
    if not SPECIAL_CHAR_PATTERN.search(password):
        issues.append("at least one special character")
    return issues


def verify_password(password: str, salt_b64: str, digest_b64: str) -> bool:
    salt = _b64url_decode(salt_b64)
    expected = _b64url_decode(digest_b64)
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(actual, expected)


def _create_token(user_id: str, *, token_type: str, ttl_seconds: int) -> str:
    payload = {
        "sub": user_id,
        "typ": token_type,
        "exp": int(time.time()) + ttl_seconds,
        "iat": int(time.time()),
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_raw)
    sig = hmac.new(
        settings.auth_secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"


def create_access_token(user_id: str) -> str:
    return _create_token(
        user_id,
        token_type="access",
        ttl_seconds=settings.auth_token_ttl_seconds,
    )


def create_auth_token(user_id: str) -> str:
    # Backward-compatible alias for existing imports.
    return create_access_token(user_id)


def verify_auth_token(token: str) -> str | None:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError:
        return None

    expected_sig = hmac.new(
        settings.auth_secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(_b64url_encode(expected_sig), sig_b64):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception:
        return None

    user_id = payload.get("sub")
    exp = payload.get("exp")
    token_type = payload.get("typ")
    if not user_id or not isinstance(exp, int):
        return None
    if exp < int(time.time()):
        return None
    # Accept legacy tokens that have no "typ", but reject explicit non-access tokens.
    if token_type and token_type != "access":
        return None
    return user_id


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def one_time_code(length: int = 6) -> str:
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def expiry_from_now(seconds: int) -> datetime:
    return datetime.utcnow() + timedelta(seconds=seconds)
