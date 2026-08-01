from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from hris.modules.attendance.extended_schemas import PunchCreate, ShiftCreate
from hris.modules.workforce.extended_schemas import HeadcountPlanCreate


def test_headcount_month_must_be_first_day() -> None:
    with pytest.raises(ValidationError):
        HeadcountPlanCreate(
            organization_id="00000000-0000-0000-0000-000000000001",
            job_id="00000000-0000-0000-0000-000000000002",
            period_month="2026-08-02",
            planned_count="1",
            change_reason="test",
        )


def test_punch_requires_timezone() -> None:
    with pytest.raises(ValidationError):
        PunchCreate(
            employment_id="00000000-0000-0000-0000-000000000001",
            punched_at=datetime(2026, 8, 1, 9, 0),
            source="test",
            source_record_id="one",
        )

    valid = PunchCreate(
        employment_id="00000000-0000-0000-0000-000000000001",
        punched_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        source="test",
        source_record_id="two",
    )
    assert valid.punched_at.tzinfo is not None


def test_shift_midnight_consistency() -> None:
    with pytest.raises(ValidationError):
        ShiftCreate(
            code="DAY",
            name="day",
            start_time="09:00:00",
            end_time="08:00:00",
            crosses_midnight=False,
            rule_set_id="00000000-0000-0000-0000-000000000001",
        )
