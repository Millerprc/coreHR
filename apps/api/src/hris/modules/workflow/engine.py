# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""流程引擎的解析工厂。

Requirement: D-108 — 计划 §7 拆包机制给出的形态：

```python
def resolve_engine() -> WorkflowEngine:
    try:
        from corehr_enterprise.workflow import EnterpriseWorkflowEngine
        return EnterpriseWorkflowEngine(session)
    except ImportError:
        return DemoWorkflowEngine(session)   # 公开壳
```

**这个工厂是公开仓里唯一允许出现私有包名字的地方**（工厂必须按名引用才能装上），
因此架构测试 `test_architecture_no_private_engine.py` 对本文件单独放行，
并额外断言本文件**只定义 `resolve_engine` 一个顶层符号**——
防止有人把引擎实现藏进工厂文件里。

工厂不做任何业务判断：装上私有包就用商业实现，没装就用公开壳。
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from hris.contracts.workflow import (
    WorkflowBusinessObjectHandler,
    WorkflowEngine,
)
from hris.modules.workflow.demo_engine import DemoWorkflowEngine


logger = logging.getLogger(__name__)

#: 私有包的顶层导入名（Wave 3 会转成独立私有仓 + pip 私有源，导入名保持不变）。
ENTERPRISE_PACKAGE_NAME = "corehr_enterprise"


def enterprise_engine_available() -> bool:
    """私有包是否可导入（只做探测，不构造引擎）。"""

    import importlib.util

    try:
        return importlib.util.find_spec(ENTERPRISE_PACKAGE_NAME) is not None
    except (ImportError, ValueError):  # pragma: no cover - 探测失败按未安装处理
        return False


def resolve_engine(
    session: AsyncSession,
    *,
    actor_id: UUID | None = None,
    trace_id: str = "",
    business_object_handler: WorkflowBusinessObjectHandler | None = None,
) -> WorkflowEngine:
    """解析当前生效的流程引擎。

    - 装上私有包 → 返回私有实现（`corehr_enterprise.workflow.EnterpriseWorkflowEngine`）；
    - 没装 → 返回公开壳（`DemoWorkflowEngine`）：读直通数据库，写统一拒绝。

    `actor_id` / `trace_id` / `business_object_handler` 只对私有实现有意义
    （审计与业务对象回写）；公开壳用不到。
    """

    try:
        from corehr_enterprise.workflow import EnterpriseWorkflowEngine
    except ImportError as exc:
        logger.debug(
            "enterprise workflow engine is not installed, falling back to the demo engine: %s",
            type(exc).__name__,
        )
        return DemoWorkflowEngine(session)
    return EnterpriseWorkflowEngine(
        session,
        actor_id=actor_id,
        trace_id=trace_id,
        business_object_handler=business_object_handler,
    )
