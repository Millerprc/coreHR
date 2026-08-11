from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_MISSING = object()
_ORDERED_OPERATORS = {"gt", "gte", "lt", "lte"}


class WorkflowConditionError(ValueError):
    """A persisted condition is malformed and must fail closed."""


def _resolve_path(context: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, _MISSING
        current = current[part]
    return True, current


def _is_orderable_pair(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return True
    return isinstance(left, str) and isinstance(right, str)


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def evaluate_workflow_rule(rule: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    path = rule.get("path")
    operator = rule.get("operator")
    if not isinstance(path, str) or not isinstance(operator, str):
        raise WorkflowConditionError("condition rule is missing path or operator")

    exists, actual = _resolve_path(context, path)
    if operator == "exists":
        return exists
    if operator == "not_exists":
        return not exists
    if not exists:
        return False

    expected = rule.get("value", _MISSING)
    if expected is _MISSING:
        raise WorkflowConditionError("condition rule is missing a comparison value")
    if operator == "eq":
        return _values_equal(actual, expected)
    if operator == "ne":
        if not (_values_equal(actual, expected) or _is_orderable_pair(actual, expected)):
            return False
        return not _values_equal(actual, expected)
    if operator in {"in", "not_in"}:
        if isinstance(expected, (str, bytes)) or not isinstance(expected, Sequence):
            raise WorkflowConditionError("membership condition value must be a list")
        compatible = [
            candidate
            for candidate in expected
            if _values_equal(actual, candidate) or _is_orderable_pair(actual, candidate)
        ]
        if not compatible:
            return False
        matched = any(actual == candidate for candidate in compatible)
        return matched if operator == "in" else not matched
    if operator in _ORDERED_OPERATORS:
        if not _is_orderable_pair(actual, expected):
            return False
        if operator == "gt":
            return actual > expected
        if operator == "gte":
            return actual >= expected
        if operator == "lt":
            return actual < expected
        return actual <= expected
    raise WorkflowConditionError("condition operator is not supported")


def evaluate_workflow_condition(
    condition: Mapping[str, Any],
    context: Mapping[str, Any],
) -> bool:
    if not isinstance(condition, Mapping):
        raise WorkflowConditionError("condition group is not an object")
    mode = condition.get("mode")
    rules = condition.get("rules")
    if mode not in {"all", "any"} or not isinstance(rules, list) or not rules:
        raise WorkflowConditionError("condition group is malformed")
    if not all(isinstance(rule, Mapping) for rule in rules):
        raise WorkflowConditionError("condition group contains a malformed rule")
    outcomes = [evaluate_workflow_rule(rule, context) for rule in rules]
    return all(outcomes) if mode == "all" else any(outcomes)
