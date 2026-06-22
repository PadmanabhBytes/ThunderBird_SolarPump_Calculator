from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from .pump import Pump
from .recommendation import RankedRecommendationSet


# ── Shared sub-models ─────────────────────────────────────────────────────────

class PipeVelocityInfo(BaseModel):
    velocity_fps: float = Field(..., description="Mean flow velocity in pipe (ft/s)")
    is_within_limit: bool = Field(..., description="True if velocity ≤ recommended max")
    recommended_max_fps: float = Field(default=10.0)


# ── Recommendation pipeline models ───────────────────────────────────────────

class HeadBreakdown(BaseModel):
    """
    TDH breakdown used inside the full recommendation pipeline response.
    All values in imperial units (feet).
    """
    static_head_ft: float = Field(..., description="Pumping level + elevation gain (ft)")
    friction_loss_ft: float = Field(..., description="Pipe + fittings friction (ft)")
    friction_flow_gpm: Optional[float] = Field(None, description="Flow rate used for friction sizing (GPM)")
    minor_losses_ft: float = Field(..., description="Parametric minor losses (ft)")
    pressure_head_ft: float = Field(default=0.0, description="Discharge pressure converted to head (ft)")
    subtotal_ft: float = Field(..., description="Sum of all components before safety factor (ft)")
    total_dynamic_head_ft: float = Field(..., description="TDH after safety factor (ft)")
    safety_factor_applied: float = Field(..., description="Safety factor multiplier used")


class SolarSizing(BaseModel):
    # ── Echoed inputs ─────────────────────────────────────────────────────────
    operating_watts: float = Field(..., description="Pump power at operating point (W) — from pump evaluation")
    deadhead_watts: float = Field(..., description="Pump power at shutoff condition (W)")
    solar_coefficient: float = Field(..., description="Array oversizing factor")
    panel_wattage_w: float = Field(..., description="Nameplate wattage per panel (W)")

    # ── Production sizing: operating_watts × solar_coefficient ────────────────
    production_required_watts: float = Field(..., description="operating_watts × solar_coefficient (W)")
    production_panels: int = Field(..., description="⌈production_required_watts / panel_wattage⌉")

    # ── Deadhead sizing: deadhead_watts / 0.35 ────────────────────────────────
    deadhead_required_watts: float = Field(..., description="deadhead_watts / 0.35 (W)")
    deadhead_panels: int = Field(..., description="⌈deadhead_required_watts / panel_wattage⌉")

    # ── Final ─────────────────────────────────────────────────────────────────
    final_panels: int = Field(..., description="max(production_panels, deadhead_panels)")
    governing_path: Literal["production", "deadhead"] = Field(
        ..., description="Which sizing path set the final panel count"
    )


class PumpRecommendation(BaseModel):
    rank: int = Field(..., description="Rank (1 = best match)")
    suitability_score: float = Field(..., ge=0, le=100, description="Composite score 0–100")
    pump: Pump
    meets_head_requirement: bool
    meets_flow_requirement: bool
    head_margin_percent: float = Field(..., description="(pump_max_head − TDH) / TDH × 100")
    flow_margin_percent: float = Field(..., description="(pump_max_flow − required) / required × 100")
    estimated_solar_panels: int = Field(..., description="Panels needed at this pump's efficiency")
    notes: str = Field(..., description="Human-readable suitability summary")
    # Curve-based operating-point data (present when performance dataset is available)
    operating_wattage_w: Optional[float] = Field(
        None,
        description=(
            "Minimum power (W) at which this pump meets the required flow at the required TDH. "
            "None when no performance dataset is available."
        ),
    )
    achievable_gpm: Optional[float] = Field(
        None,
        description="Flow (GPM) delivered at operating_wattage_w and required TDH.",
    )
    curve_based_evaluation: bool = Field(
        False,
        description=(
            "True when the operating point was derived from a real performance dataset. "
            "False means catalog envelope bounds were used — accuracy is reduced."
        ),
    )
    evaluation_warnings: List[str] = Field(
        default_factory=list,
        description=(
            "Non-fatal data-quality issues encountered during evaluation. "
            "Includes out-of-range head notices and missing-dataset notices."
        ),
    )


class WireSizingResponse(BaseModel):
    """Recommended wire gauge and supporting voltage-drop data (TBS formula)."""
    recommended_awg: str = Field(..., description="Recommended copper wire gauge (e.g. '10 AWG')")
    wire_distance_ft: float = Field(..., description="One-way wire run used for sizing (ft)")
    operating_watts: float = Field(..., description="System_Power = MIN(array_watts, pump_max_watts) (W)")
    system_voltage: float = Field(..., description="Vmp_Array = n_panels × panel_vmp × 0.95 (V)")
    operating_current_a: float = Field(..., description="Amp_Draw = MIN((System_Power/Vmp_Array)×1.05, 12) (A)")
    voltage_drop_v: float = Field(..., description="Calculated round-trip voltage drop (V)")
    voltage_drop_percent: float = Field(..., description="Voltage drop as % of Vmp_Array")
    resistance_per_1000ft: float = Field(..., description="TBS resistance of selected wire (Ω/kft equivalent)")
    note: str = Field(default="", description="Any sizing note or over-limit warning")
    # TBS-specific fields
    vmp_array_v: Optional[float] = Field(None, description="Operating array voltage = n_panels × Vmp × 0.95 (V)")
    system_power_w: Optional[float] = Field(None, description="System power capped at pump max (W)")
    amp_draw_a: Optional[float] = Field(None, description="Calculated amp draw capped at 12A (A)")
    max_length_by_gauge: Optional[dict] = Field(None, description="Max wire run per AWG gauge (ft)")


class AccessoryItem(BaseModel):
    """A single accessory required or recommended for the system."""
    sku: Optional[str] = Field(None, description="TBS product SKU (if applicable)")
    name: str = Field(..., description="Accessory name / description")
    category: str = Field(..., description="Category: e.g. 'TBS', 'Non-TBS', 'Optional'")
    reason: str = Field(default="", description="Why this accessory is recommended")


class CalculationResponse(BaseModel):
    # ── Echoed inputs ────────────────────────────────────────────────────────
    required_flow_gpm: float
    daily_water_demand_gallons: float
    peak_sun_hours: float
    solar_coefficient: float = Field(1.25, description="Solar array oversizing factor used")

    # ── Engineering results ──────────────────────────────────────────────────
    head_breakdown: HeadBreakdown
    pipe_velocity: PipeVelocityInfo
    solar_sizing: SolarSizing

    # ── Wire sizing ───────────────────────────────────────────────────────────
    wire_sizing: Optional[WireSizingResponse] = Field(
        None,
        description=(
            "Recommended wire gauge for the solar array to pump run. "
            "Present when wire_distance_ft was supplied in the request."
        ),
    )

    # ── System accessories ────────────────────────────────────────────────────
    accessories: List[AccessoryItem] = Field(
        default_factory=list,
        description=(
            "Required and recommended accessories derived from system configuration "
            "(float switch, pressure switch, dry-run protection, etc.)."
        ),
    )

    # ── Categorized recommendations ───────────────────────────────────────────
    recommendations: RankedRecommendationSet = Field(
        ...,
        description=(
            "Three-tier ranked recommendations: economical, precise, and premium. "
            "Each tier selects the single best pump for that client workflow."
        ),
    )

    # ── Metadata ─────────────────────────────────────────────────────────────
    calculation_version: str = "1.2.0"
    warnings: List[str] = Field(default_factory=list)


# ── Dedicated TDH endpoint models ────────────────────────────────────────────

class FrictionDetail(BaseModel):
    """
    Friction service lookup result embedded in a TDH breakdown.
    Provides full audit trail: what table was used, at what GPM, loss rate, etc.
    """
    material_table: str = Field(..., description="Friction table used: 'PVC' or 'Steel'")
    nominal_diameter_in: float = Field(..., description="Nominal pipe diameter used for lookup (in)")
    gpm: float = Field(..., description="Flow rate at which loss was looked up (GPM)")
    loss_per_100ft: float = Field(..., description="Interpolated loss rate (ft per 100 ft of pipe)")
    pipe_length_ft: float = Field(..., description="Straight pipe length (ft)")
    fittings_equivalent_length_ft: float = Field(..., description="Fittings equivalent length (ft)")
    total_equivalent_length_ft: float = Field(..., description="Total equivalent length used (ft)")
    pipe_friction_loss_ft: float = Field(..., description="Head loss from straight pipe (ft)")
    fittings_friction_loss_ft: float = Field(..., description="Head loss from fittings (ft)")
    total_friction_loss_ft: float = Field(..., description="Total friction head loss (ft)")


class TDHBreakdown(BaseModel):
    """
    Complete TDH breakdown with every named component in both feet and metres.

    Formula (computed mode):
        Pumping Level  = static_water_level + drawdown
        Pressure Head  = discharge_pressure_psi × 2.31  (ft)
        TDH            = (Pumping Level + Elevation Gain + Friction Loss + Pressure Head)
                         × safety_factor
    """

    # ── Water source ──────────────────────────────────────────────────────────
    static_water_level_ft: float = Field(..., description="Depth from surface to static water level (ft)")
    static_water_level_m: float  = Field(..., description="Depth from surface to static water level (m)")

    drawdown_ft: float = Field(..., description="Pumping drawdown — dynamic depression below static (ft)")
    drawdown_m: float  = Field(..., description="Pumping drawdown (m)")

    pumping_level_ft: float = Field(..., description="Total vertical lift to surface = static + drawdown (ft)")
    pumping_level_m: float  = Field(..., description="Total vertical lift to surface (m)")

    # ── Elevation ─────────────────────────────────────────────────────────────
    elevation_gain_ft: float = Field(..., description="Vertical rise from surface to delivery point (ft)")
    elevation_gain_m: float  = Field(..., description="Vertical rise from surface to delivery point (m)")

    # ── Pressure head ─────────────────────────────────────────────────────────
    discharge_pressure_psi: float = Field(..., description="Required delivery pressure (PSI)")
    pressure_head_ft: float = Field(..., description="Pressure converted to head = PSI × 2.31 (ft)")
    pressure_head_m: float  = Field(..., description="Pressure head (m)")

    # ── Friction head ─────────────────────────────────────────────────────────
    pipe_friction_loss_ft: float = Field(..., description="Pipe + fittings friction from dataset (ft)")
    pipe_friction_loss_m: float  = Field(..., description="Pipe + fittings friction (m)")

    minor_losses_ft: float = Field(..., description="Parametric minor losses = factor × pipe friction (ft)")
    minor_losses_m: float  = Field(..., description="Parametric minor losses (m)")

    total_friction_loss_ft: float = Field(..., description="pipe_friction + minor_losses (ft)")
    total_friction_loss_m: float  = Field(..., description="Total friction head loss (m)")

    # ── Aggregates ────────────────────────────────────────────────────────────
    static_lift_ft: float = Field(..., description="Pumping level + elevation gain (no losses) (ft)")
    static_lift_m: float  = Field(..., description="Static lift (m)")

    subtotal_ft: float = Field(..., description="All components summed before safety factor (ft)")
    subtotal_m: float  = Field(..., description="Subtotal (m)")

    safety_factor: float = Field(..., description="Safety factor applied (1.0 in direct mode)")

    # ── Final TDH ─────────────────────────────────────────────────────────────
    total_dynamic_head_ft: float = Field(..., description="Final TDH (ft)")
    total_dynamic_head_m: float  = Field(..., description="Final TDH (m)")

    # ── Metadata ──────────────────────────────────────────────────────────────
    is_direct_input: bool = Field(..., description="True when TDH was supplied by the caller")
    calculation_mode: Literal["computed", "direct"] = Field(
        ..., description="'computed' = derived from components; 'direct' = caller-supplied TDH"
    )


class TDHResult(BaseModel):
    """Full response from the dedicated TDH endpoint."""
    breakdown: TDHBreakdown
    pipe_velocity: Optional[PipeVelocityInfo] = Field(
        None, description="Pipe velocity info — present only when flow + pipe params are provided"
    )
    friction_detail: Optional[FrictionDetail] = Field(
        None, description="Friction lookup audit trail — present when friction was computed from pipe params"
    )
    warnings: List[str] = Field(default_factory=list)


# ── Lightweight single-concern responses (controller convenience) ─────────────

class TDHOnlyResponse(BaseModel):
    """Lightweight TDH response for the recommendation pipeline's /tdh endpoint."""
    head_breakdown: HeadBreakdown
    pipe_velocity: PipeVelocityInfo
    warnings: List[str] = Field(default_factory=list)


class SolarOnlyResponse(BaseModel):
    solar_sizing: SolarSizing
    warnings: List[str] = Field(default_factory=list)
