# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.models import NumberSequence


async def next_number(
    session: AsyncSession,
    *,
    sequence_code: str,
    width: int,
    max_value: int,
    prefix: str = "",
) -> str:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:sequence_code))"),
        {"sequence_code": f"corehr:{sequence_code}"},
    )
    sequence = await session.scalar(
        select(NumberSequence)
        .where(NumberSequence.code == sequence_code)
        .with_for_update()
    )
    if sequence is None:
        sequence = NumberSequence(
            code=sequence_code,
            current_value=0,
            width=width,
            max_value=max_value,
        )
        session.add(sequence)
        await session.flush()
    if sequence.current_value >= sequence.max_value:
        raise ApiError(
            status_code=409,
            code="NUMBER_SEQUENCE_EXHAUSTED",
            message=f"流水号空间已耗尽：{sequence_code}",
        )
    sequence.current_value += 1
    return f"{prefix}{str(sequence.current_value).zfill(sequence.width)}"


async def advance_number_sequence(
    session: AsyncSession,
    *,
    sequence_code: str,
    width: int,
    max_value: int,
    minimum_value: int,
) -> int | None:
    """把序列当前值抬到至少 ``minimum_value``。

    Requirement: D-109 — 导入保留历史编码后必须推进自动编号序列，
    否则后续取号会撞上已占用的稳定编码。推进动作与调用方处于同一事务，
    并复用 next_number 的同一把事务级 advisory lock，避免与并发取号互相覆盖。

    序列行不存在时直接跳过（不凭空造行）；超出位宽或上限的目标值同样跳过，
    因为这种编码序列本就生成不出来。

    边界说明：``next_number`` 在 ``current_value >= max_value`` 时才抛错，
    因此序列**能**生成到 ``max_value`` 本身。故上界判定用 ``> max_value``
    而不是 ``>= max_value``——否则导入的历史编码恰好等于上限时会漏推进，
    后续自动取号仍会撞上它。
    """
    if minimum_value <= 0:
        return None
    if minimum_value > max_value:
        return None
    if len(str(minimum_value)) > width:
        return None
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:sequence_code))"),
        {"sequence_code": f"corehr:{sequence_code}"},
    )
    sequence = await session.scalar(
        select(NumberSequence)
        .where(NumberSequence.code == sequence_code)
        .with_for_update()
    )
    if sequence is None:
        return None
    if minimum_value > sequence.max_value:
        return None
    if sequence.current_value >= minimum_value:
        return sequence.current_value
    sequence.current_value = minimum_value
    return sequence.current_value
