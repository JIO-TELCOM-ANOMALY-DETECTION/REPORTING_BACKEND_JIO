from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class Artifact(BaseModel):
    name: str
    kind: str
    format: str
    relative_path: str
    size_bytes: int
    preview: list[dict[str, str]] | None = None


class ReportEnvelope(BaseModel):
    run_id: str
    attempt_id: str | None = None
    stage: str
    status: str
    execution_id: str | None = None
    invocation_id: str | None = None
    training_attempt_id: str | None = None
    generated_at: str
    summary: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: dict[str, str]
