"""Core authentication utilities — password hashing, JWT token creation/validation, FastAPI dependencies."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings
from app.database.session import DbSession
from app.database.tables import UserRow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing — using bcrypt directly to avoid passlib 1.7.x + bcrypt 5.x
# incompatibility (passlib calls detect_wrap_bug which breaks on bcrypt 5.x).
# ---------------------------------------------------------------------------

import bcrypt as _bcrypt_lib


def hash_password(plain: str) -> str:
    return _bcrypt_lib.hashpw(plain.encode("utf-8"), _bcrypt_lib.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def _settings():
    return get_settings()


def create_access_token(user_id: str, tier: str) -> str:
    """Return a short-lived JWT access token."""
    settings = _settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "tier": tier, "exp": expire, "jti": str(uuid.uuid4())},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: str, tier: str) -> tuple[str, str]:
    """Return (raw_refresh_token, token_hash).  Store only the hash in the DB."""
    settings = _settings()
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    raw = jwt.encode(
        {"sub": user_id, "tier": tier, "type": "refresh", "exp": expire, "jti": str(uuid.uuid4())},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def _decode_token(token: str) -> dict:
    settings = _settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> UserRow:
    """Require an authenticated user. Raises 401 if token is missing or invalid."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = await db.get(UserRow, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> UserRow | None:
    """Return the authenticated user or None for unauthenticated requests."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


# Type aliases for use as FastAPI dependencies
CurrentUser = Annotated[UserRow, Depends(get_current_user)]
OptionalUser = Annotated[UserRow | None, Depends(get_optional_user)]
