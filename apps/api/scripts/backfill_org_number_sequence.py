# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""回填组织自动编号序列（ORG_NUMBER），可重复执行、幂等。

为什么需要这个脚本
------------------
审计 B 组 P0（``01:92`` 组织编码自动避让导入的历史编码）的修复分两层：

1. **导入时推进**：新导入的组织批次落库后，按本批次的纯数字编码推进 ``ORG_NUMBER``
   （实现见 ``hris.modules.platform.numbering.advance_number_sequence``）。
2. **存量回填**（本脚本）：在第 1 层落地**之前**就已经导入过历史编码的环境，
   序列仍然落后于已占用的编码，后续自动取号会撞 ``organizations.code`` 唯一约束。

本脚本只做第 2 层，扫描 ``organizations`` 表里**纯 ASCII 数字**的编码，
取最大值把序列抬上去；已经是最新值时什么都不做。

运行方式（容器内，``/work`` 为 ``apps/api`` 挂载点）::

    python scripts/backfill_org_number_sequence.py

安全约束：

- 只读 ``organizations``、只写 ``number_sequences`` 的一行；
- 不删除、不修改任何组织数据；
- 幂等：重复执行结果一致；
- 不推进到超出位宽（6 位）或上限（999999）的值——那种编码序列本就生成不出来。
"""

from __future__ import annotations

import asyncio
import re

from sqlalchemy import select

from hris.core.database import session_factory  # noqa: E402
from hris.modules.platform.models import NumberSequence  # noqa: E402
from hris.modules.platform.numbering import advance_number_sequence  # noqa: E402
from hris.modules.workforce.models import Organization  # noqa: E402


SEQUENCE_CODE = "ORG_NUMBER"
SEQUENCE_WIDTH = 6
SEQUENCE_MAX_VALUE = 999_999

#: 只认纯 ASCII 数字的编码；带前缀或后缀的编码（如 ``ORG-001``）不由该序列生成。
NUMERIC_CODE = re.compile(r"^\d+$")


async def backfill() -> int:
    async with session_factory() as session:
        codes = list((await session.scalars(select(Organization.code))).all())
        numeric = [int(code) for code in codes if code and NUMERIC_CODE.match(code)]
        highest = max(numeric) if numeric else 0

        sequence = await session.scalar(
            select(NumberSequence).where(NumberSequence.code == SEQUENCE_CODE)
        )
        if sequence is None:
            print(
                f"未找到序列 {SEQUENCE_CODE}，跳过（该序列由迁移 f1a000000001 预置，"
                "正常迁移过的库都存在）"
            )
            await session.rollback()
            return 0

        before = sequence.current_value
        if highest <= before:
            print(f"序列已是最新（current_value={before}），无需回填")
            await session.rollback()
            return 0

        advanced = await advance_number_sequence(
            session,
            sequence_code=SEQUENCE_CODE,
            width=SEQUENCE_WIDTH,
            max_value=SEQUENCE_MAX_VALUE,
            minimum_value=highest,
        )
        await session.commit()

        print(
            f"已回填 {SEQUENCE_CODE}：{before} -> {advanced}"
            f"（库内最大纯数字组织编码 {highest}）"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(backfill()))
