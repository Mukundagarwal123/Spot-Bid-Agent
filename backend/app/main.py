from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging
from app.core.settings import settings

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from app.db.base import create_tables

    logger.info("startup", env=settings.app_env, db=settings.database_url)
    create_tables()
    yield
    logger.info("shutdown")


app = FastAPI(title="Spot Bid Agent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.portal.router import router as portal_router  # noqa: E402

app.include_router(portal_router)


@app.get("/health")
async def health() -> dict[str, str]:
    logger.info("health_check", app_env=settings.app_env)
    return {"status": "ok"}
