#!/usr/bin/env python3
"""
Generate pump performance-curve CSV files from pump_catalog.csv specs.

Output: data/pumps/curves/<pump_id>.csv — one file per pump.

CSV format:
    head_ft, <W1>, <W2>, ..., <Wn>
    16.4,    2.1,  4.3,  ..., 9.5
    ...

Row = head operating point (ft).
Column header = power level (W), numeric string.
Cell value = achievable flow (US GPM) at that (head, power) point.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

CATALOG_PATH = Path(__file__).parent.parent / "data" / "pumps" / "pump_catalog.csv"
CURVES_DIR   = Path(__file__).parent.parent / "data" / "pumps" / "curves"

LPM_TO_GPM = 0.264172
M_TO_FT    = 3.28084


def _compute_gpm(
    head_ft: float,
    power_w: float,
    max_gpm: float,
    rated_power_w: float,
    max_head_ft: float,
) -> float:
    """
    Parametric model for solar submersible/surface pump output.

    Power exponent 0.6: sub-linear — flow rises quickly at first, levels off.
    Head  exponent 1.5: super-linear — head penalises flow more than linearly
                        near shutoff head, matching real pump curves.
    """
    if head_ft >= max_head_ft or power_w <= 0 or max_head_ft <= 0:
        return 0.0
    power_factor = min(1.0, power_w / rated_power_w) ** 0.6
    head_factor  = max(0.0, 1.0 - (head_ft / max_head_ft) ** 1.5)
    return round(max_gpm * power_factor * head_factor, 2)


def _power_levels(rated_w: float) -> list[float]:
    """Five steps at ~40/55/70/85/100 % of rated, rounded to nearest 25 W."""
    levels: list[float] = []
    for frac in (0.40, 0.55, 0.70, 0.85, 1.00):
        raw     = rated_w * frac
        rounded = round(raw / 25) * 25
        if rounded < 10:
            rounded = max(10, round(raw / 5) * 5)
        levels.append(float(max(1, rounded)))
    levels.append(float(int(rated_w)))  # always include exact rated
    return sorted({round(v) for v in levels})


def _head_levels(max_head_ft: float, min_head_ft: float, n: int = 7) -> list[float]:
    """n evenly spaced head breakpoints from min to max (inclusive)."""
    step = (max_head_ft - min_head_ft) / (n - 1)
    return [round(min_head_ft + step * i, 1) for i in range(n)]


def generate(catalog_path: Path, curves_dir: Path) -> None:
    curves_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(catalog_path)
    df.columns = df.columns.str.strip().str.lower()

    for _, row in df.iterrows():
        pump_id   = str(row["pump_id"]).strip()
        rated_w   = float(row["rated_power_w"])
        max_gpm   = float(row["max_flow_lpm"]) * LPM_TO_GPM
        max_hft   = float(row["max_head_m"]) * M_TO_FT
        min_hft   = max(5.0, float(row["min_head_m"]) * M_TO_FT)

        power_levels = _power_levels(rated_w)
        head_levels  = _head_levels(max_hft, min_hft)

        records: list[dict] = []
        for h in head_levels:
            rec: dict = {"head_ft": h}
            for p in power_levels:
                rec[str(int(p))] = _compute_gpm(h, p, max_gpm, rated_w, max_hft)
            records.append(rec)

        out_path = curves_dir / f"{pump_id}.csv"
        pd.DataFrame(records).to_csv(out_path, index=False)
        print(
            f"  {pump_id:5s} ({row['brand']} {row['model']}): "
            f"{len(head_levels)} head rows × {len(power_levels)} power cols"
        )

    print(f"\nDone — {len(df)} curve files written to {curves_dir}")


if __name__ == "__main__":
    generate(CATALOG_PATH, CURVES_DIR)
