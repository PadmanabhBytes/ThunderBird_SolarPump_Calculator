"""
End-to-end pipeline test using the Thunderbird 15TBS-4C-AC pump.

Scenario
--------
A rancher needs 15 GPM from a 250 ft deep well.  The delivery point is
20 ft above ground, the pipe run is 800 ft of 1.5" PVC, and the system
pressure requirement is 30 PSI.  Solar panels are 400 W each; the site is
in Denver, CO (lat 39.74, lon -104.99).  A float switch and pressure switch
are required; wire run to the pump is 600 ft.

Expected behaviour
------------------
- TDH is computed from components (pumping level + elevation + friction + pressure)
- Solar coefficient is derived from NREL zone (or falls back to manual 1.55)
- 15TBS-4C-AC should appear in recommendations (0-30 GPM, 0-600 ft head)
- Wire sizing should recommend a gauge for 600 ft at ~48 V
- Float switch and pressure switch should appear in accessories
"""

import asyncio
import logging

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
from app.models.calculation_request import CalculationRequest, gpm_to_gpd

logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(name)s | %(message)s")


def section(title: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


async def run() -> None:
    settings = get_settings()

    # ── Repositories ──────────────────────────────────────────────────────────
    friction_repo = FrictionRepository(settings.friction_data_dir)
    friction_repo.load()

    pump_repo = PumpRepository(settings.pump_data_path)
    pump_repo.load()

    # ── Services ──────────────────────────────────────────────────────────────
    friction_service     = FrictionService(friction_repo)
    tdh_service          = TDHService(friction_service)
    solar_service        = SolarService(settings)
    pump_eval_service    = PumpEvalService(pump_repo)
    pump_filter_service  = PumpFilterService()
    ranking_service      = RankingService(solar_service)
    nrel_service         = NRELService(settings)
    wire_sizing_service  = WireSizingService()

    # ── Request — realistic ranch scenario ────────────────────────────────────
    request = CalculationRequest(
        # Water source
        static_water_level_ft   = 230.0,   # static depth to water
        dynamic_water_level_ft  = 250.0,   # pumping level (static + 20 ft drawdown)
        discharge_head_ft       = 20.0,    # delivery point above ground

        # Flow
        required_flow_gpm       = 15.0,
        # daily_water_demand_gallons omitted → auto-calculated from GPM
        # GPD = 15 × 6.5 × 60 × 1.1 = 6,435 gal/day

        # Pipe
        pipe_material           = "PVC",
        nominal_pipe_diameter_in= 1.5,
        pipe_length_ft          = 800.0,
        discharge_pressure_psi  = 30.0,

        # Solar — Denver, CO coords; NREL will derive zone + coefficient
        latitude                = 39.74,
        longitude               = -104.99,
        panel_wattage_w         = 400.0,

        # Well characteristics
        well_casing_diameter_in = 4.5,
        recovery_rate_gpm       = 18.0,    # adequate but close
        well_recovery_unknown   = False,

        # Water quality / pump compatibility
        poor_water_quality      = False,
        generator_backup_required = False,

        # Controls
        float_switch            = True,
        pressure_switch         = True,
        pressure_switch_range   = "30/50 psi",

        # Wire run
        wire_distance_ft        = 600.0,

        # Sizing tuning
        solar_coefficient       = 1.55,    # fallback if NREL fails
        deadhead_watts          = 2200.0,
    )

    # ── Run pipeline ──────────────────────────────────────────────────────────
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   Thunderbird Solar Pump Calculator — PoC Demo       ║")
    print("╚══════════════════════════════════════════════════════╝")

    response = await _run_calculation(
        request             = request,
        settings            = settings,
        tdh_service         = tdh_service,
        solar_service       = solar_service,
        pump_eval_service   = pump_eval_service,
        pump_filter_service = pump_filter_service,
        ranking_service     = ranking_service,
        nrel_service        = nrel_service,
        wire_sizing_service = wire_sizing_service,
    )

    # ── Inputs summary ────────────────────────────────────────────────────────
    section("INPUTS")
    print(f"  Flow required      : {request.required_flow_gpm} GPM")
    print(f"  Daily demand (GPD) : {response.daily_water_demand_gallons:,.0f} gal/day"
          f"  {'(auto from GPM)' if request.daily_water_demand_gallons is None else ''}")
    print(f"  Static water level : {request.static_water_level_ft} ft")
    print(f"  Pumping level      : {request.dynamic_water_level_ft} ft")
    print(f"  Elevation gain     : {request.discharge_head_ft} ft")
    print(f"  Pipe               : {request.nominal_pipe_diameter_in}\" {request.pipe_material.value}, {request.pipe_length_ft} ft")
    print(f"  System pressure    : {request.discharge_pressure_psi} PSI")
    print(f"  Panel wattage      : {request.panel_wattage_w} W")
    print(f"  Well casing        : {request.well_casing_diameter_in}\"")
    print(f"  Recovery rate      : {request.recovery_rate_gpm} GPM")

    # ── TDH ───────────────────────────────────────────────────────────────────
    section("TOTAL DYNAMIC HEAD (TDH)")
    hb = response.head_breakdown
    print(f"  Static head        : {hb.static_head_ft:.2f} ft  (pumping level + elevation)")
    print(f"  Friction loss      : {hb.friction_loss_ft:.2f} ft")
    print(f"  Minor losses       : {hb.minor_losses_ft:.2f} ft")
    print(f"  Pressure head      : {hb.pressure_head_ft:.2f} ft  ({request.discharge_pressure_psi} PSI × 2.31)")
    print(f"  Safety factor      : {hb.safety_factor_applied}×")
    print(f"  ─────────────────────────────────")
    print(f"  TDH                : {hb.total_dynamic_head_ft:.2f} ft")
    print(f"  Pipe velocity      : {response.pipe_velocity.velocity_fps:.2f} ft/s"
          f"  {'✓ OK' if response.pipe_velocity.is_within_limit else '⚠ EXCEEDS LIMIT'}")

    # ── Solar ─────────────────────────────────────────────────────────────────
    section("SOLAR SIZING")
    ss = response.solar_sizing
    print(f"  Peak sun hours     : {response.peak_sun_hours:.2f} h/day")
    print(f"  Solar coefficient  : {response.solar_coefficient:.2f}×")
    print(f"  Operating watts    : {ss.operating_watts:.0f} W")
    print(f"  Deadhead watts     : {ss.deadhead_watts:.0f} W")
    print(f"  Production panels  : {ss.production_panels}  ({ss.production_required_watts:.0f} W needed)")
    print(f"  Deadhead panels    : {ss.deadhead_panels}  ({ss.deadhead_required_watts:.0f} W needed)")
    print(f"  ─────────────────────────────────")
    print(f"  FINAL PANELS       : {ss.final_panels}  (governed by: {ss.governing_path})")

    # ── Wire sizing ───────────────────────────────────────────────────────────
    if response.wire_sizing:
        section("WIRE SIZING")
        ws = response.wire_sizing
        print(f"  Wire run           : {ws.wire_distance_ft:.0f} ft")
        print(f"  Operating current  : {ws.operating_current_a:.2f} A @ {ws.system_voltage:.0f} V")
        print(f"  Voltage drop       : {ws.voltage_drop_v:.2f} V  ({ws.voltage_drop_percent:.1f}%)")
        print(f"  ─────────────────────────────────")
        print(f"  RECOMMENDED GAUGE  : {ws.recommended_awg}")
        if ws.note:
            print(f"  Note: {ws.note}")

    # ── Accessories ───────────────────────────────────────────────────────────
    if response.accessories:
        section("REQUIRED ACCESSORIES")
        for acc in response.accessories:
            tag = f"[{acc.category}]"
            sku = f"  SKU: {acc.sku}" if acc.sku else ""
            print(f"  {tag:<12} {acc.name}{sku}")
            print(f"               {acc.reason}")

    # ── Recommendations ───────────────────────────────────────────────────────
    section("PUMP RECOMMENDATIONS")
    recs = response.recommendations
    print(f"  Evaluated: {recs.total_evaluated} pumps | Eligible: {recs.eligible_count}")

    for label, rec in [
        ("ECONOMICAL", recs.economical),
        ("PRECISE",    recs.precise),
        ("PREMIUM",    recs.premium),
    ]:
        print(f"\n  ── {label} ──")
        if rec is None:
            print("     No eligible pump found.")
            continue
        print(f"     Pump ID   : {rec.pump.pump_id}  ({rec.pump.brand} {rec.pump.model})")
        print(f"     Type      : {rec.pump.pump_type.value}")
        print(f"     Panels    : {rec.solar_panels}")
        if rec.achievable_gpm is not None:
            print(f"     Flow @ TDH: {rec.achievable_gpm:.1f} GPM  (need {request.required_flow_gpm} GPM)")
        if rec.operating_wattage_w is not None:
            print(f"     Op. watts : {rec.operating_wattage_w:.0f} W")
        print(f"     Head margin : {rec.head_margin_percent:.1f}%  |  Flow margin: {rec.flow_margin_percent:.1f}%")
        print(f"     Score     : {rec.category_score:.1f}/100")
        print(f"     Rationale : {rec.selection_rationale}")
        if rec.evaluation_warnings:
            for w in rec.evaluation_warnings:
                print(f"     ⚠ {w}")

    # ── Warnings ──────────────────────────────────────────────────────────────
    if response.warnings:
        section("SYSTEM WARNINGS")
        for w in response.warnings:
            print(f"  ⚠  {w}")

    print(f"\n{'═' * 52}\n")


if __name__ == "__main__":
    asyncio.run(run())
