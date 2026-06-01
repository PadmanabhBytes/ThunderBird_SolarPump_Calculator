"""
Total Dynamic Head (TDH) calculation service.

Formula (four-term, US customary)
----------------------------------
    TDH = (Pumping Level + Elevation Gain + Friction Loss + Pressure Head)
          × safety_factor

where:
    Pumping Level  = static_water_level_ft + drawdown_ft
    Pressure Head  = discharge_pressure_psi × 2.31   (ft of water)
    Friction Loss  = tabular dataset lookup via FrictionService
                     (or caller-supplied value)

Two operation modes
-------------------
    computed — TDH derived from individual components (default)
    direct   — caller supplies a known TDH; service wraps it in the
               structured breakdown for display purposes

Unit strategy
-------------
This service works in US customary units internally (ft / GPM / PSI) because:
  • The four-term formula is native US (PSI × 2.31 = ft)
  • Friction dataset is in ft/100ft and GPM
  • TDH for pump selection is universally quoted in feet

Every TDHBreakdown field is duplicated in metres so the rest of the
SI-unit system (solar sizing, pump evaluation) can consume the result
without conversion.

Backward-compatible ``calculate()`` method
------------------------------------------
The original ``calculate(CalculationRequest)`` signature is preserved so
the full recommendation pipeline (controller → solar → pump eval) needs
no changes.  It now also includes the pressure head term.
"""

import logging
from typing import Optional, Tuple

from ..models.calculation_request import CalculationRequest, TDHRequest
from ..models.calculation_response import (
    FrictionDetail,
    HeadBreakdown,
    PipeVelocityInfo,
    TDHBreakdown,
    TDHResult,
)
from ..services.friction_service import FrictionLossResult, FrictionService

logger = logging.getLogger(__name__)


# ── Unit conversion constants ─────────────────────────────────────────────────

_PSI_TO_FT: float = 2.31    # 1 PSI = 2.31 ft of water head  (exact per ASPE)
_FT_TO_M:   float = 0.3048  # 1 ft  = 0.3048 m               (exact) — used by TDHBreakdown


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ft_to_m(ft: float, ndigits: int = 4) -> float:
    return round(ft * _FT_TO_M, ndigits)

def _r(value: float, ndigits: int = 3) -> float:
    return round(value, ndigits)


# ── Service ───────────────────────────────────────────────────────────────────

class TDHService:
    """
    TDH calculation engine.

    Args:
        friction_service: Loaded ``FrictionService`` instance.
    """

    def __init__(self, friction_service: FrictionService) -> None:
        self._friction = friction_service

    # ── Public: dedicated TDH endpoint ───────────────────────────────────────

    def compute(self, request: TDHRequest) -> TDHResult:
        """
        Main entry point for the dedicated TDH endpoint.

        Routes to ``_computed_mode`` or ``_direct_mode`` based on whether
        ``request.direct_tdh_ft`` is provided.

        Args:
            request: Validated ``TDHRequest``.

        Returns:
            ``TDHResult`` with complete breakdown and optional pipe velocity
            and friction audit detail.
        """
        if request.direct_tdh_ft is not None:
            logger.info("TDH direct mode: %.2f ft provided by caller", request.direct_tdh_ft)
            return self._direct_mode(request)

        logger.info("TDH computed mode: deriving from components")
        return self._computed_mode(request)

    # ── Public: backward-compatible pipeline method ───────────────────────────

    def calculate(
        self,
        request: CalculationRequest,
        max_velocity_fps: float = 10.0,
    ) -> Tuple[HeadBreakdown, PipeVelocityInfo]:
        """
        Calculate TDH for the full recommendation pipeline.

        Accepts a ``CalculationRequest`` (imperial units) and returns the
        ``HeadBreakdown`` + ``PipeVelocityInfo`` pair consumed by the
        recommendation controller.  Includes the pressure head term if
        ``request.discharge_pressure_psi`` is non-zero.

        Returns:
            (HeadBreakdown, PipeVelocityInfo) — all values in feet / fps.
        """
        # ── Static lift ───────────────────────────────────────────────────────
        # dynamic_water_level_ft = pumping level (static + drawdown)
        static_head_ft = request.dynamic_water_level_ft + request.discharge_head_ft

        # ── Friction loss ─────────────────────────────────────────────────────
        # When a pump rated flow is specified, size friction at the larger of
        # required vs. rated flow (ensures pipe can handle full pump output).
        friction_gpm = max(
            request.required_flow_gpm,
            request.pump_rated_flow_gpm if request.pump_rated_flow_gpm else 0.0,
        )
        friction_result = self._friction.calculate(
            material=request.pipe_material.value,
            nominal_diameter_in=request.nominal_pipe_diameter_in,
            gpm=friction_gpm,
            pipe_length_ft=request.pipe_length_ft,
        )
        friction_loss_ft = friction_result.total_friction_loss_ft

        # ── Parametric minor losses ───────────────────────────────────────────
        minor_losses_ft = _r(friction_loss_ft * request.minor_loss_factor)

        # ── Pressure head ─────────────────────────────────────────────────────
        pressure_head_ft = _r(request.discharge_pressure_psi * _PSI_TO_FT)

        # ── TDH ───────────────────────────────────────────────────────────────
        subtotal_ft = _r(static_head_ft + friction_loss_ft + minor_losses_ft + pressure_head_ft)
        tdh_ft      = _r(subtotal_ft * request.safety_factor)

        logger.info(
            "TDH pipeline | static=%.3f ft  friction=%.4f ft  minor=%.4f ft  "
            "pressure=%.4f ft  subtotal=%.3f ft  TDH=%.3f ft (SF=%.2f) | "
            "%s %.1f\" @ %.2f GPM  loss=%.4f ft/100ft",
            static_head_ft, friction_loss_ft, minor_losses_ft, pressure_head_ft,
            subtotal_ft, tdh_ft, request.safety_factor,
            friction_result.material_key,
            friction_result.nominal_diameter_in,
            friction_result.gpm,
            friction_result.loss_per_100ft,
        )

        head_breakdown = HeadBreakdown(
            static_head_ft=_r(static_head_ft),
            friction_loss_ft=round(friction_loss_ft, 4),
            minor_losses_ft=minor_losses_ft,
            pressure_head_ft=pressure_head_ft,
            subtotal_ft=subtotal_ft,
            total_dynamic_head_ft=tdh_ft,
            safety_factor_applied=request.safety_factor,
        )

        velocity_fps = self._friction.calculate_pipe_velocity(
            flow_gpm=request.required_flow_gpm,
            nominal_diameter_in=request.nominal_pipe_diameter_in,
        )
        pipe_velocity = PipeVelocityInfo(
            velocity_fps=velocity_fps,
            is_within_limit=velocity_fps <= max_velocity_fps,
            recommended_max_fps=max_velocity_fps,
        )

        return head_breakdown, pipe_velocity

    # ── Private: computed mode ────────────────────────────────────────────────

    def _computed_mode(self, request: TDHRequest) -> TDHResult:
        """
        Derive every TDH component from the request's inputs.

        Steps
        -----
        1. Pumping Level  = static_water_level_ft + drawdown_ft
        2. Pressure Head  = discharge_pressure_psi × 2.31
        3. Friction Loss  — from dataset lookup OR caller-supplied value
        4. Minor Losses   = minor_loss_factor × pipe_friction_loss
        5. Static Lift    = Pumping Level + Elevation Gain
        6. Subtotal       = Static Lift + Total Friction + Pressure Head
        7. TDH            = Subtotal × safety_factor
        """
        warnings: list[str] = []

        # ── Water level ───────────────────────────────────────────────────────
        static_wl_ft     = request.static_water_level_ft
        drawdown_ft      = request.drawdown_ft
        pumping_level_ft = _r(static_wl_ft + drawdown_ft)

        # ── Elevation gain ────────────────────────────────────────────────────
        elevation_gain_ft = request.elevation_gain_ft

        # ── Pressure head  (PSI × 2.31 ft) ───────────────────────────────────
        pressure_head_ft = _r(request.discharge_pressure_psi * _PSI_TO_FT)

        # ── Friction loss ─────────────────────────────────────────────────────
        pipe_friction_ft, friction_detail_model, pipe_velocity = self._resolve_friction(
            request, warnings
        )

        # ── Minor losses ──────────────────────────────────────────────────────
        minor_losses_ft   = _r(pipe_friction_ft * request.minor_loss_factor)
        total_friction_ft = _r(pipe_friction_ft + minor_losses_ft)

        # ── Aggregates ────────────────────────────────────────────────────────
        static_lift_ft = _r(pumping_level_ft + elevation_gain_ft)
        subtotal_ft    = _r(static_lift_ft + total_friction_ft + pressure_head_ft)
        tdh_ft         = _r(subtotal_ft * request.safety_factor)

        logger.info(
            "TDH computed | static_wl=%.2f ft  drawdown=%.2f ft  "
            "pumping_lvl=%.2f ft  elev=%.2f ft  pressure=%.3f ft  "
            "friction=%.3f ft  minor=%.3f ft  subtotal=%.3f ft  "
            "TDH=%.3f ft (%.3f m)  SF=%.2f",
            static_wl_ft, drawdown_ft, pumping_level_ft, elevation_gain_ft,
            pressure_head_ft, pipe_friction_ft, minor_losses_ft,
            subtotal_ft, tdh_ft, _ft_to_m(tdh_ft), request.safety_factor,
        )

        breakdown = self._build_breakdown(
            static_wl_ft=static_wl_ft,
            drawdown_ft=drawdown_ft,
            pumping_level_ft=pumping_level_ft,
            elevation_gain_ft=elevation_gain_ft,
            discharge_pressure_psi=request.discharge_pressure_psi,
            pressure_head_ft=pressure_head_ft,
            pipe_friction_ft=pipe_friction_ft,
            minor_losses_ft=minor_losses_ft,
            total_friction_ft=total_friction_ft,
            static_lift_ft=static_lift_ft,
            subtotal_ft=subtotal_ft,
            safety_factor=request.safety_factor,
            tdh_ft=tdh_ft,
            is_direct=False,
        )

        return TDHResult(
            breakdown=breakdown,
            pipe_velocity=pipe_velocity,
            friction_detail=friction_detail_model,
            warnings=warnings,
        )

    # ── Private: direct mode ──────────────────────────────────────────────────

    def _direct_mode(self, request: TDHRequest) -> TDHResult:
        """
        Wrap a caller-supplied TDH in the full breakdown structure.

        Known components (static WL, drawdown, elevation, pressure) are
        displayed as provided.  Friction is shown as the residual between
        the supplied TDH and the sum of the other known components.
        The safety factor is NOT applied — the supplied TDH is already final.
        """
        warnings: list[str] = [
            "TDH provided directly. Safety factor is not applied.",
        ]

        tdh_ft = request.direct_tdh_ft  # type: ignore[assignment]

        static_wl_ft      = request.static_water_level_ft
        drawdown_ft       = request.drawdown_ft
        pumping_level_ft  = _r(static_wl_ft + drawdown_ft)
        elevation_gain_ft = request.elevation_gain_ft
        pressure_head_ft  = _r(request.discharge_pressure_psi * _PSI_TO_FT)

        static_lift_ft    = _r(pumping_level_ft + elevation_gain_ft)

        # Derive friction as whatever the known components don't account for
        known_non_friction_ft = _r(static_lift_ft + pressure_head_ft)
        implied_total_friction_ft = _r(max(0.0, tdh_ft - known_non_friction_ft))

        # Split implied friction into pipe portion and minor losses
        # minor_losses = factor * pipe_friction  →  total = pipe * (1 + factor)
        mf = request.minor_loss_factor
        pipe_friction_ft = _r(implied_total_friction_ft / (1.0 + mf))
        minor_losses_ft  = _r(implied_total_friction_ft - pipe_friction_ft)

        if implied_total_friction_ft > 0:
            warnings.append(
                f"Friction residual of {implied_total_friction_ft:.2f} ft inferred "
                "from the difference between provided TDH and known head components."
            )

        if known_non_friction_ft > tdh_ft:
            warnings.append(
                f"Sum of known non-friction components ({known_non_friction_ft:.2f} ft) "
                f"exceeds the provided TDH ({tdh_ft:.2f} ft). "
                "Verify your inputs."
            )

        # In direct mode subtotal = TDH (no safety factor applied)
        subtotal_ft = tdh_ft

        breakdown = self._build_breakdown(
            static_wl_ft=static_wl_ft,
            drawdown_ft=drawdown_ft,
            pumping_level_ft=pumping_level_ft,
            elevation_gain_ft=elevation_gain_ft,
            discharge_pressure_psi=request.discharge_pressure_psi,
            pressure_head_ft=pressure_head_ft,
            pipe_friction_ft=pipe_friction_ft,
            minor_losses_ft=minor_losses_ft,
            total_friction_ft=implied_total_friction_ft,
            static_lift_ft=static_lift_ft,
            subtotal_ft=subtotal_ft,
            safety_factor=1.0,   # not applied in direct mode
            tdh_ft=tdh_ft,
            is_direct=True,
        )

        return TDHResult(
            breakdown=breakdown,
            pipe_velocity=None,
            friction_detail=None,
            warnings=warnings,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_friction(
        self,
        request: TDHRequest,
        warnings: list[str],
    ) -> tuple[float, Optional[FrictionDetail], Optional[PipeVelocityInfo]]:
        """
        Determine pipe friction head loss (ft) from the request.

        Priority:
            1. ``friction_loss_ft`` — use directly if provided.
            2. Pipe parameters (flow_gpm + material + diameter + length) — look up
               from the friction dataset and interpolate.
            3. Neither provided — return 0.0 with a warning.

        Returns:
            (pipe_friction_loss_ft, friction_detail_or_None, pipe_velocity_or_None)
        """
        # 1. Direct friction value
        if request.friction_loss_ft is not None:
            warnings.append("Friction loss supplied directly; no pipe dataset lookup performed.")
            return request.friction_loss_ft, None, None

        # 2. Compute from pipe parameters
        if (request.flow_gpm is not None
                and request.nominal_diameter_in is not None
                and request.pipe_length_ft is not None
                and request.pipe_material is not None):

            fr: FrictionLossResult = self._friction.calculate(
                material=request.pipe_material.value,
                nominal_diameter_in=request.nominal_diameter_in,
                gpm=request.flow_gpm,
                pipe_length_ft=request.pipe_length_ft,
                fittings_equivalent_length_ft=request.fittings_equivalent_length_ft,
            )

            friction_detail = FrictionDetail(
                material_table=fr.material_key,
                nominal_diameter_in=fr.nominal_diameter_in,
                gpm=fr.gpm,
                loss_per_100ft=fr.loss_per_100ft,
                pipe_length_ft=fr.pipe_length_ft,
                fittings_equivalent_length_ft=fr.fittings_equivalent_length_ft,
                total_equivalent_length_ft=fr.total_equivalent_length_ft,
                pipe_friction_loss_ft=fr.pipe_friction_loss_ft,
                fittings_friction_loss_ft=fr.fittings_friction_loss_ft,
                total_friction_loss_ft=fr.total_friction_loss_ft,
            )

            # Pipe velocity using Schedule 40 internal diameter
            velocity_fps = self._friction.calculate_pipe_velocity(
                flow_gpm=request.flow_gpm,
                nominal_diameter_in=fr.nominal_diameter_in,
            )

            pipe_velocity = PipeVelocityInfo(
                velocity_fps=velocity_fps,
                is_within_limit=velocity_fps <= 10.0,
                recommended_max_fps=10.0,
            )

            return fr.total_friction_loss_ft, friction_detail, pipe_velocity

        # 3. No friction data available
        warnings.append(
            "No friction loss provided and no pipe parameters supplied. "
            "Friction head contribution is 0 ft."
        )
        return 0.0, None, None

    @staticmethod
    def _build_breakdown(
        *,
        static_wl_ft: float,
        drawdown_ft: float,
        pumping_level_ft: float,
        elevation_gain_ft: float,
        discharge_pressure_psi: float,
        pressure_head_ft: float,
        pipe_friction_ft: float,
        minor_losses_ft: float,
        total_friction_ft: float,
        static_lift_ft: float,
        subtotal_ft: float,
        safety_factor: float,
        tdh_ft: float,
        is_direct: bool,
    ) -> TDHBreakdown:
        """Construct a fully-populated TDHBreakdown from pre-computed scalars."""
        return TDHBreakdown(
            # Water source
            static_water_level_ft=_r(static_wl_ft),
            static_water_level_m=_ft_to_m(static_wl_ft),
            drawdown_ft=_r(drawdown_ft),
            drawdown_m=_ft_to_m(drawdown_ft),
            pumping_level_ft=_r(pumping_level_ft),
            pumping_level_m=_ft_to_m(pumping_level_ft),
            # Elevation
            elevation_gain_ft=_r(elevation_gain_ft),
            elevation_gain_m=_ft_to_m(elevation_gain_ft),
            # Pressure
            discharge_pressure_psi=_r(discharge_pressure_psi),
            pressure_head_ft=_r(pressure_head_ft),
            pressure_head_m=_ft_to_m(pressure_head_ft),
            # Friction
            pipe_friction_loss_ft=_r(pipe_friction_ft),
            pipe_friction_loss_m=_ft_to_m(pipe_friction_ft),
            minor_losses_ft=_r(minor_losses_ft),
            minor_losses_m=_ft_to_m(minor_losses_ft),
            total_friction_loss_ft=_r(total_friction_ft),
            total_friction_loss_m=_ft_to_m(total_friction_ft),
            # Aggregates
            static_lift_ft=_r(static_lift_ft),
            static_lift_m=_ft_to_m(static_lift_ft),
            subtotal_ft=_r(subtotal_ft),
            subtotal_m=_ft_to_m(subtotal_ft),
            safety_factor=safety_factor,
            # Result
            total_dynamic_head_ft=_r(tdh_ft),
            total_dynamic_head_m=_ft_to_m(tdh_ft),
            # Meta
            is_direct_input=is_direct,
            calculation_mode="direct" if is_direct else "computed",
        )
