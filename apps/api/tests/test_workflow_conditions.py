# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""流程条件求值的单元测试。

Requirement: D-108 — 条件求值是**私有实现**（决定流程走哪条线），
测试随实现一起走：公开仓模式下按「私有包是否可导入」跳过，
装上私有包时必须全绿。断言本身没有削弱。
"""

from __future__ import annotations

import pytest

from enterprise_support import requires_enterprise


pytestmark = requires_enterprise


def _conditions():
    """取私有包里的条件求值器（模块级导入会让公开仓模式在收集期报错）。"""

    import corehr_enterprise.workflow.conditions as module

    return module


def test_condition_supports_nested_paths_and_any_mode() -> None:
    conditions = _conditions()
    assert conditions.evaluate_workflow_condition(
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
    conditions = _conditions()
    assert not conditions.evaluate_workflow_condition(
        {"mode": "all", "rules": [{"path": "amount", "operator": "gte", "value": 10}]},
        {},
    )
    assert not conditions.evaluate_workflow_condition(
        {"mode": "all", "rules": [{"path": "amount", "operator": "gte", "value": 10}]},
        {"amount": "10"},
    )
    assert not conditions.evaluate_workflow_condition(
        {"mode": "all", "rules": [{"path": "amount", "operator": "ne", "value": 10}]},
        {"amount": "10"},
    )
    assert conditions.evaluate_workflow_condition(
        {"mode": "all", "rules": [{"path": "amount", "operator": "eq", "value": 10}]},
        {"amount": 10.0},
    )


def test_malformed_persisted_condition_is_rejected() -> None:
    conditions = _conditions()
    with pytest.raises(conditions.WorkflowConditionError):
        conditions.evaluate_workflow_condition(
            {"mode": "all", "rules": [{"path": "amount", "operator": "python_eval", "value": "x"}]},
            {"amount": 10},
        )
