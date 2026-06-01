"""
Friction loss data repository.

Loads pre-computed loss-per-100-ft tables from:
    data/friction/pvc.csv    (Schedule 40 PVC,   C = 150)
    data/friction/steel.csv  (Schedule 40 Steel, C = 120)

Data is indexed as:
    _index[material][nominal_diameter_in] -> [(gpm, loss_per_100ft), ...]
    sorted by GPM ascending so callers can binary-search for interpolation.

DB-migration note
-----------------
Replace each ``pd.read_csv(...)`` call in ``load()`` with an async ORM
query that returns the same (nominal_diameter_in, gpm, loss_per_100ft)
tuples.  The public interface — ``get_data_points``, ``nearest_nominal``,
etc. — stays identical.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from ..utils.exceptions import DataLoadError, DataNotFoundError

def _parse_diameter(col_name: str) -> float:
    s = col_name.replace('"', '').strip()
    if ' ' in s:
        whole, frac = s.split(' ')
        num, den = frac.split('/')
        return float(whole) + float(num) / float(den)
    elif '/' in s:
        num, den = s.split('/')
        return float(num) / float(den)
    else:
        return float(s)

logger = logging.getLogger(__name__)

# Canonical material keys used throughout the application
MATERIAL_PVC = "PVC"
MATERIAL_STEEL = "Steel"
SUPPORTED_MATERIALS = (MATERIAL_PVC, MATERIAL_STEEL)

# Schedule 40 nominal diameters (inches) present in the datasets
_NOMINAL_SIZES_IN: Tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0)

# Type alias: sorted list of (gpm, loss_per_100ft) tuples
_Curve = List[Tuple[float, float]]
_Index = Dict[str, Dict[float, _Curve]]      # material → diameter → curve


class FrictionRepository:
    """
    In-memory store for tabular friction loss data.

    Args:
        data_dir: Directory containing ``pvc.csv`` and ``steel.csv``.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._index: _Index = {}
        self._loaded: bool = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load PVC and Steel loss tables from CSV into memory."""
        file_map = {
            MATERIAL_PVC:   self._data_dir / "pvc.csv",
            MATERIAL_STEEL: self._data_dir / "steel.csv",
        }
        index: _Index = {}

        for material, path in file_map.items():
            try:
                df = pd.read_csv(path, comment="#")
                df.columns = df.columns.str.strip()

                material_index: Dict[float, _Curve] = {}
                
                # Check for wide format (matrix)
                if "GPM" in df.columns:
                    for col in df.columns:
                        if col in ("GPM", "GPH"):
                            continue
                        try:
                            diam = _parse_diameter(col)
                        except ValueError:
                            continue
                            
                        curve = []
                        for _, row in df.iterrows():
                            gpm = float(row["GPM"])
                            loss = float(row[col])
                            if loss > 0:  # Skip zero entries
                                curve.append((gpm, loss))
                                
                        if curve:
                            curve.sort(key=lambda x: x[0])
                            material_index[diam] = curve
                else:
                    # Legacy long format
                    df = df.dropna(subset=["nominal_diameter_in", "gpm", "loss_per_100ft"])
                    for diam, group in df.groupby("nominal_diameter_in"):
                        rows = group.sort_values("gpm")
                        material_index[float(diam)] = list(
                            zip(rows["gpm"].tolist(), rows["loss_per_100ft"].tolist())
                        )

                index[material] = material_index
                logger.info(
                    "FrictionRepository: loaded %s — %d diameter(s), %d data points from %s",
                    material,
                    len(material_index),
                    sum(len(v) for v in material_index.values()),
                    path,
                )
            except FileNotFoundError as exc:
                raise DataLoadError(
                    f"Friction table not found for '{material}': {path}"
                ) from exc
            except Exception as exc:
                raise DataLoadError(
                    f"Failed to load friction table for '{material}' from {path}: {exc}"
                ) from exc

        self._index = index
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_data_points(
        self,
        material: str,
        nominal_diameter_in: float,
    ) -> _Curve:
        """
        Return the sorted (gpm, loss_per_100ft) curve for the given material
        and nominal pipe diameter.

        Args:
            material:            "PVC" or "Steel".
            nominal_diameter_in: Nominal pipe diameter (inches).

        Returns:
            List of (gpm, loss_per_100ft) tuples sorted by GPM ascending.

        Raises:
            DataNotFoundError: If material or diameter is absent from the index.
        """
        self._ensure_loaded()

        mat_data = self._index.get(material)
        if mat_data is None:
            raise DataNotFoundError(
                f"Material '{material}' not found. "
                f"Supported: {', '.join(SUPPORTED_MATERIALS)}"
            )

        curve = mat_data.get(nominal_diameter_in)
        if curve is None:
            available = sorted(mat_data.keys())
            raise DataNotFoundError(
                f"No friction data for {material} {nominal_diameter_in}\" pipe. "
                f"Available diameters: {available}"
            )

        return curve

    def nearest_nominal_diameter(self, diameter_in: float) -> float:
        """
        Return the nearest nominal Schedule 40 diameter (inches) to the
        supplied internal or nominal diameter.

        Useful when the caller has a metric diameter that must be mapped to
        the closest standard US nominal size.
        """
        return min(_NOMINAL_SIZES_IN, key=lambda n: abs(n - diameter_in))

    def get_available_diameters(self, material: str) -> List[float]:
        """Return sorted list of nominal diameters available for *material*."""
        self._ensure_loaded()
        mat_data = self._index.get(material, {})
        return sorted(mat_data.keys())

    def get_supported_materials(self) -> List[str]:
        """Return list of material keys present in the loaded index."""
        self._ensure_loaded()
        return list(self._index.keys())

    @property
    def is_loaded(self) -> bool:
        return self._loaded
