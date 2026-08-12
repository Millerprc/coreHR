from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BootstrapAdminRequest(BaseModel):
    bootstrap_token: str = Field(min_length=1, max_length=500)
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=200)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    status: str
    person_id: UUID | None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


class LogoutResponse(BaseModel):
    status: str = "logged_out"


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    is_system: bool
    is_active: bool


class RoleListResponse(BaseModel):
    items: list[RoleResponse]


class UserAdminCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=12, max_length=200)
    role_codes: list[str] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.casefold()

    @field_validator("display_name", "reason")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("role_codes")
    @classmethod
    def normalize_role_codes(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(code.strip().upper() for code in value if code.strip()))
        if not normalized:
            raise ValueError("at least one role code is required")
        return normalized


class UserAdminUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    role_codes: list[str] | None = Field(default=None, min_length=1, max_length=20)
    status: str | None = Field(default=None, pattern=r"^(active|inactive)$")
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("display_name", "reason")
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("role_codes")
    @classmethod
    def normalize_role_codes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        normalized = list(dict.fromkeys(code.strip().upper() for code in value if code.strip()))
        if not normalized:
            raise ValueError("at least one role code is required")
        return normalized

    @model_validator(mode="after")
    def validate_change(self) -> "UserAdminUpdate":
        if not self.model_dump(exclude={"reason"}, exclude_unset=True):
            raise ValueError("at least one account field must be changed")
        return self


class UserAdminResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
    status: str
    person_id: UUID | None
    roles: list[str]


class UserAdminListResponse(BaseModel):
    items: list[UserAdminResponse]
    total: int
    limit: int
    offset: int
