from hris.shared.db.base import Base
from hris.shared.db import models as registered_models


def test_phase_one_to_three_tables_are_registered() -> None:
    assert registered_models
    expected_tables = {
        "organizations",
        "organization_versions",
        "persons",
        "employments",
        "headcount_plans",
        "recruitment_requests",
        "hr_events",
        "workflow_definitions",
        "workflow_instances",
        "attendance_rule_sets",
        "attendance_punches",
        "leave_requests",
        "attendance_daily_results",
        "attendance_monthly_results",
    }

    assert expected_tables <= set(Base.metadata.tables)

