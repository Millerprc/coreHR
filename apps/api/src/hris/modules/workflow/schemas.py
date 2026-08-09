from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkflowAssigneeDraft(BaseModel):
    assignee_type: Literal["user", "role", "expression"]
    assignee_ref: str = Field(min_length=1, max_length=100)


class WorkflowNodeDraft(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    node_type: Literal["start", "approval", "action", "end"]
    sign_mode: Literal["all", "any"] | None = None
    assignees: list[WorkflowAssigneeDraft] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_approval(self) -> "WorkflowNodeDraft":
        if self.node_type == "approval" and self.sign_mode is None:
            raise ValueError("审批节点必须指定会签或或签")
        if self.node_type != "approval" and (self.sign_mode is not None or self.assignees):
            raise ValueError("只有审批节点可以配置签署方式和办理人")
        return self


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


class WorkflowVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_definition_id: UUID
    version: int
    status: str
    definition: dict[str, Any]
    change_reason: str
    created_at: datetime


class WorkflowDefinitionDetailResponse(BaseModel):
    definition: WorkflowDefinitionResponse
    versions: list[WorkflowVersionResponse]
