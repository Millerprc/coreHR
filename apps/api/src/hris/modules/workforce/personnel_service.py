from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.core.errors import ApiError
from hris.core.personnel_security import (
    ProtectedValue,
    SensitiveDataError,
    SensitiveValueProtector,
    mask_document_number,
    mask_email,
    mask_phone,
    mask_text,
    normalize_document_number,
    normalize_email,
    normalize_phone,
    normalize_text,
    protector_from_settings,
)
from hris.modules.workforce.models import (
    AuditLog,
    EmergencyContact,
    Person,
    PersonAddress,
    PersonContact,
    PersonDocument,
)
from hris.modules.workforce.personnel_schemas import (
    EmergencyContactCreate,
    PersonAddressCreate,
    PersonContactCreate,
    PersonDocumentCreate,
)


class PersonnelService:
    def __init__(self, session: AsyncSession, *, actor_id: UUID, trace_id: str) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    def _protector(self) -> SensitiveValueProtector:
        try:
            return protector_from_settings(get_settings())
        except SensitiveDataError:
            raise ApiError(
                status_code=503,
                code="PERSONNEL_SENSITIVE_KEY_UNAVAILABLE",
                message="人员敏感字段密钥未就绪，已拒绝本次操作",
            ) from None

    async def _person(self, person_id: UUID) -> Person:
        person = await self._session.get(Person, person_id)
        if person is None:
            raise ApiError(status_code=404, code="PERSON_NOT_FOUND", message="人员不存在")
        return person

    def _audit(
        self,
        *,
        action: str,
        object_type: str,
        object_id: UUID,
        person_id: UUID,
        reason: str,
        fields: list[str],
        masked_values: dict[str, str] | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type=object_type,
                object_id=object_id,
                reason=reason,
                before_payload={},
                after_payload={
                    "person_id": str(person_id),
                    "fields": fields,
                    "masked_values": masked_values or {},
                },
                source="api",
            )
        )

    @staticmethod
    def _protected_columns(value: ProtectedValue, prefix: str) -> dict[str, Any]:
        return {
            f"{prefix}_key_version": value.key_version,
            f"{prefix}_nonce": value.nonce,
            f"{prefix}_ciphertext": value.ciphertext,
        }

    async def _ensure_primary_available(
        self,
        model: type[PersonDocument] | type[PersonContact],
        *,
        person_id: UUID,
        effective_from: Any,
        effective_to: Any,
        extra_filters: list[Any],
        error_code: str,
    ) -> None:
        filters = [model.person_id == person_id, model.is_primary.is_(True), *extra_filters]
        if effective_to is not None:
            filters.append(model.effective_from <= effective_to)
        filters.append(or_(model.effective_to.is_(None), model.effective_to >= effective_from))
        if await self._session.scalar(select(model.id).where(*filters).limit(1)) is not None:
            raise ApiError(status_code=409, code=error_code, message="同一有效期间只能有一条主要记录")

    async def create_document(
        self, person_id: UUID, payload: PersonDocumentCreate
    ) -> PersonDocument:
        await self._person(person_id)
        if payload.is_primary:
            await self._ensure_primary_available(
                PersonDocument,
                person_id=person_id,
                effective_from=payload.effective_from,
                effective_to=payload.effective_to,
                extra_filters=[],
                error_code="PRIMARY_DOCUMENT_PERIOD_OVERLAP",
            )
        record_id = uuid4()
        protected = self._protector().protect(
            payload.document_number,
            field_code="document_number",
            record_id=record_id,
            normalizer=normalize_document_number,
            masker=mask_document_number,
        )
        duplicate = await self._session.scalar(
            select(PersonDocument.id).where(
                PersonDocument.person_id == person_id,
                PersonDocument.document_type_code == payload.document_type_code,
                PersonDocument.issuing_country_code == payload.issuing_country_code,
                PersonDocument.document_number_digest == protected.search_digest,
            )
        )
        if duplicate is not None:
            raise ApiError(status_code=409, code="PERSON_DOCUMENT_EXISTS", message="该人员证件已存在")
        record = PersonDocument(
            id=record_id,
            person_id=person_id,
            **payload.model_dump(exclude={"document_number", "change_reason"}),
            **self._protected_columns(protected, "document_number"),
            masked_document_number=protected.masked_value,
            document_number_digest=protected.search_digest,
        )
        self._session.add(record)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="person_document",
            object_id=record.id,
            person_id=person_id,
            reason=payload.change_reason,
            fields=["document_number"],
            masked_values={"document_number": record.masked_document_number},
        )
        return record

    async def list_documents(self, person_id: UUID) -> list[PersonDocument]:
        await self._person(person_id)
        return list(
            (
                await self._session.scalars(
                    select(PersonDocument)
                    .where(PersonDocument.person_id == person_id)
                    .order_by(PersonDocument.is_primary.desc(), PersonDocument.effective_from.desc())
                )
            ).all()
        )

    async def create_contact(
        self, person_id: UUID, payload: PersonContactCreate
    ) -> PersonContact:
        await self._person(person_id)
        if payload.is_primary:
            await self._ensure_primary_available(
                PersonContact,
                person_id=person_id,
                effective_from=payload.effective_from,
                effective_to=payload.effective_to,
                extra_filters=[PersonContact.contact_type == payload.contact_type],
                error_code="PRIMARY_CONTACT_PERIOD_OVERLAP",
            )
        normalizer = normalize_email if payload.contact_type.endswith("email") else normalize_phone
        masker = mask_email if payload.contact_type.endswith("email") else mask_phone
        record_id = uuid4()
        protected = self._protector().protect(
            payload.contact_value,
            field_code=payload.contact_type,
            record_id=record_id,
            normalizer=normalizer,
            masker=masker,
        )
        record = PersonContact(
            id=record_id,
            person_id=person_id,
            **payload.model_dump(exclude={"contact_value", "change_reason"}),
            **self._protected_columns(protected, "contact_value"),
            masked_contact_value=protected.masked_value,
            contact_value_digest=protected.search_digest,
        )
        self._session.add(record)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="person_contact",
            object_id=record.id,
            person_id=person_id,
            reason=payload.change_reason,
            fields=["contact_value"],
            masked_values={"contact_value": record.masked_contact_value},
        )
        return record

    async def list_contacts(self, person_id: UUID) -> list[PersonContact]:
        await self._person(person_id)
        return list(
            (
                await self._session.scalars(
                    select(PersonContact)
                    .where(PersonContact.person_id == person_id)
                    .order_by(PersonContact.contact_type, PersonContact.effective_from.desc())
                )
            ).all()
        )

    async def create_address(
        self, person_id: UUID, payload: PersonAddressCreate
    ) -> PersonAddress:
        await self._person(person_id)
        record_id = uuid4()
        protected = self._protector().protect(
            payload.address_detail,
            field_code="address_detail",
            record_id=record_id,
            normalizer=normalize_text,
            masker=mask_text,
        )
        record = PersonAddress(
            id=record_id,
            person_id=person_id,
            **payload.model_dump(exclude={"address_detail", "change_reason"}),
            **self._protected_columns(protected, "address_detail"),
            masked_address_detail=protected.masked_value,
        )
        self._session.add(record)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="person_address",
            object_id=record.id,
            person_id=person_id,
            reason=payload.change_reason,
            fields=["address_detail"],
            masked_values={"address_detail": record.masked_address_detail},
        )
        return record

    async def list_addresses(self, person_id: UUID) -> list[PersonAddress]:
        await self._person(person_id)
        return list(
            (
                await self._session.scalars(
                    select(PersonAddress)
                    .where(PersonAddress.person_id == person_id)
                    .order_by(PersonAddress.address_type, PersonAddress.effective_from.desc())
                )
            ).all()
        )

    async def create_emergency_contact(
        self, person_id: UUID, payload: EmergencyContactCreate
    ) -> EmergencyContact:
        await self._person(person_id)
        record_id = uuid4()
        protector = self._protector()
        protected_name = protector.protect(
            payload.name,
            field_code="emergency_contact_name",
            record_id=record_id,
            normalizer=normalize_text,
            masker=mask_text,
        )
        protected_phone = protector.protect(
            payload.phone,
            field_code="emergency_contact_phone",
            record_id=record_id,
            normalizer=normalize_phone,
            masker=mask_phone,
        )
        record = EmergencyContact(
            id=record_id,
            person_id=person_id,
            **payload.model_dump(exclude={"name", "phone", "change_reason"}),
            **self._protected_columns(protected_name, "name"),
            **self._protected_columns(protected_phone, "phone"),
            masked_name=protected_name.masked_value,
            masked_phone=protected_phone.masked_value,
            phone_digest=protected_phone.search_digest,
        )
        self._session.add(record)
        await self._session.flush()
        self._audit(
            action="create",
            object_type="emergency_contact",
            object_id=record.id,
            person_id=person_id,
            reason=payload.change_reason,
            fields=["name", "phone"],
            masked_values={"name": record.masked_name, "phone": record.masked_phone},
        )
        return record

    async def list_emergency_contacts(self, person_id: UUID) -> list[EmergencyContact]:
        await self._person(person_id)
        return list(
            (
                await self._session.scalars(
                    select(EmergencyContact)
                    .where(EmergencyContact.person_id == person_id)
                    .order_by(EmergencyContact.effective_from.desc())
                )
            ).all()
        )

    async def reveal(
        self,
        *,
        person_id: UUID,
        record_type: str,
        record_id: UUID,
        field_code: str,
        reason: str,
    ) -> str:
        await self._person(person_id)
        model_fields: dict[str, tuple[type[Any], dict[str, tuple[str, str]]]] = {
            "document": (
                PersonDocument,
                {"document_number": ("document_number", "document_number")},
            ),
            "contact": (
                PersonContact,
                {"contact_value": ("contact_value", "dynamic_contact")},
            ),
            "address": (
                PersonAddress,
                {"address_detail": ("address_detail", "address_detail")},
            ),
            "emergency_contact": (
                EmergencyContact,
                {
                    "name": ("name", "emergency_contact_name"),
                    "phone": ("phone", "emergency_contact_phone"),
                },
            ),
        }
        model_config = model_fields.get(record_type)
        if model_config is None or field_code not in model_config[1]:
            raise ApiError(status_code=422, code="SENSITIVE_FIELD_UNSUPPORTED", message="不支持读取该敏感字段")
        model, field_map = model_config
        record = await self._session.get(model, record_id)
        if record is None or record.person_id != person_id:
            raise ApiError(status_code=404, code="SENSITIVE_RECORD_NOT_FOUND", message="敏感记录不存在")
        prefix, security_field_code = field_map[field_code]
        if security_field_code == "dynamic_contact":
            security_field_code = record.contact_type
        protected = ProtectedValue(
            key_version=getattr(record, f"{prefix}_key_version"),
            nonce=getattr(record, f"{prefix}_nonce"),
            ciphertext=getattr(record, f"{prefix}_ciphertext"),
            masked_value=getattr(record, f"masked_{prefix}"),
            search_digest=getattr(record, f"{prefix}_digest", ""),
        )
        try:
            value = self._protector().reveal(
                protected,
                field_code=security_field_code,
                record_id=record_id,
            )
        except SensitiveDataError:
            raise ApiError(
                status_code=503,
                code="PERSONNEL_SENSITIVE_VALUE_UNAVAILABLE",
                message="敏感字段认证失败，已拒绝读取",
            ) from None
        self._audit(
            action="reveal",
            object_type=f"person_{record_type}",
            object_id=record_id,
            person_id=person_id,
            reason=reason,
            fields=[field_code],
        )
        return value
