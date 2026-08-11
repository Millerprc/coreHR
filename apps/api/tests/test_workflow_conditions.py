import pytest

from hris.modules.workflow.conditions import (
    WorkflowConditionError,
    evaluate_workflow_condition,
)


def test_condition_supports_nested_paths_and_any_mode() -> None:
    assert evaluate_workflow_condition(
        {
            "mode": "any",
            "rules": [
                {"path": "organization.level", "operator": "eq", "value": "BG"},
                {"path": "amount", "operator": "gte", "value": 10000},
            ],
        },
        {"organization": {"level": "BU"}, "amount": 12000},
    )


def test_missing_or_wrong_typed_values_fail_closed() -> None:
    assert not evaluate_workflow_condition(
        {"mode": "all", "rules": [{"path": "amount", "operator": "gte", "value": 10}]},
        {},
    )
    assert not evaluate_workflow_condition(
        {"mode": "all", "rules": [{"path": "amount", "operator": "gte", "value": 10}]},
        {"amount": "10"},
    )
    assert not evaluate_workflow_condition(
        {"mode": "all", "rules": [{"path": "amount", "operator": "ne", "value": 10}]},
        {"amount": "10"},
    )
    assert evaluate_workflow_condition(
        {"mode": "all", "rules": [{"path": "amount", "operator": "eq", "value": 10}]},
        {"amount": 10.0},
    )


def test_malformed_persisted_condition_is_rejected() -> None:
    with pytest.raises(WorkflowConditionError):
        evaluate_workflow_condition(
            {"mode": "all", "rules": [{"path": "amount", "operator": "python_eval", "value": "x"}]},
            {"amount": 10},
        )
