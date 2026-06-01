"""
Friction loss calculation service — tabular lookup with linear interpolation.

Lookup path
-----------
1. Map the caller's pipe material to a table key ("PVC" or "Steel").
2. Convert the nominal diameter to the nearest standard Schedule 40 size.
3. Retrieve the (gpm, loss_per_100ft) curve from the repository.
4. Interpolate loss_per_100ft at the exact GPM using piecewise-linear
   interpolation (``interpolation.interpolate_friction_loss``).
5. Apply the formula:
       pipe_friction      = (pipe_length_ft / 100) * loss_per_100ft
       fittings_friction  = (fittings_eq_length_ft / 100) * loss_per_100ft
       total_friction     = pipe_friction + fittings_friction

Unit system
-----------
The service works natively in US customary units (GPM, inches, feet).

Pipe material mapping
---------------------
Any ``PipeMaterial`` enum value (or raw string) is mapped to the nearest
available table:
    PVC, HDPE, Copper, Asbestos Cement  → PVC   table (C ≈ 150)
    Steel, Galvanized Steel, Cast Iron,
    Ductile Iron, Concrete              → Steel table (C ≈ 120)

This is an engineering approximation.  When more precise results are
required, add a dedicated table for the exact material.
"""

import logging
from dataclasses import dataclass
from typing import Dict

from ..repositories.friction_repository import (
    MATERIAL_PVC,
    MATERIAL_STEEL,
    FrictionRepository,
)
from ..services.interpolation import interpolate_friction_loss
from ..utils.exceptions import CalculationError, DataNotFoundError

logger = logging.getLogger(__name__)


# ── Material → table key mapping ──────────────────────────────────────────────

_MATERIAL_TABLE: Dict[str, str] = {
    # PVC-equivalent (C ≈ 150)
    "PVC":              MATERIAL_PVC,
    "HDPE":             MATERIAL_PVC,
    "Copper":           MATERIAL_PVC,
    "Asbestos Cement":  MATERIAL_PVC,
    # Steel-equivalent (C ≈ 120)
    "Steel":            MATERIAL_STEEL,
    "Galvanized Steel": MATERIAL_STEEL,
    "Cast Iron (New)":  MATERIAL_STEEL,
    "Cast Iron (Old)":  MATERIAL_STEEL,
    "Ductile Iron":     MATERIAL_STEEL,
    "Concrete":         MATERIAL_STEEL,
}

# Hazen-Williams C coefficients per table key (used when GPM is outside table range)
_HW_C: Dict[str, float] = {
    MATERIAL_PVC:   150.0,
    MATERIAL_STEEL: 120.0,
}


def _hazen_williams_loss_per_100ft(gpm: float, c_coeff: float, id_in: float) -> float:
    """Return friction head loss (ft) per 100 ft using Hazen-Williams.

    Formula: h_f/100 = 0.2083 × (100/C)^1.852 × Q^1.852 / D^4.8704
    where Q is in US GPM and D is internal pipe diameter in inches.
    """
    return 0.2083 * ((100.0 / c_coeff) ** 1.852) * (gpm ** 1.852) / (id_in ** 4.8704)


# ── Schedule 40 internal diameters (inches) keyed by nominal size ─────────────

_SCH40_ID_IN: dict[float, float] = {
    0.5:  0.622,
    0.75: 0.824,
    1.0:  1.049,
    1.25: 1.380,
    1.5:  1.610,
    2.0:  2.067,
    2.5:  2.469,
    3.0:  3.068,
    4.0:  4.026,
    6.0:  6.065,
}


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FrictionLossResult:
    """
    Complete result of a friction-loss calculation.

    All ``_ft`` fields are in US feet (head loss).
    """
    # Resolved inputs
    material_key: str           # "PVC" or "Steel"
    nominal_diameter_in: float  # nearest standard size used for lookup
    gpm: float

    # Pipe geometry
    pipe_length_ft: float
    fittings_equivalent_length_ft: float
    total_equivalent_length_ft: float

    # Lookup result
    loss_per_100ft: float       # ft head loss per 100 ft of pipe at this GPM

    # Calculated losses (ft)
    pipe_friction_loss_ft: float
    fittings_friction_loss_ft: float
    total_friction_loss_ft: float


# ── Service ───────────────────────────────────────────────────────────────────

class FrictionService:
    """
    Computes pipe friction loss via dataset lookup and linear interpolation.

    Args:
        friction_repo: Loaded ``FrictionRepository`` instance.
    """

    def __init__(self, friction_repo: FrictionRepository) -> None:
        self._repo = friction_repo

    # ── Primary interface (US units) ──────────────────────────────────────────

    def calculate(
        self,
        material: str,
        nominal_diameter_in: float,
        gpm: float,
        pipe_length_ft: float,
        fittings_equivalent_length_ft: float = 0.0,
    ) -> FrictionLossResult:
        """
        Calculate friction head loss for a pipe section.

        Args:
            material:                     Pipe material string or
                                          ``PipeMaterial.value``.
            nominal_diameter_in:          Nominal pipe size (inches).
                                          Snapped to nearest standard size.
            gpm:                          Flow rate (US gal/min).
            pipe_length_ft:               Actual pipe length (ft).
            fittings_equivalent_length_ft: Equivalent straight-pipe length
                                          that represents all fittings,
                                          valves, and bends (ft).

        Returns:
            :class:`FrictionLossResult` with per-component and total losses.

        Raises:
            CalculationError:  If inputs are out of physically valid range.
            DataNotFoundError: If material or diameter is not in the dataset.

        Formula:
            total_equivalent_length = pipe_length + fittings_equivalent_length
            loss_per_100ft          = interpolated from table at (material, diam, gpm)
            pipe_friction           = (pipe_length          / 100) * loss_per_100ft
            fittings_friction       = (fittings_equiv_length / 100) * loss_per_100ft
            total_friction          = pipe_friction + fittings_friction
        """
        if gpm <= 0:
            raise CalculationError(f"GPM must be positive; got {gpm}")
        if pipe_length_ft < 0:
            raise CalculationError(f"pipe_length_ft must be ≥ 0; got {pipe_length_ft}")
        if fittings_equivalent_length_ft < 0:
            raise CalculationError(
                f"fittings_equivalent_length_ft must be ≥ 0; got {fittings_equivalent_length_ft}"
            )

        material_key = self._resolve_material(material)
        snapped_diam = self._repo.nearest_nominal_diameter(nominal_diameter_in)

        if snapped_diam != nominal_diameter_in:
            logger.debug(
                "Diameter %.3f\" snapped to nearest nominal %.2f\"",
                nominal_diameter_in, snapped_diam,
            )

        data_points = self._repo.get_data_points(material_key, snapped_diam)
        min_gpm = data_points[0][0]
        max_gpm = data_points[-1][0]

        # Allow mild extrapolation (≤20% beyond table range); beyond that use H-W formula
        extrapolate = False
        use_hw = False
        if gpm < min_gpm or gpm > max_gpm:
            overshoot = max(
                (min_gpm - gpm) / min_gpm if gpm < min_gpm else 0,
                (gpm - max_gpm) / max_gpm if gpm > max_gpm else 0,
            )
            if overshoot > 0.20:
                use_hw = True
                logger.warning(
                    "GPM %.1f is %.0f%% outside table range [%.1f, %.1f] for %s %s\" — "
                    "falling back to Hazen-Williams formula",
                    gpm, overshoot * 100, min_gpm, max_gpm, material_key, snapped_diam,
                )
            else:
                extrapolate = True
                logger.warning(
                    "GPM %.1f outside table range [%.1f, %.1f] for %s %s\" — "
                    "using linear extrapolation (accuracy reduced)",
                    gpm, min_gpm, max_gpm, material_key, snapped_diam,
                )

        if use_hw:
            id_in = _SCH40_ID_IN.get(snapped_diam, snapped_diam)
            c_coeff = _HW_C.get(material_key, 120.0)
            loss_per_100ft = _hazen_williams_loss_per_100ft(gpm, c_coeff, id_in)
        else:
            # Snap up to the next available table breakpoint (ceiling lookup).
            # TBS sizes pipe friction at the next standard GPM entry ≥ required
            # flow — a conservative table-lookup convention, not interpolation.
            gpm_for_lookup = gpm
            if not extrapolate:
                table_gpms = [pt[0] for pt in data_points]
                ceiling = next((g for g in table_gpms if g >= gpm), table_gpms[-1])
                gpm_for_lookup = ceiling
            loss_per_100ft = interpolate_friction_loss(gpm_for_lookup, data_points, extrapolate=extrapolate)

        total_equiv_length = pipe_length_ft + fittings_equivalent_length_ft
        pipe_friction      = (pipe_length_ft                 / 100.0) * loss_per_100ft
        fittings_friction  = (fittings_equivalent_length_ft  / 100.0) * loss_per_100ft
        total_friction     = pipe_friction + fittings_friction

        logger.info(
            "Friction | %s %.1f\" | %.1f GPM | %.1f ft pipe + %.1f ft fittings "
            "= %.1f ft equiv | %.4f ft/100ft | total=%.4f ft",
            material_key, snapped_diam, gpm,
            pipe_length_ft, fittings_equivalent_length_ft, total_equiv_length,
            loss_per_100ft, total_friction,
        )

        return FrictionLossResult(
            material_key=material_key,
            nominal_diameter_in=snapped_diam,
            gpm=gpm,
            pipe_length_ft=pipe_length_ft,
            fittings_equivalent_length_ft=fittings_equivalent_length_ft,
            total_equivalent_length_ft=round(total_equiv_length, 3),
            loss_per_100ft=round(loss_per_100ft, 4),
            pipe_friction_loss_ft=round(pipe_friction, 4),
            fittings_friction_loss_ft=round(fittings_friction, 4),
            total_friction_loss_ft=round(total_friction, 4),
        )

    # ── Pipe velocity (imperial) ──────────────────────────────────────────────

    def calculate_pipe_velocity(
        self,
        flow_gpm: float,
        nominal_diameter_in: float,
    ) -> float:
        """
        Return mean flow velocity in the pipe (ft/s).

        Uses Schedule 40 internal diameter for the given nominal size.
        Formula: V (ft/s) = Q_gpm / (2.448 × ID_in²)

        Args:
            flow_gpm:             Flow rate (US gal/min).
            nominal_diameter_in:  Nominal pipe size (inches).

        Returns:
            Velocity in ft/s, rounded to 3 decimal places.
        """
        id_in = _SCH40_ID_IN.get(nominal_diameter_in, nominal_diameter_in)
        velocity_fps = flow_gpm / (2.448 * id_in ** 2)
        logger.debug(
            "Pipe velocity: %.3f ft/s | D_nom=%.2f in (ID=%.3f in), Q=%.1f GPM",
            velocity_fps, nominal_diameter_in, id_in, flow_gpm,
        )
        return round(velocity_fps, 3)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _resolve_material(material: str) -> str:
        """
        Map a pipe material name (or PipeMaterial enum value) to a table key.

        Returns:
            "PVC" or "Steel".

        Raises:
            DataNotFoundError: If the material cannot be mapped.
        """
        key = _MATERIAL_TABLE.get(material)
        if key is None:
            available = ", ".join(sorted(_MATERIAL_TABLE.keys()))
            raise DataNotFoundError(
                f"Material '{material}' is not mapped to a friction table. "
                f"Supported materials: {available}"
            )
        return key
