from hris.shared.db.base import Base
from hris.shared.db import models as registered_models
from hris.shared.db import business_models as registered_business_models


def test_phase_one_to_three_tables_are_registered() -> None:
    assert registered_models
    assert registered_business_models
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
        "data_dictionaries",
        "data_dictionary_items",
        "external_record_links",
        "person_labels",
    }

    assert expected_tables <= set(Base.metadata.tables)


def test_external_record_links_do_not_store_raw_source_payloads() -> None:
    columns = set(Base.metadata.tables["external_record_links"].columns.keys())

    assert "raw_payload" not in columns
    assert "source_record_id" in columns
    assert "source_checksum" in columns
