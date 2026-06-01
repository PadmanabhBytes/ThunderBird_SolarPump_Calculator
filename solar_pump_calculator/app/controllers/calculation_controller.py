"""
Calculation controller — all engineering endpoints live here.

Routes:
    POST /calculations/calculate    Full pipeline (TDH → solar → pump rank)  ← primary
    POST /calculations/recommend    Alias for /calculate (backward compat)
    POST /calculations/tdh          Full TDH breakdown (dedicated TDH engine)
    POST /calculations/tdh/pipeline Quick TDH from recommendation-pipeline request
    POST /calculations/solar        Solar sizing only
    GET  /calculations/pumps        List pump catalog
    GET  /calculations/pumps/{id}   Single pump detail
    GET  /calculations/materials    Pipe materials + available diameters
"""

import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..config import Settings, get_settings
from ..dependencies import (
    get_friction_repo,
    get_pump_eval_service,
    get_pump_filter_service,
    get_pump_repo,
    get_ranking_service,
    get_solar_service,
    get_tdh_service,
    get_nrel_service,
    get_wire_sizing_service,
)
from ..models.calculation_request import CalculationRequest, TDHRequest
from ..models.calculation_response import (
    CalculationResponse,
    SolarOnlyResponse,
    TDHOnlyResponse,
    TDHResult,
)
from ..models.pump import Pump
from ..repositories.friction_repository import FrictionRepository
from ..repositories.pump_repository import PumpRepository
from ..services.pump_eval_service import PumpEvalService
from ..services.pump_filter_service import PumpFilterService
from ..services.ranking_service import RankingService
from ..services.solar_service import SolarService, SolarZoneRegistry
from ..services.tdh_service import TDHService
from ..services.nrel_service import NRELService
from ..services.wire_sizing_service import WireSizingService
from ..utils.exceptions import (
    CalculationError,
    DataNotFoundError,
    InsufficientDataError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calculations", tags=["Calculations"])


# ── Hydraulic power estimate (used when no performance curve is available) ─────

def _hydraulic_power_w(
    tdh_ft:        float,
    flow_gpm:      float,
    pump_eff:      float,
    system_losses: float = 0.15,
) -> float:
    """
    Estimate pump input power from the hydraulic operating point.

    Formula (US customary):
        hydraulic_watts = (GPM × TDH_ft × 8.34 lb/gal) / (33,000 ft·lb/min · pump_eff)
                        × 746 W/hp / (1 − system_losses)

    This is a first-principles estimate only.  When real performance datasets
    are loaded, the actual operating wattage is used instead.

    Args:
        tdh_ft:        Total Dynamic Head (ft).
        flow_gpm:      Flow rate (US GPM).
        pump_eff:      Pump wire-to-water efficiency (fraction 0–1).
        system_losses: Wiring + controller losses as a fraction (0–1).

    Returns:
        Estimated input power in watts (always > 0).
    """
    # Water horsepower:  WHP = (GPM × TDH_ft) / 3960
    # Shaft horsepower:  SHP = WHP / pump_eff
    # Input watts:       W   = SHP × 746 / (1 − system_losses)
    if pump_eff <= 0 or pump_eff > 1:
        pump_eff = 0.45
    whp = (flow_gpm * tdh_ft) / 3960.0
    shp = whp / pump_eff
    input_w = shp * 746.0 / max(0.01, 1.0 - system_losses)
    return max(1.0, round(input_w, 1))


# ── Shared pipeline implementation ────────────────────────────────────────────

async def _run_calculation(
    request:              CalculationRequest,
    settings:             Settings,
    tdh_service:          TDHService,
    solar_service:        SolarService,
    pump_eval_service:    PumpEvalService,
    pump_filter_service:  PumpFilterService,
    ranking_service:      RankingService,
    nrel_service:         NRELService,
    wire_sizing_service:  WireSizingService,
) -> CalculationResponse:
    """
    Full calculation pipeline: TDH → solar sizing → pump evaluation → ranking.

    Steps
    -----
    1. Compute Total Dynamic Head and pipe velocity from site geometry.
    2. Estimate hydraulic power (fallback for pumps without a performance dataset).
    3. Size the solar array using production and deadhead paths.
    4. Evaluate every pump in the catalog against the required TDH / flow.
    5. Rank eligible pumps; return top-5 recommendations.
    """
    warnings: List[str] = []

    # ── 0. Solar Resource Lookup ──────────────────────────────────────────────
    peak_sun_hours   = request.peak_sun_hours
    solar_coefficient = request.solar_coefficient   # may be overridden by NREL zone

    if request.latitude is not None and request.longitude is not None:
        nrel_result = await nrel_service.get_solar_resource(request.latitude, request.longitude)
        if nrel_result is not None:
            peak_sun_hours    = nrel_result.peak_sun_hours
            solar_coefficient = nrel_result.coefficient
            warnings.append(
                f"NREL: GHI={nrel_result.ghi:.2f} kWh/m²/day → "
                f"Solar Zone {nrel_result.solar_zone} → "
                f"array coefficient {nrel_result.coefficient:.2f}×"
            )
        else:
            warnings.append(
                "NREL lookup failed — using manual peak sun hours and solar coefficient."
            )

    # When NREL didn't supply a zone coefficient (manual PSH or NREL failure),
    # derive it from peak_sun_hours treated as a GHI proxy.
    # Generator backup covers low-sun days, so no zone oversize is needed.
    if solar_coefficient == 1.0 and peak_sun_hours is not None:
        zone_id, solar_coefficient = SolarZoneRegistry.zone_from_ghi(peak_sun_hours)
        warnings.append(
            f"Manual PSH {peak_sun_hours:.1f} h/day → "
            f"Solar Zone {zone_id} → array coefficient {solar_coefficient:.2f}×"
        )

    if peak_sun_hours is None:
        peak_sun_hours = 5.0
        warnings.append("No solar resource available. Defaulting to 5.0 peak sun hours.")

    # ── 1. TDH ────────────────────────────────────────────────────────────────
    head_breakdown, pipe_velocity = tdh_service.calculate(
        request, max_velocity_fps=settings.max_pipe_velocity_fps
    )
    tdh_ft = head_breakdown.total_dynamic_head_ft

    if not pipe_velocity.is_within_limit:
        warnings.append(
            f"Pipe velocity {pipe_velocity.velocity_fps:.2f} ft/s exceeds the "
            f"recommended maximum of {pipe_velocity.recommended_max_fps:.1f} ft/s. "
            "Consider increasing pipe diameter."
        )

    # ── 2. Hydraulic power estimate (fallback for pumps without curves) ────────
    pump_eff = request.pump_efficiency or settings.default_pump_efficiency
    fallback_power_w = _hydraulic_power_w(
        tdh_ft=tdh_ft,
        flow_gpm=request.required_flow_gpm,
        pump_eff=pump_eff,
        system_losses=settings.default_system_losses,
    )

    # ── 3. Solar sizing (production + deadhead) ────────────────────────────────
    #  Use deadhead_watts from the request when provided; otherwise fall back
    #  to the hydraulic estimate so the sizing is always defined.
    dh_watts = request.deadhead_watts if request.deadhead_watts is not None else fallback_power_w

    solar_sizing = solar_service.calculate(
        operating_watts=fallback_power_w,
        deadhead_watts=dh_watts,
        solar_coefficient=solar_coefficient,
        panel_wattage_w=request.panel_wattage_w,
    )

    # ── 4a. Pump pre-filtering (casing / water quality / generator) ────────────
    all_pumps   = pump_eval_service._repo.get_all_pumps()
    filter_result = pump_filter_service.filter_pumps(
        pumps=all_pumps,
        well_casing_diameter_in=request.well_casing_diameter_in,
        generator_backup_required=request.generator_backup_required,
        poor_water_quality=request.poor_water_quality,
    )
    warnings.extend(filter_result.reasons)

    if filter_result.hard_stop:
        warnings.append(
            "No pumps are compatible with the specified well casing diameter. "
            "Cannot generate recommendations."
        )
        from ..models.recommendation import RankedRecommendationSet, RankingValidationResult
        empty_recs = RankedRecommendationSet(
            economical=None, precise=None, premium=None,
            total_evaluated=len(all_pumps), eligible_count=0,
            categories_filled=0,
            validation=RankingValidationResult(
                categories_evaluated=3, categories_with_winner=0,
                empty_categories=["economical", "precise", "premium"],
                warnings=["Hard stop: well casing too small for any pump design."],
            ),
        )
        return CalculationResponse(
            required_flow_gpm=request.required_flow_gpm,
            daily_water_demand_gallons=request.gpd,
            peak_sun_hours=peak_sun_hours,
            solar_coefficient=solar_coefficient,
            head_breakdown=head_breakdown,
            pipe_velocity=pipe_velocity,
            solar_sizing=solar_sizing,
            recommendations=empty_recs,
            warnings=warnings,
        )

    # ── 4b. Pump performance evaluation ───────────────────────────────────────
    eval_results = pump_eval_service.evaluate_pumps(
        pumps=filter_result.pumps,
        required_flow_gpm=request.required_flow_gpm,
        required_head_ft=tdh_ft,
    )

    total_candidates = len(all_pumps)
    eligible_count   = sum(1 for r in eval_results if r.is_eligible)

    if eligible_count == 0:
        warnings.append(
            "No pumps in the catalog meet the required TDH and flow. "
            "Consider relaxing requirements or expanding the pump dataset."
        )

    # ── 5. Rank ────────────────────────────────────────────────────────────────
    recommendations = ranking_service.rank(
        eval_results=eval_results,
        required_flow_gpm=request.required_flow_gpm,
        required_head_ft=tdh_ft,
        fallback_operating_watts=fallback_power_w,
        panel_wattage_w=request.panel_wattage_w,
        solar_coefficient=solar_coefficient,
        deadhead_watts=request.deadhead_watts,
        pump_eval_service=pump_eval_service,
        stc_efficiency_loss=request.stc_efficiency_loss,
        generator_backup_required=request.generator_backup_required,
        pump_rated_gpm_fallback=request.pump_rated_flow_gpm,
    )

    # ── Demand vs. daily pump runtime check ───────────────────────────────────
    effective_gpd    = request.gpd
    max_daily_volume = request.required_flow_gpm * 60.0 * peak_sun_hours
    if effective_gpd > max_daily_volume:
        warnings.append(
            f"Daily demand ({effective_gpd:.0f} gal) exceeds "
            f"maximum pumpable volume during peak sun hours "
            f"({max_daily_volume:.0f} gal). Consider battery storage or a larger array."
        )

    # ── Well recovery rate warnings ────────────────────────────────────────────
    if request.well_recovery_unknown:
        warnings.append(
            "Well recovery rate is unknown. "
            "Recommend installing dry-run protection (dry well sensor) to prevent "
            "pump damage if the well runs dry."
        )
    elif request.recovery_rate_gpm is not None:
        if request.recovery_rate_gpm < request.required_flow_gpm:
            warnings.append(
                f"Over-pumping risk: required flow ({request.required_flow_gpm:.1f} GPM) "
                f"exceeds well recovery rate ({request.recovery_rate_gpm:.1f} GPM). "
                "Install dry-run protection (dry well sensor) to prevent pump damage."
            )
        elif request.recovery_rate_gpm < request.required_flow_gpm * 1.2:
            warnings.append(
                f"Well recovery rate ({request.recovery_rate_gpm:.1f} GPM) is close to "
                f"the required flow ({request.required_flow_gpm:.1f} GPM). "
                "Consider dry-run protection as a precaution."
            )

    # ── 6. Wire sizing ─────────────────────────────────────────────────────────
    from ..models.calculation_response import WireSizingResponse
    wire_sizing_response = None
    if request.wire_distance_ft is not None:
        try:
            # Determine system voltage: prefer N_panels × panel_vmp_v (DC array
            # voltage), fall back to pump catalog voltage or 220V.
            prec = recommendations.precise
            n_panels_for_wire = prec.solar_panels if prec else None
            if request.panel_vmp_v is not None and n_panels_for_wire is not None:
                wire_voltage = n_panels_for_wire * request.panel_vmp_v
            elif prec is not None and prec.pump is not None:
                # Extract numeric voltage from catalog string (e.g. "220" → 220.0)
                raw_v = prec.pump.voltage_range or "220"
                try:
                    wire_voltage = float(str(raw_v).split("-")[0].split("/")[0].strip())
                except (ValueError, AttributeError):
                    wire_voltage = 220.0
            else:
                wire_voltage = 220.0

            # Wire sizing strategy differs by system type:
            #   Solar-only: size for pump motor rated power (AC full-load current), 5% drop
            #   Generator backup: size for DC array output (n_panels × panel_wattage), 10% drop
            # The 10% limit for backup systems matches solar pump field practice where the
            # MPPT controller tolerates array-side voltage variation and deep-well runs.
            if request.generator_backup_required and prec is not None:
                wire_watts    = prec.solar_panels * request.panel_wattage_w
                max_drop_frac = 0.10
            else:
                wire_watts = (
                    prec.operating_wattage_w
                    if prec is not None and prec.operating_wattage_w is not None
                    else fallback_power_w
                )
                max_drop_frac = 0.05

            ws = wire_sizing_service.calculate(
                wire_distance_ft=request.wire_distance_ft,
                operating_watts=wire_watts,
                system_voltage=wire_voltage,
                max_drop_fraction=max_drop_frac,
            )

            # TBS minimum wire standards:
            #   Solar-only: 10 AWG (heavier due to DC continuous-duty rating)
            #   Generator backup: 12 AWG (MPPT controller handles current variation)
            _AWG_RANK = [
                "14 AWG", "12 AWG", "10 AWG", "8 AWG", "6 AWG", "4 AWG",
                "3 AWG", "2 AWG", "1 AWG", "1/0 AWG", "2/0 AWG", "3/0 AWG", "4/0 AWG",
            ]
            _MIN_AWG = "12 AWG" if request.generator_backup_required else "10 AWG"
            try:
                if _AWG_RANK.index(ws.recommended_awg) < _AWG_RANK.index(_MIN_AWG):
                    final_awg = _MIN_AWG
                else:
                    final_awg = ws.recommended_awg
            except ValueError:
                final_awg = ws.recommended_awg

            wire_sizing_response = WireSizingResponse(
                recommended_awg=final_awg,
                wire_distance_ft=ws.wire_distance_ft,
                operating_watts=ws.operating_watts,
                system_voltage=ws.system_voltage,
                operating_current_a=ws.operating_current_a,
                voltage_drop_v=ws.voltage_drop_v,
                voltage_drop_percent=ws.voltage_drop_percent,
                resistance_per_1000ft=ws.resistance_per_1000ft,
                note=ws.note,
            )
            if ws.note:
                warnings.append(f"Wire sizing: {ws.note}")
        except Exception as exc:
            warnings.append(f"Wire sizing calculation skipped: {exc}")

    # ── 7. Accessories assembly ────────────────────────────────────────────────
    from ..models.calculation_response import AccessoryItem
    accessories: list[AccessoryItem] = []

    if request.float_switch:
        accessories.append(AccessoryItem(
            sku=None,
            name="Float Switch",
            category="TBS",
            reason="Float switch requested for tank level control.",
        ))
    if request.pressure_switch:
        range_note = f" ({request.pressure_switch_range})" if request.pressure_switch_range else ""
        accessories.append(AccessoryItem(
            sku=None,
            name=f"Pressure Switch{range_note}",
            category="TBS",
            reason="Pressure switch requested for system pressure control.",
        ))
    if request.well_recovery_unknown or (
        request.recovery_rate_gpm is not None
        and request.recovery_rate_gpm < request.required_flow_gpm
    ):
        accessories.append(AccessoryItem(
            sku=None,
            name="Dry Well Sensor (Dry-Run Protection)",
            category="Non-TBS",
            reason="Recommended due to low or unknown well recovery rate.",
        ))

    return CalculationResponse(
        required_flow_gpm=request.required_flow_gpm,
        daily_water_demand_gallons=request.gpd,
        peak_sun_hours=peak_sun_hours,
        solar_coefficient=solar_coefficient,
        head_breakdown=head_breakdown,
        pipe_velocity=pipe_velocity,
        solar_sizing=solar_sizing,
        wire_sizing=wire_sizing_response,
        accessories=accessories,
        recommendations=recommendations,
        warnings=warnings,
    )


# ── POST /calculate — primary endpoint ───────────────────────────────────────

@router.post(
    "/calculate",
    response_model=CalculationResponse,
    summary="Solar pump system sizing and recommendations",
    description=(
        "Runs the complete calculation pipeline for a solar pumping system:\n\n"
        "1. **TDH** — Total Dynamic Head from site geometry, pipe parameters, "
        "and a safety factor.\n"
        "2. **Solar sizing** — Array size via two paths:\n"
        "   - *Production*: `pump_input_power × solar_coefficient`\n"
        "   - *Deadhead*: `deadhead_watts / 0.35` (low-irradiance start check)\n"
        "   Final panel count = `max(production_panels, deadhead_panels)`.\n"
        "3. **Pump evaluation** — Each catalog pump is assessed at the required "
        "TDH/flow using performance-curve interpolation (where available) or "
        "catalog envelope bounds as a fallback.\n"
        "4. **Ranking** — Eligible pumps are scored on efficiency, power match, "
        "and head margin; top 5 are returned."
    ),
    status_code=status.HTTP_200_OK,
)
async def calculate(
    request:              CalculationRequest,
    settings:             Settings           = Depends(get_settings),
    tdh_service:          TDHService         = Depends(get_tdh_service),
    solar_service:        SolarService       = Depends(get_solar_service),
    pump_eval_service:    PumpEvalService    = Depends(get_pump_eval_service),
    pump_filter_service:  PumpFilterService  = Depends(get_pump_filter_service),
    ranking_service:      RankingService     = Depends(get_ranking_service),
    nrel_service:         NRELService        = Depends(get_nrel_service),
    wire_sizing_service:  WireSizingService  = Depends(get_wire_sizing_service),
) -> CalculationResponse:
    try:
        return await _run_calculation(
            request, settings, tdh_service, solar_service,
            pump_eval_service, pump_filter_service, ranking_service,
            nrel_service, wire_sizing_service,
        )
    except (CalculationError, InsufficientDataError) as exc:
        logger.error("Calculation error: %s", exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except DataNotFoundError as exc:
        logger.error("Data not found: %s", exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in /calculate")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ── POST /recommend — backward-compatible alias ───────────────────────────────

@router.post(
    "/recommend",
    response_model=CalculationResponse,
    summary="Full pipeline: TDH → solar sizing → pump recommendations (alias for /calculate)",
    include_in_schema=True,
    status_code=status.HTTP_200_OK,
)
async def recommend(
    request:              CalculationRequest,
    settings:             Settings           = Depends(get_settings),
    tdh_service:          TDHService         = Depends(get_tdh_service),
    solar_service:        SolarService       = Depends(get_solar_service),
    pump_eval_service:    PumpEvalService    = Depends(get_pump_eval_service),
    pump_filter_service:  PumpFilterService  = Depends(get_pump_filter_service),
    ranking_service:      RankingService     = Depends(get_ranking_service),
    nrel_service:         NRELService        = Depends(get_nrel_service),
    wire_sizing_service:  WireSizingService  = Depends(get_wire_sizing_service),
) -> CalculationResponse:
    try:
        return await _run_calculation(
            request, settings, tdh_service, solar_service,
            pump_eval_service, pump_filter_service, ranking_service,
            nrel_service, wire_sizing_service,
        )
    except (CalculationError, InsufficientDataError) as exc:
        logger.error("Calculation error: %s", exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except DataNotFoundError as exc:
        logger.error("Data not found: %s", exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in /recommend")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ── POST /tdh ─────────────────────────────────────────────────────────────────

@router.post(
    "/tdh",
    response_model=TDHResult,
    summary="Full TDH breakdown — four-term formula with computed or direct mode",
    description=(
        "Calculates TDH using the formula:\n\n"
        "    TDH = (Pumping Level + Elevation Gain + Friction Loss + Pressure Head) × SF\n\n"
        "where **Pumping Level** = static water level + drawdown, and "
        "**Pressure Head** = PSI × 2.31 ft.\n\n"
        "Supply `direct_tdh_ft` to skip calculation and wrap a known TDH value "
        "in the structured breakdown instead."
    ),
)
async def calculate_tdh(
    request:     TDHRequest,
    tdh_service: TDHService = Depends(get_tdh_service),
) -> TDHResult:
    try:
        return tdh_service.compute(request)
    except (CalculationError, DataNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in /tdh")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/tdh/pipeline",
    response_model=TDHOnlyResponse,
    summary="TDH from recommendation-pipeline inputs",
    description=(
        "Accepts the same `CalculationRequest` body used by `/calculate`. "
        "Returns a lightweight TDH + pipe-velocity result without running "
        "pump evaluation or solar sizing."
    ),
)
async def calculate_tdh_pipeline(
    request:     CalculationRequest,
    settings:    Settings   = Depends(get_settings),
    tdh_service: TDHService = Depends(get_tdh_service),
) -> TDHOnlyResponse:
    warnings: List[str] = []
    try:
        head_breakdown, pipe_velocity = tdh_service.calculate(
            request, max_velocity_fps=settings.max_pipe_velocity_fps
        )
        if not pipe_velocity.is_within_limit:
            warnings.append(
                f"Pipe velocity {pipe_velocity.velocity_fps:.2f} ft/s exceeds "
                f"{pipe_velocity.recommended_max_fps:.1f} ft/s limit."
            )
        return TDHOnlyResponse(
            head_breakdown=head_breakdown,
            pipe_velocity=pipe_velocity,
            warnings=warnings,
        )
    except (CalculationError, DataNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ── POST /solar ───────────────────────────────────────────────────────────────

@router.post(
    "/solar",
    response_model=SolarOnlyResponse,
    summary="Solar array sizing (production + deadhead) given TDH and flow",
    description=(
        "Runs solar sizing only — no pump evaluation or ranking.\n\n"
        "Two sizing paths are evaluated:\n"
        "- **Production**: `pump_input_power × solar_coefficient`\n"
        "- **Deadhead**: `deadhead_watts / 0.35`\n\n"
        "Final panel count = `max(production_panels, deadhead_panels)`."
    ),
)
async def calculate_solar(
    request:       CalculationRequest,
    settings:      Settings      = Depends(get_settings),
    tdh_service:   TDHService    = Depends(get_tdh_service),
    solar_service: SolarService  = Depends(get_solar_service),
) -> SolarOnlyResponse:
    warnings: List[str] = []
    try:
        head_breakdown, _ = tdh_service.calculate(request)
        pump_eff = request.pump_efficiency or settings.default_pump_efficiency

        fallback_power_w = _hydraulic_power_w(
            tdh_ft=head_breakdown.total_dynamic_head_ft,
            flow_gpm=request.required_flow_gpm,
            pump_eff=pump_eff,
            system_losses=settings.default_system_losses,
        )
        dh_watts = request.deadhead_watts if request.deadhead_watts is not None else fallback_power_w

        solar_sizing = solar_service.calculate(
            operating_watts=fallback_power_w,
            deadhead_watts=dh_watts,
            solar_coefficient=request.solar_coefficient,
            panel_wattage_w=request.panel_wattage_w,
        )
        return SolarOnlyResponse(solar_sizing=solar_sizing, warnings=warnings)
    except (CalculationError, DataNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ── Reference data ────────────────────────────────────────────────────────────

@router.get(
    "/pumps",
    response_model=List[Pump],
    summary="List all pumps in the catalog",
)
async def list_pumps(
    pump_type: str | None = Query(default=None, description="Filter by pump type"),
    pump_repo: PumpRepository = Depends(get_pump_repo),
) -> List[Pump]:
    pumps = pump_repo.get_all_pumps()
    if pump_type:
        pumps = [p for p in pumps if p.pump_type.value == pump_type.lower()]
    return pumps


@router.get(
    "/pumps/{pump_id}",
    response_model=Pump,
    summary="Get a single pump by ID",
)
async def get_pump(
    pump_id:   str,
    pump_repo: PumpRepository = Depends(get_pump_repo),
) -> Pump:
    try:
        return pump_repo.get_pump_by_id(pump_id)
    except DataNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/materials",
    response_model=Dict[str, List[float]],
    summary="List supported pipe materials and their available nominal diameters (inches)",
)
async def list_materials(
    friction_repo: FrictionRepository = Depends(get_friction_repo),
) -> Dict[str, List[float]]:
    return {
        mat: friction_repo.get_available_diameters(mat)
        for mat in friction_repo.get_supported_materials()
    }
