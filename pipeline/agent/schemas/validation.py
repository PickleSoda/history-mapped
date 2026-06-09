from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class ValidationResult(BaseModel):
    candidate_id: str
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence_override: float | None = None


class PipelineError(BaseModel):
    node: str
    error_type: str
    message: str
    context: dict[str, Any] | None = None


class AuditEvent(BaseModel):
    timestamp: str
    node: str
    action: str
    input_summary: str | None = None
    output_summary: str | None = None
    proposal_id: str | None = None
    validation_status: str | None = None
    approval_status: str | None = None
