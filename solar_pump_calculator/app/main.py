"""
Solar Pump Calculator API — application entry point.

Startup sequence:
    1. Configure logging
    2. Load datasets into repository singletons on app.state
    3. Mount routers
    4. Expose /health endpoint
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .controllers.calculation_controller import router as calc_router
from .repositories.friction_repository import FrictionRepository
from .repositories.pump_repository import PumpRepository
from .utils.exceptions import DataLoadError
from .utils.logger import setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("=== Solar Pump Calculator API starting up ===")

    # Friction data (loads pvc.csv + steel.csv from the friction data directory)
    friction_repo = FrictionRepository(settings.friction_data_dir)
    try:
        friction_repo.load()
    except DataLoadError as exc:
        logger.critical("Failed to load friction dataset: %s", exc)
        raise

    # Pump catalog
    pump_repo = PumpRepository(settings.pump_data_path)
    try:
        pump_repo.load()
    except DataLoadError as exc:
        logger.critical("Failed to load pump catalog: %s", exc)
        raise

    app.state.friction_repo = friction_repo
    app.state.pump_repo = pump_repo

    logger.info(
        "Datasets loaded | friction_tables=%s, pumps=%d, performance_datasets=%d",
        friction_repo.get_supported_materials(),
        pump_repo.pump_count(),
        pump_repo.performance_curve_count(),
    )

    yield  # ← application runs here

    logger.info("=== Solar Pump Calculator API shutting down ===")


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(calc_router, prefix=settings.api_prefix)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get(
        "/health",
        tags=["System"],
        summary="Liveness and readiness probe",
        description=(
            "Returns `healthy` once datasets are loaded. "
            "Reports pump catalog size, friction table coverage, and "
            "performance-curve availability."
        ),
        response_class=JSONResponse,
    )
    async def health_check() -> dict:
        pump_repo     = getattr(app.state, "pump_repo",     None)
        friction_repo = getattr(app.state, "friction_repo", None)

        pump_count      = pump_repo.pump_count()             if pump_repo else 0
        datasets_loaded = pump_repo.performance_curve_count() if pump_repo else 0
        envelope_only   = pump_count - datasets_loaded
        friction_mats   = friction_repo.get_supported_materials() if friction_repo else []

        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "data": {
                "pump_catalog": {
                    "loaded":            pump_repo is not None,
                    "pump_count":        pump_count,
                    "performance_datasets": {
                        "loaded":         datasets_loaded,
                        "envelope_only":  envelope_only,
                        "note": (
                            "Add real datasets to data/pumps/performance/<pump_id>.csv "
                            "to enable curve-based evaluation."
                        ) if envelope_only > 0 else "All pumps have performance datasets.",
                    },
                },
                "friction_tables": {
                    "loaded":    friction_repo is not None,
                    "materials": friction_mats,
                },
            },
        }

    @app.get(
        "/",
        tags=["System"],
        summary="API root — redirect hint",
        include_in_schema=False,
    )
    async def root() -> dict:
        return {
            "message": "Solar Pump Calculator API",
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
