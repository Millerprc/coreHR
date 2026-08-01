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
