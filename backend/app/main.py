import asyncio
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    ai_providers,
    analysis,
    auth,
    export,
    github,
    health,
    jobs,
    local,
    policies,
    repositories,
)
from app.core.config import get_settings
from app.core.logging import configure_logging

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


from contextlib import asynccontextmanager

from app.database.session import _init_db_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_db_engine()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_env)

    app = FastAPI(
        title="ChangePilot API",
        version="0.1.0",
        description="Deterministic change impact analysis with AI explanations.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https://[\w-]+\.onrender\.com",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "ChangePilot API",
            "status": "running",
            "docs": "/docs",
            "health": "/health",
        }

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
    app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
    app.include_router(export.router, prefix="/analysis", tags=["export"])
    app.include_router(ai_providers.router, prefix="/ai-providers", tags=["ai providers"])
    app.include_router(github.router, prefix="/github", tags=["github"])
    app.include_router(local.router, prefix="/local", tags=["local"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(policies.router, prefix="/risk-policies", tags=["risk policies"])
    return app


app = create_app()
