from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from hris.core.concurrency import VersionCommand
from hris.modules.workforce.organization_policy import (
    DomainViolation,
    assert_allocation_total,
    assert_no_cycle,
    assert_revenue_total,
)


def test_cycle_is_rejected() -> None:
    parents = {"BG": "GROUP", "BU": "BG", "GROUP": None}

    with pytest.raises(DomainViolation, match="ORGANIZATION_CYCLE"):
        assert_no_cycle("GROUP", "BU", parents)


def test_cost_allocation_requires_exactly_one_hundred_percent() -> None:
    with pytest.raises(DomainViolation, match="ALLOCATION_TOTAL_INVALID"):
        assert_allocation_total([Decimal("60"), Decimal("39.9999")])

    assert_allocation_total([Decimal("60"), Decimal("40")])


def test_monthly_revenue_must_equal_annual_revenue() -> None:
    with pytest.raises(DomainViolation, match="REVENUE_MONTH_TOTAL_INVALID"):
        assert_revenue_total(Decimal("120"), [Decimal("9")] * 12)

    assert_revenue_total(
        Decimal("120"),
        {month: Decimal("10") for month in range(1, 13)},
    )


def test_revenue_requires_exact_months_one_through_twelve() -> None:
    with pytest.raises(DomainViolation, match="REVENUE_MONTH_SET_INVALID"):
        assert_revenue_total(
            Decimal("110"),
            {month: Decimal("10") for month in range(1, 12)},
        )


def test_version_command_requires_expected_version_and_reason() -> None:
    with pytest.raises(ValidationError):
        VersionCommand(
            expected_version=0,
            idempotency_key=uuid4(),
            change_reason="合成测试",
        )

    with pytest.raises(ValidationError):
        VersionCommand(
            expected_version=1,
            idempotency_key=uuid4(),
            change_reason="",
        )
