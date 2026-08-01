from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.attendance.models import AttendanceRuleSet
from hris.modules.attendance.schemas import AttendanceRuleSetCreate


class AttendanceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_rule_set(
        self,
        payload: AttendanceRuleSetCreate,
    ) -> AttendanceRuleSet:
        existing = await self._session.scalar(
            select(AttendanceRuleSet).where(
                AttendanceRuleSet.code == payload.code,
                AttendanceRuleSet.version == 1,
            )
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="ATTENDANCE_RULE_SET_CODE_EXISTS",
                message="考勤规则集代码已存在",
            )

        rule_set = AttendanceRuleSet(
            **payload.model_dump(),
            version=1,
            status="draft",
        )
        self._session.add(rule_set)
        await self._session.flush()
        return rule_set

    async def list_rule_sets(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[AttendanceRuleSet], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(AttendanceRuleSet)
        )
        items = list(
            (
                await self._session.scalars(
                    select(AttendanceRuleSet)
                    .order_by(AttendanceRuleSet.code, AttendanceRuleSet.version.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        return items, total or 0

