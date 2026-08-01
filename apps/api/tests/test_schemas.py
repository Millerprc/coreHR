from datetime import date

import pytest
from pydantic import ValidationError

from hris.modules.attendance.schemas import AttendanceRuleSetCreate
from hris.modules.workforce.schemas import OrganizationCreate


def test_organization_code_must_be_numeric() -> None:
    with pytest.raises(ValidationError):
        OrganizationCreate(
            code="ORG-001",
            name="测试部门",
            organization_type_code="DEPARTMENT",
            effective_from=date(2026, 8, 1),
            change_reason="初始化",
        )


def test_attendance_rule_set_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError):
        AttendanceRuleSetCreate(
            code="CN_STANDARD",
            name="中国标准考勤",
            timezone="Not/A-Timezone",
            effective_from=date(2026, 8, 1),
        )

