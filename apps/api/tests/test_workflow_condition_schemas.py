import pytest
from pydantic import ValidationError
from uuid import uuid4

from hris.modules.workflow.extended_schemas import WorkflowInstanceCreate
from hris.modules.workflow.schemas import WorkflowDefinitionCreate


def _definition(condition: dict) -> WorkflowDefinitionCreate:
    return WorkflowDefinitionCreate(
        code="CONDITIONAL_APPROVAL",
        name="条件审批",
        category="synthetic",
        nodes=[
            {"code": "START", "name": "开始", "node_type": "start"},
            {"code": "APPROVE", "name": "审批", "node_type": "approval", "sign_mode": "any"},
            {"code": "END", "name": "结束", "node_type": "end"},
        ],
        edges=[
            {"source": "START", "target": "APPROVE", "condition": condition},
            {"source": "APPROVE", "target": "END"},
        ],
        change_reason="测试条件定义",
    )


def test_workflow_condition_accepts_bounded_declarative_rules() -> None:
    payload = _definition(
        {
            "mode": "all",
            "rules": [
                {"path": "amount", "operator": "gte", "value": 10000},
                {"path": "country_code", "operator": "in", "value": ["CN", "SG"]},
            ],
        }
    )

    condition = payload.edges[0].condition
    assert condition is not None
    assert condition.mode == "all"
    assert len(condition.rules) == 2


@pytest.mark.parametrize(
    "condition",
    [
        {"mode": "all", "rules": [{"path": "__class__", "operator": "eq", "value": "x"}]},
        {"mode": "all", "rules": [{"path": "amount", "operator": "in", "value": 10000}]},
        {"mode": "all", "rules": [{"path": "amount", "operator": "exists", "value": True}]},
        {"mode": "all", "rules": []},
    ],
)
def test_workflow_condition_rejects_unsafe_or_ambiguous_shapes(condition: dict) -> None:
    with pytest.raises(ValidationError):
        _definition(condition)


def test_workflow_instance_rejects_spoofed_route_history() -> None:
    with pytest.raises(ValidationError):
        WorkflowInstanceCreate(
            workflow_definition_id=uuid4(),
            business_object_type="synthetic",
            business_object_id=uuid4(),
            context={"_workflow_route_history": []},
        )
