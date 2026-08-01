from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkflowNodeDraft(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    node_type: Literal["start", "approval", "action", "end"]
    sign_mode: Literal["all", "any"] | None = None


class WorkflowEdgeDraft(BaseModel):
    source: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)
    condition: str | None = Field(default=None, max_length=500)


class WorkflowDefinitionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=50)
    description: str | None = None
    nodes: list[WorkflowNodeDraft] = Field(min_length=1)
    edges: list[WorkflowEdgeDraft] = Field(default_factory=list)
    change_reason: str = Field(min_length=1, max_length=500)


class WorkflowDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    category: str
    status: str
    active_version: int | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowDefinitionListResponse(BaseModel):
    items: list[WorkflowDefinitionResponse]
    total: int
    limit: int
    offset: int

