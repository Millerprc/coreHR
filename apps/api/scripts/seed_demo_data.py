# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""本地开发演示数据播种脚本（可重复执行，幂等）。

为什么需要这个脚本
------------------
演示数据以前是一次性临时脚本插进去的，**当时中文被按非 UTF-8 编码写成了字面量 `?`**，
所以「汇报关系」页面的上级/下级列显示成 `?????`（`persons.display_name` 里存的就是问号，
不是浏览器渲染问题）。这类"临时脚本 + 一次性播种"有三个隐患：

1. 中文容易在「PowerShell 管道 → 原生命令」这一环被按 ANSI 编码损坏；
2. 数据不可复现：换一台机器 / 重置库之后就没有了；
3. 没有归属：没人说得清哪些行是演示数据、哪些是真实数据。

这个脚本把演示数据变成**带固定 UUID 的夹具（fixture）**，并用 SQLAlchemy 参数化写入
（**绝不**用 `psql` 管道灌中文）。重复执行只会把演示数据复位到定义好的样子。

用法（在本机 Docker 环境里）::

    $root = "C:\\Users\\83289\\Documents\\HRMS\\coreHR"
    $enc = [System.Uri]::EscapeDataString("corehr_dev_only")
    $url = "postgresql+psycopg://corehr:${enc}@db:5432/corehr"
    docker run --rm --network corehr_default -v "${root}/apps/api:/work" -w /work `
      -e PYTHONPATH=/work/src -e "DATABASE_URL=$url" corehr-api `
      python scripts/seed_demo_data.py

只写 `persons` 与 `reporting_relations` 两张表，不碰任何其它业务数据。
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import select  # noqa: E402

from hris.core.database import session_factory  # noqa: E402
from hris.modules.workforce.models import Person, ReportingRelation  # noqa: E402

# ── 演示夹具（UUID 固定，便于幂等复位） ────────────────────────────────

DEMO_PERSONS: tuple[dict, ...] = (
    {
        "id": UUID("174355cd-6d2f-4b27-8cac-37655f238b58"),
        "employee_number": "000001",
        "legal_name": "演示人员",
        "display_name": "演示人员",
        "status": "active",
    },
    {
        "id": UUID("57d78b0b-0fd0-41cb-918e-54500f9f1a4f"),
        "employee_number": "000002",
        "legal_name": "演示主管",
        "display_name": "演示主管",
        "status": "active",
    },
    {
        "id": UUID("f17428a6-d4a0-4563-8793-fb80eaf23eea"),
        "employee_number": "000003",
        "legal_name": "演示专员",
        "display_name": "演示专员",
        "status": "active",
    },
)

DEMO_RELATIONS: tuple[dict, ...] = (
    {
        "id": UUID("889027f8-06fb-4600-9e92-b33432be56f2"),
        "manager_person_id": UUID("174355cd-6d2f-4b27-8cac-37655f238b58"),
        "subordinate_person_id": UUID("57d78b0b-0fd0-41cb-918e-54500f9f1a4f"),
        "relation_type": "direct",
    },
    {
        "id": UUID("9bd885aa-72a9-4aaa-9f4d-f6060c8d66e1"),
        "manager_person_id": UUID("174355cd-6d2f-4b27-8cac-37655f238b58"),
        "subordinate_person_id": UUID("f17428a6-d4a0-4563-8793-fb80eaf23eea"),
        "relation_type": "direct",
    },
    {
        "id": UUID("a390bac0-ec06-4794-a292-838641a477b2"),
        "manager_person_id": UUID("57d78b0b-0fd0-41cb-918e-54500f9f1a4f"),
        "subordinate_person_id": UUID("f17428a6-d4a0-4563-8793-fb80eaf23eea"),
        "relation_type": "dotted",
    },
    {
        "id": UUID("d9023498-3bf6-4dbd-8d57-7c7908c361e3"),
        "manager_person_id": UUID("f17428a6-d4a0-4563-8793-fb80eaf23eea"),
        "subordinate_person_id": UUID("174355cd-6d2f-4b27-8cac-37655f238b58"),
        "relation_type": "dotted",
    },
)

RELATION_EFFECTIVE_FROM = dt.date(2026, 10, 24)


def looks_corrupted(value: str | None) -> bool:
    """姓名是否只剩问号（当年编码损坏的痕迹）。"""
    if not value:
        return False
    stripped = value.replace("?", "").strip()
    return not stripped and "?" in value


async def seed() -> int:
    repaired = 0
    created = 0
    async with session_factory() as session:
        existing_people = {
            person.id: person
            for person in (await session.execute(select(Person))).scalars().all()
        }
        for row in DEMO_PERSONS:
            person = existing_people.get(row["id"])
            if person is None:
                person = Person(id=row["id"], status=row["status"])
                session.add(person)
                created += 1
            elif looks_corrupted(person.display_name) or looks_corrupted(
                person.legal_name
            ):
                repaired += 1
            person.employee_number = row["employee_number"]
            person.legal_name = row["legal_name"]
            person.display_name = row["display_name"]
            person.status = row["status"]

        existing_relations = {
            relation.id
            for relation in (
                await session.execute(select(ReportingRelation))
            ).scalars().all()
        }
        for row in DEMO_RELATIONS:
            if row["id"] in existing_relations:
                relation = (
                    await session.execute(
                        select(ReportingRelation).where(
                            ReportingRelation.id == row["id"]
                        )
                    )
                ).scalar_one()
            else:
                relation = ReportingRelation(id=row["id"])
                session.add(relation)
                created += 1
            relation.manager_person_id = row["manager_person_id"]
            relation.subordinate_person_id = row["subordinate_person_id"]
            relation.relation_type = row["relation_type"]
            relation.effective_from = RELATION_EFFECTIVE_FROM
            relation.effective_to = None

        await session.commit()

    print(f"演示人员 {len(DEMO_PERSONS)} 条，汇报关系 {len(DEMO_RELATIONS)} 条")
    print(f"新建 {created} 行，修复被编码损坏的姓名 {repaired} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(seed()))
