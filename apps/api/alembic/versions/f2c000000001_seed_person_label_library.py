# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""seed person label library dictionary

Revision ID: f2c000000001
Revises: f2b000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "f2c000000001"
down_revision: str | Sequence[str] | None = "f2b000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LIBRARY_CODE = "PERSON_LABEL_LIBRARY"

# 标签类型（字典第 0 级）与其下的标签项（字典第 1 级）。
LABEL_LIBRARY_SEED: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "TECH_SKILL",
        "技术技能",
        (
            ("PY_LANG", "Python"),
            ("JAVA_LANG", "Java"),
            ("FRONTEND_DEV", "前端开发"),
            ("DATA_ANALYSIS", "数据分析"),
            ("PRODUCT_DESIGN", "产品设计"),
        ),
    ),
    (
        "CERTIFICATION",
        "专业资格",
        (
            ("PMP", "项目管理认证"),
            ("CIA", "内部审计认证"),
            ("CPA", "注册会计师"),
        ),
    ),
    (
        "TALENT_FLAG",
        "人才标签",
        (
            ("KEY_SUCCESSOR", "关键岗位继任者"),
            ("HIGH_POTENTIAL", "高潜人才"),
            ("CORE_BACKBONE", "核心骨干"),
        ),
    ),
    (
        "CULTURE_MATCH",
        "文化匹配",
        (
            ("HIGH_PERFORMER", "高绩效"),
            ("HIGH_COLLABORATION", "高协作"),
            ("STRONG_EXECUTION", "强执行力"),
        ),
    ),
)


def upgrade() -> None:
    connection = op.get_bind()
    dictionary_id = connection.execute(
        sa.text("SELECT id FROM data_dictionaries WHERE code = :code"),
        {"code": LIBRARY_CODE},
    ).scalar_one_or_none()
    if dictionary_id is None:
        dictionary_id = uuid4()
        connection.execute(
            sa.text(
                """
                INSERT INTO data_dictionaries (
                    id, code, name, english_name, description, source, is_active
                )
                VALUES (
                    :id,
                    :code,
                    :name,
                    :english_name,
                    :description,
                    'manual',
                    true
                )
                """
            ),
            {
                "id": dictionary_id,
                "code": LIBRARY_CODE,
                "name": "员工标签库",
                "english_name": "Person Label Library",
                "description": "员工标签的类型与标签项，由基础资料维护并可扩展",
            },
        )

    for type_code, type_name, items in LABEL_LIBRARY_SEED:
        type_id = connection.execute(
            sa.text(
                """
                SELECT id FROM data_dictionary_items
                WHERE dictionary_id = :dictionary_id AND code = :code
                """
            ),
            {"dictionary_id": dictionary_id, "code": type_code},
        ).scalar_one_or_none()
        if type_id is None:
            type_id = uuid4()
            connection.execute(
                sa.text(
                    """
                    INSERT INTO data_dictionary_items (
                        id, dictionary_id, parent_item_id, code, name,
                        english_name, sort_order, level, description, is_active
                    )
                    VALUES (
                        :id, :dictionary_id, NULL, :code, :name,
                        NULL, :sort_order, 0, NULL, true
                    )
                    """
                ),
                {
                    "id": type_id,
                    "dictionary_id": dictionary_id,
                    "code": type_code,
                    "name": type_name,
                    "sort_order": 0,
                },
            )
        for sort_order, (item_code, item_name) in enumerate(items, start=1):
            existing = connection.execute(
                sa.text(
                    """
                    SELECT id FROM data_dictionary_items
                    WHERE dictionary_id = :dictionary_id AND code = :code
                    """
                ),
                {"dictionary_id": dictionary_id, "code": item_code},
            ).scalar_one_or_none()
            if existing is not None:
                continue
            connection.execute(
                sa.text(
                    """
                    INSERT INTO data_dictionary_items (
                        id, dictionary_id, parent_item_id, code, name,
                        english_name, sort_order, level, description, is_active
                    )
                    VALUES (
                        :id, :dictionary_id, :parent_item_id, :code, :name,
                        NULL, :sort_order, 1, NULL, true
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "dictionary_id": dictionary_id,
                    "parent_item_id": type_id,
                    "code": item_code,
                    "name": item_name,
                    "sort_order": sort_order,
                },
            )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM data_dictionary_items
            WHERE dictionary_id = (
                SELECT id FROM data_dictionaries WHERE code = :code
            )
            """
        ),
        {"code": LIBRARY_CODE},
    )
    connection.execute(
        sa.text("DELETE FROM data_dictionaries WHERE code = :code"),
        {"code": LIBRARY_CODE},
    )
