"""Complete model registry for the business application and Alembic."""

from hris.shared.db import models as phase_models
from hris.modules.platform.models import (
    DataDictionary,
    DataDictionaryItem,
    ExternalRecordLink,
    NumberSequence,
    Permission,
    Role,
    RolePermission,
    UserAccount,
    UserRole,
    UserSession,
)
from hris.modules.platform.governance_models import OutboxEvent
from hris.modules.platform.import_models import ImportBatch, ImportBatchRow
from hris.modules.workforce.organization_models import (
    BpServiceScope,
    OrganizationEvent,
    OrganizationLeader,
    PersonBpMembership,
    RevenueTargetMonth,
)

__all__ = [
    "DataDictionary",
    "DataDictionaryItem",
    "ExternalRecordLink",
    "ImportBatch",
    "ImportBatchRow",
    "NumberSequence",
    "OutboxEvent",
    "Permission",
    "Role",
    "RolePermission",
    "UserAccount",
    "UserRole",
    "UserSession",
    "BpServiceScope",
    "OrganizationEvent",
    "OrganizationLeader",
    "PersonBpMembership",
    "RevenueTargetMonth",
    "phase_models",
]
