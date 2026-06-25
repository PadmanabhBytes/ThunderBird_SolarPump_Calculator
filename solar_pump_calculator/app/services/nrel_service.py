"""
NREL Solar Resource Integration Service

Fetches GHI (kWh/m²/day) from the NREL Solar Resource API — annual or
seasonal average depending on the operating_window — and converts it to a
solar zone + recommended array coefficient via SolarZoneRegistry.

The returned NRELSolarResult carries:
    - ghi            : effective GHI for the selected season
    - solar_zone     : zone 1–6 per the spec table
    - coefficient    : recommended array oversizing factor for that zone
    - peak_sun_hours : alias for ghi (same numeric value, different label)
    - operating_window: which season was used ("year_round", "summer", "winter")
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

import httpx

from ..config import Settings
from ..services.solar_service import SolarZoneRegistry

logger = logging.getLogger(__name__)

_SUMMER_MONTHS = ("apr", "may", "jun", "jul", "aug", "sep")
_WINTER_MONTHS = ("oct", "nov", "dec", "jan", "feb", "mar")


def _seasonal_average(monthly: Dict[str, float], operating_window: str) -> Optional[float]:
    """Return the average GHI for the selected season, or None to use annual."""
    if operating_window == "summer":
        keys = _SUMMER_MONTHS
    elif operating_window == "winter":
        keys = _WINTER_MONTHS
    else:
        return None  # caller uses annual value

    vals = [monthly[k] for k in keys if k in monthly and monthly[k] is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


@dataclass
class NRELSolarResult:
    """Result returned by NRELService.get_solar_resource()."""
    ghi: float               # effective GHI for the chosen season (kWh/m²/day)
    solar_zone: int          # zone 1–6
    coefficient: float       # recommended array oversizing coefficient
    peak_sun_hours: float    # same as ghi — kept for downstream compatibility
    source: str              # "ghi", "ghi_seasonal", or "dni_fallback"
    operating_window: str = field(default="year_round")


class NRELService:
    """
    Service for fetching solar resource data from NREL.

    Primary method: ``get_solar_resource(lat, lon, operating_window)`` — returns
    an ``NRELSolarResult`` with GHI, zone, and coefficient for the requested season.

    The legacy ``get_peak_sun_hours`` method is preserved for backward compat.
    """

    BASE_URL = "https://developer.nrel.gov/api/solar/solar_resource/v1.json"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.nrel_api_key

    async def get_solar_resource(
        self,
        latitude: float,
        longitude: float,
        operating_window: str = "year_round",
    ) -> Optional[NRELSolarResult]:
        """
        Fetch NREL GHI, classify into a solar zone, and return the
        recommended array coefficient.

        Args:
            latitude:         Site latitude.
            longitude:        Site longitude.
            operating_window: "year_round" | "summer" | "winter"

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

            ghi_block = outputs.get("avg_ghi", {})
            source = "ghi"

            # Try seasonal average first when requested
            monthly = ghi_block.get("monthly", {})
            seasonal = _seasonal_average(monthly, operating_window) if monthly else None

            if seasonal is not None:
                ghi = seasonal
                source = "ghi_seasonal"
            else:
                # Fall back to annual GHI, then annual DNI
                ghi_val = ghi_block.get("annual")
                if ghi_val is None:
                    ghi_val = outputs.get("avg_dni", {}).get("annual")
                    source = "dni_fallback"
                if ghi_val is None:
                    logger.warning("NREL lookup failed — annual GHI/DNI not found in response.")
                    return None
                ghi = float(ghi_val)

            zone_id, coefficient = SolarZoneRegistry.zone_from_ghi(ghi)

            logger.info(
                "NREL | lat=%.4f lon=%.4f | window=%s | GHI=%.2f kWh/m²/day | "
                "Zone %d | coeff=%.2f [%s]",
                latitude, longitude, operating_window, ghi, zone_id, coefficient, source,
            )

            return NRELSolarResult(
                ghi=round(ghi, 3),
                solar_zone=zone_id,
                coefficient=coefficient,
                peak_sun_hours=round(ghi, 3),
                source=source,
                operating_window=operating_window,
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
