# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hris import __version__
from hris.api.router import api_router
from hris.core.config import get_settings
from hris.core.errors import register_exception_handlers
from hris.core.middleware import TraceIdMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
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
    app.include_router(api_router)
    return app


app = create_app()

