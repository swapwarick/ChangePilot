from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ai_providers, analysis, github, health, jobs, repositories
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_env)

    app = FastAPI(
        title="ChangePilot API",
        version="0.1.0",
        description="Deterministic change impact analysis with AI explanations.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
    app.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
    app.include_router(ai_providers.router, prefix="/ai-providers", tags=["ai providers"])
    app.include_router(github.router, prefix="/github", tags=["github"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    return app


app = create_app()
