"""
NREL Solar Resource Integration Service

Fetches annual average GHI (kWh/m²/day) from the NREL Solar Resource API
and converts it to a solar zone + recommended array coefficient via
SolarZoneRegistry.

The returned NRELSolarResult carries:
    - ghi          : raw annual average GHI value
    - solar_zone   : zone 1–6 per the spec table
    - coefficient  : recommended array oversizing factor for that zone
    - peak_sun_hours: alias for ghi (same numeric value, different label)
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from ..config import Settings
from ..services.solar_service import SolarZoneRegistry

logger = logging.getLogger(__name__)


@dataclass
class NRELSolarResult:
    """Result returned by NRELService.get_solar_resource()."""
    ghi: float               # annual average GHI (kWh/m²/day)
    solar_zone: int          # zone 1–6
    coefficient: float       # recommended array oversizing coefficient
    peak_sun_hours: float    # same as ghi — kept for downstream compatibility
    source: str              # "ghi" or "dni_fallback"


class NRELService:
    """
    Service for fetching solar resource data from NREL.

    Primary method: ``get_solar_resource(lat, lon)`` — returns an
    ``NRELSolarResult`` with GHI, zone, and coefficient.

    The legacy ``get_peak_sun_hours`` method is preserved for backward compat.
    """

    BASE_URL = "https://developer.nlr.gov/api/solar/solar_resource/v1.json"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.nrel_api_key

    async def get_solar_resource(
        self,
        latitude: float,
        longitude: float,
    ) -> Optional[NRELSolarResult]:
        """
        Fetch NREL GHI, classify into a solar zone, and return the
        recommended array coefficient.

        Args:
            latitude:  Site latitude.
            longitude: Site longitude.

        Returns:
            NRELSolarResult or None if the request fails / key not configured.
        """
        if not self.api_key:
            logger.warning("NREL lookup skipped — NREL_API_KEY is not configured.")
            return None

        params = {"api_key": self.api_key, "lat": latitude, "lon": longitude}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.BASE_URL, params=params)

            response.raise_for_status()
            data = response.json()
            outputs = data.get("outputs", {})

            # Prefer GHI; fall back to DNI
            ghi_val = outputs.get("avg_ghi", {}).get("annual")
            source  = "ghi"
            if ghi_val is None:
                ghi_val = outputs.get("avg_dni", {}).get("annual")
                source  = "dni_fallback"

            if ghi_val is None:
                logger.warning(
                    "NREL lookup failed — annual GHI/DNI not found in response."
                )
                return None

            ghi = float(ghi_val)
            zone_id, coefficient = SolarZoneRegistry.zone_from_ghi(ghi)

            logger.info(
                "NREL | lat=%.4f lon=%.4f | GHI=%.2f kWh/m²/day | "
                "Zone %d | coeff=%.2f [%s]",
                latitude, longitude, ghi, zone_id, coefficient, source,
            )

            return NRELSolarResult(
                ghi=round(ghi, 3),
                solar_zone=zone_id,
                coefficient=coefficient,
                peak_sun_hours=round(ghi, 3),
                source=source,
            )

        except httpx.TimeoutException:
            logger.warning("NREL lookup failed — request timed out.")
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "NREL lookup failed — HTTP %d: %s",
                exc.response.status_code, exc.response.text,
            )
            return None
        except Exception as exc:
            logger.warning("NREL lookup failed — unexpected error: %s", exc)
            return None

    async def get_peak_sun_hours(
        self,
        latitude: float,
        longitude: float,
    ) -> Optional[float]:
        """Backward-compatible wrapper — returns GHI value as peak_sun_hours."""
        result = await self.get_solar_resource(latitude, longitude)
        return result.peak_sun_hours if result is not None else None
