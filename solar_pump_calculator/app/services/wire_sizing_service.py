"""
Wire sizing service — recommends AWG wire gauge for a solar-to-pump run.

Method
------
Wire gauge is selected to keep voltage drop ≤ 3% of the system voltage
over the one-way wire distance, at the operating current.

Formula
-------
    voltage_drop_V  = 2 × I × R_per_ft × distance_ft
                    = 2 × I × (resistance_per_1000ft / 1000) × distance_ft

    max_drop_V      = system_voltage × max_drop_fraction   (default 3%)

    Required wire must satisfy: voltage_drop_V ≤ max_drop_V

Wire resistance data
--------------------
NEC Table 9 (copper, 75 °C rating) — DC resistance per 1,000 ft (Ω/kft).
Only standard AWG sizes from 14 AWG down to 2/0 AWG are included here;
extend the table for larger conductors if needed.
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# NEC Table 9 — copper conductor DC resistance (Ω per 1,000 ft at 75°C)
# Listed from smallest (highest resistance) to largest (lowest resistance)
_AWG_RESISTANCE: list[tuple[str, float]] = [
    ("14 AWG", 3.140),
    ("12 AWG", 1.980),
    ("10 AWG", 1.240),
    ("8 AWG",  0.778),
    ("6 AWG",  0.491),
    ("4 AWG",  0.308),
    ("3 AWG",  0.245),
    ("2 AWG",  0.194),
    ("1 AWG",  0.154),
    ("1/0 AWG", 0.122),
    ("2/0 AWG", 0.0967),
    ("3/0 AWG", 0.0766),
    ("4/0 AWG", 0.0608),
]

_DEFAULT_MAX_DROP_FRACTION: float = 0.03   # 3% voltage drop limit


@dataclass
class WireSizingResult:
    """Result of wire gauge selection."""
    recommended_awg: str
    wire_distance_ft: float
    operating_watts: float
    system_voltage: float
    operating_current_a: float
    voltage_drop_v: float
    voltage_drop_percent: float
    resistance_per_1000ft: float
    note: str = ""


class WireSizingService:
    """
    Recommends copper wire gauge (AWG) for a solar pump installation.

    Sizing criterion: voltage drop ≤ 3% over the one-way wire run at
    operating current (round-trip = 2× one-way distance in the formula).
    """

    def calculate(
        self,
        wire_distance_ft: float,
        operating_watts:  float,
        system_voltage:   float = 48.0,
        max_drop_fraction: float = _DEFAULT_MAX_DROP_FRACTION,
    ) -> WireSizingResult:
        """
        Select the minimum AWG wire that keeps voltage drop within limit.

        Args:
            wire_distance_ft:  One-way distance from array to pump (ft).
            operating_watts:   Pump input power at operating point (W).
            system_voltage:    Nominal system voltage (V). Default 48 V.
            max_drop_fraction: Maximum allowable voltage drop as a fraction
                               of system voltage. Default 0.03 (3%).

        Returns:
            WireSizingResult with recommended AWG and supporting data.
        """
        if wire_distance_ft <= 0:
            raise ValueError(f"wire_distance_ft must be > 0; got {wire_distance_ft}")
        if operating_watts <= 0:
            raise ValueError(f"operating_watts must be > 0; got {operating_watts}")
        if system_voltage <= 0:
            raise ValueError(f"system_voltage must be > 0; got {system_voltage}")

        operating_current_a = operating_watts / system_voltage
        max_drop_v          = system_voltage * max_drop_fraction

        selected_awg:   str   = _AWG_RESISTANCE[-1][0]   # start with largest
        selected_r:     float = _AWG_RESISTANCE[-1][1]

        for awg_label, r_per_kft in _AWG_RESISTANCE:
            r_per_ft     = r_per_kft / 1000.0
            # Round-trip (×2) voltage drop
            drop_v       = 2.0 * operating_current_a * r_per_ft * wire_distance_ft
            if drop_v <= max_drop_v:
                selected_awg = awg_label
                selected_r   = r_per_kft
                break

        # Compute actual drop for the selected gauge
        actual_drop_v   = 2.0 * operating_current_a * (selected_r / 1000.0) * wire_distance_ft
        actual_drop_pct = (actual_drop_v / system_voltage) * 100.0

        note = ""
        if actual_drop_pct > max_drop_fraction * 100:
            note = (
                f"Voltage drop ({actual_drop_pct:.1f}%) exceeds the {max_drop_fraction*100:.0f}% "
                "limit even at 4/0 AWG. Consider reducing wire run length or increasing "
                "system voltage."
            )

        logger.info(
            "Wire sizing: %.0f ft @ %.0f W / %.0f V → %s "
            "(I=%.2f A, drop=%.2f V / %.1f%%)",
            wire_distance_ft, operating_watts, system_voltage,
            selected_awg, operating_current_a, actual_drop_v, actual_drop_pct,
        )

        return WireSizingResult(
            recommended_awg=selected_awg,
            wire_distance_ft=round(wire_distance_ft, 1),
            operating_watts=round(operating_watts, 1),
            system_voltage=round(system_voltage, 1),
            operating_current_a=round(operating_current_a, 3),
            voltage_drop_v=round(actual_drop_v, 3),
            voltage_drop_percent=round(actual_drop_pct, 2),
            resistance_per_1000ft=selected_r,
            note=note,
        )
