"""Complete model registry for the business application and Alembic."""

from hris.shared.db import models as phase_models
from hris.modules.platform.models import (
    NumberSequence,
    Permission,
    Role,
    RolePermission,
    UserAccount,
    UserRole,
    UserSession,
)

__all__ = [
    "NumberSequence",
    "Permission",
    "Role",
    "RolePermission",
    "UserAccount",
    "UserRole",
    "UserSession",
    "phase_models",
]
