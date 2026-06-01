"""
FastAPI dependency injection container.

All service and repository instances are resolved here.
Repositories are stored on app.state (singletons loaded at startup);
services are lightweight and constructed per-request via Depends.
"""

from fastapi import Depends, Request

from .config import Settings, get_settings
from .repositories.friction_repository import FrictionRepository
from .repositories.pump_repository import PumpRepository
from .services.friction_service import FrictionService
from .services.pump_eval_service import PumpEvalService
from .services.pump_filter_service import PumpFilterService
from .services.ranking_service import RankingService
from .services.solar_service import SolarService
from .services.tdh_service import TDHService
from .services.wire_sizing_service import WireSizingService


# ── Repository providers (singletons via app.state) ───────────────────────────

def get_friction_repo(request: Request) -> FrictionRepository:
    return request.app.state.friction_repo


def get_pump_repo(request: Request) -> PumpRepository:
    return request.app.state.pump_repo


# ── Service providers (constructed per request) ───────────────────────────────

def get_friction_service(
    friction_repo: FrictionRepository = Depends(get_friction_repo),
) -> FrictionService:
    return FrictionService(friction_repo)


def get_tdh_service(
    friction_service: FrictionService = Depends(get_friction_service),
) -> TDHService:
    return TDHService(friction_service)


def get_solar_service(
    settings: Settings = Depends(get_settings),
) -> SolarService:
    return SolarService(settings)


def get_pump_eval_service(
    pump_repo: PumpRepository = Depends(get_pump_repo),
) -> PumpEvalService:
    return PumpEvalService(pump_repo)


def get_ranking_service(
    solar_service: SolarService = Depends(get_solar_service),
) -> RankingService:
    return RankingService(solar_service)

def get_pump_filter_service() -> PumpFilterService:
    return PumpFilterService()


def get_wire_sizing_service() -> WireSizingService:
    return WireSizingService()


def get_nrel_service(
    settings: Settings = Depends(get_settings),
) -> "NRELService":
    from .services.nrel_service import NRELService
    return NRELService(settings)
