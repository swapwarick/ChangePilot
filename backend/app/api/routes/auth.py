"""Authentication routes.

POST /auth/register   — create a registered account (username + email + password)
POST /auth/login      — verify credentials, return access + refresh tokens
POST /auth/logout     — revoke session; purge ephemeral data for guest accounts
POST /auth/refresh    — exchange a valid refresh token for a new access token
POST /auth/guest      — create a temporary guest session (session-only tier)
GET  /auth/me         — return current user profile + storage stats
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import delete, select

from app.core.auth import (
    CurrentUser,
    OptionalUser,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    _decode_token,
)
from app.core.config import get_settings
from app.database.session import DbSession
from app.database.tables import SessionRow, UserRow
from app.services.storage import purge_ephemeral_data

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr | None = None
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 40:
            raise ValueError("Username must be between 3 and 40 characters")
        if not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, hyphens, underscores, and dots")
        return v

    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    username: str  # Can also be email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    tier: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: str | None
    tier: str
    storage_used_bytes: int
    storage_quota_bytes: int
    email_verified: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_session(user: UserRow, db: DbSession) -> tuple[str, str]:
    """Create a DB session row and return (access_token, raw_refresh_token)."""
    settings = get_settings()
    access_token = create_access_token(user.id, user.tier)
    raw_refresh, refresh_hash = create_refresh_token(user.id, user.tier)

    session = SessionRow(
        id=str(uuid.uuid4()),
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(session)
    await db.commit()
    return access_token, raw_refresh


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession) -> TokenResponse:
    """Create a registered account with persistent 30 MB storage."""
    settings = get_settings()

    # Check username uniqueness
    existing = await db.execute(select(UserRow).where(UserRow.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    # Check email uniqueness (if provided)
    if payload.email:
        existing_email = await db.execute(select(UserRow).where(UserRow.email == payload.email))
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = UserRow(
        id=str(uuid.uuid4()),
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        tier="registered",
        storage_quota_bytes=settings.storage_quota_bytes,
        storage_used_bytes=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token, raw_refresh = await _create_session(user, db)
    logger.info("New registered user: %s (%s)", user.username, user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user_id=user.id,
        username=user.username,
        tier=user.tier,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """Authenticate with username (or email) + password."""
    # Try username first, then email
    result = await db.execute(select(UserRow).where(UserRow.username == payload.username))
    user = result.scalar_one_or_none()
    if user is None and "@" in payload.username:
        result = await db.execute(select(UserRow).where(UserRow.email == payload.username))
        user = result.scalar_one_or_none()

    if user is None or user.hashed_password is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token, raw_refresh = await _create_session(user, db)
    logger.info("User logged in: %s", user.username)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user_id=user.id,
        username=user.username,
        tier=user.tier,
    )


@router.post("/guest", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_guest_session(db: DbSession) -> TokenResponse:
    """Create a temporary guest account. All data is purged on logout."""
    guest_id = str(uuid.uuid4())
    guest_username = f"guest_{guest_id[:8]}"

    user = UserRow(
        id=guest_id,
        username=guest_username,
        tier="guest",
        storage_quota_bytes=0,  # No persistent storage
        storage_used_bytes=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token, raw_refresh = await _create_session(user, db)
    logger.info("Guest session created: %s", guest_username)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user_id=user.id,
        username=user.username,
        tier=user.tier,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUser, db: DbSession) -> None:
    """Revoke the user's sessions. For guest users, all data is purged."""
    # Delete all sessions for this user
    await db.execute(delete(SessionRow).where(SessionRow.user_id == current_user.id))
    await db.commit()

    if current_user.tier == "guest":
        await purge_ephemeral_data(current_user.id, db)
        logger.info("Guest user %s logged out and data purged", current_user.username)
    else:
        logger.info("User %s logged out", current_user.username)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: DbSession) -> TokenResponse:
    """Exchange a valid refresh token for a new access token."""
    try:
        token_data = _decode_token(payload.refresh_token)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if token_data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    result = await db.execute(select(SessionRow).where(SessionRow.refresh_token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found or revoked")
    # Normalize: SQLite returns naive datetimes — treat as UTC
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(UTC):
        await db.delete(session)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = await db.get(UserRow, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Rotate refresh token
    await db.delete(session)
    access_token, raw_refresh = await _create_session(user, db)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user_id=user.id,
        username=user.username,
        tier=user.tier,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: CurrentUser) -> UserProfileResponse:
    """Return current user profile and storage usage."""
    return UserProfileResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        tier=current_user.tier,
        storage_used_bytes=current_user.storage_used_bytes,
        storage_quota_bytes=current_user.storage_quota_bytes,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at,
    )


@router.get("/config")
async def get_auth_config() -> dict:
    """Return public auth configuration for the frontend (e.g., is_cloud mode)."""
    settings = get_settings()
    return {"is_cloud": settings.is_cloud}
