# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""私有包可用性探测（测试用）。

Requirement: D-108 — Wave 2a 拆包后，流程的**写路径**依赖私有包
`corehr_enterprise`：公开仓（没装私有包）下 Demo 引擎统一拒绝写操作
（403 / `code=LICENSE_REQUIRED`）。

因此：

- 依赖流程写路径的**既有用例**按「私有包是否可导入」**跳过**，
  而不是把断言改弱（把「写成功」改成「写返回 403」骗过 CI）；
- **新增**的公开仓模式用例反向断言「写返回 LICENSE_REQUIRED、读仍返回真实数据」，
  私有包装上后自动跳过。

这与计划 §7 守则 4 一致：公开仓的 CI 不依赖私有源，只跑壳的测试。
"""

from __future__ import annotations

import importlib.util

import pytest


#: 私有包顶层导入名。
ENTERPRISE_PACKAGE_NAME = "corehr_enterprise"


def enterprise_available() -> bool:
    """私有包是否可导入（只做探测，不构造引擎）。"""

    try:
        return importlib.util.find_spec(ENTERPRISE_PACKAGE_NAME) is not None
    except (ImportError, ValueError):  # pragma: no cover - 探测失败按未安装处理
        return False


#: 当前测试进程里私有包是否可用。
HAS_ENTERPRISE = enterprise_available()

#: 需要私有包才能跑的用例（流程写路径）。
requires_enterprise = pytest.mark.skipif(
    not HAS_ENTERPRISE,
    reason=(
        "需要私有包 corehr_enterprise：公开仓模式下流程写路径由 Demo 引擎"
        "统一拒绝（Requirement: D-108 / Wave 2a）"
    ),
)

#: 只在公开仓模式（没装私有包）下跑的用例。
requires_public_only = pytest.mark.skipif(
    HAS_ENTERPRISE,
    reason="私有包装上后流程写路径可用，本用例只验证公开仓模式",
)
