# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

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

