"""
Wire sizing service — recommends AWG wire gauge for a solar-to-pump run.

Two sizing methods are available:

TBS method (primary) — Thunderbird Solar formulas:
    Vmp_Array    = series_panels × panel_vmp × 0.95
    System_Power = MIN(total_panels × panel_watts, pump_max_watts)
    Amp_Draw     = MIN((System_Power / Vmp_Array) × 1.05, 12)
    Max_Length   = ROUNDDOWN((drop_frac × Vmp_Array) / (2 × Amp_Draw × R_per_ft), -1)
    Select smallest gauge where wire_distance ≤ Max_Length.

Legacy method (kept for fallback) — simple voltage-drop formula:
    I = watts / voltage
    drop = 2 × I × R_per_ft × distance
    Select smallest gauge where drop ≤ voltage × drop_frac.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# TBS-specified resistance constants (Ω/ft) — distinct from NEC 75°C values
_TBS_RESISTANCE: list[tuple[str, float]] = [
    ("14 AWG", 0.002525),
    ("12 AWG", 0.001588),
    ("10 AWG", 0.000999),
    ("8 AWG",  0.0006282),
    ("6 AWG",  0.0003951),
]

# NEC Table 9 (Ω per 1,000 ft at 75°C) — used by legacy calculate()
_AWG_RESISTANCE_LEGACY: list[tuple[str, float]] = [
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

_TBS_AMP_CAP: float = 12.0          # maximum allowable amp draw (TBS spec)
_TBS_SAFETY_FACTOR: float = 1.05    # amp draw safety factor
_TBS_VMP_DERATE: float = 0.95       # Vmp derate for operating temperature


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
    # TBS-specific fields (populated by calculate_tbs; None for legacy path)
    vmp_array_v: Optional[float] = None
    system_power_w: Optional[float] = None
    amp_draw_a: Optional[float] = None
    max_length_by_gauge: Dict[str, float] = field(default_factory=dict)


class WireSizingService:
    """
    Recommends copper wire gauge (AWG) for a solar pump installation.

    Primary method: calculate_tbs() — uses Thunderbird Solar formulas.
    Legacy method:  calculate()     — simple NEC voltage-drop formula.
    """

    def calculate_tbs(
        self,
        wire_distance_ft:   float,
        n_panels_series:    int,
        panel_vmp_v:        float,
        n_panels_total:     int,
        panel_wattage_w:    float,
        pump_max_watts:     float,
        max_drop_fraction:  float = 0.05,
        min_awg:            str   = "10 AWG",
    ) -> WireSizingResult:
        """
        TBS wire sizing formula.

        Computes Max_Length for each gauge and selects the smallest gauge
        where wire_distance ≤ Max_Length.

        Args:
            wire_distance_ft:  One-way wire run (ft).
            n_panels_series:   Number of panels wired in series.
            panel_vmp_v:       Per-panel Vmp (V).
            n_panels_total:    Total panel count (series × parallel strings).
            panel_wattage_w:   Per-panel nameplate wattage (W).
            pump_max_watts:    Pump hard power cap (W) — from catalog max_watts.
            max_drop_fraction: Allowed voltage drop fraction (0.05 or 0.10).
            min_awg:           Minimum gauge floor (e.g. "10 AWG" solar-only,
                               "12 AWG" generator backup).

        Returns:
            WireSizingResult with recommended AWG and TBS intermediate values.
        """
        if wire_distance_ft <= 0:
            raise ValueError(f"wire_distance_ft must be > 0; got {wire_distance_ft}")
        if n_panels_series <= 0 or panel_vmp_v <= 0:
            raise ValueError("panels and panel_vmp_v must be > 0")

        vmp_array = n_panels_series * panel_vmp_v * _TBS_VMP_DERATE
        system_power = min(n_panels_total * panel_wattage_w, pump_max_watts)
        raw_amps = (system_power / vmp_array) * _TBS_SAFETY_FACTOR
        amp_draw = min(raw_amps, _TBS_AMP_CAP)

        # Compute max wire length per gauge; select smallest gauge that fits
        max_lengths: Dict[str, float] = {}
        selected_awg = _TBS_RESISTANCE[-1][0]  # fallback: heaviest gauge

        for awg_label, r_per_ft in _TBS_RESISTANCE:
            numerator = max_drop_fraction * vmp_array
            denominator = 2.0 * amp_draw * r_per_ft
            raw_max = numerator / denominator
            # Round down to nearest 10 ft
            max_len = math.floor(raw_max / 10.0) * 10.0
            max_lengths[awg_label] = max_len
            if wire_distance_ft <= max_len:
                selected_awg = awg_label
                break  # smallest gauge that satisfies the run

        # Apply minimum gauge floor.
        # _TBS_RESISTANCE is ordered thin→thick (14→6 AWG), so a LOWER index
        # means a THINNER wire.  Upgrade when selected is thinner than the floor.
        _AWG_ORDER = [g for g, _ in _TBS_RESISTANCE]
        try:
            if _AWG_ORDER.index(selected_awg) < _AWG_ORDER.index(min_awg):
                selected_awg = min_awg
        except ValueError:
            pass

        # Compute actual voltage drop for the selected gauge
        selected_r = dict(_TBS_RESISTANCE).get(selected_awg, _TBS_RESISTANCE[-1][1])
        actual_drop_v = 2.0 * amp_draw * selected_r * wire_distance_ft
        actual_drop_pct = (actual_drop_v / vmp_array) * 100.0

        note = ""
        if wire_distance_ft > max_lengths.get("6 AWG", 0):
            note = (
                f"Wire run ({wire_distance_ft:.0f} ft) exceeds the maximum for all "
                "standard TBS gauge sizes. A parallel conductor run or a larger gauge "
                "may be required."
            )

        logger.info(
            "TBS wire sizing: %.0f ft | Vmp_Array=%.1f V | System_Power=%.0f W | "
            "Amp_Draw=%.2f A → %s",
            wire_distance_ft, vmp_array, system_power, amp_draw, selected_awg,
        )

        return WireSizingResult(
            recommended_awg=selected_awg,
            wire_distance_ft=round(wire_distance_ft, 1),
            operating_watts=round(system_power, 1),
            system_voltage=round(vmp_array, 2),
            operating_current_a=round(amp_draw, 3),
            voltage_drop_v=round(actual_drop_v, 3),
            voltage_drop_percent=round(actual_drop_pct, 2),
            resistance_per_1000ft=round(selected_r * 1000, 4),
            note=note,
            vmp_array_v=round(vmp_array, 2),
            system_power_w=round(system_power, 1),
            amp_draw_a=round(amp_draw, 3),
            max_length_by_gauge=max_lengths,
        )

    def calculate(
        self,
        wire_distance_ft: float,
        operating_watts:  float,
        system_voltage:   float = 48.0,
        max_drop_fraction: float = 0.03,
    ) -> WireSizingResult:
        """Legacy voltage-drop method (kept for backward compatibility)."""
        if wire_distance_ft <= 0:
            raise ValueError(f"wire_distance_ft must be > 0; got {wire_distance_ft}")
        if operating_watts <= 0:
            raise ValueError(f"operating_watts must be > 0; got {operating_watts}")
        if system_voltage <= 0:
            raise ValueError(f"system_voltage must be > 0; got {system_voltage}")

        operating_current_a = operating_watts / system_voltage
        max_drop_v          = system_voltage * max_drop_fraction

        selected_awg:   str   = _AWG_RESISTANCE_LEGACY[-1][0]
        selected_r:     float = _AWG_RESISTANCE_LEGACY[-1][1]

        for awg_label, r_per_kft in _AWG_RESISTANCE_LEGACY:
            r_per_ft = r_per_kft / 1000.0
            drop_v   = 2.0 * operating_current_a * r_per_ft * wire_distance_ft
            if drop_v <= max_drop_v:
                selected_awg = awg_label
                selected_r   = r_per_kft
                break

        actual_drop_v   = 2.0 * operating_current_a * (selected_r / 1000.0) * wire_distance_ft
        actual_drop_pct = (actual_drop_v / system_voltage) * 100.0

        note = ""
        if actual_drop_pct > max_drop_fraction * 100:
            note = (
                f"Voltage drop ({actual_drop_pct:.1f}%) exceeds the {max_drop_fraction*100:.0f}% "
                "limit even at 4/0 AWG. Consider reducing wire run length or increasing "
                "system voltage."
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
