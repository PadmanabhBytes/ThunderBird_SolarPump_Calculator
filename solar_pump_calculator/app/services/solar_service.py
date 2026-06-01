"""
Solar array sizing service — production + deadhead dual-path sizing.

Sizing paths
------------
    Production  — continuous pumping at the design operating point:
        production_required_watts = operating_watts × solar_coefficient
        production_panels         = ⌈production_required_watts / panel_wattage⌉

    Deadhead    — low-irradiance start (early morning / overcast):
        deadhead_required_watts   = deadhead_watts / 0.35
        deadhead_panels           = ⌈deadhead_required_watts / panel_wattage⌉

    Final:
        final_panels = max(production_panels, deadhead_panels)

Solar Zone Classification
--------------------------
    NREL returns avg GHI (kWh/m²/day).  That value maps to a zone (1–6)
    which carries a recommended array oversizing coefficient:

        Zone 1  1.0–1.99  →  2.40×
        Zone 2  2.0–2.99  →  2.00×
        Zone 3  3.0–3.99  →  1.75×
        Zone 4  4.0–4.99  →  1.55×
        Zone 5  5.0–5.99  →  1.40×
        Zone 6  6.0+      →  1.25×

    Call ``SolarZoneRegistry.coefficient_from_ghi(ghi)`` to get the
    coefficient directly from a raw NREL GHI value.
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

from ..config import Settings
from ..models.calculation_response import SolarSizing
from ..utils.exceptions import CalculationError

logger = logging.getLogger(__name__)

_DEADHEAD_IRRADIANCE_FRACTION: float = 0.35   # minimum panel output fraction for start sizing


# ── Solar zone coefficient mapping ────────────────────────────────────────────

@dataclass(frozen=True)
class SolarZoneCoefficient:
    """One row of the zone table — zone id, GHI range, and recommended coefficient."""
    zone_id:     int
    ghi_min:     float   # inclusive lower bound (kWh/m²/day)
    ghi_max:     float   # exclusive upper bound (kWh/m²/day); use float('inf') for last zone
    coefficient: float
    description: str = ""


# Zone table — mirrors the spec exactly
_ZONE_TABLE: list[SolarZoneCoefficient] = [
    SolarZoneCoefficient(1, 1.0,          2.0,          2.40, "Very low solar resource"),
    SolarZoneCoefficient(2, 2.0,          3.0,          2.00, "Low solar resource"),
    SolarZoneCoefficient(3, 3.0,          4.0,          1.75, "Moderate solar resource"),
    SolarZoneCoefficient(4, 4.0,          5.0,          1.55, "Good solar resource"),
    SolarZoneCoefficient(5, 5.0,          6.0,          1.40, "High solar resource"),
    SolarZoneCoefficient(6, 6.0, float("inf"),          1.25, "Excellent solar resource"),
]


class SolarZoneRegistry:
    """
    Maps NREL GHI (kWh/m²/day) → solar zone → recommended array coefficient.

    Usage
    -----
        zone, coeff = SolarZoneRegistry.zone_from_ghi(4.7)
        # zone=4, coeff=1.55
    """

    @staticmethod
    def zone_from_ghi(ghi: float) -> tuple[int, float]:
        """
        Return (zone_id, coefficient) for the given GHI value.

        Falls back to Zone 1 (most conservative) for GHI < 1.0,
        and Zone 6 for GHI ≥ 6.0.

        Args:
            ghi: Annual average GHI from NREL (kWh/m²/day).

        Returns:
            (zone_id, coefficient) tuple.
        """
        for entry in _ZONE_TABLE:
            if entry.ghi_min <= ghi < entry.ghi_max:
                logger.debug(
                    "Solar zone: GHI=%.2f kWh/m²/day → Zone %d (coeff=%.2f)",
                    ghi, entry.zone_id, entry.coefficient,
                )
                return entry.zone_id, entry.coefficient

        # Below Zone 1 minimum — use most conservative coefficient
        if ghi < _ZONE_TABLE[0].ghi_min:
            logger.warning(
                "GHI %.2f is below Zone 1 minimum (%.1f). Using Zone 1 coefficient %.2f.",
                ghi, _ZONE_TABLE[0].ghi_min, _ZONE_TABLE[0].coefficient,
            )
            return _ZONE_TABLE[0].zone_id, _ZONE_TABLE[0].coefficient

        # Should not be reached, but safeguard with Zone 6
        return _ZONE_TABLE[-1].zone_id, _ZONE_TABLE[-1].coefficient

    @staticmethod
    def coefficient_from_ghi(ghi: float) -> float:
        """Convenience wrapper — return only the coefficient."""
        _, coeff = SolarZoneRegistry.zone_from_ghi(ghi)
        return coeff


# ── Service ───────────────────────────────────────────────────────────────────

class SolarService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def calculate(
        self,
        operating_watts:    float,
        deadhead_watts:     float,
        solar_coefficient:  float,
        panel_wattage_w:    float,
    ) -> SolarSizing:
        """
        Size the solar array from pump operating data.

        Args:
            operating_watts:    Pump power at the design operating point (W).
                                Sourced from pump performance curve evaluation,
                                or from a hydraulic estimate when no curve exists.
            deadhead_watts:     Pump power at shutoff / deadhead condition (W).
                                Use ``operating_watts`` when actual shutoff power
                                is unknown (no curve available).
            solar_coefficient:  Array oversizing factor (≥ 1.0).
            panel_wattage_w:    Nameplate wattage of each panel (W).

        Returns:
            :class:`SolarSizing` with both sizing paths and the governing result.

        Raises:
            CalculationError: If any input is outside its valid range.
        """
        if operating_watts <= 0:
            raise CalculationError(f"operating_watts must be > 0; got {operating_watts}")
        if deadhead_watts <= 0:
            raise CalculationError(f"deadhead_watts must be > 0; got {deadhead_watts}")
        if solar_coefficient < 1.0:
            raise CalculationError(f"solar_coefficient must be ≥ 1.0; got {solar_coefficient}")
        if panel_wattage_w <= 0:
            raise CalculationError(f"panel_wattage_w must be > 0; got {panel_wattage_w}")

        # ── Production path ───────────────────────────────────────────────────
        production_required_w = round(operating_watts * solar_coefficient, 2)
        production_panels     = math.ceil(production_required_w / panel_wattage_w)

        # ── Deadhead path ─────────────────────────────────────────────────────
        deadhead_required_w = round(deadhead_watts / _DEADHEAD_IRRADIANCE_FRACTION, 2)
        deadhead_panels     = math.ceil(deadhead_required_w / panel_wattage_w)

        # ── Governing result ──────────────────────────────────────────────────
        final_panels   = max(production_panels, deadhead_panels)
        governing_path = "deadhead" if deadhead_panels > production_panels else "production"

        logger.info(
            "Solar sizing | op=%.0f W, dh=%.0f W, coeff=%.2f → "
            "production=%d panels (%.0f W) | deadhead=%d panels (%.0f W) | "
            "final=%d panels [%s]",
            operating_watts, deadhead_watts, solar_coefficient,
            production_panels, production_required_w,
            deadhead_panels, deadhead_required_w,
            final_panels, governing_path,
        )

        return SolarSizing(
            operating_watts=round(operating_watts, 2),
            deadhead_watts=round(deadhead_watts, 2),
            solar_coefficient=round(solar_coefficient, 4),
            panel_wattage_w=panel_wattage_w,
            production_required_watts=production_required_w,
            production_panels=production_panels,
            deadhead_required_watts=deadhead_required_w,
            deadhead_panels=deadhead_panels,
            final_panels=final_panels,
            governing_path=governing_path,
        )
