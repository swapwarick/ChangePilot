"""Pydantic models for Risk Policy Management and Rule Customization."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class PolicyRuleConfig(BaseModel):
    signal: str
    name: str
    category: str
    description: str
    weight: float = Field(default=0.15, ge=0.0, le=1.0)
    enabled: bool = True
    threshold: str = "1 file"
    recommendation: str = ""
    path_markers: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)
    custom: bool = False


class RiskPolicy(BaseModel):
    id: str
    name: str = "Enterprise Risk Policy"
    organization_id: str = "default-org"
    version: str = "1.0.0"
    description: str = "Standard enterprise static analysis risk rules."
    is_active: bool = True
    rules: list[PolicyRuleConfig] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PolicyComparisonResult(BaseModel):
    policy_a_version: str
    policy_b_version: str
    weight_changes: list[dict] = Field(default_factory=list)
    status_changes: list[dict] = Field(default_factory=list)
    added_rules: list[dict] = Field(default_factory=list)
    removed_rules: list[dict] = Field(default_factory=list)
