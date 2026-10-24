# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""受控错误码工具。

Requirement: D-110 — 失败原因必须能落库、能排查，又不能把个人信息带进记录。
因此所有持久化的失败原因都先收敛成「只含 ``[a-z0-9_.:-]``、最长 200 字符」的受控错误码，
异常原文一律不进库、不进日志。
"""

import re


# Requirement: D-110 — 允许字符集刻意保守：只留下错误码需要的标识符字符，
# 其余（含空格、斜杠、括号、中文）一律替换成下划线。
_SAFE_ERROR_CODE = re.compile(r"[^a-z0-9_.:-]+")

MAX_ERROR_CODE_LENGTH = 200


def sanitize_error_code(value: str | None) -> str | None:
    """把错误信息收敛成不含个人信息的受控错误码。

    ``None`` 原样返回（调用方据此表达「没有错误」）；
    空串或收敛后为空时返回 ``"unknown_error"``。
    """

    if value is None:
        return None
    cleaned = _SAFE_ERROR_CODE.sub("_", value.strip().lower())[:MAX_ERROR_CODE_LENGTH]
    return cleaned or "unknown_error"
