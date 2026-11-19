"""FastAPI Application Entrypoint for CineForge AI Studio."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.core.config import get_settings
from server.core.database import check_database_health
from server.routers.context import router as context_router
from server.routers.pipeline import router as pipeline_router
from server.routers.projects import router as projects_router
from server.routers.ws import router as ws_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle events."""
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise AI Video Production Engine combining AI-Content-Studio & ContentMachine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(context_router)
app.include_router(projects_router)
app.include_router(pipeline_router)
app.include_router(ws_router)


@app.get("/health")
@app.get("/api/health")
async def health_check() -> dict:
    """System health check endpoint verifying database connectivity."""
    db_healthy = False
    try:
        db_healthy = await check_database_health()
    except Exception:
        db_healthy = False

    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "unreachable",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
    }
