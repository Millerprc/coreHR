# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "coreHR API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://corehr:corehr_dev@127.0.0.1:54329/corehr"
    )
    redis_url: str = "redis://127.0.0.1:63800/0"
    business_timezone: str = "Asia/Shanghai"
    personnel_encryption_keys: dict[str, str] = Field(
        default_factory=dict,
        validation_alias="COREHR_PERSONNEL_ENCRYPTION_KEYS",
    )
    personnel_active_key_version: str | None = Field(
        default=None,
        validation_alias="COREHR_PERSONNEL_ACTIVE_KEY_VERSION",
    )
    personnel_search_key: str | None = Field(
        default=None,
        validation_alias="COREHR_PERSONNEL_SEARCH_KEY",
    )
    # Requirement: D-108 — 授权公钥表（轮换期临时覆盖内置表，kid 合并而非整体替换）。
    license_public_keys: str | None = Field(
        default=None,
        validation_alias="COREHR_LICENSE_PUBLIC_KEYS",
    )
    # Requirement: D-108 — 可选在线通道地址；未配置即纯离线，不发起任何外部请求。
    license_server_url: str | None = Field(
        default=None,
        validation_alias="COREHR_LICENSE_SERVER_URL",
    )
    # Requirement: D-108 — 只读演示模式的拦截总开关。
    # 默认关闭：关闭时路由级依赖只放行（内部开发 / 迁移未跑的逃生门），
    # 生产部署置 true 后未授权写操作统一 403 LICENSE_REQUIRED。
    license_enforce: bool = Field(
        default=False,
        validation_alias="COREHR_LICENSE_ENFORCE",
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
