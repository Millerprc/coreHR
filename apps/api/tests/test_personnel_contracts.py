from datetime import date

import pytest
from pydantic import ValidationError

from hris.modules.workforce.extended_schemas import (
    EmploymentLegalEntityRelationCreate,
    PersonCreate,
)


def test_person_create_requires_legal_name_and_defaults_display_name() -> None:
    payload = PersonCreate(
        legal_name="Synthetic Legal Name",
        reserve_employee_number=False,
        change_reason="Create synthetic personnel record",
    )

    assert payload.legal_name == "Synthetic Legal Name"
    assert payload.display_name == "Synthetic Legal Name"

    with pytest.raises(ValidationError):
        PersonCreate(
            reserve_employee_number=False,
            change_reason="Missing legal name must be rejected",
        )


def test_legal_entity_relation_change_requires_supported_kind() -> None:
    payload = EmploymentLegalEntityRelationCreate(
        relation_kind="payroll",
        legal_entity_id="11111111-1111-1111-1111-111111111111",
        effective_from=date(2026, 9, 1),
        change_reason="Synthetic payroll entity change",
    )

    assert payload.relation_kind == "payroll"

    with pytest.raises(ValidationError):
        EmploymentLegalEntityRelationCreate(
            relation_kind="unknown",
            legal_entity_id="11111111-1111-1111-1111-111111111111",
            effective_from=date(2026, 9, 1),
            change_reason="Unsupported relation kind",
        )
