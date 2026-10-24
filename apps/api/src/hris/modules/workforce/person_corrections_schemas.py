# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""人员基础信息「修正」的请求与响应契约。

Requirement: D-095 — 「编辑」与「修正」是两个语义不同的写操作：
「编辑」直接覆盖主档（立即生效）；「修正」不覆盖主档，而是登记一条
带生效日期的字段级版本记录（person_field_versions）。
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# 可修正的基础信息字段，取值与 PersonUpdate 的可编辑字段保持一致。
# 取舍说明：修正只允许落在「基础信息」这一层，雇佣、组织、职务与四类主体
# 关系按 07-人员档案领域规范 §9 走各自的事件与版本链路。
PERSON_CORRECTABLE_FIELD_CODES: tuple[str, ...] = (
    "legal_name",
    "display_name",
    "former_name",
    "gender_code",
    "birth_date",
    "ethnicity_code",
    "nationality_code",
    "country_code",
    "marital_status_code",
    "political_status_code",
)

# 每个可修正字段的取值长度区间（min, max）。
# birth_date 不走长度校验，按 ISO 日期解析。
# 法定姓名与显示姓名不允许置空（主档两列都是 NOT NULL）；其余字段允许清空。
PERSON_FIELD_VALUE_LIMITS: dict[str, tuple[int, int]] = {
    "legal_name": (1, 200),
    "display_name": (1, 200),
    "former_name": (0, 200),
    "gender_code": (0, 30),
    "ethnicity_code": (0, 50),
    "nationality_code": (2, 3),
    "country_code": (2, 3),
    "marital_status_code": (0, 50),
    "political_status_code": (0, 50),
}

# 字段中文名，只用于接口报错文案，不进审计与日志。
PERSON_FIELD_LABELS: dict[str, str] = {
    "legal_name": "法定姓名",
    "display_name": "显示姓名",
    "former_name": "曾用名",
    "gender_code": "性别代码",
    "birth_date": "出生日期",
    "ethnicity_code": "民族代码",
    "nationality_code": "国籍代码",
    "country_code": "国家/地区代码",
    "marital_status_code": "婚姻状况代码",
    "political_status_code": "政治面貌代码",
}


class PersonFieldVersionCreate(BaseModel):
    """创建一条基础信息修正记录。

    Requirement: D-095 — 修正必须带生效日期；不写回主档。
    修正原因是选填，但审计与事件仍会记录操作者与时间。
    """

    field_code: str = Field(min_length=1, max_length=50)
    new_value: str | None = Field(default=None, max_length=200)
    effective_from: date
    change_reason: str | None = Field(default=None, max_length=500)


class PersonFieldVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    field_code: str
    effective_from: date
    effective_to: date | None
    version: int
    new_value: str | None
    change_reason: str | None
    created_by: UUID
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime
