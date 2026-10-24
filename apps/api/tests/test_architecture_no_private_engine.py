# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""公开仓里不得残留私有引擎实现的架构守卫。

Requirement: D-108 — 计划 §7 Wave 2 验收标准第 2 条：
「架构测试扫描公开仓源码，断言不含私有实现符号（如状态机判定函数名），
**故意塞入一个符号时必须报红**。」

守则 1（计划 §7）：**公开仓里不得残留可独立算出业务结果的代码**。
本测试把这条纪律变成可执行的门禁：私有实现一旦被复制回公开仓，CI 立刻报红。

扫描范围：公开仓源码 `apps/api/src`（不含测试——测试按「私有包是否可导入」跳过，
那是公开仓 CI 不依赖私有源的正常做法，不算私有实现残留）。

例外：`hris/modules/workflow/engine.py`（工厂）**必须**按名引用私有包才能装上，
因此它被单独放行；但测试额外断言该文件**只定义 `resolve_engine` 等少数符号**，
防止有人把引擎实现藏进工厂文件里。
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SOURCE_ROOT = API_ROOT / "src"

#: 工厂文件（唯一允许出现私有包名字的公开文件），相对 `apps/api/src`。
FACTORY_MODULE = "hris/modules/workflow/engine.py"

#: 工厂文件允许出现的顶层符号：工厂、可用性探测、常量与 logger。
FACTORY_ALLOWED_TOP_LEVEL: frozenset[str] = frozenset(
    {
        "resolve_engine",
        "enterprise_engine_available",
        "ENTERPRISE_PACKAGE_NAME",
        "logger",
    }
)

#: 私有实现符号清单（**本清单就是「什么算私有实现」的定义**）。
#:
#: 判定口径：凡是能**独立算出流程业务结果**的判定规则与执行动作都算私有；
#: 而「词表」（动作取值、中文标签、状态取值）与「读路径的取数与统计推导」
#: 属于公开契约与公开 API 契约，按计划 §2.2 保持公开。
PRIVATE_WORKFLOW_SYMBOLS: frozenset[str] = frozenset(
    {
        # ---- 条件求值（选路判定）----
        "evaluate_workflow_rule",
        "evaluate_workflow_condition",
        "WorkflowConditionError",
        # ---- 状态机与动作规格（迁移判定）----
        "INSTANCE_STATUS_TRANSITIONS",
        "TASK_STATUS_TRANSITIONS",
        "WORKFLOW_ACTION_SPECS",
        "WorkflowActionSpec",
        "action_spec",
        "ensure_instance_transition",
        "ensure_task_transition",
        # ---- 引擎内部的流程推进 ----
        "EnterpriseWorkflowEngine",
        "_advance_workflow",
        "_create_approval_tasks",
        "_select_workflow_route",
        "_record_workflow_route",
        "_apply_workflow_action",
        "_sibling_tasks",
        "_cancel_pending_siblings",
        "_handle_approve",
        "_handle_terminate",
        "_handle_reassign",
        "_handle_return",
        "_resolve_previous_approval_node",
        "_notify_workflow_action",
        # ---- 流转历史写入与通知出口 ----
        "WorkflowTransitionRecorder",
        "WorkflowNotifier",
        "NullWorkflowNotifier",
        "WorkflowNotification",
        "get_workflow_notifier",
        "set_workflow_notifier",
        # ---- 调度器 ----
        "WorkflowScheduler",
        "WorkflowSchedulerSettings",
    }
)

#: 私有包顶层导入名。
PRIVATE_PACKAGE_NAME = "corehr_enterprise"


def _iter_python_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _read_source(path: Path) -> str:
    """读源码。

    用 `utf-8-sig` 去掉可能存在的 BOM：个别历史文件带 BOM，
    Python 的 `ast.parse` 不接受字符串开头的 U+FEFF，而这不是本测试要管的事。
    """

    return path.read_text(encoding="utf-8-sig")


def _declared_names(tree: ast.Module) -> set[str]:
    """收集源码里出现过的**符号名**（定义、赋值、参数、导入别名）。"""

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _imported_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
                for alias in node.names:
                    modules.add(f"{node.module}.{alias.name}")
    return modules


def scan_source_for_private_symbols(source: str) -> set[str]:
    """在一段源码里找出属于私有实现清单的符号名。"""

    tree = ast.parse(source)
    return _declared_names(tree) & PRIVATE_WORKFLOW_SYMBOLS


def _relative(path: Path) -> str:
    return path.relative_to(API_ROOT).as_posix()


def test_scanner_detects_a_deliberately_injected_private_symbol() -> None:
    """守卫本身必须先证明「能抓到」。

    Requirement: D-108 — 验收标准第 2 条要求「故意塞入一个符号时必须报红」。
    这里用一段合成源码证明检测器有效，避免门禁变成「永远绿」的摆设。
    """

    injected = """
from hris.core.errors import ApiError


def evaluate_workflow_rule(rule, context):
    return bool(rule) and bool(context)
"""

    assert scan_source_for_private_symbols(injected) == {"evaluate_workflow_rule"}


def test_public_source_contains_no_private_engine_symbol() -> None:
    """公开仓源码里不得出现私有实现符号。"""

    violations: list[str] = []
    factory_path = PUBLIC_SOURCE_ROOT / FACTORY_MODULE
    for path in _iter_python_files(PUBLIC_SOURCE_ROOT):
        if path == factory_path:
            # 工厂必须按名引用私有实现类才能装上（唯一的公开例外）；
            # 工厂本身由 `test_factory_module_contains_only_the_resolver` 单独把关。
            continue
        source = _read_source(path)
        found = scan_source_for_private_symbols(source)
        for symbol in sorted(found):
            violations.append(f"{_relative(path)}: 出现私有实现符号 {symbol}")
    assert not violations, (
        "公开仓里不得残留私有引擎实现（Requirement: D-108 / 计划 §7 守则 1）：\n"
        + "\n".join(violations)
    )


def test_public_source_does_not_import_the_private_package() -> None:
    """除工厂外，公开仓源码不得 import 私有包。"""

    violations: list[str] = []
    factory_path = PUBLIC_SOURCE_ROOT / FACTORY_MODULE
    for path in _iter_python_files(PUBLIC_SOURCE_ROOT):
        if path == factory_path:
            continue
        tree = ast.parse(_read_source(path))
        for module in _imported_modules(tree):
            if module == PRIVATE_PACKAGE_NAME or module.startswith(
                f"{PRIVATE_PACKAGE_NAME}."
            ):
                violations.append(f"{_relative(path)}: 引用了私有包 {module}")
    assert not violations, (
        "公开仓源码不得引用私有包（Requirement: D-108）：\n" + "\n".join(violations)
    )


def test_factory_module_contains_only_the_resolver() -> None:
    """工厂文件是唯一例外，因此它必须保持「薄」。

    防止有人把引擎实现直接写进工厂文件，绕过「公开仓不得残留实现」这条纪律。
    """

    path = PUBLIC_SOURCE_ROOT / FACTORY_MODULE
    assert path.exists(), f"缺少流程引擎工厂：{FACTORY_MODULE}"
    tree = ast.parse(_read_source(path))
    top_level: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            top_level.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    top_level.add(target.id)
    unexpected = top_level - FACTORY_ALLOWED_TOP_LEVEL
    assert not unexpected, (
        "流程引擎工厂只允许定义 "
        f"{sorted(FACTORY_ALLOWED_TOP_LEVEL)}，多出：{sorted(unexpected)}"
    )
