import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, health, llm, projects, users
from app.core.config import get_settings
from app.db.mongo import close_mongo, connect_mongo


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_mongo()
    yield
    await close_mongo()


logging.basicConfig(level=logging.INFO)
logging.getLogger("brandvideo.trace").setLevel(logging.INFO)

settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(llm.router, prefix=settings.api_prefix)
app.include_router(agents.router, prefix=settings.api_prefix)
