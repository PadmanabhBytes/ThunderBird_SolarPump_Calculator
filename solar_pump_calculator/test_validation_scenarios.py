"""
Validation test suite — 5 reference scenarios from the 15TBS-4C-AC spec sheet.

Each scenario is a known-good input/output pair.  Run with:
    .venv/bin/python test_validation_scenarios.py

Expected outputs (tolerance ±5%):
    TDH, friction, panel count, achievable GPM, wire AWG
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")

from app.config import get_settings
from app.repositories.friction_repository import FrictionRepository
from app.repositories.pump_repository import PumpRepository
from app.services.friction_service import FrictionService
from app.services.nrel_service import NRELService
from app.services.pump_eval_service import PumpEvalService
from app.services.pump_filter_service import PumpFilterService
from app.services.ranking_service import RankingService
from app.services.solar_service import SolarService
from app.services.tdh_service import TDHService
from app.services.wire_sizing_service import WireSizingService
from app.controllers.calculation_controller import _run_calculation
from app.models.calculation_request import CalculationRequest


# ── Expected outputs (from client-provided reference sheet) ──────────────────

@dataclass
class Expected:
    tdh_ft: float
    friction_ft: float
    panels: int
    achievable_gpm: float
    daily_gpd: int
    wire_awg: str
    pump_id: str = "15TBS-4C-AC"


SCENARIOS = [
    # ── Scenario 1 — Deep Well, Year Round, No Backup (Fort Davis TX 79835) ──
    dict(
        name="Scenario 1 — Deep Well, Fort Davis TX",
        request=dict(
            static_water_level_ft=220.0,
            dynamic_water_level_ft=265.0,   # 220+45 drawdown
            discharge_head_ft=15.0,
            required_flow_gpm=12.0,
            nominal_pipe_diameter_in=1.25,
            pipe_length_ft=300.0,
            pipe_material="PVC",
            discharge_pressure_psi=0.0,
            latitude=30.58, longitude=-103.89,    # Fort Davis TX
            panel_wattage_w=400.0,
            well_casing_diameter_in=5.0,
            recovery_rate_gpm=20.0,
            well_recovery_unknown=False,
            poor_water_quality=False,
            generator_backup_required=False,
            float_switch=True,
            pressure_switch=False,
            wire_distance_ft=300.0,
            panel_vmp_v=41.2,
        ),
        expected=Expected(
            tdh_ft=291.0,
            friction_ft=7.7,
            panels=5,
            achievable_gpm=15.1,
            daily_gpd=6478,
            wire_awg="10 AWG",
        ),
    ),
    # ── Scenario 2 — Medium Well, Summer Only, Float Switch (Alamogordo NM 88310) ──
    dict(
        name="Scenario 2 — Medium Well, Alamogordo NM",
        request=dict(
            static_water_level_ft=150.0,
            dynamic_water_level_ft=180.0,   # 150+30 drawdown
            discharge_head_ft=25.0,
            required_flow_gpm=15.0,
            nominal_pipe_diameter_in=1.5,
            pipe_length_ft=700.0,
            pipe_material="PVC",
            discharge_pressure_psi=0.0,
            latitude=32.89, longitude=-105.96,   # Alamogordo NM
            panel_wattage_w=370.0,
            well_casing_diameter_in=4.5,
            recovery_rate_gpm=15.0,
            well_recovery_unknown=False,
            poor_water_quality=False,
            generator_backup_required=False,
            float_switch=True,
            pressure_switch=False,
            wire_distance_ft=200.0,
            panel_vmp_v=39.6,
        ),
        expected=Expected(
            tdh_ft=217.0,
            friction_ft=12.2,
            panels=5,
            achievable_gpm=17.8,
            daily_gpd=7640,
            wire_awg="10 AWG",
        ),
    ),
    # ── Scenario 3 — Pressure Switch, Generator Backup (Monte Vista CO 81132) ──
    dict(
        name="Scenario 3 — Pressure Switch + Generator, Monte Vista CO",
        request=dict(
            static_water_level_ft=180.0,
            dynamic_water_level_ft=230.0,   # 180+50 drawdown
            discharge_head_ft=10.0,
            required_flow_gpm=14.0,
            nominal_pipe_diameter_in=1.25,
            pipe_length_ft=250.0,
            pipe_material="PVC",
            discharge_pressure_psi=40.0,   # 20/40 pressure switch cut-out
            latitude=37.58, longitude=-106.15,   # Monte Vista CO
            panel_wattage_w=370.0,
            well_casing_diameter_in=5.0,
            recovery_rate_gpm=17.0,
            well_recovery_unknown=True,
            poor_water_quality=False,
            generator_backup_required=True,
            float_switch=False,
            pressure_switch=True,
            pressure_switch_range="30/50 psi",
            wire_distance_ft=275.0,
            panel_vmp_v=40.0,
        ),
        expected=Expected(
            tdh_ft=339.0,
            friction_ft=6.4,
            panels=6,
            achievable_gpm=14.1,
            daily_gpd=6050,
            wire_awg="12 AWG",
        ),
    ),
    # ── Scenario 4 — Shallow Well, High Flow, Generator Backup (Monte Vista CO) ──
    dict(
        name="Scenario 4 — Shallow Well High Flow, Monte Vista CO",
        request=dict(
            static_water_level_ft=80.0,
            dynamic_water_level_ft=115.0,   # 80+35 drawdown
            discharge_head_ft=10.0,
            required_flow_gpm=20.0,
            nominal_pipe_diameter_in=2.0,   # no pipe friction given — assume large
            pipe_length_ft=1.0,             # effectively zero friction
            pipe_material="PVC",
            discharge_pressure_psi=0.0,
            latitude=37.58, longitude=-106.15,   # Monte Vista CO
            panel_wattage_w=235.0,
            well_casing_diameter_in=5.0,
            recovery_rate_gpm=50.0,
            well_recovery_unknown=False,
            poor_water_quality=False,
            generator_backup_required=True,
            float_switch=True,
            pressure_switch=False,
            wire_distance_ft=100.0,
            panel_vmp_v=31.6,
        ),
        expected=Expected(
            tdh_ft=125.0,
            friction_ft=0.0,
            panels=8,
            achievable_gpm=20.9,
            daily_gpd=8960,
            wire_awg="12 AWG",
        ),
    ),
    # ── Scenario 5 — Deep Well, Generator Backup (Cottonwood CA 96022) ──
    dict(
        name="Scenario 5 — Very Deep Well, Cottonwood CA",
        request=dict(
            static_water_level_ft=460.0,
            dynamic_water_level_ft=470.0,   # 460+10 drawdown
            discharge_head_ft=10.0,
            required_flow_gpm=10.0,
            nominal_pipe_diameter_in=2.0,   # no pipe friction given
            pipe_length_ft=1.0,
            pipe_material="PVC",
            discharge_pressure_psi=0.0,
            latitude=40.35, longitude=-122.29,   # Cottonwood CA
            panel_wattage_w=370.0,
            well_casing_diameter_in=5.0,
            recovery_rate_gpm=25.0,
            well_recovery_unknown=False,
            poor_water_quality=False,
            generator_backup_required=True,
            float_switch=True,
            pressure_switch=False,
            wire_distance_ft=600.0,
            panel_vmp_v=32.4,
        ),
        expected=Expected(
            tdh_ft=480.0,
            friction_ft=0.0,
            panels=7,
            achievable_gpm=10.2,
            daily_gpd=4376,
            wire_awg="10 AWG",
        ),
    ),
]


# ── Test runner ───────────────────────────────────────────────────────────────

def pct_err(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else 100.0
    return abs(actual - expected) / expected * 100.0


async def run_all() -> None:
    settings = get_settings()

    friction_repo = FrictionRepository(settings.friction_data_dir)
    friction_repo.load()
    pump_repo = PumpRepository(settings.pump_data_path)
    pump_repo.load()

    friction_service  = FrictionService(friction_repo)
    tdh_service       = TDHService(friction_service)
    solar_service     = SolarService(settings)
    pump_eval_service = PumpEvalService(pump_repo)
    filter_service    = PumpFilterService()
    ranking_service   = RankingService(solar_service)
    nrel_service      = NRELService(settings)
    wire_service      = WireSizingService()

    passed = 0
    failed = 0

    for sc in SCENARIOS:
        name = sc["name"]
        exp: Expected = sc["expected"]

        req = CalculationRequest(**sc["request"])

        resp = await _run_calculation(
            request=req, settings=settings,
            tdh_service=tdh_service, solar_service=solar_service,
            pump_eval_service=pump_eval_service, pump_filter_service=filter_service,
            ranking_service=ranking_service, nrel_service=nrel_service,
            wire_sizing_service=wire_service,
        )

        hb   = resp.head_breakdown
        prec = resp.recommendations.precise

        actual_tdh      = hb.total_dynamic_head_ft
        actual_friction = hb.friction_loss_ft
        actual_panels   = prec.solar_panels if prec else None
        actual_gpm      = prec.achievable_gpm if prec else None
        actual_pump     = prec.pump.pump_id if prec else "—"
        actual_wire     = resp.wire_sizing.recommended_awg if resp.wire_sizing else "—"

        tdh_ok      = pct_err(actual_tdh, exp.tdh_ft) <= 5
        friction_ok = exp.friction_ft == 0 or pct_err(actual_friction, exp.friction_ft) <= 10
        panels_ok   = actual_panels == exp.panels
        gpm_ok      = actual_gpm is not None and pct_err(actual_gpm, exp.achievable_gpm) <= 10
        pump_ok     = actual_pump == exp.pump_id
        wire_ok     = actual_wire == exp.wire_awg

        all_ok = all([tdh_ok, friction_ok, panels_ok, gpm_ok, pump_ok, wire_ok])
        status = "PASS" if all_ok else "FAIL"
        if all_ok:
            passed += 1
        else:
            failed += 1

        print(f"\n{'─'*60}")
        print(f"  {status}  {name}")
        print(f"{'─'*60}")
        _row("TDH (ft)",       actual_tdh,      exp.tdh_ft,         tdh_ok,      fmt=".1f")
        _row("Friction (ft)",  actual_friction, exp.friction_ft,    friction_ok, fmt=".2f")
        _row("Pump ID",        actual_pump,     exp.pump_id,        pump_ok,     is_str=True)
        _row("Panels",         actual_panels,   exp.panels,         panels_ok,   fmt="d")
        _row("Achievable GPM", actual_gpm,      exp.achievable_gpm, gpm_ok,      fmt=".1f")
        _row("Wire AWG",       actual_wire,     exp.wire_awg,       wire_ok,     is_str=True)

    print(f"\n{'═'*60}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(SCENARIOS)} scenarios")
    print(f"{'═'*60}\n")


def _row(label, actual, expected, ok: bool, fmt: str = "s", is_str: bool = False) -> None:
    tick = "✓" if ok else "✗"
    if is_str:
        a_str = str(actual) if actual is not None else "None"
        e_str = str(expected)
    else:
        if actual is None:
            a_str = "None"
        else:
            a_str = f"{actual:{fmt}}"
        e_str = f"{expected:{fmt}}"
    print(f"  {tick} {label:<18} actual={a_str:<12} expected={e_str}")


if __name__ == "__main__":
    asyncio.run(run_all())
