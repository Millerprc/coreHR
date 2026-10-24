# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""import batch execution mode

导入批次执行模式（审计 B 组 P0 · 01:219-220）。

Requirement: D-109 — 初始化导入整批校验、整批写入；日常批量维护允许正确行成功。
`mode` 区分两种语义：

- ``initialize``：初始化导入。任一阻断错误存在时整批不入库，
  ``execute_batch`` 直接返回 409，避免落库出层级残缺的主数据。
- ``daily``：日常批量维护。保持既有的部分成功语义（正确行入库、错误行标记）。

存量批次一律回填为 ``daily``（等价于既有行为），不需要数据回填脚本。

Revision ID: f2o000000001
Revises: f2m000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2o000000001"
down_revision: str | Sequence[str] | None = "f2m000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column(
            "mode",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'daily'"),
        ),
    )
    op.create_check_constraint(
        op.f("ck_import_batches_mode_allowed"),
        "import_batches",
        "mode IN ('initialize', 'daily')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_import_batches_mode_allowed"),
        "import_batches",
        type_="check",
    )
    op.drop_column("import_batches", "mode")
