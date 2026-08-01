from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hris import __version__
from hris.api.business_router import business_router
from hris.core.config import get_settings
from hris.core.errors import register_exception_handlers
from hris.core.middleware import TraceIdMiddleware


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
    return app


app = create_business_app()
