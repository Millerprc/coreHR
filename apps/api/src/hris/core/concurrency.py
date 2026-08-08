from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VersionCommand(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    expected_version: int = Field(ge=1)
    idempotency_key: UUID
    change_reason: str = Field(min_length=1, max_length=500)
