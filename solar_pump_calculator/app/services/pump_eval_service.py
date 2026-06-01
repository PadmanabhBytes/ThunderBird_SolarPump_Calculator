"""
Pump evaluation service.

Evaluation strategy
-------------------
1. **Performance-curve** (preferred):
   When a real dataset exists in ``data/pumps/performance/<pump_id>.csv``,
   the service interpolates GPM at the required TDH for each power column,
   then finds the minimum wattage where GPM ≥ required.

2. **Envelope fallback** (degraded):
   When no performance CSV exists the service checks catalog
   ``max_head_ft`` and ``max_flow_gpm`` bounds only.
   Operating wattage is UNKNOWN in this mode.
   Results are flagged with ``curve_based=False`` and a warning is logged.

All inputs and outputs use US customary units (GPM, ft, W).

Interpolation
-------------
GPM at a given head is computed with piecewise-linear interpolation over
the ``head_rows_ft`` breakpoints for each power column.
``extrapolate=False`` clamps results to the dataset boundary — no GPM is
fabricated outside the measured operating envelope.

Concurrency
-----------
The service is stateless (read-only repository access) and safe for
concurrent use inside FastAPI's async request handlers.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..models.pump import Pump
from ..repositories.pump_repository import PerformanceCurve, PumpRepository
from ..services.interpolation import interpolate_gpm_at_head

logger = logging.getLogger(__name__)


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class OperatingPoint:
    """
    Result of evaluating a single pump SKU at a specific operating point.

    Returned by :meth:`PumpEvalService.evaluate_operating_point`.

    Fields
    ------
    pump_id : str
        Pump identifier from the catalog.
    operating_wattage_w : Optional[float]
        Minimum power (W) at which this pump delivers ``achievable_gpm`` ≥
        ``target_gpm`` at ``selected_head_ft``.
        None when:
          - The pump cannot meet the target even at maximum power, OR
          - No performance dataset is available (envelope fallback).
    achievable_gpm : Optional[float]
        GPM delivered at ``operating_wattage_w`` and ``selected_head_ft``.
        When ``meets_flow_requirement`` is False this contains the maximum
        GPM the pump can achieve at that head (for sizing guidance).
    selected_head_ft : float
        Head used for interpolation — equal to the requested ``target_tdh_ft``.
    meets_head_requirement : bool
        True if the pump dataset covers the requested head.
    meets_flow_requirement : bool
        True if the pump can deliver ≥ ``target_gpm`` at ``selected_head_ft``.
    curve_based : bool
        True  → result derived from performance-curve interpolation.
        False → result derived from catalog envelope bounds only (degraded).
    warnings : List[str]
        Non-fatal issues encountered during evaluation.
    """
    pump_id:                 str
    operating_wattage_w:     Optional[float]
    achievable_gpm:          Optional[float]
    selected_head_ft:        float
    meets_head_requirement:  bool
    meets_flow_requirement:  bool
    curve_based:             bool
    warnings:                List[str] = field(default_factory=list)


@dataclass
class PumpEvalResult:
    """
    Full evaluation result for one pump, used by the ranking pipeline.

    Returned by :meth:`PumpEvalService.evaluate_all`.
    """
    pump:                    Pump
    meets_head_requirement:  bool
    meets_flow_requirement:  bool
    is_eligible:             bool
    # Margin as percentage of the required value (positive = headroom)
    head_margin_percent:     float
    flow_margin_percent:     float
    # Shortfall (> 0 only when requirement is not met)
    head_shortfall_ft:       float = 0.0
    flow_shortfall_gpm:      float = 0.0
    # Curve-based operating-point data (None when no dataset is available)
    operating_wattage_w:     Optional[float] = None
    achievable_gpm:          Optional[float] = None
    curve_based_evaluation:  bool            = False
    # Non-fatal issues encountered during evaluation
    evaluation_warnings:     List[str]       = field(default_factory=list)


# ── Low-level curve helpers ───────────────────────────────────────────────────

def _gpm_at_head(
    curve:            PerformanceCurve,
    power_col_idx:    int,
    required_head_ft: float,
) -> float:
    """
    Interpolate GPM for one power column at the required head.

    Delegates to ``interpolate_gpm_at_head`` which clamps to the
    dataset boundary (no extrapolation) and returns ≥ 0.0.
    """
    return interpolate_gpm_at_head(
        head_ft=required_head_ft,
        head_rows_ft=curve.head_rows_ft,
        gpm_col=curve.gpm_column(power_col_idx),
        extrapolate=False,
    )


def _evaluate_curve(
    curve:             PerformanceCurve,
    required_head_ft:  float,
    required_flow_gpm: float,
) -> Tuple[bool, bool, Optional[float], Optional[float]]:
    """
    Evaluate whether the pump meets head and flow requirements.

    Walk power levels from lowest to highest to find the **minimum** wattage
    that achieves the required GPM at the required head.

    Returns
    -------
    (meets_head, meets_flow, operating_wattage_w, achievable_gpm)

    - ``meets_head`` is False when the dataset shows 0 GPM at max power,
      meaning the required head is beyond the pump's shutoff head.
    - When ``meets_head`` is True but ``meets_flow`` is False,
      ``achievable_gpm`` is the maximum flow at that head (at full power)
      so callers can show how close the pump comes.
    """
    # Head feasibility: check maximum-power column
    max_gpm_at_head = _gpm_at_head(curve, -1, required_head_ft)
    if max_gpm_at_head <= 0.0:
        return False, False, None, None

    # Walk power columns low → high; return first that meets the flow target
    for col_idx, power_w in enumerate(curve.power_levels_w):
        gpm = _gpm_at_head(curve, col_idx, required_head_ft)
        if gpm >= required_flow_gpm:
            return True, True, power_w, gpm

    # Head OK but insufficient flow even at maximum power
    return True, False, None, max_gpm_at_head


# ── Service ───────────────────────────────────────────────────────────────────

class PumpEvalService:
    """
    Dataset-driven pump evaluation service.

    Args:
        pump_repo: Loaded :class:`PumpRepository` instance.
    """

    def __init__(self, pump_repo: PumpRepository) -> None:
        self._repo = pump_repo

    # ── Public: bilinear curve interpolation ──────────────────────────────────

    def gpm_at_head_and_watts(
        self,
        curve:   PerformanceCurve,
        head_ft: float,
        watts:   float,
    ) -> float:
        """
        Bilinear interpolation: GPM at (head_ft, watts).

        First interpolates in the head direction for each of the two bracketing
        power columns, then blends those GPM values in the watts direction.
        Result is clamped to ≥ 0.
        """
        pw = curve.power_levels_w
        # Clamp inputs to curve range
        watts_clamped = max(pw[0], min(pw[-1], watts))

        # Find bracketing power columns
        pi = len([p for p in pw if p <= watts_clamped]) - 1
        pi = max(0, min(len(pw) - 2, pi))
        p0, p1 = pw[pi], pw[pi + 1]
        t_w = (watts_clamped - p0) / (p1 - p0) if p1 > p0 else 0.0

        # Interpolate GPM at target head for each bracketing power column
        gpm0 = _gpm_at_head(curve, pi,     head_ft)
        gpm1 = _gpm_at_head(curve, pi + 1, head_ft)

        return max(0.0, round(gpm0 + t_w * (gpm1 - gpm0), 2))

    def size_panels_for_pump(
        self,
        pump_id:                 str,
        tdh_ft:                  float,
        required_gpm:            float,
        panel_wattage_w:         float,
        stc_efficiency_loss:     float           = 0.075,
        max_panels:              int             = 20,
        display_panel_wattage_w: Optional[float] = None,
    ) -> Tuple[Optional[int], Optional[float]]:
        """
        Find the minimum panel count N such that:

            gpm_bilinear(tdh_ft, N × panel_wattage_w) × (1 − stc_loss) ≥ required_gpm

        When display_panel_wattage_w is provided, the returned raw_gpm is
        computed at N × display_panel_wattage_w (actual panel rating) rather
        than N × panel_wattage_w (irradiance-adjusted sizing wattage).

        Returns (n_panels, raw_gpm) — raw GPM before any STC derating.
        Returns (None, None) when no panel count up to max_panels satisfies the requirement.
        """
        curve = self._repo.get_performance_curve(pump_id)
        if curve is None:
            return None, None

        for n in range(1, max_panels + 1):
            raw_gpm       = self.gpm_at_head_and_watts(curve, tdh_ft, n * panel_wattage_w)
            effective_gpm = raw_gpm * (1.0 - stc_efficiency_loss)
            if effective_gpm >= required_gpm:
                if display_panel_wattage_w is not None:
                    display_raw = self.gpm_at_head_and_watts(curve, tdh_ft, n * display_panel_wattage_w)
                    return n, round(display_raw, 2)
                return n, round(raw_gpm, 2)

        return None, None

    # ── Public: single-pump operating point ───────────────────────────────────

    def evaluate_operating_point(
        self,
        pump_id:        str,
        target_gpm:     float,
        target_tdh_ft:  float,
    ) -> OperatingPoint:
        """
        Evaluate a single pump SKU at an exact operating point.

        Uses the performance dataset when available; falls back to catalog
        envelope bounds otherwise.

        Args:
            pump_id:       Pump identifier matching ``pump_catalog.csv``.
            target_gpm:    Required flow rate (US GPM).
            target_tdh_ft: Required Total Dynamic Head (ft).

        Returns:
            :class:`OperatingPoint` with operating wattage, achievable GPM,
            and evaluation metadata.

        Raises:
            DataNotFoundError: If ``pump_id`` is not in the catalog.
        """
        from ..utils.exceptions import DataNotFoundError  # avoid circular import

        pump  = self._repo.get_pump_by_id(pump_id)
        curve = self._repo.get_performance_curve(pump_id)

        if curve is not None:
            return self._operating_point_from_curve(pump_id, curve, target_gpm, target_tdh_ft)

        return self._operating_point_from_envelope(pump, target_gpm, target_tdh_ft)

    # ── Public: evaluate a pre-filtered pump list ─────────────────────────────

    def evaluate_pumps(
        self,
        pumps:             List[Pump],
        required_flow_gpm: float,
        required_head_ft:  float,
    ) -> List[PumpEvalResult]:
        """
        Evaluate a caller-supplied pump list (e.g. after pre-filtering).

        Same logic as ``evaluate_all`` but works on an arbitrary list rather
        than fetching all pumps from the repository.
        """
        results = [
            self._evaluate_pump(pump, required_flow_gpm, required_head_ft)
            for pump in pumps
        ]

        eligible_count = sum(1 for r in results if r.is_eligible)
        curve_based    = sum(1 for r in results if r.curve_based_evaluation)

        logger.info(
            "PumpEval (filtered list): %d / %d eligible | "
            "%d curve-based, %d envelope-only | Q=%.1f GPM, H=%.2f ft",
            eligible_count, len(results),
            curve_based, len(results) - curve_based,
            required_flow_gpm, required_head_ft,
        )
        return results

    # ── Public: full catalog evaluation ───────────────────────────────────────

    def evaluate_all(
        self,
        required_flow_gpm: float,
        required_head_ft:  float,
    ) -> List[PumpEvalResult]:
        """
        Evaluate every pump in the catalog against the given operating point.

        Uses performance-curve interpolation when a dataset is available;
        falls back to catalog envelope bounds otherwise.

        Returns results for **all** pumps (eligible or not) so callers can
        report total evaluated vs. eligible counts.

        Args:
            required_flow_gpm: Target flow rate (US GPM).
            required_head_ft:  Required Total Dynamic Head (ft).

        Returns:
            List of :class:`PumpEvalResult` — one entry per catalog pump.
        """
        all_pumps = self._repo.get_all_pumps()
        results = [
            self._evaluate_pump(pump, required_flow_gpm, required_head_ft)
            for pump in all_pumps
        ]

        eligible_count = sum(1 for r in results if r.is_eligible)
        curve_based    = sum(1 for r in results if r.curve_based_evaluation)

        logger.info(
            "PumpEval complete: %d / %d eligible | "
            "%d curve-based, %d envelope-only | "
            "Q=%.1f GPM, H=%.2f ft",
            eligible_count, len(results),
            curve_based, len(results) - curve_based,
            required_flow_gpm, required_head_ft,
        )
        return results

    # ── Private: operating-point helpers ─────────────────────────────────────

    def _operating_point_from_curve(
        self,
        pump_id:        str,
        curve:          PerformanceCurve,
        target_gpm:     float,
        target_tdh_ft:  float,
    ) -> OperatingPoint:
        """Derive operating point from a real performance dataset."""
        warnings: List[str] = []

        # Warn if the requested head is outside the dataset's envelope
        if target_tdh_ft < curve.min_head_ft:
            warnings.append(
                f"Requested TDH ({target_tdh_ft:.1f} ft) is below the dataset "
                f"minimum ({curve.min_head_ft:.1f} ft). "
                "Result clamped to boundary — verify operating conditions."
            )
        elif target_tdh_ft > curve.max_head_ft:
            warnings.append(
                f"Requested TDH ({target_tdh_ft:.1f} ft) exceeds the dataset "
                f"maximum ({curve.max_head_ft:.1f} ft). "
                "Result clamped to boundary — verify operating conditions."
            )

        meets_head, meets_flow, op_w, achiev_gpm = _evaluate_curve(
            curve, target_tdh_ft, target_gpm,
        )

        logger.debug(
            "evaluate_operating_point(%s): curve-based | "
            "head_ok=%s flow_ok=%s op_w=%s achievable_gpm=%s",
            pump_id, meets_head, meets_flow, op_w, achiev_gpm,
        )

        return OperatingPoint(
            pump_id=pump_id,
            operating_wattage_w=op_w,
            achievable_gpm=round(achiev_gpm, 2) if achiev_gpm is not None else None,
            selected_head_ft=target_tdh_ft,
            meets_head_requirement=meets_head,
            meets_flow_requirement=meets_flow,
            curve_based=True,
            warnings=warnings,
        )

    @staticmethod
    def _operating_point_from_envelope(
        pump:           Pump,
        target_gpm:     float,
        target_tdh_ft:  float,
    ) -> OperatingPoint:
        """
        Derive operating point from catalog envelope bounds only.

        This path is taken when no performance dataset exists for the pump.
        Operating wattage cannot be determined; result is flagged as degraded.
        """
        meets_head = pump.max_head_ft >= target_tdh_ft
        meets_flow = pump.max_flow_gpm >= target_gpm

        warning = (
            f"No performance dataset found for pump '{pump.pump_id}'. "
            "Evaluation uses catalog envelope bounds only — "
            "operating wattage is unavailable and accuracy is reduced. "
            f"Add 'data/pumps/performance/{pump.pump_id}.csv' to enable curve-based evaluation."
        )
        logger.debug(
            "evaluate_operating_point(%s): envelope fallback | "
            "head_ok=%s flow_ok=%s",
            pump.pump_id, meets_head, meets_flow,
        )

        return OperatingPoint(
            pump_id=pump.pump_id,
            operating_wattage_w=None,
            achievable_gpm=pump.max_flow_gpm if meets_head else None,
            selected_head_ft=target_tdh_ft,
            meets_head_requirement=meets_head,
            meets_flow_requirement=meets_flow,
            curve_based=False,
            warnings=[warning],
        )

    # ── Private: full-catalog evaluation helpers ──────────────────────────────

    def _evaluate_pump(
        self,
        pump:              Pump,
        required_flow_gpm: float,
        required_head_ft:  float,
    ) -> PumpEvalResult:
        """Route a single pump to curve-based or envelope evaluation."""
        head_margin_pct = (
            (pump.max_head_ft - required_head_ft) / required_head_ft * 100.0
            if required_head_ft > 0 else 0.0
        )
        flow_margin_pct = (
            (pump.max_flow_gpm - required_flow_gpm) / required_flow_gpm * 100.0
            if required_flow_gpm > 0 else 0.0
        )

        curve = self._repo.get_performance_curve(pump.pump_id)

        if curve is not None:
            return self._curve_result(
                pump, curve, required_flow_gpm, required_head_ft,
                head_margin_pct, flow_margin_pct,
            )

        return self._envelope_result(
            pump, required_flow_gpm, required_head_ft,
            head_margin_pct, flow_margin_pct,
        )

    def _curve_result(
        self,
        pump:               Pump,
        curve:              PerformanceCurve,
        required_flow_gpm:  float,
        required_head_ft:   float,
        head_margin_pct:    float,
        flow_margin_pct:    float,
    ) -> PumpEvalResult:
        """Build a PumpEvalResult from curve interpolation."""
        eval_warnings: List[str] = []

        # Out-of-range head warning
        if required_head_ft > curve.max_head_ft:
            eval_warnings.append(
                f"Required head ({required_head_ft:.1f} ft) exceeds "
                f"dataset maximum ({curve.max_head_ft:.1f} ft). "
                "Result is extrapolated — accuracy reduced."
            )

        meets_head, meets_flow, op_w, achiev_gpm = _evaluate_curve(
            curve, required_head_ft, required_flow_gpm,
        )

        # Propagate any dataset-load warnings so they surface in the response
        load_warnings = self._repo.get_load_warnings(pump.pump_id)
        eval_warnings.extend(load_warnings)

        return PumpEvalResult(
            pump=pump,
            meets_head_requirement=meets_head,
            meets_flow_requirement=meets_flow,
            is_eligible=meets_head and meets_flow,
            head_margin_percent=round(head_margin_pct, 1),
            flow_margin_percent=round(flow_margin_pct, 1),
            head_shortfall_ft=round(max(0.0, required_head_ft - pump.max_head_ft), 2),
            flow_shortfall_gpm=round(max(0.0, required_flow_gpm - pump.max_flow_gpm), 1),
            operating_wattage_w=op_w,
            achievable_gpm=round(achiev_gpm, 2) if achiev_gpm is not None else None,
            curve_based_evaluation=True,
            evaluation_warnings=eval_warnings,
        )

    @staticmethod
    def _envelope_result(
        pump:              Pump,
        required_flow_gpm: float,
        required_head_ft:  float,
        head_margin_pct:   float,
        flow_margin_pct:   float,
    ) -> PumpEvalResult:
        """Build a PumpEvalResult from catalog envelope bounds (no curve data)."""
        meets_head = pump.max_head_ft >= required_head_ft
        meets_flow = pump.max_flow_gpm >= required_flow_gpm

        warning = (
            f"No performance dataset for '{pump.pump_id}'. "
            "Evaluation uses catalog envelope bounds — operating wattage unknown. "
            f"Add 'data/pumps/performance/{pump.pump_id}.csv' to enable full evaluation."
        )

        return PumpEvalResult(
            pump=pump,
            meets_head_requirement=meets_head,
            meets_flow_requirement=meets_flow,
            is_eligible=meets_head and meets_flow,
            head_margin_percent=round(head_margin_pct, 1),
            flow_margin_percent=round(flow_margin_pct, 1),
            head_shortfall_ft=round(max(0.0, required_head_ft - pump.max_head_ft), 2),
            flow_shortfall_gpm=round(max(0.0, required_flow_gpm - pump.max_flow_gpm), 1),
            evaluation_warnings=[warning],
        )
