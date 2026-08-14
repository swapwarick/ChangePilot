"""SQLAlchemy 2.0 ORM table definitions.

These models map directly to PostgreSQL tables. Pydantic models in
``app.models`` remain the API request/response schemas; conversion
happens in the repository layer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# Auth tables
# ---------------------------------------------------------------------------


class UserRow(Base):
    """Application user — both registered and guest accounts."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "registered" users have persistent 30 MB storage; "guest" sessions are ephemeral
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="guest")
    storage_used_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_quota_bytes: Mapped[int] = mapped_column(Integer, default=0)  # 0 = no persistent storage
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )


class SessionRow(Base):
    """JWT refresh-token sessions tracked server-side for revocation support."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())


# ---------------------------------------------------------------------------
# Repository & analysis tables
# ---------------------------------------------------------------------------


class RepositoryRow(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(120), server_default="main")
    language: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Ownership
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_ephemeral: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )


class AnalysisRow(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False)
    base_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    head_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    changed_files: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    impacted_modules: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    dependency_graph: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    risk_reasons: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    ai_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit & Versioning Metadata
    parser_version: Mapped[str] = mapped_column(String(30), default="1.0.0")
    graph_version: Mapped[str] = mapped_column(String(30), default="1.0.0")
    risk_engine_version: Mapped[str] = mapped_column(String(30), default="1.0.0")
    ai_prompt_version: Mapped[str] = mapped_column(String(30), default="1.0.0")
    ai_provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Ownership
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_ephemeral: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())


class AnalysisJobRow(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")  # PENDING, CLONING, PARSING, BUILDING_GRAPH, SCORING, COMPLETED, FAILED
    step: Mapped[str] = mapped_column(String(60), nullable=False, default="Queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Ownership
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_ephemeral: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )


class RepoKnowledgeGraphRow(Base):
    __tablename__ = "repo_knowledge_graphs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    graph_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    nodes: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    edges: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    health_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Ownership
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    is_ephemeral: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())


class FileASTCacheRow(Base):
    __tablename__ = "file_ast_cache"

    file_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str] = mapped_column(String(40), nullable=False)
    parsed_ast: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )


class AIProviderConfigRow(Base):
    __tablename__ = "ai_provider_configs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    task_categories: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: ["report"])
    fallback_provider_ids: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    custom_headers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=120)
    retry_max_attempts: Mapped[int] = mapped_column(Integer, default=2)
    retry_backoff: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )


class RiskPolicyRow(Base):
    __tablename__ = "risk_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default-org")
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0.0")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rules: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )
