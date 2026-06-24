"""
Pump domain models.

PumpType     — classification enum used for catalog filtering and compatibility checks.
VoltageClass — AC / DC segregation for solar controller compatibility rules.
Pump         — core catalog record (loaded from pump_catalog.csv).

Design notes
------------
- No performance data lives here.  Head/flow/wattage relationships are held
  exclusively by PerformanceCurve in the repository layer.
- ``voltage_class`` is derived automatically from ``voltage_range`` so the rest
  of the system can apply AC/DC compatibility rules without string parsing.
- All fields that require real manufacturer data are typed Optional[...] and
  default to None so that partially-filled catalogs load without crashing.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class PumpType(str, Enum):
    SUBMERSIBLE            = "submersible"
    SURFACE                = "surface"
    CENTRIFUGAL            = "centrifugal"
    POSITIVE_DISPLACEMENT  = "positive_displacement"
    HELICAL_ROTOR          = "helical_rotor"


class VoltageClass(str, Enum):
    """
    High-level voltage classification for AC/DC compatibility checks.

    DC — typically 12 V / 24 V / 48 V / 96 V / 300 V MPPT systems.
    AC — single-phase or three-phase mains or inverter-fed systems.
    HYBRID — pump accepts both (e.g. SQFlex with controller that takes PV or AC).
    UNKNOWN — voltage range string could not be parsed; operator must verify.
    """
    DC      = "dc"
    AC      = "ac"
    HYBRID  = "hybrid"
    UNKNOWN = "unknown"


def _infer_voltage_class(voltage_range: str) -> VoltageClass:
    """
    Heuristic: classify a free-text voltage_range into VoltageClass.

    Rules (applied in order):
      - Contains "ac" (case-insensitive)                        → HYBRID
      - Contains "-" and max voltage ≤ 300 V
        with both values < 300 V and no "v ac" pattern         → DC
      - Single value ≥ 110 V                                   → AC
      - Otherwise                                              → UNKNOWN

    Engineers: if the heuristic is wrong, add ``voltage_class`` explicitly
    to the catalog CSV and it will override this derivation.
    """
    v = voltage_range.strip().lower()
    if "ac" in v:
        return VoltageClass.HYBRID

    # Extract numeric parts
    import re
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", v)]
    if not nums:
        return VoltageClass.UNKNOWN

    max_v = max(nums)
    min_v = min(nums)

    # MPPT-style DC range (e.g. "24-300" common on Grundfos SQFlex)
    if min_v <= 96 and max_v <= 300 and len(nums) >= 2:
        return VoltageClass.DC

    # Typical AC nominal voltages
    if max_v in {110, 115, 120, 208, 220, 230, 240, 380, 400, 415, 460, 480}:
        return VoltageClass.AC

    # Single low-voltage value → DC
    if max_v <= 96:
        return VoltageClass.DC

    return VoltageClass.UNKNOWN


class Pump(BaseModel):
    """
    Pump catalog record.

    Populated from ``pump_catalog.csv`` at startup.  All performance data
    (head/flow/wattage curves) is held separately in ``PerformanceCurve``
    objects loaded by ``PumpRepository``.
    """

    # ── Identity ─────────────────────────────────────────────────────────────
    pump_id: str = Field(..., description="Unique pump identifier (e.g. 'P001')")
    brand: str   = Field(..., description="Manufacturer name")
    model: str   = Field(..., description="Model designation")
    pump_type: PumpType = Field(..., description="Pump classification")

    # ── Envelope (catalog bounds — used for quick pre-filter only) ────────────
    min_flow_gpm:   float = Field(..., ge=0, description="Minimum operating flow (GPM)")
    max_flow_gpm:   float = Field(..., gt=0, description="Maximum operating flow (GPM)")
    rated_flow_gpm: Optional[float] = Field(None, ge=0, description="Nameplate rated flow (GPM) — used for pipe friction sizing")
    min_head_ft:  float = Field(..., ge=0, description="Minimum operating head (ft)")
    max_head_ft:  float = Field(..., gt=0, description="Maximum operating head (ft)")

    # ── Electrical ────────────────────────────────────────────────────────────
    rated_power_w: float  = Field(..., gt=0,  description="Rated input power (W)")
    voltage_range: str    = Field(...,         description="Operating voltage range (e.g. '24-300 V')")
    voltage_class: VoltageClass = Field(
        VoltageClass.UNKNOWN,
        description=(
            "AC/DC classification derived from voltage_range. "
            "Override by supplying 'voltage_class' column in catalog CSV."
        ),
    )

    # ── Performance (catalog-level — BEP efficiency from datasheet) ───────────
    efficiency_percent: float = Field(
        ..., ge=0, le=100,
        description="Pump efficiency at Best Efficiency Point (%)",
    )

    # ── AC/DC compatibility metadata ──────────────────────────────────────────
    requires_inverter: bool = Field(
        False,
        description=(
            "True if this pump requires an AC inverter when driven by a PV array. "
            "False for native DC/MPPT pumps."
        ),
    )
    mppt_compatible: bool = Field(
        False,
        description="True if the pump accepts a direct MPPT solar controller input.",
    )

    # ── Physical compatibility ────────────────────────────────────────────────
    min_casing_diameter_in: float = Field(
        default=4.0,
        description=(
            "Minimum well casing inner diameter required to fit this pump (inches). "
            "Typical values: 3.5, 4.0, 4.5, 5.0. "
            "Pumps are excluded when the user's casing is smaller than this value."
        )
    )

    # ── TBS wire sizing cap ───────────────────────────────────────────────────
    max_watts: Optional[float] = Field(
        None, gt=0,
        description="Maximum input power cap for TBS wire sizing formula (W). Caps System_Power = MIN(array_watts, max_watts)."
    )

    # ── System category (TBS prioritization) ─────────────────────────────────
    pump_category: Optional[str] = Field(
        None,
        description=(
            "TBS system category: A=Stacked Impeller + External Drive (AC/DC), "
            "B=Stacked Impeller + Internal Drive, C=Helical Rotor."
        ),
    )

    # ── Commercial ────────────────────────────────────────────────────────────
    price_usd:   Optional[float] = Field(None, ge=0, description="Indicative price (USD)")
    description: Optional[str]   = Field(None,        description="Free-text notes")

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _derive_voltage_class(self) -> "Pump":
        """Auto-fill voltage_class if it was not explicitly set in the catalog."""
        if self.voltage_class == VoltageClass.UNKNOWN:
            object.__setattr__(self, "voltage_class", _infer_voltage_class(self.voltage_range))
        return self
