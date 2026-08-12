from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_permissions
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.personnel_schemas import (
    EducationRecordCreate,
    EducationRecordResponse,
    EmergencyContactCreate,
    EmergencyContactResponse,
    FamilyMemberCreate,
    FamilyMemberResponse,
    PersonAddressCreate,
    PersonAddressResponse,
    PersonContactCreate,
    PersonContactResponse,
    PersonDocumentCreate,
    PersonDocumentResponse,
    SensitiveRecordType,
    SensitiveRevealRequest,
    SensitiveRevealResponse,
    WorkExperienceCreate,
    WorkExperienceResponse,
)
from hris.modules.workforce.personnel_service import PersonnelService


router = APIRouter(prefix="/api/v1/workforce/persons", tags=["phase-1-personnel-sensitive"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
SensitiveViewer = Annotated[
    UserAccount,
    Depends(require_permissions("PERSON_VIEW", "PERSON_SENSITIVE_VIEW")),
]
SensitiveEditor = Annotated[
    UserAccount,
    Depends(
        require_permissions(
            "PERSON_VIEW",
            "PERSON_EDIT_BASIC",
            "PERSON_SENSITIVE_VIEW",
        )
    ),
]
SensitiveRevealer = Annotated[
    UserAccount,
    Depends(
        require_permissions(
            "PERSON_VIEW",
            "PERSON_SENSITIVE_VIEW",
            "PERSON_SENSITIVE_REVEAL",
        )
    ),
]


def service(db: AsyncSession, user: UserAccount, request: Request) -> PersonnelService:
    return PersonnelService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.post(
    "/{person_id}/documents",
    response_model=PersonDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    person_id: UUID,
    payload: PersonDocumentCreate,
    request: Request,
    db: DbSession,
    user: SensitiveEditor,
) -> PersonDocumentResponse:
    return PersonDocumentResponse.model_validate(
        await service(db, user, request).create_document(person_id, payload)
    )


@router.get("/{person_id}/documents", response_model=list[PersonDocumentResponse])
async def list_documents(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: SensitiveViewer,
) -> list[PersonDocumentResponse]:
    return [
        PersonDocumentResponse.model_validate(item)
        for item in await service(db, user, request).list_documents(person_id)
    ]


@router.post(
    "/{person_id}/contacts",
    response_model=PersonContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_contact(
    person_id: UUID,
    payload: PersonContactCreate,
    request: Request,
    db: DbSession,
    user: SensitiveEditor,
) -> PersonContactResponse:
    return PersonContactResponse.model_validate(
        await service(db, user, request).create_contact(person_id, payload)
    )


@router.get("/{person_id}/contacts", response_model=list[PersonContactResponse])
async def list_contacts(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: SensitiveViewer,
) -> list[PersonContactResponse]:
    return [
        PersonContactResponse.model_validate(item)
        for item in await service(db, user, request).list_contacts(person_id)
    ]


@router.post(
    "/{person_id}/addresses",
    response_model=PersonAddressResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_address(
    person_id: UUID,
    payload: PersonAddressCreate,
    request: Request,
    db: DbSession,
    user: SensitiveEditor,
) -> PersonAddressResponse:
    return PersonAddressResponse.model_validate(
        await service(db, user, request).create_address(person_id, payload)
    )


@router.get("/{person_id}/addresses", response_model=list[PersonAddressResponse])
async def list_addresses(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: SensitiveViewer,
) -> list[PersonAddressResponse]:
    return [
        PersonAddressResponse.model_validate(item)
        for item in await service(db, user, request).list_addresses(person_id)
    ]


@router.post(
    "/{person_id}/emergency-contacts",
    response_model=EmergencyContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_emergency_contact(
    person_id: UUID,
    payload: EmergencyContactCreate,
    request: Request,
    db: DbSession,
    user: SensitiveEditor,
) -> EmergencyContactResponse:
    return EmergencyContactResponse.model_validate(
        await service(db, user, request).create_emergency_contact(person_id, payload)
    )


@router.get(
    "/{person_id}/emergency-contacts",
    response_model=list[EmergencyContactResponse],
)
async def list_emergency_contacts(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: SensitiveViewer,
) -> list[EmergencyContactResponse]:
    return [
        EmergencyContactResponse.model_validate(item)
        for item in await service(db, user, request).list_emergency_contacts(person_id)
    ]


@router.post(
    "/{person_id}/education-records",
    response_model=EducationRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_education_record(
    person_id: UUID,
    payload: EducationRecordCreate,
    request: Request,
    db: DbSession,
    user: SensitiveEditor,
) -> EducationRecordResponse:
    return EducationRecordResponse.model_validate(
        await service(db, user, request).create_education_record(person_id, payload)
    )


@router.get("/{person_id}/education-records", response_model=list[EducationRecordResponse])
async def list_education_records(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: SensitiveViewer,
) -> list[EducationRecordResponse]:
    return [
        EducationRecordResponse.model_validate(item)
        for item in await service(db, user, request).list_education_records(person_id)
    ]


@router.post(
    "/{person_id}/work-experiences",
    response_model=WorkExperienceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_work_experience(
    person_id: UUID,
    payload: WorkExperienceCreate,
    request: Request,
    db: DbSession,
    user: SensitiveEditor,
) -> WorkExperienceResponse:
    return WorkExperienceResponse.model_validate(
        await service(db, user, request).create_work_experience(person_id, payload)
    )


@router.get("/{person_id}/work-experiences", response_model=list[WorkExperienceResponse])
async def list_work_experiences(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: SensitiveViewer,
) -> list[WorkExperienceResponse]:
    return [
        WorkExperienceResponse.model_validate(item)
        for item in await service(db, user, request).list_work_experiences(person_id)
    ]


@router.post(
    "/{person_id}/family-members",
    response_model=FamilyMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_family_member(
    person_id: UUID,
    payload: FamilyMemberCreate,
    request: Request,
    db: DbSession,
    user: SensitiveEditor,
) -> FamilyMemberResponse:
    return FamilyMemberResponse.model_validate(
        await service(db, user, request).create_family_member(person_id, payload)
    )


@router.get("/{person_id}/family-members", response_model=list[FamilyMemberResponse])
async def list_family_members(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: SensitiveViewer,
) -> list[FamilyMemberResponse]:
    return [
        FamilyMemberResponse.model_validate(item)
        for item in await service(db, user, request).list_family_members(person_id)
    ]


@router.post(
    "/{person_id}/sensitive-values/{record_type}/{record_id}/{field_code}/reveal",
    response_model=SensitiveRevealResponse,
)
async def reveal_sensitive_value(
    person_id: UUID,
    record_type: SensitiveRecordType,
    record_id: UUID,
    field_code: str,
    payload: SensitiveRevealRequest,
    request: Request,
    db: DbSession,
    user: SensitiveRevealer,
) -> SensitiveRevealResponse:
    value = await service(db, user, request).reveal(
        person_id=person_id,
        record_type=record_type,
        record_id=record_id,
        field_code=field_code,
        reason=payload.reason,
    )
    return SensitiveRevealResponse(
        record_type=record_type,
        record_id=record_id,
        field_code=field_code,
        value=value,
    )
