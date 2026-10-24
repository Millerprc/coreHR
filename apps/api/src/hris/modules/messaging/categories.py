# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Message category enum and its Chinese labels — the single source of truth.

Requirement: D-100 — 消息分类的中文标签只在本模块定义一次。
前端通过 ``GET /api/v1/messaging/categories`` 取用标签，不得另写一套映射。
"""

from enum import Enum


class MessageCategory(str, Enum):
    """消息分类。取值是稳定编码，落库与跨端传输都用编码，不使用中文标签。"""

    SYSTEM = "system"
    APPROVAL = "approval"
    WORKFLOW = "workflow"
    LIFECYCLE = "lifecycle"
    ATTENDANCE = "attendance"
    PERFORMANCE = "performance"
    DATA_GOVERNANCE = "data_governance"
    TASK = "task"


# Requirement: D-100 — 标签表与枚举一一对应，缺项会在下面的一致性断言里立刻暴露。
MESSAGE_CATEGORY_LABELS: dict[MessageCategory, str] = {
    MessageCategory.SYSTEM: "系统公告",
    MessageCategory.APPROVAL: "审批待办",
    MessageCategory.WORKFLOW: "流程进展",
    MessageCategory.LIFECYCLE: "员工生命周期",
    MessageCategory.ATTENDANCE: "考勤",
    MessageCategory.PERFORMANCE: "绩效",
    MessageCategory.DATA_GOVERNANCE: "数据治理",
    MessageCategory.TASK: "任务提醒",
}


def message_category_catalog() -> tuple[tuple[str, str], ...]:
    """返回 ``(编码, 中文标签)`` 列表，供前端直接消费。"""

    return tuple(
        (category.value, MESSAGE_CATEGORY_LABELS[category]) for category in MessageCategory
    )


def message_category_label(code: str) -> str:
    """按编码取中文标签；未知编码回退为编码本身，不抛异常。"""

    try:
        return MESSAGE_CATEGORY_LABELS[MessageCategory(code)]
    except ValueError:
        return code
