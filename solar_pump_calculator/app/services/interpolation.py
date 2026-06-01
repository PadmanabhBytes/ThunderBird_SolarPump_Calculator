"""
Numerical interpolation utilities.

Functions
---------
linear_interpolate          — core piecewise-linear engine (used by all others)
interpolate_gpm_at_head     — US-unit: GPM from a head-vs-GPM curve (ft / GPM)
interpolate_friction_loss   — US-unit: friction loss from tabular data (GPM / ft)
fit_polynomial_curve        — optional polynomial smoother for noisy datasets

Legacy SI helpers (kept for backward compatibility, not used by the main pipeline)
interpolate_pump_head       — SI: head in metres from a (L/min, m) head-flow curve
interpolate_pump_efficiency — SI: efficiency fraction from a (L/min, eff) curve

Unit strategy
-------------
The pump evaluation pipeline works in US customary units throughout:
  - Head in feet (ft)
  - Flow in US gallons per minute (GPM)
  - Power in watts (W)

Use ``interpolate_gpm_at_head`` for all performance-curve lookups.
The SI helpers remain available for future multi-unit support.
"""

import logging
import math
from typing import List, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Type alias: a curve is a sequence of (x, y) ordered pairs
Curve = List[Tuple[float, float]]


# ── Core engine ───────────────────────────────────────────────────────────────

def linear_interpolate(
    x:           float,
    xs:          Sequence[float],
    ys:          Sequence[float],
    extrapolate: bool = False,
) -> float:
    """
    Piecewise linear interpolation at point *x* over the table (xs, ys).

    Args:
        x:           Query point.
        xs:          Monotonically increasing x values.
        ys:          Corresponding y values.
        extrapolate: If True, extend the boundary segments beyond the data range.
                     If False (default), clamp to the nearest boundary value.
                     Never pass True for pump performance lookups — clamping
                     is the correct behaviour at shutoff / runout conditions.

    Returns:
        Interpolated (or clamped) y value.

    Raises:
        ValueError: If xs and ys have different lengths or fewer than 2 points.
    """
    if len(xs) != len(ys):
        raise ValueError(
            f"xs and ys must have the same length (got {len(xs)} and {len(ys)})"
        )
    if len(xs) < 2:
        raise ValueError(
            f"At least 2 data points are required for interpolation (got {len(xs)})"
        )

    xs_arr = np.asarray(xs, dtype=float)
    ys_arr = np.asarray(ys, dtype=float)

    # Below lower bound
    if x <= xs_arr[0]:
        if extrapolate:
            slope = (ys_arr[1] - ys_arr[0]) / (xs_arr[1] - xs_arr[0])
            return float(ys_arr[0] + slope * (x - xs_arr[0]))
        return float(ys_arr[0])

    # Above upper bound
    if x >= xs_arr[-1]:
        if extrapolate:
            slope = (ys_arr[-1] - ys_arr[-2]) / (xs_arr[-1] - xs_arr[-2])
            return float(ys_arr[-1] + slope * (x - xs_arr[-1]))
        return float(ys_arr[-1])

    # Binary search for the bracketing interval
    idx  = int(np.searchsorted(xs_arr, x, side="right")) - 1
    x0, x1 = xs_arr[idx], xs_arr[idx + 1]
    y0, y1 = ys_arr[idx], ys_arr[idx + 1]

    t = (x - x0) / (x1 - x0)
    return float(y0 + t * (y1 - y0))


# ── US-unit pump performance curve interpolation ──────────────────────────────

def interpolate_gpm_at_head(
    head_ft:      float,
    head_rows_ft: Sequence[float],
    gpm_col:      Sequence[float],
    extrapolate:  bool = False,
) -> float:
    """
    Interpolate GPM at a given head from one power-level column of a
    performance dataset.

    This is the primary interpolation function for the pump evaluation engine.
    It operates in US customary units (ft, GPM) to match the performance
    CSV format.

    Args:
        head_ft:      Query head in feet.
        head_rows_ft: Sorted ascending sequence of head breakpoints (ft).
                      These are the ``head_ft`` column values from the CSV.
        gpm_col:      GPM values corresponding to each head breakpoint for
                      one specific power level column.
        extrapolate:  If True, linearly extrapolate beyond the dataset boundary.
                      Defaults to False (clamp) — do not extrapolate pump
                      performance beyond the measured envelope.

    Returns:
        Interpolated GPM value, clamped to ≥ 0.0.

    Example::

        head_rows = [20.0, 60.0, 100.0, 140.0, 180.0]
        gpm_at_400w = [9.5, 8.2, 6.4, 3.1, 0.0]
        gpm = interpolate_gpm_at_head(80.0, head_rows, gpm_at_400w)
        # → linear interpolation between 60 ft and 100 ft entries
    """
    raw = linear_interpolate(head_ft, head_rows_ft, gpm_col, extrapolate=extrapolate)
    result = max(0.0, raw)
    logger.debug(
        "interpolate_gpm_at_head: %.2f ft → %.3f GPM "
        "(table range %.1f–%.1f ft, extrapolate=%s)",
        head_ft, result,
        head_rows_ft[0] if head_rows_ft else float("nan"),
        head_rows_ft[-1] if head_rows_ft else float("nan"),
        extrapolate,
    )
    return result


# ── US-unit friction loss interpolation ───────────────────────────────────────

def interpolate_friction_loss(
    gpm:         float,
    data_points: List[Tuple[float, float]],
    extrapolate: bool = False,
) -> float:
    """
    Interpolate friction head loss (ft/100 ft) at the given flow rate.

    Args:
        gpm:          Query flow rate in US gallons per minute.
        data_points:  List of ``(gpm, loss_per_100ft)`` pairs from the
                      friction table, sorted by GPM ascending.
        extrapolate:  If True, linearly extrapolate beyond the table range.
                      If False (default), clamp to the boundary value.
                      Pass ``extrapolate=True`` only for mild out-of-range
                      queries; large extrapolation degrades accuracy.

    Returns:
        Friction loss in ft head per 100 ft of pipe.

    Raises:
        ValueError: If ``data_points`` is empty or has fewer than 2 entries.

    Example::

        pts = [(10, 0.204), (20, 0.734), (30, 1.561)]
        interpolate_friction_loss(15, pts)
        # → 0.469   (linear interpolation between 10 and 20 GPM)
    """
    if not data_points:
        raise ValueError("data_points must not be empty")
    if len(data_points) < 2:
        raise ValueError(
            f"At least 2 data points are required; got {len(data_points)}"
        )

    gpm_values  = [pt[0] for pt in data_points]
    loss_values = [pt[1] for pt in data_points]

    loss = linear_interpolate(gpm, gpm_values, loss_values, extrapolate=extrapolate)

    logger.debug(
        "interpolate_friction_loss: %.4f ft/100ft at %.2f GPM "
        "(table range %.1f–%.1f GPM)",
        loss, gpm, gpm_values[0], gpm_values[-1],
    )
    return loss


# ── Polynomial curve fitting (optional smoother) ──────────────────────────────

def fit_polynomial_curve(
    xs:     Sequence[float],
    ys:     Sequence[float],
    degree: int = 2,
) -> "np.poly1d":
    """
    Fit a polynomial of the given degree to the data.

    Returns a numpy ``poly1d`` callable so callers can evaluate it at any
    point.  Useful for smoothing noisy pump curve data before linear
    interpolation, or for generating intermediate breakpoints.

    Args:
        xs:     x values (e.g. head_ft breakpoints).
        ys:     y values (e.g. GPM values).
        degree: Polynomial degree (default 2 — quadratic, typical for pump curves).

    Returns:
        ``numpy.poly1d`` instance.
    """
    if len(xs) < degree + 1:
        raise ValueError(
            f"Need at least {degree + 1} points to fit a degree-{degree} polynomial "
            f"(got {len(xs)})"
        )
    coefficients = np.polyfit(xs, ys, degree)
    poly = np.poly1d(coefficients)
    logger.debug(
        "fit_polynomial_curve: degree=%d fitted over %d points",
        degree, len(xs),
    )
    return poly


# ── Legacy SI helpers (not used by the main pipeline) ────────────────────────
# These are retained for backward compatibility.
# New code should use interpolate_gpm_at_head (US units).

def interpolate_pump_head(flow_lpm: float, curve: Curve) -> float:
    """
    [Legacy — SI units]  Return pump head (m) at the given flow (L/min).

    Args:
        flow_lpm: Operating flow rate (L/min).
        curve:    List of (flow_lpm, head_m) points sorted by flow ascending.

    Returns:
        Head in metres at the operating point.
    """
    if not curve:
        raise ValueError("Pump head-flow curve is empty")

    flows = [pt[0] for pt in curve]
    heads = [pt[1] for pt in curve]
    head  = linear_interpolate(flow_lpm, flows, heads, extrapolate=False)
    logger.debug("interpolate_pump_head: %.2f m at %.1f L/min", head, flow_lpm)
    return head


def interpolate_pump_efficiency(flow_lpm: float, curve: Curve) -> float:
    """
    [Legacy — SI units]  Return pump efficiency (fraction 0–1) at the given
    flow from an efficiency-flow curve.

    Args:
        flow_lpm: Operating flow rate (L/min).
        curve:    List of (flow_lpm, efficiency_fraction) points sorted by flow.

    Returns:
        Efficiency as a fraction (0 to 1), clamped.
    """
    if not curve:
        raise ValueError("Pump efficiency curve is empty")

    flows = [pt[0] for pt in curve]
    effs  = [pt[1] for pt in curve]
    eff   = linear_interpolate(flow_lpm, flows, effs, extrapolate=False)
    eff   = max(0.0, min(1.0, eff))
    logger.debug("interpolate_pump_efficiency: %.3f at %.1f L/min", eff, flow_lpm)
    return eff
