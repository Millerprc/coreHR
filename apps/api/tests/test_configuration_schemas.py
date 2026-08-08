from uuid import uuid4

import pytest
from pydantic import ValidationError

from hris.modules.platform.configuration_schemas import (
    DictionaryCreate,
    DictionaryItemCreate,
    DictionaryItemDeactivate,
    DictionaryItemUpdate,
)


def test_dictionary_code_is_stable_upper_snake_case() -> None:
    with pytest.raises(ValidationError):
        DictionaryCreate(code="employee type", name="人员类型")


def test_dictionary_item_requires_nonempty_name() -> None:
    with pytest.raises(ValidationError):
        DictionaryItemCreate(code="FORMAL", name="")


def test_dictionary_item_accepts_hierarchical_parent() -> None:
    parent_id = uuid4()

    payload = DictionaryItemCreate(
        code="LEVEL_2",
        name="二级",
        parent_item_id=parent_id,
        sort_order=20,
    )

    assert payload.parent_item_id == parent_id


def test_dictionary_item_update_requires_at_least_one_change() -> None:
    with pytest.raises(ValidationError):
        DictionaryItemUpdate()


def test_deactivation_requires_a_reason() -> None:
    with pytest.raises(ValidationError):
        DictionaryItemDeactivate(reason="")
