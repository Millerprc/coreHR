from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import TypeVar


Node = TypeVar("Node")
FOUR_PLACES = Decimal("0.0001")
ONE_HUNDRED = Decimal("100.0000")


class DomainViolation(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _amount(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES)


def assert_no_cycle(
    node: Node,
    proposed_parent: Node | None,
    parents: Mapping[Node, Node | None],
) -> None:
    current = proposed_parent
    visited: set[Node] = set()
    while current is not None:
        if current == node or current in visited:
            raise DomainViolation(
                "ORGANIZATION_CYCLE",
                "组织上下级关系不能形成循环",
            )
        visited.add(current)
        current = parents.get(current)


def assert_allocation_total(values: Sequence[Decimal]) -> None:
    normalized = [_amount(value) for value in values]
    if (
        not normalized
        or any(value <= 0 or value > ONE_HUNDRED for value in normalized)
        or sum(normalized, Decimal("0.0000")) != ONE_HUNDRED
    ):
        raise DomainViolation(
            "ALLOCATION_TOTAL_INVALID",
            "成本中心分摊比例合计必须精确等于100%",
        )


def assert_revenue_total(
    annual_amount: Decimal,
    months: Mapping[int, Decimal] | Sequence[Decimal],
) -> None:
    if isinstance(months, Mapping):
        if set(months) != set(range(1, 13)):
            raise DomainViolation(
                "REVENUE_MONTH_SET_INVALID",
                "收入目标必须包含1至12月且月份不能重复",
            )
        monthly_values = [months[month] for month in range(1, 13)]
    else:
        if len(months) != 12:
            raise DomainViolation(
                "REVENUE_MONTH_SET_INVALID",
                "收入目标必须包含12个月",
            )
        monthly_values = list(months)

    normalized_annual = _amount(annual_amount)
    normalized_months = [_amount(value) for value in monthly_values]
    if normalized_annual < 0 or any(value < 0 for value in normalized_months):
        raise DomainViolation(
            "REVENUE_AMOUNT_NEGATIVE",
            "收入目标不能为负数",
        )
    if sum(normalized_months, Decimal("0.0000")) != normalized_annual:
        raise DomainViolation(
            "REVENUE_MONTH_TOTAL_INVALID",
            "月度收入目标合计必须等于年度目标",
        )
