from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


WorkflowConditionScalar = str | int | float | bool | None


class WorkflowConditionRuleDraft(BaseModel):
    path: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*){0,7}$",
    )
    operator: Literal[
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "not_in",
        "exists",
        "not_exists",
    ]
    value: WorkflowConditionScalar | list[WorkflowConditionScalar] = None

    @model_validator(mode="after")
    def validate_operator_value(self) -> "WorkflowConditionRuleDraft":
        has_value = "value" in self.model_fields_set
        if self.operator in {"exists", "not_exists"}:
            if has_value:
                raise ValueError("存在性条件不能配置比较值")
            return self
        if not has_value:
            raise ValueError("比较条件必须配置比较值")
        if self.operator in {"in", "not_in"}:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError("包含条件必须配置非空值列表")
        elif isinstance(self.value, list):
            raise ValueError("只有包含条件可以配置值列表")
        return self


class WorkflowConditionDraft(BaseModel):
    mode: Literal["all", "any"] = "all"
    rules: list[WorkflowConditionRuleDraft] = Field(min_length=1, max_length=20)


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
    condition: WorkflowConditionDraft | None = None


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
