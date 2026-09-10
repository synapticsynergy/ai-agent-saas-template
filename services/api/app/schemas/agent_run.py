"""Agent run observability schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RunStatus = Literal["running", "succeeded", "failed", "cancelled"]


class AgentToolCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tool_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    error: str | None = None


class AgentRunCreate(BaseModel):
    id: str = Field(max_length=64)
    agent_name: str = Field(max_length=100)
    model: str = Field(default="", max_length=200)
    started_at: datetime
    trace_id: str | None = Field(default=None, max_length=128)


class AgentRunComplete(BaseModel):
    status: RunStatus
    completed_at: datetime
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    error: str | None = None


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    user_id: str
    agent_name: str
    model: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    trace_id: str | None = None
    error: str | None = None
    tool_calls: list[AgentToolCallRead] = Field(default_factory=list)
