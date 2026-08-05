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


class RepositoryRow(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(120), server_default="main")
    language: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )


class AnalysisRow(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    repository_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False)
    changed_files: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    impacted_modules: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    dependency_graph: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    risk_reasons: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    ai_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())


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
    max_tokens: Mapped[int] = mapped_column(Integer, default=1600)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=30)
    retry_max_attempts: Mapped[int] = mapped_column(Integer, default=2)
    retry_backoff: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )
