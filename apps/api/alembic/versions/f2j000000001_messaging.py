# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""platform messaging kernel tables

Revision ID: f2j000000001
Revises: f2i000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f2j000000001"
down_revision: str | Sequence[str] | None = "f2i000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Requirement: D-100 — 建立消息本体表与投递侧发件箱表。

    ``messages`` 是收件人的站内信本体；``message_deliveries`` 是投递记录，
    与业务写入同事务落库，保证「业务提交成功 ⇒ 消息必达」。
    """

    op.create_table(
        "messages",
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_ref_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["user_accounts.id"],
            name=op.f("fk_messages_recipient_user_id_user_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint(
            "idempotency_key",
            "recipient_user_id",
            name=op.f("uq_messages_idempotency_key"),
        ),
    )
    op.create_index(op.f("ix_messages_category"), "messages", ["category"], unique=False)
    op.create_index(
        "ix_messages_recipient_created",
        "messages",
        ["recipient_user_id", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_messages_source"), "messages", ["source"], unique=False)
    op.create_index(
        "ix_messages_unread",
        "messages",
        ["recipient_user_id"],
        unique=False,
        postgresql_where=sa.text("read_at IS NULL"),
    )

    op.create_table(
        "message_deliveries",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_deliveries_message_id_messages"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_deliveries")),
        sa.UniqueConstraint(
            "message_id",
            "channel",
            name=op.f("uq_message_deliveries_message_id"),
        ),
    )
    op.create_index(
        "ix_message_deliveries_dispatch",
        "message_deliveries",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    """回滚消息引擎的两张表。"""

    op.drop_index("ix_message_deliveries_dispatch", table_name="message_deliveries")
    op.drop_table("message_deliveries")

    op.drop_index("ix_messages_unread", table_name="messages")
    op.drop_index(op.f("ix_messages_source"), table_name="messages")
    op.drop_index("ix_messages_recipient_created", table_name="messages")
    op.drop_index(op.f("ix_messages_category"), table_name="messages")
    op.drop_table("messages")
