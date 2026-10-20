"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aura.api import agents, health, knowledge, mcp, onboarding, pipeline, projects, requirements, runs, skills, ws
from aura.api import settings as settings_api
from aura.config import get_settings
from aura.db import SessionLocal, engine
from aura.migrate import ensure_current_revision
from aura.services.mcp_service import cleanup_runtime_configs
from aura.services.seed import (
    apply_knowledge_defaults,
    reconcile_stale_runs,
    seed_default_agents,
    seed_default_mcp_servers,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with SessionLocal() as session:
        await ensure_current_revision(session)
        cleanup_runtime_configs()
        await seed_default_mcp_servers(session)
        await seed_default_agents(session)
        await apply_knowledge_defaults(session)
        await reconcile_stale_runs(session)
    try:
        yield
    finally:
        await engine.dispose()


def create_app(startup: bool = True) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Aura",
        version="0.1.0",
        lifespan=lifespan if startup else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(onboarding.router)
    app.include_router(knowledge.router)
    app.include_router(settings_api.router)
    app.include_router(projects.router)
    app.include_router(requirements.project_router)
    app.include_router(requirements.router)
    app.include_router(runs.router)
    app.include_router(skills.router)
    app.include_router(agents.router)
    app.include_router(mcp.router)
    app.include_router(pipeline.router)
    app.include_router(ws.router)
    return app


app = create_app()
