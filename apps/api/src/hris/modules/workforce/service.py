from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.workforce.models import (
    Organization,
    OrganizationType,
    OrganizationVersion,
)
from hris.modules.workforce.schemas import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationTypeCreate,
)


class WorkforceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_organization_type(
        self,
        payload: OrganizationTypeCreate,
    ) -> OrganizationType:
        existing = await self._session.scalar(
            select(OrganizationType).where(OrganizationType.code == payload.code)
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="ORGANIZATION_TYPE_CODE_EXISTS",
                message="组织类型代码已存在",
            )

        organization_type = OrganizationType(**payload.model_dump())
        self._session.add(organization_type)
        await self._session.flush()
        return organization_type

    async def create_organization(
        self,
        payload: OrganizationCreate,
    ) -> OrganizationResponse:
        existing = await self._session.scalar(
            select(Organization).where(Organization.code == payload.code)
        )
        if existing is not None:
            raise ApiError(
                status_code=409,
                code="ORGANIZATION_CODE_EXISTS",
                message="组织编码已存在",
            )

        organization_type = await self._session.scalar(
            select(OrganizationType).where(
                OrganizationType.code == payload.organization_type_code,
                OrganizationType.is_active.is_(True),
            )
        )
        if organization_type is None:
            raise ApiError(
                status_code=422,
                code="ORGANIZATION_TYPE_NOT_ACTIVE",
                message="组织类型不存在或未启用",
            )

        if payload.parent_organization_id is not None:
            parent = await self._session.get(
                Organization,
                payload.parent_organization_id,
            )
            if parent is None:
                raise ApiError(
                    status_code=422,
                    code="PARENT_ORGANIZATION_NOT_FOUND",
                    message="直接上级组织不存在",
                )

        organization = Organization(code=payload.code)
        self._session.add(organization)
        await self._session.flush()

        version = OrganizationVersion(
            organization_id=organization.id,
            version=1,
            name=payload.name,
            organization_type_id=organization_type.id,
            parent_organization_id=payload.parent_organization_id,
            country_code=payload.country_code,
            status="active",
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            is_current=True,
            change_reason=payload.change_reason,
        )
        self._session.add(version)
        await self._session.flush()

        return OrganizationResponse(
            id=organization.id,
            code=organization.code,
            name=version.name,
            organization_type_code=organization_type.code,
            organization_type_name=organization_type.name,
            parent_organization_id=version.parent_organization_id,
            country_code=version.country_code,
            status=version.status,
            effective_from=version.effective_from,
            effective_to=version.effective_to,
            version=version.version,
        )

    async def list_organizations(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[OrganizationResponse], int]:
        filters = (OrganizationVersion.is_current.is_(True),)
        total = await self._session.scalar(
            select(func.count())
            .select_from(OrganizationVersion)
            .where(*filters)
        )
        rows = (
            await self._session.execute(
                select(Organization, OrganizationVersion, OrganizationType)
                .join(
                    OrganizationVersion,
                    OrganizationVersion.organization_id == Organization.id,
                )
                .join(
                    OrganizationType,
                    OrganizationType.id == OrganizationVersion.organization_type_id,
                )
                .where(*filters)
                .order_by(Organization.code)
                .limit(limit)
                .offset(offset)
            )
        ).all()

        items = [
            OrganizationResponse(
                id=organization.id,
                code=organization.code,
                name=version.name,
                organization_type_code=organization_type.code,
                organization_type_name=organization_type.name,
                parent_organization_id=version.parent_organization_id,
                country_code=version.country_code,
                status=version.status,
                effective_from=version.effective_from,
                effective_to=version.effective_to,
                version=version.version,
            )
            for organization, version, organization_type in rows
        ]
        return items, total or 0

