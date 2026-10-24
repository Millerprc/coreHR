# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hris import __version__
from hris.api.business_router import business_router
from hris.core.config import get_settings
from hris.core.errors import register_exception_handlers
from hris.core.middleware import TraceIdMiddleware
from hris.modules.messaging.api import router as messaging_router
from hris.modules.platform.import_task_api import router as import_task_router
from hris.modules.platform.task_api import router as task_router


def create_business_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} Business API",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Trace-ID"],
    )
    register_exception_handlers(app)
    app.include_router(business_router)
    # Requirement: D-100 — 消息引擎是平台内核基础服务，路由独立于业务域注册，
    # 业务模块只通过消息引擎接口投递，不直接依赖本路由。
    app.include_router(messaging_router)
    # Requirement: D-110 — 后台任务框架是平台内核能力，路由独立于业务域注册：
    # 任务管理与「异步提交导入」都由后台任务框架承担，
    # 不挂在业务域路由上，业务模块只通过任务队列接口投递长任务。
    app.include_router(task_router)
    app.include_router(import_task_router)
    return app


app = create_business_app()
