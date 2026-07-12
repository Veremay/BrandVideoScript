from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    coordinator,
    health,
    llm,
    modification_schemes,
    negotiation,
    projects,
    research,
    share,
    users,
)
from app.core.config import get_cors_origins, get_settings
from app.db.mongo import close_mongo, connect_mongo, get_database
from app.middleware.request_logging import RequestLoggingMiddleware
from app.repositories.activity_logs import ensure_activity_log_indexes
from app.services.app_log import setup_app_logging
from app.services.pipeline_log import setup_pipeline_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_pipeline_logging()
    setup_app_logging()
    await connect_mongo()
    await ensure_activity_log_indexes(get_database())
    yield
    await close_mongo()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(settings),
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(coordinator.router, prefix=settings.api_prefix)
app.include_router(coordinator.graph_router, prefix=settings.api_prefix)
app.include_router(modification_schemes.router, prefix=settings.api_prefix)
app.include_router(negotiation.router, prefix=settings.api_prefix)
app.include_router(llm.router, prefix=settings.api_prefix)
app.include_router(research.router, prefix=settings.api_prefix)
app.include_router(share.router, prefix=settings.api_prefix)

