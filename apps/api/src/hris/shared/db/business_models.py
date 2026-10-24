# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Complete model registry for the business application and Alembic."""

from hris.shared.db import models as phase_models
from hris.modules.platform.models import (
    DataDictionary,
    DataDictionaryItem,
    ExternalRecordLink,
    LicenseRegistration,
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
from hris.modules.platform.task_models import BackgroundTask
from hris.modules.workforce.organization_models import (
    BpServiceScope,
    OrganizationEvent,
    OrganizationLeader,
    PersonBpMembership,
    RevenueTargetMonth,
)

__all__ = [
    "BackgroundTask",
    "DataDictionary",
    "DataDictionaryItem",
    "ExternalRecordLink",
    "ImportBatch",
    "ImportBatchRow",
    "LicenseRegistration",
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
