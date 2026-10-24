# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""权限码覆盖守卫：源码引用的权限码必须已经落到 permissions 表。

Requirement: D-053 — 权限沿 permissions → role_permissions → roles → user_roles 解析，
permissions 表里没有的行永远无法被任何角色持有。因此源码里一旦出现新的权限码字面量，
就必须有对应迁移把它种进 permissions 表，否则该接口对除持 `*` 的主管理员外都是 403。

采集方式说明：本文件用 ast 解析而不是逐行正则。多个调用点（例如
modules/workforce/personnel_api.py 的 require_permissions 多行调用）跨行书写，
逐行正则会漏抓，漏抓会让守卫静默失效。
"""

import ast
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.platform.models import Permission, Role, RolePermission


pytestmark = pytest.mark.asyncio

_API_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_ROOT = _API_ROOT / "src" / "hris"
_MIGRATION_PATH = (
    _API_ROOT
    / "alembic"
    / "versions"
    / "f2f000000001_seed_missing_permission_codes.py"
)

# 定义鉴权辅助函数的模块：它内部的 require_permissions(permission_code) 是包装实现，
# 不是权限码引用点，因此不做「实参必须是字面量」的检查。
_PERMISSION_HELPER_MODULE = _SOURCE_ROOT / "modules" / "platform" / "dependencies.py"

_PERMISSION_GUARD_NAMES = frozenset(
    {"require_permission", "require_permissions", "ensure_permissions"}
)

# 各守卫函数中权限码实参的起始位置：
# require_permission(code) / require_permissions(code, ...) 的第 0 个实参就是权限码；
# ensure_permissions(user, db, code, ...) 的前两个实参是用户与会话。
_PERMISSION_ARGUMENT_START = {
    "require_permission": 0,
    "require_permissions": 0,
    "ensure_permissions": 2,
}

# 主管理员通配权限码。
# 取舍说明：`*` 不是迁移种下的权限码，而是平台初始化时由
# modules/platform/service.py 的 AuthService.bootstrap_admin 创建的
# （主管理员角色连同该权限一起写入）。因此全新迁移出来的库本来就没有这一行，
# 守卫不能要求它必须存在，只能在比对时把它排除。
SUPERUSER_WILDCARD_CODE = "*"

# 仅供前端菜单展示、源码不直接引用的权限码登记在此。
# 取舍说明：目前 permissions 表里每一条权限码都能在源码里找到引用点，
# 因此保留「库中每条权限码都必须能被源码解释」的严格断言。
# 将来若出现纯菜单用的权限码，必须显式登记到这里并说明原因，而不是把守卫整体放宽。
FRONTEND_ONLY_PERMISSION_CODES: frozenset[str] = frozenset()


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    """收集模块顶层的字符串常量，用于解析 ONBOARDING_INITIATE_PERMISSION 这类引用。"""

    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if value is None or len(targets) != 1:
            continue
        target = targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            constants[target.id] = value.value
    return constants


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _permission_codes_of_call(
    node: ast.Call,
    constants: dict[str, str],
) -> tuple[set[str], list[str]]:
    """返回该调用解析出的权限码集合，以及无法解析的实参描述。"""

    name = _called_name(node)
    if name is None or name not in _PERMISSION_GUARD_NAMES:
        return set(), []
    start = _PERMISSION_ARGUMENT_START[name]
    codes: set[str] = set()
    unresolved: list[str] = []
    for argument in node.args[start:]:
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            codes.add(argument.value)
        elif isinstance(argument, ast.Name) and argument.id in constants:
            codes.add(constants[argument.id])
        else:
            unresolved.append(f"{name}(...{ast.unparse(argument)}...)")
    for keyword in node.keywords:
        if keyword.arg is None:
            continue
        value = keyword.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            codes.add(value.value)
        elif isinstance(value, ast.Name) and value.id in constants:
            codes.add(constants[value.id])
    return codes, unresolved


def _scan_source() -> tuple[set[str], list[str]]:
    """扫描 src/hris 下所有 .py，返回被引用的权限码与无法解析的引用点。"""

    referenced: set[str] = set()
    unresolved: list[str] = []
    for path in sorted(_SOURCE_ROOT.rglob("*.py")):
        # 用 utf-8-sig 读取：部分源文件带 BOM，ast.parse 不接受残留的 U+FEFF。
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        constants = _module_string_constants(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            codes, unresolved_calls = _permission_codes_of_call(node, constants)
            referenced |= codes
            if path == _PERMISSION_HELPER_MODULE:
                continue
            for description in unresolved_calls:
                unresolved.append(f"{path.relative_to(_SOURCE_ROOT)}:{node.lineno} {description}")
    return referenced, unresolved


def referenced_permission_codes() -> set[str]:
    """源码中被 require_permission / require_permissions / ensure_permissions 引用的权限码。"""

    referenced, _ = _scan_source()
    return referenced


def _load_permission_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "f2f000000001_seed_missing_permission_codes", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_missing_permission_codes_are_seeded(db_session: AsyncSession) -> None:
    rows = (
        await db_session.execute(
            select(Permission.code, Permission.module_code).where(
                Permission.code.in_(
                    ("WORKFORCE_ADMIN", "LIFECYCLE_ADMIN", "ATTENDANCE_ADMIN")
                )
            )
        )
    ).all()
    assert {row.code: row.module_code for row in rows} == {
        "WORKFORCE_ADMIN": "WORKFORCE",
        "LIFECYCLE_ADMIN": "LIFECYCLE",
        "ATTENDANCE_ADMIN": "ATTENDANCE",
    }


async def test_referenced_permission_codes_exist_in_permissions_table(
    db_session: AsyncSession,
) -> None:
    referenced = referenced_permission_codes()
    assert referenced, "源码必须至少引用一个权限码，否则扫描逻辑本身失效"

    stored = set((await db_session.scalars(select(Permission.code))).all())
    missing = sorted((referenced - {SUPERUSER_WILDCARD_CODE}) - stored)
    assert not missing, f"源码引用了未落库的权限码：{missing}"


async def test_permission_code_arguments_are_resolvable() -> None:
    _, unresolved = _scan_source()
    assert not unresolved, (
        "权限码实参必须是字面量或模块顶层字符串常量，"
        f"否则守卫无法确认其落库：{unresolved}"
    )


async def test_stored_permission_codes_are_explainable_by_source(
    db_session: AsyncSession,
) -> None:
    referenced = referenced_permission_codes()
    stored = set((await db_session.scalars(select(Permission.code))).all())
    unexplained = sorted(
        stored
        - referenced
        - {SUPERUSER_WILDCARD_CODE}
        - set(FRONTEND_ONLY_PERMISSION_CODES)
    )
    assert not unexplained, f"permissions 表里存在源码无法解释的权限码：{unexplained}"


async def test_workforce_admin_role_receives_person_permissions_after_replay(
    db_session: AsyncSession,
) -> None:
    migration = _load_permission_migration()
    person_codes = migration.PERSON_PERMISSION_CODES_GRANTED_TO_WORKFORCE_ADMIN

    workforce_permission = await db_session.scalar(
        select(Permission).where(Permission.code == "WORKFORCE_ADMIN")
    )
    assert workforce_permission is not None, "WORKFORCE_ADMIN 必须已经落库"

    person_rows = (
        await db_session.execute(
            select(Permission.code, Permission.id).where(
                Permission.code.in_(person_codes)
            )
        )
    ).all()
    assert {row.code for row in person_rows} == set(person_codes)

    role = Role(
        code="SYNTHETIC_WORKFORCE_ADMIN",
        name="合成人力管理员",
        is_system=False,
        is_active=True,
    )
    db_session.add(role)
    await db_session.flush()
    db_session.add(
        RolePermission(role_id=role.id, permission_id=workforce_permission.id)
    )
    await db_session.flush()

    grant_sql = migration.person_permission_grant_sql()
    for _ in range(2):
        await db_session.execute(text(grant_sql))
    await db_session.flush()

    granted_codes = set(
        (
            await db_session.scalars(
                select(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            )
        ).all()
    )
    assert set(person_codes).issubset(granted_codes)
    assert "PERSON_VIEW" in granted_codes

    granted_rows = await db_session.scalar(
        select(func.count())
        .select_from(RolePermission)
        .where(RolePermission.role_id == role.id)
    )
    assert granted_rows == len(person_codes) + 1, "重复重放授权语句不应产生重复授权行"
