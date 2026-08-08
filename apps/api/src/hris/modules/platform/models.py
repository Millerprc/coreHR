from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from hris.shared.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class UserAccount(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_accounts"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    person_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("persons.id"))
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Role(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Permission(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    module_code: Mapped[str] = mapped_column(String(80), nullable=False)


class UserRole(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("user_accounts.id"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("roles.id"),
        nullable=False,
        index=True,
    )


class RolePermission(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    role_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("roles.id"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("permissions.id"),
        nullable=False,
        index=True,
    )


class UserSession(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("user_accounts.id"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NumberSequence(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "number_sequences"

    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    max_value: Mapped[int] = mapped_column(Integer, nullable=False)


class DataDictionary(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_dictionaries"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    english_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DataDictionaryItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_dictionary_items"
    __table_args__ = (UniqueConstraint("dictionary_id", "code"),)

    dictionary_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("data_dictionaries.id"),
        nullable=False,
        index=True,
    )
    parent_item_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("data_dictionary_items.id"),
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    english_name: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ExternalRecordLink(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_record_links"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "source_table",
            "source_record_id",
            "target_type",
        ),
    )

    source_system: Mapped[str] = mapped_column(String(80), nullable=False)
    source_table: Mapped[str] = mapped_column(String(128), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_checksum: Mapped[str | None] = mapped_column(String(64))
