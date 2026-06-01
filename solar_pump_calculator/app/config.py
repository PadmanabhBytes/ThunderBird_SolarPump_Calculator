from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ─────────────────────────────────────────────────────────
    app_name: str = "Solar Pump Calculator API"
    app_version: str = "0.1.0"
    app_description: str = (
        "Engineering-grade backend for solar pump system sizing and recommendation."
    )
    debug: bool = False
    log_level: str = "INFO"

    # ── API ──────────────────────────────────────────────────────────────────
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["*"]
    nrel_api_key: str | None = None

    # ── Data paths ───────────────────────────────────────────────────────────
    data_dir: Path = Path("data")
    friction_data_dir: Path = Path("data/friction")   # contains pvc.csv, steel.csv
    pump_data_path: Path = Path("data/pumps/pump_catalog.csv")

    # ── Future database (placeholder) ────────────────────────────────────────
    database_url: str = ""
    use_database: bool = False

    # ── Physical constants ───────────────────────────────────────────────────
    gravity: float = 9.81          # m/s²
    water_density: float = 1000.0  # kg/m³

    # ── Calculation defaults ─────────────────────────────────────────────────
    default_safety_factor: float = 1.15
    default_minor_loss_factor: float = 0.10
    default_pump_efficiency: float = 0.45
    default_system_losses: float = 0.15       # wiring, controller, etc. (informational)
    max_pipe_velocity_fps: float = 10.0        # advisory threshold (ft/s)
    default_solar_coefficient: float = 1.25   # array oversizing factor for production sizing
    deadhead_minimum_irradiance: float = 0.35 # minimum panel-output fraction for deadhead check


@lru_cache
def get_settings() -> Settings:
    return Settings()
