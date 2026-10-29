from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging_middleware import StructuredLoggingMiddleware
from app.core.tracing import configure_tracing, shutdown_tracing

settings = get_settings()


@asynccontextmanager
async def lifespan(app):
    configure_tracing(settings)
    try:
        yield
    finally:
        shutdown_tracing()


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

app.add_middleware(StructuredLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_router, prefix=settings.api_v1_prefix)
