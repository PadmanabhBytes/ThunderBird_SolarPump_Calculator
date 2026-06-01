from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field, model_validator


def gpm_to_gpd(gpm: float) -> float:
    """
    Convert GPM to GPD using the spec formula.

    GPD = GPM × 6.5 hours/day × 60 min/hr × 1.1 buffer factor
    Example: 5 GPM → 5 × 6.5 × 60 × 1.1 = 2,145 GPD
    """
    return round(gpm * 6.5 * 60 * 1.1, 1)


class PipeMaterial(str, Enum):
    PVC = "PVC"
    HDPE = "HDPE"
    GALVANIZED_STEEL = "Galvanized Steel"
    CAST_IRON_NEW = "Cast Iron (New)"
    CAST_IRON_OLD = "Cast Iron (Old)"
    DUCTILE_IRON = "Ductile Iron"
    COPPER = "Copper"
    STEEL = "Steel"
    CONCRETE = "Concrete"


# ── Full recommendation pipeline request (imperial units) ────────────────────

class CalculationRequest(BaseModel):
    """
    Request for the complete pump recommendation pipeline.
    All lengths in feet, flow in US GPM.
    """
    # ── Water source ─────────────────────────────────────────────────────────
    static_water_level_ft: float = Field(
        ..., gt=0, description="Depth from ground surface to static water level (ft)"
    )
    dynamic_water_level_ft: float = Field(
        ..., gt=0, description="Depth from ground to pumping water level (ft) = static + drawdown"
    )
    discharge_head_ft: float = Field(
        default=0.0, ge=0, description="Elevation from ground to delivery point (ft)"
    )

    # ── Flow requirements ────────────────────────────────────────────────────
    required_flow_gpm: float = Field(
        ..., gt=0, description="Required instantaneous flow rate (US GPM)"
    )
    daily_water_demand_gallons: Optional[float] = Field(
        default=None, gt=0,
        description=(
            "Total daily water demand (US gallons/day). "
            "If omitted, the calculator derives it from required_flow_gpm "
            "using: GPM × 6.5 × 60 × 1.1"
        )
    )

    @computed_field
    @property
    def gpd(self) -> float:
        """
        Effective GPD used by the pipeline.

        If the user supplied daily_water_demand_gallons, that value is used.
        Otherwise, calculated from GPM: GPM × 6.5 × 60 × 1.1
        """
        if self.daily_water_demand_gallons is not None:
            return self.daily_water_demand_gallons
        return gpm_to_gpd(self.required_flow_gpm)

    # ── Pipe parameters ──────────────────────────────────────────────────────
    nominal_pipe_diameter_in: float = Field(
        ..., gt=0, description="Nominal pipe diameter (inches) — used for friction table lookup"
    )
    pipe_length_ft: float = Field(
        ..., gt=0, description="Total pipe length (ft)"
    )
    pipe_material: PipeMaterial = Field(
        default=PipeMaterial.PVC, description="Pipe material"
    )

    # ── Pressure ─────────────────────────────────────────────────────────────
    discharge_pressure_psi: float = Field(
        default=0.0, ge=0,
        description="Required delivery pressure (PSI). Adds PSI × 2.31 ft to TDH."
    )

    # ── Solar parameters ─────────────────────────────────────────────────────
    peak_sun_hours: Optional[float] = Field(
        default=None, gt=0, le=12, description="Daily peak sun hours (h/day). If omitted, latitude and longitude must be provided."
    )
    latitude: Optional[float] = Field(
        default=None, ge=-90.0, le=90.0, description="Site latitude for NREL solar resource lookup."
    )
    longitude: Optional[float] = Field(
        default=None, ge=-180.0, le=180.0, description="Site longitude for NREL solar resource lookup."
    )
    panel_wattage_w: float = Field(
        default=400.0, gt=0, description="Nameplate wattage of each solar panel (W)"
    )

    # ── Well characteristics ─────────────────────────────────────────────────
    well_casing_diameter_in: Optional[float] = Field(
        default=None,
        description=(
            "Inner diameter of the well casing (inches). "
            "Accepted values: 3.5, 4.0, 4.5, 5.0+. "
            "Used to filter out incompatible pump designs. "
            "Pumps requiring ≥4\" casing are excluded when casing < 4.5\". "
            "All pumps excluded when casing < 3.5\"."
        )
    )
    recovery_rate_gpm: Optional[float] = Field(
        default=None, gt=0,
        description=(
            "Well recovery rate (GPM). When provided and less than required_flow_gpm, "
            "an over-pumping warning is issued recommending dry-run protection."
        )
    )
    well_recovery_unknown: bool = Field(
        default=False,
        description=(
            "Set True if the well recovery rate is unknown. "
            "Triggers a recommendation to install dry-run protection."
        )
    )

    # ── Water quality ────────────────────────────────────────────────────────
    poor_water_quality: bool = Field(
        default=False,
        description=(
            "Set True if the well has solids, sand, or iron bacteria that make "
            "it unsuitable for helical rotor-style pumps. "
            "Excludes all helical rotor SKUs from recommendations."
        )
    )

    # ── Generator / grid backup ──────────────────────────────────────────────
    generator_backup_required: bool = Field(
        default=False,
        description=(
            "Set True if this system will have a generator or grid backup. "
            "Excludes DC-only pump designs unless no AC-compatible pump meets requirements."
        )
    )

    # ── System controls ──────────────────────────────────────────────────────
    float_switch: bool = Field(
        default=False,
        description="Set True if a float switch is required for tank level control."
    )
    pressure_switch: bool = Field(
        default=False,
        description="Set True if a pressure switch is required."
    )
    pressure_switch_range: Optional[str] = Field(
        default=None,
        description=(
            "Pressure switch cut-in/cut-out range (e.g. '30/50 psi'). "
            "Required when pressure_switch is True."
        )
    )

    # ── Wire run ─────────────────────────────────────────────────────────────
    wire_distance_ft: Optional[float] = Field(
        default=None, gt=0,
        description=(
            "Approximate wire distance from solar array to downhole pump/motor (ft). "
            "Used to calculate recommended wire gauge (AWG)."
        )
    )

    # ── Calculation tuning ───────────────────────────────────────────────────
    minor_loss_factor: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Minor losses as fraction of calculated friction loss (0 = no minor losses)"
    )
    safety_factor: float = Field(
        default=1.0, ge=1.0, le=2.0,
        description="Multiplicative safety factor applied to final TDH (1.0 = no safety factor)"
    )
    pump_efficiency: Optional[float] = Field(
        default=None, ge=0.1, le=1.0,
        description="Pump efficiency override (0–1). Defaults to 0.45."
    )
    solar_coefficient: float = Field(
        default=1.0, ge=1.0, le=3.0,
        description="Array oversizing factor. 1.0 = size panels to meet required GPM exactly via pump curve.",
    )
    deadhead_watts: Optional[float] = Field(
        default=None, gt=0,
        description=(
            "Pump power draw at shutoff condition (W). "
            "Used for low-irradiance start sizing: deadhead_array = deadhead_watts / 0.35. "
            "Defaults to pump_input_power_w when not supplied."
        ),
    )
    pump_rated_flow_gpm: Optional[float] = Field(
        default=None, gt=0,
        description=(
            "Pump nameplate flow rate (GPM). When provided, friction loss is calculated "
            "at max(required_flow_gpm, pump_rated_flow_gpm) to size the pipe for full pump output."
        ),
    )
    panel_vmp_v: Optional[float] = Field(
        default=None, gt=0,
        description="Maximum power point voltage per panel (Vdc). Used to compute array Vmp for wire sizing."
    )
    panel_voc_v: Optional[float] = Field(
        default=None, gt=0,
        description="Open-circuit voltage per panel (Vdc). Used to verify max system voltage."
    )
    stc_efficiency_loss: float = Field(
        default=0.04, ge=0.0, le=0.30,
        description="Fractional efficiency loss from STC conditions used for panel COUNT sizing (4%). Achievable GPM display always uses 7.5% via _DISPLAY_STC_LOSS in ranking_service."
    )

    @model_validator(mode="after")
    def dynamic_level_must_exceed_static(self) -> "CalculationRequest":
        if self.dynamic_water_level_ft < self.static_water_level_ft:
            raise ValueError(
                "dynamic_water_level_ft must be ≥ static_water_level_ft "
                "(pumping level is always ≥ static water level)"
            )
        return self
        
    @model_validator(mode="after")
    def validate_solar_resource(self) -> "CalculationRequest":
        has_manual = self.peak_sun_hours is not None
        has_coords = self.latitude is not None and self.longitude is not None
        
        if not has_manual and not has_coords:
            raise ValueError(
                "Must provide either peak_sun_hours OR both latitude and longitude."
            )
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "static_water_level_ft": 60.0,
                "dynamic_water_level_ft": 80.0,
                "discharge_head_ft": 20.0,
                "required_flow_gpm": 30.0,
                "daily_water_demand_gallons": 1000.0,
                "nominal_pipe_diameter_in": 2.0,
                "pipe_length_ft": 300.0,
                "pipe_material": "PVC",
                "discharge_pressure_psi": 10.0,
                "peak_sun_hours": 5.5,
                "panel_wattage_w": 400.0,
            }
        }
    }


# ── Dedicated TDH request (US units — ft, GPM, PSI) ──────────────────────────

class TDHRequest(BaseModel):
    """
    Dedicated request for the TDH calculation engine.

    Works natively in US customary units (feet, GPM, PSI) — the standard
    unit system for pump TDH in North American engineering practice.

    Two operation modes
    -------------------
    **Computed** (default):
        TDH is derived from four components:

            TDH = (Pumping Level + Elevation Gain + Friction Loss + Pressure Head)
                  × safety_factor

        where  Pumping Level = static_water_level_ft + drawdown_ft
               Pressure Head = discharge_pressure_psi × 2.31  (ft)

    **Direct**:
        Provide ``direct_tdh_ft`` to override the calculation with a known TDH.
        Any other fields supplied are shown in the breakdown for reference but
        do not affect the final TDH value, and the safety factor is not applied.
    """

    # ── Mode override ─────────────────────────────────────────────────────────
    direct_tdh_ft: Optional[float] = Field(
        None, gt=0,
        description="Known TDH (ft). If provided, skips all component calculations."
    )

    # ── Water level ───────────────────────────────────────────────────────────
    static_water_level_ft: float = Field(
        0.0, ge=0,
        description="Depth from ground surface to static (resting) water level (ft)"
    )
    drawdown_ft: float = Field(
        0.0, ge=0,
        description="Pumping drawdown — extra depth depression under pump load (ft)"
    )
    # → Pumping Level = static_water_level_ft + drawdown_ft

    # ── Elevation gain ────────────────────────────────────────────────────────
    elevation_gain_ft: float = Field(
        0.0, ge=0,
        description="Vertical rise from pump discharge to delivery point (ft)"
    )

    # ── Pressure head ─────────────────────────────────────────────────────────
    discharge_pressure_psi: float = Field(
        0.0, ge=0,
        description="Required delivery pressure (PSI). Adds PSI × 2.31 ft to TDH."
    )

    # ── Friction loss (choose one) ────────────────────────────────────────────
    friction_loss_ft: Optional[float] = Field(
        None, ge=0,
        description="Pre-computed friction loss (ft). Skips pipe parameter lookup."
    )

    # OR compute from pipe parameters:
    flow_gpm: Optional[float] = Field(
        None, gt=0,
        description="Flow rate (US gal/min). Required to compute friction from pipe data."
    )
    pipe_material: Optional[PipeMaterial] = Field(
        None,
        description="Pipe material. Required when computing friction from pipe params."
    )
    nominal_diameter_in: Optional[float] = Field(
        None, gt=0,
        description="Nominal pipe diameter (inches). Required for friction lookup."
    )
    pipe_length_ft: Optional[float] = Field(
        None, gt=0,
        description="Total pipe run length (ft). Required for friction computation."
    )
    fittings_equivalent_length_ft: float = Field(
        0.0, ge=0,
        description="Equivalent pipe length for all fittings, valves, bends (ft)."
    )

    # ── Calculation tuning ────────────────────────────────────────────────────
    minor_loss_factor: float = Field(
        0.10, ge=0.0, le=1.0,
        description="Additional minor losses as fraction of calculated friction loss."
    )
    safety_factor: float = Field(
        1.15, ge=1.0, le=2.0,
        description="Multiplier applied to final TDH subtotal (ignored in direct mode)."
    )

    @model_validator(mode="after")
    def validate_mode_inputs(self) -> "TDHRequest":
        if self.direct_tdh_ft is not None:
            return self  # direct mode — no further validation required

        # Computed mode: at least one head component must be non-zero
        has_head = (
            self.static_water_level_ft > 0
            or self.drawdown_ft > 0
            or self.elevation_gain_ft > 0
            or self.discharge_pressure_psi > 0
        )
        if not has_head and self.friction_loss_ft is None:
            raise ValueError(
                "In computed mode, provide at least one head component "
                "(static_water_level_ft, drawdown_ft, elevation_gain_ft, "
                "discharge_pressure_psi) or a friction_loss_ft."
            )

        # Validate pipe params: all-or-nothing
        pipe_fields: List[tuple[str, object]] = [
            ("flow_gpm",            self.flow_gpm),
            ("pipe_material",       self.pipe_material),
            ("nominal_diameter_in", self.nominal_diameter_in),
            ("pipe_length_ft",      self.pipe_length_ft),
        ]
        provided = [name for name, val in pipe_fields if val is not None]
        missing  = [name for name, val in pipe_fields if val is None]

        if provided and missing:
            raise ValueError(
                f"Incomplete pipe parameters for friction computation. "
                f"Provided: {provided}. Missing: {missing}. "
                "Supply all four or use friction_loss_ft instead."
            )

        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "static_water_level_ft": 60.0,
                    "drawdown_ft": 20.0,
                    "elevation_gain_ft": 20.0,
                    "discharge_pressure_psi": 10.0,
                    "flow_gpm": 30.0,
                    "pipe_material": "PVC",
                    "nominal_diameter_in": 2.0,
                    "pipe_length_ft": 300.0,
                    "fittings_equivalent_length_ft": 30.0,
                    "safety_factor": 1.15,
                },
                {
                    "static_water_level_ft": 80.0,
                    "drawdown_ft": 15.0,
                    "elevation_gain_ft": 10.0,
                    "friction_loss_ft": 12.5,
                    "discharge_pressure_psi": 5.0,
                },
                {
                    "direct_tdh_ft": 150.0,
                    "static_water_level_ft": 60.0,
                    "drawdown_ft": 20.0,
                    "elevation_gain_ft": 20.0,
                    "discharge_pressure_psi": 10.0,
                }
            ]
        }
    }
