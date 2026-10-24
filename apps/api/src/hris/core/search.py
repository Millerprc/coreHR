# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""搜索关键词的 SQL LIKE 转义。

Requirement: D-112 — 搜索关键词是用户原文，不是通配符。

背景：仓库里多处用 ``ilike(f"%{search}%")`` 做「工号 / 姓名包含」匹配，
直接把用户输入拼进模式串。``%`` 与 ``_`` 在 ``LIKE`` / ``ILIKE`` 里是通配符，
于是搜索 ``%`` 会返回**全部**数据，搜索 ``a_b`` 会命中 ``axb``——
用户搜一个含下划线的名字会拿到一堆不相干的结果。

这里提供统一的转义：**先转义反斜杠，再转义 ``%`` 与 ``_``**，
最后由调用方给 ``ilike(...)`` 传 ``escape="\\"`` 让 PostgreSQL 按字面量比较。
顺序不能反：先转义 ``\\`` 才能保证后加的反斜杠不被二次转义。

返回值是**字面量**匹配，不提供「用户可主动使用通配符」的能力——
那属于产品语义，若将来要支持，需要单独决策并单独走一遍审计。
"""

from __future__ import annotations


#: LIKE 模式里的通配符与转义符。
_LIKE_SPECIALS = ("\\", "%", "_")


def escape_like(term: str) -> str:
    """把用户输入里的 LIKE 通配符转义成字面量。

    >>> escape_like("a%b")
    'a\\\\%b'
    """

    escaped = term
    for char in _LIKE_SPECIALS:
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def like_pattern(term: str) -> str:
    """生成「包含」的 ILIKE 模式串（已转义）。

    用法::

        Person.display_name.ilike(like_pattern(search), escape="\\\\")
    """

    return f"%{escape_like(term.strip())}%"
